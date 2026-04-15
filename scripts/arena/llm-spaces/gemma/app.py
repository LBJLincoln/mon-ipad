#!/usr/bin/env python3
"""
Nomos42 Gemma-2-2B CPU LLM Space — Pure FastAPI, OpenAI-compatible.
Model: gemma-2-2b-it GGUF Q4_K_M (~1.6 GB)
"""
import os
import time
import threading
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gemma2-2b")

MODEL_REPO = os.environ.get("MODEL_REPO", "bartowski/gemma-2-2b-it-GGUF")
MODEL_FILE = os.environ.get("MODEL_FILE", "gemma-2-2b-it-Q4_K_M.gguf")
MODEL_DISPLAY = os.environ.get("MODEL_DISPLAY", "gemma-2-2b-it")
CHAT_FORMAT = os.environ.get("CHAT_FORMAT", "gemma")

N_CTX = int(os.environ.get("N_CTX", "2048"))
N_THREADS = int(os.environ.get("N_THREADS", "2"))
MAX_TOKENS_DEFAULT = int(os.environ.get("MAX_TOKENS", "400"))
TEMPERATURE_DEFAULT = float(os.environ.get("TEMPERATURE", "0.7"))

MODEL_DIR = Path("/tmp/models")
MODEL_PATH = MODEL_DIR / MODEL_FILE

llm: Optional["Llama"] = None
model_load_status = "not_started"
model_load_error = ""
load_lock = threading.Lock()
request_count = 0
start_time = time.time()


def download_model() -> bool:
    global model_load_status, model_load_error
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists():
        log.info(f"Model already cached: {MODEL_PATH} ({MODEL_PATH.stat().st_size/1e6:.1f} MB)")
        return True
    model_load_status = "downloading"
    try:
        from huggingface_hub import hf_hub_download
        log.info(f"Downloading {MODEL_REPO}/{MODEL_FILE} ...")
        hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE, local_dir=str(MODEL_DIR))
        log.info(f"Downloaded: {MODEL_PATH} ({MODEL_PATH.stat().st_size/1e6:.1f} MB)")
        return True
    except Exception as e:
        model_load_error = str(e)
        model_load_status = "download_failed"
        log.exception("Download failed")
        return False


def load_model():
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
            t0 = time.time()
            llm = Llama(
                model_path=str(MODEL_PATH),
                n_ctx=N_CTX,
                n_threads=N_THREADS,
                n_gpu_layers=0,
                verbose=False,
                chat_format=CHAT_FORMAT,
            )
            model_load_status = "ready"
            log.info(f"Model loaded in {time.time()-t0:.1f}s")
        except Exception as e:
            model_load_error = str(e)
            model_load_status = "load_failed"
            log.exception("Load failed")


threading.Thread(target=load_model, daemon=True).start()


app = FastAPI(title=f"Nomos42 {MODEL_DISPLAY} CPU", version="1.0.0")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = MODEL_DISPLAY
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stop: Optional[List[str]] = None
    stream: Optional[bool] = False


@app.get("/")
async def root():
    return {
        "model": MODEL_DISPLAY,
        "ready": model_load_status == "ready",
        "load_status": model_load_status,
        "error": model_load_error or None,
        "requests_served": request_count,
        "uptime_seconds": int(time.time() - start_time),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": ["/", "/health", "/v1/models", "/chat/completions", "/v1/chat/completions"],
    }


@app.get("/health")
async def health():
    return await root()


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{
            "id": MODEL_DISPLAY,
            "object": "model",
            "created": int(start_time),
            "owned_by": "nomos42",
            "status": model_load_status,
        }],
    }


async def _complete(req: ChatCompletionRequest):
    global request_count
    if model_load_status != "ready" or llm is None:
        raise HTTPException(status_code=503, detail=f"Model not ready: {model_load_status}. Error: {model_load_error}")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    max_tokens = req.max_tokens or MAX_TOKENS_DEFAULT
    temperature = req.temperature if req.temperature is not None else TEMPERATURE_DEFAULT
    stop = req.stop or None

    try:
        t0 = time.time()
        out = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop,
        )
        elapsed = time.time() - t0
        request_count += 1
        choice = out["choices"][0]
        usage = out.get("usage", {})
        return {
            "id": f"chatcmpl-{int(time.time()*1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": MODEL_DISPLAY,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": choice["message"]["content"],
                },
                "finish_reason": choice.get("finish_reason", "stop"),
            }],
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "x_latency_seconds": round(elapsed, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Inference error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    return await _complete(req)


@app.post("/v1/chat/completions")
async def chat_completions_v1(req: ChatCompletionRequest):
    return await _complete(req)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
