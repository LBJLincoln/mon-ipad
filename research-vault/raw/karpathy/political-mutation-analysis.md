# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 10 iterations on 2026-04-13 14:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| remove_features | 1 | 0 | 0% | +0.00639 |
| change_model | 3 | 0 | 0% | +0.04689 |
| change_max_depth | 1 | 0 | 0% | +0.01240 |
| change_max_features_ratio | 2 | 0 | 0% | +0.01785 |
| change_n_estimators | 3 | 0 | 0% | +0.00275 |

## Stagnation Analysis

- Total iterations: 10
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 10
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 1 | 0.24356 | 0.24356 | 0.24356 |
| gradient_boosting | 1 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 1 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 7 | 0.20454 | 0.21351 | 0.22242 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 1 | 0.21093 | 0.21093 |
| 80-89 | 9 | 0.20454 | 0.22644 |

## Data-Driven Recommendations

- BEST mutation type: **remove_features** (0/1 hit rate)
- WORST mutation type: **remove_features** (0/1 hit rate) — avoid
- STUCK: 10 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)