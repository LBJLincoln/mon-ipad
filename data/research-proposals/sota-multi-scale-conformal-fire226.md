# SOTA Research Proposal: Multi-Scale Conformal Prediction

**Source:** arXiv:2502.05565 (February 2026)
**Title:** Multi-Scale Conformal Prediction: A Theoretical Framework with Coverage Guarantees
**Added:** fire-226 (2026-06-05T00h)
**Priority:** 106

---

## Key Finding

Multi-scale conformal prediction provides finite-sample coverage guarantees at **multiple hierarchical scales simultaneously**. Standard CP gives `P(Y in C(X)) >= 1-alpha` globally (marginal), but this guarantee can fail at specific sub-populations. Multi-scale CP is simultaneously valid at:

- **Scale 0 (global):** all games
- **Scale 1 (macro):** home/away, playoff vs regular season, back-to-back
- **Scale 2 (meso):** opponent tier, rest-days bucket, travel distance
- **Scale 3 (micro):** recent team form, specific matchup history

Critical for NBA prediction: a model calibrated on all games may under-cover away underdogs on back-to-backs, or over-cover rested home favorites in playoffs.

---

## Applications to Nomos42

### Application 1: NBA Pareto Model Selection at Multiple Scales
Use multi-scale CP intervals to rank GA pareto members. A model achieving coverage at all scales is preferred over one with only marginal coverage.

```python
SCALE_HIERARCHY = {
    'global': lambda df: df,
    'home': lambda df: df[df.is_home == 1],
    'away': lambda df: df[df.is_home == 0],
    'back_to_back': lambda df: df[df.days_rest <= 1],
    'rested': lambda df: df[df.days_rest > 1],
    'playoff': lambda df: df[df.is_playoff == 1],
    'regular': lambda df: df[df.is_playoff == 0],
}
```

### Application 2: Multi-Scale Coverage Pareto Objective
Add `multi_scale_coverage_violation` as 6th Pareto objective in `evaluate_individual()`:
- Target: <= 5% violation across all scales
- Complements: Brier, ROI, Sharpe, features, ECE (fire-172), coverage_violation_rate (fire-216)

### Application 3: Diagnostic Fields in /api/export
```json
{
  "coverage_at_scales": {
    "global": 0.823,
    "home": 0.819,
    "away": 0.831,
    "back_to_back": 0.798,
    "playoff": 0.841
  },
  "multi_scale_violation_rate": 0.03
}
```

### Application 4: Port to POL Islands
Scale hierarchy: election-type (presidential/senate/house) -> district-tier (safe/lean/tossup) -> incumbency x polling_gap.

---

## Relationship to Existing Pipeline

| Paper | Fire | Relationship |
|---|---|---|
| arXiv:2602.19284 Localized CP | fire-224 | Multi-scale extends: structured hierarchy vs single local kernel |
| arXiv:2505.12578 Stacked CP | fire-216 | Complementary: stacked=ensemble; multi-scale=condition heterogeneity |
| arXiv:2510.07185 Split CP | fire-168 | Foundation: multi-scale is generalization of split CP |

---

## Implementation

- **Library:** MAPIE (method='aps') + custom GroupedConformalPredictor wrapper
- **Calibration:** One conformal threshold q_k per scale-level, independently calibrated
- **Model selection:** Select pareto member minimizing max_k(|coverage_k - (1-alpha)|)
- **Expected improvement:** 0.001-0.002 Brier

---

## Work Queue Item

vm-research-multi-scale-conformal-fire226 (priority=106)
