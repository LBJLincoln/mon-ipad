# Research Proposal: Calibrated Stacked Ensemble for NBA Brier Optimization

**Date:** 2026-05-04  
**Source:** WebSearch NBA SOTA 2026 (MDPI/IEEE/Nature)  
**Priority:** HIGH  
**Estimated Brier Impact:** −0.02 (fleet 0.22019 → ~0.20)  
**Target Island:** S15 (Nomos42/nba-evo-6, rebuilding at gen=16 w/ CatBoost)

## Key Finding

Academic SOTA (2026) shows XGBoost + Logistic Regression with **CalibratedClassifierCV**
(isotonic + Platt scaling) achieves Brier **~0.20** on NBA game prediction — the same
target we're chasing. This is ~0.02 better than our current fleet best (0.22019).

Key papers:
- [Uncertainty-Aware ML for NBA Forecasting](https://www.mdpi.com/2078-2489/17/1/56) — MC Dropout calibration, strict chronological split
- [Stacked Ensemble for NBA](https://www.nature.com/articles/s41598-025-13657-1) — CalibratedClassifierCV auto-selects best method
- [Comparing ML for NBA](https://ieeexplore.ieee.org/document/11030489/) — XGBoost/LR Brier ~0.20, AUC 0.75-0.76

## Gap Analysis

| Metric | Our Fleet | Academic SOTA | Gap |
|--------|-----------|---------------|-----|
| Best Brier | 0.22019 | ~0.20 | −0.02 |
| Calibration | Colab-only isotonic | In-GA CalibratedClassifierCV | Missing |
| Ensemble | Single model per island | Stacked XGB+RF+ET meta-LR | Missing |

**Root insight:** Our GA evaluates raw uncalibrated Brier during fitness computation.
Calibrating predictions *inside* the fitness loop would give more accurate model selection signals,
and the calibrated model would score better on holdout Brier.

## Implementation Options

### Option A — Post-hoc Isotonic Calibration (Quick Win, 1 day)
Wrap best model with `CalibratedClassifierCV(method='isotonic', cv=5)` after training.
Score fitness on calibrated probabilities. 5-line change in island `app.py`.

```python
from sklearn.calibration import CalibratedClassifierCV
calibrated = CalibratedClassifierCV(model, method='isotonic', cv=5)
calibrated.fit(X_train, y_train)
brier = brier_score_loss(y_test, calibrated.predict_proba(X_test)[:, 1])
```

### Option B — Stacked Ensemble Meta-Learner (Medium, 3 days)
Stage 1: XGBoost + Random Forest + Extra Trees (base learners, OOF predictions)
Stage 2: Logistic Regression meta-learner on OOF stack
Apply CalibratedClassifierCV to final meta output.
Limitation: 3× compute per generation — may be slow on CPU.

### Option C — Temperature Scaling (Fast, lightweight)
Post-hoc calibration via single temperature parameter T on logits.
Faster than isotonic (no CV). From Guo et al. 2017.
Good for logistic regression outputs (S14 is logistic — already well-calibrated).

## Recommended Sequence

1. **S15 test**: Add Option A (isotonic) to S15's GA fitness loop (CatBoost wraps cleanly)
2. **Measure**: Track Brier delta over 100 gens vs. prior best 0.22661
3. **If Brier improves >0.001**: Propagate to S13, S18, S22
4. **If no improvement**: Try Option C (temperature scaling) on S14 (logistic)

## Cross-Project Note

This calibration insight applies equally to Political islands (fleet best 0.24992).
P7 current_brier=0.24904 is approaching but not beating best=0.25412 — adding
calibration to P7's fitness loop could help break the plateau.

Political oracle CV Brier: 0.23274 (best fold 0.22329). Adding stacked ensemble to the
weekly oracle retrain script could also push the oracle below 0.22.
