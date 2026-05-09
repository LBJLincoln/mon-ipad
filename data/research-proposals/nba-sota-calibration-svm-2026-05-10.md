# NBA SOTA Research Proposal — fire-73
**Date:** 2026-05-10 | **Cycle:** fire-73 | **Author:** cloud-brain-sonnet-4-6

## Summary
SOTA NBA prediction 2026: calibrated SVM achieves 0.7749 accuracy (IEEE 2026),
stacked ensemble with calibration-first strategy delivers +34.7% ROI vs accuracy-focused.
NFL Brier 0.185 benchmark achieved with proper probability calibration (SportBot AI 2025).

## Key Findings

### 1. Calibrated SVM — New MODEL_TYPE Candidate
**Source:** IEEE Conference 2026 — "Comparing Machine Learning Methods for NBA Game Outcome Prediction"
**Finding:** SVM achieves highest accuracy (0.7749) among all tested models, ahead of AutoGluon (0.7738) and DNN (0.7726).
**Mechanism:** SVM's maximum-margin hyperplane is robust to class imbalance in NBA home/away splits.
**Probability calibration:** Must pair SVM with Platt scaling (logistic regression on SVM outputs) or isotonic calibration for proper Brier optimization. Raw SVM scores are not calibrated probabilities.
**Action:** Add `svm_platt` and `svm_isotonic` to MODEL_TYPES pool alongside pending `logistic_regression` addition.
**Expected Brier gain:** -0.003 to -0.007 from current 0.22012 floor.
**VM priority:** Extend `vm-add-logistic-regression-model-pool` work-queue item to include SVM variants. S14 (stag=12) is highest urgency — needs new model types in mutation pool.

### 2. Stacked Ensemble (Scientific Reports 2025)
**Source:** "Stacked ensemble model for NBA game outcome prediction analysis" — Nature/Scientific Reports 2025
**Finding:** 7-model stack (NB + AdaBoost + MLP + KNN + XGB + DT + LR) outperforms any single model.
**Mechanism:** Blending probability estimates from diverse model families reduces systematic bias; no single algorithm dominates all game archetypes.
**Current status:** GA islands use single model types; stacking is disabled (CPU islands, Rule #8).
**Feasibility on CPU:** Stacking 2-3 lightweight models (LR + XGBoost) is tractable (<2s per evaluation on CPU). Full 7-model stack is not.
**Proposal:** Add `stacked_lr_xgb` (logistic regression meta-learner over XGBoost + extra_trees base models) as a new MODEL_TYPE.
**Priority:** MEDIUM — requires GA mutation/crossover changes to handle stack configuration genes.

### 3. Calibration-First Strategy (+34.7% ROI)
**Source:** SportBot AI 2025 — calibration vs accuracy-first comparison
**Finding:** Models prioritizing calibration (low ECE, flat reliability diagram) deliver +34.7% ROI vs -35.17% for accuracy-first.
**Current calibration coverage:**
- S15: Venn-Abers wrapper ✓ (fleet best 0.22012)
- S13, S18, S22: XGBoost without Venn-Abers ✗
**Action:** Add Venn-Abers post-hoc calibration wrapper to XGBoost islands — S13, S18, S22.
**Expected gain:** -0.001 to -0.003 Brier on those 3 islands.

### 4. Top SHAP Features — Engine Parity Check
**Source:** PMC — "Integration of machine learning XGBoost and SHAP models for NBA game outcome prediction"
**Top-3 features across all models:** `team_elo_5_y`, `team_elo`, `home_next`
**Status:** engine.py has 54 categories, 7213 raw features — Elo features should be present.
**VM verification commands:**
```bash
grep -n 'elo_5\|elo_5y\|elo.*5.*year' features/engine.py | head -10
grep -n 'home_next\|home_game\|is_home' features/engine.py | head -10
```
**If missing:** Add `team_elo_decay_ratio = team_elo_5y / (team_elo + 1e-6)` as a cross-feature capturing long-run vs short-run form divergence.

## Priority Action Matrix

| Priority | Action | Owner | Work-queue Item | Expected Brier Gain |
|----------|--------|-------|-----------------|---------------------|
| HIGH | Add `svm_platt` to MODEL_TYPES — S14 first (stag 12/15) | VM | vm-add-logistic-regression-model-pool (extend) | -0.003 to -0.007 |
| HIGH | Add `logistic_regression` to MODEL_TYPES (already queued) | VM | vm-add-logistic-regression-model-pool | -0.003 (LR+Elo fire-70) |
| MEDIUM | Venn-Abers calibration on S13/S18/S22 XGBoost islands | VM | new item needed | -0.001 to -0.003 |
| MEDIUM | Verify `team_elo_5_y` + `home_next` in engine.py | VM | engine-parity-sync (after sync) | diagnostic |
| LOW | `stacked_lr_xgb` meta-learner MODEL_TYPE | VM | new item needed | -0.005 estimated |

## Benchmarks
- **Current fleet best Brier:** 0.22012 (S15 random_forest, gen 1131)
- **Current Pareto best:** 0.21841 (S15 extra_trees gen=566)
- **S18 Pareto candidate:** 0.21956 (200-feature XGBoost, gen ~4200)
- **SOTA calibrated target:** 0.185 (NFL 2026 calibrated model — NBA harder, target 0.20)
- **Internal target:** 0.20

## Cross-Project: Political Alpha Analogs

The SVM calibration insight applies equally to political prediction:
- `svm_platt` in political MODEL_TYPES would complement existing lightgbm/xgboost
- Political outcomes are binary (win/lose) — same SVM margin geometry applies
- Calibration-first is especially important in political markets (polling error is systemic)
- Recommend adding to `vm-add-logistic-regression-model-pool` scope: include P7 political island

## References
- [IEEE 2026: Comparing ML Methods for NBA Prediction](https://ieeexplore.ieee.org/document/11030489/)
- [Scientific Reports 2025: Stacked ensemble for NBA](https://www.nature.com/articles/s41598-025-13657-1)
- [SportBot AI 2025: Calibration in AI sports betting](https://www.sportbotai.com/blog/calibration-ai-sports-betting-model-1775671361692)
- [PMC: XGBoost+SHAP for NBA prediction](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/)
- [MDPI 2026: ML for Basketball outcomes](https://www.mdpi.com/2079-3197/13/10/230)
