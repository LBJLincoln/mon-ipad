# SOTA Proposal: Tabular Foundation Models for Conditional Density Estimation
**Fire**: 246 (EVEN WebSearch)
**Date**: 2026-06-08T08h
**Source**: arXiv:2603.26611 (Mar 2026) — "Benchmarking Tabular Foundation Models for Conditional Density Estimation in Regression"

## Key Finding
TabPFN and TabICL benchmarked on 39 real-world datasets using **6 proper evaluation metrics**:
1. **Brier Score** — binary calibration (current sole objective in Nomos42 fleet)
2. **CRPS** — Continuous Ranked Probability Score
3. **CRLS** — Continuous Ranked Log Score (tail calibration)
4. **Log-Score** — log-likelihood of true outcome
5. **Interval Score** — sharpness + coverage at 90% CI
6. **Calibration Error** — ECE-equivalent for predictive distributions

**Critical insight**: Model rankings shift substantially depending on which scoring rule is used. A model winning on Brier may lose on CRPS or CRLS. Current Nomos42 fleet uses only Brier as primary Pareto objective — missing 5 of 6 proper scoring metrics. This creates selection bias toward Brier-overfit candidates.

## Relevance to Active Candidates (fire-246)
- **S18 RF-200f-0.21949** (EXTREME URGENT, 6bp below fleet best): Brier is impressive but CRPS/CRLS validation needed before fleet-best promotion claim
- **S22 ET-0.2193** (EXTRAORDINARY, 8bp below fleet best at g=66): ET is known to produce better predictive distributions than XGB (calibration advantage from tree variance) — CRPS/CRLS evaluation would confirm this is not a Brier-overfit artifact

## Applications

### Application 1: Multi-Metric /api/export
Add all 6 proper scoring metrics to `/api/export` output:
```python
from properscoring import crps_ensemble, crps_gaussian
from netcal.metrics import ECE

export_metrics = {
    "brier": brier_score_loss(y_true, y_pred),
    "crps": crps_gaussian(y_true, y_pred, 0.5).mean(),
    "crls": crls_score(y_true, y_pred),       # custom or properscoring
    "log_score": -log_loss(y_true, y_pred),
    "interval_score_90": interval_score(y_true, q05, q95, alpha=0.1),
    "calibration_error": ECE(bins=10).measure(y_pred, y_true)
}
```

### Application 2: Multi-Metric Pareto Frontier
Extend current `[brier, roi, sharpe, ece]` to include CRPS:
```python
pareto_objectives = ["brier", "roi", "sharpe", "ece", "crps", "calibration_error"]
```
Expected: Eliminates Brier-overfit candidates; ET models tend to win on CRPS (matches S22 ET-0.2193 hypothesis).

### Application 3: Validate S18/S22 Extreme Urgent Candidates
Before promoting RF-200f-0.21949 (S18) or ET-0.2193 (S22) to fleet-best:
1. Run `curl /api/export` to get all 6 metrics
2. Confirm candidate wins on ≥4/6 metrics vs current fleet best S15 RF-0.22012
3. Only promote to fleet-best if multi-metric validation passes

### Application 4: TabICLv2 Re-Evaluation
Re-run Colab TabICL benchmark (186f NBA, 11440 games) with TabICLv2:
- Use all 6 proper scoring metrics for comparison table
- TabICLv2 native distributional calibration is expected to improve CRPS/CRLS over TabICL
- Could beat current best 0.21139 holdout on multi-metric basis
- Complements fire-236 (ScoringBench) and fire-238 (Discrete Tokenization)

### Application 5: Port to political_engine.py
Rare-event political races (competitive margins <5%) benefit most from CRLS (tail calibration):
```python
# Add to political_engine.py validation loop
pol_metrics = {
    "brier": brier_score_loss(y_true, y_pred),
    "crps": crps_gaussian(y_true, y_pred, 0.5).mean(),
    "crls": crls_score(y_true, y_pred),
    "calibration_error": ECE(bins=10).measure(y_pred, y_true)
}
```
Especially useful for P1 ALL-TIME RECORD 0.24902 validation when it wakes.

## Expected Improvement
- **Brier**: 0.001-0.003 (density-calibrated model selection eliminates Brier-overfit)
- **CRPS/CRLS**: Significant improvement (metrics where tabular FMs have natural advantage)
- **Pareto quality**: Multi-metric frontier is more trustworthy than single-metric

## Implementation
```bash
pip install properscoring netcal tabicl --upgrade
```

## Related Work in Active Pipeline
| Fire | Paper | Priority | Status |
|------|-------|----------|--------|
| fire-236 | arXiv:2603.29928 ScoringBench TabICLv2 vs TabPFNv2.5 | 110 | pending |
| fire-238 | arXiv:2603.07448 Discrete Tokenization Transformer | 111 | pending |
| fire-242 | arXiv:2502.05157 Distributional Regression Trees | 113 | pending |
| fire-244 | arXiv:2506.19689 Calibration Set Reuse (Hoeffding) | 114 | pending |
| **fire-246** | **arXiv:2603.26611 TabFM 6-Metric Density Benchmark** | **115** | **THIS** |

## Work Queue Entry
- ID: `vm-research-tabular-fm-density-estimation-fire246`
- Priority: 115
- Status: pending (VM executes)

## Port to POL
When POL islands wake, apply multi-metric 6-scoring-rule validation before any LightGBM/ET promotions:
- P1 ALL-TIME RECORD 0.24902: must validate on CRPS/CRLS before fleet-best claim
- P4 FLEET BEST 0.2497: same validation required
- New Pareto objectives apply directly to political_engine.py
