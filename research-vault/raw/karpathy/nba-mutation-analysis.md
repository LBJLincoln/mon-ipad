# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-16 14:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_min_samples_leaf | 7 | 0 | 0% | +0.00671 |
| change_max_features_ratio | 2 | 0 | 0% | +0.00543 |
| add_features | 4 | 0 | 0% | +0.00387 |
| change_max_depth | 5 | 0 | 0% | +0.00748 |
| change_model | 25 | 0 | 0% | +0.33516 |
| swap_features | 1 | 0 | 0% | +0.00772 |
| change_n_estimators | 3 | 0 | 0% | +0.00781 |
| remove_features | 3 | 0 | 0% | +0.00819 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 4 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 4 | 0.21675 | 0.21822 | 0.22093 |
| gradient_boosting | 9 | 0.24691 | 0.26117 | 0.27321 |
| lightgbm | 2 | 0.22791 | 0.23011 | 0.23231 |
| random_forest | 25 | 0.21443 | 0.21884 | 0.22211 |
| xgboost | 6 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 3 | 0.22018 | 0.22037 |
| 200-209 | 47 | 0.21443 | 0.39348 |

## Data-Driven Recommendations

- BEST mutation type: **change_min_samples_leaf** (0/7 hit rate)
- WORST mutation type: **change_min_samples_leaf** (0/7 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21443)