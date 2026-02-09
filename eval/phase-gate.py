#!/usr/bin/env python3
"""
Phase Gate Checker — Validates Phase 1 exit criteria from data.json.

Checks:
  1. Standard ≥ 85% accuracy
  2. Graph ≥ 70% accuracy
  3. Quantitative ≥ 85% accuracy
  4. Orchestrator ≥ 70% accuracy
  5. Overall ≥ 75% accuracy
  6. Orchestrator P95 latency < 15s, error rate < 5%
  7. At least 3 consecutive stable iterations (no regression)

Usage:
  python phase-gate.py              # Print gate status
  python phase-gate.py --json       # JSON output for CI/agent consumption
  python phase-gate.py --strict     # Exit code 1 if any gate fails
  python phase-gate.py --summary    # One-line pass/fail summary

Returns exit code:
  0 = All gates pass (Phase 1 COMPLETE)
  1 = One or more gates fail (--strict mode)
"""

import json
import os
import sys
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(REPO_ROOT, "docs", "data.json")

# Phase 1 targets
TARGETS = {
    "standard":      {"accuracy": 85.0, "label": "Standard RAG"},
    "graph":         {"accuracy": 70.0, "label": "Graph RAG"},
    "quantitative":  {"accuracy": 85.0, "label": "Quantitative RAG"},
    "orchestrator":  {"accuracy": 70.0, "label": "Orchestrator",
                      "p95_latency_max_ms": 15000, "error_rate_max_pct": 5.0},
}
OVERALL_TARGET = 75.0
STABILITY_REQUIRED = 3  # consecutive stable iterations


def load_data():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE) as f:
        return json.load(f)


def check_pipeline_accuracy(data):
    """Check each pipeline's accuracy against its target."""
    pipes = data.get("pipelines", {})
    results = {}

    for pipe_name, target in TARGETS.items():
        pipe = pipes.get(pipe_name, {})
        trend = pipe.get("trend", [])
        latest = trend[-1] if trend else None

        if not latest:
            results[pipe_name] = {
                "label": target["label"],
                "current": 0,
                "target": target["accuracy"],
                "gap": target["accuracy"],
                "passed": False,
                "reason": "No evaluation data",
            }
            continue

        acc = latest.get("accuracy_pct", 0)
        gap = round(target["accuracy"] - acc, 1)
        passed = acc >= target["accuracy"]

        result = {
            "label": target["label"],
            "current": acc,
            "target": target["accuracy"],
            "gap": gap,
            "passed": passed,
            "tested": latest.get("tested", 0),
            "errors": latest.get("errors", 0),
        }

        # Orchestrator-specific checks
        if pipe_name == "orchestrator":
            p95 = latest.get("p95_latency_ms", 0)
            tested = latest.get("tested", 1)
            errors = latest.get("errors", 0)
            error_rate = round(errors / tested * 100, 1) if tested > 0 else 0

            p95_max = target.get("p95_latency_max_ms", 15000)
            err_max = target.get("error_rate_max_pct", 5.0)

            result["p95_latency_ms"] = p95
            result["p95_target_ms"] = p95_max
            result["p95_passed"] = p95 <= p95_max if p95 > 0 else True
            result["error_rate_pct"] = error_rate
            result["error_rate_target_pct"] = err_max
            result["error_rate_passed"] = error_rate <= err_max

            # Orchestrator passes only if ALL sub-criteria pass
            result["passed"] = passed and result["p95_passed"] and result["error_rate_passed"]
            if not result["p95_passed"]:
                result["reason"] = f"P95 latency {p95}ms > {p95_max}ms"
            elif not result["error_rate_passed"]:
                result["reason"] = f"Error rate {error_rate}% > {err_max}%"

        results[pipe_name] = result

    return results


def check_overall_accuracy(data):
    """Check overall accuracy across all pipelines."""
    pipes = data.get("pipelines", {})
    total_tested = 0
    total_correct = 0

    for pipe in pipes.values():
        trend = pipe.get("trend", [])
        if trend:
            latest = trend[-1]
            total_tested += latest.get("tested", 0)
            total_correct += latest.get("correct", 0)

    if total_tested == 0:
        return {"current": 0, "target": OVERALL_TARGET, "passed": False,
                "reason": "No data"}

    acc = round(total_correct / total_tested * 100, 1)
    return {
        "current": acc,
        "target": OVERALL_TARGET,
        "gap": round(OVERALL_TARGET - acc, 1),
        "passed": acc >= OVERALL_TARGET,
        "total_tested": total_tested,
        "total_correct": total_correct,
    }


def check_stability(data):
    """Check for 3 consecutive stable iterations (no accuracy regression)."""
    iters = data.get("iterations", [])
    if len(iters) < STABILITY_REQUIRED:
        return {
            "passed": False,
            "consecutive_stable": len(iters),
            "required": STABILITY_REQUIRED,
            "reason": f"Only {len(iters)} iterations (need {STABILITY_REQUIRED})",
        }

    # Check last N iterations for regressions
    consecutive = 0
    for i in range(len(iters) - 1, 0, -1):
        curr = iters[i]
        prev = iters[i - 1]
        curr_acc = curr.get("overall_accuracy_pct", 0)
        prev_acc = prev.get("overall_accuracy_pct", 0)

        # Stable = no regression (current >= previous - 2pp tolerance)
        if curr_acc >= prev_acc - 2.0:
            consecutive += 1
        else:
            break

        if consecutive >= STABILITY_REQUIRED - 1:
            break

    # Need STABILITY_REQUIRED consecutive iterations (STABILITY_REQUIRED-1 non-regressing pairs)
    is_stable = consecutive >= STABILITY_REQUIRED - 1
    return {
        "passed": is_stable,
        "consecutive_stable": consecutive + 1,  # +1 because pairs → iterations
        "required": STABILITY_REQUIRED,
        "reason": None if is_stable else f"{consecutive + 1} stable (need {STABILITY_REQUIRED})",
    }


def check_all_gates(data):
    """Run all Phase 1 gate checks. Returns full report."""
    pipeline_gates = check_pipeline_accuracy(data)
    overall_gate = check_overall_accuracy(data)
    stability_gate = check_stability(data)

    all_pipeline_pass = all(g["passed"] for g in pipeline_gates.values())
    all_pass = all_pipeline_pass and overall_gate["passed"] and stability_gate["passed"]

    # Count how many gates pass
    total_gates = len(pipeline_gates) + 2  # pipelines + overall + stability
    passed_gates = sum(1 for g in pipeline_gates.values() if g["passed"])
    passed_gates += (1 if overall_gate["passed"] else 0)
    passed_gates += (1 if stability_gate["passed"] else 0)

    return {
        "phase": 1,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "all_pass": all_pass,
        "gates_passed": passed_gates,
        "gates_total": total_gates,
        "pipelines": pipeline_gates,
        "overall": overall_gate,
        "stability": stability_gate,
        "phase1_complete": all_pass,
    }


def format_report(report):
    """Format gate check as readable text."""
    lines = []
    status = "PASS" if report["all_pass"] else "FAIL"
    lines.append(f"Phase 1 Gate Check: {status} ({report['gates_passed']}/{report['gates_total']} gates)")
    lines.append("=" * 60)

    # Pipeline gates
    lines.append("\nPipeline Accuracy:")
    for name, gate in report["pipelines"].items():
        icon = "[PASS]" if gate["passed"] else "[FAIL]"
        gap_str = f" (gap: {gate['gap']}pp)" if gate.get("gap", 0) > 0 else ""
        lines.append(f"  {icon} {gate['label']}: {gate['current']}% / {gate['target']}%{gap_str}")
        if name == "orchestrator" and not gate.get("p95_passed", True):
            lines.append(f"        P95 latency: {gate['p95_latency_ms']}ms / {gate['p95_target_ms']}ms")
        if name == "orchestrator" and not gate.get("error_rate_passed", True):
            lines.append(f"        Error rate: {gate['error_rate_pct']}% / {gate['error_rate_target_pct']}%")

    # Overall
    overall = report["overall"]
    icon = "[PASS]" if overall["passed"] else "[FAIL]"
    lines.append(f"\n  {icon} Overall: {overall['current']}% / {overall['target']}%")

    # Stability
    stab = report["stability"]
    icon = "[PASS]" if stab["passed"] else "[FAIL]"
    lines.append(f"  {icon} Stability: {stab['consecutive_stable']}/{stab['required']} consecutive stable iterations")

    if report["all_pass"]:
        lines.append("\n  >>> PHASE 1 COMPLETE — All gates passed! Ready for Phase 2. <<<")
    else:
        failed = []
        for name, gate in report["pipelines"].items():
            if not gate["passed"]:
                failed.append(f"{gate['label']} ({gate['current']}% → {gate['target']}%)")
        if not overall["passed"]:
            failed.append(f"Overall ({overall['current']}% → {overall['target']}%)")
        if not stab["passed"]:
            failed.append(f"Stability ({stab['consecutive_stable']}/{stab['required']})")
        lines.append(f"\n  Blocking gates: {', '.join(failed)}")

    return "\n".join(lines)


def main():
    data = load_data()
    if not data:
        print("ERROR: No data.json found")
        sys.exit(2)

    report = check_all_gates(data)

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    elif "--summary" in sys.argv:
        status = "PASS" if report["all_pass"] else "FAIL"
        print(f"Phase1: {status} ({report['gates_passed']}/{report['gates_total']})")
    else:
        print(format_report(report))

    # Set GitHub Actions output
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"phase1_complete={'true' if report['all_pass'] else 'false'}\n")
            f.write(f"gates_passed={report['gates_passed']}\n")
            f.write(f"gates_total={report['gates_total']}\n")
            for name, gate in report["pipelines"].items():
                f.write(f"{name}_accuracy={gate['current']}\n")
                f.write(f"{name}_passed={'true' if gate['passed'] else 'false'}\n")

    if "--strict" in sys.argv and not report["all_pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
