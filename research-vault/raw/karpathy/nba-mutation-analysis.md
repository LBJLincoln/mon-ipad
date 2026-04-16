# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-16 18:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_min_samples_leaf | 3 | 0 | 0% | +0.00922 |
| swap_features | 3 | 0 | 0% | +0.00914 |
| add_features | 7 | 0 | 0% | +0.00950 |
| change_model | 23 | 0 | 0% | +0.29364 |
| change_max_depth | 2 | 0 | 0% | +0.00958 |
| change_n_estimators | 5 | 0 | 0% | +0.00810 |
| change_max_features_ratio | 4 | 0 | 0% | +0.00784 |
| remove_features | 3 | 0 | 0% | +0.00764 |

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
| extra_trees | 5 | 0.21795 | 0.21925 | 0.22305 |
| gradient_boosting | 6 | 0.26485 | 0.26963 | 0.27501 |
| lightgbm | 4 | 0.22780 | 0.22996 | 0.23209 |
| random_forest | 27 | 0.21896 | 0.22090 | 0.22396 |
| xgboost | 3 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 3 | 0.21974 | 0.21983 |
| 200-209 | 47 | 0.21795 | 0.36040 |

## Data-Driven Recommendations

- BEST mutation type: **change_min_samples_leaf** (0/3 hit rate)
- WORST mutation type: **change_min_samples_leaf** (0/3 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **extra_trees** (best Brier 0.21795)