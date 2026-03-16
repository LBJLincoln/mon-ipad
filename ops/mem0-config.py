#!/usr/bin/env python3
"""Mem0 integration config — connects to Pinecone, Neo4j, LiteLLM.

Usage:
    from ops.mem0_config import create_mem0_client
    m = create_mem0_client()
    m.add("some fact", user_id="nomos")
    results = m.search("query", user_id="nomos")

Requires: source .env.local  (PINECONE_API_KEY, NEO4J_PASSWORD)
"""
import os
import sys

from mem0 import Memory


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

def _build_config() -> dict:
    """Build Mem0 config dict from environment variables."""
    pinecone_key = os.environ.get("PINECONE_API_KEY")
    neo4j_password = os.environ.get("NEO4J_PASSWORD")
    if not pinecone_key:
        raise EnvironmentError("PINECONE_API_KEY not set — run: source .env.local")
    if not neo4j_password:
        raise EnvironmentError("NEO4J_PASSWORD not set — run: source .env.local")

    return {
        # --- Vector store: Pinecone (existing sector index) ---
        "vector_store": {
            "provider": "pinecone",
            "config": {
                "collection_name": "website-sectors-jina-1024",
                "namespace": "mem0",
                "embedding_model_dims": 1024,
                "api_key": pinecone_key,
                "metric": "cosine",
                "serverless_config": {"cloud": "aws", "region": "us-east-1"},
            },
        },
        # --- LLM: LiteLLM proxy (OpenAI-compatible) ---
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gemini-flash",
                "api_key": "sk-litellm-nomos-2026",
                "openai_base_url": "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1",
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        },
        # --- Embedder: self-hosted Jina Space (OpenAI-compatible /v1/embeddings) ---
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "jina-embeddings-v3",
                "api_key": "dummy",
                "openai_base_url": "https://lbjlincoln-nomos-embeddings-api.hf.space/v1",
                "embedding_dims": 1024,
            },
        },
        # --- Graph store: Neo4j Aura ---
        "graph_store": {
            "provider": "neo4j",
            "config": {
                "url": os.environ.get("NEO4J_URI", "neo4j+s://38c949a2.databases.neo4j.io"),
                "username": os.environ.get("NEO4J_USER", "neo4j"),
                "password": neo4j_password,
            },
        },
        "version": "v1.1",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_mem0_client() -> Memory:
    """Return a ready-to-use Mem0 Memory instance."""
    config = _build_config()
    return Memory.from_config(config_dict=config)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("[mem0-config] Initializing Mem0 client...")
    m = create_mem0_client()
    print("[mem0-config] OK — client created")

    user = "nomos-test"

    print(f"[mem0-config] Adding test memory (user={user})...")
    result = m.add(
        "L'article L.1234-5 du Code du travail definit les conditions de licenciement",
        user_id=user,
    )
    print(f"[mem0-config] Add result: {result}")

    print(f"[mem0-config] Searching 'conditions de licenciement'...")
    hits = m.search("conditions de licenciement", user_id=user)
    print(f"[mem0-config] Search results ({len(hits.get('results', []))} hits):")
    for h in hits.get("results", []):
        print(f"  - score={h.get('score', '?'):.3f}  memory={h.get('memory', '')}")

    print("[mem0-config] Test complete.")


if __name__ == "__main__":
    _test()
