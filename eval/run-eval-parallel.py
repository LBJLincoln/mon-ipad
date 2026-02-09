#!/usr/bin/env python3
"""
PARALLEL RAG EVALUATION — All 4 pipelines run concurrently
============================================================
Wraps run-eval.py logic but runs all pipeline types in parallel threads.
Each pipeline's questions still run sequentially (to not overwhelm n8n),
but all 4 pipelines execute simultaneously → ~4x speedup.

Results are written to docs/data.json in real-time (thread-safe via live-writer lock).
Per-pipeline results are saved to logs/pipeline-results/ as JSON snapshots.

Usage:
  python run-eval-parallel.py                          # All pipelines, parallel
  python run-eval-parallel.py --max 10                 # 10 questions per pipeline
  python run-eval-parallel.py --types graph,quantitative  # Specific pipelines
  python run-eval-parallel.py --reset                  # Re-test everything
  python run-eval-parallel.py --push                   # Git push after completion

Speedup: ~4x compared to sequential run-eval.py (60-90s/question × 200q → wall time = max pipeline)
"""

import json
import os
import sys
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import from the existing run-eval.py
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
sys.path.insert(0, EVAL_DIR)

from importlib.machinery import SourceFileLoader
run_eval_mod = SourceFileLoader("run_eval", os.path.join(EVAL_DIR, "run-eval.py")).load_module()
writer = SourceFileLoader("w", os.path.join(EVAL_DIR, "live-writer.py")).load_module()

# Re-use functions from run-eval.py
call_rag = run_eval_mod.call_rag
extract_answer = run_eval_mod.extract_answer
evaluate_answer = run_eval_mod.evaluate_answer
extract_pipeline_details = run_eval_mod.extract_pipeline_details
compute_f1 = run_eval_mod.compute_f1
load_questions = run_eval_mod.load_questions
load_tested_ids_by_type = run_eval_mod.load_tested_ids_by_type
save_tested_ids = run_eval_mod.save_tested_ids
RAG_ENDPOINTS = run_eval_mod.RAG_ENDPOINTS

# Directory for per-pipeline result snapshots
PIPELINE_RESULTS_DIR = os.path.join(REPO_ROOT, "logs", "pipeline-results")
os.makedirs(PIPELINE_RESULTS_DIR, exist_ok=True)

# Lock for dedup file writes
_dedup_lock = threading.Lock()

# Print lock (avoid garbled output)
_print_lock = threading.Lock()


def tprint(msg):
    """Thread-safe print."""
    with _print_lock:
        print(msg, flush=True)


def save_pipeline_results(rag_type, results, label=""):
    """Save per-pipeline results as a JSON snapshot for traceability."""
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"{rag_type}-{ts}.json"
    filepath = os.path.join(PIPELINE_RESULTS_DIR, filename)
    snapshot = {
        "pipeline": rag_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "label": label,
        "total_tested": len(results),
        "correct": sum(1 for r in results if r.get("correct")),
        "errors": sum(1 for r in results if r.get("error")),
        "accuracy_pct": round(sum(1 for r in results if r.get("correct")) / len(results) * 100, 1) if results else 0,
        "avg_latency_ms": int(sum(r.get("latency_ms", 0) for r in results) / len(results)) if results else 0,
        "results": results,
    }
    with open(filepath, "w") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    tprint(f"  [{rag_type.upper()}] Results saved: {filepath}")
    return filepath


def run_pipeline(rag_type, questions, tested_ids_by_type, label=""):
    """Run a single pipeline's evaluation. Designed to run in a thread.
    Returns (rag_type, totals_dict, per_question_results)."""
    endpoint = RAG_ENDPOINTS[rag_type]
    already_tested = tested_ids_by_type.get(rag_type, set())
    untested = [q for q in questions if q["id"] not in already_tested]

    if not untested:
        tprint(f"\n  [{rag_type.upper()}] SKIPPED (all {len(questions)} already tested)")
        return rag_type, {"tested": 0, "correct": 0, "errors": 0}, []

    tprint(f"\n  [{rag_type.upper()}] Starting {len(untested)} questions "
           f"(skipping {len(already_tested)} already tested)")

    totals = {"tested": 0, "correct": 0, "errors": 0}
    per_question_results = []

    for i, q in enumerate(untested):
        qid = q["id"]
        rag_timeout = 90 if rag_type == "orchestrator" else 60
        resp = call_rag(endpoint, q["question"], timeout=rag_timeout)

        if resp["error"]:
            answer = ""
            evaluation = {"correct": False, "method": "NO_ANSWER", "f1": 0.0,
                          "detail": resp["error"]}
            pipeline_details = {}
        else:
            answer = extract_answer(resp["data"])
            evaluation = evaluate_answer(answer, q["expected"])
            pipeline_details = extract_pipeline_details(resp["data"], rag_type)

        is_correct = evaluation.get("correct", False)
        f1_val = evaluation.get("f1", compute_f1(answer, q["expected"]))
        has_error = resp["error"] is not None

        # Thread-safe print
        symbol = "[+]" if is_correct else "[-]"
        truncated_answer = (answer[:80] + "...") if len(answer) > 80 else answer
        tprint(f"  [{rag_type.upper()} {i+1}/{len(untested)}] {symbol} {qid} | "
               f"F1={f1_val:.3f} | {resp['latency_ms']}ms | {evaluation['method']}")

        # Record to dashboard (thread-safe via live-writer lock)
        writer.record_question(
            rag_type=rag_type,
            question_id=qid,
            question_text=q["question"],
            correct=is_correct,
            f1=f1_val,
            latency_ms=resp["latency_ms"],
            error=resp["error"],
            cost_usd=0,
            expected=q["expected"],
            answer=answer,
            match_type=evaluation.get("method", "")
        )

        # Record detailed execution trace
        writer.record_execution(
            rag_type=rag_type,
            question_id=qid,
            question_text=q["question"],
            expected=q["expected"],
            input_payload=resp.get("input_payload"),
            raw_response=resp.get("raw_response"),
            extracted_answer=answer,
            correct=is_correct,
            f1=f1_val,
            match_type=evaluation.get("method", ""),
            latency_ms=resp["latency_ms"],
            http_status=resp.get("http_status"),
            response_size=resp.get("response_size", 0),
            error=resp["error"],
            cost_usd=0,
            pipeline_details=pipeline_details
        )

        # Track as tested (thread-safe)
        with _dedup_lock:
            tested_ids_by_type.setdefault(rag_type, set()).add(qid)

        totals["tested"] += 1
        if is_correct:
            totals["correct"] += 1
        if has_error:
            totals["errors"] += 1

        # Per-question result for pipeline snapshot
        per_question_results.append({
            "id": qid,
            "question": q["question"][:200],
            "expected": q["expected"][:200],
            "answer": answer[:300],
            "correct": is_correct,
            "f1": round(f1_val, 4),
            "latency_ms": resp["latency_ms"],
            "method": evaluation.get("method", ""),
            "error": resp["error"][:200] if resp["error"] else None,
        })

    # Save per-pipeline results snapshot
    if per_question_results:
        save_pipeline_results(rag_type, per_question_results, label=label)

    # Save dedup after pipeline completes (thread-safe)
    with _dedup_lock:
        save_tested_ids({k: v for k, v in tested_ids_by_type.items()})

    acc = round(totals["correct"] / totals["tested"] * 100, 1) if totals["tested"] > 0 else 0
    tprint(f"\n  [{rag_type.upper()}] DONE: {totals['correct']}/{totals['tested']} "
           f"({acc}%) | {totals['errors']} errors")
    return rag_type, totals, per_question_results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parallel RAG Evaluation (4 pipelines concurrent)")
    parser.add_argument("--max", type=int, default=None,
                        help="Max questions per pipeline type")
    parser.add_argument("--types", type=str, default="standard,graph,quantitative,orchestrator",
                        help="Comma-separated pipeline types to test")
    parser.add_argument("--dataset", type=str, default=None,
                        choices=["phase-1", "phase-2", "all"],
                        help="Dataset to evaluate: phase-1 (200q), phase-2 (1000q HF), all (1200q)")
    parser.add_argument("--include-1000", action="store_true",
                        help="[Legacy] Include HF-1000 questions (use --dataset all instead)")
    parser.add_argument("--reset", action="store_true",
                        help="Ignore dedup, re-test all questions")
    parser.add_argument("--push", action="store_true",
                        help="Git push docs/data.json after completion")
    parser.add_argument("--label", type=str, default="",
                        help="Human-readable label for this iteration")
    parser.add_argument("--description", type=str, default="",
                        help="Description of what changed before this eval")
    args = parser.parse_args()

    start_time = datetime.now()
    requested_types = [t.strip() for t in args.types.split(",")]
    dataset_label = args.dataset or ("phase-1+2" if args.include_1000 else "phase-1")

    # Auto-adjust types for Phase 2 (only graph + quantitative)
    if args.dataset == "phase-2" and args.types == "standard,graph,quantitative,orchestrator":
        requested_types = ["graph", "quantitative"]
        print("  NOTE: Phase 2 only tests graph + quantitative. Auto-adjusted --types.")

    print("=" * 70)
    print("  PARALLEL RAG EVALUATION — Pipelines Concurrent")
    print(f"  Started: {start_time.isoformat()}")
    print(f"  Dataset: {dataset_label}")
    print(f"  Types: {', '.join(requested_types)}")
    print(f"  Max per pipeline: {args.max or 'all'}")
    print(f"  Reset dedup: {args.reset}")
    print("=" * 70)

    # Initialize dashboard
    writer.init(
        status="running",
        label=args.label or f"Parallel eval {dataset_label} {args.types}",
        description=args.description or f"Dataset: {dataset_label}, Parallel: {args.types}, Max: {args.max}, Reset: {args.reset}",
    )

    # Load questions
    print("\n  Loading questions...")
    questions = load_questions(include_1000=args.include_1000, dataset=args.dataset)

    # Filter to requested types + apply max
    for t in list(questions.keys()):
        if t not in requested_types:
            questions[t] = []
        elif args.max:
            questions[t] = questions[t][:args.max]

    # Load dedup
    if args.reset:
        tested_ids = {t: set() for t in ["standard", "graph", "quantitative", "orchestrator"]}
        print("  Dedup RESET — all questions will be re-tested")
    else:
        tested_ids = load_tested_ids_by_type()
        total_already = sum(len(v) for v in tested_ids.values())
        print(f"  Dedup: {total_already} already tested (will be skipped)")

    # DB snapshot
    print("\n  Taking pre-evaluation DB snapshot...")
    try:
        writer.snapshot_databases(trigger="pre-eval")
    except Exception as e:
        print(f"  DB snapshot failed (non-fatal): {e}")

    # Run all pipelines in parallel
    print("\n  Launching parallel pipeline evaluation...")
    overall_totals = {"tested": 0, "correct": 0, "errors": 0}

    with ThreadPoolExecutor(max_workers=len(requested_types)) as executor:
        futures = {}
        for rag_type in requested_types:
            if questions.get(rag_type):
                future = executor.submit(
                    run_pipeline, rag_type, questions[rag_type],
                    tested_ids, label=args.label
                )
                futures[future] = rag_type

        for future in as_completed(futures):
            rag_type = futures[future]
            try:
                _, totals, _ = future.result()
                overall_totals["tested"] += totals["tested"]
                overall_totals["correct"] += totals["correct"]
                overall_totals["errors"] += totals["errors"]
            except Exception as e:
                print(f"  [{rag_type.upper()}] FAILED: {e}")

    # Post-eval DB snapshot
    print("\n  Taking post-evaluation DB snapshot...")
    try:
        writer.snapshot_databases(trigger="post-eval")
    except Exception as e:
        print(f"  DB snapshot failed (non-fatal): {e}")

    # Summary
    elapsed = int((datetime.now() - start_time).total_seconds())
    print(f"\n{'='*70}")
    print("  PARALLEL EVALUATION COMPLETE")
    print(f"{'='*70}")
    print(f"  Tested:  {overall_totals['tested']}")
    print(f"  Correct: {overall_totals['correct']}")
    print(f"  Errors:  {overall_totals['errors']}")
    if overall_totals['tested'] > 0:
        acc = round(overall_totals['correct'] / overall_totals['tested'] * 100, 1)
        print(f"  Accuracy: {acc}%")
    print(f"  Elapsed: {elapsed}s ({elapsed // 60}m {elapsed % 60}s)")
    print(f"  Pipeline results saved to: logs/pipeline-results/")

    if overall_totals["tested"] > 0:
        writer.finish(event="eval_complete")
        print(f"  Dashboard updated: docs/data.json")

    if args.push:
        print("  Pushing to GitHub...")
        writer.git_push(f"eval: parallel {overall_totals['tested']}q, "
                        f"{overall_totals['correct']} correct ({elapsed}s)")

    # Final dedup
    save_tested_ids(tested_ids)
    final_total = sum(len(v) for v in tested_ids.values())
    print(f"  Dedup: {final_total} total tested IDs saved")


if __name__ == "__main__":
    main()
