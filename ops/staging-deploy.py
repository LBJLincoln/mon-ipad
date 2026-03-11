#!/usr/bin/env python3
"""
Staging → Production Deployment Pipeline

Deploys a workflow change to a STAGING Space first, runs smoke tests,
and only promotes to ALL production Spaces if every test passes.

Flow:
  1. Deploy workflow JSON to staging Space (default: S9)
  2. Wait for activation, then run 3-question smoke test on staging
  3. If ALL pass → deploy to all production Spaces (S1, S2, S3, S4, S5)
  4. If ANY fail → stop, print failure report, exit(1)

Usage:
  # Deploy a Standard workflow fix to staging, test, then promote
  python3 ops/staging-deploy.py --workflow n8n/live/standard-rag-v3.8.json --pipeline standard

  # Deploy Graph workflow, custom staging Space
  python3 ops/staging-deploy.py --workflow n8n/live/graph-rag-v3.5.json --pipeline graph --staging-space S5

  # Deploy to staging only (no auto-promote)
  python3 ops/staging-deploy.py --workflow fix.json --pipeline standard --staging-only

  # Skip smoke tests (just deploy everywhere)
  python3 ops/staging-deploy.py --workflow fix.json --pipeline standard --skip-tests

  # Custom production Spaces
  python3 ops/staging-deploy.py --workflow fix.json --pipeline standard --production-spaces S1,S3,S5

  # Dry-run: show what would happen without deploying
  python3 ops/staging-deploy.py --workflow fix.json --pipeline standard --dry-run
"""

import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

# === Force IPv4 (GCP VM has broken IPv6) ===
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    responses = _original_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET] or responses
socket.getaddrinfo = _ipv4_only_getaddrinfo

# === Load .env.local ===
ENV_FILE = "/home/termius/mon-ipad/.env.local"
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)

# === Config ===
N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S2": "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S4": "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

WORKFLOW_IDS = {
    "standard":     "TmgyRP20N4JFd9CB",
    "graph":        "6257AfT1l4FMC6lY",
    "quant":        "cjhEhVs0KV1ExHqX",
    "quantitative": "cjhEhVs0KV1ExHqX",
    "orchestrator": "qOSaFFrqO8Jb4VGb",
}

WEBHOOK_PATHS = {
    "standard":     "/webhook/rag-multi-index-v3",
    "graph":        "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quant":        "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

# Smoke test questions per pipeline — 3 sector-diverse questions with expected substrings
SMOKE_QUESTIONS = {
    "standard": [
        {"query": "What is the FY2018 capital expenditure amount for 3M?", "expected_contains": "1577", "sector": "finance"},
        {"query": "What is the minimum turning space diameter required?", "expected_contains": "1500", "sector": "btp"},
        {"query": "Que dit l'article R151-19 du Code de l'urbanisme?", "expected_contains": "zone", "sector": "juridique"},
    ],
    "graph": [
        {"query": "What entities are related to Boeing in FY2022?", "expected_contains": "Boeing", "sector": "finance"},
        {"query": "Quels articles du Code de l'energie concernent les certificats?", "expected_contains": "nergie", "sector": "juridique"},
        {"query": "What relationships exist between construction safety standards?", "expected_contains": "safety", "sector": "btp"},
    ],
    "quant": [
        {"query": "What is 3M's total revenue for FY2018?", "expected_contains": "revenue", "sector": "finance"},
        {"query": "What are Boeing's operating expenses?", "expected_contains": "expense", "sector": "finance"},
        {"query": "How many financial tables exist for AMD?", "expected_contains": "AMD", "sector": "finance"},
    ],
    "quantitative": [
        {"query": "What is 3M's total revenue for FY2018?", "expected_contains": "revenue", "sector": "finance"},
        {"query": "What are Boeing's operating expenses?", "expected_contains": "expense", "sector": "finance"},
        {"query": "How many financial tables exist for AMD?", "expected_contains": "AMD", "sector": "finance"},
    ],
    "orchestrator": [
        {"query": "What is the FY2018 capital expenditure for 3M?", "expected_contains": "1577", "sector": "finance"},
        {"query": "Que dit l'article R641-3 du Code de l'energie?", "expected_contains": "nergie", "sector": "juridique"},
        {"query": "How do I connect an IP control device to the TV?", "expected_contains": "IP", "sector": "industrie"},
    ],
}

# SSL context — skip verification for HF Spaces
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ANSI colors for terminal output
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"

def colored(text, color):
    return f"{color}{text}{C.RESET}"


# ============================================================
# HTTP / n8n helpers
# ============================================================

def http_request(url, method="GET", data=None, headers=None, cookie=None, timeout=30):
    """Make HTTP request with optional cookie auth. Returns (status, body, set_cookie)."""
    if headers is None:
        headers = {}
    headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout)
        set_cookie = resp.headers.get("Set-Cookie", "")
        resp_data = resp.read().decode("utf-8")
        return resp.status, resp_data, set_cookie
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8") if e.fp else ""
        return e.code, body_err, ""
    except Exception as e:
        return 0, str(e), ""


def login(base_url):
    """Login to n8n and return session cookie string."""
    url = f"{base_url}/rest/login"
    data = {"emailOrLdapLoginId": N8N_EMAIL, "password": N8N_PASSWORD}
    status, body, set_cookie = http_request(url, method="POST", data=data)

    if status == 200:
        cookies = []
        if set_cookie:
            for part in set_cookie.split(","):
                for item in part.split(";"):
                    item = item.strip()
                    if "=" in item and not any(
                        k in item.lower()
                        for k in ["path", "expires", "max-age", "domain", "secure", "httponly", "samesite"]
                    ):
                        cookies.append(item)
        cookie_str = "; ".join(cookies) if cookies else (set_cookie.split(";")[0] if set_cookie else "")
        return cookie_str
    else:
        print(f"    {colored('LOGIN FAILED', C.RED)} ({status}): {body[:200]}")
        return None


def deploy_workflow(base_url, cookie, workflow_json, workflow_id):
    """3-step deploy: PATCH nodes → GET versionId → POST activate.

    Returns True on success, False on failure.
    """
    url = f"{base_url}/rest/workflows/{workflow_id}"

    # Step 1: PATCH — send nodes, connections, settings, name
    payload = {
        "name": workflow_json.get("name", ""),
        "nodes": workflow_json["nodes"],
        "connections": workflow_json["connections"],
        "settings": workflow_json.get("settings", {}),
    }

    status, body, _ = http_request(url, method="PATCH", data=payload, cookie=cookie, timeout=60)
    if status != 200:
        print(f"    PATCH FAILED ({status}): {body[:300]}")
        return False
    print(f"    PATCH OK")

    # Step 2: GET versionId (required for activation)
    status, body, _ = http_request(url, method="GET", cookie=cookie)
    if status != 200:
        print(f"    GET versionId FAILED ({status}): {body[:200]}")
        return False

    wf_data = json.loads(body)
    inner = wf_data.get("data", wf_data)
    version_id = inner.get("versionId")
    print(f"    versionId: {version_id}")

    # Step 3: POST activate
    activate_url = f"{base_url}/rest/workflows/{workflow_id}/activate"
    activate_data = {}
    if version_id:
        activate_data["versionId"] = version_id

    status, body, _ = http_request(activate_url, method="POST", data=activate_data, cookie=cookie)
    if status in (200, 201):
        print(f"    ACTIVATE OK")
        return True
    else:
        print(f"    ACTIVATE ({status}): {body[:200]}")
        # Retry without versionId (some n8n versions don't need it)
        if version_id:
            status2, body2, _ = http_request(activate_url, method="POST", data={}, cookie=cookie)
            if status2 in (200, 201):
                print(f"    ACTIVATE (retry without versionId) OK")
                return True
        return status == 200


def normalize_for_match(text):
    """Normalize text for fuzzy matching — strip formatting from numbers."""
    import re
    normalized = re.sub(r'(\d)[,\s](\d)', r'\1\2', text)
    normalized = re.sub(r'(\d)\s+(\d)', r'\1\2', normalized)
    normalized = normalized.replace('$', '').replace('%', '')
    return normalized.lower()


def run_smoke_test(base_url, pipeline, questions=None, timeout_per_q=120):
    """Run smoke test questions against a specific Space.

    Returns dict with:
      - passed: int (count of passing questions)
      - total: int (total questions)
      - results: list of per-question dicts
      - all_passed: bool
    """
    webhook_path = WEBHOOK_PATHS.get(pipeline)
    if not webhook_path:
        print(f"    {colored('ERROR', C.RED)}: Unknown pipeline '{pipeline}'")
        return {"passed": 0, "total": 0, "results": [], "all_passed": False}

    if questions is None:
        questions = SMOKE_QUESTIONS.get(pipeline, [])

    if not questions:
        print(f"    {colored('WARNING', C.YELLOW)}: No smoke questions for pipeline '{pipeline}'")
        return {"passed": 0, "total": 0, "results": [], "all_passed": False}

    url = f"{base_url}{webhook_path}"
    results = []

    for i, q in enumerate(questions):
        query = q["query"]
        expected = q.get("expected_contains", "")
        sector = q.get("sector", "benchmark")

        # Space between questions to avoid 503 (n8n EXECUTIONS_CONCURRENCY_LIMIT=2)
        if i > 0:
            time.sleep(3)

        payload = {
            "query": query,
            "chatInput": query,
            "user_context": {"tenant_id": sector, "groups": ["admin"]},
            "disable_acl": True,
        }

        start = time.time()
        status, body, _ = http_request(url, method="POST", data=payload, timeout=timeout_per_q)
        elapsed = time.time() - start

        result = {
            "query": query,
            "sector": sector,
            "expected": expected,
            "latency_s": round(elapsed, 1),
            "passed": False,
            "answer": "",
            "error": None,
        }

        if status == 200:
            try:
                resp = json.loads(body)
                if isinstance(resp, list):
                    resp = resp[0] if resp else {}

                # Extract answer from multiple possible keys
                answer = ""
                for key in ["response", "answer", "result", "interpretation", "final_response", "output"]:
                    if key in resp and resp[key]:
                        answer = str(resp[key])
                        break

                result["answer"] = answer

                # Check for error indicators
                unable = any(x in answer.lower() for x in [
                    "unable to generate", "impossible de", "no relevant",
                    "cannot answer", "no data found", "error processing"
                ])

                if unable:
                    result["error"] = "Error response from pipeline"
                elif expected:
                    norm_answer = normalize_for_match(answer)
                    norm_expected = normalize_for_match(expected)
                    if norm_expected in norm_answer:
                        result["passed"] = True
                    else:
                        result["error"] = f"Expected '{expected}' not found in answer"
                elif len(answer) > 20:
                    # No expected value but got a substantive answer
                    result["passed"] = True
                else:
                    result["error"] = f"Answer too short ({len(answer)} chars)"

            except json.JSONDecodeError:
                result["error"] = f"Invalid JSON response: {body[:150]}"
        else:
            result["error"] = f"HTTP {status}: {body[:200]}"

        # Print result
        if result["passed"]:
            symbol = colored("[PASS]", C.GREEN)
        else:
            symbol = colored("[FAIL]", C.RED)

        print(f"    {symbol} Q{i+1}: {query[:65]}")
        print(f"          Sector: {sector} | Latency: {result['latency_s']}s")
        if result["passed"]:
            print(f"          Answer: {result['answer'][:120]}...")
        else:
            print(f"          {colored('Error:', C.RED)} {result['error']}")
            if result["answer"]:
                print(f"          Answer: {result['answer'][:120]}...")

        results.append(result)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    all_passed = passed == total and total > 0

    return {
        "passed": passed,
        "total": total,
        "results": results,
        "all_passed": all_passed,
    }


# ============================================================
# Deploy to a single Space
# ============================================================

def deploy_to_space(space_name, workflow_json, pipeline):
    """Deploy workflow to a single Space. Returns True on success."""
    base_url = SPACES.get(space_name)
    if not base_url:
        print(f"    {colored('ERROR', C.RED)}: Unknown Space '{space_name}'")
        return False

    workflow_id = WORKFLOW_IDS.get(pipeline)
    if not workflow_id:
        print(f"    {colored('ERROR', C.RED)}: Unknown pipeline '{pipeline}'")
        return False

    print(f"    Logging in to {space_name} ({base_url})...")
    cookie = login(base_url)
    if not cookie:
        return False
    print(f"    Login OK")

    print(f"    Deploying workflow {workflow_id} to {space_name}...")
    success = deploy_workflow(base_url, cookie, workflow_json, workflow_id)

    if success:
        print(f"    {colored('DEPLOYED', C.GREEN)} to {space_name}")
    else:
        print(f"    {colored('DEPLOY FAILED', C.RED)} on {space_name}")

    return success


# ============================================================
# Logging — save deployment history
# ============================================================

def save_deploy_log(pipeline, staging_space, staging_result, prod_spaces, prod_results,
                    smoke_results, workflow_file, promoted):
    """Save deployment log to data/deploy-logs/."""
    log_dir = "/home/termius/mon-ipad/data/deploy-logs"
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = os.path.join(log_dir, f"deploy-{pipeline}-{timestamp}.json")

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "pipeline": pipeline,
        "workflow_file": workflow_file,
        "staging_space": staging_space,
        "staging_deployed": staging_result,
        "smoke_tests": smoke_results,
        "promoted_to_production": promoted,
        "production_spaces": prod_spaces,
        "production_results": prod_results,
    }

    with open(log_file, "w") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    print(f"\n  Deploy log saved: {log_file}")
    return log_file


# ============================================================
# MAIN
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Staging → Production deployment pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --workflow n8n/live/standard-rag-v3.8.json --pipeline standard
  %(prog)s --workflow fix.json --pipeline graph --staging-space S5
  %(prog)s --workflow fix.json --pipeline standard --staging-only
  %(prog)s --workflow fix.json --pipeline standard --dry-run
        """,
    )
    parser.add_argument("--workflow", required=True,
                        help="Path to workflow JSON file to deploy")
    parser.add_argument("--pipeline", required=True,
                        choices=["standard", "graph", "quant", "quantitative", "orchestrator"],
                        help="Pipeline type (determines workflow ID and webhook path)")
    parser.add_argument("--staging-space", default="S9",
                        help="Space to use as staging (default: S9)")
    parser.add_argument("--production-spaces", default="S1,S2,S3,S4,S5",
                        help="Comma-separated production Spaces (default: S1,S2,S3,S4,S5)")
    parser.add_argument("--staging-only", action="store_true",
                        help="Deploy to staging only, do not auto-promote even if tests pass")
    parser.add_argument("--skip-tests", action="store_true",
                        help="Skip smoke tests and deploy directly to all Spaces")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without deploying anything")
    parser.add_argument("--smoke-timeout", type=int, default=120,
                        help="Timeout per smoke question in seconds (default: 120)")
    parser.add_argument("--activation-wait", type=int, default=8,
                        help="Seconds to wait after deployment before running smoke tests (default: 8)")
    args = parser.parse_args()

    # Normalize pipeline name
    pipeline = args.pipeline
    if pipeline == "quantitative":
        pipeline = "quant"

    # Resolve workflow file path
    workflow_path = args.workflow
    if not os.path.isabs(workflow_path):
        workflow_path = os.path.join("/home/termius/mon-ipad", workflow_path)

    # Parse production Spaces
    prod_spaces = [s.strip() for s in args.production_spaces.split(",") if s.strip()]
    staging_space = args.staging_space

    # Validate
    if staging_space not in SPACES:
        print(f"FATAL: Unknown staging Space '{staging_space}'. Available: {list(SPACES.keys())}")
        sys.exit(1)
    for s in prod_spaces:
        if s not in SPACES:
            print(f"FATAL: Unknown production Space '{s}'. Available: {list(SPACES.keys())}")
            sys.exit(1)
    if staging_space in prod_spaces:
        prod_spaces.remove(staging_space)
        print(f"  NOTE: Removed {staging_space} from production list (it is the staging Space)")

    workflow_id = WORKFLOW_IDS.get(pipeline)
    webhook_path = WEBHOOK_PATHS.get(pipeline)

    # ──────────────────────────────────────────────────────────
    # Header
    # ──────────────────────────────────────────────────────────
    print(colored("=" * 72, C.CYAN))
    print(colored("  STAGING -> PRODUCTION DEPLOYMENT PIPELINE", C.BOLD))
    print(colored("=" * 72, C.CYAN))
    print(f"  Time:              {datetime.now().isoformat()}")
    print(f"  Pipeline:          {pipeline}")
    print(f"  Workflow ID:       {workflow_id}")
    print(f"  Webhook:           {webhook_path}")
    print(f"  Workflow file:     {workflow_path}")
    print(f"  Staging Space:     {staging_space} ({SPACES[staging_space]})")
    print(f"  Production Spaces: {', '.join(prod_spaces)}")
    print(f"  Staging only:      {args.staging_only}")
    print(f"  Skip tests:        {args.skip_tests}")
    print(f"  Dry run:           {args.dry_run}")
    print()

    # ──────────────────────────────────────────────────────────
    # PHASE 0: Load workflow JSON
    # ──────────────────────────────────────────────────────────
    print(colored("[PHASE 0] Loading workflow JSON...", C.BOLD))

    if not os.path.exists(workflow_path):
        print(f"  {colored('FATAL', C.RED)}: Workflow file not found: {workflow_path}")
        sys.exit(1)

    with open(workflow_path) as f:
        workflow_json = json.load(f)

    # Handle n8n export format: may have top-level keys or be wrapped
    if "nodes" not in workflow_json and "data" in workflow_json:
        workflow_json = workflow_json["data"]

    node_count = len(workflow_json.get("nodes", []))
    wf_name = workflow_json.get("name", "(unnamed)")
    conn_count = len(workflow_json.get("connections", {}))

    print(f"  Workflow name:  {wf_name}")
    print(f"  Nodes:          {node_count}")
    print(f"  Connections:    {conn_count}")
    print(f"  File size:      {os.path.getsize(workflow_path):,} bytes")

    if node_count == 0:
        print(f"  {colored('FATAL', C.RED)}: Workflow has 0 nodes. Aborting.")
        sys.exit(1)

    if args.dry_run:
        print(f"\n  {colored('DRY RUN', C.YELLOW)} — Would deploy to {staging_space}, test, then promote to {prod_spaces}")
        print(f"  No changes made.")
        sys.exit(0)

    # ──────────────────────────────────────────────────────────
    # PHASE 1: Deploy to staging
    # ──────────────────────────────────────────────────────────
    print(f"\n{colored('[PHASE 1] Deploying to STAGING Space: ' + staging_space, C.BOLD)}")
    staging_url = SPACES[staging_space]

    staging_success = deploy_to_space(staging_space, workflow_json, pipeline)

    if not staging_success:
        print(f"\n  {colored('FATAL', C.RED)}: Failed to deploy to staging ({staging_space}). Aborting.")
        save_deploy_log(pipeline, staging_space, False, prod_spaces, {},
                        None, args.workflow, False)
        sys.exit(1)

    print(f"\n  {colored('Staging deployment successful', C.GREEN)}")

    # ──────────────────────────────────────────────────────────
    # PHASE 2: Smoke tests on staging
    # ──────────────────────────────────────────────────────────
    smoke_results = None

    if args.skip_tests:
        print(f"\n{colored('[PHASE 2] SKIPPED — --skip-tests flag', C.YELLOW)}")
    else:
        print(f"\n{colored('[PHASE 2] Running smoke tests on STAGING (' + staging_space + ')...', C.BOLD)}")
        print(f"  Waiting {args.activation_wait}s for workflow activation to propagate...")
        time.sleep(args.activation_wait)

        smoke_results = run_smoke_test(
            staging_url, pipeline, timeout_per_q=args.smoke_timeout
        )

        # Print summary
        print(f"\n  {'─' * 50}")
        if smoke_results["all_passed"]:
            print(f"  {colored('SMOKE TEST RESULT: ALL PASSED', C.GREEN)} ({smoke_results['passed']}/{smoke_results['total']})")
        else:
            print(f"  {colored('SMOKE TEST RESULT: FAILED', C.RED)} ({smoke_results['passed']}/{smoke_results['total']})")
            print()
            print(f"  {colored('PRODUCTION DEPLOYMENT BLOCKED', C.RED)}")
            print(f"  Fix the failures above and re-run this script.")
            print()

            # Failure report
            print(colored("  FAILURE REPORT:", C.BOLD))
            for r in smoke_results["results"]:
                if not r["passed"]:
                    print(f"    Pipeline: {pipeline}")
                    print(f"    Sector:   {r['sector']}")
                    print(f"    Query:    {r['query']}")
                    print(f"    Expected: '{r['expected']}'")
                    print(f"    Error:    {r['error']}")
                    if r["answer"]:
                        print(f"    Answer:   {r['answer'][:200]}")
                    print()

            save_deploy_log(pipeline, staging_space, True, prod_spaces, {},
                            smoke_results, args.workflow, False)
            sys.exit(1)

    # ──────────────────────────────────────────────────────────
    # PHASE 3: Promote to production
    # ──────────────────────────────────────────────────────────
    if args.staging_only:
        print(f"\n{colored('[PHASE 3] SKIPPED — --staging-only flag', C.YELLOW)}")
        print(f"  Workflow is live on {staging_space} only.")
        save_deploy_log(pipeline, staging_space, True, prod_spaces, {},
                        smoke_results, args.workflow, False)
        sys.exit(0)

    print(f"\n{colored('[PHASE 3] Promoting to PRODUCTION Spaces: ' + ', '.join(prod_spaces), C.BOLD)}")

    prod_results = {}
    prod_failures = []

    for space in prod_spaces:
        print(f"\n  --- {space} ---")
        success = deploy_to_space(space, workflow_json, pipeline)
        prod_results[space] = "OK" if success else "FAILED"
        if not success:
            prod_failures.append(space)

    # ──────────────────────────────────────────────────────────
    # PHASE 4: Summary
    # ──────────────────────────────────────────────────────────
    print(f"\n{colored('=' * 72, C.CYAN)}")
    print(colored("  DEPLOYMENT SUMMARY", C.BOLD))
    print(colored("=" * 72, C.CYAN))
    print(f"  Pipeline:       {pipeline}")
    print(f"  Workflow:       {wf_name}")
    print(f"  Workflow file:  {args.workflow}")
    print(f"  Workflow ID:    {workflow_id}")
    print()

    # Staging
    staging_status = colored("DEPLOYED", C.GREEN)
    print(f"  Staging ({staging_space}): {staging_status}")

    # Smoke tests
    if smoke_results:
        if smoke_results["all_passed"]:
            smoke_status = colored(f"PASSED ({smoke_results['passed']}/{smoke_results['total']})", C.GREEN)
        else:
            smoke_status = colored(f"FAILED ({smoke_results['passed']}/{smoke_results['total']})", C.RED)
        print(f"  Smoke tests:    {smoke_status}")
    elif args.skip_tests:
        print(f"  Smoke tests:    {colored('SKIPPED', C.YELLOW)}")

    # Production
    print(f"\n  Production Deployment:")
    if args.staging_only:
        print(f"    {colored('SKIPPED (staging-only mode)', C.YELLOW)}")
    else:
        for space, result in prod_results.items():
            if result == "OK":
                print(f"    {space}: {colored('OK', C.GREEN)}")
            else:
                print(f"    {space}: {colored('FAILED', C.RED)}")

    print(colored("=" * 72, C.CYAN))

    # Save deployment log
    promoted = not args.staging_only and len(prod_failures) == 0
    save_deploy_log(pipeline, staging_space, True, prod_spaces, prod_results,
                    smoke_results, args.workflow, promoted)

    # Exit code
    if prod_failures:
        print(f"\n  {colored('WARNING', C.YELLOW)}: {len(prod_failures)} production Space(s) failed: {prod_failures}")
        print(f"  Successfully deployed to: {[s for s in prod_spaces if prod_results.get(s) == 'OK']}")
        sys.exit(1)
    else:
        if not args.staging_only:
            print(f"\n  {colored('ALL DEPLOYMENTS SUCCESSFUL', C.GREEN)}")
        sys.exit(0)


if __name__ == "__main__":
    main()
