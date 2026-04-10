#!/usr/bin/env python3
"""
Nomos42 -- Compute Orchestrator
=================================
Master script that decides WHERE and WHEN to run each GPU workload.
Reads current metrics, checks platform availability, and dispatches
the right experiment to the right platform at the right time.

Priority:
    1. ZeroGPU (free H200, 15 min/day across 3 accounts)
    2. Kaggle  (free P100, 30h/week)
    3. Lightning (free T4, 22h total)
    4. Colab   (free T4, on-demand)
    5. Modal   (paid A10G, $0.18/burst -- only if critical)

Schedule (UTC):
    06:00 -- ZeroGPU burst (all 3 accounts, 15 min total)
    08:00 -- Kaggle session (if weekly credits available)
    12:00 -- Lightning burst (if hours remaining)
    On-demand -- Modal (only for critical experiments)

This script runs on the VM (969MB RAM). It ORCHESTRATES remote GPU work.
ZERO ML runs locally.

Usage:
    python3 scripts/gpu-burst/compute-orchestrator.py              # Auto-dispatch
    python3 scripts/gpu-burst/compute-orchestrator.py --status     # Show all platforms
    python3 scripts/gpu-burst/compute-orchestrator.py --plan       # Show today's plan
    python3 scripts/gpu-burst/compute-orchestrator.py --force zerogpu  # Force specific platform
    python3 scripts/gpu-burst/compute-orchestrator.py --force modal    # Force Modal (costs $)

Cron:
    # Run 4x daily to dispatch at optimal times
    0 6,8,12,18 * * * python3 /home/lahargnedebartoli/mon-ipad/scripts/gpu-burst/compute-orchestrator.py >> /home/lahargnedebartoli/mon-ipad/logs/compute-orchestrator.log 2>&1
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any

# ══════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════

REPO_ROOT = Path("/home/lahargnedebartoli/mon-ipad")
SCRIPTS_DIR = REPO_ROOT / "scripts" / "gpu-burst"
DATA_DIR = REPO_ROOT / "data" / "gpu-burst"
KARPATHY_DIR = REPO_ROOT / "data" / "karpathy"
LOG_DIR = REPO_ROOT / "logs"

# State files
ORCHESTRATOR_STATE = DATA_DIR / "orchestrator-state.json"
ORCHESTRATOR_LOG = DATA_DIR / "orchestrator-log.jsonl"

# Result files from each platform
RESULT_FILES = {
    "zerogpu": DATA_DIR / "latest-zerogpu-result.json",
    "kaggle": DATA_DIR / "latest-kaggle-result.json",
    "lightning": DATA_DIR / "latest-lightning-nba-result.json",
    "colab": DATA_DIR / "latest-colab-result.json",
    "modal": DATA_DIR / "latest-modal-result.json",
}

# Platform scripts
PLATFORM_SCRIPTS = {
    "zerogpu": SCRIPTS_DIR / "zerogpu-burst.py",
    "kaggle": SCRIPTS_DIR / "kaggle-nba-burst.py",
    "lightning": SCRIPTS_DIR / "lightning-deploy.sh",
    "colab": SCRIPTS_DIR / "colab-nba-burst.py",
    "modal": SCRIPTS_DIR / "modal-deploy.py",
}

# Best config
BEST_CONFIG = KARPATHY_DIR / "nba-best-config.json"

# ══════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════

ATR_BRIER = 0.21570
TARGET_BRIER = 0.20000

# Platform capabilities
PLATFORMS = {
    "zerogpu": {
        "gpu": "H200",
        "cost_per_burst": 0.0,
        "daily_budget_min": 15,   # 5 min x 3 accounts
        "burst_duration_sec": 300,
        "priority": 1,
        "schedule_utc": [6, 14],   # Run 2x/day (more H200 time)
        "cooldown_hours": 10,
    },
    "kaggle": {
        "gpu": "P100",
        "cost_per_burst": 0.0,
        "daily_budget_min": 540,   # 9h sessions
        "burst_duration_sec": 1800,
        "priority": 2,
        "schedule_utc": [8],       # Run at 08:00 UTC
        "cooldown_hours": 24,
    },
    "lightning": {
        "gpu": "T4/A10G",
        "cost_per_burst": 0.0,
        "daily_budget_min": 30,    # Conservative from 22h total
        "burst_duration_sec": 1800,
        "priority": 3,
        "schedule_utc": [8, 12, 20],  # Run 3x/day
        "cooldown_hours": 6,
    },
    "colab": {
        "gpu": "T4",
        "cost_per_burst": 0.0,
        "daily_budget_min": 30,
        "burst_duration_sec": 1800,
        "priority": 4,
        "schedule_utc": [10, 16, 22],  # Run 3x/day
        "cooldown_hours": 6,
    },
    "modal": {
        "gpu": "A10G",
        "cost_per_burst": 0.18,
        "daily_budget_min": 10,
        "burst_duration_sec": 600,
        "priority": 5,             # Only if critical
        "schedule_utc": [],         # On-demand only
        "cooldown_hours": 48,       # Conservative -- costs money
    },
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, level: str = "INFO"):
    print(f"[{ts()}] [{level}] {msg}")


def log_event(event: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(ORCHESTRATOR_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


# ══════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ══════════════════════════════════════════════════════════

def load_state() -> dict:
    """Load orchestrator state (last run times, daily budgets, etc.)."""
    if ORCHESTRATOR_STATE.exists():
        return json.loads(ORCHESTRATOR_STATE.read_text())
    return {
        "last_run": {},        # platform -> ISO timestamp of last run
        "daily_runs": {},      # platform -> [ISO timestamps today]
        "total_cost": 0.0,     # Total $ spent on paid platforms
        "improvements": 0,     # Total improvements found
        "created": ts(),
    }


def save_state(state: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["updated"] = ts()
    ORCHESTRATOR_STATE.write_text(json.dumps(state, indent=2))


# ══════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════

def get_current_best() -> dict:
    """Get current best Brier score from local files."""
    result = {
        "best_brier": ATR_BRIER,
        "source": "atr",
        "model_type": "unknown",
        "n_features": 0,
    }

    # Check karpathy best config
    if BEST_CONFIG.exists():
        try:
            cfg = json.loads(BEST_CONFIG.read_text())
            brier = float(cfg.get("best_brier", 1.0))
            if 0.0 < brier < result["best_brier"]:
                result["best_brier"] = brier
                result["source"] = "karpathy"
                result["model_type"] = cfg.get("model_type", "unknown")
                result["n_features"] = cfg.get("n_features", 0)
        except Exception:
            pass

    # Check each platform's latest result
    for platform, result_file in RESULT_FILES.items():
        if result_file.exists():
            try:
                r = json.loads(result_file.read_text())
                brier = float(r.get("best_brier", r.get("best_score", 1.0)))
                if 0.0 < brier < result["best_brier"]:
                    result["best_brier"] = brier
                    result["source"] = platform
                    result["model_type"] = r.get("model_type", "unknown")
                    result["n_features"] = r.get("n_features", 0)
            except Exception:
                pass

    # Check quant summary
    quant_file = REPO_ROOT / "data" / "nba-agent" / "quant-summary.json"
    if quant_file.exists():
        try:
            q = json.loads(quant_file.read_text())
            brier = float(q.get("best_brier", q.get("fleet_best_brier", 1.0)))
            if 0.0 < brier < result["best_brier"]:
                result["best_brier"] = brier
                result["source"] = "quant-summary"
        except Exception:
            pass

    return result


def get_fleet_status() -> List[dict]:
    """Get status of HF evolution islands."""
    import urllib.request
    import ssl

    islands = {
        "S10": "https://nomos42-nba-quant.hf.space",
        "S11": "https://nomos42-nba-quant-2.hf.space",
        "S12": "https://nomos42-nba-evo-3.hf.space",
        "S13": "https://nomos42-nba-evo-4.hf.space",
        "S14": "https://nomos42-nba-evo-5.hf.space",
        "S15": "https://nomos42-nba-evo-6.hf.space",
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    statuses = []
    for name, url in islands.items():
        status = {"name": name, "url": url, "status": "unknown", "brier": None}
        try:
            req = urllib.request.Request(
                f"{url}/api/status",
                headers={"User-Agent": "Nomos42-Orchestrator/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read())
                status["status"] = "running"
                status["brier"] = data.get("best_brier", data.get("brier"))
                status["generation"] = data.get("generation")
                status["model_type"] = data.get("model_type")
        except Exception:
            status["status"] = "unreachable"
        statuses.append(status)

    return statuses


# ══════════════════════════════════════════════════════════
# PLATFORM AVAILABILITY
# ══════════════════════════════════════════════════════════

def check_platform_available(platform: str, state: dict) -> dict:
    """Check if a platform is available for a burst right now."""
    now = datetime.now(timezone.utc)
    cfg = PLATFORMS[platform]
    result = {
        "platform": platform,
        "available": False,
        "reason": "",
        "cost": cfg["cost_per_burst"],
    }

    # Check cooldown
    last_run_str = state.get("last_run", {}).get(platform)
    if last_run_str:
        try:
            last_run = datetime.fromisoformat(last_run_str)
            hours_since = (now - last_run).total_seconds() / 3600
            if hours_since < cfg["cooldown_hours"]:
                result["reason"] = f"cooldown ({hours_since:.1f}h < {cfg['cooldown_hours']}h)"
                return result
        except Exception:
            pass

    # Check schedule (if platform has one)
    if cfg["schedule_utc"]:
        current_hour = now.hour
        # Allow a 2-hour window around each scheduled time
        scheduled = False
        for sched_hour in cfg["schedule_utc"]:
            if abs(current_hour - sched_hour) <= 1 or abs(current_hour - sched_hour) >= 23:
                scheduled = True
                break
        if not scheduled:
            result["reason"] = f"not scheduled (schedule: {cfg['schedule_utc']} UTC, now: {current_hour})"
            return result

    # Platform-specific checks
    if platform == "zerogpu":
        # Check if tokens are available
        has_token = False
        for env in ["HF_TOKEN", "HF_TOKEN_2", "HF_TOKEN_3"]:
            if os.environ.get(env):
                has_token = True
                break
        if not has_token:
            result["reason"] = "no HF tokens available"
            return result

    elif platform == "kaggle":
        # Check kaggle CLI
        try:
            ret = subprocess.run(
                ["kaggle", "--version"],
                capture_output=True, text=True,
            )
            if ret.returncode != 0:
                result["reason"] = "kaggle CLI not installed"
                return result
        except FileNotFoundError:
            result["reason"] = "kaggle CLI not found in PATH"
            return result

    elif platform == "lightning":
        # Check lightning CLI
        try:
            ret = subprocess.run(
                ["lightning", "--version"],
                capture_output=True, text=True,
            )
            if ret.returncode != 0:
                result["reason"] = "lightning CLI not available"
                return result
        except FileNotFoundError:
            result["reason"] = "lightning CLI not found in PATH"
            return result

    elif platform == "modal":
        # Check modal is authenticated
        try:
            ret = subprocess.run(
                ["modal", "profile", "current"],
                capture_output=True, text=True,
            )
            if ret.returncode != 0:
                result["reason"] = "modal not authenticated"
                return result
        except FileNotFoundError:
            result["reason"] = "modal CLI not found in PATH"
            return result

    result["available"] = True
    result["reason"] = "ready"
    return result


# ══════════════════════════════════════════════════════════
# EXPERIMENT SELECTION
# ══════════════════════════════════════════════════════════

def decide_experiment(current_best: dict) -> dict:
    """Decide what experiment to run based on biggest gap to target."""
    brier = current_best["best_brier"]
    gap = brier - TARGET_BRIER

    experiment = {
        "type": "evolution",
        "description": "Standard genetic evolution burst",
        "priority": "normal",
        "params": {},
    }

    if gap > 0.015:
        # Far from target -- broad exploration
        experiment["type"] = "exploration"
        experiment["description"] = "Broad exploration: high mutation, diverse models"
        experiment["priority"] = "high"
        experiment["params"] = {
            "mutation_rate": 0.15,
            "population_size": 30,
            "model_diversity": True,
        }
    elif gap > 0.005:
        # Getting closer -- focused exploitation
        experiment["type"] = "exploitation"
        experiment["description"] = "Focused exploitation: fine-tune best config"
        experiment["priority"] = "high"
        experiment["params"] = {
            "mutation_rate": 0.06,
            "population_size": 20,
            "focus_features": True,
        }
    elif gap > 0.0:
        # Very close -- surgical tweaks
        experiment["type"] = "surgical"
        experiment["description"] = "Surgical: micro-mutations on best config"
        experiment["priority"] = "critical"
        experiment["params"] = {
            "mutation_rate": 0.03,
            "population_size": 40,
            "surgical_mode": True,
        }
    else:
        # Already at target -- push for new records
        experiment["type"] = "record_push"
        experiment["description"] = "Beyond target: push for new ATR"
        experiment["priority"] = "normal"
        experiment["params"] = {
            "mutation_rate": 0.09,
            "population_size": 25,
        }

    experiment["current_brier"] = brier
    experiment["target"] = TARGET_BRIER
    experiment["gap"] = round(gap, 5)

    return experiment


# ══════════════════════════════════════════════════════════
# DISPATCH
# ══════════════════════════════════════════════════════════

def dispatch(platform: str, experiment: dict) -> dict:
    """Dispatch an experiment to a specific platform."""
    cfg = PLATFORMS[platform]
    script = PLATFORM_SCRIPTS.get(platform)

    if not script or not script.exists():
        return {"status": "error", "reason": f"script not found: {script}"}

    log(f"Dispatching {experiment['type']} experiment to {platform} ({cfg['gpu']})")
    log(f"  Description: {experiment['description']}")
    log(f"  Current Brier: {experiment['current_brier']:.5f} | Gap: {experiment['gap']:.5f}")

    start_time = time.time()

    try:
        if platform == "zerogpu":
            cmd = [
                sys.executable, str(script),
                "--account", "all",
            ]
        elif platform == "kaggle":
            # Kaggle runs on Kaggle infrastructure, not locally
            log("Kaggle bursts must be launched manually or via kaggle API")
            cmd = [
                "kaggle", "kernels", "push",
                "-p", str(SCRIPTS_DIR / "kaggle-nba-burst.py"),
            ]
        elif platform == "lightning":
            cmd = ["bash", str(script)]
        elif platform == "modal":
            cmd = [
                sys.executable, str(script),
                "--gpu", "A10G",
                "--timeout", str(cfg["burst_duration_sec"]),
            ]
        elif platform == "colab":
            # Run colab burst script directly (it handles its own GPU detection)
            cmd = [sys.executable, str(script)]
        else:
            return {"status": "error", "reason": f"unknown platform: {platform}"}

        log(f"  Command: {' '.join(cmd)}")

        # Run with timeout (burst duration + 5 min overhead)
        timeout = cfg["burst_duration_sec"] + 300
        ret = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        )

        elapsed = time.time() - start_time

        result = {
            "status": "success" if ret.returncode == 0 else "failed",
            "platform": platform,
            "experiment": experiment["type"],
            "elapsed_sec": round(elapsed, 1),
            "exit_code": ret.returncode,
            "cost": cfg["cost_per_burst"] if ret.returncode == 0 else 0,
            "timestamp": ts(),
        }

        if ret.returncode != 0:
            result["stderr"] = ret.stderr[:500] if ret.stderr else ""
            log(f"  FAILED (exit {ret.returncode}): {ret.stderr[:200]}", "ERROR")
        else:
            log(f"  Completed in {elapsed:.0f}s")

        return result

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        log(f"  TIMEOUT after {elapsed:.0f}s", "ERROR")
        return {
            "status": "timeout",
            "platform": platform,
            "elapsed_sec": round(elapsed, 1),
            "timestamp": ts(),
        }
    except Exception as e:
        log(f"  ERROR: {e}", "ERROR")
        return {
            "status": "error",
            "platform": platform,
            "error": str(e)[:200],
            "timestamp": ts(),
        }


# ══════════════════════════════════════════════════════════
# MAIN ORCHESTRATION
# ══════════════════════════════════════════════════════════

def auto_dispatch():
    """Main orchestration: check all platforms, dispatch to best available."""
    log("=" * 60)
    log("COMPUTE ORCHESTRATOR -- Auto Dispatch")
    log("=" * 60)

    state = load_state()
    current_best = get_current_best()
    experiment = decide_experiment(current_best)

    log(f"\nCurrent best: {current_best['best_brier']:.5f} "
        f"(source: {current_best['source']}, {current_best['model_type']})")
    log(f"Target: {TARGET_BRIER:.5f} | Gap: {experiment['gap']:.5f}")
    log(f"Experiment: {experiment['type']} -- {experiment['description']}")

    # Check all platforms in priority order
    log("\nPlatform availability:")
    available_platforms = []
    for platform in sorted(PLATFORMS.keys(), key=lambda p: PLATFORMS[p]["priority"]):
        status = check_platform_available(platform, state)
        tag = "READY" if status["available"] else status["reason"]
        cost_str = f"${status['cost']:.2f}" if status["cost"] > 0 else "free"
        log(f"  {platform:12s} ({PLATFORMS[platform]['gpu']:8s}) -- {tag} [{cost_str}]")
        if status["available"]:
            available_platforms.append(platform)

    if not available_platforms:
        log("\nNo platforms available right now. Try later or use --force.")
        log_event({
            "ts": ts(), "action": "auto_dispatch", "result": "no_platforms",
            "current_brier": current_best["best_brier"],
        })
        return

    # Pick the highest priority available platform
    chosen = available_platforms[0]
    log(f"\nChosen platform: {chosen} ({PLATFORMS[chosen]['gpu']})")

    # Dispatch
    result = dispatch(chosen, experiment)

    # Update state
    if result.get("status") in ["success", "failed", "timeout"]:
        state.setdefault("last_run", {})[chosen] = ts()
        state.setdefault("daily_runs", {}).setdefault(chosen, []).append(ts())
        if result.get("cost", 0) > 0:
            state["total_cost"] = state.get("total_cost", 0) + result["cost"]

    save_state(state)
    log_event({
        "ts": ts(),
        "action": "dispatch",
        "platform": chosen,
        "experiment": experiment["type"],
        "result": result.get("status"),
        "current_brier": current_best["best_brier"],
        "cost": result.get("cost", 0),
    })

    log(f"\nResult: {result.get('status')} ({result.get('elapsed_sec', 0):.0f}s)")


def show_status():
    """Show comprehensive status of all platforms and metrics."""
    log("=" * 70)
    log("  NOMOS42 COMPUTE ORCHESTRATOR -- Status Report")
    log("=" * 70)

    # Current metrics
    current = get_current_best()
    log(f"\n  Current Best Brier: {current['best_brier']:.5f} "
        f"(source: {current['source']})")
    log(f"  Target:             {TARGET_BRIER:.5f}")
    log(f"  Gap:                {current['best_brier'] - TARGET_BRIER:.5f}")
    log(f"  ATR:                {ATR_BRIER:.5f}")

    # Platform status
    state = load_state()
    log(f"\n  {'Platform':12s} {'GPU':8s} {'Cost':8s} {'Last Run':22s} {'Status':15s}")
    log(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*22} {'-'*15}")

    for platform in sorted(PLATFORMS.keys(), key=lambda p: PLATFORMS[p]["priority"]):
        cfg = PLATFORMS[platform]
        cost_str = f"${cfg['cost_per_burst']:.2f}" if cfg['cost_per_burst'] > 0 else "free"
        last_run = state.get("last_run", {}).get(platform, "never")
        if last_run != "never":
            last_run = last_run[:19]  # Trim to readable

        avail = check_platform_available(platform, state)
        status = "READY" if avail["available"] else avail["reason"][:15]

        log(f"  {platform:12s} {cfg['gpu']:8s} {cost_str:8s} {last_run:22s} {status:15s}")

    # Latest results per platform
    log(f"\n  Latest Results:")
    log(f"  {'Platform':12s} {'Brier':10s} {'Model':15s} {'Features':10s} {'Time':10s}")
    log(f"  {'-'*12} {'-'*10} {'-'*15} {'-'*10} {'-'*10}")

    for platform, result_file in RESULT_FILES.items():
        if result_file.exists():
            try:
                r = json.loads(result_file.read_text())
                brier = r.get("best_brier", r.get("best_score", "?"))
                model = r.get("model_type", "?")[:15]
                nf = r.get("n_features", "?")
                ts_str = r.get("timestamp", "?")[:10]
                log(f"  {platform:12s} {str(brier):10s} {model:15s} {str(nf):10s} {ts_str:10s}")
            except Exception:
                log(f"  {platform:12s} (parse error)")
        else:
            log(f"  {platform:12s} (no result)")

    # Fleet status
    log(f"\n  HF Evolution Fleet:")
    fleet = get_fleet_status()
    for island in fleet:
        brier = f"{island['brier']:.5f}" if island.get("brier") else "?"
        gen = island.get("generation", "?")
        log(f"  {island['name']:4s} {island['status']:12s} brier={brier} gen={gen}")

    # Cost summary
    total_cost = state.get("total_cost", 0)
    improvements = state.get("improvements", 0)
    log(f"\n  Total cost: ${total_cost:.2f} | Improvements: {improvements}")
    log("=" * 70)


def show_plan():
    """Show today's execution plan."""
    now = datetime.now(timezone.utc)
    log("=" * 60)
    log(f"  Today's Compute Plan ({now.strftime('%Y-%m-%d')})")
    log("=" * 60)

    state = load_state()

    for hour in range(24):
        dispatches = []
        for platform, cfg in PLATFORMS.items():
            if hour in cfg["schedule_utc"]:
                dispatches.append(platform)

        if dispatches:
            past = "DONE" if hour < now.hour else ("NOW" if hour == now.hour else "    ")
            platforms_str = ", ".join(dispatches)
            gpu_str = ", ".join(PLATFORMS[p]["gpu"] for p in dispatches)
            log(f"  {hour:02d}:00 UTC [{past}] -- {platforms_str} ({gpu_str})")

    log(f"\n  On-demand: modal (A10G, ${PLATFORMS['modal']['cost_per_burst']}/burst)")
    log(f"  Manual: colab (T4, free)")
    log("=" * 60)


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Nomos42 Compute Orchestrator -- GPU workload dispatcher"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show all platforms status and metrics"
    )
    parser.add_argument(
        "--plan", action="store_true",
        help="Show today's execution plan"
    )
    parser.add_argument(
        "--force", type=str, default=None,
        choices=list(PLATFORMS.keys()),
        help="Force dispatch to a specific platform (ignores schedule/cooldown)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be dispatched without executing"
    )

    args = parser.parse_args()

    # Load env
    env_file = REPO_ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                # Strip 'export ' prefix if present
                if line.startswith("export "):
                    line = line[7:]
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and val and key not in os.environ:
                    os.environ[key] = val

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.status:
        show_status()
    elif args.plan:
        show_plan()
    elif args.force:
        # Force dispatch to specific platform
        state = load_state()
        current_best = get_current_best()
        experiment = decide_experiment(current_best)

        log(f"Forcing dispatch to {args.force}")
        log(f"Current: {current_best['best_brier']:.5f} | Experiment: {experiment['type']}")

        if args.dry_run:
            log("DRY RUN -- not executing")
        else:
            result = dispatch(args.force, experiment)
            state.setdefault("last_run", {})[args.force] = ts()
            save_state(state)
            log(f"Result: {result.get('status')}")
    else:
        if args.dry_run:
            log("DRY RUN mode")
            state = load_state()
            current_best = get_current_best()
            experiment = decide_experiment(current_best)
            log(f"Would dispatch: {experiment['type']} experiment")
            for platform in sorted(PLATFORMS.keys(), key=lambda p: PLATFORMS[p]["priority"]):
                avail = check_platform_available(platform, state)
                if avail["available"]:
                    log(f"  -> {platform} ({PLATFORMS[platform]['gpu']})")
                    break
        else:
            auto_dispatch()


if __name__ == "__main__":
    main()
