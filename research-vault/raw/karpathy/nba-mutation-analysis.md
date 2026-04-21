# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-21 05:00 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_min_samples_leaf | 3 | 0 | 0% | +0.01207 |
| change_max_features_ratio | 3 | 0 | 0% | +0.01317 |
| swap_features | 4 | 0 | 0% | +0.01153 |
| change_max_depth | 4 | 0 | 0% | +0.01307 |
| change_model | 26 | 0 | 0% | +0.23260 |
| change_n_estimators | 3 | 0 | 0% | +0.01115 |
| add_features | 4 | 0 | 0% | +0.01137 |
| remove_features | 3 | 0 | 0% | +0.01293 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| catboost | 2 | 1.00000 | 1.00000 | 1.00000 |
| extra_trees | 9 | 0.22118 | 0.22247 | 0.22389 |
| gradient_boosting | 4 | 0.26557 | 0.27552 | 0.28707 |
| lightgbm | 6 | 0.22997 | 0.24335 | 0.25992 |
| random_forest | 24 | 0.22124 | 0.22434 | 0.22793 |
| xgboost | 5 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 3 | 0.22342 | 0.22511 |
| 200-209 | 47 | 0.22118 | 0.34624 |

## Data-Driven Recommendations

- BEST mutation type: **change_min_samples_leaf** (0/3 hit rate)
- WORST mutation type: **change_min_samples_leaf** (0/3 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **extra_trees** (best Brier 0.22118)