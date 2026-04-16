# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-16 18:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| add_features | 8 | 0 | 0% | +0.01650 |
| change_min_samples_leaf | 4 | 0 | 0% | +0.01677 |
| swap_features | 7 | 0 | 0% | +0.02703 |
| remove_features | 6 | 0 | 0% | +0.02538 |
| change_model | 5 | 0 | 0% | +0.03962 |
| change_max_features_ratio | 7 | 0 | 0% | +0.02265 |
| change_max_depth | 6 | 0 | 0% | +0.01859 |
| change_n_estimators | 7 | 0 | 0% | +0.01167 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 3 | 0.24356 | 0.24356 | 0.24356 |
| lightgbm | 2 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 45 | 0.21130 | 0.22437 | 0.25731 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 6 | 0.21951 | 0.22992 |
| 80-89 | 44 | 0.21130 | 0.22586 |

## Data-Driven Recommendations

- BEST mutation type: **add_features** (0/8 hit rate)
- WORST mutation type: **add_features** (0/8 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.21130)