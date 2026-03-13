#!/usr/bin/env python3
"""
Agent Improver — Karpathy autoresearch pattern for pipeline optimization.

Cycle:
  1. Read latest eval results (baseline)
  2. Identify weakest pipeline/sector combination
  3. Analyze failure patterns (what questions fail, why)
  4. Form hypothesis (e.g., "BTP needs more data", "Graph Cypher too rigid")
  5. Execute improvement action:
     a. DATA GAP → trigger targeted ingestion via n8n
     b. PROMPT ISSUE → log recommendation for manual fix
     c. RETRIEVAL MISS → trigger enrichment for missing docs
  6. Run quick eval to measure delta
  7. Log results

This agent does NOT modify n8n workflows directly.
It feeds data and identifies bottlenecks. Human applies workflow changes.

Usage:
  source .env.local
  python3 ops/agent-improver.py                  # One cycle
  python3 ops/agent-improver.py --daemon 3600    # Continuous (every hour)
  python3 ops/agent-improver.py --sector btp     # Focus on one sector
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
from collections import defaultdict

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

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

DB_URL = os.environ.get("DATABASE_URL", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
DATA_DIR = os.path.join(REPO_ROOT, "data", "agents")
REPORT_DIR = os.path.join(DATA_DIR, "improver-reports")
os.makedirs(REPORT_DIR, exist_ok=True)

# n8n endpoints
N8N_S9 = "https://lbjlincoln-nomos-rag-engine-9.hf.space"
INGEST_WEBHOOK = f"{N8N_S9}/webhook/rag-v6-ingestion"
ENRICH_WEBHOOK = f"{N8N_S9}/webhook/rag-v6-enrichment"

SECTORS = ["finance", "btp", "juridique", "industrie"]
PIPELINES = ["standard", "graph", "quantitative", "orchestrator"]

TARGETS = {
    "standard":     {"finance": 90, "btp": 85, "juridique": 90, "industrie": 85},
    "graph":        {"finance": 75, "btp": 70, "juridique": 80, "industrie": 70},
    "quantitative": {"finance": 95, "btp": 80, "juridique": 50, "industrie": 80},
    "orchestrator": {"finance": 85, "btp": 75, "juridique": 80, "industrie": 75},
}

# Tavily queries for targeted ingestion (sector-specific deep dives)
TARGETED_QUERIES = {
    "finance": [
        "bilan comptable analyse financière ratio entreprise",
        "consolidation comptable IFRS normes internationales",
        "gestion risque marché crédit opérationnel Bâle",
    ],
    "btp": [
        "DTU 13.1 fondations superficielles techniques",
        "Eurocode 2 béton armé dimensionnement calcul",
        "réglementation RE2020 performance énergétique bâtiment",
        "CCAG travaux marchés publics clauses générales",
        "NF DTU règles professionnelles couverture étanchéité",
    ],
    "juridique": [
        "jurisprudence Cour cassation arrêt récent droit civil",
        "Code du travail licenciement économique procédure",
        "RGPD sanctions CNIL mise en conformité entreprise",
    ],
    "industrie": [
        "ISO 9001 2015 système management qualité exigences",
        "maintenance conditionnelle prédictive capteurs IoT",
        "AMDEC processus analyse défaillance cotation criticité",
    ],
}

_shutdown = False
def _handle_sig(s, f):
    global _shutdown
    _shutdown = True
signal.signal(signal.SIGINT, _handle_sig)
signal.signal(signal.SIGTERM, _handle_sig)


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix = {"INFO": "[+]", "WARN": "[!]", "ERROR": "[X]", "ACTION": "[>]"}.get(level, "[*]")
    print(f" {ts} IMPROVER {prefix} {msg}")


def get_db():
    import psycopg2
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    with conn.cursor() as c:
        c.execute("SET search_path TO public")
    return conn


def db_query(sql, params=None):
    try:
        conn = get_db()
        with conn.cursor() as c:
            c.execute(sql, params)
            if c.description:
                cols = [d[0] for d in c.description]
                return [dict(zip(cols, row)) for row in c.fetchall()]
            return []
    except Exception as e:
        log(f"DB error: {e}", "ERROR")
        return []


# ── Step 1: Read current accuracy ──
def get_accuracy_snapshot(hours=24):
    """Get accuracy per pipeline per sector from recent eval_results."""
    rows = db_query("""
        SELECT pipeline, sector,
               COUNT(*) as total,
               SUM(CASE WHEN classification = 'GOOD' THEN 1 ELSE 0 END) as good
        FROM eval_results
        WHERE created_at > NOW() - INTERVAL '%s hours'
          AND pipeline IS NOT NULL
          AND sector IS NOT NULL
        GROUP BY pipeline, sector
        ORDER BY pipeline, sector
    """, (hours,))

    snapshot = {}
    for r in rows:
        p = r["pipeline"]
        s = r["sector"]
        total = r["total"]
        good = r["good"]
        acc = round(100 * good / max(total, 1), 1)
        target = TARGETS.get(p, {}).get(s, 80)
        gap = round(acc - target, 1)

        if p not in snapshot:
            snapshot[p] = {}
        snapshot[p][s] = {
            "accuracy": acc,
            "total": total,
            "good": good,
            "target": target,
            "gap": gap,
        }

    return snapshot


# ── Step 2: Identify weakest point ──
def find_weakest(snapshot):
    """Find the pipeline/sector with the largest negative gap."""
    worst = None
    worst_gap = 0

    for pipeline, sectors in snapshot.items():
        for sector, data in sectors.items():
            if data["total"] < 10:
                continue  # Not enough data for reliable signal
            if data["gap"] < worst_gap:
                worst_gap = data["gap"]
                worst = {
                    "pipeline": pipeline,
                    "sector": sector,
                    **data,
                }

    return worst


# ── Step 3: Analyze failure patterns ──
def analyze_failures(pipeline, sector, limit=20):
    """Get recent failed questions to understand WHY they fail."""
    rows = db_query("""
        SELECT question, answer_preview, classification, total_score,
               failure_type, suggested_fix, category
        FROM eval_results
        WHERE pipeline = %s AND sector = %s
          AND classification != 'GOOD'
          AND created_at > NOW() - INTERVAL '48 hours'
        ORDER BY created_at DESC
        LIMIT %s
    """, (pipeline, sector, limit))

    patterns = defaultdict(int)
    for r in rows:
        ft = (r.get("failure_type") or "").upper()
        resp = (r.get("answer_preview") or "").lower()

        if ft:
            patterns[ft] += 1
        elif not resp or len(resp) < 20:
            patterns["EMPTY_RESPONSE"] += 1
        elif "je ne sais pas" in resp or "i don't know" in resp or "no relevant" in resp:
            patterns["NO_DATA"] += 1
        elif "error" in resp or "timeout" in resp:
            patterns["PIPELINE_ERROR"] += 1
        else:
            patterns["WRONG_ANSWER"] += 1

    return {
        "failed_questions": rows,
        "patterns": dict(patterns),
        "dominant_pattern": max(patterns, key=patterns.get) if patterns else "UNKNOWN",
    }


# ── Step 4: Form hypothesis ──
def form_hypothesis(weakness, failure_analysis):
    """Determine what action to take based on failure patterns."""
    pattern = failure_analysis["dominant_pattern"]
    pipeline = weakness["pipeline"]
    sector = weakness["sector"]

    if pattern == "NO_DATA":
        return {
            "type": "DATA_GAP",
            "action": f"Targeted ingestion for {sector} via n8n",
            "detail": f"{sector} has insufficient data for {pipeline} queries. "
                      f"Need more domain documents ingested and enriched.",
            "auto_fixable": True,
        }
    elif pattern == "EMPTY_RESPONSE":
        return {
            "type": "PIPELINE_BUG",
            "action": f"Check {pipeline} pipeline health on n8n",
            "detail": f"{pipeline} returning empty responses for {sector}. "
                      f"Possible node error or timeout in n8n workflow.",
            "auto_fixable": False,
        }
    elif pattern == "PIPELINE_ERROR":
        return {
            "type": "INFRA_ISSUE",
            "action": f"Debug {pipeline} errors",
            "detail": f"{pipeline} throwing errors for {sector}. "
                      f"Check n8n execution logs.",
            "auto_fixable": False,
        }
    elif pattern == "WRONG_ANSWER":
        return {
            "type": "QUALITY_GAP",
            "action": f"Improve retrieval quality for {sector} in {pipeline}",
            "detail": f"{pipeline} returns answers but they're wrong for {sector}. "
                      f"Likely needs better embeddings, more data, or prompt tuning.",
            "auto_fixable": True,  # Can improve via more/better data
        }
    else:
        return {
            "type": "UNKNOWN",
            "action": "Manual investigation needed",
            "detail": f"Cannot determine failure pattern for {pipeline}/{sector}",
            "auto_fixable": False,
        }


# ── Step 5: Execute improvement ──
def execute_data_improvement(sector, max_docs=10):
    """Targeted ingestion: Tavily search + n8n ingest for weak sector."""
    if not TAVILY_API_KEY:
        log("TAVILY_API_KEY not set, skipping ingestion", "WARN")
        return 0

    queries = TARGETED_QUERIES.get(sector, [])
    if not queries:
        log(f"No targeted queries for {sector}", "WARN")
        return 0

    total_ingested = 0
    for query in queries[:2]:  # Max 2 queries per cycle
        if _shutdown:
            break
        log(f"Tavily search: {query[:50]}... ({sector})", "ACTION")

        # Tavily search
        payload = json.dumps({
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "advanced",
            "include_raw_content": True,
            "max_results": 5,
        }).encode()

        try:
            req = request.Request(
                "https://api.tavily.com/search",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                results = data.get("results", [])
        except Exception as e:
            log(f"Tavily error: {e}", "ERROR")
            continue

        # Send each result to n8n ingestion
        for r in results:
            if _shutdown:
                break
            content = r.get("raw_content") or r.get("content", "")
            if not content or len(content) < 100:
                continue

            import base64
            import hashlib
            doc_id = hashlib.sha256(f"{sector}:{r.get('url', '')}".encode()).hexdigest()[:32]

            ingest_payload = json.dumps({
                "documentId": doc_id,
                "filename": (r.get("title", "document")[:80] + ".html"),
                "content_base64": base64.b64encode(content.encode()).decode(),
                "source": "improver-targeted",
                "tenant_id": sector,
                "metadata": {
                    "sector": sector,
                    "source_url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "origin": "agent-improver",
                    "improvement_target": True,
                }
            }).encode()

            try:
                req = request.Request(
                    INGEST_WEBHOOK, data=ingest_payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with request.urlopen(req, timeout=30) as resp:
                    total_ingested += 1
                    log(f"  Ingested: {r.get('title', '?')[:50]}...")

                # Also trigger enrichment
                enrich_payload = json.dumps({
                    "doc_id": doc_id,
                    "sector": sector,
                    "source": "improver",
                }).encode()
                req2 = request.Request(
                    ENRICH_WEBHOOK, data=enrich_payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                try:
                    with request.urlopen(req2, timeout=30):
                        pass
                except Exception:
                    pass  # Enrichment 500 is expected (fire-and-forget)

            except Exception as e:
                log(f"  Ingest error: {e}", "ERROR")

            time.sleep(2)
        time.sleep(1.5)

    log(f"Targeted ingestion: {total_ingested} docs for {sector}", "ACTION")
    return total_ingested


# ── Step 6: Run quick eval ──
def run_quick_eval(pipeline, sector, questions=5):
    """Run quick-test to measure improvement."""
    import subprocess
    cmd = [
        sys.executable, os.path.join(REPO_ROOT, "eval", "quick-test.py"),
        "--pipelines", pipeline,
        "--questions", str(questions),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                env={**os.environ, "PYTHONUNBUFFERED": "1"})
        output = result.stdout + result.stderr
        # Parse pass/fail from output
        for line in output.split("\n"):
            if "PASS" in line or "FAIL" in line:
                log(f"  Eval: {line.strip()}")
        return output
    except Exception as e:
        log(f"Quick eval error: {e}", "ERROR")
        return ""


# ── Main cycle ──
def run_improvement_cycle(focus_sector=None):
    """One full improvement cycle."""
    log("=" * 60)
    log("IMPROVEMENT CYCLE")
    log("=" * 60)

    # Step 1: Baseline
    log("Step 1: Reading accuracy baseline...")
    snapshot = get_accuracy_snapshot(hours=48)

    if not snapshot:
        log("No eval results found. Run eval-blast first.", "WARN")
        return None

    # Print current state
    for pipeline, sectors in sorted(snapshot.items()):
        for sector, data in sorted(sectors.items()):
            marker = "OK" if data["gap"] >= 0 else f"GAP {data['gap']}%"
            log(f"  {pipeline}/{sector}: {data['accuracy']}% ({data['total']}q) [{marker}]")

    # Step 2: Find weakest
    if focus_sector:
        # Filter to focus sector
        filtered = {}
        for p, sectors in snapshot.items():
            if focus_sector in sectors:
                filtered[p] = {focus_sector: sectors[focus_sector]}
        weakness = find_weakest(filtered) if filtered else find_weakest(snapshot)
    else:
        weakness = find_weakest(snapshot)

    if not weakness:
        log("All pipelines at or above target! Nothing to improve.", "INFO")
        return {"status": "all_good"}

    log(f"Step 2: Weakest point → {weakness['pipeline']}/{weakness['sector']} "
        f"at {weakness['accuracy']}% (target {weakness['target']}%, gap {weakness['gap']}%)")

    # Step 3: Analyze failures
    log("Step 3: Analyzing failure patterns...")
    failures = analyze_failures(weakness["pipeline"], weakness["sector"])
    log(f"  Patterns: {failures['patterns']}")
    log(f"  Dominant: {failures['dominant_pattern']}")

    # Step 4: Hypothesis
    log("Step 4: Forming hypothesis...")
    hypothesis = form_hypothesis(weakness, failures)
    log(f"  Type: {hypothesis['type']}")
    log(f"  Action: {hypothesis['action']}")
    log(f"  Auto-fixable: {hypothesis['auto_fixable']}")

    # Step 5: Execute
    docs_ingested = 0
    if hypothesis["auto_fixable"] and hypothesis["type"] in ("DATA_GAP", "QUALITY_GAP"):
        log("Step 5: Executing targeted data improvement...")
        docs_ingested = execute_data_improvement(weakness["sector"])
    else:
        log(f"Step 5: MANUAL ACTION NEEDED — {hypothesis['detail']}", "WARN")

    # Build report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "weakness": weakness,
        "failure_patterns": failures["patterns"],
        "dominant_pattern": failures["dominant_pattern"],
        "hypothesis": hypothesis,
        "action_taken": {
            "docs_ingested": docs_ingested,
            "auto_fixed": hypothesis["auto_fixable"],
        },
        "snapshot": {p: {s: d["accuracy"] for s, d in sectors.items()} for p, sectors in snapshot.items()},
    }

    # Save report
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_file = os.path.join(REPORT_DIR, f"improve-{ts}.json")
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    log(f"Report saved: {report_file}")

    log("=" * 60)
    log(f"CYCLE DONE: {weakness['pipeline']}/{weakness['sector']} "
        f"({weakness['accuracy']}% → target {weakness['target']}%) "
        f"| {docs_ingested} docs ingested")
    log("=" * 60)

    return report


def main():
    parser = argparse.ArgumentParser(description="Agent Improver — autoresearch pipeline optimization")
    parser.add_argument("--daemon", type=int, help="Run as daemon with interval (seconds)")
    parser.add_argument("--sector", type=str, help="Focus on specific sector")
    args = parser.parse_args()

    if args.daemon:
        log(f"DAEMON MODE: every {args.daemon}s")
        while not _shutdown:
            try:
                run_improvement_cycle(focus_sector=args.sector)
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
                import traceback
                traceback.print_exc()
            if _shutdown:
                break
            log(f"Next cycle in {args.daemon}s")
            elapsed = 0
            while not _shutdown and elapsed < args.daemon:
                time.sleep(5)
                elapsed += 5
        log("Daemon stopped")
    else:
        run_improvement_cycle(focus_sector=args.sector)


if __name__ == "__main__":
    main()
