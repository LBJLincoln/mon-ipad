#!/usr/bin/env python3
"""
Embedding Model Benchmark — Compare embedding models on your RAG data
Part of: RAG Chunking & Embedding Optimization Guide by Nomos AI

Usage:
    python embedding_benchmark.py --queries queries.json --corpus corpus.json --output benchmark.json

Requirements:
    pip install sentence-transformers numpy scikit-learn requests
"""

import json
import time
import argparse
import numpy as np
from pathlib import Path
from typing import Optional


# --- Embedding Providers ---

class JinaEmbedder:
    def __init__(self, api_key: str, dimensions: int = 1024):
        self.api_key = api_key
        self.dimensions = dimensions
        self.name = f"jina-v3-{dimensions}d"

    def embed(self, texts: list[str], task: str = "retrieval.passage") -> np.ndarray:
        import requests
        response = requests.post(
            "https://api.jina.ai/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "input": texts,
                "model": "jina-embeddings-v3",
                "task": task,
                "dimensions": self.dimensions,
            }
        )
        data = response.json()["data"]
        return np.array([d["embedding"] for d in data])


class LocalEmbedder:
    def __init__(self, model_name: str, dimensions: Optional[int] = None):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.dimensions = dimensions
        self.name = model_name.split("/")[-1]

    def embed(self, texts: list[str], task: str = "retrieval.passage") -> np.ndarray:
        embeddings = self.model.encode(texts, show_progress_bar=False)
        if self.dimensions and embeddings.shape[1] > self.dimensions:
            embeddings = embeddings[:, :self.dimensions]
        return embeddings


# --- Benchmark ---

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return a_norm @ b_norm.T


def retrieval_at_k(query_embeddings, doc_embeddings, relevant_ids, k=5):
    """Calculate Retrieval@K metric."""
    sim_matrix = cosine_similarity(query_embeddings, doc_embeddings)
    hits = 0
    for i, relevant in enumerate(relevant_ids):
        top_k_indices = np.argsort(sim_matrix[i])[::-1][:k]
        if any(idx in relevant for idx in top_k_indices):
            hits += 1
    return hits / len(relevant_ids)


def mrr(query_embeddings, doc_embeddings, relevant_ids):
    """Calculate Mean Reciprocal Rank."""
    sim_matrix = cosine_similarity(query_embeddings, doc_embeddings)
    reciprocal_ranks = []
    for i, relevant in enumerate(relevant_ids):
        ranked = np.argsort(sim_matrix[i])[::-1]
        for rank, idx in enumerate(ranked, 1):
            if idx in relevant:
                reciprocal_ranks.append(1.0 / rank)
                break
        else:
            reciprocal_ranks.append(0.0)
    return np.mean(reciprocal_ranks)


def benchmark_embedder(embedder, queries, documents, relevant_ids, batch_size=32):
    """Benchmark a single embedding model."""
    # Embed documents
    start = time.time()
    doc_embeddings = []
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        doc_embeddings.append(embedder.embed(batch, task="retrieval.passage"))
    doc_embeddings = np.vstack(doc_embeddings)
    doc_time = time.time() - start

    # Embed queries
    start = time.time()
    query_embeddings = []
    for i in range(0, len(queries), batch_size):
        batch = queries[i:i + batch_size]
        query_embeddings.append(embedder.embed(batch, task="retrieval.query"))
    query_embeddings = np.vstack(query_embeddings)
    query_time = time.time() - start

    # Calculate metrics
    r_at_1 = retrieval_at_k(query_embeddings, doc_embeddings, relevant_ids, k=1)
    r_at_5 = retrieval_at_k(query_embeddings, doc_embeddings, relevant_ids, k=5)
    r_at_10 = retrieval_at_k(query_embeddings, doc_embeddings, relevant_ids, k=10)
    mean_rr = mrr(query_embeddings, doc_embeddings, relevant_ids)

    return {
        "model": embedder.name,
        "dimensions": doc_embeddings.shape[1],
        "retrieval_at_1": round(r_at_1, 4),
        "retrieval_at_5": round(r_at_5, 4),
        "retrieval_at_10": round(r_at_10, 4),
        "mrr": round(mean_rr, 4),
        "doc_embed_time_s": round(doc_time, 2),
        "query_embed_time_s": round(query_time, 2),
        "docs_per_second": round(len(documents) / doc_time, 1),
        "queries_per_second": round(len(queries) / query_time, 1),
    }


def run_benchmark(queries_path: str, corpus_path: str, output_path: str):
    """Run the full benchmark suite."""
    # Load data
    with open(queries_path) as f:
        query_data = json.load(f)

    with open(corpus_path) as f:
        corpus = json.load(f)

    queries = [q["text"] for q in query_data]
    documents = [d["text"] for d in corpus]
    relevant_ids = [q.get("relevant_doc_ids", [q.get("relevant_id", 0)]) for q in query_data]

    print(f"Benchmark: {len(queries)} queries, {len(documents)} documents")

    # Test local models (no API key needed)
    models_to_test = [
        ("BAAI/bge-large-en-v1.5", None),
        ("sentence-transformers/all-MiniLM-L6-v2", None),
    ]

    results = []
    for model_name, dims in models_to_test:
        print(f"\nTesting {model_name}...")
        try:
            embedder = LocalEmbedder(model_name, dims)
            result = benchmark_embedder(embedder, queries, documents, relevant_ids)
            results.append(result)
            print(f"  R@5: {result['retrieval_at_5']:.1%} | MRR: {result['mrr']:.3f} | {result['docs_per_second']} docs/s")
        except Exception as e:
            print(f"  SKIP: {e}")

    # Save results
    output = {
        "benchmark_date": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "num_queries": len(queries),
        "num_documents": len(documents),
        "results": sorted(results, key=lambda x: x["retrieval_at_5"], reverse=True),
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {output_path}")

    if results:
        best = results[0]
        print(f"\nBest model: {best['model']} (R@5: {best['retrieval_at_5']:.1%}, MRR: {best['mrr']:.3f})")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embedding Model Benchmark for RAG")
    parser.add_argument("--queries", required=True, help="JSON file with queries")
    parser.add_argument("--corpus", required=True, help="JSON file with documents")
    parser.add_argument("--output", default="embedding_benchmark.json", help="Output JSON file")
    args = parser.parse_args()

    run_benchmark(args.queries, args.corpus, args.output)
