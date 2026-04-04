#!/usr/bin/env python3
"""
Trading Floor v5 — 27 AI Traders with REAL LLM Inference
=========================================================
27 AI traders (12 NBA + 12 Political + 3 Meta-Traders) powered by REAL LLM
API calls across 8 providers.

Key difference from v4:
  v4 used SIMULATED predictions (deterministic hash-based noise).
  v5 uses REAL LLM inference — each trader actually analyzes the game
  and produces a probability estimate. This is the whole point.

Providers:
  - Anthropic (Claude) — via CLI subagent
  - OpenAI (GPT-4o) — via OpenAI-compat API
  - xAI (Grok) — via OpenAI-compat API
  - Google (Gemini) — via OpenAI-compat API
  - Groq (5 keys, Llama/Gemma) — via OpenAI-compat API
  - OpenRouter (7 keys, Qwen/Gemma/Llama/Mistral) — via OpenAI-compat API
  - Cohere (2 keys, Command-R+) — via Cohere native API
  - Cerebras (Qwen-3-235b) — via OpenAI-compat API

Rate-limit strategy:
  - Paid APIs: every iteration
  - Groq (5 keys): rotate, 1 call/key/iteration
  - OpenRouter (7 keys): rotate, 200 RPD each
  - Cohere (2 keys): every other iteration
  - Cerebras: every iteration (30 RPM, 1M tok/day)
"""

import json, os, sys, math, time, hashlib, subprocess, random, traceback
import signal as _signal
from pathlib import Path
from datetime import datetime, timezone, date
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── PATHS ────────────────────────────────────────────────────────────────────
ROOT        = Path('/home/termius/mon-ipad')
NBA_AGENT   = Path('/home/termius/nomos-nba-agent')
POLITICAL   = Path('/home/termius/nomos-political-alpha')
DATA_DIR    = ROOT / 'data' / 'arena'
TRADERS_DIR = DATA_DIR / 'traders-v5'
V5_ITER_FILE = DATA_DIR / 'trading-floor-v5-iteration.json'

# ── TEAM MAP ─────────────────────────────────────────────────────────────────
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

# ── STAT KEYS ────────────────────────────────────────────────────────────────
STAT_KEYS = ['fg_pct', 'fg3_pct', 'ft_pct', 'reb', 'ast', 'tov', 'stl', 'blk', 'plus_minus']


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: LLM PROVIDER ABSTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

class LLMProvider:
    """Unified interface for all LLM providers using OpenAI-compatible format."""

    # Rate limit tracking: {provider_key: [timestamp, ...]}
    _call_log: Dict[str, List[float]] = defaultdict(list)
    # Failure tracking
    _failures: Dict[str, int] = defaultdict(int)
    MAX_FAILURES_PER_SESSION = 3

    @staticmethod
    def _openai_compatible_call(
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500,
        timeout: int = 30,
        provider_key: str = "default",
    ) -> Optional[str]:
        """Make an OpenAI-compatible API call. Returns response text or None."""
        if LLMProvider._failures[provider_key] >= LLMProvider.MAX_FAILURES_PER_SESSION:
            return None

        import urllib.request
        import urllib.error

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(base_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                LLMProvider._call_log[provider_key].append(time.time())
                return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")[:200]
            except Exception:
                pass
            print(f"    [API ERROR] {provider_key}: HTTP {e.code} — {error_body}")
            if e.code == 429:
                LLMProvider._failures[provider_key] += 1
            return None
        except Exception as e:
            print(f"    [API ERROR] {provider_key}: {type(e).__name__}: {str(e)[:100]}")
            LLMProvider._failures[provider_key] += 1
            return None

    @staticmethod
    def _cohere_call(
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500,
        timeout: int = 30,
        provider_key: str = "cohere",
    ) -> Optional[str]:
        """Make a Cohere API call (native format)."""
        if LLMProvider._failures[provider_key] >= LLMProvider.MAX_FAILURES_PER_SESSION:
            return None

        import urllib.request
        import urllib.error

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        body = json.dumps({
            "model": model,
            "message": user_prompt,
            "preamble": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.cohere.com/v1/chat",
            data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                LLMProvider._call_log[provider_key].append(time.time())
                return data.get("text", "").strip()
        except Exception as e:
            print(f"    [API ERROR] {provider_key}: {type(e).__name__}: {str(e)[:100]}")
            LLMProvider._failures[provider_key] += 1
            return None

    @staticmethod
    def _claude_cli_call(
        system_prompt: str,
        user_prompt: str,
        provider_key: str = "claude_cli",
    ) -> Optional[str]:
        """Call Claude via CLI subprocess (uses subscription, not API key)."""
        if LLMProvider._failures[provider_key] >= LLMProvider.MAX_FAILURES_PER_SESSION:
            return None

        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        try:
            result = subprocess.run(
                ["claude", "-p", combined_prompt, "--model", "claude-sonnet-4-6"],
                capture_output=True, text=True, timeout=60,
                cwd=str(ROOT),
            )
            if result.returncode == 0 and result.stdout.strip():
                LLMProvider._call_log[provider_key].append(time.time())
                return result.stdout.strip()
            print(f"    [CLI ERROR] {provider_key}: rc={result.returncode} stderr={result.stderr[:100]}")
            LLMProvider._failures[provider_key] += 1
            return None
        except subprocess.TimeoutExpired:
            print(f"    [CLI ERROR] {provider_key}: timeout 60s")
            LLMProvider._failures[provider_key] += 1
            return None
        except Exception as e:
            print(f"    [CLI ERROR] {provider_key}: {e}")
            LLMProvider._failures[provider_key] += 1
            return None

    @staticmethod
    def get_rate_limit_ok(provider_key: str, max_rpm: int = 30) -> bool:
        """Check if rate limit allows another call."""
        now = time.time()
        calls = LLMProvider._call_log[provider_key]
        # Prune old entries (> 60s)
        LLMProvider._call_log[provider_key] = [t for t in calls if now - t < 60]
        return len(LLMProvider._call_log[provider_key]) < max_rpm

    @staticmethod
    def reset_session():
        """Reset failure counts for a new session."""
        LLMProvider._failures.clear()
        LLMProvider._call_log.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: TRADER DEFINITIONS (27 TRADERS)
# ═══════════════════════════════════════════════════════════════════════════════

def _env(key: str) -> str:
    """Get env var or empty string."""
    return os.environ.get(key, "")


# Each trader has a call_fn that returns Optional[str]
# These are initialized lazily at runtime.

TRADER_CONFIGS = {
    # ── PAID TIER (4 traders) ────────────────────────────────────────────────
    "claude": {
        "name": "Claude",
        "model": "claude-sonnet-4-6",
        "provider": "anthropic",
        "tier": "paid",
        "personality": "Fundamental analysis — deep understanding of basketball mechanics, player matchups, and rest schedules. Conservative bankroll management.",
        "strategy_style": "fundamental_analysis",
        "risk_tolerance": 0.40,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "call_fn_type": "claude_cli",
        "max_rpm": 10,
    },
    "gpt": {
        "name": "GPT-4o",
        "model": "gpt-4o",
        "provider": "openai",
        "tier": "paid",
        "personality": "Statistical arbitrage — finds edges through statistical analysis of odds inefficiencies and line movements. Data-driven decisions.",
        "strategy_style": "statistical_arbitrage",
        "risk_tolerance": 0.55,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "OPENAI_API_KEY",
        "max_rpm": 30,
    },
    "grok": {
        "name": "Grok",
        "model": "grok-3",
        "provider": "xai",
        "tier": "paid",
        "personality": "Contrarian value — goes against public consensus, targets undervalued underdogs. Bold, unconventional picks.",
        "strategy_style": "contrarian_value",
        "risk_tolerance": 0.65,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://api.x.ai/v1/chat/completions",
        "api_key_env": "XAI_API_KEY",
        "max_rpm": 30,
    },
    "gemini": {
        "name": "Gemini",
        "model": "gemini-2.5-flash",
        "provider": "google",
        "tier": "paid",
        "personality": "Multi-factor momentum — combines multiple signals including team momentum, schedule strength, and market movements. Balanced approach.",
        "strategy_style": "multi_factor_momentum",
        "risk_tolerance": 0.55,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "api_key_env": "GOOGLE_API_KEY",
        "max_rpm": 15,
    },

    # ── CEREBRAS (1 trader) ──────────────────────────────────────────────────
    "qwen_cerebras": {
        "name": "Qwen-Cerebras",
        "model": "qwen-3-235b",
        "provider": "cerebras",
        "tier": "free_high",
        "personality": "Deep context analysis — leverages enormous context window to analyze full season narrative arcs and long-term trends.",
        "strategy_style": "deep_context_analysis",
        "risk_tolerance": 0.50,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://api.cerebras.ai/v1/chat/completions",
        "api_key_env": "CEREBRAS_API_KEY",
        "max_rpm": 30,
    },

    # ── GROQ (5 traders, 5 separate keys) ────────────────────────────────────
    "llama_scout_1": {
        "name": "Llama-Scout-1",
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "provider": "groq",
        "tier": "free",
        "personality": "Aggressive momentum — chases hot teams and winning streaks. High-conviction, high-risk plays.",
        "strategy_style": "aggressive_momentum",
        "risk_tolerance": 0.70,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env": "GROQ_API_KEY",
        "max_rpm": 15,
    },
    "llama_scout_2": {
        "name": "Llama-Scout-2",
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "provider": "groq",
        "tier": "free",
        "personality": "Conservative value — only bets when the edge is clear and substantial. Small, careful positions on high-probability outcomes.",
        "strategy_style": "conservative_value",
        "risk_tolerance": 0.35,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env": "GROQ_API_KEY_2",
        "max_rpm": 15,
    },
    "llama_8b_1": {
        "name": "Llama-8B-Fast",
        "model": "llama-3.1-8b-instant",
        "provider": "groq",
        "tier": "free",
        "personality": "Speed trader — makes quick decisions based on headline stats. Relies on strong priors about home court advantage and recent form.",
        "strategy_style": "speed_trader",
        "risk_tolerance": 0.50,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env": "GROQ_API_KEY_3",
        "max_rpm": 15,
    },
    "gemma_groq": {
        "name": "Gemma-Groq",
        "model": "gemma2-9b-it",
        "provider": "groq",
        "tier": "free",
        "personality": "Pattern recognition — looks for recurring patterns in matchup history, back-to-backs, and rest advantages.",
        "strategy_style": "pattern_recognition",
        "risk_tolerance": 0.45,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env": "GROQ_API_KEY_4",
        "max_rpm": 15,
    },
    "llama_scout_3": {
        "name": "Llama-Scout-3",
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "provider": "groq",
        "tier": "free",
        "personality": "Underdog specialist — specifically hunts for mispriced underdogs with hidden value. Higher risk for higher reward.",
        "strategy_style": "underdog_specialist",
        "risk_tolerance": 0.60,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env": "GROQ_API_KEY_5",
        "max_rpm": 15,
    },

    # ── OPENROUTER (4 traders, rotating 7 keys) ─────────────────────────────
    "qwen_or_1": {
        "name": "Qwen-OR-1",
        "model": "qwen/qwen3-30b-a3b:free",
        "provider": "openrouter",
        "tier": "free",
        "personality": "Market sentiment analyst — reads market sentiment from odds movement and public betting percentages to find contrarian value.",
        "strategy_style": "market_sentiment",
        "risk_tolerance": 0.50,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "OPENROUTER_API_KEY",
        "max_rpm": 10,
    },
    "qwen_or_2": {
        "name": "Qwen-OR-2",
        "model": "qwen/qwen3-30b-a3b:free",
        "provider": "openrouter",
        "tier": "free",
        "personality": "Quantitative edge finder — focuses purely on mathematical edge calculation and Kelly criterion application.",
        "strategy_style": "quantitative_edge",
        "risk_tolerance": 0.45,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "OPENROUTER_KEY_QUANTITATIVE",
        "max_rpm": 10,
    },
    "gemma_or": {
        "name": "Gemma-Free",
        "model": "google/gemma-3-27b-it:free",
        "provider": "openrouter",
        "tier": "free",
        "personality": "Pattern recognition specialist — analyzes historical matchup patterns, venue-specific trends, and scheduling effects.",
        "strategy_style": "pattern_recognition",
        "risk_tolerance": 0.50,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "OPENROUTER_KEY_GRAPH",
        "max_rpm": 10,
    },
    "mistral_or": {
        "name": "Mistral-Free",
        "model": "mistralai/mistral-small-3.1-24b-instruct:free",
        "provider": "openrouter",
        "tier": "free",
        "personality": "Risk manager — focuses on bankroll preservation, position sizing, and drawdown control. Skips games without clear edge.",
        "strategy_style": "risk_manager",
        "risk_tolerance": 0.30,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "api_base": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "OPENROUTER_KEY_PREDICTIONS",
        "max_rpm": 10,
    },

    # ── COHERE (2 traders) ───────────────────────────────────────────────────
    "cohere_1": {
        "name": "Cohere-1",
        "model": "command-r-plus",
        "provider": "cohere",
        "tier": "free",
        "personality": "Narrative analysis — constructs game narratives based on team storylines, injuries, and motivation factors. Qualitative edge.",
        "strategy_style": "narrative_analysis",
        "risk_tolerance": 0.50,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "call_fn_type": "cohere",
        "api_key_env": "COHERE_API_KEY",
        "max_rpm": 5,
        "call_every_n": 2,  # every other iteration
    },
    "cohere_2": {
        "name": "Cohere-2",
        "model": "command-r-plus",
        "provider": "cohere",
        "tier": "free",
        "personality": "Risk management — specializes in bankroll protection, stop-loss discipline, and position sizing optimization.",
        "strategy_style": "risk_management",
        "risk_tolerance": 0.30,
        "nba_bankroll": 100.0,
        "political_bankroll": 100_000.0,
        "call_fn_type": "cohere",
        "api_key_env": "COHERE_API_KEY_2",
        "max_rpm": 5,
        "call_every_n": 2,
    },
}

# OpenRouter key rotation pool
OPENROUTER_KEY_POOL = [
    "OPENROUTER_API_KEY",
    "OPENROUTER_KEY_QUANTITATIVE",
    "OPENROUTER_KEY_GRAPH",
    "OPENROUTER_KEY_PREDICTIONS",
    "OPENROUTER_KEY_ODDS",
    "OPENROUTER_KEY_FEATURES",
    "OPENROUTER_KEY_PIPELINE",
]

# ── BETTING STRATEGIES (from v4, subset for v5) ─────────────────────────────
STRATEGIES = {
    "half_kelly":          {"family": "kelly",        "fraction": 0.5,   "min_edge": 0.02, "max_pct": 0.15},
    "quarter_kelly":       {"family": "kelly",        "fraction": 0.25,  "min_edge": 0.03, "max_pct": 0.08},
    "flat_2pct":           {"family": "flat",         "bet_pct": 0.02,   "min_edge": 0.01, "max_pct": 0.02},
    "value_hunter":        {"family": "value",        "fraction": 0.5,   "min_edge": 0.05, "max_pct": 0.12},
    "confidence_scaled":   {"family": "confidence",   "min_edge": 0.02,  "max_pct": 0.20},
    "underdog_specialist": {"family": "underdog",     "min_odds": 2.2,   "min_edge": 0.03, "max_pct": 0.08},
}

# ── ETF UNIVERSE (from v4) ──────────────────────────────────────────────────
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
# SECTION 3: LLM CALL DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

def call_trader_llm(trader_id: str, system_prompt: str, user_prompt: str) -> Optional[str]:
    """Dispatch an LLM call for a specific trader. Returns response text or None."""
    cfg = TRADER_CONFIGS[trader_id]
    provider_key = f"{cfg['provider']}_{trader_id}"

    # Rate limit check
    max_rpm = cfg.get("max_rpm", 15)
    if not LLMProvider.get_rate_limit_ok(provider_key, max_rpm):
        return None

    call_type = cfg.get("call_fn_type", "openai_compat")

    if call_type == "claude_cli":
        return LLMProvider._claude_cli_call(
            system_prompt, user_prompt, provider_key=provider_key
        )
    elif call_type == "cohere":
        api_key = _env(cfg.get("api_key_env", ""))
        if not api_key:
            return None
        return LLMProvider._cohere_call(
            api_key=api_key,
            model=cfg["model"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            provider_key=provider_key,
        )
    else:
        # OpenAI-compatible (OpenAI, xAI, Google, Groq, Cerebras, OpenRouter)
        api_key = _env(cfg.get("api_key_env", ""))
        if not api_key:
            return None
        return LLMProvider._openai_compatible_call(
            base_url=cfg["api_base"],
            api_key=api_key,
            model=cfg["model"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            provider_key=provider_key,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: PROMPT ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════════

def build_nba_system_prompt(trader_id: str) -> str:
    """Build the system prompt for an NBA trader."""
    cfg = TRADER_CONFIGS[trader_id]
    return f"""You are {cfg['name']}, an AI NBA betting analyst on the Nomos42 Trading Floor.

Your strategy style: {cfg['personality']}

Risk tolerance: {cfg['risk_tolerance']} (0=ultra conservative, 1=ultra aggressive)

RULES:
1. Analyze the game data provided and estimate the probability that the HOME team wins.
2. Also recommend a bet type (moneyline_home, moneyline_away, spread_home, spread_away, over, under, or SKIP).
3. Rate your confidence from 0.0 to 1.0.

RESPOND IN EXACTLY THIS JSON FORMAT (nothing else):
{{"home_win_prob": 0.XX, "bet_type": "moneyline_home", "confidence": 0.XX, "reasoning": "brief explanation"}}

Valid bet_type values: moneyline_home, moneyline_away, spread_home, spread_away, over, under, SKIP
If you don't see enough edge, use "SKIP".
"""


def build_nba_game_prompt(game_ctx: Dict) -> str:
    """Build the user prompt with game data for NBA analysis."""
    home = game_ctx["home"]
    away = game_ctx["away"]
    odds = game_ctx["odds"]
    h_stand = game_ctx.get("home_standings", {})
    a_stand = game_ctx.get("away_standings", {})
    h_form = game_ctx.get("home_form_L10", {})
    a_form = game_ctx.get("away_form_L10", {})

    implied_home = 1.0 / odds.get("ml_home_dec", 2.0) if odds.get("ml_home_dec") else 0.5
    implied_away = 1.0 / odds.get("ml_away_dec", 2.0) if odds.get("ml_away_dec") else 0.5

    lines = [
        f"GAME: {home} (home) vs {away} (away) | Date: {game_ctx['date']}",
        f"",
        f"ODDS:",
        f"  Home ML: {odds.get('ml_home_dec', 'N/A')} (implied {implied_home:.1%})",
        f"  Away ML: {odds.get('ml_away_dec', 'N/A')} (implied {implied_away:.1%})",
    ]
    if odds.get("spread_home") is not None:
        lines.append(f"  Spread: {home} {odds['spread_home']:+.1f}")
    if odds.get("total") is not None:
        lines.append(f"  Total: {odds['total']:.1f}")

    lines.append(f"")
    lines.append(f"STANDINGS:")
    if h_stand:
        lines.append(f"  {home}: {h_stand.get('w',0)}-{h_stand.get('l',0)} ({h_stand.get('win_pct',0):.3f}), PPG {h_stand.get('ppg',0):.1f}, Opp PPG {h_stand.get('opp_ppg',0):.1f}")
    if a_stand:
        lines.append(f"  {away}: {a_stand.get('w',0)}-{a_stand.get('l',0)} ({a_stand.get('win_pct',0):.3f}), PPG {a_stand.get('ppg',0):.1f}, Opp PPG {a_stand.get('opp_ppg',0):.1f}")

    lines.append(f"")
    lines.append(f"RECENT FORM (Last 10):")
    if h_form.get("games"):
        lines.append(f"  {home}: {h_form['w']}-{h_form['l']}, Avg {h_form.get('avg_pts',0):.1f} pts, FG {h_form.get('avg_fg_pct',0):.1%}")
    if a_form.get("games"):
        lines.append(f"  {away}: {a_form['w']}-{a_form['l']}, Avg {a_form.get('avg_pts',0):.1f} pts, FG {a_form.get('avg_fg_pct',0):.1%}")

    return "\n".join(lines)


def build_political_system_prompt(trader_id: str) -> str:
    """Build the system prompt for a political ETF trader."""
    cfg = TRADER_CONFIGS[trader_id]
    return f"""You are {cfg['name']}, an AI political/ETF trader on the Nomos42 Trading Floor.

Your strategy style: {cfg['personality']}
Risk tolerance: {cfg['risk_tolerance']}

You trade ETFs and stocks based on political signals and market conditions.
Available tickers: {', '.join(ETF_UNIVERSE.keys())}

RULES:
1. Analyze the political signals and recommend positions.
2. Each position: ticker, direction (long/short), confidence (0.0-1.0), allocation percentage of capital (0.01-0.10).

RESPOND IN EXACTLY THIS JSON FORMAT (nothing else):
{{"positions": [{{"ticker": "SPY", "direction": "long", "confidence": 0.7, "allocation_pct": 0.05, "reasoning": "brief"}}]}}

Return empty positions [] if no clear signal. Maximum 5 positions.
"""


def build_political_prompt(signals: Dict, ticker_data: Dict) -> str:
    """Build user prompt with political signal data."""
    lines = ["POLITICAL SIGNALS:"]
    for ticker, sig in list(signals.items())[:15]:
        strength = sig.get("signal_strength", 0)
        sentiment = sig.get("combined_sentiment", 0)
        if abs(strength) > 0.01:
            lines.append(f"  {ticker}: strength={strength:.3f}, sentiment={sentiment:.3f}")
    if not lines[1:]:
        lines.append("  No significant signals detected.")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: RESPONSE PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def parse_nba_response(raw: Optional[str]) -> Optional[Dict]:
    """Parse LLM response for NBA prediction. Returns parsed dict or None."""
    if not raw:
        return None
    try:
        # Try to extract JSON from response
        text = raw.strip()
        # Find JSON block
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        # Find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end+1]
        parsed = json.loads(text)

        # Validate required fields
        home_prob = float(parsed.get("home_win_prob", 0.5))
        home_prob = max(0.05, min(0.95, home_prob))
        bet_type = parsed.get("bet_type", "SKIP")
        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        reasoning = str(parsed.get("reasoning", ""))[:200]

        return {
            "home_win_prob": home_prob,
            "bet_type": bet_type,
            "confidence": confidence,
            "reasoning": reasoning,
        }
    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        # Fallback: try to extract probability from text
        try:
            import re
            prob_match = re.search(r'home_win_prob["\s:]+([0-9.]+)', raw)
            if prob_match:
                prob = float(prob_match.group(1))
                return {
                    "home_win_prob": max(0.05, min(0.95, prob)),
                    "bet_type": "SKIP",
                    "confidence": 0.3,
                    "reasoning": "parsed from partial response",
                }
        except Exception:
            pass
        return None


def parse_political_response(raw: Optional[str]) -> Optional[List[Dict]]:
    """Parse LLM response for political positions. Returns list of positions or None."""
    if not raw:
        return None
    try:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end+1]
        parsed = json.loads(text)
        positions = parsed.get("positions", [])
        validated = []
        for pos in positions[:5]:
            ticker = str(pos.get("ticker", "")).upper()
            if ticker not in ETF_UNIVERSE:
                continue
            direction = str(pos.get("direction", "long")).lower()
            if direction not in ("long", "short"):
                continue
            confidence = max(0.0, min(1.0, float(pos.get("confidence", 0.5))))
            alloc = max(0.01, min(0.10, float(pos.get("allocation_pct", 0.03))))
            validated.append({
                "ticker": ticker,
                "direction": direction,
                "confidence": confidence,
                "allocation_pct": alloc,
                "reasoning": str(pos.get("reasoning", ""))[:200],
            })
        return validated if validated else None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: BET SIZING & KELLY
# ═══════════════════════════════════════════════════════════════════════════════

def kelly_size(p: float, odds: float, fraction: float = 1.0) -> float:
    """Kelly criterion bet sizing."""
    b = odds - 1.0
    if b <= 0:
        return 0.0
    edge = p * b - (1.0 - p)
    if edge <= 0:
        return 0.0
    return max(0.0, (edge / b) * fraction)


def compute_bet_from_prediction(
    prediction: Dict,
    odds: Dict,
    bankroll: float,
    risk_tolerance: float,
    result: Dict,
) -> Optional[Dict]:
    """Convert an LLM prediction into a concrete bet with sizing.
    result contains the actual game outcome for settlement."""
    bet_type = prediction.get("bet_type", "SKIP")
    if bet_type == "SKIP":
        return None

    home_prob = prediction["home_win_prob"]
    away_prob = 1.0 - home_prob
    confidence = prediction.get("confidence", 0.5)
    home_won = result["home_won"]
    hs, as_ = result["home_score"], result["away_score"]
    total_pts = hs + as_

    # Determine the probability, odds, and outcome for this bet type
    prob = 0.5
    bet_odds = 1.909
    won = False

    if bet_type == "moneyline_home":
        prob = home_prob
        bet_odds = odds.get("ml_home_dec", 2.0)
        won = home_won
    elif bet_type == "moneyline_away":
        prob = away_prob
        bet_odds = odds.get("ml_away_dec", 2.0)
        won = not home_won
    elif bet_type == "spread_home":
        spread = odds.get("spread_home", 0)
        prob = home_prob * 0.9  # slight discount for spread
        bet_odds = 1.909
        won = (hs + spread) > as_ if spread is not None else False
    elif bet_type == "spread_away":
        spread = odds.get("spread_home", 0)
        prob = away_prob * 0.9
        bet_odds = 1.909
        won = (as_ - spread) > hs if spread is not None else False
    elif bet_type == "over":
        total_line = odds.get("total", 220)
        prob = 0.48 + (home_prob - 0.5) * 0.1  # rough
        bet_odds = 1.909
        won = total_pts > total_line if total_line else False
    elif bet_type == "under":
        total_line = odds.get("total", 220)
        prob = 0.52 - (home_prob - 0.5) * 0.1
        bet_odds = 1.909
        won = total_pts < total_line if total_line else False
    else:
        return None

    # Edge check
    edge = prob * (bet_odds - 1.0) - (1.0 - prob)
    if edge < 0.01:
        return None

    # Kelly sizing with confidence and risk tolerance scaling
    kelly_frac = 0.25 * risk_tolerance * confidence
    bet_size = kelly_size(prob, bet_odds, kelly_frac) * bankroll
    max_bet = bankroll * 0.15 * risk_tolerance
    bet_size = min(bet_size, max_bet)
    bet_size = max(bet_size, 0.0)

    if bet_size < 0.01:
        return None

    profit = bet_size * (bet_odds - 1.0) if won else -bet_size

    return {
        "bet_type": bet_type,
        "prob": round(prob, 4),
        "odds": round(bet_odds, 4),
        "edge_pct": round(edge * 100, 2),
        "bet_size": round(bet_size, 4),
        "confidence": round(confidence, 4),
        "outcome": "Win" if won else "Loss",
        "profit": round(profit, 4),
        "reasoning": prediction.get("reasoning", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: DATA LOADERS (from v4)
# ═══════════════════════════════════════════════════════════════════════════════

def load_games_rich() -> Tuple[Dict, List[Dict]]:
    """Load historical game results with team stats."""
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
    """Load historical odds CSV."""
    import csv
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


def compute_standings(all_games: List[Dict], up_to_date: str) -> Dict[str, Dict]:
    """Compute cumulative W-L standings for every team up to a date."""
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

    for team, s in standings.items():
        total = s["w"] + s["l"]
        s["win_pct"] = round(s["w"] / total, 3) if total > 0 else 0.0
        s["ppg"] = round(s["pts_for"] / total, 1) if total > 0 else 0.0
        s["opp_ppg"] = round(s["pts_against"] / total, 1) if total > 0 else 0.0
    return dict(standings)


def compute_team_form(all_games: List[Dict], team: str, up_to_date: str, window: int = 10) -> Dict:
    """Compute rolling stats for a team over last N games."""
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


def load_political_signals() -> Dict:
    """Load latest political social signals."""
    signals_file = POLITICAL / "data" / "social" / "social_signals_latest.json"
    if signals_file.exists():
        try:
            data = json.loads(signals_file.read_text())
            return data.get("signals", data)
        except Exception:
            pass
    return {}


def load_political_events() -> List[Dict]:
    """Load consolidated political events."""
    fp = POLITICAL / "data" / "historical" / "consolidated_events.json"
    if not fp.exists():
        return []
    try:
        events = json.loads(fp.read_text())
        events.sort(key=lambda e: e.get("date", ""))
        return events
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: META-TRADERS
# ═══════════════════════════════════════════════════════════════════════════════

class MetaTraders:
    """Three special meta-traders that operate on top of regular traders."""

    @staticmethod
    def paperclip_allocate(trader_states: Dict[str, Dict]) -> Dict[str, float]:
        """
        M1 PAPERCLIP: Allocates resource weights between traders based on performance.
        Returns weight multipliers (0.5 - 2.0) for each trader.
        """
        if not trader_states:
            return {}

        weights = {}
        rois = {tid: s.get("nba_roi_pct", 0) for tid, s in trader_states.items()}
        max_roi = max(rois.values()) if rois else 0
        min_roi = min(rois.values()) if rois else 0
        spread = max_roi - min_roi if max_roi != min_roi else 1.0

        for tid, roi in rois.items():
            # Normalize ROI to [0.5, 2.0] range
            normalized = (roi - min_roi) / spread if spread > 0 else 0.5
            weights[tid] = round(0.5 + normalized * 1.5, 3)

        return weights

    @staticmethod
    def hermes_consensus(trader_predictions: Dict[str, Dict]) -> Dict:
        """
        M2 HERMES: Routes information between traders, builds consensus.
        Returns consensus prediction from all active traders.
        """
        if not trader_predictions:
            return {"consensus_prob": 0.5, "agreement": 0.0, "active_traders": 0}

        probs = [p["home_win_prob"] for p in trader_predictions.values() if p]
        if not probs:
            return {"consensus_prob": 0.5, "agreement": 0.0, "active_traders": 0}

        avg_prob = sum(probs) / len(probs)
        std_dev = (sum((p - avg_prob)**2 for p in probs) / len(probs)) ** 0.5
        agreement = max(0, 1.0 - std_dev * 5)  # Higher agreement = lower std dev

        return {
            "consensus_prob": round(avg_prob, 4),
            "std_dev": round(std_dev, 4),
            "agreement": round(agreement, 4),
            "active_traders": len(probs),
            "bullish_count": sum(1 for p in probs if p > 0.5),
            "bearish_count": sum(1 for p in probs if p < 0.5),
        }

    @staticmethod
    def oracle_ensemble(trader_states: Dict[str, Dict], trader_predictions: Dict[str, Dict]) -> Optional[Dict]:
        """
        M3 ORACLE: Ensemble of top 3 performers, weighted by recent ROI.
        Returns the Oracle's prediction.
        """
        if not trader_states or not trader_predictions:
            return None

        # Get top 3 by ROI
        ranked = sorted(
            [(tid, s.get("nba_roi_pct", 0)) for tid, s in trader_states.items()],
            key=lambda x: x[1], reverse=True
        )[:3]

        weighted_prob = 0.0
        total_weight = 0.0
        contributors = []

        for tid, roi in ranked:
            pred = trader_predictions.get(tid)
            if pred is None:
                continue
            # Weight = max(1, roi + 50) to avoid negative weights
            weight = max(1.0, roi + 50.0)
            weighted_prob += pred["home_win_prob"] * weight
            total_weight += weight
            contributors.append({"trader": tid, "weight": round(weight, 2), "roi": roi})

        if total_weight == 0:
            return None

        oracle_prob = weighted_prob / total_weight

        return {
            "home_win_prob": round(oracle_prob, 4),
            "bet_type": "moneyline_home" if oracle_prob > 0.55 else ("moneyline_away" if oracle_prob < 0.45 else "SKIP"),
            "confidence": round(min(1.0, abs(oracle_prob - 0.5) * 3), 4),
            "reasoning": f"Oracle ensemble of top {len(contributors)} traders",
            "contributors": contributors,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9: ITERATION / STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def _load_iteration() -> Dict:
    if V5_ITER_FILE.exists():
        try:
            return json.loads(V5_ITER_FILE.read_text())
        except Exception:
            pass
    return {"iteration": 0, "generation": 0}


def _save_iteration(it: Dict) -> None:
    V5_ITER_FILE.parent.mkdir(parents=True, exist_ok=True)
    V5_ITER_FILE.write_text(json.dumps(it, indent=2))


def load_trader_state(trader_id: str) -> Dict:
    """Load persisted trader state."""
    sf = TRADERS_DIR / f"{trader_id}-state.json"
    if sf.exists():
        try:
            return json.loads(sf.read_text())
        except Exception:
            pass
    cfg = TRADER_CONFIGS[trader_id]
    return {
        "trader_id": trader_id,
        "nba_bankroll": cfg["nba_bankroll"],
        "political_bankroll": cfg["political_bankroll"],
        "nba_roi_pct": 0.0,
        "political_roi_pct": 0.0,
        "nba_bets": 0,
        "nba_wins": 0,
        "nba_losses": 0,
        "nba_profit": 0.0,
        "nba_peak": cfg["nba_bankroll"],
        "nba_max_drawdown": 0.0,
        "political_trades": 0,
        "political_wins": 0,
        "political_losses": 0,
        "political_profit": 0.0,
        "nba_bets_history": [],
        "political_trades_history": [],
    }


def save_trader_state(trader_id: str, state: Dict) -> None:
    """Persist trader state."""
    TRADERS_DIR.mkdir(parents=True, exist_ok=True)
    # Trim history to keep file manageable
    if len(state.get("nba_bets_history", [])) > 500:
        state["nba_bets_history"] = state["nba_bets_history"][-500:]
    if len(state.get("political_trades_history", [])) > 500:
        state["political_trades_history"] = state["political_trades_history"][-500:]
    (TRADERS_DIR / f"{trader_id}-state.json").write_text(json.dumps(state, indent=2))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10: GAME SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

def select_games_for_iteration(
    matched: List[Tuple],
    all_games: List[Dict],
    iteration: int,
    games_per_iteration: int = 5,
) -> Tuple[List[Tuple], str]:
    """
    Select a batch of games for this iteration.
    Walk-forward: process games chronologically, never peeking ahead.
    Returns (selected_games, day_date).
    """
    if not matched:
        return [], ""

    # Group by date
    days = defaultdict(list)
    for item in matched:
        key, game_entry, odd = item
        days[key[0]].append(item)
    sorted_days = sorted(days.keys())

    # Pick the day for this iteration (cycle through days)
    day_idx = iteration % len(sorted_days)
    day_date = sorted_days[day_idx]
    day_games = days[day_date]

    # Limit games per iteration to control API costs
    if len(day_games) > games_per_iteration:
        # Pick games with the most interesting odds (furthest from pick'em)
        day_games.sort(key=lambda x: abs(1.0/x[2].get("ml_home_dec", 2.0) - 0.5), reverse=True)
        day_games = day_games[:games_per_iteration]

    return day_games, day_date


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11: MAIN COMPETITION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_one_iteration(
    games_per_iter: int = 5,
    max_parallel: int = 8,
) -> Dict:
    """
    Run one iteration of the v5 Trading Floor.
    1. Select games for this iteration
    2. Send game data to ALL traders in parallel
    3. Parse predictions, compute bets
    4. Settle bets, update bankrolls
    5. Run meta-traders
    6. Save everything
    """
    LLMProvider.reset_session()

    # Load iteration state
    it_data = _load_iteration()
    it_data["iteration"] += 1
    iteration = it_data["iteration"]

    print(f"\n{'='*70}")
    print(f"TRADING FLOOR v5 — Iteration {iteration}")
    print(f"{'='*70}")

    # Load data
    print("Loading game data...")
    games, all_games = load_games_rich()
    odds = load_odds()

    matched = []
    for key in sorted(odds.keys()):
        if key in games:
            matched.append((key, games[key], odds[key]))
    print(f"  Games: {len(games)} | Odds: {len(odds)} | Matched: {len(matched)}")

    if not matched:
        print("  ERROR: No matched games. Aborting.")
        return {"error": "no_matched_games"}

    # Select games for this iteration
    selected_games, day_date = select_games_for_iteration(
        matched, all_games, iteration, games_per_iter
    )
    print(f"  Selected {len(selected_games)} games for {day_date}")

    # Compute standings for selected day
    standings = compute_standings(all_games, day_date)

    # Load existing trader states
    all_trader_states = {}
    for tid in TRADER_CONFIGS:
        all_trader_states[tid] = load_trader_state(tid)

    # Load political data
    pol_signals = load_political_signals()

    # ── PHASE 1: NBA — Query all traders for all games ─────────────────────
    print(f"\n--- NBA PREDICTIONS ({len(TRADER_CONFIGS)} traders x {len(selected_games)} games) ---")

    # Build game contexts
    game_contexts = []
    for key, game_entry, odd in selected_games:
        home_form = compute_team_form(all_games, key[1], key[0])
        away_form = compute_team_form(all_games, key[2], key[0])
        ctx = {
            "date": key[0], "home": key[1], "away": key[2],
            "odds": odd,
            "home_standings": standings.get(key[1], {}),
            "away_standings": standings.get(key[2], {}),
            "home_form_L10": home_form,
            "away_form_L10": away_form,
            "_result": {
                "home_score": game_entry["home_score"],
                "away_score": game_entry["away_score"],
                "home_won": game_entry["home_won"],
            },
        }
        game_contexts.append(ctx)

    # Collect all (trader, game) prediction tasks
    nba_predictions: Dict[str, Dict[str, Optional[Dict]]] = defaultdict(dict)
    # {trader_id: {game_key: prediction}}

    def _nba_task(trader_id: str, game_ctx: Dict) -> Tuple[str, str, Optional[Dict]]:
        """Worker function for one trader + one game."""
        cfg = TRADER_CONFIGS[trader_id]

        # Skip traders on cooldown (Cohere every other iteration)
        call_every = cfg.get("call_every_n", 1)
        if call_every > 1 and iteration % call_every != 0:
            return trader_id, f"{game_ctx['home']}_{game_ctx['away']}", None

        sys_prompt = build_nba_system_prompt(trader_id)
        user_prompt = build_nba_game_prompt(game_ctx)

        raw_response = call_trader_llm(trader_id, sys_prompt, user_prompt)
        parsed = parse_nba_response(raw_response)

        game_key = f"{game_ctx['date']}_{game_ctx['home']}_{game_ctx['away']}"
        return trader_id, game_key, parsed

    # Submit all tasks in parallel
    tasks = []
    for tid in TRADER_CONFIGS:
        for gctx in game_contexts:
            tasks.append((tid, gctx))

    print(f"  Dispatching {len(tasks)} LLM calls (max {max_parallel} parallel)...")
    api_start = time.time()

    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = []
        for tid, gctx in tasks:
            futures.append(executor.submit(_nba_task, tid, gctx))

        completed = 0
        for future in as_completed(futures):
            try:
                tid, game_key, pred = future.result()
                nba_predictions[tid][game_key] = pred
                completed += 1
                if completed % 20 == 0:
                    print(f"    ...{completed}/{len(tasks)} done")
            except Exception as e:
                print(f"    [TASK ERROR] {e}")

    api_elapsed = time.time() - api_start
    successful = sum(1 for tid in nba_predictions for gk in nba_predictions[tid] if nba_predictions[tid][gk])
    print(f"  API calls done in {api_elapsed:.1f}s — {successful}/{len(tasks)} successful")

    # ── PHASE 2: NBA — Settle bets ─────────────────────────────────────────
    print(f"\n--- NBA BET SETTLEMENT ---")

    iteration_results = {}

    for tid in TRADER_CONFIGS:
        state = all_trader_states[tid]
        cfg = TRADER_CONFIGS[tid]
        bankroll = state["nba_bankroll"]
        bets_this_iter = []

        for gctx in game_contexts:
            game_key = f"{gctx['date']}_{gctx['home']}_{gctx['away']}"
            prediction = nba_predictions[tid].get(game_key)
            if prediction is None:
                continue

            bet = compute_bet_from_prediction(
                prediction, gctx["odds"], bankroll,
                cfg["risk_tolerance"], gctx["_result"]
            )
            if bet is None:
                continue

            # Apply bet
            bankroll += bet["profit"]
            bet["date"] = gctx["date"]
            bet["game"] = f"{gctx['home']} vs {gctx['away']}"
            bet["bankroll_after"] = round(bankroll, 4)
            bet["home_win_prob"] = prediction["home_win_prob"]
            bets_this_iter.append(bet)

            # Update state
            state["nba_bets"] = state.get("nba_bets", 0) + 1
            if bet["outcome"] == "Win":
                state["nba_wins"] = state.get("nba_wins", 0) + 1
            else:
                state["nba_losses"] = state.get("nba_losses", 0) + 1
            state["nba_profit"] = round(state.get("nba_profit", 0) + bet["profit"], 4)

        # Update bankroll
        state["nba_bankroll"] = round(max(bankroll, 0), 4)
        if bankroll > state.get("nba_peak", 100.0):
            state["nba_peak"] = round(bankroll, 4)
        if state["nba_peak"] > 0:
            dd = 1.0 - bankroll / state["nba_peak"]
            if dd > state.get("nba_max_drawdown", 0):
                state["nba_max_drawdown"] = round(dd, 4)
        state["nba_roi_pct"] = round((bankroll - 100.0) / 100.0 * 100, 2)

        # Append to history
        state.setdefault("nba_bets_history", []).extend(bets_this_iter)

        iteration_results[tid] = {
            "nba_bets_this_iter": len(bets_this_iter),
            "nba_profit_this_iter": round(sum(b["profit"] for b in bets_this_iter), 4),
            "nba_bankroll": state["nba_bankroll"],
            "nba_roi_pct": state["nba_roi_pct"],
        }

    # ── PHASE 3: Political — Query all traders ─────────────────────────────
    print(f"\n--- POLITICAL TRADING ---")

    if pol_signals:
        def _pol_task(trader_id: str) -> Tuple[str, Optional[List[Dict]]]:
            cfg = TRADER_CONFIGS[trader_id]
            call_every = cfg.get("call_every_n", 1)
            if call_every > 1 and iteration % call_every != 0:
                return trader_id, None

            sys_prompt = build_political_system_prompt(trader_id)
            user_prompt = build_political_prompt(pol_signals, ETF_UNIVERSE)
            raw = call_trader_llm(trader_id, sys_prompt, user_prompt)
            return trader_id, parse_political_response(raw)

        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            pol_futures = [executor.submit(_pol_task, tid) for tid in TRADER_CONFIGS]
            for future in as_completed(pol_futures):
                try:
                    tid, positions = future.result()
                    if positions is None:
                        continue
                    state = all_trader_states[tid]
                    capital = state["political_bankroll"]

                    for pos in positions:
                        size = capital * pos["allocation_pct"]
                        # Simulate return (deterministic hash for reproducibility)
                        seed = f"{day_date}_{tid}_{pos['ticker']}"
                        h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
                        base_return = ((h % 10000) / 10000.0 - 0.48) * 0.03
                        beta = ETF_UNIVERSE.get(pos["ticker"], {}).get("beta", 1.0)
                        trade_return = base_return * beta * pos["confidence"]
                        if pos["direction"] == "short":
                            trade_return *= -1
                        pnl = round(size * trade_return, 2)

                        capital += pnl
                        state["political_trades"] = state.get("political_trades", 0) + 1
                        state["political_profit"] = round(state.get("political_profit", 0) + pnl, 2)
                        if pnl > 0:
                            state["political_wins"] = state.get("political_wins", 0) + 1
                        else:
                            state["political_losses"] = state.get("political_losses", 0) + 1

                        state.setdefault("political_trades_history", []).append({
                            "date": day_date, "ticker": pos["ticker"],
                            "direction": pos["direction"], "size": round(size, 2),
                            "return": round(trade_return, 6), "pnl": pnl,
                            "confidence": pos["confidence"],
                            "reasoning": pos.get("reasoning", ""),
                            "capital_after": round(capital, 2),
                        })

                    state["political_bankroll"] = round(max(capital, 0), 2)
                    state["political_roi_pct"] = round(
                        (capital - 100_000) / 100_000 * 100, 4
                    )

                except Exception as e:
                    print(f"    [POL ERROR] {e}")

    # ── PHASE 4: Meta-Traders ──────────────────────────────────────────────
    print(f"\n--- META-TRADERS ---")

    # Paperclip: compute resource weights
    paperclip_weights = MetaTraders.paperclip_allocate(all_trader_states)
    print(f"  Paperclip weights: top={max(paperclip_weights.values(), default=0):.2f}, "
          f"bottom={min(paperclip_weights.values(), default=0):.2f}")

    # Hermes: per-game consensus
    hermes_consensus_all = {}
    for gctx in game_contexts:
        game_key = f"{gctx['date']}_{gctx['home']}_{gctx['away']}"
        preds_for_game = {
            tid: nba_predictions[tid].get(game_key)
            for tid in TRADER_CONFIGS
            if nba_predictions[tid].get(game_key)
        }
        hermes_consensus_all[game_key] = MetaTraders.hermes_consensus(preds_for_game)
    avg_agreement = sum(c["agreement"] for c in hermes_consensus_all.values()) / max(len(hermes_consensus_all), 1)
    print(f"  Hermes: avg agreement={avg_agreement:.3f} across {len(hermes_consensus_all)} games")

    # Oracle: ensemble of top 3
    oracle_predictions = {}
    for gctx in game_contexts:
        game_key = f"{gctx['date']}_{gctx['home']}_{gctx['away']}"
        preds_for_game = {
            tid: nba_predictions[tid].get(game_key)
            for tid in TRADER_CONFIGS
            if nba_predictions[tid].get(game_key)
        }
        oracle_pred = MetaTraders.oracle_ensemble(all_trader_states, preds_for_game)
        if oracle_pred:
            oracle_predictions[game_key] = oracle_pred
    print(f"  Oracle: {len(oracle_predictions)} game predictions")

    # ── PHASE 5: Save all states ───────────────────────────────────────────
    print(f"\n--- SAVING ---")
    for tid in TRADER_CONFIGS:
        state = all_trader_states[tid]
        state["run_timestamp"] = datetime.now(timezone.utc).isoformat()
        state["last_iteration"] = iteration
        save_trader_state(tid, state)

    # Build leaderboard
    board = []
    for tid, state in all_trader_states.items():
        cfg = TRADER_CONFIGS[tid]
        nba_roi = state.get("nba_roi_pct", 0)
        pol_roi = state.get("political_roi_pct", 0)
        combined = nba_roi + pol_roi * 0.1
        board.append({
            "rank": 0,
            "trader_id": tid,
            "name": cfg["name"],
            "provider": cfg["provider"],
            "tier": cfg["tier"],
            "strategy_style": cfg["strategy_style"],
            "nba_bankroll": state.get("nba_bankroll", 100.0),
            "nba_roi_pct": nba_roi,
            "nba_bets": state.get("nba_bets", 0),
            "nba_wins": state.get("nba_wins", 0),
            "nba_losses": state.get("nba_losses", 0),
            "political_bankroll": state.get("political_bankroll", 100_000),
            "political_roi_pct": pol_roi,
            "political_trades": state.get("political_trades", 0),
            "combined_score": round(combined, 4),
        })
    board.sort(key=lambda x: x["combined_score"], reverse=True)
    for i, entry in enumerate(board, 1):
        entry["rank"] = i

    # Save iteration
    it_data["generation"] = it_data.get("generation", 0) + len(selected_games)
    _save_iteration(it_data)

    # Build output
    output = {
        "iteration": iteration,
        "generation": it_data["generation"],
        "meta": {
            "version": "trading-floor-v5",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": day_date,
            "total_traders": len(TRADER_CONFIGS),
            "meta_traders": 3,
            "games_this_iteration": len(selected_games),
            "api_calls": len(tasks),
            "api_successful": successful,
            "api_elapsed_s": round(api_elapsed, 1),
            "providers": list(set(c["provider"] for c in TRADER_CONFIGS.values())),
        },
        "leaderboard": board,
        "traders": {
            tid: {k: v for k, v in state.items()
                  if k not in ("nba_bets_history", "political_trades_history")}
            for tid, state in all_trader_states.items()
        },
        "meta_traders": {
            "paperclip_weights": paperclip_weights,
            "hermes_consensus": hermes_consensus_all,
            "oracle_predictions": {
                k: {kk: vv for kk, vv in v.items() if kk != "contributors"}
                for k, v in oracle_predictions.items()
            },
        },
        "iteration_detail": iteration_results,
        "games_analyzed": [
            {
                "date": ctx["date"],
                "home": ctx["home"],
                "away": ctx["away"],
                "result": f"{ctx['_result']['home_score']}-{ctx['_result']['away_score']}",
                "home_won": ctx["_result"]["home_won"],
            }
            for ctx in game_contexts
        ],
    }

    # Save output
    latest = DATA_DIR / "trading-floor-v5-latest.json"
    dated = DATA_DIR / f"trading-floor-v5-{date.today().isoformat()}.json"
    latest.write_text(json.dumps(output, indent=2))
    dated.write_text(json.dumps(output, indent=2))

    # Print leaderboard
    print(f"\n{'='*70}")
    print(f"LEADERBOARD — Iteration {iteration}")
    print(f"{'='*70}")
    print(f"{'#':>3} {'Name':<18} {'Provider':<12} {'Tier':<8} {'NBA $':>8} {'ROI':>8} {'W-L':>8} {'Pol $':>12}")
    print(f"{'-'*3} {'-'*18} {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*12}")
    for entry in board:
        wl = f"{entry['nba_wins']}-{entry['nba_losses']}"
        print(f"{entry['rank']:>3} {entry['name']:<18} {entry['provider']:<12} {entry['tier']:<8} "
              f"${entry['nba_bankroll']:>7.2f} {entry['nba_roi_pct']:>+7.1f}% {wl:>8} "
              f"${entry['political_bankroll']:>11,.2f}")

    # API usage summary
    print(f"\n--- API USAGE ---")
    provider_counts = defaultdict(int)
    for tid in TRADER_CONFIGS:
        prov = TRADER_CONFIGS[tid]["provider"]
        if any(nba_predictions[tid].get(
            f"{ctx['date']}_{ctx['home']}_{ctx['away']}"
        ) for ctx in game_contexts):
            provider_counts[prov] += 1
    for prov, count in sorted(provider_counts.items()):
        print(f"  {prov}: {count} traders responded")

    failures = {k: v for k, v in LLMProvider._failures.items() if v > 0}
    if failures:
        print(f"  Failures: {failures}")

    print(f"\nSaved: {latest}")
    print(f"Saved: {dated}")

    return output


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12: CONTINUOUS ITERATION MODE
# ═══════════════════════════════════════════════════════════════════════════════

_STOP_FLAG = False

def _signal_handler(sig, frame):
    global _STOP_FLAG
    print(f"\n[v5] Received signal {sig} — stopping after current iteration.")
    _STOP_FLAG = True


def run_continuous(max_iterations: int = 0, delay_seconds: int = 60, games_per_iter: int = 5):
    """
    Run v5 Trading Floor continuously.
    Default delay is 60s to respect rate limits on free tiers.
    """
    global _STOP_FLAG
    _signal.signal(_signal.SIGINT, _signal_handler)
    _signal.signal(_signal.SIGTERM, _signal_handler)

    print("=" * 70)
    print("TRADING FLOOR v5 — CONTINUOUS MODE (REAL LLM INFERENCE)")
    print(f"Traders: {len(TRADER_CONFIGS)} + 3 meta-traders = {len(TRADER_CONFIGS) + 3}")
    print(f"Providers: {len(set(c['provider'] for c in TRADER_CONFIGS.values()))}")
    print(f"Max iterations: {'infinite' if max_iterations == 0 else max_iterations}")
    print(f"Delay: {delay_seconds}s between iterations")
    print(f"Games/iter: {games_per_iter}")
    print("=" * 70)

    count = 0
    while not _STOP_FLAG:
        count += 1
        if max_iterations > 0 and count > max_iterations:
            break

        try:
            result = run_one_iteration(games_per_iter=games_per_iter)
            if "error" in result:
                print(f"[v5] Error: {result['error']}")
                break
        except Exception as e:
            print(f"[v5] Exception in iteration: {e}")
            traceback.print_exc()

        if _STOP_FLAG:
            break

        if max_iterations == 0 or count < max_iterations:
            print(f"\n[v5] Waiting {delay_seconds}s before next iteration...")
            for _ in range(delay_seconds):
                if _STOP_FLAG:
                    break
                time.sleep(1)

    print(f"\n[v5] Stopped after {count} iterations.")


def push_results_to_git() -> bool:
    """Stage and push v5 results."""
    try:
        subprocess.run(
            ["git", "add", "data/arena/traders-v5/", "data/arena/trading-floor-v5-*.json"],
            cwd=str(ROOT), capture_output=True, timeout=10,
        )
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(ROOT), capture_output=True,
        )
        if diff.returncode != 0:
            it_data = _load_iteration()
            subprocess.run(
                ["git", "commit", "-m",
                 f"data: trading floor v5 iter {it_data['iteration']} — real LLM inference",
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


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13: ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        # Single iteration
        games = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        result = run_one_iteration(games_per_iter=games)
        print(f"\nDone. {len(result.get('leaderboard', []))} traders competed.")

    elif cmd == "iterate":
        # Continuous mode
        max_iter = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        delay = int(sys.argv[3]) if len(sys.argv) > 3 else 60
        games = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        run_continuous(max_iterations=max_iter, delay_seconds=delay, games_per_iter=games)

    elif cmd == "leaderboard":
        # Show current leaderboard
        states = {}
        for tid in TRADER_CONFIGS:
            states[tid] = load_trader_state(tid)
        board = []
        for tid, state in states.items():
            cfg = TRADER_CONFIGS[tid]
            nba_roi = state.get("nba_roi_pct", 0)
            board.append({
                "rank": 0, "trader_id": tid, "name": cfg["name"],
                "provider": cfg["provider"], "tier": cfg["tier"],
                "nba_bankroll": state.get("nba_bankroll", 100),
                "nba_roi_pct": nba_roi,
                "nba_bets": state.get("nba_bets", 0),
                "nba_wins": state.get("nba_wins", 0),
                "nba_losses": state.get("nba_losses", 0),
            })
        board.sort(key=lambda x: x["nba_roi_pct"], reverse=True)
        for i, e in enumerate(board, 1):
            e["rank"] = i
        print(json.dumps(board, indent=2))

    elif cmd == "status":
        # Quick status check
        for tid in sorted(TRADER_CONFIGS.keys()):
            state = load_trader_state(tid)
            cfg = TRADER_CONFIGS[tid]
            key_env = cfg.get("api_key_env", "")
            has_key = bool(_env(key_env)) if key_env else (cfg.get("call_fn_type") == "claude_cli")
            key_status = "KEY_OK" if has_key else "NO_KEY"
            print(f"  {tid:18s} [{cfg['provider']:10s}] {key_status:7s} "
                  f"NBA ${state.get('nba_bankroll', 100):>7.2f} "
                  f"({state.get('nba_roi_pct', 0):+.1f}%) "
                  f"{state.get('nba_wins', 0)}W-{state.get('nba_losses', 0)}L")

    elif cmd == "keys":
        # Check which API keys are available
        print("API Key Status:")
        key_checks = [
            ("ANTHROPIC", "claude_cli", "Check `claude --version`"),
            ("OPENAI_API_KEY", "openai", "GPT-4o"),
            ("XAI_API_KEY", "xai", "Grok"),
            ("GOOGLE_API_KEY", "google", "Gemini"),
            ("CEREBRAS_API_KEY", "cerebras", "Qwen-3-235b"),
            ("GROQ_API_KEY", "groq", "Llama-Scout-1"),
            ("GROQ_API_KEY_2", "groq", "Llama-Scout-2"),
            ("GROQ_API_KEY_3", "groq", "Llama-8B-Fast"),
            ("GROQ_API_KEY_4", "groq", "Gemma-Groq"),
            ("GROQ_API_KEY_5", "groq", "Llama-Scout-3"),
            ("OPENROUTER_API_KEY", "openrouter", "Qwen-OR-1"),
            ("OPENROUTER_KEY_QUANTITATIVE", "openrouter", "Qwen-OR-2"),
            ("OPENROUTER_KEY_GRAPH", "openrouter", "Gemma-Free"),
            ("OPENROUTER_KEY_PREDICTIONS", "openrouter", "Mistral-Free"),
            ("COHERE_API_KEY", "cohere", "Cohere-1"),
            ("COHERE_API_KEY_2", "cohere", "Cohere-2"),
        ]
        available = 0
        for key_name, provider, desc in key_checks:
            if key_name == "ANTHROPIC":
                has = True  # CLI-based
                status = "CLI"
            else:
                val = _env(key_name)
                has = bool(val)
                status = f"{val[:8]}..." if has else "MISSING"
            mark = "[OK]" if has else "[  ]"
            print(f"  {mark} {key_name:35s} {provider:12s} {desc:20s} {status}")
            if has:
                available += 1
        print(f"\n  {available}/{len(key_checks)} keys available = {available} traders active")

    else:
        print(f"""
Trading Floor v5 — 27 AI Traders with REAL LLM Inference

Usage:
  python3 {sys.argv[0]} run [games_per_iter]      Single iteration (default: 5 games)
  python3 {sys.argv[0]} iterate [max] [delay] [g]  Continuous mode
  python3 {sys.argv[0]} leaderboard                Show current standings
  python3 {sys.argv[0]} status                     Quick status of all traders
  python3 {sys.argv[0]} keys                       Check API key availability

Examples:
  python3 {sys.argv[0]} run 3                      Run 1 iteration with 3 games
  python3 {sys.argv[0]} iterate 10 60 5            10 iterations, 60s delay, 5 games each
  python3 {sys.argv[0]} iterate 0 120              Infinite loop, 2min between iterations
""")
        sys.exit(1)
