# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-17 02:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| swap_features | 6 | 0 | 0% | +0.02839 |
| remove_features | 8 | 0 | 0% | +0.02647 |
| change_max_features_ratio | 7 | 0 | 0% | +0.02536 |
| add_features | 8 | 0 | 0% | +0.02156 |
| change_min_samples_leaf | 10 | 0 | 0% | +0.00625 |
| change_max_depth | 4 | 0 | 0% | +0.01121 |
| change_n_estimators | 1 | 0 | 0% | +0.00000 |
| change_model | 6 | 0 | 0% | +0.05083 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| gradient_boosting | 3 | 0.26569 | 0.26569 | 0.26569 |
| lightgbm | 3 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 44 | 0.20454 | 0.22362 | 0.25185 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 8 | 0.21589 | 0.23101 |
| 80-89 | 42 | 0.20454 | 0.22675 |

## Data-Driven Recommendations

- BEST mutation type: **swap_features** (0/6 hit rate)
- WORST mutation type: **swap_features** (0/6 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)