# SOTA Research Proposal: Online Conformal Prediction under Corrupted Feedback

**Source:** arXiv:2605.20515 (May 2026) — "Online Conformal Prediction under Corrupted Feedback"  
**Priority:** 118  
**Fire:** 260 (EVEN WebSearch) / Written: 261 (ODD)  
**Date:** 2026-06-03

## Key Findings

The paper addresses a critical gap in online conformal prediction: **what happens when the feedback labels used for calibration are corrupted?** In standard ACI (Adaptive Conformal Inference), the algorithm updates its coverage threshold using observed outcomes. If outcomes are corrupted (adversarially or randomly), coverage guarantees degrade.

Key contributions:
1. **Robust ACI variant** — maintains (1-α)-coverage even when up to an α-fraction of observed labels are adversarially corrupted.
2. **Corruption-detection wrapper** — online test for detecting anomalous feedback sequences; triggers conservative threshold adjustment when corruption detected.
3. **Coverage analysis under corruption rate ε** — formal bound: actual coverage ≥ (1-α) − 2ε, where ε is the fraction of corrupted labels.
4. **No clean validation set required** — works with the corrupted online stream only.

## Application to NBA Prediction

NBA prediction has a concrete corrupted feedback problem:

1. **Late box score corrections**: Official NBA box scores are sometimes corrected hours/days after the game. If our calibration window includes preliminary scores, this is label corruption.
2. **Overtime games**: Model trained on regulation play; outcome observed after OT — distribution mismatch = implicit corruption.
3. **Data pipeline errors**: fetching from multiple sources (ESPN, NBA API, etc.) introduces occasional label noise from conflicting records.

### Implementation Plan

**Application 1: Robust ACI calibration mode**
```python
# In features/engine.py validate_model():
def validate_model(model, X, y, method='standard_aci', corruption_threshold=0.05):
    if method == 'robust_aci':
        # Robust ACI: track running corruption detection score
        # If score exceeds threshold, widen prediction interval by 2*epsilon factor
        ...
```

**Application 2: `/api/export` metric**
Add `corrupted_feedback_coverage` field: proportion of games where late score corrections occurred in trailing 50-game calibration window.

**Application 3: Calibration window health check**
- Compare game outcome logged at T+1h vs T+24h for trailing 100 games
- `label_drift_rate` = fraction where result changed → approximate ε
- If `label_drift_rate > 0.03`, trigger robust ACI mode automatically

**Application 4: Port to political_engine.py**
Election night reporting is a natural corrupted feedback scenario:
- Preliminary counts → final counts differ on 2-8% of race calls
- Use `label_drift_rate_pol` = fraction of elections where first-call differed from certified result
- Port robust ACI with political-specific corruption threshold

## Expected Improvement

- Under clean data: no regression (robust ACI degrades gracefully to standard ACI when ε≈0)
- Under 3-5% label corruption: **0.001-0.002 Brier improvement** from better-calibrated interval widths
- Eliminates systematic over-confidence from stale/corrupted calibration labels

## Library

- MAPIE (method=`"aci"`) — base framework
- Custom corruption-detection wrapper (~80 lines): sliding window Z-score on non-conformity scores, flag outliers as potentially corrupted

## Priority Rationale

- NBA box score correction rate: estimated ~2-4% (based on live data experience)
- Impact window: calibration set of 200 games × 3% corruption = 6 corrupted labels → measurable coverage degradation
- Validated by formal coverage bound: coverage loss = 2×ε = 2×0.03 = 0.06 = 6% → non-trivial for tight Brier optimization

## Next Steps

1. VM: measure actual label_drift_rate on trailing 200 games (compare NBA API T+1h vs T+48h)
2. Implement robust ACI wrapper in engine.py (validate_model)
3. A/B test: standard ACI vs robust ACI on S15 RF-75f holdout
4. Port to political_engine.py with election_label_drift_rate metric

## References

- arXiv:2605.20515 — primary source
- MAPIE documentation: https://mapie.readthedocs.io/
- Complements: arXiv:2602.16537 (Optimal conformal regret, priority=117) — both address calibration robustness under distribution changes
- Complements: arXiv:2601.18509 (EnbPI for time series, priority=95) — non-stationary streams
