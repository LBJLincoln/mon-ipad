#!/usr/bin/env python3
"""
Redis Ingestion→Enrichment Bridge
===================================
Connects the Ingestion and Enrichment pipelines via Upstash Redis.

Flow:
  1. Watches for new docs in Supabase (ingested by n8n V4.0 or VM scripts)
  2. Pushes doc_ids to Upstash Redis queue
  3. Worker calls Enrichment V4.0 on S9 for each doc
  4. Validates enrichment results in Neo4j
  5. Marks docs as enriched in Supabase

Usage:
  source .env.local
  python3 ops/redis-ingest-bridge.py                 # One cycle
  python3 ops/redis-ingest-bridge.py --daemon 600    # Every 10min
  python3 ops/redis-ingest-bridge.py --validate      # Validate only
"""

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
import urllib.request
import urllib.error
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── Config ──
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

# Load env
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
S9_URL = "https://lbjlincoln-nomos-rag-engine-9.hf.space"
ENRICHMENT_WEBHOOK = f"{S9_URL}/webhook/rag-v6-enrichment"
INGESTION_WEBHOOK = f"{S9_URL}/webhook/rag-v6-ingestion"

QUEUE_NAME = "nomos:enrich:pending"
PROCESSED_SET = "nomos:enrich:done"
BATCH_SIZE = 20

_shutdown = False
def _handle_sig(s, f):
    global _shutdown
    _shutdown = True
signal.signal(signal.SIGINT, _handle_sig)
signal.signal(signal.SIGTERM, _handle_sig)

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# ── Upstash Redis (REST API) ──
def redis_cmd(*args):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    url = f"{UPSTASH_URL}"
    payload = json.dumps(list(args)).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {UPSTASH_TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("result")
    except Exception as e:
        log(f"Redis error: {e}")
        return None

def redis_push(queue, value):
    return redis_cmd("LPUSH", queue, value)

def redis_pop(queue):
    return redis_cmd("RPOP", queue)

def redis_sismember(setname, member):
    return redis_cmd("SISMEMBER", setname, member)

def redis_sadd(setname, member):
    return redis_cmd("SADD", setname, member)

def redis_llen(queue):
    return redis_cmd("LLEN", queue)

# ── Supabase (psycopg2) ──
_db = None
def get_db():
    global _db
    if _db and not _db.closed:
        return _db
    try:
        import psycopg2
        _db = psycopg2.connect(DATABASE_URL)
        _db.autocommit = True
        with _db.cursor() as cur:
            cur.execute("SET search_path TO public")
        return _db
    except Exception as e:
        log(f"DB error: {e}")
        return None

def get_unenriched_docs(limit=50):
    db = get_db()
    if not db:
        return []
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, sector, dataset_name,
                       substring(context, 1, 200) as preview
                FROM sector_documents
                WHERE (metadata->>'enriched') IS NULL
                  OR (metadata->>'enriched')::text != 'true'
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
    except Exception as e:
        log(f"Query error: {e}")
        return []

def mark_enriched(doc_id):
    db = get_db()
    if not db:
        return
    try:
        with db.cursor() as cur:
            cur.execute("""
                UPDATE sector_documents
                SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"enriched": "true"}'::jsonb
                WHERE id = %s
            """, (doc_id,))
    except Exception as e:
        log(f"Mark error: {e}")

# ── Enrichment call ──
def call_enrichment(doc_id, sector):
    payload = json.dumps({
        "doc_id": doc_id,
        "sector": sector,
        "source": "redis-bridge",
    }).encode()
    req = urllib.request.Request(ENRICHMENT_WEBHOOK, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return True, resp.read().decode()[:200]
    except Exception as e:
        return False, str(e)[:200]

# ── Ingestion + Enrichment chain ──
def ingest_and_enrich(url, sector, source="redis-bridge"):
    """Full chain: Ingest via n8n V4.0, then queue for enrichment."""
    # Step 1: Submit to Ingestion
    payload = json.dumps({
        "url": url,
        "sector": sector,
        "source": source,
        "process_with_docling": True,
    }).encode()
    req = urllib.request.Request(INGESTION_WEBHOOK, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read().decode()
            log(f"  Ingestion submitted: {url[:60]}...")
            # Step 2: Queue enrichment (will be picked up next cycle)
            redis_push(QUEUE_NAME, json.dumps({
                "url": url, "sector": sector, "source": source,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }))
            return True
    except Exception as e:
        log(f"  Ingestion failed: {e}")
        return False

# ── Main cycle ──
def run_cycle():
    log("=== BRIDGE CYCLE START ===")

    # Phase 1: Find unenriched docs in Supabase
    docs = get_unenriched_docs(BATCH_SIZE)
    log(f"Found {len(docs)} unenriched docs in Supabase")

    # Phase 2: Push to Redis queue
    pushed = 0
    for doc_id, sector, dataset, preview in docs:
        already = redis_sismember(PROCESSED_SET, str(doc_id))
        if already:
            continue
        redis_push(QUEUE_NAME, json.dumps({
            "doc_id": str(doc_id), "sector": sector,
        }))
        pushed += 1
    log(f"Pushed {pushed} new docs to Redis queue")

    # Phase 3: Process enrichment queue
    qlen = redis_llen(QUEUE_NAME) or 0
    log(f"Redis queue length: {qlen}")

    processed = 0
    errors = 0
    while not _shutdown and processed < BATCH_SIZE:
        item = redis_pop(QUEUE_NAME)
        if not item:
            break
        try:
            data = json.loads(item)
            doc_id = data.get("doc_id", "")
            sector = data.get("sector", "finance")

            if doc_id:
                ok, detail = call_enrichment(doc_id, sector)
                if ok:
                    redis_sadd(PROCESSED_SET, doc_id)
                    mark_enriched(doc_id)
                    processed += 1
                    log(f"  Enriched: {doc_id[:20]} ({sector})")
                else:
                    errors += 1
                    log(f"  Failed: {doc_id[:20]} — {detail[:80]}")
        except Exception as e:
            errors += 1
            log(f"  Error processing item: {e}")

    log(f"=== CYCLE DONE: {processed} enriched, {errors} errors ===")
    return processed, errors

# ── Validate ──
def validate():
    log("=== VALIDATION ===")
    db = get_db()
    if not db:
        log("No DB connection")
        return

    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM sector_documents")
        total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM sector_documents WHERE (metadata->>'enriched')::text = 'true'")
        enriched = cur.fetchone()[0]
        cur.execute("""
            SELECT sector, count(*)
            FROM sector_documents
            GROUP BY sector ORDER BY sector
        """)
        sectors = cur.fetchall()

    log(f"Total docs: {total}")
    log(f"Enriched: {enriched} ({100*enriched//max(total,1)}%)")
    for sector, cnt in sectors:
        log(f"  {sector}: {cnt}")

    # Check Redis queue
    qlen = redis_llen(QUEUE_NAME) or 0
    log(f"Redis pending queue: {qlen}")

    # Check Pinecone
    try:
        pkey = os.environ.get("PINECONE_API_KEY", "")
        phost = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
        req = urllib.request.Request(f"{phost}/describe_index_stats")
        req.add_header("Api-Key", pkey)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            log(f"Pinecone E5 vectors: {data.get('totalVectorCount', 0)}")
    except Exception as e:
        log(f"Pinecone check failed: {e}")

    log("=== VALIDATION DONE ===")


def main():
    parser = argparse.ArgumentParser(description="Redis Ingestion→Enrichment Bridge")
    parser.add_argument("--daemon", type=int, help="Run as daemon with interval (seconds)")
    parser.add_argument("--validate", action="store_true", help="Validate only")
    parser.add_argument("--batch", type=int, default=20, help="Batch size")
    args = parser.parse_args()

    global BATCH_SIZE
    BATCH_SIZE = args.batch

    # Verify Redis connection
    test = redis_cmd("PING")
    if test != "PONG":
        log(f"WARNING: Redis not responding (got {test}). Queue features disabled.")
    else:
        log(f"Redis connected: {UPSTASH_URL[:30]}...")

    if args.validate:
        validate()
        return

    if args.daemon:
        log(f"Starting bridge daemon (interval: {args.daemon}s)")
        while not _shutdown:
            try:
                run_cycle()
                validate()
            except Exception as e:
                log(f"Cycle error: {e}")
            if _shutdown:
                break
            log(f"Sleeping {args.daemon}s...")
            elapsed = 0
            while not _shutdown and elapsed < args.daemon:
                time.sleep(5)
                elapsed += 5
        log("Bridge daemon stopped")
    else:
        run_cycle()
        validate()


if __name__ == "__main__":
    main()
