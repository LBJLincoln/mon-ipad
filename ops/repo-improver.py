#!/usr/bin/env python3
"""Multi-Repo Claude Code Improver — Cycles through ALL repos with Claude Code CLI.

Each cycle:
  1. Pick the repo with the oldest improvement timestamp
  2. Run Claude Code CLI with `--print` to analyze + suggest + apply improvements
  3. Git commit + push if successful
  4. Log results
  5. Move to next repo

Repos: mon-ipad, rag-website, nomos-nba-agent, nomos-casino, nomos-forge-tests, rag-data-ingestion, rag-dashboard

Usage:
    source .env.local
    python3 ops/repo-improver.py --once          # Single repo improvement
    python3 ops/repo-improver.py --daemon 600    # Loop every 10min
    python3 ops/repo-improver.py --repo rag-website --once  # Specific repo
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Force line buffering
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

BASE_DIR = Path("/home/termius/mon-ipad")
STATE_FILE = BASE_DIR / "data" / "repo-improver-state.json"
LOG_FILE = BASE_DIR / "data" / "repo-improver-log.jsonl"

REPOS = {
    "rag-website": {
        "path": "/home/termius/rag-website",
        "type": "nextjs",
        "prompt": """Read src/app/ directory listing. Pick ONE page that needs improvement. Read that page's code. Make ONE specific improvement: fix a bug, improve a visual element, add missing functionality, or enhance mobile responsiveness. The change must be small (under 50 lines diff). Do NOT rewrite entire files.""",
    },
    "nomos-nba-agent": {
        "path": "/home/termius/nomos-nba-agent",
        "type": "python",
        "prompt": """Analyze this NBA AI agent repo. Find the single highest-impact improvement.
Focus on: eval accuracy, expert data coverage, betting model quality, NBA knowledge base completeness, agent performance.
Apply the improvement. Keep changes minimal and focused. Commit with descriptive message.""",
    },
    "nomos-casino": {
        "path": "/home/termius/nomos-casino",
        "type": "python",
        "prompt": """Analyze this casino/game testing repo. Find the single highest-impact improvement.
Focus on: test coverage, game engagement scoring, user persona coverage, sync quality.
Apply the improvement. Keep changes minimal and focused. Commit with descriptive message.""",
    },
    "nomos-forge-tests": {
        "path": "/home/termius/nomos-forge-tests",
        "type": "python",
        "prompt": """Analyze this Factory test repo. Find the single highest-impact improvement.
Focus on: test accuracy, category coverage (7 categories), evaluation depth, reporting quality.
Apply the improvement. Keep changes minimal and focused. Commit with descriptive message.""",
    },
    "mon-ipad": {
        "path": "/home/termius/mon-ipad",
        "type": "python",
        "prompt": """Analyze this control tower repo. Find the single highest-impact improvement in ops/ scripts.
Focus on: monitor accuracy, eval coverage, ingestion efficiency, agent reliability.
Apply the improvement. Keep changes minimal and focused. Commit with descriptive message.
DO NOT modify directives/ or CLAUDE.md.""",
    },
}


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix = {"INFO": "[+]", "WARN": "[!]", "ERROR": "[X]"}.get(level, "[*]")
    print(f" {ts} {prefix} {msg}")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"repos": {}, "total_improvements": 0, "started": datetime.now(timezone.utc).isoformat()}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def log_result(result):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(result) + "\n")


def pick_next_repo(state, target_repo=None):
    """Pick the repo with the oldest improvement timestamp."""
    if target_repo:
        return target_repo

    oldest_ts = None
    oldest_repo = None
    for name in REPOS:
        repo_state = state.get("repos", {}).get(name, {})
        last_improved = repo_state.get("last_improved", "2020-01-01")
        if oldest_ts is None or last_improved < oldest_ts:
            oldest_ts = last_improved
            oldest_repo = name
    return oldest_repo


def improve_repo(repo_name):
    """Run Claude Code CLI on a repo to make one improvement."""
    repo_config = REPOS[repo_name]
    repo_path = repo_config["path"]

    if not Path(repo_path).exists():
        log(f"Repo {repo_name} not found at {repo_path}", "ERROR")
        return {"ok": False, "error": "repo not found", "repo": repo_name}

    log(f"Improving {repo_name} at {repo_path}...")

    # Run Claude Code CLI with --print flag
    prompt = repo_config["prompt"]
    start = time.time()

    try:
        result = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions", prompt],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
            cwd=repo_path,
        )
        duration = round(time.time() - start, 1)
        output = (result.stdout or "").strip()
        if result.returncode != 0 and result.stderr:
            output = output + "\n" + result.stderr.strip() if output else result.stderr.strip()

        # Check if changes were made
        git_status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=repo_path,
        )
        has_changes = bool(git_status.stdout.strip())

        if has_changes:
            # Commit and push
            subprocess.run(["git", "add", "-A"], cwd=repo_path)
            subprocess.run(
                ["git", "commit", "-m", f"improve: Auto-improvement by Claude Code\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"],
                cwd=repo_path, capture_output=True,
            )
            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=repo_path, capture_output=True, text=True,
            )
            pushed = push_result.returncode == 0
            log(f"  Changes committed and {'pushed' if pushed else 'push FAILED'}")
        else:
            pushed = False
            log(f"  No changes to commit")

        # Truncate output for logging
        if len(output) > 2000:
            output = output[:1000] + "\n...(truncated)...\n" + output[-800:]

        return {
            "ok": True,
            "repo": repo_name,
            "duration": duration,
            "has_changes": has_changes,
            "pushed": pushed,
            "output_preview": output[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except subprocess.TimeoutExpired:
        log(f"  Timeout (600s) for {repo_name}", "WARN")
        return {
            "ok": False,
            "repo": repo_name,
            "error": "timeout",
            "duration": 600,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log(f"  Error: {e}", "ERROR")
        return {
            "ok": False,
            "repo": repo_name,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(description="Multi-repo Claude Code improver daemon")
    parser.add_argument("--once", action="store_true", help="Run single improvement cycle")
    parser.add_argument("--daemon", type=int, metavar="SECONDS", help="Loop with interval")
    parser.add_argument("--repo", type=str, choices=list(REPOS.keys()), help="Target specific repo")
    args = parser.parse_args()

    print("=" * 60)
    print("  MULTI-REPO CLAUDE CODE IMPROVER")
    print(f"  Repos: {', '.join(REPOS.keys())}")
    print(f"  Mode: {'daemon ' + str(args.daemon) + 's' if args.daemon else 'once'}")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    state = load_state()

    while True:
        repo_name = pick_next_repo(state, args.repo)
        log(f"Selected repo: {repo_name}")

        result = improve_repo(repo_name)
        log_result(result)

        # Update state
        if "repos" not in state:
            state["repos"] = {}
        state["repos"][repo_name] = {
            "last_improved": datetime.now(timezone.utc).isoformat(),
            "last_result": "ok" if result.get("ok") else result.get("error", "unknown"),
            "has_changes": result.get("has_changes", False),
        }
        if result.get("ok") and result.get("has_changes"):
            state["total_improvements"] = state.get("total_improvements", 0) + 1
        save_state(state)

        if args.once or not args.daemon:
            break

        log(f"Sleeping {args.daemon}s before next cycle...")
        time.sleep(args.daemon)


if __name__ == "__main__":
    main()
