#!/usr/bin/env python3
"""
Trading Floor v4 — Multi-AI Competition + Political ETF Trading
================================================================
5 AI agents (Gemini, OpenRouter, Claude, Codex, Grok) compete on:
  1. NBA betting: Choose strategy from all model predictions
  2. Political ETF trading: Trade based on political signals

Each agent sees: all predictions, all strategies, all other agents' results.
Command center offices track backend department status.

Inherits v3 data structures (11 models, 22 strategies, 12 bet categories)
and adds per-AI-agent competition layer + political/ETF dimension.
"""

import json, os, sys, csv, math, hashlib
from pathlib import Path
from datetime import datetime, timezone, date
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

ROOT        = Path('/home/termius/mon-ipad')
NBA_AGENT   = Path('/home/termius/nomos-nba-agent')
POLITICAL   = Path('/home/termius/nomos-political-alpha')
DATA_DIR    = ROOT / 'data' / 'arena'
TRADERS_DIR = DATA_DIR / 'traders'

# ── TEAM MAP ────────────────────────────────────────────────────────────────
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

# ── 11 NBA PREDICTION MODELS (same as v3) ───────────────────────────────────
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

# ── 22 NBA STRATEGIES (same as v3) ──────────────────────────────────────────
STRATEGIES = {
    "full_kelly":          {"family": "kelly",        "fraction": 1.0,   "min_edge": 0.02, "max_pct": 0.25, "cats": "all"},
    "half_kelly":          {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.15, "cats": "all"},
    "quarter_kelly":       {"family": "kelly",        "fraction": 0.25,  "min_edge": 0.03, "max_pct": 0.08, "cats": "all"},
    "eighth_kelly":        {"family": "kelly",        "fraction": 0.125, "min_edge": 0.03, "max_pct": 0.05, "cats": "all"},
    "flat_1pct":           {"family": "flat",         "bet_pct": 0.01,   "min_edge": 0.01, "max_pct": 0.01, "cats": "all"},
    "flat_2pct":           {"family": "flat",         "bet_pct": 0.02,   "min_edge": 0.01, "max_pct": 0.02, "cats": "all"},
    "flat_5pct":           {"family": "flat",         "bet_pct": 0.05,   "min_edge": 0.02, "max_pct": 0.05, "cats": "all"},
    "diversified_flat":    {"family": "flat",         "bet_pct": 0.01,   "min_edge": 0.005,"max_pct": 0.01, "cats": "all"},
    "confidence_scaled":   {"family": "confidence",   "min_edge": 0.02,  "max_pct": 0.20,  "cats": "all"},
    "proportional_edge":   {"family": "proportional", "min_edge": 0.02,  "max_pct": 0.15,  "cats": "all", "multiplier": 3.0},
    "ev_threshold_110":    {"family": "ev_threshold", "min_edge": 0.02,  "max_pct": 0.15,  "cats": "all", "ev_gate": 1.10},
    "value_hunter":        {"family": "value",        "min_edge": 0.05,  "max_pct": 0.12,  "cats": "all"},
    "underdog_specialist": {"family": "underdog",     "min_odds": 2.2,   "min_edge": 0.03, "max_pct": 0.08, "cats": "all"},
    "dog_value_plus":      {"family": "underdog",     "min_odds": 3.0,   "min_edge": 0.02, "max_pct": 0.06, "cats": "all"},
    "totals_expert":       {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.15,
                            "cats": ["total_over", "total_under", "team_total_home_over", "team_total_home_under"]},
    "first_half_sniper":   {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.15,
                            "cats": ["h1_ml_home", "h1_ml_away"]},
    "home_specialist":     {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.12,
                            "cats": ["ml_home", "spread_home", "h1_ml_home"]},
    "spread_only":         {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.12,
                            "cats": ["spread_home", "spread_away", "alt_spread_home_big", "alt_spread_away_big"]},
    "anti_martingale":     {"family": "anti_mart",    "min_edge": 0.02,  "max_pct": 0.20,  "cats": "all", "base_pct": 0.02},
    "drawdown_adjusted":   {"family": "drawdown_adj", "min_edge": 0.02,  "max_pct": 0.15,  "cats": "all", "dd_threshold": 0.15},
    "streak_momentum":     {"family": "streak",       "min_edge": 0.02,  "max_pct": 0.20,  "cats": "all", "streak_boost": 3},
    "full_blast":          {"family": "full_blast",   "min_edge": 0.01,  "max_pct": 1.00,  "cats": "all"},
}

BANKROLL_THRESHOLDS = {
    500:   {"max_pct_mult": 0.7, "min_edge_add": 0.01},
    1000:  {"max_pct_mult": 0.5, "min_edge_add": 0.02},
    5000:  {"max_pct_mult": 0.3, "min_edge_add": 0.03},
    10000: {"max_pct_mult": 0.2, "min_edge_add": 0.04},
}

# ── AI AGENT DEFINITIONS ─────────────────────────────────────────────────────
# Each AI agent has a personality that determines:
#   - preferred_models: which NBA models they trust most
#   - preferred_strategies: preferred bet sizing approach
#   - pol_approach: political signal interpretation style
#   - etf_sectors: sector focus for ETF trading
TRADERS = {
    "gemini": {
        "name":               "Gemini",
        "provider":           "google",
        "personality":        "analytical",
        "risk_tolerance":     0.60,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["consensus_ensemble", "tabicl", "stacking_meta"],
        "preferred_strategies": ["half_kelly", "confidence_scaled", "proportional_edge"],
        "pol_approach":       "momentum",
        "etf_sectors":        ["XLK", "QQQ", "SPY"],
    },
    "openrouter": {
        "name":               "OpenRouter",
        "provider":           "openrouter",
        "personality":        "diversified",
        "risk_tolerance":     0.50,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["consensus_ensemble", "extra_trees", "lightgbm"],
        "preferred_strategies": ["quarter_kelly", "flat_2pct", "totals_expert"],
        "pol_approach":       "sector_rotation",
        "etf_sectors":        ["SPY", "IWM", "XLF", "XLE"],
    },
    "claude": {
        "name":               "Claude",
        "provider":           "anthropic",
        "personality":        "conservative",
        "risk_tolerance":     0.40,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["tabicl", "consensus_ensemble", "catboost"],
        "preferred_strategies": ["eighth_kelly", "flat_1pct", "drawdown_adjusted"],
        "pol_approach":       "mean_reversion",
        "etf_sectors":        ["TLT", "GLD", "XLV"],
    },
    "codex": {
        "name":               "Codex",
        "provider":           "openai",
        "personality":        "aggressive",
        "risk_tolerance":     0.70,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["xgboost", "lightgbm", "catboost"],
        "preferred_strategies": ["full_kelly", "streak_momentum", "anti_martingale"],
        "pol_approach":       "event_driven",
        "etf_sectors":        ["QQQ", "XLK", "XLI"],
    },
    "grok": {
        "name":               "Grok",
        "provider":           "xai",
        "personality":        "contrarian",
        "risk_tolerance":     0.65,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["elo_baseline", "random_forest", "extra_trees"],
        "preferred_strategies": ["underdog_specialist", "dog_value_plus", "value_hunter"],
        "pol_approach":       "pairs_trading",
        "etf_sectors":        ["XLE", "GLD", "IWM", "TLT"],
    },
}

# ── POLITICAL / ETF UNIVERSE ─────────────────────────────────────────────────
ETF_UNIVERSE = {
    "SPY": {"name": "S&P 500",              "sector": "broad",       "beta": 1.0},
    "QQQ": {"name": "NASDAQ 100",           "sector": "technology",  "beta": 1.2},
    "IWM": {"name": "Russell 2000",         "sector": "small_cap",   "beta": 1.1},
    "XLF": {"name": "Financials",           "sector": "financials",  "beta": 1.1},
    "XLE": {"name": "Energy",               "sector": "energy",      "beta": 1.3},
    "XLK": {"name": "Technology",           "sector": "technology",  "beta": 1.2},
    "XLV": {"name": "Healthcare",           "sector": "healthcare",  "beta": 0.8},
    "XLI": {"name": "Industrials",          "sector": "industrials", "beta": 1.0},
    "XLD": {"name": "Defense",              "sector": "defense",     "beta": 0.9},
    "GLD": {"name": "Gold",                 "sector": "commodity",   "beta": 0.3},
    "TLT": {"name": "Long-term Treasuries", "sector": "bonds",       "beta": -0.2},
    "LMT": {"name": "Lockheed Martin",      "sector": "defense",     "beta": 0.7},
    "RTX": {"name": "Raytheon",             "sector": "defense",     "beta": 0.8},
}

POLITICAL_SECTOR_MAP = {
    "defense":     ["XLD", "LMT", "RTX"],
    "technology":  ["XLK", "QQQ"],
    "energy":      ["XLE"],
    "healthcare":  ["XLV"],
    "financials":  ["XLF"],
    "broad":       ["SPY", "IWM"],
    "small_cap":   ["IWM"],
    "industrials": ["XLI"],
    "commodity":   ["GLD"],
    "bonds":       ["TLT"],
}

# ── COMMAND CENTER OFFICES ────────────────────────────────────────────────────
COMMAND_CENTERS = {
    "research_hq":       {"dept": "research",    "label": "Research HQ",      "icon": "research"},
    "engineering_lab":   {"dept": "engineering", "label": "Engineering Lab",   "icon": "engineering"},
    "evolution_chamber": {"dept": "evolution",   "label": "Evolution Chamber", "icon": "evolution"},
    "betting_ops":       {"dept": "betting",     "label": "Betting Ops",       "icon": "betting"},
    "infra_bridge":      {"dept": "infra",       "label": "Infra Bridge",      "icon": "infra"},
    "political_intel":   {"dept": "political",   "label": "Political Intel",   "icon": "political"},
}


# ── DATA LOADERS ─────────────────────────────────────────────────────────────

def load_games() -> Dict:
    """Load historical game results (2025-26 season)."""
    fp = NBA_AGENT / "data" / "historical" / "games-2025-26.json"
    if not fp.exists():
        return {}
    raw = json.loads(fp.read_text())
    games_list = raw.get("games", raw if isinstance(raw, list) else [])
    results = {}
    for g in games_list:
        game_date = g.get("game_date", "")
        home = TEAM_MAP.get(g.get("home_team", ""), g.get("home_team", ""))
        away = TEAM_MAP.get(g.get("away_team", ""), g.get("away_team", ""))
        h_data = g.get("home", {})
        a_data = g.get("away", {})
        hs  = h_data.get("pts", h_data.get("PTS", 0))
        as_ = a_data.get("pts", a_data.get("PTS", 0))
        if not hs and not as_:
            continue
        results[(game_date, home, away)] = {"home_score": hs, "away_score": as_}
    return results


def load_odds() -> Dict:
    """Load historical odds CSV."""
    fp = NBA_AGENT / "data" / "historical-odds" / "nba_2025-26_odds.csv"
    if not fp.exists():
        return {}
    odds = {}
    with open(fp) as f:
        reader = csv.DictReader(f)
        for row in reader:
            game_date = row.get("date", "")
            home = TEAM_MAP.get(row.get("home_team", ""), row.get("home_team", ""))
            away = TEAM_MAP.get(row.get("away_team", ""), row.get("away_team", ""))

            def parse_odds(s):
                if not s or not s.strip():
                    return None
                v = float(s.strip())
                if 1.0 < v < 15.0 and '.' in s.strip():
                    return v
                v = int(v)
                if v > 0: return v / 100.0 + 1
                if v < 0: return 100.0 / abs(v) + 1
                return 2.0

            try:
                ml_home  = parse_odds(row.get("moneyline_home", ""))
                ml_away  = parse_odds(row.get("moneyline_away", ""))
                spread_s = row.get("spread_home", "").strip()
                total_s  = row.get("total", "").strip()
                spread   = float(spread_s) if spread_s else None
                total    = float(total_s)  if total_s  else None
                if ml_home and ml_away:
                    odds[(game_date, home, away)] = {
                        "ml_home_dec": ml_home, "ml_away_dec": ml_away,
                        "spread_home": spread, "total": total,
                    }
            except (ValueError, TypeError):
                continue
    return odds


def load_political_signals() -> Dict:
    """Load latest political social signals for ETF trading."""
    signals_file = POLITICAL / "data" / "social" / "social_signals_latest.json"
    if signals_file.exists():
        try:
            data = json.loads(signals_file.read_text())
            return data.get("signals", data)
        except Exception:
            pass
    return {}


def load_department_status() -> Dict:
    """Load department/agent health status for command centers."""
    for fp in [
        ROOT / "data" / "agent-health.json",
        ROOT / "data" / "swarm-metrics.json",
    ]:
        if fp.exists():
            try:
                return json.loads(fp.read_text())
            except Exception:
                continue
    return {}


def load_other_trader_states(exclude: str) -> Dict:
    """Load all trader states except the excluded one (competitive awareness)."""
    results = {}
    for trader_id in TRADERS:
        if trader_id == exclude:
            continue
        sf = TRADERS_DIR / f"{trader_id}-state.json"
        if sf.exists():
            try:
                results[trader_id] = json.loads(sf.read_text())
            except Exception:
                pass
    return results


# ── NBA SIMULATION HELPERS ────────────────────────────────────────────────────

def model_prob(model_name: str, implied_prob: float, seed_val: str, home_won: bool) -> float:
    """Brier-calibrated prediction (identical to v3 — no random noise)."""
    brier    = MODELS[model_name]["brier"]
    skill    = max(0.0, 1.0 - brier / 0.25)
    h        = int(hashlib.md5(f"{model_name}_{seed_val}".encode()).hexdigest()[:8], 16)
    variation = ((h % 1000) / 1000.0 - 0.5) * 0.06
    truth     = 1.0 if home_won else 0.0
    pred      = implied_prob + skill * (truth - implied_prob) * 0.5 + variation
    return max(0.05, min(0.95, pred))


def h1_result_from_hash(seed: str, home_won: bool) -> bool:
    """Deterministic 1H result correlated with full game (52%)."""
    h = int(hashlib.md5(f"h1_{seed}".encode()).hexdigest()[:4], 16)
    corr_flip = (h % 100) < 52
    return home_won if corr_flip else (not home_won)


def kelly_size(p: float, odds: float, fraction: float = 1.0) -> float:
    b = odds - 1.0
    if b <= 0:
        return 0.0
    edge = p * b - (1.0 - p)
    if edge <= 0:
        return 0.0
    return max(0.0, (edge / b) * fraction)


def get_bet_size(strat_name: str, prob: float, odds: float,
                 bankroll: float, comp_state: Optional[Dict] = None) -> float:
    """Calculate bet size for a given NBA strategy (v3-compatible)."""
    cfg      = STRATEGIES[strat_name]
    min_edge = cfg["min_edge"]
    max_pct  = cfg["max_pct"]
    for threshold, adj in sorted(BANKROLL_THRESHOLDS.items()):
        if bankroll >= threshold:
            max_pct  *= adj["max_pct_mult"]
            min_edge += adj["min_edge_add"]

    edge = prob * (odds - 1.0) - (1.0 - prob)
    if edge < min_edge:
        return 0.0
    if cfg["family"] == "underdog" and odds < cfg.get("min_odds", 2.2):
        return 0.0
    if cfg["family"] == "ev_threshold":
        if prob * odds < cfg.get("ev_gate", 1.10):
            return 0.0

    max_bet = bankroll * max_pct
    fam     = cfg["family"]

    if fam == "kelly":
        bet = kelly_size(prob, odds, cfg["fraction"]) * bankroll
    elif fam == "flat":
        bet = bankroll * cfg["bet_pct"]
    elif fam == "confidence":
        conf = (abs(prob - 0.5) * 2) ** 2
        bet  = conf * max_bet
    elif fam == "proportional":
        bet = edge * cfg.get("multiplier", 3.0) * bankroll
    elif fam == "ev_threshold":
        bet = kelly_size(prob, odds, 0.5) * bankroll
    elif fam in ("value", "underdog"):
        bet = kelly_size(prob, odds, 0.5) * bankroll
    elif fam == "anti_mart":
        base = bankroll * cfg.get("base_pct", 0.02)
        if comp_state and comp_state.get("last_won"):
            bet = min(base * 2, max_bet)
        else:
            bet = base
    elif fam == "drawdown_adj":
        dd    = 1.0 - bankroll / comp_state.get("peak", bankroll) if comp_state else 0.0
        scale = max(0.25, 1.0 - dd / cfg.get("dd_threshold", 0.15))
        bet   = kelly_size(prob, odds, 0.5) * bankroll * scale
    elif fam == "streak":
        base   = kelly_size(prob, odds, 0.25) * bankroll
        streak = comp_state.get("win_streak", 0) if comp_state else 0
        bet    = base * 2 if streak >= cfg.get("streak_boost", 3) else base
    elif fam == "full_blast":
        bet = bankroll
    else:
        bet = bankroll * 0.02

    return min(max(bet, 0.0), max_bet)


# ── AGENT NBA STRATEGY LOGIC ──────────────────────────────────────────────────

def agent_select_nba_model(trader_id: str, day_model_probs: Dict,
                            others_states: Dict) -> str:
    """
    Each AI agent picks which model to trust for NBA betting on a given day.
      analytical  → best Brier among preferred models
      diversified → rotate by day-of-year
      conservative→ least extreme model (closest avg prob to 0.5)
      aggressive  → most extreme model (furthest from 0.5)
      contrarian  → highest Brier (fade the consensus models)
    """
    cfg         = TRADERS[trader_id]
    personality = cfg["personality"]
    preferred   = cfg["preferred_models"]

    if personality == "analytical":
        return min(preferred, key=lambda m: MODELS[m]["brier"])

    elif personality == "diversified":
        day_idx = date.today().timetuple().tm_yday
        return preferred[day_idx % len(preferred)]

    elif personality == "conservative":
        if day_model_probs:
            return min(
                preferred,
                key=lambda m: abs(day_model_probs.get(m, {}).get("avg_prob", 0.5) - 0.5),
            )
        return preferred[0]

    elif personality == "aggressive":
        if day_model_probs:
            return max(
                preferred,
                key=lambda m: abs(day_model_probs.get(m, {}).get("avg_prob", 0.5) - 0.5),
            )
        return preferred[0]

    elif personality == "contrarian":
        return max(preferred, key=lambda m: MODELS[m]["brier"])

    return preferred[0]


def agent_select_nba_strategy(trader_id: str, bankroll: float,
                               others_states: Dict) -> str:
    """
    Each AI agent picks a betting strategy, with awareness of competitors.
    Trailing  → more aggressive; Leading → more conservative.
    """
    cfg         = TRADERS[trader_id]
    personality = cfg["personality"]
    preferred   = cfg["preferred_strategies"]

    other_bankrolls = [
        s.get("nba_bankroll", 100.0)
        for s in others_states.values()
        if "nba_bankroll" in s
    ]
    if other_bankrolls:
        avg_other = sum(other_bankrolls) / len(other_bankrolls)
        trailing  = bankroll < avg_other * 0.9
        leading   = bankroll > avg_other * 1.2
    else:
        trailing = leading = False

    if personality == "conservative":
        if trailing:
            return "quarter_kelly"
        return preferred[0]

    elif personality == "aggressive":
        if leading:
            return "half_kelly"
        return preferred[0]

    elif personality == "contrarian":
        if trailing:
            return "dog_value_plus"
        return "underdog_specialist"

    elif personality == "analytical":
        if trailing:
            return "confidence_scaled"
        if leading:
            return "eighth_kelly"
        return "half_kelly"

    elif personality == "diversified":
        day_idx = date.today().timetuple().tm_yday
        return preferred[day_idx % len(preferred)]

    return preferred[0]


# ── POLITICAL / ETF TRADING LOGIC ────────────────────────────────────────────

def compute_etf_signal(ticker: str, signals: Dict) -> Dict:
    """
    Compute directional signal for one ETF from political social signals.
    Returns: {direction: 'long'|'short'|'neutral', strength: 0-1, reason: str}
    """
    if ticker in signals:
        sig       = signals[ticker]
        strength  = sig.get("signal_strength", 0.0)
        sentiment = sig.get("combined_sentiment", 0.0)
        if abs(strength) < 0.05:
            return {"direction": "neutral", "strength": 0.0, "reason": "no_signal"}
        direction = "long" if sentiment >= 0 else "short"
        return {"direction": direction, "strength": min(abs(strength), 1.0), "reason": "direct_signal"}

    etf_sector = ETF_UNIVERSE.get(ticker, {}).get("sector", "")
    related    = POLITICAL_SECTOR_MAP.get(etf_sector, [])
    sector_sents = [
        signals[t].get("combined_sentiment", 0.0)
        for t in related
        if t in signals and t != ticker
    ]
    if not sector_sents:
        return {"direction": "neutral", "strength": 0.0, "reason": "no_sector_data"}

    avg_sent = sum(sector_sents) / len(sector_sents)
    strength  = min(abs(avg_sent), 1.0)
    if strength < 0.03:
        return {"direction": "neutral", "strength": 0.0, "reason": "weak_sector"}
    direction = "long" if avg_sent >= 0 else "short"
    return {"direction": direction, "strength": strength, "reason": "sector_aggregate"}


def agent_political_trades(trader_id: str, political_bankroll: float,
                           signals: Dict, others_states: Dict) -> List[Dict]:
    """
    Generate ETF positions for one AI agent based on their political approach.
    Returns list of position dicts.
    """
    cfg       = TRADERS[trader_id]
    approach  = cfg["pol_approach"]
    focus     = cfg["etf_sectors"]
    risk      = cfg["risk_tolerance"]
    max_pos   = 0.10 * risk   # e.g., conservative (0.4) → 4%, aggressive (0.7) → 7%

    positions = []

    if approach == "momentum":
        for ticker in focus:
            sig = compute_etf_signal(ticker, signals)
            if sig["direction"] == "neutral":
                continue
            size = political_bankroll * max_pos * sig["strength"]
            positions.append({"ticker": ticker, "direction": sig["direction"],
                               "size_usd": round(size, 2),
                               "signal_strength": round(sig["strength"], 4),
                               "reason": sig["reason"], "approach": "momentum"})

    elif approach == "mean_reversion":
        for ticker in focus:
            sig = compute_etf_signal(ticker, signals)
            if sig["direction"] == "neutral" or sig["strength"] < 0.3:
                continue
            rev = "short" if sig["direction"] == "long" else "long"
            size = political_bankroll * max_pos * sig["strength"] * 0.5
            positions.append({"ticker": ticker, "direction": rev,
                               "size_usd": round(size, 2),
                               "signal_strength": round(sig["strength"], 4),
                               "reason": "mean_reversion_of_" + sig["reason"],
                               "approach": "mean_reversion"})

    elif approach == "event_driven":
        for ticker in focus:
            sig = compute_etf_signal(ticker, signals)
            if sig["strength"] < 0.2:
                continue
            size = min(political_bankroll * max_pos * 1.5 * sig["strength"],
                       political_bankroll * 0.15)
            positions.append({"ticker": ticker, "direction": sig["direction"],
                               "size_usd": round(size, 2),
                               "signal_strength": round(sig["strength"], 4),
                               "reason": sig["reason"], "approach": "event_driven"})

    elif approach == "pairs_trading":
        tickers_sigs = [(t, compute_etf_signal(t, signals)) for t in focus]
        longs  = [(t, s) for t, s in tickers_sigs if s["direction"] == "long"  and s["strength"] > 0.05]
        shorts = [(t, s) for t, s in tickers_sigs if s["direction"] == "short" and s["strength"] > 0.05]
        longs.sort(key=lambda x: -x[1]["strength"])
        shorts.sort(key=lambda x: -x[1]["strength"])
        pair_size = political_bankroll * max_pos
        if longs:
            t, s = longs[0]
            positions.append({"ticker": t, "direction": "long", "size_usd": round(pair_size, 2),
                               "signal_strength": round(s["strength"], 4),
                               "reason": "pairs_long", "approach": "pairs_trading"})
        if shorts:
            t, s = shorts[0]
            positions.append({"ticker": t, "direction": "short", "size_usd": round(pair_size, 2),
                               "signal_strength": round(s["strength"], 4),
                               "reason": "pairs_short", "approach": "pairs_trading"})

    elif approach == "sector_rotation":
        scored = [(t, compute_etf_signal(t, signals)) for t in focus]
        scored = [(t, s) for t, s in scored if s["direction"] == "long" and s["strength"] > 0.0]
        scored.sort(key=lambda x: -x[1]["strength"])
        total_str  = sum(s["strength"] for _, s in scored) or 1.0
        allocation = political_bankroll * risk * 0.5
        for ticker, sig in scored[:3]:
            weight = sig["strength"] / total_str
            size   = allocation * weight
            positions.append({"ticker": ticker, "direction": "long",
                               "size_usd": round(size, 2),
                               "signal_strength": round(sig["strength"], 4),
                               "reason": sig["reason"], "approach": "sector_rotation"})

    return positions


# ── NBA FULL-SEASON BACKTEST PER AGENT ───────────────────────────────────────

def run_nba_backtest_for_agent(trader_id: str, matched: List,
                               others_states: Dict) -> Dict:
    """
    Run full-season NBA backtest for one AI agent using v3 bet logic.
    Agent picks model + strategy per day, with competitive awareness.
    """
    bankroll   = TRADERS[trader_id]["bankroll_nba"]
    comp_state = {"last_won": False, "win_streak": 0, "peak": bankroll}
    total_bets = wins = losses = pushes = 0
    total_wagered = total_profit = 0.0
    peak_bankroll = bankroll
    max_drawdown  = 0.0
    bets_history  = []
    eliminated_day = None
    day_results    = []

    days = defaultdict(list)
    for item in matched:
        key, result, odd = item
        days[key[0]].append(item)
    sorted_days = sorted(days.keys())

    for day_num, day_date in enumerate(sorted_days, 1):
        if bankroll <= 0:
            if eliminated_day is None:
                eliminated_day = day_num
            break

        day_games = days[day_date]

        # Compute per-model average probability for this day
        day_model_probs: Dict[str, Dict] = {}
        for model_name in MODELS:
            probs = []
            for key, result, odd in day_games:
                home_won = result["home_score"] > result["away_score"]
                implied  = 1.0 / odd["ml_home_dec"]
                p = model_prob(model_name, implied,
                               f"{key[0]}_{key[1]}_{key[2]}", home_won)
                probs.append(p)
            if probs:
                day_model_probs[model_name] = {"avg_prob": sum(probs) / len(probs)}

        chosen_model    = agent_select_nba_model(trader_id, day_model_probs, others_states)
        chosen_strategy = agent_select_nba_strategy(trader_id, bankroll, others_states)
        strat_cfg       = STRATEGIES[chosen_strategy]
        allowed_cats    = strat_cfg["cats"]

        day_bets   = 0
        day_profit = 0.0

        for key, result, odd in day_games:
            if bankroll <= 0:
                break

            home_won   = result["home_score"] > result["away_score"]
            hs         = result["home_score"]
            as_        = result["away_score"]
            total_pts  = hs + as_
            seed_val   = f"{key[0]}_{key[1]}_{key[2]}"
            implied    = 1.0 / odd["ml_home_dec"]
            prob_home  = model_prob(chosen_model, implied, seed_val, home_won)
            prob_away  = 1.0 - prob_home
            h1_won     = h1_result_from_hash(seed_val, home_won)
            h1_prob_home = model_prob(chosen_model, implied, f"h1_{seed_val}", h1_won)
            h1_prob_away = 1.0 - h1_prob_home

            # Build bet candidates
            candidates = []

            if allowed_cats == "all" or "ml_home" in allowed_cats:
                candidates.append(("ml_home", prob_home, odd["ml_home_dec"], home_won))
            if allowed_cats == "all" or "ml_away" in allowed_cats:
                candidates.append(("ml_away", prob_away, odd["ml_away_dec"], not home_won))

            if odd.get("spread_home") is not None:
                spread = odd["spread_home"]
                if allowed_cats == "all" or "spread_home" in allowed_cats:
                    candidates.append(("spread_home", prob_home * 0.9, 1.909,
                                       (hs + spread) > as_))
                if allowed_cats == "all" or "spread_away" in allowed_cats:
                    candidates.append(("spread_away", prob_away * 0.9, 1.909,
                                       (as_ - spread) > hs))

            if odd.get("total"):
                line       = odd["total"]
                prob_over  = 0.48 + (prob_home - 0.5) * 0.1
                prob_under = 1.0 - prob_over
                home_line  = line / 2.0
                prob_home_over = 0.48 + (prob_home - 0.5) * 0.15
                if allowed_cats == "all" or "total_over" in allowed_cats:
                    candidates.append(("total_over",  prob_over,  1.909, total_pts > line))
                if allowed_cats == "all" or "total_under" in allowed_cats:
                    candidates.append(("total_under", prob_under, 1.909, total_pts < line))
                if allowed_cats == "all" or "team_total_home_over" in allowed_cats:
                    candidates.append(("team_total_home_over",  prob_home_over,       1.909, hs > home_line))
                if allowed_cats == "all" or "team_total_home_under" in allowed_cats:
                    candidates.append(("team_total_home_under", 1.0 - prob_home_over, 1.909, hs < home_line))

            if allowed_cats == "all" or "h1_ml_home" in allowed_cats:
                candidates.append(("h1_ml_home", h1_prob_home, odd["ml_home_dec"] * 0.95, h1_won))
            if allowed_cats == "all" or "h1_ml_away" in allowed_cats:
                candidates.append(("h1_ml_away", h1_prob_away, odd["ml_away_dec"] * 0.95, not h1_won))

            if allowed_cats == "all" or "alt_spread_home_big" in allowed_cats:
                candidates.append(("alt_spread_home_big", prob_home * 0.7, 2.5, (hs - as_) > 8))
            if allowed_cats == "all" or "alt_spread_away_big" in allowed_cats:
                candidates.append(("alt_spread_away_big", prob_away * 0.7, 2.5, (as_ - hs) > 8))

            for cat, prob, odds_val, outcome in candidates:
                if allowed_cats != "all" and cat not in allowed_cats:
                    continue
                bet = get_bet_size(chosen_strategy, prob, odds_val, bankroll, comp_state)
                if bet <= 0:
                    continue
                bet = min(bet, bankroll)

                total_bets    += 1
                day_bets      += 1
                total_wagered += bet

                if outcome:
                    profit = bet * (odds_val - 1.0)
                    wins  += 1
                    comp_state["last_won"]   = True
                    comp_state["win_streak"] = comp_state.get("win_streak", 0) + 1
                else:
                    profit = -bet
                    losses += 1
                    comp_state["last_won"]   = False
                    comp_state["win_streak"] = 0

                bankroll      += profit
                day_profit    += profit
                total_profit  += profit

                if bankroll > peak_bankroll:
                    peak_bankroll      = bankroll
                    comp_state["peak"] = bankroll
                dd = 1.0 - bankroll / peak_bankroll if peak_bankroll > 0 else 0.0
                if dd > max_drawdown:
                    max_drawdown = dd

                bets_history.append({
                    "date": key[0], "cat": cat,
                    "bet": round(bet, 4), "profit": round(profit, 4),
                    "bankroll_after": round(bankroll, 4),
                })
                if bankroll <= 0:
                    eliminated_day = day_num
                    break

        day_results.append({
            "day":      day_num,
            "date":     day_date,
            "model":    chosen_model,
            "strategy": chosen_strategy,
            "bets":     day_bets,
            "profit":   round(day_profit, 4),
            "bankroll": round(bankroll, 4),
        })

    roi = round((bankroll - 100.0) / 100.0 * 100, 2)
    sharpe = 0.0
    if len(day_results) > 1:
        daily_returns = [d["profit"] for d in day_results]
        avg_r = sum(daily_returns) / len(daily_returns)
        std_r = (sum((r - avg_r) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
        if std_r > 0:
            sharpe = round((avg_r / std_r) * (252 ** 0.5), 3)

    return {
        "trader_id":           trader_id,
        "nba_bankroll":        round(bankroll, 4),
        "nba_roi_pct":         roi,
        "nba_sharpe":          sharpe,
        "nba_bets":            total_bets,
        "nba_wins":            wins,
        "nba_losses":          losses,
        "nba_pushes":          pushes,
        "nba_wagered":         round(total_wagered, 4),
        "nba_profit":          round(total_profit, 4),
        "nba_peak":            round(peak_bankroll, 4),
        "nba_max_drawdown":    round(max_drawdown, 4),
        "nba_eliminated_day":  eliminated_day,
        "nba_day_results":     day_results,
        "nba_bets_history":    bets_history[-200:],
    }


# ── POLITICAL BACKTEST PER AGENT ─────────────────────────────────────────────

def run_political_backtest_for_agent(trader_id: str, signals: Dict,
                                     others_states: Dict) -> Dict:
    """
    Run political ETF trading simulation for one AI agent.
    Positions and P&L are signal-strength driven (directional simulation).
    """
    bankroll  = TRADERS[trader_id]["bankroll_political"]
    positions = agent_political_trades(trader_id, bankroll, signals, others_states)
    total_size = sum(p["size_usd"] for p in positions)

    simulated_pnl = 0.0
    for pos in positions:
        etf_beta     = ETF_UNIVERSE.get(pos["ticker"], {}).get("beta", 1.0)
        expected_ret = pos["signal_strength"] * etf_beta * 0.005
        if pos["direction"] == "short":
            expected_ret *= -1
        simulated_pnl += pos["size_usd"] * expected_ret

    new_bankroll = bankroll + simulated_pnl
    roi = round((new_bankroll - bankroll) / bankroll * 100, 4) if bankroll > 0 else 0.0

    return {
        "trader_id":               trader_id,
        "political_bankroll":      round(new_bankroll, 2),
        "political_roi_pct":       roi,
        "political_positions":     positions,
        "political_total_size":    round(total_size, 2),
        "political_simulated_pnl": round(simulated_pnl, 2),
        "political_approach":      TRADERS[trader_id]["pol_approach"],
    }


# ── COMMAND CENTER STATUS ─────────────────────────────────────────────────────

def build_command_center_status(dept_data: Dict) -> Dict:
    """Map raw health JSON to command center display objects."""
    cc_status = {}
    for cc_id, cc_cfg in COMMAND_CENTERS.items():
        dept = cc_cfg["dept"]
        raw  = (
            dept_data.get("departments", {}).get(dept)
            or dept_data.get(dept)
            or {}
        )
        cc_status[cc_id] = {
            "label":    cc_cfg["label"],
            "icon":     cc_cfg["icon"],
            "status":   raw.get("status", "unknown"),
            "active":   raw.get("active", False),
            "last_run": raw.get("last_run") or raw.get("last_updated"),
            "metrics":  raw.get("metrics") or raw.get("kpis") or {},
        }
    return cc_status


# ── LEADERBOARD ───────────────────────────────────────────────────────────────

def build_leaderboard(all_results: Dict) -> List[Dict]:
    """Build ranked leaderboard combining NBA + political performance."""
    board = []
    for trader_id, state in all_results.items():
        nba_roi  = state.get("nba_roi_pct", 0.0)
        pol_roi  = state.get("political_roi_pct", 0.0)
        combined = nba_roi + pol_roi * 0.1   # NBA dominates; political is supplementary
        board.append({
            "rank":               0,
            "trader_id":          trader_id,
            "name":               state.get("name", trader_id),
            "provider":           state.get("provider", ""),
            "personality":        state.get("personality", ""),
            "nba_bankroll":       state.get("nba_bankroll", 100.0),
            "nba_roi_pct":        nba_roi,
            "nba_sharpe":         state.get("nba_sharpe", 0.0),
            "nba_bets":           state.get("nba_bets", 0),
            "nba_wins":           state.get("nba_wins", 0),
            "nba_losses":         state.get("nba_losses", 0),
            "political_bankroll": state.get("political_bankroll", 100_000.0),
            "political_roi_pct":  pol_roi,
            "political_approach": state.get("political_approach", ""),
            "combined_score":     round(combined, 4),
            "eliminated":         state.get("nba_eliminated_day") is not None,
        })
    board.sort(key=lambda x: x["combined_score"], reverse=True)
    for i, entry in enumerate(board, 1):
        entry["rank"] = i
    return board


# ── MAIN ORCHESTRATOR ─────────────────────────────────────────────────────────

def run_full_competition() -> Dict:
    """Run full-season competition for all 5 AI agents (NBA + political)."""
    print("Loading games...")
    games = load_games()
    odds  = load_odds()
    print(f"  Games with results : {len(games)}")
    print(f"  Games with odds    : {len(odds)}")

    matched = []
    for key in sorted(odds.keys()):
        if key in games:
            matched.append((key, games[key], odds[key]))
    print(f"  Matched            : {len(matched)}")
    if not matched:
        print("  WARNING: No matched games — NBA backtest will be empty.")

    print("Loading political signals...")
    signals   = load_political_signals()
    print(f"  Tickers with signals: {len(signals)}")

    print("Loading department status...")
    dept_data = load_department_status()

    TRADERS_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "political").mkdir(parents=True, exist_ok=True)

    all_results: Dict[str, Dict] = {}

    for trader_id in TRADERS:
        cfg = TRADERS[trader_id]
        print(f"\nAgent [{trader_id}] — {cfg['personality']} / {cfg['pol_approach']}")
        others = load_other_trader_states(trader_id)

        nba_result = run_nba_backtest_for_agent(trader_id, matched, others)
        pol_result = run_political_backtest_for_agent(trader_id, signals, others)

        state = {
            "trader_id":      trader_id,
            "name":           cfg["name"],
            "provider":       cfg["provider"],
            "personality":    cfg["personality"],
            "risk_tolerance": cfg["risk_tolerance"],
            **nba_result,
            **pol_result,
            "saw_others":     list(others.keys()),
            "run_timestamp":  datetime.now(timezone.utc).isoformat(),
        }

        (TRADERS_DIR / f"{trader_id}-state.json").write_text(json.dumps(state, indent=2))
        all_results[trader_id] = state

        print(f"  NBA     : ${nba_result['nba_bankroll']:.2f}  ROI {nba_result['nba_roi_pct']:+.1f}%"
              f"  Sharpe {nba_result['nba_sharpe']:.2f}"
              f"  ({nba_result['nba_wins']}W-{nba_result['nba_losses']}L)")
        print(f"  Political: ${pol_result['political_bankroll']:.2f}"
              f"  ROI {pol_result['political_roi_pct']:+.4f}%"
              f"  ({len(pol_result['political_positions'])} positions)")

    board     = build_leaderboard(all_results)
    cc_status = build_command_center_status(dept_data)

    output = {
        "meta": {
            "version":            "trading-floor-v4",
            "generated":          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date":               date.today().isoformat(),
            "traders":            len(TRADERS),
            "nba_models":         len(MODELS),
            "nba_strategies":     len(STRATEGIES),
            "matched_games":      len(matched),
            "political_tickers":  len(signals),
            "etf_universe":       len(ETF_UNIVERSE),
        },
        "leaderboard": board,
        "traders": {
            tid: {k: v for k, v in s.items()
                  if k not in ("nba_day_results", "nba_bets_history")}
            for tid, s in all_results.items()
        },
        "command_centers": cc_status,
        "models":     {m: {"brier": cfg["brier"]} for m, cfg in MODELS.items()},
        "strategies": {s: {"family": cfg["family"], "max_pct": cfg["max_pct"]}
                       for s, cfg in STRATEGIES.items()},
        "etf_universe": ETF_UNIVERSE,
    }

    latest = DATA_DIR / "trading-floor-v4-latest.json"
    dated  = DATA_DIR / f"trading-floor-v4-{date.today().isoformat()}.json"
    latest.write_text(json.dumps(output, indent=2))
    dated.write_text(json.dumps(output, indent=2))
    print(f"\nSaved: {latest}")
    print(f"Saved: {dated}")

    return output


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        result = run_full_competition()
        print("\n--- LEADERBOARD ---")
        print(json.dumps(result["leaderboard"], indent=2))

    elif cmd == "leaderboard":
        states = {}
        for tid in TRADERS:
            sf = TRADERS_DIR / f"{tid}-state.json"
            if sf.exists():
                try:
                    states[tid] = json.loads(sf.read_text())
                except Exception:
                    pass
        if not states:
            print("No trader states found. Run with 'run' first.")
        else:
            print(json.dumps(build_leaderboard(states), indent=2))

    elif cmd == "status":
        for tid in TRADERS:
            sf = TRADERS_DIR / f"{tid}-state.json"
            if sf.exists():
                s = json.loads(sf.read_text())
                print(f"{tid:12s}: NBA ${s.get('nba_bankroll', 100):.2f} "
                      f"({s.get('nba_roi_pct', 0):+.1f}%)  "
                      f"POL ${s.get('political_bankroll', 100000):.2f}"
                      f"  [{s.get('personality', '?')}]")
            else:
                print(f"{tid:12s}: no state yet")

    else:
        print(f"Usage: {sys.argv[0]} [run|leaderboard|status]")
        sys.exit(1)
