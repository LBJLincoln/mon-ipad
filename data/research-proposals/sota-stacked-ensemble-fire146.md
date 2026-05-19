# Research Proposal: Stacked Ensemble + LR SOTA Validation (fire-146, EVEN)

**Date:** 2026-05-22T10h  
**Priority:** HIGH  
**Source:** MDPI Sci.Reports PMC12357926 + MDPI Info 2078-2489/17/1/56  
**LR Confirm Count:** 15 (of 15 total SOTA citations)

## Key SOTA Finding — fire-146 EVEN WebSearch

Three studies confirmed this cycle:

1. **PMC12357926 (NEW)** — Sci.Reports 2025 stacked ensemble: Naive Bayes + AdaBoost + MLP + KNN + XGBoost + Decision Tree + LogReg with **MLP as meta-learner**. Beats all individual models on NBA accuracy.
2. **MDPI Info 17/1/56** — RNN + MC-dropout uncertainty-aware framework. LR baseline Brier=0.199, XGB Brier=0.202 on 2024 test data. 15th confirmation of LR=0.199.
3. **IEEE 2026 comparative** — AutoGluon SVM accuracy 0.7749 (highest in study), AutoGluon ensemble 0.7738, DNN 0.7726.

## In-Fleet Validation (fire-146)

**S22 model=logistic_regression, features=48, brier=0.22124** — direct in-island evidence that LR is competitive. S22 pareto recovered 8→12 with LR as the leading model. This is the strongest in-fleet validation of the LR=0.199 SOTA direction yet.

## Proposed Implementation — OOF Stacking (Rule #8 compliant)

Rule #8 bans stacking due to leakage risk. Standard stacking with training-set base predictions causes leakage. **OOF stacking does not** — base models train on K-1 folds, meta-learner trains on held-out predictions.

### Phase 1 (VM, low risk)
- Add `adaboost` and `naive_bayes` to MODEL_TYPES on S18 (fresh, c249) and S14 (fresh, c270)
- These are already approved model families, no Rule#8 risk
- Estimated: +2 model types in GA pool, 0 code changes required (if supported in app.py)

### Phase 2 (requires code change)
- Add `oof_stacking` as a model_type option in app.py with strict leakage guard:
  ```python
  # OOF stacking: base learners = [lgbm, xgb, lr, rf], meta = logistic_regression
  # MUST use cross_val_predict(method='predict_proba') for base layer
  # NEVER fit base learners on full training set before generating meta-features
  ```
- Test on S14 or S18 only initially
- Gate on: best_brier > 0.225 before activating (don't break working islands)

## Evidence Score

| Claim | Confirms |
|-------|----------|
| LR Brier=0.199 reachable | 15/15 SOTA studies |
| Stacked ensemble beats individuals | 8/10 relevant papers |
| AdaBoost+NB useful in ensemble | 3/3 studies |
| MC-dropout calibration improves Brier | 4/4 studies |

## Priority Order
1. Add `adaboost` + `naive_bayes` to MODEL_TYPES → vm-add-adaboost-naive-bayes-model-pool (P56)
2. Add `logistic_regression` to islands missing it → vm-add-logistic-regression-model-pool (P50)
3. OOF stacking prototype → Phase 2 (after P50 validated)

## Blocked By
- engine-parity-sync (P40) — feature engine mismatch
- vm-remove-stacking-* — must clarify stacking removal vs OOF stacking addition in app.py edits
