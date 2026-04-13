#!/usr/bin/env python3
"""
LLM Agents — Real LLM reasoning for Trading Floor decisions
============================================================
Each agent is a REAL LLM call. The agent receives full game context
(odds, standings, form, previous results, its own track record) and
returns a structured JSON decision: which bets to make, at what size.

Providers (all free or near-free):
  - Cerebras: llama3.3-70b, deepseek-r1-distill, llama-4-scout (FREE, 2000 tok/s)
  - Google: gemini-2.5-flash (FREE tier, 15 RPM)
  - OpenRouter: phi-4:free, llama-3.3-70b:free (FREE)

Cost for full season (1000 games x 10 agents = 10,000 calls):
  - Cerebras: $0 (free tier)
  - Gemini Flash: $0 (free tier, may hit rate limits)
  - OpenRouter free: $0

Architecture follows TradingAgents (arXiv 2412.20138) pattern:
  Context assembly -> Agent reasoning -> Structured JSON output -> Kelly sizing
"""

import json
import os
import time
import hashlib
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


# ── PROVIDER CONFIGS ─────────────────────────────────────────────────────────

PROVIDERS = {
    "cerebras:llama3.3-70b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama3.3-70b",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 500,
    },
    "cerebras:deepseek-r1-distill-llama-70b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "deepseek-r1-distill-llama-70b",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 500,
    },
    "cerebras:llama-4-scout-17b-16e-instruct": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama-4-scout-17b-16e-instruct",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 500,
    },
    "cerebras:llama3.1-8b": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama3.1-8b",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 500,
    },
    "cerebras:qwen-3-235b-a22b-instruct-2507": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "qwen-3-235b-a22b-instruct-2507",
        "key_env": "CEREBRAS_API_KEY",
        "max_tokens": 500,
    },
    "google:gemini-2.5-flash": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-04-17:generateContent",
        "model": "gemini-2.5-flash",
        "key_env": "GOOGLE_API_KEY_2",
        "max_tokens": 500,
    },
    "openrouter:meta-llama/llama-3.3-70b-instruct:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "max_tokens": 500,
    },
    "openrouter:microsoft/phi-4:free": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "microsoft/phi-4:free",
        "key_env": "OPENROUTER_KEY_ORCHESTRATOR",
        "max_tokens": 500,
    },
    "cohere:command-r-plus": {
        "url": "https://api.cohere.com/v2/chat",
        "model": "command-r-plus",
        "key_env": "COHERE_API_KEY",
        "max_tokens": 500,
    },
    "hf:google/gemma-3-27b-it": {
        "url": "https://api-inference.huggingface.co/models/google/gemma-3-27b-it/v1/chat/completions",
        "model": "google/gemma-3-27b-it",
        "key_env": "HF_TOKEN",
        "max_tokens": 500,
    },
}

# ── AGENT PERSONALITY PROMPTS ────────────────────────────────────────────────
# Each agent gets a system prompt that shapes HOW it reasons.
# This is the core of the experiment: does personality affect betting accuracy?

AGENT_SYSTEM_PROMPTS = {
    "gemini": """You are the Gemma Analyst, an analytical NBA betting agent.
You focus on statistical patterns and historical averages. You trust the numbers over narratives.
You prefer moderate bets with clear statistical edges. You avoid emotional or momentum-based reasoning.
Your risk tolerance is moderate (0.60). You use half-Kelly sizing.""",

    "openrouter": """You are the Qwen Strategist, a diversified NBA betting agent.
You rotate between strategies based on market conditions. You watch for value across all categories.
You're a contrarian on popular favorites and a follower on underdogs with statistical backing.
Your risk tolerance is moderate (0.50). You use quarter-Kelly sizing.""",

    "claude": """You are the Claude Sentinel, a conservative NBA betting agent.
You prioritize capital preservation over returns. You only bet when the edge is clear and large.
You focus on drawdown minimization and only take high-conviction positions.
Your risk tolerance is low (0.40). You use half-Kelly sizing with a drawdown adjustment.""",

    "codex": """You are the Llama Vanguard, an aggressive NBA betting agent.
You seek maximum returns and are willing to accept volatility. You bet big on strong edges.
You focus on win rate maximization and favor high-probability outcomes at reasonable odds.
Your risk tolerance is high (0.70). You use full-Kelly sizing.""",

    "grok": """You are the Mistral Maverick, a contrarian NBA betting agent.
You specialize in underdogs and look for spots where the market is wrong.
You love fading the public, betting against the consensus, and finding value in longshots.
Your risk tolerance is high (0.65). You use aggressive sizing on high-value underdogs.""",

    "deepseek": """You are the DeepSeek Quant, a quantitative NBA betting agent.
You focus purely on the numbers: model predictions, implied probabilities, and edges.
You minimize variance by spreading bets evenly across high-confidence picks.
Your risk tolerance is moderate (0.55). You use flat 2% sizing on qualifying bets.""",

    "phi": """You are the Phi Theorist, a theoretical NBA betting agent.
You are extremely selective — you only bet when the model-vs-market disagreement is large.
You believe in information ratio maximization: few bets, high conviction.
Your risk tolerance is very low (0.35). You use quarter-Kelly sizing.""",

    "cohere": """You are the Command Tactician, a tactical NBA betting agent.
You focus on momentum and recent form. You ride winning streaks and fade losing teams.
You optimize for Sortino ratio — you accept upside volatility but protect against drawdowns.
Your risk tolerance is moderate (0.60). You use half-Kelly with momentum adjustments.""",

    "gemma": """You are the Gemma Arbitrageur, an aggressive arbitrage NBA betting agent.
You hunt for the biggest model-vs-market disagreements and bet heavily on them.
You specialize in alternative markets (props, totals, quarters) where the market is thinner.
Your risk tolerance is very high (0.75). You use full-Kelly on large edges.""",

    "mixtral": """You are the Mixtral Ensemble, a consensus-seeking NBA betting agent.
You look at all model predictions and only bet when multiple models agree.
You diversify across categories and avoid concentrating in any single bet type.
Your risk tolerance is moderate (0.50). You use flat 2% sizing with consensus scaling.""",
}


# ── CORE LLM CALL ────────────────────────────────────────────────────────────

def _call_llm(provider: str, system_prompt: str, user_prompt: str,
              timeout: float = 15.0) -> Optional[str]:
    """Make a real LLM API call. Returns raw text response or None on failure."""
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return None

    api_key = os.environ.get(cfg["key_env"], "")
    if not api_key:
        return None

    try:
        if "gemini" in provider and "google" in provider:
            # Google Gemini API (different format)
            url = f"{cfg['url']}?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                "generationConfig": {"maxOutputTokens": cfg["max_tokens"], "temperature": 0.3},
            }
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        elif "cohere" in provider:
            # Cohere v2 API
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
        elif "huggingface" in cfg["url"] or "hf" in provider:
            # HuggingFace Inference API (OpenAI-compatible)
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
    except Exception as e:
        print(f"[LLM] {provider} error: {e}")
        return None

    return None


# ── GAME DECISION PROMPT ─────────────────────────────────────────────────────

def build_game_prompt(game_ctx: Dict, trader_state: Dict) -> str:
    """Build the user prompt that presents the game to the agent."""
    odds = game_ctx.get("odds", {})
    home_std = game_ctx.get("home_standings", {})
    away_std = game_ctx.get("away_standings", {})
    home_form = game_ctx.get("home_form_L10", {})
    away_form = game_ctx.get("away_form_L10", {})
    models = game_ctx.get("models", {})

    # Model predictions summary
    model_lines = []
    for mname, mpred in models.items():
        if isinstance(mpred, dict) and "home_win_prob" in mpred:
            model_lines.append(f"  {mname}: {mpred['home_win_prob']:.1%} home win")
        elif isinstance(mpred, (int, float)):
            model_lines.append(f"  {mname}: {mpred:.1%} home win")
    model_summary = "\n".join(model_lines) if model_lines else "  No model predictions available"

    # Track record
    bankroll = trader_state.get("nba_bankroll", trader_state.get("bankroll_nba", 100.0))
    total_bets = trader_state.get("total_bets", 0)
    wins = trader_state.get("wins", 0)
    losses = trader_state.get("losses", 0)
    roi = trader_state.get("roi_pct", 0.0)

    prompt = f"""GAME: {game_ctx.get('home', '?')} vs {game_ctx.get('away', '?')}
Date: {game_ctx.get('date', '?')}

ODDS:
  Moneyline home: {odds.get('ml_home_dec', '?')} | away: {odds.get('ml_away_dec', '?')}
  Spread home: {odds.get('spread_home', '?')}
  Total: {odds.get('total', '?')}

STANDINGS:
  Home ({game_ctx.get('home', '?')}): {home_std.get('wins', '?')}-{home_std.get('losses', '?')} ({home_std.get('win_pct', '?')})
  Away ({game_ctx.get('away', '?')}): {away_std.get('wins', '?')}-{away_std.get('losses', '?')} ({away_std.get('win_pct', '?')})

RECENT FORM (last 10):
  Home: {home_form.get('record', '?')}
  Away: {away_form.get('record', '?')}

MODEL PREDICTIONS:
{model_summary}

YOUR TRACK RECORD:
  Bankroll: ${bankroll:.2f} (started $100)
  Bets: {total_bets} | Wins: {wins} | Losses: {losses}
  ROI: {roi:+.1f}%

AVAILABLE BET CATEGORIES:
  ml_home, ml_away (moneyline)
  spread_home, spread_away
  total_over, total_under
  h1_ml_home, h1_ml_away (first half)
  team_total_home_over, team_total_home_under

Respond with ONLY a JSON object. Do NOT include any text before or after the JSON.
Format:
{{
  "reasoning": "Brief 1-2 sentence reasoning",
  "bets": [
    {{"category": "ml_home", "confidence": 0.65, "edge": 0.05, "bet_pct": 0.02}},
  ],
  "pass": false
}}

Rules:
- "confidence": your probability estimate (0.0-1.0)
- "edge": your estimated edge vs the market (positive = value bet)
- "bet_pct": fraction of bankroll to bet (0.001-0.10)
- Set "pass": true and empty bets if you see no value
- Max 3 bets per game
- Be honest — if you don't see an edge, pass"""

    return prompt


# ── PARSE LLM RESPONSE ──────────────────────────────────────────────────────

def parse_llm_decision(raw: str) -> Optional[Dict]:
    """Extract JSON decision from LLM response."""
    if not raw:
        return None
    # Try to find JSON in the response
    text = raw.strip()
    # Remove markdown code fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


# ── MAIN AGENT DECISION ─────────────────────────────────────────────────────

def agent_llm_decide(trader_id: str, provider: str, game_ctx: Dict,
                     trader_state: Dict) -> Dict:
    """
    Make a REAL LLM decision for one game.
    Returns: {"bets": [...], "reasoning": "...", "llm_used": True/False, "provider": "..."}
    """
    system_prompt = AGENT_SYSTEM_PROMPTS.get(trader_id, "You are an NBA betting agent.")
    user_prompt = build_game_prompt(game_ctx, trader_state)

    # Try LLM call
    raw_response = _call_llm(provider, system_prompt, user_prompt)

    if raw_response:
        decision = parse_llm_decision(raw_response)
        if decision and isinstance(decision.get("bets"), list):
            return {
                "bets": decision["bets"],
                "reasoning": decision.get("reasoning", "LLM decision"),
                "pass": decision.get("pass", False),
                "llm_used": True,
                "provider": provider,
                "raw_response_len": len(raw_response),
            }

    # Fallback: no LLM available, return pass
    return {
        "bets": [],
        "reasoning": "LLM unavailable — passing",
        "pass": True,
        "llm_used": False,
        "provider": provider,
    }


# ── POLITICAL DECISION ──────────────────────────────────────────────────────

POLITICAL_SYSTEM_PROMPTS = {
    "gemini": """You are the Gemma Analyst, a momentum-focused political-to-ETF trader.
You analyze executive orders, Fed rules, and tech sector policy to decide ETF positions.
Focus: XLK, QQQ, SPY. You follow trends and ride momentum.""",

    "openrouter": """You are the Qwen Strategist, a macro sector-rotation ETF trader.
You rotate between sectors based on Fed policy and tariff signals.
Focus: SPY, IWM, XLF, XLE. You follow insider trading patterns.""",

    "claude": """You are the Claude Sentinel, a conservative safe-haven ETF trader.
You move to bonds and gold during uncertainty. You follow Fed rate signals closely.
Focus: TLT, GLD, XLV. Mean reversion strategy.""",

    "codex": """You are the Llama Vanguard, an aggressive event-driven ETF trader.
You trade on breaking political events: executive orders, prediction market moves.
Focus: QQQ, XLK, TSLA. You bet big on catalysts.""",

    "grok": """You are the Mistral Maverick, an energy contrarian ETF trader.
You fade the consensus on energy and commodities. You love tariff plays.
Focus: XLE, GLD, IWM. Pairs trading specialist.""",
}

# Add remaining agents with shorter prompts
for tid in ["deepseek", "phi", "cohere", "gemma", "mixtral"]:
    if tid not in POLITICAL_SYSTEM_PROMPTS:
        POLITICAL_SYSTEM_PROMPTS[tid] = AGENT_SYSTEM_PROMPTS.get(tid, "You are a political-to-ETF trader.").replace("NBA betting", "political-to-ETF trading")


def build_political_prompt(signals: Dict, events: List, trader_state: Dict,
                           available_tickers: List[str]) -> str:
    """Build prompt for political ETF trading decisions."""
    events_text = "\n".join(f"  - {e.get('type', '?')}: {e.get('summary', '?')}" for e in events[:10]) if events else "  No recent events"
    signals_text = json.dumps(signals, indent=2)[:800] if signals else "  No signals"

    bankroll = trader_state.get("political_bankroll", trader_state.get("capital", 100000.0))

    return f"""POLITICAL SIGNALS:
{signals_text}

RECENT EVENTS:
{events_text}

AVAILABLE TICKERS: {', '.join(available_tickers[:15])}

YOUR PORTFOLIO:
  Capital: ${bankroll:,.2f}

Respond with ONLY a JSON object:
{{
  "reasoning": "Brief reasoning",
  "positions": [
    {{"ticker": "XLK", "direction": "long", "conviction": 0.7, "pct_capital": 0.05}},
  ],
  "pass": false
}}

Rules:
- direction: "long" or "short"
- conviction: 0.0-1.0
- pct_capital: fraction of capital (0.01-0.10)
- Max 5 positions
- Set "pass": true if no clear signal"""


# ── BATCH HELPERS ────────────────────────────────────────────────────────────

_LLM_CALL_COUNT = 0
_LLM_CALL_FAILURES = 0


def get_llm_stats() -> Dict:
    """Return stats about LLM usage in this session."""
    return {
        "total_calls": _LLM_CALL_COUNT,
        "failures": _LLM_CALL_FAILURES,
        "success_rate": round((_LLM_CALL_COUNT - _LLM_CALL_FAILURES) / max(1, _LLM_CALL_COUNT) * 100, 1),
    }
