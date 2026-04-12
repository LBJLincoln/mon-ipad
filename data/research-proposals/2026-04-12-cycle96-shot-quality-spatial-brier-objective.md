# NBA Research Proposal: Shot-Quality Spatial Embeddings + XGBoost Brier Objective
**Date:** 2026-04-12 | **Brain cycle:** 96 | **Priority:** HIGH

## Problem
Current NBA engine (v3.1-59cat+) optimizes XGBoost with `binary:logistic` (log-loss). Walk-forward avg Brier = 0.22447. Best ever = 0.21570 (TabICL, Colab). Gap to target = 0.0157.

Two research findings from 2025-2026 literature directly applicable:
1. Shot-chart spatial embeddings provide complementary signal beyond team stats (MDPI 2025)
2. Direct Brier optimization via `reg:squarederror` on probability labels outperforms binary logistic when Brier is the evaluation metric

---

## Improvement 1: XGBoost Brier-Direct Objective

### What
Switch XGBoost training objective from `binary:logistic` → `reg:squarederror` (regression on 0/1 labels), which directly minimizes mean squared error = Brier score.

### Why
- Brier score = MSE of predicted probabilities vs 0/1 outcomes
- `binary:logistic` minimizes cross-entropy (log-loss), which is a surrogate for Brier
- `reg:squarederror` on binary outcomes IS direct Brier minimization
- The resulting model outputs uncalibrated probability estimates (may need isotonic recalibration if outputs drift outside [0,1])
- MDPI uncertainty-aware paper (2025) confirms direct probability calibration improves both discrimination AND calibration vs standard binary classification

### Implementation
```python
# In hf-space/app.py — individual XGBoost evaluations
# Current:
params = {'objective': 'binary:logistic', 'eval_metric': 'logloss', ...}

# Proposed (add as new model_type = 'xgboost_brier'):
params_brier = {
    'objective': 'reg:squarederror',  # direct Brier minimization
    'eval_metric': 'rmse',
    'max_depth': params['max_depth'],
    'n_estimators': params['n_estimators'],
    'learning_rate': params['learning_rate'],
    'subsample': params.get('subsample', 0.8),
    'colsample_bytree': params.get('colsample_bytree', 0.8),
    'min_child_weight': params.get('min_child_weight', 5),
    'reg_alpha': params.get('reg_alpha', 0.1),
    'reg_lambda': params.get('reg_lambda', 1.0),
    'clip': (0.05, 0.95),  # CRITICAL: clip outputs to valid probability range
}
# After prediction: preds = np.clip(model.predict(X), 0.05, 0.95)
```

### Expected Brier delta
-0.001 to -0.003 (estimated from political alpha analogous shift)

### Risk
Low. `reg:squarederror` is a standard XGBoost objective. Clip to [0.05, 0.95] prevents out-of-range outputs. Run A/B in evolution (new `model_type = 'xgboost_brier'`) alongside existing `binary:logistic`.

### Deploy as
`xgboost_brier` model_type in GA chromosome. Add to model_type options in `ALLOWED_MODELS` list in hf-space/app.py.

---

## Improvement 2: Shot-Quality Spatial Zone Features (Cat52)

### What
18 features encoding shot-quality spatial context as team-level signals.
Based on: *Uncertainty-Aware Machine Learning for NBA Forecasting* (MDPI Information 2025, Vol 17).
Key finding: shot-chart embeddings provide complementary calibration improvement beyond team-level statistics.

### Features
```
tc52_avg_shot_quality_home       — weighted avg shot quality (distance × rim-proximity)
tc52_avg_shot_quality_away
tc52_paint_shot_rate_home        — % shots from paint (0-8 ft)
tc52_paint_shot_rate_away
tc52_midrange_pct_home           — % shots from midrange (8-22 ft, lower efficiency)
tc52_midrange_pct_away
tc52_corner_3_rate_home          — corner 3s (highest efficiency 3pt zone)
tc52_corner_3_rate_away
tc52_shot_quality_differential   — home minus away (composite advantage)
tc52_paint_pressure_adv          — paint shot rate differential (home adv)
tc52_3pt_zone_efficiency_home    — 3PT% weighted by zone (corner vs above break)
tc52_3pt_zone_efficiency_away
tc52_assisted_shot_rate_home     — % shots off assists (system vs ISO quality)
tc52_assisted_shot_rate_away
tc52_shot_quality_momentum_home  — rolling 10-game shot quality trend
tc52_shot_quality_momentum_away
tc52_opponent_def_zone_adj       — opponent's defensive zone tendency
tc52_zone_vs_opponent_def_match  — home shot zones vs opponent's defensive weak zones
```

### Data Source
NBA Stats API: `/stats/shotchartdetail` + `/stats/teamdashboardbygeneralgeneralsplits`
- Already fetched in predict_today.py pipeline
- Zone breakdowns: RestrictedArea, InThePaint, MidRange, LeftCorner3, RightCorner3, AboveBreakLeft3, AboveBreakRight3

### Implementation
```python
# In features/engine.py — add to categories_ext list:
("52_shot_quality_spatial", self._cat52.extract)

# New module: features/cat52_shot_quality_spatial.py
# Zone efficiency mapping from NBA zone codes:
ZONE_EFFICIENCY = {
    'Restricted Area': 1.28,   # highest: near-rim layups
    'In The Paint (Non-RA)': 0.82,
    'Mid-Range': 0.76,         # inefficient zone
    'Left Corner 3': 1.13,
    'Right Corner 3': 1.14,
    'Above the Break 3': 1.04,
    'Backcourt': 0.10,
}
```

### Expected Brier delta
-0.001 to -0.003 (literature reports consistent calibration improvement from shot-chart features)

### Cross-project note
Analogy in Political Alpha: spatial/zone clustering of political donations → sector affinity mapping. Same principle: aggregate spatial patterns compress informative signals that raw stats miss.

---

## Implementation Priority

| Improvement | Effort | Expected Brier | Deploy Target |
|-------------|--------|----------------|---------------|
| XGBoost Brier objective (`xgboost_brier` model_type) | Low (config change) | -0.001 to -0.003 | Next GA reset (S10/S11 target) |
| Cat52 shot-quality spatial (18f) | Medium (new data fetch) | -0.001 to -0.003 | When shot zone data available |
| Combined both | - | -0.003 to -0.006 | Sequential (objective first) |

## Action Items for Next Cycle
- [ ] Add `xgboost_brier` to ALLOWED_MODELS in hf-space/app.py
- [ ] Update GA init to include `xgboost_brier` in model_type sampling
- [ ] Create features/cat52_shot_quality_spatial.py (18 features)
- [ ] Add zone data fetch to scripts/predict_today.py pipeline
- [ ] Update ENGINE_VERSION to v3.1-61cat after Cat52 integration

## Sources
- [Uncertainty-Aware ML for NBA Forecasting (MDPI Information 2025)](https://www.mdpi.com/2078-2489/17/1/56)
- [Stacked Ensemble for NBA Outcome Prediction (Nature Sci Reports 2025)](https://www.nature.com/articles/s41598-025-13657-1)
- [Key Factors in NBA Game Outcomes via ML (Preprints.org 2025)](https://www.preprints.org/manuscript/202504.1348)
