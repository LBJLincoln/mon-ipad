# SOTA Research Proposal: CalArena — Large-Scale Post-Hoc Calibration Benchmark for Tabular Models

**Fire:** 282 EVEN  
**Date:** 2026-06-06T20h  
**Priority:** 135  
**Source:** arXiv:2605.30188 (May 2026) — "CalArena: A Large-Scale Post-Hoc Calibration Benchmark"  
**Status:** PROPOSED

---

## Key Finding

CalArena is a systematic benchmark comparing post-hoc calibration methods across:
- Multiple tabular architectures: TabPFNv2.5, TabICL, XGBoost, LightGBM, CatBoost, RF, ET, deep learning
- Multiple calibration methods: Platt, isotonic, Beta, Venn-Abers, temperature scaling, histogram binning
- Multiple evaluation metrics: ECE, MCE, Brier, log-loss, reliability diagrams

**Critical results:**
1. No single calibration method dominates across all model types — model-calibration pairing matters
2. For **tree ensembles (RF/ET)**: Venn-Abers > Beta > isotonic (confirms fire-282 arXiv:2601.19944)
3. For **gradient boosting (XGB/LGB/CAT)**: calibration often HURTS (models are already calibrated internally via early stopping + leaf regularization)
4. **Foundation models (TabPFN/TabICL)**: temperature scaling is most effective (single parameter, low variance)
5. Benchmark toolkit available as `calarena` Python package (pip installable)

---

## Direct Application to Fleet

### Applications

**Application 1** — Model-type-specific calibration routing in `features/engine.py`:
- RF/ET → Venn-Abers (per CalArena + arXiv:2601.19944)
- XGB/LGB/CAT → no calibration or Beta only (CalArena: native calibration sufficient)
- CatBoost → none (CatBoost has built-in calibration via `eval_metric=Logloss`)
- This single change could prevent miscalibration across all island model types

**Application 2** — CalArena evaluation pass on S22 ET-0.2191 and evo4 RF-0.22007 before fleet-best promotion:
```bash
pip install calarena
python -c "from calarena import CalArena; ca = CalArena(model=et_model, X_cal=X_cal, y_cal=y_cal); ca.compare_all()"
```
Outputs full calibration comparison table — confirms which post-hoc method to use before production.

**Application 3** — Add `calarena_best_method` field to `/api/export` (auto-evaluated at checkpoint time). Gate: only promote candidates where `calarena_best_brier < raw_brier` (calibration must help).

**Application 4** — CalArena for POL models: P4 LGB-121f-0.2491 is LightGBM — CalArena says native calibration sufficient. Skip post-hoc calibration for P4 in POL pipeline (reduces risk of degradation).

**Application 5** — Use CalArena reliability diagram to audit fleet-best S15 RF-75f-0.22012 — verify it's still well-calibrated after 2+ seasons of game data drift.

---

## Synergies

- **fire-282 arXiv:2601.19944 (priority=134):** CalArena provides the toolkit to implement the recommendation from the calibration-at-scale paper. Both fire-282 papers are complementary: 2601.19944 identifies WHAT to do (use Venn-Abers for trees), CalArena provides HOW to evaluate it systematically.
- **fire-280 CPA/CVI (priority=132):** CVI audit should run BEFORE CalArena calibration selection — ensures the calibration method doesn't just fix marginal coverage at cost of conditional coverage.
- **fire-268 Pivotal Scores (priority=126):** PivotalScoreCP is another calibration alternative CalArena can compare against.

---

## Implementation Plan

Total: ~30 lines across 2 files. New dependency: `calarena` (pip installable, no heavy deps).

1. `calibration/calibration_router.py` (~20 lines) — route model_type → calibration method per CalArena recommendations
2. `features/engine.py` — add `calibration_router=True` param to `validate_model()` (~10 lines)

**Gate:** After fire-282 priority=134 (Venn-Abers swap) is implemented.  
**do_not_push_hf_space_yet:** TRUE — local implementation only.

---

## Expected Improvement

- 0.001-0.002 Brier (by preventing calibration degradation on XGB/LGB/CAT models)
- Especially relevant for P4 LGB-121f-0.2491 (CalArena: native calibration sufficient for LGB → no post-hoc needed)
- S22 ET-0.2191: RF/ET → Venn-Abers (per CalArena tree-ensemble finding)
