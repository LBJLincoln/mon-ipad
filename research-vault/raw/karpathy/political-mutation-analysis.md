# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-14 16:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| remove_features | 8 | 0 | 0% | +0.01924 |
| change_min_samples_leaf | 7 | 0 | 0% | +0.01384 |
| change_max_features_ratio | 5 | 0 | 0% | +0.02511 |
| swap_features | 4 | 0 | 0% | +0.02150 |
| change_model | 6 | 0 | 0% | +0.05033 |
| add_features | 9 | 0 | 0% | +0.01817 |
| change_n_estimators | 6 | 0 | 0% | +0.01106 |
| change_max_depth | 5 | 0 | 0% | +0.01986 |

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
| lightgbm | 1 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 44 | 0.20454 | 0.22253 | 0.24306 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 8 | 0.21644 | 0.22379 |
| 80-89 | 42 | 0.20454 | 0.22691 |

## Data-Driven Recommendations

- BEST mutation type: **remove_features** (0/8 hit rate)
- WORST mutation type: **remove_features** (0/8 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)