#!/usr/bin/env python3
"""Cross-Repo Dashboard — Aggregates self-improvement status from ALL repos.

Shows per-repo:
  - Agentic loop: active/inactive, last cycle, cycle count
  - Self-improvement: improvements made, reverts, trend
  - Eval: test pass rate, coverage metric
  - Git: activity, commits, freshness
  - Health: overall score

Reads from:
  - /home/termius/mon-ipad/data/cross-repo/{repo}-status.json (written by universal-agent-loop.py)
  - Git repos directly for activity metrics
  - Local state files for eval results

Usage:
    python3 ops/cross-repo-dashboard.py              # Print dashboard
    python3 ops/cross-repo-dashboard.py --json        # JSON output (for HTTP server / Vercel)
    python3 ops/cross-repo-dashboard.py --loop 300    # Refresh every 5min
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

BASE_DIR = Path("/home/termius/mon-ipad")
CROSS_REPO_DIR = BASE_DIR / "data" / "cross-repo"
OUTPUT_FILE = BASE_DIR / "data" / "cross-repo-dashboard.json"

REPOS = {
    "mon-ipad": {
        "path": "/home/termius/mon-ipad",
        "type": "control",
        "description": "Tour de controle — eval, ops, agents",
        "eval_sources": ["data/eval/blast-state.json", "data/agents/v2/dashboard.json"],
        "loop_indicators": ["data/agents/v2/orchestrator.pid", "ops/rag-self-improve.py"],
    },
    "rag-website": {
        "path": "/home/termius/rag-website",
        "type": "nextjs",
        "description": "Product website — 9 Vercel pages",
        "eval_sources": [],
        "loop_indicators": ["data/self-improve-state.json"],
    },
    "rag-data-ingestion": {
        "path": "/home/termius/rag-data-ingestion",
        "type": "python",
        "description": "Ingestion engine — Docling, chunking, embedding",
        "eval_sources": [],
        "loop_indicators": ["data/self-improve-state.json", "testing-daemon.sh"],
    },
    "rag-dashboard": {
        "path": "/home/termius/rag-dashboard",
        "type": "static",
        "description": "Dashboard — HTML/JS control panels",
        "eval_sources": [],
        "loop_indicators": ["data/self-improve-state.json"],
    },
    "nomos-nba-agent": {
        "path": "/home/termius/nomos-nba-agent",
        "type": "python",
        "description": "NBA quant agent — Tony Bloom system",
        "eval_sources": ["data/nba-agent/eval-history.jsonl"],
        "loop_indicators": ["data/self-improve-state.json", "ops/self-improve.py"],
    },
}


def git_info(repo_path):
    """Get git activity info for a repo."""
    if not Path(repo_path).exists():
        return {"exists": False}
    def run(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path, timeout=10)
            return r.stdout.strip()
        except Exception:
            return ""
    try:
        commits_7d = len(run(["git", "log", "--oneline", "--since=7 days ago"]).splitlines())
        commits_24h = len(run(["git", "log", "--oneline", "--since=24 hours ago"]).splitlines())
        last_commit = run(["git", "log", "-1", "--format=%ci"])
        last_msg = run(["git", "log", "-1", "--format=%s"])
        total = int(run(["git", "rev-list", "--count", "HEAD"]) or 0)
        branch = run(["git", "branch", "--show-current"])
        dirty = len(run(["git", "status", "--porcelain"]).splitlines())
        return {
            "exists": True, "branch": branch, "total_commits": total,
            "commits_7d": commits_7d, "commits_24h": commits_24h,
            "last_commit": last_commit[:19], "last_msg": last_msg[:80],
            "dirty_files": dirty,
        }
    except Exception as e:
        return {"exists": True, "error": str(e)[:100]}


def check_loop_status(repo_name, repo_config):
    """Check if agentic loop is active for this repo."""
    repo_path = repo_config["path"]

    # Check central cross-repo status (written by universal-agent-loop.py)
    status_file = CROSS_REPO_DIR / f"{repo_name}-status.json"
    if status_file.exists():
        try:
            data = json.loads(status_file.read_text())
            last_cycle = data.get("last_cycle", "")
            if last_cycle:
                # Active if last cycle was within 2 hours
                try:
                    dt = datetime.fromisoformat(last_cycle.replace("Z", "+00:00"))
                    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                    return {
                        "active": age_hours < 2,
                        "last_cycle": last_cycle,
                        "age_hours": round(age_hours, 1),
                        "total_cycles": data.get("total_cycles", 0),
                        "total_improvements": data.get("total_improvements", 0),
                        "last_action": data.get("last_action"),
                        "last_result": data.get("last_result"),
                        "source": "cross-repo",
                    }
                except Exception:
                    pass
            return {"active": True, "source": "cross-repo", **data}
        except Exception:
            pass

    # Check local state file
    for indicator in repo_config.get("loop_indicators", []):
        state_path = Path(repo_path) / indicator
        if state_path.exists() and state_path.suffix == ".json":
            try:
                data = json.loads(state_path.read_text())
                last_updated = data.get("last_updated", "")
                if last_updated:
                    try:
                        dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                        return {
                            "active": age_hours < 2,
                            "last_cycle": last_updated,
                            "age_hours": round(age_hours, 1),
                            "total_cycles": data.get("cycles", 0),
                            "total_improvements": data.get("improvements", 0),
                            "source": indicator,
                        }
                    except Exception:
                        pass
            except Exception:
                pass

    # Special: mon-ipad has V2 orchestrator
    if repo_name == "mon-ipad":
        orch_state = Path(repo_path) / "data" / "agents" / "v2" / "orchestrator-state.json"
        if orch_state.exists():
            try:
                data = json.loads(orch_state.read_text())
                # last_cycle_ts is nested under repos.{name}
                last = data.get("last_cycle_ts", "")
                if not last:
                    for rdata in data.get("repos", {}).values():
                        ts = rdata.get("last_cycle_ts", "")
                        if ts > last:
                            last = ts
                if last:
                    dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                    return {
                        "active": age_hours < 2,
                        "last_cycle": last,
                        "age_hours": round(age_hours, 1),
                        "total_cycles": data.get("total_cycles", 0),
                        "total_improvements": data.get("total_improvements", 0),
                        "source": "v2-orchestrator",
                    }
            except Exception:
                pass

    # Check PID files
    for indicator in repo_config.get("loop_indicators", []):
        if indicator.endswith(".pid"):
            pid_path = Path(repo_path) / indicator
            if pid_path.exists():
                try:
                    pid = int(pid_path.read_text().strip())
                    os.kill(pid, 0)  # Check if process alive
                    return {"active": True, "pid": pid, "source": indicator}
                except (ProcessLookupError, ValueError):
                    pass

    return {"active": False, "source": "none"}


def check_eval_status(repo_name, repo_config):
    """Check eval/test status for a repo."""
    repo_path = repo_config["path"]

    # Check eval sources
    for source in repo_config.get("eval_sources", []):
        source_path = Path(repo_path) / source
        if not source_path.exists():
            # Try in mon-ipad
            source_path = BASE_DIR / source
        if source_path.exists():
            try:
                data = json.loads(source_path.read_text())
                if isinstance(data, dict):
                    return {
                        "has_eval": True,
                        "source": source,
                        "data": {k: v for k, v in list(data.items())[:5]},
                    }
            except Exception:
                pass

    # Count test files
    test_patterns = ["test_*.py", "*.test.ts", "*.test.tsx", "*.spec.ts"]
    test_count = 0
    for pat in test_patterns:
        test_count += len(list(Path(repo_path).rglob(pat)))

    return {
        "has_eval": test_count > 0,
        "test_files": test_count,
        "source": "file_count",
    }


def compute_health_score(git, loop, eval_status):
    """Compute overall health score 0-100."""
    score = 0

    # Git activity (30 points)
    if git.get("commits_7d", 0) >= 5:
        score += 30
    elif git.get("commits_7d", 0) >= 1:
        score += 15

    # Agentic loop active (40 points)
    if loop.get("active"):
        score += 40
    elif loop.get("total_cycles", 0) > 0:
        score += 10

    # Eval exists (30 points)
    if eval_status.get("has_eval"):
        score += 15
        if eval_status.get("test_files", 0) >= 5:
            score += 15
        elif eval_status.get("test_files", 0) >= 1:
            score += 5

    return score


def build_dashboard():
    """Build the full cross-repo dashboard."""
    now = datetime.now(timezone.utc).isoformat()
    dashboard = {
        "timestamp": now,
        "repos": {},
        "summary": {},
    }

    total_health = 0
    active_loops = 0
    total_improvements = 0

    for repo_name, repo_config in REPOS.items():
        git = git_info(repo_config["path"])
        loop = check_loop_status(repo_name, repo_config)
        eval_status = check_eval_status(repo_name, repo_config)
        health = compute_health_score(git, loop, eval_status)

        dashboard["repos"][repo_name] = {
            "description": repo_config["description"],
            "type": repo_config["type"],
            "git": git,
            "agentic_loop": loop,
            "eval": eval_status,
            "health_score": health,
        }

        total_health += health
        if loop.get("active"):
            active_loops += 1
        total_improvements += loop.get("total_improvements", 0)

    dashboard["summary"] = {
        "total_repos": len(REPOS),
        "active_loops": active_loops,
        "avg_health": round(total_health / max(len(REPOS), 1), 1),
        "total_improvements": total_improvements,
    }

    return dashboard


def print_dashboard(dashboard):
    """Pretty-print the dashboard."""
    print("\n" + "=" * 70)
    print("  CROSS-REPO DASHBOARD — Self-Improvement Status")
    print(f"  {dashboard['timestamp'][:19]}")
    print("=" * 70)

    summary = dashboard["summary"]
    print(f"\n  Active Loops: {summary['active_loops']}/{summary['total_repos']}"
          f"  |  Avg Health: {summary['avg_health']}%"
          f"  |  Total Improvements: {summary['total_improvements']}")
    print("-" * 70)

    for repo_name, repo_data in dashboard["repos"].items():
        health = repo_data["health_score"]
        loop = repo_data["agentic_loop"]
        git = repo_data["git"]
        eval_st = repo_data["eval"]

        # Health indicator
        if health >= 70:
            indicator = "[OK]"
        elif health >= 40:
            indicator = "[!!]"
        else:
            indicator = "[XX]"

        loop_status = "ACTIVE" if loop.get("active") else "INACTIVE"
        loop_detail = ""
        if loop.get("total_cycles", 0) > 0:
            loop_detail = f" ({loop['total_cycles']} cycles, {loop.get('total_improvements', 0)} improvements)"
        elif loop.get("age_hours"):
            loop_detail = f" (last: {loop['age_hours']:.0f}h ago)"

        commits = git.get("commits_7d", 0)
        tests = eval_st.get("test_files", 0)

        print(f"\n  {indicator} {repo_name} — {health}% health")
        print(f"      Type: {repo_data['type']} | {repo_data['description']}")
        print(f"      Loop: {loop_status}{loop_detail}")
        print(f"      Git:  {commits} commits/7d | last: {git.get('last_msg', 'N/A')[:50]}")
        print(f"      Eval: {tests} test files | {'HAS' if eval_st.get('has_eval') else 'NO'} eval")

    print("\n" + "=" * 70)

    # Recommendations
    inactive = [n for n, d in dashboard["repos"].items() if not d["agentic_loop"].get("active")]
    no_eval = [n for n, d in dashboard["repos"].items() if not d["eval"].get("has_eval")]
    low_health = [n for n, d in dashboard["repos"].items() if d["health_score"] < 40]

    if inactive or no_eval or low_health:
        print("\n  RECOMMENDATIONS:")
        if inactive:
            print(f"    - Start agentic loops for: {', '.join(inactive)}")
        if no_eval:
            print(f"    - Add eval/tests for: {', '.join(no_eval)}")
        if low_health:
            print(f"    - Low health repos need attention: {', '.join(low_health)}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Cross-Repo Self-Improvement Dashboard")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    parser.add_argument("--loop", type=int, metavar="INTERVAL", help="Refresh interval (seconds)")
    args = parser.parse_args()

    while True:
        dashboard = build_dashboard()

        # Always save JSON
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(dashboard, indent=2, default=str))

        if args.json:
            print(json.dumps(dashboard, indent=2, default=str))
        else:
            print_dashboard(dashboard)

        if not args.loop:
            break

        time.sleep(args.loop)


if __name__ == "__main__":
    main()
