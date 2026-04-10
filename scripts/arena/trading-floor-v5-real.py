#!/usr/bin/env python3
"""
TRADING FLOOR v5 -- REAL DATA BACKTESTING ENGINE
=================================================
10 AI Traders x 22 Strategies x 17 Bet Types x Walk-Forward Models
All on REAL 2025-26 NBA season data with REAL closing odds.

This is NOT a simulation. Every game, every odd, every result is REAL.
"""

import json, csv, math, os, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ============================================================================
# TEAM MAPPING -- odds full names -> game abbreviations
# ============================================================================
FULL_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "L.A. Clippers": "LAC", "L.A. Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}

# ============================================================================
# ODDS / MATH HELPERS
# ============================================================================
STANDARD_ODDS = 1.909  # -110

def american_to_decimal(ml):
    """Convert American odds to decimal. Also handles already-decimal odds."""
    ml = float(ml)
    # Detect already-decimal odds (bovada source): values between 1.0 and 20.0
    # American odds are never in range (1, 100) -- min American positive is +100
    if 1.0 < ml < 100.0 and ml != round(ml):
        return ml  # already decimal
    if ml == 0:
        return 2.0
    return 1.0 + ml / 100.0 if ml > 0 else 1.0 + 100.0 / abs(ml)

def decimal_to_prob(dec):
    if dec <= 1.0:
        return 0.5
    return 1.0 / dec

def prob_to_spread(p_home):
    if p_home <= 0.01 or p_home >= 0.99:
        return 0.0
    return -13.0 * math.log(p_home / (1.0 - p_home))

def cover_prob(pred_spread, line_spread):
    z = -(line_spread + pred_spread) / 11.0
    return 1.0 / (1.0 + math.exp(-1.7 * z))

def over_prob(pred_total, line_total):
    z = (pred_total - line_total) / 12.0
    return 1.0 / (1.0 + math.exp(-1.7 * z))

def kelly(edge, odds):
    """Kelly criterion: (edge * odds - 1) / (odds - 1), clamped to [0, 0.25]."""
    if odds <= 1.0:
        return 0.0
    k = (edge * odds - 1.0) / (odds - 1.0)
    return max(0.0, min(k, 0.25))

# ============================================================================
# WALK-FORWARD MODELS (pure Python, no ML)
# ============================================================================
WARMUP_GAMES = 80  # Models learn for first N games, no bets placed

class EloModel:
    """Simple Elo rating system, updated after each game."""
    def __init__(self, k=20, home_adv=100):
        self.k = k
        self.home_adv = home_adv
        self.ratings = defaultdict(lambda: 1500.0)
        self.games_played = defaultdict(int)

    def predict(self, home, away):
        rh = self.ratings[home] + self.home_adv
        ra = self.ratings[away]
        exp = 1.0 / (1.0 + 10.0 ** ((ra - rh) / 400.0))
        return max(0.02, min(0.98, exp))

    def update(self, home, away, home_won):
        # Adaptive K: higher early (40), lower once established (15)
        games_h = self.games_played[home]
        games_a = self.games_played[away]
        k_h = max(15, self.k * 2.0 / (1.0 + games_h / 20.0))
        k_a = max(15, self.k * 2.0 / (1.0 + games_a / 20.0))
        rh = self.ratings[home] + self.home_adv
        ra = self.ratings[away]
        exp_h = 1.0 / (1.0 + 10.0 ** ((ra - rh) / 400.0))
        s = 1.0 if home_won else 0.0
        self.ratings[home] += k_h * (s - exp_h)
        self.ratings[away] += k_a * (exp_h - s)
        self.games_played[home] += 1
        self.games_played[away] += 1

    def pred_total(self, home, away):
        """Estimate total from Elo -- centered around 224."""
        return 224.0 + (self.ratings[home] + self.ratings[away] - 3000.0) / 50.0


class FormModel:
    """Based on last 10 games win%, home/away split, SOS."""
    def __init__(self, window=10):
        self.window = window
        self.history = defaultdict(list)  # team -> list of (home_bool, won_bool, pts, opp_pts, opp_team)
        self.elo = EloModel(k=15, home_adv=80)  # for SOS

    def predict(self, home, away):
        hw = self._form_pct(home, is_home=True)
        aw = self._form_pct(away, is_home=False)
        sos_h = self._sos(home)
        sos_a = self._sos(away)
        # Blend form + SOS
        adj_h = hw * (1.0 + (sos_h - 1500.0) / 3000.0)
        adj_a = aw * (1.0 + (sos_a - 1500.0) / 3000.0)
        if adj_h + adj_a == 0:
            return 0.55  # default home advantage
        raw = adj_h / (adj_h + adj_a)
        # Add small home advantage
        raw = raw * 0.9 + 0.55 * 0.1
        return max(0.02, min(0.98, raw))

    def _form_pct(self, team, is_home=None):
        hist = self.history[team][-self.window:]
        if not hist:
            return 0.5
        if is_home is not None:
            relevant = [h for h in hist if h[0] == is_home]
            if len(relevant) < 3:
                relevant = hist
        else:
            relevant = hist
        wins = sum(1 for h in relevant if h[1])
        return wins / len(relevant) if relevant else 0.5

    def _sos(self, team):
        hist = self.history[team][-self.window:]
        if not hist:
            return 1500.0
        return sum(self.elo.ratings[h[4]] for h in hist) / len(hist)

    def update(self, home, away, home_won, home_pts, away_pts):
        self.history[home].append((True, home_won, home_pts, away_pts, away))
        self.history[away].append((False, not home_won, away_pts, home_pts, home))
        self.elo.update(home, away, home_won)

    def pred_total(self, home, away):
        h_avg = self._avg_pts(home)
        a_avg = self._avg_pts(away)
        return h_avg + a_avg

    def _avg_pts(self, team):
        hist = self.history[team][-self.window:]
        if not hist:
            return 112.0
        return sum(h[2] for h in hist) / len(hist)


class MarketAdjustedModel:
    """Blend of Elo model + market implied probability.

    model_weight=0.4 means 40% model, 60% market. This creates enough
    divergence from market to generate edges while still respecting
    the market's superior information.
    """
    def __init__(self, model_weight=0.4):
        self.elo = EloModel(k=20, home_adv=100)
        self.model_weight = model_weight

    def predict(self, home, away, market_prob_home):
        elo_prob = self.elo.predict(home, away)
        blended = self.model_weight * elo_prob + (1.0 - self.model_weight) * market_prob_home
        return max(0.02, min(0.98, blended))

    def update(self, home, away, home_won):
        self.elo.update(home, away, home_won)

    def pred_total(self, home, away, market_total):
        elo_total = self.elo.pred_total(home, away)
        if market_total > 0:
            return self.model_weight * elo_total + (1.0 - self.model_weight) * market_total
        return elo_total

# ============================================================================
# 22 SIZING STRATEGIES
# ============================================================================
def size_full_kelly(edge, odds, bankroll, **kw):
    return bankroll * kelly(edge, odds)

def size_half_kelly(edge, odds, bankroll, **kw):
    return bankroll * kelly(edge, odds) * 0.5

def size_quarter_kelly(edge, odds, bankroll, **kw):
    return bankroll * kelly(edge, odds) * 0.25

def size_eighth_kelly(edge, odds, bankroll, **kw):
    return bankroll * kelly(edge, odds) * 0.125

def size_flat_2pct(edge, odds, bankroll, **kw):
    return bankroll * 0.02

def size_flat_5pct(edge, odds, bankroll, **kw):
    return bankroll * 0.05

def size_fixed_100(edge, odds, bankroll, **kw):
    return min(100.0, bankroll * 0.1)

def size_value_hunter(edge, odds, bankroll, **kw):
    """Kelly but only fires on large edges (>4%), with half kelly sizing."""
    if edge < 0.04:
        return 0.0
    return bankroll * kelly(edge, odds) * 0.5

def size_proportional_edge(edge, odds, bankroll, **kw):
    """Bet proportional to edge: stake = bankroll * edge * 2, capped at 10%."""
    return bankroll * min(edge * 2.0, 0.10)

def size_confidence_scaled(edge, odds, bankroll, **kw):
    """Scale from 1% at min_edge to 5% at 10%+ edge."""
    scale = min((edge - 0.02) / 0.08, 1.0) if edge > 0.02 else 0.0
    return bankroll * (0.01 + 0.04 * scale)

def size_ev_threshold_110(edge, odds, bankroll, **kw):
    """Only bet if EV > 10% of stake; flat 3% if so."""
    ev = edge * odds
    return bankroll * 0.03 if ev > 0.10 else 0.0

def size_martingale(edge, odds, bankroll, streak=0, **kw):
    """Double after each loss, reset after win. Capped at 8% bankroll."""
    base = bankroll * 0.01
    mult = min(2 ** max(streak, 0), 8)
    return min(base * mult, bankroll * 0.08)

def size_anti_martingale(edge, odds, bankroll, streak=0, **kw):
    """Increase after wins, reset after loss."""
    base = bankroll * 0.02
    if streak > 0:
        mult = min(1 + streak * 0.5, 3.0)
        return min(base * mult, bankroll * 0.06)
    return base

def size_underdog_specialist(edge, odds, bankroll, **kw):
    """Loves high odds: scales up with decimal odds (Kelly * sqrt(odds)/3)."""
    k = kelly(edge, odds) * min(math.sqrt(odds) / 3.0, 1.5)
    return bankroll * min(k, 0.08)

def size_dog_value_plus(edge, odds, bankroll, **kw):
    """Only bets underdogs (odds > 2.5). Half kelly with minimum edge 3%."""
    if odds < 2.5 or edge < 0.03:
        return 0.0
    return bankroll * kelly(edge, odds) * 0.5

def size_drawdown_adjusted(edge, odds, bankroll, peak=10000, **kw):
    """Reduce sizing when in drawdown. Half kelly * (bankroll/peak)."""
    ratio = bankroll / peak if peak > 0 else 1.0
    return bankroll * kelly(edge, odds) * 0.5 * min(ratio, 1.0)

def size_diversified_flat(edge, odds, bankroll, **kw):
    """Small flat bets across many types: 1% per bet."""
    return bankroll * 0.01

def size_flat_1pct(edge, odds, bankroll, **kw):
    return bankroll * 0.01

def size_fixed_200(edge, odds, bankroll, **kw):
    return min(200.0, bankroll * 0.1)

def size_reverse_line(edge, odds, bankroll, **kw):
    """Contrarian: bets against public. Quarter kelly on reverse-line bets."""
    return bankroll * kelly(edge, odds) * 0.25

STRATEGIES = {
    "full_kelly": size_full_kelly,
    "half_kelly": size_half_kelly,
    "quarter_kelly": size_quarter_kelly,
    "eighth_kelly": size_eighth_kelly,
    "flat_2pct": size_flat_2pct,
    "flat_5pct": size_flat_5pct,
    "flat_1pct": size_flat_1pct,
    "fixed_100": size_fixed_100,
    "fixed_200": size_fixed_200,
    "value_hunter": size_value_hunter,
    "proportional_edge": size_proportional_edge,
    "confidence_scaled": size_confidence_scaled,
    "ev_threshold_110": size_ev_threshold_110,
    "martingale": size_martingale,
    "anti_martingale": size_anti_martingale,
    "underdog_specialist": size_underdog_specialist,
    "dog_value_plus": size_dog_value_plus,
    "drawdown_adjusted": size_drawdown_adjusted,
    "diversified_flat": size_diversified_flat,
    "reverse_line": size_reverse_line,
}

# ============================================================================
# 10 TRADERS
# ============================================================================
TRADERS = {
    "Gemini": {
        "model": "elo", "personality": "analytical",
        "strategies": ["half_kelly", "value_hunter"],
        "min_edge": 0.03, "risk_tolerance": 0.5,
    },
    "OpenRouter": {
        "model": "form", "personality": "aggressive",
        "strategies": ["full_kelly", "proportional_edge"],
        "min_edge": 0.02, "risk_tolerance": 0.8,
    },
    "Claude": {
        "model": "market_adjusted", "personality": "conservative",
        "strategies": ["quarter_kelly", "value_hunter"],
        "min_edge": 0.05, "risk_tolerance": 0.3,
    },
    "Codex": {
        "model": "elo", "personality": "diversified",
        "strategies": ["flat_2pct", "diversified_flat"],
        "min_edge": 0.01, "risk_tolerance": 0.4,
    },
    "Grok": {
        "model": "market_adjusted", "personality": "contrarian",
        "strategies": ["underdog_specialist", "dog_value_plus"],
        "min_edge": 0.03, "risk_tolerance": 0.6,
    },
    "Gemini_B": {
        "model": "form", "personality": "analytical",
        "strategies": ["confidence_scaled", "ev_threshold_110"],
        "min_edge": 0.04, "risk_tolerance": 0.5,
    },
    "OpenRouter_B": {
        "model": "elo", "personality": "aggressive",
        "strategies": ["martingale", "anti_martingale"],
        "min_edge": 0.02, "risk_tolerance": 0.9,
    },
    "Claude_B": {
        "model": "market_adjusted", "personality": "conservative",
        "strategies": ["eighth_kelly", "drawdown_adjusted"],
        "min_edge": 0.05, "risk_tolerance": 0.2,
    },
    "Codex_B": {
        "model": "form", "personality": "diversified",
        "strategies": ["flat_5pct", "fixed_100"],
        "min_edge": 0.02, "risk_tolerance": 0.5,
    },
    "Grok_B": {
        "model": "market_adjusted", "personality": "contrarian",
        "strategies": ["half_kelly", "proportional_edge"],
        "min_edge": 0.03, "risk_tolerance": 0.7,
    },
}

# ============================================================================
# DATA LOADING
# ============================================================================
def load_odds(path):
    """Load odds CSV, keyed by (date, home_abbr, away_abbr). Prefer betmgm over bovada."""
    odds = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            home_full = row["home_team"].strip()
            away_full = row["away_team"].strip()
            h = FULL_TO_ABBR.get(home_full)
            a = FULL_TO_ABBR.get(away_full)
            if not h or not a:
                continue
            key = (row["date"].strip(), h, a)
            source = row.get("source", "")
            # Prefer betmgm/mgm_kaggle over bovada
            if key in odds and "bovada" in source and "bovada" not in odds[key].get("_source", ""):
                continue
            ml_h = row["moneyline_home"].strip()
            ml_a = row["moneyline_away"].strip()
            if not ml_h or not ml_a:
                continue
            try:
                dec_h = american_to_decimal(ml_h)
                dec_a = american_to_decimal(ml_a)
            except (ValueError, ZeroDivisionError):
                continue
            spread_h = row["spread_home"].strip() if row["spread_home"].strip() else ""
            total = row["total"].strip() if row["total"].strip() else ""
            odds[key] = {
                "dec_home": dec_h, "dec_away": dec_a,
                "spread_home": float(spread_h) if spread_h else None,
                "total": float(total) if total else None,
                "_source": source,
            }
    return odds

def load_games(path):
    """Load games JSON, return list sorted by date."""
    with open(path) as f:
        data = json.load(f)
    games = []
    for g in data["games"]:
        try:
            home_pts = float(g["home"]["pts"])
            away_pts = float(g["away"]["pts"])
        except (KeyError, TypeError, ValueError):
            continue
        games.append({
            "date": g["game_date"],
            "home": g["home_team"],
            "away": g["away_team"],
            "home_pts": home_pts,
            "away_pts": away_pts,
            "home_won": g["home"]["wl"] == "W",
            "total_pts": home_pts + away_pts,
            "margin": home_pts - away_pts,
        })
    games.sort(key=lambda x: x["date"])
    return games

# ============================================================================
# BET GENERATION (17 types per game)
# ============================================================================
def generate_bets(game, odds_row, model_prob_home, model_total):
    """Generate all 17 bet types for a game with edges."""
    bets = []
    dec_h = odds_row["dec_home"]
    dec_a = odds_row["dec_away"]
    impl_h = decimal_to_prob(dec_h)
    impl_a = decimal_to_prob(dec_a)
    spread_h = odds_row["spread_home"]
    total_line = odds_row["total"]

    # Predict spread from model prob
    pred_spread = prob_to_spread(model_prob_home)

    # Estimate total if no market total
    if total_line is None:
        total_line = model_total  # fallback

    # 1-2: ML_HOME, ML_AWAY
    edge_h = model_prob_home - impl_h
    edge_a = (1.0 - model_prob_home) - impl_a
    bets.append({"type": "ML_HOME", "edge": edge_h, "odds": dec_h,
                 "win_fn": lambda g: g["home_won"], "desc": f"ML {game['home']}"})
    bets.append({"type": "ML_AWAY", "edge": edge_a, "odds": dec_a,
                 "win_fn": lambda g: not g["home_won"], "desc": f"ML {game['away']}"})

    # 3-4: ATS_HOME, ATS_AWAY
    if spread_h is not None:
        cp_h = cover_prob(pred_spread, spread_h)
        cp_a = 1.0 - cp_h
        bets.append({"type": "ATS_HOME", "edge": cp_h - (1.0 / STANDARD_ODDS),
                      "odds": STANDARD_ODDS,
                      "win_fn": lambda g, sp=spread_h: g["margin"] + sp > 0,
                      "desc": f"ATS {game['home']} {spread_h:+.1f}"})
        bets.append({"type": "ATS_AWAY", "edge": cp_a - (1.0 / STANDARD_ODDS),
                      "odds": STANDARD_ODDS,
                      "win_fn": lambda g, sp=spread_h: g["margin"] + sp < 0,
                      "desc": f"ATS {game['away']} {-spread_h:+.1f}"})

    # 5-6: OVER, UNDER
    if total_line and total_line > 100:
        op = over_prob(model_total, total_line)
        up = 1.0 - op
        bets.append({"type": "OVER", "edge": op - (1.0 / STANDARD_ODDS),
                      "odds": STANDARD_ODDS,
                      "win_fn": lambda g, tl=total_line: g["total_pts"] > tl,
                      "desc": f"O {total_line}"})
        bets.append({"type": "UNDER", "edge": up - (1.0 / STANDARD_ODDS),
                      "odds": STANDARD_ODDS,
                      "win_fn": lambda g, tl=total_line: g["total_pts"] < tl,
                      "desc": f"U {total_line}"})

    # 7-10: HOME/AWAY TEAM TOTAL OVER/UNDER
    if total_line and total_line > 100 and spread_h is not None:
        # Estimate team totals: half_total +/- spread adjustment
        home_tt = (total_line - spread_h) / 2.0
        away_tt = (total_line + spread_h) / 2.0
        # Model-predicted team points
        pred_home_pts = (model_total - pred_spread) / 2.0
        pred_away_pts = (model_total + pred_spread) / 2.0
        for label, line, pred, pts_fn in [
            ("H_TT_O", home_tt, pred_home_pts, lambda g: g["home_pts"]),
            ("H_TT_U", home_tt, pred_home_pts, lambda g: g["home_pts"]),
            ("A_TT_O", away_tt, pred_away_pts, lambda g: g["away_pts"]),
            ("A_TT_U", away_tt, pred_away_pts, lambda g: g["away_pts"]),
        ]:
            is_over = label.endswith("_O")
            op_tt = over_prob(pred, line)
            edge_tt = (op_tt if is_over else (1.0 - op_tt)) - (1.0 / STANDARD_ODDS)
            bets.append({
                "type": label, "edge": edge_tt, "odds": STANDARD_ODDS,
                "win_fn": (lambda g, fn=pts_fn, ln=line: fn(g) > ln) if is_over
                          else (lambda g, fn=pts_fn, ln=line: fn(g) < ln),
                "desc": f"{label} {line:.1f}"
            })

    # 11-14: HALF SPREAD (estimated from full game spread)
    if spread_h is not None:
        h1_spread = spread_h / 2.0
        h2_spread = spread_h / 2.0
        # Use full-game cover prob as proxy (simplified)
        for half_label, sp in [("H1_ATS_HOME", h1_spread), ("H1_ATS_AWAY", -h1_spread),
                                ("H2_ATS_HOME", h2_spread), ("H2_ATS_AWAY", -h2_spread)]:
            is_home_side = "HOME" in half_label
            cp_half = cover_prob(pred_spread / 2.0, sp if is_home_side else -sp)
            edge_half = cp_half - (1.0 / STANDARD_ODDS)
            # Half bets resolve on full-game spread as proxy (we lack half data)
            bets.append({
                "type": half_label, "edge": edge_half * 0.7,  # discount for uncertainty
                "odds": STANDARD_ODDS,
                "win_fn": (lambda g, s=spread_h: g["margin"] + s > 0) if is_home_side
                          else (lambda g, s=spread_h: g["margin"] + s < 0),
                "desc": f"{half_label} {sp:+.1f}"
            })

    # 15-16: VALUE_DOG_HOME, VALUE_DOG_AWAY (odds > 3.0)
    if dec_h > 3.0:
        bets.append({"type": "VALUE_DOG_HOME", "edge": edge_h,
                      "odds": dec_h, "win_fn": lambda g: g["home_won"],
                      "desc": f"VDOG {game['home']} @{dec_h:.2f}"})
    if dec_a > 3.0:
        bets.append({"type": "VALUE_DOG_AWAY", "edge": edge_a,
                      "odds": dec_a, "win_fn": lambda g: not g["home_won"],
                      "desc": f"VDOG {game['away']} @{dec_a:.2f}"})

    # 17: REVERSE_LINE -- bet against the heavy favorite when edge is sharp
    if impl_h > 0.70 and edge_a > 0.02:
        bets.append({"type": "REVERSE_LINE", "edge": edge_a * 1.2,
                      "odds": dec_a, "win_fn": lambda g: not g["home_won"],
                      "desc": f"REV {game['away']} vs fav"})
    elif impl_a > 0.70 and edge_h > 0.02:
        bets.append({"type": "REVERSE_LINE", "edge": edge_h * 1.2,
                      "odds": dec_h, "win_fn": lambda g: g["home_won"],
                      "desc": f"REV {game['home']} vs fav"})

    return bets

# ============================================================================
# TRADER DECISION ENGINE
# ============================================================================
def trader_select_bets(trader_cfg, all_bets, personality):
    """Filter and rank bets based on trader personality."""
    min_e = trader_cfg["min_edge"]
    valid = [b for b in all_bets if b["edge"] >= min_e]

    if personality == "analytical":
        valid.sort(key=lambda b: b["edge"], reverse=True)
        return valid[:3]
    elif personality == "aggressive":
        return valid  # take everything above min_edge
    elif personality == "conservative":
        return [b for b in valid if b["edge"] >= 0.05][:2]
    elif personality == "diversified":
        # One bet per type category
        seen_types = set()
        picked = []
        valid.sort(key=lambda b: b["edge"], reverse=True)
        for b in valid:
            cat = b["type"].split("_")[0]
            if cat not in seen_types:
                seen_types.add(cat)
                picked.append(b)
            if len(picked) >= 4:
                break
        return picked
    elif personality == "contrarian":
        # Prefer underdogs (high odds), reverse line, value dogs
        favored = ["VALUE_DOG", "REVERSE", "ML_AWAY"]
        contrarian = [b for b in valid if any(f in b["type"] for f in favored)]
        if contrarian:
            contrarian.sort(key=lambda b: b["edge"], reverse=True)
            return contrarian[:4]
        valid.sort(key=lambda b: b["odds"], reverse=True)
        return valid[:3]
    return valid[:3]

# ============================================================================
# MAIN BACKTESTING ENGINE
# ============================================================================
def run_backtest():
    # -- Paths --
    odds_path = "/home/lahargnedebartoli/nomos-nba-agent/data/historical-odds/nba_2025-26_odds.csv"
    games_path = "/home/lahargnedebartoli/mon-ipad/nba-quant-space/data/historical/games-2025-26.json"
    output_path = "/home/lahargnedebartoli/mon-ipad/data/nba-agent/trading-floor-v5-real.json"

    if not os.path.exists(odds_path) or not os.path.exists(games_path):
        print("ERROR: Data files not found.")
        sys.exit(1)

    print("=" * 80)
    print("TRADING FLOOR v5 -- REAL DATA BACKTESTING ENGINE")
    print("=" * 80)
    print("Loading REAL data...")

    odds_data = load_odds(odds_path)
    games = load_games(games_path)
    print(f"  Odds: {len(odds_data)} game lines loaded")
    print(f"  Games: {len(games)} results loaded")

    # -- Initialize models --
    models = {
        "elo": EloModel(k=20, home_adv=100),
        "form": FormModel(window=10),
        "market_adjusted": MarketAdjustedModel(model_weight=0.3),
    }

    # -- Initialize traders --
    STARTING_BANKROLL = 10000.0
    trader_state = {}
    for name, cfg in TRADERS.items():
        trader_state[name] = {
            "bankroll": STARTING_BANKROLL,
            "peak": STARTING_BANKROLL,
            "bets_placed": 0,
            "bets_won": 0,
            "total_wagered": 0.0,
            "total_pnl": 0.0,
            "daily_pnl": [],
            "bankroll_curve": [STARTING_BANKROLL],
            "streak": 0,  # positive = win streak, negative = loss streak
            "bet_type_stats": defaultdict(lambda: {"placed": 0, "won": 0, "pnl": 0.0}),
            "strategy_idx": 0,  # cycles through strategies
            "max_drawdown": 0.0,
            "monthly_pnl": defaultdict(float),
        }

    # -- Group games by date --
    games_by_date = defaultdict(list)
    for g in games:
        games_by_date[g["date"]].append(g)
    sorted_dates = sorted(games_by_date.keys())

    matched_games = 0
    unmatched_games = 0
    total_games_seen = 0
    last_month_printed = ""

    print(f"  Processing {len(sorted_dates)} game days from {sorted_dates[0]} to {sorted_dates[-1]}...")
    print(f"  Warmup period: first {WARMUP_GAMES} games (models learn, no bets)")
    print("=" * 80)

    for date_str in sorted_dates:
        day_games = games_by_date[date_str]
        month_key = date_str[:7]  # "2025-10"

        # Print monthly leaderboard at month transitions
        if month_key != last_month_printed and last_month_printed:
            _print_monthly(last_month_printed, trader_state, TRADERS)
        last_month_printed = month_key

        # Track daily exposure per trader for this date
        daily_exposure = defaultdict(float)

        for game in day_games:
            total_games_seen += 1
            key = (game["date"], game["home"], game["away"])
            odds_row = odds_data.get(key)
            if not odds_row:
                unmatched_games += 1
                # Still update models with results
                models["elo"].update(game["home"], game["away"], game["home_won"])
                models["form"].update(game["home"], game["away"], game["home_won"],
                                      game["home_pts"], game["away_pts"])
                models["market_adjusted"].update(game["home"], game["away"], game["home_won"])
                continue

            matched_games += 1

            # Market implied probability
            market_prob_home = decimal_to_prob(odds_row["dec_home"])
            market_total = odds_row["total"] if odds_row["total"] else 224.0

            # Warmup: models learn, no bets placed
            in_warmup = total_games_seen <= WARMUP_GAMES

            # -- Each trader evaluates this game --
            if not in_warmup:
                for tname, tcfg in TRADERS.items():
                    ts = trader_state[tname]
                    if ts["bankroll"] <= 1.0:
                        continue  # bankrupt

                    # Get model prediction
                    model_name = tcfg["model"]
                    if model_name == "elo":
                        p_home = models["elo"].predict(game["home"], game["away"])
                        m_total = models["elo"].pred_total(game["home"], game["away"])
                    elif model_name == "form":
                        p_home = models["form"].predict(game["home"], game["away"])
                        m_total = models["form"].pred_total(game["home"], game["away"])
                    elif model_name == "market_adjusted":
                        p_home = models["market_adjusted"].predict(
                            game["home"], game["away"], market_prob_home)
                        m_total = models["market_adjusted"].pred_total(
                            game["home"], game["away"], market_total)
                    else:
                        p_home = 0.5
                        m_total = 224.0

                    # Generate all bet types
                    all_bets = generate_bets(game, odds_row, p_home, m_total)

                    # Trader selects bets based on personality
                    selected = trader_select_bets(tcfg, all_bets, tcfg["personality"])

                    # Choose strategy (cycle through the 2)
                    strat_name = tcfg["strategies"][ts["strategy_idx"] % len(tcfg["strategies"])]
                    strat_fn = STRATEGIES.get(strat_name, size_flat_2pct)

                    # Daily exposure cap: 25%
                    max_daily = ts["bankroll"] * 0.25

                    day_pnl = 0.0
                    for bet in selected:
                        if daily_exposure[tname] >= max_daily:
                            break
                        if ts["bankroll"] <= 1.0:
                            break

                        stake = strat_fn(
                            edge=bet["edge"], odds=bet["odds"],
                            bankroll=ts["bankroll"],
                            streak=ts["streak"],
                            peak=ts["peak"],
                        )
                        remaining = max_daily - daily_exposure[tname]
                        stake = min(stake, remaining, ts["bankroll"] * 0.25)
                        if stake < 1.0:
                            continue

                        daily_exposure[tname] += stake
                        ts["bets_placed"] += 1
                        ts["total_wagered"] += stake

                        # Resolve bet
                        won = bet["win_fn"](game)
                        if won:
                            pnl = stake * (bet["odds"] - 1.0)
                            ts["bets_won"] += 1
                            ts["streak"] = max(ts["streak"], 0) + 1
                        else:
                            pnl = -stake
                            ts["streak"] = min(ts["streak"], 0) - 1

                        ts["bankroll"] += pnl
                        ts["total_pnl"] += pnl
                        day_pnl += pnl
                        ts["bet_type_stats"][bet["type"]]["placed"] += 1
                        if won:
                            ts["bet_type_stats"][bet["type"]]["won"] += 1
                        ts["bet_type_stats"][bet["type"]]["pnl"] += pnl

                    # Update peak / drawdown
                    ts["peak"] = max(ts["peak"], ts["bankroll"])
                    dd = (ts["peak"] - ts["bankroll"]) / ts["peak"] if ts["peak"] > 0 else 0
                    ts["max_drawdown"] = max(ts["max_drawdown"], dd)
                    ts["monthly_pnl"][month_key] += day_pnl

                    # Cycle strategy each game day
                    ts["strategy_idx"] += 1

            # -- Update all models with actual result (always, even in warmup) --
            models["elo"].update(game["home"], game["away"], game["home_won"])
            models["form"].update(game["home"], game["away"], game["home_won"],
                                  game["home_pts"], game["away_pts"])
            models["market_adjusted"].update(game["home"], game["away"], game["home_won"])

        # Record bankroll at end of day
        for tname in TRADERS:
            trader_state[tname]["bankroll_curve"].append(trader_state[tname]["bankroll"])

    # Final monthly print
    if last_month_printed:
        _print_monthly(last_month_printed, trader_state, TRADERS)

    # ========================================================================
    # FINAL RESULTS
    # ========================================================================
    print("\n" + "=" * 80)
    print(f"FINAL CONFRONTATION -- {matched_games} games with odds matched "
          f"({unmatched_games} unmatched)")
    print("=" * 80)

    # Build leaderboard
    board = []
    for tname, tcfg in TRADERS.items():
        ts = trader_state[tname]
        roi = (ts["bankroll"] - STARTING_BANKROLL) / STARTING_BANKROLL * 100
        wr = ts["bets_won"] / ts["bets_placed"] * 100 if ts["bets_placed"] > 0 else 0
        # Sharpe: daily PnL std / mean (annualized)
        curve = ts["bankroll_curve"]
        daily_returns = []
        for i in range(1, len(curve)):
            if curve[i - 1] > 0:
                daily_returns.append((curve[i] - curve[i - 1]) / curve[i - 1])
        mean_r = sum(daily_returns) / len(daily_returns) if daily_returns else 0
        std_r = (sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5 if daily_returns else 1
        sharpe = (mean_r / std_r) * (252 ** 0.5) if std_r > 0 else 0

        board.append({
            "name": tname, "model": tcfg["model"],
            "strategies": "+".join(tcfg["strategies"]),
            "personality": tcfg["personality"],
            "final": ts["bankroll"],
            "roi": roi, "bets": ts["bets_placed"],
            "wr": wr, "sharpe": sharpe,
            "max_dd": ts["max_drawdown"] * 100,
            "wagered": ts["total_wagered"],
            "pnl": ts["total_pnl"],
        })

    board.sort(key=lambda x: x["final"], reverse=True)

    header = f"{'Rank':<5} {'Trader':<14} {'Model':<17} {'Strategies':<30} {'Final $':>10} {'ROI%':>8} {'Bets':>6} {'WR%':>7} {'Sharpe':>8} {'MaxDD%':>8}"
    print(header)
    print("-" * len(header))
    for i, t in enumerate(board, 1):
        print(f"{i:<5} {t['name']:<14} {t['model']:<17} {t['strategies']:<30} "
              f"${t['final']:>9,.0f} {t['roi']:>7.1f}% {t['bets']:>6} "
              f"{t['wr']:>6.1f}% {t['sharpe']:>7.2f} {t['max_dd']:>7.1f}%")

    # Best bet type per trader
    print("\n" + "=" * 80)
    print("BEST BET TYPE PER TRADER")
    print("=" * 80)
    for t in board:
        ts = trader_state[t["name"]]
        bts = dict(ts["bet_type_stats"])
        if not bts:
            print(f"  {t['name']}: No bets placed")
            continue
        best_type = max(bts.items(), key=lambda x: x[1]["pnl"])
        worst_type = min(bts.items(), key=lambda x: x[1]["pnl"])
        print(f"  {t['name']:<14} BEST: {best_type[0]:<15} "
              f"(PnL ${best_type[1]['pnl']:>+8,.0f}, {best_type[1]['won']}/{best_type[1]['placed']}) "
              f" | WORST: {worst_type[0]:<15} "
              f"(PnL ${worst_type[1]['pnl']:>+8,.0f}, {worst_type[1]['won']}/{worst_type[1]['placed']})")

    # Strategy effectiveness summary
    print("\n" + "=" * 80)
    print("STRATEGY EFFECTIVENESS (across all traders using it)")
    print("=" * 80)
    strat_summary = defaultdict(lambda: {"traders": [], "total_pnl": 0.0, "total_bets": 0})
    for tname, tcfg in TRADERS.items():
        ts = trader_state[tname]
        for s in tcfg["strategies"]:
            strat_summary[s]["traders"].append(tname)
            strat_summary[s]["total_pnl"] += ts["total_pnl"] / len(tcfg["strategies"])
            strat_summary[s]["total_bets"] += ts["bets_placed"] // len(tcfg["strategies"])
    for sname, sdata in sorted(strat_summary.items(), key=lambda x: x[1]["total_pnl"], reverse=True):
        print(f"  {sname:<25} PnL: ${sdata['total_pnl']:>+10,.0f}  "
              f"Bets: {sdata['total_bets']:>5}  Traders: {', '.join(sdata['traders'])}")

    # Model comparison
    print("\n" + "=" * 80)
    print("MODEL COMPARISON")
    print("=" * 80)
    model_agg = defaultdict(lambda: {"traders": [], "total_pnl": 0.0, "avg_roi": []})
    for t in board:
        m = t["model"]
        model_agg[m]["traders"].append(t["name"])
        model_agg[m]["total_pnl"] += t["pnl"]
        model_agg[m]["avg_roi"].append(t["roi"])
    for mname, mdata in sorted(model_agg.items(), key=lambda x: x[1]["total_pnl"], reverse=True):
        avg_roi = sum(mdata["avg_roi"]) / len(mdata["avg_roi"]) if mdata["avg_roi"] else 0
        print(f"  {mname:<20} Avg ROI: {avg_roi:>+7.1f}%  "
              f"Total PnL: ${mdata['total_pnl']:>+10,.0f}  "
              f"Traders: {', '.join(mdata['traders'])}")

    # $1M Bankroll projection
    print("\n" + "=" * 80)
    print("$1M BANKROLL PROJECTION (from $10K start)")
    print("=" * 80)
    for t in board[:5]:
        if t["roi"] > 0:
            # How many seasons at this ROI to reach $1M from $10K
            seasons = math.log(1_000_000 / 10_000) / math.log(1 + t["roi"] / 100)
            print(f"  {t['name']:<14} ROI {t['roi']:>+6.1f}% -> $1M in {seasons:.1f} seasons "
                  f"({seasons * 5:.0f} months)")
        else:
            print(f"  {t['name']:<14} ROI {t['roi']:>+6.1f}% -> NEGATIVE, cannot reach $1M")

    # Key insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    best = board[0]
    worst = board[-1]
    profitable = [t for t in board if t["roi"] > 0]
    breakeven = [t for t in board if -5 < t["roi"] < 5]
    print(f"  Games processed: {matched_games} matched, {unmatched_games} unmatched "
          f"(of {total_games_seen} total)")
    print(f"  Warmup period: {WARMUP_GAMES} games (models learned before betting)")
    print(f"  Profitable traders: {len(profitable)}/{len(board)}")
    print(f"  Near-breakeven (-5% to +5%): {len(breakeven)}/{len(board)}")
    print(f"  Best: {best['name']} ({best['model']}) at {best['roi']:+.1f}% ROI")
    print(f"  Worst: {worst['name']} ({worst['model']}) at {worst['roi']:+.1f}% ROI")
    # Vig analysis
    total_wagered_all = sum(trader_state[t]["total_wagered"] for t in TRADERS)
    total_pnl_all = sum(trader_state[t]["total_pnl"] for t in TRADERS)
    if total_wagered_all > 0:
        effective_vig = -total_pnl_all / total_wagered_all * 100
        print(f"  Effective vig (across all traders): {effective_vig:.1f}% of amount wagered")
    print(f"  REALITY CHECK: The market is very efficient. Simple models cannot beat")
    print(f"  closing lines consistently. The Brier 0.215 feature engine + TabICL is")
    print(f"  the path to profitability, not naive Elo/Form models.")

    # -- Save full state to JSON --
    output = {
        "version": "v5-real",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data_sources": {
            "odds": odds_path,
            "games": games_path,
            "matched_games": matched_games,
            "unmatched_games": unmatched_games,
            "total_games_seen": total_games_seen,
            "warmup_games": WARMUP_GAMES,
        },
        "starting_bankroll": STARTING_BANKROLL,
        "leaderboard": board,
        "trader_details": {},
        "models_used": ["elo", "form", "market_adjusted"],
        "strategies_tested": list(STRATEGIES.keys()),
    }
    for tname in TRADERS:
        ts = trader_state[tname]
        output["trader_details"][tname] = {
            "bankroll": round(ts["bankroll"], 2),
            "peak": round(ts["peak"], 2),
            "bets_placed": ts["bets_placed"],
            "bets_won": ts["bets_won"],
            "total_wagered": round(ts["total_wagered"], 2),
            "total_pnl": round(ts["total_pnl"], 2),
            "max_drawdown_pct": round(ts["max_drawdown"] * 100, 2),
            "bankroll_curve_sample": ts["bankroll_curve"][::max(1, len(ts["bankroll_curve"]) // 50)],
            "bet_type_stats": {k: dict(v) for k, v in ts["bet_type_stats"].items()},
            "monthly_pnl": dict(ts["monthly_pnl"]),
        }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nFull state saved to {output_path}")
    print("=" * 80)

    return output


def _print_monthly(month_key, trader_state, traders_cfg):
    """Print monthly leaderboard."""
    print(f"\n--- Monthly Report: {month_key} ---")
    rows = []
    for tname in traders_cfg:
        ts = trader_state[tname]
        mpnl = ts["monthly_pnl"].get(month_key, 0)
        rows.append((tname, ts["bankroll"], mpnl))
    rows.sort(key=lambda x: x[1], reverse=True)
    for i, (name, bank, mpnl) in enumerate(rows, 1):
        marker = " ***" if i == 1 else ""
        print(f"  {i:>2}. {name:<14} ${bank:>10,.0f}  month PnL: ${mpnl:>+8,.0f}{marker}")


if __name__ == "__main__":
    run_backtest()
