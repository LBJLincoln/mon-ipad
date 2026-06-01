# SOTA Research Proposal — fire-244 EVEN WebSearch

**Source:** arXiv:2506.19689 (Jun 2026)
**Title:** "When Can We Reuse a Calibration Set for Multiple Conformal Predictions?"
**Authors:** A.A. Balinsky, A.D. Balinsky
**Venue:** AISTATS 2026

---

## Key Finding

Standard Inductive Conformal Prediction (ICP) requires a fresh calibration set for each prediction task — expensive when calibrating k Pareto models simultaneously. This paper proves that **e-conformal prediction + Hoeffding's inequality** enables repeated reuse of a single calibration set while maintaining distribution-free coverage guarantees.

Core result: using Markov's inequality with a Hoeffding correction, the coverage gap from calibration set reuse is bounded. For k reuses, n calibration samples, target coverage 1-α, and confidence δ:

```
α_corrected = α + sqrt(log(k / δ) / (2 * n))
```

This reduces calibration overhead from **O(k×n)** to **O(n)** for k Pareto models — they share one calibration pass.

---

## Application to Nomos42 Evolution Islands

### Application 1: Multi-Pareto Calibration in engine.py (PRIMARY)
**Current:** Each Pareto model gets a dedicated calibration split of size n/k (wasteful)
**Proposed:** Single shared calibration split of size n, reused for all k models with Hoeffding bound
**Impact:** Each model trains on k× more data → more stable Brier; calibration variance drops by ~1/sqrt(k)

Implementation sketch:
```python
import numpy as np
from nonconformist.cp import IcpClassifier

def hoeffding_corrected_alpha(alpha, n_cal, n_reuses, delta=0.05):
    """Coverage correction for calibration set reuse (arXiv:2506.19689)."""
    return alpha + np.sqrt(np.log(n_reuses / delta) / (2 * n_cal))

def calibrate_pareto_models_shared(pareto_models, X_cal, y_cal, alpha=0.05):
    k = len(pareto_models)
    corrected_alpha = hoeffding_corrected_alpha(alpha, len(X_cal), k)
    results = []
    for model in pareto_models:
        icp = IcpClassifier(model)
        icp.calibrate(X_cal, y_cal)
        p_vals = icp.predict(X_cal, significance=corrected_alpha)
        brier = np.mean((p_vals[:, 1] - y_cal) ** 2)
        results.append({"brier": brier, "alpha_corrected": corrected_alpha})
    return results
```

### Application 2: Temporal CV Fold Reuse (complements fire-230)
Currently each sliding-window fold has its own calibration subset.
Proposed: shared calibration set across all folds with Hoeffding bound.
Impact: larger effective training windows per fold → 0.001-0.002 Brier improvement.

### Application 3: Cross-Island Shared Calibration
When engine parity (Rule #2) is achieved: share calibration sets between S18 and S22.
This enables direct Brier comparison with matched calibration methodology across islands.

### Application 4: Hoeffding Coverage Metric in /api/export
Add `hoeffding_coverage_gap` field to /api/export response:
```json
{
  "hoeffding_coverage_gap": 0.0023,
  "calibration_reuses": 15,
  "calibration_n": 1400,
  "delta": 0.05,
  "alpha_corrected": 0.0723
}
```
Flag models where coverage_gap > 0.01 as calibration quality violations.

### Application 5: Port to political_engine.py
Same Hoeffding correction applies for POL islands when they wake.
Especially valuable for rare political events (low n_cal) — calibration set reuse avoids the n-splitting penalty.

---

## Library
- `crepes` / `nonconformist`: ICP framework (already in research pipeline from fire-168)
- Custom Hoeffding correction wrapper: ~50 lines, no new dependencies

---

## Expected Improvement
- **0.001-0.002 Brier** from larger effective training set (k× more calibration data per model)
- Reduced calibration variance (consistent splits across Pareto models and across fires)
- Reduced computational cost: 1 calibration pass instead of k

---

## Connection to Existing Research
| Related Paper | Fire | Connection |
|---|---|---|
| arXiv:2510.07185 | 168 | Split Conformal Calibration — foundation for ICP methodology |
| arXiv:2505.12578 | 216 | Stacked Conformal Prediction — reduces per-model calibration overhead |
| arXiv:2502.05565 | 226 | Multi-Scale CP — calibration reuse benefits all k scales simultaneously |
| arXiv:2602.06773 | 240 | Multicalibration GB — subgroup audit benefits from shared calibration set |
| arXiv:2506.12183 | 230 | Sliding-window CV — complementary: reuse cal set across folds |

---

## Priority
- Work-queue ID: `vm-research-conformal-calibration-reuse-fire244`
- Priority: **114**
- Status: pending (local-vm)
