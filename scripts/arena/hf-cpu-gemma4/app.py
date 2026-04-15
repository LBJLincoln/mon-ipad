"""Nomos42 CPU LLM agent — Gemma 4 E4B (Q4_K_XL).

Deploys a frontier-class open model on free-tier HF CPU Space (16GB / 2 vCPU).
Exposes /api/decide(system, user) -> {text} for the Trading Floor to call as
agent T12. First of a planned 4-5 self-hosted CPU LLM agents.

Model: unsloth/gemma-4-E4B-it-GGUF (UD-Q4_K_XL, 5.10GB)
Inference: llama-cpp-python (CPU only)
Cadence: ~5-12s/call on 2 vCPU; OK for day-bucket-v3 (~1925 calls/season)
"""
from __future__ import annotations
import os, time, json, threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

MODEL_REPO = os.environ.get("MODEL_REPO", "unsloth/gemma-4-E4B-it-GGUF")
MODEL_FILE = os.environ.get("MODEL_FILE", "gemma-4-E4B-it-UD-Q4_K_XL.gguf")
N_CTX = int(os.environ.get("N_CTX", "4096"))
N_THREADS = int(os.environ.get("N_THREADS", "2"))

_llm: Llama | None = None
_load_error: str | None = None
_load_lock = threading.Lock()
_stats = {"calls": 0, "errors": 0, "total_tokens_out": 0, "total_seconds": 0.0}


def _load_model() -> None:
    global _llm, _load_error
    with _load_lock:
        if _llm is not None or _load_error is not None:
            return
        try:
            path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE)
            _llm = Llama(
                model_path=path,
                n_ctx=N_CTX,
                n_threads=N_THREADS,
                n_batch=256,
                verbose=False,
                seed=42,
            )
        except Exception as e:
            _load_error = f"load failed: {e}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_load_model, daemon=True).start()
    yield


app = FastAPI(title="Nomos42 CPU Gemma-4 Agent", lifespan=lifespan)


class DecideIn(BaseModel):
    system: str = ""
    user: str
    max_tokens: int = 600
    temperature: float = 0.3
    json_only: bool = True


@app.get("/")
def root():
    return {
        "service": "nomos-cpu-gemma4",
        "model": f"{MODEL_REPO}/{MODEL_FILE}",
        "ready": _llm is not None,
        "load_error": _load_error,
        "stats": _stats,
        "endpoints": ["/api/health", "/api/decide", "/api/stats"],
    }


@app.get("/api/health")
def health():
    return {"ready": _llm is not None, "load_error": _load_error}


@app.get("/api/stats")
def stats():
    out = dict(_stats)
    if out["calls"]:
        out["avg_seconds"] = round(out["total_seconds"] / out["calls"], 2)
        out["avg_tokens"] = round(out["total_tokens_out"] / out["calls"], 1)
    return out


@app.post("/api/decide")
def decide(payload: DecideIn):
    if _llm is None:
        return {"error": _load_error or "model still loading", "ready": False}
    t0 = time.time()
    try:
        messages = []
        if payload.system:
            messages.append({"role": "system", "content": payload.system})
        messages.append({"role": "user", "content": payload.user})
        kwargs = dict(
            messages=messages,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        )
        if payload.json_only:
            kwargs["response_format"] = {"type": "json_object"}
        out = _llm.create_chat_completion(**kwargs)
        text = out["choices"][0]["message"]["content"]
        usage = out.get("usage", {})
        elapsed = time.time() - t0
        _stats["calls"] += 1
        _stats["total_seconds"] += elapsed
        _stats["total_tokens_out"] += int(usage.get("completion_tokens", 0))
        return {
            "text": text,
            "elapsed_s": round(elapsed, 2),
            "tokens_out": usage.get("completion_tokens"),
            "model": MODEL_FILE,
        }
    except Exception as e:
        _stats["errors"] += 1
        return {"error": str(e), "elapsed_s": round(time.time() - t0, 2)}
