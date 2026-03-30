#!/usr/bin/env python3
"""
Pierre Monitoring Agents (3 dedicated)
======================================
Agent 23: pierre-usage-monitor    — Claude Code CLI quota consumption
Agent 24: pierre-practice-monitor — Optimize patterns, suggest improvements
Agent 25: pierre-infra-monitor    — RAM/CPU/GPU usage on Pierre's MacBook

Run: python3 scripts/agents/pierre-monitor.py
Cron: */30 * * * * python3 ~/mon-ipad/scripts/agents/pierre-monitor.py
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "fleet"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PIERRE_REPO = Path.home() / "nomos-pierre"
LOG_FILE = DATA_DIR / "pierre-monitor.json"


def agent_23_usage_monitor():
    """
    Monitor Pierre's Claude Code CLI usage vs Alexis's daily/weekly quota.
    Reads git log from nomos-pierre to estimate session count and token usage.
    """
    report = {
        "agent": "pierre-usage-monitor",
        "agent_id": 23,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if not PIERRE_REPO.exists():
        report["status"] = "repo_not_found"
        return report

    try:
        # Count commits today (each 'auto: session sync' = 1 Claude session)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = subprocess.run(
            ["git", "-C", str(PIERRE_REPO), "log", "--oneline",
             f"--since={today}", "--all"],
            capture_output=True, text=True, timeout=10
        )
        commits_today = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

        # Count commits this week
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        result_week = subprocess.run(
            ["git", "-C", str(PIERRE_REPO), "log", "--oneline",
             f"--since={week_ago}", "--all"],
            capture_output=True, text=True, timeout=10
        )
        commits_week = len(result_week.stdout.strip().split("\n")) if result_week.stdout.strip() else 0

        # Count 'auto: session sync' commits specifically (= Claude sessions)
        result_sessions = subprocess.run(
            ["git", "-C", str(PIERRE_REPO), "log", "--oneline",
             f"--since={week_ago}", "--all", "--grep=auto: session"],
            capture_output=True, text=True, timeout=10
        )
        sessions_week = len(result_sessions.stdout.strip().split("\n")) if result_sessions.stdout.strip() else 0

        # Estimate cost: ~$0.50-2 per session (Opus usage)
        est_cost_low = sessions_week * 0.50
        est_cost_high = sessions_week * 2.00

        report["status"] = "ok"
        report["commits_today"] = commits_today
        report["commits_this_week"] = commits_week
        report["claude_sessions_this_week"] = sessions_week
        report["estimated_cost_usd"] = f"${est_cost_low:.2f}-${est_cost_high:.2f}"
        report["alert"] = sessions_week > 50  # Alert if >50 sessions/week

    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)

    return report


def agent_24_practice_monitor():
    """
    Monitor Pierre's practices for optimization:
    - Which agents/skills does he use most?
    - What patterns can be improved?
    - Session duration estimates
    """
    report = {
        "agent": "pierre-practice-monitor",
        "agent_id": 24,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if not PIERRE_REPO.exists():
        report["status"] = "repo_not_found"
        return report

    try:
        # Analyze commit messages for skill/agent usage patterns
        result = subprocess.run(
            ["git", "-C", str(PIERRE_REPO), "log", "--oneline", "-100", "--all"],
            capture_output=True, text=True, timeout=10
        )
        commits = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Count patterns
        skills_used = {}
        agent_mentions = {}
        for commit in commits:
            msg = commit.lower()
            for skill in ["karpathy", "daily-edge", "progress", "spaces-health",
                          "evolve-report", "agent-review", "cross-repo"]:
                if skill in msg:
                    skills_used[skill] = skills_used.get(skill, 0) + 1
            for agent in ["research", "feature", "evolution", "betting",
                          "odds", "backtest", "halftime"]:
                if agent in msg:
                    agent_mentions[agent] = agent_mentions.get(agent, 0) + 1

        # Check file changes for activity areas
        result_diff = subprocess.run(
            ["git", "-C", str(PIERRE_REPO), "diff", "--stat", "HEAD~10..HEAD"],
            capture_output=True, text=True, timeout=10
        )
        files_changed = result_diff.stdout.strip() if result_diff.stdout.strip() else "none"

        report["status"] = "ok"
        report["total_commits_analyzed"] = len(commits)
        report["skills_used"] = skills_used
        report["agent_mentions"] = agent_mentions
        report["recent_file_changes"] = files_changed[:500]  # Truncate
        report["recommendations"] = []

        if not skills_used:
            report["recommendations"].append("Pierre hasn't used any skills yet — send tutorial")
        if len(skills_used) == 1:
            report["recommendations"].append(f"Pierre only uses {list(skills_used.keys())[0]} — suggest others")

    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)

    return report


def agent_25_infra_monitor():
    """
    Monitor Pierre's MacBook resource usage (when SSH is available).
    Track: RAM available, CPU load, disk space, GPU (Intel) status.
    Determines how much compute we can offload to Pierre.
    """
    report = {
        "agent": "pierre-infra-monitor",
        "agent_id": 25,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Try SSH to Pierre's machine (if key is configured)
    ssh_key = Path.home() / ".ssh" / "pierre_fleet"
    pierre_ip = os.environ.get("PIERRE_IP", "")

    if not pierre_ip:
        report["status"] = "no_ip_configured"
        report["note"] = "Set PIERRE_IP in .env.local once Pierre is connected"
        return report

    if not ssh_key.exists():
        report["status"] = "no_ssh_key"
        return report

    try:
        # Get system stats via SSH
        cmd = (
            f"ssh -i {ssh_key} -o ConnectTimeout=10 -o StrictHostKeyChecking=no "
            f"-o BatchMode=yes pierre@{pierre_ip} "
            "'echo CPU:$(sysctl -n hw.ncpu 2>/dev/null || nproc);echo RAM:$(sysctl -n hw.memsize 2>/dev/null || free -b | awk \"/Mem:/ {print \\$2}\");echo LOAD:$(uptime | awk -F\"load average:\" \"{print \\$2}\");echo DISK:$(df -g ~ | awk \"NR==2 {print \\$4}\")GB_free'"
        )
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=15
        )

        if result.returncode == 0:
            stats = {}
            for line in result.stdout.strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    stats[k.strip().lower()] = v.strip()

            report["status"] = "ok"
            report["stats"] = stats

            # Determine available compute
            load_str = stats.get("load", "0,0,0")
            try:
                load_1m = float(load_str.split(",")[0].strip())
                report["load_1m"] = load_1m
                report["can_offload"] = load_1m < 1.5  # Can offload if load < 1.5
            except:
                report["can_offload"] = None
        else:
            report["status"] = "ssh_failed"
            report["error"] = result.stderr[:200]

    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)

    return report


def run_all():
    """Run all 3 Pierre monitoring agents."""
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agents": [
            agent_23_usage_monitor(),
            agent_24_practice_monitor(),
            agent_25_infra_monitor(),
        ]
    }

    # Write report
    LOG_FILE.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))

    # Alert if cost is high
    usage = results["agents"][0]
    if usage.get("alert"):
        print(f"\n⚠️  ALERT: Pierre used {usage.get('claude_sessions_this_week', '?')} "
              f"sessions this week (est. {usage.get('estimated_cost_usd', '?')})")

    return results


if __name__ == "__main__":
    run_all()
