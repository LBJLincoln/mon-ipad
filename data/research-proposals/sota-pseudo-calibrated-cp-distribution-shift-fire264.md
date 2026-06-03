# SOTA: Coverage Guarantees for Pseudo-Calibrated CP under Distribution Shift

> Source: arXiv:2602.14913 (Feb 2026) | Priority: 121 | Added: fire-264 EVEN (2026-06-03T20h)

## Paper Summary

**Title:** "Coverage Guarantees for Pseudo-Calibrated Conformal Prediction under Distribution Shift"
**arXiv:** 2602.14913
**Year:** February 2026

**Key finding:** Pseudo-calibration counters performance loss in conformal prediction under bounded label-conditional covariate shift. The paper derives a lower bound on target coverage expressed in terms of:
1. Source-domain loss of the underlying classifier
2. A Wasserstein distance measure of the distribution shift

This enables maintaining theoretical coverage guarantees even when train/test distributions differ — a core challenge for NBA season prediction where team rosters, coaching styles, and league-wide trends shift continuously.

## Why This Matters for Nomos42

The NBA evolution fleet currently uses:
- Static isotonic calibration (post-hoc)
- Venn-Abers calibration (S22 organic, validated fire-197+)
- Split conformal / ACI (MAPIE, fire-168)

All three assume train ≈ test distribution. In practice, NBA data has systematic temporal distribution shift:
- Trade deadline roster changes (Feb)
- Injury patterns (back-to-back fatigue compounds through season)
- Rookie emergence (performance drift upward through first season)
- Playoff-vs-regular-season pace differences

arXiv:2602.14913 provides a framework to maintain coverage guarantees despite this shift.

## Applications

### App 1: Pseudo-Calibration Wrapper (GA Evolution)
- Add `pseudo_calibrated_cp` as new MODEL_TYPE calibration option in app.py
- Wrap existing isotonic calibrator with pseudo-calibration layer that estimates Wasserstein shift
- Expected: coverage bound improves 5-15% under trade-deadline and playoff scenarios
- Implementation: ~80 lines using scipy Wasserstein + MAPIE ACI

### App 2: Wasserstein Shift as Pareto Objective
- Add `wasserstein_shift_estimate` as new metric to /api/export
- Use inverse Wasserstein shift to re-weight island predictions in predict_today.py
- Islands with lower shift score (distribution closer to current test) get higher fusion weight
- Complements fire-260 shift-robust calibration (priority=120)

### App 3: Coverage Bound Monitoring
- Add `pseudo_calibration_coverage_bound` to /api/export
- Alert when bound drops below 0.85 (shift too high for reliable coverage)
- Trigger diversify or hard-reset when coverage bound degrades

### App 4: Political Alpha Port
- Election cycle shift: 2024 → 2026 → 2028 creates systematic distribution shift in political_engine.py
- Add pseudo-calibrated CP to political islands (P4, P7)
- Wasserstein shift estimate on political features — incumbency patterns, approval ratings drift

### App 5: Synergy with Pipeline
- Complements arXiv:2603.06733 (shift-robust calibration, priority=120)
- Complements arXiv:2602.16537 (optimal conformal regret under drift, priority=117)
- Together: 3-layer temporal robustness (detect shift → quantify → pseudo-calibrate)

## Expected Impact
- **Brier improvement:** 0.001-0.002 (especially late-season, back-to-back heavy stretches)
- **Coverage quality:** +5-15% bound tightness under trade-deadline shift
- **ROI/Sharpe:** indirect improvement from better late-season calibration

## Implementation Notes
```python
from scipy.stats import wasserstein_distance
from mapie.regression import MapieRegressor

# Pseudo-calibration step after isotonic
def pseudo_calibrate(model, X_cal, y_cal, X_test):
    shift = wasserstein_distance(
        X_cal.mean(axis=1), X_test.mean(axis=1)
    )
    # Scale conformal scores by shift factor
    alpha_corrected = alpha * (1 + shift_penalty(shift))
    return MapieRegressor(model, method='naive', cv='prefit')
```

## Library
- `scipy.stats.wasserstein_distance` (already available)
- `MAPIE` (already in pipeline from fire-168)
- No new dependencies required

## Work Queue
- ID: `vm-research-pseudo-calibrated-cp-shift-fire264`
- Priority: 121
- Owner: local-vm
