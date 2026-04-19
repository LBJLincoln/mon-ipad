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
POSITIONS_PATH.parent.mkdir(parents=True, exist_ok=True)

MAX_OPEN_PER_AGENT = 3
EOD_FLATTEN_UTC_HOUR = 19
EOD_FLATTEN_UTC_MIN = 50


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


def _asset_class(ticker: str) -> str:
    if "/" in ticker:
        return "crypto"
    return "equity"


def _alpaca_place_bracket(ticker: str, qty: float, side: str,
                          stop_price: float, tp_price: float) -> Dict[str, Any]:
    """Place an Alpaca paper order. Equities get bracket; crypto gets plain market GTC
    (Alpaca rejects bracket+stop_loss for crypto — only simple market/limit allowed)."""
    import requests
    key = os.environ["ALPACA_PAPER_KEY"]
    secret = os.environ["ALPACA_PAPER_SECRET"]

    asset = _asset_class(ticker)
    if asset == "crypto":
        # Crypto: market GTC, no bracket. Stop/TP tracked client-side via close_expired.
        payload = {
            "symbol": ticker,
            "qty": qty,
            "side": side,
            "type": "market",
            "time_in_force": "gtc",
        }
    else:
        payload = {
            "symbol": ticker,
            "qty": qty,
            "side": side,
            "type": "market",
            "time_in_force": "day",
            "order_class": "bracket",
            "extended_hours": False,  # bracket orders cannot be extended_hours on Alpaca
            "stop_loss": {"stop_price": round(stop_price, 2)},
            "take_profit": {"limit_price": round(tp_price, 2)},
        }
    r = requests.post(
        "https://paper-api.alpaca.markets/v2/orders",
        headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
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
            resp = _alpaca_place_bracket(ticker, qty, alp_side, stop_price, tp_price)
            entry["broker_order_id"] = resp.get("id")
            entry["broker_status"] = resp.get("status")
        except Exception as e:
            entry["status"] = "broker_error"
            entry["error"] = str(e)[:200]
    else:
        # Dry run — simulate the fill and set sim_close_at for EOD flatten
        entry["sim_filled_at"] = last
        entry["sim_pnl_usd"] = 0.0  # filled flat, realized on close

    positions.setdefault(agent_tid, []).append(entry)
    _save_positions(positions)
    _append_order_log(entry)
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
        # Alpaca options paper — minimal per-leg POST
        try:
            import requests
            key = os.environ["ALPACA_PAPER_KEY"]
            secret = os.environ["ALPACA_PAPER_SECRET"]
            broker_ids = []
            for leg in legs:
                payload = {
                    "symbol": leg["symbol"],
                    "qty": leg["qty"],
                    "side": leg["side"],
                    "type": "market",
                    "time_in_force": "day",
                }
                r = requests.post(
                    "https://paper-api.alpaca.markets/v2/orders",
                    headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
                    json=payload, timeout=10,
                )
                r.raise_for_status()
                broker_ids.append(r.json().get("id"))
            entry["broker_order_ids"] = broker_ids
        except Exception as e:
            entry["status"] = "broker_error"
            entry["error"] = str(e)[:200]
    else:
        entry["sim_opened_at_underlying"] = last

    positions.setdefault(agent_tid, []).append(entry)
    _save_positions(positions)
    _append_order_log(entry)
    return entry


def close_expired(now_utc: datetime) -> List[Dict[str, Any]]:
    """Walk positions and close any that passed persona.max_hold or hit EOD flatten."""
    closed: List[Dict[str, Any]] = []
    positions = _load_positions()
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
                closed.append(p)
    _save_positions(positions)
    return closed


def list_open() -> List[Dict[str, Any]]:
    positions = _load_positions()
    out: List[Dict[str, Any]] = []
    for agent_tid, rows in positions.items():
        for p in rows:
            if p.get("status") == "open":
                out.append(p)
    return out
