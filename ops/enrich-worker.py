#!/usr/bin/env python3
"""
Enrichment Worker — Consumes from enrichment queue, enriches documents.

Queue backend: Supabase `enrichment_queue` table (Redis upgrade path available).

Flow:
  1. Poll Supabase enrichment_queue for pending docs
  2. Fetch document content from sector_documents
  3. Extract entities (regex NER) → Neo4j
  4. Extract financial data → Supabase sector_financial_tables
  5. Mark document as enriched
  6. Log results

Usage:
  source .env.local
  python3 ops/enrich-worker.py                    # One cycle
  python3 ops/enrich-worker.py --daemon 300       # Every 5min
  python3 ops/enrich-worker.py --batch 50         # Process 50 docs
"""

# ── IPv4 fix (VM has IPv6 issues) ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import argparse
import hashlib
import json
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone
from collections import defaultdict

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── Config ──
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

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

DATABASE_URL = os.environ.get("DATABASE_URL", "")
NEO4J_URI = os.environ.get("NEO4J_URI", "")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")

BATCH_SIZE = 20
STATE_FILE = os.path.join(REPO_ROOT, "data", "agents", "enrich-worker-state.json")

_shutdown = False
def _handle_sig(s, f):
    global _shutdown
    _shutdown = True
signal.signal(signal.SIGINT, _handle_sig)
signal.signal(signal.SIGTERM, _handle_sig)

# ── Entity extraction patterns (from populate-neo4j-entities.py) ──
LAW_PATTERNS = [
    r'[Aa]rticle\s+(?:L\.?\s*)?[\d][\d\-\.]+',
    r'[Cc]ode\s+(?:civil|de\s+commerce|du\s+travail|p[eé]nal|de\s+l[\'\u2019]environnement|de\s+la\s+construction|g[eé]n[eé]ral\s+des\s+imp[oô]ts|mon[eé]taire\s+et\s+financier)',
    r'[Ll]oi\s+n[°o]?\s*[\d\-]+',
    r'[Dd][eé]cret\s+n[°o]?\s*[\d\-]+',
    r'[Dd]irective\s+\d{4}/\d+/[A-Z]+',
    r'[Rr][eè]glement\s+\d{4}/\d+',
]

STANDARD_PATTERNS = [
    r'ISO\s*\d{3,5}(?:[:\-]\d+)?',
    r'NF\s+(?:EN\s+)?\d{3,}',
    r'DTU\s+\d{1,2}(?:\.\d+)*',
    r'Eurocode\s*\d{1}',
    r'IFRS\s*\d{0,2}',
    r'IAS\s*\d{1,2}',
    r'Basel\s+(?:I{1,3}|IV)',
    r'MiFID\s*(?:I{1,2})?',
    r'RGPD', r'DORA',
]

FINANCIAL_TERMS = [
    r'\bEBITDA\b', r'\bEBIT\b', r'\bROE\b', r'\bROA\b', r'\bWACC\b',
    r'\bEPS\b', r'\bP/E\b', r'\bBFR\b', r'\bCAF\b', r'\bDCF\b',
    r'\bFCF\b', r'\bNAV\b', r'\bIPO\b', r'\bM&A\b', r'\bLBO\b',
]

BTP_TERMS = [
    r'\b(?:gros\s+[oœ]uvre|second\s+[oœ]uvre)\b',
    r'\b(?:b[eé]ton\s+arm[eé])\b',
    r'\b(?:VRD|CVC|HVAC|SSI)\b',
    r'\bDQE\b', r'\bDPGF\b', r'\bDCE\b',
    r'\bOPC\b', r'\bBET\b', r'\bAMO\b',
]

INDUSTRIE_TERMS = [
    r'\bAMDEC\b', r'\bSPC\b', r'\bTPM\b', r'\bSMED\b',
    r'\b(?:Lean|Six\s+Sigma|Kaizen|5S)\b',
    r'\bISO\s*(?:9001|14001|45001|50001)\b',
]

ALL_PATTERNS = {
    "law": LAW_PATTERNS,
    "standard": STANDARD_PATTERNS,
    "financial_term": FINANCIAL_TERMS,
    "btp_term": BTP_TERMS,
    "industrie_term": INDUSTRIE_TERMS,
}


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f" {ts} [{level}] {msg}")


def db_connect():
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET search_path TO public")
    return conn, cur


def ensure_queue_table():
    """Create enrichment_queue table if it doesn't exist."""
    conn, cur = db_connect()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS enrichment_queue (
                id SERIAL PRIMARY KEY,
                doc_id TEXT NOT NULL,
                sector TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                processed_at TIMESTAMPTZ,
                result JSONB,
                UNIQUE(doc_id)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_eq_status ON enrichment_queue(status)
        """)
        log("enrichment_queue table ready")
    finally:
        cur.close()
        conn.close()


def queue_push(doc_ids_sectors):
    """Push document IDs to enrichment queue."""
    if not doc_ids_sectors:
        return 0
    conn, cur = db_connect()
    pushed = 0
    try:
        for doc_id, sector in doc_ids_sectors:
            try:
                cur.execute(
                    "INSERT INTO enrichment_queue (doc_id, sector) VALUES (%s, %s) ON CONFLICT (doc_id) DO NOTHING",
                    (doc_id, sector)
                )
                pushed += 1
            except Exception as e:
                log(f"Queue push error for {doc_id}: {e}", "WARN")
    finally:
        cur.close()
        conn.close()
    return pushed


def queue_pop(batch_size=20):
    """Pop batch of pending docs from queue."""
    conn, cur = db_connect()
    try:
        cur.execute("""
            UPDATE enrichment_queue
            SET status = 'processing', processed_at = NOW()
            WHERE id IN (
                SELECT id FROM enrichment_queue
                WHERE status = 'pending'
                ORDER BY created_at
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            RETURNING doc_id, sector
        """, (batch_size,))
        rows = cur.fetchall()
        return [(r[0], r[1]) for r in rows]
    finally:
        cur.close()
        conn.close()


def queue_complete(doc_id, result):
    """Mark a doc as enriched in queue."""
    conn, cur = db_connect()
    try:
        cur.execute(
            "UPDATE enrichment_queue SET status = 'done', result = %s WHERE doc_id = %s",
            (json.dumps(result), doc_id)
        )
    finally:
        cur.close()
        conn.close()


def queue_fail(doc_id, error_msg):
    """Mark a doc as failed in queue."""
    conn, cur = db_connect()
    try:
        cur.execute(
            "UPDATE enrichment_queue SET status = 'failed', result = %s WHERE doc_id = %s",
            (json.dumps({"error": error_msg}), doc_id)
        )
    finally:
        cur.close()
        conn.close()


def queue_stats():
    """Get queue statistics."""
    conn, cur = db_connect()
    try:
        cur.execute("""
            SELECT status, COUNT(*) FROM enrichment_queue GROUP BY status
        """)
        stats = {r[0]: r[1] for r in cur.fetchall()}
        return stats
    finally:
        cur.close()
        conn.close()


def fetch_doc_content(doc_id):
    """Fetch document content from sector_documents."""
    conn, cur = db_connect()
    try:
        cur.execute(
            "SELECT id, title, content, sector, source_url, metadata FROM sector_documents WHERE id = %s",
            (doc_id,)
        )
        row = cur.fetchone()
        if row:
            return {
                "id": row[0], "title": row[1], "content": row[2],
                "sector": row[3], "source_url": row[4],
                "metadata": row[5] if row[5] else {}
            }
        return None
    finally:
        cur.close()
        conn.close()


def extract_entities(text, sector):
    """Extract entities from text using regex NER."""
    entities = []
    seen = set()

    # Select relevant patterns based on sector
    pattern_groups = [("law", LAW_PATTERNS), ("standard", STANDARD_PATTERNS)]
    if sector == "finance":
        pattern_groups.append(("financial_term", FINANCIAL_TERMS))
    elif sector == "btp":
        pattern_groups.append(("btp_term", BTP_TERMS))
    elif sector == "industrie":
        pattern_groups.append(("industrie_term", INDUSTRIE_TERMS))

    for entity_type, patterns in pattern_groups:
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                name = match.group().strip()
                key = (name.lower(), entity_type)
                if key not in seen and len(name) > 2:
                    seen.add(key)
                    entities.append({
                        "name": name,
                        "type": entity_type,
                        "sector": sector,
                    })

    return entities


def neo4j_write_entities(doc_id, title, sector, entities):
    """Write entities and relationships to Neo4j."""
    if not entities:
        return 0

    try:
        from neo4j import GraphDatabase
    except ImportError:
        log("neo4j driver not installed, skipping Neo4j write", "WARN")
        return 0

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    written = 0

    try:
        with driver.session() as session:
            # Create/merge SectorDocument node
            session.run("""
                MERGE (d:SectorDocument {doc_id: $doc_id})
                SET d.title = $title, d.sector = $sector, d.enriched_at = datetime()
            """, doc_id=doc_id, title=title or "", sector=sector)

            # Batch create entities and relationships
            for batch_start in range(0, len(entities), 50):
                batch = entities[batch_start:batch_start + 50]
                session.run("""
                    UNWIND $entities AS e
                    MERGE (ent:Entity {name: e.name, sector: e.sector})
                    ON CREATE SET ent.type = e.type, ent.created_at = datetime()
                    WITH ent, e
                    MATCH (d:SectorDocument {doc_id: $doc_id})
                    MERGE (d)-[:MENTIONS]->(ent)
                """, entities=batch, doc_id=doc_id)
                written += len(batch)
    finally:
        driver.close()

    return written


def enrich_document(doc_id, sector):
    """Full enrichment pipeline for a single document."""
    doc = fetch_doc_content(doc_id)
    if not doc:
        return {"status": "not_found", "entities": 0}

    content = doc.get("content", "") or ""
    title = doc.get("title", "") or ""
    text = f"{title}\n{content}"

    if len(text) < 50:
        return {"status": "too_short", "entities": 0}

    # Extract entities
    entities = extract_entities(text, sector)

    # Write to Neo4j
    neo4j_count = 0
    if entities and NEO4J_URI:
        try:
            neo4j_count = neo4j_write_entities(doc_id, title, sector, entities)
        except Exception as e:
            log(f"Neo4j write failed for {doc_id}: {e}", "ERROR")

    # Mark document as enriched in Supabase
    try:
        conn, cur = db_connect()
        cur.execute(
            "UPDATE sector_documents SET metadata = COALESCE(metadata, '{}'::jsonb) || %s WHERE id = %s",
            (json.dumps({"enriched": True, "enriched_at": datetime.now(timezone.utc).isoformat(),
                         "entity_count": len(entities)}), doc_id)
        )
        cur.close()
        conn.close()
    except Exception as e:
        log(f"Supabase update failed for {doc_id}: {e}", "WARN")

    return {
        "status": "enriched",
        "entities_found": len(entities),
        "entities_written": neo4j_count,
        "entity_types": list(set(e["type"] for e in entities)),
    }


def find_unenriched_docs(limit=100):
    """Find documents that haven't been enriched yet (not in queue or sector_documents)."""
    conn, cur = db_connect()
    try:
        cur.execute("""
            SELECT id, sector FROM sector_documents
            WHERE (metadata IS NULL OR metadata->>'enriched' IS NULL OR metadata->>'enriched' = 'false')
            AND content IS NOT NULL AND LENGTH(content) > 50
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        return [(r[0], r[1]) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def run_cycle(batch_size=20, auto_discover=True):
    """Run one enrichment cycle."""
    stats_before = queue_stats()
    pending = stats_before.get("pending", 0)
    log(f"Queue stats: {stats_before}")

    # Auto-discover unenriched docs if queue is low
    if auto_discover and pending < batch_size:
        unenriched = find_unenriched_docs(limit=batch_size * 2)
        if unenriched:
            pushed = queue_push(unenriched)
            log(f"Auto-discovered {len(unenriched)} unenriched docs, queued {pushed}")

    # Pop batch from queue
    batch = queue_pop(batch_size)
    if not batch:
        log("No documents to enrich")
        return {"processed": 0, "entities_total": 0}

    log(f"Processing {len(batch)} documents...")

    total_entities = 0
    successes = 0
    failures = 0

    for doc_id, sector in batch:
        if _shutdown:
            break

        try:
            result = enrich_document(doc_id, sector)
            queue_complete(doc_id, result)
            total_entities += result.get("entities_found", 0)
            if result["status"] == "enriched":
                successes += 1
            log(f"  {doc_id[:20]}... ({sector}): {result['status']}, {result.get('entities_found', 0)} entities")
        except Exception as e:
            queue_fail(doc_id, str(e))
            failures += 1
            log(f"  {doc_id[:20]}... FAILED: {e}", "ERROR")

    stats_after = queue_stats()
    summary = {
        "processed": len(batch),
        "successes": successes,
        "failures": failures,
        "entities_total": total_entities,
        "queue_after": stats_after,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    log(f"Cycle complete: {successes} enriched, {failures} failed, {total_entities} entities")

    # Save state
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Enrichment Worker")
    parser.add_argument("--daemon", type=int, help="Run as daemon with N second interval")
    parser.add_argument("--batch", type=int, default=20, help="Batch size (default: 20)")
    parser.add_argument("--stats", action="store_true", help="Show queue stats and exit")
    parser.add_argument("--setup", action="store_true", help="Create queue table and exit")
    args = parser.parse_args()

    if args.setup:
        ensure_queue_table()
        return

    if args.stats:
        ensure_queue_table()
        stats = queue_stats()
        print(json.dumps(stats, indent=2))
        return

    ensure_queue_table()

    if args.daemon:
        log(f"Starting enrichment worker daemon (every {args.daemon}s, batch={args.batch})")
        cycle = 0
        while not _shutdown:
            cycle += 1
            log(f"═══ Enrichment cycle {cycle} ═══")
            try:
                run_cycle(batch_size=args.batch)
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
            if not _shutdown:
                log(f"Next cycle in {args.daemon}s")
                for _ in range(args.daemon):
                    if _shutdown:
                        break
                    time.sleep(1)
        log("Worker stopped")
    else:
        run_cycle(batch_size=args.batch)


if __name__ == "__main__":
    main()
