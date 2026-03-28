# Research Proposal: Schedule-Aware Fatigue & Rest-Day Features

**Date:** 2026-03-28  
**Priority:** HIGH  
**Target:** Brier improvement 0.22006 → <0.219 (Δ~0.001)  
**Source:** WebSearch findings — SHAP analysis from 2025 NBA ML research  

---

## Motivation

Recent 2025 research (MDPI, ACM CISAT 2025) identified via SHAP that **`home_next`** (whether the team's *next* game is home or away) is consistently the **#1 most influential feature** across all NBA prediction models — outranking ELO, efficiency ratings, and box-score stats. This is not yet explicitly in our Cat42/Cat45 feature set.

Current engine has travel-related proxies but NOT:
- Explicit look-ahead: is this team's next game home/away?
- Distance of next road trip (miles to next away city)
- Rest days before THIS game (back-to-back vs 3+ days rest)
- Cumulative fatigue: games in last 7 days for both teams

---

## Proposed Features (add to engine.py Cat46 — Schedule Context)

```python
# Cat46: Schedule Context & Fatigue (NEW — 45 features)

# 1. Rest day asymmetry (6 features)
'home_rest_days',           # days since home team last game
'away_rest_days',           # days since away team last game  
'rest_advantage',           # home_rest - away_rest
'home_b2b',                 # 1 if home team on back-to-back
'away_b2b',                 # 1 if away team on back-to-back
'b2b_asymmetry',            # home_b2b - away_b2b

# 2. Next-game context (4 features) — TOP SHAP FEATURE
'home_next_is_home',        # 1 if home team's next game is home
'away_next_is_home',        # 1 if away team's next game is home  
'home_road_trip_length',    # consecutive road games home team is on
'away_road_trip_length',    # consecutive road games away team is on

# 3. Recent load (8 features)
'home_games_last_7d',       # games played in last 7 days (home)
'away_games_last_7d',       # games played in last 7 days (away)
'home_games_last_14d',
'away_games_last_14d',
'home_minutes_last_7d',     # total team minutes last 7 days
'away_minutes_last_7d',
'home_load_vs_avg',         # vs season avg games/week
'away_load_vs_avg',

# 4. Travel distance (5 features)
'travel_distance_home',     # miles traveled since last game (home)
'travel_distance_away',
'time_zone_crosses_home',   # time zone changes crossed
'time_zone_crosses_away',
'travel_asymmetry',         # away_travel - home_travel

# 5. Seasonal fatigue (7 features)
'game_number_in_season',    # game 1 vs game 82
'games_remaining',
'home_season_pct',          # % of season completed
'playoff_race_intensity',   # closeness of playoff race (top 8 diff)
'home_eliminated',          # team mathematically eliminated
'away_eliminated',
'tanking_signal',           # 1 if both teams losing to draft position

# 6. Interaction features (15 features)
'rest_adv_x_home_court',    # rest_advantage * home_court interaction
'b2b_x_road_trip',
'fatigue_x_opponent_pace',  # fatigued team vs high-pace opponent
'rest_adv_x_elo_diff',
'b2b_x_starter_minutes_7d', # back-to-back when starters played heavy
'b2b_road_x_elo_favorite',  # b2b road game when team is ELO fav
'load_x_age',               # older team load is more impactful
'rest_adv_x_net_rating',
'home_b2b_x_opp_rest',
'away_b2b_x_opp_rest',
'b2b_x_win_pct_last10',
'fatigue_x_pace_last5',
'rest_days_x_travel',
'b2b_x_travel',
'rest_advantage_squared',
```

---

## Implementation Plan

### Step 1: Schedule data source
NBA schedule data already available via `nba_api.stats.endpoints.leaguegamelog`. Extract:
- Game dates → compute rest days for each team
- Home/away flags → road trip length
- City names → travel distance via haversine formula

### Step 2: Add Cat46 to `features/engine.py`
- Insert after Cat45 (Player Tracking)
- New category ID: `cat46_schedule_fatigue`
- Target: 45 features → brings raw total to ~6,256
- No impact on MAX_FEATURES=200 cap

### Step 3: Validate on S14 (fleet best)
- S14 is Extra Trees + 59 features, Brier 0.22006
- Push engine.py update → features auto-regenerate on space restart
- Expected: ~0.001 Brier improvement based on SHAP importance magnitude

---

## Expected Impact

| Metric | Current | Expected |
|--------|---------|----------|
| Brier | 0.22006 | ~0.219 |
| ROI | 32.55% | hold |
| Sharpe | 8.43 | hold |

Basis: SHAP magnitude for `home_next` ≈ 0.15 normalized importance. If captured cleanly, models like Extra Trees should use it in top-5 selected features.

---

## Cross-Project Note

The Political Alpha engine already has a `TEMPORAL_DECAY` concept in Cat8 (Interactions & Temporal). The schedule fatigue approach is the NBA equivalent — **temporal context over the season arc**. Consider porting seasonal fatigue signals back to political (executive order fatigue, legislative calendar context).

---

## Risk
- LOW: pure feature addition, no architecture change
- Max downside: features ignored by GA (cost: ~5min rebuild time)
- Max upside: breaks 0.21837 checkpoint threshold

**Recommended action:** Implement Cat46 in next engine.py update.
