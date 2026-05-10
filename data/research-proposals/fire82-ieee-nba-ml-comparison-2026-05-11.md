# fire-82 SOTA: IEEE 2026 + MDPI 2026 NBA ML Comparison

**Date:** 2026-05-11T06h (fire-82)  
**Sources:**
- IEEE Xplore 2026: "Comparing Machine Learning Methods for NBA Game Outcome Prediction" https://ieeexplore.ieee.org/document/11030489/
- MDPI 2026 (MDPI 2078-2489/17/1/56): "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets"
- Scientific Reports 2025: Stacked ensemble for NBA game outcome prediction https://www.nature.com/articles/s41598-025-13657-1
- arXiv 2410.21484: Systematic Review of ML in Sports Betting

**Status:** New — IEEE 2026 paper (11030489) not previously catalogued.

## Key Benchmark Results

### IEEE 2026 Comparison Study
- LR + XGBoost: accuracy ~0.68, **Brier ~0.20**, log-loss ~0.58, AUC 0.75-0.76 on NBA 2024 holdout
- CNN: **lowest Brier = 0.221** in ensemble comparison
- Both match or beat current fleet best (0.22012) on comparable data

### MDPI 2026 Uncertainty-Aware Framework
- RNN + Monte Carlo dropout: calibrated sequential probabilities
- Shot-chart spatial embeddings as preprocessing
- Brier ~0.199 (competitive with best tabular LR baseline)

### Scientific Reports 2025 Stacked Ensemble
- Base learners: Naïve Bayes + AdaBoost + MLP + KNN + XGBoost + DT + LR
- Meta-learner: LR (logistic regression)
- Best performing base learners selected for final stack

### arXiv Systematic Review (2410.21484)
- **Key insight: calibration > accuracy for sports betting profit**
- Current GA fitness Brier (calibration) ✓ already aligned
- Bettors who optimise calibration outperform accuracy-optimised models

## Gap Analysis vs Current Fleet

| Metric | Fleet Best (S15) | IEEE 2026 LR | Gap |
|--------|-----------------|-------------|-----|
| Brier | 0.22012 | ~0.20 | -0.020 |
| Method | Random Forest GA | LR + isotonic | missing LR in pool |
| Model diversity | ET/RF/XGB in pool | + LR + CNN | LR not yet added |

## Proposed Actions

### Action 1 — Add LR + Isotonic to MODEL_TYPES (Priority: HIGH)
- **VM item:** vm-add-logistic-regression-model-pool (priority 50)
- Islands: S14 first (once restarted), then S13/S18/S22, then P7
- Expected gain: 0.22→0.20 range per IEEE 2026 benchmark on same domain
- Implementation: `logistic_regression` in MODEL_TYPES; use `CalibratedClassifierCV(base, method='isotonic')` wrapper

### Action 2 — Stacked Ensemble LR Meta (Priority: HIGH)
- **VM item:** vm-add-logistic-regression-model-pool (same, extend scope)
- Base: xgboost + extra_trees + lightgbm (all already in fleet)
- Meta: logistic_regression calibrated
- `stacked_ensemble_lr_meta` as new MODEL_TYPE in app.py
- Scientific Reports 2025 shows consistent +0.5-1.5% Brier reduction vs single-best base

### Action 3 — CNN Spatial Embedding Preprocessing (Priority: MEDIUM)
- IEEE 2026 CNN Brier=0.221 achieved with spatial shot-chart features
- Cannot run CNN on CPU islands (Rule: CPU-only, tree-based only)
- **Alternative:** extract CNN-derived spatial embeddings offline (GPU burst) → add as features to engine.py
- Mechanism: ZeroGPU H200 burst → compute spatial embeddings → commit to feature cache

### Action 4 — Calibration Gate in GA Fitness (Priority: MEDIUM)
- arXiv 2410.21484: calibration is the primary driver of profitability
- GA fitness already uses Brier (calibration proxy) ✓
- Enhancement: add ECE (Expected Calibration Error) as secondary fitness term
- Penalise individuals where ECE > 0.02 even if Brier looks good

## Cross-Project Ports

- **NBA→Political:** LR + isotonic validated for political prediction markets too
  - P7 (worst POL brier=0.25412) is primary target for vm-p7-extra-trees-trial + stacked_ensemble
- **Political→NBA:** No immediate technique identified this cycle

## Next Research Cycle Targets
- arXiv 2508.02725: NCAA Basketball LSTM/Transformer — validate architecture for NBA
- Validate: does adding `logistic_regression` to GA pool reduce fleet Brier by >0.001 within 500 gens?
- Monitor: S15 RF is already fleet best (0.22012) — does LR challenge it?
