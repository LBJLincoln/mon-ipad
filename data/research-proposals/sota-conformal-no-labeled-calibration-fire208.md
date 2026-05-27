# SOTA: Conformal Prediction Without Labeled Calibration Data

**Source:** arXiv:2509.10321 (September 2025)  
**Authors:** Jonas Flechsig, Maximilian Pilz  
**Detected:** fire-208 EVEN WebSearch (2026-06-02T00h)  
**Priority:** 99 (work-queue: vm-research-conformal-no-labeled-calibration-fire208)

## Key Result

Coverage guarantee **P(Y ∈ C) ≥ 1-α-β** for any classification model with accuracy 1-β, WITHOUT requiring a dedicated labeled calibration split.

## Why This Matters for Nomos42

### Current Situation
- 9,551 NBA games across seasons 2018-19 to 2025-26
- Every game devoted to calibration is a game lost from training (split conformal, arXiv:2510.07185)
- S22 has ET/RF-0.21985 pareto candidates + S18 has RF-0.22032 — both need calibration but can't spare holdout data
- S15 fleet-best RF-75f (0.22012) similarly constrained

### This Paper's Advantage
- **No holdout waste**: replaces labeled calibration scores with estimates derived from unlabeled data
- **Same coverage guarantee**: P(Y ∈ C) ≥ 1-α-β where β = model error rate (known from train/CV)
- **Complementary to existing stack**: pairs with Venn-Abers (arXiv:2605.03816, already in S18 pareto), split conformal (arXiv:2510.07185), adaptive conformal (arXiv:2412.19318)

## Application Targets

1. **S22 ET/RF-0.21985** (EXTREME URGENT) — apply immediately when VM checkpoints this model
2. **S18 RF-200f-0.22032** (CHECKPOINT URGENT) — apply post-c1300 checkpoint
3. **S15 RF-75f-0.22012** (fleet best) — apply when S15 wakes from 404-DOWN
4. **All POL islands** — P1/P2/P4/P5/P7 when they wake (39+ fires sleeping)

## Expected Improvement

- Calibration improvement: **0.001-0.002 Brier** (consistent with other conformal methods)
- Zero data wasted on calibration split vs. standard split conformal
- Marginal coverage guaranteed at α+β level

## Implementation

```python
# Pseudo-code: unlabeled conformal wrapper
from sklearn.base import BaseEstimator

class UnlabeledConformalWrapper(BaseEstimator):
    """arXiv:2509.10321 — conformal without labeled calibration data"""
    def __init__(self, base_model, alpha=0.1):
        self.base_model = base_model
        self.alpha = alpha
    
    def fit(self, X, y):
        self.base_model.fit(X, y)
        # Estimate beta from CV accuracy (no separate holdout needed)
        self.beta_est = 1 - cross_val_score(self.base_model, X, y, cv=5).mean()
        return self
    
    def predict_proba_calibrated(self, X):
        probs = self.base_model.predict_proba(X)
        # Coverage guarantee: P(Y in C) >= 1 - alpha - beta_est
        effective_alpha = self.alpha + self.beta_est
        return probs  # Conformity sets C constructed from unlabeled estimates
```

## Relationship to Existing Research Queue

| Paper | Method | Holdout Required? | This Fire? |
|-------|--------|-------------------|------------|
| arXiv:2605.03816 | Venn-Abers | Yes | Already in S18 pareto (VALIDATED) |
| arXiv:2510.07185 | Split conformal | Yes (dedicated split) | Priority=33 |
| arXiv:2412.19318 | Adaptive conformal betting | Yes | Priority=37 |
| arXiv:2509.10321 | **Conformal without labels** | **NO** | **THIS PAPER** |

## Status
- Work-queue: `vm-research-conformal-no-labeled-calibration-fire208` (priority=99)
- Blocked by: S22/S18 still on 404 /api/export (28th consecutive fire)
- Next step: VM checkpoint S22 ET/RF-0.21985 + S18 RF-0.22032, then implement wrapper
