#!/usr/bin/env python3
"""Test all 14 n8n webhooks on HF Space in parallel."""

import urllib.request
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple

BASE_URL = "https://lbjlincoln-nomos-rag-engine.hf.space"

# Define all webhooks to test
WEBHOOKS = [
    # RAG Pipelines (POST with query)
    {
        "name": "Standard RAG",
        "path": "/webhook/rag-multi-index-v3",
        "method": "POST",
        "body": {"query": "Quel est le chiffre d'affaires de Total en 2023?"}
    },
    {
        "name": "Graph RAG",
        "path": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "method": "POST",
        "body": {"query": "Quel est le chiffre d'affaires de Total en 2023?"}
    },
    {
        "name": "Quantitative RAG",
        "path": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "method": "POST",
        "body": {"query": "Quel est le chiffre d'affaires de Total en 2023?"}
    },
    {
        "name": "Orchestrator",
        "path": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
        "method": "POST",
        "body": {"query": "Quel est le chiffre d'affaires de Total en 2023?"}
    },

    # Support webhooks
    {
        "name": "Status Dashboard",
        "path": "/webhook/nomos-status",
        "method": "GET",
        "body": None
    },
    {
        "name": "Benchmark V2",
        "path": "/webhook/benchmark-v2",
        "method": "POST",
        "body": {"query": "test"}
    },
    {
        "name": "Benchmark SQL Exec",
        "path": "/webhook/benchmark-sql-exec",
        "method": "POST",
        "body": {"query": "SELECT 1"}
    },
    {
        "name": "Project Chatbot",
        "path": "/webhook/project-chatbot",
        "method": "POST",
        "body": {"query": "status du projet"}
    },
    {
        "name": "Benchmark Ingest",
        "path": "/webhook/benchmark-ingest",
        "method": "POST",
        "body": {"query": "test"}
    },
    {
        "name": "RAG V6 Ingestion",
        "path": "/webhook/rag-v6-ingestion",
        "method": "POST",
        "body": {"query": "test"}
    },
]


def test_webhook(webhook: Dict) -> Dict:
    """Test a single webhook and return results."""
    name = webhook["name"]
    url = BASE_URL + webhook["path"]
    method = webhook["method"]
    body = webhook["body"]

    result = {
        "name": name,
        "path": webhook["path"],
        "method": method,
        "status": None,
        "time": None,
        "response_preview": None,
        "error": None,
        "passed": False
    }

    try:
        start = time.time()

        if method == "GET":
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "Mozilla/5.0")
        else:  # POST
            data = json.dumps(body).encode('utf-8')
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "Mozilla/5.0")

        with urllib.request.urlopen(req, timeout=120) as response:
            elapsed = time.time() - start
            status = response.status
            response_text = response.read().decode('utf-8', errors='ignore')

            result["status"] = status
            result["time"] = elapsed
            result["response_preview"] = response_text[:200] if response_text else "(empty)"
            result["passed"] = (200 <= status < 300)

    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        result["status"] = e.code
        result["time"] = elapsed
        result["error"] = f"HTTP {e.code}: {e.reason}"
        try:
            error_body = e.read().decode('utf-8', errors='ignore')
            result["response_preview"] = error_body[:200]
        except:
            result["response_preview"] = "(could not read error body)"

    except urllib.error.URLError as e:
        elapsed = time.time() - start
        result["time"] = elapsed
        result["error"] = f"URL Error: {str(e.reason)}"

    except Exception as e:
        elapsed = time.time() - start
        result["time"] = elapsed
        result["error"] = f"Exception: {str(e)}"

    return result


def main():
    """Test all webhooks in parallel."""
    print(f"\n{'='*80}")
    print(f"Testing {len(WEBHOOKS)} webhooks on HF Space")
    print(f"Base URL: {BASE_URL}")
    print(f"{'='*80}\n")

    results = []

    # Test all webhooks in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(test_webhook, wh): wh for wh in WEBHOOKS}

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            # Print progress
            status_icon = "✓" if result["passed"] else "✗"
            status_str = f"{result['status']}" if result['status'] else "ERROR"
            time_str = f"{result['time']:.1f}s" if result['time'] is not None else "N/A"

            print(f"{status_icon} [{status_str:>3}] {time_str:>6} | {result['name']}")
            if result['error']:
                print(f"    Error: {result['error']}")

    # Print summary table
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")

    # Sort results by name for consistent display
    results.sort(key=lambda x: x['name'])

    # Print table header
    print(f"{'Status':<8} {'Time':<8} {'HTTP':<6} {'Name':<30} {'Preview'}")
    print(f"{'-'*80}")

    passed_count = 0
    failed_count = 0

    for r in results:
        status_icon = "PASS" if r["passed"] else "FAIL"
        status_str = str(r['status']) if r['status'] else "ERR"
        time_str = f"{r['time']:.1f}s" if r['time'] is not None else "N/A"
        preview = r['response_preview'] if r['response_preview'] else r['error']
        preview = preview[:40] + "..." if len(preview) > 40 else preview

        print(f"{status_icon:<8} {time_str:<8} {status_str:<6} {r['name']:<30} {preview}")

        if r["passed"]:
            passed_count += 1
        else:
            failed_count += 1

    print(f"\n{'='*80}")
    print(f"Results: {passed_count}/{len(WEBHOOKS)} PASSED, {failed_count}/{len(WEBHOOKS)} FAILED")
    print(f"{'='*80}\n")

    # Print detailed failures
    failures = [r for r in results if not r["passed"]]
    if failures:
        print("\nDETAILED FAILURES:\n")
        for r in failures:
            print(f"• {r['name']} ({r['method']} {r['path']})")
            print(f"  Status: {r['status']}")
            print(f"  Error: {r['error']}")
            if r['response_preview']:
                print(f"  Response: {r['response_preview']}")
            print()


if __name__ == "__main__":
    main()
