# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-21 05:00 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_n_estimators | 4 | 0 | 0% | +0.00207 |
| change_min_samples_leaf | 8 | 0 | 0% | +0.01012 |
| remove_features | 8 | 0 | 0% | +0.02950 |
| change_max_depth | 6 | 0 | 0% | +0.01350 |
| add_features | 8 | 0 | 0% | +0.02366 |
| change_model | 6 | 0 | 0% | +0.04664 |
| change_max_features_ratio | 6 | 0 | 0% | +0.02819 |
| swap_features | 4 | 0 | 0% | +0.03097 |

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
| gradient_boosting | 2 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 1 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 44 | 0.20454 | 0.22474 | 0.26746 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 8 | 0.21614 | 0.23404 |
| 80-89 | 42 | 0.20454 | 0.22674 |

## Data-Driven Recommendations

- BEST mutation type: **change_n_estimators** (0/4 hit rate)
- WORST mutation type: **change_n_estimators** (0/4 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)