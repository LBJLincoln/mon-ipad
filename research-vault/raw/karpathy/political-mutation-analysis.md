# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-13 08:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_n_estimators | 8 | 0 | 0% | +0.00451 |
| add_features | 12 | 0 | 0% | +0.01773 |
| change_max_depth | 4 | 0 | 0% | +0.01646 |
| change_max_features_ratio | 6 | 0 | 0% | +0.02298 |
| swap_features | 7 | 0 | 0% | +0.01901 |
| change_min_samples_leaf | 4 | 0 | 0% | +0.01035 |
| change_model | 5 | 0 | 0% | +0.05229 |
| remove_features | 4 | 0 | 0% | +0.02737 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 2 | 0.24356 | 0.24356 | 0.24356 |
| gradient_boosting | 3 | 0.26569 | 0.26569 | 0.26569 |
| random_forest | 45 | 0.20454 | 0.22091 | 0.23900 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 4 | 0.22595 | 0.23191 |
| 80-89 | 46 | 0.20454 | 0.22386 |

## Data-Driven Recommendations

- BEST mutation type: **change_n_estimators** (0/8 hit rate)
- WORST mutation type: **change_n_estimators** (0/8 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)