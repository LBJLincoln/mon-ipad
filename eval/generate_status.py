#!/usr/bin/env python3
"""
Lightweight Status Generator — Produces docs/status.json from data.json
========================================================================
Creates a compact (<3KB) status file that any Claude Code session can read
instantly, without needing to parse the full data.json (1MB+).

Called automatically by live-writer.py after every eval write.
Can also be run standalone: python3 eval/generate_status.py

Output: docs/status.json
"""
import json
import os
import sys
from datetime import datetime

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
DATA_JSON = os.path.join(REPO_ROOT, "docs", "data.json")
STATUS_JSON = os.path.join(REPO_ROOT, "docs", "status.json")

# Phase gate targets (must match phase_gates.py)
PHASE_1_TARGETS = {
    "standard": 85.0,
    "graph": 70.0,
    "quantitative": 85.0,
    "orchestrator": 70.0,
}
PHASE_1_OVERALL = 75.0


def compute_registry_accuracy(data):
    """Compute per-pipeline accuracy from question_registry (source of truth)."""
    reg = data.get("question_registry", {})
    stats = {}
    for qid, qdata in reg.items():
        rt = qdata.get("rag_type", "")
        runs = qdata.get("runs", [])
        if not runs or not rt:
            continue
        if rt not in stats:
            stats[rt] = {"tested": 0, "correct": 0, "errors": 0}
        stats[rt]["tested"] += 1
        last = runs[-1]
        if last.get("correct"):
            stats[rt]["correct"] += 1
        if last.get("error"):
            stats[rt]["errors"] += 1
    return stats


def get_last_iteration(data):
    """Get summary of last meaningful iteration."""
    iters = data.get("iterations", [])
    if not iters:
        return None
    last = iters[-1]
    return {
        "id": last.get("id"),
        "label": last.get("label", ""),
        "timestamp": last.get("timestamp_start"),
        "total_tested": last.get("total_tested", 0),
        "overall_accuracy_pct": last.get("overall_accuracy_pct", 0),
        "pipelines": {
            pipe: {
                "tested": rs.get("tested", 0),
                "correct": rs.get("correct", 0),
                "accuracy": rs.get("accuracy_pct", 0),
            }
            for pipe, rs in last.get("results_summary", {}).items()
        },
    }


def generate():
    """Generate docs/status.json from data.json."""
    if not os.path.exists(DATA_JSON):
        print("  ERROR: docs/data.json not found")
        return None

    with open(DATA_JSON) as f:
        data = json.load(f)

    # Compute real accuracy from question_registry
    stats = compute_registry_accuracy(data)

    # Build pipeline status
    pipelines = {}
    total_correct = 0
    total_tested = 0
    for pipe in ["standard", "graph", "quantitative", "orchestrator"]:
        s = stats.get(pipe, {"tested": 0, "correct": 0, "errors": 0})
        target = PHASE_1_TARGETS.get(pipe, 0)
        acc = round(s["correct"] / s["tested"] * 100, 1) if s["tested"] > 0 else 0
        met = acc >= target
        pipelines[pipe] = {
            "accuracy": acc,
            "tested": s["tested"],
            "correct": s["correct"],
            "errors": s["errors"],
            "target": target,
            "met": met,
            "gap": round(acc - target, 1),
        }
        total_correct += s["correct"]
        total_tested += s["tested"]

    overall_acc = round(total_correct / total_tested * 100, 1) if total_tested > 0 else 0
    # Also compute average of pipeline accuracies for gate check
    pipe_accs = [p["accuracy"] for p in pipelines.values() if p["tested"] > 0]
    avg_acc = round(sum(pipe_accs) / len(pipe_accs), 1) if pipe_accs else 0
    overall_met = avg_acc >= PHASE_1_OVERALL

    all_met = all(p["met"] for p in pipelines.values()) and overall_met

    # Compute blockers
    blockers = []
    for pipe, p in pipelines.items():
        if not p["met"]:
            blockers.append(f"{pipe}: {p['accuracy']}% < {p['target']}% (gap: {p['gap']}pp)")
    if not overall_met:
        blockers.append(f"overall: {avg_acc}% < {PHASE_1_OVERALL}%")

    # Determine next action
    if all_met:
        next_action = "Phase 1 COMPLETE — run Phase 2: python3 eval/run-eval-parallel.py --dataset phase-2 --reset"
    else:
        # Find worst pipeline
        worst = min(pipelines.items(), key=lambda x: x[1]["gap"])
        next_action = f"Fix {worst[0]} pipeline ({worst[1]['accuracy']}% vs {worst[1]['target']}% target, gap: {worst[1]['gap']}pp)"

    status = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "phase": {
            "current": 1,
            "name": "Baseline (200q)",
            "gates_passed": all_met,
        },
        "pipelines": pipelines,
        "overall": {
            "accuracy": avg_acc,
            "target": PHASE_1_OVERALL,
            "met": overall_met,
        },
        "blockers": blockers,
        "next_action": next_action,
        "last_iteration": get_last_iteration(data),
        "totals": {
            "unique_questions": data.get("meta", {}).get("total_unique_questions", 0),
            "test_runs": data.get("meta", {}).get("total_test_runs", 0),
            "iterations": data.get("meta", {}).get("total_iterations", 0),
        },
    }

    # Write atomically
    tmp = STATUS_JSON + ".tmp"
    with open(tmp, "w") as f:
        json.dump(status, f, indent=2)
    os.replace(tmp, STATUS_JSON)

    return status


if __name__ == "__main__":
    status = generate()
    if status:
        print(json.dumps(status, indent=2))
    else:
        sys.exit(1)
