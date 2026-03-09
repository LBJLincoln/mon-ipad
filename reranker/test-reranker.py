#!/usr/bin/env python3
"""
Test script for the Nomos Self-Hosted Reranker API.

Usage:
  # Test local server (during development)
  python3 reranker/test-reranker.py --url http://localhost:7860

  # Test deployed HF Space
  python3 reranker/test-reranker.py --url https://lbjlincoln-nomos-reranker-api.hf.space

  # Quick local test without server (FlashRank directly)
  python3 reranker/test-reranker.py --local

  # Test with custom model
  python3 reranker/test-reranker.py --local --model medium
"""

import argparse
import json
import sys
import time
from urllib import request, error


# ── Test data ──────────────────────────────────────────────────────────────
TESTS = [
    {
        "name": "Basic geography",
        "query": "What is the capital of France?",
        "documents": [
            "Berlin is the capital of Germany and has a population of 3.6 million.",
            "Paris is the capital of France, known for the Eiffel Tower.",
            "Tokyo is the capital of Japan, a major financial center.",
            "The French Revolution began in 1789 in Paris.",
            "Madrid is the capital of Spain.",
            "France exports wine and cheese worldwide."
        ],
        "expected_top": 1,  # "Paris is the capital of France" should be #1
        "top_n": 3
    },
    {
        "name": "Financial RAG query",
        "query": "What is the revenue growth rate for Q3 2024?",
        "documents": [
            "The company reported record profits in 2023.",
            "Revenue grew 23% year-over-year in Q3 2024, reaching $4.2 billion.",
            "The CEO announced a new product line at the conference.",
            "Operating expenses decreased by 5% compared to Q2 2024.",
            "Q3 2024 saw strong momentum with 23.1% revenue growth driven by cloud services.",
            "The annual report will be published in February 2025."
        ],
        "expected_top": 1,  # Index 1 or 4 should rank highest
        "top_n": 3
    },
    {
        "name": "Legal/compliance query",
        "query": "What are the GDPR requirements for data retention?",
        "documents": [
            "GDPR Article 5(1)(e) requires data to be kept for no longer than necessary.",
            "The company uses AWS for cloud hosting.",
            "Data subjects have the right to erasure under GDPR Article 17.",
            "Annual compliance training is mandatory for all employees.",
            "Personal data must be stored with appropriate security measures per GDPR.",
            "The marketing team launched a new campaign last quarter."
        ],
        "expected_top": 0,  # GDPR Article 5 about retention should be #1
        "top_n": 3
    },
    {
        "name": "Empty edge case",
        "query": "test",
        "documents": ["only one document"],
        "expected_top": 0,
        "top_n": 1
    },
    {
        "name": "Many documents (stress test)",
        "query": "machine learning model training",
        "documents": [
            f"Document {i}: {'Machine learning models require large datasets for training.' if i == 7 else 'Unrelated content about cooking recipes.'}"
            for i in range(25)
        ],
        "expected_top": 7,
        "top_n": 5
    }
]


def test_via_api(base_url: str, tests: list) -> tuple:
    """Test via HTTP API (Jina-compatible /v1/rerank endpoint)."""
    passed = 0
    failed = 0
    endpoint = f"{base_url.rstrip('/')}/v1/rerank"

    print(f"\n{'='*60}")
    print(f"Testing API at: {endpoint}")
    print(f"{'='*60}\n")

    # Health check first
    try:
        health_url = f"{base_url.rstrip('/')}/health"
        req = request.Request(health_url)
        with request.urlopen(req, timeout=30) as resp:
            health = json.loads(resp.read())
            print(f"Health: {json.dumps(health, indent=2)}\n")
    except Exception as e:
        print(f"Health check failed: {e}")
        print("Server may not be running. Use --local for direct testing.\n")
        return 0, len(tests)

    for test in tests:
        name = test["name"]
        payload = {
            "query": test["query"],
            "documents": test["documents"],
            "top_n": test["top_n"]
        }

        t0 = time.time()
        try:
            data = json.dumps(payload).encode()
            req = request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
            with request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
        except error.HTTPError as e:
            err_body = e.read().decode()[:300]
            print(f"  FAIL {name}: HTTP {e.code} - {err_body}")
            failed += 1
            continue
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failed += 1
            continue

        elapsed = time.time() - t0

        if "error" in result:
            print(f"  FAIL {name}: {result['error']}")
            failed += 1
            continue

        results = result.get("results", [])
        if not results:
            print(f"  FAIL {name}: No results returned")
            failed += 1
            continue

        top_idx = results[0]["index"]
        top_score = results[0]["relevance_score"]
        expected = test["expected_top"]

        # For the financial test, accept index 1 or 4 (both mention Q3 2024 revenue growth)
        acceptable = {expected}
        if name == "Financial RAG query":
            acceptable = {1, 4}
        if name == "Many documents (stress test)":
            acceptable = {7}

        ok = top_idx in acceptable
        status = "PASS" if ok else "WARN"
        if ok:
            passed += 1
        else:
            failed += 1

        print(f"  {status} {name}")
        print(f"       Top result: idx={top_idx} score={top_score:.4f} ({elapsed*1000:.0f}ms)")
        if len(results) > 1:
            print(f"       Results: {[(r['index'], round(r['relevance_score'], 4)) for r in results]}")
        if not ok:
            print(f"       Expected top idx in {acceptable}, got {top_idx}")
        print()

    return passed, failed


def test_local(model: str = "small") -> tuple:
    """Test FlashRank directly without HTTP server."""
    passed = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"Testing FlashRank locally (model: {model})")
    print(f"{'='*60}\n")

    try:
        from flashrank import Ranker, RerankRequest
    except ImportError:
        print("FlashRank not installed. Install with: pip install flashrank")
        return 0, len(TESTS)

    print("Loading model...")
    t0 = time.time()

    # Map alias to FlashRank model name
    model_map = {
        "nano": "ms-marco-TinyBERT-L-2-v2",
        "small": "ms-marco-MiniLM-L-12-v2",
        "medium": "rank-T5-flan",
        "large": "ms-marco-MultiBERT-L-12",
    }
    flashrank_model = model_map.get(model, model)
    ranker = Ranker(model_name=flashrank_model)
    print(f"Model loaded in {time.time()-t0:.1f}s\n")

    for test in TESTS:
        name = test["name"]
        query = test["query"]
        docs = test["documents"]
        top_n = test["top_n"]

        # Tag passages with original index for tracking
        t0 = time.time()
        passages = [{"id": i, "text": d} for i, d in enumerate(docs)]
        rr = RerankRequest(query=query, passages=passages)
        results = ranker.rerank(rr)
        elapsed = time.time() - t0

        if not results:
            print(f"  FAIL {name}: No results")
            failed += 1
            continue

        # Build text->index lookup as fallback
        text_to_idx = {d: i for i, d in enumerate(docs)}

        # Extract top result
        top = results[0]
        top_text = top.get("text", "") if isinstance(top, dict) else getattr(top, "text", "")
        top_score = top.get("score", 0) if isinstance(top, dict) else getattr(top, "score", 0)
        raw_id = top.get("id", None) if isinstance(top, dict) else getattr(top, "id", None)

        # Resolve index: use id if valid int, otherwise text lookup
        if isinstance(raw_id, int) and 0 <= raw_id < len(docs):
            top_idx = raw_id
        else:
            top_idx = text_to_idx.get(top_text, -1)

        expected = test["expected_top"]

        acceptable = {expected}
        if name == "Financial RAG query":
            acceptable = {1, 4}

        ok = top_idx in acceptable
        status = "PASS" if ok else "WARN"
        if ok:
            passed += 1
        else:
            failed += 1

        # Show top_n results with resolved indices
        ranked = []
        for r in results[:top_n]:
            r_text = r.get("text", "") if isinstance(r, dict) else getattr(r, "text", "")
            r_score = r.get("score", 0) if isinstance(r, dict) else getattr(r, "score", 0)
            r_raw_id = r.get("id", None) if isinstance(r, dict) else getattr(r, "id", None)
            if isinstance(r_raw_id, int) and 0 <= r_raw_id < len(docs):
                r_idx = r_raw_id
            else:
                r_idx = text_to_idx.get(r_text, -1)
            ranked.append((r_idx, round(float(r_score), 4)))

        print(f"  {status} {name}")
        print(f"       Top: idx={top_idx} score={float(top_score):.4f} ({elapsed*1000:.0f}ms)")
        print(f"       Top-{top_n}: {ranked}")
        if not ok:
            print(f"       Expected top idx in {acceptable}, got {top_idx}")
        print()

    return passed, failed


def test_n8n_compatibility(base_url: str) -> bool:
    """
    Test that the endpoint works exactly like Jina reranker API
    (the format n8n workflows send).
    """
    print(f"\n{'='*60}")
    print("n8n Workflow Compatibility Test")
    print(f"{'='*60}\n")

    endpoint = f"{base_url.rstrip('/')}/v1/rerank"

    # This is exactly what the n8n "Cohere Reranker" node sends
    payload = {
        "model": "jina-reranker-v2-base-multilingual",
        "query": "What is the GDP growth rate?",
        "documents": [
            "GDP grew by 2.1% in 2024.",
            "The weather forecast shows rain.",
            "Economic indicators suggest moderate growth.",
            "The stock market closed higher."
        ],
        "top_n": 10
    }

    try:
        data = json.dumps(payload).encode()
        req = request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

    # Verify response format matches what n8n expects
    checks = []

    # Must have "results" array
    has_results = "results" in result and isinstance(result["results"], list)
    checks.append(("Has 'results' array", has_results))

    if has_results and len(result["results"]) > 0:
        first = result["results"][0]
        # Each result must have "index" and "relevance_score"
        has_index = "index" in first
        has_score = "relevance_score" in first
        checks.append(("Result has 'index'", has_index))
        checks.append(("Result has 'relevance_score'", has_score))
        checks.append(("Score is float", isinstance(first.get("relevance_score"), (int, float))))
        checks.append(("Index is int", isinstance(first.get("index"), int)))

    # Model name accepted (mapped to local model)
    has_model = "model" in result
    checks.append(("Accepts jina model name", has_model))

    # Self-hosted marker
    checks.append(("Self-hosted flag", result.get("_self_hosted", False)))
    checks.append(("Zero cost", result.get("_cost", -1) == 0.0))

    all_pass = True
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  {status} {check_name}")
        if not passed:
            all_pass = False

    print(f"\n  Response: {json.dumps(result, indent=2)}")
    return all_pass


def main():
    parser = argparse.ArgumentParser(description="Test Nomos Self-Hosted Reranker")
    parser.add_argument("--url", default="http://localhost:7860",
                        help="Base URL of the reranker API")
    parser.add_argument("--local", action="store_true",
                        help="Test FlashRank directly (no server needed)")
    parser.add_argument("--model", default="small",
                        choices=["nano", "small", "medium", "large"],
                        help="Model to use for local testing")
    parser.add_argument("--n8n", action="store_true",
                        help="Run n8n compatibility test only")
    args = parser.parse_args()

    if args.local:
        passed, failed = test_local(args.model)
    elif args.n8n:
        ok = test_n8n_compatibility(args.url)
        passed = 1 if ok else 0
        failed = 0 if ok else 1
    else:
        passed, failed = test_via_api(args.url, TESTS)

        # Also run n8n compatibility if API is up
        if passed > 0:
            n8n_ok = test_n8n_compatibility(args.url)
            if n8n_ok:
                passed += 1
            else:
                failed += 1

    total = passed + failed
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    if failed > 0:
        print(f"WARNING: {failed} test(s) failed or had unexpected rankings")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
