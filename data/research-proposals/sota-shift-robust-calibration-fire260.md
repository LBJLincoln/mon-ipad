# SOTA Research Proposal: Shift-Robust Calibrated Prediction for NBA Distribution Shift

**Source:** arXiv:2603.06733 (Mar 2026) — "Calibrated Credit Intelligence: Shift-Robust and Fair Risk Scoring with Bayesian Uncertainty and Gradient Boosting"  
**Priority:** 120  
**Fire:** 260 (EVEN WebSearch)  
**Date:** 2026-06-03

## Key Findings

The paper introduces a three-layer calibration pipeline for high-stakes predictions under distribution shift:

1. **Bayesian neural risk scorer** — captures epistemic uncertainty (what the model doesn't know)
2. **Fairness-constrained gradient boosting** — strong tabular performance while controlling group disparities
3. **Shift-aware fusion + post-hoc probability calibration** — adapts to distribution shift between training and deployment

Core insight: A "shift-aware fusion strategy" reweights model components based on detected distribution drift, then applies post-hoc calibration to stabilize decision thresholds. This reduces calibration error by ~15-30% under temporal distribution shift vs. static isotonic calibration.

## Application to NBA Prediction

NBA prediction has strong seasonal distribution shift:
- Team rosters change every offseason
- Coaching strategies evolve season-by-season
- Game pace and play style drift year-over-year
- Our current isotonic calibrator doesn't account for this drift

### Application 1: Shift-Aware Multi-Island Fusion
Replace the current rank-based fusion in `predict_today.py` with a shift-aware fusion:
```python
def shift_aware_fusion(predictions_by_island, shift_weights):
    """Weight island predictions by inverse distribution shift magnitude."""
    # drift_score = KL divergence between island's training distribution and current games
    # lower drift → higher fusion weight
    weights = softmax([-drift_score(island) for island in islands])
    return np.average(predictions_by_island, weights=weights)
```

### Application 2: Add shift_calibration_metrics to /api/export
Track calibration error per season-phase × team-tier subgroup:
```python
shift_calibration_metrics = {
    "early_season_ece": 0.023,
    "mid_season_ece": 0.018,
    "playoffs_ece": 0.031,
    "back_to_back_ece": 0.028,
    "drift_magnitude": 0.041  # KL div current vs training
}
```

### Application 3: Bayesian Ensemble for S18/S22
Add MC dropout or deep ensemble uncertainty to ET/RF candidates to produce epistemic uncertainty bands. Candidates with high epistemic uncertainty get lower fusion weight.

### Application 4: Port to political_engine.py
Political races have severe temporal distribution shift:
- Different election cycles have different dynamics
- New candidates change the feature space
- Apply shift-aware calibration per election_type × incumbency_status

## Expected Improvement
- 0.001-0.002 Brier improvement from better calibration under distribution shift
- Particularly effective for late-season predictions (largest drift from training data)

## Implementation Notes
- Library: `scikit-learn calibration` + `skshift` for distribution shift detection
- Drift metric: Maximum Mean Discrepancy (MMD) or KL divergence between season distributions
- ~100 lines of Python to implement shift-aware fusion in predict_today.py
- Does NOT require retraining islands — pure post-processing layer

## Links
- arXiv:2603.06733: https://arxiv.org/abs/2603.06733
- Related: fire-230 Temporal CV (arXiv:2506.12183), fire-244 Conformal Reuse (arXiv:2506.19689)
