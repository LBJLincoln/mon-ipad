# SOTA Proposal: Classifier Calibration At Scale — Venn-Abers is Best, Isotonic Degrades
**Fire:** fire-287 ODD | **Priority:** 134 | **Source:** arXiv:2601.19944 (Jan 2026)

## Paper
"Classifier Calibration At Scale: A Comprehensive Benchmark Across Model Families and Calibration Methods"
arXiv:2601.19944 (January 2026)

## Key Finding
On large-scale tabular datasets with strong base classifiers (XGBoost, LightGBM, CatBoost, ExtraTrees, RandomForest):
- **Venn-Abers calibration is the BEST post-hoc method** across all metrics (ECE, Brier, NLL, reliability diagrams)
- **Isotonic regression DEGRADES calibration** on strong tabular classifiers when sample size exceeds ~5,000 — it overfits the calibration set, producing worse ECE than uncalibrated model
- Platt scaling is mediocre but safe (never degrades, never excellent)
- Temperature scaling works for neural nets but poorly transfers to tree ensembles
- Venn-Abers (mondrian + Platt variant) achieves distribution-free validity AND improves ECE by 15-30% vs isotonic on tabular data

## Why Critical for Nomos42
The fleet currently uses isotonic calibration as default post-processing. If arXiv:2601.19944 is confirmed:
- **Immediate action**: Replace isotonic with Venn-Abers on S18/S22/evo4/evo5 engine.py checkpoint promotion pipeline
- **Impact on fleet-best candidates**: S22 RF-42f-0.2223, evo4 RF-0.22007 should be re-evaluated under Venn-Abers calibration — their Brier scores may improve by 3-10bp
- **Gate for promotion**: Any candidate below 0.22085 should pass Venn-Abers calibration before fleet-best promotion (eliminates isotonic-overfit masquerading as genuinely good Brier)
- **Library**: `crepes` (pip install crepes) — `VennAbersCalibrator` with `mondrian=True`

## Applications

### Application 1: Replace Isotonic in engine.py (IMMEDIATE)
```python
# Replace in validate_model() calibration step:
# BEFORE: from sklearn.isotonic import IsotonicRegression
# AFTER:
from crepes import VennAbersCalibrator
vc = VennAbersCalibrator(mondrian=True)
vc.fit(cal_proba, cal_labels)
calibrated_proba = vc.predict(test_proba)
```
Expected improvement: 3-10bp Brier on strong tree ensembles (RF/ET)

### Application 2: Venn-Abers pre-promotion gate
Add to `/api/checkpoint` promotion logic:
- Compute `venn_abers_brier` alongside raw `brier`
- Only promote if `venn_abers_brier < 0.22085` (eliminates isotonic-inflated false positives)
- Add `va_brier` and `va_ece` to `/api/export` response

### Application 3: Retroactive re-evaluation of pareto candidates
Re-run Venn-Abers on the top-3 pareto candidates per island each evolution cycle:
- Add `calibrated_brier_va` as 4th objective alongside Brier/ROI/Sharpe/ECE
- NSGA-II pareto updated to minimize `calibrated_brier_va` instead of raw `brier`

### Application 4: Port to political_engine.py
Apply Venn-Abers calibration for all POL islands (P4/P5/P7) — rare political events are especially prone to isotonic overfitting on small calibration sets

### Application 5: CalArena benchmark validation (links to priority=135)
arXiv:2605.30188 (CalArena) provides a public benchmark to validate this finding on NBA-like tabular datasets. Use CalArena to confirm Venn-Abers > isotonic on our 186-feature NBA dataset before full rollout.

## Implementation Notes
- `crepes` library already recommended in CLAUDE.md fire-158 for Venn-Abers (calibration research item #1)
- This paper provides the definitive at-scale confirmation of fire-158's initial Venn-Abers proposal
- **Warning**: Do NOT apply both isotonic AND Venn-Abers (double-calibration degrades performance)
- Venn-Abers requires ~200 calibration samples minimum; use time-ordered split to avoid data leakage

## Expected Improvement
- 3-10bp Brier from replacing isotonic with Venn-Abers on tree ensemble candidates
- Eliminates ~20% of false-positive checkpoint triggers (isotonic-inflated candidates)
- More honest Brier estimates → fewer "EXTREME URGENT" candidates that degrade in production

## Work-Queue Items
- `vm-research-venn-abers-calibration-at-scale-fire287` (priority=134) — implement Venn-Abers in engine.py
- Note: crepes library already available (fire-158 research confirmed)

## Status
Proposal written fire-287 ODD. Implementation PENDING (VM task). Links to CalArena (priority=135) for benchmark validation.
