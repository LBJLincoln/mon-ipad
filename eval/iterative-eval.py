#!/usr/bin/env python3
"""
ITERATIVE PIPELINE EVALUATION — Progressive Stage Gates (5 → 10 → 50)
=======================================================================
Prevents wasted time by testing in escalating stages per pipeline.
Only advances to the next stage if the current stage meets its threshold.

Stages:
  Stage 1:  5 questions  — smoke validation (must pass ≥60%)
  Stage 2: 10 questions  — quick validation (must pass ≥65%)
  Stage 3: 50 questions  — full validation  (must pass pipeline target)

Each pipeline is evaluated independently. A pipeline that fails stage 1
does NOT block other pipelines from advancing.

Key features:
  - Per-pipeline independent progression
  - Automatic error pattern detection & knowledge base lookup
  - Results saved to dashboard via live-writer
  - Detailed stage report with fix recommendations
  - Auto-loads knowledge base for known error remediation

Usage:
  python eval/iterative-eval.py                          # All pipelines, all stages
  python eval/iterative-eval.py --pipelines graph        # Single pipeline
  python eval/iterative-eval.py --stage 2                # Start from stage 2
  python eval/iterative-eval.py --min-accuracy 70        # Custom pass threshold
  python eval/iterative-eval.py --label "after fix X"    # Tag the run
  python eval/iterative-eval.py --no-gate                # Run all stages regardless
  python eval/iterative-eval.py --dataset phase-2        # Use Phase 2 questions
"""

import json
import os
import sys
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

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

# Node analyzer for post-stage diagnostics
try:
    node_analyzer = SourceFileLoader("node_analyzer", os.path.join(EVAL_DIR, "node-analyzer.py")).load_module()
except Exception:
    node_analyzer = None

# Directories
RESULTS_DIR = os.path.join(REPO_ROOT, "logs", "iterative-eval")
KB_FILE = os.path.join(REPO_ROOT, "docs", "knowledge-base.json")
os.makedirs(RESULTS_DIR, exist_ok=True)

_print_lock = threading.Lock()

# ============================================================
# Stage Definitions
# ============================================================
STAGES = [
    {"name": "Stage 1: Smoke (5q)",  "questions": 5,  "min_accuracy": 60.0, "max_errors_pct": 40.0},
    {"name": "Stage 2: Quick (10q)", "questions": 10, "min_accuracy": 65.0, "max_errors_pct": 20.0},
    {"name": "Stage 3: Full (50q)",  "questions": 50, "min_accuracy": None, "max_errors_pct": 10.0},
    # min_accuracy=None means use pipeline-specific target
]

PIPELINE_TARGETS = {
    "standard": 85.0,
    "graph": 70.0,
    "quantitative": 85.0,
    "orchestrator": 70.0,
}


def tprint(msg):
    with _print_lock:
        print(msg, flush=True)


# ============================================================
# Knowledge Base
# ============================================================
def load_knowledge_base():
    """Load the knowledge base for error pattern matching."""
    if os.path.exists(KB_FILE):
        with open(KB_FILE) as f:
            return json.load(f)
    return {"error_patterns": [], "fixes": [], "functional_choices": []}


def match_error_patterns(errors, kb):
    """Match observed errors against known patterns in the knowledge base."""
    matches = []
    for err in errors:
        err_type = err.get("error_type", "")
        err_msg = (err.get("error", "") or "").lower()
        pipeline = err.get("rag_type", "")

        for pattern in kb.get("error_patterns", []):
            if pattern.get("error_type") == err_type or \
               any(kw.lower() in err_msg for kw in pattern.get("keywords", [])):
                if not pattern.get("pipeline") or pattern["pipeline"] == pipeline:
                    matches.append({
                        "error": err,
                        "pattern": pattern,
                        "fix": pattern.get("fix", "No known fix"),
                        "priority": pattern.get("priority", "medium"),
                    })
                    break

    return matches


def update_knowledge_base(stage_results, kb):
    """Auto-detect new error patterns and suggest additions to the KB."""
    error_counts = defaultdict(lambda: defaultdict(int))
    for pipeline, results in stage_results.items():
        for r in results:
            if r.get("error"):
                key = (pipeline, r.get("error_type", "UNKNOWN"))
                error_counts[key]["count"] += 1
                error_counts[key]["sample_msg"] = r["error"][:200]
                error_counts[key]["sample_qid"] = r["id"]

    new_patterns = []
    for (pipeline, err_type), info in error_counts.items():
        if info["count"] >= 2:  # Pattern threshold: 2+ occurrences
            existing = any(
                p.get("error_type") == err_type and (not p.get("pipeline") or p["pipeline"] == pipeline)
                for p in kb.get("error_patterns", [])
            )
            if not existing:
                new_patterns.append({
                    "pipeline": pipeline,
                    "error_type": err_type,
                    "count": info["count"],
                    "sample": info["sample_msg"],
                    "sample_qid": info["sample_qid"],
                })

    return new_patterns


# ============================================================
# Question Selection
# ============================================================
def select_questions_for_stage(all_questions, pipeline, stage_num, n, previous_stage_results=None):
    """Select questions for a stage, prioritizing failing and untested questions.

    Stage 1: Random mix
    Stage 2: Include all Stage 1 failures + new questions
    Stage 3: All questions (up to n)
    """
    data_file = os.path.join(REPO_ROOT, "docs", "data.json")
    registry = {}
    if os.path.exists(data_file):
        with open(data_file) as f:
            data = json.load(f)
        registry = data.get("question_registry", {})

    # Categorize
    failing = []
    passing = []
    untested = []
    for q in all_questions:
        qid = q["id"]
        if qid in registry:
            runs = registry[qid].get("runs", [])
            if runs and runs[-1].get("correct"):
                passing.append(q)
            elif runs:
                failing.append(q)
            else:
                untested.append(q)
        else:
            untested.append(q)

    if stage_num == 0:
        # Stage 1: 60% failing, 20% untested, 20% passing
        selected = []
        n_fail = min(len(failing), max(1, int(n * 0.6)))
        selected.extend(failing[:n_fail])
        n_unt = min(len(untested), max(1, int(n * 0.2)))
        selected.extend(untested[:n_unt])
        remaining = n - len(selected)
        selected.extend(passing[:remaining])
        # Fill with untested if not enough
        if len(selected) < n:
            used_ids = {q["id"] for q in selected}
            for q in all_questions:
                if q["id"] not in used_ids:
                    selected.append(q)
                    if len(selected) >= n:
                        break
        return selected[:n]

    elif stage_num == 1:
        # Stage 2: Include all Stage 1 failures + more failing + new untested
        selected = []
        prev_fail_ids = set()
        if previous_stage_results:
            prev_fail_ids = {r["id"] for r in previous_stage_results if not r.get("correct")}
            # Re-test previous failures
            for q in all_questions:
                if q["id"] in prev_fail_ids:
                    selected.append(q)

        # Add more failing questions
        used_ids = {q["id"] for q in selected}
        for q in failing:
            if q["id"] not in used_ids:
                selected.append(q)
                if len(selected) >= n:
                    break

        # Fill with untested
        used_ids = {q["id"] for q in selected}
        for q in untested:
            if q["id"] not in used_ids:
                selected.append(q)
                if len(selected) >= n:
                    break

        # Fill with passing (regression check)
        used_ids = {q["id"] for q in selected}
        for q in passing:
            if q["id"] not in used_ids:
                selected.append(q)
                if len(selected) >= n:
                    break

        return selected[:n]

    else:
        # Stage 3: All questions up to n
        # Prioritize: failing first, then untested, then passing
        selected = failing + untested + passing
        return selected[:n]


# ============================================================
# Pipeline Runner
# ============================================================
def run_pipeline_stage(pipeline, questions, stage_name):
    """Run a single pipeline stage and return results."""
    endpoint = RAG_ENDPOINTS[pipeline]
    results = []
    start = time.time()

    tprint(f"\n  [{pipeline.upper()}] {stage_name}: Testing {len(questions)} questions...")

    for i, q in enumerate(questions):
        qid = q["id"]
        rag_timeout = 120 if pipeline == "orchestrator" else 60
        resp = call_rag(endpoint, q["question"], timeout=rag_timeout)

        if resp["error"]:
            answer = ""
            evaluation = {"correct": False, "method": "NO_ANSWER", "f1": 0.0, "detail": resp["error"]}
            pipeline_details = {}
        else:
            answer = extract_answer(resp["data"])
            evaluation = evaluate_answer(answer, q["expected"])
            pipeline_details = extract_pipeline_details(resp["data"], pipeline)

        is_correct = evaluation.get("correct", False)
        f1_val = evaluation.get("f1", compute_f1(answer, q["expected"]))

        error_type = None
        if resp["error"]:
            err_lower = resp["error"].lower()
            if "timeout" in err_lower or "timed out" in err_lower:
                error_type = "TIMEOUT"
            elif "connection" in err_lower or "network" in err_lower:
                error_type = "NETWORK"
            elif "500" in err_lower or "server" in err_lower:
                error_type = "SERVER_ERROR"
            elif "empty" in err_lower:
                error_type = "EMPTY_RESPONSE"
            else:
                error_type = "UNKNOWN"

        symbol = "[+]" if is_correct else ("[ ]" if resp["error"] else "[-]")
        tprint(f"    {symbol} {qid} | F1={f1_val:.3f} | {resp['latency_ms']}ms | {evaluation['method']}"
               + (f" | ERR: {error_type}" if error_type else ""))

        # Record to dashboard
        writer.record_question(
            rag_type=pipeline,
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
            rag_type=pipeline,
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
            "error_type": error_type,
            "rag_type": pipeline,
        })

        # Rate-limit protection: delay between questions
        if i < len(questions) - 1:
            delay = 5 if pipeline == "orchestrator" else 2
            time.sleep(delay)

    elapsed = int(time.time() - start)
    correct = sum(1 for r in results if r["correct"])
    errors = sum(1 for r in results if r.get("error"))
    total = len(results)
    acc = round(correct / total * 100, 1) if total > 0 else 0
    err_rate = round(errors / total * 100, 1) if total > 0 else 0

    tprint(f"  [{pipeline.upper()}] {stage_name} DONE: {correct}/{total} ({acc}%) | "
           f"{errors} errors ({err_rate}%) | {elapsed}s")

    return {
        "pipeline": pipeline,
        "stage": stage_name,
        "results": results,
        "accuracy": acc,
        "error_rate": err_rate,
        "correct": correct,
        "total": total,
        "errors": errors,
        "elapsed_s": elapsed,
    }


# ============================================================
# Stage Gate Check
# ============================================================
def check_stage_gate(stage_result, stage_config, pipeline):
    """Check if a pipeline passed a stage gate.

    Returns (passed: bool, reason: str, recommendations: list)
    """
    acc = stage_result["accuracy"]
    err_rate = stage_result["error_rate"]

    min_acc = stage_config["min_accuracy"]
    if min_acc is None:
        min_acc = PIPELINE_TARGETS.get(pipeline, 70.0)

    max_err = stage_config["max_errors_pct"]

    reasons = []
    recommendations = []

    # Check accuracy
    if acc < min_acc:
        reasons.append(f"accuracy {acc}% < {min_acc}% threshold")
        gap = min_acc - acc
        if gap > 20:
            recommendations.append(f"CRITICAL: {pipeline} is {gap:.1f}pp below target. Check if pipeline is functional.")
        elif gap > 10:
            recommendations.append(f"Significant gap ({gap:.1f}pp). Review error logs and consider workflow patches.")
        else:
            recommendations.append(f"Close to target ({gap:.1f}pp gap). Fine-tune answer extraction or matching.")

    # Check error rate
    if err_rate > max_err:
        reasons.append(f"error rate {err_rate}% > {max_err}% limit")
        recommendations.append(f"Fix errors first: {stage_result['errors']} errors out of {stage_result['total']} questions.")

    passed = len(reasons) == 0
    reason = "; ".join(reasons) if reasons else "All checks passed"

    # Analyze error patterns for recommendations
    if not passed:
        error_types = defaultdict(int)
        for r in stage_result["results"]:
            if r.get("error_type"):
                error_types[r["error_type"]] += 1
        if error_types:
            most_common = max(error_types.items(), key=lambda x: x[1])
            recommendations.append(f"Most common error: {most_common[0]} ({most_common[1]}x)")

    return passed, reason, recommendations


# ============================================================
# Report Generation
# ============================================================
def generate_stage_report(all_stage_results, kb):
    """Generate a detailed report after all stages complete."""
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pipelines": {},
        "summary": {},
        "error_analysis": {},
        "kb_matches": [],
        "new_patterns": [],
        "recommendations": [],
    }

    overall_correct = 0
    overall_total = 0

    for pipeline, stages in all_stage_results.items():
        last_stage = stages[-1] if stages else None
        if not last_stage:
            continue

        report["pipelines"][pipeline] = {
            "stages_completed": len(stages),
            "stages_total": len(STAGES),
            "final_accuracy": last_stage["accuracy"],
            "final_error_rate": last_stage["error_rate"],
            "target": PIPELINE_TARGETS.get(pipeline, 70.0),
            "met_target": last_stage["accuracy"] >= PIPELINE_TARGETS.get(pipeline, 70.0),
            "stage_details": [{
                "name": s["stage"],
                "accuracy": s["accuracy"],
                "error_rate": s["error_rate"],
                "correct": s["correct"],
                "total": s["total"],
            } for s in stages],
        }

        overall_correct += last_stage["correct"]
        overall_total += last_stage["total"]

        # Error analysis
        all_errors = [r for s in stages for r in s["results"] if r.get("error")]
        if all_errors:
            matches = match_error_patterns(all_errors, kb)
            report["kb_matches"].extend(matches)

            error_dist = defaultdict(int)
            for e in all_errors:
                error_dist[e.get("error_type", "UNKNOWN")] += 1
            report["error_analysis"][pipeline] = dict(error_dist)

    # New patterns
    all_results = {}
    for pipeline, stages in all_stage_results.items():
        all_results[pipeline] = [r for s in stages for r in s["results"]]
    report["new_patterns"] = update_knowledge_base(all_results, kb)

    # Overall summary
    report["summary"] = {
        "overall_accuracy": round(overall_correct / overall_total * 100, 1) if overall_total > 0 else 0,
        "total_tested": overall_total,
        "total_correct": overall_correct,
        "pipelines_at_target": sum(
            1 for p in report["pipelines"].values() if p["met_target"]
        ),
        "pipelines_total": len(report["pipelines"]),
    }

    # Global recommendations
    for pipeline, stages in all_stage_results.items():
        if stages and stages[-1]["accuracy"] < PIPELINE_TARGETS.get(pipeline, 70.0):
            gap = PIPELINE_TARGETS[pipeline] - stages[-1]["accuracy"]
            if len(stages) == 1:
                report["recommendations"].append(
                    f"[{pipeline}] BLOCKED at Stage 1 ({stages[-1]['accuracy']}%). "
                    f"Pipeline may be non-functional. Check n8n workflow status and endpoint connectivity."
                )
            else:
                report["recommendations"].append(
                    f"[{pipeline}] Reached Stage {len(stages)} but {gap:.1f}pp below target. "
                    f"Review Stage {len(stages)} failures for targeted fixes."
                )

    return report


# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Iterative Pipeline Evaluation — Progressive 5 → 10 → 50 stages"
    )
    parser.add_argument("--pipelines", type=str, default="standard,graph,quantitative,orchestrator",
                        help="Comma-separated pipelines to test")
    parser.add_argument("--stage", type=int, default=1, choices=[1, 2, 3],
                        help="Start from stage N (default: 1)")
    parser.add_argument("--min-accuracy", type=float, default=None,
                        help="Override minimum accuracy for stage gates")
    parser.add_argument("--label", type=str, default="",
                        help="Label for this evaluation run")
    parser.add_argument("--no-gate", action="store_true",
                        help="Run all stages regardless of gate results")
    parser.add_argument("--dataset", type=str, default=None,
                        choices=["phase-1", "phase-2", "all"],
                        help="Dataset to use")
    parser.add_argument("--force", action="store_true",
                        help="Skip phase gate checks")
    parser.add_argument("--push", action="store_true",
                        help="Git push results after completion")
    parser.add_argument("--parallel", action="store_true",
                        help="Run pipelines in parallel within each stage")
    parser.add_argument("--no-analysis", action="store_true",
                        help="Skip post-stage node-by-node analysis")
    args = parser.parse_args()

    start_time = datetime.now()
    pipelines = [p.strip() for p in args.pipelines.split(",")]
    start_stage = args.stage - 1  # 0-indexed

    # Auto-adjust for Phase 2
    if args.dataset == "phase-2" and args.pipelines == "standard,graph,quantitative,orchestrator":
        pipelines = ["graph", "quantitative"]
        tprint("  NOTE: Phase 2 tests graph + quantitative only. Auto-adjusted.")

    print("=" * 70)
    print("  ITERATIVE PIPELINE EVALUATION — Progressive Stage Gates")
    print(f"  Started: {start_time.isoformat()}")
    print(f"  Pipelines: {', '.join(pipelines)}")
    print(f"  Starting stage: {args.stage}")
    print(f"  Gate enforcement: {'OFF' if args.no_gate else 'ON'}")
    if args.label:
        print(f"  Label: {args.label}")
    print("=" * 70)

    # Init writer
    writer.init(
        label=args.label or f"Iterative eval ({len(pipelines)} pipes, stage {args.stage}+)",
        description=f"Iterative evaluation: stages {args.stage}-3, pipelines: {','.join(pipelines)}",
    )

    # Load questions
    tprint("\n  Loading questions...")
    all_questions = load_questions(dataset=args.dataset)

    # Load knowledge base
    kb = load_knowledge_base()

    # Track results per pipeline per stage
    all_stage_results = {p: [] for p in pipelines}
    pipeline_status = {p: "pending" for p in pipelines}

    for stage_idx in range(start_stage, len(STAGES)):
        stage = STAGES[stage_idx]
        stage_name = stage["name"]
        n_questions = stage["questions"]

        # Apply min-accuracy override
        if args.min_accuracy is not None:
            stage = dict(stage)
            stage["min_accuracy"] = args.min_accuracy

        print(f"\n{'='*70}")
        print(f"  === {stage_name} ===")
        print(f"  Questions per pipeline: {n_questions}")
        print(f"  Min accuracy: {stage['min_accuracy'] or 'pipeline target'}%")
        print(f"  Max error rate: {stage['max_errors_pct']}%")
        print(f"{'='*70}")

        # Determine which pipelines are still active
        active_pipelines = [
            p for p in pipelines
            if pipeline_status[p] != "blocked" or args.no_gate
        ]

        if not active_pipelines:
            tprint("\n  All pipelines blocked. Stopping.")
            break

        tprint(f"\n  Active pipelines: {', '.join(active_pipelines)}")

        # Select questions and run
        stage_results = {}

        if args.parallel and len(active_pipelines) > 1:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=len(active_pipelines)) as executor:
                futures = {}
                for pipe in active_pipelines:
                    pipe_qs = all_questions.get(pipe, [])
                    if not pipe_qs:
                        tprint(f"  [{pipe.upper()}] No questions available, skipping")
                        continue

                    prev_results = None
                    if stage_idx > 0 and all_stage_results[pipe]:
                        prev_results = all_stage_results[pipe][-1]["results"]

                    selected = select_questions_for_stage(
                        pipe_qs, pipe, stage_idx, n_questions, prev_results
                    )
                    future = executor.submit(run_pipeline_stage, pipe, selected, stage_name)
                    futures[future] = pipe

                for future in as_completed(futures):
                    pipe = futures[future]
                    try:
                        result = future.result()
                        stage_results[pipe] = result
                    except Exception as e:
                        tprint(f"  [{pipe.upper()}] FAILED: {e}")
        else:
            # Sequential execution
            for pipe in active_pipelines:
                pipe_qs = all_questions.get(pipe, [])
                if not pipe_qs:
                    tprint(f"  [{pipe.upper()}] No questions available, skipping")
                    continue

                prev_results = None
                if stage_idx > 0 and all_stage_results[pipe]:
                    prev_results = all_stage_results[pipe][-1]["results"]

                selected = select_questions_for_stage(
                    pipe_qs, pipe, stage_idx, n_questions, prev_results
                )
                result = run_pipeline_stage(pipe, selected, stage_name)
                stage_results[pipe] = result

        # Check gates
        print(f"\n  --- {stage_name}: GATE CHECK ---")
        for pipe in active_pipelines:
            if pipe not in stage_results:
                continue

            result = stage_results[pipe]
            all_stage_results[pipe].append(result)

            passed, reason, recommendations = check_stage_gate(result, stage, pipe)

            if passed:
                tprint(f"  [{pipe.upper()}] PASSED: {result['accuracy']}% accuracy, "
                       f"{result['error_rate']}% errors → advancing to next stage")
                pipeline_status[pipe] = "passed"
            else:
                tprint(f"  [{pipe.upper()}] BLOCKED: {reason}")
                for rec in recommendations:
                    tprint(f"    → {rec}")

                # Check KB for known fixes
                errors = [r for r in result["results"] if r.get("error")]
                if errors:
                    matches = match_error_patterns(errors, kb)
                    if matches:
                        tprint(f"    Known fixes from knowledge base:")
                        seen_fixes = set()
                        for m in matches:
                            fix = m["fix"]
                            if fix not in seen_fixes:
                                tprint(f"      • [{m['priority'].upper()}] {fix}")
                                seen_fixes.add(fix)

                if not args.no_gate:
                    pipeline_status[pipe] = "blocked"

        # === POST-STAGE NODE ANALYSIS ===
        # Automatically fetch n8n execution logs and analyze node-by-node
        if node_analyzer and not args.no_analysis:
            tprint(f"\n  --- {stage_name}: NODE-BY-NODE ANALYSIS ---")
            for pipe in active_pipelines:
                if pipe not in stage_results:
                    continue
                result = stage_results[pipe]
                questions_for_analysis = [
                    {"id": r["id"], "question": r["question"]}
                    for r in result["results"]
                ]
                try:
                    diag = node_analyzer.analyze_stage(
                        pipeline=pipe,
                        questions_tested=questions_for_analysis,
                        stage_name=stage_name,
                        label=args.label,
                    )
                    # Attach diagnostics to stage results
                    result["diagnostics"] = {
                        "total_issues": diag.get("total_issues", 0),
                        "issues_by_severity": diag.get("issues_by_severity", {}),
                        "top_issues": diag.get("top_issues", [])[:5],
                        "recommendations": diag.get("recommendations", [])[:3],
                    }
                except Exception as e:
                    tprint(f"  [NODE-ANALYZER] Error analyzing {pipe}: {e}")

    # Generate report
    report = generate_stage_report(all_stage_results, kb)

    # Save report
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    report_path = os.path.join(RESULTS_DIR, f"iterative-{ts}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Save stage data to a format the dashboard can consume
    stage_data_path = os.path.join(RESULTS_DIR, f"stages-{ts}.json")
    stage_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "label": args.label,
        "pipelines": {},
    }
    for pipe, stages in all_stage_results.items():
        stage_data["pipelines"][pipe] = {
            "status": pipeline_status[pipe],
            "stages": [{
                "name": s["stage"],
                "accuracy": s["accuracy"],
                "error_rate": s["error_rate"],
                "correct": s["correct"],
                "total": s["total"],
                "errors": s["errors"],
                "elapsed_s": s["elapsed_s"],
                "results": s["results"],
                "diagnostics": s.get("diagnostics"),
            } for s in stages],
        }
    with open(stage_data_path, "w") as f:
        json.dump(stage_data, f, indent=2, ensure_ascii=False)

    # Also save the latest stage data to a well-known location
    latest_path = os.path.join(RESULTS_DIR, "latest-stages.json")
    with open(latest_path, "w") as f:
        json.dump(stage_data, f, indent=2, ensure_ascii=False)

    # Print final summary
    elapsed = int((datetime.now() - start_time).total_seconds())

    print(f"\n{'='*70}")
    print("  ITERATIVE EVALUATION COMPLETE")
    print(f"{'='*70}")
    print(f"\n  Pipeline Results:")
    for pipe in pipelines:
        stages = all_stage_results[pipe]
        status = pipeline_status[pipe]
        if stages:
            last = stages[-1]
            stage_count = len(stages)
            status_icon = "PASS" if status == "passed" else "BLOCKED"
            tprint(f"    {pipe.upper():15s}: {status_icon} at Stage {stage_count} | "
                   f"{last['accuracy']}% accuracy | {last['error_rate']}% errors")
        else:
            tprint(f"    {pipe.upper():15s}: NO DATA")

    # Overall
    if report["summary"]["total_tested"] > 0:
        tprint(f"\n  Overall: {report['summary']['overall_accuracy']}% "
               f"({report['summary']['total_correct']}/{report['summary']['total_tested']})")
        tprint(f"  Pipelines at target: {report['summary']['pipelines_at_target']}/{report['summary']['pipelines_total']}")

    # Recommendations
    if report["recommendations"]:
        tprint(f"\n  Recommendations:")
        for rec in report["recommendations"]:
            tprint(f"    → {rec}")

    # New patterns
    if report["new_patterns"]:
        tprint(f"\n  New error patterns detected (consider adding to knowledge base):")
        for p in report["new_patterns"]:
            tprint(f"    [{p['pipeline']}] {p['error_type']}: {p['count']}x — e.g. {p['sample'][:100]}")

    tprint(f"\n  Elapsed: {elapsed}s ({elapsed // 60}m {elapsed % 60}s)")
    tprint(f"  Report: {report_path}")
    tprint(f"  Stages: {stage_data_path}")

    writer.finish(event="iterative_eval_complete")

    if args.push:
        tprint("\n  Pushing results to GitHub...")
        writer.git_push(f"iterative-eval: {report['summary']['total_tested']}q tested ({elapsed}s)")

    # Decision guidance
    all_passed = all(pipeline_status[p] in ("passed", "pending") for p in pipelines)
    if all_passed and report["summary"].get("overall_accuracy", 0) >= 75:
        tprint(f"\n  All pipelines passed all stages. Ready for full eval:")
        tprint(f"    python eval/run-eval-parallel.py --reset --label \"{args.label}\"")
    else:
        blocked = [p for p in pipelines if pipeline_status[p] == "blocked"]
        if blocked:
            tprint(f"\n  Blocked pipelines: {', '.join(blocked)}")
            tprint(f"  Fix the issues above, then re-run:")
            tprint(f"    python eval/iterative-eval.py --pipelines {','.join(blocked)} --label \"fix attempt\"")


if __name__ == "__main__":
    main()
