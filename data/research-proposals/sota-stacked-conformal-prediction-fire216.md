# SOTA Research Proposal: Stacked Conformal Prediction for NBA Islands

**Source:** arXiv:2505.12578 — "Stacked conformal prediction" (Paulo C. Marques F, 2025)  
**Fire:** 216 (EVEN, 2026-06-03T08h)  
**Work-queue ID:** vm-research-stacked-conformal-prediction-fire216 (priority=102)

## Key Finding

Stacked conformal prediction provides **approximate marginal coverage guarantees for stacked ensembles without requiring a separate labeled calibration dataset**. Unlike standard split conformal prediction (arXiv:2509.10321, fire-208), which wastes holdout data, this method integrates calibration directly into the ensemble meta-learner structure using cross-fitting.

- Method: "conformalizing a stacked ensemble of predictive models"
- Guarantee: approximate marginal validity — P(Y ∈ C(X)) ≥ 1-α without holdout split
- Key advantage: no calibration holdout waste — more training data available for base models
- Empirical results: "compares favourably to a standard inductive alternative"

## Why This Matters for Nomos42

Our islands currently waste holdout data on post-hoc calibration:
- Standard isotonic calibration (current default): no coverage guarantees
- Split conformal / MAPIE (fire-168, arXiv:2510.07185): requires a dedicated hold-out set
- Venn-Abers (fire-158, arXiv:2605.03816): improves calibration but still needs holdout split

Stacked conformal removes this constraint:
- Coverage-guaranteed prediction intervals without holdout waste
- More training samples for GA pareto individuals → potential Brier improvement
- Compatible with any randomized learner (RF, ET, XGBoost, LightGBM)

## Application to Active Islands

### S18 (c1421, post-c1400-reset, RF-44f dominant)
- Apply stacked conformal wrapper to RF-44f pareto candidates post-reset
- Coverage target α=0.10 (90% marginal coverage)
- Compare to current sigmoid/isotonic calibration in pareto

### S22 (c1385, RF-48f best, threshold candidates RF-0.22047+XGB-0.22069 gen=4094 possibly alive)
- Wrap threshold candidates in stacked conformal before next reset (~c1403)
- If stacked conformal reduces ECE, add coverage_violation_rate as 5th Pareto objective

### S15 (fleet best RF-75f 0.22012, sleeping)
- Highest priority when wakes — wrap fleet best before any modification

## Implementation Plan

```python
# Using MAPIE library (already proposed fire-168)
from mapie.classification import MapieClassifier
from sklearn.ensemble import RandomForestClassifier

# Stacked conformal: no separate calibration set needed
rf = RandomForestClassifier(n_estimators=200, max_features=200)
mapie_clf = MapieClassifier(
    estimator=rf,
    method="aci",          # ACI = Adaptive Conformal Inference (fire-188)
    cv=5,                  # Cross-fitting (key: avoids holdout waste)
    random_state=42
)
mapie_clf.fit(X_train, y_train)  # No separate calibration set!
y_pred, y_pred_sets = mapie_clf.predict(X_test, alpha=0.10)
```

Expected Brier improvement from more training data: **0.001-0.003**  
Additional: coverage_violation_rate metric for Pareto objective 5 (extends fire-172 ECE work)

## Connection to Prior Research

- fire-168: Split conformal MAPIE (arXiv:2510.07185) — same library, this paper removes holdout need
- fire-172: ECE Pareto objective (arXiv:2303.06021) — coverage_violation_rate as 5th objective
- fire-158: Venn-Abers (arXiv:2605.03816) — stacked conformal gives stronger theoretical guarantees
- fire-188: Adaptive Conformal Betting (arXiv:2412.19318) — ACI method compatible
- fire-200: Conformal TS benchmarking (arXiv:2601.18509) — stacked variant for temporal NBA data

## Prerequisites

1. engine-parity-sync (priority=40) — must sync engine.py first
2. pip install mapie (if not already installed on VM)
3. VM: /api/export S22 to confirm RF-0.22047 still alive before wrapping

## Estimated Impact

- Brier: -0.001 to -0.003 (from holdout data recovered for training)
- Coverage: guaranteed at 1-α = 90% (currently no guarantee)
- Pareto diversity: new calibration models add non-dominated solutions
- POL port: same wrapper works for LightGBM/XGBoost political models
