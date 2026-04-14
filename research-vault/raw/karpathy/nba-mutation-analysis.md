# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-14 22:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| add_features | 5 | 0 | 0% | +0.00855 |
| change_min_samples_leaf | 3 | 0 | 0% | +0.00801 |
| change_max_features_ratio | 4 | 0 | 0% | +0.00735 |
| change_n_estimators | 4 | 0 | 0% | +0.00796 |
| change_model | 24 | 0 | 0% | +0.28626 |
| change_max_depth | 3 | 0 | 0% | +0.00868 |
| remove_features | 3 | 0 | 0% | +0.00872 |
| swap_features | 4 | 0 | 0% | +0.00719 |

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
| extra_trees | 4 | 0.22018 | 0.22142 | 0.22350 |
| gradient_boosting | 6 | 0.26543 | 0.27703 | 0.28324 |
| lightgbm | 6 | 0.23275 | 0.23580 | 0.23889 |
| random_forest | 26 | 0.21674 | 0.22022 | 0.22349 |
| xgboost | 4 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 3 | 0.21950 | 0.22090 |
| 200-209 | 47 | 0.21674 | 0.36225 |

## Data-Driven Recommendations

- BEST mutation type: **add_features** (0/5 hit rate)
- WORST mutation type: **add_features** (0/5 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21674)