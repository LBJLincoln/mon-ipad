#!/usr/bin/env python3
"""
S96 Direct Ingestion — Simple and fast.
Bypasses the complex fast-ingest.py in favor of a minimal approach
that is proven to work at 7+ rec/s.

Usage:
  source .env.local && python3 -u ops/ingest-s96-direct.py
"""
import json
import os
import sys
import time
import threading
import requests
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Force unbuffered
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── Config ──
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
NAMESPACE = "sectors"
UPSERT_URL = f"{PINECONE_HOST}/records/namespaces/{NAMESPACE}/upsert"
DATASETS_DIR = os.path.expanduser("~/rag-data-ingestion/datasets/sectors")
PROGRESS_FILE = os.path.expanduser("~/mon-ipad/data/ingest/progress.json")
LOG_FILE = os.path.expanduser("~/mon-ipad/data/ingest/ingest-s96.log")

MAX_TEXT_LEN = 1500
MIN_TEXT_LEN = 30
WORKERS = 4
BATCH_SIZE = 50  # Submit futures in small batches

SECTOR_DIRS = ["finance", "btp", "juridique", "industrie"]

# ── Thread-local sessions ──
_local = threading.local()
_lock = threading.Lock()
_stats = {"ok": 0, "err": 0, "skip": 0, "total": 0}


def get_session():
    if not hasattr(_local, "session"):
        s = requests.Session()
        s.mount("https://", HTTPAdapter(pool_connections=1, pool_maxsize=1))
        s.headers.update({
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json",
        })
        _local.session = s
    return _local.session


def log(msg):
    line = f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def upsert(record):
    """Upsert one record. Returns True on success."""
    for attempt in range(3):
        try:
            resp = get_session().post(UPSERT_URL, json=record, timeout=15)
            if resp.status_code in (200, 201, 409):
                with _lock:
                    _stats["ok"] += 1
                return True
            elif resp.status_code == 429:
                time.sleep(min(2 ** attempt + 0.5, 5))
                continue
            else:
                with _lock:
                    _stats["err"] += 1
                return False
        except Exception:
            if attempt == 2:
                with _lock:
                    _stats["err"] += 1
                return False
            time.sleep(0.5)
    with _lock:
        _stats["err"] += 1
    return False


def extract_text(record):
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
                record.get("Question", record.get("inputs",
                record.get("user_prompt", "")))))).strip()
        a = str(record.get("answer", record.get("response",
                record.get("Answer", record.get("Explanation",
                record.get("reason", "")))))).strip()
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


def get_vector_count():
    try:
        resp = requests.post(
            f"{PINECONE_HOST}/describe_index_stats",
            headers={"Api-Key": PINECONE_API_KEY},
            json={},
            timeout=15,
        )
        return resp.json().get("totalVectorCount", 0)
    except Exception:
        return -1


def check_existing_ids(ids):
    """Check which IDs already exist. Returns set of existing IDs."""
    existing = set()
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        ids_param = "&".join(f"ids={rid}" for rid in batch)
        try:
            resp = requests.get(
                f"{PINECONE_HOST}/vectors/fetch?{ids_param}&namespace={NAMESPACE}",
                headers={"Api-Key": PINECONE_API_KEY},
                timeout=30,
            )
            vectors = resp.json().get("vectors", {})
            existing.update(vectors.keys())
        except Exception:
            pass
    return existing


def load_jsonl_records(sector):
    """Load records from JSONL files for a sector."""
    sector_dir = os.path.join(DATASETS_DIR, sector)
    if not os.path.isdir(sector_dir):
        log(f"  WARN: {sector_dir} not found")
        return []

    records = []
    for fname in sorted(os.listdir(sector_dir)):
        if not fname.endswith(".jsonl"):
            continue
        filepath = os.path.join(sector_dir, fname)
        source_name = fname.replace(".jsonl", "")
        count = 0
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = extract_text(raw)
                if len(text) < MIN_TEXT_LEN:
                    continue
                rec_id = f"{sector}-{source_name}-{line_num}"
                record = {
                    "_id": rec_id,
                    "text": text,
                    "sector": sector,
                    "source": source_name,
                }
                records.append(record)
                count += 1
        log(f"    {fname}: {count} records")
    return records


def load_hf_records(dataset_name, sector, max_records=10000):
    """Load records from HuggingFace dataset."""
    try:
        from datasets import load_dataset
    except ImportError:
        log("  ERROR: datasets library not available")
        return []

    log(f"  Loading HF: {dataset_name} (max {max_records})...")
    try:
        ds = load_dataset(dataset_name, split="train", streaming=True)
    except Exception as e:
        log(f"  ERROR: {e}")
        return []

    records = []
    ds_short = dataset_name.split("/")[-1].replace("-", "_")[:30]

    for i, raw in enumerate(ds):
        if i >= max_records:
            break
        if not isinstance(raw, dict):
            raw = dict(raw)
        text = extract_text(raw)
        if len(text) < MIN_TEXT_LEN:
            continue
        rec_id = f"{sector}-hf-{ds_short}-{i}"
        records.append({
            "_id": rec_id,
            "text": text,
            "sector": sector,
            "source": f"hf:{dataset_name}",
        })
        if (i + 1) % 2000 == 0:
            log(f"    ... {i + 1} read, {len(records)} valid")

    log(f"  HF loaded: {len(records)} valid from {min(i + 1, max_records)} read")
    return records


def ingest_batch(records, label):
    """Ingest a list of records using ThreadPoolExecutor."""
    if not records:
        return

    # Dedup
    log(f"  Checking {len(records)} IDs for duplicates...")
    all_ids = [r["_id"] for r in records]
    existing = check_existing_ids(all_ids)
    if existing:
        before = len(records)
        records = [r for r in records if r["_id"] not in existing]
        with _lock:
            _stats["skip"] += before - len(records)
        log(f"  Skipping {before - len(records)} existing, {len(records)} to upsert")

    if not records:
        log(f"  All records already exist.")
        return

    with _lock:
        _stats["total"] += len(records)

    log(f"  Starting {len(records)} records with {WORKERS} workers...")
    start = time.time()

    # Process in small batches to avoid overwhelming the GIL
    for batch_start in range(0, len(records), BATCH_SIZE):
        batch = records[batch_start:batch_start + BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            list(executor.map(upsert, batch))

        # Progress
        elapsed = time.time() - start
        done = min(batch_start + BATCH_SIZE, len(records))
        rate = _stats["ok"] / elapsed if elapsed > 0.1 else 0
        log(f"  [{label}] {done}/{len(records)} | {rate:.1f} rec/s | ok:{_stats['ok']} err:{_stats['err']}")

        # Write progress file
        try:
            os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
            with open(PROGRESS_FILE, "w") as f:
                json.dump({
                    "phase": label,
                    "processed": done,
                    "total": len(records),
                    "ok": _stats["ok"],
                    "err": _stats["err"],
                    "skip": _stats["skip"],
                    "rate": f"{rate:.1f} rec/s",
                    "elapsed_s": round(elapsed, 1),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }, f, indent=2)
        except Exception:
            pass


def main():
    if not PINECONE_API_KEY:
        print("ERROR: PINECONE_API_KEY not set. Run: source .env.local")
        sys.exit(1)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    # Clear log
    with open(LOG_FILE, "w") as f:
        f.write("")

    start_count = get_vector_count()
    log("=" * 60)
    log("  S96 DIRECT INGESTION")
    log(f"  Start vectors: {start_count:,}")
    log(f"  Target: 50,000")
    log(f"  Workers: {WORKERS} | Batch: {BATCH_SIZE}")
    log("=" * 60)

    # ── Phase 1: Local JSONL ──
    log("")
    log("=== PHASE 1: Local JSONL (all sectors) ===")
    for sector in SECTOR_DIRS:
        log(f"  SECTOR: {sector.upper()}")
        records = load_jsonl_records(sector)
        ingest_batch(records, f"P1-{sector}")

    count = get_vector_count()
    log(f"  Post-Phase-1 vectors: {count:,} (added {count - start_count:,})")

    # ── Phase 2: HF Sujet Finance (10K) ──
    log("")
    log("=== PHASE 2: HF Sujet-Finance-Instruct (10K) ===")
    records = load_hf_records("sujet-ai/Sujet-Finance-Instruct-177k", "finance", 10000)
    ingest_batch(records, "P2-finance-hf")

    count = get_vector_count()
    log(f"  Post-Phase-2 vectors: {count:,} (added {count - start_count:,})")

    # ── Phase 3: HF Cold French Law (10K) ──
    log("")
    log("=== PHASE 3: HF Cold-French-Law (10K) ===")
    records = load_hf_records("harvard-lil/cold-french-law", "juridique", 10000)
    ingest_batch(records, "P3-juridique-hf")

    final_count = get_vector_count()
    log("")
    log("=" * 60)
    log("  INGESTION COMPLETE")
    log(f"  Final vectors: {final_count:,}")
    log(f"  Added: {final_count - start_count:,}")
    log(f"  Target: 50,000")
    log(f"  Gap: {max(0, 50000 - final_count):,}")
    log(f"  Stats: ok={_stats['ok']} err={_stats['err']} skip={_stats['skip']}")
    log("=" * 60)


if __name__ == "__main__":
    main()
