#!/usr/bin/env python3
"""
experiment_id_injector — Cycle 14 Tier 2.C2 (Hamilton UI lineage foundation)

Threads a short deterministic SHA through the 12 state files the pipeline
reads and writes, so that a losing bet, a council decision, an island
evolution step, and a PAV refit can all be joined back to a single
experiment_id.

The ID is derived from:
  feature_engine_version + engine_sha256 + date + source_basename + content_sha

Writing the field is **additive** — we never touch any other key. If the
field already exists with the expected value, we no-op (idempotent for
cron). If it exists with a different value (because a downstream tool
wrote its own), we preserve theirs.

Run manually:
    python3 scripts/lineage/experiment_id_injector.py
    python3 scripts/lineage/experiment_id_injector.py --dry
    python3 scripts/lineage/experiment_id_injector.py --refresh

Cron: every 4h aligned with autonomous-cycle.sh, see README.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/termius/mon-ipad")
ENGINE_LOCK = REPO / "engine.sha256.lock"
ENGINE_VERSION = "v3.1-54cat"  # keep in sync with CLAUDE.md

TARGETS: list[Path] = [
    REPO / "data/departments/council-research-latest.json",
    REPO / "data/departments/council-engineering-latest.json",
    REPO / "data/departments/council-evolution-latest.json",
    REPO / "data/departments/council-evaluation-latest.json",
    REPO / "data/departments/council-product-latest.json",
    REPO / "data/departments/council-business-latest.json",
    REPO / "data/departments/council-finance-latest.json",
    REPO / "data/departments/council-infra-latest.json",
    REPO / "data/departments/council-cross-repo-latest.json",
    REPO / "data/arena/agent-states-v5.json",
    REPO / "data/arena/cpcv-gated-strategies.json",
    REPO / "data/nba-agent/full-season-backtest.json",
]


def engine_hash_short() -> str:
    if not ENGINE_LOCK.exists():
        return "nolock"
    for line in ENGINE_LOCK.read_text().splitlines():
        if line.startswith("sha256 = "):
            return line.split("=", 1)[1].strip()[:12]
    return "nolock"


def compute_eid(path: Path, data: dict) -> str:
    """Stable short experiment id. 12-char SHA over:
    engine_version | engine_sha | yyyy-mm-dd | basename | json-sorted-content-sha.
    """
    content_bytes = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    content_sha = hashlib.sha256(content_bytes).hexdigest()[:16]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    basename = path.name
    raw = f"{ENGINE_VERSION}|{engine_hash_short()}|{today}|{basename}|{content_sha}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def inject(path: Path, refresh: bool, dry: bool) -> tuple[str, str]:
    """Returns (status, eid). Status in {SKIP, WROTE, REFRESH, KEPT, MISS}."""
    if not path.exists():
        return ("MISS", "")
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        return (f"ERR:{type(e).__name__}", "")
    if not isinstance(data, dict):
        return ("NOTDICT", "")
    existing = data.get("experiment_id")
    eid = compute_eid(path, {k: v for k, v in data.items() if k != "experiment_id"})
    if existing:
        if refresh and existing != eid:
            if not dry:
                data["experiment_id"] = eid
                data["experiment_id_refreshed_at"] = datetime.now(timezone.utc).isoformat()
                path.write_text(json.dumps(data, indent=2))
            return ("REFRESH", eid)
        return ("KEPT", existing)
    if dry:
        return ("WROTE*", eid)
    data["experiment_id"] = eid
    data["experiment_id_written_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2))
    return ("WROTE", eid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="compute but don't write")
    ap.add_argument("--refresh", action="store_true", help="recompute even if present")
    args = ap.parse_args()

    print(f"[lineage] engine={ENGINE_VERSION} sha={engine_hash_short()} "
          f"targets={len(TARGETS)} refresh={args.refresh} dry={args.dry}")

    for t in TARGETS:
        status, eid = inject(t, refresh=args.refresh, dry=args.dry)
        rel = t.relative_to(REPO) if t.is_relative_to(REPO) else t
        print(f"  {status:8s} {eid:12s}  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
