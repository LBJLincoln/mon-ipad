#!/usr/bin/env python3
"""
POLITICAL CPCV GATE — strategic parity with the NBA gate
========================================================
Mirrors `scripts/arena/cpcv_gate.py` (NBA) but reads political-trading-floor
swarm output. Same DSR + PBO + min-bets logic, same OUT schema, so the
dashboard can render NBA and Political gated leaderboards side-by-side.

WHY this exists (parity rationale):
  NBA and Political run on different starting bankrolls ($100 vs $100K) and
  different bet semantics (binary game outcome vs ETF position). For the
  promotion gate to be apples-to-apples we use SCALE-INVARIANT metrics:
    - Sharpe (no units)
    - ROI % (no units)
    - growth_factor = final_bankroll / initial_bankroll (no units)
  → A strategy with sharpe=2 in political is comparable to sharpe=2 in NBA.

INPUT:
  data/arena/political-backtest-results/political-backtest-*.json
  Each file is one fold. Schema (subset):
    {
      "traders": {
        "<trader_id>": {
          "political_bankroll": float,
          "political_roi_pct": float,
          "political_sharpe": float,
          "political_total_trades": int,
          ...
        }, ...
      },
      "strategies": { "<strategy_name>": {...} }
    }

OUTPUT:
  data/arena/political-cpcv-gated-strategies.json
  Same shape as cpcv-gated-strategies.json (NBA) for dashboard reuse.

USAGE:
  python3 scripts/arena/political_cpcv_gate.py
  python3 scripts/arena/political_cpcv_gate.py --recent 24 --min-trades 30
"""

import argparse
import glob
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/termius/mon-ipad")
BACKTEST_DIR = ROOT / "data" / "arena" / "political-backtest-results"
OUT_FILE = ROOT / "data" / "arena" / "political-cpcv-gated-strategies.json"

DEFAULT_RECENT = 24            # 4 days × 6 runs/day
MIN_TRADES = 30                # politics is lower volume than NBA bets
DSR_P_VALUE = 0.05
PBO_MAX = 0.40
INITIAL_CAPITAL = 100_000.0    # political starts at $100K (see WHY block)


def load_runs(limit: int) -> list:
    files = sorted(glob.glob(str(BACKTEST_DIR / "political-backtest-*.json")))
    files = files[-limit:]
    runs = []
    for f in files:
        try:
            data = json.loads(Path(f).read_text())
            data["_file"] = Path(f).name
            runs.append(data)
        except Exception as e:
            print(f"[pol-cpcv] skip {f}: {e}")
    return runs


def per_strategy_rows(runs: list) -> dict:
    """Treat each (trader_id) as a strategy. Future: split by trader×strategy."""
    rows: dict = {}
    for run in runs:
        traders = run.get("traders", {}) or {}
        for tid, t in traders.items():
            trades = int(t.get("political_total_trades", 0))
            if trades == 0:
                continue
            sharpe = float(t.get("political_sharpe", 0) or 0)
            roi = float(t.get("political_roi_pct", 0) or 0)
            bankroll = float(
                t.get("political_bankroll", INITIAL_CAPITAL) or INITIAL_CAPITAL
            )
            growth = bankroll / INITIAL_CAPITAL
            rows.setdefault(tid, []).append({
                "bets": trades,
                "sharpe": sharpe,
                "roi": roi,
                "bankroll": bankroll,
                "growth_factor": growth,
                "name": tid,
            })
    return rows


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def deflated_sharpe(sharpes: list, trials: int) -> tuple:
    """Bailey & López de Prado 2014 — identical to NBA gate."""
    n = len(sharpes)
    if n < 3:
        return 0.0, 1.0
    sr_mean = statistics.mean(sharpes)
    sr_std = statistics.stdev(sharpes) if n > 1 else 0.0
    if sr_std <= 1e-9:
        return 0.0, 1.0
    gamma = 0.5772156649
    if trials < 2:
        trials = 2
    z1 = math.sqrt(2.0 * math.log(trials))
    z2 = math.sqrt(2.0 * math.log(trials * math.e))
    expected_max_sr = sr_std * ((1 - gamma) * z1 + gamma * z2)
    dsr = (sr_mean - expected_max_sr) / max(sr_std / math.sqrt(n), 1e-9)
    p_value = 1.0 - _normal_cdf(dsr)
    return dsr, p_value


def compute_pbo(rows: dict) -> dict:
    """Combinatorially Symmetric CV — identical to NBA gate."""
    pbo_estimates: dict = {}
    for sid, observations in rows.items():
        n = len(observations)
        if n < 4:
            pbo_estimates[sid] = 0.5
            continue
        half = n // 2
        in_sample = observations[:half]
        out_sample = observations[half:]
        in_sharpe = statistics.mean(o["sharpe"] for o in in_sample)
        out_sharpe = statistics.mean(o["sharpe"] for o in out_sample)
        if in_sharpe <= 0:
            pbo_estimates[sid] = 0.5
            continue
        relative_drop = max(0.0, (in_sharpe - out_sharpe) / in_sharpe)
        pbo_estimates[sid] = min(1.0, relative_drop)
    return pbo_estimates


def gate_strategies(rows: dict, trials: int, min_trades: int) -> dict:
    pbo_map = compute_pbo(rows)
    gated: dict = {}
    for sid, obs in rows.items():
        total_trades = sum(o["bets"] for o in obs)
        if total_trades < min_trades:
            continue
        sharpes = [o["sharpe"] for o in obs]
        rois = [o["roi"] for o in obs]
        banks = [o["bankroll"] for o in obs]
        growths = [o["growth_factor"] for o in obs]
        if len(sharpes) < 3:
            continue

        sr_mean = statistics.mean(sharpes)
        sr_std = statistics.stdev(sharpes)
        dsr, p = deflated_sharpe(sharpes, trials)
        pbo = pbo_map.get(sid, 0.5)

        passes = (dsr > 0) and (p < DSR_P_VALUE) and (pbo < PBO_MAX) and sr_mean > 0

        gated[sid] = {
            "name": obs[0]["name"],
            "total_bets": total_trades,           # alias kept for dashboard
            "total_trades": total_trades,
            "n_folds": len(obs),
            "sr_mean": round(sr_mean, 4),
            "sr_std": round(sr_std, 4),
            "dsr": round(dsr, 4),
            "dsr_p_value": round(p, 5),
            "pbo": round(pbo, 4),
            "roi_mean_pct": round(statistics.mean(rois), 3),
            "final_bankroll_mean": round(statistics.mean(banks), 2),
            "growth_factor_mean": round(statistics.mean(growths), 4),
            "passes_gate": passes,
        }
    return gated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recent", type=int, default=DEFAULT_RECENT)
    ap.add_argument("--min-trades", type=int, default=MIN_TRADES)
    args = ap.parse_args()

    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[pol-cpcv] Loading last {args.recent} runs from {BACKTEST_DIR}")
    runs = load_runs(args.recent)
    if not runs:
        print("[pol-cpcv] No runs found — write fold files via "
              "scripts/arena/continuous-political-backtest-swarm.sh")
        # Still write an empty result so dashboard sees the file
        OUT_FILE.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_runs_analyzed": 0,
            "n_strategies_evaluated": 0,
            "n_passed": 0,
            "n_rejected": 0,
            "passed_rate_pct": 0.0,
            "passed": {},
            "rejected_top10_by_dsr": {},
            "note": "No backtest runs in pool yet. Run "
                    "scripts/arena/continuous-political-backtest-swarm.sh.",
        }, indent=2))
        return

    print(f"[pol-cpcv] Loaded {len(runs)} runs")
    rows = per_strategy_rows(runs)
    print(f"[pol-cpcv] {len(rows)} strategies (traders) with ≥1 trade")

    trials = max(len(rows), 5)   # politics has only 5 traders, give DSR room
    gated = gate_strategies(rows, trials=trials, min_trades=args.min_trades)

    passed = {sid: g for sid, g in gated.items() if g["passes_gate"]}
    rejected = {sid: g for sid, g in gated.items() if not g["passes_gate"]}
    rejected_top = dict(sorted(
        rejected.items(), key=lambda kv: -kv[1]["dsr"]
    )[:10])

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": "political",
        "initial_capital": INITIAL_CAPITAL,
        "n_runs_analyzed": len(runs),
        "n_strategies_evaluated": len(rows),
        "n_trials_for_dsr": trials,
        "gate": {
            "min_trades": args.min_trades,
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
                "insufficient_trades" if g["total_trades"] < args.min_trades else
                "negative_or_zero_sharpe" if g["sr_mean"] <= 0 else
                "dsr_p_value" if g["dsr_p_value"] >= DSR_P_VALUE else
                "pbo_too_high"
            )}
            for sid, g in rejected.items()
        },
    }

    OUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"[pol-cpcv] Wrote {OUT_FILE}")
    print(f"[pol-cpcv]   passed: {len(passed)}/{len(rows)} "
          f"({output['passed_rate_pct']}%)")

    if passed:
        print("\n[pol-cpcv] TOP 5 GATED STRATEGIES")
        top5 = sorted(passed.items(), key=lambda kv: -kv[1]["dsr"])[:5]
        for sid, g in top5:
            print(f"  {sid:<20} sr={g['sr_mean']:.2f}±{g['sr_std']:.2f} "
                  f"dsr={g['dsr']:.2f} p={g['dsr_p_value']:.3f} "
                  f"pbo={g['pbo']:.2f} trades={g['total_trades']}")


if __name__ == "__main__":
    main()
