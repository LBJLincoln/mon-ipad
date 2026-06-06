# SOTA: Multi-Variable Conformal Prediction without Data Splitting
**Paper:** arXiv:2605.12341 (May 2026)
**Title:** "Multi-Variable Conformal Prediction: Optimizing Prediction Sets without Data Splitting"
**Priority:** 130 (pipeline fire-274)
**Fire:** 285 ODD — 2026-06-07T08h

---

## Summary

Standard split-CP reserves a held-out calibration set — reducing effective training data and introducing variance across calibration runs. This paper extends CP to **vector-valued score functions** (multiple calibration metrics simultaneously), eliminating the data-split overhead while achieving prediction set sizes ≤ split-CP baselines.

Two variants:
- **RemMCP** (Constraint Removal): convex case. Removes redundant scalar CP constraints one at a time; O(k log k) over k objectives. Suitable for Brier+ECE+ROI+Sharpe in NSGA-II.
- **RelMCP** (Iterative Relaxation): non-convex case. Iterates over a relaxation grid to find minimal valid prediction set. Suitable for asymmetric election-outcome scores in POL.

Key guarantees:
1. Simultaneous valid marginal coverage for all k metrics — no per-metric calibration split.
2. Prediction set sizes ≤ split-CP baselines (RemMCP equal; RelMCP strictly smaller when non-convex support exploited).
3. Lower variance across calibration runs — especially valuable for data-scarce late-season NBA and rare political events.

---

## Why This Matters for Nomos42

### Problem: Sequential calibration wastes data and compounds errors
Current engine.py pipeline:
1. Split calibration set for isotonic calibration → loses 10-20% training data
2. Split again for ECE estimation → reduces calibration sample size
3. Split again for CRPS/CRLS (priority=115) → further reduction

MV-CP collapses all three into a single pass over the **unsplit full training set**, with formal coverage guarantees for (Brier, ECE, CRPS) simultaneously. No per-metric calibration sets needed.

### The S22 ET-0.2191 and evo4 RF-0.22007 case
Both candidates are ~10bp below fleet best but lack multi-metric coverage validation. MV-CP would provide a single joint validation step — if they pass the RemMCP audit under (Brier+ECE+CRPS), promotion is justified. Currently only Brier is checked (via arXiv:2605.17269 U-calibeating, priority=136), leaving ECE and CRPS unchecked.

---

## Applications

### Application 1: Simultaneous multi-metric calibration in engine.py
**File:** `features/engine.py` — `validate_model()` function

```python
# Current: sequential calibration (3 separate splits)
brier = compute_brier(y_true, y_pred)
ece = compute_ece(y_true, y_pred)  # separate split
crps = compute_crps(y_true, y_pred)  # another split

# MV-CP replacement: single pass, no splits
from calibration.mv_cp import RemMCPCalibrator
calibrator = RemMCPCalibrator(
    objectives=['brier', 'ece', 'crps'],
    alpha=0.1
)
calibrator.fit(y_true, y_pred)  # uses full unsplit dataset
coverage = calibrator.predict_set_sizes()  # vector: (brier_cov, ece_cov, crps_cov)
```

**Implementation:** `calibration/mv_cp.py` (~80 lines, scipy.optimize + numpy)
- `RemMCPCalibrator`: convex variant for NBA pareto (3 objectives: Brier+ECE+CRPS)
- `RelMCPCalibrator`: non-convex variant for POL (asymmetric election scores)
- No new dependencies beyond existing scipy/numpy

### Application 2: Multi-variable Pareto frontier in NSGA-II
**File:** `hf-space/app.py` — NSGA-II evolution loop (~30 lines)

Replace per-objective calibration splits in the Pareto ranking with RemMCP joint evaluation:
- Current: each of (Brier, ROI, Sharpe, ECE) requires separate calibration set → 4× calibration overhead per generation
- MV-CP: single calibration step for all 4 objectives → 4× throughput improvement per generation

This directly helps data-scarce islands (S22 3rd run started fresh at c=5 — every calibration sample counts).

### Application 3: Replace split-CP in `compute_consensus_distance`
**File:** `hf-llm-trading-floor/app.py` line ~3863 (NBA), `hf-political-trading-floor/app.py` line ~2521 (POL)

`compute_consensus_distance` currently computes a scalar KL-div distance from consensus. With MV-CP, replace with a vector-valued nonconformity score `(kl_div, eccentricity, prediction_volatility)` calibrated jointly — agents with simultaneous outlier status on all 3 dimensions trigger the DMAD anti-groupthink gate more reliably.

```python
# MV-CP consensus distance (replaces scalar KL-div)
def compute_consensus_distance(preds, consensus, calibrator_mv):
    scores = np.array([
        kl_divergence(p, consensus) for p in preds
    ])
    return calibrator_mv.nonconformity_vector(scores)  # 3D vector
```

### Application 4: Port to `political_engine.py`
- RelMCP non-convex variant handles asymmetric binary election scores (P(win) vs P(loss) have different calibration requirements by incumbency status)
- Simultaneous calibration for (Brier, ECE, political_upset_rate) in P4/P7 validation
- Critical for P2 history brier=0.24903 promotion check — joint calibration with ECE avoids the Brier-overfit trap

---

## Implementation Roadmap

1. `calibration/mv_cp.py` — RemMCPCalibrator + RelMCPCalibrator (~80 lines)
2. `features/engine.py` — update `validate_model()` to accept `calibration_method='mv_cp'` param (~10 lines)
3. `hf-space/app.py` — update NSGA-II Pareto ranking to use MV-CP joint objectives (~30 lines)
4. `hf-llm-trading-floor/app.py` — update `compute_consensus_distance` to return MV vector (~20 lines, parity with POL)
5. `hf-political-trading-floor/app.py` — same as #4 (RelMCP variant for POL asymmetric scores)

**Total:** ~220 lines across 5 files.
**Gate:** After priority=136 (U-calibeating audit gate), priority=135 (CalArena router), priority=134 (Venn-Abers swap).

---

## Expected Impact

| Metric | Current | MV-CP | Delta |
|--------|---------|-------|-------|
| Calibration data utilization | 70-80% | 100% | +20-30% |
| Prediction set size vs split-CP | 1.0× | 0.8-1.0× | smaller or equal |
| CV variance (calibration fold) | high | low | |
| Brier improvement | 0.22012 | 0.2199-0.2201 est. | 0.001-0.002 |
| Calibration steps per Pareto eval | 4 | 1 | 4× faster |

**Estimated Brier improvement:** 0.001-0.002 (mainly from data-efficiency gain in late-season and data-scarce islands; smaller prediction intervals under non-stationary game conditions).

---

## References

- arXiv:2605.12341 (May 2026): "Multi-Variable Conformal Prediction: Optimizing Prediction Sets without Data Splitting"
- MAPIE library: `pip install mapie` (already in pipeline)
- scipy.optimize (no new dependencies)
- Complements: arXiv:2506.19689 (calibration set reuse, priority=114) + arXiv:2601.18509 (CP time series, priority=95)
