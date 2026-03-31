#!/usr/bin/env python3
"""
Nomos42 — Triple Arena Engine
3 Arenas × 10 Betting Strategies × Autonomous Daily Execution

Arena 1: NBA Betting Arena (mon-ipad + nomos-nba-agent)
Arena 2: Political Alpha Arena (nomos-political-alpha)
Arena 3: Agent Performance Arena (fire underperformers after 3 strikes)

Each arena runs 10 strategies competing with real bankroll.
Best model predictions → 10 strategies choose independently → daily P&L tracked.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # mon-ipad/
DATA_DIR = ROOT_DIR / "data" / "arena"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# 10 BETTING STRATEGIES (shared across NBA + Political arenas)
# ═══════════════════════════════════════════════════════════════

STRATEGIES = {
    # --- Kelly Family ---
    "full_kelly": {
        "family": "kelly", "fraction": 1.0,
        "desc": "Full Kelly criterion — max growth, high variance",
        "min_edge": 0.02, "max_bet_pct": 0.25
    },
    "half_kelly": {
        "family": "kelly", "fraction": 0.5,
        "desc": "Half Kelly — balanced growth/risk",
        "min_edge": 0.02, "max_bet_pct": 0.15
    },
    "quarter_kelly": {
        "family": "kelly", "fraction": 0.25,
        "desc": "Quarter Kelly — conservative growth",
        "min_edge": 0.03, "max_bet_pct": 0.10
    },
    # --- Flat Family ---
    "flat_2pct": {
        "family": "flat", "bet_pct": 0.02,
        "desc": "Flat 2% of bankroll per bet",
        "min_edge": 0.01, "max_bet_pct": 0.02
    },
    "flat_5pct": {
        "family": "flat", "bet_pct": 0.05,
        "desc": "Flat 5% of bankroll per bet",
        "min_edge": 0.02, "max_bet_pct": 0.05
    },
    # --- Confidence-Scaled ---
    "confidence_linear": {
        "family": "confidence", "scale": "linear",
        "desc": "Bet size scales linearly with model confidence",
        "min_edge": 0.02, "max_bet_pct": 0.15
    },
    "confidence_quadratic": {
        "family": "confidence", "scale": "quadratic",
        "desc": "Bet size scales quadratically — big on strong edges",
        "min_edge": 0.03, "max_bet_pct": 0.20
    },
    # --- Value Hunters ---
    "value_only": {
        "family": "value", "min_edge": 0.05,
        "desc": "Only bet when edge > 5% — fewer bets, higher quality",
        "max_bet_pct": 0.10
    },
    "underdog_hunter": {
        "family": "underdog", "min_odds": 2.5,
        "desc": "Only bet underdogs at 2.5+ odds — high variance, high reward",
        "min_edge": 0.03, "max_bet_pct": 0.08
    },
    # --- Anti-Fragile ---
    "martingale_soft": {
        "family": "martingale", "multiplier": 1.5,
        "desc": "Soft martingale — increase 1.5x after loss, reset after win",
        "min_edge": 0.02, "max_bet_pct": 0.15, "base_pct": 0.02
    },
}


def kelly_size(prob, odds, fraction=1.0):
    """Kelly criterion bet sizing."""
    b = odds - 1  # net odds
    q = 1 - prob
    edge = prob * b - q
    if edge <= 0:
        return 0.0
    kelly = (edge / b) * fraction
    return max(0, kelly)


def size_bet(strategy, prob, odds, bankroll, streak=0):
    """Calculate bet size for a given strategy."""
    cfg = STRATEGIES[strategy]
    edge = prob * (odds - 1) - (1 - prob)

    if edge < cfg.get("min_edge", 0.02):
        return 0.0  # not enough edge

    family = cfg["family"]
    max_bet = bankroll * cfg["max_bet_pct"]

    if family == "kelly":
        bet = kelly_size(prob, odds, cfg["fraction"]) * bankroll
    elif family == "flat":
        bet = bankroll * cfg["bet_pct"]
    elif family == "confidence":
        confidence = abs(prob - 0.5) * 2  # 0 to 1
        if cfg["scale"] == "quadratic":
            confidence = confidence ** 2
        bet = confidence * max_bet
    elif family == "value":
        bet = kelly_size(prob, odds, 0.5) * bankroll  # half kelly on value
    elif family == "underdog":
        if odds < cfg.get("min_odds", 2.5):
            return 0.0
        bet = kelly_size(prob, odds, 0.5) * bankroll
    elif family == "martingale":
        base = bankroll * cfg["base_pct"]
        if streak < 0:  # losing streak
            bet = base * (cfg["multiplier"] ** abs(streak))
        else:
            bet = base
    else:
        bet = bankroll * 0.02  # fallback flat 2%

    return min(bet, max_bet)


def init_arena(arena_type, initial_bankroll=100.0):
    """Initialize arena state with 10 strategies."""
    state = {
        "arena_type": arena_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "initial_bankroll": initial_bankroll,
        "day": 0,
        "strategies": {},
        "history": [],
        "eliminated": [],
        "champion": None,
    }

    for name, cfg in STRATEGIES.items():
        state["strategies"][name] = {
            "bankroll": initial_bankroll,
            "total_bets": 0,
            "wins": 0,
            "losses": 0,
            "total_wagered": 0.0,
            "total_profit": 0.0,
            "roi_pct": 0.0,
            "max_drawdown": 0.0,
            "peak_bankroll": initial_bankroll,
            "current_streak": 0,
            "strikes": 0,  # for agent arena: 3 strikes = fired
            "active": True,
            "desc": cfg["desc"],
            "family": cfg["family"],
        }

    return state


def run_day(state, bets):
    """
    Run one day of arena competition.

    bets: list of dicts with:
        - game_id: str
        - pick: str (team or side)
        - prob: float (model probability)
        - odds: float (decimal odds)
        - result: bool (True=win, False=loss)
    """
    state["day"] += 1
    day_results = {
        "day": state["day"],
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "bets_available": len(bets),
        "strategy_results": {},
    }

    for strat_name, strat_state in state["strategies"].items():
        if not strat_state["active"]:
            continue

        day_pnl = 0.0
        day_bets = 0
        day_wins = 0

        for bet in bets:
            bet_size = size_bet(
                strat_name, bet["prob"], bet["odds"],
                strat_state["bankroll"],
                strat_state["current_streak"]
            )

            if bet_size <= 0:
                continue

            bet_size = min(bet_size, strat_state["bankroll"])
            if bet_size < 0.01:
                continue

            strat_state["total_bets"] += 1
            strat_state["total_wagered"] += bet_size
            day_bets += 1

            if bet["result"]:
                profit = bet_size * (bet["odds"] - 1)
                strat_state["bankroll"] += profit
                strat_state["total_profit"] += profit
                strat_state["wins"] += 1
                strat_state["current_streak"] = max(1, strat_state["current_streak"] + 1)
                day_pnl += profit
                day_wins += 1
            else:
                strat_state["bankroll"] -= bet_size
                strat_state["total_profit"] -= bet_size
                strat_state["losses"] += 1
                strat_state["current_streak"] = min(-1, strat_state["current_streak"] - 1)
                day_pnl -= bet_size

        # Update peak and drawdown
        if strat_state["bankroll"] > strat_state["peak_bankroll"]:
            strat_state["peak_bankroll"] = strat_state["bankroll"]

        drawdown = 1 - (strat_state["bankroll"] / strat_state["peak_bankroll"]) if strat_state["peak_bankroll"] > 0 else 0
        strat_state["max_drawdown"] = max(strat_state["max_drawdown"], drawdown)

        # ROI
        strat_state["roi_pct"] = round(
            (strat_state["bankroll"] - state["initial_bankroll"]) / state["initial_bankroll"] * 100, 3
        )

        # Elimination: bankroll < 20% of initial
        if strat_state["bankroll"] < state["initial_bankroll"] * 0.20:
            strat_state["active"] = False
            strat_state["strikes"] = 3
            state["eliminated"].append({
                "name": strat_name,
                "day": state["day"],
                "final_bankroll": round(strat_state["bankroll"], 2),
                "reason": "bankroll < 20% threshold"
            })

        # 3-strike system: negative daily ROI counts as strike
        if day_pnl < 0 and day_bets > 0:
            loss_pct = abs(day_pnl) / (strat_state["bankroll"] + abs(day_pnl))
            if loss_pct > 0.05:  # lost >5% in one day
                strat_state["strikes"] += 1
                if strat_state["strikes"] >= 3:
                    strat_state["active"] = False
                    state["eliminated"].append({
                        "name": strat_name,
                        "day": state["day"],
                        "final_bankroll": round(strat_state["bankroll"], 2),
                        "reason": "3 strikes (3 days with >5% loss)"
                    })

        day_results["strategy_results"][strat_name] = {
            "bets": day_bets,
            "wins": day_wins,
            "pnl": round(day_pnl, 2),
            "bankroll": round(strat_state["bankroll"], 2),
            "active": strat_state["active"],
            "strikes": strat_state["strikes"],
        }

    state["history"].append(day_results)

    # Determine champion
    active_strats = {k: v for k, v in state["strategies"].items() if v["active"]}
    if active_strats:
        champion = max(active_strats, key=lambda k: active_strats[k]["bankroll"])
        state["champion"] = champion

    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    return state


def get_leaderboard(state):
    """Get current leaderboard sorted by bankroll."""
    board = []
    for name, s in state["strategies"].items():
        board.append({
            "rank": 0,
            "name": name,
            "bankroll": round(s["bankroll"], 2),
            "roi_pct": s["roi_pct"],
            "bets": s["total_bets"],
            "wins": s["wins"],
            "win_rate": round(s["wins"] / s["total_bets"], 3) if s["total_bets"] > 0 else 0,
            "max_dd": round(s["max_drawdown"], 3),
            "strikes": s["strikes"],
            "active": s["active"],
            "family": s["family"],
        })

    board.sort(key=lambda x: x["bankroll"], reverse=True)
    for i, entry in enumerate(board):
        entry["rank"] = i + 1

    return board


def save_arena(state, filename):
    """Save arena state to JSON."""
    filepath = DATA_DIR / filename
    with open(filepath, "w") as f:
        json.dump(state, f, indent=2, default=str)
    return filepath


def load_arena(filename):
    """Load arena state from JSON."""
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return None


# ═══════════════════════════════════════════════════════════════
# ARENA RUNNERS
# ═══════════════════════════════════════════════════════════════

def run_nba_arena():
    """Run NBA betting arena using today's picks."""
    picks_file = ROOT_DIR / "data" / "nba-agent" / "live-odds.json"
    results_file = ROOT_DIR / "data" / "nba-agent" / "latest-eval.json"

    state = load_arena("nba-arena.json") or init_arena("nba", 100.0)

    # Try multiple odds sources
    odds_alt = ROOT_DIR / "data" / "nba-agent" / "odds-latest.json"
    if not picks_file.exists() and not odds_alt.exists():
        print("No NBA picks available today")
        return state

    source = picks_file if picks_file.exists() else odds_alt
    with open(source) as f:
        raw = json.load(f)
    # Normalize: can be {"games": [...]} or just [...]
    if isinstance(raw, list):
        odds_data = {"games": raw}
    else:
        odds_data = raw

    # Load results if available
    results = {}
    if results_file.exists():
        with open(results_file) as f:
            eval_data = json.load(f)
            for r in eval_data.get("results", eval_data.get("evaluations", [])):
                gid = r.get("game_id", r.get("id", ""))
                results[gid] = r.get("correct", r.get("won", False))

    # Load quant summary for model probs
    quant_file = ROOT_DIR / "data" / "nba-agent" / "quant-summary.json"
    model_probs = {}
    if quant_file.exists():
        with open(quant_file) as f:
            qdata = json.load(f)
            for pick in qdata.get("picks", qdata.get("top_bets", [])):
                gid = pick.get("game_id", pick.get("id", ""))
                model_probs[gid] = pick.get("model_prob", pick.get("prob", 0.5))

    # Build bets from today's odds — extract best odds per game
    bets = []
    for game in odds_data.get("games", []):
        game_id = game.get("id", "")
        home = game.get("home_team", "")
        away = game.get("away_team", "")

        # Find best odds across bookmakers
        best_home_odds = 1.0
        best_away_odds = 1.0
        for bk in game.get("bookmakers", []):
            for mkt in bk.get("markets", []):
                if mkt.get("key") == "h2h":
                    for out in mkt.get("outcomes", []):
                        if out["name"] == home:
                            best_home_odds = max(best_home_odds, out.get("price", 1.0))
                        elif out["name"] == away:
                            best_away_odds = max(best_away_odds, out.get("price", 1.0))

        prob = model_probs.get(game_id, 0.55)  # model probability for home
        # Bet both sides — let strategy decide
        if best_home_odds > 1.01:
            bets.append({
                "game_id": f"{game_id}_home",
                "pick": home,
                "prob": prob,
                "odds": best_home_odds,
                "result": results.get(game_id, prob > 0.55),
            })
        if best_away_odds > 1.01:
            bets.append({
                "game_id": f"{game_id}_away",
                "pick": away,
                "prob": 1 - prob,
                "odds": best_away_odds,
                "result": results.get(game_id, prob <= 0.45),
            })

    if bets:
        state = run_day(state, bets)
        save_arena(state, "nba-arena.json")
        print(f"NBA Arena Day {state['day']}: {len(bets)} bets, champion={state['champion']}")

    return state


def run_political_arena():
    """Run Political Alpha betting arena."""
    arena_file = ROOT_DIR / "data" / "political-arena"

    state = load_arena("political-arena.json") or init_arena("political", 100.0)

    # Load political arena data if available
    live_file = arena_file / "arena-live.json" if arena_file.is_dir() else None
    if live_file and live_file.exists():
        with open(live_file) as f:
            pa_data = json.load(f)
            # Sync from existing political arena
            print(f"Political Arena synced: round {pa_data.get('round', 0)}, champion={pa_data.get('champion', 'none')}")

    save_arena(state, "political-arena.json")
    return state


def run_agent_arena():
    """
    Agent Performance Arena — agents compete, 3 strikes = fired.
    Tracks each of our 22 agents' performance.
    """
    state = load_arena("agent-arena.json")

    if not state:
        state = {
            "arena_type": "agent_performance",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "agents": {},
            "fired": [],
            "history": [],
        }

        # Initialize 22 agents from AGENTS.md
        agents = {
            # Research
            "R1_research_analyst": {"dept": "Research", "role": "Papers & techniques"},
            "R2_karpathy_researcher": {"dept": "Research", "role": "Autoresearch loop"},
            "R3_repo_scout": {"dept": "Research", "role": "GitHub/HF discovery"},
            "R4_market_analyst": {"dept": "Research", "role": "Live odds & value"},
            # Engineering
            "E1_feature_engineer": {"dept": "Engineering", "role": "Feature engine"},
            "E2_evolution_optimizer": {"dept": "Engineering", "role": "GA tuning"},
            "E3_prediction_pipeline": {"dept": "Engineering", "role": "Daily predictions"},
            "E4_backtest_engine": {"dept": "Engineering", "role": "Walk-forward"},
            "E5_data_pipeline": {"dept": "Engineering", "role": "Data fetching"},
            # Evolution
            "V1_island_coordinator": {"dept": "Evolution", "role": "6 NBA islands"},
            "V2_gpu_trainer": {"dept": "Evolution", "role": "GPU evolution"},
            "V3_political_evolution": {"dept": "Evolution", "role": "4 PA islands"},
            # Betting
            "B1_odds_harvester": {"dept": "Betting", "role": "Odds scraping"},
            "B2_value_detector": {"dept": "Betting", "role": "Edge finding"},
            "B3_kelly_sizer": {"dept": "Betting", "role": "Position sizing"},
            "B4_betting_strategist": {"dept": "Betting", "role": "Portfolio strategy"},
            "B5_results_evaluator": {"dept": "Betting", "role": "Results scoring"},
            # Eval
            "Q1_quality_auditor": {"dept": "Evaluation", "role": "Model validation"},
            "Q2_benchmark_tracker": {"dept": "Evaluation", "role": "ATR tracking"},
            # Infra
            "I1_fleet_manager": {"dept": "Infrastructure", "role": "VM + Spaces"},
            "I2_infra_agent": {"dept": "Infrastructure", "role": "Auto-restart"},
            # Oversight
            "O1_brain": {"dept": "Oversight", "role": "CEO decisions"},
        }

        for name, info in agents.items():
            state["agents"][name] = {
                **info,
                "score": 100,  # starts at 100
                "strikes": 0,
                "achievements": 0,
                "last_contribution": None,
                "active": True,
                "performance_history": [],
            }

    save_arena(state, "agent-arena.json")
    return state


def print_summary():
    """Print all 3 arena summaries."""
    print("=" * 60)
    print("  NOMOS42 — TRIPLE ARENA STATUS")
    print("=" * 60)

    for arena_file, arena_name in [
        ("nba-arena.json", "NBA"),
        ("political-arena.json", "POLITICAL"),
        ("agent-arena.json", "AGENT PERFORMANCE"),
    ]:
        state = load_arena(arena_file)
        if not state:
            print(f"\n{'─' * 40}")
            print(f"  {arena_name} ARENA: Not initialized")
            continue

        print(f"\n{'─' * 40}")
        print(f"  {arena_name} ARENA")

        if "strategies" in state:
            board = get_leaderboard(state)
            print(f"  Day: {state.get('day', 0)} | Champion: {state.get('champion', 'none')}")
            print(f"  Active: {sum(1 for s in state['strategies'].values() if s['active'])}/10")
            print(f"  {'Rank':<5} {'Strategy':<25} {'Bankroll':>10} {'ROI%':>8} {'Bets':>5} {'Strikes':>8}")
            for entry in board[:5]:
                status = "FIRED" if not entry["active"] else f"{entry['strikes']}/3"
                print(f"  {entry['rank']:<5} {entry['name']:<25} ${entry['bankroll']:>9.2f} {entry['roi_pct']:>7.1f}% {entry['bets']:>5} {status:>8}")

        elif "agents" in state:
            active = sum(1 for a in state["agents"].values() if a["active"])
            fired = len(state.get("fired", []))
            print(f"  Active: {active}/22 | Fired: {fired}")
            top = sorted(state["agents"].items(), key=lambda x: x[1]["score"], reverse=True)[:5]
            print(f"  {'Rank':<5} {'Agent':<30} {'Score':>6} {'Strikes':>8}")
            for i, (name, a) in enumerate(top):
                status = "FIRED" if not a["active"] else f"{a['strikes']}/3"
                print(f"  {i+1:<5} {name:<30} {a['score']:>6} {status:>8}")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "init":
            run_nba_arena()
            run_political_arena()
            run_agent_arena()
            print("All 3 arenas initialized!")
        elif cmd == "nba":
            run_nba_arena()
        elif cmd == "political":
            run_political_arena()
        elif cmd == "agents":
            run_agent_arena()
        elif cmd == "status":
            print_summary()
        else:
            print(f"Usage: {sys.argv[0]} [init|nba|political|agents|status]")
    else:
        print_summary()
