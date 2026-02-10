#!/usr/bin/env python3
"""
Migrate Pinecone vectors from 1536d (OpenAI) to 1024d (Cohere embed-english-v3.0).

Steps:
1. List all vector IDs from the source index (1536d)
2. Fetch metadata (contains the embeddable text)
3. Re-embed with Cohere embed-english-v3.0 (1024d)
4. Upsert to the target index (1024d)

Usage:
  python3 db/populate/migrate_to_cohere.py                    # Full migration
  python3 db/populate/migrate_to_cohere.py --namespace benchmark-triviaqa  # Single namespace
  python3 db/populate/migrate_to_cohere.py --dry-run           # Preview only
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import argparse

# Configuration — set via environment variables (no hardcoded keys)
SOURCE_HOST = os.environ.get("PINECONE_HOST", "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io")
TARGET_HOST = os.environ.get("PINECONE_TARGET_HOST", "https://sota-rag-cohere-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io")
PINECONE_KEY = os.environ["PINECONE_API_KEY"]
COHERE_KEY = os.environ["COHERE_API_KEY"]
COHERE_MODEL = "embed-english-v3.0"
COHERE_BATCH_SIZE = 96  # Cohere max batch
PINECONE_FETCH_BATCH = 100
RATE_LIMIT_PAUSE = 1.0  # seconds between Cohere batches


def api_request(url, data=None, headers=None, method=None, timeout=30, retries=3):
    """Make HTTP request with retries."""
    for attempt in range(retries):
        try:
            if data is not None:
                encoded = json.dumps(data).encode()
            else:
                encoded = None
            req = urllib.request.Request(url, data=encoded, method=method or ("POST" if encoded else "GET"))
            req.add_header("Content-Type", "application/json")
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 429:
                wait = 2 ** attempt * 2
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if attempt == retries - 1:
                print(f"    HTTP {e.code}: {body[:200]}")
                raise
            time.sleep(1)
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(1)


def pinecone_request(host, endpoint, data=None, method=None):
    """Make Pinecone API request."""
    url = f"{host}{endpoint}"
    return api_request(url, data=data, headers={"Api-Key": PINECONE_KEY}, method=method)


def cohere_embed(texts, input_type="search_document"):
    """Embed texts using Cohere API."""
    url = "https://api.cohere.com/v2/embed"
    data = {
        "model": COHERE_MODEL,
        "texts": texts,
        "input_type": input_type,
        "embedding_types": ["float"],
    }
    result = api_request(url, data=data, headers={"Authorization": f"Bearer {COHERE_KEY}"}, timeout=60)
    return result["embeddings"]["float"]


def list_all_ids(host, namespace=""):
    """List all vector IDs in a namespace using pagination."""
    ids = []
    pagination_token = None
    while True:
        params = f"?namespace={namespace}&limit=100"
        if pagination_token:
            params += f"&paginationToken={pagination_token}"
        result = pinecone_request(host, f"/vectors/list{params}")
        vectors = result.get("vectors", [])
        ids.extend(v["id"] for v in vectors)
        pagination_token = result.get("pagination", {}).get("next")
        if not pagination_token or not vectors:
            break
    return ids


def fetch_vectors(host, ids, namespace=""):
    """Fetch vectors with metadata by IDs."""
    result = pinecone_request(host, "/vectors/fetch", method="GET",
                               data=None)
    # Use GET with query params for fetch
    id_params = "&".join(f"ids={vid}" for vid in ids)
    url = f"{host}/vectors/fetch?namespace={namespace}&{id_params}"
    return api_request(url, headers={"Api-Key": PINECONE_KEY}, method="GET")


def extract_text(vector_data, namespace):
    """Extract embeddable text from vector metadata."""
    meta = vector_data.get("metadata", {})

    # Benchmark namespaces: question + expected_answer
    if namespace.startswith("benchmark-"):
        question = meta.get("question", "")
        answer = meta.get("expected_answer", "")
        if question:
            return f"{question}\n{answer}" if answer else question

    # Default namespace: content field
    content = meta.get("content", "")
    if content:
        return content

    # Fallback: try various fields
    for field in ["text", "document", "passage", "chunk_text", "page_content"]:
        if meta.get(field):
            return meta[field]

    return ""


def upsert_batch(host, vectors, namespace=""):
    """Upsert a batch of vectors to Pinecone."""
    data = {
        "vectors": vectors,
        "namespace": namespace,
    }
    return pinecone_request(host, "/vectors/upsert", data=data)


def migrate_namespace(namespace, dry_run=False):
    """Migrate a single namespace."""
    print(f"\n  === Migrating namespace: '{namespace}' ===")

    # Step 1: List all IDs
    print(f"    Listing vector IDs...")
    ids = list_all_ids(SOURCE_HOST, namespace)
    print(f"    Found {len(ids)} vectors")

    if not ids:
        print(f"    Skipping empty namespace")
        return 0

    if dry_run:
        print(f"    DRY RUN: Would migrate {len(ids)} vectors")
        return len(ids)

    total_migrated = 0

    # Process in batches
    for batch_start in range(0, len(ids), PINECONE_FETCH_BATCH):
        batch_ids = ids[batch_start:batch_start + PINECONE_FETCH_BATCH]

        # Step 2: Fetch vectors with metadata
        id_params = "&".join(f"ids={vid}" for vid in batch_ids)
        url = f"{SOURCE_HOST}/vectors/fetch?namespace={namespace}&{id_params}"
        fetch_result = api_request(url, headers={"Api-Key": PINECONE_KEY}, method="GET")
        vectors_data = fetch_result.get("vectors", {})

        if not vectors_data:
            print(f"    Batch {batch_start//PINECONE_FETCH_BATCH + 1}: No vectors returned")
            continue

        # Step 3: Extract texts and prepare for embedding
        texts_to_embed = []
        vector_ids = []
        metadata_list = []

        for vid, vdata in vectors_data.items():
            text = extract_text(vdata, namespace)
            if text and len(text.strip()) > 0:
                texts_to_embed.append(text[:8000])  # Cohere limit
                vector_ids.append(vid)
                metadata_list.append(vdata.get("metadata", {}))

        if not texts_to_embed:
            print(f"    Batch {batch_start//PINECONE_FETCH_BATCH + 1}: No extractable text")
            continue

        # Step 4: Embed with Cohere in sub-batches
        all_embeddings = []
        for emb_start in range(0, len(texts_to_embed), COHERE_BATCH_SIZE):
            emb_batch = texts_to_embed[emb_start:emb_start + COHERE_BATCH_SIZE]
            embeddings = cohere_embed(emb_batch, input_type="search_document")
            all_embeddings.extend(embeddings)
            time.sleep(RATE_LIMIT_PAUSE)

        # Step 5: Upsert to target index
        upsert_vectors = []
        for i, (vid, emb, meta) in enumerate(zip(vector_ids, all_embeddings, metadata_list)):
            upsert_vectors.append({
                "id": vid,
                "values": emb,
                "metadata": meta,
            })

            # Upsert in batches of 100
            if len(upsert_vectors) >= 100 or i == len(vector_ids) - 1:
                upsert_batch(TARGET_HOST, upsert_vectors, namespace)
                total_migrated += len(upsert_vectors)
                upsert_vectors = []

        progress = min(batch_start + PINECONE_FETCH_BATCH, len(ids))
        print(f"    Batch {batch_start//PINECONE_FETCH_BATCH + 1}: "
              f"Fetched {len(vectors_data)}, embedded {len(all_embeddings)}, "
              f"migrated {total_migrated}/{len(ids)}")

    print(f"    Done: {total_migrated} vectors migrated")
    return total_migrated


def main():
    parser = argparse.ArgumentParser(description="Migrate Pinecone vectors to Cohere 1024d")
    parser.add_argument("--namespace", help="Migrate single namespace")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--skip-default", action="store_true", help="Skip default namespace")
    args = parser.parse_args()

    print("=" * 60)
    print("  PINECONE MIGRATION: 1536d (OpenAI) → 1024d (Cohere)")
    print("=" * 60)
    print(f"  Source: {SOURCE_HOST}")
    print(f"  Target: {TARGET_HOST}")
    print(f"  Cohere model: {COHERE_MODEL}")
    if args.dry_run:
        print("  MODE: DRY RUN")

    # Get source index stats
    print("\n  Fetching source index stats...")
    stats = pinecone_request(SOURCE_HOST, "/describe_index_stats", data={}, method="POST")
    namespaces = stats.get("namespaces", {})
    total_vectors = stats.get("totalVectorCount", 0)
    dimension = stats.get("dimension", "?")

    print(f"  Source: {total_vectors} vectors, {dimension}d, {len(namespaces)} namespaces")

    # Determine which namespaces to migrate
    if args.namespace:
        ns_list = [args.namespace]
    else:
        ns_list = sorted(namespaces.keys())
        if args.skip_default and "" in ns_list:
            ns_list.remove("")

    print(f"  Namespaces to migrate: {len(ns_list)}")
    for ns in ns_list:
        count = namespaces.get(ns, {}).get("vectorCount", "?")
        print(f"    {ns or '(default)'}: {count} vectors")

    # Migrate each namespace
    grand_total = 0
    start_time = time.time()

    for ns in ns_list:
        try:
            count = migrate_namespace(ns, dry_run=args.dry_run)
            grand_total += count
        except Exception as e:
            print(f"    ERROR: {e}")
            continue

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print(f"  MIGRATION COMPLETE")
    print(f"  Total vectors migrated: {grand_total}")
    print(f"  Time elapsed: {elapsed:.1f}s")
    print("=" * 60)

    if not args.dry_run and grand_total > 0:
        # Verify target index
        print("\n  Verifying target index...")
        target_stats = pinecone_request(TARGET_HOST, "/describe_index_stats", data={}, method="POST")
        print(f"  Target: {target_stats.get('totalVectorCount', 0)} vectors, "
              f"{target_stats.get('dimension', '?')}d")


if __name__ == "__main__":
    main()
