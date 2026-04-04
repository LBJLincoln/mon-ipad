#!/usr/bin/env python3
"""
Forge Council Template — Universal Karpathy loop for any department in any repo.

Usage:
    python3 council-template.py --repo mon-ipad --dept research [--dry-run]

Each department has 4 council agents that follow the Karpathy autoresearch pattern:
    1. SCAN: Gather current state and data
    2. PROPOSE: Generate improvement hypothesis
    3. EXECUTE: Apply the change (5-min budget)
    4. EVALUATE: Measure metric delta → keep or revert

Inspired by:
    - Karpathy autoresearch (github.com/karpathy/autoresearch)
    - Paperclip org charts (github.com/paperclipai/paperclip)
    - Hermes-agent self-improvement (github.com/nousresearch/hermes-agent)
"""

import json
import sys
import os
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────

FORGE_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = FORGE_ROOT / "department-config.json"

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def log(repo, dept, msg, level="INFO"):
    print(f"[{ts()}] [{level}] [{repo}:{dept}] {msg}")

# ── Metric Logger ───────────────────────────────────────────────────────

def log_metric(repo_path, dept, metric_name, value, delta=None):
    """Append a metric entry to the department's metrics JSONL file."""
    metrics_dir = Path(repo_path) / "data" / "departments" / dept
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = metrics_dir / "metrics.jsonl"

    entry = {
        "ts": ts(),
        "repo": Path(repo_path).name,
        "dept": dept,
        "metric": metric_name,
        "value": value,
    }
    if delta is not None:
        entry["delta"] = delta

    with open(metrics_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

# ── Council State ───────────────────────────────────────────────────────

def load_council_state(repo_path, dept):
    """Load the current council state for a department."""
    state_file = Path(repo_path) / "data" / "departments" / f"council-{dept}.json"
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {
        "dept": dept,
        "iteration": 0,
        "best_metric": None,
        "last_run": None,
        "history": [],
        "agents": {},
    }

def save_council_state(repo_path, dept, state):
    """Save council state after a run."""
    state_dir = Path(repo_path) / "data" / "departments"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"council-{dept}.json"

    state["last_run"] = ts()
    state["iteration"] = state.get("iteration", 0) + 1

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

# ── Karpathy Loop Core ─────────────────────────────────────────────────

def run_karpathy_loop(repo_path, dept, config, dry_run=False):
    """
    The universal Karpathy loop:
    1. SCAN current state
    2. PROPOSE improvement
    3. EXECUTE (5-min budget)
    4. EVALUATE → keep or revert
    """
    repo_name = Path(repo_path).name
    dept_config = config["departments"].get(dept)

    if not dept_config:
        log(repo_name, dept, f"Department '{dept}' not found in config", "ERROR")
        return False

    state = load_council_state(repo_path, dept)
    iteration = state.get("iteration", 0) + 1

    log(repo_name, dept, f"=== Council Iteration {iteration} ===")
    log(repo_name, dept, f"Layer: {dept_config['layer']}")
    log(repo_name, dept, f"Metrics: {', '.join(dept_config['metrics'])}")
    log(repo_name, dept, f"Loop: {dept_config['karpathy_loop']}")

    if dry_run:
        log(repo_name, dept, "[DRY RUN] Would execute Karpathy loop", "WARN")
        return True

    # Phase 1: SCAN
    log(repo_name, dept, "Phase 1/4: SCAN — gathering current state")
    scan_result = phase_scan(repo_path, dept, dept_config)

    # Phase 2: PROPOSE
    log(repo_name, dept, "Phase 2/4: PROPOSE — generating improvement hypothesis")
    proposal = phase_propose(repo_path, dept, dept_config, scan_result)

    # Phase 3: EXECUTE (5-min budget)
    log(repo_name, dept, "Phase 3/4: EXECUTE — applying change (5-min budget)")
    start_time = time.time()
    exec_result = phase_execute(repo_path, dept, dept_config, proposal)
    elapsed = time.time() - start_time
    log(repo_name, dept, f"Execution took {elapsed:.1f}s")

    # Phase 4: EVALUATE
    log(repo_name, dept, "Phase 4/4: EVALUATE — measuring metric delta")
    eval_result = phase_evaluate(repo_path, dept, dept_config, exec_result)

    # Log result
    for metric in dept_config["metrics"]:
        if metric in eval_result:
            log_metric(repo_path, dept, metric, eval_result[metric].get("value"), eval_result[metric].get("delta"))

    # Update state
    state["history"] = state.get("history", [])[-49:]  # keep last 50
    state["history"].append({
        "iteration": iteration,
        "ts": ts(),
        "proposal": proposal.get("summary", ""),
        "result": eval_result.get("decision", "unknown"),
        "metrics": {k: v for k, v in eval_result.items() if k != "decision"},
    })

    save_council_state(repo_path, dept, state)

    decision = eval_result.get("decision", "revert")
    log(repo_name, dept, f"Decision: {decision.upper()}")
    return decision == "keep"


# ── Phase Implementations (Override per department) ─────────────────────

def phase_scan(repo_path, dept, config):
    """Scan current state. Returns dict of findings."""
    repo_name = Path(repo_path).name
    result = {"dept": dept, "repo": repo_name, "ts": ts()}

    # Check for metrics history
    metrics_file = Path(repo_path) / "data" / "departments" / dept / "metrics.jsonl"
    if metrics_file.exists():
        lines = metrics_file.read_text().strip().split("\n")
        result["metrics_count"] = len(lines)
        if lines:
            last = json.loads(lines[-1])
            result["last_metric"] = last

    # Check department-specific files
    dept_dir = Path(repo_path) / "data" / "departments" / dept
    if dept_dir.exists():
        result["files"] = [f.name for f in dept_dir.iterdir()]

    return result

def phase_propose(repo_path, dept, config, scan_result):
    """Generate improvement proposal based on scan."""
    return {
        "summary": f"Auto-improvement for {dept}",
        "action": config["karpathy_loop"],
        "target_metrics": config["metrics"],
    }

def phase_execute(repo_path, dept, config, proposal):
    """Execute the proposal within 5-min budget."""
    # Base implementation: just log. Override per department.
    return {"executed": True, "action": proposal.get("summary", "")}

def phase_evaluate(repo_path, dept, config, exec_result):
    """Evaluate results and decide keep/revert."""
    return {"decision": "keep"}


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Forge Council — Universal Karpathy Loop")
    parser.add_argument("--repo", required=True, help="Repo name or path")
    parser.add_argument("--dept", required=True, help="Department name")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute, just show plan")
    parser.add_argument("--all-depts", action="store_true", help="Run all 8 departments")
    args = parser.parse_args()

    config = load_config()

    # Resolve repo path
    repo_path = args.repo
    if not os.path.isabs(repo_path):
        repo_path = f"/home/termius/{args.repo}"
    if not os.path.isdir(repo_path):
        print(f"ERROR: Repo not found: {repo_path}")
        sys.exit(1)

    if args.all_depts:
        depts = list(config["departments"].keys())
    else:
        depts = [args.dept]

    results = {}
    for dept in depts:
        success = run_karpathy_loop(repo_path, dept, config, dry_run=args.dry_run)
        results[dept] = "KEEP" if success else "REVERT"

    print(f"\n{'='*60}")
    print(f"Council Results for {Path(repo_path).name}:")
    for dept, result in results.items():
        print(f"  {dept:15s} → {result}")

if __name__ == "__main__":
    main()
