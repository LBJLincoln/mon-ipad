#!/usr/bin/env python3
"""
calibration_fit.py — Fit a real isotonic calibration map from prospective
predictions (nomos-nba-agent/data/predictions) joined against actual game
outcomes (scripts/arena/backtest_engine.load_games).

Status (2026-04-07): NEW. Replaces the hand-tuned 31-game calibration map
at data/calibration/calibration-map.json (D5 audit, 2026-03-31) which
over-corrected bin 6 0.65→0.35. Real ground-truth on 104 matched games
shows milder over-confidence and the hand-tuned map was hurting accuracy.

Method: Pool Adjacent Violators (PAV) — optimal monotone regression, pure
Python, no sklearn. Produces the same piecewise-linear bin format
IsotonicCalibration (scripts/calibration.py) already consumes.

Writes TWO artifacts so both calibration paths get refreshed atomically:
  1. mon-ipad/data/calibration/calibration-map.json
       — consumed by scripts/calibration.IsotonicCalibration
       (applied at scripts/autonomous-cycle.sh line 120 and
        scripts/betting_agent.py line 463)
  2. nomos-nba-agent/calibration/isotonic_breakpoints.json
       — consumed by nomos-nba-agent/calibration/IsotonicPostCalibrator
       (applied at nomos-nba-agent/predict_today.py line 668)
     This file was previously an IDENTITY STUB and is replaced by a real fit.

Reports before/after Brier + ECE so the improvement is visible.

Usage:
  python3 scripts/calibration_fit.py               # fit + write
  python3 scripts/calibration_fit.py --dry-run     # print, don't write
  python3 scripts/calibration_fit.py --n-bins 15   # override bin count
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/lahargnedebartoli/mon-ipad")
CAL_MAP_PATH = ROOT / "data" / "calibration" / "calibration-map.json"
ISO_BREAKPOINTS_PATH = Path("/home/lahargnedebartoli/nomos-nba-agent/calibration/isotonic_breakpoints.json")

sys.path.insert(0, str(ROOT / "scripts" / "arena"))
from real_predictions_loader import load_real_predictions  # noqa: E402
from backtest_engine import load_games  # noqa: E402


def collect_matched_pairs() -> list[tuple[float, int]]:
    """Join real predictions to actual outcomes. Returns [(prob_home, home_won)]."""
    preds = load_real_predictions()
    games = load_games()
    by_key = {(g.date, g.home_abbr, g.away_abbr): g for g in games}
    pairs: list[tuple[float, int]] = []
    for key, p in preds.items():
        g = by_key.get(key)
        if g is None:
            continue
        pairs.append((float(p["prob_home"]), 1 if g.home_won else 0))
    return pairs


def brier(pairs: list[tuple[float, int]]) -> float:
    if not pairs:
        return 0.0
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def ece(pairs: list[tuple[float, int]], n_bins: int = 10) -> float:
    if not pairs:
        return 0.0
    edges = [i / n_bins for i in range(n_bins + 1)]
    total = 0.0
    n = len(pairs)
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        bucket = [
            (p, y) for p, y in pairs
            if (lo <= p < hi) or (i == n_bins - 1 and p == 1.0)
        ]
        if not bucket:
            continue
        avg_p = sum(p for p, _ in bucket) / len(bucket)
        rate = sum(y for _, y in bucket) / len(bucket)
        total += (len(bucket) / n) * abs(avg_p - rate)
    return total


def pav_isotonic(pairs: list[tuple[float, int]]) -> list[tuple[float, float]]:
    """Pool Adjacent Violators — pure-Python monotone regression.

    Sorts pairs by x, then pools adjacent blocks whose means violate
    monotonicity. Returns a list of (x, y_hat) for every input point,
    where y_hat is the pooled mean of its block.
    """
    if not pairs:
        return []
    sorted_pairs = sorted(pairs, key=lambda t: t[0])
    # Each block is (sum_x, sum_y, count)
    blocks: list[list[float]] = [
        [float(p), float(y), 1.0] for p, y in sorted_pairs
    ]
    i = 0
    while i < len(blocks) - 1:
        mean_i = blocks[i][1] / blocks[i][2]
        mean_j = blocks[i + 1][1] / blocks[i + 1][2]
        if mean_i > mean_j + 1e-12:
            merged = [
                blocks[i][0] + blocks[i + 1][0],
                blocks[i][1] + blocks[i + 1][1],
                blocks[i][2] + blocks[i + 1][2],
            ]
            blocks[i : i + 2] = [merged]
            if i > 0:
                i -= 1  # re-check backwards
        else:
            i += 1
    # Expand back: for each block, emit (x_mean, y_mean)
    result: list[tuple[float, float]] = []
    for s_x, s_y, c in blocks:
        result.append((s_x / c, s_y / c))
    return result


def build_bin_map(
    pairs: list[tuple[float, int]], n_bins: int = 10
) -> tuple[list[float], list[float], list[float], list[int]]:
    """Project the PAV-fitted curve onto a fixed grid of bin centers so the
    output matches the calibration-map.json schema used by IsotonicCalibration.
    """
    isotonic_curve = pav_isotonic(pairs)
    if not isotonic_curve:
        raise SystemExit("[calibration_fit] no pairs — cannot fit")
    edges = [round(i / n_bins, 4) for i in range(n_bins + 1)]
    raw_centers = [round((edges[i] + edges[i + 1]) / 2.0, 4) for i in range(n_bins)]
    cal_centers: list[float] = []
    bin_counts: list[int] = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        bucket = [
            (p, y) for p, y in pairs
            if (lo <= p < hi) or (i == n_bins - 1 and p == 1.0)
        ]
        bin_counts.append(len(bucket))
        if bucket:
            rate = sum(y for _, y in bucket) / len(bucket)
            # Monotone-smooth against the PAV curve: pick the nearest
            # isotonic point to the raw center and blend toward it.
            target = min(
                isotonic_curve,
                key=lambda xy: abs(xy[0] - raw_centers[i]),
            )[1]
            # 70% PAV curve / 30% empirical bin rate — PAV is more stable in
            # low-count bins because it borrows strength from neighbors.
            blended = 0.7 * target + 0.3 * rate
            cal_centers.append(round(blended, 4))
        else:
            # Empty bin: fall back to PAV curve at this x
            nearest = min(
                isotonic_curve,
                key=lambda xy: abs(xy[0] - raw_centers[i]),
            )
            cal_centers.append(round(nearest[1], 4))
    # Enforce monotonicity on the final output (cumulative max from both ends)
    for i in range(1, n_bins):
        if cal_centers[i] < cal_centers[i - 1]:
            cal_centers[i] = cal_centers[i - 1]
    return edges, raw_centers, cal_centers, bin_counts


def build_calibrated_pairs(
    pairs: list[tuple[float, int]],
    edges: list[float],
    raw_centers: list[float],
    cal_centers: list[float],
) -> list[tuple[float, int]]:
    """Re-evaluate Brier/ECE after applying the map (piecewise-linear interp)."""

    def calibrate(p: float) -> float:
        if p <= 0.0:
            return 0.0
        if p >= 1.0:
            return 1.0
        n = len(raw_centers)
        # Find bin index
        i = 0
        for k in range(len(edges) - 1):
            if edges[k] <= p < edges[k + 1]:
                i = k
                break
        raw_c = raw_centers[i]
        cal_c = cal_centers[i]
        if p < raw_c:
            if i == 0:
                t = p / raw_c if raw_c > 0 else 0.5
                return max(0.0, min(1.0, t * cal_c))
            raw_prev = raw_centers[i - 1]
            cal_prev = cal_centers[i - 1]
            span = raw_c - raw_prev
            t = (p - raw_prev) / span if span > 0 else 0.5
            return max(0.0, min(1.0, cal_prev + t * (cal_c - cal_prev)))
        if i == n - 1:
            span = 1.0 - raw_c
            t = (p - raw_c) / span if span > 0 else 0.5
            return max(0.0, min(1.0, cal_c + t * (1.0 - cal_c)))
        raw_next = raw_centers[i + 1]
        cal_next = cal_centers[i + 1]
        span = raw_next - raw_c
        t = (p - raw_c) / span if span > 0 else 0.5
        return max(0.0, min(1.0, cal_c + t * (cal_next - cal_c)))

    return [(calibrate(p), y) for p, y in pairs]


def write_calibration_map(
    edges: list[float],
    raw_centers: list[float],
    cal_centers: list[float],
    bin_counts: list[int],
    pairs: list[tuple[float, int]],
    brier_before: float,
    brier_after: float,
    ece_before: float,
    ece_after: float,
) -> None:
    now = datetime.now(timezone.utc)
    dates = sorted({
        # retrieve via the global preds dict — cheaper to recompute
        key[0]
        for key in load_real_predictions().keys()
    })
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "unknown"
    payload = {
        "_meta": {
            "version": "2.0",
            "created": now.date().isoformat(),
            "generated_at": now.isoformat(),
            "source": "scripts/calibration_fit.py (Pool Adjacent Violators + empirical blend)",
            "model_version": "ensemble v1 / real_predictions_loader",
            "notes": (
                "Rebuilt from real matched predictions (prospective, no look-ahead). "
                "Previous 31-game hand-tuned map over-corrected bin 6 0.65->0.35. "
                "This fit uses 70% PAV curve + 30% empirical bin rate to borrow "
                "strength from neighbouring bins in low-count regions."
            ),
            "n_games_used": len(pairs),
            "date_range": date_range,
            "brier_before": round(brier_before, 5),
            "brier_after": round(brier_after, 5),
            "ece_before": round(ece_before, 5),
            "ece_after": round(ece_after, 5),
        },
        "bin_edges": edges,
        "bin_counts": bin_counts,
        "raw_centers": raw_centers,
        "calibrated_centers": cal_centers,
    }
    CAL_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    CAL_MAP_PATH.write_text(json.dumps(payload, indent=2))
    print(f"[calibration_fit] wrote {CAL_MAP_PATH}")


def write_isotonic_breakpoints(
    raw_centers: list[float],
    cal_centers: list[float],
    n_games: int,
    brier_before: float,
    brier_after: float,
    ece_before: float,
    ece_after: float,
) -> None:
    """Write the nomos-nba-agent isotonic_breakpoints.json (was identity stub)."""
    # IsotonicPostCalibrator uses x_points/y_points piecewise-linear,
    # same conceptual shape — pad with endpoints at 0 and 1 and clamp.
    xs = [0.0] + list(raw_centers) + [1.0]
    ys = [0.0] + list(cal_centers) + [1.0]
    # Enforce monotonic y
    for i in range(1, len(ys)):
        if ys[i] < ys[i - 1]:
            ys[i] = ys[i - 1]
    payload = {
        "x_points": [round(x, 4) for x in xs],
        "y_points": [round(y, 4) for y in ys],
        "metadata": {
            "identity": False,
            "fitted_on": datetime.now(timezone.utc).isoformat(),
            "n_breakpoints": len(xs),
            "n_games_used": n_games,
            "brier_before": round(brier_before, 5),
            "brier_after": round(brier_after, 5),
            "ece_before": round(ece_before, 5),
            "ece_after": round(ece_after, 5),
            "fitter": "scripts/calibration_fit.py (PAV)",
            "source_repo": "mon-ipad",
        },
    }
    if not ISO_BREAKPOINTS_PATH.parent.exists():
        print(f"[calibration_fit] skip isotonic_breakpoints (dir missing): {ISO_BREAKPOINTS_PATH}")
        return
    ISO_BREAKPOINTS_PATH.write_text(json.dumps(payload, indent=2))
    print(f"[calibration_fit] wrote {ISO_BREAKPOINTS_PATH}")


def kfold_cv_brier(
    pairs: list[tuple[float, int]], n_bins: int, k: int = 5
) -> tuple[float, float]:
    """Out-of-sample Brier/ECE via k-fold (deterministic stratified split)."""
    if len(pairs) < 2 * k:
        return float("nan"), float("nan")
    # Sort by prob then round-robin into folds → preserves class/probability
    # balance across folds without needing numpy.
    sorted_pairs = sorted(pairs, key=lambda t: t[0])
    folds: list[list[tuple[float, int]]] = [[] for _ in range(k)]
    for i, pr in enumerate(sorted_pairs):
        folds[i % k].append(pr)
    oos: list[tuple[float, int]] = []
    for i in range(k):
        train = [pr for j, f in enumerate(folds) if j != i for pr in f]
        test = folds[i]
        edges, raw_c, cal_c, _ = build_bin_map(train, n_bins)
        oos.extend(build_calibrated_pairs(test, edges, raw_c, cal_c))
    return brier(oos), ece(oos)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    # n_bins=5 is empirically best (5-fold CV Brier -0.00413) on the current
    # 104-game pool. 10 bins overfits (+0.008 CV Brier). Re-tune via
    # `for k in 3..10; do python3 scripts/calibration_fit.py --dry-run --n-bins $k`
    # when the pool grows past ~300 games.
    p.add_argument("--n-bins", type=int, default=5)
    p.add_argument(
        "--force",
        action="store_true",
        help="Write even if 5-fold CV Brier is worse than raw",
    )
    args = p.parse_args()

    pairs = collect_matched_pairs()
    if not pairs:
        print("[calibration_fit] no matched pairs — aborting")
        return 1

    brier_before = brier(pairs)
    ece_before = ece(pairs)
    print(f"[calibration_fit] matched={len(pairs)} "
          f"raw Brier={brier_before:.5f} raw ECE={ece_before:.5f}")

    edges, raw_centers, cal_centers, bin_counts = build_bin_map(pairs, args.n_bins)
    calibrated = build_calibrated_pairs(pairs, edges, raw_centers, cal_centers)
    brier_after = brier(calibrated)
    ece_after = ece(calibrated)
    print(f"[calibration_fit] in-sample after Brier={brier_after:.5f} "
          f"after ECE={ece_after:.5f}")

    # Out-of-sample 5-fold CV (honest Brier improvement)
    cv_brier, cv_ece = kfold_cv_brier(pairs, args.n_bins, k=5)
    print(f"[calibration_fit] 5-fold CV  Brier={cv_brier:.5f} ECE={cv_ece:.5f}")
    print(f"[calibration_fit] CV Brier delta = {cv_brier - brier_before:+.5f}")
    print(f"[calibration_fit] CV ECE   delta = {cv_ece - ece_before:+.5f}")
    print(f"[calibration_fit] in-sample Brier delta = {brier_after - brier_before:+.5f}")
    print(f"[calibration_fit] in-sample ECE   delta = {ece_after - ece_before:+.5f}")
    print()
    print("bin | count | raw_c   | cal_c   | shift")
    for i in range(len(raw_centers)):
        shift = cal_centers[i] - raw_centers[i]
        print(f"  {i} | {bin_counts[i]:5d} | {raw_centers[i]:.4f} | {cal_centers[i]:.4f} | {shift:+.4f}")

    if args.dry_run:
        return 0

    if cv_brier > brier_before and not args.force:
        print("[calibration_fit] REFUSING to write: 5-fold CV Brier is worse "
              "than raw. Try a different --n-bins or wait for more data. "
              "Pass --force to override.")
        return 2

    write_calibration_map(
        edges, raw_centers, cal_centers, bin_counts, pairs,
        brier_before, brier_after, ece_before, ece_after,
    )
    write_isotonic_breakpoints(
        raw_centers, cal_centers, len(pairs),
        brier_before, brier_after, ece_before, ece_after,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
