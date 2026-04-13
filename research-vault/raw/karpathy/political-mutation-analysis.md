# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-13 06:48 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_min_samples_leaf | 13 | 0 | 0% | +0.01386 |
| remove_features | 4 | 0 | 0% | +0.03169 |
| swap_features | 5 | 0 | 0% | +0.03414 |
| add_features | 4 | 0 | 0% | +0.02975 |
| change_model | 7 | 0 | 0% | +0.04893 |
| change_max_features_ratio | 5 | 0 | 0% | +0.02081 |
| change_n_estimators | 8 | 0 | 0% | +0.00822 |
| change_max_depth | 4 | 0 | 0% | +0.01643 |

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
| lightgbm | 2 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 43 | 0.20454 | 0.22390 | 0.24408 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 4 | 0.22465 | 0.23623 |
| 80-89 | 46 | 0.20454 | 0.22732 |

## Data-Driven Recommendations

- BEST mutation type: **change_min_samples_leaf** (0/13 hit rate)
- WORST mutation type: **change_min_samples_leaf** (0/13 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)