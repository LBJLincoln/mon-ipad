#!/usr/bin/env python3
"""
DIAGNOSTIC TEST: 10 questions per RAG type (30 total)
=====================================================
Tests the corrected workflow (fetch -> this.helpers.httpRequest) with a small
sample to validate the fix before re-running the full benchmark.

Tests 3 RAG types x 10 questions = 30 questions total.
Uses squad_v2 dataset as it has simple, verifiable Q&A pairs.

Usage:
  python3 run-diagnostic-30q.py
"""

import json
import os
import time
from datetime import datetime
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
WEBHOOK_PATH = "benchmark-test-rag"
BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
OUTPUT_FILE = os.path.join(BASE_DIR, "diagnostic-30q-results.json")

RAG_TYPES = ["standard", "graph", "quantitative"]
DATASET = "squad_v2"
SAMPLE_SIZE = 10
TEST_TYPE = "e2e"
TIMEOUT = 120


def webhook_call(payload, timeout=120):
    """Call n8n benchmark webhook with retry."""
    url = f"{N8N_HOST}/webhook/{WEBHOOK_PATH}"
    headers = {"Content-Type": "application/json"}

    for attempt in range(4):
        body = json.dumps(payload).encode()
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                if not raw or raw.strip() == "":
                    return {"status": resp.status, "data": None,
                            "error": f"Empty response (HTTP {resp.status})"}
                try:
                    return {"status": resp.status, "data": json.loads(raw), "error": None}
                except json.JSONDecodeError:
                    return {"status": resp.status, "data": raw, "error": None}
        except error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()
            except:
                pass
            if (e.code == 403 or e.code >= 500) and attempt < 3:
                wait = 2 ** (attempt + 1)
                print(f"  [RETRY] HTTP {e.code}, wait {wait}s...")
                time.sleep(wait)
                continue
            return {"status": e.code, "data": None, "error": f"HTTP {e.code}: {err_body[:500]}"}
        except Exception as e:
            if attempt < 3:
                wait = 2 ** (attempt + 1)
                print(f"  [RETRY] {e}, wait {wait}s...")
                time.sleep(wait)
                continue
            return {"status": 0, "data": None, "error": str(e)}

    return {"status": 0, "data": None, "error": "Max retries exceeded"}


def fetch_results_from_supabase(run_id):
    """Fetch the actual stored results from Supabase for a given run_id."""
    sql = f"""SELECT json_agg(row_to_json(t))::text as data FROM (
        SELECT run_id, dataset_name, item_index, question, expected_answer,
               actual_answer, metrics, latency_ms, error
        FROM benchmark_results
        WHERE run_id = '{run_id}'
        ORDER BY item_index
        LIMIT 20
    ) t"""

    url = f"{N8N_HOST}/webhook/benchmark-sql-exec"
    body = json.dumps({"sql": sql}).encode()
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            data = json.loads(raw)
            if isinstance(data, dict) and "data" in data:
                data_str = data["data"]
                if data_str and data_str != "null":
                    return json.loads(data_str)
    except Exception as e:
        print(f"  [WARN] Could not fetch results: {e}")

    return []


if __name__ == "__main__":
    print("=" * 60)
    print("  DIAGNOSTIC TEST: 10 questions x 3 RAG types")
    print("=" * 60)
    print(f"  Dataset:    {DATASET}")
    print(f"  Sample:     {SAMPLE_SIZE} per RAG type")
    print(f"  RAG types:  {', '.join(RAG_TYPES)}")
    print(f"  Test type:  {TEST_TYPE}")
    print(f"  Total:      {SAMPLE_SIZE * len(RAG_TYPES)} questions")
    print("=" * 60)

    all_results = []
    overall_start = time.time()

    for rag_type in RAG_TYPES:
        print(f"\n--- Testing {rag_type} RAG ({SAMPLE_SIZE} questions) ---")

        payload = {
            "dataset_name": DATASET,
            "test_type": TEST_TYPE,
            "rag_target": rag_type,
            "sample_size": SAMPLE_SIZE,
            "batch_size": SAMPLE_SIZE,
            "tenant_id": "benchmark",
        }

        t0 = time.time()
        resp = webhook_call(payload, timeout=TIMEOUT)
        elapsed = time.time() - t0

        result = {
            "rag_type": rag_type,
            "dataset": DATASET,
            "sample_size": SAMPLE_SIZE,
            "webhook_status": resp.get("status"),
            "webhook_error": resp.get("error"),
            "webhook_latency_s": round(elapsed, 1),
            "timestamp": datetime.now().isoformat(),
            "run_id": None,
            "qa_results": [],
        }

        if resp.get("error"):
            print(f"  WEBHOOK ERROR: {resp['error'][:200]}")
        else:
            data = resp.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            run_id = data.get("run_id", "") if isinstance(data, dict) else ""
            result["run_id"] = run_id
            result["webhook_response"] = data if isinstance(data, dict) else str(data)[:500]

            print(f"  Webhook OK ({elapsed:.1f}s) — run_id: {run_id}")
            print(f"  Response: {json.dumps(data, indent=2)[:500] if isinstance(data, dict) else str(data)[:500]}")

            # Fetch detailed results from Supabase
            if run_id:
                print(f"  Fetching detailed Q&A results from Supabase...")
                time.sleep(3)  # Wait for results to be stored
                qa_results = fetch_results_from_supabase(run_id)
                result["qa_results"] = qa_results

                if qa_results:
                    print(f"  Got {len(qa_results)} Q&A results:")
                    has_answer = sum(1 for r in qa_results if r.get("actual_answer"))
                    has_error = sum(1 for r in qa_results if r.get("error"))
                    print(f"    With answers:  {has_answer}/{len(qa_results)}")
                    print(f"    With errors:   {has_error}/{len(qa_results)}")

                    # Show first 3 results
                    for i, r in enumerate(qa_results[:3]):
                        print(f"\n    Q{i+1}: {r.get('question', '?')[:80]}")
                        print(f"    Expected: {str(r.get('expected_answer', ''))[:80]}")
                        print(f"    Actual:   {str(r.get('actual_answer', ''))[:80]}")
                        print(f"    Error:    {r.get('error', 'None')}")
                        print(f"    Metrics:  {r.get('metrics', {})}")
                else:
                    print(f"  No Q&A results found in Supabase for {run_id}")

        all_results.append(result)

        # Wait between RAG types
        if rag_type != RAG_TYPES[-1]:
            print(f"\n  Waiting 5s before next RAG type...")
            time.sleep(5)

    # Summary
    total_elapsed = time.time() - overall_start
    total_answers = sum(
        sum(1 for r in res.get("qa_results", []) if r.get("actual_answer"))
        for res in all_results
    )
    total_errors = sum(
        sum(1 for r in res.get("qa_results", []) if r.get("error"))
        for res in all_results
    )
    total_qa = sum(len(res.get("qa_results", [])) for res in all_results)

    report = {
        "test": "Diagnostic 30Q — fetch() fix validation",
        "started_at": datetime.fromtimestamp(overall_start).isoformat(),
        "completed_at": datetime.now().isoformat(),
        "total_elapsed_s": round(total_elapsed, 1),
        "config": {
            "dataset": DATASET,
            "sample_per_rag": SAMPLE_SIZE,
            "rag_types": RAG_TYPES,
            "test_type": TEST_TYPE,
        },
        "summary": {
            "total_qa_results": total_qa,
            "with_answers": total_answers,
            "with_errors": total_errors,
            "fix_validated": total_answers > 0 and total_errors == 0,
        },
        "results_per_rag": all_results,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print("\n" + "=" * 60)
    print("  DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"  Total Q&A results: {total_qa}")
    print(f"  With answers:      {total_answers}")
    print(f"  With errors:       {total_errors}")
    print(f"  Fix validated:     {'YES' if total_answers > 0 and total_errors == 0 else 'NO'}")
    print(f"  Duration:          {total_elapsed:.1f}s")
    print(f"  Saved to:          {OUTPUT_FILE}")
    print("=" * 60)
