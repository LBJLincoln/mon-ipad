"""Nomos42 Intraday Trading Floor (ITF) — 6 LLM agents, 15-min cadence.

Mirrors POL TF / PQTF structure. Each tick:
  1. quote_bus.refresh() pulls fresh ETF quotes (yfinance free, 15-min delayed;
     auto-flips to Alpaca when ALPACA_PAPER_KEY present).
  2. context_bus.build_intraday_context() fuses NBA edges + POL signals +
     PQTF state + the fresh quotes into ONE dict.
  3. Each of 6 personas gets a real LLM call (Cerebras / Google / Mistral /
     OpenRouter, primary + fallback) with:
        COLLECTIVE_MISSION preamble  (shared $1M season goal — same as NBA/POL/PQTF)
      + AXELROD_CANON                (cooperation canon — same)
      + persona style                (scalper, momentum, mean-rev, breakout, pairs, vol)
      + intraday_context             (merged dict)
   and is asked to emit JSON: {ticker, side, stake_usd, stop_pct, tp_pct, thesis} or PASS.
  4. executor.submit() either writes the order to dry-run jsonl OR places it on
     Alpaca paper (bracket order). Max 3 open positions per agent.
  5. EOD flatten at 19:50 UTC closes any open positions.

Run modes:
  - `python3 app.py --once`   — one tick, no FastAPI, prints all 6 decisions. Dev smoke test.
  - `python3 app.py`          — FastAPI + tick loop every 15 min, 13:00-20:00 UTC weekdays.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Repo path on import so `scripts.arena.shared` resolves.
_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.arena.shared.quote_bus import refresh as quote_refresh, latest as quote_latest  # noqa: E402
from scripts.arena.shared.context_bus import build_intraday_context  # noqa: E402

# 2026-04-22 EVENT MARKETS — Kalshi + Polymarket paper-mode executor. Both venues
# READ live (free public APIs, no auth). Fills are SIMULATED at midpoint +
# slippage. Live execution is gated behind KALSHI_LIVE=1 / POLY_LIVE=1 (neither
# on by default — Poly requires USDC+gas on Polygon, Kalshi needs signed creds).
# Module lives beside app.py; on HF, /home/user/app is already sys.path[0], and
# locally the script-dir is sys.path[0] too.
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))
import event_executor as ev  # noqa: E402


# ── 2026-04-22 POWER-DEPLOY WINDOW — force >50% fleet bankroll into liquid
# positions during the first 2h of US market open (14:30-16:30 UTC weekdays).
# 6 liquid-specialist agents × 20% sub-bankroll stake floor × 90s tick cadence
# = fleet cumulative deployed capital climbs past $50k (50% of $100k seed)
# within the window, regardless of how cautious individual LLMs decide to be.
#
# Liberty: the liquid UNIVERSE is NOT hardcoded — any ticker the agent picks
# qualifies if its runtime dollar-volume clears POWER_LIQUIDITY_FLOOR_USD.
# Agents have full carte blanche over 10k+ equities + 30+ crypto + options;
# the floor just ensures the stake sits in something actually exit-able.
POWER_WINDOW_START = (14, 30)  # UTC
POWER_WINDOW_END = (16, 30)
POWER_AGENTS = {
    "momentum-1", "breakout-1", "leveraged-momentum-1",
    "news-catalyst-1", "crypto-whale-1", "scalper-1",
}
POWER_STAKE_FLOOR_PCT = float(os.environ.get("ITF_STAKE_FLOOR_PCT", "0.20"))  # 20% default, bumpable via env for max-aggressive runs
POWER_LIQUIDITY_FLOOR_USD = 50_000_000  # $50M daily dollar volume = liquid enough
                                          # to exit any single-agent stake in seconds


def _current_power_mode(
    now: Optional[datetime] = None,
    quotes: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[str]:
    """Return which power mode is active:
        'equity_power' — 14:30-16:30 UTC weekdays. Applies to POWER_AGENTS only,
                         any ticker whose runtime $-vol ≥ $50M qualifies.
        'crypto_247'   — equity markets CLOSED + crypto tape moving. Applies to
                         ALL 17 agents, crypto pairs only. Keeps compounding
                         24/7 including weekends.
        None           — no forced floor.
    """
    now = now or datetime.now(timezone.utc)
    # Equity power-window (weekday first 2h of US open)
    if now.weekday() < 5:
        cur_min = now.hour * 60 + now.minute
        start_min = POWER_WINDOW_START[0] * 60 + POWER_WINDOW_START[1]
        end_min = POWER_WINDOW_END[0] * 60 + POWER_WINDOW_END[1]
        if start_min <= cur_min <= end_min:
            return "equity_power"
    # Off-hours crypto window (equity closed, crypto tape active)
    equity_open = now.weekday() < 5 and 8 <= now.hour < 24
    if not equity_open and quotes and _off_hours_crypto_signal(quotes):
        return "crypto_247"
    return None


def _is_power_liquid(ticker: str, quote: Optional[Dict[str, Any]]) -> bool:
    """Runtime liquidity test: dollar-volume (volume × last) ≥ $50M.
    Crypto pairs always qualify (top-30 CEX pairs are deep 24/7)."""
    if not ticker:
        return False
    if "/" in ticker:  # crypto pair — always deep enough on Alpaca
        return True
    if not quote:
        return False
    try:
        last = float(quote.get("last") or 0)
        vol = float(quote.get("volume") or 0)
    except (TypeError, ValueError):
        return False
    return last > 0 and vol > 0 and (last * vol) >= POWER_LIQUIDITY_FLOOR_USD


def _agent_in_power_mode(persona_tid: str, mode: Optional[str]) -> bool:
    """Which personas get the stake floor under which mode."""
    if mode == "equity_power":
        return persona_tid in POWER_AGENTS
    if mode == "crypto_247":
        return True  # ALL 17 agents compound 24/7 in crypto
    return False


# 2026-04-21 v2.6 — UNRESTRICTED UNIVERSE: on-demand fetch for any Alpaca-supported
# ticker the agent emits that isn't in the ~110-deep quote bus. Returns a quote
# dict in the same shape quote_bus produces, or None on failure.
_ONDEMAND_CACHE: Dict[str, Dict[str, Any]] = {}
_ONDEMAND_TS: Dict[str, float] = {}

def _ondemand_quote(ticker: str) -> Optional[Dict[str, Any]]:
    import time as _tm
    now_ts = _tm.time()
    # 30s cache
    if ticker in _ONDEMAND_CACHE and now_ts - _ONDEMAND_TS.get(ticker, 0) < 30:
        return _ONDEMAND_CACHE[ticker]
    key = os.environ.get("ALPACA_PAPER_KEY", "")
    secret = os.environ.get("ALPACA_PAPER_SECRET", "")
    if not (key and secret):
        return None
    import requests as _rq
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    try:
        if "/" in ticker:
            # Crypto latest bar
            r = _rq.get(
                "https://data.alpaca.markets/v1beta3/crypto/us/latest/bars",
                headers=headers,
                params={"symbols": ticker},
                timeout=5,
            )
            if r.ok:
                bars = (r.json() or {}).get("bars") or {}
                bar = bars.get(ticker) or {}
                if bar.get("c"):
                    out = {
                        "last": float(bar["c"]),
                        "change_pct": 0.0,  # unknown without open
                        "volume": float(bar.get("v") or 0),
                        "5m_high": float(bar.get("h") or bar["c"]),
                        "5m_low": float(bar.get("l") or bar["c"]),
                    }
                    _ONDEMAND_CACHE[ticker] = out
                    _ONDEMAND_TS[ticker] = now_ts
                    return out
        else:
            # Equity latest trade
            r = _rq.get(
                f"https://data.alpaca.markets/v2/stocks/{ticker}/trades/latest",
                headers=headers,
                timeout=5,
            )
            if r.ok:
                trade = (r.json() or {}).get("trade") or {}
                if trade.get("p"):
                    out = {
                        "last": float(trade["p"]),
                        "change_pct": 0.0,
                        "volume": float(trade.get("s") or 0),
                        "5m_high": float(trade["p"]),
                        "5m_low": float(trade["p"]),
                    }
                    _ONDEMAND_CACHE[ticker] = out
                    _ONDEMAND_TS[ticker] = now_ts
                    return out
    except Exception:
        pass
    return None

# Local (HF Space style) imports
sys.path.insert(0, str(_HERE.parent))
from personas import PERSONAS, get as get_persona  # type: ignore  # noqa: E402
import executor  # type: ignore  # noqa: E402
from gateway_client import gateway_call  # type: ignore  # noqa: E402

# ───────────────────────── Prompts ─────────────────────────

# 2026-04-26 — STRIPPED to user spec: personality (in personas.py) + bankroll rules + $1M goal.
# No "passing is cowardice", no "MUST trade", no AGGRESSIVE_MANDATE, no PQTF playbook coercion.
# Agents are autonomous; Kelly cap + bankroll floor are enforced server-side.
COLLECTIVE_MISSION = """
You are ONE of 17 LLM agents on the Nomos42 Intraday Trading Floor.
GOAL: contribute to fleet $1M target. You choose freely; bankroll rules
(Kelly cap + per-agent sub-bankroll floor) are enforced server-side.
""".strip()

AXELROD_CANON = """
JSON OUT: respond ONLY with the JSON object specified by the schema.
No markdown fences, no prose.
""".strip()


# Prompt-mutator overrides (2026-04-20) — scripts/arena/prompt_mutator.py writes
# data/prompts/overrides.json from priority-1 post-mortem proposals. Injected into
# the per-persona prompt as PROMPT MUTATOR OVERRIDE block just after AXELROD_CANON.
def _load_prompt_override(fleet: str = "itf") -> str:
    import os as _os, json as _json
    candidates = [
        "/app/data/prompts/overrides.json",
        "/home/user/app/data/prompts/overrides.json",
        _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "data", "prompts", "overrides.json"),
    ]
    for p in candidates:
        try:
            if not _os.path.exists(p):
                continue
            with open(p) as fh:
                ov = _json.load(fh)
            section = (ov.get(fleet) or {})
            rule = section.get("current_text") or ""
            narrative = section.get("market_narrative") or ""
            mvc = section.get("manual_videos_count") or 0
            v = section.get("current_version") or "?"
            out = ""
            if rule:
                out += f"\n=== PROMPT MUTATOR OVERRIDE ({v}) ===\n{rule}\n=== END OVERRIDE ===\n"
            if narrative:
                out += f"\n=== YOUTUBE MARKET NARRATIVE ({mvc} tracked videos, 22 channels) ===\n{narrative}\n=== END NARRATIVE ===\n"
            if out:
                return out
        except Exception:
            continue
    return ""

DECISION_SCHEMA = """
Five action types (all equally first-class — pick whichever fits your edge):

(1) Pass:
  { "action": "pass", "reason": "..." }

(2) Close an existing open position:
  { "action": "close", "ticker": "NVDA", "reason": "..." }

(3) Equity / crypto trade:
  { "action": "trade",
    "ticker": <any equity, leveraged ETF, inverse ETF, vol product, commodity ETF, intl ETF, single-name, or crypto pair like BTC/USD>,
    "side": "long"|"short",
    "stake_usd": <number — Kelly cap enforced server-side>,
    "stop_pct": 0.002-0.03,
    "take_profit_pct": 0.005-0.08,
    "thesis": "1-2 sentence reason"
  }

(4) Options derivative:
  { "action": "option_trade",
    "underlying": <any liquid US-options underlying>,
    "option_type": "call"|"put",
    "strategy": "long"|"vertical_debit"|"vertical_credit"|"iron_condor"|"straddle",
    "dte": 0|1|2|5, "strike_offset_pct": -0.03 to 0.03, "wing_width_pct": 0.005-0.03,
    "stake_usd": <number>, "max_loss_pct": 0.01-0.05,
    "thesis": "1-2 sentence reason"
  }

(5) Binary event-market bet on Kalshi or Polymarket — paper-mode, 24/7, NOT gated by equity hours.
    Market_ids are listed in the EVENT MARKETS — PAPER-TRADEABLE block above with live YES/NO prices.
    YES resolves to $1.00 and NO to $0.00 at close. Edge = your model_p − market YES price.
  { "action": "event_trade",
    "venue": "kalshi"|"polymarket",
    "market_id": <copy market_id verbatim from the EVENT MARKETS block>,
    "side": "yes"|"no",
    "stake_usd": <number — server caps at min($1500, 5% of your bankroll)>,
    "thesis": "1-2 sentence reason citing the price mispricing"
  }

Universe: Alpaca paper supports 10,000+ US equities, 30+ crypto pairs, listed US options.
Kalshi + Polymarket cover politics, Fed rates, crypto prices, sports, SCOTUS — 24/7.
The INTRADAY TAPE shows liquid equities; the EVENT MARKETS block shows binary markets.
Both are FIRST-CLASS — pick whichever venue your edge fits. No futures/forex (use ETFs).
Crypto + event markets trade 24/7; equities + options only during RTH + extended hours.

Return JSON ONLY. No markdown fences, no prose.
""".strip()


# 2026-04-26 — STRIPPED: off-hours coercion removed. Agents pivot freely.
_OFF_HOURS_STYLE_BY_TID: Dict[str, str] = {} if True else {
    "scalper-1": (
        "OFF-HOURS CRYPTO MODE: You are SCALPER, crypto edition. Equity markets "
        "closed. You MUST trade BTC/USD, ETH/USD, SOL/USD, AVAX/USD, LINK/USD, "
        "or DOGE/USD IF any has |change_pct| > 0.3%. Sub-hour micro-scalp. "
        "Stop <= 0.4% from entry (crypto vol is higher), TP <= 1.0%. Pass ONLY "
        "if ALL crypto |change_pct| < 0.2%."
    ),
    "momentum-1": (
        "OFF-HOURS CRYPTO MODE: You are MOMENTUM, crypto edition. Equity markets "
        "closed. Find the strongest trending crypto (largest |change_pct|) and "
        "go with the trend. Enter long if chg > 0.5%, short if chg < -0.5%. "
        "Stop 0.8%, TP 1.5-2.0%. Pass only if no crypto has |chg| > 0.4%."
    ),
    "mean-rev-1": (
        "OFF-HOURS CRYPTO MODE: You are MEAN-REVERSION, crypto edition. Fade "
        "extreme crypto moves. Enter if BTC OR ETH OR SOL has |change_pct| > 1.5% "
        "(fade the move). Stop 1.0%, TP 1.0%. Pass if tape is quiet (< 1.0% max move)."
    ),
    "breakout-1": (
        "OFF-HOURS CRYPTO MODE: You are BREAKOUT, crypto edition. Find the crypto "
        "with BIGGEST recent |change_pct| and enter with the breakout direction. "
        "Stop = 0.8% against entry. Target 2R. Works 24/7 on crypto."
    ),
    "pairs-1": (
        "OFF-HOURS CRYPTO MODE: You are PAIRS, crypto edition. Trade the spread "
        "between crypto pairs. Example: if BTC +1% and ETH flat, long ETH short BTC "
        "(mean-reversion spread). Candidates: (BTC-ETH), (ETH-SOL), (SOL-AVAX). "
        "Enter only when intraday chg spread > 0.8%. One pair max."
    ),
    "vol-1": (
        "OFF-HOURS CRYPTO MODE: You are VOL-REGIME, crypto edition. Crypto has no "
        "VIX but realized vol is high 24/7. If BTC |chg| > 1.0% → defensive (long "
        "BTC as the 'safe' crypto carry, skip alts). If BTC flat and alts |chg| > "
        "1.5% → fade alts (they always revert to BTC correlation). Stop 1.0%, TP 1.5%."
    ),
    "options-1": (
        "OFF-HOURS MODE: Options markets are CLOSED. You may ONLY emit action='pass' "
        "during off-hours (no options markets trade 24/7 for us). Document what "
        "you'd do when markets reopen."
    ),
    # 2026-04-20 AGGRESSIVE-MODE expansion — off-hours crypto overrides for +7 personas.
    "arbitrage-1": (
        "OFF-HOURS CRYPTO MODE: Arb, crypto edition. Look for cross-exchange-proxy "
        "dislocations: e.g. BTC/USD vs IBIT gap, ETH/USD relative to SOL. If chg-spread "
        "> 0.8% between BTC and largest alt, long the laggard. Stop 0.5%, TP 1.0%. "
        "Pass only if all 10 crypto pairs within 0.2% of each other."
    ),
    "news-catalyst-1": (
        "OFF-HOURS CRYPTO MODE: News-catalyst, crypto edition. Crypto reacts 24/7 to "
        "headlines. Whichever crypto has |chg| > 1% is the tape's story — follow "
        "it in the same direction. Stop 0.8%, TP 2.0%. Pass ONLY if no crypto > 0.5%."
    ),
    "crypto-whale-1": (
        "OFF-HOURS (or anytime) 24/7 MANDATE: You are CRYPTO specialist. Equity closed "
        "changes nothing. You MUST place at least one crypto trade this tick unless "
        "every crypto pair is < 0.3% from flat (then emit pass with reason 'crypto_dead_tape')."
    ),
    "earnings-gap-1": (
        "OFF-HOURS CRYPTO MODE: Earnings-gap off-hours = crypto whale orders create "
        "mini-gaps. Find crypto with biggest 1hr |chg| and trade follow-through. "
        "Stop 1.0%, TP 2.5%. Pass if all crypto < 0.5%."
    ),
    "iv-crush-1": (
        "OFF-HOURS MODE: Options markets closed. You may ONLY pass. Document what "
        "IV-sell you'd do tomorrow at open."
    ),
    "macro-rotate-1": (
        "OFF-HOURS CRYPTO MODE: Macro-rotate, crypto edition. Crypto is the 24/7 "
        "macro barometer. If BTC down + USDT premium widens → risk-off, long USDC "
        "proxy / short BTC. If BTC + SOL + LINK all up → risk-on, long SOL (highest "
        "beta). Stop 1.0%, TP 2.0%. Pass if crypto tape flat (|chg| < 0.3% for all)."
    ),
    "leveraged-momentum-1": (
        "OFF-HOURS CRYPTO MODE: Leveraged-momentum, crypto edition. Crypto itself is "
        "intrinsically volatile (implicit leverage). Find the biggest |chg| crypto "
        "and ride it for 30-90 min. Stop 1.2%, TP 3%. Pass if max crypto |chg| < 0.5%."
    ),
    # 2026-04-21 v2.7 — last 3 personas wired so ALL 17 stay active 24/7.
    "gap-fade-1": (
        "OFF-HOURS CRYPTO MODE: Gap-fade, crypto edition. Crypto overnight gaps happen "
        "nonstop. If any crypto |chg| > 1.2% in last hr, FADE it (short the move). "
        "Stop 1.0%, TP 1.5%. Pass ONLY if all crypto |chg| < 0.5%."
    ),
    "carry-1": (
        "OFF-HOURS CRYPTO MODE: Carry, crypto edition. Stablecoin carry + BTC/ETH "
        "funding-proxy via spot premia. If BTC in up-trend (chg > 0.3%), long BTC as "
        "positive-carry risk asset. If BTC flat + alts up, long highest-momentum alt. "
        "Stop 1.0%, TP 2.0%. Pass if BTC chg < 0.2% AND alts < 0.4%."
    ),
    "breakdown-1": (
        "OFF-HOURS CRYPTO MODE: Breakdown, crypto edition. Short weakness. If any "
        "crypto pair has chg < -1.0% with momentum (last 1hr trending down), SHORT "
        "it. Stop 1.0%, TP 2.0%. Pass if no crypto has chg < -0.3%."
    ),
}


# 2026-04-26 — STRIPPED: winner-aware tier coercion removed.
_WINNER_AWARE_ADDENDA: Dict[str, str] = {} if True else {
    "scalper-1": (
        "WINNER-AWARE MANDATE (scalper-1, router=mistral:medium — PQTF $155K winner): "
        "You are the ITF SCALPER. Micro-timeframes (<1h), tight stops (0.3-0.4%), "
        "small-but-frequent edges. Your provider is a proven compounder — execute "
        "with confidence when you see 0.3%+ dislocation. Prefer SPY/QQQ/TQQQ/SQQQ "
        "and top-10 crypto. Churn = death; 2-3 real setups beat 8 speculative."
    ),
    "momentum-1": (
        "WINNER-AWARE MANDATE (momentum-1, router=mistral:large — PQTF $244K #1 winner): "
        "You are the ITF MOMENTUM lead. Ride trending names w/ clear higher-highs "
        "structure. Your brain is the PQTF champion — SCALE with conviction: when "
        "a name has 3x avg volume + breaking VWAP, size UP. Stops at swing-low, "
        "targets at 2-3R. No mean-reversion overlays; stay on the train."
    ),
    "mean-rev-1": (
        "WINNER-AWARE MANDATE (mean-rev-1, router=mistral:large — PQTF #1 provider): "
        "You are the ITF MEAN-REVERSION specialist. Fade extremes: 1.5sigma+ moves "
        "w/o catalyst, VWAP-anchored reversions, low-vol consolidation breaks that "
        "fail. Your provider is a proven edge-extractor; trust its fade signal. If "
        "no extreme exists this tick, PASS — forcing a fade into trend is how you die."
    ),
    "breakout-1": (
        "WINNER-AWARE MANDATE (breakout-1, router=github:gpt-4.1-mini — post-reroute stable): "
        "You are the ITF BREAKOUT specialist. Clean horizontal/channel breaks w/ "
        "volume confirmation. Stop = break level − ATR, target 2R+. Your currently-"
        "IDLE state (0 reserved) says the tape hasn't given you a clean setup — "
        "don't manufacture one. Patience is the breakout-trader's edge."
    ),
    "pairs-1": (
        "WINNER-AWARE MANDATE (pairs-1, router=mistral:medium — PQTF $155K #2 winner): "
        "You are the ITF PAIRS/RELATIVE-VALUE specialist. Trade spreads — XLK vs "
        "SPY, SMH vs QQQ, BTC vs ETH, KO vs PEP. Z-score >=2 on 20-bar returns "
        "is the minimum. Your provider converts small edges into compounding wins; "
        "trust the stat-arb logic. Always hedge both legs; one-sided = not pairs."
    ),
    "vol-1": (
        "WINNER-AWARE MANDATE (vol-1, router=mistral:large — top derivatives brain): "
        "You are the ITF VOL-REGIME allocator. VIX term-structure + SPY GEX + unusual "
        "options flow drive your positioning. Contango+low GEX = risk-on sizing, "
        "backwardation+negative GEX = defensive. Your provider owns the PQTF options "
        "book — it reads vol surfaces correctly. Don't fight signed gamma."
    ),
    "options-1": (
        "WINNER-AWARE MANDATE (options-1, router=mistral:large — PQTF #1 derivatives): "
        "You are the ITF DERIVATIVES lead. Multi-leg ONLY — verticals, condors, "
        "butterflies, straddles. Single-leg naked = not your role (scalper-1's). "
        "You currently hold $1,953 reserved — active deployment, keep converting. "
        "IV-rank >=40 → short premium (condor/credit spread); IV-rank <20 → long "
        "premium (debit spread/straddle). Delta-neutral bias where possible."
    ),
    "arbitrage-1": (
        "WINNER-AWARE MANDATE (arbitrage-1, router=github:gpt-4.1-nano — fast+cheap): "
        "You are the ITF ARB specialist. Cross-venue dislocations: IBIT vs BTC-spot, "
        "ETF-NAV premia, futures-spot basis. Your router is the fastest live route — "
        "exploit latency when the other venue mispriced. Current $400 reserved = low "
        "deployment; if no clean arb this tick, PASS. Arb is boring by design."
    ),
    "news-catalyst-1": (
        "WINNER-AWARE MANDATE (news-catalyst-1, router=cerebras:qwen-3-235b — 2000 tok/s, biggest context): "
        "You are the ITF CATALYST trader. Alpaca news feed + Polymarket + POL-engine "
        "hot-signals are your fuel. When a headline drops, you move FIRST. Cerebras "
        "gives you the speed to beat the herd. Currently IDLE — if no catalyst this "
        "tick, PASS; manufacturing a reaction to stale news = losing trade."
    ),
    "crypto-whale-1": (
        "WINNER-AWARE MANDATE (crypto-whale-1, router=mistral:medium — PQTF #2, 24/7 operator): "
        "You are the ITF CRYPTO specialist. Equity hours DON'T apply — crypto never "
        "closes, neither do you. Your mandate is ACTIVE every tick: if any /USD "
        "pair has |chg| > 0.4%, you trade. Currently 0 reserved = too passive. "
        "PASS is only justified if ALL crypto pairs are <0.3% from flat."
    ),
    "earnings-gap-1": (
        "WINNER-AWARE MANDATE (earnings-gap-1, router=cerebras:qwen-3-235b — fast + 235B params): "
        "You are the ITF EARNINGS specialist. Post-earnings drift, gap-fill plays, "
        "surprise vs guide. Currently holding $1,975 reserved — your highest-conviction "
        "tick state. Stay in the trade to the thesis target. Don't rotate out until "
        "gap fills or drift exhausts. No new positions if no fresh report this session."
    ),
    "iv-crush-1": (
        "WINNER-AWARE MANDATE (iv-crush-1, router=mistral:large — PQTF #1 derivatives brain): "
        "You are the ITF IV-CRUSH specialist. Sell premium INTO events (earnings, "
        "FOMC, CPI), close the day of event at open. Currently $1,711 reserved = "
        "active book. Manage theta decay daily; roll credits when underlying moves "
        "against the short strike. Off-hours = pass (options markets closed)."
    ),
    "macro-rotate-1": (
        "WINNER-AWARE MANDATE (macro-rotate-1, router=selfhost:phi-4-mini — LBJLincoln fleet, free): "
        "You are the ITF MACRO-ROTATE. XLK/XLE/XLF/XLV/SMH rotation based on POL "
        "hot-signals + VIX term + MM dealer positioning. Currently IDLE — rotation "
        "is weekly-timeframe, not per-tick; PASS if no regime shift in the POL 44-cat "
        "block. If your selfhost route times out, note it and pass — don't rush."
    ),
    "gap-fade-1": (
        "WINNER-AWARE MANDATE (gap-fade-1, router=cerebras:qwen-3-235b — fast + aggressive): "
        "You are the ITF GAP-FADE specialist. Opening-bell gaps without catalyst = "
        "your prey. First 30min of US session is prime hunting. Currently $1,200 "
        "reserved = healthy. Cerebras speed lets you get filled before the fade "
        "consumes itself. Pass outside 14:30-15:30 UTC unless crypto gap > 1.5%."
    ),
    "carry-1": (
        "WINNER-AWARE MANDATE (carry-1, router=github:llama-3.3-70b — stable after reroute): "
        "You are the ITF CARRY trader. Positive-carry structures: dividend-rich ETFs "
        "(SCHD/VYM), stablecoin-yield proxies, negative funding-rate shorts. Currently "
        "IDLE — carry is multi-day/week, not hour-to-hour. PASS is correct most ticks; "
        "only deploy when a new carry window opens (new dividend cycle, funding flip)."
    ),
    "breakdown-1": (
        "WINNER-AWARE MANDATE (breakdown-1, router=github:mistral-medium — stable route): "
        "You are the ITF BREAKDOWN specialist — the short side. Failed-breakouts, "
        "support losses, lower-lows structure. Currently $1,450 reserved = active "
        "short book, keep managing existing positions. SPY/QQQ below 200MA + VIX "
        "up-trend = your green light. Small-cap (IWM/RTY) shorts when dollar-up."
    ),
    "leveraged-momentum-1": (
        "WINNER-AWARE MANDATE (leveraged-momentum-1, router=mistral:medium — PQTF #2, leveraged-safe): "
        "You are the ITF LEVERAGED-MOMENTUM trader. TQQQ/SOXL/UVXY/USD on STRONG "
        "multi-day trends only (no chop). Currently $1,200 reserved = deployed. "
        "Decay is real — never hold 3x-leveraged ETFs into sideways tape. Your "
        "provider understands this; trust it to cut when the daily trend breaks."
    ),
}


# Dynamic tier selector — recomputed at each _build_prompt call from executor.
# Seed share is fleet_equity / 17; tiers key off realized delta + reservation ratio.
_WINNER_TIER_THRESHOLDS = {
    "winner_mult": 1.10,       # > 110% of seed share = winner
    "loser_mult":  0.90,       # <  90% of seed share = loser (probation)
    "deployer_ratio": 0.25,    # reserved / total >= 25% = active deployer
}


def _compute_agent_tier(tid: str, seed_share: float, total_equity: float,
                        reserved: float) -> str:
    """Return one of: 'winner' | 'deployer' | 'holder' | 'idle' | 'loser'."""
    if seed_share <= 0:
        seed_share = 5943.9  # defensive fallback matching current seed
    if total_equity >= seed_share * _WINNER_TIER_THRESHOLDS["winner_mult"]:
        return "winner"
    if total_equity <= seed_share * _WINNER_TIER_THRESHOLDS["loser_mult"]:
        return "loser"
    if total_equity <= 0 or reserved <= 0:
        return "idle"
    ratio = reserved / max(total_equity, 1.0)
    if ratio >= _WINNER_TIER_THRESHOLDS["deployer_ratio"]:
        return "deployer"
    return "holder"


def _tier_directive(tier: str, total_equity: float, seed_share: float) -> str:
    """Dynamic, tier-keyed directive appended AFTER the static addendum."""
    delta_pct = ((total_equity - seed_share) / max(seed_share, 1.0)) * 100.0
    if tier == "winner":
        _floor_pct = int(POWER_STAKE_FLOOR_PCT * 100)
        return (
            f"TIER: WINNER (equity ${total_equity:,.0f} = {delta_pct:+.1f}% vs seed). "
            f"SCALE: per-trade floor = {_floor_pct}% of your sub-bankroll "
            f"(ITF_STAKE_FLOOR_PCT={POWER_STAKE_FLOOR_PCT:.2f} active). You earned the "
            f"right to size up — keep executing what works. Up to 5 concurrent orders "
            f"per ticker allowed — stack conviction."
        )
    if tier == "deployer":
        return (
            f"TIER: ACTIVE-DEPLOYER (equity ${total_equity:,.0f}, {delta_pct:+.1f}%). "
            f"Tighten edge bar to >=0.03 on new entries. Prefer 2-3 high-conviction "
            f"per tick over 5-6 speculative. Manage existing book to thesis completion."
        )
    if tier == "holder":
        return (
            f"TIER: HOLDER (equity ${total_equity:,.0f}, {delta_pct:+.1f}%). "
            f"Tactical high-conviction mode. Let existing positions work; new entries "
            f"require edge >=0.03 AND a named thesis (not just a spread). PASS freely."
        )
    if tier == "loser":
        return (
            f"TIER: PROBATION (equity ${total_equity:,.0f} = {delta_pct:+.1f}% vs seed). "
            f"Edge >=0.05 REQUIRED on every new entry. MIN_HOLD_SEC=900 already blocks "
            f"sub-15min daytrade closes. No churn. Rebuild discipline — one good trade "
            f"per tick beats three speculative. 20-tick probation until you recover."
        )
    # idle
    return (
        f"TIER: IDLE (equity ${total_equity:,.0f}, 0 reserved). "
        f"No open book. Deploy ONLY on a named setup w/ edge >=0.03. Don't force action "
        f"just because everyone else is trading — the tape is not obligated to give you a "
        f"setup every 90s. Pass is valid; speculative entries to 'stay active' are not."
    )


# ────── 2026-04-20 AGGRESSIVE-MODE: knowledge + peer-bet + milestone council ──────
#
# All 3 digests are lazily computed once per day and cached in STATE.
# Scientific rationale:
#   - Paper digest brings cross-repo research (papers/PQTF post-mortem/TF lessons)
#     into every ITF prompt so agents aren't reasoning from their training cutoff alone.
#   - Peer-bet digest (last 3 days) gives Axelrod-canon awareness: what did peers do,
#     did they win? Enables cooperate-or-differentiate choices without council lockstep.
#   - Milestone council (every 15 days) synthesizes fleet state via cerebras:qwen-3-235b
#     (2000 tok/s, biggest context among live routes). Plan persists 15 days — loose
#     enough to avoid DMAD-style groupthink, tight enough to coordinate when the fleet
#     has a clear leader trajectory. Rationale logged in data/intraday/council_plans/.

_KNOWLEDGE_DIGEST_CACHE: Dict[str, str] = {"date": "", "text": ""}
COUNCIL_INTERVAL_DAYS = int(os.environ.get("ITF_COUNCIL_DAYS", "15"))
COUNCIL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "intraday" / "council_plans"
try:
    COUNCIL_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


def _build_knowledge_digest() -> str:
    """Return compact (~800 tok) 1× / day digest of: recent arxiv scans, PQTF post-
    mortem highlights, NBA/POL lessons. Cached by UTC day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _KNOWLEDGE_DIGEST_CACHE.get("date") == today and _KNOWLEDGE_DIGEST_CACHE.get("text"):
        return _KNOWLEDGE_DIGEST_CACHE["text"]

    lines: List[str] = []
    lines.append("RESEARCH + CROSS-TF LESSONS (refreshed daily):")

    # (A) Top 3 papers from most-recent multiagent-trading scan
    try:
        research_dir = _REPO / "data" / "research"
        scan_files = sorted(research_dir.glob("arxiv-multiagent-trading-scan-*.json"), reverse=True)[:1]
        if not scan_files:
            scan_files = sorted(research_dir.glob("arxiv-scan-*.json"), reverse=True)[:1]
        if scan_files:
            data = json.loads(scan_files[0].read_text())
            papers = (data.get("papers") or [])[:3]
            if papers:
                lines.append("• Recent papers (arxiv):")
                for p in papers:
                    title = str(p.get("title", ""))[:90]
                    summary = str(p.get("summary", ""))[:120].replace("\n", " ")
                    lines.append(f"  - {title}: {summary}")
    except Exception:
        pass

    # (B) PQTF $1M proof highlights
    lines.append("• PQTF $1M VALIDATION (50/50 days, $600→$602,354, 100,292% ROI):")
    lines.append("  - mistral:large → $244,050 (+40,667%) — derivatives brain, XLC/XLE/XLF/XLK, 12 positions/day, 4 pacts")
    lines.append("  - mistral:medium → $154,566 (+25,761%) — sector-options spread trader")
    lines.append("  - gemini-2.5-flash → $17K via macro-anl reasoning")
    lines.append("  - Lesson: concentrate on sectors with live signal, compound wins, pact with peers")

    # (C) NBA/POL TF lessons
    lines.append("• NBA/POL TF LIVE WINNERS (2026-04-19):")
    lines.append("  - POL: google:gemini-3-flash (gemini-anl) $470.72 +370.7% on event-driven sector bets")
    lines.append("  - NBA: selfhost:dolphin3-l32-3b +3× / cerebras:qwen-3-235b (qwen-quant) $26.06")
    lines.append("  - Failure modes: lockstep (4/5 picks held by ≥10/17 agents was luck not skill),")
    lines.append("    silent-pass on LLM error (fixed via uniform-fallback emitter — YOU must never silent-pass)")

    # (D) Axelrod / cooperation canon
    lines.append("• COOPERATION DOCTRINE:")
    lines.append("  - BE NICE. Don't front-run teammate thesis.")
    lines.append("  - STRUCTURAL DIVERGE — if you see 10 peers on QQQ-long, consider short VIXY or pair trade.")
    lines.append("  - COLLECTIVE-HELP — if any peer bankroll < $50, top-3 agents must propose pact.")
    lines.append("  - Milestones at days 15, 30, 45, 60 emit a council_plan — read it.")

    # (E) Calibration + regime reminders
    lines.append("• REGIME HINTS: VIX<15=carry, 15-22=neutral, >22=defensive, >30=whipsaw-skip.")
    lines.append("  Crypto: always has delta, use when equities closed.")

    text = "\n".join(lines)
    # Crude 800-token cap (~3200 chars).
    if len(text) > 3200:
        text = text[:3200] + "\n  [... truncated for token budget ...]"
    _KNOWLEDGE_DIGEST_CACHE["date"] = today
    _KNOWLEDGE_DIGEST_CACHE["text"] = text
    return text


def _build_peer_bets_digest(persona: Dict[str, Any], n_days: int = 3) -> str:
    """Compact 'what peers did last N days' summary — feeds Axelrod cooperation."""
    tid = persona["tid"]
    lines: List[str] = []
    # Find last n_days worth of decisions jsonl files.
    all_days = sorted(
        [p for p in DECISIONS_DIR.glob("*.jsonl") if p.is_file()],
        key=lambda p: p.stem,
        reverse=True,
    )[:n_days]
    if not all_days:
        return "(no prior history — you are the first tick)"
    for day_file in reversed(all_days):
        day = day_file.stem
        # Summarize: tid → ticker → side → count (max 5 peers per day to stay compact)
        by_tid: Dict[str, List[str]] = {}
        try:
            for line in day_file.read_text().splitlines()[-80:]:  # cap per day
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                peer_tid = r.get("agent_tid")
                if not peer_tid or peer_tid == tid:
                    continue
                dec = r.get("decision") or {}
                if dec.get("action") == "trade":
                    by_tid.setdefault(peer_tid, []).append(
                        f"{dec.get('ticker', '?')} {dec.get('side','?')}"
                    )
                elif dec.get("action") == "option_trade":
                    by_tid.setdefault(peer_tid, []).append(
                        f"{dec.get('underlying','?')} {dec.get('strategy','?')} {dec.get('option_type','?')}"
                    )
        except Exception:
            continue
        if not by_tid:
            continue
        top = list(by_tid.items())[:5]
        lines.append(f"  [{day}] " + " | ".join(
            f"{t}: {', '.join(acts[:2])}" for t, acts in top
        ))
    if not lines:
        return "(peers passed all of last N days — lead from the front)"
    return "PEER BETS (last {}d, excluding you):\n".format(n_days) + "\n".join(lines[-3:])


def _current_day_idx() -> int:
    """0-indexed day counter since ITF state init (approximated by # of decisions files)."""
    try:
        return max(0, len(list(DECISIONS_DIR.glob("*.jsonl"))) - 1)
    except Exception:
        return 0


def _latest_council_plan() -> Optional[Dict[str, Any]]:
    """Read newest council plan if any — persists 15 days."""
    try:
        files = sorted(COUNCIL_DIR.glob("*.json"), key=lambda p: p.stem, reverse=True)
        if not files:
            return None
        return json.loads(files[0].read_text())
    except Exception:
        return None


def run_milestone_council(fleet_board: List[Dict[str, Any]],
                          ctx: Dict[str, Any], day_idx: int) -> Optional[Dict[str, Any]]:
    """Every COUNCIL_INTERVAL_DAYS (default 15): moderator LLM writes a 15-day plan
    that all 14 agents see. Persists to data/intraday/council_plans/day-XXX.json."""
    roster = []
    for row in fleet_board:
        roster.append(
            f"  - {row.get('tid')}: ${row.get('total_pnl_usd',0):+.0f} "
            f"({row.get('trades',0)}t/{row.get('passes',0)}p, open={row.get('open_positions',0)})"
        )
    quotes = ctx.get("quotes") or {}
    hot_tickers = sorted(
        [(t, abs(float((q or {}).get("change_pct") or 0))) for t, q in quotes.items()],
        key=lambda x: -x[1]
    )[:8]
    hot_block = ", ".join(f"{t} {chg:+.2f}%" for t, chg in hot_tickers if chg > 0)

    sys_prompt = (
        "You are the ITF COUNCIL MODERATOR. 14 intraday LLM agents need a shared "
        "15-day plan: which tickers/asset-classes to focus on, which regimes to "
        "avoid, which coalitions to seed. One agent must reach $1M by Aug 1 2026."
    )
    usr_prompt = f"""COUNCIL SESSION · day {day_idx}

FLEET:
{chr(10).join(roster)}

HOT TAPE (|chg| ranked): {hot_block or '(flat)'}

TASK: Output PLAN JSON:
{{
  "council_summary": "1 sentence — what's the next 15 days' focus?",
  "focus_tickers": ["SPY", "BTC/USD", ...],      // 3-8 tickers
  "avoid_regimes": ["VIX>30 whipsaw", ...],      // 1-3 regimes
  "seed_coalitions": [["momentum-1","leveraged-momentum-1","leverage-long-tech"]],  // pair/trio IDs + thesis tag
  "risk_posture": "aggressive"|"balanced"|"defensive",
  "shared_notes": "1-3 sentences actionable"
}}

RAW JSON ONLY. 14 agent ids are: scalper-1, momentum-1, mean-rev-1, breakout-1, pairs-1, vol-1, options-1, arbitrage-1, news-catalyst-1, crypto-whale-1, earnings-gap-1, iv-crush-1, macro-rotate-1, leveraged-momentum-1."""

    try:
        resp = gateway_call(
            "cerebras:qwen-3-235b",
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": usr_prompt},
            ],
            temperature=0.4, max_tokens=500, timeout=20.0,
        )
        parsed = _parse_json((resp or {}).get("text") or "")
    except Exception:
        parsed = None

    plan = parsed if isinstance(parsed, dict) else {
        "council_summary": "deterministic fallback — balanced posture, follow strongest tape",
        "focus_tickers": ["SPY", "QQQ", "NVDA", "BTC/USD", "ETH/USD"],
        "avoid_regimes": ["VIX>30 whipsaw"],
        "seed_coalitions": [],
        "risk_posture": "balanced",
        "shared_notes": "No LLM response — default plan. Read peer bets and act.",
    }
    plan["day_idx"] = day_idx
    plan["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        out = COUNCIL_DIR / f"day-{day_idx:03d}.json"
        out.write_text(json.dumps(plan, indent=2, default=str))
    except Exception as e:
        print(f"[itf-council] persist fail: {e}", file=sys.stderr)
    return plan


def _format_council_block(plan: Optional[Dict[str, Any]]) -> str:
    if not plan:
        return "(no active council plan)"
    focus = ", ".join(plan.get("focus_tickers", [])[:8]) or "(any)"
    avoid = "; ".join(plan.get("avoid_regimes", [])[:3]) or "(none)"
    posture = plan.get("risk_posture", "balanced")
    summary = (plan.get("council_summary") or "")[:200]
    notes = (plan.get("shared_notes") or "")[:200]
    return (
        f"COUNCIL PLAN (day {plan.get('day_idx','?')}, posture={posture}):\n"
        f"  focus: {focus}\n  avoid: {avoid}\n  summary: {summary}\n  notes: {notes}"
    )


def _off_hours_crypto_signal(quotes: Dict[str, Dict[str, Any]]) -> bool:
    """True if any of BTC/ETH/SOL has |change_pct| > 0.2% — enough tape to trade."""
    for pair in ("BTC/USD", "ETH/USD", "SOL/USD"):
        q = quotes.get(pair) or {}
        chg = q.get("change_pct")
        if chg is not None and abs(float(chg)) > 0.2:
            return True
    return False


# ── NO-TRADE REGIME GATE (2026-04-21, proposal #3) ──────────────────────────
# Source: MDPI Mathematics 13/15/2382 + Amberdata vol framework. Markov-
# switching vol classifier. When the 30-min realized-vol floor is breached,
# waive the "≥3 allocations" + "≥75% deploy" mandates and let agents pass.
#
# Implementation: proxy realized_vol as (5m_high − 5m_low) / last across the
# crypto universe (20 pairs), median across pairs. No persistent rolling-30min
# history available per-Space (quote_bus writes 5 ticks/day), so this is a
# same-tick proxy. 5m range ≈ 30-min realized vol when scaled by sqrt(6).
# Empirical tune: 0.3% per 5min = 0.3% × sqrt(6) ≈ 0.73% per 30min, which
# lines up with the 0.3%-floor target in the proposal *if we interpret it as
# 5-min floor*. We key the floor to the 5-min proxy directly: REGIME_FLOOR_5M=0.003.
#
# Env override: ITF_REGIME_FLOOR_5M (default 0.003 = 0.3%).
REGIME_FLOOR_5M = float(os.environ.get("ITF_REGIME_FLOOR_5M", "0.003"))


def _compute_crypto_regime(quotes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Return {'median_realized_vol': float, 'low_vol_regime': bool, 'floor': float,
    'sample_n': int, 'pairs_checked': list}. Median across crypto pairs only
    (24/7 tradeable; we gate ITF on crypto regime since most personas crypto-pivot
    off-hours and the equity universe is discontinuous overnight).
    """
    ranges: List[float] = []
    pairs: List[str] = []
    for t, q in (quotes or {}).items():
        if "/" not in t:
            continue
        q = q or {}
        last = q.get("last")
        hi = q.get("5m_high")
        lo = q.get("5m_low")
        try:
            last_f = float(last) if last is not None else None
            hi_f = float(hi) if hi is not None else None
            lo_f = float(lo) if lo is not None else None
        except (TypeError, ValueError):
            continue
        if not last_f or hi_f is None or lo_f is None or last_f <= 0:
            continue
        rv = max(0.0, (hi_f - lo_f) / last_f)
        ranges.append(rv)
        pairs.append(t)
    if not ranges:
        return {"median_realized_vol": None, "low_vol_regime": False,
                "floor": REGIME_FLOOR_5M, "sample_n": 0, "pairs_checked": []}
    ranges_sorted = sorted(ranges)
    mid = len(ranges_sorted) // 2
    if len(ranges_sorted) % 2 == 1:
        median = ranges_sorted[mid]
    else:
        median = (ranges_sorted[mid - 1] + ranges_sorted[mid]) / 2.0
    return {
        "median_realized_vol": round(median, 5),
        "low_vol_regime": bool(median < REGIME_FLOOR_5M),
        "floor": REGIME_FLOOR_5M,
        "sample_n": len(ranges),
        "pairs_checked": pairs[:10],
    }


DEAD_TAPE_CLAUSE = (
    "REGIME OVERRIDE — DEAD TAPE: Median crypto 5m range is below the "
    "0.3% floor (markov-switching vol classifier flags low-vol regime). "
    "Market is in low-vol regime. Preserving capital is the winning move. "
    "action='pass' is fully acceptable for this tick. The ≥3-trades / ≥75%-"
    "deploy mandates are WAIVED until vol recovers. Trade ONLY if you see a "
    "true asymmetric edge — otherwise pass and let the tape tell you when to strike."
)

FULL_UNIVERSE_MANDATE = """
FULL-UNIVERSE MANDATE (ITF 2026-04-24): the $1M target requires using EVERY
asset class available on Alpaca paper -- not just SPY/QQQ/sector ETFs. Your
daily allocation MUST span ≥4 of these 7 classes (rotate weekly, never dwell):

  1. Core equity       (SPY, QQQ, IWM, DIA, VOO, VTI)
  2. Sector/thematic   (XLK/XLF/XLE/XLV/XLI/XLB/XLRE/XLU/XLC + ARKK/IBIT/SMH/XBI/ITA/TAN/ICLN/GDX/XME/KRE/XHB)
  3. Leveraged/inverse (TQQQ/SQQQ/SPXL/SPXS/SOXL/SOXS/TNA/TZA -- up to 3x; size DOWN)
  4. Volatility        (VXX/UVXY/SVXY/VIXY -- hedge + asymmetric upside on shock days)
  5. International     (EEM/FXI/EWZ/EWJ/EWT/EWW/VGK/INDA/VEA/IEFA/ACWX/EFA/VWO)
  6. Bonds/rates       (TLT/IEF/IEI/SHY/LQD/HYG -- duration + credit legs)
  7. Commodity/FX      (GLD/SLV/USO/UNG/DBA/DBC/CORN/WEAT/CPER/URA + UUP)
  8. Crypto 24/7       (BTC/ETH/SOL/LINK/AVAX/DOGE/DOT/MATIC/LTC/UNI/BCH/XLM/XRP/AAVE/SHIB/MKR/SUSHI/CRV/YFI/GRT)
  9. Options spreads   (verticals, iron condors, straddles on SPY/QQQ/NVDA/TSLA/MSTR -- 1-5 DTE)

BANNED ANTI-PATTERNS: (a) same 3 tickers every day, (b) >60% allocation in a
single asset class, (c) skipping crypto outside market hours -- it's 24/7,
non-participation is a wasted tick.

When equity market is closed (nights/weekends), pivot weight to crypto +
already-open options positions. Never pass the whole tick citing "market
closed" -- crypto tape is ALWAYS live.

POL-SIGNAL MANDATE (2026-04-24): The POL engine hot-signals block above lists
specific tickers where insiders (Form-4 clusters), Congress, or bill-related
news is actively firing. These are PRE-VETTED asymmetric-edge tickers. If the
POL block shows a Form4 cluster (n>=3 insiders buying) OR a Congress buy OR a
SCOTUS case in a specific sector, you MUST:
  - Include that ticker (or its sector ETF) as a LONG allocation today, OR
  - Write an explicit rebuttal in your `thesis` field citing why the POL
    signal is wrong (e.g., "JPM cluster is disclosure-driven not alpha-driven"
    with a specific counter-reason).
Ignoring POL signals in silence = violating the mandate. The political engine
ships fresh every 5 minutes precisely to give ITF its alpha edge -- USE IT.

PQTF CHAMPION PLAYBOOK (2026-04-24 — empirical from 50-day archive):
  PQTF mistral:large won +$244K by concentrating on:
    XLF (+$14,406)  - financials, single-leg calls on Fed / rate-cut tailwind
    XLK (+$4,305)   - tech, same pattern
    XLC (+$2,271)   - communications
  Multi-leg strategies (iron_condor/straddle/vertical) had NET LOSSES in the
  same period. The PQTF champion's edge was SINGLE-LEG directional calls on
  sector-rotation tickers, not clever spreads.
  Lesson for ITF options-1 / iv-crush-1 personas: single-leg on XLF/XLK/XLC
  during favorable regime is PROVEN. Reserve multi-leg for explicit vol/IV
  trades, not as a default.
"""


def _build_prompt(persona: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    # Compact context to stay under token caps (~1500 tokens).
    # CRITICAL: previous version `quotes_summary[:22]` truncated everything after
    # the first 22 equity tickers, so crypto (24/7) was never shown — every agent
    # passed at night citing "vol=0 / market closed" when in fact BTC/ETH/SOL etc.
    # were actively moving. We now group by asset class + show VIX + equity probes.
    quotes = ctx.get("quotes") or {}

    def _fmt(t: str, q: Dict[str, Any]) -> str:
        last = q.get("last")
        chg = q.get("change_pct")
        vol = q.get("volume")
        return f"{t}: last={last} Δ={chg}% vol={vol}"

    now_utc = datetime.now(timezone.utc)
    equity_hours = now_utc.weekday() < 5 and 8 <= now_utc.hour < 24

    crypto_tickers  = [t for t in quotes if "/" in t]
    index_tickers   = [t for t in quotes if t.startswith("^")]
    equity_tickers  = [t for t in quotes if t not in crypto_tickers and t not in index_tickers]
    # Equity probes we always want visible if present.
    # 2026-04-21 expansion: surface more mega-caps + sector leaders in the tape so
    # LLMs see a broader opportunity surface (user request). On-demand quotes still
    # unlock the full 10k+ equity universe for any ticker an agent mentions.
    priority_eq = [t for t in ["SPY", "QQQ", "IWM", "DIA",
                                "XLK", "XLE", "XLF", "XLV", "SMH",
                                "TQQQ", "SQQQ", "UVXY", "VXX",
                                "NVDA", "TSLA", "AAPL", "META", "MSFT", "GOOGL", "AMD", "AMZN",
                                "GLD", "TLT", "IBIT",
                                "COIN", "MSTR", "CRWD", "PLTR"] if t in quotes]
    # Remaining equities (leveraged, sector, stocks we haven't already shown), capped.
    remaining_eq = [t for t in equity_tickers if t not in priority_eq][:8]

    lines: List[str] = []
    if index_tickers:
        lines.append("--- VIX / Indices ---")
        for t in index_tickers:
            lines.append(_fmt(t, quotes[t] or {}))
    if crypto_tickers:
        lines.append(f"--- Crypto (24/7, tradeable NOW) ---")
        for t in crypto_tickers:
            lines.append(_fmt(t, quotes[t] or {}))
    lines.append(f"--- Equities ({'OPEN' if equity_hours else 'CLOSED — do not emit equity/option trades'}) ---")
    for t in priority_eq + remaining_eq:
        lines.append(_fmt(t, quotes[t] or {}))
    quotes_block = "\n".join(lines)

    nba_edges = ctx.get("nba_top_edges") or []
    nba_block = "; ".join(
        f"{g.get('away')}@{g.get('home')} {g.get('pick')} edge={g.get('edge_pct'):.2f}%"
        for g in nba_edges
    ) or "(none today)"

    pol_sigs = ctx.get("pol_top_signals") or []
    pol_block = "; ".join(
        f"{s.get('event')} {s.get('sector_etf')} strength={s.get('strength')}"
        for s in pol_sigs
    ) or "(none today)"

    # 2026-04-20 UPGRADE: live news + event markets as signal. Tight token budget —
    # 10 headlines + 6 events max, each truncated so total stays <700 tok.
    news_items = ctx.get("live_news") or []
    news_lines: List[str] = []
    for n in news_items[:10]:
        syms = ",".join((n.get("symbols") or [])[:3]) or "—"
        headline = (n.get("headline") or "")[:110]
        created = (n.get("created_at") or "")[11:16]  # HH:MM
        news_lines.append(f"  [{created}Z {syms}] {headline}")
    news_block = "\n".join(news_lines) or "  (no fresh news)"

    poly_items = ctx.get("polymarket_events") or []
    poly_lines: List[str] = []
    for m in poly_items[:6]:
        q = (m.get("question") or "")[:100]
        yes = m.get("yes_prob")
        vol = m.get("volume_24h")
        prob_str = f"YES={yes*100:.0f}%" if isinstance(yes, (int, float)) and yes else "?"
        vol_str = f"${vol:,.0f}" if isinstance(vol, (int, float)) else "?"
        poly_lines.append(f"  {prob_str} {vol_str}/24h — {q}")
    poly_block = "\n".join(poly_lines) or "  (no active markets)"

    # 2026-04-22 — live Kalshi + Polymarket order books (paper-tradeable). Each
    # row is a fully-quoted binary market the agent can stake YES or NO on via
    # {"action":"event_trade", ...}. Both venues use free public APIs (no auth
    # needed for data). Cache TTL 60s inside event_executor.
    _ev_lines: List[str] = []
    try:
        kalshi_rows = ev.list_markets("kalshi", limit=8) or []
        for r in kalshi_rows:
            mid = (r.get("market_id") or "")[:36]
            q = (r.get("question") or "")[:85]
            yp = r.get("yes_price"); np = r.get("no_price")
            vol = r.get("volume_usd") or 0
            _ev_lines.append(
                f"  [KALSHI {mid}] YES={yp:.2f} NO={np:.2f} "
                f"vol=${vol:,.0f} — {q}" if yp is not None and np is not None
                else f"  [KALSHI {mid}] (no live midpoint) — {q}"
            )
    except Exception as _ke:
        _ev_lines.append(f"  (kalshi feed err: {_ke})")
    try:
        poly_rows = ev.list_markets("polymarket", limit=8) or []
        for r in poly_rows:
            mid = (r.get("market_id") or "")[:36]
            q = (r.get("question") or "")[:85]
            yp = r.get("yes_price"); np = r.get("no_price")
            vol = r.get("volume_usd") or 0
            _ev_lines.append(
                f"  [POLY {mid}] YES={yp:.2f} NO={np:.2f} "
                f"vol=${vol:,.0f}/24h — {q}"
            )
    except Exception as _pe:
        _ev_lines.append(f"  (polymarket feed err: {_pe})")
    event_markets_block = "\n".join(_ev_lines) or "  (no live binary markets)"

    pqtf = ctx.get("pqtf_state") or {}
    pqtf_block = (
        f"last_day={pqtf.get('last_day', '?')} fleet=${pqtf.get('fleet_bankroll', '?')} "
        f"open_positions={len(pqtf.get('open_positions') or [])}"
    )

    # 2026-04-21 v2.7 — POL ENGINE 44-cat hot signals + MM dealer-positioning.
    # Every one of the 17 personas sees both blocks verbatim (user directive:
    # "chaque agent aura bien all infos"). Tight formatting so total prompt stays
    # ≲4.5k tokens even after these injections.
    pol_hot = ctx.get("pol_engine_hot") or {}
    pol_hot_lines: List[str] = []
    tariff = pol_hot.get("cat26_37_tariff") or {}
    if tariff.get("regime"):
        pol_hot_lines.append(
            f"  Tariff: {tariff.get('regime')} · China {tariff.get('china_tariff')} · "
            f"{tariff.get('days_left_in_pause', 0)}d left in pause"
        )
    iran = (pol_hot.get("cat36_iran") or {}).get("markets") or []
    for m in iran[:2]:
        pol_hot_lines.append(f"  Iran Poly: p={m.get('p')} vol24={m.get('v24')} — {(m.get('q') or '')[:70]}")
    poly_d = (pol_hot.get("cat11_polymarket_delta") or {}).get("markets") or []
    for m in poly_d[:3]:
        pol_hot_lines.append(f"  Poly Δ24h: {m.get('d24'):+.3f} (p={m.get('p')}) v=${m.get('v24')} — {(m.get('q') or '')[:60]}")
    kalshi = (pol_hot.get("cat27_kalshi") or {}).get("top_kalshi") or []
    for k in kalshi[:2]:
        pol_hot_lines.append(f"  Kalshi: p={k.get('p')} v={k.get('v')} — {(k.get('t') or '')[:60]}")
    clusters = (pol_hot.get("cat6_form4_clusters") or {}).get("clusters") or []
    # 2026-04-24: show ALL (was [:3]) + robust net_usd formatting
    for c in clusters[:10]:
        net = c.get("net_usd")
        net_s = f" ${net:,}" if isinstance(net, (int, float)) else ""
        pol_hot_lines.append(f"  Form4 cluster: {c.get('tkr')} n={c.get('n')}{net_s} (most_recent {c.get('most_recent','?')})")
    congress = (pol_hot.get("cat24_congress") or {}).get("trades") or []
    for t in congress[:10]:
        usd = t.get("usd")
        usd_s = f" ~${usd:,}" if isinstance(usd, (int, float)) else ""
        pol_hot_lines.append(f"  Congress buy: {t.get('tkr')} by {t.get('rep')}{usd_s} ({t.get('date','?')})")
    # 2026-04-24 MANDATE: collect POL-signaled tickers for prioritization
    pol_signaled = set()
    for c in clusters[:10]:
        if c.get("tkr"): pol_signaled.add(c["tkr"])
    for t in congress[:10]:
        if t.get("tkr"): pol_signaled.add(t["tkr"])
    if pol_signaled:
        pol_hot_lines.append(
            f"  POL-SIGNALED TICKERS (long-bias candidates): {', '.join(sorted(pol_signaled))}"
        )
    scotus = (pol_hot.get("cat30_scotus") or {}).get("cases") or []
    for s in scotus[:2]:
        pol_hot_lines.append(f"  SCOTUS: {(s.get('case') or '')[:60]} [{s.get('sector')}/{s.get('stage')}]")
    yt = (pol_hot.get("cat44_youtube_finbert") or {}).get("top") or []
    if yt:
        yt_s = ", ".join(f"{x.get('ticker')}={x.get('polarity_3d', x.get('polarity','?'))}" for x in yt[:5] if isinstance(x, dict))
        if yt_s:
            pol_hot_lines.append(f"  YT FinBERT 3d: {yt_s}")
    pol_hot_block = "\n".join(pol_hot_lines) or "  (POL engine hot-signals unavailable)"

    mm = ctx.get("mm_signals") or {}
    mm_lines: List[str] = []
    if mm.get("summary"):
        mm_lines.append(f"  {mm['summary']}")
    term = mm.get("vix_term") or {}
    if term.get("vix9d") is not None or term.get("vix") is not None or term.get("vix3m") is not None:
        mm_lines.append(
            f"  VIX term: 9d={term.get('vix9d')} · 30d={term.get('vix')} · 3M={term.get('vix3m')}"
            + (f" ({term.get('regime')})" if term.get("regime") else "")
        )
    spy = mm.get("spy") or {}
    if spy:
        mm_lines.append(
            f"  SPY spot={spy.get('spot')} PCR={spy.get('spy_pcr')} {spy.get('pcr_regime','')} "
            f"GEX_proxy={spy.get('spy_gex_proxy_mm')}M {spy.get('gex_sign','')}"
        )
    for u in (mm.get("unusual_options") or [])[:4]:
        mm_lines.append(
            f"  Unusual {u.get('t')} {u.get('side')}{u.get('strike')} exp={u.get('exp')} "
            f"vol={u.get('vol')} vol/oi={u.get('vol_oi')}"
        )
    mm_block = "\n".join(mm_lines) or "  (MM signals unavailable)"

    # 2026-04-26 — STRIPPED to user spec: persona style is the only style.
    # No off-hours override, no FULL_UNIVERSE_MANDATE, no winner-aware addendum,
    # no tier directives. Agents choose freely per personality + bankroll rules.
    style_final = persona["style"]

    # 2026-04-26 — STRIPPED: knowledge/council/peer digests were coercive
    # ("YOU MUST never silent-pass", cooperation pacts, milestone councils).
    # Carte-blanche removes them. _pm_override left in (user-edited rule file).
    knowledge_digest = ""
    peer_digest = ""
    council_block = ""

    _pm_override = _load_prompt_override("itf")

    # 2026-04-26 — bankroll rules block (carte-blanche on choice, structural on sizing).
    _agent_bankroll = executor.get_bankroll(persona["tid"])
    # POL-signaled tickers (Form-4 insider clusters + Congress trades — proven
    # alpha source from POL TF where qwen-quant +275% / llama-contra +100% on
    # exactly these signals).
    _pol_signaled_str = ", ".join(sorted(pol_signaled)) if pol_signaled else "(none today)"
    _bankroll_block = (
        f"YOUR CAPITAL: ${_agent_bankroll:,.2f} (your sub-bankroll out of 17 agents).\n"
        f"Bankroll rules (server-enforced):\n"
        f"  • Stake sizing: Kelly cap + per-agent floor (over-bets clipped automatically).\n"
        f"  • 5 action types first-class: trade / option_trade / event_trade (Kalshi/Polymarket) / close / pass.\n"
        f"  • Event markets are 24/7 — outside equity hours they are often the only live edge.\n"
        f"  • POL CROSS-POLLINATION (priority): when your chosen ticker matches a POL\n"
        f"    SIGNAL (Form-4 insider cluster ≥3 OR Congress trade), the server applies\n"
        f"    a 1.5× stake multiplier. POL agents qwen-quant/llama-contra/gemini-tact\n"
        f"    compounded +275% / +100% / +97% on exactly these signals. Today's POL-\n"
        f"    signaled tickers: {_pol_signaled_str}. Sector ETFs (XLE/XLK/XLF/XLV/XLY)\n"
        f"    are the proven POL-winners' instrument; single-name from the cluster\n"
        f"    list also qualifies for the 1.5× stake bonus."
    )

    # 2026-04-28 MAX-AGGRESSION DOCTRINE — gated on ITF_MAX_AGGRO env. User has
    # explicitly accepted -$90K downside to chase $1M target ($93K → $1M = ~10×).
    # Removes edge floors below 1.5%, mandates leveraged instruments on conviction,
    # and blocks "PASS unless tape is dead" framing.
    _max_aggro_block = ""
    if os.environ.get("ITF_MAX_AGGRO") == "1":
        _max_aggro_block = (
            "\n=== MAX-AGGRESSION DOCTRINE (user-authorized 2026-04-28) ===\n"
            "TARGET: fleet equity $1,000,000 (we are at ~$93K). User has explicitly\n"
            "accepted -$90K full drawdown of remaining capital to get there.\n"
            "RULES:\n"
            "  • Every position must have ≥3× asymmetric upside (3:1 reward/risk min).\n"
            "  • Edge floor: 1.5%. Below that → PASS. Above → SIZE UP, not down.\n"
            "  • PREFER: 0DTE OTM options on SPY/QQQ/IWM (max gamma), leveraged ETFs\n"
            "    (TQQQ/SOXL/SPXL/UPRO/TNA on bullish, SQQQ/SPXS/TZA on bearish),\n"
            "    high-conviction crypto (BTC/ETH/SOL when momentum >2σ).\n"
            "  • PASS only when there is genuinely no setup — never as risk avoidance.\n"
            "  • Stake size = the FULL Kelly cap, not fractional. The server enforces\n"
            "    your per-agent leverage ceiling ($per_agent_equity × 4) — sizing UP\n"
            "    to that ceiling is correct behavior, not reckless.\n"
            "  • You are 1 of 17 agents. Top winners (qwen-arb +103×, mistral-large +PQTF)\n"
            "    got there by sizing up on their highest-conviction setups, not hedging.\n"
            "=========================================================\n"
        )

    return f"""{COLLECTIVE_MISSION}

{AXELROD_CANON}{_pm_override}

{_bankroll_block}

{knowledge_digest}

{council_block}

{peer_digest}

YOUR ROLE — {persona['name']} ({persona['tid']}):
{style_final}

INTRADAY TAPE ({ctx.get('quotes_ts')} · {ctx.get('quotes_source')}):
{quotes_block}

LIVE NEWS (Alpaca news feed, ticker-indexed, last hour):
{news_block}

EVENT MARKETS — SIGNAL (Polymarket context, top volume 24h):
{poly_block}

EVENT MARKETS — PAPER-TRADEABLE (Kalshi + Polymarket, YES/NO binary at midpoint + 1¢ slippage):
{event_markets_block}

POL ENGINE HOT SIGNALS (44-cat upstream, refreshed ~15min — macro / catalysts / insider / prediction-markets):
{pol_hot_block}

MM DEALER POSITIONING (vol regime, gamma, unusual flow — what market-makers are telling us):
{mm_block}

NBA TOP-5 EDGES today: {nba_block}
POL TOP-5 SIGNALS today: {pol_block}
PQTF state: {pqtf_block}
{_max_aggro_block}
{DECISION_SCHEMA}
"""


def _uniform_fallback_itf(persona: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """When both LLMs fail, emit a tier-rotated, traceable trade instead of silence.

    Rationale mirrors NBA/POL/PQTF uniform-fallback: silent-pass storage drops were
    the dominant TF failure mode (commits efdddd5e1 + 77a01a839). ITF must follow.
    Picks a liquid ticker keyed on persona tier + tid hash so 7 personas don't all
    pile on the same instrument on a global LLM outage.
    """
    # 2026-04-21 proposal #3 — regime gate: in low-vol regime, emit an explicit
    # pass (waive the "silent-pass banned" rule). Tagged so analytics can split
    # regime-passes from pure silent drops.
    try:
        regime = ctx.get("regime") or {}
        if regime.get("low_vol_regime"):
            return {"action": "pass",
                    "reason": f"regime_gate_low_vol (median_5m_vol={regime.get('median_realized_vol')} < {regime.get('floor')})",
                    "provider_status": "regime_pass"}
    except Exception:
        pass
    tier = (persona.get("tier") or "").lower()
    tid = persona.get("tid") or ""
    # Tier-rotated candidate pools. Post-2026-04-20 expansion: tier is now S/M/L
    # so we also map per-tid to keep archetype flavor (arb → pair, whale → BTC).
    by_tid = {
        "scalper-1":            ["SPY", "QQQ", "IWM"],
        "momentum-1":           ["XLK", "XLE", "XLF"],
        "mean-rev-1":           ["XLV", "XLP", "SPY"],
        "breakout-1":           ["QQQ", "TSLA", "AMD", "COIN"],
        "pairs-1":              ["XLE", "XLU", "XLK"],
        "vol-1":                ["VXX", "UVXY", "SPY"],
        "options-1":            ["SPY", "QQQ"],
        "arbitrage-1":          ["SPY", "QQQ", "IWM"],
        "news-catalyst-1":      ["NVDA", "TSLA", "COIN", "MSTR"],
        "crypto-whale-1":       ["BTC/USD", "ETH/USD", "SOL/USD"],
        "earnings-gap-1":       ["NVDA", "AAPL", "META", "TSLA"],
        "iv-crush-1":           ["SPY", "QQQ"],
        "macro-rotate-1":       ["GLD", "TLT", "UUP", "XLU"],
        "leveraged-momentum-1": ["TQQQ", "SPXL", "SOXL"],
        "gap-fade-1":           ["SPY", "QQQ", "IWM"],
        "carry-1":              ["SPY", "QQQ", "DIA"],
        "breakdown-1":          ["SPY", "QQQ", "IWM"],
    }
    pools_tier = {
        "s": ["SPY", "QQQ", "IWM"],
        "m": ["SPY", "QQQ", "XLK", "XLE"],
        "l": ["QQQ", "TQQQ", "NVDA", "BTC/USD"],
    }
    pool = by_tid.get(tid) or pools_tier.get(tier, ["SPY", "QQQ"])
    # tid-hash rotation so a global failure doesn't cluster 7 personas on 1 ticker.
    import hashlib as _hl
    shift = int(_hl.sha1((tid or persona.get("name","?")).encode()).hexdigest()[:4], 16)
    ticker = pool[shift % len(pool)]
    # Only trade if the ticker is in the live quote bus (don't fabricate).
    quotes = ctx.get("quotes") or {}
    if ticker not in quotes:
        # Fall through to SPY (always in universe) as last-resort
        if "SPY" not in quotes:
            return {"action": "pass", "reason": "uniform_fallback_no_quote_available",
                    "provider_status": "fallback_uniform"}
        ticker = "SPY"
    last = (quotes.get(ticker) or {}).get("last") or 0
    if not last:
        return {"action": "pass", "reason": "uniform_fallback_stale_quote",
                "provider_status": "fallback_uniform"}
    # Conservative sizing: 0.5% of the $1k persona bankroll target, 120-min hold,
    # stop 1% under entry, tp 1.5% above. Explicit tag so analytics segregate.
    side = "buy"  # neutral long bias on fallback; vol tier could flip but keep simple
    return {
        "action": "trade",
        "ticker": ticker,
        "side": side,
        "qty_usd": 5.0,
        "max_hold_min": 120,
        "stop_loss_pct": 0.01,
        "take_profit_pct": 0.015,
        "rationale": "UNIFORM_FALLBACK: LLM primary+fallback both failed; tier-rotated liquid ticker per $1M doctrine (silent-pass banned 2026-04-20).",
        "provider_status": "fallback_uniform",
        "_llm_model": persona.get("model_primary", "?"),
        "_llm_routed_via": "fallback_uniform",
    }


# 2026-04-21 user directive: "limite tlutes les 30 seocneds ? que tout soit bien
# optimise pour ca ?" — 30s tick cadence requires per-model timeout ≪ tick length.
# 45s was safe for 5min ticks; with 30s ticks we need ≤10s so a stuck provider
# can't block the whole tick window. Env var for future tuning without redeploy.
_CALL_AGENT_TIMEOUT = float(os.environ.get("ITF_LLM_TIMEOUT", "10.0"))


def _call_agent(persona: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    prompt = _build_prompt(persona, ctx)
    messages = [
        {"role": "system", "content": f"{COLLECTIVE_MISSION}\n\n{AXELROD_CANON}"},
        {"role": "user", "content": prompt},
    ]
    # Try primary then fallback
    for model_key in (persona["model_primary"], persona["model_fallback"]):
        resp = gateway_call(model_key, messages, temperature=0.6, max_tokens=400,
                            fallback_direct=False, timeout=_CALL_AGENT_TIMEOUT)
        text = (resp or {}).get("text") or ""
        parsed = _parse_json(text)
        if parsed:
            parsed["_llm_model"] = resp.get("model_used") or model_key
            parsed["_llm_latency_ms"] = resp.get("latency_ms")
            parsed["_llm_routed_via"] = resp.get("routed_via")
            return parsed
    # 2026-04-20 point #2: ban silent-pass on LLM failure — emit uniform fallback.
    return _uniform_fallback_itf(persona, ctx)


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    s = text.strip()
    # Strip markdown fences if present.
    if s.startswith("```"):
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    # Find first { and last }
    try:
        start = s.index("{")
        end = s.rindex("}") + 1
        return json.loads(s[start:end])
    except Exception:
        return None


# ───────────────────────── Tick loop ─────────────────────────

STATE: Dict[str, Any] = {
    "running": False,
    "last_tick_at": None,
    "tick_count": 0,
    "agents": {p["tid"]: {"decisions": 0, "trades": 0, "passes": 0, "bankroll": 0.0}
               for p in PERSONAS},
}
_stop = threading.Event()
_lock = threading.Lock()
DECISIONS_DIR = _REPO / "data" / "intraday" / "decisions"
DECISIONS_DIR.mkdir(parents=True, exist_ok=True)


def tick_once(dry_print: bool = False) -> List[Dict[str, Any]]:
    """Run one tick: refresh quotes, build context, call all 17 agents, execute."""
    with _lock:
        # 2026-04-22 DIAG — tick_count pinned at 1 observed. Log id(STATE) so we
        # know if different threads/workers see different STATE dicts.
        _pre = STATE["tick_count"]
        STATE["tick_count"] += 1
        STATE["last_tick_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _post = STATE["tick_count"]
    print(f"[itf] tick #{_post} starting "
          f"(pre={_pre} id(STATE)={id(STATE)} thread={threading.get_ident()})",
          file=sys.stderr, flush=True)
    # 2026-04-22 — reconcile any new Alpaca fills FIRST so get_bankroll()
    # returns the real post-fill number when the prompt is built this tick.
    # See project_itf_compound_fix_apr22.md: 232 fills were landing with 0
    # realized PnL credited because there was no broker→ledger path.
    try:
        _rc = executor.reconcile_broker_fills(
            lookback_min=int(os.environ.get("ITF_RECON_LOOKBACK_MIN", "15"))
        )
        if _rc.get("fills_processed", 0) or _rc.get("closes_applied", 0):
            print(f"[itf] fill-reconcile: {_rc}", file=sys.stderr, flush=True)
    except Exception as _rce:
        print(f"[itf] fill-reconcile err (non-fatal): {_rce}", file=sys.stderr, flush=True)
    # 2026-04-28 — every tick, rescale per-agent bankrolls so SUM == alpaca.equity.
    # Cheap (Alpaca account fetch is 30s-cached). Threshold env-tunable; default 2%.
    try:
        _eq_rc = executor.reconcile_fleet_to_alpaca(
            min_drift_pct=float(os.environ.get("ITF_FLEET_RECON_MIN_DRIFT", "0.02")),
            persist=True,
        )
        if _eq_rc.get("applied"):
            print(f"[itf] fleet-equity reconcile: {_eq_rc}",
                  file=sys.stderr, flush=True)
    except Exception as _erc:
        print(f"[itf] fleet-equity reconcile err (non-fatal): {_erc}",
              file=sys.stderr, flush=True)
    # 2026-04-21 — refresh stale broker statuses BEFORE anything else so
    # /api/status + positions.json reflect real fills, not cached pending_new.
    # Addresses user report: "ITF seems slow, orders not moving at all".
    try:
        _bs = executor.refresh_broker_statuses()
        if _bs.get("polled", 0) > 0 or _bs.get("budget_exceeded", 0) > 0:
            print(f"[itf] broker-status refresh: {_bs}", file=sys.stderr, flush=True)
        if _bs.get("budget_exceeded", 0) > 0:
            # 2026-04-22 — surface this so the tick stall RCA is visible. Means
            # positions.json had more non-terminal orders than the Alpaca poll
            # budget allowed. Continuing is SAFE: positions are retried next tick.
            print("[itf] WARN broker-status budget exceeded — non-terminal orders "
                  "carried to next tick", file=sys.stderr, flush=True)
    except Exception as _brs:
        print(f"[itf] broker-status refresh err (non-fatal): {_brs}", file=sys.stderr, flush=True)
    # 2026-04-22 ROUND-2 BP UNLOCK — every 5th tick, sweep stale-losing equity
    # positions (>4h old AND <= -2% unrealized PnL) to free buying power. Without
    # this, open positions pile up until free_bp=$0 and agents correctly pass via
    # bp_guard_free_bp_<$300 even with $49K cash. Crypto skipped (no BP issue).
    # 2026-04-22 SHIP-100%: env-overridable to push ITF deploy 31% → 95%. Defaults
    # tightened from 14400/0.02 to 7200/0.01 — 2h age + 1% loss = 2× faster rotation.
    try:
        if int(STATE.get("tick_count", 0)) % 5 == 0:
            _max_age = int(os.environ.get("ITF_CLOSE_STALE_MAX_AGE_SEC", "7200"))
            _min_loss = float(os.environ.get("ITF_CLOSE_STALE_MIN_LOSS_PCT", "0.01"))
            _sl = executor.close_stale_losers(max_age_sec=_max_age, min_loss_pct=_min_loss)
            if _sl.get("closed", 0) > 0 or _sl.get("errors", 0) > 0 or _sl.get("budget_exceeded", 0) > 0:
                print(f"[itf] stale-loser close (age>{_max_age}s,loss<={-_min_loss:+.1%}): {_sl}", file=sys.stderr, flush=True)
    except Exception as _sle:
        print(f"[itf] stale-loser close FAIL: {_sle}", file=sys.stderr, flush=True)
    # 2026-04-22 ROUND-3 ORDER-PILEUP — every 10th tick, cancel Alpaca open orders
    # >30 min old. Incident: 319 pending brackets piled up, drained
    # daytrading_buying_power from $157K → $246 on $101K equity. The dedup
    # guard in executor.submit() prevents NEW pileups; this sweep unwinds any
    # that slipped through (drifted limit price, partial fills stuck open, etc).
    try:
        if int(STATE.get("tick_count", 0)) % 10 == 0:
            _cs = executor.cancel_stale_pending()
            if _cs.get("cancelled", 0) > 0 or _cs.get("errors", 0) > 0 or _cs.get("budget_exceeded", 0) > 0:
                print(f"[itf] cancel-stale-pending: {_cs}", file=sys.stderr, flush=True)
    except Exception as _cse:
        print(f"[itf] cancel-stale-pending FAIL: {_cse}", file=sys.stderr, flush=True)
    # v2.5 — ensure sub-bankrolls are seeded (idempotent) and sync each into STATE.
    try:
        executor.seed_bankrolls([p["tid"] for p in PERSONAS])
        for p in PERSONAS:
            STATE["agents"].setdefault(p["tid"], {
                "decisions": 0, "trades": 0, "passes": 0, "bankroll": 0.0,
            })
            STATE["agents"][p["tid"]]["bankroll"] = executor.get_bankroll(p["tid"])
    except Exception as _se:
        print(f"[itf] bankroll sync err (non-fatal): {_se}", file=sys.stderr, flush=True)
    quote_refresh()  # persist snapshot
    ctx = build_intraday_context()
    # 2026-04-21 proposal #3 — attach regime snapshot so prompt + downstream logic
    # can waive ≥3-trade + MIN_DEPLOY when crypto tape is dead.
    try:
        ctx["regime"] = _compute_crypto_regime(ctx.get("quotes") or {})
        if ctx["regime"].get("low_vol_regime"):
            print(f"[itf] LOW-VOL REGIME active: median_5m_vol="
                  f"{ctx['regime'].get('median_realized_vol')} < floor "
                  f"{ctx['regime'].get('floor')} — ≥3/MIN_DEPLOY waived this tick",
                  file=sys.stderr, flush=True)
    except Exception as _re:
        print(f"[itf] regime compute err (non-fatal): {_re}", file=sys.stderr, flush=True)
        ctx["regime"] = {"low_vol_regime": False, "floor": REGIME_FLOOR_5M}
    results: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # 2026-04-20 AGGRESSIVE-MODE: milestone council at days 15/30/45/... Run max 1×/day.
    try:
        day_idx = _current_day_idx()
        latest = _latest_council_plan()
        latest_idx = int((latest or {}).get("day_idx", -99))
        if day_idx > 0 and day_idx % COUNCIL_INTERVAL_DAYS == 0 and latest_idx != day_idx:
            fleet_board = []
            for p in PERSONAS:
                s = STATE["agents"].get(p["tid"], {})
                fleet_board.append({
                    "tid": p["tid"], "tier": p["tier"],
                    "trades": s.get("trades", 0), "passes": s.get("passes", 0),
                    "total_pnl_usd": 0.0, "open_positions": 0,
                })
            plan = run_milestone_council(fleet_board, ctx, day_idx)
            if plan:
                print(f"[itf] milestone council day {day_idx}: "
                      f"{(plan.get('council_summary') or '')[:120]}",
                      file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[itf] council scheduler err (non-fatal): {e}", file=sys.stderr, flush=True)

    # EOD flatten before new entries — mark-to-market using current quote bus.
    def _q(ticker: str):
        q = (ctx.get("quotes") or {}).get(ticker) or {}
        return q.get("last")
    executor.close_expired(now, quote_fn=_q)

    # 2026-04-22 — close any Kalshi/Poly position whose market close_ts has passed.
    try:
        _ev_closed = ev.expire_stale(now)
        if _ev_closed:
            print(f"[itf] event-markets expired {_ev_closed} stale positions",
                  file=sys.stderr, flush=True)
    except Exception as _ee:
        print(f"[itf] event expire err: {_ee}", file=sys.stderr, flush=True)

    # 2026-04-21 BP GUARD — fetch free Alpaca buying power once per tick so bracket
    # submits downsize or pass when margin is exhausted. Observed 2026-04-21: 53
    # orders stuck in "new" status because BP=$238 after 57 daytrades. Guard caps
    # new-open stakes to min(raw, $400) and forces pass when BP<$300. Safe fallback
    # on API error so dry-run keeps working.
    _free_bp = float("inf")
    try:
        if executor.live_mode():
            import requests as _req
            _k = os.environ.get("ALPACA_PAPER_KEY", "")
            _s = os.environ.get("ALPACA_PAPER_SECRET", "")
            if _k and _s:
                _r = _req.get(
                    "https://paper-api.alpaca.markets/v2/account",
                    headers={"APCA-API-KEY-ID": _k, "APCA-API-SECRET-KEY": _s},
                    timeout=5,
                )
                if _r.ok:
                    _free_bp = float(_r.json().get("buying_power") or 0.0)
    except Exception as _e:
        print(f"[itf] BP fetch err (non-fatal, cap defaults to inf): {_e}", file=sys.stderr, flush=True)

    # 2026-04-20 ANTI-LOCKSTEP guardrail — cap agents per (ticker,side) at MAX_CONCURRENT_PER_KEY.
    # GLOBAL (not per-tick): seed from executor's existing open positions so cross-tick
    # accumulation also caps out. Without this, 2 ticks of 2 AVAX-longs each = 4 AVAX-longs.
    # Fair-order randomization so early-called personas don't monopolize the edge.
    import random as _random
    MAX_CONCURRENT_PER_KEY = 4  # 2026-04-21 aggression push: 3→4 concurrent agents per (ticker,side)
    SUBMITS_PER_TICK = 3  # 2026-04-21 aggression push: 2→3 new orders per agent per tick (compute still OK — 17×3=51/tick)
    _submits_this_tick: Dict[str, int] = {}
    _tick_counts: Dict[Tuple[str, str], int] = {}
    try:
        _existing_positions = executor._load_positions()
        for _agent_id, _plist in (_existing_positions or {}).items():
            for _p in (_plist or []):
                if _p.get("status") != "open":
                    continue
                _t = _p.get("ticker") or _p.get("underlying")
                _s = _p.get("side") or _p.get("option_type")
                if _t and _s:
                    _tick_counts[(_t, _s)] = _tick_counts.get((_t, _s), 0) + 1
    except Exception as _e:
        print(f"[itf] anti-lockstep seed failed (non-fatal): {_e}", file=sys.stderr, flush=True)
    _personas_this_tick = list(PERSONAS)
    _random.shuffle(_personas_this_tick)

    # Divert ticker pools — when anti-lockstep blocks a persona, rotate through
    # these in order until one is uncrowded. Keeps all 14 agents trading instead
    # of 5 silent-passing every tick (observed 2026-04-20: 70/75 passes on
    # momentum-1/breakout-1/pairs-1/vol-1/macro-rotate-1 were anti-lockstep
    # forced to pass, not LLM choice). Pool = persona's uniform_fallback pool + crypto.
    _DIVERT_POOLS = {
        "scalper-1":            ["QQQ", "IWM", "DIA", "XLK", "BTC/USD"],
        "momentum-1":           ["XLK", "XLE", "XLF", "XLV", "XLY", "ETH/USD"],
        "mean-rev-1":           ["XLV", "XLP", "XLU", "XLRE", "SOL/USD"],
        "breakout-1":           ["TSLA", "AMD", "COIN", "SMCI", "LINK/USD"],
        "pairs-1":              ["XLU", "XLB", "XLC", "XLI", "DOGE/USD"],
        "vol-1":                ["VXX", "UVXY", "TLT", "GLD", "BTC/USD"],
        "options-1":            ["SPY", "QQQ", "IWM"],
        "arbitrage-1":          ["IWM", "DIA", "XLK", "XLE", "ETH/USD"],
        "news-catalyst-1":      ["NVDA", "COIN", "SMCI", "AMD", "BTC/USD"],
        "crypto-whale-1":       ["ETH/USD", "SOL/USD", "LINK/USD", "AVAX/USD", "DOGE/USD", "BTC/USD"],
        "earnings-gap-1":       ["NVDA", "AMD", "META", "GOOGL", "AAPL"],
        "iv-crush-1":           ["SPY", "QQQ", "IWM"],
        "macro-rotate-1":       ["GLD", "TLT", "UUP", "XLU", "SHY"],
        "leveraged-momentum-1": ["SPXL", "SOXL", "TNA", "UPRO", "BTC/USD"],
        "gap-fade-1":           ["SPY", "QQQ", "IWM", "DIA", "XLK"],
        "carry-1":              ["SPY", "QQQ", "IWM", "DIA", "XLV"],
        "breakdown-1":          ["SPY", "QQQ", "IWM", "TQQQ", "SPXL"],
    }

    def _divert(tid: str, original_ticker: str, original_side: str) -> Optional[str]:
        """Find first ticker in persona's divert pool that (a) is in quotes,
        (b) isn't at MAX_CONCURRENT_PER_KEY for this side. Returns None if all taken."""
        pool = _DIVERT_POOLS.get(tid, [])
        quotes = ctx.get("quotes") or {}
        for cand in pool:
            if cand == original_ticker:
                continue
            if cand not in quotes:
                continue
            if _tick_counts.get((cand, original_side), 0) < MAX_CONCURRENT_PER_KEY:
                return cand
        return None

    # 2026-04-21 PARALLEL LLM CALLS — sequential 17× _call_agent at 10s each = 170s
    # worst case, incompatible with 30s tick cadence. Fan out to ThreadPoolExecutor
    # so all 17 personas call their gateway concurrently; wall-clock ≈ slowest call.
    # Post-processing (anti-lockstep/broker) stays sequential to avoid broker races.
    from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _ac
    _decisions_by_tid: Dict[str, Dict[str, Any]] = {}
    _call_budget = float(os.environ.get("ITF_TICK_BUDGET_SEC", "25.0"))
    with _TPE(max_workers=len(_personas_this_tick)) as _pool:
        _futs = {_pool.submit(_call_agent, p, ctx): p for p in _personas_this_tick}
        for _fut in _ac(_futs, timeout=_call_budget + 5):
            _p = _futs[_fut]
            try:
                _decisions_by_tid[_p["tid"]] = _fut.result(timeout=_call_budget)
            except Exception as _ce:
                print(f"[itf] _call_agent raised for {_p['tid']}: {_ce} — "
                      f"uniform fallback", file=sys.stderr, flush=True)
                _decisions_by_tid[_p["tid"]] = _uniform_fallback_itf(_p, ctx)

    for persona in _personas_this_tick:
        # 2026-04-21 compute cap — if agent already submitted SUBMITS_PER_TICK
        # orders in THIS tick, skip the LLM call entirely (saves $, prevents
        # lockstep spamming). Ledger event for scientific audit.
        if _submits_this_tick.get(persona["tid"], 0) >= SUBMITS_PER_TICK:
            try:
                executor._append_ledger({
                    "tid": persona["tid"],
                    "event": "skip_compute_cap",
                    "tick": STATE.get("tick_count"),
                    "cap": SUBMITS_PER_TICK,
                })
            except Exception:
                pass
            STATE["agents"][persona["tid"]]["passes"] += 1
            results.append({
                "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "agent_tid": persona["tid"],
                "agent_name": persona["name"],
                "tier": persona["tier"],
                "decision": {"action": "pass", "reason": f"compute_cap_{SUBMITS_PER_TICK}_submits_reached"},
            })
            continue
        # LLM call already happened in parallel — just pick up the decision.
        decision = _decisions_by_tid.get(persona["tid"]) or _uniform_fallback_itf(persona, ctx)
        action = decision.get("action")
        # 2026-04-21 CLOSE ACTION — agent can free BP by closing one of its open
        # positions; bypasses anti-lockstep/BP checks (closing always fine).
        if action == "close":
            close_ticker = decision.get("ticker")
            if close_ticker:
                try:
                    close_entry = executor.close_position(persona["tid"], close_ticker)
                    result = {
                        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "agent_tid": persona["tid"],
                        "agent_name": persona["name"],
                        "tier": persona["tier"],
                        "decision": decision,
                        "execution": close_entry,
                    }
                    STATE["agents"][persona["tid"]]["decisions"] += 1
                    STATE["agents"][persona["tid"]]["trades"] += 1
                    results.append(result)
                    continue
                except Exception as _ce:
                    print(f"[itf] close err {persona['tid']} {close_ticker}: {_ce}",
                          file=sys.stderr, flush=True)
                    # fall through to pass
                    decision = {"action": "pass", "reason": f"close_failed: {_ce}"}
                    action = "pass"
        # Anti-lockstep post-filter WITH DIVERT (2026-04-20 v2)
        if action == "trade":
            _key = (decision.get("ticker", "?"), decision.get("side", "?"))
            if _tick_counts.get(_key, 0) >= MAX_CONCURRENT_PER_KEY:
                alt = _divert(persona["tid"], _key[0], _key[1])
                if alt:
                    decision = dict(decision)
                    decision["ticker"] = alt
                    decision["_diverted_from"] = _key[0]
                    decision["rationale"] = (decision.get("rationale") or decision.get("thesis") or "") + \
                        f" [DIVERT: {_key[0]} crowded → {alt}]"
                    _key = (alt, _key[1])
                    _tick_counts[_key] = _tick_counts.get(_key, 0) + 1
                else:
                    decision = {
                        "action": "pass",
                        "reason": f"anti_lockstep: {_key[0]} {_key[1]} crowded + divert pool exhausted",
                        "_original_ticker": _key[0],
                        "_original_side": _key[1],
                    }
                    action = "pass"
            else:
                _tick_counts[_key] = _tick_counts.get(_key, 0) + 1
        elif action == "option_trade":
            _key = (decision.get("underlying", "?"), decision.get("option_type", "?"))
            if _tick_counts.get(_key, 0) >= MAX_CONCURRENT_PER_KEY:
                alt = _divert(persona["tid"], _key[0], _key[1])
                if alt and "/" not in alt:  # options only on equities/ETFs
                    decision = dict(decision)
                    decision["underlying"] = alt
                    decision["_diverted_from"] = _key[0]
                    _key = (alt, _key[1])
                    _tick_counts[_key] = _tick_counts.get(_key, 0) + 1
                else:
                    decision = {
                        "action": "pass",
                        "reason": f"anti_lockstep: {_key[0]} {_key[1]}-options crowded + divert pool exhausted",
                        "_original_underlying": _key[0],
                    }
                    action = "pass"
            else:
                _tick_counts[_key] = _tick_counts.get(_key, 0) + 1

        # 2026-04-26 — STRIPPED: POWER-DEPLOY FLOOR removed. Agent's chosen stake
        # stands; only Kelly cap + bankroll floor are enforced server-side downstream.

        # 2026-04-26 — POL CROSS-POLLINATION 1.5× stake multiplier.
        # When agent's chosen ticker matches a POL signal (Form-4 insider cluster
        # ≥3 OR Congress trade), apply 1.5× stake. Sector ETFs of POL-signaled
        # sector also qualify. This is what made POL agents qwen-quant +275% /
        # llama-contra +100% — same signal class, applied to live Alpaca paper.
        # 2026-04-26 PM FIX: re-derive pol_signaled from ctx (was scope-leaking
        # crash since pol_signaled is local to _build_prompt).
        if action in ("trade", "option_trade"):
            _pol_hot = ctx.get("pol_engine_hot") or {}
            _pol_signaled_set = set()
            for _c in (_pol_hot.get("cat6_form4_clusters") or {}).get("clusters", [])[:10]:
                if _c.get("tkr"): _pol_signaled_set.add(_c["tkr"])
            for _t in (_pol_hot.get("cat24_congress") or {}).get("trades", [])[:10]:
                if _t.get("tkr"): _pol_signaled_set.add(_t["tkr"])
            _tk = (decision.get("ticker") or decision.get("underlying") or "").upper()
            _ticker_to_sector_etf = {
                # tech
                'AAPL':'XLK','MSFT':'XLK','GOOG':'XLK','GOOGL':'XLK','META':'XLK',
                'NVDA':'XLK','AMD':'XLK','MU':'XLK','AMZN':'XLY','AVGO':'XLK',
                'CRM':'XLK','ORCL':'XLK',
                # financials
                'JPM':'XLF','GS':'XLF','MS':'XLF','BAC':'XLF','WFC':'XLF','C':'XLF',
                # energy
                'COP':'XLE','XOM':'XLE','CVX':'XLE','SLB':'XLE','EOG':'XLE',
                # healthcare
                'UNH':'XLV','PFE':'XLV','LLY':'XLV','JNJ':'XLV',
                # consumer
                'WMT':'XLY','HD':'XLY','MCD':'XLY','NKE':'XLY','TSLA':'XLY',
            }
            _signal_match = False
            _signal_reason = ""
            if _tk in _pol_signaled_set:
                _signal_match = True
                _signal_reason = f"direct POL signal on {_tk}"
            elif _tk in ('XLE','XLK','XLF','XLV','XLY','XLP','XLI','XLU'):
                # Sector ETF — match if any POL-signaled ticker maps to this sector
                _matched_tickers = [t for t in _pol_signaled_set if _ticker_to_sector_etf.get(t) == _tk]
                if _matched_tickers:
                    _signal_match = True
                    _signal_reason = f"sector ETF {_tk} aggregates POL signals on {','.join(_matched_tickers[:3])}"
            if _signal_match:
                _orig_stake = float(decision.get("stake_usd") or 0)
                if _orig_stake > 0:
                    decision = dict(decision)
                    decision["stake_usd"] = round(_orig_stake * 1.5, 2)
                    decision["_pol_signal_bonus"] = _signal_reason
                    decision["thesis"] = (
                        f"[POL-SIGNAL 1.5×: {_signal_reason}] "
                        f"{decision.get('thesis', '')[:300]}"
                    )

        result = {
            "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_tid": persona["tid"],
            "agent_name": persona["name"],
            "tier": persona["tier"],
            "decision": decision,
        }
        STATE["agents"][persona["tid"]]["decisions"] += 1
        # 2026-04-21 v2.6 — UNRESTRICTED UNIVERSE: if agent emits a ticker not in
        # the ~110-deep quote bus, fetch its last price from Alpaca on demand.
        # This unlocks the full 10k+ US equity universe + 30+ crypto pairs + any
        # listed option, per the UNRESTRICTED UNIVERSE clause in DECISION_SCHEMA.
        if action == "trade" and decision.get("ticker") and decision["ticker"] not in (ctx.get("quotes") or {}):
            try:
                _odq = _ondemand_quote(decision["ticker"])
                if _odq and _odq.get("last"):
                    ctx.setdefault("quotes", {})[decision["ticker"]] = _odq
                    print(f"[itf] ondemand_quote ok {decision['ticker']}=${_odq['last']}", file=sys.stderr, flush=True)
            except Exception as _qe:
                print(f"[itf] ondemand_quote err {decision['ticker']}: {_qe}", file=sys.stderr, flush=True)
        if action == "trade" and decision.get("ticker") in (ctx.get("quotes") or {}):
            last_quote = (ctx["quotes"][decision["ticker"]] or {}).get("last") or 0
            raw_stake = float(decision.get("stake_usd", 500) or 500)
            _ticker_is_crypto = "/" in decision["ticker"]
            # 2026-04-21 BP-AWARE CAP — equities: cap stake at min(raw, $400) and
            # force pass if free BP<$300. Crypto untouched (uses cash, not margin).
            if not _ticker_is_crypto and _free_bp != float("inf"):
                if _free_bp < 300.0:
                    decision = {"action": "pass", "reason": f"bp_guard_free_bp=${_free_bp:.0f}_lt_300",
                                "_original_ticker": decision.get("ticker")}
                    action = "pass"
                    STATE["agents"][persona["tid"]]["decisions"] += 1
                    STATE["agents"][persona["tid"]]["passes"] += 1
                    result["decision"] = decision
                    results.append(result)
                    continue
                else:
                    # 2026-04-26 — STRIPPED: no automatic 3x leveraged ETF routing.
                    # Agent's chosen ticker stands. Bankroll cap enforced server-side.
                    # 2026-04-28 MAX_AGGRO — equity per-trade ceiling lifts $2.5K → $7.5K.
                    _eq_cap = 7500.0 if os.environ.get("ITF_MAX_AGGRO") == "1" else 2500.0
                    raw_stake = min(raw_stake, _eq_cap)
            order = {
                "ticker": decision["ticker"],
                "side": decision.get("side", "long"),
                "stake_usd": max(100.0, raw_stake),
                "stop_pct": min(0.03, max(0.001, float(decision.get("stop_pct", 0.005) or 0.005))),
                "take_profit_pct": min(0.08, max(0.002, float(decision.get("take_profit_pct", 0.012) or 0.012))),
                "thesis": decision.get("thesis", ""),
            }
            entry = executor.submit(persona["tid"], order, last_quote)
            result["execution"] = entry
            STATE["agents"][persona["tid"]]["trades"] += 1
            _submits_this_tick[persona["tid"]] = _submits_this_tick.get(persona["tid"], 0) + 1
        elif action == "option_trade" and decision.get("underlying") in (ctx.get("quotes") or {}):
            last_quote = (ctx["quotes"][decision["underlying"]] or {}).get("last") or 0
            option_order = {
                "underlying": decision["underlying"],
                "option_type": decision.get("option_type", "call"),
                "strategy":    decision.get("strategy", "long"),
                "dte":         int(decision.get("dte", 0) or 0),
                "strike_offset_pct": float(decision.get("strike_offset_pct", 0.0) or 0.0),
                "wing_width_pct":    float(decision.get("wing_width_pct", 0.01) or 0.01),
                "stake_usd":   min(10000 if os.environ.get("ITF_MAX_AGGRO") == "1" else 5000, max(200, float(decision.get("stake_usd", 500) or 500))),
                "max_loss_pct":min(0.05, max(0.005, float(decision.get("max_loss_pct", 0.02) or 0.02))),
                "thesis":      decision.get("thesis", ""),
            }
            entry = executor.submit_option(persona["tid"], option_order, last_quote)
            result["execution"] = entry
            STATE["agents"][persona["tid"]]["trades"] += 1
            _submits_this_tick[persona["tid"]] = _submits_this_tick.get(persona["tid"], 0) + 1
        elif action == "event_trade":
            # 2026-04-22 binary event-market paper-trade (Kalshi + Polymarket).
            # 24/7 asset class — not gated by equity hours. Per-agent stake cap =
            # min($1500, 5% of agent bankroll) so one pick can't blow the pot.
            _venue = (decision.get("venue") or "").lower()
            _mid = decision.get("market_id")
            _side = (decision.get("side") or "").lower()
            if _venue not in ("kalshi", "polymarket") or not _mid or _side not in ("yes", "no"):
                STATE["agents"][persona["tid"]]["passes"] += 1
                result["execution"] = {"status": "error",
                                       "reason": f"bad event_trade: venue={_venue} mid={_mid} side={_side}"}
            else:
                _agent_bk = executor.get_bankroll(persona["tid"])
                _raw_stake = float(decision.get("stake_usd", 25) or 25)
                _cap = min(1500.0, _agent_bk * 0.05)
                _stake = max(5.0, min(_raw_stake, _cap))
                entry = ev.place_paper_order(
                    agent_tid=persona["tid"],
                    venue=_venue,
                    market_id=_mid,
                    side=_side,
                    size_usd=_stake,
                    thesis=decision.get("thesis", ""),
                )
                result["execution"] = entry
                STATE["agents"][persona["tid"]]["trades"] += 1
                _submits_this_tick[persona["tid"]] = _submits_this_tick.get(persona["tid"], 0) + 1
        else:
            STATE["agents"][persona["tid"]]["passes"] += 1
        results.append(result)
        if dry_print:
            print(json.dumps(result, indent=2, default=str))
            print("-" * 72)

    print(f"[itf] tick #{STATE['tick_count']} done — {len(results)} decisions", file=sys.stderr, flush=True)

    # Persist day log
    day = now.strftime("%Y-%m-%d")
    day_path = DECISIONS_DIR / f"{day}.jsonl"
    with day_path.open("a") as fh:
        for r in results:
            fh.write(json.dumps(r, default=str) + "\n")

    # 2026-04-22 — HF-persist the 4 ledger files (positions, bankrolls, cursor,
    # ledger jsonl) so a factory_reboot replays state. Gated by _LEDGER_DIRTY
    # in executor: no Hub round-trip on a no-mutation tick. Silent on outage —
    # never let Hub problems kill a live tick.
    try:
        _lp = executor.persist_ledgers_to_hub()
        if _lp.get("uploaded"):
            print(f"[itf] hub-persist uploaded={_lp['uploaded']}",
                  file=sys.stderr, flush=True)
        elif _lp.get("errors"):
            print(f"[itf] hub-persist errors={_lp['errors']}",
                  file=sys.stderr, flush=True)
    except Exception as _lpe:
        print(f"[itf] hub-persist err (non-fatal): {_lpe}",
              file=sys.stderr, flush=True)

    return results


def _is_equity_hours(now_utc: datetime) -> bool:
    """US equities extended hours: weekdays 08:00-24:00 UTC (04:00 ET pre-market - 20:00 ET after-hours)."""
    if now_utc.weekday() >= 5:
        return False
    return 8 <= now_utc.hour < 24


def _is_tradeable_now(asset_class: str, now_utc: datetime) -> bool:
    """Crypto is 24/7. Equities are extended-hours only."""
    if asset_class == "crypto":
        return True
    return _is_equity_hours(now_utc)


def _is_market_hours(now_utc: datetime) -> bool:
    """Back-compat alias — tick_loop uses this to decide whether to skip.
    Returns True if ANY asset class is currently tradeable (crypto is 24/7 → always True
    for Alpaca-live mode, equity-hours fallback otherwise)."""
    if live_mode_any_crypto():
        return True
    return _is_equity_hours(now_utc)


def live_mode_any_crypto() -> bool:
    """True when Alpaca crypto is reachable — crypto is always tradeable."""
    return bool(os.environ.get("ALPACA_PAPER_KEY") and os.environ.get("ALPACA_PAPER_SECRET"))


def tick_loop(interval_sec: int = int(os.environ.get("ITF_TICK_SEC", "300"))) -> None:
    STATE["running"] = True
    _stop.clear()
    while not _stop.is_set():
        now = datetime.now(timezone.utc)
        if _is_market_hours(now):
            try:
                tick_once()
            except Exception as e:
                import traceback
                print(f"[itf] tick failed: {e}", file=sys.stderr, flush=True)
                traceback.print_exc(file=sys.stderr)
        else:
            print(f"[itf] market closed at {now.isoformat()} — skipping tick", file=sys.stderr, flush=True)
        time.sleep(interval_sec)
    STATE["running"] = False


# ───────────────────────── FastAPI ─────────────────────────

def _build_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    app = FastAPI(title="Nomos42 ITF")

    @app.get("/api/status")
    def api_status():
        # 2026-04-28 — Alpaca truth on every status reply so dashboards never
        # disagree with the broker. Cached 30s in executor.fetch_alpaca_account.
        try:
            acct = executor.fetch_alpaca_account()
        except Exception as _e:
            acct = {}
        cash = executor.all_bankrolls()
        # Total equity = available cash + reserved on open positions (matches
        # /api/bankrolls.fleet_equity_internal). Comparing Alpaca's total-equity
        # against agent available alone would always overstate drift.
        _open = executor._load_positions() or {}
        _reserved_total = 0.0
        for _tid, _plist in _open.items():
            for _pos in (_plist or []):
                if _pos.get("status") == "open":
                    _reserved_total += float(_pos.get("stake_usd") or 0.0)
        internal_available = round(sum(float(v or 0.0) for v in cash.values()), 2)
        internal_total = round(internal_available + _reserved_total, 2)
        alpaca_equity = float(acct.get("equity") or 0.0)
        drift = round(alpaca_equity - internal_total, 2) if alpaca_equity > 0 else None
        return JSONResponse({
            "running": STATE["running"],
            "last_tick_at": STATE["last_tick_at"],
            "tick_count": STATE["tick_count"],
            "mode": "live" if executor.live_mode() else "dry_run",
            "agents": STATE["agents"],
            "config_agents": PERSONAS,
            "quote_source": (quote_latest() or {}).get("_source"),
            "alpaca": {
                "equity": acct.get("equity"),
                "cash": acct.get("cash"),
                "buying_power": acct.get("buying_power"),
                "long_market_value": acct.get("long_market_value"),
                "short_market_value": acct.get("short_market_value"),
                "daytrade_count": acct.get("daytrade_count"),
                "pattern_day_trader": acct.get("pattern_day_trader"),
                "fetched_at": acct.get("fetched_at"),
            } if acct else None,
            "fleet_internal_total_usd": internal_total,
            "fleet_internal_available_usd": internal_available,
            "fleet_internal_reserved_usd": round(_reserved_total, 2),
            "fleet_drift_vs_alpaca_usd": drift,
            # 2026-04-22 DIAG — tick_count pin RCA. If reader and writer see
            # different id(STATE) → different processes → single-worker premise wrong.
            "_diag_state_id": id(STATE),
            "_diag_reader_thread": threading.get_ident(),
            "_diag_pid": os.getpid(),
        })

    @app.post("/api/run")
    async def api_run(request: Request):
        if STATE["running"]:
            return JSONResponse({"error": "already running"}, status_code=409)
        threading.Thread(target=tick_loop, daemon=True).start()
        return JSONResponse({"started": True})

    @app.post("/api/stop")
    def api_stop():
        _stop.set()
        return JSONResponse({"stopping": True})

    @app.get("/api/positions")
    def api_positions():
        return JSONResponse({"open": executor.list_open()})

    @app.get("/api/events")
    def api_events():
        """Kalshi + Polymarket paper ledger — open positions, mark-to-market,
        realized P&L. Dashboard uses this to surface the binary-event panel.
        """
        try:
            ledger = ev.load_positions() or {}
            all_pos: List[Dict[str, Any]] = []
            fleet_unrealized = 0.0
            fleet_realized = 0.0
            for tid, rows in ledger.items():
                for p in rows:
                    all_pos.append({**p, "agent_tid": tid})
                mtm = ev.mark_to_market(tid)
                fleet_unrealized += float(mtm.get("unrealized_pnl") or 0)
                fleet_realized += ev.realized_pnl(tid)
            open_rows = [p for p in all_pos if p.get("status") == "open"]
            closed_rows = [p for p in all_pos if p.get("status") == "closed"]
            # Cache 60s of live top-markets as well so the dashboard can render
            # the board even without a separate Kalshi/Poly fetch.
            try:
                kalshi_top = ev.list_markets("kalshi", limit=8)
            except Exception:
                kalshi_top = []
            try:
                poly_top = ev.list_markets("polymarket", limit=8)
            except Exception:
                poly_top = []
            return JSONResponse({
                "open_positions": open_rows,
                "closed_positions": closed_rows[-50:],  # recent tail only
                "fleet_unrealized_pnl": round(fleet_unrealized, 2),
                "fleet_realized_pnl": round(fleet_realized, 2),
                "venues": {
                    "kalshi_top": kalshi_top,
                    "polymarket_top": poly_top,
                },
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
        except Exception as e:
            return JSONResponse({"error": str(e)[:200], "open_positions": []}, status_code=200)

    @app.get("/api/decisions")
    def api_decisions(date: Optional[str] = None):
        day = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        p = DECISIONS_DIR / f"{day}.jsonl"
        if not p.exists():
            return JSONResponse({"date": day, "decisions": []})
        rows = []
        for line in p.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return JSONResponse({"date": day, "decisions": rows})

    @app.get("/api/leaderboard")
    def api_leaderboard():
        opens = executor.list_open()
        # Mark-to-market via the most recent quote snapshot (no LLM call here).
        snap = quote_latest() or {}
        quotes = snap.get("quotes") or {}
        def _q(ticker: str):
            return (quotes.get(ticker) or {}).get("last")
        pnl = executor.pnl_snapshot(quote_fn=_q)
        per_agent = pnl.get("per_agent", {})
        board = []
        for p in PERSONAS:
            tid = p["tid"]
            agent_open = [o for o in opens if o.get("agent_tid") == tid]
            s = STATE["agents"][tid]
            ag = per_agent.get(tid, {})
            board.append({
                "tid": tid, "name": p["name"], "tier": p["tier"],
                "decisions": s["decisions"], "trades": s["trades"], "passes": s["passes"],
                "open_positions": len(agent_open),
                "bankroll_usd": round(executor.get_bankroll(tid), 2),
                "realized_pnl_usd": ag.get("realized_pnl_usd", 0.0),
                "unrealized_pnl_usd": ag.get("unrealized_pnl_usd", 0.0),
                "total_pnl_usd": ag.get("total_pnl_usd", 0.0),
                "trades_closed": ag.get("trades_closed", 0),
                "win_rate": ag.get("win_rate", 0.0),
            })
        # Sort by total_pnl_usd desc
        board.sort(key=lambda r: r["total_pnl_usd"], reverse=True)
        for i, r in enumerate(board, 1):
            r["rank"] = i
        return JSONResponse({
            "agents": board,
            "fleet_realized_pnl_usd": pnl.get("fleet_realized_pnl_usd", 0.0),
            "fleet_unrealized_pnl_usd": pnl.get("fleet_unrealized_pnl_usd", 0.0),
            "fleet_total_pnl_usd": pnl.get("fleet_total_pnl_usd", 0.0),
        })

    @app.get("/api/pnl")
    def api_pnl():
        snap = quote_latest() or {}
        quotes = snap.get("quotes") or {}
        def _q(ticker: str):
            return (quotes.get(ticker) or {}).get("last")
        return JSONResponse(executor.pnl_snapshot(quote_fn=_q))

    @app.get("/api/trades")
    def api_trades(limit: int = 200):
        trades = executor.read_trades(limit=limit)
        return JSONResponse({"count": len(trades), "trades": trades})

    @app.get("/api/bankrolls")
    def api_bankrolls(reconcile: bool = False):
        """Honest accounting — per-agent + fleet, anchored to Alpaca truth.
          available    = free cash in agent's sub-bankroll (after reserves)
          reserved     = sum of stake_usd on that agent's OPEN positions
          total_equity = available + reserved
          llm_tag      = underlying LLM this persona routes to (for cross-TF
                         LLM leaderboard comparison with NBA/POL)

        2026-04-28 reconciliation contract: every reply ALSO returns the live
        Alpaca account snapshot (`alpaca_truth`) and `fleet_drift_vs_alpaca_usd`.
        Pass `?reconcile=true` to persistently rescale the per-agent ledger so
        SUM(agent.equity) ≡ alpaca.equity (drift > 2%); the rescaled view is
        what's returned. Without that flag the response is read-only.
        """
        if reconcile:
            try:
                executor.reconcile_fleet_to_alpaca(min_drift_pct=0.02, persist=True)
            except Exception as _e:
                print(f"[itf] reconcile_fleet_to_alpaca err: {_e}",
                      file=sys.stderr, flush=True)
        cash = executor.all_bankrolls()  # {tid: available_float}
        positions = executor._load_positions()
        reserved_by_tid: Dict[str, float] = {}
        for tid, plist in (positions or {}).items():
            for pos in (plist or []):
                if pos.get("status") != "open":
                    continue
                reserved_by_tid[tid] = reserved_by_tid.get(tid, 0.0) + float(pos.get("stake_usd") or 0)
        agents: Dict[str, Dict[str, float]] = {}
        for tid, avail in cash.items():
            reserved = round(reserved_by_tid.get(tid, 0.0), 2)
            # Look up underlying LLM from personas registry so cross-TF
            # comparison (tf_cross_llm_view.py) can attribute PnL per model.
            persona = get_persona(tid) or {}
            agents[tid] = {
                "available": round(float(avail or 0.0), 2),
                "reserved_open": reserved,
                "total_equity": round(float(avail or 0.0) + reserved, 2),
                "llm_tag": persona.get("model_primary") or "unknown",
                "llm_fallback": persona.get("model_fallback") or None,
            }
        fleet_available = round(sum(a["available"] for a in agents.values()), 2)
        fleet_reserved = round(sum(a["reserved_open"] for a in agents.values()), 2)
        fleet_equity_internal = round(fleet_available + fleet_reserved, 2)
        try:
            acct = executor.fetch_alpaca_account()
        except Exception:
            acct = {}
        alpaca_equity = float(acct.get("equity") or 0.0)
        drift = round(alpaca_equity - fleet_equity_internal, 2) if alpaca_equity > 0 else None
        return JSONResponse({
            "fleet_available": fleet_available,
            "fleet_reserved": fleet_reserved,
            "fleet_equity": fleet_equity_internal,
            "fleet_equity_internal": fleet_equity_internal,
            "fleet_equity_alpaca": acct.get("equity"),
            "fleet_drift_vs_alpaca_usd": drift,
            "alpaca_truth": {
                "equity": acct.get("equity"),
                "cash": acct.get("cash"),
                "buying_power": acct.get("buying_power"),
                "long_market_value": acct.get("long_market_value"),
                "short_market_value": acct.get("short_market_value"),
                "daytrade_count": acct.get("daytrade_count"),
                "pattern_day_trader": acct.get("pattern_day_trader"),
                "fetched_at": acct.get("fetched_at"),
            } if acct else None,
            "agents": agents,
            "meta": executor._load_bankrolls().get("_meta", {}),
        })

    @app.get("/api/llm-leaderboard")
    def api_llm_leaderboard():
        """Roll-up by underlying LLM — shows which MODEL ships best on ITF.
        Parallel to /api/leaderboard on NBA/POL (strategy-name there; here
        the strategy wraps an LLM so we aggregate at the LLM level)."""
        cash = executor.all_bankrolls()
        positions = executor._load_positions()
        reserved_by_tid: Dict[str, float] = {}
        for tid, plist in (positions or {}).items():
            for pos in (plist or []):
                if pos.get("status") != "open":
                    continue
                reserved_by_tid[tid] = reserved_by_tid.get(tid, 0.0) + float(pos.get("stake_usd") or 0)
        by_llm: Dict[str, Dict[str, Any]] = {}
        for tid, avail in cash.items():
            persona = get_persona(tid) or {}
            llm = persona.get("model_primary") or "unknown"
            slot = by_llm.setdefault(llm, {"llm": llm, "total_equity": 0.0, "tids": [], "n_agents": 0})
            eq = float(avail or 0.0) + reserved_by_tid.get(tid, 0.0)
            slot["total_equity"] += eq
            slot["tids"].append(tid)
            slot["n_agents"] += 1
        rollup = sorted(by_llm.values(), key=lambda x: -x["total_equity"])
        for r in rollup:
            r["total_equity"] = round(r["total_equity"], 2)
        return JSONResponse({"leaderboard": rollup, "n_llms": len(rollup)})

    @app.get("/api/reconcile")
    def api_reconcile(lookback_min: int = 60):
        """On-demand broker-fill reconciliation. GET so it can be curled from
        cron/dashboards. Default lookback 60 min (tick default is 15)."""
        try:
            stats = executor.reconcile_broker_fills(lookback_min=int(lookback_min))
            return JSONResponse({"ok": True, **stats})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)[:400]}, status_code=500)

    @app.post("/api/reconcile-equity")
    def api_reconcile_equity(min_drift_pct: float = 0.02):
        """Persistent fleet→Alpaca rescale. Use when the dashboard shows drift
        between fleet_equity and Alpaca equity. Default min_drift_pct=0.02 (2%);
        below that we no-op so we don't churn the ledger on noise."""
        try:
            stats = executor.reconcile_fleet_to_alpaca(
                min_drift_pct=float(min_drift_pct), persist=True)
            return JSONResponse({"ok": True, **stats})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)[:400]}, status_code=500)

    @app.post("/api/reset-bankrolls")
    def api_reset_bankrolls():
        """Force re-seed from current Alpaca equity split across 17 personas."""
        b = executor.seed_bankrolls([p["tid"] for p in PERSONAS], force=True)
        for p in PERSONAS:
            STATE["agents"].setdefault(p["tid"], {
                "decisions": 0, "trades": 0, "passes": 0, "bankroll": 0.0,
            })
            STATE["agents"][p["tid"]]["bankroll"] = executor.get_bankroll(p["tid"])
        return JSONResponse({"ok": True, "bankrolls": {k: v for k, v in b.items() if not k.startswith("_")}, "meta": b.get("_meta", {})})

    return app


# Lazy-construct FastAPI only when serving
app = None


def get_app():
    global app
    if app is None:
        app = _build_app()
    return app


# ───────────────────────── CLI ─────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Single tick, print decisions, exit")
    parser.add_argument("--serve", action="store_true", help="Run FastAPI server on 0.0.0.0:7860")
    args = parser.parse_args()

    if args.once:
        print(f"[itf] mode={'live' if executor.live_mode() else 'dry_run'} — single tick")
        tick_once(dry_print=True)
    elif args.serve:
        import uvicorn  # type: ignore
        threading.Thread(target=tick_loop, daemon=True).start()
        uvicorn.run(get_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
    else:
        parser.print_help()
