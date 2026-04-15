# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-15 16:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_depth | 10 | 0 | 0% | +0.01453 |
| change_model | 4 | 0 | 0% | +0.05599 |
| swap_features | 6 | 0 | 0% | +0.02536 |
| add_features | 6 | 0 | 0% | +0.01541 |
| change_n_estimators | 12 | 0 | 0% | +0.00427 |
| change_max_features_ratio | 5 | 0 | 0% | +0.01695 |
| change_min_samples_leaf | 4 | 0 | 0% | +0.01553 |
| remove_features | 3 | 0 | 0% | +0.02366 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| gradient_boosting | 3 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 1 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 46 | 0.20454 | 0.21887 | 0.23954 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 3 | 0.22404 | 0.22820 |
| 80-89 | 47 | 0.20454 | 0.22182 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_depth** (0/10 hit rate)
- WORST mutation type: **change_max_depth** (0/10 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)