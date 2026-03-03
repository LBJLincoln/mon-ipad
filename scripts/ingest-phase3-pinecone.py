#!/usr/bin/env python3
"""Ingest Phase 3 standard contexts into Pinecone default namespace.

Extracts unique context paragraphs from datasets/phase-3/standard-8700.json,
embeds them via Jina API, and upserts to Pinecone 'sota-rag-jina-1024' default namespace.

Features:
- Deduplication by content hash
- Progress state file for resume after interruption
- Batch embedding (20 texts per call) with rate limiting
- Token counting to respect Jina free tier (~1M tokens/day)

Usage:
  source .env.local
  python3 scripts/ingest-phase3-pinecone.py                    # Full run
  python3 scripts/ingest-phase3-pinecone.py --max-tokens 500000 # Limit to 500K tokens
  python3 scripts/ingest-phase3-pinecone.py --dry-run           # Count only, no embedding
"""
import json, os, sys, hashlib, time, urllib.request, urllib.error

# Config
DATASET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "datasets", "phase-3", "standard-8700.json")
STATE_FILE = "/tmp/ingest-phase3-state.json"
JINA_API_KEY = os.environ.get("JINA_API_KEY", "")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sota-rag-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
NAMESPACE = ""  # default namespace
BATCH_SIZE = 20
EMBED_DIM = 1024
MAX_TOKENS_DEFAULT = 1_000_000  # ~1M tokens per run
CHARS_PER_TOKEN = 4  # rough estimate


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"completed_hashes": [], "total_embedded": 0, "total_tokens_used": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def extract_unique_contexts(filepath):
    """Extract unique context paragraphs, deduplicated by hash."""
    with open(filepath) as f:
        data = json.load(f)

    contexts = {}  # hash -> text
    for q in data.get("questions", []):
        ctx = q.get("context", "").strip()
        if not ctx or len(ctx) < 50:
            continue
        h = hashlib.md5(ctx.encode()).hexdigest()
        if h not in contexts:
            contexts[h] = ctx
    return contexts


def embed_batch(texts, api_key):
    """Embed a batch of texts via Jina API."""
    url = "https://api.jina.ai/v1/embeddings"
    body = json.dumps({
        "model": "jina-embeddings-v3",
        "task": "retrieval.passage",
        "dimensions": EMBED_DIM,
        "input": texts
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "NomosRAG/1.0",
        "Accept": "application/json"
    })
    resp = urllib.request.urlopen(req, timeout=60)
    result = json.loads(resp.read().decode())
    return [item["embedding"] for item in result["data"]]


def upsert_pinecone(vectors, api_key, host, namespace=""):
    """Upsert vectors to Pinecone."""
    url = f"{host}/vectors/upsert"
    body = json.dumps({
        "vectors": vectors,
        "namespace": namespace
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Api-Key": api_key
    })
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode())


def main():
    dry_run = "--dry-run" in sys.argv
    max_tokens = MAX_TOKENS_DEFAULT
    for i, arg in enumerate(sys.argv):
        if arg == "--max-tokens" and i + 1 < len(sys.argv):
            max_tokens = int(sys.argv[i + 1])

    if not dry_run and (not JINA_API_KEY or not PINECONE_API_KEY):
        print("ERROR: JINA_API_KEY and PINECONE_API_KEY required. Run: source .env.local")
        sys.exit(1)

    print(f"Loading contexts from {DATASET}...")
    contexts = extract_unique_contexts(DATASET)
    print(f"  {len(contexts)} unique contexts")

    # Load state for resume
    state = load_state()
    completed = set(state.get("completed_hashes", []))
    tokens_used = state.get("total_tokens_used", 0)

    # Filter out already-done contexts
    pending = {h: t for h, t in contexts.items() if h not in completed}
    print(f"  {len(completed)} already done, {len(pending)} remaining")

    if dry_run:
        total_chars = sum(len(t) for t in pending.values())
        est_tokens = total_chars // CHARS_PER_TOKEN
        print(f"\n  DRY RUN: {total_chars:,} chars, ~{est_tokens:,} tokens estimated")
        print(f"  At 1M tokens/day: ~{est_tokens / 1_000_000:.1f} days")
        return

    # Process in batches
    pending_items = list(pending.items())
    total_batches = (len(pending_items) + BATCH_SIZE - 1) // BATCH_SIZE
    batch_num = 0
    errors = 0

    for i in range(0, len(pending_items), BATCH_SIZE):
        batch = pending_items[i:i + BATCH_SIZE]
        batch_hashes = [h for h, _ in batch]
        batch_texts = [t for _, t in batch]

        # Estimate tokens
        batch_chars = sum(len(t) for t in batch_texts)
        batch_tokens_est = batch_chars // CHARS_PER_TOKEN

        if tokens_used + batch_tokens_est > max_tokens:
            print(f"\n  Token limit reached ({tokens_used:,}/{max_tokens:,}). Stopping.")
            print(f"  Resume with: python3 scripts/ingest-phase3-pinecone.py")
            break

        batch_num += 1
        try:
            # Embed
            embeddings = embed_batch(batch_texts, JINA_API_KEY)

            # Prepare vectors
            vectors = []
            for j, (h, text) in enumerate(batch):
                vectors.append({
                    "id": f"p3-std-{h}",
                    "values": embeddings[j],
                    "metadata": {
                        "text": text[:40000],  # Pinecone metadata limit
                        "source": "phase3_standard",
                        "content_hash": h
                    }
                })

            # Upsert
            upsert_pinecone(vectors, PINECONE_API_KEY, PINECONE_HOST, NAMESPACE)

            # Update state
            tokens_used += batch_tokens_est
            completed.update(batch_hashes)
            state["completed_hashes"] = list(completed)
            state["total_embedded"] = len(completed)
            state["total_tokens_used"] = tokens_used

            if batch_num % 5 == 0:
                save_state(state)

            done_pct = len(completed) / len(contexts) * 100
            print(f"  Batch {batch_num}/{total_batches}: +{len(batch)} vectors, "
                  f"{len(completed)}/{len(contexts)} ({done_pct:.1f}%), "
                  f"~{tokens_used:,} tokens used")

            # Rate limit: ~2 calls/sec
            time.sleep(0.5)
            errors = 0

        except urllib.error.HTTPError as e:
            errors += 1
            body = e.read().decode()[:200]
            print(f"  ERROR batch {batch_num}: HTTP {e.code} — {body}")
            if e.code == 429:
                wait = min(60, 10 * errors)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif errors >= 3:
                print(f"  3 consecutive errors, stopping.")
                break
            time.sleep(2)
        except Exception as e:
            errors += 1
            print(f"  ERROR batch {batch_num}: {e}")
            if errors >= 3:
                print(f"  3 consecutive errors, stopping.")
                break
            time.sleep(2)

    # Final save
    save_state(state)
    print(f"\nDone: {len(completed)}/{len(contexts)} contexts embedded, "
          f"~{tokens_used:,} tokens used")
    print(f"State saved to {STATE_FILE}")


if __name__ == "__main__":
    main()
