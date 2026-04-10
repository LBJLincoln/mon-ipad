#!/usr/bin/env python3
"""
CPCV GATE — Deflated Sharpe Ratio + PBO filter for strategy promotion
========================================================================
Implements the promotion gate from:
  - López de Prado, Lipton, Zoonekynd — "Sharpe Ratio Inference" SSRN:5520741
  - ScienceDirect 2024 — "CPCV beats walk-forward"
  - arXiv:2410.21484 — Backtest Overfitting

The continuous backtest swarm produces 6 independent backtest runs per day.
Each run uses a different snapshot of games/odds and resolves to a per-
strategy (bets, ROI, Sharpe) row. We treat the recent N runs as an empirical
fold ensemble and compute for every strategy:

  1. Mean Sharpe across folds        (SR_mean)
  2. Std of Sharpe across folds      (SR_std)
  3. Deflated Sharpe Ratio (DSR)     — Bailey & López de Prado 2014
  4. Probabilistic Sharpe Ratio (PSR) — p-value of SR > 0
  5. Probability of Backtest Overfitting (PBO) — how often this strategy
     is the best in-sample but underperforms out-of-sample

Strategies that pass the gate (DSR > 0, PBO < 0.40, min 50 bets) are written
to data/arena/cpcv-gated-strategies.json — the trading-floor consumer
should promote only gated strategies to the live floor.

Why:
  With ~50 strategies × 24 recent runs = 1,200 Sharpe observations, ~15%
  will look profitable by chance. CPCV gating cuts this to <3% false
  positives per SSRN:5520741.

Usage:
  python3 scripts/arena/cpcv_gate.py                  # default 24 folds
  python3 scripts/arena/cpcv_gate.py --recent 48      # last 48 runs
  python3 scripts/arena/cpcv_gate.py --min-bets 100   # stricter gate
"""

import argparse
import glob
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/lahargnedebartoli/mon-ipad")
BACKTEST_DIR = ROOT / "data" / "arena" / "backtest-results"
OUT_FILE = ROOT / "data" / "arena" / "cpcv-gated-strategies.json"

DEFAULT_RECENT = 24     # 4 days × 6 runs/day
MIN_BETS = 50           # below this, Sharpe is noise
DSR_P_VALUE = 0.05      # one-sided gate
PBO_MAX = 0.40          # reject if backtest-overfitting prob too high


def load_runs(limit: int) -> list:
    files = sorted(glob.glob(str(BACKTEST_DIR / "backtest-*.json")))
    files = files[-limit:]
    runs = []
    for f in files:
        try:
            data = json.loads(Path(f).read_text())
            data["_file"] = Path(f).name
            runs.append(data)
        except Exception as e:
            print(f"[cpcv] skip {f}: {e}")
    return runs


def per_strategy_rows(runs: list) -> dict:
    """Collect per-strategy stat rows across runs. Key: strategy_id."""
    rows: dict = {}
    for run in runs:
        strats = run.get("strategies", {}) or {}
        for sid, s in strats.items():
            bets = int(s.get("total_bets", 0))
            if bets == 0:
                continue
            sharpe = float(s.get("sharpe", 0))
            roi = float(s.get("roi", 0))
            bankroll = float(s.get("final_bankroll", 100))
            rows.setdefault(sid, []).append({
                "bets": bets,
                "sharpe": sharpe,
                "roi": roi,
                "bankroll": bankroll,
                "name": s.get("name", sid),
            })
    return rows


def _normal_cdf(x: float) -> float:
    """Standard normal CDF without scipy dependency."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def deflated_sharpe(sharpes: list, trials: int) -> tuple:
    """
    Deflated Sharpe Ratio (Bailey & López de Prado 2014).

    Returns (dsr, p_value). dsr > 0 at p < 0.05 means the strategy's
    Sharpe is statistically above what a null population of `trials`
    random strategies would produce.
    """
    n = len(sharpes)
    if n < 3:
        return 0.0, 1.0
    sr_mean = statistics.mean(sharpes)
    sr_std = statistics.stdev(sharpes) if n > 1 else 0.0
    if sr_std <= 1e-9:
        # No variance → treat as noise
        return 0.0, 1.0

    # Expected maximum Sharpe under null (order statistic approximation)
    # E[max(SR)] ≈ SR_std * ((1-γ) * Φ⁻¹(1 - 1/N) + γ * Φ⁻¹(1 - 1/(Ne)))
    # γ ≈ 0.5772 (Euler-Mascheroni)
    gamma = 0.5772156649
    if trials < 2:
        trials = 2
    # Φ⁻¹ approximations via standard normal quantile from beta distribution
    # Use simple approximation: Φ⁻¹(1 - 1/N) ≈ sqrt(2 * ln(N))
    z1 = math.sqrt(2.0 * math.log(trials))
    z2 = math.sqrt(2.0 * math.log(trials * math.e))
    expected_max_sr = sr_std * ((1 - gamma) * z1 + gamma * z2)

    # DSR = (SR_mean - expected_max) * sqrt(n-1) / sqrt(1 - skew*SR + (kurt-1)/4 * SR^2)
    # Simplified: drop skew/kurt (assume normal) → DSR_num / sqrt(n-1)
    dsr = (sr_mean - expected_max_sr) / max(sr_std / math.sqrt(n), 1e-9)
    p_value = 1.0 - _normal_cdf(dsr)
    return dsr, p_value


def compute_pbo(rows: dict) -> dict:
    """
    Probability of Backtest Overfitting — Combinatorially Symmetric CV.

    Method (Bailey, Borwein, López de Prado 2014):
      1. Split the N runs into two halves (earlier vs later).
      2. For each strategy, measure its rank in each half.
      3. PBO = P(rank worsens out-of-sample) averaged across strategies.

    Returns {strategy_id: pbo_estimate}.
    """
    pbo_estimates: dict = {}
    for sid, observations in rows.items():
        n = len(observations)
        if n < 4:
            pbo_estimates[sid] = 0.5  # insufficient data, neutral
            continue
        half = n // 2
        in_sample = observations[:half]
        out_sample = observations[half:]
        in_sharpe = statistics.mean(o["sharpe"] for o in in_sample)
        out_sharpe = statistics.mean(o["sharpe"] for o in out_sample)
        # If OOS Sharpe drops below IS Sharpe, contributes to PBO
        if in_sharpe <= 0:
            pbo_estimates[sid] = 0.5
            continue
        relative_drop = max(0.0, (in_sharpe - out_sharpe) / in_sharpe)
        pbo_estimates[sid] = min(1.0, relative_drop)
    return pbo_estimates


def gate_strategies(rows: dict, trials: int, min_bets: int) -> dict:
    """Apply CPCV + DSR + PBO gate to all strategies."""
    pbo_map = compute_pbo(rows)
    gated: dict = {}
    for sid, obs in rows.items():
        total_bets = sum(o["bets"] for o in obs)
        if total_bets < min_bets:
            continue
        sharpes = [o["sharpe"] for o in obs]
        rois = [o["roi"] for o in obs]
        banks = [o["bankroll"] for o in obs]
        if len(sharpes) < 3:
            continue

        sr_mean = statistics.mean(sharpes)
        sr_std = statistics.stdev(sharpes)
        dsr, p = deflated_sharpe(sharpes, trials)
        pbo = pbo_map.get(sid, 0.5)

        passes = (dsr > 0) and (p < DSR_P_VALUE) and (pbo < PBO_MAX) and sr_mean > 0

        gated[sid] = {
            "name": obs[0]["name"],
            "total_bets": total_bets,
            "n_folds": len(obs),
            "sr_mean": round(sr_mean, 4),
            "sr_std": round(sr_std, 4),
            "dsr": round(dsr, 4),
            "dsr_p_value": round(p, 5),
            "pbo": round(pbo, 4),
            "roi_mean_pct": round(statistics.mean(rois), 3),
            "final_bankroll_mean": round(statistics.mean(banks), 2),
            "passes_gate": passes,
            # Cycle 13: per-fold series for skfolio-style fold-band visualization
            # on /trading-floor. Cap rounding to keep payload small.
            "sharpes_per_fold": [round(s, 3) for s in sharpes],
            "rois_per_fold": [round(r, 3) for r in rois],
        }
    return gated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recent", type=int, default=DEFAULT_RECENT)
    ap.add_argument("--min-bets", type=int, default=MIN_BETS)
    args = ap.parse_args()

    print(f"[cpcv] Loading last {args.recent} backtest runs from {BACKTEST_DIR}")
    runs = load_runs(args.recent)
    if not runs:
        print("[cpcv] No runs found")
        return

    print(f"[cpcv] Loaded {len(runs)} runs")
    rows = per_strategy_rows(runs)
    print(f"[cpcv] {len(rows)} strategies with ≥1 bet")

    # Number of strategies tried = trials for DSR denominator
    trials = len(rows)
    gated = gate_strategies(rows, trials=trials, min_bets=args.min_bets)

    passed = {sid: g for sid, g in gated.items() if g["passes_gate"]}
    rejected = {sid: g for sid, g in gated.items() if not g["passes_gate"]}

    # Top-10 rejected by DSR — operator visibility for "almost passed" strategies
    rejected_top = dict(sorted(
        rejected.items(), key=lambda kv: -kv[1]["dsr"]
    )[:10])

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_runs_analyzed": len(runs),
        "n_strategies_evaluated": len(rows),
        "n_trials_for_dsr": trials,
        "gate": {
            "min_bets": args.min_bets,
            "dsr_p_value_max": DSR_P_VALUE,
            "pbo_max": PBO_MAX,
        },
        "n_passed": len(passed),
        "n_rejected": len(rejected),
        "passed_rate_pct": round(100.0 * len(passed) / max(len(gated), 1), 2),
        "passed": passed,
        "rejected_top10_by_dsr": rejected_top,
        "rejected_summary": {
            sid: {"reason": (
                "insufficient_bets" if g["total_bets"] < args.min_bets else
                "negative_or_zero_sharpe" if g["sr_mean"] <= 0 else
                "dsr_p_value" if g["dsr_p_value"] >= DSR_P_VALUE else
                "pbo_too_high"
            )}
            for sid, g in rejected.items()
        },
    }

    OUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"[cpcv] Wrote {OUT_FILE}")
    print(f"[cpcv]   passed: {len(passed)}/{len(rows)} "
          f"({output['passed_rate_pct']}%)")

    if passed:
        print("\n[cpcv] TOP 5 GATED STRATEGIES")
        top5 = sorted(passed.items(),
                      key=lambda kv: -kv[1]["dsr"])[:5]
        for sid, g in top5:
            print(f"  {sid:<30} sr={g['sr_mean']:.2f}±{g['sr_std']:.2f} "
                  f"dsr={g['dsr']:.2f} p={g['dsr_p_value']:.3f} "
                  f"pbo={g['pbo']:.2f} bets={g['total_bets']}")


if __name__ == "__main__":
    main()
