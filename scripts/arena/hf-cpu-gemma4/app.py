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

FALLBACK_MODELS = [
    ("unsloth/Phi-4-mini-instruct-GGUF", "Phi-4-mini-instruct-Q4_K_M.gguf"),
    ("bartowski/microsoft_Phi-4-mini-instruct-GGUF", "microsoft_Phi-4-mini-instruct-Q4_K_M.gguf"),
    ("bartowski/Qwen2.5-3B-Instruct-GGUF", "Qwen2.5-3B-Instruct-Q4_K_M.gguf"),
]
_active_model: tuple[str, str] | None = None

_llm: Llama | None = None
_load_error: str | None = None
_load_lock = threading.Lock()
_stats = {"calls": 0, "errors": 0, "total_tokens_out": 0, "total_seconds": 0.0}


def _try_load(repo: str, filename: str) -> Llama | None:
    """Download + load one model. Returns Llama or None."""
    try:
        path = hf_hub_download(repo_id=repo, filename=filename)
        return Llama(
            model_path=path,
            n_ctx=N_CTX,
            n_threads=N_THREADS,
            n_batch=256,
            verbose=False,
            seed=42,
        )
    except Exception:
        return None


def _load_model() -> None:
    """Try primary model first, then fallbacks. First success wins."""
    global _llm, _load_error, _active_model
    with _load_lock:
        if _llm is not None:
            return
        attempts = [(MODEL_REPO, MODEL_FILE)] + FALLBACK_MODELS
        errors = []
        for repo, fname in attempts:
            llm = _try_load(repo, fname)
            if llm is not None:
                _llm = llm
                _active_model = (repo, fname)
                return
            errors.append(f"{repo}/{fname}")
        _load_error = "all model loads failed: " + " | ".join(errors)


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
        "model_requested": f"{MODEL_REPO}/{MODEL_FILE}",
        "model_active": f"{_active_model[0]}/{_active_model[1]}" if _active_model else None,
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
