# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-15 10:23 UTC
> Best Brier: 0.21218334576044304
> Current model: random_forest
> Current features: 200

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_n_estimators | 5 | 0 | 0% | +0.00682 |
| change_min_samples_leaf | 2 | 0 | 0% | +0.00647 |
| swap_features | 6 | 0 | 0% | +0.00745 |
| remove_features | 2 | 0 | 0% | +0.00635 |
| add_features | 5 | 0 | 0% | +0.00645 |
| change_max_features_ratio | 4 | 0 | 0% | +0.00703 |
| change_model | 22 | 0 | 0% | +0.20329 |
| change_max_depth | 4 | 0 | 0% | +0.00863 |

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
| extra_trees | 4 | 0.21649 | 0.21847 | 0.21968 |
| gradient_boosting | 7 | 0.25849 | 0.26710 | 0.28039 |
| lightgbm | 6 | 0.22791 | 0.23281 | 0.23740 |
| random_forest | 28 | 0.21529 | 0.21930 | 0.22315 |
| xgboost | 3 | 1.00000 | 1.00000 | 1.00000 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 190-199 | 2 | 0.21766 | 0.21853 |
| 200-209 | 48 | 0.21529 | 0.30925 |

## Data-Driven Recommendations

- BEST mutation type: **change_n_estimators** (0/5 hit rate)
- WORST mutation type: **change_n_estimators** (0/5 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21529)