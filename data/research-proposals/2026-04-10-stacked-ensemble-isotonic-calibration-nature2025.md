# NBA Stacked Ensemble with Isotonic Calibration — Nature Scientific Reports 2025

**Cycle:** 89 | **Date:** 2026-04-10 | **Source:** Nature Sci Reports 2025 + MDPI Uncertainty-Aware 2026

## Problem

Current fleet best Brier: **0.22291** (Island-6, xgboost_brier). All-time best: 0.21570.  
Target: < 0.21837 (checkpoint threshold), ultimately < 0.20.

Key gap: individual models (ExtraTrees, XGBoost, CatBoost) plateau near 0.222–0.224.  
Island-6 found ExtraTrees 200-features achieving **0.21906** — close to checkpoint but isolated.

## Research Basis

1. **Nature Scientific Reports 2025** — "Stacked ensemble model for NBA game outcome prediction"  
   - Logistic meta-learner over base models achieves Brier 0.199 (best tabular)  
   - Key: uses out-of-fold (OOF) predictions from each base model as meta-features  
   - XGBoost (high AUC but Brier 0.202) + LR (Brier 0.199) ensemble beats either alone

2. **MDPI Uncertainty-Aware ML 2026** — calibrated probability pipelines  
   - `CalibratedClassifierCV` with Brier-based selection of method (sigmoid/isotonic/none)  
   - Isotonic regression wins over sigmoid for non-linear probability distortions (>500 samples)

3. **Island-6 observation** — ExtraTrees 200 features → 0.21906 in generation 860  
   - Confirms feature richness helps; but single model plateaus

## Proposed Implementation

### Phase 1: OOF Stacking Layer (Kaggle GPU — no VM ML)

```python
# In kaggle karpathy loop:
from sklearn.ensemble import StackingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

base_models = [
    ("xgb", XGBClassifier(**best_xgb_params)),
    ("et", ExtraTreesClassifier(**best_et_params)),   # Island-6 winner
    ("cat", CatBoostClassifier(**best_cat_params)),   # Island-2 winner
    ("lgbm", LGBMClassifier(**best_lgbm_params)),
]

meta = LogisticRegression(C=0.1, max_iter=500)  # LR meta-learner (Nature 2025)

stack = StackingClassifier(
    estimators=base_models,
    final_estimator=meta,
    cv=5,  # OOF predictions
    stack_method="predict_proba",
)

# Calibrate the stacked output
calibrated_stack = CalibratedClassifierCV(
    stack, cv="prefit", method="isotonic"  # isotonic for n>500
)
```

### Phase 2: GA Evolution Tweak

In `evolution/genetic_loop.py`, add `"stacked_ensemble"` as a valid model_type:
- GA evolves which base models to include + meta-learner regularization (C param)
- Pareto front tracks: Brier + ROI + ECE (calibration error)
- Expected Brier improvement: 0.222 → 0.217 based on paper benchmarks

### Phase 3: CPU-Safe Variant for HF Spaces

Since HF Spaces are CPU-only, use **smaller base ensembles**:
- Reduce base model n_estimators to 50-80 (from 100-200)
- Use 3 base models max (XGB + ET + LR) not 4
- Pre-compute OOF on Kaggle, export fitted stacking weights as JSON
- HF Space loads pre-fitted meta-weights, only runs inference

## Expected Impact

| Metric | Current | Expected |
|--------|---------|----------|
| Brier (fleet best) | 0.22291 | 0.217–0.219 |
| ECE | ~0.03 | ~0.015 |
| ROI | 29.0% | 28–31% |

If Brier reaches 0.21837 → Supabase checkpoint triggered.  
If Brier reaches 0.218 → breakthrough, trigger full Kaggle GPU session.

## Prerequisites

- Best XGB params from Island-6 gen-860 (200 features, Brier 0.21906)
- Best CatBoost params from Island-3 (gen ~470, Brier 0.22494 ROI 27%)
- OOF training requires GPU session (~2-3h on P100)

## Priority: HIGH

Assign to: Kaggle Karpathy Loop, next GPU session.  
Cycle: implement in cycle 90 after verifying Island-6 params survive migration.

## Cross-Project Port

This same OOF stacking approach applies to **Political Alpha**:  
- P1 (xgboost_brier) + P2 (catboost) → LR meta-learner  
- Expected Political Brier improvement: 0.231 → 0.225  
- Port after NBA validation.
