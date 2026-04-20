"""Pure engine logic — no FastAPI, no Gradio, no network imports at top-level.

Separated from app.py so unit tests can exercise the core intraday loop without
spinning up a Space. app.py re-imports everything from here.
"""
import json
import os
import time
import traceback
import threading
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from options import bs_price, option_pnl
# 2026-04-19 real-data migration: switch paths backend via USE_REAL_PATHS env.
# real_paths falls back to simulator when cache is missing, so this is safe
# to flip on before the cache exists.
if os.environ.get("USE_REAL_PATHS") == "1":
    from real_paths import (
        gbm_path, jump_path, scale_iv_for_event, EVENT_IV_SCALE,
    )
else:
    from intraday_paths import (
        gbm_path, jump_path, scale_iv_for_event, EVENT_IV_SCALE,
    )
from session_data import load_events, all_days, enrich_event_for_quant
from spreads import (
    vertical_spread, iron_condor, straddle, butterfly,
    mark_position, portfolio_var, check_stop_loss,
)

# ── Config ─────────────────────────────────────────────────────────────────

AGENTS = [
    {"tid": "qwen-quant",    "model": "cerebras:qwen-3-235b",   "personality": "quantitative", "risk": 0.55},
    {"tid": "llama-contra",  "model": "cerebras:llama3.1-8b",   "personality": "contrarian",   "risk": 0.55},
    {"tid": "gemini-anl",    "model": "google:gemini-3-flash",  "personality": "analytical",   "risk": 0.55},
    {"tid": "mistral-large", "model": "mistral:large",          "personality": "ensemble",     "risk": 0.50},
    {"tid": "mistral-medium","model": "mistral:medium",         "personality": "diversified",  "risk": 0.45},
    {"tid": "mistral-nemo",  "model": "mistral:nemo",           "personality": "aggressive",   "risk": 0.70},
]

STARTING_BANKROLL = 100.0  # parity with NBA/POL TF (was $100K — 2026-04-19)
MAX_POSITIONS_PER_SESSION = 3
MIN_DEPLOY_PCT_PER_SESSION = 0.10
MAX_DEPLOY_PCT_PER_SESSION = 0.30
KELLY_MULT = 0.25
RISK_FREE_RATE = 0.045
OPTION_MULT = 100
# Scale position-cost floor with bankroll. $50 was sensible at $100K, prohibitive at $100.
# 50 bps of starting bankroll, capped at $0.50 min so we still reject dust.
MIN_POSITION_COST = max(0.5, STARTING_BANKROLL * 0.005)
# Defensive-mode threshold: 20% of starting bankroll (was absolute $20K for $100K).
DEFENSIVE_BANKROLL_FLOOR = STARTING_BANKROLL * 0.20

ETF_BASE_SPOT = {
    "SPY": 520.0, "XLF": 50.0, "XLK": 240.0, "XLE": 95.0,
    "XLV": 155.0, "XLP": 82.0, "XLY": 200.0, "XLC": 95.0,
    "XLI": 135.0, "XLB": 95.0, "XLRE": 45.0, "XLU": 75.0,
}
ETF_BASE_IV = 0.18

COLLECTIVE_MISSION = """You are ONE of 6 LLM agents running a QUANT political-trading floor.
You trade OPTIONS on sector ETFs (XLF, XLK, XLE, etc.) across 4 intraday sessions per day.
Every agent sees the SAME data; you are distinguished by personality + reasoning style.

SHARED GOAL: grow the fleet bankroll 10× by Nov 3 2026 (6 agents starting at $100 each = $600 fleet → $6,000).
RULES (hard):
  - Every session, you must propose 0-3 option trades (call or put, sector ETF, OTM/ATM/ITM strike).
  - You may coalition with ≤1 peer on a trade (structural DMAD: proposer + peer run DIFFERENT reasoning templates).
  - Peak-drawdown guard: if your bankroll drops below 20% of starting ($20 on a $100 base), go defensive (ATM options only, ≤5% per trade).
"""


# ── Prompt / LLM ───────────────────────────────────────────────────────────

def _load_prompt_override(fleet: str = "pqtf") -> str:
    """Load prompt-mutator override block from data/prompts/overrides.json.

    Mirrors NBA/POL TF helper (scripts/arena/hf-political-trading-floor/app.py:140).
    Silent on missing file so unit tests + offline runs keep working.
    """
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
            rule = (ov.get(fleet) or {}).get("current_text") or ""
            if rule:
                v = (ov.get(fleet) or {}).get("current_version") or "?"
                return f"\n=== PROMPT MUTATOR OVERRIDE ({v}) ===\n{rule}\n=== END OVERRIDE ===\n"
        except Exception:
            continue
    return ""


def build_prompt(agent: Dict, date: str, session_id: int, session_events: List[Dict],
                 bankroll: float, peers_bankroll: Dict[str, float],
                 etf_spots: Dict[str, float]) -> str:
    events_block = []
    for i, ev in enumerate(session_events):
        events_block.append(
            f"  [{i}] {ev.get('event_type','?')} ticker={ev.get('ticker','?')} "
            f"etf={ev['etf_ticker']} sector={ev.get('signal_sector','?')} "
            f"signal_strength={ev.get('signal_strength',0):.2f} bias={ev['direction_bias']:+d} "
            f"iv_category={ev['iv_category']} title='{(ev.get('title') or '')[:80]}'"
        )
    events_str = "\n".join(events_block) if events_block else "  (no events in this session)"
    spots_str = ", ".join(f"{t}={s:.2f}" for t, s in sorted(etf_spots.items()))
    peers_str = ", ".join(f"{t}=${b:,.0f}" for t, b in sorted(peers_bankroll.items(), key=lambda x: -x[1])[:5])

    # ITF v1 (2026-04-19): inject live intraday tape from the shared quote bus.
    # Additive — silent on missing file so backtests keep working.
    intraday_tape_str = ""
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _repo = _Path(__file__).resolve().parents[3]
        if str(_repo) not in _sys.path:
            _sys.path.insert(0, str(_repo))
        from scripts.arena.shared.quote_bus import latest as _qlatest  # type: ignore
        _snap = _qlatest() or {}
        _tape = _snap.get("tickers") or {}
        if _tape:
            intraday_tape_str = (
                "\nINTRADAY TAPE (live "
                f"{_snap.get('_source','yfinance')} @ {_snap.get('ts','?')}): "
                + ", ".join(f"{t}={q.get('last')}({q.get('change_pct')}%)"
                            for t, q in list(_tape.items())[:12])
                + "\n"
            )
    except Exception:
        pass

    _pm_override = _load_prompt_override("pqtf")

    return f"""{COLLECTIVE_MISSION}{_pm_override}

YOU: {agent['tid']} ({agent['personality']}, risk={agent['risk']})
DATE: {date}  SESSION: s{session_id}  YOUR BANKROLL: ${bankroll:,.0f}
PEERS (top 5): {peers_str}

SESSION EVENTS:
{events_str}

ETF SPOTS: {spots_str}{intraday_tape_str}

YOUR TASK — return a JSON object with keys:
  "thesis": <string, 1-2 sentences>
  "reasoning_template": <mean-reversion | momentum | vol-expansion | sector-rotation | macro-hedge>
  "allocations": [
    # SINGLE-LEG:
    {{"event_idx": <int>, "etf": <ticker>, "option_type": "call"|"put",
      "strike_pct": <float 0.9-1.1>, "tte_days": <int 1-5>, "qty": <int 1-10>,
      "rationale": <str>}}
    # OR MULTI-LEG (Phase 2 spreads — use for vol plays + defined risk):
    # vertical: bull call / bear put (defined risk, defined reward)
    {{"event_idx": <int>, "etf": <ticker>, "strategy": "vertical",
      "option_type": "call"|"put",
      "strike_low_pct": <float 0.95-1.0>, "strike_high_pct": <float 1.0-1.08>,
      "tte_days": <int 2-10>, "qty": <int 1-5>, "rationale": <str>}}
    # iron_condor: net-credit, bet on range
    {{"event_idx": <int>, "etf": <ticker>, "strategy": "iron_condor",
      "put_long_pct": 0.93, "put_short_pct": 0.96, "call_short_pct": 1.04, "call_long_pct": 1.07,
      "tte_days": <int 3-14>, "qty": <int 1-3>, "rationale": <str>}}
    # straddle: long or short vol
    {{"event_idx": <int>, "etf": <ticker>, "strategy": "straddle",
      "side": "long"|"short", "strike_pct": 1.0,
      "tte_days": <int 2-7>, "qty": <int 1-3>, "rationale": <str>}}
    # butterfly: pin play at strike
    {{"event_idx": <int>, "etf": <ticker>, "strategy": "butterfly",
      "option_type": "call"|"put",
      "strike_low_pct": 0.97, "strike_mid_pct": 1.0, "strike_high_pct": 1.03,
      "tte_days": <int 3-10>, "qty": <int 1-3>, "rationale": <str>}}
    # ...max {MAX_POSITIONS_PER_SESSION} allocations
  ]
  "coalition_proposal": {{"peer": <tid or "none">, "event_idx": <int>, "etf": <ticker>, "option_type": "call|put"}}

RULES (collective dynamics):
- coalition_proposal is MANDATORY (must be present on every response). Set "peer" to a
  different agent tid you want to pact with AND match with an allocation on that
  event_idx+etf, or set "peer": "none" with a rationale for no pact this session.
  Empty/missing field = invalid response.
- COLLECTIVE-HELP: if any peer bankroll < $50, a top-3 agent must propose a carry-pact
  (structural DMAD: you two must run DIFFERENT reasoning_templates).

Respond ONLY with valid JSON, no markdown fences.
"""


def parse_llm_response(text: str) -> Optional[Dict]:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    lo = text.find("{")
    hi = text.rfind("}")
    if lo < 0 or hi < 0:
        return None
    try:
        return json.loads(text[lo:hi+1])
    except Exception:
        return None


# call_llm is injectable — default uses gateway_client, tests override
_call_llm_impl = None


def default_call_llm(agent: Dict, prompt: str) -> Optional[Dict]:
    try:
        from gateway_client import gateway_call
    except Exception as e:
        print(f"[llm] import fail: {e}")
        return None
    try:
        t0 = time.time()
        resp = gateway_call(
            model_key=agent["model"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000, temperature=0.6, timeout=40,
        )
        dt = time.time() - t0
        text = (resp or {}).get("text") or (resp or {}).get("content") or ""
        routed = (resp or {}).get("routed_via", "?")
        if not text:
            print(f"[llm] {agent['tid']} empty text (routed={routed}, err={(resp or {}).get('error')})")
            return None
        parsed = parse_llm_response(text)
        if parsed is None:
            print(f"[llm] {agent['tid']} parse fail (routed={routed}, text_head={text[:120]!r})")
            return None
        parsed["_llm_seconds"] = round(dt, 2)
        parsed["_routed_via"] = routed
        return parsed
    except Exception as e:
        print(f"[llm] {agent['tid']} failed: {type(e).__name__}: {e}")
        return None


def set_call_llm(fn):
    """Override LLM caller (used by tests)."""
    global _call_llm_impl
    _call_llm_impl = fn


def call_llm(agent: Dict, prompt: str) -> Optional[Dict]:
    impl = _call_llm_impl or default_call_llm
    return impl(agent, prompt)


# ── Session / day runners ──────────────────────────────────────────────────

def run_session(agents_state: Dict, date: str, session_id: int,
                session_events: List[Dict], etf_spot_open: Dict[str, float],
                etf_iv: Dict[str, float], session_minutes: int) -> Dict:
    peers_bankroll = {tid: s["bankroll"] for tid, s in agents_state.items()}
    proposals: Dict[str, Optional[Dict]] = {}

    # Parallel LLM calls
    # Survival floor: skip LLM if bankroll below DEFENSIVE_BANKROLL_FLOOR (= $20 for $100 start).
    # 2026-04-19: prior floor hardcoded to <1000 from the $100K era — never fired under the
    # new $100 STARTING_BANKROLL, silencing every agent for entire 50-day run (PQTF reset bug).
    with ThreadPoolExecutor(max_workers=len(AGENTS)) as ex:
        futs = {}
        for a in AGENTS:
            tid = a["tid"]
            if agents_state[tid]["bankroll"] < DEFENSIVE_BANKROLL_FLOOR:
                proposals[tid] = None
                continue
            prompt = build_prompt(a, date, session_id, session_events,
                                  agents_state[tid]["bankroll"], peers_bankroll, etf_spot_open)
            futs[ex.submit(call_llm, a, prompt)] = tid
        for fut in as_completed(futs, timeout=90):
            tid = futs[fut]
            try:
                proposals[tid] = fut.result()
            except Exception:
                proposals[tid] = None

    # Coalition pacts (structural DMAD — reasoning_template must differ)
    # 2026-04-19 BUGFIX #3 — accept MANDATORY prompt's "none" sentinel + allow
    # dict-shaped coalition_proposal only. Previously null was silently skipped;
    # now explicit "none" is also skipped so the mandatory prompt round-trips.
    pacts = {}
    for tid, prop in proposals.items():
        if not prop or not isinstance(prop, dict):
            continue
        cp = prop.get("coalition_proposal")
        if not isinstance(cp, dict):
            cp = {}
        peer_tid = cp.get("peer")
        if isinstance(peer_tid, str) and peer_tid.strip().lower() == "none":
            peer_tid = None
        if not peer_tid or peer_tid == tid or peer_tid not in proposals:
            continue
        peer_prop = proposals.get(peer_tid)
        if not peer_prop:
            continue
        if prop.get("reasoning_template") == peer_prop.get("reasoning_template"):
            continue
        key = tuple(sorted([tid, peer_tid]))
        pacts[key] = {"event_idx": cp.get("event_idx"), "etf": cp.get("etf"),
                      "option_type": cp.get("option_type")}

    # Open positions (BS entry price)
    positions = []
    for tid, prop in proposals.items():
        if not prop:
            continue
        state = agents_state[tid]
        allocs = prop.get("allocations") or []
        if not isinstance(allocs, list):
            continue
        allocs = allocs[:MAX_POSITIONS_PER_SESSION]
        bankroll = state["bankroll"]
        defensive = bankroll < DEFENSIVE_BANKROLL_FLOOR

        for alloc in allocs:
            if not isinstance(alloc, dict):
                continue
            try:
                etf = alloc.get("etf", "SPY")
                if etf not in etf_spot_open:
                    etf = "SPY"
                spot = etf_spot_open[etf]
                iv = etf_iv.get(etf, ETF_BASE_IV)
                tte_days = max(1, min(14, int(alloc.get("tte_days", 2))))
                tte_years = tte_days / 252.0
                strategy_kind = (alloc.get("strategy") or "").strip().lower()

                if strategy_kind in ("vertical", "iron_condor", "straddle", "butterfly"):
                    # ── Multi-leg (Phase 2) ───────────────────────────
                    qty = max(1, min(3 if defensive else 5, int(alloc.get("qty", 1))))
                    if strategy_kind == "vertical":
                        opt_type = alloc.get("option_type", "call")
                        if opt_type not in ("call", "put"):
                            continue
                        lo_pct = max(0.90, min(1.05, float(alloc.get("strike_low_pct", 0.98))))
                        hi_pct = max(0.95, min(1.10, float(alloc.get("strike_high_pct", 1.03))))
                        if lo_pct >= hi_pct:
                            continue
                        strat = vertical_spread(spot, spot*lo_pct, spot*hi_pct,
                                                tte_years, iv, opt_type, r=RISK_FREE_RATE)
                    elif strategy_kind == "iron_condor":
                        pl = float(alloc.get("put_long_pct",  0.93))
                        ps = float(alloc.get("put_short_pct", 0.96))
                        cs = float(alloc.get("call_short_pct",1.04))
                        cl = float(alloc.get("call_long_pct", 1.07))
                        if not (pl < ps < 1.0 < cs < cl):
                            continue
                        strat = iron_condor(spot, spot*ps, spot*pl, spot*cs, spot*cl,
                                            tte_years, iv, r=RISK_FREE_RATE)
                    elif strategy_kind == "straddle":
                        side = alloc.get("side", "long")
                        if side not in ("long", "short"):
                            continue
                        if defensive and side == "short":
                            continue  # no naked shorts when small
                        k_pct = max(0.95, min(1.05, float(alloc.get("strike_pct", 1.0))))
                        strat = straddle(spot, spot*k_pct, tte_years, iv, r=RISK_FREE_RATE, side=side)
                    else:  # butterfly
                        opt_type = alloc.get("option_type", "call")
                        lo = float(alloc.get("strike_low_pct", 0.97))
                        mid = float(alloc.get("strike_mid_pct", 1.00))
                        hi = float(alloc.get("strike_high_pct", 1.03))
                        if not (lo < mid < hi):
                            continue
                        strat = butterfly(spot, spot*lo, spot*mid, spot*hi,
                                          tte_years, iv, opt_type, r=RISK_FREE_RATE)

                    strat_cost = float(strat.get("cost") or -strat.get("net_credit", 0))
                    # Net credit strategies (iron_condor) have cost<0, flip sign for margin
                    max_loss = float(strat.get("max_loss", abs(strat_cost)))
                    position_cost = max(abs(strat_cost), max_loss) * qty * OPTION_MULT
                    max_cost = bankroll * (0.05 if defensive else 0.15)
                    if position_cost > max_cost:
                        qty = max(1, int(max_cost / max(1, max_loss * OPTION_MULT)))
                        position_cost = max(abs(strat_cost), max_loss) * qty * OPTION_MULT
                    if position_cost < MIN_POSITION_COST or position_cost > bankroll * MAX_DEPLOY_PCT_PER_SESSION:
                        continue

                    # Tag multi-leg with explicit option_type + representative strike
                    # so downstream analytics/serialization don't see `type=null,
                    # strike=0` (the "zombie row" bug 2026-04-20). Strategy kind is
                    # the canonical type label; representative strike is the short
                    # strike (vertical/iron_condor) or ATM (straddle/butterfly).
                    if strategy_kind == "vertical":
                        rep_strike = float(spot * hi_pct)  # short strike of debit spread
                    elif strategy_kind == "iron_condor":
                        rep_strike = float(spot * ps)      # put-short strike
                    elif strategy_kind == "straddle":
                        rep_strike = float(spot * k_pct)   # ATM
                    else:  # butterfly
                        rep_strike = float(spot * mid)     # body strike
                    positions.append({
                        "tid": tid, "etf": etf, "spot_open": spot,
                        "strategy": strategy_kind, "multi_leg": True,
                        "option_type": strategy_kind,      # explicit type (was missing → null)
                        "strike": rep_strike,              # explicit strike (was missing → 0)
                        "legs_spec": strat,  # full strat payload (legs + cost + max_loss + etc)
                        "tte_days": tte_days, "qty": qty,
                        "iv_open": iv, "entry_cost_per_contract": strat_cost,
                        "entry_price": float(abs(strat_cost)),  # per-contract premium for analytics
                        "cost": position_cost,
                        "event_idx": alloc.get("event_idx"),
                        "rationale": str(alloc.get("rationale", ""))[:200],
                        "reasoning_template": prop.get("reasoning_template", ""),
                    })
                    state["bankroll"] -= position_cost
                else:
                    # ── Single-leg (existing) ───────────────────────────
                    opt_type = alloc.get("option_type", "call")
                    if opt_type not in ("call", "put"):
                        continue
                    strike_pct = float(alloc.get("strike_pct", 1.0))
                    if defensive:
                        strike_pct = 1.0
                    strike_pct = max(0.90, min(1.10, strike_pct))
                    strike = spot * strike_pct
                    tte_days = max(1, min(5, tte_days))
                    qty = max(1, min(5 if defensive else 10, int(alloc.get("qty", 1))))

                    entry_price = bs_price(spot, strike, tte_years, iv, opt_type, r=RISK_FREE_RATE)
                    if entry_price < 0.05:
                        continue
                    cost = entry_price * qty * OPTION_MULT
                    max_cost = bankroll * (0.05 if defensive else 0.15)
                    if cost > max_cost:
                        qty = max(1, int(max_cost / (entry_price * OPTION_MULT)))
                        cost = entry_price * qty * OPTION_MULT
                    if cost < MIN_POSITION_COST or cost > bankroll * MAX_DEPLOY_PCT_PER_SESSION:
                        continue

                    positions.append({
                        "tid": tid, "etf": etf, "spot_open": spot, "strike": strike,
                        "option_type": opt_type, "tte_days": tte_days, "qty": qty,
                        "iv_open": iv, "entry_price": entry_price, "cost": cost,
                        "multi_leg": False,
                        "event_idx": alloc.get("event_idx"),
                        "rationale": str(alloc.get("rationale", ""))[:200],
                        "reasoning_template": prop.get("reasoning_template", ""),
                    })
                    state["bankroll"] -= cost
            except Exception as e:
                print(f"[open] {tid} alloc rejected: {e}")

    # Simulate intraday path + mark-to-market
    etf_spot_close = {}
    for etf in etf_spot_open:
        jumps = []
        for i, ev in enumerate(session_events):
            if ev["etf_ticker"] != etf:
                continue
            minute = int((i + 1) / max(1, len(session_events)) * session_minutes * 0.8)
            sig = float(ev.get("signal_strength", 0.3))
            pct = min(0.03, max(0.003, sig * 0.03)) * (ev["direction_bias"] or 1)
            jumps.append((minute, pct))
        iv = etf_iv.get(etf, ETF_BASE_IV)
        seed = hash((date, session_id, etf)) & 0xFFFFFFFF
        if jumps:
            path = jump_path(etf_spot_open[etf], iv, session_minutes, jumps, seed=seed)
        else:
            path = gbm_path(etf_spot_open[etf], iv, session_minutes, seed=seed)
        etf_spot_close[etf] = path[-1]

    stops_triggered = 0
    for pos in positions:
        spot_close = etf_spot_close.get(pos["etf"], pos["spot_open"])
        tte_remaining = max(0.0, (pos["tte_days"] - 0.25) / 252.0)

        if pos.get("multi_leg"):
            mk = mark_position(pos["legs_spec"], spot_close, tte_remaining,
                               pos["iv_open"], r=RISK_FREE_RATE, multiplier=OPTION_MULT)
            # mk.pnl is per contract over multiplier; scale by qty
            pnl = mk["pnl"] * pos["qty"]
            if check_stop_loss(pos["entry_cost_per_contract"], mk["pnl"], pct_threshold=-0.5):
                stops_triggered += 1
                pos["stopped_out"] = True
            pos["spot_close"] = spot_close
            pos["mark"] = mk["mark_per_share"]
            pos["pnl"] = pnl
            pos["net_greeks"] = mk["net_greeks"]
        else:
            mark = bs_price(spot_close, pos["strike"], tte_remaining, pos["iv_open"],
                            pos["option_type"], r=RISK_FREE_RATE)
            pnl = option_pnl(pos["entry_price"], mark, pos["qty"], OPTION_MULT, side="long")
            pos["spot_close"] = spot_close
            pos["mark"] = mark
            pos["pnl"] = pnl
        agents_state[pos["tid"]]["bankroll"] += pos["cost"] + pnl

    # Portfolio VaR across open positions for this session
    var_input = []
    for pos in positions:
        if pos.get("multi_leg") and pos.get("net_greeks"):
            var_input.append({
                "spot": pos.get("spot_close", pos["spot_open"]),
                "iv":   pos.get("iv_open", ETF_BASE_IV),
                "net_greeks": pos["net_greeks"],
            })
        elif not pos.get("multi_leg"):
            # rough single-leg delta proxy (use 0.5 for ATM; refinable)
            d_sign = 1 if pos.get("option_type") == "call" else -1
            var_input.append({
                "spot": pos.get("spot_close", pos["spot_open"]),
                "iv":   pos.get("iv_open", ETF_BASE_IV),
                "net_greeks": {"delta": 0.5 * d_sign * pos.get("qty", 1)},
            })
    session_var95 = portfolio_var(var_input, 0.95) if var_input else 0.0

    return {
        "date": date, "session_id": session_id,
        "n_events": len(session_events),
        "etf_spot_open": etf_spot_open, "etf_spot_close": etf_spot_close, "etf_iv": etf_iv,
        "positions": positions,
        "pacts": [{"pair": list(k), **v} for k, v in pacts.items()],
        "risk": {
            "var_95_1d": round(session_var95, 2),
            "stops_triggered": stops_triggered,
            "n_multi_leg": sum(1 for p in positions if p.get("multi_leg")),
            "n_single_leg": sum(1 for p in positions if not p.get("multi_leg")),
        },
    }


def run_day(agents_state: Dict, date: str, day_events: Dict[str, List[Dict]]) -> Dict:
    session_minutes = (150, 150, 90, 240)
    day_log = {"date": date, "sessions": [],
               "agents_start": {tid: s["bankroll"] for tid, s in agents_state.items()}}

    seed = hash(date) & 0xFFFFFFFF
    rng = random.Random(seed)
    etf_spot = {t: s * (1 + rng.gauss(0, 0.005)) for t, s in ETF_BASE_SPOT.items()}
    etf_iv_base = dict.fromkeys(ETF_BASE_SPOT, ETF_BASE_IV)

    for session_id in range(1, 5):
        sess_events = day_events.get(f"s{session_id}", [])
        enriched = [enrich_event_for_quant(e) for e in sess_events]

        etf_iv = dict(etf_iv_base)
        for ev in enriched:
            etf = ev["etf_ticker"]
            scaled = scale_iv_for_event(etf_iv[etf], ev["iv_category"])
            etf_iv[etf] = max(etf_iv[etf], scaled)

        session_result = run_session(agents_state, date, session_id, enriched,
                                     dict(etf_spot), etf_iv, session_minutes[session_id - 1])
        day_log["sessions"].append(session_result)

        for etf, close in session_result["etf_spot_close"].items():
            etf_spot[etf] = close

    day_log["agents_end"] = {tid: s["bankroll"] for tid, s in agents_state.items()}
    day_log["etf_spot_final"] = etf_spot
    return day_log


# ── Self-test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    def fake_llm(agent, prompt):
        # Deterministic proposals — distinct reasoning templates to test DMAD pact
        personalities = {
            "qwen-quant": "momentum", "llama-contra": "mean-reversion",
            "gemini-anl": "vol-expansion", "mistral-large": "sector-rotation",
            "mistral-medium": "macro-hedge", "mistral-nemo": "momentum",
        }
        # Exercise Phase 2 strategies — one per agent to test all code paths
        strat_by_tid = {
            "qwen-quant":     {"event_idx": 0, "etf": "XLF", "strategy": "vertical",
                               "option_type": "call", "strike_low_pct": 0.98, "strike_high_pct": 1.03,
                               "tte_days": 5, "qty": 3, "rationale": "bull call"},
            "llama-contra":   {"event_idx": 0, "etf": "XLF", "option_type": "put",
                               "strike_pct": 0.99, "tte_days": 3, "qty": 5, "rationale": "single put"},
            "gemini-anl":     {"event_idx": 0, "etf": "XLF", "strategy": "straddle",
                               "side": "long", "strike_pct": 1.0, "tte_days": 5, "qty": 2,
                               "rationale": "long vol"},
            "mistral-large":  {"event_idx": 0, "etf": "XLF", "strategy": "iron_condor",
                               "put_long_pct": 0.92, "put_short_pct": 0.97,
                               "call_short_pct": 1.03, "call_long_pct": 1.08,
                               "tte_days": 7, "qty": 2, "rationale": "range-bound"},
            "mistral-medium": {"event_idx": 0, "etf": "XLF", "strategy": "butterfly",
                               "option_type": "call", "strike_low_pct": 0.97,
                               "strike_mid_pct": 1.0, "strike_high_pct": 1.03,
                               "tte_days": 5, "qty": 2, "rationale": "pin play"},
            "mistral-nemo":   {"event_idx": 0, "etf": "XLF", "option_type": "call",
                               "strike_pct": 1.01, "tte_days": 4, "qty": 10,
                               "rationale": "single call"},
        }
        return {
            "thesis": f"fake thesis for {agent['tid']}",
            "reasoning_template": personalities[agent["tid"]],
            "allocations": [strat_by_tid[agent["tid"]]],
            "coalition_proposal": {"peer": "llama-contra" if agent["tid"] == "qwen-quant" else None,
                                    "event_idx": 0, "etf": "XLF", "option_type": "call"},
        }
    set_call_llm(fake_llm)

    events = load_events("data/political_events.json")
    days = all_days(events)
    date0 = sorted(days.keys())[0]
    agents_state = {a["tid"]: {"bankroll": STARTING_BANKROLL, "wins": 0, "losses": 0}
                    for a in AGENTS}
    print(f"[engine] Dry-run day {date0}")
    day_log = run_day(agents_state, date0, days[date0])
    total_positions = sum(len(s["positions"]) for s in day_log["sessions"])
    total_pacts = sum(len(s["pacts"]) for s in day_log["sessions"])
    total_pnl = sum(p["pnl"] for s in day_log["sessions"] for p in s["positions"])
    print(f"[engine] {len(day_log['sessions'])} sessions, {total_positions} positions, "
          f"{total_pacts} pacts, total PnL ${total_pnl:+,.2f}")
    for tid, s in sorted(agents_state.items(), key=lambda x: -x[1]["bankroll"]):
        delta = s["bankroll"] - STARTING_BANKROLL
        print(f"  {tid:16} ${s['bankroll']:>10,.0f}  ({delta:+,.0f})")
    # Assertions
    assert total_positions > 0, "should open at least some positions"
    assert all(100 < s["bankroll"] < 200_000 for s in agents_state.values()), "bankrolls in sane range"
    # Pact must only form between DIFFERENT reasoning templates — qwen/llama differ so 1 pact expected
    assert total_pacts >= 1, f"DMAD pact should form (got {total_pacts})"
    print("[engine] all assertions pass")
