#!/usr/bin/env python3
"""
aggregate-health.py -- Nomos42 Unified Cross-Repo Health Aggregator

Reads karpathy outputs from all departments (local + satellite repos),
queries HF Space /api/status endpoints (S10-S15, P1-P4), reads data
server status, and produces a unified cross-repo-health.json.

Usage:
    python3 /home/lahargnedebartoli/mon-ipad/scripts/sync/aggregate-health.py
    python3 /home/lahargnedebartoli/mon-ipad/scripts/sync/aggregate-health.py --output /tmp/health.json
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BRAIN = Path("/home/lahargnedebartoli/mon-ipad")
OUTPUT_DEFAULT = BRAIN / "data" / "cross-repo-health.json"

REPOS = {
    "mon-ipad": {
        "path": Path("/home/lahargnedebartoli/mon-ipad"),
        "type": "brain",
        "departments": [
            "research", "engineering", "evolution", "betting",
            "evaluation", "infra", "political", "creative", "trading_floor",
        ],
    },
    "nomos-nba-agent": {
        "path": Path("/home/lahargnedebartoli/nomos-nba-agent"),
        "type": "engine",
        "departments": ["prediction"],
    },
    "nomos-political-alpha": {
        "path": Path("/home/lahargnedebartoli/nomos-political-alpha"),
        "type": "engine",
        "departments": ["signals"],
    },
    "rgwa": {
        "path": Path("/home/lahargnedebartoli/rgwa"),
        "type": "creative",
        "departments": ["creative"],
    },
    "nomos-dashboard": {
        "path": Path("/home/lahargnedebartoli/nomos-dashboard"),
        "type": "dashboard",
        "departments": [],
    },
}

HF_NBA_SPACES = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
}

HF_POLITICAL_SPACES = {
    "P1": "https://nomos42-political-alpha.hf.space",
    "P2": "https://nomos42-political-alpha-2.hf.space",
    # P3/P4 removed 2026-04-03 — spaces never existed on HF, caused phantom 404s
}

DATA_SERVER_URL = "http://localhost:8080/nba-agent/quant-summary.json"

# Thresholds for health scoring
HEALTH_WEIGHTS = {
    "repos_active": 15,       # All repos accessible
    "departments_running": 20, # Departments producing karpathy output
    "hf_nba_fleet": 25,       # NBA HF spaces running
    "hf_political_fleet": 10, # Political HF spaces running
    "data_server": 10,        # Local data server up
    "brier_progress": 10,     # Fleet best Brier improving
    "no_blockers": 10,        # No critical blockers
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_url_json(url: str, timeout: int = 10) -> dict | None:
    """Fetch JSON from URL, return None on failure."""
    try:
        req = urllib.request.Request(
            f"{url}/api/status",
            headers={"User-Agent": "Nomos42-Sync/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            OSError, TimeoutError):
        pass
    return None


def fetch_space_status(space_id: str, url: str) -> dict:
    """Fetch HF Space status, return structured result."""
    result = {
        "space_id": space_id,
        "url": url,
        "status": "unknown",
        "http_code": None,
        "generation": None,
        "best_brier": None,
        "model_type": None,
        "error": None,
    }

    try:
        req = urllib.request.Request(
            f"{url}/api/status",
            headers={"User-Agent": "Nomos42-Sync/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result["http_code"] = resp.status
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                result["status"] = data.get("status", "running")
                result["generation"] = data.get("generation")
                result["best_brier"] = data.get("best_brier")
                result["model_type"] = data.get("best_model_type")
                result["cycle"] = data.get("cycle")
                result["mutation_rate"] = data.get("mutation_rate")
                result["stagnation"] = data.get("stagnation", 0)
                result["last_update"] = data.get("last_update")
    except urllib.error.HTTPError as e:
        result["status"] = f"error_{e.code}"
        result["http_code"] = e.code
        result["error"] = str(e)
    except urllib.error.URLError as e:
        result["status"] = "offline"
        result["error"] = str(e.reason)
    except (OSError, TimeoutError) as e:
        result["status"] = "timeout"
        result["error"] = str(e)
    except json.JSONDecodeError as e:
        result["status"] = "bad_response"
        result["error"] = f"Invalid JSON: {e}"

    return result


def get_repo_status(name: str, config: dict) -> dict:
    """Get git status for a repo."""
    repo_path = config["path"]
    result = {
        "name": name,
        "type": config["type"],
        "path": str(repo_path),
        "status": "error",
        "exists": False,
        "last_commit_date": None,
        "last_commit_hash": None,
        "last_commit_msg": None,
        "uncommitted_changes": 0,
        "error": None,
    }

    if not repo_path.exists():
        result["error"] = "Directory does not exist"
        return result

    result["exists"] = True

    try:
        # Last commit info
        log_out = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--format=%H|%ai|%s"],
            capture_output=True, text=True, timeout=10,
        )
        if log_out.returncode == 0 and log_out.stdout.strip():
            parts = log_out.stdout.strip().split("|", 2)
            if len(parts) == 3:
                result["last_commit_hash"] = parts[0][:8]
                result["last_commit_date"] = parts[1]
                result["last_commit_msg"] = parts[2]

        # Uncommitted changes count
        status_out = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        if status_out.returncode == 0:
            changes = [l for l in status_out.stdout.strip().split("\n") if l.strip()]
            result["uncommitted_changes"] = len(changes)

        result["status"] = "active"

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        result["error"] = str(e)

    return result


def read_karpathy_output(repo_path: Path, dept: str) -> dict | None:
    """Read karpathy-output.json from a department directory."""
    kfile = repo_path / "data" / "departments" / dept / "karpathy-output.json"
    if not kfile.exists():
        return None
    try:
        with open(kfile) as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def get_data_server_status() -> dict:
    """Check if the local NBA data server is running."""
    result = {
        "status": "offline",
        "url": DATA_SERVER_URL,
        "error": None,
    }
    try:
        req = urllib.request.Request(DATA_SERVER_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                result["status"] = "running"
                try:
                    data = json.loads(resp.read().decode())
                    result["games"] = data.get("games")
                    result["last_update"] = data.get("last_update")
                except (json.JSONDecodeError, KeyError):
                    pass
    except Exception as e:
        result["error"] = str(e)
    return result


def compute_health_score(
    repos: dict,
    departments: dict,
    nba_fleet: dict,
    political_fleet: dict,
    data_server: dict,
    blockers: list,
) -> int:
    """Compute overall system health score 0-100."""
    score = 0

    # Repos active (15 pts)
    active_repos = sum(1 for r in repos.values() if r.get("status") == "active")
    total_repos = len(repos)
    if total_repos > 0:
        score += int(HEALTH_WEIGHTS["repos_active"] * active_repos / total_repos)

    # Departments running (20 pts)
    depts_with_output = sum(1 for d in departments.values() if d is not None)
    total_depts = len(departments) if departments else 1
    score += int(HEALTH_WEIGHTS["departments_running"] * depts_with_output / total_depts)

    # NBA HF fleet (25 pts)
    nba_running = nba_fleet.get("running_count", 0)
    nba_total = nba_fleet.get("total", 6)
    if nba_total > 0:
        score += int(HEALTH_WEIGHTS["hf_nba_fleet"] * nba_running / nba_total)

    # Political HF fleet (10 pts)
    pol_running = political_fleet.get("running_count", 0)
    pol_total = political_fleet.get("total", 4)
    if pol_total > 0:
        score += int(HEALTH_WEIGHTS["hf_political_fleet"] * pol_running / pol_total)

    # Data server (10 pts)
    if data_server.get("status") == "running":
        score += HEALTH_WEIGHTS["data_server"]

    # Brier progress (10 pts): award if fleet best < 0.225
    fleet_best = nba_fleet.get("best_brier")
    if fleet_best is not None and fleet_best < 0.225:
        score += HEALTH_WEIGHTS["brier_progress"]
    elif fleet_best is not None and fleet_best < 0.230:
        score += HEALTH_WEIGHTS["brier_progress"] // 2

    # No blockers (10 pts)
    critical_blockers = [b for b in blockers if b.get("severity") == "CRITICAL"]
    if len(critical_blockers) == 0:
        score += HEALTH_WEIGHTS["no_blockers"]
    elif len(critical_blockers) <= 2:
        score += HEALTH_WEIGHTS["no_blockers"] // 2

    return min(score, 100)


def identify_blockers(repos: dict, departments: dict, nba_spaces: dict, political_spaces: dict) -> list:
    """Identify blockers and produce recommendations."""
    blockers = []

    # Check for offline repos
    for name, info in repos.items():
        if info.get("status") != "active":
            blockers.append({
                "severity": "CRITICAL",
                "source": f"repo/{name}",
                "issue": f"Repo {name} is not accessible: {info.get('error', 'unknown')}",
                "recommendation": f"Check {info.get('path')} exists and is a valid git repo",
            })
        elif info.get("uncommitted_changes", 0) > 50:
            blockers.append({
                "severity": "HIGH",
                "source": f"repo/{name}",
                "issue": f"Repo {name} has {info['uncommitted_changes']} uncommitted changes",
                "recommendation": f"Commit or stash changes in {name}",
            })

    # Check for offline NBA spaces
    for sid, sdata in nba_spaces.items():
        if sdata.get("status") not in ("running", "unknown"):
            blockers.append({
                "severity": "HIGH",
                "source": f"hf/{sid}",
                "issue": f"HF Space {sid} is {sdata.get('status')}: {sdata.get('error', '')}",
                "recommendation": f"Restart {sid} via HuggingFace dashboard or keepalive script",
            })
        stag = sdata.get("stagnation", 0)
        if stag and stag > 15:
            blockers.append({
                "severity": "HIGH",
                "source": f"hf/{sid}",
                "issue": f"HF Space {sid} stagnant for {stag} cycles",
                "recommendation": f"Send diversify command: POST {sdata['url']}/api/config",
            })

    # Check for offline political spaces
    for sid, sdata in political_spaces.items():
        if sdata.get("status") not in ("running", "unknown"):
            blockers.append({
                "severity": "MEDIUM",
                "source": f"hf/{sid}",
                "issue": f"Political space {sid} is {sdata.get('status')}",
                "recommendation": f"Restart {sid} via HuggingFace dashboard",
            })

    # Check department outputs for staleness (older than 12h)
    for dept_key, dept_data in departments.items():
        if dept_data is None:
            blockers.append({
                "severity": "LOW",
                "source": f"dept/{dept_key}",
                "issue": f"Department {dept_key} has no karpathy output",
                "recommendation": f"Run karpathy loop for {dept_key}",
            })

    return blockers


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Nomos42 Cross-Repo Health Aggregator")
    parser.add_argument("--output", "-o", default=str(OUTPUT_DEFAULT),
                        help="Output JSON path")
    parser.add_argument("--skip-hf", action="store_true",
                        help="Skip HF Space status checks (faster)")
    parser.add_argument("--json-only", action="store_true",
                        help="Output JSON only, no human summary")
    args = parser.parse_args()

    timestamp = now_utc()
    print(f"[aggregate-health] Starting at {timestamp}")

    # -----------------------------------------------------------------------
    # 1. Repo status
    # -----------------------------------------------------------------------
    print("[aggregate-health] Checking repo status...")
    repo_status = {}
    for name, config in REPOS.items():
        repo_status[name] = get_repo_status(name, config)

    # -----------------------------------------------------------------------
    # 2. Department karpathy outputs
    # -----------------------------------------------------------------------
    print("[aggregate-health] Reading department karpathy outputs...")
    department_data = {}

    for repo_name, config in REPOS.items():
        for dept in config["departments"]:
            key = f"{repo_name}/{dept}"
            dept_output = read_karpathy_output(config["path"], dept)
            if dept_output is not None:
                department_data[key] = {
                    "repo": repo_name,
                    "department": dept,
                    "timestamp": dept_output.get("timestamp"),
                    "iteration": dept_output.get("iteration"),
                    "status": dept_output.get("status", "unknown"),
                    "improved": dept_output.get("improved", False),
                    "best_brier": dept_output.get("best_brier"),
                    "fleet_avg_brier": dept_output.get("fleet_avg_brier"),
                    "best_island": dept_output.get("best_island"),
                    "recommendations_count": len(dept_output.get("recommendations", [])),
                }
            else:
                department_data[key] = None

    # -----------------------------------------------------------------------
    # 3. HF Space fleet status
    # -----------------------------------------------------------------------
    nba_spaces = {}
    political_spaces = {}
    nba_fleet_summary = {"total": 6, "running_count": 0, "best_brier": None}
    political_fleet_summary = {"total": 2, "running_count": 0, "best_brier": None}

    if not args.skip_hf:
        print("[aggregate-health] Querying HF Spaces (NBA)...")
        for sid, url in HF_NBA_SPACES.items():
            sdata = fetch_space_status(sid, url)
            nba_spaces[sid] = sdata
            if sdata["status"] in ("running", "evolving"):
                nba_fleet_summary["running_count"] += 1
            brier = sdata.get("best_brier")
            if brier is not None:
                if nba_fleet_summary["best_brier"] is None or brier < nba_fleet_summary["best_brier"]:
                    nba_fleet_summary["best_brier"] = brier
                    nba_fleet_summary["best_island"] = sid
                    nba_fleet_summary["best_model"] = sdata.get("model_type")

        print("[aggregate-health] Querying HF Spaces (Political)...")
        for sid, url in HF_POLITICAL_SPACES.items():
            sdata = fetch_space_status(sid, url)
            political_spaces[sid] = sdata
            if sdata["status"] in ("running", "evolving"):
                political_fleet_summary["running_count"] += 1
            brier = sdata.get("best_brier")
            if brier is not None:
                if political_fleet_summary["best_brier"] is None or brier < political_fleet_summary["best_brier"]:
                    political_fleet_summary["best_brier"] = brier

        # Compute fleet averages
        nba_briers = [s["best_brier"] for s in nba_spaces.values() if s.get("best_brier")]
        if nba_briers:
            nba_fleet_summary["avg_brier"] = round(sum(nba_briers) / len(nba_briers), 5)
            nba_fleet_summary["worst_brier"] = max(nba_briers)
            nba_fleet_summary["spaces_with_brier"] = len(nba_briers)
    else:
        print("[aggregate-health] Skipping HF Space checks (--skip-hf)")

    # -----------------------------------------------------------------------
    # 4. Data server status
    # -----------------------------------------------------------------------
    print("[aggregate-health] Checking data server...")
    data_server = get_data_server_status()

    # -----------------------------------------------------------------------
    # 5. Blockers and recommendations
    # -----------------------------------------------------------------------
    print("[aggregate-health] Identifying blockers...")
    blockers = identify_blockers(repo_status, department_data, nba_spaces, political_spaces)

    # -----------------------------------------------------------------------
    # 6. Health score
    # -----------------------------------------------------------------------
    health_score = compute_health_score(
        repo_status, department_data,
        nba_fleet_summary, political_fleet_summary,
        data_server, blockers,
    )

    # -----------------------------------------------------------------------
    # 7. Build final report
    # -----------------------------------------------------------------------
    report = {
        "timestamp": timestamp,
        "health_score": health_score,
        "health_grade": (
            "A" if health_score >= 90 else
            "B" if health_score >= 75 else
            "C" if health_score >= 60 else
            "D" if health_score >= 40 else "F"
        ),
        "repos": repo_status,
        "departments": department_data,
        "hf_spaces": {
            "nba": {
                "spaces": nba_spaces,
                "fleet": nba_fleet_summary,
            },
            "political": {
                "spaces": political_spaces,
                "fleet": political_fleet_summary,
            },
        },
        "data_server": data_server,
        "blockers": blockers,
        "blocker_counts": {
            "critical": sum(1 for b in blockers if b["severity"] == "CRITICAL"),
            "high": sum(1 for b in blockers if b["severity"] == "HIGH"),
            "medium": sum(1 for b in blockers if b["severity"] == "MEDIUM"),
            "low": sum(1 for b in blockers if b["severity"] == "LOW"),
        },
        "summary": {
            "total_repos": len(repo_status),
            "active_repos": sum(1 for r in repo_status.values() if r.get("status") == "active"),
            "departments_reporting": sum(1 for d in department_data.values() if d is not None),
            "departments_total": len(department_data),
            "nba_spaces_running": nba_fleet_summary["running_count"],
            "nba_fleet_best_brier": nba_fleet_summary.get("best_brier"),
            "nba_fleet_avg_brier": nba_fleet_summary.get("avg_brier"),
            "political_spaces_running": political_fleet_summary["running_count"],
            "political_fleet_best_brier": political_fleet_summary.get("best_brier"),
            "data_server_status": data_server["status"],
            "total_blockers": len(blockers),
        },
    }

    # -----------------------------------------------------------------------
    # 8. Write output
    # -----------------------------------------------------------------------
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"[aggregate-health] Report written to {output_path}")

    # -----------------------------------------------------------------------
    # 9. Human summary
    # -----------------------------------------------------------------------
    if not args.json_only:
        print("")
        print("=" * 60)
        print(f"  NOMOS42 SYSTEM HEALTH: {health_score}/100 ({report['health_grade']})")
        print("=" * 60)
        print(f"  Repos:       {report['summary']['active_repos']}/{report['summary']['total_repos']} active")
        print(f"  Departments: {report['summary']['departments_reporting']}/{report['summary']['departments_total']} reporting")
        print(f"  NBA Fleet:   {nba_fleet_summary['running_count']}/6 running | Best Brier: {nba_fleet_summary.get('best_brier', 'N/A')}")
        print(f"  Political:   {political_fleet_summary['running_count']}/2 running | Best Brier: {political_fleet_summary.get('best_brier', 'N/A')}")
        print(f"  Data Server: {data_server['status']}")
        print(f"  Blockers:    {len(blockers)} total ({report['blocker_counts']['critical']} critical)")
        print("=" * 60)

        if blockers:
            print("\nTop Blockers:")
            for b in sorted(blockers, key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(x["severity"], 4))[:5]:
                print(f"  [{b['severity']}] {b['issue']}")
                print(f"    -> {b['recommendation']}")

    print(f"\n[aggregate-health] Done. Health score: {health_score}/100")
    return 0


if __name__ == "__main__":
    sys.exit(main())
