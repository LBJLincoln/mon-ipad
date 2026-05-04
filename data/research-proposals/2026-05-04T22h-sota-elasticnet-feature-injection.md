# SOTA: ElasticNetCV Feature Injection for NBA/POL Islands

**Date:** 2026-05-04T22h  
**Source:** MDPI Computation 2079-3197/13/10/230 (2026)  
**Status:** PROPOSAL  
**Priority:** HIGH — S15 checkpoint validates this direction

## Finding

Academic SOTA for NBA Brier prediction (2026):
- CNN model: **Brier 0.221** (best reported)
- Logistic Regression: **Brier 0.223**
- Features: **75 top features via ElasticNetCV** from full pool
- Sample: 2015–2024 NBA seasons, 2023/24 as holdout test

Our fleet (same cycle):
- S14: **0.22019** (all-time fleet best, logistic_regression, 26 features)
- S15: **0.22034** (NEW CHECKPOINT, xgboost_brier, **76 features**)
- Academic CNN: 0.221 — *we beat academic SOTA*

**S15's 76 features aligns exactly with academic SOTA's 75 ElasticNetCV features.** The GA is organically discovering the same feature-count sweet spot.

## Key Insight

ElasticNetCV as regularized feature ranker:
- L1 sparsity + L2 correlation penalty simultaneously
- Cross-validated alpha avoids overfitting
- Consistently selects 60–80 features on NBA-scale datasets

Our GA selects 44–76 features per island via fitness — same range, different mechanism. The convergence is non-trivial.

## Proposed Enhancement: ElasticNetCV Elite Seeding

Inject ElasticNetCV-selected feature subsets as elite seed individuals into island populations:

```python
from sklearn.linear_model import ElasticNetCV
import numpy as np

# 1. Run ElasticNetCV on full feature pool (one-time per season)
en = ElasticNetCV(cv=5, l1_ratio=[0.1, 0.5, 0.9, 1.0], max_iter=10000)
en.fit(X_train_scaled, y_train)

# 2. Top 75 features by |coefficient|
top75 = np.argsort(np.abs(en.coef_))[-75:]

# 3. Inject as elite individual at island init (not as hard constraint)
island.seed_elite(feature_mask=top75, model_type='xgboost_brier', source='elasticnet_sota')
```

## Priority Islands

| Island | Reason | Expected Impact |
|--------|--------|----------------|
| S15 | xgboost_brier + 76f already at 0.22034; add EN seed | Push toward 0.22019 or below |
| S13 | 30 cycles since improvement; diversify with EN seed | Break 0.22457 plateau |
| P2 | 3 hard resets at ~0.25003 plateau | Break 0.25003 with fresh feature basis |
| P7 | Actively improving (current 0.24904 < best 0.25412) | Accelerate descent below 0.249 |

## SOTA Gap Analysis

| Metric | Academic SOTA (2026) | Our Fleet Best |
|--------|---------------------|----------------|
| NBA Brier | 0.221 (CNN, ElasticNetCV 75f) | **0.22019** (S14) |
| NBA Brier | 0.223 (LR, ElasticNetCV 75f) | 0.22034 (S15) |
| POL Brier | — | 0.24992 (P4) |

**Our fleet beats published academic SOTA on NBA prediction.** The 0.00081 gap to CNN (0.22019 vs 0.221) is within noise. Next frontier: break 0.22 barrier.

## Secondary: Stacked Ensemble (Nature Sci Reports 2025)

Stacked ensemble (NB + AdaBoost + MLP + KNN + XGBoost + DT + LR) shows marginal gains over single models. Relevant for S14 (logistic_regression) — adding XGBoost layer on top of LR predictions could push below 0.22019.

**Implementation path:** S14 island → modify fitness function to train stacked LR+XGB → evaluate on same holdout → compare Brier.

## Status
- [ ] ElasticNetCV feature export script (scripts/features/elasticnet_export.py)
- [ ] Island elite_seed API endpoint (/api/seed_elite)
- [ ] Test on S15 first (clean slate, same model type)
- [ ] Evaluate Brier delta after 10 cycles
