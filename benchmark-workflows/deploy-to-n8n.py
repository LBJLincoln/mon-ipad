#!/usr/bin/env python3
"""
Push benchmark workflows to n8n cloud and run Supabase migration.
Then ingest the most complex datasets first.
"""
import json
import os
import sys
import copy
import time
from urllib import request, error
from datetime import datetime

N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"

BASE_DIR = '/home/user/mon-ipad/benchmark-workflows'

WORKFLOW_FILES = [
    "WF-Benchmark-Dataset-Ingestion.json",
    "WF-Benchmark-RAG-Tester.json",
    "WF-Benchmark-Orchestrator-Tester.json",
    "WF-Benchmark-Monitoring.json",
]


def api_request(method, endpoint, data=None, timeout=60):
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
        error_body = e.read().decode('utf-8') if e.fp else ''
        return {"status": e.code, "error": str(e), "body": error_body}
    except Exception as e:
        return {"status": 0, "error": str(e)}


def prepare_workflow(wf_data):
    """Strip workflow JSON to only n8n-accepted fields."""
    ALLOWED_TOP_LEVEL = {"name", "nodes", "connections", "settings"}
    STRIP_SETTINGS = {"timeSavedMode", "saveExecutionProgress", "saveManualExecutions"}

    prepared = {}
    for key in ALLOWED_TOP_LEVEL:
        if key in wf_data:
            prepared[key] = copy.deepcopy(wf_data[key])

    if "settings" in prepared:
        for field in STRIP_SETTINGS:
            prepared["settings"].pop(field, None)

    if "name" not in prepared:
        prepared["name"] = "Unnamed Workflow"
    if "nodes" not in prepared:
        prepared["nodes"] = []
    if "connections" not in prepared:
        prepared["connections"] = {}

    for node in prepared.get("nodes", []):
        if "id" not in node:
            import uuid
            node["id"] = str(uuid.uuid4())
        if "typeVersion" not in node:
            node["typeVersion"] = 1
        if "position" not in node:
            node["position"] = [0, 0]
        for key in list(node.keys()):
            if key.startswith('_'):
                del node[key]

    return prepared


def push_workflows():
    """Push all 4 benchmark workflows to n8n cloud."""
    results = {}

    # First check if any already exist
    resp = api_request("GET", "/workflows?limit=100")
    existing = {}
    if resp.get("data"):
        for wf in resp["data"].get("data", []):
            existing[wf["name"]] = wf["id"]

    for filename in WORKFLOW_FILES:
        filepath = os.path.join(BASE_DIR, filename)
        print(f"\n{'='*60}")
        print(f"Processing: {filename}")

        with open(filepath, 'r') as f:
            wf_data = json.load(f)

        wf_name = wf_data.get("name", filename)
        prepared = prepare_workflow(wf_data)

        # Check if workflow already exists
        if wf_name in existing:
            wf_id = existing[wf_name]
            print(f"  Updating existing workflow: {wf_id}")
            resp = api_request("PUT", f"/workflows/{wf_id}", prepared)
        else:
            print(f"  Creating new workflow...")
            resp = api_request("POST", "/workflows", prepared)

        if resp.get("data"):
            wf_id = resp["data"].get("id", "?")
            print(f"  SUCCESS: ID={wf_id}, Name={resp['data'].get('name', '?')}")
            results[filename] = {"id": wf_id, "status": "ok", "name": wf_name}

            # Activate the workflow
            activate_resp = api_request("PATCH", f"/workflows/{wf_id}", {"active": True})
            if activate_resp.get("data", {}).get("active"):
                print(f"  ACTIVATED: {wf_name}")
            else:
                print(f"  Note: Could not activate (webhooks may need credentials)")
        else:
            print(f"  FAILED: {resp.get('error', resp.get('body', 'unknown error'))}")
            results[filename] = {"status": "error", "error": str(resp)}

    return results


def check_supabase():
    """Check Supabase connectivity via n8n variables or direct."""
    print("\n" + "="*60)
    print("Checking Supabase connectivity...")

    # Try to get n8n credentials info
    resp = api_request("GET", "/credentials?limit=50")
    if resp.get("data"):
        creds = resp["data"].get("data", [])
        pg_creds = [c for c in creds if 'postgres' in c.get("type", "").lower() or 'supabase' in c.get("name", "").lower()]
        print(f"  Found {len(pg_creds)} Postgres/Supabase credentials:")
        for c in pg_creds:
            print(f"    - {c['name']} (ID: {c['id']}, Type: {c['type']})")
        return pg_creds
    else:
        print(f"  Could not list credentials: {resp.get('error', 'unknown')}")
        return []


def list_pushed_workflows(results):
    """Print summary of all pushed workflows."""
    print("\n" + "="*60)
    print("BENCHMARK WORKFLOWS SUMMARY")
    print("="*60)
    for filename, info in results.items():
        status = "OK" if info.get("status") == "ok" else "FAILED"
        print(f"  [{status}] {info.get('name', filename)}")
        if info.get("id"):
            print(f"       ID: {info['id']}")
            print(f"       URL: {N8N_HOST}/workflow/{info['id']}")


if __name__ == "__main__":
    print("=" * 60)
    print("RAG BENCHMARK — n8n Deployment")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    # 1. Push workflows
    results = push_workflows()
    list_pushed_workflows(results)

    # 2. Check Supabase
    pg_creds = check_supabase()

    # 3. Summary
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("  1. Run supabase-migration.sql against your Supabase instance")
    print("  2. Configure credentials in n8n for the benchmark workflows")
    print("  3. Start dataset ingestion via webhook calls")
    print("="*60)

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "workflows": results,
        "postgres_credentials": [{"id": c["id"], "name": c["name"]} for c in pg_creds] if pg_creds else []
    }
    with open(os.path.join(BASE_DIR, "deployment-results.json"), "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {BASE_DIR}/deployment-results.json")
