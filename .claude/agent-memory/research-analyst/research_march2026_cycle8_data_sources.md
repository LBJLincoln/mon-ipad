---
name: research_march2026_cycle8_data_sources
description: March 28 2026 cycle 8: Complete free NBA data source catalog — nba_api endpoints, shot charts, injuries, props, referee data, play types — player-level data to replace proxy features
type: project
---

# Research Cycle 8 — Free NBA Data Sources (2026-03-28)

**Why:** All 37 feature categories use team-level data or proxies for player-level data. Montrucchio 2026 (Brier 0.199) used shot chart spatial features and real player data. Closing this gap = -0.008 to -0.015 Brier.

**Full catalog:** `/home/termius/mon-ipad/docs/FREE-DATA-SOURCES.md`

## Top Priority Data Sources (ranked by Brier delta)

| Rank | Source | Type | Delta | Effort |
|------|--------|------|-------|--------|
| 1 | DomSamangy/NBA_Shots_04_25 | CSV download | -0.004 | 4h |
| 2 | NBA Official Injury Report PDFs | PDF scrape | -0.003 | 3h |
| 3 | nba_api LeagueHustleStatsPlayer | API no-auth | -0.002 | 2h |
| 4 | nba_api LeagueDashPtStats (tracking) | API no-auth | -0.002 | 3h |
| 5 | SBR Historical Odds (SportsBookReviewsOnline) | Excel DL | -0.003 | 4h |
| 6 | FiveThirtyEight RAPTOR CSV | CSV download | -0.002 | 2h |
| 7 | DomSamangy/NBA_Play_Types_12_25 | CSV download | -0.002 | 2h |
| 8 | nba_api LeagueSeasonMatchups | API no-auth | -0.002 | 4h |

## Key URLs

- Shot data: https://github.com/DomSamangy/NBA_Shots_04_25
- Play types: https://github.com/DomSamangy/NBA_Play_Types_12_25
- Injury PDFs: `https://ak-static.cms.nba.com/referee/injury/Injury-Report_{DATE}_{TIME}PM.pdf`
- RAPTOR: https://github.com/fivethirtyeight/data/tree/master/nba-raptor
- SBR Odds: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba/nbaoddsarchives.htm
- nba_api docs: https://github.com/swar/nba_api

## nba_api Endpoints NOT Currently Used

- LeagueHustleStatsPlayer — deflections, contested shots, charges drawn
- LeagueDashPtStats(SpeedDistance) — DIST_MILES, AVG_SPEED per player
- LeagueDashPtStats(Passing/Touches/Drives/Defense) — all tracking stats
- LeagueDashPlayerClutch — clutch W_PCT and PLUS_MINUS
- LeagueDashPlayerShotLocations — EFG% by zone
- ShotChartDetail — LOC_X, LOC_Y per shot
- LeagueSeasonMatchups / MatchupsRollup — defensive matchup data
- PlayerEstimatedMetrics — E_OFF_RATING, E_DEF_RATING
- TeamPlayerOnOffSummary — on/off court splits

## Critical Operational Note

NBA.com stats endpoints blocked on AWS/GCP/Azure. Collection must run on:
1. VM (1 vCPU is fine — I/O bound, not CPU)
2. Kaggle notebooks (usually works)
3. HF Spaces with proper headers (tested, works)

Headers required:
```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
}
```

## PrizePicks Undocumented API (no auth needed)

```
GET https://api.prizepicks.com/projections?league_id=7&per_page=500&in_game=false
```
Returns live player props lines — use to compute implied team scoring features.

## How to apply

When proposing feature additions, prioritize sources from this list in rank order. Shot zone features (rank 1) and injury PDFs (rank 2) are the highest-ROI quick wins with direct Brier evidence from Montrucchio 2026.
