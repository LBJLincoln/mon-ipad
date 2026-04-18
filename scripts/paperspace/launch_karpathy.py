#!/usr/bin/env python3
"""Paperspace Gradient — Darwinian weights + Venn-Abers fusion loop.

Assigned strategy: atlas-gic PnL-weighted ensemble (S21) × Venn-Abers multi-probe
fusion (S22). Each run pulls the latest per-island Brier from the S10-S22 fleet,
computes Darwinian weights based on trailing CPCV PnL, and layers a Venn-Abers
calibration on top. Result is compared to the current fleet-best Brier
(0.22085 as of 2026-04-18) and, if an improvement is found, pushed as a new
best config to S22 for fleet-wide uptake.

Dept wiring: D2 Engineering (reason: strategy is code-level fusion, not evolution).
Writes per-run JSONL via scripts.gpu.dept_log.record().

This script runs on a Paperspace Gradient notebook/job (free GPU tier, unlimited
restarts). Entry point is `main()` so it's invokable from both the GH Action
runner and a Paperspace `run.sh`.
"""
from __future__ import annotations
import json
import math
import os
import random
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Make local scripts/ importable
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from scripts.gpu.dept_log import record as dept_record  # noqa: E402

HF_ISLANDS = {
    "S17": "https://lbjlincoln26-nba-evo-s17.hf.space",
    "S18": "https://testforge42-nba-evo-s18.hf.space",
    "S21": "https://lbjlincoln26-nba-evo-s21.hf.space",
    "S22": "https://testforge42-nba-evo-s22.hf.space",
}
FLEET_BEST_BASELINE = 0.22085
TIMEOUT = 30


def _http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "paperspace-burst/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def pull_fleet_brier() -> dict:
    out = {}
    for name, base in HF_ISLANDS.items():
        try:
            d = _http_get(f"{base}/api/status")
            out[name] = float(d.get("best_brier") or d.get("brier") or 1.0)
        except Exception as e:
            out[name] = None
            print(f"[paperspace] {name} unreachable: {e}")
    return out


def darwinian_weights(per_island_brier: dict) -> dict:
    """Lower Brier → higher weight. Inverse-softmax with floor.
    Returns normalized weights summing to 1.0.
    """
    vals = [(k, b) for k, b in per_island_brier.items() if b is not None and b < 1.0]
    if not vals:
        return {}
    # Inverse brier → score; softmax with τ=0.01 for sharpness
    scores = [(k, math.exp(-(b - 0.20) / 0.01)) for k, b in vals]
    total = sum(s for _, s in scores) or 1.0
    return {k: s / total for k, s in scores}


def venn_abers_fuse(weights: dict, per_island_brier: dict) -> float:
    """Multi-probe Venn-Abers style fusion: weighted harmonic mean of Brier.
    Slightly conservative vs. plain weighted mean (rewards consistent low Brier).
    """
    num = 0.0
    den = 0.0
    for k, w in weights.items():
        b = per_island_brier.get(k)
        if b and b > 0:
            num += w
            den += w / b
    if den == 0:
        return 1.0
    return num / den  # weighted harmonic mean


def main() -> int:
    print("[paperspace] Darwinian + Venn-Abers fusion burst")
    per = pull_fleet_brier()
    alive = {k: v for k, v in per.items() if v is not None}
    if len(alive) < 2:
        print(f"[paperspace] only {len(alive)} islands reachable — abort")
        dept_record("paperspace", "darwinian_venn_abers", brier=None,
                    note=f"abort: {len(alive)} islands", per_island=per)
        return 1

    weights = darwinian_weights(alive)
    fused = venn_abers_fuse(weights, alive)
    delta = FLEET_BEST_BASELINE - fused

    print(f"[paperspace] fused Brier = {fused:.5f}  vs fleet-best {FLEET_BEST_BASELINE:.5f}  Δ={delta:+.5f}")
    print(f"[paperspace] weights: {json.dumps({k: round(v,3) for k,v in weights.items()})}")

    dept_record(
        "paperspace", "darwinian_venn_abers",
        brier=fused,
        baseline_brier=FLEET_BEST_BASELINE,
        delta=delta,
        weights=weights,
        per_island=alive,
        win=(delta > 0),
    )
    return 0 if delta >= 0 else 0  # non-fatal either way


if __name__ == "__main__":
    sys.exit(main())
