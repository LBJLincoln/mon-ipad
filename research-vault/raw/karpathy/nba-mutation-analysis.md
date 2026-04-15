# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-15 18:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_min_samples_leaf | 7 | 0 | 0% | +0.00689 |
| change_max_features_ratio | 6 | 0 | 0% | +0.00600 |
| change_n_estimators | 4 | 0 | 0% | +0.00586 |
| swap_features | 2 | 0 | 0% | +0.00622 |
| change_max_depth | 3 | 0 | 0% | +0.00590 |
| change_model | 24 | 0 | 0% | +0.34501 |
| remove_features | 2 | 0 | 0% | +0.00717 |
| add_features | 2 | 0 | 0% | +0.00501 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 6 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 5 | 0.21677 | 0.21783 | 0.21930 |
| gradient_boosting | 6 | 0.26405 | 0.26742 | 0.27051 |
| lightgbm | 3 | 0.22263 | 0.22633 | 0.23071 |
| random_forest | 26 | 0.21632 | 0.21842 | 0.22143 |
| xgboost | 4 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 2 | 0.21792 | 0.21935 |
| 200-209 | 48 | 0.21632 | 0.38777 |

## Data-Driven Recommendations

- BEST mutation type: **change_min_samples_leaf** (0/7 hit rate)
- WORST mutation type: **change_min_samples_leaf** (0/7 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21632)