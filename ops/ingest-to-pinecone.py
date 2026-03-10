#!/usr/bin/env python3
"""
Ingest sector JSONL datasets into Pinecone via self-hosted Jina embeddings.

Memory-efficient: streams line-by-line, batches embeddings, gc.collect.
Target: website-sectors-jina-1024, namespace=sectors, 1024 dims.

Usage:
  source .env.local
  python3 ops/ingest-to-pinecone.py                  # all files
  python3 ops/ingest-to-pinecone.py --sector finance  # one sector
  python3 ops/ingest-to-pinecone.py --dry-run         # count only
"""

import json
import os
import sys
import gc
import time
import hashlib
import urllib.request
import urllib.error

# ── Config ──────────────────────────────────────────────────────
EMBEDDINGS_URL = "https://lbjlincoln-nomos-embeddings-api.hf.space/embed"
PINECONE_HOST = "website-sectors-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
NAMESPACE = "sectors"
DATASETS_DIR = os.path.expanduser("~/rag-data-ingestion/datasets/sectors")

EMBED_BATCH = 4  # texts per embedding call (HF Space timeout-safe)
UPSERT_BATCH = 50  # vectors per upsert call
MAX_TEXT_LEN = 2000  # chars per text for embedding
MIN_TEXT_LEN = 30  # skip very short texts
MAX_VECTORS = 50000  # safety cap (don't exceed 100K index limit)

SECTOR_DIRS = ["finance", "btp", "juridique", "industrie"]

# ── Text extraction ─────────────────────────────────────────────
def extract_text(record):
    """Extract embeddable text from a JSONL record (various schemas)."""
    parts = []

    # Priority fields for main content
    for field in ["text", "content", "passage", "document", "context",
                   "article_contenu_text", "article_contenu_markdown", "fact"]:
        if field in record and record[field]:
            val = str(record[field]).strip()
            if len(val) > MIN_TEXT_LEN:
                parts.append(val)
                break

    # If no main content, try Q&A concatenation
    if not parts:
        q = str(record.get("query", record.get("question",
                record.get("Question", "")))).strip()
        a = str(record.get("answer", record.get("response",
                record.get("Answer", record.get("Explanation", ""))))).strip()
        if q and a:
            parts.append(f"Question: {q}\nAnswer: {a}")
        elif q:
            parts.append(q)

    # Add title if available
    title = str(record.get("title", "")).strip()
    if title and len(title) > 5:
        parts.insert(0, title)

    # Add summary if available
    summary = str(record.get("summary", "")).strip()
    if summary and len(summary) > 20:
        parts.append(summary)

    combined = "\n".join(parts)
    return combined[:MAX_TEXT_LEN] if combined else ""


def extract_metadata(record, sector, source_file):
    """Extract metadata for Pinecone storage."""
    meta = {"sector": sector, "source": source_file}
    for field in ["title", "id", "dataset", "decision_date", "jurisdiction",
                   "nature", "keywords", "source_dataset"]:
        if field in record and record[field]:
            val = str(record[field])[:200]
            if val:
                meta[field] = val
    # Store truncated text for retrieval
    text = extract_text(record)
    if text:
        meta["text"] = text[:500]
    return meta


# ── API calls ────────────────────────────────────────────────────
def embed_texts(texts, retries=3):
    """Call self-hosted Jina embeddings API."""
    data = json.dumps({"inputs": texts}).encode()
    req = urllib.request.Request(
        EMBEDDINGS_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    for attempt in range(retries):
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            result = json.loads(resp.read())
            # Response is a list of lists (embeddings)
            if isinstance(result, list) and len(result) == len(texts):
                return result
            elif isinstance(result, dict) and "embeddings" in result:
                return result["embeddings"]
            else:
                print(f"  WARN: unexpected response shape: {type(result)}", flush=True)
                return result if isinstance(result, list) else None
        except Exception as e:
            print(f"  EMBED ERROR (attempt {attempt+1}): {e}", flush=True)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def upsert_vectors(vectors):
    """Upsert vectors to Pinecone."""
    data = json.dumps({"vectors": vectors, "namespace": NAMESPACE}).encode()
    req = urllib.request.Request(
        f"https://{PINECONE_HOST}/vectors/upsert",
        data=data,
        headers={
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json",
        },
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        return result
    except Exception as e:
        print(f"  UPSERT ERROR: {e}", flush=True)
        return None


# ── Main ingestion ───────────────────────────────────────────────
def ingest_file(filepath, sector, dry_run=False):
    """Ingest a single JSONL file into Pinecone."""
    filename = os.path.basename(filepath)
    print(f"\n  [{sector}] {filename}", flush=True)

    texts = []
    metas = []
    ids = []
    skipped = 0
    total = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            text = extract_text(record)
            if len(text) < MIN_TEXT_LEN:
                skipped += 1
                continue

            # Generate stable ID
            text_hash = hashlib.md5(text[:500].encode()).hexdigest()[:12]
            vec_id = f"{sector}-{filename.replace('.jsonl','')}-{line_num}-{text_hash}"

            texts.append(text)
            metas.append(extract_metadata(record, sector, filename))
            ids.append(vec_id)
            total += 1

    print(f"    {total} valid records, {skipped} skipped", flush=True)

    if dry_run:
        return total, 0

    # Embed and upsert in batches
    upserted = 0
    pending_vectors = []

    for i in range(0, len(texts), EMBED_BATCH):
        batch_texts = texts[i:i+EMBED_BATCH]
        batch_ids = ids[i:i+EMBED_BATCH]
        batch_metas = metas[i:i+EMBED_BATCH]

        embeddings = embed_texts(batch_texts)
        if not embeddings or len(embeddings) != len(batch_texts):
            print(f"    SKIP batch {i}-{i+len(batch_texts)}: embedding failed", flush=True)
            continue

        for j, emb in enumerate(embeddings):
            pending_vectors.append({
                "id": batch_ids[j],
                "values": emb,
                "metadata": batch_metas[j],
            })

        # Upsert when we have enough
        if len(pending_vectors) >= UPSERT_BATCH:
            result = upsert_vectors(pending_vectors)
            if result:
                upserted += len(pending_vectors)
            pending_vectors = []

        if (i // EMBED_BATCH) % 5 == 0 and i > 0:
            print(f"    ... {upserted} upserted, processing batch {i}/{len(texts)}", flush=True)
            gc.collect()

    # Final upsert
    if pending_vectors:
        result = upsert_vectors(pending_vectors)
        if result:
            upserted += len(pending_vectors)

    print(f"    DONE: {upserted}/{total} upserted", flush=True)
    return total, upserted


def main():
    dry_run = "--dry-run" in sys.argv
    sector_filter = None
    if "--sector" in sys.argv:
        idx = sys.argv.index("--sector")
        if idx + 1 < len(sys.argv):
            sector_filter = sys.argv[idx + 1]

    if not PINECONE_API_KEY and not dry_run:
        print("ERROR: PINECONE_API_KEY not set. Run: source .env.local")
        sys.exit(1)

    print("=" * 60)
    print(f"  SECTOR DATA INGESTION → Pinecone")
    print(f"  Index: website-sectors-jina-1024 | Namespace: {NAMESPACE}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    if sector_filter:
        print(f"  Sector: {sector_filter}")
    print("=" * 60, flush=True)

    total_records = 0
    total_upserted = 0

    for sector in SECTOR_DIRS:
        if sector_filter and sector != sector_filter:
            continue

        sector_dir = os.path.join(DATASETS_DIR, sector)
        if not os.path.isdir(sector_dir):
            print(f"\n  [{sector}] Directory not found: {sector_dir}")
            continue

        print(f"\n{'─'*40}")
        print(f"  SECTOR: {sector.upper()}")
        print(f"{'─'*40}", flush=True)

        for fname in sorted(os.listdir(sector_dir)):
            if not fname.endswith(".jsonl"):
                continue
            filepath = os.path.join(sector_dir, fname)
            records, upserted = ingest_file(filepath, sector, dry_run)
            total_records += records
            total_upserted += upserted

            if total_upserted >= MAX_VECTORS:
                print(f"\n  SAFETY CAP: {MAX_VECTORS} vectors reached, stopping.")
                break
            gc.collect()

        if total_upserted >= MAX_VECTORS:
            break

    print(f"\n{'='*60}")
    print(f"  TOTAL: {total_records} records → {total_upserted} upserted")
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
