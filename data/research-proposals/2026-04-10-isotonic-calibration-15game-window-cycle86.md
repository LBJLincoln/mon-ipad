# NBA Proposal: Isotonic Calibration + 15-Game Rolling Window

**Cycle:** 86 | **Date:** 2026-04-10 | **Priority:** HIGH  
**Source:** Nature Scientific Reports (s41598-025-13657-1), MDPI 2079-3197/13/10/230, PMC 11265715 (SHAP+XGBoost NBA)

## Finding

Two consistent signals from 2025-2026 NBA prediction literature:

### 1. Isotonic Regression Calibration Post-Processing

Multiple 2025 papers report that tree ensembles (XGBoost, LightGBM, ExtraTrees) produce **systematically overconfident** probability outputs at extremes. Isotonic regression post-calibration reduces Brier by 0.003-0.007 vs sigmoid (Platt scaling) on multi-season NBA data. Current islands use `CalibratedClassifierCV(method='sigmoid')` or uncalibrated outputs.

**Action:** Switch all islands to `CalibratedClassifierCV(method='isotonic', cv=3)` in the evaluation function. Isotonic handles non-monotonic miscalibration (common in tree models) that Platt cannot fix.

**Expected Brier improvement:** 0.002-0.004 on current 0.2204 → target 0.217-0.219  
**Risk:** Isotonic needs min ~200 samples (we have 9,551 games — safe)

### 2. 15-Game Rolling Window (currently missing)

Research consistently identifies **5/10/15-game windows** as the optimal triple for team form. Current NBA engine WINDOWS = `[1, 3, 5, 7, 10, 15, 20, 30, 60, 90]` — 15 IS present. But SHAP analysis shows 15-game window features rank higher than 20/30-game features. The GA may be selecting 20/30d over 15d because of correlated feature masking.

**Action:** In the GA's feature importance seeding (for S15 SHAP-seeded init), explicitly **weight 15-game window features 1.5× over 20/30-game equivalents** as init bias. This nudges the population toward the research-validated window.

## Implementation Plan

```python
# In evolution/genetic_loop.py — shap_seeded_init():
WINDOW_WEIGHTS = {
    '5d': 1.2, '10d': 1.3, '15d': 1.5,   # research-validated high-signal
    '20d': 1.0, '30d': 0.9, '60d': 0.7,   # attenuate longer windows
}
# Weight feature selection probability by window suffix
for i, fname in enumerate(feature_names):
    for window, weight in WINDOW_WEIGHTS.items():
        if f'_{window}_' in fname or fname.endswith(f'_{window}'):
            selection_probs[i] *= weight
selection_probs /= selection_probs.sum()
```

### Calibration change (hf-space/evolution/genetic_loop.py):
```python
# Line ~150 in evaluate_individual():
# BEFORE:
cal_model = CalibratedClassifierCV(base_model, method='sigmoid', cv=3)
# AFTER:
cal_model = CalibratedClassifierCV(base_model, method='isotonic', cv=3)
```

## Target Validation

Run on Kaggle (GPU, full dataset):
- Baseline: current best_brier 0.22041 (S15, ExtraTrees, 200f)
- Expected post-isotonic: 0.217-0.219
- If Brier < 0.21837 → checkpoint to Supabase

## Cross-Project Port

Same isotonic calibration improvement applicable to Political Alpha P1/P2 (currently using `venn_abers`). Consider A/B test: isotonic vs venn_abers on P1.

## References
- [Stacked ensemble NBA prediction](https://www.nature.com/articles/s41598-025-13657-1) — Nature Sci Rep 2025
- [ML for Basketball Outcomes NBA+WNBA](https://www.mdpi.com/2079-3197/13/10/230) — MDPI 2025
- [XGBoost+SHAP NBA prediction](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/) — PMC 2025
