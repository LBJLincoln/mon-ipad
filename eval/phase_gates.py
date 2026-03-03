#!/usr/bin/env python3
"""
PHASE GATE VALIDATOR — Centralized enforcement for phase transitions
=====================================================================
Prevents advancing to the next phase until ALL pipelines in the current
phase meet their accuracy targets. Called by eval scripts before execution.

Usage:
  from phase_gates import check_gates, get_current_phase, enforce_gate

  # Check if Phase 1 gates are met
  result = check_gates(phase=1)
  if not result["passed"]:
      print(f"BLOCKED: {result['blockers']}")

  # Enforce before Phase 2 eval (will sys.exit if gates unmet)
  enforce_gate(target_phase=2)
"""

import json
import os
import sys
from datetime import datetime

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
DATA_JSON = os.path.join(REPO_ROOT, "docs", "data.json")
READINESS_DIR = os.path.join(REPO_ROOT, "db", "readiness")

# Phase gate definitions — single source of truth
PHASE_GATES = {
    1: {
        "name": "Baseline (200q)",
        "pipeline_targets": {
            "standard": 85.0,
            "graph": 70.0,
            "quantitative": 85.0,
            "orchestrator": 70.0,
        },
        "overall_target": 75.0,
        "additional": [
            "orchestrator_p95_latency_under_15s",
            "orchestrator_error_rate_under_5pct",
            "3_consecutive_stable_iterations",
        ],
    },
    2: {
        "name": "Expand (1,000q)",
        "requires_phase": 1,
        "pipeline_targets": {
            "graph": 60.0,
            "quantitative": 70.0,
        },
        "overall_target": 65.0,
        "additional": [
            "no_phase1_regression",
        ],
    },
    3: {
        "name": "Scale (~9,500q)",
        "requires_phase": 2,
        "pipeline_targets": {
            "standard": 75.0,
            "graph": 55.0,
            "quantitative": 65.0,
            "orchestrator": 60.0,
        },
        "overall_target": 65.0,
        "additional": [
            "error_rate_under_10pct",
            "orchestrator_p95_latency_under_20s",
        ],
    },
    4: {
        "name": "Full HF (~100Kq)",
        "requires_phase": 3,
        "pipeline_targets": {},
        "overall_target": None,
        "additional": [
            "no_phase3_regression_within_5pct",
        ],
    },
    5: {
        "name": "Million+ (1M+q)",
        "requires_phase": 4,
        "pipeline_targets": {},
        "overall_target": None,
        "additional": [
            "sustained_throughput_100q_per_hour",
        ],
    },
}

# Downstream triggers — actions gated behind specific phase completions
# Each trigger defines: required_phases (all must pass), required_repos (all must be complete),
# and the action to unlock.
DOWNSTREAM_TRIGGERS = {
    "eti_site_tests": {
        "name": "ETI 4-Sector Site Tests",
        "description": (
            "Launch ETI site tests (finance, santé, industrie, legal) only when "
            "Phase 4 RAG pipelines are validated at scale AND data-ingestion has "
            "finished ingesting+enriching all sector documents. Both conditions are "
            "required: Phase 4 proves pipeline reliability at 100K questions, "
            "data-ingestion ensures sector-specific content is present in all databases."
        ),
        "required_phases": [4],
        "required_repos": ["rag-data-ingestion"],
        "action": "run_eti_site_tests",
        "sites": [
            "nomos-ai-pied.vercel.app",
            "nomos-pme-connectors-alexis-morets-projects.vercel.app",
        ],
    },
}


def check_trigger(trigger_name, phase_results=None, repo_status=None):
    """Check if a downstream trigger's conditions are met.

    Args:
        trigger_name: Key in DOWNSTREAM_TRIGGERS
        phase_results: Dict of {phase_num: bool} — pre-computed gate results.
                       If None, checks gates live from data.json.
        repo_status: Dict of {repo_name: bool} — whether each repo has completed its work.
                     Must be provided by the caller (cannot be auto-detected).

    Returns:
        dict: {"ready": bool, "blockers": [str], "trigger": dict}
    """
    if trigger_name not in DOWNSTREAM_TRIGGERS:
        return {"ready": False, "blockers": [f"Unknown trigger: {trigger_name}"]}

    trigger = DOWNSTREAM_TRIGGERS[trigger_name]
    blockers = []

    # Check required phases
    for phase_num in trigger.get("required_phases", []):
        if phase_results and phase_num in phase_results:
            passed = phase_results[phase_num]
        else:
            result = check_gates(phase=phase_num)
            passed = result["passed"]
        if not passed:
            blockers.append(f"Phase {phase_num} ({PHASE_GATES[phase_num]['name']}) not passed")

    # Check required repos
    repo_status = repo_status or {}
    for repo in trigger.get("required_repos", []):
        if not repo_status.get(repo, False):
            blockers.append(f"Repo '{repo}' work not complete")

    return {
        "ready": len(blockers) == 0,
        "trigger": trigger,
        "blockers": blockers,
    }


def load_data_json():
    """Load docs/data.json and return parsed data."""
    if not os.path.exists(DATA_JSON):
        return None
    with open(DATA_JSON) as f:
        return json.load(f)


_PHASE1_IDS = None

def _load_phase1_ids():
    """Load Phase 1 question IDs from dataset files."""
    global _PHASE1_IDS
    if _PHASE1_IDS is not None:
        return _PHASE1_IDS
    ids = set()
    for fname in ["standard-orch-50x2.json", "graph-quant-50x2.json"]:
        fpath = os.path.join(REPO_ROOT, "datasets", "phase-1", fname)
        if os.path.exists(fpath):
            import json as _json
            with open(fpath) as f:
                d = _json.load(f)
            for q in d.get("questions", []):
                ids.add(q["id"])
    _PHASE1_IDS = ids
    return ids


def _is_phase1_question(qid):
    """Return True if question belongs to Phase 1 baseline (loaded from dataset files)."""
    p1_ids = _load_phase1_ids()
    if p1_ids:
        return qid in p1_ids
    # Fallback: pattern-based exclusion if dataset files unavailable
    qid_lower = qid.lower()
    return not any(pat in qid_lower for pat in ("musique", "finqa", "phase2", "p2-", "tatqa", "convfinqa", "2wiki"))


def get_pipeline_accuracy(data, phase1_only=True):
    """Extract current pipeline accuracies from data.json.
    Returns dict: {pipeline_name: accuracy_pct}

    Args:
        data: Parsed data.json
        phase1_only: If True, exclude Phase 2 questions (musique, finqa) for Phase 1 gate check.
    """
    accuracies = {}
    pipelines = data.get("pipelines", {})
    for name, info in pipelines.items():
        trends = info.get("accuracy_trend", [])
        if trends:
            accuracies[name] = trends[-1]
        elif "accuracy" in info:
            accuracies[name] = info["accuracy"]
    # Also check question_registry for computed accuracy
    registry = data.get("question_registry", {})
    if registry:
        pipe_correct = {}
        pipe_total = {}
        for qid, qdata in registry.items():
            if phase1_only and not _is_phase1_question(qid):
                continue
            runs = qdata.get("runs", [])
            if not runs:
                continue
            last_run = runs[-1]
            pipe = qdata.get("rag_type", "")
            if not pipe:
                continue
            pipe_total[pipe] = pipe_total.get(pipe, 0) + 1
            if last_run.get("correct"):
                pipe_correct[pipe] = pipe_correct.get(pipe, 0) + 1
        for pipe in pipe_total:
            computed = round(pipe_correct.get(pipe, 0) / pipe_total[pipe] * 100, 1)
            # Use computed if no trend data, or if more recent
            if pipe not in accuracies or pipe_total[pipe] > 10:
                accuracies[pipe] = computed
    return accuracies


def check_gates(phase=1, data=None):
    """Check if all gates for a given phase are met.

    Returns:
        dict: {
            "passed": bool,
            "phase": int,
            "phase_name": str,
            "pipeline_status": {name: {"current": float, "target": float, "met": bool}},
            "overall": {"current": float, "target": float, "met": bool},
            "blockers": [str],
            "timestamp": str,
        }
    """
    if phase not in PHASE_GATES:
        return {"passed": False, "blockers": [f"Unknown phase: {phase}"]}

    gate = PHASE_GATES[phase]
    if data is None:
        data = load_data_json()
    if data is None:
        return {"passed": False, "blockers": ["docs/data.json not found"]}

    accuracies = get_pipeline_accuracy(data)
    blockers = []
    pipeline_status = {}

    # Check each pipeline target
    for pipe, target in gate["pipeline_targets"].items():
        current = accuracies.get(pipe, 0.0)
        met = current >= target
        pipeline_status[pipe] = {
            "current": current,
            "target": target,
            "met": met,
            "gap": round(current - target, 1),
        }
        if not met:
            blockers.append(f"{pipe}: {current}% < {target}% (gap: {round(target - current, 1)}pp)")

    # Check overall target
    overall_current = 0.0
    overall_met = True
    if gate.get("overall_target") and accuracies:
        total_correct = sum(accuracies.values())
        overall_current = round(total_correct / len(accuracies), 1) if accuracies else 0
        overall_met = overall_current >= gate["overall_target"]
        if not overall_met:
            blockers.append(f"overall: {overall_current}% < {gate['overall_target']}%")

    # Check prerequisite phase
    req_phase = gate.get("requires_phase")
    if req_phase:
        prereq = check_gates(phase=req_phase, data=data)
        if not prereq["passed"]:
            blockers.insert(0, f"Phase {req_phase} gates NOT met (prerequisite)")

    passed = len(blockers) == 0

    return {
        "passed": passed,
        "phase": phase,
        "phase_name": gate["name"],
        "pipeline_status": pipeline_status,
        "overall": {
            "current": overall_current,
            "target": gate.get("overall_target"),
            "met": overall_met,
        },
        "blockers": blockers,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def get_current_phase(data=None):
    """Determine the highest phase whose prerequisites are met.
    Returns (phase_number, reason_if_blocked)."""
    if data is None:
        data = load_data_json()
    if data is None:
        return 1, "No data.json found"

    for phase in range(5, 0, -1):
        result = check_gates(phase=phase, data=data)
        if result["passed"]:
            return phase + 1, None  # Ready for next phase

    return 1, "Phase 1 gates not yet met"


def enforce_gate(target_phase, force=False):
    """Enforce that prerequisite gates are met before running target_phase eval.

    Args:
        target_phase: The phase we want to evaluate (e.g., 2 for Phase 2 eval)
        force: If True, warn but don't block

    Returns:
        True if gate passed or forced, exits if blocked
    """
    if target_phase <= 1:
        return True  # Phase 1 has no prerequisites

    gate = PHASE_GATES.get(target_phase, {})
    req_phase = gate.get("requires_phase")
    if not req_phase:
        return True

    result = check_gates(phase=req_phase)

    if result["passed"]:
        print(f"  GATE CHECK: Phase {req_phase} gates PASSED")
        for pipe, status in result["pipeline_status"].items():
            print(f"    {pipe}: {status['current']}% >= {status['target']}%")
        return True

    # Gates not met
    print(f"\n{'='*70}")
    print(f"  PHASE GATE BLOCKED — Phase {req_phase} gates NOT met")
    print(f"{'='*70}")
    print(f"  Cannot run Phase {target_phase} evaluation until Phase {req_phase} passes.\n")

    for blocker in result["blockers"]:
        print(f"  BLOCKER: {blocker}")

    print(f"\n  Pipeline Status:")
    for pipe, status in result["pipeline_status"].items():
        symbol = "[PASS]" if status["met"] else "[FAIL]"
        print(f"    {symbol} {pipe}: {status['current']}% / {status['target']}% "
              f"(gap: {status['gap']:+.1f}pp)")

    if force:
        print(f"\n  --force flag set: proceeding anyway (results may be unreliable)")
        return True

    print(f"\n  To override: add --force flag (not recommended)")
    print(f"  To fix: improve Phase {req_phase} pipelines, then re-run")
    sys.exit(1)


def print_gate_summary(phase=None):
    """Print a summary of gate status for the given phase (or current phase)."""
    data = load_data_json()
    if data is None:
        print("  No docs/data.json found")
        return

    if phase is None:
        phase, reason = get_current_phase(data)
        phase = max(1, phase - 1)  # Show current, not next

    result = check_gates(phase=phase, data=data)

    print(f"\n  Phase {phase}: {result['phase_name']}")
    print(f"  Status: {'PASSED' if result['passed'] else 'NOT MET'}")

    if result["pipeline_status"]:
        for pipe, status in result["pipeline_status"].items():
            symbol = "[x]" if status["met"] else "[ ]"
            print(f"    {symbol} {pipe}: {status['current']}% / {status['target']}%")

    if result["overall"]["target"]:
        symbol = "[x]" if result["overall"]["met"] else "[ ]"
        print(f"    {symbol} overall: {result['overall']['current']}% / {result['overall']['target']}%")

    if result["blockers"]:
        print(f"\n  Blockers:")
        for b in result["blockers"]:
            print(f"    - {b}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phase Gate Validator")
    parser.add_argument("--phase", type=int, default=None, help="Phase to check (default: current)")
    parser.add_argument("--enforce", type=int, default=None, help="Enforce gate for target phase")
    parser.add_argument("--trigger", type=str, default=None,
                        help="Check downstream trigger (e.g., 'eti_site_tests')")
    parser.add_argument("--repo-complete", nargs="*", default=[],
                        help="Mark repos as complete (e.g., 'rag-data-ingestion')")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.trigger:
        repo_status = {r: True for r in args.repo_complete}
        result = check_trigger(args.trigger, repo_status=repo_status)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            t = result["trigger"]
            status = "READY" if result["ready"] else "BLOCKED"
            print(f"\n  Trigger: {t['name']}")
            print(f"  Status: {status}")
            print(f"  Description: {t['description']}")
            if result["blockers"]:
                print(f"\n  Blockers:")
                for b in result["blockers"]:
                    print(f"    - {b}")
    elif args.enforce:
        enforce_gate(target_phase=args.enforce)
        print("  Gate check passed.")
    elif args.json:
        phase = args.phase or 1
        result = check_gates(phase=phase)
        print(json.dumps(result, indent=2))
    else:
        print_gate_summary(phase=args.phase)
