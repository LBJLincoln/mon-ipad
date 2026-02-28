#!/usr/bin/env python3
"""
Populate Trading Board — Write pipeline metrics to Supabase trading_board_snapshots.
====================================================================================
After each eval run, this script extracts metrics from data.json (or custom results file)
and writes a snapshot to the trading_board_snapshots table, powering the live trading board UI.

Usage:
  python3 scripts/populate-trading-board.py                    # Auto from data.json
  python3 scripts/populate-trading-board.py --results-file X   # From specific file
  python3 scripts/populate-trading-board.py --dry-run          # Preview without writing

Integration with eval pipeline:
  # After running iterative-eval
  source .env.local
  python3 eval/iterative-eval.py --label "Phase2-batch1"
  python3 scripts/populate-trading-board.py

  # After decision engine
  DECISION=$(python3 scripts/decision-engine.py --pipeline standard --quiet | jq -r '.decision')
  python3 scripts/populate-trading-board.py --last-decision "$DECISION" --last-decision-pipeline standard

  # From custom results file
  python3 scripts/populate-trading-board.py --results-file logs/iterative-eval/iterative-20260227.json

Schema:
  trading_board_snapshots:
    - best_pipeline, best_accuracy, best_latency_p95, best_since
    - worst_pipeline, worst_accuracy, worst_latency_p95, worst_since
    - middle_pipelines (jsonb), total_tests_24h, overall_accuracy
    - active_alerts_count, last_decision, last_decision_pipeline, last_decision_at
    - alert_feed (jsonb)

  bug_signatures:
    - signature_id, pipeline, source, detected_at, execution_id
    - error_snippet, metadata (jsonb), acknowledged, auto_action_taken, fix_applied
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_JSON = os.path.join(REPO_ROOT, "docs", "data.json")
EVAL_DIR = os.path.join(REPO_ROOT, "eval")
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

# ---------------------------------------------------------------------------
# Load .env.local
# ---------------------------------------------------------------------------
def _load_env_local():
    """Parse .env.local and inject into os.environ (skip comments/blanks)."""
    if not os.path.exists(ENV_FILE):
        print(f"WARNING: {ENV_FILE} not found. Supabase credentials required.", file=sys.stderr)
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
# Import golden thresholds (for best/worst classification)
# ---------------------------------------------------------------------------
sys.path.insert(0, EVAL_DIR)
try:
    from importlib.machinery import SourceFileLoader
    _gc = SourceFileLoader("golden_check", os.path.join(EVAL_DIR, "golden-check.py")).load_module()
    GOLDEN_THRESHOLDS = _gc.GOLDEN_THRESHOLDS
except Exception:
    # Fallback inline
    GOLDEN_THRESHOLDS = {
        "standard":     {"min_accuracy": 85.0, "max_latency_p95": 5000},
        "graph":        {"min_accuracy": 70.0, "max_latency_p95": 8000},
        "quantitative": {"min_accuracy": 85.0, "max_latency_p95": 10000},
        "orchestrator": {"min_accuracy": 70.0, "max_latency_p95": 15000},
        "nomos42":      {"min_accuracy": 75.0, "max_latency_p95": 5000},
    }

ALL_PIPELINES = list(GOLDEN_THRESHOLDS.keys())

# ---------------------------------------------------------------------------
# Metrics extraction from data.json
# ---------------------------------------------------------------------------

def _load_data_json(filepath: str = DATA_JSON) -> dict:
    """Load and parse data.json or custom results file."""
    if not os.path.exists(filepath):
        print(f"ERROR: {filepath} not found.", file=sys.stderr)
        sys.exit(1)

    with open(filepath) as f:
        return json.load(f)


def _extract_pipeline_metrics_from_data_json(data: dict) -> dict:
    """Extract per-pipeline metrics from data.json structure.

    Returns:
        {
            "standard": {"accuracy": 85.5, "latency_p95": 3200, "error_rate": 2.0, "total_tested": 200},
            "graph": {...},
            ...
        }
    """
    metrics = {}

    # Check if it's iterative-eval format (has "pipelines" key)
    if "pipelines" in data:
        for pipeline, pipe_data in data["pipelines"].items():
            accuracy = pipe_data.get("final_accuracy", 0.0)
            error_rate = pipe_data.get("final_error_rate", 0.0)

            # Extract latency from stage details
            latencies = []
            for stage in pipe_data.get("stage_details", []):
                if "latencies" in stage:
                    latencies.extend(stage["latencies"])

            latency_p95 = 0
            if latencies:
                latencies.sort()
                idx = int(len(latencies) * 0.95)
                latency_p95 = latencies[min(idx, len(latencies) - 1)]

            total = 0
            for stage in pipe_data.get("stage_details", []):
                total += stage.get("total", 0)

            metrics[pipeline] = {
                "accuracy": accuracy,
                "latency_p95": int(latency_p95),
                "error_rate": error_rate,
                "total_tested": total,
            }

    # Otherwise try data.json format (prioritize iterations over quick_tests)
    else:
        # First, try to get latest metrics from most recent iterations
        iterations = data.get("iterations", [])

        # Get last iteration with results_summary
        latest_results = {}
        for iteration in reversed(iterations[-20:]):  # Check last 20 iterations
            results_summary = iteration.get("results_summary", {})
            if results_summary:
                for pipeline, pipe_results in results_summary.items():
                    if pipeline not in latest_results and pipe_results.get("tested", 0) > 0:
                        latest_results[pipeline] = {
                            "accuracy": pipe_results.get("accuracy_pct", 0.0),
                            "latency_p95": pipe_results.get("p95_latency_ms", 0),
                            "error_rate": (pipe_results.get("errors", 0) / max(pipe_results.get("tested", 1), 1)) * 100,
                            "total_tested": pipe_results.get("tested", 0),
                        }

        # If we found results from iterations, use them
        if latest_results:
            metrics = latest_results

        # Otherwise fallback to quick_tests (less reliable)
        else:
            quick_tests = data.get("quick_tests", [])
            for pipeline in ALL_PIPELINES:
                pipe_tests = [t for t in quick_tests if t.get("pipeline") == pipeline]

                if not pipe_tests:
                    continue

                recent = pipe_tests[-10:]  # last 10 tests

                # Calculate accuracy from recent tests
                passed = sum(1 for t in recent if t.get("status") == "pass")
                accuracy = (passed / len(recent)) * 100 if recent else 0.0

                # Extract latency (if available)
                latencies = [t.get("latency_ms", 0) for t in recent if t.get("latency_ms")]
                latency_p95 = 0
                if latencies:
                    latencies.sort()
                    idx = int(len(latencies) * 0.95)
                    latency_p95 = latencies[min(idx, len(latencies) - 1)]

                # Extract error rate
                errors = sum(1 for t in recent if t.get("status") == "error")
                error_rate = (errors / len(recent)) * 100 if recent else 0.0

                metrics[pipeline] = {
                    "accuracy": round(accuracy, 1),
                    "latency_p95": int(latency_p95),
                    "error_rate": round(error_rate, 1),
                    "total_tested": len(recent),
                }

        # Calculate 24h test volume from iterations
        cutoff = datetime.utcnow() - timedelta(hours=24)
        for iteration in data.get("iterations", []):
            timestamp = iteration.get("timestamp_start", "")
            if not timestamp:
                continue
            try:
                # Handle both Z and +XX:XX timezone formats
                ts_str = timestamp.replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_str)
                if ts < cutoff:
                    continue
            except:
                continue

            for pipeline in ALL_PIPELINES:
                results = iteration.get("results_summary", {}).get(pipeline, {})
                if results and pipeline in metrics:
                    # Accumulate 24h tests (don't overwrite accuracy from latest)
                    metrics[pipeline]["total_tested"] += results.get("tested", 0)

    return metrics


def _calculate_overall_metrics(pipeline_metrics: dict) -> dict:
    """Calculate overall metrics and rank pipelines.

    Returns:
        {
            "best_pipeline": str,
            "best_accuracy": float,
            "best_latency_p95": int,
            "worst_pipeline": str,
            "worst_accuracy": float,
            "worst_latency_p95": int,
            "middle_pipelines": [{"pipeline": str, "accuracy": float, "latency_p95": int}],
            "overall_accuracy": float,
            "total_tests_24h": int,
        }
    """
    if not pipeline_metrics:
        return {
            "best_pipeline": None,
            "best_accuracy": 0.0,
            "best_latency_p95": 0,
            "worst_pipeline": None,
            "worst_accuracy": 0.0,
            "worst_latency_p95": 0,
            "middle_pipelines": [],
            "overall_accuracy": 0.0,
            "total_tests_24h": 0,
        }

    # Sort by accuracy descending
    sorted_pipes = sorted(
        pipeline_metrics.items(),
        key=lambda x: x[1]["accuracy"],
        reverse=True
    )

    best_name, best_data = sorted_pipes[0]
    worst_name, worst_data = sorted_pipes[-1]

    middle = []
    if len(sorted_pipes) > 2:
        for name, data in sorted_pipes[1:-1]:
            middle.append({
                "pipeline": name,
                "accuracy": data["accuracy"],
                "latency_p95": data["latency_p95"],
            })

    # Calculate overall accuracy (weighted by tests)
    total_tested = sum(p["total_tested"] for p in pipeline_metrics.values())
    if total_tested > 0:
        weighted_accuracy = sum(
            p["accuracy"] * p["total_tested"] for p in pipeline_metrics.values()
        ) / total_tested
    else:
        weighted_accuracy = sum(p["accuracy"] for p in pipeline_metrics.values()) / len(pipeline_metrics)

    return {
        "best_pipeline": best_name,
        "best_accuracy": best_data["accuracy"],
        "best_latency_p95": best_data["latency_p95"],
        "worst_pipeline": worst_name,
        "worst_accuracy": worst_data["accuracy"],
        "worst_latency_p95": worst_data["latency_p95"],
        "middle_pipelines": middle,
        "overall_accuracy": round(weighted_accuracy, 1),
        "total_tests_24h": total_tested,
    }


def _detect_errors_and_bugs(data: dict, pipeline_metrics: dict) -> list:
    """Scan for errors/bugs and return bug signatures for bug_signatures table.

    Returns:
        [
            {
                "signature_id": str,
                "pipeline": str,
                "source": str,
                "detected_at": str (ISO8601),
                "execution_id": str,
                "error_snippet": str,
                "metadata": dict,
                "acknowledged": bool,
                "auto_action_taken": str,
                "fix_applied": str,
            },
            ...
        ]
    """
    bugs = []
    now = datetime.utcnow().isoformat() + "Z"

    # Check for pipelines with high error rates
    for pipeline, metrics in pipeline_metrics.items():
        if metrics["error_rate"] > 20.0:
            bugs.append({
                "signature_id": f"high-error-rate-{pipeline}-{int(datetime.utcnow().timestamp())}",
                "pipeline": pipeline,
                "source": "automated-scan",
                "detected_at": now,
                "execution_id": None,
                "error_snippet": f"Error rate {metrics['error_rate']:.1f}% exceeds threshold",
                "metadata": {
                    "error_rate": metrics["error_rate"],
                    "accuracy": metrics["accuracy"],
                    "total_tested": metrics["total_tested"],
                },
                "acknowledged": False,
                "auto_action_taken": None,
                "fix_applied": None,
            })

    # Check for pipelines with accuracy below golden threshold
    for pipeline, metrics in pipeline_metrics.items():
        golden = GOLDEN_THRESHOLDS.get(pipeline, {})
        min_acc = golden.get("min_accuracy", 0)
        if min_acc > 0 and metrics["accuracy"] < min_acc * 0.9:  # Critical: <90% of golden
            bugs.append({
                "signature_id": f"accuracy-regression-{pipeline}-{int(datetime.utcnow().timestamp())}",
                "pipeline": pipeline,
                "source": "golden-check",
                "detected_at": now,
                "execution_id": None,
                "error_snippet": f"Accuracy {metrics['accuracy']:.1f}% < 90% of golden ({min_acc * 0.9:.1f}%)",
                "metadata": {
                    "accuracy": metrics["accuracy"],
                    "golden_threshold": min_acc,
                    "regression_severity": "critical",
                },
                "acknowledged": False,
                "auto_action_taken": "REVERT recommended",
                "fix_applied": None,
            })

    # Scan iterations for errors (if available)
    for iteration in data.get("iterations", [])[-10:]:  # last 10 iterations
        for pipeline in ALL_PIPELINES:
            results = iteration.get("results_summary", {}).get(pipeline, {})
            if results.get("error_count", 0) > 0:
                bugs.append({
                    "signature_id": f"iteration-error-{iteration.get('id', 'unknown')}-{pipeline}",
                    "pipeline": pipeline,
                    "source": "iteration-scan",
                    "detected_at": iteration.get("timestamp_start", now),
                    "execution_id": None,
                    "error_snippet": f"{results.get('error_count')} errors in iteration {iteration.get('number')}",
                    "metadata": {
                        "iteration_id": iteration.get("id"),
                        "error_count": results.get("error_count"),
                        "total": results.get("total", 0),
                    },
                    "acknowledged": False,
                    "auto_action_taken": None,
                    "fix_applied": None,
                })

    return bugs


# ---------------------------------------------------------------------------
# Supabase REST API
# ---------------------------------------------------------------------------

def _supabase_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Make a Supabase REST API request.

    Args:
        endpoint: e.g., "/rest/v1/trading_board_snapshots"
        method: GET, POST, PATCH, DELETE
        data: JSON payload for POST/PATCH

    Returns:
        Response data (parsed JSON)
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_API_KEY", "")

    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL and SUPABASE_API_KEY required in .env.local", file=sys.stderr)
        sys.exit(1)

    url = supabase_url + endpoint
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"  # Return inserted row
    }

    req_data = json.dumps(data).encode("utf-8") if data else None

    request = urllib.request.Request(
        url,
        data=req_data,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_data = response.read().decode("utf-8")
            if response_data:
                return json.loads(response_data)
            return {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"ERROR: Supabase API {method} {endpoint} failed: {e.code} {e.reason}", file=sys.stderr)
        print(f"Response: {error_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Supabase API request failed: {e}", file=sys.stderr)
        sys.exit(1)


def _write_trading_board_snapshot(snapshot: dict, dry_run: bool = False, show_request: bool = False) -> dict:
    """Write a snapshot to trading_board_snapshots table.

    Args:
        snapshot: Snapshot data dict
        dry_run: If True, only print what would be written
        show_request: If True, show the actual HTTP request details

    Returns:
        Inserted row (or snapshot if dry_run)
    """
    if dry_run:
        print("DRY RUN: Would write to trading_board_snapshots:", file=sys.stderr)
        print(json.dumps(snapshot, indent=2), file=sys.stderr)

        if show_request:
            supabase_url = os.environ.get("SUPABASE_URL", "")
            print(f"\nHTTP Request:", file=sys.stderr)
            print(f"  POST {supabase_url}/rest/v1/trading_board_snapshots", file=sys.stderr)
            print(f"  Headers:", file=sys.stderr)
            print(f"    apikey: <SUPABASE_API_KEY>", file=sys.stderr)
            print(f"    Authorization: Bearer <SUPABASE_API_KEY>", file=sys.stderr)
            print(f"    Content-Type: application/json", file=sys.stderr)
            print(f"    Prefer: return=representation", file=sys.stderr)

        return snapshot

    return _supabase_request("/rest/v1/trading_board_snapshots", method="POST", data=snapshot)


def _write_bug_signatures(bugs: list, dry_run: bool = False) -> list:
    """Write bug signatures to bug_signatures table.

    Args:
        bugs: List of bug signature dicts
        dry_run: If True, only print what would be written

    Returns:
        Inserted rows (or bugs if dry_run)
    """
    if not bugs:
        return []

    if dry_run:
        print(f"\nDRY RUN: Would write {len(bugs)} bug signatures:", file=sys.stderr)
        for bug in bugs:
            print(f"  - {bug['signature_id']}: {bug['error_snippet']}", file=sys.stderr)
        return bugs

    # Batch insert
    return _supabase_request("/rest/v1/bug_signatures", method="POST", data=bugs)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def populate_trading_board(
    results_file: str = None,
    dry_run: bool = False,
    last_decision: str = None,
    last_decision_pipeline: str = None,
    verbose: bool = False
):
    """Main function: extract metrics, calculate rankings, write to Supabase.

    Args:
        results_file: Path to results JSON (default: docs/data.json)
        dry_run: If True, preview without writing
        last_decision: Optional last decision (KEEP/REVERT/HOLD)
        last_decision_pipeline: Optional pipeline for last decision
        verbose: If True, show detailed output
    """
    filepath = results_file or DATA_JSON

    if verbose or dry_run:
        print(f"Loading metrics from: {filepath}", file=sys.stderr)
    else:
        print(f"Loading metrics...", file=sys.stderr)
    data = _load_data_json(filepath)

    if verbose or dry_run:
        print("Extracting pipeline metrics...", file=sys.stderr)
    pipeline_metrics = _extract_pipeline_metrics_from_data_json(data)

    if not pipeline_metrics:
        print("WARNING: No pipeline metrics found in data file.", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print("Pipeline metrics:", file=sys.stderr)
        for name, metrics in pipeline_metrics.items():
            print(f"  {name}: accuracy={metrics['accuracy']:.1f}%, latency_p95={metrics['latency_p95']}ms, error_rate={metrics['error_rate']:.1f}%", file=sys.stderr)

    if verbose or dry_run:
        print("Calculating overall rankings...", file=sys.stderr)
    overall = _calculate_overall_metrics(pipeline_metrics)

    if verbose or dry_run:
        print("Scanning for errors and bugs...", file=sys.stderr)
    bugs = _detect_errors_and_bugs(data, pipeline_metrics)

    # Build snapshot
    now = datetime.utcnow().isoformat() + "Z"

    snapshot = {
        "best_pipeline": overall["best_pipeline"],
        "best_accuracy": overall["best_accuracy"],
        "best_latency_p95": overall["best_latency_p95"],
        "best_since": now,  # Will be updated by triggers if best changes

        "worst_pipeline": overall["worst_pipeline"],
        "worst_accuracy": overall["worst_accuracy"],
        "worst_latency_p95": overall["worst_latency_p95"],
        "worst_since": now,

        "middle_pipelines": overall["middle_pipelines"],
        "total_tests_24h": overall["total_tests_24h"],
        "overall_accuracy": overall["overall_accuracy"],

        "active_alerts_count": len(bugs),
        "last_decision": last_decision,
        "last_decision_pipeline": last_decision_pipeline,
        "last_decision_at": now if last_decision else None,

        "alert_feed": [
            {
                "severity": "critical" if "critical" in bug.get("metadata", {}).get("regression_severity", "") else "warning",
                "message": bug["error_snippet"],
                "pipeline": bug["pipeline"],
                "timestamp": bug["detected_at"],
            }
            for bug in bugs[:10]  # Top 10 alerts
        ],
    }

    # Write to Supabase
    if verbose or dry_run:
        print("\nWriting snapshot to Supabase...", file=sys.stderr)
    result = _write_trading_board_snapshot(snapshot, dry_run=dry_run, show_request=verbose)

    if bugs:
        print(f"\nWriting {len(bugs)} bug signatures to Supabase...", file=sys.stderr)
        bug_results = _write_bug_signatures(bugs, dry_run=dry_run)

    if not dry_run:
        print("\n✓ Trading board populated successfully.", file=sys.stderr)
        print(f"  Best: {overall['best_pipeline']} ({overall['best_accuracy']:.1f}%)", file=sys.stderr)
        print(f"  Worst: {overall['worst_pipeline']} ({overall['worst_accuracy']:.1f}%)", file=sys.stderr)
        print(f"  Overall: {overall['overall_accuracy']:.1f}% ({overall['total_tests_24h']} tests)", file=sys.stderr)
        print(f"  Alerts: {len(bugs)}", file=sys.stderr)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Populate Trading Board - write pipeline metrics to Supabase"
    )
    parser.add_argument(
        "--results-file", "-r",
        type=str,
        default=None,
        help="Path to results JSON file (default: docs/data.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be written without writing to Supabase",
    )
    parser.add_argument(
        "--last-decision",
        type=str,
        choices=["KEEP", "REVERT", "HOLD"],
        help="Optional: last decision made (for tracking)",
    )
    parser.add_argument(
        "--last-decision-pipeline",
        type=str,
        help="Optional: pipeline for last decision",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output (show full JSON payload)",
    )
    args = parser.parse_args()

    populate_trading_board(
        results_file=args.results_file,
        dry_run=args.dry_run,
        last_decision=args.last_decision,
        last_decision_pipeline=args.last_decision_pipeline,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
