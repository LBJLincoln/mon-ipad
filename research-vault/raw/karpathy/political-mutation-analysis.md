# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-14 08:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_depth | 6 | 0 | 0% | +0.01547 |
| swap_features | 7 | 0 | 0% | +0.02492 |
| change_max_features_ratio | 6 | 0 | 0% | +0.02150 |
| add_features | 6 | 0 | 0% | +0.02047 |
| change_n_estimators | 4 | 0 | 0% | +0.00933 |
| remove_features | 5 | 0 | 0% | +0.03432 |
| change_min_samples_leaf | 9 | 0 | 0% | +0.00980 |
| change_model | 7 | 0 | 0% | +0.05188 |

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
| gradient_boosting | 4 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 1 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 43 | 0.20454 | 0.22352 | 0.25825 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 5 | 0.22232 | 0.23887 |
| 80-89 | 45 | 0.20454 | 0.22694 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_depth** (0/6 hit rate)
- WORST mutation type: **change_max_depth** (0/6 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)