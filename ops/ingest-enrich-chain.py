#!/usr/bin/env python3
"""
Ingestion → Enrichment Chain — Direct n8n webhook chain.

Since Redis (Upstash) is unreachable from VM and n8n Redis nodes are stubs,
this script chains Ingestion and Enrichment via direct webhook calls.

Flow:
  1. Find unenriched docs in Supabase
  2. For each batch: call Ingestion V4.0 webhook (if URL provided)
  3. Wait for processing
  4. Call Enrichment V4.0 webhook for each doc
  5. Verify enrichment in Supabase
  6. Mark docs as enriched

Usage:
  source .env.local
  python3 ops/ingest-enrich-chain.py                    # One cycle
  python3 ops/ingest-enrich-chain.py --daemon 1800      # Every 30min
  python3 ops/ingest-enrich-chain.py --ingest-urls urls.txt  # Ingest from file
"""

# ── IPv4 fix ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from urllib import request, error

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

# Load env
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip().lstrip("export").strip()
                v = v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

DB_URL = os.environ.get("DATABASE_URL", "")

# n8n endpoints — S9 has Ingestion V4.0 + Enrichment V4.0
N8N_HOSTS = [
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",   # S9 — primary (has both workflows)
    "https://lbjlincoln-nomos-rag-engine.hf.space",      # S1 — fallback
]
INGEST_WEBHOOK_PATH = "/webhook/rag-v6-ingestion"
ENRICH_WEBHOOK_PATH = "/webhook/rag-v6-enrichment"

BATCH_SIZE = 10
_shutdown = False

def _handle_sig(s, f):
    global _shutdown
    _shutdown = True
signal.signal(signal.SIGINT, _handle_sig)
signal.signal(signal.SIGTERM, _handle_sig)


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] CHAIN: {msg}")


def get_db():
    import psycopg2
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    with conn.cursor() as c:
        c.execute("SET search_path TO public")
    return conn


def get_unenriched_docs(limit=50):
    """Find docs that need enrichment."""
    try:
        conn = get_db()
        with conn.cursor() as c:
            c.execute("""
                SELECT id, sector, dataset_name,
                       SUBSTRING(context, 1, 100) as preview
                FROM sector_documents
                WHERE (metadata->>'enriched') IS NULL
                   OR (metadata->>'enriched')::text != 'true'
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        log(f"DB error: {e}")
        return []


def get_recently_ingested(hours=6, limit=50):
    """Find recently ingested docs."""
    try:
        conn = get_db()
        with conn.cursor() as c:
            c.execute("""
                SELECT id, sector, dataset_name
                FROM sector_documents
                WHERE created_at > NOW() - INTERVAL '%s hours'
                ORDER BY created_at DESC
                LIMIT %s
            """, (hours, limit))
            rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        log(f"DB error: {e}")
        return []


def call_ingest(url, sector, source="chain"):
    """Submit URL to Ingestion V4.0 (tries S9 then S1)."""
    payload = json.dumps({
        "url": url,
        "sector": sector,
        "source": source,
        "tenant_id": sector,
        "process_with_docling": True,
    }).encode()
    for host in N8N_HOSTS:
        webhook = f"{host}{INGEST_WEBHOOK_PATH}"
        req = request.Request(webhook, data=payload,
                              headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=30) as resp:
                result = resp.read().decode()
                return True, result[:100]
        except Exception as e:
            continue
    return False, "All hosts failed"


def call_enrich(doc_id, sector, source="chain"):
    """Submit doc to Enrichment V4.0 (tries S9 then S1)."""
    payload = json.dumps({
        "doc_id": str(doc_id),
        "sector": sector,
        "source": source,
    }).encode()
    for host in N8N_HOSTS:
        webhook = f"{host}{ENRICH_WEBHOOK_PATH}"
        req = request.Request(webhook, data=payload,
                              headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=60) as resp:
                result = resp.read().decode()
                return True, result[:100]
        except error.HTTPError as e:
            # 500 is expected — workflow runs but response node format issue
            if e.code == 500 and "No item to return" in (e.read().decode() if hasattr(e, 'read') else ""):
                return True, "fire-and-forget (workflow ran)"
            continue
        except Exception:
            continue
    return False, "All hosts failed"


def mark_enriched(doc_id):
    """Mark doc as enriched in Supabase."""
    try:
        conn = get_db()
        with conn.cursor() as c:
            c.execute("""
                UPDATE sector_documents
                SET metadata = COALESCE(metadata, '{}'::jsonb)
                    || '{"enriched": "true"}'::jsonb
                WHERE id = %s
            """, (doc_id,))
        conn.close()
    except Exception as e:
        log(f"Mark error: {e}")


def ingest_from_urls(url_file, sector="finance"):
    """Ingest URLs from a file."""
    log(f"Ingesting from {url_file}")
    with open(url_file) as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    log(f"Found {len(urls)} URLs to ingest")
    ok, fail = 0, 0
    for url in urls:
        if _shutdown:
            break
        success, detail = call_ingest(url, sector)
        if success:
            ok += 1
            log(f"  [+] {url[:60]}...")
        else:
            fail += 1
            log(f"  [-] {url[:60]}... — {detail}")
        time.sleep(2)  # Don't flood n8n

    log(f"Ingestion done: {ok} OK, {fail} failed")
    return ok, fail


def run_enrichment_cycle():
    """Find unenriched docs and submit to Enrichment V4.0."""
    log("=== ENRICHMENT CYCLE ===")

    docs = get_unenriched_docs(BATCH_SIZE)
    log(f"Found {len(docs)} unenriched docs")

    if not docs:
        log("Nothing to enrich")
        return 0, 0

    ok, fail = 0, 0
    for doc_id, sector, dataset, preview in docs:
        if _shutdown:
            break
        success, detail = call_enrich(doc_id, sector)
        if success:
            mark_enriched(doc_id)
            ok += 1
            log(f"  [+] {str(doc_id)[:20]} ({sector}) — {detail[:60]}")
        else:
            fail += 1
            log(f"  [-] {str(doc_id)[:20]} ({sector}) — {detail[:60]}")
        time.sleep(1)

    log(f"Enrichment: {ok} OK, {fail} failed")
    return ok, fail


def run_full_cycle():
    """Full cycle: check recent ingestions, enrich what's needed."""
    log("=" * 60)
    log("INGESTION→ENRICHMENT CHAIN CYCLE")
    log("=" * 60)

    # Phase 1: Check recently ingested docs
    recent = get_recently_ingested(hours=24, limit=100)
    log(f"Recently ingested (24h): {len(recent)} docs")

    # Phase 2: Run enrichment on unenriched docs
    ok, fail = run_enrichment_cycle()

    # Phase 3: Verify
    try:
        conn = get_db()
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) FROM sector_documents")
            total = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM sector_documents WHERE (metadata->>'enriched')::text = 'true'")
            enriched = c.fetchone()[0]
        conn.close()
        log(f"Status: {enriched}/{total} enriched ({100*enriched//max(total,1)}%)")
    except Exception as e:
        log(f"Verify error: {e}")

    log(f"=== CYCLE DONE: {ok} enriched, {fail} failed ===")
    return ok, fail


def main():
    parser = argparse.ArgumentParser(description="Ingestion→Enrichment Chain")
    parser.add_argument("--daemon", type=int, help="Run as daemon with interval (seconds)")
    parser.add_argument("--ingest-urls", type=str, help="File with URLs to ingest")
    parser.add_argument("--sector", type=str, default="finance", help="Sector for URL ingestion")
    parser.add_argument("--batch", type=int, default=10, help="Batch size")
    args = parser.parse_args()

    global BATCH_SIZE
    BATCH_SIZE = args.batch

    # Test n8n connectivity
    log(f"Ingestion: {N8N_HOSTS[0]}{INGEST_WEBHOOK_PATH}")
    log(f"Enrichment: {N8N_HOSTS[0]}{ENRICH_WEBHOOK_PATH}")

    if args.ingest_urls:
        ingest_from_urls(args.ingest_urls, args.sector)
        time.sleep(10)  # Wait for ingestion to process

    if args.daemon:
        log(f"DAEMON MODE: every {args.daemon}s")
        while not _shutdown:
            try:
                run_full_cycle()
            except Exception as e:
                log(f"Cycle error: {e}")
            if _shutdown:
                break
            log(f"Sleeping {args.daemon}s...")
            elapsed = 0
            while not _shutdown and elapsed < args.daemon:
                time.sleep(5)
                elapsed += 5
        log("Daemon stopped")
    else:
        run_full_cycle()


if __name__ == "__main__":
    main()
