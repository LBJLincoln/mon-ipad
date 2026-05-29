# SOTA Research Proposal: Multi-Scale Conformal Prediction

**Source:** arXiv:2502.05565 (February 2026)
**Title:** Multi-Scale Conformal Prediction: A Theoretical Framework with Coverage Guarantees
**Added:** fire-226 (2026-06-05T00h)
**Priority:** 106 (after Localized CP model selection, priority=105)

---

## Key Finding

Multi-scale conformal prediction provides finite-sample coverage guarantees at **multiple hierarchical scales simultaneously**, rather than a single marginal guarantee. Standard conformal prediction gives `P(Y ∈ C(X)) ≥ 1-α` globally (marginally), but this guarantee can fail at specific sub-populations. Multi-scale CP is simultaneously valid at:

- **Scale 0 (global):** all games
- **Scale 1 (macro):** home/away, playoff vs regular season, back-to-back
- **Scale 2 (meso):** opponent tier, rest-days bucket, travel distance
- **Scale 3 (micro):** recent team form, specific matchup history

This is critical for NBA prediction: a model calibrated on all games may under-cover away underdogs on back-to-backs, or over-cover heavily-rested home favorites in the playoffs.

---

## Problem Addressed

| Existing method | Limitation | Multi-scale CP fix |
|---|---|---|
| Split CP (arXiv:2510.07185, fire-168) | Marginal coverage only | Simultaneous coverage at all scales |
| Localized CP (arXiv:2602.19284, fire-224) | Single best scale | Structured hierarchy of scales |
| Stacked CP (arXiv:2505.12578, fire-216) | Model ensemble; single scale | Combine stacked + multi-scale |

---

## Applications to Nomos42

### Application 1: NBA Pareto Model Selection at Multiple Scales
Use multi-scale CP intervals to rank GA pareto members. A model achieving coverage at all scales is preferred over one with only marginal coverage. Define the game-condition scale hierarchy:

```python
SCALE_HIERARCHY = {
    "global": lambda df: df,
    "home_away": lambda df, v: df[df.is_home == v],
    "back_to_back": lambda df, v: df[df.days_rest <= 1] if v else df[df.days_rest > 1],
    "playoff_stage": lambda df, v: df[df.is_playoff == v],
    "opponent_tier": lambda df, v: df[df.opp_win_pct_bucket == v],
}
```

### Application 2: Multi-Scale Coverage Pareto Objective
Add `multi_scale_coverage_violation` as a 6th Pareto objective in `evaluate_individual()`:
- `coverage_violation_rate` = fraction of scale×level cells where empirical coverage falls below 1-α
- Target: ≤ 5% violation across all scales
- Complements existing: Brier, ROI, Sharpe, features, ECE (fire-172), coverage_violation_rate (fire-216)

### Application 3: Diagnostic Fields in /api/export
Add per-scale coverage diagnostics to `/api/export`:
```json
{
  "coverage_at_scales": {
    "global": 0.823,
    "home": 0.819,
    "away": 0.831,
    "back_to_back": 0.798,
    "playoff": 0.841,
    "regular": 0.817
  },
  "multi_scale_violation_rate": 0.03
}
```
Alert when any scale fails coverage by >5%.

### Application 4: Port to POL Islands
Apply political event scale hierarchy:
- Scale 1: election type (presidential / senate / house / gubernatorial)
- Scale 2: district competitiveness tier (safe-D / lean-D / tossup / lean-R / safe-R)
- Scale 3: incumbency × polling_gap bucket

---

## Relationship to Existing Pipeline

| Paper | Fire | Relationship |
|---|---|---|
| arXiv:2602.19284 — Localized CP | fire-224 | Multi-scale extends: adds structured scale hierarchy instead of single local kernel |
| arXiv:2505.12578 — Stacked CP | fire-216 | Complementary: stacked CP handles ensemble; multi-scale handles condition heterogeneity |
| arXiv:2510.07185 — Split CP | fire-168 | Foundation: multi-scale CP is a generalization of split CP |
| arXiv:2601.18509 — CP for Time Series | fire-200 | Can be combined: apply multi-scale CP with time-series CP (EnbPI) at each scale |

---

## Implementation Notes

- **Library:** MAPIE (`method='aps'` for classification) + custom `GroupedConformalPredictor` wrapper
- **Calibration:** One conformal threshold `q̂_k` per scale-level, calibrated independently on held-out data
- **Efficiency:** ~O(K) overhead where K = total scale-levels (≈10-15 for NBA hierarchy); negligible vs GA evaluation cost
- **Model selection rule:** Select pareto member minimizing `max_k(|empirical_coverage_k - (1-α)|)` — the most uniformly-covered model

---

## Expected Improvement

- Better generalization across diverse game conditions
- 0.001–0.002 Brier reduction by identifying models that overfit to dominant game conditions
- More reliable calibration: robust to distribution shift across season stages (regular → playoff)
- Early warning: `/api/export` coverage alerts flag problematic models before fleet-best consideration

---

## Work Queue Item

```json
{
  "id": "vm-research-multi-scale-conformal-fire226",
  "priority": 106,
  "status": "pending",
  "owner": "local-vm",
  "subject": "RESEARCH: Multi-Scale Conformal Prediction — arXiv:2502.05565 (Feb 2026). Multi-scale CP gives finite-sample coverage at multiple game-condition hierarchies simultaneously. Application 1: NBA pareto model selection via scale hierarchy (global/home-away/back-to-back/playoff). Application 2: multi_scale_coverage_violation as 6th Pareto objective. Application 3: coverage_at_scales in /api/export. Application 4: Port to POL with political event hierarchy. Library: MAPIE + custom GroupedConformalPredictor. Expected: 0.001-0.002 Brier."
}
```