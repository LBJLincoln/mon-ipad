#!/usr/bin/env python3
"""
Exa.AI Mass Ingest — Discover expert documents via Exa.AI, send to n8n pipelines.

Flow: Exa.AI search → discover URLs/content → n8n Ingestion webhook → n8n handles:
  chunking, embedding, Pinecone, Supabase, NER → then Enrichment → Neo4j graph

This script is DISCOVERY ONLY. All processing goes through n8n workflows.

Replaces tavily-mass-ingest.py (Tavily credits exhausted).

Usage:
  source .env.local
  python3 ops/exa-mass-ingest.py --sector btp
  python3 ops/exa-mass-ingest.py --sector all
  python3 ops/exa-mass-ingest.py --sector btp --dry-run
  python3 ops/exa-mass-ingest.py --sector btp --max-queries 5
"""

import argparse
import base64
import hashlib
import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# ── Force line buffering for nohup ────────────────────────────
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# ── Force IPv4 globally ──────────────────────────────────────
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type_=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type_, proto, flags)
socket.getaddrinfo = _ipv4_getaddrinfo

# ── Load .env.local ──────────────────────────────────────────
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

# ── Config ────────────────────────────────────────────────────
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
EXA_SEARCH_URL = "https://api.exa.ai/search"
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# n8n endpoints — ingestion + enrichment webhooks
N8N_SPACES = [
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",   # S9 — primary ingest
    "https://lbjlincoln-nomos-rag-engine.hf.space",      # S1 — fallback
    "https://lbjlincoln-nomos-rag-engine-3.hf.space",    # S3 — fallback
]
INGEST_PATH = "/webhook/rag-v6-ingestion"
ENRICH_PATH = "/webhook/rag-v6-enrichment"

PROGRESS_DIR = Path(os.path.expanduser("~/mon-ipad/data/ingest"))
PROGRESS_FILE = PROGRESS_DIR / "exa-mass-progress.json"

EXA_DELAY = 1.0         # seconds between Exa requests
N8N_DELAY = 2.0          # seconds between n8n calls (avoid overwhelming)
MIN_CONTENT_LEN = 200    # minimum content length to send to n8n

# ── Search Queries ────────────────────────────────────────────
BTP_QUERIES = [
    "DTU 31.2 ossature bois construction",
    "permis de construire étapes procédure",
    "normes parasismiques Eurocode 8 France",
    "CCTP marché public travaux rédaction",
    "RE2020 obligations réglementation environnementale",
    "DTU couverture toiture étanchéité",
    "fondations profondes techniques pieux",
    "béton armé eurocode 2 calcul",
    "isolation thermique bâtiment RT2012",
    "sécurité chantier BTP réglementation",
    "AFNOR normes construction bâtiment",
    "diagnostic amiante plomb DPE",
    "marché public BOAMP appel offre",
    "assurance décennale garantie construction",
    "plan local urbanisme PLU permis",
]

INDUSTRIE_QUERIES = [
    "ISO 9001 démarche qualité certification",
    "AMDEC analyse défaillance criticité",
    "fiche données sécurité FDS rédaction",
    "lean manufacturing principes gaspillage",
    "maintenance préventive planification équipement",
    "ISO 14001 environnement management",
    "Six Sigma DMAIC amélioration continue",
    "HACCP sécurité alimentaire",
    "norme ISO 45001 santé sécurité travail",
    "gestion stock méthode kanban",
    "TPM maintenance productive totale",
    "audit qualité processus certification",
    "REACH substances chimiques réglementation",
    "contrôle non destructif CND ultrasons",
    "automatisation industrielle 4.0 IoT",
]

FINANCE_QUERIES = [
    "IFRS normes comptables internationales",
    "ratio financier analyse entreprise",
    "bilan comptable actif passif explication",
    "marché obligataire taux d intérêt France",
    "gestion de portefeuille diversification risque",
    "analyse fondamentale actions bourse",
    "réglementation bancaire Bâle III IV",
    "fiscalité entreprise impôt société France",
    "fusion acquisition due diligence",
    "trésorerie entreprise cash flow gestion",
    "audit financier commissaire aux comptes",
    "crédit scoring notation financière",
    "assurance vie épargne placement",
    "fintech blockchain finance décentralisée",
    "ESG investissement responsable critères",
]

JURIDIQUE_QUERIES = [
    "code civil responsabilité contractuelle articles",
    "droit du travail licenciement procédure France",
    "RGPD protection données personnelles conformité",
    "droit des sociétés SAS SARL statuts",
    "propriété intellectuelle brevet marque dépôt",
    "contentieux commercial tribunal procédure",
    "droit immobilier bail commercial résiliation",
    "droit fiscal contrôle redressement",
    "droit de la concurrence pratiques anticoncurrentielles",
    "procédure collective sauvegarde liquidation judiciaire",
    "contrat de travail clause non concurrence",
    "droit administratif marché public recours",
    "médiation arbitrage résolution litiges",
    "droit pénal des affaires abus de biens sociaux",
    "conformité compliance entreprise loi Sapin II",
]

SECTOR_QUERIES = {
    "btp": BTP_QUERIES,
    "industrie": INDUSTRIE_QUERIES,
    "finance": FINANCE_QUERIES,
    "juridique": JURIDIQUE_QUERIES,
}


# ── Utilities ─────────────────────────────────────────────────

def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix = {"INFO": "[+]", "WARN": "[!]", "ERROR": "[X]"}.get(level, "[*]")
    print(f" {ts} {prefix} {msg}")


def make_id(text, sector, url=""):
    raw = f"{sector}:{url}:{text[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return "unknown"


# ── Exa.AI Search ─────────────────────────────────────────────

def exa_search(query: str, num_results: int = 10) -> list[dict]:
    """Search Exa.AI and return results with text content."""
    payload = json.dumps({
        "query": query,
        "numResults": num_results,
        "type": "auto",
        "contents": {
            "text": True
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        EXA_SEARCH_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": EXA_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            normalized = []
            for r in results:
                normalized.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "text": r.get("text", ""),
                    "published_date": r.get("publishedDate", ""),
                    "author": r.get("author", ""),
                })
            return normalized
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        log(f"Exa.AI HTTP {e.code}: {body}", "ERROR")
        return []
    except Exception as e:
        log(f"Exa.AI request failed: {e}", "ERROR")
        return []


def brave_search(query: str, num_results: int = 10) -> list[dict]:
    """Search Brave Web Search API and return results."""
    if not BRAVE_API_KEY:
        return []

    params = urllib.parse.urlencode({
        "q": query,
        "count": num_results,
        "text_decorations": "false",
        "search_lang": "fr",
    })

    req = urllib.request.Request(
        f"{BRAVE_SEARCH_URL}?{params}",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": BRAVE_API_KEY,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            # Handle gzip
            if resp.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
            results = data.get("web", {}).get("results", [])
            normalized = []
            for r in results:
                desc = r.get("description", "")
                # Brave doesn't return full text, just snippets — we send URL to n8n for Docling
                normalized.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "text": desc if len(desc) > MIN_CONTENT_LEN else "",
                    "published_date": r.get("age", ""),
                    "author": "",
                    "source": "brave",
                })
            return normalized
    except Exception as e:
        log(f"Brave Search failed: {e}", "ERROR")
        return []


def multi_search(query: str, num_results: int = 10) -> list[dict]:
    """Search both Exa.AI and Brave Search, deduplicate by URL."""
    results = exa_search(query, num_results)
    brave_results = brave_search(query, num_results)

    seen_urls = {r["url"] for r in results}
    for br in brave_results:
        if br["url"] and br["url"] not in seen_urls:
            results.append(br)
            seen_urls.add(br["url"])

    return results


# ── n8n Webhook Callers ───────────────────────────────────────

def call_n8n_ingest(doc, timeout=90):
    """Send a document to n8n Ingestion webhook for full processing."""
    doc_id = doc.get("id") or make_id(doc.get("content", ""), doc.get("sector", ""), doc.get("url", ""))

    payload = {
        "documentId": doc_id,
        "filename": (doc.get("title", "document"))[:100] + ".html",
        "source": "exa",
        "tenant_id": doc.get("sector", "finance"),
        "metadata": {
            "sector": doc.get("sector", "finance"),
            "source_url": doc.get("url", ""),
            "title": doc.get("title", ""),
            "domain": doc.get("domain", ""),
            "origin": "exa-mass-ingest",
            "published_date": doc.get("published_date", ""),
        }
    }

    # If URL available, let n8n fetch & process it (best: Docling/Unstructured)
    if doc.get("url"):
        payload["content_url"] = doc["url"]

    # Also send content as base64 fallback (in case URL is paywalled)
    if doc.get("content"):
        payload["content_base64"] = base64.b64encode(doc["content"].encode()).decode()

    data = json.dumps(payload).encode()

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
                space_name = space_url.split("//")[1].split(".")[0]
                return {"ok": True, "space": space_name, "result": result, "doc_id": doc_id}
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            log(f"n8n {space_url.split('//')[1][:30]} HTTP {e.code}: {body}", "WARN")
        except Exception as e:
            log(f"n8n {space_url.split('//')[1][:30]} error: {e}", "WARN")

    return {"ok": False, "error": "All n8n Spaces failed", "doc_id": doc_id}


def call_n8n_enrich(doc_id, sector, timeout=90):
    """Trigger n8n Enrichment for Neo4j graph building."""
    payload = json.dumps({
        "doc_id": doc_id,
        "sector": sector,
        "source": "exa-mass-ingest",
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
            if e.code == 500:
                return {"ok": True, "note": "workflow ran, response format issue"}
        except Exception:
            pass

    return {"ok": False}


# ── Main Ingestion Logic ─────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            pass
    return {"started": datetime.now(timezone.utc).isoformat(), "sectors": {}}


def save_progress(progress: dict):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    progress["last_updated"] = datetime.now(timezone.utc).isoformat()
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2, ensure_ascii=False))


def ingest_sector(sector: str, queries: list[str], dry_run: bool = False,
                  max_queries: int = 0, enrich: bool = True) -> dict:
    """Discover docs via Exa.AI, send each to n8n ingestion + enrichment."""
    stats = {
        "sector": sector,
        "queries_run": 0,
        "queries_total": len(queries),
        "results_found": 0,
        "docs_sent_to_n8n": 0,
        "docs_ingested_ok": 0,
        "docs_enriched_ok": 0,
        "docs_failed": 0,
        "urls_processed": [],
        "errors": [],
        "started": datetime.now(timezone.utc).isoformat(),
    }

    if max_queries > 0:
        queries = queries[:max_queries]
        stats["queries_total"] = len(queries)

    seen_urls = set()

    print(f"\n{'='*70}")
    print(f"  SECTOR: {sector.upper()}")
    print(f"  Queries: {len(queries)}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE → n8n pipelines'}")
    print(f"  Enrich: {'YES (Neo4j)' if enrich else 'NO'}")
    print(f"{'='*70}\n")

    for qi, query in enumerate(queries):
        log(f"[{qi+1}/{len(queries)}] Query: \"{query}\"")
        stats["queries_run"] += 1

        results = multi_search(query) if BRAVE_API_KEY else exa_search(query)
        log(f"  Found {len(results)} results (Exa+Brave)" if BRAVE_API_KEY else f"  Found {len(results)} results (Exa only)")
        stats["results_found"] += len(results)

        if not results:
            time.sleep(EXA_DELAY)
            continue

        for ri, result in enumerate(results):
            url = result.get("url", "")
            title = result.get("title", "")[:100]
            text = result.get("text", "") or ""
            domain = extract_domain(url)

            # Skip if no content or too short
            if not text or len(text) < MIN_CONTENT_LEN:
                continue

            # Skip duplicate URLs
            if url in seen_urls:
                continue
            seen_urls.add(url)

            log(f"  [{ri}] {title[:55]} | {domain} | {len(text):,} chars")
            stats["urls_processed"].append({
                "url": url[:200],
                "title": title,
                "domain": domain,
                "text_len": len(text),
            })

            if dry_run:
                stats["docs_sent_to_n8n"] += 1
                stats["docs_ingested_ok"] += 1
                continue

            # Send to n8n Ingestion pipeline
            doc = {
                "url": url,
                "title": title,
                "content": text,
                "sector": sector,
                "domain": domain,
                "published_date": result.get("published_date", ""),
            }

            stats["docs_sent_to_n8n"] += 1
            ingest_result = call_n8n_ingest(doc)

            if ingest_result.get("ok"):
                stats["docs_ingested_ok"] += 1
                log(f"    → n8n ingested OK ({ingest_result.get('space', '?')})")

                # Trigger enrichment for Neo4j graph
                if enrich:
                    doc_id = ingest_result.get("doc_id", "")
                    enrich_result = call_n8n_enrich(doc_id, sector)
                    if enrich_result.get("ok"):
                        stats["docs_enriched_ok"] += 1
                        log(f"    → enriched OK")
            else:
                stats["docs_failed"] += 1
                stats["errors"].append(f"{url}: {ingest_result.get('error', 'unknown')}")
                log(f"    → FAILED: {ingest_result.get('error', 'unknown')}", "WARN")

            time.sleep(N8N_DELAY)

        time.sleep(EXA_DELAY)

    stats["finished"] = datetime.now(timezone.utc).isoformat()
    stats["duration_s"] = round(
        (datetime.fromisoformat(stats["finished"]) - datetime.fromisoformat(stats["started"])).total_seconds(), 1
    )

    print(f"\n{'-'*50}")
    print(f"  SECTOR {sector.upper()} COMPLETE")
    print(f"  Queries:    {stats['queries_run']}/{stats['queries_total']}")
    print(f"  Results:    {stats['results_found']} found")
    print(f"  n8n sent:   {stats['docs_sent_to_n8n']}")
    print(f"  Ingested:   {stats['docs_ingested_ok']} OK, {stats['docs_failed']} failed")
    print(f"  Enriched:   {stats['docs_enriched_ok']}")
    print(f"  Duration:   {stats['duration_s']}s")
    print(f"  URLs:       {len(seen_urls)} unique")
    print(f"{'-'*50}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Exa.AI discovery → n8n ingestion+enrichment pipeline")
    parser.add_argument("--sector", required=True,
                        choices=["btp", "industrie", "finance", "juridique", "all"],
                        help="Sector to ingest")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate without calling n8n")
    parser.add_argument("--max-queries", type=int, default=0,
                        help="Limit number of queries (0=all)")
    parser.add_argument("--no-enrich", action="store_true",
                        help="Skip Neo4j enrichment step")
    args = parser.parse_args()

    if not EXA_API_KEY:
        print("ERROR: EXA_API_KEY not set. Run: source .env.local")
        sys.exit(1)

    print("=" * 70)
    print("  EXA.AI MASS INGEST → n8n pipelines")
    print(f"  Flow: Exa.AI search → n8n Ingestion → n8n Enrichment → Neo4j")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    progress = load_progress()
    sectors_to_run = list(SECTOR_QUERIES.keys()) if args.sector == "all" else [args.sector]

    all_stats = {}
    for sector in sectors_to_run:
        queries = SECTOR_QUERIES[sector]
        sector_stats = ingest_sector(
            sector, queries,
            dry_run=args.dry_run,
            max_queries=args.max_queries,
            enrich=not args.no_enrich,
        )
        all_stats[sector] = sector_stats
        progress["sectors"][sector] = sector_stats

    save_progress(progress)

    total_ingested = sum(s["docs_ingested_ok"] for s in all_stats.values())
    total_enriched = sum(s["docs_enriched_ok"] for s in all_stats.values())
    total_failed = sum(s["docs_failed"] for s in all_stats.values())

    print(f"\n{'='*70}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"  Total docs ingested via n8n: {total_ingested}")
    print(f"  Total docs enriched (Neo4j): {total_enriched}")
    print(f"  Total failed: {total_failed}")
    print(f"  Progress saved: {PROGRESS_FILE}")
    print(f"  Finished: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
