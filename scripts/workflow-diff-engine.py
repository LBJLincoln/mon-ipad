#!/usr/bin/env python3
"""
Workflow Diff Engine - Compare live HF Space workflows against golden reference
Session 61 - Diagnostic tool for workflow drift detection

Compares current workflow state on 10 HF Spaces against golden reference from 22 Feb.
Diagnoses differences in nodes, connections, credentials, and parameters.
"""

import urllib.request
import urllib.parse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookiejar import CookieJar
from typing import Dict, List, Tuple, Optional, Any
import time
import argparse
import re

# HF Spaces to check
SPACES = [
    "https://lbjlincoln-nomos-rag-engine.hf.space",
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

WORKFLOW_DIR = "/home/termius/mon-ipad/hf-space/n8n-workflows"

# Core pipelines to compare
CORE_PIPELINES = {
    "standard": "standard.json",
    "graph": "graph.json",
    "quantitative": "quantitative.json",
    "orchestrator": "orchestrator-v10.json",
}

# Fields to ignore in comparison (they change on every deploy)
IGNORE_FIELDS = {
    "id",  # Node IDs change
    "versionId",  # Version changes
    "updatedAt",  # Timestamps change
    "createdAt",
    "webhookId",  # Regenerated
    "position",  # UI position doesn't affect logic
}

# ANSI colors for terminal output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"


class N8nClient:
    """N8n API client with cookie-based authentication"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

    def _request(
        self, method: str, path: str, data: Optional[dict] = None, headers: Optional[dict] = None
    ) -> Any:
        """Make HTTP request with cookie jar"""
        url = f"{self.base_url}{path}"
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)

        body = json.dumps(data).encode("utf-8") if data else None

        request = urllib.request.Request(url, data=body, headers=req_headers, method=method)

        try:
            with self.opener.open(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                # n8n API wraps responses in {"data": ..., "count": N} or just {"data": ...}
                if isinstance(result, dict) and "data" in result:
                    return result["data"]
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise Exception(f"HTTP {e.code}: {error_body}")

    def login(self, email: str, password: str) -> bool:
        """Login to n8n"""
        try:
            self._request(
                "POST",
                "/rest/login",
                {"emailOrLdapLoginId": email, "password": password},
            )
            return True
        except Exception as e:
            print(f"Login failed: {e}")
            return False

    def get_credentials(self) -> List[dict]:
        """Get all credentials"""
        return self._request("GET", "/rest/credentials")

    def get_workflows(self) -> List[dict]:
        """Get all workflows"""
        return self._request("GET", "/rest/workflows")

    def get_workflow(self, workflow_id: str) -> dict:
        """Get workflow details"""
        return self._request("GET", f"/rest/workflows/{workflow_id}")

    def update_workflow(self, workflow_id: str, data: dict) -> dict:
        """Update workflow using PATCH"""
        return self._request("PATCH", f"/rest/workflows/{workflow_id}", data)

    def activate_workflow(self, workflow_id: str, version_id: str) -> dict:
        """Activate workflow using POST /activate with versionId"""
        return self._request(
            "POST",
            f"/rest/workflows/{workflow_id}/activate",
            {"versionId": version_id},
        )


def load_golden_workflow(filename: str) -> Optional[dict]:
    """Load golden reference workflow from file"""
    filepath = os.path.join(WORKFLOW_DIR, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        return json.load(f)


def normalize_credential_ref(cred_ref: Any) -> str:
    """Normalize credential reference for comparison (ignore IDs)"""
    if isinstance(cred_ref, dict):
        # Use type + name as signature, ignore ID
        cred_type = cred_ref.get("type", "")
        cred_name = cred_ref.get("name", "")
        return f"{cred_type}:{cred_name}"
    return str(cred_ref)


def normalize_node(node: dict) -> dict:
    """Normalize node for comparison (remove volatile fields)"""
    normalized = {}
    for key, value in node.items():
        if key in IGNORE_FIELDS:
            continue

        if key == "credentials":
            # Normalize credential references (ignore IDs)
            normalized_creds = {}
            if isinstance(value, dict):
                for cred_type, cred_data in value.items():
                    normalized_creds[cred_type] = normalize_credential_ref(cred_data)
            normalized[key] = normalized_creds
        else:
            normalized[key] = value

    return normalized


def compare_nodes(golden_nodes: List[dict], current_nodes: List[dict]) -> List[dict]:
    """Compare nodes between golden and current workflows"""
    differences = []

    # Build node lookups by name
    golden_by_name = {node["name"]: node for node in golden_nodes}
    current_by_name = {node["name"]: node for node in current_nodes}

    # Check for missing nodes
    for name in golden_by_name:
        if name not in current_by_name:
            differences.append({
                "type": "NODE_REMOVED",
                "severity": "high",
                "node": name,
                "message": f"Node '{name}' exists in golden but not in current",
                "details": {
                    "node_type": golden_by_name[name].get("type"),
                }
            })

    # Check for added nodes
    for name in current_by_name:
        if name not in golden_by_name:
            differences.append({
                "type": "NODE_ADDED",
                "severity": "medium",
                "node": name,
                "message": f"Node '{name}' exists in current but not in golden",
                "details": {
                    "node_type": current_by_name[name].get("type"),
                }
            })

    # Compare common nodes
    for name in set(golden_by_name.keys()) & set(current_by_name.keys()):
        golden_node = normalize_node(golden_by_name[name])
        current_node = normalize_node(current_by_name[name])

        # Check node type change
        if golden_node.get("type") != current_node.get("type"):
            differences.append({
                "type": "NODE_TYPE_CHANGED",
                "severity": "high",
                "node": name,
                "message": f"Node '{name}' type changed",
                "details": {
                    "golden_type": golden_node.get("type"),
                    "current_type": current_node.get("type"),
                }
            })
            continue

        # Check credential changes
        golden_creds = golden_node.get("credentials", {})
        current_creds = current_node.get("credentials", {})

        if golden_creds != current_creds:
            missing_creds = set(golden_creds.keys()) - set(current_creds.keys())
            if missing_creds:
                differences.append({
                    "type": "CREDENTIAL_MISSING",
                    "severity": "critical",
                    "node": name,
                    "message": f"Node '{name}' is missing credentials",
                    "details": {
                        "missing_credential_types": list(missing_creds),
                        "golden": golden_creds,
                        "current": current_creds,
                    }
                })

        # Check parameter changes (deep comparison)
        golden_params = golden_node.get("parameters", {})
        current_params = current_node.get("parameters", {})

        param_diffs = compare_parameters(golden_params, current_params)
        if param_diffs:
            differences.append({
                "type": "NODE_MODIFIED",
                "severity": "medium",
                "node": name,
                "message": f"Node '{name}' has different parameters",
                "details": {
                    "parameter_changes": param_diffs,
                }
            })

    return differences


def compare_parameters(golden_params: dict, current_params: dict, path: str = "") -> List[dict]:
    """Deep comparison of node parameters"""
    differences = []

    all_keys = set(golden_params.keys()) | set(current_params.keys())

    for key in all_keys:
        current_path = f"{path}.{key}" if path else key

        if key not in golden_params:
            differences.append({
                "path": current_path,
                "change": "added",
                "current_value": current_params[key],
            })
        elif key not in current_params:
            differences.append({
                "path": current_path,
                "change": "removed",
                "golden_value": golden_params[key],
            })
        else:
            golden_val = golden_params[key]
            current_val = current_params[key]

            if isinstance(golden_val, dict) and isinstance(current_val, dict):
                # Recursive comparison for nested objects
                nested_diffs = compare_parameters(golden_val, current_val, current_path)
                differences.extend(nested_diffs)
            elif golden_val != current_val:
                differences.append({
                    "path": current_path,
                    "change": "modified",
                    "golden_value": str(golden_val)[:100],  # Truncate for readability
                    "current_value": str(current_val)[:100],
                })

    return differences


def compare_connections(golden_conn: dict, current_conn: dict, golden_nodes: List[dict], current_nodes: List[dict]) -> List[dict]:
    """Compare connections between nodes"""
    differences = []

    # Build node ID to name mapping
    golden_id_to_name = {node["id"]: node["name"] for node in golden_nodes}
    current_id_to_name = {node["id"]: node["name"] for node in current_nodes}

    # Build node name to ID mapping (reverse)
    golden_name_to_id = {node["name"]: node["id"] for node in golden_nodes}
    current_name_to_id = {node["name"]: node["id"] for node in current_nodes}

    # Convert connections to name-based format for comparison
    def normalize_connections(conn_map: dict, id_to_name: dict) -> dict:
        normalized = {}
        for source_id, targets in conn_map.items():
            source_name = id_to_name.get(source_id, source_id)
            normalized[source_name] = {}
            for output_type, connections in targets.items():
                normalized[source_name][output_type] = []
                # Connections can be [[{...}]] or [{...}]
                if isinstance(connections, list):
                    for conn_group in connections:
                        # Handle nested list [[{...}]]
                        if isinstance(conn_group, list):
                            for conn in conn_group:
                                if isinstance(conn, dict):
                                    target_name = id_to_name.get(conn.get("node"), conn.get("node"))
                                    normalized[source_name][output_type].append({
                                        "node": target_name,
                                        "type": conn.get("type"),
                                        "index": conn.get("index", 0),
                                    })
                        # Handle flat list [{...}]
                        elif isinstance(conn_group, dict):
                            target_name = id_to_name.get(conn_group.get("node"), conn_group.get("node"))
                            normalized[source_name][output_type].append({
                                "node": target_name,
                                "type": conn_group.get("type"),
                                "index": conn_group.get("index", 0),
                            })
        return normalized

    golden_normalized = normalize_connections(golden_conn, golden_id_to_name)
    current_normalized = normalize_connections(current_conn, current_id_to_name)

    # Compare normalized connections
    all_sources = set(golden_normalized.keys()) | set(current_normalized.keys())

    for source in all_sources:
        if source not in golden_normalized:
            differences.append({
                "type": "CONNECTION_ADDED",
                "severity": "low",
                "message": f"New connections from node '{source}'",
                "details": current_normalized[source],
            })
        elif source not in current_normalized:
            differences.append({
                "type": "CONNECTION_REMOVED",
                "severity": "medium",
                "message": f"Connections from node '{source}' removed",
                "details": golden_normalized[source],
            })
        else:
            if golden_normalized[source] != current_normalized[source]:
                differences.append({
                    "type": "CONNECTION_CHANGED",
                    "severity": "medium",
                    "message": f"Connections from node '{source}' modified",
                    "details": {
                        "golden": golden_normalized[source],
                        "current": current_normalized[source],
                    }
                })

    return differences


def compare_workflow(golden: dict, current: dict) -> dict:
    """Compare golden workflow against current workflow"""
    differences = {
        "workflow_name": current.get("name"),
        "workflow_active": current.get("active", False),
        "differences": [],
        "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
    }

    # Check if workflow is inactive
    if not current.get("active", False):
        differences["differences"].append({
            "type": "WORKFLOW_INACTIVE",
            "severity": "high",
            "message": "Workflow is imported but not activated",
            "details": {},
        })
        differences["severity_counts"]["high"] += 1

    # Compare nodes
    node_diffs = compare_nodes(golden.get("nodes", []), current.get("nodes", []))
    differences["differences"].extend(node_diffs)

    # Compare connections
    conn_diffs = compare_connections(
        golden.get("connections", {}),
        current.get("connections", {}),
        golden.get("nodes", []),
        current.get("nodes", [])
    )
    differences["differences"].extend(conn_diffs)

    # Count severities
    for diff in differences["differences"]:
        severity = diff.get("severity", "low")
        differences["severity_counts"][severity] += 1

    return differences


def check_space(space_url: str, verbose: bool = False) -> dict:
    """Check a single HF Space and compare workflows"""
    result = {
        "space": space_url,
        "status": "unknown",
        "workflows": {},
        "errors": [],
    }

    try:
        if verbose:
            print(f"Connecting to {space_url}...")
        client = N8nClient(space_url)

        # Login
        if verbose:
            print(f"Logging in...")
        if not client.login(LOGIN_EMAIL, LOGIN_PASSWORD):
            result["status"] = "login_failed"
            result["errors"].append("Failed to login")
            return result

        # Get current workflows
        if verbose:
            print(f"Fetching workflows...")
        workflows = client.get_workflows()
        if verbose:
            print(f"Found {len(workflows)} workflows")

        # Process each core pipeline
        for pipeline_name, golden_file in CORE_PIPELINES.items():
            try:
                if verbose:
                    print(f"Processing pipeline: {pipeline_name}")

                golden_wf = load_golden_workflow(golden_file)
                if not golden_wf:
                    result["errors"].append(f"Golden workflow not found: {golden_file}")
                    continue

                # Find matching current workflow
                current_wf = None
                for wf in workflows:
                    if verbose:
                        print(f"  Checking workflow: {wf.get('name', 'unnamed')}")

                    wf_name_lower = wf.get("name", "").lower()
                    if pipeline_name in wf_name_lower or golden_file.replace(".json", "") in wf_name_lower:
                        # Get full workflow details
                        if verbose:
                            print(f"  Found match! Getting full details for ID: {wf.get('id')}")
                        current_wf = client.get_workflow(wf["id"])
                        break

                if not current_wf:
                    result["workflows"][pipeline_name] = {
                        "status": "not_found",
                        "message": f"Workflow not found in {space_url}",
                    }
                    continue

                # Compare workflows
                if verbose:
                    print(f"  Comparing workflows...")
                comparison = compare_workflow(golden_wf, current_wf)
                result["workflows"][pipeline_name] = comparison

            except Exception as e:
                if verbose:
                    import traceback
                    traceback.print_exc()
                result["errors"].append(f"Error processing {pipeline_name}: {e}")

        result["status"] = "success"

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(str(e))

    return result


def print_summary(results: List[dict]):
    """Print color-coded summary to stdout"""
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}WORKFLOW DIFF ENGINE - SUMMARY{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}\n")

    for result in results:
        space_url = result["space"]
        status = result["status"]

        # Space header
        if status == "success":
            status_icon = f"{Colors.GREEN}✓{Colors.RESET}"
        elif status == "login_failed":
            status_icon = f"{Colors.RED}✗{Colors.RESET}"
        else:
            status_icon = f"{Colors.YELLOW}⚠{Colors.RESET}"

        print(f"{status_icon} {Colors.BOLD}{space_url}{Colors.RESET}")

        if result.get("errors"):
            for error in result["errors"]:
                print(f"  {Colors.RED}ERROR:{Colors.RESET} {error}")
            print()
            continue

        # Workflow summaries
        for pipeline_name, workflow_data in result.get("workflows", {}).items():
            if workflow_data.get("status") == "not_found":
                print(f"  {Colors.YELLOW}⚠ {pipeline_name}{Colors.RESET}: {workflow_data['message']}")
                continue

            counts = workflow_data.get("severity_counts", {})
            total_diffs = sum(counts.values())

            if total_diffs == 0:
                print(f"  {Colors.GREEN}✓ {pipeline_name}{Colors.RESET}: No differences (100% match)")
            else:
                status_color = Colors.RED if counts.get("critical", 0) > 0 else (
                    Colors.YELLOW if counts.get("high", 0) > 0 else Colors.CYAN
                )

                active = workflow_data.get("workflow_active", False)
                active_str = f"{Colors.GREEN}active{Colors.RESET}" if active else f"{Colors.RED}inactive{Colors.RESET}"

                print(f"  {status_color}⚠ {pipeline_name}{Colors.RESET} ({active_str}): {total_diffs} differences")
                print(f"    Critical: {counts.get('critical', 0)} | High: {counts.get('high', 0)} | "
                      f"Medium: {counts.get('medium', 0)} | Low: {counts.get('low', 0)}")

                # Show top 3 critical/high issues
                critical_diffs = [d for d in workflow_data.get("differences", [])
                                 if d.get("severity") in ["critical", "high"]][:3]
                for diff in critical_diffs:
                    severity = diff["severity"]
                    severity_color = Colors.RED if severity == "critical" else Colors.YELLOW
                    print(f"      {severity_color}[{severity.upper()}]{Colors.RESET} {diff['message']}")

        print()

    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}\n")


def revert_workflow(space_url: str, pipeline_name: str, golden_file: str, dry_run: bool = False) -> bool:
    """Revert a workflow to golden state"""
    try:
        client = N8nClient(space_url)

        if not client.login(LOGIN_EMAIL, LOGIN_PASSWORD):
            print(f"{Colors.RED}Failed to login to {space_url}{Colors.RESET}")
            return False

        # Load golden workflow
        golden_wf = load_golden_workflow(golden_file)
        if not golden_wf:
            print(f"{Colors.RED}Golden workflow not found: {golden_file}{Colors.RESET}")
            return False

        # Find current workflow
        workflows = client.get_workflows()
        current_wf_id = None
        current_wf_name = None
        for wf in workflows:
            if pipeline_name in wf.get("name", "").lower():
                current_wf_id = wf["id"]
                current_wf_name = wf["name"]
                break

        if not current_wf_id:
            print(f"{Colors.RED}Workflow not found: {pipeline_name}{Colors.RESET}")
            return False

        if dry_run:
            print(f"{Colors.CYAN}[DRY-RUN]{Colors.RESET} Would revert '{current_wf_name}' (ID: {current_wf_id})")
            return True

        # Get current workflow for backup
        current_wf = client.get_workflow(current_wf_id)

        # Update workflow with golden state
        # Note: We use golden nodes/connections but preserve the workflow ID
        update_data = {
            "nodes": golden_wf["nodes"],
            "connections": golden_wf.get("connections", {}),
            "settings": golden_wf.get("settings", {}),
        }

        client.update_workflow(current_wf_id, update_data)
        print(f"{Colors.GREEN}✓ Reverted {pipeline_name} on {space_url}{Colors.RESET}")

        # Reactivate if it was active in golden
        if golden_wf.get("active", False):
            new_current = client.get_workflow(current_wf_id)
            version_id = new_current.get("versionId", "1")
            client.activate_workflow(current_wf_id, version_id)
            print(f"{Colors.GREEN}✓ Re-activated {pipeline_name}{Colors.RESET}")

        return True

    except Exception as e:
        print(f"{Colors.RED}Failed to revert {pipeline_name}: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Compare live workflows against golden reference")
    parser.add_argument("--revert", action="store_true", help="Revert workflows to golden state")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be reverted without actually reverting")
    parser.add_argument("--space", type=str, help="Check only this space URL")
    parser.add_argument("--pipeline", type=str, choices=list(CORE_PIPELINES.keys()),
                       help="Check only this pipeline")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    spaces_to_check = [args.space] if args.space else SPACES

    print(f"{Colors.BOLD}Starting Workflow Diff Engine...{Colors.RESET}")
    print(f"Comparing {len(spaces_to_check)} spaces against golden reference")
    print(f"Golden reference: {WORKFLOW_DIR}")
    print()

    results = []

    # Check spaces in parallel (or sequentially if single space + verbose)
    if len(spaces_to_check) == 1 and args.verbose:
        # Sequential for better debugging
        try:
            result = check_space(spaces_to_check[0], verbose=True)
            results.append(result)
        except Exception as e:
            print(f"{Colors.RED}Exception checking {spaces_to_check[0]}: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()
            results.append({
                "space": spaces_to_check[0],
                "status": "exception",
                "errors": [str(e)],
                "workflows": {},
            })
    else:
        # Parallel for efficiency
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(check_space, space, args.verbose): space for space in spaces_to_check}

            for future in as_completed(futures):
                space = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"{Colors.RED}Exception checking {space}: {e}{Colors.RESET}")
                    results.append({
                        "space": space,
                        "status": "exception",
                        "errors": [str(e)],
                        "workflows": {},
                    })

    # Print summary
    print_summary(results)

    # Save detailed JSON report
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    report_path = f"/home/termius/mon-ipad/logs/workflow-diff-{timestamp}.json"
    os.makedirs("/home/termius/mon-ipad/logs", exist_ok=True)

    with open(report_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_spaces": len(spaces_to_check),
            "golden_reference": WORKFLOW_DIR,
            "results": results,
        }, f, indent=2)

    print(f"{Colors.CYAN}Detailed report saved to: {report_path}{Colors.RESET}\n")

    # Revert if requested
    if args.revert or args.dry_run:
        if args.dry_run:
            print(f"{Colors.BOLD}DRY-RUN: Showing what would be reverted...{Colors.RESET}\n")
        else:
            print(f"{Colors.BOLD}REVERTING workflows to golden state...{Colors.RESET}\n")

        revert_count = 0
        for result in results:
            if result["status"] != "success":
                continue

            space_url = result["space"]
            for pipeline_name, workflow_data in result["workflows"].items():
                if args.pipeline and args.pipeline != pipeline_name:
                    continue

                if workflow_data.get("status") == "not_found":
                    continue

                # Only revert if there are differences
                total_diffs = sum(workflow_data.get("severity_counts", {}).values())
                if total_diffs > 0:
                    print(f"Reverting {pipeline_name} on {space_url}...")
                    success = revert_workflow(space_url, pipeline_name, CORE_PIPELINES[pipeline_name], dry_run=args.dry_run)
                    if success:
                        revert_count += 1

        if args.dry_run:
            print(f"\n{Colors.CYAN}Would revert {revert_count} workflows{Colors.RESET}\n")
        else:
            print(f"\n{Colors.GREEN}✓ Reverted {revert_count} workflows{Colors.RESET}\n")


if __name__ == "__main__":
    main()
