#!/usr/bin/env python3
"""
Lightning.ai Karpathy-Loop Launcher
====================================
Thin CLI wrapper around scripts/gpu-burst/lightning-burst.py that selects the
NBA or Political burst mode via --project and invokes the evolution loop.

Designed to run inside a GitHub Actions job. The Lightning credentials
(LIGHTNING_USER_ID, LIGHTNING_API_KEY) are read from the environment and
written to ~/.lightning/credentials so the Lightning SDK (if installed) can
authenticate. The actual GPU work executes on Lightning AI infrastructure
when the burst script detects /teamspace/studios/this_studio, otherwise
falls back to CPU inside the runner (still useful as a smoke test).

Usage:
    python scripts/lightning/launch_karpathy.py --project nba
    python scripts/lightning/launch_karpathy.py --project political --duration 600

Environment (GitHub Actions secrets):
    LIGHTNING_USER_ID     -- required for Lightning CLI auth
    LIGHTNING_API_KEY     -- required for Lightning CLI auth
    HF_TOKEN              -- needed to clone feature engine
    GITHUB_TOKEN          -- needed to push results back
    TELEGRAM_BOT_TOKEN    -- optional, for alerts
    ADMIN_TELEGRAM_ID     -- optional, for alerts
    DATABASE_URL          -- optional, fallback data source
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BURST_SCRIPT_DIR = REPO_ROOT / "scripts" / "gpu-burst"


def _write_lightning_credentials() -> None:
    """Persist Lightning creds to ~/.lightning/credentials if both env vars set."""
    user_id = os.environ.get("LIGHTNING_USER_ID", "").strip()
    api_key = os.environ.get("LIGHTNING_API_KEY", "").strip()
    if not user_id or not api_key:
        print("[launch_karpathy] WARNING: LIGHTNING_USER_ID / LIGHTNING_API_KEY "
              "not set -- Lightning cloud dispatch disabled, will run locally.")
        return

    cred_dir = Path.home() / ".lightning"
    cred_dir.mkdir(parents=True, exist_ok=True)
    cred_file = cred_dir / "credentials"
    cred_file.write_text(
        f"[DEFAULT]\nusername = {user_id}\napi_key = {api_key}\n"
    )
    try:
        cred_file.chmod(0o600)
    except Exception:
        pass
    print(f"[launch_karpathy] Lightning credentials written to {cred_file}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Karpathy burst on Lightning AI")
    parser.add_argument(
        "--project",
        choices=["nba", "political"],
        required=True,
        help="Which workload to run",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=600,
        help="Max burst duration in seconds (default 600 = 10 min)",
    )
    args = parser.parse_args()

    _write_lightning_credentials()

    # Surface project selection to the burst script.
    os.environ["BURST_MODE"] = args.project

    # Make lightning-burst.py importable (its filename has a hyphen).
    sys.path.insert(0, str(BURST_SCRIPT_DIR))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "lightning_burst",
        BURST_SCRIPT_DIR / "lightning-burst.py",
    )
    if spec is None or spec.loader is None:
        print(f"[launch_karpathy] FATAL: cannot load lightning-burst.py "
              f"from {BURST_SCRIPT_DIR}")
        return 2
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Override burst duration without editing the original module.
    module.MAX_DURATION_SECONDS = int(args.duration)

    print(f"[launch_karpathy] project={args.project} duration={args.duration}s")
    result = module.run_burst()

    metric_label = "brier" if args.project == "nba" else "signal_accuracy"
    print(f"[launch_karpathy] Done. {metric_label}="
          f"{result.get('best_score', result.get('best_brier', '?'))} "
          f"iterations={result.get('iterations', '?')}")
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from gpu.dept_log import record as _dept_record
        score = result.get('best_brier') if args.project == 'nba' else result.get('best_score')
        _dept_record("lightning", f"karpathy_tree_{args.project}",
                     brier=float(score) if score is not None else None,
                     project=args.project,
                     iterations=result.get('iterations'),
                     duration_s=args.duration)
    except Exception as _e:
        print(f"[dept-log] lightning record failed: {_e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
