#!/usr/bin/env python3
"""
local-pdf-ingest.py — Local PDF extraction fallback when Docling HF Space OOMs.

Downloads PDFs from sectors/real-documents-to-ingest.json, extracts text via
pdfplumber (with PyPDF2 fallback), chunks, and upserts to E5 Pinecone index.

Designed for 1 vCPU / 969 MB RAM VM — sequential processing, cleanup after each doc.

Usage:
    source .env.local
    python3 -u ops/local-pdf-ingest.py [--test] [--sector SECTOR] [--dry-run]
"""

import sys
import os
import json
import hashlib
import time
import argparse
import socket
import tempfile
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from datetime import datetime, timezone

# ─── Force IPv4 globally (HF / Pinecone DNS issues on IPv6) ───
_original_getaddrinfo = socket.getaddrinfo

def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _ipv4_only_getaddrinfo

# ─── Unbuffered stdout ───
sys.stdout.reconfigure(line_buffering=True)

# ─── Paths ───
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DOC_LIST = PROJECT_DIR / "sectors" / "real-documents-to-ingest.json"
PROGRESS_DIR = PROJECT_DIR / "data" / "ingest"
PROGRESS_FILE = PROGRESS_DIR / "pdf-progress.json"

# ─── E5 Pinecone config ───
E5_HOST = "sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
E5_UPSERT_URL = f"https://{E5_HOST}/records/namespaces/sectors/upsert"

# ─── Chunking config ───
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# ─── Max text per record (E5 integrated limit) ───
MAX_TEXT_FOR_E5 = 4000


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_progress() -> dict:
    """Load progress tracking file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"processed": {}, "stats": {"total_chunks": 0, "total_upserted": 0, "errors": []}}


def save_progress(progress: dict):
    """Save progress tracking file."""
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    progress["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def get_pdf_documents(sector_filter: str = None) -> list:
    """Load document list and filter to PDFs only."""
    with open(DOC_LIST) as f:
        data = json.load(f)

    docs = []
    for doc in data["documents"]:
        url = doc["url"].lower()
        if not url.endswith(".pdf"):
            continue
        if sector_filter and doc.get("sector") != sector_filter:
            continue
        docs.append(doc)

    return docs


def is_pdf_accessible(url: str, timeout: int = 15) -> bool:
    """Check if URL is actually a PDF via HEAD request."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (compatible; NomosRAG/1.0)")
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        content_type = resp.headers.get("Content-Type", "").lower()
        return "pdf" in content_type or url.lower().endswith(".pdf")
    except Exception as e:
        # Some servers block HEAD, try GET with range
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0 (compatible; NomosRAG/1.0)")
            req.add_header("Range", "bytes=0-4")
            ctx = ssl.create_default_context()
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            data = resp.read(5)
            return data[:4] == b"%PDF"
        except Exception:
            return False


def download_pdf(url: str, dest: str, timeout: int = 60) -> bool:
    """Download PDF to local path."""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (compatible; NomosRAG/1.0)")
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        log(f"  Downloaded: {size_mb:.1f} MB")
        return True
    except Exception as e:
        log(f"  Download FAILED: {e}")
        return False


def extract_text_pdfplumber(pdf_path: str) -> str:
    """Extract text using pdfplumber (better for tables)."""
    import pdfplumber
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            except Exception as e:
                log(f"  pdfplumber page {i} error: {e}")
    return "\n\n".join(text_parts)


def extract_text_pypdf2(pdf_path: str) -> str:
    """Extract text using PyPDF2 (fallback)."""
    from PyPDF2 import PdfReader
    reader = PdfReader(pdf_path)
    text_parts = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        except Exception as e:
            log(f"  PyPDF2 page {i} error: {e}")
    return "\n\n".join(text_parts)


def extract_text(pdf_path: str) -> str:
    """Extract text with pdfplumber, fallback to PyPDF2."""
    text = ""
    try:
        text = extract_text_pdfplumber(pdf_path)
        if text.strip():
            log(f"  Extracted via pdfplumber: {len(text)} chars")
            return text
    except Exception as e:
        log(f"  pdfplumber failed: {e}")

    try:
        text = extract_text_pypdf2(pdf_path)
        if text.strip():
            log(f"  Extracted via PyPDF2: {len(text)} chars")
            return text
    except Exception as e:
        log(f"  PyPDF2 also failed: {e}")

    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks."""
    if not text.strip():
        return []

    # Clean up whitespace
    text = " ".join(text.split())

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(". ")
            last_newline = chunk.rfind("\n")
            break_at = max(last_period, last_newline)
            if break_at > chunk_size * 0.5:
                chunk = text[start:start + break_at + 1]
                end = start + break_at + 1

        if chunk.strip():
            chunks.append(chunk.strip())

        start = end - overlap
        if start >= len(text):
            break

    return chunks


def make_record_id(sector: str, url_hash: str, idx: int) -> str:
    """Generate deterministic record ID."""
    return f"pdf-{sector}-{url_hash}-{idx:03d}"


def upsert_one_record(record_id: str, text: str, sector: str, source: str,
                      api_key: str) -> bool:
    """Upsert a single record to E5 Pinecone integrated embedding index."""
    if len(text) > MAX_TEXT_FOR_E5:
        text = text[:MAX_TEXT_FOR_E5]

    payload = json.dumps({
        "_id": record_id,
        "text": text,
        "sector": sector,
        "source": source,
    }).encode("utf-8")

    req = urllib.request.Request(
        E5_UPSERT_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Api-Key": api_key,
        },
        method="POST",
    )

    try:
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, timeout=30, context=ctx)
        status = resp.getcode()
        return status in (200, 201, 202)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200] if e.fp else ""
        log(f"    Upsert FAILED {record_id}: HTTP {e.code} — {body}")
        return False
    except Exception as e:
        log(f"    Upsert FAILED {record_id}: {e}")
        return False


def upsert_to_e5(records: list, api_key: str, dry_run: bool = False) -> bool:
    """Upsert all records to E5 Pinecone index, one at a time."""
    if dry_run:
        log(f"  [DRY-RUN] Would upsert {len(records)} records")
        return True

    success_count = 0
    for i, rec in enumerate(records):
        ok = upsert_one_record(rec["_id"], rec["text"], rec["sector"], rec["source"], api_key)
        if ok:
            success_count += 1
        else:
            log(f"    Failed on record {i+1}/{len(records)}")

        # Small pause every 10 records to avoid rate limits
        if (i + 1) % 10 == 0:
            time.sleep(0.3)

    # Consider success if at least 80% went through
    ratio = success_count / len(records) if records else 0
    if ratio < 0.8:
        log(f"  Only {success_count}/{len(records)} upserted ({ratio:.0%})")
        return False

    return True


def process_one_pdf(doc: dict, api_key: str, progress: dict, dry_run: bool = False) -> dict:
    """Process a single PDF document end-to-end."""
    url = doc["url"]
    sector = doc.get("sector", "unknown")
    title = doc.get("title", "Unknown")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    filename = url.split("/")[-1][:60]

    result = {
        "url": url,
        "sector": sector,
        "title": title,
        "status": "unknown",
        "chunks": 0,
        "upserted": 0,
        "chars": 0,
    }

    # Download to temp
    tmp_path = os.path.join(tempfile.gettempdir(), f"nomos-pdf-{url_hash}.pdf")

    try:
        if not download_pdf(url, tmp_path):
            result["status"] = "download_failed"
            return result

        # Extract text
        text = extract_text(tmp_path)
        if not text.strip():
            result["status"] = "no_text_extracted"
            return result

        result["chars"] = len(text)

        # Chunk
        chunks = chunk_text(text)
        result["chunks"] = len(chunks)
        log(f"  Chunks: {len(chunks)}")

        if not chunks:
            result["status"] = "no_chunks"
            return result

        # Build records
        records = []
        for idx, chunk_text_str in enumerate(chunks):
            record = {
                "_id": make_record_id(sector, url_hash, idx),
                "text": chunk_text_str,
                "sector": sector,
                "source": f"pdf-{filename}",
            }
            records.append(record)

        # Upsert
        if upsert_to_e5(records, api_key, dry_run=dry_run):
            result["upserted"] = len(records)
            result["status"] = "success"
            log(f"  Upserted {len(records)} records to E5")
        else:
            result["status"] = "upsert_failed"

        return result

    finally:
        # Always clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    parser = argparse.ArgumentParser(description="Local PDF ingest fallback for Docling OOM")
    parser.add_argument("--test", action="store_true", help="Process only the first PDF")
    parser.add_argument("--sector", type=str, help="Filter to specific sector")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual upsert")
    parser.add_argument("--check-only", action="store_true", help="Only check PDF accessibility")
    args = parser.parse_args()

    # Validate env
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key and not args.dry_run and not args.check_only:
        log("ERROR: PINECONE_API_KEY not set. Run: source .env.local")
        sys.exit(1)

    # Load documents
    pdfs = get_pdf_documents(sector_filter=args.sector)
    log(f"Found {len(pdfs)} PDF documents" + (f" (sector={args.sector})" if args.sector else ""))

    if args.test:
        pdfs = pdfs[:1]
        log("TEST MODE: processing only first PDF")

    # Check accessibility
    log("Checking PDF accessibility...")
    accessible = []
    for doc in pdfs:
        ok = is_pdf_accessible(doc["url"])
        status = "OK" if ok else "BLOCKED"
        log(f"  [{status}] {doc['title'][:50]}")
        if ok:
            accessible.append(doc)

    log(f"Accessible: {len(accessible)}/{len(pdfs)}")

    if args.check_only:
        return

    if not accessible:
        log("No accessible PDFs. Exiting.")
        return

    # Load progress
    progress = load_progress()

    # Filter already processed
    to_process = []
    for doc in accessible:
        url_hash = hashlib.md5(doc["url"].encode()).hexdigest()[:10]
        if url_hash in progress.get("processed", {}):
            prev = progress["processed"][url_hash]
            if prev.get("status") == "success":
                log(f"  SKIP (already done): {doc['title'][:50]}")
                continue
        to_process.append(doc)

    log(f"To process: {len(to_process)} PDFs")

    if not to_process:
        log("All PDFs already processed. Nothing to do.")
        return

    # Process sequentially
    total_chunks = 0
    total_upserted = 0
    successes = 0
    failures = 0

    for i, doc in enumerate(to_process):
        url_hash = hashlib.md5(doc["url"].encode()).hexdigest()[:10]
        log(f"\n[{i+1}/{len(to_process)}] {doc['title'][:60]}")
        log(f"  Sector: {doc['sector']} | URL: {doc['url'][:80]}...")

        result = process_one_pdf(doc, api_key, progress, dry_run=args.dry_run)

        total_chunks += result["chunks"]
        total_upserted += result["upserted"]

        if result["status"] == "success":
            successes += 1
        else:
            failures += 1
            progress["stats"]["errors"].append({
                "url": doc["url"][:100],
                "error": result["status"],
                "time": datetime.now(timezone.utc).isoformat(),
            })

        # Update progress
        progress["processed"][url_hash] = {
            "url": doc["url"],
            "sector": doc["sector"],
            "title": doc["title"][:80],
            "status": result["status"],
            "chunks": result["chunks"],
            "upserted": result["upserted"],
            "chars": result["chars"],
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        progress["stats"]["total_chunks"] = sum(
            p.get("chunks", 0) for p in progress["processed"].values()
        )
        progress["stats"]["total_upserted"] = sum(
            p.get("upserted", 0) for p in progress["processed"].values()
        )

        # Save progress every 5 docs (or on last)
        if (i + 1) % 5 == 0 or i == len(to_process) - 1:
            save_progress(progress)
            log(f"  Progress saved ({i+1}/{len(to_process)})")

        # Brief pause between docs
        if i < len(to_process) - 1:
            time.sleep(1)

    # Final summary
    log(f"\n{'='*60}")
    log(f"SUMMARY")
    log(f"  Processed: {successes + failures}")
    log(f"  Success:   {successes}")
    log(f"  Failed:    {failures}")
    log(f"  Chunks:    {total_chunks}")
    log(f"  Upserted:  {total_upserted}")
    log(f"  Progress:  {PROGRESS_FILE}")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
