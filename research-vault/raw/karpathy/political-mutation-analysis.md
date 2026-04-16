# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-16 04:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| add_features | 9 | 0 | 0% | +0.01659 |
| swap_features | 9 | 0 | 0% | +0.02874 |
| change_model | 6 | 0 | 0% | +0.04346 |
| change_min_samples_leaf | 8 | 0 | 0% | +0.00664 |
| remove_features | 5 | 0 | 0% | +0.03140 |
| change_max_features_ratio | 5 | 0 | 0% | +0.02212 |
| change_n_estimators | 5 | 0 | 0% | +0.00911 |
| change_max_depth | 3 | 0 | 0% | +0.01660 |

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
| gradient_boosting | 1 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 3 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 44 | 0.20454 | 0.22327 | 0.24501 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 5 | 0.22535 | 0.23594 |
| 80-89 | 45 | 0.20454 | 0.22516 |

## Data-Driven Recommendations

- BEST mutation type: **add_features** (0/9 hit rate)
- WORST mutation type: **add_features** (0/9 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)