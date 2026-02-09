#!/usr/bin/env python3
"""
Phase Gate Validator — Checks exit criteria for the current phase.
================================================================
Reads docs/data.json and validates all Phase 1 (or Phase 2+) exit criteria.
Returns structured pass/fail with details per criterion.

Used by:
  - eval/agentic-loop.py (automated iteration cycle)
  - .github/workflows/agentic-iteration.yml (CI/CD)
  - Manual checks from terminal

Usage:
  python phase-gate.py                  # Check Phase 1 gates (default)
  python phase-gate.py --phase 2        # Check Phase 2 gates
  python phase-gate.py --json           # JSON output for automation
  python phase-gate.py --strict         # Also check stability requirement

Exit codes:
  0 = All gates pass
  1 = Some gates fail
  2 = Data unavailable
"""

import json
import os
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(REPO_ROOT, "docs", "data.json")

# Phase 1 exit criteria
PHASE_1_TARGETS = {
    "standard":     {"accuracy": 85.0, "label": "Standard RAG"},
    "graph":        {"accuracy": 70.0, "label": "Graph RAG"},
    "quantitative": {"accuracy": 85.0, "label": "Quantitative RAG"},
    "orchestrator": {"accuracy": 70.0, "label": "Orchestrator",
                     "p95_latency_max_ms": 15000, "error_rate_max_pct": 5.0},
}
PHASE_1_OVERALL_TARGET = 75.0
PHASE_1_STABLE_ITERATIONS = 3  # consecutive stable iterations required

# Phase 2 exit criteria
PHASE_2_TARGETS = {
    "graph":        {"accuracy": 60.0, "label": "Graph RAG (Phase 2)"},
    "quantitative": {"accuracy": 70.0, "label": "Quantitative RAG (Phase 2)"},
}
PHASE_2_OVERALL_TARGET = 65.0


def load_data():
    """Load data.json, return None if unavailable."""
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE) as f:
        return json.load(f)


def get_latest_pipeline_stats(data):
    """Extract latest accuracy, latency, error rate per pipeline from the most recent iteration."""
    stats = {}
    iters = data.get("iterations", [])
    if not iters:
        return stats

    latest = iters[-1]
    summary = latest.get("results_summary", {})

    for pipe_name, pipe_summary in summary.items():
        tested = pipe_summary.get("tested", 0)
        correct = pipe_summary.get("correct", 0)
        errors = pipe_summary.get("errors", 0)
        stats[pipe_name] = {
            "accuracy_pct": pipe_summary.get("accuracy_pct", 0),
            "tested": tested,
            "correct": correct,
            "errors": errors,
            "error_rate_pct": round(errors / tested * 100, 1) if tested > 0 else 0,
            "avg_latency_ms": pipe_summary.get("avg_latency_ms", 0),
            "p95_latency_ms": pipe_summary.get("p95_latency_ms", 0),
            "avg_f1": pipe_summary.get("avg_f1", 0),
        }

    return stats


def get_overall_accuracy(data):
    """Compute overall accuracy from latest iteration."""
    iters = data.get("iterations", [])
    if not iters:
        return 0
    latest = iters[-1]
    total = latest.get("total_tested", 0)
    correct = latest.get("total_correct", 0)
    return round(correct / total * 100, 1) if total > 0 else 0


def check_stability(data, n_stable=3):
    """Check if the last N iterations show no regression.

    'Stable' = no pipeline's accuracy dropped by more than 2pp between consecutive iterations.
    Returns (is_stable, consecutive_stable_count, details).
    """
    iters = data.get("iterations", [])
    if len(iters) < n_stable:
        return False, len(iters), f"Only {len(iters)} iterations (need {n_stable})"

    consecutive = 0
    for i in range(len(iters) - 1, 0, -1):
        curr = iters[i].get("results_summary", {})
        prev = iters[i - 1].get("results_summary", {})

        regressed = False
        for pipe in curr:
            if pipe in prev:
                curr_acc = curr[pipe].get("accuracy_pct", 0)
                prev_acc = prev[pipe].get("accuracy_pct", 0)
                if prev_acc - curr_acc > 2.0:  # >2pp drop = regression
                    regressed = True
                    break

        if regressed:
            break
        consecutive += 1

    is_stable = consecutive >= n_stable
    return is_stable, consecutive, f"{consecutive} consecutive stable iterations"


def check_phase_1(data, strict=False):
    """Validate all Phase 1 exit criteria.

    Returns:
        {
            "phase": 1,
            "passed": bool,
            "criteria": [
                {"name": str, "passed": bool, "current": str, "target": str, "detail": str},
                ...
            ],
            "summary": str,
            "overall_accuracy": float,
            "pipeline_stats": dict,
        }
    """
    stats = get_latest_pipeline_stats(data)
    overall_acc = get_overall_accuracy(data)
    criteria = []

    # Per-pipeline accuracy gates
    for pipe_name, target_info in PHASE_1_TARGETS.items():
        pipe_stats = stats.get(pipe_name, {})
        acc = pipe_stats.get("accuracy_pct", 0)
        target = target_info["accuracy"]
        passed = acc >= target

        criterion = {
            "name": f"{target_info['label']} accuracy",
            "passed": passed,
            "current": f"{acc}%",
            "target": f">={target}%",
            "gap_pp": round(target - acc, 1),
            "detail": f"{acc}% vs {target}% target" + ("" if passed else f" (gap: {round(target - acc, 1)}pp)"),
        }
        criteria.append(criterion)

        # Orchestrator-specific: P95 latency and error rate
        if pipe_name == "orchestrator":
            p95_max = target_info.get("p95_latency_max_ms", 15000)
            p95_curr = pipe_stats.get("p95_latency_ms", 0)
            criteria.append({
                "name": "Orchestrator P95 latency",
                "passed": p95_curr <= p95_max,
                "current": f"{p95_curr}ms",
                "target": f"<={p95_max}ms",
                "gap_pp": 0,
                "detail": f"{p95_curr}ms vs {p95_max}ms max",
            })

            err_max = target_info.get("error_rate_max_pct", 5.0)
            err_curr = pipe_stats.get("error_rate_pct", 0)
            criteria.append({
                "name": "Orchestrator error rate",
                "passed": err_curr <= err_max,
                "current": f"{err_curr}%",
                "target": f"<={err_max}%",
                "gap_pp": 0,
                "detail": f"{err_curr}% vs {err_max}% max",
            })

    # Overall accuracy gate
    criteria.append({
        "name": "Overall accuracy",
        "passed": overall_acc >= PHASE_1_OVERALL_TARGET,
        "current": f"{overall_acc}%",
        "target": f">={PHASE_1_OVERALL_TARGET}%",
        "gap_pp": round(PHASE_1_OVERALL_TARGET - overall_acc, 1),
        "detail": f"{overall_acc}% vs {PHASE_1_OVERALL_TARGET}% target",
    })

    # Stability check
    if strict:
        is_stable, stable_count, stable_detail = check_stability(data, PHASE_1_STABLE_ITERATIONS)
        criteria.append({
            "name": f"Stability ({PHASE_1_STABLE_ITERATIONS} consecutive stable iterations)",
            "passed": is_stable,
            "current": f"{stable_count} stable",
            "target": f">={PHASE_1_STABLE_ITERATIONS}",
            "gap_pp": 0,
            "detail": stable_detail,
        })

    all_passed = all(c["passed"] for c in criteria)
    passed_count = sum(1 for c in criteria if c["passed"])
    total_count = len(criteria)

    return {
        "phase": 1,
        "passed": all_passed,
        "criteria": criteria,
        "passed_count": passed_count,
        "total_count": total_count,
        "summary": f"Phase 1: {passed_count}/{total_count} gates passed" +
                   (" - ALL PASS" if all_passed else " - NOT MET"),
        "overall_accuracy": overall_acc,
        "pipeline_stats": stats,
    }


def check_phase_2(data):
    """Validate Phase 2 exit criteria."""
    stats = get_latest_pipeline_stats(data)
    overall_acc = get_overall_accuracy(data)
    criteria = []

    for pipe_name, target_info in PHASE_2_TARGETS.items():
        pipe_stats = stats.get(pipe_name, {})
        acc = pipe_stats.get("accuracy_pct", 0)
        target = target_info["accuracy"]
        passed = acc >= target

        criteria.append({
            "name": f"{target_info['label']} accuracy",
            "passed": passed,
            "current": f"{acc}%",
            "target": f">={target}%",
            "gap_pp": round(target - acc, 1),
            "detail": f"{acc}% vs {target}% target",
        })

    # Overall accuracy
    criteria.append({
        "name": "Overall accuracy (Phase 1 + 2 combined)",
        "passed": overall_acc >= PHASE_2_OVERALL_TARGET,
        "current": f"{overall_acc}%",
        "target": f">={PHASE_2_OVERALL_TARGET}%",
        "gap_pp": round(PHASE_2_OVERALL_TARGET - overall_acc, 1),
        "detail": f"{overall_acc}% vs {PHASE_2_OVERALL_TARGET}% target",
    })

    # Phase 1 no-regression check
    phase1_result = check_phase_1(data, strict=False)
    criteria.append({
        "name": "Phase 1 no regression",
        "passed": phase1_result["passed"],
        "current": f"{phase1_result['passed_count']}/{phase1_result['total_count']}",
        "target": "All Phase 1 gates still pass",
        "gap_pp": 0,
        "detail": phase1_result["summary"],
    })

    all_passed = all(c["passed"] for c in criteria)
    passed_count = sum(1 for c in criteria if c["passed"])
    total_count = len(criteria)

    return {
        "phase": 2,
        "passed": all_passed,
        "criteria": criteria,
        "passed_count": passed_count,
        "total_count": total_count,
        "summary": f"Phase 2: {passed_count}/{total_count} gates passed" +
                   (" - ALL PASS" if all_passed else " - NOT MET"),
        "overall_accuracy": overall_acc,
        "pipeline_stats": stats,
    }


def identify_priorities(result):
    """Identify which pipelines need the most work, ordered by gap size."""
    priorities = []
    for criterion in result["criteria"]:
        if not criterion["passed"] and criterion.get("gap_pp", 0) > 0:
            priorities.append({
                "name": criterion["name"],
                "gap_pp": criterion["gap_pp"],
                "current": criterion["current"],
                "target": criterion["target"],
            })
    return sorted(priorities, key=lambda x: -x["gap_pp"])


def format_report(result):
    """Format a human-readable report."""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  PHASE {result['phase']} GATE CHECK")
    lines.append(f"{'='*60}")

    for c in result["criteria"]:
        icon = "[PASS]" if c["passed"] else "[FAIL]"
        lines.append(f"  {icon} {c['name']}: {c['detail']}")

    lines.append(f"\n  {'='*56}")
    lines.append(f"  {result['summary']}")
    lines.append(f"  Overall accuracy: {result['overall_accuracy']}%")

    if not result["passed"]:
        priorities = identify_priorities(result)
        if priorities:
            lines.append(f"\n  Priority fixes (by gap size):")
            for p in priorities:
                lines.append(f"    - {p['name']}: {p['current']} (need {p['target']}, gap {p['gap_pp']}pp)")

    lines.append(f"{'='*60}\n")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Phase Gate Validator")
    parser.add_argument("--phase", type=int, default=1, help="Phase to check (1 or 2)")
    parser.add_argument("--json", action="store_true", help="JSON output for automation")
    parser.add_argument("--strict", action="store_true",
                        help="Include stability requirement (3 consecutive stable iterations)")
    args = parser.parse_args()

    data = load_data()
    if data is None:
        print("ERROR: docs/data.json not found")
        sys.exit(2)

    if args.phase == 1:
        result = check_phase_1(data, strict=args.strict)
    elif args.phase == 2:
        result = check_phase_2(data)
    else:
        print(f"ERROR: Unknown phase {args.phase}")
        sys.exit(2)

    result["priorities"] = identify_priorities(result)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))

    # Set GitHub Actions output
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"phase_passed={'true' if result['passed'] else 'false'}\n")
            f.write(f"overall_accuracy={result['overall_accuracy']}\n")
            f.write(f"passed_count={result['passed_count']}\n")
            f.write(f"total_count={result['total_count']}\n")

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
