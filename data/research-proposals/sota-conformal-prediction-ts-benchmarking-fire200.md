# SOTA Research Proposal: Conformal Prediction for Time Series (fire-200)

**Source:** arXiv:2601.18509 — "Conformal Prediction Algorithms for Time Series Forecasting: Methods and Benchmarking" (January 2026)
**Detected:** fire-200 (EVEN WebSearch, 2026-05-31T14h)

## Summary

Conformal prediction is a model-agnostic post-hoc calibration framework that wraps any base predictor to deliver prediction sets with provable coverage guarantees. The 2026 benchmarking paper evaluates multiple conformal prediction algorithms for time series settings, with methods specifically designed to handle non-exchangeability.

## Key Findings

1. **Distribution-free guarantee**: Coverage guarantees hold without distributional assumptions
2. **Multi-step horizons**: Horizon-specific calibration scores and quantiles for multi-step prediction
3. **Non-exchangeability handling**: Ensemble methods under mixing conditions — directly applicable to NBA sequences (rosters change, form evolves across a season)
4. **Algorithm benchmarking**: Multiple conformal algorithms compared on real time series, providing guidance on which methods suit different characteristics

## Relevance to Nomos42

### Direct Application
- NBA games form a temporal sequence — conformal prediction for time series handles this naturally
- Post-hoc, no retraining required: wrap existing RF/ET models directly
- Distribution-free coverage guarantees are more principled than sigmoid/isotonic calibration alone
- Handles NBA's non-stationary nature (trades, injuries, form cycles)

### Port Targets
1. **S18 RF/ET** (post-c1150 possibly-clean reset) — highest priority
2. **S22 RF/ET** (performance cliff; conformal intervals could flag regime changes early)
3. **S15 RF-75f fleet best** (when it wakes from 32+ fire sleep)
4. Complement existing Venn-Abers + beta calibration (both organically evolved in S18 fire-200)

### Expected Improvement
- Brier: 0.001–0.003 improvement from principled calibration
- Coverage guarantee: distribution-free marginal coverage on holdout
- Regime detection: widening intervals during performance cliffs = early warning signal

## Implementation Path

```python
from mapie.time_series import TimeSeriesRegressor
# EnbPI for non-stationary sequences (best per arXiv:2601.18509 benchmark)
wrapper = TimeSeriesRegressor(estimator=fitted_rf, method="enbpi", cv="prefit")
wrapper.fit(X_calib, y_calib)
y_pred, y_intervals = wrapper.predict(X_test, alpha=0.1)
```

Algorithm ranking per benchmark:
- **EnbPI**: best for non-stationary (top pick for NBA season sequences)
- **ACI** (arXiv:2412.19318): parameter-free, handles distribution shift
- **SPCI**: optimal for multi-step horizons

## Relationship to Existing Proposals

| Proposal | arXiv | Status |
|----------|-------|--------|
| Split Conformal Calibration | 2510.07185 | pending vm-add-split-conformal-calibration |
| Adaptive Conformal Betting | 2412.19318 | pending vm-add-adaptive-conformal-betting |
| Venn-Abers Calibration | 2605.03816 | **VALIDATED** organically S18 fire-197, surviving 3 resets |
| Beta Calibration | — | **NEW** organically evolved S18 fire-200 |

**Recommendation:** Implement as time series-specific conformal layer AFTER Venn-Abers + beta calibration extraction from S18 app.py. Complementary: Venn-Abers handles point calibration; conformal TS handles coverage intervals.

## Priority
**Priority 95** (vm-research-conformal-ts-benchmarking-fire200)
