#!/usr/bin/env python3
"""
Deploy Error Trigger Handler workflow to all n8n Spaces (S1, S3, S5, S9).

This script:
1. Creates the Error Trigger Handler workflow on each Space
2. Activates it
3. Updates all existing pipelines to set their settings.errorWorkflow
   to point to the Error Trigger Handler's workflow ID

Cookie auth pattern (API key returns 401 on HF Spaces n8n).
IPv4 monkey-patch for GCP VM compatibility.
"""

import json
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error

# === Force IPv4 (GCP VM has broken IPv6) ===
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    responses = _original_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET] or responses
socket.getaddrinfo = _ipv4_only_getaddrinfo

# === Config ===
N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

WORKFLOW_JSON_PATH = "/home/termius/mon-ipad/n8n/live/error-trigger-handler.json"

SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S2": "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S4": "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

# Existing pipeline workflows to update with errorWorkflow setting
# Map: workflow_id -> {name, spaces where it runs}
PIPELINE_WORKFLOWS = {
    "TmgyRP20N4JFd9CB": {
        "name": "Standard RAG V3.5",
        "spaces": ["S1", "S2", "S3", "S4", "S5", "S9"],
    },
    "6257AfT1l4FMC6lY": {
        "name": "Graph RAG V3.3",
        "spaces": ["S1"],
    },
    "cjhEhVs0KV1ExHqX": {
        "name": "Quantitative V3.1",
        "spaces": ["S9"],
    },
    "qOSaFFrqO8Jb4VGb": {
        "name": "Orchestrator V11",
        "spaces": ["S1"],
    },
}

# SSL context (HF spaces sometimes have cert issues)
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
        # Parse Set-Cookie header to extract session cookie
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
# Workflow Operations
# ========================================

def create_workflow(base_url, cookie, workflow_json):
    """Create a new workflow via POST /rest/workflows. Returns the new workflow ID."""
    url = f"{base_url}/rest/workflows"

    payload = {
        "name": workflow_json["name"],
        "nodes": workflow_json["nodes"],
        "connections": workflow_json["connections"],
        "settings": workflow_json.get("settings", {}),
        "active": False,  # Create inactive, activate after
    }

    status, body, _ = http_request(url, method="POST", data=payload, cookie=cookie)

    if status in (200, 201):
        resp = json.loads(body)
        inner = resp.get("data", resp)
        wf_id = inner.get("id")
        print(f"  CREATE OK -> workflow ID: {wf_id}")
        return wf_id
    else:
        print(f"  CREATE FAILED ({status}): {body[:300]}")
        return None


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


def update_workflow(base_url, cookie, workflow_id, payload):
    """Update an existing workflow via PATCH."""
    url = f"{base_url}/rest/workflows/{workflow_id}"
    status, body, _ = http_request(url, method="PATCH", data=payload, cookie=cookie)

    if status == 200:
        print(f"  PATCH OK for {workflow_id}")
        return True
    else:
        print(f"  PATCH FAILED ({status}) for {workflow_id}: {body[:200]}")
        return False


def activate_workflow(base_url, cookie, workflow_id):
    """Activate a workflow. Gets versionId first, then POSTs activate."""
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


def get_workflow_settings(base_url, cookie, workflow_id):
    """GET a workflow and return its current settings dict."""
    url = f"{base_url}/rest/workflows/{workflow_id}"
    status, body, _ = http_request(url, method="GET", cookie=cookie)

    if status == 200:
        resp = json.loads(body)
        inner = resp.get("data", resp)
        return inner.get("settings", {})
    return None


def set_error_workflow(base_url, cookie, pipeline_wf_id, error_wf_id):
    """Update a pipeline workflow's settings.errorWorkflow to point to the error handler."""
    # First get current settings
    current_settings = get_workflow_settings(base_url, cookie, pipeline_wf_id)
    if current_settings is None:
        print(f"  Could not GET settings for {pipeline_wf_id}")
        return False

    # Merge errorWorkflow into settings
    current_settings["errorWorkflow"] = error_wf_id

    payload = {"settings": current_settings}
    return update_workflow(base_url, cookie, pipeline_wf_id, payload)


# ========================================
# Main
# ========================================

def main():
    print("=" * 70)
    print("DEPLOY Error Trigger Handler to All Spaces")
    print("=" * 70)

    # Load workflow JSON
    try:
        with open(WORKFLOW_JSON_PATH, "r") as f:
            workflow_json = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Workflow JSON not found at {WORKFLOW_JSON_PATH}")
        sys.exit(1)

    wf_name = workflow_json["name"]
    print(f"\nWorkflow: {wf_name}")
    print(f"Nodes: {len(workflow_json['nodes'])}")
    print(f"  1. Error Trigger (catches failures from other workflows)")
    print(f"  2. Extract Error Details (Code node)")
    print(f"  3. Log to Supabase (HTTP POST to pipeline_errors table)")
    print(f"  4. Log Result (summary)")

    # ---- Phase 1: Deploy Error Trigger Handler to each Space ----
    print(f"\n{'=' * 70}")
    print("PHASE 1: Deploy Error Trigger Handler")
    print(f"{'=' * 70}")

    # Track the error handler workflow ID per space
    error_wf_ids = {}  # space_name -> workflow_id
    deploy_results = {}

    for space_name, base_url in SPACES.items():
        print(f"\n--- {space_name} ({base_url}) ---")

        cookie = login(base_url)
        if not cookie:
            deploy_results[space_name] = "LOGIN_FAILED"
            continue

        # Check if already deployed
        existing_id = check_existing_workflow(base_url, cookie, wf_name)
        if existing_id:
            print(f"  Already exists with ID: {existing_id}")
            # Update it instead of creating a new one
            payload = {
                "name": workflow_json["name"],
                "nodes": workflow_json["nodes"],
                "connections": workflow_json["connections"],
                "settings": workflow_json.get("settings", {}),
            }
            if update_workflow(base_url, cookie, existing_id, payload):
                error_wf_ids[space_name] = existing_id
                # Make sure it's active
                activate_workflow(base_url, cookie, existing_id)
                deploy_results[space_name] = "UPDATED"
            else:
                deploy_results[space_name] = "UPDATE_FAILED"
            continue

        # Create new workflow
        wf_id = create_workflow(base_url, cookie, workflow_json)
        if not wf_id:
            deploy_results[space_name] = "CREATE_FAILED"
            continue

        error_wf_ids[space_name] = wf_id

        # Now update the workflow's own settings.errorWorkflow to itself
        # (so errors in the error handler don't cause infinite loops — n8n handles this)
        # Actually, we should NOT point errorWorkflow to itself. Leave it unset for the handler.

        # Activate
        if activate_workflow(base_url, cookie, wf_id):
            deploy_results[space_name] = "OK"
        else:
            deploy_results[space_name] = "CREATED_NOT_ACTIVATED"

    print(f"\n{'=' * 70}")
    print("PHASE 1 RESULTS — Error Trigger Handler Deployment:")
    for space, result in deploy_results.items():
        icon = "PASS" if result in ("OK", "UPDATED") else "FAIL"
        wf_id = error_wf_ids.get(space, "N/A")
        print(f"  {space}: {icon} ({result}) -> ID: {wf_id}")

    # ---- Phase 2: Update existing pipelines to use errorWorkflow ----
    print(f"\n{'=' * 70}")
    print("PHASE 2: Update Pipeline Workflows with errorWorkflow")
    print(f"{'=' * 70}")

    update_results = {}

    for pipeline_wf_id, info in PIPELINE_WORKFLOWS.items():
        pipeline_name = info["name"]
        pipeline_spaces = info["spaces"]

        for space_name in pipeline_spaces:
            if space_name not in error_wf_ids:
                key = f"{pipeline_name}@{space_name}"
                update_results[key] = "SKIPPED (no error handler ID)"
                print(f"\n  {key}: SKIPPED (error handler not deployed on {space_name})")
                continue

            base_url = SPACES.get(space_name)
            if not base_url:
                continue

            error_handler_id = error_wf_ids[space_name]
            key = f"{pipeline_name}@{space_name}"
            print(f"\n--- {key} ---")
            print(f"  Pipeline WF: {pipeline_wf_id}")
            print(f"  Error Handler WF: {error_handler_id}")

            # Login again (cookies may have expired)
            cookie = login(base_url)
            if not cookie:
                update_results[key] = "LOGIN_FAILED"
                continue

            # First check if the pipeline workflow exists on this space
            url = f"{base_url}/rest/workflows/{pipeline_wf_id}"
            status, body, _ = http_request(url, method="GET", cookie=cookie)
            if status != 200:
                update_results[key] = f"WF_NOT_FOUND ({status})"
                print(f"  Workflow {pipeline_wf_id} not found on {space_name} ({status})")
                continue

            # Set errorWorkflow
            if set_error_workflow(base_url, cookie, pipeline_wf_id, error_handler_id):
                update_results[key] = "OK"
            else:
                update_results[key] = "PATCH_FAILED"

    print(f"\n{'=' * 70}")
    print("PHASE 2 RESULTS — Pipeline errorWorkflow Updates:")
    for key, result in update_results.items():
        icon = "PASS" if result == "OK" else "WARN" if "SKIP" in result else "FAIL"
        print(f"  {icon} {key}: {result}")

    # ---- Summary ----
    print(f"\n{'=' * 70}")
    print("FINAL SUMMARY")
    print(f"{'=' * 70}")

    total_deployed = sum(1 for r in deploy_results.values() if r in ("OK", "UPDATED"))
    total_updated = sum(1 for r in update_results.values() if r == "OK")
    total_pipelines = sum(len(info["spaces"]) for info in PIPELINE_WORKFLOWS.values())

    print(f"  Error Handler deployed: {total_deployed}/{len(SPACES)} spaces")
    print(f"  Pipelines updated:      {total_updated}/{total_pipelines} pipeline-space combos")
    print(f"  Error Handler IDs:      {json.dumps(error_wf_ids, indent=2)}")
    print()
    print("  When a pipeline fails, the Error Trigger Handler will:")
    print("  1. Catch the error via n8n Error Trigger node")
    print("  2. Extract: workflow name, failing node, error message, execution ID")
    print("  3. POST to Supabase `pipeline_errors` table")
    print()
    print("  Query errors: SELECT * FROM pipeline_errors ORDER BY timestamp DESC LIMIT 20;")
    print(f"{'=' * 70}")

    # Save deployment state for reference
    state = {
        "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "error_handler_ids": error_wf_ids,
        "deploy_results": deploy_results,
        "update_results": update_results,
    }
    state_path = "/home/termius/mon-ipad/n8n/live/error-trigger-deploy-state.json"
    try:
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
        print(f"\nDeploy state saved to: {state_path}")
    except Exception as e:
        print(f"\nCould not save state: {e}")


if __name__ == "__main__":
    main()
