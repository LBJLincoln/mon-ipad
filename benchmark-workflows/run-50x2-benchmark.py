#!/usr/bin/env python3
"""
Benchmark Runner — 50 Graph RAG + 50 Quantitative RAG questions
================================================================
Sends questions matched to actual seeded data (Neo4j entities + Supabase financials)
to the live n8n webhooks, evaluates responses, and saves results.

Usage:
  python3 run-50x2-benchmark.py [--timeout 180] [--delay 2]
"""

import json
import os
import re
import sys
import time
import subprocess
from datetime import datetime
from urllib import request, error

# ─── Configuration ───────────────────────────────────────────────
N8N_HOST = "https://amoret.app.n8n.cloud"
GRAPH_RAG_WEBHOOK = f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717"
QUANT_RAG_WEBHOOK = f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9"
TENANT_ID = "benchmark"

BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
REPO_DIR = "/home/user/mon-ipad"
QUESTIONS_FILE = os.path.join(BASE_DIR, "benchmark-50x2-questions.json")
RESULTS_FILE = os.path.join(BASE_DIR, "benchmark-50x2-results.json")
GIT_BRANCH = "claude/verify-sql-results-nuklI"

import argparse
parser = argparse.ArgumentParser(description="Run 50×2 RAG benchmark")
parser.add_argument("--timeout", type=int, default=180, help="Webhook timeout seconds")
parser.add_argument("--delay", type=float, default=2.0, help="Delay between questions (seconds)")
parser.add_argument("--max-questions", type=int, default=100, help="Max questions to process")
parser.add_argument("--rag-type", default="both", choices=["graph", "quantitative", "both"])
parser.add_argument("--dry-run", action="store_true", help="Validate only, don't send")
args = parser.parse_args()


# ─── Helpers ─────────────────────────────────────────────────────

def call_webhook(url, payload, timeout=180):
    """Call n8n webhook with retry and exponential backoff."""
    headers = {"Content-Type": "application/json"}
    for attempt in range(4):
        body = json.dumps(payload).encode()
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                if not raw or not raw.strip():
                    return {"error": f"Empty response (HTTP {resp.status})", "data": None}
                try:
                    return {"error": None, "data": json.loads(raw)}
                except json.JSONDecodeError:
                    return {"error": None, "data": raw}
        except error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()[:500]
            except:
                pass
            if (e.code == 403 or e.code >= 500) and attempt < 3:
                wait = 2 ** (attempt + 1)
                print(f"      [RETRY] HTTP {e.code}, waiting {wait}s (attempt {attempt+1}/4)...")
                time.sleep(wait)
                continue
            return {"error": f"HTTP {e.code}: {err_body}", "data": None}
        except Exception as e:
            if attempt < 3:
                wait = 2 ** (attempt + 1)
                print(f"      [RETRY] {str(e)[:80]}, waiting {wait}s...")
                time.sleep(wait)
                continue
            return {"error": str(e), "data": None}
    return {"error": "Max retries exceeded", "data": None}


def normalize(text):
    """Normalize text for comparison."""
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r'[^a-z0-9\s\.]', '', text)
    return text


def compute_f1(predicted, expected):
    """Token-level F1 score."""
    pred_tokens = set(normalize(predicted).split())
    exp_tokens = set(normalize(expected).split())
    if not pred_tokens or not exp_tokens:
        return 0.0
    common = pred_tokens & exp_tokens
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(exp_tokens)
    return 2 * precision * recall / (precision + recall)


def extract_number(text):
    """Extract the primary financial number from a text string.
    Prefers the largest number to avoid extracting years (2023) instead of amounts.
    """
    if not text:
        return None
    text = str(text)
    # Remove currency symbols and commas
    clean = re.sub(r'[$€£]', '', text)
    clean = re.sub(r'(\d),(\d)', r'\1\2', clean)  # remove commas in numbers
    # Find ALL numbers
    matches = re.findall(r'-?\d+\.?\d*', clean)
    if not matches:
        return None
    # Parse all numbers
    numbers = []
    for m in matches:
        try:
            numbers.append(float(m))
        except ValueError:
            continue
    if not numbers:
        return None
    # If only one number, return it
    if len(numbers) == 1:
        return numbers[0]
    # Filter out likely years (2019-2030)
    non_years = [n for n in numbers if not (2019 <= n <= 2030)]
    if non_years:
        # Return the largest absolute value (financial amounts are typically larger than years)
        return max(non_years, key=abs)
    # Fallback: return the first number
    match = re.search(r'-?\d+\.?\d*', clean)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def evaluate_quantitative(actual_answer, expected_answer, raw_results):
    """Evaluate a quantitative RAG response."""
    result = {
        "has_answer": bool(actual_answer and str(actual_answer).strip()),
        "answer_correct": False,
        "numeric_match": False,
        "null_result": False,
        "f1": 0.0,
        "notes": []
    }

    # Check for null results
    if raw_results:
        all_nulls = all(
            all(v is None for v in row.values()) if isinstance(row, dict) else row is None
            for row in raw_results
        )
        if all_nulls:
            result["null_result"] = True
            result["notes"].append("NULL_AGGREGATION: All results are null")
            return result

    if not result["has_answer"]:
        result["notes"].append("NO_ANSWER: Empty response")
        return result

    # F1 score
    result["f1"] = compute_f1(str(actual_answer), str(expected_answer))

    # Numeric comparison
    actual_num = extract_number(str(actual_answer))
    expected_num = extract_number(str(expected_answer))

    if actual_num is not None and expected_num is not None and expected_num != 0:
        tolerance = 0.05  # 5% tolerance
        ratio = actual_num / expected_num if expected_num != 0 else float('inf')
        if 1 - tolerance <= ratio <= 1 + tolerance:
            result["numeric_match"] = True
            result["answer_correct"] = True
            result["notes"].append(f"NUMERIC_MATCH: {actual_num} ≈ {expected_num}")
        else:
            result["notes"].append(f"NUMERIC_MISMATCH: got {actual_num}, expected {expected_num}")
    else:
        # Text-based evaluation
        if result["f1"] >= 0.5:
            result["answer_correct"] = True
            result["notes"].append(f"TEXT_MATCH: F1={result['f1']:.3f}")
        else:
            # Check if expected answer appears in actual
            exp_norm = normalize(expected_answer)
            act_norm = normalize(actual_answer)
            if exp_norm and exp_norm in act_norm:
                result["answer_correct"] = True
                result["notes"].append("SUBSTRING_MATCH")

    return result


def evaluate_graph(actual_answer, expected_answer):
    """Evaluate a Graph RAG response."""
    result = {
        "has_answer": bool(actual_answer and str(actual_answer).strip()),
        "answer_correct": False,
        "key_entities_found": [],
        "key_entities_missing": [],
        "f1": 0.0,
        "notes": []
    }

    if not result["has_answer"]:
        result["notes"].append("NO_ANSWER: Empty response")
        return result

    # F1 score
    result["f1"] = compute_f1(str(actual_answer), str(expected_answer))

    # Check for key entities from expected answer
    answer_norm = normalize(actual_answer)
    expected_entities = [e.strip() for e in str(expected_answer).split(",")]

    for entity in expected_entities:
        entity_norm = normalize(entity)
        # Check each significant word
        words = [w for w in entity_norm.split() if len(w) > 2]
        if words and all(w in answer_norm for w in words):
            result["key_entities_found"].append(entity.strip())
        else:
            result["key_entities_missing"].append(entity.strip())

    # Determine correctness
    total_expected = len(expected_entities)
    found = len(result["key_entities_found"])

    if total_expected > 0 and found / total_expected >= 0.5:
        result["answer_correct"] = True
        result["notes"].append(f"ENTITY_MATCH: {found}/{total_expected} entities found")
    elif result["f1"] >= 0.3:
        result["answer_correct"] = True
        result["notes"].append(f"F1_MATCH: F1={result['f1']:.3f}")
    else:
        result["notes"].append(f"PARTIAL: {found}/{total_expected} entities, F1={result['f1']:.3f}")

    return result


def save_results(all_results, summary, status="running"):
    """Save results to JSON file."""
    output = {
        "suite": "Benchmark 50×2 — Graph RAG + Quantitative RAG",
        "status": status,
        "started_at": start_time.isoformat(),
        "updated_at": datetime.now().isoformat(),
        "config": {
            "timeout": args.timeout,
            "delay": args.delay,
            "rag_type": args.rag_type,
            "graph_webhook": GRAPH_RAG_WEBHOOK,
            "quant_webhook": QUANT_RAG_WEBHOOK,
            "tenant_id": TENANT_ID
        },
        "summary": summary,
        "results": all_results
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def git_push(message):
    """Commit and push results."""
    try:
        subprocess.run(
            ["git", "add",
             "benchmark-workflows/benchmark-50x2-results.json",
             "benchmark-workflows/benchmark-50x2-questions.json",
             "benchmark-workflows/verify-sql-results.md",
             "modified-workflows/"],
            cwd=REPO_DIR, capture_output=True, timeout=30
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_DIR, capture_output=True, timeout=30
        )
        for attempt in range(4):
            result = subprocess.run(
                ["git", "push", "-u", "origin", GIT_BRANCH],
                cwd=REPO_DIR, capture_output=True, timeout=60
            )
            if result.returncode == 0:
                print(f"  [GIT] Push successful")
                return True
            wait = 2 ** (attempt + 1)
            print(f"  [GIT] Push failed, retrying in {wait}s...")
            time.sleep(wait)
        return False
    except Exception as e:
        print(f"  [GIT] Error: {e}")
        return False


# ─── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    start_time = datetime.now()

    print("=" * 70)
    print("  BENCHMARK 50×2 — Graph RAG + Quantitative RAG Evaluation")
    print(f"  Started: {start_time.isoformat()}")
    print("=" * 70)

    # Load questions
    with open(QUESTIONS_FILE) as f:
        data = json.load(f)
    all_questions = data["questions"]

    # Filter by RAG type
    if args.rag_type == "graph":
        questions = [q for q in all_questions if q["rag_target"] == "graph"]
    elif args.rag_type == "quantitative":
        questions = [q for q in all_questions if q["rag_target"] == "quantitative"]
    else:
        questions = all_questions

    questions = questions[:args.max_questions]

    # Count by type
    graph_count = sum(1 for q in questions if q["rag_target"] == "graph")
    quant_count = sum(1 for q in questions if q["rag_target"] == "quantitative")
    print(f"  Total questions: {len(questions)}")
    print(f"  Graph RAG:       {graph_count}")
    print(f"  Quantitative:    {quant_count}")
    print(f"  Timeout:         {args.timeout}s")
    print(f"  Delay:           {args.delay}s")
    print("=" * 70)

    if args.dry_run:
        print("\n  [DRY RUN] Validation complete.")
        sys.exit(0)

    # Process questions
    all_results = []
    graph_results = []
    quant_results = []

    for i, q in enumerate(questions):
        q_id = q["id"]
        rag_type = q["rag_target"]
        question = q["question"]
        expected = q.get("expected_answer", "")

        print(f"\n  [{i+1}/{len(questions)}] {q_id} ({rag_type})")
        print(f"    Q: {question[:100]}...")

        # Select webhook
        if rag_type == "graph":
            webhook = GRAPH_RAG_WEBHOOK
        else:
            webhook = QUANT_RAG_WEBHOOK

        # Build payload
        payload = {
            "query": question,
            "tenant_id": TENANT_ID,
            "include_sources": True,
            "benchmark_mode": True
        }

        # Call webhook
        t0 = time.time()
        response = call_webhook(webhook, payload, timeout=args.timeout)
        latency_ms = int((time.time() - t0) * 1000)

        # Extract answer
        actual_answer = ""
        raw_results = []
        resp_status = "ERROR"
        sql_executed = ""
        validation_status = ""

        if response["error"]:
            actual_answer = ""
            print(f"    ERROR: {response['error'][:100]}")
        elif response["data"]:
            resp_data = response["data"]
            if isinstance(resp_data, list):
                resp_data = resp_data[0] if resp_data else {}
            if isinstance(resp_data, dict):
                # Graph RAG response format
                actual_answer = resp_data.get("response", "")
                if not actual_answer:
                    # Quantitative RAG response format
                    actual_answer = resp_data.get("interpretation", "")
                resp_status = resp_data.get("status", "UNKNOWN")
                raw_results = resp_data.get("raw_results", [])
                sql_executed = resp_data.get("sql_executed", "")
                validation_status = resp_data.get("metadata", {}).get("validation_status", "")

        # Evaluate
        if rag_type == "quantitative":
            evaluation = evaluate_quantitative(actual_answer, expected, raw_results)
        else:
            evaluation = evaluate_graph(actual_answer, expected)

        # Build result
        result = {
            "id": q_id,
            "rag_type": rag_type,
            "question": question,
            "expected_answer": expected,
            "expected_detail": q.get("expected_detail", ""),
            "actual_answer": str(actual_answer)[:1000],
            "response_status": resp_status,
            "sql_executed": sql_executed,
            "validation_status": validation_status,
            "raw_results": raw_results[:5] if raw_results else [],
            "latency_ms": latency_ms,
            "evaluation": evaluation,
            "error": response["error"],
            "category": q.get("category", ""),
            "timestamp": datetime.now().isoformat()
        }

        all_results.append(result)
        if rag_type == "graph":
            graph_results.append(result)
        else:
            quant_results.append(result)

        # Print result
        status_icon = "+" if evaluation["answer_correct"] else "-"
        if evaluation.get("null_result"):
            status_icon = "!"
        f1 = evaluation.get("f1", 0)
        print(f"    [{status_icon}] F1={f1:.3f} | {latency_ms}ms | {', '.join(evaluation.get('notes', []))}")
        if actual_answer:
            print(f"    A: {str(actual_answer)[:120]}...")

        # Save intermediate results every 10 questions
        if (i + 1) % 10 == 0:
            g_correct = sum(1 for r in graph_results if r["evaluation"]["answer_correct"])
            q_correct = sum(1 for r in quant_results if r["evaluation"]["answer_correct"])
            g_total = len(graph_results) or 1
            q_total = len(quant_results) or 1
            interim_summary = {
                "processed": i + 1,
                "graph": {"total": len(graph_results), "correct": g_correct, "accuracy": f"{g_correct/g_total*100:.1f}%"},
                "quantitative": {"total": len(quant_results), "correct": q_correct, "accuracy": f"{q_correct/q_total*100:.1f}%"}
            }
            save_results(all_results, interim_summary)
            print(f"\n  --- Checkpoint @ {i+1}: Graph {g_correct}/{g_total} | Quant {q_correct}/{q_total} ---\n")

        # Delay between questions
        if i < len(questions) - 1:
            time.sleep(args.delay)

    # ─── Final Summary ───────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()

    def compute_summary(results, label):
        if not results:
            return {"total": 0, "correct": 0, "accuracy": "N/A"}
        correct = sum(1 for r in results if r["evaluation"]["answer_correct"])
        has_answer = sum(1 for r in results if r["evaluation"]["has_answer"])
        null_results = sum(1 for r in results if r["evaluation"].get("null_result", False))
        f1_scores = [r["evaluation"]["f1"] for r in results]
        latencies = [r["latency_ms"] for r in results]
        errors = sum(1 for r in results if r["error"])

        return {
            "total": len(results),
            "correct": correct,
            "accuracy": f"{correct/len(results)*100:.1f}%",
            "has_answer": has_answer,
            "answer_rate": f"{has_answer/len(results)*100:.1f}%",
            "null_results": null_results,
            "errors": errors,
            "avg_f1": round(sum(f1_scores) / len(f1_scores), 4) if f1_scores else 0,
            "max_f1": round(max(f1_scores), 4) if f1_scores else 0,
            "min_f1": round(min(f1_scores), 4) if f1_scores else 0,
            "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
            "p95_latency_ms": int(sorted(latencies)[int(len(latencies) * 0.95)]) if latencies else 0,
        }

    graph_summary = compute_summary(graph_results, "graph")
    quant_summary = compute_summary(quant_results, "quantitative")
    overall_correct = graph_summary["correct"] + quant_summary["correct"]
    overall_total = graph_summary["total"] + quant_summary["total"]

    final_summary = {
        "status": "completed",
        "elapsed_seconds": int(elapsed),
        "total_questions": overall_total,
        "total_correct": overall_correct,
        "overall_accuracy": f"{overall_correct/overall_total*100:.1f}%" if overall_total > 0 else "N/A",
        "graph_rag": graph_summary,
        "quantitative_rag": quant_summary,
    }

    # Print final report
    print(f"\n{'='*70}")
    print(f"  FINAL RESULTS")
    print(f"{'='*70}")
    print(f"  Elapsed:          {int(elapsed)}s")
    print(f"  Overall:          {overall_correct}/{overall_total} ({final_summary['overall_accuracy']})")
    print(f"")
    print(f"  GRAPH RAG ({graph_summary['total']} questions):")
    print(f"    Correct:        {graph_summary['correct']} ({graph_summary['accuracy']})")
    print(f"    With answer:    {graph_summary['has_answer']} ({graph_summary['answer_rate']})")
    print(f"    Avg F1:         {graph_summary['avg_f1']}")
    print(f"    Avg latency:    {graph_summary['avg_latency_ms']}ms")
    print(f"    Errors:         {graph_summary['errors']}")
    print(f"")
    print(f"  QUANTITATIVE RAG ({quant_summary['total']} questions):")
    print(f"    Correct:        {quant_summary['correct']} ({quant_summary['accuracy']})")
    print(f"    With answer:    {quant_summary['has_answer']} ({quant_summary['answer_rate']})")
    print(f"    Null results:   {quant_summary['null_results']}")
    print(f"    Avg F1:         {quant_summary['avg_f1']}")
    print(f"    Avg latency:    {quant_summary['avg_latency_ms']}ms")
    print(f"    Errors:         {quant_summary['errors']}")
    print(f"{'='*70}")

    # Category breakdown
    print(f"\n  By category:")
    categories = {}
    for r in all_results:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "correct": 0}
        categories[cat]["total"] += 1
        if r["evaluation"]["answer_correct"]:
            categories[cat]["correct"] += 1

    for cat, stats in sorted(categories.items()):
        acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"    {cat:30s} {stats['correct']:3d}/{stats['total']:3d}  ({acc:.0f}%)")

    # Save final results
    save_results(all_results, final_summary, status="completed")
    print(f"\n  Results saved to: {RESULTS_FILE}")

    # Git push
    print(f"\n  Pushing results to git...")
    git_push(
        f"benchmark: 50x2 evaluation complete — "
        f"Graph {graph_summary['accuracy']} | Quant {quant_summary['accuracy']} | "
        f"Overall {final_summary['overall_accuracy']}"
    )
