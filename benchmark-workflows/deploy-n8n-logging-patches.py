#!/usr/bin/env python3
"""
Deploy GitHub logging patches to n8n workflows.

Adds GitHub Error Logger + Execution Summary Logger nodes directly
to the active n8n workflows via the REST API. Errors/executions
are pushed to GitHub via repository_dispatch events so that
logs/ gets updated in real-time without git conflicts.

Usage:
    python deploy-n8n-logging-patches.py          # patch all workflows
    python deploy-n8n-logging-patches.py --dry-run # preview changes only
"""

import json
import os
import sys
import time
import copy
import urllib.request
import urllib.error

N8N_HOST = os.environ.get("N8N_HOST", "https://amoret.app.n8n.cloud")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A")

# GitHub repo for logging (repository_dispatch target)
GITHUB_REPO = "LBJLincoln/mon-ipad"

WORKFLOW_IDS = {
    "graph_rag": "95x2BBAbJlLWZtWEJn6rb",
    "orchestrator": "FZxkpldDbgV8AD_cg7IWG",
    "standard_rag": "LnTqRX4LZlI009Ks-3Jnp",
    "quantitative_rag": "LjUz8fxQZ03G9IsU",
}


def n8n_api(method, path, data=None, retries=3):
    """Make n8n API request with retry."""
    url = f"{N8N_HOST}{path}"
    for attempt in range(retries):
        try:
            body = json.dumps(data).encode() if data else None
            req = urllib.request.Request(url, data=body, method=method)
            req.add_header("X-N8N-API-KEY", N8N_API_KEY)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"  API ERROR: {e}")
            return None


def download_workflow(wf_id):
    return n8n_api("GET", f"/api/v1/workflows/{wf_id}")


def update_workflow(wf_id, wf_data):
    clean = {k: v for k, v in wf_data.items()
             if k in ("nodes", "connections", "settings", "name")}
    return n8n_api("PUT", f"/api/v1/workflows/{wf_id}", clean)


def activate_workflow(wf_id):
    return n8n_api("PATCH", f"/api/v1/workflows/{wf_id}", {"active": True})


def find_node(wf, name):
    for n in wf.get("nodes", []):
        if n["name"] == name:
            return n
    return None


def find_node_containing(wf, substring):
    return [n for n in wf.get("nodes", []) if substring.lower() in n["name"].lower()]


def has_node(wf, name):
    return find_node(wf, name) is not None


def get_max_position(wf):
    """Get the rightmost node position for placing new nodes."""
    max_x = 0
    for n in wf.get("nodes", []):
        pos = n.get("position", [0, 0])
        if isinstance(pos, list) and len(pos) >= 2:
            max_x = max(max_x, pos[0])
    return max_x


def make_github_logger_node(pipeline_name, position):
    """Create a Code node that formats error data and sends to GitHub via repository_dispatch."""
    return {
        "parameters": {
            "jsCode": f"""// GitHub Error Logger for {pipeline_name}
const errorData = $input.first().json;
const timestamp = new Date().toISOString();
const questionId = errorData.question_id || errorData.trace_id || 'q-' + Date.now();
const errorType = errorData.error_type || errorData.error_code || 'UNKNOWN';
const pipeline = '{pipeline_name}';

const logEntry = {{
  timestamp: timestamp,
  pipeline: pipeline,
  question_id: questionId,
  error_type: errorType,
  error_message: (errorData.error || errorData.message || 'No message').slice(0, 500),
  input: {{
    query: (errorData.query || errorData.original_query || '').slice(0, 300),
    tenant_id: errorData.tenant_id || 'benchmark'
  }},
  partial_response: errorData.partial_response || errorData.response || null,
  n8n_context: {{
    workflow_id: $workflow.id,
    workflow_name: $workflow.name,
    execution_id: $execution.id
  }},
  performance: {{
    latency_ms: errorData.latency_ms || 0,
    http_status: errorData.http_status || null
  }}
}};

return [{{ json: logEntry }}];"""
        },
        "id": f"github-logger-{pipeline_name}",
        "name": f"GitHub Error Logger ({pipeline_name})",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "onError": "continueRegularOutput"
    }


def make_execution_summary_node(pipeline_name, position):
    """Create a Code node that logs every execution (success or failure)."""
    return {
        "parameters": {
            "jsCode": f"""// Execution Summary Logger for {pipeline_name}
const input = $input.first().json;
const timestamp = new Date().toISOString();

const summary = {{
  timestamp: timestamp,
  pipeline: '{pipeline_name}',
  question_id: input.trace_id || input.question_id || 'q-' + Date.now(),
  query: (input.query || input.original_query || '').slice(0, 300),
  success: !!(input.response || input.final_response || input.answer),
  response_length: (input.response || input.final_response || input.answer || '').length,
  confidence: input.confidence || 0,
  latency_ms: input.latency_ms || 0,
  engine: input.engine || input.selected_engine || '{pipeline_name}',
  n8n_context: {{
    workflow_id: $workflow.id,
    execution_id: $execution.id
  }}
}};

return [{{ json: summary }}];"""
        },
        "id": f"exec-summary-{pipeline_name}",
        "name": f"Execution Summary ({pipeline_name})",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "onError": "continueRegularOutput"
    }


# ============================================================
# PATCHES
# ============================================================

def patch_orchestrator(wf, dry_run=False):
    """Add logging nodes to orchestrator workflow."""
    changes = []

    # Check if already patched
    if has_node(wf, "GitHub Error Logger (orchestrator)"):
        print("  Already has GitHub Error Logger - skipping")
        return changes

    max_x = get_max_position(wf)

    # Add error logger node
    error_logger = make_github_logger_node("orchestrator", [max_x + 300, 0])
    wf["nodes"].append(error_logger)
    changes.append("Added GitHub Error Logger node")

    # Add execution summary node
    exec_summary = make_execution_summary_node("orchestrator", [max_x + 300, 200])
    wf["nodes"].append(exec_summary)
    changes.append("Added Execution Summary Logger node")

    # Try to connect error logger to error handler nodes
    error_nodes = find_node_containing(wf, "error")
    if error_nodes:
        for en in error_nodes:
            if "handler" in en["name"].lower() or "payload" in en["name"].lower():
                conn_key = en["name"]
                if conn_key not in wf.get("connections", {}):
                    wf["connections"][conn_key] = {"main": [[]]}
                if not wf["connections"][conn_key]["main"]:
                    wf["connections"][conn_key]["main"] = [[]]
                wf["connections"][conn_key]["main"][0].append({
                    "node": error_logger["name"],
                    "type": "main",
                    "index": 0
                })
                changes.append(f"Connected {conn_key} -> GitHub Error Logger")
                break

    # Connect execution summary to Response Builder
    response_builders = find_node_containing(wf, "response builder")
    if response_builders:
        rb = response_builders[0]
        conn_key = rb["name"]
        if conn_key not in wf.get("connections", {}):
            wf["connections"][conn_key] = {"main": [[]]}
        if not wf["connections"][conn_key]["main"]:
            wf["connections"][conn_key]["main"] = [[]]
        wf["connections"][conn_key]["main"][0].append({
            "node": exec_summary["name"],
            "type": "main",
            "index": 0
        })
        changes.append(f"Connected {conn_key} -> Execution Summary Logger")

    return changes


def patch_graph_rag(wf, dry_run=False):
    """Add entity extraction logging to Graph RAG."""
    changes = []

    if has_node(wf, "GitHub Error Logger (graph)"):
        print("  Already has GitHub Error Logger - skipping")
        return changes

    max_x = get_max_position(wf)

    # Error logger
    error_logger = make_github_logger_node("graph", [max_x + 300, 0])
    wf["nodes"].append(error_logger)
    changes.append("Added GitHub Error Logger node")

    # Entity extraction logger
    entity_logger = {
        "parameters": {
            "jsCode": """// Entity Extraction Logger
const input = $input.first().json;
const entities = input.entities || input.parameters?.entity_names || [];
const skipNeo4j = input.skip_neo4j || false;

const log = {
  timestamp: new Date().toISOString(),
  pipeline: 'graph',
  step: 'entity_extraction',
  query: (input.query_text || input.query || '').slice(0, 300),
  entities_extracted: entities,
  entity_count: entities.length,
  skip_neo4j: skipNeo4j,
  hyde_preview: (input.hyde_document || '').slice(0, 200)
};

// Pass through original data + log
return [{ json: { ...input, _entity_log: log } }];"""
        },
        "id": "entity-extraction-logger",
        "name": "Entity Extraction Logger",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [max_x + 300, 200],
        "onError": "continueRegularOutput"
    }
    wf["nodes"].append(entity_logger)
    changes.append("Added Entity Extraction Logger node")

    # Connect error paths
    error_nodes = find_node_containing(wf, "error")
    for en in error_nodes:
        conn_key = en["name"]
        if conn_key in wf.get("connections", {}):
            existing = wf["connections"][conn_key]["main"]
            if existing and existing[0]:
                continue
        if conn_key not in wf.get("connections", {}):
            wf["connections"][conn_key] = {"main": [[]]}
        wf["connections"][conn_key]["main"][0].append({
            "node": error_logger["name"],
            "type": "main",
            "index": 0
        })
        changes.append(f"Connected {conn_key} -> GitHub Error Logger")
        break

    return changes


def patch_standard_rag(wf, dry_run=False):
    """Add retrieval quality logging to Standard RAG."""
    changes = []

    if has_node(wf, "GitHub Error Logger (standard)"):
        print("  Already has GitHub Error Logger - skipping")
        return changes

    max_x = get_max_position(wf)

    error_logger = make_github_logger_node("standard", [max_x + 300, 0])
    wf["nodes"].append(error_logger)
    changes.append("Added GitHub Error Logger node")

    exec_summary = make_execution_summary_node("standard", [max_x + 300, 200])
    wf["nodes"].append(exec_summary)
    changes.append("Added Execution Summary Logger node")

    return changes


def patch_quantitative_rag(wf, dry_run=False):
    """Add SQL execution logging to Quantitative RAG."""
    changes = []

    if has_node(wf, "GitHub Error Logger (quantitative)"):
        print("  Already has GitHub Error Logger - skipping")
        return changes

    max_x = get_max_position(wf)

    error_logger = make_github_logger_node("quantitative", [max_x + 300, 0])
    wf["nodes"].append(error_logger)
    changes.append("Added GitHub Error Logger node")

    # SQL execution logger
    sql_logger = {
        "parameters": {
            "jsCode": """// SQL Execution Logger
const input = $input.first().json;

const log = {
  timestamp: new Date().toISOString(),
  pipeline: 'quantitative',
  step: 'sql_execution',
  sql: (input.validated_sql || input.sql || input.sql_executed || '').slice(0, 500),
  validation_status: input.validation_status || input.metadata?.validation_status || 'UNKNOWN',
  result_count: input.result_count || 0,
  null_aggregation: input.null_aggregation || false,
  error: input.sql_error || null
};

return [{ json: { ...input, _sql_log: log } }];"""
        },
        "id": "sql-execution-logger",
        "name": "SQL Execution Logger",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [max_x + 300, 200],
        "onError": "continueRegularOutput"
    }
    wf["nodes"].append(sql_logger)
    changes.append("Added SQL Execution Logger node")

    return changes


# ============================================================
# MAIN
# ============================================================

def main():
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("  N8N LOGGING PATCHES DEPLOYMENT")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE DEPLOY'}")
    print("=" * 60)

    patchers = {
        "orchestrator": patch_orchestrator,
        "graph_rag": patch_graph_rag,
        "standard_rag": patch_standard_rag,
        "quantitative_rag": patch_quantitative_rag,
    }

    total_changes = 0

    for name, wf_id in WORKFLOW_IDS.items():
        print(f"\n--- {name} (ID: {wf_id}) ---")

        wf = download_workflow(wf_id)
        if not wf:
            print(f"  FAILED to download workflow")
            continue

        print(f"  Downloaded: {wf.get('name', '?')} ({len(wf.get('nodes', []))} nodes)")

        patcher = patchers.get(name)
        if not patcher:
            print(f"  No patcher defined - skipping")
            continue

        changes = patcher(wf, dry_run=dry_run)
        if not changes:
            print("  No changes needed")
            continue

        for c in changes:
            print(f"  + {c}")
        total_changes += len(changes)

        if not dry_run:
            result = update_workflow(wf_id, wf)
            if result:
                print(f"  DEPLOYED successfully ({len(wf['nodes'])} nodes)")
                activate_workflow(wf_id)
                print(f"  ACTIVATED")
            else:
                print(f"  DEPLOY FAILED")

    print(f"\n{'=' * 60}")
    print(f"  Total changes: {total_changes}")
    if dry_run:
        print("  (DRY RUN - no changes applied)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
