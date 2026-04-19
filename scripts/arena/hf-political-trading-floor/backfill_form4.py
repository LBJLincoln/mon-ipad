#!/usr/bin/env python3
"""backfill_form4 — pull Form 4 insider filings from SEC EDGAR for all POL TF
tickers over the Jul 2025 → Jan 2026 window so build_full_dataset.py can
resolve excess_return and extend POL TF beyond 50 days.

EDGAR endpoints (public, free, 10 req/s):
  https://www.sec.gov/files/company_tickers.json           → ticker → CIK
  https://data.sec.gov/submissions/CIK{padded}.json        → recent filings

SEC requires a User-Agent with contact info.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import urllib.request

POL_ALPHA = Path(os.environ.get("POL_ALPHA", "/home/termius/nomos-political-alpha")).resolve()
INSIDER = POL_ALPHA / "data" / "insider"
OUT = INSIDER / "form4_backfill.json"

UA = "Nomos42 Research nomos42@lahargnedebartoli.com"
HEADERS = {"User-Agent": UA, "Accept": "application/json"}

TICKERS = [
    "GEO", "CXW", "CVX", "XOM", "OXY", "COP", "OKLO",
    "UNH", "PFE", "MRK", "JNJ",
    "JPM", "BAC", "GS", "MS", "FOUR", "HOOD", "MSTR", "COIN",
    "MSFT", "META", "GOOGL", "AMZN", "NVDA", "AAPL", "QCOM", "TSLA",
    "MO", "PPC", "KO",
    "UBER", "CMCSA",
]

START = "2025-07-01"
END   = "2026-01-31"


def fetch(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except Exception as e:
        print(f"[ERR] {url}: {e}")
        return None


def ticker_to_cik() -> dict[str, str]:
    raw = fetch("https://www.sec.gov/files/company_tickers.json")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for _, row in data.items():
        t = row.get("ticker", "").upper()
        cik = str(row.get("cik_str", "")).zfill(10)
        if t and cik:
            out[t] = cik
    return out


def fetch_form4s(cik: str, ticker: str) -> list[dict]:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    raw = fetch(url)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs  = recent.get("accessionNumber", [])
    out = []
    for i, form in enumerate(forms):
        if form != "4":
            continue
        d = dates[i] if i < len(dates) else ""
        if not d or d < START or d > END:
            continue
        out.append({
            "file_date": d,
            "accession_number": accs[i] if i < len(accs) else "",
            "display_names": [f"Insider ({ticker})"],
        })
    return out


def main() -> int:
    if not INSIDER.exists():
        print(f"[ERR] missing {INSIDER}", file=sys.stderr)
        return 1

    print("Fetching ticker→CIK map ...")
    t2c = ticker_to_cik()
    print(f"  → {len(t2c)} tickers in SEC map")
    if not t2c:
        return 2

    out: dict[str, list[dict]] = {}
    total = 0
    for t in TICKERS:
        cik = t2c.get(t)
        if not cik:
            print(f"  {t:>6}: no CIK")
            continue
        time.sleep(0.12)  # stay under 10 req/s
        filings = fetch_form4s(cik, t)
        if filings:
            out[t] = filings
            total += len(filings)
            print(f"  {t:>6}: {len(filings)} Form 4 filings  ({filings[0]['file_date']} → {filings[-1]['file_date']})")
        else:
            print(f"  {t:>6}: 0 filings")

    OUT.write_text(json.dumps(out))
    sz = OUT.stat().st_size / 1024
    print(f"\nWrote {OUT}  ({sz:.1f} KB)  tickers={len(out)} total={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
