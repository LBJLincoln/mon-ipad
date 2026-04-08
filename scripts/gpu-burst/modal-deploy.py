#!/usr/bin/env python3
"""
Nomos42 -- Modal Serverless GPU Deploy
=======================================
Wrapper that launches modal-burst.py on Modal's serverless infrastructure.
Can also be run directly as a Modal app via `modal run`.

Usage (from VM -- orchestrates remote GPU work, zero local ML):
    python3 scripts/gpu-burst/modal-deploy.py                    # Default: A10G, 10 min
    python3 scripts/gpu-burst/modal-deploy.py --gpu a100         # A100 GPU ($0.62/burst)
    python3 scripts/gpu-burst/modal-deploy.py --timeout 300      # 5 min burst
    python3 scripts/gpu-burst/modal-deploy.py --status           # Check last result
    python3 scripts/gpu-burst/modal-deploy.py --cost-check       # Estimate cost only

    # Direct Modal CLI (if you prefer):
    modal run scripts/gpu-burst/modal-burst.py
    modal run scripts/gpu-burst/modal-burst.py --gpu a100

Cron example:
    # On-demand only (costs money). Use compute-orchestrator.py for scheduling.
    0 14 * * 1 python3 /home/termius/mon-ipad/scripts/gpu-burst/modal-deploy.py >> /home/termius/mon-ipad/logs/modal-burst.log 2>&1
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ══════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════

REPO_ROOT = Path("/home/termius/mon-ipad")
SCRIPT_DIR = REPO_ROOT / "scripts" / "gpu-burst"
MODAL_BURST = SCRIPT_DIR / "modal-burst.py"
RESULT_DIR = REPO_ROOT / "data" / "gpu-burst"
LOG_DIR = REPO_ROOT / "logs"

# Cost per hour by GPU type (approximate, Modal pricing as of 2026)
GPU_COST_PER_HOUR = {
    "T4": 0.59,
    "A10G": 1.10,
    "A100": 3.73,
    "A100-80GB": 4.53,
    "H100": 7.49,
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, level: str = "INFO"):
    print(f"[{ts()}] [{level}] {msg}")


# ══════════════════════════════════════════════════════════
# PRE-FLIGHT CHECKS
# ══════════════════════════════════════════════════════════

def check_modal_installed() -> bool:
    """Check if Modal is installed and authenticated."""
    try:
        import modal  # noqa: F401
        log("Modal Python package: OK")
    except ImportError:
        log("Modal not installed -- installing...", "WARN")
        ret = subprocess.run(
            [sys.executable, "-m", "pip", "install", "modal", "--break-system-packages", "-q"],
            capture_output=True, text=True,
        )
        if ret.returncode != 0:
            log(f"Failed to install modal: {ret.stderr[:200]}", "ERROR")
            return False
        log("Modal installed successfully")

    # Check authentication
    ret = subprocess.run(
        ["modal", "profile", "current"],
        capture_output=True, text=True,
    )
    if ret.returncode == 0:
        profile = ret.stdout.strip()
        log(f"Modal profile: {profile}")
        return True
    else:
        log("Modal not authenticated. Run: modal token set", "ERROR")
        return False


def check_secrets() -> dict:
    """Check which secrets are available in Modal."""
    ret = subprocess.run(
        ["modal", "secret", "list"],
        capture_output=True, text=True,
    )
    secrets_found = {}
    if ret.returncode == 0:
        output = ret.stdout
        secrets_found["nomos42-secrets"] = "nomos42-secrets" in output
    else:
        secrets_found["nomos42-secrets"] = False

    if not secrets_found.get("nomos42-secrets"):
        log("Modal secret 'nomos42-secrets' not found.", "WARN")
        log("Create it: modal secret create nomos42-secrets "
            "HF_TOKEN=xxx GITHUB_TOKEN=xxx", "WARN")

    return secrets_found


# ══════════════════════════════════════════════════════════
# STATUS CHECK
# ══════════════════════════════════════════════════════════

def check_status():
    """Check last burst result from local files and Modal volume."""
    log("=== Modal Burst Status ===")

    # Local result file
    result_file = RESULT_DIR / "latest-modal-result.json"
    if result_file.exists():
        try:
            result = json.loads(result_file.read_text())
            log(f"Last local result:")
            log(f"  Brier: {result.get('best_brier', '?')}")
            log(f"  Model: {result.get('model_type', '?')}")
            log(f"  Features: {result.get('n_features', '?')}")
            log(f"  Iterations: {result.get('iterations', '?')}")
            log(f"  Time: {result.get('total_time_sec', '?')}s")
            log(f"  Platform: {result.get('platform', '?')}")
            log(f"  Timestamp: {result.get('timestamp', '?')}")
            log(f"  Beat ATR: {result.get('beat_atr', '?')}")
        except Exception as e:
            log(f"Could not parse result: {e}", "WARN")
    else:
        log("No local result file found")

    # Check Modal volume status (no GPU cost)
    log("\nChecking Modal volume...")
    ret = subprocess.run(
        ["modal", "run", str(MODAL_BURST) + "::check_status"],
        capture_output=True, text=True, timeout=120,
    )
    if ret.returncode == 0:
        log("Modal volume status:")
        for line in ret.stdout.strip().split("\n"):
            log(f"  {line}")
    else:
        log(f"Modal check failed: {ret.stderr[:200]}", "WARN")


# ══════════════════════════════════════════════════════════
# COST ESTIMATION
# ══════════════════════════════════════════════════════════

def estimate_cost(gpu: str, timeout: int) -> float:
    """Estimate cost for a burst."""
    hourly = GPU_COST_PER_HOUR.get(gpu, GPU_COST_PER_HOUR["A10G"])
    # Add 50% overhead for setup/teardown
    effective_minutes = (timeout / 60) * 1.5
    cost = hourly * (effective_minutes / 60)
    return round(cost, 3)


# ══════════════════════════════════════════════════════════
# DEPLOY
# ══════════════════════════════════════════════════════════

def deploy(gpu: str = "A10G", timeout: int = 600, dry_run: bool = False):
    """Launch Modal burst."""
    cost = estimate_cost(gpu, timeout)
    log(f"=== Modal GPU Burst Deploy ===")
    log(f"GPU: {gpu}")
    log(f"Timeout: {timeout}s ({timeout/60:.0f} min)")
    log(f"Estimated cost: ${cost:.3f}")
    log(f"Script: {MODAL_BURST}")

    if dry_run:
        log("DRY RUN -- not launching")
        return

    # Pre-flight
    if not check_modal_installed():
        sys.exit(1)

    check_secrets()

    # Ensure result directory exists
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    # Launch via modal CLI
    log(f"\nLaunching burst on Modal {gpu}...")
    start_time = time.time()

    cmd = [
        "modal", "run", str(MODAL_BURST),
        "--gpu", gpu,
        "--timeout", str(timeout),
    ]

    log(f"Command: {' '.join(cmd)}")

    ret = subprocess.run(
        cmd,
        capture_output=False,  # Stream output to stdout
        text=True,
        timeout=timeout + 300,  # Extra 5 min for Modal overhead
    )

    elapsed = time.time() - start_time
    actual_cost = GPU_COST_PER_HOUR.get(gpu, 1.10) * (elapsed / 3600)

    if ret.returncode == 0:
        log(f"\nBurst completed in {elapsed:.0f}s (est. cost: ${actual_cost:.3f})")

        # Check if result was pushed to local
        result_file = RESULT_DIR / "latest-modal-result.json"
        if result_file.exists():
            result = json.loads(result_file.read_text())
            log(f"Result: brier={result.get('best_brier', '?')}, "
                f"model={result.get('model_type', '?')}, "
                f"features={result.get('n_features', '?')}")
    else:
        log(f"Burst failed (exit code {ret.returncode})", "ERROR")
        log(f"Elapsed: {elapsed:.0f}s, Wasted cost: ~${actual_cost:.3f}", "ERROR")

    # Log to JSONL
    log_entry = {
        "timestamp": ts(),
        "gpu": gpu,
        "timeout": timeout,
        "elapsed": round(elapsed, 1),
        "estimated_cost": round(actual_cost, 4),
        "exit_code": ret.returncode,
        "success": ret.returncode == 0,
    }
    log_file = RESULT_DIR / "modal-deploy-log.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Modal Serverless GPU Deploy for NBA Quant Evolution"
    )
    parser.add_argument(
        "--gpu", default="A10G",
        choices=["T4", "A10G", "A100", "A100-80GB", "H100"],
        help="GPU type (default: A10G)"
    )
    parser.add_argument(
        "--timeout", type=int, default=600,
        help="Burst duration in seconds (default: 600)"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Check last burst result (no GPU cost)"
    )
    parser.add_argument(
        "--cost-check", action="store_true",
        help="Estimate cost without running"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without launching"
    )

    args = parser.parse_args()

    if args.status:
        check_status()
    elif args.cost_check:
        cost = estimate_cost(args.gpu, args.timeout)
        log(f"Estimated cost: ${cost:.3f} ({args.gpu}, {args.timeout}s)")
        log(f"Hourly rate: ${GPU_COST_PER_HOUR.get(args.gpu, '?')}/hr")
    else:
        deploy(
            gpu=args.gpu,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
