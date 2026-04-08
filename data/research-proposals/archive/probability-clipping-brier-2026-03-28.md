# Research Proposal: Probability Clipping for Brier Score Improvement
**Date**: 2026-03-28  
**Cycle**: 2026-03-28-1220  
**Priority**: HIGH — direct Brier improvement, 0-code risk  
**Source**: MDPI 2026 (Uncertainty-Aware ML for NBA, Jan 2026) + MDPI Sports 2025

## Finding
Clipping predicted probabilities to `[0.025, 0.975]` before computing Brier score prevents single extreme-confidence wrong predictions from disproportionately penalizing the loss. Referenced in:
- *Uncertainty-Aware Machine Learning for NBA Forecasting* (MDPI Information 17(1):56, Jan 2026)
- March Madness competition practice (avoids one bad 5% pick destroying overall score)

## Current State
Our GA evaluates `brier_score_loss(y_true, y_pred)` where `y_pred` comes from `model.predict_proba()`. No clipping is applied. XGBoost/LightGBM can output probabilities near 0.0 or 1.0 especially early in training — these are high-variance predictions that inflate Brier.

## Proposed Change
In `hf-space/app.py`, in the `evaluate_individual` function where Brier score is computed:

```python
# BEFORE
proba = model.predict_proba(X_test)[:, 1]
brier = brier_score_loss(y_test, proba)

# AFTER — clip to [0.025, 0.975]
proba = model.predict_proba(X_test)[:, 1]
proba_clipped = np.clip(proba, 0.025, 0.975)
brier = brier_score_loss(y_test, proba_clipped)
```

## Expected Impact
- Direct Brier improvement: ~0.001-0.003 reduction (estimated from MDPI benchmark)
- Calibration methods (Beta, Venn-Abers) already reduce extreme probabilities but not fully
- Zero computational cost — single `np.clip` call
- Benchmark: LogReg with clipping achieves **Brier 0.199** on NBA data (MDPI 2025)

## Additional Technique: Logistic Regression Baseline
MDPI 2025 shows Logistic Regression outperforms XGBoost on Brier/log-loss in NBA prediction:
- LogReg: Brier 0.199, log-loss 0.583
- XGBoost: Brier 0.202 (but better ROI)

**Action**: Add `logistic_regression` as a model type in the GA chromosome. Use as calibration reference / ensemble member.

## Effort Estimate
- Probability clipping: 5 lines in app.py — immediate deploy to S10
- LogReg model type: ~20 lines in app.py model_type dispatch

## Priority Ranking
1. **Probability clipping** — deploy this cycle to S10 (S10 is exploitation island, lowest risk)
2. **LogReg model type** — add next cycle after clipping validated
3. **SHAP feature importance** — medium-term: use SHAP to prune low-importance features from 200-cap pool

## Cross-Project Note
Same clipping applies to Political Alpha. PA4 (best brier=0.25008) would benefit from the same 2-line change.
