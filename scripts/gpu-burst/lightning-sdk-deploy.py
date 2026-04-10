#!/usr/bin/env python3
"""
Nomos42 -- Lightning AI GPU Burst via lightning_sdk
=====================================================
Launches a 10-min NBA evolution burst on Lightning AI using the Python SDK.
No lightning CLI needed — uses lightning_sdk directly.

Usage:
    python3 scripts/gpu-burst/lightning-sdk-deploy.py
    python3 scripts/gpu-burst/lightning-sdk-deploy.py --check
    python3 scripts/gpu-burst/lightning-sdk-deploy.py --mode political

Cron:
    0 12 * * * /home/termius/mon-ipad/scripts/gpu-burst/lightning-sdk-deploy.py >> /home/termius/mon-ipad/logs/lightning-burst.log 2>&1

Requires in .env.local:
    LIGHTNING_USER_ID=8c36cf20-9101-4f04-98c7-eb1f35ec3---
    LIGHTNING_API_KEY=ea1fc226-7481-4fd5-85cf-c3ea45291---
"""

import argparse
import json
import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path("/home/termius/mon-ipad")
RESULT_DIR = REPO_ROOT / "data" / "gpu-burst"
LOG_DIR = REPO_ROOT / "logs"
BURST_SCRIPT = REPO_ROOT / "scripts" / "gpu-burst" / "lightning-burst.py"
RESULT_FILE = RESULT_DIR / "latest-lightning-nba-result.json"

# Lightning AI studio details (from reference_lightning_ai.md)
LIGHTNING_USER = "moretalexis24"
LIGHTNING_TEAMSPACE = "inference-optimization-project"
LIGHTNING_STUDIO = "nba-tabicl-eval"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, level: str = "INFO"):
    print(f"[{ts()}] [{level}] {msg}")


def load_env():
    """Load .env.local into os.environ."""
    env_file = REPO_ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:]
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and val and key not in os.environ:
                os.environ[key] = val


def check_studio():
    """Check Lightning AI studio status."""
    user_id = os.environ.get("LIGHTNING_USER_ID", "")
    api_key = os.environ.get("LIGHTNING_API_KEY", "")

    if not user_id or not api_key:
        log("LIGHTNING_USER_ID or LIGHTNING_API_KEY not set", "ERROR")
        return {"status": "error", "reason": "no credentials"}

    try:
        from lightning_sdk import Studio
        os.environ["LIGHTNING_USER_ID"] = user_id
        os.environ["LIGHTNING_API_KEY"] = api_key

        s = Studio(
            name=LIGHTNING_STUDIO,
            teamspace=LIGHTNING_TEAMSPACE,
            user=LIGHTNING_USER,
        )
        status = s.status
        log(f"Studio '{LIGHTNING_STUDIO}' status: {status}")
        return {"status": str(status), "studio": LIGHTNING_STUDIO}
    except Exception as e:
        log(f"Studio check failed: {e}", "WARN")
        return {"status": "error", "reason": str(e)}


def run_burst(mode: str = "nba") -> dict:
    """Launch a GPU burst on Lightning AI Studio using lightning_sdk."""
    load_env()
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    user_id = os.environ.get("LIGHTNING_USER_ID", "")
    api_key = os.environ.get("LIGHTNING_API_KEY", "")
    hf_token = os.environ.get("HF_TOKEN", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    db_url = os.environ.get("DATABASE_URL", "")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("ADMIN_TELEGRAM_ID", "")

    if not user_id or not api_key:
        log("LIGHTNING_USER_ID or LIGHTNING_API_KEY not set — skipping", "ERROR")
        return {
            "status": "error",
            "reason": "no lightning credentials",
            "platform": "lightning",
            "timestamp": ts(),
        }

    log(f"=== Lightning AI GPU Burst (mode={mode}) ===")
    start = time.time()

    try:
        from lightning_sdk import Studio, Machine

        os.environ["LIGHTNING_USER_ID"] = user_id
        os.environ["LIGHTNING_API_KEY"] = api_key

        log(f"Connecting to studio '{LIGHTNING_STUDIO}' ({LIGHTNING_TEAMSPACE}/{LIGHTNING_USER})...")
        studio = Studio(
            name=LIGHTNING_STUDIO,
            teamspace=LIGHTNING_TEAMSPACE,
            user=LIGHTNING_USER,
        )

        # Start the studio with T4 GPU
        log("Starting studio with T4 GPU...")
        try:
            studio.start(machine=Machine.T4)
            log("Studio started on T4")
        except Exception as e:
            log(f"T4 start failed ({e}), trying CPU...", "WARN")
            studio.start()
            log("Studio started on CPU (no GPU)")

        # Upload the burst script
        log("Uploading burst script to studio...")
        studio.upload_file(str(BURST_SCRIPT), "/teamspace/studios/this_studio/lightning-burst.py")

        # Run the burst remotely
        log("Executing burst on Lightning AI...")
        cmd = (
            f"cd /teamspace/studios/this_studio && "
            f"pip install -q xgboost lightgbm catboost scikit-learn 2>/dev/null && "
            f"BURST_MODE={mode} "
            f"HF_TOKEN='{hf_token}' "
            f"GITHUB_TOKEN='{github_token}' "
            f"DATABASE_URL='{db_url}' "
            f"TELEGRAM_BOT_TOKEN='{telegram_token}' "
            f"ADMIN_TELEGRAM_ID='{telegram_chat}' "
            f"python3 lightning-burst.py"
        )
        output = studio.run(cmd, timeout=720)  # 12 min max

        # Download result
        result_remote = f"/teamspace/studios/this_studio/burst-cache/burst_result_{mode}.json"
        try:
            studio.download_file(result_remote, str(RESULT_FILE))
            log(f"Downloaded result to {RESULT_FILE}")
        except Exception as e:
            log(f"Result download failed: {e}", "WARN")

        # Stop studio to save credits
        log("Stopping studio...")
        studio.stop()

        elapsed = time.time() - start

        # Parse result
        result = {
            "status": "success",
            "platform": "lightning_t4",
            "elapsed_sec": round(elapsed, 1),
            "timestamp": ts(),
        }

        if RESULT_FILE.exists():
            try:
                burst_result = json.loads(RESULT_FILE.read_text())
                result.update(burst_result)
                log(f"Best Brier: {burst_result.get('best_brier', '?')}")
                log(f"Improvement: {burst_result.get('improvement', '?')}")
            except Exception:
                pass

        log(f"=== Burst complete ({elapsed:.0f}s) ===")
        return result

    except Exception as e:
        elapsed = time.time() - start
        log(f"Lightning burst failed: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e)[:500],
            "platform": "lightning",
            "elapsed_sec": round(elapsed, 1),
            "timestamp": ts(),
        }


def main():
    load_env()

    parser = argparse.ArgumentParser(description="Lightning AI GPU burst via lightning_sdk")
    parser.add_argument("--check", action="store_true", help="Check studio status")
    parser.add_argument("--mode", default="nba", choices=["nba", "political"])
    args = parser.parse_args()

    if args.check:
        result = check_studio()
        print(json.dumps(result, indent=2))
    else:
        result = run_burst(mode=args.mode)
        # Write result for orchestrator to pick up
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        result_out = RESULT_DIR / f"latest-lightning-{args.mode}-result.json"
        result_out.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("status") in ("success", "error") else 1)


if __name__ == "__main__":
    main()
