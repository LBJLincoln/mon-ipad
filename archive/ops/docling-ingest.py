#!/usr/bin/env python3
"""
Docling PDF Ingest → E5 Pinecone Pipeline

Downloads PDFs from the Tavily document list, processes them through the
Docling HF Space (convert-url), then upserts the resulting chunks into
the E5 integrated-embedding Pinecone index.

Usage:
  source .env.local
  python3 ops/docling-ingest.py --priority-only
  python3 ops/docling-ingest.py --sector finance --max 5
  python3 ops/docling-ingest.py --all --max 20
  python3 ops/docling-ingest.py --report

Features:
  - Forces IPv4 for Docling calls (IPv6 broken on this VM)
  - Sequential processing (Docling is cpu-basic, one at a time)
  - Graceful error handling: skip failed docs, continue
  - Progress file at data/ingest/docling-progress.json
  - Unique IDs: docling-{sector}-{hash(url)[:8]}-{chunk_idx:03d}
"""

import argparse
import hashlib
import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Force unbuffered output for nohup/background execution
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── Force IPv4 globally ─────────────────────────────────────────
# Monkey-patch socket to prefer IPv4 (IPv6 doesn't work from this VM)
_original_getaddrinfo = socket.getaddrinfo

def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _ipv4_getaddrinfo

# ── Try to use requests (better connection handling) ────────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── Config ──────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCLING_BASE = os.environ.get(
    "DOCLING_URL", "https://lbjlincoln-nomos-docling-api.hf.space"
)
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
NAMESPACE = "sectors"

DOC_LIST_PATH = os.path.join(REPO_ROOT, "sectors", "real-documents-to-ingest.json")
PROGRESS_DIR = os.path.join(REPO_ROOT, "data", "ingest")
PROGRESS_FILE = os.path.join(PROGRESS_DIR, "docling-progress.json")
LOG_FILE = os.path.join(PROGRESS_DIR, "docling-results.json")

DEFAULT_DOCLING_TIMEOUT = 300   # seconds per PDF conversion (cpu-basic needs time)
DOCLING_TIMEOUT = 300           # active timeout (may be overridden by CLI)
PINECONE_TIMEOUT = 15           # seconds per upsert
CHUNK_SIZE = 1000           # chars per chunk
CHUNK_OVERLAP = 200         # overlap between chunks
MIN_CHUNK_LEN = 30          # skip tiny chunks
MAX_TEXT_LEN = 1500          # cap text length for embedding
DELAY_BETWEEN_DOCS = 5      # seconds between documents (be gentle to cpu-basic)
DELAY_AFTER_SUCCESS = 10    # longer delay after a successful conversion (memory recovery)
PINECONE_BATCH_SIZE = 5     # upsert this many records at once (one at a time for integrated)
CONSECUTIVE_TIMEOUT_LIMIT = 3   # restart Space after this many consecutive timeouts
HF_TOKEN = os.environ.get("HF_TOKEN", "")


def url_hash(url: str) -> str:
    """Generate a short hash from a URL for ID generation."""
    return hashlib.md5(url.encode()).hexdigest()[:8]


def make_chunk_id(sector: str, url: str, chunk_idx: int) -> str:
    """Generate unique deterministic ID for a chunk."""
    return f"docling-{sector}-{url_hash(url)}-{chunk_idx:03d}"


def filename_from_url(url: str) -> str:
    """Extract a short filename from a URL for display."""
    path = url.split("?")[0].split("#")[0]
    name = path.rstrip("/").split("/")[-1]
    if len(name) > 50:
        name = name[:47] + "..."
    return name or "unknown"


# ── Load document list ──────────────────────────────────────────

def load_documents(sector_filter=None, priority_only=False, max_docs=None):
    """Load and filter documents from the Tavily list."""
    if not os.path.exists(DOC_LIST_PATH):
        print(f"FATAL: Document list not found: {DOC_LIST_PATH}")
        sys.exit(1)

    with open(DOC_LIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = data.get("documents", [])

    # Filter: priority
    if priority_only:
        docs = [d for d in docs if d.get("priority") == "high"]

    # Filter: sector
    if sector_filter:
        docs = [d for d in docs if d.get("sector", "").lower() == sector_filter.lower()]

    # Filter: ONLY PDFs — Docling is a PDF converter, not HTML
    # Check URL extension (.pdf) and Content-Type via HEAD request
    filtered = []
    skipped_non_pdf = []
    for d in docs:
        url = d.get("url", "")
        url_clean = url.lower().split("?")[0].split("#")[0].rstrip("/")
        is_pdf = url_clean.endswith(".pdf")

        if not is_pdf:
            # Try HEAD request to check Content-Type
            try:
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "Mozilla/5.0")
                resp = urllib.request.urlopen(req, timeout=10)
                ctype = resp.headers.get("Content-Type", "").lower()
                is_pdf = "pdf" in ctype
            except Exception:
                pass  # If HEAD fails, skip non-.pdf URLs

        if is_pdf:
            filtered.append(d)
        else:
            skipped_non_pdf.append(d.get("title", url)[:60])

    if skipped_non_pdf:
        print(f"  Skipped {len(skipped_non_pdf)} non-PDF URLs:")
        for s in skipped_non_pdf[:5]:
            print(f"    - {s}")
        if len(skipped_non_pdf) > 5:
            print(f"    ... and {len(skipped_non_pdf) - 5} more")
    docs = filtered

    # Deduplicate by URL
    seen = set()
    unique = []
    for d in docs:
        if d["url"] not in seen:
            seen.add(d["url"])
            unique.append(d)
    docs = unique

    # Limit
    if max_docs and max_docs > 0:
        docs = docs[:max_docs]

    return docs


# ── Docling API ─────────────────────────────────────────────────

def docling_health():
    """Check Docling API health."""
    url = f"{DOCLING_BASE}/health"
    try:
        if HAS_REQUESTS:
            resp = requests.get(url, timeout=20)
            return resp.status_code == 200, resp.json() if resp.status_code == 200 else {}
        else:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=20)
            data = json.loads(resp.read().decode())
            return True, data
    except Exception as e:
        return False, {"error": str(e)[:200]}


def restart_docling_space():
    """Restart the Docling HF Space and wait for it to come back."""
    if not HF_TOKEN:
        print("    WARN: No HF_TOKEN — cannot restart Space automatically", flush=True)
        return False

    print("    Restarting Docling HF Space...", end=" ", flush=True)
    try:
        restart_url = "https://huggingface.co/api/spaces/LBJLincoln/nomos-docling-api/restart"
        if HAS_REQUESTS:
            resp = requests.post(restart_url, headers={"Authorization": f"Bearer {HF_TOKEN}"}, timeout=30)
            if resp.status_code not in (200, 202):
                print(f"FAILED (HTTP {resp.status_code})", flush=True)
                return False
        else:
            req = urllib.request.Request(
                restart_url,
                headers={"Authorization": f"Bearer {HF_TOKEN}"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"FAILED ({e})", flush=True)
        return False

    # Wait for Space to come back (up to 300s — converter takes time to load)
    print("waiting for restart...", end=" ", flush=True)
    health_ok = False
    for i in range(30):
        time.sleep(10)
        healthy, info = docling_health()
        if healthy:
            converter_loaded = info.get("converter_loaded", False)
            if converter_loaded:
                print(f"UP + converter ready after {(i+1)*10}s", flush=True)
                return True
            elif not health_ok:
                health_ok = True
                print(f"health OK at {(i+1)*10}s, waiting for converter...", end=" ", flush=True)

    if health_ok:
        print("converter not loaded within 300s, proceeding anyway", flush=True)
        return True

    print("TIMEOUT (Space did not respond after 300s)", flush=True)
    return False


def docling_convert(doc_url: str, timeout=None):
    """
    Send a URL to Docling for conversion.
    Returns (chunks_list, metadata_dict, elapsed_seconds, error_string_or_None).
    """
    if timeout is None:
        timeout = DOCLING_TIMEOUT

    endpoint = f"{DOCLING_BASE}/convert-url"
    payload = {
        "url": doc_url,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
    }

    start = time.time()
    try:
        if HAS_REQUESTS:
            resp = requests.post(endpoint, json=payload, timeout=timeout)
            elapsed = time.time() - start
            if resp.status_code != 200:
                return None, {}, elapsed, f"HTTP {resp.status_code}: {resp.text[:300]}"
            data = resp.json()
        else:
            req_data = json.dumps(payload).encode()
            req = urllib.request.Request(
                endpoint,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=timeout)
            elapsed = time.time() - start
            data = json.loads(resp.read().decode())

    except Exception as e:
        elapsed = time.time() - start
        err_type = type(e).__name__
        return None, {}, elapsed, f"{err_type}: {str(e)[:200]}"

    # Check Docling-level status
    status = data.get("status", "unknown")
    if status == "error":
        return None, {}, elapsed, f"Docling error: {data.get('error', 'unknown')}"

    # Extract chunks
    chunks_raw = data.get("chunks", [])
    chunks = []
    for c in chunks_raw:
        if isinstance(c, str):
            text = c.strip()
        elif isinstance(c, dict):
            text = (c.get("text", "") or c.get("content", "")).strip()
        else:
            continue
        if len(text) >= MIN_CHUNK_LEN:
            # Cap text length for embedding
            chunks.append(text[:MAX_TEXT_LEN])

    # If no chunks but full_text exists, manually chunk it
    if not chunks:
        full_text = data.get("full_text", "")
        if full_text and len(full_text) >= MIN_CHUNK_LEN:
            chunks = manual_chunk(full_text, CHUNK_SIZE, CHUNK_OVERLAP)

    meta = {
        "num_pages": data.get("num_pages", 0),
        "num_tables": data.get("num_tables", 0),
        "full_text_chars": len(data.get("full_text", "")),
        "raw_chunks": len(chunks_raw),
        "usable_chunks": len(chunks),
        "processing_time_s": round(elapsed, 2),
    }

    return chunks, meta, elapsed, None


def manual_chunk(text: str, chunk_size: int, overlap: int) -> list:
    """Fallback chunking when Docling doesn't return chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_LEN:
            chunks.append(chunk[:MAX_TEXT_LEN])
        start += chunk_size - overlap
    return chunks


# ── Pinecone E5 Upsert ─────────────────────────────────────────

def upsert_to_pinecone(records: list, retries=3):
    """
    Upsert records to Pinecone E5 integrated-embedding index.
    Each record: {"_id": "...", "text": "...", "sector": "...", "source": "..."}
    Returns (success_count, error_count, errors_list).
    """
    if not PINECONE_API_KEY:
        return 0, len(records), ["PINECONE_API_KEY not set"]

    url = f"{PINECONE_HOST}/records/namespaces/{NAMESPACE}/upsert"
    success = 0
    errors_list = []

    # Upsert one at a time (Pinecone integrated embedding limitation)
    for rec in records:
        ok = False
        for attempt in range(retries):
            try:
                if HAS_REQUESTS:
                    resp = requests.post(
                        url,
                        json=rec,
                        headers={
                            "Api-Key": PINECONE_API_KEY,
                            "Content-Type": "application/json",
                        },
                        timeout=PINECONE_TIMEOUT,
                    )
                    if resp.status_code in (200, 201):
                        ok = True
                        break
                    elif resp.status_code == 409:
                        # Already exists — count as success
                        ok = True
                        break
                    elif resp.status_code == 429:
                        wait = min(2 ** attempt + 0.5, 5)
                        time.sleep(wait)
                        continue
                    elif attempt == retries - 1:
                        errors_list.append(f"{rec['_id']}: HTTP {resp.status_code}")
                    else:
                        time.sleep(0.5)
                else:
                    req_data = json.dumps(rec).encode()
                    req = urllib.request.Request(
                        url,
                        data=req_data,
                        headers={
                            "Api-Key": PINECONE_API_KEY,
                            "Content-Type": "application/json",
                        },
                        method="POST",
                    )
                    urllib.request.urlopen(req, timeout=PINECONE_TIMEOUT)
                    ok = True
                    break
            except urllib.error.HTTPError as e:
                if e.code == 409:
                    ok = True
                    break
                elif e.code == 429:
                    wait = min(2 ** attempt + 0.5, 5)
                    time.sleep(wait)
                    continue
                elif attempt == retries - 1:
                    errors_list.append(f"{rec['_id']}: HTTP {e.code}")
                else:
                    time.sleep(0.5)
            except Exception as e:
                if attempt == retries - 1:
                    errors_list.append(f"{rec['_id']}: {str(e)[:100]}")
                else:
                    time.sleep(0.5)

        if ok:
            success += 1
        # Small delay between upserts
        time.sleep(0.05)

    return success, len(records) - success, errors_list


# ── Progress tracking ──────────────────────────────────────────

class ProgressTracker:
    """Tracks and persists ingestion progress."""

    def __init__(self):
        self.results = []
        self.total_docs = 0
        self.processed_docs = 0
        self.total_chunks_upserted = 0
        self.total_chunks_failed = 0
        self.total_docs_failed = 0
        self.start_time = time.time()

    def add_result(self, doc, chunks_count, upserted, failed, elapsed, error=None):
        """Record result for one document."""
        self.processed_docs += 1
        result = {
            "doc_index": self.processed_docs,
            "title": doc.get("title", "")[:80],
            "url": doc.get("url", ""),
            "sector": doc.get("sector", "unknown"),
            "priority": doc.get("priority", "medium"),
            "chunks_extracted": chunks_count,
            "chunks_upserted": upserted,
            "chunks_failed": failed,
            "elapsed_s": round(elapsed, 1),
            "status": "error" if error else "ok",
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.results.append(result)

        if error:
            self.total_docs_failed += 1
        else:
            self.total_chunks_upserted += upserted
            self.total_chunks_failed += failed

    def save(self):
        """Save progress to JSON files."""
        os.makedirs(PROGRESS_DIR, exist_ok=True)

        # Progress summary
        elapsed_total = time.time() - self.start_time
        progress = {
            "status": "running" if self.processed_docs < self.total_docs else "complete",
            "processed": self.processed_docs,
            "total": self.total_docs,
            "pct": round(self.processed_docs / max(self.total_docs, 1) * 100, 1),
            "docs_ok": self.processed_docs - self.total_docs_failed,
            "docs_failed": self.total_docs_failed,
            "chunks_upserted": self.total_chunks_upserted,
            "chunks_failed": self.total_chunks_failed,
            "elapsed_s": round(elapsed_total, 1),
            "avg_time_per_doc_s": round(elapsed_total / max(self.processed_docs, 1), 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)

        # Detailed results
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "config": {
                "docling_endpoint": DOCLING_BASE,
                "pinecone_index": "sectors-e5-multilingual",
                "namespace": NAMESPACE,
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
            },
            "summary": progress,
            "documents": self.results,
        }
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)


# ── Main processing loop ──────────────────────────────────────

def process_documents(docs, dry_run=False):
    """Process all documents: Docling convert → Pinecone upsert."""
    tracker = ProgressTracker()
    tracker.total_docs = len(docs)

    print("=" * 70)
    print("  DOCLING PDF INGEST → E5 PINECONE")
    print(f"  Docling:   {DOCLING_BASE}")
    print(f"  Pinecone:  sectors-e5-multilingual / {NAMESPACE}")
    print(f"  Documents: {len(docs)}")
    print(f"  Chunk:     {CHUNK_SIZE} chars, {CHUNK_OVERLAP} overlap")
    print(f"  Timeout:   {DOCLING_TIMEOUT}s per doc")
    print(f"  Dry run:   {dry_run}")
    print("=" * 70)

    # Health check
    print("\n  Docling health check...", end=" ", flush=True)
    healthy, info = docling_health()
    if healthy:
        print("UP")
    else:
        print(f"WARN: {info.get('error', 'not responding')}")
        print("  Will attempt processing anyway (Space may wake on first request)...")

    if not PINECONE_API_KEY and not dry_run:
        print("\n  FATAL: PINECONE_API_KEY not set. Run: source .env.local")
        sys.exit(1)

    print()

    consecutive_timeouts = 0

    for i, doc in enumerate(docs):
        doc_start = time.time()
        sector = doc.get("sector", "unknown")
        title = doc.get("title", "")[:60]
        url = doc.get("url", "")
        fname = filename_from_url(url)
        prefix = f"[{i+1}/{len(docs)}]"

        # Step 1: Convert with Docling
        chunks, meta, elapsed, error = docling_convert(url)

        if error:
            is_timeout = "timeout" in error.lower() or "timed out" in error.lower()
            print(f"  {prefix} {sector:10s} | ERROR  | {elapsed:.1f}s | {fname}")
            print(f"           {error[:100]}")
            tracker.add_result(doc, 0, 0, 0, time.time() - doc_start, error=error)
            tracker.save()

            # Track consecutive timeouts — Space may need restart
            if is_timeout:
                consecutive_timeouts += 1
                if consecutive_timeouts >= CONSECUTIVE_TIMEOUT_LIMIT:
                    print(f"\n    {consecutive_timeouts} consecutive timeouts — Docling Space likely crashed", flush=True)
                    if restart_docling_space():
                        consecutive_timeouts = 0
                        time.sleep(5)  # Extra time after restart
                    else:
                        print("    Could not restart. Continuing (may keep timing out)...", flush=True)
                        time.sleep(10)
            else:
                # Non-timeout error (HTTP 400/500) — Space is responsive, just rejected the doc
                consecutive_timeouts = 0

            if i < len(docs) - 1:
                time.sleep(DELAY_BETWEEN_DOCS)
            continue

        # Reset timeout counter on success
        consecutive_timeouts = 0

        if not chunks:
            err_msg = "No usable chunks extracted"
            print(f"  {prefix} {sector:10s} | 0 chunks | {elapsed:.1f}s | {fname}")
            tracker.add_result(doc, 0, 0, 0, time.time() - doc_start, error=err_msg)
            tracker.save()
            if i < len(docs) - 1:
                time.sleep(DELAY_BETWEEN_DOCS)
            continue

        # Step 2: Prepare Pinecone records
        records = []
        for ci, chunk_text in enumerate(chunks):
            rec_id = make_chunk_id(sector, url, ci)
            record = {
                "_id": rec_id,
                "text": chunk_text,
                "sector": sector,
                "source": f"docling-{fname}",
            }
            # Add title as metadata if available
            if title:
                record["title"] = title[:200]
            records.append(record)

        # Step 3: Upsert to Pinecone
        if dry_run:
            upserted = len(records)
            failed = 0
            print(f"  {prefix} {sector:10s} | {len(chunks):3d} chunks | {elapsed:.1f}s | {fname} [DRY RUN]")
        else:
            upserted, failed, errs = upsert_to_pinecone(records)
            total_elapsed = time.time() - doc_start
            status = "OK" if failed == 0 else f"{failed} FAIL"
            print(f"  {prefix} {sector:10s} | {upserted:3d} chunks | {total_elapsed:.1f}s | {fname}")
            if errs:
                for e in errs[:3]:
                    print(f"           upsert error: {e[:80]}")

        tracker.add_result(doc, len(chunks), upserted, failed, time.time() - doc_start)
        tracker.save()

        # After successful PDF conversion, proactively restart Docling Space
        # cpu-basic runs out of memory after processing 1 PDF, so restart preemptively
        if i < len(docs) - 1:
            print(f"    Proactive restart after successful conversion...", flush=True)
            restart_docling_space()
            time.sleep(DELAY_AFTER_SUCCESS)

    # Final summary
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    ok = tracker.processed_docs - tracker.total_docs_failed
    print(f"  Documents: {ok} OK / {tracker.total_docs_failed} failed / {tracker.total_docs} total")
    print(f"  Chunks:    {tracker.total_chunks_upserted} upserted / {tracker.total_chunks_failed} failed")
    print(f"  Time:      {time.time() - tracker.start_time:.1f}s total")
    print(f"  Progress:  {PROGRESS_FILE}")
    print(f"  Results:   {LOG_FILE}")
    print("=" * 70)

    return tracker


def show_report():
    """Display the latest progress report."""
    if not os.path.exists(LOG_FILE):
        print(f"No results file found at {LOG_FILE}")
        print("Run the ingestion first.")
        sys.exit(1)

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 70)
    print("  DOCLING INGEST — LATEST REPORT")
    print(f"  Generated: {data.get('generated_at', '?')}")
    print("=" * 70)

    summary = data.get("summary", {})
    print(f"\n  Status:     {summary.get('status', '?')}")
    print(f"  Processed:  {summary.get('processed', 0)} / {summary.get('total', 0)}")
    print(f"  Docs OK:    {summary.get('docs_ok', 0)}")
    print(f"  Docs fail:  {summary.get('docs_failed', 0)}")
    print(f"  Chunks up:  {summary.get('chunks_upserted', 0)}")
    print(f"  Chunks fail:{summary.get('chunks_failed', 0)}")
    print(f"  Elapsed:    {summary.get('elapsed_s', 0):.1f}s")

    docs = data.get("documents", [])
    if docs:
        print(f"\n  Per-document:")
        # Group by sector
        by_sector = {}
        for d in docs:
            s = d.get("sector", "unknown")
            if s not in by_sector:
                by_sector[s] = []
            by_sector[s].append(d)

        for sector in sorted(by_sector.keys()):
            print(f"\n    [{sector.upper()}]")
            for d in by_sector[sector]:
                fname = filename_from_url(d.get("url", ""))
                if d.get("status") == "ok":
                    print(f"      OK   {d.get('chunks_upserted', 0):3d} chunks  {d.get('elapsed_s', 0):5.1f}s  {fname}")
                else:
                    print(f"      FAIL                    {d.get('elapsed_s', 0):5.1f}s  {fname}")
                    if d.get("error"):
                        print(f"           {d['error'][:70]}")


# ── CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Docling PDF Ingest → E5 Pinecone Pipeline"
    )
    parser.add_argument("--sector", type=str,
                        help="Filter by sector (finance, btp, juridique, industrie)")
    parser.add_argument("--priority-only", action="store_true",
                        help="Only process high-priority documents")
    parser.add_argument("--max", type=int, default=0,
                        help="Maximum number of documents to process")
    parser.add_argument("--all", action="store_true",
                        help="Process all documents (PDFs + high priority)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Convert via Docling but don't upsert to Pinecone")
    parser.add_argument("--report", action="store_true",
                        help="Show latest ingestion results")
    parser.add_argument("--timeout", type=int, default=DEFAULT_DOCLING_TIMEOUT,
                        help=f"Timeout per document in seconds (default: {DEFAULT_DOCLING_TIMEOUT})")
    args = parser.parse_args()

    if args.report:
        show_report()
        return

    global DOCLING_TIMEOUT  # noqa
    DOCLING_TIMEOUT = args.timeout

    # Determine filters
    priority_only = args.priority_only
    if not args.all and not args.priority_only and not args.sector:
        # Default: priority only
        priority_only = True
        print("  NOTE: Defaulting to --priority-only. Use --all for everything.")

    docs = load_documents(
        sector_filter=args.sector,
        priority_only=priority_only,
        max_docs=args.max if args.max > 0 else None,
    )

    if not docs:
        print("  No documents match the filters.")
        print(f"  Tried: sector={args.sector}, priority_only={priority_only}, max={args.max}")
        sys.exit(1)

    print(f"\n  Loaded {len(docs)} documents to process")

    # Show what we're about to process
    sectors = {}
    for d in docs:
        s = d.get("sector", "unknown")
        sectors[s] = sectors.get(s, 0) + 1
    for s, c in sorted(sectors.items()):
        print(f"    {s}: {c} docs")

    tracker = process_documents(docs, dry_run=args.dry_run)

    # Exit code: 0 if any docs succeeded
    ok = tracker.processed_docs - tracker.total_docs_failed
    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
