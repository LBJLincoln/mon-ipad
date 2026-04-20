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

# Local (HF Space style) imports
sys.path.insert(0, str(_HERE.parent))
from personas import PERSONAS, get as get_persona  # type: ignore  # noqa: E402
import executor  # type: ignore  # noqa: E402
from gateway_client import gateway_call  # type: ignore  # noqa: E402

# ───────────────────────── Prompts ─────────────────────────

COLLECTIVE_MISSION = """
You are ONE of 6 LLM agents on the Nomos42 Intraday Trading Floor.
All 6 see the same market tape and the same cross-repo context.
COLLECTIVE GOAL: grow the fleet to $1M over the trading season.
You will each start at $10,000. EVERY trading day ≥3 of the 6 must hold a
position — passing is allowed but cowardice is punished on the leaderboard.
You know other agents exist; over time you may propose coalitions (pairs of
agents taking opposite sides of a pair trade, for example).
""".strip()

AXELROD_CANON = """
AXELROD CANON (cooperation doctrine):
- BE NICE. Don't front-run a teammate's stated thesis.
- BE RETALIATORY. If someone tanks a pair-trade by flipping, flag it.
- BE FORGIVING. One bad tick does not make an enemy.
- BE CLEAR. Your JSON must be machine-parseable. No ambiguity.
""".strip()

DECISION_SCHEMA = """
Respond with ONE of:
  { "action": "pass", "reason": "..." }
OR a standard equity/crypto trade:
  { "action": "trade",
    "ticker": one of:
      SECTOR_ETF:    "SPY","QQQ","IWM","DIA","XLE","XLF","XLK","XLV","XLI","XLB","XLY","XLP","XLRE","XLU","XLC","GLD","TLT","SLV","USO","UUP"
      LEVERAGED:     "TQQQ","SQQQ","SPXL","SPXS","SOXL","SOXS","TNA","TZA"
      VOLATILITY:    "VXX","UVXY","SVXY","VIXY"
      INTERNATIONAL: "EEM","FXI","EWZ","EWJ","EWT","EWW","VGK","INDA","VEA","IEFA","ACWX","EFA","EFV","VWO"
      COMMODITIES:   "DBA","DBC","PDBC","CORN","WEAT","CPER","URA","UNG"
      BONDS:         "SHY","IEI","IEF","LQD","HYG"
      THEMATIC:      "ARKK","SOXX","SMH","XBI","ICLN","TAN","ITA","IBIT"
      STOCKS:        "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AMD","AVGO","COST","NFLX","ORCL","CRM","ADBE","PYPL","SMCI","UBER","SHOP","DIS","BA","JPM","BAC","WFC","GS","V","MA","LLY","UNH","COIN","MSTR","PLTR","RIVN"
      CRYPTO:        "BTC/USD","ETH/USD","SOL/USD","AVAX/USD","LINK/USD","DOGE/USD","DOT/USD","MATIC/USD","LTC/USD","UNI/USD","BCH/USD","XLM/USD","XRP/USD","AAVE/USD","SHIB/USD","MKR/USD","SUSHI/USD","CRV/USD","YFI/USD","GRT/USD"  (24/7 tradeable)
    "side": "long"|"short",
    "stake_usd": 500-3000,
    "stop_pct": 0.002-0.02,
    "take_profit_pct": 0.005-0.05,
    "thesis": "1-2 sentence reason citing quote/edge/signal"
  }
OR an intraday options derivative (dry-run logged; live options routing via executor.submit_option):
  { "action": "option_trade",
    "underlying": "SPY"|"QQQ"|"IWM"|"XLE"|"XLK"|"XLF"|"NVDA"|"TSLA",
    "option_type": "call"|"put",
    "strategy": "long"|"vertical_debit"|"vertical_credit"|"iron_condor"|"straddle",
    "dte": 0|1|2|5,
    "strike_offset_pct": -0.02 to 0.02,
    "wing_width_pct": 0.005-0.02,   # for verticals / condors
    "stake_usd": 200-1500,
    "max_loss_pct": 0.01-0.05,
    "thesis": "1-2 sentence reason — cite IV rank, realized vol, gamma, or skew"
  }

Return JSON ONLY. No markdown fences, no prose.

RULE: Crypto tickers trade 24/7. Equities (incl. leveraged/vol/intl/stocks) and options
trade only during extended hours (08:00-24:00 UTC weekdays). When markets are closed,
emit crypto trades OR pass — NEVER emit equity/option trades outside hours.
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
}


def _off_hours_crypto_signal(quotes: Dict[str, Dict[str, Any]]) -> bool:
    """True if any of BTC/ETH/SOL has |change_pct| > 0.2% — enough tape to trade."""
    for pair in ("BTC/USD", "ETH/USD", "SOL/USD"):
        q = quotes.get(pair) or {}
        chg = q.get("change_pct")
        if chg is not None and abs(float(chg)) > 0.2:
            return True
    return False


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
    priority_eq = [t for t in ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLE", "XLF", "TQQQ", "SQQQ",
                                "UVXY", "VXX", "NVDA", "TSLA", "AAPL", "META"] if t in quotes]
    # Remaining equities (leveraged, sector, stocks we haven't already shown), capped.
    remaining_eq = [t for t in equity_tickers if t not in priority_eq][:6]

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

    return f"""{COLLECTIVE_MISSION}

{AXELROD_CANON}

YOUR ROLE — {persona['name']} ({persona['tid']}):
{style_final}

INTRADAY TAPE ({ctx.get('quotes_ts')} · {ctx.get('quotes_source')}):
{quotes_block}

NBA TOP-5 EDGES today: {nba_block}
POL TOP-5 SIGNALS today: {pol_block}
PQTF state: {pqtf_block}

{DECISION_SCHEMA}
"""


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
    return {"action": "pass", "reason": "llm_failed_both_models",
            "_llm_model": persona["model_primary"], "_llm_routed_via": "failed"}


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
    "agents": {p["tid"]: {"decisions": 0, "trades": 0, "passes": 0} for p in PERSONAS},
}
_stop = threading.Event()
_lock = threading.Lock()
DECISIONS_DIR = _REPO / "data" / "intraday" / "decisions"
DECISIONS_DIR.mkdir(parents=True, exist_ok=True)


def tick_once(dry_print: bool = False) -> List[Dict[str, Any]]:
    """Run one tick: refresh quotes, build context, call all 6 agents, execute."""
    with _lock:
        STATE["tick_count"] += 1
        STATE["last_tick_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[itf] tick #{STATE['tick_count']} starting", file=sys.stderr, flush=True)
    quote_refresh()  # persist snapshot
    ctx = build_intraday_context()
    results: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # EOD flatten before new entries — mark-to-market using current quote bus.
    def _q(ticker: str):
        q = (ctx.get("quotes") or {}).get(ticker) or {}
        return q.get("last")
    executor.close_expired(now, quote_fn=_q)

    for persona in PERSONAS:
        decision = _call_agent(persona, ctx)
        result = {
            "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_tid": persona["tid"],
            "agent_name": persona["name"],
            "tier": persona["tier"],
            "decision": decision,
        }
        STATE["agents"][persona["tid"]]["decisions"] += 1
        action = decision.get("action")
        if action == "trade" and decision.get("ticker") in (ctx.get("quotes") or {}):
            last_quote = (ctx["quotes"][decision["ticker"]] or {}).get("last") or 0
            order = {
                "ticker": decision["ticker"],
                "side": decision.get("side", "long"),
                "stake_usd": min(3000, max(500, float(decision.get("stake_usd", 1000) or 1000))),
                "stop_pct": min(0.02, max(0.001, float(decision.get("stop_pct", 0.005) or 0.005))),
                "take_profit_pct": min(0.05, max(0.002, float(decision.get("take_profit_pct", 0.012) or 0.012))),
                "thesis": decision.get("thesis", ""),
            }
            entry = executor.submit(persona["tid"], order, last_quote)
            result["execution"] = entry
            STATE["agents"][persona["tid"]]["trades"] += 1
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
