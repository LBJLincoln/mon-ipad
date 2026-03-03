#!/usr/bin/env python3
"""Test data-ingestion + enrichment workflows on HF Space.

Sends multiple test payloads to both webhooks and validates HTTP 200 + response content.

Usage:
  source .env.local
  python3 scripts/test-data-ingestion.py
"""
import json, os, sys, time, urllib.request, urllib.error

N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

INGESTION_URL = f"{N8N_HOST}/webhook/rag-v6-ingestion"
ENRICHMENT_URL = f"{N8N_HOST}/webhook/rag-v6-enrichment"

# Test payloads for ingestion
INGESTION_PAYLOADS = [
    {
        "name": "Short text document",
        "payload": {
            "filename": "test-short.txt",
            "documentId": "test-ing-001",
            "content": "Artificial intelligence is transforming healthcare through improved diagnostic accuracy and personalized treatment plans.",
            "source": "automated-test",
            "metadata": {"phase": "test", "type": "short"}
        }
    },
    {
        "name": "Medium technical document",
        "payload": {
            "filename": "test-medium.txt",
            "documentId": "test-ing-002",
            "content": """Graph neural networks (GNNs) have emerged as a powerful paradigm for learning on graph-structured data.
Unlike traditional neural networks that operate on grid-like data, GNNs can capture complex relationships
between entities in a graph. Recent advances include Graph Attention Networks (GAT), which use attention
mechanisms to weigh neighbor contributions, and GraphSAGE, which enables inductive learning on previously
unseen nodes. Applications span drug discovery, social network analysis, and recommendation systems.
The message-passing framework underpins most GNN architectures, where each node aggregates information
from its neighbors iteratively to build rich representations.""",
            "source": "automated-test",
            "metadata": {"phase": "test", "type": "technical", "domain": "ML"}
        }
    },
    {
        "name": "Financial document",
        "payload": {
            "filename": "test-financial.txt",
            "documentId": "test-ing-003",
            "content": """Q3 2024 Financial Results for TechCorp Inc. Revenue reached $4.2 billion, a 15% increase
year-over-year. Operating income was $890 million with an operating margin of 21.2%. The company
reported net income of $720 million, or $3.45 per diluted share. Free cash flow was $1.1 billion.
The board approved a quarterly dividend of $0.85 per share. Full-year guidance raised to $16.5-17.0B revenue.""",
            "source": "automated-test",
            "metadata": {"phase": "test", "type": "financial", "sector": "technology"}
        }
    },
]

# Test payloads for enrichment
ENRICHMENT_PAYLOADS = [
    {
        "name": "Basic enrichment",
        "payload": {
            "documentId": "test-enr-001",
            "content": "Machine learning algorithms can be categorized into supervised, unsupervised, and reinforcement learning. Each category has distinct training paradigms and use cases.",
            "entities": []
        }
    },
    {
        "name": "Enrichment with entities",
        "payload": {
            "documentId": "test-enr-002",
            "content": "Google DeepMind published a breakthrough paper on protein structure prediction using AlphaFold3. The model achieved unprecedented accuracy on CASP15 benchmarks.",
            "entities": [
                {"name": "Google DeepMind", "type": "organization"},
                {"name": "AlphaFold3", "type": "model"},
                {"name": "CASP15", "type": "benchmark"}
            ]
        }
    },
]


def send_request(url, payload, timeout=45):
    """Send POST request and return (status_code, response_body, elapsed_ms)."""
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "User-Agent": "NomosRAG-Test/1.0"
    })
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        elapsed = int((time.time() - start) * 1000)
        resp_body = resp.read().decode()
        return resp.status, resp_body, elapsed
    except urllib.error.HTTPError as e:
        elapsed = int((time.time() - start) * 1000)
        resp_body = e.read().decode() if e.fp else str(e)
        return e.code, resp_body, elapsed
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return 0, str(e), elapsed


def main():
    print("=" * 60)
    print("DATA-INGESTION WORKFLOW TESTS")
    print(f"Target: {N8N_HOST}")
    print("=" * 60)

    results = {"pass": 0, "fail": 0, "details": []}

    # Test Ingestion
    print(f"\n--- INGESTION WEBHOOK ({INGESTION_URL}) ---")
    for i, test in enumerate(INGESTION_PAYLOADS, 1):
        status, body, elapsed = send_request(INGESTION_URL, test["payload"])
        passed = 200 <= status < 300
        icon = "PASS" if passed else "FAIL"
        results["pass" if passed else "fail"] += 1
        results["details"].append({
            "workflow": "ingestion",
            "test": test["name"],
            "status": status,
            "elapsed_ms": elapsed,
            "passed": passed
        })

        print(f"  [{icon}] Test {i}: {test['name']}")
        print(f"         HTTP {status}, {elapsed}ms")
        if body:
            # Truncate long responses
            preview = body[:200] + "..." if len(body) > 200 else body
            print(f"         Response: {preview}")
        if not passed:
            print(f"         FULL: {body[:500]}")
        time.sleep(1)  # small delay between tests

    # Test Enrichment
    print(f"\n--- ENRICHMENT WEBHOOK ({ENRICHMENT_URL}) ---")
    for i, test in enumerate(ENRICHMENT_PAYLOADS, 1):
        status, body, elapsed = send_request(ENRICHMENT_URL, test["payload"])
        passed = 200 <= status < 300
        icon = "PASS" if passed else "FAIL"
        results["pass" if passed else "fail"] += 1
        results["details"].append({
            "workflow": "enrichment",
            "test": test["name"],
            "status": status,
            "elapsed_ms": elapsed,
            "passed": passed
        })

        print(f"  [{icon}] Test {i}: {test['name']}")
        print(f"         HTTP {status}, {elapsed}ms")
        if body:
            preview = body[:200] + "..." if len(body) > 200 else body
            print(f"         Response: {preview}")
        if not passed:
            print(f"         FULL: {body[:500]}")
        time.sleep(1)

    # Summary
    total = results["pass"] + results["fail"]
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {results['pass']}/{total} passed")
    if results["fail"] > 0:
        print("FAILED TESTS:")
        for d in results["details"]:
            if not d["passed"]:
                print(f"  - [{d['workflow']}] {d['test']}: HTTP {d['status']}")
    print(f"{'=' * 60}")

    # Save results
    with open("/tmp/data-ingestion-test-results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to /tmp/data-ingestion-test-results.json")

    sys.exit(0 if results["fail"] == 0 else 1)


if __name__ == "__main__":
    main()
