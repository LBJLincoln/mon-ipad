# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-19 05:00 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_features_ratio | 8 | 0 | 0% | +0.02506 |
| change_model | 12 | 0 | 0% | +0.04702 |
| change_min_samples_leaf | 9 | 0 | 0% | +0.00590 |
| change_max_depth | 3 | 0 | 0% | +0.01629 |
| remove_features | 5 | 0 | 0% | +0.02949 |
| add_features | 6 | 0 | 0% | +0.01996 |
| swap_features | 4 | 0 | 0% | +0.02469 |
| change_n_estimators | 3 | 0 | 0% | +0.00275 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 3 | 0.24356 | 0.24356 | 0.24356 |
| gradient_boosting | 4 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 5 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 38 | 0.20454 | 0.22235 | 0.24508 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 5 | 0.22762 | 0.23403 |
| 80-89 | 45 | 0.20454 | 0.22884 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_features_ratio** (0/8 hit rate)
- WORST mutation type: **change_max_features_ratio** (0/8 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)