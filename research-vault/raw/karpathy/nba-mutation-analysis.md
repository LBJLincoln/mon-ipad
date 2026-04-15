# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-15 06:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| remove_features | 5 | 0 | 0% | +0.00680 |
| add_features | 3 | 0 | 0% | +0.00558 |
| change_max_depth | 5 | 0 | 0% | +0.00583 |
| swap_features | 1 | 0 | 0% | +0.00534 |
| change_n_estimators | 5 | 0 | 0% | +0.00545 |
| change_min_samples_leaf | 6 | 0 | 0% | +0.00619 |
| change_model | 23 | 0 | 0% | +0.38540 |
| change_max_features_ratio | 2 | 0 | 0% | +0.00769 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 4 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 4 | 0.21602 | 0.21725 | 0.21861 |
| gradient_boosting | 2 | 0.25189 | 0.25379 | 0.25569 |
| lightgbm | 6 | 0.22400 | 0.22797 | 0.23231 |
| random_forest | 27 | 0.21499 | 0.21829 | 0.22119 |
| xgboost | 7 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 5 | 0.21738 | 0.21899 |
| 200-209 | 45 | 0.21499 | 0.41208 |

## Data-Driven Recommendations

- BEST mutation type: **remove_features** (0/5 hit rate)
- WORST mutation type: **remove_features** (0/5 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21499)