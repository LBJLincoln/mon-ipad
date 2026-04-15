# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-15 22:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_features_ratio | 6 | 0 | 0% | +0.00587 |
| change_max_depth | 4 | 0 | 0% | +0.00542 |
| remove_features | 5 | 0 | 0% | +0.00579 |
| swap_features | 2 | 0 | 0% | +0.00661 |
| add_features | 7 | 0 | 0% | +0.00641 |
| change_model | 23 | 0 | 0% | +0.42341 |
| change_n_estimators | 2 | 0 | 0% | +0.00677 |
| change_min_samples_leaf | 1 | 0 | 0% | +0.00573 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 7 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 2 | 0.21616 | 0.21647 | 0.21677 |
| gradient_boosting | 3 | 0.27070 | 0.27489 | 0.27985 |
| lightgbm | 6 | 0.22331 | 0.22685 | 0.23372 |
| random_forest | 27 | 0.21655 | 0.21823 | 0.22016 |
| xgboost | 5 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 5 | 0.21655 | 0.21797 |
| 200-209 | 45 | 0.21616 | 0.43158 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_features_ratio** (0/6 hit rate)
- WORST mutation type: **change_max_features_ratio** (0/6 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **extra_trees** (best Brier 0.21616)