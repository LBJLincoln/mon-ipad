# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-20 05:00 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_max_depth | 4 | 0 | 0% | +0.01285 |
| swap_features | 4 | 0 | 0% | +0.01174 |
| change_n_estimators | 3 | 0 | 0% | +0.01198 |
| change_min_samples_leaf | 3 | 0 | 0% | +0.01378 |
| change_max_features_ratio | 2 | 0 | 0% | +0.01087 |
| add_features | 9 | 0 | 0% | +0.01228 |
| change_model | 23 | 0 | 0% | +0.29169 |
| remove_features | 2 | 0 | 0% | +0.01158 |

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
| extra_trees | 8 | 0.22185 | 0.22371 | 0.22537 |
| gradient_boosting | 2 | 0.27566 | 0.27672 | 0.27778 |
| lightgbm | 5 | 0.23555 | 0.24917 | 0.25961 |
| random_forest | 27 | 0.22158 | 0.22444 | 0.22826 |
| xgboost | 4 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 2 | 0.22367 | 0.22376 |
| 200-209 | 48 | 0.22158 | 0.35836 |

## Data-Driven Recommendations

- BEST mutation type: **change_max_depth** (0/4 hit rate)
- WORST mutation type: **change_max_depth** (0/4 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.22158)