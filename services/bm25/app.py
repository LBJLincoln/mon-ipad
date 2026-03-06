"""BM25 hybrid search service with RRF fusion.
Flask on port 5002.
Endpoints:
  POST /search   — BM25 keyword search
  POST /hybrid   — RRF fusion of BM25 + dense (Pinecone) results
  GET  /health   — Health check
"""
import os, sys, json, pickle, re, logging, requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bm25-service")

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    sys.exit("pip install rank-bm25")

INDEX_PATH = os.environ.get("BM25_INDEX_PATH", "bm25_index.pkl")
PORT = int(os.environ.get("BM25_PORT", 5002))
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = os.environ.get("PINECONE_HOST", "")
RRF_K = int(os.environ.get("RRF_K", 60))

# Load index
bm25 = None
chunks = []
corpus = []

def load_index():
    global bm25, chunks, corpus
    if not os.path.exists(INDEX_PATH):
        log.warning(f"No index at {INDEX_PATH}. Run build_index.py first.")
        return
    with open(INDEX_PATH, "rb") as f:
        data = pickle.load(f)
    bm25 = data["bm25"]
    chunks = data["chunks"]
    corpus = data["corpus"]
    log.info(f"Loaded BM25 index: {len(chunks)} docs")

load_index()

app = Flask(__name__)

def tokenize(text):
    return re.findall(r'\w+', text.lower())

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "docs": len(chunks), "index_loaded": bm25 is not None})

@app.route("/search", methods=["POST"])
def search():
    data = request.get_json(force=True)
    query = data.get("query", "")
    top_k = data.get("top_k", 10)

    if not query:
        return jsonify({"error": "query required"}), 400
    if bm25 is None:
        return jsonify({"error": "index not loaded"}), 503

    tokens = tokenize(query)
    scores = bm25.get_scores(tokens)
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = []
    for rank, idx in enumerate(ranked_indices):
        results.append({
            "rank": rank + 1,
            "score": float(scores[idx]),
            "text": chunks[idx]["text"][:500],
            "metadata": chunks[idx].get("metadata", {}),
        })
    return jsonify({"results": results, "total": len(chunks)})

@app.route("/hybrid", methods=["POST"])
def hybrid():
    """RRF fusion: Score(d) = 1/(K+rank_dense) + 1/(K+rank_bm25)"""
    data = request.get_json(force=True)
    query = data.get("query", "")
    top_k = data.get("top_k", 10)
    namespace = data.get("namespace", "")
    dense_results = data.get("dense_results", None)

    if not query:
        return jsonify({"error": "query required"}), 400

    # BM25 results
    bm25_results = []
    if bm25 is not None:
        tokens = tokenize(query)
        scores = bm25.get_scores(tokens)
        bm25_ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k * 2]
        for rank, idx in enumerate(bm25_ranked):
            bm25_results.append({
                "id": f"bm25-{idx}",
                "rank": rank + 1,
                "score": float(scores[idx]),
                "text": chunks[idx]["text"],
                "metadata": chunks[idx].get("metadata", {}),
            })

    # Dense results (from Pinecone or passed in)
    if dense_results is None and PINECONE_API_KEY and PINECONE_HOST:
        dense_results = query_pinecone(query, namespace, top_k * 2)
    elif dense_results is None:
        dense_results = []

    # RRF fusion
    doc_scores = {}
    doc_data = {}
    for rank, doc in enumerate(dense_results):
        doc_id = doc.get("id", f"dense-{rank}")
        doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1.0 / (RRF_K + rank + 1)
        doc_data[doc_id] = doc

    for rank, doc in enumerate(bm25_results):
        text_key = doc["text"][:100]
        best_match = None
        for did, ddata in doc_data.items():
            if ddata.get("text", "")[:100] == text_key:
                best_match = did
                break
        doc_id = best_match or doc["id"]
        doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1.0 / (RRF_K + rank + 1)
        if doc_id not in doc_data:
            doc_data[doc_id] = doc

    fused = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for rank, (doc_id, score) in enumerate(fused):
        entry = doc_data.get(doc_id, {})
        results.append({
            "rank": rank + 1,
            "rrf_score": round(score, 6),
            "text": entry.get("text", "")[:500],
            "metadata": entry.get("metadata", {}),
            "source": "dense" if doc_id.startswith("dense") or not doc_id.startswith("bm25") else "bm25",
        })

    return jsonify({"results": results, "bm25_count": len(bm25_results), "dense_count": len(dense_results)})

def query_pinecone(query, namespace, top_k):
    """Query Pinecone for dense results (embedding via Jina or HF)."""
    try:
        # Use Jina embeddings if available
        jina_key = os.environ.get("JINA_API_KEY", "")
        if jina_key:
            emb_resp = requests.post(
                "https://api.jina.ai/v1/embeddings",
                headers={"Authorization": f"Bearer {jina_key}", "Content-Type": "application/json"},
                json={"model": "jina-embeddings-v3", "input": [query], "dimensions": 1024},
                timeout=10,
            )
            vector = emb_resp.json()["data"][0]["embedding"]
        else:
            return []

        # Query Pinecone
        pc_resp = requests.post(
            f"{PINECONE_HOST}/query",
            headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"},
            json={"vector": vector, "topK": top_k, "namespace": namespace, "includeMetadata": True},
            timeout=10,
        )
        matches = pc_resp.json().get("matches", [])
        return [
            {"id": m["id"], "score": m.get("score", 0), "text": m.get("metadata", {}).get("text", ""), "metadata": m.get("metadata", {})}
            for m in matches
        ]
    except Exception as e:
        log.error(f"Pinecone query failed: {e}")
        return []

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
