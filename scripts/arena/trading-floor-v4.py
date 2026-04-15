#!/usr/bin/env python3
"""
Trading Floor v9 — Game-Level Learning + Cross-Repo Iterative Engine
=====================================================================
5 AI agents (Gemini, OpenRouter, Claude, Codex, Grok) compete on:
  1. NBA betting: Choose strategy from all model predictions
  2. Political ETF trading: Trade based on political signals

v8 features retained from prior version:
  - Cross-repo integration: reads karpathy outputs from all satellite repos
  - Continuous iteration mode: `iterate` command loops forever
  - Cron-activated: every 4h, runs full analysis + mutation + next iteration
  - All repos synchronized: mon-ipad pilots nomos-nba-agent + nomos-political-alpha + rgwa
  - Guardian cross-pollination integrated into each iteration
  - $1M fitness tracking with generational improvement history

Inherits v5 data structures (11 models, 22 strategies, 16 bet categories,
per-game decisions, structured justifications, season documents).
"""

import json, os, sys, csv, math, hashlib, time, signal as _signal, subprocess, random
from pathlib import Path
from datetime import datetime, timezone, date
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

ROOT        = Path(__file__).resolve().parent.parent.parent

# ── REAL LLM AGENTS ──────────────────────────────────────────────────────────
# Import the real LLM decision engine. When available, agents make actual API
# calls to reason about each game. Falls back to hash-based simulation if missing.
_LLM_AGENTS_AVAILABLE = False
try:
    from llm_agents import agent_llm_decide, get_llm_stats, AGENT_SYSTEM_PROMPTS
    _LLM_AGENTS_AVAILABLE = True
    print("[TRADING FLOOR] LLM agents loaded — REAL reasoning enabled")
except ImportError:
    print("[TRADING FLOOR] llm_agents not available — using hash simulation fallback")

# ── SOTA TECHNIQUES (10 papers — P1-P10) ────────────────────────────────────
# Import lazily so the trading floor still runs if the module is missing.
_SOTA_AVAILABLE = False
try:
    from sota_techniques import (  # type: ignore
        SOTAEnhancer,
        apply_heterogeneous_objective,
        apply_coherence_gate,
        compute_agent_brier,
        compute_brier_weights,
        apply_brier_weight,
        detect_debate_trigger,
        resolve_debate,
        run_belief_market,
        opinion_dynamics_converge,
        detect_whale,
        apply_whale_dampening,
        build_chart_context,
        discover_correlations,
        apply_correlation_boost,
        AGENT_OBJECTIVES,
    )
    _SOTA_AVAILABLE = True
except Exception as _sota_err:
    pass

# ── OASIS ADAPTER (social discussion → per-trader biases) ────────────────────
# Import lazily so the trading floor still runs if the adapter is missing.
_OASIS_ADAPTER_AVAILABLE = False
try:
    sys.path.insert(0, str(ROOT / "scripts" / "arena"))
    from oasis_adapter import (  # type: ignore
        load_oasis_context,
        oasis_kelly_modifier,
        oasis_prob_nudge,
    )
    _OASIS_ADAPTER_AVAILABLE = True
except Exception as _oasis_import_err:
    # Define no-op stubs so the rest of the code can call these unconditionally
    def load_oasis_context(target_date=None):  # type: ignore[misc]
        return {}
    def oasis_kelly_modifier(trader_id, oasis_ctx):  # type: ignore[misc]
        return 1.0
    def oasis_prob_nudge(trader_id, oasis_ctx, base_prob):  # type: ignore[misc]
        return base_prob

# ── DMAD: Diverse Multi-Agent Debate (ICLR 2025) ─────────────────────────────
# Import lazily so the floor still runs if the module is missing.
_DMAD_AVAILABLE = False
try:
    from dmad_profiles import (  # type: ignore
        filter_nba_context,
        filter_political_signals,
        check_nba_consensus,
        check_political_consensus,
        compute_dmad_divergence,
        NBA_DMAD_PROFILES,
        POLITICAL_DMAD_PROFILES,
        CONSENSUS_DAMPING,
        CONSENSUS_THRESHOLD,
    )
    _DMAD_AVAILABLE = True
except Exception as _dmad_import_err:
    # No-op stubs — floor runs normally without DMAD filtering
    def filter_nba_context(ctx, trader_id): return ctx  # type: ignore[misc]
    def filter_political_signals(sigs, evts, trader_id): return sigs, evts  # type: ignore[misc]
    def check_nba_consensus(decisions, key): return {"consensus": False, "damping_factor": 1.0}  # type: ignore[misc]
    def check_political_consensus(positions, ticker): return {"consensus": False, "damping_factor": 1.0}  # type: ignore[misc]
    def compute_dmad_divergence(decisions): return {"divergence": 0.0, "consensus_events": 0, "healthy": True}  # type: ignore[misc]
    NBA_DMAD_PROFILES = {}  # type: ignore[assignment]
    POLITICAL_DMAD_PROFILES = {}  # type: ignore[assignment]
    CONSENSUS_DAMPING = 0.60
    CONSENSUS_THRESHOLD = 3

# ── ITERATION / GENERATION TRACKING ──────────────────────────────────────────
# Incremented each run; generation tracks game-day count
_ITERATION_FILE = ROOT / 'data' / 'arena' / 'trading-floor-iteration.json'

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

# ── ATLAS-GIC DARWINIAN WEIGHTS (Cycle 13 — github.com/chrisworsey55/atlas-gic) ─
# Per-trader allocation multiplier compounded daily by darwin_weights.py:
#   top quartile  → x1.05
#   bottom quart. → x0.95
#   middle ranks  → x1.00
# Bounded [0.30, 2.50]. Drives kelly_adj ⇒ winners get more capital, losers fade
# gracefully without elimination. 4 days/yr published lift +22% on 16/54 traders.
_DARWIN_FILE   = ROOT / 'data' / 'arena' / 'trader-darwin-weights.json'
_DARWIN_MIN_W  = 0.30
_DARWIN_MAX_W  = 2.50

def _load_darwin_weights() -> Dict[str, float]:
    """Load per-trader Darwinian weights. Returns {trader_id: weight} mapping.
    Missing file or unparseable JSON ⇒ all traders get neutral 1.0."""
    if not _DARWIN_FILE.exists():
        return {}
    try:
        raw = json.loads(_DARWIN_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    out: Dict[str, float] = {}
    for tid, entry in (raw.get("traders") or {}).items():
        try:
            w = float(entry.get("weight", 1.0))
        except (TypeError, ValueError):
            w = 1.0
        out[tid] = max(_DARWIN_MIN_W, min(_DARWIN_MAX_W, w))
    return out

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

NBA_AGENT   = ROOT.parent / 'nomos-nba-agent'
POLITICAL   = ROOT.parent / 'nomos-political-alpha'
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
# TRADER POOL — refactored 2026-04-07 from paid APIs (Gemini/Grok/OpenAI/OpenRouter)
# to FREE HF models. We have 4 HF accounts (HF_TOKEN, HF_TOKEN_NBA/3, HF_TOKEN_COUNCILS)
# so all of these are reachable via the HF Inference Router with no per-request cost.
# Dict KEYS preserved (gemini/openrouter/claude/codex/grok) so existing state files
# under data/arena/traders/{key}-state.json keep accumulating bankroll history.
# Only `name` and `provider` change — they are display labels for the dashboard.
TRADERS = {
    "gemini": {  # Gemma Analyst — google:gemini-2.5-flash primary (diversified 2026-04-12)
        "name":               "Gemma Analyst",
        "provider":           "google:gemini-2.5-flash",
        "personality":        "analytical",
        "risk_tolerance":     0.60,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["consensus_ensemble", "tabicl", "stacking_meta"],
        "preferred_strategies": ["half_kelly", "confidence_scaled", "proportional_edge"],
        "pol_approach":       "momentum",
        "etf_sectors":        ["XLK", "QQQ", "SPY"],
    },
    "openrouter": {  # Qwen Strategist — cerebras:qwen-3-235b primary
        "name":               "Qwen Strategist",
        "provider":           "cerebras:qwen-3-235b-a22b-instruct-2507",
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
    "claude": {  # Claude Sentinel — cerebras:llama3.3-70b (was anthropic_cli, swapped for GH Actions compat)
        "name":               "Claude Sentinel",
        "provider":           "cerebras:llama3.3-70b",
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
    "codex": {  # Llama Vanguard — openrouter:llama-3.3-70b free tier (diversified 2026-04-12)
        "name":               "Llama Vanguard",
        "provider":           "openrouter:meta-llama/llama-3.3-70b-instruct:free",
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
    "grok": {  # Mistral Maverick — cerebras:llama3.1-8b primary (kept on cerebras)
        "name":               "Mistral Maverick",
        "provider":           "cerebras:llama3.1-8b",
        "personality":        "contrarian",
        "risk_tolerance":     0.65,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["elo_baseline", "random_forest", "extra_trees"],
        "preferred_strategies": ["underdog_specialist", "dog_value_plus", "value_hunter"],
        "pol_approach":       "pairs_trading",
        "etf_sectors":        ["XLE", "GLD", "IWM", "TLT"],
    },
    # ── NEW TRADERS (expanded roster Apr 2026) ───────────────────────────────
    # 5 additional agents for genuine epistemic diversity per DMAD + Prediction Arena papers.
    # Each agent has a structurally unique data view, strategy, and objective function.
    "deepseek": {  # DeepSeek Quant — cerebras:deepseek-r1-distill-llama-70b
        "name":               "DeepSeek Quant",
        "provider":           "cerebras:deepseek-r1-distill-llama-70b",
        "personality":        "quantitative",
        "risk_tolerance":     0.55,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["xgboost", "catboost", "consensus_ensemble"],
        "preferred_strategies": ["half_kelly", "proportional_edge", "flat_2pct"],
        "pol_approach":       "statistical_arb",
        "etf_sectors":        ["SPY", "QQQ", "XLF", "IWM"],
    },
    "phi": {  # Phi Theorist — openrouter:microsoft/phi-4:free
        "name":               "Phi Theorist",
        "provider":           "openrouter:microsoft/phi-4:free",
        "personality":        "theoretical",
        "risk_tolerance":     0.35,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["tabicl", "extra_trees", "random_forest"],
        "preferred_strategies": ["quarter_kelly", "drawdown_adjusted", "flat_1pct"],
        "pol_approach":       "safe_haven",
        "etf_sectors":        ["TLT", "GLD", "XLV"],
    },
    "cohere": {  # Command Tactician — cohere:command-r-plus (via COHERE_API_KEY)
        "name":               "Command Tactician",
        "provider":           "cohere:command-r-plus",
        "personality":        "tactical",
        "risk_tolerance":     0.60,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["lightgbm", "xgboost", "consensus_ensemble"],
        "preferred_strategies": ["value_hunter", "streak_momentum", "half_kelly"],
        "pol_approach":       "momentum",
        "etf_sectors":        ["XLK", "XLI", "QQQ", "SPY"],
    },
    "gemma": {  # Gemma Arbitrageur — google:gemma-3-27b (via HF free inference)
        "name":               "Gemma Arbitrageur",
        "provider":           "hf:google/gemma-3-27b-it",
        "personality":        "arbitrage",
        "risk_tolerance":     0.75,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["catboost", "tabnet", "xgboost"],
        "preferred_strategies": ["full_kelly", "anti_martingale", "dog_value_plus"],
        "pol_approach":       "event_driven",
        "etf_sectors":        ["XLE", "XLK", "IWM", "QQQ"],
    },
    "mixtral": {  # Mixtral Ensemble — cerebras:llama-4-scout-17b-16e-instruct
        "name":               "Mixtral Ensemble",
        "provider":           "cerebras:llama-4-scout-17b-16e-instruct",
        "personality":        "ensemble",
        "risk_tolerance":     0.50,
        "bankroll_nba":       100.0,
        "bankroll_political": 100_000.0,
        "preferred_models":   ["consensus_ensemble", "stacking_meta", "extra_trees"],
        "preferred_strategies": ["flat_2pct", "confidence_scaled", "quarter_kelly"],
        "pol_approach":       "sector_rotation",
        "etf_sectors":        ["SPY", "XLF", "XLE", "TLT"],
    },
}

# ── POLITICAL / ETF UNIVERSE ─────────────────────────────────────────────────
ETF_UNIVERSE = {
    # Broad market
    "SPY":  {"name": "S&P 500",              "sector": "broad",        "beta": 1.0,  "type": "etf"},
    "QQQ":  {"name": "NASDAQ 100",           "sector": "technology",   "beta": 1.2,  "type": "etf"},
    "IWM":  {"name": "Russell 2000",         "sector": "small_cap",    "beta": 1.1,  "type": "etf"},
    # Sector ETFs
    "XLF":  {"name": "Financials",           "sector": "financials",   "beta": 1.1,  "type": "etf"},
    "XLE":  {"name": "Energy",               "sector": "energy",       "beta": 1.3,  "type": "etf"},
    "XLK":  {"name": "Technology",           "sector": "technology",   "beta": 1.2,  "type": "etf"},
    "XLV":  {"name": "Healthcare",           "sector": "healthcare",   "beta": 0.8,  "type": "etf"},
    "XLI":  {"name": "Industrials",          "sector": "industrials",  "beta": 1.0,  "type": "etf"},
    "XLD":  {"name": "Defense",              "sector": "defense",      "beta": 0.9,  "type": "etf"},
    # Safe haven
    "GLD":  {"name": "Gold",                 "sector": "commodity",    "beta": 0.3,  "type": "etf"},
    "TLT":  {"name": "Long-term Treasuries", "sector": "bonds",        "beta": -0.2, "type": "etf"},
    # Individual stocks (defense)
    "LMT":  {"name": "Lockheed Martin",      "sector": "defense",      "beta": 0.7,  "type": "stock"},
    "RTX":  {"name": "Raytheon",             "sector": "defense",      "beta": 0.8,  "type": "stock"},
    "BA":   {"name": "Boeing",               "sector": "defense",      "beta": 1.2,  "type": "stock"},
    "NOC":  {"name": "Northrop Grumman",     "sector": "defense",      "beta": 0.6,  "type": "stock"},
    "GD":   {"name": "General Dynamics",     "sector": "defense",      "beta": 0.7,  "type": "stock"},
    # Individual stocks (tech)
    "AAPL": {"name": "Apple",                "sector": "technology",   "beta": 1.1,  "type": "stock"},
    "MSFT": {"name": "Microsoft",            "sector": "technology",   "beta": 1.0,  "type": "stock"},
    "GOOGL":{"name": "Alphabet",             "sector": "technology",   "beta": 1.1,  "type": "stock"},
    "META": {"name": "Meta Platforms",       "sector": "technology",   "beta": 1.3,  "type": "stock"},
    "NVDA": {"name": "NVIDIA",               "sector": "technology",   "beta": 1.5,  "type": "stock"},
    "AMZN": {"name": "Amazon",               "sector": "technology",   "beta": 1.2,  "type": "stock"},
    "TSLA": {"name": "Tesla",                "sector": "technology",   "beta": 1.8,  "type": "stock"},
    # Financials
    "JPM":  {"name": "JPMorgan Chase",       "sector": "financials",   "beta": 1.1,  "type": "stock"},
    "GS":   {"name": "Goldman Sachs",        "sector": "financials",   "beta": 1.3,  "type": "stock"},
    "MS":   {"name": "Morgan Stanley",       "sector": "financials",   "beta": 1.2,  "type": "stock"},
    "BLK":  {"name": "BlackRock",            "sector": "financials",   "beta": 1.1,  "type": "stock"},
    "AXP":  {"name": "American Express",     "sector": "financials",   "beta": 1.0,  "type": "stock"},
    # Energy
    "XOM":  {"name": "Exxon Mobil",          "sector": "energy",       "beta": 1.0,  "type": "stock"},
    "CVX":  {"name": "Chevron",              "sector": "energy",       "beta": 0.9,  "type": "stock"},
    "COP":  {"name": "ConocoPhillips",       "sector": "energy",       "beta": 1.1,  "type": "stock"},
    "OXY":  {"name": "Occidental",           "sector": "energy",       "beta": 1.4,  "type": "stock"},
    "HAL":  {"name": "Halliburton",          "sector": "energy",       "beta": 1.3,  "type": "stock"},
    # Healthcare
    "PFE":  {"name": "Pfizer",               "sector": "healthcare",   "beta": 0.7,  "type": "stock"},
    "JNJ":  {"name": "Johnson & Johnson",    "sector": "healthcare",   "beta": 0.6,  "type": "stock"},
    "UNH":  {"name": "UnitedHealth",         "sector": "healthcare",   "beta": 0.8,  "type": "stock"},
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

# ── POLITICAL EVENT CATEGORIES (markets) ────��───────────────────────────────
POLITICAL_MARKETS = [
    "exec_order", "fed_rule", "insider_trade", "polymarket",
    "EXECUTIVE_ORDER", "TARIFF_ESCALATE", "CONTRACT_AWARD",
    "ENFORCEMENT_DROP", "ENERGY_LONG", "FINANCIALS_LONG",
    "DEFENSE_LONG", "PHARMA_SHORT", "SECTOR_LONG", "SECTOR_SHORT",
    "STOCK_LONG", "STOCK_SHORT", "STOCK_LONG_3D", "STOCK_LONG_10D",
    "INSIDER_BUY", "INSIDER_SELL", "CONGRESS_TRADE",
    "POLY_STOCK_ARB", "EVENT_BINARY", "EVENT_MULTI",
    "CEO_PERSONAL", "STOCK_LONG_EARNINGS",
]

# ── POLITICAL TRADING STRATEGIES ───────────────────────────────────────────
POLITICAL_STRATEGIES = {
    "momentum": {
        "desc": "Follow political momentum signals",
        "position_pct": 0.05,
        "min_signal": 0.10,
        "max_positions": 10,
        "holding_days": 3,
        "family": "momentum",
    },
    "mean_reversion": {
        "desc": "Fade extreme political signals",
        "position_pct": 0.03,
        "min_signal": 0.30,
        "max_positions": 6,
        "holding_days": 5,
        "family": "reversion",
    },
    "event_driven": {
        "desc": "Large positions on high-conviction events",
        "position_pct": 0.08,
        "min_signal": 0.20,
        "max_positions": 5,
        "holding_days": 2,
        "family": "event",
    },
    "pairs_trading": {
        "desc": "Long/short within sectors on relative strength",
        "position_pct": 0.04,
        "min_signal": 0.05,
        "max_positions": 8,
        "holding_days": 5,
        "family": "pairs",
    },
    "sector_rotation": {
        "desc": "Rotate into strongest political-signal sectors",
        "position_pct": 0.06,
        "min_signal": 0.05,
        "max_positions": 6,
        "holding_days": 7,
        "family": "rotation",
    },
    "safe_haven": {
        "desc": "Defensive positioning on negative signals (GLD, TLT)",
        "position_pct": 0.04,
        "min_signal": 0.15,
        "max_positions": 4,
        "holding_days": 5,
        "family": "defensive",
    },
    "insider_follow": {
        "desc": "Follow insider trades and congressional disclosures",
        "position_pct": 0.05,
        "min_signal": 0.10,
        "max_positions": 8,
        "holding_days": 10,
        "family": "insider",
    },
    "vol_scaled": {
        "desc": "Scale position size inversely to VIX / volatility",
        "position_pct": 0.04,
        "min_signal": 0.10,
        "max_positions": 8,
        "holding_days": 3,
        "family": "vol_adjusted",
    },
}

# ── POLITICAL TRADER PROFILES (per-agent, overlaid onto TRADERS) ───────────
# Each trader in TRADERS already has: pol_approach, etf_sectors
# We add political-specific fields used by the full backtest.
POLITICAL_TRADER_PROFILES = {
    "gemini": {
        "primary_strategy":   "momentum",
        "secondary_strategies": ["sector_rotation", "vol_scaled"],
        "sector_focus":       ["technology", "broad", "defense"],
        "ticker_focus":       ["XLK", "QQQ", "SPY", "LMT", "NVDA", "MSFT"],
        "event_weight":       {"exec_order": 1.2, "fed_rule": 1.0, "insider_trade": 0.8, "polymarket": 0.9},
    },
    "openrouter": {
        "primary_strategy":   "sector_rotation",
        "secondary_strategies": ["insider_follow", "pairs_trading"],
        "sector_focus":       ["broad", "energy", "financials", "small_cap"],
        "ticker_focus":       ["SPY", "IWM", "XLF", "XLE", "JPM", "XOM"],
        "event_weight":       {"exec_order": 1.0, "fed_rule": 1.1, "insider_trade": 1.2, "polymarket": 0.8},
    },
    "claude": {
        "primary_strategy":   "mean_reversion",
        "secondary_strategies": ["safe_haven", "vol_scaled"],
        "sector_focus":       ["bonds", "commodity", "healthcare"],
        "ticker_focus":       ["TLT", "GLD", "XLV", "JNJ", "UNH", "SPY"],
        "event_weight":       {"exec_order": 0.8, "fed_rule": 1.3, "insider_trade": 0.7, "polymarket": 1.0},
    },
    "codex": {
        "primary_strategy":   "event_driven",
        "secondary_strategies": ["momentum", "insider_follow"],
        "sector_focus":       ["technology", "defense", "energy"],
        "ticker_focus":       ["QQQ", "XLK", "NVDA", "BA", "TSLA", "META"],
        "event_weight":       {"exec_order": 1.5, "fed_rule": 0.7, "insider_trade": 1.0, "polymarket": 1.3},
    },
    "grok": {
        "primary_strategy":   "pairs_trading",
        "secondary_strategies": ["mean_reversion", "insider_follow"],
        "sector_focus":       ["energy", "commodity", "small_cap", "bonds"],
        "ticker_focus":       ["XLE", "GLD", "IWM", "TLT", "OXY", "CVX"],
        "event_weight":       {"exec_order": 0.9, "fed_rule": 1.0, "insider_trade": 1.3, "polymarket": 1.1},
    },
    "deepseek": {
        "primary_strategy":   "statistical_arb",
        "secondary_strategies": ["pairs_trading", "vol_scaled"],
        "sector_focus":       ["broad", "financials", "small_cap", "technology"],
        "ticker_focus":       ["SPY", "QQQ", "XLF", "IWM", "GS", "MS"],
        "event_weight":       {"exec_order": 0.8, "fed_rule": 1.2, "insider_trade": 0.9, "polymarket": 1.0},
    },
    "phi": {
        "primary_strategy":   "safe_haven",
        "secondary_strategies": ["mean_reversion", "vol_scaled"],
        "sector_focus":       ["bonds", "commodity", "healthcare"],
        "ticker_focus":       ["TLT", "GLD", "XLV", "JNJ", "PFE", "ABT"],
        "event_weight":       {"exec_order": 0.6, "fed_rule": 1.5, "insider_trade": 0.7, "polymarket": 0.8},
    },
    "cohere": {
        "primary_strategy":   "momentum",
        "secondary_strategies": ["event_driven", "sector_rotation"],
        "sector_focus":       ["technology", "industrials", "broad"],
        "ticker_focus":       ["XLK", "XLI", "QQQ", "SPY", "AMZN", "GOOGL"],
        "event_weight":       {"exec_order": 1.3, "fed_rule": 0.8, "insider_trade": 1.0, "polymarket": 1.2},
    },
    "gemma": {
        "primary_strategy":   "event_driven",
        "secondary_strategies": ["momentum", "insider_follow"],
        "sector_focus":       ["energy", "technology", "small_cap"],
        "ticker_focus":       ["XLE", "XLK", "IWM", "QQQ", "TSLA", "RIVN"],
        "event_weight":       {"exec_order": 1.4, "fed_rule": 0.7, "insider_trade": 1.1, "polymarket": 1.4},
    },
    "mixtral": {
        "primary_strategy":   "sector_rotation",
        "secondary_strategies": ["safe_haven", "pairs_trading"],
        "sector_focus":       ["broad", "financials", "energy", "bonds"],
        "ticker_focus":       ["SPY", "XLF", "XLE", "TLT", "BRK.B", "BAC"],
        "event_weight":       {"exec_order": 1.0, "fed_rule": 1.1, "insider_trade": 1.0, "polymarket": 0.9},
    },
}

# ── POLITICAL CONFIG PERSISTENCE ───────────────────────────────────────────
POLITICAL_TRADER_CONFIG_FILE = DATA_DIR / 'political-trader-configs-evolved.json'

def _load_evolved_political_configs() -> None:
    """Load evolved political trader configs from disk, overriding defaults."""
    if not POLITICAL_TRADER_CONFIG_FILE.exists():
        return
    try:
        saved = json.loads(POLITICAL_TRADER_CONFIG_FILE.read_text())
        for tid, cfg in saved.items():
            if tid in POLITICAL_TRADER_PROFILES:
                for key in ("primary_strategy", "secondary_strategies",
                            "risk_tolerance", "ticker_focus"):
                    if key in cfg:
                        POLITICAL_TRADER_PROFILES[tid][key] = cfg[key]
    except Exception:
        pass

def _save_evolved_political_configs() -> None:
    """Persist current political trader configs to disk."""
    configs = {}
    for tid, t in POLITICAL_TRADER_PROFILES.items():
        configs[tid] = {
            "primary_strategy": t.get("primary_strategy"),
            "secondary_strategies": t.get("secondary_strategies", []),
            "ticker_focus": t.get("ticker_focus", []),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    POLITICAL_TRADER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    POLITICAL_TRADER_CONFIG_FILE.write_text(json.dumps(configs, indent=2))

_load_evolved_political_configs()

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


# ── TRADER CONFIG PERSISTENCE ────────────────────────────────────────────────
# Council mutations modify TRADERS in-memory. This persists them across restarts.
TRADER_CONFIG_FILE = DATA_DIR / 'trader-configs-evolved.json'

def _load_evolved_trader_configs() -> None:
    """Load evolved trader configs from disk, overriding hardcoded defaults."""
    if not TRADER_CONFIG_FILE.exists():
        return
    try:
        saved = json.loads(TRADER_CONFIG_FILE.read_text())
        for tid, cfg in saved.items():
            if tid in TRADERS:
                # Only override mutable fields (strategies, models, risk)
                if "preferred_strategies" in cfg:
                    TRADERS[tid]["preferred_strategies"] = cfg["preferred_strategies"]
                if "preferred_models" in cfg:
                    TRADERS[tid]["preferred_models"] = cfg["preferred_models"]
                if "risk_tolerance" in cfg:
                    TRADERS[tid]["risk_tolerance"] = cfg["risk_tolerance"]
    except Exception:
        pass

def _save_evolved_trader_configs() -> None:
    """Persist current trader configs (strategies + models + risk) to disk."""
    configs = {}
    for tid, t in TRADERS.items():
        configs[tid] = {
            "preferred_strategies": t.get("preferred_strategies", []),
            "preferred_models": t.get("preferred_models", []),
            "risk_tolerance": t.get("risk_tolerance", 0.5),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    TRADER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRADER_CONFIG_FILE.write_text(json.dumps(configs, indent=2))

# Load evolved configs on import (override hardcoded defaults)
_load_evolved_trader_configs()


# ── SEASON MEMORY (Game-Level Learning) ──────────────────────────────────────
# Persists per-game bet outcomes across iterations so traders can LEARN.
# Each trader accumulates a rolling memory of bet results.

SEASON_MEMORY_FILE = DATA_DIR / 'season-memory.json'

def _load_season_memory() -> Dict:
    """Load season memory — per-game bet results from previous iterations."""
    if SEASON_MEMORY_FILE.exists():
        try:
            return json.loads(SEASON_MEMORY_FILE.read_text())
        except Exception:
            pass
    return {
        "version": 2,
        "last_iteration": 0,
        "trader_memories": {},       # {trader_id: [bet_records...]}
        "strategy_posteriors": {},   # {strategy: posterior_prob}
        "cross_trader_steals": [],   # [{from, to, strategy, iteration}]
        "feature_correlations": {},  # {feature_key: {win_rate, sample_size}}
    }


def _save_season_memory(memory: Dict) -> None:
    """Persist season memory to disk."""
    SEASON_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Keep memory bounded: max 2000 bets per trader
    for tid in list(memory.get("trader_memories", {}).keys()):
        bets = memory["trader_memories"][tid]
        if len(bets) > 2000:
            memory["trader_memories"][tid] = bets[-2000:]
    SEASON_MEMORY_FILE.write_text(json.dumps(memory, indent=2))


def _compute_rolling_accuracy(bets: List[Dict], window: int = 20) -> Dict:
    """Compute rolling accuracy metrics from last N bets."""
    recent = bets[-window:] if len(bets) >= window else bets
    if not recent:
        return {"accuracy": 0.5, "roi": 0.0, "streak": 0, "streak_type": "none",
                "bet_type_accuracy": {}, "confidence_accuracy": {}, "team_accuracy": {}}

    wins = sum(1 for b in recent if b.get("outcome") == "Win")
    total = len(recent)
    accuracy = wins / total if total > 0 else 0.5

    total_profit = sum(b.get("profit", 0) for b in recent)
    total_wagered = sum(b.get("bet_size", 0) for b in recent)
    roi = total_profit / total_wagered if total_wagered > 0 else 0.0

    # Current streak
    streak = 0
    streak_type = "none"
    if recent:
        last_outcome = recent[-1].get("outcome")
        for b in reversed(recent):
            if b.get("outcome") == last_outcome:
                streak += 1
            else:
                break
        streak_type = "win" if last_outcome == "Win" else "loss"

    # Per bet-type accuracy
    bt_acc = defaultdict(lambda: {"wins": 0, "total": 0})
    for b in recent:
        cat = b.get("category", "unknown")
        bt_type = cat.split("_")[0] if "_" in cat else cat  # e.g. "ml", "spread", "total"
        bt_acc[bt_type]["total"] += 1
        if b.get("outcome") == "Win":
            bt_acc[bt_type]["wins"] += 1
    bet_type_accuracy = {k: round(v["wins"] / v["total"], 3) if v["total"] > 0 else 0.5
                         for k, v in bt_acc.items()}

    # Per confidence-range accuracy (binned)
    conf_acc = defaultdict(lambda: {"wins": 0, "total": 0})
    for b in recent:
        prob = b.get("model_prob", 0.5)
        conf_bin = f"{int(abs(prob - 0.5) * 100 / 10) * 10}-{int(abs(prob - 0.5) * 100 / 10) * 10 + 10}%"
        conf_acc[conf_bin]["total"] += 1
        if b.get("outcome") == "Win":
            conf_acc[conf_bin]["wins"] += 1
    confidence_accuracy = {k: round(v["wins"] / v["total"], 3) if v["total"] > 0 else 0.5
                           for k, v in conf_acc.items()}

    # Per team accuracy
    team_acc = defaultdict(lambda: {"wins": 0, "total": 0})
    for b in recent:
        game = b.get("game", "")
        teams = game.split(" vs ") if " vs " in game else []
        for t in teams:
            team_acc[t.strip()]["total"] += 1
            if b.get("outcome") == "Win":
                team_acc[t.strip()]["wins"] += 1
    team_accuracy = {k: round(v["wins"] / v["total"], 3) if v["total"] > 0 else 0.5
                     for k, v in team_acc.items()}

    return {
        "accuracy": round(accuracy, 4),
        "roi": round(roi, 4),
        "streak": streak,
        "streak_type": streak_type,
        "bet_type_accuracy": dict(bet_type_accuracy),
        "confidence_accuracy": dict(confidence_accuracy),
        "team_accuracy": dict(team_accuracy),
    }


def _compute_kelly_adjustment(rolling: Dict) -> float:
    """
    Adjust Kelly fraction based on rolling performance.
    - 3+ loss streak → reduce by 50% for next 5 games (returns 0.5)
    - 5+ win streak → boost up to 2x (returns min(2.0, 1.0 + streak * 0.2))
    - Otherwise scale by accuracy relative to breakeven
    """
    streak = rolling.get("streak", 0)
    streak_type = rolling.get("streak_type", "none")
    accuracy = rolling.get("accuracy", 0.5)

    # Losing streak protection
    if streak_type == "loss" and streak >= 3:
        return max(0.25, 0.5 - (streak - 3) * 0.05)  # 0.5 at 3, 0.45 at 4, etc.

    # Winning streak amplification
    if streak_type == "win" and streak >= 5:
        return min(2.0, 1.0 + (streak - 4) * 0.2)  # 1.2 at 5, 1.4 at 6, etc.

    # Accuracy-based scaling: >55% → boost, <45% → reduce
    if accuracy > 0.55:
        return min(1.5, 1.0 + (accuracy - 0.55) * 5.0)
    elif accuracy < 0.45:
        return max(0.4, 1.0 - (0.45 - accuracy) * 5.0)

    return 1.0


def _compute_bayesian_posteriors(memory: Dict) -> Dict[str, float]:
    """
    Compute Bayesian posterior probabilities for each strategy.
    P(strategy_i | data) proportional to P(data | strategy_i) * P(strategy_i)
    where P(data | strategy_i) is based on ROI.
    """
    strat_results = defaultdict(lambda: {"profit": 0.0, "wagered": 0.0, "bets": 0})

    for tid, bets in memory.get("trader_memories", {}).items():
        for b in bets:
            s = b.get("strategy", "unknown")
            strat_results[s]["bets"] += 1
            strat_results[s]["profit"] += b.get("profit", 0)
            strat_results[s]["wagered"] += b.get("bet_size", 0)

    # Prior: uniform across active strategies
    active_strats = [s for s in STRATEGIES if s not in ELIMINATED_STRATEGIES]
    n = max(len(active_strats), 1)
    prior = 1.0 / n

    posteriors = {}
    for s in active_strats:
        sr = strat_results.get(s, {"profit": 0, "wagered": 0, "bets": 0})
        if sr["bets"] < 5:
            # Not enough data — use prior
            posteriors[s] = prior
            continue

        roi = sr["profit"] / sr["wagered"] if sr["wagered"] > 0 else 0.0
        # Likelihood: transform ROI to positive score
        # ROI of +10% → high likelihood, ROI of -50% → low likelihood
        likelihood = math.exp(roi * 3.0)  # Exponential weighting
        posteriors[s] = likelihood * prior

    # Normalize
    total = sum(posteriors.values())
    if total > 0:
        posteriors = {s: round(p / total, 6) for s, p in posteriors.items()}

    return posteriors


def _check_dead_strategies(memory: Dict) -> List[str]:
    """
    Identify strategies that should be permanently eliminated.
    Dead = < -80% ROI over 50+ bets.
    """
    strat_results = defaultdict(lambda: {"profit": 0.0, "wagered": 0.0, "bets": 0})

    for tid, bets in memory.get("trader_memories", {}).items():
        for b in bets:
            s = b.get("strategy", "unknown")
            strat_results[s]["bets"] += 1
            strat_results[s]["profit"] += b.get("profit", 0)
            strat_results[s]["wagered"] += b.get("bet_size", 0)

    dead = []
    for s, sr in strat_results.items():
        if s in ELIMINATED_STRATEGIES or s not in STRATEGIES:
            continue
        if sr["bets"] < 50:
            continue
        roi = sr["profit"] / sr["wagered"] if sr["wagered"] > 0 else 0.0
        if roi < -0.80:  # -80% ROI
            dead.append(s)
            ELIMINATED_STRATEGIES[s] = {
                "eliminated_at": date.today().isoformat(),
                "reason": f"Bayesian death: {roi*100:.0f}% ROI over {sr['bets']} bets",
                "final_roi": round(roi, 2),
                "department": "D4_BETTING",
            }
            print(f"  [BAYESIAN DEATH] '{s}': {roi*100:.0f}% ROI over {sr['bets']} bets")
    return dead


def _compute_feature_correlations(memory: Dict) -> Dict[str, Dict]:
    """
    Analyze which game features correlate with winning bets.
    Features: spread_size, home_away, conference, bet_type, strategy.
    Returns correlation dict for smart mutations.
    """
    features = defaultdict(lambda: {"wins": 0, "total": 0, "profit": 0.0})

    for tid, bets in memory.get("trader_memories", {}).items():
        for b in bets:
            # Feature: strategy + bet_type combo
            strat = b.get("strategy", "unknown")
            cat = b.get("category", "unknown")
            combo_key = f"strat={strat}|cat={cat}"
            features[combo_key]["total"] += 1
            features[combo_key]["profit"] += b.get("profit", 0)
            if b.get("outcome") == "Win":
                features[combo_key]["wins"] += 1

            # Feature: spread size bucket
            edge = b.get("edge_pct", 0)
            edge_bucket = f"edge={'high' if edge > 5 else 'mid' if edge > 2 else 'low'}"
            strat_edge = f"strat={strat}|{edge_bucket}"
            features[strat_edge]["total"] += 1
            features[strat_edge]["profit"] += b.get("profit", 0)
            if b.get("outcome") == "Win":
                features[strat_edge]["wins"] += 1

            # Feature: confidence level
            prob = b.get("model_prob", 0.5)
            conf = abs(prob - 0.5)
            conf_level = f"conf={'high' if conf > 0.15 else 'mid' if conf > 0.08 else 'low'}"
            strat_conf = f"strat={strat}|{conf_level}"
            features[strat_conf]["total"] += 1
            features[strat_conf]["profit"] += b.get("profit", 0)
            if b.get("outcome") == "Win":
                features[strat_conf]["wins"] += 1

    # Compute win rates and filter for statistical significance
    result = {}
    for key, stats in features.items():
        if stats["total"] < 10:
            continue
        wr = stats["wins"] / stats["total"]
        result[key] = {
            "win_rate": round(wr, 4),
            "sample_size": stats["total"],
            "avg_profit": round(stats["profit"] / stats["total"], 4),
            "profitable": stats["profit"] > 0,
        }

    return result


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


def load_political_events() -> List[Dict]:
    """Load consolidated political events from nomos-political-alpha."""
    fp = POLITICAL / "data" / "historical" / "consolidated_events.json"
    if not fp.exists():
        return []
    try:
        events = json.loads(fp.read_text())
        events.sort(key=lambda e: e.get("date", ""))
        return events
    except Exception:
        return []


def load_all_social_snapshots() -> List[Tuple[str, Dict]]:
    """Load all historical social signal snapshots, sorted by timestamp."""
    social_dir = POLITICAL / "data" / "social"
    if not social_dir.exists():
        return []
    snapshots = []
    for fp in sorted(social_dir.glob("social_signals_*.json")):
        if fp.name == "social_signals_latest.json":
            continue
        try:
            data = json.loads(fp.read_text())
            sigs = data.get("signals", data)
            ts = fp.stem.replace("social_signals_", "")
            snapshots.append((ts, sigs))
        except Exception:
            continue
    return snapshots


def load_political_trader_states(exclude: str) -> Dict:
    """Load other political trader states for competitive awareness."""
    results = {}
    for trader_id in TRADERS:
        if trader_id == exclude:
            continue
        sf = TRADERS_DIR / f"political-{trader_id}-state.json"
        if sf.exists():
            try:
                results[trader_id] = json.loads(sf.read_text())
            except Exception:
                pass
    return results


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


# ── DMAD: PRIOR-RUN CONSENSUS MAP ────────────────────────────────────────────

def build_dmad_consensus_map(all_trader_states: Dict[str, Dict]) -> Dict[str, float]:
    """
    Build a per-game damping map from last iteration's bet histories.

    For each game key (date_home_away), count how many agents bet the same
    primary direction (ml_home vs ml_away). If >= CONSENSUS_THRESHOLD agree,
    record CONSENSUS_DAMPING; otherwise 1.0.

    This is the DMAD "last-round consensus penalty" — agents that would group-
    think on a game get a 40% Kelly reduction on that game next round.

    Returns: {game_key: damping_factor}  e.g. {"2026-01-15_BOS_LAL": 0.60}
    """
    if not _DMAD_AVAILABLE:
        return {}

    # Accumulate votes: game_key -> {direction: [trader_ids]}
    votes: Dict[str, Dict[str, list]] = {}

    for trader_id, state in all_trader_states.items():
        bets = state.get("nba_bets_history", [])
        for bet in bets:
            game = bet.get("game", "")
            date = bet.get("date", "")
            cat = bet.get("category", "")
            if not game or not date or not cat:
                continue
            key = f"{date}_{game.replace(' vs ', '_')}"
            # Determine direction: "home" if category contains "home", else "away"
            direction = "home" if "home" in cat else "away"
            if key not in votes:
                votes[key] = {"home": [], "away": []}
            if trader_id not in votes[key][direction]:
                votes[key][direction].append(trader_id)

    damping_map: Dict[str, float] = {}
    for key, dirs in votes.items():
        max_agreement = max(len(dirs["home"]), len(dirs["away"]))
        if max_agreement >= CONSENSUS_THRESHOLD:
            damping_map[key] = CONSENSUS_DAMPING

    if damping_map:
        n_consensus = len(damping_map)
        print(f"  [DMAD] {n_consensus} game(s) with prior-round consensus → "
              f"Kelly x{CONSENSUS_DAMPING} applied")
    return damping_map


# ── POLITICAL SIGNAL COMPUTATION ─────────────────────────────────────────────

def compute_political_ticker_signal(ticker: str, social_signals: Dict,
                                    events_for_day: List[Dict]) -> Dict:
    """Compute combined signal for one ticker from social signals + political events."""
    components = []
    total_strength = 0.0
    total_direction = 0.0

    if ticker in social_signals:
        sig = social_signals[ticker]
        sentiment = sig.get("combined_sentiment", 0.0)
        strength = sig.get("signal_strength", 0.0)
        if strength > 0.01:
            components.append({"source": "social", "sentiment": sentiment,
                               "strength": strength, "mentions": sig.get("total_mentions", 0)})
            total_strength += strength
            total_direction += sentiment * strength

    ticker_events = [e for e in events_for_day if e.get("ticker") == ticker]
    for ev in ticker_events:
        ev_strength = ev.get("signal_strength", 0.5)
        ev_outcome = ev.get("outcome", 0.5)
        ev_direction = (ev_outcome - 0.5) * 2
        components.append({"source": "event", "event_type": ev.get("event_type", "unknown"),
                           "title": ev.get("title", "")[:60], "strength": ev_strength,
                           "direction": ev_direction})
        total_strength += ev_strength * 0.5
        total_direction += ev_direction * ev_strength * 0.5

    if not components:
        etf_info = ETF_UNIVERSE.get(ticker, {})
        sector = etf_info.get("sector", "")
        sector_tickers = POLITICAL_SECTOR_MAP.get(sector, [])
        sector_sigs = []
        for st in sector_tickers:
            if st != ticker and st in social_signals:
                s = social_signals[st]
                if s.get("signal_strength", 0) > 0.01:
                    sector_sigs.append(s.get("combined_sentiment", 0.0) * s.get("signal_strength", 0.0))
        if sector_sigs:
            avg = sum(sector_sigs) / len(sector_sigs)
            components.append({"source": "sector_spillover", "strength": min(abs(avg), 0.3),
                               "direction": 1.0 if avg > 0 else -1.0})
            total_strength += min(abs(avg), 0.3)
            total_direction += avg

    if total_strength < 0.01:
        return {"direction": "neutral", "strength": 0.0, "components": []}

    net_direction = total_direction / total_strength if total_strength > 0 else 0.0
    direction = "long" if net_direction > 0 else ("short" if net_direction < 0 else "neutral")
    return {"direction": direction, "strength": min(total_strength, 1.0),
            "net_direction": round(net_direction, 4), "components": components}


# ── POLITICAL POSITION SIZING ───────────────────────────────────────────────

POLITICAL_INITIAL_CAPITAL = 100_000.0

def compute_political_position_size(strategy_name: str, signal: Dict, capital: float,
                                    risk_tolerance: float, existing_positions: int) -> float:
    """Compute position size in USD for a given signal and political strategy."""
    cfg = POLITICAL_STRATEGIES.get(strategy_name, POLITICAL_STRATEGIES["momentum"])
    if signal["direction"] == "neutral" or signal["strength"] < cfg["min_signal"]:
        return 0.0
    if existing_positions >= cfg["max_positions"]:
        return 0.0
    base_pct = cfg["position_pct"] * risk_tolerance
    scaled_pct = base_pct * min(signal["strength"] * 2, 1.0)
    if capital < POLITICAL_INITIAL_CAPITAL * 0.8:
        scaled_pct *= 0.5
    elif capital < POLITICAL_INITIAL_CAPITAL * 0.5:
        scaled_pct *= 0.25
    return round(max(capital * scaled_pct, 0.0), 2)


def simulate_political_trade_outcome(ticker: str, direction: str, signal_strength: float,
                                     event_return: Optional[float], seed: str) -> float:
    """Simulate the return of a political trade (deterministic hash-based)."""
    etf_info = ETF_UNIVERSE.get(ticker, {"beta": 1.0})
    beta = etf_info.get("beta", 1.0)
    h = int(hashlib.md5(f"pol_{ticker}_{seed}".encode()).hexdigest()[:8], 16)
    noise = ((h % 10000) / 10000.0 - 0.5) * 0.04
    if event_return is not None:
        base_return = event_return
    else:
        h2 = int(hashlib.md5(f"ret_{ticker}_{seed}".encode()).hexdigest()[:6], 16)
        market_move = ((h2 % 1000) / 1000.0 - 0.45) * 0.02
        base_return = market_move * beta + signal_strength * 0.005
    trade_return = base_return + noise
    if direction == "short":
        trade_return *= -1
    return round(trade_return, 6)


# ── POLITICAL AGENT DECISION ENGINE ─────────────────────────────────────────

def political_agent_decide_positions(trader_id: str, day_date: str, capital: float,
                                     social_signals: Dict, day_events: List[Dict],
                                     others: Dict, existing_positions: int) -> List[Dict]:
    """Political agent decides all positions for one trading day."""
    pol_cfg = POLITICAL_TRADER_PROFILES.get(trader_id, {})
    trader_cfg = TRADERS[trader_id]
    personality = trader_cfg["personality"]
    primary_strat = pol_cfg.get("primary_strategy", trader_cfg.get("pol_approach", "momentum"))
    secondary_strats = pol_cfg.get("secondary_strategies", [])
    risk = trader_cfg["risk_tolerance"]
    focus_tickers = pol_cfg.get("ticker_focus", trader_cfg.get("etf_sectors", []))
    sector_focus = pol_cfg.get("sector_focus", [])
    event_weights = pol_cfg.get("event_weight", {})

    candidates = list(focus_tickers)
    for sector in sector_focus:
        for ticker in POLITICAL_SECTOR_MAP.get(sector, []):
            if ticker not in candidates:
                candidates.append(ticker)

    positions = []
    budget_remaining = capital * risk * 0.3
    pos_count = existing_positions

    for ticker in candidates:
        if budget_remaining <= 0:
            break
        signal = compute_political_ticker_signal(ticker, social_signals, day_events)
        if signal["direction"] == "neutral":
            continue
        for comp in signal.get("components", []):
            if comp.get("source") == "event":
                ev_type = comp.get("event_type", "")
                weight = event_weights.get(ev_type, 1.0)
                signal["strength"] = min(signal["strength"] * weight, 1.0)

        chosen_strat = primary_strat
        if personality == "analytical":
            if signal["strength"] < 0.2 and secondary_strats:
                chosen_strat = secondary_strats[0]
        elif personality == "diversified":
            h = int(hashlib.md5(f"{day_date}_{ticker}".encode()).hexdigest()[:4], 16)
            all_strats = [primary_strat] + secondary_strats
            chosen_strat = all_strats[h % len(all_strats)]
        elif personality == "conservative":
            other_caps = [s.get("capital", POLITICAL_INITIAL_CAPITAL) for s in others.values()]
            avg_other = sum(other_caps) / len(other_caps) if other_caps else capital
            if capital < avg_other * 0.9 and "safe_haven" in [primary_strat] + secondary_strats:
                chosen_strat = "safe_haven"
        elif personality == "aggressive":
            if signal["strength"] > 0.3:
                chosen_strat = "event_driven"
            elif secondary_strats:
                chosen_strat = secondary_strats[0]
        elif personality == "contrarian":
            if signal["strength"] > 0.25:
                chosen_strat = "mean_reversion" if "mean_reversion" in [primary_strat] + secondary_strats else primary_strat
                signal = dict(signal)
                signal["direction"] = "short" if signal["direction"] == "long" else "long"
                signal["net_direction"] = -signal.get("net_direction", 0)

        if chosen_strat in ELIMINATED_POLITICAL_STRATEGIES:
            continue

        size = compute_political_position_size(chosen_strat, signal, capital, risk, pos_count)
        if size <= 0 or size > budget_remaining:
            size = min(size, budget_remaining) if size > 0 else 0
        if size <= 0:
            continue

        event_return = None
        ticker_events = [e for e in day_events if e.get("ticker") == ticker]
        if ticker_events:
            event_return = ticker_events[0].get("excess_return")

        seed = f"{day_date}_{trader_id}_{ticker}_{chosen_strat}"
        trade_return = simulate_political_trade_outcome(
            ticker, signal["direction"], signal["strength"], event_return, seed)
        pnl = size * trade_return

        reasoning_parts = [f"strategy={chosen_strat}",
                           f"signal={signal['strength']:.3f} {signal['direction']}"]
        if ticker_events:
            reasoning_parts.append(f"event={ticker_events[0].get('event_type','?')}")
        reasoning_parts.append(f"beta={ETF_UNIVERSE.get(ticker, {}).get('beta', 1.0)}")

        positions.append({
            "date": day_date, "ticker": ticker,
            "name": ETF_UNIVERSE.get(ticker, {}).get("name", ticker),
            "type": ETF_UNIVERSE.get(ticker, {}).get("type", "stock"),
            "sector": ETF_UNIVERSE.get(ticker, {}).get("sector", "unknown"),
            "direction": signal["direction"], "strategy_used": chosen_strat,
            "signal_strength": round(signal["strength"], 4),
            "net_direction": signal.get("net_direction", 0),
            "position_size": size, "trade_return": trade_return,
            "pnl": round(pnl, 2), "outcome": "Win" if pnl > 0 else "Loss",
            "reasoning": " | ".join(reasoning_parts),
            "event_count": len(ticker_events),
        })
        budget_remaining -= size
        pos_count += 1

    return positions


# ── NBA SIMULATION HELPERS ────────────────────────────────────────────────────

def model_prob(model_name: str, implied_prob: float, seed_val: str, home_won: bool) -> float:
    """
    Simulate model prediction WITHOUT leaking the outcome.

    The prediction is based on implied_prob (market line) plus model-specific
    noise calibrated to the model's Brier score. The `home_won` param is NOT
    used in prediction — it exists only for API compat with bet resolution.

    Fix (2026-04-02): previous version used `truth` in the prediction formula,
    making the sim unrealistically accurate and creating the 100% win-rate
    artifact on ml_away categories.
    """
    brier    = MODELS[model_name]["brier"]
    # Model skill: how much the model can deviate from market (higher = better)
    skill    = max(0.0, 1.0 - brier / 0.25)
    # Deterministic per-model-per-game noise (replaces outcome-leaked signal)
    h        = int(hashlib.md5(f"{model_name}_{seed_val}".encode()).hexdigest()[:8], 16)
    # Noise proportional to skill — better models have tighter spreads
    noise    = ((h % 1000) / 1000.0 - 0.5) * 0.12 * (1.0 - skill * 0.5)
    # Home court bias: better models pick up ~2% home court advantage
    h2       = int(hashlib.md5(f"hca_{model_name}_{seed_val}".encode()).hexdigest()[:4], 16)
    home_bias = skill * 0.02 * (1.0 if (h2 % 2 == 0) else -1.0)
    pred     = implied_prob + noise + home_bias
    # Apply calibration if available
    pred     = _calibrate_prob(pred)
    return max(0.05, min(0.95, pred))


def _calibrate_prob(raw_prob: float) -> float:
    """Apply isotonic calibration from calibration-map if available."""
    global _CALIBRATION_MAP
    if _CALIBRATION_MAP is None:
        _CALIBRATION_MAP = _load_calibration_map()
    if not _CALIBRATION_MAP:
        return raw_prob
    # Piecewise linear interpolation
    keys = sorted(_CALIBRATION_MAP.keys())
    if raw_prob <= keys[0]:
        return _CALIBRATION_MAP[keys[0]]
    if raw_prob >= keys[-1]:
        return _CALIBRATION_MAP[keys[-1]]
    for i in range(len(keys) - 1):
        if keys[i] <= raw_prob <= keys[i + 1]:
            t = (raw_prob - keys[i]) / (keys[i + 1] - keys[i])
            return _CALIBRATION_MAP[keys[i]] * (1 - t) + _CALIBRATION_MAP[keys[i + 1]] * t
    return raw_prob


_CALIBRATION_MAP: Optional[Dict[float, float]] = None

def _load_calibration_map() -> Dict[float, float]:
    """Load calibration map from nomos-nba-agent or local copy."""
    paths = [
        NBA_AGENT / 'hf-space' / 'data' / 'calibration-map.json',
        ROOT / 'data' / 'calibration' / 'calibration-map.json',
    ]
    for p in paths:
        if p.exists():
            try:
                raw = json.loads(p.read_text())
                return {float(k): float(v) for k, v in raw.items()}
            except Exception:
                continue
    return {}


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
                 bankroll: float, comp_state: Optional[Dict] = None,
                 kelly_adj: float = 1.0) -> float:
    """Calculate bet size for a given NBA strategy.
    kelly_adj: multiplier from game-level learning (0.25-2.0). Adjusts final bet size
    based on rolling accuracy, streak detection, and Bayesian priors."""
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

    # Apply game-level learning adjustment
    bet *= kelly_adj

    return min(max(bet, 0.0), max_bet)


# ── PER-GAME AGENT DECISION ENGINE (v5) ──────────────────────────────────────

def agent_pick_model_for_game(trader_id: str, game_ctx: Dict) -> str:
    """Agent picks which model to trust for THIS specific game based on full context.
    Respects OASIS discussion model_bias if the game_ctx carries one."""
    cfg = TRADERS[trader_id]
    personality = cfg["personality"]
    preferred = cfg["preferred_models"]
    models_info = game_ctx.get("models", {})
    preds = models_info.get("predictions", {})

    # ── OASIS model bias (additive: bias model must be in MODELS to apply) ────
    oasis_bias = game_ctx.get("oasis", {})
    oasis_model = oasis_bias.get("model_bias", "")
    if oasis_model and oasis_model in MODELS:
        return oasis_model

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
    """Agent picks which strategies to use for THIS game. Can pick multiple.
    Respects OASIS discussion strategy_bias if the game_ctx carries one."""
    cfg = TRADERS[trader_id]
    personality = cfg["personality"]
    preferred = [s for s in cfg["preferred_strategies"] if s not in ELIMINATED_STRATEGIES]
    if not preferred:
        preferred = ["half_kelly"]

    # ── OASIS strategy bias (additive: bias strategy must be active to apply) ─
    oasis_bias = game_ctx.get("oasis", {})
    oasis_strategy = oasis_bias.get("strategy_bias", "")
    if oasis_strategy and oasis_strategy in STRATEGIES and oasis_strategy not in ELIMINATED_STRATEGIES:
        return [oasis_strategy]

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


def _resolve_bet_outcome(category: str, odds: Dict, result: Dict,
                         hs: int, as_: int, total_pts: int, home_won: bool) -> bool:
    """Resolve whether a bet category won based on game outcome."""
    cat = category.lower()
    spread = odds.get("spread_home", 0) or 0
    total_line = odds.get("total", 0) or 0
    margin = abs(hs - as_)

    outcomes = {
        "ml_home": home_won,
        "ml_away": not home_won,
        "spread_home": (hs + spread) > as_,
        "spread_away": (as_ - spread) > hs,
        "total_over": total_pts > total_line,
        "total_under": total_pts < total_line,
        "h1_ml_home": home_won,  # approximation
        "h1_ml_away": not home_won,
        "team_total_home_over": hs > (total_line / 2),
        "team_total_home_under": hs < (total_line / 2),
    }
    return outcomes.get(cat, False)


def agent_decide_game_bets(trader_id: str, game_ctx: Dict, bankroll: float,
                           day_budget: float, others: Dict, comp_state: Dict,
                           kelly_adj: float = 1.0,
                           category_weights: Optional[Dict[str, float]] = None,
                           dmad_damping: float = 1.0) -> List[Dict]:
    """
    v9 CORE: Agent decides ALL bets for ONE game with LEARNING.
    Now uses:
    - kelly_adj: rolling-window adjustment from season memory (0.25-2.0)
    - category_weights: per-category boost/penalty from feature correlations
    - dmad_damping: DMAD consensus damping factor (0.60 when >3/5 agents agree)
    Agent sees: standings, team form, all model predictions, odds, other agents.
    DMAD: each agent sees only its locked data partition (see dmad_profiles.py).
    Agent chooses: model, strategies, categories — all freely.
    """
    # ── DMAD: filter context to this agent's locked data partition ────────────
    game_ctx = filter_nba_context(game_ctx, trader_id)
    cfg = TRADERS[trader_id]
    odds = game_ctx["odds"]
    result = game_ctx["_result"]
    home_won = result["home_won"]
    hs, as_ = result["home_score"], result["away_score"]
    total_pts = hs + as_
    seed_val = f"{game_ctx['date']}_{game_ctx['home']}_{game_ctx['away']}"

    # ── REAL LLM DECISION (for live/recent games only) ──────────────────────
    # Full-season backtest = hash simulation (1000+ games, too many API calls).
    # Live/recent games (last 7 days) = REAL LLM reasoning per agent.
    # This lets us scientifically compare LLM reasoning vs hash simulation.
    _is_recent = False
    try:
        from datetime import timedelta
        game_date = datetime.strptime(game_ctx.get("date", "2020-01-01"), "%Y-%m-%d").date()
        _is_recent = (date.today() - game_date).days <= 7
    except Exception:
        pass
    if _LLM_AGENTS_AVAILABLE and _is_recent:
        provider = cfg.get("provider", "")
        trader_state = comp_state.get(trader_id, {})
        llm_result = agent_llm_decide(trader_id, provider, game_ctx, trader_state)
        if llm_result.get("llm_used") and not llm_result.get("pass"):
            # Convert LLM bets to trading floor format
            llm_bets = []
            for lb in llm_result.get("bets", []):
                cat = lb.get("category", "")
                conf = float(lb.get("confidence", 0.5))
                edge_est = float(lb.get("edge", 0.0))
                bet_pct = float(lb.get("bet_pct", 0.01))
                if cat and edge_est > 0 and bet_pct > 0:
                    # Resolve outcome for this category
                    cat_won = _resolve_bet_outcome(cat, odds, result, hs, as_, total_pts, home_won)
                    llm_bets.append({
                        "category": cat,
                        "bet_size": round(min(bet_pct, day_budget / bankroll) * bankroll, 4),
                        "odds_dec": odds.get(f"{cat.split('_')[0]}_dec", 1.909),
                        "prob": round(conf, 4),
                        "edge": round(edge_est, 4),
                        "won": cat_won,
                        "model": "llm_reasoning",
                        "strategy": "llm_agent",
                        "reasoning": llm_result.get("reasoning", ""),
                        "llm_provider": provider,
                    })
            if llm_bets:
                return llm_bets
        # If LLM passed or failed, fall through to hash simulation below

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

    # ── EXPANDED CATEGORIES (v10): margin, race-to, exotic, quarter, props ──
    margin = abs(hs - as_)
    # Margin bands
    candidates.append(("margin_1_5", prob_home * 0.6, 3.0, 1 <= margin <= 5))
    candidates.append(("margin_6_10", 0.30, 3.5, 6 <= margin <= 10))
    candidates.append(("margin_11_15", 0.20, 5.0, 11 <= margin <= 15))
    candidates.append(("margin_16_plus", 0.12, 7.0, margin >= 16))
    # Race to points
    race_75 = hs >= 75 or as_ >= 75
    race_100 = hs >= 100 or as_ >= 100
    candidates.append(("race_to_75_home", prob_home * 0.85, 1.85, hs >= 75 and (hs >= 75 or as_ < 75)))
    candidates.append(("race_to_100_home", prob_home * 0.80, 1.90, hs >= 100 and (hs >= 100 or as_ < 100)))
    # Quarter winners (synthetic from final margin)
    for q_name, q_prob_factor in [("q1_home", 0.9), ("q2_home", 0.85), ("q3_home", 0.88), ("q4_home", 0.82)]:
        candidates.append((q_name, prob_home * q_prob_factor, 1.90, home_won))  # approx
    # Double result (H1 + FT)
    candidates.append(("double_result_hh", prob_home * 0.7 * h1_prob_home, 2.2, home_won and h1_won))
    candidates.append(("double_result_aa", prob_away * 0.7 * h1_prob_away, 2.2, not home_won and not h1_won))
    # Combined: ML + O/U
    if odds.get("total"):
        line = odds["total"]
        candidates.append(("home_and_over", prob_home * 0.5, 3.0, home_won and total_pts > line))
        candidates.append(("away_and_under", prob_away * 0.45, 3.5, not home_won and total_pts < line))
    # Alt totals
    if odds.get("total"):
        line = odds["total"]
        for alt_adj, alt_name in [(-5, "alt_over_minus5"), (5, "alt_under_plus5"),
                                   (-10, "alt_over_minus10"), (10, "alt_under_plus10")]:
            alt_line = line + alt_adj
            if alt_adj < 0:
                candidates.append((alt_name, 0.65, 1.65, total_pts > alt_line))
            else:
                candidates.append((alt_name, 0.65, 1.65, total_pts < alt_line))
    # Alt spreads
    for alt_s, alt_odds, alt_label in [(3.5, 2.1, "alt_spread_home_3.5"),
                                        (7.5, 2.8, "alt_spread_home_7.5"),
                                        (-3.5, 2.1, "alt_spread_away_3.5"),
                                        (-7.5, 2.8, "alt_spread_away_7.5")]:
        if alt_s > 0:
            candidates.append((alt_label, prob_home * 0.75, alt_odds, (hs - as_) > alt_s))
        else:
            candidates.append((alt_label, prob_away * 0.75, alt_odds, (as_ - hs) > abs(alt_s)))
    # Player props (synthetic from team totals)
    if odds.get("total"):
        line = odds["total"]
        # Lead scorer estimate: ~25% of team total
        lead_pts = hs * 0.25
        candidates.append(("player_pts_over_24.5", 0.50, 1.85, lead_pts > 24.5))
        candidates.append(("player_pts_under_24.5", 0.50, 1.85, lead_pts < 24.5))
        # Lead rebounder: ~10 per game
        candidates.append(("player_reb_over_9.5", 0.48, 1.85, True))  # synthetic
        candidates.append(("player_ast_over_7.5", 0.47, 1.90, True))  # synthetic
    # Exact margin
    candidates.append(("exact_margin_1", 0.08, 11.0, margin == 1))
    candidates.append(("exact_margin_2", 0.07, 13.0, margin == 2))
    candidates.append(("exact_margin_3", 0.07, 13.0, margin == 3))

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

    # Category weights from feature correlations (learned from memory)
    cat_weights = category_weights or {}

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

            # Apply per-category weight from feature correlations
            cat_adj = cat_weights.get(f"strat={strat_name}|cat={cat}", 1.0)
            # Apply DMAD consensus damping (anti-groupthink: 40% reduction when >3/5 agree)
            effective_kelly_adj = kelly_adj * cat_adj * dmad_damping

            bet_size = get_bet_size(strat_name, prob, odds_val, remaining_budget,
                                    comp_state, kelly_adj=effective_kelly_adj)
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
            if effective_kelly_adj != 1.0:
                reasoning_parts.append(f"kelly_adj: {effective_kelly_adj:.2f}")
            # Append DMAD role tag to reasoning for audit trail
            _dmad_meta = game_ctx.get("_dmad", {})
            if _dmad_meta:
                reasoning_parts.append(f"dmad_role: {_dmad_meta.get('role', '?')}")
            if dmad_damping < 1.0:
                reasoning_parts.append(f"CONSENSUS_WARNING dmad_damp={dmad_damping:.2f}")

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
                "kelly_adjustment": round(effective_kelly_adj, 4),
                "dmad_role": _dmad_meta.get("role", ""),
                "dmad_damping": round(dmad_damping, 4),
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
                               all_games: Optional[List[Dict]] = None,
                               season_memory: Optional[Dict] = None,
                               darwin_weight: float = 1.0,
                               oasis_ctx: Optional[Dict] = None,
                               dmad_consensus_map: Optional[Dict[str, float]] = None) -> Dict:
    """
    v9+DMAD: Full-season backtest WITH GAME-LEVEL LEARNING + DIVERSE MULTI-AGENT DEBATE.
    Agent gets a DMAD-filtered context (locked to its data partition, see dmad_profiles.py).

    darwin_weight: atlas-gic per-trader allocation multiplier (0.3..2.5). Applied
    on top of kelly_adj so winners scale up daily and losers fade. Updated by
    scripts/arena/darwin_weights.py before each iteration.

    oasis_ctx: optional OASIS social-discussion output for today.  If present,
    the Kelly multiplier and probability nudges from the multi-agent discussion
    are blended into this agent's decisions (additive integration, never replaces).
    Load via: oasis_ctx = load_oasis_context()

    dmad_consensus_map: per-game damping factors from prior iteration's consensus
    check (built by build_dmad_consensus_map). Keys are "date_home_away" strings.
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

    # ── OASIS: per-trader discussion biases ──────────────────────────────────
    # oasis_kelly_mod  — scalar applied to kelly_adj for every bet this session
    # oasis_prob_nudge — applied per-game to the home-win probability estimate
    _oasis_ctx       = oasis_ctx or {}
    oasis_kelly_mod  = oasis_kelly_modifier(trader_id, _oasis_ctx)
    if oasis_kelly_mod != 1.0:
        print(f"  [oasis] {trader_id} Kelly modifier: {oasis_kelly_mod:.4f}  "
              f"(consensus={_oasis_ctx.get('consensus', {}).get('sentiment', 'n/a')})")

    # ── GAME-LEVEL LEARNING: Load prior bets from season memory ──
    memory = season_memory or {}
    prior_bets = list(memory.get("trader_memories", {}).get(trader_id, []))
    running_bets = list(prior_bets)  # Start with memory from previous iterations

    # Precompute category weights from feature correlations
    feature_corr = memory.get("feature_correlations", {})
    category_weights = {}
    for key, stats in feature_corr.items():
        if stats.get("sample_size", 0) >= 10:
            wr = stats.get("win_rate", 0.5)
            if wr > 0.55:
                category_weights[key] = min(1.5, 1.0 + (wr - 0.55) * 5.0)
            elif wr < 0.40:
                category_weights[key] = max(0.3, 1.0 - (0.40 - wr) * 5.0)

    # Cooldown tracker: games remaining in reduced-bet mode after losing streaks
    loss_cooldown = 0

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

        # ── ROLLING ACCURACY: Compute kelly_adj from recent performance ──
        rolling = _compute_rolling_accuracy(running_bets, window=20)
        kelly_adj = _compute_kelly_adjustment(rolling)

        # Apply loss cooldown (3 losses in row -> reduce for next 5 games)
        if rolling.get("streak_type") == "loss" and rolling.get("streak", 0) >= 3:
            loss_cooldown = 5
        if loss_cooldown > 0:
            kelly_adj *= 0.5
            loss_cooldown -= 1

        # ── ATLAS-GIC DARWINIAN MULTIPLIER ──
        # Compounds the rolling kelly adjustment by the trader's atlas-gic
        # weight (top-quartile traders trend toward 2.5x stake, bottom toward
        # 0.3x). Computed once per day so all bets on a given day share the
        # same Darwinian scale.
        if darwin_weight != 1.0:
            kelly_adj *= darwin_weight

        # ── OASIS SOCIAL DISCUSSION MODIFIER ──
        # Applied once per day after Darwin to layer in peer-discussion signal.
        # oasis_kelly_mod comes from the discussion consensus + trader personality.
        # Bounded 0.70–1.30 by the adapter so it can never dominate.
        if oasis_kelly_mod != 1.0:
            kelly_adj *= oasis_kelly_mod

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
            # ── OASIS probability nudge ──
            # The OASIS discussion may have shifted this trader's home-win
            # prior slightly (confidence_delta in [-0.10, +0.10]).  We apply
            # the nudge to the implied probability before passing it to the
            # model ensemble so the discussion signal propagates through all
            # downstream bet-sizing calculations.
            implied = oasis_prob_nudge(trader_id, _oasis_ctx, implied)
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
            # Tag the game context with OASIS decision so agent_pick_* functions
            # can optionally use it for model/strategy selection
            if _oasis_ctx:
                game_ctx["oasis"] = _oasis_ctx.get("decisions", {}).get(trader_id, {})

            # ── DMAD: look up prior-round consensus damping for this game ──────
            _game_key = f"{key[0]}_{key[1]}_{key[2]}"
            _dmad_map = dmad_consensus_map or {}
            _dmad_damp = _dmad_map.get(_game_key, 1.0)

            # Agent decides all bets for this game
            # Budget per game: split remaining budget across remaining games
            games_remaining = max(1, len(day_games) - day_games.index((key, game_entry, odd)))
            game_budget = bankroll / games_remaining  # Even split of current bankroll
            if TRADERS[trader_id]["personality"] == "aggressive":
                game_budget = bankroll * 0.5  # Aggressive: bet big on each game
            elif TRADERS[trader_id]["personality"] == "conservative":
                game_budget = bankroll * 0.15  # Conservative: small per game

            game_bets = agent_decide_game_bets(
                trader_id, game_ctx, bankroll, game_budget, others_states, comp_state,
                kelly_adj=kelly_adj, category_weights=category_weights,
                dmad_damping=_dmad_damp,
            )

            # ── SOTA: Per-agent enhancements (P6 Heterogeneous Objectives + P9 Coherence Gate) ──
            if _SOTA_AVAILABLE and game_bets:
                # [P6] Apply agent-specific objective function (Sharpe/ROI/Drawdown/WinRate/Kelly)
                game_bets = apply_heterogeneous_objective(trader_id, game_bets)
                # [P9] Coherence gate: reject bets where reasoning contradicts prediction
                game_bets, _rejected = apply_coherence_gate(game_bets)
                # [P4] Rolling Brier weight for this agent
                agent_brier = compute_agent_brier(running_bets, window=50)
                _brier_w = max(0.5, min(1.8, 1.0 / (agent_brier + 0.01) / 4.0))
                for _b in game_bets:
                    _b["bet_size"] = round(_b["bet_size"] * _brier_w, 4)
                    _b["brier_weight"] = round(_brier_w, 4)

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

                # ── RECORD TO RUNNING MEMORY for rolling-window updates ──
                running_bets.append({
                    "game_id": f"{bet['date']}_{bet['game']}",
                    "date": bet["date"],
                    "category": bet.get("category", ""),
                    "strategy": bet.get("strategy_used", ""),
                    "model": bet.get("model_used", ""),
                    "model_prob": bet.get("model_prob", 0.5),
                    "edge_pct": bet.get("edge_pct", 0),
                    "bet_size": round(bet_size, 4),
                    "odds": bet.get("odds", 2.0),
                    "outcome": bet["outcome"],
                    "profit": round(profit, 4),
                    "kelly_fraction": bet.get("kelly_adjustment", 1.0),
                    "game": bet.get("game", ""),
                })

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
            "kelly_adj":  round(kelly_adj, 3),
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
        "nba_bets_history":    all_bets[-500:],
        "nba_all_bets":        all_bets,
        "_new_memory_bets":    running_bets[len(prior_bets):],
        "_rolling_stats":      rolling if day_results else {},
    }


# ── POLITICAL FULL BACKTEST PER AGENT ────────────────────────────────────────

def run_political_backtest_for_agent(trader_id: str, events: List[Dict],
                                     social_snapshots: List[Tuple[str, Dict]],
                                     latest_signals: Dict,
                                     others_states: Dict) -> Dict:
    """
    Run full multi-day political ETF trading backtest for one AI agent.
    Iterates through each day of political events, makes decisions, tracks P&L.
    """
    capital = TRADERS[trader_id]["bankroll_political"]
    peak_capital = capital
    max_drawdown = 0.0
    total_trades = 0
    total_wins = 0
    total_losses = 0
    total_wagered = 0.0
    total_pnl = 0.0
    all_trades: List[Dict] = []
    day_results: List[Dict] = []
    sector_pnl: Dict[str, float] = defaultdict(float)
    strategy_pnl: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0})
    ticker_pnl: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0})

    pol_cfg = POLITICAL_TRADER_PROFILES.get(trader_id, {})
    primary_strat = pol_cfg.get("primary_strategy", TRADERS[trader_id].get("pol_approach", "momentum"))

    # Group events by date
    events_by_date: Dict[str, List[Dict]] = defaultdict(list)
    for ev in events:
        d = ev.get("date", "")
        if d:
            events_by_date[d].append(ev)
    sorted_dates = sorted(events_by_date.keys())

    # Map social snapshots to dates
    signal_by_date: Dict[str, Dict] = {}
    for ts, sigs in social_snapshots:
        try:
            d = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            signal_by_date[d] = sigs
        except Exception:
            continue
    if latest_signals:
        for d in sorted_dates:
            if d not in signal_by_date:
                signal_by_date[d] = latest_signals

    for day_num, day_date in enumerate(sorted_dates, 1):
        if capital <= 0:
            break

        day_events = events_by_date.get(day_date, [])
        day_signals = signal_by_date.get(day_date, latest_signals)

        positions = political_agent_decide_positions(
            trader_id, day_date, capital,
            day_signals, day_events, others_states,
            existing_positions=0,
        )

        day_pnl = 0.0
        day_trade_count = 0
        day_strategies = set()
        day_sectors = set()

        for pos in positions:
            total_trades += 1
            day_trade_count += 1
            pnl = pos["pnl"]
            total_wagered += pos["position_size"]
            total_pnl += pnl
            day_pnl += pnl

            if pnl > 0:
                total_wins += 1
                strategy_pnl[pos["strategy_used"]]["wins"] += 1
                ticker_pnl[pos["ticker"]]["wins"] += 1
            else:
                total_losses += 1

            capital += pnl
            sector_pnl[pos.get("sector", "unknown")] += pnl
            strategy_pnl[pos["strategy_used"]]["count"] += 1
            strategy_pnl[pos["strategy_used"]]["pnl"] += pnl
            ticker_pnl[pos["ticker"]]["count"] += 1
            ticker_pnl[pos["ticker"]]["pnl"] += pnl
            day_strategies.add(pos["strategy_used"])
            day_sectors.add(pos.get("sector", "unknown"))

            pos["capital_after"] = round(capital, 2)
            all_trades.append(pos)

        if capital > peak_capital:
            peak_capital = capital
        dd = 1.0 - capital / peak_capital if peak_capital > 0 else 0.0
        if dd > max_drawdown:
            max_drawdown = dd

        day_results.append({
            "day": day_num, "date": day_date, "trades": day_trade_count,
            "events": len(day_events), "pnl": round(day_pnl, 2),
            "capital": round(capital, 2), "strategies": list(day_strategies),
            "sectors": list(day_sectors),
        })

    roi_pct = round((capital - POLITICAL_INITIAL_CAPITAL) / POLITICAL_INITIAL_CAPITAL * 100, 4)

    # Compute Sharpe
    sharpe = 0.0
    if len(day_results) > 1:
        daily_rets = [d["pnl"] for d in day_results]
        avg_r = sum(daily_rets) / len(daily_rets)
        std_r = (sum((r - avg_r) ** 2 for r in daily_rets) / len(daily_rets)) ** 0.5
        if std_r > 0:
            sharpe = round((avg_r / std_r) * (252 ** 0.5), 3)

    # Strategy breakdown
    strategy_breakdown = {}
    for strat, stats in strategy_pnl.items():
        strategy_breakdown[strat] = {
            "trades": stats["count"], "pnl": round(stats["pnl"], 2),
            "wins": stats["wins"],
            "win_rate": round(stats["wins"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0,
        }

    sector_breakdown = {s: round(pnl_val, 2) for s, pnl_val in sorted(sector_pnl.items(), key=lambda x: -x[1])}

    ticker_breakdown = {}
    for t, stats in sorted(ticker_pnl.items(), key=lambda x: -x[1]["pnl"]):
        ticker_breakdown[t] = {
            "trades": stats["count"], "pnl": round(stats["pnl"], 2),
            "wins": stats["wins"],
            "win_rate": round(stats["wins"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0,
        }

    return {
        "trader_id":                     trader_id,
        "political_bankroll":            round(capital, 2),
        "political_roi_pct":             roi_pct,
        "political_sharpe":              sharpe,
        "political_total_trades":        total_trades,
        "political_wins":                total_wins,
        "political_losses":              total_losses,
        "political_win_rate":            round(total_wins / total_trades * 100, 1) if total_trades > 0 else 0,
        "political_total_wagered":       round(total_wagered, 2),
        "political_total_pnl":           round(total_pnl, 2),
        "political_peak_capital":        round(peak_capital, 2),
        "political_max_drawdown":        round(max_drawdown, 4),
        "political_trading_days":        len(day_results),
        "political_approach":            primary_strat,
        "political_strategy_breakdown":  strategy_breakdown,
        "political_sector_breakdown":    sector_breakdown,
        "political_ticker_breakdown":    ticker_breakdown,
        "political_day_results":         day_results,
        "political_trades_history":      all_trades[-500:],
        "political_all_trades":          all_trades,
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
            "political_bankroll":     state.get("political_bankroll", 100_000.0),
            "political_roi_pct":      pol_roi,
            "political_sharpe":       state.get("political_sharpe", 0.0),
            "political_approach":     state.get("political_approach", ""),
            "political_total_trades": state.get("political_total_trades", 0),
            "political_wins":         state.get("political_wins", 0),
            "political_losses":       state.get("political_losses", 0),
            "political_win_rate":     state.get("political_win_rate", 0.0),
            "political_max_drawdown": state.get("political_max_drawdown", 0.0),
            "combined_score":     round(combined, 4),
            "eliminated":         state.get("nba_eliminated_day") is not None,
            "darwin_weight":      state.get("darwin_weight", 1.0),
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
    print(f"Trading Floor v9 — iteration {it_data['iteration']}")
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

    print("Loading political events...")
    pol_events = load_political_events()
    print(f"  Political events: {len(pol_events)}")

    print("Loading social snapshots...")
    social_snapshots = load_all_social_snapshots()
    print(f"  Social snapshots: {len(social_snapshots)}")

    pol_event_dates = sorted(set(e.get("date", "") for e in pol_events if e.get("date")))
    print(f"  Political trading days: {len(pol_event_dates)}")

    print("Loading department status...")
    dept_data = load_department_status()

    TRADERS_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "political").mkdir(parents=True, exist_ok=True)

    # ── LOAD SEASON MEMORY for game-level learning ──
    season_memory = _load_season_memory()
    print(f"Season memory: {sum(len(v) for v in season_memory.get('trader_memories', {}).values())} prior bets across {len(season_memory.get('trader_memories', {}))} traders")
    if season_memory.get("feature_correlations"):
        print(f"  Feature correlations: {len(season_memory['feature_correlations'])} features tracked")

    # ── LOAD ATLAS-GIC DARWINIAN WEIGHTS (Cycle 13) ──
    darwin_weights = _load_darwin_weights()
    if darwin_weights:
        snippet = ", ".join(f"{tid}={w:.3f}" for tid, w in sorted(darwin_weights.items()))
        print(f"Darwin weights : {snippet}")
    else:
        print("Darwin weights : none yet (will seed at 1.0)")

    # ── LOAD OASIS SOCIAL DISCUSSION (additive signal layer) ─────────────────
    # If data/arena/oasis-discussions/YYYY-MM-DD.json exists for today, load it.
    # If not, oasis_ctx will be {} and all oasis_* helpers are no-ops.
    # To generate today's discussion: python3 scripts/arena/oasis_adapter.py
    today_str = date.today().isoformat()
    oasis_ctx = load_oasis_context(today_str)
    if oasis_ctx:
        oasis_mode = oasis_ctx.get("mode", "lite")
        oasis_sentiment = oasis_ctx.get("consensus", {}).get("sentiment", "n/a")
        oasis_conf = oasis_ctx.get("consensus", {}).get("home_confidence", 0.5)
        print(f"OASIS discussion : {today_str}  mode={oasis_mode}"
              f"  consensus={oasis_sentiment}  home_conf={oasis_conf:.3f}")
    else:
        print("OASIS discussion : none for today (run oasis_adapter.py to generate)")

    # ── DMAD: build prior-round consensus map from all existing state files ────
    # Load ALL trader states to determine which games had consensus last run.
    # Any game where >= CONSENSUS_THRESHOLD agents agreed → Kelly x0.60 this run.
    _all_prior_states: Dict[str, Dict] = {}
    for _tid in TRADERS:
        _sf = TRADERS_DIR / f"{_tid}-state.json"
        if _sf.exists():
            try:
                _all_prior_states[_tid] = json.loads(_sf.read_text())
            except Exception:
                pass
    dmad_consensus_map = build_dmad_consensus_map(_all_prior_states)
    if _DMAD_AVAILABLE:
        _dmad_role_summary = {tid: NBA_DMAD_PROFILES.get(tid, {}).get("name", "?") for tid in TRADERS}
        print(f"DMAD profiles    : {_dmad_role_summary}")
        print(f"DMAD consensus   : {len(dmad_consensus_map)} game(s) flagged from prior run")
    else:
        print("DMAD             : not available (dmad_profiles.py missing)")

    all_results: Dict[str, Dict] = {}

    for trader_id in TRADERS:
        cfg = TRADERS[trader_id]
        pol_profile = POLITICAL_TRADER_PROFILES.get(trader_id, {})
        pol_strat = pol_profile.get("primary_strategy", cfg.get("pol_approach", "momentum"))
        dw = darwin_weights.get(trader_id, 1.0)
        dw_tag = f" darwin={dw:.3f}" if dw != 1.0 else ""
        _dmad_role = NBA_DMAD_PROFILES.get(trader_id, {}).get("name", "") if _DMAD_AVAILABLE else ""
        _dmad_tag = f" dmad={_dmad_role}" if _dmad_role else ""
        print(f"\nAgent [{trader_id}] — {cfg['personality']} / NBA + Political ({pol_strat}){dw_tag}{_dmad_tag}")
        others = load_other_trader_states(trader_id)
        pol_others = load_political_trader_states(trader_id)

        nba_result = run_nba_backtest_for_agent(trader_id, matched, others, all_games_sorted,
                                                 season_memory=season_memory,
                                                 darwin_weight=dw,
                                                 oasis_ctx=oasis_ctx,
                                                 dmad_consensus_map=dmad_consensus_map)
        pol_result = run_political_backtest_for_agent(
            trader_id, pol_events, social_snapshots, signals, pol_others)

        state = {
            "trader_id":      trader_id,
            "name":           cfg["name"],
            "provider":       cfg["provider"],
            "personality":    cfg["personality"],
            "risk_tolerance": cfg["risk_tolerance"],
            "darwin_weight":  round(dw, 4),
            **nba_result,
            **{k: v for k, v in pol_result.items() if k != "political_all_trades"},
            "saw_others":     list(others.keys()),
            "run_timestamp":  datetime.now(timezone.utc).isoformat(),
        }

        # Save NBA state
        (TRADERS_DIR / f"{trader_id}-state.json").write_text(json.dumps(state, indent=2))

        # Save political state separately (with full trade history)
        pol_save_state = {k: v for k, v in pol_result.items() if k != "political_all_trades"}
        pol_save_state["name"] = cfg["name"]
        pol_save_state["provider"] = cfg["provider"]
        pol_save_state["personality"] = cfg["personality"]
        (TRADERS_DIR / f"political-{trader_id}-state.json").write_text(
            json.dumps(pol_save_state, indent=2))

        # Full state in memory includes all_trades for doc generation
        all_results[trader_id] = {**state, **pol_result}

        print(f"  NBA      : ${nba_result['nba_bankroll']:.2f}  ROI {nba_result['nba_roi_pct']:+.1f}%"
              f"  Sharpe {nba_result['nba_sharpe']:.2f}"
              f"  ({nba_result['nba_wins']}W-{nba_result['nba_losses']}L)")
        print(f"  Political: ${pol_result['political_bankroll']:,.2f}"
              f"  ROI {pol_result['political_roi_pct']:+.4f}%"
              f"  Sharpe {pol_result['political_sharpe']:.3f}"
              f"  ({pol_result['political_wins']}W-{pol_result['political_losses']}L"
              f"  {pol_result['political_total_trades']} trades)")

    # ── SOTA: Cross-agent enhancements (P2 Debate, P5 Opinion, P7 Belief, P10 Whale) ──
    if _SOTA_AVAILABLE:
        _sota_enhancer = SOTAEnhancer()
        # Collect all agent bets and compute cross-agent metrics
        _all_agent_bets = {tid: res.get("nba_all_bets", []) for tid, res in all_results.items()}
        _all_agent_probs = {}
        for tid, res in all_results.items():
            # Average model probability across all bets as agent's "belief"
            bets = res.get("nba_all_bets", [])
            if bets:
                _all_agent_probs[tid] = sum(b.get("model_prob", 0.5) for b in bets) / len(bets)
            else:
                _all_agent_probs[tid] = 0.5
        _agent_histories = {tid: res.get("nba_all_bets", []) for tid, res in all_results.items()}

        # Apply cross-agent enhancements
        _enhanced = _sota_enhancer.enhance_game(
            "full_season", _all_agent_bets, _all_agent_probs, _agent_histories
        )
        # Get SOTA summary and persist to state
        _sota_summary = _sota_enhancer.get_enhancement_summary()
        for tid in all_results:
            all_results[tid]["sota_papers_active"] = _sota_summary["papers_implemented"]
            all_results[tid]["sota_techniques"] = _sota_summary["techniques"]
            all_results[tid]["sota_debates"] = _sota_summary["debates_triggered"]
            _pnl = _sota_summary["agent_pnl"].get(tid, {})
            all_results[tid]["sota_pnl_capital"] = _pnl.get("capital", 100.0)
            all_results[tid]["sota_pnl_sharpe"] = _pnl.get("sharpe", 0.0)
            all_results[tid]["sota_pnl_max_dd"] = _pnl.get("max_drawdown_pct", 0.0)
        print(f"\nSOTA papers      : {_sota_summary['papers_implemented']} active")
        print(f"SOTA techniques  : {', '.join(_sota_summary['techniques'][:5])}...")
        print(f"SOTA debates     : {_sota_summary['debates_triggered']} triggered")
        for tid, pnl in _sota_summary["agent_pnl"].items():
            print(f"  P1 {tid}: ${pnl.get('capital', 0):.2f}  "
                  f"ROI {pnl.get('roi_pct', 0):+.1f}%  "
                  f"Sharpe {pnl.get('sharpe', 0):.2f}  "
                  f"MaxDD {pnl.get('max_drawdown_pct', 0):.1f}%")
    else:
        print("\nSOTA techniques  : not available (sota_techniques.py missing)")

    board     = build_leaderboard(all_results)
    cc_status = build_command_center_status(dept_data)

    # ── DMAD: compute divergence metrics for this iteration ───────────────────
    if _DMAD_AVAILABLE:
        _dmad_all_bets: Dict[str, list] = {
            tid: res.get("nba_all_bets", []) for tid, res in all_results.items()
        }
        _dmad_div = compute_dmad_divergence(_dmad_all_bets)
        _health_tag = "HEALTHY" if _dmad_div["healthy"] else "GROUPTHINK RISK"
        print(f"\nDMAD divergence  : {_dmad_div['divergence']:.3f}  "
              f"consensus_events={_dmad_div['consensus_events']}  [{_health_tag}]")
        if not _dmad_div["healthy"]:
            print("  WARNING: Low divergence — agents may be reasoning too similarly. "
                  "Check DMAD profiles.")
        # Persist divergence to state for dashboard display
        for tid in all_results:
            all_results[tid]["dmad_divergence"] = _dmad_div["divergence"]
            all_results[tid]["dmad_consensus_games"] = _dmad_div["consensus_events"]
            all_results[tid]["dmad_healthy"] = _dmad_div["healthy"]

    # ── UPDATE SEASON MEMORY with new bets from this iteration ──
    for tid, res in all_results.items():
        new_bets = res.get("_new_memory_bets", [])
        if new_bets:
            if tid not in season_memory.get("trader_memories", {}):
                season_memory.setdefault("trader_memories", {})[tid] = []
            season_memory["trader_memories"][tid].extend(new_bets)

    season_memory["last_iteration"] = it_data["iteration"]

    # Update Bayesian posteriors
    season_memory["strategy_posteriors"] = _compute_bayesian_posteriors(season_memory)

    # Update feature correlations
    season_memory["feature_correlations"] = _compute_feature_correlations(season_memory)

    # Check for Bayesian strategy deaths
    dead_strats = _check_dead_strategies(season_memory)
    if dead_strats:
        print(f"  Bayesian deaths: {dead_strats}")

    # Save season memory
    _save_season_memory(season_memory)
    total_mem = sum(len(v) for v in season_memory.get("trader_memories", {}).values())
    print(f"Season memory saved: {total_mem} total bets, {len(season_memory.get('strategy_posteriors', {}))} posteriors")

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
            "version":            "trading-floor-v9",
            "generated":          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date":               date.today().isoformat(),
            "traders":            len(TRADERS),
            "nba_models":         len(MODELS),
            "nba_strategies":     len(STRATEGIES),
            "nba_strategies_eliminated": len(ELIMINATED_STRATEGIES),
            "matched_games":      len(matched),
            "political_tickers":  len(signals),
            "political_events":   len(pol_events),
            "political_trading_days": len(pol_event_dates),
            "political_strategies": len(POLITICAL_STRATEGIES),
            "political_strategies_eliminated": len(ELIMINATED_POLITICAL_STRATEGIES),
            "etf_universe":       len(ETF_UNIVERSE),
        },
        "eliminations": eliminations,
        "leaderboard": board,
        "traders": {
            tid: {k: v for k, v in s.items()
                  if k not in ("nba_day_results", "nba_bets_history", "nba_all_bets", "political_day_results", "political_trades_history", "political_all_trades", "political_ticker_breakdown")}
            for tid, s in all_results.items()
        },
        "command_centers": cc_status,
        "models":     {m: {"brier": cfg["brier"]} for m, cfg in MODELS.items()},
        "strategies": {s: {"family": cfg["family"], "max_pct": cfg["max_pct"]}
                       for s, cfg in STRATEGIES.items()},
        "political_strategies": {s: {"family": cfg["family"], "position_pct": cfg["position_pct"]}
                                 for s, cfg in POLITICAL_STRATEGIES.items()},
        "etf_universe": {t: {"name": v["name"], "sector": v["sector"], "type": v.get("type", "etf")}
                         for t, v in ETF_UNIVERSE.items()},
    }

    latest = DATA_DIR / "trading-floor-v4-latest.json"
    dated  = DATA_DIR / f"trading-floor-v4-{date.today().isoformat()}.json"
    latest.write_text(json.dumps(output, indent=2))
    dated.write_text(json.dumps(output, indent=2))
    print(f"\nSaved: {latest}")
    print(f"Saved: {dated}")
    print(f"Iteration: {it_data['iteration']}  Generation: {it_data['generation']}")
    print(f"Active NBA strategies: {len(STRATEGIES)}  Eliminated: {len(ELIMINATED_STRATEGIES)}")
    print(f"Active Political strategies: {len(POLITICAL_STRATEGIES)}  Eliminated: {len(ELIMINATED_POLITICAL_STRATEGIES)}")

    # Also save political-specific output for compatibility with political-trading-floor.py consumers
    pol_output = {
        "iteration": it_data["iteration"],
        "generation": it_data["generation"],
        "meta": {
            "version": "political-trading-floor-integrated-v1",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": date.today().isoformat(),
            "traders": len(TRADERS),
            "strategies": len(POLITICAL_STRATEGIES),
            "eliminated": len(ELIMINATED_POLITICAL_STRATEGIES),
            "events_total": len(pol_events),
            "trading_days": len(pol_event_dates),
            "social_tickers": len(signals),
            "etf_universe": len(ETF_UNIVERSE),
        },
        "leaderboard": [{
            "rank": e["rank"], "trader_id": e["trader_id"], "name": e["name"],
            "provider": e["provider"], "personality": e["personality"],
            "capital": e.get("political_bankroll", 100000),
            "roi_pct": e.get("political_roi_pct", 0),
            "sharpe": e.get("political_sharpe", 0),
            "total_trades": e.get("political_total_trades", 0),
            "wins": e.get("political_wins", 0),
            "losses": e.get("political_losses", 0),
            "win_rate": e.get("political_win_rate", 0),
            "max_drawdown": e.get("political_max_drawdown", 0),
            "primary_strategy": POLITICAL_TRADER_PROFILES.get(e["trader_id"], {}).get("primary_strategy", ""),
        } for e in board],
        "traders": {
            tid: {k: v for k, v in s.items()
                  if k.startswith("political_") and k not in ("political_day_results",
                                                               "political_trades_history",
                                                               "political_all_trades",
                                                               "political_ticker_breakdown")}
            for tid, s in all_results.items()
        },
        "strategies": {s: {"family": cfg_s["family"], "position_pct": cfg_s["position_pct"]}
                       for s, cfg_s in POLITICAL_STRATEGIES.items()},
        "eliminations": {
            "strategies": ELIMINATED_POLITICAL_STRATEGIES,
            "coffins": [{"name": k, **v, "type": "political_strategy"}
                        for k, v in ELIMINATED_POLITICAL_STRATEGIES.items()],
        },
        "etf_universe": {t: {"name": v["name"], "sector": v["sector"], "type": v.get("type", "etf")}
                         for t, v in ETF_UNIVERSE.items()},
    }
    pol_latest = (DATA_DIR / "political" / "political-trading-floor-latest.json")
    pol_dated = (DATA_DIR / "political" / f"political-trading-floor-{date.today().isoformat()}.json")
    pol_latest.write_text(json.dumps(pol_output, indent=2))
    pol_dated.write_text(json.dumps(pol_output, indent=2))
    print(f"Saved political: {pol_latest}")

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


def generate_political_season_doc(trader_id: str, state: Dict, board: List[Dict]) -> str:
    """Generate full markdown season document for one agent's political trading."""
    cfg = TRADERS[trader_id]
    pol_cfg = POLITICAL_TRADER_PROFILES.get(trader_id, {})
    all_trades = state.get("political_all_trades", state.get("political_trades_history", []))
    day_results = state.get("political_day_results", [])

    lines = []
    lines.append(f"# Political Trading Season 2025-26 -- Agent {cfg['name'].upper()}")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(f"- **Provider:** {cfg['provider']}")
    lines.append(f"- **Personality:** {cfg['personality']}")
    lines.append(f"- **Risk Tolerance:** {cfg['risk_tolerance']}")
    pol_strat = pol_cfg.get('primary_strategy', state.get('political_approach', '?'))
    lines.append(f"- **Primary Strategy:** {pol_strat}")
    lines.append(f"- **Secondary:** {', '.join(pol_cfg.get('secondary_strategies', []))}")
    lines.append(f"- **Initial Capital:** ${POLITICAL_INITIAL_CAPITAL:,.2f}")
    lines.append(f"- **Final Capital:** ${state.get('political_bankroll', 0):,.2f}")
    lines.append(f"- **ROI:** {state.get('political_roi_pct', 0):+,.4f}%")
    lines.append(f"- **Sharpe Ratio:** {state.get('political_sharpe', 0):.3f}")
    lines.append(f"- **Record:** {state.get('political_wins', 0)}W-{state.get('political_losses', 0)}L")
    lines.append(f"- **Win Rate:** {state.get('political_win_rate', 0):.1f}%")
    lines.append(f"- **Peak Capital:** ${state.get('political_peak_capital', 0):,.2f}")
    lines.append(f"- **Max Drawdown:** {state.get('political_max_drawdown', 0)*100:.1f}%")
    lines.append(f"- **Wagered:** ${state.get('political_total_wagered', 0):,.2f}")
    lines.append("")

    # Peer comparison
    lines.append("## Peer Comparison")
    lines.append("| Rank | Agent | Capital | ROI | Sharpe | WR | Trades |")
    lines.append("|------|-------|---------|-----|--------|-----|--------|")
    for entry in board:
        marker = " **" if entry["trader_id"] == trader_id else ""
        lines.append(
            f"| {entry['rank']} | {entry['name']}{marker} | "
            f"${entry.get('political_bankroll', 0):,.2f} | "
            f"{entry.get('political_roi_pct', 0):+,.4f}% | "
            f"{entry.get('political_sharpe', 0):.3f} | "
            f"{entry.get('political_win_rate', 0):.1f}% | "
            f"{entry.get('political_total_trades', 0)} |"
        )
    lines.append("")

    # Strategy performance
    strat_bd = state.get("political_strategy_breakdown", {})
    if strat_bd:
        lines.append("## Strategy Performance")
        lines.append("| Strategy | Trades | P&L | Win Rate |")
        lines.append("|----------|--------|-----|----------|")
        for s, stats in sorted(strat_bd.items(), key=lambda x: -x[1].get("pnl", 0)):
            lines.append(f"| {s} | {stats['trades']} | ${stats['pnl']:+,.2f} | {stats['win_rate']:.1f}% |")
        lines.append("")

    # Sector performance
    sector_bd = state.get("political_sector_breakdown", {})
    if sector_bd:
        lines.append("## Sector Performance")
        lines.append("| Sector | P&L |")
        lines.append("|--------|-----|")
        for s, pnl_val in sector_bd.items():
            lines.append(f"| {s} | ${pnl_val:+,.2f} |")
        lines.append("")

    # Day-by-day
    if day_results:
        lines.append("## Day-by-Day Results")
        lines.append("| Day | Date | Events | Trades | P&L | Capital |")
        lines.append("|-----|------|--------|--------|-----|---------|")
        for d in day_results:
            lines.append(
                f"| {d['day']} | {d['date']} | {d.get('events', 0)} | {d['trades']} | "
                f"${d['pnl']:+,.2f} | ${d['capital']:,.2f} |"
            )
        lines.append("")

    # Sample trades
    if all_trades:
        lines.append(f"## Trade Log (first 30 + last 30 of {len(all_trades)} total)")
        lines.append("")
        sample = all_trades[:30] + (all_trades[-30:] if len(all_trades) > 60 else [])
        for i, tr in enumerate(sample):
            if i == 30 and len(all_trades) > 60:
                lines.append(f"*... ({len(all_trades) - 60} trades omitted) ...*")
                lines.append("")
            lines.append(f"### {tr.get('date', '?')} | {tr.get('ticker', '?')} | {tr.get('direction', '?')}")
            lines.append(f"- **Strategy:** {tr.get('strategy_used', '?')} | **Signal:** {tr.get('signal_strength', 0):.3f}")
            lines.append(f"- **Size:** ${tr.get('position_size', 0):,.2f} | **Return:** {tr.get('trade_return', 0)*100:+.3f}%")
            lines.append(f"- **{tr.get('outcome', '?')}** -> P&L ${tr.get('pnl', 0):+,.2f}")
            lines.append(f"- **Reasoning:** {tr.get('reasoning', '')}")
            lines.append("")

    return "\n".join(lines)


def generate_all_season_docs(all_results: Dict, board: List[Dict]) -> None:
    """Generate season doc for all 5 agents (NBA + Political)."""
    docs_dir = DATA_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for tid, state in all_results.items():
        # NBA season doc
        doc = generate_agent_season_doc(tid, state, board)
        doc_path = docs_dir / f"{tid}-season-2025-26.md"
        doc_path.write_text(doc)
        print(f"  NBA season doc: {doc_path} ({len(doc)} chars)")

        # Political season doc
        pol_doc = generate_political_season_doc(tid, state, board)
        pol_doc_path = docs_dir / f"political-{tid}-season-2025-26.md"
        pol_doc_path.write_text(pol_doc)
        print(f"  Political season doc: {pol_doc_path} ({len(pol_doc)} chars)")


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
    v9 Enhanced mutation with 3 learning mechanisms:
    1. STRATEGY THEFT: 20% chance losing traders copy winner's strategy
    2. BAYESIAN SELECTION: Use posterior probabilities to weight strategy choices
    3. CORRELATION-BASED: Mutate toward strategy+category combos that win
    Returns mutation log per trader.
    """
    board = result.get("leaderboard", [])
    if len(board) < 2:
        return {}

    # Load season memory for Bayesian priors and feature correlations
    season_memory = _load_season_memory()
    posteriors = season_memory.get("strategy_posteriors", {})
    feature_corr = season_memory.get("feature_correlations", {})

    winner = board[0]
    loser  = board[-1]
    winner_id = winner["trader_id"]
    loser_id  = loser["trader_id"]

    mutations = {}

    # ── 1. STRATEGY THEFT (20% chance per losing trader) ──
    # Any trader below winner can "steal" winner's most profitable strategy
    winner_sf = TRADERS_DIR / f"{winner_id}-state.json"
    winner_best_strat = None
    winner_best_profit_strat = None

    if winner_sf.exists():
        try:
            ws = json.loads(winner_sf.read_text())
            # Find winner's most profitable strategy (not just most used)
            strat_profit = defaultdict(float)
            strat_count = defaultdict(int)
            for b in ws.get("nba_bets_history", []):
                s = b.get("strategy_used", "")
                strat_profit[s] += b.get("profit", 0)
                strat_count[s] += 1
            if strat_profit:
                # Most profitable by total P&L
                winner_best_profit_strat = max(strat_profit, key=strat_profit.get)
                # Most used (fallback)
                winner_best_strat = max(strat_count, key=strat_count.get)
        except Exception:
            pass

    for entry in board[1:]:  # All non-winners
        tid = entry["trader_id"]
        roi = entry.get("nba_roi_pct", 0)

        # Strategy theft: 20% chance, higher if losing badly
        steal_chance = 0.20
        if roi < -20:
            steal_chance = 0.40  # Desperate traders steal more
        elif roi < 0:
            steal_chance = 0.30

        stolen_strat = winner_best_profit_strat or winner_best_strat
        if stolen_strat and stolen_strat in STRATEGIES and random.random() < steal_chance:
            trader_cfg = TRADERS[tid]
            if stolen_strat not in trader_cfg["preferred_strategies"]:
                old_prefs = list(trader_cfg["preferred_strategies"])
                trader_cfg["preferred_strategies"] = [stolen_strat] + old_prefs[:2]
                mutations[tid] = {
                    "type": "strategy_theft",
                    "from_trader": winner_id,
                    "stolen_strategy": stolen_strat,
                    "old_preferences": old_prefs,
                    "new_preferences": trader_cfg["preferred_strategies"],
                    "steal_probability": steal_chance,
                    "reason": f"{tid} (ROI {roi:+.1f}%) steals '{stolen_strat}' from {winner_id} "
                              f"(ROI {winner['nba_roi_pct']:+.1f}%)",
                }
                # Track steal in season memory
                season_memory.setdefault("cross_trader_steals", []).append({
                    "from": winner_id, "to": tid, "strategy": stolen_strat,
                    "iteration": result.get("iteration", 0),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                print(f"  [STEAL] {tid} steals '{stolen_strat}' from {winner_id} (p={steal_chance:.0%})")

    # ── 2. BAYESIAN STRATEGY SELECTION for stagnant traders ──
    # If posteriors exist, stagnant traders replace their worst strategy with the
    # highest-posterior strategy they don't already have
    if posteriors:
        top_posterior_strats = sorted(posteriors.items(), key=lambda x: x[1], reverse=True)
        for entry in board:
            tid = entry["trader_id"]
            if tid in mutations:
                continue  # Already mutated this iteration
            roi = entry.get("nba_roi_pct", 0)
            if abs(roi) < 5.0:  # Stagnant (near zero ROI)
                trader_cfg = TRADERS[tid]
                current_strats = trader_cfg["preferred_strategies"]
                # Find highest-posterior strategy not in current set
                for strat, post in top_posterior_strats:
                    if strat not in current_strats and strat in STRATEGIES and strat not in ELIMINATED_STRATEGIES:
                        old_prefs = list(current_strats)
                        # Replace the last (worst) strategy
                        trader_cfg["preferred_strategies"] = current_strats[:2] + [strat]
                        mutations[tid] = {
                            "type": "bayesian_swap",
                            "added_strategy": strat,
                            "posterior": post,
                            "old_preferences": old_prefs,
                            "new_preferences": trader_cfg["preferred_strategies"],
                            "reason": f"{tid} stagnant (ROI {roi:+.1f}%) — Bayesian swap: add '{strat}' (posterior {post:.4f})",
                        }
                        print(f"  [BAYESIAN] {tid} swaps in '{strat}' (posterior {post:.4f})")
                        break

    # ── 3. CORRELATION-BASED MODEL MUTATIONS ──
    # If feature correlations show a model performs well, push traders toward it
    if feature_corr:
        # Find best model from correlations
        model_scores = defaultdict(lambda: {"profit": 0.0, "count": 0})
        for key, stats in feature_corr.items():
            if "strat=" in key and "|cat=" in key and stats.get("sample_size", 0) >= 20:
                # Not model-specific, but strategy-category combos tell us what works
                pass

        # Check per-trader: if their preferred model has low correlation scores,
        # adopt winner's model
        for entry in board[1:]:
            tid = entry["trader_id"]
            if tid in mutations:
                continue
            if entry.get("nba_roi_pct", 0) < -10:
                winner_models = TRADERS[winner_id]["preferred_models"]
                current_models = TRADERS[tid]["preferred_models"]
                if winner_models and winner_models[0] not in current_models:
                    old_models = list(current_models)
                    TRADERS[tid]["preferred_models"] = [winner_models[0]] + current_models[:2]
                    mutations[tid] = {
                        "type": "correlation_model_swap",
                        "from_trader": winner_id,
                        "adopted_model": winner_models[0],
                        "old_models": old_models,
                        "new_models": TRADERS[tid]["preferred_models"],
                        "reason": f"{tid} losing (ROI {entry['nba_roi_pct']:+.1f}%) — adopts model '{winner_models[0]}' from {winner_id}",
                    }
                    print(f"  [CORR-MODEL] {tid} adopts model '{winner_models[0]}' from {winner_id}")

    # Persist mutations and updated season memory
    if mutations:
        _save_evolved_trader_configs()
        _save_season_memory(season_memory)
        print(f"  [PERSIST] Saved {len(mutations)} mutations to {TRADER_CONFIG_FILE}")

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
    print("TRADING FLOOR v9 — KARPATHY LOOP (with Game-Level Learning)")
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

        # v9: Learning metrics
        "learning": {
            "season_memory_bets": sum(
                len(v) for v in _load_season_memory().get("trader_memories", {}).values()
            ),
            "bayesian_posteriors": _load_season_memory().get("strategy_posteriors", {}),
            "feature_correlations_count": len(
                _load_season_memory().get("feature_correlations", {})
            ),
            "cross_trader_steals": len(
                _load_season_memory().get("cross_trader_steals", [])
            ),
            "trader_rolling_stats": {
                tid: res.get("_rolling_stats", {})
                for tid, res in result.get("traders", {}).items()
                if res.get("_rolling_stats")
            },
        },

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
    "nomos-nba-agent":       ROOT.parent / "nomos-nba-agent",
    "nomos-political-alpha": ROOT.parent / "nomos-political-alpha",
    "rgwa":                  ROOT.parent / "rgwa",
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
                 f"data: trading floor v9 iter {it_data['iteration']} — auto",
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
                lines[i] = f"> **Last updated:** {now} | **Auto-refreshed by:** trading-floor-v9 cron"
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
    print(f"\n[v9] Received signal {sig} — stopping after current iteration.")
    _STOP_FLAG = True

def run_continuous_iteration(max_iterations: int = 0, delay_seconds: int = 10):
    """
    Trading Floor v9 continuous iteration mode.
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
    print("TRADING FLOOR v9 — CONTINUOUS ITERATION MODE")
    print(f"Max iterations: {'infinite' if max_iterations == 0 else max_iterations}")
    print(f"Delay between iterations: {delay_seconds}s")
    print("Send SIGINT/SIGTERM to stop gracefully.")
    print("=" * 70)

    while not _STOP_FLAG:
        iteration_count += 1
        if max_iterations > 0 and iteration_count > max_iterations:
            print(f"\n[v9] Reached max iterations ({max_iterations}). Stopping.")
            break

        cycle_start = time.time()
        it_data = _load_iteration()
        print(f"\n{'='*60}")
        print(f"[v9] CYCLE {iteration_count} — iteration {it_data['iteration'] + 1}")
        print(f"{'='*60}")

        # Phase 1: Sync satellite repos
        print("\n[v9] Phase 1: Syncing satellite repos...")
        sync_status = sync_satellite_repos()
        for repo, status in sync_status.items():
            print(f"  {repo}: {status}")

        # Phase 2: Load cross-repo data
        print("\n[v9] Phase 2: Loading cross-repo karpathy data...")
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
        print("\n[v9] Phase 3: Running Karpathy loop...")
        karpathy_result = run_karpathy_loop()

        # Inject cross-repo data into output
        karpathy_result["cross_repo"] = {
            "sync_status": sync_status,
            "satellite_data": {k: {"status": v.get("status", "loaded")} for k, v in cross_data.items()},
        }

        # Phase 4: Guardian cross-pollination
        print("\n[v9] Phase 4: Guardian cross-pollination...")
        guardian_result = run_guardian_cross_pollination()
        print(f"  Guardian: {guardian_result.get('status')}")

        # Phase 5: Update OPERATIONS.md
        print("\n[v9] Phase 5: Updating OPERATIONS.md...")
        update_operations_md()

        # Phase 6: Push to Git
        print("\n[v9] Phase 6: Pushing to Git...")
        pushed = push_results_to_git()
        print(f"  Pushed: {'yes' if pushed else 'no changes'}")

        cycle_elapsed = time.time() - cycle_start
        print(f"\n[v9] Cycle {iteration_count} complete in {cycle_elapsed:.1f}s")
        print(f"  Iteration: {karpathy_result.get('iteration')}")
        print(f"  Best: ${karpathy_result.get('optimization', {}).get('current_best', 0):,.0f}")
        print(f"  Improved: {karpathy_result.get('optimization', {}).get('improved_this_iteration', False)}")

        # Log cycle summary
        log_file = ROOT / "logs" / "trading-floor-v9.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now(timezone.utc).isoformat()}] cycle={iteration_count} "
                    f"iter={karpathy_result.get('iteration')} "
                    f"best=${karpathy_result.get('optimization', {}).get('current_best', 0):,.0f} "
                    f"elapsed={cycle_elapsed:.1f}s\n")

        if _STOP_FLAG:
            break

        if max_iterations == 0 or iteration_count < max_iterations:
            print(f"\n[v9] Waiting {delay_seconds}s before next iteration...")
            for _ in range(delay_seconds):
                if _STOP_FLAG:
                    break
                time.sleep(1)

    print(f"\n[v9] Stopped after {iteration_count} iterations.")
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
        # v9 continuous iteration: sync → karpathy → cross-pollinate → push → repeat
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
                      f"POL ${s.get('political_bankroll', 100000):,.2f} "
                      f"({s.get('political_roi_pct', 0):+.4f}% "
                      f"Sharpe {s.get('political_sharpe', 0):.3f} "
                      f"{s.get('political_wins', 0)}W-{s.get('political_losses', 0)}L)"
                      f"  [{s.get('personality', '?')}]")
            else:
                print(f"{tid:12s}: no state yet")

    else:
        print(f"Usage: {sys.argv[0]} [run|karpathy|iterate [max_iter] [delay]|leaderboard|status]")
        sys.exit(1)
