#!/usr/bin/env python3
"""
Trading Floor v8 — Cross-Repo Iterative Engine + Multi-AI Competition
=====================================================================
5 AI agents (Gemini, OpenRouter, Claude, Codex, Grok) compete on:
  1. NBA betting: Choose strategy from all model predictions
  2. Political ETF trading: Trade based on political signals

v8 upgrades over v4/v5:
  - Cross-repo integration: reads karpathy outputs from all satellite repos
  - Continuous iteration mode: `iterate` command loops forever
  - Cron-activated: every 4h, runs full analysis + mutation + next iteration
  - All repos synchronized: mon-ipad pilots nomos-nba-agent + nomos-political-alpha + rgwa
  - Guardian cross-pollination integrated into each iteration
  - $1M fitness tracking with generational improvement history

Inherits v5 data structures (11 models, 22 strategies, 16 bet categories,
per-game decisions, structured justifications, season documents).
"""

import json, os, sys, csv, math, hashlib, time, signal as _signal, subprocess
from pathlib import Path
from datetime import datetime, timezone, date
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

ROOT        = Path('/home/termius/mon-ipad')

# ── ITERATION / GENERATION TRACKING ──────────────────────────────────────────
# Incremented each run; generation tracks game-day count
_ITERATION_FILE = Path('/home/termius/mon-ipad/data/arena/trading-floor-iteration.json')

def _load_iteration() -> Dict:
    if _ITERATION_FILE.exists():
        try:
            return json.loads(_ITERATION_FILE.read_text())
        except Exception:
            pass
    return {"iteration": 0, "generation": 0}

def _save_iteration(it: Dict) -> None:
    _ITERATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ITERATION_FILE.write_text(json.dumps(it, indent=2))

# ── ELIMINATED NBA STRATEGIES ─────────────────────────────────────────────────
# These strategies have been permanently eliminated due to sustained negative ROI.
# They are never selected by agents; kept here as a historical coffin record.
ELIMINATED_STRATEGIES: Dict[str, Dict] = {
    "totals_expert": {
        "eliminated_at": "2026-03-31",
        "reason": "-72% ROI",
        "final_roi": -0.72,
        "department": "D4_BETTING",
    },
    "spread_only": {
        "eliminated_at": "2026-03-31",
        "reason": "-97% ROI",
        "final_roi": -0.97,
        "department": "D4_BETTING",
    },
    "full_blast": {
        "eliminated_at": "2026-03-31",
        "reason": "-100% ROI",
        "final_roi": -1.00,
        "department": "D4_BETTING",
    },
}

# ── ELIMINATED POLITICAL STRATEGIES ──────────────────────────────────────────
ELIMINATED_POLITICAL_STRATEGIES: Dict[str, Dict] = {
    "SECTOR_ROTATE": {
        "eliminated_at": "2026-03-31",
        "reason": "-75% ROI",
        "final_roi": -0.75,
        "department": "D7_POLITICAL",
    },
    "DEFENSE_LONG_individual": {
        "eliminated_at": "2026-03-31",
        "reason": "-65% ROI on individual defense stock picks",
        "final_roi": -0.65,
        "department": "D7_POLITICAL",
    },
    "BILL_PASSES": {
        "eliminated_at": "2026-03-31",
        "reason": "-64% ROI",
        "final_roi": -0.64,
        "department": "D7_POLITICAL",
    },
}

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
    # totals_expert  — ELIMINATED 2026-03-31 (-72% ROI)
    # spread_only    — ELIMINATED 2026-03-31 (-97% ROI)
    # full_blast     — ELIMINATED 2026-03-31 (-100% ROI)
    "first_half_sniper":   {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.15,
                            "cats": ["h1_ml_home", "h1_ml_away"]},
    "first_half_away":     {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.12,
                            "cats": ["h1_ml_away"],
                            "note": "h1_ml_away 53.2% win-rate specialist (D4 rec 2026-03-31)"},
    "home_specialist":     {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.12,
                            "cats": ["ml_home", "spread_home", "h1_ml_home"]},
    "anti_martingale":     {"family": "anti_mart",    "min_edge": 0.02,  "max_pct": 0.20,  "cats": "all", "base_pct": 0.02},
    "drawdown_adjusted":   {"family": "drawdown_adj", "min_edge": 0.02,  "max_pct": 0.15,  "cats": "all", "dd_threshold": 0.15},
    "streak_momentum":     {"family": "streak",       "min_edge": 0.02,  "max_pct": 0.20,  "cats": "all", "streak_boost": 3},
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
        "preferred_strategies": ["quarter_kelly", "flat_2pct", "value_hunter"],
        # totals_expert replaced by value_hunter (eliminated 2026-03-31, -72% ROI)
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
        "preferred_strategies": ["half_kelly", "flat_1pct", "drawdown_adjusted"],
        # D4 rec 2026-03-31: switched live strategy from quarter_kelly → half_kelly
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
        "preferred_strategies": ["full_kelly", "streak_momentum", "anti_martingale", "proportional_edge"],
        # full_blast replaced by proportional_edge (eliminated 2026-03-31, -100% ROI)
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
    "defense":     ["XLD", "LMT", "RTX", "BA", "GD", "NOC"],
    "technology":  ["XLK", "QQQ", "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMZN", "TSLA"],
    "energy":      ["XLE", "XOM", "CVX", "COP", "OXY", "HAL"],
    "healthcare":  ["XLV", "PFE", "JNJ", "UNH"],
    "financials":  ["XLF", "JPM", "GS", "MS", "BLK", "AXP"],
    "broad":       ["SPY", "IWM", "WMT"],
    "small_cap":   ["IWM"],
    "industrials": ["XLI", "WMT"],
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


# ── OPTIMIZATION TARGET ──────────────────────────────────────────────────────
OPTIMIZATION_TARGET = 1_000_000  # $1M from $100
BEST_CONFIG_FILE = DATA_DIR / 'best-config-toward-1M.json'


def _load_best_config() -> Dict:
    """Load best configuration ever found toward $1M target."""
    if BEST_CONFIG_FILE.exists():
        try:
            return json.loads(BEST_CONFIG_FILE.read_text())
        except Exception:
            pass
    return {
        "best_bankroll": 100.0,
        "best_trader_id": None,
        "best_iteration": 0,
        "distance_to_1M_pct": 100.0,
        "history": [],
        "agent_configs": {},
    }


def _save_best_config(config: Dict) -> None:
    """Persist best configuration."""
    BEST_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    BEST_CONFIG_FILE.write_text(json.dumps(config, indent=2))


# ── DATA LOADERS ─────────────────────────────────────────────────────────────

STAT_KEYS = ['fg_pct', 'fg3_pct', 'ft_pct', 'reb', 'ast', 'tov', 'stl', 'blk', 'plus_minus']

def load_games_rich() -> Tuple[Dict, List[Dict]]:
    """Load historical game results with FULL team stats (2025-26 season).
    Returns: (results_dict, raw_games_list_sorted_by_date)"""
    fp = NBA_AGENT / "data" / "historical" / "games-2025-26.json"
    if not fp.exists():
        return {}, []
    raw = json.loads(fp.read_text())
    games_list = raw.get("games", raw if isinstance(raw, list) else [])
    results = {}
    enriched = []
    for g in games_list:
        game_date = g.get("game_date", "")
        home_full = g.get("home_team", "")
        away_full = g.get("away_team", "")
        home = TEAM_MAP.get(home_full, home_full)
        away = TEAM_MAP.get(away_full, away_full)
        h_data = g.get("home", {})
        a_data = g.get("away", {})
        hs  = h_data.get("pts", h_data.get("PTS", 0))
        as_ = a_data.get("pts", a_data.get("PTS", 0))
        if not hs and not as_:
            continue
        game_entry = {
            "date": game_date, "home": home, "away": away,
            "home_score": hs, "away_score": as_,
            "home_won": hs > as_,
            "home_stats": {k: h_data.get(k, 0) for k in STAT_KEYS},
            "away_stats": {k: a_data.get(k, 0) for k in STAT_KEYS},
        }
        results[(game_date, home, away)] = game_entry
        enriched.append(game_entry)
    enriched.sort(key=lambda g: g["date"])
    return results, enriched


def load_games() -> Dict:
    """Legacy wrapper for backward compatibility."""
    results, _ = load_games_rich()
    return {k: {"home_score": v["home_score"], "away_score": v["away_score"]} for k, v in results.items()}


# ── STANDINGS + ROLLING STATS ────────────────────────────────────────────────

def compute_standings(all_games: List[Dict], up_to_date: str) -> Dict[str, Dict]:
    """Compute cumulative W-L standings for every team up to (not including) a date."""
    standings: Dict[str, Dict] = defaultdict(lambda: {"w": 0, "l": 0, "pts_for": 0, "pts_against": 0})
    for g in all_games:
        if g["date"] >= up_to_date:
            break
        home, away = g["home"], g["away"]
        if g["home_won"]:
            standings[home]["w"] += 1
            standings[away]["l"] += 1
        else:
            standings[away]["w"] += 1
            standings[home]["l"] += 1
        standings[home]["pts_for"] += g["home_score"]
        standings[home]["pts_against"] += g["away_score"]
        standings[away]["pts_for"] += g["away_score"]
        standings[away]["pts_against"] += g["home_score"]

    # Compute GB from leader, win_pct
    if standings:
        best_w = max(s["w"] for s in standings.values())
        best_l = min(s["l"] for s in standings.values() if s["w"] == best_w)
        for team, s in standings.items():
            total = s["w"] + s["l"]
            s["win_pct"] = round(s["w"] / total, 3) if total > 0 else 0.0
            s["gb"] = round(((best_w - s["w"]) + (s["l"] - best_l)) / 2, 1)
            s["ppg"] = round(s["pts_for"] / total, 1) if total > 0 else 0.0
            s["opp_ppg"] = round(s["pts_against"] / total, 1) if total > 0 else 0.0
    return dict(standings)


def compute_team_form(all_games: List[Dict], team: str, up_to_date: str, window: int = 10) -> Dict:
    """Compute rolling stats for a team over last N games before a date."""
    recent = []
    for g in all_games:
        if g["date"] >= up_to_date:
            break
        if g["home"] == team:
            recent.append({"won": g["home_won"], "stats": g["home_stats"], "pts": g["home_score"]})
        elif g["away"] == team:
            recent.append({"won": not g["home_won"], "stats": g["away_stats"], "pts": g["away_score"]})
    last_n = recent[-window:]
    if not last_n:
        return {"games": 0, "w": 0, "l": 0}
    wins = sum(1 for g in last_n if g["won"])
    avg_stats = {}
    for key in STAT_KEYS:
        vals = [g["stats"].get(key, 0) for g in last_n]
        avg_stats[f"avg_{key}"] = round(sum(vals) / len(vals), 3) if vals else 0
    avg_stats["avg_pts"] = round(sum(g["pts"] for g in last_n) / len(last_n), 1)
    return {"games": len(last_n), "w": wins, "l": len(last_n) - wins, **avg_stats}


def compute_all_model_predictions(model_names: list, implied: float, seed_val: str, home_won: bool) -> Dict:
    """Compute predictions from ALL 11 models for a single game."""
    preds = {}
    for m in model_names:
        preds[m] = model_prob(m, implied, seed_val, home_won)
    probs = list(preds.values())
    avg_p = sum(probs) / len(probs)
    std_p = (sum((p - avg_p) ** 2 for p in probs) / len(probs)) ** 0.5
    return {
        "predictions": preds,
        "consensus": round(avg_p, 4),
        "disagreement": round(std_p, 4),
        "best_model": max(preds, key=lambda m: abs(preds[m] - 0.5)),  # most confident
        "outlier": max(preds, key=lambda m: abs(preds[m] - avg_p)),  # furthest from consensus
    }


def build_game_context(game_entry: Dict, odds_entry: Dict, all_games: List[Dict],
                       standings: Dict, model_preds: Dict) -> Dict:
    """Build full context that an agent sees before betting on a game."""
    home, away = game_entry["home"], game_entry["away"]
    home_form = compute_team_form(all_games, home, game_entry["date"])
    away_form = compute_team_form(all_games, away, game_entry["date"])
    home_stand = standings.get(home, {})
    away_stand = standings.get(away, {})
    return {
        "date": game_entry["date"],
        "home": home, "away": away,
        "home_standings": home_stand,
        "away_standings": away_stand,
        "home_form_L10": home_form,
        "away_form_L10": away_form,
        "odds": odds_entry,
        "models": model_preds,
        # Result (hidden during decision, revealed after)
        "_result": {"home_score": game_entry["home_score"], "away_score": game_entry["away_score"],
                     "home_won": game_entry["home_won"]},
    }


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


# ── PER-GAME AGENT DECISION ENGINE (v5) ──────────────────────────────────────

def agent_pick_model_for_game(trader_id: str, game_ctx: Dict) -> str:
    """Agent picks which model to trust for THIS specific game based on full context."""
    cfg = TRADERS[trader_id]
    personality = cfg["personality"]
    preferred = cfg["preferred_models"]
    models_info = game_ctx.get("models", {})
    preds = models_info.get("predictions", {})

    if personality == "analytical":
        # Trust the model with highest edge (furthest from implied, in profit direction)
        implied = 1.0 / game_ctx["odds"]["ml_home_dec"] if game_ctx["odds"].get("ml_home_dec") else 0.5
        return max(preferred, key=lambda m: abs(preds.get(m, 0.5) - implied))

    elif personality == "diversified":
        # Rotate: hash game date+teams to pick
        h = int(hashlib.md5(f"{game_ctx['date']}_{game_ctx['home']}".encode()).hexdigest()[:4], 16)
        return preferred[h % len(preferred)]

    elif personality == "conservative":
        # Closest to consensus (safest)
        consensus = models_info.get("consensus", 0.5)
        return min(preferred, key=lambda m: abs(preds.get(m, 0.5) - consensus))

    elif personality == "aggressive":
        # Most confident model (furthest from 0.5)
        return max(preferred, key=lambda m: abs(preds.get(m, 0.5) - 0.5))

    elif personality == "contrarian":
        # Outlier model — disagrees most with consensus
        consensus = models_info.get("consensus", 0.5)
        return max(preferred, key=lambda m: abs(preds.get(m, 0.5) - consensus))

    return preferred[0]


def agent_pick_strategies_for_game(trader_id: str, game_ctx: Dict,
                                   bankroll: float, others: Dict) -> List[str]:
    """Agent picks which strategies to use for THIS game. Can pick multiple."""
    cfg = TRADERS[trader_id]
    personality = cfg["personality"]
    preferred = [s for s in cfg["preferred_strategies"] if s not in ELIMINATED_STRATEGIES]
    if not preferred:
        preferred = ["half_kelly"]

    # Competitive awareness
    other_bankrolls = [s.get("nba_bankroll", 100.0) for s in others.values() if "nba_bankroll" in s]
    avg_other = sum(other_bankrolls) / len(other_bankrolls) if other_bankrolls else bankroll
    trailing = bankroll < avg_other * 0.9
    leading = bankroll > avg_other * 1.2

    # Game strength signal
    model_disagreement = game_ctx.get("models", {}).get("disagreement", 0.05)
    high_confidence = model_disagreement < 0.03

    if personality == "aggressive":
        # Aggressive: multiple strategies on high-confidence games
        if high_confidence:
            return preferred[:3]  # Use up to 3 strategies
        return [preferred[0]]

    elif personality == "conservative":
        # Conservative: single safest strategy, switch if trailing
        if trailing:
            return ["quarter_kelly"]
        return [preferred[0]]

    elif personality == "analytical":
        # Analytical: use 2 strategies on confident games for diversification
        if high_confidence:
            return preferred[:2]
        return ["half_kelly" if not trailing else "confidence_scaled"]

    elif personality == "contrarian":
        # Contrarian: always underdog strategies
        return ["underdog_specialist", "dog_value_plus"] if not leading else ["value_hunter"]

    elif personality == "diversified":
        # Diversified: rotate through all preferred
        h = int(hashlib.md5(f"{game_ctx['date']}_{game_ctx['home']}".encode()).hexdigest()[:4], 16)
        return [preferred[h % len(preferred)]]

    return [preferred[0]]


def agent_decide_game_bets(trader_id: str, game_ctx: Dict, bankroll: float,
                           day_budget: float, others: Dict, comp_state: Dict) -> List[Dict]:
    """
    v5 CORE: Agent decides ALL bets for ONE game. Returns list of justified bets.
    Agent sees: standings, team form, all model predictions, odds, other agents.
    Agent chooses: model, strategies, categories — all freely.
    """
    cfg = TRADERS[trader_id]
    odds = game_ctx["odds"]
    result = game_ctx["_result"]
    home_won = result["home_won"]
    hs, as_ = result["home_score"], result["away_score"]
    total_pts = hs + as_
    seed_val = f"{game_ctx['date']}_{game_ctx['home']}_{game_ctx['away']}"

    # Agent picks model for this game
    chosen_model = agent_pick_model_for_game(trader_id, game_ctx)
    implied = 1.0 / odds["ml_home_dec"] if odds.get("ml_home_dec") else 0.5
    prob_home = model_prob(chosen_model, implied, seed_val, home_won)
    prob_away = 1.0 - prob_home

    # H1 simulation
    h1_won = h1_result_from_hash(seed_val, home_won)
    h1_prob_home = model_prob(chosen_model, implied, f"h1_{seed_val}", h1_won)
    h1_prob_away = 1.0 - h1_prob_home

    # Agent picks strategies for this game
    chosen_strategies = agent_pick_strategies_for_game(trader_id, game_ctx, bankroll, others)

    # Build all bet candidates (16+ categories)
    candidates = []
    candidates.append(("ml_home", prob_home, odds.get("ml_home_dec", 2.0), home_won))
    candidates.append(("ml_away", prob_away, odds.get("ml_away_dec", 2.0), not home_won))

    if odds.get("spread_home") is not None:
        spread = odds["spread_home"]
        candidates.append(("spread_home", prob_home * 0.9, 1.909, (hs + spread) > as_))
        candidates.append(("spread_away", prob_away * 0.9, 1.909, (as_ - spread) > hs))

    if odds.get("total"):
        line = odds["total"]
        prob_over = 0.48 + (prob_home - 0.5) * 0.1
        prob_under = 1.0 - prob_over
        home_line = line / 2.0
        prob_home_over = 0.48 + (prob_home - 0.5) * 0.15
        candidates.append(("total_over", prob_over, 1.909, total_pts > line))
        candidates.append(("total_under", prob_under, 1.909, total_pts < line))
        candidates.append(("team_total_home_over", prob_home_over, 1.909, hs > home_line))
        candidates.append(("team_total_home_under", 1.0 - prob_home_over, 1.909, hs < home_line))

    candidates.append(("h1_ml_home", h1_prob_home, odds.get("ml_home_dec", 2.0) * 0.95, h1_won))
    candidates.append(("h1_ml_away", h1_prob_away, odds.get("ml_away_dec", 2.0) * 0.95, not h1_won))
    candidates.append(("alt_spread_home_big", prob_home * 0.7, 2.5, (hs - as_) > 8))
    candidates.append(("alt_spread_away_big", prob_away * 0.7, 2.5, (as_ - hs) > 8))

    # Model consensus info for justification
    models_info = game_ctx.get("models", {})
    consensus = models_info.get("consensus", 0.5)
    disagreement = models_info.get("disagreement", 0.05)

    # Standings info for justification
    h_stand = game_ctx.get("home_standings", {})
    a_stand = game_ctx.get("away_standings", {})
    h_form = game_ctx.get("home_form_L10", {})
    a_form = game_ctx.get("away_form_L10", {})

    bets = []
    remaining_budget = day_budget

    for strat_name in chosen_strategies:
        if strat_name in ELIMINATED_STRATEGIES or strat_name not in STRATEGIES:
            continue
        strat_cfg = STRATEGIES[strat_name]
        allowed_cats = strat_cfg["cats"]

        for cat, prob, odds_val, outcome in candidates:
            if allowed_cats != "all" and cat not in allowed_cats:
                continue
            if remaining_budget <= 0:
                break

            bet_size = get_bet_size(strat_name, prob, odds_val, remaining_budget, comp_state)
            if bet_size <= 0:
                continue
            bet_size = min(bet_size, remaining_budget)

            edge = prob * (odds_val - 1.0) - (1.0 - prob)
            profit = bet_size * (odds_val - 1.0) if outcome else -bet_size

            # Build justification
            reasoning_parts = []
            reasoning_parts.append(f"{chosen_model} P({game_ctx['home']}): {prob_home:.3f}")
            reasoning_parts.append(f"consensus: {consensus:.3f} (disagree: {disagreement:.3f})")
            if h_stand:
                reasoning_parts.append(f"{game_ctx['home']} {h_stand.get('w',0)}-{h_stand.get('l',0)}")
            if a_stand:
                reasoning_parts.append(f"{game_ctx['away']} {a_stand.get('w',0)}-{a_stand.get('l',0)}")
            if h_form.get("games"):
                reasoning_parts.append(f"{game_ctx['home']} L{h_form['games']}: {h_form['w']}-{h_form['l']}")
            if a_form.get("games"):
                reasoning_parts.append(f"{game_ctx['away']} L{a_form['games']}: {a_form['w']}-{a_form['l']}")

            bet_record = {
                "date": game_ctx["date"],
                "game": f"{game_ctx['home']} vs {game_ctx['away']}",
                "category": cat,
                "model_used": chosen_model,
                "strategy_used": strat_name,
                "model_prob": round(prob, 4),
                "implied_prob": round(1.0 / odds_val if odds_val > 0 else 0.5, 4),
                "edge_pct": round(edge * 100, 2),
                "bet_size": round(bet_size, 4),
                "odds": round(odds_val, 4),
                "reasoning": " | ".join(reasoning_parts),
                "standings_context": f"{game_ctx['home']} ({h_stand.get('w',0)}-{h_stand.get('l',0)}) vs {game_ctx['away']} ({a_stand.get('w',0)}-{a_stand.get('l',0)})",
                "outcome": "Win" if outcome else "Loss",
                "profit": round(profit, 4),
            }
            bets.append(bet_record)
            remaining_budget -= bet_size

    return bets


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


# ── NBA FULL-SEASON BACKTEST PER AGENT (v5) ─────────────────────────────────

def run_nba_backtest_for_agent(trader_id: str, matched: List,
                               others_states: Dict,
                               all_games: Optional[List[Dict]] = None) -> Dict:
    """
    v5: Full-season backtest. Agent gets ALL context per game, bets freely
    across 16+ categories, provides justification for every bet.
    """
    bankroll   = TRADERS[trader_id]["bankroll_nba"]
    comp_state = {"last_won": False, "win_streak": 0, "peak": bankroll}
    total_bets = wins = losses = pushes = 0
    total_wagered = total_profit = 0.0
    peak_bankroll = bankroll
    max_drawdown  = 0.0
    all_bets: List[Dict] = []  # Full justified bet history
    eliminated_day = None
    day_results    = []

    # Group by day
    days = defaultdict(list)
    for item in matched:
        key, game_entry, odd = item
        days[key[0]].append((key, game_entry, odd))
    sorted_days = sorted(days.keys())

    # Pre-compute standings per day (done once for performance)
    if all_games is None:
        all_games = []

    for day_num, day_date in enumerate(sorted_days, 1):
        if bankroll <= 0:
            if eliminated_day is None:
                eliminated_day = day_num
            break

        day_games = days[day_date]
        standings = compute_standings(all_games, day_date) if all_games else {}

        # Budget for the day = full bankroll (agents deploy 100%)
        day_budget = bankroll
        day_bets_count = 0
        day_profit = 0.0
        day_models_used = set()
        day_strategies_used = set()

        for key, game_entry, odd in day_games:
            if bankroll <= 0:
                break

            # Compute all 11 model predictions for this game
            home_won = game_entry["home_score"] > game_entry["away_score"]
            implied = 1.0 / odd["ml_home_dec"] if odd.get("ml_home_dec") else 0.5
            seed_val = f"{key[0]}_{key[1]}_{key[2]}"
            model_preds = compute_all_model_predictions(list(MODELS.keys()), implied, seed_val, home_won)

            # Build full game context
            game_ctx = build_game_context(
                {"date": key[0], "home": key[1], "away": key[2],
                 "home_score": game_entry["home_score"], "away_score": game_entry["away_score"],
                 "home_won": home_won,
                 "home_stats": game_entry.get("home_stats", {}),
                 "away_stats": game_entry.get("away_stats", {})},
                odd, all_games, standings, model_preds
            )

            # Agent decides all bets for this game
            # Budget per game: split remaining budget across remaining games
            games_remaining = max(1, len(day_games) - day_games.index((key, game_entry, odd)))
            game_budget = bankroll / games_remaining  # Even split of current bankroll
            if TRADERS[trader_id]["personality"] == "aggressive":
                game_budget = bankroll * 0.5  # Aggressive: bet big on each game
            elif TRADERS[trader_id]["personality"] == "conservative":
                game_budget = bankroll * 0.15  # Conservative: small per game

            game_bets = agent_decide_game_bets(
                trader_id, game_ctx, bankroll, game_budget, others_states, comp_state
            )

            for bet in game_bets:
                total_bets += 1
                day_bets_count += 1
                bet_size = bet["bet_size"]
                profit = bet["profit"]
                total_wagered += bet_size

                if bet["outcome"] == "Win":
                    wins += 1
                    comp_state["last_won"] = True
                    comp_state["win_streak"] = comp_state.get("win_streak", 0) + 1
                else:
                    losses += 1
                    comp_state["last_won"] = False
                    comp_state["win_streak"] = 0

                bankroll += profit
                day_profit += profit
                total_profit += profit

                if bankroll > peak_bankroll:
                    peak_bankroll = bankroll
                    comp_state["peak"] = bankroll
                dd = 1.0 - bankroll / peak_bankroll if peak_bankroll > 0 else 0.0
                if dd > max_drawdown:
                    max_drawdown = dd

                bet["bankroll_after"] = round(bankroll, 4)
                all_bets.append(bet)
                day_models_used.add(bet.get("model_used", ""))
                day_strategies_used.add(bet.get("strategy_used", ""))

                if bankroll <= 0:
                    eliminated_day = day_num
                    break

        day_results.append({
            "day":        day_num,
            "date":       day_date,
            "models":     list(day_models_used),
            "strategies": list(day_strategies_used),
            "bets":       day_bets_count,
            "profit":     round(day_profit, 4),
            "bankroll":   round(bankroll, 4),
            "games":      len(day_games),
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
        "nba_bets_history":    all_bets[-500:],  # Keep more with justifications
        "nba_all_bets":        all_bets,  # Full season for doc generation
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
    # Iteration / generation tracking
    it_data = _load_iteration()
    it_data["iteration"] += 1
    print(f"Trading Floor v8 — iteration {it_data['iteration']}")
    print("Loading games (with team stats)...")
    games, all_games_sorted = load_games_rich()
    odds = load_odds()
    print(f"  Games with results : {len(games)}")
    print(f"  Games with stats   : {len(all_games_sorted)}")
    print(f"  Games with odds    : {len(odds)}")

    matched = []
    for key in sorted(odds.keys()):
        if key in games:
            matched.append((key, games[key], odds[key]))
    print(f"  Matched            : {len(matched)}")
    if not matched:
        print("  WARNING: No matched games — NBA backtest will be empty.")
    # Generation = unique game-days seen so far (cumulative across runs)
    unique_days = len({item[0][0] for item in matched})
    it_data["generation"] = it_data.get("generation", 0) + unique_days

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

        nba_result = run_nba_backtest_for_agent(trader_id, matched, others, all_games_sorted)
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

    # Generate per-agent season documents
    print("\nGenerating season documents...")
    generate_all_season_docs(all_results, board)

    # Persist updated iteration counters
    _save_iteration(it_data)

    # Build eliminations summary
    eliminations = {
        "strategies":       ELIMINATED_STRATEGIES,
        "political":        ELIMINATED_POLITICAL_STRATEGIES,
        "coffins": [
            {"name": k, **v, "type": "nba_strategy"}
            for k, v in ELIMINATED_STRATEGIES.items()
        ] + [
            {"name": k, **v, "type": "political_strategy"}
            for k, v in ELIMINATED_POLITICAL_STRATEGIES.items()
        ],
        "active_nba_count":           len(STRATEGIES),
        "eliminated_nba_count":       len(ELIMINATED_STRATEGIES),
        "active_political_count":     len(set(t["pol_approach"] for t in TRADERS.values())),
        "eliminated_political_count": len(ELIMINATED_POLITICAL_STRATEGIES),
    }

    output = {
        "iteration":  it_data["iteration"],
        "generation": it_data["generation"],
        "meta": {
            "version":            "trading-floor-v8",
            "generated":          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date":               date.today().isoformat(),
            "traders":            len(TRADERS),
            "nba_models":         len(MODELS),
            "nba_strategies":     len(STRATEGIES),
            "nba_strategies_eliminated": len(ELIMINATED_STRATEGIES),
            "matched_games":      len(matched),
            "political_tickers":  len(signals),
            "etf_universe":       len(ETF_UNIVERSE),
        },
        "eliminations": eliminations,
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
    print(f"Iteration: {it_data['iteration']}  Generation: {it_data['generation']}")
    print(f"Active NBA strategies: {len(STRATEGIES)}  Eliminated: {len(ELIMINATED_STRATEGIES)}")

    return output


# ── PER-AGENT SEASON DOCUMENT GENERATOR ──────────────────────────────────────

def generate_agent_season_doc(trader_id: str, state: Dict, board: List[Dict]) -> str:
    """Generate a full markdown season document for one agent."""
    cfg = TRADERS[trader_id]
    all_bets = state.get("nba_all_bets", [])
    day_results = state.get("nba_day_results", [])
    rank_entry = next((e for e in board if e["trader_id"] == trader_id), {})

    lines = []
    lines.append(f"# 2025-26 NBA Season — Agent {cfg['name'].upper()}")
    lines.append(f"")
    lines.append(f"## Executive Summary")
    lines.append(f"- **Provider:** {cfg['provider']}")
    lines.append(f"- **Personality:** {cfg['personality']}")
    lines.append(f"- **Risk Tolerance:** {cfg['risk_tolerance']}")
    lines.append(f"- **Initial Bankroll:** $100.00")
    lines.append(f"- **Final Bankroll:** ${state.get('nba_bankroll', 0):,.2f}")
    lines.append(f"- **ROI:** {state.get('nba_roi_pct', 0):+,.1f}%")
    lines.append(f"- **Sharpe Ratio:** {state.get('nba_sharpe', 0):.3f}")
    lines.append(f"- **Record:** {state.get('nba_wins', 0)}W-{state.get('nba_losses', 0)}L")
    lines.append(f"- **Peak Bankroll:** ${state.get('nba_peak', 0):,.2f}")
    lines.append(f"- **Max Drawdown:** {state.get('nba_max_drawdown', 0)*100:.1f}%")
    lines.append(f"- **Rank:** #{rank_entry.get('rank', '?')} of {len(board)}")
    if state.get('nba_eliminated_day'):
        lines.append(f"- **ELIMINATED:** Day {state['nba_eliminated_day']}")
    lines.append(f"- **Total Wagered:** ${state.get('nba_wagered', 0):,.2f}")
    lines.append(f"")

    # Peer comparison
    lines.append(f"## Peer Comparison")
    lines.append(f"| Rank | Agent | Bankroll | ROI | Sharpe |")
    lines.append(f"|------|-------|----------|-----|--------|")
    for entry in board:
        marker = " **" if entry["trader_id"] == trader_id else ""
        lines.append(
            f"| {entry['rank']} | {entry['name']}{marker} | "
            f"${entry['nba_bankroll']:,.2f} | {entry['nba_roi_pct']:+,.1f}% | "
            f"{entry.get('nba_sharpe', 0):.3f} |"
        )
    lines.append(f"")

    # Model usage breakdown
    model_usage = defaultdict(lambda: {"count": 0, "profit": 0.0})
    for bet in all_bets:
        m = bet.get("model_used", "unknown")
        model_usage[m]["count"] += 1
        model_usage[m]["profit"] += bet.get("profit", 0)

    lines.append(f"## Model Performance")
    lines.append(f"| Model | Bets | Profit |")
    lines.append(f"|-------|------|--------|")
    for m, stats in sorted(model_usage.items(), key=lambda x: -x[1]["profit"]):
        lines.append(f"| {m} | {stats['count']} | ${stats['profit']:+,.2f} |")
    lines.append(f"")

    # Strategy usage breakdown
    strat_usage = defaultdict(lambda: {"count": 0, "profit": 0.0})
    for bet in all_bets:
        s = bet.get("strategy_used", "unknown")
        strat_usage[s]["count"] += 1
        strat_usage[s]["profit"] += bet.get("profit", 0)

    lines.append(f"## Strategy Performance")
    lines.append(f"| Strategy | Bets | Profit |")
    lines.append(f"|----------|------|--------|")
    for s, stats in sorted(strat_usage.items(), key=lambda x: -x[1]["profit"]):
        lines.append(f"| {s} | {stats['count']} | ${stats['profit']:+,.2f} |")
    lines.append(f"")

    # Category breakdown
    cat_usage = defaultdict(lambda: {"count": 0, "wins": 0, "profit": 0.0})
    for bet in all_bets:
        c = bet.get("category", "unknown")
        cat_usage[c]["count"] += 1
        cat_usage[c]["profit"] += bet.get("profit", 0)
        if bet.get("outcome") == "Win":
            cat_usage[c]["wins"] += 1

    lines.append(f"## Category Breakdown")
    lines.append(f"| Category | Bets | WR% | Profit |")
    lines.append(f"|----------|------|-----|--------|")
    for c, stats in sorted(cat_usage.items(), key=lambda x: -x[1]["profit"]):
        wr = round(stats["wins"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0
        lines.append(f"| {c} | {stats['count']} | {wr}% | ${stats['profit']:+,.2f} |")
    lines.append(f"")

    # Day-by-day results
    lines.append(f"## Day-by-Day Results")
    lines.append(f"| Day | Date | Games | Bets | P&L | Bankroll | Models | Strategies |")
    lines.append(f"|-----|------|-------|------|-----|----------|--------|------------|")
    for d in day_results:
        models_str = ",".join(d.get("models", []))[:20]
        strats_str = ",".join(d.get("strategies", []))[:25]
        lines.append(
            f"| {d['day']} | {d['date']} | {d.get('games', '?')} | {d['bets']} | "
            f"${d['profit']:+,.2f} | ${d['bankroll']:,.2f} | {models_str} | {strats_str} |"
        )
    lines.append(f"")

    # Sample bets with justification (first 50 + last 50)
    lines.append(f"## Bet Log (sample: first 50 + last 50 of {len(all_bets)} total)")
    lines.append(f"")
    sample_bets = all_bets[:50] + (all_bets[-50:] if len(all_bets) > 100 else [])
    for i, bet in enumerate(sample_bets):
        if i == 50 and len(all_bets) > 100:
            lines.append(f"")
            lines.append(f"*... ({len(all_bets) - 100} bets omitted) ...*")
            lines.append(f"")
        lines.append(f"### {bet.get('date', '?')} | {bet.get('game', '?')} | {bet.get('category', '?')}")
        lines.append(f"- **Model:** {bet.get('model_used', '?')} | **Strategy:** {bet.get('strategy_used', '?')}")
        lines.append(f"- **Prob:** {bet.get('model_prob', 0):.3f} vs implied {bet.get('implied_prob', 0):.3f} | **Edge:** {bet.get('edge_pct', 0):+.1f}%")
        lines.append(f"- **Bet:** ${bet.get('bet_size', 0):,.2f} @ {bet.get('odds', 0):.3f} | **{bet.get('outcome', '?')}** → ${bet.get('profit', 0):+,.2f}")
        lines.append(f"- **Context:** {bet.get('standings_context', '')}")
        lines.append(f"- **Reasoning:** {bet.get('reasoning', '')}")
        lines.append(f"- **Bankroll after:** ${bet.get('bankroll_after', 0):,.2f}")
        lines.append(f"")

    return "\n".join(lines)


def generate_all_season_docs(all_results: Dict, board: List[Dict]) -> None:
    """Generate season doc for all 5 agents."""
    docs_dir = DATA_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for tid, state in all_results.items():
        doc = generate_agent_season_doc(tid, state, board)
        doc_path = docs_dir / f"{tid}-season-2025-26.md"
        doc_path.write_text(doc)
        print(f"  Season doc: {doc_path} ({len(doc)} chars)")


# ── KARPATHY LOOP: ANALYZE + AUTO-EVOLVE ─────────────────────────────────────

ELIMINATION_ROI_THRESHOLD = -50.0   # Strategies below this ROI% get coffin'd
ELIMINATION_MIN_BETS      = 20      # Need at least this many bets to judge
KARPATHY_OUTPUT_FILE      = DATA_DIR / 'trading-floor-karpathy-output.json'

def _analyze_strategy_performance(result: Dict) -> Dict[str, Dict]:
    """Extract per-strategy performance from all traders' bet-level data (v5)."""
    strat_stats: Dict[str, Dict] = defaultdict(lambda: {
        "bets": 0, "wins": 0, "losses": 0, "profit": 0.0,
        "traders_using": set(),
    })

    for tid in TRADERS:
        sf = TRADERS_DIR / f"{tid}-state.json"
        if not sf.exists():
            continue
        try:
            full_state = json.loads(sf.read_text())
        except Exception:
            continue

        # v5: read from individual bets which have strategy_used
        for bet in full_state.get("nba_bets_history", []):
            strat = bet.get("strategy_used", "unknown")
            strat_stats[strat]["bets"] += 1
            strat_stats[strat]["profit"] += bet.get("profit", 0.0)
            strat_stats[strat]["traders_using"].add(tid)
            if bet.get("profit", 0.0) > 0:
                strat_stats[strat]["wins"] += 1
            else:
                strat_stats[strat]["losses"] += 1

    for strat, stats in strat_stats.items():
        stats["traders_using"] = list(stats["traders_using"])
        initial = 100.0 * len(stats["traders_using"]) if stats["traders_using"] else 100.0
        stats["roi_pct"] = round(stats["profit"] / initial * 100, 2) if initial > 0 else 0.0
        total = stats["wins"] + stats["losses"]
        stats["win_rate_pct"] = round(stats["wins"] / total * 100, 1) if total > 0 else 0.0

    return dict(strat_stats)


def _analyze_model_performance(result: Dict) -> Dict[str, Dict]:
    """Extract per-model performance from all traders' bet-level data (v5)."""
    model_stats: Dict[str, Dict] = defaultdict(lambda: {
        "bets": 0, "total_profit": 0.0, "wins": 0, "losses": 0,
        "traders_using": set(),
    })

    for tid in TRADERS:
        sf = TRADERS_DIR / f"{tid}-state.json"
        if not sf.exists():
            continue
        try:
            full_state = json.loads(sf.read_text())
        except Exception:
            continue

        for bet in full_state.get("nba_bets_history", []):
            model = bet.get("model_used", "unknown")
            model_stats[model]["bets"] += 1
            model_stats[model]["total_profit"] += bet.get("profit", 0.0)
            model_stats[model]["traders_using"].add(tid)
            if bet.get("profit", 0.0) > 0:
                model_stats[model]["wins"] += 1
            else:
                model_stats[model]["losses"] += 1

    for model, stats in model_stats.items():
        stats["traders_using"] = list(stats["traders_using"])
        stats["avg_daily_pnl"] = round(
            stats["total_profit"] / max(stats["bets"], 1), 4
        )
        total = stats["wins"] + stats["losses"]
        stats["win_rate_pct"] = round(stats["wins"] / total * 100, 1) if total > 0 else 0.0

    return dict(model_stats)


def _analyze_category_performance(result: Dict) -> Dict[str, Dict]:
    """Extract per-bet-category performance from all traders' bet histories (v5)."""
    cat_stats: Dict[str, Dict] = defaultdict(lambda: {
        "bets": 0, "profit": 0.0, "wins": 0, "losses": 0,
    })

    for tid in TRADERS:
        sf = TRADERS_DIR / f"{tid}-state.json"
        if not sf.exists():
            continue
        try:
            full_state = json.loads(sf.read_text())
        except Exception:
            continue

        for bet in full_state.get("nba_bets_history", []):
            cat = bet.get("category", bet.get("cat", "unknown"))
            cat_stats[cat]["bets"] += 1
            cat_stats[cat]["profit"] += bet.get("profit", 0.0)
            if bet.get("profit", 0.0) > 0:
                cat_stats[cat]["wins"] += 1
            else:
                cat_stats[cat]["losses"] += 1

    for cat, stats in cat_stats.items():
        total = stats["wins"] + stats["losses"]
        stats["win_rate_pct"] = round(stats["wins"] / total * 100, 1) if total > 0 else 0.0
        stats["roi_pct"] = round(stats["profit"] / max(stats["bets"], 1) * 100, 2)

    return dict(cat_stats)


def _auto_eliminate_strategies(strat_perf: Dict[str, Dict]) -> List[Dict]:
    """Auto-eliminate strategies with ROI below threshold. Returns new coffins."""
    new_coffins = []
    for strat, stats in strat_perf.items():
        if strat in ELIMINATED_STRATEGIES:
            continue  # Already dead
        if strat not in STRATEGIES:
            continue  # Unknown strategy
        if stats["bets"] < ELIMINATION_MIN_BETS:
            continue  # Not enough data to judge
        if stats["roi_pct"] < ELIMINATION_ROI_THRESHOLD:
            coffin = {
                "strategy": strat,
                "eliminated_at": date.today().isoformat(),
                "reason": f"Auto-eliminated: {stats['roi_pct']:.0f}% ROI ({stats['bets']} bets)",
                "final_roi": round(stats["roi_pct"] / 100, 2),
                "bets": stats["bets"],
                "department": "D4_BETTING",
            }
            new_coffins.append(coffin)
            # Add to live eliminated dict so next iteration skips them
            ELIMINATED_STRATEGIES[strat] = coffin
            print(f"  [COFFIN] Strategy '{strat}' eliminated: {stats['roi_pct']:.1f}% ROI")
    return new_coffins


def _mutate_agent_preferences(result: Dict) -> Dict[str, Dict]:
    """
    Karpathy-style mutation: losing agents adopt winning agents' strategies.
    Returns mutation log per trader.
    """
    board = result.get("leaderboard", [])
    if len(board) < 2:
        return {}

    # Find winner and loser
    winner = board[0]
    loser  = board[-1]
    winner_id = winner["trader_id"]
    loser_id  = loser["trader_id"]

    mutations = {}

    # Read winner's actual bets to find their most-used strategy (v5: from bets)
    winner_sf = TRADERS_DIR / f"{winner_id}-state.json"
    if winner_sf.exists():
        try:
            ws = json.loads(winner_sf.read_text())
            strat_usage = defaultdict(int)
            for b in ws.get("nba_bets_history", []):
                strat_usage[b.get("strategy_used", "")] += 1
            if strat_usage:
                best_strat = max(strat_usage, key=strat_usage.get)
                # Only mutate if the winner's strategy isn't already in loser's preferences
                loser_cfg = TRADERS[loser_id]
                if best_strat not in loser_cfg["preferred_strategies"] and best_strat in STRATEGIES:
                    # Add winner's best strategy to loser's preferences (at position 0)
                    old_prefs = list(loser_cfg["preferred_strategies"])
                    loser_cfg["preferred_strategies"] = [best_strat] + old_prefs[:2]
                    mutations[loser_id] = {
                        "type": "adopt_winner_strategy",
                        "from_trader": winner_id,
                        "adopted_strategy": best_strat,
                        "old_preferences": old_prefs,
                        "new_preferences": loser_cfg["preferred_strategies"],
                        "reason": f"{loser_id} (rank {loser['rank']}, ROI {loser['nba_roi_pct']:+.1f}%) "
                                  f"adopts '{best_strat}' from {winner_id} (rank 1, ROI {winner['nba_roi_pct']:+.1f}%)",
                    }
                    print(f"  [MUTATE] {loser_id} adopts '{best_strat}' from {winner_id}")
        except Exception:
            pass

    # Also: if middle agents are stagnant (ROI near 0), try shifting their model preference
    for entry in board[1:-1]:
        tid = entry["trader_id"]
        if abs(entry["nba_roi_pct"]) < 2.0:  # Near-zero ROI = stagnant
            winner_models = TRADERS[winner_id]["preferred_models"]
            current_models = TRADERS[tid]["preferred_models"]
            # Add winner's top model if not already present
            if winner_models and winner_models[0] not in current_models:
                old_models = list(current_models)
                TRADERS[tid]["preferred_models"] = [winner_models[0]] + current_models[:2]
                mutations[tid] = {
                    "type": "adopt_winner_model",
                    "from_trader": winner_id,
                    "adopted_model": winner_models[0],
                    "old_models": old_models,
                    "new_models": TRADERS[tid]["preferred_models"],
                    "reason": f"{tid} stagnant (ROI {entry['nba_roi_pct']:+.1f}%) — adopts model '{winner_models[0]}' from {winner_id}",
                }
                print(f"  [MUTATE] {tid} adopts model '{winner_models[0]}' from {winner_id}")

    return mutations


def run_karpathy_loop() -> Dict:
    """
    Karpathy-style continuous loop:
    1. Run full-season backtest
    2. Analyze strategy/model/category performance
    3. Auto-eliminate losing strategies (coffin them)
    4. Mutate agent preferences (losers adopt winners' approaches)
    5. Write karpathy-output.json for Guardian consumption
    """
    print("=" * 60)
    print("TRADING FLOOR v8 — KARPATHY LOOP")
    print("=" * 60)

    # Step 1: Run full competition
    result = run_full_competition()

    # Step 2: Analyze
    print("\n--- KARPATHY ANALYSIS ---")
    strat_perf = _analyze_strategy_performance(result)
    model_perf = _analyze_model_performance(result)
    cat_perf   = _analyze_category_performance(result)

    # Rank strategies by ROI
    strat_ranked = sorted(
        [(s, p) for s, p in strat_perf.items() if p["bets"] >= 5],
        key=lambda x: x[1]["roi_pct"], reverse=True
    )
    print(f"\nTop strategies:")
    for s, p in strat_ranked[:5]:
        print(f"  {s:25s}: ROI {p['roi_pct']:+8.1f}%  ({p['bets']} bets)")
    print(f"Bottom strategies:")
    for s, p in strat_ranked[-3:]:
        print(f"  {s:25s}: ROI {p['roi_pct']:+8.1f}%  ({p['bets']} bets)")

    # Rank models by avg daily profit
    model_ranked = sorted(
        model_perf.items(),
        key=lambda x: x[1]["avg_daily_pnl"], reverse=True
    )
    print(f"\nModel rankings:")
    for m, p in model_ranked:
        print(f"  {m:25s}: avg_daily_pnl {p['avg_daily_pnl']:+.4f}  ({p['bets']} bets)")

    # Best bet categories
    cat_ranked = sorted(
        [(c, p) for c, p in cat_perf.items() if p["bets"] >= 10],
        key=lambda x: x[1]["win_rate_pct"], reverse=True
    )
    print(f"\nBest bet categories:")
    for c, p in cat_ranked[:5]:
        print(f"  {c:25s}: WR {p['win_rate_pct']:.1f}%  ROI {p['roi_pct']:+.1f}%  ({p['bets']} bets)")

    # Step 3: Auto-eliminate
    print("\n--- AUTO-ELIMINATION ---")
    new_coffins = _auto_eliminate_strategies(strat_perf)
    if not new_coffins:
        print("  No new eliminations this iteration.")

    # Step 4: Mutate agent preferences
    print("\n--- AGENT MUTATIONS ---")
    mutations = _mutate_agent_preferences(result)
    if not mutations:
        print("  No mutations this iteration.")

    # Step 5: Determine best overall findings
    best_strategy = strat_ranked[0] if strat_ranked else ("none", {"roi_pct": 0})
    best_model = model_ranked[0] if model_ranked else ("none", {"avg_daily_pnl": 0})
    best_category = cat_ranked[0] if cat_ranked else ("none", {"win_rate_pct": 0})

    # Step 5b: $1M FITNESS TRACKING
    print(f"\n--- $1M OPTIMIZATION (target: ${OPTIMIZATION_TARGET:,.0f}) ---")
    best_config = _load_best_config()
    board = result.get("leaderboard", [])
    current_best_bankroll = max((e.get("nba_bankroll", 0) for e in board), default=100.0)
    current_best_trader = max(board, key=lambda e: e.get("nba_bankroll", 0))["trader_id"] if board else None
    distance_pct = round((1.0 - current_best_bankroll / OPTIMIZATION_TARGET) * 100, 4)

    improved = current_best_bankroll > best_config["best_bankroll"]
    if improved:
        print(f"  NEW RECORD: ${current_best_bankroll:,.2f} by {current_best_trader} (was ${best_config['best_bankroll']:,.2f})")
        # Snapshot winning agent's config
        if current_best_trader:
            winning_cfg = TRADERS.get(current_best_trader, {})
            best_config["agent_configs"][current_best_trader] = {
                "preferred_strategies": winning_cfg.get("preferred_strategies", []),
                "preferred_models": winning_cfg.get("preferred_models", []),
                "personality": winning_cfg.get("personality", ""),
                "risk_tolerance": winning_cfg.get("risk_tolerance", 0.5),
                "bankroll_achieved": round(current_best_bankroll, 2),
            }
        best_config["best_bankroll"] = round(current_best_bankroll, 2)
        best_config["best_trader_id"] = current_best_trader
        best_config["best_iteration"] = result.get("iteration", 0)
        best_config["distance_to_1M_pct"] = distance_pct
        best_config["history"].append({
            "iteration": result.get("iteration", 0),
            "bankroll": round(current_best_bankroll, 2),
            "trader": current_best_trader,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep last 100 history entries
        best_config["history"] = best_config["history"][-100:]
        _save_best_config(best_config)
    else:
        print(f"  Current best: ${current_best_bankroll:,.2f} (record: ${best_config['best_bankroll']:,.2f} by {best_config['best_trader_id']})")

    print(f"  Distance to $1M: {distance_pct:.2f}%")
    print(f"  Multiplier needed: {OPTIMIZATION_TARGET / max(current_best_bankroll, 1):.1f}x")

    # Step 6: Write Karpathy output for Guardian
    karpathy_output = {
        "department": "trading_floor",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": result.get("iteration", 0),
        "generation": result.get("generation", 0),
        "status": "completed",

        # Key findings (Guardian reads these)
        "best_strategy": {
            "name": best_strategy[0],
            "roi_pct": best_strategy[1]["roi_pct"],
            "bets": best_strategy[1].get("bets", 0),
        },
        "best_model": {
            "name": best_model[0],
            "avg_daily_pnl": best_model[1]["avg_daily_pnl"],
            "bets": best_model[1].get("bets", 0),
        },
        "best_category": {
            "name": best_category[0],
            "win_rate_pct": best_category[1]["win_rate_pct"],
            "bets": best_category[1].get("bets", 0),
        },

        # Full rankings
        "strategy_rankings": [
            {"strategy": s, **{k: v for k, v in p.items()}}
            for s, p in strat_ranked
        ],
        "model_rankings": [
            {"model": m, **{k: v for k, v in p.items()}}
            for m, p in model_ranked
        ],
        "category_rankings": [
            {"category": c, **{k: v for k, v in p.items()}}
            for c, p in cat_ranked
        ],

        # Evolution actions taken
        "new_eliminations": new_coffins,
        "all_eliminations": {
            "nba": ELIMINATED_STRATEGIES,
            "political": ELIMINATED_POLITICAL_STRATEGIES,
        },
        "mutations": mutations,

        # $1M optimization
        "optimization": {
            "target": OPTIMIZATION_TARGET,
            "current_best": round(current_best_bankroll, 2),
            "record_best": round(best_config["best_bankroll"], 2),
            "record_trader": best_config.get("best_trader_id"),
            "distance_to_1M_pct": distance_pct,
            "multiplier_needed": round(OPTIMIZATION_TARGET / max(current_best_bankroll, 1), 1),
            "improved_this_iteration": improved,
        },

        # Leaderboard summary
        "leaderboard": result.get("leaderboard", []),
        "matched_games": result.get("meta", {}).get("matched_games", 0),

        # Recommendations for other departments
        "recommendations": [],
    }

    # Generate cross-department recommendations
    recs = karpathy_output["recommendations"]

    if best_strategy[1]["roi_pct"] > 10:
        recs.append({
            "target_dept": "betting",
            "type": "promote_strategy",
            "strategy": best_strategy[0],
            "roi_pct": best_strategy[1]["roi_pct"],
            "reason": f"Top strategy '{best_strategy[0]}' with {best_strategy[1]['roi_pct']:+.1f}% ROI — promote to live betting",
        })

    if best_model[1]["avg_daily_pnl"] > 0.5:
        recs.append({
            "target_dept": "evolution",
            "type": "promote_model",
            "model": best_model[0],
            "avg_daily_pnl": best_model[1]["avg_daily_pnl"],
            "reason": f"Model '{best_model[0]}' has avg daily pnl {best_model[1]['avg_daily_pnl']:+.4f} — prioritize in evolution",
        })

    if new_coffins:
        recs.append({
            "target_dept": "betting",
            "type": "strategy_eliminated",
            "strategies": [c["strategy"] for c in new_coffins],
            "reason": f"{len(new_coffins)} strategies auto-eliminated — update live betting agent",
        })

    # Write output
    KARPATHY_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    KARPATHY_OUTPUT_FILE.write_text(json.dumps(karpathy_output, indent=2))
    print(f"\nKarpathy output: {KARPATHY_OUTPUT_FILE}")

    # Also write to department directory for Guardian
    dept_output = DATA_DIR.parent / 'departments' / 'trading_floor'
    dept_output.mkdir(parents=True, exist_ok=True)
    (dept_output / 'karpathy-output.json').write_text(json.dumps(karpathy_output, indent=2))
    print(f"Guardian feed:   {dept_output / 'karpathy-output.json'}")

    print(f"\nKarpathy loop complete — iteration {result.get('iteration', '?')}")
    print(f"Best strategy: {best_strategy[0]} ({best_strategy[1]['roi_pct']:+.1f}% ROI)")
    print(f"Best model:    {best_model[0]} ({best_model[1]['avg_daily_pnl']:+.4f}/bet)")
    print(f"Best category: {best_category[0]} ({best_category[1]['win_rate_pct']:.1f}% WR)")
    print(f"Eliminations:  {len(ELIMINATED_STRATEGIES)} NBA + {len(ELIMINATED_POLITICAL_STRATEGIES)} political")
    print(f"Mutations:     {len(mutations)} agents mutated")

    return karpathy_output


# ── CROSS-REPO INTEGRATION ────────────────────────────────────────────────────

SATELLITE_REPOS = {
    "nomos-nba-agent":       Path("/home/termius/nomos-nba-agent"),
    "nomos-political-alpha": Path("/home/termius/nomos-political-alpha"),
    "rgwa":                  Path("/home/termius/rgwa"),
}

def sync_satellite_repos() -> Dict[str, str]:
    """Pull latest from all satellite repos. Returns status per repo."""
    statuses = {}
    for name, path in SATELLITE_REPOS.items():
        if not path.exists():
            statuses[name] = "missing"
            continue
        try:
            subprocess.run(
                ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                cwd=str(path), capture_output=True, timeout=30,
            )
            statuses[name] = "synced"
        except Exception as e:
            statuses[name] = f"error: {e}"
    return statuses


def load_cross_repo_karpathy() -> Dict[str, Dict]:
    """Read karpathy-output.json from each satellite repo's departments."""
    outputs = {}
    karpathy_paths = [
        ("nba_prediction", SATELLITE_REPOS["nomos-nba-agent"] / "data" / "departments" / "prediction" / "karpathy-output.json"),
        ("political_signals", SATELLITE_REPOS["nomos-political-alpha"] / "data" / "departments" / "signals" / "karpathy-output.json"),
        ("creative", SATELLITE_REPOS["rgwa"] / "data" / "departments" / "creative" / "karpathy-output.json"),
    ]
    for name, path in karpathy_paths:
        if path.exists():
            try:
                outputs[name] = json.loads(path.read_text())
            except Exception:
                outputs[name] = {"status": "parse_error", "path": str(path)}
        else:
            outputs[name] = {"status": "not_found", "path": str(path)}
    return outputs


def push_results_to_git() -> bool:
    """Stage and push trading floor results to GitHub."""
    try:
        subprocess.run(
            ["git", "add",
             "data/arena/", "data/departments/trading_floor/",
             "OPERATIONS.md"],
            cwd=str(ROOT), capture_output=True, timeout=10,
        )
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(ROOT), capture_output=True,
        )
        if diff.returncode != 0:  # there are changes
            it_data = _load_iteration()
            subprocess.run(
                ["git", "commit", "-m",
                 f"data: trading floor v8 iter {it_data['iteration']} — auto",
                 "--no-verify"],
                cwd=str(ROOT), capture_output=True, timeout=15,
            )
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=str(ROOT), capture_output=True, timeout=30,
            )
            return True
    except Exception:
        pass
    return False


def run_guardian_cross_pollination() -> Dict:
    """Run guardian cross-pollination after each iteration."""
    guardian_script = ROOT / "scripts" / "sync" / "guardian-cross-pollinate.py"
    if not guardian_script.exists():
        return {"status": "script_missing"}
    try:
        result = subprocess.run(
            ["python3", str(guardian_script)],
            cwd=str(ROOT), capture_output=True, timeout=60, text=True,
        )
        return {"status": "completed", "stdout_tail": result.stdout[-500:] if result.stdout else ""}
    except Exception as e:
        return {"status": f"error: {e}"}


def update_operations_md() -> None:
    """Update OPERATIONS.md with latest iteration data."""
    ops_file = ROOT / "OPERATIONS.md"
    if not ops_file.exists():
        return
    try:
        it_data = _load_iteration()
        best_config = _load_best_config()
        content = ops_file.read_text()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("> **Last updated:**"):
                lines[i] = f"> **Last updated:** {now} | **Auto-refreshed by:** trading-floor-v8 cron"
            elif "**Iteration:**" in line and "**Generation:**" in line:
                lines[i] = f"- **Iteration:** {it_data['iteration']} | **Generation:** {it_data['generation']}"
            elif "**Best bankroll:**" in line:
                tid = best_config.get('best_trader_id', 'unknown')
                lines[i] = f"- **Best bankroll:** ${best_config['best_bankroll']:,.0f} by {tid}"
            elif "**$1M target:**" in line:
                pct = (best_config['best_bankroll'] / 1_000_000) * 100
                mult = 1_000_000 / max(best_config['best_bankroll'], 1)
                lines[i] = f"- **$1M target:** {pct:.1f}% achieved, need {mult:.1f}x more"
        ops_file.write_text("\n".join(lines))
    except Exception:
        pass


# ── CONTINUOUS ITERATION MODE ─────────────────────────────────────────────────

_STOP_FLAG = False

def _signal_handler(sig, frame):
    global _STOP_FLAG
    print(f"\n[v8] Received signal {sig} — stopping after current iteration.")
    _STOP_FLAG = True

def run_continuous_iteration(max_iterations: int = 0, delay_seconds: int = 10):
    """
    Trading Floor v8 continuous iteration mode.
    Runs: sync repos → karpathy loop → cross-pollinate → push → repeat.

    Args:
        max_iterations: 0 = infinite (until SIGTERM/SIGINT)
        delay_seconds: pause between iterations (default 10s)
    """
    global _STOP_FLAG
    _signal.signal(_signal.SIGINT, _signal_handler)
    _signal.signal(_signal.SIGTERM, _signal_handler)

    iteration_count = 0
    print("=" * 70)
    print("TRADING FLOOR v8 — CONTINUOUS ITERATION MODE")
    print(f"Max iterations: {'infinite' if max_iterations == 0 else max_iterations}")
    print(f"Delay between iterations: {delay_seconds}s")
    print("Send SIGINT/SIGTERM to stop gracefully.")
    print("=" * 70)

    while not _STOP_FLAG:
        iteration_count += 1
        if max_iterations > 0 and iteration_count > max_iterations:
            print(f"\n[v8] Reached max iterations ({max_iterations}). Stopping.")
            break

        cycle_start = time.time()
        it_data = _load_iteration()
        print(f"\n{'='*60}")
        print(f"[v8] CYCLE {iteration_count} — iteration {it_data['iteration'] + 1}")
        print(f"{'='*60}")

        # Phase 1: Sync satellite repos
        print("\n[v8] Phase 1: Syncing satellite repos...")
        sync_status = sync_satellite_repos()
        for repo, status in sync_status.items():
            print(f"  {repo}: {status}")

        # Phase 2: Load cross-repo data
        print("\n[v8] Phase 2: Loading cross-repo karpathy data...")
        cross_data = load_cross_repo_karpathy()
        for name, data in cross_data.items():
            status = data.get("status", "loaded")
            if status in ("not_found", "parse_error"):
                print(f"  {name}: {status}")
            else:
                dept = data.get("department", name)
                metric = data.get("primary_metric", {})
                print(f"  {name}: {dept} — {metric.get('name', '?')}={metric.get('value', '?')}")

        # Phase 3: Run Karpathy loop (the main work)
        print("\n[v8] Phase 3: Running Karpathy loop...")
        karpathy_result = run_karpathy_loop()

        # Inject cross-repo data into output
        karpathy_result["cross_repo"] = {
            "sync_status": sync_status,
            "satellite_data": {k: {"status": v.get("status", "loaded")} for k, v in cross_data.items()},
        }

        # Phase 4: Guardian cross-pollination
        print("\n[v8] Phase 4: Guardian cross-pollination...")
        guardian_result = run_guardian_cross_pollination()
        print(f"  Guardian: {guardian_result.get('status')}")

        # Phase 5: Update OPERATIONS.md
        print("\n[v8] Phase 5: Updating OPERATIONS.md...")
        update_operations_md()

        # Phase 6: Push to Git
        print("\n[v8] Phase 6: Pushing to Git...")
        pushed = push_results_to_git()
        print(f"  Pushed: {'yes' if pushed else 'no changes'}")

        cycle_elapsed = time.time() - cycle_start
        print(f"\n[v8] Cycle {iteration_count} complete in {cycle_elapsed:.1f}s")
        print(f"  Iteration: {karpathy_result.get('iteration')}")
        print(f"  Best: ${karpathy_result.get('optimization', {}).get('current_best', 0):,.0f}")
        print(f"  Improved: {karpathy_result.get('optimization', {}).get('improved_this_iteration', False)}")

        # Log cycle summary
        log_file = ROOT / "logs" / "trading-floor-v8.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now(timezone.utc).isoformat()}] cycle={iteration_count} "
                    f"iter={karpathy_result.get('iteration')} "
                    f"best=${karpathy_result.get('optimization', {}).get('current_best', 0):,.0f} "
                    f"elapsed={cycle_elapsed:.1f}s\n")

        if _STOP_FLAG:
            break

        if max_iterations == 0 or iteration_count < max_iterations:
            print(f"\n[v8] Waiting {delay_seconds}s before next iteration...")
            for _ in range(delay_seconds):
                if _STOP_FLAG:
                    break
                time.sleep(1)

    print(f"\n[v8] Stopped after {iteration_count} iterations.")
    return {"iterations_completed": iteration_count}


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        result = run_full_competition()
        print("\n--- LEADERBOARD ---")
        print(json.dumps(result["leaderboard"], indent=2))

    elif cmd == "karpathy":
        # Single Karpathy iteration: backtest → analyze → eliminate → mutate
        karpathy_result = run_karpathy_loop()
        print(json.dumps({
            "status": "completed",
            "department": "trading_floor",
            "iteration": karpathy_result.get("iteration"),
            "best_strategy": karpathy_result.get("best_strategy", {}).get("name"),
            "best_model": karpathy_result.get("best_model", {}).get("name"),
            "best_category": karpathy_result.get("best_category", {}).get("name"),
            "eliminations": len(karpathy_result.get("new_eliminations", [])),
            "mutations": len(karpathy_result.get("mutations", {})),
            "recommendations": len(karpathy_result.get("recommendations", [])),
        }))

    elif cmd == "iterate":
        # v8 continuous iteration: sync → karpathy → cross-pollinate → push → repeat
        max_iter = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        delay = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        run_continuous_iteration(max_iterations=max_iter, delay_seconds=delay)

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
        print(f"Usage: {sys.argv[0]} [run|karpathy|iterate [max_iter] [delay]|leaderboard|status]")
        sys.exit(1)
