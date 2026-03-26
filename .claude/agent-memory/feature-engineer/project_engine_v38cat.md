---
name: NBA Feature Engine v3.0-38cat state
description: Engine analysis, bugs found, and Cat 38 implementation (2026-03-26)
type: project
---

Engine upgraded from v3.0-35cat to v3.0-38cat on 2026-03-26.

**Why:** Added Cat 38 venue-conditional matchup features — 14 new features that compute (home team's home-only rolling stats) vs (away team's road-only rolling stats). These use the already-tracked `team_home_results` and `team_away_results` dicts which were never directly compared against each other in the existing categories.

**New features:** `venue_wp_edge_{5,10,20}`, `venue_margin_edge_{5,10,20}`, `venue_ortg_edge_{5,10,20}`, `venue_drtg_edge_{5,10,20}`, `venue_home_boost`, `venue_road_penalty`. Total: 6135 → 6149.

**How to apply:** When proposing more features, note that home/away splits are already computed (lines ~4886-4902 in build()). The new Cat 38 adds venue-specific MATCHUP comparisons on top of the per-team split stats.

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
