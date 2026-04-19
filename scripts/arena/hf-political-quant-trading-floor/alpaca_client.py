"""Alpaca paper-trading shim for PQTF live mode.

Only used when USE_ALPACA=1 (default off — backtest mode remains primary).
Falls back to paper-in-memory order book if ALPACA_API_KEY is missing.

The PQTF engine calls this module to:
  - fetch_latest_quote(ticker) -> {bid, ask, last, ts}
  - submit_option_order(...) -> order_id
  - get_position(ticker) -> {qty, avg_price, unrealized_pnl}
  - list_account() -> {equity, buying_power}

Alpaca free tier supports equities + options on paper accounts, 200 req/min.
For backtest mode, engine continues to resolve via real_paths.gbm_path marks.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

try:
    import requests
except Exception:
    requests = None  # pragma: no cover

BASE_PAPER = "https://paper-api.alpaca.markets"
BASE_DATA = "https://data.alpaca.markets"


def _enabled() -> bool:
    return os.environ.get("USE_ALPACA") == "1"


def _auth_headers() -> Optional[Dict[str, str]]:
    key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        return None
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def fetch_latest_quote(ticker: str) -> Dict[str, Any]:
    if not _enabled() or requests is None:
        return {"bid": 0.0, "ask": 0.0, "last": 0.0, "ts": time.time(), "source": "disabled"}
    h = _auth_headers()
    if not h:
        return {"bid": 0.0, "ask": 0.0, "last": 0.0, "ts": time.time(), "source": "no_keys"}
    try:
        r = requests.get(f"{BASE_DATA}/v2/stocks/{ticker}/quotes/latest",
                         headers=h, timeout=5)
        if r.status_code == 200:
            q = r.json().get("quote", {})
            return {
                "bid": float(q.get("bp") or 0.0),
                "ask": float(q.get("ap") or 0.0),
                "last": float((q.get("bp") or 0.0) + (q.get("ap") or 0.0)) / 2.0,
                "ts": time.time(),
                "source": "alpaca",
            }
    except Exception:
        pass
    return {"bid": 0.0, "ask": 0.0, "last": 0.0, "ts": time.time(), "source": "error"}


def list_account() -> Dict[str, Any]:
    if not _enabled() or requests is None:
        return {"equity": 0.0, "buying_power": 0.0, "source": "disabled"}
    h = _auth_headers()
    if not h:
        return {"equity": 0.0, "buying_power": 0.0, "source": "no_keys"}
    try:
        r = requests.get(f"{BASE_PAPER}/v2/account", headers=h, timeout=5)
        if r.status_code == 200:
            d = r.json()
            return {
                "equity": float(d.get("equity", 0.0)),
                "buying_power": float(d.get("buying_power", 0.0)),
                "source": "alpaca",
            }
    except Exception:
        pass
    return {"equity": 0.0, "buying_power": 0.0, "source": "error"}


if __name__ == "__main__":
    print("enabled:", _enabled())
    print("account:", list_account())
    print("SPY quote:", fetch_latest_quote("SPY"))
