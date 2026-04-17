# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-17 04:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_min_samples_leaf | 6 | 0 | 0% | +0.00710 |
| swap_features | 3 | 0 | 0% | +0.00806 |
| add_features | 6 | 0 | 0% | +0.00772 |
| change_n_estimators | 2 | 0 | 0% | +0.00812 |
| change_max_depth | 4 | 0 | 0% | +0.00797 |
| change_model | 24 | 0 | 0% | +0.10031 |
| remove_features | 5 | 0 | 0% | +0.00796 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 1 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 3 | 0.21859 | 0.21899 | 0.21971 |
| gradient_boosting | 10 | 0.26531 | 0.27359 | 0.28224 |
| lightgbm | 9 | 0.22757 | 0.23410 | 0.23980 |
| random_forest | 26 | 0.21735 | 0.21992 | 0.22154 |
| xgboost | 1 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 5 | 0.21945 | 0.22014 |
| 200-209 | 45 | 0.21735 | 0.26927 |

## Data-Driven Recommendations

- BEST mutation type: **change_min_samples_leaf** (0/6 hit rate)
- WORST mutation type: **change_min_samples_leaf** (0/6 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21735)