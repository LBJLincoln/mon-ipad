#!/usr/bin/env python3
"""
FAST ITERATION — 10 questions per pipeline, parallel execution
===============================================================
Designed for the rapid workflow improvement cycle:
  1. Make a change in n8n
  2. Run fast-iter.py (10q × 4 pipelines in parallel → ~2-3 min wall time)
  3. Check per-pipeline results
  4. If good → push workflow JSON + run full 200q eval
  5. If bad → revert and try again

This script:
- Runs 10 questions per pipeline (configurable via --questions)
- Executes all pipelines in parallel threads
- Saves per-pipeline JSON results to logs/pipeline-results/
- Records to docs/data.json dashboard (thread-safe)
- Selects a MIX of question difficulties: known-pass, known-fail, and untested
- Auto-compares with previous fast-iter results to detect regressions

Usage:
  python fast-iter.py                               # 10q per pipeline, all 4
  python fast-iter.py --questions 5                  # 5q per pipeline
  python fast-iter.py --pipelines graph,orchestrator # Specific pipelines
  python fast-iter.py --label "after fuzzy matching" # Tag the run
  python fast-iter.py --only-failing                 # Re-test only previously failing questions
  python fast-iter.py --push                         # Git push results
"""

import json
import os
import sys
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
sys.path.insert(0, EVAL_DIR)

from importlib.machinery import SourceFileLoader
run_eval_mod = SourceFileLoader("run_eval", os.path.join(EVAL_DIR, "run-eval.py")).load_module()
writer = SourceFileLoader("w", os.path.join(EVAL_DIR, "live-writer.py")).load_module()

call_rag = run_eval_mod.call_rag
extract_answer = run_eval_mod.extract_answer
evaluate_answer = run_eval_mod.evaluate_answer
extract_pipeline_details = run_eval_mod.extract_pipeline_details
compute_f1 = run_eval_mod.compute_f1
load_questions = run_eval_mod.load_questions
RAG_ENDPOINTS = run_eval_mod.RAG_ENDPOINTS

PIPELINE_RESULTS_DIR = os.path.join(REPO_ROOT, "logs", "pipeline-results")
FAST_ITER_DIR = os.path.join(REPO_ROOT, "logs", "fast-iter")
os.makedirs(PIPELINE_RESULTS_DIR, exist_ok=True)
os.makedirs(FAST_ITER_DIR, exist_ok=True)

_print_lock = threading.Lock()


def tprint(msg):
    with _print_lock:
        print(msg, flush=True)


def select_questions(all_questions, rag_type, n=10, only_failing=False):
    """Select a strategic mix of questions for fast iteration.

    Strategy: pick a mix of previously-failing, previously-passing, and untested
    questions to maximize signal about whether a change helped or hurt.
    """
    data_file = os.path.join(REPO_ROOT, "docs", "data.json")
    registry = {}
    if os.path.exists(data_file):
        with open(data_file) as f:
            data = json.load(f)
        registry = data.get("question_registry", {})

    # Categorize questions by their history
    failing = []
    passing = []
    untested = []

    for q in all_questions:
        qid = q["id"]
        if qid in registry:
            runs = registry[qid].get("runs", [])
            if runs:
                last_run = runs[-1]
                if last_run.get("correct"):
                    passing.append(q)
                else:
                    failing.append(q)
            else:
                untested.append(q)
        else:
            untested.append(q)

    if only_failing:
        selected = failing[:n]
        if len(selected) < n:
            selected += untested[:n - len(selected)]
        return selected

    # Mix: prioritize failing (they show if our fix worked), then untested, then passing
    selected = []

    # 50% failing questions (to check if fix worked)
    n_failing = min(len(failing), n // 2)
    selected.extend(failing[:n_failing])

    # 30% untested (new coverage)
    remaining = n - len(selected)
    n_untested = min(len(untested), max(1, remaining * 3 // 5))
    selected.extend(untested[:n_untested])

    # 20% passing (regression check)
    remaining = n - len(selected)
    n_passing = min(len(passing), remaining)
    selected.extend(passing[:n_passing])

    # Fill any remaining slots
    remaining = n - len(selected)
    if remaining > 0:
        all_ids = {q["id"] for q in selected}
        for q in all_questions:
            if q["id"] not in all_ids:
                selected.append(q)
                remaining -= 1
                if remaining <= 0:
                    break

    return selected[:n]


def run_pipeline_fast(rag_type, questions, label=""):
    """Run a single pipeline's fast iteration test.
    Returns (rag_type, results_list)."""
    endpoint = RAG_ENDPOINTS[rag_type]

    tprint(f"\n  [{rag_type.upper()}] Testing {len(questions)} questions...")
    results = []
    start = time.time()

    for i, q in enumerate(questions):
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

        symbol = "[+]" if is_correct else "[-]"
        tprint(f"  [{rag_type.upper()} {i+1}/{len(questions)}] {symbol} {qid} | "
               f"F1={f1_val:.3f} | {resp['latency_ms']}ms | {evaluation['method']}")

        # Record to dashboard (thread-safe)
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

        results.append({
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

    elapsed = int(time.time() - start)
    correct = sum(1 for r in results if r["correct"])
    errors = sum(1 for r in results if r.get("error"))
    acc = round(correct / len(results) * 100, 1) if results else 0

    tprint(f"  [{rag_type.upper()}] DONE: {correct}/{len(results)} ({acc}%) | "
           f"{errors} errors | {elapsed}s")

    return rag_type, results


def load_previous_fast_iter():
    """Load the most recent fast-iter result for comparison."""
    files = sorted([f for f in os.listdir(FAST_ITER_DIR) if f.endswith(".json")])
    if not files:
        return None
    with open(os.path.join(FAST_ITER_DIR, files[-1])) as f:
        return json.load(f)


def compare_with_previous(current_results, previous):
    """Compare current fast-iter with previous run."""
    if not previous:
        return

    print("\n  --- COMPARISON WITH PREVIOUS FAST-ITER ---")

    for pipe, results in current_results.items():
        curr_correct = sum(1 for r in results if r["correct"])
        curr_total = len(results)
        curr_acc = round(curr_correct / curr_total * 100, 1) if curr_total else 0

        prev_pipe = previous.get("pipelines", {}).get(pipe, {})
        prev_acc = prev_pipe.get("accuracy_pct", 0)
        prev_total = prev_pipe.get("total_tested", 0)

        if prev_total > 0:
            delta = curr_acc - prev_acc
            arrow = "^" if delta > 0 else ("v" if delta < 0 else "=")
            status = "IMPROVED" if delta > 0 else ("REGRESSED" if delta < 0 else "STABLE")
            print(f"  {pipe.upper()}: {prev_acc}% -> {curr_acc}% ({arrow}{abs(delta):.1f}pp) {status}")

            # Check for individual question regressions
            prev_results = {r["id"]: r for r in prev_pipe.get("results", [])}
            regressions = []
            fixes = []
            for r in results:
                if r["id"] in prev_results:
                    prev_r = prev_results[r["id"]]
                    if prev_r.get("correct") and not r["correct"]:
                        regressions.append(r["id"])
                    elif not prev_r.get("correct") and r["correct"]:
                        fixes.append(r["id"])
            if regressions:
                print(f"    REGRESSIONS: {', '.join(regressions)}")
            if fixes:
                print(f"    FIXES: {', '.join(fixes)}")
        else:
            print(f"  {pipe.upper()}: {curr_acc}% (no previous data)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fast Iteration — 10q/pipeline parallel test")
    parser.add_argument("--questions", "-n", type=int, default=10,
                        help="Questions per pipeline (default: 10)")
    parser.add_argument("--pipelines", type=str, default="standard,graph,quantitative,orchestrator",
                        help="Comma-separated pipelines to test")
    parser.add_argument("--dataset", type=str, default=None,
                        choices=["phase-1", "phase-2", "all"],
                        help="Dataset: phase-1 (200q), phase-2 (1000q HF), all (1200q)")
    parser.add_argument("--label", type=str, default="",
                        help="Label for this fast iteration run")
    parser.add_argument("--only-failing", action="store_true",
                        help="Re-test only previously failing questions")
    parser.add_argument("--push", action="store_true",
                        help="Git push results after completion")
    parser.add_argument("--force", action="store_true",
                        help="Force run even if phase gates are not met")
    args = parser.parse_args()

    start_time = datetime.now()
    pipelines = [p.strip() for p in args.pipelines.split(",")]
    dataset_label = args.dataset or "phase-1"

    # Phase gate enforcement for Phase 2+
    if args.dataset and args.dataset != "phase-1":
        try:
            from phase_gates import enforce_gate
            phase_num = int(args.dataset.split("-")[1]) if "-" in args.dataset else 2
            enforce_gate(target_phase=phase_num, force=getattr(args, 'force', False))
        except (ImportError, Exception) as e:
            print(f"  WARN: Phase gate check skipped: {e}")

    # Auto-adjust pipelines for Phase 2 (only graph + quantitative)
    if args.dataset == "phase-2" and args.pipelines == "standard,graph,quantitative,orchestrator":
        pipelines = ["graph", "quantitative"]
        print("  NOTE: Phase 2 only tests graph + quantitative. Auto-adjusted --pipelines.")

    print("=" * 70)
    print("  FAST ITERATION — Quick Pipeline Validation")
    print(f"  Started: {start_time.isoformat()}")
    print(f"  Dataset: {dataset_label}")
    print(f"  Pipelines: {', '.join(pipelines)}")
    print(f"  Questions per pipeline: {args.questions}")
    print(f"  Only failing: {args.only_failing}")
    if args.label:
        print(f"  Label: {args.label}")
    print("=" * 70)

    # Init writer for this fast-iter session
    writer.init(
        status="running",
        label=args.label or f"Fast-iter {dataset_label} {args.questions}q x {len(pipelines)} pipes",
        description=f"Fast iteration: {args.questions}q/pipeline, parallel, dataset={dataset_label}",
    )

    # Load questions
    print("\n  Loading questions...")
    all_questions = load_questions(dataset=args.dataset)

    # Select strategic question mix per pipeline
    selected = {}
    for pipe in pipelines:
        pipe_qs = all_questions.get(pipe, [])
        if not pipe_qs:
            print(f"  [{pipe.upper()}] No questions available")
            continue
        selected[pipe] = select_questions(
            pipe_qs, pipe, n=args.questions, only_failing=args.only_failing
        )
        print(f"  [{pipe.upper()}] Selected {len(selected[pipe])} questions")

    # Load previous results for comparison
    previous = load_previous_fast_iter()

    # Run all pipelines in parallel
    print("\n  Launching parallel fast iteration...")
    all_results = {}

    with ThreadPoolExecutor(max_workers=len(pipelines)) as executor:
        futures = {}
        for pipe in pipelines:
            if pipe in selected and selected[pipe]:
                future = executor.submit(
                    run_pipeline_fast, pipe, selected[pipe], label=args.label
                )
                futures[future] = pipe

        for future in as_completed(futures):
            pipe = futures[future]
            try:
                _, results = future.result()
                all_results[pipe] = results
            except Exception as e:
                print(f"  [{pipe.upper()}] FAILED: {e}")

    # Save combined fast-iter snapshot
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    snapshot = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "label": args.label,
        "questions_per_pipeline": args.questions,
        "only_failing": args.only_failing,
        "pipelines": {},
    }

    for pipe, results in all_results.items():
        correct = sum(1 for r in results if r["correct"])
        errors = sum(1 for r in results if r.get("error"))
        snapshot["pipelines"][pipe] = {
            "total_tested": len(results),
            "correct": correct,
            "errors": errors,
            "accuracy_pct": round(correct / len(results) * 100, 1) if results else 0,
            "avg_latency_ms": int(sum(r.get("latency_ms", 0) for r in results) / len(results)) if results else 0,
            "results": results,
        }

    snapshot_path = os.path.join(FAST_ITER_DIR, f"fast-iter-{ts}.json")
    with open(snapshot_path, "w") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    # Also save per-pipeline snapshots
    for pipe, results in all_results.items():
        pipe_path = os.path.join(PIPELINE_RESULTS_DIR, f"{pipe}-fast-{ts}.json")
        with open(pipe_path, "w") as f:
            json.dump({
                "pipeline": pipe,
                "timestamp": snapshot["timestamp"],
                "label": args.label,
                "mode": "fast-iter",
                **snapshot["pipelines"][pipe],
            }, f, indent=2, ensure_ascii=False)

    # Compare with previous
    compare_with_previous(all_results, previous)

    # Summary
    elapsed = int((datetime.now() - start_time).total_seconds())
    total_tested = sum(len(r) for r in all_results.values())
    total_correct = sum(sum(1 for r in results if r["correct"]) for results in all_results.values())

    print(f"\n{'='*70}")
    print("  FAST ITERATION COMPLETE")
    print(f"{'='*70}")

    for pipe in pipelines:
        if pipe in all_results:
            r = all_results[pipe]
            correct = sum(1 for x in r if x["correct"])
            errors = sum(1 for x in r if x.get("error"))
            acc = round(correct / len(r) * 100, 1) if r else 0
            print(f"  {pipe.upper():15s}: {correct}/{len(r)} ({acc}%) | {errors} errors")

    if total_tested > 0:
        overall_acc = round(total_correct / total_tested * 100, 1)
        print(f"  {'OVERALL':15s}: {total_correct}/{total_tested} ({overall_acc}%)")

    print(f"\n  Elapsed: {elapsed}s ({elapsed // 60}m {elapsed % 60}s)")
    print(f"  Results: {snapshot_path}")
    print(f"  Pipeline results: logs/pipeline-results/")

    if total_tested > 0:
        writer.finish(event="fast_iter_complete")

    if args.push:
        print("\n  Pushing results to GitHub...")
        writer.git_push(f"fast-iter: {total_tested}q, {total_correct} correct ({elapsed}s)")

    # Decision guidance
    if total_tested > 0:
        print(f"\n  --- NEXT STEPS ---")
        if overall_acc >= 70:
            print(f"  Results look good ({overall_acc}%). Consider running full eval:")
            print(f"    python eval/run-eval-parallel.py --reset --label \"{args.label}\"")
        else:
            print(f"  Results below target ({overall_acc}%). Review failures and iterate:")
            print(f"    python eval/fast-iter.py --only-failing --label \"fix attempt 2\"")


if __name__ == "__main__":
    main()
