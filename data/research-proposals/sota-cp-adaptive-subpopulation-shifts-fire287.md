# Conformal Prediction Adaptive to Unknown Subpopulation Shifts

**Fire:** 287 (ODD) | **Priority:** 122 | **Date:** 2026-06-07T16h
**Paper:** arXiv:2506.05583 (Jun 2026, AISTATS proceedings)
**Title:** "Conformal Prediction Adaptive to Unknown Subpopulation Shifts"

---

## Key Finding

Standard CP maintains marginal coverage but fails under subpopulation shift — when test data comes from a subgroup systematically different from the calibration set. This paper provides the first adaptive CP method that:

1. **Does NOT require prior knowledge** of subpopulation structure at calibration time
2. Per-test-point filtering and reweighting of calibration scores (k-nearest-neighbor density estimation)
3. Coverage guarantee: P(Y ∈ C(X) | X ∈ S) ≥ 1 - α for any subgroup S (marginal + conditional)
4. Finite-sample correction: adds sqrt(log(2k/δ) / (2k)) to nominal α for coverage validity
5. Complements fixed-group methods (PFGCP fire-268, MOPI fire-272) — no pre-specified subgroups needed

---

## Relevance to NBA Fleet

**Current fleet situation (fire-287 context):**
- S22 c=591: RF-42f/69f dominating, RULE8 CLEAN after 23rd reset. No candidates below gate.
- S18 c=1063: 44th reset IMMINENT, RULE8 stacking PERSISTS.
- evo4 c=1522: LR-47f best at 0.22169. RF-0.22007 evicted at 55th reset.
- evo5 c=1799: CatBoost-50f at 0.22126. 49th reset IMMINENT.

**NBA subpopulation shifts that harm calibration:**
- Playoff vs regular season (different pace, defense intensity)
- Back-to-back games (fatigue creating distribution shift)
- Travel extremes (3+ time zones, >3000 miles)
- Star player injury mid-season (roster composition shift)
- Season phase transitions (early vs mid vs late season momentum)

Standard isotonic calibration on Pareto models uses global calibration set — subgroups like "playoff back-to-backs" have systematically different score distributions, causing coverage failures exactly when calibration matters most.

---

## Application Plan

### Application 1: Pre-Promotion Audit
Before promoting any island model (e.g., future S22 ET/RF below 0.22085):
- Run adaptive CP audit: split calibration set → k-NN reweighted coverage per subgroup
- Gate: adaptive_coverage_gap < 0.05 for all subgroups
- ~50 lines using sklearn.neighbors.NearestNeighbors + scipy.stats.binom_test

### Application 2: engine.py Integration
Add `adaptive_cp_audit()` to `validate_model()` in `features/engine.py`:
```python
def adaptive_cp_audit(model, X_cal, y_cal, X_test, alpha=0.05, k=50):
    # 1. KNN density ratio estimation between test and calibration
    # 2. Reweight calibration scores by density ratio
    # 3. Compute weighted quantile as coverage threshold
    # 4. Return adaptive_coverage_gap metric
```

### Application 3: Pareto Objective
Add `adaptive_coverage_gap` as 12th Pareto objective in NSGA-II evolution loop:
- Forces GA to find models calibrated well across all game subgroups, not just on average
- Gate: adaptive_coverage_gap < 0.05 (similar to existing ECE gate)

### Application 4: Island-Level Monitoring
Add `subpopulation_shift_alert` to `/api/export`:
- Compute adaptive coverage gap on each island's recent prediction set
- Alert if gap > 0.10 → island's calibration degrading under distribution shift

### Application 5: Political Alpha
Port to `political_engine.py`:
- Subgroups: battleground vs safe states, presidential vs midterm, open seat vs incumbent
- Especially relevant for rare-event political races (natural distribution shift from pre-election to election-day)

---

## Library Requirements

```python
# All in sklearn/scipy — no new dependencies
from sklearn.neighbors import NearestNeighbors
import scipy.stats
import numpy as np

def adaptive_cp_coverage(nonconformity_scores_cal, weights, y_cal, alpha=0.05):
    """k-NN reweighted conformal prediction coverage."""
    # Weighted quantile of calibration scores
    sorted_idx = np.argsort(nonconformity_scores_cal)
    cumsum = np.cumsum(weights[sorted_idx])
    threshold = nonconformity_scores_cal[sorted_idx][cumsum >= (1 - alpha)][0]
    return threshold
```

**Expected improvement:** 0.001-0.002 Brier (prevents promoting conditionally miscalibrated candidates)
**Finite-sample correction factor:** sqrt(log(2k/δ) / (2k)) ≈ 0.05 for k=50, δ=0.05

---

## Implementation Priority

**Priority within existing pipeline:** 122 (between fire-264 Pseudo-Calibrated CP at 121 and fire-268 Multi-Agent CP at 123)

**Recommended implementation sequence:**
1. Implement `adaptive_cp_audit()` in `calibration/isotonic_calibrator.py` (~50 lines)
2. Add gate to `/api/checkpoint` endpoint: only checkpoint if adaptive_coverage_gap < 0.05
3. Add as monitoring metric to `/api/export`
4. Port to `political_engine.py`

**VM work-queue entry:** vm-research-cp-adaptive-subpopulation-fire264 (priority=122, pending)

---

## Connection to Existing Research

This paper bridges:
- **PFGCP** (fire-268, priority=125): Fixed subgroups with parameter-free adaptation → use adaptive CP when subgroup structure is unknown, PFGCP when subgroups are known
- **MOPI** (fire-272, priority=129): Shape-adaptive conditional coverage via minimax optimization → MOPI + adaptive CP as complementary post-hoc wrappers
- **CPA/CVI** (fire-280, priority=132): Conditional Validity Index audits → adaptive CP provides the fix for CVI failures

**Key advantage over CVI audit (fire-280):** CVI tells you WHERE calibration fails; adaptive CP FIXES it without retraining.
