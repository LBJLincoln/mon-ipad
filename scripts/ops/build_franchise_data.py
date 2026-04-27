#!/usr/bin/env python3
"""Static NBA franchise history table per team — engine cat fields:
  franchise_wp_10yr, franchise_wp_5yr, franchise_championships,
  franchise_finals, franchise_playoff_rate_10yr, franchise_avg_seed_5yr,
  franchise_consistency_5yr, franchise_stability_index

Data hand-curated from basketball-reference (public, free) — last 10 seasons
through 2024-25. Static is fine: franchise stats don't change mid-season.

Output: data/karpathy/franchise_data.json keyed by team_abbr.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "franchise_data.json"

# wp_10yr = avg win % 2015-16 to 2024-25
# championships, finals = NBA-history total
# playoff_rate_10yr = % of 10 last seasons reaching playoffs
# avg_seed_5yr = average playoff seed 2020-25 (15 = no playoffs that year)
# consistency_5yr = stdev of W% lastsfrom 5 yrs (lower = more consistent)
# stability_index = 1.0 if same coach + GM 5+ years; lower if frequent changes
FRANCHISE = {
    "ATL": {"wp_10yr": 0.495, "wp_5yr": 0.48, "championships": 1, "finals": 1,  "playoff_rate_10yr": 0.7, "avg_seed_5yr": 8.4,  "consistency_5yr": 0.07, "stability_index": 0.6},
    "BOS": {"wp_10yr": 0.620, "wp_5yr": 0.66, "championships": 18, "finals": 23, "playoff_rate_10yr": 1.0, "avg_seed_5yr": 2.0,  "consistency_5yr": 0.04, "stability_index": 0.7},
    "BKN": {"wp_10yr": 0.450, "wp_5yr": 0.46, "championships": 0, "finals": 2,  "playoff_rate_10yr": 0.6, "avg_seed_5yr": 9.6,  "consistency_5yr": 0.10, "stability_index": 0.4},
    "CHA": {"wp_10yr": 0.380, "wp_5yr": 0.34, "championships": 0, "finals": 0,  "playoff_rate_10yr": 0.2, "avg_seed_5yr": 14.0, "consistency_5yr": 0.08, "stability_index": 0.5},
    "CHI": {"wp_10yr": 0.435, "wp_5yr": 0.42, "championships": 6, "finals": 6,  "playoff_rate_10yr": 0.4, "avg_seed_5yr": 11.0, "consistency_5yr": 0.06, "stability_index": 0.7},
    "CLE": {"wp_10yr": 0.530, "wp_5yr": 0.58, "championships": 1, "finals": 5,  "playoff_rate_10yr": 0.7, "avg_seed_5yr": 5.4,  "consistency_5yr": 0.12, "stability_index": 0.6},
    "DAL": {"wp_10yr": 0.530, "wp_5yr": 0.55, "championships": 1, "finals": 3,  "playoff_rate_10yr": 0.7, "avg_seed_5yr": 5.6,  "consistency_5yr": 0.08, "stability_index": 0.7},
    "DEN": {"wp_10yr": 0.575, "wp_5yr": 0.62, "championships": 1, "finals": 1,  "playoff_rate_10yr": 0.8, "avg_seed_5yr": 3.4,  "consistency_5yr": 0.05, "stability_index": 0.8},
    "DET": {"wp_10yr": 0.345, "wp_5yr": 0.30, "championships": 3, "finals": 7,  "playoff_rate_10yr": 0.2, "avg_seed_5yr": 14.4, "consistency_5yr": 0.05, "stability_index": 0.4},
    "GSW": {"wp_10yr": 0.665, "wp_5yr": 0.58, "championships": 7, "finals": 11, "playoff_rate_10yr": 0.9, "avg_seed_5yr": 4.6,  "consistency_5yr": 0.13, "stability_index": 0.9},
    "HOU": {"wp_10yr": 0.485, "wp_5yr": 0.36, "championships": 2, "finals": 4,  "playoff_rate_10yr": 0.5, "avg_seed_5yr": 11.0, "consistency_5yr": 0.16, "stability_index": 0.5},
    "IND": {"wp_10yr": 0.490, "wp_5yr": 0.50, "championships": 0, "finals": 1,  "playoff_rate_10yr": 0.6, "avg_seed_5yr": 8.0,  "consistency_5yr": 0.08, "stability_index": 0.7},
    "LAC": {"wp_10yr": 0.555, "wp_5yr": 0.56, "championships": 0, "finals": 0,  "playoff_rate_10yr": 0.8, "avg_seed_5yr": 5.4,  "consistency_5yr": 0.07, "stability_index": 0.7},
    "LAL": {"wp_10yr": 0.510, "wp_5yr": 0.53, "championships": 17,"finals": 32, "playoff_rate_10yr": 0.6, "avg_seed_5yr": 6.6,  "consistency_5yr": 0.13, "stability_index": 0.5},
    "MEM": {"wp_10yr": 0.490, "wp_5yr": 0.50, "championships": 0, "finals": 0,  "playoff_rate_10yr": 0.6, "avg_seed_5yr": 7.4,  "consistency_5yr": 0.10, "stability_index": 0.6},
    "MIA": {"wp_10yr": 0.530, "wp_5yr": 0.54, "championships": 3, "finals": 7,  "playoff_rate_10yr": 0.8, "avg_seed_5yr": 5.0,  "consistency_5yr": 0.06, "stability_index": 0.9},
    "MIL": {"wp_10yr": 0.585, "wp_5yr": 0.62, "championships": 2, "finals": 3,  "playoff_rate_10yr": 0.9, "avg_seed_5yr": 3.6,  "consistency_5yr": 0.06, "stability_index": 0.7},
    "MIN": {"wp_10yr": 0.430, "wp_5yr": 0.51, "championships": 0, "finals": 0,  "playoff_rate_10yr": 0.4, "avg_seed_5yr": 8.4,  "consistency_5yr": 0.10, "stability_index": 0.6},
    "NOP": {"wp_10yr": 0.435, "wp_5yr": 0.46, "championships": 0, "finals": 0,  "playoff_rate_10yr": 0.4, "avg_seed_5yr": 11.0, "consistency_5yr": 0.07, "stability_index": 0.6},
    "NYK": {"wp_10yr": 0.430, "wp_5yr": 0.52, "championships": 2, "finals": 4,  "playoff_rate_10yr": 0.4, "avg_seed_5yr": 9.4,  "consistency_5yr": 0.08, "stability_index": 0.6},
    "OKC": {"wp_10yr": 0.555, "wp_5yr": 0.58, "championships": 1, "finals": 4,  "playoff_rate_10yr": 0.7, "avg_seed_5yr": 6.4,  "consistency_5yr": 0.13, "stability_index": 0.7},
    "ORL": {"wp_10yr": 0.405, "wp_5yr": 0.48, "championships": 0, "finals": 2,  "playoff_rate_10yr": 0.3, "avg_seed_5yr": 10.4, "consistency_5yr": 0.10, "stability_index": 0.7},
    "PHI": {"wp_10yr": 0.530, "wp_5yr": 0.55, "championships": 3, "finals": 9,  "playoff_rate_10yr": 0.7, "avg_seed_5yr": 5.8,  "consistency_5yr": 0.07, "stability_index": 0.6},
    "PHX": {"wp_10yr": 0.480, "wp_5yr": 0.48, "championships": 0, "finals": 3,  "playoff_rate_10yr": 0.5, "avg_seed_5yr": 8.4,  "consistency_5yr": 0.14, "stability_index": 0.5},
    "POR": {"wp_10yr": 0.480, "wp_5yr": 0.40, "championships": 1, "finals": 3,  "playoff_rate_10yr": 0.5, "avg_seed_5yr": 11.4, "consistency_5yr": 0.10, "stability_index": 0.5},
    "SAC": {"wp_10yr": 0.435, "wp_5yr": 0.48, "championships": 1, "finals": 1,  "playoff_rate_10yr": 0.2, "avg_seed_5yr": 11.6, "consistency_5yr": 0.07, "stability_index": 0.6},
    "SAS": {"wp_10yr": 0.485, "wp_5yr": 0.34, "championships": 5, "finals": 6,  "playoff_rate_10yr": 0.6, "avg_seed_5yr": 11.0, "consistency_5yr": 0.13, "stability_index": 0.9},
    "TOR": {"wp_10yr": 0.530, "wp_5yr": 0.40, "championships": 1, "finals": 1,  "playoff_rate_10yr": 0.6, "avg_seed_5yr": 10.6, "consistency_5yr": 0.13, "stability_index": 0.6},
    "UTA": {"wp_10yr": 0.515, "wp_5yr": 0.42, "championships": 0, "finals": 0,  "playoff_rate_10yr": 0.6, "avg_seed_5yr": 9.8,  "consistency_5yr": 0.13, "stability_index": 0.7},
    "WAS": {"wp_10yr": 0.420, "wp_5yr": 0.32, "championships": 1, "finals": 4,  "playoff_rate_10yr": 0.4, "avg_seed_5yr": 13.0, "consistency_5yr": 0.07, "stability_index": 0.5},
}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(FRANCHISE, indent=2))
    print(f"wrote {len(FRANCHISE)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
