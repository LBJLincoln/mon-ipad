#!/usr/bin/env python3
"""
Enrichment Pipeline V5.0 — Standalone daemon for document enrichment.
=====================================================================

Replaces the broken n8n enrichment workflow (ORa01sX4xI0iRCJ8) with a
clean Python pipeline that handles entity extraction + Neo4j storage
directly, then optionally notifies n8n for any follow-up processing.

Architecture:
  1. Query Supabase for un-enriched documents
  2. LLM entity extraction via LiteLLM S7 (sector-aware prompts)
  3. Store entities in Neo4j via Bolt driver
  4. Update Supabase with enrichment metadata
  5. (Optional) Trigger n8n webhook for additional processing
  6. Log everything to data/enrichment/enrichment.jsonl

Usage:
  source .env.local
  python3 ops/enrichment-pipeline.py                        # One-shot
  python3 ops/enrichment-pipeline.py --daemon               # 300s cycles
  python3 ops/enrichment-pipeline.py --daemon --interval 600
  python3 ops/enrichment-pipeline.py --batch-size 10
  python3 ops/enrichment-pipeline.py --status               # Show stats
  python3 ops/enrichment-pipeline.py --sector finance       # Single sector
  nohup python3 ops/enrichment-pipeline.py --daemon > data/enrichment/daemon.log 2>&1 &
"""

# ── Force IPv4 globally (IPv6 broken on this VM) ─────────────────────────
import socket
from socket import AF_INET

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, AF_INET, type_, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

# ── Standard imports ──────────────────────────────────────────────────────
import argparse
import json
import os
import re
import signal
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Force line-buffered output ────────────────────────────────────────────
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── Load .env.local ──────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.local"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip().lstrip("export").strip()
                v = v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

# ── SSL context (permissive for HF Spaces) ───────────────────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# =========================================================================
# CONFIGURATION
# =========================================================================

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ayqviqmxifzmhphiqfmj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY", "")
SUPABASE_TABLE = "sector_documents"

# Neo4j
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j+s://38c949a2.databases.neo4j.io")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

# LiteLLM S7
LITELLM_URL = os.environ.get("LITELLM_PROXY_URL",
    "https://lbjlincoln-nomos-rag-engine-7.hf.space")
LITELLM_CHAT_URL = f"{LITELLM_URL}/v1/chat/completions"
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")

# n8n (optional post-enrichment notification)
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

# Data dirs
DATA_DIR = REPO_ROOT / "data" / "enrichment"
LOG_FILE = DATA_DIR / "enrichment.jsonl"
STATS_FILE = DATA_DIR / "enrichment-stats.json"
PID_FILE = DATA_DIR / "enrichment.pid"

# Processing config
DEFAULT_BATCH_SIZE = 5
DEFAULT_INTERVAL = 300  # 5 minutes
MAX_ENTITIES_PER_DOC = 20
LLM_TIMEOUT = 60
SUPABASE_TIMEOUT = 30
INTER_DOC_DELAY = 2  # seconds between documents (avoid LiteLLM overload)

SECTORS = ["finance", "btp", "juridique", "industrie"]

# Graceful shutdown
_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    log("Shutdown signal received, finishing current batch...", "WARN")


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# =========================================================================
# LOGGING
# =========================================================================

def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_short = ts[11:19]
    prefix = {"INFO": "+", "WARN": "!", "ERROR": "X", "OK": "v", "SKIP": "-"}.get(level, " ")
    print(f"[{ts_short}] [{prefix}] {msg}", flush=True)

    # Append to JSONL log
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {"ts": ts, "level": level, "msg": msg}
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# =========================================================================
# HTTP UTILITIES
# =========================================================================

def http_request(url, data=None, headers=None, method="GET", timeout=30):
    """HTTP request via urllib. Returns (status, body_bytes, error_string)."""
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


def supabase_request(path, method="GET", data=None, params=None):
    """Make authenticated Supabase REST API request."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, safe=".,*()=")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    status, resp_body, err = http_request(url, data=body, headers=headers,
                                           method=method, timeout=SUPABASE_TIMEOUT)
    if err:
        return None, err

    try:
        result = json.loads(resp_body.decode("utf-8"))
        return result, None
    except Exception as e:
        return None, f"JSON parse error: {e}"


# =========================================================================
# SECTOR-AWARE ENTITY EXTRACTION PROMPTS
# =========================================================================

SECTOR_ENTITY_TYPES = {
    "finance": {
        "types": "Person, Organization, Financial_Metric, Regulation, Standard, Concept, Location, Currency, Index",
        "examples": "e.g., IFRS 16, EBITDA, Bale III, CAC 40, ECB, Jerome Powell",
    },
    "btp": {
        "types": "Person, Organization, Standard, Regulation, Material, Technique, Location, Concept",
        "examples": "e.g., DTU 31.2, Eurocode 2, RE2020, NF EN 1992, beton arme, CCTP",
    },
    "juridique": {
        "types": "Person, Organization, Law, Regulation, Court, Concept, Location, Legal_Principle",
        "examples": "e.g., Code civil art. 1240, RGPD, Cour de cassation, SAS, SARL, Loi Sapin II",
    },
    "industrie": {
        "types": "Person, Organization, Standard, Concept, Equipment, Process, Location, Chemical",
        "examples": "e.g., ISO 9001, AMDEC, Six Sigma, ICPE, Seveso, HACCP, lean manufacturing",
    },
}


def build_extraction_prompt(sector, title, content):
    """Build a sector-aware entity extraction prompt."""
    sector_info = SECTOR_ENTITY_TYPES.get(sector, SECTOR_ENTITY_TYPES["finance"])

    return {
        "model": "smart",
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are an expert in the {sector} sector. "
                    f"Extract all named entities from the document below.\n\n"
                    f"For each entity, provide:\n"
                    f"- name: the entity name (as it appears or its standard name)\n"
                    f"- type: one of [{sector_info['types']}]\n"
                    f"- description: a one-line description in the document's language\n\n"
                    f"Sector-specific examples: {sector_info['examples']}\n\n"
                    f"Return ONLY a JSON array, no markdown, no explanation:\n"
                    f'[{{"name": "...", "type": "...", "description": "..."}}]\n\n'
                    f"If no entities found, return: []"
                ),
            },
            {
                "role": "user",
                "content": f"Sector: {sector}\nTitle: {title}\n\nDocument content:\n{content[:3000]}",
            },
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
    }


# =========================================================================
# STEP 1: QUERY SUPABASE FOR UN-ENRICHED DOCUMENTS
# =========================================================================

def fetch_unenriched_documents(batch_size, sector=None):
    """
    Query Supabase for documents needing enrichment.

    Schema: sector_documents has columns:
      id, sector, dataset_name, pipeline, question, answer, context,
      metadata (JSONB), tenant_id, created_at

    Enrichment status lives in metadata JSONB:
      metadata->has_entities (bool), metadata->entity_count (int),
      metadata->enriched (string "true"/"false")

    We target documents where metadata->>has_entities = 'false'
    (32K+ documents with entity_count=0 and has_entities=false).
    """
    # PostgREST JSONB arrow operator for filtering
    select_fields = "id,sector,question,answer,context,metadata,tenant_id,created_at"

    # Filter: metadata->has_entities is false (needs enrichment)
    # Also require context is not null/empty (skip docs with no text)
    filter_str = "metadata->>has_entities=eq.false&context=neq."

    if sector and sector != "all":
        filter_str += f"&sector=eq.{sector}"

    params_str = (
        f"select={select_fields}"
        f"&{filter_str}"
        f"&order=created_at.desc"
        f"&limit={batch_size}"
    )

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?{params_str}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    status, body, err = http_request(url, headers=headers, method="GET",
                                      timeout=SUPABASE_TIMEOUT)
    if err:
        log(f"Supabase query failed: {err}", "ERROR")
        return []

    if status != 200:
        body_str = body.decode("utf-8", errors="replace")[:200] if body else "empty"
        log(f"Supabase returned HTTP {status}: {body_str}", "ERROR")
        return []

    try:
        docs = json.loads(body.decode("utf-8"))
        if isinstance(docs, list):
            return docs
        # Sometimes Supabase returns an error object
        if isinstance(docs, dict) and "message" in docs:
            log(f"Supabase error: {docs['message']}", "ERROR")
            return []
        return []
    except Exception as e:
        log(f"Supabase parse error: {e}", "ERROR")
        return []


# =========================================================================
# STEP 2: LLM ENTITY EXTRACTION VIA LITELLM
# =========================================================================

def extract_entities(sector, title, content):
    """
    Call LiteLLM S7 for entity extraction.
    Returns (entities_list, error_string).
    """
    if not content or len(content.strip()) < 30:
        return [], "content too short for extraction"

    prompt = build_extraction_prompt(sector, title, content)
    payload = json.dumps(prompt, ensure_ascii=False).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}",
    }

    status, body, err = http_request(
        LITELLM_CHAT_URL, data=payload, headers=headers,
        method="POST", timeout=LLM_TIMEOUT,
    )

    if err:
        return [], f"LiteLLM request failed: {err}"

    if status != 200:
        err_text = body.decode("utf-8", errors="replace")[:200] if body else "empty"
        return [], f"LiteLLM HTTP {status}: {err_text}"

    # Parse LLM response
    try:
        result = json.loads(body.decode("utf-8"))
        content_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return [], f"LiteLLM JSON parse error: {e}"

    if not content_text:
        return [], "LiteLLM returned empty content"

    # Extract JSON array from response (handle markdown code blocks, etc.)
    entities = _parse_entities_json(content_text)
    return entities, None


def _parse_entities_json(text):
    """Parse entity JSON from LLM response, handling various formats."""
    # Strip markdown code blocks
    text = text.strip()
    if text.startswith("```"):
        # Remove ```json ... ``` wrapper
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct JSON array parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return _validate_entities(parsed)
        if isinstance(parsed, dict) and "entities" in parsed:
            return _validate_entities(parsed["entities"])
        return []
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in text
    match = re.search(r'\[[\s\S]*?\]', text)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return _validate_entities(parsed)
        except json.JSONDecodeError:
            pass

    # Try to find JSON object with entities key
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict) and "entities" in parsed:
                return _validate_entities(parsed["entities"])
        except json.JSONDecodeError:
            pass

    return []


def _validate_entities(entities):
    """Validate and clean entity list."""
    valid = []
    for e in entities:
        if not isinstance(e, dict):
            continue
        name = (e.get("name") or "").strip()
        etype = (e.get("type") or "Concept").strip()
        desc = (e.get("description") or "").strip()

        if not name or len(name) < 2 or len(name) > 200:
            continue

        valid.append({
            "name": name,
            "type": etype,
            "description": desc[:500],
        })

    return valid[:MAX_ENTITIES_PER_DOC]


# =========================================================================
# STEP 3: STORE ENTITIES IN NEO4J
# =========================================================================

def store_in_neo4j(doc_id, doc_title, sector, entities):
    """
    Store document + entities in Neo4j via Bolt driver.
    Uses doc_id (Supabase primary key) as the document node identifier.
    Returns (success, entity_count, error_string).
    """
    if not NEO4J_PASSWORD:
        return False, 0, "NEO4J_PASSWORD not set"

    try:
        from neo4j import GraphDatabase
    except ImportError:
        return False, 0, "neo4j Python driver not installed"

    driver = None
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

        with driver.session() as session:
            # Create/update the SectorDocument node (keyed by Supabase id)
            session.run(
                """
                MERGE (d:SectorDocument {id: $doc_id})
                SET d.title = $title,
                    d.sector = $sector,
                    d.enriched = true,
                    d.enrichment_ts = datetime(),
                    d.entity_count = $entity_count
                """,
                doc_id=doc_id,
                title=(doc_title or "")[:200],
                sector=sector,
                entity_count=len(entities),
            )

            # Create entities and link them
            stored = 0
            for ent in entities:
                name = ent.get("name", "")
                etype = ent.get("type", "Concept")
                desc = ent.get("description", "")

                if not name:
                    continue

                session.run(
                    """
                    MERGE (e:Entity {name: $name, type: $type})
                    SET e.description = $description,
                        e.sector = $sector,
                        e.updated_at = datetime()

                    WITH e
                    MATCH (d:SectorDocument {id: $doc_id})
                    MERGE (d)-[:MENTIONS]->(e)
                    """,
                    name=name,
                    type=etype,
                    description=desc,
                    sector=sector,
                    doc_id=doc_id,
                )
                stored += 1

        return True, stored, None

    except Exception as e:
        return False, 0, f"Neo4j error: {type(e).__name__}: {str(e)[:200]}"
    finally:
        if driver:
            try:
                driver.close()
            except Exception:
                pass


# =========================================================================
# STEP 4: UPDATE SUPABASE ENRICHMENT STATUS
# =========================================================================

def update_supabase_enrichment(doc_id, entity_count, entities_list, current_metadata=None, error=None):
    """
    Update Supabase document metadata JSONB with enrichment results.
    Merges new fields into existing metadata to preserve other data.

    Schema: sector_documents.metadata is JSONB containing:
      has_entities (bool), entity_count (int), enriched (string),
      entities (array of names), source, phase, etc.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # Start from current metadata or empty dict
    new_metadata = dict(current_metadata) if current_metadata else {}

    if error is None:
        # Successful enrichment
        new_metadata["has_entities"] = True
        new_metadata["enriched"] = "true"
        new_metadata["entity_count"] = entity_count
        new_metadata["enrichment_status"] = "done"
        new_metadata["enrichment_ts"] = ts
        new_metadata["enrichment_source"] = "pipeline-v5"
        if entities_list:
            new_metadata["entities"] = entities_list[:15]
    else:
        # Enrichment failed/skipped
        new_metadata["enrichment_status"] = "error"
        new_metadata["enrichment_error"] = str(error)[:500]
        new_metadata["enrichment_ts"] = ts

    # PATCH by id — update the metadata JSONB column
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?id=eq.{urllib.parse.quote(str(doc_id))}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    update_data = {"metadata": new_metadata}
    payload = json.dumps(update_data, ensure_ascii=False).encode("utf-8")
    status, body, err = http_request(url, data=payload, headers=headers,
                                      method="PATCH", timeout=SUPABASE_TIMEOUT)

    if err:
        log(f"  Supabase update failed for doc {doc_id}: {err}", "WARN")
        return False

    if status not in (200, 204):
        body_str = body.decode("utf-8", errors="replace")[:200] if body else "empty"
        log(f"  Supabase update HTTP {status} for doc {doc_id}: {body_str}", "WARN")
        return False

    return True


# =========================================================================
# STEP 5 (OPTIONAL): NOTIFY N8N
# =========================================================================

def notify_n8n(doc_id, sector, entity_count):
    """
    Optionally ping n8n webhook to signal enrichment complete.
    Non-blocking: failure here does not affect enrichment status.
    """
    webhook_url = f"{N8N_HOST}/webhook/enrichment-complete"
    payload = json.dumps({
        "doc_id": doc_id,
        "sector": sector,
        "entity_count": entity_count,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "source": "enrichment-pipeline-v5",
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    try:
        status, _, err = http_request(webhook_url, data=payload, headers=headers,
                                       method="POST", timeout=10)
        if status in (200, 201, 202):
            return True
    except Exception:
        pass

    return False


# =========================================================================
# STATS MANAGEMENT
# =========================================================================

def load_stats():
    """Load enrichment stats from file."""
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "total_enriched": 0,
        "total_entities_created": 0,
        "total_errors": 0,
        "total_skipped": 0,
        "total_cycles": 0,
        "by_sector": {},
        "last_cycle": None,
        "consecutive_empty": 0,
    }


def save_stats(stats):
    """Save enrichment stats to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stats["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = str(STATS_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, str(STATS_FILE))


def print_stats(stats):
    """Print enrichment stats."""
    print(f"\n{'=' * 60}", flush=True)
    print(f"  ENRICHMENT PIPELINE V5.0 — STATS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Total enriched:   {stats['total_enriched']}", flush=True)
    print(f"  Total entities:   {stats['total_entities_created']}", flush=True)
    print(f"  Total errors:     {stats['total_errors']}", flush=True)
    print(f"  Total skipped:    {stats['total_skipped']}", flush=True)
    print(f"  Total cycles:     {stats['total_cycles']}", flush=True)
    print(f"  Created:          {stats.get('created', '?')}", flush=True)
    print(f"  Last updated:     {stats.get('last_updated', '?')}", flush=True)

    if stats.get("by_sector"):
        print(f"\n  By sector:", flush=True)
        for sector, s in stats["by_sector"].items():
            print(f"    {sector:12s}  enriched={s.get('enriched', 0):4d}  "
                  f"entities={s.get('entities', 0):5d}  "
                  f"errors={s.get('errors', 0):3d}", flush=True)

    if stats.get("last_cycle"):
        lc = stats["last_cycle"]
        print(f"\n  Last cycle:", flush=True)
        print(f"    Time:       {lc.get('started', '?')}", flush=True)
        print(f"    Processed:  {lc.get('processed', 0)}", flush=True)
        print(f"    Enriched:   {lc.get('enriched', 0)}", flush=True)
        print(f"    Entities:   {lc.get('entities_created', 0)}", flush=True)
        print(f"    Duration:   {lc.get('elapsed_s', 0):.1f}s", flush=True)

    print(f"{'=' * 60}\n", flush=True)


# =========================================================================
# ENRICHMENT CYCLE
# =========================================================================

def enrich_one_document(doc):
    """
    Enrich a single document. Full pipeline:
    LLM extraction -> Neo4j storage -> Supabase update -> n8n notification.

    Returns dict with enrichment results.
    """
    doc_id = doc.get("id")
    sector = doc.get("sector") or "finance"
    metadata = doc.get("metadata") or {}

    # sector_documents uses question/answer/context — concatenate for richer extraction
    question = doc.get("question") or ""
    answer = doc.get("answer") or ""
    ctx = doc.get("context") or ""
    title = question[:100]
    content = f"Question: {question}\nAnswer: {answer}\nContext: {ctx}".strip()

    result = {
        "doc_id": doc_id,
        "sector": sector,
        "title": title[:60],
        "status": "pending",
        "entity_count": 0,
        "neo4j_ok": False,
        "supabase_ok": False,
        "error": None,
    }

    # Check content quality
    if not content or len(content.strip()) < 30:
        result["status"] = "skipped"
        result["error"] = f"content too short ({len(content or '')} chars)"
        # Mark in Supabase so we don't retry endlessly
        update_supabase_enrichment(doc_id, 0, None,
                                    current_metadata=metadata,
                                    error="content_too_short")
        return result

    # Step 2: LLM entity extraction
    log(f"  Extracting entities ({sector})...", "INFO")
    entities, llm_err = extract_entities(sector, title, content)

    if llm_err:
        log(f"  LLM error: {llm_err}", "ERROR")
        result["status"] = "llm_error"
        result["error"] = llm_err
        update_supabase_enrichment(doc_id, 0, None,
                                    current_metadata=metadata,
                                    error=llm_err)
        return result

    result["entity_count"] = len(entities)

    if not entities:
        log(f"  No entities found", "SKIP")
        result["status"] = "no_entities"
        # Mark as processed with 0 entities so we don't retry
        update_supabase_enrichment(doc_id, 0, [],
                                    current_metadata=metadata)
        return result

    # Build entity name list for Supabase metadata
    entity_names = [e["name"] for e in entities[:15]]

    # Step 3: Store in Neo4j (keyed by Supabase doc id)
    log(f"  Storing {len(entities)} entities in Neo4j...", "INFO")
    neo4j_ok, stored_count, neo4j_err = store_in_neo4j(
        doc_id, title, sector, entities
    )
    result["neo4j_ok"] = neo4j_ok

    if neo4j_err:
        log(f"  Neo4j error: {neo4j_err}", "WARN")
        # Continue — Supabase update is still useful
    else:
        log(f"  Neo4j OK: {stored_count} entities stored", "OK")

    # Step 4: Update Supabase metadata
    log(f"  Updating Supabase metadata...", "INFO")
    supabase_ok = update_supabase_enrichment(
        doc_id, len(entities), entity_names,
        current_metadata=metadata,
    )
    result["supabase_ok"] = supabase_ok

    if supabase_ok:
        log(f"  Supabase OK", "OK")
    else:
        log(f"  Supabase update failed", "WARN")

    # Step 5: Optional n8n notification (fire-and-forget)
    notify_n8n(doc_id, sector, len(entities))

    result["status"] = "enriched"
    return result


def run_cycle(batch_size, sector_filter, stats):
    """
    Run one enrichment cycle:
    1. Fetch un-enriched docs from Supabase
    2. Enrich each one
    3. Update stats
    """
    global _shutdown_requested

    cycle_start = time.time()
    cycle_num = stats["total_cycles"] + 1

    print(f"\n{'=' * 60}", flush=True)
    print(f"  ENRICHMENT CYCLE #{cycle_num}", flush=True)
    print(f"  Batch: {batch_size} | Sector: {sector_filter or 'all'}", flush=True)
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC", flush=True)
    print(f"{'=' * 60}", flush=True)

    # Step 1: Fetch un-enriched documents
    log(f"Querying Supabase for un-enriched documents...", "INFO")
    docs = fetch_unenriched_documents(batch_size, sector=sector_filter)

    if not docs:
        log("No un-enriched documents found", "SKIP")
        stats["consecutive_empty"] += 1
        stats["total_cycles"] = cycle_num
        stats["last_cycle"] = {
            "started": datetime.now(timezone.utc).isoformat(),
            "processed": 0,
            "enriched": 0,
            "entities_created": 0,
            "elapsed_s": round(time.time() - cycle_start, 1),
        }
        save_stats(stats)
        return stats

    log(f"Found {len(docs)} documents to enrich", "OK")
    stats["consecutive_empty"] = 0

    # Process each document
    cycle_enriched = 0
    cycle_entities = 0
    cycle_errors = 0
    cycle_skipped = 0

    for i, doc in enumerate(docs):
        if _shutdown_requested:
            log("Shutdown requested — stopping batch", "WARN")
            break

        doc_id = doc.get("id", "?")
        question = (doc.get("question") or "untitled")[:50]
        sector = doc.get("sector") or "?"

        print(f"\n--- [{i + 1}/{len(docs)}] id={doc_id} sector={sector} ---", flush=True)
        log(f"Processing: {question}", "INFO")

        try:
            result = enrich_one_document(doc)
        except Exception as e:
            log(f"  EXCEPTION: {e}", "ERROR")
            traceback.print_exc()
            result = {"status": "exception", "error": str(e), "entity_count": 0, "sector": sector}

        # Update cycle counters
        if result["status"] == "enriched":
            cycle_enriched += 1
            cycle_entities += result.get("entity_count", 0)
        elif result["status"] in ("skipped", "no_entities"):
            cycle_skipped += 1
        else:
            cycle_errors += 1

        # Update per-sector stats
        s = result.get("sector", "unknown")
        if s not in stats["by_sector"]:
            stats["by_sector"][s] = {"enriched": 0, "entities": 0, "errors": 0, "skipped": 0}

        if result["status"] == "enriched":
            stats["by_sector"][s]["enriched"] += 1
            stats["by_sector"][s]["entities"] += result.get("entity_count", 0)
        elif result["status"] in ("skipped", "no_entities"):
            stats["by_sector"][s]["skipped"] += 1
        else:
            stats["by_sector"][s]["errors"] += 1

        # Delay between documents
        if i < len(docs) - 1:
            time.sleep(INTER_DOC_DELAY)

    # Update global stats
    stats["total_enriched"] += cycle_enriched
    stats["total_entities_created"] += cycle_entities
    stats["total_errors"] += cycle_errors
    stats["total_skipped"] += cycle_skipped
    stats["total_cycles"] = cycle_num

    elapsed = time.time() - cycle_start
    stats["last_cycle"] = {
        "started": datetime.now(timezone.utc).isoformat(),
        "processed": len(docs),
        "enriched": cycle_enriched,
        "entities_created": cycle_entities,
        "errors": cycle_errors,
        "skipped": cycle_skipped,
        "elapsed_s": round(elapsed, 1),
    }

    save_stats(stats)

    # Print cycle summary
    print(f"\n{'=' * 60}", flush=True)
    print(f"  CYCLE #{cycle_num} COMPLETE ({elapsed:.1f}s)", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Processed:  {len(docs)}", flush=True)
    print(f"  Enriched:   {cycle_enriched}", flush=True)
    print(f"  Entities:   {cycle_entities}", flush=True)
    print(f"  Skipped:    {cycle_skipped}", flush=True)
    print(f"  Errors:     {cycle_errors}", flush=True)
    print(f"  TOTALS:     {stats['total_enriched']} enriched, "
          f"{stats['total_entities_created']} entities, "
          f"{stats['total_errors']} errors", flush=True)
    print(f"{'=' * 60}", flush=True)

    return stats


# =========================================================================
# MAIN / CLI
# =========================================================================

def main():
    global _shutdown_requested
    parser = argparse.ArgumentParser(
        description="Enrichment Pipeline V5.0 — Standalone document enrichment daemon"
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run as daemon with continuous cycles"
    )
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL,
        help=f"Cycle interval in seconds (default: {DEFAULT_INTERVAL})"
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Documents per cycle (default: {DEFAULT_BATCH_SIZE})"
    )
    parser.add_argument(
        "--sector", choices=SECTORS + ["all"], default=None,
        help="Filter by sector (default: all sectors)"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show enrichment stats and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Query Supabase but don't enrich (show what would be processed)"
    )
    args = parser.parse_args()

    # Status mode
    if args.status:
        stats = load_stats()
        print_stats(stats)
        return

    # Validate config
    if not SUPABASE_KEY:
        log("FATAL: SUPABASE_API_KEY not set. Run: source .env.local", "ERROR")
        sys.exit(1)

    if not NEO4J_PASSWORD:
        log("WARN: NEO4J_PASSWORD not set — Neo4j storage will be skipped", "WARN")

    # Create data dir and save PID
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    sector_filter = args.sector if args.sector and args.sector != "all" else None

    # Dry run mode
    if args.dry_run:
        log("DRY RUN — querying Supabase for un-enriched documents...", "INFO")
        docs = fetch_unenriched_documents(args.batch_size, sector=sector_filter)
        if not docs:
            log("No un-enriched documents found", "SKIP")
        else:
            print(f"\nFound {len(docs)} un-enriched documents:", flush=True)
            for i, doc in enumerate(docs):
                question = (doc.get("question") or "untitled")[:60]
                sector = doc.get("sector") or "?"
                context_len = len(doc.get("context") or "")
                meta = doc.get("metadata") or {}
                has_entities = meta.get("has_entities", "null")
                entity_count = meta.get("entity_count", "null")
                print(f"  [{i + 1}] id={doc.get('id')} sector={sector} "
                      f"has_entities={has_entities} entity_count={entity_count} "
                      f"context={context_len}chars — {question}", flush=True)
        return

    # Print startup banner
    print(f"\n{'=' * 60}", flush=True)
    print(f"  ENRICHMENT PIPELINE V5.0", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"  Mode:       {'Daemon' if args.daemon else 'One-shot'}", flush=True)
    print(f"  Interval:   {args.interval}s ({args.interval / 60:.0f}min)", flush=True)
    print(f"  Batch:      {args.batch_size} docs/cycle", flush=True)
    print(f"  Sector:     {sector_filter or 'all'}", flush=True)
    print(f"  LiteLLM:    {LITELLM_CHAT_URL}", flush=True)
    print(f"  Neo4j:      {NEO4J_URI}", flush=True)
    print(f"  Supabase:   {SUPABASE_URL}", flush=True)
    print(f"  Log:        {LOG_FILE}", flush=True)
    print(f"  PID:        {os.getpid()}", flush=True)
    print(f"  Started:    {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(f"{'=' * 60}\n", flush=True)

    stats = load_stats()

    if args.daemon:
        log(f"Starting enrichment daemon — {args.interval}s cycles, "
            f"batch={args.batch_size}", "INFO")

        while not _shutdown_requested:
            try:
                stats = run_cycle(args.batch_size, sector_filter, stats)
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
                traceback.print_exc()

            if _shutdown_requested:
                break

            # Adaptive backoff: if 3+ consecutive empty cycles, slow down
            if stats.get("consecutive_empty", 0) >= 3:
                wait_time = min(args.interval * 2, 1800)
                log(f"No documents for 3+ cycles — sleeping {wait_time}s "
                    f"(2x interval, max 30min)", "INFO")
            else:
                wait_time = args.interval

            log(f"Next cycle in {wait_time}s ({wait_time / 60:.1f}min)...", "INFO")

            try:
                # Sleep in small increments to respond to shutdown quickly
                sleep_end = time.time() + wait_time
                while time.time() < sleep_end and not _shutdown_requested:
                    time.sleep(min(5, sleep_end - time.time()))
            except KeyboardInterrupt:
                _shutdown_requested = True

        log("Enrichment daemon stopped gracefully", "OK")
    else:
        # One-shot mode
        stats = run_cycle(args.batch_size, sector_filter, stats)

    # Clean up PID
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    log("Enrichment Pipeline V5.0 finished", "OK")


if __name__ == "__main__":
    main()
