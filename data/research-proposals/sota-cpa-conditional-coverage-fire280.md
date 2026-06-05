# SOTA Proposal: Conformal Prediction Assessment (CPA/CVI) for Conditional Coverage Validation

**Fire**: fire-280 (EVEN)
**arXiv**: 2603.27189
**Priority**: 132
**Date**: 2026-06-06T12h

## Paper

"Conformal Prediction Assessment" (CPA) — Mar 2026

**Key finding**: CPA is a post-hoc framework to assess whether *any* CP method achieves conditional (feature-conditional) validity on a given dataset. The CVI (Conditional Validity Index) score quantifies the gap between marginal and conditional coverage across arbitrary subgroups — without requiring knowledge of the subgroup structure. Works as a wrapper around any pre-trained CP interval: feed in test points, get back a scalar CVI ∈ [0,1] where 0 = perfectly conditionally valid, 1 = maximally conditionally invalid. Paper validates across 40+ real-world tabular datasets; finds that most off-the-shelf CP methods achieve marginal coverage but fail conditional validity (CVI > 0.1) on structured subpopulations.

## Relevance to Nomos42

### Critical Application: Pre-Promotion Audit for S18/S22 Fleet-Best Candidates

Current promotion gate (Rule #5): brier < 0.22085 → CHECKPOINT. But a model with good marginal Brier may fail conditional calibration on:
- Playoff vs. regular season (structural distribution shift)
- Back-to-back games (fatigue-driven miscalibration)
- High-altitude venues, extreme rest disparities
- Early/late season (roster construction phase vs. stable rosters)

**CPA/CVI audit**: Before promoting any fleet-best candidate (S22 ET-0.2191, evo4 RF-0.22007, S18 next candidate), compute CVI score on held-out test set. If CVI > 0.10 → flag for conditional recalibration before production.

### Application 1: CVI Gate in /api/checkpoint Promotion Logic

Add CVI computation to `engine.py` checkpoint wrapper:
```python
from calibration.cpa_calibrator import compute_cvi
cvi = compute_cvi(model, X_test, y_test, alpha=0.1)
if cvi > 0.10:
    flag_conditional_miscalibration(model_id, cvi)
# Still checkpoint, but flag for downstream recalibration
```
Add `cvi_score` to `/api/export` output alongside brier/roi/sharpe.

### Application 2: Island-Level CVI Monitoring

Add `conditional_validity_index` as 11th Pareto objective in NSGA-II:
- Subgroups: venue × back_to_back × season_phase × fatigue_index × playoff_round
- Models with CVI > 0.10 are penalized in Pareto ranking — prevents conditionally miscalibrated models from dominating the frontier

### Application 3: S22 ET-0.2191 Pre-Production Validation

Before S22 ET-0.2191 reaches production (if it survives 18th reset):
1. Compute CVI on 2025-26 season holdout (back-to-back + playoff subsplit)
2. Compare CVI vs. current S15 RF-75f fleet-best baseline
3. If ET-0.2191 CVI < S15 CVI → conditional calibration is also superior → stronger promotion case

### Application 4: POL Cross-Domain Conditional Validity

Political predictions fail conditional calibration across:
- Primary vs. general elections (different voter turnout models)
- Competitive vs. non-competitive districts
- Incumbency × district_type × cycle_type

Add `political_cvi_score` to POL island `/api/export`. Gate: CVI < 0.15 for political predictions (higher threshold than NBA due to smaller calibration set).

### Application 5: Axelrod COMMON_KNOWLEDGE[D] Enhancement

Add `cvi_score` per island to `build_common_knowledge()` in Mech A block:
```python
COMMON_KNOWLEDGE["D"]["island_cvi_scores"] = {
    "s22": s22_cvi, "evo4": evo4_cvi, "s18": s18_cvi
}
```
Agents with high CVI (conditionally miscalibrated) weighted down in consensus distance computation.

## Implementation

**Library**: MAPIE (conditional coverage diagnostic) + scipy.stats + sklearn.tree
- CVI computation: decision-stump function class over test set subgroups (~40 lines)
- No new dependencies (scipy/sklearn already available)
- Wraps around any pre-fitted model + calibration set

**Work-queue**: `vm-research-cpa-conditional-coverage-fire280` (priority=132)

**Expected improvement**: 0.001-0.002 Brier (prevents promoting conditionally miscalibrated models that degrade in production) + formal audit trail for each fleet-best candidate.

## Connection to Existing Pipeline

- Extends fire-268 PFWCP (priority=123) — complements personalized per-agent coverage with dataset-level CVI audit
- Extends fire-268 MOPI (priority=129) — MOPI optimizes conditional gap; CPA measures the resulting gap post-hoc
- Extends fire-268 PivotalScoreCP (priority=126) — pivotal scores achieve conditional coverage; CPA verifies they succeeded
- Direct validation for S22 ET-0.2191 before production promotion
