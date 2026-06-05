# SOTA Research Proposal: Classifier Calibration at Scale — Venn-Abers Best, Isotonic Degrades Strong Tabular Models

**Fire:** 282 EVEN  
**Date:** 2026-06-06T20h  
**Priority:** 134  
**Source:** arXiv:2601.19944 (Jan 2026) — "Classifier Calibration at Scale: An Empirical Study of Model-Agnostic Post-Hoc Methods"  
**Status:** PROPOSED

---

## Key Finding

Empirical study across hundreds of tabular datasets finds:

1. **Venn-Abers predictors achieve the LARGEST average reductions in log-loss** among all post-hoc calibration methods — outperforming Platt scaling, isotonic regression, Beta calibration, and temperature scaling.

2. **CRITICAL WARNING: Platt scaling and isotonic regression can SYSTEMATICALLY DEGRADE proper scoring performance for strong modern tabular models.** This is directly relevant to our pipeline — we currently use isotonic calibration by default on pareto models.

3. **Beta calibration** is the second-best performer (behind Venn-Abers) — more stable than isotonic for high-Brier models.

4. The degradation effect is strongest for RF/ET/XGB/LGB models that are already well-calibrated — isotonic overcorrects, causing systematic miscalibration in the opposite direction.

---

## Direct Application to Fleet

### Current Risk
- `calibration/isotonic_calibrator.py` applies isotonic calibration post-hoc to pareto candidates
- S22 ET-0.2191 and evo4 RF-0.22007 are STRONG tabular models (per arXiv:2410.21484 fire-228)
- Applying isotonic calibration to these candidates may DEGRADE their Brier score before production promotion
- S22 already uses Venn-Abers internally via `venn_abers_fusion` — this validates that finding

### Applications

**Application 1** — Swap isotonic to Venn-Abers in `calibration/isotonic_calibrator.py` (~5 lines, crepes already installed):
```python
from crepes import WrapClassifier
from crepes.extras import DifficultyEstimator
# Replace: calibrator = IsotonicRegression()
# With:    calibrator = WrapClassifier(model).calibrate(X_cal, y_cal)
```

**Application 2** — Add `calibration_method` parameter to `validate_model()` in `features/engine.py` (options: 'venn_abers', 'beta', 'isotonic', 'none'). Default to 'venn_abers' for RF/ET models, 'none' for already-calibrated (CatBoost native calibration).

**Application 3** — Pre-promotion calibration audit: compare Brier(isotonic) vs Brier(venn_abers) vs Brier(none) for S22 ET-0.2191 and evo4 RF-0.22007 before fleet-best promotion. If isotonic > venn_abers (worse), confirm the degradation risk.

**Application 4** — Add `calibration_method_used` and `calibration_brier_delta` fields to `/api/export` — track whether calibration improved or degraded the model.

**Application 5** — Port to `political_engine.py`: POL models (P4 LGB-121f-0.2491) are also strong tabular models. Replace isotonic with Venn-Abers in POL calibration pipeline.

---

## Synergies

- **fire-158 (Venn-Abers):** This confirms Venn-Abers was the right choice for S22 from the start. S22's `venn_abers_fusion` architecture is validated.
- **fire-228 (ET > RF):** ET models are strong tabular models — isotonic degradation risk highest for ET candidates.
- **fire-280 CPA/CVI (priority=132):** Conditional coverage gap audits should use Venn-Abers (not isotonic) as baseline calibration.
- **fire-281 Conformal Social Choice (priority=127):** Linear opinion pool should use Venn-Abers outputs for each agent's marginal distribution.

---

## Implementation Plan

Total: ~60 lines across 3 files. No new dependencies (crepes already installed).

1. `calibration/isotonic_calibrator.py` — add `VennAbersCalibrator` class, keep `IsotonicCalibrator` for backwards compatibility (~20 lines)
2. `features/engine.py` — add `calibration_method='venn_abers'` param to `validate_model()` (~15 lines)
3. Both TF `app.py` files — add `calibration_method_used` to `/api/export` response (~10 lines each)

**Gate:** Implement AFTER fire-282 VM tasks are cleared (checkpoint ET-0.2191 + RF-0.22007 first).  
**do_not_push_hf_space_yet:** TRUE — local implementation only until HF push gate lifts.

---

## Expected Improvement

- 0.001-0.003 Brier (prevents isotonic overcorrection on strong RF/ET/LGB models)
- Especially high impact on S22 ET-0.2191 and evo4 RF-0.22007 pre-promotion calibration
- POL: P4 LGB-121f-0.2491 likely benefits (strong LGB model, isotonic may degrade)
