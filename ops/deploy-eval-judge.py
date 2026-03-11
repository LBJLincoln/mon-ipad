#!/usr/bin/env python3
"""
Deploy Eval Judge workflow to S8 (lbjlincoln26-nomos-rag-engine-8).

This script:
  1. Checks if S8 is UP (health check)
  2. If DOWN, provides instructions to start it via HF API
  3. Logs in to n8n on S8
  4. Deploys eval-judge-workflow.json (create or update)
  5. Activates the workflow
  6. Tests the /webhook/eval-judge endpoint with a sample execution

Cookie auth pattern (API key returns 401 on HF Spaces n8n).
IPv4 monkey-patch for GCP VM compatibility.
"""

import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# === Force IPv4 (GCP VM has broken IPv6) ===
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    responses = _original_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET] or responses
socket.getaddrinfo = _ipv4_only_getaddrinfo

# === Load env vars from .env.local ===
ENV_FILE = "/home/termius/mon-ipad/.env.local"
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r") as f:
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

S8_URL = "https://lbjlincoln26-nomos-rag-engine-8.hf.space"
S8_SPACE_ID = "lbjlincoln26/nomos-rag-engine-8"
S8_HF_ACCOUNT = "lbjlincoln26"

WORKFLOW_JSON_PATH = "/home/termius/mon-ipad/n8n/live/eval-judge-workflow.json"
DEPLOY_STATE_PATH = "/home/termius/mon-ipad/n8n/live/eval-judge-deploy-state.json"

# HF Token for account lbjlincoln26 (second account)
HF_TOKEN_2 = os.environ.get("HF_TOKEN_2", "")

# SSL context — skip verification for HF Spaces
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


# ========================================
# HTTP Helpers
# ========================================

def http_request(url, method="GET", data=None, headers=None, cookie=None, timeout=30):
    """Make HTTP request with cookie auth. Returns (status, body, set_cookie)."""
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
        resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
        set_cookie = resp.headers.get("Set-Cookie", "")
        resp_data = resp.read().decode("utf-8")
        return resp.status, resp_data, set_cookie
    except urllib.error.HTTPError as e:
        body_err = ""
        try:
            body_err = e.read().decode("utf-8")
        except Exception:
            pass
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
                        for k in [
                            "path", "expires", "max-age", "domain",
                            "secure", "httponly", "samesite",
                        ]
                    ):
                        cookies.append(item)
        cookie_str = (
            "; ".join(cookies)
            if cookies
            else set_cookie.split(";")[0] if set_cookie else ""
        )
        print(f"  Login OK, cookie: {cookie_str[:60]}...")
        return cookie_str
    else:
        print(f"  Login FAILED ({status}): {body[:200]}")
        return None


# ========================================
# HF Space Management
# ========================================

def check_space_health(base_url, timeout=15):
    """Check if the HF Space is UP by hitting its root or health endpoint."""
    # Try n8n healthz first
    for endpoint in ["/healthz", "/rest/login", "/"]:
        url = f"{base_url}{endpoint}"
        status, body, _ = http_request(url, method="GET", timeout=timeout)
        if status in (200, 301, 302, 401, 404):
            return True, status, endpoint
    return False, 0, None


def get_space_status_via_api():
    """Check HF Space runtime status via HF API."""
    if not HF_TOKEN_2:
        return None, "HF_TOKEN_2 not set"

    url = f"https://huggingface.co/api/spaces/{S8_SPACE_ID}"
    headers = {"Authorization": f"Bearer {HF_TOKEN_2}"}
    status, body, _ = http_request(url, method="GET", headers=headers, timeout=15)

    if status == 200:
        data = json.loads(body)
        runtime = data.get("runtime", {})
        stage = runtime.get("stage", "UNKNOWN")
        hardware = runtime.get("hardware", {}).get("current", "UNKNOWN")
        return stage, f"stage={stage}, hardware={hardware}"
    elif status == 404:
        return "NOT_FOUND", "Space does not exist yet"
    else:
        return None, f"API error ({status}): {body[:200]}"


def restart_space_via_api():
    """Restart the HF Space using the HF API."""
    if not HF_TOKEN_2:
        print("  ERROR: HF_TOKEN_2 not set in .env.local — cannot restart Space")
        return False

    url = f"https://huggingface.co/api/spaces/{S8_SPACE_ID}/restart"
    headers = {"Authorization": f"Bearer {HF_TOKEN_2}"}
    status, body, _ = http_request(url, method="POST", headers=headers, timeout=30)

    if status in (200, 201, 202):
        print(f"  Restart request sent OK ({status})")
        return True
    else:
        print(f"  Restart FAILED ({status}): {body[:200]}")
        return False


def wait_for_space(base_url, max_wait=180, poll_interval=10):
    """Wait for the Space to become responsive."""
    print(f"  Waiting up to {max_wait}s for S8 to become responsive...")
    start = time.time()
    while time.time() - start < max_wait:
        is_up, status, endpoint = check_space_health(base_url, timeout=10)
        if is_up:
            elapsed = time.time() - start
            print(f"  S8 is UP (status={status} on {endpoint}) after {elapsed:.0f}s")
            return True
        elapsed = time.time() - start
        print(f"  Not yet ({elapsed:.0f}s elapsed)... retrying in {poll_interval}s")
        time.sleep(poll_interval)

    print(f"  TIMEOUT: S8 did not come up within {max_wait}s")
    return False


# ========================================
# Workflow Operations
# ========================================

def check_existing_workflow(base_url, cookie, workflow_name):
    """Check if a workflow with this name already exists. Returns its ID or None."""
    url = f"{base_url}/rest/workflows"
    status, body, _ = http_request(url, method="GET", cookie=cookie)

    if status == 200:
        resp = json.loads(body)
        workflows = resp.get("data", resp)
        if isinstance(workflows, list):
            for wf in workflows:
                if wf.get("name") == workflow_name:
                    return wf.get("id")
    return None


def create_workflow(base_url, cookie, workflow_json):
    """Create a new workflow via POST /rest/workflows. Returns the new workflow ID."""
    url = f"{base_url}/rest/workflows"

    payload = {
        "name": workflow_json["name"],
        "nodes": workflow_json["nodes"],
        "connections": workflow_json["connections"],
        "settings": workflow_json.get("settings", {}),
        "active": False,
    }

    status, body, _ = http_request(url, method="POST", data=payload, cookie=cookie, timeout=60)

    if status in (200, 201):
        resp = json.loads(body)
        inner = resp.get("data", resp)
        wf_id = inner.get("id")
        print(f"  CREATE OK -> workflow ID: {wf_id}")
        return wf_id
    else:
        print(f"  CREATE FAILED ({status}): {body[:300]}")
        return None


def update_workflow(base_url, cookie, workflow_id, workflow_json):
    """Update an existing workflow via PATCH."""
    url = f"{base_url}/rest/workflows/{workflow_id}"

    payload = {
        "name": workflow_json["name"],
        "nodes": workflow_json["nodes"],
        "connections": workflow_json["connections"],
        "settings": workflow_json.get("settings", {}),
    }

    status, body, _ = http_request(url, method="PATCH", data=payload, cookie=cookie, timeout=60)

    if status == 200:
        print(f"  PATCH OK for {workflow_id}")
        return True
    else:
        print(f"  PATCH FAILED ({status}) for {workflow_id}: {body[:300]}")
        return False


def activate_workflow(base_url, cookie, workflow_id):
    """Activate a workflow: GET versionId -> POST activate."""
    # Step 1: GET workflow to get versionId
    url = f"{base_url}/rest/workflows/{workflow_id}"
    status, body, _ = http_request(url, method="GET", cookie=cookie)

    version_id = None
    if status == 200:
        resp = json.loads(body)
        inner = resp.get("data", resp)
        version_id = inner.get("versionId")
        print(f"  versionId: {version_id}")
    else:
        print(f"  GET versionId FAILED ({status})")

    # Step 2: POST activate
    activate_url = f"{base_url}/rest/workflows/{workflow_id}/activate"
    activate_data = {}
    if version_id:
        activate_data["versionId"] = version_id

    status, body, _ = http_request(activate_url, method="POST", data=activate_data, cookie=cookie)

    if status in (200, 201):
        print(f"  ACTIVATE OK for {workflow_id}")
        return True
    else:
        print(f"  ACTIVATE ({status}): {body[:200]}")
        # Retry without versionId
        if version_id:
            status2, body2, _ = http_request(
                activate_url, method="POST", data={}, cookie=cookie
            )
            if status2 in (200, 201):
                print(f"  ACTIVATE (retry) OK")
                return True
        return False


# ========================================
# Eval Judge Endpoint Test
# ========================================

def test_eval_judge_endpoint(base_url):
    """Send a sample execution payload to /webhook/eval-judge and verify response."""
    url = f"{base_url}/webhook/eval-judge"

    # Sample execution data simulating a Standard pipeline result
    sample_payload = {
        "question": "Quels sont les principaux ratios de solvabilite bancaire selon Bale III?",
        "sector": "finance",
        "pipeline": "standard",
        "response": (
            "Les principaux ratios de solvabilite bancaire selon Bale III sont : "
            "1) Le ratio CET1 (Common Equity Tier 1) qui doit etre superieur a 4,5% des actifs ponderes par les risques. "
            "2) Le ratio Tier 1 qui doit depasser 6%. "
            "3) Le ratio de capital total qui doit etre au minimum de 8%. "
            "4) Le coussin de conservation de 2,5% supplementaire. "
            "5) Le ratio de levier (Leverage Ratio) minimum de 3%. "
            "Ces ratios visent a garantir la solidite financiere des etablissements bancaires "
            "et leur capacite a absorber les pertes en periode de stress."
        ),
        "sources": [
            {"title": "Bale III - Cadre reglementaire", "document_id": "doc_001"},
            {"title": "Ratios prudentiels bancaires", "document_id": "doc_002"},
        ],
        "space": "S1",
        "execution_id": f"test_{int(time.time())}",
        "latency_ms": 2450,
    }

    print(f"\n  Testing endpoint: {url}")
    print(f"  Question: {sample_payload['question'][:80]}...")
    print(f"  Sector: {sample_payload['sector']}")
    print(f"  Pipeline: {sample_payload['pipeline']}")

    start = time.time()
    status, body, _ = http_request(url, method="POST", data=sample_payload, timeout=120)
    elapsed = time.time() - start

    if status == 200:
        try:
            resp = json.loads(body)
            # Handle n8n list response
            if isinstance(resp, list):
                resp = resp[0] if resp else {}

            total_score = resp.get("total_score", resp.get("totalScore", "N/A"))
            classification = resp.get("classification", "N/A")
            accuracy = resp.get("accuracy_score", resp.get("accuracyScore", "N/A"))
            completeness = resp.get("completeness_score", resp.get("completenessScore", "N/A"))
            terminology = resp.get("terminology_score", resp.get("terminologyScore", "N/A"))
            sources = resp.get("sources_score", resp.get("sourcesScore", "N/A"))
            language = resp.get("language_score", resp.get("languageScore", "N/A"))
            reasoning = resp.get("judge_reasoning", resp.get("judgeReasoning", ""))
            failure = resp.get("failure_type", resp.get("failureType", None))
            suggested = resp.get("suggested_fix", resp.get("suggestedFix", None))

            print(f"\n  EVAL JUDGE RESPONSE ({elapsed:.1f}s):")
            print(f"  {'=' * 50}")
            print(f"  Total Score:       {total_score}/100")
            print(f"  Classification:    {classification}")
            print(f"  Accuracy:          {accuracy}/20")
            print(f"  Completeness:      {completeness}/20")
            print(f"  Terminology:       {terminology}/20")
            print(f"  Sources:           {sources}/20")
            print(f"  Language:          {language}/20")
            if failure:
                print(f"  Failure Type:      {failure}")
            if suggested:
                print(f"  Suggested Fix:     {suggested}")
            if reasoning:
                print(f"  Reasoning:         {reasoning[:300]}...")
            print(f"  {'=' * 50}")

            return True, resp
        except json.JSONDecodeError:
            print(f"  JSON parse error: {body[:300]}")
            return False, None
    else:
        print(f"  HTTP {status} ({elapsed:.1f}s): {body[:300]}")
        return False, None


# ========================================
# Main
# ========================================

def main():
    print("=" * 72)
    print("DEPLOY Eval Judge Workflow to S8")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Space: {S8_SPACE_ID}")
    print(f"URL: {S8_URL}")
    print("=" * 72)

    # ----------------------------------------------------------
    # PHASE 0: Check workflow JSON exists
    # ----------------------------------------------------------
    print(f"\n[PHASE 0] Loading workflow JSON...")

    if not os.path.exists(WORKFLOW_JSON_PATH):
        print(f"  ERROR: Workflow JSON not found at {WORKFLOW_JSON_PATH}")
        print(f"  Please create the eval-judge workflow JSON first.")
        print(f"  Expected path: {WORKFLOW_JSON_PATH}")
        sys.exit(1)

    with open(WORKFLOW_JSON_PATH, "r") as f:
        workflow_json = json.load(f)

    wf_name = workflow_json.get("name", "Eval Judge")
    node_count = len(workflow_json.get("nodes", []))
    print(f"  Workflow: {wf_name}")
    print(f"  Nodes: {node_count}")

    node_names = [n.get("name", "?") for n in workflow_json.get("nodes", [])]
    for i, name in enumerate(node_names, 1):
        print(f"    {i}. {name}")

    # ----------------------------------------------------------
    # PHASE 1: Check S8 health
    # ----------------------------------------------------------
    print(f"\n[PHASE 1] Checking S8 health...")

    is_up, status, endpoint = check_space_health(S8_URL)

    if is_up:
        print(f"  S8 is UP (status={status} on {endpoint})")
    else:
        print(f"  S8 appears DOWN (status={status})")

        # Check via HF API
        stage, info = get_space_status_via_api()
        print(f"  HF API status: {info}")

        if stage == "NOT_FOUND":
            print(f"\n  S8 does not exist yet. To create it:")
            print(f"  1. Go to https://huggingface.co/spaces/{S8_HF_ACCOUNT}")
            print(f"  2. Duplicate an existing n8n Space (e.g., S4)")
            print(f"  3. Name it: nomos-rag-engine-8")
            print(f"  4. Set to cpu-basic (free tier)")
            print(f"  5. Re-run this script")
            sys.exit(1)

        if stage in ("STOPPED", "SLEEPING", "PAUSED", None):
            print(f"\n  Attempting to restart S8 via HF API...")
            if restart_space_via_api():
                print(f"  Restart initiated. Waiting for S8 to come up...")
                if not wait_for_space(S8_URL, max_wait=180, poll_interval=10):
                    print(f"  FATAL: S8 did not come up after restart.")
                    print(f"  Manual steps:")
                    print(f"    1. Go to https://huggingface.co/spaces/{S8_SPACE_ID}")
                    print(f"    2. Click 'Restart this Space'")
                    print(f"    3. Wait for it to become RUNNING")
                    print(f"    4. Re-run this script")
                    sys.exit(1)
            else:
                print(f"\n  Could not restart S8 automatically.")
                print(f"  Manual steps:")
                print(f"    1. Go to https://huggingface.co/spaces/{S8_SPACE_ID}")
                print(f"    2. Click 'Restart this Space'")
                print(f"    3. Wait for it to become RUNNING")
                print(f"    4. Re-run this script")
                if not HF_TOKEN_2:
                    print(f"\n  Hint: Set HF_TOKEN_2 in .env.local for auto-restart capability")
                sys.exit(1)
        elif stage == "BUILDING":
            print(f"  S8 is currently BUILDING. Waiting...")
            if not wait_for_space(S8_URL, max_wait=300, poll_interval=15):
                print(f"  FATAL: Build did not complete in time.")
                sys.exit(1)
        elif stage == "RUNNING":
            # API says running but health check failed — maybe just slow
            print(f"  HF API says RUNNING but health check failed. Waiting...")
            if not wait_for_space(S8_URL, max_wait=60, poll_interval=5):
                print(f"  FATAL: S8 says RUNNING but not responding.")
                sys.exit(1)
        else:
            print(f"  Unknown stage: {stage}. Attempting to wait...")
            if not wait_for_space(S8_URL, max_wait=120, poll_interval=10):
                print(f"  FATAL: S8 is not accessible. Stage: {stage}")
                sys.exit(1)

    # ----------------------------------------------------------
    # PHASE 2: Login to n8n on S8
    # ----------------------------------------------------------
    print(f"\n[PHASE 2] Logging in to n8n on S8...")

    cookie = login(S8_URL)
    if not cookie:
        print(f"  FATAL: Cannot login to S8 n8n")
        print(f"  This may happen if S8 is a fresh Space with no n8n setup.")
        print(f"  Ensure n8n is configured with:")
        print(f"    Email: {N8N_EMAIL}")
        print(f"    Password: {N8N_PASSWORD}")
        sys.exit(1)

    # ----------------------------------------------------------
    # PHASE 3: Deploy workflow (create or update)
    # ----------------------------------------------------------
    print(f"\n[PHASE 3] Deploying workflow '{wf_name}' to S8...")

    # Check if already exists
    existing_id = check_existing_workflow(S8_URL, cookie, wf_name)

    if existing_id:
        print(f"  Workflow already exists with ID: {existing_id}")
        print(f"  Updating existing workflow...")
        if not update_workflow(S8_URL, cookie, existing_id, workflow_json):
            print(f"  FATAL: Could not update workflow")
            sys.exit(1)
        workflow_id = existing_id
        deploy_action = "UPDATED"
    else:
        print(f"  Creating new workflow...")
        workflow_id = create_workflow(S8_URL, cookie, workflow_json)
        if not workflow_id:
            print(f"  FATAL: Could not create workflow")
            sys.exit(1)
        deploy_action = "CREATED"

    print(f"  Workflow ID: {workflow_id}")
    print(f"  Action: {deploy_action}")

    # ----------------------------------------------------------
    # PHASE 4: Activate workflow
    # ----------------------------------------------------------
    print(f"\n[PHASE 4] Activating workflow...")

    if not activate_workflow(S8_URL, cookie, workflow_id):
        print(f"  WARNING: Activation may have failed. Testing endpoint anyway...")

    # Give n8n a moment to register the webhook
    print(f"  Waiting 3s for webhook registration...")
    time.sleep(3)

    # ----------------------------------------------------------
    # PHASE 5: Test /webhook/eval-judge endpoint
    # ----------------------------------------------------------
    print(f"\n[PHASE 5] Testing /webhook/eval-judge endpoint...")

    test_ok, test_response = test_eval_judge_endpoint(S8_URL)

    # ----------------------------------------------------------
    # PHASE 6: Save deploy state
    # ----------------------------------------------------------
    print(f"\n[PHASE 6] Saving deploy state...")

    state = {
        "deployed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "space": "S8",
        "space_url": S8_URL,
        "space_id": S8_SPACE_ID,
        "workflow_name": wf_name,
        "workflow_id": workflow_id,
        "deploy_action": deploy_action,
        "webhook_url": f"{S8_URL}/webhook/eval-judge",
        "test_result": "PASS" if test_ok else "FAIL",
        "test_response": test_response,
    }

    try:
        os.makedirs(os.path.dirname(DEPLOY_STATE_PATH), exist_ok=True)
        with open(DEPLOY_STATE_PATH, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print(f"  Saved to: {DEPLOY_STATE_PATH}")
    except Exception as e:
        print(f"  Could not save state: {e}")

    # ----------------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------------
    print(f"\n{'=' * 72}")
    print("DEPLOY SUMMARY — Eval Judge on S8")
    print(f"{'=' * 72}")
    print(f"  Space:          S8 ({S8_SPACE_ID})")
    print(f"  URL:            {S8_URL}")
    print(f"  Workflow:       {wf_name}")
    print(f"  Workflow ID:    {workflow_id}")
    print(f"  Action:         {deploy_action}")
    print(f"  Webhook:        {S8_URL}/webhook/eval-judge")
    print(f"  Endpoint Test:  {'PASS' if test_ok else 'FAIL'}")
    print(f"")
    print(f"  Usage from eval scripts:")
    print(f"    POST {S8_URL}/webhook/eval-judge")
    print(f"    Body: {{")
    print(f'      "question": "...",')
    print(f'      "sector": "finance|btp|juridique|industrie",')
    print(f'      "pipeline": "standard|graph|quantitative|orchestrator",')
    print(f'      "response": "...",')
    print(f'      "sources": [...],')
    print(f'      "space": "S1",')
    print(f'      "execution_id": "...",')
    print(f'      "latency_ms": 2450')
    print(f"    }}")
    print(f"")
    print(f"  Results stored in Supabase: execution_scores table")
    print(f"  Query: SELECT * FROM execution_scores ORDER BY created_at DESC LIMIT 20;")
    print(f"{'=' * 72}")

    if not test_ok:
        print(f"\n  NOTE: Endpoint test failed. This may be because:")
        print(f"  1. The eval-judge workflow JSON needs an LLM judge node")
        print(f"  2. The webhook path in the workflow does not match '/webhook/eval-judge'")
        print(f"  3. The LLM provider is rate-limited or down")
        print(f"  Check the workflow in n8n UI: {S8_URL}")

    return 0 if test_ok else 1


if __name__ == "__main__":
    sys.exit(main())
