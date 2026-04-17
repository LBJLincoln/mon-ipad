# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-17 10:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| remove_features | 9 | 0 | 0% | +0.01034 |
| change_min_samples_leaf | 4 | 0 | 0% | +0.00997 |
| change_max_depth | 2 | 0 | 0% | +0.00804 |
| add_features | 7 | 0 | 0% | +0.01149 |
| change_n_estimators | 3 | 0 | 0% | +0.00975 |
| change_model | 20 | 0 | 0% | +0.25652 |
| swap_features | 4 | 0 | 0% | +0.01236 |
| change_max_features_ratio | 1 | 0 | 0% | +0.01196 |

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
| extra_trees | 3 | 0.22015 | 0.22111 | 0.22237 |
| gradient_boosting | 4 | 0.26056 | 0.27042 | 0.27522 |
| lightgbm | 7 | 0.22791 | 0.23271 | 0.24060 |
| random_forest | 30 | 0.22003 | 0.22285 | 0.22584 |
| xgboost | 4 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 9 | 0.22068 | 0.22252 |
| 200-209 | 41 | 0.22003 | 0.34285 |

## Data-Driven Recommendations

- BEST mutation type: **remove_features** (0/9 hit rate)
- WORST mutation type: **remove_features** (0/9 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.22003)