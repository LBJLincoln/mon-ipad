# Distributional Regression Trees for Calibrated Non-Parametric Probabilistic Forecasts

**arXiv:2502.05157** (Feb 2026)
**Fire:** 242 (EVEN WebSearch)
**Priority:** 113
**Expected improvement:** 0.001-0.003 Brier

## Key Findings

"Efficient Distributional Regression Trees Learning Algorithms for Calibrated Non-Parametric Probabilistic Forecasts" introduces DRT — a tree ensemble method that outputs full predictive distributions natively rather than point estimates, with guaranteed non-parametric calibration (distribution-free coverage, no assumptions about outcome distribution).

Key advantages over standard RF/ET + post-hoc isotonic/Venn-Abers:
- Learns full conditional distribution directly during tree growth
- O(n log n) per tree — comparable efficiency to standard RF/ET training
- Outperforms standard Quantile Regression Forests on probabilistic calibration benchmarks
- No labeled calibration set needed (unlike split conformal / isotonic methods)
- Naturally produces Brier-optimal probability estimates for binary outcomes

Connection to S22 evolution: Extra Trees currently holds the pareto best at 0.21875–0.21908 Brier. DRT is the distributional generalization of ET — same tree ensemble structure with calibrated output layer. Direct successor model type candidate.

## Applications

### App 1: New MODEL_TYPE on evolution islands
Add `distributional_regression_tree` as new MODEL_TYPE candidate alongside RF/ET/XGB/LGB/CAT. Implementation via `quantile_forest` Python library (ExtraTreesQuantileRegressor) or custom DRT wrapper.

### App 2: Replace post-hoc isotonic/Venn-Abers calibration
DRT produces calibrated PDFs natively. For islands where top performer is ET (S22, S18), DRT directly upgrades the calibration pipeline: no separate calibration step needed. Extends fire-238 (discrete tokenization) goal via tree-based architecture.

### App 3: distribution_calibration_error as new Pareto objective
Add `distribution_calibration_error` (ECE-equivalent for full predictive distribution) as a new Pareto objective alongside Brier, Sharpe, ROI, and CRPS (fire-236). Measures calibration of the full conditional distribution, not just point probability.

### App 4: Brier-loss native training
DRT with proper scoring rule (Brier/CRPS) as split criterion — avoids post-hoc calibration entirely. Extends fire-236 (CRPS as Pareto objective) and fire-238 (calibrated PDF output via discrete tokenization).

### App 5: Port to political_engine.py
DRT for state-level political probability prediction. Non-parametric calibration especially valuable for rare events (special elections, upsets) where isotonic calibration has insufficient data. Subgroup-aware via distribution per feature cluster.

## Implementation

```python
# pip install quantile-forest
from quantile_forest import ExtraTreesQuantileRegressor

drt = ExtraTreesQuantileRegressor(n_estimators=200, random_state=42)
drt.fit(X_train, y_train)
# Point estimate (median)
probs = drt.predict(X_test, quantiles=0.5)
# Full distribution (for CRPS/Brier computation)
full_dist = drt.predict(X_test, quantiles=[0.1, 0.25, 0.5, 0.75, 0.9])
```

## Connection to Current Research Pipeline

- fire-236: ScoringBench (CRPS/CRLS proper scoring) — DRT natively optimizes CRPS
- fire-238: Discrete Tokenization — same goal (calibrated PDF) via different architecture
- fire-240: Multicalibration GB — subgroup-aware calibration; DRT adds distributional depth per subgroup
- S22 ET-0.21908 candidate — DRT is ET's distributional sibling; same tree structure with calibrated output
- arXiv:2410.21484 (fire-228): ET > RF on 200f validated — DRT is the natural distributional upgrade path

## Work Queue Entry
`vm-research-distributional-regression-trees-fire242` (priority=113)
