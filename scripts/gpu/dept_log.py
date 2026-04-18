"""Cross-platform GPU result logger — writes one JSONL line per run
to the assigned department's council feed. Used by Kaggle / Lightning /
Modal / ZeroGPU / Paperspace / Colab launchers.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
GPU_DIR = ROOT / "data" / "gpu"
DEPT_DIR = ROOT / "data" / "departments"

PLATFORM_DEPT = {
    "colab_a":     "evolution",
    "colab_b":     "evolution",
    "kaggle":      "research",
    "zerogpu":     "evaluation",
    "modal":       "evaluation",
    "lightning":   "evolution",
    "paperspace":  "engineering",
}


def record(platform: str, strategy: str, brier: Optional[float] = None, **extra) -> Path:
    """Append a run record. Returns the dept-log path written."""
    platform = platform.lower().strip()
    dept = PLATFORM_DEPT.get(platform, "research")
    ts = datetime.now(timezone.utc).isoformat()
    row = {
        "ts": ts,
        "platform": platform,
        "strategy": strategy,
        "dept": dept,
        "brier": brier,
        **extra,
    }
    # per-platform raw
    plat_dir = GPU_DIR / platform
    plat_dir.mkdir(parents=True, exist_ok=True)
    (plat_dir / "runs.jsonl").open("a").write(json.dumps(row, default=str) + "\n")
    # dept-council feed
    DEPT_DIR.mkdir(parents=True, exist_ok=True)
    dept_path = DEPT_DIR / f"gpu-results-{dept}.jsonl"
    dept_path.open("a").write(json.dumps(row, default=str) + "\n")
    return dept_path


if __name__ == "__main__":
    p = record("kaggle", "smoke-test", brier=0.22500, iteration=0, notes="dept-log smoke")
    print(f"wrote smoke record to {p}")
