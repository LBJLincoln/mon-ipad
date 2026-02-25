#!/usr/bin/env python3
"""
Activate all workflows across 8 HF Spaces in parallel.
Uses urllib with CookieJar to maintain session cookies.
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
import time

# Configuration
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

CREDENTIALS = {
    "emailOrLdapLoginId": "ci@nomos.ai",
    "password": "CI-Nomos-2026!"
}

WEBHOOK_PATHS = {
    "Standard": "/webhook/rag-multi-index-v3",
    "Graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "Quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "Orchestrator": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
}

TEST_QUESTION = {
    "question": "What is RAG?",
    "sector": "technology"
}


class N8nSpaceActivator:
    """Handles activation of workflows on a single HF Space."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.results = {
            "space": base_url,
            "login": False,
            "workflows_activated": [],
            "workflows_failed": [],
            "webhook_tests": {},
            "errors": []
        }

    def _request(self, method: str, path: str, data: dict = None, timeout: int = 30) -> Tuple[dict, int]:
        """Make HTTP request with cookie jar."""
        url = f"{self.base_url}{path}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if data is not None:
            request_data = json.dumps(data).encode('utf-8')
        else:
            request_data = None

        req = urllib.request.Request(url, data=request_data, headers=headers, method=method)

        try:
            response = self.opener.open(req, timeout=timeout)
            response_data = json.loads(response.read().decode('utf-8'))
            return response_data, response.status
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else "No error body"
            raise Exception(f"HTTP {e.code}: {error_body}")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")

    def login(self) -> bool:
        """Login to n8n instance."""
        try:
            response, status = self._request("POST", "/rest/login", CREDENTIALS)
            self.results["login"] = True
            return True
        except Exception as e:
            self.results["errors"].append(f"Login failed: {str(e)}")
            return False

    def list_workflows(self) -> List[dict]:
        """List all workflows."""
        try:
            workflows, status = self._request("GET", "/rest/workflows")
            return workflows.get("data", []) if isinstance(workflows, dict) else workflows
        except Exception as e:
            self.results["errors"].append(f"List workflows failed: {str(e)}")
            return []

    def activate_workflow(self, workflow_id: str, version_id: str, name: str) -> bool:
        """Activate a single workflow."""
        try:
            response, status = self._request(
                "POST",
                f"/rest/workflows/{workflow_id}/activate",
                {"versionId": version_id}
            )
            self.results["workflows_activated"].append({
                "id": workflow_id,
                "name": name,
                "versionId": version_id
            })
            return True
        except Exception as e:
            self.results["workflows_failed"].append({
                "id": workflow_id,
                "name": name,
                "error": str(e)
            })
            return False

    def test_webhook(self, path: str, name: str) -> bool:
        """Test a webhook endpoint."""
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        request_data = json.dumps(TEST_QUESTION).encode('utf-8')

        try:
            req = urllib.request.Request(url, data=request_data, headers=headers, method="POST")
            response = urllib.request.urlopen(req, timeout=30)
            status_code = response.status
            body = response.read().decode('utf-8')

            self.results["webhook_tests"][name] = {
                "success": 200 <= status_code < 300,
                "status": status_code,
                "has_body": len(body) > 0
            }
            return True
        except Exception as e:
            self.results["webhook_tests"][name] = {
                "success": False,
                "error": str(e)
            }
            return False

    def activate_all(self) -> dict:
        """Main activation flow."""
        print(f"\n{'='*80}")
        print(f"Processing: {self.base_url}")
        print(f"{'='*80}")

        # Step 1: Login
        print("  [1/4] Logging in...")
        if not self.login():
            print("  ❌ Login failed")
            return self.results
        print("  ✓ Login successful")

        # Step 2: List workflows
        print("  [2/4] Listing workflows...")
        workflows = self.list_workflows()
        if not workflows:
            print("  ⚠️  No workflows found")
            return self.results
        print(f"  ✓ Found {len(workflows)} workflows")

        # Step 3: Activate all workflows
        print("  [3/4] Activating workflows...")
        activated_count = 0
        for wf in workflows:
            wf_id = wf.get("id")
            wf_name = wf.get("name", "Unnamed")
            version_id = wf.get("versionId")

            if not wf_id or not version_id:
                print(f"    ⚠️  Skipping {wf_name} - missing ID or versionId")
                continue

            print(f"    Activating: {wf_name}...", end=" ")
            if self.activate_workflow(wf_id, version_id, wf_name):
                print("✓")
                activated_count += 1
            else:
                print("✗")

        print(f"  ✓ Activated {activated_count}/{len(workflows)} workflows")

        # Step 4: Test webhooks
        print("  [4/4] Testing webhooks...")
        for name, path in WEBHOOK_PATHS.items():
            print(f"    Testing {name}...", end=" ")
            self.test_webhook(path, name)
            result = self.results["webhook_tests"][name]
            if result.get("success"):
                print("✓")
            else:
                print(f"✗ ({result.get('error', 'Unknown error')})")

        return self.results


def activate_space(space_url: str) -> dict:
    """Activate all workflows on a single space."""
    activator = N8nSpaceActivator(space_url)
    return activator.activate_all()


def main():
    """Main execution."""
    print("\n" + "="*80)
    print("HF SPACES WORKFLOW ACTIVATOR")
    print("="*80)
    print(f"Total spaces to process: {len(SPACES)}")
    print(f"Credentials: {CREDENTIALS['emailOrLdapLoginId']}")
    print("="*80)

    start_time = time.time()
    all_results = []

    # Process all spaces in parallel
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_space = {executor.submit(activate_space, space): space for space in SPACES}

        for future in as_completed(future_to_space):
            space = future_to_space[future]
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                print(f"\n❌ ERROR processing {space}: {str(e)}")
                all_results.append({
                    "space": space,
                    "login": False,
                    "errors": [str(e)]
                })

    # Summary report
    elapsed = time.time() - start_time
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)

    successful_spaces = [r for r in all_results if r["login"]]
    failed_spaces = [r for r in all_results if not r["login"]]

    print(f"\nSpaces processed: {len(all_results)}")
    print(f"  ✓ Successful logins: {len(successful_spaces)}")
    print(f"  ✗ Failed logins: {len(failed_spaces)}")

    total_activated = sum(len(r["workflows_activated"]) for r in all_results)
    total_failed = sum(len(r["workflows_failed"]) for r in all_results)

    print(f"\nWorkflows:")
    print(f"  ✓ Activated: {total_activated}")
    print(f"  ✗ Failed: {total_failed}")

    print(f"\nWebhook tests by pipeline:")
    for pipeline in WEBHOOK_PATHS.keys():
        working = sum(1 for r in all_results if r.get("webhook_tests", {}).get(pipeline, {}).get("success"))
        total = len([r for r in all_results if pipeline in r.get("webhook_tests", {})])
        print(f"  {pipeline}: {working}/{total} working")

    print(f"\nTotal execution time: {elapsed:.1f}s")

    # Detailed failures
    if failed_spaces:
        print("\n" + "="*80)
        print("FAILED SPACES (detailed)")
        print("="*80)
        for result in failed_spaces:
            print(f"\n{result['space']}")
            for error in result.get("errors", []):
                print(f"  ❌ {error}")

    # Working spaces with webhook status
    if successful_spaces:
        print("\n" + "="*80)
        print("WORKING SPACES")
        print("="*80)
        for result in successful_spaces:
            print(f"\n{result['space']}")
            print(f"  Workflows activated: {len(result['workflows_activated'])}")

            webhook_tests = result.get("webhook_tests", {})
            if webhook_tests:
                print("  Webhooks:")
                for name, test_result in webhook_tests.items():
                    status = "✓" if test_result.get("success") else "✗"
                    print(f"    {status} {name}")

    # Save detailed results
    output_file = "/home/termius/mon-ipad/logs/spaces-activation-report.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_spaces": len(all_results),
            "successful_logins": len(successful_spaces),
            "total_workflows_activated": total_activated,
            "total_workflows_failed": total_failed,
            "execution_time_seconds": elapsed,
            "results": all_results
        }, f, indent=2)

    print(f"\n📄 Detailed report saved to: {output_file}")
    print("="*80 + "\n")

    return len(successful_spaces) == len(SPACES)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
