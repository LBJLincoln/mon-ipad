# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-19 05:00 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_depth | 6 | 0 | 0% | +0.01272 |
| change_model | 22 | 0 | 0% | +0.23483 |
| remove_features | 5 | 0 | 0% | +0.01079 |
| change_max_features_ratio | 2 | 0 | 0% | +0.01135 |
| swap_features | 3 | 0 | 0% | +0.01070 |
| add_features | 3 | 0 | 0% | +0.01333 |
| change_min_samples_leaf | 3 | 0 | 0% | +0.01386 |
| change_n_estimators | 6 | 0 | 0% | +0.01400 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 5 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 5 | 0.22078 | 0.22299 | 0.22464 |
| gradient_boosting | 4 | 0.27071 | 0.27533 | 0.27809 |
| lightgbm | 7 | 0.22451 | 0.23115 | 0.24138 |
| random_forest | 28 | 0.22045 | 0.22470 | 0.22945 |
| xgboost | 1 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 5 | 0.22045 | 0.22297 |
| 200-209 | 45 | 0.22078 | 0.33358 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_depth** (0/6 hit rate)
- WORST mutation type: **change_max_depth** (0/6 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.22045)