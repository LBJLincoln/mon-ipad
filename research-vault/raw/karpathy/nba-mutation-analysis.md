# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-16 06:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_model | 22 | 0 | 0% | +0.23191 |
| change_max_depth | 6 | 0 | 0% | +0.00827 |
| remove_features | 6 | 0 | 0% | +0.00848 |
| change_n_estimators | 2 | 0 | 0% | +0.00657 |
| add_features | 4 | 0 | 0% | +0.00882 |
| swap_features | 5 | 0 | 0% | +0.00987 |
| change_max_features_ratio | 2 | 0 | 0% | +0.01015 |
| change_min_samples_leaf | 3 | 0 | 0% | +0.01235 |

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
| extra_trees | 2 | 0.21697 | 0.21743 | 0.21790 |
| gradient_boosting | 4 | 0.26053 | 0.26284 | 0.26927 |
| lightgbm | 10 | 0.22182 | 0.22839 | 0.23230 |
| random_forest | 28 | 0.21716 | 0.22131 | 0.22507 |
| xgboost | 1 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 6 | 0.21800 | 0.22067 |
| 200-209 | 44 | 0.21697 | 0.33279 |

## Data-Driven Recommendations

- BEST mutation type: **change_model** (0/22 hit rate)
- WORST mutation type: **change_model** (0/22 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **extra_trees** (best Brier 0.21697)