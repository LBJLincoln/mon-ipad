#!/usr/bin/env python3
"""
Clean Ingestion Pipeline — Purge junk, re-ingest ONLY high-quality sector data.

This script:
1. Purges ALL vectors from both Pinecone indexes (sectors namespace)
2. Re-ingests ONLY curated GOOD files into sectors-e5-multilingual
   (integrated embedding with multilingual-e5-large — Pinecone embeds server-side)
3. Skips junk files (no text, wrong language, irrelevant content)

GOOD files (curated, high-quality):
  Finance:   convfinqa, financebench, finqa_ragbench, tatqa, tatqa_ragbench
  BTP:       btp-boamp-marches
  Juridique: cold_french_law, french_case_law_cetat, french_case_law_juri
  Industrie: ragbench_emanual, manufacturing_qa

Usage:
  source .env.local
  python3 ops/clean-ingest.py                    # full run (purge + ingest)
  python3 ops/clean-ingest.py --dry-run          # count records without touching Pinecone
  python3 ops/clean-ingest.py --ingest-only      # skip purge, just ingest
  python3 ops/clean-ingest.py --purge-only       # purge both indexes, don't ingest
  python3 ops/clean-ingest.py --sector finance   # single sector only
"""

import json
import os
import sys
import gc
import time
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Suppress SSL warnings (Pinecone uses valid certs but verify=False is safer on some VMs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ──────────────────────────────────────────────────────
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
E5_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
JINA_HOST = "https://website-sectors-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
NAMESPACE = "sectors"
DATASETS_DIR = os.path.expanduser("~/rag-data-ingestion/datasets/sectors")

MIN_TEXT_LEN = 50       # Skip records with text shorter than this
MAX_TEXT_LEN = 2000     # Truncate text to this length
CONCURRENCY = 8         # Parallel upsert threads
PROGRESS_INTERVAL = 100  # Print progress every N records

# ── Curated file list — ONLY these get ingested ─────────────────
GOOD_FILES = {
    "finance": [
        "convfinqa.jsonl",
        "financebench.jsonl",
        "finqa_ragbench.jsonl",
        "tatqa.jsonl",
        "tatqa_ragbench.jsonl",
    ],
    "btp": [
        "btp-boamp-marches.jsonl",
    ],
    "juridique": [
        "cold_french_law.jsonl",
        "french_case_law_cetat.jsonl",
        "french_case_law_juri.jsonl",
    ],
    "industrie": [
        "ragbench_emanual.jsonl",
        "manufacturing_qa.jsonl",
    ],
}

SECTOR_ORDER = ["finance", "btp", "juridique", "industrie"]


# ── Text extraction ─────────────────────────────────────────────
def extract_text(record):
    """
    Extract the best embeddable text from a JSONL record.

    Priority:
    1. 'text' field (btp-boamp, tatqa)
    2. 'content' field (french_case_law)
    3. 'article_contenu_text' field (cold_french_law)
    4. 'documents' field (ragbench variants)
    5. Q+A composite (convfinqa, financebench, manufacturing_qa)

    Also prepends title/summary if available.
    """
    main_text = ""

    # Try direct text fields in priority order
    for field in ["text", "content", "article_contenu_text", "article_contenu_markdown"]:
        val = record.get(field)
        if val and isinstance(val, str) and len(val.strip()) >= MIN_TEXT_LEN:
            main_text = val.strip()
            break

    # Try 'documents' field (ragbench format — contains the actual document text)
    if not main_text:
        docs = record.get("documents")
        if docs and isinstance(docs, str) and len(docs.strip()) >= MIN_TEXT_LEN:
            main_text = docs.strip()

    # Fallback: build from Q+A pairs
    if not main_text:
        q = record.get("query") or record.get("question") or record.get("Question") or ""
        a = record.get("answer") or record.get("response") or record.get("Answer") or record.get("Explanation") or ""
        q = str(q).strip()
        a = str(a).strip()

        if q and a and (len(q) + len(a)) >= MIN_TEXT_LEN:
            main_text = f"Question: {q}\nReponse: {a}"
        elif q and len(q) >= MIN_TEXT_LEN:
            main_text = q

    if not main_text or len(main_text) < MIN_TEXT_LEN:
        return ""

    # Prepend title if it adds value
    parts = []
    title = record.get("title") or record.get("texte_titre") or ""
    title = str(title).strip()
    if title and len(title) > 10 and title not in main_text[:200]:
        parts.append(title)

    parts.append(main_text)

    # Append summary if available and distinct from main text
    summary = record.get("summary") or ""
    summary = str(summary).strip()
    if summary and len(summary) > 30 and summary not in main_text[:500]:
        parts.append(f"Resume: {summary}")

    # Append keywords for legal docs
    keywords = record.get("keywords") or ""
    keywords = str(keywords).strip()
    if keywords and len(keywords) > 20:
        parts.append(f"Mots-cles: {keywords[:300]}")

    combined = "\n\n".join(parts)
    return combined[:MAX_TEXT_LEN]


def build_metadata(record, sector, source_file):
    """Extract clean metadata from a record (only string/number/bool values for Pinecone)."""
    meta = {
        "sector": sector,
        "source": source_file.replace(".jsonl", ""),
        "source_file": source_file,
    }

    # Add optional metadata fields if present
    optional_fields = {
        "title": 200,
        "dataset": 100,
        "decision_date": 20,
        "jurisdiction": 100,
        "nature": 50,
        "formation": 100,
        "solution": 100,
        "source_dataset": 100,
        "texte_titre": 200,
        "texte_titre_court": 200,
        "texte_nature": 50,
        "article_num": 50,
        "article_etat": 20,
        "company": 100,
        "doc_type": 50,
        "ecli": 50,
    }

    for field, max_len in optional_fields.items():
        val = record.get(field)
        if val and isinstance(val, (str, int, float, bool)):
            meta[field] = str(val)[:max_len]

    return meta


# ── HTTP Session (connection reuse for speed) ──────────────────
_session = None

def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json",
        })
        _session.verify = False
        # Increase connection pool for concurrency
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=CONCURRENCY + 2,
            pool_maxsize=CONCURRENCY + 2,
            max_retries=0,  # We handle retries ourselves
        )
        _session.mount("https://", adapter)
    return _session


# ── Pinecone API helpers ────────────────────────────────────────
def pinecone_headers():
    return {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
    }


def purge_namespace(host, index_name):
    """Delete ALL vectors in the 'sectors' namespace of an index."""
    print(f"\n  PURGING {index_name} namespace='{NAMESPACE}' ...", flush=True)

    try:
        r = requests.post(
            f"{host}/vectors/delete",
            headers=pinecone_headers(),
            json={"deleteAll": True, "namespace": NAMESPACE},
            verify=False,
            timeout=60,
        )
        if r.status_code == 200:
            print(f"    OK — all vectors deleted (status {r.status_code})", flush=True)
            return True
        else:
            print(f"    FAILED — status {r.status_code}: {r.text[:300]}", flush=True)
            return False
    except Exception as e:
        print(f"    ERROR: {e}", flush=True)
        return False


def get_index_stats(host, index_name):
    """Get vector count for an index."""
    try:
        r = requests.get(
            f"{host}/describe_index_stats",
            headers=pinecone_headers(),
            verify=False,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            ns_data = data.get("namespaces", {}).get(NAMESPACE, {})
            return ns_data.get("vectorCount", 0), data.get("totalVectorCount", 0)
        return -1, -1
    except Exception:
        return -1, -1


def upsert_record(host, record, retries=3):
    """Upsert a single record with integrated embedding (uses connection-pooled session)."""
    session = get_session()
    url = f"{host}/records/namespaces/{NAMESPACE}/upsert"
    for attempt in range(retries):
        try:
            r = session.post(url, json=record, timeout=30)
            if r.status_code == 201:
                return True
            elif r.status_code == 429:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
            elif r.status_code == 409:
                # Conflict = already exists, treat as success
                return True
            else:
                if attempt == retries - 1:
                    print(f"    ERR {r.status_code}: {r.text[:200]}", flush=True)
                    return False
                time.sleep(0.5)
        except requests.exceptions.Timeout:
            if attempt == retries - 1:
                print(f"    TIMEOUT on attempt {attempt+1}", flush=True)
                return False
            time.sleep(1)
        except Exception as e:
            if attempt == retries - 1:
                print(f"    ERR: {e}", flush=True)
                return False
            time.sleep(0.5)
    return False


# ── File ingestion ──────────────────────────────────────────────
def ingest_file(filepath, sector, dry_run=False):
    """Read a JSONL file, extract text, and upsert to Pinecone E5 index."""
    filename = os.path.basename(filepath)
    print(f"\n  [{sector.upper()}] {filename}", flush=True)

    if not os.path.exists(filepath):
        print(f"    FILE NOT FOUND — skipping", flush=True)
        return 0, 0, 0

    valid_records = []
    skipped = 0
    total_lines = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f):
            total_lines += 1
            line = line.strip()
            if not line:
                skipped += 1
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

            # Build record ID — use existing ID if available, else generate
            rec_id = raw.get("id")
            if not rec_id:
                rec_id = f"{sector}-{filename.replace('.jsonl','')}-{line_num}"
            rec_id = str(rec_id)

            # Build the Pinecone record
            metadata = build_metadata(raw, sector, filename)
            record = {"_id": rec_id, "text": text}
            record.update(metadata)

            valid_records.append(record)

    print(f"    {len(valid_records)} valid / {skipped} skipped / {total_lines} total lines", flush=True)

    if dry_run:
        # Show a sample
        if valid_records:
            sample = valid_records[0]
            print(f"    Sample ID: {sample['_id']}", flush=True)
            print(f"    Sample text: {sample['text'][:120]}...", flush=True)
        return len(valid_records), 0, skipped

    # Concurrent upserts using ThreadPoolExecutor
    upserted = 0
    errors = 0
    lock = threading.Lock()
    abort = threading.Event()
    consecutive_errors = 0
    completed = 0
    start_time = time.time()

    def do_upsert(record):
        nonlocal upserted, errors, consecutive_errors, completed
        if abort.is_set():
            return False
        success = upsert_record(E5_HOST, record)
        with lock:
            completed += 1
            if success:
                upserted += 1
                consecutive_errors = 0
            else:
                errors += 1
                consecutive_errors += 1
                if consecutive_errors >= 20:
                    abort.set()
            if completed % PROGRESS_INTERVAL == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                print(f"    ... {upserted}/{completed} upserted (errors: {errors}, {rate:.1f} rec/s)", flush=True)
        return success

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(do_upsert, rec) for rec in valid_records]
        for f in as_completed(futures):
            if abort.is_set():
                break

    if abort.is_set():
        print(f"    ABORTED — too many consecutive errors", flush=True)

    elapsed = time.time() - start_time
    rate = len(valid_records) / elapsed if elapsed > 0 else 0
    print(f"    DONE: {upserted} upserted, {errors} errors ({elapsed:.1f}s, {rate:.1f} rec/s)", flush=True)
    return len(valid_records), upserted, skipped


# ── Main ────────────────────────────────────────────────────────
def main():
    # Parse args
    dry_run = "--dry-run" in sys.argv
    ingest_only = "--ingest-only" in sys.argv
    purge_only = "--purge-only" in sys.argv
    sector_filter = None
    if "--sector" in sys.argv:
        idx = sys.argv.index("--sector")
        if idx + 1 < len(sys.argv):
            sector_filter = sys.argv[idx + 1]

    if not PINECONE_API_KEY and not dry_run:
        print("ERROR: PINECONE_API_KEY not set. Run: source .env.local")
        sys.exit(1)

    # Header
    print()
    print("=" * 65)
    print("  CLEAN INGESTION PIPELINE")
    print("=" * 65)
    print(f"  E5 Index : sectors-e5-multilingual (integrated embedding)")
    print(f"  Jina Index: website-sectors-jina-1024 (purge only)")
    print(f"  Namespace : {NAMESPACE}")
    mode = "DRY RUN" if dry_run else "PURGE ONLY" if purge_only else "INGEST ONLY" if ingest_only else "PURGE + INGEST"
    print(f"  Mode      : {mode}")
    if sector_filter:
        print(f"  Sector    : {sector_filter}")
    print("=" * 65, flush=True)

    # ── Step 0: Show current state ──────────────────────────────
    if not dry_run:
        print("\n--- BEFORE ---", flush=True)
        e5_ns, e5_total = get_index_stats(E5_HOST, "sectors-e5-multilingual")
        jina_ns, jina_total = get_index_stats(JINA_HOST, "website-sectors-jina-1024")
        print(f"  E5   : {e5_ns} vectors in '{NAMESPACE}' ({e5_total} total)", flush=True)
        print(f"  Jina : {jina_ns} vectors in '{NAMESPACE}' ({jina_total} total)", flush=True)

    # ── Step 1: Purge ───────────────────────────────────────────
    if not dry_run and not ingest_only:
        print("\n" + "=" * 65)
        print("  STEP 1: PURGE ALL VECTORS")
        print("=" * 65, flush=True)

        purge_namespace(E5_HOST, "sectors-e5-multilingual")
        purge_namespace(JINA_HOST, "website-sectors-jina-1024")

        # Wait for deletion to propagate
        print("\n  Waiting 10s for deletion to propagate...", flush=True)
        time.sleep(10)

        e5_ns, _ = get_index_stats(E5_HOST, "sectors-e5-multilingual")
        jina_ns, _ = get_index_stats(JINA_HOST, "website-sectors-jina-1024")
        print(f"  E5   after purge: {e5_ns} vectors", flush=True)
        print(f"  Jina after purge: {jina_ns} vectors", flush=True)

    if purge_only:
        print("\n  PURGE ONLY mode — done.", flush=True)
        return

    # ── Step 2: Ingest GOOD files into E5 ───────────────────────
    print("\n" + "=" * 65)
    print("  STEP 2: INGEST CURATED FILES → E5")
    print("=" * 65, flush=True)

    total_valid = 0
    total_upserted = 0
    total_skipped = 0
    file_stats = []

    for sector in SECTOR_ORDER:
        if sector_filter and sector != sector_filter:
            continue

        files = GOOD_FILES.get(sector, [])
        if not files:
            continue

        print(f"\n{'─' * 50}")
        print(f"  SECTOR: {sector.upper()} ({len(files)} files)")
        print(f"{'─' * 50}", flush=True)

        for fname in files:
            filepath = os.path.join(DATASETS_DIR, sector, fname)
            valid, upserted, skipped = ingest_file(filepath, sector, dry_run)
            total_valid += valid
            total_upserted += upserted
            total_skipped += skipped
            file_stats.append((sector, fname, valid, upserted, skipped))
            gc.collect()

    # ── Summary ─────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  SUMMARY")
    print("=" * 65)
    print(f"\n  {'Sector':<12} {'File':<35} {'Valid':>6} {'Upserted':>9} {'Skipped':>8}")
    print(f"  {'─'*12} {'─'*35} {'─'*6} {'─'*9} {'─'*8}")

    for sector, fname, valid, upserted, skipped in file_stats:
        print(f"  {sector:<12} {fname:<35} {valid:>6} {upserted:>9} {skipped:>8}")

    print(f"  {'─'*12} {'─'*35} {'─'*6} {'─'*9} {'─'*8}")
    print(f"  {'TOTAL':<12} {'':<35} {total_valid:>6} {total_upserted:>9} {total_skipped:>8}")

    if not dry_run and not purge_only:
        # Wait for index to update
        print("\n  Waiting 15s for index to update...", flush=True)
        time.sleep(15)

        print("\n--- AFTER ---", flush=True)
        e5_ns, e5_total = get_index_stats(E5_HOST, "sectors-e5-multilingual")
        jina_ns, jina_total = get_index_stats(JINA_HOST, "website-sectors-jina-1024")
        print(f"  E5   : {e5_ns} vectors in '{NAMESPACE}' ({e5_total} total)", flush=True)
        print(f"  Jina : {jina_ns} vectors in '{NAMESPACE}' ({jina_total} total)", flush=True)

    print(f"\n{'=' * 65}")
    print(f"  DONE")
    print(f"{'=' * 65}\n", flush=True)


if __name__ == "__main__":
    main()
