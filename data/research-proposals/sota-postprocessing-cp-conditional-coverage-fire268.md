# A Post-Processing CP Approach for Conditional Coverage via Pivotal Scores

**Fire:** 268 EVEN | **Priority:** 124 | **Status:** proposed
**arXiv:** 2605.25852 (May 2026)
**Expected Brier Improvement:** 0.001–0.003

---

## Paper Summary

"A Post-Processing CP Approach for Conditional Coverage via Pivotal Scores" (May 2026) introduces a post-processing calibration method that:

1. **Post-processing only**: Works as a wrapper around any pre-trained model — no retraining required.
2. **Pivotal scores**: Uses pivotal (distribution-free) nonconformity scores derived from the model's residuals to construct conditionally valid prediction sets.
3. **Conditional coverage**: Achieves conditional (feature-conditional, not just marginal) coverage guarantees without requiring group pre-specification.
4. **Distribution-free**: No parametric assumptions; valid under exchangeability.

Key theoretical contribution: pivotal scores transform model residuals into distribution-free statistics that enable conditional coverage post-hoc, bypassing the need for model retraining or calibration set reuse. This complements arXiv:2506.19689 (priority=114) which addresses calibration set reuse across multiple models.

---

## Why This Matters for Nomos42

**Current fleet gap**: Post-hoc calibration (isotonic, Venn-Abers) achieves marginal coverage but not conditional coverage — games with extreme conditions (playoff back-to-backs, heavy travel schedules) are systematically miscalibrated.

**This paper enables**: wrap any pareto model from S18/S22/evo4/evo5 with pivotal score post-processor → conditional coverage guaranteed, no retraining.

**Fleet-best relevance**: S18 CatBoost-0.2191 and S22 XGBoost-0.21985 (both discovered fire-268 at TRIPLE FLEET-BEST level) would benefit immediately — apply pivotal score wrapper before promotion to production predict_today.py.

---

## Applications

### Application 1: Fleet-Best Model Post-Processing (predict_today.py)
Wrap S18 CatBoost-0.2191 and S22 XGBoost-0.21985 candidates with pivotal score calibrator:
```python
from calibration.pivotal_calibrator import PivotalScoreCP

# Load pareto best from island export
model = load_pareto_best('S18', gen=2450)
calibrator = PivotalScoreCP(coverage=0.90)
calibrator.fit(cal_X, cal_y, model)

# Post-processing: conditional coverage guaranteed
pred_intervals = calibrator.predict(test_X)
brier_scores = calibrator.brier(test_X, test_y)
```
Expected: 0.001–0.002 Brier improvement from better conditional calibration.

### Application 2: Replace Isotonic Calibration in engine.py
Current pipeline: `model.predict_proba()` → isotonic calibration → output.
New pipeline: `model.predict_proba()` → pivotal score CP → output.
- No retraining needed: fits pivotal calibrator on held-out calibration split
- Achieves conditional coverage vs. marginal-only isotonic
- ~30 lines implementation in `calibration/isotonic_calibrator.py`

### Application 3: Add `pivotal_coverage_gap` to /api/export
```json
{
  "pivotal_calibration": {
    "marginal_coverage": 0.892,
    "conditional_coverage_home": 0.891,
    "conditional_coverage_away": 0.893,
    "pivotal_coverage_gap": 0.002,
    "isotonic_brier": 0.21985,
    "pivotal_brier": 0.21941
  }
}
```
This metric identifies which pareto candidates gain most from pivotal calibration — a new dimension for island ranking.

### Application 4: POL Island Port
Apply to P4/P5/P7 political predictions:
- Pivotal score calibrator fits on historical election results (calibration set)
- Conditional coverage for state-level predictions (battleground vs. safe)
- Particularly valuable for P5 (fresh restart post-fire-268 RULE9 RESOLVED)
- ~25 lines in `features/political_engine.py`

### Application 5: Calibration Audit for Promotion Gate
Before any island candidate is promoted to fleet best, apply pivotal score audit:
- Compute `pivotal_coverage_gap` on held-out season
- Only promote if `pivotal_coverage_gap < 0.05` (tight conditional coverage)
- Add to Rule #5 (Threshold Gates): conditional coverage audit as prerequisite

---

## Implementation Plan

1. **VM Step 1** (~80 lines): Implement `PivotalScoreCP` class in `calibration/pivotal_calibrator.py`
   - Pivotal residual computation from model outputs
   - Distribution-free nonconformity scores
   - Conditional prediction set construction
   - Dependencies: scipy.stats (already available)

2. **VM Step 2** (~20 lines): Integration hook in `calibration/isotonic_calibrator.py` — optional drop-in replacement

3. **VM Step 3** (~25 lines): Add `pivotal_coverage_gap` metric to `hf-space/app.py` export

4. **VM Step 4** (~20 lines): Add conditional coverage gate to `/api/checkpoint` promotion logic

5. **VM Step 5** (~25 lines): Port to `features/political_engine.py`

**Total**: ~170 lines across 4 files. No new dependencies (scipy only).

---

## Synergies

- **arXiv:2606.00419** (priority=123): Parameter-free group-CP + pivotal scores = fully automated conditional coverage stack. Run in sequence: group-conditional CP for online adaptation, pivotal scores for post-hoc conditional audit.
- **arXiv:2506.19689** (priority=114): Calibration set reuse across k pareto models. Combine: single pivotal calibrator reused across all island candidates using Hoeffding correction.
- **arXiv:2602.14913** (priority=121): Pseudo-calibrated CP under distribution shift. Pivotal scores + pseudo-calibration = conditional + shift-robust coverage.
- **fire-268 S18/S22 triple fleet-best**: Apply pivotal calibrator to CatBoost-0.2191 and XGBoost-0.21985 before production promotion.

---

## Expected Results

- **Brier improvement**: 0.001–0.003 (conditional calibration tighter than marginal isotonic)
- **Coverage improvement**: marginal → conditional, especially for extreme game conditions
- **Promotion gate**: prevents promoting models with good marginal but poor conditional calibration
- **POL benefit**: conditional coverage for state-level elections (not just national aggregate)

---

*Written by cloud-brain-fire-268 (2026-06-04T12h). VM: implement after priority=0 checkpoint items.*
