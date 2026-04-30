"""ITF ledger restore — runs in the Dockerfile CMD chain before uvicorn starts.

HF Space /app is wiped on every factory_reboot, so positions.json,
agent_bankrolls.json, fill_reconciliation_cursor.json and agent_ledger.jsonl
evaporate. executor.persist_ledgers_to_hub() uploads them at end-of-tick to
the ITF Space repo at data/intraday/*. This script runs at boot to pull them
back down into /app/data/intraday so the first tick after a restart starts
from the last persisted state instead of cold seed.

Silent by design: if any file is missing in the repo (first-ever boot), or
if the Hub is down, or if no token is wired, we exit 0 and let the app start
from empty. Failure here must never block startup — the executor treats
missing files as empty-state anyway.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


_FILES = [
    "data/intraday/positions.json",
    "data/intraday/agent_bankrolls.json",
    "data/intraday/fill_reconciliation_cursor.json",
    "data/intraday/agent_ledger.jsonl",
]


def _token() -> str:
    for k in ("HF_TOKEN_2", "HF_TOKEN_NBA", "HF_WRITE_TOKEN", "NOMOS_HF_TOKEN", "HF_TOKEN"):
        v = os.environ.get(k)
        if v:
            return v
    return ""


def main() -> int:
    repo_id = os.environ.get("SPACE_ID") or "LBJLincoln26/intraday-trading-floor"
    tok = _token()
    if not tok:
        print("[itf-restore] no HF token in env — skipping ledger restore",
              file=sys.stderr, flush=True)
        return 0
    try:
        from huggingface_hub import hf_hub_download
        from huggingface_hub.utils import (
            EntryNotFoundError,
            RepositoryNotFoundError,
        )
    except Exception as e:
        print(f"[itf-restore] huggingface_hub import failed: {e}",
              file=sys.stderr, flush=True)
        return 0

    root = Path("/app")
    (root / "data" / "intraday").mkdir(parents=True, exist_ok=True)

    restored = []
    missing = []
    errors = []
    for remote in _FILES:
        try:
            # Download into a temp HF cache then copy into /app/<remote>.
            src = hf_hub_download(
                repo_id=repo_id,
                filename=remote,
                repo_type="space",
                token=tok,
            )
            dst = root / remote
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Copy rather than symlink — symlinks into /tmp/hf-cache break
            # after the next Hub refresh and leave executor.py reading stale.
            dst.write_bytes(Path(src).read_bytes())
            restored.append(remote)
        except (EntryNotFoundError, RepositoryNotFoundError):
            missing.append(remote)
        except Exception as e:
            errors.append(f"{remote}: {str(e)[:200]}")

    print(f"[itf-restore] restored={len(restored)} missing={len(missing)} "
          f"errors={len(errors)} repo={repo_id}", file=sys.stderr, flush=True)
    if restored:
        print(f"[itf-restore]   files: {restored}", file=sys.stderr, flush=True)
    if errors:
        print(f"[itf-restore]   errors: {errors}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Belt-and-braces: don't ever let a restore failure block uvicorn.
        print(f"[itf-restore] unexpected: {e}", file=sys.stderr, flush=True)
        sys.exit(0)
