"""Shared live-quote bus (ITF + POL TF + PQTF).

Pulls 5-min bars from yfinance (free, 15-min delayed, no auth) for the
PQTF sector-ETF universe plus extras. Caches the latest snapshot to
`data/intraday/quotes/latest.json` and appends to a daily jsonl.

Auto-swap to Alpaca Market Data when ALPACA_PAPER_KEY + ALPACA_PAPER_SECRET
are present in env (Alpaca is lower-latency, real-time on paper).

Schema:
  {
    "ts": "2026-04-19T14:33:00Z",
    "_source": "yfinance" | "alpaca",
    "tickers": {
      "SPY": {"last": 502.11, "change_pct": 0.34, "volume": 12345678,
              "5m_high": 502.40, "5m_low": 501.80}, ...
    }
  }

Callers:
  from scripts.arena.shared.quote_bus import refresh, latest
  snapshot = refresh()   # pulls + writes, returns dict
  current  = latest()    # reads latest.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_EQUITIES: List[str] = [
    # Broad + sector ETFs (20)
    "SPY", "QQQ", "IWM", "DIA",
    "XLE", "XLF", "XLK", "XLV", "XLI", "XLB", "XLY", "XLP", "XLRE", "XLU", "XLC",
    "GLD", "TLT", "SLV", "USO", "UUP",
    # Leveraged ETFs (8)
    "TQQQ", "SQQQ", "SPXL", "SPXS", "SOXL", "SOXS", "TNA", "TZA",
    # Volatility products (4)
    "VXX", "UVXY", "SVXY", "VIXY",
    # International (8)
    "EEM", "FXI", "EWZ", "EWJ", "EWT", "EWW", "VGK", "INDA",
    # MAG7 + extended single-name (20)
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD", "AVGO", "COST",
    "NFLX", "ORCL", "CRM", "ADBE", "PYPL", "SMCI", "UBER", "SHOP", "DIS", "BA",
]
DEFAULT_CRYPTO: List[str] = [
    "BTC/USD", "ETH/USD", "SOL/USD", "AVAX/USD", "LINK/USD", "DOGE/USD",
    "DOT/USD", "MATIC/USD", "LTC/USD", "UNI/USD",
]
DEFAULT_TICKERS: List[str] = DEFAULT_EQUITIES + DEFAULT_CRYPTO + ["^VIX"]


def ticker_asset_class(t: str) -> str:
    """Return 'crypto' | 'equity' | 'index'."""
    if "/" in t:
        return "crypto"
    if t.startswith("^"):
        return "index"
    return "equity"

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = REPO / "data" / "intraday" / "quotes"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LATEST_PATH = OUT_DIR / "latest.json"


def _has_alpaca() -> bool:
    return bool(os.environ.get("ALPACA_PAPER_KEY") and os.environ.get("ALPACA_PAPER_SECRET"))


def _fetch_yfinance(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    import yfinance as yf
    out: Dict[str, Dict[str, Any]] = {}
    try:
        # Download 1 day of 5m bars for all tickers in a single request.
        data = yf.download(
            tickers=" ".join(tickers),
            period="1d",
            interval="5m",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception as e:
        print(f"[quote_bus] yf.download failed: {e}", file=sys.stderr)
        return out

    for t in tickers:
        try:
            # yfinance returns a multi-index frame when multiple tickers; index by ticker.
            if len(tickers) == 1:
                df = data
            else:
                df = data[t] if t in data.columns.get_level_values(0) else None
            if df is None or df.empty:
                continue
            df = df.dropna()
            if df.empty:
                continue
            last_row = df.iloc[-1]
            first_row = df.iloc[0]
            last = float(last_row["Close"])
            first_open = float(first_row["Open"])
            change_pct = ((last - first_open) / first_open * 100.0) if first_open else 0.0
            out[t] = {
                "last": round(last, 4),
                "change_pct": round(change_pct, 3),
                "volume": int(last_row.get("Volume", 0) or 0),
                "5m_high": round(float(last_row["High"]), 4),
                "5m_low": round(float(last_row["Low"]), 4),
            }
        except Exception as e:
            print(f"[quote_bus] parse fail {t}: {e}", file=sys.stderr)
            continue
    return out


def _fetch_alpaca(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """Delegate to executor-scope alpaca client if env has paper keys."""
    try:
        # Lazy import to avoid requests requirement outside Alpaca mode.
        import requests
    except Exception:
        return {}
    key = os.environ.get("ALPACA_PAPER_KEY", "")
    secret = os.environ.get("ALPACA_PAPER_SECRET", "")
    if not key or not secret:
        return {}
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    eq_tickers = [t for t in tickers if ticker_asset_class(t) == "equity"]
    cr_tickers = [t for t in tickers if ticker_asset_class(t) == "crypto"]

    out: Dict[str, Dict[str, Any]] = {}
    # ── Equities
    if eq_tickers:
        try:
            r = requests.get(
                "https://data.alpaca.markets/v2/stocks/quotes/latest",
                params={"symbols": ",".join(eq_tickers)},
                headers=headers, timeout=8,
            )
            if r.status_code == 200:
                for t, q in r.json().get("quotes", {}).items():
                    bid = float(q.get("bp") or 0); ask = float(q.get("ap") or 0)
                    last = (bid + ask) / 2 if (bid and ask) else (bid or ask)
                    out[t] = {
                        "last": round(last, 4),
                        "change_pct": 0.0,
                        "volume": 0,
                        "5m_high": round(max(bid, ask), 4),
                        "5m_low": round(min(bid, ask) if (bid and ask) else (bid or ask), 4),
                        "asset_class": "equity",
                    }
        except Exception:
            pass
    # ── Crypto (24/7)
    if cr_tickers:
        try:
            r = requests.get(
                "https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes",
                params={"symbols": ",".join(cr_tickers)},
                headers=headers, timeout=8,
            )
            if r.status_code == 200:
                for t, q in r.json().get("quotes", {}).items():
                    bid = float(q.get("bp") or 0); ask = float(q.get("ap") or 0)
                    last = (bid + ask) / 2 if (bid and ask) else (bid or ask)
                    out[t] = {
                        "last": round(last, 4),
                        "change_pct": 0.0,
                        "volume": 0,
                        "5m_high": round(max(bid, ask), 4),
                        "5m_low": round(min(bid, ask) if (bid and ask) else (bid or ask), 4),
                        "asset_class": "crypto",
                    }
        except Exception:
            pass
    return out


def fetch_live_quotes(tickers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return {'ts', '_source', 'tickers': {...}}. No file I/O."""
    symbols = tickers if tickers else DEFAULT_TICKERS
    if _has_alpaca():
        quotes = _fetch_alpaca(symbols)
        source = "alpaca"
        if not quotes:  # fall back to yfinance if Alpaca returns empty
            quotes = _fetch_yfinance(symbols)
            source = "yfinance"
    else:
        quotes = _fetch_yfinance(symbols)
        source = "yfinance"
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_source": source,
        "tickers": quotes,
    }


def refresh(tickers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Fetch + persist to latest.json + append to YYYY-MM-DD.jsonl."""
    snap = fetch_live_quotes(tickers)
    try:
        LATEST_PATH.write_text(json.dumps(snap, indent=2))
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = OUT_DIR / f"{day}.jsonl"
        with daily.open("a") as fh:
            fh.write(json.dumps(snap) + "\n")
    except Exception as e:
        print(f"[quote_bus] persist fail: {e}", file=sys.stderr)
    return snap


def latest() -> Dict[str, Any]:
    """Read the latest snapshot; empty dict if absent."""
    if not LATEST_PATH.exists():
        return {}
    try:
        return json.loads(LATEST_PATH.read_text())
    except Exception:
        return {}


if __name__ == "__main__":
    snap = refresh()
    print(json.dumps(snap, indent=2))
