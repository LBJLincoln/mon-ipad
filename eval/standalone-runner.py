#!/usr/bin/env python3
"""
STANDALONE RUNNER — Runs eval continuously without Claude Code.
================================================================
Autonomous evaluation loop that runs on any VM/Codespace/HF Space.
No Claude Code dependency. Just Python + n8n.

Features:
- Continuous eval loop (runs all pipelines, then restarts)
- Auto-stop on N consecutive failures per pipeline (default: 3)
- Auto-push results to GitHub every push_interval minutes
- Optimized batch sizes per pipeline
- Parallel execution within pipelines (--batch-size)
- Progress monitoring via /tmp/eval-progress.json
- Health checks before each run
- Can run as systemd service, nohup, or foreground

Usage:
  # Foreground (debug)
  source .env.local && python3 eval/standalone-runner.py --dataset phase-2

  # Background (production)
  source .env.local && nohup python3 eval/standalone-runner.py \\
    --dataset phase-2 --label "autonomous-v1" --push-interval 15 \\
    > /tmp/standalone-runner.log 2>&1 &

  # Single pass (no loop)
  source .env.local && python3 eval/standalone-runner.py --dataset phase-2 --once

  # Custom pipelines with batch sizes
  source .env.local && python3 eval/standalone-runner.py \\
    --types standard,graph --batch-size 5 --dataset phase-2

Environment variables required:
  N8N_HOST — n8n base URL (default: https://lbjlincoln-nomos-rag-engine.hf.space)
             For HF Space: https://lbjlincoln-nomos-rag-engine.hf.space
  OPENROUTER_API_KEY — for local LLM fallback

Last updated: 2026-02-22
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(REPO_ROOT, "eval")
PID_FILE = "/tmp/standalone-runner.pid"
PROGRESS_FILE = "/tmp/eval-progress.json"
LOG_PREFIX = "[standalone]"

# Optimized batch sizes per pipeline
DEFAULT_BATCH_SIZES = {
    "standard": 5,
    "graph": 3,
    "quantitative": 5,
    "orchestrator": 1,  # calls sub-workflows, no parallel
}

# Paris timezone
PARIS_TZ = timezone(timedelta(hours=1))

_running = True


def log(msg):
    ts = datetime.now(PARIS_TZ).strftime("%H:%M:%S")
    print(f"{LOG_PREFIX} [{ts}] {msg}", flush=True)


def signal_handler(sig, frame):
    global _running
    log(f"Received signal {sig}, shutting down gracefully...")
    _running = False


def check_n8n_health(n8n_host):
    """Check if n8n is reachable and healthy."""
    import urllib.request
    import urllib.error
    url = f"{n8n_host}/healthz"
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data.get("status") == "ok"
    except Exception as e:
        log(f"Health check failed: {e}")
        return False


def check_webhook(n8n_host, path):
    """Check if a specific webhook is registered (responds to POST)."""
    import urllib.request
    import urllib.error
    url = f"{n8n_host}/webhook/{path}"
    try:
        data = json.dumps({"test": True}).encode()
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        return True  # Any non-404 response means webhook is registered
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        return True  # 500 means workflow errored but webhook IS registered
    except Exception:
        return False


def auto_push(repo_root, label=""):
    """Commit and push results to GitHub."""
    try:
        # Regenerate status
        status_script = os.path.join(repo_root, "eval", "generate_status.py")
        if os.path.exists(status_script):
            subprocess.run(
                [sys.executable, status_script],
                cwd=repo_root, capture_output=True, timeout=30
            )

        # Check for changes
        result = subprocess.run(
            ["git", "status", "--porcelain", "docs/status.json", "docs/data.json",
             "website/public/eval-data.json", "logs/pipeline-results/"],
            cwd=repo_root, capture_output=True, text=True, timeout=10
        )
        if not result.stdout.strip():
            return  # No changes

        # Security check
        diff = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=repo_root, capture_output=True, text=True, timeout=10
        )
        import re
        if re.search(r'sk-or-|pcsk_|jV_zGdx|sbp_|hf_[A-Za-z]{10}|ghp_', diff.stdout):
            log("SECURITY: Credentials detected in diff! Skipping push.")
            return

        # Stage + commit + push
        subprocess.run(
            ["git", "add", "docs/status.json", "docs/data.json",
             "website/public/eval-data.json", "logs/pipeline-results/"],
            cwd=repo_root, capture_output=True, timeout=10
        )

        commit_msg = f"auto: standalone runner {label} {datetime.now(PARIS_TZ).strftime('%H:%M')}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg, "--no-verify"],
            cwd=repo_root, capture_output=True, timeout=15
        )

        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=repo_root, capture_output=True, timeout=30
        )
        log("Auto-push: committed and pushed to origin")

    except Exception as e:
        log(f"Auto-push error: {e}")


def write_progress(status, pipelines_status, label=""):
    """Write progress file for remote monitoring."""
    try:
        progress = {
            "status": status,
            "label": label,
            "timestamp": datetime.now(PARIS_TZ).isoformat(),
            "pid": os.getpid(),
            "pipelines": pipelines_status,
        }
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f, indent=2)
    except Exception:
        pass


def run_eval(types, dataset, batch_size, max_q, label, early_stop, force,
             local_pipelines="", n8n_host=None):
    """Run a single eval pass using run-eval-parallel.py."""
    cmd = [
        sys.executable, os.path.join(EVAL_DIR, "run-eval-parallel.py"),
        "--types", ",".join(types),
        "--dataset", dataset,
        "--early-stop", str(early_stop),
        "--label", label,
        "--force",  # always force in standalone mode (gates already checked)
    ]
    if batch_size:
        cmd.extend(["--batch-size", str(batch_size)])
    if max_q:
        cmd.extend(["--max", str(max_q)])
    if local_pipelines:
        cmd.extend(["--local-pipelines", local_pipelines])

    env = os.environ.copy()
    if n8n_host:
        env["N8N_HOST"] = n8n_host

    log(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=REPO_ROOT, env=env,
            timeout=7200,  # 2 hour max per eval run
            capture_output=False,  # let output flow to stdout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log("Eval run timed out after 2 hours")
        return False
    except Exception as e:
        log(f"Eval run error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Standalone Runner — Continuous RAG eval without Claude Code")
    parser.add_argument("--dataset", type=str, default="phase-2",
                        choices=["phase-1", "phase-2", "all"],
                        help="Dataset to evaluate (default: phase-2)")
    parser.add_argument("--types", type=str, default="standard,graph,quantitative,orchestrator",
                        help="Comma-separated pipeline types")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Override batch size for all pipelines (default: per-pipeline optimal)")
    parser.add_argument("--max", type=int, default=None,
                        help="Max questions per pipeline per pass")
    parser.add_argument("--label", type=str, default="standalone",
                        help="Label for this eval run")
    parser.add_argument("--early-stop", type=int, default=3,
                        help="Stop pipeline after N consecutive failures (default: 3)")
    parser.add_argument("--push-interval", type=int, default=15,
                        help="Auto-push interval in minutes (default: 15, 0=disable)")
    parser.add_argument("--once", action="store_true",
                        help="Run once then exit (no continuous loop)")
    parser.add_argument("--n8n-host", type=str, default=None,
                        help="n8n host URL (overrides N8N_HOST env)")
    parser.add_argument("--local-pipelines", type=str, default="",
                        help="Pipelines to run via local LLM (e.g. quantitative,graph)")
    parser.add_argument("--max-passes", type=int, default=0,
                        help="Max number of eval passes (0=unlimited)")
    parser.add_argument("--pause-between", type=int, default=60,
                        help="Pause between eval passes in seconds (default: 60)")
    args = parser.parse_args()

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Write PID file
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    n8n_host = args.n8n_host or os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
    types = [t.strip() for t in args.types.split(",")]

    log("=" * 60)
    log("STANDALONE RUNNER — Autonomous RAG Evaluation")
    log(f"  PID: {os.getpid()}")
    log(f"  Dataset: {args.dataset}")
    log(f"  Pipelines: {', '.join(types)}")
    log(f"  N8N Host: {n8n_host}")
    log(f"  Batch size: {args.batch_size or 'per-pipeline optimal'}")
    log(f"  Early stop: {args.early_stop} consecutive failures")
    log(f"  Push interval: {args.push_interval}m")
    log(f"  Mode: {'single pass' if args.once else 'continuous loop'}")
    log("=" * 60)

    # Pre-flight: check n8n health
    log("Checking n8n health...")
    health_retries = 0
    while not check_n8n_health(n8n_host):
        health_retries += 1
        if health_retries > 10:
            log("FATAL: n8n not reachable after 10 attempts. Exiting.")
            sys.exit(1)
        log(f"n8n not ready (attempt {health_retries}/10), waiting 30s...")
        time.sleep(30)
    log("n8n is healthy!")

    # Check critical webhooks
    webhook_paths = {
        "standard": "rag-multi-index-v3",
        "graph": "ff622742-6d71-4e91-af71-b5c666088717",
        "quantitative": "3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "orchestrator": "92217bb8-ffc8-459a-8331-3f553812c3d0",
    }
    active_types = []
    for t in types:
        if t in webhook_paths:
            if check_webhook(n8n_host, webhook_paths[t]):
                active_types.append(t)
                log(f"  {t}: webhook OK")
            else:
                log(f"  {t}: webhook 404 — SKIPPING this pipeline")
        else:
            active_types.append(t)

    if not active_types:
        log("FATAL: No active webhooks found. All pipelines 404. Exiting.")
        sys.exit(1)

    types = active_types

    # Determine batch size
    batch_size = args.batch_size
    if not batch_size:
        # Use max of per-pipeline defaults (run-eval-parallel handles per-pipeline internally)
        batch_size = max(DEFAULT_BATCH_SIZES.get(t, 1) for t in types)

    # Auto-push tracking
    last_push = time.time()
    pass_count = 0

    # Main loop
    while _running:
        pass_count += 1
        log(f"\n{'='*60}")
        log(f"PASS {pass_count} — {datetime.now(PARIS_TZ).isoformat()}")
        log(f"{'='*60}")

        write_progress("running", {t: "pending" for t in types}, args.label)

        # Run eval
        success = run_eval(
            types=types,
            dataset=args.dataset,
            batch_size=batch_size,
            max_q=args.max,
            label=f"{args.label}-pass{pass_count}",
            early_stop=args.early_stop,
            force=True,
            local_pipelines=args.local_pipelines,
            n8n_host=n8n_host,
        )

        if success:
            log(f"Pass {pass_count} completed successfully")
        else:
            log(f"Pass {pass_count} had errors (see output above)")

        # Auto-push if interval elapsed
        if args.push_interval > 0 and (time.time() - last_push) >= args.push_interval * 60:
            log("Auto-push triggered...")
            auto_push(REPO_ROOT, label=args.label)
            last_push = time.time()

        write_progress("idle", {t: "completed" for t in types}, args.label)

        # Exit conditions
        if args.once:
            log("Single pass mode (--once), exiting.")
            break

        if args.max_passes > 0 and pass_count >= args.max_passes:
            log(f"Reached max passes ({args.max_passes}), exiting.")
            break

        if not _running:
            break

        # Pause between passes
        log(f"Pausing {args.pause_between}s before next pass...")
        for _ in range(args.pause_between):
            if not _running:
                break
            time.sleep(1)

    # Final push
    if args.push_interval > 0:
        log("Final auto-push...")
        auto_push(REPO_ROOT, label=args.label)

    write_progress("stopped", {}, args.label)

    # Cleanup
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass

    log(f"Standalone runner exited after {pass_count} passes.")


if __name__ == "__main__":
    main()
