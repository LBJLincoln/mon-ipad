---
name: YouTube Feature Research Cycle 7
description: Feature ideas extracted from NBA analytics YouTube and recent research (March 2026)
type: project
---

# YouTube-Sourced Feature Research — Cycle 7 (2026-03-28)

## Summary
Extracted 18 new feature categories from NBA analytics YouTube channels, academic research, and recent published work on basketball prediction. Focus on ACTIONABLE features not yet in v3.0-43cat engine.

## Current Engine Status
- **v3.0-43cat**: 6,211 raw features, 43 categories
- **Deployed to all 6 HF islands** (2026-03-28)
- **ATR Brier**: 0.21570 (Colab TabICL, 110f)
- **Gap to SOTA**: 0.0157 (published best = 0.199)

---

## NEW FEATURE CATEGORIES (47-64)

### **CAT 47: Advanced Clutch Dynamics** (10 features)
**Source:** MDPI 2025, NBER Clutch Studies
**Relevance:** HIGH — Clutch has demonstrated predictive power
**Effort:** 2h
**Expected Delta:** -0.0008 to -0.0012

- `clutch_ecc_home` / `clutch_ecc_away`: Estimation of Clutch Competency (scoring + defense + ORB - TOV)
- `clutch_3p_decline_pct`: 3-point accuracy drop in clutch vs regular (pressure effect)
- `clutch_ft_reliability`: FT% in last 5 min vs season avg
- `clutch_late_game_netrtg`: Net rating in games within 5 pts, last 5 min
- `clutch_margin_conversion_rate`: Win % when trailing by 5+ after Q3
- `clutch_holding_pct`: % of 10+ pt leads held to end
- `clutch_mo_swing`: Momentum indicator: Q4 scoring vs Q1 (coaching adjustments)
- `clutch_decision_quality`: Usage rate × TS% in clutch (shot selection)
- `fourth_quarter_pace`: Possession-weighted pace in Q4 (stalling indicator)

**Data Source:** nba_api historical logs, box scores w/ time stamps
**Implementation:** Filter games by margin, compute rolling stats per team in clutch windows

---

### **CAT 48: Referee Crew Bias & Foul Patterns** (12 features)
**Source:** 2025 Belasen et al., Sabag et al. 2026, NBER classics
**Relevance:** HIGH — Recent 2026 study confirms home favoritism persistent
**Effort:** 3h (requires ref crew mapping)
**Expected Delta:** -0.0006 to -0.0010

- `ref_crew_home_foul_delta`: Avg (home fouls - away fouls) for this crew
- `ref_crew_ft_advantage_home`: Avg FTA differential (home - away)
- `ref_crew_total_fouls_avg`: Total fouls per game (tight vs loose)
- `ref_crew_foul_rate_vs_league`: Z-score vs league avg (this crew)
- `ref_crew_over_under_rate`: % games going over/under for crew
- `ref_crew_home_win_pct`: Historical home team win % w/ this crew
- `ref_crew_technical_rate`: Tech fouls per game (player discipline)
- `ref_crew_consistency`: Std dev of foul calls (variable vs consistent)
- `ref_crew_playoff_bias`: Playoff games: extra home favoritism?
- `ref_crew_3pt_call_rate`: 3-pt fouls per 3p attempt (shooting fouls)
- `ref_crew_bench_foul_rate`: Bench players get more calls?
- `ref_home_close_game_bias`: Home win % when decided by ≤3 pts

**Data Source:** NBA.com L2M reports (scraped), official ref crew assignments
**Implementation:** Pre-compute crew stats in feature build; join on game + crew IDs

---

### **CAT 49: Game Script & Game Flow Dynamics** (8 features)
**Source:** PLOS One 2025, arXiv game theory papers
**Relevance:** MEDIUM-HIGH — Game flow affects pace, shot selection
**Effort:** 2h
**Expected Delta:** -0.0005 to -0.0008

- `halftime_margin_predictor`: H1 margin (stronger predictor than some people think)
- `garbage_time_indicator`: 1 if final margin > 15 (affects Q4 stats inflation)
- `game_flow_phase_1`: Offensive dominance phase (0-8 min, avg lead/deficit)
- `game_flow_phase_2`: Mid-game momentum swing (8-16 min)
- `game_flow_phase_3`: Adjustment window (16-24 min, typical halftime adjustments)
- `momentum_streak_score`: Consecutive scoring runs (3+ possessions)
- `lead_trading_frequency`: # times lead changed hands (volatile game)
- `expected_final_margin_at_half`: Simple: h_margin_h1 + (trend_h1 - trend_season)

**Data Source:** Play-by-play logs, timestamps
**Implementation:** Window-based aggregation on 8-min segments; rolling average lead

---

### **CAT 50: Market Microstructure & Sharp Money Signals** (14 features)
**Source:** Sports AI 2026, Covers consensus, SBR closing lines
**Relevance:** HIGH — Market data is complementary signal
**Effort:** 2h (API integration w/ BetMGM, DraftKings)
**Expected Delta:** -0.0010 to -0.0015

- `opening_spread_vs_consensus`: Opening line vs pregame consensus model
- `sharp_move_indicator`: 1 if line moved >1.5 pts away from steam direction
- `late_money_direction_flag`: -1 (away money), 0 (balanced), +1 (home money)
- `steam_move_velocity`: Speed of line movement (pts/hour)
- `reverse_line_movement`: 1 if line moved opposite to public bet %
- `public_money_pct_home`: % of money on home side (vs bet % divergence)
- `best_available_spread`: Min spread across books (best price)
- `vig_overround`: Total implied prob > 1.0 (line is out of whack)
- `closing_line_consensus`: Average closing lines across books
- `polymarket_vs_books`: Polymarket prob - best book prob (divergence)
- `prediction_market_vol_24h`: Trading volume on Kalshi/Polymarket (confidence)
- `clv_recent_rolling`: CLV% of our last 10 bets (are we getting value?)
- `books_disagreement_pct`: (Max implied prob - min implied prob) / avg (consensus)
- `steam_direction_consistency`: Previous 5 games: did steam direction work?

**Data Source:** SBR (closing lines archive), BetMGM/DraftKings APIs, Polymarket API
**Implementation:** Pre-fetch pregame + halftime lines; compute deltas vs opening

---

### **CAT 51: Lineup Continuity & Rotation Depth** (10 features)
**Source:** MIT Sloan Lineup Analysis, NBA.com lineups, Rotowire
**Relevance:** MEDIUM-HIGH — Lineup quality matters
**Effort:** 2h (requires lineup-level data)
**Expected Delta:** -0.0004 to -0.0008

- `starting_lineup_continuity_pct`: % same starters as last game
- `bench_net_rating_10g`: Net rating of bench unit (last 10 games)
- `lineup_minutes_balance`: How evenly distributed are minutes (Gini coeff)
- `key_player_minutes_load`: Top 2 players' avg minutes (last 5 games)
- `rotation_size_depth`: # of players w/ 10+ min played (broader rotation)
- `lineup_efficiency_best5`: Net rating of best-performing 5-man combo (season)
- `unused_lineup_sample_size`: # of possible combos played <10 times (experimentation)
- `sixth_man_scoring_rate`: Bench scoring % (vs starting 5)
- `closing_unit_reliability`: How often best-scoring lineup is deployed in Q4
- `position_redundancy_score`: # of players who can play same position (flexibility)

**Data Source:** NBA.com lineups (requires scrape or stats.nba.com API)
**Implementation:** Pre-compute lineup stats from historical game logs; aggregate by team

---

### **CAT 52: Player Tracking & Hustle Metrics** (12 features)
**Source:** NBA.com Hustle Stats (2025 official), player tracking APIs
**Relevance:** MEDIUM — Hustle is real but noisy
**Effort:** 3h (multiple nba_api endpoints)
**Expected Delta:** -0.0003 to -0.0007

- `contested_shots_pct`: % of opponent shots contested (last 10)
- `contested_shots_allowed_3p`: 3-point shots contested %
- `deflections_per_100`: Deflections per 100 possessions (steals predecessor)
- `loose_ball_fouls_rate`: Fouls on loose ball plays
- `screen_assists_home` / `screen_assists_away`: Screen-setting effort
- `charges_drawn_per_100`: Charges taken (defensive commitment)
- `help_defense_frequency`: # of times helped on drives (risk metric)
- `transition_defense_stops`: Stops in transition (last 10)
- `paint_defense_intensity`: Field goal % allowed in paint (20 ft or less)
- `recovery_time_avg`: How quickly players recover after fouls
- `speed_distance_per_game`: Total distance covered (fitness indicator)
- `drives_per_game`: Offensive drives (pace control, aggression)

**Data Source:** nba_api hustle stats, player tracking (if available)
**Implementation:** Fetch from nba_api.stats.endpoints.leaguehustlestatsplayer

---

### **CAT 53: Rest, Fatigue & Travel Load (Nonlinear)** (10 features)
**Source:** Montrucchio 2026 (SOTA at 0.199), travel research
**Relevance:** HIGH — Rest effects are well-established
**Effort:** 2h
**Expected Delta:** -0.0005 to -0.0010

- `rest_days_squared`: Rest days ^ 2 (nonlinear diminishing returns)
- `cumulative_fatigue_index`: Exponential decay over 7 days (more recent games worse)
- `b2b_streak_consecutive`: Consecutive back-to-backs played (compounding fatigue)
- `travel_distance_rolling_14d`: Total miles traveled (last 14 days)
- `altitude_adjustment_factor`: DEN/UTA advantage decay per game at altitude
- `timezone_drift_score`: Cumulative effect of tz changes (jet lag)
- `schedule_density_percentile`: Where is team in schedule (dense vs sparse)
- `days_since_last_heavy_game`: Days since opponent played heavy (travel-heavy)
- `fatigue_inflated_margin`: Margin adjusted for fatigue delta (what margin should it be?)
- `rest_advantage_decay_ln`: ln(rest_diff + 1) — nonlinear rest edge

**Data Source:** NBA schedule, arena coords, dates
**Implementation:** Use exponential decay: fatigue = sum(e^(-k*days_ago)) for last 10 games

---

### **CAT 54: Offensive Efficiency Splits (Shot Location & Distribution)** (8 features)
**Source:** Montrucchio 2026, shot quality research
**Relevance:** HIGH — Shot location is predictive
**Effort:** 2h (requires shot-level data or pbpstats)
**Expected Delta:** -0.0006 to -0.0010

- `rim_freq_pct`: % of FGA at rim (0-3 ft) — pace indicator
- `rim_efg_rate`: Effective FG% at rim
- `mid_range_freq_pct`: % of FGA in mid-range (3-23 ft)
- `mid_range_efg_rate`: Mid-range efficiency
- `three_point_freq_pct`: % of FGA from 3pt
- `three_point_efg_rate`: 3pt efficiency
- `expected_fg_pct`: xEFG — expected FG% based on shot chart (shot quality)
- `shot_quality_delta`: Actual eFG% - Expected FG% (over/underperformance)

**Data Source:** pbpstats.com (shot data), nba_api (can extract zones)
**Implementation:** Group shots by distance/angle; compute freq & eFG% per zone

---

### **CAT 55: Head-to-Head & Historical Matchup Dynamics** (8 features)
**Source:** Thinking Basketball (Ben Taylor's empirical work), Sloan papers
**Relevance:** MEDIUM — H2H can be noisy but some signals
**Effort:** 1h
**Expected Delta:** -0.0002 to -0.0005

- `h2h_wp_3yr`: Win % in all meetings (last 3 years)
- `h2h_home_wp`: H2H home team win % (home court effect in matchup)
- `h2h_avg_margin`: Average margin (home perspective)
- `h2h_last5_wp`: Last 5 meetings (recent form)
- `h2h_spread_cover_home`: Home team ATS % in H2H
- `h2h_ou_history`: Over/under record in matchup
- `matchup_style_clash`: ORtg vs DRtg gap (pace/defense mismatch)
- `historical_recency_weight`: Exponential decay: older games weighted less

**Data Source:** Historical game logs (3-5 years)
**Implementation:** Filter for H2H games; compute metrics over rolling windows

---

### **CAT 56: Season Phase & Context Features (Nonlinear)** (8 features)
**Source:** ESPN BPI (pace, SOS, preseason), contextual modeling
**Relevance:** MEDIUM-HIGH — Season progression matters
**Effort:** 1h
**Expected Delta:** -0.0004 to -0.0006

- `season_phase_sqrt`: sqrt(games_played / 82) — nonlinear phase
- `playoff_implication_score`: Playoff seeding impact (playoff hunt vs eliminated)
- `playoff_team_indicator`: Both teams in playoff hunt (1) vs not (0)
- `tanking_flag`: Team mathematically eliminated from playoffs
- `revenge_game_flag`: Team lost to opponent in last 3 meetings
- `back_from_road_trip`: Home after 3+ consecutive road games
- `preseason_expectation_delta`: Current win% - preseason projection (surprise)
- `games_until_trade_deadline`: Urgency factor (deadline approaching)

**Data Source:** NBA schedule, standings, preseason projections
**Implementation:** Simple date/game-count calculations; lookup from standings

---

### **CAT 57: Player Health & Injury Impact (Weighted)** (10 features)
**Source:** NBA injury reports, FiveThirtyEight RAPTOR injury adjustments
**Relevance:** HIGH — Injuries are massive signal
**Effort:** 3h (requires reliable injury data source)
**Expected Delta:** -0.0008 to -0.0012

- `injured_war_home`: Win Above Replacement lost (weighted by severity)
- `injured_star_count`: # of All-Star caliber players out
- `bench_depth_strength`: How strong is backup unit for injured player
- `days_since_return`: Days since key player returned from injury (rust factor)
- `injury_list_duration`: How long was player out (longer = more rust)
- `injury_replacement_caliber`: Quality of fill-in (veteran vs rookie)
- `multiple_injury_interaction`: Compounding effect of multiple injuries
- `key_position_affected`: 1 if PG/C out, 0.5 if SF, 0.3 if PF (position importance)
- `preseason_lineup_available`: % of projected starting lineup available
- `injury_recovery_trajectory`: Is team getting healthier? (last 7 games)

**Data Source:** NBA.com injury report, ESPN injury tracker, basketball-reference
**Implementation:** Scrape injury list daily; join on game date; compute deltas

---

### **CAT 58: Tempo Adjustment & Pace Dynamics** (8 features)
**Source:** PLOS One 2025 pace study, ESPN BPI
**Relevance:** MEDIUM — Pace is second-order effect
**Effort:** 2h
**Expected Delta:** -0.0003 to -0.0006

- `pace_home_last_5`: Pace last 5 games (team adjustment)
- `pace_away_last_5`: Visitor pace tendency
- `pace_delta_absolute`: |home pace - away pace| (style clash)
- `pace_trend`: Pace trend (accelerating or decelerating)
- `transition_rate`: Fast break % (pace indicator, 2nd-string factor)
- `half_court_offense_rate`: Complement of transition %
- `defensive_pace_imposed`: Pace forced on opponent (slowing D)
- `possession_length_variance`: Std dev of possession times (unpredictable tempo?)

**Data Source:** nba_api box scores (PACE stat), play-by-play timing
**Implementation:** Use PACE rating; compute rolling averages & deltas

---

### **CAT 59: Defensive Efficiency by Position & Situation** (10 features)
**Source:** Cleaning the Glass (Ben Falk), defensive analytics
**Relevance:** MEDIUM — Defense is harder to model than offense
**Effort:** 2.5h
**Expected Delta:** -0.0002 to -0.0005

- `perimeter_defense_3p_allowed`: Opponent 3p% allowed (SG/SF defense)
- `paint_defense_rating`: Points in paint allowed per game
- `transition_defense_ppg`: Points allowed in fast break (last 10)
- `drive_defense_rate`: FG% allowed on drives (penetration D)
- `post_defense_efficiency`: Points allowed in post (C defense)
- `wing_isolation_defense`: Points allowed in ISO (wing D)
- `corner_3pt_defense`: Corner 3pt% allowed (spot-up D)
- `bench_defense_rating`: Bench unit defensive rating
- `defense_consistency`: Std dev of DRTG (variable vs stable)
- `defensive_plus_minus`: Defensive net rating (advanced)

**Data Source:** nba_api, Cleaning the Glass API (if available)
**Implementation:** Use opp_3p%, paint PTS allowed from box scores; advanced from stats

---

### **CAT 60: Bench & Role Player Production** (8 features)
**Source:** NBA roster analysis, fantasy basketball
**Relevance:** MEDIUM — Bench depth affects reserves' role expansion
**Effort:** 1.5h
**Expected Delta:** -0.0002 to -0.0004

- `bench_scoring_avg`: Bench scoring per game
- `bench_net_rating`: Bench unit net rating (defensive efficiency)
- `bench_consistency`: Std dev of bench scoring
- `role_player_usage`: Usage rate of 4th/5th best players
- `backup_pg_reliability`: Backup PG scoring/assists consistency
- `bench_scoring_trend`: Bench PPG trend (improving or declining)
- `starter_overlap_vs_bench`: Usage rate delta (are starters being rested?)
- `trash_time_minutes_pct`: % of game in blowout (bench gets inflated stats)

**Data Source:** nba_api box scores, team rosters
**Implementation:** Filter for bench players (minutes 15-25); aggregate

---

### **CAT 61: Vegas Model Consensus & Line Efficiency** (6 features)
**Source:** Vegas consensus, DRatings, sports-reference
**Relevance:** MEDIUM-HIGH — Markets are smart
**Effort:** 1h
**Expected Delta:** -0.0003 to -0.0006

- `implied_prob_consensus`: Average implied probability (all books)
- `line_movement_consensus`: Avg line movement magnitude
- `sharp_vs_public_spread`: % money diff vs % bets diff (smart money signal)
- `closing_line_value_vs_model`: Our model prob vs closing line (edge magnitude)
- `historical_accuracy_this_book`: This sportsbook's accuracy % on moneyline
- `vegas_power_rating_diff`: Vegas power rating delta (indirect from lines)

**Data Source:** SBR, Vegas consensus sites, closing lines
**Implementation:** Pre-fetch Vegas lines; compute implied probs; store centrally

---

### **CAT 62: Player Fatigue & Usage Overload** (8 features)
**Source:** Player load management studies, workload tracking
**Relevance:** MEDIUM — Usage creep affects performance
**Effort:** 2h
**Expected Delta:** -0.0003 to -0.0005

- `star_usage_combined`: Top 2 players' combined usage rate
- `star_minutes_load`: Avg minutes of top 2 players
- `usage_spike_recent`: Usage rate spike vs season avg (workload)
- `fouls_accumulated_player`: Star players' foul trouble (impacts performance)
- `carry_load_indicator`: 1 if team has dominant player carrying (efficiency drop?)
- `deep_bench_usage_forced`: 1 if bench players forced into heavy role
- `playing_time_balance`: Gini coefficient of minutes distribution
- `star_injury_worry_indicator`: Did star practice? (missing shoot-arounds)

**Data Source:** nba_api player stats, practice reports
**Implementation:** Compute usage rates; track per-player minutes; aggregate by team

---

### **CAT 63: Game Importance Score & Situational Context** (6 features)
**Source:** FiveThirtyEight methodology, playoff implications
**Relevance:** MEDIUM — Motivation matters
**Effort:** 1h
**Expected Delta:** -0.0002 to -0.0003

- `playoff_implications_score`: Playoff seeding impact (WP change from win)
- `conference_game_flag`: In-conference (tougher) vs out
- `division_game_flag`: Divisional games (rivalry effect)
- `national_tv_flag`: ESPN/TNT (higher motivation)
- `revenge_factor`: Opponent beat us recently (added motivation)
- `motivation_composite`: Weighted combination of above

**Data Source:** NBA schedule, standings
**Implementation:** Simple lookup from schedule; calculate WP swing

---

### **CAT 64: Tempo-Adjusted Efficiency & Pace Ratios** (6 features)
**Source:** Dean Oliver four factors, KenPom (college)
**Relevance:** MEDIUM — Pace-free analysis
**Effort:** 1h
**Expected Delta:** -0.0001 to -0.0003

- `tempo_free_ortg`: Offensive rating (100 poss pace-adjusted)
- `tempo_free_drtg`: Defensive rating (pace-adjusted)
- `per_100_ortg_delta`: ORTG adjusted for pace (vs season)
- `efficiency_per_possession`: Points per possession (raw efficiency)
- `ppp_vs_pace_ratio`: Offensive efficiency vs pace trade-off
- `pace_adjusted_netrtg`: Net rating adjusted for pace environment

**Data Source:** nba_api ORTG, DRTG, PACE
**Implementation:** Use PACE stat; divide ORTG/DRTG by (PACE/100)

---

## Implementation Priority Matrix

| Category | Effort | Expected Delta | Priority | Ease |
|----------|--------|-----------------|----------|------|
| CAT 47 (Clutch) | 2h | -0.0010 | **HIGH** | Easy |
| CAT 48 (Refs) | 3h | -0.0008 | **HIGH** | Medium |
| CAT 49 (Game Flow) | 2h | -0.0007 | HIGH | Easy |
| CAT 50 (Market Micro) | 2h | -0.0012 | **HIGHEST** | Medium |
| CAT 51 (Lineups) | 2h | -0.0006 | MEDIUM | Medium |
| CAT 52 (Hustle) | 3h | -0.0005 | MEDIUM | Hard |
| CAT 53 (Rest Nonlin) | 2h | -0.0008 | **HIGH** | Easy |
| CAT 54 (Shot Zones) | 2h | -0.0008 | **HIGH** | Hard |
| CAT 55 (H2H) | 1h | -0.0004 | MEDIUM | Easy |
| CAT 56 (Season Phase) | 1h | -0.0005 | MEDIUM | Easy |
| CAT 57 (Injuries) | 3h | -0.0010 | **HIGH** | Medium |
| CAT 58 (Tempo) | 2h | -0.0005 | MEDIUM | Easy |
| CAT 59 (Def Splits) | 2.5h | -0.0004 | LOW | Hard |
| CAT 60 (Bench) | 1.5h | -0.0003 | LOW | Easy |
| CAT 61 (Vegas) | 1h | -0.0005 | MEDIUM | Easy |
| CAT 62 (Player Fatigue) | 2h | -0.0004 | LOW | Medium |
| CAT 63 (Importance) | 1h | -0.0003 | LOW | Easy |
| CAT 64 (Tempo-Free) | 1h | -0.0002 | LOW | Easy |

---

## Quick-Win Implementation Plan (4 Hours)

1. **CAT 49 (Game Flow)** — 2h | -0.0007 Brier
   - Halftime margin, garbage time flag, game phase segments
   - Easy: just filter box scores by quarter/time

2. **CAT 53 (Rest Nonlinear)** — 1h | -0.0008 Brier
   - Add rest_squared, cumulative fatigue exponential decay
   - Easy: existing rest data, just add nonlinear transforms

3. **CAT 61 (Vegas Consensus)** — 1h | -0.0005 Brier
   - Implied prob consensus, line movement magnitude
   - Easy: use existing BetMGM/DK APIs

**Expected Combined Delta: -0.0020 Brier** (0.21570 → 0.21370 if gains stack)

---

## YouTube Channel Breakdown

### Thinking Basketball (Ben Taylor)
- Focus: Shot quality, lineup analysis, advanced metrics
- Key Insight: Shot location & xEFG models predictive
- Feature Gap: CAT 54 (shot zones)

### Cleaning the Glass (Ben Falk)
- Focus: Garbage time filters, situational defense
- Key Insight: Bench depth & rotation matter
- Feature Gap: CAT 51 (lineups), CAT 60 (bench)

### The Athletic / Seth Partnow
- Focus: Player impact, injury adjustments
- Key Insight: Injuries are massive predictor
- Feature Gap: CAT 57 (injury impact)

### Nylon Calculus / FiveThirtyEight Alumni
- Focus: RAPTOR methodology, Bayesian priors
- Key Insight: Player tracking + box score blend
- Feature Gap: CAT 52 (hustles), CAT 58 (tempo)

### BBall Index / Advanced Analytics
- Focus: Game flow, clutch dynamics, game script
- Key Insight: Game flow affects pace & shot selection
- Feature Gap: CAT 49 (game flow)

### SBR / Vegas Sources
- Focus: Sharp money detection, line movement
- Key Insight: Market moves ahead of public opinion
- Feature Gap: CAT 50 (market micro)

---

## Data Source Checklist

| Source | Coverage | API Available | Status |
|--------|----------|---------------|--------|
| nba_api | Box, play-by-play, lineups | YES | WORKING |
| NBA.com L2M reports | Ref crew, fouls | WEB SCRAPE | Ready |
| Basketball-Reference | Historical records | NO | CSV export |
| pbpstats.com | Shot data, zones | API | Requires key |
| BetMGM / DraftKings | Opening/closing lines | YES | Configured |
| Polymarket / Kalshi | Prediction markets | API | Available |
| Hoopshype | Trade deadline info | Web scrape | Ready |
| NBA.com Hustle | Player tracking | YES | nba_api endpoint |

---

## Notes

- **YouTube transcripts**: Enhanced miner script ready (see youtube_transcript_miner_v2.py)
- **Montrucchio 2026**: SOTA at 0.199 (11 features focus: xEFG, nonlinear rest, game flow)
- **Calibration**: Brier is focus; all new features should improve calibration over raw accuracy
- **Market inefficiency**: Vegas lines are already smart; market micro features likely <0.001 delta
- **Expected combined gain**: 18 new categories × avg -0.0006 = -0.0108 theoretical max (overly optimistic)
- **Realistic gain estimate**: -0.004 to -0.008 Brier (accounting for redundancy, noisy features, overfitting)

---

## Next Steps

1. **Implement CAT 49, 53, 61** (quick wins)
2. **Scrape NBA.com L2M reports** (CAT 48 data)
3. **Fetch shot-level data** from pbpstats (CAT 54)
4. **Deploy to S10/S11** for testing
5. **Backtest walk-forward** on 2025-26 season
6. **Monitor Brier on validation set**
7. **Iterate if <-0.003 gain**: cull low-performers

