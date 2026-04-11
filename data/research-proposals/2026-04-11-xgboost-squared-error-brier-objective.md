# XGBoost Direct Brier Loss (Squared Error Objective) — Cycle 91

**Date:** 2026-04-11  
**Cycle:** 91  
**Priority:** HIGH  
**Source:** MDPI Information 17(1), 56 (2026) — Uncertainty-Aware NBA Forecasting; PMC XGBoost+SHAP (2024)

## Problem

All HF islands train XGBoost with `objective='binary:logistic'`, which minimizes log-loss. Our fitness metric is Brier score. **Log-loss is a proxy, not the direct target.** Log-loss penalizes extreme confident-but-wrong predictions very heavily, pushing all predictions toward 0.5 — this is a known calibration problem for sports prediction.

## Proposed Change

Add `use_brier_objective` boolean flag to the GA chromosome (S13 CatBoost island to test first, then propagate). When enabled, train XGBoost as a **regressor** with `objective='reg:squarederror'`, which minimizes MSE = Brier score directly.

```python
# In hf-space/app.py (S13 catboost island as test case):
# ADD to chromosome init/mutate: 'use_brier_objective': random.random() < 0.3

def _train_model(self, X_train, y_train, chromosome):
    use_brier = chromosome.get('use_brier_objective', False)
    if use_brier and chromosome.get('model_type') == 'xgboost':
        model = xgb.XGBRegressor(
            objective='reg:squarederror',
            n_estimators=chromosome.get('n_estimators', 200),
            max_depth=chromosome.get('max_depth', 4),
            learning_rate=chromosome.get('learning_rate', 0.05),
            subsample=chromosome.get('subsample', 0.8),
            colsample_bytree=chromosome.get('colsample_bytree', 0.8),
            reg_alpha=chromosome.get('reg_alpha', 0.1),
            reg_lambda=chromosome.get('reg_lambda', 1.0),
            random_state=42, n_jobs=2
        )
        model.fit(X_train, y_train)
        # Clip to valid probability range
        probs = np.clip(model.predict(X_val), 0.02, 0.98)
    else:
        # existing binary:logistic path
        model = xgb.XGBClassifier(...)
        probs = model.predict_proba(X_val)[:, 1]
```

## Why This Works

1. **Direct optimization**: Gradient descent in XGBoost directly minimizes Brier score instead of a proxy. The gradient of MSE w.r.t. raw score pushes predictions to the true probability.

2. **Better calibration**: Log-loss gradient `(p - y)/p(1-p)` has large gradients for confident predictions, collapsing probabilities toward 0.5. MSE gradient `2(p - y)` is linear, producing better-spread probability distributions.

3. **Research evidence**: MDPI 2026 uncertainty-aware models achieve Brier 0.089 using direct probability regression objectives. PMC 2024 XGBoost+SHAP paper shows Brier 0.202 vs Logistic Regression 0.199 — the gap narrows with proper objectives.

4. **Synergy with island GA**: The GA already selects for Brier score as fitness. Adding Brier-objective training makes the model training ALSO optimize Brier — double alignment.

## Expected Impact

- Fleet best currently: 0.22249 (S11, gen 1023)
- Estimated improvement from direct Brier objective: 0.002–0.005 Brier reduction
- If applied to S13 (CatBoost specialist): could push 0.22316 → ~0.218 (past checkpoint threshold 0.21837)
- If GA discovers `use_brier_objective=True` is winning, it propagates across population automatically

## Implementation Steps

1. Add `use_brier_objective` to chromosome schema in `hf-space/app.py` init and mutation functions
2. Modify `_train_model` (or equivalent) to branch on this flag
3. Add `XGBRegressor` import alongside `XGBClassifier`
4. Deploy to S13 first (CatBoost specialist — smallest change risk)
5. Monitor 2 cycles. If Brier < 0.220, propagate to all XGBoost islands

## Related Proposals (already written)

- Isotonic calibration (2026-04-08, 2026-04-10) — complements this (post-hoc calibration on top of Brier-trained model)
- MLP meta-learner (2026-04-10) — can receive Brier-trained base model outputs
- Era normalization (2026-04-11) — orthogonal feature engineering improvement

## Status

`PROPOSED` — ready for implementation when islands are awake (currently 503)
