# Karpathy POLITICAL — Mutation Effectiveness Analysis

> Auto-generated from 50 iterations on 2026-04-25 05:00 UTC
> Best Brier: 0.2023861347092226
> Current model: random_forest
> Current features: 75

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| remove_features | 4 | 0 | 0% | +0.03497 |
| change_model | 3 | 0 | 0% | +0.03417 |
| change_max_depth | 7 | 0 | 0% | +0.01954 |
| change_max_features_ratio | 7 | 0 | 0% | +0.03082 |
| change_n_estimators | 11 | 0 | 0% | +0.00404 |
| swap_features | 6 | 0 | 0% | +0.03293 |
| change_min_samples_leaf | 4 | 0 | 0% | +0.01664 |
| add_features | 8 | 0 | 0% | +0.02853 |

## Stagnation Analysis

- Total iterations: 50
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 50
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| extra_trees | 2 | 0.24033 | 0.24033 | 0.24033 |
| gradient_boosting | 1 | 0.22901 | 0.22901 | 0.22901 |
| random_forest | 47 | 0.20239 | 0.22428 | 0.25818 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 70-79 | 42 | 0.20239 | 0.22390 |
| 80-89 | 8 | 0.21696 | 0.23091 |

## Data-Driven Recommendations

- BEST mutation type: **remove_features** (0/4 hit rate)
- WORST mutation type: **remove_features** (0/4 hit rate) — avoid
- STUCK: 50 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **random_forest** (best Brier 0.20239)