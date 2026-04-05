#!/usr/bin/env python3
"""
Trading Floor v5.1 -- 217+ AI Agent Swarm with Multi-Phase Thinking
===================================================================
The most ambitious NBA betting AI system ever built.

Architecture (4 Tiers):
  Tier 1: 4 Premium Traders (GPT-4o, Grok, Gemini, Claude) — full game analysis
  Tier 2: 20 Free Power Traders (Groq, OpenRouter, Cohere, Cerebras) — focused
  Tier 3: 176+ Specialist Swarm (Groq llama-3.1-8b, gemma2-9b) — one per bet category
  Tier 4: 3 Meta-Traders (Paperclip, Hermes, Oracle) — aggregate + synthesize

Karpathy LLM Council Pattern (3 stages):
  Stage 1: All agents predict in parallel
  Stage 2: Anonymized peer review (Hermes)
  Stage 3: Chairman synthesis (Oracle)

API Capacity:
  Groq:       5 keys × 14,400 RPD = 72,000/day
  OpenRouter: 7 keys × 200 RPD   = 1,400/day
  Cohere:     2 keys × 1,000 RPD = 2,000/day
  Cerebras:   1 key  × 1,000 RPD = 1,000/day
  HuggingFace: 4 tokens           = 2,000/day
  Google:     1 key                = 10,000/day
  OpenAI:     1 key                = 10,000/day
  xAI:        1 key                = 5,000/day
  TOTAL: ~153,400+ calls/day

  Needed for 5 games: ~1,000 calls — EASILY within capacity

Usage:
  python trading-floor-v5.py                     # Run for today's games
  python trading-floor-v5.py --date 2026-04-04   # Run for specific date
  python trading-floor-v5.py --status            # Show fleet status
  python trading-floor-v5.py --retrolearn        # Score past predictions
  python trading-floor-v5.py --dry-run           # Simulate without API calls
  python trading-floor-v5.py --keys              # Check API key availability

Inherits & replaces v4's 5-trader system and the 27-trader v5 prototype.
"""

import json
import os
import sys
import csv
import math
import time
import random
import hashlib
import argparse
import traceback
import signal as _signal
import subprocess
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from api_pool import APIPool, get_pool, PROVIDERS
from agent_registry import AgentRegistry, TradingAgent, AgentTier
from bet_categories import (
    ALL_CATEGORIES, CATEGORY_BY_ID, CATEGORIES_BY_GROUP,
    get_specialist_prompt, get_tier2_prompt, get_tier1_prompt, get_meta_prompt,
)


# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════
ROOT = Path("/home/termius/mon-ipad")
NBA_AGENT = Path("/home/termius/nomos-nba-agent")
POLITICAL = Path("/home/termius/nomos-political-alpha")
DATA_DIR = ROOT / "data" / "arena"
TRADERS_DIR = DATA_DIR / "traders-v5"
OUTPUT_LATEST = DATA_DIR / "trading-floor-v5-latest.json"
AGENT_STATE_FILE = DATA_DIR / "agent-states-v5.json"
RETROLEARN_FILE = DATA_DIR / "retrolearn-v5.json"
PREDICTIONS_DIR = DATA_DIR / "predictions-v5"
V5_ITER_FILE = DATA_DIR / "trading-floor-v5-iteration.json"

# External data sources
ODDS_CSV = NBA_AGENT / "data" / "historical-odds" / "nba_2025-26_odds.csv"
GAMES_JSON = ROOT / "nba-quant-space" / "data" / "historical" / "games-2025-26.json"
PREDICTIONS_JSON = ROOT / "data" / "nba-agent" / "predictions-latest.json"

STAT_KEYS = ['fg_pct', 'fg3_pct', 'ft_pct', 'reb', 'ast', 'tov', 'stl', 'blk', 'plus_minus']


def _output_dated(d: str) -> Path:
    return DATA_DIR / f"trading-floor-v5-{d}.json"


# ═══════════════════════════════════════════════════════════════════════════════
# REAL ML PREDICTIONS — from 6 HF evolution islands (not LLM guessing)
# ═══════════════════════════════════════════════════════════════════════════════
_ML_PREDICTIONS_CACHE = {}

def _inject_ml_predictions(home: str, away: str, date_str: str) -> dict:
    """Inject real ML model predictions from HF spaces into agent context.

    Returns dict with keys that get merged into ctx:
      - model_prob_home: ensemble P(home_win) from evolved models
      - model_spread: predicted margin (home - away)
      - model_total: predicted total points
      - model_confidence: high/medium/low
      - model_details: list of individual model predictions
      - model_n_models: how many models contributed
      - model_avg_brier: average training brier of contributing models
    """
    global _ML_PREDICTIONS_CACHE

    # Check cached predictions file first
    if not _ML_PREDICTIONS_CACHE:
        pred_file = DATA_DIR / "model-predictions-latest.json"
        if pred_file.exists():
            try:
                data = json.loads(pred_file.read_text())
                for p in data.get("predictions", []):
                    key = (p.get("home_team", ""), p.get("away_team", ""))
                    _ML_PREDICTIONS_CACHE[key] = p
            except Exception:
                pass

    # Look up this game
    home_full = ABBR_TO_FULL.get(home, home)
    away_full = ABBR_TO_FULL.get(away, away)
    pred = _ML_PREDICTIONS_CACHE.get((home_full, away_full))

    result = {}
    if pred and pred.get("predictions"):
        ml = pred["predictions"].get("moneyline", {})
        sp = pred["predictions"].get("spread", {})
        tot = pred["predictions"].get("total", {})
        qual = pred.get("quality", {})

        if ml.get("home_win_prob"):
            result["model_prob_home"] = ml["home_win_prob"]
            result["model_prob_ci"] = ml.get("ci_90", [0.3, 0.7])
            result["model_ml_edge"] = ml.get("edge_vs_odds")

        if sp.get("predicted_margin") is not None:
            result["model_spread"] = sp["predicted_margin"]
            result["model_spread_ci"] = sp.get("ci_90")

        if tot.get("predicted_total") is not None:
            result["model_total"] = tot["predicted_total"]
            result["model_total_ci"] = tot.get("ci_90")

        result["model_confidence"] = qual.get("confidence", "low")
        result["model_n_models"] = qual.get("n_models", 0)
        result["model_avg_brier"] = qual.get("avg_brier", 1.0)
        result["model_details"] = pred.get("model_details", [])

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# ITERATION TRACKING
# ═══════════════════════════════════════════════════════════════════════════════
def _load_iteration() -> Dict:
    if V5_ITER_FILE.exists():
        try:
            return json.loads(V5_ITER_FILE.read_text())
        except Exception:
            pass
    return {"iteration": 0, "generation": 0, "total_api_calls": 0, "total_bets": 0}


def _save_iteration(it: Dict) -> None:
    V5_ITER_FILE.parent.mkdir(parents=True, exist_ok=True)
    V5_ITER_FILE.write_text(json.dumps(it, indent=2))


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM MAPPING
# ═══════════════════════════════════════════════════════════════════════════════
TEAM_MAP = {
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
ABBR_TO_FULL = {v: k for k, v in TEAM_MAP.items()}

# ETF Universe for political trading (retained from v4)
ETF_UNIVERSE = {
    "SPY": {"name": "S&P 500", "sector": "broad", "beta": 1.0},
    "QQQ": {"name": "NASDAQ 100", "sector": "technology", "beta": 1.2},
    "XLK": {"name": "Technology", "sector": "technology", "beta": 1.2},
    "XLE": {"name": "Energy", "sector": "energy", "beta": 1.3},
    "XLF": {"name": "Financials", "sector": "financials", "beta": 1.1},
    "XLV": {"name": "Healthcare", "sector": "healthcare", "beta": 0.8},
    "GLD": {"name": "Gold", "sector": "commodity", "beta": 0.3},
    "TLT": {"name": "Long-term Treasuries", "sector": "bonds", "beta": -0.2},
    "IWM": {"name": "Russell 2000", "sector": "small_cap", "beta": 1.1},
}


# ═══════════════════════════════════════════════════════════════════════════════
# ODDS / MATH HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def american_to_decimal(ml):
    ml = float(ml)
    if 1.0 < ml < 100.0 and ml != round(ml):
        return ml  # already decimal
    if ml == 0:
        return 2.0
    return 1.0 + ml / 100.0 if ml > 0 else 1.0 + 100.0 / abs(ml)


def decimal_to_prob(dec):
    return 1.0 / dec if dec > 1.0 else 0.5


def kelly_criterion(prob: float, odds: float, fraction: float = 0.5) -> float:
    """Kelly criterion bet sizing with fraction. Clamped to [0, 0.15]."""
    b = odds - 1.0
    if b <= 0 or prob <= 0:
        return 0.0
    edge = prob * b - (1.0 - prob)
    if edge <= 0:
        return 0.0
    k = (edge / b) * fraction
    return max(0.0, min(k, 0.15))


# ═══════════════════════════════════════════════════════════════════════════════
# SIZING STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════════
def _sz_value_hunter_half_kelly(edge, odds, bankroll, **kw):
    if edge < 0.04:
        return 0.0
    return bankroll * kelly_criterion(0.5 + edge, odds, 0.5)

def _sz_half_kelly(edge, odds, bankroll, **kw):
    return bankroll * kelly_criterion(0.5 + edge, odds, 0.5)

def _sz_quarter_kelly(edge, odds, bankroll, **kw):
    return bankroll * kelly_criterion(0.5 + edge, odds, 0.25)

def _sz_eighth_kelly(edge, odds, bankroll, **kw):
    return bankroll * kelly_criterion(0.5 + edge, odds, 0.125)

def _sz_proportional_edge(edge, odds, bankroll, **kw):
    return bankroll * min(edge * 2.0, 0.10)

def _sz_confidence_scaled(edge, odds, bankroll, **kw):
    scale = min((edge - 0.02) / 0.08, 1.0) if edge > 0.02 else 0.0
    return bankroll * (0.01 + 0.04 * scale)

def _sz_flat_2pct(edge, odds, bankroll, **kw):
    return bankroll * 0.02

def _sz_flat_1pct(edge, odds, bankroll, **kw):
    return bankroll * 0.01

def _sz_underdog_specialist(edge, odds, bankroll, **kw):
    if odds < 2.5 or edge < 0.03:
        return 0.0
    k = kelly_criterion(0.5 + edge, odds, 0.5) * min(math.sqrt(odds) / 3.0, 1.5)
    return bankroll * min(k, 0.08)

def _sz_meta_allocation(edge, odds, bankroll, **kw):
    consensus = kw.get("consensus_strength", 0.5)
    return bankroll * min(consensus * 0.05, 0.10)

def _sz_meta_synthesis(edge, odds, bankroll, **kw):
    return bankroll * kelly_criterion(0.5 + edge, odds, 0.5)

SIZING_FNS = {
    "value_hunter_half_kelly": _sz_value_hunter_half_kelly,
    "value_hunter": _sz_value_hunter_half_kelly,
    "half_kelly": _sz_half_kelly,
    "quarter_kelly": _sz_quarter_kelly,
    "eighth_kelly": _sz_eighth_kelly,
    "proportional_edge": _sz_proportional_edge,
    "confidence_scaled": _sz_confidence_scaled,
    "flat_2pct": _sz_flat_2pct,
    "flat_1pct": _sz_flat_1pct,
    "underdog_specialist": _sz_underdog_specialist,
    "meta_allocation": _sz_meta_allocation,
    "meta_consensus": lambda *a, **kw: 0.0,
    "meta_synthesis": _sz_meta_synthesis,
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════
def load_games_rich() -> Tuple[Dict, List[Dict]]:
    """Load historical game results with team stats."""
    fp = NBA_AGENT / "data" / "historical" / "games-2025-26.json"
    if not fp.exists():
        fp = GAMES_JSON
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
        hs = h_data.get("pts", h_data.get("PTS", 0))
        as_ = a_data.get("pts", a_data.get("PTS", 0))
        if not hs and not as_:
            continue
        game_entry = {
            "date": game_date, "home": home, "away": away,
            "home_full": home_full, "away_full": away_full,
            "home_score": hs, "away_score": as_,
            "home_won": hs > as_,
            "total_pts": hs + as_,
            "margin": hs - as_,
            "home_stats": {k: h_data.get(k, 0) for k in STAT_KEYS},
            "away_stats": {k: a_data.get(k, 0) for k in STAT_KEYS},
        }
        results[(game_date, home, away)] = game_entry
        enriched.append(game_entry)
    enriched.sort(key=lambda g: g["date"])
    return results, enriched


def load_odds() -> Dict:
    """Load historical odds CSV, keyed by (date, home_abbr, away_abbr)."""
    if not ODDS_CSV.exists():
        return {}
    odds = {}

    def parse_odds(s):
        s = str(s).strip()
        if not s:
            return None
        try:
            return american_to_decimal(s)
        except (ValueError, ZeroDivisionError):
            return None

    with open(ODDS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            date_str = row.get("date", "").strip()
            home_full = row.get("home_team", "").strip()
            away_full = row.get("away_team", "").strip()
            h = TEAM_MAP.get(home_full)
            a = TEAM_MAP.get(away_full)
            if not h or not a or not date_str:
                continue
            key = (date_str, h, a)
            source = row.get("source", "")
            # Prefer betmgm over bovada
            if key in odds and "bovada" in source and "bovada" not in odds[key].get("_source", ""):
                continue
            ml_h = parse_odds(row.get("moneyline_home", ""))
            ml_a = parse_odds(row.get("moneyline_away", ""))
            if not ml_h or not ml_a:
                continue
            spread_str = row.get("spread_home", "").strip()
            total_str = row.get("total", "").strip()
            odds[key] = {
                "ml_home_dec": ml_h,
                "ml_away_dec": ml_a,
                "impl_home": decimal_to_prob(ml_h),
                "impl_away": decimal_to_prob(ml_a),
                "spread_home": float(spread_str) if spread_str else None,
                "total": float(total_str) if total_str else None,
                "ml_home_raw": row.get("moneyline_home", ""),
                "ml_away_raw": row.get("moneyline_away", ""),
                "_source": source,
            }
    return odds


def load_todays_predictions() -> List[Dict]:
    """Load model predictions from predictions-latest.json."""
    if not PREDICTIONS_JSON.exists():
        return []
    try:
        with open(PREDICTIONS_JSON) as f:
            data = json.load(f)
        return data.get("predictions", [])
    except Exception:
        return []


def compute_standings(all_games: List[Dict], up_to_date: str) -> Dict[str, Dict]:
    """Compute team standings up to a date."""
    standings = defaultdict(lambda: {"w": 0, "l": 0, "pts_for": 0, "pts_against": 0})
    for g in all_games:
        if g["date"] >= up_to_date:
            break
        h, a = g["home"], g["away"]
        hs, as_ = g["home_score"], g["away_score"]
        standings[h]["pts_for"] += hs
        standings[h]["pts_against"] += as_
        standings[a]["pts_for"] += as_
        standings[a]["pts_against"] += hs
        if g["home_won"]:
            standings[h]["w"] += 1
            standings[a]["l"] += 1
        else:
            standings[a]["w"] += 1
            standings[h]["l"] += 1
    for team in standings:
        s = standings[team]
        total = s["w"] + s["l"]
        s["win_pct"] = s["w"] / total if total > 0 else 0.5
        s["ppg"] = s["pts_for"] / total if total > 0 else 110
        s["opp_ppg"] = s["pts_against"] / total if total > 0 else 110
    return dict(standings)


def compute_team_form(all_games: List[Dict], team: str, up_to_date: str,
                      window: int = 10) -> Dict:
    """Compute recent form (last N games) for a team."""
    relevant = [g for g in all_games
                if g["date"] < up_to_date and (g["home"] == team or g["away"] == team)]
    recent = relevant[-window:]
    if not recent:
        return {"games": 0, "w": 0, "l": 0, "avg_pts": 110, "avg_fg_pct": 0.45}
    w = 0
    pts_list = []
    fg_list = []
    for g in recent:
        if g["home"] == team:
            won = g["home_won"]
            pts = g["home_score"]
            fg = g["home_stats"].get("fg_pct", 0.45)
        else:
            won = not g["home_won"]
            pts = g["away_score"]
            fg = g["away_stats"].get("fg_pct", 0.45)
        if won:
            w += 1
        pts_list.append(pts)
        fg_list.append(fg if fg else 0.45)
    return {
        "games": len(recent), "w": w, "l": len(recent) - w,
        "avg_pts": sum(pts_list) / len(pts_list),
        "avg_fg_pct": sum(fg_list) / len(fg_list),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GAME CONTEXT BUILDER
# ═══════════════════════════════════════════════════════════════════════════════
def build_game_context(game: Dict, odds_entry: Optional[Dict],
                       standings: Dict, all_games: List[Dict]) -> Dict:
    """Build a rich context dict for prompts."""
    home = game["home"]
    away = game["away"]
    date_str = game["date"]

    h_stand = standings.get(home, {})
    a_stand = standings.get(away, {})
    h_form = compute_team_form(all_games, home, date_str)
    a_form = compute_team_form(all_games, away, date_str)

    ctx = {
        "date": date_str,
        "home": home,
        "away": away,
        "home_team": ABBR_TO_FULL.get(home, home),
        "away_team": ABBR_TO_FULL.get(away, away),
        "home_standings": h_stand,
        "away_standings": a_stand,
        "home_form": f"{h_form['w']}-{h_form['l']} L{h_form['games']}, {h_form['avg_pts']:.1f} PPG",
        "away_form": f"{a_form['w']}-{a_form['l']} L{a_form['games']}, {a_form['avg_pts']:.1f} PPG",
        "home_form_L10": h_form,
        "away_form_L10": a_form,
    }

    if odds_entry:
        ctx["odds"] = odds_entry
        ctx["odds_home"] = odds_entry.get("ml_home_raw", "N/A")
        ctx["odds_away"] = odds_entry.get("ml_away_raw", "N/A")
        ctx["spread_home"] = odds_entry.get("spread_home", "N/A")
        ctx["total"] = odds_entry.get("total", "N/A")
        ctx["impl_home"] = odds_entry.get("impl_home", 0.5)
        ctx["impl_away"] = odds_entry.get("impl_away", 0.5)
        ctx["model_prob_home"] = odds_entry.get("impl_home", 0.5)
    else:
        # Estimate from standings
        h_wp = h_stand.get("win_pct", 0.5)
        a_wp = a_stand.get("win_pct", 0.5)
        raw = (h_wp * 1.03) / (h_wp * 1.03 + a_wp) if (h_wp + a_wp) > 0 else 0.55
        ctx["odds"] = {}
        ctx["odds_home"] = "N/A"
        ctx["odds_away"] = "N/A"
        ctx["spread_home"] = "N/A"
        ctx["total"] = "N/A"
        ctx["impl_home"] = raw
        ctx["impl_away"] = 1 - raw
        ctx["model_prob_home"] = raw

    ctx["predicted_total"] = (
        h_stand.get("ppg", 110) + a_stand.get("ppg", 110)
    ) if h_stand or a_stand else 224.0

    return ctx




# ===============================================================================
# MULTI-PHASE THINKING ARCHITECTURE (v5.1)
# ===============================================================================
class ThinkingPhase:
    # Phase 1: Game Analysis (1 shared call per game, cached for all agents)
    # Phase 2: Category Screening (agents screen which categories offer VALUE)
    # Phase 3: Bet Decision (1 call per screened category, full Kelly sizing)

    PHASE_1_SYSTEM = (
        "You are an elite NBA betting analyst. Analyze this NBA matchup comprehensively. "
        "Output ONLY valid JSON with keys: team_strengths (object), key_factors (list of str), "
        "injury_impact (object), model_agreement (str: high/medium/low), "
        "edge_opportunities (list of str), predicted_score (object with home/away), "
        "confidence (float 0-1)."
    )

    PHASE_2_SYSTEM = (
        "You are an NBA betting value screener. Given game analysis and a list of bet categories, "
        "identify which categories offer betting VALUE. "
        "Output ONLY valid JSON: a list of objects, each with: "
        "category_id (str), has_edge (bool), estimated_edge (float 0-0.15), "
        "confidence (float 0-1), reasoning (str, max 30 words). "
        "Only include categories where has_edge=true."
    )

    PHASE_3_SYSTEM = (
        "You are an elite NBA bet decision engine. Make a final bet decision on ONE specific "
        "category given all available data. "
        "Output ONLY valid JSON with: bet (bool), side (str), edge (float 0-0.15), "
        "confidence (float 0-1), kelly_fraction (float 0-0.15), "
        "reasoning (str, max 50 words), key_factor (str)."
    )

    @staticmethod
    def build_phase1_prompt(ctx):
        # type: (dict) -> str
        home = ctx.get("home_team", ctx.get("home", ""))
        away = ctx.get("away_team", ctx.get("away", ""))
        lines = [
            "Analyze this NBA matchup: " + away + " @ " + home,
            "Date: " + str(ctx.get("date", "today")),
            "Home form: " + str(ctx.get("home_form", "N/A")),
            "Away form: " + str(ctx.get("away_form", "N/A")),
            "Home odds: " + str(ctx.get("odds_home", "N/A"))
            + " | Away odds: " + str(ctx.get("odds_away", "N/A")),
            "Spread: " + str(ctx.get("spread_home", "N/A"))
            + " | Total: " + str(ctx.get("total", "N/A")),
            "Implied home prob: {:.3f}".format(ctx.get("impl_home", 0.5)),
            "ML model P(home): " + str(ctx.get("model_prob_home", "N/A")),
            "Model spread: " + str(ctx.get("model_spread", "N/A")),
            "Model total: " + str(ctx.get("model_total", "N/A")),
            "Model confidence: " + str(ctx.get("model_confidence", "low")),
            "Models contributing: " + str(ctx.get("model_n_models", 0)),
            "Avg model Brier: " + str(ctx.get("model_avg_brier", 1.0)),
            "",
            "Provide comprehensive game analysis to guide all downstream bet decisions.",
        ]
        return "\n".join(lines)

    @staticmethod
    def build_phase2_prompt(game_analysis, categories, ctx):
        # type: (dict, list, dict) -> str
        home = ctx.get("home_team", ctx.get("home", ""))
        away = ctx.get("away_team", ctx.get("away", ""))
        cat_list = "\n".join(
            "- " + c["id"] + ": " + c["name"] + " (" + c["group"] + ")"
            for c in categories
        )
        import json as _json
        analysis_str = _json.dumps(game_analysis, indent=2, default=str)[:1200]
        return (
            "Game: " + away + " @ " + home + "\n\n"
            "GAME ANALYSIS:\n" + analysis_str + "\n\n"
            "CATEGORIES TO SCREEN:\n" + cat_list + "\n\n"
            "Which of these categories have exploitable edge? "
            "Consider model predictions vs market odds. "
            "Return JSON list with category_id, has_edge, estimated_edge, confidence, reasoning."
        )

    @staticmethod
    def build_phase3_prompt(category, game_analysis, ctx):
        # type: (dict, dict, dict) -> str
        home = ctx.get("home_team", ctx.get("home", ""))
        away = ctx.get("away_team", ctx.get("away", ""))
        key_factors = ", ".join(game_analysis.get("key_factors", [])[:4])
        edge_opps = ", ".join(game_analysis.get("edge_opportunities", [])[:3])
        return (
            "FINAL BET DECISION\n"
            "Game: " + away + " @ " + home + "\n"
            "Category: " + category.get("id", "") + " -- " + category.get("name", "") + "\n"
            "Group: " + category.get("group", "") + "\n"
            "Estimated edge from screening: {:.3f}\n\n".format(
                category.get("estimated_edge", 0)) +
            "GAME ANALYSIS (condensed):\n"
            "  Key factors: " + key_factors + "\n"
            "  Edge opportunities: " + edge_opps + "\n"
            "  Model agreement: " + str(game_analysis.get("model_agreement", "low")) + "\n\n"
            "MARKET DATA:\n"
            "  Home odds: " + str(ctx.get("odds_home", "N/A"))
            + " | Away: " + str(ctx.get("odds_away", "N/A")) + "\n"
            "  Spread: " + str(ctx.get("spread_home", "N/A"))
            + " | Total: " + str(ctx.get("total", "N/A")) + "\n"
            "  ML P(home): {:.3f} (mkt={:.3f})\n".format(
                ctx.get("model_prob_home", 0.5), ctx.get("impl_home", 0.5)) +
            "  Model spread: " + str(ctx.get("model_spread", "N/A"))
            + " | Model total: " + str(ctx.get("model_total", "N/A")) + "\n\n"
            "Make final bet/no-bet decision with Kelly fraction. Be specific about which side."
        )


# ===============================================================================
# CLAUDE CODE CLI HANDLER
# ===============================================================================
def _call_claude_cli(pool, agent, prompt, system=""):
    # type: (Any, Any, str, str) -> Optional[dict]
    """Call Claude Code CLI for anthropic_cli provider agents via pool.call_llm_cli()."""
    return pool.call_llm_cli(
        model=agent.model,
        prompt=prompt,
        system=system or "You are an elite NBA betting analyst. Respond only with valid JSON.",
        max_tokens=1024,
        temperature=0.3,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CORE: TRADING FLOOR V5 ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════
class TradingFloorV5:
    """Orchestrator for 217+ AI agents across 4 tiers with multi-phase thinking."""

    def __init__(self, dry_run: bool = False, multiphase: bool = False):
        self.pool = get_pool()
        self.registry = AgentRegistry()
        self.dry_run = dry_run
        self.multiphase = multiphase    # Enable 3-phase thinking architecture
        self.predictions: Dict[str, Dict[str, Any]] = {}
        self.consensus: Dict[str, dict] = {}
        self.bets: List[dict] = []
        self.iteration = _load_iteration()
        self.run_stats = {
            "start_time": None,
            "end_time": None,
            "games_processed": 0,
            "agents_called": 0,
            "api_calls_made": 0,
            "api_errors": 0,
            "total_bets": 0,
            "tier_calls": {1: 0, 2: 0, 3: 0, 4: 0},
            "multiphase_calls": 0,
            "phase1_hits": 0,
            "phase2_screenings": 0,
            "phase3_decisions": 0,
        }
        # Phase 1 cache: game_key -> game_analysis dict (shared across agents)
        self._game_analysis_cache: Dict[str, dict] = {}

        # Load saved agent states
        if AGENT_STATE_FILE.exists():
            self.registry.load_state(str(AGENT_STATE_FILE))

    # ───────────────────────────────────────────────────────────────────────
    # MAIN ENTRY: run for a date
    # ───────────────────────────────────────────────────────────────────────
    def run(self, target_date: str, games_per_iter: int = 20):
        """Run the full 4-tier trading floor for a given date."""
        self.run_stats["start_time"] = datetime.now(timezone.utc).isoformat()
        self.iteration["iteration"] += 1

        print("=" * 80)
        print("TRADING FLOOR v5.1 -- 217+ AI AGENT SWARM + MULTI-PHASE THINKING")
        print(f"Date: {target_date} | Iteration: {self.iteration['iteration']}")
        print(f"Agents: {len(self.registry.active_agents)} active "
              f"({len(self.registry.agents)} total)")
        mode_parts = ["DRY-RUN (synthetic)" if self.dry_run else "LIVE (real API calls)"]
        if self.multiphase:
            mode_parts.append("3-PHASE THINKING ON")
        print(f"Mode: {' | '.join(mode_parts)}")
        print("=" * 80)

        # Load data
        all_odds = load_odds()
        results_dict, all_games = load_games_rich()

        # Find games for target date
        date_games = [g for g in all_games if g["date"] == target_date]

        # If no played games, try today's predictions
        if not date_games:
            preds = load_todays_predictions()
            for p in preds:
                home_full = p.get("home_team", p.get("home", ""))
                away_full = p.get("away_team", p.get("away", ""))
                home = TEAM_MAP.get(home_full, home_full[:3].upper() if home_full else "UNK")
                away = TEAM_MAP.get(away_full, away_full[:3].upper() if away_full else "UNK")
                if p.get("date", p.get("game_date", "")) == target_date or not date_games:
                    date_games.append({
                        "date": target_date, "home": home, "away": away,
                        "home_full": home_full, "away_full": away_full,
                        "home_score": 0, "away_score": 0, "home_won": None,
                        "total_pts": 0, "margin": 0,
                        "home_stats": {}, "away_stats": {},
                        "_predicted": True,
                        "model_prob_home": p.get("prob_home", p.get("home_win_prob", 0.5)),
                    })

        # Fallback: load from odds-latest.json (today's live odds feed)
        if not date_games:
            odds_latest = ROOT / "data" / "nba-agent" / "odds-latest.json"
            if odds_latest.exists():
                try:
                    live_games = json.loads(odds_latest.read_text())
                    if isinstance(live_games, dict):
                        live_games = live_games.get("games", live_games.get("predictions", []))
                    for g in live_games:
                        home_full = g.get("home_team", g.get("home", ""))
                        away_full = g.get("away_team", g.get("away", ""))
                        home = TEAM_MAP.get(home_full, home_full[:3].upper() if home_full else "UNK")
                        away = TEAM_MAP.get(away_full, away_full[:3].upper() if away_full else "UNK")
                        # Extract bookmaker odds directly from game object
                        live_odds_entry = None
                        for bk in g.get("bookmakers", []):
                            for mkt in bk.get("markets", []):
                                if mkt["key"] == "h2h":
                                    outcomes = {o["name"]: o["price"] for o in mkt.get("outcomes", [])}
                                    ml_h = outcomes.get(home_full, 1.91)
                                    ml_a = outcomes.get(away_full, 1.91)
                                    live_odds_entry = {
                                        "ml_home_dec": ml_h, "ml_away_dec": ml_a,
                                        "impl_home": 1.0 / ml_h, "impl_away": 1.0 / ml_a,
                                        "ml_home_raw": str(ml_h), "ml_away_raw": str(ml_a),
                                        "spread_home": None, "total": None,
                                    }
                                    break
                            if live_odds_entry:
                                break
                        ml_preds = _inject_ml_predictions(home, away, target_date)
                        ml_prob = ml_preds.get("model_prob_home", 0.5)
                        date_games.append({
                            "date": target_date, "home": home, "away": away,
                            "home_full": home_full, "away_full": away_full,
                            "home_score": 0, "away_score": 0, "home_won": None,
                            "total_pts": 0, "margin": 0,
                            "home_stats": {}, "away_stats": {},
                            "_live_odds": True,
                            "_live_odds_entry": live_odds_entry,
                            "model_prob_home": ml_prob,
                        })
                    if date_games:
                        print(f"  Using odds-latest.json: {len(date_games)} live games")
                except Exception as e:
                    print(f"  odds-latest.json load failed: {e}")

        if not date_games:
            print(f"\nNo games found for {target_date}. Try: --date YYYY-MM-DD")
            return

        date_games = date_games[:games_per_iter]
        standings = compute_standings(all_games, target_date)

        print(f"\nGames: {len(date_games)} | Historical odds: {len(all_odds):,} entries")
        print(f"API capacity: {self.pool.get_total_daily_capacity():,} calls/day")
        cap_report = self.pool.get_capacity_report()
        active_providers = [p for p, info in cap_report.items() if info.get("keys", 0) > 0]
        print(f"Active providers: {', '.join(active_providers)}")

        # Process each game through the 4-tier pipeline
        for game_idx, game in enumerate(date_games):
            home = game["home"]
            away = game["away"]
            game_key = f"{game['date']}_{away}@{home}"

            print(f"\n{'─' * 75}")
            print(f"GAME {game_idx + 1}/{len(date_games)}: {away} @ {home}")
            if game.get("home_score") and game.get("away_score"):
                print(f"  Result: {game['home_score']}-{game['away_score']} "
                      f"({'HOME' if game['home_won'] else 'AWAY'} wins)")
            print(f"{'─' * 75}")

            # Build context — prefer historical odds CSV, fall back to embedded live odds
            odds_key = (game["date"], home, away)
            odds_entry = all_odds.get(odds_key) or game.get("_live_odds_entry")
            ctx = build_game_context(game, odds_entry, standings, all_games)

            # Inject REAL ML model predictions from 6 evolution islands
            if game.get("model_prob_home"):
                ctx["model_prob_home"] = game["model_prob_home"]
            ctx.update(_inject_ml_predictions(home, away, game.get("date", target_date)))

            # === PHASE 1 (Multi-phase): Shared Game Analysis ===
            if self.multiphase:
                game_analysis = self._phase1_game_analysis(ctx, game_key)
                ctx["_game_analysis"] = game_analysis
                self.run_stats["phase1_hits"] += 1
            else:
                game_analysis = None

            # === STAGE 1: All agents predict in parallel ===
            print(f"\n  [Stage 1] Parallel prediction -- {len(self.registry.active_agents)} agents...")
            game_predictions = self._stage1_parallel_predict(ctx, game_key)

            # === STAGE 2: Anonymized peer review (Hermes) ===
            print(f"  [Stage 2] Peer review (Hermes)...")
            peer_review = self._stage2_peer_review(game_predictions, ctx, game_key)

            # === STAGE 3: Chairman synthesis (Oracle) ===
            print(f"  [Stage 3] Chairman synthesis (Oracle)...")
            synthesis = self._stage3_chairman_synthesis(
                game_predictions, peer_review, ctx, game_key
            )
            self.consensus[game_key] = synthesis

            # === PHASE 2+3 (Multi-phase): Category Screening + Deep Decisions ===
            multiphase_bets: List[dict] = []
            if self.multiphase and game_analysis:
                print(f"  [Phase 2] Category screening (T1/T2 agents)...")
                screened_cats = self._phase2_category_screening(
                    game_analysis, ctx, game_key
                )
                print(f"  [Phase 3] Deep bet decisions ({len(screened_cats)} categories)...")
                multiphase_bets = self._phase3_bet_decisions(
                    screened_cats, game_analysis, ctx, game_key, game, odds_entry
                )
                print(f"    Multi-phase: {len(screened_cats)} screened -> "
                      f"{len(multiphase_bets)} bets")

            # === Generate bets from synthesis ===
            game_bets = self._generate_bets(synthesis, ctx, odds_entry, game_key, game)
            # Merge multi-phase bets (deduplicate by category)
            if multiphase_bets:
                existing_cats = {b["category"] for b in game_bets}
                for mb in multiphase_bets:
                    if mb.get("category") not in existing_cats:
                        game_bets.append(mb)
                        existing_cats.add(mb["category"])
            self.bets.extend(game_bets)
            self.run_stats["games_processed"] += 1

            # Settle bets if we have results
            if game.get("home_won") is not None:
                self._settle_bets(game_bets, game)

            extra = f" ({len(multiphase_bets)} from multi-phase)" if multiphase_bets else ""
            print(f"\n  Summary: {len(game_predictions)} predictions -> "
                  f"{len(game_bets)} bets generated{extra}")

        # Save everything
        self.run_stats["end_time"] = datetime.now(timezone.utc).isoformat()
        self._save_results(target_date)
        self._print_summary()

    # ===================================================================
    # STAGE 1: Parallel Prediction
    # ===================================================================
    def _stage1_parallel_predict(self, ctx: dict, game_key: str) -> Dict[str, dict]:
        """All tiers predict in parallel using thread pool."""
        predictions = {}

        # --- Tier 1: Premium (careful with paid APIs) ---
        for agent in self.registry.tier1:
            if not agent.active:
                continue
            pred = self._call_agent(agent, ctx, game_key)
            if pred:
                predictions[agent.id] = pred
                self.run_stats["tier_calls"][1] += 1

        t1_count = len(predictions)
        print(f"    T1 Premium: {t1_count} predictions")

        # --- Tier 2: Free Power (parallel) ---
        t2_agents = [a for a in self.registry.tier2 if a.active]
        t2_preds = self._parallel_call(t2_agents, ctx, game_key)
        predictions.update(t2_preds)
        for _ in t2_preds:
            self.run_stats["tier_calls"][2] += 1
        print(f"    T2 Free Power: {len(t2_preds)} predictions")

        # --- Tier 3: Specialist Swarm (parallel, batch by provider) ---
        # ALL specialists get a chance — 120+ categories per game
        t3_agents = [a for a in self.registry.tier3 if a.active]
        # Filter out agents with unknown categories only
        t3_agents = [a for a in t3_agents if CATEGORY_BY_ID.get(a.focus_category) is not None]

        t3_preds = self._parallel_call(t3_agents, ctx, game_key)
        predictions.update(t3_preds)
        for _ in t3_preds:
            self.run_stats["tier_calls"][3] += 1
        print(f"    T3 Specialist: {len(t3_preds)} predictions "
              f"(of {len(t3_agents)} sampled)")

        print(f"    Total: {len(predictions)} predictions collected")
        return predictions

    def _parallel_call(self, agents: List[TradingAgent], ctx: dict,
                       game_key: str) -> Dict[str, dict]:
        """Call multiple agents in parallel. Returns {agent_id: prediction}."""
        predictions = {}

        if self.dry_run:
            for agent in agents:
                pred = self._synthetic_prediction(agent, ctx)
                predictions[agent.id] = pred
                self.run_stats["agents_called"] += 1
            return predictions

        max_workers = min(30, len(agents))
        if max_workers == 0:
            return predictions

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for agent in agents:
                future = executor.submit(self._call_agent, agent, ctx, game_key)
                futures[future] = agent

            for future in as_completed(futures, timeout=180):
                agent = futures[future]
                try:
                    pred = future.result()
                    if pred:
                        predictions[agent.id] = pred
                except Exception:
                    self.run_stats["api_errors"] += 1

        return predictions

    def _call_agent(self, agent: TradingAgent, ctx: dict, game_key: str) -> Optional[dict]:
        """Call a single agent's LLM to get a prediction."""
        self.run_stats["agents_called"] += 1
        self.run_stats["api_calls_made"] += 1

        if self.dry_run:
            return self._synthetic_prediction(agent, ctx)

        # Build prompt based on tier
        if agent.tier == AgentTier.PREMIUM:
            prompt = get_tier1_prompt(ctx)
        elif agent.tier == AgentTier.FREE_POWER:
            prompt = get_tier2_prompt(ctx, agent.focus_groups)
        elif agent.tier == AgentTier.SPECIALIST:
            cat = CATEGORY_BY_ID.get(agent.focus_category)
            if not cat:
                return None
            prompt = get_specialist_prompt(cat, ctx, agent.focus_side)
        else:
            return None  # Meta agents handled separately

        # Route to correct backend
        if agent.provider == "anthropic_cli":
            # Claude Code CLI via subprocess
            result = _call_claude_cli(self.pool, agent, prompt)
        else:
            # Standard OpenAI-compat API pool
            result = self.pool.call_llm(
                provider=agent.provider,
                prompt=prompt,
                model=agent.model,
                temperature=0.3 + (0.2 if agent.personality == "contrarian" else 0.0),
            )

        if result:
            result["_agent_id"] = agent.id
            result["_agent_tier"] = agent.tier.name
            result["_game_key"] = game_key
            result["_timestamp"] = datetime.now(timezone.utc).isoformat()
            self.predictions.setdefault(agent.id, {})[game_key] = result

        return result

    def _synthetic_prediction(self, agent: TradingAgent, ctx: dict) -> dict:
        """Generate synthetic prediction for dry-run mode."""
        seed = hashlib.md5(
            f"{agent.id}_{ctx['home']}_{ctx['away']}_{ctx['date']}".encode()
        ).hexdigest()
        rng = random.Random(seed)

        base_prob = ctx.get("model_prob_home", ctx.get("impl_home", 0.5))
        noise = rng.gauss(0, 0.05)
        prob = max(0.05, min(0.95, base_prob + noise))

        return {
            "ml_fg": {
                "direction": "home" if prob > 0.5 else "away",
                "confidence": abs(prob - 0.5) * 2,
                "edge_pct": round((prob - ctx.get("impl_home", 0.5)) * 100, 2),
            },
            "spread_fg": {
                "direction": "home" if rng.random() > 0.5 else "away",
                "confidence": rng.uniform(0.3, 0.7),
                "edge_pct": round(rng.gauss(0, 3), 2),
            },
            "total_fg": {
                "direction": "over" if rng.random() > 0.5 else "under",
                "confidence": rng.uniform(0.3, 0.7),
                "edge_pct": round(rng.gauss(0, 3), 2),
            },
            "_synthetic": True,
            "_agent_id": agent.id,
            "_agent_tier": agent.tier.name,
        }

    # ===================================================================
    # MULTI-PHASE THINKING METHODS (v5.1)
    # ===================================================================
    def _phase1_game_analysis(self, ctx, game_key):
        # type: (dict, str) -> dict
        """Phase 1: Shared game analysis, cached per game_key."""
        if game_key in self._game_analysis_cache:
            return self._game_analysis_cache[game_key]

        if self.dry_run:
            analysis = {
                "team_strengths": {
                    "home": ctx.get("home_form", "5-5 L10"),
                    "away": ctx.get("away_form", "5-5 L10"),
                },
                "key_factors": ["home advantage", "recent form", "ML model edge"],
                "injury_impact": {"home": "none known", "away": "none known"},
                "model_agreement": ctx.get("model_confidence", "medium"),
                "edge_opportunities": ["moneyline", "total"],
                "predicted_score": {
                    "home": round(ctx.get("predicted_total", 224) * 0.52),
                    "away": round(ctx.get("predicted_total", 224) * 0.48),
                },
                "confidence": 0.6,
                "_source": "synthetic",
            }
            self._game_analysis_cache[game_key] = analysis
            return analysis

        prompt = ThinkingPhase.build_phase1_prompt(ctx)
        result = None

        # Try Claude Opus CLI first (best reasoning)
        opus_agent = self.registry.get("t1_claude_code_opus")
        if opus_agent and opus_agent.active:
            result = _call_claude_cli(
                self.pool, opus_agent, prompt, ThinkingPhase.PHASE_1_SYSTEM
            )
            self.run_stats["multiphase_calls"] += 1

        # Fallback: Gemini 2.5 Pro
        if not result:
            result = self.pool.call_llm(
                provider="google", prompt=prompt, model="gemini-2.5-pro",
                system=ThinkingPhase.PHASE_1_SYSTEM, max_tokens=800, temperature=0.2,
            )
            self.run_stats["multiphase_calls"] += 1

        # Fallback: Gemini 2.5 Flash
        if not result:
            result = self.pool.call_llm(
                provider="google", prompt=prompt, model="gemini-2.5-flash",
                system=ThinkingPhase.PHASE_1_SYSTEM, max_tokens=600, temperature=0.2,
            )
            self.run_stats["multiphase_calls"] += 1

        if not result:
            result = {
                "team_strengths": {},
                "key_factors": ["model predictions available"],
                "injury_impact": {},
                "model_agreement": ctx.get("model_confidence", "low"),
                "edge_opportunities": [],
                "predicted_score": {},
                "confidence": 0.3,
                "_source": "fallback",
            }
        else:
            result["_source"] = result.get("_source", "phase1_llm")
            result["_game_key"] = game_key

        self._game_analysis_cache[game_key] = result
        return result

    def _phase2_category_screening(self, game_analysis, ctx, game_key):
        # type: (dict, dict, str) -> List[dict]
        """Phase 2: Screen all bet categories for value. Returns top 20."""
        if self.dry_run:
            return [
                {"id": "ml_fg", "name": "Moneyline Full Game", "group": "moneyline",
                 "estimated_edge": 0.04, "confidence": 0.7},
                {"id": "sp_fg", "name": "Spread Full Game", "group": "spread",
                 "estimated_edge": 0.03, "confidence": 0.6},
                {"id": "tot_fg", "name": "Total Full Game", "group": "totals",
                 "estimated_edge": 0.025, "confidence": 0.55},
            ]

        screened = {}   # category_id -> best result dict

        all_cat_dicts = [
            {"id": c.id, "name": c.name, "group": c.group}
            for c in ALL_CATEGORIES
        ]
        chunk_size = 30
        for chunk_start in range(0, len(all_cat_dicts), chunk_size):
            chunk = all_cat_dicts[chunk_start:chunk_start + chunk_size]
            prompt = ThinkingPhase.build_phase2_prompt(game_analysis, chunk, ctx)

            result = None
            sonnet_agent = self.registry.get("t1_claude_code_sonnet")
            if sonnet_agent and sonnet_agent.active:
                result = _call_claude_cli(
                    self.pool, sonnet_agent, prompt, ThinkingPhase.PHASE_2_SYSTEM
                )
                self.run_stats["multiphase_calls"] += 1

            if not result:
                result = self.pool.call_llm(
                    provider="google", prompt=prompt, model="gemini-2.5-flash",
                    system=ThinkingPhase.PHASE_2_SYSTEM, max_tokens=800, temperature=0.2,
                )
                self.run_stats["multiphase_calls"] += 1

            if result:
                items = result if isinstance(result, list) else result.get("categories", [])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if not item.get("has_edge") or not item.get("category_id"):
                        continue
                    cid = item["category_id"]
                    item_conf = float(item.get("confidence", 0.5))
                    if cid in screened and item_conf <= screened[cid].get("confidence", 0):
                        continue
                    cat_obj = CATEGORY_BY_ID.get(cid)
                    if cat_obj:
                        screened[cid] = {
                            "id": cid,
                            "name": cat_obj.name,
                            "group": cat_obj.group,
                            "estimated_edge": float(item.get("estimated_edge", 0.03)),
                            "confidence": item_conf,
                            "reasoning": item.get("reasoning", ""),
                        }

        self.run_stats["phase2_screenings"] += len(screened)
        result_list = sorted(screened.values(),
                             key=lambda x: x["estimated_edge"], reverse=True)
        return result_list[:20]

    def _phase3_bet_decisions(self, screened_cats, game_analysis, ctx,
                              game_key, game, odds_entry):
        # type: (List[dict], dict, dict, str, dict, Optional[dict]) -> List[dict]
        """Phase 3: Deep bet decision for each screened category. Returns final bets."""
        if not screened_cats:
            return []

        bets = []

        def _decide_one(cat_info):
            prompt = ThinkingPhase.build_phase3_prompt(cat_info, game_analysis, ctx)
            result = None
            group = cat_info.get("group", "moneyline")

            if group in ("moneyline", "spread"):
                haiku_agent = self.registry.get("t1_claude_code_haiku")
                if haiku_agent and haiku_agent.active:
                    result = _call_claude_cli(
                        self.pool, haiku_agent, prompt, ThinkingPhase.PHASE_3_SYSTEM
                    )
            elif group in ("player_props", "exotic"):
                research_agent = self.registry.get("t2_claude_code_research")
                if research_agent and research_agent.active:
                    result = _call_claude_cli(
                        self.pool, research_agent, prompt, ThinkingPhase.PHASE_3_SYSTEM
                    )

            if not result:
                result = self.pool.call_llm(
                    provider="google", prompt=prompt, model="gemini-2.5-flash-thinking",
                    system=ThinkingPhase.PHASE_3_SYSTEM, max_tokens=512, temperature=0.2,
                )
            if not result:
                result = self.pool.call_llm(
                    provider="google", prompt=prompt, model="gemini-2.5-flash",
                    system=ThinkingPhase.PHASE_3_SYSTEM, max_tokens=400, temperature=0.2,
                )

            self.run_stats["multiphase_calls"] += 1
            return result, cat_info

        max_workers = min(10, len(screened_cats))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_decide_one, cat): cat for cat in screened_cats}
            for future in as_completed(futures, timeout=120):
                try:
                    outcome = future.result()
                    if not outcome:
                        continue
                    result, cat_info = outcome
                    if not result or not isinstance(result, dict):
                        continue
                    if not result.get("bet"):
                        continue

                    edge = float(result.get("edge", 0.03))
                    confidence = float(result.get("confidence", 0.5))
                    kelly_frac = float(result.get("kelly_fraction", 0.25))
                    side = str(result.get("side", "home"))

                    bet_odds = 1.909
                    if odds_entry and cat_info["group"] == "moneyline":
                        if "home" in side:
                            bet_odds = odds_entry.get("ml_home_dec", 1.91)
                        else:
                            bet_odds = odds_entry.get("ml_away_dec", 1.91)

                    paperclip = self.registry.get("t4_paperclip")
                    bankroll = paperclip.bankroll if paperclip else 10_000.0
                    stake = bankroll * kelly_criterion(0.5 + edge, bet_odds, kelly_frac)
                    stake = min(stake, bankroll * 0.10)

                    bets.append({
                        "game_key": game_key,
                        "category": cat_info["id"],
                        "direction": side,
                        "confidence": round(confidence, 4),
                        "edge_pct": round(edge * 100, 2),
                        "odds": round(bet_odds, 3),
                        "stake": round(max(stake, 0), 2),
                        "source": "multiphase_p3",
                        "reasoning": result.get("reasoning", ""),
                        "key_factor": result.get("key_factor", ""),
                        "_phase": 3,
                    })
                    self.run_stats["phase3_decisions"] += 1

                except Exception:
                    pass

        return bets

    # ===================================================================
    # STAGE 2: Anonymized Peer Review (Hermes)
    # ===================================================================
    def _stage2_peer_review(self, predictions: Dict[str, dict],
                            ctx: dict, game_key: str) -> dict:
        """
        Karpathy Council Stage 2: Hermes routes anonymized predictions
        for peer review. Returns consensus metrics.
        """
        if len(predictions) < 3:
            return {"consensus": "insufficient_data", "ml_agreement": 0.0,
                    "num_predictions": len(predictions)}

        # Aggregate votes
        ml_votes = {"home": 0, "away": 0}
        spread_votes = {"home": 0, "away": 0}
        total_votes = {"over": 0, "under": 0}
        confidence_sum = 0.0
        edge_values = []
        tier_breakdown = defaultdict(int)

        for pred in predictions.values():
            tier = pred.get("_agent_tier", "UNKNOWN")
            tier_breakdown[tier] += 1

            # Handle both tier1 (nested) and tier2/3 (flat) formats
            ml = pred.get("ml_fg", {})
            if isinstance(ml, dict):
                d = ml.get("direction", "")
                if d in ml_votes:
                    ml_votes[d] += 1
                conf = ml.get("confidence", 0)
                confidence_sum += conf
                edge = ml.get("edge_pct", 0)
                if edge:
                    edge_values.append(float(edge) if isinstance(edge, (int, float, str)) else 0)

            # Also handle bets list format from tier2
            for bet in pred.get("bets", []):
                if isinstance(bet, dict):
                    cat = bet.get("category", "")
                    d = bet.get("direction", "")
                    if cat == "ml_fg" and d in ml_votes:
                        ml_votes[d] += 1
                    elif "spread" in cat and d in spread_votes:
                        spread_votes[d] += 1
                    elif "total" in cat and d in total_votes:
                        total_votes[d] += 1

            sp = pred.get("spread_fg", {})
            if isinstance(sp, dict):
                d = sp.get("direction", "")
                if d in spread_votes:
                    spread_votes[d] += 1

            tt = pred.get("total_fg", {})
            if isinstance(tt, dict):
                d = tt.get("direction", "")
                if d in total_votes:
                    total_votes[d] += 1

        total_ml = sum(ml_votes.values()) or 1
        total_sp = sum(spread_votes.values()) or 1
        total_tt = sum(total_votes.values()) or 1

        ml_winner = max(ml_votes, key=ml_votes.get)
        spread_winner = max(spread_votes, key=spread_votes.get)
        total_winner = max(total_votes, key=total_votes.get)

        avg_edge = sum(edge_values) / len(edge_values) if edge_values else 0.0
        avg_conf = confidence_sum / total_ml if total_ml > 0 else 0.0

        review = {
            "ml_consensus": ml_winner,
            "ml_agreement": round(ml_votes[ml_winner] / total_ml, 4),
            "ml_votes": ml_votes,
            "spread_consensus": spread_winner,
            "spread_agreement": round(spread_votes[spread_winner] / total_sp, 4),
            "spread_votes": spread_votes,
            "total_consensus": total_winner,
            "total_agreement": round(total_votes[total_winner] / total_tt, 4),
            "total_votes": total_votes,
            "avg_confidence": round(avg_conf, 4),
            "avg_edge_pct": round(avg_edge, 3),
            "num_predictions": len(predictions),
            "tier_breakdown": dict(tier_breakdown),
        }

        # Hermes LLM-enhanced review (if available and not dry-run)
        hermes = self.registry.get("t4_hermes")
        if hermes and hermes.active and not self.dry_run:
            hermes_prompt = (
                f"PEER REVIEW for {ctx.get('away_team', ctx['away'])} @ "
                f"{ctx.get('home_team', ctx['home'])}:\n\n"
                f"ML votes: home={ml_votes['home']} away={ml_votes['away']} "
                f"(consensus: {ml_winner} at {review['ml_agreement']:.0%})\n"
                f"Spread votes: home={spread_votes['home']} away={spread_votes['away']}\n"
                f"Total votes: over={total_votes['over']} under={total_votes['under']}\n"
                f"Average edge: {avg_edge:.2f}% | Avg confidence: {avg_conf:.2f}\n"
                f"Agents: {len(predictions)} ({dict(tier_breakdown)})\n\n"
                f"Assess consensus quality. Flag suspicious unanimity or strong splits.\n"
                f"JSON only: {{\"quality\": 0-1, \"flags\": [], \"recommendation\": \"str\"}}"
            )
            hermes_result = self.pool.call_llm(
                provider=hermes.provider, prompt=hermes_prompt, model=hermes.model,
            )
            if hermes_result:
                review["hermes_assessment"] = hermes_result
                self.run_stats["tier_calls"][4] += 1

        print(f"    Consensus: ML={ml_winner}({review['ml_agreement']:.0%}) "
              f"Spread={spread_winner}({review['spread_agreement']:.0%}) "
              f"Total={total_winner}({review['total_agreement']:.0%}) "
              f"Edge={avg_edge:+.1f}% [{len(predictions)} agents]")

        return review

    # ===================================================================
    # STAGE 3: Chairman Synthesis (Oracle)
    # ===================================================================
    def _stage3_chairman_synthesis(self, predictions: Dict[str, dict],
                                   peer_review: dict, ctx: dict,
                                   game_key: str) -> dict:
        """Karpathy Council Stage 3: Oracle synthesizes all into final consensus."""
        oracle = self.registry.get("t4_oracle")

        # Always start with statistical synthesis as baseline
        stat_synth = self._statistical_synthesis(predictions, peer_review, ctx)

        if not oracle or not oracle.active or self.dry_run:
            return stat_synth

        # Build Oracle prompt (limit to top 30 predictions for context size)
        limited_preds = dict(list(predictions.items())[:30])
        prompt = get_meta_prompt(limited_preds, ctx)
        prompt += f"\n\nPEER REVIEW:\n{json.dumps(peer_review, indent=2, default=str)[:1500]}"

        result = self.pool.call_llm(
            provider=oracle.provider, prompt=prompt, model=oracle.model,
            max_tokens=1024, temperature=0.2,
        )
        self.run_stats["tier_calls"][4] += 1

        if result:
            # Merge Oracle LLM result with statistical baseline
            result["_source"] = "oracle_llm"
            result["_peer_review"] = peer_review
            # Ensure critical fields exist
            if "consensus_ml" not in result:
                result["consensus_ml"] = stat_synth["consensus_ml"]
            if "consensus_spread" not in result:
                result["consensus_spread"] = stat_synth["consensus_spread"]
            if "consensus_total" not in result:
                result["consensus_total"] = stat_synth["consensus_total"]
            return result

        return stat_synth

    def _statistical_synthesis(self, predictions: Dict[str, dict],
                                peer_review: dict, ctx: dict) -> dict:
        """Pure statistical synthesis (fallback when Oracle is unavailable).
        Uses vote agreement as primary confidence signal (more reliable than
        avg LLM-reported confidence, which is near-zero in synthetic mode).
        """
        ml_agree = peer_review.get("ml_agreement", 0.5)
        sp_agree = peer_review.get("spread_agreement", 0.5)
        tt_agree = peer_review.get("total_agreement", 0.5)
        avg_conf = peer_review.get("avg_confidence", 0.0)
        # Blend: vote agreement (80%) + LLM avg confidence (20%)
        ml_conf = ml_agree * 0.8 + min(avg_conf, 1.0) * 0.2
        sp_conf = sp_agree * 0.8 + min(avg_conf, 1.0) * 0.2
        tt_conf = tt_agree * 0.8 + min(avg_conf, 1.0) * 0.2
        return {
            "consensus_ml": {
                "direction": peer_review.get("ml_consensus", "home"),
                "confidence": round(ml_conf, 4),
                "agreement_pct": ml_agree,
            },
            "consensus_spread": {
                "direction": peer_review.get("spread_consensus", "home"),
                "confidence": round(sp_conf, 4),
                "agreement_pct": sp_agree,
            },
            "consensus_total": {
                "direction": peer_review.get("total_consensus", "over"),
                "confidence": round(tt_conf, 4),
                "agreement_pct": tt_agree,
            },
            "top_3_bets": [],
            "avg_edge_pct": peer_review.get("avg_edge_pct", 0),
            "num_agents": peer_review.get("num_predictions", 0),
            "narrative": "Statistical synthesis (aggregated agent votes)",
            "_source": "statistical",
            "_peer_review": peer_review,
        }

    # ===================================================================
    # BET GENERATION
    # ===================================================================
    def _generate_bets(self, synthesis: dict, ctx: dict,
                       odds_entry: Optional[dict], game_key: str,
                       game: Dict) -> List[dict]:
        """Convert consensus into actionable bets with Kelly sizing."""
        bets = []

        ml_c = synthesis.get("consensus_ml", {})
        sp_c = synthesis.get("consensus_spread", {})
        tt_c = synthesis.get("consensus_total", {})

        # --- ML BET --- (lower thresholds: 0.35 conf, 0.40 agree)
        ml_conf = ml_c.get("confidence", 0)
        ml_agree = ml_c.get("agreement_pct", 0)
        if ml_conf > 0.35 and ml_agree > 0.40:
            direction = ml_c.get("direction", "home")
            edge_pct = synthesis.get("avg_edge_pct", 0)
            edge = abs(float(edge_pct)) / 100.0 if edge_pct else 0.02
            bet_odds = 1.91
            if odds_entry:
                bet_odds = odds_entry["ml_home_dec"] if direction == "home" else odds_entry["ml_away_dec"]

            # Paperclip allocation
            paperclip = self.registry.get("t4_paperclip")
            base_bankroll = paperclip.bankroll if paperclip else 10_000
            stake = _sz_value_hunter_half_kelly(edge, bet_odds, base_bankroll)
            stake = min(stake, base_bankroll * 0.10)

            bets.append({
                "game_key": game_key,
                "category": "ml_fg",
                "direction": direction,
                "confidence": round(ml_conf, 4),
                "agreement": round(ml_agree, 4),
                "edge_pct": round(edge * 100, 2),
                "odds": round(bet_odds, 3),
                "stake": round(max(stake, 0), 2),
                "source": "consensus",
                "agents": synthesis.get("num_agents", 0),
            })

        # --- SPREAD BET ---
        sp_conf = sp_c.get("confidence", 0)
        sp_agree = sp_c.get("agreement_pct", 0)
        if (sp_conf > 0.35 and sp_agree > 0.40 and odds_entry and
                odds_entry.get("spread_home") is not None):
            direction = sp_c.get("direction", "home")
            stake = _sz_confidence_scaled(0.03, 1.909, 10_000)
            bets.append({
                "game_key": game_key,
                "category": "spread_fg",
                "direction": direction,
                "confidence": round(sp_conf, 4),
                "agreement": round(sp_agree, 4),
                "spread_line": odds_entry.get("spread_home"),
                "odds": 1.909,
                "stake": round(min(stake, 500), 2),
                "source": "consensus",
            })

        # --- TOTAL BET ---
        tt_conf = tt_c.get("confidence", 0)
        tt_agree = tt_c.get("agreement_pct", 0)
        if (tt_conf > 0.35 and tt_agree > 0.40):
            direction = tt_c.get("direction", "over")
            stake = _sz_confidence_scaled(0.02, 1.909, 10_000)
            bets.append({
                "game_key": game_key,
                "category": "total_fg",
                "direction": direction,
                "confidence": round(tt_conf, 4),
                "agreement": round(tt_agree, 4),
                "total_line": odds_entry.get("total"),
                "odds": 1.909,
                "stake": round(min(stake, 500), 2),
                "source": "consensus",
            })

        # --- Oracle's Top-3 bets ---
        for top_bet in synthesis.get("top_3_bets", []):
            if isinstance(top_bet, dict) and top_bet.get("category"):
                bets.append({
                    "game_key": game_key,
                    "category": top_bet["category"],
                    "direction": top_bet.get("direction", ""),
                    "confidence": top_bet.get("confidence", 0),
                    "edge_pct": top_bet.get("edge_pct", 0),
                    "odds": 1.909,
                    "stake": 50.0,
                    "source": "oracle_top3",
                })

        self.run_stats["total_bets"] += len(bets)
        return bets

    # ===================================================================
    # BET SETTLEMENT (retrolearning)
    # ===================================================================
    def _settle_bets(self, bets: List[dict], game: Dict):
        """Settle bets against actual game results."""
        for bet in bets:
            cat = bet.get("category", "")
            direction = bet.get("direction", "")
            won = None

            if cat == "ml_fg":
                if game.get("home_won") is not None:
                    won = (direction == "home" and game["home_won"]) or \
                          (direction == "away" and not game["home_won"])

            elif cat == "spread_fg":
                spread = bet.get("spread_line")
                if spread is not None and game.get("margin") is not None:
                    margin = game["margin"]
                    won = (direction == "home" and margin + spread > 0) or \
                          (direction == "away" and margin + spread < 0)

            elif cat == "total_fg":
                total_line = bet.get("total_line")
                if total_line and game.get("total_pts"):
                    won = (direction == "over" and game["total_pts"] > total_line) or \
                          (direction == "under" and game["total_pts"] < total_line)

            if won is not None:
                bet["settled"] = True
                bet["won"] = won
                stake = bet.get("stake", 0)
                odds = bet.get("odds", 1.909)
                bet["pnl"] = round(stake * (odds - 1) if won else -stake, 2)

    # ===================================================================
    # RETROLEARNING
    # ===================================================================
    def retrolearn(self, target_date: str):
        """Score past predictions against actual results and update agent weights."""
        print(f"\n{'=' * 80}")
        print(f"RETROLEARNING — Scoring predictions for {target_date}")
        print(f"{'=' * 80}")

        pred_file = _output_dated(target_date)
        if not pred_file.exists():
            print(f"No predictions found: {pred_file}")
            return

        with open(pred_file) as f:
            run_data = json.load(f)

        _, all_games = load_games_rich()
        date_results = {g["date"] + "_" + g["away"] + "@" + g["home"]: g
                        for g in all_games if g["date"] == target_date}

        if not date_results:
            print(f"No game results for {target_date}")
            return

        scored = 0
        wins = 0
        pnl_total = 0.0

        for bet in run_data.get("bets", []):
            game_key = bet.get("game_key", "")
            result = date_results.get(game_key)
            if not result:
                continue

            self._settle_bets([bet], result)
            if bet.get("settled"):
                scored += 1
                if bet.get("won"):
                    wins += 1
                pnl_total += bet.get("pnl", 0)

        # Update agent weights
        self.registry.update_weights_from_performance()
        deactivated = self.registry.deactivate_underperformers()

        # Save
        self.registry.save_state(str(AGENT_STATE_FILE))
        retro_data = {
            "date": target_date,
            "scored": scored,
            "wins": wins,
            "win_rate": round(wins / scored, 4) if scored > 0 else 0,
            "pnl": round(pnl_total, 2),
            "deactivated": deactivated,
            "bets": run_data.get("bets", []),
        }
        with open(RETROLEARN_FILE, "w") as f:
            json.dump(retro_data, f, indent=2, default=str)

        print(f"  Scored: {scored} bets | Wins: {wins} "
              f"({wins/scored*100:.1f}%)" if scored > 0 else "  No bets scored")
        print(f"  PnL: ${pnl_total:+,.2f}")
        if deactivated:
            print(f"  Deactivated {len(deactivated)} underperformers")

    # ===================================================================
    # OUTPUT + REPORTING
    # ===================================================================
    def _save_results(self, target_date: str):
        """Save full run results."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        TRADERS_DIR.mkdir(parents=True, exist_ok=True)
        PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

        self.iteration["total_api_calls"] = (
            self.iteration.get("total_api_calls", 0) + self.run_stats["api_calls_made"]
        )
        self.iteration["total_bets"] = (
            self.iteration.get("total_bets", 0) + self.run_stats["total_bets"]
        )
        _save_iteration(self.iteration)

        output = {
            "version": "v5_200_agents",
            "date": target_date,
            "iteration": self.iteration["iteration"],
            "run_stats": self.run_stats,
            "agent_count": len(self.registry.agents),
            "active_agents": len(self.registry.active_agents),
            "tier_summary": {
                "T1_premium": len(self.registry.tier1),
                "T2_free_power": len(self.registry.tier2),
                "T3_specialist": len(self.registry.tier3),
                "T4_meta": len(self.registry.tier4),
            },
            "games_processed": self.run_stats["games_processed"],
            "consensus": {k: _safe_serialize(v) for k, v in self.consensus.items()},
            "bets": self.bets,
            "api_pool_status": self.pool.get_capacity_report(),
            "top_agents": [a.to_dict() for a in self.registry.get_top_performers(20)],
            "leaderboard": self._build_leaderboard(),
        }

        # Save dated + latest
        for path in [_output_dated(target_date), OUTPUT_LATEST]:
            with open(path, "w") as f:
                json.dump(output, f, indent=2, default=str)

        # Save agent states
        self.registry.save_state(str(AGENT_STATE_FILE))

        # Save raw predictions
        pred_file = PREDICTIONS_DIR / f"predictions-{target_date}.json"
        pred_data = {}
        for aid, gpreds in self.predictions.items():
            pred_data[aid] = {k: _safe_serialize(v) for k, v in gpreds.items()}
        with open(pred_file, "w") as f:
            json.dump(pred_data, f, indent=2, default=str)

        print(f"\n  Saved: {OUTPUT_LATEST}")
        print(f"  Saved: {_output_dated(target_date)}")
        print(f"  Saved: {AGENT_STATE_FILE}")

    def _build_leaderboard(self) -> List[dict]:
        """Build a leaderboard from all agents."""
        board = []
        for agent in self.registry.active_agents:
            if agent.total_bets == 0 and agent.tier != AgentTier.META:
                continue
            board.append(agent.to_dict())
        board.sort(key=lambda x: x.get("roi", 0), reverse=True)
        for i, entry in enumerate(board, 1):
            entry["rank"] = i
        return board

    def _print_summary(self):
        """Print run summary."""
        stats = self.run_stats
        print(f"\n{'=' * 80}")
        print(f"TRADING FLOOR v5 — RUN SUMMARY (Iteration {self.iteration['iteration']})")
        print(f"{'=' * 80}")
        print(f"  Games processed:  {stats['games_processed']}")
        print(f"  Agents called:    {stats['agents_called']}")
        print(f"  API calls made:   {stats['api_calls_made']}")
        print(f"  API errors:       {stats['api_errors']}")
        print(f"  Total bets:       {stats['total_bets']}")
        print(f"  Tier calls:       T1={stats['tier_calls'][1]} T2={stats['tier_calls'][2]} "
              f"T3={stats['tier_calls'][3]} T4={stats['tier_calls'][4]}")
        print(f"  Cumulative:       {self.iteration.get('total_api_calls', 0)} calls, "
              f"{self.iteration.get('total_bets', 0)} bets across "
              f"{self.iteration['iteration']} iterations")
        print()

        # Consensus per game
        if self.consensus:
            print("GAME CONSENSUS:")
            for game_key, synth in self.consensus.items():
                ml = synth.get("consensus_ml", {})
                sp = synth.get("consensus_spread", {})
                tt = synth.get("consensus_total", {})
                print(f"  {game_key}:")
                print(f"    ML: {ml.get('direction','?')} "
                      f"({ml.get('confidence',0):.0%} conf, "
                      f"{ml.get('agreement_pct',0):.0%} agree)")
                print(f"    Spread: {sp.get('direction','?')} "
                      f"({sp.get('agreement_pct',0):.0%} agree)")
                print(f"    Total: {tt.get('direction','?')} "
                      f"({tt.get('agreement_pct',0):.0%} agree)")

        # Bets
        if self.bets:
            settled = [b for b in self.bets if b.get("settled")]
            print(f"\nBETS ({len(self.bets)} total, {len(settled)} settled):")
            for bet in self.bets:
                result_str = ""
                if bet.get("settled"):
                    result_str = f" -> {'WIN' if bet['won'] else 'LOSS'} (${bet.get('pnl', 0):+.0f})"
                print(f"  {bet.get('game_key',''):<35} {bet.get('category',''):<12} "
                      f"{bet.get('direction',''):<6} conf={bet.get('confidence',0):.0%} "
                      f"agree={bet.get('agreement',0):.0%} "
                      f"stake=${bet.get('stake',0):.0f}{result_str}")

            if settled:
                wins = sum(1 for b in settled if b.get("won"))
                pnl = sum(b.get("pnl", 0) for b in settled)
                print(f"\n  Results: {wins}/{len(settled)} wins "
                      f"({wins/len(settled)*100:.0f}%) | PnL: ${pnl:+,.0f}")

    def show_status(self):
        """Show fleet status without running predictions."""
        print("=" * 80)
        print("TRADING FLOOR v5 — FLEET STATUS")
        print("=" * 80)
        print()
        print(self.registry.summary())
        print()
        print(self.pool.summary())
        print()

        # Iteration tracking
        it = _load_iteration()
        print(f"Iterations: {it.get('iteration', 0)} | "
              f"Total API calls: {it.get('total_api_calls', 0):,} | "
              f"Total bets: {it.get('total_bets', 0):,}")

        # Top performers
        top = self.registry.get_top_performers(15)
        if top:
            print(f"\nTOP PERFORMERS:")
            print(f"  {'Agent':<30} {'Tier':<12} {'Provider':<12} "
                  f"{'Bets':>5} {'WR%':>6} {'ROI%':>7} {'Wt':>5}")
            print(f"  {'─' * 78}")
            for a in top:
                print(f"  {a.name:<30} {a.tier.name:<12} {a.provider:<12} "
                      f"{a.total_bets:>5} {a.win_rate*100:>5.1f}% "
                      f"{a.roi:>+6.1f}% {a.weight:>4.2f}")

        # API capacity
        report = self.pool.get_capacity_report()
        print(f"\nAPI CAPACITY:")
        for prov, info in sorted(report.items()):
            if info.get("keys", 0) > 0:
                print(f"  {prov:<15} {info['keys']} keys | "
                      f"{info.get('calls_remaining', '?'):>7} remaining | "
                      f"models: {', '.join(info.get('models', [])[:2])} | "
                      f"{info['status']}")

    def show_keys(self):
        """Check API key availability."""
        print("API Key Status:")
        print(f"{'─' * 70}")
        report = self.pool.get_capacity_report()
        total_keys = 0
        total_capacity = 0
        for prov, info in sorted(report.items()):
            keys = info.get("keys", 0)
            cap = info.get("max_daily", 0)
            status = info.get("status", "UNKNOWN")
            mark = "[OK]" if keys > 0 else "[  ]"
            models = ", ".join(info.get("models", [])[:2])
            free_tag = " (FREE)" if info.get("is_free") else " (PAID)"
            print(f"  {mark} {prov:<15} {keys} keys | {cap:>7,} RPD | "
                  f"{models:<35}{free_tag} [{status}]")
            total_keys += keys
            total_capacity += cap

        print(f"\n  TOTAL: {total_keys} keys | {total_capacity:,} calls/day capacity")
        print(f"  Agents: {len(self.registry.agents)} total, "
              f"{len(self.registry.active_agents)} active")


# ═══════════════════════════════════════════════════════════════════════════════
# CONTINUOUS MODE
# ═══════════════════════════════════════════════════════════════════════════════
_STOP_FLAG = False


def _signal_handler(sig, frame):
    global _STOP_FLAG
    print(f"\n[v5] Received signal {sig} — stopping after current iteration.")
    _STOP_FLAG = True


def run_continuous(dry_run: bool = False, max_iterations: int = 0,
                   delay: int = 300, games: int = 20):
    """Run trading floor continuously."""
    global _STOP_FLAG
    _signal.signal(_signal.SIGINT, _signal_handler)
    _signal.signal(_signal.SIGTERM, _signal_handler)

    floor = TradingFloorV5(dry_run=dry_run)
    count = 0

    while not _STOP_FLAG:
        count += 1
        if max_iterations > 0 and count > max_iterations:
            break

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            floor.run(today, games_per_iter=games)
        except Exception as e:
            print(f"[v5] Error: {e}")
            traceback.print_exc()

        if _STOP_FLAG:
            break

        # Push to git
        _push_results()

        if max_iterations == 0 or count < max_iterations:
            print(f"\n[v5] Waiting {delay}s before next iteration...")
            for _ in range(delay):
                if _STOP_FLAG:
                    break
                time.sleep(1)

    print(f"\n[v5] Stopped after {count} iterations.")


def _push_results():
    """Push results to git."""
    try:
        subprocess.run(
            ["git", "add",
             "data/arena/trading-floor-v5-*.json",
             "data/arena/agent-states-v5.json",
             "data/arena/predictions-v5/",
             "data/arena/traders-v5/",
             "data/arena/retrolearn-v5.json",
             "data/arena/trading-floor-v5-iteration.json"],
            cwd=str(ROOT), capture_output=True, timeout=10,
        )
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(ROOT), capture_output=True,
        )
        if diff.returncode != 0:
            it = _load_iteration()
            subprocess.run(
                ["git", "commit", "-m",
                 f"data: trading floor v5 iter {it['iteration']} — 200+ agent swarm"],
                cwd=str(ROOT), capture_output=True, timeout=15,
            )
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=str(ROOT), capture_output=True, timeout=30,
            )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
def _safe_serialize(obj):
    """Make objects JSON-serializable."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_serialize(v) for v in obj]
    if callable(obj):
        return "<function>"
    return obj


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Trading Floor v5 — 200+ AI Agent Swarm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python trading-floor-v5.py                      # Today's games, live API calls
  python trading-floor-v5.py --dry-run             # Synthetic predictions (no API)
  python trading-floor-v5.py --date 2026-04-03     # Specific date
  python trading-floor-v5.py --status              # Fleet status
  python trading-floor-v5.py --keys                # Check API keys
  python trading-floor-v5.py --retrolearn --retro-date 2026-04-03
  python trading-floor-v5.py --iterate --delay 300  # Continuous mode
""",
    )
    parser.add_argument("--date", type=str, default=None,
                        help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--status", action="store_true",
                        help="Show fleet status")
    parser.add_argument("--keys", action="store_true",
                        help="Check API key availability")
    parser.add_argument("--retrolearn", action="store_true",
                        help="Score past predictions")
    parser.add_argument("--retro-date", type=str, default=None,
                        help="Date to retrolearn (default: yesterday)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Synthetic predictions, no API calls")
    parser.add_argument("--iterate", action="store_true",
                        help="Continuous iteration mode")
    parser.add_argument("--delay", type=int, default=300,
                        help="Delay between iterations in seconds (default: 300)")
    parser.add_argument("--games", type=int, default=20,
                        help="Max games per iteration (default: 20)")
    parser.add_argument("--multiphase", action="store_true", default=True,
                        help="Enable 3-phase thinking (default: ON)")
    parser.add_argument("--no-multiphase", dest="multiphase", action="store_false",
                        help="Disable multi-phase thinking")
    parser.add_argument("--loop", action="store_true",
                        help="Continuous loop every 5-10 min (like a real trading desk)")

    # Also support legacy positional command
    parser.add_argument("command", nargs="?", default=None,
                        help="Legacy: run|iterate|status|keys|leaderboard")

    args = parser.parse_args()

    # Handle legacy commands
    if args.command:
        if args.command == "status":
            args.status = True
        elif args.command == "keys":
            args.keys = True
        elif args.command == "iterate":
            args.iterate = True
        elif args.command == "leaderboard":
            args.status = True

    target_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.status:
        floor = TradingFloorV5(dry_run=True)
        floor.show_status()

    elif args.keys:
        floor = TradingFloorV5(dry_run=True)
        floor.show_keys()

    elif args.retrolearn:
        retro_date = args.retro_date or (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).strftime("%Y-%m-%d")
        floor = TradingFloorV5(dry_run=False)
        floor.retrolearn(retro_date)

    elif args.iterate or args.loop:
        loop_delay = 300 if args.loop else args.delay  # 5 min for --loop
        run_continuous(
            dry_run=args.dry_run,
            delay=loop_delay,
            games=args.games,
        )

    else:
        floor = TradingFloorV5(dry_run=args.dry_run,
                               multiphase=args.multiphase)
        floor.run(target_date, games_per_iter=args.games)


if __name__ == "__main__":
    main()
