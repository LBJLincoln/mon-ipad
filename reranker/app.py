#!/usr/bin/env python3
"""
Nomos Self-Hosted Reranker API
Drop-in replacement for Jina/Cohere reranking APIs using FlashRank (CPU, no API key).

Endpoints:
  POST /v1/rerank   - Jina/Cohere-compatible rerank endpoint
  POST /rerank      - TEI-compatible rerank endpoint
  GET  /health      - Health check
  GET  /info        - Model info

Models (FlashRank):
  - nano:   ms-marco-TinyBERT-L-2-v2      (~4MB,  fastest, lowest accuracy)
  - small:  ms-marco-MiniLM-L-12-v2       (~34MB, good balance)  [DEFAULT]
  - medium: rank-T5-flan                   (~110MB, higher accuracy)
  - large:  ms-marco-MultiBERT-L-12        (~150MB, best cross-encoder)

Deploy on HuggingFace Space (cpu-basic, Gradio SDK) — same pattern as nomos-embeddings-api.
"""

import os
import sys
import json
import time
import logging
from typing import Optional

# Gradio for HF Space compatibility (must import before FastAPI on Spaces)
import gradio as gr

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy model loading (avoid startup timeout on cpu-basic)
# ---------------------------------------------------------------------------
_ranker = None
_model_name = None
_load_time = None

# Model aliases -> FlashRank model IDs
MODEL_MAP = {
    "nano":   "ms-marco-TinyBERT-L-2-v2",
    "small":  "ms-marco-MiniLM-L-12-v2",
    "medium": "rank-T5-flan",
    "large":  "ms-marco-MultiBERT-L-12",
    # Accept full names too
    "ms-marco-TinyBERT-L-2-v2":   "ms-marco-TinyBERT-L-2-v2",
    "ms-marco-MiniLM-L-12-v2":    "ms-marco-MiniLM-L-12-v2",
    "rank-T5-flan":                "rank-T5-flan",
    "ms-marco-MultiBERT-L-12":    "ms-marco-MultiBERT-L-12",
    # Jina/Cohere model names -> map to our best equivalent
    "jina-reranker-v2-base-multilingual": "ms-marco-MiniLM-L-12-v2",
    "rerank-english-v3.0":                "ms-marco-MiniLM-L-12-v2",
    "rerank-multilingual-v3.0":           "ms-marco-MiniLM-L-12-v2",
    "rerank-english-v2.0":                "ms-marco-MiniLM-L-12-v2",
}

DEFAULT_MODEL = os.environ.get("RERANKER_MODEL", "small")


def get_ranker(model_alias: str = None):
    """Lazy-load the FlashRank ranker. Thread-safe enough for single-worker Gradio."""
    global _ranker, _model_name, _load_time

    alias = model_alias or DEFAULT_MODEL
    flashrank_model = MODEL_MAP.get(alias, MODEL_MAP.get(DEFAULT_MODEL, "ms-marco-MiniLM-L-12-v2"))

    # If already loaded with same model, return cached
    if _ranker is not None and _model_name == flashrank_model:
        return _ranker

    logger.info(f"Loading FlashRank model: {flashrank_model} (alias: {alias})")
    t0 = time.time()

    from flashrank import Ranker
    _ranker = Ranker(model_name=flashrank_model)
    _model_name = flashrank_model
    _load_time = time.time() - t0

    logger.info(f"Model loaded in {_load_time:.1f}s")
    return _ranker


def do_rerank(query: str, documents: list, top_n: int = 5, model: str = None) -> dict:
    """
    Rerank documents against a query.
    Returns Jina/Cohere-compatible response format.
    """
    if not query or not documents:
        return {"error": "query and documents are required"}

    t0 = time.time()
    ranker = get_ranker(model)

    # FlashRank expects list of dicts with "text" key
    # We tag each passage with its original index via "id" field for tracking
    from flashrank import RerankRequest
    passages = [{"id": i, "text": doc} for i, doc in enumerate(documents)]
    rerank_request = RerankRequest(query=query, passages=passages)
    raw_results = ranker.rerank(rerank_request)

    # Build response — FlashRank returns dicts with 'text', 'score', and 'id' (our injected index)
    # Build a text->index lookup as fallback if 'id' is not preserved
    text_to_idx = {doc: i for i, doc in enumerate(documents)}

    results = []
    for item in raw_results:
        text = item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
        score = item.get("score", 0.0) if isinstance(item, dict) else getattr(item, "score", 0.0)
        raw_id = item.get("id", None) if isinstance(item, dict) else getattr(item, "id", None)

        # Use injected id if it's a valid int, otherwise fall back to text matching
        if isinstance(raw_id, int) and 0 <= raw_id < len(documents):
            idx = raw_id
        else:
            idx = text_to_idx.get(text, -1)

        results.append({
            "index": idx,
            "relevance_score": float(score),
            "document": {"text": text}
        })

    # Sort by score descending, take top_n
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    results = results[:top_n]

    elapsed = time.time() - t0

    return {
        "model": _model_name,
        "results": results,
        "meta": {
            "api_version": {"version": "1"},
            "billed_units": {"search_units": 0},  # free!
            "warning": None
        },
        "usage": {
            "total_tokens": 0,
            "prompt_tokens": 0
        },
        "_timing_ms": round(elapsed * 1000, 1),
        "_self_hosted": True,
        "_cost": 0.0
    }


# ---------------------------------------------------------------------------
# Gradio interface (for HF Space compatibility)
# ---------------------------------------------------------------------------
def gradio_rerank(query: str, documents_json: str, top_n: int = 5, model: str = "small") -> str:
    """Gradio wrapper for the rerank function."""
    try:
        docs = json.loads(documents_json) if isinstance(documents_json, str) else documents_json
        if not isinstance(docs, list):
            return json.dumps({"error": "documents must be a JSON array of strings"}, indent=2)
        result = do_rerank(query, docs, top_n, model)
        return json.dumps(result, indent=2)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON in documents field"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def health_check():
    """Return health status."""
    return json.dumps({
        "status": "ok",
        "model_loaded": _model_name is not None,
        "model": _model_name,
        "load_time_s": round(_load_time, 2) if _load_time else None
    }, indent=2)


# Build Gradio app with API endpoints
with gr.Blocks(title="Nomos Reranker API") as demo:
    gr.Markdown("# Nomos Self-Hosted Reranker API")
    gr.Markdown("""
    Free, self-hosted document reranker using FlashRank (CPU, no API key needed).

    **API Endpoints:**
    - `POST /v1/rerank` - Jina/Cohere-compatible (use from n8n workflows)
    - `POST /rerank` - TEI-compatible
    - `GET /health` - Health check

    **Models:** nano (4MB), small (34MB, default), medium (110MB), large (150MB)
    """)

    with gr.Row():
        with gr.Column():
            query_input = gr.Textbox(label="Query", placeholder="What is the capital of France?")
            docs_input = gr.Textbox(
                label="Documents (JSON array)",
                placeholder='["Paris is the capital of France.", "Berlin is the capital of Germany.", "Tokyo is in Japan."]',
                lines=5
            )
            top_n_input = gr.Number(label="Top N", value=5, minimum=1, maximum=100)
            model_input = gr.Dropdown(
                choices=["nano", "small", "medium", "large"],
                value="small",
                label="Model"
            )
            rerank_btn = gr.Button("Rerank", variant="primary")

        with gr.Column():
            output = gr.Textbox(label="Results", lines=15)

    rerank_btn.click(
        fn=gradio_rerank,
        inputs=[query_input, docs_input, top_n_input, model_input],
        outputs=output
    )


# ---------------------------------------------------------------------------
# Mount FastAPI routes for /v1/rerank and /rerank (Jina/Cohere/TEI compatible)
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Nomos Reranker API")


@app.post("/v1/rerank")
async def v1_rerank(request: Request):
    """Jina/Cohere-compatible rerank endpoint."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    query = body.get("query", "")
    documents = body.get("documents", [])
    top_n = body.get("top_n", 5)
    model = body.get("model", None)

    # Handle documents as list of strings or list of dicts
    if documents and isinstance(documents[0], dict):
        documents = [d.get("text", d.get("content", str(d))) for d in documents]

    result = do_rerank(query, documents, top_n, model)
    if "error" in result:
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)


@app.post("/rerank")
async def tei_rerank(request: Request):
    """TEI-compatible rerank endpoint."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    query = body.get("query", "")
    # TEI uses "texts" instead of "documents"
    documents = body.get("texts", body.get("documents", []))
    top_n = body.get("top_n", len(documents))

    if documents and isinstance(documents[0], dict):
        documents = [d.get("text", d.get("content", str(d))) for d in documents]

    result = do_rerank(query, documents, top_n)
    if "error" in result:
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)


@app.get("/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "model_loaded": _model_name is not None,
        "model": _model_name,
        "load_time_s": round(_load_time, 2) if _load_time else None
    })


@app.get("/info")
async def info():
    return JSONResponse({
        "service": "nomos-reranker-api",
        "framework": "FlashRank",
        "models_available": list(set(MODEL_MAP.values())),
        "default_model": MODEL_MAP.get(DEFAULT_MODEL, "ms-marco-MiniLM-L-12-v2"),
        "current_model": _model_name,
        "endpoints": ["/v1/rerank", "/rerank", "/health", "/info"],
        "api_key_required": False,
        "cost": "free"
    })


# Mount FastAPI into Gradio
demo = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
