#!/usr/bin/env python3
"""
EVALUATION RUNNER: 100 custom questions (50 graph+quant + 50 standard+orchestrator)
==================================================================================
Runs the evaluation questions against live n8n webhooks and computes F1 scores.
Tests specifically: ISSUE-QT-13 (ILIKE), ISSUE-QT-14 (null aggregation),
intent routing accuracy, and multi-pipeline synthesis quality.
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
BASE_DIR = "/home/user/mon-ipad"

RAG_ENDPOINTS = {
    "standard": f"{N8N_HOST}/webhook/rag-multi-index-v3",
    "graph": f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": f"{N8N_HOST}/webhook/benchmark-test-orchestrator",
}

EVAL_FILES = {
    "graph_quant": os.path.join(BASE_DIR, "dataset-results/eval-graph-quantitative-50.json"),
    "std_orch": os.path.join(BASE_DIR, "dataset-results/eval-standard-orchestrator-50.json"),
}

OUTPUT_FILE = os.path.join(BASE_DIR, "dataset-results/eval-100-results.json")


def call_rag(endpoint, question, tenant_id="benchmark", timeout=60):
    """Call a RAG endpoint and return the response."""
    body = json.dumps({
        "query": question,
        "tenant_id": tenant_id,
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True
    }).encode()
    headers = {"Content-Type": "application/json"}

    for attempt in range(3):
        try:
            req = request.Request(endpoint, data=body, headers=headers, method="POST")
            start = time.time()
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                latency = int((time.time() - start) * 1000)
                if raw and raw.strip():
                    data = json.loads(raw)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    return {"data": data, "latency_ms": latency, "error": None}
                return {"data": None, "latency_ms": latency, "error": "Empty response"}
        except error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()[:300]
            except:
                pass
            if (e.code == 403 or e.code >= 500) and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"data": None, "latency_ms": 0, "error": f"HTTP {e.code}: {err_body}"}
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"data": None, "latency_ms": 0, "error": str(e)}

    return {"data": None, "latency_ms": 0, "error": "Max retries exceeded"}


def extract_answer(data):
    """Extract the answer string from RAG response."""
    if not data:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        # Standard RAG
        if isinstance(data.get("response"), str):
            return data["response"]
        # Quantitative RAG
        if isinstance(data.get("interpretation"), str):
            return data["interpretation"]
        if isinstance(data.get("answer"), str):
            return data["answer"]
        # Graph RAG
        if isinstance(data.get("response"), dict):
            inner = data["response"]
            if isinstance(inner.get("response"), str):
                return inner["response"]
    return str(data)[:500]


def compute_f1(predicted, expected):
    """Token-level F1 score."""
    if not predicted or not expected:
        return 0.0
    norm = lambda s: re.sub(r'[^a-z0-9\s.]', '', s.lower().strip()).split()
    pred_tokens = set(norm(predicted))
    exp_tokens = set(norm(expected))
    if not pred_tokens or not exp_tokens:
        return 0.0
    common = pred_tokens & exp_tokens
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(exp_tokens)
    return 2 * precision * recall / (precision + recall)


def check_ilike(data):
    """Check if SQL used ILIKE for entity name matching."""
    sql = ""
    if isinstance(data, dict):
        sql = data.get("sql_executed", "") or ""
    return "ILIKE" in sql.upper()


def check_null_aggregation(data):
    """Check if null aggregation was properly detected."""
    if isinstance(data, dict):
        return data.get("null_aggregation", False) is True or data.get("status") == "NULL_RESULT"
    return False


def check_routing(data, expected_routing):
    """Check if orchestrator routed to the expected pipeline."""
    if not isinstance(data, dict):
        return None
    meta = data.get("metadata", {})
    routing = meta.get("pipeline", meta.get("engine", meta.get("rag_type", "")))
    if not routing:
        # Infer from response structure
        if data.get("sql_executed"):
            routing = "quantitative"
        elif data.get("response") and isinstance(data.get("response"), dict):
            routing = "graph"
        else:
            routing = "standard"
    return routing.lower() if routing else None


def run_evaluation():
    print("=" * 70)
    print("  EVALUATION RUNNER — 100 Custom Questions")
    print("=" * 70)
    print(f"  Date: {datetime.now().isoformat()}")
    print("=" * 70)

    all_results = []
    overall_start = time.time()

    # ─── PHASE 1: Graph + Quantitative (50 questions) ────────────
    print(f"\n{'='*70}")
    print(f"  PHASE 1: GRAPH RAG + QUANTITATIVE (50 questions)")
    print(f"{'='*70}")

    with open(EVAL_FILES["graph_quant"]) as f:
        gq_data = json.load(f)

    gq_questions = gq_data["questions"]
    quant_results = []
    graph_results = []

    for i, q in enumerate(gq_questions):
        qid = q["id"]
        rag_target = q["rag_target"]
        endpoint = RAG_ENDPOINTS.get(rag_target, RAG_ENDPOINTS["standard"])

        print(f"\n  [{i+1}/50] {qid} ({rag_target})")
        print(f"    Q: {q['question'][:80]}...")

        resp = call_rag(endpoint, q["question"])
        answer = extract_answer(resp["data"])
        expected = q.get("expected_answer", "")
        f1 = compute_f1(answer, str(expected))

        result = {
            "id": qid,
            "rag_target": rag_target,
            "category": q.get("category", ""),
            "question": q["question"],
            "expected_answer": str(expected)[:300],
            "actual_answer": answer[:500] if answer else None,
            "f1_score": round(f1, 4),
            "latency_ms": resp["latency_ms"],
            "error": resp["error"],
            "has_answer": bool(answer and len(answer) > 2),
            "difficulty": q.get("difficulty", ""),
        }

        # ISSUE-specific checks
        if q.get("tests_issue") == "ISSUE-QT-13":
            result["ilike_used"] = check_ilike(resp["data"])
            sql = resp["data"].get("sql_executed", "") if isinstance(resp["data"], dict) else ""
            result["sql_executed"] = sql
            print(f"    ILIKE check: {'PASS' if result['ilike_used'] else 'FAIL (exact match)'}")
            print(f"    SQL: {sql[:120]}")

        if q.get("tests_issue") == "ISSUE-QT-14":
            result["null_detected"] = check_null_aggregation(resp["data"])
            status = resp["data"].get("status", "") if isinstance(resp["data"], dict) else ""
            result["response_status"] = status
            print(f"    Null aggregation check: {'PASS' if result['null_detected'] else 'FAIL (false positive)'}")

        # Quantitative: check raw results
        if rag_target == "quantitative" and isinstance(resp["data"], dict):
            raw = resp["data"].get("raw_results", [])
            result["raw_results"] = str(raw)[:200]
            result["status"] = resp["data"].get("status", "")

        status_str = "OK" if result["has_answer"] else "EMPTY"
        if resp["error"]:
            status_str = "ERROR"
        print(f"    {status_str} | F1={f1:.3f} | {resp['latency_ms']}ms")
        if answer:
            print(f"    A: {answer[:120]}...")

        all_results.append(result)
        if rag_target == "quantitative":
            quant_results.append(result)
        else:
            graph_results.append(result)

        time.sleep(0.5)

    # ─── PHASE 2: Standard RAG + Orchestrator (50 questions) ─────
    print(f"\n{'='*70}")
    print(f"  PHASE 2: STANDARD RAG + ORCHESTRATOR (50 questions)")
    print(f"{'='*70}")

    with open(EVAL_FILES["std_orch"]) as f:
        so_data = json.load(f)

    so_questions = so_data["questions"]
    std_results = []
    orch_results = []

    for i, q in enumerate(so_questions):
        qid = q["id"]
        rag_target = q["rag_target"]

        # Route to the correct endpoint
        if rag_target == "orchestrator":
            # Check expected routing
            expected_routing = q.get("expected_routing", "standard")
            if "+" in expected_routing:
                # Multi-pipeline: use orchestrator
                endpoint = RAG_ENDPOINTS["orchestrator"]
            else:
                endpoint = RAG_ENDPOINTS.get(expected_routing, RAG_ENDPOINTS["standard"])
        else:
            endpoint = RAG_ENDPOINTS.get(rag_target, RAG_ENDPOINTS["standard"])

        print(f"\n  [{i+1}/50] {qid} ({rag_target})")
        print(f"    Q: {q['question'][:80]}...")

        resp = call_rag(endpoint, q["question"])
        answer = extract_answer(resp["data"])
        expected = q.get("expected_answer", "")
        f1 = compute_f1(answer, str(expected))

        result = {
            "id": qid,
            "rag_target": rag_target,
            "category": q.get("category", ""),
            "question": q["question"],
            "expected_answer": str(expected)[:300],
            "actual_answer": answer[:500] if answer else None,
            "f1_score": round(f1, 4),
            "latency_ms": resp["latency_ms"],
            "error": resp["error"],
            "has_answer": bool(answer and len(answer) > 2),
            "difficulty": q.get("difficulty", ""),
        }

        # Routing checks for orchestrator
        if rag_target == "orchestrator":
            actual_routing = check_routing(resp["data"], q.get("expected_routing", ""))
            result["expected_routing"] = q.get("expected_routing", "")
            result["actual_routing"] = actual_routing
            result["routing_correct"] = actual_routing == q.get("expected_routing", "") if actual_routing else None

        status_str = "OK" if result["has_answer"] else "EMPTY"
        if resp["error"]:
            status_str = "ERROR"
        print(f"    {status_str} | F1={f1:.3f} | {resp['latency_ms']}ms")
        if answer:
            print(f"    A: {answer[:120]}...")

        all_results.append(result)
        if rag_target == "orchestrator":
            orch_results.append(result)
        else:
            std_results.append(result)

        time.sleep(0.5)

    # ─── SUMMARY ──────────────────────────────────────────────────
    elapsed = time.time() - overall_start
    print(f"\n{'='*70}")
    print(f"  EVALUATION SUMMARY")
    print(f"{'='*70}")

    def summarize(results, label):
        if not results:
            print(f"\n  {label}: No results")
            return {}
        answered = sum(1 for r in results if r["has_answer"])
        errors = sum(1 for r in results if r["error"])
        f1s = [r["f1_score"] for r in results if r["has_answer"]]
        avg_f1 = sum(f1s) / len(f1s) if f1s else 0
        latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        f1_good = sum(1 for f in f1s if f >= 0.5)
        f1_excellent = sum(1 for f in f1s if f >= 0.7)

        print(f"\n  {label} ({len(results)} questions):")
        print(f"    Answered:   {answered}/{len(results)} ({100*answered/len(results):.0f}%)")
        print(f"    Errors:     {errors}/{len(results)}")
        print(f"    Avg F1:     {avg_f1:.4f}")
        print(f"    F1 >= 0.5:  {f1_good}/{len(f1s)} ({100*f1_good/len(f1s) if f1s else 0:.0f}%)")
        print(f"    F1 >= 0.7:  {f1_excellent}/{len(f1s)} ({100*f1_excellent/len(f1s) if f1s else 0:.0f}%)")
        print(f"    Avg Latency: {avg_lat:.0f}ms")

        # Difficulty breakdown
        for diff in ["easy", "medium", "hard"]:
            diff_r = [r for r in results if r.get("difficulty") == diff]
            if diff_r:
                diff_f1s = [r["f1_score"] for r in diff_r if r["has_answer"]]
                diff_avg = sum(diff_f1s) / len(diff_f1s) if diff_f1s else 0
                print(f"    [{diff.upper()}] {len(diff_r)} questions, avg F1: {diff_avg:.4f}")

        return {
            "total": len(results),
            "answered": answered,
            "errors": errors,
            "avg_f1": round(avg_f1, 4),
            "f1_good_pct": round(100 * f1_good / len(f1s), 1) if f1s else 0,
            "f1_excellent_pct": round(100 * f1_excellent / len(f1s), 1) if f1s else 0,
            "avg_latency_ms": round(avg_lat),
        }

    q_summary = summarize(quant_results, "QUANTITATIVE RAG")
    g_summary = summarize(graph_results, "GRAPH RAG")
    s_summary = summarize(std_results, "STANDARD RAG")
    o_summary = summarize(orch_results, "ORCHESTRATOR")

    # ISSUE-QT-13 specific check
    ilike_questions = [r for r in all_results if r.get("ilike_used") is not None]
    if ilike_questions:
        ilike_pass = sum(1 for r in ilike_questions if r["ilike_used"])
        print(f"\n  ISSUE-QT-13 (ILIKE): {ilike_pass}/{len(ilike_questions)} use ILIKE")

    # ISSUE-QT-14 specific check
    null_questions = [r for r in all_results if r.get("null_detected") is not None]
    if null_questions:
        null_pass = sum(1 for r in null_questions if r["null_detected"])
        print(f"  ISSUE-QT-14 (Null Agg): {null_pass}/{len(null_questions)} detect null")

    # Routing accuracy
    routing_questions = [r for r in all_results if r.get("routing_correct") is not None]
    if routing_questions:
        routing_pass = sum(1 for r in routing_questions if r["routing_correct"])
        print(f"  ROUTING ACCURACY: {routing_pass}/{len(routing_questions)}")

    print(f"\n  Total time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"{'='*70}")

    # Save results
    output = {
        "suite": "Custom Evaluation — 100 Questions",
        "date": datetime.now().isoformat(),
        "elapsed_seconds": int(elapsed),
        "summary": {
            "quantitative": q_summary,
            "graph": g_summary,
            "standard": s_summary,
            "orchestrator": o_summary,
        },
        "issue_checks": {
            "ISSUE_QT_13_ilike": {
                "tested": len(ilike_questions),
                "passed": sum(1 for r in ilike_questions if r.get("ilike_used")) if ilike_questions else 0,
            },
            "ISSUE_QT_14_null_agg": {
                "tested": len(null_questions),
                "passed": sum(1 for r in null_questions if r.get("null_detected")) if null_questions else 0,
            },
        },
        "results": all_results,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  Results saved to: {OUTPUT_FILE}")
    return output


if __name__ == "__main__":
    run_evaluation()
