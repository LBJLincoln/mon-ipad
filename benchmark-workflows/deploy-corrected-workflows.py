#!/usr/bin/env python3
"""
Deploy corrected Graph RAG and Orchestrator workflows to n8n cloud.

Fixes:
- Graph RAG: responseMode=responseNode + Respond to Webhook node
- Orchestrator: Return: Error Response node on error path + deduplicated code
"""
import json
import os
import sys
import time
import copy
from urllib import request, error

# ============================================================
# Configuration
# ============================================================
N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"

# Workflow IDs on n8n cloud
WORKFLOWS = {
    "graph_rag": {
        "id": "95x2BBAbJlLWZtWEJn6rb",
        "file": "/home/user/mon-ipad/TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED (1).json",
        "name": "Graph RAG V3.3"
    },
    "orchestrator": {
        "id": "FZxkpldDbgV8AD_cg7IWG",
        "file": "/home/user/mon-ipad/V10.1 orchestrator copy (5).json",
        "name": "Orchestrator V10.1"
    }
}

# Only these settings properties are accepted by n8n API
ALLOWED_SETTINGS = {"executionOrder", "callerPolicy", "saveManualExecutions", "saveExecutionProgress"}


def api_request(method, endpoint, data=None, timeout=60):
    """Make a request to the n8n REST API."""
    url = f"{N8N_HOST}/api/v1{endpoint}"
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode('utf-8') if data else None
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            response_data = resp.read().decode('utf-8')
            return {"status": resp.status, "data": json.loads(response_data) if response_data else None}
    except error.HTTPError as e:
        error_body = ''
        try:
            error_body = e.read().decode('utf-8')
        except Exception:
            pass
        return {"status": e.code, "error": str(e), "body": error_body}
    except Exception as e:
        return {"status": 0, "error": str(e)}


def prepare_workflow(wf_data):
    """Strip workflow JSON to only n8n-accepted fields with clean settings."""
    prepared = {
        "name": wf_data.get("name", "Unnamed Workflow"),
        "nodes": copy.deepcopy(wf_data.get("nodes", [])),
        "connections": copy.deepcopy(wf_data.get("connections", {})),
    }

    # Clean settings - only keep allowed properties
    if "settings" in wf_data:
        clean_settings = {}
        for key, value in wf_data["settings"].items():
            if key in ALLOWED_SETTINGS:
                clean_settings[key] = value
        if clean_settings:
            prepared["settings"] = clean_settings

    # Clean nodes - remove private/internal fields
    for node in prepared["nodes"]:
        if "id" not in node:
            import uuid
            node["id"] = str(uuid.uuid4())
        if "typeVersion" not in node:
            node["typeVersion"] = 1
        if "position" not in node:
            node["position"] = [0, 0]
        # Remove underscore-prefixed internal fields
        for key in list(node.keys()):
            if key.startswith('_'):
                del node[key]

    return prepared


def deploy_workflow(wf_key, wf_config):
    """Deploy a single workflow to n8n cloud."""
    wf_id = wf_config["id"]
    filepath = wf_config["file"]
    name = wf_config["name"]

    print(f"\n{'='*60}")
    print(f"Deploying: {name}")
    print(f"  File: {os.path.basename(filepath)}")
    print(f"  Target ID: {wf_id}")
    print(f"{'='*60}")

    # Load workflow JSON
    if not os.path.exists(filepath):
        print(f"  ERROR: File not found: {filepath}")
        return False

    with open(filepath, 'r') as f:
        wf_data = json.load(f)

    # Prepare clean payload
    prepared = prepare_workflow(wf_data)

    print(f"  Nodes: {len(prepared['nodes'])}")
    print(f"  Connections: {len(prepared['connections'])} groups")
    print(f"  Settings: {prepared.get('settings', {})}")

    # Step 1: Deactivate workflow first (required for update)
    print(f"\n  Step 1: Deactivating workflow...")
    deactivate = api_request("PATCH", f"/workflows/{wf_id}", {"active": False})
    if deactivate.get("status") == 200:
        print(f"    Deactivated OK")
    else:
        print(f"    Deactivate response: {deactivate.get('status')} (may already be inactive)")

    # Step 2: PUT the updated workflow
    print(f"\n  Step 2: Updating workflow via PUT...")
    result = api_request("PUT", f"/workflows/{wf_id}", prepared)

    if result.get("status") == 200 and result.get("data"):
        print(f"    UPDATE SUCCESS")
        updated_nodes = len(result["data"].get("nodes", []))
        print(f"    Nodes in response: {updated_nodes}")
    else:
        print(f"    UPDATE FAILED: HTTP {result.get('status')}")
        print(f"    Error: {result.get('body', result.get('error', 'unknown'))[:500]}")
        return False

    # Step 3: Reactivate workflow
    print(f"\n  Step 3: Activating workflow...")
    activate = api_request("PATCH", f"/workflows/{wf_id}", {"active": True})
    if activate.get("data", {}).get("active"):
        print(f"    ACTIVATED OK")
    else:
        print(f"    Activation response: {activate.get('status')}")
        print(f"    Detail: {activate.get('body', activate.get('error', ''))[:200]}")
        # Not a fatal error - workflow is updated even if not activated

    return True


def verify_deployment(wf_key, wf_config):
    """Verify a workflow was deployed correctly."""
    wf_id = wf_config["id"]
    name = wf_config["name"]

    print(f"\n  Verifying {name}...")
    resp = api_request("GET", f"/workflows/{wf_id}")
    if resp.get("data"):
        data = resp["data"]
        print(f"    Name: {data.get('name')}")
        print(f"    Active: {data.get('active')}")
        print(f"    Nodes: {len(data.get('nodes', []))}")
        print(f"    Updated: {data.get('updatedAt', 'unknown')}")

        # Check for key nodes
        node_names = [n.get("name") for n in data.get("nodes", [])]
        if wf_key == "graph_rag":
            has_respond = "Respond to Webhook" in node_names
            print(f"    Has 'Respond to Webhook' node: {has_respond}")
            webhook_nodes = [n for n in data.get("nodes", []) if n.get("type") == "n8n-nodes-base.webhook"]
            for wh in webhook_nodes:
                print(f"    Webhook responseMode: {wh.get('parameters', {}).get('responseMode', 'NOT SET')}")
        elif wf_key == "orchestrator":
            has_error_resp = "Return: Error Response" in node_names
            print(f"    Has 'Return: Error Response' node: {has_error_resp}")
            respond_nodes = [n.get("name") for n in data.get("nodes", []) if n.get("type") == "n8n-nodes-base.respondToWebhook"]
            print(f"    respondToWebhook nodes ({len(respond_nodes)}): {respond_nodes}")

        return True
    else:
        print(f"    VERIFY FAILED: {resp.get('error', 'unknown')}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("N8N WORKFLOW DEPLOYMENT - CORRECTED WORKFLOWS")
    print(f"Host: {N8N_HOST}")
    print("=" * 60)

    # Test API connectivity
    print("\nTesting API connectivity...")
    test = api_request("GET", "/workflows?limit=1")
    if test.get("data"):
        print("  API connection OK")
    else:
        print(f"  API connection FAILED: {test}")
        sys.exit(1)

    # Deploy each workflow
    results = {}
    for wf_key, wf_config in WORKFLOWS.items():
        success = deploy_workflow(wf_key, wf_config)
        results[wf_key] = success

    # Verify deployments
    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}")
    for wf_key, wf_config in WORKFLOWS.items():
        if results.get(wf_key):
            verify_deployment(wf_key, wf_config)

    # Summary
    print(f"\n{'='*60}")
    print("DEPLOYMENT SUMMARY")
    print(f"{'='*60}")
    for wf_key, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {WORKFLOWS[wf_key]['name']}: {status}")

    all_ok = all(results.values())
    if all_ok:
        print("\nAll workflows deployed successfully!")
    else:
        print("\nSome deployments FAILED - check output above")
        sys.exit(1)
