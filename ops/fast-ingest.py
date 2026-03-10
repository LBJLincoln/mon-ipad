#!/usr/bin/env python3
"""
Fast parallel ingestion into Pinecone E5 integrated embedding index.

Multi-threaded upsert using concurrent.futures.ThreadPoolExecutor.
Each worker sends 1 record at a time (Pinecone integrated embedding limit)
but N workers run in parallel for N× throughput.

Target: sectors-e5-multilingual index, namespace=sectors
Model:  multilingual-e5-large (1024 dims, built into Pinecone)

Usage:
  source .env.local
  python3 ops/fast-ingest.py --workers 8 --sector finance
  python3 ops/fast-ingest.py --workers 16 --all
  python3 ops/fast-ingest.py --dry-run
  python3 ops/fast-ingest.py --workers 8 --skip-existing
  python3 ops/fast-ingest.py --workers 8 --hf-dataset sujet-ai/Sujet-Finance-Instruct-177k --max 10000
"""

import argparse
import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
NAMESPACE = "sectors"
DATASETS_DIR = os.path.expanduser("~/rag-data-ingestion/datasets/sectors")

MAX_TEXT_LEN = 1500
MIN_TEXT_LEN = 30
MAX_RECORDS = 200000  # safety cap
MAX_WORKERS = 20
DEFAULT_WORKERS = 8
DEFAULT_DELAY = 0.05  # seconds between requests per worker

SECTOR_DIRS = ["finance", "btp", "juridique", "industrie"]

METADATA_FIELDS = [
    "title", "dataset", "decision_date", "jurisdiction",
    "nature", "source_dataset", "texte_titre", "company",
    "doc_type", "doc_period", "question_type",
]

METRICS_DIR = os.path.expanduser("~/mon-ipad/data/metrics")
ERROR_LOG = os.path.join(METRICS_DIR, "ingestion_errors.json")


# ── Thread-safe counters ────────────────────────────────────────
class Stats:
    """Thread-safe counters for tracking ingestion progress."""

    def __init__(self):
        self._lock = threading.Lock()
        self.total = 0
        self.upserted = 0
        self.skipped = 0
        self.errors = 0
        self.start_time = time.monotonic()
        self._error_details = []

    def inc_upserted(self):
        with self._lock:
            self.upserted += 1

    def inc_skipped(self):
        with self._lock:
            self.skipped += 1

    def inc_error(self, record_id, error_msg):
        with self._lock:
            self.errors += 1
            if len(self._error_details) < 500:  # cap stored errors
                self._error_details.append({
                    "id": record_id,
                    "error": error_msg,
                    "ts": datetime.utcnow().isoformat(),
                })

    @property
    def processed(self):
        with self._lock:
            return self.upserted + self.skipped + self.errors

    @property
    def rate(self):
        elapsed = time.monotonic() - self.start_time
        if elapsed < 0.1:
            return 0.0
        with self._lock:
            return self.upserted / elapsed

    @property
    def elapsed(self):
        return time.monotonic() - self.start_time

    def eta_str(self):
        r = self.rate
        if r < 0.01:
            return "?"
        with self._lock:
            remaining = self.total - self.processed
        secs = remaining / r
        if secs < 60:
            return f"{secs:.0f}s"
        elif secs < 3600:
            return f"{secs / 60:.1f}m"
        else:
            return f"{secs / 3600:.1f}h"

    def save_errors(self):
        if not self._error_details:
            return
        os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)
        # Append to existing errors or create new
        existing = []
        if os.path.exists(ERROR_LOG):
            try:
                with open(ERROR_LOG, "r") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing = []
        existing.extend(self._error_details)
        # Keep last 2000 errors
        existing = existing[-2000:]
        with open(ERROR_LOG, "w") as f:
            json.dump(existing, f, indent=2)


# ── Text extraction (from ingest-integrated.py) ────────────────
def extract_text(record):
    """Extract embeddable text from a JSONL record."""
    parts = []

    # Direct text fields (priority order)
    for field in [
        "text", "content", "passage", "document", "documents",
        "context", "article_contenu_text", "article_contenu_markdown",
        "fact",
    ]:
        if field in record and record[field]:
            val = str(record[field]).strip()
            if len(val) > MIN_TEXT_LEN:
                parts.append(val)
                break

    # Q+A composite (convfinqa, financebench, manufacturing_qa, etc.)
    if not parts:
        q = str(record.get("query", record.get("question",
                record.get("Question", "")))).strip()
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


# ── Pinecone operations ────────────────────────────────────────
def upsert_one(record, delay=DEFAULT_DELAY, retries=3):
    """Upsert a single record. Returns (success: bool, error_msg: str|None)."""
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
                method="POST",
            )
            urllib.request.urlopen(req, timeout=30)
            if delay > 0:
                time.sleep(delay)
            return True, None
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:300]
            except Exception:
                pass
            if e.code == 429:
                # Rate limited — exponential backoff
                wait = (2 ** (attempt + 1)) + (attempt * 0.5)
                time.sleep(wait)
                continue
            elif e.code == 409:
                # Conflict / already exists — treat as success
                return True, None
            elif attempt == retries - 1:
                return False, f"HTTP {e.code}: {body}"
            else:
                time.sleep(1)
        except Exception as e:
            if attempt == retries - 1:
                return False, str(e)
            time.sleep(1)
    return False, "max retries exceeded"


def check_id_exists(record_id):
    """Check if a record ID exists in Pinecone. Returns True if exists."""
    try:
        url = f"{PINECONE_HOST}/vectors/fetch?ids={record_id}&namespace={NAMESPACE}"
        req = urllib.request.Request(
            url,
            headers={"Api-Key": PINECONE_API_KEY},
            method="GET",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode())
        return bool(result.get("vectors", {}).get(record_id))
    except Exception:
        return False  # On error, assume not exists and try to upsert


def batch_check_ids(record_ids):
    """Check which IDs already exist in Pinecone. Returns set of existing IDs."""
    existing = set()
    # Pinecone fetch supports up to 1000 IDs at once
    batch_size = 100
    for i in range(0, len(record_ids), batch_size):
        batch = record_ids[i:i + batch_size]
        ids_param = "&".join(f"ids={rid}" for rid in batch)
        try:
            url = f"{PINECONE_HOST}/vectors/fetch?{ids_param}&namespace={NAMESPACE}"
            req = urllib.request.Request(
                url,
                headers={"Api-Key": PINECONE_API_KEY},
                method="GET",
            )
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read().decode())
            vectors = result.get("vectors", {})
            existing.update(vectors.keys())
        except Exception as e:
            # On error, skip this batch check — will try to upsert
            print(f"  WARN: ID check batch failed: {e}", flush=True)
    return existing


# ── Record preparation ──────────────────────────────────────────
def prepare_records_from_jsonl(filepath, sector):
    """Read a JSONL file and return list of prepared records."""
    filename = os.path.basename(filepath)
    source_name = filename.replace(".jsonl", "")
    records = []
    skipped = 0

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

            # Deterministic ID: {sector}-{filename}-{line_num}
            rec_id = f"{sector}-{source_name}-{line_num}"

            record = {
                "_id": rec_id,
                "text": text,
                "sector": sector,
                "source": source_name,
            }

            # Add optional metadata
            for field in METADATA_FIELDS:
                if field in raw and raw[field]:
                    record[field] = str(raw[field])[:200]

            records.append(record)

    return records, skipped


def prepare_records_from_hf(dataset_name, sector, max_records=10000):
    """Download and prepare records from a HuggingFace dataset."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: 'datasets' package required for --hf-dataset. Install: pip install datasets")
        sys.exit(1)

    print(f"  Downloading HF dataset: {dataset_name} ...", flush=True)
    try:
        ds = load_dataset(dataset_name, split="train", streaming=True)
    except Exception as e:
        print(f"  ERROR loading dataset: {e}")
        # Try without streaming
        try:
            ds = load_dataset(dataset_name, split="train")
        except Exception as e2:
            print(f"  ERROR: Could not load dataset: {e2}")
            return [], 0

    records = []
    skipped = 0
    ds_short = dataset_name.split("/")[-1].replace("-", "_")[:30]

    for i, raw in enumerate(ds):
        if i >= max_records:
            break

        # Convert HF record to dict if needed
        if not isinstance(raw, dict):
            raw = dict(raw)

        text = extract_text(raw)
        if len(text) < MIN_TEXT_LEN:
            skipped += 1
            continue

        rec_id = f"{sector}-hf-{ds_short}-{i}"
        record = {
            "_id": rec_id,
            "text": text,
            "sector": sector,
            "source": f"hf:{dataset_name}",
            "dataset": ds_short,
        }

        for field in METADATA_FIELDS:
            if field in raw and raw[field]:
                record[field] = str(raw[field])[:200]

        records.append(record)

        if (i + 1) % 5000 == 0:
            print(f"    ... read {i + 1} from HF ({len(records)} valid)", flush=True)

    print(f"  HF dataset: {len(records)} valid, {skipped} skipped out of {min(i + 1, max_records)} read", flush=True)
    return records, skipped


# ── Worker function ─────────────────────────────────────────────
def worker_upsert(record, stats, sector, delay):
    """Worker function: upsert one record, update stats."""
    success, err = upsert_one(record, delay=delay)
    if success:
        stats.inc_upserted()
    else:
        stats.inc_error(record["_id"], err or "unknown")

    # Progress reporting every 100 processed records
    processed = stats.processed
    if processed % 100 == 0 and processed > 0:
        pct = (processed / stats.total * 100) if stats.total > 0 else 0
        print(
            f"  [{sector}] {processed:,}/{stats.total:,} "
            f"({pct:.0f}%) | "
            f"{stats.rate:.1f} rec/s | "
            f"ok:{stats.upserted:,} err:{stats.errors} skip:{stats.skipped} | "
            f"ETA {stats.eta_str()}",
            flush=True,
        )

    return success


# ── Main ingestion logic ────────────────────────────────────────
def ingest_records(records, sector, stats, workers, delay, skip_existing):
    """Ingest a list of prepared records using thread pool."""
    if not records:
        return

    # Deduplication: check existing IDs
    if skip_existing:
        print(f"  [{sector}] Checking {len(records):,} IDs for duplicates...", flush=True)
        all_ids = [r["_id"] for r in records]
        existing_ids = batch_check_ids(all_ids)
        if existing_ids:
            before = len(records)
            records = [r for r in records if r["_id"] not in existing_ids]
            dup_count = before - len(records)
            stats.skipped += dup_count
            print(f"  [{sector}] Skipping {dup_count:,} existing, {len(records):,} to upsert", flush=True)

    if not records:
        print(f"  [{sector}] All records already exist, nothing to do.", flush=True)
        return

    stats.total += len(records)

    print(
        f"  [{sector}] Starting {len(records):,} records with {workers} workers "
        f"(delay={delay}s/req)",
        flush=True,
    )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(worker_upsert, record, stats, sector, delay): record
            for record in records
        }

        # Wait for all to complete — as_completed gives earliest-done first
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                record = futures[future]
                stats.inc_error(record["_id"], f"future exception: {e}")


# ── CLI ─────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="Fast parallel ingestion into Pinecone E5 integrated embedding index",
    )
    parser.add_argument(
        "--sector",
        choices=SECTOR_DIRS,
        help="Ingest a single sector",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all sectors",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of parallel workers (default: {DEFAULT_WORKERS}, max: {MAX_WORKERS})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay in seconds between requests per worker (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count records only, do not upsert",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Check Pinecone and skip records that already exist",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=MAX_RECORDS,
        help=f"Maximum records to ingest (default: {MAX_RECORDS})",
    )
    parser.add_argument(
        "--hf-dataset",
        type=str,
        help="HuggingFace dataset name (e.g. sujet-ai/Sujet-Finance-Instruct-177k)",
    )
    parser.add_argument(
        "--hf-sector",
        type=str,
        choices=SECTOR_DIRS,
        default="finance",
        help="Sector to assign to HF dataset records (default: finance)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Validate
    workers = min(args.workers, MAX_WORKERS)
    if workers < 1:
        workers = 1

    if not args.sector and not args.all and not args.hf_dataset:
        print("ERROR: Specify --sector <name>, --all, or --hf-dataset <name>")
        print("  python3 ops/fast-ingest.py --workers 8 --sector finance")
        print("  python3 ops/fast-ingest.py --workers 16 --all")
        print("  python3 ops/fast-ingest.py --hf-dataset sujet-ai/Sujet-Finance-Instruct-177k --max 10000")
        sys.exit(1)

    if not PINECONE_API_KEY and not args.dry_run:
        print("ERROR: PINECONE_API_KEY not set. Run: source .env.local")
        sys.exit(1)

    sectors = SECTOR_DIRS if args.all else ([args.sector] if args.sector else [])

    # Banner
    print("=" * 64)
    print("  FAST PARALLEL INGESTION → Pinecone E5")
    print(f"  Index: sectors-e5-multilingual | Namespace: {NAMESPACE}")
    print(f"  Model: multilingual-e5-large (integrated)")
    print(f"  Workers: {workers} | Delay: {args.delay}s | Max: {args.max:,}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    if args.skip_existing:
        print(f"  Dedup: ON (skip existing IDs)")
    if args.hf_dataset:
        print(f"  HF Dataset: {args.hf_dataset} → sector={args.hf_sector}")
    else:
        print(f"  Sectors: {', '.join(sectors)}")
    print("=" * 64, flush=True)

    stats = Stats()
    grand_total_valid = 0
    grand_total_skipped_extract = 0

    # ── HuggingFace dataset mode ──
    if args.hf_dataset:
        sector = args.hf_sector
        records, skipped_extract = prepare_records_from_hf(
            args.hf_dataset, sector, max_records=args.max
        )
        grand_total_valid += len(records)
        grand_total_skipped_extract += skipped_extract

        if args.dry_run:
            print(f"\n  DRY RUN: {len(records):,} records would be ingested")
        else:
            ingest_records(records, sector, stats, workers, args.delay, args.skip_existing)

    # ── Local JSONL mode ──
    else:
        for sector in sectors:
            sector_dir = os.path.join(DATASETS_DIR, sector)
            if not os.path.isdir(sector_dir):
                print(f"\n  WARN: Directory not found: {sector_dir}", flush=True)
                continue

            print(f"\n{'─' * 50}")
            print(f"  SECTOR: {sector.upper()}")
            print(f"{'─' * 50}", flush=True)

            # Collect all records from all JSONL files in this sector
            sector_records = []
            sector_skipped = 0

            for fname in sorted(os.listdir(sector_dir)):
                if not fname.endswith(".jsonl"):
                    continue
                filepath = os.path.join(sector_dir, fname)
                recs, skipped = prepare_records_from_jsonl(filepath, sector)
                sector_records.extend(recs)
                sector_skipped += skipped
                print(f"    {fname}: {len(recs):,} valid, {skipped} skipped", flush=True)

            grand_total_valid += len(sector_records)
            grand_total_skipped_extract += sector_skipped

            # Cap total records
            if grand_total_valid > args.max:
                over = grand_total_valid - args.max
                sector_records = sector_records[:len(sector_records) - over]
                print(f"  CAP: Limiting to {len(sector_records):,} records (--max {args.max:,})", flush=True)

            if args.dry_run:
                print(f"  DRY RUN: {len(sector_records):,} records in {sector}", flush=True)
                continue

            ingest_records(
                sector_records, sector, stats, workers, args.delay, args.skip_existing
            )

            # Check if we hit the cap
            if stats.upserted + stats.errors >= args.max:
                print(f"\n  MAX CAP reached: {args.max:,}", flush=True)
                break

    # ── Summary ──
    elapsed = stats.elapsed
    print(f"\n{'=' * 64}")
    if args.dry_run:
        print(f"  DRY RUN SUMMARY")
        print(f"  Total valid records: {grand_total_valid:,}")
        print(f"  Skipped (bad text):  {grand_total_skipped_extract:,}")
    else:
        print(f"  INGESTION COMPLETE")
        print(f"  Upserted:  {stats.upserted:,}")
        print(f"  Skipped:   {stats.skipped:,} (existing)")
        print(f"  Errors:    {stats.errors}")
        print(f"  Rate:      {stats.rate:.1f} rec/s")
        print(f"  Elapsed:   {elapsed:.1f}s ({elapsed / 60:.1f}m)")
        if stats.errors > 0:
            stats.save_errors()
            print(f"  Error log: {ERROR_LOG}")
    print(f"{'=' * 64}", flush=True)


if __name__ == "__main__":
    main()
