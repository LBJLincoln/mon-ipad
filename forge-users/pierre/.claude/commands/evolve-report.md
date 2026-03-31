---
name: evolve-report
description: Generate a comprehensive evolution progress report across all 6 islands.
---

Generate a comprehensive evolution progress report across all 6 islands.

Arguments: $ARGUMENTS (optional: time period like "24h", "7d")

## Steps

1. **Fetch current state** from all 6 HF Spaces `/api/status` and `/api/results`

2. **Query Supabase** for historical evolution data:
   ```sql
   SELECT space_name, generation, brier_score, model_type, n_features,
          created_at, calibration_method
   FROM nba_experiments
   WHERE created_at > NOW() - INTERVAL '24 hours'
   ORDER BY brier_score ASC
   LIMIT 50
   ```

3. **Calculate metrics**:
   - Best Brier across all islands (current + historical)
   - Brier improvement rate (delta per hour)
   - Generation velocity (gens per hour per island)
   - Model type distribution (which models win most)
   - Feature count distribution
   - Cross-island diversity (are islands converging?)

4. **Identify trends**:
   - Which island is improving fastest?
   - Which model type dominates?
   - Are any islands exploring novel territory?
   - Is the overall best improving or plateaued?

5. **Output report**:
   ```
   ## Evolution Report — [period]

   **Overall Best**: Brier X.XXXXX (Island, model, N features)
   **Improvement**: +/- X.XXXXX over period
   **Velocity**: X.X gens/hour average

   ### Island Rankings
   | Rank | Island | Brier | Gen | Model | Improving? |

   ### Model Distribution
   - extra_trees: XX% of top-10 results
   - xgboost: XX%
   - random_forest: XX%

   ### Recommendations
   1. ...
   ```

## Constraints
- ZERO ML on VM
- Use pooler connection if Supabase primary is down (402)
- All data from APIs and Supabase only
