# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-15 22:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| remove_features | 5 | 0 | 0% | +0.02269 |
| add_features | 7 | 0 | 0% | +0.01903 |
| change_model | 13 | 0 | 0% | +0.04141 |
| change_max_features_ratio | 7 | 0 | 0% | +0.02233 |
| change_max_depth | 6 | 0 | 0% | +0.01349 |
| change_n_estimators | 3 | 0 | 0% | +0.01203 |
| swap_features | 3 | 0 | 0% | +0.04502 |
| change_min_samples_leaf | 6 | 0 | 0% | +0.00540 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 6 | 0.24356 | 0.24356 | 0.24356 |
| gradient_boosting | 1 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 6 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 37 | 0.20454 | 0.22312 | 0.27061 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 5 | 0.21884 | 0.22724 |
| 80-89 | 45 | 0.20454 | 0.22926 |

## Data-Driven Recommendations

- BEST mutation type: **remove_features** (0/5 hit rate)
- WORST mutation type: **remove_features** (0/5 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)