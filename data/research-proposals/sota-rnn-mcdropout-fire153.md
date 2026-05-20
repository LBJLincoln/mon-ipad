# Research Proposal: Bootstrap Uncertainty Estimation for CPU Tree Ensembles

**Fire:** 153 | **Date:** 2026-05-23 | **Priority:** Medium | **Track:** EVEN WebSearch SOTA
**Source:** MDPI Information 2026 — "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets" (18th confirm of RNN+MC-dropout approach)

## Problem

The MDPI 2026 paper achieves Brier ~0.20 using RNN + Monte Carlo dropout for uncertainty-aware NBA forecasting. Our fleet best is 0.22012 (S15 RF-75f). The gap (~0.02 Brier) may be partially attributable to:
1. Temporal modeling (RNN captures sequential game patterns)
2. Uncertainty quantification (calibrated confidence intervals improve Kelly sizing)
3. Dropout regularization (reduces overfitting on small feature sets)

However, RNN/neural nets are banned on CPU islands (Rule #8). We need a tree-ensemble approximation.

## Proposed Technique: Bootstrap Variance Calibration (BVC)

Approximate MC-dropout uncertainty for scikit-learn Random Forests using existing bootstrap structure:

```python
# RF already trains on bootstrap samples — use prediction variance across estimators
probs = np.array([tree.predict_proba(X)[:, 1] for tree in rf.estimators_])
mean_prob = probs.mean(axis=0)
uncertainty = probs.std(axis=0)  # epistemic uncertainty proxy

# Calibrate: high-uncertainty predictions → shrink toward 0.5
calibrated = mean_prob * (1 - alpha * uncertainty) + 0.5 * alpha * uncertainty
# alpha ~ 0.3-0.5 tuned on validation set
```

**Why this works:** RF's bootstrap ensembling is mathematically equivalent to approximate Bayesian inference (ICLR 2017, Lakshminarayanan). The variance across trees IS the uncertainty estimate — no neural net needed.

## Implementation Plan

1. **Post-processing wrapper** (zero island changes needed):
   - Add `uncertainty_calibration_wrapper.py` to features/
   - Input: fitted RF model + validation X/y
   - Output: calibrated probabilities + uncertainty scores
   - Test: check if calibrated Brier < raw Brier on S15 RF-75f holdout

2. **Kelly sizing integration** (trading floor):
   - High-uncertainty games → reduced stake (multiply Kelly by (1 - uncertainty))
   - Expected effect: fewer confident wrong bets → improved Sharpe

3. **Feature-level uncertainty**:
   - Track which features have highest prediction variance
   - Use as SHAP proxy to identify unreliable feature categories
   - Feeds into engine-parity-sync priority (what features add noise vs signal)

## Expected Impact

- Brier improvement: 0.001-0.005 (calibration typically helps 0.5-2%)
- Sharpe improvement: higher (Kelly bet-sizing with uncertainty should reduce drawdowns)
- Validation: compare S15 calibrated Brier vs raw 0.22012 on held-out 2025-26 games

## Evidence Base

1. MDPI Info 2026: RNN+MC-dropout NBA Brier ~0.20 (18th confirm across fire-100→153)
2. ICLR 2017 Lakshminarayanan: "Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles" (tree analogy valid)
3. S15 RF-75f: 2156 cycles stable — ideal candidate for calibration wrapper experiment
4. S22 RF-48f: pareto=10 recovering from 17-peak — 2nd test candidate

## Status

- [ ] Implement uncertainty_calibration_wrapper.py
- [ ] Test on S15 RF-75f validation data (fire-153 checkpoint)
- [ ] If Brier improves → add to all RF islands (S15, S18, S22)
- [ ] Port to POL RF islands if applicable

**Blocking:** vm-checkpoint-s15 (need the model weights). Priority AFTER checkpoints.
