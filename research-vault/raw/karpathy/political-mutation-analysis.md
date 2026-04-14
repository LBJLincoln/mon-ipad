# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-14 20:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_depth | 7 | 0 | 0% | +0.01701 |
| swap_features | 6 | 0 | 0% | +0.02755 |
| change_model | 6 | 0 | 0% | +0.05058 |
| change_max_features_ratio | 8 | 0 | 0% | +0.02114 |
| change_n_estimators | 2 | 0 | 0% | +0.00696 |
| change_min_samples_leaf | 12 | 0 | 0% | +0.00713 |
| remove_features | 4 | 0 | 0% | +0.02795 |
| add_features | 5 | 0 | 0% | +0.01991 |

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
| gradient_boosting | 3 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 2 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 44 | 0.20454 | 0.22191 | 0.24367 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 4 | 0.22266 | 0.23249 |
| 80-89 | 46 | 0.20454 | 0.22533 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_depth** (0/7 hit rate)
- WORST mutation type: **change_max_depth** (0/7 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)