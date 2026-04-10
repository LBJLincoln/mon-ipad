---
name: NBA Feature Engine v3.0-43cat state
description: Engine analysis, Cat 38-44 additions, architecture facts (updated 2026-03-28)
type: project
---

Engine is at v3.0-43cat on 2026-03-28.

**Cat 38 (prior session):** Added venue-conditional matchup features — 14 new features comparing home team's home-only stats vs away team's road-only stats. `venue_wp_edge_{5,10,20}`, `venue_margin_edge_{5,10,20}`, `venue_ortg_edge_{5,10,20}`, `venue_drtg_edge_{5,10,20}`, `venue_home_boost`, `venue_road_penalty`.

**Cat 37 extension (prior session):** Added 7 raw delta_MOV rolling features. `h/a_delta_mov_raw`, `h/a_delta_mov_rolling_5`, `h/a_delta_mov_rolling_10`, `delta_mov_diff`. `_update_movda()` accepts `delta_mov_history` (positional arg between `mov_surprise_ewm` and `K`).

**Cat 39 (2026-03-28):** Circadian Rhythm & Travel Fatigue — 8 normalized composite features. `circ_h/a_travel_dist` (dist/500 normalized), `circ_h/a_tz_shift`, `circ_h/a_fatigue_index` (= dist/500 + tz*0.5 + b2b*2 - min(rest,4)*0.3), `circ_advantage` (away - home fatigue), `circ_rest_nonlinear` (sqrt(h_rest) - sqrt(a_rest)). DISTINCT from Cat 6 raw values. Uses existing `_travel_dist`, `TIMEZONE_ET`, `haversine`.

**Cat 41 (2026-03-28):** Transition vs Half-Court Efficiency — 7 features. `trans41_h/a_fb_rate` (fb_pts/ppg), `trans41_h/a_halfcourt_eff` ((ppg*(1-fb_rate))/pace*100), `trans41_fb_rate_diff`, `trans41_pace_x_fb` (pace/100 * fb_rate), `trans41_halfcourt_edge`. All computed from existing `fb_pts`, `pace` stats — no external API.

**Cat 43 (2026-03-28):** Clutch Performance — 8 features. Filters last 30 records where |margin| <= 5. `clutch43_h/a_wp`, `clutch43_h/a_margin` (/10 normalized), `clutch43_h/a_ortg` ((ortg-100)/20 normalized), `clutch43_wp_diff`, `clutch43_margin_diff`. 30-game window (vs Cat 5's 10-game _clutch_wp). Adds margin + ortg breakdowns.

**Cat 44 (2026-03-28):** Game Totals Prediction — 10 features. Encodes expected scoring environment normalized to league averages. `tot44_h/a_ppg10` (PPG/110), `tot44_h/a_papg10` (PAPG/110), `tot44_matchup_total` ((H_PPG + A_PAP + A_PPG + H_PAP) / 2 / 220), `tot44_pace_sum` (avg_pace/97), `tot44_pace_mismatch` (|h_pace - a_pace|/10), `tot44_ortg_sum` and `tot44_drtg_sum` (combined ratings/220), `tot44_score_env` ((ortg_sum - drtg_sum)/20). All derived from existing rolling stats — no new data source.

**Totals model (2026-03-28):** `/home/lahargnedebartoli/mon-ipad/scripts/totals_model.py` — standalone O/U predictor. RMSE 18.56 pts vs market 17.73 pts. NBA O/U market is highly efficient; no standalone betting edge above vig. Primary use: injury-adjusted prediction and as source of Cat44 features for moneyline model.

**Current total features: 5869** (was 5859 before this session). +10 new features.

**Beta calibration (prior session):** Added `beta` as 4th calibration option in `hf-space/app.py`. Initial weights: [25,15,30,30] for [none,sigmoid,venn_abers,beta].

**How to apply:** When proposing more features, note that home/away splits are already computed. `delta_mov_history` is a per-team list. Next feature ideas: opponent-adjusted eFG% differential, 4th-quarter-only stats, lineup continuity metrics.

## Bugs found but NOT yet fixed

1. **MOVDA parameters look suspicious but may be correct**: `GAMMA=648.0334, DELTA=-645.8717`. Do NOT change without validation.

2. **ext_* features (~500)**: Declared in feature names but no compute path. These are zero-padded. GA ignores them.

3. **meta2/meta3 ensemble features (~160)**: Hardcoded to 0.5/0.0. Require OOF predictions.

4. **Bayesian game-level diffs (Cat 32)**: 9 of 10 features hardcoded to 0.0.

## Key architecture facts

- `ha_*` features (home/away split by window) ARE properly computed. Not zero-padded.
- Evolution engine subsamples features for speed. MAX_FEATURES=200 hard cap.
- Best result: Brier 0.21570 (Colab TabICL, 110f, iter 15).
- MOVDA-era best on active spaces: 0.22041 (S10, xgboost, gen 435).
- New cats 39/41/43/44 use try/except so failures never crash the engine.
- Engine parity rule: always cp features/engine.py to hf-space/features/engine.py and verify sha256sum.
- Cat44 default values on exception: [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0] (normalized to league avg, mismatch=0).
