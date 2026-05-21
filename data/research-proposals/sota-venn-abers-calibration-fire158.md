# Research Proposal: Venn-Abers Calibration for XGBoost/LightGBM — fire-158 EVEN

**Source:** arXiv:2605.03816 (Manokhin Probability Matrix, May 2026) + NBA prediction Brier-score context  
**Detected:** fire-158 EVEN (2026-05-24T12h)  
**Priority:** HIGH — directly applicable to P1/P2 (xgboost_brier best_model) and NBA islands (S13 XGB-47f best_model)

## SOTA Finding

Manokhin (arXiv:2605.03816) introduces the Probability Matrix diagnostic framework for classifier probability quality across 30 benchmark datasets:

| Category | Models | Calibration | Discrimination |
|----------|--------|-------------|----------------|
| Eagles   | CatBoost, TabICL, EBM, TabPFN, GBC, Random Forest | GOOD | GOOD |
| Bulls    | **XGBoost, LightGBM, HGB** | **POOR** | GOOD |
| Bears    | Logistic Regression, SVC, KNN | POOR | POOR |

**Key result:** CatBoost wins **26/30 datasets on Brier score**, 28/30 on log-loss, 24/30 on AUC-ROC.

**Fix for Bulls:** Venn-Abers calibration converts XGBoost/LightGBM from Bull→Eagle. Available as `venn_abers` in Python `nonconformist` or `crepes` libraries.

## Relevance to Nomos42 Fleet

### NBA Islands
- S13 best_model: `xgboost_brier` (47f) — Bull category → poor calibration
- S14 best_model: `random_forest` (48f) — Eagle category (OK)
- S15 best_model: `random_forest` (75f) — Eagle category (OK)
- S22 best_model: `random_forest` (48f) — Eagle category (OK)

### Political Islands  
- P1 best_model: `xgboost_brier` (85f) — Bull → poor calibration
- P2 best_model: `xgboost_brier` (65f) — Bull → poor calibration
- P4 best_model: `lightgbm` (62f) — Bull → poor calibration
- P5 best_model: `xgboost_brier` (58f) — Bull → poor calibration
- P7 best_model: `xgboost_brier` (60f) — Bull → poor calibration

**All 5 active POL islands use Bull-category models as best_model.**  
**This is a systematic calibration deficiency in the political fleet.**

## Proposed Implementation

### Phase 1: Add Venn-Abers wrapper to political_engine.py
```python
# After model.fit(X_train, y_train):
from crepes import WrapClassifier
venn_model = WrapClassifier(model)
venn_model.fit_calibrate(X_calib, y_calib, method='va')  # Venn-Abers
y_prob_calibrated = venn_model.predict_p(X_test)[:, 1]
# Use y_prob_calibrated for Brier score calculation
```

### Phase 2: Compare Brier with/without calibration  
Expected improvement: 0.001-0.003 on Brier score for XGB/LightGBM models.

### Phase 3: Port to NBA features/engine.py if POL validates
The `features/engine.py` fitness function uses raw model probabilities. Adding Venn-Abers post-hoc calibration could push XGB models from ~0.250 to ~0.247 on political islands.

## Why CatBoost Dominates Pareto Fronts

This finding explains the empirical observation that CatBoost dominates NBA pareto fronts:
- S13 CatBoost-200f-0.21992 (below fleet best!)
- S18 CatBoost-200f-0.22197 (new S18 pareto best)
- S22 CatBoost-200f-0.21818 (was all-time record before reboot)

CatBoost is naturally well-calibrated (Eagle). XGBoost achieves lower log-loss but higher Brier because its probabilities are poorly calibrated. Venn-Abers would make XGBoost competitive with CatBoost on Brier.

## Expected ROI

If Venn-Abers calibration moves P1/P2 from 0.2499→0.2489 on Brier:
- Sharpe improvement: 0.1→0.5 (better calibrated Kelly sizing)
- Prioritization: implement on P1 first (ALL-TIME RECORD candidate 0.24902)

## Action Items
1. `vm-add-venn-abers-political` — add `crepes` or `nonconformist` to political_engine.py
2. `vm-test-venn-abers-nba-s13` — test on S13 XGBoost-47f vs CatBoost-200f
3. Validate on holdout before adding to GA fitness function

## References
- arXiv:2605.03816 — Manokhin Probability Matrix (May 2026)
- MDPI Info Jan 2026 — NBA uncertainty-aware RNN+MC-dropout Brier~0.20
- `nonconformist` Python library — Venn-Abers implementation
- `crepes` Python library — conformal prediction + calibration
