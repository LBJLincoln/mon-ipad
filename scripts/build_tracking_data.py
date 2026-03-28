#!/usr/bin/env python3
"""
Build team-level tracking features from nba_api player CSVs.
Output: data/player-tracking/team_tracking_{season}.json

Format: {"BOS": {"rim_rate": 0.32, "contested_shots": 52.3, ...}, ...}
Ready for engine.py build(tracking_data=...) parameter.
"""
import os, sys, json
from pathlib import Path

import pandas as pd
import numpy as np

SEASON = sys.argv[sys.argv.index('--season') + 1] if '--season' in sys.argv else '2025-26'
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "player-tracking"

TEAM_ABBREV_MAP = {
    1610612737: "ATL", 1610612738: "BOS", 1610612751: "BKN", 1610612766: "CHA",
    1610612741: "CHI", 1610612739: "CLE", 1610612742: "DAL", 1610612743: "DEN",
    1610612765: "DET", 1610612744: "GSW", 1610612745: "HOU", 1610612754: "IND",
    1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM", 1610612748: "MIA",
    1610612749: "MIL", 1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
    1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHX",
    1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612761: "TOR",
    1610612762: "UTA", 1610612764: "WAS",
}

def load_csv(name):
    path = DATA_DIR / f"{name}_{SEASON}.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()

def get_team(row):
    """Get team abbreviation from row."""
    if 'TEAM_ABBREVIATION' in row.index:
        return row['TEAM_ABBREVIATION']
    if 'TEAM_ID' in row.index:
        return TEAM_ABBREV_MAP.get(int(row['TEAM_ID']), None)
    return None

print(f"Building team tracking data for {SEASON}...")

tracking = {}

# 1. Hustle stats → team-level aggregation (minutes-weighted)
hustle = load_csv("hustle")
if len(hustle) > 0:
    print(f"  Hustle: {len(hustle)} players")
    # Aggregate by team: sum per-game stats × games played for weighted average
    for team_abbr in hustle['TEAM_ABBREVIATION'].unique():
        team_df = hustle[hustle['TEAM_ABBREVIATION'] == team_abbr]
        # Weight by minutes played
        total_min = (team_df['MIN'] * team_df['G']).sum()
        if total_min > 0:
            if team_abbr not in tracking:
                tracking[team_abbr] = {}
            # Sum per-game stats for team (already per-game, so we weight by minutes share)
            for col, key in [
                ('CONTESTED_SHOTS', 'contested_shots'),
                ('DEFLECTIONS', 'deflections'),
                ('LOOSE_BALLS_RECOVERED', 'loose_balls'),
                ('BOX_OUTS', 'box_outs'),
                ('CHARGES_DRAWN', 'charges_drawn'),
                ('SCREEN_ASSISTS', 'screen_assists'),
            ]:
                if col in team_df.columns:
                    # Team total ≈ sum of top 10 rotation players' per-game stats
                    top10 = team_df.nlargest(10, 'MIN')
                    tracking[team_abbr][key] = round(float(top10[col].sum()), 2)

# 2. Speed & Distance
speed = load_csv("speed_distance")
if len(speed) > 0:
    print(f"  Speed/Distance: {len(speed)} entries")
    team_col = 'TEAM_ABBREVIATION' if 'TEAM_ABBREVIATION' in speed.columns else None
    if team_col:
        for _, row in speed.iterrows():
            team = row[team_col]
            if team not in tracking:
                tracking[team] = {}
            for col, key in [
                ('DIST_MILES', 'dist_miles'),
                ('AVG_SPEED', 'avg_speed'),
                ('DIST_MILES_OFF', 'dist_miles_off'),
                ('DIST_MILES_DEF', 'dist_miles_def'),
                ('AVG_SPEED_OFF', 'avg_speed_off'),
                ('AVG_SPEED_DEF', 'avg_speed_def'),
            ]:
                if col in row.index and pd.notna(row[col]):
                    tracking[team][key] = round(float(row[col]), 3)

# 3. Shot Locations → team-level zone rates
shots = load_csv("shot_locations")
if len(shots) > 0:
    print(f"  Shot Locations: {len(shots)} players")
    # This is complex multi-header data; extract zone stats
    # nba_api shot locations has nested columns — let's extract what we can
    if 'TEAM_ABBREVIATION' in shots.columns:
        for team_abbr in shots['TEAM_ABBREVIATION'].unique():
            team_df = shots[shots['TEAM_ABBREVIATION'] == team_abbr]
            if team_abbr not in tracking:
                tracking[team_abbr] = {}
            # Try to extract zone rates from available columns
            # Column names vary by nba_api version
            total_fga = 0
            for col in shots.columns:
                if 'FGA' in str(col) and 'PCT' not in str(col):
                    vals = pd.to_numeric(team_df[col], errors='coerce')
                    total_fga += vals.sum()

            if total_fga > 0:
                for zone_name, zone_key in [
                    ('Restricted Area', 'rim'),
                    ('Mid-Range', 'mid'),
                    ('Above the Break 3', 'three'),
                    ('Corner 3', 'corner3'),
                ]:
                    for col in shots.columns:
                        if zone_name in str(col) and 'FGA' in str(col) and 'PCT' not in str(col):
                            vals = pd.to_numeric(team_df[col], errors='coerce')
                            rate = vals.sum() / total_fga if total_fga > 0 else 0
                            tracking[team_abbr][f'{zone_key}_rate'] = round(float(rate), 4)

            # Also extract FG% if available
            for zone_name, zone_key in [
                ('Restricted Area', 'rim_fg_pct'),
                ('Mid-Range', 'mid_fg_pct'),
                ('Above the Break 3', 'three_fg_pct'),
            ]:
                for col in shots.columns:
                    if zone_name in str(col) and 'FG_PCT' in str(col):
                        vals = pd.to_numeric(team_df[col], errors='coerce').dropna()
                        if len(vals) > 0:
                            # Minutes-weighted average
                            tracking[team_abbr][zone_key] = round(float(vals.mean()), 4)

# 4. Drives
drives = load_csv("drives")
if len(drives) > 0:
    print(f"  Drives: {len(drives)} entries")
    team_col = 'TEAM_ABBREVIATION' if 'TEAM_ABBREVIATION' in drives.columns else None
    if team_col:
        for _, row in drives.iterrows():
            team = row[team_col]
            if team not in tracking:
                tracking[team] = {}
            for col, key in [
                ('DRIVES', 'drives'),
                ('DRIVE_PTS', 'drive_pts'),
                ('DRIVE_FG_PCT', 'drive_fg_pct'),
            ]:
                if col in row.index and pd.notna(row[col]):
                    tracking[team][key] = round(float(row[col]), 3)

# 5. Estimated Metrics → team-level averages
metrics = load_csv("estimated_metrics")
if len(metrics) > 0:
    print(f"  Estimated Metrics: {len(metrics)} players")
    if 'TEAM_ABBREVIATION' in metrics.columns:
        for team_abbr in metrics['TEAM_ABBREVIATION'].unique():
            team_df = metrics[metrics['TEAM_ABBREVIATION'] == team_abbr]
            if team_abbr not in tracking:
                tracking[team_abbr] = {}
            # Top 8 by minutes
            if 'GP' in team_df.columns and 'MIN' in team_df.columns:
                top8 = team_df.nlargest(8, 'MIN')
            else:
                top8 = team_df.head(8)
            for col, key in [
                ('E_OFF_RATING', 'e_off_rating'),
                ('E_DEF_RATING', 'e_def_rating'),
                ('E_NET_RATING', 'e_net_rating'),
                ('E_PACE', 'e_pace'),
            ]:
                if col in top8.columns:
                    vals = pd.to_numeric(top8[col], errors='coerce').dropna()
                    if len(vals) > 0:
                        tracking[team_abbr][key] = round(float(vals.mean()), 3)

# Compute xEFG for all teams
for team, data in tracking.items():
    rim = data.get('rim_rate', 0.30)
    mid = data.get('mid_rate', 0.15)
    three = data.get('three_rate', 0.40)
    data['xefg'] = round(0.65 * rim + 0.40 * mid + 0.53 * three * 1.5, 4)

# Save
out_file = DATA_DIR / f"team_tracking_{SEASON}.json"
with open(out_file, 'w') as f:
    json.dump(tracking, f, indent=2)

print(f"\nTeams: {len(tracking)}")
for team in sorted(tracking.keys()):
    data = tracking[team]
    print(f"  {team}: {len(data)} features | "
          f"contested={data.get('contested_shots', '?')} "
          f"speed={data.get('avg_speed', '?')} "
          f"deflections={data.get('deflections', '?')} "
          f"drives={data.get('drives', '?')}")

print(f"\nSaved to {out_file}")
