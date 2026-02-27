#!/usr/bin/env python3
"""
Decision Engine — KEEP / REVERT / HOLD decision for each RAG pipeline.
========================================================================
Implements the decision matrix from agentic-automation-spec.md:

  - Accuracy regression >10% from golden  =>  auto REVERT  (confidence 1.0)
  - Accuracy below golden                 =>  HOLD / REVERT depending on other signals
  - Smoke test failure below threshold     =>  strong REVERT signal
  - Error spike >2x threshold             =>  strong REVERT signal
  - Latency degradation >1.5x threshold   =>  weak REVERT signal

Usage (standalone):
  python3 scripts/decision-engine.py --pipeline standard
  python3 scripts/decision-engine.py --check-all
  python3 scripts/decision-engine.py --check-all --pretty
  python3 scripts/decision-engine.py --test          # dry-run with synthetic data

Usage (importable):
  from decision_engine import make_keep_revert_decision
  result = make_keep_revert_decision("standard", metrics)
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
EVAL_DIR = os.path.join(REPO_ROOT, "eval")
DATA_JSON = os.path.join(REPO_ROOT, "docs", "data.json")
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
ITERATIVE_DIR = os.path.join(LOGS_DIR, "iterative-eval")
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

# ---------------------------------------------------------------------------
# Load .env.local (best-effort)
# ---------------------------------------------------------------------------
def _load_env_local():
    """Parse .env.local and inject into os.environ (skip comments/blanks)."""
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

_load_env_local()

# ---------------------------------------------------------------------------
# Import golden thresholds from eval/golden-check.py
# ---------------------------------------------------------------------------
sys.path.insert(0, EVAL_DIR)
try:
    from importlib.machinery import SourceFileLoader
    _gc = SourceFileLoader("golden_check", os.path.join(EVAL_DIR, "golden-check.py")).load_module()
    GOLDEN_THRESHOLDS = _gc.GOLDEN_THRESHOLDS
    get_metrics = _gc.get_metrics
except Exception:
    # Fallback: inline thresholds if import fails
    GOLDEN_THRESHOLDS = {
        "standard":     {"min_accuracy": 85.0, "max_latency_p95": 5000,  "max_error_rate": 5.0,  "required_smoke_pass": 0.8},
        "graph":        {"min_accuracy": 70.0, "max_latency_p95": 8000,  "max_error_rate": 10.0, "required_smoke_pass": 0.6},
        "quantitative": {"min_accuracy": 85.0, "max_latency_p95": 10000, "max_error_rate": 5.0,  "required_smoke_pass": 0.8},
        "orchestrator": {"min_accuracy": 70.0, "max_latency_p95": 15000, "max_error_rate": 10.0, "required_smoke_pass": 0.6},
        "nomos42":      {"min_accuracy": 75.0, "max_latency_p95": 5000,  "max_error_rate": 15.0, "required_smoke_pass": 0.75},
    }
    get_metrics = None

ALL_PIPELINES = list(GOLDEN_THRESHOLDS.keys())


# ---------------------------------------------------------------------------
# Metrics loading (local fallback if golden-check import failed)
# ---------------------------------------------------------------------------

def _find_latest_results_file() -> str:
    """Find the most recent iterative-eval results file."""
    pattern = os.path.join(ITERATIVE_DIR, "iterative-*.json")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else ""


def _load_metrics_from_results_file(filepath: str, pipeline: str) -> dict:
    """Load metrics from an iterative-eval JSON file."""
    if not filepath or not os.path.exists(filepath):
        return {}
    with open(filepath) as f:
        data = json.load(f)
    pipe_data = data.get("pipelines", {}).get(pipeline, {})
    if not pipe_data:
        return {}

    accuracy = pipe_data.get("final_accuracy", 0.0)
    error_rate = pipe_data.get("final_error_rate", 0.0)
    total = 0
    correct = 0
    for stage in pipe_data.get("stage_details", []):
        total += stage.get("total", 0)
        correct += stage.get("correct", 0)
    smoke_pass_rate = correct / total if total > 0 else 0.0

    return {
        "accuracy": accuracy,
        "latency_p95": 0,
        "error_rate": error_rate,
        "smoke_pass_rate": smoke_pass_rate,
        "source": filepath,
    }


def _load_metrics_from_data_json(pipeline: str) -> dict:
    """Load metrics from docs/data.json."""
    if not os.path.exists(DATA_JSON):
        return {}
    with open(DATA_JSON) as f:
        data = json.load(f)
    pipe_data = data.get("pipelines", {}).get(pipeline, {})
    if not pipe_data:
        return {}

    accuracy = 0.0
    trends = pipe_data.get("accuracy_trend", [])
    if trends:
        accuracy = trends[-1]
    elif "accuracy" in pipe_data:
        accuracy = pipe_data["accuracy"]

    latency_p95 = pipe_data.get("latency_p95", 0)
    error_rate = pipe_data.get("error_rate", 0.0)

    quick_tests = data.get("quick_tests", [])
    pipe_tests = [t for t in quick_tests if t.get("pipeline") == pipeline]
    if pipe_tests:
        recent = pipe_tests[-5:]
        passed = sum(1 for t in recent if t.get("status") == "pass")
        smoke_pass_rate = passed / len(recent)
    else:
        smoke_pass_rate = accuracy / 100.0

    return {
        "accuracy": accuracy,
        "latency_p95": latency_p95,
        "error_rate": error_rate,
        "smoke_pass_rate": smoke_pass_rate,
        "source": DATA_JSON,
    }


def _load_metrics_from_supabase(pipeline: str) -> dict:
    """Try to load metrics from Supabase benchmark_results (best-effort).

    Requires SUPABASE_URL in environment. Falls back gracefully.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    if not supabase_url:
        return {}

    try:
        import subprocess
        result = subprocess.run(
            [
                "psql", supabase_url, "-t", "-A", "-c",
                f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN (metrics->>'accuracy')::float >= 0.5 THEN 1 END) as correct,
                    AVG(latency_ms) as avg_latency,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
                    COUNT(CASE WHEN error IS NOT NULL THEN 1 END)::float / NULLIF(COUNT(*), 0) * 100 as error_rate
                FROM benchmark_results
                WHERE dataset_name = '{pipeline}'
                  AND created_at > NOW() - INTERVAL '24 hours';
                """,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {}

        parts = result.stdout.strip().split("|")
        if len(parts) < 5:
            return {}

        total = int(parts[0]) if parts[0] else 0
        correct = int(parts[1]) if parts[1] else 0
        avg_lat = float(parts[2]) if parts[2] else 0
        p95_lat = float(parts[3]) if parts[3] else 0
        err_rate = float(parts[4]) if parts[4] else 0

        if total == 0:
            return {}

        accuracy = round(correct / total * 100, 1)
        return {
            "accuracy": accuracy,
            "latency_p95": int(p95_lat),
            "error_rate": round(err_rate, 1),
            "smoke_pass_rate": correct / total,
            "source": "supabase",
        }
    except Exception:
        return {}


def load_pipeline_metrics(pipeline: str, results_file: str = None) -> dict:
    """Load metrics for a pipeline from the best available source.

    Priority:
      1. golden-check.get_metrics (if imported successfully)
      2. Explicit results_file
      3. Latest iterative-eval file
      4. docs/data.json
      5. Supabase (if SUPABASE_URL set)
    """
    # Use golden-check's unified loader if available
    if get_metrics is not None:
        metrics = get_metrics(pipeline, results_file)
        if metrics:
            return metrics

    # Manual fallback chain
    if results_file and os.path.exists(results_file):
        m = _load_metrics_from_results_file(results_file, pipeline)
        if m:
            return m

    latest = _find_latest_results_file()
    if latest:
        m = _load_metrics_from_results_file(latest, pipeline)
        if m:
            return m

    m = _load_metrics_from_data_json(pipeline)
    if m:
        return m

    m = _load_metrics_from_supabase(pipeline)
    if m:
        return m

    return {}


# ---------------------------------------------------------------------------
# Decision Matrix (from agentic-automation-spec.md Section 2.2)
# ---------------------------------------------------------------------------

def make_keep_revert_decision(pipeline: str, metrics: dict) -> dict:
    """Evaluate metrics against golden thresholds and return a KEEP/REVERT/HOLD decision.

    Args:
        pipeline: Pipeline name.
        metrics: Dict with keys: accuracy, latency_p95, error_rate, smoke_pass_rate.

    Returns:
        {
            "pipeline": str,
            "decision": "KEEP" | "REVERT" | "HOLD",
            "reasons": [str],
            "confidence": float (0.0 - 1.0),
            "metrics": dict,
            "golden": dict,
            "timestamp": str,
        }
    """
    if pipeline not in GOLDEN_THRESHOLDS:
        return {
            "pipeline": pipeline,
            "decision": "HOLD",
            "reasons": [f"Unknown pipeline: {pipeline}. Cannot evaluate."],
            "confidence": 0.0,
            "metrics": metrics,
            "golden": {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    if not metrics:
        return {
            "pipeline": pipeline,
            "decision": "HOLD",
            "reasons": ["No metrics available. Cannot make informed decision."],
            "confidence": 0.0,
            "metrics": {},
            "golden": GOLDEN_THRESHOLDS[pipeline],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    golden = GOLDEN_THRESHOLDS[pipeline]
    reasons = []
    confidence = 1.0

    accuracy = metrics.get("accuracy", 0.0)
    latency_p95 = metrics.get("latency_p95", 0)
    error_rate = metrics.get("error_rate", 0.0)
    smoke_pass_rate = metrics.get("smoke_pass_rate", 0.0)

    # ---- Critical: accuracy regression >10% from golden => auto REVERT ----
    critical_threshold = golden["min_accuracy"] * 0.9
    if accuracy < critical_threshold:
        reasons.append(
            f"CRITICAL: Accuracy {accuracy:.1f}% < 90% of golden "
            f"({critical_threshold:.1f}%). Severe regression detected."
        )
        return {
            "pipeline": pipeline,
            "decision": "REVERT",
            "reasons": reasons,
            "confidence": 1.0,
            "metrics": metrics,
            "golden": golden,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    # ---- Warning: accuracy below golden ----
    if accuracy < golden["min_accuracy"]:
        gap = golden["min_accuracy"] - accuracy
        reasons.append(
            f"WARNING: Accuracy {accuracy:.1f}% < golden {golden['min_accuracy']:.1f}% "
            f"(gap: {gap:.1f}pp)"
        )
        confidence -= 0.2

    # ---- Smoke test failure ----
    if smoke_pass_rate < golden["required_smoke_pass"]:
        reasons.append(
            f"CRITICAL: Smoke pass rate {smoke_pass_rate:.2f} < required "
            f"{golden['required_smoke_pass']:.2f}"
        )
        confidence -= 0.4

    # ---- Error spike (>2x threshold) ----
    if error_rate > golden["max_error_rate"] * 2:
        reasons.append(
            f"CRITICAL: Error rate {error_rate:.1f}% > 2x threshold "
            f"({golden['max_error_rate'] * 2:.1f}%)"
        )
        confidence -= 0.3
    elif error_rate > golden["max_error_rate"]:
        reasons.append(
            f"WARNING: Error rate {error_rate:.1f}% > threshold "
            f"{golden['max_error_rate']:.1f}%"
        )
        confidence -= 0.1

    # ---- Latency degradation (>1.5x threshold) ----
    if latency_p95 > 0 and latency_p95 > golden["max_latency_p95"] * 1.5:
        reasons.append(
            f"WARNING: P95 latency {latency_p95}ms > 1.5x threshold "
            f"({int(golden['max_latency_p95'] * 1.5)}ms)"
        )
        confidence -= 0.1
    elif latency_p95 > 0 and latency_p95 > golden["max_latency_p95"]:
        reasons.append(
            f"INFO: P95 latency {latency_p95}ms > threshold "
            f"{golden['max_latency_p95']}ms (minor)"
        )
        confidence -= 0.05

    # ---- Positive signals ----
    if accuracy >= golden["min_accuracy"] and not reasons:
        reasons.append(
            f"All metrics within golden thresholds. "
            f"Accuracy {accuracy:.1f}% >= {golden['min_accuracy']:.1f}%."
        )

    # Clamp confidence
    confidence = max(0.0, min(1.0, confidence))

    # Decision based on remaining confidence
    if confidence >= 0.7:
        decision = "KEEP"
    elif confidence >= 0.4:
        decision = "HOLD"
    else:
        decision = "REVERT"

    return {
        "pipeline": pipeline,
        "decision": decision,
        "reasons": reasons,
        "confidence": round(confidence, 3),
        "metrics": metrics,
        "golden": golden,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# Multi-pipeline check
# ---------------------------------------------------------------------------

def check_all_pipelines(results_file: str = None) -> dict:
    """Run the decision engine on all pipelines."""
    decisions = {}
    summary_counts = {"KEEP": 0, "REVERT": 0, "HOLD": 0}

    for pipeline in ALL_PIPELINES:
        metrics = load_pipeline_metrics(pipeline, results_file)
        result = make_keep_revert_decision(pipeline, metrics)
        decisions[pipeline] = result
        summary_counts[result["decision"]] += 1

    return {
        "decisions": decisions,
        "summary": summary_counts,
        "any_revert": summary_counts["REVERT"] > 0,
        "all_keep": summary_counts["KEEP"] == len(ALL_PIPELINES),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# Test mode — synthetic data for dry-run validation
# ---------------------------------------------------------------------------

def run_test_mode():
    """Run the decision engine with synthetic test data to validate logic."""
    test_cases = [
        {
            "label": "Standard - healthy (should KEEP)",
            "pipeline": "standard",
            "metrics": {
                "accuracy": 88.0,
                "latency_p95": 3000,
                "error_rate": 2.0,
                "smoke_pass_rate": 0.9,
            },
            "expected_decision": "KEEP",
        },
        {
            "label": "Graph - critical regression (should REVERT)",
            "pipeline": "graph",
            "metrics": {
                "accuracy": 55.0,  # < 70 * 0.9 = 63
                "latency_p95": 12000,
                "error_rate": 25.0,
                "smoke_pass_rate": 0.3,
            },
            "expected_decision": "REVERT",
        },
        {
            "label": "Quantitative - borderline (should HOLD)",
            "pipeline": "quantitative",
            "metrics": {
                "accuracy": 82.0,  # below 85 but above 85*0.9=76.5 (-0.2)
                "latency_p95": 9000,
                "error_rate": 4.0,  # within threshold
                "smoke_pass_rate": 0.75,  # below 0.8 (-0.4) => confidence 0.4 => HOLD
            },
            "expected_decision": "HOLD",
        },
        {
            "label": "Orchestrator - mild degradation (should KEEP)",
            "pipeline": "orchestrator",
            "metrics": {
                "accuracy": 72.0,
                "latency_p95": 14000,
                "error_rate": 8.0,
                "smoke_pass_rate": 0.7,
            },
            "expected_decision": "KEEP",
        },
        {
            "label": "Standard - total failure (should REVERT)",
            "pipeline": "standard",
            "metrics": {
                "accuracy": 20.0,
                "latency_p95": 25000,
                "error_rate": 60.0,
                "smoke_pass_rate": 0.1,
            },
            "expected_decision": "REVERT",
        },
        {
            "label": "Nomos42 - no data (should HOLD)",
            "pipeline": "nomos42",
            "metrics": {},
            "expected_decision": "HOLD",
        },
    ]

    print("=" * 60)
    print("  DECISION ENGINE — TEST MODE (dry-run)")
    print("=" * 60)

    all_ok = True
    results = []

    for tc in test_cases:
        result = make_keep_revert_decision(tc["pipeline"], tc["metrics"])
        match = result["decision"] == tc["expected_decision"]
        status = "OK" if match else "MISMATCH"
        if not match:
            all_ok = False

        print(f"\n  [{status}] {tc['label']}")
        print(f"    Decision: {result['decision']} (expected: {tc['expected_decision']})")
        print(f"    Confidence: {result['confidence']}")
        for reason in result["reasons"]:
            print(f"    - {reason}")

        results.append({
            "label": tc["label"],
            "status": status,
            "decision": result["decision"],
            "expected": tc["expected_decision"],
            "confidence": result["confidence"],
        })

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r["status"] == "OK")
    total = len(results)
    print(f"  Test Results: {passed}/{total} passed")
    if all_ok:
        print("  All test cases matched expected decisions.")
    else:
        print("  WARNING: Some test cases did not match. Review logic.")
    print("=" * 60)

    return {"passed": all_ok, "results": results}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Decision Engine - KEEP/REVERT/HOLD decisions for RAG pipelines"
    )
    parser.add_argument(
        "--pipeline", "-p",
        type=str,
        choices=ALL_PIPELINES,
        help="Pipeline to evaluate",
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Check all pipelines",
    )
    parser.add_argument(
        "--results-file", "-r",
        type=str,
        default=None,
        help="Path to a specific eval results JSON file",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode with synthetic data (dry-run validation)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only output JSON, no human-readable summary",
    )
    args = parser.parse_args()

    # Test mode
    if args.test:
        test_result = run_test_mode()
        if args.quiet:
            print(json.dumps(test_result, indent=2 if args.pretty else None))
        sys.exit(0 if test_result["passed"] else 1)

    # Check all pipelines
    if args.check_all:
        result = check_all_pipelines(results_file=args.results_file)
        indent = 2 if args.pretty else None

        if not args.quiet:
            print("=" * 60, file=sys.stderr)
            print("  DECISION ENGINE — All Pipelines", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            for name, dec in result["decisions"].items():
                emoji = {"KEEP": "[KEEP]", "REVERT": "[REVERT]", "HOLD": "[HOLD]"}
                tag = emoji.get(dec["decision"], "[?]")
                print(f"  {tag} {name}: confidence={dec['confidence']}", file=sys.stderr)
                for r in dec["reasons"]:
                    print(f"    - {r}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            s = result["summary"]
            print(
                f"  Summary: KEEP={s['KEEP']} HOLD={s['HOLD']} REVERT={s['REVERT']}",
                file=sys.stderr,
            )
            if result["any_revert"]:
                print("  ACTION REQUIRED: At least one pipeline needs REVERT.", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

        print(json.dumps(result, indent=indent))
        sys.exit(0 if not result["any_revert"] else 1)

    # Single pipeline
    if args.pipeline:
        metrics = load_pipeline_metrics(args.pipeline, args.results_file)
        result = make_keep_revert_decision(args.pipeline, metrics)
        indent = 2 if args.pretty else None

        if not args.quiet:
            tag = {"KEEP": "[KEEP]", "REVERT": "[REVERT]", "HOLD": "[HOLD]"}.get(
                result["decision"], "[?]"
            )
            print("=" * 60, file=sys.stderr)
            print(
                f"  DECISION ENGINE — {result['pipeline']} — {tag}",
                file=sys.stderr,
            )
            print(f"  Confidence: {result['confidence']}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            for r in result["reasons"]:
                print(f"  - {r}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

        print(json.dumps(result, indent=indent))
        sys.exit(0 if result["decision"] != "REVERT" else 1)

    # No pipeline specified and not --check-all or --test
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
