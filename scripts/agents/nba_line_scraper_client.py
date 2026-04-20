#!/usr/bin/env python3
"""
nba_line_scraper_client — cron-friendly VM client for the
LBJLincoln/nomos-browser-nba HF Space.

Usage:
    python scripts/agents/nba_line_scraper_client.py [YYYY-MM-DD]

Env:
    BROWSER_NBA_URL   override base URL (default: LBJLincoln/nomos-browser-nba)
    BROWSER_NBA_SOURCES  comma-separated sources (default: espn,bbref,vegasinsider)

Writes:
    data/lines/YYYY-MM-DD.json   fresh scrape for the given date
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
LINES_DIR = REPO / "data" / "lines"
LINES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_URL = "https://lbjlincoln-nomos-browser-nba.hf.space"
BASE = os.environ.get("BROWSER_NBA_URL", DEFAULT_URL).rstrip("/")
SOURCES = [
    s.strip()
    for s in os.environ.get("BROWSER_NBA_SOURCES", "espn,bbref,vegasinsider").split(",")
    if s.strip()
]
TIMEOUT = float(os.environ.get("BROWSER_NBA_TIMEOUT", "360"))


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Confirm Space is alive.
    try:
        status = httpx.get(f"{BASE}/api/status", timeout=15).json()
    except Exception as e:
        print(f"[line-scraper] status probe failed: {e}", file=sys.stderr)
        return 2

    if not status.get("browser_use_available"):
        print(
            f"[line-scraper] Space reports browser_use unavailable: "
            f"{status.get('browser_use_import_error')}",
            file=sys.stderr,
        )
        # Still allow the run to try — the error is diagnostic.

    # 2. Trigger scrape.
    payload = {"sources": SOURCES, "date": date, "max_seconds": 240}
    print(f"[line-scraper] POST {BASE}/api/scrape-nba-lines  sources={SOURCES} date={date}")

    try:
        r = httpx.post(
            f"{BASE}/api/scrape-nba-lines", json=payload, timeout=TIMEOUT
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[line-scraper] scrape failed: {e}", file=sys.stderr)
        return 3

    # 3. Persist.
    out = LINES_DIR / f"{date}.json"
    out.write_text(json.dumps(data, indent=2))
    n_games = len(data.get("games", []))
    succ = data.get("sources_succeeded", [])
    errs = data.get("errors", {})
    print(f"[line-scraper] wrote {out}  games={n_games}  succeeded={succ}  errors={list(errs)}")
    return 0 if n_games > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
