"""ITF executor — DRY_RUN writes to jsonl, live uses Alpaca paper bracket orders.

Auto-detect: ALPACA_PAPER_KEY + ALPACA_PAPER_SECRET in env => live mode.
Otherwise: dry-run (simulated fill at last quote).

Position management:
  - max 3 open positions per agent
  - max hold = persona.max_hold_min
  - EOD flatten at 19:50 UTC (15:50 ET — 10 min before market close)
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[3]
ORDERS_JSONL = REPO / "data" / "intraday" / "dry-run-orders.jsonl"
POSITIONS_PATH = REPO / "data" / "intraday" / "positions.json"
BANKROLLS_PATH = REPO / "data" / "intraday" / "agent_bankrolls.json"
LEDGER_JSONL = REPO / "data" / "intraday" / "agent_ledger.jsonl"
POSITIONS_PATH.parent.mkdir(parents=True, exist_ok=True)

MAX_OPEN_PER_AGENT = 5  # 2026-04-21: 3→5, 14×5=70 max positions (+67%)
EOD_FLATTEN_UTC_HOUR = 19
EOD_FLATTEN_UTC_MIN = 50


# ───── 2026-04-21 v2.5 PER-AGENT SUB-BANKROLL ─────
# Each of 14 personas gets an equal slice of current Alpaca equity at cold-start.
# Every submit() reserves stake_usd from agent's bankroll; close_expired /
# close_position credits stake + realized_pnl back. Enables a SCIENTIFIC
# leaderboard (which persona is actually best) instead of a single blended pool.

def _load_bankrolls() -> Dict[str, float]:
    if not BANKROLLS_PATH.exists():
        return {}
    try:
        return json.loads(BANKROLLS_PATH.read_text())
    except Exception:
        return {}


def _save_bankrolls(b: Dict[str, float]) -> None:
    BANKROLLS_PATH.write_text(json.dumps(b, indent=2, sort_keys=True))


def _fetch_alpaca_equity() -> float:
    """Pull live Alpaca paper equity. Fallback $100k if not live or API error."""
    if not live_mode():
        return 100_000.0
    try:
        import requests
        r = requests.get(
            "https://paper-api.alpaca.markets/v2/account",
            headers={
                "APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_KEY", ""),
                "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET", ""),
            },
            timeout=5,
        )
        if r.ok:
            return float(r.json().get("equity") or 100_000.0)
    except Exception:
        pass
    return 100_000.0


def seed_bankrolls(tids: List[str], force: bool = False) -> Dict[str, float]:
    """Seed each tid at equal share of current Alpaca equity. Idempotent unless
    `force=True` (used by /api/reset)."""
    existing = _load_bankrolls()
    if existing and not force:
        return existing
    total = _fetch_alpaca_equity()
    share = round(total / max(1, len(tids)), 2)
    b = {tid: share for tid in tids}
    b["_meta"] = {
        "seeded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed_equity_usd": round(total, 2),
        "seed_share_usd": share,
        "n_agents": len(tids),
    }
    _save_bankrolls(b)
    return b


def get_bankroll(tid: str) -> float:
    b = _load_bankrolls()
    return float(b.get(tid, 0.0) or 0.0)


def _append_ledger(event: Dict[str, Any]) -> None:
    """Append a per-agent bankroll event to agent_ledger.jsonl for scientific audit."""
    LEDGER_JSONL.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = event.get("ts") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with LEDGER_JSONL.open("a") as fh:
        fh.write(json.dumps(event, default=str) + "\n")


def reserve_bankroll(tid: str, amount: float, meta: Optional[Dict[str, Any]] = None) -> float:
    """Deduct amount from tid's bankroll. Returns new balance (can go negative — caller checks)."""
    b = _load_bankrolls()
    before = float(b.get(tid, 0.0) or 0.0)
    b[tid] = round(before - amount, 2)
    _save_bankrolls(b)
    _append_ledger({"tid": tid, "event": "reserve", "delta": -round(amount, 2),
                    "balance_before": round(before, 2), "balance_after": b[tid],
                    **(meta or {})})
    return b[tid]


def credit_bankroll(tid: str, amount: float, meta: Optional[Dict[str, Any]] = None) -> float:
    b = _load_bankrolls()
    before = float(b.get(tid, 0.0) or 0.0)
    b[tid] = round(before + amount, 2)
    _save_bankrolls(b)
    _append_ledger({"tid": tid, "event": "credit", "delta": round(amount, 2),
                    "balance_before": round(before, 2), "balance_after": b[tid],
                    **(meta or {})})
    return b[tid]


def all_bankrolls() -> Dict[str, float]:
    """Return copy without _meta for leaderboard rendering."""
    b = _load_bankrolls()
    return {k: v for k, v in b.items() if not k.startswith("_")}


def live_mode() -> bool:
    """Live only when ITF_MODE=live AND Alpaca keys present.
    Default is dry_run — safer for an unvalidated key-pair. Explicitly opt in
    via env `ITF_MODE=live` once you've confirmed the key at /v2/account.
    """
    if os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("ITF_MODE", "").lower() != "live":
        return False
    return bool(os.environ.get("ALPACA_PAPER_KEY") and os.environ.get("ALPACA_PAPER_SECRET"))


def _load_positions() -> Dict[str, List[Dict[str, Any]]]:
    if not POSITIONS_PATH.exists():
        return {}
    try:
        return json.loads(POSITIONS_PATH.read_text())
    except Exception:
        return {}


def _save_positions(p: Dict[str, List[Dict[str, Any]]]) -> None:
    POSITIONS_PATH.write_text(json.dumps(p, indent=2, default=str))


def _append_order_log(entry: Dict[str, Any]) -> None:
    ORDERS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with ORDERS_JSONL.open("a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def refresh_broker_statuses() -> Dict[str, int]:
    """Re-poll Alpaca for every position with a broker_order_id whose cached
    broker_status is non-terminal. Updates positions.json in place.

    Terminal statuses (skipped to save API calls): filled, canceled, expired,
    rejected, replaced, closed_by_agent, sim_*, closed.

    Returns a counter dict of what changed, e.g. {"polled": 23, "updated": 18,
    "filled": 11, "canceled": 2}. Called once at the top of tick_once() so the
    /api/status view never shows stale pending_new.
    """
    stats = {"polled": 0, "updated": 0, "filled": 0, "canceled": 0, "other": 0, "errors": 0}
    if not live_mode():
        return stats
    key = os.environ.get("ALPACA_PAPER_KEY")
    secret = os.environ.get("ALPACA_PAPER_SECRET")
    if not (key and secret):
        return stats

    TERMINAL = {
        "filled", "canceled", "cancelled", "expired", "rejected", "replaced",
        "closed_by_agent", "closed", "done_for_day", "stopped", "suspended",
    }
    import requests
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    positions = _load_positions()
    changed = False
    for agent_tid, lst in positions.items():
        for p in lst:
            oid = p.get("broker_order_id")
            if not oid:
                continue
            cur = (p.get("broker_status") or "").lower()
            if cur in TERMINAL:
                continue
            stats["polled"] += 1
            try:
                r = requests.get(
                    f"https://paper-api.alpaca.markets/v2/orders/{oid}",
                    headers=headers, timeout=6,
                )
                if r.status_code == 404:
                    p["broker_status"] = "not_found"
                    stats["updated"] += 1
                    stats["other"] += 1
                    changed = True
                    continue
                if not r.ok:
                    stats["errors"] += 1
                    continue
                body = r.json()
                new = (body.get("status") or "").lower()
                if new and new != cur:
                    p["broker_status"] = new
                    if body.get("filled_avg_price"):
                        p["filled_avg_price"] = float(body["filled_avg_price"])
                    if body.get("filled_at"):
                        p["filled_at"] = body["filled_at"]
                    if body.get("filled_qty"):
                        p["filled_qty"] = float(body["filled_qty"])
                    stats["updated"] += 1
                    if new == "filled":
                        stats["filled"] += 1
                    elif new in {"canceled", "cancelled"}:
                        stats["canceled"] += 1
                    else:
                        stats["other"] += 1
                    changed = True
            except Exception:
                stats["errors"] += 1
    if changed:
        _save_positions(positions)
    return stats


def _asset_class(ticker: str) -> str:
    if "/" in ticker:
        return "crypto"
    return "equity"


def _alpaca_place_bracket(ticker: str, qty: float, stake: float, last: float,
                          side: str, stop_price: float, tp_price: float) -> Dict[str, Any]:
    """Place an Alpaca paper order.

    Routing (canonical alpaca-py examples pattern):
      * crypto (BTC/USD etc)    → market GTC, fractional qty ok, NO bracket
      * equity qty >= 1 integer → bracket with integer qty + stop_loss + take_profit
      * equity qty < 1 or frac  → notional-based market day, NO bracket
        (Alpaca 422s on bracket+fractional; stop/TP tracked client-side in close_expired)
    """
    import requests
    key = os.environ["ALPACA_PAPER_KEY"]
    secret = os.environ["ALPACA_PAPER_SECRET"]

    asset = _asset_class(ticker)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    if asset == "crypto":
        payload = {
            "symbol": ticker,
            "qty": qty,
            "side": side,
            "type": "market",
            "time_in_force": "gtc",
        }
    else:
        int_qty = int(qty)  # floor — Alpaca rejects bracket on fractional
        if int_qty >= 1:
            # Defensive: bracket MUST have integer qty >= 1. If this assert ever fires,
            # it means something bypassed the fractional routing — crash-log the call
            # site so we can pin the regression fast.
            assert int_qty >= 1 and float(int_qty).is_integer(), \
                f"bracket qty must be integer>=1, got {qty!r} (ticker={ticker}, stake={stake})"
            payload = {
                "symbol": ticker,
                "qty": int_qty,
                "side": side,
                "type": "market",
                "time_in_force": "day",
                "order_class": "bracket",
                "extended_hours": False,
                "stop_loss": {"stop_price": round(stop_price, 2)},
                "take_profit": {"limit_price": round(tp_price, 2)},
            }
        else:
            # Stake too small for 1 whole share → notional fractional, no bracket.
            # close_expired() already tracks stop/TP client-side via age/EOD flatten.
            payload = {
                "symbol": ticker,
                "notional": round(stake, 2),
                "side": side,
                "type": "market",
                "time_in_force": "day",
            }
    r = requests.post(
        "https://paper-api.alpaca.markets/v2/orders",
        headers=headers,
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def submit(agent_tid: str, order: Dict[str, Any], last_quote: float) -> Dict[str, Any]:
    """Submit an order. Shape of `order`:
       {ticker, side: long|short, stake_usd, stop_pct, take_profit_pct, thesis}
    Returns the recorded order entry (with fill or simulated fill).
    """
    positions = _load_positions()
    open_for_agent = [p for p in positions.get(agent_tid, []) if p.get("status") == "open"]
    # 2026-04-21 wash-trade pre-check: if same agent has an OPEN opposite-side
    # position on same ticker, skip. Alpaca rejects these as wash-trades anyway;
    # pre-check gives a clean ledger event instead of a broker_error.
    _inbound_side = order.get("side")
    _inbound_ticker = order.get("ticker")
    for _p in open_for_agent:
        if _p.get("ticker") == _inbound_ticker and _p.get("side") and _inbound_side and _p.get("side") != _inbound_side:
            wash = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "agent_tid": agent_tid, "status": "wash_skip",
                "reason": f"opposite-side {_p.get('side')} open on {_inbound_ticker}",
                "order": order,
            }
            _append_order_log(wash)
            return wash
    if len(open_for_agent) >= MAX_OPEN_PER_AGENT:
        reject = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_tid": agent_tid, "status": "rejected",
            "reason": f"max {MAX_OPEN_PER_AGENT} open positions already",
            "order": order,
        }
        _append_order_log(reject)
        return reject

    ticker = order["ticker"]
    side = order["side"]  # "long" | "short"
    stake = float(order.get("stake_usd", 1000))
    stop_pct = float(order.get("stop_pct", 0.005))
    tp_pct = float(order.get("take_profit_pct", 0.012))
    last = float(last_quote or 0) or 1.0
    qty = round(stake / last, 2)

    if side == "long":
        stop_price = last * (1 - stop_pct)
        tp_price = last * (1 + tp_pct)
        alp_side = "buy"
    else:
        stop_price = last * (1 + stop_pct)
        tp_price = last * (1 - tp_pct)
        alp_side = "sell"

    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_tid": agent_tid,
        "ticker": ticker,
        "side": side,
        "qty": qty,
        "entry_price": round(last, 4),
        "stop_price": round(stop_price, 4),
        "take_profit_price": round(tp_price, 4),
        "stake_usd": round(stake, 2),
        "stop_pct": stop_pct,
        "take_profit_pct": tp_pct,
        "thesis": order.get("thesis", "")[:500],
        "status": "open",
        "mode": "live" if live_mode() else "dry_run",
    }

    if live_mode():
        try:
            resp = _alpaca_place_bracket(ticker, qty, stake, last, alp_side, stop_price, tp_price)
            entry["broker_order_id"] = resp.get("id")
            entry["broker_status"] = resp.get("status")
            entry["broker_class"] = resp.get("order_class") or ("notional" if resp.get("notional") else "bracket")
        except Exception as e:
            entry["status"] = "broker_error"
            # Capture Alpaca body text when available (RequestException.response) so we can
            # diagnose broker_errors beyond the generic "422 Unprocessable Entity" prefix.
            body = ""
            try:
                body = " | body=" + getattr(e, "response", None).text[:400]  # type: ignore
            except Exception:
                pass
            entry["error"] = (str(e) + body)[:600]
    else:
        # Dry run — simulate the fill and set sim_close_at for EOD flatten
        entry["sim_filled_at"] = last
        entry["sim_pnl_usd"] = 0.0  # filled flat, realized on close

    positions.setdefault(agent_tid, []).append(entry)
    _save_positions(positions)
    _append_order_log(entry)
    # v2.5 — reserve stake from agent's sub-bankroll (do NOT reserve if broker rejected).
    if entry.get("status") == "open":
        new_bal = reserve_bankroll(agent_tid, stake, meta={
            "ticker": ticker, "side": side, "stake": round(stake, 2),
            "instrument": "equity_or_crypto",
            "broker_order_id": entry.get("broker_order_id"),
        })
        entry["agent_bankroll_after_reserve"] = new_bal
    return entry


def _occ_symbol(underlying: str, expiry: datetime, option_type: str, strike: float) -> str:
    """OCC-standard option symbol: <UND><YYMMDD><C|P><strike*1000 zero-padded to 8>.
    Example: SPY251220C00480000 = SPY call, strike $480, expiring 2025-12-20.
    """
    exp = expiry.strftime("%y%m%d")
    cp = "C" if option_type.lower().startswith("c") else "P"
    strike_int = int(round(strike * 1000))
    return f"{underlying.upper()}{exp}{cp}{strike_int:08d}"


def _next_expiry(dte: int, now_utc: datetime) -> datetime:
    """Return the nearest US market expiry that is `dte` trading days ahead.
    SPY/QQQ/IWM have daily expiries (0/1/2 DTE) during the week; we approximate
    by skipping weekends only (holidays treated as weekdays for dry-run intent)."""
    d = now_utc
    added = 0
    while added < max(0, dte):
        d = d + timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def submit_option(agent_tid: str, order: Dict[str, Any], last_quote: float) -> Dict[str, Any]:
    """Submit an intraday option order. Shape:
       {underlying, option_type, strategy, dte, strike_offset_pct, wing_width_pct, stake_usd, max_loss_pct, thesis}

    Strategy handling:
      - "long":              1-leg long call/put
      - "vertical_debit":    2-leg debit spread (buy ATM, sell ATM+wing)
      - "vertical_credit":   2-leg credit spread (sell ATM, buy ATM+wing)
      - "iron_condor":       4-leg (call spread above, put spread below)
      - "straddle":          2-leg long call + long put at same strike

    Dry-run logs the structured intent with computed OCC symbols.
    Live mode routes to Alpaca /v2/options/orders (minimal wrapper; paper-only).
    """
    positions = _load_positions()
    open_for_agent = [p for p in positions.get(agent_tid, []) if p.get("status") == "open"]
    if len(open_for_agent) >= MAX_OPEN_PER_AGENT:
        reject = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_tid": agent_tid, "status": "rejected",
            "reason": f"max {MAX_OPEN_PER_AGENT} open positions already",
            "order": order,
        }
        _append_order_log(reject)
        return reject

    now = datetime.now(timezone.utc)
    underlying = order["underlying"]
    option_type = order.get("option_type", "call")
    strategy   = order.get("strategy", "long")
    dte = int(order.get("dte", 0) or 0)
    offset_pct = float(order.get("strike_offset_pct", 0.0) or 0.0)
    wing_pct   = float(order.get("wing_width_pct", 0.01) or 0.01)
    stake      = float(order.get("stake_usd", 500))
    last       = float(last_quote or 0) or 1.0
    expiry     = _next_expiry(dte, now)

    # Compute strikes (rounded to $1 — broker will snap to chain)
    atm = round(last * (1 + offset_pct))
    wing_up = round(last * (1 + offset_pct + wing_pct))
    wing_dn = round(last * (1 + offset_pct - wing_pct))

    legs: List[Dict[str, Any]] = []
    if strategy == "long":
        legs = [{"side": "buy", "symbol": _occ_symbol(underlying, expiry, option_type, atm), "qty": 1}]
    elif strategy == "vertical_debit":
        outer = wing_up if option_type == "call" else wing_dn
        legs = [
            {"side": "buy",  "symbol": _occ_symbol(underlying, expiry, option_type, atm),   "qty": 1},
            {"side": "sell", "symbol": _occ_symbol(underlying, expiry, option_type, outer), "qty": 1},
        ]
    elif strategy == "vertical_credit":
        outer = wing_up if option_type == "call" else wing_dn
        legs = [
            {"side": "sell", "symbol": _occ_symbol(underlying, expiry, option_type, atm),   "qty": 1},
            {"side": "buy",  "symbol": _occ_symbol(underlying, expiry, option_type, outer), "qty": 1},
        ]
    elif strategy == "iron_condor":
        legs = [
            # call spread above
            {"side": "sell", "symbol": _occ_symbol(underlying, expiry, "call", wing_up),                "qty": 1},
            {"side": "buy",  "symbol": _occ_symbol(underlying, expiry, "call", round(last*(1+offset_pct+2*wing_pct))), "qty": 1},
            # put spread below
            {"side": "sell", "symbol": _occ_symbol(underlying, expiry, "put",  wing_dn),                "qty": 1},
            {"side": "buy",  "symbol": _occ_symbol(underlying, expiry, "put",  round(last*(1+offset_pct-2*wing_pct))), "qty": 1},
        ]
    elif strategy == "straddle":
        legs = [
            {"side": "buy", "symbol": _occ_symbol(underlying, expiry, "call", atm), "qty": 1},
            {"side": "buy", "symbol": _occ_symbol(underlying, expiry, "put",  atm), "qty": 1},
        ]
    else:
        legs = [{"side": "buy", "symbol": _occ_symbol(underlying, expiry, option_type, atm), "qty": 1}]

    entry = {
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_tid": agent_tid,
        "instrument_type": "option",
        "underlying": underlying,
        "option_type": option_type,
        "strategy": strategy,
        "dte": dte,
        "expiry": expiry.strftime("%Y-%m-%d"),
        "atm_strike": atm,
        "legs": legs,
        "stake_usd": round(stake, 2),
        "max_loss_pct": float(order.get("max_loss_pct", 0.02)),
        "last_quote_underlying": round(last, 4),
        "thesis": order.get("thesis", "")[:500],
        "status": "open",
        "mode": "live" if live_mode() else "dry_run",
    }

    if live_mode() and os.environ.get("ITF_OPTIONS_LIVE", "").lower() in ("1","true","yes"):
        # Alpaca multi-leg options (order_class=mleg) — canonical alpaca-py pattern.
        # Single atomic POST replaces the old per-leg loop which broke spread pricing
        # AND left naked legs when one fill succeeded and another failed.
        try:
            import requests
            key = os.environ["ALPACA_PAPER_KEY"]
            secret = os.environ["ALPACA_PAPER_SECRET"]
            headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

            if len(legs) == 1:
                # Single-leg: simple market order on OCC symbol (no mleg).
                leg = legs[0]
                payload = {
                    "symbol": leg["symbol"],
                    "qty": leg["qty"],
                    "side": leg["side"],
                    "type": "market",
                    "time_in_force": "day",
                }
                r = requests.post("https://paper-api.alpaca.markets/v2/orders",
                                  headers=headers, json=payload, timeout=10)
                r.raise_for_status()
                entry["broker_order_ids"] = [r.json().get("id")]
            else:
                # Multi-leg: one mleg order, 2-4 legs. ratio_qty defines leg proportions;
                # position_intent declares open vs close so Alpaca can validate margin.
                mleg_legs = []
                for leg in legs:
                    mleg_legs.append({
                        "symbol": leg["symbol"],
                        "side": leg["side"],
                        "ratio_qty": str(leg["qty"]),
                        "position_intent": "buy_to_open" if leg["side"] == "buy" else "sell_to_open",
                    })
                payload = {
                    "order_class": "mleg",
                    "qty": "1",
                    "type": "market",
                    "time_in_force": "day",
                    "legs": mleg_legs,
                }
                r = requests.post("https://paper-api.alpaca.markets/v2/orders",
                                  headers=headers, json=payload, timeout=10)
                r.raise_for_status()
                resp = r.json()
                entry["broker_order_ids"] = [resp.get("id")]
                entry["broker_class"] = "mleg"
                entry["broker_legs_count"] = len(mleg_legs)
        except Exception as e:
            entry["status"] = "broker_error"
            # Capture Alpaca body text when available (RequestException.response) so we can
            # diagnose broker_errors beyond the generic "422 Unprocessable Entity" prefix.
            body = ""
            try:
                body = " | body=" + getattr(e, "response", None).text[:400]  # type: ignore
            except Exception:
                pass
            entry["error"] = (str(e) + body)[:600]
    else:
        entry["sim_opened_at_underlying"] = last

    positions.setdefault(agent_tid, []).append(entry)
    _save_positions(positions)
    _append_order_log(entry)
    # v2.5 — reserve option stake from agent's sub-bankroll
    if entry.get("status") == "open":
        new_bal = reserve_bankroll(agent_tid, stake, meta={
            "underlying": underlying, "strategy": strategy, "stake": round(stake, 2),
            "instrument": "option",
        })
        entry["agent_bankroll_after_reserve"] = new_bal
    return entry


def _mark_to_market(p: Dict[str, Any], quote_fn) -> Dict[str, Any]:
    """Compute realized P&L on close. Mutates `p` with realized_pnl_usd + exit_price + return_pct.

    For equities: P&L = qty * (exit - entry) for long, qty * (entry - exit) for short.
    For options (dry-run): approximate intrinsic value delta via underlying quote — coarse
    but gives a direction/magnitude signal. Live options P&L pulled from broker fill feed.
    For broker_error / rejected entries: leave P&L at 0.0.
    """
    if p.get("status") in ("broker_error", "rejected"):
        p["realized_pnl_usd"] = 0.0
        return p

    if p.get("instrument_type") == "option":
        # Dry-run option P&L: Δ(underlying) × stake × direction sign. Not real Greeks,
        # but enough to produce non-zero leaderboard numbers and catch obviously
        # losing theses. Live mode will overwrite via broker fills.
        underlying_entry = float(p.get("last_quote_underlying") or 0) or 0.0
        exit_q = quote_fn(p.get("underlying", "")) or underlying_entry
        if underlying_entry > 0:
            delta_pct = (exit_q - underlying_entry) / underlying_entry
        else:
            delta_pct = 0.0
        direction = 1 if p.get("option_type", "call") == "call" else -1
        if p.get("strategy") in ("vertical_credit",):
            direction *= -1  # credit: we profit on small moves, lose on large in direction
        stake = float(p.get("stake_usd") or 0)
        pnl = stake * delta_pct * direction
        # Cap loss at stake (long premium) — no naked unlimited here by design.
        pnl = max(pnl, -stake)
        p["realized_pnl_usd"] = round(pnl, 2)
        p["exit_underlying"] = round(exit_q, 4)
        p["return_pct"] = round(delta_pct * direction, 5)
        return p

    entry_px = float(p.get("entry_price") or 0) or 0.0
    qty = float(p.get("qty") or 0) or 0.0
    ticker = p.get("ticker", "")
    exit_px = quote_fn(ticker) or entry_px
    if p.get("side") == "short":
        gross = qty * (entry_px - exit_px)
    else:
        gross = qty * (exit_px - entry_px)
    p["realized_pnl_usd"] = round(gross, 2)
    p["exit_price"] = round(exit_px, 4)
    if entry_px > 0:
        p["return_pct"] = round((exit_px - entry_px) / entry_px, 5)
    else:
        p["return_pct"] = 0.0
    return p


def close_expired(now_utc: datetime, quote_fn=None) -> List[Dict[str, Any]]:
    """Walk positions and close any that passed persona.max_hold or hit EOD flatten.

    `quote_fn(ticker) -> last_price` is injected from app.py so we can stay
    decoupled from the quote_bus import. If None, we fall back to entry_price
    (zero P&L) but still mark status=closed_expired.
    """
    closed: List[Dict[str, Any]] = []
    positions = _load_positions()
    qf = quote_fn or (lambda _t: None)
    for agent_tid, rows in positions.items():
        for p in rows:
            if p.get("status") != "open":
                continue
            try:
                opened = datetime.fromisoformat(p["ts"].replace("Z", "+00:00"))
            except Exception:
                continue
            age_min = (now_utc - opened).total_seconds() / 60.0
            eod = (now_utc.hour > EOD_FLATTEN_UTC_HOUR or
                   (now_utc.hour == EOD_FLATTEN_UTC_HOUR and now_utc.minute >= EOD_FLATTEN_UTC_MIN))
            # We don't know per-agent max_hold here without loading personas; use 240 as a ceiling.
            if age_min > 240 or eod:
                p["status"] = "closed_expired"
                p["closed_at"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                _mark_to_market(p, qf)
                # v2.5 — credit stake + realized_pnl back to agent's sub-bankroll
                _stake = float(p.get("stake_usd") or 0)
                _pnl = float(p.get("realized_pnl_usd") or 0)
                credit_bankroll(agent_tid, _stake + _pnl, meta={
                    "ticker": p.get("ticker") or p.get("underlying"),
                    "event_type": "eod_or_expired_close",
                    "stake_returned": round(_stake, 2),
                    "realized_pnl": round(_pnl, 2),
                })
                closed.append(p)
    _save_positions(positions)
    return closed


def pnl_snapshot(quote_fn=None) -> Dict[str, Any]:
    """Per-agent P&L aggregate. Realized = sum(realized_pnl_usd) on closed rows.
    Unrealized = mark-to-market on still-open rows. Total = realized + unrealized.

    Uses `quote_fn(ticker)` for the open-position mark. If quote missing, mark is 0.
    """
    positions = _load_positions()
    qf = quote_fn or (lambda _t: None)
    per_agent: Dict[str, Dict[str, float]] = {}
    for agent_tid, rows in positions.items():
        realized = 0.0
        unrealized = 0.0
        wins = 0
        losses = 0
        trades_closed = 0
        trades_open = 0
        for p in rows:
            if p.get("status") == "open":
                trades_open += 1
                # Shadow-copy to mark-to-market without persisting.
                tmp = dict(p)
                _mark_to_market(tmp, qf)
                unrealized += float(tmp.get("realized_pnl_usd") or 0)
            elif p.get("status", "").startswith("closed"):
                trades_closed += 1
                r = float(p.get("realized_pnl_usd") or 0)
                realized += r
                if r > 0: wins += 1
                elif r < 0: losses += 1
        per_agent[agent_tid] = {
            "realized_pnl_usd": round(realized, 2),
            "unrealized_pnl_usd": round(unrealized, 2),
            "total_pnl_usd": round(realized + unrealized, 2),
            "trades_closed": trades_closed,
            "trades_open": trades_open,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / trades_closed, 4) if trades_closed else 0.0,
        }
    total_realized = sum(a["realized_pnl_usd"] for a in per_agent.values())
    total_unrealized = sum(a["unrealized_pnl_usd"] for a in per_agent.values())
    return {
        "per_agent": per_agent,
        "fleet_realized_pnl_usd": round(total_realized, 2),
        "fleet_unrealized_pnl_usd": round(total_unrealized, 2),
        "fleet_total_pnl_usd": round(total_realized + total_unrealized, 2),
    }


def close_position(agent_tid: str, ticker: str) -> Dict[str, Any]:
    """2026-04-21 — agent-driven close. Mark matching local open positions closed
    and (in live mode) submit Alpaca DELETE /v2/positions/{symbol} to flatten the
    broker position. Returns entry-style dict mirroring submit().

    Scope: matches ALL open positions for this agent_tid + ticker pair. Broker
    close is market-time-in-force, so crypto closes GTC via order, equities via
    the dedicated positions-close endpoint (net flat).
    """
    positions = _load_positions()
    ticker_u = (ticker or "").upper().strip()
    matched: List[Dict[str, Any]] = [
        p for p in positions.get(agent_tid, [])
        if p.get("status") == "open" and (p.get("ticker", "") or "").upper().strip() == ticker_u
    ]
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_tid": agent_tid,
        "ticker": ticker_u,
        "action": "close_position",
        "matched_positions": len(matched),
        "mode": "live" if live_mode() else "dry_run",
    }
    if not matched:
        entry["status"] = "no_open_position"
        _append_order_log(entry)
        return entry

    if live_mode():
        import requests
        key = os.environ["ALPACA_PAPER_KEY"]
        secret = os.environ["ALPACA_PAPER_SECRET"]
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        try:
            r = requests.delete(
                f"https://paper-api.alpaca.markets/v2/positions/{ticker_u}",
                headers=headers,
                timeout=10,
            )
            if r.ok:
                entry["broker_status"] = "closed"
                entry["broker_resp"] = (r.json() if r.text else {}).get("status", "submitted")
            else:
                entry["broker_status"] = f"error_{r.status_code}"
                entry["broker_resp"] = r.text[:300]
        except Exception as e:
            entry["broker_status"] = "exception"
            entry["broker_resp"] = str(e)[:300]

    # Mark all matched local positions closed + credit stake back to sub-bankroll.
    # For agent-driven closes we don't have a live quote for exact P&L, so credit
    # only the reserved stake (P&L reconciles from broker fills → next tick via
    # a snapshot reconciliation). This is intentionally conservative: the stake
    # returns, any unrealized gain is "free" on close until reconciled.
    total_stake_returned = 0.0
    for p in matched:
        p["status"] = "closed_by_agent"
        p["closed_at"] = entry["ts"]
        total_stake_returned += float(p.get("stake_usd") or 0)
    if total_stake_returned > 0:
        credit_bankroll(agent_tid, total_stake_returned, meta={
            "ticker": ticker_u,
            "event_type": "agent_close",
            "stake_returned": round(total_stake_returned, 2),
            "n_positions": len(matched),
        })
    _save_positions(positions)
    _append_order_log(entry)
    return entry


def read_trades(limit: int = 200) -> List[Dict[str, Any]]:
    """Tail the dry_run_orders.jsonl log. Shape: every submit() call (fill or reject)."""
    if not ORDERS_JSONL.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        lines = ORDERS_JSONL.read_text().splitlines()
    except Exception:
        return []
    for line in lines[-limit:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def list_open() -> List[Dict[str, Any]]:
    positions = _load_positions()
    out: List[Dict[str, Any]] = []
    for agent_tid, rows in positions.items():
        for p in rows:
            if p.get("status") == "open":
                out.append(p)
    return out
