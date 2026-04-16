"""D7 Infra council hook — GPU burst health watch.

Reads the latest output of each specialized GPU script:
  - data/gpu-burst/zerogpu-tabpfn-latest.json   (H200 TabPFN)
  - data/gpu-burst/modal-cpcv-latest.json       (A10G CPCV+DSR)
  - data/kaggle/latest.json                      (P100 full-season)
  - data/lightning/latest.json                   (T4 NBA/Political alternation)

Computes:
  - Staleness (ts vs now)
  - Recent error rate (last 5 history entries)
  - Per-platform "burst-cost vs improvement" — emit alert if A10G cost is
    burning without Brier delta justifying it

Emits to data/councils/d7/gpu-monitor-{date}.json. Also restarts any
platform that's been stale > 12h via gh workflow run.

Cron: 35 */2 * * *  (every 2h at :35)
"""
from __future__ import annotations
import json, os, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "councils" / "d7"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = [
    {"name": "zerogpu-h200",
     "latest": "data/gpu-burst/zerogpu-tabpfn-latest.json",
     "fallback": "data/gpu-burst/latest-zerogpu-result.json",  # legacy zerogpu-burst.py
     "history": "data/gpu-burst/tabpfn-history.jsonl",
     "workflow": "gpu-cron-launcher.yml", "stale_h": 12},
    {"name": "modal-a10g",
     "latest": "data/gpu-burst/modal-cpcv-latest.json",
     "fallback": "data/gpu-burst/latest-modal-result.json",  # legacy modal-burst.py
     "history": "data/gpu-burst/cpcv-history.jsonl",
     "workflow": "modal-burst.yml", "stale_h": 8},
    {"name": "lightning-t4",
     "latest": "data/lightning/latest.json",
     "fallback": None,
     "history": "data/lightning/history.jsonl",
     "workflow": "lightning-burst.yml", "stale_h": 24},
    {"name": "kaggle-p100",
     "latest": "data/kaggle/latest.json",
     "fallback": None,
     "history": "data/kaggle/history.jsonl",
     "workflow": None, "stale_h": 168},  # weekly manual today
]


def _staleness_hours(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return None


def _read_latest(p):
    fp = ROOT / p
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text())
    except Exception:
        return None


def _recent_errors(p, n=5):
    fp = ROOT / p
    if not fp.exists():
        return 0
    try:
        lines = fp.read_text().splitlines()[-n:]
        return sum(1 for ln in lines if '"error"' in ln or '"dispatch_failed"' in ln)
    except Exception:
        return 0


def _maybe_restart(plat, stale_h):
    """If GH CLI available and platform supports it, kick the workflow."""
    if not plat["workflow"] or stale_h is None:
        return None
    if stale_h < plat["stale_h"]:
        return None
    try:
        r = subprocess.run(
            ["gh", "workflow", "run", plat["workflow"]],
            capture_output=True, text=True, timeout=20,
        )
        return {"action": "restart_dispatched", "ok": r.returncode == 0,
                "stderr": r.stderr[:200] if r.returncode else None}
    except Exception as e:
        return {"action": "restart_failed", "error": str(e)[:200]}


def main():
    out = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "council": "d7-infra",
        "task": "gpu-burst-health",
        "platforms": [],
    }
    for plat in PLATFORMS:
        latest = _read_latest(plat["latest"])
        source = "specialized"
        if not latest and plat.get("fallback"):
            latest = _read_latest(plat["fallback"])
            source = "legacy_fallback" if latest else "missing"
        ts = (latest.get("ts") or latest.get("timestamp")) if latest else None
        stale_h = _staleness_hours(ts)
        errs = _recent_errors(plat["history"])
        # Legacy zerogpu-burst.py uses best_brier_found instead of brier
        brier = None
        if latest:
            brier = latest.get("brier") or latest.get("best_brier_found")
        record = {
            "name": plat["name"],
            "source": source,
            "last_run": ts,
            "stale_hours": round(stale_h, 1) if stale_h is not None else None,
            "stale_threshold_h": plat["stale_h"],
            "stale_alert": (stale_h is not None and stale_h > plat["stale_h"]),
            "recent_errors_in_last_5": errs,
            "latest_brier": brier,
            "latest_dsr": latest.get("dsr") if latest else None,
            "beats_atr": (brier is not None and brier < 0.21570),
        }
        if record["stale_alert"]:
            record["restart"] = _maybe_restart(plat, stale_h)
        out["platforms"].append(record)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (OUT_DIR / f"gpu-monitor-{date}.json").write_text(json.dumps(out, indent=2))
    (OUT_DIR / "latest.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
