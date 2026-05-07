# Rotation C: Port NBA CatBoost Success to Political Engine
**Date:** 2026-05-08 | **Fire:** 61 | **Rotation:** C (Port NBA Techniques → Political)

## Finding
S22 (TESTforge42/nba-evo-s22) just achieved a new all-time fleet Pareto best of **0.21850 Brier** using CatBoost_200f at gen=2309, beating the previous record of 0.21879 (S15 RandomForest_200f). Four consecutive Pareto candidates are all CatBoost_200f:

| gen  | brier   | ROI   | Sharpe |
|------|---------|-------|--------|
| 2309 | 0.21850 | 34.3% | 9.06   |
| 2307 | 0.21912 | 33.6% | 7.99   |
| 2309 | 0.21950 | 33.2% | 8.21   |
| 2308 | 0.21994 | 32.5% | 7.94   |

Pattern: CatBoost consistently outperforms RandomForest on the Pareto front at MAX_FEATURES=200.

## Political Engine Current State
- Best: P4 lightgbm 0.24904 (alltime)
- Models in use: logistic_regression, lightgbm, extra_trees, xgboost
- **CatBoost NOT in political model zoo**
- Feature candidates: 272 (vs NBA 3377) — primary bottleneck
- Data crons: 39d+ stale (VM work-queue item pending)

## Proposed Port (3 actions, prioritized)

### 1. Add CatBoost to political_engine.py model zoo (HIGH — 5-line change)
In the model candidates dict, add:
```python
"catboost": CatBoostClassifier(
    iterations=500, depth=6, learning_rate=0.05,
    loss_function='Logloss', verbose=0, random_state=42
)
```
Expected gain: ~0.001-0.003 Brier based on NBA delta (LightGBM→CatBoost advantage visible in S22 Pareto vs P4).

### 2. Verify NSGA-II Pareto is active on all political islands (MEDIUM)
NBA islands use NSGA-II multi-objective (brier + roi + sharpe). If political uses single-objective brier only, adding ROI/Sharpe as secondary objectives could unlock the same Pareto diversity that enabled S22's 0.21850 breakthrough. Check `political_engine.py` evolution loop.

### 3. Feature candidate expansion via data cron restart (HIGHEST LEVERAGE — VM)
Restart `fetch_political_data.py` + `insider_tracker.py` (39d+ stale). Expected: 272→320+ feature candidates. Each 10% feature expansion historically yields ~0.001 Brier improvement in political. VM work-queue item `vm-restart-political-data-crons` is HIGH priority.

## SOTA Context (fire-61)
- **MC-dropout uncertainty-aware RNN**: Brier 0.199 LR / 0.202 XGBoost on 2024 NBA test (MDPI Information 17/1/56). Uses live betting lines as sequential features. Gap to tree-only approach = market features + sequential modeling.
- **CNN tabular-only SOTA**: 0.221 — our fleet best 0.22012 already beats this.
- **Stacked ensemble SOTA** (Nature Sci Reports 2025): LightGBM + XGBoost + RF meta-learner — closest to our island architecture.
- **Next target**: sub-0.218 via validated CatBoost ensemble or MC-dropout calibration layer on island oracle output.

## Implementation Path
1. VM: Add catboost to `political_engine.py` model zoo (5-line diff)
2. VM: Restart political data crons (`vm-restart-political-data-crons` in work-queue)
3. Cloud (next cycle): Check if P-islands show catboost in `/api/status` model field
4. Future: If P-fleet best improves >0.002, port NSGA-II secondary objectives

## Priority: HIGH
CatBoost port is a 5-line VM change with expected positive return. Data cron restart is higher leverage but same VM task.
