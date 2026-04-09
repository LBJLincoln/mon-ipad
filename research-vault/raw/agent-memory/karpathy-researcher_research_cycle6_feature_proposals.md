---
name: Karpathy Cycle 6 — Unconventional Feature Proposals
description: 18 unconventional NBA feature categories researched March 2026. Beyond standard box score. Sources: arXiv, Nature, Chronobiology International, MDPI, SAGE.
type: project
---

Research cycle 6 — feature proposals beyond the existing 38 categories. Engine is at v3.0-38cat with 6142+ features. These proposals cover territory NOT yet in the engine.

**Why:** Best Brier = 0.21570 (TabICL Colab). Target is <0.20. The gap requires novel signal orthogonal to box score.

**How to apply:** Each proposal includes the Cat number to add (39–56), data source, and implementation path.

## HIGH-PRIORITY PROPOSALS (ranked by expected signal × ease)

### Cat 39: Circadian Rhythm / Travel Fatigue (HIGH signal, confirmed in 25k-game study)
- Source: Chronobiology International 2024 (Taylor & Francis, 25,016 matches, 21 seasons)
- Signal: PDT home vs EDT away = 63.5% win rate; EDT home vs PDT away = 55.0%. ~10% differential.
- Features: `circadian_phase_diff`, `timezone_crossing_days_since`, `travel_direction_east_west`, `cumulative_miles_last_7d`, `altitude_delta_feet` (Denver = 5280ft), `days_since_last_altitude_game`
- Data source: Team city coordinates + schedule (nba_api LeagueSchedule), Denver altitude lookup
- Implementation: MEDIUM (need schedule parsing + city coordinates table)
- Academic: Erlacher et al. 2024 Chronobiology International; PubMed 38689400

### Cat 40: Referee Crew Analytics (HIGH signal, 3-5 pt total shift)
- Source: Belasen et al. 2025 (SAGE Journals), RefEye AI, Covers.com/OddsShark live data
- Signal: Scott Foster games go OVER 67% of time. Referee crew shifts total by 3-5 pts. Home bias = 1.2 ppt more calls for home team. 15-20% improvement claimed by bettors using ref data.
- Features: `ref_crew_avg_foul_rate`, `ref_crew_home_bias_score`, `ref_crew_over_pct_last20`, `ref_crew_pace_tendency`, `ref_crew_total_foul_variance`, `ref_home_adv_adj`
- Data source: NBA.com/referees page (scrape), Covers.com referee stats, DonaghyEffect.com
- Implementation: MEDIUM (scraping needed, ref assignments usually announced day-of)
- Academic: Belasen 2025 SAGE doi:10.1177/15270025251369447; PMC 10031197 (implicit bias)

### Cat 41: Transition vs Half-Court Efficiency Split (HIGH signal, clear style mismatch)
- Source: Cleaning The Glass, NBA.com/stats/teams/transition, inpredictable.com
- Signal: Transition play = 1.228 pts/poss vs half-court = 1.084 pts/poss. Cleveland 2024-25 = 1.38 pts/poss in transition (best in league). Style mismatch between fast/slow teams is exploitable.
- Features: `h_transition_ppp`, `a_transition_ppp`, `transition_freq_diff`, `h_halfcourt_ortg`, `a_halfcourt_ortg`, `halfcourt_ortg_diff`, `transition_steal_ppp_diff`, `h_transition_drtg`, `a_transition_drtg`
- Data source: NBA.com stats API (play-type breakdown), Cleaning the Glass (CTG scrape)
- Implementation: EASY (NBA stats API has play-type endpoint: `PlayType` with `TypeGrouping=Transition`)
- No paywall for NBA.com stats API

### Cat 42: Shot Chart Zone Differentials (MEDIUM signal, spatial mismatch)
- Source: arXiv 2405.01182 (model-based shot charts), arXiv 2105.12785 (corner 3s), ShotQuality.com
- Signal: Teams have different zone efficiencies vs specific opponents. Corner 3 rate is highly efficient (arXiv corner 3 paper). Defense-in-zone efficiency reveals mismatches.
- Features: `h_corner3_rate_allowed`, `a_corner3_rate_allowed`, `corner3_mismatch`, `h_paint_pts_pct`, `a_paint_pts_pct`, `h_midrange_freq`, `a_midrange_freq`, `zone_eff_mismatch_score`
- Data source: NBA.com ShotChart API (`shotchartdetail`), already accessible via nba_api
- Implementation: EASY (nba_api.stats.endpoints.ShotChartDetail is free)

### Cat 43: Clutch Performance Trends (MEDIUM signal, undervalued in standard models)
- Source: MDPI 2024 (Clutch Dynamics paper), arXiv 2510.08597, NBA.com/stats/teams/clutch-advanced
- Signal: Shai Gilgeous-Alexander ranked #1 clutch 2023-24. Clutch net rating is distinct from overall net rating. Teams with high clutch ortg win more close games by definition.
- Features: `h_clutch_net_rtg_last10`, `a_clutch_net_rtg_last10`, `h_clutch_fg_pct`, `a_clutch_fg_pct`, `h_clutch_turnover_rate`, `a_clutch_turnover_rate`, `clutch_net_diff`, `h_close_game_record_pct`
- Data source: NBA.com/stats/teams/clutch-traditional (free API)
- Implementation: EASY (nba_api.stats.endpoints.TeamGameLogs + clutch filter)

### Cat 44: Lineup Rotation Stability / Entropy (MEDIUM signal, underused in models)
- Source: CoreSportsBetting.com analysis, CraftedNBA.com, DataBallR WOWY
- Signal: Teams with stable rotations have predictable scoring margins. High entropy (constant shuffling) = unpredictable performance. Top-5 lineup net rating predicts team ceiling.
- Features: `h_rotation_entropy_5g`, `a_rotation_entropy_5g`, `h_top5_lineup_net_rtg`, `a_top5_lineup_net_rtg`, `h_bench_minutes_pct`, `a_bench_minutes_pct`, `h_starter_minutes_consistency`, `a_starter_minutes_consistency`
- Data source: NBA.com/stats/lineups/advanced (free), nba_api.stats.endpoints.LineupDetails
- Implementation: MEDIUM (need to compute Shannon entropy over minutes distribution per game)

### Cat 45: Opponent-Adjusted eFG% Differential (HIGH signal, extension of existing)
- Source: PMC 11265715 (XGBoost+SHAP NBA), feature_engineer memory notes "opponent-adjusted eFG%"
- Signal: SHAP analysis shows free-throw efficiency difference as top feature. eFG% adjusted for opponent defensive quality isolates true offensive skill vs schedule difficulty.
- Features: `h_opp_adj_efg_diff_5g`, `a_opp_adj_efg_diff_5g`, `h_def_efg_allowed_rank`, `a_def_efg_allowed_rank`, `efg_opp_adj_matchup_edge`
- Data source: Basketball-Reference.com (four factors table), NBA.com stats API
- Implementation: EASY (can compute from existing game logs + opponent context already in engine)

### Cat 46: Betting Market Signals — Line Movement & Sharp Action (POTENTIALLY HIGH signal)
- Source: Action Network, BetQL, Unabated.com — published research on CLV
- Signal: Reverse line movement (line moves against public) = sharp money signal. Over/under % vs money % divergence identifies steam moves. CLV (closing line value) is the gold standard for edge detection.
- Features: `line_open`, `line_close`, `line_move_direction`, `public_bet_pct`, `public_money_pct`, `sharp_action_indicator`, `steam_move_flag`, `implied_prob_home_close`
- Data source: The Odds API (free tier: 500 req/mo), OddsShark, ActionNetwork public data
- Implementation: HARD (requires real-time API integration, timing-sensitive, legal gray area in some contexts)
- NOTE: This is ORTHOGONAL to all current features — pure market signal

### Cat 47: Positional Matchup Advantages (MEDIUM signal, measurable via tracking)
- Source: JMP Community 2022 (Positional Matchup Model), OptimizeDefensiveMatchups ML paper
- Signal: Trae Young best defended by "smaller player with tremendous length" per ML model. Positional size/speed mismatches predictable from roster data.
- Features: `pg_height_matchup_delta`, `sg_height_matchup_delta`, `sf_height_matchup_delta`, `pf_weight_matchup_delta`, `positional_length_advantage_score`, `positional_speed_advantage_score`
- Data source: NBA.com player bio data (height/weight/wingspan), nba_api.stats.endpoints.CommonPlayerInfo
- Implementation: MEDIUM (need to match starting lineups to opposing positions)

### Cat 48: Load Management / Injury Risk Index (MEDIUM signal, widely used by sharp bettors)
- Source: CMU 2025 (Load Management paper), PMC 9340342 (ML lower extremity strain), Cohan et al. 2021
- Signal: Cumulative minutes in last 7/14/21 days predicts performance degradation better than raw rest days (per CMU 2025). Minutes management > rest days as predictor.
- Features: `h_star_minutes_7d`, `a_star_minutes_7d`, `h_cumulative_load_14d`, `a_cumulative_load_14d`, `h_injury_risk_index`, `a_injury_risk_index`, `h_days_rest`, `a_days_rest`, `b2b_flag`
- Data source: nba_api.stats.endpoints.PlayerGameLog (already used for box scores)
- Implementation: EASY (extend existing player-level aggregation, compute rolling minutes sums)

### Cat 49: Pace-of-Play Mismatch Index (MEDIUM signal, documented)
- Source: ESPN Hollinger pace stats, Basketball-Reference, PLOS ONE pace paper
- Signal: When a fast-paced team (top 5 in possessions/game) plays a slow team (bottom 5), the faster team tends to "win" the pace battle at home. Pace mismatch = variance inflator.
- Features: `pace_mismatch_abs`, `h_pace_rank`, `a_pace_rank`, `h_forced_pace_games_pct`, `a_slow_game_record`, `pace_control_home_advantage`
- Data source: NBA.com/stats API (TeamDashboardByTeamPerformance), already accessible
- Implementation: EASY (pace is already computable from existing possession data)

### Cat 50: Market Sentiment / Social Signals (LOW-MEDIUM signal, harder to validate)
- Source: ESPN Gambling Twitter piece, Oreate AI analysis, Reddit/Twitter public APIs
- Signal: When public massively backs a team (>70% of tickets), the market overprices them. "Fading the public" has documented but small edge (~2-3% over base rate per research).
- Features: `reddit_sentiment_score_3d`, `injury_report_news_count_24h`, `lineup_confirmation_flag`, `beat_reporter_tweet_sentiment`, `public_narrative_score`
- Data source: Reddit PRAW API (PENDING - user needs to create OAuth app), Twitter/X API v2 (costly)
- Implementation: HARD (requires OAuth, rate limits, NLP processing — but Reddit PRAW is partially built per MEMORY.md)

## LOWER PRIORITY / LONGER HORIZON

### Cat 51: Expected Shot Quality (xSQ) — Second Spectrum Style
- Source: arXiv 2405.10453 (EPAA Bayesian), ResearchGate deep network shot quality
- Signal: Shot quality separates good offense generating open looks vs lucky shooting. EPAA metric outperforms BPM in player evaluation.
- Features: `h_avg_shot_quality_score`, `a_avg_shot_quality_score`, `h_contested_shot_pct`, `a_open_shot_pct`, `xSQ_diff`
- Data source: ShotQuality.com (requires subscription), or compute from NBA tracking data (defender distance available via nba_api.stats.endpoints.ShotChartDetail)
- Implementation: MEDIUM-HARD (defender distance available free; xSQ requires computation)

### Cat 52: Coaching Tenure & System Stability
- Source: ESPN/Basketball-Reference coaching records
- Signal: New coaches in year 1-2 have higher variance outcomes. Teams in year 3+ of same system show more predictable patterns.
- Features: `h_coach_tenure_games`, `a_coach_tenure_games`, `h_system_stability_score`, `h_coaching_change_flag_season`
- Data source: Basketball-Reference coaching records (scrape)
- Implementation: EASY (static data, scrape once per season)

### Cat 53: 4th Quarter / Late-Game Specific Splits
- Source: Frontiers Psychology 2024 (Bayesian logistic Q4), MDPI clutch paper
- Signal: Some teams are consistently better/worse in 4th quarters independent of overall net rating. Predicts close game outcomes specifically.
- Features: `h_q4_net_rtg_20g`, `a_q4_net_rtg_20g`, `h_comeback_rate`, `a_lead_protection_rate`, `q4_net_diff`
- Data source: NBA.com Play-by-play API (free, via nba_api)
- Implementation: MEDIUM (need to parse PBP for quarter-level scoring)

### Cat 54: Player Health / Availability Index
- Source: ScienceDirect 2021 (NBA injury impact), Hilaris Publisher injury analytics
- Signal: Having all top-4 players available = baseline; each missing star reduces win probability by ~8-12% based on point differential research.
- Features: `h_availability_index`, `a_availability_index`, `h_missing_star_count`, `a_missing_star_count`, `h_impact_player_minutes_pct`, `availability_diff`
- Data source: NBA.com injury reports (free), nba_api injured players endpoint
- Implementation: EASY (nba_api already queries injury data; extend daily pipeline)

### Cat 55: Head-to-Head Historical Matchup Memory
- Source: Medium (Sam Iyer-Sequeira H2H simulations), logistic regression with matchup priors
- Signal: Some team pairs have systematic matchup advantages beyond current rating. E.g., teams with great rim protection vs. paint-heavy offenses.
- Features: `h2h_home_win_pct_5y`, `h2h_avg_margin_5y`, `h2h_last3_outcome_sum`, `h2h_home_comfort_score`
- Data source: Existing game logs in Supabase (already available)
- Implementation: EASY (can compute from existing historical data)

### Cat 56: Betting Closing Line Implied Probability
- Source: Unabated.com, BetQL
- Signal: The closing line represents the sharpest market signal available. Using it as a feature (implied probability) instead of as a target variable = meta-signal.
- Features: `implied_prob_home_close`, `implied_prob_home_open`, `line_move_magnitude`, `juice_implied_vig`
- Data source: OddsAPI free tier (500 req/mo) or historical from TheOddsAPI
- Implementation: MEDIUM (API integration, but data is already partially in live-odds.json)
- CAUTION: Risk of circular reasoning if odds already encode what model tries to predict. Use as secondary signal only.

## QUICK WINS (can implement in 1-4 hours each)

1. **Cat 39 — Circadian**: Days-since-timezone-crossing + altitude flag. Just need city → timezone table and schedule data. nba_api has LeagueSchedule. ~2h.
2. **Cat 43 — Clutch**: NBA.com/stats clutch API endpoint is free. Rolling 10-game clutch net rating per team. ~1h.
3. **Cat 41 — Transition**: NBA.com play-type API endpoint. Direct feature. ~1h.
4. **Cat 48 — Load**: Extend existing player game log aggregation to sum minutes over 7/14/21d windows. ~1h.
5. **Cat 55 — H2H**: Pure SQL/pandas from existing Supabase game logs. ~30 min.

## NOTES ON EXISTING ENGINE GAPS (from feature-engineer memory)

- ext_* features (~500): zero-padded, no compute path — fix these for free features
- meta2/meta3 (~160): hardcoded to 0.5/0.0 — OOF predictions at feature time is hard but high-value
- Bayesian game-level diffs Cat 32 (9 of 10 hardcoded to 0.0) — fix preseason_diff computation
- MOVDA parameters (GAMMA=648, DELTA=-646) — suspicious, validate before touching

## SOURCES

1. Chronobiology International 2024: https://www.tandfonline.com/doi/10.1080/07420528.2024.2325641
2. Belasen et al. 2025 (Referee betting): https://journals.sagepub.com/doi/10.1177/15270025251369447
3. arXiv 2405.10453 (EPAA shot quality): https://arxiv.org/abs/2405.10453
4. arXiv 2405.01182 (shot charts): https://arxiv.org/html/2405.01182v1
5. PMC 11265715 (XGBoost+SHAP NBA): https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/
6. MDPI Clutch Dynamics: https://www.mdpi.com/2504-4990/6/3/102
7. Frontiers Q4 Bayesian: https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2024.1383084/full
8. Nature stacked ensemble: https://www.nature.com/articles/s41598-025-13657-1
9. PMC referee bias: https://pmc.ncbi.nlm.nih.gov/articles/PMC10031197/
10. RefEye AI: https://refeye.ai/
