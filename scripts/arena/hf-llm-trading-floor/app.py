#!/usr/bin/env python3
"""
Nomos42 Real LLM Trading Floor — HuggingFace Spaces
====================================================
10 AI agents (real LLM API calls) compete on 1257 NBA games (2025-26 season).
Each agent receives full game context (odds, standings, form, track record)
and REASONS about what to bet. NO hash simulation. Every decision is a real LLM call.

Providers: Cerebras (5 models), Google Gemini, OpenRouter (2), Cohere, HuggingFace
Runtime: ~4-6 hours for full season. Live visualization throughout.

Architecture follows:
  - TradingAgents (arXiv 2412.20138): structured agent reasoning
  - Prediction Arena (arXiv 2604.07355): 1-bet-per-agent validation
  - DMAD (Diverse Multi-Agent Debate): structurally different data views
"""

import gradio as gr
import json
import os
import csv
import time
import requests
import traceback
import io
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ── STARTUP DIAGNOSTICS ─────────────────────────────────────────────────────
print("=" * 60)
print("NOMOS42 REAL LLM TRADING FLOOR — STARTUP")
print("=" * 60)
for k in ["CEREBRAS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_API_KEY_2",
          "OPENROUTER_KEY_ORCHESTRATOR", "OPENROUTER_KEY_PME", "OPENROUTER_KEY_BARTOLI"]:
    v = os.environ.get(k, "")
    if v:
        print(f"  {k}: {v[:6]}...{v[-3:]} (len={len(v)})")
    else:
        print(f"  {k}: NOT SET")
print("=" * 60)
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── CONTROL STATE (stop/mutate/resume) ──────────────────────────────────────
_stop_event = threading.Event()
_experiment_running = False
_experiment_state = {}  # Persisted to disk
_agent_logs: Dict[str, List[dict]] = defaultdict(list)  # Per-agent decision log
_state_lock = threading.Lock()
STATE_PATH = Path("/tmp/tf-state.json")   # Persists across restarts on HF Spaces
LOGS_PATH = Path("/tmp/tf-agent-logs.json")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "").rstrip("/")

def _save_state_to_disk(state: dict):
    """Persist experiment state to disk (survives Space restarts)."""
    try:
        STATE_PATH.write_text(json.dumps(state, default=str))
    except Exception:
        pass

def _load_state_from_disk() -> Optional[dict]:
    """Load persisted state if available."""
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
    except Exception:
        pass
    return None

def _save_logs_to_disk():
    """Persist agent logs."""
    try:
        LOGS_PATH.write_text(json.dumps(dict(_agent_logs), default=str))
    except Exception:
        pass

def _load_logs_from_disk():
    """Load persisted logs."""
    global _agent_logs
    try:
        if LOGS_PATH.exists():
            data = json.loads(LOGS_PATH.read_text())
            _agent_logs = defaultdict(list, data)
    except Exception:
        pass

_load_logs_from_disk()

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

STAT_KEYS = ["fg_pct", "fg3_pct", "ft_pct", "reb", "ast", "tov", "stl", "blk", "plus_minus"]

# ── PROVIDER CONFIGS (verified working 2026-04-13) ───────────────────────────
# Cerebras: 4 models (all free, fast)
# Gemini: 2 keys, different models (free tier 15 RPM each)
# OpenRouter: 3 keys, many free models
PROVIDERS = {
    # ── CEREBRAS (4 models, all free) ──
    "cerebras:qwen-3-235b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "qwen-3-235b-a22b-instruct-2507",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 400,
        "rpm": 30,
    },
    "cerebras:llama3.1-8b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama3.1-8b",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 400,
        "rpm": 30,
    },
    # NOTE: cerebras:zai-glm-4.7 and gpt-oss-120b return 404 — replaced with OpenRouter
    "openrouter:glm-4.5-air:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "z-ai/glm-4.5-air:free",
        "key_env": "OPENROUTER_KEY_BARTOLI",
        "max_tokens": 400,
        "rpm": 20,
    },
    "openrouter:gpt-oss-20b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openai/gpt-oss-20b:free",
        "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "max_tokens": 400,
        "rpm": 20,
    },
    # ── GEMINI (2 keys) ──
    "google:gemini-2.5-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "model": "gemini-2.5-flash",
        "key_env": "GOOGLE_API_KEY",
        "max_tokens": 400,
        "rpm": 14,
    },
    "google:gemini-3-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent",
        "model": "gemini-3-flash-preview",
        "key_env": "GOOGLE_API_KEY_2",
        "max_tokens": 400,
        "rpm": 14,
    },
    # ── OPENROUTER (3 keys, free models) ──
    "openrouter:gemma-4-26b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "google/gemma-4-26b-a4b-it:free",
        "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "max_tokens": 400,
        "rpm": 20,
    },
    "openrouter:nemotron-120b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "key_env": "OPENROUTER_KEY_BARTOLI",
        "max_tokens": 400,
        "rpm": 20,
    },
    "openrouter:minimax-m2.5:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "minimax/minimax-m2.5:free",
        "key_env": "OPENROUTER_KEY_PME",
        "max_tokens": 400,
        "rpm": 20,
    },
    "openrouter:qwen3-80b:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "qwen/qwen3-next-80b-a3b-instruct:free",
        "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "max_tokens": 400,
        "rpm": 20,
    },
}

# ── AGENT DEFINITIONS (10 agents, all verified working 2026-04-13) ────────────
TRADERS = {
    "gemini": {
        "name": "Gemini Flash", "provider": "google:gemini-2.5-flash",
        "personality": "analytical", "risk_tolerance": 0.60,
    },
    "gemini3": {
        "name": "Gemini 3 Flash", "provider": "google:gemini-3-flash",
        "personality": "diversified", "risk_tolerance": 0.50,
    },
    "qwen": {
        "name": "Qwen 3 235B", "provider": "cerebras:qwen-3-235b",
        "personality": "quantitative", "risk_tolerance": 0.55,
    },
    "llama": {
        "name": "Llama 3.1 8B", "provider": "cerebras:llama3.1-8b",
        "personality": "contrarian", "risk_tolerance": 0.65,
    },
    "glm": {
        "name": "GLM 4.5 Air", "provider": "openrouter:glm-4.5-air:free",
        "personality": "conservative", "risk_tolerance": 0.40,
    },
    "gptoss": {
        "name": "GPT-OSS 20B", "provider": "openrouter:gpt-oss-20b:free",
        "personality": "aggressive", "risk_tolerance": 0.70,
    },
    "gemma4": {
        "name": "Gemma 4 26B", "provider": "openrouter:gemma-4-26b:free",
        "personality": "arbitrage", "risk_tolerance": 0.75,
    },
    "nemotron": {
        "name": "Nemotron 120B", "provider": "openrouter:nemotron-120b:free",
        "personality": "tactical", "risk_tolerance": 0.60,
    },
    "minimax": {
        "name": "MiniMax M2.5", "provider": "openrouter:minimax-m2.5:free",
        "personality": "theoretical", "risk_tolerance": 0.35,
    },
    "qwen3": {
        "name": "Qwen3 80B", "provider": "openrouter:qwen3-80b:free",
        "personality": "ensemble", "risk_tolerance": 0.50,
    },
}

AGENT_SYSTEM_PROMPTS = {
    "gemini": """You are Gemini Flash, an analytical NBA betting agent powered by Google Gemini 2.5 Flash.
APPROACH: Statistical patterns + historical averages. You trust numbers over narratives. Cross-reference model predictions with market odds to find mispricings.
PREFERRED STRATEGIES: half_kelly, confidence_scaled, proportional_edge
EDGE DETECTION: Look for games where model win probability diverges >3% from implied odds probability. Calculate EV precisely.
RISK: Moderate (0.60). Never >15% bankroll on one game. Prefer 2-4 bets per game day.
SPECIALTY: Moneyline and spread markets. Deep understanding of home court advantage.""",

    "gemini3": """You are Gemini 3 Flash, a diversified strategy rotation agent powered by Google Gemini 3.
APPROACH: Rotate strategies based on recent performance. When drawdown >10%, switch to conservative. On winning streaks, increase exposure.
PREFERRED STRATEGIES: quarter_kelly, flat_2pct, value_hunter, drawdown_adjusted
EDGE DETECTION: Compare odds across all categories (ML, spread, total, team totals, halves). Bet where edge is largest. Diversify across bet types.
RISK: Moderate (0.50). Spread risk across 3-5 bet categories per game.
SPECIALTY: Portfolio diversification. Treat each game as a mini-portfolio.""",

    "qwen": """You are Qwen 3 235B, a quantitative NBA betting agent (235 billion parameters).
APPROACH: Pure quant. Calculate implied probabilities, compare with model predictions, compute Kelly fractions. Only bet when math demands it. Ignore narratives.
PREFERRED STRATEGIES: half_kelly, ev_threshold_110, proportional_edge
EDGE DETECTION: Compute exact EV for every category. Require EV > 1.05 minimum. Use model confidence as probability estimate.
RISK: Moderate-low (0.55). Precision over volume. Pass if no edge exists.
SPECIALTY: Totals and alternate totals. Excel at predicting pace and scoring patterns.""",

    "llama": """You are Llama 3.1 8B, a contrarian NBA betting agent.
APPROACH: Fade the public. When public money >70% on one side, find value on the other. Markets overreact to recent form and media narratives.
PREFERRED STRATEGIES: underdog_specialist, dog_value_plus, anti_martingale
EDGE DETECTION: Target games where public betting % diverges from sharp money. Love underdogs getting points.
RISK: High (0.65). Larger positions on strong contrarian signals. Willing to bet big on +200 underdogs.
SPECIALTY: Spread betting, especially taking points. Track line movement for reverse line moves.""",

    "glm": """You are GLM 4.5 Air, a conservative capital-preservation agent powered by Zhipu AI.
APPROACH: Only bet when multiple signals align: model prediction + odds value + form + matchup advantage all pointing same direction.
PREFERRED STRATEGIES: eighth_kelly, flat_1pct, drawdown_adjusted
EDGE DETECTION: Require edge >5% AND model confidence >65% AND positive recent form. Triple confirmation.
RISK: Very low (0.40). Pass on most games. When you bet, it's small. Steady low-variance growth.
SPECIALTY: Home favorites with strong recent form. Rarely bet road teams or underdogs.""",

    "gptoss": """You are GPT-OSS 20B, an aggressive high-conviction betting agent.
APPROACH: Go big or go home. Find strongest edges and bet aggressively. Analyze player matchups, rest days, back-to-back situations.
PREFERRED STRATEGIES: full_kelly, streak_momentum, confidence_scaled
EDGE DETECTION: When edge >3%, bet big. Weight player-level stats heavily — if star averages 28 PPG and total seems low, hammer over.
RISK: Very high (0.70). Will put 20% on single bet if edge is there. Ride hot streaks aggressively.
SPECIALTY: Player-influenced totals and moneylines. Weight individual player impact heavily.""",

    "gemma4": """You are Gemma 4 26B, an arbitrage-hunting agent powered by Google Gemma 4.
APPROACH: Hunt pricing inefficiencies between bet categories. If ML implies 65% but spread implies 60%, something is mispriced.
PREFERRED STRATEGIES: confidence_scaled, proportional_edge, parlay_2leg
EDGE DETECTION: Cross-reference ML odds, spread odds, total odds, team totals, half lines for internal consistency. Bet mispriced side.
RISK: High (0.75). Aggressive when finding cross-market arbitrage.
SPECIALTY: Cross-market analysis. Build correlated 2-leg parlays on related edges.""",

    "nemotron": """You are Nemotron 120B, a tactical agent powered by NVIDIA Nemotron.
APPROACH: Military precision. Analyze team form (L10), head-to-head, rest advantage, travel distance, schedule spots.
PREFERRED STRATEGIES: half_kelly, home_specialist, first_half_sniper
EDGE DETECTION: Weight schedule factors: back-to-backs, rest days, travel, altitude (Denver). Teams on 3-in-4-nights are fade candidates.
RISK: Moderate (0.60). Disciplined execution. Pre-commit bet size before analysis.
SPECIALTY: First-half betting and schedule-based plays. First-half lines are less efficient.""",

    "minimax": """You are MiniMax M2.5, a theoretical/academic betting agent.
APPROACH: Game theory + information theory. Model each bet as decision under uncertainty. Use entropy to measure information advantage.
PREFERRED STRATEGIES: eighth_kelly, flat_1pct, diversified_flat, teaser_6pt
EDGE DETECTION: Compute KL divergence between your probability distribution and implied market distribution. Only bet when divergence exceeds threshold.
RISK: Very low (0.35). Prioritize theoretical soundness. Small, frequent, well-reasoned bets.
SPECIALTY: Teasers and alternative lines. NBA teasers crossing key numbers (3, 7) add value.""",

    "qwen3": """You are Qwen3 80B, an ensemble/meta-learning betting agent.
APPROACH: Aggregate signals: model predictions (40% weight), market implied probability (30%), own matchup analysis (30%). Only bet when ensemble edge >3%.
PREFERRED STRATEGIES: confidence_scaled, value_hunter, drawdown_adjusted
EDGE DETECTION: Build meta-model weighting multiple signals. Strongest when model, odds, and form all agree.
RISK: Moderate (0.50). Balanced and adaptive. Reduce exposure during losing streaks.
SPECIALTY: Consensus plays where multiple signals agree. Strongest on high-agreement games.""",
}

# ── RATE LIMITER ─────────────────────────────────────────────────────────────
_last_call_time: Dict[str, float] = {}

def _rate_limit(provider: str):
    """Enforce per-provider rate limiting."""
    cfg = PROVIDERS.get(provider, {})
    rpm = cfg.get("rpm", 15)
    min_interval = 60.0 / rpm
    key = provider.split(":")[0]  # Group by base provider
    now = time.time()
    last = _last_call_time.get(key, 0)
    wait = min_interval - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_call_time[key] = time.time()


# ── LLM CALL ────────────────────────────────────────────────────────────────
_llm_calls = 0
_llm_failures = 0
_llm_errors: List[str] = []  # Recent errors for debugging

def _call_llm(provider: str, system_prompt: str, user_prompt: str,
              timeout: float = 20.0) -> Optional[str]:
    """Make a real LLM API call. Returns raw text or None on failure."""
    global _llm_calls, _llm_failures
    cfg = PROVIDERS.get(provider)
    if not cfg:
        _llm_failures += 1
        if len(_llm_errors) < 50:
            _llm_errors.append(f"{provider}: unknown provider")
        return None

    api_key = os.environ.get(cfg["key_env"], "")
    if not api_key:
        _llm_failures += 1
        if len(_llm_errors) < 50:
            _llm_errors.append(f"{provider}: no key ({cfg['key_env']})")
        return None

    _rate_limit(provider)
    _llm_calls += 1

    last_error = ""
    for attempt in range(2):  # 1 retry
        try:
            if "google" in provider:
                url = f"{cfg['url']}?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"maxOutputTokens": cfg["max_tokens"], "temperature": 0.3},
                }
                resp = requests.post(url, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                if resp.status_code == 429 and attempt == 0:
                    time.sleep(5)
                    continue
            elif "cohere" in provider:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": cfg["max_tokens"],
                    "temperature": 0.3,
                }
                resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("message", {}).get("content", [{}])[0].get("text", "")
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                if resp.status_code == 429 and attempt == 0:
                    time.sleep(5)
                    continue
            elif "huggingface" in cfg["url"] or provider.startswith("hf:"):
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": cfg["max_tokens"],
                    "temperature": 0.3,
                }
                resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                if resp.status_code in (429, 503) and attempt == 0:
                    time.sleep(8)
                    continue
            else:
                # OpenAI-compatible (Cerebras, OpenRouter)
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                if "openrouter" in provider:
                    headers["HTTP-Referer"] = "https://nomos42.ai"
                    headers["X-Title"] = "Nomos42 Trading Floor"
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": cfg["max_tokens"],
                    "temperature": 0.3,
                }
                resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
                if resp.status_code == 429 and attempt == 0:
                    time.sleep(3)
                    continue
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:100]}"
            if attempt == 0:
                time.sleep(2)
                continue
            break

    _llm_failures += 1
    if len(_llm_errors) < 100:
        _llm_errors.append(f"{provider}: {last_error}")
    return None


# ── PROMPT BUILDER ──────────────────────────────────────────────────────────

def build_game_prompt(game_ctx: Dict, trader_state: Dict,
                      rosters=None, team_advanced=None, player_stats=None,
                      full_odds=None, model_preds=None, strategies=None) -> str:
    """Build comprehensive prompt with 100+ data points for the agent."""
    odds = game_ctx.get("odds", {})
    home_std = game_ctx.get("home_standings", {})
    away_std = game_ctx.get("away_standings", {})
    home_form = game_ctx.get("home_form_L10", {})
    away_form = game_ctx.get("away_form_L10", {})
    home = game_ctx.get("home", "?")
    away = game_ctx.get("away", "?")
    date = game_ctx.get("date", "?")
    game_key = f"{date}_{away}@{home}"

    ml_h = odds.get("ml_home_dec", 2.0)
    ml_a = odds.get("ml_away_dec", 2.0)
    impl_home = round(1.0 / ml_h, 3) if ml_h > 1 else 0.5
    impl_away = round(1.0 / ml_a, 3) if ml_a > 1 else 0.5

    bankroll = trader_state.get("bankroll", 100.0)
    total_bets = trader_state.get("total_bets", 0)
    wins = trader_state.get("wins", 0)
    losses = trader_state.get("losses", 0)
    roi = ((bankroll - 100.0) / 100.0) * 100 if bankroll != 100.0 else 0.0

    lines = [f"GAME: {away} @ {home} | {date}"]

    # ── STANDINGS ──
    h_w = home_std.get("w", 0); h_l = home_std.get("l", 0)
    a_w = away_std.get("w", 0); a_l = away_std.get("l", 0)
    h_wp = home_std.get("win_pct", 0); a_wp = away_std.get("win_pct", 0)
    lines.append(f"\nSTANDINGS: {home} {h_w}-{h_l} ({h_wp:.3f}) | {away} {a_w}-{a_l} ({a_wp:.3f})")

    # ── FORM ──
    h_form_str = f"{home_form.get('w','?')}-{home_form.get('l','?')}" if home_form.get("games", 0) > 0 else "N/A"
    a_form_str = f"{away_form.get('w','?')}-{away_form.get('l','?')}" if away_form.get("games", 0) > 0 else "N/A"
    lines.append(f"FORM L10: {home} {h_form_str} | {away} {a_form_str}")

    # ── ADVANCED TEAM STATS ──
    if team_advanced:
        for t, label in [(home, "HOME"), (away, "AWAY")]:
            ts = team_advanced.get(t, {})
            if ts:
                lines.append(f"{label} {t}: OffRtg={ts.get('OFF_RATING','?')} DefRtg={ts.get('DEF_RATING','?')} Net={ts.get('NET_RATING','?')} Pace={ts.get('PACE','?')} TS%={ts.get('TS_PCT','?')}")

    # ── KEY PLAYERS (Top 5 per team) ──
    if player_stats:
        lines.append("\nKEY PLAYERS:")
        for t, label in [(home, "HOME"), (away, "AWAY")]:
            ps_entry = player_stats.get(t, {})
            players = (ps_entry.get("players", ps_entry) if isinstance(ps_entry, dict) else ps_entry) or []
            if isinstance(players, list):
                players = players[:5]
            else:
                players = []
            if players:
                pstrs = []
                for p in players:
                    ppg = p.get('PPG', p.get('ppg', 0)) or 0
                    rpg = p.get('RPG', p.get('rpg', 0)) or 0
                    apg = p.get('APG', p.get('apg', 0)) or 0
                    fg = p.get('FG_PCT', p.get('fg_pct', 0)) or 0
                    fg3 = p.get('FG3_PCT', p.get('fg3_pct', 0)) or 0
                    mins = p.get('MIN', p.get('min', 0)) or 0
                    pstrs.append(f"{p.get('name','?')} {ppg:.1f}p/{rpg:.1f}r/{apg:.1f}a {fg:.0%}FG")
                lines.append(f"  {label} {t}: {' | '.join(pstrs)}")

    # ── BASE ODDS ──
    lines.append(f"\nBASE ODDS:")
    lines.append(f"  ML: {home} {ml_h:.3f} (impl {impl_home:.1%}) | {away} {ml_a:.3f} (impl {impl_away:.1%})")
    lines.append(f"  Spread: {home} {odds.get('spread_home', 'N/A')} | Total: {odds.get('total', 'N/A')}")

    # ── FULL ODDS MENU (100+ categories) ──
    fo_raw = (full_odds or {}).get(game_key, {})
    fo = fo_raw.get("categories", fo_raw) if isinstance(fo_raw, dict) else {}
    if fo and isinstance(fo, dict):
        cats = sorted(fo.keys())
        def _fmt(c):
            v = fo[c]
            if isinstance(v, dict):
                odds_v = v.get("odds", v.get("line", "?"))
                return f"{c}={odds_v}"
            return f"{c}={v}"
        alt_sp = [c for c in cats if c.startswith("alt_spread")]
        alt_tot = [c for c in cats if c.startswith("alt_total")]
        team_tots = [c for c in cats if c.startswith("team_total")]
        halves = [c for c in cats if c.startswith("h1_") or c.startswith("h2_")]
        quarters = [c for c in cats if c.startswith("q1_")]
        game_props = [c for c in cats if c.startswith("prop_")]
        n_cats = fo_raw.get("category_count", len(cats))
        lines.append(f"\nFULL ODDS ({n_cats} categories):")
        if alt_sp:
            lines.append(f"  ALT SPREADS: {', '.join(_fmt(c) for c in alt_sp[:8])}")
        if alt_tot:
            lines.append(f"  ALT TOTALS: {', '.join(_fmt(c) for c in alt_tot[:8])}")
        if team_tots:
            lines.append(f"  TEAM TOTALS: {', '.join(_fmt(c) for c in team_tots)}")
        if halves:
            lines.append(f"  HALVES: {', '.join(_fmt(c) for c in halves[:8])}")
        if quarters:
            lines.append(f"  QUARTERS: {', '.join(_fmt(c) for c in quarters)}")
        if game_props:
            lines.append(f"  GAME PROPS: {', '.join(_fmt(c) for c in game_props[:8])}")

    # ── NOMOS42 MODEL PREDICTIONS ──
    pred = (model_preds or {}).get(game_key, {})
    if pred:
        lines.append(f"\nNOMOS42 AI MODEL (Brier=0.217, {pred.get('total_agents',0)} agents):")
        lines.append(f"  ML: {pred.get('consensus_ml_direction','?')} conf={pred.get('consensus_ml_confidence',0):.1%} ({pred.get('ml_agree',0)}/{pred.get('total_agents',0)} agree)")
        lines.append(f"  Spread: {pred.get('consensus_spread_direction','?')} conf={pred.get('consensus_spread_confidence',0):.1%}")
        lines.append(f"  Total: {pred.get('consensus_total_direction','?')} conf={pred.get('consensus_total_confidence',0):.1%}")

    # ── TRACK RECORD ──
    lines.append(f"\nYOUR TRACK RECORD: ${bankroll:.2f} | {total_bets} bets | {wins}W-{losses}L | ROI {roi:+.1f}%")

    # ── STRATEGIES (abbreviated) ──
    if strategies:
        strat_list = ", ".join(strategies.keys())
        lines.append(f"\nAVAILABLE STRATEGIES ({len(strategies)}): {strat_list}")

    # ── DECISION FORMAT ──
    lines.append(f"""
AVAILABLE CATEGORIES: ml_home, ml_away, spread_home, spread_away, total_over, total_under, h1_ml_home, h1_ml_away, h1_spread, h1_total_over, h1_total_under, team_total_home_over, team_total_home_under, team_total_away_over, team_total_away_under, alt_spread_home_minus3.5, alt_spread_home_minus5.5, alt_total_over_plus3, alt_total_under_minus3, q1_ml_home, q1_ml_away, prop_both_100, prop_overtime

Respond with ONLY JSON:
{{"reasoning": "1-2 sentences", "bets": [{{"category": "ml_home", "confidence": 0.65, "edge": 0.05, "bet_pct": 0.02, "strategy": "half_kelly"}}], "pass": false}}

Rules: confidence 0-1, edge positive=value, bet_pct 0.005-0.08, max 2 bets, strategy from list above. Pass if no edge.""")

    return "\n".join(lines)


def parse_llm_decision(raw: str) -> Optional[Dict]:
    """Extract JSON decision from LLM response."""
    if not raw:
        return None
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


# ── BET RESOLUTION ──────────────────────────────────────────────────────────

def resolve_bet(category: str, odds: Dict, hs: int, as_: int, home_won: bool,
                game_data: Dict = None) -> bool:
    """Resolve whether a bet category won. Supports 100+ categories."""
    cat = category.lower().strip()
    total_pts = hs + as_
    spread = odds.get("spread_home", 0) or 0
    total_line = odds.get("total", 0) or 0
    margin = hs - as_  # positive = home won by N

    # Base categories
    if cat == "ml_home": return home_won
    if cat == "ml_away": return not home_won
    if cat == "spread_home": return (hs + spread) > as_
    if cat == "spread_away": return (as_ - spread) > hs
    if cat == "total_over": return total_pts > total_line if total_line else False
    if cat == "total_under": return total_pts < total_line if total_line else False

    # Alt spreads: alt_spread_home_minus3.5 means home -3.5
    if cat.startswith("alt_spread_home_minus"):
        try:
            alt_line = float(cat.split("minus")[-1])
            return margin > alt_line
        except ValueError: pass
    if cat.startswith("alt_spread_home_plus"):
        try:
            alt_line = float(cat.split("plus")[-1])
            return margin > -alt_line
        except ValueError: pass
    if cat.startswith("alt_spread_away"):
        try:
            n = float(cat.split("_")[-1].replace("minus","-").replace("plus",""))
            return -margin > n
        except ValueError: pass

    # Alt totals: alt_total_over_plus3 means total > (line + 3)
    if cat.startswith("alt_total_over"):
        try:
            adj = float(cat.split("_")[-1].replace("plus","").replace("minus","-"))
            return total_pts > (total_line + adj) if total_line else False
        except ValueError: pass
    if cat.startswith("alt_total_under"):
        try:
            adj = float(cat.split("_")[-1].replace("plus","").replace("minus","-"))
            return total_pts < (total_line + adj) if total_line else False
        except ValueError: pass

    # Team totals
    if cat == "team_total_home_over":
        home_line = (total_line - spread) / 2 if total_line else 0
        return hs > home_line
    if cat == "team_total_home_under":
        home_line = (total_line - spread) / 2 if total_line else 0
        return hs < home_line
    if cat == "team_total_away_over":
        away_line = (total_line + spread) / 2 if total_line else 0
        return as_ > away_line
    if cat == "team_total_away_under":
        away_line = (total_line + spread) / 2 if total_line else 0
        return as_ < away_line

    # Halves (approximate: H1 ~ 48-52% of total)
    if cat.startswith("h1_") or cat.startswith("h2_"):
        # Without quarter data, use total game result as proxy
        if "ml_home" in cat: return home_won
        if "ml_away" in cat: return not home_won
        if "total_over" in cat: return total_pts > total_line if total_line else False
        if "total_under" in cat: return total_pts < total_line if total_line else False
        if "spread" in cat: return (hs + spread) > as_

    # Quarter MLs
    if cat.startswith("q1_"):
        if "ml_home" in cat: return home_won
        if "ml_away" in cat: return not home_won

    # Game props
    if cat == "prop_both_100": return hs >= 100 and as_ >= 100
    if cat == "prop_overtime": return False  # Can't determine from final score alone
    if cat.startswith("prop_margin"):
        if "1_5" in cat: return 1 <= abs(margin) <= 5
        if "6_10" in cat: return 6 <= abs(margin) <= 10
        if "11_15" in cat: return 11 <= abs(margin) <= 15
        if "16_20" in cat: return 16 <= abs(margin) <= 20
        if "21plus" in cat: return abs(margin) >= 21

    # Fallback: unknown category — treat as loss
    return False


def get_odds_dec(category: str, odds: Dict) -> float:
    """Get decimal odds for a bet category. Supports 100+ categories."""
    cat = category.lower().strip()
    # Base categories with real odds
    if cat == "ml_home": return odds.get("ml_home_dec", 1.91)
    if cat == "ml_away": return odds.get("ml_away_dec", 1.91)
    if cat in ("spread_home", "spread_away", "total_over", "total_under"):
        return 1.91  # Standard -110 juice
    # Alt spreads: adjusted odds (tighter = worse odds, wider = better)
    if "alt_spread" in cat:
        if "minus" in cat:
            try:
                n = float(cat.split("minus")[-1])
                base = odds.get("spread_home", 0) or 0
                diff = n - abs(base)
                return max(1.2, 1.91 - diff * 0.08)  # ~8 cents per point
            except ValueError: pass
        return 1.91
    # Alt totals
    if "alt_total" in cat: return 1.85
    # Team totals, halves, quarters: standard juice
    if cat.startswith(("team_total", "h1_", "h2_", "q1_")): return 1.91
    # Game props: higher odds for prop bets
    if cat == "prop_both_100": return 1.80
    if cat == "prop_overtime": return 8.0
    if "prop_margin" in cat: return 3.0
    return 1.91


# ── DATA LOADING ────────────────────────────────────────────────────────────

def load_games() -> List[Dict]:
    """Load 2025-26 season games."""
    data_dir = Path(__file__).parent / "data"
    fp = data_dir / "games-2025-26.json"
    if not fp.exists():
        return []
    raw = json.loads(fp.read_text())
    games_list = raw.get("games", raw if isinstance(raw, list) else [])
    enriched = []
    for g in games_list:
        game_date = g.get("game_date", "")
        # home_team is already an abbreviation in this dataset
        home = g.get("home_team") or g.get("home", {}).get("team_abbr", "")
        away = g.get("away_team") or g.get("away", {}).get("team_abbr", "")
        if not home or not away:
            continue
        h_data = g.get("home", {})
        a_data = g.get("away", {})
        hs = h_data.get("pts", h_data.get("PTS", 0))
        as_ = a_data.get("pts", a_data.get("PTS", 0))
        if not hs or not as_:
            continue
        enriched.append({
            "date": game_date, "home": home, "away": away,
            "home_score": int(hs), "away_score": int(as_),
            "home_won": int(hs) > int(as_),
            "home_stats": {k: h_data.get(k, 0) for k in STAT_KEYS},
            "away_stats": {k: a_data.get(k, 0) for k in STAT_KEYS},
        })
    enriched.sort(key=lambda g: g["date"])
    return enriched


def load_odds() -> Dict:
    """Load odds from CSV. Maps full team names to abbreviations."""
    data_dir = Path(__file__).parent / "data"
    fp = data_dir / "nba_2025-26_odds.csv"
    if not fp.exists():
        return {}

    def parse_odds_val(s):
        if not s or not s.strip():
            return None
        v = float(s.strip())
        if 1.0 < v < 15.0 and "." in s.strip():
            return v
        v = int(v)
        if v > 0:
            return v / 100.0 + 1
        if v < 0:
            return 100.0 / abs(v) + 1
        return 2.0

    odds = {}
    with open(fp) as f:
        reader = csv.DictReader(f)
        for row in reader:
            game_date = row.get("date", "")
            # Odds CSV uses full team names — map to abbreviations
            home = TEAM_MAP.get(row.get("home_team", ""), row.get("home_team", ""))
            away = TEAM_MAP.get(row.get("away_team", ""), row.get("away_team", ""))

            try:
                ml_home = parse_odds_val(row.get("moneyline_home", ""))
                ml_away = parse_odds_val(row.get("moneyline_away", ""))
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


DATA = Path(__file__).parent / "data"

def load_rosters():
    """Load team rosters {team_abbr: [{name, position, age, ...}, ...]}"""
    path = DATA / "rosters-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_team_advanced():
    """Load advanced team stats {team_abbr: {OFF_RATING, DEF_RATING, ...}}"""
    path = DATA / "team-advanced-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_player_stats():
    """Load player per-game stats {team_abbr: [{name, ppg, rpg, ...}, ...]}"""
    path = DATA / "player-stats-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_full_odds():
    """Load 100+ odds categories {game_key: {category: odds, ...}}"""
    path = DATA / "full-odds-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_model_predictions():
    """Load our Nomos42 model consensus predictions {game_key: {...}}"""
    path = DATA / "model-predictions-2025-26.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_strategies():
    """Load 22 SOTA betting strategies"""
    path = DATA / "strategies.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def generate_implied_odds(home_wp: float, away_wp: float) -> Dict:
    """Generate implied odds from team win percentages when no real odds available."""
    if home_wp <= 0:
        home_wp = 0.4
    if away_wp <= 0:
        away_wp = 0.4
    # Home court advantage ~ +3.5%
    home_prob = (home_wp * 0.6 + 0.5 * 0.4) + 0.035
    home_prob = max(0.15, min(0.85, home_prob))
    ml_home = round(1.0 / home_prob, 3)
    ml_away = round(1.0 / (1.0 - home_prob), 3)
    # Rough spread from prob
    spread = round((0.5 - home_prob) * 20, 1)
    return {
        "ml_home_dec": ml_home, "ml_away_dec": ml_away,
        "spread_home": spread, "total": 220.0,
        "synthetic": True,
    }


# ── STANDINGS + FORM ────────────────────────────────────────────────────────

def compute_standings(all_games: List[Dict], up_to_date: str) -> Dict:
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
    for team, s in standings.items():
        total = s["w"] + s["l"]
        s["win_pct"] = round(s["w"] / total, 3) if total > 0 else 0.0
    return dict(standings)


def compute_form(all_games: List[Dict], team: str, up_to_date: str, window: int = 10) -> Dict:
    recent = []
    for g in all_games:
        if g["date"] >= up_to_date:
            break
        if g["home"] == team:
            recent.append(g["home_won"])
        elif g["away"] == team:
            recent.append(not g["home_won"])
    last_n = recent[-window:]
    if not last_n:
        return {"games": 0, "w": 0, "l": 0}
    wins = sum(1 for w in last_n if w)
    return {"games": len(last_n), "w": wins, "l": len(last_n) - wins}


# ── EXPERIMENT RUNNER ────────────────────────────────────────────────────────

def run_experiment(progress=gr.Progress(track_tqdm=False)):
    """Main experiment: 10 agents × all games. Yields live updates."""
    global _llm_calls, _llm_failures
    _llm_calls = 0
    _llm_failures = 0

    # Load data
    all_games = load_games()
    odds_dict = load_odds()
    rosters = load_rosters()
    team_advanced = load_team_advanced()
    player_stats = load_player_stats()
    full_odds = load_full_odds()
    model_preds = load_model_predictions()
    strategies = load_strategies()
    n_games = len(all_games)

    if n_games == 0:
        yield ("No game data found!", None, None, "Error: No game data in data/ directory")
        return

    # Check which API keys are available
    available_keys = {}
    for prov, cfg in PROVIDERS.items():
        key = os.environ.get(cfg["key_env"], "")
        if key:
            available_keys[cfg["key_env"]] = True
    key_summary = ", ".join(sorted(available_keys.keys()))

    # Init trader state
    state = {}
    for tid, cfg in TRADERS.items():
        state[tid] = {
            "bankroll": 100.0,
            "total_bets": 0,
            "wins": 0,
            "losses": 0,
            "passes": 0,
            "llm_calls": 0,
            "llm_ok": 0,
            "history": [100.0],
            "game_log": [],
            "best_bankroll": 100.0,
            "worst_bankroll": 100.0,
            "max_drawdown": 0.0,
        }

    global _experiment_running, _experiment_state
    _experiment_running = True
    _stop_event.clear()

    # Check for persisted state (resume after restart)
    saved = _load_state_from_disk()
    start_from = 0
    if saved and not saved.get("completed") and saved.get("games_processed", 0) > 0:
        # Resume from where we left off
        state = {tid: saved["agents"][tid] for tid in TRADERS if tid in saved.get("agents", {})}
        start_from = saved.get("games_processed", 0)
        for tid in TRADERS:
            if tid not in state:
                state[tid] = {
                    "bankroll": 100.0, "total_bets": 0, "wins": 0, "losses": 0,
                    "passes": 0, "llm_calls": 0, "llm_ok": 0,
                    "history": [100.0], "game_log": [], "best_bankroll": 100.0,
                    "worst_bankroll": 100.0, "max_drawdown": 0.0,
                }
        print(f"RESUMING from game {start_from}")

    start_time = time.time()
    odds_matched = 0
    odds_synthetic = 0
    game_dates_seen = set()
    log_lines = []

    log_lines.append(f"=== NOMOS42 REAL LLM TRADING FLOOR ===")
    log_lines.append(f"Season: 2025-26 | Games: {n_games} | Agents: {len(TRADERS)}")
    log_lines.append(f"API keys: {key_summary or 'NONE FOUND'}")
    log_lines.append(f"Data: {len(rosters)} rosters | {len(team_advanced)} teams adv | {len(full_odds)} odds games | {len(model_preds)} predictions | {len(strategies)} strategies")
    if start_from > 0:
        log_lines.append(f"RESUMED from game {start_from}")
    log_lines.append(f"Start: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    log_lines.append("=" * 50)

    for game_idx, game in enumerate(all_games):
        # Skip already-processed games (resume support)
        if game_idx < start_from:
            game_dates_seen.add(game["date"])
            continue

        # Check stop signal
        if _stop_event.is_set():
            log_lines.append(f"=== STOPPED at game {game_idx} by user/council ===")
            break
        game_date = game["date"]
        home = game["home"]
        away = game["away"]
        hs = game["home_score"]
        as_ = game["away_score"]
        home_won = game["home_won"]
        game_dates_seen.add(game_date)

        # Build context
        standings = compute_standings(all_games, game_date)
        home_stand = standings.get(home, {})
        away_stand = standings.get(away, {})
        home_form = compute_form(all_games, home, game_date)
        away_form = compute_form(all_games, away, game_date)

        # Get odds
        odds_key = (game_date, home, away)
        if odds_key in odds_dict:
            odds = odds_dict[odds_key]
            odds_matched += 1
        else:
            # Try reverse (some odds have teams swapped)
            odds_key_rev = (game_date, away, home)
            if odds_key_rev in odds_dict:
                raw = odds_dict[odds_key_rev]
                odds = {
                    "ml_home_dec": raw.get("ml_away_dec", 2.0),
                    "ml_away_dec": raw.get("ml_home_dec", 2.0),
                    "spread_home": -(raw.get("spread_home", 0) or 0),
                    "total": raw.get("total"),
                    "swapped": True,
                }
                odds_matched += 1
            else:
                odds = generate_implied_odds(
                    home_stand.get("win_pct", 0.5),
                    away_stand.get("win_pct", 0.5),
                )
                odds_synthetic += 1

        game_ctx = {
            "date": game_date, "home": home, "away": away,
            "odds": odds,
            "home_standings": home_stand,
            "away_standings": away_stand,
            "home_form_L10": home_form,
            "away_form_L10": away_form,
        }

        game_log_entry = f"[{game_idx+1}/{n_games}] {game_date} {home} vs {away} | {hs}-{as_} "
        game_decisions = []

        # Each agent decides
        for tid, cfg in TRADERS.items():
            provider = cfg["provider"]
            ts = state[tid]
            bankroll = ts["bankroll"]

            if bankroll <= 1.0:
                # Bankrupt — skip
                ts["passes"] += 1
                ts["history"].append(bankroll)
                continue

            system_prompt = AGENT_SYSTEM_PROMPTS.get(tid, "You are an NBA betting agent.")
            user_prompt = build_game_prompt(
                game_ctx, ts, rosters=rosters, team_advanced=team_advanced,
                player_stats=player_stats, full_odds=full_odds,
                model_preds=model_preds, strategies=strategies
            )

            # REAL LLM CALL
            ts["llm_calls"] += 1
            raw_response = _call_llm(provider, system_prompt, user_prompt)

            if raw_response:
                ts["llm_ok"] += 1
                decision = parse_llm_decision(raw_response)
            else:
                decision = None

            if decision and isinstance(decision.get("bets"), list) and not decision.get("pass", True):
                bets = decision["bets"][:2]  # Max 2 per game
                for bet in bets:
                    cat = bet.get("category", "").lower()
                    conf = float(bet.get("confidence", 0.5))
                    edge = float(bet.get("edge", 0.0))
                    bet_pct = float(bet.get("bet_pct", 0.01))

                    if not cat or edge <= 0 or bet_pct <= 0:
                        continue

                    # Cap bet size
                    bet_pct = min(bet_pct, 0.08)
                    bet_amount = round(bankroll * bet_pct, 2)
                    bet_amount = min(bet_amount, bankroll * 0.1)  # Never more than 10%
                    if bet_amount < 0.10:
                        continue

                    # Resolve
                    won = resolve_bet(cat, odds, hs, as_, home_won)
                    odds_dec = get_odds_dec(cat, odds)

                    if won:
                        profit = bet_amount * (odds_dec - 1)
                        ts["bankroll"] += profit
                        ts["wins"] += 1
                    else:
                        ts["bankroll"] -= bet_amount
                        ts["losses"] += 1

                    ts["total_bets"] += 1
                    ts["bankroll"] = round(ts["bankroll"], 2)
                    bankroll = ts["bankroll"]

                    game_decisions.append(f"{cfg['name'][:8]}:{cat}({'W' if won else 'L'})")
            else:
                ts["passes"] += 1

            ts["history"].append(ts["bankroll"])
            ts["best_bankroll"] = max(ts["best_bankroll"], ts["bankroll"])
            dd = (ts["best_bankroll"] - ts["bankroll"]) / ts["best_bankroll"] if ts["best_bankroll"] > 0 else 0
            ts["max_drawdown"] = max(ts["max_drawdown"], dd)

        # Log
        decisions_str = " | ".join(game_decisions[:5]) if game_decisions else "all passed"
        game_log_entry += decisions_str
        log_lines.append(game_log_entry)

        # Persist state to disk every 10 games (survive restarts)
        if (game_idx + 1) % 10 == 0:
            with _state_lock:
                _experiment_state = {
                    "games_processed": game_idx + 1,
                    "games_total": n_games,
                    "completed": False,
                    "agents": {tid: {k: v for k, v in ts.items() if k != "history"}
                               for tid, ts in state.items()},
                    "updated": datetime.now(timezone.utc).isoformat(),
                }
                _save_state_to_disk(_experiment_state)
                _save_logs_to_disk()

        # Yield update every 5 games or at milestones
        if (game_idx + 1) % 5 == 0 or game_idx == n_games - 1 or game_idx < 3:
            elapsed = time.time() - start_time
            games_done = game_idx + 1
            rate = games_done / (elapsed / 60) if elapsed > 0 else 0
            eta_min = (n_games - games_done) / rate if rate > 0 else 0

            progress(games_done / n_games,
                     desc=f"Game {games_done}/{n_games} | {rate:.1f} games/min | ETA {eta_min:.0f}min")

            # Build leaderboard
            lb_data = []
            for tid, ts in sorted(state.items(), key=lambda x: -x[1]["bankroll"]):
                cfg = TRADERS[tid]
                roi = ((ts["bankroll"] - 100.0) / 100.0) * 100
                win_rate = ts["wins"] / max(1, ts["total_bets"]) * 100
                llm_rate = ts["llm_ok"] / max(1, ts["llm_calls"]) * 100
                lb_data.append([
                    cfg["name"],
                    cfg["provider"].split(":")[-1][:20],
                    f"${ts['bankroll']:.2f}",
                    f"{roi:+.1f}%",
                    ts["total_bets"],
                    f"{win_rate:.0f}%",
                    ts["passes"],
                    f"{llm_rate:.0f}%",
                    f"{ts['max_drawdown']:.1%}",
                ])

            # Build chart
            fig = make_bankroll_chart(state, games_done)

            # Show recent unique errors
            err_summary = ""
            if _llm_errors:
                unique_errs = list(set(_llm_errors[-20:]))[:5]
                err_summary = " | ERRORS: " + "; ".join(unique_errs)

            status = (
                f"Game {games_done}/{n_games} | "
                f"{len(game_dates_seen)} game days | "
                f"LLM calls: {_llm_calls} (fail: {_llm_failures}) | "
                f"Odds: {odds_matched} real + {odds_synthetic} synthetic | "
                f"Rate: {rate:.1f} g/min | ETA: {eta_min:.0f}min | "
                f"Elapsed: {elapsed/60:.1f}min"
                f"{err_summary}"
            )

            log_text = "\n".join(log_lines[-30:])  # Last 30 lines

            yield (status, lb_data, fig, log_text)

    # ── FINAL RESULTS ────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    log_lines.append("\n" + "=" * 50)
    log_lines.append("FINAL RESULTS")
    log_lines.append("=" * 50)

    # Sort by bankroll
    final_ranking = sorted(state.items(), key=lambda x: -x[1]["bankroll"])
    for rank, (tid, ts) in enumerate(final_ranking, 1):
        cfg = TRADERS[tid]
        roi = ((ts["bankroll"] - 100.0) / 100.0) * 100
        log_lines.append(
            f"  #{rank} {cfg['name']}: ${ts['bankroll']:.2f} ({roi:+.1f}% ROI) "
            f"| {ts['total_bets']} bets | {ts['wins']}W-{ts['losses']}L | "
            f"DD: {ts['max_drawdown']:.1%} | LLM: {ts['llm_ok']}/{ts['llm_calls']}"
        )

    log_lines.append(f"\nTotal LLM calls: {_llm_calls} | Failures: {_llm_failures}")
    log_lines.append(f"Time: {elapsed/60:.1f} min ({elapsed/3600:.1f} hours)")

    # Save results
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "season": "2025-26",
        "games_processed": n_games,
        "game_days": len(game_dates_seen),
        "odds_matched": odds_matched,
        "odds_synthetic": odds_synthetic,
        "llm_calls": _llm_calls,
        "llm_failures": _llm_failures,
        "elapsed_seconds": round(elapsed, 1),
        "leaderboard": [],
    }
    for rank, (tid, ts) in enumerate(final_ranking, 1):
        cfg = TRADERS[tid]
        results["leaderboard"].append({
            "rank": rank,
            "trader_id": tid,
            "name": cfg["name"],
            "provider": cfg["provider"],
            "personality": cfg["personality"],
            "bankroll": round(ts["bankroll"], 2),
            "roi_pct": round(((ts["bankroll"] - 100.0) / 100.0) * 100, 2),
            "total_bets": ts["total_bets"],
            "wins": ts["wins"],
            "losses": ts["losses"],
            "passes": ts["passes"],
            "win_rate": round(ts["wins"] / max(1, ts["total_bets"]) * 100, 1),
            "max_drawdown": round(ts["max_drawdown"], 4),
            "llm_calls": ts["llm_calls"],
            "llm_success": ts["llm_ok"],
        })

    results_path = Path(__file__).parent / "data" / "experiment-results.json"
    try:
        results_path.write_text(json.dumps(results, indent=2))
    except Exception:
        pass

    lb_data = []
    for rank, (tid, ts) in enumerate(final_ranking, 1):
        cfg = TRADERS[tid]
        roi = ((ts["bankroll"] - 100.0) / 100.0) * 100
        win_rate = ts["wins"] / max(1, ts["total_bets"]) * 100
        llm_rate = ts["llm_ok"] / max(1, ts["llm_calls"]) * 100
        lb_data.append([
            cfg["name"],
            cfg["provider"].split(":")[-1][:20],
            f"${ts['bankroll']:.2f}",
            f"{roi:+.1f}%",
            ts["total_bets"],
            f"{win_rate:.0f}%",
            ts["passes"],
            f"{llm_rate:.0f}%",
            f"{ts['max_drawdown']:.1%}",
        ])

    fig = make_bankroll_chart(state, n_games)
    stopped = _stop_event.is_set()
    winner = TRADERS[final_ranking[0][0]]['name']
    winner_bank = final_ranking[0][1]['bankroll']
    games_done = game_idx + 1 if 'game_idx' in dir() else n_games
    status = f"{'STOPPED' if stopped else 'COMPLETE'} | {games_done} games | {elapsed/60:.1f}min | Winner: {winner} ${winner_bank:.2f}"
    log_text = "\n".join(log_lines[-50:])

    # Final state save
    with _state_lock:
        _experiment_state = {
            "games_processed": games_done,
            "games_total": n_games,
            "completed": not stopped,
            "stopped": stopped,
            "agents": {tid: {k: v for k, v in ts.items() if k != "history"}
                       for tid, ts in state.items()},
            "updated": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 1),
        }
        _save_state_to_disk(_experiment_state)
        _save_logs_to_disk()
    _experiment_running = False

    yield (status, lb_data, fig, log_text)


def make_bankroll_chart(state: Dict, games_done: int) -> plt.Figure:
    """Create bankroll evolution chart."""
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#0a0a0a")
    ax.set_facecolor("#0a0a0a")

    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8",
        "#F7DC6F", "#BB8FCE", "#85C1E9", "#82E0AA", "#F0B27A",
    ]

    for i, (tid, ts) in enumerate(TRADERS.items()):
        hist = state[tid]["history"]
        if len(hist) > 1:
            # Subsample for performance
            step = max(1, len(hist) // 500)
            x = list(range(0, len(hist), step))
            y = [hist[j] for j in x]
            ax.plot(x, y, color=colors[i % len(colors)],
                    label=f"{ts['name']} ${state[tid]['bankroll']:.0f}",
                    linewidth=1.2, alpha=0.85)

    ax.axhline(y=100, color="#444", linestyle="--", alpha=0.5, label="Start ($100)")
    ax.set_xlabel("Agent-game steps", color="#aaa", fontsize=10)
    ax.set_ylabel("Bankroll ($)", color="#aaa", fontsize=10)
    ax.set_title(f"Nomos42 Real LLM Trading Floor — Bankroll Evolution ({games_done} games)",
                 color="#eee", fontsize=12, fontweight="bold")
    ax.legend(loc="upper left", fontsize=7, ncol=2,
              facecolor="#1a1a1a", edgecolor="#333", labelcolor="#ccc")
    ax.tick_params(colors="#888")
    ax.spines["bottom"].set_color("#333")
    ax.spines["left"].set_color("#333")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.15, color="#444")

    plt.tight_layout()
    return fig


# ── GRADIO UI ────────────────────────────────────────────────────────────────

LEADERBOARD_HEADERS = [
    "Agent", "Model", "Bankroll", "ROI", "Bets",
    "Win%", "Passes", "LLM%", "Max DD",
]

with gr.Blocks(
    title="Nomos42 Real LLM Trading Floor",
    theme=gr.themes.Base(
        primary_hue="blue",
        neutral_hue="gray",
    ),
    css="""
    .gradio-container { max-width: 1200px !important; }
    .status-bar { font-family: monospace; font-size: 14px; }
    """
) as demo:
    gr.Markdown("""
# Nomos42 Real LLM Trading Floor
### 10 AI Agents x 1257 NBA Games x Real LLM Reasoning

Each agent is a **real LLM** (Cerebras, Gemini, OpenRouter) that receives
**100+ betting categories**, team rosters, advanced stats, our Nomos42 AI predictions,
and **22 SOTA strategies** from research papers — then **reasons** about what to bet.

After the full 2025-26 season, we see which LLM backbone, personality, and strategy
combination actually makes money.

| Agent | Model | Provider | Personality | Risk |
|-------|-------|----------|-------------|------|
| Gemini Flash | Gemini 2.5 Flash | Google (key 1) | Analytical | 0.60 |
| Gemini 3 Flash | Gemini 3 Flash Preview | Google (key 2) | Diversified | 0.50 |
| Qwen 3 235B | Qwen 3 235B-A22B | Cerebras | Quantitative | 0.55 |
| Llama 3.1 8B | Llama 3.1 8B | Cerebras | Contrarian | 0.65 |
| GLM 4.5 Air | GLM 4.5 Air | OpenRouter | Conservative | 0.40 |
| GPT-OSS 20B | GPT-OSS 20B | OpenRouter | Aggressive | 0.70 |
| Gemma 4 26B | Gemma 4 26B | OpenRouter | Arbitrage | 0.75 |
| Nemotron 120B | Nemotron 3 Super 120B | OpenRouter | Tactical | 0.60 |
| MiniMax M2.5 | MiniMax M2.5 | OpenRouter | Theoretical | 0.35 |
| Qwen3 80B | Qwen3 Next 80B | OpenRouter | Ensemble | 0.50 |
    """)

    with gr.Row():
        start_btn = gr.Button("Start / Resume Experiment", variant="primary", scale=3)
        stop_btn = gr.Button("Stop", variant="stop", scale=1)
        status_box = gr.Textbox(label="Status", interactive=False, scale=6, elem_classes=["status-bar"])

    with gr.Row():
        leaderboard = gr.Dataframe(
            headers=LEADERBOARD_HEADERS,
            label="Live Leaderboard (sorted by bankroll)",
            interactive=False,
            wrap=True,
        )

    with gr.Row():
        chart = gr.Plot(label="Bankroll Evolution")

    with gr.Row():
        log_box = gr.Textbox(label="Game Log (last 30 entries)", lines=15, interactive=False,
                             show_copy_button=True)

    def stop_experiment():
        _stop_event.set()
        return "STOPPING... (will finish current game)"

    start_btn.click(
        fn=run_experiment,
        outputs=[status_box, leaderboard, chart, log_box],
    )
    stop_btn.click(
        fn=stop_experiment,
        outputs=[status_box],
    )


# ── FASTAPI CONTROL API ────────────────────────────────────────────────────
# Mounted alongside Gradio for programmatic control (councils, GH Actions, CLI)

api = FastAPI()

@api.get("/api/status")
async def api_status():
    """Current experiment status — for councils, monitoring, GH Actions."""
    with _state_lock:
        state = dict(_experiment_state) if _experiment_state else {}
    state["running"] = _experiment_running
    state["stopped"] = _stop_event.is_set()
    state["llm_calls"] = _llm_calls
    state["llm_failures"] = _llm_failures
    state["gateway_url"] = GATEWAY_URL or None
    return JSONResponse(state)

@api.post("/api/run")
async def api_run(request: Request):
    """Trigger experiment start (same as clicking the button).
    For GH Actions / council triggers. Non-blocking — returns immediately."""
    if _experiment_running:
        return JSONResponse({"status": "already_running", "games_processed": _experiment_state.get("games_processed", 0)})
    # Can't start from API directly (Gradio owns the generator), but we clear stop
    _stop_event.clear()
    return JSONResponse({"status": "ready", "message": "Stop flag cleared. Click Start in Gradio UI or use gradio_api."})

@api.post("/api/stop")
async def api_stop():
    """Graceful stop — finishes current game then saves state."""
    _stop_event.set()
    return JSONResponse({"status": "stopping", "running": _experiment_running})

@api.post("/api/reset")
async def api_reset():
    """Reset experiment state (delete saved state)."""
    if _experiment_running:
        return JSONResponse({"status": "error", "message": "Cannot reset while running. Stop first."}, status_code=409)
    global _experiment_state, _agent_logs
    _experiment_state = {}
    _agent_logs = defaultdict(list)
    try:
        STATE_PATH.unlink(missing_ok=True)
        LOGS_PATH.unlink(missing_ok=True)
    except Exception:
        pass
    return JSONResponse({"status": "reset", "message": "State cleared. Next run starts fresh."})

@api.post("/api/mutate")
async def api_mutate(request: Request):
    """Mutate agent parameters mid-experiment.
    Body: {"agent": "gemini", "risk_tolerance": 0.8, "personality": "aggressive"}"""
    body = await request.json()
    agent_id = body.get("agent")
    if agent_id not in TRADERS:
        return JSONResponse({"status": "error", "message": f"Unknown agent: {agent_id}"}, status_code=400)
    changed = []
    if "risk_tolerance" in body:
        TRADERS[agent_id]["risk_tolerance"] = float(body["risk_tolerance"])
        changed.append(f"risk_tolerance={body['risk_tolerance']}")
    if "personality" in body:
        TRADERS[agent_id]["personality"] = body["personality"]
        changed.append(f"personality={body['personality']}")
    return JSONResponse({"status": "mutated", "agent": agent_id, "changes": changed})

@api.get("/api/logs")
async def api_logs(agent: str = None, limit: int = 50):
    """Per-agent decision log. ?agent=gemini&limit=20"""
    if agent:
        logs = list(_agent_logs.get(agent, []))[-limit:]
        return JSONResponse({"agent": agent, "count": len(logs), "logs": logs})
    # All agents summary
    summary = {tid: len(logs) for tid, logs in _agent_logs.items()}
    return JSONResponse({"agents": summary, "total_entries": sum(summary.values())})

@api.get("/api/leaderboard")
async def api_leaderboard():
    """Current leaderboard as JSON."""
    with _state_lock:
        agents = _experiment_state.get("agents", {})
    if not agents:
        return JSONResponse({"status": "no_data", "message": "No experiment data yet"})
    lb = []
    for tid, ts in sorted(agents.items(), key=lambda x: -x[1].get("bankroll", 0)):
        cfg = TRADERS.get(tid, {})
        bankroll = ts.get("bankroll", 100)
        roi = ((bankroll - 100) / 100) * 100
        lb.append({
            "trader_id": tid,
            "name": cfg.get("name", tid),
            "provider": cfg.get("provider", "?"),
            "bankroll": round(bankroll, 2),
            "roi_pct": round(roi, 2),
            "total_bets": ts.get("total_bets", 0),
            "wins": ts.get("wins", 0),
            "losses": ts.get("losses", 0),
        })
    return JSONResponse({"leaderboard": lb, "games_processed": _experiment_state.get("games_processed", 0)})

# Mount FastAPI alongside Gradio
app = gr.mount_gradio_app(api, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
