---
name: NBA Free Data Sources Inventory
description: Comprehensive map of free NBA data sources — GitHub repos, Kaggle datasets, APIs, HuggingFace — for feature engineering
type: project
---

Scanned 2026-03-28. Full doc at `/home/lahargnedebartoli/mon-ipad/docs/REPO-SCOUT-NBA-DATA.md`.

## Tier 1 — Essential Sources (use immediately)

**swar/nba_api** (~8k stars, active)
- Free, no key, stats.nba.com wrapper
- Critical endpoints: LeagueHustleStatsPlayer, LeagueDashPtStats (SpeedDistance), ShotChartDetail, LeagueDashPlayerShotLocations, BoxScorePlayerTrackV3
- `pip install nba_api`

**shufinskiy/nba_data** (~400 stars, active, auto-updated)
- Pre-built CSVs: PBP from 3 sources + shot detail 1996-2025
- Companion: nba-on-court adds lineup info to every PBP event
- Download 28 seasons in 5-10 min: `pip install nba-on-court`

**DomSamangy/NBA_Shots_04_25** (~600 stars, updated 2025)
- All NBA shots 2003-04 to 2024-25 as CSVs
- Columns: zone, XY coords, shot type, result, game date
- `git clone https://github.com/DomSamangy/NBA_Shots_04_25`

**Kaggle: cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024**
- CC0 license, 19,820+ games, moneyline/spread/total 2007-2025
- `kaggle datasets download cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024`

**NBA-Betting/NBA_AI** (~300 stars, active)
- SQLite DB download from GitHub Releases: 4,100 games, 3 seasons
- Pre-engineered GameStates features from PBP (momentum, scoring runs)
- Also has injury data

## Tier 2 — High Value

- **dblackrun/pbpstats**: Lineup on/off, possession-level, `pip install pbpstats`
- **josedv82/airball** (R): Travel miles, time zone changes, game density → port to Python
- **atlhawksfanatic/L2M**: Referee data via Last Two Minute Reports, CSV in repo
- **mxufc29/nbainjuries**: Injury history 2021-present, `pip install nbainjuries`
- **vishaalagartha/basketball_reference_scraper**: BPM, VORP, Win Shares, `pip install basketball-reference-scraper`
- **kyleskom/NBA-Machine-Learning-Sports-Betting** (~1.5k stars): SBR odds scraper + Kelly sizing
- **fivethirtyeight/data/nba-elo**: All-time Elo CSV, `wget https://raw.githubusercontent.com/fivethirtyeight/data/master/nba-elo/nbaallelo.csv`

## HuggingFace Assessment
Minimal useful NBA prediction data on HF:
- `dcayton/nba_tracking_data_15_16`: 2015-16 SportVU tracking (historic only, last public tracking year)
- Others are NLP/LLM benchmark datasets, not useful for prediction features

## Features NOT Yet in Our Engine (key gaps)
- Shot zone efficiency by court area
- Hustle stats (deflections, contested shots, screen assists)
- Player tracking speed/distance
- Lineup net rating (5-man unit)
- Travel distance + time zone changes
- Referee crew impact
- Injury-adjusted lineup quality
- Closing line value (market efficiency)
- PBP momentum/GameStates features

## 8 Proposals Inserted to Supabase (2026-03-28)
Categories: shot_zone_efficiency, hustle_stats, historical_odds, schedule_travel_fatigue,
referee_impact, injury_lineup_quality, speed_distance_tracking, lineup_net_rating_pbp

**Why:** All features above expected to contribute -0.002 to -0.005 Brier each (total possible ~-0.020 if all work).
**How to apply:** Prioritize hustle stats + shot zones first (nba_api, minimal effort). Use Kaggle GPU for all feature computation. Never run ML on VM.
