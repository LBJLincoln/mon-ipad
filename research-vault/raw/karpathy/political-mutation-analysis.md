# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-20 05:00 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| remove_features | 6 | 0 | 0% | +0.02038 |
| change_max_depth | 10 | 0 | 0% | +0.01409 |
| change_min_samples_leaf | 9 | 0 | 0% | +0.01207 |
| change_n_estimators | 4 | 0 | 0% | +0.00363 |
| add_features | 3 | 0 | 0% | +0.01239 |
| change_max_features_ratio | 3 | 0 | 0% | +0.02573 |
| change_model | 7 | 0 | 0% | +0.04914 |
| swap_features | 8 | 0 | 0% | +0.03137 |

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
| lightgbm | 3 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 43 | 0.20454 | 0.22202 | 0.27230 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 6 | 0.21313 | 0.22493 |
| 80-89 | 44 | 0.20454 | 0.22666 |

## Data-Driven Recommendations

- BEST mutation type: **remove_features** (0/6 hit rate)
- WORST mutation type: **remove_features** (0/6 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)