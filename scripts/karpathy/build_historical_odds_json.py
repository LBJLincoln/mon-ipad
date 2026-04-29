#!/usr/bin/env python3
"""Build full-odds-historical-2017-2026.json from CSV + current season JSON.

The TabICL Oracle training pipeline (Colab notebook in
LBJLincoln26/nba-feature-cache) loads `full-odds-2025-26.json` as the
`odds_data` feed for engine.build(). This only covers the current season,
so 7 of 9 training seasons (~10,200 / 11,440 games) are passed through the
engine's 30+ market-aware feature categories with all-zero market columns.

This builds a merged file that covers 2017-18 through 2025-26 by:
  1. Reading data/historical-odds/nba_2008-2025.csv for 2017-18..2024-25
  2. Mapping CSV short codes (lal, gsw, sa) to JSON abbrs (LAL, GSW, SAS)
  3. Producing engine-format keys: 'YYYY-MM-DD_AWAY@HOME' with
     `base: {moneyline_home, moneyline_away, spread_home, total, h2_total,
             book, source}`
  4. Merging current 2025-26 odds (richer 249-cat surface) on top
  5. Writing data/historical-odds/full-odds-historical-2017-2026.json

After this, Cell 3 of tabicl_oracle_train.ipynb just needs:
    raw_odds = json.loads((DATA_DIR / 'full-odds-historical-2017-2026.json').read_text())

and Cell 2 needs to download the new filename. No engine.py change.

This unlocks the engine's market features (categories 46, 52, 55, 58, etc.)
across all 9 training seasons. Per the MDPI 2026 NBA paper, market-feature
baselines hit Brier 0.199 on 2024 — our current TabICL is 0.22054 because
it doesn't see the lines.
"""
from __future__ import annotations

import csv
import json
import logging
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT / "data" / "historical-odds" / "nba_2008-2025.csv"
CURRENT_SEASON_PATH = (
    ROOT
    / "scripts"
    / "arena"
    / "hf-llm-trading-floor"
    / "data"
    / "full-odds-2025-26.json"
)
OUT_PATH = ROOT / "data" / "historical-odds" / "full-odds-historical-2017-2026.json"

# CSV short-code → NBA standard team_abbr (matches games-*.json team_abbr).
TEAM_MAP = {
    "atl": "ATL", "bkn": "BKN", "bos": "BOS", "cha": "CHA", "chi": "CHI",
    "cle": "CLE", "dal": "DAL", "den": "DEN", "det": "DET", "gs": "GSW",
    "hou": "HOU", "ind": "IND", "lac": "LAC", "lal": "LAL", "mem": "MEM",
    "mia": "MIA", "mil": "MIL", "min": "MIN", "no": "NOP", "ny": "NYK",
    "okc": "OKC", "orl": "ORL", "phi": "PHI", "phx": "PHX", "por": "POR",
    "sa": "SAS", "sac": "SAC", "tor": "TOR", "utah": "UTA", "wsh": "WAS",
}

# Cache only seasons present in the games-*.json training set.
# Seasons in the CSV are stored as the END year of the season (2018 = 2017-18).
SEASON_MIN = 2018  # 2017-18 season
SEASON_MAX = 2025  # 2024-25 season (2025-26 comes from the JSON merge)


log = logging.getLogger("hist-odds")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _try_float(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def parse_csv() -> dict[str, dict]:
    """Build {key: {base: {...}}} from nba_2008-2025.csv for SEASON_MIN..SEASON_MAX."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(CSV_PATH)
    odds: dict[str, dict] = {}
    season_counts: Counter = Counter()
    skip_team = 0
    skip_ml = 0
    skip_dup = 0
    with CSV_PATH.open() as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                season = int(row["season"])
            except (ValueError, TypeError):
                continue
            if season < SEASON_MIN or season > SEASON_MAX:
                continue
            date = (row.get("date") or "").strip()
            if not date:
                continue
            away = TEAM_MAP.get((row.get("away") or "").strip().lower())
            home = TEAM_MAP.get((row.get("home") or "").strip().lower())
            if not away or not home:
                skip_team += 1
                continue
            ml_home = _try_float(row.get("moneyline_home"))
            ml_away = _try_float(row.get("moneyline_away"))
            spread = _try_float(row.get("spread"))
            total = _try_float(row.get("total"))
            # Synthesize ML from spread when CSV omitted it (2023-24, 2024-25
            # rows in this dataset). Standard NBA mapping: spread is the
            # primary line, ML is derivable. Skip only if BOTH are missing.
            if (ml_home is None or ml_away is None) and spread is None:
                skip_ml += 1
                continue
            if ml_home is None or ml_away is None:
                # Conservative sigmoid: 1pt spread ≈ 3.4% win-prob shift near
                # pick'em. Convert prob → American ML, vig-inclusive ~1.05.
                fav_pts = abs(spread or 0.0)
                p_fav = min(0.92, max(0.50, 0.50 + 0.034 * fav_pts))
                p_dog = 1.0 - p_fav
                # American: dog +EV, fav -EV. Inflate to 1.05 overround.
                p_fav_book = p_fav * 1.025
                p_dog_book = p_dog * 1.025
                fav_ml = -round(100.0 * p_fav_book / max(0.01, 1.0 - p_fav_book))
                dog_ml = round(100.0 * (1.0 - p_dog_book) / max(0.01, p_dog_book))
                whos_temp = (row.get("whos_favored") or "").strip().lower()
                if whos_temp == "home":
                    ml_home = float(fav_ml)
                    ml_away = float(dog_ml)
                else:
                    ml_away = float(fav_ml)
                    ml_home = float(dog_ml)
            h2_total = _try_float(row.get("h2_total"))
            whos = (row.get("whos_favored") or "").strip().lower()
            # Sign convention: spread_home negative when home favored, positive
            # when home is the dog. The CSV stores spread as positive magnitude
            # plus a `whos_favored` column.
            if spread is not None:
                spread_home = -abs(spread) if whos == "home" else abs(spread)
            else:
                spread_home = 0.0
            key = f"{date}_{away}@{home}"
            if key in odds:
                # Same game appearing twice in the CSV — keep the first (preferred
                # book ordering). Bumping the dup counter for transparency.
                skip_dup += 1
                continue
            odds[key] = {
                "base": {
                    "moneyline_home": ml_home,
                    "moneyline_away": ml_away,
                    "spread_home": spread_home,
                    "total": total if total is not None else 220.0,
                    "h2_total": h2_total if h2_total is not None else (
                        total / 2.0 if total is not None else 110.0
                    ),
                    "book": "historical_csv",
                    "source": "sportsbookreviews",
                    "season": season,
                },
            }
            season_counts[season] += 1
    log.info(
        "csv parsed: %d keys, skip_team=%d skip_ml=%d skip_dup=%d",
        len(odds), skip_team, skip_ml, skip_dup,
    )
    log.info("per-season: %s", dict(sorted(season_counts.items())))
    return odds


def merge_current_season(odds: dict[str, dict]) -> dict[str, dict]:
    if not CURRENT_SEASON_PATH.exists():
        log.warning("no current-season file at %s — skipping merge", CURRENT_SEASON_PATH)
        return odds
    current = json.loads(CURRENT_SEASON_PATH.read_text())
    if not isinstance(current, dict):
        log.warning("current-season file is not a dict — skipping merge")
        return odds
    overlay = 0
    new = 0
    for k, v in current.items():
        if k in odds:
            overlay += 1
        else:
            new += 1
        odds[k] = v  # Current-season schema has 249 cats, we want it to win.
    log.info("current-season merged: %d new, %d overlay", new, overlay)
    return odds


def main():
    odds = parse_csv()
    odds = merge_current_season(odds)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(odds, separators=(",", ":")))
    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    log.info("wrote %s (%d keys, %.1f MB)", OUT_PATH, len(odds), size_mb)


if __name__ == "__main__":
    main()
