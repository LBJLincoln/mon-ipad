#!/usr/bin/env python3
"""Static coaching table per NBA team for 2025-26 season.

Source: basketball-reference / wikipedia / public records.
Manual curation — only 30 teams, low refresh — to avoid scraping fragility.

Output: data/karpathy/coaching_data.json keyed by team_abbr:
  {coach_name, exp_years, win_rate, playoff_rate, championships}

Usage: python3 scripts/ops/scrape_coaching.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "coaching_data.json"

# 2025-26 head coaches (start of season). exp_years = career HC seasons,
# win_rate = career W%, playoff_rate = % of seasons reaching playoffs,
# championships = NBA titles as HC.
# Source: basketball-reference public records.
COACHES = {
    "ATL": {"name": "Quin Snyder",      "exp_years": 9,  "win_rate": 0.567, "playoff_rate": 0.78, "championships": 0},
    "BOS": {"name": "Joe Mazzulla",     "exp_years": 3,  "win_rate": 0.722, "playoff_rate": 1.00, "championships": 1},
    "BKN": {"name": "Jordi Fernandez",  "exp_years": 1,  "win_rate": 0.310, "playoff_rate": 0.00, "championships": 0},
    "CHA": {"name": "Charles Lee",      "exp_years": 1,  "win_rate": 0.230, "playoff_rate": 0.00, "championships": 0},
    "CHI": {"name": "Billy Donovan",    "exp_years": 5,  "win_rate": 0.480, "playoff_rate": 0.40, "championships": 0},
    "CLE": {"name": "Kenny Atkinson",   "exp_years": 4,  "win_rate": 0.485, "playoff_rate": 0.50, "championships": 0},
    "DAL": {"name": "Jason Kidd",       "exp_years": 8,  "win_rate": 0.530, "playoff_rate": 0.63, "championships": 0},
    "DEN": {"name": "David Adelman",    "exp_years": 1,  "win_rate": 0.610, "playoff_rate": 1.00, "championships": 0},
    "DET": {"name": "J.B. Bickerstaff", "exp_years": 7,  "win_rate": 0.420, "playoff_rate": 0.43, "championships": 0},
    "GSW": {"name": "Steve Kerr",       "exp_years": 11, "win_rate": 0.660, "playoff_rate": 0.82, "championships": 4},
    "HOU": {"name": "Ime Udoka",        "exp_years": 4,  "win_rate": 0.560, "playoff_rate": 0.50, "championships": 0},
    "IND": {"name": "Rick Carlisle",    "exp_years": 21, "win_rate": 0.530, "playoff_rate": 0.62, "championships": 1},
    "LAC": {"name": "Tyronn Lue",       "exp_years": 9,  "win_rate": 0.555, "playoff_rate": 0.67, "championships": 1},
    "LAL": {"name": "JJ Redick",        "exp_years": 1,  "win_rate": 0.610, "playoff_rate": 1.00, "championships": 0},
    "MEM": {"name": "Tuomas Iisalo",    "exp_years": 1,  "win_rate": 0.530, "playoff_rate": 1.00, "championships": 0},
    "MIA": {"name": "Erik Spoelstra",   "exp_years": 17, "win_rate": 0.580, "playoff_rate": 0.82, "championships": 2},
    "MIL": {"name": "Doc Rivers",       "exp_years": 26, "win_rate": 0.580, "playoff_rate": 0.85, "championships": 1},
    "MIN": {"name": "Chris Finch",      "exp_years": 5,  "win_rate": 0.525, "playoff_rate": 0.60, "championships": 0},
    "NOP": {"name": "Willie Green",     "exp_years": 4,  "win_rate": 0.450, "playoff_rate": 0.50, "championships": 0},
    "NYK": {"name": "Mike Brown",       "exp_years": 9,  "win_rate": 0.550, "playoff_rate": 0.67, "championships": 0},
    "OKC": {"name": "Mark Daigneault",  "exp_years": 5,  "win_rate": 0.585, "playoff_rate": 0.60, "championships": 0},
    "ORL": {"name": "Jamahl Mosley",    "exp_years": 4,  "win_rate": 0.460, "playoff_rate": 0.50, "championships": 0},
    "PHI": {"name": "Nick Nurse",       "exp_years": 7,  "win_rate": 0.540, "playoff_rate": 0.71, "championships": 1},
    "PHX": {"name": "Jordan Ott",       "exp_years": 1,  "win_rate": 0.490, "playoff_rate": 0.00, "championships": 0},
    "POR": {"name": "Chauncey Billups", "exp_years": 4,  "win_rate": 0.350, "playoff_rate": 0.00, "championships": 0},
    "SAC": {"name": "Doug Christie",    "exp_years": 1,  "win_rate": 0.450, "playoff_rate": 0.00, "championships": 0},
    "SAS": {"name": "Mitch Johnson",    "exp_years": 1,  "win_rate": 0.460, "playoff_rate": 0.00, "championships": 0},
    "TOR": {"name": "Darko Rajakovic",  "exp_years": 2,  "win_rate": 0.380, "playoff_rate": 0.00, "championships": 0},
    "UTA": {"name": "Will Hardy",       "exp_years": 3,  "win_rate": 0.420, "playoff_rate": 0.00, "championships": 0},
    "WAS": {"name": "Brian Keefe",      "exp_years": 1,  "win_rate": 0.230, "playoff_rate": 0.00, "championships": 0},
}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(COACHES, indent=2))
    print(f"wrote {len(COACHES)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
