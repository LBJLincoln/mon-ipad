# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-18 05:00 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_min_samples_leaf | 3 | 0 | 0% | +0.01480 |
| change_n_estimators | 5 | 0 | 0% | +0.01378 |
| change_max_features_ratio | 4 | 0 | 0% | +0.01382 |
| change_max_depth | 5 | 0 | 0% | +0.01427 |
| change_model | 25 | 0 | 0% | +0.21071 |
| add_features | 5 | 0 | 0% | +0.01459 |
| remove_features | 2 | 0 | 0% | +0.01287 |
| swap_features | 1 | 0 | 0% | +0.01556 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 3 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 6 | 0.22257 | 0.22381 | 0.22480 |
| gradient_boosting | 4 | 0.26856 | 0.27212 | 0.27736 |
| lightgbm | 9 | 0.22926 | 0.23788 | 0.25359 |
| random_forest | 25 | 0.22418 | 0.22635 | 0.22812 |
| xgboost | 3 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 2 | 0.22418 | 0.22506 |
| 200-209 | 48 | 0.22257 | 0.32877 |

## Data-Driven Recommendations

- BEST mutation type: **change_min_samples_leaf** (0/3 hit rate)
- WORST mutation type: **change_min_samples_leaf** (0/3 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **extra_trees** (best Brier 0.22257)