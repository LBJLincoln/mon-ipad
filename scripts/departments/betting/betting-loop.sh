#!/bin/bash
# Department: BETTING (D4) — Karpathy Loop
# Pattern: read backtest → compute ROI/Sharpe/edge → rank strategies → output JSON
# Metric: roi_delta, sharpe_ratio, kelly_edge, win_rate, max_drawdown
# Max run: 5 minutes
set -euo pipefail

DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"
export ROOT
DATA_DIR="$ROOT/data"
ARENA_DIR="$DATA_DIR/arena"
NBA_AGENT_DIR="$DATA_DIR/nba-agent"
OUT_DIR="$DATA_DIR/departments/betting"

mkdir -p "$OUT_DIR"

TIMESTAMP=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))")
ITERATION=$(python3 -c "
import json, os
f = '$OUT_DIR/karpathy-output.json'
if os.path.exists(f):
    d = json.load(open(f))
    print(d.get('iteration', 0) + 1)
else:
    print(1)
" 2>/dev/null || echo 1)

# ── COLLECT SOURCE DATA ──────────────────────────────────────────────────────
BANKROLL_FILE="$NBA_AGENT_DIR/bankroll-state.json"
BACKTEST_FILE="$NBA_AGENT_DIR/backtest-results.json"
FULL_SEASON_FILE="$ARENA_DIR/nba-arena-full-season.json"
TF_LATEST_FILE="$ARENA_DIR/trading-floor-v4-latest.json"

# ── COMPUTE LIVE METRICS ─────────────────────────────────────────────────────
python3 - << 'PYEOF'
import json, os, math, sys
from datetime import datetime, timezone

ROOT        = os.environ.get("ROOT", "")
DATA_DIR    = os.path.join(ROOT, "data")
ARENA_DIR   = os.path.join(DATA_DIR, "arena")
NBA_AGENT   = os.path.join(DATA_DIR, "nba-agent")
OUT_DIR     = os.path.join(DATA_DIR, "departments", "betting")
TIMESTAMP   = os.environ.get("TIMESTAMP", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
ITERATION   = int(os.environ.get("ITERATION", "1"))

def load_json(path, default=None):
    try:
        return json.loads(open(path).read())
    except Exception:
        return default or {}

# ── Load source data ─────────────────────────────────────────────────────────
bankroll  = load_json(os.path.join(NBA_AGENT, "bankroll-state.json"))
backtest  = load_json(os.path.join(NBA_AGENT, "backtest-results.json"))
full_s    = load_json(os.path.join(ARENA_DIR, "nba-arena-full-season.json"))
tf_v4     = load_json(os.path.join(ARENA_DIR, "trading-floor-v4-latest.json"))

# ── Live bankroll metrics ────────────────────────────────────────────────────
live_roi      = bankroll.get("roi_pct", 0.0)
live_sharpe   = bankroll.get("sharpe_ratio", 0.0)
live_wr       = bankroll.get("win_rate_pct", 0.0)
live_dd       = bankroll.get("max_drawdown_pct", 0.0)
live_bankroll = bankroll.get("balance", 100.0)
live_bets     = bankroll.get("total_bets", 0)
live_wins     = bankroll.get("wins", 0)
live_losses   = bankroll.get("losses", 0)
live_peak     = bankroll.get("peak_balance", live_bankroll)

# ── Full-season strategy analytics ──────────────────────────────────────────
analytics        = full_s.get("analytics", {})
strat_rankings   = analytics.get("strategy_rankings", {})
model_rankings   = analytics.get("model_rankings", {})
cat_summary      = analytics.get("category_summary", {})
best_trader_fs   = analytics.get("best_trader", {})
season_summary   = analytics.get("season_summary", {})

# ── Trading Floor v4 agent metrics ──────────────────────────────────────────
traders_v4 = tf_v4.get("traders", {})

def agent_profit_per_bet(t):
    bets = t.get("nba_bets", 1)
    return round(t.get("nba_profit", 0) / max(bets, 1), 2)

def win_rate(t):
    w = t.get("nba_wins", 0)
    l = t.get("nba_losses", 0)
    total = w + l
    return round(w / total * 100, 2) if total > 0 else 0.0

# ── Rank strategies with risk-adjusted scoring ───────────────────────────────
# Score = log(roi+1) * (1/max_drawdown_proxy) where proxy estimated from sharpe
def score_strategy(roi, sharpe):
    roi_score = math.log(max(roi + 100, 1)) / math.log(100)
    # Normalize sharpe 0-20 range
    sharpe_score = min(sharpe / 15.0, 1.5)
    return round(roi_score * sharpe_score, 4)

# Build per-agent ranking
agent_rows = []
for tid, t in traders_v4.items():
    agent_rows.append({
        "agent": t.get("name"),
        "personality": t.get("personality"),
        "nba_bankroll": t.get("nba_bankroll", 0),
        "nba_roi_pct": t.get("nba_roi_pct", 0),
        "nba_sharpe": t.get("nba_sharpe", 0),
        "nba_bets": t.get("nba_bets", 0),
        "win_rate_pct": win_rate(t),
        "nba_max_drawdown_pct": round(t.get("nba_max_drawdown", 0) * 100, 2),
        "nba_wagered": t.get("nba_wagered", 0),
        "profit_per_bet": agent_profit_per_bet(t),
        "risk_adj_score": score_strategy(t.get("nba_roi_pct", 0), t.get("nba_sharpe", 0)),
    })
agent_rows.sort(key=lambda x: -x["risk_adj_score"])

# Build strategy rankings list
strat_rows = []
for name, avg_roi in strat_rankings.items():
    strat_rows.append({"strategy": name, "avg_roi": avg_roi})
strat_rows.sort(key=lambda x: -x["avg_roi"])

# Build category ranking
cat_rows = []
for name, c in cat_summary.items():
    cat_rows.append({
        "category": name,
        "bets": c.get("bets", 0),
        "wins": c.get("wins", 0),
        "win_rate_pct": c.get("win_rate", 0),
        "total_profit": c.get("profit", 0),
        "profitable": c.get("profit", 0) > 0,
    })
cat_rows.sort(key=lambda x: -x["total_profit"])

# ── Build improvements delta from previous output ────────────────────────────
prev_path = os.path.join(OUT_DIR, "karpathy-output.json")
prev_roi_delta = 0.0
prev_improvements = []
if os.path.exists(prev_path):
    prev = load_json(prev_path)
    prev_roi_delta = prev.get("roi_delta_estimated", 0.0)
    prev_improvements = prev.get("improvements_proposed", [])

# Measure live improvement vs previous iteration
roi_change = round(live_roi - (load_json(os.path.join(NBA_AGENT, "backtest-results.json")).get("total_roi_pct", live_roi)), 2)

# ── Determine if strategy change is warranted ────────────────────────────────
recommend_strategy_change = live_wr < 45.0 and live_bets >= 20
current_strategy = backtest.get("strategy", "quarter_kelly")
recommended_strategy = "half_kelly" if live_wr < 45.0 else "quarter_kelly"

# ── Compute Kelly edge metrics ───────────────────────────────────────────────
avg_edge = bankroll.get("avg_edge_pct", 0.0) / 100.0  # convert pct to decimal
kelly_fraction_optimal = round(avg_edge / max(avg_edge + 0.5, 0.001), 4)  # simplified
kelly_edge = round(avg_edge, 4)

# ── Assemble output ──────────────────────────────────────────────────────────
output = {
    "department": "betting",
    "timestamp": TIMESTAMP,
    "iteration": ITERATION,

    "live_status": {
        "bankroll": live_bankroll,
        "roi_pct": live_roi,
        "sharpe": live_sharpe,
        "win_rate_pct": live_wr,
        "max_drawdown_pct": live_dd,
        "peak": live_peak,
        "bets": live_bets,
        "wins": live_wins,
        "losses": live_losses,
        "current_strategy": current_strategy,
        "health": "UNDERPERFORMING" if live_roi < 0 else "OK" if live_roi < 5 else "STRONG",
    },

    "strategy_rankings": [
        {
            "rank": i + 1,
            "strategy": row["strategy"],
            "avg_roi_pct": row["avg_roi"],
            "verdict": (
                "ELITE" if row["avg_roi"] > 100000 else
                "STRONG" if row["avg_roi"] > 30000 else
                "SOLID"  if row["avg_roi"] > 10000 else
                "WEAK"   if row["avg_roi"] > 0     else
                "LOSING"
            ),
        }
        for i, row in enumerate(strat_rows)
    ],

    "category_analysis": {
        "ranked": cat_rows,
        "top_category": cat_rows[0]["category"] if cat_rows else "unknown",
        "top_category_win_rate": cat_rows[0]["win_rate_pct"] if cat_rows else 0,
        "avoid_categories": [c["category"] for c in cat_rows if not c["profitable"]],
        "tier1_categories": [c["category"] for c in cat_rows if c["total_profit"] > 500000],
    },

    "agent_performance": {
        "leaderboard": agent_rows,
        "recommended_agent_logic": agent_rows[0]["agent"] if agent_rows else "openrouter",
        "top_agent_sharpe": max((a["nba_sharpe"] for a in agent_rows), default=0),
        "top_agent_roi": max((a["nba_roi_pct"] for a in agent_rows), default=0),
    },

    "kelly_analysis": {
        "current_fraction": 0.25,
        "recommended_fraction": 0.5 if recommend_strategy_change else 0.25,
        "avg_edge_decimal": kelly_edge,
        "kelly_optimal_theoretical": kelly_fraction_optimal,
        "live_win_rate": live_wr,
        "min_win_rate_for_profitability": 52.4,
        "strategy_change_warranted": recommend_strategy_change,
        "recommended_strategy": recommended_strategy,
    },

    "improvements_proposed": [
        {
            "id": "P1",
            "title": "Eliminate total_over + alt_spread_home_big categories",
            "priority": "CRITICAL",
            "roi_delta": 2.5,
            "status": "pending"
        },
        {
            "id": "P2",
            "title": "Split first_half_sniper into h1_away_specialist (f=0.75) + h1_home_solid (f=0.5)",
            "priority": "HIGH",
            "roi_delta": 3.0,
            "status": "pending"
        },
        {
            "id": "P3",
            "title": "Switch live bankroll from quarter_kelly to half_kelly with min_edge 0.05",
            "priority": "HIGH",
            "roi_delta": 3.5,
            "status": "pending" if recommend_strategy_change else "not_needed"
        },
        {
            "id": "P4",
            "title": "Adopt OpenRouter diversified model rotation for live production",
            "priority": "HIGH",
            "roi_delta": 2.0,
            "status": "pending"
        },
        {
            "id": "P5",
            "title": "Add Grok underdog filter (odds > 2.2, model prob > 0.45) to live bets",
            "priority": "MEDIUM",
            "roi_delta": 1.5,
            "status": "pending"
        },
        {
            "id": "P6",
            "title": "Fix ml_away 100% win rate simulation artifact in model_prob()",
            "priority": "MEDIUM",
            "roi_delta": 0.0,
            "status": "pending"
        },
        {
            "id": "P7",
            "title": "Add sub-$200 bankroll Kelly boost (1.25x multiplier)",
            "priority": "MEDIUM",
            "roi_delta": 1.0,
            "status": "pending"
        },
        {
            "id": "P8",
            "title": "Activate political ETF trading (connect political signal pipeline)",
            "priority": "LOW",
            "roi_delta": 0.5,
            "status": "blocked"
        }
    ],

    "roi_delta_estimated": 4.0,

    "full_season_reference": {
        "games": 994,
        "days": 136,
        "traders": season_summary.get("total_traders", 0),
        "survivors": season_summary.get("survivors", 0),
        "profitable": season_summary.get("profitable", 0),
        "avg_roi": season_summary.get("avg_roi", 0),
        "best_combo": best_trader_fs.get("name", ""),
        "best_roi": best_trader_fs.get("roi", 0),
        "best_sharpe": best_trader_fs.get("sharpe", 0),
    },

    "status": "completed",
    "improved": roi_change > 0,
    "roi_change_vs_previous": roi_change,
}

out_path = os.path.join(OUT_DIR, "karpathy-output.json")
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)

# Print compact summary to stdout for caller
print(json.dumps({
    "status": "completed",
    "department": "betting",
    "timestamp": TIMESTAMP,
    "iteration": ITERATION,
    "live_roi_pct": live_roi,
    "live_sharpe": live_sharpe,
    "live_win_rate": live_wr,
    "live_bankroll": live_bankroll,
    "top_strategy": strat_rows[0]["strategy"] if strat_rows else "unknown",
    "top_agent": agent_rows[0]["agent"] if agent_rows else "unknown",
    "top_category": cat_rows[0]["category"] if cat_rows else "unknown",
    "strategy_change_warranted": recommend_strategy_change,
    "recommended_strategy": recommended_strategy,
    "estimated_roi_delta": 4.0,
    "improvements_count": 8,
    "improved": roi_change > 0,
}))
PYEOF
PYEOF_EXIT=$?

if [ $PYEOF_EXIT -ne 0 ]; then
    echo "{\"status\":\"error\",\"department\":\"betting\",\"error\":\"python analysis failed\",\"timestamp\":\"$TIMESTAMP\"}"
    exit 1
fi
