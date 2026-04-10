---
name: NBA Feature Engine current state
description: Engine v3.1-54cat: 6312 features, architecture facts (updated 2026-04-05)
type: project
---

Engine is at v3.1-54cat on 2026-04-05. Previous: v3.1-51cat (6257 features).

**Why:** Added 3 new odds-derived categories (52, 53, 54) using the historical odds CSV.

**How to apply:** When proposing more features, check what's already in the 54 categories listed below before adding new ones.

## Current Category List (v3.1-54cat)

- Cat 1-15: Core stats (rolling perf, four factors, pace, scoring, momentum, rest, opp-adj, H2H, market, context, ref, player, quarter, def-matchup, polymarket)
- Cat 16-35: Advanced expansion (interactions, EWMA, season trajectory, lineup, game theory, environmental, cross-window momentum, market II, power ratings, fatigue, player impact, referee, venue, market III, time series, cross-team matrix, Bayesian, network, ensemble, temporal decay)
- Cat 37: MOVDA ELO (margin-of-victory deviation analysis)
- Cat 38: Venue-conditional matchup features (home-only vs road-only stats)
- Cat 39: Circadian Rhythm & Travel Fatigue (8 features)
- Cat 41: Transition vs Half-Court Efficiency (7 features)
- Cat 43: Clutch Performance (8 features, 30-game window)
- Cat 44: Game Totals Prediction (10 features)
- Cat 46: Real Odds Market Features (8 features, Cat46 — implied prob, fair prob, spread/total/overround)
- Cat 47: Drive-Offense vs Rim-Defense Matchup (14 features, from tracking_data)
- Cat 48: Passing Network Quality (10 features, from tracking_data)
- Cat 49: Play-Type Efficiency (10 features, from tracking_data)
- Cat 50: Temporal Win Sequence Encoding (12 features)
- Cat 51: Season Era Normalization (8 features, z-score vs league running avg)
- **Cat 52 (NEW 2026-04-05):** Odds Line Features (15 features) — spread magnitude, total line, vig, season percentiles, ML-implied spread vs actual gap, sharpness
- **Cat 53 (NEW 2026-04-05):** ATS Record Features (12 features) — cover rate last 10/season, ATS streaks, as-fav/as-dog splits, home-only ATS, margin vs spread rolling avg
- **Cat 54 (NEW 2026-04-05):** Over/Under Record Features (12 features) — over rate last 10/season, O/U streaks, pace vs total line, home/road O/U splits, margin vs total rolling avg

## Cat 52-54 Implementation Details

**State trackers** (in build() method):
- `_team_ats`: per-team list of (gd, covered_ats, spread_home, is_home_game, margin_vs_spread). Populated AFTER feature extraction to prevent lookahead.
- `_team_ou`: per-team list of (gd, went_over, total, is_home_game, margin_vs_total). Populated after feature extraction.
- `_season_spreads`: rolling list of abs(spread_home) values for percentile features.
- `_season_totals`: rolling list of total line values for percentile features.

**ATS cover formula:** `h_covered = actual_margin > -spread_home` (spread_home is negative when home is favored)

**O/U formula:** `went_over = (hs + as_) > total_line`

## Key architecture facts

- `ha_*` features (home/away split by window) ARE properly computed. Not zero-padded.
- Evolution engine subsamples features for speed. MAX_FEATURES=200 hard cap.
- Best result: Brier 0.21570 (Colab TabICL, 110f, iter 15).
- MOVDA-era best on active spaces: 0.22041 (S10, xgboost, gen 435).
- All new cats use try/except so failures never crash the engine.
- Engine parity rule: always cp features/engine.py to hf-space/features/engine.py and verify sha256sum.
- SHA256 both files: 857e234dc908b66b53b54f2934101cc69af3df8224001929af583225f04c9836 (2026-04-05)
- MOVDA parameters: GAMMA=648.0334, DELTA=-645.8717 — do NOT change without validation.

## Known zero-padded / placeholder feature sets

- ext_* features (~500): Declared in feature names but no compute path.
- meta2/meta3 ensemble features (~160): Hardcoded to 0.5/0.0. Require OOF predictions.
- Bayesian game-level diffs (Cat 32): 9 of 10 features hardcoded to 0.0.
- Player tracking features (Cat 47-49): Fallback to league-average defaults when tracking_data=None.

## Historical session notes

**Cat 37 extension:** 7 raw delta_MOV rolling features. `_update_movda()` accepts `delta_mov_history` as positional arg.

**Cat 38:** Venue-conditional matchup, 14 features.

**Cat 39:** Circadian Rhythm, 8 normalized composite features. Distinct from Cat 6 raw values.

**Cat 41:** Transition vs Half-Court Efficiency, 7 features from existing fb_pts/pace stats.

**Cat 43:** Clutch Performance, 8 features from 30-game window close games.

**Cat 44:** Game Totals Prediction, 10 features normalized to league averages.

**Totals model:** `/home/lahargnedebartoli/mon-ipad/scripts/totals_model.py` RMSE 18.56 pts vs market 17.73.

**Beta calibration:** Added `beta` as 4th calibration option in `hf-space/app.py`. Initial weights [25,15,30,30].
