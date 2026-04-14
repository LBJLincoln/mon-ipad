# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-14 18:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| add_features | 1 | 0 | 0% | +0.01194 |
| change_model | 26 | 0 | 0% | +0.29269 |
| swap_features | 2 | 0 | 0% | +0.01041 |
| change_min_samples_leaf | 3 | 0 | 0% | +0.00892 |
| change_max_depth | 4 | 0 | 0% | +0.00947 |
| remove_features | 5 | 0 | 0% | +0.00886 |
| change_n_estimators | 4 | 0 | 0% | +0.00955 |
| change_max_features_ratio | 5 | 0 | 0% | +0.00907 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 6 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 3 | 0.22042 | 0.22126 | 0.22259 |
| gradient_boosting | 5 | 0.26634 | 0.27094 | 0.27731 |
| lightgbm | 9 | 0.22999 | 0.23426 | 0.23791 |
| random_forest | 24 | 0.21915 | 0.22157 | 0.22427 |
| xgboost | 3 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 5 | 0.21925 | 0.22104 |
| 200-209 | 45 | 0.21915 | 0.38532 |

## Data-Driven Recommendations

- BEST mutation type: **add_features** (0/1 hit rate)
- WORST mutation type: **add_features** (0/1 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21915)