#!/usr/bin/env python3
"""
Full-Season Arena Backtest — ALL 60 competitors × ALL games × ALL bankroll daily
Joins games-2025-26.json (results) with nba_2025-26_odds.csv (closing lines)
Produces complete ROI/Sharpe/drawdown for each model×strategy combo.
"""
import json, csv, math, sys, os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent.parent
NBA_DIR = Path("/home/termius/nomos-nba-agent")

# ═══════════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════════

def load_games():
    """Load game results: {(date, home, away) -> {home_score, away_score}}"""
    fp = NBA_DIR / "data" / "historical" / "games-2025-26.json"
    raw = json.load(open(fp))
    games = raw.get("games", raw if isinstance(raw, list) else [])

    # Normalize team abbreviations
    team_map = {
        "Los Angeles Lakers": "LAL", "Los Angeles Clippers": "LAC",
        "Golden State Warriors": "GSW", "Boston Celtics": "BOS",
        "Oklahoma City Thunder": "OKC", "Houston Rockets": "HOU",
        "Cleveland Cavaliers": "CLE", "New York Knicks": "NYK",
        "Milwaukee Bucks": "MIL", "Denver Nuggets": "DEN",
        "Phoenix Suns": "PHX", "Dallas Mavericks": "DAL",
        "Memphis Grizzlies": "MEM", "Minnesota Timberwolves": "MIN",
        "Sacramento Kings": "SAC", "Indiana Pacers": "IND",
        "Miami Heat": "MIA", "Philadelphia 76ers": "PHI",
        "Orlando Magic": "ORL", "Atlanta Hawks": "ATL",
        "Chicago Bulls": "CHI", "Toronto Raptors": "TOR",
        "Brooklyn Nets": "BKN", "San Antonio Spurs": "SAS",
        "Detroit Pistons": "DET", "Charlotte Hornets": "CHA",
        "Portland Trail Blazers": "POR", "New Orleans Pelicans": "NOP",
        "Utah Jazz": "UTA", "Washington Wizards": "WAS",
    }

    results = {}
    for g in games:
        date = g.get("game_date", "")
        home = g.get("home_team", "")
        away = g.get("away_team", "")
        h_data = g.get("home", {})
        a_data = g.get("away", {})

        # Get scores
        hs = h_data.get("pts", h_data.get("PTS", 0))
        as_ = a_data.get("pts", a_data.get("PTS", 0))
        if not hs and not as_:
            continue

        # Map team names to abbreviations
        home_abbr = team_map.get(home, home)
        away_abbr = team_map.get(away, away)

        results[(date, home_abbr, away_abbr)] = {
            "home_score": hs, "away_score": as_,
            "home_stats": h_data, "away_stats": a_data,
        }
    return results


def load_odds():
    """Load season odds: {(date, home_abbr, away_abbr) -> odds_dict}"""
    fp = NBA_DIR / "data" / "historical-odds" / "nba_2025-26_odds.csv"
    if not fp.exists():
        return {}

    team_map = {
        "Los Angeles Lakers": "LAL", "Los Angeles Clippers": "LAC",
        "Golden State Warriors": "GSW", "Boston Celtics": "BOS",
        "Oklahoma City Thunder": "OKC", "Houston Rockets": "HOU",
        "Cleveland Cavaliers": "CLE", "New York Knicks": "NYK",
        "Milwaukee Bucks": "MIL", "Denver Nuggets": "DEN",
        "Phoenix Suns": "PHX", "Dallas Mavericks": "DAL",
        "Memphis Grizzlies": "MEM", "Minnesota Timberwolves": "MIN",
        "Sacramento Kings": "SAC", "Indiana Pacers": "IND",
        "Miami Heat": "MIA", "Philadelphia 76ers": "PHI",
        "Orlando Magic": "ORL", "Atlanta Hawks": "ATL",
        "Chicago Bulls": "CHI", "Toronto Raptors": "TOR",
        "Brooklyn Nets": "BKN", "San Antonio Spurs": "SAS",
        "Detroit Pistons": "DET", "Charlotte Hornets": "CHA",
        "Portland Trail Blazers": "POR", "New Orleans Pelicans": "NOP",
        "Utah Jazz": "UTA", "Washington Wizards": "WAS",
    }

    odds = {}
    with open(fp) as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row["date"]
            home = team_map.get(row["home_team"], row["home_team"])
            away = team_map.get(row["away_team"], row["away_team"])

            try:
                ml_home_str = row.get("moneyline_home", "").strip()
                ml_away_str = row.get("moneyline_away", "").strip()
                spread_str = row.get("spread_home", "").strip()
                total_str = row.get("total", "").strip()

                spread = float(spread_str) if spread_str else None
                total = float(total_str) if total_str else None

                def parse_odds(s):
                    """Parse odds — handles both American (+150, -200) and decimal (1.33, 2.50)"""
                    if not s: return None
                    v = float(s)
                    if 1.0 < v < 15.0 and '.' in s:
                        # Decimal odds already
                        return v
                    else:
                        # American odds
                        v = int(float(s))
                        if v > 0: return v / 100.0 + 1
                        if v < 0: return 100.0 / abs(v) + 1
                        return 2.0

                ml_home_dec = parse_odds(ml_home_str)
                ml_away_dec = parse_odds(ml_away_str)

                if ml_home_dec and ml_away_dec:
                    odds[(date, home, away)] = {
                        "ml_home_dec": ml_home_dec,
                        "ml_away_dec": ml_away_dec,
                        "spread_home": spread,
                        "total": total,
                    }
            except (ValueError, TypeError):
                continue
    return odds


# ═══════════════════════════════════════════════════════════════
# MODELS & STRATEGIES (same as arena-engine.py)
# ═══════════════════════════════════════════════════════════════

MODELS = {
    "tabicl":        {"brier": 0.2157, "noise": 0.015},
    "catboost":      {"brier": 0.2204, "noise": 0.020},
    "xgboost":       {"brier": 0.2205, "noise": 0.020},
    "lightgbm":      {"brier": 0.2208, "noise": 0.022},
    "extra_trees":   {"brier": 0.2225, "noise": 0.025},
    "random_forest": {"brier": 0.2245, "noise": 0.028},
}

STRATEGIES = {
    "full_kelly":        {"family": "kelly", "fraction": 1.0,  "min_edge": 0.02, "max_pct": 0.25, "cats": "all"},
    "half_kelly":        {"family": "kelly", "fraction": 0.5,  "min_edge": 0.02, "max_pct": 0.15, "cats": "all"},
    "quarter_kelly":     {"family": "kelly", "fraction": 0.25, "min_edge": 0.03, "max_pct": 0.08, "cats": "all"},
    "flat_2pct":         {"family": "flat",  "bet_pct": 0.02,  "min_edge": 0.01, "max_pct": 0.02, "cats": "all"},
    "flat_5pct":         {"family": "flat",  "bet_pct": 0.05,  "min_edge": 0.02, "max_pct": 0.05, "cats": "all"},
    "confidence_scaled": {"family": "confidence",              "min_edge": 0.02, "max_pct": 0.20, "cats": "all"},
    "value_hunter":      {"family": "value",                   "min_edge": 0.05, "max_pct": 0.12, "cats": "all"},
    "underdog_specialist": {"family": "underdog", "min_odds": 2.2, "min_edge": 0.03, "max_pct": 0.08, "cats": ["ml_away"]},
    "totals_expert":     {"family": "kelly", "fraction": 0.5,  "min_edge": 0.02, "max_pct": 0.15, "cats": ["total_over", "total_under"]},
    "first_half_sniper": {"family": "kelly", "fraction": 0.5,  "min_edge": 0.02, "max_pct": 0.15, "cats": ["ml_home", "ml_away"]},
    "full_blast":        {"family": "full_blast", "min_edge": 0.01, "max_pct": 1.00, "cats": "all"},
}


def kelly_size(p, odds, fraction=1.0):
    b = odds - 1
    if b <= 0: return 0.0
    edge = p * b - (1 - p)
    if edge <= 0: return 0.0
    return max(0, (edge / b) * fraction)


def get_bet_size(strat_name, prob, odds, bankroll):
    cfg = STRATEGIES[strat_name]
    edge = prob * (odds - 1) - (1 - prob)
    if edge < cfg["min_edge"]: return 0.0
    if cfg["family"] == "underdog" and odds < cfg.get("min_odds", 2.2): return 0.0

    max_bet = bankroll * cfg["max_pct"]
    if cfg["family"] == "kelly":
        bet = kelly_size(prob, odds, cfg["fraction"]) * bankroll
    elif cfg["family"] == "flat":
        bet = bankroll * cfg["bet_pct"]
    elif cfg["family"] == "confidence":
        conf = (abs(prob - 0.5) * 2) ** 2
        bet = conf * max_bet
    elif cfg["family"] in ("value", "underdog"):
        bet = kelly_size(prob, odds, 0.5) * bankroll
    elif cfg["family"] == "full_blast":
        # 100% bankroll on best edge bet of the day
        bet = bankroll
    else:
        bet = bankroll * 0.02
    return min(max(bet, 0), max_bet)


def model_prob(model_name, implied_prob, seed_val):
    """Generate model probability with deterministic noise based on model quality."""
    import hashlib
    noise_std = MODELS[model_name]["noise"]
    # Deterministic noise from seed
    h = int(hashlib.md5(f"{model_name}_{seed_val}".encode()).hexdigest()[:8], 16)
    # Box-Muller for deterministic gaussian
    u1 = (h % 10000) / 10000.0 + 0.0001
    u2 = ((h // 10000) % 10000) / 10000.0 + 0.0001
    noise = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2) * noise_std
    return max(0.05, min(0.95, implied_prob + noise))


# ═══════════════════════════════════════════════════════════════
# FULL SEASON SIMULATION
# ═══════════════════════════════════════════════════════════════

def run_full_season():
    print("Loading data...")
    games = load_games()
    odds = load_odds()
    print(f"Games with results: {len(games)}")
    print(f"Games with odds: {len(odds)}")

    # Match games with odds
    matched = []
    for key in sorted(odds.keys()):
        if key in games:
            matched.append((key, games[key], odds[key]))

    print(f"Matched (results + odds): {len(matched)}")
    if not matched:
        print("ERROR: No matched games. Check team name mapping.")
        return

    # Group by date for daily simulation
    days = defaultdict(list)
    for key, result, odd in matched:
        days[key[0]].append((key, result, odd))

    sorted_days = sorted(days.keys())
    print(f"Playing days: {len(sorted_days)}")
    print(f"Date range: {sorted_days[0]} → {sorted_days[-1]}")

    # Initialize 60 competitors
    competitors = {}
    for m in MODELS:
        for s in STRATEGIES:
            k = f"{m}__{s}"
            competitors[k] = {
                "model": m, "strategy": s,
                "bankroll": 100.0, "peak": 100.0,
                "bets": 0, "wins": 0, "losses": 0,
                "total_wagered": 0.0, "total_profit": 0.0,
                "max_drawdown": 0.0,
                "daily_returns": [],
                "active": True,
                "bankroll_history": [100.0],
            }

    # Run day by day
    for day_idx, date in enumerate(sorted_days):
        day_games = days[date]

        for comp_key, comp in competitors.items():
            if not comp["active"]:
                comp["bankroll_history"].append(comp["bankroll"])
                continue

            m = comp["model"]
            s = comp["strategy"]
            cfg = STRATEGIES[s]
            day_pnl = 0.0
            start_bankroll = comp["bankroll"]

            # For full_blast: collect all candidate bets first, pick only the best one
            is_full_blast = (cfg["family"] == "full_blast")
            candidate_bets = []  # (edge, bet_odds, bet_won, bet_type, game_key)

            for (key, result, odd) in day_games:
                date_str, home, away = key
                hs = result["home_score"]
                as_ = result["away_score"]
                home_won = hs > as_

                # Available bets for this game
                bets_available = {}
                if odd["ml_home_dec"]:
                    bets_available["ml_home"] = (odd["ml_home_dec"], home_won)
                if odd["ml_away_dec"]:
                    bets_available["ml_away"] = (odd["ml_away_dec"], not home_won)
                if odd["spread_home"] is not None:
                    margin = hs - as_
                    covered = margin > -odd["spread_home"]
                    bets_available["spread_home"] = (1.91, covered)
                    bets_available["spread_away"] = (1.91, not covered)
                if odd["total"] is not None:
                    game_total = hs + as_
                    bets_available["total_over"] = (1.91, game_total > odd["total"])
                    bets_available["total_under"] = (1.91, game_total < odd["total"])

                # Implied probability from moneyline
                impl_home = 1.0 / odd["ml_home_dec"] if odd["ml_home_dec"] else 0.5
                prob = model_prob(m, impl_home, f"{date_str}_{home}_{away}")

                # Map probabilities for each bet type
                bet_probs = {
                    "ml_home": prob,
                    "ml_away": 1 - prob,
                    "spread_home": 0.52 + (prob - 0.5) * 0.3,
                    "spread_away": 0.48 + (0.5 - prob) * 0.3,
                    "total_over": 0.50 + (prob - 0.5) * 0.15,
                    "total_under": 0.50 - (prob - 0.5) * 0.15,
                }

                for bet_type, (bet_odds, bet_won) in bets_available.items():
                    cats = cfg["cats"]
                    if cats != "all" and bet_type not in cats:
                        continue

                    bp = bet_probs.get(bet_type, 0.5)

                    if is_full_blast:
                        # Collect candidate, pick best edge later
                        edge = bp * (bet_odds - 1) - (1 - bp)
                        if edge >= cfg["min_edge"]:
                            candidate_bets.append((edge, bet_odds, bet_won, bet_type, f"{date_str}_{home}_{away}"))
                        continue

                    bet_size = get_bet_size(s, bp, bet_odds, comp["bankroll"])

                    if bet_size < 0.01 or bet_size > comp["bankroll"]:
                        continue

                    comp["bets"] += 1
                    comp["total_wagered"] += bet_size

                    if bet_won:
                        profit = bet_size * (bet_odds - 1)
                        comp["bankroll"] += profit
                        comp["total_profit"] += profit
                        comp["wins"] += 1
                        day_pnl += profit
                    else:
                        comp["bankroll"] -= bet_size
                        comp["total_profit"] -= bet_size
                        comp["losses"] += 1
                        day_pnl -= bet_size

            # Full blast: bet 100% bankroll on highest-edge bet of the day
            if is_full_blast and candidate_bets and comp["bankroll"] >= 0.01:
                candidate_bets.sort(key=lambda x: x[0], reverse=True)
                best_edge, best_odds, best_won, best_type, best_game = candidate_bets[0]
                bet_size = comp["bankroll"]
                comp["bets"] += 1
                comp["total_wagered"] += bet_size
                if best_won:
                    profit = bet_size * (best_odds - 1)
                    comp["bankroll"] += profit
                    comp["total_profit"] += profit
                    comp["wins"] += 1
                    day_pnl += profit
                else:
                    comp["bankroll"] -= bet_size
                    comp["total_profit"] -= bet_size
                    comp["losses"] += 1
                    day_pnl -= bet_size

            # Update peak/drawdown
            if comp["bankroll"] > comp["peak"]:
                comp["peak"] = comp["bankroll"]
            if comp["peak"] > 0:
                dd = 1 - comp["bankroll"] / comp["peak"]
                comp["max_drawdown"] = max(comp["max_drawdown"], dd)

            # Daily return
            if start_bankroll > 0:
                comp["daily_returns"].append(day_pnl / start_bankroll)
            else:
                comp["daily_returns"].append(0)

            comp["bankroll_history"].append(comp["bankroll"])

            # Elimination
            if comp["bankroll"] < 5.0:  # Below $5
                comp["active"] = False

    # ═══════════════════════════════════════════════════════════════
    # RESULTS
    # ═══════════════════════════════════════════════════════════════

    # Calculate final metrics
    for k, c in competitors.items():
        c["roi_pct"] = round((c["bankroll"] - 100) / 100 * 100, 2)
        rets = c["daily_returns"]
        if rets and len(rets) > 1:
            avg_r = sum(rets) / len(rets)
            std_r = (sum((r - avg_r) ** 2 for r in rets) / len(rets)) ** 0.5
            c["sharpe"] = round(avg_r / std_r * math.sqrt(252) if std_r > 0 else 0, 2)
        else:
            c["sharpe"] = 0

    # Sort by final bankroll
    board = sorted(competitors.items(), key=lambda x: x[1]["bankroll"], reverse=True)

    # Print results
    print(f"\n{'='*90}")
    print(f"  FULL-SEASON ARENA — {len(matched)} games × 60 competitors × all bankroll daily")
    print(f"  Season: {sorted_days[0]} → {sorted_days[-1]} ({len(sorted_days)} days)")
    print(f"{'='*90}")

    # Top 20
    print(f"\n  {'#':<3} {'Competitor':<35} {'Bankroll':>10} {'ROI':>8} {'Sharpe':>7} {'Bets':>6} {'W/L':>10} {'DD':>6} {'Active':>6}")
    print(f"  {'─'*3} {'─'*35} {'─'*10} {'─'*8} {'─'*7} {'─'*6} {'─'*10} {'─'*6} {'─'*6}")
    for i, (k, v) in enumerate(board[:20]):
        wl = f"{v['wins']}/{v['losses']}"
        status = "YES" if v["active"] else "BUST"
        print(f"  {i+1:<3} {k:<35} ${v['bankroll']:>8.2f} {v['roi_pct']:>7.1f}% {v['sharpe']:>6.2f} {v['bets']:>6} {wl:>10} {v['max_drawdown']:>5.1%} {status:>6}")

    # Best per strategy
    print(f"\n  BEST MODEL PER STRATEGY:")
    print(f"  {'Strategy':<25} {'Best Model':<15} {'Bankroll':>10} {'ROI':>8} {'Sharpe':>7}")
    for strat in STRATEGIES:
        strat_comps = [(k, v) for k, v in board if v["strategy"] == strat]
        if strat_comps:
            best_k, best_v = strat_comps[0]
            model = best_v["model"]
            print(f"  {strat:<25} {model:<15} ${best_v['bankroll']:>8.2f} {best_v['roi_pct']:>7.1f}% {best_v['sharpe']:>6.2f}")

    # Best per model
    print(f"\n  BEST STRATEGY PER MODEL:")
    print(f"  {'Model':<20} {'Best Strategy':<25} {'Bankroll':>10} {'ROI':>8} {'Sharpe':>7}")
    for model in MODELS:
        model_comps = [(k, v) for k, v in board if v["model"] == model]
        if model_comps:
            best_k, best_v = model_comps[0]
            strat = best_v["strategy"]
            print(f"  {model:<20} {strat:<25} ${best_v['bankroll']:>8.2f} {best_v['roi_pct']:>7.1f}% {best_v['sharpe']:>6.2f}")

    # Stats
    alive = sum(1 for k, v in competitors.items() if v["active"])
    profitable = sum(1 for k, v in competitors.items() if v["bankroll"] > 100)
    avg_roi = sum(v["roi_pct"] for v in competitors.values()) / len(competitors)
    print(f"\n  SUMMARY:")
    print(f"    Active: {alive}/60 | Profitable: {profitable}/60 | Avg ROI: {avg_roi:.1f}%")
    print(f"    Best: {board[0][0]} → ${board[0][1]['bankroll']:.2f} ({board[0][1]['roi_pct']:.1f}%)")
    print(f"    Worst: {board[-1][0]} → ${board[-1][1]['bankroll']:.2f} ({board[-1][1]['roi_pct']:.1f}%)")

    # Save results
    out = {
        "meta": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "games_matched": len(matched),
            "playing_days": len(sorted_days),
            "date_range": f"{sorted_days[0]} to {sorted_days[-1]}",
            "competitors": 60,
        },
        "leaderboard": [
            {
                "rank": i + 1,
                "name": k,
                "model": v["model"],
                "strategy": v["strategy"],
                "bankroll": round(v["bankroll"], 2),
                "roi_pct": v["roi_pct"],
                "sharpe": v["sharpe"],
                "bets": v["bets"],
                "wins": v["wins"],
                "losses": v["losses"],
                "max_drawdown": round(v["max_drawdown"], 4),
                "active": v["active"],
                "bankroll_history": [round(b, 2) for b in v["bankroll_history"]],
            }
            for i, (k, v) in enumerate(board)
        ],
    }

    out_file = ROOT / "data" / "arena" / "nba-arena-full-season.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Saved to {out_file}")


if __name__ == "__main__":
    run_full_season()
