#!/usr/bin/env python3
"""
Post-hoc Platt Scaling Calibration for NBA Predictions
=====================================================
Applies a pre-fitted calibration map to raw model probabilities.
Runs on VM (no ML training needed — just lookup/interpolation).

Calibration map is derived from historical predictions vs outcomes.
Updated periodically from HF space evaluation results.

D5 Audit findings (2026-03-31):
  - Raw ECE: 0.2758  (target < 0.05)
  - 60-70% bucket: only 16.7% actual win rate (catastrophic over-confidence)
  - Calibration is the #1 driver of -2.6% ROI on live betting

Usage:
  # Apply calibration to a predictions file:
  python3 scripts/calibration.py --apply data/nba-agent/predictions-today.json

  # Bootstrap calibration map from Supabase history:
  python3 scripts/calibration.py --bootstrap

  # Run full evaluation report:
  python3 scripts/calibration.py --report

  # Import as a module:
  from scripts.calibration import IsotonicCalibration
  cal = IsotonicCalibration()
  calibrated_prob = cal.calibrate(raw_prob)
"""

import json
import math
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime


# ═══════════════════════════════════════
# PATHS
# ═══════════════════════════════════════

BASE_DIR = Path("/home/lahargnedebartoli/mon-ipad")
CAL_MAP_PATH = BASE_DIR / "data" / "calibration" / "calibration-map.json"
CAL_REPORT_PATH = BASE_DIR / "data" / "calibration" / "calibration-report.json"
PREDICTIONS_PATH = BASE_DIR / "data" / "nba-agent" / "predictions-today.json"
PICKS_PATH = BASE_DIR / "data" / "nba-agent" / "latest-picks.json"
EVAL_HISTORY_PATH = BASE_DIR / "data" / "nba-agent" / "eval-history.jsonl"


# ═══════════════════════════════════════
# SECTION 1: IsotonicCalibration class
# ═══════════════════════════════════════

class IsotonicCalibration:
    """
    Applies a pre-fitted calibration map to raw model probabilities.

    The calibration map is a piecewise-linear interpolation between bin centers.
    This is equivalent to isotonic regression applied post-hoc — no ML training
    required on the VM.

    Design constraints:
      - Zero ML dependencies (no sklearn, scipy, numpy required)
      - Pure Python stdlib only
      - Sub-millisecond per prediction
      - Safe with NaN, 0.0, 1.0 edge cases
    """

    def __init__(self, map_path: Path = CAL_MAP_PATH):
        self.map_path = map_path
        self.bin_edges = []
        self.raw_centers = []
        self.calibrated_centers = []
        self.meta = {}
        self._loaded = False
        self._load()

    def _load(self):
        """Load calibration map from JSON. Falls back to identity if missing."""
        if not self.map_path.exists():
            print(f"[calibration] WARNING: map not found at {self.map_path}, using identity")
            self._use_identity()
            return

        try:
            data = json.loads(self.map_path.read_text())
            self.bin_edges = data["bin_edges"]
            self.raw_centers = data["raw_centers"]
            self.calibrated_centers = data["calibrated_centers"]
            self.meta = data.get("_meta", {})
            self._loaded = True

            # Validate
            n_bins = len(self.bin_edges) - 1
            if len(self.calibrated_centers) != n_bins:
                raise ValueError(
                    f"calibrated_centers length {len(self.calibrated_centers)} "
                    f"!= n_bins {n_bins}"
                )
            if len(self.raw_centers) != n_bins:
                raise ValueError(
                    f"raw_centers length {len(self.raw_centers)} != n_bins {n_bins}"
                )

            print(
                f"[calibration] Loaded map v{self.meta.get('version','?')} "
                f"({n_bins} bins, ECE_before={self.meta.get('ece_before','?')})"
            )

        except Exception as e:
            print(f"[calibration] ERROR loading map: {e} — using identity")
            self._use_identity()

    def _use_identity(self):
        """Identity calibration: output = input (no correction)."""
        self.bin_edges = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        n = 10
        self.raw_centers = [round((i + 0.5) / n, 3) for i in range(n)]
        self.calibrated_centers = self.raw_centers[:]
        self._loaded = False

    def _find_bin(self, p: float) -> int:
        """Return index i such that bin_edges[i] <= p < bin_edges[i+1]."""
        for i in range(len(self.bin_edges) - 1):
            if self.bin_edges[i] <= p < self.bin_edges[i + 1]:
                return i
        # p == 1.0 falls into last bin
        return len(self.bin_edges) - 2

    def calibrate(self, raw_prob: float) -> float:
        """
        Apply calibration to a single raw probability.

        Uses piecewise-linear interpolation between calibrated bin centers.
        The interpolation ensures smooth output (not a step function).

        Args:
            raw_prob: Raw model probability in [0, 1]. NaN → 0.5 (no opinion).

        Returns:
            Calibrated probability in [0, 1].
        """
        # Handle edge cases
        if raw_prob is None or (isinstance(raw_prob, float) and math.isnan(raw_prob)):
            return 0.5
        p = float(raw_prob)
        p = max(0.0, min(1.0, p))  # clamp to [0,1]

        # Edge values
        if p == 0.0:
            return 0.0
        if p == 1.0:
            return 1.0

        # Find bin
        i = self._find_bin(p)
        raw_c = self.raw_centers[i]
        cal_c = self.calibrated_centers[i]

        # For piecewise-linear interpolation, find neighboring bin center
        # Interpolate between current bin center and the next/prev center
        # based on which side of the bin center we're on.
        if p < raw_c:
            # Interpolate between bin i-1 center and bin i center
            if i == 0:
                # First bin: interpolate between 0.0 and center
                t = p / raw_c if raw_c > 0 else 0.5
                cal_low = 0.0
                cal_high = cal_c
            else:
                raw_prev = self.raw_centers[i - 1]
                cal_prev = self.calibrated_centers[i - 1]
                span = raw_c - raw_prev
                t = (p - raw_prev) / span if span > 0 else 0.5
                cal_low = cal_prev
                cal_high = cal_c
        else:
            # Interpolate between bin i center and bin i+1 center
            n_bins = len(self.raw_centers)
            if i == n_bins - 1:
                # Last bin: interpolate between center and 1.0
                span = 1.0 - raw_c
                t = (p - raw_c) / span if span > 0 else 0.5
                cal_low = cal_c
                cal_high = 1.0
            else:
                raw_next = self.raw_centers[i + 1]
                cal_next = self.calibrated_centers[i + 1]
                span = raw_next - raw_c
                t = (p - raw_c) / span if span > 0 else 0.5
                cal_low = cal_c
                cal_high = cal_next

        # Linear interpolation
        t = max(0.0, min(1.0, t))
        calibrated = cal_low + t * (cal_high - cal_low)
        return round(max(0.0, min(1.0, calibrated)), 4)

    def calibrate_game(self, game: dict) -> dict:
        """
        Apply calibration to a game prediction dict (from predictions-today.json).

        Adds raw_home_win_prob, raw_away_win_prob fields and updates
        home_win_prob / away_win_prob with calibrated values.

        Returns the modified game dict (does NOT mutate in place).
        """
        g = dict(game)
        # Idempotency: if the in-process IsotonicPostCalibrator in
        # nomos-nba-agent/predict_today.py (line 672) already calibrated
        # this game, or a previous calibrate_game() pass ran, don't
        # double-apply. Detect via model_version suffix or calibrated flag.
        already_calibrated = (
            g.get("calibrated") is True
            or "+isotonic" in str(g.get("model_version", ""))
            or "raw_home_win_prob" in g
        )
        if already_calibrated:
            return g

        raw_home = float(g.get("home_win_prob", 0.5))
        raw_away = float(g.get("away_win_prob", 0.5))

        # Store originals
        g["raw_home_win_prob"] = round(raw_home, 4)
        g["raw_away_win_prob"] = round(raw_away, 4)

        # Calibrate home probability, derive away as complement
        cal_home = self.calibrate(raw_home)
        cal_away = round(1.0 - cal_home, 4)

        g["home_win_prob"] = cal_home
        g["away_win_prob"] = cal_away
        g["calibrated"] = True
        g["calibration_version"] = self.meta.get("version", "unknown")

        # Confidence label based on calibrated prob
        best = max(cal_home, cal_away)
        if best >= 0.70:
            g["confidence"] = "HIGH"
        elif best >= 0.55:
            g["confidence"] = "MEDIUM"
        else:
            g["confidence"] = "LOW"

        return g

    def summary(self) -> dict:
        """Return a summary dict for logging."""
        corrections = []
        for i, (r, c) in enumerate(zip(self.raw_centers, self.calibrated_centers)):
            delta = round(c - r, 4)
            lo = self.bin_edges[i]
            hi = self.bin_edges[i + 1]
            corrections.append({
                "bin": f"{lo:.0%}-{hi:.0%}",
                "raw": r,
                "calibrated": c,
                "delta": delta,
                "direction": "DOWN" if delta < -0.02 else ("UP" if delta > 0.02 else "FLAT"),
            })
        return {
            "loaded": self._loaded,
            "map_path": str(self.map_path),
            "meta": self.meta,
            "bin_corrections": corrections,
        }


# ═══════════════════════════════════════
# SECTION 2: ECE + Brier utilities
# ═══════════════════════════════════════

def compute_ece(probs: list, actuals: list, n_bins: int = 10) -> float:
    """
    Expected Calibration Error (ECE) — uniform binning.

    Args:
        probs:   list of predicted probabilities (floats in [0,1])
        actuals: list of actual outcomes (1 = home won, 0 = home lost)
        n_bins:  number of equal-width bins (default 10)

    Returns:
        ECE as a float. Lower is better. Well-calibrated ≈ 0.0.
    """
    if not probs or len(probs) != len(actuals):
        return float("nan")

    n = len(probs)
    bin_width = 1.0 / n_bins

    total_ece = 0.0
    for b in range(n_bins):
        lo = b * bin_width
        hi = (b + 1) * bin_width
        in_bin = [(p, a) for p, a in zip(probs, actuals) if lo <= p < hi]
        if b == n_bins - 1:
            in_bin = [(p, a) for p, a in zip(probs, actuals) if lo <= p <= hi]
        if not in_bin:
            continue
        bin_n = len(in_bin)
        avg_conf = sum(p for p, _ in in_bin) / bin_n
        avg_acc = sum(a for _, a in in_bin) / bin_n
        total_ece += (bin_n / n) * abs(avg_conf - avg_acc)

    return round(total_ece, 6)


def compute_brier(probs: list, actuals: list) -> float:
    """
    Brier score: mean squared error of probability forecasts.

    Args:
        probs:   predicted probabilities (floats in [0,1])
        actuals: binary outcomes (1 or 0)

    Returns:
        Brier score. Lower is better. Random = 0.25, perfect = 0.0.
    """
    if not probs or len(probs) != len(actuals):
        return float("nan")
    mse = sum((p - a) ** 2 for p, a in zip(probs, actuals)) / len(probs)
    return round(mse, 6)


def calibration_bins(probs: list, actuals: list, n_bins: int = 10) -> list:
    """
    Return per-bin calibration statistics for reporting.

    Returns list of dicts with: bin_range, n, avg_conf, avg_acc, gap, over_confident.
    """
    bin_width = 1.0 / n_bins
    bins = []
    for b in range(n_bins):
        lo = b * bin_width
        hi = (b + 1) * bin_width
        in_bin = [(p, a) for p, a in zip(probs, actuals) if lo <= p < hi]
        if b == n_bins - 1:
            in_bin = [(p, a) for p, a in zip(probs, actuals) if lo <= p <= hi]
        if not in_bin:
            bins.append({
                "bin_range": f"{lo:.0%}-{hi:.0%}",
                "n": 0, "avg_conf": None, "avg_acc": None, "gap": None,
                "over_confident": None
            })
            continue
        bin_n = len(in_bin)
        avg_conf = sum(p for p, _ in in_bin) / bin_n
        avg_acc = sum(a for _, a in in_bin) / bin_n
        gap = avg_conf - avg_acc
        bins.append({
            "bin_range": f"{lo:.0%}-{hi:.0%}",
            "n": bin_n,
            "avg_conf": round(avg_conf, 4),
            "avg_acc": round(avg_acc, 4),
            "gap": round(gap, 4),
            "over_confident": gap > 0.05,
        })
    return bins


# ═══════════════════════════════════════
# SECTION 3: Bootstrap from Supabase / eval history
# ═══════════════════════════════════════

def bootstrap_from_supabase(n_bins: int = 10) -> dict | None:
    """
    Query Supabase for historical predictions with actual_home_win outcomes.
    Compute calibration curve from real data and return a new calibration map.

    Requires DATABASE_URL in environment.
    """
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        env_file = BASE_DIR / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    db_url = line.split("=", 1)[1].strip().strip('"').strip("'")

    if not db_url:
        print("[calibration] No DATABASE_URL — skipping Supabase bootstrap")
        return None

    try:
        import psycopg2
        conn = psycopg2.connect(db_url, connect_timeout=20, options="-c search_path=public")
        cur = conn.cursor()

        cur.execute("""
            SELECT predicted_home_prob, actual_home_win
            FROM nba_predictions
            WHERE actual_home_win IS NOT NULL
              AND predicted_home_prob IS NOT NULL
              AND predicted_home_prob > 0
            ORDER BY game_date
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if len(rows) < 20:
            print(f"[calibration] Only {len(rows)} evaluated predictions — need 20+ for bootstrap")
            return None

        probs = [float(r[0]) for r in rows]
        actuals = [int(r[1]) for r in rows]

        print(f"[calibration] Bootstrap: {len(rows)} predictions loaded from Supabase")
        return _build_calibration_map(probs, actuals, n_bins, source="supabase")

    except Exception as e:
        print(f"[calibration] Supabase bootstrap failed: {e}")
        return None


def bootstrap_from_eval_history(n_bins: int = 10) -> dict | None:
    """
    Bootstrap from local eval-history.jsonl if Supabase is unavailable.
    Each line: {"ts": ..., "probs": [...], "actuals": [...], ...}
    """
    if not EVAL_HISTORY_PATH.exists():
        print(f"[calibration] eval-history.jsonl not found at {EVAL_HISTORY_PATH}")
        return None

    probs = []
    actuals = []
    for line in EVAL_HISTORY_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if "probs" in rec and "actuals" in rec:
                probs.extend(rec["probs"])
                actuals.extend(rec["actuals"])
        except Exception:
            continue

    if len(probs) < 20:
        print(f"[calibration] eval-history: only {len(probs)} samples — need 20+ for bootstrap")
        return None

    print(f"[calibration] Bootstrap: {len(probs)} predictions from eval-history.jsonl")
    return _build_calibration_map(probs, actuals, n_bins, source="eval-history")


def _build_calibration_map(
    probs: list,
    actuals: list,
    n_bins: int = 10,
    source: str = "unknown"
) -> dict:
    """
    Build a calibration map from raw probabilities and actual outcomes.

    Uses isotonic-style binning: for each bin, the calibrated value is the
    empirical win rate of predictions in that bin.

    Bins with < 3 samples fall back to the nearest populated neighbor
    (prevents noise from small samples).
    """
    n = len(probs)
    bin_width = 1.0 / n_bins

    bin_edges = [round(b * bin_width, 2) for b in range(n_bins + 1)]
    raw_centers = [round((b + 0.5) * bin_width, 3) for b in range(n_bins)]
    calibrated_centers = []
    bin_counts = []

    bins_data = []
    for b in range(n_bins):
        lo = b * bin_width
        hi = (b + 1) * bin_width
        in_bin = [(p, a) for p, a in zip(probs, actuals) if lo <= p < hi]
        if b == n_bins - 1:
            in_bin = [(p, a) for p, a in zip(probs, actuals) if lo <= p <= hi]
        bins_data.append(in_bin)
        bin_counts.append(len(in_bin))

    # First pass: compute empirical rates
    raw_calibrated = []
    for b, bin_samples in enumerate(bins_data):
        if len(bin_samples) >= 3:
            rate = sum(a for _, a in bin_samples) / len(bin_samples)
            raw_calibrated.append(round(rate, 4))
        else:
            raw_calibrated.append(None)  # sparse — fill later

    # Second pass: fill sparse bins via nearest-neighbor
    for b in range(n_bins):
        if raw_calibrated[b] is not None:
            continue
        # Search outward for the nearest populated bin
        found = None
        for radius in range(1, n_bins):
            for offset in [radius, -radius]:
                idx = b + offset
                if 0 <= idx < n_bins and raw_calibrated[idx] is not None:
                    found = raw_calibrated[idx]
                    break
            if found is not None:
                break
        raw_calibrated[b] = found if found is not None else raw_centers[b]

    calibrated_centers = raw_calibrated

    ece_before = compute_ece(probs, actuals, n_bins)
    brier_before = compute_brier(probs, actuals)

    # Estimate ECE after calibration (apply the new map to the training data)
    cal_obj = _CalibrationMapApplier(bin_edges, raw_centers, calibrated_centers)
    cal_probs = [cal_obj.apply(p) for p in probs]
    ece_after = compute_ece(cal_probs, actuals, n_bins)
    brier_after = compute_brier(cal_probs, actuals)

    cal_map = {
        "_meta": {
            "version": "1.0",
            "created": datetime.now().strftime("%Y-%m-%d"),
            "source": source,
            "n_games_used": n,
            "ece_before": round(ece_before, 6),
            "ece_after_estimated": round(ece_after, 6),
            "brier_before": round(brier_before, 6),
            "brier_after_estimated": round(brier_after, 6),
            "notes": f"Auto-bootstrapped from {source}. Review bin_notes for corrections.",
        },
        "bin_edges": bin_edges,
        "bin_counts": bin_counts,
        "raw_centers": raw_centers,
        "calibrated_centers": calibrated_centers,
        "bin_notes": _generate_bin_notes(raw_centers, calibrated_centers, bins_data),
    }

    print(f"[calibration] Map built: ECE {ece_before:.4f} -> {ece_after:.4f} (est.)")
    print(f"[calibration] Brier {brier_before:.4f} -> {brier_after:.4f} (est.)")
    return cal_map


class _CalibrationMapApplier:
    """Lightweight helper used internally during bootstrap ECE estimation."""
    def __init__(self, bin_edges, raw_centers, calibrated_centers):
        self.bin_edges = bin_edges
        self.raw_centers = raw_centers
        self.calibrated_centers = calibrated_centers

    def apply(self, p: float) -> float:
        p = max(0.0, min(1.0, float(p)))
        for i in range(len(self.bin_edges) - 1):
            if self.bin_edges[i] <= p < self.bin_edges[i + 1]:
                return self.calibrated_centers[i]
        return self.calibrated_centers[-1]


def _generate_bin_notes(raw_centers, calibrated_centers, bins_data) -> dict:
    notes = {}
    for i, (r, c) in enumerate(zip(raw_centers, calibrated_centers)):
        delta = c - r
        n = len(bins_data[i])
        if abs(delta) >= 0.05:
            direction = "OVER-CONFIDENT" if delta < 0 else "UNDER-CONFIDENT"
            actual_rate = sum(a for _, a in bins_data[i]) / n if n >= 3 else None
            actual_str = f", actual win rate={actual_rate:.1%}" if actual_rate is not None else ""
            notes[f"bin_{i+1}"] = (
                f"{int(r*100)-5:.0f}-{int(r*100)+5:.0f}% bucket: "
                f"raw {r:.2f} -> calibrated {c:.2f} "
                f"(delta={delta:+.2f}, n={n}, {direction}{actual_str})"
            )
    return notes


# ═══════════════════════════════════════
# SECTION 4: Apply calibration to predictions files
# ═══════════════════════════════════════

def apply_to_predictions_file(
    predictions_path: Path,
    calibration: IsotonicCalibration,
    in_place: bool = True,
) -> dict:
    """
    Load a predictions-today.json (or latest-picks.json), apply calibration
    to all home_win_prob values, and write back.

    Adds calibration metadata to the file's 'metadata' section.

    Returns summary of changes.
    """
    if not predictions_path.exists():
        raise FileNotFoundError(f"Predictions file not found: {predictions_path}")

    data = json.loads(predictions_path.read_text())
    games = data.get("games", [])

    raw_probs = []
    cal_probs = []
    n_calibrated = 0

    for i, game in enumerate(games):
        raw_home = game.get("home_win_prob")
        if raw_home is None:
            continue

        cal_game = calibration.calibrate_game(game)
        games[i] = cal_game
        raw_probs.append(raw_home)
        cal_probs.append(cal_game["home_win_prob"])
        n_calibrated += 1

    data["games"] = games

    # Also calibrate any embedded value_bets model_prob
    value_bets = data.get("value_bets", [])
    for j, vb in enumerate(value_bets):
        raw_mp = vb.get("model_prob")
        if raw_mp is not None:
            value_bets[j]["raw_model_prob"] = raw_mp
            value_bets[j]["model_prob"] = calibration.calibrate(raw_mp)
    data["value_bets"] = value_bets

    # Add calibration metadata
    if "metadata" not in data:
        data["metadata"] = {}
    data["metadata"]["calibration_applied"] = True
    data["metadata"]["calibration_version"] = calibration.meta.get("version", "unknown")
    data["metadata"]["calibration_applied_at"] = datetime.now().isoformat()
    data["metadata"]["n_games_calibrated"] = n_calibrated

    # Log changes
    if raw_probs:
        avg_raw = sum(raw_probs) / len(raw_probs)
        avg_cal = sum(cal_probs) / len(cal_probs)
        avg_delta = avg_cal - avg_raw
        print(f"[calibration] Applied to {n_calibrated} games in {predictions_path.name}")
        print(f"[calibration]   Avg raw prob: {avg_raw:.4f}  ->  Avg calibrated: {avg_cal:.4f}")
        print(f"[calibration]   Avg delta: {avg_delta:+.4f}")
        for r, c in zip(raw_probs, cal_probs):
            delta = c - r
            if abs(delta) >= 0.05:
                print(f"[calibration]   Notable correction: {r:.4f} -> {c:.4f} ({delta:+.4f})")

    if in_place:
        predictions_path.write_text(json.dumps(data, indent=2))
        print(f"[calibration] Saved calibrated predictions -> {predictions_path}")

    return {
        "n_games": n_calibrated,
        "avg_raw": round(avg_raw, 4) if raw_probs else None,
        "avg_calibrated": round(avg_cal, 4) if cal_probs else None,
        "pairs": list(zip(raw_probs, cal_probs)),
    }


# ═══════════════════════════════════════
# SECTION 5: Evaluation report
# ═══════════════════════════════════════

def build_evaluation_report(calibration: IsotonicCalibration) -> dict:
    """
    Build a calibration evaluation report using Supabase historical data.
    Computes ECE and Brier before/after calibration.
    Writes to data/calibration/calibration-report.json.
    """
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        env_file = BASE_DIR / ".env.local"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    db_url = line.split("=", 1)[1].strip().strip('"').strip("'")

    probs_raw = []
    actuals = []

    if db_url:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url, connect_timeout=20, options="-c search_path=public")
            cur = conn.cursor()
            cur.execute("""
                SELECT predicted_home_prob, actual_home_win
                FROM nba_predictions
                WHERE actual_home_win IS NOT NULL
                  AND predicted_home_prob IS NOT NULL
                  AND predicted_home_prob > 0
                ORDER BY game_date
            """)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            probs_raw = [float(r[0]) for r in rows]
            actuals = [int(r[1]) for r in rows]
            print(f"[calibration] Report: {len(rows)} predictions from Supabase")
        except Exception as e:
            print(f"[calibration] Supabase query failed: {e}")

    if not probs_raw:
        print("[calibration] No data available for report — using empty report")
        report = {
            "error": "No evaluated predictions found",
            "hint": "Run evaluate_predictions.py first to populate Supabase with outcomes",
            "generated_at": datetime.now().isoformat(),
        }
        CAL_REPORT_PATH.write_text(json.dumps(report, indent=2))
        return report

    probs_cal = [calibration.calibrate(p) for p in probs_raw]

    ece_raw = compute_ece(probs_raw, actuals)
    ece_cal = compute_ece(probs_cal, actuals)
    brier_raw = compute_brier(probs_raw, actuals)
    brier_cal = compute_brier(probs_cal, actuals)

    bins_before = calibration_bins(probs_raw, actuals)
    bins_after = calibration_bins(probs_cal, actuals)

    ece_improvement_pct = round((ece_raw - ece_cal) / ece_raw * 100, 1) if ece_raw > 0 else 0
    brier_improvement_pct = round((brier_raw - brier_cal) / brier_raw * 100, 1) if brier_raw > 0 else 0

    report = {
        "generated_at": datetime.now().isoformat(),
        "n_predictions": len(probs_raw),
        "calibration_map_version": calibration.meta.get("version", "unknown"),
        "calibration_map_source": calibration.meta.get("source", "unknown"),
        "metrics_before": {
            "ece": ece_raw,
            "brier": brier_raw,
            "avg_predicted_prob": round(sum(probs_raw) / len(probs_raw), 4),
            "actual_win_rate": round(sum(actuals) / len(actuals), 4),
        },
        "metrics_after": {
            "ece": ece_cal,
            "brier": brier_cal,
            "avg_predicted_prob": round(sum(probs_cal) / len(probs_cal), 4),
            "actual_win_rate": round(sum(actuals) / len(actuals), 4),
        },
        "improvement": {
            "ece_delta": round(ece_cal - ece_raw, 6),
            "ece_improvement_pct": ece_improvement_pct,
            "brier_delta": round(brier_cal - brier_raw, 6),
            "brier_improvement_pct": brier_improvement_pct,
        },
        "target": {
            "ece_target": 0.05,
            "ece_target_met_before": ece_raw <= 0.05,
            "ece_target_met_after": ece_cal <= 0.05,
        },
        "calibration_bins_before": bins_before,
        "calibration_bins_after": bins_after,
        "recommendation": _generate_recommendation(ece_raw, ece_cal, brier_raw, brier_cal),
    }

    CAL_REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\n{'='*60}")
    print(f"  CALIBRATION REPORT")
    print(f"{'='*60}")
    print(f"  Predictions evaluated: {len(probs_raw)}")
    print(f"  ECE:   {ece_raw:.4f} -> {ece_cal:.4f}  ({ece_improvement_pct:+.1f}%)")
    print(f"  Brier: {brier_raw:.4f} -> {brier_cal:.4f}  ({brier_improvement_pct:+.1f}%)")
    print(f"  ECE target (<0.05): {'MET' if ece_cal <= 0.05 else 'NOT MET'}")
    print(f"  Recommendation: {report['recommendation']['action']}")
    print(f"  Report saved: {CAL_REPORT_PATH}")
    print(f"{'='*60}\n")

    return report


def _generate_recommendation(
    ece_raw: float, ece_cal: float,
    brier_raw: float, brier_cal: float
) -> dict:
    """Generate actionable recommendation based on calibration metrics."""
    if ece_cal > 0.20:
        action = "CRITICAL: Re-bootstrap calibration map from fresh data. Current map inadequate."
        priority = "CRITICAL"
    elif ece_cal > 0.10:
        action = "HIGH: Calibration significantly improved but still poor. Bootstrap from >=50 predictions."
        priority = "HIGH"
    elif ece_cal > 0.05:
        action = "MEDIUM: Calibration improved. Consider refreshing map when 100+ predictions available."
        priority = "MEDIUM"
    else:
        action = "LOW: Calibration target met. Monitor and refresh map monthly."
        priority = "LOW"

    if brier_cal > brier_raw:
        action += " WARNING: Brier score worsened — calibration map may be overfitting noise."
        priority = max(priority, "HIGH", key=lambda x: {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}[x])

    return {
        "action": action,
        "priority": priority,
        "refresh_calibration_map": ece_cal > 0.10,
        "map_adequate": ece_cal <= 0.10,
    }


# ═══════════════════════════════════════
# SECTION 6: CLI entry point
# ═══════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Nomos42 NBA Calibration — post-hoc Platt scaling"
    )
    parser.add_argument(
        "--apply",
        metavar="PREDICTIONS_FILE",
        nargs="?",
        const=str(PREDICTIONS_PATH),
        help="Apply calibration to a predictions JSON file (default: predictions-today.json)"
    )
    parser.add_argument(
        "--apply-picks",
        action="store_true",
        help="Apply calibration to latest-picks.json"
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Bootstrap calibration map from Supabase predictions history"
    )
    parser.add_argument(
        "--bootstrap-eval-history",
        action="store_true",
        help="Bootstrap calibration map from local eval-history.jsonl"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Build ECE/Brier calibration report from Supabase data"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show current calibration map summary"
    )
    parser.add_argument(
        "--map",
        metavar="MAP_PATH",
        default=str(CAL_MAP_PATH),
        help=f"Path to calibration map JSON (default: {CAL_MAP_PATH})"
    )
    args = parser.parse_args()

    cal_map_path = Path(args.map)

    if args.bootstrap:
        print("[calibration] Bootstrapping from Supabase...")
        new_map = bootstrap_from_supabase()
        if new_map:
            cal_map_path.parent.mkdir(parents=True, exist_ok=True)
            cal_map_path.write_text(json.dumps(new_map, indent=2))
            print(f"[calibration] Calibration map saved -> {cal_map_path}")
        else:
            print("[calibration] Bootstrap failed — keeping existing map")
        return

    if args.bootstrap_eval_history:
        print("[calibration] Bootstrapping from eval-history.jsonl...")
        new_map = bootstrap_from_eval_history()
        if new_map:
            cal_map_path.parent.mkdir(parents=True, exist_ok=True)
            cal_map_path.write_text(json.dumps(new_map, indent=2))
            print(f"[calibration] Calibration map saved -> {cal_map_path}")
        else:
            print("[calibration] Bootstrap failed — keeping existing map")
        return

    # Load calibration
    calibration = IsotonicCalibration(cal_map_path)

    if args.summary:
        summary = calibration.summary()
        print(f"\n[calibration] Map summary:")
        print(f"  Loaded: {summary['loaded']}")
        print(f"  Source: {summary['meta'].get('source', 'N/A')}")
        print(f"  ECE before: {summary['meta'].get('ece_before', 'N/A')}")
        print(f"  Bins:")
        for b in summary["bin_corrections"]:
            print(f"    {b['bin']:>10s}  raw={b['raw']:.2f} -> cal={b['calibrated']:.2f}  "
                  f"delta={b['delta']:+.2f}  [{b['direction']}]")
        return

    if args.report:
        build_evaluation_report(calibration)
        return

    if args.apply_picks:
        apply_to_predictions_file(PICKS_PATH, calibration)
        return

    if args.apply:
        apply_to_predictions_file(Path(args.apply), calibration)
        return

    # Default: apply to today's predictions if they exist
    if PREDICTIONS_PATH.exists():
        print(f"[calibration] Applying to {PREDICTIONS_PATH.name}...")
        apply_to_predictions_file(PREDICTIONS_PATH, calibration)
    elif PICKS_PATH.exists():
        print(f"[calibration] Applying to {PICKS_PATH.name}...")
        apply_to_predictions_file(PICKS_PATH, calibration)
    else:
        print("[calibration] No predictions file found. Use --apply <path> to specify one.")
        print("  Available options:")
        print("    --summary          Show current calibration map")
        print("    --apply <file>     Apply calibration to a predictions file")
        print("    --bootstrap        Rebuild map from Supabase history")
        print("    --report           Full ECE/Brier evaluation report")
        parser.print_help()


if __name__ == "__main__":
    main()
