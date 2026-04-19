#!/usr/bin/env python3
"""backfill_price_history — extend POL TF price coverage with yfinance so
build_full_dataset.py can resolve excess_return for older form4/congressional
filings and reach the 175-day parity target with NBA TF.

Current state (2026-04-19):
  price coverage: 72 unique dates, 2026-01-05 → 2026-04-17
  form4 raw:      31 unique file_dates (2026-02-24 → 2026-04-07)
  events out:     50 unique dates (bottleneck = price coverage)

After backfill target:
  price coverage: 2025-07-01 → 2026-04-17 (~200 trading days)
  events out:     ~150-175 unique dates

Writes: nomos-political-alpha/data/historical/prices_backfill.json
        (same schema as existing prices_*.json → merged by load_price_history())
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("[ERR] yfinance not installed", file=sys.stderr)
    sys.exit(1)

POL_ALPHA = Path(os.environ.get("POL_ALPHA", "/home/termius/nomos-political-alpha")).resolve()
HIST = POL_ALPHA / "data" / "historical"
OUT = HIST / "prices_backfill.json"

# Must match TICKER_TO_SECTOR in build_full_dataset.py
TICKERS = [
    "SPY",  # benchmark — REQUIRED for excess_return
    "GEO", "CXW",
    "XLE", "CVX", "XOM", "OXY", "COP", "OKLO",
    "XLV", "UNH", "PFE", "MRK", "JNJ",
    "XLF", "JPM", "BAC", "GS", "MS", "FOUR", "HOOD", "MSTR", "COIN",
    "XLK", "MSFT", "META", "GOOGL", "AMZN", "NVDA", "AAPL", "QCOM", "TSLA",
    "MO", "PPC", "KO",
    "UBER", "CMCSA",
]

START = "2025-07-01"
END   = "2026-04-17"


def fetch_ticker(t: str) -> list[dict]:
    try:
        df = yf.download(t, start=START, end=END, progress=False, auto_adjust=False)
    except Exception as e:
        print(f"[ERR] {t}: {e}")
        return []
    if df is None or df.empty:
        return []
    bars = []
    for idx, row in df.iterrows():
        date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        try:
            close = float(row["Close"].iloc[0] if hasattr(row["Close"], "iloc") else row["Close"])
            adj_close = float(row["Adj Close"].iloc[0] if hasattr(row["Adj Close"], "iloc") else row["Adj Close"])
        except Exception:
            continue
        if close != close or adj_close != adj_close:  # NaN check
            continue
        bars.append({"date": date, "close": close, "adj_close": adj_close})
    return bars


def main() -> int:
    if not HIST.exists():
        print(f"[ERR] missing {HIST}", file=sys.stderr)
        return 1

    out: dict[str, list[dict]] = {}
    for t in TICKERS:
        bars = fetch_ticker(t)
        if bars:
            out[t] = bars
            print(f"  {t:>6}: {len(bars)} bars  {bars[0]['date']} → {bars[-1]['date']}")
        else:
            print(f"  {t:>6}: 0 bars  (SKIP)")

    OUT.write_text(json.dumps(out))
    sz = OUT.stat().st_size / 1024
    print(f"\nWrote {OUT}  ({sz:.1f} KB)  tickers={len(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
