#!/usr/bin/env python3
"""
Ingest Phase 2 dataset contexts into Pinecone (default namespace).

Reads hf-1000.json, extracts paragraph texts from each question's context,
embeds them via Jina API (jina-embeddings-v3, 1024 dims), and upserts
into Pinecone index sota-rag-jina-1024.

Usage:
    source .env.local && python3 scripts/ingest-phase2-contexts.py
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import hashlib
from datetime import datetime, timezone

# -- Configuration --

DATASET_PATH = "/home/termius/mon-ipad/datasets/phase-2/hf-1000.json"
PINECONE_HOST = "https://sota-rag-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
JINA_EMBED_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v3"
EMBED_DIM = 1024
MAX_PARAGRAPH_CHARS = 2000
JINA_BATCH_SIZE = 20
PINECONE_BATCH_SIZE = 100
BATCH_DELAY = 0.5
NAMESPACE = ""

# -- Load environment --

JINA_API_KEY = os.environ.get("JINA_API_KEY", "")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")

if not JINA_API_KEY:
    print("ERROR: JINA_API_KEY not set. Run: source .env.local")
    sys.exit(1)
if not PINECONE_API_KEY:
    print("ERROR: PINECONE_API_KEY not set. Run: source .env.local")
    sys.exit(1)

print(f"JINA_API_KEY: {JINA_API_KEY[:8]}...{JINA_API_KEY[-4:]}")
print(f"PINECONE_API_KEY: {PINECONE_API_KEY[:8]}...{PINECONE_API_KEY[-4:]}")


# -- Helper functions --

def jina_embed(texts):
    """Embed a batch of texts via Jina API. Returns list of 1024-dim vectors."""
    payload = json.dumps({
        "model": JINA_MODEL,
        "input": texts,
        "dimensions": EMBED_DIM,
        "task": "retrieval.passage",
    }).encode("utf-8")

    req = urllib.request.Request(
        JINA_EMBED_URL,
        method="POST",
        headers={
            "Authorization": f"Bearer {JINA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        data=payload,
    )

    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            result = json.loads(resp.read())
            embeddings_data = sorted(result["data"], key=lambda x: x["index"])
            return [e["embedding"] for e in embeddings_data]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429:
                wait = (attempt + 1) * 5
                print(f"  Jina rate limited (429), waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  Jina HTTP {e.code}: {body[:200]}")
            if attempt < 2:
                time.sleep(2)
                continue
            raise
        except Exception as e:
            if attempt < 2:
                print(f"  Jina error: {e}, retrying...")
                time.sleep(2)
                continue
            raise

    return []


def pinecone_upsert(vectors):
    """Upsert a batch of vectors into Pinecone."""
    payload = json.dumps({
        "vectors": vectors,
        "namespace": NAMESPACE,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{PINECONE_HOST}/vectors/upsert",
        method="POST",
        headers={
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json",
        },
        data=payload,
    )

    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
            return result
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"  Pinecone HTTP {e.code}: {body[:200]}")
            if attempt < 2:
                time.sleep(2)
                continue
            raise
        except Exception as e:
            if attempt < 2:
                print(f"  Pinecone error: {e}, retrying...")
                time.sleep(2)
                continue
            raise

    return {}


def pinecone_stats():
    """Get Pinecone index stats."""
    req = urllib.request.Request(
        f"{PINECONE_HOST}/describe_index_stats",
        method="POST",
        headers={
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json",
        },
        data=b"{}",
    )
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())


def parse_context(context_str, dataset_name):
    """
    Parse a context string into a list of {text, title} dicts.
    Graph questions have JSON-encoded lists of paragraph objects.
    Quantitative questions have plain text or table data.
    """
    paragraphs = []

    # Try JSON parse first (graph questions)
    try:
        parsed = json.loads(context_str)
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    text = item.get("paragraph_text", item.get("text", ""))
                    title = item.get("title", "")
                    if text and len(text.strip()) > 10:
                        paragraphs.append({
                            "text": text.strip()[:MAX_PARAGRAPH_CHARS],
                            "title": title,
                        })
                elif isinstance(item, str) and len(item.strip()) > 10:
                    paragraphs.append({"text": item.strip()[:MAX_PARAGRAPH_CHARS], "title": ""})
            return paragraphs
        elif isinstance(parsed, dict):
            text = parsed.get("paragraph_text", parsed.get("text", str(parsed)))
            if text and len(str(text).strip()) > 10:
                paragraphs.append({"text": str(text).strip()[:MAX_PARAGRAPH_CHARS], "title": ""})
            return paragraphs
    except (json.JSONDecodeError, TypeError):
        pass

    # Plain text context (quantitative questions)
    text = context_str.strip()
    if len(text) > 10:
        if len(text) > MAX_PARAGRAPH_CHARS:
            chunks = []
            while text:
                if len(text) <= MAX_PARAGRAPH_CHARS:
                    chunks.append(text)
                    break
                split_at = text.rfind(". ", 0, MAX_PARAGRAPH_CHARS)
                if split_at < 500:
                    split_at = text.rfind(" ", 0, MAX_PARAGRAPH_CHARS)
                if split_at < 100:
                    split_at = MAX_PARAGRAPH_CHARS
                chunks.append(text[:split_at + 1].strip())
                text = text[split_at + 1:].strip()
            for chunk in chunks:
                if len(chunk) > 10:
                    paragraphs.append({"text": chunk, "title": ""})
        else:
            paragraphs.append({"text": text, "title": ""})

    return paragraphs


# -- Main ingestion --

def main():
    print(f"\n{'='*70}")
    print(f"Phase 2 Context Ingestion into Pinecone")
    print(f"{'='*70}")

    # Get initial stats
    print("\nFetching initial Pinecone stats...")
    initial_stats = pinecone_stats()
    initial_default_count = initial_stats.get("namespaces", {}).get("", {}).get("vectorCount", 0)
    print(f"  Default namespace: {initial_default_count} vectors")
    print(f"  Total index: {initial_stats.get('totalVectorCount', 0)} vectors")

    # Load dataset
    print(f"\nLoading dataset: {DATASET_PATH}")
    with open(DATASET_PATH) as f:
        data = json.load(f)
    questions = data["questions"]
    print(f"  Loaded {len(questions)} questions")

    # Parse all contexts into paragraphs
    print("\nParsing contexts...")
    all_chunks = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    seen_texts = set()
    skipped_dupes = 0

    for qi, q in enumerate(questions):
        context_str = q.get("context", "")
        if not context_str:
            continue

        question_id = q.get("id", f"q-{qi}")
        dataset_name = q.get("dataset_name", "unknown")
        category = q.get("category", "unknown")

        paragraphs = parse_context(context_str, dataset_name)

        for pi, para in enumerate(paragraphs):
            text = para["text"]
            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
            if text_hash in seen_texts:
                skipped_dupes += 1
                continue
            seen_texts.add(text_hash)

            vector_id = f"hf-context-{question_id}-{pi}"
            metadata = {
                "content": text,
                "source": dataset_name,
                "category": category,
                "tenant_id": "default",
                "ingested_at": now_iso,
            }
            if para["title"]:
                metadata["title"] = para["title"]

            all_chunks.append((vector_id, text, metadata))

        if (qi + 1) % 100 == 0:
            print(f"  Parsed {qi + 1}/{len(questions)} questions -> {len(all_chunks)} unique chunks so far")

    print(f"\n  Total unique chunks to embed: {len(all_chunks)}")
    print(f"  Duplicates skipped: {skipped_dupes}")

    # Embed and upsert in batches
    print(f"\nStarting embedding + upsert...")
    print(f"  Jina batch size: {JINA_BATCH_SIZE}")
    print(f"  Pinecone batch size: {PINECONE_BATCH_SIZE}")

    total_embedded = 0
    total_upserted = 0
    failed_embed = 0
    failed_upsert = 0
    pending_vectors = []

    start_time = time.time()

    for batch_start in range(0, len(all_chunks), JINA_BATCH_SIZE):
        batch_end = min(batch_start + JINA_BATCH_SIZE, len(all_chunks))
        batch = all_chunks[batch_start:batch_end]
        texts = [chunk[1] for chunk in batch]

        try:
            embeddings = jina_embed(texts)
            total_embedded += len(embeddings)

            for i, emb in enumerate(embeddings):
                vec_id, text, metadata = batch[i]
                pending_vectors.append({
                    "id": vec_id,
                    "values": emb,
                    "metadata": metadata,
                })
        except Exception as e:
            print(f"  EMBED FAILED batch {batch_start}-{batch_end}: {e}")
            failed_embed += len(batch)
            continue

        # Upsert to Pinecone when we have enough
        while len(pending_vectors) >= PINECONE_BATCH_SIZE:
            upsert_batch = pending_vectors[:PINECONE_BATCH_SIZE]
            pending_vectors = pending_vectors[PINECONE_BATCH_SIZE:]
            try:
                result = pinecone_upsert(upsert_batch)
                upserted = result.get("upsertedCount", len(upsert_batch))
                total_upserted += upserted
            except Exception as e:
                print(f"  UPSERT FAILED: {e}")
                failed_upsert += len(upsert_batch)

        # Progress logging
        processed = batch_end
        if processed % 100 < JINA_BATCH_SIZE or processed == len(all_chunks):
            elapsed = time.time() - start_time
            rate = total_embedded / elapsed if elapsed > 0 else 0
            eta = (len(all_chunks) - processed) / rate if rate > 0 else 0
            print(f"  [{processed}/{len(all_chunks)}] embedded={total_embedded} upserted={total_upserted} "
                  f"failed_embed={failed_embed} failed_upsert={failed_upsert} "
                  f"rate={rate:.1f}/s ETA={eta:.0f}s")

        time.sleep(BATCH_DELAY)

    # Flush remaining vectors
    if pending_vectors:
        try:
            result = pinecone_upsert(pending_vectors)
            upserted = result.get("upsertedCount", len(pending_vectors))
            total_upserted += upserted
        except Exception as e:
            print(f"  FINAL UPSERT FAILED: {e}")
            failed_upsert += len(pending_vectors)

    elapsed = time.time() - start_time

    # Final stats
    print(f"\n{'='*70}")
    print(f"INGESTION COMPLETE")
    print(f"{'='*70}")
    print(f"  Time: {elapsed:.1f}s ({elapsed/60:.1f}m)")
    print(f"  Chunks processed: {len(all_chunks)}")
    print(f"  Embedded: {total_embedded}")
    print(f"  Upserted: {total_upserted}")
    print(f"  Failed embed: {failed_embed}")
    print(f"  Failed upsert: {failed_upsert}")

    # Verify with Pinecone stats
    print(f"\nVerifying Pinecone index stats...")
    time.sleep(2)
    final_stats = pinecone_stats()
    final_default_count = final_stats.get("namespaces", {}).get("", {}).get("vectorCount", 0)
    print(f"  Default namespace: {initial_default_count} -> {final_default_count} vectors")
    print(f"  Growth: +{final_default_count - initial_default_count} vectors")
    print(f"  Total index: {final_stats.get('totalVectorCount', 0)} vectors")
    print(f"\nDone.")


if __name__ == "__main__":
    main()
