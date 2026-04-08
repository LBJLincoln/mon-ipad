# Isotonic Regression Post-Calibration for Brier Score

**Date:** 2026-04-05  
**Source:** MDPI Information 17(1):56 (2025) "Uncertainty-Aware ML for NBA Forecasting" + Underdogchance calibration benchmarks 2025  
**Priority:** HIGH — confirmed -10 to -15% ECE reduction, targets sub-0.218 Brier  
**Cycle:** Brain cycle 66 (research cycle)

## Problem

Current fleet best: **0.22098** (S15 extra_trees). Target: **< 0.21837** for checkpoint, **< 0.20** long-term.

Previous calibration work (temperature scaling, ECE fitness objective) has not broken below 0.221. The MDPI 2025 paper achieved **Brier 0.199 with XGBoost** on NBA data — 11% below our best. Their key differentiator was **isotonic regression calibration**, not temperature scaling.

Temperature scaling: fits 1 parameter (T), optimal for neural networks with well-shaped sigmoid outputs.  
Isotonic regression: fits a non-parametric monotone function on a held-out calibration fold — 50% better ECE reduction vs temperature scaling, especially for tree models (our primary model type).

## Evidence

From 2025 benchmark (Underdogchance + MDPI paper):
- Temperature scaling: ~33% ECE reduction on tree models
- Isotonic regression: ~50% ECE reduction on tree models  
- Platt scaling: ~25% ECE reduction
- **On NBA XGBoost**: isotonic brought Brier from 0.228 → 0.199 (12% improvement)

Key insight: tree models (random_forest, extra_trees, xgboost, lightgbm, catboost) output poorly-calibrated probabilities that need non-parametric correction. The monotone constraint of isotonic regression matches the expected direction of probability corrections without overfitting.

## Proposed Implementation

### Step 1: Add calibration fold to genetic loop evaluation

```python
# In hf-space/evolution/genetic_loop.py — evaluate_individual()
from sklearn.isotonic import IsotonicRegression
import numpy as np

def evaluate_with_isotonic_calibration(model, X_train, y_train, X_val, y_val,
                                        calibration_frac=0.15):
    """
    Split val set: 15% for isotonic fitting, 85% for Brier evaluation.
    Requires at least 500 samples in val for reliable isotonic fit.
    """
    n_cal = max(500, int(len(X_val) * calibration_frac))
    X_cal, X_test = X_val[:n_cal], X_val[n_cal:]
    y_cal, y_test = y_val[:n_cal], y_val[n_cal:]
    
    # Fit isotonic regression on calibration fold
    raw_probs_cal = model.predict_proba(X_cal)[:, 1]
    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit(raw_probs_cal, y_cal)
    
    # Apply calibration to test fold
    raw_probs_test = model.predict_proba(X_test)[:, 1]
    calibrated_probs = ir.transform(raw_probs_test)
    
    brier = np.mean((calibrated_probs - y_test) ** 2)
    return brier, ir
```

### Step 2: Implement minimum calibration samples guard

Only apply isotonic when calibration fold ≥ 500 samples (prevents overfitting on small folds). With 9,551 games and 15% cal fold, we get ~1,433 samples — well above threshold.

```python
MIN_CAL_SAMPLES = 500
if n_cal < MIN_CAL_SAMPLES:
    # Fall back to raw probabilities (no calibration)
    brier = compute_brier_raw(model, X_val, y_val)
else:
    brier, ir = evaluate_with_isotonic_calibration(...)
```

### Step 3: Save calibrator with best individual

The GA currently saves `best_model` (the sklearn estimator). Add `best_calibrator` (the IsotonicRegression instance) so it persists across cycles and can be used in daily predictions.

```python
evolution_state['best_model'] = model
evolution_state['best_calibrator'] = ir  # NEW
```

### Step 4: Apply calibrator in predict_today.py

```python
# In scripts/predict_today.py
calibrated = state['best_calibrator'].transform(raw_probs)
```

## Expected Impact

- Brier improvement: **-0.010 to -0.020** (conservative estimate based on MDPI: 0.228→0.199)
- Our current best 0.22098 → estimated **0.200–0.210** post-calibration
- This would cross the 0.21837 Supabase checkpoint threshold
- ECE (Expected Calibration Error) improvement: ~50% reduction

## Implementation Notes

- **No change to GA selection** — isotonic calibration runs at evaluation time, not selection time
- **No SHAP dependency** — independent of the SHAP crossover proposal
- **CPU-safe** — `sklearn.isotonic.IsotonicRegression` is O(n log n), ~0.5s on 1,500 samples
- **Applies to all 6 islands** — same genetic_loop.py code base

## Files to Modify

1. `hf-space/evolution/genetic_loop.py` — add isotonic calibration to `evaluate_individual()`
2. `hf-space/app.py` — save `best_calibrator` in evolution state JSON
3. `scripts/predict_today.py` — use calibrator in daily predictions
4. Also update: `nomos-nba-agent/evolution/genetic_loop.py` for engine parity

## Cross-Project Application

Political Alpha uses the same `evolution/genetic_loop.py` (IDENTICAL per CLAUDE.md). Apply the same isotonic calibration fix to `nomos-political-alpha/evolution/genetic_loop.py`. Expected Brier improvement: PA2 0.23134 → ~0.210.

---
**Status:** PROPOSED  
**Priority:** SHIP THIS CYCLE — highest expected Brier delta of any pending proposal  
**Estimated effort:** 1–2 hours (< 50 LOC change)  
**Risk:** Low (isotonic is well-validated, guard protects against small-fold overfitting)
