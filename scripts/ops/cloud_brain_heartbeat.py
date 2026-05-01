#!/usr/bin/env python3
"""Cloud Brain heartbeat — alarm if the Anthropic-hosted brain stops firing.

Per CLAUDE.md the cloud brain is supposed to publish health-status.json
every 4h via trigger trig_01BS3ixBvt2uKHY9p5EemcgD. Empirically (2026-05-01)
the trigger fires far less than declared; the VM muscle then runs on stale
recommendations, which is silent and dangerous.

This script:
  1. Reads health-status.json mtime + parsed `timestamp` field.
  2. Reports `OK` (<6h), `WARN` (6h-24h), or `DEAD` (>24h).
  3. Writes data/ops/cloud-brain-heartbeat.json with full diagnostic.
  4. Exits non-zero on DEAD so a wrapping cron can alert (Telegram / log).

Cron suggestion: 33 * * * *  (every hour at :33)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HEALTH = REPO / "health-status.json"
OUT = REPO / "data" / "ops" / "cloud-brain-heartbeat.json"

WARN_HOURS = 6
DEAD_HOURS = 24


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def main() -> int:
    now = _now()
    if not HEALTH.exists():
        status = "DEAD"
        age_hours = None
        published_ts = None
        reason = "health-status.json missing entirely"
    else:
        mtime = dt.datetime.fromtimestamp(HEALTH.stat().st_mtime, tz=dt.timezone.utc)
        age_hours = (now - mtime).total_seconds() / 3600
        published_ts = None
        try:
            d = json.loads(HEALTH.read_text())
            published_ts = d.get("timestamp")
        except Exception:
            pass
        if age_hours < WARN_HOURS:
            status = "OK"; reason = "fresh"
        elif age_hours < DEAD_HOURS:
            status = "WARN"; reason = f"published {age_hours:.1f}h ago — past {WARN_HOURS}h threshold"
        else:
            status = "DEAD"; reason = f"published {age_hours:.1f}h ago — likely trigger paused/failed"

    payload = {
        "checked_at": now.isoformat(),
        "status": status,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "file_mtime": (
            dt.datetime.fromtimestamp(HEALTH.stat().st_mtime, tz=dt.timezone.utc).isoformat()
            if HEALTH.exists() else None
        ),
        "published_timestamp": published_ts,
        "reason": reason,
        "trigger_id": "trig_01BS3ixBvt2uKHY9p5EemcgD",
        "expected_cadence_hours": 4,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))

    print(f"cloud-brain heartbeat: {status} — {reason}")
    return 0 if status == "OK" else (1 if status == "WARN" else 2)


if __name__ == "__main__":
    sys.exit(main())
