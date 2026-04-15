# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-15 02:23 UTC
> Best Brier: 0.20454312075559716
> Current model: random_forest
> Current features: 80

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| add_features | 7 | 0 | 0% | +0.01584 |
| change_max_depth | 8 | 0 | 0% | +0.01483 |
| change_min_samples_leaf | 7 | 0 | 0% | +0.01222 |
| swap_features | 6 | 0 | 0% | +0.02205 |
| change_max_features_ratio | 7 | 0 | 0% | +0.02702 |
| change_n_estimators | 6 | 0 | 0% | +0.00484 |
| remove_features | 6 | 0 | 0% | +0.02507 |
| change_model | 3 | 0 | 0% | +0.03952 |

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
| lightgbm | 1 | 0.24506 | 0.24506 | 0.24506 |
| random_forest | 47 | 0.20454 | 0.22190 | 0.23768 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 6 | 0.22427 | 0.22961 |
| 80-89 | 44 | 0.20454 | 0.22236 |

## Data-Driven Recommendations

- BEST mutation type: **add_features** (0/7 hit rate)
- WORST mutation type: **add_features** (0/7 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20454)