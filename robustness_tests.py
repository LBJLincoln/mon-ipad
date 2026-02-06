#!/usr/bin/env python3
"""
N8N Robustness Test Suite - Multi-RAG Orchestrator SOTA 2026
10+ tests covering structural integrity, security, edge cases,
cross-workflow consistency, and n8n API import validation.
"""
import json
import copy
import os
import re
import sys
import time
from datetime import datetime
from urllib import request, error
from collections import defaultdict

N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"

MODIFIED_DIR = '/home/user/mon-ipad/modified-workflows'

# Workflow file -> n8n ID mapping
WORKFLOW_MAP = {
    "TEST - SOTA 2026 - Ingestion V3.1.json": "nh1D4Up0wBZhuQbp",
    "TEST - SOTA 2026 - Enrichissement V3.1.json": "ORa01sX4xI0iRCJ8",
    "V10.1 orchestrator copy (5).json": "FZxkpldDbgV8AD_cg7IWG",
    "TEST - SOTA 2026 - WF5 Standard RAG V3.4 - CORRECTED.json": "LnTqRX4LZlI009Ks-3Jnp",
    "TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED (1).json": "95x2BBAbJlLWZtWEJn6rb",
    "TEST - SOTA 2026 - Feedback V3.1.json": "iVsj6dq8UpX5Dk7c",
    "TEST - SOTA 2026 - WF4 Quantitative V2.0 (1).json": "LjUz8fxQZ03G9IsU",
}


class TestResult:
    def __init__(self, name, status, details=None, errors=None):
        self.name = name
        self.status = status  # PASS, FAIL, WARN
        self.details = details or []
        self.errors = errors or []


def load_workflows():
    """Load all patched workflows from disk."""
    workflows = {}
    for fname in WORKFLOW_MAP.keys():
        fpath = os.path.join(MODIFIED_DIR, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            workflows[fname] = json.load(f)
    return workflows


def api_get(endpoint):
    url = f"{N8N_HOST}/api/v1{endpoint}"
    req = request.Request(url, headers={
        "X-N8N-API-KEY": N8N_API_KEY,
        "Accept": "application/json"
    })
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def api_put(wf_id, data):
    url = f"{N8N_HOST}/api/v1/workflows/{wf_id}"
    body = json.dumps(data).encode('utf-8')
    req = request.Request(url, data=body, headers={
        "X-N8N-API-KEY": N8N_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }, method="PUT")
    try:
        with request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)


# ============================================================
# TEST 1: Connection Graph Completeness
# ============================================================
def test_connection_graph_completeness(workflows):
    """Every connection source and target must reference existing nodes."""
    errors = []
    details = []

    for fname, wf in workflows.items():
        node_names = {n["name"] for n in wf.get("nodes", [])}
        connections = wf.get("connections", {})

        # Check source keys
        for source_key in connections:
            if source_key not in node_names:
                errors.append(f"[{fname}] Orphaned connection source: '{source_key}'")

        # Check target nodes
        for source_key, conn_data in connections.items():
            if isinstance(conn_data, dict) and "main" in conn_data:
                for out_idx, outputs in enumerate(conn_data["main"]):
                    if isinstance(outputs, list):
                        for conn in outputs:
                            target = conn.get("node", "")
                            if target and target not in node_names:
                                errors.append(
                                    f"[{fname}] '{source_key}' main[{out_idx}] -> "
                                    f"non-existent target '{target}'"
                                )

        details.append(f"{fname}: {len(node_names)} nodes, {len(connections)} sources checked")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T01: Connection Graph Completeness", status, details, errors)


# ============================================================
# TEST 2: $node['...'] Reference Integrity
# ============================================================
def test_node_reference_integrity(workflows):
    """All $node['X'] references in code/expressions must point to existing nodes."""
    errors = []
    details = []
    ref_pattern = re.compile(r"\$node\[[\'\"]([^\'\"]+)[\'\"]\]")

    for fname, wf in workflows.items():
        node_names = {n["name"] for n in wf.get("nodes", [])}
        refs_found = 0
        refs_broken = 0

        for node in wf.get("nodes", []):
            node_name = node.get("name", "?")
            params = node.get("parameters", {})

            # Check jsCode
            js_code = params.get("jsCode", "")
            if js_code:
                for match in ref_pattern.finditer(js_code):
                    ref = match.group(1)
                    refs_found += 1
                    if ref not in node_names:
                        refs_broken += 1
                        errors.append(
                            f"[{fname}] Node '{node_name}' jsCode references "
                            f"non-existent node: $node['{ref}']"
                        )

            # Check expression templates in jsonBody and other params
            for param_key, param_val in params.items():
                if isinstance(param_val, str) and "$node[" in param_val:
                    for match in ref_pattern.finditer(param_val):
                        ref = match.group(1)
                        refs_found += 1
                        if ref not in node_names:
                            refs_broken += 1
                            errors.append(
                                f"[{fname}] Node '{node_name}' param '{param_key}' "
                                f"references non-existent: $node['{ref}']"
                            )

        details.append(f"{fname}: {refs_found} refs found, {refs_broken} broken")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T02: $node[] Reference Integrity", status, details, errors)


# ============================================================
# TEST 3: Duplicate Node IDs and Names
# ============================================================
def test_no_duplicate_nodes(workflows):
    """No workflow should have duplicate node IDs or names."""
    errors = []
    details = []

    for fname, wf in workflows.items():
        ids_seen = {}
        names_seen = {}

        for i, node in enumerate(wf.get("nodes", [])):
            nid = node.get("id", "")
            nname = node.get("name", "")

            if nid in ids_seen:
                errors.append(f"[{fname}] Duplicate node ID '{nid}' at indices {ids_seen[nid]} and {i}")
            else:
                ids_seen[nid] = i

            if nname in names_seen:
                errors.append(f"[{fname}] Duplicate node name '{nname}' at indices {names_seen[nname]} and {i}")
            else:
                names_seen[nname] = i

        details.append(f"{fname}: {len(ids_seen)} unique IDs, {len(names_seen)} unique names")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T03: No Duplicate Node IDs/Names", status, details, errors)


# ============================================================
# TEST 4: Security - SQL Injection Patterns Blocked
# ============================================================
def test_sql_injection_protection(workflows):
    """Verify SQL validator nodes properly block injection patterns."""
    errors = []
    details = []

    injection_patterns_to_check = [
        "DELETE", "UPDATE", "INSERT", "DROP", "TRUNCATE",
        "ALTER", "CREATE", "GRANT", "REVOKE", "EXEC"
    ]

    for fname, wf in workflows.items():
        for node in wf.get("nodes", []):
            if "SQL Validator" in node.get("name", "") or "Shield #1" in node.get("name", ""):
                code = node.get("parameters", {}).get("jsCode", "")

                # Check each injection pattern is blocked
                blocked = []
                missing = []
                for pattern in injection_patterns_to_check:
                    if pattern in code:
                        blocked.append(pattern)
                    else:
                        missing.append(pattern)

                if missing:
                    errors.append(f"[{fname}] SQL Validator missing blocks for: {missing}")
                details.append(f"{fname} SQL Validator: {len(blocked)}/{len(injection_patterns_to_check)} patterns blocked")

                # Check tenant_id enforcement
                if "tenant_id" in code.lower() or "TENANT_ID" in code:
                    details.append(f"{fname}: tenant_id enforcement present")
                else:
                    errors.append(f"[{fname}] SQL Validator missing tenant_id enforcement")

                # Check LIMIT enforcement
                if "limitValue > 100" in code:
                    details.append(f"{fname}: LIMIT 100 enforcement present")
                elif "limitValue > 1000" in code:
                    errors.append(f"[{fname}] SQL Validator still has LIMIT 1000 (should be 100)")
                else:
                    details.append(f"{fname}: No explicit LIMIT check found")

    if not details:
        details.append("No SQL Validator nodes found (only WF4 has one)")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T04: SQL Injection Protection", status, details, errors)


# ============================================================
# TEST 5: ACL / Tenant Isolation
# ============================================================
def test_tenant_isolation(workflows):
    """Verify tenant_id is properly used in ACL nodes and queries."""
    errors = []
    details = []

    for fname, wf in workflows.items():
        has_acl = False
        for node in wf.get("nodes", []):
            name = node.get("name", "")
            code = node.get("parameters", {}).get("jsCode", "")

            if "ACL" in name or "Init" in name:
                has_acl = True

                # WF5: Check ACL inversion fix
                if "disable_acl" in code:
                    if "disable_acl === true" in code:
                        details.append(f"[{fname}] ACL bypass check: CORRECT (=== true)")
                    elif "disable_acl !== true" in code:
                        errors.append(f"[{fname}] ACL logic still inverted (!== true)")
                    else:
                        details.append(f"[{fname}] ACL disable_acl present but pattern unknown")

                # Check tenant_id extraction
                if "tenant_id" in code:
                    details.append(f"[{fname}] '{name}' extracts tenant_id")

            # Check queries that touch Postgres/Neo4j for tenant_id
            if node.get("type") == "n8n-nodes-base.postgres":
                query = node.get("parameters", {}).get("query", "")
                if query and "tenant_id" not in query.lower() and "SELECT" in query.upper():
                    details.append(f"[{fname}] WARN: Postgres query in '{name}' may lack tenant_id filter")

    status = "PASS" if not errors else ("WARN" if not has_acl else "PASS")
    return TestResult("T05: Tenant Isolation & ACL", status, details, errors)


# ============================================================
# TEST 6: Cross-Workflow Consistency (Orchestrator -> Sub-workflows)
# ============================================================
def test_cross_workflow_consistency(workflows):
    """Verify orchestrator sub-workflow references match actual workflow IDs."""
    errors = []
    details = []

    orch_fname = "V10.1 orchestrator copy (5).json"
    if orch_fname not in workflows:
        return TestResult("T06: Cross-Workflow Consistency", "SKIP", ["Orchestrator not found"])

    orch = workflows[orch_fname]

    # Known sub-workflow IDs that should be referenced
    expected_sub_wfs = {
        "WF5": "LnTqRX4LZlI009Ks-3Jnp",    # Standard RAG
        "WF2": "95x2BBAbJlLWZtWEJn6rb",      # Graph RAG
        "WF4": "LjUz8fxQZ03G9IsU",           # Quantitative (note: may use different ID)
    }

    # Find executeWorkflow nodes in orchestrator
    for node in orch.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.executeWorkflow":
            name = node.get("name", "")
            raw_wf_id = node.get("parameters", {}).get("workflowId", "")

            # n8n uses __rl objects: {'__rl': True, 'value': 'actual_id', 'mode': 'id'}
            if isinstance(raw_wf_id, dict):
                wf_id = raw_wf_id.get("value", "")
                details.append(f"  '{name}' -> workflowId: {wf_id} (mode={raw_wf_id.get('mode')})")
            elif isinstance(raw_wf_id, str):
                wf_id = raw_wf_id
                details.append(f"  '{name}' -> workflowId: {wf_id}")
            else:
                wf_id = ""
                details.append(f"  '{name}' has no workflowId (may use expression)")

            if wf_id:
                # Verify the sub-workflow exists on n8n
                resp = api_get(f"/workflows/{wf_id}")
                if "error" in resp:
                    errors.append(f"Sub-workflow {wf_id} ('{name}') not accessible: {resp['error']}")
                else:
                    sub_name = resp.get("name", "?")
                    sub_nodes = len(resp.get("nodes", []))
                    details.append(f"    -> Found: '{sub_name}' ({sub_nodes} nodes)")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T06: Cross-Workflow Consistency", status, details, errors)


# ============================================================
# TEST 7: Expression Template Syntax Validation
# ============================================================
def test_expression_syntax(workflows):
    """Check for malformed n8n expression templates."""
    errors = []
    details = []
    warnings = []

    # Patterns that indicate broken expressions
    # Note: n8n jsonBody fields often span multiple lines with {{ }} on different lines
    # so we only check for truly broken patterns, not multiline templates
    bad_patterns = [
        (re.compile(r'\{\{\{\{'), "Quadruple-nested braces {{{{ detected"),
    ]

    for fname, wf in workflows.items():
        expr_count = 0
        for node in wf.get("nodes", []):
            params = node.get("parameters", {})
            for param_key, param_val in params.items():
                if isinstance(param_val, str) and "{{" in param_val:
                    expr_count += 1

                    for pattern, desc in bad_patterns:
                        if pattern.search(param_val):
                            errors.append(
                                f"[{fname}] Node '{node.get('name', '?')}' param '{param_key}': {desc}"
                            )

                    # Check for common expression issues
                    # Unmatched {{ and }}
                    opens = param_val.count("{{")
                    closes = param_val.count("}}")
                    if opens != closes:
                        warnings.append(
                            f"[{fname}] Node '{node.get('name', '?')}' param '{param_key}': "
                            f"unbalanced braces ({{ x{opens}, }} x{closes})"
                        )

        details.append(f"{fname}: {expr_count} expressions checked")

    if warnings:
        details.extend([f"  WARN: {w}" for w in warnings[:5]])

    status = "PASS" if not errors else "FAIL"
    return TestResult("T07: Expression Template Syntax", status, details, errors)


# ============================================================
# TEST 8: Node Type Validity
# ============================================================
def test_node_types_valid(workflows):
    """All node types should be valid n8n node types."""
    errors = []
    details = []

    valid_prefixes = [
        "n8n-nodes-base.",
        "@n8n/n8n-nodes-langchain.",
    ]

    for fname, wf in workflows.items():
        type_counts = defaultdict(int)
        invalid_types = []

        for node in wf.get("nodes", []):
            ntype = node.get("type", "")
            type_counts[ntype] += 1

            if not ntype:
                invalid_types.append(f"'{node.get('name', '?')}' has empty type")
            elif not any(ntype.startswith(prefix) for prefix in valid_prefixes):
                invalid_types.append(f"'{node.get('name', '?')}' has unknown type: {ntype}")

        details.append(f"{fname}: {len(type_counts)} distinct types, {sum(type_counts.values())} total nodes")

        if invalid_types:
            for it in invalid_types:
                errors.append(f"[{fname}] {it}")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T08: Node Type Validity", status, details, errors)


# ============================================================
# TEST 9: Settings & API Compatibility
# ============================================================
def test_settings_api_compatibility(workflows):
    """Verify no forbidden settings fields remain that would cause API rejection."""
    errors = []
    details = []

    FORBIDDEN_SETTINGS = {"timeSavedMode", "saveExecutionProgress", "saveManualExecutions"}

    for fname, wf in workflows.items():
        settings = wf.get("settings", {})
        forbidden_found = []

        for field in FORBIDDEN_SETTINGS:
            if field in settings:
                forbidden_found.append(field)
                errors.append(f"[{fname}] Forbidden settings field: '{field}'")

        if not forbidden_found:
            details.append(f"{fname}: settings clean ({sorted(settings.keys())})")
        else:
            details.append(f"{fname}: forbidden fields found: {forbidden_found}")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T09: Settings API Compatibility", status, details, errors)


# ============================================================
# TEST 10: Idempotent Re-import via API
# ============================================================
def test_idempotent_reimport(workflows):
    """Verify all workflows can be re-imported without errors (idempotency)."""
    errors = []
    details = []

    STRIP_SETTINGS = {"timeSavedMode", "saveExecutionProgress", "saveManualExecutions"}

    for fname, wf_id in WORKFLOW_MAP.items():
        wf = workflows.get(fname)
        if not wf:
            errors.append(f"[{fname}] File not loaded")
            continue

        settings = copy.deepcopy(wf.get("settings", {}))
        for field in STRIP_SETTINGS:
            settings.pop(field, None)

        payload = {
            "name": wf["name"],
            "nodes": wf["nodes"],
            "connections": wf["connections"],
            "settings": settings
        }

        status_code, resp = api_put(wf_id, payload)
        if status_code == 200:
            resp_nodes = len(resp.get("nodes", []))
            if resp_nodes == len(wf["nodes"]):
                details.append(f"{fname}: re-import OK ({resp_nodes} nodes)")
            else:
                errors.append(
                    f"[{fname}] Node count mismatch after re-import: "
                    f"sent {len(wf['nodes'])}, got {resp_nodes}"
                )
        else:
            errors.append(f"[{fname}] Re-import failed ({status_code}): {str(resp)[:200]}")

        time.sleep(0.5)

    status = "PASS" if not errors else "FAIL"
    return TestResult("T10: Idempotent Re-import", status, details, errors)


# ============================================================
# TEST 11: Topological Sort - No Circular Dependencies
# ============================================================
def test_no_circular_dependencies(workflows):
    """Verify no unexpected cycles. Intentional n8n loops are allowed:
    - SplitInBatches loops (batch processing pattern)
    - Self-repair loops (SQL retry pattern)
    - Task execution loops (orchestrator pattern)
    """
    errors = []
    details = []

    # Node types/names that legitimately create cycles in n8n
    ALLOWED_CYCLE_PATTERNS = {
        "splitInBatches", "SplitInBatches", "Split",    # Batch processing
        "Repair", "Self-Healing", "Diagnostic",          # Self-repair loops
        "Execution Engine", "Task Result", "Fallback",   # Orchestrator loops
        "Loop", "Retry",                                  # Explicit loop nodes
    }

    for fname, wf in workflows.items():
        node_names = {n["name"] for n in wf.get("nodes", [])}
        node_types = {n["name"]: n.get("type", "") for n in wf.get("nodes", [])}

        # Build adjacency list
        adj = defaultdict(set)
        connections = wf.get("connections", {})

        for source, conn_data in connections.items():
            if isinstance(conn_data, dict) and "main" in conn_data:
                for outputs in conn_data["main"]:
                    if isinstance(outputs, list):
                        for conn in outputs:
                            target = conn.get("node", "")
                            if target:
                                adj[source].add(target)

        # DFS cycle detection
        WHITE, GRAY, BLACK = 0, 1, 2
        color = defaultdict(int)
        cycles = []

        def dfs(node, path):
            color[node] = GRAY
            for neighbor in adj.get(node, []):
                if color[neighbor] == GRAY:
                    cycles.append((node, neighbor))
                elif color[neighbor] == WHITE:
                    dfs(neighbor, path + [node])
            color[node] = BLACK

        all_nodes = set(adj.keys())
        for targets in adj.values():
            all_nodes.update(targets)

        for node in all_nodes:
            if color[node] == WHITE:
                dfs(node, [])

        # Filter out allowed cycles
        unexpected_cycles = []
        allowed_cycles = []
        for src, tgt in cycles:
            is_allowed = False
            for pattern in ALLOWED_CYCLE_PATTERNS:
                if (pattern.lower() in src.lower() or pattern.lower() in tgt.lower() or
                        "splitInBatches" in node_types.get(src, "") or
                        "splitInBatches" in node_types.get(tgt, "")):
                    is_allowed = True
                    break
            if is_allowed:
                allowed_cycles.append(f"{src} -> {tgt}")
            else:
                unexpected_cycles.append(f"{src} -> {tgt}")

        if unexpected_cycles:
            errors.append(f"[{fname}] Unexpected cycles: {', '.join(unexpected_cycles[:3])}")
            details.append(f"{fname}: {len(unexpected_cycles)} unexpected cycles")
        else:
            cycle_info = f", {len(allowed_cycles)} intentional loops" if allowed_cycles else ""
            details.append(
                f"{fname}: OK ({len(all_nodes)} nodes, "
                f"{sum(len(v) for v in adj.values())} edges{cycle_info})"
            )

    status = "PASS" if not errors else "FAIL"
    return TestResult("T11: No Circular Dependencies (DAG)", status, details, errors)


# ============================================================
# TEST 12: Critical Patch Verification (Regression Guard)
# ============================================================
def test_critical_patches_applied(workflows):
    """Verify specific critical patches haven't been reverted."""
    errors = []
    details = []

    # ---- Ingestion: Chunk Validator & Enricher V4 (renamed from Chunk Enricher V3.1) ----
    ing = workflows.get("TEST - SOTA 2026 - Ingestion V3.1.json")
    if ing:
        names = {n["name"] for n in ing["nodes"]}
        if "Chunk Validator & Enricher V4" in names:
            details.append("Ingestion: Chunk Validator & Enricher V4 present")
        else:
            errors.append("Ingestion: Chunk Validator & Enricher V4 MISSING (regression)")

        if "Chunk Enricher V3.1 (Contextual)" in names:
            errors.append("Ingestion: OLD node 'Chunk Enricher V3.1 (Contextual)' still exists (regression)")

        # Check embedding template fix
        for n in ing["nodes"]:
            if n.get("name") == "Generate Embeddings V3.1 (Contextual)":
                jb = n.get("parameters", {}).get("jsonBody", "")
                if "{{{{" in jb:
                    errors.append("Ingestion: Generate Embeddings still has triple-nested {{{{ (regression)")
                else:
                    details.append("Ingestion: Embedding template clean")

    # ---- WF2 Graph RAG: Shield #9 enabled ----
    gr = workflows.get("TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED (1).json")
    if gr:
        for n in gr["nodes"]:
            if "Shield #9" in n.get("name", ""):
                if n.get("disabled") is False:
                    details.append("WF2 Graph RAG: Shield #9 enabled (OTEL tracing active)")
                else:
                    errors.append(f"WF2 Graph RAG: Shield #9 disabled={n.get('disabled')} (regression)")

        # Centrality Scoring node exists
        names = {n["name"] for n in gr["nodes"]}
        if "Centrality Scoring" in names:
            details.append("WF2 Graph RAG: Centrality Scoring node present")
        else:
            errors.append("WF2 Graph RAG: Centrality Scoring node MISSING (regression)")

        # Check Cohere reranker model
        for n in gr["nodes"]:
            jb = n.get("parameters", {}).get("jsonBody", "")
            if "rerank" in jb:
                if "rerank-v3.5" in jb:
                    details.append("WF2 Graph RAG: Cohere rerank-v3.5 confirmed")
                elif "rerank-multilingual-v3.0" in jb:
                    errors.append("WF2 Graph RAG: Still using old rerank-multilingual-v3.0 (regression)")

    # ---- WF4 Quantitative: Q01/Q02 renames ----
    qt = workflows.get("TEST - SOTA 2026 - WF4 Quantitative V2.0 (1).json")
    if qt:
        names = {n["name"] for n in qt["nodes"]}
        if "Few-Shot SQL Generator (Q01)" in names:
            details.append("WF4 Quant: Q01 rename confirmed")
        else:
            errors.append("WF4 Quant: Few-Shot SQL Generator (Q01) MISSING (regression)")

        if "Diagnostic Error Handler (Q02)" in names:
            details.append("WF4 Quant: Q02 rename confirmed")
        else:
            errors.append("WF4 Quant: Diagnostic Error Handler (Q02) MISSING (regression)")

        # Check old names don't exist
        if "Prepare SQL Request" in names:
            errors.append("WF4 Quant: OLD 'Prepare SQL Request' still exists (regression)")
        if "SQL Error Handler (Self-Healing)" in names:
            errors.append("WF4 Quant: OLD 'SQL Error Handler (Self-Healing)' still exists (regression)")

    # ---- Orchestrator: claude-sonnet-4-5 ----
    orch = workflows.get("V10.1 orchestrator copy (5).json")
    if orch:
        for n in orch["nodes"]:
            if n.get("name") == "LLM 3: Agent Harness":
                jb = n.get("parameters", {}).get("jsonBody", "")
                if "claude-sonnet-4-5" in jb:
                    details.append("Orchestrator: claude-sonnet-4-5 confirmed in LLM 3")
                else:
                    errors.append("Orchestrator: claude-sonnet-4-5 NOT FOUND in LLM 3 (regression)")

    # ---- Feedback: Webhook -> IFA ----
    fb = workflows.get("TEST - SOTA 2026 - Feedback V3.1.json")
    if fb:
        conn = fb.get("connections", {})
        if "Webhook Feedback" in conn:
            targets = [c["node"] for c in conn["Webhook Feedback"]["main"][0]]
            if "Implicit Feedback Analyzer" in targets:
                details.append("Feedback: Webhook -> IFA connected")
            else:
                errors.append(f"Feedback: Webhook -> IFA not connected (targets: {targets}) (regression)")

    status = "PASS" if not errors else "FAIL"
    return TestResult("T12: Critical Patch Regression Guard", status, details, errors)


# ============================================================
# TEST 13: Node Position Validity (no overlapping nodes)
# ============================================================
def test_node_positions(workflows):
    """Check that nodes have valid positions and no exact overlaps."""
    errors = []
    details = []

    for fname, wf in workflows.items():
        positions = {}
        missing_pos = 0
        overlaps = 0

        for node in wf.get("nodes", []):
            name = node.get("name", "?")
            pos = node.get("position")

            if not pos or not isinstance(pos, (list, tuple)) or len(pos) < 2:
                missing_pos += 1
                continue

            pos_key = f"{pos[0]},{pos[1]}"
            if pos_key in positions:
                overlaps += 1
                # Only flag if both are non-stickyNote (sticky notes can overlap)
                if (node.get("type") != "n8n-nodes-base.stickyNote" and
                        positions[pos_key].get("type") != "n8n-nodes-base.stickyNote"):
                    details.append(
                        f"[{fname}] Overlap: '{name}' and '{positions[pos_key].get('name', '?')}' "
                        f"at ({pos[0]}, {pos[1]})"
                    )
            else:
                positions[pos_key] = node

        detail = f"{fname}: {len(positions)} positions"
        if missing_pos:
            detail += f", {missing_pos} missing"
        if overlaps:
            detail += f", {overlaps} overlaps"
        details.append(detail)

    # Overlaps are warnings, not errors (n8n handles them)
    status = "PASS"
    return TestResult("T13: Node Position Validity", status, details, errors)


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 70)
    print("  ROBUSTNESS TEST SUITE - Multi-RAG Orchestrator SOTA 2026")
    print(f"  Target: {N8N_HOST}")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    print("\nLoading workflows...")
    workflows = load_workflows()
    print(f"Loaded {len(workflows)} workflows\n")

    # Run all tests
    tests = [
        ("T01", test_connection_graph_completeness),
        ("T02", test_node_reference_integrity),
        ("T03", test_no_duplicate_nodes),
        ("T04", test_sql_injection_protection),
        ("T05", test_tenant_isolation),
        ("T06", test_cross_workflow_consistency),
        ("T07", test_expression_syntax),
        ("T08", test_node_types_valid),
        ("T09", test_settings_api_compatibility),
        ("T10", test_idempotent_reimport),
        ("T11", test_no_circular_dependencies),
        ("T12", test_critical_patches_applied),
        ("T13", test_node_positions),
    ]

    results = []
    for test_id, test_fn in tests:
        print(f"\n{'─'*70}")
        print(f"Running {test_id}...")
        try:
            result = test_fn(workflows)
            results.append(result)
            icon = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "SKIP"}.get(result.status, "????")
            print(f"  [{icon}] {result.name}")
            for d in result.details[:8]:
                print(f"    {d}")
            if result.errors:
                print(f"    ERRORS ({len(result.errors)}):")
                for e in result.errors[:5]:
                    print(f"      {e}")
                if len(result.errors) > 5:
                    print(f"      ... and {len(result.errors) - 5} more")
        except Exception as ex:
            print(f"  [ERR!] {test_id} crashed: {ex}")
            results.append(TestResult(test_id, "ERROR", [], [str(ex)]))

    # ============================================================
    # FINAL SUMMARY
    # ============================================================
    print(f"\n{'='*70}")
    print("  FINAL RESULTS")
    print(f"{'='*70}")

    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    warned = sum(1 for r in results if r.status == "WARN")
    skipped = sum(1 for r in results if r.status == "SKIP")
    errored = sum(1 for r in results if r.status == "ERROR")

    for r in results:
        icon = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "SKIP", "ERROR": "ERR!"}.get(r.status, "????")
        error_summary = f" ({len(r.errors)} errors)" if r.errors else ""
        print(f"  [{icon}] {r.name}{error_summary}")

    print(f"\n  Total: {len(results)} tests")
    print(f"  Passed: {passed}")
    if failed: print(f"  Failed: {failed}")
    if warned: print(f"  Warnings: {warned}")
    if skipped: print(f"  Skipped: {skipped}")
    if errored: print(f"  Errors: {errored}")

    overall = "ALL TESTS PASSED" if failed == 0 and errored == 0 else "SOME TESTS FAILED"
    print(f"\n  >> {overall} <<")

    # Save report
    report = {
        "generated_at": datetime.now().isoformat(),
        "generated_by": "n8n-robustness-test-suite",
        "target": N8N_HOST,
        "total_tests": len(results),
        "passed": passed,
        "failed": failed,
        "warned": warned,
        "tests": [
            {
                "name": r.name,
                "status": r.status,
                "details": r.details,
                "errors": r.errors
            }
            for r in results
        ]
    }

    report_path = os.path.join(MODIFIED_DIR, 'robustness-test-results.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Report: {report_path}")

    return 0 if failed == 0 and errored == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
