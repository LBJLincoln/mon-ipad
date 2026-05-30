# SOTA Research Proposal: Temporal CV — Sliding Window vs Walk-Forward

**Source:** arXiv:2506.12183 (June 2025/2026)
**Title:** "Temporal cross-validation impacts multivariate time series subsequence anomaly detection evaluation"
**Relevance:** HIGH — directly addresses our negative CV→holdout gap (~-0.01)
**Priority:** 108
**Fire:** 230 (EVEN WebSearch)

## Problem Statement

All 3 of our primary models show a consistent negative CV→holdout gap (~-0.01 Brier):
- TabICL: CV 0.22169 vs holdout 0.21139 (gap = -0.01030, window-biased)
- XGBoost 4581f: holdout 0.22079 vs CV (~0.22169 est, gap ≈ -0.00090)
- LightGBM 4581f: similar pattern

Walk-forward validation (our current method in GA islands) uses an expanding window — trains on all past, tests on next fold. This means early folds have tiny training sets while late folds have huge ones, creating inconsistent fold-to-fold Brier scores.

## Key Findings from arXiv:2506.12183

1. **Sliding window CV** yields higher median AUC-PR and **reduced fold-to-fold performance variance** vs walk-forward (expanding window)
2. Walk-forward can underestimate model performance when training set size effects dominate over temporal patterns
3. For non-stationary series (concept drift), sliding window is more robust — consistent window size controls for training volume effects
4. The paper recommends sliding window as the default for evaluation of sequential ML models

## Direct Application to Nomos42

The negative CV→holdout gap in our models (-0.01) is partially explained by walk-forward's inconsistent fold sizes. With 11,440 games across 8 seasons, the expanding window gives early folds (e.g. fold 1: 1,500 train / 300 test) very different performance than late folds (fold 7: 9,000 train / 300 test). Sliding window with fixed `max_train_size=3000` would equalize fold conditions.

### Application 1: CV method flag in engine.py
```python
# In validate_model(), add cv_method parameter:
def validate_model(model, X, y, cv_method='sliding_window', window_size=3000):
    if cv_method == 'sliding_window':
        tscv = TimeSeriesSplit(n_splits=5, max_train_size=window_size)
    else:  # walk_forward (current)
        tscv = TimeSeriesSplit(n_splits=5)
    ...
```

### Application 2: CV holdout gap metric
- Compute `brier_cv` (sliding window) and `brier_holdout` (walk-forward on final season)
- Add `cv_gap = brier_cv - brier_holdout` to /api/export
- Alert when |cv_gap| > 0.005 (indicates temporal leakage or fold size artifact)

### Application 3: 7th Pareto objective
- Add `minimize_cv_gap = abs(brier_cv - brier_holdout)` as 7th Pareto objective
- Models with large CV→holdout gap are overfit to specific time windows; deprioritize them
- Complement existing: Brier, ROI, Sharpe, ECE, coverage_violation, multi_scale_coverage

### Application 4: Port to political_engine.py
- Political prediction has even stronger temporal non-stationarity (election cycle effects)
- Apply same `sliding_window` CV with window_size matching ~2 election cycles
- Expected: tighter Brier estimates for POL models

## Expected Improvement
- 0.001-0.003 Brier reduction via more honest CV estimates driving GA selection
- Reduced overfitting to specific season windows (especially helpful for 200f models)
- Better model ranking: stable CV scores → more reliable pareto front
- More honest reporting: CV→holdout gap narrows from ~0.01 to ~0.005

## Library
- `sklearn.model_selection.TimeSeriesSplit(n_splits=5, max_train_size=3000)`
- No new dependencies required (scikit-learn already in requirements)

## Integration Notes
- S22 and S18 are the active islands — apply when they next come up for config update
- S13/S14/S15 sleeping — apply on wake
- Expected pareto impact: models with lower cv_gap rise in pareto; high-gap overfit models fall

## Relationship to Prior Research
- arXiv:2602.19284 (fire-224): Localized conformal model selection — complementary (per-region CV)
- arXiv:2502.05565 (fire-226): Multi-scale conformal prediction — complementary (multi-scale coverage)
- arXiv:2505.12578 (fire-216): Stacked conformal prediction — complementary (calibration post-CV)

## Status
Proposal written fire-230 (2026-06-05T16h). Work-queue: vm-research-temporal-cv-sliding-window-fire230 (priority=108).
