# Research Proposal: Post-hoc Calibration Layer
**Date:** 2026-03-27  
**Priority:** HIGH  
**Expected Brier improvement:** 0.221 → ~0.210 (-0.011, ~5% gain)

## Context

Current best Brier: **0.22126** (S14, random_forest, 34 features)  
All-time record: **0.21837**  
Target: **< 0.21837**  
Literature best (XGBoost/LR): **~0.200** (Jan 2026 MDPI, Uncertainty-Aware NBA Forecasting)

The gap between our current 0.221 and the literature 0.200 is primarily a **calibration gap**, not a feature gap. Our models are well-discriminating (ROI 31%, Sharpe 8) but may be overconfident/underconfident in probability outputs.

## The Opportunity

From: *[Uncertainty-Aware Machine Learning for NBA Forecasting](https://www.mdpi.com/2078-2489/17/1/56)* (Jan 2026):
> SKlearn's CalibratedClassifierCV is used to ensure that model probabilities are calibrated against the true probability distribution. The Brier loss score is used to automatically select the best calibration method (sigmoid, isotonic, or none). Logistic regression and XGBoost both achieve Brier ~0.20 with proper calibration.

From: *[Stacked Ensemble Model for NBA Game Outcome Prediction](https://www.nature.com/articles/s41598-025-13657-1)* (Aug 2025):
> SHAP reveals `team_elo_5_y` (5-year EWMA team ELO) as the single most predictive feature — above current season performance.

## Proposed Changes

### Change 1: Isotonic Calibration Wrapper (IMMEDIATE)

In `hf-space/app.py`, modify the `evaluate_individual()` function to wrap the fitted model with isotonic regression calibration:

```python
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import cross_val_score

def evaluate_individual(ind, X_train, y_train, X_val, y_val):
    base_model = build_model(ind)  # existing
    base_model.fit(X_train, y_train)
    
    # Calibrate on validation set with cross-val
    calibrated = CalibratedClassifierCV(base_model, method='isotonic', cv='prefit')
    calibrated.fit(X_val, y_val)
    
    probs = calibrated.predict_proba(X_val)[:, 1]
    brier = brier_score(y_val, probs)
    return brier, probs
```

**Note:** Use `cv='prefit'` to avoid double-training. This adds ~50ms per evaluation but is CPU-friendly.

**Alternative:** Train with 5-fold CV calibration on full training set:
```python
calibrated = CalibratedClassifierCV(base_model, method='isotonic', cv=5)
calibrated.fit(X_train, y_train)
```

### Change 2: Long-horizon ELO Feature (MEDIUM EFFORT)

Add `team_elo_5y` to feature engine — an EWMA of team Elo rating spanning 5 seasons (α=0.1):

```python
# In features/engine.py, add to CATEGORY 26 or new Cat38:
def _compute_elo_5y(team, season, elo_history):
    """5-year EWMA ELO — most predictive single feature per literature."""
    alpha = 0.1
    seasons = [s for s in elo_history if s <= season][-20:]  # up to 5yr window
    elo_vals = [elo_history[s].get(team, 1500) for s in seasons]
    ewma = elo_vals[0]
    for v in elo_vals[1:]:
        ewma = alpha * v + (1 - alpha) * ewma
    return ewma
```

This captures long-run franchise quality (Warriors dynasty, Celtics era) vs pure current-season form.

### Change 3: Reliability Diagram Logging (MONITORING)

Add calibration curve logging every 10 generations:
```python
from sklearn.calibration import calibration_curve

def log_calibration(probs, y_true, gen):
    fraction_of_positives, mean_predicted = calibration_curve(y_true, probs, n_bins=10)
    ece = np.mean(np.abs(fraction_of_positives - mean_predicted))  # Expected Calibration Error
    log(f"Gen {gen} ECE={ece:.4f} | calibration: {list(zip(mean_predicted.round(2), fraction_of_positives.round(2)))}")
```

## Implementation Priority

| Change | Effort | Expected Gain | Deploy On |
|--------|--------|---------------|-----------|
| Isotonic calibration | 30 min | -0.005 to -0.015 Brier | S10 first, then all |
| team_elo_5y feature | 2h (engine parity needed) | -0.003 to -0.007 Brier | All spaces |
| Calibration logging | 15 min | monitoring only | All spaces |

## References

- [Uncertainty-Aware ML for NBA Forecasting, MDPI Jan 2026](https://www.mdpi.com/2078-2489/17/1/56)
- [Stacked Ensemble NBA, Scientific Reports Aug 2025](https://www.nature.com/articles/s41598-025-13657-1)
- [NBA/WNBA ML comparison, MDPI Oct 2025](https://www.mdpi.com/2079-3197/13/10/230)
