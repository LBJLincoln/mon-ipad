#!/usr/bin/env python3
"""
Quick Test — Smoke test RAG endpoints after workflow modifications.

Runs 3-5 known-good questions per pipeline and records results
in data.json quick_tests[]. Used for fast validation before full eval.

Usage:
  python quick-test.py                                    # All pipelines, 3 questions
  python quick-test.py --pipelines standard,graph         # Specific pipelines
  python quick-test.py --questions 5                      # 5 questions per pipeline
"""

import json
import os
import sys
import time
from datetime import datetime
from urllib import request, error
from importlib.machinery import SourceFileLoader

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
N8N_HOST = os.environ.get("N8N_HOST", "http://34.136.180.66:5678")

# Load writer
writer = SourceFileLoader("w", os.path.join(EVAL_DIR, "live-writer.py")).load_module()

RAG_ENDPOINTS = {
    "standard":     f"{N8N_HOST}/webhook/rag-multi-index-v3",
    "graph":        f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": f"{N8N_HOST}/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
}

# Known-good test questions (questions that should always pass)
SMOKE_QUESTIONS = {
    "standard": [
        {"query": "What is the capital of Japan?", "expected_contains": "Tokyo"},
        {"query": "Where is Normandy located?", "expected_contains": "France"},
        {"query": "Who painted the Mona Lisa?", "expected_contains": "Vinci"},
        {"query": "What is the largest ocean?", "expected_contains": "Pacific"},
        {"query": "What year did World War II end?", "expected_contains": "1945"},
    ],
    "graph": [
        {"query": "What did Marie Curie win Nobel Prizes for?", "expected_contains": "Physics"},
        {"query": "What did Alexander Fleming discover?", "expected_contains": "penicillin"},
        {"query": "Who founded Microsoft?", "expected_contains": "Gates"},
        {"query": "What is the WHO?", "expected_contains": "Health"},
        {"query": "What disease is caused by mosquitoes?", "expected_contains": "malaria"},
    ],
    "quantitative": [
        {"query": "What was TechVision Inc's total revenue in fiscal year 2023?", "expected_contains": ""},
        {"query": "What was GreenEnergy Corp's total revenue in 2023?", "expected_contains": ""},
        {"query": "What is the total number of products across all companies?", "expected_contains": ""},
        {"query": "What was HealthPlus Labs' net income in 2022?", "expected_contains": ""},
        {"query": "What was TechVision's revenue in Q1 2023?", "expected_contains": ""},
    ],
    "orchestrator": [
        {"query": "What is the capital of Japan?", "expected_contains": "Tokyo"},
        {"query": "What was TechVision Inc's total revenue in 2023?", "expected_contains": "6745"},
        {"query": "What did Marie Curie win Nobel Prizes for?", "expected_contains": "Physics"},
        {"query": "Who painted the Mona Lisa?", "expected_contains": "Vinci"},
        {"query": "What is the largest ocean?", "expected_contains": "Pacific"},
    ],
}


def normalize_for_match(text):
    """Normalize text for fuzzy matching — strip formatting from numbers etc."""
    import re
    # Remove commas from numbers (6,745 → 6745), dollar signs, percent signs
    normalized = re.sub(r'(\d),(\d)', r'\1\2', text)
    normalized = normalized.replace('$', '').replace('%', '')
    return normalized.lower()


def call_endpoint(endpoint, query, timeout=60):
    """Call a RAG endpoint and return response info."""
    payload = json.dumps({
        "query": query,
        "tenant_id": "benchmark",
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True,
    }).encode()
    headers = {"Content-Type": "application/json"}

    try:
        req = request.Request(endpoint, data=payload, headers=headers, method="POST")
        start = time.time()
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            latency = int((time.time() - start) * 1000)
            if raw and raw.strip():
                data = json.loads(raw)
                if isinstance(data, list):
                    data = data[0] if data else {}
                # Extract answer
                answer = ""
                for key in ["response", "answer", "result", "interpretation", "final_response"]:
                    if key in data and data[key]:
                        answer = str(data[key])
                        break
                return {"status": "ok", "latency_ms": latency, "answer": answer, "error": None}
            return {"status": "empty", "latency_ms": latency, "answer": "", "error": "Empty response"}
    except Exception as e:
        return {"status": "error", "latency_ms": 0, "answer": "", "error": str(e)[:200]}


def run_quick_tests(pipelines, max_questions=3, trigger="manual"):
    """Run quick smoke tests for specified pipelines."""
    results = {}

    for pipe in pipelines:
        endpoint = RAG_ENDPOINTS.get(pipe)
        questions = SMOKE_QUESTIONS.get(pipe, [])[:max_questions]
        if not endpoint or not questions:
            continue

        print(f"\n  Quick test: {pipe.upper()} ({len(questions)} questions)")
        pipe_results = []

        for i, q in enumerate(questions):
            # Use generous timeouts — LLM calls via free models can be slow
            pipe_timeout = 180 if pipe == "orchestrator" else 90
            resp = call_endpoint(endpoint, q["query"], timeout=pipe_timeout)
            expected = q.get("expected_contains", "")
            passed = False

            if resp["status"] == "ok" and resp["answer"]:
                if expected:
                    # Normalize both sides to handle number formatting (6,745 vs 6745)
                    norm_answer = normalize_for_match(resp["answer"])
                    norm_expected = normalize_for_match(expected)
                    if norm_expected in norm_answer:
                        passed = True
                elif not expected and len(resp["answer"]) > 10:
                    passed = True  # No expected = just check non-empty

            status = "pass" if passed else ("error" if resp["error"] else "fail")
            symbol = "[+]" if passed else "[-]"
            print(f"    {symbol} {q['query'][:60]} | {resp['latency_ms']}ms | {status}")
            if resp["error"]:
                print(f"        ERR: {resp['error'][:100]}")
            else:
                print(f"        A: {resp['answer'][:100]}")

            # Record to dashboard
            writer.record_quick_test(
                pipeline=pipe,
                query=q["query"],
                status=status,
                latency_ms=resp["latency_ms"],
                response_preview=resp["answer"][:200],
                trigger=trigger,
                error=resp["error"],
            )

            pipe_results.append({"query": q["query"], "status": status, "latency_ms": resp["latency_ms"]})

        pass_count = sum(1 for r in pipe_results if r["status"] == "pass")
        total = len(pipe_results)
        print(f"    Result: {pass_count}/{total} passed")
        results[pipe] = {"passed": pass_count, "total": total, "results": pipe_results}

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Quick endpoint smoke tests")
    parser.add_argument("--pipelines", type=str, default="standard,graph,quantitative,orchestrator")
    parser.add_argument("--questions", type=int, default=3)
    parser.add_argument("--trigger", type=str, default="manual")
    args = parser.parse_args()

    pipelines = [p.strip() for p in args.pipelines.split(",")]
    print("=" * 50)
    print("  QUICK ENDPOINT SMOKE TEST")
    print(f"  Pipelines: {', '.join(pipelines)}")
    print(f"  Questions per pipeline: {args.questions}")
    print("=" * 50)

    results = run_quick_tests(pipelines, max_questions=args.questions, trigger=args.trigger)

    print("\n" + "=" * 50)
    print("  SUMMARY")
    print("=" * 50)
    all_pass = True
    for pipe, info in results.items():
        status = "PASS" if info["passed"] == info["total"] else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  {pipe}: {info['passed']}/{info['total']} {status}")

    if not all_pass:
        print("\n  WARNING: Some endpoints are failing. Check before running full eval.")
        sys.exit(1)
    else:
        print("\n  All endpoints healthy.")


if __name__ == "__main__":
    main()
