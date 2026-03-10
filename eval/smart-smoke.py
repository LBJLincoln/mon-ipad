#!/usr/bin/env python3
"""Smart Smoke Test — Node-by-Node Regression Detection

Tests all pipelines in parallel with golden Q&A pairs (known correct answers),
captures per-node execution metrics from n8n API, compares current run vs
previous run node-by-node, and highlights regressions instantly.

Usage:
  python3 eval/smart-smoke.py                      # Run all pipelines
  python3 eval/smart-smoke.py --pipeline standard   # Run specific pipeline
  python3 eval/smart-smoke.py --compare             # Compare with last run
  python3 eval/smart-smoke.py --fix-mode            # Re-test after fix, show diff
  python3 eval/smart-smoke.py --loop 300            # Continuous every 5min
  python3 eval/smart-smoke.py --last                # Show last run results
  python3 eval/smart-smoke.py --history 5           # Show last N runs summary
"""

# ── IPv4 monkey-patch (GCP VM has broken IPv6) ───────────────────
import socket
from socket import AF_INET
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_only

import argparse
import http.cookiejar
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
SMOKE_DIR = REPO_ROOT / "data" / "smoke-tests"
SMOKE_DIR.mkdir(parents=True, exist_ok=True)

# ── ANSI colors ──────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"

def colored(text, color):
    return f"{color}{text}{C.RESET}"

# ── SSL context (permissive for HF proxy) ────────────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ── Space URLs & Credentials ────────────────────────────────────
SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

N8N_EMAIL = os.environ.get("N8N_CI_EMAIL", "ci@nomos.ai")
N8N_PASSWORD = os.environ.get("N8N_CI_PASSWORD", "CI-Nomos-2026!")

# ── Pipeline config ─────────────────────────────────────────────
PIPELINES = {
    "standard": {
        "webhook": "/webhook/rag-multi-index-v3",
        "workflow_id": "TmgyRP20N4JFd9CB",
        "spaces": ["S1", "S3", "S9"],  # deployed on 3 Spaces
    },
    "graph": {
        "webhook": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "workflow_id": "6257AfT1l4FMC6lY",
        "spaces": ["S1"],
    },
    "quant": {
        "webhook": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "workflow_id": "cjhEhVs0KV1ExHqX",
        "spaces": ["S9"],
    },
    "orchestrator": {
        "webhook": "/webhook/orchestrator-v2",
        "workflow_id": "qOSaFFrqO8Jb4VGb",
        "spaces": ["S1"],
    },
}

# ── Golden Q&A pairs ────────────────────────────────────────────
GOLDEN_QA = {
    "standard": [
        {
            "query": "Quel est le ratio de solvabilité Bâle III minimum requis pour les banques?",
            "sector": "finance",
            "tenant_id": "finance",
            "expected_keywords": ["8%", "CET1", "fonds propres", "Bâle III"],
            "expected_sources_min": 3,
        },
        {
            "query": "Quelles sont les principales normes DTU pour l'isolation thermique?",
            "sector": "btp",
            "tenant_id": "btp",
            "expected_keywords": ["DTU", "isolation", "thermique", "résistance"],
            "expected_sources_min": 2,
        },
        {
            "query": "Quels sont les délais de prescription en droit civil français?",
            "sector": "juridique",
            "tenant_id": "juridique",
            "expected_keywords": ["prescription", "Code civil", "ans", "délai"],
            "expected_sources_min": 2,
        },
    ],
    "graph": [
        {
            "query": "Quelles entités sont liées aux normes Eurocode pour le béton armé?",
            "sector": "btp",
            "tenant_id": "btp",
            "expected_keywords": ["Eurocode", "béton", "NF EN"],
            "expected_sources_min": 1,
        },
        {
            "query": "Quels sont les liens entre IFRS 9 et la gestion du risque crédit?",
            "sector": "finance",
            "tenant_id": "finance",
            "expected_keywords": ["IFRS", "risque", "crédit"],
            "expected_sources_min": 1,
        },
        {
            "query": "Quelles relations entre Code du travail et responsabilité employeur?",
            "sector": "juridique",
            "tenant_id": "juridique",
            "expected_keywords": ["Code du travail", "employeur", "responsabilité"],
            "expected_sources_min": 1,
        },
    ],
    "quant": [
        {
            "query": "Quel est le chiffre d'affaires de TotalEnergies en 2023?",
            "sector": "finance",
            "tenant_id": "finance",
            "expected_keywords": ["TotalEnergies", "chiffre", "2023"],
            "expected_sources_min": 0,
        },
        {
            "query": "Quel est le résultat net de BNP Paribas?",
            "sector": "finance",
            "tenant_id": "finance",
            "expected_keywords": ["BNP", "résultat", "net"],
            "expected_sources_min": 0,
        },
        {
            "query": "Compare la marge opérationnelle des banques françaises",
            "sector": "finance",
            "tenant_id": "finance",
            "expected_keywords": ["marge", "opérationnelle"],
            "expected_sources_min": 0,
        },
    ],
    "orchestrator": [
        {
            "query": "Quel est le taux de TVA applicable en BTP en France?",
            "sector": "btp",
            "tenant_id": "btp",
            "expected_keywords": ["TVA", "BTP", "10%", "20%"],
            "expected_sources_min": 1,
        },
        {
            "query": "Quelles sont les obligations RGPD pour les entreprises?",
            "sector": "juridique",
            "tenant_id": "juridique",
            "expected_keywords": ["RGPD", "données", "protection"],
            "expected_sources_min": 1,
        },
        {
            "query": "Quels indicateurs financiers utiliser pour évaluer une PME?",
            "sector": "finance",
            "tenant_id": "finance",
            "expected_keywords": ["EBE", "ratio", "trésorerie"],
            "expected_sources_min": 1,
        },
    ],
}


# ═══════════════════════════════════════════════════════════════════
#  n8n Client — Cookie-authenticated HTTP client per Space
# ═══════════════════════════════════════════════════════════════════

class N8nClient:
    """Cookie-authenticated HTTP client for one n8n HF Space."""

    def __init__(self, space_label, base_url):
        self.label = space_label
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPSHandler(context=_ssl_ctx),
        )
        self.logged_in = False

    def _request(self, method, path, data=None, timeout=30):
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            resp = self.opener.open(req, timeout=timeout)
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")[:500]
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, {"error": raw}
        except urllib.error.URLError as e:
            return 503, {"error": f"URLError: {e.reason}"}
        except Exception as e:
            return 0, {"error": str(e)[:300]}

    def login(self):
        status, _ = self._request("POST", "/rest/login", {
            "emailOrLdapLoginId": N8N_EMAIL,
            "password": N8N_PASSWORD,
        })
        if status == 200:
            self.logged_in = True
            return True
        return False

    def get_latest_execution(self, workflow_id):
        """Fetch the latest execution for a workflow, with full node data."""
        if not self.logged_in and not self.login():
            return None
        # Get latest execution ID
        path = f"/rest/executions?limit=1&workflowId={workflow_id}"
        status, resp = self._request("GET", path, timeout=30)
        if status != 200:
            return None
        data = resp.get("data", resp)
        if isinstance(data, dict):
            results = data.get("results", data.get("data", []))
        elif isinstance(data, list):
            results = data
        else:
            return None
        if not results:
            return None
        exec_id = results[0].get("id")
        if not exec_id:
            return None
        # Fetch full execution detail
        path2 = f"/rest/executions/{exec_id}"
        status2, resp2 = self._request("GET", path2, timeout=30)
        if status2 != 200:
            return None
        return resp2.get("data", resp2) if isinstance(resp2, dict) else resp2


# ═══════════════════════════════════════════════════════════════════
#  Node Metric Extraction
# ═══════════════════════════════════════════════════════════════════

def extract_node_metrics(execution_data):
    """Extract per-node metrics from an n8n execution detail object."""
    if not execution_data:
        return []
    run_data = execution_data.get("data", {}).get("resultData", {}).get("runData", {})
    if not run_data:
        return []

    nodes = []
    for node_name, runs in run_data.items():
        if not runs:
            continue
        run = runs[0]  # take first (usually only) run
        start_ts = run.get("startTime")
        exec_time_ms = run.get("executionTime", 0)
        status = "success"
        error_msg = None
        if run.get("error"):
            status = "error"
            err = run["error"]
            if isinstance(err, dict):
                error_msg = err.get("message", str(err))[:200]
            else:
                error_msg = str(err)[:200]

        # Estimate data size from output
        output_data = run.get("data", {})
        data_size = 0
        try:
            data_size = len(json.dumps(output_data, ensure_ascii=False))
        except (TypeError, ValueError):
            pass

        # Count output items
        item_count = 0
        if isinstance(output_data, dict):
            main = output_data.get("main", [])
            if isinstance(main, list):
                for branch in main:
                    if isinstance(branch, list):
                        item_count += len(branch)

        nodes.append({
            "name": node_name,
            "status": status,
            "exec_time_ms": exec_time_ms or 0,
            "data_size_bytes": data_size,
            "item_count": item_count,
            "error": error_msg,
            "type": _classify_node(node_name),
        })

    # Sort by execution order (start time) — fallback to name
    nodes.sort(key=lambda n: n["name"])
    return nodes


def _classify_node(name):
    """Classify node into functional category."""
    nl = name.lower()
    rules = [
        ("trigger", ["trigger", "webhook", "cron", "schedule", "manual"]),
        ("llm", ["llm", "generation", "chat", "completion", "gpt", "hyde",
                 "entity", "query decompos", "answer", "synthesis", "groq",
                 "openai", "gemini", "litellm"]),
        ("retrieval", ["pinecone", "neo4j", "supabase", "postgres", "search",
                       "query", "bm25", "embedding", "vector", "rerank", "e5"]),
        ("routing", ["router", "switch", "if ", "merge", "wait", "branch",
                     "decomposition", "orchestrat"]),
        ("transform", ["set ", "code", "function", "item", "split", "aggregate",
                       "filter", "transform", "map", "reduce", "edit fields",
                       "format", "parse"]),
        ("http", ["http", "api request", "fetch", "curl"]),
    ]
    for ntype, keywords in rules:
        for kw in keywords:
            if kw in nl:
                return ntype
    return "other"


# ═══════════════════════════════════════════════════════════════════
#  Webhook Caller
# ═══════════════════════════════════════════════════════════════════

def call_webhook(space_url, webhook_path, query, sector, tenant_id, timeout=90):
    """Call a pipeline webhook and return structured result."""
    url = f"{space_url}{webhook_path}"
    payload = json.dumps({
        "query": query,
        "tenant_id": tenant_id,
        "sector": sector,
        "top_k": 10,
        "include_sources": True,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    start = time.time()
    try:
        handler = urllib.request.HTTPSHandler(context=_ssl_ctx)
        opener = urllib.request.build_opener(handler)
        resp = opener.open(req, timeout=timeout)
        raw = resp.read().decode("utf-8")
        latency_ms = int((time.time() - start) * 1000)

        if not raw or not raw.strip():
            return {"status": "empty", "latency_ms": latency_ms, "response": "",
                    "sources": [], "sources_count": 0, "error": "Empty response body"}

        data = json.loads(raw)
        if isinstance(data, list):
            data = data[0] if data else {}

        # Extract response text from various possible keys
        response_text = ""
        for key in ["response", "answer", "result", "interpretation", "final_response", "output"]:
            if key in data and data[key]:
                response_text = str(data[key])
                break

        sources = data.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        sources_count = data.get("sources_count", len(sources))

        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "response": response_text,
            "sources": sources,
            "sources_count": sources_count,
            "error": None,
            "raw_keys": list(data.keys()),
        }

    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start) * 1000)
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        return {"status": "error", "latency_ms": latency_ms, "response": "",
                "sources": [], "sources_count": 0,
                "error": f"HTTP {e.code}: {body[:150]}"}

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        return {"status": "error", "latency_ms": latency_ms, "response": "",
                "sources": [], "sources_count": 0,
                "error": f"{type(e).__name__}: {str(e)[:150]}"}


# ═══════════════════════════════════════════════════════════════════
#  Response Quality Scoring
# ═══════════════════════════════════════════════════════════════════

def score_response(result, golden):
    """Score a response 0-100 against golden Q&A expectations.

    Breakdown:
      - 40 pts: keyword hits (proportional to expected_keywords matched)
      - 25 pts: sources count meets minimum
      - 20 pts: response length (>200 chars = full, >50 = half)
      - 15 pts: no error + response present
    """
    score = 0
    details = {}

    # 1. Keyword hits (40 pts)
    expected_kw = golden.get("expected_keywords", [])
    if expected_kw:
        response_lower = result.get("response", "").lower()
        hits = [kw for kw in expected_kw if kw.lower() in response_lower]
        kw_ratio = len(hits) / len(expected_kw)
        kw_score = int(40 * kw_ratio)
        score += kw_score
        details["keywords"] = {
            "hits": hits,
            "misses": [kw for kw in expected_kw if kw.lower() not in response_lower],
            "ratio": round(kw_ratio, 2),
            "score": kw_score,
        }
    else:
        score += 40
        details["keywords"] = {"hits": [], "misses": [], "ratio": 1.0, "score": 40}

    # 2. Sources (25 pts)
    min_sources = golden.get("expected_sources_min", 0)
    actual_sources = result.get("sources_count", 0)
    if actual_sources >= min_sources:
        score += 25
        details["sources"] = {"expected_min": min_sources, "actual": actual_sources, "score": 25}
    elif min_sources > 0 and actual_sources > 0:
        src_ratio = actual_sources / min_sources
        src_score = int(25 * src_ratio)
        score += src_score
        details["sources"] = {"expected_min": min_sources, "actual": actual_sources, "score": src_score}
    else:
        details["sources"] = {"expected_min": min_sources, "actual": actual_sources, "score": 0}

    # 3. Response length (20 pts)
    resp_len = len(result.get("response", ""))
    if resp_len > 200:
        score += 20
        details["length"] = {"chars": resp_len, "score": 20}
    elif resp_len > 50:
        score += 10
        details["length"] = {"chars": resp_len, "score": 10}
    else:
        details["length"] = {"chars": resp_len, "score": 0}

    # 4. Alive (15 pts)
    if result.get("status") == "ok" and result.get("response"):
        score += 15
        details["alive"] = {"score": 15}
    elif result.get("status") == "ok":
        score += 5
        details["alive"] = {"score": 5}
    else:
        details["alive"] = {"score": 0}

    return score, details


# ═══════════════════════════════════════════════════════════════════
#  Single Test Runner
# ═══════════════════════════════════════════════════════════════════

def run_single_test(pipeline_name, qa, space_label, n8n_clients):
    """Run a single golden Q&A test and collect node metrics.

    Returns a result dict with response data, quality score, and node metrics.
    """
    cfg = PIPELINES[pipeline_name]
    space_url = SPACES[space_label]

    # 1. Call webhook
    result = call_webhook(
        space_url, cfg["webhook"], qa["query"], qa["sector"], qa["tenant_id"]
    )

    # 2. Score response
    score, score_details = score_response(result, qa)

    # 3. Fetch node metrics from n8n API (best effort)
    node_metrics = []
    client = n8n_clients.get(space_label)
    if client:
        try:
            # Small delay to let execution complete in n8n
            time.sleep(2)
            exec_data = client.get_latest_execution(cfg["workflow_id"])
            node_metrics = extract_node_metrics(exec_data)
        except Exception as e:
            node_metrics = [{"name": "_fetch_error", "error": str(e)[:200]}]

    return {
        "pipeline": pipeline_name,
        "space": space_label,
        "query": qa["query"],
        "sector": qa["sector"],
        "status": result["status"],
        "latency_ms": result["latency_ms"],
        "response_preview": result["response"][:300] if result.get("response") else "",
        "response_length": len(result.get("response", "")),
        "sources_count": result.get("sources_count", 0),
        "error": result.get("error"),
        "score": score,
        "score_details": score_details,
        "node_metrics": node_metrics,
    }


# ═══════════════════════════════════════════════════════════════════
#  Full Run — All pipelines in parallel
# ═══════════════════════════════════════════════════════════════════

def run_all_tests(pipelines_filter=None, max_workers=8):
    """Run all golden Q&A tests in parallel across pipelines.

    Returns a run report dict ready for saving and comparison.
    """
    ts_start = datetime.now(timezone.utc)
    print(f"\n{colored('='*70, C.CYAN)}")
    print(f"{colored('  SMART SMOKE TEST', C.BOLD + C.CYAN)}  —  {ts_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{colored('='*70, C.CYAN)}\n")

    # Filter pipelines
    active_pipelines = list(PIPELINES.keys())
    if pipelines_filter:
        active_pipelines = [p for p in pipelines_filter if p in PIPELINES]
    if not active_pipelines:
        print(colored("  No valid pipelines selected.", C.RED))
        return None

    # Pre-authenticate n8n clients for all unique spaces we need
    needed_spaces = set()
    for p in active_pipelines:
        for s in PIPELINES[p]["spaces"]:
            needed_spaces.add(s)

    print(f"  Authenticating to {len(needed_spaces)} Space(s)...", end="", flush=True)
    n8n_clients = {}
    for sl in needed_spaces:
        client = N8nClient(sl, SPACES[sl])
        if client.login():
            n8n_clients[sl] = client
            print(f" {colored(sl, C.GREEN)}", end="", flush=True)
        else:
            print(f" {colored(sl + '!', C.RED)}", end="", flush=True)
    print()

    # Build task list: (pipeline, qa, space)
    tasks = []
    for pipe in active_pipelines:
        cfg = PIPELINES[pipe]
        questions = GOLDEN_QA.get(pipe, [])
        space_idx = 0
        for qa in questions:
            # Round-robin across available spaces for this pipeline
            space = cfg["spaces"][space_idx % len(cfg["spaces"])]
            space_idx += 1
            tasks.append((pipe, qa, space))

    total = len(tasks)
    print(f"  Running {colored(str(total), C.BOLD)} tests across "
          f"{colored(str(len(active_pipelines)), C.BOLD)} pipeline(s)...\n")

    # Execute in parallel
    results = []
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for pipe, qa, space in tasks:
            future = executor.submit(run_single_test, pipe, qa, space, n8n_clients)
            future_map[future] = (pipe, qa["query"][:50], space)

        for future in as_completed(future_map):
            pipe, q_short, space = future_map[future]
            completed += 1
            try:
                res = future.result()
                results.append(res)
                # Live progress
                status_icon = _status_icon(res["status"], res["score"])
                res_score = res["score"]
                score_color = C.GREEN if res_score >= 70 else (C.YELLOW if res_score >= 40 else C.RED)
                lat_str = f"{res['latency_ms']}ms" if res['latency_ms'] else "---"
                print(f"  {colored(f'[{completed}/{total}]', C.DIM)} "
                      f"{status_icon} "
                      f"{colored(pipe.upper()[:4], C.CYAN):>4s} "
                      f"{colored(str(res_score).rjust(3), score_color)}/100 "
                      f"{lat_str:>7s}  "
                      f"{q_short}...")
                if res.get("error"):
                    print(f"         {colored('ERR: ' + res['error'][:80], C.RED)}")
            except Exception as e:
                results.append({
                    "pipeline": pipe, "space": space, "query": q_short,
                    "status": "exception", "error": str(e)[:200],
                    "score": 0, "latency_ms": 0, "node_metrics": [],
                })
                print(f"  {colored(f'[{completed}/{total}]', C.DIM)} "
                      f"{colored('EXCP', C.BG_RED + C.WHITE)} {pipe}: {str(e)[:60]}")

    ts_end = datetime.now(timezone.utc)
    total_duration = (ts_end - ts_start).total_seconds()

    # Build run report
    report = {
        "timestamp": ts_start.isoformat(),
        "timestamp_end": ts_end.isoformat(),
        "duration_s": round(total_duration, 1),
        "pipelines_tested": active_pipelines,
        "total_tests": total,
        "results": results,
        "summary": _compute_summary(results),
    }

    # Save run
    filename = f"run-{ts_start.strftime('%Y%m%d-%H%M%S')}.json"
    filepath = SMOKE_DIR / filename
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Also save as "latest.json" for easy access
    latest_path = SMOKE_DIR / "latest.json"
    with open(latest_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    _print_summary(report)

    return report


def _status_icon(status, score):
    if status == "error":
        return colored("FAIL", C.BG_RED + C.WHITE)
    elif status == "empty":
        return colored("EMPT", C.BG_YELLOW + C.WHITE)
    elif score >= 70:
        return colored("PASS", C.BG_GREEN + C.WHITE)
    elif score >= 40:
        return colored("WEAK", C.YELLOW)
    else:
        return colored("POOR", C.RED)


def _compute_summary(results):
    """Compute aggregate summary from test results."""
    total = len(results)
    passed = sum(1 for r in results if r.get("score", 0) >= 70 and r.get("status") == "ok")
    failed = sum(1 for r in results if r.get("status") in ("error", "exception"))
    weak = total - passed - failed
    timeouts = sum(1 for r in results if r.get("error") and "timeout" in str(r.get("error", "")).lower())

    avg_score = sum(r.get("score", 0) for r in results) / total if total else 0
    avg_latency = sum(r.get("latency_ms", 0) for r in results if r.get("latency_ms", 0) > 0)
    latency_count = sum(1 for r in results if r.get("latency_ms", 0) > 0)
    avg_latency = avg_latency / latency_count if latency_count else 0

    # Per-pipeline breakdown
    by_pipeline = defaultdict(list)
    for r in results:
        by_pipeline[r.get("pipeline", "unknown")].append(r)

    pipeline_summary = {}
    for pipe, pipe_results in by_pipeline.items():
        p_passed = sum(1 for r in pipe_results if r.get("score", 0) >= 70 and r.get("status") == "ok")
        p_scores = [r.get("score", 0) for r in pipe_results]
        p_latencies = [r.get("latency_ms", 0) for r in pipe_results if r.get("latency_ms", 0) > 0]
        pipeline_summary[pipe] = {
            "total": len(pipe_results),
            "passed": p_passed,
            "avg_score": round(sum(p_scores) / len(p_scores), 1) if p_scores else 0,
            "avg_latency_ms": round(sum(p_latencies) / len(p_latencies)) if p_latencies else 0,
            "errors": sum(1 for r in pipe_results if r.get("status") in ("error", "exception")),
        }

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "weak": weak,
        "timeouts": timeouts,
        "avg_score": round(avg_score, 1),
        "avg_latency_ms": round(avg_latency),
        "by_pipeline": pipeline_summary,
    }


def _print_summary(report):
    """Print a beautiful colored summary table."""
    s = report["summary"]
    print(f"\n{colored('='*70, C.CYAN)}")
    print(f"{colored('  SUMMARY', C.BOLD + C.CYAN)}")
    print(f"{colored('='*70, C.CYAN)}\n")

    # Headline
    headline_parts = []
    if s["passed"]:
        headline_parts.append(colored(f'{s["passed"]}/{s["total"]} PASS', C.GREEN + C.BOLD))
    if s["weak"]:
        headline_parts.append(colored(f'{s["weak"]} WEAK', C.YELLOW))
    if s["failed"]:
        headline_parts.append(colored(f'{s["failed"]} FAIL', C.RED + C.BOLD))
    if s["timeouts"]:
        headline_parts.append(colored(f'{s["timeouts"]} TIMEOUT', C.MAGENTA))
    print(f"  {' | '.join(headline_parts)}")
    print(f"  Avg score: {colored(str(s['avg_score']), C.BOLD)}/100  "
          f"  Avg latency: {colored(str(s['avg_latency_ms']) + 'ms', C.BOLD)}  "
          f"  Duration: {report['duration_s']}s\n")

    # Per-pipeline table
    print(f"  {'Pipeline':<14s} {'Pass':>5s} {'Score':>6s} {'Latency':>9s} {'Status':>8s}")
    print(f"  {'─'*14} {'─'*5} {'─'*6} {'─'*9} {'─'*8}")

    for pipe, ps in s["by_pipeline"].items():
        pass_str = f"{ps['passed']}/{ps['total']}"
        score_str = f"{ps['avg_score']}"
        lat_str = f"{ps['avg_latency_ms']}ms" if ps['avg_latency_ms'] else "---"
        if ps["errors"] > 0:
            status_str = colored("ERROR", C.RED)
        elif ps["passed"] == ps["total"]:
            status_str = colored("OK", C.GREEN)
        elif ps["passed"] > 0:
            status_str = colored("PARTIAL", C.YELLOW)
        else:
            status_str = colored("FAIL", C.RED)

        score_color = C.GREEN if ps["avg_score"] >= 70 else (C.YELLOW if ps["avg_score"] >= 40 else C.RED)
        print(f"  {pipe:<14s} {pass_str:>5s} {colored(score_str, score_color):>15s} {lat_str:>9s} {status_str:>17s}")

    # Node metrics summary (if available)
    _print_node_metrics_summary(report["results"])

    print(f"\n  Report saved: {colored(str(SMOKE_DIR / 'latest.json'), C.DIM)}")
    print()


def _print_node_metrics_summary(results):
    """Print a summary of node execution across all tests."""
    # Collect all node metrics across tests
    node_stats = defaultdict(lambda: {"times": [], "errors": 0, "total": 0})
    for r in results:
        for nm in r.get("node_metrics", []):
            if nm.get("name", "").startswith("_"):
                continue
            key = f"{r['pipeline']}::{nm['name']}"
            node_stats[key]["times"].append(nm.get("exec_time_ms", 0))
            node_stats[key]["total"] += 1
            if nm.get("status") == "error":
                node_stats[key]["errors"] += 1
            node_stats[key]["type"] = nm.get("type", "other")
            node_stats[key]["pipeline"] = r["pipeline"]
            node_stats[key]["node_name"] = nm["name"]

    if not node_stats:
        return

    # Find slowest and most error-prone nodes
    print(f"\n  {colored('Node Metrics (top slowest)', C.BOLD + C.YELLOW)}")
    print(f"  {'Pipeline':<10s} {'Node':<35s} {'Type':<10s} {'Avg ms':>7s} {'Errors':>7s}")
    print(f"  {'─'*10} {'─'*35} {'─'*10} {'─'*7} {'─'*7}")

    # Sort by avg exec time descending
    sorted_nodes = sorted(
        node_stats.items(),
        key=lambda x: (sum(x[1]["times"]) / len(x[1]["times"])) if x[1]["times"] else 0,
        reverse=True,
    )

    for key, stats in sorted_nodes[:10]:
        avg_ms = round(sum(stats["times"]) / len(stats["times"])) if stats["times"] else 0
        err_str = str(stats["errors"]) if stats["errors"] else "."
        node_short = stats["node_name"][:35]
        time_color = C.RED if avg_ms > 10000 else (C.YELLOW if avg_ms > 3000 else C.GREEN)
        err_color = C.RED if stats["errors"] > 0 else C.DIM
        print(f"  {stats['pipeline']:<10s} {node_short:<35s} {stats['type']:<10s} "
              f"{colored(str(avg_ms), time_color):>16s} {colored(err_str, err_color):>16s}")

    # Nodes with errors
    error_nodes = [(k, v) for k, v in node_stats.items() if v["errors"] > 0]
    if error_nodes:
        print(f"\n  {colored('Nodes with ERRORS:', C.RED + C.BOLD)}")
        for key, stats in error_nodes:
            print(f"    {colored('!', C.RED)} {stats['pipeline']}::{stats['node_name']} "
                  f"({stats['errors']}/{stats['total']} runs failed)")


# ═══════════════════════════════════════════════════════════════════
#  Comparison Engine
# ═══════════════════════════════════════════════════════════════════

def load_previous_run(offset=1):
    """Load the Nth most recent run (offset=1 = latest, offset=2 = before that)."""
    runs = sorted(SMOKE_DIR.glob("run-*.json"), reverse=True)
    if len(runs) < offset:
        return None
    with open(runs[offset - 1]) as f:
        return json.load(f)


def load_latest_run():
    """Load the latest run."""
    latest = SMOKE_DIR / "latest.json"
    if latest.exists():
        with open(latest) as f:
            return json.load(f)
    return load_previous_run(1)


def compare_runs(before, after):
    """Compare two runs and produce a diff report."""
    print(f"\n{colored('='*70, C.MAGENTA)}")
    print(f"{colored('  COMPARISON: BEFORE vs AFTER', C.BOLD + C.MAGENTA)}")
    print(f"{colored('='*70, C.MAGENTA)}")
    print(f"  Before: {before.get('timestamp', '?')}")
    print(f"  After:  {after.get('timestamp', '?')}\n")

    sb = before.get("summary", {})
    sa = after.get("summary", {})

    # Headline diff
    _print_metric_diff("Avg Score", sb.get("avg_score", 0), sa.get("avg_score", 0), "/100", higher_is_better=True)
    _print_metric_diff("Pass Rate", sb.get("passed", 0), sa.get("passed", 0),
                       f"/{sa.get('total', 0)}", higher_is_better=True)
    _print_metric_diff("Avg Latency", sb.get("avg_latency_ms", 0), sa.get("avg_latency_ms", 0),
                       "ms", higher_is_better=False)
    _print_metric_diff("Failures", sb.get("failed", 0), sa.get("failed", 0), "", higher_is_better=False)

    # Per-pipeline diff
    print(f"\n  {colored('Per-Pipeline Changes:', C.BOLD)}")
    all_pipes = set(list(sb.get("by_pipeline", {}).keys()) + list(sa.get("by_pipeline", {}).keys()))
    for pipe in sorted(all_pipes):
        pb = sb.get("by_pipeline", {}).get(pipe, {})
        pa = sa.get("by_pipeline", {}).get(pipe, {})
        score_before = pb.get("avg_score", 0)
        score_after = pa.get("avg_score", 0)
        lat_before = pb.get("avg_latency_ms", 0)
        lat_after = pa.get("avg_latency_ms", 0)

        score_delta = score_after - score_before
        lat_delta = lat_after - lat_before

        score_arrow = colored(f"+{score_delta}", C.GREEN) if score_delta > 0 else (
            colored(str(score_delta), C.RED) if score_delta < 0 else colored("=", C.DIM))
        lat_arrow = colored(f"+{lat_delta}ms", C.RED) if lat_delta > 100 else (
            colored(f"{lat_delta}ms", C.GREEN) if lat_delta < -100 else colored(f"{lat_delta}ms", C.DIM))

        print(f"    {pipe:<14s}  score: {score_before} -> {score_after} ({score_arrow})  "
              f"latency: {lat_before}ms -> {lat_after}ms ({lat_arrow})")

    # Node-by-node diff
    _compare_node_metrics(before.get("results", []), after.get("results", []))

    print()


def _print_metric_diff(label, before, after, suffix, higher_is_better=True):
    """Print a single metric diff line with color."""
    delta = after - before
    if delta == 0:
        arrow = colored(f"= {after}{suffix}", C.DIM)
    elif (delta > 0 and higher_is_better) or (delta < 0 and not higher_is_better):
        arrow = colored(f"{before}{suffix} -> {after}{suffix} (+{abs(delta):.1f})", C.GREEN + C.BOLD)
    else:
        arrow = colored(f"{before}{suffix} -> {after}{suffix} (-{abs(delta):.1f})", C.RED + C.BOLD)
    print(f"  {label:<16s} {arrow}")


def _compare_node_metrics(results_before, results_after):
    """Compare node-level metrics between two runs."""
    # Build lookup: pipeline::query -> node_metrics
    def _build_node_map(results):
        nm = {}
        for r in results:
            key = f"{r['pipeline']}::{r.get('query', '')[:40]}"
            node_map = {}
            for n in r.get("node_metrics", []):
                if not n.get("name", "").startswith("_"):
                    node_map[n["name"]] = n
            nm[key] = node_map
        return nm

    before_map = _build_node_map(results_before)
    after_map = _build_node_map(results_after)

    # Find regressions
    regressions = []
    improvements = []

    for key in set(list(before_map.keys()) + list(after_map.keys())):
        bm = before_map.get(key, {})
        am = after_map.get(key, {})
        all_nodes = set(list(bm.keys()) + list(am.keys()))

        for node_name in all_nodes:
            nb = bm.get(node_name)
            na = am.get(node_name)

            if na and nb:
                time_before = nb.get("exec_time_ms", 0)
                time_after = na.get("exec_time_ms", 0)

                # Regression: node got >2x slower
                if time_before > 0 and time_after > time_before * 2 and time_after > 1000:
                    regressions.append({
                        "test": key, "node": node_name,
                        "metric": "exec_time", "before": time_before, "after": time_after,
                        "ratio": round(time_after / time_before, 1),
                    })
                elif time_before > 0 and time_after < time_before * 0.5 and time_before > 1000:
                    improvements.append({
                        "test": key, "node": node_name,
                        "metric": "exec_time", "before": time_before, "after": time_after,
                        "ratio": round(time_after / time_before, 1),
                    })

                # Regression: node now errors when it didn't before
                if nb.get("status") == "success" and na.get("status") == "error":
                    regressions.append({
                        "test": key, "node": node_name,
                        "metric": "status", "before": "success", "after": "error",
                        "error_msg": na.get("error", ""),
                    })
                elif nb.get("status") == "error" and na.get("status") == "success":
                    improvements.append({
                        "test": key, "node": node_name,
                        "metric": "status", "before": "error", "after": "success",
                    })

            elif na and not nb:
                # New node appeared
                pass
            elif nb and not na:
                # Node disappeared — could be regression
                regressions.append({
                    "test": key, "node": node_name,
                    "metric": "missing", "before": "present", "after": "missing",
                })

    if regressions:
        print(f"\n  {colored('NODE REGRESSIONS DETECTED:', C.RED + C.BOLD)} ({len(regressions)})")
        for reg in regressions[:15]:
            if reg["metric"] == "exec_time":
                print(f"    {colored('!', C.RED)} {reg['node'][:40]}  "
                      f"{reg['before']}ms -> {colored(str(reg['after']) + 'ms', C.RED)} "
                      f"({reg['ratio']}x slower)")
            elif reg["metric"] == "status":
                print(f"    {colored('!', C.RED)} {reg['node'][:40]}  "
                      f"was OK, now {colored('ERROR', C.RED)}: {reg.get('error_msg', '')[:60]}")
            elif reg["metric"] == "missing":
                print(f"    {colored('?', C.YELLOW)} {reg['node'][:40]}  "
                      f"node {colored('DISAPPEARED', C.YELLOW)}")

    if improvements:
        print(f"\n  {colored('NODE IMPROVEMENTS:', C.GREEN + C.BOLD)} ({len(improvements)})")
        for imp in improvements[:10]:
            if imp["metric"] == "exec_time":
                print(f"    {colored('+', C.GREEN)} {imp['node'][:40]}  "
                      f"{imp['before']}ms -> {colored(str(imp['after']) + 'ms', C.GREEN)} "
                      f"({imp['ratio']}x faster)")
            elif imp["metric"] == "status":
                print(f"    {colored('+', C.GREEN)} {imp['node'][:40]}  "
                      f"was ERROR, now {colored('OK', C.GREEN)}")

    if not regressions and not improvements:
        print(f"\n  {colored('No significant node-level changes detected.', C.DIM)}")


# ═══════════════════════════════════════════════════════════════════
#  --last : Show last run
# ═══════════════════════════════════════════════════════════════════

def show_last_run():
    """Display the most recent run results."""
    run = load_latest_run()
    if not run:
        print(colored("  No previous runs found.", C.RED))
        return
    print(f"\n{colored('  LAST RUN:', C.BOLD + C.CYAN)} {run.get('timestamp', '?')}")
    _print_summary(run)

    # Also show per-test detail
    print(f"  {colored('Per-Test Detail:', C.BOLD)}")
    print(f"  {'Pipeline':<12s} {'Sector':<10s} {'Score':>6s} {'Lat':>7s} {'Src':>4s} {'Status':<6s} Question")
    print(f"  {'─'*12} {'─'*10} {'─'*6} {'─'*7} {'─'*4} {'─'*6} {'─'*40}")
    for r in run.get("results", []):
        sc = r.get("score", 0)
        sc_color = C.GREEN if sc >= 70 else (C.YELLOW if sc >= 40 else C.RED)
        lat = f"{r.get('latency_ms', 0)}ms" if r.get("latency_ms") else "---"
        src = str(r.get("sources_count", 0))
        st = r.get("status", "?")
        st_color = C.GREEN if st == "ok" else C.RED
        q = r.get("query", "")[:45]
        print(f"  {r.get('pipeline','?'):<12s} {r.get('sector','?'):<10s} "
              f"{colored(str(sc), sc_color):>15s} {lat:>7s} {src:>4s} "
              f"{colored(st, st_color):<15s} {q}")

    print()


# ═══════════════════════════════════════════════════════════════════
#  --history N : Show last N runs
# ═══════════════════════════════════════════════════════════════════

def show_history(n=5):
    """Show summary of last N runs."""
    runs = sorted(SMOKE_DIR.glob("run-*.json"), reverse=True)[:n]
    if not runs:
        print(colored("  No runs found.", C.RED))
        return

    print(f"\n{colored('  RUN HISTORY', C.BOLD + C.CYAN)} (last {len(runs)})\n")
    print(f"  {'Timestamp':<22s} {'Pass':>6s} {'Score':>6s} {'Latency':>9s} {'Dur':>5s} {'Errors':>7s}")
    print(f"  {'─'*22} {'─'*6} {'─'*6} {'─'*9} {'─'*5} {'─'*7}")

    for rp in runs:
        try:
            with open(rp) as f:
                run = json.load(f)
        except Exception:
            continue
        s = run.get("summary", {})
        ts = run.get("timestamp", "?")[:19].replace("T", " ")
        pass_str = f"{s.get('passed', 0)}/{s.get('total', 0)}"
        score = s.get("avg_score", 0)
        lat = s.get("avg_latency_ms", 0)
        dur = f"{run.get('duration_s', 0)}s"
        errs = s.get("failed", 0)

        sc_color = C.GREEN if score >= 70 else (C.YELLOW if score >= 40 else C.RED)
        err_color = C.RED if errs > 0 else C.DIM
        print(f"  {ts:<22s} {pass_str:>6s} {colored(str(score), sc_color):>15s} "
              f"{str(lat) + 'ms':>9s} {dur:>5s} {colored(str(errs), err_color):>16s}")

    print()


# ═══════════════════════════════════════════════════════════════════
#  --fix-mode : Before/After comparison
# ═══════════════════════════════════════════════════════════════════

def fix_mode(pipelines_filter=None):
    """Run tests and compare against the last run to show fix impact."""
    # Load "before" (last run)
    before = load_latest_run()
    if not before:
        print(colored("  No previous run found. Running first baseline...", C.YELLOW))
        before = run_all_tests(pipelines_filter)
        if not before:
            return
        print(colored("\n  Baseline captured. Apply your fix, then run --fix-mode again.", C.CYAN))
        return

    # Run "after" (current test)
    print(colored("  Running current tests to compare with last run...\n", C.CYAN))
    after = run_all_tests(pipelines_filter)
    if not after:
        return

    # Show diff
    compare_runs(before, after)


# ═══════════════════════════════════════════════════════════════════
#  --compare : Compare last two runs
# ═══════════════════════════════════════════════════════════════════

def compare_last_two():
    """Compare the two most recent runs."""
    runs = sorted(SMOKE_DIR.glob("run-*.json"), reverse=True)
    if len(runs) < 2:
        print(colored("  Need at least 2 runs to compare. Run tests first.", C.RED))
        return

    with open(runs[0]) as f:
        after = json.load(f)
    with open(runs[1]) as f:
        before = json.load(f)

    compare_runs(before, after)


# ═══════════════════════════════════════════════════════════════════
#  --loop : Continuous monitoring
# ═══════════════════════════════════════════════════════════════════

def loop_mode(interval_s, pipelines_filter=None):
    """Run tests continuously at fixed intervals."""
    print(f"\n{colored('  CONTINUOUS SMOKE TEST', C.BOLD + C.CYAN)}")
    print(f"  Interval: {interval_s}s ({interval_s//60}min)")
    print(f"  Press Ctrl+C to stop\n")

    run_count = 0
    try:
        while True:
            run_count += 1
            print(f"\n{colored(f'  === RUN #{run_count} ===', C.BOLD)}")
            current = run_all_tests(pipelines_filter)

            # Auto-compare with previous
            runs = sorted(SMOKE_DIR.glob("run-*.json"), reverse=True)
            if len(runs) >= 2 and current:
                with open(runs[1]) as f:
                    previous = json.load(f)
                # Quick regression check
                s_prev = previous.get("summary", {})
                s_curr = current.get("summary", {})
                score_delta = s_curr.get("avg_score", 0) - s_prev.get("avg_score", 0)
                if score_delta < -5:
                    print(f"\n  {colored('!! REGRESSION ALERT !!', C.BG_RED + C.WHITE + C.BOLD)}"
                          f"  Score dropped by {abs(score_delta):.1f} points")
                    compare_runs(previous, current)
                elif score_delta > 5:
                    print(f"\n  {colored('++ IMPROVEMENT ++', C.BG_GREEN + C.WHITE + C.BOLD)}"
                          f"  Score improved by {score_delta:.1f} points")

            print(f"\n  Next run in {interval_s}s... (Ctrl+C to stop)")
            time.sleep(interval_s)

    except KeyboardInterrupt:
        print(f"\n\n  {colored('Stopped.', C.YELLOW)} {run_count} runs completed.")
        show_history(min(run_count, 10))


# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Smart Smoke Test — Node-by-Node Regression Detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 eval/smart-smoke.py                      # Run all pipelines
  python3 eval/smart-smoke.py --pipeline standard   # Test only standard
  python3 eval/smart-smoke.py --pipeline standard,graph  # Test two
  python3 eval/smart-smoke.py --compare             # Diff last two runs
  python3 eval/smart-smoke.py --fix-mode            # Before/after fix diff
  python3 eval/smart-smoke.py --loop 300            # Every 5 minutes
  python3 eval/smart-smoke.py --last                # Show last run
  python3 eval/smart-smoke.py --history 10          # Show last 10 runs
        """,
    )
    parser.add_argument("--pipeline", "-p", type=str, default=None,
                        help="Comma-separated pipeline names (standard,graph,quant,orchestrator)")
    parser.add_argument("--compare", "-c", action="store_true",
                        help="Compare last two runs")
    parser.add_argument("--fix-mode", "-f", action="store_true",
                        help="Re-test and show diff with last run")
    parser.add_argument("--loop", "-l", type=int, default=0, metavar="SECONDS",
                        help="Run continuously at N-second intervals")
    parser.add_argument("--last", action="store_true",
                        help="Show last run results")
    parser.add_argument("--history", type=int, default=0, metavar="N",
                        help="Show last N runs summary")
    parser.add_argument("--workers", "-w", type=int, default=8,
                        help="Max parallel workers (default: 8)")

    args = parser.parse_args()

    # Parse pipeline filter
    pipelines_filter = None
    if args.pipeline:
        pipelines_filter = [p.strip() for p in args.pipeline.split(",") if p.strip()]

    # Dispatch
    if args.last:
        show_last_run()
    elif args.history:
        show_history(args.history)
    elif args.compare:
        compare_last_two()
    elif args.fix_mode:
        fix_mode(pipelines_filter)
    elif args.loop:
        loop_mode(args.loop, pipelines_filter)
    else:
        report = run_all_tests(pipelines_filter, max_workers=args.workers)
        if report:
            # Exit code: 0 if all passed, 1 if any failed
            s = report.get("summary", {})
            if s.get("failed", 0) > 0:
                sys.exit(1)
            elif s.get("passed", 0) < s.get("total", 0):
                sys.exit(2)  # partial pass


if __name__ == "__main__":
    main()
