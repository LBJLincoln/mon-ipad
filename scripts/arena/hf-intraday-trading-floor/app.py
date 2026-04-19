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
OR:
  { "action": "trade",
    "ticker": one of:
      EQUITIES: "SPY","QQQ","IWM","DIA","XLE","XLF","XLK","XLV","XLI","XLB","XLY","XLP","XLRE","XLU","XLC","GLD","TLT","SLV","USO","UUP"
      STOCKS:   "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AMD","AVGO","COST"
      CRYPTO:   "BTC/USD","ETH/USD","SOL/USD","AVAX/USD","LINK/USD","DOGE/USD"  (24/7 tradeable)
    "side": "long"|"short",
    "stake_usd": 500-3000,
    "stop_pct": 0.002-0.02,
    "take_profit_pct": 0.005-0.05,
    "thesis": "1-2 sentence reason citing quote/edge/signal"
  }
Return JSON ONLY. No markdown fences, no prose.

RULE: Crypto tickers (BTC/USD, ETH/USD, SOL/USD, AVAX/USD, LINK/USD, DOGE/USD) trade 24/7.
When US equity market is closed, you MAY still emit crypto trades — NEVER emit equity trades
outside extended hours (equities gate in executor will reject).
""".strip()


def _build_prompt(persona: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    # Compact context to stay under token caps (~1500 tokens).
    quotes_summary = []
    for t, q in (ctx.get("quotes") or {}).items():
        quotes_summary.append(
            f"{t}: last={q.get('last')} Δ={q.get('change_pct')}% vol={q.get('volume')}"
        )
    quotes_block = "\n".join(quotes_summary[:22])

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

    return f"""{COLLECTIVE_MISSION}

{AXELROD_CANON}

YOUR ROLE — {persona['name']} ({persona['tid']}):
{persona['style']}

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
    quote_refresh()  # persist snapshot
    ctx = build_intraday_context()
    results: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # EOD flatten before new entries
    executor.close_expired(now)

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
        if decision.get("action") == "trade" and decision.get("ticker") in (ctx.get("quotes") or {}):
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
        else:
            STATE["agents"][persona["tid"]]["passes"] += 1
        results.append(result)
        if dry_print:
            print(json.dumps(result, indent=2, default=str))
            print("-" * 72)

    with _lock:
        STATE["last_tick_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        STATE["tick_count"] += 1

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
                print(f"[itf] tick failed: {e}", file=sys.stderr)
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
        # Very simple leaderboard: count open positions per agent + total decisions.
        board = []
        for p in PERSONAS:
            tid = p["tid"]
            agent_open = [o for o in opens if o.get("agent_tid") == tid]
            s = STATE["agents"][tid]
            board.append({
                "tid": tid, "name": p["name"], "tier": p["tier"],
                "decisions": s["decisions"], "trades": s["trades"], "passes": s["passes"],
                "open_positions": len(agent_open),
            })
        return JSONResponse({"agents": board})

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
