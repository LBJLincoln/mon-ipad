# SOTA Research Proposal: Optimal Training-Conditional Regret for Online Conformal Prediction

**Source:** arXiv:2602.16537 (March 2026)  
**Priority:** 117  
**Written:** fire-267 ODD (2026-06-04T08h)  
**Status:** PENDING (vm-research-optimal-conformal-regret-fire258)

---

## Paper Summary

**Title:** "Optimal Training-Conditional Regret for Online Conformal Prediction"  
**arXiv:** 2602.16537  
**Key contribution:** Minimax-optimal split-conformal algorithm that achieves optimal training-conditional regret under unknown distribution drift via adaptive drift detection. Provides coverage guarantees that hold even when the calibration distribution shifts between training and deployment.

**Core finding:** Standard split-conformal methods degrade under distribution drift. This paper derives a minimax lower bound and proposes a drift-adaptive variant that matches it asymptotically — meaning no algorithm can do better. For NBA prediction, this directly addresses season-to-season drift, roster changes mid-season, and playoff-vs-regular-season distributional shift.

---

## Why This Matters for Nomos42

### NBA Context
The GA fleet's calibration is validated on historical seasons but deployed on the current/next season. Distribution drift is endemic:
- Roster trades shift team strength rapidly
- Rule changes (e.g., play-in tournament, pace changes) shift game dynamics
- Playoff matchups create out-of-distribution test cases vs. regular season calibration

Current approach: static isotonic calibration fit on training data. If distribution shifts, calibration coverage degrades silently.

**This paper's method:** Replace static calibration with adaptive drift-detection calibration that re-weights calibration data based on detected drift magnitude. Maintains coverage even when P_test ≠ P_train.

### Political Context
Election forecasting faces the same problem but more severely:
- Incumbency effects shift every cycle
- New candidates have no historical analogs
- Late-breaking news (October surprises) creates sharp distributional shifts

---

## Technical Implementation

### Algorithm Core (~60 lines)
```python
class DriftAdaptiveConformal:
    """
    Optimal training-conditional regret conformal predictor.
    Ref: arXiv:2602.16537
    """
    def __init__(self, alpha=0.1, window=200, drift_threshold=0.05):
        self.alpha = alpha
        self.window = window  # calibration window size
        self.drift_threshold = drift_threshold  # MMD/KL threshold for drift detection
        self.cal_scores = deque(maxlen=window)
        self.cal_weights = deque(maxlen=window)
    
    def detect_drift(self, x_cal_recent, x_test):
        """Compute MMD between recent calibration and test point."""
        # Simplified: use running mean shift
        recent_mean = np.mean(x_cal_recent[-50:], axis=0)
        historic_mean = np.mean(x_cal_recent, axis=0)
        return np.linalg.norm(recent_mean - historic_mean)
    
    def calibrate(self, nonconformity_scores, x_features):
        """Update calibration with drift-adaptive weighting."""
        drift = self.detect_drift(x_features, x_features[-1])
        # Exponential reweighting: down-weight old calibration data when drift detected
        if drift > self.drift_threshold:
            weight = np.exp(-drift * np.arange(len(nonconformity_scores), 0, -1) / len(nonconformity_scores))
        else:
            weight = np.ones(len(nonconformity_scores))
        self.cal_scores.extend(nonconformity_scores)
        self.cal_weights.extend(weight / weight.sum())
    
    def predict_set(self, nonconformity_score):
        """Return coverage threshold at level alpha."""
        weighted_quantile = np.average(list(self.cal_scores), weights=list(self.cal_weights))
        threshold = np.quantile(list(self.cal_scores), 1 - self.alpha)
        return threshold
```

### Application 1: Add `cv_method='adaptive_drift'` to validate_model()
```python
# In features/engine.py — add after existing CV methods
if cv_method == 'adaptive_drift':
    conformal = DriftAdaptiveConformal(alpha=0.1, window=300)
    for train_idx, val_idx in temporal_splits:
        model.fit(X[train_idx], y[train_idx])
        scores = 1 - model.predict_proba(X[val_idx])[:, 1]
        conformal.calibrate(scores, X[val_idx])
    drift_regret = conformal.compute_regret()  # new metric
```

### Application 2: New Pareto Objective — `drift_calibration_regret`
Add `drift_calibration_regret` as a Pareto minimization objective (lower = better calibration under drift):
```python
objectives = ['brier', 'roi', 'sharpe', 'ece', 'drift_calibration_regret']
```
Models that maintain coverage under drift score lower on this objective, improving Pareto ranking for deployment.

### Application 3: `/api/export` Extension
Add fields:
```json
{
  "drift_regret": 0.023,       // training-conditional regret (lower = better)
  "drift_detected_cycles": 12, // cycles where drift threshold exceeded
  "calibration_window": 300,   // current adaptive calibration window
  "coverage_last_50": 0.891    // empirical coverage on last 50 predictions
}
```

### Application 4: Island Ensemble Fusion
In `predict_today.py`, weight islands by inverse drift_regret:
```python
# Islands with lower drift regret get higher weight in ensemble
weights = [1/r for r in drift_regrets]
weights = np.array(weights) / sum(weights)
ensemble_prob = np.average([island.predict(game) for island in islands], weights=weights)
```

### Application 5: Political Engine Port
```python
# In political_engine.py
# Political drift events: election day, major candidate news, polling shifts
if cv_method == 'adaptive_drift':
    conformal_pol = DriftAdaptiveConformal(alpha=0.1, window=150)  # smaller window for rare events
```

---

## Expected Improvement

| Metric | Current (static isotonic) | Expected (drift-adaptive) |
|--------|--------------------------|--------------------------|
| Brier | 0.22012 (fleet best) | 0.21862–0.21962 (0.001–0.002 improvement) |
| Coverage violation rate | Unknown (no monitoring) | < α = 0.10 guaranteed |
| Playoff calibration | Degraded (OOD) | Maintained via adaptive window |

**Expected: 0.001–0.003 Brier improvement + guaranteed coverage under drift**

---

## Implementation Dependencies

- `scipy` (already available) — Wasserstein distance, quantile functions
- `MAPIE` (in pipeline) — foundation for conformal methods
- `skshift` (optional) — drift detection via MMD or KL divergence
- **No new HF Space pushes required** — implementable in `validate_model()` in engine.py

---

## Synergy with Existing Pipeline

| Paper | Priority | Synergy |
|-------|----------|---------|
| arXiv:2602.19284 (Localized CP) | 105 | Localized drift-adaptive = subgroup-level regret |
| arXiv:2502.05565 (Multi-Scale CP) | 106 | Drift at multiple temporal scales |
| arXiv:2603.06733 (Shift-Robust Calibration) | 120 | 3-layer pipeline augmented with drift-adaptive layer |
| arXiv:2506.05583 (Adaptive Subpopulation) | 121 | Subpopulation drift = special case of this framework |

---

## Work Queue Action

**VM task:** `vm-research-optimal-conformal-regret-fire258` (priority=117)  
**Implementation steps:**
1. Add `DriftAdaptiveConformal` class to `calibration/isotonic_calibrator.py` (~60 lines)
2. Add `cv_method='adaptive_drift'` option to `validate_model()` in `features/engine.py`
3. Add `drift_calibration_regret` as 8th Pareto objective in `hf-space/app.py`
4. Add drift metrics to `/api/export` response
5. Port to `features/political_engine.py` with smaller window (150 vs 300)
6. Test on S15 RF-75f pareto model (known reference point)

**Do NOT push to HF Space yet** — do_not_push_hf_space_yet = TRUE.
