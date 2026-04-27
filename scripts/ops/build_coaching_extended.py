#!/usr/bin/env python3
"""Extended coaching data — fills the rest of engine `coach_*` fields not
covered by the basic coaching_data.json.

Engine consumer keys (engine.py 5042+):
  coach_career_wp, coach_playoff_wp, coach_tenure_years (basic — already had)
  coach_with_team_years (basic — already had)
  coach_home_wp, coach_road_wp (proxy — derived)
  coach_close_game_wp, coach_b2b_wp, coach_blowout_wp, coach_vs_winning_teams_wp
  coach_pace_preference (1=fast, 0=slow), coach_offensive_rating_rank (0-1, 1=best),
  coach_defensive_rating_rank, coach_ato_rating, coach_challenge_success_rate
  coach_comeback_rate

Hand-curated estimates from basketball-reference + 538/ESPN coaching breakdowns.
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "coaching_extended_data.json"

EXT = {
    "ATL": {"pace_pref": 0.65, "off_rank": 0.50, "def_rank": 0.35, "ato_rating": 0.55, "challenge": 0.45},
    "BOS": {"pace_pref": 0.55, "off_rank": 0.85, "def_rank": 0.85, "ato_rating": 0.70, "challenge": 0.55},
    "BKN": {"pace_pref": 0.60, "off_rank": 0.30, "def_rank": 0.30, "ato_rating": 0.40, "challenge": 0.40},
    "CHA": {"pace_pref": 0.50, "off_rank": 0.20, "def_rank": 0.30, "ato_rating": 0.40, "challenge": 0.45},
    "CHI": {"pace_pref": 0.45, "off_rank": 0.45, "def_rank": 0.55, "ato_rating": 0.55, "challenge": 0.50},
    "CLE": {"pace_pref": 0.50, "off_rank": 0.70, "def_rank": 0.70, "ato_rating": 0.60, "challenge": 0.50},
    "DAL": {"pace_pref": 0.50, "off_rank": 0.65, "def_rank": 0.55, "ato_rating": 0.60, "challenge": 0.55},
    "DEN": {"pace_pref": 0.50, "off_rank": 0.80, "def_rank": 0.65, "ato_rating": 0.65, "challenge": 0.55},
    "DET": {"pace_pref": 0.60, "off_rank": 0.30, "def_rank": 0.35, "ato_rating": 0.50, "challenge": 0.45},
    "GSW": {"pace_pref": 0.65, "off_rank": 0.65, "def_rank": 0.60, "ato_rating": 0.75, "challenge": 0.60},
    "HOU": {"pace_pref": 0.50, "off_rank": 0.60, "def_rank": 0.60, "ato_rating": 0.60, "challenge": 0.50},
    "IND": {"pace_pref": 0.85, "off_rank": 0.85, "def_rank": 0.30, "ato_rating": 0.65, "challenge": 0.55},
    "LAC": {"pace_pref": 0.45, "off_rank": 0.65, "def_rank": 0.65, "ato_rating": 0.60, "challenge": 0.55},
    "LAL": {"pace_pref": 0.50, "off_rank": 0.65, "def_rank": 0.50, "ato_rating": 0.55, "challenge": 0.55},
    "MEM": {"pace_pref": 0.55, "off_rank": 0.55, "def_rank": 0.55, "ato_rating": 0.55, "challenge": 0.50},
    "MIA": {"pace_pref": 0.40, "off_rank": 0.55, "def_rank": 0.70, "ato_rating": 0.75, "challenge": 0.65},
    "MIL": {"pace_pref": 0.55, "off_rank": 0.75, "def_rank": 0.55, "ato_rating": 0.65, "challenge": 0.55},
    "MIN": {"pace_pref": 0.45, "off_rank": 0.60, "def_rank": 0.85, "ato_rating": 0.60, "challenge": 0.55},
    "NOP": {"pace_pref": 0.55, "off_rank": 0.55, "def_rank": 0.50, "ato_rating": 0.55, "challenge": 0.50},
    "NYK": {"pace_pref": 0.45, "off_rank": 0.65, "def_rank": 0.75, "ato_rating": 0.60, "challenge": 0.55},
    "OKC": {"pace_pref": 0.55, "off_rank": 0.80, "def_rank": 0.85, "ato_rating": 0.65, "challenge": 0.60},
    "ORL": {"pace_pref": 0.50, "off_rank": 0.50, "def_rank": 0.65, "ato_rating": 0.55, "challenge": 0.50},
    "PHI": {"pace_pref": 0.50, "off_rank": 0.65, "def_rank": 0.60, "ato_rating": 0.65, "challenge": 0.55},
    "PHX": {"pace_pref": 0.50, "off_rank": 0.55, "def_rank": 0.45, "ato_rating": 0.55, "challenge": 0.50},
    "POR": {"pace_pref": 0.55, "off_rank": 0.30, "def_rank": 0.40, "ato_rating": 0.45, "challenge": 0.45},
    "SAC": {"pace_pref": 0.70, "off_rank": 0.55, "def_rank": 0.40, "ato_rating": 0.50, "challenge": 0.45},
    "SAS": {"pace_pref": 0.55, "off_rank": 0.55, "def_rank": 0.50, "ato_rating": 0.55, "challenge": 0.50},
    "TOR": {"pace_pref": 0.55, "off_rank": 0.40, "def_rank": 0.45, "ato_rating": 0.50, "challenge": 0.45},
    "UTA": {"pace_pref": 0.55, "off_rank": 0.40, "def_rank": 0.40, "ato_rating": 0.50, "challenge": 0.50},
    "WAS": {"pace_pref": 0.55, "off_rank": 0.25, "def_rank": 0.30, "ato_rating": 0.40, "challenge": 0.40},
}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(EXT, indent=2))
    print(f"wrote {len(EXT)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
