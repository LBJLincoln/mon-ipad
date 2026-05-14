# fire-107 SOTA Research — Uncertainty-Aware Ensemble + LR Brier=0.199
**Date:** 2026-05-14T22:00:00Z | **Cycle:** fire-107 ODD | **Brain:** claude-sonnet-4-6

## Summary
Four independent confirmations of LR Brier=0.199 as CPU-tree baseline target. New 2026 uncertainty-aware RNN approach introduces MC dropout calibration as a novel direction.

## Papers

### 1. Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets
- **Source:** MDPI Information 17(1):56, Montrucchio et al., 2026
- **URL:** https://www.mdpi.com/2078-2489/17/1/56
- **Key result:** Logistic Regression Brier=0.199 (log-loss 0.583), XGBoost Brier=0.202. Uncertainty quantification via Monte Carlo dropout on RNN.
- **4th cycle reconfirmation** — extremely reliable benchmark target for fleet
- **Action:** `vm-add-logistic-regression-model-pool` (priority 50) = highest-priority new model

### 2. Stacked Ensemble Model for NBA Game Outcome Prediction
- **Source:** Scientific Reports s41598-025-13657-1, Nature 2025
- **URL:** https://www.nature.com/articles/s41598-025-13657-1
- **Key result:** Stacked ensemble: NaiveBayes + AdaBoost + MLP + KNN + LR + XGBoost base; LR meta. ~74-75% accuracy. Top features: rolling-form-5g, ELO, H2H-10, rest_days_diff, B2B_flag.
- **Action:** `vm-add-adaboost-naive-bayes-model-pool` (P56) after LR confirmed, then `vm-add-knn-small-feature-model-pool` (P70)

### 3. Forecasting NCAA Basketball Outcomes with Deep Learning
- **Source:** arXiv 2508.02725
- **Key result:** Deep RNN encoder with Monte Carlo dropout for uncertainty quantification. Achieves calibrated sequential probabilities. NCAA-focused but architecture transferable.
- **Action:** Research/tracking only — MC dropout calibration concept worth monitoring for post-GPU-burst experiments

### 4. Machine Learning for NBA and WNBA Game Outcomes (MDPI 2026)
- **Source:** MDPI Computation 13(10):230
- **URL:** https://www.mdpi.com/2079-3197/13/10/230
- **Key result:** SVM accuracy 0.7749 (best), AutoGluon 0.7738, DNN 0.7726. CNN Brier=0.221.
- **Action:** AutoGluon benchmark noted; CNN 0.221 confirms tree ensemble is competitive for CPU

## Fleet Context

### S15 Pending Candidate (fire-107 1st fire)
- CatBoost 200f Brier=0.21932 at gen=3050 in Pareto front
- Official best_brier still 0.22012 (field-lag pattern confirmed from fire-98)
- If confirmed at fire-108, this would be new fleet best (0.21932 < 0.22012)
- **Threshold test:** 0.21932 < 0.22085 checkpoint threshold — WOULD trigger checkpoint if confirmed

### POL LightGBM Dominance → NBA S22 Port
- P2 (cycle=16212): LightGBM 108f in-pop, 1%ROI — field-lag 6+ fires
- P4 (cycle=26104): LightGBM 108f in-pop, 1%ROI — COOLDOWN confirmed
- P7 (cycle=23130): model=lightgbm (best type), best_brier 0.25412 stuck
- S22 (NBA laggard 0.22551): extra_trees, has NEVER tried LightGBM
- **Recommendation:** `vm-add-lightgbm-s22-s13` = highest-confidence cross-port in fleet history

## Priority Stack (Post fire-107)
1. LR addition to all islands (SOTA LR=0.199 x4 confirmed)
2. LightGBM to S22 + verify S13 (cross-port from POL signal)
3. Stacking removal (Rule#8 — vm-remove-stacking-s13/s14/s15/s22)
4. AdaBoost + NaiveBayes after LR validated
5. KNN after AdaBoost/NB validated
