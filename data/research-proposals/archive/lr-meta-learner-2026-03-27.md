# Research Proposal: Logistic Regression as 7th Model Type + Probability Clipping
**Date:** 2026-03-27 (Cycle 2)  
**Priority:** HIGH — IMMEDIATE IMPLEMENTATION  
**Expected Brier improvement:** 0.221 → ~0.208 (-0.013, ~6% gain)  
**Effort:** 45 minutes — add LR to model registry, add clipping to evaluate_individual()

## Motivation

From *[Uncertainty-Aware ML for NBA Forecasting, MDPI Jan 2026](https://www.mdpi.com/2078-2489/17/1/56)*:
> "Logistic regression attained the best Brier score among tabular baselines (0.199), while XGBoost offered slightly worse probabilistic scores (Brier 0.202) but higher AUC (0.754)"

We are running 6 model types (xgboost, lightgbm, catboost, extra_trees, random_forest, xgboost_brier) but **no Logistic Regression**. Literature suggests LR achieves **Brier 0.199** on NBA data — below our all-time record of 0.21837.

From *[March Madness 2026 Brier optimization](https://jtmarcu.github.io/projects/march-madness.html)*:
> "Final probabilities are clipped to [0.025, 0.975] so no single wrong pick destroys the Brier score."

Probability clipping is a **free 2-line improvement** that reduces extreme tail predictions.

## Why LR Can Beat Tree Models on Brier Score

1. **Better calibration by default**: LR outputs are natively probabilistic with good ECE
2. **SHAP shows linear separability**: Top features (team_elo, home advantage, form) are already near-linear
3. **Feature engine has 3,230 candidates**: LR + L1/L2 regularization performs excellent feature selection
4. **No overfitting on 9,551 games**: With proper C regularization, LR generalizes better than deep trees

## Change 1: Add LR to NBA Model Registry (hf-space/app.py)

In the `build_model()` function, add:

```python
elif model_type == "logistic_regression":
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler  
    from sklearn.pipeline import Pipeline
    return Pipeline([
        ('scaler', StandardScaler()),
        ('lr', LogisticRegression(
            C=ind.get('lr_C', 1.0),       # GA-tunable: [0.01, 0.1, 1.0, 10.0]
            penalty=ind.get('lr_penalty', 'l2'),  # 'l1' for sparsity, 'l2' for stability
            solver='saga',                 # handles l1+l2, scales to 3230 features
            max_iter=1000,
            random_state=42,
            n_jobs=-1,
        ))
    ])
```

GA gene additions for LR:
```python
# In init_individual():
if model_type == 'logistic_regression':
    ind['lr_C'] = random.choice([0.01, 0.1, 1.0, 10.0])
    ind['lr_penalty'] = random.choice(['l1', 'l2'])
```

Add `'logistic_regression'` to `MODEL_TYPES` list (weight: give it 15% probability, same as xgboost_brier).

## Change 2: Probability Clipping (Universal — all models)

In `evaluate_individual()`, after `probs = model.predict_proba(X_val)[:, 1]`, add:

```python
# Clip extremes — prevents single catastrophic prediction dominating Brier score
# From March Madness 2026 optimal strategy: [0.025, 0.975]
probs = np.clip(probs, 0.025, 0.975)
```

**Expected effect:** -0.001 to -0.004 Brier improvement on all existing model types immediately.

## Change 3: Add to Political Alpha too (cross-project port)

The `app.py` in `nomos-political-alpha/hf-space/` already imports `LogisticRegression` and `Pipeline`. Just add it to the political model registry with the same pattern. Political alpha has similar linear separability in Polymarket/donor features.

## Implementation Priority

| Change | Effort | Expected Brier Gain | Deploy On |
|--------|--------|--------------------|-----------|
| Prob clipping [0.025, 0.975] | 5 min | -0.001 to -0.004 | ALL islands immediately |
| LR as 7th model type | 30 min | -0.005 to -0.015 | S10 first, then fleet |
| LR in political alpha | 15 min | unknown — new domain | PA1 first |

## Validation Plan

1. Add clipping to ONE island (S10) first — compare next-cycle Brier
2. Add LR to ONE island (S10) — track if LR individuals dominate Pareto front
3. If LR appears in top-5 solutions after 20 gens → deploy fleet-wide
4. Feature subset: LR works best with 50-200 features (not all 3,230) — let GA select

## References

- [Uncertainty-Aware ML for NBA Forecasting, MDPI Jan 2026](https://www.mdpi.com/2078-2489/17/1/56)
- [Stacked Ensemble NBA, Scientific Reports Aug 2025](https://www.nature.com/articles/s41598-025-13657-1)
- [XGBoost + SHAP for NBA, PMC/NIH](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/)
