# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-15 04:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_depth | 5 | 0 | 0% | +0.01656 |
| change_model | 9 | 0 | 0% | +0.04935 |
| add_features | 3 | 0 | 0% | +0.02278 |
| remove_features | 4 | 0 | 0% | +0.03054 |
| change_max_features_ratio | 9 | 0 | 0% | +0.01980 |
| change_n_estimators | 10 | 0 | 0% | +0.00657 |
| swap_features | 4 | 0 | 0% | +0.03060 |
| change_min_samples_leaf | 6 | 0 | 0% | +0.00308 |

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
| lightgbm | 3 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 41 | 0.20454 | 0.22059 | 0.24455 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 4 | 0.23036 | 0.23508 |
| 80-89 | 46 | 0.20454 | 0.22585 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_depth** (0/5 hit rate)
- WORST mutation type: **change_max_depth** (0/5 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)