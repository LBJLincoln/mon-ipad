# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-17 08:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_min_samples_leaf | 10 | 0 | 0% | +0.01108 |
| change_max_depth | 8 | 0 | 0% | +0.01362 |
| add_features | 7 | 0 | 0% | +0.02614 |
| remove_features | 10 | 0 | 0% | +0.03079 |
| change_model | 6 | 0 | 0% | +0.04371 |
| change_n_estimators | 6 | 0 | 0% | +0.00991 |
| change_max_features_ratio | 2 | 0 | 0% | +0.02496 |
| swap_features | 1 | 0 | 0% | +0.05610 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 1 | 0.24356 | 0.24356 | 0.24356 |
| gradient_boosting | 1 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 4 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 44 | 0.20454 | 0.22446 | 0.27017 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 10 | 0.21403 | 0.23534 |
| 80-89 | 40 | 0.20454 | 0.22531 |

## Data-Driven Recommendations

- BEST mutation type: **change_min_samples_leaf** (0/10 hit rate)
- WORST mutation type: **change_min_samples_leaf** (0/10 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)