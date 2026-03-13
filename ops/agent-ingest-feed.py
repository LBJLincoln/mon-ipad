#!/usr/bin/env python3
"""
Agent Ingest Feed — Tavily → n8n Ingestion/Enrichment → Docling → DBs

Feeds Tavily search results into the n8n Ingestion V4.0 and Enrichment V4.0
workflows. This is the SEPARATE ingestion system (not RAG pipelines).

Architecture:
  1. Tavily search (per sector, rotating queries)
  2. For each result with PDF/document:
     a. POST to n8n Ingestion V4.0 webhook → Docling S6 → Pinecone + Supabase
     b. POST to n8n Enrichment V4.0 webhook → Neo4j entities
  3. For text results:
     a. Direct fast-ingest to E5 Pinecone
     b. populate-neo4j-entities for enrichment
  4. Track progress in Supabase document_registry

Usage:
  source .env.local
  python3 ops/agent-ingest-feed.py                    # One cycle
  python3 ops/agent-ingest-feed.py --daemon 3600      # Continuous
  python3 ops/agent-ingest-feed.py --sector finance   # Single sector
"""

# ── IPv4 fix ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import json
import os
import subprocess
import sys
import time
import traceback
import hashlib
from datetime import datetime, timezone
from urllib import request, error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "agents")
INGEST_DIR = os.path.join(REPO_ROOT, "data", "ingest")
os.makedirs(INGEST_DIR, exist_ok=True)

# n8n Ingestion/Enrichment webhooks (on S1, shared DB with S3/S5)
N8N_HOST = "https://lbjlincoln-nomos-rag-engine.hf.space"
INGESTION_WEBHOOK = f"{N8N_HOST}/webhook/rag-v6-ingestion"
ENRICHMENT_WEBHOOK = f"{N8N_HOST}/webhook/rag-v6-enrichment"

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

DB_URL = os.environ.get("DATABASE_URL", "")
_db = None

def get_db():
    global _db
    if _db and not _db.closed:
        return _db
    try:
        import psycopg2
        _db = psycopg2.connect(DB_URL)
        _db.autocommit = True
        with _db.cursor() as c:
            c.execute("SET search_path TO public")
        return _db
    except:
        return None

def db_execute(sql, params=None):
    conn = get_db()
    if not conn:
        return None
    try:
        with conn.cursor() as c:
            c.execute(sql, params)
            if c.description:
                return c.fetchall()
            return True
    except Exception as e:
        log(f"DB: {e}")
        return None

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] INGEST: {msg}")

# ── Sector Tavily queries ──
SECTOR_QUERIES = {
    "finance": [
        "IFRS 2024 normes comptables internationales",
        "ratio financier analyse crédit entreprise",
        "bilan comptable analyse financière PME France",
        "réglementation bancaire Bâle III France",
        "marché obligataire taux intérêt 2024",
    ],
    "btp": [
        "DTU normes construction France 2024",
        "Eurocode béton armé calcul structure",
        "RE2020 réglementation environnementale bâtiment",
        "CCTP cahier clauses techniques travaux publics",
        "permis construire urbanisme PLU France",
    ],
    "juridique": [
        "code civil obligations contrats France",
        "RGPD protection données personnelles entreprise",
        "droit du travail licenciement procédure France",
        "droit des sociétés SAS SARL statuts",
        "jurisprudence cour cassation commerciale récente",
    ],
    "industrie": [
        "ISO 9001 qualité management certification",
        "AMDEC analyse défaillances processus industriel",
        "maintenance prédictive industrie 4.0 IoT",
        "fiche données sécurité FDS REACH chimie",
        "lean manufacturing Six Sigma amélioration continue",
    ],
}

_query_index = {}


def tavily_search(query, max_results=5):
    """Search via Tavily API."""
    if not TAVILY_API_KEY:
        log("No TAVILY_API_KEY — skipping search")
        return []

    payload = json.dumps({
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "include_raw_content": True,
        "search_depth": "advanced",
    }).encode()

    try:
        req = request.Request("https://api.tavily.com/search",
                              data=payload,
                              headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("results", [])
    except Exception as e:
        log(f"Tavily error: {e}")
        return []


def feed_to_n8n_ingestion(doc, sector):
    """Send document to n8n Ingestion V4.0 webhook."""
    payload = json.dumps({
        "url": doc.get("url", ""),
        "title": doc.get("title", ""),
        "content": doc.get("raw_content", doc.get("content", "")),
        "sector": sector,
        "source": "tavily",
        "source_domain": doc.get("url", "").split("/")[2] if "/" in doc.get("url", "") else "",
    }).encode()

    try:
        req = request.Request(INGESTION_WEBHOOK, data=payload,
                              headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            return {"ok": True, "result": result}
    except error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except:
            pass
        return {"ok": False, "error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def feed_to_n8n_enrichment(doc, sector):
    """Send to n8n Enrichment V4.0 webhook."""
    payload = json.dumps({
        "text": doc.get("raw_content", doc.get("content", "")),
        "sector": sector,
        "source_url": doc.get("url", ""),
        "title": doc.get("title", ""),
    }).encode()

    try:
        req = request.Request(ENRICHMENT_WEBHOOK, data=payload,
                              headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode())
            return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def direct_ingest(docs, sector):
    """Fallback: direct E5 Pinecone ingest via fast-ingest."""
    # Save to JSONL for fast-ingest
    jsonl_path = os.path.expanduser(
        f"~/rag-data-ingestion/datasets/sectors/{sector}/tavily_web.jsonl")
    os.makedirs(os.path.dirname(jsonl_path), exist_ok=True)

    new_count = 0
    existing_hashes = set()
    if os.path.exists(jsonl_path):
        with open(jsonl_path) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    h = rec.get("content_hash", "")
                    if h:
                        existing_hashes.add(h)
                except:
                    pass

    with open(jsonl_path, "a") as f:
        for doc in docs:
            content = doc.get("raw_content", doc.get("content", ""))
            if not content or len(content) < 50:
                continue
            h = hashlib.md5(content.encode()).hexdigest()[:12]
            if h in existing_hashes:
                continue
            existing_hashes.add(h)

            # Chunk
            chunks = chunk_text(content, 1000, 200)
            for i, chunk in enumerate(chunks):
                record = {
                    "text": chunk,
                    "sector": sector,
                    "source": doc.get("url", ""),
                    "title": doc.get("title", ""),
                    "content_hash": f"{h}-{i:03d}",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                new_count += 1

    if new_count > 0:
        log(f"  Saved {new_count} chunks to JSONL, running fast-ingest...")
        try:
            subprocess.run(
                [sys.executable, os.path.join(REPO_ROOT, "ops", "fast-ingest.py"),
                 "--sector", sector],
                capture_output=True, text=True, timeout=300, cwd=REPO_ROOT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except:
            pass

    return new_count


def chunk_text(text, size=1000, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += size - overlap
    return chunks


def register_document(doc, sector, status):
    """Track in document_registry."""
    url = doc.get("url", "")
    if not url:
        return
    domain = url.split("/")[2] if len(url.split("/")) > 2 else ""
    h = hashlib.md5(url.encode()).hexdigest()[:16]

    db_execute("""
        INSERT INTO document_registry (sector, source_type, source_url, source_domain,
                                       title, processing_status, content_hash)
        VALUES (%s, 'tavily', %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (sector, url, domain, doc.get("title", "")[:500], status, h))


def run_cycle(sector_filter=None):
    log("=" * 60)
    log("INGEST FEED CYCLE")
    log("=" * 60)

    sectors = [sector_filter] if sector_filter else ["finance", "btp", "juridique", "industrie"]
    total_docs = 0
    total_ingested = 0
    n8n_ok = 0
    n8n_fail = 0

    for sector in sectors:
        queries = SECTOR_QUERIES.get(sector, [])
        if not queries:
            continue

        # Rotate through queries
        idx = _query_index.get(sector, 0)
        query = queries[idx % len(queries)]
        _query_index[sector] = idx + 1

        log(f"\n  [{sector}] Query: {query[:50]}...")
        results = tavily_search(query, max_results=5)
        log(f"  [{sector}] Got {len(results)} results")
        total_docs += len(results)

        for doc in results:
            url = doc.get("url", "")
            title = doc.get("title", "")[:60]
            content = doc.get("raw_content", doc.get("content", ""))

            if not content or len(content) < 100:
                continue

            # Try n8n Ingestion workflow first
            log(f"    → {title}...")
            ing_result = feed_to_n8n_ingestion(doc, sector)

            if ing_result["ok"]:
                n8n_ok += 1
                log(f"      n8n Ingestion: OK")
                # Also enrich
                enr_result = feed_to_n8n_enrichment(doc, sector)
                if enr_result["ok"]:
                    log(f"      n8n Enrichment: OK")
                else:
                    log(f"      n8n Enrichment: FAIL ({enr_result.get('error', '')[:50]})")
                register_document(doc, sector, "ingested_n8n")
                total_ingested += 1
            else:
                n8n_fail += 1
                log(f"      n8n Ingestion: FAIL ({ing_result.get('error', '')[:50]})")
                # Fallback to direct ingest
                chunks = direct_ingest([doc], sector)
                if chunks > 0:
                    log(f"      Direct ingest: {chunks} chunks")
                    total_ingested += 1
                register_document(doc, sector, "ingested_direct")

            time.sleep(1.5)  # Rate limit

    # Write marker
    marker = os.path.join(DATA_DIR, "ingest_feed_done.marker")
    with open(marker, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_docs": total_docs,
            "total_ingested": total_ingested,
            "n8n_ok": n8n_ok,
            "n8n_fail": n8n_fail,
        }, f)

    log(f"\nCycle complete: {total_docs} docs found, {total_ingested} ingested "
        f"(n8n: {n8n_ok} OK, {n8n_fail} fail)")
    log("=" * 60)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", type=int, default=0)
    parser.add_argument("--sector", default=None)
    args = parser.parse_args()

    if args.daemon > 0:
        log(f"DAEMON MODE: every {args.daemon}s")
        while True:
            try:
                run_cycle(args.sector)
            except Exception as e:
                log(f"Cycle error: {e}")
                traceback.print_exc()
            time.sleep(args.daemon)
    else:
        run_cycle(args.sector)


if __name__ == "__main__":
    main()
