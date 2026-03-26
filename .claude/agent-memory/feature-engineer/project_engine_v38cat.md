---
name: NBA Feature Engine v3.0-38cat state
description: Engine analysis, bugs found, Cat 38 + delta_MOV + beta cal implementation (2026-03-26)
type: project
---

Engine is at v3.0-38cat on 2026-03-26.

**Cat 38 (prior session):** Added venue-conditional matchup features — 14 new features comparing home team's home-only stats vs away team's road-only stats. `venue_wp_edge_{5,10,20}`, `venue_margin_edge_{5,10,20}`, `venue_ortg_edge_{5,10,20}`, `venue_drtg_edge_{5,10,20}`, `venue_home_boost`, `venue_road_penalty`. 6135 → 6149.

**Cat 37 extension (this session):** Added 7 raw delta_MOV rolling features without EWM smoothing. Cat 37 grew from 6 to 13 features. 6149 → 6142 (NOTE: prior session count 6149 was stale; confirmed new count = 6135 + 7 = 6142). Features: `h/a_delta_mov_raw`, `h/a_delta_mov_rolling_5`, `h/a_delta_mov_rolling_10`, `delta_mov_diff`. `_update_movda()` now also accepts `delta_mov_history` (new positional arg between `mov_surprise_ewm` and `K`). Both call sites updated.

**Beta calibration (this session):** Added `beta` as 4th calibration option in `hf-space/app.py`. Initial weights: [25,15,30,30] for [none,sigmoid,venn_abers,beta]. Mutation weights: [50,15,15,20]. Uses `BetaCalibration(parameters='abm')` from `betacal` package (added to requirements.txt). Fits on last 200 training samples; `_model_fitted` flag prevents double-fit. Expected -0.003 Brier per arXiv.

**How to apply:** When proposing more features, note that home/away splits are already computed (lines ~4886-4902 in build()). `delta_mov_history` is a per-team list of raw delta_MOV values (appended AFTER features are read, so no lookahead). Next feature ideas: fix MOVDA parameters, add opponent-adjusted eFG% differential.

## Bugs found but NOT yet fixed

1. **MOVDA parameters look suspicious but may be correct**: `GAMMA=648.0334, DELTA=-645.8717`. These sum to ~2.16 (neutral game home court baseline). The tanh curve with `ALPHA=19.25, BETA=0.002342` gives reasonable MOV predictions for large Elo gaps. Do NOT change without running parameter validation first.

2. **ext_* features (~500)**: Declared in feature names as `ext_{prefix}_{stat}_{w}` but no compute path exists for stats like `net_rating`, `ast_to_tov`, `efg_minus_opp_efg`. These are zero-padded. The GA ignores them after a few generations.

3. **meta2/meta3 ensemble features (~160)**: Hardcoded to 0.5/0.0. Require OOF predictions which can't be computed at feature engineering time.

4. **Bayesian game-level diffs (Cat 32)**: Lines ~4048-4056 — 9 of 10 features hardcoded to 0.0. Only preseason_diff computed.

## Key architecture facts

- `ha_*` features (home/away split by window) ARE properly computed at lines ~4886-4902. Not zero-padded.
- Evolution engine subsamples ~999 features from 6149 for speed. MAX_FEATURES=200 hard cap.
- Best result: 0.21867 extra_trees 74 features (pre-MOVDA era on v3.0-35cat-pre-unification).
- MOVDA-era best on active spaces: 0.22041 (S10, xgboost, gen 435).
