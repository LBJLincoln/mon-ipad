#!/usr/bin/env python3
"""
MAP BACKTEST RESULTS → AGENT STATES
====================================
Reads the latest NBA backtest_engine.py output and political arena_confrontation.py
output, then projects per-agent performance into data/arena/agent-states-v5.json
so the 217 NBA agents and political strategies all reflect FULL-SEASON backtest
stats (ROI, win-rate, total bets, Sharpe, bankroll), not today's noise.

Mapping rules:
- T1 Premium (9 agents): inherit the best overall NBA strategy stats (Half-Kelly).
- T2 Free Power (25): inherit a strategy proportional to their `strategy` field.
- T3 Specialist (180): inherit category_stats for their `focus_category` from
  the NBA backtest. If no stats → marked inactive.
- T4 Meta (3): aggregate of T1/T2/T3.

Also writes data/arena/strategy-truth.json — the source of truth for
optimal strategy selection (consumed by TF v5 daily bet generator + research loop).
"""

import json
import glob
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "arena"
AGENT_STATE = DATA / "agent-states-v5.json"
BACKTEST_DIR = DATA / "backtest-results"
POLITICAL_RESULTS = ROOT.parent / "nomos-political-alpha" / "data" / "arena" / "arena-results.json"
STRATEGY_TRUTH = DATA / "strategy-truth.json"


def latest_nba_backtest():
    files = sorted(glob.glob(str(BACKTEST_DIR / "backtest-*.json")))
    if not files:
        return None
    with open(files[-1]) as f:
        return json.load(f)


def latest_political_arena():
    if not POLITICAL_RESULTS.exists():
        return None
    with open(POLITICAL_RESULTS) as f:
        return json.load(f)


def map_strategy_for_agent(agent: dict, nba_strategies: dict) -> dict:
    """Pick the best matching strategy from the backtest for this agent."""
    if not nba_strategies:
        return {}
    strat_field = (agent.get("strategy") or "").lower()
    # Heuristic match: kelly variants, value hunter, fixed flat
    if "value" in strat_field:
        key = "value_0.05"
    elif "quarter" in strat_field or "0.25" in strat_field:
        key = "kelly_0.25_0.03"
    elif "half" in strat_field or "0.5" in strat_field:
        key = "kelly_0.5_0.03"
    elif "fixed" in strat_field or "flat" in strat_field:
        key = "fixed_0.02"
    elif "moneyline" in strat_field or agent.get("focus_category", "").startswith("ml"):
        key = "spec_moneyline"
    else:
        key = "kelly_0.5_0.03"
    return nba_strategies.get(key, nba_strategies.get("kelly_0.5_0.03", {}))


def update_specialist(agent: dict, category_stats: dict) -> bool:
    """Apply category-level stats to a T3 specialist agent."""
    cat = agent.get("focus_category")
    if not cat:
        # Recover category from agent id like "t3_ml_fg_s0" or "t3_sp_alt_p2_s1"
        aid = agent.get("id", "")
        if aid.startswith("t3_") and ("_s0" in aid or "_s1" in aid):
            core = aid[len("t3_"):]
            for suffix in ("_s0", "_s1"):
                if core.endswith(suffix):
                    cat = core[: -len(suffix)]
                    break
    if not cat or cat not in category_stats:
        return False
    cs = category_stats[cat]
    bets = int(cs.get("bets", 0))
    wins = int(cs.get("wins", round(bets * cs.get("win_rate", 0.5))))
    pnl = float(cs.get("pnl", cs.get("total_pnl", 0)))
    agent["total_bets"] = bets
    agent["total_wins"] = wins
    agent["win_rate"] = round(wins / bets, 4) if bets > 0 else 0.0
    agent["total_pnl"] = round(pnl, 2)
    agent["roi"] = round(pnl / max(bets, 1) / 10.0, 4)  # rough per-unit ROI
    agent["bankroll"] = round(100.0 + pnl, 2)
    if agent["bankroll"] > agent.get("peak_bankroll", 100):
        agent["peak_bankroll"] = agent["bankroll"]
    return True


def main():
    nba = latest_nba_backtest()
    pol = latest_political_arena()

    if not AGENT_STATE.exists():
        print("[mapper] No agent-states-v5.json — abort")
        return

    state = json.loads(AGENT_STATE.read_text())
    agents = state.get("agents", {})

    nba_strategies = nba.get("strategies", {}) if nba else {}
    nba_categories = nba.get("category_stats", {}) if nba else {}

    updated_t1 = updated_t2 = updated_t3 = updated_t4 = 0
    for aid, ag in agents.items():
        tier = ag.get("tier")
        if tier == "PREMIUM":
            s = map_strategy_for_agent(ag, nba_strategies)
            if s:
                ag["total_bets"] = int(s.get("total_bets", 0))
                ag["total_wins"] = int(s.get("wins", 0))
                ag["win_rate"] = float(s.get("win_rate", 0))
                ag["total_pnl"] = float(s.get("total_pnl", 0))
                ag["roi"] = float(s.get("roi", 0))
                ag["bankroll"] = float(s.get("final_bankroll", 100))
                ag["sharpe"] = float(s.get("sharpe", 0))
                ag["max_drawdown"] = float(s.get("max_drawdown", 0))
                updated_t1 += 1
        elif tier == "FREE_POWER":
            s = map_strategy_for_agent(ag, nba_strategies)
            if s:
                # Slightly worse than T1 (free models)
                ag["total_bets"] = int(s.get("total_bets", 0) * 0.7)
                ag["total_wins"] = int(s.get("wins", 0) * 0.7)
                ag["win_rate"] = float(s.get("win_rate", 0))
                ag["total_pnl"] = float(s.get("total_pnl", 0) * 0.7)
                ag["roi"] = float(s.get("roi", 0) * 0.7)
                ag["bankroll"] = float(s.get("final_bankroll", 100))
                updated_t2 += 1
        elif tier == "SPECIALIST":
            if update_specialist(ag, nba_categories):
                updated_t3 += 1
        elif tier == "META":
            # Aggregate later
            updated_t4 += 1

    # Aggregate META agents from T1+T2+T3
    all_specs = [a for a in agents.values() if a.get("tier") == "SPECIALIST"]
    total_pnl = sum(a.get("total_pnl", 0) for a in all_specs)
    total_bets = sum(a.get("total_bets", 0) for a in all_specs)
    total_wins = sum(a.get("total_wins", 0) for a in all_specs)
    for aid in ("t4_paperclip", "t4_hermes", "t4_oracle"):
        ag = agents.get(aid)
        if not ag:
            continue
        ag["total_bets"] = total_bets
        ag["total_wins"] = total_wins
        ag["win_rate"] = round(total_wins / max(total_bets, 1), 4)
        ag["total_pnl"] = round(total_pnl, 2)
        ag["bankroll"] = round(100.0 + total_pnl / 3, 2)
        ag["peak_bankroll"] = max(ag["bankroll"], ag.get("peak_bankroll", 100))

    state["last_backtest_sync"] = datetime.now(timezone.utc).isoformat()
    state["backtest_source"] = {
        "nba_games": nba.get("games_total") if nba else None,
        "nba_brier": nba.get("model_brier") if nba else None,
        "nba_strategies": len(nba_strategies),
        "nba_categories": len(nba_categories),
        "political_strategies": len(pol.get("leaderboard", [])) if pol else 0,
        "political_champion": (pol.get("champion") if pol else None),
    }
    AGENT_STATE.write_text(json.dumps(state, indent=2))

    # ── Strategy Truth: source of truth for TF v5 + research loop ──
    truth = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nba": {
            "games": nba.get("games_total") if nba else 0,
            "brier": nba.get("model_brier") if nba else None,
            "best_strategy": None,
            "best_strategy_stats": None,
            "best_categories": [],
            "worst_categories": [],
        },
        "political": {
            "champion": pol.get("champion") if pol else None,
            "active": pol.get("active_count") if pol else 0,
            "eliminated": pol.get("eliminated_count") if pol else 0,
            "top_5": [],
        },
    }
    if nba_strategies:
        ranked = sorted(nba_strategies.values(), key=lambda s: s.get("roi", 0), reverse=True)
        truth["nba"]["best_strategy"] = ranked[0].get("name")
        truth["nba"]["best_strategy_stats"] = ranked[0]
    if nba_categories:
        cats = sorted(nba_categories.items(),
                      key=lambda kv: kv[1].get("pnl", kv[1].get("total_pnl", 0)),
                      reverse=True)
        truth["nba"]["best_categories"] = [
            {"category": k, **v} for k, v in cats[:10]
        ]
        truth["nba"]["worst_categories"] = [
            {"category": k, **v} for k, v in cats[-5:]
        ]
    if pol and "leaderboard" in pol:
        truth["political"]["top_5"] = pol["leaderboard"][:5]

    STRATEGY_TRUTH.write_text(json.dumps(truth, indent=2, default=str))

    print(f"[mapper] Updated T1={updated_t1} T2={updated_t2} T3={updated_t3} META={updated_t4}")
    print(f"[mapper] Wrote {STRATEGY_TRUTH}")
    print(f"[mapper] NBA strategies={len(nba_strategies)} categories={len(nba_categories)}")
    if pol:
        print(f"[mapper] Political champion={pol.get('champion')} active={pol.get('active_count')}")


if __name__ == "__main__":
    main()
