#!/usr/bin/env python3
"""
N8N Tester Agent - Multi-RAG Orchestrator SOTA 2026
Tests patched workflows by importing them into n8n cloud via API.
"""
import json
import os
import sys
import time
from datetime import datetime
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"

BASE_DIR = '/home/user/mon-ipad'
MODIFIED_DIR = os.path.join(BASE_DIR, 'modified-workflows')

# Mapping of workflow files to their existing n8n IDs (for update)
# These are the TEST - SOTA 2026 workflows found on the instance
WORKFLOW_MAP = {
    "TEST - SOTA 2026 - Ingestion V3.1.json": {
        "existing_id": "nh1D4Up0wBZhuQbp",
        "label": "Ingestion V3.1"
    },
    "TEST - SOTA 2026 - Enrichissement V3.1.json": {
        "existing_id": "ORa01sX4xI0iRCJ8",
        "label": "Enrichissement V3.1"
    },
    "V10.1 orchestrator copy (5).json": {
        "existing_id": "FZxkpldDbgV8AD_cg7IWG",
        "label": "Orchestrator V10.1"
    },
    "TEST - SOTA 2026 - WF5 Standard RAG V3.4 - CORRECTED.json": {
        "existing_id": "LnTqRX4LZlI009Ks-3Jnp",
        "label": "WF5 Standard RAG V3.4"
    },
    "TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED (1).json": {
        "existing_id": "95x2BBAbJlLWZtWEJn6rb",
        "label": "WF2 Graph RAG V3.3"
    },
    "TEST - SOTA 2026 - Feedback V3.1.json": {
        "existing_id": "iVsj6dq8UpX5Dk7c",
        "label": "Feedback V3.1"
    },
    "TEST - SOTA 2026 - WF4 Quantitative V2.0 (1).json": {
        "existing_id": "LjUz8fxQZ03G9IsU",
        "label": "WF4 Quantitative V2.0"
    }
}


def api_request(method, endpoint, data=None):
    """Make an API request to n8n."""
    url = f"{N8N_HOST}/api/v1{endpoint}"
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    body = json.dumps(data).encode('utf-8') if data else None
    req = request.Request(url, data=body, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=60) as resp:
            response_data = resp.read().decode('utf-8')
            return {
                "status": resp.status,
                "data": json.loads(response_data) if response_data else None
            }
    except error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        return {
            "status": e.code,
            "error": str(e),
            "body": error_body
        }
    except Exception as e:
        return {
            "status": 0,
            "error": str(e)
        }


def prepare_workflow_for_import(wf_data):
    """Prepare workflow JSON for n8n API import.

    The n8n public API (PUT/POST /workflows) only accepts specific top-level fields.
    Any extra field triggers "request/body must NOT have additional properties".
    """
    import copy

    # Only these top-level fields are accepted by n8n public API for PUT/POST
    ALLOWED_TOP_LEVEL = {"name", "nodes", "connections", "settings"}

    # Settings fields NOT accepted by n8n cloud API
    STRIP_SETTINGS = {"timeSavedMode", "saveExecutionProgress", "saveManualExecutions"}

    prepared = {}
    for key in ALLOWED_TOP_LEVEL:
        if key in wf_data:
            prepared[key] = copy.deepcopy(wf_data[key])

    # Strip non-standard settings fields
    if "settings" in prepared:
        for field in STRIP_SETTINGS:
            prepared["settings"].pop(field, None)

    # Ensure required fields
    if "name" not in prepared:
        prepared["name"] = "Unnamed Workflow"
    if "nodes" not in prepared:
        prepared["nodes"] = []
    if "connections" not in prepared:
        prepared["connections"] = {}

    # Clean up nodes - ensure all have required fields
    ALLOWED_NODE_FIELDS = {
        "id", "name", "type", "typeVersion", "position", "parameters",
        "credentials", "disabled", "notes", "notesInFlow",
        "retryOnFail", "maxTries", "waitBetweenTries",
        "alwaysOutputData", "executeOnce", "onError",
        "continueOnFail", "color"
    }

    for node in prepared.get("nodes", []):
        # Ensure required fields
        if "id" not in node:
            import uuid
            node["id"] = str(uuid.uuid4())
        if "typeVersion" not in node:
            node["typeVersion"] = 1
        if "position" not in node:
            node["position"] = [0, 0]

        # Remove non-standard node fields
        for key in list(node.keys()):
            if key.startswith('_'):
                del node[key]

    return prepared


def validate_node_types(wf_data):
    """Check for potentially invalid node types."""
    issues = []
    known_types = {
        "n8n-nodes-base.code",
        "n8n-nodes-base.stickyNote",
        "n8n-nodes-base.httpRequest",
        "n8n-nodes-base.if",
        "n8n-nodes-base.set",
        "n8n-nodes-base.merge",
        "n8n-nodes-base.webhook",
        "n8n-nodes-base.function",
        "n8n-nodes-base.noOp",
        "n8n-nodes-base.respondToWebhook",
        "n8n-nodes-base.splitInBatches",
        "n8n-nodes-base.switch",
        "n8n-nodes-base.aggregate",
        "n8n-nodes-base.executeWorkflow",
        "n8n-nodes-base.redis",
        "n8n-nodes-base.postgres",
        "n8n-nodes-base.crypto",
        "n8n-nodes-base.dateTime",
        "n8n-nodes-base.wait",
        "n8n-nodes-base.filter",
        "n8n-nodes-base.manualTrigger",
        "n8n-nodes-base.scheduleTrigger",
        "@n8n/n8n-nodes-langchain.agent",
        "@n8n/n8n-nodes-langchain.chainLlm",
        "@n8n/n8n-nodes-langchain.lmChatOpenAi",
        "@n8n/n8n-nodes-langchain.memoryBufferWindow",
        "@n8n/n8n-nodes-langchain.outputParserStructured",
        "@n8n/n8n-nodes-langchain.toolWorkflow",
    }

    for node in wf_data.get("nodes", []):
        node_type = node.get("type", "")
        if not node_type:
            issues.append(f"Node '{node.get('name', '?')}' has no type")

    return issues


def test_workflow_import(wf_file, wf_info):
    """Test importing a workflow via n8n API."""
    label = wf_info["label"]
    existing_id = wf_info["existing_id"]

    print(f"\n{'='*60}")
    print(f"Testing: {label}")
    print(f"{'='*60}")

    # Load patched workflow
    wf_path = os.path.join(MODIFIED_DIR, wf_file)
    if not os.path.exists(wf_path):
        print(f"  ERROR: File not found: {wf_path}")
        return {"status": "ERROR", "error": "File not found"}

    with open(wf_path, 'r', encoding='utf-8') as f:
        wf_data = json.load(f)

    node_count = len(wf_data.get("nodes", []))
    conn_count = len(wf_data.get("connections", {}))
    print(f"  Loaded: {node_count} nodes, {conn_count} connections")

    # Validate node types
    type_issues = validate_node_types(wf_data)
    if type_issues:
        print(f"  Node type warnings: {len(type_issues)}")
        for issue in type_issues[:5]:
            print(f"    - {issue}")

    # Prepare for import
    prepared = prepare_workflow_for_import(wf_data)

    # First, try to GET the existing workflow to check it exists
    print(f"  Checking existing workflow {existing_id}...")
    check_resp = api_request("GET", f"/workflows/{existing_id}")

    if check_resp.get("status") == 200:
        print(f"  Existing workflow found: '{check_resp['data'].get('name', '?')}'")

        # Update existing workflow via PUT
        print(f"  Updating workflow via PUT...")
        update_resp = api_request("PUT", f"/workflows/{existing_id}", prepared)

        if update_resp.get("status") == 200:
            updated_wf = update_resp["data"]
            updated_nodes = len(updated_wf.get("nodes", []))
            print(f"  SUCCESS: Updated workflow '{updated_wf.get('name', '?')}' ({updated_nodes} nodes)")

            # Validate the returned workflow matches what we sent
            if updated_nodes != node_count:
                print(f"  WARNING: Node count mismatch: sent {node_count}, got {updated_nodes}")

            return {
                "status": "SUCCESS",
                "method": "PUT",
                "id": existing_id,
                "name": updated_wf.get("name"),
                "nodes": updated_nodes,
                "url": f"{N8N_HOST}/workflow/{existing_id}"
            }
        else:
            error_msg = update_resp.get("body", update_resp.get("error", "Unknown error"))
            print(f"  ERROR on PUT ({update_resp.get('status')}): {error_msg[:500]}")

            # If PUT fails, try creating as new workflow
            print(f"  Falling back to POST (create new)...")
            return create_new_workflow(prepared, label, error_msg)
    else:
        print(f"  Existing workflow not found (status {check_resp.get('status')})")
        print(f"  Creating new workflow via POST...")
        return create_new_workflow(prepared, label)


def create_new_workflow(prepared, label, original_error=None):
    """Create a new workflow via POST."""
    create_resp = api_request("POST", "/workflows", prepared)

    if create_resp.get("status") == 200 or create_resp.get("status") == 201:
        created_wf = create_resp["data"]
        new_id = created_wf.get("id")
        created_nodes = len(created_wf.get("nodes", []))
        print(f"  SUCCESS: Created workflow '{created_wf.get('name', '?')}' (id={new_id}, {created_nodes} nodes)")

        return {
            "status": "SUCCESS",
            "method": "POST",
            "id": new_id,
            "name": created_wf.get("name"),
            "nodes": created_nodes,
            "url": f"{N8N_HOST}/workflow/{new_id}",
            "original_error": original_error
        }
    else:
        error_msg = create_resp.get("body", create_resp.get("error", "Unknown error"))
        print(f"  ERROR on POST ({create_resp.get('status')}): {error_msg[:500]}")

        return {
            "status": "ERROR",
            "error": error_msg[:500],
            "original_error": original_error
        }


def main():
    print("="*60)
    print("N8N TESTER AGENT - Multi-RAG Orchestrator SOTA 2026")
    print(f"Target: {N8N_HOST}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)

    # Test API connectivity
    print("\nTesting API connectivity...")
    health_resp = api_request("GET", "/workflows?limit=1")
    if health_resp.get("status") != 200:
        print(f"ERROR: Cannot connect to n8n API: {health_resp}")
        sys.exit(1)
    print("API connectivity: OK")

    results = []

    for wf_file, wf_info in WORKFLOW_MAP.items():
        result = test_workflow_import(wf_file, wf_info)
        result["file"] = wf_file
        result["label"] = wf_info["label"]
        results.append(result)
        time.sleep(1)  # Rate limiting

    # === SUMMARY ===
    print(f"\n{'='*60}")
    print("TEST RESULTS SUMMARY")
    print(f"{'='*60}")

    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    error_count = sum(1 for r in results if r["status"] == "ERROR")

    for r in results:
        icon = "PASS" if r["status"] == "SUCCESS" else "FAIL"
        method = r.get("method", "N/A")
        nodes = r.get("nodes", "?")
        url = r.get("url", "N/A")
        print(f"  [{icon}] {r['label']}: {method} ({nodes} nodes)")
        if r["status"] == "SUCCESS":
            print(f"         URL: {url}")
        else:
            print(f"         Error: {r.get('error', 'Unknown')[:200]}")

    print(f"\nTotal: {success_count} passed, {error_count} failed out of {len(results)}")

    # Save test report
    report = {
        "generated_at": datetime.now().isoformat(),
        "generated_by": "n8n-tester-agent",
        "target": N8N_HOST,
        "total": len(results),
        "passed": success_count,
        "failed": error_count,
        "results": results
    }

    report_path = os.path.join(MODIFIED_DIR, 'test-results.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved: {report_path}")

    return results


if __name__ == '__main__':
    main()
