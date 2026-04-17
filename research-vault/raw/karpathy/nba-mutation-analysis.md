# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-17 08:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_features_ratio | 4 | 0 | 0% | +0.00861 |
| change_max_depth | 3 | 0 | 0% | +0.00931 |
| change_n_estimators | 7 | 0 | 0% | +0.00844 |
| remove_features | 9 | 0 | 0% | +0.00840 |
| change_min_samples_leaf | 3 | 0 | 0% | +0.00792 |
| change_model | 22 | 0 | 0% | +0.37310 |
| swap_features | 1 | 0 | 0% | +0.01180 |
| add_features | 1 | 0 | 0% | +0.00742 |

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
| extra_trees | 5 | 0.21940 | 0.22175 | 0.22290 |
| gradient_boosting | 4 | 0.25033 | 0.26891 | 0.27824 |
| lightgbm | 3 | 0.22498 | 0.23059 | 0.23975 |
| random_forest | 28 | 0.21772 | 0.22075 | 0.22398 |
| xgboost | 3 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 9 | 0.21772 | 0.22058 |
| 200-209 | 41 | 0.21852 | 0.41639 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_features_ratio** (0/4 hit rate)
- WORST mutation type: **change_max_features_ratio** (0/4 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21772)