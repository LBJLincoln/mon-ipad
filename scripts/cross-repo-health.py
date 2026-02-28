#!/usr/bin/env python3
"""
Cross-Repo Health — Live health analysis across all 7 repos + infrastructure.
=============================================================================
Checks CI status, Vercel deployments, HF Space, n8n webhooks, databases,
and pipeline health. Outputs a unified JSON report for the dashboard.

Usage:
  python3 scripts/cross-repo-health.py                # Full check, save report
  python3 scripts/cross-repo-health.py --quick         # Fast check (skip slow tests)
  python3 scripts/cross-repo-health.py --json          # JSON to stdout
  python3 scripts/cross-repo-health.py --push          # Push to rag-dashboard
  python3 scripts/cross-repo-health.py --continuous    # Run every 5 min

Output files:
  docs/cross-repo-health.json   — Full report (dashboard data source)
  docs/status.json              — Updated with cross-repo section

Last updated: 2026-02-28
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Paths ────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "cross-repo-health.json")
STATUS_JSON = os.path.join(REPO_ROOT, "docs", "status.json")

# ─── Load .env.local ──────────────────────────────────────────────
def _load_env():
    env_file = os.path.join(REPO_ROOT, ".env.local")
    if not os.path.exists(env_file):
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

_load_env()

N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

# ═══════════════════════════════════════════════════════════════════
# Configuration — All repos, endpoints, services
# ═══════════════════════════════════════════════════════════════════

REPOS = {
    "mon-ipad": {
        "remote": "origin",
        "github": "LBJLincoln/mon-ipad",
        "role": "Control tower — directives, eval scripts, MCP configs",
        "has_ci": True,
        "ci_workflows": ["Eval 1000q Parallel"],
    },
    "rag-tests": {
        "remote": "rag-tests",
        "github": "LBJLincoln/rag-tests",
        "role": "Eval scripts, datasets, test results",
        "has_ci": True,
        "ci_workflows": ["CI - RAG Tests"],
    },
    "rag-website": {
        "remote": "rag-website",
        "github": "LBJLincoln/rag-website",
        "role": "Next.js 14 — 4 sector sites + chatbots",
        "has_ci": False,
        "vercel_url": "https://nomos-ai-pied.vercel.app",
    },
    "rag-dashboard": {
        "remote": "rag-dashboard",
        "github": "LBJLincoln/rag-dashboard",
        "role": "Live metrics dashboard (HTML/JS)",
        "has_ci": False,
        "vercel_url": "https://nomos-dashboard-alexis-morets-projects.vercel.app",
    },
    "rag-pme-connectors": {
        "remote": "rag-pme-connectors",
        "github": "LBJLincoln/rag-pme-connectors",
        "role": "Next.js 15 — 15 PME apps + MacBook chat",
        "has_ci": True,
        "ci_workflows": ["Deploy Website to Vercel"],
        "vercel_url": "https://nomos-pme-connectors-alexis-morets-projects.vercel.app",
    },
    "rag-pme-usecases": {
        "remote": "rag-pme-usecases",
        "github": "LBJLincoln/rag-pme-usecases",
        "role": "Next.js 14 — 200 use cases",
        "has_ci": False,
        "vercel_url": "https://nomos-pme-usecases-alexis-morets-projects.vercel.app",
    },
    "rag-data-ingestion": {
        "remote": "rag-data-ingestion",
        "github": "LBJLincoln/rag-data-ingestion",
        "role": "Ingestion V3.1 + Enrichissement V3.1",
        "has_ci": False,
    },
}

PIPELINES = {
    "standard": {
        "webhook": "/webhook/rag-multi-index-v3",
        "workflow_id": "TmgyRP20N4JFd9CB",
        "target_accuracy": 85.0,
    },
    "graph": {
        "webhook": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "workflow_id": "6257AfT1l4FMC6lY",
        "target_accuracy": 70.0,
    },
    "quantitative": {
        "webhook": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "workflow_id": "E19NZG9WfM7FNsxr",
        "target_accuracy": 85.0,
    },
    "orchestrator": {
        "webhook": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
        "workflow_id": "ALd4gOEqiKL5KR1p",
        "target_accuracy": 70.0,
    },
}

VERCEL_SITES = {
    "ETI 4 Sectors": "https://nomos-ai-pied.vercel.app",
    "PME Connectors": "https://nomos-pme-connectors-alexis-morets-projects.vercel.app",
    "PME Use Cases": "https://nomos-pme-usecases-alexis-morets-projects.vercel.app",
    "Dashboard": "https://nomos-dashboard-alexis-morets-projects.vercel.app",
}

DATABASES = {
    "pinecone_primary": {
        "type": "pinecone",
        "index": "sota-rag-jina-1024",
        "expected_vectors_min": 10000,
    },
    "pinecone_graph": {
        "type": "pinecone",
        "index": "sota-rag-phase2-graph",
        "expected_vectors_min": 1000,
    },
    "neo4j": {
        "type": "neo4j",
        "expected_nodes_min": 15000,
    },
    "supabase": {
        "type": "supabase",
        "expected_tables_min": 30,
    },
}


# ═══════════════════════════════════════════════════════════════════
# HTTP Helper
# ═══════════════════════════════════════════════════════════════════

def http_check(url, method="GET", timeout=15, data=None) -> dict:
    """Quick HTTP check — returns status_code, latency, error."""
    headers = {"User-Agent": "CrossRepoHealth/1.0"}
    body = None
    if data:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "healthy": True,
            "status_code": resp.status,
            "latency_ms": latency_ms,
        }
    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "healthy": e.code < 500,
            "status_code": e.code,
            "latency_ms": latency_ms,
            "error": f"HTTP {e.code}",
        }
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        return {
            "healthy": False,
            "status_code": 0,
            "latency_ms": latency_ms,
            "error": str(e)[:200],
        }


def gh_api(endpoint, timeout=15) -> dict:
    """Call GitHub API via gh CLI (handles auth)."""
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        return {}
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════════════
# Check Functions
# ═══════════════════════════════════════════════════════════════════

def check_repo_git(repo_name: str, config: dict) -> dict:
    """Check git status for a repo: last commit, branch, sync status."""
    github = config["github"]

    # Get last commit via GitHub API
    commits = gh_api(f"repos/{github}/commits?per_page=1")
    if isinstance(commits, list) and commits:
        last_commit = commits[0]
        sha = last_commit.get("sha", "")[:7]
        message = last_commit.get("commit", {}).get("message", "").split("\n")[0][:60]
        date = last_commit.get("commit", {}).get("committer", {}).get("date", "")
    else:
        sha, message, date = "?", "?", ""

    # Check if local remote is in sync
    local_check = "N/A"
    remote = config.get("remote", "")
    if remote:
        try:
            result = subprocess.run(
                ["git", "rev-parse", f"{remote}/main"],
                capture_output=True, text=True, timeout=5,
                cwd=REPO_ROOT,
            )
            if result.returncode == 0:
                local_sha = result.stdout.strip()[:7]
                local_check = "in_sync" if local_sha == sha else "behind"
        except Exception:
            pass

    # Days since last commit
    days_stale = 999
    if date:
        try:
            commit_dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
            days_stale = (datetime.now(timezone.utc) - commit_dt).days
        except Exception:
            pass

    return {
        "repo": repo_name,
        "role": config.get("role", ""),
        "last_commit_sha": sha,
        "last_commit_msg": message,
        "last_commit_date": date,
        "days_since_commit": days_stale,
        "local_sync": local_check,
        "stale": days_stale > 7,
    }


def check_ci_status(repo_name: str, config: dict) -> dict:
    """Check CI/CD status via GitHub Actions API."""
    if not config.get("has_ci"):
        return {"status": "no_ci", "workflows": []}

    github = config["github"]
    runs_data = gh_api(f"repos/{github}/actions/runs?per_page=5")
    runs = runs_data.get("workflow_runs", []) if isinstance(runs_data, dict) else []

    workflows = []
    for run in runs[:5]:
        workflows.append({
            "name": run.get("name", "?"),
            "status": run.get("status", "?"),
            "conclusion": run.get("conclusion", "?"),
            "updated_at": run.get("updated_at", ""),
            "run_number": run.get("run_number", 0),
        })

    # Overall CI health: latest run of each expected workflow
    expected = config.get("ci_workflows", [])
    ci_healthy = True
    for wf_name in expected:
        matching = [w for w in workflows if w["name"] == wf_name]
        if matching:
            if matching[0]["conclusion"] not in ("success", None):
                ci_healthy = False
        else:
            ci_healthy = False  # workflow not found

    return {
        "status": "healthy" if ci_healthy else "failing",
        "healthy": ci_healthy,
        "workflows": workflows[:3],
        "expected_workflows": expected,
    }


def check_vercel_site(name: str, url: str) -> dict:
    """Check a Vercel deployment health."""
    result = http_check(url, timeout=15)
    result["name"] = name
    result["url"] = url
    return result


def check_hf_space() -> dict:
    """Check HF Space n8n health."""
    # Health endpoint
    healthz = http_check(f"{N8N_HOST}/healthz", timeout=15)

    return {
        "url": N8N_HOST,
        "healthz": healthz,
        "healthy": healthz.get("healthy", False),
    }


def check_webhook(pipeline: str, config: dict) -> dict:
    """Check a pipeline webhook with a test POST."""
    url = f"{N8N_HOST}{config['webhook']}"
    result = http_check(
        url, method="POST", timeout=30,
        data={"query": "health check", "tenant_id": "health"},
    )
    result["pipeline"] = pipeline
    result["webhook"] = config["webhook"]
    return result


def check_pinecone(db_config: dict) -> dict:
    """Check Pinecone index via MCP or API."""
    index_name = db_config["index"]
    try:
        result = subprocess.run(
            ["python3", "-c", f"""
import json, os
from pinecone import Pinecone
pc = Pinecone(api_key=os.environ.get('PINECONE_API_KEY', ''))
idx = pc.Index('{index_name}')
stats = idx.describe_index_stats()
print(json.dumps({{"vectors": stats.total_vector_count, "dimension": stats.dimension}}))
"""],
            capture_output=True, text=True, timeout=15,
            cwd=REPO_ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            vectors = data.get("vectors", 0)
            return {
                "index": index_name,
                "healthy": vectors >= db_config.get("expected_vectors_min", 0),
                "vectors": vectors,
                "dimension": data.get("dimension", 0),
            }
    except Exception:
        pass

    # Fallback: use known cached data
    return {
        "index": index_name,
        "healthy": None,
        "vectors": "unknown",
        "note": "Could not connect (API key or library missing)",
    }


def check_neo4j() -> dict:
    """Check Neo4j via MCP read-cypher."""
    try:
        result = subprocess.run(
            ["python3", "-c", """
import json, os, urllib.request
# Quick count via Neo4j HTTP API
url = os.environ.get('NEO4J_URI', '').replace('neo4j+s://', 'https://') + '/db/neo4j/query/v2'
if not url or url == '/db/neo4j/query/v2':
    print(json.dumps({"healthy": None, "note": "NEO4J_URI not set"}))
else:
    data = json.dumps({"statements": [{"statement": "MATCH (n) RETURN count(n) as c"}]}).encode()
    headers = {"Content-Type": "application/json"}
    user = os.environ.get('NEO4J_USERNAME', 'neo4j')
    pw = os.environ.get('NEO4J_PASSWORD', '')
    import base64
    auth = base64.b64encode(f"{user}:{pw}".encode()).decode()
    headers["Authorization"] = f"Basic {auth}"
    req = urllib.request.Request(url, data=data, headers=headers)
    resp = urllib.request.urlopen(req, timeout=10)
    print(json.dumps({"healthy": True, "status": resp.status}))
"""],
            capture_output=True, text=True, timeout=15,
            cwd=REPO_ROOT, env={**os.environ},
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except Exception:
        pass

    return {"healthy": None, "note": "Could not check (env vars missing)"}


def check_supabase() -> dict:
    """Check Supabase via SQL."""
    try:
        result = subprocess.run(
            ["python3", "-c", """
import json, os
# Use psycopg2 or pg8000 if available
try:
    import pg8000
    conn = pg8000.connect(
        host=os.environ.get('SUPABASE_DB_HOST', 'aws-1-eu-west-1.pooler.supabase.com'),
        port=int(os.environ.get('SUPABASE_DB_PORT', '6543')),
        user=os.environ.get('SUPABASE_DB_USER', ''),
        password=os.environ.get('SUPABASE_DB_PASSWORD', ''),
        database=os.environ.get('SUPABASE_DB_NAME', 'postgres'),
        ssl_context=True,
    )
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
    count = cur.fetchone()[0]
    conn.close()
    print(json.dumps({"healthy": True, "tables": count}))
except ImportError:
    print(json.dumps({"healthy": None, "note": "pg8000 not installed"}))
except Exception as e:
    print(json.dumps({"healthy": False, "error": str(e)[:200]}))
"""],
            capture_output=True, text=True, timeout=15,
            cwd=REPO_ROOT, env={**os.environ},
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except Exception:
        pass

    return {"healthy": None, "note": "Could not check"}


def get_pipeline_metrics() -> dict:
    """Load current pipeline accuracy from status.json."""
    if os.path.exists(STATUS_JSON):
        try:
            with open(STATUS_JSON) as f:
                data = json.load(f)
            return data.get("pipelines", {})
        except Exception:
            pass
    return {}


def load_doctor_report() -> dict:
    """Load the latest pipeline-doctor report if available."""
    doctor_report = os.path.join(REPO_ROOT, "logs", "pipeline-doctor-report.json")
    if os.path.exists(doctor_report):
        try:
            with open(doctor_report) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ═══════════════════════════════════════════════════════════════════
# Health Score Aggregation
# ═══════════════════════════════════════════════════════════════════

def compute_overall_health(report: dict) -> dict:
    """Compute a single overall health score (0-100) from all checks."""
    scores = {}
    weights = {
        "repos": 0.10,
        "ci": 0.15,
        "vercel": 0.10,
        "hf_space": 0.15,
        "webhooks": 0.25,
        "databases": 0.10,
        "pipelines": 0.15,
    }

    # Repos: % not stale
    repos = report.get("repos", {})
    if repos:
        total = len(repos)
        not_stale = sum(1 for r in repos.values() if not r.get("stale", True))
        scores["repos"] = (not_stale / total * 100) if total > 0 else 0

    # CI: % healthy
    ci = report.get("ci", {})
    if ci:
        ci_repos = [c for c in ci.values() if c.get("status") != "no_ci"]
        if ci_repos:
            healthy = sum(1 for c in ci_repos if c.get("healthy", False))
            scores["ci"] = (healthy / len(ci_repos) * 100)
        else:
            scores["ci"] = 100  # no CI = neutral

    # Vercel: % healthy (200)
    vercel = report.get("vercel", {})
    if vercel:
        total = len(vercel)
        healthy = sum(1 for v in vercel.values() if v.get("healthy", False))
        scores["vercel"] = (healthy / total * 100) if total > 0 else 0

    # HF Space
    hf = report.get("hf_space", {})
    scores["hf_space"] = 100 if hf.get("healthy", False) else 0

    # Webhooks: % healthy
    webhooks = report.get("webhooks", {})
    if webhooks:
        total = len(webhooks)
        healthy = sum(1 for w in webhooks.values() if w.get("healthy", False))
        scores["webhooks"] = (healthy / total * 100) if total > 0 else 0

    # Databases: % healthy (skip unknowns)
    dbs = report.get("databases", {})
    if dbs:
        known = [d for d in dbs.values() if d.get("healthy") is not None]
        if known:
            healthy = sum(1 for d in known if d.get("healthy", False))
            scores["databases"] = (healthy / len(known) * 100)
        else:
            scores["databases"] = 50  # all unknown = neutral

    # Pipelines: avg accuracy vs target
    pipelines = report.get("pipeline_metrics", {})
    if pipelines:
        acc_ratios = []
        for pipe, data in pipelines.items():
            if isinstance(data, dict) and "accuracy" in data and "target" in data:
                ratio = min(data["accuracy"] / data["target"], 1.0) if data["target"] > 0 else 0
                acc_ratios.append(ratio)
        scores["pipelines"] = (sum(acc_ratios) / len(acc_ratios) * 100) if acc_ratios else 0

    # Weighted total
    total = 0
    for key, weight in weights.items():
        total += scores.get(key, 50) * weight  # default 50 if no data

    # Count critical issues
    critical = 0
    if not hf.get("healthy", False):
        critical += 1
    for w in webhooks.values():
        if not w.get("healthy", False):
            critical += 1
    for c in ci.values():
        if c.get("status") not in ("no_ci", "healthy"):
            critical += 1

    # Status
    if total >= 80 and critical == 0:
        status = "HEALTHY"
    elif total >= 50:
        status = "DEGRADED"
    else:
        status = "CRITICAL"

    return {
        "score": round(total, 1),
        "status": status,
        "critical_issues": critical,
        "component_scores": {k: round(v, 1) for k, v in scores.items()},
        "weights": weights,
    }


# ═══════════════════════════════════════════════════════════════════
# Main Report Builder
# ═══════════════════════════════════════════════════════════════════

def build_report(quick=False) -> dict:
    """Build the full cross-repo health report."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "repos": {},
        "ci": {},
        "vercel": {},
        "hf_space": {},
        "webhooks": {},
        "databases": {},
        "pipeline_metrics": {},
        "doctor_report": {},
        "overall": {},
    }

    # ── 1. Git repos (parallel) ──────────────────────────────
    print("  [1/7] Checking git repos...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(check_repo_git, name, cfg): name for name, cfg in REPOS.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                report["repos"][name] = future.result()
            except Exception as e:
                report["repos"][name] = {"repo": name, "error": str(e)[:200]}

    active = sum(1 for r in report["repos"].values() if not r.get("stale", True))
    stale = sum(1 for r in report["repos"].values() if r.get("stale", True))
    print(f"    {active} active, {stale} stale (>7 days)")

    # ── 2. CI status (parallel) ──────────────────────────────
    print("  [2/7] Checking CI/CD status...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(check_ci_status, name, cfg): name for name, cfg in REPOS.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                report["ci"][name] = future.result()
            except Exception as e:
                report["ci"][name] = {"status": "error", "error": str(e)[:200]}

    ci_health = sum(1 for c in report["ci"].values() if c.get("healthy", False))
    ci_repos = sum(1 for c in report["ci"].values() if c.get("status") != "no_ci")
    print(f"    {ci_health}/{ci_repos} CI pipelines healthy")

    # ── 3. Vercel deployments (parallel) ─────────────────────
    print("  [3/7] Checking Vercel deployments...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(check_vercel_site, name, url): name for name, url in VERCEL_SITES.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                report["vercel"][name] = future.result()
            except Exception as e:
                report["vercel"][name] = {"name": name, "healthy": False, "error": str(e)[:200]}

    vercel_up = sum(1 for v in report["vercel"].values() if v.get("healthy", False))
    print(f"    {vercel_up}/{len(VERCEL_SITES)} sites live")

    # ── 4. HF Space ──────────────────────────────────────────
    print("  [4/7] Checking HF Space...")
    report["hf_space"] = check_hf_space()
    hf_status = "UP" if report["hf_space"].get("healthy") else "DOWN"
    print(f"    HF Space: {hf_status}")

    # ── 5. Webhooks (sequential — avoid overwhelming n8n) ───
    print("  [5/7] Checking webhooks...")
    if not quick:
        for pipeline, config in PIPELINES.items():
            result = check_webhook(pipeline, config)
            report["webhooks"][pipeline] = result
            icon = "[+]" if result.get("healthy") else "[-]"
            print(f"    {icon} {pipeline}: HTTP {result.get('status_code', '?')} ({result.get('latency_ms', '?')}ms)")
            time.sleep(1)  # rate-limit
    else:
        print("    (skipped in quick mode)")

    # ── 6. Databases ─────────────────────────────────────────
    print("  [6/7] Checking databases...")
    if not quick:
        # Pinecone — use MCP tools
        for db_name, db_cfg in DATABASES.items():
            if db_cfg["type"] == "pinecone":
                report["databases"][db_name] = check_pinecone(db_cfg)
            elif db_cfg["type"] == "neo4j":
                report["databases"][db_name] = check_neo4j()
            elif db_cfg["type"] == "supabase":
                report["databases"][db_name] = check_supabase()

        for name, db in report["databases"].items():
            h = db.get("healthy")
            icon = "[+]" if h else ("[-]" if h is False else "[?]")
            extra = ""
            if "vectors" in db:
                extra = f" ({db['vectors']} vectors)"
            elif "tables" in db:
                extra = f" ({db['tables']} tables)"
            print(f"    {icon} {name}{extra}")
    else:
        print("    (skipped in quick mode)")

    # ── 7. Pipeline metrics (from status.json + doctor) ──────
    print("  [7/7] Loading pipeline metrics...")
    report["pipeline_metrics"] = get_pipeline_metrics()
    report["doctor_report"] = load_doctor_report()

    for pipe, data in report["pipeline_metrics"].items():
        if isinstance(data, dict):
            acc = data.get("accuracy", 0)
            target = data.get("target", 0)
            met = data.get("met", False)
            icon = "[+]" if met else "[-]"
            print(f"    {icon} {pipe}: {acc}% (target: {target}%)")

    # ── Compute overall health ────────────────────────────────
    report["overall"] = compute_overall_health(report)

    return report


def print_summary(report: dict):
    """Print a human-readable summary."""
    overall = report.get("overall", {})
    score = overall.get("score", 0)
    status = overall.get("status", "?")
    critical = overall.get("critical_issues", 0)

    print(f"\n{'='*60}")
    print(f"  CROSS-REPO HEALTH — {status}")
    print(f"  Overall Score: {score:.1f}/100")
    if critical > 0:
        print(f"  Critical Issues: {critical}")
    print(f"{'='*60}")

    components = overall.get("component_scores", {})
    for comp, score_val in components.items():
        bar_len = int(score_val / 5)  # 20 chars max
        bar = "#" * bar_len + "." * (20 - bar_len)
        print(f"  {comp:15s} [{bar}] {score_val:5.1f}")

    # Quick repo summary
    print(f"\n  Repos:")
    for name, data in report.get("repos", {}).items():
        stale_icon = " (STALE)" if data.get("stale") else ""
        ci = report.get("ci", {}).get(name, {})
        ci_status = ci.get("status", "?")
        vercel = ""
        for v_name, v_data in report.get("vercel", {}).items():
            # Match vercel to repo
            repo_cfg = REPOS.get(name, {})
            if repo_cfg.get("vercel_url") and v_data.get("url") == repo_cfg["vercel_url"]:
                vercel = f" | vercel: {'UP' if v_data.get('healthy') else 'DOWN'}"
        print(f"    {name:25s} | ci: {ci_status:8s} | {data.get('last_commit_sha', '?'):7s} {data.get('days_since_commit', '?')}d ago{stale_icon}{vercel}")

    # Webhook summary
    if report.get("webhooks"):
        print(f"\n  Webhooks:")
        for pipe, data in report["webhooks"].items():
            icon = "[+]" if data.get("healthy") else "[-]"
            print(f"    {icon} {pipe:15s} | HTTP {str(data.get('status_code', '?')):>3s} | {data.get('latency_ms', '?')}ms")

    print()


def update_status_json(report: dict):
    """Inject cross-repo health section into docs/status.json."""
    if not os.path.exists(STATUS_JSON):
        return

    try:
        with open(STATUS_JSON) as f:
            status = json.load(f)
    except Exception:
        return

    # Add cross-repo section
    status["cross_repo_health"] = {
        "generated_at": report.get("generated_at", ""),
        "overall_score": report.get("overall", {}).get("score", 0),
        "overall_status": report.get("overall", {}).get("status", "?"),
        "critical_issues": report.get("overall", {}).get("critical_issues", 0),
        "component_scores": report.get("overall", {}).get("component_scores", {}),
        "repos_summary": {
            name: {
                "stale": data.get("stale", True),
                "days_since_commit": data.get("days_since_commit", 999),
                "ci_status": report.get("ci", {}).get(name, {}).get("status", "unknown"),
            }
            for name, data in report.get("repos", {}).items()
        },
        "vercel_sites": {
            name: {"healthy": data.get("healthy", False), "latency_ms": data.get("latency_ms", 0)}
            for name, data in report.get("vercel", {}).items()
        },
        "webhooks": {
            pipe: {"healthy": data.get("healthy", False), "latency_ms": data.get("latency_ms", 0)}
            for pipe, data in report.get("webhooks", {}).items()
        },
        "hf_space_healthy": report.get("hf_space", {}).get("healthy", False),
    }

    with open(STATUS_JSON, "w") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def push_to_dashboard(report: dict):
    """Push cross-repo-health.json and status.json to rag-dashboard repo."""
    # Copy health report to rag-dashboard
    dash_dir = os.path.join(REPO_ROOT, "docs")

    # Save to docs/
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Git operations for rag-dashboard
    try:
        # Create a temporary copy for pushing
        subprocess.run(
            ["git", "push", "rag-dashboard", "main"],
            capture_output=True, text=True, timeout=30,
            cwd=REPO_ROOT,
        )
        print("  Pushed to rag-dashboard remote")
    except Exception as e:
        print(f"  Warning: Could not push to rag-dashboard: {e}")


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Cross-Repo Health — Live analysis across all 7 repos + infrastructure",
    )
    parser.add_argument("--quick", "-q", action="store_true", help="Fast check (skip webhooks + DBs)")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("--push", action="store_true", help="Push results to rag-dashboard")
    parser.add_argument("--continuous", action="store_true", help="Run every 5 minutes")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between continuous runs (default: 300)")
    args = parser.parse_args()

    while True:
        print("=" * 60)
        print("  CROSS-REPO HEALTH v1.0")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Repos: {len(REPOS)} | Sites: {len(VERCEL_SITES)} | Pipelines: {len(PIPELINES)}")
        print("=" * 60)

        report = build_report(quick=args.quick)
        print_summary(report)

        # Save report
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"  Report saved: {REPORT_PATH}")

        # Update status.json
        update_status_json(report)
        print(f"  Updated: {STATUS_JSON}")

        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

        if args.push:
            push_to_dashboard(report)

        if not args.continuous:
            break

        print(f"\n  Next check in {args.interval}s...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
