# SOTA Research Proposal: Split Conformal Calibration for NBA Probabilistic Predictions

**Source:** arXiv:2510.07185 — "Split Conformal Classification with Unsupervised Calibration"
**Detected:** fire-168 (EVEN) — 2026-05-26T04h
**Priority:** 33 (between Venn-Abers=32 and win-diff-feature=35)

## Key Insight

Split conformal prediction provides distribution-free coverage guarantees for probabilistic classifiers: P(Y ∈ Ĉ(X)) ≥ 1 − α for any user-chosen α. Unlike isotonic calibration (which minimizes MSE/Brier directly but can overfit on small calibration sets), conformal prediction guarantees marginal coverage without holdout label waste.

**Novel contribution of arXiv:2510.07185:** Eliminates the need for separate labeled calibration data by using unsupervised calibration samples — directly applicable to our low-data NBA regime where every labeled game is precious.

## Current Calibration Pipeline

- Stage 1: GA evolves feature sets + model types (train/val split)
- Stage 2: isotonic regression post-hoc calibration
- Problem: isotonic can overfit when validation set is small (<500 games); uncalibrated models poorly resolved near p=0.5 (close games)

## Proposed Change

Replace or supplement isotonic calibration with split conformal predictor:

```python
from mapie.classification import MapieClassifier

# After GA selects best model (e.g., RF-48f, LightGBM-38f):
mapie = MapieClassifier(estimator=best_model, method="score", cv="prefit")
mapie.fit(X_cal, y_cal)  # labeled calibration set (small OK)
y_pred, y_pi = mapie.predict(X_test, alpha=0.10)  # 90% coverage sets
# Use y_pred[:,1] as calibrated win probability
```

**Unsupervised variant (arXiv:2510.07185):** When labeled calibration data is limited, use unlabeled test distribution to calibrate — eliminates splitting waste entirely.

## Expected Improvement

- Brier: 0.001–0.003 improvement (similar to Venn-Abers estimate)
- Calibration reliability: guaranteed marginal coverage (isotonic has none)
- Particularly valuable for close games (p ≈ 0.4–0.6) where current models are worst-calibrated

## Target Islands

1. **S18** — RF-44f / LightGBM-38f pareto (c637, pareto=19 surging)
2. **S22** — RF-48f pareto_best (c492, approaching hard-reset c503)
3. **S15** — RF-75f fleet best (sleeping, priority after wake)

## Library

- Primary: `MAPIE` (Model Agnostic Prediction Interval Estimator, scikit-learn compatible)
- Alternative: `nonconformist` (also used by crepes for Venn-Abers)
- Note: `nonconformist` already proposed for Venn-Abers (vm-add-venn-abers-calibration, priority=32) — can install both in same dependency PR

## Synergies

- Venn-Abers (arXiv:2605.03816, priority=32): targets XGBoost/LightGBM "Bulls-effect" miscalibration
- Split conformal (this proposal, priority=33): targets coverage guarantee for ALL model types including RF
- Together: Venn-Abers handles model-specific calibration bias; split conformal wraps the ensemble for guaranteed marginal coverage
- Combine both in single `vm-add-calibration-suite` implementation task

## Action Item

- Add `vm-add-split-conformal-calibration` to work-queue (priority=33)
- Depends on: island wake (S15) or can run on S18/S22 directly (both UP)
- Fast path: test on S22 RF-48f (UP, c492) before next hard-reset ~c503
