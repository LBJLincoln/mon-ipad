#!/usr/bin/env python3
"""
PARALLEL RAG EVALUATION — Up to 12 workflows run concurrently
==============================================================
Runs all pipeline types in parallel threads. Within each pipeline, questions
can also run in parallel batches (--batch-size). Supports up to 12+ concurrent
workflow executions across RAG + PME + custom pipelines.

Results are written to docs/data.json in real-time (thread-safe via live-writer lock).
Per-pipeline results are saved to logs/pipeline-results/ as JSON snapshots.

Usage:
  python run-eval-parallel.py                                  # All 4 RAG pipelines, parallel
  python run-eval-parallel.py --max 10                         # 10 questions per pipeline
  python run-eval-parallel.py --types graph,quantitative       # Specific pipelines
  python run-eval-parallel.py --all-parallel --workers 12      # ALL pipelines truly concurrent (including orchestrator)
  python run-eval-parallel.py --types standard,graph,quantitative,orchestrator,pme-gateway --workers 12
  python run-eval-parallel.py --reset                          # Re-test everything
  python run-eval-parallel.py --push                           # Git push after completion

Speedup: ~4-12x compared to sequential run-eval.py depending on --workers and --batch-size
"""

import json
import os
import sys
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Timezone: Europe/Paris
EVAL_DIR_TZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EVAL_DIR_TZ)
try:
    from tz_utils import paris_iso, paris_strftime
except ImportError:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Paris")
    def paris_iso(): return datetime.now(_TZ).isoformat(timespec='seconds')
    def paris_strftime(fmt="%Y-%m-%dT%H-%M-%S"): return datetime.now(_TZ).strftime(fmt)

# Import from the existing run-eval.py
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
sys.path.insert(0, EVAL_DIR)

from importlib.machinery import SourceFileLoader
run_eval_mod = SourceFileLoader("run_eval", os.path.join(EVAL_DIR, "run-eval.py")).load_module()
writer = SourceFileLoader("w", os.path.join(EVAL_DIR, "live-writer.py")).load_module()

# Progress callback for live monitoring from VM
try:
    from progress_callback import ProgressReporter
    _reporter = None  # initialized in main()
except ImportError:
    ProgressReporter = None
    _reporter = None

# Re-use functions from run-eval.py
call_rag = run_eval_mod.call_rag
call_local_reasoning = run_eval_mod.call_local_reasoning
extract_answer = run_eval_mod.extract_answer
evaluate_answer = run_eval_mod.evaluate_answer
extract_pipeline_details = run_eval_mod.extract_pipeline_details
compute_f1 = run_eval_mod.compute_f1
load_questions = run_eval_mod.load_questions
load_tested_ids_by_type = run_eval_mod.load_tested_ids_by_type
save_tested_ids = run_eval_mod.save_tested_ids
RAG_ENDPOINTS = run_eval_mod.RAG_ENDPOINTS
PIPELINE_BATCH_SIZES = getattr(run_eval_mod, 'PIPELINE_BATCH_SIZES', {})
PIPELINE_TIMEOUTS = getattr(run_eval_mod, 'PIPELINE_TIMEOUTS', {})
WEBHOOK_PATHS = getattr(run_eval_mod, 'WEBHOOK_PATHS', {})

# Pipelines that should use local LLM reasoning instead of HF Space
_local_pipelines = set()

# Directory for per-pipeline result snapshots
PIPELINE_RESULTS_DIR = os.path.join(REPO_ROOT, "logs", "pipeline-results")
os.makedirs(PIPELINE_RESULTS_DIR, exist_ok=True)

# Lock for dedup file writes
_dedup_lock = threading.Lock()

# Print lock (avoid garbled output)
_print_lock = threading.Lock()


def check_phase_gate(requested_dataset):
    """Verify previous phase gates are met before allowing progression.
    Returns True if OK, False if blocked. Use --force-phase to override."""
    if not requested_dataset or requested_dataset == "phase-1":
        return True

    # For phase-2+, check Phase 1 gates from readiness file
    readiness_file = os.path.join(REPO_ROOT, "db", "readiness", "phase-1.json")
    if not os.path.exists(readiness_file):
        print("  WARNING: Phase 1 readiness file not found. Cannot verify gates.")
        print("  Use --force-phase to skip gate check.")
        return False

    with open(readiness_file) as f:
        p1 = json.load(f)

    gates = p1.get("gate_criteria", {})
    all_met = True
    unmet = []

    for pipeline, info in gates.items():
        if not info.get("met", False):
            all_met = False
            target = info.get("target_accuracy", info.get("target", "?"))
            current = info.get("current", "?")
            unmet.append(f"    {pipeline}: {current}% (target: {target}%)")

    if not all_met:
        print("\n  PHASE GATE BLOCKED: Phase 1 exit criteria NOT met.")
        print("  Pipelines below target:")
        for line in unmet:
            print(line)
        print(f"\n  Cannot run --dataset {requested_dataset} until all Phase 1 gates pass.")
        print("  Use --force-phase to override (for testing/debugging only).")
        return False

    print("  Phase 1 gates: ALL MET. Proceeding to requested dataset.")
    return True


def tprint(msg):
    """Thread-safe print."""
    with _print_lock:
        print(msg, flush=True)


def save_pipeline_results(rag_type, results, label=""):
    """Save per-pipeline results as a JSON snapshot for traceability."""
    ts = paris_strftime()
    filename = f"{rag_type}-{ts}.json"
    filepath = os.path.join(PIPELINE_RESULTS_DIR, filename)
    snapshot = {
        "pipeline": rag_type,
        "timestamp": paris_iso(),
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


def _process_question(rag_type, q, i, total, endpoint, rag_timeout):
    """Process a single question. Thread-safe — designed for batch parallel execution."""
    qid = q["id"]
    used_local = False

    # Use local LLM reasoning for designated pipelines
    if rag_type in _local_pipelines:
        resp = call_local_reasoning(q["question"], rag_type=rag_type, timeout=rag_timeout)
        used_local = True
    else:
        resp = call_rag(endpoint, q["question"], timeout=rag_timeout)

    if resp["error"]:
        answer = ""
    else:
        answer = extract_answer(resp["data"])

    # LOCAL FALLBACK DISABLED (Session 57) — VM is pilotage ONLY, no local LLM calls.
    # All results must come from HF Space n8n pipelines. Local fallback was masking
    # real pipeline failures by calling OpenRouter directly, producing fake accuracy.

    if resp["error"]:
        answer = ""
        evaluation = {"correct": False, "method": "NO_ANSWER", "f1": 0.0,
                      "detail": resp["error"]}
        pipeline_details = {}
    else:
        if not answer:
            answer = extract_answer(resp["data"])
        evaluation = evaluate_answer(answer, q["expected"])
        pipeline_details = extract_pipeline_details(resp["data"], rag_type)

    is_correct = evaluation.get("correct", False)
    f1_val = evaluation.get("f1", compute_f1(answer, q["expected"]))
    has_error = resp["error"] is not None

    # Thread-safe print
    symbol = "[+]" if is_correct else "[-]"
    local_tag = " LOCAL" if used_local else ""
    tprint(f"  [{rag_type.upper()} {i+1}/{total}] {symbol} {qid} | "
           f"F1={f1_val:.3f} | {resp['latency_ms']}ms | {evaluation['method']}{local_tag}")

    return {
        "qid": qid,
        "question": q["question"],
        "expected": q["expected"],
        "answer": answer,
        "is_correct": is_correct,
        "f1_val": f1_val,
        "has_error": has_error,
        "used_local": used_local,
        "resp": resp,
        "evaluation": evaluation,
        "pipeline_details": pipeline_details,
    }


def run_pipeline(rag_type, questions, tested_ids_by_type, label=""):
    """Run a single pipeline's evaluation. Designed to run in a thread.
    Returns (rag_type, totals_dict, per_question_results).
    Early-stop: halts after N consecutive failures (default 4).
    Batch-size: processes N questions in parallel within the pipeline (E5 improvement)."""
    PIPELINE_TIMEOUTS = {
        "standard": 60,
        "graph": 90,
        "quantitative": 60,
        "orchestrator": 90,
    }
    EARLY_STOP_THRESHOLD = getattr(run_pipeline, '_early_stop', 4)
    _bs_auto = getattr(run_pipeline, '_batch_size_auto', False)
    if _bs_auto:
        BATCH_SIZE = PIPELINE_BATCH_SIZES.get(rag_type, 1)
    else:
        BATCH_SIZE = getattr(run_pipeline, '_batch_size', 1) or PIPELINE_BATCH_SIZES.get(rag_type, 1)

    endpoint = RAG_ENDPOINTS[rag_type]
    already_tested = tested_ids_by_type.get(rag_type, set())
    untested = [q for q in questions if q["id"] not in already_tested]

    if not untested:
        tprint(f"\n  [{rag_type.upper()}] SKIPPED (all {len(questions)} already tested)")
        return rag_type, {"tested": 0, "correct": 0, "errors": 0}, []

    batch_label = f" (batch={BATCH_SIZE})" if BATCH_SIZE > 1 else ""
    tprint(f"\n  [{rag_type.upper()}] Starting {len(untested)} questions{batch_label} "
           f"(skipping {len(already_tested)} already tested)")

    totals = {"tested": 0, "correct": 0, "errors": 0}
    per_question_results = []
    consecutive_failures = 0
    rag_timeout = PIPELINE_TIMEOUTS.get(rag_type, 120)
    stop_flag = False

    # Process in batches of BATCH_SIZE
    for batch_start in range(0, len(untested), BATCH_SIZE):
        if stop_flag:
            break

        batch = untested[batch_start:batch_start + BATCH_SIZE]

        if BATCH_SIZE > 1 and len(batch) > 1:
            # PARALLEL: process batch questions concurrently
            from concurrent.futures import ThreadPoolExecutor as BatchPool, as_completed as batch_done
            batch_results = []
            with BatchPool(max_workers=min(len(batch), BATCH_SIZE)) as batch_pool:
                futures = {}
                for j, q in enumerate(batch):
                    idx = batch_start + j
                    future = batch_pool.submit(
                        _process_question, rag_type, q, idx, len(untested), endpoint, rag_timeout
                    )
                    futures[future] = (j, q)

                for future in batch_done(futures):
                    j, q = futures[future]
                    try:
                        result = future.result()
                        batch_results.append((j, result))
                    except Exception as e:
                        tprint(f"  [{rag_type.upper()}] Batch error: {e}")

            # Process batch results in order
            batch_results.sort(key=lambda x: x[0])
            for _, result in batch_results:
                _record_result(rag_type, result, tested_ids_by_type, totals,
                               per_question_results)
                if result["is_correct"]:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                if result["has_error"]:
                    totals["errors"] += 1

                if _reporter:
                    _reporter.update(
                        pipeline=rag_type,
                        question_id=result["qid"],
                        correct=result["is_correct"],
                        latency_ms=result["resp"]["latency_ms"],
                        error=result["resp"]["error"],
                    )

        else:
            # SEQUENTIAL: single question (batch_size=1 or last partial batch)
            for j, q in enumerate(batch):
                idx = batch_start + j
                result = _process_question(rag_type, q, idx, len(untested), endpoint, rag_timeout)
                _record_result(rag_type, result, tested_ids_by_type, totals,
                               per_question_results)
                if result["is_correct"]:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                if result["has_error"]:
                    totals["errors"] += 1

                if _reporter:
                    _reporter.update(
                        pipeline=rag_type,
                        question_id=result["qid"],
                        correct=result["is_correct"],
                        latency_ms=result["resp"]["latency_ms"],
                        error=result["resp"]["error"],
                    )

                # Adaptive delay (only in sequential mode)
                if idx < len(untested) - 1:
                    custom_delay = getattr(run_pipeline, '_delay', None)
                    if custom_delay is not None:
                        time.sleep(custom_delay)
                    elif result["has_error"] and result["resp"]["error"] and \
                         ("429" in result["resp"]["error"] or "rate" in result["resp"]["error"].lower()):
                        time.sleep(3)
                    elif rag_type == "orchestrator":
                        time.sleep(1)

        # Early-stop check after each batch
        if consecutive_failures >= EARLY_STOP_THRESHOLD and totals["tested"] > EARLY_STOP_THRESHOLD:
            tprint(f"  [{rag_type.upper()}] EARLY STOP: {consecutive_failures} consecutive failures "
                   f"at question {batch_start + len(batch)}/{len(untested)}. Stopping pipeline.")
            stop_flag = True

        # Brief pause between batches to avoid overwhelming APIs
        if BATCH_SIZE > 1 and not stop_flag and batch_start + BATCH_SIZE < len(untested):
            time.sleep(0.5)

    # Save per-pipeline results snapshot
    if per_question_results:
        save_pipeline_results(rag_type, per_question_results, label=label)

    # Save dedup after pipeline completes
    with _dedup_lock:
        save_tested_ids({k: v for k, v in tested_ids_by_type.items()})

    acc = round(totals["correct"] / totals["tested"] * 100, 1) if totals["tested"] > 0 else 0
    tprint(f"\n  [{rag_type.upper()}] DONE: {totals['correct']}/{totals['tested']} "
           f"({acc}%) | {totals['errors']} errors")

    if _reporter:
        _reporter.pipeline_done(
            pipeline=rag_type,
            accuracy=acc,
            tested=totals["tested"],
            correct=totals["correct"],
        )

    return rag_type, totals, per_question_results


def _record_result(rag_type, result, tested_ids_by_type, totals, per_question_results):
    """Record a processed question result to dashboard and tracking."""
    writer.record_question(
        rag_type=rag_type,
        question_id=result["qid"],
        question_text=result["question"],
        correct=result["is_correct"],
        f1=result["f1_val"],
        latency_ms=result["resp"]["latency_ms"],
        error=result["resp"]["error"],
        cost_usd=0,
        expected=result["expected"],
        answer=result["answer"],
        match_type=result["evaluation"].get("method", "")
    )
    writer.record_execution(
        rag_type=rag_type,
        question_id=result["qid"],
        question_text=result["question"],
        expected=result["expected"],
        input_payload=result["resp"].get("input_payload"),
        raw_response=result["resp"].get("raw_response"),
        extracted_answer=result["answer"],
        correct=result["is_correct"],
        f1=result["f1_val"],
        match_type=result["evaluation"].get("method", ""),
        latency_ms=result["resp"]["latency_ms"],
        http_status=result["resp"].get("http_status"),
        response_size=result["resp"].get("response_size", 0),
        error=result["resp"]["error"],
        cost_usd=0,
        pipeline_details=result["pipeline_details"]
    )
    with _dedup_lock:
        tested_ids_by_type.setdefault(rag_type, set()).add(result["qid"])
    totals["tested"] += 1
    if result["is_correct"]:
        totals["correct"] += 1
    per_question_results.append({
        "id": result["qid"],
        "question": result["question"][:200],
        "expected": result["expected"][:200],
        "answer": result["answer"][:300],
        "correct": result["is_correct"],
        "f1": round(result["f1_val"], 4),
        "latency_ms": result["resp"]["latency_ms"],
        "method": result["evaluation"].get("method", ""),
        "error": result["resp"]["error"][:200] if result["resp"]["error"] else None,
    })


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parallel RAG Evaluation (up to 12 workflows concurrent)")
    parser.add_argument("--max", type=int, default=None,
                        help="Max questions per pipeline type")
    parser.add_argument("--types", type=str, default="standard,graph,quantitative,orchestrator",
                        help="Comma-separated pipeline types to test. "
                             "Available: standard,graph,quantitative,orchestrator,"
                             "pme-gateway,pme-action,pme-whatsapp")
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
    parser.add_argument("--force", action="store_true",
                        help="Force run even if phase gates are not met")
    parser.add_argument("--delay", type=int, default=None,
                        help="Delay (seconds) between questions. Default: 2s (5s for orchestrator). Use 10+ for free models.")
    parser.add_argument("--workers", type=int, default=None,
                        help="Max parallel workers. Default: number of pipeline types. Use 1 for sequential.")
    parser.add_argument("--early-stop", type=int, default=4,
                        help="Stop pipeline after N consecutive failures (default: 4). Use 0 to disable.")
    parser.add_argument("--local-pipelines", type=str, default="",
                        help="Comma-separated pipelines to run via local LLM (OpenRouter direct from VM). "
                             "Bypasses HF Space n8n for rate-limited pipelines. E.g.: quantitative,graph")
    parser.add_argument("--batch-size", type=int, default=0,
                        help="Questions processed in parallel WITHIN each pipeline. "
                             "Default: 0 = auto (uses per-pipeline optimal from PIPELINE_BATCH_SIZES: "
                             "standard=10, graph=5, quantitative=3, orchestrator=2). "
                             "Explicit value overrides auto for ALL pipelines.")
    parser.add_argument("--all-parallel", action="store_true",
                        help="Run ALL pipelines concurrently (including orchestrator). "
                             "Removes the orchestrator-sequential constraint. "
                             "Use with --workers 12 for maximum throughput.")
    args = parser.parse_args()

    # Pass delay, early-stop, and batch-size to run_pipeline via function attributes
    if args.delay is not None:
        run_pipeline._delay = args.delay
    run_pipeline._early_stop = args.early_stop if args.early_stop > 0 else 999
    # batch-size: 0 = auto (per-pipeline optimal), >0 = explicit override
    run_pipeline._batch_size = args.batch_size  # 0 means "use per-pipeline default"
    run_pipeline._batch_size_auto = (args.batch_size == 0)

    # LOCAL pipelines DISABLED (Session 57) — VM is pilotage ONLY
    # All eval must go through HF Space n8n pipelines
    if args.local_pipelines:
        print("  WARNING: --local-pipelines is DISABLED. VM is pilotage only.")
        print("  All evaluation must go through HF Space n8n pipelines.")
        print("  Ignoring --local-pipelines flag.")

    # Phase gate enforcement
    if not args.force and not check_phase_gate(args.dataset):
        sys.exit(1)

    start_time = datetime.now()
    requested_types = [t.strip() for t in args.types.split(",")]
    dataset_label = args.dataset or ("phase-1+2" if args.include_1000 else "phase-1")

    # PRE-FLIGHT: Validate datasets before running (FIX-39h — permanent data guard)
    try:
        from preflight import run_preflight
        print("\n  Running pre-flight checks...")
        pf_ok, pf_issues, pf_warnings = run_preflight(
            dataset=args.dataset, quick=True)
        if not pf_ok and not args.force:
            print("  PRE-FLIGHT FAILED — fix data issues before running eval.")
            for issue in pf_issues[:5]:
                print(f"    [BLOCK] {issue}")
            print("  Use --force to skip pre-flight checks.")
            sys.exit(1)
        if pf_warnings:
            for w in pf_warnings[:3]:
                print(f"    [WARN] {w}")
    except ImportError:
        print("  WARN: preflight.py not found — skipping data validation")

    # Phase gate enforcement for Phase 2+
    if args.dataset and args.dataset != "phase-1":
        try:
            from phase_gates import enforce_gate
            phase_num = int(args.dataset.split("-")[1]) if "-" in args.dataset else 2
            enforce_gate(target_phase=phase_num, force=getattr(args, 'force', False))
        except (ImportError, Exception) as e:
            print(f"  WARN: Phase gate check skipped: {e}")

    # Phase 2 now includes all 4 pipelines (standard-orch-1000x2.json added)
    if args.dataset == "phase-2" and args.types == "standard,graph,quantitative,orchestrator":
        requested_types = ["standard", "graph", "quantitative", "orchestrator"]
        print("  NOTE: Phase 2 tests all 4 pipelines (3000 questions total).")

    print("=" * 70)
    print("  PARALLEL RAG EVALUATION — Pipelines Concurrent")
    print(f"  Started: {start_time.isoformat()}")
    print(f"  Dataset: {dataset_label}")
    print(f"  Types: {', '.join(requested_types)}")
    print(f"  Max per pipeline: {args.max or 'all'}")
    if args.batch_size == 0:
        bs_info = ", ".join(f"{p}={PIPELINE_BATCH_SIZES.get(p, 1)}" for p in requested_types)
        print(f"  Batch size: auto ({bs_info})")
    else:
        print(f"  Batch size: {args.batch_size} (override for all pipelines)")
    # Show per-pipeline endpoints
    for p in requested_types:
        print(f"  [{p.upper()}] → {RAG_ENDPOINTS.get(p, 'UNKNOWN')}")
    print(f"  Reset dedup: {args.reset}")
    print("=" * 70)

    # Initialize dashboard
    writer.init(
        status="running",
        label=args.label or f"Parallel eval {dataset_label} {args.types}",
        description=args.description or f"Dataset: {dataset_label}, Parallel: {args.types}, Max: {args.max}, Reset: {args.reset}",
    )

    # Initialize progress reporter for live monitoring
    global _reporter
    if ProgressReporter:
        _reporter = ProgressReporter(label=args.label or f"eval-{dataset_label}")

    # Load questions
    print("\n  Loading questions...")
    questions = load_questions(include_1000=args.include_1000, dataset=args.dataset or "phase-1")

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

    # Start progress reporter
    if _reporter:
        total_q = sum(len(v) for v in questions.values())
        _reporter.start(total_questions=total_q, pipelines=list(questions.keys()))

    # DB snapshot
    print("\n  Taking pre-evaluation DB snapshot...")
    try:
        writer.snapshot_databases(trigger="pre-eval")
    except Exception as e:
        print(f"  DB snapshot failed (non-fatal): {e}")

    # Run pipelines
    print("\n  Launching pipeline evaluation...")
    overall_totals = {"tested": 0, "correct": 0, "errors": 0}

    if args.all_parallel:
        # ALL-PARALLEL MODE: every pipeline runs concurrently (up to --workers)
        all_workers = args.workers or len(requested_types)
        print(f"\n  ALL-PARALLEL: {', '.join(requested_types)} ({all_workers} workers)")

        with ThreadPoolExecutor(max_workers=all_workers) as executor:
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
    else:
        # LEGACY MODE: orchestrator runs AFTER others (resource conflict avoidance)
        non_orch = [t for t in requested_types if t != "orchestrator"]
        orch_only = [t for t in requested_types if t == "orchestrator"]

        for batch_label, batch_types in [("parallel", non_orch), ("sequential (post-parallel)", orch_only)]:
            if not batch_types:
                continue
            batch_workers = args.workers or len(batch_types)
            if "orchestrator" in batch_types:
                batch_workers = 1
            print(f"\n  Batch: {', '.join(batch_types)} ({batch_label}, {batch_workers} workers)")

            with ThreadPoolExecutor(max_workers=batch_workers) as executor:
                futures = {}
                for rag_type in batch_types:
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

    # Finish progress reporter
    if _reporter:
        final_acc = round(overall_totals['correct'] / overall_totals['tested'] * 100, 1) if overall_totals['tested'] > 0 else 0
        _reporter.finish(overall_accuracy=final_acc)

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
