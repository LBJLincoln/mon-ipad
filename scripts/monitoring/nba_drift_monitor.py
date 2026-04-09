#!/usr/bin/env python3
"""
Nomos42 NBA drift monitor — Cycle 14 Tier 1.4

Four drift signals in one pass, reading the full-season backtest output
and writing four JSON files the dashboard + auto-PAV refit trigger can poll.

Signals:
  1. CONCEPT DRIFT — Frouros DDM on the per-trade (model_prob, won) stream.
     Falls back to a stdlib DDM implementation if frouros isn't installed.
  2. CALIBRATION DRIFT — CUSUM (arXiv:2510.25573 "Monitoring the calibration
     of probability forecasts with an application to concept drift detection",
     Oct 2025). S_t = (p - y)^2 - baseline_brier; C_t = max(0, C_{t-1} + S_t - k).
     Alert at C_t > h for 3 consecutive checks.
  3. DATA DRIFT — PSI on the p_hat distribution versus a reference window
     (first 200 trades of the season). Yellow > 0.10, red > 0.20.
  4. LABEL DRIFT — home-win rate z-score vs the season baseline. Flags
     referee / schedule anomalies.

Auto-recalibration hook: when rolling 50-trade ECE > 0.03 (Wilkens 2023,
arXiv:2303.06021), drift-summary.json emits {"recalibration_needed": true}.
A separate cron (Tier 1.5) polls this flag and triggers the PAV refit.

Input:  data/nba-agent/full-season-backtest.json
Output: data/monitoring/drift-{concept,calibration,data,summary}.json

Cron: */30 * * * * ≈ 8 seconds, 35 MB RAM.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO = Path(__file__).resolve().parent.parent.parent
IN_BACKTEST = REPO / "data" / "nba-agent" / "full-season-backtest.json"
OUT_DIR = REPO / "data" / "monitoring"
OUT_CONCEPT = OUT_DIR / "drift-concept.json"
OUT_CALIBRATION = OUT_DIR / "drift-calibration.json"
OUT_DATA = OUT_DIR / "drift-data.json"
OUT_SUMMARY = OUT_DIR / "drift-summary.json"

# ────────────────────────── thresholds (paper-sourced) ──────────────────────────
REFERENCE_N = 200           # first N trades define the reference distribution
CUSUM_K = 0.005             # drift magnitude (Brier units); see arXiv:2510.25573
CUSUM_H = 0.05              # alert threshold
CUSUM_CONSECUTIVE = 3       # consecutive checks above H before firing
PSI_YELLOW = 0.10           # Siddiqi (2006) default
PSI_RED = 0.20
ECE_RECAL_TRIGGER = 0.03    # Wilkens 2023 / arXiv:2303.06021 for NBA
ECE_WINDOW = 50             # rolling window (trades) for ECE
HOMEWIN_Z_RED = 2.0         # sigma for home-win label drift


# ────────────────────────── helpers ──────────────────────────
def load_trades() -> list[dict[str, Any]]:
    if not IN_BACKTEST.exists():
        return []
    try:
        data = json.loads(IN_BACKTEST.read_text())
    except Exception:
        return []
    trades = data.get("trades") or []
    out: list[dict[str, Any]] = []
    for t in trades:
        p = t.get("model_prob")
        w = t.get("won")
        if p is None or w is None:
            continue
        out.append({
            "date": t.get("date", ""),
            "p": float(p),
            "y": 1 if w else 0,
        })
    return out


def psi(expected: list[float], actual: list[float], bins: int = 10) -> float:
    """Population Stability Index — Siddiqi 2006. Returns 0.0 when empty."""
    if not expected or not actual:
        return 0.0
    edges = [i / bins for i in range(bins + 1)]
    exp_counts = [0] * bins
    act_counts = [0] * bins
    for v in expected:
        idx = min(int(v * bins), bins - 1)
        exp_counts[idx] += 1
    for v in actual:
        idx = min(int(v * bins), bins - 1)
        act_counts[idx] += 1
    total_e = max(sum(exp_counts), 1)
    total_a = max(sum(act_counts), 1)
    total = 0.0
    for e, a in zip(exp_counts, act_counts):
        pe = max(e / total_e, 1e-6)
        pa = max(a / total_a, 1e-6)
        total += (pa - pe) * math.log(pa / pe)
    return total


def ece(probs: list[float], labels: list[int], bins: int = 10) -> float:
    """Expected Calibration Error — uniform-width binning."""
    if not probs:
        return 0.0
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, y in zip(probs, labels):
        idx = min(int(p * bins), bins - 1)
        buckets[idx].append((p, y))
    total = 0.0
    n = len(probs)
    for b in buckets:
        if not b:
            continue
        avg_p = sum(p for p, _ in b) / len(b)
        avg_y = sum(y for _, y in b) / len(b)
        total += (len(b) / n) * abs(avg_p - avg_y)
    return total


def brier(probs: list[float], labels: list[int]) -> float:
    if not probs:
        return 0.0
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


# ────────────────────────── drift detectors ──────────────────────────
def ddm_concept(errors: list[float]) -> dict[str, Any]:
    """Frouros-style DDM. Falls back to a 40-line stdlib impl if frouros absent.

    DDM tracks running mean + stdev of the error stream and raises:
      - warning when e + s >= e_min + 2*s_min
      - drift   when e + s >= e_min + 3*s_min
    """
    try:
        import numpy as np  # noqa: F401
        from frouros.detectors.concept_drift import DDM, DDMConfig  # type: ignore
        detector = DDM(config=DDMConfig(warning_level=2.0, drift_level=3.0, min_num_instances=30))
        state = "STABLE"
        idx_alert = None
        for i, err in enumerate(errors):
            detector.update(value=err)
            status = detector.status
            if status and status.get("drift"):
                state = "DRIFT"
                idx_alert = i
                break
            if status and status.get("warning"):
                state = "WARNING"
        return {
            "detector": "frouros.DDM",
            "state": state,
            "alert_index": idx_alert,
            "n": len(errors),
        }
    except Exception:
        pass
    # Fallback pure-python DDM
    n = 0
    p_sum = 0.0
    p_min = float("inf")
    s_min = float("inf")
    state = "STABLE"
    idx_alert = None
    for i, err in enumerate(errors):
        n += 1
        p_sum += err
        p = p_sum / n
        if n < 30:
            continue
        s = math.sqrt(p * (1 - p) / n)
        if p + s < p_min + s_min:
            p_min = p
            s_min = s
        if p + s >= p_min + 3 * s_min:
            state = "DRIFT"
            idx_alert = i
            break
        elif p + s >= p_min + 2 * s_min:
            state = "WARNING"
    return {
        "detector": "fallback.DDM",
        "state": state,
        "alert_index": idx_alert,
        "n": len(errors),
    }


def cusum_calibration(probs: list[float], labels: list[int]) -> dict[str, Any]:
    """arXiv:2510.25573 CUSUM on calibration residuals.

    baseline Brier = mean over reference window;
    S_t = (p-y)^2 - baseline; C_t = max(0, C_{t-1} + S_t - k).
    Alert when C_t > h for CUSUM_CONSECUTIVE consecutive trades.
    """
    if len(probs) < REFERENCE_N:
        return {"state": "INSUFFICIENT", "cusum": 0.0, "baseline_brier": 0.0, "n": len(probs)}
    baseline = brier(probs[:REFERENCE_N], labels[:REFERENCE_N])
    c = 0.0
    consecutive = 0
    state = "STABLE"
    fire_index = None
    peak = 0.0
    for i in range(REFERENCE_N, len(probs)):
        s = (probs[i] - labels[i]) ** 2 - baseline
        c = max(0.0, c + s - CUSUM_K)
        peak = max(peak, c)
        if c > CUSUM_H:
            consecutive += 1
            if consecutive >= CUSUM_CONSECUTIVE and state != "DRIFT":
                state = "DRIFT"
                fire_index = i
        else:
            consecutive = 0
    return {
        "state": state,
        "cusum": round(c, 6),
        "peak_cusum": round(peak, 6),
        "baseline_brier": round(baseline, 6),
        "fire_index": fire_index,
        "k": CUSUM_K,
        "h": CUSUM_H,
        "n": len(probs),
    }


def rolling_ece(probs: list[float], labels: list[int], window: int = ECE_WINDOW) -> dict[str, Any]:
    if len(probs) < window:
        return {"ece": None, "window": window, "n": len(probs), "recal_needed": False}
    tail_p = probs[-window:]
    tail_y = labels[-window:]
    e = ece(tail_p, tail_y, bins=10)
    return {
        "ece": round(e, 5),
        "window": window,
        "n": len(probs),
        "recal_needed": e > ECE_RECAL_TRIGGER,
        "trigger": ECE_RECAL_TRIGGER,
    }


def pop_stability(probs: list[float]) -> dict[str, Any]:
    if len(probs) < 2 * REFERENCE_N:
        return {"psi": 0.0, "state": "INSUFFICIENT", "n": len(probs)}
    ref = probs[:REFERENCE_N]
    cur = probs[-REFERENCE_N:]
    val = psi(ref, cur)
    if val > PSI_RED:
        state = "DRIFT"
    elif val > PSI_YELLOW:
        state = "WARNING"
    else:
        state = "STABLE"
    return {
        "psi": round(val, 5),
        "state": state,
        "yellow": PSI_YELLOW,
        "red": PSI_RED,
        "n_ref": REFERENCE_N,
        "n_cur": REFERENCE_N,
    }


def label_z(labels: list[int]) -> dict[str, Any]:
    """Home-win rate z-score. Trade labels are 'bet won', not pure home-wins,
    but the bet side is almost always the home team for model_pick strategy,
    so the drift signal is still meaningful as a coarse label-distribution check.
    """
    if len(labels) < 2 * REFERENCE_N:
        return {"z": 0.0, "state": "INSUFFICIENT", "n": len(labels)}
    ref = labels[:REFERENCE_N]
    cur = labels[-REFERENCE_N:]
    p_ref = mean(ref)
    p_cur = mean(cur)
    se = math.sqrt(p_ref * (1 - p_ref) / REFERENCE_N) if 0 < p_ref < 1 else 1.0
    z = (p_cur - p_ref) / se if se > 0 else 0.0
    return {
        "z": round(z, 3),
        "p_ref": round(p_ref, 4),
        "p_cur": round(p_cur, 4),
        "state": "DRIFT" if abs(z) > HOMEWIN_Z_RED else "STABLE",
        "threshold": HOMEWIN_Z_RED,
    }


# ────────────────────────── main ──────────────────────────
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    trades = load_trades()
    probs = [t["p"] for t in trades]
    labels = [t["y"] for t in trades]
    errors = [(p - y) ** 2 for p, y in zip(probs, labels)]

    if not trades:
        summary = {
            "generated_at": ts,
            "state": "INSUFFICIENT",
            "reason": "no trades found in full-season-backtest.json",
            "recalibration_needed": False,
            "signals": {},
        }
        OUT_SUMMARY.write_text(json.dumps(summary, indent=2))
        print("[drift] no trades — nothing to do")
        return 0

    concept = ddm_concept(errors)
    calib = cusum_calibration(probs, labels)
    data_drift = pop_stability(probs)
    lab_drift = label_z(labels)
    roll_ece = rolling_ece(probs, labels)

    OUT_CONCEPT.write_text(json.dumps({"generated_at": ts, **concept}, indent=2))
    OUT_CALIBRATION.write_text(json.dumps({
        "generated_at": ts,
        "cusum": calib,
        "rolling_ece": roll_ece,
    }, indent=2))
    OUT_DATA.write_text(json.dumps({
        "generated_at": ts,
        "psi": data_drift,
        "label": lab_drift,
    }, indent=2))

    # Overall state = worst of the 4 signals
    states = [concept["state"], calib["state"], data_drift["state"], lab_drift["state"]]
    if "DRIFT" in states:
        overall = "DRIFT"
    elif "WARNING" in states:
        overall = "WARNING"
    elif any(s == "INSUFFICIENT" for s in states):
        overall = "PARTIAL"
    else:
        overall = "STABLE"

    summary = {
        "generated_at": ts,
        "state": overall,
        "recalibration_needed": bool(roll_ece.get("recal_needed", False)),
        "signals": {
            "concept": concept["state"],
            "calibration": calib["state"],
            "data": data_drift["state"],
            "label": lab_drift["state"],
        },
        "metrics": {
            "trades": len(trades),
            "baseline_brier": calib.get("baseline_brier"),
            "cusum_peak": calib.get("peak_cusum"),
            "psi": data_drift.get("psi"),
            "label_z": lab_drift.get("z"),
            "rolling_ece": roll_ece.get("ece"),
            "rolling_ece_window": ECE_WINDOW,
            "recal_trigger_ece": ECE_RECAL_TRIGGER,
        },
        "sources": {
            "backtest": str(IN_BACKTEST.relative_to(REPO)),
            "papers": [
                "arXiv:2510.25573 (CUSUM calibration drift)",
                "arXiv:2303.06021 (Wilkens NBA calibration)",
            ],
        },
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2))

    print(f"[drift] state={overall} trades={len(trades)} "
          f"ece={roll_ece.get('ece')} psi={data_drift.get('psi')} "
          f"cusum={calib.get('peak_cusum')} recal={summary['recalibration_needed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
