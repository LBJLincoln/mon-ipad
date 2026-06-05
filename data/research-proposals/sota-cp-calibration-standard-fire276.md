# SOTA Research Proposal: Conformal Prediction as Universal Calibration Standard

**Source**: arXiv:2512.17048 (Dec 2025): "Another Fit Bites the Dust: Conformal Prediction as a Calibration Standard for Machine Learning in High-Energy Physics"
**Fire**: 276 EVEN (2026-06-05T20h)
**Priority**: 131
**Work-queue ID**: vm-research-cp-calibration-standard-fire276

## Key Finding

CP provides universal, distribution-free calibration across ALL model types simultaneously:
- Binary classification (Brier score)
- Multi-class classification (log-loss)
- Regression (CRPS)
- Anomaly detection (ECE)
- Generative models (CRLS)

Validated on HEP datasets: CP calibration outperforms Platt scaling, isotonic regression, and Venn-Abers on tail-heavy distributions — particularly relevant for our playoff back-to-back NBA games and rare political events.

Key property: CP calibration is **model-agnostic** and requires NO retraining. It works as a post-hoc wrapper identical to our current isotonic calibrator but with stronger theoretical guarantees.

## Applications to Nomos42 Pipeline

### Application 1: Universal CP Calibrator in engine.py
Replace the per-model-type calibration chain (isotonic → Venn-Abers → ECE) with a single CP calibrator wrapper:
```python
# calibration/cp_universal_calibrator.py (~80 lines)
from nonconformist import ClassifierNc, NcFactory
calibrator = ClassifierNc(model, MarginErrFunc())
# Works for RF, ET, CatBoost, XGBoost, LR — no model-specific logic
```
Expected improvement: 0.001-0.002 Brier (eliminates calibration mismatch between model types)

### Application 2: Validate S22 ET-200f-0.2191 Under CP Standard
Before promoting S22 ET-200f-0.2191 (fire-276 fleet best candidate), apply CP calibration audit:
- Measure: marginal coverage vs. conditional coverage (home/away, back-to-back, playoffs)
- Gate: promote only if conditional coverage gap < 0.05 across all groups
- Prevents promoting Brier-optimal but conditionally miscalibrated models

### Application 3: Unified CP Calibration Across Fleet
Apply same CP calibration standard across evo4 RF-0.22007, evo5 RF-0.2191, S22 ET-0.2191 before fusion in predict_today.py. Ensures apples-to-apples comparison for fleet-best ranking.

### Application 4: POL Fleet Calibration
Apply CP universal calibrator to P4 LGB-121f-0.2491 (fire-276 POL fleet best candidate) before production promotion.

### Application 5: CP Coverage as New Checkpoint Gate
Extend Rule #5 (Threshold Gates): any candidate below 0.22085 must ALSO pass CP conditional coverage audit before checkpoint confirmation.

## Library
```
pip install nonconformist crepes mapie
```
No new dependencies beyond existing pipeline (nonconformist and crepes already in proposals 1-2).

## Expected Improvement
- 0.001-0.002 Brier (uniform calibration quality)
- Prevents false fleet-best claims from models calibrated on marginal but not conditional distributions
- Especially impactful for playoff predictions (historically 4-6% under-confident)

## Integration with Existing Research
Complements:
- fire-268 pivot scores (priority=126) — both post-hoc conditional coverage
- fire-268 group-conditional OCP (priority=125) — both target subgroup calibration
- fire-272 MOPI (priority=129) — MOPI shape-adaptive + CP standard combined

## Next Steps (VM)
1. Implement `calibration/cp_universal_calibrator.py` (~80 lines)
2. Add `cp_calibration_coverage` field to /api/export
3. Run calibration audit on S22 ET-0.2191 pickle (once VM saves it — fire-276 priority=0)
