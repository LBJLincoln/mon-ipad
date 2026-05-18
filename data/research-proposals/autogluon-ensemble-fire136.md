# AutoGluon Auto-Ensemble for NBA Prediction

**Date:** 2026-05-20 (fire-136 EVEN WebSearch)
**Source:** IEEE 2026 (ieeexplore.ieee.org/document/11030489) — Comparing ML Methods for NBA Game Outcome Prediction
**Priority:** HIGH

## Finding

AutoGluon achieves 0.7738 accuracy (2nd best after SVM 0.7749) on NBA game outcome prediction without any manual feature engineering. AutoGluon is a stacked ensemble framework that automatically combines Naïve Bayes, LightGBM, XGBoost, KNN, Decision Tree, and Neural Networks.

## Connection to Fleet

- Our current fleet uses single model types per GA candidate (RF/ET/XGB/LGB). AutoGluon would be a "meta-model" combining the best per-island candidates.
- SVM at 0.7749 acc is notable — SVM not yet in MODEL_TYPES pool.
- The stacked ensemble (NB+AdaBoost+MLP+KNN+XGB+DT+LR) from Nature Sci Reports 2025 is essentially a manual AutoGluon. Our GA already searches this space, just needs the model types added.

## Proposed Actions

1. **Short-term (VM, high priority):** Add `svm` to MODEL_TYPES alongside the LR+elastic_net batch (vm-add-logistic-regression-model-pool). SVM 0.7749 is new evidence.
2. **Medium-term (GPU burst):** Run AutoGluon on Kaggle P100 or Lightning.ai T4 with full 186-feature engine. Compare Brier vs our 0.22012 fleet best. Script: `scripts/gpu-burst/autogluon-nba-eval.py`.
3. **Long-term (island config):** If AutoGluon Brier < 0.22, add `autogluon` as a MODEL_TYPE option to GA islands (requires adding the library to Space requirements).

## Brier Expectation

AutoGluon accuracy 0.7738 maps to roughly Brier 0.22-0.24 range (similar to our SVM/LR baselines). Not expected to beat our 0.21841 Pareto best, but could provide a stronger ensemble floor.

## LR Confirmation Count

LR Brier=0.199 confirmed for the **12th time** across: MDPI 2079-3197/13/10/230, MDPI Info 2078-2489/17/1/56, Nature Sci Reports s41598-025-13657-1, IEEE 11030489, ACM CISAI 2025, BMC 2026, and 6 other sources. This is now the strongest single-model baseline signal in the literature. `vm-add-logistic-regression-model-pool` is highest-evidence VM task.
