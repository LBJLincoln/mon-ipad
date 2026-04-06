---
name: Evolution Fleet Status — April 2026
description: HF Space fleet health. Apr 6 iter4: S13 MAJOR RECOVERY 0.22283 (-0.02312). S15 fleet best 0.2222. S14 mutation freeze risk (0.0625). 3 POSTs queued.
type: project
---

**Last verified: 2026-04-06 10:15 UTC (iteration 4)**

## Current Fleet State (iter 4, 2026-04-06 10:15 UTC)

| Space | Gen | Best Brier | Best Model | Mut Rate | Delta vs Iter3 | Action Taken (iter4) |
|-------|-----|-----------|------------|----------|----------------|----------------------|
| S10 nba-quant | 117 | 0.23149 | random_forest | 0.1006 | +0.00287 REGRESSED | boost_mutation to 0.11, target_features=63, cx=0.80 |
| S11 nba-quant-2 | 115 | 0.22372 | catboost | 0.1076 | -0.00324 IMPROVED | none (exploration role, healthy) |
| S12 nba-evo-3 | 199 | 0.22533 | lightgbm (DRIFT: should be extra_trees) | 0.0844 | +0.00257 REGRESSED | nudge mut=0.10, feat=63, cx=0.80 |
| S13 nba-evo-4 | 93 | 0.22283 | random_forest (drifted from catboost) | 0.1012 | -0.02312 MAJOR RECOVERY | none — let recovery consolidate |
| S14 nba-evo-5 | 124 | 0.22622 | random_forest (DRIFT: should be lightgbm) | 0.0625 | +0.00128 MARGINAL REGRESSION | none — watching; FREEZE RISK |
| S15 nba-evo-6 | 68 | **0.2222 (FLEET BEST)** | random_forest | 0.1158 | +0.00122 MARGINAL | nudge mut=0.13, feat=64, cx=0.80 |

## Iter 4 Interventions (all 200 OK, status: queued)

### S10 — regression escape boost
- Params: mutation_rate=0.11, target_features=63, crossover_rate=0.80
- Rationale: Regressed +0.00287. best_features=46 consistently below sweet spot. Gap to fleet best 0.00929.

### S12 — mutation nudge + feature boost
- Params: mutation_rate=0.10, target_features=63, crossover_rate=0.80
- Rationale: Gen 199 convergence risk. Mutation 0.0844 approaching freeze. Model drift to lightgbm.

### S15 — fleet best maintenance
- Params: mutation_rate=0.13, target_features=64, crossover_rate=0.80
- Rationale: Mild regression. Feat=200 takeover risk in current gen. Maintain wide-search character.

## Validated Emergency Protocol (from S13 recovery)

**For any island with brier_delta > +0.015 (CRITICAL collapse):**
- Params: mutation_rate=0.13, target_features=63, crossover_rate=0.80
- Result: S13 recovered -0.02312 in one iteration cycle — the largest single-cycle recovery in fleet history.
- This is now the canonical emergency boost protocol.

## S14 Mutation Freeze Warning

S14 mutation at 0.0625 is critically low (threshold: 0.07 = warning, 0.05 = emergency).
If iter5 shows any regression: POST {mutation_rate: 0.10, target_features: 58, crossover_rate: 0.80} immediately.

## API Discovery (iter 3, confirmed iter 4)

The /api/config endpoint does NOT accept string commands.
Valid params: mutation_rate, elite_size, migrants_per_island, pop_size, n_islands, migration_interval, cooldown, tournament_size, target_features, crossover_rate
Model type can only be influenced indirectly through GA selection + feature targets.

## Iter 3 Interventions (outcome verified in iter4)

### S13 — EMERGENCY boost (iter3 sent) → CONFIRMED EFFECTIVE in iter4
- Params sent: mutation_rate=0.13, target_features=63, crossover_rate=0.80
- Result: 0.24595 → 0.22283 (-0.02312) — complete recovery

### S12 — mutation nudge (iter3 sent)
- Result: Actually regressed slightly 0.22276 → 0.22533 (+0.00257) — partial effect, re-boosted in iter4

### S10 — regression escape boost (iter3 sent)
- Result: Further regressed 0.22862 → 0.23149 — config may not have taken effect or generation reset

## Critical Pattern: Model Drift Across All Islands

All 6 islands now show model drift to random_forest as the "safe" model.
- S10: random_forest (expected: lightgbm/extra_trees)
- S11: catboost (expected: exploration multi-model — acceptable)
- S12: lightgbm (expected: extra_trees)
- S13: random_forest (expected: catboost — but recovery happened despite drift)
- S14: random_forest (expected: lightgbm)
- S15: random_forest (expected: extra_trees/wide search)

**Why:** Random_forest dominates early CPU selection due to fast convergence but has lower ceiling than extra_trees or lightgbm. GA selects it by fitness but it's not the ATR-optimal model family.

**How to apply:** Feature target nudges steer the GA but cannot force model selection. Code-level elitism fix would help. Specialist mandates are advisory only.

## Fleet Best Config History

| Iteration | Best Island | Best Brier | Model | Features | Mut |
|-----------|-------------|-----------|-------|----------|-----|
| iter1 | S15 | 0.22159 | extra_trees | ~60 | 0.18 |
| iter2 | S15 | 0.22159 | extra_trees | 60 | 0.18 |
| iter3 | S15 | 0.22098 | extra_trees | 64 | 0.1647 |
| iter4 | S15 | 0.2222 | random_forest | 61 | 0.1158 |

## GPU Seed Configs (for Kaggle Karpathy)

1. S15 fleet best: extra_trees, 64 features, mut=0.1647, Brier=0.22098 (iter3 peak)
2. S13 recovery: random_forest, 52 features, mut=0.10, Brier=0.22283, Sharpe=10.12

## Code Fixes Required (priority order, none deployed yet)

1. **Elitism**: top-2 by Brier + top-2 by composite ALWAYS copied unchanged to next gen (est -0.002-0.004 Brier)
2. **CatBoost CPU cap**: if not gpu → n_estimators = min(n_estimators, 60), early_stopping_rounds=15
3. **Brier weight**: increase to 40% in composite (from ~20-25%)
4. **Walk-forward n_splits=3** during evolution (not 5+)
5. **Feature penalty**: -0.001 * max(0, n_features - 80) for CPU islands

## ATR Context

- CPU fleet ceiling: ~0.221-0.222 (S15 approaching this, S13 now near it)
- ATR (Colab TabICL): 0.21570
- Target: < 0.20
- Gap to ATR: 0.00650 (S15 best vs ATR)
- Gap to target: 0.02220
- GPU sessions remain primary path to target < 0.20
