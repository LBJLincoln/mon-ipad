"""Refresh PQTF real-data cache: daily OHLC for 12 sector ETFs + VIX.

Pulls yfinance data for all PQTF session dates and writes
scripts/arena/hf-political-quant-trading-floor/data/real_paths_cache.json.

Idempotent: re-running fills missing dates without re-fetching existing ones.
Intended to run weekly via GH Action; also callable manually.

Usage:
  python3 scripts/gpu/refresh_pqtf_cache.py [--full]

  --full  ignore cache, refetch everything (use after a lookback change)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yfinance as yf  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
PQTF = ROOT / "scripts" / "arena" / "hf-political-quant-trading-floor"
CACHE = PQTF / "data" / "real_paths_cache.json"
EVENTS = PQTF / "data" / "political_events.json"

ETFS = ["SPY", "XLF", "XLK", "XLE", "XLV", "XLP",
        "XLY", "XLC", "XLI", "XLB", "XLRE", "XLU"]


def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except Exception:
            pass
    return {"ohlc": {}, "vix": {}}


def save_cache(c: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(c, indent=2))


def session_dates() -> list[str]:
    if not EVENTS.exists():
        return []
    data = json.loads(EVENTS.read_text())
    events = data if isinstance(data, list) else data.get("events", [])
    dates = sorted({e.get("date") for e in events if e.get("date")})
    return dates


def fetch_etf(ticker: str, start: str, end: str) -> dict[str, dict]:
    df = yf.download(ticker, start=start, end=end, progress=False,
                     auto_adjust=False, group_by="column")
    if df is None or df.empty:
        return {}
    # yfinance returns MultiIndex columns when ticker is single-str-in-list;
    # flatten to "Open"/"High"/"Low"/"Close"/"Volume" regardless of shape.
    if hasattr(df.columns, "levels") and df.columns.nlevels > 1:
        df = df.droplevel(1, axis=1)
    out = {}
    for idx, row in df.iterrows():
        date = idx.strftime("%Y-%m-%d")
        try:
            out[date] = {
                "o": float(row["Open"]),
                "h": float(row["High"]),
                "l": float(row["Low"]),
                "c": float(row["Close"]),
                "v": float(row.get("Volume", 0) or 0),
            }
        except Exception:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    cache = {"ohlc": {}, "vix": {}} if args.full else load_cache()
    dates = session_dates()
    if not dates:
        print("no session dates in", EVENTS)
        return 2
    start, end = dates[0], dates[-1]
    print(f"dates {start}…{end}  n={len(dates)}  tickers={len(ETFS)}")

    for ticker in ETFS:
        if not args.full:
            existing = {d for d, v in cache["ohlc"].items() if ticker in v}
            if existing.issuperset(set(dates)):
                print(f"  {ticker}: cache complete, skip")
                continue
        print(f"  fetching {ticker}")
        t_data = fetch_etf(ticker, start, end)
        for d, row in t_data.items():
            cache["ohlc"].setdefault(d, {})[ticker] = row

    print("  fetching ^VIX")
    vix_data = fetch_etf("^VIX", start, end)
    for d, row in vix_data.items():
        cache["vix"][d] = row["c"]

    save_cache(cache)
    print(f"wrote {CACHE}  ohlc_dates={len(cache['ohlc'])}  vix_dates={len(cache['vix'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
