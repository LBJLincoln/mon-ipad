# Research Proposal: Stacked Ensemble Meta-Learner
**Date:** 2026-03-27  
**Priority:** HIGH  
**Expected Brier improvement:** 0.221 → ~0.215 (-0.006, ~3% gain)  
**Complements:** calibration-improvement-2026-03-27.md (apply isotonic AFTER stacking)

## Context

Current best Brier: **0.22126** (S14, random_forest, 34 features)  
All-time record: **0.21837** | Target: **< 0.21837**

The fleet runs 6 specialist islands with diverse model types:
- S10: XGBoost | S11: RandomForest | S12: ExtraTrees
- S13: LightGBM | S14: RandomForest | S15: ExtraTrees

Each island finds different local optima. **Stacking their Pareto-front predictions** into a meta-learner is a well-documented technique for squeezing the final few Brier points.

## Literature Basis

From: *[Stacked Ensemble Model for NBA Game Outcome Prediction](https://www.nature.com/articles/s41598-025-13657-1)* (Scientific Reports, Aug 2025):
> Base learners: Naïve Bayes, AdaBoost, MLP, KNN, XGBoost, Decision Tree, Logistic Regression.
> Stacked ensemble outperforms all individual models on Brier score.
> Meta-learner: Logistic Regression (interpretable, low-variance).

From: *[Uncertainty-Aware NBA Forecasting](https://www.mdpi.com/2078-2489/17/1/56)* (MDPI, Jan 2026):
> Logistic regression as meta-learner achieves best Brier (0.199) among tabular approaches.
> Key insight: LR meta-learner inherits diversity from base learners without overfitting.

## Proposed Architecture

### Cross-Island Meta-Learner (NEW: `ops/meta_stacker.py`)

```python
# Fetch Pareto-front predictions from all 6 islands via /api/status
# Each island exposes best_model probabilities on a held-out validation set

class CrossIslandMetaStacker:
    """
    Stacks predictions from all 6 island best models into a
    Logistic Regression meta-learner. Runs on VM (CPU-only, lightweight).
    """
    def __init__(self, island_urls):
        self.islands = island_urls
        self.meta = LogisticRegression(C=0.1, max_iter=200)
    
    def collect_oof_predictions(self):
        """Fetch OOF (out-of-fold) probabilities from each island API."""
        # Each island /api/oof_probs returns {"probs": [...], "y_true": [...]}
        # This requires adding a /api/oof_probs endpoint to each HF Space
        ...
    
    def fit(self, X_meta, y):
        """X_meta: (n_games, 6) — one prob column per island."""
        self.meta.fit(X_meta, y)
    
    def predict(self, X_meta):
        return self.meta.predict_proba(X_meta)[:, 1]
```

### Quick Win: In-Island Stacking (IMMEDIATE, no API changes)

Within each island's `evaluate_individual()`, instead of using a single model:

```python
def evaluate_with_stacking(ind, X_train, y_train, X_val, y_val, n_folds=3):
    """Stack 3 base learners within a single evaluation."""
    tscv = TimeSeriesSplit(n_splits=n_folds)
    base_models = [
        build_model(ind),                    # primary model
        ExtraTreesClassifier(n_estimators=50, random_state=42),  # fast ET
        LogisticRegression(C=0.5, max_iter=100),                 # LR fallback
    ]
    
    # OOF stack
    oof_preds = np.zeros((len(X_train), len(base_models)))
    for i, model in enumerate(base_models):
        for fold, (tr_idx, val_idx) in enumerate(tscv.split(X_train)):
            model.fit(X_train[tr_idx], y_train[tr_idx])
            oof_preds[val_idx, i] = model.predict_proba(X_train[val_idx])[:, 1]
    
    # Meta-learner on OOF
    meta = LogisticRegression(C=0.1, max_iter=100)
    meta.fit(oof_preds, y_train)
    
    # Val predictions
    val_stack = np.column_stack([
        m.predict_proba(X_val)[:, 1] for m in base_models
    ])
    probs = meta.predict_proba(val_stack)[:, 1]
    brier = brier_score_loss(y_val, probs)
    return brier, probs
```

**Note:** This adds ~2x eval time. Best deployed on **S15 (pop=50, wide search)** as experiment first.

## Probability Clipping Quick Win (1 LINE, IMMEDIATE)

Prevents extreme predictions (0.02, 0.98) from inflating Brier score on close games:

```python
# In evaluate_individual(), after probs = model.predict_proba(X_val)[:, 1]:
probs = np.clip(probs, 0.025, 0.975)  # Literature-recommended range
brier = brier_score_loss(y_val, probs)
```

**Expected gain:** -0.001 to -0.003 Brier. Trivially safe. Deploy everywhere immediately.

## Implementation Plan

| Change | Effort | Expected Gain | Deploy On | Priority |
|--------|--------|---------------|-----------|----------|
| Probability clipping | 1 line | -0.001 to -0.003 | ALL islands immediately | CRITICAL |
| In-island stacking (LR+ET+primary) | 1h | -0.003 to -0.006 | S15 first | HIGH |
| Cross-island meta-stacker | 4h + API change | -0.005 to -0.010 | ops/ on VM | MEDIUM |

## Combined Effect

If clipping + isotonic calibration + in-island stacking all applied:
- Current: 0.22126
- After clipping: ~0.219
- After isotonic calibration: ~0.213  
- After stacking: ~0.210
- **Literature floor with these techniques: ~0.199** (MDPI Jan 2026)

## References

- [Stacked Ensemble NBA, Scientific Reports Aug 2025](https://www.nature.com/articles/s41598-025-13657-1)
- [Uncertainty-Aware NBA, MDPI Jan 2026](https://www.mdpi.com/2078-2489/17/1/56)
- [NBA/WNBA ML Survey, MDPI Oct 2025](https://www.mdpi.com/2079-3197/13/10/230)
