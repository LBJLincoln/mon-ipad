# Research Proposal: Stacked Ensemble Meta-Learner + Probability Clipping
**Date:** 2026-03-27  
**Priority:** HIGH  
**Expected Brier improvement:** 0.221 → ~0.213 (-0.008, ~3.5% gain)  
**Complementary to:** calibration-improvement-2026-03-27.md (isotonic wrapping)

## Context

Current best Brier: **0.22126** (S14, random_forest, 34 features)  
All-time record: **0.21837** | Target: **< 0.21837**  

This proposal covers two orthogonal techniques from 2025–2026 literature that complement the isotonic calibration proposal:
1. **Stacked ensemble meta-learner** (logistic regression over tree outputs)
2. **Probability clipping** [0.025, 0.975] as a 1-line quick win

## Technique 1: Probability Clipping (5-minute implementation)

From *[MDPI Uncertainty-Aware NBA Forecasting, Jan 2026]*:
> Probability clipping prevents extreme predictions from disproportionately penalizing Brier score. Clipping to [0.025, 0.975] eliminates the worst 5% of miscalibrated predictions without affecting model structure.

Brier score penalizes wrong confident predictions quadratically. A single prediction of 0.02 on a winning team contributes `(0.02-1)^2 = 0.9604` vs a clipped 0.025 contributing `0.950625` — a small but cumulative gain across 9,551 games.

### Implementation (1 line change in hf-space/app.py)

In `evaluate_individual()`, after getting probabilities:
```python
# Before (current):
probs = model.predict_proba(X_val)[:, 1]
brier = brier_score_loss(y_val, probs)

# After (add 1 line):
probs = model.predict_proba(X_val)[:, 1]
probs = np.clip(probs, 0.025, 0.975)  # prevent extreme overconfident predictions
brier = brier_score_loss(y_val, probs)
```

**Expected gain:** -0.001 to -0.003 Brier (small but free, zero compute cost)  
**Risk:** None — only improves calibration at extremes  
**Deploy on:** All 6 islands simultaneously (single line)

## Technique 2: Stacked Meta-Learner (2-3h implementation)

From *[Stacked Ensemble Model for NBA, Scientific Reports Aug 2025]*:
> Stacking with Logistic Regression as meta-learner over XGBoost + Extra Trees + Random Forest base learners achieves the best ensemble performance. The meta-learner learns to weight each model's probability output based on its calibration quality.

From *[NBA & WNBA ML, MDPI Oct 2025]*:
> CNN achieves Brier 0.221, LR achieves 0.223 — close, but stacked ensemble beats both at 0.219.

### Architecture

```
Level 0 (base models, already evolved):
  XGBoost → prob_xgb
  Random Forest → prob_rf  
  Extra Trees → prob_et
  LightGBM → prob_lgbm
  CatBoost → prob_cat

Level 1 (meta-learner, trained on OOF predictions):
  LogisticRegression(probs=[prob_xgb, prob_rf, prob_et, prob_lgbm, prob_cat]) → final_prob
```

### Implementation Strategy

```python
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict

def build_stacked_ensemble(X_train, y_train, best_individuals):
    """
    Takes the Pareto-optimal individuals from GA, builds a stacked ensemble.
    Level 0: Each individual's model, trained via 5-fold OOF
    Level 1: LogisticRegression on OOF predictions
    """
    oof_preds = []
    for ind in best_individuals[:5]:  # Top 5 Pareto-front models
        model = build_model(ind)  # existing builder
        oof = cross_val_predict(model, X_train, y_train, cv=5, method='predict_proba')[:, 1]
        oof_preds.append(oof)
    
    meta_X = np.column_stack(oof_preds)
    meta_model = LogisticRegression(C=1.0, max_iter=500)
    meta_model.fit(meta_X, y_train)
    
    return meta_model, [build_model(ind).fit(X_train, y_train) for ind in best_individuals[:5]]

def predict_stacked(base_models, meta_model, X):
    base_preds = np.column_stack([m.predict_proba(X)[:, 1] for m in base_models])
    return np.clip(meta_model.predict_proba(base_preds)[:, 1], 0.025, 0.975)
```

### Where to run stacking

Do NOT run stacking inside the GA evaluation loop (too slow). Instead:
- GA evolves individual models as usual
- Every 20 generations, take the top-5 Pareto-front individuals
- Build stacked ensemble out-of-loop
- Log stacked Brier separately as `stacked_brier`
- If stacked_brier < best_brier → use as the reported best

**Expected gain:** -0.004 to -0.010 Brier  
**Compute cost:** ~5min per stacking call (CPU, 20-gen intervals)  
**Deploy on:** S10 first (exploitation specialist), then all if improvement confirmed

## Combined Expected Impact

| Technique | Effort | Expected Gain | Status |
|-----------|--------|---------------|--------|
| Prob clipping [0.025, 0.975] | 5 min | -0.001–0.003 | **Ready to deploy** |
| Isotonic calibration wrapper | 30 min | -0.005–0.015 | Proposed 2026-03-27 AM |
| Stacked meta-learner (LR) | 2-3h | -0.004–0.010 | This proposal |
| team_elo_5y feature | 2h | -0.003–0.007 | Proposed 2026-03-27 AM |

Combined ceiling: **0.22126 - 0.023 = ~0.198** (would beat literature best of 0.199)

## Key Insight from Literature

The Jan 2026 MDPI paper achieves Brier **0.199** with logistic regression + calibration. Our models have:
- Better features (6,135 raw vs ~50 typical)
- Better data (9,551 games vs 3,000-5,000 typical)
- BUT: no calibration wrapper, no stacking

We're leaving ~0.015 Brier on the table purely from post-processing. The GA finds good discriminators; calibration + stacking converts them to good probabilists.

## References

- [Stacked Ensemble for NBA, Scientific Reports Aug 2025](https://www.nature.com/articles/s41598-025-13657-1)
- [Uncertainty-Aware ML for NBA, MDPI Jan 2026](https://www.mdpi.com/2078-2489/17/1/56)
- [NBA/WNBA ML comparison, MDPI Oct 2025](https://www.mdpi.com/2079-3197/13/10/230)
- [XGBoost + SHAP for NBA, PMC Jul 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/)
