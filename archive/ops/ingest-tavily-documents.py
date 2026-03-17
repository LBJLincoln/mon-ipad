#!/usr/bin/env python3
"""
Ingest 158 real French sector documents via Exa.AI -> Pinecone E5.

Flow:
1. Read document list from sectors/real-documents-to-ingest.json
2. Fetch full content via Exa.AI search API (sequential, 45s hard timeout)
3. Chunk content (max 1500 chars, paragraph boundaries, cap 100K chars/doc)
4. Upsert chunks to Pinecone E5 integrated embedding (sequential)
5. Track and report stats
"""

import json
import os
import sys
import time
import ssl
import re
import signal
import urllib.request
import urllib.error
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
PINECONE_UPSERT_URL = f"{PINECONE_HOST}/records/namespaces/sectors/upsert"
EXA_SEARCH_URL = "https://api.exa.ai/search"

DOC_LIST_PATH = "/home/termius/mon-ipad/sectors/real-documents-to-ingest.json"

CHUNK_MAX = 1500
CHUNK_MIN = 50
CONTENT_CAP = 100_000  # Cap content at 100K chars (avoids 1000+ chunk docs)
UPSERT_DELAY = 0.25  # seconds between upserts
FETCH_TIMEOUT = 45  # hard timeout per Exa.AI call

# SSL context that skips verification
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
stats = {
    "docs_total": 0,
    "docs_fetched": 0,
    "docs_snippet_fallback": 0,
    "docs_failed": 0,
    "chunks_created": 0,
    "chunks_upserted": 0,
    "upsert_errors": 0,
    "by_sector": {},
}


def inc_stat(key, n=1):
    stats[key] = stats.get(key, 0) + n


def inc_sector_stat(sector, key, n=1):
    if sector not in stats["by_sector"]:
        stats["by_sector"][sector] = {"fetched": 0, "chunks": 0, "upserted": 0, "errors": 0}
    stats["by_sector"][sector][key] = stats["by_sector"][sector].get(key, 0) + n


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Timeout handler
# ---------------------------------------------------------------------------
class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


# ---------------------------------------------------------------------------
# Exa.AI Fetch
# ---------------------------------------------------------------------------
def exa_fetch(url: str) -> str | None:
    """Fetch full content of a URL via Exa.AI search API. Returns text or None."""
    payload = json.dumps({
        "query": url,
        "numResults": 1,
        "type": "auto",
        "contents": {"text": True},
    }).encode()
    req = urllib.request.Request(
        EXA_SEARCH_URL,
        data=payload,
        headers={"Content-Type": "application/json", "x-api-key": EXA_API_KEY},
        method="POST",
    )

    # Set hard timeout via signal alarm
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(FETCH_TIMEOUT)
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
            raw = resp.read().decode()
        signal.alarm(0)  # Cancel alarm

        data = json.loads(raw)
        results = data.get("results", [])
        if results and results[0].get("text"):
            content = results[0]["text"].strip()
            if len(content) >= CHUNK_MIN:
                # Cap content to avoid monster documents
                if len(content) > CONTENT_CAP:
                    content = content[:CONTENT_CAP]
                return content
        return None
    except TimeoutError:
        signal.alarm(0)
        return None
    except Exception:
        signal.alarm(0)
        return None
    finally:
        signal.signal(signal.SIGALRM, old_handler)
        signal.alarm(0)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def chunk_text(text: str, max_size: int = CHUNK_MAX, min_size: int = CHUNK_MIN) -> list[str]:
    """Split text into chunks on paragraph boundaries, respecting max/min sizes."""
    text = text.strip()
    if not text:
        return []

    # Split on double newlines (paragraphs)
    paragraphs = re.split(r'\n\s*\n', text)
    # If no paragraph breaks, split on single newlines
    if len(paragraphs) <= 1:
        paragraphs = text.split('\n')
    # If still one big block, split on sentence boundaries
    if len(paragraphs) <= 1 and len(text) > max_size:
        paragraphs = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 <= max_size:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if len(current) >= min_size:
                chunks.append(current)
            elif current:
                para = current + "\n\n" + para
            current = ""

            if len(para) > max_size:
                while len(para) > max_size:
                    split_at = max_size
                    for delim in ['. ', '! ', '? ', '; ', ', ', ' ']:
                        pos = para.rfind(delim, 0, max_size)
                        if pos > min_size:
                            split_at = pos + len(delim)
                            break
                    chunk_part = para[:split_at].strip()
                    if len(chunk_part) >= min_size:
                        chunks.append(chunk_part)
                    para = para[split_at:].strip()
                current = para
            else:
                current = para

    if current and len(current) >= min_size:
        chunks.append(current)
    elif current and chunks:
        chunks[-1] = chunks[-1] + "\n\n" + current

    return chunks


# ---------------------------------------------------------------------------
# Pinecone Upsert
# ---------------------------------------------------------------------------
def pinecone_upsert(record_id: str, text: str, sector: str, source: str, title: str) -> bool:
    """Upsert a single record to Pinecone E5 integrated embedding index."""
    payload = json.dumps({
        "_id": record_id,
        "text": text,
        "sector": sector,
        "source": source,
        "title": title,
    }).encode()

    req = urllib.request.Request(
        PINECONE_UPSERT_URL,
        data=payload,
        headers={
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
            status = resp.getcode()
            return status in (200, 201)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except:
            pass
        log(f"    [UPSERT ERROR] {record_id}: HTTP {e.code} -- {body}")
        return False
    except Exception as e:
        log(f"    [UPSERT ERROR] {record_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    dry_run = "--dry-run" in sys.argv
    limit = None
    skip = 0
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        if arg.startswith("--skip="):
            skip = int(arg.split("=")[1])

    if not EXA_API_KEY:
        log("ERROR: EXA_API_KEY not set")
        sys.exit(1)
    if not PINECONE_API_KEY:
        log("ERROR: PINECONE_API_KEY not set")
        sys.exit(1)

    # Load documents
    with open(DOC_LIST_PATH) as f:
        data = json.load(f)
    docs = data["documents"]

    if skip:
        docs = docs[skip:]
    if limit:
        docs = docs[:limit]

    stats["docs_total"] = len(docs)

    mode = "DRY RUN" if dry_run else "LIVE"
    log(f"\n{'='*60}")
    log(f"Exa.AI Document Ingestion -- {mode}")
    log(f"Documents: {len(docs)} | Content cap: {CONTENT_CAP} chars")
    log(f"Pinecone: sectors-e5-multilingual / sectors namespace")
    log(f"{'='*60}\n")

    # Phase 1: Fetch all documents (sequential to avoid hangs)
    log("[Phase 1] Fetching documents via Exa.AI...")
    fetched = []
    t0 = time.time()

    for i, doc in enumerate(docs):
        url = doc["url"]
        sector = doc["sector"]
        title = doc["title"]
        snippet = doc.get("snippet", "")
        domain = urlparse(url).netloc.replace("www.", "")
        idx = skip + i  # Preserve original index for record IDs

        content = exa_fetch(url)
        if content:
            inc_stat("docs_fetched")
            inc_sector_stat(sector, "fetched")
            fetched.append({"doc": doc, "content": content, "source_type": "exa-full", "domain": domain, "idx": idx})
            log(f"  [{i+1:3d}/{len(docs)}] OK (full)     {sector:10s} | {len(content):6d} chars | {title[:55]}")
        elif snippet and len(snippet) >= CHUNK_MIN:
            inc_stat("docs_snippet_fallback")
            inc_sector_stat(sector, "fetched")
            fetched.append({"doc": doc, "content": snippet, "source_type": "snippet", "domain": domain, "idx": idx})
            log(f"  [{i+1:3d}/{len(docs)}] OK (snippet)  {sector:10s} | {len(snippet):6d} chars | {title[:55]}")
        else:
            inc_stat("docs_failed")
            inc_sector_stat(sector, "errors")
            log(f"  [{i+1:3d}/{len(docs)}] FAIL          {sector:10s} | {url[:65]}")

    fetch_time = time.time() - t0
    log(f"\n  Fetch complete: {len(fetched)} OK / {stats['docs_total']} total in {fetch_time:.1f}s")

    # Phase 2: Chunk all fetched documents
    log(f"\n[Phase 2] Chunking {len(fetched)} documents...")
    all_chunks = []

    for item in fetched:
        doc = item["doc"]
        content = item["content"]
        domain = item["domain"]
        idx = item["idx"]
        sector = doc["sector"]
        title = doc["title"]

        prefixed = f"{title}\n\nSecteur: {sector}\n\n{content}"
        chunks = chunk_text(prefixed)

        for ci, chunk in enumerate(chunks):
            record_id = f"exa-{sector}-{idx:04d}-{ci:03d}"
            source = f"exa-{domain}"
            all_chunks.append({
                "record_id": record_id,
                "text": chunk,
                "sector": sector,
                "source": source,
                "title": title,
            })

        inc_stat("chunks_created", len(chunks))
        inc_sector_stat(sector, "chunks", len(chunks))

    log(f"  Total chunks: {stats['chunks_created']}")
    for sector, s_stats in sorted(stats["by_sector"].items()):
        log(f"    {sector:12s}: {s_stats.get('chunks', 0)} chunks from {s_stats.get('fetched', 0)} docs")

    if dry_run:
        log(f"\n[DRY RUN] Would upsert {len(all_chunks)} chunks. Exiting.")
        if all_chunks:
            sample = all_chunks[0]
            log(f"\n  Sample record:")
            log(f"    _id:    {sample['record_id']}")
            log(f"    sector: {sample['sector']}")
            log(f"    source: {sample['source']}")
            log(f"    title:  {sample['title'][:80]}")
            log(f"    text:   {sample['text'][:200]}...")
        print_stats()
        return

    # Phase 3: Upsert to Pinecone (sequential)
    log(f"\n[Phase 3] Upserting {len(all_chunks)} chunks to Pinecone E5...")
    t1 = time.time()

    for i, chunk in enumerate(all_chunks):
        ok = pinecone_upsert(
            record_id=chunk["record_id"],
            text=chunk["text"],
            sector=chunk["sector"],
            source=chunk["source"],
            title=chunk["title"],
        )
        if ok:
            inc_stat("chunks_upserted")
            inc_sector_stat(chunk["sector"], "upserted")
        else:
            inc_stat("upsert_errors")
            inc_sector_stat(chunk["sector"], "errors")

        if (i + 1) % 50 == 0 or i == len(all_chunks) - 1:
            elapsed = time.time() - t1
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            log(f"  [{i+1:4d}/{len(all_chunks)}] upserted={stats['chunks_upserted']} errors={stats['upsert_errors']} ({rate:.1f}/s)")

        time.sleep(UPSERT_DELAY)

    upsert_time = time.time() - t1
    total_time = time.time() - t0
    log(f"\n  Upsert complete in {upsert_time:.1f}s (total {total_time:.1f}s)")

    print_stats()


def print_stats():
    log(f"\n{'='*60}")
    log(f"FINAL STATS")
    log(f"{'='*60}")
    log(f"  Documents total:      {stats['docs_total']}")
    log(f"  Documents fetched:    {stats['docs_fetched']}")
    log(f"  Snippet fallbacks:    {stats['docs_snippet_fallback']}")
    log(f"  Documents failed:     {stats['docs_failed']}")
    log(f"  Chunks created:       {stats['chunks_created']}")
    log(f"  Chunks upserted:      {stats['chunks_upserted']}")
    log(f"  Upsert errors:        {stats['upsert_errors']}")
    log(f"\n  By sector:")
    for sector, s_stats in sorted(stats["by_sector"].items()):
        log(f"    {sector:12s}: fetched={s_stats.get('fetched',0)} chunks={s_stats.get('chunks',0)} upserted={s_stats.get('upserted',0)} errors={s_stats.get('errors',0)}")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
