# Karpathy NBA — Mutation Effectiveness Analysis

> Auto-generated from 10 iterations on 2026-04-13 12:23 UTC
> Best Brier: 1.0
> Current model: extra_trees
> Current features: 0

## Mutation Type Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| remove_features | 1 | 0 | 0% | +0.06790 |
| change_n_estimators | 3 | 0 | 0% | +0.05797 |
| swap_features | 2 | 0 | 0% | +0.06317 |
| add_features | 1 | 0 | 0% | +0.05884 |
| change_max_depth | 2 | 0 | 0% | +0.06524 |
| change_model | 1 | 0 | 0% | +0.03818 |

## Stagnation Analysis

- Total iterations: 10
- Total improvements: 0
- Improvement rate: 0.0%
- Current no-improve streak: 10
- Stuck in local minimum: YES

## Model Type Comparison

| Model | Tries | Best Brier | Avg Brier | Worst Brier |
|-------|-------|------------|-----------|-------------|
| gradient_boosting | 9 | 0.23774 | 0.25291 | 0.26515 |
| lightgbm | 1 | 0.22915 | 0.22915 | 0.22915 |

## Feature Count vs Brier

| Feature Range | Tries | Best Brier | Avg Brier |
|---------------|-------|------------|-----------|
| 80-89 | 9 | 0.22915 | 0.25062 |
| 90-99 | 1 | 0.24981 | 0.24981 |

## Data-Driven Recommendations

- BEST mutation type: **remove_features** (0/1 hit rate)
- WORST mutation type: **remove_features** (0/1 hit rate) — avoid
- STUCK: 10 iterations without improvement
- ACTION: Try a diversity move (change_model or large swap_features)
- Best model type: **lightgbm** (best Brier 0.22915)