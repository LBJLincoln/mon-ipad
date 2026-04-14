# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-14 16:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_n_estimators | 7 | 0 | 0% | +0.00896 |
| change_max_features_ratio | 2 | 0 | 0% | +0.00906 |
| remove_features | 3 | 0 | 0% | +0.00756 |
| change_max_depth | 9 | 0 | 0% | +0.00881 |
| add_features | 2 | 0 | 0% | +0.00993 |
| swap_features | 4 | 0 | 0% | +0.01016 |
| change_model | 22 | 0 | 0% | +0.27317 |
| change_min_samples_leaf | 1 | 0 | 0% | +0.00768 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 2 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 4 | 0.21771 | 0.21955 | 0.22172 |
| gradient_boosting | 6 | 0.26354 | 0.27180 | 0.27679 |
| lightgbm | 5 | 0.22948 | 0.23373 | 0.23630 |
| random_forest | 28 | 0.21882 | 0.22115 | 0.22389 |
| xgboost | 5 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 3 | 0.21882 | 0.21974 |
| 200-209 | 47 | 0.21771 | 0.34491 |

## Data-Driven Recommendations

- BEST mutation type: **change_n_estimators** (0/7 hit rate)
- WORST mutation type: **change_n_estimators** (0/7 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **extra_trees** (best Brier 0.21771)