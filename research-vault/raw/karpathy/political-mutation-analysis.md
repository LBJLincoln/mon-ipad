# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-22 05:00 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_features_ratio | 5 | 0 | 0% | +0.02076 |
| change_min_samples_leaf | 6 | 0 | 0% | +0.00577 |
| change_model | 10 | 0 | 0% | +0.05068 |
| swap_features | 3 | 0 | 0% | +0.03041 |
| change_n_estimators | 5 | 0 | 0% | +0.00847 |
| change_max_depth | 6 | 0 | 0% | +0.01640 |
| remove_features | 8 | 0 | 0% | +0.02891 |
| add_features | 7 | 0 | 0% | +0.02000 |

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
| gradient_boosting | 5 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 4 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 40 | 0.20454 | 0.22309 | 0.25330 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 8 | 0.22244 | 0.23346 |
| 80-89 | 42 | 0.20454 | 0.22876 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_features_ratio** (0/5 hit rate)
- WORST mutation type: **change_max_features_ratio** (0/5 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)