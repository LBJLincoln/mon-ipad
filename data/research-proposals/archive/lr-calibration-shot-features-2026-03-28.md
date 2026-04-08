# Research Proposal: Calibrated Logistic Regression + Shot-Zone Features
**Date:** 2026-03-28  
**Priority:** HIGH  
**Source:** MDPI 2026 (Uncertainty-Aware ML for NBA, January 2026) + MDPI 2025 (ML for NBA & WNBA)

## Finding

The MDPI January 2026 paper "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets" tested LR, XGBoost, CNN, and LSTM+MC-Dropout on comparable NBA data (strict chronological split, 2012–2024):

| Model | Brier Score | Notes |
|-------|-------------|-------|
| Logistic Regression | **0.199** | Best tabular Brier |
| XGBoost | 0.202 | Best economic ROI |
| CNN | 0.221 | (MDPI 2025) |
| Our current GA best (S10) | 0.2237 | XGBoost on 71 features |
| All-time best (Colab TabICL) | 0.21570 | 110 features, GPU |

**LR at Brier 0.199 is better than our all-time best of 0.21570.**

## Root Cause Analysis

Our GA currently tests: `xgboost`, `xgboost_brier`, `lightgbm`, `catboost`, `extra_trees`, `random_forest`.  
**We do NOT include `logistic_regression`.** This is a significant gap.

Calibrated LR works well because:
1. Binary classification in NBA is close to linear in log-odds space (home advantage, Elo delta → win prob)
2. LR is less prone to overfit on small feature sets
3. CalibratedClassifierCV (Platt/isotonic) directly minimizes Brier score
4. SHAP shows top features are `team_elo`, `team_elo_5y`, `home_next` — all near-linear

## Proposed Change (concrete, 1-fix rule)

### In `hf-space/app.py` → `train_model()` function

Add `logistic_regression` to the model type pool:

```python
# ADD to MODEL_TYPES list:
"logistic_regression"

# ADD to train_model() dispatch:
elif model_type == "logistic_regression":
    from sklearn.linear_model import LogisticRegression
    from sklearn.calibration import CalibratedClassifierCV
    base = LogisticRegression(
        C=hp.get("C", 1.0),
        max_iter=hp.get("max_iter", 1000),
        solver="lbfgs",
        random_state=42
    )
    if hp.get("calibration", "platt") == "isotonic" and len(X_train) >= 300:
        model = CalibratedClassifierCV(base, method="isotonic", cv=3)
    else:
        model = CalibratedClassifierCV(base, method="sigmoid", cv=3)
    model.fit(X_train, y_train)
```

### GA Hyperparameters for LR

```python
# In init_individual() when model_type == "logistic_regression":
hp = {
    "C": random.choice([0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]),
    "max_iter": random.choice([500, 1000, 2000]),
    "calibration": random.choice(["platt", "isotonic", "none"])
}
```

### S15 (wide_search): Enable LR in Model Pool

S15 already has `mut=0.18, pop=50` — ideal for wide exploration.  
Add LR to S15's model type pool specifically to test against XGBoost.

## Expected Impact

- Target: Brier < 0.215 on S15 within 48h if LR performs as in literature
- Low compute cost (LR trains in milliseconds vs seconds for XGBoost)
- Enables 3x more generations per hour on LR individuals
- Cross-project: identical pattern applicable to Political Alpha

## Also Noted: Shot-Chart Zone Features

The 2026 MDPI paper found shot-chart spatial embeddings added +0.003 Brier improvement:
- Zone-weighted FGA rates (paint, mid-range, corner-3, above-break-3)
- Already partially in `features/engine.py` as Category 7 (Shot Quality)
- Proposal: verify Cat7 features are in active feature pool with non-zero variance

## Implementation Effort
- Code change: ~20 lines in `hf-space/app.py`
- Applies to: S15 immediately, all islands after validation
- Risk: LOW (additive change, GA will naturally select or discard LR)

## References
- [Uncertainty-Aware ML for NBA, MDPI 2026](https://www.mdpi.com/2078-2489/17/1/56)
- [ML for NBA & WNBA Outcomes, MDPI 2025](https://www.mdpi.com/2079-3197/13/10/230)
- [Stacked Ensemble NBA, Nature Sci Rep 2025](https://www.nature.com/articles/s41598-025-13657-1)
