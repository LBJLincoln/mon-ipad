#!/usr/bin/env python3
"""
Deploy Standard RAG V3.8 — Switch from Groq direct to LiteLLM proxy.

Root cause: All 5 Groq keys are 403/429 rate-limited.
Fix: Route all LLM calls through LiteLLM proxy (S7) which has 13-provider fallback.

Steps:
  1. Login to S1 via cookie auth
  2. GET live Standard workflow (TmgyRP20N4JFd9CB)
  3. Find all HTTP Request nodes calling api.groq.com → change URL to LiteLLM proxy
  4. Change Authorization headers to LiteLLM key
  5. Find Code nodes referencing Groq model names → change to 'smart'
  6. Save modified JSON to n8n/live/standard-rag-v3.8-litellm.json
  7. PATCH + activate to S1, S3, S5
  8. Run a smoke test
"""

import json
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error
import re
import os
from datetime import datetime

# === Force IPv4 (GCP VM has broken IPv6) ===
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    responses = _original_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET] or responses
socket.getaddrinfo = _ipv4_only_getaddrinfo

# === Config ===
WORKFLOW_ID = "TmgyRP20N4JFd9CB"
N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "Bearer sk-litellm-nomos-2026"
LITELLM_MODEL = "smart"

# Groq patterns to detect
GROQ_URL_PATTERNS = [
    "api.groq.com",
    "groq.com/openai",
]
GROQ_MODEL_PATTERNS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.3-70b",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
]
GROQ_AUTH_PATTERNS = [
    "gsk_",
    "$env.GROQ_API_KEY",
    "env.GROQ_API_KEY",
]

SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
}

OUTPUT_PATH = "/home/termius/mon-ipad/n8n/live/standard-rag-v3.8-litellm.json"

# SSL context — skip verification for HF Spaces
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def http_request(url, method="GET", data=None, headers=None, cookie=None, timeout=30):
    """Make HTTP request with cookie auth."""
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
        print(f"  Login OK — cookie: {cookie_str[:60]}...")
        return cookie_str
    else:
        print(f"  Login FAILED ({status}): {body[:200]}")
        return None


def get_workflow(base_url, cookie):
    """GET the live workflow JSON from n8n."""
    url = f"{base_url}/rest/workflows/{WORKFLOW_ID}"
    status, body, _ = http_request(url, method="GET", cookie=cookie)
    if status != 200:
        print(f"  GET workflow FAILED ({status}): {body[:300]}")
        return None
    data = json.loads(body)
    # n8n wraps in "data" key
    return data.get("data", data)


def is_groq_url(url_str):
    """Check if a URL string points to Groq API."""
    if not url_str or not isinstance(url_str, str):
        return False
    return any(p in url_str for p in GROQ_URL_PATTERNS)


def is_groq_auth(value):
    """Check if an auth value is a Groq key."""
    if not value or not isinstance(value, str):
        return False
    return any(p in value for p in GROQ_AUTH_PATTERNS)


def is_groq_model(model_str):
    """Check if a model string is a Groq model."""
    if not model_str or not isinstance(model_str, str):
        return False
    return any(p in model_str for p in GROQ_MODEL_PATTERNS)


def is_litellm_url(url_str):
    """Check if URL already points to LiteLLM."""
    if not url_str or not isinstance(url_str, str):
        return False
    return "nomos-rag-engine-7" in url_str


def patch_http_request_node(node, changes_log):
    """Patch an HTTP Request node that calls Groq → LiteLLM."""
    params = node.get("parameters", {})
    node_name = node.get("name", "unnamed")
    changed = False

    # 1. Check and fix URL
    url = params.get("url", "")
    if is_groq_url(url):
        old_url = url
        params["url"] = LITELLM_URL
        changes_log.append(f"  NODE '{node_name}': URL changed from '{old_url}' → LiteLLM proxy")
        changed = True
    elif is_litellm_url(url):
        # Already pointing to LiteLLM — good, but check auth
        pass

    # 2. Check and fix Authorization header
    header_params = params.get("headerParameters", {})
    if isinstance(header_params, dict):
        param_list = header_params.get("parameters", [])
        if isinstance(param_list, list):
            for hp in param_list:
                name = hp.get("name", "")
                value = hp.get("value", "")
                if name.lower() == "authorization":
                    if is_groq_auth(value) or "gsk_" in value:
                        old_val = value[:30] + "..."
                        hp["value"] = LITELLM_KEY
                        changes_log.append(f"  NODE '{node_name}': Auth header changed from '{old_val}' → LiteLLM key")
                        changed = True
                    elif value == LITELLM_KEY:
                        # Already correct
                        pass

    # 3. Check and fix model in jsonBody
    json_body = params.get("jsonBody", "")
    if isinstance(json_body, str):
        for model_name in GROQ_MODEL_PATTERNS:
            if model_name in json_body:
                new_body = json_body.replace(model_name, LITELLM_MODEL)
                params["jsonBody"] = new_body
                json_body = new_body  # Update for next iteration
                changes_log.append(f"  NODE '{node_name}': Model in jsonBody changed from '{model_name}' → '{LITELLM_MODEL}'")
                changed = True

    # Also check if URL is LiteLLM but auth is still Groq
    if is_litellm_url(params.get("url", "")):
        header_params = params.get("headerParameters", {})
        if isinstance(header_params, dict):
            param_list = header_params.get("parameters", [])
            if isinstance(param_list, list):
                for hp in param_list:
                    name = hp.get("name", "")
                    value = hp.get("value", "")
                    if name.lower() == "authorization" and is_groq_auth(value):
                        hp["value"] = LITELLM_KEY
                        changes_log.append(f"  NODE '{node_name}': Auth still Groq on LiteLLM URL — fixed")
                        changed = True

    return changed


def patch_code_node(node, changes_log):
    """Patch Code nodes that reference Groq models or URLs."""
    params = node.get("parameters", {})
    node_name = node.get("name", "unnamed")
    changed = False

    js_code = params.get("jsCode", "")
    if not js_code:
        return False

    # Replace Groq model names with 'smart'
    new_code = js_code
    for model_name in GROQ_MODEL_PATTERNS:
        if model_name in new_code:
            new_code = new_code.replace(model_name, LITELLM_MODEL)
            changes_log.append(f"  NODE '{node_name}' (Code): Model '{model_name}' → '{LITELLM_MODEL}'")
            changed = True

    # Replace Groq URLs
    for pattern in GROQ_URL_PATTERNS:
        if pattern in new_code:
            # Replace the full Groq chat completions URL
            new_code = re.sub(
                r'https?://api\.groq\.com/openai/v1/chat/completions',
                LITELLM_URL,
                new_code
            )
            changes_log.append(f"  NODE '{node_name}' (Code): Groq URL → LiteLLM proxy URL")
            changed = True

    # Replace Groq API key references in code
    # Pattern: Bearer gsk_xxxx
    new_code = re.sub(
        r'Bearer gsk_[A-Za-z0-9]+',
        LITELLM_KEY,
        new_code
    )
    if new_code != js_code and "Bearer gsk_" in js_code:
        changes_log.append(f"  NODE '{node_name}' (Code): Groq API key → LiteLLM key")
        changed = True

    # Replace $env.GROQ_API_KEY references
    if "$env.GROQ_API_KEY" in new_code:
        # Replace expressions like `$env.GROQ_API_KEY` with the literal LiteLLM key
        new_code = re.sub(
            r'\$env\.GROQ_API_KEY[_A-Z0-9]*',
            '"sk-litellm-nomos-2026"',
            new_code
        )
        changes_log.append(f"  NODE '{node_name}' (Code): $env.GROQ_API_KEY → LiteLLM key literal")
        changed = True

    if changed:
        params["jsCode"] = new_code
    return changed


def patch_set_node(node, changes_log):
    """Patch Set/Assign nodes that may contain Groq references."""
    params = node.get("parameters", {})
    node_name = node.get("name", "unnamed")
    changed = False

    # Check assignments in Set nodes
    assignments = params.get("assignments", {})
    if isinstance(assignments, dict):
        assign_list = assignments.get("assignments", [])
        if isinstance(assign_list, list):
            for assignment in assign_list:
                value = assignment.get("value", "")
                if isinstance(value, str):
                    for model_name in GROQ_MODEL_PATTERNS:
                        if model_name in value:
                            assignment["value"] = value.replace(model_name, LITELLM_MODEL)
                            changes_log.append(f"  NODE '{node_name}' (Set): Model '{model_name}' → '{LITELLM_MODEL}'")
                            changed = True
                    if is_groq_url(value):
                        assignment["value"] = LITELLM_URL
                        changes_log.append(f"  NODE '{node_name}' (Set): Groq URL → LiteLLM URL")
                        changed = True

    # Check options/values
    for key in ["value", "url", "model"]:
        val = params.get(key, "")
        if isinstance(val, str):
            for model_name in GROQ_MODEL_PATTERNS:
                if model_name in val:
                    params[key] = val.replace(model_name, LITELLM_MODEL)
                    changes_log.append(f"  NODE '{node_name}': param '{key}' model → '{LITELLM_MODEL}'")
                    changed = True

    return changed


def deep_scan_node(node, changes_log):
    """Deep scan any node type for Groq references in all string parameters."""
    node_name = node.get("name", "unnamed")
    changed = False

    def scan_and_replace(obj, path=""):
        nonlocal changed
        if isinstance(obj, dict):
            for key, val in obj.items():
                if isinstance(val, str):
                    new_val = val
                    for model_name in GROQ_MODEL_PATTERNS:
                        if model_name in new_val:
                            new_val = new_val.replace(model_name, LITELLM_MODEL)
                            changes_log.append(f"  NODE '{node_name}' (deep): {path}.{key} model '{model_name}' → '{LITELLM_MODEL}'")
                            changed = True
                    for groq_url in GROQ_URL_PATTERNS:
                        if groq_url in new_val:
                            new_val = re.sub(
                                r'https?://api\.groq\.com/openai/v1/chat/completions',
                                LITELLM_URL,
                                new_val
                            )
                            changes_log.append(f"  NODE '{node_name}' (deep): {path}.{key} Groq URL → LiteLLM")
                            changed = True
                    if new_val != val:
                        obj[key] = new_val
                elif isinstance(val, (dict, list)):
                    scan_and_replace(val, f"{path}.{key}")
            return obj
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, (dict, list)):
                    scan_and_replace(item, f"{path}[{i}]")
                elif isinstance(item, str):
                    new_item = item
                    for model_name in GROQ_MODEL_PATTERNS:
                        if model_name in new_item:
                            new_item = new_item.replace(model_name, LITELLM_MODEL)
                            changed = True
                    if new_item != item:
                        obj[i] = new_item
            return obj

    scan_and_replace(node.get("parameters", {}))
    return changed


def deploy_workflow(base_url, cookie, workflow_json):
    """3-step deploy: PATCH → GET versionId → POST activate."""
    url = f"{base_url}/rest/workflows/{WORKFLOW_ID}"

    # Step 1: PATCH
    payload = {
        "name": workflow_json["name"],
        "nodes": workflow_json["nodes"],
        "connections": workflow_json["connections"],
        "settings": workflow_json.get("settings", {}),
    }

    status, body, _ = http_request(url, method="PATCH", data=payload, cookie=cookie, timeout=60)
    if status != 200:
        print(f"  PATCH FAILED ({status}): {body[:300]}")
        return False
    print(f"  PATCH OK")

    # Step 2: GET versionId
    status, body, _ = http_request(url, method="GET", cookie=cookie)
    if status != 200:
        print(f"  GET versionId FAILED ({status}): {body[:200]}")
        return False

    wf_data = json.loads(body)
    inner = wf_data.get("data", wf_data)
    version_id = inner.get("versionId")
    print(f"  versionId: {version_id}")

    # Step 3: POST activate
    activate_url = f"{base_url}/rest/workflows/{WORKFLOW_ID}/activate"
    activate_data = {}
    if version_id:
        activate_data["versionId"] = version_id

    status, body, _ = http_request(activate_url, method="POST", data=activate_data, cookie=cookie)
    if status in (200, 201):
        print(f"  ACTIVATE OK")
        return True
    else:
        print(f"  ACTIVATE ({status}): {body[:200]}")
        # Retry without versionId
        if version_id:
            status2, body2, _ = http_request(activate_url, method="POST", data={}, cookie=cookie)
            if status2 in (200, 201):
                print(f"  ACTIVATE (retry) OK")
                return True
        return status == 200


def smoke_test(base_url, question="Quels sont les principaux ratios de solvabilite en finance?"):
    """Send a quick test query to verify the pipeline works."""
    url = f"{base_url}/webhook/rag-multi-index-v3"
    data = {
        "query": question,
        "user_context": {"tenant_id": "benchmark", "groups": ["admin"]},
        "disable_acl": True,
    }

    start = time.time()
    status, body, _ = http_request(url, method="POST", data=data, timeout=120)
    elapsed = time.time() - start

    if status == 200:
        try:
            resp = json.loads(body)
            if isinstance(resp, list):
                resp = resp[0] if resp else {}
            answer = resp.get("response", "")
            sources = resp.get("sources", [])
            version = resp.get("version", "?")

            unable = "unable to generate" in answer.lower() or "impossible de" in answer.lower()

            print(f"  Status: OK | Version: {version} | Latency: {elapsed:.1f}s")
            print(f"  Answer length: {len(answer)} chars | Sources: {len(sources)}")
            print(f"  Contains 'unable to generate': {'YES — STILL BROKEN' if unable else 'NO — FIXED!'}")
            print(f"  Preview: {answer[:250]}...")
            return not unable
        except json.JSONDecodeError:
            print(f"  JSON parse error: {body[:200]}")
            return False
    else:
        print(f"  HTTP {status}: {body[:200]}")
        return False


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 72)
    print("DEPLOY Standard RAG V3.8 — Groq → LiteLLM Migration")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 72)

    # ----------------------------------------------------------
    # PHASE 0: Check LiteLLM proxy is alive
    # ----------------------------------------------------------
    print("\n[PHASE 0] Checking LiteLLM proxy (S7)...")
    s7_url = "https://lbjlincoln-nomos-rag-engine-7.hf.space/health"
    status, body, _ = http_request(s7_url, method="GET", timeout=15)
    if status == 200:
        print(f"  S7 LiteLLM: UP ({body[:100]})")
    else:
        print(f"  S7 LiteLLM: status={status} — {body[:200]}")
        print("  WARNING: LiteLLM proxy may be down. Continuing anyway (proxy may wake on request)...")

    # Also test the model list endpoint
    models_url = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/models"
    status, body, _ = http_request(models_url, method="GET",
                                    headers={"Authorization": LITELLM_KEY}, timeout=15)
    if status == 200:
        try:
            models_data = json.loads(body)
            model_names = [m.get("id", "?") for m in models_data.get("data", [])]
            print(f"  Available models: {model_names[:10]}")
            if LITELLM_MODEL in model_names:
                print(f"  Model '{LITELLM_MODEL}' is available — GOOD")
            else:
                print(f"  WARNING: Model '{LITELLM_MODEL}' not found in list. Available: {model_names}")
                # Try with first available model as fallback info
        except:
            print(f"  Models response: {body[:200]}")
    else:
        print(f"  Models endpoint: {status} — {body[:200]}")

    # ----------------------------------------------------------
    # PHASE 1: Login + GET live workflow from S1
    # ----------------------------------------------------------
    print(f"\n[PHASE 1] Fetching live workflow from S1...")
    s1_url = SPACES["S1"]

    cookie = login(s1_url)
    if not cookie:
        print("FATAL: Cannot login to S1")
        sys.exit(1)

    workflow = get_workflow(s1_url, cookie)
    if not workflow:
        print("FATAL: Cannot GET workflow")
        sys.exit(1)

    print(f"  Workflow name: {workflow['name']}")
    print(f"  Node count: {len(workflow['nodes'])}")
    print(f"  Updated at: {workflow.get('updatedAt', '?')}")

    # ----------------------------------------------------------
    # PHASE 2: Analyze + Patch all Groq references
    # ----------------------------------------------------------
    print(f"\n[PHASE 2] Scanning {len(workflow['nodes'])} nodes for Groq references...")

    changes = []
    nodes_changed = set()
    groq_http_nodes = []
    groq_code_nodes = []
    already_litellm_nodes = []

    for node in workflow["nodes"]:
        node_type = node.get("type", "")
        node_name = node.get("name", "unnamed")
        params = node.get("parameters", {})

        # Track what we find
        url = params.get("url", "")
        if is_groq_url(url):
            groq_http_nodes.append(node_name)
        elif is_litellm_url(url):
            already_litellm_nodes.append(node_name)

        js_code = params.get("jsCode", "")
        if js_code and any(m in js_code for m in GROQ_MODEL_PATTERNS):
            groq_code_nodes.append(node_name)

        # Patch based on type
        prev_len = len(changes)
        if "httpRequest" in node_type:
            patch_http_request_node(node, changes)
        elif "code" in node_type.lower():
            patch_code_node(node, changes)
        elif "set" in node_type.lower() or "assign" in node_type.lower():
            patch_set_node(node, changes)

        # Deep scan every node regardless
        deep_scan_node(node, changes)

        if len(changes) > prev_len:
            nodes_changed.add(node_name)

    # Also verify: check that ALL HTTP Request nodes pointing to LiteLLM have correct auth
    print(f"\n  --- Verification pass: ensuring LiteLLM auth on all proxy-targeting nodes ---")
    for node in workflow["nodes"]:
        node_type = node.get("type", "")
        node_name = node.get("name", "unnamed")
        params = node.get("parameters", {})

        if "httpRequest" not in node_type:
            continue

        url = params.get("url", "")
        if not is_litellm_url(url):
            continue

        # This node targets LiteLLM — ensure auth is correct
        header_params = params.get("headerParameters", {})
        if isinstance(header_params, dict):
            param_list = header_params.get("parameters", [])
            if isinstance(param_list, list):
                has_auth = False
                for hp in param_list:
                    if hp.get("name", "").lower() == "authorization":
                        has_auth = True
                        if hp["value"] != LITELLM_KEY:
                            old = hp["value"][:30]
                            hp["value"] = LITELLM_KEY
                            changes.append(f"  NODE '{node_name}' (verify): Auth '{old}...' → LiteLLM key")
                            nodes_changed.add(node_name)
                if not has_auth:
                    # Add Authorization header
                    param_list.append({"name": "Authorization", "value": LITELLM_KEY})
                    changes.append(f"  NODE '{node_name}' (verify): Added missing Authorization header")
                    nodes_changed.add(node_name)

        # Also fix model in jsonBody if still Groq
        json_body = params.get("jsonBody", "")
        if isinstance(json_body, str):
            for model_name in GROQ_MODEL_PATTERNS:
                if model_name in json_body:
                    params["jsonBody"] = json_body.replace(model_name, LITELLM_MODEL)
                    json_body = params["jsonBody"]
                    changes.append(f"  NODE '{node_name}' (verify): jsonBody model '{model_name}' → '{LITELLM_MODEL}'")
                    nodes_changed.add(node_name)

    # Summary of findings
    print(f"\n  SCAN RESULTS:")
    print(f"  Groq HTTP Request nodes found: {groq_http_nodes if groq_http_nodes else 'none'}")
    print(f"  Already LiteLLM nodes: {already_litellm_nodes if already_litellm_nodes else 'none'}")
    print(f"  Groq Code nodes found: {groq_code_nodes if groq_code_nodes else 'none'}")
    print(f"  Total changes made: {len(changes)}")
    print(f"  Nodes modified: {sorted(nodes_changed)}")

    if changes:
        print(f"\n  CHANGE LOG:")
        for c in changes:
            print(c)
    else:
        print(f"\n  No Groq references found — workflow may already be on LiteLLM.")
        print(f"  Proceeding with deploy anyway to ensure latest version is active.")

    # ----------------------------------------------------------
    # PHASE 3: Update workflow name + save to disk
    # ----------------------------------------------------------
    # Bump version in name
    old_name = workflow["name"]
    new_name = re.sub(r'V3\.\d+', 'V3.8', old_name)
    if new_name == old_name:
        new_name = old_name.replace("Standard RAG", "Standard RAG V3.8")
    if "LiteLLM" not in new_name:
        new_name = new_name.rstrip() + " (LiteLLM)"
    workflow["name"] = new_name
    print(f"\n  Workflow name: '{old_name}' → '{new_name}'")

    # Save to disk
    print(f"\n[PHASE 3] Saving to {OUTPUT_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"  Saved: {file_size:,} bytes")

    # ----------------------------------------------------------
    # PHASE 4: Deploy to S1, S3, S5
    # ----------------------------------------------------------
    print(f"\n[PHASE 4] Deploying to S1, S3, S5...")
    deploy_results = {}

    for space_name, base_url in SPACES.items():
        print(f"\n  --- {space_name} ({base_url}) ---")

        space_cookie = login(base_url)
        if not space_cookie:
            deploy_results[space_name] = "LOGIN_FAILED"
            continue

        success = deploy_workflow(base_url, space_cookie, workflow)
        deploy_results[space_name] = "OK" if success else "FAILED"

    print(f"\n  DEPLOY RESULTS:")
    for space, result in deploy_results.items():
        icon = "PASS" if result == "OK" else "FAIL"
        print(f"    {space}: {icon} ({result})")

    all_deployed = all(r == "OK" for r in deploy_results.values())
    if not all_deployed:
        print(f"\n  WARNING: Not all spaces deployed successfully.")

    # ----------------------------------------------------------
    # PHASE 5: Smoke test
    # ----------------------------------------------------------
    print(f"\n[PHASE 5] Smoke test (waiting 5s for activation)...")
    time.sleep(5)

    test_questions = [
        ("Quels sont les principaux ratios de solvabilite en finance?", "Finance"),
        ("Quelles sont les exigences du DTU 13.3?", "BTP"),
    ]

    for question, sector in test_questions:
        print(f"\n  --- Smoke test: {sector} ---")
        print(f"  Q: {question}")
        # Test on first successfully deployed space
        test_url = None
        for space, result in deploy_results.items():
            if result == "OK":
                test_url = SPACES[space]
                break
        if test_url:
            smoke_test(test_url, question)
        else:
            print(f"  SKIP: No space available for testing")

    # ----------------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------------
    print(f"\n{'=' * 72}")
    print("MIGRATION SUMMARY — Standard RAG V3.8 (Groq → LiteLLM)")
    print(f"{'=' * 72}")
    print(f"  Workflow: {workflow['name']}")
    print(f"  Changes: {len(changes)} modifications across {len(nodes_changed)} nodes")
    print(f"  Nodes changed: {sorted(nodes_changed)}")
    print(f"  LiteLLM URL: {LITELLM_URL}")
    print(f"  LiteLLM model: {LITELLM_MODEL}")
    print(f"  Saved to: {OUTPUT_PATH}")
    print(f"  Deploy: {deploy_results}")
    print(f"{'=' * 72}")
