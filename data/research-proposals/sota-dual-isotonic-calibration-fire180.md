# SOTA Proposal: Dual Isotonic Calibration (arXiv:2510.17915) — fire-180

**Source:** arXiv:2510.17915 — "Uncertainty-Aware Post-Hoc Calibration: Mitigating Confidently Incorrect Predictions Beyond Calibration Metrics"  
**Discovered:** fire-180 EVEN WebSearch (2026-05-28T06h)  
**Work-queue priority:** 36 (after vm-add-ece-pareto-objective=34, before vm-add-win-diff-5game-feature=35)

## Key Finding
Standard isotonic regression treats all calibration samples equally — but confidently wrong predictions (high probability, wrong outcome) are systematically under-penalized. This paper proposes **dual isotonic calibration**:

1. **Stratify** calibration set into "putatively correct" (model confidence aligns with label) vs "putatively incorrect" (model overconfident on wrong outcome) using proximity-based conformal prediction
2. **Apply separate isotonic regression** models for each group
3. **Underconfidence-regularization** on the incorrect group to reduce overconfidence on hard cases

The method is post-hoc — no model retraining required. Evaluated on image classification (CIFAR-10/100) but approach is model-agnostic.

## Why Relevant to NBA Fleet
- **Our isotonic calibration** is already in production (Colab TabICL `isotonic-calibrated 0.22054`)
- S22 local-optimum convergence: API reports "identical Brier=0.2226, ROI=29.5%, Sharpe=9.00 each generation" — suggests calibration plateau, not feature saturation
- RF/ET models systematically overconfident on heavy-favorite upset games (tail risk)
- Dual stratification by confidence bucket mirrors our multi-objective Pareto philosophy
- ECE (Expected Calibration Error, fire-172 proposal, priority=34) will expose exactly this overconfidence pattern

## Implementation Plan
```python
# After engine-parity-sync, apply to S15 RF-75f / S22 RF-48f pareto models:

from sklearn.isotonic import IsotonicRegression
import numpy as np

# 1. Get calibration holdout predictions
proba_val = model.predict_proba(X_val)[:, 1]
correct_mask = (proba_val > 0.5) == y_val  # putatively correct

# 2. Fit separate isotonic regressors
iso_correct = IsotonicRegression(out_of_bounds='clip').fit(
    proba_val[correct_mask], y_val[correct_mask])
iso_incorrect = IsotonicRegression(out_of_bounds='clip').fit(
    proba_val[~correct_mask], y_val[~correct_mask])

# 3. Predict with confidence-based routing
def dual_isotonic_predict(proba):
    mask = proba > 0.5
    result = np.zeros_like(proba)
    if mask.any():
        result[mask] = iso_correct.predict(proba[mask])
    if (~mask).any():
        result[~mask] = iso_incorrect.predict(proba[~mask])
    return result
```

## Expected Improvement
- **Conservative:** 0.001-0.002 Brier over standard isotonic
- **Target:** Reduce tail overconfidence on ~20-30% upset games
- **Synergy:** Combine with ECE Pareto objective (fire-172, priority=34) for calibration-aware evolution
- **Caveat:** Paper evaluated on image classifiers; tabular proximity metric may differ (e.g., feature-space distance)

## Work-Queue Item
- `id: vm-add-dual-isotonic-calibration`
- `priority: 36`
- `owner: local-vm`
- Blocked by: engine-parity-sync (priority=40)
- Target: S15 RF-75f, S22 RF-48f, P1/P2/P5/P7 (post POL wake)
- Library: sklearn IsotonicRegression (already a dependency)
