#!/usr/bin/env python3
"""
Replace pseudo-vectors in Pinecone with real embeddings.

Uses OpenAI text-embedding-3-small (1536-dim) via OpenRouter to create
proper semantic embeddings for all benchmark questions.

The WF2 Graph RAG and WF5 Standard RAG workflows use the same embedding
model for their HyDE queries, so the vectors must be compatible.
"""
import json
import os
import sys
import time
import hashlib
from datetime import datetime
from urllib import request, error, parse

# ============================================================
# Configuration
# ============================================================
SUPABASE_CONN = f"postgresql://postgres:{os.environ['SUPABASE_PASSWORD']}@db.ayqviqmxifzmhphiqfmj.supabase.co:5432/postgres"
PINECONE_HOST = os.environ.get("PINECONE_HOST", "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io").rstrip("/")
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]

# Embedding API - use OpenAI directly or via OpenRouter
# OpenAI is preferred for embeddings as it's cheaper and faster
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536-dim, same as WF2/WF5
EMBEDDING_DIM = 1536

# Batch sizes
EMBEDDING_BATCH_SIZE = 100  # OpenAI allows up to 2048 per batch
PINECONE_BATCH_SIZE = 100   # Pinecone limit per upsert


# ============================================================
# Embedding API
# ============================================================

def get_embeddings_openai(texts):
    """Get embeddings from OpenAI API (or compatible endpoint)."""
    api_key = OPENAI_API_KEY or OPENROUTER_API_KEY
    if not api_key:
        print("  ERROR: No OPENAI_API_KEY or OPENROUTER_API_KEY set")
        return None

    # Use OpenAI directly if key available, else OpenRouter
    if OPENAI_API_KEY:
        url = "https://api.openai.com/v1/embeddings"
        auth_key = OPENAI_API_KEY
    else:
        url = "https://openrouter.ai/api/v1/embeddings"
        auth_key = OPENROUTER_API_KEY

    body = json.dumps({
        "model": EMBEDDING_MODEL,
        "input": texts,
        "encoding_format": "float"
    }).encode()

    headers = {
        "Authorization": f"Bearer {auth_key}",
        "Content-Type": "application/json"
    }
    if not OPENAI_API_KEY:
        headers["HTTP-Referer"] = "https://github.com/mon-ipad"
        headers["X-Title"] = "RAG-Benchmark-Embeddings"

    req = request.Request(url, data=body, headers=headers, method="POST")

    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                embeddings = [item["embedding"] for item in result["data"]]
                return embeddings
        except error.HTTPError as e:
            err_body = e.read().decode() if hasattr(e, 'read') else str(e)
            print(f"    Embedding API error (attempt {attempt+1}): {e.code} - {err_body[:200]}")
            if e.code == 429:  # Rate limited
                time.sleep(5 * (attempt + 1))
            elif e.code >= 500:
                time.sleep(2 ** attempt)
            else:
                return None
        except Exception as e:
            print(f"    Embedding error (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)

    return None


def get_embeddings_batch(texts, batch_size=EMBEDDING_BATCH_SIZE):
    """Get embeddings for a large list of texts, batching as needed."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        # Truncate texts to avoid token limits (8191 tokens max for text-embedding-3-small)
        batch = [t[:6000] for t in batch]  # ~1500 tokens per text

        embeddings = get_embeddings_openai(batch)
        if embeddings is None:
            print(f"    FAILED to get embeddings for batch {i//batch_size + 1}")
            # Return None for failed items
            all_embeddings.extend([None] * len(batch))
        else:
            all_embeddings.extend(embeddings)

        if i > 0 and i % (batch_size * 5) == 0:
            print(f"    Embedded {i + len(batch)}/{len(texts)} texts...")
            time.sleep(0.5)  # Rate limit buffer

    return all_embeddings


# ============================================================
# Pinecone operations
# ============================================================

def pinecone_describe_index():
    """Get Pinecone index stats."""
    req = request.Request(
        f"{PINECONE_HOST}/describe_index_stats",
        headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"},
        data=b"{}",
        method="POST"
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  Pinecone describe error: {e}")
        return None


def pinecone_upsert(vectors, namespace):
    """Upsert vectors to Pinecone."""
    total = 0
    for i in range(0, len(vectors), PINECONE_BATCH_SIZE):
        batch = vectors[i:i+PINECONE_BATCH_SIZE]
        body = json.dumps({"vectors": batch, "namespace": namespace}).encode()

        req = request.Request(
            f"{PINECONE_HOST}/vectors/upsert",
            data=body,
            headers={
                "Api-Key": PINECONE_API_KEY,
                "Content-Type": "application/json"
            },
            method="POST"
        )
        for attempt in range(3):
            try:
                with request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                    total += result.get("upsertedCount", len(batch))
                    break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    print(f"    Pinecone upsert error: {e}")

    return total


def pinecone_delete_namespace(namespace):
    """Delete all vectors in a namespace."""
    body = json.dumps({"deleteAll": True, "namespace": namespace}).encode()
    req = request.Request(
        f"{PINECONE_HOST}/vectors/delete",
        data=body,
        headers={
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            return True
    except Exception as e:
        print(f"    Delete namespace error: {e}")
        return False


# ============================================================
# Supabase data fetching
# ============================================================

def fetch_questions(dataset_name=None, limit=1000, offset=0):
    """Fetch questions from Supabase benchmark_datasets."""
    import subprocess

    where = "WHERE tenant_id = 'benchmark'"
    if dataset_name:
        where += f" AND dataset_name = '{dataset_name}'"

    sql = f"""SELECT dataset_name, category, split, item_index, question, expected_answer, context
    FROM benchmark_datasets
    {where}
    ORDER BY dataset_name, item_index
    LIMIT {limit} OFFSET {offset};"""

    result = subprocess.run(
        ["psql", SUPABASE_CONN, "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True, timeout=30
    )

    if result.returncode != 0:
        print(f"  Supabase error: {result.stderr[:300]}")
        return []

    rows = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        rows.append({
            "dataset_name": parts[0],
            "category": parts[1],
            "split": parts[2],
            "item_index": int(parts[3]),
            "question": parts[4],
            "expected_answer": parts[5] if len(parts) > 5 else "",
            "context": parts[6] if len(parts) > 6 else None
        })

    return rows


def get_dataset_names():
    """Get list of distinct dataset names from Supabase."""
    import subprocess
    sql = "SELECT DISTINCT dataset_name, COUNT(*) as cnt FROM benchmark_datasets WHERE tenant_id = 'benchmark' GROUP BY dataset_name ORDER BY cnt DESC;"
    result = subprocess.run(
        ["psql", SUPABASE_CONN, "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        return []

    datasets = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            datasets.append({"name": parts[0], "count": int(parts[1])})
    return datasets


# ============================================================
# Main pipeline
# ============================================================

def populate_embeddings():
    """Main: replace pseudo-vectors with real embeddings in Pinecone."""
    print("=" * 60)
    print("PINECONE REAL EMBEDDINGS POPULATION")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Model: {EMBEDDING_MODEL} ({EMBEDDING_DIM}-dim)")
    print("=" * 60)

    # Check Pinecone status
    print("\n1. Checking Pinecone index status...")
    stats = pinecone_describe_index()
    if stats:
        print(f"   Dimension: {stats.get('dimension', 'unknown')}")
        print(f"   Total vectors: {stats.get('totalVectorCount', 0)}")
        namespaces = stats.get("namespaces", {})
        for ns, info in namespaces.items():
            print(f"   Namespace '{ns}': {info.get('vectorCount', 0)} vectors")

    # Get datasets from Supabase
    print("\n2. Fetching dataset inventory from Supabase...")
    datasets = get_dataset_names()
    if not datasets:
        print("  ERROR: No datasets found in Supabase")
        return

    for ds in datasets:
        print(f"   {ds['name']}: {ds['count']} questions")

    total_embedded = 0
    total_upserted = 0

    # Process each dataset
    for ds in datasets:
        ds_name = ds["name"]
        ds_count = ds["count"]
        namespace = f"benchmark-{ds_name}"

        print(f"\n{'='*50}")
        print(f"Processing: {ds_name} ({ds_count} questions)")
        print(f"Namespace: {namespace}")
        print(f"{'='*50}")

        # Delete old pseudo-vectors in this namespace
        print(f"  Clearing old vectors in namespace '{namespace}'...")
        pinecone_delete_namespace(namespace)
        time.sleep(1)

        # Fetch all questions for this dataset
        all_questions = []
        offset = 0
        while offset < ds_count:
            batch = fetch_questions(ds_name, limit=500, offset=offset)
            if not batch:
                break
            all_questions.extend(batch)
            offset += len(batch)

        print(f"  Fetched {len(all_questions)} questions from Supabase")

        # Build text for embedding: question + context snippet
        texts = []
        for q in all_questions:
            # Combine question + answer + context for richer embedding
            text = q["question"]
            if q.get("expected_answer"):
                text += f"\nAnswer: {q['expected_answer']}"
            if q.get("context"):
                ctx = q["context"]
                if isinstance(ctx, str) and len(ctx) > 50:
                    text += f"\nContext: {ctx[:2000]}"
            texts.append(text)

        # Get real embeddings
        print(f"  Getting embeddings ({EMBEDDING_MODEL})...")
        embeddings = get_embeddings_batch(texts)

        # Build Pinecone vectors
        vectors = []
        skipped = 0
        for i, (q, emb) in enumerate(zip(all_questions, embeddings)):
            if emb is None:
                skipped += 1
                continue

            vec_id = f"bench-{ds_name}-{q['split']}-{q['item_index']}"
            vectors.append({
                "id": vec_id,
                "values": emb,
                "metadata": {
                    "dataset_name": ds_name,
                    "category": q["category"],
                    "item_index": q["item_index"],
                    "question": q["question"][:400],
                    "expected_answer": (q.get("expected_answer") or "")[:400],
                    "tenant_id": "benchmark"
                }
            })

        if skipped:
            print(f"  WARNING: {skipped} embeddings failed, skipped")

        # Upsert to Pinecone
        print(f"  Upserting {len(vectors)} vectors to Pinecone...")
        upserted = pinecone_upsert(vectors, namespace)
        print(f"  Upserted: {upserted} vectors")

        total_embedded += len(vectors)
        total_upserted += upserted

    # Final stats
    print(f"\n{'='*60}")
    print("EMBEDDING POPULATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Total texts embedded: {total_embedded}")
    print(f"  Total vectors upserted: {total_upserted}")

    # Verify
    print("\n  Verifying Pinecone index...")
    time.sleep(2)
    stats = pinecone_describe_index()
    if stats:
        print(f"  Total vectors now: {stats.get('totalVectorCount', 0)}")
        namespaces = stats.get("namespaces", {})
        for ns, info in namespaces.items():
            print(f"   '{ns}': {info.get('vectorCount', 0)} vectors")


if __name__ == "__main__":
    populate_embeddings()
