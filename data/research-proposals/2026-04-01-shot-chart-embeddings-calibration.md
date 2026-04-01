# Research Proposal: Shot-Chart Spatial Embeddings + Isotonic Calibration

**Date:** 2026-04-01  
**Source:** MDPI Information Jan 2026 - "Uncertainty-Aware Machine Learning for NBA Forecasting"  
**Priority:** HIGH  
**Target Metric:** Brier < 0.21837 (current best: 0.22066)

## Summary

Recent 2026 research achieves Brier 0.199 using a unified framework combining:
1. PCA-refined spatial shot-chart embeddings
2. Monte Carlo Dropout RNN for uncertainty quantification  
3. CalibratedClassifierCV with automatic method selection

## Proposed Changes to features/engine.py

### 1. Shot Zone Efficiency Features (NEW)
Add shot zone proportions and efficiency by court region:
- Corner 3 rate vs wing 3 rate vs mid-range rate (home/away)
- Paint points per possession
- 3-point attempt rate in last N games (rolling)
- Opponent allowed corner 3 rate

These add ~30 features and represent the spatial distribution captured by shot charts without needing actual chart images.

### 2. Isotonic Calibration Post-Processing
After GA selects best model, apply `CalibratedClassifierCV` with:
- method='isotonic' for tree models (RF, XGBoost, CatBoost)  
- method='sigmoid' for linear/logistic
- CV=5, evaluate both and pick lower Brier

Expected improvement: 0.003-0.008 Brier score reduction based on paper benchmarks.

### 3. ECE/MCE Calibration Metrics in Fitness
Add Expected Calibration Error to the GA fitness function alongside Brier:
```python
composite = 0.7 * brier + 0.2 * ece + 0.1 * (1 / (1 + sharpe))
```
This guides GA toward better-calibrated models.

### 4. Monte Carlo Dropout Ensemble (ADVANCED)
Replace single model with 30-sample MC-dropout ensemble:
- Run inference 30x with dropout enabled
- Use mean prediction + std as uncertainty estimate
- Filter low-confidence predictions from betting signals

## Implementation Steps
1. Add shot zone features to `NBAFeatureEngine._build_feature_names()` (est. +30 features)
2. Add `CalibratedClassifierCV` wrapper in model training pipeline
3. Add ECE computation to fitness evaluation
4. Validate on holdout set: target Brier improvement of 0.002+

## Expected Outcome
- Brier: 0.22066 → ~0.218 (approaching threshold)
- Better calibrated probabilities → higher Sharpe
- 30 new shot-zone features for GA to select from

## References
- [MDPI Information 2026](https://www.mdpi.com/2078-2489/17/1/56)
- [Nature Scientific Reports 2025](https://www.nature.com/articles/s41598-025-13657-1)
