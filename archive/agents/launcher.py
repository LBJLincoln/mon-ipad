#!/usr/bin/env python3
"""7-Category Agent Launcher — Dogfooding our own framework.

Usage:
    python3 agents/launcher.py launch all     # Start all 7 agents
    python3 agents/launcher.py launch business # Start one agent
    python3 agents/launcher.py status          # Show all agent statuses
    python3 agents/launcher.py stop all        # Stop all agents
    python3 agents/launcher.py stop business   # Stop one agent
    python3 agents/launcher.py run business    # Run one agent foreground (--once)
    python3 agents/launcher.py report          # Generate cross-category report
"""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/home/termius/mon-ipad")
AGENTS_DIR = BASE_DIR / "agents"
DATA_DIR = BASE_DIR / "data" / "agents"
PID_DIR = DATA_DIR

# 7 Enterprise Categories — same as what we sell
CATEGORIES = {
    "strategie": {
        "script": "strategie/agent.py",
        "interval": 21600,  # 6h
        "description": "Market intelligence, competitive analysis, roadmap",
        "color": "\033[94m",  # Blue
    },
    "produit": {
        "script": "produit/agent.py",
        "interval": 600,  # 10min
        "description": "Product health, UX monitoring, feature tracking",
        "color": "\033[95m",  # Purple
    },
    "business": {
        "script": "business/agent.py",
        "interval": 3600,  # 1h
        "description": "Revenue tracking (Stripe/Whop/Gumroad), cost analysis",
        "color": "\033[92m",  # Green
    },
    "communication": {
        "script": "communication/agent.py",
        "interval": 43200,  # 12h
        "description": "Social media, content generation, Telegram broadcasts",
        "color": "\033[96m",  # Cyan
    },
    "admin": {
        "script": "admin/agent.py",
        "interval": 3600,  # 1h
        "description": "Credential auditing, cost tracking, infra health",
        "color": "\033[93m",  # Yellow
    },
    "test_eval": {
        "script": "test_eval/agent.py",
        "interval": 1800,  # 30min
        "description": "Pipeline testing, accuracy tracking, regression guard",
        "color": "\033[91m",  # Red
    },
    "amelioration": {
        "script": "amelioration/agent.py",
        "interval": 7200,  # 2h
        "description": "Karpathy-style improvement, weakness identification",
        "color": "\033[33m",  # Orange
    },
}

RESET = "\033[0m"


def get_pid_file(category):
    return PID_DIR / f"{category}.pid"


def is_running(category):
    pid_file = get_pid_file(category)
    if not pid_file.exists():
        return False, 0
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # Check if process exists
        return True, pid
    except (ProcessLookupError, ValueError, PermissionError):
        pid_file.unlink(missing_ok=True)
        return False, 0


def launch(category):
    """Launch an agent as a background daemon."""
    if category not in CATEGORIES:
        print(f"Unknown category: {category}")
        return False

    running, pid = is_running(category)
    if running:
        print(f"  [{category}] Already running (PID {pid})")
        return True

    config = CATEGORIES[category]
    script = AGENTS_DIR / config["script"]

    if not script.exists():
        print(f"  [{category}] Script not found: {script}")
        return False

    # Source env and launch
    env = os.environ.copy()
    env_file = BASE_DIR / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                if line.startswith("export "):
                    line = line[7:]
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip("'\"")

    log_dir = DATA_DIR / category
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"

    with open(log_file, "a") as log:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(BASE_DIR),
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )

    pid_file = get_pid_file(category)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(proc.pid))

    color = config["color"]
    print(f"  {color}[{category}]{RESET} Launched PID {proc.pid} — {config['description']}")
    return True


def stop(category):
    """Stop an agent."""
    running, pid = is_running(category)
    if not running:
        print(f"  [{category}] Not running")
        return

    try:
        os.kill(pid, signal.SIGTERM)
        print(f"  [{category}] Stopped PID {pid}")
    except Exception as e:
        print(f"  [{category}] Error stopping: {e}")

    get_pid_file(category).unlink(missing_ok=True)


def status():
    """Show status of all 7 agents."""
    print(f"\n{'='*60}")
    print(f"  NOMOS 7-CATEGORY AGENTS — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    total_running = 0
    for cat, config in CATEGORIES.items():
        running, pid = is_running(cat)
        color = config["color"]
        status_str = f"{'UP':>4} (PID {pid})" if running else f"{'DOWN':>4}"
        icon = "●" if running else "○"

        # Check for latest event
        events_file = DATA_DIR / cat / "events.jsonl"
        last_event = ""
        if events_file.exists():
            try:
                lines = events_file.read_text().strip().split("\n")
                if lines:
                    last = json.loads(lines[-1])
                    last_event = f" | Last: {last.get('timestamp', '?')[:16]}"
            except Exception:
                pass

        print(f"  {color}{icon} {cat:<15}{RESET} {status_str}{last_event}")
        print(f"    {config['description']}")
        print(f"    Cycle: {config['interval']}s ({config['interval']//60}min)")
        print()

        if running:
            total_running += 1

    print(f"  Total: {total_running}/7 running\n")


def run_once(category):
    """Run an agent once in foreground."""
    if category not in CATEGORIES:
        print(f"Unknown category: {category}")
        return

    config = CATEGORIES[category]
    script = AGENTS_DIR / config["script"]
    subprocess.run([sys.executable, str(script), "--once"], cwd=str(BASE_DIR))


def report():
    """Generate cross-category report."""
    print(f"\n{'='*60}")
    print(f"  CROSS-CATEGORY REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    for cat in CATEGORIES:
        events_file = DATA_DIR / cat / "events.jsonl"
        if not events_file.exists():
            print(f"  [{cat}] No data yet")
            continue

        try:
            lines = events_file.read_text().strip().split("\n")
            if lines:
                latest = json.loads(lines[-1])
                print(f"  [{cat}] Last tick: {latest.get('timestamp', '?')[:16]}")
                # Print key metrics from each category
                for key in ["summary", "scores", "credentials_ok", "proposal"]:
                    if key in latest:
                        val = latest[key]
                        if isinstance(val, dict):
                            for k, v in list(val.items())[:3]:
                                print(f"    {k}: {v}")
                        else:
                            print(f"    {key}: {val}")
        except Exception as e:
            print(f"  [{cat}] Error reading: {e}")
        print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()

    if cmd == "status":
        status()

    elif cmd == "launch":
        target = sys.argv[2] if len(sys.argv) > 2 else "all"
        if target == "all":
            print(f"\nLaunching all 7 category agents...\n")
            for cat in CATEGORIES:
                launch(cat)
            print(f"\nDone. Use 'python3 agents/launcher.py status' to check.")
        elif target in CATEGORIES:
            launch(target)
        else:
            print(f"Unknown target: {target}. Available: all, {', '.join(CATEGORIES.keys())}")

    elif cmd == "stop":
        target = sys.argv[2] if len(sys.argv) > 2 else "all"
        if target == "all":
            print("Stopping all agents...")
            for cat in CATEGORIES:
                stop(cat)
        elif target in CATEGORIES:
            stop(target)
        else:
            print(f"Unknown: {target}")

    elif cmd == "run":
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        if target in CATEGORIES:
            run_once(target)
        else:
            print(f"Usage: launcher.py run <category>")
            print(f"Categories: {', '.join(CATEGORIES.keys())}")

    elif cmd == "report":
        report()

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: launch, stop, status, run, report")


if __name__ == "__main__":
    main()
