#!/usr/bin/env python3
"""
NBA Player Tracking Data Fetcher — via nba_api (FREE, no auth)
Fetches hustle stats, speed/distance, shot zones, clutch, matchup data.
Saves to data/player-tracking/ as CSV for feature engine consumption.

Usage: python3 scripts/fetch_player_tracking.py [--season 2025-26]
"""
import os, sys, json, time
from pathlib import Path
from datetime import datetime

try:
    import pandas as pd
except ImportError:
    print("pip install pandas")
    sys.exit(1)

try:
    from nba_api.stats.endpoints import (
        LeagueHustleStatsPlayer,
        LeagueDashPtStats,
        LeagueDashPlayerClutch,
        LeagueDashPlayerShotLocations,
        PlayerEstimatedMetrics,
        LeagueDashPlayerStats,
    )
except ImportError:
    print("pip install nba_api")
    sys.exit(1)

SEASON = sys.argv[sys.argv.index('--season') + 1] if '--season' in sys.argv else '2025-26'
NBA_SEASON = SEASON.replace('-', '-')  # nba_api format: "2025-26"

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "player-tracking"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DELAY = 1.5  # seconds between API calls (be polite to NBA.com)

def fetch_with_retry(endpoint_class, max_retries=3, **kwargs):
    """Fetch endpoint with retry logic."""
    for attempt in range(max_retries):
        try:
            time.sleep(DELAY)
            ep = endpoint_class(**kwargs)
            dfs = ep.get_data_frames()
            return dfs[0] if dfs else pd.DataFrame()
        except Exception as e:
            if attempt < max_retries - 1:
                wait = DELAY * (2 ** attempt)
                print(f"    Retry {attempt+1}: {e}, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    FAILED after {max_retries} attempts: {e}")
                return pd.DataFrame()

print(f"{'='*60}")
print(f"  NBA PLAYER TRACKING DATA FETCHER — {SEASON}")
print(f"{'='*60}")

results = {}

# 1. Hustle Stats (contested shots, deflections, loose balls, box outs)
print(f"\n1. Hustle Stats...")
df = fetch_with_retry(LeagueHustleStatsPlayer, season=NBA_SEASON, per_mode_time='PerGame')
if len(df) > 0:
    df.to_csv(OUT_DIR / f"hustle_{SEASON}.csv", index=False)
    results['hustle'] = len(df)
    print(f"   {len(df)} players | {list(df.columns)}")

# 2. Speed & Distance tracking
print(f"\n2. Speed & Distance...")
df = fetch_with_retry(LeagueDashPtStats, season=NBA_SEASON, pt_measure_type="SpeedDistance", per_mode_simple="PerGame")
if len(df) > 0:
    df.to_csv(OUT_DIR / f"speed_distance_{SEASON}.csv", index=False)
    results['speed_distance'] = len(df)
    print(f"   {len(df)} players")

# 3. Passing stats (assists, passes, potential assists)
print(f"\n3. Passing Stats...")
df = fetch_with_retry(LeagueDashPtStats, season=NBA_SEASON, pt_measure_type="Passing", per_mode_simple="PerGame")
if len(df) > 0:
    df.to_csv(OUT_DIR / f"passing_{SEASON}.csv", index=False)
    results['passing'] = len(df)
    print(f"   {len(df)} players")

# 4. Touches (front court, time of possession)
print(f"\n4. Touches...")
df = fetch_with_retry(LeagueDashPtStats, season=NBA_SEASON, pt_measure_type="Touches", per_mode_simple="PerGame")
if len(df) > 0:
    df.to_csv(OUT_DIR / f"touches_{SEASON}.csv", index=False)
    results['touches'] = len(df)
    print(f"   {len(df)} players")

# 5. Drives (drive attempts, drive points, drive FG%)
print(f"\n5. Drives...")
df = fetch_with_retry(LeagueDashPtStats, season=NBA_SEASON, pt_measure_type="Drives", per_mode_simple="PerGame")
if len(df) > 0:
    df.to_csv(OUT_DIR / f"drives_{SEASON}.csv", index=False)
    results['drives'] = len(df)
    print(f"   {len(df)} players")

# 6. Defense (rim protection, contested shots)
print(f"\n6. Defense Tracking...")
df = fetch_with_retry(LeagueDashPtStats, season=NBA_SEASON, pt_measure_type="Defense", per_mode_simple="PerGame")
if len(df) > 0:
    df.to_csv(OUT_DIR / f"defense_{SEASON}.csv", index=False)
    results['defense'] = len(df)
    print(f"   {len(df)} players")

# 7. Shot Locations (zone FG% for all players)
print(f"\n7. Shot Locations...")
df = fetch_with_retry(LeagueDashPlayerShotLocations, season=NBA_SEASON, per_mode_detailed="PerGame")
if len(df) > 0:
    df.to_csv(OUT_DIR / f"shot_locations_{SEASON}.csv", index=False)
    results['shot_locations'] = len(df)
    print(f"   {len(df)} players")

# 8. Clutch Stats (last 5 min, within 5 points)
print(f"\n8. Clutch Stats...")
df = fetch_with_retry(LeagueDashPlayerClutch, season=NBA_SEASON, per_mode_detailed="PerGame",
                      clutch_time_nullable="Last 5 Minutes",
                      ahead_behind_nullable="Ahead or Behind",
                      point_diff_nullable=5)
if len(df) > 0:
    df.to_csv(OUT_DIR / f"clutch_{SEASON}.csv", index=False)
    results['clutch'] = len(df)
    print(f"   {len(df)} players")

# 9. Estimated Advanced Metrics (E_OFF_RATING, E_DEF_RATING, E_NET_RATING)
print(f"\n9. Estimated Metrics...")
df = fetch_with_retry(PlayerEstimatedMetrics, season=NBA_SEASON)
if len(df) > 0:
    df.to_csv(OUT_DIR / f"estimated_metrics_{SEASON}.csv", index=False)
    results['estimated_metrics'] = len(df)
    print(f"   {len(df)} players")

# 10. Full Player Stats (traditional + advanced)
print(f"\n10. Full Player Stats...")
df = fetch_with_retry(LeagueDashPlayerStats, season=NBA_SEASON, per_mode_detailed="PerGame")
if len(df) > 0:
    df.to_csv(OUT_DIR / f"player_stats_{SEASON}.csv", index=False)
    results['player_stats'] = len(df)
    print(f"   {len(df)} players")

# Summary
print(f"\n{'='*60}")
print(f"  FETCH COMPLETE — {SEASON}")
print(f"{'='*60}")
for name, count in results.items():
    print(f"  {name:20s}: {count} players")
print(f"  Total datasets: {len(results)}")
print(f"  Saved to: {OUT_DIR}")
print(f"{'='*60}")

# Save metadata
meta = {
    'season': SEASON,
    'fetched_at': datetime.now().isoformat(),
    'datasets': results,
    'total_datasets': len(results),
    'out_dir': str(OUT_DIR),
}
with open(OUT_DIR / f"metadata_{SEASON}.json", 'w') as f:
    json.dump(meta, f, indent=2)
