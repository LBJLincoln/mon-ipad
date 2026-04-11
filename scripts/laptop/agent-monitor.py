#!/usr/bin/env python3
"""
Nomos42 Agent Monitor — Laptop-based Monitoring Agent
=====================================================
Runs on the Acer Aspire 3 laptop via Ollama local models.

Functions:
  1. Monitor all 8 repos via git status (if accessible)
  2. Check HF Spaces health (S10-S15 + P1-P2)
  3. Fetch Bloomberg API status (from VM)
  4. Generate daily analysis using local Ollama model
  5. Output structured JSON report

Dependencies: requests (for Ollama + HTTP), otherwise stdlib only.
Ollama must be running on localhost:11434.

Usage:
  python3 agent-monitor.py                    # Full monitoring cycle
  python3 agent-monitor.py --quick            # Quick health check only
  python3 agent-monitor.py --model gemma2:2b  # Use specific model
  python3 agent-monitor.py --loop 300         # Loop every 5 minutes
  python3 agent-monitor.py --output report.json
"""

import json
import os
import sys
import time
import datetime
import argparse
import subprocess
from pathlib import Path

# Try to import requests, fall back to urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

# ── Configuration ──────────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"

# Bloomberg API (on VM, accessible via Tailscale or localhost)
BLOOMBERG_API = os.environ.get("BLOOMBERG_API", "http://127.0.0.1:8042")

# HF Space endpoints to monitor
HF_SPACES = {
    "S10": {"url": "https://nomos42-nba-quant.hf.space", "role": "NBA Exploitation"},
    "S11": {"url": "https://nomos42-nba-quant-2.hf.space", "role": "NBA Exploration"},
    "S12": {"url": "https://nomos42-nba-evo-3.hf.space", "role": "NBA ExtraTrees"},
    "S13": {"url": "https://nomos42-nba-evo-4.hf.space", "role": "NBA CatBoost"},
    "S14": {"url": "https://nomos42-nba-evo-5.hf.space", "role": "NBA LightGBM"},
    "S15": {"url": "https://nomos42-nba-evo-6.hf.space", "role": "NBA Wide Search"},
    "S16": {"url": "https://lbjlincoln26-nba-evo-s16.hf.space", "role": "NBA Gradient"},
    "S17": {"url": "https://lbjlincoln26-nba-evo-s17.hf.space", "role": "NBA Ensemble"},
    "P1": {"url": "https://lbjlincoln-political-alpha.hf.space", "role": "Political 1"},
    "P2": {"url": "https://lbjlincoln26-political-alpha-2.hf.space", "role": "Political 2"},
}

# Git repos to monitor (paths on the laptop or accessible via SSH)
REPOS = {
    "mon-ipad": {"path": os.environ.get("REPO_MON_IPAD", str(Path.home() / "mon-ipad")), "type": "flagship"},
    "nomos-nba-agent": {"path": os.environ.get("REPO_NBA_AGENT", str(Path.home() / "nomos-nba-agent")), "type": "agent"},
    "nomos-dashboard": {"path": os.environ.get("REPO_DASHBOARD", str(Path.home() / "nomos-dashboard")), "type": "dashboard"},
    "nomos-political-alpha": {"path": os.environ.get("REPO_POLITICAL", str(Path.home() / "nomos-political-alpha")), "type": "political"},
    "rgwa": {"path": os.environ.get("REPO_RGWA", str(Path.home() / "rgwa")), "type": "creative"},
    "rag-website": {"path": os.environ.get("REPO_RAG", str(Path.home() / "rag-website")), "type": "shelved"},
    "hf-brain": {"path": os.environ.get("REPO_HF_BRAIN", str(Path.home() / "hf-brain")), "type": "hf-space"},
    "hf-space": {"path": os.environ.get("REPO_HF_SPACE", str(Path.home() / "hf-space")), "type": "hf-space"},
}

OUTPUT_DIR = Path(__file__).resolve().parent / "reports"


# ── HTTP Helpers ───────────────────────────────────────────────────────────

def http_get(url: str, timeout: int = 10) -> dict | None:
    """HTTP GET, returns parsed JSON or None."""
    try:
        if HAS_REQUESTS:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        else:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Nomos42-Monitor/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
    except Exception:
        return None


def http_post(url: str, data: dict, timeout: int = 60) -> dict | None:
    """HTTP POST JSON, returns parsed JSON or None."""
    try:
        if HAS_REQUESTS:
            resp = requests.post(url, json=data, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        else:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "Nomos42-Monitor/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
    except Exception:
        return None


# ── Monitoring Functions ───────────────────────────────────────────────────

def check_ollama() -> dict:
    """Check if Ollama is running and list available models."""
    result = {"status": "offline", "models": [], "version": None}
    data = http_get(f"{OLLAMA_URL}/api/tags", timeout=5)
    if data:
        result["status"] = "online"
        result["models"] = [m.get("name", "?") for m in data.get("models", [])]

    version = http_get(f"{OLLAMA_URL}/api/version", timeout=5)
    if version:
        result["version"] = version.get("version", "?")

    return result


def check_hf_spaces() -> dict:
    """Check health of all HF Spaces."""
    results = {}
    for sid, info in HF_SPACES.items():
        url = info["url"]
        start = time.time()
        data = http_get(f"{url}/api/status", timeout=8)
        latency_ms = int((time.time() - start) * 1000)

        if data:
            results[sid] = {
                "role": info["role"],
                "status": "running",
                "latency_ms": latency_ms,
                "brier": data.get("best_brier", data.get("brier", "?")),
                "generation": data.get("generation", data.get("gen", "?")),
                "model": data.get("best_model", data.get("model", "?")),
            }
        else:
            # Try a simple GET to check if space is alive at all
            alive = http_get(url, timeout=5)
            results[sid] = {
                "role": info["role"],
                "status": "alive" if alive else "offline",
                "latency_ms": latency_ms,
                "brier": None,
                "generation": None,
            }

    # Compute summary
    running = sum(1 for r in results.values() if r["status"] == "running")
    offline = sum(1 for r in results.values() if r["status"] == "offline")
    return {
        "spaces": results,
        "summary": {
            "total": len(results),
            "running": running,
            "offline": offline,
            "alive_but_no_api": len(results) - running - offline,
        },
    }


def check_repos() -> dict:
    """Check git status of all repos."""
    results = {}
    for name, info in REPOS.items():
        repo_path = info["path"]
        repo_result = {
            "path": repo_path,
            "type": info["type"],
            "exists": False,
            "branch": None,
            "dirty": False,
            "ahead": 0,
            "behind": 0,
            "modified_files": 0,
            "untracked_files": 0,
            "last_commit": None,
            "last_commit_age_hours": None,
        }

        if not os.path.isdir(repo_path):
            results[name] = repo_result
            continue

        repo_result["exists"] = True

        try:
            # Current branch
            branch = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=10
            )
            if branch.returncode == 0:
                repo_result["branch"] = branch.stdout.strip()

            # Status (porcelain for easy parsing)
            status = subprocess.run(
                ["git", "-C", repo_path, "status", "--porcelain"],
                capture_output=True, text=True, timeout=10
            )
            if status.returncode == 0:
                lines = [l for l in status.stdout.strip().split("\n") if l]
                repo_result["modified_files"] = sum(1 for l in lines if not l.startswith("??"))
                repo_result["untracked_files"] = sum(1 for l in lines if l.startswith("??"))
                repo_result["dirty"] = len(lines) > 0

            # Last commit
            log = subprocess.run(
                ["git", "-C", repo_path, "log", "-1", "--format=%H|%s|%aI"],
                capture_output=True, text=True, timeout=10
            )
            if log.returncode == 0 and log.stdout.strip():
                parts = log.stdout.strip().split("|", 2)
                if len(parts) >= 3:
                    repo_result["last_commit"] = {
                        "hash": parts[0][:8],
                        "message": parts[1][:80],
                        "date": parts[2],
                    }
                    # Compute age
                    try:
                        commit_dt = datetime.datetime.fromisoformat(parts[2])
                        now = datetime.datetime.now(datetime.timezone.utc)
                        age = now - commit_dt
                        repo_result["last_commit_age_hours"] = round(age.total_seconds() / 3600, 1)
                    except Exception:
                        pass

            # Ahead/behind remote
            ab = subprocess.run(
                ["git", "-C", repo_path, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
                capture_output=True, text=True, timeout=10
            )
            if ab.returncode == 0 and ab.stdout.strip():
                parts = ab.stdout.strip().split()
                if len(parts) == 2:
                    repo_result["ahead"] = int(parts[0])
                    repo_result["behind"] = int(parts[1])

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass

        results[name] = repo_result

    # Summary
    existing = sum(1 for r in results.values() if r["exists"])
    dirty = sum(1 for r in results.values() if r["dirty"])
    stale = sum(1 for r in results.values()
                if r.get("last_commit_age_hours") and r["last_commit_age_hours"] > 48)

    return {
        "repos": results,
        "summary": {
            "total": len(results),
            "found": existing,
            "not_found": len(results) - existing,
            "dirty": dirty,
            "stale_48h": stale,
        },
    }


def check_bloomberg_api() -> dict:
    """Check if the Bloomberg API server is running on the VM."""
    result = {"status": "offline", "url": BLOOMBERG_API, "data": None}
    data = http_get(f"{BLOOMBERG_API}/api/health", timeout=5)
    if data:
        result["status"] = "online"
        result["data"] = data
    return result


def ollama_generate(prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 1000) -> str | None:
    """Generate text using Ollama API."""
    data = http_post(
        f"{OLLAMA_URL}/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.3,
                "top_p": 0.9,
            },
        },
        timeout=120,
    )
    if data:
        return data.get("response", "")
    return None


# ── Analysis Generation ───────────────────────────────────────────────────

def generate_analysis(report: dict, model: str = DEFAULT_MODEL) -> str | None:
    """Use local Ollama model to generate analysis from the monitoring report."""
    # Build a compact summary for the LLM
    hf = report.get("hf_spaces", {})
    hf_summary = hf.get("summary", {})
    repos = report.get("repos", {})
    repo_summary = repos.get("summary", {})
    bloomberg = report.get("bloomberg_api", {})

    # Extract top-level numbers
    spaces_running = hf_summary.get("running", 0)
    spaces_total = hf_summary.get("total", 0)
    spaces_offline = hf_summary.get("offline", 0)

    # Best Brier from spaces
    best_brier = 999.0
    best_island = ""
    for sid, sdata in hf.get("spaces", {}).items():
        try:
            b = float(sdata.get("brier", 999))
            if b < best_brier:
                best_brier = b
                best_island = sid
        except (ValueError, TypeError):
            pass

    # Dirty/stale repos
    dirty_repos = [name for name, r in repos.get("repos", {}).items() if r.get("dirty")]
    stale_repos = [name for name, r in repos.get("repos", {}).items()
                   if r.get("last_commit_age_hours") and r["last_commit_age_hours"] > 48]

    prompt = f"""You are the Nomos42 AI monitoring agent. Analyze this system health snapshot and provide a brief daily analysis.

SYSTEM STATUS:
- HF Spaces: {spaces_running}/{spaces_total} running, {spaces_offline} offline
- Best Brier: {best_brier:.5f} ({best_island})
- Repos found: {repo_summary.get('found', 0)}/{repo_summary.get('total', 0)}
- Dirty repos: {', '.join(dirty_repos) if dirty_repos else 'none'}
- Stale repos (>48h): {', '.join(stale_repos) if stale_repos else 'none'}
- Bloomberg API: {bloomberg.get('status', 'unknown')}

Provide a 3-5 bullet point analysis covering:
1. Overall system health (GREEN/YELLOW/RED)
2. Any issues requiring attention
3. Evolution fleet performance
4. Recommendations for next 24 hours

Keep it concise and actionable. Output as plain text, no JSON."""

    return ollama_generate(prompt, model=model, max_tokens=500)


# ── Main Report Generation ─────────────────────────────────────────────────

def run_monitoring_cycle(model: str = DEFAULT_MODEL, quick: bool = False) -> dict:
    """Run a full monitoring cycle and return the report."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(f"[{timestamp[:19]}] Starting monitoring cycle...")

    report = {
        "timestamp": timestamp,
        "version": "agent-monitor-v1.0",
        "model_used": model,
        "quick_mode": quick,
    }

    # Step 1: Check Ollama
    print("  [1/5] Checking Ollama...")
    report["ollama"] = check_ollama()
    ollama_ok = report["ollama"]["status"] == "online"
    print(f"  -> Ollama: {report['ollama']['status']} ({len(report['ollama']['models'])} models)")

    # Step 2: Check HF Spaces
    print("  [2/5] Checking HF Spaces...")
    report["hf_spaces"] = check_hf_spaces()
    hf_s = report["hf_spaces"]["summary"]
    print(f"  -> Spaces: {hf_s['running']}/{hf_s['total']} running")

    if quick:
        # Quick mode: skip repos and analysis
        report["repos"] = {"summary": {"note": "skipped in quick mode"}}
        report["bloomberg_api"] = {"status": "skipped"}
        report["analysis"] = "Quick mode — no analysis generated."
        return report

    # Step 3: Check repos
    print("  [3/5] Checking git repos...")
    report["repos"] = check_repos()
    repo_s = report["repos"]["summary"]
    print(f"  -> Repos: {repo_s['found']}/{repo_s['total']} found, {repo_s['dirty']} dirty")

    # Step 4: Check Bloomberg API
    print("  [4/5] Checking Bloomberg API...")
    report["bloomberg_api"] = check_bloomberg_api()
    print(f"  -> Bloomberg API: {report['bloomberg_api']['status']}")

    # Step 5: Generate analysis with Ollama
    if ollama_ok:
        print(f"  [5/5] Generating analysis with {model}...")
        analysis = generate_analysis(report, model=model)
        report["analysis"] = analysis or "Analysis generation failed."
        print(f"  -> Analysis: {len(analysis)} chars" if analysis else "  -> Analysis: failed")
    else:
        report["analysis"] = "Ollama offline — no analysis generated."
        print("  [5/5] Skipping analysis (Ollama offline)")

    # Compute overall health
    health = "GREEN"
    issues = []

    if hf_s["offline"] > 0:
        health = "YELLOW" if hf_s["offline"] <= 2 else "RED"
        issues.append(f"{hf_s['offline']} spaces offline")

    if repo_s.get("stale_48h", 0) > 2:
        health = max(health, "YELLOW")
        issues.append(f"{repo_s['stale_48h']} repos stale >48h")

    if not ollama_ok:
        issues.append("Ollama offline")

    report["overall_health"] = health
    report["issues"] = issues

    return report


def save_report(report: dict, output_path: str | None = None) -> str:
    """Save report to JSON file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path:
        path = Path(output_path)
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUTPUT_DIR / f"monitor-{ts}.json"

    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Also save as latest
    latest = OUTPUT_DIR / "monitor-latest.json"
    with open(latest, "w") as f:
        json.dump(report, f, indent=2, default=str)

    return str(path)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Nomos42 Agent Monitor")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--quick", action="store_true", help="Quick health check only (no repos, no analysis)")
    parser.add_argument("--loop", type=int, default=0, help="Loop interval in seconds (0 = run once)")
    parser.add_argument("--output", default=None, help="Output file path (default: reports/monitor-TIMESTAMP.json)")
    parser.add_argument("--bloomberg-api", default=None, help=f"Bloomberg API URL (default: {BLOOMBERG_API})")
    args = parser.parse_args()

    if args.bloomberg_api:
        global BLOOMBERG_API
        BLOOMBERG_API = args.bloomberg_api

    print("""
╔══════════════════════════════════════════════════════╗
║     Nomos42 Agent Monitor v1.0                       ║
║     Laptop-based Monitoring Agent                    ║
╚══════════════════════════════════════════════════════╝
""")
    print(f"  Model:  {args.model}")
    print(f"  Mode:   {'quick' if args.quick else 'full'}")
    print(f"  Loop:   {'every ' + str(args.loop) + 's' if args.loop > 0 else 'once'}")
    print(f"  API:    {BLOOMBERG_API}")
    print()

    def run_once():
        report = run_monitoring_cycle(model=args.model, quick=args.quick)
        saved = save_report(report, args.output)

        print()
        print(f"  Health: {report['overall_health']}")
        if report.get("issues"):
            print(f"  Issues: {', '.join(report['issues'])}")
        print(f"  Report: {saved}")

        if report.get("analysis") and "skipped" not in str(report["analysis"]).lower():
            print()
            print("  --- Analysis ---")
            print(f"  {report['analysis'][:500]}")
        print()

        return report

    if args.loop > 0:
        cycle = 0
        while True:
            cycle += 1
            print(f"{'='*60}")
            print(f"  Cycle {cycle} — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}")
            try:
                run_once()
            except Exception as e:
                print(f"  ERROR in cycle {cycle}: {e}")
            print(f"  Next cycle in {args.loop}s...")
            try:
                time.sleep(args.loop)
            except KeyboardInterrupt:
                print("\nMonitor stopped.")
                break
    else:
        run_once()


if __name__ == "__main__":
    main()
