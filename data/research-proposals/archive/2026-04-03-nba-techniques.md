# NBA Prediction Improvement Proposals — 2026-04-03

**Source:** 24/7 Brain cycle research (WebSearch, 2025-2026 literature)
**Priority:** Implement in order

---

## Proposal 1: Lineup-Weighted EPM Features (Low Risk, High Value)

**Technique:** Compute projected starting lineup net rating differentials using public EPM/LEBRON metrics, aggregated to the expected 5-man unit.

**Features to add to features/engine.py:**
- `lineup_epm_diff`: home starting-5 EPM sum minus away starting-5 EPM sum (from dunksandthrees.com/epm)
- `lineup_net_rtg_10g`: rolling 10-game net rating for each team's most-used 8-minute lineup unit
- `injury_adj_net_rtg`: reduce absent player's EPM from lineup total based on injury report
- `four_factors_efg_diff`, `four_factors_tov_diff`, `four_factors_orb_diff`, `four_factors_ftr_diff`: per-factor home/away differentials (not combined into single net rating)

**Why:** SHAP analysis (Scientific Reports 2025, PMC12357926) shows player-level efficiency is top predictor. Current team-level rolling averages conflate garbage-time with competitive lineups.

**Expected Brier reduction:** 0.003–0.007
**Risk:** Low — just new features, GA selector will prune unhelpful ones
**Implementation:** Add Cat52-LineupEPM category to features/engine.py (after v3.1-51cat)

---

## Proposal 2: Stratified Isotonic Calibration (Low Risk, High Calibration Value)

**Technique:** Post-hoc isotonic regression calibration stratified by game type, not global.

**Strata:**
- home_normal, home_b2b, away_normal, away_b2b, early_season (games 1-15)

**Implementation:**
```python
from sklearn.calibration import CalibratedClassifierCV
# Fit separate calibrators per stratum on held-out validation set
# Route each game at inference to correct calibrator
```

**Why:** Tree ensembles push probabilities toward 0/1 faster than warranted. NBA games are heteroscedastic — B2B games have different uncertainty distributions than normal games. Global Platt scaling misses this. (MDPI Computation 2025, TabPFN v2 analysis arxiv 2502.17361)

**Expected Brier reduction:** 0.003–0.008
**Risk:** Low — post-hoc, doesn't change model training
**Implementation:** Add to scripts/predict_today.py calibration step, and to HF space inference pipeline

---

## Proposal 3: MLP Meta-Learner Stacking (Medium Risk, Highest Potential)

**Technique:** Two-level stacking: base models (LGBM/CatBoost/ExtraTrees/RF) generate OOF predictions as features for a small MLP meta-learner.

**Why:** Scientific Reports 2025 NBA paper shows MLP meta-learner consistently outperforms any single model or naive averaging. CatBoost better at scheduling features; LightGBM better at rolling efficiency. Meta-learner learns when to trust which model.

**Expected Brier reduction:** 0.005–0.010
**Risk:** Medium — architectural change, requires CPU-safe MLP (no GPU on HF spaces)
**Note:** Use sklearn MLPClassifier (CPU-safe) or logistic regression as meta-learner. Keep base models unchanged.
**Implementation:** Add stacking layer to HF space evolution, evaluate on validation before deploying

---

## Cross-Project Port: Extra Trees for Political Fleet

**Observation:** NBA S12 (extra_trees specialist) achieves best fleet Brier at 0.22132 with stagnation=0. Current political fleet uses xgboost + catboost primarily.

**Action:** Add extra_trees specialist island to political fleet (PA-5 if resources allow). Same GA config as NBA S12: mut=0.08, target_feat=60.

---

## Engine Parity Fix Needed

**Issue:** mon-ipad features/engine.py = v3.1-46cat (6,696 lines) but nomos-nba-agent (HF space) = v3.1-51cat (6,841 lines, 145 lines newer)

**Action:** Sync mon-ipad/features/engine.py from nomos-nba-agent/features/engine.py. Do NOT reverse-sync (HF space is source of truth).
