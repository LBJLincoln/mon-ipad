#!/usr/bin/env python3
"""Build static NBA arena altitude table.

Output: data/karpathy/altitude_data.json keyed by team_abbr → elevation_ft.
Used by engine env_*_high_altitude features (6 dead columns → alive when team
is at altitude ≥ 4000ft, which is essentially just DEN, UTA, OKC).

Source: public arena elevation data (Wikipedia / arena pages).

Usage: python3 scripts/ops/build_altitude_data.py
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "altitude_data.json"

# Arena elevation in feet (city ground level / arena ~equivalent for NBA arenas)
ARENA_ELEVATION_FT = {
    "ATL": 1050, "BOS": 19,   "BKN": 33,   "CHA": 751,
    "CHI": 597,  "CLE": 653,  "DAL": 430,  "DEN": 5280,  # mile-high
    "DET": 605,  "GSW": 39,   "HOU": 80,   "IND": 715,
    "LAC": 233,  "LAL": 233,  "MEM": 337,  "MIA": 6,
    "MIL": 617,  "MIN": 830,  "NOP": 7,    "NYK": 33,
    "OKC": 1201, "ORL": 82,   "PHI": 39,   "PHX": 1086,
    "POR": 50,   "SAC": 30,   "SAS": 660,  "TOR": 250,
    "UTA": 4226, "WAS": 410,
}

LEAGUE_BASELINE_FT = sum(ARENA_ELEVATION_FT.values()) / len(ARENA_ELEVATION_FT)


def main() -> int:
    out = {}
    for team, elev in ARENA_ELEVATION_FT.items():
        out[team] = {
            "elevation_ft": elev,
            "altitude_advantage": (elev - LEAGUE_BASELINE_FT) / 1000.0,  # 1 unit = 1000ft above league avg
            "high_altitude_flag": 1.0 if elev >= 4000 else 0.0,
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} teams to {OUT.name}")
    print(f"high-altitude (≥4000ft): {sum(1 for v in out.values() if v['high_altitude_flag'] > 0)}")
    print(f"league baseline: {LEAGUE_BASELINE_FT:.0f} ft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
