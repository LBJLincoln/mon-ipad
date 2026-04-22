# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-22 05:00 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_features_ratio | 6 | 0 | 0% | +0.00928 |
| change_min_samples_leaf | 4 | 0 | 0% | +0.00943 |
| remove_features | 3 | 0 | 0% | +0.00917 |
| swap_features | 6 | 0 | 0% | +0.01049 |
| change_model | 25 | 0 | 0% | +0.36355 |
| change_max_depth | 3 | 0 | 0% | +0.00891 |
| add_features | 1 | 0 | 0% | +0.00933 |
| change_n_estimators | 2 | 0 | 0% | +0.00823 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 8 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 4 | 0.22379 | 0.22500 | 0.22702 |
| gradient_boosting | 4 | 0.26579 | 0.26839 | 0.27226 |
| lightgbm | 6 | 0.23142 | 0.23661 | 0.24019 |
| random_forest | 25 | 0.21927 | 0.22164 | 0.22612 |
| xgboost | 3 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 3 | 0.22068 | 0.22135 |
| 200-209 | 47 | 0.21927 | 0.41000 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_features_ratio** (0/6 hit rate)
- WORST mutation type: **change_max_features_ratio** (0/6 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21927)