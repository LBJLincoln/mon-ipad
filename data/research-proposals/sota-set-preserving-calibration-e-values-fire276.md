# SOTA Research Proposal: Set-Preserving Calibration from Conformal P-Values to E-Values

**Source:** arXiv:2606.03600 (Jun 2026)
**Title:** "Set-Preserving Calibration from Conformal P-Values to E-Values"
**Fire:** 276 (EVEN WebSearch)
**Priority:** 131
**Work-queue ID:** vm-research-set-preserving-e-values-fire276

---

## Key Finding

Develops an e-value formulation that enables principled use of e-value merging and
randomization in cross-conformal prediction and conformal aggregation. The e-value-based
calibration satisfies the desired 1-α coverage guarantee while improving efficiency over
standard p-value baselines. "Set-preserving" means the prediction sets from conformal
p-values are mapped to e-values WITHOUT losing information from the original set structure.

**Why e-values matter:**
- Anytime-valid: no need to fix calibration sample size in advance
- Multiplicative merging across heterogeneous sources WITHOUT independence assumption
  (Fisher's p-value combination requires independence; e-values do not)
- Sequential model promotion: can evaluate evidence incrementally per-fire
- Direct connection to Kelly criterion: e-values = likelihood ratios = natural betting framework

---

## Applications for Nomos42

### Application 1: E-Value Calibration Wrapper (engine.py)
Replace isotonic calibration in `validate_model()` with e-value calibration wrapper:
```python
# calibration/e_value_calibrator.py (~40 lines)
def fit_e_value_calibrator(scores, labels):
    """Map conformal p-values to e-values (set-preserving)."""
    from scipy.stats import rankdata
    n = len(scores)
    # conformal p-values: p_i = #{j: score_j >= score_i} / n
    p_values = 1 - rankdata(scores, method='max') / n
    # set-preserving e-values: e_i = 1/p_i * (coverage indicator)
    e_values = np.where(labels == 1, 1.0 / np.maximum(p_values, 1/n), 0.0)
    return e_values.mean()  # joint e-value
```

### Application 2: Cross-Island Evidence Aggregation
Multiply e-values from S18/S22/evo4/evo5 to get joint e-value for fleet-best claim.
Replaces ad-hoc rank-averaging with principled anytime-valid test:
```python
# In predict_today.py — multi-island e-value fusion
joint_e_value = e_s18 * e_s22 * e_evo4 * e_evo5  # valid without independence
# Add to /api/export:
{"joint_e_value": joint_e_value, "fleet_best_claim_valid": joint_e_value > threshold}
```

### Application 3: E-Value-Based Consensus Distance (Mech C)
Replace split-CP KL-divergence in `compute_consensus_distance()` with e-value distance:
- Anytime-valid KL bounds without splitting calibration data per-fire
- Enables running KL estimate per-fire rather than per-calibration-batch
- Directly compatible with COMMON_KNOWLEDGE[D] block (Mech A)

### Application 4: E-Value Stopping Criterion for Evolution
Island stops queuing /api/checkpoint candidates when joint_e_value < threshold (1.0 = null,
> 1.0 = evidence for improvement). Replaces field-lag heuristic with principled early stopping:
```python
# In island app.py checkpoint logic
if compute_joint_e_value(current_pareto, baseline_brier=0.22085) > 5.0:
    save_checkpoint()  # strong evidence of improvement
```

### Application 5: Political Engine Port
E-value merging for rare POL event calibration (election night label corrections = exactly
the "corrupted feedback" case where anytime-valid testing is critical).
Complements arXiv:2605.20515 (priority=118, robust ACI under corrupted feedback):
- Use e-value calibration for P4/P5/P7 POL islands
- Election night corrections don't require recalibration from scratch
- Anytime-valid sequential testing across P4/P5/P7 for POL fleet-best claim

---

## Implementation Plan

1. Add `calibration/e_value_calibrator.py` (~40 lines, scipy.stats only)
2. Add `calibration_method='e_value'` option to `validate_model()` in engine.py
3. Add `joint_e_value` field to `/api/export` schema
4. Update `compute_consensus_distance()` to optionally use e-value distance
5. Port to `political_engine.py` (same wrapper)

**Dependencies:** scipy.stats (already available — no new deps)

**Expected improvement:** 0.001-0.002 Brier + anytime-valid island promotion + principled multi-island fusion

---

## Connection to Existing Pipeline

| Existing research | How e-values complement |
|---|---|
| arXiv:2606.00419 (priority=125) — Parameter-Free Group OCP | E-values provide anytime-valid group-conditional bounds |
| arXiv:2605.20515 (priority=118) — Online CP Corrupted Feedback | E-values are robust to corrupted labels (same domain) |
| arXiv:2605.12341 (priority=130) — Multi-Variable CP | E-value merging extends MV-CP to multi-island setting |
| arXiv:2602.03168 (priority=119) — Universal Portfolio OCP | E-values = log-optimal betting = unified framework |
| Axelrod Mech C — compute_consensus_distance | E-value KL-div replaces split-CP in consensus tracking |
