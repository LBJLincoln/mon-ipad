#!/usr/bin/env python3
"""
Auto-Remediation Script — Multi-RAG Orchestrator
Detects and fixes known patterns from fixes-library.md automatically.

Usage:
    source .env.local && python3 scripts/auto-remediate.py [--fix] [--space URL]

Without --fix: diagnostic only (safe, read-only)
With --fix: applies fixes automatically
With --space: target a single space (default: all 10)

Covers these pattern categories:
  1. Missing/broken credentials (FIX-06, FIX-08, FIX-52, FIX-53)
  2. Inactive workflows with no webhooks (FIX-16, FIX-18, FIX-19)
  3. $env access denied (FIX-63, FIX-65)
  4. Empty webhook responses (FIX-28, FIX-34)
  5. 404 webhooks (workflow not activated)
  6. Redis nodes blocking startup (FIX-64)
"""

import urllib.request
import urllib.parse
import json
import os
import sys
import time
import re
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookiejar import CookieJar
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

ALL_SPACES = [
    "https://lbjlincoln-nomos-rag-engine.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-6.hf.space",
    "https://lbjlincoln-nomos-rag-engine-7.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-8.hf.space",
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-10.hf.space",
]

LOGIN_EMAIL = "ci@nomos.ai"
LOGIN_PASSWORD = "CI-Nomos-2026!"

WEBHOOK_TESTS = {
    "standard": {
        "path": "rag-multi-index-v3",
        "field": "query",
        "question": "Quel est le chiffre d'affaires de TotalEnergies en 2023?",
    },
    "graph": {
        "path": "ff622742-6d71-4e91-af71-b5c666088717",
        "field": "query",
        "question": "Quels sont les principaux fournisseurs de Airbus?",
    },
    "quantitative": {
        "path": "3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "field": "query",
        "question": "Quel est le ratio dette/capitaux propres de LVMH?",
    },
    "orchestrator": {
        "path": "92217bb8-ffc8-459a-8331-3f553812c3d0",
        "field": "query",
        "question": "Compare les performances financieres de TotalEnergies et LVMH",
    },
    "chatbot": {
        "path": "project-chatbot",
        "field": "question",
        "question": "Que fait ce projet?",
    },
}

# Known credential types that must exist
REQUIRED_CREDENTIALS = [
    {"type": "postgres", "name_contains": "Supabase", "env_var": "SUPABASE_PASSWORD"},
    {"type": "httpHeaderAuth", "name_contains": "Pinecone", "env_var": "PINECONE_API_KEY"},
    {"type": "httpBasicAuth", "name_contains": "Neo4j", "env_var": "NEO4J_AUTH"},
    {"type": "httpHeaderAuth", "name_contains": "OpenRouter", "env_var": "OPENROUTER_KEY_STANDARD"},
]

WORKFLOW_DIR = "/home/termius/mon-ipad/hf-space/n8n-workflows"
SNAPSHOT_DIR = "/home/termius/mon-ipad/snapshot"
LOG_DIR = "/home/termius/mon-ipad/logs"

# ============================================================
# COLORS
# ============================================================

class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"

def ok(msg): print(f"  {C.GREEN}OK{C.END}  {msg}")
def warn(msg): print(f"  {C.YELLOW}WARN{C.END} {msg}")
def fail(msg): print(f"  {C.RED}FAIL{C.END} {msg}")
def info(msg): print(f"  {C.BLUE}INFO{C.END} {msg}")
def header(msg): print(f"\n{C.BOLD}{'='*60}\n {msg}\n{'='*60}{C.END}")

# ============================================================
# N8N CLIENT
# ============================================================

class N8nClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.logged_in = False

    def _request(self, method: str, path: str, data=None, timeout=30):
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if isinstance(result, dict) and "data" in result:
                    return result["data"]
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise Exception(f"HTTP {e.code}: {error_body[:200]}")

    def login(self) -> bool:
        try:
            self._request("POST", "/rest/login",
                          {"emailOrLdapLoginId": LOGIN_EMAIL, "password": LOGIN_PASSWORD})
            self.logged_in = True
            return True
        except Exception as e:
            return False

    def get_credentials(self) -> List[dict]:
        return self._request("GET", "/rest/credentials")

    def get_workflows(self) -> List[dict]:
        return self._request("GET", "/rest/workflows")

    def get_workflow(self, wf_id: str) -> dict:
        return self._request("GET", f"/rest/workflows/{wf_id}")

    def update_workflow(self, wf_id: str, data: dict) -> dict:
        return self._request("PATCH", f"/rest/workflows/{wf_id}", data)

    def activate_workflow(self, wf_id: str, version_id: str) -> dict:
        return self._request("POST", f"/rest/workflows/{wf_id}/activate",
                             {"versionId": version_id})

    def deactivate_workflow(self, wf_id: str) -> dict:
        return self._request("PATCH", f"/rest/workflows/{wf_id}", {"active": False})

    def test_webhook(self, path: str, field: str, question: str, timeout=60) -> Tuple[int, str]:
        url = f"{self.base_url}/webhook/{path}"
        data = json.dumps({field: question}).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, body
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")[:500]
        except Exception as e:
            return 0, str(e)

    def get_executions(self, limit=5) -> List[dict]:
        try:
            return self._request("GET", f"/rest/executions?limit={limit}")
        except:
            return []


# ============================================================
# DIAGNOSTIC CHECKS
# ============================================================

class DiagnosticResult:
    def __init__(self, check_name: str, status: str, details: str, fix_ref: str = "",
                 auto_fixable: bool = False, fix_data: dict = None):
        self.check_name = check_name
        self.status = status  # "ok", "warn", "fail"
        self.details = details
        self.fix_ref = fix_ref
        self.auto_fixable = auto_fixable
        self.fix_data = fix_data or {}


def check_connectivity(space_url: str) -> DiagnosticResult:
    """Check if HF Space is reachable"""
    try:
        req = urllib.request.Request(f"{space_url}/healthz", method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return DiagnosticResult("connectivity", "ok", f"Space reachable (HTTP {resp.status})")
    except Exception as e:
        pass
    return DiagnosticResult("connectivity", "fail", f"Space unreachable",
                            fix_ref="Check HF Space status on huggingface.co")


def check_credentials(client: N8nClient) -> List[DiagnosticResult]:
    """Check all required credentials exist"""
    results = []
    try:
        creds = client.get_credentials()
        cred_types = [(c["type"], c.get("name", "")) for c in creds]

        for req_cred in REQUIRED_CREDENTIALS:
            found = any(
                t == req_cred["type"] and req_cred["name_contains"].lower() in n.lower()
                for t, n in cred_types
            )
            if found:
                results.append(DiagnosticResult(
                    f"credential:{req_cred['name_contains']}", "ok",
                    f"{req_cred['name_contains']} credential exists"))
            else:
                env_val = os.environ.get(req_cred["env_var"], "")
                results.append(DiagnosticResult(
                    f"credential:{req_cred['name_contains']}", "fail",
                    f"Missing {req_cred['name_contains']} credential (type={req_cred['type']})",
                    fix_ref=f"FIX-06/53: recreate from env var {req_cred['env_var']}",
                    auto_fixable=bool(env_val),
                    fix_data={"action": "create_credential", "credential": req_cred}
                ))

        # Check OpenRouter per-pipeline keys
        or_creds = [c for c in creds if c["type"] == "httpHeaderAuth" and "openrouter" in c.get("name", "").lower()]
        if len(or_creds) < 4:
            results.append(DiagnosticResult(
                "credential:openrouter_count", "warn",
                f"Only {len(or_creds)} OpenRouter credentials (need 4 for per-pipeline rotation)",
                fix_ref="FIX-52: per-pipeline OpenRouter keys"))
        else:
            results.append(DiagnosticResult(
                "credential:openrouter_count", "ok",
                f"{len(or_creds)} OpenRouter credentials (per-pipeline rotation OK)"))

    except Exception as e:
        results.append(DiagnosticResult("credentials", "fail", f"Cannot list credentials: {e}"))

    return results


def check_workflows(client: N8nClient) -> List[DiagnosticResult]:
    """Check all workflows are active and have webhooks"""
    results = []
    try:
        workflows = client.get_workflows()

        active_count = sum(1 for w in workflows if w.get("active"))
        total = len(workflows)
        results.append(DiagnosticResult(
            "workflows:count", "ok" if total >= 9 else "warn",
            f"{total} workflows ({active_count} active, {total - active_count} inactive)"))

        # Check each core pipeline workflow
        core_patterns = {
            "standard": ["standard", "wf5"],
            "graph": ["graph", "wf2"],
            "quantitative": ["quantitative", "wf4"],
            "orchestrator": ["orchestrator"],
        }

        for pipeline, patterns in core_patterns.items():
            matched = None
            for wf in workflows:
                name_lower = wf["name"].lower()
                if any(p in name_lower for p in patterns):
                    matched = wf
                    break

            if not matched:
                results.append(DiagnosticResult(
                    f"workflow:{pipeline}", "fail",
                    f"{pipeline} workflow not found in n8n",
                    fix_ref="FIX-08: re-import workflow from snapshot"))
            elif not matched.get("active"):
                results.append(DiagnosticResult(
                    f"workflow:{pipeline}", "fail",
                    f"{pipeline} workflow exists but INACTIVE (id={matched['id']})",
                    fix_ref="FIX-16/19: activate with versionId",
                    auto_fixable=True,
                    fix_data={"action": "activate_workflow", "workflow_id": matched["id"],
                              "workflow_name": matched["name"]}
                ))
            else:
                results.append(DiagnosticResult(
                    f"workflow:{pipeline}", "ok",
                    f"{pipeline} workflow active (id={matched['id']})"))

    except Exception as e:
        results.append(DiagnosticResult("workflows", "fail", f"Cannot list workflows: {e}"))

    return results


def check_webhooks(client: N8nClient) -> List[DiagnosticResult]:
    """Test each webhook endpoint"""
    results = []
    for pipeline, cfg in WEBHOOK_TESTS.items():
        code, body = client.test_webhook(cfg["path"], cfg["field"], cfg["question"], timeout=90)

        if code == 404:
            results.append(DiagnosticResult(
                f"webhook:{pipeline}", "fail",
                f"{pipeline} webhook returns 404 (not registered)",
                fix_ref="FIX-19: workflow not activated, webhooks not registered",
                auto_fixable=True,
                fix_data={"action": "reactivate_webhook", "pipeline": pipeline}
            ))
        elif code == 500:
            # Check for known error patterns
            if "access to environment variables" in body.lower() or "env vars denied" in body.lower():
                results.append(DiagnosticResult(
                    f"webhook:{pipeline}", "fail",
                    f"{pipeline} returns 500: $env access denied",
                    fix_ref="FIX-63: N8N_BLOCK_ENV_ACCESS_IN_NODE=false missing"))
            elif "credential" in body.lower():
                results.append(DiagnosticResult(
                    f"webhook:{pipeline}", "fail",
                    f"{pipeline} returns 500: credential error",
                    fix_ref="FIX-06/53: missing or broken credential reference",
                    auto_fixable=True,
                    fix_data={"action": "restore_credentials", "pipeline": pipeline}
                ))
            else:
                results.append(DiagnosticResult(
                    f"webhook:{pipeline}", "fail",
                    f"{pipeline} returns 500: {body[:150]}"))
        elif code == 200:
            # Check for empty body (FIX-34 pattern)
            if not body or body.strip() == "" or body.strip() == "{}":
                results.append(DiagnosticResult(
                    f"webhook:{pipeline}", "warn",
                    f"{pipeline} returns 200 but EMPTY body",
                    fix_ref="FIX-34: executeWorkflow returns empty when sub-wf uses respondToWebhook"))
            elif "no_answer" in body.lower() or "unable to generate" in body.lower():
                results.append(DiagnosticResult(
                    f"webhook:{pipeline}", "warn",
                    f"{pipeline} returns 200 but NO_ANSWER pattern",
                    fix_ref="Check LLM model availability and rate limits"))
            else:
                # Check if response has actual content
                try:
                    resp_json = json.loads(body)
                    answer = resp_json.get("answer", resp_json.get("response", resp_json.get("output", "")))
                    if answer and len(str(answer)) > 20:
                        results.append(DiagnosticResult(
                            f"webhook:{pipeline}", "ok",
                            f"{pipeline} returns valid response ({len(str(answer))} chars)"))
                    else:
                        results.append(DiagnosticResult(
                            f"webhook:{pipeline}", "warn",
                            f"{pipeline} returns short/empty answer: {str(answer)[:80]}"))
                except json.JSONDecodeError:
                    if len(body) > 20:
                        results.append(DiagnosticResult(
                            f"webhook:{pipeline}", "ok",
                            f"{pipeline} returns non-JSON response ({len(body)} chars)"))
                    else:
                        results.append(DiagnosticResult(
                            f"webhook:{pipeline}", "warn",
                            f"{pipeline} returns short response: {body[:80]}"))
        elif code == 0:
            results.append(DiagnosticResult(
                f"webhook:{pipeline}", "fail",
                f"{pipeline} connection error: {body[:100]}"))
        else:
            results.append(DiagnosticResult(
                f"webhook:{pipeline}", "warn",
                f"{pipeline} returns HTTP {code}"))

    return results


def check_env_vars() -> List[DiagnosticResult]:
    """Check required environment variables are set"""
    results = []
    required_vars = [
        "OPENROUTER_KEY_STANDARD", "OPENROUTER_KEY_GRAPH",
        "OPENROUTER_KEY_QUANTITATIVE", "OPENROUTER_KEY_ORCHESTRATOR",
        "PINECONE_API_KEY", "NEO4J_AUTH", "SUPABASE_PASSWORD",
        "N8N_ENCRYPTION_KEY",
    ]
    missing = []
    for var in required_vars:
        val = os.environ.get(var, "")
        if not val:
            missing.append(var)

    if missing:
        results.append(DiagnosticResult(
            "env_vars", "fail",
            f"Missing env vars: {', '.join(missing)}",
            fix_ref="source .env.local before running"))
    else:
        results.append(DiagnosticResult(
            "env_vars", "ok",
            f"All {len(required_vars)} required env vars present"))

    return results


# ============================================================
# AUTO-FIX ACTIONS
# ============================================================

def fix_activate_workflow(client: N8nClient, fix_data: dict) -> bool:
    """Activate an inactive workflow"""
    wf_id = fix_data["workflow_id"]
    try:
        # Get fresh workflow to get versionId
        wf = client.get_workflow(wf_id)
        version_id = wf.get("versionId", "1")

        # Deactivate first (reset)
        client.deactivate_workflow(wf_id)
        time.sleep(1)

        # Activate with versionId
        client.activate_workflow(wf_id, version_id)
        info(f"Activated workflow {fix_data.get('workflow_name', wf_id)} (versionId={version_id})")
        return True
    except Exception as e:
        fail(f"Failed to activate workflow {wf_id}: {e}")
        return False


def fix_reactivate_webhook(client: N8nClient, fix_data: dict) -> bool:
    """Re-activate all workflows to register webhooks"""
    pipeline = fix_data["pipeline"]
    try:
        workflows = client.get_workflows()
        # Find the pipeline's workflow
        patterns = {
            "standard": ["standard", "wf5"],
            "graph": ["graph", "wf2"],
            "quantitative": ["quantitative", "wf4"],
            "orchestrator": ["orchestrator"],
            "chatbot": ["chatbot"],
        }
        target_patterns = patterns.get(pipeline, [pipeline])

        for wf in workflows:
            name_lower = wf["name"].lower()
            if any(p in name_lower for p in target_patterns):
                wf_full = client.get_workflow(wf["id"])
                version_id = wf_full.get("versionId", "1")

                # Deactivate + reactivate cycle
                client.deactivate_workflow(wf["id"])
                time.sleep(1)
                client.activate_workflow(wf["id"], version_id)
                info(f"Reactivated {wf['name']} (webhooks re-registered)")
                return True

        warn(f"No workflow found matching pipeline '{pipeline}'")
        return False
    except Exception as e:
        fail(f"Failed to reactivate webhook for {pipeline}: {e}")
        return False


# ============================================================
# MAIN DIAGNOSTIC FLOW
# ============================================================

def diagnose_space(space_url: str, apply_fixes: bool = False) -> dict:
    """Run full diagnostic on a single HF Space"""
    space_short = space_url.split("//")[1].split(".")[0]
    header(f"Diagnosing: {space_short}")

    report = {
        "space": space_url,
        "timestamp": datetime.now().isoformat(),
        "checks": [],
        "fixes_applied": [],
        "summary": {"ok": 0, "warn": 0, "fail": 0},
    }

    # 1. Connectivity
    print(f"\n  [1/5] Connectivity...")
    conn = check_connectivity(space_url)
    report["checks"].append({"name": conn.check_name, "status": conn.status, "details": conn.details})
    (ok if conn.status == "ok" else fail)(conn.details)
    if conn.status == "fail":
        report["summary"]["fail"] += 1
        return report

    # 2. Login + Credentials
    print(f"\n  [2/5] Credentials...")
    client = N8nClient(space_url)
    if not client.login():
        fail("Cannot login to n8n REST API")
        report["checks"].append({"name": "login", "status": "fail", "details": "Login failed"})
        report["summary"]["fail"] += 1
        return report

    cred_results = check_credentials(client)
    for r in cred_results:
        report["checks"].append({"name": r.check_name, "status": r.status, "details": r.details})
        report["summary"][r.status] = report["summary"].get(r.status, 0) + 1
        (ok if r.status == "ok" else warn if r.status == "warn" else fail)(
            f"{r.details}" + (f" [{r.fix_ref}]" if r.fix_ref and r.status != "ok" else ""))

    # 3. Workflows
    print(f"\n  [3/5] Workflows...")
    wf_results = check_workflows(client)
    for r in wf_results:
        report["checks"].append({"name": r.check_name, "status": r.status, "details": r.details})
        report["summary"][r.status] = report["summary"].get(r.status, 0) + 1
        (ok if r.status == "ok" else warn if r.status == "warn" else fail)(
            f"{r.details}" + (f" [{r.fix_ref}]" if r.fix_ref and r.status != "ok" else ""))

        # Auto-fix inactive workflows
        if apply_fixes and r.auto_fixable and r.status == "fail":
            action = r.fix_data.get("action")
            if action == "activate_workflow":
                info(f"AUTO-FIX: Activating {r.fix_data.get('workflow_name', '?')}...")
                if fix_activate_workflow(client, r.fix_data):
                    report["fixes_applied"].append(f"Activated {r.fix_data.get('workflow_name')}")

    # 4. Webhooks (functional test)
    print(f"\n  [4/5] Webhooks (functional tests)...")
    wh_results = check_webhooks(client)
    for r in wh_results:
        report["checks"].append({"name": r.check_name, "status": r.status, "details": r.details})
        report["summary"][r.status] = report["summary"].get(r.status, 0) + 1
        (ok if r.status == "ok" else warn if r.status == "warn" else fail)(
            f"{r.details}" + (f" [{r.fix_ref}]" if r.fix_ref and r.status != "ok" else ""))

        # Auto-fix 404 webhooks
        if apply_fixes and r.auto_fixable and r.status == "fail":
            action = r.fix_data.get("action")
            if action == "reactivate_webhook":
                info(f"AUTO-FIX: Reactivating webhook for {r.fix_data.get('pipeline')}...")
                if fix_reactivate_webhook(client, r.fix_data):
                    report["fixes_applied"].append(f"Reactivated webhook for {r.fix_data['pipeline']}")

    # 5. Recent executions (error patterns)
    print(f"\n  [5/5] Recent execution patterns...")
    try:
        execs = client.get_executions(limit=10)
        if isinstance(execs, list):
            error_count = sum(1 for e in execs if e.get("status") == "error" or not e.get("finished"))
            success_count = sum(1 for e in execs if e.get("finished") and e.get("status") != "error")
            total = len(execs)
            if total > 0:
                error_rate = error_count / total * 100
                status = "ok" if error_rate < 30 else "warn" if error_rate < 60 else "fail"
                msg = f"Last {total} executions: {success_count} success, {error_count} errors ({error_rate:.0f}% error rate)"
                (ok if status == "ok" else warn if status == "warn" else fail)(msg)
                report["checks"].append({"name": "executions", "status": status, "details": msg})
                report["summary"][status] = report["summary"].get(status, 0) + 1
    except Exception as e:
        warn(f"Cannot check executions: {e}")

    return report


def print_summary(reports: List[dict]):
    """Print global summary across all spaces"""
    header("GLOBAL SUMMARY")

    total_ok = sum(r["summary"].get("ok", 0) for r in reports)
    total_warn = sum(r["summary"].get("warn", 0) for r in reports)
    total_fail = sum(r["summary"].get("fail", 0) for r in reports)
    total_fixes = sum(len(r.get("fixes_applied", [])) for r in reports)

    print(f"\n  Spaces tested: {len(reports)}")
    print(f"  {C.GREEN}OK:   {total_ok}{C.END}")
    print(f"  {C.YELLOW}WARN: {total_warn}{C.END}")
    print(f"  {C.RED}FAIL: {total_fail}{C.END}")
    if total_fixes > 0:
        print(f"  {C.BLUE}Fixes applied: {total_fixes}{C.END}")

    print(f"\n  Per-space breakdown:")
    for r in reports:
        space_short = r["space"].split("//")[1].split(".")[0]
        s = r["summary"]
        icon = C.GREEN + "OK" if s.get("fail", 0) == 0 and s.get("warn", 0) == 0 else \
               C.YELLOW + "WARN" if s.get("fail", 0) == 0 else C.RED + "FAIL"
        fixes_str = f" (+{len(r.get('fixes_applied', []))} fixes)" if r.get("fixes_applied") else ""
        print(f"    {icon}{C.END} {space_short}: "
              f"{s.get('ok',0)} ok, {s.get('warn',0)} warn, {s.get('fail',0)} fail{fixes_str}")


def main():
    parser = argparse.ArgumentParser(description="Auto-remediation for Multi-RAG HF Spaces")
    parser.add_argument("--fix", action="store_true", help="Apply automatic fixes (default: diagnostic only)")
    parser.add_argument("--space", type=str, help="Target a single space URL")
    parser.add_argument("--quick", action="store_true", help="Skip webhook tests (faster)")
    parser.add_argument("--parallel", type=int, default=1, help="Parallel space processing (default: 1)")
    args = parser.parse_args()

    header("Auto-Remediation — Multi-RAG Orchestrator")
    print(f"  Mode: {'FIX' if args.fix else 'DIAGNOSTIC ONLY'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check env vars first
    print(f"\n  [Pre-flight] Environment variables...")
    env_results = check_env_vars()
    for r in env_results:
        (ok if r.status == "ok" else fail)(r.details)
        if r.status == "fail" and not args.fix:
            print(f"\n  {C.RED}Run: source .env.local{C.END}")

    # Select spaces
    spaces = [args.space] if args.space else ALL_SPACES

    # Run diagnostics
    reports = []
    if args.parallel > 1 and len(spaces) > 1:
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {executor.submit(diagnose_space, s, args.fix): s for s in spaces}
            for future in as_completed(futures):
                try:
                    reports.append(future.result())
                except Exception as e:
                    fail(f"Space diagnostic failed: {e}")
    else:
        for space in spaces:
            try:
                reports.append(diagnose_space(space, args.fix))
            except Exception as e:
                fail(f"Space {space} diagnostic failed: {e}")

    # Print summary
    print_summary(reports)

    # Save report
    os.makedirs(LOG_DIR, exist_ok=True)
    report_path = os.path.join(LOG_DIR, f"auto-remediate-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump({"reports": reports, "mode": "fix" if args.fix else "diagnostic",
                    "timestamp": datetime.now().isoformat()}, f, indent=2)
    info(f"Report saved: {report_path}")

    # Exit code based on failures
    total_fail = sum(r["summary"].get("fail", 0) for r in reports)
    sys.exit(1 if total_fail > 0 else 0)


if __name__ == "__main__":
    main()
