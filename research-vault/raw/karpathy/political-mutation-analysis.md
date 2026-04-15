# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-15 18:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| swap_features | 11 | 0 | 0% | +0.03394 |
| add_features | 7 | 0 | 0% | +0.01628 |
| change_model | 6 | 0 | 0% | +0.05377 |
| remove_features | 5 | 0 | 0% | +0.02729 |
| change_n_estimators | 10 | 0 | 0% | +0.00657 |
| change_min_samples_leaf | 2 | 0 | 0% | +0.00925 |
| change_max_depth | 6 | 0 | 0% | +0.01752 |
| change_max_features_ratio | 3 | 0 | 0% | +0.02100 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 2 | 0.24356 | 0.24356 | 0.24356 |
| gradient_boosting | 4 | 0.26569 | 0.26569 | 0.26569 |
| random_forest | 44 | 0.20454 | 0.22445 | 0.25103 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 5 | 0.21890 | 0.23183 |
| 80-89 | 45 | 0.20454 | 0.22815 |

## Data-Driven Recommendations

- BEST mutation type: **swap_features** (0/11 hit rate)
- WORST mutation type: **swap_features** (0/11 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)