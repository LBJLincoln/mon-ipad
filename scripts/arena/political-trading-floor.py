#!/usr/bin/env python3
"""
Political Trading Floor — Multi-AI ETF/Stock Competition
=========================================================
5 AI agents (Gemini, OpenRouter, Claude, Codex, Grok) compete on:
  - Political signal-driven ETF/stock trading
  - Historical event backtesting (exec orders, fed rules, insider trades, polymarket)
  - Daily social sentiment rebalancing

Each agent starts with $100,000 virtual capital and trades based on
political signals from nomos-political-alpha.

Output: JSON state files compatible with the NBA trading floor dashboard.
State saved to: data/arena/traders/political-{trader_id}-state.json

Usage:
  python3 political-trading-floor.py run          # Full backtest
  python3 political-trading-floor.py karpathy     # Karpathy loop (backtest + analyze + mutate)
  python3 political-trading-floor.py leaderboard  # Show current standings
  python3 political-trading-floor.py status       # Quick status summary
"""

import json, os, sys, math, hashlib, time, signal as _signal, subprocess
from pathlib import Path
from datetime import datetime, timezone, date
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# ── PATHS ────────────────────────────────────────────────────────────────────
ROOT        = Path('/home/termius/mon-ipad')
POLITICAL   = Path('/home/termius/nomos-political-alpha')
DATA_DIR    = ROOT / 'data' / 'arena'
TRADERS_DIR = DATA_DIR / 'traders'
POL_DIR     = DATA_DIR / 'political'

INITIAL_CAPITAL = 100_000.0

# ── ITERATION TRACKING ───────────────────────────────────────────────────────
_ITERATION_FILE = DATA_DIR / 'political-trading-floor-iteration.json'

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

# ── ELIMINATED POLITICAL STRATEGIES ─────────────────────────────────────────
ELIMINATED_STRATEGIES: Dict[str, Dict] = {
    "SECTOR_ROTATE": {
        "eliminated_at": "2026-03-31",
        "reason": "-75% ROI",
        "final_roi": -0.75,
    },
    "DEFENSE_LONG_individual": {
        "eliminated_at": "2026-03-31",
        "reason": "-65% ROI on individual defense stock picks",
        "final_roi": -0.65,
    },
    "BILL_PASSES": {
        "eliminated_at": "2026-03-31",
        "reason": "-64% ROI",
        "final_roi": -0.64,
    },
}

# ── ETF / STOCK UNIVERSE ────────────────────────────────────────────────────
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

SECTOR_MAP = {
    "defense":     ["XLD", "LMT", "RTX", "BA", "GD", "NOC"],
    "technology":  ["XLK", "QQQ", "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMZN", "TSLA"],
    "energy":      ["XLE", "XOM", "CVX", "COP", "OXY", "HAL"],
    "healthcare":  ["XLV", "PFE", "JNJ", "UNH"],
    "financials":  ["XLF", "JPM", "GS", "MS", "BLK", "AXP"],
    "broad":       ["SPY", "IWM"],
    "small_cap":   ["IWM"],
    "industrials": ["XLI"],
    "commodity":   ["GLD"],
    "bonds":       ["TLT"],
}

# ── POLITICAL EVENT CATEGORIES (markets) ────────────────────────────────────
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

# ── POLITICAL TRADING STRATEGIES ────────────────────────────────────────────
STRATEGIES = {
    "momentum": {
        "desc": "Follow political momentum signals",
        "position_pct": 0.05,    # 5% of capital per position
        "min_signal": 0.10,      # min signal strength to trade
        "max_positions": 10,     # max concurrent positions
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

# ── AI TRADER DEFINITIONS ───────────────────────────────────────────────────
# TRADER POOL — refactored 2026-04-07 from paid APIs to FREE HF models.
# Same rebrand as scripts/arena/trading-floor-v4.py (NBA-side). Dict keys preserved
# so existing state files under data/arena/traders/political-{key}-state.json keep
# accumulating bankroll history. Only `name` and `provider` change.
# Free HF models are routed via the HF Inference API; we have 4 HF accounts so
# rate limits are effectively unlimited for batch trading.
TRADERS = {
    "gemini": {  # was Google Gemini → now Gemma 3 27B (free, HF)
        "name":               "Gemma 3 27B",
        "provider":           "hf:google/gemma-3-27b-it",
        "personality":        "analytical",
        "risk_tolerance":     0.60,
        "capital":            INITIAL_CAPITAL,
        "primary_strategy":   "momentum",
        "secondary_strategies": ["sector_rotation", "vol_scaled"],
        "sector_focus":       ["technology", "broad", "defense"],
        "ticker_focus":       ["XLK", "QQQ", "SPY", "LMT", "NVDA", "MSFT"],
        "event_weight":       {"exec_order": 1.2, "fed_rule": 1.0, "insider_trade": 0.8, "polymarket": 0.9},
    },
    "openrouter": {  # was OpenRouter → now Qwen 3 72B (free, HF)
        "name":               "Qwen 3 72B",
        "provider":           "hf:Qwen/Qwen2.5-72B-Instruct",
        "personality":        "diversified",
        "risk_tolerance":     0.50,
        "capital":            INITIAL_CAPITAL,
        "primary_strategy":   "sector_rotation",
        "secondary_strategies": ["insider_follow", "pairs_trading"],
        "sector_focus":       ["broad", "energy", "financials", "small_cap"],
        "ticker_focus":       ["SPY", "IWM", "XLF", "XLE", "JPM", "XOM"],
        "event_weight":       {"exec_order": 1.0, "fed_rule": 1.1, "insider_trade": 1.2, "polymarket": 0.8},
    },
    "claude": {  # Claude Code CLI — already free locally
        "name":               "Claude Code CLI",
        "provider":           "anthropic_cli",
        "personality":        "conservative",
        "risk_tolerance":     0.40,
        "capital":            INITIAL_CAPITAL,
        "primary_strategy":   "mean_reversion",
        "secondary_strategies": ["safe_haven", "vol_scaled"],
        "sector_focus":       ["bonds", "commodity", "healthcare"],
        "ticker_focus":       ["TLT", "GLD", "XLV", "JNJ", "UNH", "SPY"],
        "event_weight":       {"exec_order": 0.8, "fed_rule": 1.3, "insider_trade": 0.7, "polymarket": 1.0},
    },
    "codex": {  # was OpenAI Codex → now Llama 3.3 70B (free, HF)
        "name":               "Llama 3.3 70B",
        "provider":           "hf:meta-llama/Llama-3.3-70B-Instruct",
        "personality":        "aggressive",
        "risk_tolerance":     0.75,
        "capital":            INITIAL_CAPITAL,
        "primary_strategy":   "event_driven",
        "secondary_strategies": ["momentum", "insider_follow"],
        "sector_focus":       ["technology", "defense", "energy"],
        "ticker_focus":       ["QQQ", "XLK", "NVDA", "BA", "TSLA", "META"],
        "event_weight":       {"exec_order": 1.5, "fed_rule": 0.7, "insider_trade": 1.0, "polymarket": 1.3},
    },
    "grok": {  # was xAI Grok → now Mistral Large 2 (free, HF)
        "name":               "Mistral Large 2",
        "provider":           "hf:mistralai/Mistral-Large-Instruct-2411",
        "personality":        "contrarian",
        "risk_tolerance":     0.65,
        "capital":            INITIAL_CAPITAL,
        "primary_strategy":   "pairs_trading",
        "secondary_strategies": ["mean_reversion", "insider_follow"],
        "sector_focus":       ["energy", "commodity", "small_cap", "bonds"],
        "ticker_focus":       ["XLE", "GLD", "IWM", "TLT", "OXY", "CVX"],
        "event_weight":       {"exec_order": 0.9, "fed_rule": 1.0, "insider_trade": 1.3, "polymarket": 1.1},
    },
    "glm": {  # GLM-5.1 (Z.ai, Apr 2026) — 754B MoE, #1 SWE-Bench Pro, via OpenRouter
        "name":               "GLM-5.1 Architect",
        "provider":           "openrouter:z-ai/glm-5.1",
        "personality":        "systematic",
        "risk_tolerance":     0.55,
        "capital":            INITIAL_CAPITAL,
        "primary_strategy":   "vol_scaled",
        "secondary_strategies": ["sector_rotation", "event_driven"],
        "sector_focus":       ["technology", "broad", "financials", "healthcare"],
        "ticker_focus":       ["SPY", "QQQ", "XLF", "XLV", "NVDA", "AAPL"],
        "event_weight":       {"exec_order": 1.1, "fed_rule": 1.2, "insider_trade": 1.0, "polymarket": 1.1},
    },
}

# ── TRADER CONFIG PERSISTENCE ────────────────────────────────────────────────
TRADER_CONFIG_FILE = DATA_DIR / 'political-trader-configs-evolved.json'

def _load_evolved_configs() -> None:
    """Load evolved trader configs from disk, overriding defaults."""
    if not TRADER_CONFIG_FILE.exists():
        return
    try:
        saved = json.loads(TRADER_CONFIG_FILE.read_text())
        for tid, cfg in saved.items():
            if tid in TRADERS:
                for key in ("primary_strategy", "secondary_strategies",
                            "risk_tolerance", "ticker_focus"):
                    if key in cfg:
                        TRADERS[tid][key] = cfg[key]
    except Exception:
        pass

def _save_evolved_configs() -> None:
    """Persist current trader configs to disk."""
    configs = {}
    for tid, t in TRADERS.items():
        configs[tid] = {
            "primary_strategy": t.get("primary_strategy"),
            "secondary_strategies": t.get("secondary_strategies", []),
            "risk_tolerance": t.get("risk_tolerance", 0.5),
            "ticker_focus": t.get("ticker_focus", []),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    TRADER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRADER_CONFIG_FILE.write_text(json.dumps(configs, indent=2))

_load_evolved_configs()


# ── DATA LOADERS ─────────────────────────────────────────────────────────────

def load_political_events() -> List[Dict]:
    """Load consolidated political events from nomos-political-alpha."""
    fp = POLITICAL / "data" / "historical" / "consolidated_events.json"
    if not fp.exists():
        print(f"  WARNING: {fp} not found")
        return []
    try:
        events = json.loads(fp.read_text())
        # Sort by date
        events.sort(key=lambda e: e.get("date", ""))
        return events
    except Exception as e:
        print(f"  ERROR loading events: {e}")
        return []


def load_social_signals() -> Dict:
    """Load latest social signals from nomos-political-alpha."""
    fp = POLITICAL / "data" / "social" / "social_signals_latest.json"
    if fp.exists():
        try:
            data = json.loads(fp.read_text())
            return data.get("signals", data)
        except Exception:
            pass
    return {}


def load_all_social_snapshots() -> List[Tuple[str, Dict]]:
    """Load all historical social signal snapshots, sorted by timestamp.
    Returns list of (timestamp_str, signals_dict)."""
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
            # Extract timestamp from filename: social_signals_YYYYMMDD_HHMM.json
            ts = fp.stem.replace("social_signals_", "")
            snapshots.append((ts, sigs))
        except Exception:
            continue
    return snapshots


def load_other_trader_states(exclude: str) -> Dict:
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


# ── SIGNAL COMPUTATION ───────────────────────────────────────────────────────

def compute_ticker_signal(ticker: str, social_signals: Dict,
                          events_for_day: List[Dict]) -> Dict:
    """
    Compute combined signal for one ticker from social signals + political events.
    Returns: {direction, strength, components}
    """
    components = []
    total_strength = 0.0
    total_direction = 0.0  # positive = long, negative = short

    # Social sentiment signal
    if ticker in social_signals:
        sig = social_signals[ticker]
        sentiment = sig.get("combined_sentiment", 0.0)
        strength = sig.get("signal_strength", 0.0)
        if strength > 0.01:
            components.append({
                "source": "social",
                "sentiment": sentiment,
                "strength": strength,
                "mentions": sig.get("total_mentions", 0),
            })
            total_strength += strength
            total_direction += sentiment * strength

    # Event-driven signal
    ticker_events = [e for e in events_for_day if e.get("ticker") == ticker]
    for ev in ticker_events:
        ev_strength = ev.get("signal_strength", 0.5)
        ev_outcome = ev.get("outcome", 0.5)
        # outcome=1 means positive for stock, outcome=0 means negative
        ev_direction = (ev_outcome - 0.5) * 2  # map [0,1] -> [-1,1]
        components.append({
            "source": "event",
            "event_type": ev.get("event_type", "unknown"),
            "title": ev.get("title", "")[:60],
            "strength": ev_strength,
            "direction": ev_direction,
        })
        total_strength += ev_strength * 0.5
        total_direction += ev_direction * ev_strength * 0.5

    # Sector spillover: if no direct signal, use sector average
    if not components:
        etf_info = ETF_UNIVERSE.get(ticker, {})
        sector = etf_info.get("sector", "")
        sector_tickers = SECTOR_MAP.get(sector, [])
        sector_sigs = []
        for st in sector_tickers:
            if st != ticker and st in social_signals:
                s = social_signals[st]
                if s.get("signal_strength", 0) > 0.01:
                    sector_sigs.append(s.get("combined_sentiment", 0.0) * s.get("signal_strength", 0.0))
        if sector_sigs:
            avg = sum(sector_sigs) / len(sector_sigs)
            components.append({
                "source": "sector_spillover",
                "strength": min(abs(avg), 0.3),
                "direction": 1.0 if avg > 0 else -1.0,
            })
            total_strength += min(abs(avg), 0.3)
            total_direction += avg

    if total_strength < 0.01:
        return {"direction": "neutral", "strength": 0.0, "components": []}

    net_direction = total_direction / total_strength if total_strength > 0 else 0.0
    direction = "long" if net_direction > 0 else ("short" if net_direction < 0 else "neutral")

    return {
        "direction": direction,
        "strength": min(total_strength, 1.0),
        "net_direction": round(net_direction, 4),
        "components": components,
    }


# ── POSITION SIZING ─────────────────────────────────────────────────────────

def compute_position_size(strategy_name: str, signal: Dict, capital: float,
                          risk_tolerance: float, existing_positions: int) -> float:
    """Compute position size in USD for a given signal and strategy."""
    cfg = STRATEGIES.get(strategy_name, STRATEGIES["momentum"])

    if signal["direction"] == "neutral":
        return 0.0
    if signal["strength"] < cfg["min_signal"]:
        return 0.0
    if existing_positions >= cfg["max_positions"]:
        return 0.0

    base_pct = cfg["position_pct"] * risk_tolerance
    # Scale by signal strength
    scaled_pct = base_pct * min(signal["strength"] * 2, 1.0)
    # Capital protection: reduce size if capital has declined
    if capital < INITIAL_CAPITAL * 0.8:
        scaled_pct *= 0.5
    elif capital < INITIAL_CAPITAL * 0.5:
        scaled_pct *= 0.25

    position_usd = capital * scaled_pct
    return round(max(position_usd, 0.0), 2)


# ── TRADE OUTCOME SIMULATION ────────────────────────────────────────────────

def simulate_trade_outcome(ticker: str, direction: str, signal_strength: float,
                           event_return: Optional[float], seed: str) -> float:
    """
    Simulate the return of a political trade.
    Uses deterministic hash + signal strength + beta for reproducibility.
    When event data has excess_return, incorporates it.
    """
    etf_info = ETF_UNIVERSE.get(ticker, {"beta": 1.0})
    beta = etf_info.get("beta", 1.0)

    # Deterministic noise from seed
    h = int(hashlib.md5(f"pol_{ticker}_{seed}".encode()).hexdigest()[:8], 16)
    noise = ((h % 10000) / 10000.0 - 0.5) * 0.04  # +/- 2% base noise

    # Signal-driven expected return
    if event_return is not None:
        # We have actual excess return data from the consolidated events
        base_return = event_return
    else:
        # Simulate based on signal strength
        h2 = int(hashlib.md5(f"ret_{ticker}_{seed}".encode()).hexdigest()[:6], 16)
        market_move = ((h2 % 1000) / 1000.0 - 0.45) * 0.02  # Slight positive bias
        base_return = market_move * beta + signal_strength * 0.005

    # Final return
    trade_return = base_return + noise
    if direction == "short":
        trade_return *= -1

    return round(trade_return, 6)


# ── AGENT DECISION ENGINE ───────────────────────────────────────────────────

def agent_decide_positions(trader_id: str, day_date: str, capital: float,
                           social_signals: Dict, day_events: List[Dict],
                           others: Dict, existing_positions: int) -> List[Dict]:
    """
    Agent decides all positions for one trading day.
    Returns list of position dicts with full justification.
    """
    cfg = TRADERS[trader_id]
    personality = cfg["personality"]
    primary_strat = cfg["primary_strategy"]
    secondary_strats = cfg["secondary_strategies"]
    risk = cfg["risk_tolerance"]
    focus_tickers = cfg["ticker_focus"]
    sector_focus = cfg["sector_focus"]
    event_weights = cfg.get("event_weight", {})

    # Build candidate tickers based on focus
    candidates = list(focus_tickers)
    # Also add any ticker with a strong enough signal
    for sector in sector_focus:
        for ticker in SECTOR_MAP.get(sector, []):
            if ticker not in candidates:
                candidates.append(ticker)

    positions = []
    budget_remaining = capital * risk * 0.3  # Max 30% of risk-adjusted capital per day
    pos_count = existing_positions

    for ticker in candidates:
        if budget_remaining <= 0:
            break

        signal = compute_ticker_signal(ticker, social_signals, day_events)
        if signal["direction"] == "neutral":
            continue

        # Apply event weight bias
        for comp in signal.get("components", []):
            if comp.get("source") == "event":
                ev_type = comp.get("event_type", "")
                weight = event_weights.get(ev_type, 1.0)
                signal["strength"] = min(signal["strength"] * weight, 1.0)

        # Pick strategy based on personality and context
        chosen_strat = primary_strat

        if personality == "analytical":
            # Use primary for strong signals, secondary for weak
            if signal["strength"] < 0.2 and secondary_strats:
                chosen_strat = secondary_strats[0]
        elif personality == "diversified":
            # Rotate strategies
            h = int(hashlib.md5(f"{day_date}_{ticker}".encode()).hexdigest()[:4], 16)
            all_strats = [primary_strat] + secondary_strats
            chosen_strat = all_strats[h % len(all_strats)]
        elif personality == "conservative":
            # If trailing, switch to safe haven
            other_caps = [s.get("capital", INITIAL_CAPITAL) for s in others.values()]
            avg_other = sum(other_caps) / len(other_caps) if other_caps else capital
            if capital < avg_other * 0.9 and "safe_haven" in [primary_strat] + secondary_strats:
                chosen_strat = "safe_haven"
        elif personality == "aggressive":
            # Use event_driven for strong signals, momentum otherwise
            if signal["strength"] > 0.3:
                chosen_strat = "event_driven"
            elif secondary_strats:
                chosen_strat = secondary_strats[0]
        elif personality == "contrarian":
            # Fade strong signals (mean_reversion), follow weak ones (pairs)
            if signal["strength"] > 0.25:
                chosen_strat = "mean_reversion" if "mean_reversion" in [primary_strat] + secondary_strats else primary_strat
                # Reverse direction for contrarian plays
                signal = dict(signal)
                signal["direction"] = "short" if signal["direction"] == "long" else "long"
                signal["net_direction"] = -signal.get("net_direction", 0)

        # Skip eliminated strategies
        if chosen_strat in ELIMINATED_STRATEGIES:
            continue

        # Size the position
        size = compute_position_size(chosen_strat, signal, capital, risk, pos_count)
        if size <= 0 or size > budget_remaining:
            size = min(size, budget_remaining) if size > 0 else 0
        if size <= 0:
            continue

        # Find matching event return if available
        event_return = None
        ticker_events = [e for e in day_events if e.get("ticker") == ticker]
        if ticker_events:
            event_return = ticker_events[0].get("excess_return")

        # Simulate outcome
        seed = f"{day_date}_{trader_id}_{ticker}_{chosen_strat}"
        trade_return = simulate_trade_outcome(
            ticker, signal["direction"], signal["strength"], event_return, seed
        )
        pnl = size * trade_return

        # Build reasoning
        reasoning_parts = []
        reasoning_parts.append(f"strategy={chosen_strat}")
        reasoning_parts.append(f"signal={signal['strength']:.3f} {signal['direction']}")
        if ticker_events:
            reasoning_parts.append(f"event={ticker_events[0].get('event_type','?')}")
        reasoning_parts.append(f"beta={ETF_UNIVERSE.get(ticker, {}).get('beta', 1.0)}")

        position = {
            "date":           day_date,
            "ticker":         ticker,
            "name":           ETF_UNIVERSE.get(ticker, {}).get("name", ticker),
            "type":           ETF_UNIVERSE.get(ticker, {}).get("type", "stock"),
            "sector":         ETF_UNIVERSE.get(ticker, {}).get("sector", "unknown"),
            "direction":      signal["direction"],
            "strategy_used":  chosen_strat,
            "signal_strength": round(signal["strength"], 4),
            "net_direction":  signal.get("net_direction", 0),
            "position_size":  size,
            "trade_return":   trade_return,
            "pnl":            round(pnl, 2),
            "outcome":        "Win" if pnl > 0 else "Loss",
            "reasoning":      " | ".join(reasoning_parts),
            "event_count":    len(ticker_events),
        }
        positions.append(position)
        budget_remaining -= size
        pos_count += 1

    return positions


# ── FULL BACKTEST PER AGENT ──────────────────────────────────────────────────

def run_backtest_for_agent(trader_id: str, events: List[Dict],
                           social_snapshots: List[Tuple[str, Dict]],
                           latest_signals: Dict,
                           others_states: Dict) -> Dict:
    """
    Run political ETF trading backtest for one AI agent.
    Iterates through each day of political events, makes decisions, tracks P&L.
    """
    capital = TRADERS[trader_id]["capital"]
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

    # Group events by date
    events_by_date: Dict[str, List[Dict]] = defaultdict(list)
    for ev in events:
        d = ev.get("date", "")
        if d:
            events_by_date[d].append(ev)
    sorted_dates = sorted(events_by_date.keys())

    # Map social snapshots to date approximations
    # snapshot timestamps are like "20260328_0430"
    signal_by_date: Dict[str, Dict] = {}
    for ts, sigs in social_snapshots:
        try:
            d = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            signal_by_date[d] = sigs  # Last snapshot for each date wins
        except Exception:
            continue
    # Add dates from events that might not have social snapshots
    if latest_signals:
        for d in sorted_dates:
            if d not in signal_by_date:
                signal_by_date[d] = latest_signals

    for day_num, day_date in enumerate(sorted_dates, 1):
        if capital <= 0:
            break

        day_events = events_by_date.get(day_date, [])
        day_signals = signal_by_date.get(day_date, latest_signals)

        positions = agent_decide_positions(
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
            # Track intraday peak for accurate drawdown measurement
            if capital > peak_capital:
                peak_capital = capital
            # Compute drawdown after each trade (intraday, not just end-of-day)
            dd = 1.0 - capital / peak_capital if peak_capital > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd

            sector_pnl[pos.get("sector", "unknown")] += pnl
            strategy_pnl[pos["strategy_used"]]["count"] += 1
            strategy_pnl[pos["strategy_used"]]["pnl"] += pnl
            ticker_pnl[pos["ticker"]]["count"] += 1
            ticker_pnl[pos["ticker"]]["pnl"] += pnl
            day_strategies.add(pos["strategy_used"])
            day_sectors.add(pos.get("sector", "unknown"))

            pos["capital_after"] = round(capital, 2)
            all_trades.append(pos)

        day_results.append({
            "day":        day_num,
            "date":       day_date,
            "trades":     day_trade_count,
            "events":     len(day_events),
            "pnl":        round(day_pnl, 2),
            "capital":    round(capital, 2),
            "strategies": list(day_strategies),
            "sectors":    list(day_sectors),
        })

    roi_pct = round((capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 4)

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
            "trades": stats["count"],
            "pnl": round(stats["pnl"], 2),
            "wins": stats["wins"],
            "win_rate": round(stats["wins"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0,
            "roi_pct": round(stats["pnl"] / max(stats["count"] * 1000, 1) * 100, 2),
        }

    # Sector breakdown
    sector_breakdown = {s: round(pnl, 2) for s, pnl in sorted(sector_pnl.items(), key=lambda x: -x[1])}

    # Top/bottom tickers
    ticker_breakdown = {}
    for t, stats in sorted(ticker_pnl.items(), key=lambda x: -x[1]["pnl"]):
        ticker_breakdown[t] = {
            "trades": stats["count"],
            "pnl": round(stats["pnl"], 2),
            "wins": stats["wins"],
            "win_rate": round(stats["wins"] / stats["count"] * 100, 1) if stats["count"] > 0 else 0,
        }

    return {
        "trader_id":            trader_id,
        "name":                 TRADERS[trader_id]["name"],
        "provider":             TRADERS[trader_id]["provider"],
        "personality":          TRADERS[trader_id]["personality"],
        "risk_tolerance":       TRADERS[trader_id]["risk_tolerance"],
        "primary_strategy":     TRADERS[trader_id]["primary_strategy"],
        "capital":              round(capital, 2),
        "initial_capital":      INITIAL_CAPITAL,
        "roi_pct":              roi_pct,
        "sharpe":               sharpe,
        "total_trades":         total_trades,
        "wins":                 total_wins,
        "losses":               total_losses,
        "win_rate":             round(total_wins / total_trades * 100, 1) if total_trades > 0 else 0,
        "total_wagered":        round(total_wagered, 2),
        "total_pnl":            round(total_pnl, 2),
        "peak_capital":         round(peak_capital, 2),
        "max_drawdown":         round(max_drawdown, 4),
        "trading_days":         len(day_results),
        "strategy_breakdown":   strategy_breakdown,
        "sector_breakdown":     sector_breakdown,
        "ticker_breakdown":     ticker_breakdown,
        "day_results":          day_results,
        "trades_history":       all_trades[-500:],
        "all_trades":           all_trades,
    }


# ── LEADERBOARD ──────────────────────────────────────────────────────────────

def build_leaderboard(all_results: Dict) -> List[Dict]:
    """Build ranked leaderboard of political traders."""
    board = []
    for trader_id, state in all_results.items():
        board.append({
            "rank":              0,
            "trader_id":         trader_id,
            "name":              state.get("name", trader_id),
            "provider":          state.get("provider", ""),
            "personality":       state.get("personality", ""),
            "primary_strategy":  state.get("primary_strategy", ""),
            "capital":           state.get("capital", INITIAL_CAPITAL),
            "roi_pct":           state.get("roi_pct", 0.0),
            "sharpe":            state.get("sharpe", 0.0),
            "total_trades":      state.get("total_trades", 0),
            "wins":              state.get("wins", 0),
            "losses":            state.get("losses", 0),
            "win_rate":          state.get("win_rate", 0.0),
            "max_drawdown":      state.get("max_drawdown", 0.0),
            "trading_days":      state.get("trading_days", 0),
        })
    board.sort(key=lambda x: x["capital"], reverse=True)
    for i, entry in enumerate(board, 1):
        entry["rank"] = i
    return board


# ── SEASON DOCUMENT GENERATOR ────────────────────────────────────────────────

def generate_season_doc(trader_id: str, state: Dict, board: List[Dict]) -> str:
    """Generate full markdown season document for one political trader."""
    cfg = TRADERS[trader_id]
    all_trades = state.get("all_trades", [])
    day_results = state.get("day_results", [])
    rank_entry = next((e for e in board if e["trader_id"] == trader_id), {})

    lines = []
    lines.append(f"# Political Trading Season 2025-26 -- Agent {cfg['name'].upper()}")
    lines.append(f"")
    lines.append(f"## Executive Summary")
    lines.append(f"- **Provider:** {cfg['provider']}")
    lines.append(f"- **Personality:** {cfg['personality']}")
    lines.append(f"- **Risk Tolerance:** {cfg['risk_tolerance']}")
    lines.append(f"- **Primary Strategy:** {cfg['primary_strategy']}")
    lines.append(f"- **Secondary Strategies:** {', '.join(cfg.get('secondary_strategies', []))}")
    lines.append(f"- **Initial Capital:** ${INITIAL_CAPITAL:,.2f}")
    lines.append(f"- **Final Capital:** ${state.get('capital', 0):,.2f}")
    lines.append(f"- **ROI:** {state.get('roi_pct', 0):+,.4f}%")
    lines.append(f"- **Sharpe Ratio:** {state.get('sharpe', 0):.3f}")
    lines.append(f"- **Record:** {state.get('wins', 0)}W-{state.get('losses', 0)}L")
    lines.append(f"- **Win Rate:** {state.get('win_rate', 0):.1f}%")
    lines.append(f"- **Peak Capital:** ${state.get('peak_capital', 0):,.2f}")
    lines.append(f"- **Max Drawdown:** {state.get('max_drawdown', 0)*100:.1f}%")
    lines.append(f"- **Rank:** #{rank_entry.get('rank', '?')} of {len(board)}")
    lines.append(f"- **Total Wagered:** ${state.get('total_wagered', 0):,.2f}")
    lines.append(f"")

    # Peer comparison
    lines.append(f"## Peer Comparison")
    lines.append(f"| Rank | Agent | Capital | ROI | Sharpe | Win Rate |")
    lines.append(f"|------|-------|---------|-----|--------|----------|")
    for entry in board:
        marker = " **" if entry["trader_id"] == trader_id else ""
        lines.append(
            f"| {entry['rank']} | {entry['name']}{marker} | "
            f"${entry['capital']:,.2f} | {entry['roi_pct']:+,.4f}% | "
            f"{entry.get('sharpe', 0):.3f} | {entry.get('win_rate', 0):.1f}% |"
        )
    lines.append(f"")

    # Strategy performance
    strat_bd = state.get("strategy_breakdown", {})
    if strat_bd:
        lines.append(f"## Strategy Performance")
        lines.append(f"| Strategy | Trades | P&L | Win Rate |")
        lines.append(f"|----------|--------|-----|----------|")
        for s, stats in sorted(strat_bd.items(), key=lambda x: -x[1].get("pnl", 0)):
            lines.append(f"| {s} | {stats['trades']} | ${stats['pnl']:+,.2f} | {stats['win_rate']:.1f}% |")
        lines.append(f"")

    # Sector performance
    sector_bd = state.get("sector_breakdown", {})
    if sector_bd:
        lines.append(f"## Sector Performance")
        lines.append(f"| Sector | P&L |")
        lines.append(f"|--------|-----|")
        for s, pnl in sector_bd.items():
            lines.append(f"| {s} | ${pnl:+,.2f} |")
        lines.append(f"")

    # Top tickers
    ticker_bd = state.get("ticker_breakdown", {})
    if ticker_bd:
        lines.append(f"## Top/Bottom Tickers")
        lines.append(f"| Ticker | Trades | P&L | Win Rate |")
        lines.append(f"|--------|--------|-----|----------|")
        items = list(ticker_bd.items())
        for t, stats in items[:10]:
            lines.append(f"| {t} | {stats['trades']} | ${stats['pnl']:+,.2f} | {stats['win_rate']:.1f}% |")
        if len(items) > 10:
            lines.append(f"| ... | | | |")
            for t, stats in items[-3:]:
                lines.append(f"| {t} | {stats['trades']} | ${stats['pnl']:+,.2f} | {stats['win_rate']:.1f}% |")
        lines.append(f"")

    # Day-by-day
    lines.append(f"## Day-by-Day Results")
    lines.append(f"| Day | Date | Events | Trades | P&L | Capital |")
    lines.append(f"|-----|------|--------|--------|-----|---------|")
    for d in day_results:
        lines.append(
            f"| {d['day']} | {d['date']} | {d.get('events', 0)} | {d['trades']} | "
            f"${d['pnl']:+,.2f} | ${d['capital']:,.2f} |"
        )
    lines.append(f"")

    # Sample trades
    lines.append(f"## Trade Log (sample: first 30 + last 30 of {len(all_trades)} total)")
    lines.append(f"")
    sample = all_trades[:30] + (all_trades[-30:] if len(all_trades) > 60 else [])
    for i, tr in enumerate(sample):
        if i == 30 and len(all_trades) > 60:
            lines.append(f"")
            lines.append(f"*... ({len(all_trades) - 60} trades omitted) ...*")
            lines.append(f"")
        lines.append(f"### {tr.get('date', '?')} | {tr.get('ticker', '?')} | {tr.get('direction', '?')}")
        lines.append(f"- **Strategy:** {tr.get('strategy_used', '?')} | **Signal:** {tr.get('signal_strength', 0):.3f}")
        lines.append(f"- **Size:** ${tr.get('position_size', 0):,.2f} | **Return:** {tr.get('trade_return', 0)*100:+.3f}%")
        lines.append(f"- **{tr.get('outcome', '?')}** -> P&L ${tr.get('pnl', 0):+,.2f}")
        lines.append(f"- **Reasoning:** {tr.get('reasoning', '')}")
        lines.append(f"- **Capital after:** ${tr.get('capital_after', 0):,.2f}")
        lines.append(f"")

    return "\n".join(lines)


def generate_all_season_docs(all_results: Dict, board: List[Dict]) -> None:
    """Generate season doc for all 5 political agents."""
    docs_dir = DATA_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for tid, state in all_results.items():
        doc = generate_season_doc(tid, state, board)
        doc_path = docs_dir / f"political-{tid}-season-2025-26.md"
        doc_path.write_text(doc)
        print(f"  Political season doc: {doc_path} ({len(doc)} chars)")


# ── MAIN ORCHESTRATOR ────────────────────────────────────────────────────────

def run_full_competition() -> Dict:
    """Run full political trading competition for all 5 AI agents."""
    it_data = _load_iteration()
    it_data["iteration"] += 1
    print(f"Political Trading Floor -- iteration {it_data['iteration']}")

    print("Loading political events...")
    events = load_political_events()
    print(f"  Events: {len(events)}")

    print("Loading social signals...")
    latest_signals = load_social_signals()
    social_snapshots = load_all_social_snapshots()
    print(f"  Social tickers: {len(latest_signals)}")
    print(f"  Social snapshots: {len(social_snapshots)}")

    # Unique event dates
    event_dates = sorted(set(e.get("date", "") for e in events if e.get("date")))
    it_data["generation"] = it_data.get("generation", 0) + len(event_dates)
    print(f"  Trading days: {len(event_dates)}")

    TRADERS_DIR.mkdir(parents=True, exist_ok=True)
    POL_DIR.mkdir(parents=True, exist_ok=True)

    all_results: Dict[str, Dict] = {}

    for trader_id in TRADERS:
        cfg = TRADERS[trader_id]
        print(f"\nAgent [{trader_id}] -- {cfg['personality']} / {cfg['primary_strategy']}")
        others = load_other_trader_states(trader_id)

        result = run_backtest_for_agent(
            trader_id, events, social_snapshots, latest_signals, others
        )
        all_results[trader_id] = result

        # Save individual state
        # Remove all_trades (too big) from saved state, keep trades_history
        save_state = {k: v for k, v in result.items() if k != "all_trades"}
        (TRADERS_DIR / f"political-{trader_id}-state.json").write_text(
            json.dumps(save_state, indent=2)
        )

        print(f"  Capital: ${result['capital']:,.2f}  ROI {result['roi_pct']:+.4f}%"
              f"  Sharpe {result['sharpe']:.3f}"
              f"  ({result['wins']}W-{result['losses']}L)"
              f"  Trades: {result['total_trades']}")

    board = build_leaderboard(all_results)

    # Generate season docs
    print("\nGenerating political season documents...")
    generate_all_season_docs(all_results, board)

    _save_iteration(it_data)

    output = {
        "iteration":  it_data["iteration"],
        "generation": it_data["generation"],
        "meta": {
            "version":            "political-trading-floor-v1",
            "generated":          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date":               date.today().isoformat(),
            "traders":            len(TRADERS),
            "strategies":         len(STRATEGIES),
            "eliminated":         len(ELIMINATED_STRATEGIES),
            "events_total":       len(events),
            "trading_days":       len(event_dates),
            "social_tickers":     len(latest_signals),
            "etf_universe":       len(ETF_UNIVERSE),
        },
        "leaderboard": board,
        "traders": {
            tid: {k: v for k, v in s.items()
                  if k not in ("day_results", "trades_history", "all_trades",
                               "ticker_breakdown")}
            for tid, s in all_results.items()
        },
        "strategies": {s: {"family": cfg["family"], "position_pct": cfg["position_pct"]}
                       for s, cfg in STRATEGIES.items()},
        "eliminations": {
            "strategies": ELIMINATED_STRATEGIES,
            "coffins": [
                {"name": k, **v, "type": "political_strategy"}
                for k, v in ELIMINATED_STRATEGIES.items()
            ],
        },
        "etf_universe": {t: {"name": v["name"], "sector": v["sector"], "type": v["type"]}
                         for t, v in ETF_UNIVERSE.items()},
    }

    latest_file = POL_DIR / "political-trading-floor-latest.json"
    dated_file = POL_DIR / f"political-trading-floor-{date.today().isoformat()}.json"
    latest_file.write_text(json.dumps(output, indent=2))
    dated_file.write_text(json.dumps(output, indent=2))
    print(f"\nSaved: {latest_file}")
    print(f"Saved: {dated_file}")
    print(f"Iteration: {it_data['iteration']}  Generation: {it_data['generation']}")

    return output


# ── KARPATHY LOOP ────────────────────────────────────────────────────────────

ELIMINATION_ROI_THRESHOLD = -5.0  # % threshold for auto-elimination
ELIMINATION_MIN_TRADES = 10
KARPATHY_OUTPUT_FILE = POL_DIR / 'political-karpathy-output.json'

def _analyze_strategy_performance(all_results: Dict) -> Dict[str, Dict]:
    """Extract per-strategy performance from all traders."""
    strat_stats: Dict[str, Dict] = defaultdict(lambda: {
        "trades": 0, "wins": 0, "pnl": 0.0, "traders_using": set(),
    })
    for tid, state in all_results.items():
        trades = state.get("all_trades", state.get("trades_history", []))
        for trade in trades:
            strat = trade.get("strategy_used", "unknown")
            strat_stats[strat]["trades"] += 1
            strat_stats[strat]["pnl"] += trade.get("pnl", 0.0)
            strat_stats[strat]["traders_using"].add(tid)
            if trade.get("pnl", 0.0) > 0:
                strat_stats[strat]["wins"] += 1

    for strat, stats in strat_stats.items():
        stats["traders_using"] = list(stats["traders_using"])
        stats["win_rate"] = round(stats["wins"] / stats["trades"] * 100, 1) if stats["trades"] > 0 else 0.0
        initial = INITIAL_CAPITAL * len(stats["traders_using"]) if stats["traders_using"] else INITIAL_CAPITAL
        stats["roi_pct"] = round(stats["pnl"] / initial * 100, 4)
    return dict(strat_stats)


def _analyze_sector_performance(all_results: Dict) -> Dict[str, Dict]:
    """Extract per-sector performance."""
    sector_stats: Dict[str, Dict] = defaultdict(lambda: {"trades": 0, "pnl": 0.0, "wins": 0})
    for tid, state in all_results.items():
        trades = state.get("all_trades", state.get("trades_history", []))
        for trade in trades:
            sector = trade.get("sector", "unknown")
            sector_stats[sector]["trades"] += 1
            sector_stats[sector]["pnl"] += trade.get("pnl", 0.0)
            if trade.get("pnl", 0.0) > 0:
                sector_stats[sector]["wins"] += 1
    for sector, stats in sector_stats.items():
        stats["win_rate"] = round(stats["wins"] / stats["trades"] * 100, 1) if stats["trades"] > 0 else 0.0
    return dict(sector_stats)


def _analyze_ticker_performance(all_results: Dict) -> Dict[str, Dict]:
    """Extract per-ticker performance."""
    ticker_stats: Dict[str, Dict] = defaultdict(lambda: {"trades": 0, "pnl": 0.0, "wins": 0})
    for tid, state in all_results.items():
        trades = state.get("all_trades", state.get("trades_history", []))
        for trade in trades:
            ticker = trade.get("ticker", "unknown")
            ticker_stats[ticker]["trades"] += 1
            ticker_stats[ticker]["pnl"] += trade.get("pnl", 0.0)
            if trade.get("pnl", 0.0) > 0:
                ticker_stats[ticker]["wins"] += 1
    for ticker, stats in ticker_stats.items():
        stats["win_rate"] = round(stats["wins"] / stats["trades"] * 100, 1) if stats["trades"] > 0 else 0.0
    return dict(ticker_stats)


def _auto_eliminate_strategies(strat_perf: Dict[str, Dict]) -> List[Dict]:
    """Auto-eliminate strategies with ROI below threshold."""
    new_coffins = []
    for strat, stats in strat_perf.items():
        if strat in ELIMINATED_STRATEGIES:
            continue
        if strat not in STRATEGIES:
            continue
        if stats["trades"] < ELIMINATION_MIN_TRADES:
            continue
        if stats["roi_pct"] < ELIMINATION_ROI_THRESHOLD:
            coffin = {
                "strategy": strat,
                "eliminated_at": date.today().isoformat(),
                "reason": f"Auto-eliminated: {stats['roi_pct']:.2f}% ROI ({stats['trades']} trades)",
                "final_roi": round(stats["roi_pct"] / 100, 4),
                "trades": stats["trades"],
            }
            new_coffins.append(coffin)
            ELIMINATED_STRATEGIES[strat] = coffin
            print(f"  [COFFIN] Strategy '{strat}' eliminated: {stats['roi_pct']:.2f}% ROI")
    return new_coffins


def _mutate_agent_preferences(all_results: Dict, board: List[Dict]) -> Dict:
    """Karpathy-style mutation: losing agents adopt winning agents' strategies."""
    if len(board) < 2:
        return {}

    winner = board[0]
    loser = board[-1]
    winner_id = winner["trader_id"]
    loser_id = loser["trader_id"]
    mutations = {}

    # Loser adopts winner's primary strategy
    winner_strat = TRADERS[winner_id]["primary_strategy"]
    loser_strat = TRADERS[loser_id]["primary_strategy"]
    if winner_strat != loser_strat and winner_strat not in ELIMINATED_STRATEGIES:
        old_primary = loser_strat
        old_secondary = list(TRADERS[loser_id]["secondary_strategies"])
        TRADERS[loser_id]["secondary_strategies"] = [old_primary] + old_secondary[:1]
        TRADERS[loser_id]["primary_strategy"] = winner_strat
        mutations[loser_id] = {
            "type": "adopt_winner_strategy",
            "from_trader": winner_id,
            "old_primary": old_primary,
            "new_primary": winner_strat,
            "reason": f"{loser_id} (rank {loser['rank']}, ROI {loser['roi_pct']:+.4f}%) "
                      f"adopts '{winner_strat}' from {winner_id} (rank 1, ROI {winner['roi_pct']:+.4f}%)",
        }
        print(f"  [MUTATE] {loser_id} adopts '{winner_strat}' from {winner_id}")

    # Stagnant middle agents: adopt winner's top ticker
    for entry in board[1:-1]:
        tid = entry["trader_id"]
        if abs(entry["roi_pct"]) < 0.5:
            winner_tickers = TRADERS[winner_id]["ticker_focus"]
            current_tickers = TRADERS[tid]["ticker_focus"]
            if winner_tickers and winner_tickers[0] not in current_tickers:
                TRADERS[tid]["ticker_focus"] = [winner_tickers[0]] + current_tickers[:5]
                mutations[tid] = {
                    "type": "adopt_winner_ticker",
                    "from_trader": winner_id,
                    "adopted_ticker": winner_tickers[0],
                    "reason": f"{tid} stagnant (ROI {entry['roi_pct']:+.4f}%) -- adds ticker '{winner_tickers[0]}' from {winner_id}",
                }
                print(f"  [MUTATE] {tid} adopts ticker '{winner_tickers[0]}' from {winner_id}")

    if mutations:
        _save_evolved_configs()
        print(f"  [PERSIST] Saved {len(mutations)} mutations to {TRADER_CONFIG_FILE}")

    return mutations


def run_karpathy_loop() -> Dict:
    """
    Karpathy-style loop:
    1. Run full backtest
    2. Analyze strategy/sector/ticker performance
    3. Auto-eliminate losing strategies
    4. Mutate agent preferences
    5. Write karpathy output for Guardian
    """
    print("=" * 60)
    print("POLITICAL TRADING FLOOR -- KARPATHY LOOP")
    print("=" * 60)

    result = run_full_competition()

    # Reconstruct all_results with all_trades for analysis
    # (run_full_competition stores limited trades in state files)
    # Re-run is expensive, so we'll analyze from saved state
    all_results = {}
    for tid in TRADERS:
        sf = TRADERS_DIR / f"political-{tid}-state.json"
        if sf.exists():
            try:
                all_results[tid] = json.loads(sf.read_text())
            except Exception:
                pass

    print("\n--- KARPATHY ANALYSIS ---")
    strat_perf = _analyze_strategy_performance(all_results)
    sector_perf = _analyze_sector_performance(all_results)
    ticker_perf = _analyze_ticker_performance(all_results)

    strat_ranked = sorted(
        [(s, p) for s, p in strat_perf.items() if p["trades"] >= 3],
        key=lambda x: x[1]["pnl"], reverse=True,
    )
    print(f"\nStrategy rankings:")
    for s, p in strat_ranked:
        print(f"  {s:20s}: P&L ${p['pnl']:+,.2f}  WR {p['win_rate']:.1f}%  ({p['trades']} trades)")

    sector_ranked = sorted(sector_perf.items(), key=lambda x: -x[1]["pnl"])
    print(f"\nSector rankings:")
    for s, p in sector_ranked:
        print(f"  {s:15s}: P&L ${p['pnl']:+,.2f}  WR {p['win_rate']:.1f}%  ({p['trades']} trades)")

    ticker_ranked = sorted(
        [(t, p) for t, p in ticker_perf.items() if p["trades"] >= 2],
        key=lambda x: x[1]["pnl"], reverse=True,
    )
    print(f"\nTop tickers:")
    for t, p in ticker_ranked[:8]:
        print(f"  {t:6s}: P&L ${p['pnl']:+,.2f}  WR {p['win_rate']:.1f}%  ({p['trades']} trades)")

    # Auto-eliminate
    print("\n--- AUTO-ELIMINATION ---")
    new_coffins = _auto_eliminate_strategies(strat_perf)
    if not new_coffins:
        print("  No new eliminations this iteration.")

    # Mutate
    print("\n--- AGENT MUTATIONS ---")
    board = result.get("leaderboard", [])
    mutations = _mutate_agent_preferences(all_results, board)
    if not mutations:
        print("  No mutations this iteration.")

    # Best findings
    best_strategy = strat_ranked[0] if strat_ranked else ("none", {"pnl": 0})
    best_sector = sector_ranked[0] if sector_ranked else ("none", {"pnl": 0})
    best_ticker = ticker_ranked[0] if ticker_ranked else ("none", {"pnl": 0})

    # Best capital
    best_capital = max((e.get("capital", 0) for e in board), default=INITIAL_CAPITAL)
    best_trader = max(board, key=lambda e: e.get("capital", 0))["trader_id"] if board else None

    karpathy_output = {
        "department": "political_trading_floor",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": result.get("iteration", 0),
        "generation": result.get("generation", 0),
        "status": "completed",
        "best_strategy": {
            "name": best_strategy[0],
            "pnl": round(best_strategy[1].get("pnl", 0), 2),
            "trades": best_strategy[1].get("trades", 0),
        },
        "best_sector": {
            "name": best_sector[0],
            "pnl": round(best_sector[1].get("pnl", 0), 2),
        },
        "best_ticker": {
            "name": best_ticker[0],
            "pnl": round(best_ticker[1].get("pnl", 0), 2),
        },
        "strategy_rankings": [
            {"strategy": s, **{k: (round(v, 2) if isinstance(v, float) else v)
                               for k, v in p.items()}}
            for s, p in strat_ranked
        ],
        "sector_rankings": [
            {"sector": s, **{k: (round(v, 2) if isinstance(v, float) else v)
                             for k, v in p.items()}}
            for s, p in sector_ranked
        ],
        "ticker_rankings": [
            {"ticker": t, **{k: (round(v, 2) if isinstance(v, float) else v)
                             for k, v in p.items()}}
            for t, p in ticker_ranked[:15]
        ],
        "new_eliminations": new_coffins,
        "mutations": mutations,
        "leaderboard": board,
        "optimization": {
            "current_best_capital": round(best_capital, 2),
            "best_trader": best_trader,
            "target": 1_000_000,
            "distance_pct": round((1.0 - best_capital / 1_000_000) * 100, 2),
        },
        "recommendations": [],
    }

    # Recommendations
    recs = karpathy_output["recommendations"]
    if best_strategy[1].get("pnl", 0) > 100:
        recs.append({
            "target_dept": "D7_POLITICAL",
            "type": "promote_strategy",
            "strategy": best_strategy[0],
            "reason": f"Top political strategy '{best_strategy[0]}' with P&L ${best_strategy[1]['pnl']:+,.2f}",
        })
    if new_coffins:
        recs.append({
            "target_dept": "D4_BETTING",
            "type": "strategy_eliminated",
            "strategies": [c["strategy"] for c in new_coffins],
            "reason": f"{len(new_coffins)} political strategies auto-eliminated",
        })

    KARPATHY_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    KARPATHY_OUTPUT_FILE.write_text(json.dumps(karpathy_output, indent=2))
    print(f"\nKarpathy output: {KARPATHY_OUTPUT_FILE}")

    # Also write to department directory
    dept_output = ROOT / 'data' / 'departments' / 'political_trading_floor'
    dept_output.mkdir(parents=True, exist_ok=True)
    (dept_output / 'karpathy-output.json').write_text(json.dumps(karpathy_output, indent=2))
    print(f"Guardian feed:   {dept_output / 'karpathy-output.json'}")

    print(f"\nKarpathy loop complete -- iteration {result.get('iteration', '?')}")
    print(f"Best strategy: {best_strategy[0]} (P&L ${best_strategy[1].get('pnl', 0):+,.2f})")
    print(f"Best sector:   {best_sector[0]} (P&L ${best_sector[1].get('pnl', 0):+,.2f})")
    print(f"Best ticker:   {best_ticker[0]} (P&L ${best_ticker[1].get('pnl', 0):+,.2f})")
    print(f"Best trader:   {best_trader} (${best_capital:,.2f})")

    return karpathy_output


# ── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        result = run_full_competition()
        print("\n--- LEADERBOARD ---")
        print(json.dumps(result["leaderboard"], indent=2))

    elif cmd == "karpathy":
        karpathy_result = run_karpathy_loop()
        print(json.dumps({
            "status": "completed",
            "department": "political_trading_floor",
            "iteration": karpathy_result.get("iteration"),
            "best_strategy": karpathy_result.get("best_strategy", {}).get("name"),
            "best_sector": karpathy_result.get("best_sector", {}).get("name"),
            "best_ticker": karpathy_result.get("best_ticker", {}).get("name"),
            "eliminations": len(karpathy_result.get("new_eliminations", [])),
            "mutations": len(karpathy_result.get("mutations", {})),
        }))

    elif cmd == "leaderboard":
        states = {}
        for tid in TRADERS:
            sf = TRADERS_DIR / f"political-{tid}-state.json"
            if sf.exists():
                try:
                    states[tid] = json.loads(sf.read_text())
                except Exception:
                    pass
        if not states:
            print("No political trader states found. Run with 'run' first.")
        else:
            print(json.dumps(build_leaderboard(states), indent=2))

    elif cmd == "status":
        for tid in TRADERS:
            sf = TRADERS_DIR / f"political-{tid}-state.json"
            if sf.exists():
                s = json.loads(sf.read_text())
                print(f"{tid:12s}: ${s.get('capital', INITIAL_CAPITAL):,.2f} "
                      f"({s.get('roi_pct', 0):+.4f}%) "
                      f"Sharpe {s.get('sharpe', 0):.3f} "
                      f"WR {s.get('win_rate', 0):.1f}% "
                      f"[{s.get('personality', '?')} / {s.get('primary_strategy', '?')}]")
            else:
                print(f"{tid:12s}: no state yet")

    else:
        print(f"Usage: {sys.argv[0]} [run|karpathy|leaderboard|status]")
        sys.exit(1)
