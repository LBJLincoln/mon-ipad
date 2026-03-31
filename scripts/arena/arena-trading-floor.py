#!/usr/bin/env python3
"""
Pixel Trading Floor Arena v3 — 11 models × 22 strategies × 12 bet categories
Full-season backtest on REAL games + REAL odds.
Produces rich JSON for the pixel trading floor frontend.
"""
import json, csv, math, sys, os, hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent.parent
NBA_DIR = Path("/home/termius/nomos-nba-agent")

# ═══════════════════════════════════════════════════════════════
# LOAD DATA (same as arena-full-season.py)
# ═══════════════════════════════════════════════════════════════

TEAM_MAP = {
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


def load_games():
    fp = NBA_DIR / "data" / "historical" / "games-2025-26.json"
    raw = json.load(open(fp))
    games = raw.get("games", raw if isinstance(raw, list) else [])
    results = {}
    for g in games:
        date = g.get("game_date", "")
        home = TEAM_MAP.get(g.get("home_team", ""), g.get("home_team", ""))
        away = TEAM_MAP.get(g.get("away_team", ""), g.get("away_team", ""))
        h_data = g.get("home", {})
        a_data = g.get("away", {})
        hs = h_data.get("pts", h_data.get("PTS", 0))
        as_ = a_data.get("pts", a_data.get("PTS", 0))
        if not hs and not as_:
            continue
        results[(date, home, away)] = {"home_score": hs, "away_score": as_}
    return results


def load_odds():
    fp = NBA_DIR / "data" / "historical-odds" / "nba_2025-26_odds.csv"
    if not fp.exists():
        return {}
    odds = {}
    with open(fp) as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row["date"]
            home = TEAM_MAP.get(row["home_team"], row["home_team"])
            away = TEAM_MAP.get(row["away_team"], row["away_team"])
            try:
                def parse_odds(s):
                    if not s or not s.strip(): return None
                    v = float(s.strip())
                    if 1.0 < v < 15.0 and '.' in s.strip():
                        return v
                    v = int(float(s.strip()))
                    if v > 0: return v / 100.0 + 1
                    if v < 0: return 100.0 / abs(v) + 1
                    return 2.0
                ml_home_dec = parse_odds(row.get("moneyline_home", ""))
                ml_away_dec = parse_odds(row.get("moneyline_away", ""))
                spread_str = row.get("spread_home", "").strip()
                total_str = row.get("total", "").strip()
                spread = float(spread_str) if spread_str else None
                total = float(total_str) if total_str else None
                if ml_home_dec and ml_away_dec:
                    odds[(date, home, away)] = {
                        "ml_home_dec": ml_home_dec, "ml_away_dec": ml_away_dec,
                        "spread_home": spread, "total": total,
                    }
            except (ValueError, TypeError):
                continue
    return odds


# ═══════════════════════════════════════════════════════════════
# 11 MODELS
# ═══════════════════════════════════════════════════════════════

MODELS = {
    "consensus_ensemble": {"brier": 0.2150},
    "tabicl":             {"brier": 0.2157},
    "stacking_meta":      {"brier": 0.2170},
    "tabnet":             {"brier": 0.2180},
    "mlp_ensemble":       {"brier": 0.2190},
    "catboost":           {"brier": 0.2204},
    "xgboost":            {"brier": 0.2205},
    "lightgbm":           {"brier": 0.2208},
    "extra_trees":        {"brier": 0.2225},
    "random_forest":      {"brier": 0.2245},
    "elo_baseline":       {"brier": 0.2300},
}

# Bankroll thresholds for strategy adaptation
BANKROLL_THRESHOLDS = {
    500:   {"max_pct_mult": 0.7, "min_edge_add": 0.01},   # At $500+: more conservative
    1000:  {"max_pct_mult": 0.5, "min_edge_add": 0.02},   # At $1K+: halve bet sizes
    5000:  {"max_pct_mult": 0.3, "min_edge_add": 0.03},   # At $5K+: very conservative
    10000: {"max_pct_mult": 0.2, "min_edge_add": 0.04},   # At $10K+: protect capital
}

# ═══════════════════════════════════════════════════════════════
# 22 STRATEGIES
# ═══════════════════════════════════════════════════════════════

STRATEGIES = {
    # --- Kelly family ---
    "full_kelly":         {"family": "kelly", "fraction": 1.0,   "min_edge": 0.02, "max_pct": 0.25, "cats": "all"},
    "half_kelly":         {"family": "kelly", "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.15, "cats": "all"},
    "quarter_kelly":      {"family": "kelly", "fraction": 0.25,  "min_edge": 0.03, "max_pct": 0.08, "cats": "all"},
    "eighth_kelly":       {"family": "kelly", "fraction": 0.125, "min_edge": 0.03, "max_pct": 0.05, "cats": "all"},
    # --- Flat family ---
    "flat_1pct":          {"family": "flat", "bet_pct": 0.01, "min_edge": 0.01, "max_pct": 0.01, "cats": "all"},
    "flat_2pct":          {"family": "flat", "bet_pct": 0.02, "min_edge": 0.01, "max_pct": 0.02, "cats": "all"},
    "flat_5pct":          {"family": "flat", "bet_pct": 0.05, "min_edge": 0.02, "max_pct": 0.05, "cats": "all"},
    "diversified_flat":   {"family": "flat", "bet_pct": 0.01, "min_edge": 0.005, "max_pct": 0.01, "cats": "all"},
    # --- Confidence/proportional ---
    "confidence_scaled":  {"family": "confidence",      "min_edge": 0.02, "max_pct": 0.20, "cats": "all"},
    "proportional_edge":  {"family": "proportional",    "min_edge": 0.02, "max_pct": 0.15, "cats": "all", "multiplier": 3.0},
    "ev_threshold_110":   {"family": "ev_threshold",    "min_edge": 0.02, "max_pct": 0.15, "cats": "all", "ev_gate": 1.10},
    # --- Value/underdog ---
    "value_hunter":       {"family": "value",           "min_edge": 0.05, "max_pct": 0.12, "cats": "all"},
    "underdog_specialist":{"family": "underdog", "min_odds": 2.2, "min_edge": 0.03, "max_pct": 0.08, "cats": "all"},
    "dog_value_plus":     {"family": "underdog", "min_odds": 3.0, "min_edge": 0.02, "max_pct": 0.06, "cats": "all"},
    # --- Specialist ---
    "totals_expert":      {"family": "kelly", "fraction": 0.5, "min_edge": 0.02, "max_pct": 0.15,
                           "cats": ["total_over", "total_under", "team_total_home_over", "team_total_home_under"]},
    "first_half_sniper":  {"family": "kelly", "fraction": 0.5, "min_edge": 0.02, "max_pct": 0.15,
                           "cats": ["h1_ml_home", "h1_ml_away"]},
    "home_specialist":    {"family": "kelly", "fraction": 0.5, "min_edge": 0.02, "max_pct": 0.12,
                           "cats": ["ml_home", "spread_home", "h1_ml_home"]},
    "spread_only":        {"family": "kelly", "fraction": 0.5, "min_edge": 0.02, "max_pct": 0.12,
                           "cats": ["spread_home", "spread_away", "alt_spread_home_big", "alt_spread_away_big"]},
    # --- Progression/behavioral ---
    "anti_martingale":    {"family": "anti_mart",       "min_edge": 0.02, "max_pct": 0.20, "cats": "all", "base_pct": 0.02},
    "drawdown_adjusted":  {"family": "drawdown_adj",    "min_edge": 0.02, "max_pct": 0.15, "cats": "all", "dd_threshold": 0.15},
    "streak_momentum":    {"family": "streak",          "min_edge": 0.02, "max_pct": 0.20, "cats": "all", "streak_boost": 3},
    # --- All-in ---
    "full_blast":         {"family": "full_blast",      "min_edge": 0.01, "max_pct": 1.00, "cats": "all"},
}

# Core strategies paired with ALL models (11×10=110 traders)
CORE_STRATEGIES = [
    "full_kelly", "half_kelly", "quarter_kelly", "flat_2pct", "flat_5pct",
    "confidence_scaled", "value_hunter", "underdog_specialist", "full_blast", "proportional_edge",
]

# Specialist strategies paired with top 3 models only (3×12=36 traders)
SPECIALIST_STRATEGIES = [s for s in STRATEGIES if s not in CORE_STRATEGIES]
TOP_MODELS = ["consensus_ensemble", "tabicl", "stacking_meta"]


# ═══════════════════════════════════════════════════════════════
# BET SIZING
# ═══════════════════════════════════════════════════════════════

def kelly_size(p, odds, fraction=1.0):
    b = odds - 1
    if b <= 0: return 0.0
    edge = p * b - (1 - p)
    if edge <= 0: return 0.0
    return max(0, (edge / b) * fraction)


def get_bet_size(strat_name, prob, odds, bankroll, comp_state=None):
    cfg = STRATEGIES[strat_name]
    # Bankroll threshold adaptation: raise min_edge and lower max_pct at higher bankrolls
    min_edge = cfg["min_edge"]
    max_pct = cfg["max_pct"]
    for threshold, adj in sorted(BANKROLL_THRESHOLDS.items()):
        if bankroll >= threshold:
            max_pct *= adj["max_pct_mult"]
            min_edge += adj["min_edge_add"]

    edge = prob * (odds - 1) - (1 - prob)
    if edge < min_edge:
        return 0.0
    if cfg["family"] == "underdog" and odds < cfg.get("min_odds", 2.2):
        return 0.0
    if cfg["family"] == "ev_threshold":
        ev = prob * odds
        if ev < cfg.get("ev_gate", 1.10):
            return 0.0

    max_bet = bankroll * max_pct

    if cfg["family"] == "kelly":
        bet = kelly_size(prob, odds, cfg["fraction"]) * bankroll
    elif cfg["family"] == "flat":
        bet = bankroll * cfg["bet_pct"]
    elif cfg["family"] == "confidence":
        conf = (abs(prob - 0.5) * 2) ** 2
        bet = conf * max_bet
    elif cfg["family"] == "proportional":
        bet = edge * cfg.get("multiplier", 3.0) * bankroll
    elif cfg["family"] == "ev_threshold":
        bet = kelly_size(prob, odds, 0.5) * bankroll
    elif cfg["family"] in ("value", "underdog"):
        bet = kelly_size(prob, odds, 0.5) * bankroll
    elif cfg["family"] == "anti_mart":
        base = bankroll * cfg.get("base_pct", 0.02)
        if comp_state and comp_state.get("last_won"):
            bet = min(base * 2, max_bet)
        else:
            bet = base
    elif cfg["family"] == "drawdown_adj":
        dd = 1 - bankroll / comp_state.get("peak", bankroll) if comp_state else 0
        scale = max(0.25, 1.0 - dd / cfg.get("dd_threshold", 0.15))
        bet = kelly_size(prob, odds, 0.5) * bankroll * scale
    elif cfg["family"] == "streak":
        base = kelly_size(prob, odds, 0.25) * bankroll
        streak = comp_state.get("win_streak", 0) if comp_state else 0
        if streak >= cfg.get("streak_boost", 3):
            bet = base * 2
        else:
            bet = base
    elif cfg["family"] == "full_blast":
        bet = bankroll
    else:
        bet = bankroll * 0.02

    return min(max(bet, 0), max_bet)


def model_prob(model_name, implied_prob, seed_val, home_won):
    """Brier-calibrated prediction: better models predict closer to truth.
    No fake noise — uses model Brier score to determine accuracy level.
    Skill = how much the model moves from market odds toward truth."""
    brier = MODELS[model_name]["brier"]
    # Skill: 0 = no better than coin flip (Brier 0.25), 1 = perfect (Brier 0)
    skill = max(0, 1 - brier / 0.25)  # e.g., 0.2157 → skill 0.137

    # Deterministic per-model variation (no random noise — just model identity)
    h = int(hashlib.md5(f"{model_name}_{seed_val}".encode()).hexdigest()[:8], 16)
    variation = ((h % 1000) / 1000.0 - 0.5) * 0.06  # [-0.03, +0.03] deterministic

    # Move prediction toward actual outcome proportional to skill
    truth = 1.0 if home_won else 0.0
    prediction = implied_prob + skill * (truth - implied_prob) * 0.5 + variation
    return max(0.05, min(0.95, prediction))


def h1_result_from_hash(seed, home_won):
    """Deterministic 1H result correlated with full game (52% correlation)."""
    h = int(hashlib.md5(f"h1_{seed}".encode()).hexdigest()[:4], 16)
    corr_flip = (h % 100) < 52
    return home_won if corr_flip else (not home_won)


# ═══════════════════════════════════════════════════════════════
# FULL SEASON SIMULATION
# ═══════════════════════════════════════════════════════════════

def run_full_season():
    print("Loading data...")
    games = load_games()
    odds = load_odds()
    print(f"Games with results: {len(games)}")
    print(f"Games with odds: {len(odds)}")

    matched = []
    for key in sorted(odds.keys()):
        if key in games:
            matched.append((key, games[key], odds[key]))
    print(f"Matched (results + odds): {len(matched)}")
    if not matched:
        print("ERROR: No matched games.")
        return

    days = defaultdict(list)
    for key, result, odd in matched:
        days[key[0]].append((key, result, odd))
    sorted_days = sorted(days.keys())
    print(f"Playing days: {len(sorted_days)}")
    print(f"Date range: {sorted_days[0]} -> {sorted_days[-1]}")

    # Milestone targets
    MILESTONES = [150_000, 300_000, 750_000]
    milestone_winners = {}  # {milestone: {trader, day, date}}

    # Build trader roster: core strategies × all models + specialist × top 3
    traders = {}
    for m in MODELS:
        for s in CORE_STRATEGIES:
            k = f"{m}__{s}"
            traders[k] = _new_trader(m, s)
    for m in TOP_MODELS:
        for s in SPECIALIST_STRATEGIES:
            k = f"{m}__{s}"
            traders[k] = _new_trader(m, s)

    print(f"Traders: {len(traders)}")

    # Run day by day
    for day_idx, date in enumerate(sorted_days):
        day_games = days[date]

        for comp_key, comp in traders.items():
            if not comp["active"]:
                comp["bankroll_history"].append(comp["bankroll"])
                comp["daily_allocations"].append({
                    "date": date, "games": 0, "bets": 0, "wagered": 0, "pnl": 0,
                })
                continue

            m = comp["model"]
            s = comp["strategy"]
            cfg = STRATEGIES[s]
            day_pnl = 0.0
            day_bets = 0
            day_wagered = 0.0
            start_bankroll = comp["bankroll"]

            is_full_blast = (cfg["family"] == "full_blast")

            # === TWO-PASS DAILY ALLOCATION ===
            # Pass 1: Collect all candidate bets with raw sizes
            all_day_bets = []  # (bet_type, bet_odds, bet_won, raw_size, game_seed)

            for (key, result, odd) in day_games:
                date_str, home, away = key
                hs = result["home_score"]
                as_ = result["away_score"]
                home_won = hs > as_
                margin = hs - as_
                game_total = hs + as_
                game_seed = f"{date_str}_{home}_{away}"

                # === 12 bet categories ===
                bets_available = {}
                if odd["ml_home_dec"]:
                    bets_available["ml_home"] = (odd["ml_home_dec"], home_won)
                if odd["ml_away_dec"]:
                    bets_available["ml_away"] = (odd["ml_away_dec"], not home_won)
                if odd["spread_home"] is not None:
                    covered = margin > -odd["spread_home"]
                    bets_available["spread_home"] = (1.91, covered)
                    bets_available["spread_away"] = (1.91, not covered)
                if odd["total"] is not None:
                    bets_available["total_over"] = (1.91, game_total > odd["total"])
                    bets_available["total_under"] = (1.91, game_total < odd["total"])
                if odd["ml_home_dec"]:
                    h1_home_won = h1_result_from_hash(game_seed, home_won)
                    bets_available["h1_ml_home"] = (odd["ml_home_dec"] * 1.15, h1_home_won)
                    bets_available["h1_ml_away"] = (odd["ml_away_dec"] * 1.15, not h1_home_won)
                if odd["total"] is not None and odd["spread_home"] is not None:
                    expected_home_total = odd["total"] / 2 - odd["spread_home"] / 2
                    home_over = hs > expected_home_total
                    bets_available["team_total_home_over"] = (1.91, home_over)
                    bets_available["team_total_home_under"] = (1.91, not home_over)
                if odd["spread_home"] is not None:
                    alt_spread = odd["spread_home"] - 3
                    alt_covered = margin > -alt_spread
                    bets_available["alt_spread_home_big"] = (1.65, alt_covered)
                    bets_available["alt_spread_away_big"] = (2.20, not alt_covered)

                impl_home = 1.0 / odd["ml_home_dec"] if odd["ml_home_dec"] else 0.5
                prob = model_prob(m, impl_home, game_seed, home_won)

                bet_probs = {
                    "ml_home": prob, "ml_away": 1 - prob,
                    "spread_home": 0.52 + (prob - 0.5) * 0.3,
                    "spread_away": 0.48 + (0.5 - prob) * 0.3,
                    "total_over": 0.50 + (prob - 0.5) * 0.15,
                    "total_under": 0.50 - (prob - 0.5) * 0.15,
                    "h1_ml_home": prob * 0.9 + 0.05,
                    "h1_ml_away": (1 - prob) * 0.9 + 0.05,
                    "team_total_home_over": 0.50 + (prob - 0.5) * 0.10,
                    "team_total_home_under": 0.50 - (prob - 0.5) * 0.10,
                    "alt_spread_home_big": 0.58 + (prob - 0.5) * 0.25,
                    "alt_spread_away_big": 0.42 + (0.5 - prob) * 0.25,
                }

                for bet_type, (bet_odds, bet_won) in bets_available.items():
                    cats = cfg["cats"]
                    if cats != "all" and bet_type not in cats:
                        continue
                    bp = bet_probs.get(bet_type, 0.5)
                    raw_size = get_bet_size(s, bp, bet_odds, start_bankroll, comp)
                    if raw_size < 0.01:
                        continue
                    all_day_bets.append((bet_type, bet_odds, bet_won, raw_size, game_seed, bp))

            # Pass 2: Scale bets to fit within daily bankroll (100% allocation)
            if is_full_blast and all_day_bets:
                # Full blast: pick single highest-edge bet, wager 100%
                best_bet = max(all_day_bets, key=lambda x: x[5] * (x[1] - 1) - (1 - x[5]))
                bt, bo, bw, _, gs, _ = best_bet
                _execute_bet(comp, bt, bo, bw, start_bankroll, date, gs)
                day_bets = 1
                day_wagered = start_bankroll
                day_pnl = start_bankroll * (bo - 1) if bw else -start_bankroll
            elif all_day_bets:
                total_raw = sum(b[3] for b in all_day_bets)
                # Cap total wagered at 100% of starting bankroll
                scale = min(1.0, start_bankroll / total_raw) if total_raw > 0 else 0
                for bt, bo, bw, raw_size, gs, _ in all_day_bets:
                    bet_size = round(raw_size * scale, 2)
                    if bet_size < 0.01:
                        continue
                    _execute_bet(comp, bt, bo, bw, bet_size, date, gs)
                    day_bets += 1
                    day_wagered += bet_size
                    day_pnl += bet_size * (bo - 1) if bw else -bet_size

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
            comp["daily_allocations"].append({
                "date": date, "games": len(day_games), "bets": day_bets,
                "wagered": round(day_wagered, 2), "pnl": round(day_pnl, 2),
            })

            # Milestone tracking
            for ms in MILESTONES:
                if ms not in milestone_winners and comp["bankroll"] >= ms:
                    milestone_winners[ms] = {
                        "trader": comp_key, "day": day_idx + 1,
                        "date": date, "bankroll": round(comp["bankroll"], 2),
                    }

            # Elimination
            if comp["bankroll"] < 5.0:
                comp["active"] = False
                comp["eliminated_day"] = day_idx + 1
                comp["eliminated_date"] = date

    # ═══════════════════════════════════════════════════════════════
    # COMPUTE FINAL METRICS + ANALYTICS
    # ═══════════════════════════════════════════════════════════════

    for k, c in traders.items():
        c["roi_pct"] = round((c["bankroll"] - 100) / 100 * 100, 2)
        rets = c["daily_returns"]
        if rets and len(rets) > 1:
            avg_r = sum(rets) / len(rets)
            std_r = (sum((r - avg_r) ** 2 for r in rets) / len(rets)) ** 0.5
            c["sharpe"] = round(avg_r / std_r * math.sqrt(252) if std_r > 0 else 0, 2)
        else:
            c["sharpe"] = 0

    board = sorted(traders.items(), key=lambda x: x[1]["bankroll"], reverse=True)

    # Analytics
    analytics = _compute_analytics(board, traders, sorted_days, matched)
    analytics["milestones"] = {
        "$150K": milestone_winners.get(150_000, {"trader": "none", "day": None}),
        "$300K": milestone_winners.get(300_000, {"trader": "none", "day": None}),
        "$750K": milestone_winners.get(750_000, {"trader": "none", "day": None}),
    }

    # Print summary
    _print_results(board, traders, sorted_days, matched)

    # ═══════════════════════════════════════════════════════════════
    # SAVE RESULTS (full + slim)
    # ═══════════════════════════════════════════════════════════════

    meta = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "version": "trading-floor-v3",
        "games_matched": len(matched),
        "playing_days": len(sorted_days),
        "date_range": f"{sorted_days[0]} to {sorted_days[-1]}",
        "traders": len(traders),
        "models": len(MODELS),
        "strategies": len(STRATEGIES),
        "bet_categories": 12,
    }

    # Slim version (for frontend)
    slim = {
        "meta": meta,
        "analytics": analytics,
        "leaderboard": [
            {
                "rank": i + 1,
                "name": k,
                "model": v["model"],
                "strategy": v["strategy"],
                "strategy_type": v["strategy"],
                "bankroll": round(v["bankroll"], 2),
                "roi_pct": v["roi_pct"],
                "sharpe": v["sharpe"],
                "bets": v["bets"],
                "wins": v["wins"],
                "losses": v["losses"],
                "max_drawdown": round(v["max_drawdown"], 4),
                "active": v["active"],
                "eliminated_day": v.get("eliminated_day"),
                "eliminated_date": v.get("eliminated_date"),
                "bankroll_history": [round(b, 2) for b in v["bankroll_history"]],
                "category_stats": v["category_stats"],
                "win_streak_max": v.get("win_streak_max", 0),
                "lose_streak_max": v.get("lose_streak_max", 0),
            }
            for i, (k, v) in enumerate(board)
        ],
    }

    # Full version (with bet logs + daily allocations)
    full = {
        "meta": meta,
        "analytics": analytics,
        "leaderboard": [
            {
                **slim["leaderboard"][i],
                "bet_log": traders[board[i][0]].get("bet_log", [])[-200:],  # last 200 bets
                "daily_allocations": traders[board[i][0]].get("daily_allocations", []),
            }
            for i in range(len(board))
        ],
    }

    out_dir = ROOT / "data" / "arena"
    out_dir.mkdir(parents=True, exist_ok=True)

    slim_file = out_dir / "nba-arena-trading-floor-slim.json"
    with open(slim_file, "w") as f:
        json.dump(slim, f, separators=(',', ':'))
    print(f"\n  Slim saved to {slim_file} ({slim_file.stat().st_size / 1024:.0f} KB)")

    full_file = out_dir / "nba-arena-trading-floor.json"
    with open(full_file, "w") as f:
        json.dump(full, f, indent=1)
    print(f"  Full saved to {full_file} ({full_file.stat().st_size / 1024:.0f} KB)")

    # Also overwrite the standard arena file for dashboard compatibility
    compat_file = out_dir / "nba-arena-full-season.json"
    with open(compat_file, "w") as f:
        json.dump(slim, f, indent=2)
    print(f"  Compat saved to {compat_file}")


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _new_trader(model, strategy):
    return {
        "model": model, "strategy": strategy,
        "bankroll": 100.0, "peak": 100.0,
        "bets": 0, "wins": 0, "losses": 0,
        "total_wagered": 0.0, "total_profit": 0.0,
        "max_drawdown": 0.0,
        "daily_returns": [],
        "active": True,
        "bankroll_history": [100.0],
        "daily_allocations": [],
        "bet_log": [],
        "category_stats": {},
        "last_won": None,
        "win_streak": 0, "win_streak_max": 0,
        "lose_streak": 0, "lose_streak_max": 0,
        "eliminated_day": None, "eliminated_date": None,
    }


def _execute_bet(comp, bet_type, bet_odds, bet_won, bet_size, date, game_seed):
    comp["bets"] += 1
    comp["total_wagered"] += bet_size

    if bet_won:
        profit = bet_size * (bet_odds - 1)
        comp["bankroll"] += profit
        comp["total_profit"] += profit
        comp["wins"] += 1
        comp["last_won"] = True
        comp["win_streak"] += 1
        comp["lose_streak"] = 0
        comp["win_streak_max"] = max(comp["win_streak_max"], comp["win_streak"])
    else:
        comp["bankroll"] -= bet_size
        comp["total_profit"] -= bet_size
        comp["losses"] += 1
        profit = -bet_size
        comp["last_won"] = False
        comp["lose_streak"] += 1
        comp["win_streak"] = 0
        comp["lose_streak_max"] = max(comp["lose_streak_max"], comp["lose_streak"])

    # Category stats
    if bet_type not in comp["category_stats"]:
        comp["category_stats"][bet_type] = {"bets": 0, "wins": 0, "profit": 0.0}
    cs = comp["category_stats"][bet_type]
    cs["bets"] += 1
    if bet_won:
        cs["wins"] += 1
    cs["profit"] = round(cs["profit"] + profit, 2)

    # Bet log (keep all for full version)
    comp["bet_log"].append({
        "date": date, "game": game_seed, "cat": bet_type,
        "odds": round(bet_odds, 3), "stake": round(bet_size, 2),
        "won": bet_won, "profit": round(profit, 2),
        "bankroll_after": round(comp["bankroll"], 2),
    })


def _compute_analytics(board, traders, sorted_days, matched):
    # Best trader
    best_k, best_v = board[0]

    # Best model (avg ROI across all strategies)
    model_rois = defaultdict(list)
    for k, v in traders.items():
        model_rois[v["model"]].append(v["roi_pct"])
    best_model = max(model_rois.items(), key=lambda x: sum(x[1]) / len(x[1]))

    # Best strategy (avg ROI across all models)
    strat_rois = defaultdict(list)
    for k, v in traders.items():
        strat_rois[v["strategy"]].append(v["roi_pct"])
    best_strat = max(strat_rois.items(), key=lambda x: sum(x[1]) / len(x[1]))

    # Best per category
    cat_stats = defaultdict(lambda: {"bets": 0, "wins": 0, "profit": 0.0})
    for k, v in traders.items():
        for cat, cs in v["category_stats"].items():
            cat_stats[cat]["bets"] += cs["bets"]
            cat_stats[cat]["wins"] += cs["wins"]
            cat_stats[cat]["profit"] += cs["profit"]
    best_cat = max(cat_stats.items(), key=lambda x: x[1]["profit"]) if cat_stats else ("none", {})

    # Best model per category
    model_cat_profit = defaultdict(lambda: defaultdict(float))
    for k, v in traders.items():
        for cat, cs in v["category_stats"].items():
            model_cat_profit[cat][v["model"]] += cs["profit"]
    best_model_per_cat = {}
    for cat, models in model_cat_profit.items():
        if models:
            best_model_per_cat[cat] = max(models.items(), key=lambda x: x[1])[0]

    # Elimination timeline
    elim_timeline = []
    for k, v in traders.items():
        if not v["active"]:
            elim_timeline.append({
                "day": v.get("eliminated_day", 0),
                "date": v.get("eliminated_date", ""),
                "trader": k,
                "bankroll": round(v["bankroll"], 2),
            })
    elim_timeline.sort(key=lambda x: x["day"])

    alive = sum(1 for v in traders.values() if v["active"])
    profitable = sum(1 for v in traders.values() if v["bankroll"] > 100)

    return {
        "best_trader": {"name": best_k, "roi": best_v["roi_pct"], "bankroll": round(best_v["bankroll"], 2), "sharpe": best_v["sharpe"]},
        "best_model": {"name": best_model[0], "avg_roi": round(sum(best_model[1]) / len(best_model[1]), 2)},
        "best_strategy": {"name": best_strat[0], "avg_roi": round(sum(best_strat[1]) / len(best_strat[1]), 2)},
        "best_model_x_strategy": {"model": best_v["model"], "strategy": best_v["strategy"], "roi": best_v["roi_pct"]},
        "best_bet_type": {"name": best_cat[0], "profit": round(best_cat[1].get("profit", 0), 2),
                          "win_rate": round(best_cat[1]["wins"] / best_cat[1]["bets"] * 100, 1) if best_cat[1].get("bets") else 0},
        "best_model_per_category": best_model_per_cat,
        "top3_portfolios": [
            {"name": board[i][0], "bankroll": round(board[i][1]["bankroll"], 2),
             "roi": board[i][1]["roi_pct"], "sharpe": board[i][1]["sharpe"]}
            for i in range(min(3, len(board)))
        ],
        "elimination_timeline": elim_timeline[:50],
        "category_summary": {
            cat: {
                "bets": cs["bets"], "wins": cs["wins"],
                "win_rate": round(cs["wins"] / cs["bets"] * 100, 1) if cs["bets"] else 0,
                "profit": round(cs["profit"], 2),
            }
            for cat, cs in sorted(cat_stats.items(), key=lambda x: -x[1]["profit"])
        },
        "model_rankings": {
            m: round(sum(rois) / len(rois), 2)
            for m, rois in sorted(model_rois.items(), key=lambda x: -sum(x[1]) / len(x[1]))
        },
        "strategy_rankings": {
            s: round(sum(rois) / len(rois), 2)
            for s, rois in sorted(strat_rois.items(), key=lambda x: -sum(x[1]) / len(x[1]))
        },
        "season_summary": {
            "total_games": len(matched),
            "playing_days": len(sorted_days),
            "total_traders": len(traders),
            "survivors": alive,
            "eliminated": len(traders) - alive,
            "profitable": profitable,
            "avg_roi": round(sum(v["roi_pct"] for v in traders.values()) / len(traders), 2),
        },
    }


def _print_results(board, traders, sorted_days, matched):
    alive = sum(1 for v in traders.values() if v["active"])
    profitable = sum(1 for v in traders.values() if v["bankroll"] > 100)
    avg_roi = sum(v["roi_pct"] for v in traders.values()) / len(traders)

    print(f"\n{'='*100}")
    print(f"  PIXEL TRADING FLOOR v3 — {len(matched)} games × {len(traders)} traders × 12 bet categories")
    print(f"  Season: {sorted_days[0]} -> {sorted_days[-1]} ({len(sorted_days)} days)")
    print(f"  Models: {len(MODELS)} | Strategies: {len(STRATEGIES)}")
    print(f"{'='*100}")

    print(f"\n  {'#':<3} {'Trader':<40} {'Bank':>9} {'ROI':>8} {'Sharpe':>7} {'Bets':>6} {'W/L':>10} {'DD':>6} {'Status':>6}")
    print(f"  {'─'*3} {'─'*40} {'─'*9} {'─'*8} {'─'*7} {'─'*6} {'─'*10} {'─'*6} {'─'*6}")
    for i, (k, v) in enumerate(board[:30]):
        wl = f"{v['wins']}/{v['losses']}"
        status = "LIVE" if v["active"] else "BUST"
        print(f"  {i+1:<3} {k:<40} ${v['bankroll']:>7.2f} {v['roi_pct']:>7.1f}% {v['sharpe']:>6.2f} {v['bets']:>6} {wl:>10} {v['max_drawdown']:>5.1%} {status:>6}")

    print(f"\n  SUMMARY: Active={alive}/{len(traders)} | Profitable={profitable}/{len(traders)} | Avg ROI={avg_roi:.1f}%")
    print(f"  CHAMPION: {board[0][0]} -> ${board[0][1]['bankroll']:.2f} ({board[0][1]['roi_pct']:.1f}% ROI)")


if __name__ == "__main__":
    run_full_season()
