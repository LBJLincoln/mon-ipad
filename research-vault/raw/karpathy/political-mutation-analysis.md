# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-18 05:00 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| remove_features | 7 | 0 | 0% | +0.03075 |
| add_features | 4 | 0 | 0% | +0.01500 |
| change_n_estimators | 11 | 0 | 0% | +0.00559 |
| change_max_features_ratio | 7 | 0 | 0% | +0.01794 |
| swap_features | 5 | 0 | 0% | +0.03245 |
| change_max_depth | 3 | 0 | 0% | +0.01617 |
| change_model | 7 | 0 | 0% | +0.05209 |
| change_min_samples_leaf | 6 | 0 | 0% | +0.00961 |

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
| gradient_boosting | 4 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 2 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 43 | 0.20454 | 0.22154 | 0.25446 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 7 | 0.21773 | 0.23529 |
| 80-89 | 43 | 0.20454 | 0.22501 |

## Data-Driven Recommendations

- BEST mutation type: **remove_features** (0/7 hit rate)
- WORST mutation type: **remove_features** (0/7 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)