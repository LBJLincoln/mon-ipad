#!/usr/bin/env python3
"""Fleet-matrix scoreboard aggregator.

Scans data/fleet-matrix/<slot>/metrics.jsonl (written by each GPU/CPU launcher
via scripts/gpu-burst/_fleet_slots.log_slot_result) and emits:

    data/fleet-matrix/scoreboard.json  — latest per-slot + global Pareto-best

Cron: */30 * * * * lightweight (reads JSONL, writes one JSON). No network.

Run locally:
    python3 scripts/fleet-matrix/aggregate.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_DIR = REPO_ROOT / "data" / "fleet-matrix"
REGISTRY_PATH = MATRIX_DIR / "hypothesis-registry.json"
SCOREBOARD_PATH = MATRIX_DIR / "scoreboard.json"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _slot_summary(slot_id: str, records: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Roll up a slot's metrics.jsonl into a single summary."""
    if not records:
        return {
            "slot": slot_id,
            "hypothesis": cfg.get("hypothesis"),
            "platform": cfg.get("platform"),
            "status": cfg.get("status"),
            "n_runs": 0,
            "last_brier": cfg.get("last_brier"),
            "best_brier": None,
            "last_ts": None,
        }
    last = records[-1]
    briers = [r["brier"] for r in records if isinstance(r.get("brier"), (int, float))]
    best = min(briers) if briers else None
    gens = [r["gen"] for r in records if isinstance(r.get("gen"), (int, float))]
    walltime_total = sum(r.get("walltime_s", 0) or 0 for r in records)
    return {
        "slot": slot_id,
        "hypothesis": cfg.get("hypothesis"),
        "platform": cfg.get("platform"),
        "status": cfg.get("status"),
        "n_runs": len(records),
        "last_brier": round(last.get("brier"), 5) if last.get("brier") is not None else None,
        "best_brier": round(best, 5) if best is not None else None,
        "last_gen": gens[-1] if gens else None,
        "walltime_s_total": round(walltime_total, 1),
        "last_ts": last.get("ts"),
    }


def aggregate() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"error": "no registry", "generated_at": datetime.now(timezone.utc).isoformat()}
    with REGISTRY_PATH.open() as f:
        registry = json.load(f)

    taken = registry.get("taken", {})
    slots_summary = {}
    for slot_id, cfg in taken.items():
        metrics_file = MATRIX_DIR / slot_id / "metrics.jsonl"
        records = _read_jsonl(metrics_file)
        slots_summary[slot_id] = _slot_summary(slot_id, records, cfg)

    # Global Pareto-best: lowest best_brier across all slots with a measurement.
    scored = [s for s in slots_summary.values() if s.get("best_brier") is not None]
    scored.sort(key=lambda s: s["best_brier"])
    global_best = scored[0] if scored else None

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "global_best": global_best,
        "n_slots_tracked": len(taken),
        "n_slots_measured": len(scored),
        "slots": slots_summary,
    }


def main() -> None:
    board = aggregate()
    MATRIX_DIR.mkdir(parents=True, exist_ok=True)
    with SCOREBOARD_PATH.open("w") as f:
        json.dump(board, f, indent=2, sort_keys=True)
    gb = board.get("global_best")
    if gb:
        print(f"[fleet-matrix] updated — best={gb.get('best_brier')} [{gb.get('slot')}/{gb.get('hypothesis')}] measured={board.get('n_slots_measured')}/{board.get('n_slots_tracked')}")
    else:
        print(f"[fleet-matrix] updated — no slot has reported a brier yet ({board.get('n_slots_tracked')} slots registered)")


if __name__ == "__main__":
    main()
