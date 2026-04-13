# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-13 06:48 UTC
> Best Brier: 0.1909689543969487
> Current model: gradient_boosting
> Current features: 85

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| swap_features | 5 | 0 | 0% | +0.03617 |
| change_max_depth | 5 | 0 | 0% | +0.00430 |
| change_min_samples_leaf | 11 | 0 | 0% | +0.02529 |
| change_model | 4 | 0 | 0% | +0.02562 |
| change_max_features_ratio | 6 | 0 | 0% | +0.03118 |
| add_features | 7 | 0 | 0% | +0.02562 |
| remove_features | 7 | 0 | 0% | +0.02715 |
| change_n_estimators | 5 | 0 | 0% | +0.00183 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 1 | 0.22237 | 0.22237 | 0.22237 |
| gradient_boosting | 46 | 0.19097 | 0.21371 | 0.23763 |
| lightgbm | 1 | 0.21074 | 0.21074 | 0.21074 |
| random_forest | 2 | 0.21663 | 0.21663 | 0.21663 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 80-89 | 43 | 0.19097 | 0.21351 |
| 90-99 | 7 | 0.20934 | 0.21659 |

## Data-Driven Recommendations

- BEST mutation type: **swap_features** (0/5 hit rate)
- WORST mutation type: **swap_features** (0/5 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **gradient_boosting** (best Brier 0.19097)