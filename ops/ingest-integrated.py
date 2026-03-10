#!/usr/bin/env python3
"""
Ingest sector data into Pinecone with INTEGRATED embedding (multilingual-e5-large).
No external embeddings API needed — Pinecone embeds on upsert.

Target: sectors-e5-multilingual index, namespace=sectors
Model: multilingual-e5-large (1024 dims, built into Pinecone)

Usage:
  source .env.local
  python3 ops/ingest-integrated.py                  # all
  python3 ops/ingest-integrated.py --sector finance  # one sector
  python3 ops/ingest-integrated.py --dry-run         # count only
"""

import json
import os
import sys
import gc
import time
import urllib.request
import urllib.error

# ── Config ──────────────────────────────────────────────────────
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
NAMESPACE = "sectors"
DATASETS_DIR = os.path.expanduser("~/rag-data-ingestion/datasets/sectors")

UPSERT_BATCH = 20  # records per upsert (Pinecone integrated embed limit)
MAX_TEXT_LEN = 1500  # chars per text field
MIN_TEXT_LEN = 30
MAX_RECORDS = 50000  # safety cap

SECTOR_DIRS = ["finance", "btp", "juridique", "industrie"]


def extract_text(record):
    """Extract embeddable text from a JSONL record."""
    parts = []
    for field in ["text", "content", "passage", "document", "context",
                   "article_contenu_text", "article_contenu_markdown", "fact"]:
        if field in record and record[field]:
            val = str(record[field]).strip()
            if len(val) > MIN_TEXT_LEN:
                parts.append(val)
                break
    if not parts:
        q = str(record.get("query", record.get("question",
                record.get("Question", "")))).strip()
        a = str(record.get("answer", record.get("response",
                record.get("Answer", record.get("Explanation", ""))))).strip()
        if q and a:
            parts.append(f"Question: {q}\nAnswer: {a}")
        elif q:
            parts.append(q)
    title = str(record.get("title", record.get("texte_titre", ""))).strip()
    if title and len(title) > 5:
        parts.insert(0, title)
    summary = str(record.get("summary", "")).strip()
    if summary and len(summary) > 20:
        parts.append(summary)
    return "\n".join(parts)[:MAX_TEXT_LEN]


def upsert_one_record(record, retries=3):
    """Upsert a single record with integrated embedding (Pinecone embeds it)."""
    data = json.dumps(record).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{PINECONE_HOST}/records/namespaces/{NAMESPACE}/upsert",
                data=data,
                headers={
                    "Api-Key": PINECONE_API_KEY,
                    "Content-Type": "application/json",
                },
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=30)
            return True
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            if e.code == 429:  # Rate limit
                time.sleep(2 ** (attempt + 1))
            elif attempt == retries - 1:
                print(f"    ERR {e.code}: {body}", flush=True)
                return False
        except Exception as e:
            if attempt == retries - 1:
                print(f"    ERR: {e}", flush=True)
                return False
            time.sleep(1)
    return False


def ingest_file(filepath, sector, dry_run=False):
    """Ingest one JSONL file."""
    filename = os.path.basename(filepath)
    print(f"\n  [{sector}] {filename}", flush=True)

    records = []
    skipped = 0
    total = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            text = extract_text(raw)
            if len(text) < MIN_TEXT_LEN:
                skipped += 1
                continue

            rec_id = raw.get("id", f"{sector}-{filename.replace('.jsonl','')}-{line_num}")
            record = {
                "_id": str(rec_id),
                "text": text,
                "sector": sector,
                "source": filename.replace(".jsonl", ""),
            }
            # Add optional metadata (only string/number/bool/string-array)
            for field in ["title", "dataset", "decision_date", "jurisdiction",
                          "nature", "source_dataset", "texte_titre"]:
                if field in raw and raw[field]:
                    record[field] = str(raw[field])[:200]

            records.append(record)
            total += 1

    print(f"    {total} valid, {skipped} skipped", flush=True)

    if dry_run:
        return total, 0

    # Upsert one record at a time (Pinecone integrated embedding API)
    upserted = 0
    for i, record in enumerate(records):
        if upsert_one_record(record):
            upserted += 1
        if (i + 1) % 100 == 0:
            print(f"    ... {upserted}/{i+1} upserted ({total} total)", flush=True)
            gc.collect()
            time.sleep(0.05)  # Brief pause for rate limits

    print(f"    DONE: {upserted}/{total}", flush=True)
    return total, upserted


def main():
    dry_run = "--dry-run" in sys.argv
    sector_filter = None
    if "--sector" in sys.argv:
        idx = sys.argv.index("--sector")
        if idx + 1 < len(sys.argv):
            sector_filter = sys.argv[idx + 1]

    if not PINECONE_API_KEY and not dry_run:
        print("ERROR: PINECONE_API_KEY not set")
        sys.exit(1)

    print("=" * 60)
    print("  INTEGRATED EMBEDDING INGESTION → Pinecone")
    print(f"  Index: sectors-e5-multilingual | Namespace: {NAMESPACE}")
    print(f"  Model: multilingual-e5-large (built-in)")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 60, flush=True)

    grand_total = 0
    grand_upserted = 0

    for sector in SECTOR_DIRS:
        if sector_filter and sector != sector_filter:
            continue
        sector_dir = os.path.join(DATASETS_DIR, sector)
        if not os.path.isdir(sector_dir):
            continue

        print(f"\n{'─'*40}\n  SECTOR: {sector.upper()}\n{'─'*40}", flush=True)

        for fname in sorted(os.listdir(sector_dir)):
            if not fname.endswith(".jsonl"):
                continue
            filepath = os.path.join(sector_dir, fname)
            total, upserted = ingest_file(filepath, sector, dry_run)
            grand_total += total
            grand_upserted += upserted

            if grand_upserted >= MAX_RECORDS:
                print(f"\n  SAFETY CAP reached: {MAX_RECORDS}")
                break
            gc.collect()

        if grand_upserted >= MAX_RECORDS:
            break

    print(f"\n{'='*60}")
    print(f"  TOTAL: {grand_total} records → {grand_upserted} upserted")
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
