# NBA Quant Model — 500+ Feature Candidates
# For Genetic Algorithm Feature Selection
# Compiled: 2026-03-16

> **Current state**: 75 features (58 base + 17 advanced)
> **Target**: 500+ candidates, narrowed via GA to optimal ~80-120 subset
> **Data sources**: nba_api (253 endpoints), OddsHarvester, DARKO, Basketball-Reference

---

## CATEGORY 1: TEAM ROLLING STATS (Windows: L3, L5, L10, L15, L20, L30, Season)

Each stat computed over 7 windows = 7 features per base stat.

### 1A. Win/Loss Metrics (7 windows x 7 stats = 49 features)
| # | Feature | Description |
|---|---------|-------------|
| 1-7 | `win_pct_L{3,5,10,15,20,30,season}` | Rolling win percentage |
| 8-14 | `home_win_pct_L{3,5,10,15,20,30,season}` | Home win percentage |
| 15-21 | `away_win_pct_L{3,5,10,15,20,30,season}` | Away win percentage |
| 22-28 | `ats_cover_pct_L{3,5,10,15,20,30,season}` | Against-the-spread cover rate |
| 29-35 | `over_pct_L{3,5,10,15,20,30,season}` | Over/under hit rate |
| 36-42 | `margin_avg_L{3,5,10,15,20,30,season}` | Average point differential |
| 43-49 | `close_game_win_pct_L{3,5,10,15,20,30,season}` | Win% in games decided by <=5 pts |

### 1B. Scoring Metrics (7 windows x 8 stats = 56 features)
| # | Feature | Description |
|---|---------|-------------|
| 50-56 | `pts_avg_L{...}` | Points scored per game |
| 57-63 | `pts_allowed_avg_L{...}` | Points allowed per game |
| 64-70 | `pts_diff_avg_L{...}` | Point differential |
| 71-77 | `pts_1q_avg_L{...}` | First quarter scoring average |
| 78-84 | `pts_2q_avg_L{...}` | Second quarter scoring average |
| 85-91 | `pts_3q_avg_L{...}` | Third quarter scoring average |
| 92-98 | `pts_4q_avg_L{...}` | Fourth quarter scoring average |
| 99-105 | `pts_variance_L{...}` | Scoring variance (consistency measure) |

**Subtotal Category 1: 105 features**

---

## CATEGORY 2: FOUR FACTORS (Dean Oliver Framework)

Offense + Defense x 7 windows = 14 features per factor.

### 2A. Effective Field Goal % (14 features)
| # | Feature | Description |
|---|---------|-------------|
| 106-112 | `efg_pct_off_L{...}` | Offensive eFG% = (FG + 0.5*3P) / FGA |
| 113-119 | `efg_pct_def_L{...}` | Opponent eFG% allowed |

### 2B. Turnover Rate (14 features)
| # | Feature | Description |
|---|---------|-------------|
| 120-126 | `tov_rate_off_L{...}` | Offensive TOV% = TOV / (FGA + 0.44*FTA + TOV) |
| 127-133 | `tov_rate_def_L{...}` | Forced turnover rate |

### 2C. Offensive Rebound Rate (14 features)
| # | Feature | Description |
|---|---------|-------------|
| 134-140 | `oreb_pct_off_L{...}` | Offensive rebound % = OREB / (OREB + Opp_DREB) |
| 141-147 | `oreb_pct_def_L{...}` | Opponent offensive rebound % allowed |

### 2D. Free Throw Rate (14 features)
| # | Feature | Description |
|---|---------|-------------|
| 148-154 | `ft_rate_off_L{...}` | FT Rate = FTA / FGA |
| 155-161 | `ft_rate_def_L{...}` | Opponent FT Rate allowed |

### 2E. Four Factors Composite (7 features)
| # | Feature | Description |
|---|---------|-------------|
| 162-168 | `four_factors_composite_L{...}` | Weighted: 0.40*eFG + 0.25*TOV + 0.20*OREB + 0.15*FT |

**Subtotal Category 2: 63 features**

---

## CATEGORY 3: PACE & EFFICIENCY

### 3A. Pace Metrics (7 windows x 4 stats = 28 features)
| # | Feature | Description |
|---|---------|-------------|
| 169-175 | `pace_L{...}` | Possessions per 48 minutes |
| 176-182 | `possessions_avg_L{...}` | Total possessions per game |
| 183-189 | `pace_delta_vs_league_L{...}` | Pace relative to league average |
| 190-196 | `pace_home_away_diff_L{...}` | Pace difference home vs away |

### 3B. Efficiency Ratings (7 windows x 6 stats = 42 features)
| # | Feature | Description |
|---|---------|-------------|
| 197-203 | `ortg_L{...}` | Offensive rating (pts per 100 poss) |
| 204-210 | `drtg_L{...}` | Defensive rating (pts allowed per 100 poss) |
| 211-217 | `net_rtg_L{...}` | Net rating = ORtg - DRtg |
| 218-224 | `ortg_home_L{...}` | Offensive rating at home |
| 225-231 | `ortg_away_L{...}` | Offensive rating on road |
| 232-238 | `drtg_home_L{...}` | Defensive rating at home |

### 3C. Pace-Adjusted Metrics (4 features)
| # | Feature | Description |
|---|---------|-------------|
| 239 | `expected_pace_matchup` | Average of both teams' pace |
| 240 | `pace_mismatch` | Absolute difference in team paces |
| 241 | `expected_possessions` | Projected possessions in this game |
| 242 | `tempo_free_net_rtg_diff` | Net rating difference (pace-neutral) |

**Subtotal Category 3: 74 features**

---

## CATEGORY 4: SHOOTING & SHOT DISTRIBUTION

### 4A. Overall Shooting Efficiency (7 windows x 6 stats = 42 features)
| # | Feature | Description |
|---|---------|-------------|
| 243-249 | `ts_pct_L{...}` | True Shooting % = PTS / (2 * (FGA + 0.44*FTA)) |
| 250-256 | `fg_pct_L{...}` | Field goal percentage |
| 257-263 | `fg3_pct_L{...}` | Three-point percentage |
| 264-270 | `ft_pct_L{...}` | Free throw percentage |
| 271-277 | `fg3_attempt_rate_L{...}` | 3PA / FGA (three-point attempt rate) |
| 278-284 | `mid_range_pct_L{...}` | Mid-range FG% |

### 4B. Shot Zone Distribution (14 features, season-level)
| # | Feature | Description |
|---|---------|-------------|
| 285 | `pct_shots_restricted_area` | % of shots in restricted area (0-4 ft) |
| 286 | `pct_shots_paint_non_ra` | % of shots in paint (non-restricted) |
| 287 | `pct_shots_mid_range` | % of shots from mid-range |
| 288 | `pct_shots_corner_3` | % of shots from corner three |
| 289 | `pct_shots_above_break_3` | % of shots from above-the-break three |
| 290 | `fg_pct_restricted_area` | FG% in restricted area |
| 291 | `fg_pct_paint_non_ra` | FG% in paint (non-restricted) |
| 292 | `fg_pct_mid_range` | FG% from mid-range |
| 293 | `fg_pct_corner_3` | FG% from corner three |
| 294 | `fg_pct_above_break_3` | FG% from above-the-break three |
| 295 | `pts_in_paint_avg` | Points in the paint per game |
| 296 | `second_chance_pts_avg` | Second chance points per game |
| 297 | `fast_break_pts_avg` | Fast break points per game |
| 298 | `pts_off_turnovers_avg` | Points off turnovers per game |

### 4C. Opponent Shot Defense (14 features, season-level)
| # | Feature | Description |
|---|---------|-------------|
| 299 | `opp_fg_pct_restricted_area` | Opponent FG% allowed at rim |
| 300 | `opp_fg_pct_paint_non_ra` | Opponent FG% allowed in paint |
| 301 | `opp_fg_pct_mid_range` | Opponent FG% allowed mid-range |
| 302 | `opp_fg_pct_corner_3` | Opponent FG% allowed corner 3 |
| 303 | `opp_fg_pct_above_break_3` | Opponent FG% allowed above-break 3 |
| 304 | `opp_pct_shots_restricted_area` | % of opp shots at rim (rim protection deterrence) |
| 305 | `opp_pct_shots_mid_range` | % of opp shots forced to mid-range |
| 306 | `opp_pct_shots_3pt` | % of opp shots from three |
| 307 | `opp_pts_in_paint_avg` | Opp points in paint allowed |
| 308 | `opp_second_chance_pts_avg` | Opp second chance pts allowed |
| 309 | `opp_fast_break_pts_avg` | Opp fast break pts allowed |
| 310 | `opp_pts_off_turnovers_avg` | Opp pts off turnovers allowed |
| 311 | `opp_ts_pct_L10` | Opponent TS% over last 10 games |
| 312 | `opp_efg_pct_L10` | Opponent eFG% over last 10 games |

**Subtotal Category 4: 70 features**

---

## CATEGORY 5: PLAYER IMPACT & INJURIES

### 5A. Team Aggregate Player Metrics (14 features)
| # | Feature | Description |
|---|---------|-------------|
| 313 | `total_team_vorp` | Sum of roster VORP |
| 314 | `total_team_bpm` | Minutes-weighted team BPM |
| 315 | `total_team_ws` | Total team Win Shares |
| 316 | `total_team_per` | Minutes-weighted team PER |
| 317 | `top5_player_vorp_sum` | Sum of top 5 players' VORP |
| 318 | `star_player_bpm` | Best player BPM (max on roster) |
| 319 | `team_depth_score` | Std dev of minutes distribution (higher = deeper) |
| 320 | `bench_scoring_avg` | Average bench points per game |
| 321 | `bench_plus_minus_avg` | Average bench +/- per game |
| 322 | `starters_net_rtg` | Starting lineup net rating |
| 323 | `best_lineup_net_rtg` | Best 5-man lineup net rating (min 50 min) |
| 324 | `worst_lineup_net_rtg` | Worst 5-man lineup net rating (min 50 min) |
| 325 | `lineup_volatility` | Variance across lineup net ratings |
| 326 | `top_closer_clutch_net_rtg` | Best clutch performer's net rating |

### 5B. Injury Impact Features (18 features)
| # | Feature | Description |
|---|---------|-------------|
| 327 | `injured_vorp_missing` | Total VORP of injured/out players |
| 328 | `injured_bpm_missing` | Usage-weighted BPM of missing players |
| 329 | `injured_ws_missing` | Win shares of missing players |
| 330 | `injured_minutes_missing` | Total minutes of missing players |
| 331 | `injured_usage_rate_missing` | Usage-weighted impact of missing players |
| 332 | `star_player_available` | Binary: is the team's best player playing? (1/0) |
| 333 | `num_players_out` | Count of players on injury report (out) |
| 334 | `num_players_questionable` | Count of questionable players |
| 335 | `num_players_probable` | Count of probable players |
| 336 | `injury_adjusted_ortg` | ORtg adjusted for missing player contribution |
| 337 | `injury_adjusted_drtg` | DRtg adjusted for missing player contribution |
| 338 | `days_since_star_return` | Days since best player returned from injury |
| 339 | `games_since_star_return` | Games since best player returned |
| 340 | `top3_players_available_pct` | % of top 3 players (by VORP) available |
| 341 | `replacement_level_gap` | Skill gap between injured and replacement player |
| 342 | `injury_trend_3g` | Are injuries getting worse or better? (delta) |
| 343 | `load_managed_star` | Binary: is star resting (load management)? |
| 344 | `minutes_restriction_active` | Binary: any player on minutes restriction? |

### 5C. Player Tracking / Hustle Aggregates (12 features)
| # | Feature | Description |
|---|---------|-------------|
| 345 | `team_deflections_pg` | Team deflections per game |
| 346 | `team_loose_balls_recovered_pg` | Loose balls recovered per game |
| 347 | `team_contested_shots_pg` | Contested shots per game |
| 348 | `team_contested_3pt_pg` | Contested 3PT shots per game |
| 349 | `team_charges_drawn_pg` | Charges drawn per game |
| 350 | `team_screen_assists_pg` | Screen assists per game |
| 351 | `team_box_outs_pg` | Box outs per game |
| 352 | `team_avg_speed_off` | Average offensive speed (mph) |
| 353 | `team_avg_speed_def` | Average defensive speed (mph) |
| 354 | `team_distance_miles_pg` | Total distance covered per game |
| 355 | `team_touches_pg` | Total touches per game |
| 356 | `team_paint_touches_pg` | Paint touches per game |

**Subtotal Category 5: 44 features**

---

## CATEGORY 6: REST & SCHEDULE

### 6A. Rest Days (12 features)
| # | Feature | Description |
|---|---------|-------------|
| 357 | `rest_days` | Days since last game (0 = B2B) |
| 358 | `opp_rest_days` | Opponent days since last game |
| 359 | `rest_advantage` | rest_days - opp_rest_days |
| 360 | `is_b2b` | Binary: back-to-back? |
| 361 | `is_b2b_away` | Binary: B2B and away? |
| 362 | `is_b2b_2nd_away` | Binary: second night of B2B, on road? |
| 363 | `opp_is_b2b` | Binary: opponent on B2B? |
| 364 | `is_3_in_4_nights` | Binary: 3 games in 4 nights? |
| 365 | `is_4_in_6_nights` | Binary: 4 games in 6 nights? |
| 366 | `is_5_in_7_nights` | Binary: 5 games in 7 nights? |
| 367 | `games_in_last_7_days` | Count of games played in last 7 days |
| 368 | `games_in_last_14_days` | Count of games played in last 14 days |

### 6B. Travel Fatigue (12 features)
| # | Feature | Description |
|---|---------|-------------|
| 369 | `travel_distance_miles` | Distance from last game venue |
| 370 | `travel_distance_cumul_7d` | Cumulative travel in last 7 days |
| 371 | `travel_distance_cumul_14d` | Cumulative travel in last 14 days |
| 372 | `timezone_change` | Timezone shift from last game |
| 373 | `timezone_direction` | East (+) or West (-) travel |
| 374 | `timezone_cumul_7d` | Cumulative timezone changes in 7 days |
| 375 | `altitude_change_ft` | Altitude change from last venue |
| 376 | `altitude_current_venue` | Current game venue altitude |
| 377 | `is_high_altitude_game` | Binary: Denver or Utah game? |
| 378 | `fatigue_composite_score` | Weighted: distance + TZ + altitude + B2B |
| 379 | `opp_travel_distance_miles` | Opponent travel distance |
| 380 | `opp_fatigue_composite` | Opponent fatigue composite |

### 6C. Schedule Context (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 381 | `home_road_trip_length` | Current consecutive home/away game count |
| 382 | `road_trip_game_number` | Game N of a road trip (1st, 2nd, 3rd...) |
| 383 | `home_stand_game_number` | Game N of home stand |
| 384 | `days_until_next_game` | Look-ahead rest (motivation to conserve energy?) |
| 385 | `is_first_game_after_allstar` | Binary: first game post All-Star break |
| 386 | `is_first_game_after_break` | Binary: first game after any 3+ day break |
| 387 | `schedule_difficulty_next5` | Avg opponent win% in next 5 games |
| 388 | `is_national_tv_game` | Binary: ESPN/TNT/ABC national broadcast |
| 389 | `game_start_time_local` | Local start time (early = afternoon, late = 10pm+) |
| 390 | `opp_schedule_difficulty_next5` | Opponent's upcoming schedule strength |

**Subtotal Category 6: 34 features**

---

## CATEGORY 7: MARKET MICROSTRUCTURE (Betting Lines & Odds)

### 7A. Spread Features (14 features)
| # | Feature | Description |
|---|---------|-------------|
| 391 | `spread_open` | Opening point spread |
| 392 | `spread_close` | Closing point spread |
| 393 | `spread_movement` | spread_close - spread_open |
| 394 | `spread_movement_abs` | Absolute spread movement |
| 395 | `spread_movement_direction` | +1 if moved toward team, -1 away |
| 396 | `spread_pinnacle_close` | Pinnacle closing spread (sharpest) |
| 397 | `spread_consensus` | Average across 5+ books |
| 398 | `spread_dispersion` | Std dev of spread across books |
| 399 | `spread_vs_power_rating` | Model spread minus market spread |
| 400 | `spread_crossed_key_number` | Binary: crossed 3, 5, 7, or 10? |
| 401 | `is_pick_em` | Binary: spread within +/- 1.5 |
| 402 | `spread_home_ats_season` | Home team's season ATS record |
| 403 | `spread_away_ats_season` | Away team's season ATS record |
| 404 | `spread_ats_L10` | Team's ATS record last 10 games |

### 7B. Moneyline Features (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 405 | `ml_open_home` | Opening moneyline (home) |
| 406 | `ml_close_home` | Closing moneyline (home) |
| 407 | `ml_implied_prob_open` | Implied probability from opening ML |
| 408 | `ml_implied_prob_close` | Implied probability from closing ML |
| 409 | `ml_movement` | Moneyline shift (open to close) |
| 410 | `ml_pinnacle_implied` | Pinnacle de-vigged implied probability |
| 411 | `ml_best_available` | Best available ML odds across books |
| 412 | `ml_worst_available` | Worst available ML odds across books |
| 413 | `ml_market_width` | Best - worst (market efficiency indicator) |
| 414 | `ml_no_vig_fair_prob` | De-vigged fair probability |

### 7C. Total (Over/Under) Features (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 415 | `total_open` | Opening total points line |
| 416 | `total_close` | Closing total points line |
| 417 | `total_movement` | Total shift (open to close) |
| 418 | `total_movement_direction` | Over or under movement |
| 419 | `total_pinnacle_close` | Pinnacle closing total |
| 420 | `total_vs_model_projection` | Model projected total minus market total |
| 421 | `total_season_avg_combined` | Season avg combined scoring of both teams |
| 422 | `total_over_trend_L10` | Over% in last 10 games (both teams) |
| 423 | `total_1h_2h_split` | 1st half vs 2nd half scoring tendency |
| 424 | `total_dispersion_across_books` | Std dev of total across books |

### 7D. Sharp Money Signals (14 features)
| # | Feature | Description |
|---|---------|-------------|
| 425 | `clv_last_bet` | Closing line value of our last bet |
| 426 | `steam_move_detected` | Binary: rapid multi-book line move |
| 427 | `reverse_line_movement` | Binary: line moved opposite to public % |
| 428 | `public_bet_pct_spread` | % of bets on this side (spread) |
| 429 | `public_money_pct_spread` | % of money on this side (spread) |
| 430 | `sharp_money_indicator` | money% - bet% divergence |
| 431 | `public_bet_pct_total` | % of bets on over/under |
| 432 | `public_money_pct_total` | % of money on over/under |
| 433 | `line_freeze` | Binary: line didn't move despite heavy action |
| 434 | `books_disagreement_score` | Max spread difference across books |
| 435 | `pinnacle_vs_market_avg` | Pinnacle line vs average market line |
| 436 | `time_of_line_move` | How early/late did the biggest move happen? |
| 437 | `num_line_changes` | Total number of line changes pre-game |
| 438 | `kaunitz_consensus_gap` | Gap between bookmaker consensus and true probability |

**Subtotal Category 7: 48 features**

---

## CATEGORY 8: OPPONENT-ADJUSTED METRICS

### 8A. Strength of Schedule (7 windows x 4 stats = 28 features)
| # | Feature | Description |
|---|---------|-------------|
| 439-445 | `sos_win_pct_L{...}` | Avg opponent win% over window |
| 446-452 | `sos_net_rtg_L{...}` | Avg opponent net rating over window |
| 453-459 | `sos_ortg_L{...}` | Avg opponent offensive rating |
| 460-466 | `sos_drtg_L{...}` | Avg opponent defensive rating |

### 8B. Performance vs Opponent Tiers (12 features)
| # | Feature | Description |
|---|---------|-------------|
| 467 | `record_vs_top10_teams` | Win% vs top 10 teams (by net rating) |
| 468 | `record_vs_bottom10_teams` | Win% vs bottom 10 teams |
| 469 | `record_vs_500_plus_teams` | Win% vs .500+ teams |
| 470 | `record_vs_sub_500_teams` | Win% vs sub-.500 teams |
| 471 | `margin_vs_top10` | Average margin vs top 10 |
| 472 | `margin_vs_bottom10` | Average margin vs bottom 10 |
| 473 | `ortg_vs_top10_defense` | ORtg against top 10 defenses |
| 474 | `ortg_vs_bottom10_defense` | ORtg against bottom 10 defenses |
| 475 | `drtg_vs_top10_offense` | DRtg against top 10 offenses |
| 476 | `drtg_vs_bottom10_offense` | DRtg against bottom 10 offenses |
| 477 | `opp_current_tier` | Opponent's current tier (top/mid/bottom) |
| 478 | `tier_adjusted_net_rtg` | Net rating adjusted for schedule strength |

### 8C. Opponent-Specific Matchup (8 features)
| # | Feature | Description |
|---|---------|-------------|
| 479 | `opp_ortg_season` | Opponent's current season ORtg |
| 480 | `opp_drtg_season` | Opponent's current season DRtg |
| 481 | `opp_net_rtg_season` | Opponent's current season net rating |
| 482 | `opp_pace_season` | Opponent's current pace |
| 483 | `opp_ts_pct_season` | Opponent's current TS% |
| 484 | `opp_tov_rate_season` | Opponent's current turnover rate |
| 485 | `opp_oreb_pct_season` | Opponent's offensive rebound % |
| 486 | `opp_ft_rate_season` | Opponent's free throw rate |

**Subtotal Category 8: 48 features**

---

## CATEGORY 9: MOMENTUM & FORM

### 9A. Streak Features (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 487 | `current_streak` | Current W/L streak length (+/- for W/L) |
| 488 | `current_streak_home` | Current home W/L streak |
| 489 | `current_streak_away` | Current away W/L streak |
| 490 | `current_ats_streak` | Current ATS cover streak |
| 491 | `longest_win_streak_season` | Longest winning streak this season |
| 492 | `longest_losing_streak_season` | Longest losing streak this season |
| 493 | `opp_current_streak` | Opponent's current streak |
| 494 | `streak_against_opp` | Current streak in H2H matchup |
| 495 | `combined_momentum` | Team streak minus opp streak |
| 496 | `is_bounce_back` | Binary: coming off a blowout loss (>15 pts)? |

### 9B. Recent Form vs Season Average (14 features)
| # | Feature | Description |
|---|---------|-------------|
| 497 | `ortg_L5_vs_season` | Recent ORtg minus season ORtg |
| 498 | `drtg_L5_vs_season` | Recent DRtg minus season DRtg |
| 499 | `net_rtg_L5_vs_season` | Recent NetRtg minus season NetRtg |
| 500 | `ts_pct_L5_vs_season` | Recent TS% minus season TS% |
| 501 | `fg3_pct_L5_vs_season` | Recent 3PT% minus season 3PT% |
| 502 | `ft_pct_L5_vs_season` | Recent FT% minus season FT% |
| 503 | `tov_rate_L5_vs_season` | Recent TOV% minus season TOV% |
| 504 | `oreb_pct_L5_vs_season` | Recent OREB% minus season OREB% |
| 505 | `pts_L5_vs_season` | Recent scoring vs season avg |
| 506 | `pts_allowed_L5_vs_season` | Recent defense vs season avg |
| 507 | `ortg_L3_vs_L10` | Very recent form vs medium-term form |
| 508 | `drtg_L3_vs_L10` | Very recent defense vs medium-term |
| 509 | `scoring_trend_slope` | Linear regression slope of last 10 game scores |
| 510 | `defense_trend_slope` | Linear regression slope of last 10 pts allowed |

### 9C. Hot/Cold Shooting Detection (8 features)
| # | Feature | Description |
|---|---------|-------------|
| 511 | `fg3_pct_L3_zscore` | 3PT% last 3 games as z-score vs season |
| 512 | `ts_pct_L3_zscore` | TS% last 3 games as z-score vs season |
| 513 | `is_hot_shooting_L3` | Binary: 3PT% > 1.5 std dev above season avg |
| 514 | `is_cold_shooting_L3` | Binary: 3PT% > 1.5 std dev below season avg |
| 515 | `opp_fg3_pct_L3_zscore` | Opponent's recent 3PT% z-score |
| 516 | `ft_pct_L3_zscore` | FT% last 3 games z-score |
| 517 | `shooting_regression_expected` | Expected regression to mean (hot = negative) |
| 518 | `opp_shooting_regression_expected` | Opponent's expected shooting regression |

**Subtotal Category 9: 32 features**

---

## CATEGORY 10: MATCHUP-SPECIFIC

### 10A. Head-to-Head History (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 519 | `h2h_record_season` | H2H record this season |
| 520 | `h2h_record_last3_seasons` | H2H record last 3 seasons |
| 521 | `h2h_avg_margin_season` | Average H2H margin this season |
| 522 | `h2h_avg_margin_last3` | Average H2H margin last 3 seasons |
| 523 | `h2h_avg_total_season` | Average combined score in H2H |
| 524 | `h2h_games_played_season` | Number of H2H meetings this season |
| 525 | `h2h_home_record` | H2H record at this venue |
| 526 | `h2h_ats_record` | H2H against-the-spread record |
| 527 | `h2h_over_under_record` | H2H over/under record |
| 528 | `h2h_last_game_margin` | Margin of most recent H2H game |

### 10B. Style Matchup (14 features)
| # | Feature | Description |
|---|---------|-------------|
| 529 | `pace_delta` | Team pace minus opponent pace |
| 530 | `fg3_attempt_rate_delta` | 3PA rate difference |
| 531 | `paint_scoring_vs_opp_paint_defense` | Points in paint vs opp paint defense |
| 532 | `fg3_pct_vs_opp_3pt_defense` | Team 3PT% vs opp 3PT defense% |
| 533 | `oreb_pct_vs_opp_dreb_pct` | Team OREB% vs opp DREB% |
| 534 | `tov_rate_vs_opp_steal_rate` | Team TOV% vs opp steal rate |
| 535 | `ft_rate_vs_opp_foul_rate` | Team FT rate vs opp fouls per game |
| 536 | `fast_break_pts_vs_opp_transition_defense` | Fast break pts vs opp transition D |
| 537 | `bench_scoring_vs_opp_bench` | Bench scoring advantage |
| 538 | `size_matchup_avg_height` | Average roster height difference |
| 539 | `size_matchup_avg_weight` | Average roster weight difference |
| 540 | `assist_rate_delta` | Team assist rate vs opponent |
| 541 | `block_rate_vs_opp_rim_attack` | Team block% vs opp shots at rim |
| 542 | `steal_rate_vs_opp_tov_tendency` | Team steal% vs opp turnover tendency |

### 10C. Play Type Matchup (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 543 | `iso_freq_vs_opp_iso_defense` | Isolation frequency vs opp ISO defense |
| 544 | `pnr_handler_freq_vs_opp_pnr_defense` | Pick & roll handler vs opp PnR defense |
| 545 | `pnr_roll_freq_vs_opp_roll_defense` | Pick & roll roll man vs opp roll defense |
| 546 | `post_up_freq_vs_opp_post_defense` | Post-up frequency vs opp post defense |
| 547 | `spot_up_freq_vs_opp_spot_defense` | Spot-up frequency vs opp spot-up defense |
| 548 | `transition_freq_vs_opp_transition_defense` | Transition freq vs opp transition D |
| 549 | `cut_freq_vs_opp_cut_defense` | Cut frequency vs opp cut defense |
| 550 | `handoff_freq_vs_opp_handoff_defense` | Handoff frequency vs opp handoff D |
| 551 | `off_screen_freq_vs_opp_screen_defense` | Off-screen freq vs opp screen D |
| 552 | `putback_freq_vs_opp_putback_defense` | Putback freq vs opp putback D |

**Subtotal Category 10: 34 features**

---

## CATEGORY 11: POWER RATINGS & META

### 11A. Elo & Power Ratings (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 553 | `elo_rating` | Current Elo rating |
| 554 | `opp_elo_rating` | Opponent Elo rating |
| 555 | `elo_diff` | Elo difference (home - away) |
| 556 | `elo_season_high` | Season-high Elo |
| 557 | `elo_season_low` | Season-low Elo |
| 558 | `elo_pct_of_range` | Where current Elo falls in season range |
| 559 | `elo_change_L5` | Elo change over last 5 games |
| 560 | `elo_change_L10` | Elo change over last 10 games |
| 561 | `power_rating` | Custom composite power rating |
| 562 | `power_rating_diff` | Power rating difference (home - away) |

### 11B. Pythagorean & Expected Metrics (8 features)
| # | Feature | Description |
|---|---------|-------------|
| 563 | `pythagorean_win_pct` | Expected win% from pts scored/allowed |
| 564 | `pythagorean_vs_actual` | Over/underperformance vs Pythagorean |
| 565 | `opp_pythagorean_win_pct` | Opponent's Pythagorean win% |
| 566 | `opp_pythagorean_vs_actual` | Opponent's over/underperformance |
| 567 | `luck_factor` | Actual wins minus expected wins |
| 568 | `opp_luck_factor` | Opponent's luck factor |
| 569 | `clutch_win_pct_vs_expected` | Win% in close games vs expected |
| 570 | `regression_candidate_score` | How likely to regress (combines luck metrics) |

### 11C. Season Context (12 features)
| # | Feature | Description |
|---|---------|-------------|
| 571 | `season_game_number` | Game N of 82 (early/mid/late season) |
| 572 | `season_phase` | Phase encoding: preseason_form/early/mid/late/playoff_push |
| 573 | `is_playoff_contender` | Binary: currently in playoff position? |
| 574 | `games_back_from_playoff` | Games behind 8th/10th seed |
| 575 | `is_tanking_candidate` | Binary: bottom 5 record + post-trade-deadline? |
| 576 | `is_division_game` | Binary: same division? |
| 577 | `is_conference_game` | Binary: same conference? |
| 578 | `is_rivalry_game` | Binary: known rivalry (LAL-BOS, etc.)? |
| 579 | `days_since_trade_deadline` | Days since trade deadline (roster disruption) |
| 580 | `roster_continuity_pct` | % of minutes from players on roster all season |
| 581 | `new_player_integration_games` | Games since last major trade/signing |
| 582 | `coach_tenure_games` | Games under current head coach |

**Subtotal Category 11: 30 features**

---

## CATEGORY 12: ADVANCED BOX SCORE DERIVATIVES

### 12A. Team-Level Advanced (14 features, L10 window)
| # | Feature | Description |
|---|---------|-------------|
| 583 | `ast_pct_L10` | Assist percentage (assisted FGs / total FGs) |
| 584 | `ast_to_tov_ratio_L10` | Assist-to-turnover ratio |
| 585 | `stl_pct_L10` | Steal percentage per 100 possessions |
| 586 | `blk_pct_L10` | Block percentage per 100 possessions |
| 587 | `dreb_pct_L10` | Defensive rebound percentage |
| 588 | `total_reb_pct_L10` | Total rebound percentage |
| 589 | `pf_per_poss_L10` | Personal fouls per possession |
| 590 | `opp_pf_per_poss_L10` | Opponent fouls drawn per possession |
| 591 | `ast_ratio_L10` | Assist ratio = AST / (FGA + 0.44*FTA + AST + TOV) |
| 592 | `usage_concentration_top3` | % of usage by top 3 players (ball-dominant?) |
| 593 | `effective_poss_per_game` | Effective possessions (excl. end-of-period) |
| 594 | `half_court_ortg` | Half-court offensive rating (excl. transition) |
| 595 | `transition_ortg` | Transition offensive rating |
| 596 | `half_court_drtg` | Half-court defensive rating |

### 12B. Clutch Stats (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 597 | `clutch_net_rtg` | Net rating in clutch (last 5 min, <=5 pt game) |
| 598 | `clutch_ortg` | Offensive rating in clutch |
| 599 | `clutch_drtg` | Defensive rating in clutch |
| 600 | `clutch_fg_pct` | FG% in clutch |
| 601 | `clutch_ft_pct` | FT% in clutch |
| 602 | `clutch_tov_rate` | Turnover rate in clutch |
| 603 | `clutch_win_pct` | Win% when game is clutch |
| 604 | `clutch_minutes_pct` | % of games that reached clutch time |
| 605 | `opp_clutch_net_rtg` | Opponent's clutch net rating |
| 606 | `clutch_differential` | Team clutch NetRtg minus opp clutch NetRtg |

**Subtotal Category 12: 24 features**

---

## CATEGORY 13: REFEREE & GAME CONDITIONS

### 13A. Referee Features (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 607 | `ref_crew_avg_total` | Average total points in this crew's games |
| 608 | `ref_crew_avg_fouls` | Average fouls called per game by this crew |
| 609 | `ref_crew_home_cover_pct` | Home team cover % with this crew |
| 610 | `ref_crew_over_pct` | Over% in games with this crew |
| 611 | `ref_lead_home_bias` | Lead ref's historical home team advantage |
| 612 | `ref_crew_avg_ft_attempts` | Average FTA per game by this crew |
| 613 | `team_record_with_ref` | Team's record with this lead ref |
| 614 | `opp_record_with_ref` | Opponent's record with this lead ref |
| 615 | `ref_crew_tech_fouls_avg` | Average technicals per game by this crew |
| 616 | `ref_pace_tendency` | Does this crew call a fast or slow game? |

### 13B. Home Court Features (8 features)
| # | Feature | Description |
|---|---------|-------------|
| 617 | `is_home` | Binary: home team? |
| 618 | `home_court_advantage_pts` | Historical HCA for this team (pts above avg) |
| 619 | `home_win_pct_season` | Home win% this season |
| 620 | `away_win_pct_season` | Away win% this season |
| 621 | `home_ortg_season` | Home offensive rating |
| 622 | `away_ortg_season` | Away offensive rating |
| 623 | `home_drtg_season` | Home defensive rating |
| 624 | `away_drtg_season` | Away defensive rating |

**Subtotal Category 13: 18 features**

---

## CATEGORY 14: DARKO & EXTERNAL MODEL FEATURES

### 14A. DARKO Player Projections (8 features)
| # | Feature | Description |
|---|---------|-------------|
| 625 | `darko_team_dpm_sum` | Sum of available players' DARKO DPM |
| 626 | `darko_team_o_dpm_sum` | Sum of DARKO offensive DPM |
| 627 | `darko_team_d_dpm_sum` | Sum of DARKO defensive DPM |
| 628 | `darko_proj_margin` | DARKO-projected game margin |
| 629 | `darko_proj_total` | DARKO-projected total points |
| 630 | `darko_missing_dpm` | DARKO DPM of injured/missing players |
| 631 | `darko_vs_opp_darko` | Team DARKO sum minus opp DARKO sum |
| 632 | `darko_lineup_adjusted` | DARKO adjusted for projected starters |

### 14B. External Model Consensus (8 features)
| # | Feature | Description |
|---|---------|-------------|
| 633 | `fivethirtyeight_elo_diff` | 538/Nate Silver Elo difference |
| 634 | `espn_bpi_diff` | ESPN BPI difference |
| 635 | `model_consensus_prob` | Average of all external model probabilities |
| 636 | `model_consensus_vs_market` | Model consensus minus market implied prob |
| 637 | `model_agreement_score` | How much do external models agree? (1=unanimous) |
| 638 | `model_edge_vs_market` | Largest model edge over market |
| 639 | `polymarket_implied_prob` | Polymarket (if available) implied probability |
| 640 | `prediction_market_vs_books` | Prediction market prob minus book implied prob |

**Subtotal Category 14: 16 features**

---

## CATEGORY 15: DEFENSIVE SCHEME & TRANSITION

### 15A. Defensive Profile (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 641 | `def_fg_pct_at_rim` | Opponent FG% allowed at rim |
| 642 | `def_fg_pct_mid` | Opponent FG% allowed mid-range |
| 643 | `def_fg_pct_3pt` | Opponent FG% allowed from 3 |
| 644 | `def_rim_deterrence` | % of opp shots forced away from rim |
| 645 | `def_3pt_contest_rate` | % of 3PT attempts that are contested |
| 646 | `def_paint_pts_allowed` | Opponent paint points allowed per game |
| 647 | `def_fast_break_pts_allowed` | Opponent fast break points allowed |
| 648 | `def_2nd_chance_pts_allowed` | Opponent second chance points allowed |
| 649 | `def_iso_ppp` | Points per possession allowed in isolation |
| 650 | `def_pnr_ppp` | Points per possession allowed in PnR |

### 15B. Transition Metrics (8 features)
| # | Feature | Description |
|---|---------|-------------|
| 651 | `transition_freq_off` | % of possessions in transition (offense) |
| 652 | `transition_ppp_off` | Points per possession in transition (offense) |
| 653 | `transition_freq_def` | % of opponent possessions in transition |
| 654 | `transition_ppp_def` | PPP allowed in transition |
| 655 | `half_court_ppp_off` | PPP in half-court offense |
| 656 | `half_court_ppp_def` | PPP allowed in half-court defense |
| 657 | `early_offense_freq` | % of possessions as early offense (first 8 sec) |
| 658 | `late_clock_freq` | % of possessions ending with <7 sec on shot clock |

**Subtotal Category 15: 18 features**

---

## CATEGORY 16: TEMPORAL & CALENDAR

### 16A. Calendar Features (10 features)
| # | Feature | Description |
|---|---------|-------------|
| 659 | `day_of_week` | Day of week (0-6) |
| 660 | `is_weekend` | Binary: Saturday or Sunday? |
| 661 | `month_of_season` | Month (Oct=1 through Jun=9) |
| 662 | `is_pre_allstar` | Binary: before All-Star break? |
| 663 | `is_post_allstar` | Binary: after All-Star break? |
| 664 | `is_post_trade_deadline` | Binary: after trade deadline? |
| 665 | `is_last_10_games` | Binary: final 10 games of season? |
| 666 | `is_last_week` | Binary: final week of regular season? |
| 667 | `is_december` | Binary: historically low-effort month |
| 668 | `is_april` | Binary: historically high-effort month (seeding) |

### 16B. Time Series Features (8 features)
| # | Feature | Description |
|---|---------|-------------|
| 669 | `ewma_net_rtg_alpha05` | Exponentially weighted moving avg net rating (alpha=0.05) |
| 670 | `ewma_net_rtg_alpha15` | EWMA net rating (alpha=0.15, faster decay) |
| 671 | `ewma_net_rtg_alpha30` | EWMA net rating (alpha=0.30, very recent) |
| 672 | `trend_strength_5g` | Slope of 5-game linear regression on margin |
| 673 | `trend_strength_10g` | Slope of 10-game linear regression on margin |
| 674 | `volatility_10g` | Standard deviation of margins over 10 games |
| 675 | `volatility_20g` | Standard deviation of margins over 20 games |
| 676 | `consistency_score` | 1 - (volatility / abs(mean_margin)) |

**Subtotal Category 16: 18 features**

---

## CATEGORY 17: INTERACTION & DERIVED FEATURES

### 17A. Cross-Category Interactions (20 features)
| # | Feature | Description |
|---|---------|-------------|
| 677 | `rest_x_travel_fatigue` | rest_days * fatigue_composite (interaction) |
| 678 | `b2b_x_away` | is_b2b * (1 - is_home) |
| 679 | `injury_impact_x_b2b` | injured_vorp_missing * is_b2b |
| 680 | `elo_diff_x_rest_adv` | elo_diff * rest_advantage |
| 681 | `hot_shooting_x_3pt_defense` | is_hot_shooting * opp_3pt_defense |
| 682 | `pace_delta_x_transition_freq` | pace_delta * transition_freq_off |
| 683 | `home_x_altitude` | is_home * altitude_current_venue |
| 684 | `streak_x_motivation` | current_streak * is_playoff_contender |
| 685 | `spread_edge_x_sharp_signal` | spread_vs_power_rating * sharp_money_indicator |
| 686 | `fatigue_x_opp_pace` | fatigue_composite * opp_pace_season |
| 687 | `injury_x_bench_depth` | injured_vorp_missing * team_depth_score |
| 688 | `clutch_diff_x_close_game_freq` | clutch_differential * clutch_minutes_pct |
| 689 | `paint_attack_x_rim_protection` | pts_in_paint_avg * opp_fg_pct_restricted_area |
| 690 | `3pt_volume_x_3pt_defense` | fg3_attempt_rate * opp_fg_pct_above_break_3 |
| 691 | `tov_rate_x_opp_steal_rate` | tov_rate * opp_stl_pct |
| 692 | `ref_foul_tendency_x_ft_rate` | ref_crew_avg_fouls * ft_rate_off |
| 693 | `b2b_x_altitude_change` | is_b2b * altitude_change_ft |
| 694 | `regression_x_luck` | shooting_regression_expected * luck_factor |
| 695 | `road_trip_x_fatigue` | road_trip_game_number * fatigue_composite |
| 696 | `tanking_x_spread` | is_tanking_candidate * spread_open |

### 17B. Ratio & Composite Features (12 features)
| # | Feature | Description |
|---|---------|-------------|
| 697 | `offense_defense_balance` | abs(ortg_rank - drtg_rank) (balanced vs lopsided) |
| 698 | `four_factors_offense_rank` | Composite rank across 4 offensive factors |
| 699 | `four_factors_defense_rank` | Composite rank across 4 defensive factors |
| 700 | `overall_efficiency_rank` | Combined off + def efficiency rank |
| 701 | `market_model_divergence` | abs(model_prob - market_implied_prob) |
| 702 | `total_edge_score` | Composite of all identified edges |
| 703 | `home_away_performance_gap` | Home NetRtg minus Away NetRtg |
| 704 | `opp_home_away_performance_gap` | Opponent's home/away gap |
| 705 | `fatigue_adjusted_net_rtg` | Net rating minus fatigue penalty |
| 706 | `injury_adjusted_net_rtg` | Net rating minus injury impact |
| 707 | `full_strength_net_rtg` | Net rating when all top 5 players available |
| 708 | `projected_game_margin` | Master model projected margin |

**Subtotal Category 17: 32 features**

---

## GRAND TOTAL: 708 Feature Candidates

### Summary by Category

| # | Category | Count |
|---|----------|-------|
| 1 | Team Rolling Stats (Win/Loss, Scoring) | 105 |
| 2 | Four Factors (Dean Oliver) | 63 |
| 3 | Pace & Efficiency | 74 |
| 4 | Shooting & Shot Distribution | 70 |
| 5 | Player Impact & Injuries | 44 |
| 6 | Rest & Schedule | 34 |
| 7 | Market Microstructure | 48 |
| 8 | Opponent-Adjusted Metrics | 48 |
| 9 | Momentum & Form | 32 |
| 10 | Matchup-Specific | 34 |
| 11 | Power Ratings & Meta | 30 |
| 12 | Advanced Box Score Derivatives | 24 |
| 13 | Referee & Game Conditions | 18 |
| 14 | DARKO & External Models | 16 |
| 15 | Defensive Scheme & Transition | 18 |
| 16 | Temporal & Calendar | 18 |
| 17 | Interaction & Derived Features | 32 |
| **TOTAL** | | **708** |

---

## Data Sources for Each Category

| Category | Primary Source | Endpoint / API |
|----------|---------------|----------------|
| 1-4, 12 | nba_api | `TeamGameLog`, `LeagueDashTeamStats`, `TeamDashboardByGeneralSplits` |
| 2 | nba_api | `LeagueDashTeamStats` (MeasureType=Four Factors) |
| 3 | nba_api | `LeagueDashTeamStats` (MeasureType=Advanced) |
| 4 | nba_api | `LeagueDashTeamPtShot`, `TeamDashboardByShootingSplits` |
| 5 (impact) | nba_api + DARKO | `LeagueDashPlayerStats`, DARKO Google Sheet |
| 5 (injuries) | Rotowire / NBA injury API | Custom scraper |
| 5 (hustle) | nba_api | `LeagueHustleStatsTeam`, `LeagueHustleStatsPlayer` |
| 5 (tracking) | nba_api | `LeagueDashPtStats`, player speed & distance endpoint |
| 6 | Computed | Schedule + arena coordinates |
| 7 | OddsHarvester | OddsPortal scraper (80+ books) |
| 8 | Computed | From categories 1-4 + opponent data |
| 9 | Computed | From categories 1-4 (rolling deltas) |
| 10 | nba_api + Synergy | `LeagueDashTeamPtShot`, Synergy play type stats |
| 11 | Computed + external | Elo model + 538 + ESPN BPI |
| 12 | nba_api | `LeagueDashTeamClutch`, `TeamDashboardByGeneralSplits` |
| 13 | Covers.com / Ref API | Referee assignment + historical stats |
| 14 | DARKO + external | beta.darko.app, 538, ESPN BPI |
| 15 | nba_api | `LeagueDashTeamPtShot`, defensive dashboard endpoints |
| 16 | Computed | Calendar + time series transforms |
| 17 | Computed | Cross-products and ratios of above features |

---

## Genetic Algorithm Feature Selection Strategy

### Phase 1: Baseline (all 708)
- Compute all features for 8 seasons (2018-2026)
- Correlation analysis: remove features with >0.95 pairwise correlation
- Expected reduction: 708 -> ~500 uncorrelated features

### Phase 2: GA Selection
- Population: 200 chromosomes (each = binary mask of 500 features)
- Fitness: 5-fold time-series CV Brier score (lower = better)
- Selection: tournament (k=5)
- Crossover: uniform crossover (50% swap rate)
- Mutation: 2% bit flip per feature
- Generations: 100-200
- Elitism: top 10% preserved
- Target: optimal subset of 80-120 features

### Phase 3: Validation
- Walk-forward validation on unseen seasons
- Compare GA-selected vs manual 75-feature baseline
- Target improvement: Brier 0.2034 -> < 0.195

### Phase 4: Ensemble
- Run GA selection for each model type (XGBoost, LightGBM, CatBoost)
- Each model may prefer different feature subsets
- Meta-learner combines model outputs with their preferred features
