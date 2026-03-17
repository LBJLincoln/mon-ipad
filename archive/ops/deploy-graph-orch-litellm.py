#!/usr/bin/env python3
"""
Deploy Graph RAG + Orchestrator — Switch from Groq direct to LiteLLM proxy.

Root cause: All 5 Groq keys are rate-limited (429).
Fix: Route all LLM calls through LiteLLM proxy (S7) which has multi-provider fallback.

Pipelines migrated:
  1. Graph RAG (6257AfT1l4FMC6lY) → V3.4-litellm
  2. Orchestrator (qOSaFFrqO8Jb4VGb) → V13-litellm

Steps per pipeline:
  1. Login to S1 via cookie auth
  2. GET live workflow
  3. Find ALL nodes referencing api.groq.com (HTTP Request nodes)
  4. Change URL to LiteLLM proxy
  5. CRITICAL: Change authentication from predefinedCredentialType to none
  6. Set Authorization header to LiteLLM key
  7. In Code nodes, change Groq model names to 'smart'
  8. Save fixed workflow JSON to n8n/live/
  9. Deploy to S1, S3, S5 via 3-step: PATCH → GET versionId → POST activate
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
N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "Bearer sk-litellm-nomos-2026"
LITELLM_MODEL = "smart"

# Pipelines to migrate
PIPELINES = {
    "graph": {
        "workflow_id": "6257AfT1l4FMC6lY",
        "webhook_path": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "output_path": "/home/termius/mon-ipad/n8n/live/graph-rag-v3.4-litellm.json",
        "version_tag": "V3.4",
        "new_version_tag": "V3.4-litellm",
        "smoke_question": "Quelles sont les relations entre les entites du secteur BTP?",
        "smoke_sector": "btp",
    },
    "orchestrator": {
        "workflow_id": "qOSaFFrqO8Jb4VGb",
        "webhook_path": "/webhook/orchestrator-v2",
        "output_path": "/home/termius/mon-ipad/n8n/live/orchestrator-v13-litellm.json",
        "version_tag": "V13",
        "new_version_tag": "V13-litellm",
        "smoke_question": "Quels sont les principaux ratios de solvabilite en finance?",
        "smoke_sector": "finance",
    },
}

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
GROQ_CREDENTIAL_TYPES = [
    "groqApi",
    "groqCloud",
]

SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
}

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


def get_workflow(base_url, cookie, workflow_id):
    """GET the live workflow JSON from n8n."""
    url = f"{base_url}/rest/workflows/{workflow_id}"
    status, body, _ = http_request(url, method="GET", cookie=cookie)
    if status != 200:
        print(f"  GET workflow FAILED ({status}): {body[:300]}")
        return None
    data = json.loads(body)
    return data.get("data", data)


def is_groq_url(url_str):
    if not url_str or not isinstance(url_str, str):
        return False
    return any(p in url_str for p in GROQ_URL_PATTERNS)


def is_groq_auth(value):
    if not value or not isinstance(value, str):
        return False
    return any(p in value for p in GROQ_AUTH_PATTERNS)


def is_groq_model(model_str):
    if not model_str or not isinstance(model_str, str):
        return False
    return any(p in model_str for p in GROQ_MODEL_PATTERNS)


def is_litellm_url(url_str):
    if not url_str or not isinstance(url_str, str):
        return False
    return "nomos-rag-engine-7" in url_str


def fix_authentication(node, changes_log):
    """CRITICAL: Remove predefinedCredentialType auth — it overrides headers with Groq creds.

    When authentication is 'predefinedCredentialType', n8n injects the stored credential
    (Groq API key) into the request, overriding any Authorization header we set.
    Changing to 'none' lets our explicit header take effect.
    """
    node_name = node.get("name", "unnamed")
    params = node.get("parameters", {})
    changed = False

    # Check if node uses predefinedCredentialType authentication
    auth = params.get("authentication", "")
    if auth == "predefinedCredentialType":
        params["authentication"] = "none"
        changes_log.append(f"  NODE '{node_name}': authentication changed 'predefinedCredentialType' → 'none'")
        changed = True

        # Also remove the credential reference to avoid confusion
        if "credentials" in node:
            creds = node["credentials"]
            # Remove Groq credential references
            keys_to_remove = []
            for cred_key, cred_val in creds.items():
                cred_name = ""
                if isinstance(cred_val, dict):
                    cred_name = cred_val.get("name", "")
                elif isinstance(cred_val, str):
                    cred_name = cred_val
                if any(g in cred_key.lower() for g in ["groq"]) or any(g in cred_name.lower() for g in ["groq"]):
                    keys_to_remove.append(cred_key)
            for k in keys_to_remove:
                del creds[k]
                changes_log.append(f"  NODE '{node_name}': removed Groq credential reference '{k}'")
                changed = True

    # Also check the 'credentials' block directly for Groq credential type
    if "credentials" in node:
        creds = node["credentials"]
        keys_to_remove = []
        for cred_key in creds:
            if any(g in cred_key.lower() for g in ["groq"]):
                keys_to_remove.append(cred_key)
        if keys_to_remove and auth != "predefinedCredentialType":
            # Credentials exist but auth mode wasn't predefined — still remove them
            for k in keys_to_remove:
                del node["credentials"][k]
                changes_log.append(f"  NODE '{node_name}': removed stale Groq credential '{k}'")
                changed = True

    return changed


def ensure_auth_header(node, changes_log):
    """Ensure the node has a proper Authorization header for LiteLLM."""
    node_name = node.get("name", "unnamed")
    params = node.get("parameters", {})
    changed = False

    # Get or create headerParameters
    header_params = params.get("headerParameters", {})
    if not isinstance(header_params, dict):
        header_params = {}

    param_list = header_params.get("parameters", [])
    if not isinstance(param_list, list):
        param_list = []

    # Check existing Authorization header
    has_auth = False
    for hp in param_list:
        name = hp.get("name", "")
        value = hp.get("value", "")
        if name.lower() == "authorization":
            has_auth = True
            if value != LITELLM_KEY:
                old_val = value[:40] + "..." if len(value) > 40 else value
                hp["value"] = LITELLM_KEY
                changes_log.append(f"  NODE '{node_name}': Auth header '{old_val}' → LiteLLM key")
                changed = True

    if not has_auth:
        param_list.append({"name": "Authorization", "value": LITELLM_KEY})
        changes_log.append(f"  NODE '{node_name}': Added Authorization header for LiteLLM")
        changed = True

    header_params["parameters"] = param_list
    params["headerParameters"] = header_params

    # Also ensure sendHeaders is enabled
    if not params.get("sendHeaders"):
        params["sendHeaders"] = True
        changes_log.append(f"  NODE '{node_name}': Enabled sendHeaders")
        changed = True

    return changed


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
        changes_log.append(f"  NODE '{node_name}': URL '{old_url}' → LiteLLM proxy")
        changed = True

    # 2. CRITICAL: Fix authentication mode (predefinedCredentialType → none)
    if is_groq_url(url) or is_litellm_url(params.get("url", "")):
        if fix_authentication(node, changes_log):
            changed = True
        if ensure_auth_header(node, changes_log):
            changed = True

    # 3. Fix Authorization header (including old Groq keys)
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
                        changes_log.append(f"  NODE '{node_name}': Auth header '{old_val}' → LiteLLM key")
                        changed = True

    # 4. Fix model in jsonBody
    json_body = params.get("jsonBody", "")
    if isinstance(json_body, str):
        for model_name in GROQ_MODEL_PATTERNS:
            if model_name in json_body:
                new_body = json_body.replace(model_name, LITELLM_MODEL)
                params["jsonBody"] = new_body
                json_body = new_body
                changes_log.append(f"  NODE '{node_name}': jsonBody model '{model_name}' → '{LITELLM_MODEL}'")
                changed = True

    # 5. Also check if URL is in an expression (={{ }})
    url_str = params.get("url", "")
    if isinstance(url_str, str) and "groq.com" in url_str:
        new_url = re.sub(r'https?://api\.groq\.com/openai/v1/chat/completions', LITELLM_URL, url_str)
        if new_url != url_str:
            params["url"] = new_url
            changes_log.append(f"  NODE '{node_name}': URL expression fixed → LiteLLM")
            changed = True
            # Also fix auth
            if fix_authentication(node, changes_log):
                changed = True
            if ensure_auth_header(node, changes_log):
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

    new_code = js_code

    # Replace Groq model names with 'smart'
    for model_name in GROQ_MODEL_PATTERNS:
        if model_name in new_code:
            new_code = new_code.replace(model_name, LITELLM_MODEL)
            changes_log.append(f"  NODE '{node_name}' (Code): Model '{model_name}' → '{LITELLM_MODEL}'")
            changed = True

    # Replace Groq URLs
    for pattern in GROQ_URL_PATTERNS:
        if pattern in new_code:
            new_code = re.sub(
                r'https?://api\.groq\.com/openai/v1/chat/completions',
                LITELLM_URL,
                new_code
            )
            changes_log.append(f"  NODE '{node_name}' (Code): Groq URL → LiteLLM proxy URL")
            changed = True

    # Replace Bearer gsk_ API keys
    if "Bearer gsk_" in new_code:
        new_code = re.sub(r'Bearer gsk_[A-Za-z0-9]+', LITELLM_KEY, new_code)
        changes_log.append(f"  NODE '{node_name}' (Code): Groq API key → LiteLLM key")
        changed = True

    # Replace $env.GROQ_API_KEY references
    if "$env.GROQ_API_KEY" in new_code:
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

    # Check assignments
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

    # Check direct params
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
                    # Also catch bare groq.com URLs (not just chat/completions)
                    for groq_url in GROQ_URL_PATTERNS:
                        if groq_url in new_val:
                            new_val = re.sub(
                                r'https?://api\.groq\.com[^\s"\']*',
                                LITELLM_URL,
                                new_val
                            )
                            changes_log.append(f"  NODE '{node_name}' (deep): {path}.{key} residual Groq URL → LiteLLM")
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


def deploy_workflow(base_url, cookie, workflow_json, workflow_id):
    """3-step deploy: PATCH → GET versionId → POST activate."""
    url = f"{base_url}/rest/workflows/{workflow_id}"

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
    activate_url = f"{base_url}/rest/workflows/{workflow_id}/activate"
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


def smoke_test(base_url, webhook_path, question, sector):
    """Send a quick test query to verify the pipeline works."""
    url = f"{base_url}{webhook_path}"
    data = {
        "query": question,
        "chatInput": question,
        "user_context": {"tenant_id": sector, "groups": ["admin"]},
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
            answer = resp.get("response", resp.get("output", ""))
            sources = resp.get("sources", [])

            unable = any(x in answer.lower() for x in ["unable to generate", "impossible de", "error"])

            print(f"  Status: OK | Latency: {elapsed:.1f}s")
            print(f"  Answer length: {len(answer)} chars | Sources: {len(sources) if isinstance(sources, list) else 'N/A'}")
            print(f"  Preview: {answer[:300]}...")
            return not unable
        except json.JSONDecodeError:
            print(f"  JSON parse error: {body[:200]}")
            return False
    else:
        print(f"  HTTP {status}: {body[:200]}")
        return False


def process_pipeline(pipeline_name, config):
    """Process a single pipeline: fetch, patch, save, deploy, test."""
    workflow_id = config["workflow_id"]
    output_path = config["output_path"]

    print(f"\n{'='*72}")
    print(f"PIPELINE: {pipeline_name.upper()} ({workflow_id})")
    print(f"{'='*72}")

    # --- PHASE 1: Login + GET workflow from S1 ---
    print(f"\n[{pipeline_name.upper()} PHASE 1] Fetching workflow from S1...")
    s1_url = SPACES["S1"]

    cookie = login(s1_url)
    if not cookie:
        print("FATAL: Cannot login to S1")
        return False

    workflow = get_workflow(s1_url, cookie, workflow_id)
    if not workflow:
        print("FATAL: Cannot GET workflow")
        return False

    print(f"  Workflow name: {workflow['name']}")
    print(f"  Node count: {len(workflow['nodes'])}")
    print(f"  Updated at: {workflow.get('updatedAt', '?')}")

    # --- PHASE 2: Analyze + Patch all Groq references ---
    print(f"\n[{pipeline_name.upper()} PHASE 2] Scanning {len(workflow['nodes'])} nodes...")

    changes = []
    nodes_changed = set()
    groq_http_nodes = []
    groq_code_nodes = []
    already_litellm_nodes = []
    predefined_auth_nodes = []

    # First pass: inventory
    for node in workflow["nodes"]:
        node_type = node.get("type", "")
        node_name = node.get("name", "unnamed")
        params = node.get("parameters", {})

        url = params.get("url", "")
        if is_groq_url(url):
            groq_http_nodes.append(node_name)
        elif is_litellm_url(url):
            already_litellm_nodes.append(node_name)

        auth = params.get("authentication", "")
        if auth == "predefinedCredentialType":
            predefined_auth_nodes.append(node_name)

        js_code = params.get("jsCode", "")
        if js_code and any(m in js_code for m in GROQ_MODEL_PATTERNS + GROQ_URL_PATTERNS):
            groq_code_nodes.append(node_name)

    print(f"\n  INVENTORY:")
    print(f"  Groq HTTP nodes: {groq_http_nodes or 'none'}")
    print(f"  Already LiteLLM: {already_litellm_nodes or 'none'}")
    print(f"  predefinedCredentialType nodes: {predefined_auth_nodes or 'none'}")
    print(f"  Code nodes with Groq refs: {groq_code_nodes or 'none'}")

    # Second pass: patch
    for node in workflow["nodes"]:
        node_type = node.get("type", "")
        node_name = node.get("name", "unnamed")

        prev_len = len(changes)

        if "httpRequest" in node_type:
            patch_http_request_node(node, changes)
        elif "code" in node_type.lower():
            patch_code_node(node, changes)
        elif "set" in node_type.lower() or "assign" in node_type.lower():
            patch_set_node(node, changes)

        # Deep scan every node
        deep_scan_node(node, changes)

        if len(changes) > prev_len:
            nodes_changed.add(node_name)

    # Third pass: verification — ensure ALL HTTP nodes targeting LiteLLM have correct auth
    print(f"\n  --- Verification pass ---")
    for node in workflow["nodes"]:
        node_type = node.get("type", "")
        if "httpRequest" not in node_type:
            continue

        node_name = node.get("name", "unnamed")
        params = node.get("parameters", {})
        url = params.get("url", "")

        if not is_litellm_url(url):
            continue

        prev_len = len(changes)

        # Ensure auth mode is 'none' (not predefinedCredentialType)
        fix_authentication(node, changes)
        ensure_auth_header(node, changes)

        # Ensure model in jsonBody is correct
        json_body = params.get("jsonBody", "")
        if isinstance(json_body, str):
            for model_name in GROQ_MODEL_PATTERNS:
                if model_name in json_body:
                    params["jsonBody"] = json_body.replace(model_name, LITELLM_MODEL)
                    json_body = params["jsonBody"]
                    changes.append(f"  NODE '{node_name}' (verify): jsonBody model '{model_name}' → '{LITELLM_MODEL}'")

        if len(changes) > prev_len:
            nodes_changed.add(node_name)

    # Deduplicate changes (deep scan may repeat)
    seen = set()
    unique_changes = []
    for c in changes:
        if c not in seen:
            seen.add(c)
            unique_changes.append(c)
    changes = unique_changes

    print(f"\n  CHANGES SUMMARY:")
    print(f"  Total changes: {len(changes)}")
    print(f"  Nodes modified: {sorted(nodes_changed)}")

    if changes:
        print(f"\n  CHANGE LOG:")
        for c in changes:
            print(c)
    else:
        print(f"\n  No Groq references found — workflow may already be on LiteLLM.")

    # --- PHASE 3: Update name + save ---
    old_name = workflow["name"]
    new_name = old_name
    if "LiteLLM" not in new_name:
        new_name = new_name.rstrip() + " (LiteLLM)"
    workflow["name"] = new_name
    print(f"\n  Workflow name: '{old_name}' → '{new_name}'")

    print(f"\n[{pipeline_name.upper()} PHASE 3] Saving to {output_path}...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    file_size = os.path.getsize(output_path)
    print(f"  Saved: {file_size:,} bytes")

    # --- PHASE 4: Deploy to S1, S3, S5 ---
    print(f"\n[{pipeline_name.upper()} PHASE 4] Deploying to S1, S3, S5...")
    deploy_results = {}

    for space_name, base_url in SPACES.items():
        print(f"\n  --- {space_name} ({base_url}) ---")

        space_cookie = login(base_url)
        if not space_cookie:
            deploy_results[space_name] = "LOGIN_FAILED"
            continue

        success = deploy_workflow(base_url, space_cookie, workflow, workflow_id)
        deploy_results[space_name] = "OK" if success else "FAILED"

    print(f"\n  DEPLOY RESULTS:")
    for space, result in deploy_results.items():
        status_str = "PASS" if result == "OK" else "FAIL"
        print(f"    {space}: {status_str} ({result})")

    # --- PHASE 5: Smoke test ---
    print(f"\n[{pipeline_name.upper()} PHASE 5] Smoke test (waiting 5s)...")
    time.sleep(5)

    test_url = None
    for space, result in deploy_results.items():
        if result == "OK":
            test_url = SPACES[space]
            break

    if test_url:
        print(f"\n  Testing on {test_url}...")
        print(f"  Q: {config['smoke_question']}")
        smoke_test(test_url, config["webhook_path"], config["smoke_question"], config["smoke_sector"])
    else:
        print(f"  SKIP: No space available for testing")

    return {
        "pipeline": pipeline_name,
        "changes": len(changes),
        "nodes_changed": sorted(nodes_changed),
        "deploy": deploy_results,
        "saved_to": output_path,
    }


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 72)
    print("DEPLOY Graph RAG + Orchestrator — Groq → LiteLLM Migration")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 72)

    # ----------------------------------------------------------
    # PHASE 0: Check LiteLLM proxy
    # ----------------------------------------------------------
    print("\n[PHASE 0] Checking LiteLLM proxy (S7)...")
    s7_url = "https://lbjlincoln-nomos-rag-engine-7.hf.space/health"
    status, body, _ = http_request(s7_url, method="GET", timeout=15)
    if status == 200:
        print(f"  S7 LiteLLM: UP ({body[:100]})")
    else:
        print(f"  S7 LiteLLM: status={status} — {body[:200]}")
        print("  WARNING: LiteLLM proxy may be down. Continuing anyway...")

    # Test model availability
    models_url = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/models"
    status, body, _ = http_request(models_url, method="GET",
                                    headers={"Authorization": LITELLM_KEY}, timeout=15)
    if status == 200:
        try:
            models_data = json.loads(body)
            model_names = [m.get("id", "?") for m in models_data.get("data", [])]
            print(f"  Available models: {model_names[:10]}")
            if LITELLM_MODEL in model_names:
                print(f"  Model '{LITELLM_MODEL}' available — GOOD")
        except:
            print(f"  Models response: {body[:200]}")
    else:
        print(f"  Models endpoint: {status} — {body[:200]}")

    # ----------------------------------------------------------
    # Process each pipeline
    # ----------------------------------------------------------
    all_results = []

    for pipeline_name, config in PIPELINES.items():
        result = process_pipeline(pipeline_name, config)
        all_results.append(result)

    # ----------------------------------------------------------
    # FINAL SUMMARY
    # ----------------------------------------------------------
    print(f"\n{'='*72}")
    print("MIGRATION SUMMARY — Graph RAG + Orchestrator (Groq → LiteLLM)")
    print(f"{'='*72}")

    for result in all_results:
        if result:
            print(f"\n  {result['pipeline'].upper()}:")
            print(f"    Changes: {result['changes']} across nodes {result['nodes_changed']}")
            print(f"    Saved to: {result['saved_to']}")
            print(f"    Deploy: {result['deploy']}")

    print(f"\n  LiteLLM URL: {LITELLM_URL}")
    print(f"  LiteLLM model: {LITELLM_MODEL}")
    print(f"  CRITICAL FIX: authentication changed from predefinedCredentialType → none")
    print(f"{'='*72}")
