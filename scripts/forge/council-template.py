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


# ── Data Helpers ───────────────────────────────────────────────────────

MON_IPAD = Path("/home/termius/mon-ipad")

def _read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default or {}

def _read_jsonl_tail(path, n=10):
    try:
        lines = Path(path).read_text().strip().split("\n")
        return [json.loads(l) for l in lines[-n:] if l.strip()]
    except Exception:
        return []

def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── Phase Implementations (REAL per-department logic) ──────────────────

def phase_scan(repo_path, dept, config):
    """Scan current state with REAL data reads per department."""
    repo_name = Path(repo_path).name
    result = {"dept": dept, "repo": repo_name, "ts": ts()}

    # Common: metrics history
    metrics_file = Path(repo_path) / "data" / "departments" / dept / "metrics.jsonl"
    result["metrics_history"] = _read_jsonl_tail(metrics_file, 5)

    # Previous council state for trend detection
    state = load_council_state(repo_path, dept)
    result["iteration"] = state.get("iteration", 0)
    result["last_run"] = state.get("last_run")
    last_hist = state.get("history", [])[-3:]
    result["recent_decisions"] = [h.get("result") for h in last_hist]

    # Department-specific scans
    scanners = {
        "research": _scan_research,
        "engineering": _scan_engineering,
        "evolution": _scan_evolution,
        "product": _scan_product,
        "business": _scan_business,
        "evaluation": _scan_evaluation,
        "infra": _scan_infra,
        "finance": _scan_finance,
    }
    scanner = scanners.get(dept)
    if scanner:
        result.update(scanner(repo_path))

    return result


def _scan_research(repo_path):
    """Scan ArXiv outputs, research proposals, paper counts."""
    data = {}
    scan_dir = MON_IPAD / "data" / "research"
    if scan_dir.exists():
        scans = sorted(scan_dir.glob("*.json"))
        data["scan_count"] = len(scans)
        if scans:
            latest = _read_json(scans[-1])
            data["latest_scan"] = scans[-1].name
            data["papers_found"] = len(latest) if isinstance(latest, list) else latest.get("count", 0)
    proposals_dir = MON_IPAD / "data" / "departments" / "research"
    if proposals_dir.exists():
        data["proposal_files"] = [f.name for f in proposals_dir.iterdir()]
    return data


def _scan_engineering(repo_path):
    """Scan code quality: latest eval, Brier, test results."""
    data = {}
    eval_data = _read_json(MON_IPAD / "data" / "nba-agent" / "latest-eval.json")
    if eval_data:
        data["brier"] = eval_data.get("brier_score") or eval_data.get("brier")
        data["games_evaluated"] = eval_data.get("games_evaluated", 0)
        data["model_version"] = eval_data.get("model", "unknown")
    summary = _read_json(MON_IPAD / "data" / "nba-agent" / "quant-summary.json")
    if summary:
        data["atr_brier"] = summary.get("atr_brier", summary.get("best_brier"))
        data["walk_forward_brier"] = summary.get("walk_forward_avg")
    return data


def _scan_evolution(repo_path):
    """Scan HF island health, generation counts, Brier scores, stagnation."""
    data = {}
    health = _read_json(MON_IPAD / "data" / "agent-health.json")
    spaces = health.get("projects", {}).get("nba", {}).get("spaces", {})
    islands = {}
    best_brier = 1.0
    total_gens = 0
    stagnant_count = 0
    for sid, info in spaces.items():
        brier = _safe_float(info.get("brier"), 1.0)
        gen = info.get("generation", 0)
        stag = info.get("stagnation_cycles", 0)
        islands[sid] = {"brier": brier, "gen": gen, "status": info.get("status"), "stagnation": stag}
        if brier < best_brier:
            best_brier = brier
        total_gens += gen
        if stag > 5:
            stagnant_count += 1
    data["islands"] = islands
    data["best_fleet_brier"] = round(best_brier, 5)
    data["total_generations"] = total_gens
    data["stagnant_islands"] = stagnant_count
    data["fleet_size"] = len(islands)
    data["all_up"] = all(i.get("status") == "UP" for i in islands.values())
    return data


def _scan_product(repo_path):
    """Scan dashboard, Telegram bots, picks delivery."""
    import subprocess
    data = {}
    # Check dashboard repo
    dash_dir = Path("/home/termius/nomos-dashboard")
    if dash_dir.exists():
        try:
            res = subprocess.run(["git", "-C", str(dash_dir), "log", "-1", "--format=%h %s"],
                                 capture_output=True, text=True, timeout=5)
            data["dashboard_last_commit"] = res.stdout.strip()
        except Exception:
            data["dashboard_last_commit"] = "error"
    # Check picks freshness
    picks = _read_json(MON_IPAD / "data" / "nba-agent" / "predictions-today.json")
    if isinstance(picks, list):
        data["picks_count"] = len(picks)
    elif isinstance(picks, dict):
        data["picks_count"] = len(picks.get("predictions", []))
    # Check bot status
    for bot in ["nomos42-brain", "forge-bot", "nba-bot"]:
        pid_file = Path(f"/tmp/{bot}.pid")
        data[f"bot_{bot.replace('-', '_')}"] = pid_file.exists()
    return data


def _scan_business(repo_path):
    """Scan user count, subscription state, API usage."""
    data = {}
    users_file = MON_IPAD / "data" / "forge-users" / "users.json"
    users = _read_json(users_file, {})
    data["total_users"] = len(users) if isinstance(users, (dict, list)) else 0
    data["mrr"] = 0  # No revenue yet
    # Check API docs exist
    api_doc = MON_IPAD / "docs" / "business" / "api-architecture.md"
    data["api_docs_exist"] = api_doc.exists()
    data["pricing_tiers"] = ["free", "scout_19", "edge_49", "whale_149"]
    return data


def _scan_evaluation(repo_path):
    """Scan calibration, backtest results, false positive rates."""
    data = {}
    eval_data = _read_json(MON_IPAD / "data" / "nba-agent" / "latest-eval.json")
    if eval_data:
        data["brier"] = eval_data.get("brier_score") or eval_data.get("brier")
        data["ece"] = eval_data.get("ece")
        data["mce"] = eval_data.get("mce")
        data["log_loss"] = eval_data.get("log_loss")
        data["games"] = eval_data.get("games_evaluated", 0)
    backtest = _read_json(MON_IPAD / "data" / "nba-agent" / "backtest-results.json")
    if backtest:
        data["backtest_roi"] = backtest.get("roi")
        data["backtest_sharpe"] = backtest.get("sharpe")
        data["backtest_games"] = backtest.get("total_games", 0)
    bankroll = _read_json(MON_IPAD / "data" / "nba-agent" / "bankroll-state.json")
    if bankroll:
        data["real_roi"] = bankroll.get("roi_pct", 0)
        data["real_sharpe"] = bankroll.get("sharpe_ratio", 0)
    return data


def _scan_infra(repo_path):
    """Scan VM health, disk, memory, process counts, space status."""
    import shutil, subprocess
    data = {}
    # Disk
    usage = shutil.disk_usage("/")
    data["disk_used_pct"] = round(usage.used / usage.total * 100, 1)
    data["disk_free_gb"] = round(usage.free / (1024**3), 2)
    # Memory
    try:
        with open("/proc/meminfo") as f:
            lines = f.read()
        for line in lines.split("\n"):
            if line.startswith("MemTotal:"):
                data["mem_total_mb"] = int(line.split()[1]) // 1024
            elif line.startswith("MemAvailable:"):
                data["mem_avail_mb"] = int(line.split()[1]) // 1024
    except Exception:
        pass
    # Process count
    try:
        res = subprocess.run(["pgrep", "-c", "python3"], capture_output=True, text=True, timeout=5)
        data["python_procs"] = int(res.stdout.strip() or 0)
    except Exception:
        data["python_procs"] = -1
    # Spaces health
    health = _read_json(MON_IPAD / "data" / "agent-health.json")
    spaces = health.get("projects", {}).get("nba", {}).get("spaces", {})
    data["spaces_up"] = sum(1 for s in spaces.values() if s.get("status") == "UP")
    data["spaces_total"] = len(spaces)
    data["issues"] = health.get("issues", [])
    return data


def _scan_finance(repo_path):
    """Scan bankroll, costs, revenue projections."""
    data = {}
    bankroll = _read_json(MON_IPAD / "data" / "nba-agent" / "bankroll-state.json")
    if bankroll:
        data["bankroll"] = bankroll.get("balance", bankroll.get("bankroll", 0))
        data["roi_pct"] = bankroll.get("roi_pct", 0)
        data["total_bets"] = bankroll.get("total_bets", 0)
    data["estimated_monthly_cost"] = 20  # $20/mo baseline
    data["revenue"] = 0  # Pre-revenue
    data["burn_rate"] = 20
    return data


# ── PROPOSE: Generate real proposals ───────────────────────────────────

def phase_propose(repo_path, dept, config, scan):
    """Generate REAL improvement proposals based on scan data."""
    proposers = {
        "research": _propose_research,
        "engineering": _propose_engineering,
        "evolution": _propose_evolution,
        "product": _propose_product,
        "business": _propose_business,
        "evaluation": _propose_evaluation,
        "infra": _propose_infra,
        "finance": _propose_finance,
    }
    proposer = proposers.get(dept, _propose_generic)
    return proposer(repo_path, scan)


def _propose_generic(repo_path, scan):
    return {"summary": f"No specific proposer for {scan['dept']}", "action": "skip", "priority": "low"}


def _propose_research(repo_path, scan):
    papers = scan.get("papers_found", 0)
    if papers == 0:
        return {"summary": "Run ArXiv + GitHub scan for latest NBA/ML papers",
                "action": "run_scan", "priority": "high",
                "cmd": "python3 scripts/agents/research-cron.sh"}
    return {"summary": f"Research scan found {papers} papers — check for actionable techniques",
            "action": "review_proposals", "priority": "medium"}


def _propose_engineering(repo_path, scan):
    brier = _safe_float(scan.get("brier"), 0.23)
    atr = _safe_float(scan.get("atr_brier"), 0.21570)
    gap = brier - atr
    if gap > 0.01:
        return {"summary": f"Latest Brier {brier:.4f} is {gap:.4f} above ATR {atr:.5f} — investigate regression",
                "action": "investigate_brier_gap", "priority": "critical"}
    if brier > 0.22:
        return {"summary": f"Brier {brier:.4f} above 0.22 — check calibration and feature selection",
                "action": "calibration_check", "priority": "high"}
    return {"summary": f"Brier {brier:.4f} healthy — monitor for drift",
            "action": "monitor", "priority": "low"}


def _propose_evolution(repo_path, scan):
    stagnant = scan.get("stagnant_islands", 0)
    best = scan.get("best_fleet_brier", 0.23)
    if not scan.get("all_up", True):
        return {"summary": "One or more islands DOWN — restart needed",
                "action": "restart_islands", "priority": "critical"}
    if stagnant >= 3:
        return {"summary": f"{stagnant} islands stagnant — inject diversity via cross-pollination",
                "action": "cross_pollinate", "priority": "high",
                "cmd": "python3 scripts/agents/cross-pollinate.py"}
    if best > 0.222:
        return {"summary": f"Best fleet Brier {best:.5f} > 0.222 — consider mutation rate bump",
                "action": "tune_mutation", "priority": "medium"}
    return {"summary": f"Fleet healthy at {best:.5f} — {scan.get('total_generations', 0)} total gens",
            "action": "monitor", "priority": "low"}


def _propose_product(repo_path, scan):
    picks = scan.get("picks_count", 0)
    bots_up = sum(1 for k, v in scan.items() if k.startswith("bot_") and v)
    if picks == 0:
        return {"summary": "No picks today — check prediction pipeline",
                "action": "check_pipeline", "priority": "critical"}
    if bots_up < 2:
        return {"summary": f"Only {bots_up} bots running — restart bot fleet",
                "action": "restart_bots", "priority": "high",
                "cmd": "bash scripts/telegram/start_bots.sh restart"}
    return {"summary": f"{picks} picks ready, {bots_up} bots running",
            "action": "monitor", "priority": "low"}


def _propose_business(repo_path, scan):
    users = scan.get("total_users", 0)
    if users == 0:
        return {"summary": "Zero users — focus on first 10 users via Telegram channel",
                "action": "user_acquisition", "priority": "high"}
    if not scan.get("api_docs_exist"):
        return {"summary": "API docs missing — create API architecture",
                "action": "create_api_docs", "priority": "medium"}
    return {"summary": f"{users} users — track engagement and conversion",
            "action": "monitor", "priority": "low"}


def _propose_evaluation(repo_path, scan):
    ece = _safe_float(scan.get("ece"), 0)
    real_roi = _safe_float(scan.get("real_roi"), 0)
    real_sharpe = _safe_float(scan.get("real_sharpe"), 0)
    issues = []
    if ece > 0.10:
        issues.append(f"ECE {ece:.3f} > 0.10 — calibration needs fixing")
    if real_roi < -5:
        issues.append(f"Real ROI {real_roi:.1f}% — strategy losing money")
    if real_sharpe < 0:
        issues.append(f"Sharpe {real_sharpe:.2f} negative — risk-adjusted returns bad")
    if issues:
        return {"summary": " | ".join(issues), "action": "fix_calibration", "priority": "critical"}
    return {"summary": f"Evaluation metrics OK: ECE={ece:.3f}, ROI={real_roi:.1f}%, Sharpe={real_sharpe:.2f}",
            "action": "monitor", "priority": "low"}


def _propose_infra(repo_path, scan):
    disk = scan.get("disk_used_pct", 0)
    mem = scan.get("mem_avail_mb", 999)
    spaces_up = scan.get("spaces_up", 0)
    spaces_total = scan.get("spaces_total", 6)
    issues = scan.get("issues", [])
    proposals = []
    if disk > 85:
        proposals.append(f"Disk at {disk}% — cleanup needed")
    if mem < 200:
        proposals.append(f"Only {mem}MB RAM free — kill idle processes")
    if spaces_up < spaces_total:
        proposals.append(f"Only {spaces_up}/{spaces_total} spaces UP")
    if issues:
        proposals.append(f"{len(issues)} issues: {', '.join(issues[:3])}")
    if proposals:
        return {"summary": " | ".join(proposals), "action": "fix_infra", "priority": "high"}
    return {"summary": f"Infra healthy: disk {disk}%, {mem}MB free, {spaces_up}/{spaces_total} spaces",
            "action": "monitor", "priority": "low"}


def _propose_finance(repo_path, scan):
    bankroll = _safe_float(scan.get("bankroll"), 100)
    roi = _safe_float(scan.get("roi_pct"), 0)
    if bankroll < 80:
        return {"summary": f"Bankroll ${bankroll:.2f} below $80 — pause betting, analyze losses",
                "action": "pause_betting", "priority": "critical"}
    if roi < -10:
        return {"summary": f"ROI {roi:.1f}% — strategy review needed",
                "action": "strategy_review", "priority": "high"}
    return {"summary": f"Bankroll ${bankroll:.2f}, ROI {roi:.1f}%, burn ${scan.get('burn_rate', 20)}/mo",
            "action": "monitor", "priority": "low"}


# ── EXECUTE: Real actions ──────────────────────────────────────────────

def phase_execute(repo_path, dept, config, proposal):
    """Execute the proposal. Runs real commands for high-priority items."""
    import subprocess
    action = proposal.get("action", "monitor")
    priority = proposal.get("priority", "low")

    result = {"executed": False, "action": action, "proposal": proposal.get("summary", "")}

    # Only execute commands for high/critical priority with explicit cmd
    cmd = proposal.get("cmd")
    if cmd and priority in ("high", "critical"):
        log(Path(repo_path).name, dept, f"Executing: {cmd}")
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                  timeout=300, cwd=str(MON_IPAD))
            result["executed"] = True
            result["exit_code"] = proc.returncode
            result["stdout_tail"] = proc.stdout[-500:] if proc.stdout else ""
            result["stderr_tail"] = proc.stderr[-200:] if proc.stderr else ""
        except subprocess.TimeoutExpired:
            result["error"] = "Timeout after 5 minutes"
        except Exception as e:
            result["error"] = str(e)
    elif action == "monitor":
        result["executed"] = True
        result["note"] = "Monitoring — no action needed"
    else:
        result["note"] = f"Action '{action}' logged but not auto-executed (priority={priority})"

    return result


# ── EVALUATE: Real metric comparison ───────────────────────────────────

def phase_evaluate(repo_path, dept, config, exec_result):
    """Evaluate with REAL metrics. Compare before/after when possible."""
    repo_name = Path(repo_path).name
    eval_out = {"decision": "keep"}

    # Re-scan to get fresh metrics for comparison
    scanners = {
        "research": _scan_research,
        "engineering": _scan_engineering,
        "evolution": _scan_evolution,
        "evaluation": _scan_evaluation,
        "infra": _scan_infra,
        "finance": _scan_finance,
    }
    scanner = scanners.get(dept)
    fresh = scanner(repo_path) if scanner else {}

    # Department-specific evaluation
    if dept == "evolution":
        brier = fresh.get("best_fleet_brier", 1.0)
        eval_out["best_fleet_brier"] = {"value": brier}
        eval_out["total_generations"] = {"value": fresh.get("total_generations", 0)}
        eval_out["stagnant_islands"] = {"value": fresh.get("stagnant_islands", 0)}
        if not fresh.get("all_up"):
            eval_out["decision"] = "alert"

    elif dept == "engineering":
        brier = _safe_float(fresh.get("brier"), 0.23)
        eval_out["brier"] = {"value": round(brier, 5)}
        atr = _safe_float(fresh.get("atr_brier"), 0.21570)
        eval_out["atr_brier"] = {"value": round(atr, 5)}
        eval_out["gap_to_atr"] = {"value": round(brier - atr, 5)}

    elif dept == "evaluation":
        for k in ["brier", "ece", "mce", "real_roi", "real_sharpe"]:
            if k in fresh:
                eval_out[k] = {"value": fresh[k]}

    elif dept == "infra":
        eval_out["disk_used_pct"] = {"value": fresh.get("disk_used_pct", 0)}
        eval_out["mem_avail_mb"] = {"value": fresh.get("mem_avail_mb", 0)}
        eval_out["spaces_up"] = {"value": f"{fresh.get('spaces_up', 0)}/{fresh.get('spaces_total', 6)}"}
        if fresh.get("disk_used_pct", 0) > 90 or fresh.get("mem_avail_mb", 999) < 100:
            eval_out["decision"] = "alert"

    elif dept == "finance":
        eval_out["bankroll"] = {"value": fresh.get("bankroll", 0)}
        eval_out["roi_pct"] = {"value": fresh.get("roi_pct", 0)}
        eval_out["burn_rate"] = {"value": fresh.get("estimated_monthly_cost", 20)}

    elif dept == "research":
        eval_out["papers_found"] = {"value": fresh.get("papers_found", 0)}
        eval_out["scan_count"] = {"value": fresh.get("scan_count", 0)}

    # If execution failed, decide revert
    if exec_result.get("error"):
        eval_out["decision"] = "revert"
        eval_out["error"] = {"value": exec_result["error"]}

    return eval_out


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
