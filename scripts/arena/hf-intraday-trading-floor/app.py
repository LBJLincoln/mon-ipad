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

COLLECTIVE_MISSION = """
You are ONE of 14 LLM agents on the Nomos42 Intraday Trading Floor (AGGRESSIVE MODE +1).
All 14 see the same market tape, research digest, peer bets, and council plan.
COLLECTIVE GOAL: ONE of us must reach $1,000,000 by Aug 1, 2026 — rapidly.
You each start at $10,000. EVERY trading day ≥9 of the 14 must hold a position.
Passing is cowardice, punished on the leaderboard. Pass ONLY if tape is
literally flat (all moves < 0.15%).

PQTF PROOF — DERIVATIVES $1M PLAYBOOK (50 days, 6 agents, $600 → $602,354):
  • mistral:large $100 → $244,050 (+40,667%) — 12 positions/day, sized 5-8% per trade,
    concentrated XLC/XLE/XLF/XLK sectors with options overlay, 4 cooperation pacts.
  • mistral:medium $100 → $154,566 (+25,761%) — mirror strategy at smaller scale.
  • Key rule: COMPOUND AGGRESSIVELY. Start $10k → target 3-8% per position on
    high-conviction edges. After each win, scale UP (not back down). The winner
    doubled bankroll every ~5 days for the first month then kept compounding.

FULL FREEDOM: any ticker visible in the tape, any side, stake 3-8% of bankroll
for high-conviction (edge>2% + regime match). Options preferred when IV rank
supports strategy. Cooperate (pact) or STRUCTURALLY DIVERGE peers — never
blindly copy, never silent-pass on LLM failure.
""".strip()

AXELROD_CANON = """
AXELROD CANON (cooperation doctrine):
- BE NICE. Don't front-run a teammate's stated thesis.
- BE RETALIATORY. If someone tanks a pair-trade by flipping, flag it.
- BE FORGIVING. One bad tick does not make an enemy.
- BE CLEAR. Your JSON must be machine-parseable. No ambiguity.
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
$1M COLLECTIVE MISSION: the 17 ITF agents together must reach $1,000,000 by Aug 1, 2026.
Each agent has a dedicated sub-bankroll (see YOUR CAPITAL block). Be MAX-AGGRESSIVE:
5-12% of YOUR bankroll per high-conviction trade, target 8-15 trades/day MINIMUM, paper
account has NO PDT limit — exploit unlimited daytrading. PQTF proved it — mistral:large
$100 → $244,050 (+40,667%) in 50 days by sizing UP 5-8% and stacking 12 positions/day.
Do the same here at intraday cadence across equity+crypto+options universe.

Respond with ONE of:
  { "action": "pass", "reason": "..." }
OR close an existing open position to free buying power (USE THIS when your agent already has
an open position that hit target thesis OR macro regime flipped — don't wait for the bracket):
  { "action": "close", "ticker": "NVDA", "reason": "thesis played out, freeing BP for next setup" }
OR a standard equity/crypto trade:
  { "action": "trade",
    "ticker": ANY ticker visible in the INTRADAY TAPE block below (equities, leveraged,
              volatility, international, commodities, bonds, thematic, stocks, or
              crypto). You are NOT restricted to a whitelist — pick the best edge.
    "side": "long"|"short",
    "stake_usd": 300 to (0.08 × your_bankroll_in_usd). Floor $300. High-conviction (>3% edge
                 AND VIX-regime match) SHOULD go to 5-8% of bankroll — PQTF mistral:large proved
                 aggressive sizing compounds into 400×. Survival rule: if bankroll would drop
                 below $20 post-trade, PASS instead.
    "stop_pct": 0.002-0.03,
    "take_profit_pct": 0.005-0.08,
    "thesis": "1-2 sentence reason citing quote/edge/signal/peer-bet/council-plan"
  }
OR an intraday options derivative (dry-run logged; live options routing via executor.submit_option):
  { "action": "option_trade",
    "underlying": ANY ticker visible in the INTRADAY TAPE block (was SPY|QQQ|IWM|XLE|XLK|
                  XLF|NVDA|TSLA whitelist — now unrestricted; choose by option liquidity),
    "option_type": "call"|"put",
    "strategy": "long"|"vertical_debit"|"vertical_credit"|"iron_condor"|"straddle",
    "dte": 0|1|2|5,
    "strike_offset_pct": -0.03 to 0.03,
    "wing_width_pct": 0.005-0.03,
    "stake_usd": 100-1500,
    "max_loss_pct": 0.01-0.05,
    "thesis": "1-2 sentence reason — cite IV rank, realized vol, gamma, or skew"
  }

Return JSON ONLY. No markdown fences, no prose.

UNRESTRICTED UNIVERSE: Alpaca paper supports 10,000+ US equities, 30+ crypto pairs,
and every listed US option. The INTRADAY TAPE block below shows the most-liquid ~110
for macro context — you are NOT restricted to it. If you have an edge on a ticker not
on the tape (e.g. UAL for airlines-earnings, LCID for EV-rotation, BITO for BTC proxy,
EWZ for Brazil, PDBC for commodities, FXI for China, LEU for nuclear), emit it. The
executor will fetch its last quote on demand.

FULL ARSENAL — use everything. You have unrestricted access to:
  • LONG  — any equity/ETF/crypto, any size up to 12% of YOUR sub-bankroll.
  • SHORT — any shortable US equity or ETF. Emit side="short"; executor routes
            to Alpaca sell-short. Use for bearish conviction, not just hedging.
  • INVERSE ETFs — SH (S&P -1x), SQQQ (Nasdaq -3x), SPXU (S&P -3x), SDOW, TZA,
            FAZ, SRTY, SOXS — bearish beta without shorting mechanics.
  • LEVERAGED ETFs — TQQQ/SQQQ, UPRO/SPXU, SOXL/SOXS, TNA/TZA, FAS/FAZ, LABU/LABD,
            NUGT/DUST, ERX/ERY — synthetic futures-like leverage on any sector.
  • COMMODITY ETFs — GLD (gold), SLV (silver), USO (oil), UNG (natgas), DBA (agri),
            CORN, WEAT, SOYB, JO (coffee), COPX (copper), URA (uranium), PALL
            (palladium), PPLT (platinum), BAL (cotton).
  • OPTIONS DERIVATIVES — verticals, iron condors, straddles, butterflies (schema
            below). Use for non-linear payoff, event-driven trades, vol plays.
  • CRYPTO 24/7 — BTC, ETH, SOL, AVAX, LINK, DOGE, etc. Always live, no market hours.

No futures/forex on paper Alpaca (use commodity ETFs + leveraged ETFs as proxies).
No whitelist restriction — the only gate is "does this have edge for my persona."

RULE: Crypto tickers trade 24/7. Equities (incl. leveraged/inverse/vol/intl/commodity)
and options trade only during RTH + extended hours (08:00-24:00 UTC weekdays). Off-hours:
emit crypto OR queued-for-open equities. Passing with "market closed" is cowardice —
crypto is ALWAYS live. 17 agents × 8-15 trades/day × 5-12% sizing compounds to $1M fast.
""".strip()


# Hard off-hours override — CRYPTO_PIVOT_CLAUSE was additive but persona primary
# narratives (e.g. scalper "favor SPY/QQQ", pairs "sector-ETF") still pushed
# equities. When markets are closed AND crypto has moving signal, we REPLACE
# the style wholesale with a crypto-only mandate so 5/7 silent agents trade.
_OFF_HOURS_STYLE_BY_TID: Dict[str, str] = {
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

    pqtf = ctx.get("pqtf_state") or {}
    pqtf_block = (
        f"last_day={pqtf.get('last_day', '?')} fleet=${pqtf.get('fleet_bankroll', '?')} "
        f"open_positions={len(pqtf.get('open_positions') or [])}"
    )

    # Hard off-hours crypto override — swap style wholesale so equity-tape-dependent
    # personas (scalper/momentum/mean-rev/pairs/vol) trade crypto 24/7 instead of
    # passing because "SPY tape flat, market closed".
    style_final = persona["style"]
    if not equity_hours and _off_hours_crypto_signal(quotes):
        override = _OFF_HOURS_STYLE_BY_TID.get(persona["tid"])
        if override:
            style_final = override

    # 2026-04-21 proposal #3 — regime gate. If low-vol regime, append DEAD_TAPE
    # clause so the LLM knows it can pass. Waiver of min-deploy is enforced
    # downstream in the tick loop; we just feed the context here.
    regime = ctx.get("regime") or _compute_crypto_regime(quotes)
    if regime.get("low_vol_regime"):
        style_final = f"{style_final}\n\n{DEAD_TAPE_CLAUSE}"

    # 2026-04-20 AGGRESSIVE-MODE: inject knowledge digest + peer-bet digest + council plan.
    # All 3 are cached/day; token-bounded so total prompt stays well under 4k tokens.
    knowledge_digest = _build_knowledge_digest()
    peer_digest = _build_peer_bets_digest(persona, n_days=3)
    council_block = _format_council_block(_latest_council_plan())

    _pm_override = _load_prompt_override("itf")

    # v2.5 — per-agent sub-bankroll from executor ledger. LLM sees its OWN capital
    # and sizes stakes 5-12% of that number, not a fiction shared across 17 agents.
    _agent_bankroll = executor.get_bankroll(persona["tid"])
    _bankroll_block = (
        f"═══ YOUR CAPITAL ═══\n"
        f"YOU ({persona['tid']}) have a dedicated sub-bankroll of ${_agent_bankroll:,.2f}. "
        f"This is YOUR pot out of 17 agents sharing Alpaca's paper equity. Every trade "
        f"you place RESERVES stake from this number; every close (bracket-TP, bracket-SL, "
        f"EOD, agent-close) returns stake + realized P&L. The $1M mission is COLLECTIVE — "
        f"all 17 agents together must reach $1,000,000. You personally compound YOURS.\n"
        f"Stake sizing: 5-12% of ${_agent_bankroll:,.0f} per trade = "
        f"${max(100, _agent_bankroll*0.05):.0f}-${max(300, _agent_bankroll*0.12):.0f}. "
        f"If bankroll < $200, shrink to $100/trade; if > $10k, scale to $1,200/trade max.\n"
        f"PAPER ACCOUNT: no PDT rule — unlimited daytrades. Target 8-15 trades/day MINIMUM. "
        f"Passing is cowardice — the leaderboard rewards aggression compounded safely."
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

EVENT MARKETS (Polymarket, top volume 24h):
{poly_block}

NBA TOP-5 EDGES today: {nba_block}
POL TOP-5 SIGNALS today: {pol_block}
PQTF state: {pqtf_block}

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


def _call_agent(persona: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    prompt = _build_prompt(persona, ctx)
    messages = [
        {"role": "system", "content": f"{COLLECTIVE_MISSION}\n\n{AXELROD_CANON}"},
        {"role": "user", "content": prompt},
    ]
    # Try primary then fallback
    for model_key in (persona["model_primary"], persona["model_fallback"]):
        resp = gateway_call(model_key, messages, temperature=0.6, max_tokens=400,
                            fallback_direct=False, timeout=45.0)
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
        STATE["tick_count"] += 1
        STATE["last_tick_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[itf] tick #{STATE['tick_count']} starting", file=sys.stderr, flush=True)
    # 2026-04-21 — refresh stale broker statuses BEFORE anything else so
    # /api/status + positions.json reflect real fills, not cached pending_new.
    # Addresses user report: "ITF seems slow, orders not moving at all".
    try:
        _bs = executor.refresh_broker_statuses()
        if _bs.get("polled", 0) > 0:
            print(f"[itf] broker-status refresh: {_bs}", file=sys.stderr, flush=True)
    except Exception as _brs:
        print(f"[itf] broker-status refresh err (non-fatal): {_brs}", file=sys.stderr, flush=True)
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
        decision = _call_agent(persona, ctx)
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
                    raw_stake = min(raw_stake, 400.0)
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
                "stake_usd":   min(1500, max(200, float(decision.get("stake_usd", 500) or 500))),
                "max_loss_pct":min(0.05, max(0.005, float(decision.get("max_loss_pct", 0.02) or 0.02))),
                "thesis":      decision.get("thesis", ""),
            }
            entry = executor.submit_option(persona["tid"], option_order, last_quote)
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
        return JSONResponse({
            "running": STATE["running"],
            "last_tick_at": STATE["last_tick_at"],
            "tick_count": STATE["tick_count"],
            "mode": "live" if executor.live_mode() else "dry_run",
            "agents": STATE["agents"],
            "config_agents": PERSONAS,
            "quote_source": (quote_latest() or {}).get("_source"),
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
    def api_bankrolls():
        """Honest accounting — per-agent + fleet:
          available   = free cash in agent's sub-bankroll (after reserves)
          reserved    = sum of stake_usd on that agent's OPEN positions
          total_equity = available + reserved
        Fleet rollups sum across all personas. stake_usd is the canonical
        source of truth (reserved on submit, credited on close)."""
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
            agents[tid] = {
                "available": round(float(avail or 0.0), 2),
                "reserved_open": reserved,
                "total_equity": round(float(avail or 0.0) + reserved, 2),
            }
        fleet_available = round(sum(a["available"] for a in agents.values()), 2)
        fleet_reserved = round(sum(a["reserved_open"] for a in agents.values()), 2)
        return JSONResponse({
            "fleet_available": fleet_available,
            "fleet_reserved": fleet_reserved,
            "fleet_equity": round(fleet_available + fleet_reserved, 2),
            "agents": agents,
            "meta": executor._load_bankrolls().get("_meta", {}),
        })

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
