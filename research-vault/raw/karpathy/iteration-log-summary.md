# Karpathy Iteration Log Summary

> 50 sessions logged as of 2026-04-14 08:23 UTC

## Session Outcomes

| Timestamp | Domain | Mutation | Decision | Brier After |
|-----------|--------|----------|----------|-------------|
| 2026-04-12T18:41:03 | nba | max_depth: 10 -> 11 | REVERT | 0.19097 |
| 2026-04-12T18:41:11 | nba | max_features_ratio: 0.4 -> 0.3 | REVERT | 0.20795 |
| 2026-04-12T18:41:12 | nba | model: gradient_boosting -> li | REVERT | 0.21074 |
| 2026-04-12T18:41:19 | nba | n_estimators: 125 -> 100 | REVERT | 0.19396 |
| 2026-04-12T18:41:28 | nba | remove 5 features (now 80) | REVERT | 0.22305 |
| 2026-04-12T18:41:32 | nba | n_estimators: 125 -> 50 | REVERT | 0.19284 |
| 2026-04-12T18:41:49 | nba | n_estimators: 125 -> 225 | REVERT | 0.20089 |
| 2026-04-12T18:41:57 | nba | max_features_ratio: 0.4 -> 0.3 | REVERT | 0.22606 |
| 2026-04-12T18:42:06 | nba | max_features_ratio: 0.4 -> 0.3 | REVERT | 0.22606 |
| 2026-04-12T18:42:16 | nba | min_samples_leaf: 7 -> 9 | REVERT | 0.21715 |
| 2026-04-12T18:42:24 | nba | max_depth: 10 -> 7 | REVERT | 0.21248 |
| 2026-04-12T18:42:33 | nba | min_samples_leaf: 7 -> 4 | REVERT | 0.22107 |
| 2026-04-12T18:42:43 | nba | add 5 features (now 90) | REVERT | 0.22098 |
| 2026-04-12T18:42:54 | nba | max_features_ratio: 0.4 -> 0.5 | REVERT | 0.22031 |
| 2026-04-12T18:43:04 | nba | max_depth: 10 -> 9 | REVERT | 0.19097 |
| 2026-04-12T18:43:13 | nba | max_depth: 10 -> 12 | REVERT | 0.19097 |
| 2026-04-12T18:43:22 | nba | max_depth: 10 -> 9 | REVERT | 0.19097 |
| 2026-04-12T18:43:31 | nba | remove 5 features (now 80) | REVERT | 0.22079 |
| 2026-04-12T18:43:40 | nba | min_samples_leaf: 7 -> 5 | REVERT | 0.23138 |
| 2026-04-12T18:43:49 | nba | max_features_ratio: 0.4 -> 0.3 | REVERT | 0.22606 |

## Aggregate
- Sessions: 50
- KEEP: 0 (0%)
- REVERT: 50 (100%)