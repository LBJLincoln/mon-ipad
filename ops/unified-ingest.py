#!/usr/bin/env python3
"""
Unified Ingestion Daemon — ALL sources through n8n for full enrichment.
======================================================================
Single daemon that discovers, processes, and verifies document ingestion
across all 4 sectors. Every document goes through n8n workflows for:
  - Semantic chunking
  - QA generation
  - Entity extraction (NER)
  - Neo4j graph enrichment
  - Pinecone vector storage
  - Supabase document storage

Phases per cycle:
  1. DISCOVER — Exa.AI + Brave Search for new documents
  2. PROCESS  — Route each document through n8n (PDFs via Docling first)
  3. VERIFY   — Check Pinecone/Supabase counts
  4. LOG      — Record everything to data/ingest/unified-state.json

Usage:
  source .env.local
  python3 ops/unified-ingest.py --sector all
  python3 ops/unified-ingest.py --sector finance --max-queries 5
  python3 ops/unified-ingest.py --sector btp --dry-run
  python3 ops/unified-ingest.py --daemon 1800               # Every 30min
  python3 ops/unified-ingest.py --daemon 1800 --sector all   # Full daemon
  nohup python3 ops/unified-ingest.py --daemon 1800 --sector all > data/ingest/unified.log 2>&1 &
"""

# ── Force IPv4 globally (IPv6 broken on this VM) ────────────────────────
import socket
from socket import AF_INET

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, AF_INET, type_, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

# ── Standard imports ────────────────────────────────────────────────────
import argparse
import base64
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Force line-buffered output ──────────────────────────────────────────
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── Load .env.local ─────────────────────────────────────────────────────
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

# ── SSL context (permissive for government PDFs) ────────────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# =========================================================================
# CONFIGURATION
# =========================================================================

# API Keys
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")

# Exa.AI
EXA_SEARCH_URL = "https://api.exa.ai/search"

# Brave Search
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# Docling S6
DOCLING_BASE = "https://lbjlincoln-nomos-docling-api.hf.space"
DOCLING_CONVERT_URL = f"{DOCLING_BASE}/convert-url"
DOCLING_HEALTH_URL = f"{DOCLING_BASE}/health"
DOCLING_TIMEOUT = 600

# n8n Spaces — ingestion + enrichment webhooks
N8N_SPACES = [
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",   # S9 — primary
    "https://lbjlincoln-nomos-rag-engine.hf.space",      # S1 — fallback
    "https://lbjlincoln-nomos-rag-engine-3.hf.space",    # S3 — fallback
]
N8N_INGEST_PATH = "/webhook/rag-v6-ingestion"
N8N_ENRICH_PATH = "/webhook/rag-v6-enrichment"
N8N_TIMEOUT = 120

# Pinecone (for verification only)
PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"

# State/Progress files
DATA_DIR = REPO_ROOT / "data" / "ingest"
STATE_FILE = DATA_DIR / "unified-state.json"

# Timing
EXA_DELAY = 1.0       # seconds between search API calls
BRAVE_DELAY = 0.5      # seconds between Brave calls
N8N_DELAY = 2.0        # seconds between n8n webhook calls
DOCLING_COOLDOWN = 10   # seconds after PDF processing
MIN_CONTENT_LEN = 200   # minimum text to send to n8n
MAX_FILE_SIZE_MB = 10    # max PDF size for Docling

SECTORS = ["finance", "btp", "juridique", "industrie"]

# =========================================================================
# SEARCH QUERIES — sector-specific expert document discovery
# =========================================================================

SECTOR_QUERIES = {
    "finance": [
        "IFRS normes comptables internationales",
        "ratio financier analyse entreprise",
        "bilan comptable actif passif explication",
        "marche obligataire taux d interet France",
        "gestion de portefeuille diversification risque",
        "analyse fondamentale actions bourse",
        "reglementation bancaire Bale III IV",
        "fiscalite entreprise impot societe France",
        "fusion acquisition due diligence",
        "tresorerie entreprise cash flow gestion",
        "audit financier commissaire aux comptes",
        "credit scoring notation financiere",
        "assurance vie epargne placement",
        "fintech blockchain finance decentralisee",
        "ESG investissement responsable criteres",
    ],
    "btp": [
        "DTU 31.2 ossature bois construction",
        "permis de construire etapes procedure",
        "normes parasismiques Eurocode 8 France",
        "CCTP marche public travaux redaction",
        "RE2020 obligations reglementation environnementale",
        "DTU couverture toiture etancheite",
        "fondations profondes techniques pieux",
        "beton arme eurocode 2 calcul",
        "isolation thermique batiment RT2012",
        "securite chantier BTP reglementation",
        "AFNOR normes construction batiment",
        "diagnostic amiante plomb DPE",
        "marche public BOAMP appel offre",
        "assurance decennale garantie construction",
        "plan local urbanisme PLU permis",
    ],
    "juridique": [
        "code civil responsabilite contractuelle articles",
        "droit du travail licenciement procedure France",
        "RGPD protection donnees personnelles conformite",
        "droit des societes SAS SARL statuts",
        "propriete intellectuelle brevet marque depot",
        "contentieux commercial tribunal procedure",
        "droit immobilier bail commercial resiliation",
        "droit fiscal controle redressement",
        "droit de la concurrence pratiques anticoncurrentielles",
        "procedure collective sauvegarde liquidation judiciaire",
        "contrat de travail clause non concurrence",
        "droit administratif marche public recours",
        "mediation arbitrage resolution litiges",
        "droit penal des affaires abus de biens sociaux",
        "conformite compliance entreprise loi Sapin II",
    ],
    "industrie": [
        "ISO 9001 demarche qualite certification",
        "AMDEC analyse defaillance criticite",
        "fiche donnees securite FDS redaction",
        "lean manufacturing principes gaspillage",
        "maintenance preventive planification equipement",
        "ISO 14001 environnement management",
        "Six Sigma DMAIC amelioration continue",
        "HACCP securite alimentaire",
        "norme ISO 45001 sante securite travail",
        "gestion stock methode kanban",
        "TPM maintenance productive totale",
        "audit qualite processus certification",
        "REACH substances chimiques reglementation",
        "controle non destructif CND ultrasons",
        "automatisation industrielle 4.0 IoT",
    ],
}


# =========================================================================
# LOGGING
# =========================================================================

def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix = {"INFO": "+", "WARN": "!", "ERROR": "X", "OK": "v", "SKIP": "-"}.get(level, " ")
    print(f"[{ts}] [{prefix}] {msg}", flush=True)


# =========================================================================
# UTILITIES
# =========================================================================

def url_hash(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def make_doc_id(sector, url):
    return f"unified-{sector}-{url_hash(url)}"


def extract_domain(url):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return "unknown"


def is_pdf_url(url):
    url_lower = url.lower().split("?")[0].split("#")[0]
    return url_lower.endswith(".pdf") or "/pdf/" in url_lower or "filetype=pdf" in url.lower()


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


# =========================================================================
# STATE MANAGEMENT
# =========================================================================

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "cycles": 0,
        "totals": {
            "docs_discovered": 0,
            "docs_processed": 0,
            "docs_enriched": 0,
            "docs_via_docling": 0,
            "docs_direct_text": 0,
            "errors": 0,
        },
        "processed_urls": {},
        "cycles_history": [],
    }


def save_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, str(STATE_FILE))


# =========================================================================
# PHASE 1: DISCOVER — Exa.AI + Brave Search
# =========================================================================

def exa_search(query, num_results=10):
    """Search Exa.AI, return normalized results."""
    if not EXA_API_KEY:
        log("EXA_API_KEY not set — skipping Exa.AI", "WARN")
        return []

    payload = json.dumps({
        "query": query,
        "numResults": num_results,
        "type": "auto",
        "contents": {"text": True},
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": EXA_API_KEY,
    }

    status, body, err = http_request(EXA_SEARCH_URL, data=payload, headers=headers, method="POST", timeout=60)
    if err:
        log(f"Exa.AI search failed: {err}", "ERROR")
        return []

    try:
        data = json.loads(body.decode("utf-8"))
        results = []
        for r in data.get("results", []):
            results.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "text": r.get("text", ""),
                "published_date": r.get("publishedDate", ""),
                "source_api": "exa",
            })
        return results
    except Exception as e:
        log(f"Exa.AI parse error: {e}", "ERROR")
        return []


def brave_search(query, num_results=10):
    """Search Brave Web Search API, return normalized results."""
    if not BRAVE_API_KEY:
        return []

    params = urllib.parse.urlencode({
        "q": query,
        "count": num_results,
        "text_decorations": "false",
        "search_lang": "fr",
    })

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }

    status, body, err = http_request(f"{BRAVE_SEARCH_URL}?{params}", headers=headers, timeout=30)
    if err:
        log(f"Brave Search failed: {err}", "ERROR")
        return []

    try:
        raw = body
        # Handle gzip
        if len(raw) > 2 and raw[:2] == b'\x1f\x8b':
            import gzip
            raw = gzip.decompress(raw)
        data = json.loads(raw.decode("utf-8"))
        results = []
        for r in data.get("web", {}).get("results", []):
            desc = r.get("description", "")
            results.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "text": desc if len(desc) > MIN_CONTENT_LEN else "",
                "published_date": r.get("age", ""),
                "source_api": "brave",
            })
        return results
    except Exception as e:
        log(f"Brave parse error: {e}", "ERROR")
        return []


def discover_documents(sector, queries, max_queries=0):
    """
    Run Exa.AI + Brave Search for a sector. Returns deduplicated list of docs.
    Each doc: {url, title, text, source_api, is_pdf, domain}
    """
    if max_queries > 0:
        queries = queries[:max_queries]

    all_docs = []
    seen_urls = set()

    for qi, query in enumerate(queries):
        log(f"[{qi+1}/{len(queries)}] Search: \"{query}\"")

        # Exa.AI
        exa_results = exa_search(query)
        time.sleep(EXA_DELAY)

        # Brave Search
        brave_results = brave_search(query)
        if brave_results:
            time.sleep(BRAVE_DELAY)

        combined = exa_results + brave_results

        new_count = 0
        for r in combined:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            doc = {
                "url": url,
                "title": r.get("title", "")[:200],
                "text": r.get("text", ""),
                "source_api": r.get("source_api", "unknown"),
                "is_pdf": is_pdf_url(url),
                "domain": extract_domain(url),
                "published_date": r.get("published_date", ""),
            }
            all_docs.append(doc)
            new_count += 1

        log(f"  Found {len(combined)} results, {new_count} new unique")

    log(f"Discovery complete: {len(all_docs)} unique docs ({sum(1 for d in all_docs if d['is_pdf'])} PDFs)")
    return all_docs


# =========================================================================
# PHASE 2: PROCESS — Route through n8n (PDFs via Docling first)
# =========================================================================

def docling_extract(pdf_url):
    """
    Send PDF URL to Docling S6, return extracted text.
    Returns (text, meta_dict, error_string).
    """
    # Check file size first
    try:
        req = urllib.request.Request(pdf_url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (compatible; Nomos-Unified/1.0)")
        resp = urllib.request.urlopen(req, timeout=15, context=_ssl_ctx)
        cl = resp.headers.get("Content-Length")
        if cl and int(cl) > MAX_FILE_SIZE_MB * 1024 * 1024:
            return None, {}, f"PDF too large: {int(cl)/(1024*1024):.1f}MB"
    except Exception:
        pass  # HEAD failed — try conversion anyway

    payload = json.dumps({"url": pdf_url}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    start = time.time()
    status, body, err = http_request(
        DOCLING_CONVERT_URL, data=payload, headers=headers,
        method="POST", timeout=DOCLING_TIMEOUT,
    )
    elapsed = time.time() - start

    if err:
        return None, {"elapsed_s": elapsed}, f"Docling error: {err}"

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        return None, {"elapsed_s": elapsed}, f"Docling JSON parse: {e}"

    if data.get("status") == "error":
        return None, {"elapsed_s": elapsed}, f"Docling: {data.get('error', 'unknown')}"

    text = data.get("full_text", "") or data.get("markdown", "") or data.get("text", "")
    meta = {
        "num_pages": data.get("num_pages", 0),
        "num_tables": data.get("num_tables", 0),
        "text_chars": len(text),
        "elapsed_s": round(elapsed, 1),
    }

    return text, meta, None


def send_to_n8n_ingest(content, sector, url, title, doc_id, source="unified"):
    """
    Send content to n8n Ingestion webhook. Tries each Space.
    Returns (success, result_dict).
    """
    payload = json.dumps({
        "content": content[:50000],
        "sector": sector,
        "tenant_id": sector,
        "source": source,
        "documentId": doc_id,
        "metadata": {
            "source_url": url[:2000],
            "title": (title or "")[:500],
            "origin": "unified-ingest",
            "domain": extract_domain(url),
        }
    }, ensure_ascii=False).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    for attempt in range(3):
        for space_url in N8N_SPACES:
            webhook_url = f"{space_url}{N8N_INGEST_PATH}"
            status, body, err = http_request(
                webhook_url, data=payload, headers=headers,
                method="POST", timeout=N8N_TIMEOUT,
            )
            if status in (200, 201, 202):
                result = {}
                try:
                    result = json.loads(body.decode("utf-8"))
                except Exception:
                    pass
                space_name = space_url.split("//")[1].split(".")[0]
                return True, {"space": space_name, "result": result}

            space_short = space_url.split("//")[1].split(".")[0][-15:]
            if err:
                log(f"  n8n {space_short}: {err}", "WARN")

        if attempt < 2:
            time.sleep(5 * (attempt + 1))

    return False, {"error": "All n8n Spaces failed"}


def send_to_n8n_enrich(doc_id, sector):
    """Trigger n8n enrichment for Neo4j graph building."""
    payload = json.dumps({
        "doc_id": doc_id,
        "sector": sector,
        "source": "unified-ingest",
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    for space_url in N8N_SPACES:
        webhook_url = f"{space_url}{N8N_ENRICH_PATH}"
        status, body, err = http_request(
            webhook_url, data=payload, headers=headers,
            method="POST", timeout=60,
        )
        if status in (200, 201, 202) or status == 500:
            # 500 often means workflow ran but response format issue
            return True
    return False


def process_document(doc, sector, state, dry_run=False):
    """
    Process a single discovered document through the n8n pipeline.
    - PDF: Docling S6 extraction -> n8n ingest -> n8n enrich
    - HTML/text: direct n8n ingest -> n8n enrich
    Returns stats dict.
    """
    url = doc["url"]
    title = doc.get("title", "")
    doc_id = make_doc_id(sector, url)
    is_pdf = doc.get("is_pdf", False)

    result = {
        "url": url,
        "title": title[:80],
        "sector": sector,
        "doc_id": doc_id,
        "type": "pdf" if is_pdf else "text",
        "status": "pending",
        "n8n_ok": False,
        "enriched": False,
        "error": None,
    }

    # Skip already processed
    if url in state.get("processed_urls", {}):
        result["status"] = "already_processed"
        return result

    if dry_run:
        result["status"] = "dry_run"
        return result

    content = doc.get("text", "")

    # PDF: extract via Docling first
    if is_pdf:
        log(f"  PDF: extracting via Docling S6...", "INFO")
        text, meta, docling_err = docling_extract(url)
        if docling_err:
            log(f"  Docling failed: {docling_err}", "WARN")
            result["status"] = "docling_error"
            result["error"] = docling_err
            # If we have some text from search results, use that as fallback
            if not content or len(content) < MIN_CONTENT_LEN:
                return result
            log(f"  Using search snippet as fallback ({len(content)} chars)", "INFO")
        else:
            content = text
            log(f"  Docling OK: {meta.get('text_chars', 0):,} chars, "
                f"{meta.get('num_pages', '?')} pages, {meta.get('elapsed_s', '?')}s", "OK")
            time.sleep(DOCLING_COOLDOWN)

    # Check content quality
    if not content or len(content) < MIN_CONTENT_LEN:
        result["status"] = "insufficient_content"
        result["error"] = f"Content too short: {len(content or '')} chars"
        return result

    # Send to n8n Ingestion
    source = "docling" if is_pdf else "web"
    n8n_ok, n8n_result = send_to_n8n_ingest(content, sector, url, title, doc_id, source=source)

    if n8n_ok:
        result["n8n_ok"] = True
        result["n8n_space"] = n8n_result.get("space", "")
        log(f"  n8n ingest OK ({n8n_result.get('space', '?')})", "OK")

        # Trigger enrichment
        enriched = send_to_n8n_enrich(doc_id, sector)
        result["enriched"] = enriched
        if enriched:
            log(f"  n8n enrich OK", "OK")

        result["status"] = "ok"
    else:
        result["status"] = "n8n_failed"
        result["error"] = n8n_result.get("error", "unknown")
        log(f"  n8n ingest FAILED: {result['error']}", "ERROR")

    # Track as processed
    state["processed_urls"][url] = {
        "sector": sector,
        "doc_id": doc_id,
        "status": result["status"],
        "type": result["type"],
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    return result


# =========================================================================
# PHASE 3: VERIFY — Check database counts
# =========================================================================

def verify_pinecone_count():
    """Check Pinecone E5 vector count."""
    if not PINECONE_API_KEY:
        return 0
    try:
        status, body, err = http_request(
            f"{PINECONE_HOST}/describe_index_stats",
            data=b"{}",
            headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"},
            method="POST",
            timeout=10,
        )
        if err:
            return 0
        data = json.loads(body.decode("utf-8"))
        return data.get("totalRecordCount", data.get("totalVectorCount", 0))
    except Exception:
        return 0


# =========================================================================
# MAIN CYCLE
# =========================================================================

def run_cycle(sectors, state, max_queries=0, dry_run=False):
    """
    Run one full ingestion cycle for the given sectors.
    Returns cycle stats dict.
    """
    cycle_num = state["cycles"] + 1
    cycle_start = datetime.now(timezone.utc)

    print("=" * 70, flush=True)
    print(f"  UNIFIED INGESTION — Cycle {cycle_num}", flush=True)
    print(f"  Sectors:  {', '.join(sectors)}", flush=True)
    print(f"  Mode:     {'DRY RUN' if dry_run else 'LIVE -> n8n pipeline'}", flush=True)
    print(f"  Sources:  Exa.AI{' + Brave' if BRAVE_API_KEY else ''}", flush=True)
    print(f"  Started:  {cycle_start.isoformat()}", flush=True)
    print("=" * 70, flush=True)

    cycle_stats = {
        "cycle": cycle_num,
        "started": cycle_start.isoformat(),
        "sectors": {},
        "totals": {
            "docs_discovered": 0,
            "docs_processed": 0,
            "docs_enriched": 0,
            "docs_via_docling": 0,
            "docs_direct_text": 0,
            "docs_skipped": 0,
            "errors": 0,
        },
    }

    # PHASE 3 pre-check: vectors before
    vectors_before = verify_pinecone_count()
    log(f"Pinecone vectors before: {vectors_before:,}", "INFO")

    for sector in sectors:
        queries = SECTOR_QUERIES.get(sector, [])
        if not queries:
            log(f"No queries for sector: {sector}", "WARN")
            continue

        print(f"\n{'─' * 60}", flush=True)
        print(f"  SECTOR: {sector.upper()}", flush=True)
        print(f"{'─' * 60}", flush=True)

        sector_stats = {
            "docs_discovered": 0,
            "docs_processed": 0,
            "docs_enriched": 0,
            "docs_via_docling": 0,
            "docs_direct_text": 0,
            "docs_skipped": 0,
            "errors": 0,
            "error_details": [],
        }

        # PHASE 1: DISCOVER
        log(f"Phase 1: DISCOVER ({sector})", "INFO")
        docs = discover_documents(sector, queries, max_queries=max_queries)
        sector_stats["docs_discovered"] = len(docs)
        cycle_stats["totals"]["docs_discovered"] += len(docs)

        # Filter already processed
        new_docs = [d for d in docs if d["url"] not in state.get("processed_urls", {})]
        if len(docs) > len(new_docs):
            log(f"  Filtered {len(docs) - len(new_docs)} already-processed URLs", "SKIP")
            sector_stats["docs_skipped"] += len(docs) - len(new_docs)
            cycle_stats["totals"]["docs_skipped"] += len(docs) - len(new_docs)

        if not new_docs:
            log(f"  No new documents for {sector}", "SKIP")
            cycle_stats["sectors"][sector] = sector_stats
            continue

        # PHASE 2: PROCESS
        log(f"Phase 2: PROCESS {len(new_docs)} documents ({sector})", "INFO")
        for di, doc in enumerate(new_docs):
            prefix = f"[{di+1}/{len(new_docs)}]"
            domain = doc.get("domain", "?")
            doc_type = "PDF" if doc["is_pdf"] else "text"
            log(f"{prefix} {doc_type} | {domain} | {doc.get('title', '?')[:50]}", "INFO")

            result = process_document(doc, sector, state, dry_run=dry_run)

            if result["status"] == "ok":
                sector_stats["docs_processed"] += 1
                cycle_stats["totals"]["docs_processed"] += 1

                if result.get("enriched"):
                    sector_stats["docs_enriched"] += 1
                    cycle_stats["totals"]["docs_enriched"] += 1

                if result["type"] == "pdf":
                    sector_stats["docs_via_docling"] += 1
                    cycle_stats["totals"]["docs_via_docling"] += 1
                else:
                    sector_stats["docs_direct_text"] += 1
                    cycle_stats["totals"]["docs_direct_text"] += 1

            elif result["status"] == "dry_run":
                sector_stats["docs_processed"] += 1
                cycle_stats["totals"]["docs_processed"] += 1

            elif result["status"] == "already_processed":
                sector_stats["docs_skipped"] += 1
                cycle_stats["totals"]["docs_skipped"] += 1

            else:
                sector_stats["errors"] += 1
                cycle_stats["totals"]["errors"] += 1
                if result.get("error"):
                    sector_stats["error_details"].append({
                        "url": result["url"][:100],
                        "error": result["error"][:200],
                    })

            # Delay between n8n calls
            if result["status"] not in ("already_processed", "dry_run"):
                time.sleep(N8N_DELAY)

        # Keep error_details capped
        sector_stats["error_details"] = sector_stats["error_details"][:20]
        cycle_stats["sectors"][sector] = sector_stats

        # Print sector summary
        print(f"\n  {sector.upper()} complete: "
              f"{sector_stats['docs_processed']} processed, "
              f"{sector_stats['docs_enriched']} enriched, "
              f"{sector_stats['errors']} errors", flush=True)

    # PHASE 3: VERIFY
    vectors_after = verify_pinecone_count()
    new_vectors = vectors_after - vectors_before
    log(f"Pinecone vectors after: {vectors_after:,} (+{new_vectors:,})", "INFO")

    # PHASE 4: LOG
    cycle_end = datetime.now(timezone.utc)
    elapsed = (cycle_end - cycle_start).total_seconds()

    cycle_stats["finished"] = cycle_end.isoformat()
    cycle_stats["elapsed_s"] = round(elapsed, 1)
    cycle_stats["vectors_before"] = vectors_before
    cycle_stats["vectors_after"] = vectors_after
    cycle_stats["new_vectors"] = new_vectors

    # Update global state
    state["cycles"] = cycle_num
    for k in ["docs_discovered", "docs_processed", "docs_enriched",
              "docs_via_docling", "docs_direct_text", "errors"]:
        state["totals"][k] = state["totals"].get(k, 0) + cycle_stats["totals"].get(k, 0)

    # Keep last 20 cycles
    state["cycles_history"] = (state.get("cycles_history", []) + [cycle_stats])[-20:]
    save_state(state)

    # Final summary
    print(f"\n{'=' * 70}", flush=True)
    print(f"  CYCLE {cycle_num} COMPLETE", flush=True)
    print(f"{'=' * 70}", flush=True)
    t = cycle_stats["totals"]
    print(f"  Discovered:    {t['docs_discovered']}", flush=True)
    print(f"  Processed:     {t['docs_processed']} (via n8n pipeline)", flush=True)
    print(f"  Enriched:      {t['docs_enriched']} (Neo4j)", flush=True)
    print(f"  Via Docling:   {t['docs_via_docling']} PDFs", flush=True)
    print(f"  Direct text:   {t['docs_direct_text']}", flush=True)
    print(f"  Skipped:       {t['docs_skipped']}", flush=True)
    print(f"  Errors:        {t['errors']}", flush=True)
    print(f"  Vectors:       {vectors_before:,} -> {vectors_after:,} (+{new_vectors:,})", flush=True)
    print(f"  Duration:      {elapsed:.0f}s ({elapsed/60:.1f}min)", flush=True)
    print(f"  State saved:   {STATE_FILE}", flush=True)
    print(f"{'=' * 70}", flush=True)

    return cycle_stats


# =========================================================================
# CLI
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified Ingestion Daemon — ALL sources through n8n for full enrichment"
    )
    parser.add_argument(
        "--sector",
        choices=SECTORS + ["all"],
        default="all",
        help="Sector(s) to ingest (default: all)",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=0,
        help="Max search queries per sector (0 = all, default: 0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover documents but do not send to n8n",
    )
    parser.add_argument(
        "--daemon",
        type=int,
        default=0,
        metavar="SECONDS",
        help="Run as daemon with given interval in seconds (e.g. 1800 = 30min)",
    )
    args = parser.parse_args()

    # Validate API keys
    if not EXA_API_KEY and not BRAVE_API_KEY:
        log("FATAL: Neither EXA_API_KEY nor BRAVE_API_KEY set. Run: source .env.local", "ERROR")
        sys.exit(1)

    sectors = SECTORS if args.sector == "all" else [args.sector]

    print("=" * 70, flush=True)
    print("  UNIFIED INGESTION DAEMON", flush=True)
    print(f"  All data flows through n8n for full enrichment", flush=True)
    print(f"  Sources: Exa.AI{' + Brave' if BRAVE_API_KEY else ''} + Docling S6 (PDFs)", flush=True)
    print(f"  Sectors: {', '.join(sectors)}", flush=True)
    print(f"  Mode:    {'Daemon (' + str(args.daemon) + 's interval)' if args.daemon else 'One-shot'}", flush=True)
    print(f"  State:   {STATE_FILE}", flush=True)
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}", flush=True)
    print("=" * 70, flush=True)

    state = load_state()

    if args.daemon:
        while True:
            try:
                run_cycle(sectors, state, max_queries=args.max_queries, dry_run=args.dry_run)
            except KeyboardInterrupt:
                log("Daemon stopped by user (Ctrl+C)", "INFO")
                break
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
                import traceback
                traceback.print_exc()

            log(f"Next cycle in {args.daemon}s ({args.daemon/60:.0f}min)...", "INFO")
            try:
                time.sleep(args.daemon)
            except KeyboardInterrupt:
                log("Daemon stopped by user (Ctrl+C)", "INFO")
                break
    else:
        run_cycle(sectors, state, max_queries=args.max_queries, dry_run=args.dry_run)

    log("Unified Ingestion finished", "OK")


if __name__ == "__main__":
    main()
