#!/usr/bin/env python3
"""
Continuous Ingestion Loop — Feed real documents to n8n Ingestion + Enrichment H24.

Cycle every 30min:
1. Search real documents per sector (Brave Search API)
2. Send each to n8n Ingestion V4.0 webhook (/webhook/rag-v6-ingestion)
3. Send to n8n Enrichment V4.0 webhook (/webhook/rag-v6-enrichment)
4. Track stats: docs ingested, enriched, errors, per sector
5. Log everything for monitoring

Target: 1M documents across 4 sectors.
"""

import os, sys, json, ssl, time, hashlib, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent

# ── Load env ─────────────────────────────────────────────────
def load_env():
    env_file = ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

load_env()

# ── Config ───────────────────────────────────────────────────
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
INGEST_WEBHOOK = f"{N8N_HOST}/webhook/rag-v6-ingestion"
ENRICH_WEBHOOK = f"{N8N_HOST}/webhook/rag-v6-enrichment"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

DATA_DIR = ROOT / "data" / "ingest"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "ingest-loop.jsonl"
STATS_FILE = DATA_DIR / "ingest-stats.json"
SEEN_FILE = DATA_DIR / "seen-urls.json"

CYCLE_INTERVAL = 1800  # 30 minutes

# ── Search queries per sector (rotated each cycle) ───────────
SECTOR_QUERIES = {
    "finance": [
        "IFRS 2026 new standards accounting",
        "SEC filing 10-K annual report 2025",
        "Basel III regulation banking capital requirements",
        "EBITDA financial analysis corporate valuation",
        "ESG reporting sustainability finance 2026",
        "derivatives trading risk management futures options",
        "central bank monetary policy inflation 2026",
        "private equity venture capital fund performance",
        "financial audit procedures compliance SOX",
        "cryptocurrency regulation DeFi blockchain finance",
    ],
    "btp": [
        "DTU normes construction batiment 2026",
        "Eurocode calcul structure beton arme",
        "CCTP cahier clauses techniques particulieres",
        "permis construire urbanisme PLU",
        "BIM building information modeling construction",
        "norme NF EN isolation thermique RE2020",
        "BOAMP appel offre marche public travaux",
        "diagnostic immobilier DPE amiante plomb",
        "securite chantier plan prevention risques",
        "RT2020 reglementation thermique batiment neuf",
    ],
    "juridique": [
        "jurisprudence Cour cassation 2025 2026",
        "RGPD protection donnees personnelles conformite",
        "code civil contrat obligations 2026",
        "droit travail licenciement procedure France",
        "code commerce societes SAS SARL",
        "propriete intellectuelle brevet marque depot",
        "droit immobilier bail commercial habitation",
        "procedure penale garde vue droits defense",
        "droit fiscal impot societes TVA",
        "arbitrage commercial international CCI",
    ],
    "industrie": [
        "ISO 9001 2025 quality management system",
        "maintenance predictive industrie 4.0 IoT",
        "AMDEC analyse modes defaillances effets",
        "lean manufacturing six sigma production",
        "norme ISO 14001 management environnemental",
        "securite machines directive 2006/42/CE",
        "supply chain management logistique industrielle",
        "automatisation robotique industrielle cobots",
        "controle qualite metrologie calibration",
        "gestion risques industriels ICPE Seveso",
    ],
}

_query_index = defaultdict(int)


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).isoformat()[:19]
    entry = {"ts": ts, "level": level, "msg": msg}
    print(f"[{ts}] [{level}] {msg}")
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def http_post(url, data, headers=None, timeout=60):
    body = json.dumps(data).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except Exception as e:
        return {"error": str(e)}, 0


def http_get(url, headers=None, timeout=20):
    hdrs = headers or {}
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except Exception as e:
        return {"error": str(e)}, 0


# ── Load/save seen URLs ──────────────────────────────────────
def load_seen():
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()))
        except Exception:
            pass
    return set()


def save_seen(seen):
    # Keep last 10K URLs
    seen_list = list(seen)[-10000:]
    SEEN_FILE.write_text(json.dumps(seen_list))


# ══════════════════════════════════════════════════════════════
# STEP 1: SEARCH FOR DOCUMENTS
# ══════════════════════════════════════════════════════════════

def search_documents(sector, max_results=5):
    """Search for real documents using Brave Search API."""
    queries = SECTOR_QUERIES.get(sector, [])
    if not queries:
        return []

    # Rotate through queries
    idx = _query_index[sector]
    query = queries[idx % len(queries)]
    _query_index[sector] = idx + 1

    docs = []

    if BRAVE_API_KEY:
        try:
            url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count={max_results}&freshness=pm"
            data, status = http_get(url, headers={
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_API_KEY,
            })
            if status == 200 and "web" in data:
                for result in data["web"].get("results", []):
                    docs.append({
                        "url": result.get("url", ""),
                        "title": result.get("title", ""),
                        "description": result.get("description", "")[:500],
                        "sector": sector,
                        "source": "brave",
                        "query": query,
                    })
        except Exception as e:
            log(f"Brave search failed for {sector}: {e}", "WARN")

    # Exa.AI as secondary source
    if EXA_API_KEY and len(docs) < max_results:
        try:
            data, status = http_post(
                "https://api.exa.ai/search",
                {"query": query, "numResults": 3, "useAutoprompt": True, "type": "neural"},
                headers={"Authorization": f"Bearer {EXA_API_KEY}"},
                timeout=15
            )
            if status == 200 and "results" in data:
                for result in data["results"]:
                    docs.append({
                        "url": result.get("url", ""),
                        "title": result.get("title", ""),
                        "description": result.get("text", "")[:500],
                        "sector": sector,
                        "source": "exa",
                        "query": query,
                    })
        except Exception as e:
            log(f"Exa search failed for {sector}: {e}", "WARN")

    return docs


# ══════════════════════════════════════════════════════════════
# STEP 2: SEND TO N8N INGESTION
# ══════════════════════════════════════════════════════════════

def ingest_document(doc, seen):
    """Send a document to n8n Ingestion V4.0 webhook."""
    url = doc.get("url", "")
    if not url or url in seen:
        return False, "duplicate"

    payload = {
        "url": url,
        "title": doc.get("title", ""),
        "sector": doc.get("sector", "finance"),
        "source": doc.get("source", "brave"),
        "description": doc.get("description", ""),
    }

    result, status = http_post(INGEST_WEBHOOK, payload, timeout=90)

    if status in (200, 201):
        seen.add(url)
        return True, "ok"
    elif status == 0:
        return False, f"timeout/error: {result.get('error', 'unknown')[:100]}"
    else:
        return False, f"http {status}"


# ══════════════════════════════════════════════════════════════
# STEP 3: SEND TO N8N ENRICHMENT
# ══════════════════════════════════════════════════════════════

def enrich_document(doc):
    """Send a document to n8n Enrichment V4.0 webhook."""
    payload = {
        "url": doc.get("url", ""),
        "sector": doc.get("sector", "finance"),
        "title": doc.get("title", ""),
        "text": doc.get("description", ""),
    }

    result, status = http_post(ENRICH_WEBHOOK, payload, timeout=90)
    return status in (200, 201), result


# ══════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════

def load_stats():
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text())
        except Exception:
            pass
    return {
        "total_searched": 0,
        "total_ingested": 0,
        "total_enriched": 0,
        "total_errors": 0,
        "total_duplicates": 0,
        "by_sector": {},
        "cycles": 0,
        "started": datetime.now(timezone.utc).isoformat(),
        "last_cycle": "",
    }


def save_stats(stats):
    stats["last_updated"] = datetime.now(timezone.utc).isoformat()
    STATS_FILE.write_text(json.dumps(stats, indent=2))


# ══════════════════════════════════════════════════════════════
# MAIN CYCLE
# ══════════════════════════════════════════════════════════════

def run_cycle(stats):
    """One full ingestion cycle across all 4 sectors."""
    cycle_start = time.time()
    stats["cycles"] += 1
    stats["last_cycle"] = datetime.now(timezone.utc).isoformat()

    seen = load_seen()
    cycle_ingested = 0
    cycle_enriched = 0
    cycle_errors = 0
    cycle_dupes = 0

    for sector in ["finance", "btp", "juridique", "industrie"]:
        # Search for documents
        docs = search_documents(sector, max_results=5)
        stats["total_searched"] += len(docs)

        if sector not in stats["by_sector"]:
            stats["by_sector"][sector] = {"searched": 0, "ingested": 0, "enriched": 0, "errors": 0}
        stats["by_sector"][sector]["searched"] += len(docs)

        for doc in docs:
            # Ingest
            success, reason = ingest_document(doc, seen)
            if success:
                cycle_ingested += 1
                stats["total_ingested"] += 1
                stats["by_sector"][sector]["ingested"] += 1

                # Enrich after successful ingestion
                enrich_ok, _ = enrich_document(doc)
                if enrich_ok:
                    cycle_enriched += 1
                    stats["total_enriched"] += 1
                    stats["by_sector"][sector]["enriched"] += 1
            elif reason == "duplicate":
                cycle_dupes += 1
                stats["total_duplicates"] += 1
            else:
                cycle_errors += 1
                stats["total_errors"] += 1
                stats["by_sector"][sector]["errors"] += 1

            # Small delay between requests to not overwhelm n8n
            time.sleep(2)

    save_seen(seen)
    save_stats(stats)

    elapsed = time.time() - cycle_start
    log(f"CYCLE #{stats['cycles']} DONE ({elapsed:.0f}s) — "
        f"ingested={cycle_ingested} enriched={cycle_enriched} "
        f"dupes={cycle_dupes} errors={cycle_errors} | "
        f"TOTAL: {stats['total_ingested']} ingested, {stats['total_enriched']} enriched")

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Continuous Ingestion Loop")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (30min cycles)")
    parser.add_argument("--once", action="store_true", help="Run one cycle")
    parser.add_argument("--interval", type=int, default=CYCLE_INTERVAL, help="Cycle interval seconds")
    parser.add_argument("--status", action="store_true", help="Show stats")
    args = parser.parse_args()

    if args.status:
        stats = load_stats()
        print(f"\n{'='*50}")
        print(f"INGESTION LOOP STATS")
        print(f"{'='*50}")
        print(f"Cycles: {stats['cycles']}")
        print(f"Total searched: {stats['total_searched']}")
        print(f"Total ingested: {stats['total_ingested']}")
        print(f"Total enriched: {stats['total_enriched']}")
        print(f"Total errors: {stats['total_errors']}")
        print(f"Total duplicates: {stats['total_duplicates']}")
        print(f"\nBy sector:")
        for sector, s in stats.get("by_sector", {}).items():
            print(f"  {sector}: {s['ingested']} ingested, {s['enriched']} enriched, {s['errors']} errors")
        print(f"\nStarted: {stats.get('started', '?')}")
        print(f"Last cycle: {stats.get('last_cycle', '?')}")
        return

    # Save PID
    pid_file = DATA_DIR / "unified.pid"
    pid_file.write_text(str(os.getpid()))

    stats = load_stats()

    if args.once or not args.daemon:
        run_cycle(stats)
    else:
        log(f"Starting Ingestion Loop daemon — {args.interval}s cycles")
        while True:
            try:
                stats = run_cycle(stats)
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
