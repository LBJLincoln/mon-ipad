# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-13 16:23 UTC
> Best Brier: 0.21349678992299034
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_depth | 3 | 1 | 33% | +0.00174 |
| change_model | 21 | 1 | 5% | +0.34545 |
| remove_features | 8 | 1 | 12% | +0.00172 |
| change_n_estimators | 2 | 1 | 50% | +0.00118 |
| change_max_features_ratio | 3 | 0 | 0% | +0.00180 |
| change_min_samples_leaf | 4 | 0 | 0% | +0.00158 |
| swap_features | 6 | 0 | 0% | +0.00163 |
| add_features | 3 | 0 | 0% | +0.00137 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 4
- Improvement rate: 8.0%
- Current no-improve streak: 8
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 6 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 20 | 0.21410 | 0.21600 | 0.21794 |
| gradient_boosting | 3 | 0.24387 | 0.25242 | 0.25888 |
| lightgbm | 5 | 0.22307 | 0.22527 | 0.22854 |
| random_forest | 13 | 0.21350 | 0.21534 | 0.21926 |
| xgboost | 3 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 5 | 0.21486 | 0.21600 |
| 200-209 | 21 | 0.21350 | 0.32851 |
| 70-79 | 22 | 0.21410 | 0.43480 |
| 80-89 | 2 | 0.21493 | 0.22940 |

## Data-Driven Recommendations

- BEST mutation type: **change_n_estimators** (1/2 hit rate)
- WORST mutation type: **change_max_features_ratio** (0/3 hit rate) — avoid
- STUCK: 8 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21350)