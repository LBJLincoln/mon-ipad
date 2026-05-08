# Research Proposal: Extra Trees Injection for Political Islands

**ID:** extra_trees_pol_injection_fire66  
**Fire:** 66 | **Rotation:** B (political_engine.py review)  
**Date:** 2026-05-09T02:00:00Z  
**Estimated Brier delta:** -0.003  
**Status:** BLOCKED on pol-engine-placeholder VM fix

## Finding

S15 (Nomos42/nba-evo-6) achieved a new fleet Pareto alltime best of **0.21841** using `extra_trees` at gen=566 (Sharpe 10.55, ROI 34.5%). This beats the previous alltime Pareto best of 0.21850 (S22 CatBoost gen=2309).

All 5 POL islands currently run `xgboost_brier` or `lightgbm` as dominant model types. None explicitly seeds `extra_trees` individuals at high frequency.

## NBA→Political Cross-Port

S15's extra_trees success is not an accident — extra trees has lower variance than random forests and performs well on datasets with correlated features (which political features are: FEC, poll, market, congressional vote data all correlate).

### Proposed change (after pol-engine-placeholder fix):
1. In `hf-space/app.py` for P1/P2 (Nomos42 islands), increase `extra_trees` seeding probability from default ~5% to **25%** in the `_MODEL_TYPE_WEIGHTS` init distribution.
2. Set `extra_trees` preferred mutation weight to 0.20 for the next 200 generations.
3. Monitor P1/P2 Pareto front for improvement — if top Pareto member switches to extra_trees, propagate to P4/P5/P7.

## Related SOTA (fire-66 search)

- **Nature s41598-025-13657-1**: Stacked ensemble (NB+AdaBoost+MLP+KNN+XGB+DT+LR) NBA prediction — best base learner combination beats single-model XGBoost by ~0.004 Brier. Political analog: stacking extra_trees + lightgbm could close ~0.003 gap.
- **IEEE 11030489**: CNN achieves Brier 0.221 on NBA — we beat with S15 official 0.22012. Confirms tree ensemble competitive without neural overhead.
- **PMC 11265715**: XGBoost + SHAP feature importance analysis — suggests top 50-100 features dominate. Political islands already run 71-72 features per best models, aligned with this.

## Root Cause: Data Starvation

POL plateau at 0.249-0.254 is primarily caused by **data starvation** (272 feature candidates vs NBA 3377 — 12x deficit). Extra trees injection is secondary — the primary lever is:
1. VM restart of `fetch_political_data.py` + `insider_tracker.py` crons (40d+ stale)
2. This alone expected to add +50 feature candidates → est. -0.005 Brier

Extra trees injection provides incremental gain on top, not a substitute.
