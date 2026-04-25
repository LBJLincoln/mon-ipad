# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-25 05:00 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_n_estimators | 7 | 0 | 0% | +0.01254 |
| change_max_depth | 5 | 0 | 0% | +0.01155 |
| swap_features | 1 | 0 | 0% | +0.01394 |
| add_features | 7 | 0 | 0% | +0.01038 |
| change_max_features_ratio | 2 | 0 | 0% | +0.01211 |
| remove_features | 6 | 0 | 0% | +0.01117 |
| change_model | 21 | 0 | 0% | +0.24270 |
| change_min_samples_leaf | 1 | 0 | 0% | +0.01026 |

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
| extra_trees | 5 | 0.22077 | 0.22191 | 0.22343 |
| gradient_boosting | 4 | 0.25761 | 0.26438 | 0.26785 |
| lightgbm | 6 | 0.22760 | 0.23090 | 0.23216 |
| random_forest | 29 | 0.22143 | 0.22369 | 0.22638 |
| xgboost | 2 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 6 | 0.22225 | 0.22335 |
| 200-209 | 44 | 0.22077 | 0.33407 |

## Data-Driven Recommendations

- BEST mutation type: **change_n_estimators** (0/7 hit rate)
- WORST mutation type: **change_n_estimators** (0/7 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **extra_trees** (best Brier 0.22077)