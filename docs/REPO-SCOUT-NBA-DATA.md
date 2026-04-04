# NBA Data Repository Scout
> Generated: 2026-03-28 | Agent: repo-scout | Purpose: Free data sources for NBA game prediction

## TL;DR — Top 5 Immediate Downloads

| Priority | Source | What You Get | Download |
|----------|--------|-------------|----------|
| 1 | `shufinskiy/nba_data` | PBP + shots 1996-2025, pre-built CSVs | `pip install nba-on-court` |
| 2 | Kaggle `cviaxmiwnptr` | Betting odds 2007-2025, moneyline/spread/total | kaggle CLI |
| 3 | `DomSamangy/NBA_Shots_04_25` | Shot coordinates + zones 2004-2025 | git clone |
| 4 | `swar/nba_api` | Live API: hustle, tracking, shot zones, PBP | `pip install nba_api` |
| 5 | `NBA-Betting/NBA_AI` | SQLite DB: 4,100 games + features + PBP | GitHub Releases |

---

## 1. GitHub Repositories

### Tier 1 — Essential (use immediately)

#### swar/nba_api
- **URL**: https://github.com/swar/nba_api
- **Stars**: ~8,000
- **Last updated**: Active (2025)
- **What it provides**: Python client for every stats.nba.com endpoint. The critical endpoints for us:
  - `LeagueHustleStatsPlayer` — deflections, contested shots, charges drawn, screen assists, loose balls
  - `LeagueDashPtStats` (PtMeasureType=SpeedDistance) — DIST_FEET, DIST_MILES, AVG_SPEED, AVG_SPEED_OFF
  - `BoxScorePlayerTrackV3` — per-game tracking: speed, distance, touches, passes, rebounds chances
  - `LeagueDashPlayerShotLocations` — FG% by zone: Restricted Area, Paint non-RA, Mid-Range, Corner 3, Above-Break 3
  - `ShotChartDetail` — XY coordinates + SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE per shot
  - `LeagueDashPlayerStats` — standard + advanced per player per season
  - `LeagueDashTeamStats` — team-level splits
- **Language**: Python 3.10+
- **Dependencies**: requests, numpy
- **Direct use**: YES — install and query directly
- **Install**: `pip install nba_api`
- **Notes**: Rate-limited by NBA.com (~600ms delay between calls). Works with all active seasons. No API key needed.

#### shufinskiy/nba_data
- **URL**: https://github.com/shufinskiy/nba_data
- **Stars**: ~400
- **Last updated**: 2025 (active GitHub Actions auto-update)
- **What it provides**: Pre-built CSV downloads for:
  - PBP from stats.nba.com (`nbastats`) — 1996/97 to present
  - PBP from data.nba.com (`datanba`) — 2016/17 to present
  - PBP from pbpstats.com (`pbpstats`) — 2000/01 to present
  - Shot detail (`shotdetail`) — 1996/97 to present (XY coords, zone, defender, distance)
  - Matchups data (`matchups`)
- **Language**: Python
- **Companion package**: `shufinskiy/nba-on-court` — adds which 10 players are on court to every PBP event
- **Direct use**: YES — download CSVs directly, whole season in seconds
- **Install**: `pip install nba-on-court`
- **Download example**:
  ```python
  from nba_on_court import load_nba_data
  df = load_nba_data(seasons=list(range(2015, 2026)), data_type=['shotdetail'])
  ```
- **Feature value**: Shot-level data with defender info, zone, distance for every shot 1996-2025. Enables shot quality features (QSG), contest rate, zone efficiency by opponent.

#### DomSamangy/NBA_Shots_04_25
- **URL**: https://github.com/DomSamangy/NBA_Shots_04_25
- **Stars**: ~600
- **Last updated**: 2025 (includes 2024-25 season)
- **What it provides**: All NBA regular season shots 2003-04 through 2024-25 in a single CSV plus per-season CSVs. Columns include: PLAYER_NAME, TEAM_NAME, ACTION_TYPE, SHOT_TYPE, SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE, SHOT_DISTANCE, LOC_X, LOC_Y, SHOT_MADE_FLAG, GAME_DATE
- **Direct use**: YES — git clone and load CSV directly
- **Feature value**: 20 seasons of zone-level shooting. Build zone efficiency rolling averages per player, opponent zone defense rates. Pure CSV, no API calls needed.
- **Clone**: `git clone https://github.com/DomSamangy/NBA_Shots_04_25`

#### NBA-Betting/NBA_AI
- **URL**: https://github.com/NBA-Betting/NBA_AI
- **Stars**: ~300
- **Last updated**: 2025 (active)
- **What it provides**:
  - SQLite database (download from GitHub Releases): 3 seasons (2023-24, 2024-25, 2025-26), ~4,100 games
  - Full pipeline: Schedule → Players → Injuries → Betting → PBP → GameStates → Boxscores → Features → Predictions
  - Pre-engineered game-state features from PBP (momentum, scoring runs, etc.)
  - Injury data included in DB
- **Language**: Python, Flask, SQLite, XGBoost, scikit-learn
- **Direct use**: YES — download SQLite from Releases, query directly
- **Download**: https://github.com/NBA-Betting/NBA_AI/releases (look for NBA_AI_BASE.sqlite)
- **Feature value**: Pre-built PBP → GameStates features for 4,100 games. The GameStates feature set is the most valuable steal — reverse-engineer their feature engineering from the code.

### Tier 2 — High Value

#### kyleskom/NBA-Machine-Learning-Sports-Betting
- **URL**: https://github.com/kyleskom/NBA-Machine-Learning-Sports-Betting
- **Stars**: ~1,500
- **Last updated**: 2025 (active)
- **What it provides**:
  - Data pipeline: pulls team stats from NBA endpoints 2007-08 to present
  - Odds scraping from SportsBookReview (SBR) — closing moneyline, spread, total
  - SQLite databases: team stats + odds merged
  - Features: team stats + days_rest + odds merge → matchup dataset
  - Models: XGBoost + Neural Net for moneyline and totals
  - Output: EV + Kelly Criterion sizing
- **What to steal**:
  - `Get_Odds_Data.py` — the SBR scraper pattern for historical odds
  - `Create_Games.py` — team stats + odds merge logic
  - Their feature set: team PPG, opp PPG, pace, TS%, eFG%, days rest, home/away
- **Direct use**: YES for the data pipeline, needs API key for live odds
- **Notes**: Achieves ~67% moneyline accuracy. Good baseline but we already exceed this.

#### cmunch1/nba-prediction
- **URL**: https://github.com/cmunch1/nba-prediction
- **Stars**: ~300
- **Last updated**: 2024 (active)
- **What it provides**:
  - End-to-end ML deployment: scrapes → feature store → daily predictions → Streamlit app
  - Rolling stats + streaks feature engineering
  - Calibration: auto-selects sigmoid/isotonic/none via Brier score minimization
  - GitHub Actions for daily automated scraping
  - XGBoost + LightGBM with CalibratedClassifierCV
- **What to steal**:
  - Their calibration selection logic (auto Brier-minimized) — directly applicable
  - Rolling stats feature pipeline approach
  - GitHub Actions daily automation pattern
- **Notes**: 61.5% accuracy on 2022-23 season. We beat this. Steal the calibration pattern.

#### dblackrun/pbpstats
- **URL**: https://github.com/dblackrun/pbpstats
- **Stars**: ~400
- **Last updated**: 2025 (active, powers pbpstats.com)
- **What it provides**:
  - Python package to parse NBA/WNBA/G-League PBP
  - Adds lineup info (which 10 players on court) to every event
  - Possession-level data: start time, end time, score margin, how possession ended
  - Shots/rebounds/assists broken down by shot zone
  - On/off splits computable from this data
- **Install**: `pip install pbpstats`
- **Feature value**: Lineup-level net rating computations. Best 5-man unit features, opponent lineup quality. This is what 538 and Second Spectrum use at a basic level.

#### josedv82/airball (R) + josedv82/NBA_Schedule_XGBoost_Classifier
- **URL**: https://github.com/josedv82/airball
- **Stars**: ~200
- **Last updated**: 2024
- **What it provides** (R package, but logic is portable to Python):
  - Distance traveled per game
  - Time zone changes (east/west travel direction)
  - Flight duration estimate
  - Number of rest days
  - Games in last 7/14 days (density)
  - Game Index: composite schedule stress score
- **What to steal**: The formula for Game Index (rest days + travel miles + time zone crossings + game density). Convert to Python. Validated with XGBoost on 20 seasons.
- **Direct use**: Logic only — port to Python. The XGBoost classifier repo shows SHAP feature importance — time zone shifts and density are top predictors.

#### atlhawksfanatic/L2M
- **URL**: https://github.com/atlhawksfanatic/L2M
- **Stars**: ~200
- **Last updated**: 2025 (updated through 2025 playoffs)
- **What it provides**: NBA Last Two Minute Report data — official call accuracy data. For every L2M game: referee decisions, correct/incorrect calls, missed calls, shot clock violations, player involved.
- **Feature value**: Referee-specific foul-calling rate, home team bias per referee, missed call rate. Rare data source almost nobody uses in prediction models.
- **Direct use**: YES — CSV files in repo, load directly.

#### blakelaw/Referee-Analysis
- **URL**: https://github.com/blakelaw/Referee-Analysis
- **Stars**: ~50
- **Last updated**: 2023
- **What it provides**: Analysis of ~64,000 NBA games for referee neutrality. Four quantitative approaches to referee impact on game metrics.
- **What to steal**: Their methodology for building referee features (foul rates, home favoritism, pace impact per ref crew).

#### mxufc29/nbainjuries
- **URL**: https://github.com/mxufc29/nbainjuries
- **Stars**: ~100
- **Last updated**: 2025
- **What it provides**: Python package for historical + real-time NBA injury report data. Historical from 2021-22 season. Returns structured injury reports per date in JSON or DataFrame.
- **Install**: `pip install nbainjuries`
- **Feature value**: Missing player impact (star player absent → opponent advantage), injury trend features (days since last game for each player), lineup quality adjustments.
- **Direct use**: YES — pip install and query.

#### chevyphillip/plus-ev-model
- **URL**: https://github.com/chevyphillip/plus-ev-model
- **Stars**: ~50
- **Last updated**: 2024
- **What it provides**: NBA player props prediction with MotherDuck (DuckDB cloud) integration. Modules: NBA API data pipeline, career stats, Monte Carlo simulation for props, odds processing, betting edge analysis.
- **What to steal**: Monte Carlo simulation approach for player props uncertainty quantification. Their career stats normalization logic for props lines.

#### fivethirtyeight/data (nba-elo)
- **URL**: https://github.com/fivethirtyeight/data/tree/master/nba-elo
- **Stars**: ~17,000 (whole repo)
- **What it provides**: `nbaallelo.csv` — every NBA game since 1947 with Elo ratings (team Elo before game, Elo probability, actual result). Also: Neil-Paine-1/NBA-elo is an updated fork post-538 shutdown.
- **Direct download**: `wget https://raw.githubusercontent.com/fivethirtyeight/data/master/nba-elo/nbaallelo.csv`
- **Feature value**: Pre-computed Elo as a baseline feature + 75+ years of game outcomes for feature validation.

#### vishaalagartha/basketball_reference_scraper
- **URL**: https://github.com/vishaalagartha/basketball_reference_scraper
- **Stars**: ~500
- **Last updated**: 2024
- **What it provides**: BPM (Box Plus/Minus), VORP, Win Shares, PER, True Shooting%, usage rate, all standard advanced stats from Basketball Reference. Modules: teams, players, seasons, box_scores, pbp, shot_charts, injury_report.
- **Install**: `pip install basketball-reference-scraper`
- **Feature value**: VORP and BPM are superior to raw box score for player quality estimation. Win Shares for team composition quality. Rate-limited to 20 req/min — build data cache.

---

## 2. Kaggle Datasets

### Best in Class

#### NBA Betting Data 2007-2025
- **URL**: https://www.kaggle.com/datasets/cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024
- **Coverage**: October 2007 to June 2025 (updated)
- **License**: CC0 Public Domain (free to use)
- **What it provides**: Every NBA regular season game with closing moneyline, spread, total, actual score, and result. ~19,820+ games.
- **Download**:
  ```bash
  kaggle datasets download cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024
  ```
- **Feature value**: 18 seasons of betting lines. Build market efficiency features: line movement, juice, closing line value (CLV). Validate our model against historical closing lines.

#### NBA Historical Stats and Betting Data
- **URL**: https://www.kaggle.com/datasets/ehallmar/nba-historical-stats-and-betting-data
- **What it provides**: Combined team stats + betting lines dataset. Moneyline + spread + total + team box score stats per game.
- **Download**: `kaggle datasets download ehallmar/nba-historical-stats-and-betting-data`

#### NBA Database (wyattowalsh) — Master Reference
- **URL**: https://www.kaggle.com/datasets/wyattowalsh/basketball
- **Coverage**: 1947 to present (daily updated SQLite)
- **What it provides**: SQLite with tables: games (64,000+), players (4,800+), teams (30), box scores, draft data. Pulls directly from stats.nba.com via nba_api.
- **GitHub source**: https://github.com/wyattowalsh/nbadb (for custom queries)
- **Download**: `kaggle datasets download wyattowalsh/basketball`
- **Note**: Good for historical game outcomes and box scores. Less useful than shufinskiy for PBP but has longer history.

#### NBA Games Data (nathanlauga)
- **URL**: https://www.kaggle.com/datasets/nathanlauga/nba-games
- **What it provides**: Clean game-level dataset with team stats per game, home/away splits. Good for quick prototyping.
- **Download**: `kaggle datasets download nathanlauga/nba-games`

#### NBA Historical Data 1947-Present (eoinamoore)
- **URL**: https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores
- **What it provides**: Player box scores from 1947 to present. Individual game-level stats per player.
- **Download**: `kaggle datasets download eoinamoore/historical-nba-data-and-player-box-scores`

#### NBA Player Stats 2024-25
- **URL**: https://www.kaggle.com/datasets/eduardopalmieri/nba-player-stats-season-2425
- **What it provides**: Current season player stats snapshot.
- **Download**: `kaggle datasets download eduardopalmieri/nba-player-stats-season-2425`

---

## 3. HuggingFace Datasets

#### dcayton/nba_tracking_data_15_16
- **URL**: https://huggingface.co/datasets/dcayton/nba_tracking_data_15_16
- **What it provides**: NBA player tracking data from the 2015-16 season (last year of SportVU public data). XY coordinates per 0.04 seconds for all players + ball.
- **Note**: Historic only — 2015-16 was the last season with public SportVU data. Second Spectrum (2016+) and Hawk-Eye (2023+) data is proprietary. Good for building tracking-derived feature proxies.

#### suzyanil/nba-data
- **URL**: https://huggingface.co/datasets/suzyanil/nba-data
- **What it provides**: NBA game stats dataset.

#### UniqueData/basketball_tracking and TrainingDataPro/basketball_tracking
- **URLs**: https://huggingface.co/datasets/UniqueData/basketball_tracking, https://huggingface.co/datasets/TrainingDataPro/basketball_tracking
- **What it provides**: Basketball player tracking annotation data (CV/annotation focused, not game stats).

#### megagonlabs/cmdbench-nba
- **URL**: https://huggingface.co/datasets/megagonlabs/cmdbench-nba
- **What it provides**: Multimodal NBA datalake with Neo4j KG + PostgreSQL + MongoDB. Updated through February 2025. More useful for LLM benchmarking than prediction features.

**HF Assessment**: HuggingFace has minimal useful NBA prediction datasets. Kaggle and GitHub are the primary sources. The 2015-16 tracking data is the only HF dataset with direct feature value.

---

## 4. APIs (No API Key Required)

### nba_api (stats.nba.com) — The Gold Standard
The free, unofficial NBA stats API. No key needed. Key endpoints:

```python
from nba_api.stats.endpoints import (
    LeagueHustleStatsPlayer,      # deflections, contested shots, charges, screen assists
    LeagueDashPtStats,            # speed, distance (PtMeasureType='SpeedDistance')
    LeagueDashPlayerShotLocations, # zone FG% (restricted area, paint, mid, corner3, above3)
    LeagueDashTeamStats,          # team stats with splits
    BoxScorePlayerTrackV3,        # per-game tracking data
    ShotChartDetail,              # XY shot locations per player
    LeagueDashPlayerStats,        # standard + advanced player stats
    PlayerGameLog,                # game-by-game log per player
    TeamGameLog,                  # game-by-game log per team
    PlayByPlayV2,                 # play-by-play per game
    ScoreboardV2,                 # today's games + scores
)
```

All return DataFrames. Rate limit: ~600ms between calls. Use `time.sleep(0.6)` between requests.

### pbpstats.com
- Powers the pbpstats Python package
- Free tier: game-level aggregates, lineup stats
- Paid tier: full possession-level, on/off, WOWY
- Install: `pip install pbpstats`

---

## 5. Feature Engineering Opportunities

Based on all sources above, here are new feature categories we can build:

### From Shot Data (DomSamangy + shufinskiy shotdetail)
- Zone efficiency rolling average per player (last 10, 20, 40 games by zone)
- Shot quality score: % of shots from high-efficiency zones vs opponent allowed
- Corner 3 rate differential (team vs opponent allowed)
- Restricted area conversion rate (team offense vs opponent defense)
- Mid-range avoidance rate (proxy for offensive sophistication)

### From Hustle Stats (nba_api LeagueHustleStatsPlayer)
- Deflections per 100 possessions (team hustle proxy)
- Contested shot rate vs opponent
- Screen assist differential (offensive motion quality)
- Loose ball recovery rate differential
- Charges drawn per 100 possessions

### From Tracking/Speed Data (nba_api LeagueDashPtStats)
- AVG_SPEED_OFF differential (team vs opponent)
- Distance traveled per game (fatigue proxy over season)
- Offensive/defensive speed split

### From Schedule/Travel (josedv82/airball logic)
- Miles traveled last 7 days (compute from team city schedule)
- Time zone direction changes (west→east is harder)
- Games in 5 days (density feature)
- Days rest differential (our teams vs opponent)

### From Referee Data (L2M + blakelaw)
- Referee foul rate (fouls per 48 min for assigned crew)
- Referee home team foul rate differential
- Referee pace impact (high-foul vs low-foul crews affect game pace)
- Referee correct call rate (L2M accuracy)

### From Injury Reports (nbainjuries)
- Missing player WAR (sum of win shares of injured players)
- Days since last injury (fatigue/return risk)
- Roster availability score (% of normal rotation available)
- Star player absence flag (top-3 scorer/rebounder missing)

### From PBP/Lineup Data (pbpstats + NBA_AI GameStates)
- Best 5-man lineup net rating (rolling 30-game)
- Depth-adjusted net rating (how does lineup quality drop with bench)
- Close-game performance (net rating when margin within 5)
- 4th quarter net rating differential
- Transition pace rate (fast break opportunities per possession)

---

## 6. Download Instructions

### Prerequisites
```bash
pip install nba_api nba-on-court basketball-reference-scraper nbainjuries pbpstats
pip install kaggle  # requires ~/.kaggle/kaggle.json
```

### Download All Key Datasets
```bash
# Kaggle datasets (run from Kaggle GPU to avoid local RAM limits)
kaggle datasets download cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024 -p /data/odds/
kaggle datasets download wyattowalsh/basketball -p /data/nba-db/
kaggle datasets download nathanlauga/nba-games -p /data/games/
kaggle datasets download eoinamoore/historical-nba-data-and-player-box-scores -p /data/players/

# Git clone shot data
git clone https://github.com/DomSamangy/NBA_Shots_04_25 /data/shots/

# FiveThirtyEight Elo (direct download)
wget -O /data/elo/nbaallelo.csv \
  https://raw.githubusercontent.com/fivethirtyeight/data/master/nba-elo/nbaallelo.csv

# NBA_AI SQLite database (check latest release)
# Go to: https://github.com/NBA-Betting/NBA_AI/releases
# Download NBA_AI_BASE.sqlite or NBA_AI_DEV.sqlite

# L2M referee data
git clone https://github.com/atlhawksfanatic/L2M /data/referee/
```

### Pull Live Data via nba_api
```python
import time
from nba_api.stats.endpoints import LeagueHustleStatsPlayer, LeagueDashPtStats

# Hustle stats for current season
hustle = LeagueHustleStatsPlayer(season='2024-25', per_mode_time='Per100Possessions')
df_hustle = hustle.get_data_frames()[0]
time.sleep(0.6)

# Speed/distance stats
speed = LeagueDashPtStats(
    season='2024-25',
    pt_measure_type='SpeedDistance',
    per_mode_simple='PerGame'
)
df_speed = speed.get_data_frames()[0]
```

---

## 7. Priority Ranking for Integration

| Rank | Source | New Features | Brier Impact Est. | Effort |
|------|--------|-------------|-------------------|--------|
| 1 | nba_api hustle + tracking | 20-30 new features (hustle, speed, zones) | -0.003 to -0.005 | 8h |
| 2 | Kaggle odds 2007-2025 | CLV, market efficiency, line movement | -0.002 to -0.004 | 4h |
| 3 | DomSamangy shot zones | 15 zone efficiency features per team | -0.002 to -0.003 | 6h |
| 4 | Schedule/travel features | 8 fatigue/travel features | -0.001 to -0.003 | 4h |
| 5 | L2M referee data | 4 referee impact features | -0.001 to -0.002 | 3h |
| 6 | nbainjuries package | 5 injury/availability features | -0.001 to -0.002 | 3h |
| 7 | pbpstats lineup data | Lineup net rating features | -0.002 to -0.004 | 12h |
| 8 | FiveThirtyEight Elo | Elo differential features | -0.001 | 1h |

**IMPORTANT**: All feature engineering must happen on Kaggle GPU or Colab, not on the VM (1 vCPU, 969 MB RAM). Use the Karpathy loop pattern: one feature category at a time, measure Brier improvement, keep if better.

---

## 8. What We Already Have vs. What's New

### Already in Our Feature Engine (v3.1, 46 categories)
- Basic team stats, rolling averages
- Elo-like ratings (MOVDA)
- Rest days
- Home/away splits
- EWMA stats

### NEW — Not in Our Engine
- Shot zone efficiency by court area (nba_api + DomSamangy)
- Hustle stats: deflections, contested shots, screen assists (nba_api)
- Player tracking speed/distance (nba_api)
- Lineup-level net rating (pbpstats)
- Travel distance + time zone features (airball logic)
- Referee crew impact features (L2M)
- Injury-adjusted lineup quality (nbainjuries)
- Closing line value / market efficiency features (Kaggle odds)
- PBP-derived momentum features (NBA_AI GameStates)

---

## 9. Tracking Data Reality Check

**Hawk-Eye data (2023+ season)**: Fully proprietary. Not available publicly. Requires NBA team partnership or licensed vendor (Sportradar, Second Spectrum). Cost: six-figure licensing.

**Second Spectrum (2016-2022)**: Proprietary. Was never released publicly.

**SportVU (2013-2016)**: The 2015-16 season data was briefly public and is preserved at `dcayton/nba_tracking_data_15_16` on HuggingFace. Too old to be directly useful for current models, but can validate tracking-derived proxy features.

**Best proxy**: Use nba_api `LeagueDashPtStats` (SpeedDistance) which provides aggregated tracking derivatives (speed, distance) from Hawk-Eye data. These are actual tracking outputs, freely available via the stats.nba.com API.

---

## 10. Specific Repos to Check (from original request)

| Repo | Status | Assessment |
|------|--------|-----------|
| swar/nba_api | ACTIVE, ~8k stars | Essential — our primary data source |
| jaebradley/basketball_reference_web_scraper | Active, v4.15.3 | Good for BPM/VORP/Win Shares |
| chevyphillip/plus-ev-model | Active | Monte Carlo props logic worth stealing |
| NBA-Betting/NBA_AI | Active, ~300 stars | SQLite DB download + GameStates features |
| NBA-Betting/NBA_Betting | Hiatus | Old project, use NBA_AI instead |
| kyleskom/NBA-Machine-Learning-Sports-Betting | Active, ~1.5k stars | SBR odds scraper + Kelly sizing |
| vishaalagartha/basketball_reference_scraper | Active | Advanced stats: BPM, VORP, WS |
| dblackrun/pbpstats | Active | Lineup on/off data |
| DomSamangy/NBA_Shots_04_25 | Active, ~600 stars | Best shot location dataset |
| shufinskiy/nba_data | Active, ~400 stars | Best PBP + shot detail CSVs |

Sources verified: 2026-03-28
