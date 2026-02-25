#!/usr/bin/env python3
"""
Restore credential references and re-activate workflows on 8 HF Spaces in parallel
Session 61 - Emergency restoration after credential loss
"""

import urllib.request
import urllib.parse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookiejar import CookieJar
from typing import Dict, List, Tuple, Optional
import time

# HF Spaces to restore
SPACES = [
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

# Credential mapping patterns
CREDENTIAL_PATTERNS = {
    "postgres": {"type": "postgres", "name_pattern": "Supabase"},
    "neo4j": {"type": "httpBasicAuth", "name_pattern": "Neo4j"},
    "redis": {"type": "redis", "name_pattern": "Redis"},
    "pinecone": {"type": "httpHeaderAuth", "name_pattern": "Pinecone"},
    "openrouter_standard": {"type": "httpHeaderAuth", "name_pattern": "OpenRouter.*Standard"},
    "openrouter_graph": {"type": "httpHeaderAuth", "name_pattern": "OpenRouter.*Graph"},
    "openrouter_quantitative": {"type": "httpHeaderAuth", "name_pattern": "OpenRouter.*Quantitative"},
    "openrouter_orchestrator": {"type": "httpHeaderAuth", "name_pattern": "OpenRouter.*Orchestrator"},
}

# Workflow name to file mapping
WORKFLOW_FILES = {
    "standard": "standard.json",
    "graph": "graph.json",
    "quantitative": "quantitative.json",
    "orchestrator": "orchestrator-v10.json",
    "benchmark": "benchmark.json",
    "ingestion": "ingestion.json",
    "enrichment": "enrichment.json",
    "pme-gateway": "pme-gateway.json",
    "dashboard": "dashboard-status-api.json",
}


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
    ) -> dict:
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
                # n8n API wraps responses in {"data": ...}
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
        """Activate workflow (registers webhooks)"""
        return self._request(
            "POST", f"/rest/workflows/{workflow_id}/activate", {"versionId": version_id}
        )

    def test_webhook(self, webhook_path: str, question: str) -> Tuple[int, str]:
        """Test webhook with a question"""
        url = f"{self.base_url}/webhook/{webhook_path}"
        data = json.dumps({"query": question}).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )

        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read().decode("utf-8")
                return response.status, body
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")
        except Exception as e:
            return 0, str(e)


def load_workflow_file(filename: str) -> Optional[dict]:
    """Load workflow JSON from file"""
    filepath = os.path.join(WORKFLOW_DIR, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        return json.load(f)


def map_credentials(original_nodes: List[dict], current_credentials: List[dict]) -> dict:
    """Map original credential IDs to current ones"""
    # Build credential lookup by type and name
    cred_lookup = {}
    for cred in current_credentials:
        key = f"{cred['type']}:{cred.get('name', '')}"
        cred_lookup[key] = cred["id"]

    # Extract unique credential references from original
    original_cred_refs = {}
    for node in original_nodes:
        if "credentials" in node and node["credentials"]:
            for cred_type, cred_data in node["credentials"].items():
                if "id" in cred_data:
                    original_cred_refs[cred_type] = cred_data["id"]

    # Map to current credentials
    mapping = {}
    for cred_type, orig_id in original_cred_refs.items():
        # Find matching credential in current space
        for pattern_name, pattern in CREDENTIAL_PATTERNS.items():
            if pattern["type"] == cred_type:
                # Find by type and name pattern
                for key, cred_id in cred_lookup.items():
                    if key.startswith(f"{cred_type}:") and pattern["name_pattern"] in key:
                        mapping[cred_type] = cred_id
                        break

    return mapping


def restore_credentials_in_workflow(nodes: List[dict], cred_mapping: dict) -> List[dict]:
    """Restore credential references in workflow nodes"""
    updated_nodes = []
    for node in nodes:
        updated_node = node.copy()
        if "credentials" in node and node["credentials"]:
            updated_creds = {}
            for cred_type, cred_data in node["credentials"].items():
                if cred_type in cred_mapping:
                    updated_creds[cred_type] = {"id": cred_mapping[cred_type], "name": cred_data.get("name", "")}
                else:
                    updated_creds[cred_type] = cred_data
            updated_node["credentials"] = updated_creds
        updated_nodes.append(updated_node)
    return updated_nodes


def restore_space(space_url: str) -> dict:
    """Restore a single HF Space"""
    result = {
        "space": space_url,
        "status": "unknown",
        "workflows_restored": 0,
        "workflows_activated": 0,
        "errors": [],
    }

    try:
        client = N8nClient(space_url)

        # 1. Login
        if not client.login(LOGIN_EMAIL, LOGIN_PASSWORD):
            result["status"] = "login_failed"
            result["errors"].append("Failed to login")
            return result

        # 2. Get credentials
        credentials = client.get_credentials()
        print(f"[{space_url}] Found {len(credentials)} credentials")

        # 3. Get workflows
        workflows = client.get_workflows()
        print(f"[{space_url}] Found {len(workflows)} workflows")

        # 4. Process each workflow
        for wf_summary in workflows:
            wf_id = wf_summary["id"]
            wf_name = wf_summary["name"].lower()

            # Get full workflow
            try:
                current_wf = client.get_workflow(wf_id)
            except Exception as e:
                result["errors"].append(f"Failed to get workflow {wf_name}: {e}")
                continue

            # Find matching original workflow file
            original_wf = None
            for key, filename in WORKFLOW_FILES.items():
                if key in wf_name or filename.replace(".json", "") in wf_name:
                    original_wf = load_workflow_file(filename)
                    break

            if not original_wf:
                print(f"[{space_url}] No original file for workflow: {wf_name}")
                continue

            # Map credentials
            cred_mapping = map_credentials(original_wf["nodes"], credentials)
            if not cred_mapping:
                print(f"[{space_url}] No credential mapping for: {wf_name}")
                continue

            # Restore credentials in nodes
            updated_nodes = restore_credentials_in_workflow(current_wf["nodes"], cred_mapping)

            # Update workflow
            try:
                update_data = {
                    "nodes": updated_nodes,
                    "connections": current_wf.get("connections", {}),
                    "settings": current_wf.get("settings", {}),
                }
                client.update_workflow(wf_id, update_data)
                result["workflows_restored"] += 1
                print(f"[{space_url}] Restored credentials for: {wf_name}")

                # Re-activate if it was active
                if current_wf.get("active", False):
                    version_id = current_wf.get("versionId", "1")
                    client.activate_workflow(wf_id, version_id)
                    result["workflows_activated"] += 1
                    print(f"[{space_url}] Re-activated: {wf_name}")

            except Exception as e:
                result["errors"].append(f"Failed to update workflow {wf_name}: {e}")

        result["status"] = "success" if not result["errors"] else "partial"

    except Exception as e:
        result["status"] = "failed"
        result["errors"].append(f"Space-level error: {e}")

    return result


def main():
    """Main execution"""
    print(f"Starting restoration of {len(SPACES)} HF Spaces...")
    print(f"Workflow directory: {WORKFLOW_DIR}")
    print()

    results = []

    # Process spaces in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(restore_space, space): space for space in SPACES}

        for future in as_completed(futures):
            space = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"\n✓ Completed: {space}")
                print(f"  Status: {result['status']}")
                print(f"  Restored: {result['workflows_restored']} workflows")
                print(f"  Activated: {result['workflows_activated']} workflows")
                if result["errors"]:
                    print(f"  Errors: {len(result['errors'])}")
                    for err in result["errors"][:3]:
                        print(f"    - {err}")
            except Exception as e:
                print(f"\n✗ Failed: {space} - {e}")
                results.append({"space": space, "status": "exception", "errors": [str(e)]})

    # Summary
    print("\n" + "=" * 80)
    print("RESTORATION SUMMARY")
    print("=" * 80)

    total_restored = sum(r["workflows_restored"] for r in results)
    total_activated = sum(r["workflows_activated"] for r in results)
    success_count = sum(1 for r in results if r["status"] == "success")

    print(f"Spaces processed: {len(results)}/{len(SPACES)}")
    print(f"Successful: {success_count}")
    print(f"Total workflows restored: {total_restored}")
    print(f"Total workflows activated: {total_activated}")
    print()

    for result in results:
        status_icon = "✓" if result["status"] == "success" else ("⚠" if result["status"] == "partial" else "✗")
        print(f"{status_icon} {result['space']}: {result['status']} ({result['workflows_restored']} restored)")

    # Save detailed report
    report_path = "/home/termius/mon-ipad/logs/space-restoration-report.json"
    with open(report_path, "w") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_spaces": len(SPACES),
                "successful": success_count,
                "total_restored": total_restored,
                "total_activated": total_activated,
                "results": results,
            },
            f,
            indent=2,
        )

    print(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    main()
