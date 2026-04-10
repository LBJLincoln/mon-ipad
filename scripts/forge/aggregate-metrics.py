#!/usr/bin/env python3
"""
Forge v19 — Cross-repo metrics aggregator.
Scans all repos for department metrics and produces a unified report.

Usage: python3 aggregate-metrics.py [--output /path/to/report.json]
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPOS = [
    "/home/termius/mon-ipad",
    "/home/termius/nomos-nba-agent",
    "/home/termius/nomos-political-alpha",
    "/home/termius/nomos-dashboard",
    "/home/termius/rgwa",
    "/home/termius/nomos-picks",
    "/home/termius/nomos-pierre",
    "/home/termius/OddsHarvester",
]

DEPARTMENTS = ["research", "engineering", "evolution", "product", "business", "evaluation", "infra", "finance"]

def collect_metrics():
    """Collect latest metrics from all repos and departments."""
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "forge_version": "v19",
        "repos": {},
        "summary": {
            "total_repos": 0,
            "total_departments": 0,
            "active_departments": 0,
            "total_iterations": 0,
        },
    }

    for repo_path in REPOS:
        repo_name = os.path.basename(repo_path)
        repo_data = {"departments": {}, "status": "MISSING"}

        if not os.path.isdir(repo_path):
            report["repos"][repo_name] = repo_data
            continue

        report["summary"]["total_repos"] += 1
        guardian_file = Path(repo_path) / "data" / "departments" / "guardian-report.json"

        if guardian_file.exists():
            repo_data["status"] = "FORGED"
        else:
            repo_data["status"] = "UNFORGED"

        for dept in DEPARTMENTS:
            dept_data = {"status": "NONE", "iterations": 0, "latest_metric": None}

            # Check council state
            council_file = Path(repo_path) / "data" / "departments" / f"council-{dept}.json"
            if council_file.exists():
                try:
                    with open(council_file) as f:
                        state = json.load(f)
                    dept_data["iterations"] = state.get("iteration", 0)
                    dept_data["last_run"] = state.get("last_run")
                    dept_data["status"] = "ACTIVE" if state.get("iteration", 0) > 0 else "READY"
                    report["summary"]["total_iterations"] += state.get("iteration", 0)
                except (json.JSONDecodeError, KeyError):
                    dept_data["status"] = "ERROR"

            # Check metrics
            metrics_file = Path(repo_path) / "data" / "departments" / dept / "metrics.jsonl"
            if metrics_file.exists():
                try:
                    lines = metrics_file.read_text().strip().split("\n")
                    if lines and lines[-1]:
                        dept_data["latest_metric"] = json.loads(lines[-1])
                        dept_data["metrics_count"] = len(lines)
                except (json.JSONDecodeError, IndexError):
                    pass

            repo_data["departments"][dept] = dept_data
            report["summary"]["total_departments"] += 1
            if dept_data["status"] == "ACTIVE":
                report["summary"]["active_departments"] += 1

        report["repos"][repo_name] = repo_data

    return report

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Forge v19 — Cross-repo metrics")
    parser.add_argument("--output", default="/home/termius/mon-ipad/data/forge-metrics.json")
    args = parser.parse_args()

    report = collect_metrics()

    # Save
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    s = report["summary"]
    print(f"Forge v19 Metrics Report — {report['ts']}")
    print(f"  Repos: {s['total_repos']} | Departments: {s['total_departments']} | Active: {s['active_departments']} | Iterations: {s['total_iterations']}")
    print()

    for repo_name, repo_data in report["repos"].items():
        status = repo_data["status"]
        active = sum(1 for d in repo_data.get("departments", {}).values() if d.get("status") == "ACTIVE")
        total = len(repo_data.get("departments", {}))
        print(f"  {repo_name:25s} [{status:8s}] {active}/{total} active depts")

    print(f"\nSaved to: {args.output}")

if __name__ == "__main__":
    main()
