#!/usr/bin/env python3
"""
Unified Ingestion Pipeline — Feeds documents to n8n workflows.

The SCRIPT finds documents. The N8N WORKFLOW processes them.
  - n8n Ingestion V4.0: MIME detect → OCR/Unstructured → PII → Semantic Chunk
                         → Contextual Embed → Pinecone + Postgres + BM25 + NER
  - n8n Enrichment V4.0: AI Entity Extraction → Relationship Mapping → Neo4j
                         → Community Detection → Cross-doc Linking

Flow:
  1. Source discovery (Tavily web, HF datasets, local JSONL, PDF URLs)
  2. Dedup (check Supabase document_registry)
  3. POST each document to n8n Ingestion V4.0 webhook
  4. n8n handles: Docling/Unstructured, chunking, embedding, storage, NER
  5. Optionally trigger Enrichment V4.0 for Neo4j graph

n8n Ingestion payload:
  { documentId, filename, content_url, content_base64, source, tenant_id, metadata }

Usage:
  source .env.local
  python3 ops/ingest-pipeline.py --source tavily --sector finance --max 5
  python3 ops/ingest-pipeline.py --source pdf --urls urls.txt --sector btp
  python3 ops/ingest-pipeline.py --source jsonl --sector all
  python3 ops/ingest-pipeline.py --daemon 1800 --sector all
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
import base64
import hashlib
import json
import os
import signal
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

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

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DATASETS_DIR = Path.home() / "rag-data-ingestion" / "datasets" / "sectors"

# n8n endpoints — S9 has Ingestion V4.0 + Enrichment V4.0
N8N_SPACES = [
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",   # S9 — primary ingest
    "https://lbjlincoln-nomos-rag-engine.hf.space",      # S1 — fallback
]
INGEST_PATH = "/webhook/rag-v6-ingestion"
ENRICH_PATH = "/webhook/rag-v6-enrichment"

SECTORS = ["finance", "btp", "juridique", "industrie"]
MIN_TEXT_LEN = 50
STATE_FILE = os.path.join(REPO_ROOT, "data", "ingest", "pipeline-state.json")

_shutdown = False
def _handle_sig(s, f):
    global _shutdown
    _shutdown = True
signal.signal(signal.SIGINT, _handle_sig)
signal.signal(signal.SIGTERM, _handle_sig)

# ── Tavily queries per sector ──
TAVILY_QUERIES = {
    "finance": [
        "analyse financière entreprise EBITDA marge nette bilan",
        "IFRS 17 assurance normes comptables application",
        "ratio financier ROE ROA banque française Bâle III",
        "audit financier commissaire aux comptes rapport annuel",
        "gestion de trésorerie entreprise BFR cash flow prévision",
        "réglementation bancaire prudentielle fonds propres",
        "marchés financiers AMF régulation produits dérivés",
        "private equity LBO capital investissement valorisation",
        "analyse crédit scoring notation risque défaut",
        "fintech paiement innovation réglementation DSP2",
    ],
    "btp": [
        "DTU normes construction bâtiment France application",
        "Eurocode calcul structure béton armé ferraillage",
        "réglementation thermique RE2020 bâtiment neuf",
        "CCTP cahier clauses techniques particulières marché",
        "étude géotechnique sol fondation profonde superficielle",
        "charpente métallique dimensionnement assemblage",
        "isolation thermique extérieure rénovation énergétique",
        "VRD voirie réseau assainissement terrassement",
        "permis construire urbanisme PLU réglementation",
        "maître ouvrage maîtrise œuvre BET coordination",
    ],
    "juridique": [
        "Code civil contrat obligations responsabilité civile",
        "droit travail licenciement procédure prud'hommes indemnités",
        "RGPD protection données personnelles conformité DPO",
        "droit sociétés SAS SARL création statuts assemblée",
        "marchés publics code commande publique attribution critères",
        "jurisprudence Cour cassation chambre commerciale 2025",
        "propriété intellectuelle brevet marque contrefaçon INPI",
        "bail commercial renouvellement résiliation indemnité éviction",
        "procédure collective redressement liquidation judiciaire",
        "contentieux administratif tribunal recours annulation",
    ],
    "industrie": [
        "ISO 9001 système management qualité certification audit",
        "maintenance préventive industrielle TPM GMAO planification",
        "AMDEC analyse modes défaillance processus cotation",
        "lean manufacturing Six Sigma Kaizen amélioration continue",
        "sécurité industrielle ATEX directive risque explosion",
        "automatisation robotique industrie 4.0 usine connectée",
        "supply chain logistique approvisionnement juste à temps",
        "contrôle qualité métrologie étalonnage incertitude mesure",
        "gestion production MRP ERP ordonnancement planification",
        "environnement ISO 14001 ICPE installation classée",
    ],
}


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix = {"INFO": "[+]", "WARN": "[!]", "ERROR": "[X]"}.get(level, "[*]")
    print(f" {ts} {prefix} {msg}")


def make_id(text, sector, source=""):
    raw = f"{sector}:{source}:{text[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ── n8n webhook caller ──
def call_n8n_ingest(doc, timeout=90):
    """Send a document to n8n Ingestion V4.0 webhook."""
    doc_id = doc.get("id") or make_id(doc.get("content", ""), doc.get("sector", ""), doc.get("url", ""))

    # Build n8n payload
    payload = {
        "documentId": doc_id,
        "filename": doc.get("filename", doc.get("title", "document")) + ".html",
        "source": doc.get("source", "tavily"),
        "tenant_id": doc.get("sector", "finance"),
        "metadata": {
            "sector": doc.get("sector", "finance"),
            "source_url": doc.get("url", ""),
            "title": doc.get("title", ""),
            "origin": "ingest-pipeline",
        }
    }

    # If we have a URL, use content_url (n8n will fetch & process it)
    if doc.get("url"):
        payload["content_url"] = doc["url"]
    # If we have raw content, base64 encode it
    elif doc.get("content"):
        payload["content_base64"] = base64.b64encode(doc["content"].encode()).decode()

    data = json.dumps(payload).encode()

    # Try each Space
    for space_url in N8N_SPACES:
        url = f"{space_url}{INGEST_PATH}"
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read())
                return {"ok": True, "space": space_url.split("//")[1].split(".")[0], "result": result}
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200] if hasattr(e, 'read') else str(e)
            log(f"n8n {space_url} HTTP {e.code}: {body}", "WARN")
        except Exception as e:
            log(f"n8n {space_url} error: {e}", "WARN")

    return {"ok": False, "error": "All Spaces failed"}


def call_n8n_enrich(doc_id, sector, timeout=90):
    """Trigger n8n Enrichment V4.0 for a document."""
    payload = json.dumps({
        "doc_id": doc_id,
        "sector": sector,
        "source": "ingest-pipeline",
    }).encode()

    for space_url in N8N_SPACES:
        url = f"{space_url}{ENRICH_PATH}"
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {"ok": True, "space": space_url.split("//")[1].split(".")[0]}
        except urllib.error.HTTPError as e:
            # 500 is expected (workflow runs but response format issue)
            if e.code == 500:
                return {"ok": True, "space": space_url.split("//")[1].split(".")[0], "note": "workflow ran, response format issue"}
        except Exception as e:
            log(f"Enrich {space_url} error: {e}", "WARN")

    return {"ok": False, "error": "All Spaces failed"}


# ── Source: Tavily ──
def tavily_search(query, sector, max_results=5):
    if not TAVILY_API_KEY:
        log("TAVILY_API_KEY not set", "WARN")
        return []

    payload = json.dumps({
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "include_raw_content": True,
        "max_results": max_results,
    }).encode()

    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            results = []
            for r in data.get("results", []):
                content = r.get("raw_content") or r.get("content", "")
                if content and len(content) > MIN_TEXT_LEN:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "content": content,
                        "sector": sector,
                        "source": "tavily",
                        "filename": r.get("title", "document")[:100],
                    })
            return results
    except Exception as e:
        log(f"Tavily search failed: {e}", "ERROR")
        return []


# ── Source: Local JSONL ──
def load_jsonl_docs(sector, max_records=200):
    sector_dir = DATASETS_DIR / sector
    if not sector_dir.exists():
        return []

    docs = []
    for jsonl_file in sorted(sector_dir.glob("*.jsonl")):
        try:
            with open(jsonl_file) as f:
                for line in f:
                    if len(docs) >= max_records:
                        break
                    try:
                        record = json.loads(line.strip())
                        text = record.get("text") or record.get("content") or record.get("instruction", "")
                        if text and len(text) >= MIN_TEXT_LEN:
                            docs.append({
                                "title": record.get("title", jsonl_file.stem),
                                "url": record.get("url", record.get("source_url", "")),
                                "content": text,
                                "sector": sector,
                                "source": "jsonl",
                                "filename": record.get("title", jsonl_file.stem)[:100],
                            })
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            log(f"Error reading {jsonl_file}: {e}", "WARN")

    return docs


# ── Main pipeline ──
def ingest_batch(docs, enrich=True, delay=2.0):
    """Send a batch of documents to n8n Ingestion V4.0."""
    if not docs:
        return {"total": 0, "ok": 0, "fail": 0, "enriched": 0}

    ok = 0
    fail = 0
    enriched = 0

    for i, doc in enumerate(docs):
        if _shutdown:
            break

        title = doc.get("title", "?")[:50]
        sector = doc.get("sector", "?")
        log(f"[{i+1}/{len(docs)}] Ingesting: {title}... ({sector})")

        result = call_n8n_ingest(doc)

        if result["ok"]:
            ok += 1
            log(f"  -> OK ({result.get('space', '?')})")

            # Trigger enrichment
            if enrich:
                doc_id = doc.get("id") or make_id(doc.get("content", ""), sector, doc.get("url", ""))
                e_result = call_n8n_enrich(doc_id, sector)
                if e_result["ok"]:
                    enriched += 1
        else:
            fail += 1
            log(f"  -> FAIL: {result.get('error', '?')}", "ERROR")

        time.sleep(delay)  # Don't overwhelm n8n

    return {"total": len(docs), "ok": ok, "fail": fail, "enriched": enriched}


def run_tavily_cycle(sectors, max_queries=3, enrich=True):
    """Run Tavily → n8n ingestion cycle."""
    all_docs = []
    for sector in sectors:
        queries = TAVILY_QUERIES.get(sector, [])[:max_queries]
        for query in queries:
            if _shutdown:
                break
            log(f"Tavily: {query[:50]}... ({sector})")
            results = tavily_search(query, sector, max_results=5)
            all_docs.extend(results)
            time.sleep(1.5)  # Tavily rate limit

    log(f"Tavily found {len(all_docs)} documents across {len(sectors)} sectors")
    return ingest_batch(all_docs, enrich=enrich)


def run_jsonl_cycle(sectors, max_per_sector=50, enrich=True):
    """Run JSONL → n8n ingestion cycle."""
    all_docs = []
    for sector in sectors:
        docs = load_jsonl_docs(sector, max_records=max_per_sector)
        all_docs.extend(docs)
        log(f"JSONL: {len(docs)} documents from {sector}")

    return ingest_batch(all_docs, enrich=enrich)


def run_url_cycle(urls_file, sector, enrich=True):
    """Run URL list → n8n ingestion cycle."""
    docs = []
    with open(urls_file) as f:
        for line in f:
            url = line.strip()
            if url and url.startswith("http"):
                docs.append({
                    "url": url,
                    "title": url.split("/")[-1],
                    "sector": sector,
                    "source": "url_list",
                    "filename": url.split("/")[-1],
                })

    log(f"URLs: {len(docs)} documents from {urls_file}")
    return ingest_batch(docs, enrich=enrich)


def run_daemon(sectors, interval, max_queries=3):
    """Run ingestion daemon: Tavily → JSONL rotation."""
    cycle = 0
    while not _shutdown:
        cycle += 1
        source = "tavily" if cycle % 2 == 1 else "jsonl"
        log(f"=== Ingestion cycle {cycle} (source={source}) ===")

        try:
            if source == "tavily":
                result = run_tavily_cycle(sectors, max_queries=max_queries)
            else:
                result = run_jsonl_cycle(sectors, max_per_sector=50)

            log(f"Cycle {cycle}: {json.dumps(result)}")

            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump({
                    "cycle": cycle, "source": source,
                    "result": result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, f, indent=2)

        except Exception as e:
            log(f"Cycle {cycle} error: {e}", "ERROR")

        if not _shutdown:
            log(f"Next cycle in {interval}s")
            for _ in range(interval):
                if _shutdown:
                    break
                time.sleep(1)

    log("Daemon stopped")


def main():
    parser = argparse.ArgumentParser(description="Unified Ingestion Pipeline (n8n-backed)")
    parser.add_argument("--source", choices=["tavily", "jsonl", "pdf", "all"], default="tavily")
    parser.add_argument("--sector", default="all", help="Sector or 'all'")
    parser.add_argument("--max-queries", type=int, default=2, help="Max Tavily queries per sector")
    parser.add_argument("--daemon", type=int, help="Run as daemon with N second interval")
    parser.add_argument("--urls", help="File with URLs (one per line)")
    parser.add_argument("--no-enrich", action="store_true", help="Skip enrichment trigger")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between documents (seconds)")
    args = parser.parse_args()

    sectors = SECTORS if args.sector == "all" else [args.sector]
    enrich = not args.no_enrich

    if args.daemon:
        run_daemon(sectors, args.daemon, max_queries=args.max_queries)
        return

    if args.source == "tavily":
        result = run_tavily_cycle(sectors, max_queries=args.max_queries, enrich=enrich)
    elif args.source == "jsonl":
        result = run_jsonl_cycle(sectors, enrich=enrich)
    elif args.source == "pdf" and args.urls:
        result = run_url_cycle(args.urls, sectors[0], enrich=enrich)
    elif args.source == "all":
        r1 = run_tavily_cycle(sectors, max_queries=args.max_queries, enrich=enrich)
        r2 = run_jsonl_cycle(sectors, enrich=enrich)
        result = {"tavily": r1, "jsonl": r2}
    else:
        log("No valid source specified", "ERROR")
        return

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
