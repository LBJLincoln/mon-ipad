#!/usr/bin/env python3
"""Merge all per-team and per-(team,date) data files into a single
player_data structure consumable by engine.build().

Engine reads `pd_ = (player_data or {}).get((team_key, gd), {team-level-fallback})`.
This script creates entries for every (team, date) seen in player_data, merging:
  - injury/star fields from player_data.json
  - position breakdown from position_data.json
  - synergy combos from synergy_data.json (per-team, broadcast)
  - coaching from coaching_data.json (per-team, broadcast)
  - altitude from altitude_data.json (per-team, broadcast)
  - tracking from tracking_data.json (per-team, broadcast)

Output: data/karpathy/player_data_merged.json (the single dict for engine.build)

Schema:
  {f"{team}|{date}": {<all fields>}, ...same for every team-date}
  + team-only fallback: {team: {<team-level fields>}} (for cold-start games)

Usage: python3 scripts/ops/merge_player_data.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KARP = REPO / "data" / "karpathy"

PLAYER = json.loads((KARP / "player_data.json").read_text())
POSITION = json.loads((KARP / "position_data.json").read_text())
SYNERGY = json.loads((KARP / "synergy_data.json").read_text())
COACHING = json.loads((KARP / "coaching_data.json").read_text())
ALTITUDE = json.loads((KARP / "altitude_data.json").read_text())
TRACKING = json.loads((KARP / "tracking_data.json").read_text())
TRAVEL = json.loads((KARP / "travel_data.json").read_text())
FRANCHISE = json.loads((KARP / "franchise_data.json").read_text())
VEGAS = json.loads((KARP / "vegas_preseason_data.json").read_text())
COACH_EXT = json.loads((KARP / "coaching_extended_data.json").read_text())
STAR_META = json.loads((KARP / "star_metadata.json").read_text())
STREAKS = json.loads((KARP / "streaks_data.json").read_text())
CLUTCH = json.loads((KARP / "clutch_data.json").read_text())
MISC = json.loads((KARP / "misc_team_data.json").read_text())
SHOT_ZONES = json.loads((KARP / "shot_zones_data.json").read_text())
PLAYER_TOP = json.loads((KARP / "player_top_data.json").read_text())
TEAM_EST = json.loads((KARP / "team_est_data.json").read_text())
FRANCHISE_REAL = json.loads((KARP / "franchise_real_data.json").read_text())

OUT = KARP / "player_data_merged.json"


def coach_to_features(coach: dict, ext: dict) -> dict:
    """Map coaching_data fields to engine `coach_*` keys.
    `ext` is coaching_extended_data — overrides defaults with curated values.
    """
    if not coach:
        return {}
    base_wr = coach.get("win_rate", 0.5)
    return {
        "coach_career_wp": base_wr,
        "coach_playoff_wp": base_wr * 0.95,
        "coach_tenure_years": float(coach.get("exp_years", 1)),
        "coach_with_team_years": min(float(coach.get("exp_years", 1)), 5.0),
        "coach_home_wp": min(0.85, base_wr + 0.07),
        "coach_road_wp": max(0.20, base_wr - 0.07),
        "coach_close_game_wp": base_wr * 0.97,
        "coach_b2b_wp": base_wr * 0.93,
        "coach_comeback_rate": 0.30,
        "coach_blowout_wp": base_wr * 1.05 if base_wr > 0.5 else base_wr,
        "coach_vs_winning_teams_wp": base_wr * 0.88,
        "coach_pace_preference": ext.get("pace_pref", 0.5),
        "coach_offensive_rating_rank": ext.get("off_rank", 0.5),
        "coach_defensive_rating_rank": ext.get("def_rank", 0.5),
        "coach_ato_rating": ext.get("ato_rating", 0.5),
        "coach_challenge_success_rate": ext.get("challenge", 0.4),
        "coach_championships": float(coach.get("championships", 0)),
        "coach_playoff_rate": coach.get("playoff_rate", 0.4),
    }


def franchise_to_features(fr: dict) -> dict:
    if not fr:
        return {}
    return {
        "franchise_wp_10yr": fr["wp_10yr"],
        "franchise_wp_5yr": fr["wp_5yr"],
        "franchise_championships": float(fr["championships"]),
        "franchise_finals": float(fr["finals"]),
        "franchise_playoff_rate_10yr": fr["playoff_rate_10yr"],
        "franchise_avg_seed_5yr": fr["avg_seed_5yr"],
        "franchise_consistency_5yr": fr["consistency_5yr"],
        "franchise_stability_index": fr["stability_index"],
    }


def altitude_to_features(alt: dict) -> dict:
    if not alt:
        return {}
    return {
        "altitude_ft": float(alt.get("elevation_ft", 686)),
        "altitude_advantage": float(alt.get("altitude_advantage", 0.0)),
        "high_altitude_flag": float(alt.get("high_altitude_flag", 0.0)),
    }


def tracking_to_features(tk: dict) -> dict:
    if not tk:
        return {}
    return {
        "shot_contest_rate": tk.get("shot_contest_rate", 30.0),
        "deflections_per_game": tk.get("deflections_per_game", 12.0),
        "paint_pts_pct": tk.get("paint_pts_pct", 0.45),
        "fb_pts_pct": tk.get("fb_pts_pct", 0.13),
        "perimeter_defense": tk.get("perimeter_defense", 0.5),
    }


def main() -> int:
    # ── Step 1: per-team broadcast fields ──
    team_static = {}
    all_teams = (COACHING.keys() | SYNERGY.keys() | ALTITUDE.keys() | TRACKING.keys()
                 | FRANCHISE.keys() | VEGAS.keys() | COACH_EXT.keys()
                 | CLUTCH.keys() | MISC.keys() | SHOT_ZONES.keys()
                 | PLAYER_TOP.keys() | TEAM_EST.keys() | FRANCHISE_REAL.keys())
    for tabbr in all_teams:
        merged = {}
        merged.update(coach_to_features(COACHING.get(tabbr, {}), COACH_EXT.get(tabbr, {})))
        merged.update(altitude_to_features(ALTITUDE.get(tabbr, {})))
        merged.update(tracking_to_features(TRACKING.get(tabbr, {})))
        merged.update(SYNERGY.get(tabbr, {}))
        merged.update(franchise_to_features(FRANCHISE.get(tabbr, {})))
        merged.update(VEGAS.get(tabbr, {}))
        merged.update(CLUTCH.get(tabbr, {}))
        merged.update(MISC.get(tabbr, {}))
        merged.update(SHOT_ZONES.get(tabbr, {}))
        merged.update(PLAYER_TOP.get(tabbr, {}))
        merged.update(TEAM_EST.get(tabbr, {}))
        merged.update(FRANCHISE_REAL.get(tabbr, {}))
        team_static[tabbr] = merged
    print(f"team-static fields: {len(team_static)} teams × {len(list(team_static.values())[0])} fields", file=sys.stderr)

    # ── Step 2: merge per-(team, date) ──
    out = {}
    for key, pd_per_game in PLAYER.items():
        team, date = key.split("|", 1)
        merged = dict(team_static.get(team, {}))   # team baseline
        merged.update(pd_per_game)                  # injury fields
        pos_entry = POSITION.get(key)
        if pos_entry:
            merged.update(pos_entry)
        travel_entry = TRAVEL.get(key)
        if travel_entry:
            merged.update(travel_entry)
        star_entry = STAR_META.get(key)
        if star_entry:
            merged.update(star_entry)
        streak_entry = STREAKS.get(key)
        if streak_entry:
            merged.update(streak_entry)
        out[key] = merged

    # ── Step 3: also write team-only entries for cold-start fallback ──
    for tabbr, ts in team_static.items():
        out[tabbr] = ts

    OUT.write_text(json.dumps(out, indent=None))
    sz_kb = OUT.stat().st_size / 1024
    print(f"wrote {len(out)} keys to {OUT.name} ({sz_kb:.1f} KB)", file=sys.stderr)
    sample = list(k for k in out.keys() if "|" in k)[100] if any("|" in k for k in out.keys()) else None
    if sample:
        s = out[sample]
        n = len(s)
        keys_summary = sorted(s.keys())
        print(f"  fields per (team,date): {n}", file=sys.stderr)
        print(f"  sample fields: {keys_summary[:10]}", file=sys.stderr)
        print(f"  has coach_career_wp: {'coach_career_wp' in s}", file=sys.stderr)
        print(f"  has pos_pg_rating: {'pos_pg_rating' in s}", file=sys.stderr)
        print(f"  has combo1_netrtg: {'combo1_netrtg' in s}", file=sys.stderr)
        print(f"  has injury_impact_score: {'injury_impact_score' in s}", file=sys.stderr)
        print(f"  has shot_contest_rate: {'shot_contest_rate' in s}", file=sys.stderr)
        print(f"  has high_altitude_flag: {'high_altitude_flag' in s}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
