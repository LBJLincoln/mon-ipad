# NBA Free Data Sources — Complete Catalog
> Research date: 2026-03-28 | Priority ranked by Brier delta potential

## CRITICAL GAP DIAGNOSIS

Our feature engine has 37 categories and ~6135 raw features — but **all are team-level**. Categories 12, 19, 24, 26 use player impact features that are **estimated from box scores, not from real player-level APIs**. This is the core gap to close.

**What we lack that Montrucchio 2026 (Brier 0.199) had:**
- Shot-chart spatial embeddings (CNN -> PCA -> features) — estimated Brier delta: -0.004
- Real player availability / injury severity scores (not proxied)
- Play-type breakdown (isolation%, pick-and-roll%, transition%)
- Defensive matchup data (who guards whom, MATCHUP_MIN)

---

## TIER 1 — HIGHEST PRIORITY (Direct Brier impact, free, easy integration)

### 1.1 NBA.com Player-Level APIs via nba_api (FREE, no auth)

**Package:** `pip install nba_api`
**Source:** https://github.com/swar/nba_api
**Rate limit:** ~1 req/sec (add delays), blocked on AWS/GCP but works locally and on HF Spaces

**Critical note:** NBA.com blocks some cloud IPs. Use HF Space or VM with proper headers:
```python
headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nba.com/'}
```

#### Endpoint Catalog — All Useful Endpoints We Are NOT Using:

| Endpoint | Class | Key Fields | Feature Category |
|----------|-------|-----------|------------------|
| LeagueHustleStatsPlayer | `from nba_api.stats.endpoints import LeagueHustleStatsPlayer` | CONTESTED_SHOTS, DEFLECTIONS, CHARGES_DRAWN, LOOSE_BALLS_RECOVERED, BOX_OUTS | Cat 38 (new) |
| LeagueDashPtStats (SpeedDistance) | `LeagueDashPtStats(pt_measure_type="SpeedDistance")` | DIST_MILES, DIST_MILES_OFF, DIST_MILES_DEF, AVG_SPEED, AVG_SPEED_OFF, AVG_SPEED_DEF | Cat 38 |
| LeagueDashPtStats (Passing) | `LeagueDashPtStats(pt_measure_type="Passing")` | AST, PASSES_MADE, PASSES_RECEIVED, SECONDARY_AST, POTENTIAL_AST | Cat 38 |
| LeagueDashPtStats (Touches) | `LeagueDashPtStats(pt_measure_type="Touches")` | TOUCHES, FRONT_CT_TOUCHES, TIME_OF_POSS, AVG_SEC_PER_TOUCH | Cat 38 |
| LeagueDashPtStats (Drives) | `LeagueDashPtStats(pt_measure_type="Drives")` | DRIVES, DRIVE_PTS, DRIVE_FGA, DRIVE_FTA, DRIVE_EFG_PCT | Cat 38 |
| LeagueDashPtStats (Defense) | `LeagueDashPtStats(pt_measure_type="Defense")` | DEF_RIM_FGA, DEF_RIM_FGM, DEF_RIM_FG_PCT, DEF_2PT_PCT, DEF_3PT_PCT | Cat 38 |
| LeagueDashPlayerClutch | `LeagueDashPlayerClutch` | W_PCT, PLUS_MINUS, PTS, REB, AST in last 5 min of close games | Cat 43 (exists, needs real data) |
| PlayerDashPtShots | `PlayerDashPtShots` | shot zones: restricted area, paint, mid-range, corner 3, above break 3 | Cat 38 (shot zones) |
| LeagueDashPlayerPtShot | `LeagueDashPlayerPtShot` | FGA/FGM by shot zone for all players | Cat 38 |
| LeagueDashPlayerShotLocations | `LeagueDashPlayerShotLocations` | EFG_PCT by zone for all players | Cat 38 |
| BoxScorePlayerTrackV3 | Per-game: `BoxScorePlayerTrackV3(game_id=...)` | SPD, DIST, REBOUNDCHANCESOFF, REBOUNDCHANCESDEF, TOUCHES, PASSES | pre-game can't use, but historical |
| LeagueSeasonMatchups | `LeagueSeasonMatchups` | MATCHUP_MIN, DEF_PLAYER_ID, OFF_PLAYER_ID, MATCHUP_FG_PCT, PARTIAL_POSS | Cat 14 (real data) |
| MatchupsRollup | `MatchupsRollup` | Season-level matchup rollup: who guards whom across all games | Cat 14 |
| PlayerEstimatedMetrics | `PlayerEstimatedMetrics` | E_OFF_RATING, E_DEF_RATING, E_NET_RATING, E_PACE | Cat 12 (real data) |
| LeagueDashPtDefend | `LeagueDashPtDefend` | FREQ, FG_PCT, EFG_PCT by defender distance (tight/open/6+ ft) | Cat 14 |
| ShotChartDetail | `ShotChartDetail(player_id=..., team_id=..., season=...)` | LOC_X, LOC_Y, SHOT_TYPE, SHOT_ZONE_AREA, EVENT_TYPE | Cat 38 (spatial) |
| ShotChartLineupDetail | `ShotChartLineupDetail` | Shot charts by lineup combination | Cat 38 |
| PlayerGameLog | `PlayerGameLog(player_id=..., season=...)` | Per-game stats for each player: PTS, REB, AST, MIN, PLUS_MINUS | Cat 26 (real data) |
| LeagueDashPlayerStats | `LeagueDashPlayerStats` | Full player stats leaderboard — AVAILABLE NOW | Cat 12, 26 |
| PlayerCareerStats | `PlayerCareerStats(player_id=...)` | Career splits by season | Cat 32 (Bayesian priors) |
| TeamPlayerOnOffSummary | `TeamPlayerOnOffSummary` | On/off court ratings per player | Cat 26 |
| PlayerDashPtPass | `PlayerDashPtPass` | PASSES_MADE, AST, SECONDARY_AST, POTENTIAL_AST | Cat 38 |
| PlayerDashPtReb | `PlayerDashPtReb` | OREB_CONTEST, DREB_CONTEST, REB_CHANCE | Cat 38 |
| PlayerDashPtShotDefend | `PlayerDashPtShotDefend` | Shots defended at rim, mid, 3pt by player | Cat 14 |

**Implementation plan:**
```python
from nba_api.stats.endpoints import (
    LeagueHustleStatsPlayer,
    LeagueDashPtStats,
    LeagueDashPlayerClutch,
    LeagueDashPlayerShotLocations,
    LeagueSeasonMatchups,
    PlayerEstimatedMetrics,
    ShotChartDetail,
    PlayerGameLog,
)
import time

def fetch_player_tracking_season(season="2024-25"):
    """Fetch all tracking stats for a season. ~15 API calls, ~2 min with rate limiting."""
    results = {}

    # Speed/Distance
    time.sleep(1)
    spd = LeagueDashPtStats(season=season, pt_measure_type="SpeedDistance")
    results['speed_distance'] = spd.get_data_frames()[0]

    # Hustle stats
    time.sleep(1)
    hustle = LeagueHustleStatsPlayer(season=season)
    results['hustle'] = hustle.get_data_frames()[0]

    # Clutch
    time.sleep(1)
    clutch = LeagueDashPlayerClutch(season=season)
    results['clutch'] = clutch.get_data_frames()[0]

    # Shot locations
    time.sleep(1)
    shots = LeagueDashPlayerShotLocations(season=season)
    results['shot_locations'] = shots.get_data_frames()[0]

    # Estimated metrics (advanced)
    time.sleep(1)
    metrics = PlayerEstimatedMetrics(season=season)
    results['estimated_metrics'] = metrics.get_data_frames()[0]

    return results
```

**Expected Brier delta:** -0.003 to -0.006 (player-level features replace estimated proxies)

---

### 1.2 ShotChartDetail — Spatial Embeddings (Montrucchio 2026 method)

**URL:** `https://stats.nba.com/stats/shotchartdetail`
**Via nba_api:** `ShotChartDetail(player_id=..., team_id=0, season=..., season_type_all_star="Regular Season")`
**Free:** Yes, no auth
**Format:** JSON -> DataFrame with LOC_X, LOC_Y, SHOT_MADE_FLAG, SHOT_DISTANCE, SHOT_ZONE_AREA

**Montrucchio 2026 pipeline:**
1. Fetch per-player season shot chart -> rasterize to 48x48 grid
2. Compute zone FG% in 5 zones: restricted area, paint non-RA, mid-range, corner 3, above-break 3
3. Compute xEFG (expected eFG from shot location distribution)
4. For team: aggregate player shot charts weighted by usage/minutes
5. PCA or CNN for spatial embedding -> 10-20 components as features

**Pre-built dataset (2004-2025):** https://github.com/DomSamangy/NBA_Shots_04_25
- All NBA regular season shots from 2003-04 to 2024-25 in a single CSV
- Fields: PLAYER_ID, GAME_DATE, SHOT_DISTANCE, LOC_X, LOC_Y, SHOT_MADE_FLAG
- Google Drive link: https://drive.google.com/file/d/1uktZ3wcE5670ZAR5c7MciMHbu8-zPMwM/view

**ETL pipeline code:**
```python
# Zone-based shot quality features (no CNN needed — faster than rasterization)
def compute_team_shot_quality(shot_df, team_id, season):
    """Compute 10 shot quality features per team for Cat 38."""
    team_shots = shot_df[shot_df['TEAM_ID'] == team_id]
    zones = ['Restricted Area', 'In The Paint (Non-RA)', 'Mid-Range',
             'Left Corner 3', 'Right Corner 3', 'Above the Break 3']
    feats = {}
    for zone in zones:
        z = team_shots[team_shots['SHOT_ZONE_AREA'] == zone]
        feats[f'fg_pct_{zone.lower().replace(" ","_")}'] = (
            z['SHOT_MADE_FLAG'].mean() if len(z) > 0 else 0.45
        )
    # xEFG: shot distribution × league-average zone FG%
    total = len(team_shots)
    feats['three_pt_rate'] = (team_shots['SHOT_TYPE'] == '3PT Field Goal').mean()
    feats['rim_rate'] = (team_shots['SHOT_ZONE_BASIC'] == 'Restricted Area').mean()
    feats['mid_range_rate'] = (team_shots['SHOT_ZONE_BASIC'] == 'Mid-Range').mean()
    feats['xefg'] = (0.65 * feats['rim_rate'] + 0.40 * feats['mid_range_rate'] +
                     0.53 * feats['three_pt_rate'])
    return feats
```

**Expected Brier delta:** -0.003 to -0.005 (Montrucchio 2026 ablation confirmed)

---

### 1.3 Official NBA Injury Report (FREE, PDF scraping)

**URL pattern:** `https://ak-static.cms.nba.com/referee/injury/Injury-Report_{DATE}_{TIME}PM.pdf`
**Example:** `https://ak-static.cms.nba.com/referee/injury/Injury-Report_2025-12-28_05_00PM.pdf`
**Format:** PDF -> parse with pdfplumber or tabula-py
**Mandatory reports:** Teams must report by 5 PM local time the day before games

**Scraping approach:**
```python
import pdfplumber, requests
from datetime import datetime, timedelta

def fetch_nba_injury_report(game_date: str) -> pd.DataFrame:
    """game_date format: YYYY-MM-DD"""
    # Reports published day-of at 5PM local time of each team
    report_date = datetime.strptime(game_date, "%Y-%m-%d")
    url = f"https://ak-static.cms.nba.com/referee/injury/Injury-Report_{game_date}_05_00PM.pdf"
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    if r.status_code == 200:
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            # Extract table rows: Team, Player, Status, Reason
            tables = [t for page in pdf.pages for t in page.extract_tables()]
        return pd.DataFrame(tables[0][1:], columns=['date','time','matchup','team','player','status','reason'])
    return pd.DataFrame()

# Status mapping to numeric feature
STATUS_MAP = {'Out': 1.0, 'Doubtful': 0.8, 'Questionable': 0.5, 'Probable': 0.2, 'Available': 0.0}
```

**Key features to derive:**
- `injury_star_out`: 1.0 if primary scorer (>20 PPG) is OUT
- `injury_impact_score`: weighted sum of injured players' WAR (from RAPTOR)
- `injury_adj_lineup_rating`: team net rating with injury adjustments
- Real injury data replaces our proxy `h_injury_impact_score` feature

**Expected Brier delta:** -0.002 to -0.004 (our current proxy is noise; real injury data is signal)

---

### 1.4 FiveThirtyEight RAPTOR Data (FREE, GitHub)

**URL:** https://github.com/fivethirtyeight/data/tree/master/nba-raptor
**Also at:** https://github.com/fivethirtyeight/nba-player-advanced-metrics
**Format:** CSV, direct download
**Coverage:** 1976-present (box-score estimates pre-2014, full tracking 2014+)
**Last update:** FiveThirtyEight shut down in 2023 — data frozen at 2023 season

**Files:**
- `historical_RAPTOR_by_player.csv` — RAPTOR_O, RAPTOR_D, RAPTOR_total per player-season
- `latest_RAPTOR_by_player.csv` — most recent season
- Also on HuggingFace: `andrewkroening/538-NBA-Historical-Raptor`

**Key fields to use as features:**
```python
# raptor_o: offensive RAPTOR (pts per 100 poss above league avg)
# raptor_d: defensive RAPTOR
# raptor_total: raptor_o + raptor_d
# pace_impact: player's effect on team pace
# war_total: wins above replacement

def team_raptor_features(roster, raptor_df, season):
    """Aggregate RAPTOR for top 8 players in rotation."""
    players = roster['player_id'].values
    rap = raptor_df[(raptor_df['player_id'].isin(players)) &
                    (raptor_df['season'] == season)]
    top8 = rap.nlargest(8, 'mp')  # minutes-weighted
    feats = {
        'raptor_top_off': top8['raptor_o'].nlargest(3).mean(),  # top 3 O players
        'raptor_top_def': top8['raptor_d'].nlargest(3).mean(),  # top 3 D players
        'raptor_team_total': (top8['raptor_total'] * top8['mp']).sum() / top8['mp'].sum(),
        'raptor_depth_8': top8['raptor_total'].mean(),
        'war_team': top8['war_total'].sum(),
    }
    return feats
```

**Note:** For 2024-25 season, use nbarapm.com RAPM data or Basketball-Index PIPM instead
**Expected Brier delta:** -0.001 to -0.003 (replaces proxy `key_player_impact` in Cat 12/26)

---

### 1.5 Referee Assignment Data (FREE, scraped)

**NBA Official:** https://official.nba.com/referee-assignments/ (posted 9 AM ET game day)
**Covers.com:** https://www.covers.com/sport/basketball/nba/referees/assignments
**NBAstuffer:** https://www.nbastuffer.com/2025-2026-nba-referee-stats/ (Excel download)
**RefMetrics:** https://www.refmetrics.com/ (largest database, 161,491+ games, some free)
**RefAnalytics:** https://refanalytics.com/ (daily scouting reports, free)
**The F5 Database:** https://thef5.substack.com/p/the-f5s-nba-referee-database (foul counts 2020-21+)

**Features to extract:**
```python
REF_FEATURES = {
    'ref_avg_total_fouls': float,      # Avg total fouls called per game (pace proxy)
    'ref_avg_total_pts': float,         # Avg total points in games (over/under proxy)
    'ref_home_foul_bias': float,        # (home_fouls_called - away_fouls_called) / game
    'ref_home_win_pct': float,          # Home team win% with this ref
    'ref_foul_rate_per_48': float,      # Normalized foul rate
    'ref_home_ats_cover': float,        # Home team ATS cover% with this ref
    'crew_avg_pts': float,              # 3-man crew average total pts
    'crew_home_bias': float,            # Crew-level home advantage bias
    'ref_ot_rate': float,               # Overtime rate (close game driver)
    'ref_experience_years': int,        # Seniority proxy
}
```

**NBAstuffer Excel download (free throughout season):**
- Columns: GAME, REF1, REF2, REF3, HOME_PTS, AWAY_PTS, TOTAL, H_FOULS, A_FOULS, HOME_WIN
- Provides: Home team W%, average points, foul differential by referee

**Expected Brier delta:** -0.001 to -0.002 (referee effect is ~1.5-2 pts/game on foul differential)

---

## TIER 2 — HIGH PRIORITY (Free, moderate integration effort)

### 2.1 Basketball-Reference.com Advanced Stats

**URL:** https://www.basketball-reference.com/leagues/NBA_2026_advanced.html
**Rate limit:** 20 requests/minute (strict — add `time.sleep(4)`)
**Python package:** `pip install basketball-reference-scraper` (vishaalagartha/basketball_reference_scraper)
**Alternative:** `pip install sportsreference` (deprecated but functional)

**Available data tables:**
| Table | URL suffix | Key columns |
|-------|-----------|-------------|
| Advanced | `/leagues/NBA_2026_advanced.html` | PER, TS%, 3PAr, FTr, ORB%, DRB%, TRB%, AST%, STL%, BLK%, TOV%, USG%, OWS, DWS, WS, BPM, VORP |
| Per 36 minutes | `/leagues/NBA_2026_per_minute.html` | Stats normalized to per-36-min |
| Per 100 possessions | `/leagues/NBA_2026_per_poss.html` | Pace-adjusted offensive/defensive stats |
| Shooting | `/leagues/NBA_2026_shooting.html` | FGA/FG% by distance: 0-3ft, 3-10ft, 10-16ft, 16-3pt, 3pt |

**Integration approach:**
```python
from basketball_reference_scraper.players import get_stats
import time

def get_player_advanced_season(player_name, season=2026):
    time.sleep(4)  # Rate limit
    stats = get_stats(player_name, stat_type='ADVANCED', playoffs=False, ask_season=season)
    return stats[['PER', 'TS_PCT', 'USG_PCT', 'OWS', 'DWS', 'WS', 'BPM', 'VORP']].iloc[-1]
```

**Key aggregate features per team:**
- Weighted USG% of top 3 players (star concentration)
- Average BPM of top 8 by minutes (team quality estimate)
- Shooting table: distance distribution (corner 3 rate, rim rate) as xEFG proxy

**Expected Brier delta:** -0.001 to -0.002

---

### 2.2 Play-Type Data via hoopR / NBA.com Synergy (FREE)

**Source:** NBA.com Synergy (free limited access)
**URL:** https://www.nba.com/stats/teams/ball-handler (pick-and-roll ball handler stats)
**Pre-scraped dataset:** https://github.com/DomSamangy/NBA_Play_Types_12_25 (2012-2025, 13 seasons)
**Via R hoopR:** `nba_synergyplaytypes(season="2024-25")`

**Play types available (via NBA.com, 13 categories):**
1. Isolation — frequency, PPP (points per possession)
2. Pick-and-Roll Ball Handler
3. Pick-and-Roll Roll Man
4. Post Up
5. Spot Up
6. Handoff
7. Cut
8. Off Screen
9. Off Rebound
10. Transition
11. Miscellaneous

**Features to extract:**
```python
PLAY_TYPE_FEATURES = [
    'transition_freq',      # % of possessions in transition (pace proxy)
    'iso_ppp',              # Isolation PPP (star quality proxy)
    'pnr_freq',             # Pick-and-roll frequency
    'pnr_ball_ppp',         # P&R ball handler efficiency
    'post_up_ppp',          # Post-up efficiency (size advantage)
    'cut_freq',             # Cutting frequency (off-ball movement quality)
    'spot_up_freq',         # Spot-up shooting frequency (3pt spacing)
    'opp_transition_freq',  # Opponent's transition rate (defensive speed)
    'opp_iso_freq',         # Opponent isolation rate
]
```

**Expected Brier delta:** -0.001 to -0.003 (play style features capture team identity that box scores miss)

---

### 2.3 DomSamangy NBA Play Types 2012-2025 (FREE, GitHub)

**URL:** https://github.com/DomSamangy/NBA_Play_Types_12_25
**Format:** CSV, all 13 seasons
**Content:** NBA player play type data — PPP, frequency, percentile by play type
**Download:** Direct from GitHub releases

**This is immediately usable** — aggregate to team level:
- Team transition_freq (transition %)
- Team spot_up_ppp weighted by usage
- Team pnr_bh_ppp (P&R primary ball handler efficiency)

---

### 2.4 Play-by-Play Data — pbpstats (FREE, Python)

**Package:** `pip install pbpstats` (dblackrun/pbpstats)
**Source:** stats.nba.com + data.nba.com + pbpstats.com
**URL:** https://github.com/dblackrun/pbpstats

**Pre-assembled dataset:** https://github.com/shufinskiy/nba_data
- Play-by-play from stats.nba.com (1996/97+), data.nba.com (2016/17+), pbpstats.com (2000/01+)
- Shots data with season 1996/97

**Key derived features:**
```python
# From PBP: derive clutch performance features (last 5 min, margin ≤5)
def compute_clutch_stats(pbp_df, team_id, n_games=20):
    clutch = pbp_df[
        (pbp_df['PCTIMESTRING'].str[:2].astype(int) <= 5) &  # last 5 min
        (pbp_df['SCOREMARGIN'].abs() <= 5)
    ]
    team_clutch = clutch[clutch['TEAM_ID'] == team_id]
    return {
        'clutch_fg_pct': team_clutch['SHOT_MADE_FLAG'].mean(),
        'clutch_tov_rate': (team_clutch['EVENTMSGTYPE'] == 5).mean(),
        'clutch_plus_minus': team_clutch['SCORE_MARGIN_CHANGE'].sum(),
        'clutch_win_pct': ...,  # terminal clutch win rate
    }
```

**Expected Brier delta:** -0.001 to -0.002 (clutch features are real signal for close-game prediction)

---

### 2.5 Historical Betting Odds — SportsBookReviewsOnline (FREE)

**URL:** https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba/nbaoddsarchives.htm
**Format:** Excel/HTML tables per season (2007-present)
**Columns:** Date, Home, Away, 1st-half-ML, Final-ML, Open-Spread, Close-Spread, Open-Total, Close-Total

**Pre-scraped GitHub version:** https://github.com/FinnedAI/sportsbookreview-scraper
**Kaggle version:** https://www.kaggle.com/datasets/ehallmar/nba-historical-stats-and-betting-data
**Also:** https://www.kaggle.com/datasets/erichqiu/nba-odds-and-scores

**Uses for our model:**
1. Line movement: Open vs Close spread delta -> steam move indicator
2. Line consensus: multiple books open vs close -> sharp money indicator
3. Historical closing line as ground truth calibration target
4. CLV (closing line value) calculation for bet evaluation

**Integration with Cat 9 (Market Microstructure):**
```python
# Currently Cat 9 features are mostly estimated — real odds data changes this
def compute_market_features(odds_row):
    return {
        'open_spread': odds_row['OpenSpread'],
        'close_spread': odds_row['CloseSpread'],
        'line_movement': odds_row['CloseSpread'] - odds_row['OpenSpread'],  # steam
        'open_total': odds_row['OpenTotal'],
        'close_total': odds_row['CloseTotal'],
        'total_movement': odds_row['CloseTotal'] - odds_row['OpenTotal'],
        'sharp_ml_diff': odds_row['CloseML'] - odds_row['OpenML'],         # sharp indicator
        'home_close_prob': ml_to_prob(odds_row['HomeCloseML']),
        'away_close_prob': ml_to_prob(odds_row['AwayCloseML']),
    }
```

**Expected Brier delta:** -0.002 to -0.004 (Cat 9 with real data vs proxies = large improvement)

---

### 2.6 ActionNetwork — Live Odds + Public Money (FREE, no key)

**URL:** https://api.actionnetwork.com/web/v1/scoreboard/nba
**Free tier:** Unlimited (public API, no authentication)
**Coverage:** Live moneyline, spread, totals + public bet % + public money %
**Sharp/square:** Unique source for ticket % vs money % divergence (steam detection)

**Key endpoint:**
```
GET https://api.actionnetwork.com/web/v1/scoreboard/nba?periods=event&bookIds=15,30,68,69,123
```

**Book IDs:**
- 15 = DraftKings, 30 = FanDuel, 68 = BetMGM, 69 = Caesars, 123 = Pinnacle (sharp)
- 19 = BetRivers, 76 = PointsBet, 283 = Bet365, 100 = Bovada

**Public money fields per game:**
- `ml_away_public` / `ml_home_public` — % of tickets bet on each side
- `ml_away_money` / `ml_home_money` — % of total dollars on each side
- Same pattern for spread and totals

**Sharp/square signal:** When money% diverges from ticket% by 15%+, sharp bettors are fading the public.

**Script:** `/home/termius/mon-ipad/scripts/fetch_free_odds.py`

**Expected Brier delta:** Public money % as Cat 9 feature -> -0.002 to -0.003 (market microstructure with real sharp data)

---

### 2.7 Injury Data — ESPN / RotoWire Scraping (FREE)

**ESPN Injuries page:** https://www.espn.com/nba/injuries
**ESPN undocumented API:**
```
GET https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries
```
**RotoWire:** https://www.rotowire.com/basketball/injury-report.php (HTML scraping)
**Basketball-Reference injuries:** https://www.basketball-reference.com/friv/injuries.fcgi

**ESPN Hidden API (documented by pseudo-r/Public-ESPN-API):**
```python
import requests
resp = requests.get(
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries",
    headers={'User-Agent': 'Mozilla/5.0'}
)
data = resp.json()  # Returns structured injury data
```

**Key features:**
- `star_player_out`: Is a player averaging >18 PPG listed OUT?
- `pts_lost`: Sum of PPG of all players listed OUT or Doubtful
- `usage_lost`: Sum of USG% of injured players
- `defensive_anchor_out`: Is primary rim protector (BLK% > 4%) out?
- `playmaker_out`: Is primary ball-handler/PG out?

**Expected Brier delta:** -0.002 to -0.004 (injury info is among top-5 predictive signals)

---

## TIER 3 — MEDIUM PRIORITY (Free, higher effort or lower delta)

### 3.1 DARKO Player Projections (Free website, scraping required)

**URL:** https://www.darko.app/
**Also at:** https://www.nbarapm.com/ (DARKO + other RAPM-based metrics)
**What it is:** Daily updated player projections using Kalman filter on box score + play-by-play

**Key metrics:**
- DPM (DARKO Plus-Minus): overall pts/100 above league avg
- ODPM: offensive
- DDPM: defensive
- Updates daily — provides today's projected player quality

**GitHub ML integration:** https://github.com/notoctosting/NBA-ML-with-DARKO
**Expected Brier delta:** -0.001 to -0.002 (better player quality estimates than box-score proxies)

---

### 3.2 Player Props Historical Data (GitHub repos)

**akhilpenumudy/NBA-Player-Prop-Cheat-Sheet-Maker:**
https://github.com/akhilpenumudy/NBA-Player-Prop-Cheat-Sheet-Maker
- Real-time props from PrizePicks + FanDuel
- Hit rate tracking
- nba_api integration for player averages vs opponent

**chevyphillip/plus-ev-model:**
https://github.com/chevyphillip/plus-ev-model
- NBA player props prediction with MotherDuck (DuckDB) integration
- XGBoost models for NBA player props

**VinceDiR/Prop_Betting_Regression_Project:**
https://github.com/VinceDiR/Prop_Betting_Regression_Project
- Regression models for NBA prop betting
- Feature engineering: player avg vs opponent defensive rating

**Use case for Nomos42:**
Props lines reveal expected player output -> implied team quality features:
```python
def props_implied_team_strength(props_data, game):
    """Convert player prop lines into team-level features."""
    home_pts_line = sum(p['line'] for p in props_data if p['team'] == game.home_team
                        and p['market'] == 'player_points')
    return {
        'implied_team_scoring': home_pts_line,     # Sum of all player pts lines
        'star_pts_expectation': max(p['line'] for p in props_data if ...),
        'props_implied_total': home_pts_line + away_pts_line
    }
```

---

### 3.3 FiveThirtyEight NBA Elo (FREE, Kaggle)

**Kaggle dataset:** https://www.kaggle.com/datasets/fivethirtyeight/fivethirtyeight-nba-elo-dataset
**GitHub:** https://github.com/fivethirtyeight/data/tree/master/nba-elo
**Coverage:** 1946 to present (manually maintained post-538 shutdown)
**Key fields:** `elo1_pre`, `elo2_pre`, `elo_prob1`, `elo_prob2`, `raptor1_pre`, `raptor2_pre`

**NOTE:** Our Cat 24 already has Elo features. The FiveThirtyEight dataset adds:
- Pre-game RAPTOR-based win probability (different from our Elo)
- Historical validation of our Elo implementation
- 5-year decay Elo variant (`team_elo_5_y` from Alves & Barbosa 2025)

---

### 3.4 Google Trends via pytrends (FREE)

**Package:** `pip install pytrends`
**URL:** https://github.com/GeneralMills/pytrends
**New official API (alpha 2025):** https://developers.google.com/search/blog/2025/07/trends-api

**Hypothesis:** Team search interest spike before games correlates with lineup changes, injury news, or star absences that markets don't fully price in.

```python
from pytrends.request import TrendReq
import time

def get_nba_team_interest(team_name, lookback_days=7):
    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload([team_name, 'NBA'], timeframe=f'now {lookback_days}-d')
    time.sleep(1)
    df = pytrends.interest_over_time()
    return {
        'search_interest_7d': df[team_name].mean(),
        'search_interest_spike': df[team_name].iloc[-1] / df[team_name].mean(),
    }
```

**Caveat:** pytrends is an unofficial API, prone to CAPTCHAs. Rate limit severely.
**Expected Brier delta:** -0.0005 to -0.001 (small signal, mostly useful for outlier games)

---

### 3.5 Reddit r/nba via PRAW (FREE)

**URL:** https://praw.readthedocs.io/
**Auth:** Create free app at https://www.reddit.com/prefs/apps

**Game thread sentiment:**
```python
import praw
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

def get_pregame_sentiment(reddit, team_name, hours_before=24):
    """Scrape r/nba posts about team in 24h before game."""
    posts = reddit.subreddit('nba').search(
        team_name, sort='new', time_filter='day', limit=50
    )
    analyzer = SentimentIntensityAnalyzer()
    scores = [analyzer.polarity_scores(p.title)['compound'] for p in posts]
    return {
        'reddit_sentiment_24h': np.mean(scores) if scores else 0.0,
        'reddit_post_volume': len(scores),
    }
```

**Expected Brier delta:** -0.0005 to -0.001 (marginal signal, already in our Cat 16 as proxy)
**Implementation in MEMORY:** Reddit OAuth2 app creation required (pending per project memory)

---

### 3.6 BallDontLie API v2 (FREE tier with API key)

**URL:** https://docs.balldontlie.io/
**Free tier:** Generous rate limits, requires free account at app.balldontlie.io
**v2 additions:** 100+ advanced metrics, 8 NBA data sources, hustle stats, per-period breakdowns

**Key endpoints:**
```
GET /nba/v2/stats/advanced?game_id={id}
GET /nba/v2/players/stats/seasons?player_id={id}&season={year}
GET /nba/v2/games/odds (player props, betting odds — LIVE only)
GET /nba/v2/players/injuries (injury status — LIVE 2025+ only)
```

**Limitation:** Lineup data only from 2025+. Historical player props not available.
**Best use:** Live day-of-game injury status (replaces PDF scraping), starting lineup confirmation

---

### 3.7 Kaggle NBA Datasets

| Dataset | URL | Content | Seasons |
|---------|-----|---------|---------|
| NBA Database (wyattowalsh) | https://www.kaggle.com/datasets/wyattowalsh/basketball | Full NBA database SQLite | 1946-2023 |
| NBA Historical Stats + Betting | https://www.kaggle.com/datasets/ehallmar/nba-historical-stats-and-betting-data | Stats + odds | 2012-2018 |
| NBA Odds and Scores | https://www.kaggle.com/datasets/erichqiu/nba-odds-and-scores | Moneylines + scores | Recent |
| NBA Player Statistics | https://www.kaggle.com/datasets/joebeachcapital/nba-player-statistics | Per-game stats | 2024-25 |
| NBA 2024-25 Season Stats | https://www.kaggle.com/datasets/columbiaave/nba-2024-2025-season-stats | Per-game + advanced | 2024-25 |

---

### 3.8 hoopR — R Package with 127 NBA Endpoints (FREE)

**Package:** R: `install.packages('hoopR')`, Python: no native port
**URL:** https://hoopr.sportsdataverse.org/
**Wrapper for:** All NBA Stats API endpoints + ESPN + full PBP since 2002

**Best Python alternative:** Call hoopR via subprocess or use nba_api directly
**Key unique functions:**
- `nba_synergyplaytypes()` — Play type PPP by team/player
- `nba_leaguedashptteamdefend()` — Team defense by shot distance
- `nba_boxscoreadvancedv3()` — Advanced per-game box scores
- `nba_leaguedashptstats()` — All tracking stats (SpeedDistance, Passing, Touches, etc.)

---

## TIER 4 — ALTERNATIVE/UNCONVENTIONAL (Lower priority, experimental)

### 4.1 NBAnation / NBASense (Shot Quality Models)

**URL:** http://nbasense.com/nba-api/
**What it provides:** Shot quality models, historical efficiency
**Access:** Limited free endpoints

### 4.2 DraftKings/FanDuel Props (Live scraping)

**PrizePicks undocumented API:**
```
GET https://api.prizepicks.com/projections?league_id=7&per_page=500&in_game=false
```
No auth required (unauthenticated JSON API).
Fields: player name, stat_type (Points/Rebounds/Assists), line_score, flash_sale_line_score

**PrizePicker ML tool:**
https://github.com/shoumik123majumdar/PrizePicker
Uses nba_api + PrizePicks scraping for props prediction

### 4.3 Attendance Data (ESPN + InsideHoops)

**ESPN Attendance API:**
```
GET https://www.espn.com/nba/attendance/_/year/2025/sort/homeTotal
```
**InsideHoops:** http://www.insidehoops.com/attendance.shtml (HTML scrape)

**Hypothesis:** Crowd capacity % inversely correlates with home court advantage in modern NBA
**Expected Brier delta:** Near zero for modern era (consistent 90%+ attendance league-wide)

### 4.4 RefMetrics + NBAstuffer Referee Data

**NBAstuffer Excel download:** https://www.nbastuffer.com/2025-2026-nba-referee-stats/
- Free throughout season, Excel format
- Columns: home W%, avg pts, foul differential

**Covers.com referee assignments:**
https://www.covers.com/sport/basketball/nba/referees/assignments
- Posted morning of game
- Includes: ref names, career over% stats, home cover%

**RefAnalytics daily reports:** https://refanalytics.com/
- Free daily scouting reports on officials
- Foul tendency: does this ref favor drives to rim vs perimeter?

**Our Cat 11/27 already has referee features** — but they use estimated values. Replace with real ref data.

---

## TIER 5 — GITHUB REPOSITORIES TO EXAMINE

### Prediction Models with Data Pipelines

| Repo | URL | Why Useful |
|------|-----|-----------|
| NBA-Betting/NBA_AI | https://github.com/NBA-Betting/NBA_AI | Full PBP->GameStates->Features->Predictions pipeline, 2023-2026 |
| NBA-Betting/NBA_Betting | https://github.com/NBA-Betting/NBA_Betting | Comprehensive system: 500+ features, profitable ATS |
| kyleskom/NBA-Machine-Learning | https://github.com/kyleskom/NBA-Machine-Learning-Sports-Betting | XGBoost + NN, moneylines + totals, SBR odds integration |
| DomSamangy/NBA_Shots_04_25 | https://github.com/DomSamangy/NBA_Shots_04_25 | All shots 2004-2025, CSV download |
| DomSamangy/NBA_Play_Types_12_25 | https://github.com/DomSamangy/NBA_Play_Types_12_25 | Play type data 2012-2025 |
| shufinskiy/nba_data | https://github.com/shufinskiy/nba_data | PBP data 1996-2025, all sources |
| dblackrun/pbpstats | https://github.com/dblackrun/pbpstats | PBP parsing library |
| fivethirtyeight/data/nba-raptor | https://github.com/fivethirtyeight/data/tree/master/nba-raptor | RAPTOR 1976-2023 |
| fivethirtyeight/nba-player-advanced-metrics | https://github.com/fivethirtyeight/nba-player-advanced-metrics | WAR, RAPTOR, Elo |
| saccofrancesco/deepshot | https://github.com/saccofrancesco/deepshot | Deep learning NBA predictions |
| parlayparlor/nba-prop-prediction-model | https://github.com/parlayparlor/nba-prop-prediction-model | Props tool, nba_api integration |
| akhilpenumudy/NBA-Prop-Cheat-Sheet | https://github.com/akhilpenumudy/NBA-Player-Prop-Cheat-Sheet-Maker | PrizePicks + nba_api |

---

## IMPLEMENTATION PRIORITY RANKING

| Priority | Source | Effort | Estimated Brier Delta | Cat |
|----------|--------|--------|----------------------|-----|
| 1 | Shot chart zones (DomSamangy CSV) | 4h | -0.004 | Cat38 |
| 2 | Real injury severity (NBA PDF reports) | 3h | -0.003 | Cat12 |
| 3 | nba_api tracking: hustle + speed + touches | 6h | -0.003 | Cat38 |
| 4 | SBR historical odds (real Cat 9 data) | 4h | -0.003 | Cat9 |
| 5 | RAPTOR team quality aggregates | 2h | -0.002 | Cat24 |
| 6 | Play type frequencies (DomSamangy) | 2h | -0.002 | Cat38 |
| 7 | LeagueSeasonMatchups (defensive matchup data) | 4h | -0.002 | Cat14 |
| 8 | Referee assignment + NBAstuffer stats | 3h | -0.001 | Cat11 |
| 9 | PBP clutch stats (pbpstats) | 8h | -0.001 | Cat43 |
| 10 | BallDontLie day-of injury status | 2h | -0.001 | Cat12 |
| 11 | Props lines as implied team features | 4h | -0.001 | Cat9 |
| 12 | Google Trends team interest | 3h | -0.0005 | Cat21 |
| 13 | Reddit sentiment (PRAW) | 4h | -0.0005 | Cat16 |

**Combined maximum theoretical delta (independent, non-overlapping): -0.020 to -0.025**
**Realistic estimate (correlated signals): -0.008 to -0.015**

This would take us from 0.2157 to potentially 0.200-0.207, meeting our target.

---

## QUICK WINS — IMPLEMENT THIS WEEK

### Quick Win 1: Shot Zone Features (2h, highest ROI)
```python
# Use DomSamangy CSV (pre-downloaded, no API needed)
# URL: github.com/DomSamangy/NBA_Shots_04_25
# Compute for each team: rim_rate, corner3_rate, mid_range_rate, xefg_team
# Add as 4 features per team = 8 new features in Cat38
```

### Quick Win 2: Injury Score from Official NBA Report (2h)
```python
# Scrape ak-static.cms.nba.com/referee/injury/
# Match player names to RAPTOR data for WAR
# Compute: pts_lost, star_out, defensive_anchor_out
# Replace 8 proxy features in Cat12 with real data
```

### Quick Win 3: Real Referee Stats (2h)
```python
# Download NBAstuffer Excel: nbastuffer.com/2025-2026-nba-referee-stats/
# Match daily assignment from official.nba.com/referee-assignments/
# Features: ref_avg_total, ref_home_win_pct, crew_foul_rate
# Replace Cat11 proxy values with real historical ref stats
```

### Quick Win 4: Props Lines as Team Features (3h)
```python
# PrizePicks undocumented API (no auth needed):
# GET https://api.prizepicks.com/projections?league_id=7&per_page=500
# Sum player pts lines -> implied team scoring
# Add as pre-game features: h_implied_pts, a_implied_pts, implied_total
```

---

## DATA COLLECTION ARCHITECTURE

```
collect_player_data.py  (runs ONCE per season on HF Space)
    ├── fetch_tracking_season()     → data/player_tracking_{season}.parquet
    ├── fetch_shot_zones_season()   → data/shot_zones_{season}.parquet
    ├── fetch_play_types_season()   → data/play_types_{season}.parquet
    └── fetch_matchup_data()        → data/matchups_{season}.parquet

collect_daily_data.py  (runs daily, fast, low-data)
    ├── scrape_injury_report()      → data/injuries_{date}.json
    ├── fetch_referee_assignment()  → data/refs_{date}.json
    ├── fetch_props_lines()         → data/props_{date}.json
    └── fetch_live_odds()           → data/odds_{date}.json

feature_engine.py  (reads parquet + daily json)
    → JOIN player_tracking to team games by season
    → JOIN shot_zones to team games by season
    → MERGE injuries by game date
    → MERGE referee data by game date
    → MERGE props lines by game date
```

**Key constraint:** nba_api blocked on some cloud IPs. Collect on VM (local), cache to Supabase or S3, read from HF Spaces.

---

## NOTES ON NBA.COM IP RESTRICTIONS

NBA.com blocks requests from major cloud providers (AWS, GCP, Azure, DigitalOcean) on stats.nba.com endpoints. Solutions:
1. Run collection on VM (1 vCPU but data collection is I/O-bound, not CPU-bound)
2. Add `time.sleep(1-2)` between requests
3. Use residential proxy service (e.g., Bright Data has free tier)
4. Use Kaggle notebooks for bulk historical collection (Kaggle IPs usually work)
5. HF Spaces has been tested successfully with proper headers

**Required headers:**
```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.nba.com/',
    'Accept-Language': 'en-US,en;q=0.9',
    'Host': 'stats.nba.com',
    'Origin': 'https://www.nba.com',
}
```
