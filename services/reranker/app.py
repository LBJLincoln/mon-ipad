"""Cross-encoder reranker microservice — SOTA 2026.
Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (~150MB, ~30ms/pair CPU).
"""
import os, json, logging
from flask import Flask, request, jsonify
from sentence_transformers import CrossEncoder

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("reranker")

MODEL_NAME = os.environ.get("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
PORT = int(os.environ.get("RERANKER_PORT", 5001))

log.info(f"Loading cross-encoder model: {MODEL_NAME}")
model = CrossEncoder(MODEL_NAME)
log.info("Model loaded.")

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": MODEL_NAME})

@app.route("/rerank", methods=["POST"])
def rerank():
    data = request.get_json(force=True)
    query = data.get("query", "")
    documents = data.get("documents", [])
    top_n = data.get("top_n", len(documents))

    if not query or not documents:
        return jsonify({"error": "query and documents required"}), 400

    pairs = [[query, doc if isinstance(doc, str) else doc.get("text", "")] for doc in documents]
    scores = model.predict(pairs).tolist()

    ranked = sorted(
        [{"index": i, "score": s, "document": documents[i]} for i, s in enumerate(scores)],
        key=lambda x: x["score"],
        reverse=True,
    )[:top_n]

    return jsonify({"results": ranked})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
