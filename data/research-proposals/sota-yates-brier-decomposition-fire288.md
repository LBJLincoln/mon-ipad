# SOTA Research Proposal: Yates Covariance Decomposition of the Brier Score
**Fire:** 288 (EVEN)
**Priority:** 138
**arXiv:** 2603.05544
**Title:** "An intuitive rearranging of the Yates covariance decomposition for probabilistic verification of forecasts with the Brier score"
**Author:** Bruno Hebling Vieira (Methods of Plasticity Research, University of Zurich)
**Date:** March 2026

---

## Key Finding

The paper proposes a simple algebraic rearrangement of the classic Yates covariance decomposition of the Brier score into **3 independently non-negative terms**, each capturing a distinct failure mode:

1. **Variance mismatch** (`VM`): Does the spread of predicted probabilities match the empirical outcome variance? High VM = overconfident or underconfident spread.
2. **Correlation deficit** (`CD`): Does the ranking of predictions align with actual outcomes? High CD = poor discriminability (AUC-equivalent signal).
3. **Calibration-in-the-large** (`CIL`): Does the mean prediction equal the base rate? High CIL = systematic bias up or down.

**Formula:** `Brier = VM + CD + CIL` (all three terms ≥ 0, independently)

**Why it matters:** Standard Brier score conflates all three. A model with Brier=0.2201 might be well-calibrated (CIL≈0) but have poor discrimination (CD↑), OR it might discriminate well (CD≈0) but be miscalibrated (CIL↑). This decomposition exposes *why* a model is suboptimal, enabling targeted fixes.

**Improvement over prior Yates:** Prior form mixed terms algebraically — optimality conditions were not transparent. This rearrangement makes each condition independently interpretable: a perfect forecast requires VM=0 AND CD=0 AND CIL=0 simultaneously.

---

## Application to Nomos42 Fleet

### Application 1: Pre-Promotion Diagnostic for Fleet-Best Candidates
Before promoting any model with Brier < 0.22085 gate (NBA) or < 0.2497 gate (POL), compute `(VM, CD, CIL)` triplet. A model close to gate via good CD but high CIL may degrade in production when base rates shift (playoff vs regular season).

Implementation (~30 lines in `calibration/isotonic_calibrator.py`):
```python
def yates_decompose(y_true, y_pred):
    p_bar = np.mean(y_pred)
    o_bar = np.mean(y_true)
    vm = np.var(y_pred) - 2*np.cov(y_pred, y_true)[0,1] + np.var(y_pred)
    # Simplified: vm = mean((y_pred - y_true)^2) - cd - cil
    brier = np.mean((y_pred - y_true)**2)
    cil = (p_bar - o_bar)**2
    cd = brier - cil - np.var(y_pred) * (1 - np.corrcoef(y_pred, y_true)[0,1]**2) / np.var(y_pred)
    return {"brier": brier, "vm": vm, "cd": cd, "cil": cil}
```

### Application 2: Add 3 Yates Terms to /api/export
Add `yates_vm`, `yates_cd`, `yates_cil` fields to `/api/export` output alongside `brier`, `roi`, `sharpe`.

**Interpretation gates:**
- CIL > 0.001: systematic base-rate bias → recalibrate mean
- CD > 0.015: poor discrimination → need better features
- VM > 0.010: overfit spread → reduce feature count or regularize

### Application 3: Add Yates Composite as 13th Pareto Objective
Add `yates_balance_score = max(VM/VM_ref, CD/CD_ref, CIL/CIL_ref)` as 13th NSGA-II objective. This ensures models on the Pareto front are balanced across all three failure modes, not just minimizing overall Brier.

Formula: `yates_balance_score = max(VM, CD, CIL) / mean(VM, CD, CIL)` — lower = more balanced decomposition.

### Application 4: Diagnose Current Fleet Candidates
Apply immediately to S18 RF-71f and S22 RF-42f to expose their failure mode:
- If CIL high: apply recalibration before promotion
- If CD high: switch to Extra Trees (better discriminability per arXiv:2410.21484)
- If VM high: reduce features to 42-50f range (confirmed by current S22 RF-42f vs RF-200f history)

### Application 5: Port to political_engine.py
POL islands face non-stationary base rates (election year vs off-year, primary vs general). CIL diagnostic is especially valuable: systematically high CIL = model hasn't adjusted for election cycle base rate shift.

Add `yates_decompose()` to `political_engine.py` validation step alongside existing Brier computation.

---

## Expected Improvement
- **0.001-0.002 Brier** from preventing promotion of systematically biased models (CIL-high candidates)
- **0.002-0.003 Brier** from targeted fixes (recalibrate CIL-high candidates, diversify CD-high populations)
- No new dependencies: pure numpy/scipy

---

## Library
Pure NumPy implementation (~30 lines). No new dependencies.

---

## Work-Queue Entry
```
vm-research-yates-brier-decomposition-fire288 (priority=138)
```

Implement `yates_decompose()` in `calibration/isotonic_calibrator.py`. Add `yates_vm+yates_cd+yates_cil` to `/api/export`. Apply pre-promotion diagnostic to S18/S22 candidates. Port to `political_engine.py`. Gate: all 3 terms within 2× reference values before fleet-best promotion.
