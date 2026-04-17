"""Canonical slot → hypothesis mapping for the Nomos42 GPU/CPU fleet.

Single source of truth for "what is each account/platform supposed to run?".
Every launcher (modal-burst, lightning-burst, zerogpu-burst, kaggle, colab)
should import this and log its results through log_slot_result() so the
fleet-matrix scoreboard stays consistent.

Usage from any launcher:
    from _fleet_slots import get_slot, log_slot_result

    slot = get_slot(os.environ.get("FLEET_SLOT", "G6"))  # default = Modal
    # ... train ...
    log_slot_result(slot["id"], brier=0.22041, gen=1142, walltime_s=287,
                    hypothesis=slot["hypothesis"])
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "data" / "fleet-matrix" / "hypothesis-registry.json"
METRICS_DIR = REPO_ROOT / "data" / "fleet-matrix"


def _load_registry() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"taken": {}, "open_hypotheses": []}
    with REGISTRY_PATH.open() as f:
        return json.load(f)


def get_slot(slot_id: str) -> Dict[str, Any]:
    """Return canonical config for a slot (G1-G8, P-G1-P-G4).

    Returns:
        {"id": "G6", "hypothesis": "...", "platform": "...", "status": "..."}
    Raises KeyError if slot_id is not in the registry.
    """
    reg = _load_registry()
    taken = reg.get("taken", {})
    if slot_id not in taken:
        raise KeyError(
            f"Unknown slot {slot_id!r}. Known: {sorted(taken.keys())}"
        )
    cfg = dict(taken[slot_id])
    cfg["id"] = slot_id
    return cfg


def list_slots(status: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """All slots, optionally filtered by status (active/ready/scheduled/etc.)."""
    reg = _load_registry()
    taken = reg.get("taken", {})
    if status is None:
        return {k: {**v, "id": k} for k, v in taken.items()}
    return {k: {**v, "id": k} for k, v in taken.items() if v.get("status") == status}


def open_hypotheses() -> list[str]:
    """Hypotheses not yet assigned to any slot — new accounts should pick from here."""
    reg = _load_registry()
    return list(reg.get("open_hypotheses", []))


def log_slot_result(
    slot_id: str,
    brier: float,
    gen: Optional[int] = None,
    walltime_s: Optional[float] = None,
    hypothesis: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Append a result line to data/fleet-matrix/<slot>/metrics.jsonl.

    Returns the metrics file path. Creates the slot dir on first write.
    Idempotent — safe to call multiple times per run.
    """
    slot_dir = METRICS_DIR / slot_id
    slot_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = slot_dir / "metrics.jsonl"
    last_file = slot_dir / "last.json"

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "slot": slot_id,
        "brier": round(float(brier), 5),
    }
    if gen is not None:
        record["gen"] = int(gen)
    if walltime_s is not None:
        record["walltime_s"] = round(float(walltime_s), 1)
    if hypothesis:
        record["hypothesis"] = hypothesis
    if extra:
        record["extra"] = extra

    with metrics_file.open("a") as f:
        f.write(json.dumps(record) + "\n")
    with last_file.open("w") as f:
        json.dump(record, f, indent=2)
    return metrics_file


def update_registry_brier(slot_id: str, brier: float) -> None:
    """Patch taken[slot_id].last_brier in registry. Safe concurrent — read/write."""
    if not REGISTRY_PATH.exists():
        return
    with REGISTRY_PATH.open() as f:
        reg = json.load(f)
    if slot_id in reg.get("taken", {}):
        reg["taken"][slot_id]["last_brier"] = round(float(brier), 5)
        reg["updated_at"] = datetime.now(timezone.utc).isoformat()
        with REGISTRY_PATH.open("w") as f:
            json.dump(reg, f, indent=2)


if __name__ == "__main__":
    # CLI: show fleet status
    reg = _load_registry()
    print(f"Registry updated: {reg.get('updated_at')}")
    print(f"Taken slots: {len(reg.get('taken', {}))}")
    for slot_id, cfg in sorted(reg.get("taken", {}).items()):
        brier = cfg.get("last_brier", "—")
        print(f"  {slot_id:<5} {cfg.get('platform', '?'):<20} {cfg.get('status', '?'):<30} brier={brier}  [{cfg.get('hypothesis', '?')}]")
    print(f"\nOpen hypotheses ({len(reg.get('open_hypotheses', []))}):")
    for h in reg.get("open_hypotheses", []):
        print(f"  - {h}")
