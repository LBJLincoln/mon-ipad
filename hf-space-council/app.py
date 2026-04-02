#!/usr/bin/env python3
"""
Trading Floor Council Loop — HuggingFace Space Edition
======================================================
Runs the full Trading Floor v8 Karpathy + Council loop continuously on HF Spaces.

Architecture:
  1. On startup: clones mon-ipad + nomos-nba-agent repos (needs GH_TOKEN secret)
  2. Every 5 minutes: runs a council iteration (backtest -> analyze -> council -> git push)
  3. Gradio dashboard shows live status, leaderboard, council decisions

This is a self-contained port of:
  - scripts/arena/trading-floor-v4.py (backtest + karpathy loop)
  - scripts/arena/trading-floor-council-loop.sh (council analysis)
"""

import json
import os
import sys
import csv
import math
import hashlib
import time
import threading
import subprocess
import traceback
import gradio as gr
from pathlib import Path
from datetime import datetime, timezone, date
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

GH_TOKEN = os.environ.get("GH_TOKEN", "")
REPO_URL = f"https://{GH_TOKEN}@github.com/LBJLincoln/mon-ipad.git" if GH_TOKEN else "https://github.com/LBJLincoln/mon-ipad.git"
NBA_REPO_URL = f"https://{GH_TOKEN}@github.com/LBJLincoln/nomos-nba-agent.git" if GH_TOKEN else "https://github.com/LBJLincoln/nomos-nba-agent.git"

WORKSPACE = Path("/tmp/council-workspace")
ROOT = WORKSPACE / "mon-ipad"
NBA_AGENT = WORKSPACE / "nomos-nba-agent"
DATA_DIR = ROOT / "data" / "arena"
TRADERS_DIR = DATA_DIR / "traders"
COUNCIL_DIR = DATA_DIR / "council"
ITERATION_FILE = DATA_DIR / "trading-floor-iteration.json"
KARPATHY_OUTPUT_FILE = DATA_DIR / "trading-floor-karpathy-output.json"
BEST_CONFIG_FILE = DATA_DIR / "best-config-toward-1M.json"

LOOP_DELAY_SECONDS = 300  # 5 minutes
MAX_ITERATIONS = 10000

# ============================================================================
# GLOBAL STATE (thread-safe via lock)
# ============================================================================

_state_lock = threading.Lock()
_state = {
    "status": "initializing",
    "council_iteration": 0,
    "tf_iteration": 0,
    "tf_generation": 0,
    "best_bankroll": 0.0,
    "best_trader": "none",
    "best_roi_pct": 0.0,
    "distance_to_1m": 100.0,
    "total_completed": 0,
    "total_failures": 0,
    "last_run_time": "never",
    "last_duration_s": 0,
    "leaderboard": [],
    "council_decisions": [],
    "council_history": [],
    "log_lines": [],
    "loop_running": False,
}


def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _state_lock:
        _state["log_lines"].append(line)
        # Keep last 200 lines
        if len(_state["log_lines"]) > 200:
            _state["log_lines"] = _state["log_lines"][-200:]
    print(line, flush=True)


def _update_state(**kwargs):
    with _state_lock:
        _state.update(kwargs)


def _get_state():
    with _state_lock:
        return dict(_state)


# ============================================================================
# GIT OPERATIONS
# ============================================================================

def clone_repos():
    """Clone or pull the required repos."""
    _log("Cloning/updating repos...")
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    for name, url, target in [
        ("mon-ipad", REPO_URL, ROOT),
        ("nomos-nba-agent", NBA_REPO_URL, NBA_AGENT),
    ]:
        if target.exists():
            _log(f"  Pulling {name}...")
            try:
                subprocess.run(
                    ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                    cwd=str(target), capture_output=True, timeout=60,
                )
                _log(f"  {name}: pulled")
            except Exception as e:
                _log(f"  {name}: pull failed ({e}), re-cloning...")
                subprocess.run(["rm", "-rf", str(target)], capture_output=True)
                subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(target)],
                    capture_output=True, timeout=120,
                )
                _log(f"  {name}: re-cloned")
        else:
            _log(f"  Cloning {name}...")
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url, str(target)],
                capture_output=True, timeout=120, text=True,
            )
            if result.returncode != 0:
                _log(f"  {name}: clone FAILED: {result.stderr[:200]}")
                raise RuntimeError(f"Failed to clone {name}")
            _log(f"  {name}: cloned")

    # Configure git identity for commits
    for cmd in [
        ["git", "config", "user.email", "council-bot@nomos42.ai"],
        ["git", "config", "user.name", "Council Bot"],
    ]:
        subprocess.run(cmd, cwd=str(ROOT), capture_output=True)


def git_pull():
    """Pull latest changes before each iteration."""
    for target in [ROOT, NBA_AGENT]:
        if target.exists():
            try:
                subprocess.run(
                    ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                    cwd=str(target), capture_output=True, timeout=60,
                )
            except Exception:
                pass


def git_commit_and_push(council_iter: int, tf_iter: int, tf_gen: int):
    """Stage, commit, and push results."""
    if not GH_TOKEN:
        _log("No GH_TOKEN -- skipping git push")
        return

    try:
        # Stage arena data
        subprocess.run(
            ["git", "add",
             "data/arena/trading-floor-karpathy-output.json",
             "data/arena/trading-floor-iteration.json",
             "data/arena/trading-floor-v4-latest.json",
             "data/arena/traders/",
             "data/arena/proposals/",
             "data/arena/council/",
             "data/departments/trading_floor/"],
            cwd=str(ROOT), capture_output=True, timeout=10,
        )
        # Also stage any dated files
        subprocess.run(
            ["git", "add", "data/arena/trading-floor-v4-*.json"],
            cwd=str(ROOT), capture_output=True, timeout=10,
        )

        # Check for changes
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(ROOT), capture_output=True,
        )
        if diff.returncode == 0:
            _log("No changes to commit")
            return

        msg = f"data: Trading Floor council iter {council_iter} (tf-iter {tf_iter}, gen {tf_gen})"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=str(ROOT), capture_output=True, timeout=15,
        )

        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(ROOT), capture_output=True, timeout=60, text=True,
        )
        if result.returncode == 0:
            _log("Git push: success")
        else:
            _log(f"Git push: failed ({result.stderr[:100]})")
    except Exception as e:
        _log(f"Git error: {e}")


# ============================================================================
# TRADING FLOOR v8 — SELF-CONTAINED BACKTEST ENGINE
# ============================================================================

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
    "first_half_sniper":   {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.15,
                            "cats": ["h1_ml_home", "h1_ml_away"]},
    "first_half_away":     {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.12,
                            "cats": ["h1_ml_away"]},
    "home_specialist":     {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.12,
                            "cats": ["ml_home", "spread_home", "h1_ml_home"]},
    "anti_martingale":     {"family": "anti_mart",    "min_edge": 0.02,  "max_pct": 0.20,  "cats": "all", "base_pct": 0.02},
    "drawdown_adjusted":   {"family": "drawdown_adj", "min_edge": 0.02,  "max_pct": 0.15,  "cats": "all", "dd_threshold": 0.15},
    "streak_momentum":     {"family": "streak",       "min_edge": 0.02,  "max_pct": 0.20,  "cats": "all", "streak_boost": 3},
}

ELIMINATED_STRATEGIES: Dict[str, Dict] = {
    "totals_expert": {"eliminated_at": "2026-03-31", "reason": "-72% ROI", "final_roi": -0.72},
    "spread_only":   {"eliminated_at": "2026-03-31", "reason": "-97% ROI", "final_roi": -0.97},
    "full_blast":    {"eliminated_at": "2026-03-31", "reason": "-100% ROI", "final_roi": -1.00},
}

ELIMINATED_POLITICAL_STRATEGIES: Dict[str, Dict] = {
    "SECTOR_ROTATE":           {"eliminated_at": "2026-03-31", "reason": "-75% ROI"},
    "DEFENSE_LONG_individual": {"eliminated_at": "2026-03-31", "reason": "-65% ROI"},
    "BILL_PASSES":             {"eliminated_at": "2026-03-31", "reason": "-64% ROI"},
}

BANKROLL_THRESHOLDS = {
    500:   {"max_pct_mult": 0.7, "min_edge_add": 0.01},
    1000:  {"max_pct_mult": 0.5, "min_edge_add": 0.02},
    5000:  {"max_pct_mult": 0.3, "min_edge_add": 0.03},
    10000: {"max_pct_mult": 0.2, "min_edge_add": 0.04},
}

TRADERS = {
    "gemini": {
        "name": "Gemini", "provider": "google", "personality": "analytical",
        "risk_tolerance": 0.60, "bankroll_nba": 100.0, "bankroll_political": 100_000.0,
        "preferred_models": ["consensus_ensemble", "tabicl", "stacking_meta"],
        "preferred_strategies": ["half_kelly", "confidence_scaled", "proportional_edge"],
        "pol_approach": "momentum", "etf_sectors": ["XLK", "QQQ", "SPY"],
    },
    "openrouter": {
        "name": "OpenRouter", "provider": "openrouter", "personality": "diversified",
        "risk_tolerance": 0.50, "bankroll_nba": 100.0, "bankroll_political": 100_000.0,
        "preferred_models": ["consensus_ensemble", "extra_trees", "lightgbm"],
        "preferred_strategies": ["quarter_kelly", "flat_2pct", "value_hunter"],
        "pol_approach": "sector_rotation", "etf_sectors": ["SPY", "IWM", "XLF", "XLE"],
    },
    "claude": {
        "name": "Claude", "provider": "anthropic", "personality": "conservative",
        "risk_tolerance": 0.40, "bankroll_nba": 100.0, "bankroll_political": 100_000.0,
        "preferred_models": ["tabicl", "consensus_ensemble", "catboost"],
        "preferred_strategies": ["half_kelly", "flat_1pct", "drawdown_adjusted"],
        "pol_approach": "mean_reversion", "etf_sectors": ["TLT", "GLD", "XLV"],
    },
    "codex": {
        "name": "Codex", "provider": "openai", "personality": "aggressive",
        "risk_tolerance": 0.70, "bankroll_nba": 100.0, "bankroll_political": 100_000.0,
        "preferred_models": ["xgboost", "lightgbm", "catboost"],
        "preferred_strategies": ["full_kelly", "streak_momentum", "anti_martingale", "proportional_edge"],
        "pol_approach": "event_driven", "etf_sectors": ["QQQ", "XLK", "XLI"],
    },
    "grok": {
        "name": "Grok", "provider": "xai", "personality": "contrarian",
        "risk_tolerance": 0.65, "bankroll_nba": 100.0, "bankroll_political": 100_000.0,
        "preferred_models": ["elo_baseline", "random_forest", "extra_trees"],
        "preferred_strategies": ["underdog_specialist", "dog_value_plus", "value_hunter"],
        "pol_approach": "pairs_trading", "etf_sectors": ["XLE", "GLD", "IWM", "TLT"],
    },
}

ETF_UNIVERSE = {
    "SPY": {"name": "S&P 500", "sector": "broad", "beta": 1.0},
    "QQQ": {"name": "NASDAQ 100", "sector": "technology", "beta": 1.2},
    "IWM": {"name": "Russell 2000", "sector": "small_cap", "beta": 1.1},
    "XLF": {"name": "Financials", "sector": "financials", "beta": 1.1},
    "XLE": {"name": "Energy", "sector": "energy", "beta": 1.3},
    "XLK": {"name": "Technology", "sector": "technology", "beta": 1.2},
    "XLV": {"name": "Healthcare", "sector": "healthcare", "beta": 0.8},
    "XLI": {"name": "Industrials", "sector": "industrials", "beta": 1.0},
    "GLD": {"name": "Gold", "sector": "commodity", "beta": 0.3},
    "TLT": {"name": "Long-term Treasuries", "sector": "bonds", "beta": -0.2},
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

OPTIMIZATION_TARGET = 1_000_000
ELIMINATION_ROI_THRESHOLD = -50.0
ELIMINATION_MIN_BETS = 20

STAT_KEYS = ['fg_pct', 'fg3_pct', 'ft_pct', 'reb', 'ast', 'tov', 'stl', 'blk', 'plus_minus']


# ============================================================================
# DATA LOADERS
# ============================================================================

def load_iteration() -> Dict:
    if ITERATION_FILE.exists():
        try:
            return json.loads(ITERATION_FILE.read_text())
        except Exception:
            pass
    return {"iteration": 0, "generation": 0}


def save_iteration(it: Dict):
    ITERATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    ITERATION_FILE.write_text(json.dumps(it, indent=2))


def load_best_config() -> Dict:
    if BEST_CONFIG_FILE.exists():
        try:
            return json.loads(BEST_CONFIG_FILE.read_text())
        except Exception:
            pass
    return {"best_bankroll": 100.0, "best_trader_id": None, "best_iteration": 0,
            "distance_to_1M_pct": 100.0, "history": [], "agent_configs": {}}


def save_best_config(config: Dict):
    BEST_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    BEST_CONFIG_FILE.write_text(json.dumps(config, indent=2))


def load_games_rich() -> Tuple[Dict, List[Dict]]:
    fp = NBA_AGENT / "data" / "historical" / "games-2025-26.json"
    if not fp.exists():
        _log(f"Games file not found: {fp}")
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
            "home_score": hs, "away_score": as_,
            "home_won": hs > as_,
            "home_stats": {k: h_data.get(k, 0) for k in STAT_KEYS},
            "away_stats": {k: a_data.get(k, 0) for k in STAT_KEYS},
        }
        results[(game_date, home, away)] = game_entry
        enriched.append(game_entry)
    enriched.sort(key=lambda g: g["date"])
    return results, enriched


def load_odds() -> Dict:
    fp = NBA_AGENT / "data" / "historical-odds" / "nba_2025-26_odds.csv"
    if not fp.exists():
        _log(f"Odds file not found: {fp}")
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
                if v > 0:
                    return v / 100.0 + 1
                if v < 0:
                    return 100.0 / abs(v) + 1
                return 2.0

            try:
                ml_home = parse_odds(row.get("moneyline_home", ""))
                ml_away = parse_odds(row.get("moneyline_away", ""))
                spread_s = row.get("spread_home", "").strip()
                total_s = row.get("total", "").strip()
                spread = float(spread_s) if spread_s else None
                total = float(total_s) if total_s else None
                if ml_home and ml_away:
                    odds[(game_date, home, away)] = {
                        "ml_home_dec": ml_home, "ml_away_dec": ml_away,
                        "spread_home": spread, "total": total,
                    }
            except (ValueError, TypeError):
                continue
    return odds


def load_political_signals() -> Dict:
    signals_file = Path("/tmp/council-workspace/nomos-political-alpha/data/social/social_signals_latest.json")
    if signals_file.exists():
        try:
            data = json.loads(signals_file.read_text())
            return data.get("signals", data)
        except Exception:
            pass
    return {}


# ============================================================================
# SIMULATION HELPERS (identical to trading-floor-v4.py)
# ============================================================================

def model_prob(model_name: str, implied_prob: float, seed_val: str, home_won: bool) -> float:
    brier = MODELS[model_name]["brier"]
    skill = max(0.0, 1.0 - brier / 0.25)
    h = int(hashlib.md5(f"{model_name}_{seed_val}".encode()).hexdigest()[:8], 16)
    variation = ((h % 1000) / 1000.0 - 0.5) * 0.06
    truth = 1.0 if home_won else 0.0
    pred = implied_prob + skill * (truth - implied_prob) * 0.5 + variation
    return max(0.05, min(0.95, pred))


def h1_result_from_hash(seed: str, home_won: bool) -> bool:
    h = int(hashlib.md5(f"h1_{seed}".encode()).hexdigest()[:4], 16)
    return home_won if (h % 100) < 52 else (not home_won)


def kelly_size(p: float, odds: float, fraction: float = 1.0) -> float:
    b = odds - 1.0
    if b <= 0:
        return 0.0
    edge = p * b - (1.0 - p)
    if edge <= 0:
        return 0.0
    return max(0.0, (edge / b) * fraction)


def compute_standings(all_games: List[Dict], up_to_date: str) -> Dict[str, Dict]:
    standings = defaultdict(lambda: {"w": 0, "l": 0, "pts_for": 0, "pts_against": 0})
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

    if standings:
        best_w = max(s["w"] for s in standings.values())
        best_l = min(s["l"] for s in standings.values() if s["w"] == best_w)
        for team, s in standings.items():
            total = s["w"] + s["l"]
            s["win_pct"] = round(s["w"] / total, 3) if total > 0 else 0.0
            s["gb"] = round(((best_w - s["w"]) + (s["l"] - best_l)) / 2, 1)
    return dict(standings)


def compute_team_form(all_games: List[Dict], team: str, up_to_date: str, window: int = 10) -> Dict:
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
    return {"games": len(last_n), "w": wins, "l": len(last_n) - wins}


def compute_all_model_predictions(model_names: list, implied: float, seed_val: str, home_won: bool) -> Dict:
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
        "best_model": max(preds, key=lambda m: abs(preds[m] - 0.5)),
        "outlier": max(preds, key=lambda m: abs(preds[m] - avg_p)),
    }


def get_bet_size(strat_name: str, prob: float, odds: float,
                 bankroll: float, comp_state: Optional[Dict] = None) -> float:
    cfg = STRATEGIES[strat_name]
    min_edge = cfg["min_edge"]
    max_pct = cfg["max_pct"]
    for threshold, adj in sorted(BANKROLL_THRESHOLDS.items()):
        if bankroll >= threshold:
            max_pct *= adj["max_pct_mult"]
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
    fam = cfg["family"]

    if fam == "kelly":
        bet = kelly_size(prob, odds, cfg["fraction"]) * bankroll
    elif fam == "flat":
        bet = bankroll * cfg["bet_pct"]
    elif fam == "confidence":
        conf = (abs(prob - 0.5) * 2) ** 2
        bet = conf * max_bet
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
        dd = 1.0 - bankroll / comp_state.get("peak", bankroll) if comp_state else 0.0
        scale = max(0.25, 1.0 - dd / cfg.get("dd_threshold", 0.15))
        bet = kelly_size(prob, odds, 0.5) * bankroll * scale
    elif fam == "streak":
        base = kelly_size(prob, odds, 0.25) * bankroll
        streak = comp_state.get("win_streak", 0) if comp_state else 0
        bet = base * 2 if streak >= cfg.get("streak_boost", 3) else base
    else:
        bet = bankroll * 0.02

    return min(max(bet, 0.0), max_bet)


# ============================================================================
# AGENT DECISION ENGINE
# ============================================================================

def agent_pick_model_for_game(trader_id: str, game_ctx: Dict) -> str:
    cfg = TRADERS[trader_id]
    personality = cfg["personality"]
    preferred = cfg["preferred_models"]
    models_info = game_ctx.get("models", {})
    preds = models_info.get("predictions", {})

    if personality == "analytical":
        implied = 1.0 / game_ctx["odds"]["ml_home_dec"] if game_ctx["odds"].get("ml_home_dec") else 0.5
        return max(preferred, key=lambda m: abs(preds.get(m, 0.5) - implied))
    elif personality == "diversified":
        h = int(hashlib.md5(f"{game_ctx['date']}_{game_ctx['home']}".encode()).hexdigest()[:4], 16)
        return preferred[h % len(preferred)]
    elif personality == "conservative":
        consensus = models_info.get("consensus", 0.5)
        return min(preferred, key=lambda m: abs(preds.get(m, 0.5) - consensus))
    elif personality == "aggressive":
        return max(preferred, key=lambda m: abs(preds.get(m, 0.5) - 0.5))
    elif personality == "contrarian":
        consensus = models_info.get("consensus", 0.5)
        return max(preferred, key=lambda m: abs(preds.get(m, 0.5) - consensus))
    return preferred[0]


def agent_pick_strategies_for_game(trader_id: str, game_ctx: Dict,
                                   bankroll: float, others: Dict) -> List[str]:
    cfg = TRADERS[trader_id]
    personality = cfg["personality"]
    preferred = [s for s in cfg["preferred_strategies"] if s not in ELIMINATED_STRATEGIES]
    if not preferred:
        preferred = ["half_kelly"]

    other_bankrolls = [s.get("nba_bankroll", 100.0) for s in others.values() if "nba_bankroll" in s]
    avg_other = sum(other_bankrolls) / len(other_bankrolls) if other_bankrolls else bankroll
    trailing = bankroll < avg_other * 0.9
    leading = bankroll > avg_other * 1.2

    model_disagreement = game_ctx.get("models", {}).get("disagreement", 0.05)
    high_confidence = model_disagreement < 0.03

    if personality == "aggressive":
        return preferred[:3] if high_confidence else [preferred[0]]
    elif personality == "conservative":
        return ["quarter_kelly"] if trailing else [preferred[0]]
    elif personality == "analytical":
        if high_confidence:
            return preferred[:2]
        return ["half_kelly" if not trailing else "confidence_scaled"]
    elif personality == "contrarian":
        return ["underdog_specialist", "dog_value_plus"] if not leading else ["value_hunter"]
    elif personality == "diversified":
        h = int(hashlib.md5(f"{game_ctx['date']}_{game_ctx['home']}".encode()).hexdigest()[:4], 16)
        return [preferred[h % len(preferred)]]
    return [preferred[0]]


def agent_decide_game_bets(trader_id: str, game_ctx: Dict, bankroll: float,
                           day_budget: float, others: Dict, comp_state: Dict) -> List[Dict]:
    cfg = TRADERS[trader_id]
    odds = game_ctx["odds"]
    result = game_ctx["_result"]
    home_won = result["home_won"]
    hs, as_ = result["home_score"], result["away_score"]
    total_pts = hs + as_
    seed_val = f"{game_ctx['date']}_{game_ctx['home']}_{game_ctx['away']}"

    chosen_model = agent_pick_model_for_game(trader_id, game_ctx)
    implied = 1.0 / odds["ml_home_dec"] if odds.get("ml_home_dec") else 0.5
    prob_home = model_prob(chosen_model, implied, seed_val, home_won)
    prob_away = 1.0 - prob_home

    h1_won = h1_result_from_hash(seed_val, home_won)
    h1_prob_home = model_prob(chosen_model, implied, f"h1_{seed_val}", h1_won)
    h1_prob_away = 1.0 - h1_prob_home

    chosen_strategies = agent_pick_strategies_for_game(trader_id, game_ctx, bankroll, others)

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

            bet_record = {
                "date": game_ctx["date"],
                "game": f"{game_ctx['home']} vs {game_ctx['away']}",
                "category": cat,
                "model_used": chosen_model,
                "strategy_used": strat_name,
                "model_prob": round(prob, 4),
                "edge_pct": round(edge * 100, 2),
                "bet_size": round(bet_size, 4),
                "odds": round(odds_val, 4),
                "outcome": "Win" if outcome else "Loss",
                "profit": round(profit, 4),
            }
            bets.append(bet_record)
            remaining_budget -= bet_size

    return bets


# ============================================================================
# NBA FULL-SEASON BACKTEST
# ============================================================================

def run_nba_backtest_for_agent(trader_id: str, matched: List,
                               others_states: Dict,
                               all_games: Optional[List[Dict]] = None) -> Dict:
    bankroll = TRADERS[trader_id]["bankroll_nba"]
    comp_state = {"last_won": False, "win_streak": 0, "peak": bankroll}
    total_bets = wins = losses = 0
    total_wagered = total_profit = 0.0
    peak_bankroll = bankroll
    max_drawdown = 0.0
    all_bets: List[Dict] = []
    eliminated_day = None
    day_results = []

    days = defaultdict(list)
    for item in matched:
        key, game_entry, odd = item
        days[key[0]].append((key, game_entry, odd))
    sorted_days = sorted(days.keys())

    if all_games is None:
        all_games = []

    for day_num, day_date in enumerate(sorted_days, 1):
        if bankroll <= 0:
            if eliminated_day is None:
                eliminated_day = day_num
            break

        day_games = days[day_date]
        standings = compute_standings(all_games, day_date) if all_games else {}
        day_bets_count = 0
        day_profit = 0.0

        for idx, (key, game_entry, odd) in enumerate(day_games):
            if bankroll <= 0:
                break

            home_won = game_entry["home_score"] > game_entry["away_score"]
            implied = 1.0 / odd["ml_home_dec"] if odd.get("ml_home_dec") else 0.5
            seed_val = f"{key[0]}_{key[1]}_{key[2]}"
            model_preds = compute_all_model_predictions(list(MODELS.keys()), implied, seed_val, home_won)

            game_ctx = {
                "date": key[0], "home": key[1], "away": key[2],
                "odds": odd,
                "models": model_preds,
                "home_standings": standings.get(key[1], {}),
                "away_standings": standings.get(key[2], {}),
                "home_form_L10": compute_team_form(all_games, key[1], key[0]),
                "away_form_L10": compute_team_form(all_games, key[2], key[0]),
                "_result": {
                    "home_score": game_entry["home_score"],
                    "away_score": game_entry["away_score"],
                    "home_won": home_won,
                },
            }

            games_remaining = max(1, len(day_games) - idx)
            game_budget = bankroll / games_remaining
            if TRADERS[trader_id]["personality"] == "aggressive":
                game_budget = bankroll * 0.5
            elif TRADERS[trader_id]["personality"] == "conservative":
                game_budget = bankroll * 0.15

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

                if bankroll <= 0:
                    eliminated_day = day_num
                    break

        day_results.append({
            "day": day_num, "date": day_date,
            "bets": day_bets_count,
            "profit": round(day_profit, 4),
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
        "trader_id": trader_id,
        "nba_bankroll": round(bankroll, 4),
        "nba_roi_pct": roi,
        "nba_sharpe": sharpe,
        "nba_bets": total_bets,
        "nba_wins": wins,
        "nba_losses": losses,
        "nba_wagered": round(total_wagered, 4),
        "nba_profit": round(total_profit, 4),
        "nba_peak": round(peak_bankroll, 4),
        "nba_max_drawdown": round(max_drawdown, 4),
        "nba_eliminated_day": eliminated_day,
        "nba_day_results": day_results,
        "nba_bets_history": all_bets[-500:],
    }


# ============================================================================
# POLITICAL BACKTEST
# ============================================================================

def compute_etf_signal(ticker: str, signals: Dict) -> Dict:
    if ticker in signals:
        sig = signals[ticker]
        strength = sig.get("signal_strength", 0.0)
        sentiment = sig.get("combined_sentiment", 0.0)
        if abs(strength) < 0.05:
            return {"direction": "neutral", "strength": 0.0, "reason": "no_signal"}
        direction = "long" if sentiment >= 0 else "short"
        return {"direction": direction, "strength": min(abs(strength), 1.0), "reason": "direct_signal"}

    etf_sector = ETF_UNIVERSE.get(ticker, {}).get("sector", "")
    related = POLITICAL_SECTOR_MAP.get(etf_sector, [])
    sector_sents = [signals[t].get("combined_sentiment", 0.0) for t in related if t in signals and t != ticker]
    if not sector_sents:
        return {"direction": "neutral", "strength": 0.0, "reason": "no_sector_data"}
    avg_sent = sum(sector_sents) / len(sector_sents)
    strength = min(abs(avg_sent), 1.0)
    if strength < 0.03:
        return {"direction": "neutral", "strength": 0.0, "reason": "weak_sector"}
    direction = "long" if avg_sent >= 0 else "short"
    return {"direction": direction, "strength": strength, "reason": "sector_aggregate"}


def run_political_backtest_for_agent(trader_id: str, signals: Dict, others_states: Dict) -> Dict:
    cfg = TRADERS[trader_id]
    bankroll = cfg["bankroll_political"]
    approach = cfg["pol_approach"]
    focus = cfg["etf_sectors"]
    risk = cfg["risk_tolerance"]
    max_pos = 0.10 * risk

    positions = []

    if approach == "momentum":
        for ticker in focus:
            sig = compute_etf_signal(ticker, signals)
            if sig["direction"] == "neutral":
                continue
            size = bankroll * max_pos * sig["strength"]
            positions.append({"ticker": ticker, "direction": sig["direction"],
                              "size_usd": round(size, 2), "signal_strength": round(sig["strength"], 4)})
    elif approach == "mean_reversion":
        for ticker in focus:
            sig = compute_etf_signal(ticker, signals)
            if sig["direction"] == "neutral" or sig["strength"] < 0.3:
                continue
            rev = "short" if sig["direction"] == "long" else "long"
            size = bankroll * max_pos * sig["strength"] * 0.5
            positions.append({"ticker": ticker, "direction": rev,
                              "size_usd": round(size, 2), "signal_strength": round(sig["strength"], 4)})
    elif approach == "event_driven":
        for ticker in focus:
            sig = compute_etf_signal(ticker, signals)
            if sig["strength"] < 0.2:
                continue
            size = min(bankroll * max_pos * 1.5 * sig["strength"], bankroll * 0.15)
            positions.append({"ticker": ticker, "direction": sig["direction"],
                              "size_usd": round(size, 2), "signal_strength": round(sig["strength"], 4)})
    elif approach == "pairs_trading":
        tickers_sigs = [(t, compute_etf_signal(t, signals)) for t in focus]
        longs = [(t, s) for t, s in tickers_sigs if s["direction"] == "long" and s["strength"] > 0.05]
        shorts = [(t, s) for t, s in tickers_sigs if s["direction"] == "short" and s["strength"] > 0.05]
        pair_size = bankroll * max_pos
        if longs:
            longs.sort(key=lambda x: -x[1]["strength"])
            t, s = longs[0]
            positions.append({"ticker": t, "direction": "long", "size_usd": round(pair_size, 2),
                              "signal_strength": round(s["strength"], 4)})
        if shorts:
            shorts.sort(key=lambda x: -x[1]["strength"])
            t, s = shorts[0]
            positions.append({"ticker": t, "direction": "short", "size_usd": round(pair_size, 2),
                              "signal_strength": round(s["strength"], 4)})
    elif approach == "sector_rotation":
        scored = [(t, compute_etf_signal(t, signals)) for t in focus]
        scored = [(t, s) for t, s in scored if s["direction"] == "long" and s["strength"] > 0.0]
        scored.sort(key=lambda x: -x[1]["strength"])
        total_str = sum(s["strength"] for _, s in scored) or 1.0
        allocation = bankroll * risk * 0.5
        for ticker, sig in scored[:3]:
            weight = sig["strength"] / total_str
            size = allocation * weight
            positions.append({"ticker": ticker, "direction": "long",
                              "size_usd": round(size, 2), "signal_strength": round(sig["strength"], 4)})

    simulated_pnl = 0.0
    for pos in positions:
        etf_beta = ETF_UNIVERSE.get(pos["ticker"], {}).get("beta", 1.0)
        expected_ret = pos["signal_strength"] * etf_beta * 0.005
        if pos["direction"] == "short":
            expected_ret *= -1
        simulated_pnl += pos["size_usd"] * expected_ret

    new_bankroll = bankroll + simulated_pnl
    roi = round((new_bankroll - bankroll) / bankroll * 100, 4) if bankroll > 0 else 0.0

    return {
        "trader_id": trader_id,
        "political_bankroll": round(new_bankroll, 2),
        "political_roi_pct": roi,
        "political_positions": positions,
        "political_approach": cfg["pol_approach"],
    }


# ============================================================================
# LEADERBOARD + ANALYSIS
# ============================================================================

def build_leaderboard(all_results: Dict) -> List[Dict]:
    board = []
    for trader_id, state in all_results.items():
        nba_roi = state.get("nba_roi_pct", 0.0)
        pol_roi = state.get("political_roi_pct", 0.0)
        combined = nba_roi + pol_roi * 0.1
        board.append({
            "rank": 0,
            "trader_id": trader_id,
            "name": state.get("name", trader_id),
            "provider": state.get("provider", ""),
            "personality": state.get("personality", ""),
            "nba_bankroll": state.get("nba_bankroll", 100.0),
            "nba_roi_pct": nba_roi,
            "nba_sharpe": state.get("nba_sharpe", 0.0),
            "nba_bets": state.get("nba_bets", 0),
            "nba_wins": state.get("nba_wins", 0),
            "nba_losses": state.get("nba_losses", 0),
            "political_bankroll": state.get("political_bankroll", 100_000.0),
            "political_roi_pct": pol_roi,
            "combined_score": round(combined, 4),
            "eliminated": state.get("nba_eliminated_day") is not None,
        })
    board.sort(key=lambda x: x["combined_score"], reverse=True)
    for i, entry in enumerate(board, 1):
        entry["rank"] = i
    return board


def analyze_strategy_performance() -> Dict[str, Dict]:
    strat_stats = defaultdict(lambda: {"bets": 0, "wins": 0, "losses": 0, "profit": 0.0, "traders_using": set()})
    for tid in TRADERS:
        sf = TRADERS_DIR / f"{tid}-state.json"
        if not sf.exists():
            continue
        try:
            full_state = json.loads(sf.read_text())
        except Exception:
            continue
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


def analyze_model_performance() -> Dict[str, Dict]:
    model_stats = defaultdict(lambda: {"bets": 0, "total_profit": 0.0, "wins": 0, "losses": 0, "traders_using": set()})
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
        stats["avg_daily_pnl"] = round(stats["total_profit"] / max(stats["bets"], 1), 4)
        total = stats["wins"] + stats["losses"]
        stats["win_rate_pct"] = round(stats["wins"] / total * 100, 1) if total > 0 else 0.0
    return dict(model_stats)


def analyze_category_performance() -> Dict[str, Dict]:
    cat_stats = defaultdict(lambda: {"bets": 0, "profit": 0.0, "wins": 0, "losses": 0})
    for tid in TRADERS:
        sf = TRADERS_DIR / f"{tid}-state.json"
        if not sf.exists():
            continue
        try:
            full_state = json.loads(sf.read_text())
        except Exception:
            continue
        for bet in full_state.get("nba_bets_history", []):
            cat = bet.get("category", "unknown")
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


def auto_eliminate_strategies(strat_perf: Dict[str, Dict]) -> List[Dict]:
    new_coffins = []
    for strat, stats in strat_perf.items():
        if strat in ELIMINATED_STRATEGIES or strat not in STRATEGIES:
            continue
        if stats["bets"] < ELIMINATION_MIN_BETS:
            continue
        if stats["roi_pct"] < ELIMINATION_ROI_THRESHOLD:
            coffin = {
                "strategy": strat,
                "eliminated_at": date.today().isoformat(),
                "reason": f"Auto-eliminated: {stats['roi_pct']:.0f}% ROI ({stats['bets']} bets)",
                "final_roi": round(stats["roi_pct"] / 100, 2),
            }
            new_coffins.append(coffin)
            ELIMINATED_STRATEGIES[strat] = coffin
            _log(f"COFFIN: Strategy '{strat}' eliminated: {stats['roi_pct']:.1f}% ROI")
    return new_coffins


def mutate_agent_preferences(board: List[Dict]) -> Dict[str, Dict]:
    if len(board) < 2:
        return {}

    winner = board[0]
    loser = board[-1]
    winner_id = winner["trader_id"]
    loser_id = loser["trader_id"]
    mutations = {}

    winner_sf = TRADERS_DIR / f"{winner_id}-state.json"
    if winner_sf.exists():
        try:
            ws = json.loads(winner_sf.read_text())
            strat_usage = defaultdict(int)
            for b in ws.get("nba_bets_history", []):
                strat_usage[b.get("strategy_used", "")] += 1
            if strat_usage:
                best_strat = max(strat_usage, key=strat_usage.get)
                loser_cfg = TRADERS[loser_id]
                if best_strat not in loser_cfg["preferred_strategies"] and best_strat in STRATEGIES:
                    old_prefs = list(loser_cfg["preferred_strategies"])
                    loser_cfg["preferred_strategies"] = [best_strat] + old_prefs[:2]
                    mutations[loser_id] = {
                        "type": "adopt_winner_strategy",
                        "from_trader": winner_id,
                        "adopted_strategy": best_strat,
                        "reason": f"{loser_id} adopts '{best_strat}' from {winner_id}",
                    }
                    _log(f"MUTATE: {loser_id} adopts '{best_strat}' from {winner_id}")
        except Exception:
            pass

    for entry in board[1:-1]:
        tid = entry["trader_id"]
        if abs(entry["nba_roi_pct"]) < 2.0:
            winner_models = TRADERS[winner_id]["preferred_models"]
            current_models = TRADERS[tid]["preferred_models"]
            if winner_models and winner_models[0] not in current_models:
                TRADERS[tid]["preferred_models"] = [winner_models[0]] + current_models[:2]
                mutations[tid] = {
                    "type": "adopt_winner_model",
                    "from_trader": winner_id,
                    "adopted_model": winner_models[0],
                    "reason": f"{tid} stagnant -- adopts model '{winner_models[0]}' from {winner_id}",
                }
                _log(f"MUTATE: {tid} adopts model '{winner_models[0]}' from {winner_id}")

    return mutations


# ============================================================================
# FULL COMPETITION + KARPATHY LOOP
# ============================================================================

def run_full_competition() -> Dict:
    it_data = load_iteration()
    it_data["iteration"] += 1
    _log(f"Trading Floor v8 -- iteration {it_data['iteration']}")

    _log("Loading games...")
    games, all_games_sorted = load_games_rich()
    odds = load_odds()
    _log(f"  Games: {len(games)}, Odds: {len(odds)}")

    matched = []
    for key in sorted(odds.keys()):
        if key in games:
            matched.append((key, games[key], odds[key]))
    _log(f"  Matched: {len(matched)}")

    unique_days = len({item[0][0] for item in matched})
    it_data["generation"] = it_data.get("generation", 0) + unique_days

    signals = load_political_signals()

    TRADERS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for trader_id in TRADERS:
        cfg = TRADERS[trader_id]
        others = {}
        for oid in TRADERS:
            if oid == trader_id:
                continue
            sf = TRADERS_DIR / f"{oid}-state.json"
            if sf.exists():
                try:
                    others[oid] = json.loads(sf.read_text())
                except Exception:
                    pass

        nba_result = run_nba_backtest_for_agent(trader_id, matched, others, all_games_sorted)
        pol_result = run_political_backtest_for_agent(trader_id, signals, others)

        state = {
            "trader_id": trader_id,
            "name": cfg["name"],
            "provider": cfg["provider"],
            "personality": cfg["personality"],
            "risk_tolerance": cfg["risk_tolerance"],
            **nba_result,
            **pol_result,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        (TRADERS_DIR / f"{trader_id}-state.json").write_text(json.dumps(state, indent=2))
        all_results[trader_id] = state

        _log(f"  {trader_id}: ${nba_result['nba_bankroll']:.2f} ROI {nba_result['nba_roi_pct']:+.1f}%")

    board = build_leaderboard(all_results)
    save_iteration(it_data)

    output = {
        "iteration": it_data["iteration"],
        "generation": it_data["generation"],
        "meta": {
            "version": "trading-floor-v8-hf",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": date.today().isoformat(),
            "traders": len(TRADERS),
            "nba_models": len(MODELS),
            "nba_strategies": len(STRATEGIES),
            "matched_games": len(matched),
        },
        "leaderboard": board,
        "traders": {
            tid: {k: v for k, v in s.items() if k not in ("nba_day_results", "nba_bets_history")}
            for tid, s in all_results.items()
        },
    }

    latest = DATA_DIR / "trading-floor-v4-latest.json"
    dated = DATA_DIR / f"trading-floor-v4-{date.today().isoformat()}.json"
    latest.write_text(json.dumps(output, indent=2))
    dated.write_text(json.dumps(output, indent=2))

    return output


def run_karpathy_loop() -> Dict:
    _log("=== KARPATHY LOOP START ===")

    result = run_full_competition()

    _log("Analyzing performance...")
    strat_perf = analyze_strategy_performance()
    model_perf = analyze_model_performance()
    cat_perf = analyze_category_performance()

    strat_ranked = sorted(
        [(s, p) for s, p in strat_perf.items() if p["bets"] >= 5],
        key=lambda x: x[1]["roi_pct"], reverse=True
    )
    model_ranked = sorted(model_perf.items(), key=lambda x: x[1]["avg_daily_pnl"], reverse=True)
    cat_ranked = sorted(
        [(c, p) for c, p in cat_perf.items() if p["bets"] >= 10],
        key=lambda x: x[1]["win_rate_pct"], reverse=True
    )

    new_coffins = auto_eliminate_strategies(strat_perf)
    mutations = mutate_agent_preferences(result.get("leaderboard", []))

    best_strategy = strat_ranked[0] if strat_ranked else ("none", {"roi_pct": 0, "bets": 0})
    best_model = model_ranked[0] if model_ranked else ("none", {"avg_daily_pnl": 0, "bets": 0})
    best_category = cat_ranked[0] if cat_ranked else ("none", {"win_rate_pct": 0, "bets": 0})

    # $1M optimization
    best_config = load_best_config()
    board = result.get("leaderboard", [])
    current_best_bankroll = max((e.get("nba_bankroll", 0) for e in board), default=100.0)
    current_best_trader = max(board, key=lambda e: e.get("nba_bankroll", 0))["trader_id"] if board else None
    distance_pct = round((1.0 - current_best_bankroll / OPTIMIZATION_TARGET) * 100, 4)

    improved = current_best_bankroll > best_config["best_bankroll"]
    if improved:
        _log(f"NEW RECORD: ${current_best_bankroll:,.2f} by {current_best_trader}")
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
        best_config["history"] = best_config["history"][-100:]
        save_best_config(best_config)

    karpathy_output = {
        "department": "trading_floor",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": result.get("iteration", 0),
        "generation": result.get("generation", 0),
        "status": "completed",
        "best_strategy": {"name": best_strategy[0], "roi_pct": best_strategy[1]["roi_pct"], "bets": best_strategy[1].get("bets", 0)},
        "best_model": {"name": best_model[0], "avg_daily_pnl": best_model[1]["avg_daily_pnl"], "bets": best_model[1].get("bets", 0)},
        "best_category": {"name": best_category[0], "win_rate_pct": best_category[1]["win_rate_pct"], "bets": best_category[1].get("bets", 0)},
        "strategy_rankings": [{"strategy": s, **p} for s, p in strat_ranked],
        "model_rankings": [{"model": m, **p} for m, p in model_ranked],
        "category_rankings": [{"category": c, **p} for c, p in cat_ranked],
        "new_eliminations": new_coffins,
        "all_eliminations": {"nba": ELIMINATED_STRATEGIES, "political": ELIMINATED_POLITICAL_STRATEGIES},
        "mutations": mutations,
        "optimization": {
            "target": OPTIMIZATION_TARGET,
            "current_best": round(current_best_bankroll, 2),
            "record_best": round(best_config["best_bankroll"], 2),
            "record_trader": best_config.get("best_trader_id"),
            "distance_to_1M_pct": distance_pct,
            "multiplier_needed": round(OPTIMIZATION_TARGET / max(current_best_bankroll, 1), 1),
            "improved_this_iteration": improved,
        },
        "leaderboard": result.get("leaderboard", []),
        "matched_games": result.get("meta", {}).get("matched_games", 0),
        "recommendations": [],
    }

    KARPATHY_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    KARPATHY_OUTPUT_FILE.write_text(json.dumps(karpathy_output, indent=2))

    dept_output = DATA_DIR.parent / "departments" / "trading_floor"
    dept_output.mkdir(parents=True, exist_ok=True)
    (dept_output / "karpathy-output.json").write_text(json.dumps(karpathy_output, indent=2))

    _log(f"Karpathy done: iter {result.get('iteration')}, best ${current_best_bankroll:,.0f} ({current_best_trader})")
    return karpathy_output


# ============================================================================
# COUNCIL ANALYSIS (port from council-loop.sh embedded Python)
# ============================================================================

def run_council_analysis(karpathy_output: Dict, council_iter: int) -> Dict:
    COUNCIL_DIR.mkdir(parents=True, exist_ok=True)

    strat_rankings = karpathy_output.get("strategy_rankings", [])
    top_strategies = strat_rankings[:3]
    bottom_strategies = strat_rankings[-3:] if len(strat_rankings) >= 3 else strat_rankings

    model_rankings = karpathy_output.get("model_rankings", [])
    cat_rankings = karpathy_output.get("category_rankings", [])
    best_categories = cat_rankings[:5]

    leaderboard = karpathy_output.get("leaderboard", [])
    best_trader = leaderboard[0] if leaderboard else {}
    worst_trader = leaderboard[-1] if leaderboard else {}

    best_bankroll = best_trader.get("nba_bankroll", 100.0)
    best_trader_id = best_trader.get("trader_id", "unknown")
    best_roi = best_trader.get("nba_roi_pct", 0.0)

    opt = karpathy_output.get("optimization", {})
    distance_to_1m = opt.get("distance_to_1M_pct", 100.0)

    # Read previous council for improvement tracking
    prev_best = None
    council_latest_path = COUNCIL_DIR / "council-latest.json"
    if council_latest_path.exists():
        try:
            prev_data = json.loads(council_latest_path.read_text())
            prev_best = prev_data.get("metrics", {}).get("best_bankroll")
        except Exception:
            pass

    improvement_since_last = 0.0
    if prev_best is not None and prev_best > 0:
        improvement_since_last = round(((best_bankroll - prev_best) / prev_best) * 100, 4)

    # Generate decisions
    mutations = []
    new_experiments = []
    eliminations = []

    if len(leaderboard) >= 2:
        winner_strats = []
        winner_models = []
        for sr in strat_rankings[:3]:
            if best_trader_id in sr.get("traders_using", []):
                winner_strats.append(sr.get("strategy", ""))
        for mr in model_rankings[:3]:
            if best_trader_id in mr.get("traders_using", []):
                winner_models.append(mr.get("model", ""))

        for loser in leaderboard[-2:]:
            loser_id = loser.get("trader_id", "unknown")
            if loser_id == best_trader_id:
                continue
            mutations.append({
                "agent": loser_id,
                "action": "adopt_winner_strategies",
                "from_agent": best_trader_id,
                "adopt_strategies": winner_strats[:2] if winner_strats else [s.get("strategy") for s in top_strategies[:2]],
                "adopt_models": winner_models[:2] if winner_models else [m.get("model") for m in model_rankings[:2]],
                "reason": f"{loser_id} (rank {loser.get('rank', '?')}) should learn from {best_trader_id} (rank 1)",
            })

    if top_strategies and len(model_rankings) >= 3:
        best_strat_name = top_strategies[0].get("strategy", "unknown")
        mid_models = [m.get("model") for m in model_rankings[2:5]]
        new_experiments.append({
            "type": "cross_pollination",
            "strategy": best_strat_name,
            "test_with_models": mid_models,
            "hypothesis": f"Top strategy '{best_strat_name}' may perform better with mid-tier models",
            "priority": 1,
        })

    if len(best_categories) >= 2:
        new_experiments.append({
            "type": "category_focus",
            "categories": [c.get("category") for c in best_categories[:2]],
            "expected_win_rate": round(sum(c.get("win_rate_pct", 0) for c in best_categories[:2]) / 2, 1),
            "hypothesis": "Focus bets on top-2 winning categories",
            "priority": 2,
        })

    for sr in bottom_strategies:
        roi = sr.get("roi_pct", 0)
        strat_name = sr.get("strategy", "")
        bets = sr.get("bets", 0)
        if roi < -20 and bets >= 10:
            eliminations.append({
                "strategy": strat_name,
                "roi_pct": roi,
                "bets": bets,
                "reason": f"Sustained negative ROI ({roi:+.1f}%) over {bets} bets",
            })

    if model_rankings:
        best_model = model_rankings[0]
        new_experiments.append({
            "type": "model_promotion",
            "model": best_model.get("model", "unknown"),
            "avg_daily_pnl": best_model.get("avg_daily_pnl", 0),
            "win_rate_pct": best_model.get("win_rate_pct", 0),
            "hypothesis": f"Prioritize {best_model.get('model')} in evolution -- top daily PnL",
            "priority": 1,
        })

    if distance_to_1m < 50:
        new_experiments.append({
            "type": "aggression_increase",
            "current_distance": distance_to_1m,
            "action": "increase Kelly fraction for top 2 traders",
            "hypothesis": f"Within {distance_to_1m:.1f}% of $1M -- increase position sizing",
            "priority": 1,
        })

    council_output = {
        "council_iteration": council_iter,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_iteration": karpathy_output.get("iteration", 0),
        "source_generation": karpathy_output.get("generation", 0),
        "analysis": {
            "top_strategies": [
                {"strategy": s.get("strategy", ""), "roi_pct": s.get("roi_pct", 0),
                 "win_rate_pct": s.get("win_rate_pct", 0), "bets": s.get("bets", 0),
                 "traders_using": s.get("traders_using", [])}
                for s in top_strategies
            ],
            "bottom_strategies": [
                {"strategy": s.get("strategy", ""), "roi_pct": s.get("roi_pct", 0),
                 "win_rate_pct": s.get("win_rate_pct", 0), "bets": s.get("bets", 0),
                 "traders_using": s.get("traders_using", [])}
                for s in bottom_strategies
            ],
            "model_rankings": [
                {"model": m.get("model", ""), "avg_daily_pnl": m.get("avg_daily_pnl", 0),
                 "win_rate_pct": m.get("win_rate_pct", 0), "bets": m.get("bets", 0)}
                for m in model_rankings
            ],
            "best_categories": [
                {"category": c.get("category", ""), "win_rate_pct": c.get("win_rate_pct", 0),
                 "roi_pct": c.get("roi_pct", 0), "bets": c.get("bets", 0)}
                for c in best_categories
            ],
            "leaderboard_summary": [
                {"rank": t.get("rank", 0), "trader_id": t.get("trader_id", ""),
                 "nba_bankroll": t.get("nba_bankroll", 0), "nba_roi_pct": t.get("nba_roi_pct", 0),
                 "nba_sharpe": t.get("nba_sharpe", 0)}
                for t in leaderboard
            ],
        },
        "decisions": {
            "mutations": mutations,
            "new_experiments": new_experiments,
            "eliminations": eliminations,
        },
        "metrics": {
            "best_bankroll": round(best_bankroll, 2),
            "best_trader": best_trader_id,
            "best_roi_pct": round(best_roi, 2),
            "distance_to_1m": round(distance_to_1m, 4),
            "improvement_since_last": improvement_since_last,
            "total_traders": len(leaderboard),
            "total_strategies_active": len(strat_rankings),
            "total_eliminations_all_time": (
                len(karpathy_output.get("all_eliminations", {}).get("nba", {}))
                + len(karpathy_output.get("all_eliminations", {}).get("political", {}))
            ),
            "matched_games": karpathy_output.get("matched_games", 0),
        },
    }

    # Write council output
    iter_file = COUNCIL_DIR / f"council-iter-{council_iter}.json"
    iter_file.write_text(json.dumps(council_output, indent=2))
    council_latest_path.write_text(json.dumps(council_output, indent=2))

    return council_output


# ============================================================================
# COUNCIL LOOP (single iteration)
# ============================================================================

def run_one_council_iteration() -> Dict:
    """Run a single council iteration: pull -> backtest -> analyze -> council -> push."""
    start_time = time.time()

    # Determine council iteration
    council_iter = 1
    council_latest = COUNCIL_DIR / "council-latest.json"
    if council_latest.exists():
        try:
            prev = json.loads(council_latest.read_text())
            council_iter = prev.get("council_iteration", 0) + 1
        except Exception:
            pass

    _log(f"--- Council Iteration {council_iter} ---")

    # Phase 1: Pull latest
    _log("Phase 1: Git pull...")
    git_pull()

    # Phase 2: Run karpathy loop
    _log("Phase 2: Karpathy loop (backtest + analyze + mutate)...")
    karpathy_output = run_karpathy_loop()

    # Phase 3: Council analysis
    _log("Phase 3: Council analysis...")
    council_output = run_council_analysis(karpathy_output, council_iter)

    # Phase 4: Git commit + push
    _log("Phase 4: Git commit + push...")
    tf_iter = karpathy_output.get("iteration", 0)
    tf_gen = karpathy_output.get("generation", 0)
    git_commit_and_push(council_iter, tf_iter, tf_gen)

    duration = time.time() - start_time
    _log(f"Council iteration {council_iter} complete in {duration:.1f}s")

    # Update global state
    metrics = council_output.get("metrics", {})
    leaderboard = council_output.get("analysis", {}).get("leaderboard_summary", [])
    decisions = council_output.get("decisions", {})

    _update_state(
        status="idle",
        council_iteration=council_iter,
        tf_iteration=tf_iter,
        tf_generation=tf_gen,
        best_bankroll=metrics.get("best_bankroll", 0),
        best_trader=metrics.get("best_trader", "none"),
        best_roi_pct=metrics.get("best_roi_pct", 0),
        distance_to_1m=metrics.get("distance_to_1m", 100),
        total_completed=_get_state()["total_completed"] + 1,
        last_run_time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        last_duration_s=round(duration, 1),
        leaderboard=leaderboard,
        council_decisions=decisions,
    )

    # Append to council history (keep last 50)
    with _state_lock:
        _state["council_history"].append({
            "iter": council_iter,
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "best": f"${metrics.get('best_bankroll', 0):,.0f}",
            "trader": metrics.get("best_trader", "?"),
            "duration": f"{duration:.0f}s",
            "mutations": len(decisions.get("mutations", [])),
            "experiments": len(decisions.get("new_experiments", [])),
        })
        if len(_state["council_history"]) > 50:
            _state["council_history"] = _state["council_history"][-50:]

    return council_output


# ============================================================================
# BACKGROUND LOOP
# ============================================================================

def background_council_loop():
    """Runs continuously in a background thread."""
    _update_state(loop_running=True, status="starting")

    try:
        _log("Initializing council loop...")
        clone_repos()
        _update_state(status="repos cloned")
    except Exception as e:
        _log(f"FATAL: Failed to clone repos: {e}")
        _update_state(status=f"error: {e}", loop_running=False)
        return

    consecutive_failures = 0
    max_consecutive = 5

    iteration = 0
    while iteration < MAX_ITERATIONS:
        iteration += 1
        _update_state(status="running")

        try:
            run_one_council_iteration()
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            _update_state(
                status=f"error: {e}",
                total_failures=_get_state()["total_failures"] + 1,
            )
            _log(f"ERROR: {e}")
            _log(traceback.format_exc())

            if consecutive_failures >= max_consecutive:
                _log(f"FATAL: {max_consecutive} consecutive failures -- stopping loop")
                _update_state(status="stopped (too many failures)", loop_running=False)
                return

        # Wait between iterations
        _update_state(status=f"waiting ({LOOP_DELAY_SECONDS}s)")
        for _ in range(LOOP_DELAY_SECONDS):
            time.sleep(1)

    _update_state(status="completed (max iterations)", loop_running=False)


# ============================================================================
# GRADIO UI
# ============================================================================

def get_status_markdown():
    s = _get_state()
    bankroll_str = f"${s['best_bankroll']:,.0f}" if s['best_bankroll'] >= 1000 else f"${s['best_bankroll']:.2f}"

    md = f"""# Trading Floor Council Loop

| Metric | Value |
|--------|-------|
| **Status** | `{s['status']}` |
| **Council Iteration** | {s['council_iteration']} |
| **TF Iteration** | {s['tf_iteration']} |
| **TF Generation** | {s['tf_generation']} |
| **Best Bankroll** | {bankroll_str} |
| **Best Trader** | {s['best_trader']} |
| **Best ROI** | {s['best_roi_pct']:+,.1f}% |
| **Distance to $1M** | {s['distance_to_1m']:.2f}% |
| **Completed** | {s['total_completed']} |
| **Failures** | {s['total_failures']} |
| **Last Run** | {s['last_run_time']} |
| **Last Duration** | {s['last_duration_s']}s |
| **Loop Active** | {'Yes' if s['loop_running'] else 'No'} |
"""
    return md


def get_leaderboard_markdown():
    s = _get_state()
    lb = s.get("leaderboard", [])
    if not lb:
        return "No leaderboard data yet. Waiting for first iteration..."

    md = "# Leaderboard\n\n"
    md += "| Rank | Trader | Bankroll | ROI | Sharpe |\n"
    md += "|------|--------|----------|-----|--------|\n"
    for entry in lb:
        bankroll = entry.get("nba_bankroll", 0)
        b_str = f"${bankroll:,.0f}" if bankroll >= 1000 else f"${bankroll:.2f}"
        md += f"| {entry.get('rank', '?')} | {entry.get('trader_id', '?')} | {b_str} | {entry.get('nba_roi_pct', 0):+,.1f}% | {entry.get('nba_sharpe', 0):.3f} |\n"

    return md


def get_decisions_markdown():
    s = _get_state()
    decisions = s.get("council_decisions", {})
    if not decisions:
        return "No council decisions yet. Waiting for first iteration..."

    md = "# Council Decisions\n\n"

    mutations = decisions.get("mutations", [])
    md += f"## Mutations ({len(mutations)})\n\n"
    for m in mutations:
        md += f"- **{m.get('agent', '?')}**: {m.get('action', '?')} from {m.get('from_agent', '?')}\n"
        md += f"  - Strategies: {', '.join(m.get('adopt_strategies', []))}\n"
        md += f"  - Models: {', '.join(m.get('adopt_models', []))}\n"
        md += f"  - Reason: {m.get('reason', '')}\n\n"

    experiments = decisions.get("new_experiments", [])
    md += f"## Experiments ({len(experiments)})\n\n"
    for e in experiments:
        md += f"- **{e.get('type', '?')}**: {e.get('hypothesis', '')}\n"
        md += f"  - Priority: {e.get('priority', '?')}\n\n"

    elims = decisions.get("eliminations", [])
    md += f"## Eliminations ({len(elims)})\n\n"
    for el in elims:
        md += f"- **{el.get('strategy', '?')}**: {el.get('reason', '')}\n\n"

    return md


def get_history_markdown():
    s = _get_state()
    history = s.get("council_history", [])
    if not history:
        return "No history yet. Waiting for first iteration..."

    md = "# Council History\n\n"
    md += "| Iter | Time | Best | Trader | Duration | Mutations | Experiments |\n"
    md += "|------|------|------|--------|----------|-----------|-------------|\n"
    for h in reversed(history):
        md += f"| {h.get('iter', '?')} | {h.get('time', '?')} | {h.get('best', '?')} | {h.get('trader', '?')} | {h.get('duration', '?')} | {h.get('mutations', 0)} | {h.get('experiments', 0)} |\n"

    return md


def get_logs_text():
    s = _get_state()
    return "\n".join(s.get("log_lines", ["No logs yet..."]))


def run_manual_iteration():
    """Triggered by the button click."""
    _update_state(status="manual run")
    try:
        if not ROOT.exists():
            clone_repos()
        result = run_one_council_iteration()
        return "Manual iteration completed successfully."
    except Exception as e:
        _log(f"Manual run error: {e}")
        return f"Error: {e}"


# Build the Gradio app
with gr.Blocks(
    title="Nomos42 Trading Floor Council",
    theme=gr.themes.Base(primary_hue="purple"),
) as demo:
    gr.Markdown("# Nomos42 Trading Floor Council Loop")
    gr.Markdown("*Continuous Karpathy + Council pattern for 5-AI NBA trading competition*")

    with gr.Row():
        with gr.Column(scale=2):
            status_display = gr.Markdown(get_status_markdown, every=10)
        with gr.Column(scale=1):
            run_btn = gr.Button("Run Council Iteration", variant="primary", size="lg")
            run_output = gr.Textbox(label="Manual Run Output", lines=2)

    with gr.Tabs():
        with gr.Tab("Leaderboard"):
            leaderboard_display = gr.Markdown(get_leaderboard_markdown, every=15)

        with gr.Tab("Council Decisions"):
            decisions_display = gr.Markdown(get_decisions_markdown, every=15)

        with gr.Tab("History"):
            history_display = gr.Markdown(get_history_markdown, every=15)

        with gr.Tab("Logs"):
            logs_display = gr.Textbox(
                get_logs_text,
                every=5,
                label="Live Logs",
                lines=25,
                max_lines=30,
                interactive=False,
            )

    run_btn.click(fn=run_manual_iteration, outputs=run_output)


# Start background loop
_log("Starting background council loop thread...")
loop_thread = threading.Thread(target=background_council_loop, daemon=True)
loop_thread.start()

# Launch Gradio
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
else:
    # HF Spaces auto-launches when it imports the `demo` object
    pass
