#!/usr/bin/env python3
"""
Golden Check — Validate pipeline results against golden thresholds.
====================================================================
Compares accuracy, latency (P95), error rate, and smoke-test pass rate
against per-pipeline golden thresholds. Returns structured PASS/FAIL
JSON to stdout.

Can be used:
  - Standalone CLI:
      python3 eval/golden-check.py --pipeline standard
      python3 eval/golden-check.py --pipeline graph --results-file logs/iterative-eval/latest.json
      python3 eval/golden-check.py --all

  - As importable module:
      from golden_check import GOLDEN_THRESHOLDS, run_golden_check
      result = run_golden_check("standard", metrics)
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
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
DATA_JSON = os.path.join(REPO_ROOT, "docs", "data.json")
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
ITERATIVE_DIR = os.path.join(LOGS_DIR, "iterative-eval")
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

# ---------------------------------------------------------------------------
# Load .env.local (best-effort, no hard dependency on python-dotenv)
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
# Golden Thresholds — single source of truth (from agentic-automation-spec.md)
# ---------------------------------------------------------------------------
GOLDEN_THRESHOLDS = {
    "standard": {
        "min_accuracy": 85.0,
        "max_latency_p95": 5000,       # ms
        "max_error_rate": 5.0,         # %
        "required_smoke_pass": 4 / 5,  # 0.8
    },
    "graph": {
        "min_accuracy": 70.0,
        "max_latency_p95": 8000,
        "max_error_rate": 10.0,
        "required_smoke_pass": 3 / 5,  # 0.6
    },
    "quantitative": {
        "min_accuracy": 85.0,
        "max_latency_p95": 10000,
        "max_error_rate": 5.0,
        "required_smoke_pass": 4 / 5,  # 0.8
    },
    "orchestrator": {
        "min_accuracy": 70.0,
        "max_latency_p95": 15000,
        "max_error_rate": 10.0,
        "required_smoke_pass": 3 / 5,  # 0.6
    },
    "nomos42": {
        "min_accuracy": 75.0,
        "max_latency_p95": 5000,
        "max_error_rate": 15.0,
        "required_smoke_pass": 3 / 4,  # 0.75
    },
}

ALL_PIPELINES = list(GOLDEN_THRESHOLDS.keys())


# ---------------------------------------------------------------------------
# Metrics extraction helpers
# ---------------------------------------------------------------------------

def _extract_metrics_from_results_file(filepath: str, pipeline: str) -> dict:
    """Extract metrics from an iterative-eval JSON results file."""
    with open(filepath) as f:
        data = json.load(f)

    pipe_data = data.get("pipelines", {}).get(pipeline, {})
    if not pipe_data:
        return {}

    accuracy = pipe_data.get("final_accuracy", 0.0)
    error_rate = pipe_data.get("final_error_rate", 0.0)

    # Attempt to compute latency stats from stage details
    latencies = []
    for stage in pipe_data.get("stage_details", []):
        if "latencies" in stage:
            latencies.extend(stage["latencies"])

    latency_p95 = 0
    if latencies:
        latencies.sort()
        idx = int(len(latencies) * 0.95)
        latency_p95 = latencies[min(idx, len(latencies) - 1)]

    # Smoke pass rate: ratio of correct / total
    total = pipe_data.get("stage_details", [{}])[0].get("total", 0) if pipe_data.get("stage_details") else 0
    correct = pipe_data.get("stage_details", [{}])[0].get("correct", 0) if pipe_data.get("stage_details") else 0
    smoke_pass_rate = correct / total if total > 0 else 0.0

    return {
        "accuracy": accuracy,
        "latency_p95": latency_p95,
        "error_rate": error_rate,
        "smoke_pass_rate": smoke_pass_rate,
        "source": filepath,
        "total_tested": total,
    }


def _extract_metrics_from_data_json(pipeline: str) -> dict:
    """Extract metrics from the global docs/data.json dashboard file."""
    if not os.path.exists(DATA_JSON):
        return {}

    with open(DATA_JSON) as f:
        data = json.load(f)

    pipe_data = data.get("pipelines", {}).get(pipeline, {})
    if not pipe_data:
        return {}

    # Accuracy: last value in trend array, or direct field
    accuracy = 0.0
    trends = pipe_data.get("accuracy_trend", [])
    if trends:
        accuracy = trends[-1]
    elif "accuracy" in pipe_data:
        accuracy = pipe_data["accuracy"]

    # Latency P95
    latency_p95 = pipe_data.get("latency_p95", 0)
    if not latency_p95:
        latency_p95 = pipe_data.get("avg_latency_ms", 0) * 1.5  # rough estimate

    # Error rate
    error_rate = pipe_data.get("error_rate", 0.0)

    # Smoke pass rate from quick tests
    quick_tests = data.get("quick_tests", [])
    pipe_tests = [t for t in quick_tests if t.get("pipeline") == pipeline]
    if pipe_tests:
        recent = pipe_tests[-5:]  # last 5
        passed = sum(1 for t in recent if t.get("status") == "pass")
        smoke_pass_rate = passed / len(recent)
    else:
        smoke_pass_rate = accuracy / 100.0  # fallback: use accuracy as proxy

    total_tested = pipe_data.get("total_tested", 0)

    return {
        "accuracy": accuracy,
        "latency_p95": latency_p95,
        "error_rate": error_rate,
        "smoke_pass_rate": smoke_pass_rate,
        "source": DATA_JSON,
        "total_tested": total_tested,
    }


def _find_latest_results_file() -> str:
    """Find the most recent iterative-eval results file."""
    pattern = os.path.join(ITERATIVE_DIR, "iterative-*.json")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else ""


def get_metrics(pipeline: str, results_file: str = None) -> dict:
    """Get metrics for a pipeline from the best available source.

    Priority:
      1. Explicit results_file
      2. Latest iterative-eval JSON
      3. docs/data.json
    """
    if results_file and os.path.exists(results_file):
        metrics = _extract_metrics_from_results_file(results_file, pipeline)
        if metrics:
            return metrics

    # Try latest iterative eval
    latest = _find_latest_results_file()
    if latest:
        metrics = _extract_metrics_from_results_file(latest, pipeline)
        if metrics:
            return metrics

    # Fallback to data.json
    return _extract_metrics_from_data_json(pipeline)


# ---------------------------------------------------------------------------
# Core check logic
# ---------------------------------------------------------------------------

def run_golden_check(pipeline: str, metrics: dict = None, results_file: str = None) -> dict:
    """Run golden threshold validation for a single pipeline.

    Args:
        pipeline: Pipeline name (standard, graph, quantitative, orchestrator, nomos42)
        metrics: Pre-computed metrics dict. If None, will be loaded from files.
        results_file: Path to a specific results JSON file.

    Returns:
        {
            "pipeline": str,
            "passed": bool,
            "checks": {
                "accuracy": {"value": float, "threshold": float, "passed": bool},
                "latency_p95": {...},
                "error_rate": {...},
                "smoke_pass_rate": {...},
            },
            "failed_checks": [str],
            "metrics_source": str,
            "timestamp": str,
        }
    """
    if pipeline not in GOLDEN_THRESHOLDS:
        return {
            "pipeline": pipeline,
            "passed": False,
            "checks": {},
            "failed_checks": [f"Unknown pipeline: {pipeline}"],
            "metrics_source": "none",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    golden = GOLDEN_THRESHOLDS[pipeline]

    if metrics is None:
        metrics = get_metrics(pipeline, results_file)

    if not metrics:
        return {
            "pipeline": pipeline,
            "passed": False,
            "checks": {},
            "failed_checks": ["No metrics available (no results file or data.json)"],
            "metrics_source": "none",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    checks = {}
    failed_checks = []

    # 1. Accuracy check
    acc_value = metrics.get("accuracy", 0.0)
    acc_threshold = golden["min_accuracy"]
    acc_passed = acc_value >= acc_threshold
    checks["accuracy"] = {
        "value": acc_value,
        "threshold": acc_threshold,
        "passed": acc_passed,
        "detail": f"{acc_value:.1f}% {'>=' if acc_passed else '<'} {acc_threshold:.1f}%",
    }
    if not acc_passed:
        failed_checks.append(f"accuracy: {acc_value:.1f}% < {acc_threshold:.1f}%")

    # 2. Latency P95 check
    lat_value = metrics.get("latency_p95", 0)
    lat_threshold = golden["max_latency_p95"]
    lat_passed = lat_value <= lat_threshold or lat_value == 0  # 0 = no data, skip
    checks["latency_p95"] = {
        "value": lat_value,
        "threshold": lat_threshold,
        "passed": lat_passed,
        "detail": f"{lat_value}ms {'<=' if lat_passed else '>'} {lat_threshold}ms",
    }
    if not lat_passed:
        failed_checks.append(f"latency_p95: {lat_value}ms > {lat_threshold}ms")

    # 3. Error rate check
    err_value = metrics.get("error_rate", 0.0)
    err_threshold = golden["max_error_rate"]
    err_passed = err_value <= err_threshold
    checks["error_rate"] = {
        "value": err_value,
        "threshold": err_threshold,
        "passed": err_passed,
        "detail": f"{err_value:.1f}% {'<=' if err_passed else '>'} {err_threshold:.1f}%",
    }
    if not err_passed:
        failed_checks.append(f"error_rate: {err_value:.1f}% > {err_threshold:.1f}%")

    # 4. Smoke pass rate check
    smoke_value = metrics.get("smoke_pass_rate", 0.0)
    smoke_threshold = golden["required_smoke_pass"]
    smoke_passed = smoke_value >= smoke_threshold
    checks["smoke_pass_rate"] = {
        "value": round(smoke_value, 3),
        "threshold": round(smoke_threshold, 3),
        "passed": smoke_passed,
        "detail": f"{smoke_value:.2f} {'>=' if smoke_passed else '<'} {smoke_threshold:.2f}",
    }
    if not smoke_passed:
        failed_checks.append(f"smoke_pass_rate: {smoke_value:.2f} < {smoke_threshold:.2f}")

    all_passed = len(failed_checks) == 0

    return {
        "pipeline": pipeline,
        "passed": all_passed,
        "checks": checks,
        "failed_checks": failed_checks,
        "metrics_source": metrics.get("source", "unknown"),
        "total_tested": metrics.get("total_tested", 0),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def run_all_golden_checks(results_file: str = None) -> dict:
    """Run golden checks on all pipelines. Returns aggregated result."""
    results = {}
    all_passed = True

    for pipeline in ALL_PIPELINES:
        result = run_golden_check(pipeline, results_file=results_file)
        results[pipeline] = result
        if not result["passed"]:
            all_passed = False

    return {
        "all_passed": all_passed,
        "pipelines": results,
        "checked_count": len(results),
        "passed_count": sum(1 for r in results.values() if r["passed"]),
        "failed_count": sum(1 for r in results.values() if not r["passed"]),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Golden Check - validate pipeline results against golden thresholds"
    )
    parser.add_argument(
        "--pipeline", "-p",
        type=str,
        choices=ALL_PIPELINES,
        help="Pipeline to check (default: all)",
    )
    parser.add_argument(
        "--all", "-a",
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

    if args.all or (args.pipeline is None):
        result = run_all_golden_checks(results_file=args.results_file)
    else:
        result = run_golden_check(args.pipeline, results_file=args.results_file)

    # JSON output to stdout
    indent = 2 if args.pretty else None
    json_out = json.dumps(result, indent=indent)

    if args.quiet:
        print(json_out)
    else:
        # Human-readable summary to stderr, JSON to stdout
        if "pipelines" in result:
            # Multi-pipeline result
            print("=" * 60, file=sys.stderr)
            print("  GOLDEN CHECK — All Pipelines", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            for name, pr in result["pipelines"].items():
                status = "PASS" if pr["passed"] else "FAIL"
                print(f"  [{status}] {name}", file=sys.stderr)
                for check_name, check_data in pr.get("checks", {}).items():
                    sym = "[+]" if check_data["passed"] else "[-]"
                    print(f"    {sym} {check_name}: {check_data['detail']}", file=sys.stderr)
                if pr["failed_checks"]:
                    for fc in pr["failed_checks"]:
                        print(f"    FAIL: {fc}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            overall = "PASS" if result["all_passed"] else "FAIL"
            print(
                f"  Overall: {overall} "
                f"({result['passed_count']}/{result['checked_count']} passed)",
                file=sys.stderr,
            )
            print("=" * 60, file=sys.stderr)
        else:
            # Single pipeline result
            status = "PASS" if result["passed"] else "FAIL"
            print("=" * 60, file=sys.stderr)
            print(f"  GOLDEN CHECK — {result['pipeline']} — {status}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            for check_name, check_data in result.get("checks", {}).items():
                sym = "[+]" if check_data["passed"] else "[-]"
                print(f"  {sym} {check_name}: {check_data['detail']}", file=sys.stderr)
            if result["failed_checks"]:
                print(f"\n  Failed checks:", file=sys.stderr)
                for fc in result["failed_checks"]:
                    print(f"    - {fc}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)

        # JSON to stdout
        print(json_out)

    # Exit code: 0 = PASS, 1 = FAIL
    if "all_passed" in result:
        sys.exit(0 if result["all_passed"] else 1)
    else:
        sys.exit(0 if result.get("passed", False) else 1)


if __name__ == "__main__":
    main()
