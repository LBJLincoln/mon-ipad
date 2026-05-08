# NBA SOTA 2026: Logistic Regression + Elo Rolling Features → Brier 0.199

**Date:** 2026-05-09  
**Cycle:** fire-70  
**Source:** MDPI Information Vol.17(1):56, "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets" (2026)

## Key Finding

Logistic regression with rolling Elo features achieves **Brier=0.199** on 2026 NBA test data (2024 season holdout) — compared to our fleet best of **0.22012** (S15 random_forest). Gap: **0.021 Brier points**.

This is the target-breaking technique: if we can reproduce 0.199, we beat our `<0.20` target.

## Critical Features (SHAP analysis)

| Rank | Feature | Description |
|------|---------|-------------|
| 1 | `home_next` | Is the team's next game at home? (rolling schedule context) |
| 2 | `team_elo_5_y` | 5-game rolling Elo average |
| 3 | `team_elo` | Absolute Elo rating |

## Methodology Details

1. Strict **chronological** train/test split (train ≤ 2022, val 2023, test 2024 — no data leakage)
2. Rolling-form indicators: 3, 5, 10-game windows
3. Spatial shot-chart embeddings (secondary, adds ~0.002 Brier)
4. Monte Carlo dropout on LSTM version (LR baseline alone = 0.199)
5. XGBoost: Brier=0.202, AUC=0.754 (better on ranking, worse on calibration)

## Recommended Actions for Nomos42 Fleet

### Action 1 — Add `logistic_regression` to mutation pool (HIGH)

Current island MODEL_TYPES: `random_forest`, `xgboost`, `extra_trees`, `lightgbm`  
Add: `logistic_regression` with isotonic calibration

```python
# In hf-space/app.py MODEL_TYPES init:
"logistic_regression": {
    "model": LogisticRegression(C=1.0, max_iter=300, solver='lbfgs'),
    "calibration": "isotonic"
}
```

Expected: LR wins on Brier when Elo features are selected; ensemble diversity across RF/XGB/LR should push fleet best below 0.220.

### Action 2 — Verify Elo rolling columns in engine (HIGH)

Check `features/engine.py` for columns matching `elo_rolling_*` or `team_elo_5*`:  
```bash
grep -n 'elo_rolling\|team_elo' features/engine.py | head -20
```
If missing: add `team_elo_rolling_3`, `team_elo_rolling_5`, `team_elo_rolling_10` for both home and away teams.

### Action 3 — `home_next` schedule feature (MEDIUM)

Feature = "is the team's next game a home game?" — captures rest/travel asymmetry.  
May already exist as `team_next_home` or `schedule_home_next_1`. If missing, compute from schedule in `predict_today.py`.

### Action 4 — Cross-project: apply to Political (MEDIUM)

Analog features for political events:
- `consensus_prior_rolling_5` (5-event rolling agreement Elo)
- `event_momentum` (direction × magnitude of last 5 event moves)
- `market_home` analog = "is this category historically consensus-heavy?"

Same 1-line MODEL_TYPES change applies to `nomos-political-alpha` island app.py.

## Competitive Context

| Source | Model | Best Brier | Date |
|--------|-------|-----------|------|
| MDPI Information 2026 | LR + rolling Elo | **0.199** | 2026 |
| MDPI Information 2026 | XGBoost | 0.202 | 2026 |
| MDPI Computation 2025 | CNN | 0.221 | Oct 2025 |
| Nature Sci Reports 2025 | Stacked ensemble | competitive | Aug 2025 |
| Nomos42 fleet best | RF (S15) | 0.22012 | live |
| Nomos42 Pareto best | extra_trees (S15) | 0.21841 | live |
| **Nomos42 target** | — | **0.20** | target |

## Validation Plan

1. VM: `grep -n 'elo_rolling\|team_elo' features/engine.py` — confirm or add Elo rolling columns
2. Deploy logistic_regression to S14 (most recently stagnant, post-diversify at gen~300)
3. Monitor S14 gen 300–400 for Brier crossing 0.22295
4. If S14 breaks best → checkpoint + propagate logistic_regression to S13/S18/S22
5. Simultaneously add to political P7 (Rotation C target island)

## Why This Beats Trees for Brier

Logistic regression's probabilistic output is inherently calibrated (sigmoid maps to probability).  
Tree ensembles require post-hoc isotonic calibration to achieve comparable ECE.  
With clean Elo features, LR's linear decision boundary is sufficient — and its Brier score beats even XGBoost's calibrated version.  
Adding LR to the mutation pool gives the GA a third calibration paradigm to explore.
