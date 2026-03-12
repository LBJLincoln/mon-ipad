#!/usr/bin/env python3
"""
Docling S6 Ingest — CPU-basic-safe PDF ingestion via HF Space S6
=================================================================
Processes PDFs through the Docling API on HF Space S6 (CPU-basic, 2 vCPU,
16GB RAM) with conservative limits to avoid OOM, then upserts chunks to
Pinecone E5 (integrated inference) and Supabase sector_documents.

Key constraints for CPU-basic:
  - MAX 10MB per PDF (not 50MB — OOM risk on large files)
  - MAX 30 pages estimated (from Content-Length heuristic)
  - Sequential processing (1 job at a time)
  - 300s timeout per PDF (CPU-basic is slow)
  - 10s cooldown between PDFs (memory recovery)

Usage:
  source .env.local
  python3 ops/docling-s6-ingest.py --from-discovered --sector finance --max 5
  python3 ops/docling-s6-ingest.py --url "https://example.com/doc.pdf" --sector btp
  python3 ops/docling-s6-ingest.py --urls urls.txt --sector juridique
  python3 ops/docling-s6-ingest.py --from-discovered --sector all --max 20 --dry-run

Env vars required:
  PINECONE_API_KEY, SUPABASE_URL, SUPABASE_API_KEY  (via .env.local)
"""

# ── Force IPv4 globally (IPv6 broken on this VM) ─────────────────────────
import socket
from socket import AF_INET

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, AF_INET, type_, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

# ── Standard imports ─────────────────────────────────────────────────────
import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Force line-buffered output for nohup/background ─────────────────────
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── SSL context (permissive for government PDFs with outdated certs) ────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# =========================================================================
# CONFIGURATION
# =========================================================================

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
DISCOVERED_PATH = REPO_ROOT / "data" / "eval" / "expert-discovery" / "discovered-documents.json"
PROCESSED_PATH = REPO_ROOT / "data" / "ingest" / "docling-s6-processed.json"
LOG_DIR = REPO_ROOT / "data" / "ingest"

# Docling S6
DOCLING_BASE = "https://lbjlincoln-nomos-docling-api.hf.space"
DOCLING_CONVERT_URL = f"{DOCLING_BASE}/convert-url"
DOCLING_HEALTH_URL = f"{DOCLING_BASE}/health"
DOCLING_TIMEOUT = 600  # seconds — CPU-basic is VERY slow (15-page PDF ~5min)

# Pinecone E5 integrated inference
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
PINECONE_UPSERT_URL = f"{PINECONE_HOST}/records/namespaces/sectors/upsert"
PINECONE_TIMEOUT = 20

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY", "")

# HF Token (for Space restart)
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Size limits — conservative for CPU-basic
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_ESTIMATED_PAGES = 20  # ~50KB per page heuristic (CPU-basic OOMs on large docs)
BYTES_PER_PAGE_ESTIMATE = 50_000

# Chunking — 500 tokens ~ 2000 chars (4 chars/token)
CHUNK_SIZE_CHARS = 2000
CHUNK_OVERLAP_CHARS = 200  # ~50 tokens
MIN_CHUNK_LEN = 80
MAX_TEXT_FOR_E5 = 1500  # Pinecone E5 max useful text length

# Timing
DELAY_BETWEEN_DOCS = 10  # seconds between PDFs (memory recovery for CPU-basic)
PINECONE_DELAY = 0.05  # seconds between upserts
CONSECUTIVE_TIMEOUT_LIMIT = 3  # restart Space after N consecutive timeouts

SECTORS = ["finance", "btp", "juridique", "industrie"]


# =========================================================================
# LOGGING
# =========================================================================

def log(msg, level="INFO"):
    """Print with timestamp prefix."""
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix = {"INFO": "+", "WARN": "!", "ERROR": "X", "OK": "v", "SKIP": "-"}.get(level, " ")
    print(f"[{ts}] [{prefix}] {msg}", flush=True)


# =========================================================================
# UTILITIES
# =========================================================================

def url_hash(url):
    """12-char hash of a URL for deterministic IDs."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def short_hash(text):
    """8-char hash for dedup."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def make_chunk_id(sector, url, chunk_idx):
    """Deterministic chunk ID: docling-{sector}-{hash}-{idx:03d}"""
    return f"docling-{sector}-{url_hash(url)}-{chunk_idx:03d}"


def filename_from_url(url):
    """Extract short display name from URL."""
    path = url.split("?")[0].split("#")[0]
    name = path.rstrip("/").split("/")[-1]
    if len(name) > 55:
        name = name[:52] + "..."
    return name or "unknown"


def clean_text(text):
    """Clean raw PDF text for chunking."""
    if not text:
        return ""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n\s*Page \d+ (?:of|sur|/) \d+\s*\n', '\n', text)
    text = re.sub(r'(?:\xa9|Copyright).*?\d{4}.*?\n', '', text, flags=re.IGNORECASE)
    return text.strip()


def chunk_text(text, chunk_size=CHUNK_SIZE_CHARS, overlap=CHUNK_OVERLAP_CHARS):
    """Split text into overlapping chunks, preferring sentence/paragraph breaks."""
    if not text or len(text) < MIN_CHUNK_LEN:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size

        if end >= text_len:
            chunk = text[start:].strip()
            if len(chunk) >= MIN_CHUNK_LEN:
                chunks.append(chunk)
            break

        # Try paragraph boundary
        candidate = text[start:end]
        para_break = candidate.rfind('\n\n')
        if para_break > chunk_size * 0.4:
            end = start + para_break + 2
        else:
            # Try sentence boundary (French + English punctuation)
            for sep in ['. ', '.\n', '? ', '!\n', ';\n', ' ; ']:
                sent_break = candidate.rfind(sep)
                if sent_break > chunk_size * 0.4:
                    end = start + sent_break + len(sep)
                    break

        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_LEN:
            chunks.append(chunk)

        # Advance with overlap
        start = end - overlap
        if start <= (end - chunk_size):
            start = end

    return chunks


def http_request(url, data=None, headers=None, method="GET", timeout=30):
    """
    Perform an HTTP request using urllib. Returns (status_code, response_body_bytes, error_string).
    On success error_string is None. On failure status_code may be 0.
    """
    if headers is None:
        headers = {}
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)
        body = resp.read()
        return resp.status, body, None
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        return e.code, body, f"HTTP {e.code}"
    except Exception as e:
        return 0, b"", f"{type(e).__name__}: {str(e)[:200]}"


# =========================================================================
# PROCESSED URLs TRACKER
# =========================================================================

def load_processed():
    """Load set of already-processed URLs from JSON file."""
    if PROCESSED_PATH.exists():
        try:
            data = json.loads(PROCESSED_PATH.read_text("utf-8"))
            return data
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "urls": {},
        "stats": {
            "total_processed": 0,
            "total_chunks": 0,
            "created": datetime.now(timezone.utc).isoformat(),
        },
    }


def save_processed(data):
    """Atomically save processed URLs tracker."""
    data["stats"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    data["stats"]["total_processed"] = len(data.get("urls", {}))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(PROCESSED_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, str(PROCESSED_PATH))


def is_already_processed(data, url):
    """Check if URL has been processed before."""
    return url in data.get("urls", {})


def mark_as_processed(data, url, info):
    """Mark URL as processed with metadata."""
    data["urls"][url] = info
    data["stats"]["total_chunks"] = sum(
        v.get("chunks", 0) for v in data["urls"].values() if isinstance(v, dict)
    )


# =========================================================================
# INPUT LOADING
# =========================================================================

def load_from_discovered(sector_filter=None, max_docs=None, processed_data=None):
    """
    Load PDF URLs from data/eval/expert-discovery/discovered-documents.json.
    Returns list of dicts: [{url, title, sector}, ...]
    """
    if not DISCOVERED_PATH.exists():
        log(f"Discovered documents file not found: {DISCOVERED_PATH}", "ERROR")
        return []

    with open(DISCOVERED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = []
    sectors_data = data.get("sectors", {})

    for sector, items in sectors_data.items():
        if sector_filter and sector_filter != "all" and sector != sector_filter:
            continue
        for item in items:
            url = item.get("url", "")
            if not url:
                continue
            # Only accept PDF URLs
            url_lower = url.lower().split("?")[0].split("#")[0]
            is_pdf = (
                url_lower.endswith(".pdf")
                or "/pdf/" in url_lower
                or "filetype=pdf" in url.lower()
            )
            if not is_pdf:
                continue
            # Skip already processed
            if processed_data and is_already_processed(processed_data, url):
                continue
            docs.append({
                "url": url,
                "title": item.get("title", filename_from_url(url)),
                "sector": sector,
            })

    # Deduplicate by URL
    seen = set()
    unique = []
    for d in docs:
        if d["url"] not in seen:
            seen.add(d["url"])
            unique.append(d)
    docs = unique

    if max_docs and max_docs > 0:
        docs = docs[:max_docs]

    return docs


def load_from_urls_file(filepath, sector):
    """Load URLs from a text file (one per line). Returns list of dicts."""
    docs = []
    path = Path(filepath)
    if not path.exists():
        log(f"URLs file not found: {filepath}", "ERROR")
        return []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            docs.append({
                "url": url,
                "title": filename_from_url(url),
                "sector": sector,
            })
    return docs


def load_single_url(url, sector):
    """Wrap a single URL into the expected format."""
    return [{
        "url": url,
        "title": filename_from_url(url),
        "sector": sector,
    }]


# =========================================================================
# DOCLING S6 API
# =========================================================================

def docling_health():
    """Check Docling S6 /health endpoint. Returns (is_healthy, info_dict)."""
    status, body, err = http_request(DOCLING_HEALTH_URL, timeout=20)
    if err:
        return False, {"error": err}
    try:
        info = json.loads(body.decode("utf-8"))
        return True, info
    except Exception:
        return status == 200, {}


def restart_docling_space():
    """Restart HF Space S6 and wait for it to come back (up to 5 min)."""
    if not HF_TOKEN:
        log("No HF_TOKEN — cannot restart Space automatically", "WARN")
        return False

    log("Restarting Docling HF Space S6...", "INFO")
    restart_url = "https://huggingface.co/api/spaces/LBJLincoln/nomos-docling-api/restart"
    status, _, err = http_request(
        restart_url,
        headers={"Authorization": f"Bearer {HF_TOKEN}"},
        method="POST",
        timeout=30,
    )
    if err and status not in (200, 202):
        log(f"Restart failed: {err}", "ERROR")
        return False

    # Wait for Space to come back
    log("Waiting for Space to restart...", "INFO")
    for i in range(30):
        time.sleep(10)
        healthy, info = docling_health()
        if healthy:
            converter_loaded = info.get("converter_loaded", False)
            if converter_loaded:
                log(f"Space UP + converter ready after {(i + 1) * 10}s", "OK")
                return True
            elif i > 10:
                log(f"Health OK but converter not loaded at {(i + 1) * 10}s, proceeding", "WARN")
                return True

    log("Space did not respond within 300s", "ERROR")
    return False


def check_file_size(url):
    """
    HEAD request to get Content-Length.
    Returns (size_bytes, error_string). size_bytes=0 if unknown.
    """
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (compatible; Nomos-Docling/2.0)")
        req.add_header("Accept", "application/pdf,*/*")
        resp = urllib.request.urlopen(req, timeout=15, context=_ssl_ctx)
        cl = resp.headers.get("Content-Length")
        if cl:
            return int(cl), None
        return 0, None
    except Exception as e:
        # HEAD failed — not fatal, we can still try the conversion
        return 0, f"HEAD failed: {type(e).__name__}: {str(e)[:100]}"


def docling_convert(doc_url, timeout=None):
    """
    Send URL to Docling S6 /convert-url endpoint.
    Returns (full_text, chunks_list, meta_dict, elapsed_s, error_string).
    """
    if timeout is None:
        timeout = DOCLING_TIMEOUT
    payload = json.dumps({"url": doc_url}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    start = time.time()
    status, body, err = http_request(
        DOCLING_CONVERT_URL,
        data=payload,
        headers=headers,
        method="POST",
        timeout=timeout,
    )
    elapsed = time.time() - start

    if err:
        return None, [], {}, elapsed, err

    try:
        data = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, [], {}, elapsed, f"JSON parse error: {e}"

    # Check for Docling-level error
    doc_status = data.get("status", "")
    if doc_status == "error":
        return None, [], {}, elapsed, f"Docling error: {data.get('error', 'unknown')}"

    # Extract text — Docling returns full_text
    full_text = data.get("full_text", "") or data.get("markdown", "") or data.get("text", "")

    # Extract pre-made chunks if available
    raw_chunks = data.get("chunks", [])
    chunks = []
    for c in raw_chunks:
        if isinstance(c, str):
            t = c.strip()
        elif isinstance(c, dict):
            t = (c.get("text", "") or c.get("content", "")).strip()
        else:
            continue
        if len(t) >= MIN_CHUNK_LEN:
            chunks.append(t[:MAX_TEXT_FOR_E5])

    # If no pre-made chunks, chunk the full text ourselves
    if not chunks and full_text:
        cleaned = clean_text(full_text)
        chunks = chunk_text(cleaned)
        # Cap each chunk for E5
        chunks = [c[:MAX_TEXT_FOR_E5] for c in chunks]

    meta = {
        "num_pages": data.get("num_pages", 0),
        "num_tables": data.get("num_tables", 0),
        "full_text_chars": len(full_text),
        "chunks_from_api": len(raw_chunks),
        "usable_chunks": len(chunks),
        "processing_time_s": round(elapsed, 2),
    }

    return full_text, chunks, meta, elapsed, None


# =========================================================================
# PINECONE E5 UPSERT (integrated inference — text only)
# =========================================================================

def pinecone_upsert_single(record, retries=3):
    """
    Upsert a single record to Pinecone E5 integrated-embedding index.
    Record format: {"_id": ..., "chunk_text": ..., "sector": ..., ...}
    Returns True on success.
    """
    if not PINECONE_API_KEY:
        return False

    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
    }
    payload = json.dumps(record).encode("utf-8")

    for attempt in range(retries):
        status, body, err = http_request(
            PINECONE_UPSERT_URL,
            data=payload,
            headers=headers,
            method="POST",
            timeout=PINECONE_TIMEOUT,
        )

        if status in (200, 201):
            return True
        if status == 409:
            return True  # Already exists
        if status == 429:
            wait = min(2 ** attempt + 0.5, 5)
            time.sleep(wait)
            continue
        if err and attempt < retries - 1:
            time.sleep(0.5 * (attempt + 1))
            continue
        # Final attempt failed
        return False

    return False


# =========================================================================
# SUPABASE UPSERT
# =========================================================================

def supabase_upsert(doc_id, sector, chunk_text_content, source_url, title):
    """
    Upsert a document/chunk to Supabase sector_documents table.
    Uses Prefer: resolution=merge-duplicates for idempotent upserts.
    Returns True on success.
    """
    if not SUPABASE_URL or not SUPABASE_API_KEY:
        return False

    insert_url = f"{SUPABASE_URL}/rest/v1/sector_documents"

    row = {
        "id": doc_id,
        "sector": sector,
        "dataset_name": "docling-pdf",
        "pipeline": "docling-s6",
        "context": chunk_text_content[:10000],
        "question": (title or "Untitled")[:500],
        "answer": "",
        "metadata": json.dumps({"source_url": source_url[:2000], "source_type": "expert_pdf_docling"}),
        "tenant_id": "default",
    }

    payload = json.dumps(row, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Prefer": "resolution=merge-duplicates",
    }

    status, body, err = http_request(
        insert_url,
        data=payload,
        headers=headers,
        method="POST",
        timeout=20,
    )

    if status in (200, 201, 204):
        return True
    if status == 409:
        return True  # Duplicate — fine

    if err:
        body_str = ""
        try:
            body_str = body.decode("utf-8")[:200]
        except Exception:
            pass
        log(f"Supabase upsert {doc_id}: {err} {body_str}", "WARN")
    return False


# =========================================================================
# MAIN PROCESSING
# =========================================================================

def process_single_pdf(doc, processed_data, dry_run=False):
    """
    Full pipeline for one PDF:
      1. HEAD check size
      2. Docling S6 /convert-url
      3. Chunk text
      4. Upsert chunks to Pinecone E5
      5. Upsert representative doc to Supabase
      6. Track as processed

    Returns stats dict.
    """
    url = doc["url"]
    sector = doc["sector"]
    title = doc.get("title", filename_from_url(url))
    fname = filename_from_url(url)

    stats = {
        "url": url,
        "sector": sector,
        "title": title[:80],
        "status": "started",
        "file_size_bytes": 0,
        "num_chunks": 0,
        "pinecone_ok": 0,
        "pinecone_fail": 0,
        "supabase_ok": 0,
        "elapsed_s": 0,
        "error": None,
    }
    t0 = time.time()

    # ── Step 1: HEAD check file size ─────────────────────────────────
    file_size, head_err = check_file_size(url)

    if file_size > 0:
        size_mb = file_size / (1024 * 1024)
        stats["file_size_bytes"] = file_size

        if file_size > MAX_FILE_SIZE_BYTES:
            stats["status"] = "skipped_too_large"
            stats["error"] = f"File too large: {size_mb:.1f}MB > {MAX_FILE_SIZE_MB}MB limit"
            stats["elapsed_s"] = round(time.time() - t0, 1)
            log(f"SKIP (too large: {size_mb:.1f}MB) | {fname}", "SKIP")
            return stats

        # Estimate pages
        est_pages = file_size // BYTES_PER_PAGE_ESTIMATE
        if est_pages > MAX_ESTIMATED_PAGES:
            stats["status"] = "skipped_too_many_pages"
            stats["error"] = f"Estimated ~{est_pages} pages > {MAX_ESTIMATED_PAGES} limit ({size_mb:.1f}MB)"
            stats["elapsed_s"] = round(time.time() - t0, 1)
            log(f"SKIP (~{est_pages} pages, {size_mb:.1f}MB) | {fname}", "SKIP")
            return stats

        log(f"Size: {size_mb:.1f}MB (~{max(est_pages, 1)} pages) | {fname}", "INFO")
    else:
        if head_err:
            log(f"HEAD: {head_err} — proceeding anyway | {fname}", "WARN")
        else:
            log(f"Size unknown (no Content-Length) — proceeding | {fname}", "WARN")

    if dry_run:
        stats["status"] = "dry_run"
        stats["elapsed_s"] = round(time.time() - t0, 1)
        log(f"DRY RUN — would process | {fname}", "SKIP")
        return stats

    # ── Step 2: Docling S6 convert ───────────────────────────────────
    log(f"Converting via Docling S6...", "INFO")
    full_text, chunks, meta, docling_elapsed, docling_err = docling_convert(url)

    if docling_err:
        stats["status"] = "docling_error"
        stats["error"] = docling_err
        stats["elapsed_s"] = round(time.time() - t0, 1)
        log(f"FAIL ({docling_elapsed:.1f}s) {docling_err[:100]} | {fname}", "ERROR")
        return stats

    if not chunks:
        stats["status"] = "no_chunks"
        stats["error"] = f"No usable chunks (full_text: {len(full_text or '')} chars)"
        stats["elapsed_s"] = round(time.time() - t0, 1)
        log(f"FAIL (0 chunks from {len(full_text or '')} chars) | {fname}", "ERROR")
        return stats

    stats["num_chunks"] = len(chunks)
    log(f"Extracted {len(chunks)} chunks in {docling_elapsed:.1f}s "
        f"(text: {meta.get('full_text_chars', 0):,} chars, "
        f"pages: {meta.get('num_pages', '?')}, "
        f"tables: {meta.get('num_tables', '?')})", "OK")

    # ── Step 3: Upsert chunks to Pinecone E5 ────────────────────────
    log(f"Upserting {len(chunks)} chunks to Pinecone E5...", "INFO")
    pc_ok = 0
    pc_fail = 0

    for ci, chunk in enumerate(chunks):
        chunk_id = make_chunk_id(sector, url, ci)
        record = {
            "_id": chunk_id,
            "text": chunk,
            "sector": sector,
            "source": "docling-pdf",
            "title": title[:200] if title else "",
        }

        if pinecone_upsert_single(record):
            pc_ok += 1
        else:
            pc_fail += 1

        time.sleep(PINECONE_DELAY)

        # Progress every 50 chunks
        if (ci + 1) % 50 == 0:
            log(f"  Pinecone progress: {ci + 1}/{len(chunks)}", "INFO")

    stats["pinecone_ok"] = pc_ok
    stats["pinecone_fail"] = pc_fail
    log(f"Pinecone: {pc_ok} OK, {pc_fail} failed out of {len(chunks)}", "OK" if pc_fail == 0 else "WARN")

    # ── Step 4: Upsert representative doc to Supabase ────────────────
    # Insert first chunk as representative document
    first_chunk_id = make_chunk_id(sector, url, 0)
    representative_text = (clean_text(full_text) or "")[:10000]
    sb_ok = supabase_upsert(first_chunk_id, sector, representative_text, url, title)
    if sb_ok:
        stats["supabase_ok"] = 1
        log("Supabase: 1 document upserted", "OK")
    else:
        log("Supabase: upsert failed (non-critical)", "WARN")

    # ── Step 5: Mark as processed ────────────────────────────────────
    mark_as_processed(processed_data, url, {
        "sector": sector,
        "title": title[:200],
        "chunks": len(chunks),
        "pinecone_ok": pc_ok,
        "supabase_ok": 1 if sb_ok else 0,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })
    save_processed(processed_data)

    stats["status"] = "ok"
    stats["elapsed_s"] = round(time.time() - t0, 1)
    return stats


def run(docs, dry_run=False):
    """
    Process a list of documents sequentially through the full pipeline.
    Returns summary dict.
    """
    processed_data = load_processed()
    existing = len(processed_data.get("urls", {}))

    # Filter out already-processed URLs
    before_filter = len(docs)
    docs = [d for d in docs if not is_already_processed(processed_data, d["url"])]
    if before_filter > len(docs):
        log(f"Filtered {before_filter - len(docs)} already-processed URLs", "SKIP")

    if not docs:
        log("No documents to process (all already done or empty input).", "OK")
        return {"processed": 0, "ok": 0, "skipped": 0, "failed": 0, "chunks_total": 0}

    # Count by sector
    sector_counts = {}
    for d in docs:
        s = d["sector"]
        sector_counts[s] = sector_counts.get(s, 0) + 1

    # Banner
    print("=" * 70, flush=True)
    print("  DOCLING S6 INGEST — CPU-basic safe", flush=True)
    print(f"  Docling:     {DOCLING_BASE}", flush=True)
    print(f"  Pinecone:    sectors-e5-multilingual / sectors", flush=True)
    print(f"  Documents:   {len(docs)}", flush=True)
    for s, c in sorted(sector_counts.items()):
        print(f"    {s}: {c}", flush=True)
    print(f"  Max size:    {MAX_FILE_SIZE_MB}MB / ~{MAX_ESTIMATED_PAGES} pages", flush=True)
    print(f"  Chunk:       {CHUNK_SIZE_CHARS} chars, {CHUNK_OVERLAP_CHARS} overlap", flush=True)
    print(f"  Timeout:     {DOCLING_TIMEOUT}s per PDF", flush=True)
    print(f"  Already done:{existing}", flush=True)
    print(f"  Mode:        {'DRY RUN' if dry_run else 'LIVE'}", flush=True)
    print("=" * 70, flush=True)
    print("", flush=True)

    # Health check
    log("Docling S6 health check...", "INFO")
    healthy, info = docling_health()
    if healthy:
        converter = info.get("converter_loaded", "?")
        log(f"Docling S6: UP (converter_loaded={converter})", "OK")
    else:
        log(f"Docling S6: not responding — will try anyway (Space may wake on request)", "WARN")

    if not PINECONE_API_KEY and not dry_run:
        log("FATAL: PINECONE_API_KEY not set. Run: source .env.local", "ERROR")
        sys.exit(1)

    # Process
    summary = {"processed": 0, "ok": 0, "skipped": 0, "failed": 0, "chunks_total": 0}
    consecutive_timeouts = 0

    for i, doc in enumerate(docs):
        prefix = f"[{i + 1}/{len(docs)}]"
        log(f"{prefix} Processing: {doc['url'][:80]}", "INFO")

        stats = process_single_pdf(doc, processed_data, dry_run=dry_run)
        summary["processed"] += 1

        status = stats["status"]
        if status == "ok":
            summary["ok"] += 1
            summary["chunks_total"] += stats["num_chunks"]
            consecutive_timeouts = 0
            result_line = f"OK ({stats['num_chunks']} chunks, {stats['pinecone_ok']} to Pinecone)"
        elif status == "dry_run":
            summary["ok"] += 1
            consecutive_timeouts = 0
            result_line = "DRY RUN"
        elif status.startswith("skipped"):
            summary["skipped"] += 1
            consecutive_timeouts = 0
            result_line = f"SKIP ({stats.get('error', status)})"
        else:
            summary["failed"] += 1
            result_line = f"FAIL ({stats.get('error', status)[:80]})"

            # Track consecutive timeouts
            err_str = (stats.get("error") or "").lower()
            is_timeout = "timeout" in err_str or "timed out" in err_str
            if is_timeout:
                consecutive_timeouts += 1
                if consecutive_timeouts >= CONSECUTIVE_TIMEOUT_LIMIT:
                    log(f"{consecutive_timeouts} consecutive timeouts — restarting Space", "WARN")
                    if restart_docling_space():
                        consecutive_timeouts = 0
                        time.sleep(5)
                    else:
                        log("Could not restart Space — continuing anyway", "WARN")
            else:
                consecutive_timeouts = 0

        log(f"{prefix} Result: {result_line} ({stats['elapsed_s']}s)", "INFO")

        # Cooldown between PDFs (CPU-basic memory recovery)
        if i < len(docs) - 1 and status == "ok":
            log(f"Cooldown {DELAY_BETWEEN_DOCS}s (CPU-basic memory recovery)...", "INFO")
            time.sleep(DELAY_BETWEEN_DOCS)
        elif i < len(docs) - 1:
            time.sleep(3)

    # Final summary
    print("", flush=True)
    print("=" * 70, flush=True)
    print("  SUMMARY", flush=True)
    print("=" * 70, flush=True)
    print(f"  PDFs processed:   {summary['ok']} OK", flush=True)
    print(f"  PDFs skipped:     {summary['skipped']}", flush=True)
    print(f"  PDFs failed:      {summary['failed']}", flush=True)
    print(f"  Chunks ingested:  {summary['chunks_total']}", flush=True)
    print(f"  URLs now tracked: {len(processed_data.get('urls', {}))}", flush=True)
    print(f"  Finished:         {datetime.now(timezone.utc).isoformat()}", flush=True)
    print("=" * 70, flush=True)

    return summary


# =========================================================================
# CLI
# =========================================================================

def main():
    global DOCLING_TIMEOUT  # noqa: PLW0603

    parser = argparse.ArgumentParser(
        description="Docling S6 Ingest — CPU-basic-safe PDF ingestion via HF Space S6"
    )

    # Input modes (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--from-discovered",
        action="store_true",
        help="Read URLs from data/eval/expert-discovery/discovered-documents.json",
    )
    input_group.add_argument(
        "--urls",
        type=str,
        metavar="FILE",
        help="Read URLs from a text file (one per line)",
    )
    input_group.add_argument(
        "--url",
        type=str,
        metavar="URL",
        help="Process a single URL",
    )

    # Options
    parser.add_argument(
        "--sector",
        type=str,
        choices=SECTORS + ["all"],
        default="all",
        help="Sector filter (default: all). Required for --url and --urls modes.",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Maximum number of PDFs to process (0 = unlimited)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check sizes and discover docs but do not convert/ingest",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DOCLING_TIMEOUT,
        help=f"Timeout per PDF in seconds (default: {DOCLING_TIMEOUT})",
    )

    args = parser.parse_args()

    # Validate sector is provided for --url and --urls modes
    if (args.url or args.urls) and args.sector == "all":
        parser.error("--sector is required when using --url or --urls (cannot be 'all')")

    # Override timeout if specified
    DOCLING_TIMEOUT = args.timeout

    # Load processed tracker
    processed_data = load_processed()

    # Load documents based on input mode
    if args.from_discovered:
        docs = load_from_discovered(
            sector_filter=args.sector,
            max_docs=args.max if args.max > 0 else None,
            processed_data=processed_data,
        )
    elif args.urls:
        docs = load_from_urls_file(args.urls, args.sector)
        if args.max > 0:
            docs = docs[:args.max]
    elif args.url:
        docs = load_single_url(args.url, args.sector)
    else:
        docs = []

    if not docs:
        log("No documents to process.", "WARN")
        log("Check: --from-discovered needs discovered-documents.json with PDF URLs", "INFO")
        sys.exit(1)

    log(f"Loaded {len(docs)} document(s) to process", "INFO")

    summary = run(docs, dry_run=args.dry_run)

    # Exit code
    if summary["ok"] > 0 or summary["processed"] == 0:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
