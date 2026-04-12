#!/usr/bin/env python3
"""
SEASON LEADERBOARD + CATEGORY CHAMPIONS + $1M PROJECTION
==========================================================
Consumes every backtest-*.json in data/arena/backtest-results/ (one file =
one 1081-game season simulation) and produces three artifacts scientists
can reason about directly:

  1. data/arena/season-leaderboard.json
     → per-season top-20 traders ranked by Sharpe × ROI
     → trajectory (last 24 seasons = 4 days of 6 runs/day)
     → consistency score: how often a trader stays in top-20

  2. data/arena/category-model-registry.json
     → all 102 categories with cumulative stats across seasons
     → champions list (top-20 categories by ROI)
     → coverage: which categories never got bets (missing odds)
     → status per category: has_model / pending / untrained

  3. data/arena/one-million-projection.json
     → given best strategy from last N seasons, projects:
       - days to $1M at current ROI & volume
       - bankroll trajectory
       - bottleneck analysis (volume vs edge vs variance)

Runs as a post-step after continuous-backtest-swarm.sh and is cheap enough
(< 1 second) to execute every cycle.

Usage:
  python3 scripts/arena/season-leaderboard.py
  python3 scripts/arena/season-leaderboard.py --recent 24
"""

import argparse
import glob
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bet_categories import ALL_CATEGORIES

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "arena"
BACKTEST_DIR = DATA / "backtest-results"
LEADERBOARD_FILE = DATA / "season-leaderboard.json"
CATEGORY_REGISTRY_FILE = DATA / "category-model-registry.json"
MILLION_FILE = DATA / "one-million-projection.json"

# Tuning
DEFAULT_RECENT = 24          # 24 seasons = 4 days × 6 runs/day
TOP_N_TRADERS = 20
TOP_N_CATEGORIES = 20
TARGET_BANKROLL = 1_000_000  # $1M
STARTING_BANKROLL = 100      # $100 per backtest


def load_recent_seasons(limit: int = DEFAULT_RECENT) -> list:
    """Load the most recent N backtest files, newest last."""
    files = sorted(glob.glob(str(BACKTEST_DIR / "backtest-*.json")))
    if not files:
        return []
    files = files[-limit:]
    seasons = []
    for f in files:
        try:
            data = json.loads(Path(f).read_text())
            data["_file"] = Path(f).name
            seasons.append(data)
        except Exception as e:
            print(f"[leaderboard] skip {f}: {e}")
    return seasons


def rank_traders(season: dict, top_n: int = TOP_N_TRADERS) -> list:
    """Rank traders in a single season by (Sharpe × ROI) with noise filter."""
    strats = season.get("strategies", {}) or {}
    rows = []
    for sid, stats in strats.items():
        bets = int(stats.get("total_bets", 0))
        roi = float(stats.get("roi", 0))
        sharpe = float(stats.get("sharpe", 0))
        bank = float(stats.get("final_bankroll", STARTING_BANKROLL))
        wr = float(stats.get("win_rate", 0))
        mdd = float(stats.get("max_drawdown", 0))
        # Filter: need >= 20 bets to avoid one-shot noise
        if bets < 20:
            continue
        score = sharpe * (1 + max(roi, 0) / 100.0)
        rows.append({
            "strategy_id": sid,
            "name": stats.get("name", sid),
            "total_bets": bets,
            "win_rate": round(wr, 4),
            "roi_pct": round(roi, 3),
            "sharpe": round(sharpe, 3),
            "max_drawdown_pct": round(mdd, 3),
            "final_bankroll": round(bank, 2),
            "score": round(score, 4),
        })
    rows.sort(key=lambda r: (-r["score"], -r["final_bankroll"]))
    return rows[:top_n]


def trader_consistency(seasons: list) -> dict:
    """Count how often each trader made top-20 across the recent seasons."""
    counts = defaultdict(lambda: {
        "appearances": 0,
        "total_seasons": len(seasons),
        "avg_roi": 0.0,
        "avg_sharpe": 0.0,
        "avg_bankroll": 0.0,
        "best_bankroll": 0.0,
    })
    for season in seasons:
        for row in rank_traders(season):
            sid = row["strategy_id"]
            c = counts[sid]
            c["appearances"] += 1
            c["avg_roi"] += row["roi_pct"]
            c["avg_sharpe"] += row["sharpe"]
            c["avg_bankroll"] += row["final_bankroll"]
            c["best_bankroll"] = max(c["best_bankroll"], row["final_bankroll"])
    for sid, c in counts.items():
        a = max(c["appearances"], 1)
        c["avg_roi"] = round(c["avg_roi"] / a, 3)
        c["avg_sharpe"] = round(c["avg_sharpe"] / a, 3)
        c["avg_bankroll"] = round(c["avg_bankroll"] / a, 2)
        c["consistency_pct"] = round(100.0 * c["appearances"] / c["total_seasons"], 1)
    # sort by consistency then avg_sharpe
    ranked = sorted(
        counts.items(),
        key=lambda kv: (-kv[1]["consistency_pct"], -kv[1]["avg_sharpe"])
    )
    return {sid: data for sid, data in ranked[:TOP_N_TRADERS]}


def _init_cat_row(name: str, group: str) -> dict:
    return {
        "name": name,
        "group": group,
        "seasons_seen": 0,
        "total_bets": 0,
        "total_wins": 0,
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "avg_pnl_per_bet": 0.0,
        "status": "pending",    # pending | active | untrained
        "has_model": False,
        # Per-season pnl samples → powers risk-adjusted SOTA ranking below.
        "season_pnls": [],
        "best_season_pnl": 0.0,
        "worst_season_pnl": 0.0,
    }


def _sota_score(r: dict) -> float:
    """
    SOTA category score — risk-adjusted PnL per bet.

    Raw total_pnl is a terrible ranking proxy: it rewards big-volume, high-
    variance categories even when the avg-per-bet is thin, and a single
    lucky season flashes through to the top of the board (prior behaviour).

    Instead we blend four signals:

        base      = avg_pnl_per_bet                         (mean edge)
        maturity  = min(1, seasons_seen / 20)               (sample size)
        consist   = profitable_seasons / seasons_seen       (repeatability)
        volume    = sqrt(log1p(total_bets) / log1p(5000))   (stat reliability)
        risk      = mean_season / (std_season + 1e-6)       (Sharpe-ish)

        score     = base × maturity × consist × volume × sigmoid(risk)

    Negative base → score preserves sign so losers sort last. A category
    with one explosive season and 23 flat seasons lands near zero (consist
    low) even if total_pnl is high. A thin-edge category with 24 consistent
    profitable seasons beats a volatile winner at the same total_pnl — this
    is the "stop rewarding fantasy backtests" anchor.
    """
    import math
    seasons = r["seasons_seen"]
    bets = r["total_bets"]
    if seasons == 0 or bets == 0:
        return 0.0

    base = r["avg_pnl_per_bet"]  # signed
    pnls = r.get("season_pnls") or []
    if len(pnls) >= 2:
        mean = sum(pnls) / len(pnls)
        var = sum((p - mean) ** 2 for p in pnls) / (len(pnls) - 1)
        std = math.sqrt(var)
        sharpe_like = mean / (std + 1e-6)
    else:
        sharpe_like = 0.0

    profitable = sum(1 for p in pnls if p > 0)
    consist = profitable / max(seasons, 1)
    maturity = min(1.0, seasons / 20.0)
    volume = math.sqrt(math.log1p(bets) / math.log1p(5000))

    # Compress sharpe_like with a tanh so extreme single-season flashes
    # (div-by-tiny std) don't dominate the product.
    risk_mult = 0.5 + 0.5 * math.tanh(sharpe_like)

    score = base * maturity * consist * volume * risk_mult
    # Preserve sign of base so losers still rank at the bottom with
    # magnitudes sensibly ordered.
    if base < 0:
        score = -abs(score)
    return float(score)


def build_category_registry(seasons: list) -> dict:
    """
    Accumulate per-category stats across all recent seasons.
    Every one of the 102 ALL_CATEGORIES gets an entry, even if zero bets.

    Champions are now ranked by `_sota_score` (risk-adjusted, consistency-
    weighted), NOT raw total_pnl. See `_sota_score` for rationale.
    """
    registry: dict = {}
    for cat in ALL_CATEGORIES:
        cat_id = cat.id if hasattr(cat, "id") else cat.get("id")
        cat_group = cat.group if hasattr(cat, "group") else cat.get("group", "?")
        cat_name = cat.name if hasattr(cat, "name") else cat.get("name", cat_id)
        registry[cat_id] = _init_cat_row(cat_name, cat_group)

    # Aggregate across seasons
    for season in seasons:
        cat_stats = season.get("category_stats", {}) or {}
        for cat_id, s in cat_stats.items():
            if cat_id not in registry:
                registry[cat_id] = _init_cat_row(cat_id, "unknown")
            r = registry[cat_id]
            bets = int(s.get("bets", 0))
            wins = int(s.get("wins", 0))
            pnl = float(s.get("pnl", 0))
            if bets > 0:
                r["seasons_seen"] += 1
                r["total_bets"] += bets
                r["total_wins"] += wins
                r["total_pnl"] += pnl
                r["season_pnls"].append(round(pnl, 2))
                if pnl > r["best_season_pnl"]:
                    r["best_season_pnl"] = round(pnl, 2)
                if pnl < r["worst_season_pnl"]:
                    r["worst_season_pnl"] = round(pnl, 2)

    # Finalize per-category metrics + status + SOTA score
    coverage = {"active": 0, "untrained": 0, "pending": 0}
    for cat_id, r in registry.items():
        if r["total_bets"] > 0:
            r["win_rate"] = round(r["total_wins"] / r["total_bets"], 4)
            r["avg_pnl_per_bet"] = round(r["total_pnl"] / r["total_bets"], 3)
            r["total_pnl"] = round(r["total_pnl"], 2)
            r["status"] = "active"
            r["has_model"] = True
            # Risk-adjusted metrics
            pnls = r["season_pnls"]
            if pnls:
                mean = sum(pnls) / len(pnls)
                profitable = sum(1 for p in pnls if p > 0)
                r["mean_season_pnl"] = round(mean, 2)
                r["profitable_seasons"] = profitable
                r["consistency"] = round(profitable / len(pnls), 3)
            r["sota_score"] = round(_sota_score(r), 4)
        elif r["seasons_seen"] == 0:
            r["status"] = "untrained"  # category defined but never bet on
            r["sota_score"] = 0.0
        coverage[r["status"]] += 1

    # Champions list: top categories by sota_score with >= 20 bets and
    # >= 2 seasons seen. Require multi-season exposure so single-season
    # flukes can't rank — fantasy-backtest filter.
    eligible = [
        {"category_id": cid, **r}
        for cid, r in registry.items()
        if r["total_bets"] >= 20 and r["seasons_seen"] >= 2
    ]
    eligible.sort(key=lambda c: -c.get("sota_score", 0))
    champions = eligible[:TOP_N_CATEGORIES]

    losers = sorted(eligible, key=lambda c: c.get("sota_score", 0))[:10]

    # Also keep a parallel raw-pnl ranking so the UI can show both views.
    by_raw_pnl = sorted(eligible, key=lambda c: -c["total_pnl"])[:TOP_N_CATEGORIES]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_categories": len(registry),
        "coverage": coverage,
        "ranking_method": "sota_score = avg_pnl_per_bet × maturity × consistency × √volume × σ(sharpe_like)",
        "eligibility": "total_bets >= 20 AND seasons_seen >= 2",
        "registry": registry,
        "champions_top20": champions,
        "champions_top20_by_raw_pnl": by_raw_pnl,
        "losers_bottom10": losers,
    }


def project_to_one_million(leaderboard_top: list, seasons: list) -> dict:
    """
    Given the best trader's typical season performance, project how many
    real-world seasons of identical play are needed to hit $1M.

    Season compounding: bankroll_{t+1} = bankroll_t × (1 + roi_pct/100)
    """
    if not leaderboard_top:
        return {"status": "no_data"}

    # Pick the best trader by avg roi × consistency (already sorted)
    best = leaderboard_top[0]
    avg_roi_pct = best.get("avg_roi", 0)
    best_bankroll = best.get("best_bankroll", STARTING_BANKROLL)
    avg_bankroll = best.get("avg_bankroll", STARTING_BANKROLL)
    consistency = best.get("consistency_pct", 0) / 100.0

    if avg_roi_pct <= 0:
        return {
            "status": "unprofitable",
            "best_strategy": best.get("strategy_id") if isinstance(best, dict) else None,
            "avg_roi_pct": avg_roi_pct,
            "message": "Best trader is unprofitable — $1M unreachable without tuning.",
        }

    # Each season: starting bankroll × (1 + roi/100) → we track how many
    # compounding seasons until $1M
    bank = STARTING_BANKROLL
    seasons_needed = 0
    trajectory = [round(bank, 2)]
    growth_factor = 1 + (avg_roi_pct / 100.0) * max(consistency, 0.5)
    if growth_factor <= 1.0:
        return {
            "status": "unreachable",
            "best_strategy": best.get("strategy_id"),
            "growth_factor": round(growth_factor, 4),
            "message": "Growth factor <= 1.0 after consistency adjustment.",
        }

    while bank < TARGET_BANKROLL and seasons_needed < 500:
        bank *= growth_factor
        seasons_needed += 1
        if seasons_needed <= 50:
            trajectory.append(round(bank, 2))

    # Each backtest season represents one real-world NBA season. But we
    # run 6 backtests/day, so calendar projection = seasons / (6/day).
    calendar_days = round(seasons_needed * (82 / 6.0), 1)
    calendar_nba_seasons = round(seasons_needed / 1.0, 1)

    # Bottleneck analysis
    total_bets_sample = 0
    sample_count = 0
    for season in seasons[-6:]:
        strats = season.get("strategies", {})
        row = strats.get(best["strategy_id"])
        if row:
            total_bets_sample += int(row.get("total_bets", 0))
            sample_count += 1
    avg_bets_per_season = round(total_bets_sample / sample_count, 1) if sample_count else 0

    return {
        "status": "reachable" if seasons_needed < 500 else "very_far",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "best_strategy": best.get("strategy_id"),
        "best_strategy_name": best.get("name", ""),
        "avg_roi_pct": avg_roi_pct,
        "consistency_pct": round(consistency * 100, 1),
        "growth_factor": round(growth_factor, 4),
        "starting_bankroll": STARTING_BANKROLL,
        "target_bankroll": TARGET_BANKROLL,
        "seasons_needed": seasons_needed,
        "calendar_days_estimate": calendar_days,
        "calendar_nba_seasons": calendar_nba_seasons,
        "avg_bets_per_season": avg_bets_per_season,
        "bankroll_trajectory_first_50": trajectory[:51],
        "bottleneck": (
            "volume" if avg_bets_per_season < 50
            else "edge" if avg_roi_pct < 10
            else "consistency" if consistency < 0.5
            else "variance"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Season leaderboard builder")
    parser.add_argument("--recent", type=int, default=DEFAULT_RECENT,
                        help="How many recent backtests to include")
    args = parser.parse_args()

    print(f"[leaderboard] Loading last {args.recent} seasons from {BACKTEST_DIR}")
    seasons = load_recent_seasons(limit=args.recent)
    if not seasons:
        print("[leaderboard] No backtests found — abort")
        return

    print(f"[leaderboard] Loaded {len(seasons)} seasons")

    # Per-season top-20
    per_season = []
    for season in seasons:
        per_season.append({
            "timestamp": season.get("timestamp"),
            "file": season.get("_file"),
            "games_total": season.get("games_total"),
            "model_brier": season.get("model_brier"),
            "top_20": rank_traders(season),
            "debate_verdict_counts": season.get("debate_verdict_counts", {}),
        })

    # Consistency leaderboard across all seasons
    consistency = trader_consistency(seasons)
    consistency_list = [{"strategy_id": k, **v} for k, v in consistency.items()]

    leaderboard = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seasons_analyzed": len(seasons),
        "per_season": per_season,
        "consistency_top20": consistency_list,
        "latest_season_top5": per_season[-1]["top_20"][:5] if per_season else [],
    }
    LEADERBOARD_FILE.write_text(json.dumps(leaderboard, indent=2, default=str))
    print(f"[leaderboard] Wrote {LEADERBOARD_FILE}")

    # Category registry
    registry = build_category_registry(seasons)
    CATEGORY_REGISTRY_FILE.write_text(json.dumps(registry, indent=2, default=str))
    print(f"[leaderboard] Wrote {CATEGORY_REGISTRY_FILE}")
    print(f"[leaderboard]   categories: {registry['total_categories']} "
          f"(active={registry['coverage']['active']}, "
          f"untrained={registry['coverage']['untrained']}, "
          f"pending={registry['coverage']['pending']})")

    # $1M projection
    million = project_to_one_million(consistency_list, seasons)
    MILLION_FILE.write_text(json.dumps(million, indent=2, default=str))
    print(f"[leaderboard] Wrote {MILLION_FILE}")
    if million.get("status") == "reachable":
        print(f"[leaderboard]   ${STARTING_BANKROLL} → ${TARGET_BANKROLL:,} in "
              f"{million['seasons_needed']} seasons "
              f"(~{million['calendar_nba_seasons']} real NBA seasons)")
        print(f"[leaderboard]   best strategy: {million['best_strategy']} "
              f"avg ROI {million['avg_roi_pct']}% "
              f"bottleneck={million['bottleneck']}")
    else:
        print(f"[leaderboard]   status: {million.get('status')}")


if __name__ == "__main__":
    main()
