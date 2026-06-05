# SOTA Proposal: Sequential Conformalized Density Regions for NBA Time-Series Prediction

**Fire**: fire-280 (EVEN)
**arXiv**: 2604.07325
**Priority**: 133
**Date**: 2026-06-06T12h

## Paper

"Sequential Conformalized Density Regions" (Sequential CDR) — Apr 2026

**Key finding**: Distribution-free sequential prediction regions for time series with finite-sample coverage guarantees. Standard split-CP requires i.i.d. data — invalid for time series due to temporal autocorrelation. Sequential CDR adapts to serial correlation by using online martingale-based correction, achieving valid marginal coverage even under strong autocorrelation. Beats ACI (Adaptive Conformal Inference) on 12 real-world time series datasets for interval width (tighter) with equivalent or better coverage. Key innovation: "conformalized density regions" — instead of scalar intervals, outputs prediction *sets* defined by kernel density level sets, capturing multi-modal prediction distributions (e.g., a game where either team could dominate = bimodal score distribution).

## Relevance to Nomos42

### Why This Matters

NBA game outcomes exhibit strong temporal autocorrelation:
- Team momentum: win streaks, losing streaks (5-10 game autocorrelation)
- Fatigue accumulation: back-to-back patterns are structured, not i.i.d.
- Seasonal phase transitions: October/November vs. playoff pace shifts create non-stationarity
- Current split-CP baseline (fire-168) treats each game as i.i.d. — theoretically invalid

Sequential CDR provides coverage guarantees that are valid for the actual NBA data-generating process.

### Application 1: Replace Split-CP Calibration in engine.py

Replace static isotonic calibration / split-CP with Sequential CDR:
```python
from calibration.sequential_cdr import SequentialCDRCalibrator
calibrator = SequentialCDRCalibrator(kernel='gaussian', bandwidth='scott', online=True)
calibrator.fit(X_cal_seq, y_cal_seq, timestamps=t_cal)  # time-ordered calibration
intervals = calibrator.predict(X_test, alpha=0.1)
```
Respects temporal structure of NBA data (game sequences within season).

### Application 2: Multi-Modal Prediction Sets for Swing Games

CDR outputs kernel density level sets — naturally captures bimodal distributions:
- High-variance playoff games: model outputs P(home_win) ≈ 0.5 with high uncertainty
- Current point prediction + isotonic band = symmetric, underestimates tail risk
- CDR prediction set = asymmetric density region (e.g., "home team wins by 10+ OR loses by 5+" as disjoint modes)

Add `prediction_set_width` and `prediction_set_modality` metrics to `/api/export`.

### Application 3: Sequential CDR for evo4/S22 Pareto Model Validation

Before promoting evo4 RF-0.22007 or S22 ET-0.2191 to production:
1. Fit Sequential CDR calibrator on 2024-25 season (time-ordered)
2. Evaluate on 2025-26 season — valid coverage even under team roster changes (distribution shift)
3. Compare CDR interval width vs. split-CP — expect 10-20% tighter intervals

### Application 4: Online Adaptation During Live Season

Sequential CDR is online: calibration set updates with each new game result.
- Deploy as live-update calibrator in `predict_today.py`
- Each prediction uses all previous 2025-26 games as calibration data
- Automatically adapts to mid-season trades (distribution shift), playoff pace changes
- Add `adaptive_calibration_lag` metric to daily prediction output (tracks drift magnitude)

### Application 5: POL Time Series Calibration

Political predictions are even more temporally autocorrelated:
- Pre-election polling has strong momentum structure
- State-level correlations: swing states cluster (not i.i.d. across geography+time)
- Apply Sequential CDR to P4/P7 calibration pipeline for POL islands
- Add `temporal_coverage_gap` to POL `/api/export`

## Implementation

**Library**: No dedicated library exists yet — implement from paper algorithm (~80 lines, numpy/scipy):
```python
class SequentialCDRCalibrator:
    """Online martingale-corrected conformal density regions."""
    def __init__(self, kernel='gaussian', bandwidth='scott', alpha=0.1):
        ...
    def update(self, x_new, y_new):
        # Online update of kernel density estimate
        # Martingale correction for temporal autocorrelation
        ...
    def predict_set(self, x):
        # Return density level set at coverage level alpha
        ...
```
Dependencies: numpy, scipy.stats (KDE), statsmodels (autocorrelation test) — all available.

**Work-queue**: `vm-research-sequential-cdr-time-series-fire280` (priority=133)

**Expected improvement**: 0.001-0.003 Brier (valid calibration under temporal autocorrelation) + 10-20% tighter prediction intervals vs. split-CP for sequential NBA games.

## Connection to Existing Pipeline

- Complements fire-200 EnbPI (priority=95) — EnbPI is the current SOTA for non-stationary time series CP; Sequential CDR adds multi-modal density sets on top
- Complements fire-230 Temporal CV Sliding Window (priority=108) — both address temporal structure; CDR is calibration-side, sliding-window is training-side
- Complements fire-244 Calibration Set Reuse (priority=114) — CDR online update enables reusing growing calibration set across season without data split overhead
- Direct validation path: Sequential CDR on evo4 RF-0.22007 + S22 ET-0.2191 before fleet-best promotion — more valid coverage claim than static split-CP
