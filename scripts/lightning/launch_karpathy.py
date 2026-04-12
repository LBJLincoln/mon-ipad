#!/usr/bin/env python3
"""
Lightning.ai Karpathy Launcher — Credit-Efficient GPU Evolution
===============================================================
Launches a Karpathy autoresearch loop on Lightning.ai T4 GPU.
Uses lightning_sdk to programmatically start/stop studios.

Usage:
    # From VM (strategist role):
    python3 scripts/lightning/launch_karpathy.py --account 1 --iterations 200 --hours 4
    python3 scripts/lightning/launch_karpathy.py --account 2 --iterations 200 --hours 4

    # Parallel burst (both accounts):
    python3 scripts/lightning/launch_karpathy.py --account 1 --iterations 200 --hours 4 &
    python3 scripts/lightning/launch_karpathy.py --account 2 --iterations 200 --hours 4 &

Credit strategy:
    - T4 GPU = cheapest option (~$0.10/hr on free tier)
    - 22h free/account/month → 44h total with 2 accounts
    - Auto-stop after --hours to preserve credits
    - Each iteration ~25s → ~144 iter/hr → 576 iter in 4h burst
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# Load env
_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = _ROOT / ".env.local"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k = k.strip().removeprefix("export").strip()
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))

# Account configs
ACCOUNTS = {
    1: {
        "user_id": os.environ.get("LIGHTNING_USER_ID", "8c36cf20-9101-4f04-98c7-eb1f35ec3eb4"),
        "api_key": os.environ.get("LIGHTNING_API_KEY", ""),
        "user": "moretalexis24",
        "teamspace": "inference-optimization-project",
        "studio_name": "nba-karpathy-1",
    },
    2: {
        "user_id": os.environ.get("LIGHTNING_USER_ID_2", ""),
        "api_key": os.environ.get("LIGHTNING_API_KEY_2", ""),
        "user": os.environ.get("LIGHTNING_USER_2", ""),
        "teamspace": os.environ.get("LIGHTNING_TEAMSPACE_2", ""),
        "studio_name": "nba-karpathy-2",
    },
}


def main():
    parser = argparse.ArgumentParser(description="Launch Karpathy loop on Lightning.ai")
    parser.add_argument("--account", type=int, choices=[1, 2], default=1, help="Which Lightning account to use")
    parser.add_argument("--iterations", type=int, default=200, help="Max iterations")
    parser.add_argument("--hours", type=float, default=4.0, help="Max hours (auto-stop after)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    args = parser.parse_args()

    acct = ACCOUNTS[args.account]
    if not acct["api_key"]:
        print(f"ERROR: No API key for account {args.account}. Set LIGHTNING_API_KEY{'_2' if args.account == 2 else ''} in .env.local")
        sys.exit(1)

    os.environ["LIGHTNING_USER_ID"] = acct["user_id"]
    os.environ["LIGHTNING_API_KEY"] = acct["api_key"]

    print(f"=== Lightning Karpathy Launcher ===")
    print(f"Account: {args.account} ({acct['user']})")
    print(f"Studio:  {acct['studio_name']}")
    print(f"Budget:  {args.iterations} iterations, {args.hours}h max")
    print()

    if args.dry_run:
        print("[DRY RUN] Would start studio and run karpathy loop")
        return

    try:
        from lightning_sdk import Studio, Machine
    except ImportError:
        print("Installing lightning_sdk...")
        os.system("pip install lightning-sdk -q")
        from lightning_sdk import Studio, Machine

    # Get or create studio
    print(f"Connecting to studio '{acct['studio_name']}'...")
    try:
        studio = Studio(
            name=acct["studio_name"],
            teamspace=acct["teamspace"],
            user=acct["user"],
        )
        print(f"Studio found: {studio.name}")
    except Exception:
        print(f"Creating new studio '{acct['studio_name']}'...")
        studio = Studio.create(
            name=acct["studio_name"],
            teamspace=acct["teamspace"],
        )
        print(f"Studio created: {studio.name}")

    # Start with T4 GPU (cheapest)
    print("Starting T4 GPU...")
    studio.start(machine=Machine.T4)
    print("GPU started!")

    # Upload the karpathy loop script
    karpathy_script = _ROOT / "scripts" / "lightning" / "nba_karpathy_lightning.py"
    if karpathy_script.exists():
        studio.upload_file(str(karpathy_script), remote_path="nba_karpathy_lightning.py")
        print("Uploaded karpathy script")

    # Run the loop with timeout
    timeout_sec = int(args.hours * 3600)
    cmd = (
        f"timeout {timeout_sec} python3 nba_karpathy_lightning.py "
        f"--iterations {args.iterations} "
        f"--max-hours {args.hours} "
        f"2>&1 | tee karpathy_output.log"
    )
    print(f"Running: {cmd}")
    print()

    try:
        output = studio.run(cmd)
        print(output)
    except Exception as e:
        print(f"Run error: {e}")
    finally:
        # Always stop to save credits
        print("\nStopping studio to save credits...")
        try:
            studio.stop()
            print("Studio stopped.")
        except Exception as e:
            print(f"Stop error: {e}")

    # Download results
    try:
        studio.download_file("karpathy_output.log", "logs/lightning-karpathy-output.log")
        studio.download_file("karpathy_state.json", "data/lightning-karpathy-state.json")
        print("Results downloaded.")
    except Exception:
        print("Could not download results (studio already stopped?)")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
