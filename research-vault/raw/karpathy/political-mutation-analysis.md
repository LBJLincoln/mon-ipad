# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-16 10:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_n_estimators | 13 | 0 | 0% | +0.00832 |
| change_min_samples_leaf | 7 | 0 | 0% | +0.01023 |
| swap_features | 3 | 0 | 0% | +0.03263 |
| remove_features | 6 | 0 | 0% | +0.02542 |
| change_max_features_ratio | 8 | 0 | 0% | +0.02592 |
| change_model | 9 | 0 | 0% | +0.05377 |
| add_features | 2 | 0 | 0% | +0.02253 |
| change_max_depth | 2 | 0 | 0% | +0.01002 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 3 | 0.24356 | 0.24356 | 0.24356 |
| gradient_boosting | 6 | 0.26569 | 0.26569 | 0.26569 |
| random_forest | 41 | 0.20454 | 0.22168 | 0.26479 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 6 | 0.20795 | 0.22996 |
| 80-89 | 44 | 0.20454 | 0.22804 |

## Data-Driven Recommendations

- BEST mutation type: **change_n_estimators** (0/13 hit rate)
- WORST mutation type: **change_n_estimators** (0/13 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)