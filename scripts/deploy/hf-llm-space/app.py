#!/usr/bin/env python3
"""
Nomos42 LLM Space — OpenAI-Compatible Inference Server
=======================================================
Self-hosted GGUF model on HF Spaces FREE CPU tier (16 GB RAM).
Exposes /v1/chat/completions for use by trading floor agents as fallback.

Model: Qwen3-1.7B-Q4_K_M.gguf (~1.2 GB) — best quality/size for CPU free tier.
Alternatives commented below: Qwen3-0.6B (ultra-small), Llama-3.2-1B, SmolLM2-1.7B.

HF Space hardware: 2 vCPU, 16 GB RAM (free tier)
Inference speed: ~5-15 tok/s on CPU (adequate for single-agent JSON responses ≤512 tok)

Endpoints:
  GET  /          → status + model info (Gradio UI)
  POST /v1/chat/completions → OpenAI-compatible (handled by FastAPI mounted on Gradio)
  GET  /v1/models           → list loaded models
  GET  /health              → {status: "ok", model: "...", ...}

Usage from api_pool.py:
  Add "self_hosted" provider with base_url = "https://YOUR-SPACE.hf.space"
  and model = "Qwen/Qwen3-1.7B" (or whatever HF model ID maps to this Space).
"""

import os
import json
import time
import threading
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

import gradio as gr
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ─── llama-cpp-python ────────────────────────────────────────────────────────
try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False
    logging.warning("llama-cpp-python not installed — inference disabled")

# ─── Configuration ────────────────────────────────────────────────────────────

# Model selection — change MODEL_REPO + MODEL_FILE to swap models.
# All tested options below:
#
#   1. Qwen3-1.7B Q4_K_M  — 1.2 GB, recommended for free CPU tier
#      REPO: "Qwen/Qwen3-1.7B-GGUF"   FILE: "qwen3-1.7b-q4_k_m.gguf"
#
#   2. Qwen3-0.6B Q4_K_M  — 0.5 GB, ultra-small if space is tight
#      REPO: "Qwen/Qwen3-0.6B-GGUF"   FILE: "qwen3-0.6b-q4_k_m.gguf"
#
#   3. SmolLM2-1.7B Q4    — 1.1 GB, HuggingFace's own tiny model
#      REPO: "HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF"  FILE: "smollm2-1.7b-instruct-q4_k_m.gguf"
#
#   4. Llama-3.2-1B Q4    — 0.8 GB, Meta's smallest Llama
#      REPO: "bartowski/Llama-3.2-1B-Instruct-GGUF"  FILE: "Llama-3.2-1B-Instruct-Q4_K_M.gguf"
#
#   5. Phi-4-mini Q4      — 2.5 GB, Microsoft's Phi-4 mini (3.8B params)
#      REPO: "microsoft/Phi-4-mini-instruct-GGUF"  FILE: "Phi-4-mini-instruct-q4.gguf"
#      NOTE: needs 4+ GB RAM headroom; fits on 16 GB free tier

MODEL_REPO = os.environ.get("MODEL_REPO", "unsloth/Qwen3-1.7B-GGUF")
MODEL_FILE = os.environ.get("MODEL_FILE", "Qwen3-1.7B-Q4_K_M.gguf")
MODEL_DISPLAY = os.environ.get("MODEL_DISPLAY", "Qwen/Qwen3-1.7B")

# Server config
N_CTX = int(os.environ.get("N_CTX", "2048"))       # context window
N_THREADS = int(os.environ.get("N_THREADS", "2"))   # CPU threads (HF free = 2 vCPU)
MAX_TOKENS_DEFAULT = int(os.environ.get("MAX_TOKENS", "512"))
TEMPERATURE_DEFAULT = float(os.environ.get("TEMPERATURE", "0.3"))

# Paths
MODEL_DIR = Path("/tmp/models")
MODEL_PATH = MODEL_DIR / MODEL_FILE

# ─── State ────────────────────────────────────────────────────────────────────

llm: Optional["Llama"] = None
model_load_status = "not_started"
model_load_error = ""
load_lock = threading.Lock()
request_count = 0
start_time = time.time()


def download_model():
    """Download GGUF model from HuggingFace Hub."""
    global model_load_status, model_load_error
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if MODEL_PATH.exists():
        size_gb = MODEL_PATH.stat().st_size / 1e9
        logging.info(f"Model already cached: {MODEL_PATH} ({size_gb:.2f} GB)")
        return True

    model_load_status = "downloading"
    try:
        from huggingface_hub import hf_hub_download
        logging.info(f"Downloading {MODEL_REPO} / {MODEL_FILE} ...")
        hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILE,
            local_dir=str(MODEL_DIR),
        )
        size_gb = MODEL_PATH.stat().st_size / 1e9
        logging.info(f"Downloaded: {MODEL_PATH} ({size_gb:.2f} GB)")
        return True
    except Exception as e:
        model_load_error = str(e)
        model_load_status = "download_failed"
        logging.error(f"Download failed: {e}")
        return False


def load_model():
    """Load GGUF model into llama-cpp-python."""
    global llm, model_load_status, model_load_error
    if not HAS_LLAMA:
        model_load_status = "no_llama_cpp"
        model_load_error = "llama-cpp-python not installed"
        return

    with load_lock:
        if llm is not None:
            return

        if not download_model():
            return

        model_load_status = "loading"
        try:
            logging.info(f"Loading model from {MODEL_PATH} ...")
            t0 = time.time()
            llm = Llama(
                model_path=str(MODEL_PATH),
                n_ctx=N_CTX,
                n_threads=N_THREADS,
                n_gpu_layers=0,          # CPU-only
                verbose=False,
                chat_format="chatml",    # works for Qwen3, SmolLM2, Llama3.2
            )
            elapsed = time.time() - t0
            model_load_status = "ready"
            logging.info(f"Model loaded in {elapsed:.1f}s")
        except Exception as e:
            model_load_error = str(e)
            model_load_status = "load_failed"
            logging.error(f"Model load failed: {e}")


# Start model loading in background thread so Gradio UI starts immediately
threading.Thread(target=load_model, daemon=True).start()


# ─── FastAPI app (mounted on Gradio) ─────────────────────────────────────────

api = FastAPI(title="Nomos42 LLM API", version="1.0.0")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = MODEL_DISPLAY
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None


@api.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_DISPLAY,
                "object": "model",
                "created": int(start_time),
                "owned_by": "nomos42",
                "status": model_load_status,
            }
        ]
    }


@api.get("/health")
async def health():
    return {
        "status": "ok" if model_load_status == "ready" else model_load_status,
        "model": MODEL_DISPLAY,
        "model_file": MODEL_FILE,
        "load_status": model_load_status,
        "requests_served": request_count,
        "uptime_seconds": int(time.time() - start_time),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, request: Request):
    global request_count

    if model_load_status != "ready" or llm is None:
        raise HTTPException(
            status_code=503,
            detail=f"Model not ready: {model_load_status}. Error: {model_load_error}"
        )

    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    max_tokens = req.max_tokens or MAX_TOKENS_DEFAULT
    temperature = req.temperature if req.temperature is not None else TEMPERATURE_DEFAULT
    stop = req.stop or []

    try:
        t0 = time.time()
        output = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop if stop else None,
        )
        elapsed = time.time() - t0
        request_count += 1

        # Format as OpenAI-compatible response
        choice = output["choices"][0]
        usage = output.get("usage", {})

        return {
            "id": f"chatcmpl-{int(time.time()*1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": MODEL_DISPLAY,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": choice["message"]["content"],
                    },
                    "finish_reason": choice.get("finish_reason", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "x_latency_seconds": round(elapsed, 2),
        }

    except Exception as e:
        logging.error(f"Inference error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Gradio UI ────────────────────────────────────────────────────────────────

def status_fn():
    uptime = int(time.time() - start_time)
    h, m, s = uptime // 3600, (uptime % 3600) // 60, uptime % 60
    lines = [
        f"Model: {MODEL_DISPLAY}",
        f"Status: {model_load_status}",
        f"Requests served: {request_count}",
        f"Uptime: {h:02d}:{m:02d}:{s:02d}",
        f"Context: {N_CTX} tokens | Threads: {N_THREADS}",
        "",
        "API endpoints:",
        "  POST /v1/chat/completions (OpenAI-compatible)",
        "  GET  /v1/models",
        "  GET  /health",
        "",
        "For trading floor use, add to api_pool.py:",
        '  "self_hosted": ProviderConfig(',
        f'      base_url="https://YOUR-SPACE.hf.space",',
        f'      models=["{MODEL_DISPLAY}"],',
        '  )',
    ]
    if model_load_error:
        lines.append(f"\nError: {model_load_error}")
    return "\n".join(lines)


def chat_fn(message: str, history: list):
    """Simple chat interface for testing the model. gradio 5.x passes history as list of dicts."""
    if model_load_status != "ready" or llm is None:
        return f"Model not ready: {model_load_status}"

    messages = []
    for item in history:
        if isinstance(item, dict):
            messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            # Legacy tuple format (user, assistant)
            if item[0]:
                messages.append({"role": "user", "content": item[0]})
            if item[1]:
                messages.append({"role": "assistant", "content": item[1]})
    messages.append({"role": "user", "content": message})

    try:
        output = llm.create_chat_completion(
            messages=messages,
            max_tokens=512,
            temperature=0.7,
        )
        return output["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"


with gr.Blocks(title="Nomos42 LLM Space") as demo:
    gr.Markdown(f"## Nomos42 LLM — {MODEL_DISPLAY}")
    gr.Markdown("OpenAI-compatible inference server for trading floor agents.")

    with gr.Tab("Status"):
        # gradio 5.x removed the 'every' param on Textbox; use a button to refresh
        status_box = gr.Textbox(value=status_fn(), label="Server Status",
                                lines=20, interactive=False)
        refresh_btn = gr.Button("Refresh Status")
        refresh_btn.click(fn=status_fn, outputs=status_box)

    with gr.Tab("Test Chat"):
        chat = gr.ChatInterface(chat_fn)

    gr.Markdown("**API:** POST `/v1/chat/completions` (OpenAI-compatible)")


# Mount FastAPI on Gradio
app = gr.mount_gradio_app(api, demo, path="/")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
