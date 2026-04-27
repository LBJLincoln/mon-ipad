#!/usr/bin/env python3
"""2025-26 Vegas preseason power ranks + win-total O/U + championship odds.

Hand-curated from public ESPN/VegasInsider/Caesars at season start (Oct 2025).
Static — changes during season tracked separately if needed.

Output: data/karpathy/vegas_preseason_data.json keyed by team_abbr.
Engine fields: preseason_win_total_ou, preseason_power_rank, preseason_conf_rank,
preseason_division_rank, vegas_championship_odds, vegas_conf_winner_odds,
vegas_season_win_total.
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "vegas_preseason_data.json"

# Pre-season Oct 2025 lines: win_total_ou (set by Caesars), power_rank (ESPN),
# conf_rank (1-15 within conference), division_rank (1-5),
# championship_odds (decimal: 1/odds = implied prob), conf_winner_odds.
VEGAS = {
    # Eastern Conference
    "BOS": {"win_total_ou": 56.5, "power_rank": 1,  "conf_rank": 1,  "division_rank": 1, "championship_odds": 4.0,  "conf_winner_odds": 1.8, "division": "Atlantic"},
    "MIL": {"win_total_ou": 49.5, "power_rank": 7,  "conf_rank": 4,  "division_rank": 1, "championship_odds": 25.0, "conf_winner_odds": 9.0, "division": "Central"},
    "NYK": {"win_total_ou": 51.5, "power_rank": 5,  "conf_rank": 3,  "division_rank": 2, "championship_odds": 14.0, "conf_winner_odds": 5.0, "division": "Atlantic"},
    "PHI": {"win_total_ou": 47.5, "power_rank": 9,  "conf_rank": 5,  "division_rank": 3, "championship_odds": 22.0, "conf_winner_odds": 9.0, "division": "Atlantic"},
    "MIA": {"win_total_ou": 44.5, "power_rank": 11, "conf_rank": 6,  "division_rank": 1, "championship_odds": 35.0, "conf_winner_odds": 13.0,"division": "Southeast"},
    "CLE": {"win_total_ou": 49.5, "power_rank": 6,  "conf_rank": 2,  "division_rank": 1, "championship_odds": 16.0, "conf_winner_odds": 6.0, "division": "Central"},
    "ORL": {"win_total_ou": 45.5, "power_rank": 12, "conf_rank": 7,  "division_rank": 2, "championship_odds": 50.0, "conf_winner_odds": 18.0,"division": "Southeast"},
    "ATL": {"win_total_ou": 36.5, "power_rank": 18, "conf_rank": 11, "division_rank": 3, "championship_odds": 200.0,"conf_winner_odds": 60.0,"division": "Southeast"},
    "IND": {"win_total_ou": 47.5, "power_rank": 10, "conf_rank": 6,  "division_rank": 3, "championship_odds": 30.0, "conf_winner_odds": 11.0,"division": "Central"},
    "DET": {"win_total_ou": 30.5, "power_rank": 24, "conf_rank": 13, "division_rank": 5, "championship_odds": 500.0,"conf_winner_odds": 200.0,"division":"Central"},
    "BKN": {"win_total_ou": 24.5, "power_rank": 26, "conf_rank": 14, "division_rank": 4, "championship_odds": 750.0,"conf_winner_odds": 300.0,"division":"Atlantic"},
    "TOR": {"win_total_ou": 31.5, "power_rank": 23, "conf_rank": 12, "division_rank": 5, "championship_odds": 300.0,"conf_winner_odds": 100.0,"division":"Atlantic"},
    "WAS": {"win_total_ou": 22.5, "power_rank": 28, "conf_rank": 15, "division_rank": 5, "championship_odds": 1000.0,"conf_winner_odds":400.0,"division":"Southeast"},
    "CHA": {"win_total_ou": 27.5, "power_rank": 25, "conf_rank": 13, "division_rank": 4, "championship_odds": 750.0,"conf_winner_odds": 200.0,"division":"Southeast"},
    "CHI": {"win_total_ou": 33.5, "power_rank": 21, "conf_rank": 12, "division_rank": 4, "championship_odds": 250.0,"conf_winner_odds": 90.0,"division": "Central"},
    # Western Conference
    "OKC": {"win_total_ou": 56.5, "power_rank": 2,  "conf_rank": 1,  "division_rank": 1, "championship_odds": 5.5,  "conf_winner_odds": 2.4, "division": "Northwest"},
    "DEN": {"win_total_ou": 55.5, "power_rank": 3,  "conf_rank": 2,  "division_rank": 2, "championship_odds": 8.0,  "conf_winner_odds": 3.5, "division": "Northwest"},
    "MIN": {"win_total_ou": 51.5, "power_rank": 4,  "conf_rank": 3,  "division_rank": 3, "championship_odds": 13.0, "conf_winner_odds": 5.5, "division": "Northwest"},
    "DAL": {"win_total_ou": 48.5, "power_rank": 8,  "conf_rank": 4,  "division_rank": 1, "championship_odds": 18.0, "conf_winner_odds": 7.0, "division": "Southwest"},
    "PHX": {"win_total_ou": 48.5, "power_rank": 13, "conf_rank": 8,  "division_rank": 1, "championship_odds": 40.0, "conf_winner_odds": 14.0,"division": "Pacific"},
    "LAL": {"win_total_ou": 42.5, "power_rank": 15, "conf_rank": 9,  "division_rank": 4, "championship_odds": 60.0, "conf_winner_odds": 22.0,"division": "Pacific"},
    "LAC": {"win_total_ou": 42.5, "power_rank": 14, "conf_rank": 8,  "division_rank": 3, "championship_odds": 55.0, "conf_winner_odds": 20.0,"division": "Pacific"},
    "GSW": {"win_total_ou": 41.5, "power_rank": 16, "conf_rank": 10, "division_rank": 5, "championship_odds": 45.0, "conf_winner_odds": 18.0,"division": "Pacific"},
    "HOU": {"win_total_ou": 41.5, "power_rank": 17, "conf_rank": 11, "division_rank": 2, "championship_odds": 45.0, "conf_winner_odds": 16.0,"division": "Southwest"},
    "MEM": {"win_total_ou": 47.5, "power_rank": 11, "conf_rank": 6,  "division_rank": 3, "championship_odds": 35.0, "conf_winner_odds": 12.0,"division": "Southwest"},
    "SAS": {"win_total_ou": 40.5, "power_rank": 19, "conf_rank": 12, "division_rank": 4, "championship_odds": 100.0,"conf_winner_odds": 35.0,"division": "Southwest"},
    "SAC": {"win_total_ou": 39.5, "power_rank": 20, "conf_rank": 13, "division_rank": 4, "championship_odds": 80.0, "conf_winner_odds": 30.0,"division": "Pacific"},
    "POR": {"win_total_ou": 30.5, "power_rank": 27, "conf_rank": 14, "division_rank": 4, "championship_odds": 500.0,"conf_winner_odds": 200.0,"division":"Northwest"},
    "UTA": {"win_total_ou": 28.5, "power_rank": 22, "conf_rank": 13, "division_rank": 5, "championship_odds": 300.0,"conf_winner_odds": 110.0,"division":"Northwest"},
    "NOP": {"win_total_ou": 39.5, "power_rank": 19, "conf_rank": 11, "division_rank": 5, "championship_odds": 90.0, "conf_winner_odds": 32.0,"division": "Southwest"},
    "MIL": {"win_total_ou": 49.5, "power_rank": 7,  "conf_rank": 4,  "division_rank": 1, "championship_odds": 25.0, "conf_winner_odds": 9.0, "division": "Central"},
}


def main() -> int:
    out = {}
    for tabbr, v in VEGAS.items():
        out[tabbr] = {
            "preseason_win_total_ou": v["win_total_ou"],
            "vegas_season_win_total": v["win_total_ou"],
            "preseason_power_rank": v["power_rank"],
            "preseason_conf_rank": v["conf_rank"],
            "preseason_division_rank": v["division_rank"],
            "vegas_championship_odds": 1.0 / v["championship_odds"],  # implied prob
            "vegas_conf_winner_odds": 1.0 / v["conf_winner_odds"],
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
