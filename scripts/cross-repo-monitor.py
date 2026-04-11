#!/usr/bin/env python3
"""
cross-repo-monitor.py — Nomos42 Cross-Repo Health Monitor

Collects health data from all repos, HF Spaces, GPU platforms, crons,
Telegram bots, and outputs a JSON report + human-readable summary.

Usage:
    python3 scripts/cross-repo-monitor.py
    python3 scripts/cross-repo-monitor.py --json-only
    python3 scripts/cross-repo-monitor.py --output /tmp/health.json
    python3 scripts/cross-repo-monitor.py --spaces-only
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPOS = {
    "mon-ipad": {"path": "~/mon-ipad", "type": "brain"},
    "nomos-nba-agent": {"path": "~/nomos-nba-agent", "type": "engine"},
    "nomos-political-alpha": {"path": "~/nomos-political-alpha", "type": "engine"},
    "rgwa": {"path": "~/rgwa", "type": "creative"},
    "nomos-dashboard": {"path": "~/nomos-dashboard", "type": "dashboard"},
}

HF_SPACES = {
    "S10": "https://nomos42-nba-quant.hf.space",
    "S11": "https://nomos42-nba-quant-2.hf.space",
    "S12": "https://nomos42-nba-evo-3.hf.space",
    "S13": "https://nomos42-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
    "S16": "https://lbjlincoln26-nba-evo-s16.hf.space",
    "S17": "https://lbjlincoln26-nba-evo-s17.hf.space",
}

# Alternative URLs (old account-based subdomain pattern for keepalive compatibility)
HF_SPACES_ALT = {
    "S10": "https://lbjlincoln-nomos-nba-quant.hf.space",
    "S11": "https://lbjlincoln-nomos-nba-quant-2.hf.space",
    "S12": "https://lbjlincoln26-nba-evo-3.hf.space",
    "S13": "https://lbjlincoln26-nba-evo-4.hf.space",
    "S14": "https://nomos42-nba-evo-5.hf.space",
    "S15": "https://nomos42-nba-evo-6.hf.space",
}

GPU_PLATFORMS = {
    "kaggle": {
        "check_cmd": "kaggle kernels status alexismoret6/nba-quant-gpu-evolution-v2",
        "kernel": "alexismoret6/nba-quant-gpu-evolution-v2",
    },
    "colab": {
        "check": "drive_state",
        "state_paths": [
            "~/nomos-nba-agent/colab/nba_gpu_v2_state.json",
            "/content/drive/MyDrive/nba_gpu_state.json",
        ],
    },
}

# Telegram bot process patterns
BOT_PROCESSES = {
    "nomos42_brain": {
        "pattern": "nomos42_brain",
        "repo": "mon-ipad",
        "script": "scripts/telegram/nomos42_brain.py",
    },
    "rgwa_bot": {
        "pattern": "rgwa.*bot|telegram.*rgwa",
        "repo": "rgwa",
        "script": "scripts/telegram/",
    },
}

# Expected cron patterns (regex) and their project tags
EXPECTED_CRONS = {
    "keepalive-spaces": {"pattern": r"keepalive-spaces", "project": "nba-quant"},
    "nba-daily-odds": {"pattern": r"nba-daily-odds", "project": "nba-quant"},
    "autonomous-cycle": {"pattern": r"autonomous-cycle", "project": "brain"},
    "cross-repo-optimize": {"pattern": r"cross-repo-optimize", "project": "brain"},
    "political-fast": {"pattern": r"fetch_political_data.*--fast", "project": "political-alpha"},
    "political-full": {"pattern": r"fetch_political_data.*--all", "project": "political-alpha"},
    "political-insider": {"pattern": r"fetch_political_data.*--insider", "project": "political-alpha"},
    "political-prices": {"pattern": r"fetch_political_data.*--prices", "project": "political-alpha"},
}

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "cross-repo-health.json"
HTTP_TIMEOUT = 8  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run a shell command, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def http_get(url: str, timeout: int = HTTP_TIMEOUT) -> tuple[int, Any]:
    """
    HTTP GET. Returns (status_code, parsed_json_or_None).
    Returns (0, None) on connection error.
    """
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Nomos42-HealthMonitor/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, {"raw": body[:500]}
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path))


def dir_size_mb(path: Path) -> float:
    """Return total size of a directory in MB."""
    if not path.exists():
        return 0.0
    rc, out, _ = run(f"du -sm {path} 2>/dev/null | cut -f1", timeout=10)
    try:
        return float(out.strip()) if out.strip() else 0.0
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Repo collectors
# ---------------------------------------------------------------------------

def collect_repo(name: str, config: dict) -> dict:
    """Collect git and filesystem metrics for one repo."""
    path = expand(config["path"])
    result: dict = {
        "type": config["type"],
        "path": str(path),
        "exists": path.exists(),
        "last_commit_date": None,
        "last_commit_hash": None,
        "last_commit_msg": None,
        "uncommitted_changes": 0,
        "uncommitted_files": [],
        "data_size_mb": 0.0,
        "error": None,
    }

    if not path.exists():
        result["error"] = "directory not found"
        return result

    git_prefix = f"git -C {path}"

    # Last commit
    rc, out, err = run(f"{git_prefix} log -1 --format='%H|%ci|%s' 2>/dev/null")
    if rc == 0 and out:
        parts = out.split("|", 2)
        if len(parts) == 3:
            result["last_commit_hash"] = parts[0][:8]
            result["last_commit_date"] = parts[1].strip()
            result["last_commit_msg"] = parts[2].strip()

    # Uncommitted changes
    rc, out, err = run(f"{git_prefix} status --porcelain 2>/dev/null")
    if rc == 0:
        lines = [l for l in out.splitlines() if l.strip()]
        result["uncommitted_changes"] = len(lines)
        result["uncommitted_files"] = [l[3:] for l in lines[:10]]  # max 10

    # Data directory size
    data_dir = path / "data"
    if data_dir.exists():
        result["data_size_mb"] = dir_size_mb(data_dir)

    return result


# ---------------------------------------------------------------------------
# Cron collectors
# ---------------------------------------------------------------------------

def collect_crons() -> dict:
    """Parse crontab -l and categorize all jobs."""
    rc, out, err = run("crontab -l 2>/dev/null")
    raw_lines = out.splitlines() if rc == 0 else []

    jobs = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Categorize
        project = "unknown"
        label = "unknown"
        for key, spec in EXPECTED_CRONS.items():
            if re.search(spec["pattern"], stripped):
                project = spec["project"]
                label = key
                break
        if project == "unknown":
            # Heuristic fallback
            if "political" in stripped:
                project = "political-alpha"
            elif "nba" in stripped:
                project = "nba-quant"
            elif "mon-ipad" in stripped:
                project = "brain"
            elif "rgwa" in stripped:
                project = "rgwa"

        jobs.append({"schedule": _extract_schedule(stripped), "command": stripped, "project": project, "label": label})

    # Check which expected crons are present
    present = set()
    for job in jobs:
        if job["label"] != "unknown":
            present.add(job["label"])

    missing = [k for k in EXPECTED_CRONS if k not in present]

    return {
        "total": len(jobs),
        "jobs": jobs,
        "expected_present": sorted(present),
        "missing": missing,
        "by_project": _group_by(jobs, "project"),
    }


def _extract_schedule(line: str) -> str:
    """Extract cron schedule fields (first 5 tokens)."""
    parts = line.split()
    if len(parts) >= 5:
        return " ".join(parts[:5])
    return line


def _group_by(items: list, key: str) -> dict:
    out: dict = {}
    for item in items:
        k = item.get(key, "unknown")
        out.setdefault(k, 0)
        out[k] += 1
    return out


# ---------------------------------------------------------------------------
# Process / bot collectors
# ---------------------------------------------------------------------------

def collect_bots() -> dict:
    """Check if Telegram bots are running."""
    result = {}
    for bot_name, spec in BOT_PROCESSES.items():
        pattern = spec["pattern"]
        rc, out, _ = run(f"pgrep -fa '{pattern}' 2>/dev/null")
        running = rc == 0 and bool(out.strip())
        pids = []
        if running:
            for line in out.splitlines():
                parts = line.split(None, 1)
                if parts:
                    pids.append(parts[0])
        result[bot_name] = {
            "running": running,
            "pids": pids,
            "repo": spec["repo"],
        }

    return result


def collect_processes() -> dict:
    """Check for key running processes (data server, fetchers)."""
    checks = {
        "nba_data_server": "nba-data-server",
        "nba_daily_odds": "nba-daily-odds",
        "autonomous_cycle": "autonomous-cycle",
        "political_fetcher": "fetch_political_data",
        "keepalive": "keepalive-spaces",
    }
    result = {}
    for name, pattern in checks.items():
        rc, out, _ = run(f"pgrep -fa '{pattern}' 2>/dev/null")
        result[name] = rc == 0 and bool(out.strip())
    return result


# ---------------------------------------------------------------------------
# HF Space collectors
# ---------------------------------------------------------------------------

def probe_space(space_id: str, primary_url: str, alt_url: str | None = None) -> dict:
    """
    Hit /api/status on a HF Space. Fall back to alt_url if primary 404s or fails.
    """
    result: dict = {
        "space_id": space_id,
        "url": primary_url,
        "status": "unknown",
        "http_code": 0,
        "generation": None,
        "best_brier": None,
        "model_type": None,
        "stagnation_cycles": None,
        "cycle": None,
        "mutation_rate": None,
        "pareto_front_size": None,
        "role": None,
        "last_update": None,
        "error": None,
    }

    urls_to_try = [primary_url]
    if alt_url and alt_url != primary_url:
        urls_to_try.append(alt_url)

    for url in urls_to_try:
        code, data = http_get(f"{url}/api/status")
        result["http_code"] = code
        result["url"] = url

        if code == 200 and isinstance(data, dict):
            result["status"] = "running"
            # Parse common fields from the /api/status response
            result["generation"] = _get(data, ["generation", "gen"])
            result["best_brier"] = _get(data, ["best_brier", "brier"])
            result["model_type"] = _get(data, ["best_model_type", "model_type"])
            result["stagnation_cycles"] = _get(data, ["stagnation_cycles", "stagnation"])
            result["cycle"] = _get(data, ["cycle"])
            result["mutation_rate"] = _get(data, ["mutation_rate"])
            result["pareto_front_size"] = _get(data, ["pareto_front_size"])
            result["role"] = _get(data, ["role"])
            result["last_update"] = _get(data, ["last_update", "timestamp"])
            result["raw_keys"] = list(data.keys())[:20]
            return result
        elif code in (503, 503):
            result["status"] = "sleeping"
            result["error"] = f"HTTP {code} — space sleeping"
            return result
        elif code == 0:
            result["status"] = "offline"
            result["error"] = "connection failed"
            # try alt
            continue
        else:
            result["status"] = "error"
            result["error"] = f"HTTP {code}"
            # try alt
            continue

    return result


def _get(d: dict, keys: list) -> Any:
    """Try multiple keys on a dict, return first match or None."""
    for k in keys:
        if k in d:
            return d[k]
    return None


def collect_hf_spaces() -> dict:
    """Probe all 6 HF Spaces."""
    spaces = {}
    briers = []

    for space_id, url in HF_SPACES.items():
        alt = HF_SPACES_ALT.get(space_id)
        data = probe_space(space_id, url, alt)
        spaces[space_id] = data
        if isinstance(data.get("best_brier"), (int, float)) and data["best_brier"] < 1.0:
            briers.append(data["best_brier"])

    fleet_stats: dict = {
        "running_count": sum(1 for s in spaces.values() if s["status"] == "running"),
        "sleeping_count": sum(1 for s in spaces.values() if s["status"] == "sleeping"),
        "offline_count": sum(1 for s in spaces.values() if s["status"] in ("offline", "error", "unknown")),
        "fleet_best_brier": min(briers) if briers else None,
        "fleet_avg_brier": round(sum(briers) / len(briers), 5) if briers else None,
        "fleet_worst_brier": max(briers) if briers else None,
        "spaces_with_brier": len(briers),
    }

    return {"spaces": spaces, "fleet": fleet_stats}


# ---------------------------------------------------------------------------
# GPU platform collectors
# ---------------------------------------------------------------------------

def collect_gpu_platforms() -> dict:
    """Check GPU platform statuses."""
    result = {}

    # Kaggle
    kaggle_cfg = GPU_PLATFORMS["kaggle"]
    rc, out, err = run(f"{kaggle_cfg['check_cmd']} 2>/dev/null", timeout=20)
    kaggle_status = "unknown"
    kaggle_detail = None
    if rc == 0 and out:
        # Parse "status: running" from kaggle CLI output
        for line in out.lower().splitlines():
            if "status" in line:
                if "running" in line:
                    kaggle_status = "running"
                elif "complete" in line:
                    kaggle_status = "complete"
                elif "failed" in line or "error" in line:
                    kaggle_status = "failed"
                elif "queued" in line:
                    kaggle_status = "queued"
                break
        kaggle_detail = out[:300]
    elif "command not found" in err or "No module" in err:
        kaggle_status = "cli_not_installed"
        kaggle_detail = err[:200]
    elif rc == 1 and "not found" in out.lower():
        kaggle_status = "kernel_not_found"
        kaggle_detail = out[:200]
    else:
        kaggle_status = "error"
        kaggle_detail = (err or out)[:200]

    result["kaggle"] = {
        "status": kaggle_status,
        "kernel": kaggle_cfg["kernel"],
        "detail": kaggle_detail,
    }

    # Colab — check Drive state file if accessible locally
    colab_status = "not_running"
    colab_state = None
    colab_detail = None
    for state_path_str in GPU_PLATFORMS["colab"]["state_paths"]:
        state_path = expand(state_path_str)
        if state_path.exists():
            try:
                colab_state = json.loads(state_path.read_text())
                colab_status = colab_state.get("status", "unknown")
                colab_detail = f"state file found: {state_path}"
                break
            except Exception as e:
                colab_detail = f"state file parse error: {e}"
                break
    else:
        colab_detail = "no Drive state file found locally (normal if Colab not mounted)"

    result["colab"] = {
        "status": colab_status,
        "state": colab_state,
        "detail": colab_detail,
    }

    return result


# ---------------------------------------------------------------------------
# Alert generator
# ---------------------------------------------------------------------------

def generate_alerts(repos: dict, spaces_data: dict, crons: dict, bots: dict) -> list[str]:
    alerts = []

    # Repo alerts
    for name, repo in repos.items():
        if not repo["exists"]:
            alerts.append(f"REPO MISSING: {name} not found at {repo['path']}")
        elif repo.get("uncommitted_changes", 0) > 10:
            alerts.append(f"REPO DIRTY: {name} has {repo['uncommitted_changes']} uncommitted changes")

    # Space alerts
    for sid, space in spaces_data["spaces"].items():
        if space["status"] in ("offline", "error"):
            alerts.append(f"SPACE {sid} OFFLINE: {space.get('error', 'unknown error')}")
        elif space["status"] == "sleeping":
            alerts.append(f"SPACE {sid} SLEEPING — needs keepalive")
        elif space["status"] == "running":
            sc = space.get("stagnation_cycles")
            if sc and sc > 300:
                alerts.append(f"SPACE {sid} STAGNATING: {sc} cycles without improvement")
            brier = space.get("best_brier")
            if brier and brier >= 1.0:
                alerts.append(f"SPACE {sid} COLD START — no valid brier yet")

    # Cron alerts
    if crons.get("missing"):
        for missing in crons["missing"]:
            alerts.append(f"CRON MISSING: {missing}")

    # Bot alerts
    for bot, info in bots.items():
        if not info["running"]:
            alerts.append(f"BOT NOT RUNNING: {bot} ({info['repo']})")

    return alerts


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def build_summary(repos: dict, spaces_data: dict, crons: dict, bots: dict, gpu: dict) -> dict:
    active_repos = sum(1 for r in repos.values() if r["exists"])
    fleet = spaces_data["fleet"]
    bots_running_count = sum(1 for b in bots.values() if b["running"])

    return {
        "total_repos": len(repos),
        "active_repos": active_repos,
        "running_spaces": fleet["running_count"],
        "sleeping_spaces": fleet["sleeping_count"],
        "offline_spaces": fleet["offline_count"],
        "fleet_best_brier": fleet["fleet_best_brier"],
        "fleet_avg_brier": fleet["fleet_avg_brier"],
        "total_crons": crons["total"],
        "missing_crons": len(crons.get("missing", [])),
        "bots_running": bots_running_count,
        "total_bots": len(bots),
        "gpu_kaggle_status": gpu.get("kaggle", {}).get("status", "unknown"),
        "gpu_colab_status": gpu.get("colab", {}).get("status", "unknown"),
    }


# ---------------------------------------------------------------------------
# Human-readable printer
# ---------------------------------------------------------------------------

def print_report(report: dict) -> None:
    ts = report["timestamp"]
    summary = report["summary"]
    alerts = report["alerts"]

    W = 70
    print("=" * W)
    print(f"  NOMOS42 CROSS-REPO HEALTH REPORT — {ts}")
    print("=" * W)

    # Summary
    print("\n[SUMMARY]")
    print(f"  Repos      : {summary['active_repos']}/{summary['total_repos']} active")
    print(f"  HF Spaces  : {summary['running_spaces']} running / "
          f"{summary['sleeping_spaces']} sleeping / "
          f"{summary['offline_spaces']} offline")
    if summary.get("fleet_best_brier"):
        print(f"  Fleet Best : Brier {summary['fleet_best_brier']:.5f} "
              f"(avg {summary.get('fleet_avg_brier', '?')})")
    print(f"  Crons      : {summary['total_crons']} total "
          f"({summary['missing_crons']} missing)")
    print(f"  Bots       : {summary['bots_running']}/{summary['total_bots']} running")
    print(f"  Kaggle     : {summary['gpu_kaggle_status']}")
    print(f"  Colab      : {summary['gpu_colab_status']}")

    # Alerts
    print("\n[ALERTS]")
    if alerts:
        for a in alerts:
            print(f"  ! {a}")
    else:
        print("  No alerts — all systems nominal")

    # Repos
    print("\n[REPOS]")
    for name, repo in report["repos"].items():
        status = "OK" if repo["exists"] else "MISSING"
        commit = repo.get("last_commit_date", "?")
        changes = repo.get("uncommitted_changes", 0)
        msg = (repo.get("last_commit_msg") or "")[:50]
        data_mb = repo.get("data_size_mb", 0)
        print(f"  {name:<28} [{status}]  {commit}  +{changes} uncommitted  "
              f"data={data_mb:.1f}MB")
        if msg:
            print(f"    -> {msg}")

    # HF Spaces
    print("\n[HF SPACES]")
    for sid, space in report["hf_spaces"]["spaces"].items():
        status = space["status"].upper()
        gen = space.get("generation") or "-"
        brier = f"{space['best_brier']:.5f}" if isinstance(space.get("best_brier"), float) else "-"
        model = space.get("model_type") or "-"
        stag = space.get("stagnation_cycles") or 0
        role = (space.get("role") or "-")
        print(f"  {sid}  [{status:<10}]  gen={gen:<6}  brier={brier}  "
              f"model={model:<15}  stag={stag:<5}  role={role}")

    # Crons
    print("\n[CRON JOBS]")
    print(f"  Total: {report['crons']['total']}")
    by_project = report["crons"].get("by_project", {})
    for proj, count in sorted(by_project.items()):
        print(f"    {proj:<28} {count} job(s)")
    if report["crons"].get("missing"):
        print(f"  Missing: {', '.join(report['crons']['missing'])}")

    # Bots
    print("\n[TELEGRAM BOTS]")
    for bot, info in report["bots"].items():
        status = "RUNNING" if info["running"] else "DOWN"
        pids = ",".join(info.get("pids", [])) or "-"
        print(f"  {bot:<28} [{status}]  pids={pids}  repo={info['repo']}")

    # GPU
    print("\n[GPU PLATFORMS]")
    for platform, info in report["gpu_platforms"].items():
        status = info.get("status", "unknown").upper()
        detail = (info.get("detail") or "")[:60]
        print(f"  {platform:<12}  [{status:<18}]  {detail}")

    print("\n" + "=" * W)
    print(f"  Report saved: {OUTPUT_PATH}")
    print("=" * W)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Nomos42 Cross-Repo Health Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/cross-repo-monitor.py
  python3 scripts/cross-repo-monitor.py --json-only
  python3 scripts/cross-repo-monitor.py --spaces-only
  python3 scripts/cross-repo-monitor.py --output /tmp/health.json
        """,
    )
    parser.add_argument("--json-only", action="store_true", help="Print JSON only, no human summary")
    parser.add_argument("--spaces-only", action="store_true", help="Only probe HF Spaces")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Output JSON path")
    parser.add_argument("--no-save", action="store_true", help="Do not write output file")
    parser.add_argument("--timeout", type=int, default=HTTP_TIMEOUT, help="HTTP timeout per request (s)")
    args = parser.parse_args()

    # Override module-level timeout if requested
    if args.timeout != HTTP_TIMEOUT:
        sys.modules[__name__].HTTP_TIMEOUT = args.timeout

    ts = now_utc()
    print(f"[{ts}] Starting cross-repo health monitor...", file=sys.stderr)

    if args.spaces_only:
        spaces_data = collect_hf_spaces()
        print(json.dumps(spaces_data, indent=2))
        return

    # --- Collect all data ---
    print("[...] Collecting repo metrics...", file=sys.stderr)
    repos = {name: collect_repo(name, cfg) for name, cfg in REPOS.items()}

    print("[...] Probing HF Spaces (6 endpoints)...", file=sys.stderr)
    spaces_data = collect_hf_spaces()

    print("[...] Checking GPU platforms...", file=sys.stderr)
    gpu = collect_gpu_platforms()

    print("[...] Parsing crontab...", file=sys.stderr)
    crons = collect_crons()

    print("[...] Checking Telegram bots...", file=sys.stderr)
    bots = collect_bots()

    print("[...] Checking key processes...", file=sys.stderr)
    processes = collect_processes()

    # --- Build report ---
    alerts = generate_alerts(repos, spaces_data, crons, bots)
    summary = build_summary(repos, spaces_data, crons, bots, gpu)

    report = {
        "timestamp": ts,
        "repos": repos,
        "hf_spaces": spaces_data,
        "gpu_platforms": gpu,
        "crons": crons,
        "bots": bots,
        "processes": processes,
        "alerts": alerts,
        "summary": summary,
    }

    # --- Save ---
    if not args.no_save:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        print(f"[OK] Saved: {out_path}", file=sys.stderr)

    # --- Output ---
    if args.json_only:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
        if not args.json_only:
            # Also print compact JSON at the end for piping
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
