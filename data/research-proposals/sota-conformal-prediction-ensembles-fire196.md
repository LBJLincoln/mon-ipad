# SOTA Research Proposal: Conformal Prediction for Ensembles via Score-Based Aggregation

**Source:** arXiv:2405.16246 — "Conformal Prediction for Ensembles: Improving Efficiency via Score-Based Aggregation"  
**Fire:** fire-196 (EVEN WebSearch, 2026-05-30T22h)  
**Priority:** 38 (vm-research-conformal-prediction-ensembles-fire196)  
**Also:** MDPI-2079-3197/13/10/230 — LR Brier=0.199 NBA 2024 (validates calibration-first)

---

## Summary

This paper proposes a framework extending standard scalar conformal prediction to a **multivariate score function** for ensemble models. When aggregating predictions from multiple ensemble members (e.g., the island Pareto front across S18/S22), using a multivariate score captures the joint uncertainty structure and produces **smaller, more efficient prediction regions** while maintaining marginal coverage guarantees.

## Relevance to Nomos42

Our GA islands produce Pareto fronts with 10-20 non-dominated models per island. Currently, ensemble aggregation is illegal under Rule#8 (stacking). Score-based conformal aggregation would:

1. **Replace stacking (Rule#8) with a provably valid ensemble method** — same predictive power, no overfitting
2. Provide tighter Brier-calibrated probability intervals than standard conformal prediction
3. Work **post-hoc**: no retraining required, applied to existing Pareto models directly
4. Enable principled cross-island aggregation (S15 RF-75f + S18 ET/LGB + S22 RF-48f)

## Key Technical Points

- Extends conformal prediction score function from scalar to multivariate (multi-model) setting
- Score-based aggregation: combines nonconformity scores from K ensemble members into a single coverage-guaranteed output
- Distribution-free: no parametric assumptions on model or data
- Efficiency: smaller prediction regions vs naive ensemble averaging OR individual conformal models
- Compatible with any base model — wraps around existing island outputs

## Implementation Sketch

```python
# Post-hoc, no retraining needed
# Step 1: Collect calibration nonconformity scores from each pareto model
scores = np.stack([model.predict_proba(X_cal)[:,1] for model in pareto_models])  # (K, N_cal)

# Step 2: Fit multivariate score aggregator
# Paper proposes score-based aggregation via e.g. minimum, product, or learned weight
agg_scores = scores.min(axis=0)  # or weighted mean

# Step 3: Compute quantile threshold for coverage
alpha = 0.1  # 90% coverage
threshold = np.quantile(np.abs(agg_scores - y_cal), 1 - alpha)

# Step 4: Predict with coverage intervals on test set
test_scores = np.stack([model.predict_proba(X_test)[:,1] for model in pareto_models])
agg_test = test_scores.min(axis=0)
prediction_intervals = (agg_test - threshold, agg_test + threshold)
```

## Expected Improvement

- Brier: **0.001-0.003 improvement** over individual model selection from pareto front
- Replaces stacking (Rule#8 violation) with a provably valid ensemble method
- Coverage: marginal frequentist guarantee (distribution-free, no assumptions)
- Key advantage: adaptive to distribution shift (playoff games differ from regular season)

## Dependencies

- Library: `crepes` (already targeted for Venn-Abers, fire-158) or custom numpy/scipy
- No new libraries strictly needed — implementable in ~50 lines of numpy
- Target: S15 RF-75f + S18 ET/LGB Pareto front + S22 Pareto aggregation
- Prerequisite: /api/export working (need model files; currently 404 via WebFetch, VM must curl)

---

## Also Found (MDPI 2079-3197/13/10/230, 2026)

**"Machine Learning for Basketball Game Outcomes: NBA and WNBA Leagues"**

- **Logistic Regression: Brier = 0.199** on NBA 2024 test season
- **XGBoost: Brier = 0.202** on NBA 2024 test season
- **Implication**: LR as a PRIMARY model type achieves Brier 0.199, far below our fleet best 0.22012
- Already consistent with: S22 LR-43f dominating fires 183-188 (calibration-first validated)
- Validates: fire-172 arXiv:2303.06021 calibration-first model selection insight
- Action: Elevate `vm-add-logistic-regression-model-pool` priority; ensure LR present in ALL island MODEL_TYPES on next wake
- Cross-project: Port LR as primary to political_engine.py MODEL_TYPES (P1/P2 missing LR)

---

## Work-Queue Item

```json
{
  "id": "vm-research-conformal-prediction-ensembles-fire196",
  "priority": 38,
  "status": "pending",
  "owner": "local-vm",
  "subject": "PORT SOTA: Implement Conformal Prediction for Ensembles score-based aggregation (arXiv:2405.16246) as post-hoc pareto front aggregator — replaces stacking (Rule#8) with valid ensemble method"
}
```
