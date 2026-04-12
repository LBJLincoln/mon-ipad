#!/usr/bin/env python3
"""
Nomos42 Orchestrator — Master agent that monitors and controls the entire ecosystem.

Runs every 4 hours. Checks health of all subsystems, detects issues, takes action.

Projects: NBA Quant AI + Political Alpha
"""
import json, os, sys, subprocess, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ═══════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════

PROJECTS = {
    "nba": {
        "name": "NBA Quant AI",
        "spaces": [
            ("nomos42-nba-quant", "S10"),
            ("nomos42-nba-quant-2", "S11"),
            ("nomos42-nba-evo-3", "S12"),
            ("nomos42-nba-evo-4", "S13"),
            ("nomos42-nba-evo-5", "S14"),
            ("nomos42-nba-evo-6", "S15"),
            ("lbjlincoln26-nba-evo-s16", "S16"),
            ("lbjlincoln26-nba-evo-s17", "S17"),
        ],
        "kaggle_kernels": [
            "alexismoret6/nba-karpathy-loop",
            "alexismoret6/nba-season-backtest",
        ],
        "target_brier": 0.20,
        "current_atr": 0.21570,
    },
    "political": {
        "name": "Political Alpha",
        "spaces": [],
        "kaggle_kernels": [
            "alexismoret6/political-alpha-karpathy-loop",
        ],
        "target_brier": 0.20,
        "current_atr": None,
    },
}

_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = _ROOT / "data"
HEALTH_FILE = DATA_DIR / "agent-health.json"

# ═══════════════════════════════════════
# HEALTH CHECKS
# ═══════════════════════════════════════

def check_hf_space(space_name):
    """Check if a HuggingFace Space is running and get its latest metrics."""
    url = f"https://{space_name}.hf.space/api/status"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return {
                "status": "UP",
                "brier": data.get("best_brier"),
                "generation": data.get("generation"),
                "model": data.get("best_model_type"),
                "last_improvement": data.get("last_improvement_gen"),
                "stagnation_cycles": data.get("stagnation", 0),
            }
    except Exception as e:
        return {"status": "DOWN", "error": str(e)[:100]}


def check_kaggle_kernel(kernel_ref):
    """Check Kaggle kernel status via CLI."""
    try:
        result = subprocess.run(
            ["kaggle", "kernels", "status", kernel_ref],
            capture_output=True, text=True, timeout=45
        )
        output = result.stdout.strip()
        if "RUNNING" in output:
            return {"status": "RUNNING"}
        elif "COMPLETE" in output:
            return {"status": "COMPLETE"}
        elif "ERROR" in output:
            return {"status": "ERROR"}
        else:
            return {"status": output.split(".")[-1].strip('"') if output else "UNKNOWN"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)[:100]}


def check_data_server():
    """Check if local data server is running.

    Data server serves from /home/termius/mon-ipad/data/ on port 8080,
    so files at data/nba-agent/*.json are at http://localhost:8080/nba-agent/*.json
    """
    endpoints = ["backtest-results.json", "bankroll-state.json", "quant-summary.json"]
    results = {}
    for ep in endpoints:
        try:
            req = urllib.request.Request(f"http://localhost:8080/nba-agent/{ep}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                results[ep] = resp.status
        except:
            results[ep] = "DOWN"
    return results


def check_telegram_bots():
    """Check if Telegram bots are running."""
    bots = {}
    try:
        result = subprocess.run(
            ["pgrep", "-f", "nomos42_brain.py"], capture_output=True, text=True
        )
        bots["brain"] = "ALIVE" if result.returncode == 0 else "DOWN"
    except:
        bots["brain"] = "UNKNOWN"
    return bots


def detect_stagnation(space_data):
    """Detect if a space has stagnated (no improvement in 50+ stagnation cycles)."""
    if space_data.get("status") != "UP":
        return None
    stag_cycles = space_data.get("stagnation_cycles", 0)
    gen = space_data.get("generation", 0)
    last_imp = space_data.get("last_improvement", 0)
    # Use stagnation_cycles from API (counter), or fall back to gen-based calc
    gens_stale = stag_cycles * 10 if stag_cycles else (gen - last_imp if gen and last_imp else 0)
    if gens_stale > 200:
        return {
            "stagnant": True,
            "stagnation_cycles": stag_cycles,
            "gens_since_improvement": gens_stale,
            "recommendation": "inject_diversity" if gens_stale < 500 else "reset_population",
        }
    return {"stagnant": False}


# ═══════════════════════════════════════
# ACTIONS
# ═══════════════════════════════════════

def restart_space(space_name):
    """Restart a HuggingFace Space by hitting its keepalive endpoint."""
    url = f"https://{space_name}.hf.space/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42/1.0"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except:
        return False


def relaunch_kaggle_kernel(kernel_ref):
    """Re-push a Kaggle kernel to restart it."""
    # Map kernel ref to local script
    scripts = {
        "alexismoret6/nba-karpathy-loop": "scripts/kaggle/nba_karpathy_loop.py",
        "alexismoret6/nba-season-backtest": "scripts/kaggle/nba_season_backtest.py",
        "alexismoret6/political-alpha-karpathy-loop": None,
    }
    script = scripts.get(kernel_ref)
    if not script:
        return False

    try:
        result = subprocess.run(
            ["kaggle", "kernels", "push", "-p", str(Path(script).parent)],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except:
        return False


# ═══════════════════════════════════════
# MAIN ORCHESTRATION LOOP
# ═══════════════════════════════════════

def run_health_check():
    """Full ecosystem health check."""
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "projects": {},
        "infra": {},
        "actions_taken": [],
        "issues": [],
    }

    # Check each project
    for proj_id, proj in PROJECTS.items():
        proj_report = {"name": proj["name"], "spaces": {}, "kaggle": {}}

        # HF Spaces
        for space_name, label in proj["spaces"]:
            data = check_hf_space(space_name)
            proj_report["spaces"][label] = data

            # Auto-restart DOWN spaces
            if data["status"] == "DOWN":
                report["issues"].append(f"{label} ({space_name}) is DOWN")
                if restart_space(space_name):
                    report["actions_taken"].append(f"Restarted {label}")

            # Detect stagnation
            stag = detect_stagnation(data)
            if stag and stag.get("stagnant"):
                report["issues"].append(
                    f"{label} stagnant: {stag['gens_since_improvement']} gens without improvement"
                )
                data["stagnation"] = stag

        # Kaggle kernels
        for kernel in proj["kaggle_kernels"]:
            k_name = kernel.split("/")[1]
            data = check_kaggle_kernel(kernel)
            proj_report["kaggle"][k_name] = data

            if data["status"] == "ERROR":
                report["issues"].append(f"Kaggle {k_name} ERRORED")

        report["projects"][proj_id] = proj_report

    # Infrastructure
    report["infra"]["data_server"] = check_data_server()
    report["infra"]["telegram"] = check_telegram_bots()

    # Summary
    n_spaces_up = sum(
        1 for p in report["projects"].values()
        for s in p["spaces"].values()
        if s["status"] == "UP"
    )
    n_spaces_total = sum(len(p["spaces"]) for p in report["projects"].values())
    n_issues = len(report["issues"])

    report["summary"] = {
        "spaces": f"{n_spaces_up}/{n_spaces_total} UP",
        "issues": n_issues,
        "actions": len(report["actions_taken"]),
        "status": "HEALTHY" if n_issues == 0 else "DEGRADED" if n_issues <= 2 else "CRITICAL",
    }

    # Save
    HEALTH_FILE.write_text(json.dumps(report, indent=2))
    return report


def print_report(report):
    """Print health report to console."""
    print(f"\n{'='*60}")
    print(f"  NOMOS42 ORCHESTRATOR — {report['timestamp'][:19]}")
    print(f"  Status: {report['summary']['status']}")
    print(f"{'='*60}")

    for proj_id, proj in report["projects"].items():
        print(f"\n  [{proj['name'].upper()}]")
        for label, data in proj["spaces"].items():
            if data["status"] == "UP":
                brier = f"brier={data.get('brier', '?')}"
                gen = f"gen={data.get('generation', '?')}"
                print(f"    {label}: UP  {brier}  {gen}")
            else:
                print(f"    {label}: DOWN")

        for name, data in proj["kaggle"].items():
            print(f"    Kaggle/{name}: {data['status']}")

    if report["issues"]:
        print(f"\n  ISSUES ({len(report['issues'])}):")
        for issue in report["issues"]:
            print(f"    - {issue}")

    if report["actions_taken"]:
        print(f"\n  ACTIONS TAKEN:")
        for action in report["actions_taken"]:
            print(f"    + {action}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    report = run_health_check()
    print_report(report)
