---
name: Evolution Fleet Status — April 2026
description: HF Space fleet health. Apr 5: S14 worst at 0.22666 (xgboost drift), S12 at 0.22506 (catboost drift), S15 fleet leader 0.22159. Cross-pollination and mutation boosts applied to 3 islands.
type: project
---

**Last verified: 2026-04-05 00:00 UTC**

## Current Fleet State (2026-04-05 post-intervention)

| Space | Gen | Best Brier | Best Model | Mut Rate | Action Taken (Apr 5) |
|-------|-----|-----------|------------|----------|----------------------|
| S10 nba-quant | 787 | 0.22454 | xgboost_brier | 0.05 | boost_mutation queued: mut=0.10 |
| S11 nba-quant-2 | — | — | — | — | no action this session |
| S12 nba-evo-3 | 1473 | 0.22506 | catboost (DRIFT: should be extra_trees) | 0.04 | boost_mutation+model queued: mut=0.12, ET, feat=65 |
| S13 nba-evo-4 | — | — | — | — | no action this session |
| S14 nba-evo-5 | 1200 | 0.22666 (WORST) | xgboost_brier (DRIFT: should be lightgbm) | 0.04 | cross_pollinate from S15 queued: mut=0.12, lightgbm, feat=75, pop=50 |
| S15 nba-evo-6 | 2103 | 0.22159 (BEST) | random_forest | 0.08 | source for S14 cross-pollination, no change |

## Apr 5 Interventions (all 200 OK, status: queued)

### S14 — cross_pollinate from S15
- Command: `cross_pollinate`
- Source: S15 (fleet leader, 0.22159, random_forest 79f)
- Params: mutation_rate=0.12, model_type=lightgbm, feature_count=75, population_size=50
- Rationale: S14 worst in fleet at 0.22666. Mutation frozen at 0.04. Full model drift to xgboost. Cross-pollination injects S15 diversity and restores lightgbm specialist mandate.

### S12 — boost_mutation + model restore
- Command: `boost_mutation`
- Params: mutation_rate=0.12, model_type=extra_trees, feature_count=65
- Rationale: S12 catboost takeover with mutation frozen at 0.04. extra_trees at 65 features is the proven CPU-fast specialist (Sharpe 8.39 in 1244 experiments). Boost breaks monoculture.

### S10 — boost_mutation
- Command: `boost_mutation`
- Params: mutation_rate=0.10
- Rationale: S10 plateau at gen 787. Mutation at 0.05 too conservative for escape. 0.10 is exploitation sweet spot.

## Critical Pattern: Mutation Freeze + Model Drift

S12 and S14 both show mutation_rate=0.04 (adaptive decay has bottomed out) AND model drift to wrong families. This is the recurrent failure mode: once the GA finds a local optimum, adaptive mutation decays below 0.05 and the island becomes permanently locked. External boost commands are the only remedy without a code-level fix.

**Why:**  Adaptive mutation decay is designed to exploit once a good region is found, but if the "good region" is actually a catboost/xgboost local trap, the island never escapes.
**How to apply:** Any island showing mutation_rate <= 0.05 AND no Brier improvement for 50+ gens should receive a boost_mutation command immediately.

## Apr 3 Session Context (prior interventions)

| Island | Command | Status Brier at time | Gen |
|--------|---------|---------------------|-----|
| S10 | boost_mutation + config mut=0.12 feat=63 | 0.22563 | 108 |
| S13 | diversify | 0.22455 | 153 |
| S14 | diversify + config mut=0.15 feat=63 | 0.22666 | 174 |
| S15 | diversify + config mut=0.15 feat=63 | 0.22159 | 164 |
| S11 | 3 experiments: ET-63, LightGBM-55, ET-63 (pri=9) | 0.22799 | 207 |

## Critical Findings (still unresolved)

### 1. CatBoost is 3-5x slower than LightGBM on CPU
- S12 (lightgbm): ~46s/gen
- S10 (catboost): ~242s/gen
- Fleet throughput: 219 gen/hr vs target 380 gen/hr

### 2. NSGA-II composite does not protect Brier gains
The best individual (S15 gen-1 random_forest 0.22159) was preserved in memory but could not be reproduced into the population. The GA has no elitism protecting top Brier individuals from replacement.

### 3. Feat=200 catboost trap
catboost at 200 features dominates training set Brier but cannot generalize. NSGA-II never punishes this because there is no feature-count penalty in the composite fitness.

## Code Fixes Required (priority order, none deployed yet)

1. **Elitism**: top-2 by Brier + top-2 by composite ALWAYS copied unchanged to next generation
2. **CatBoost CPU cap**: if not gpu → n_estimators = min(n_estimators, 60), early_stopping_rounds=15
3. **Brier weight**: increase to 40% in composite (from ~20-25%)
4. **Walk-forward n_splits=3** during evolution (not 5+)
5. **Feature penalty**: -0.001 * max(0, n_features - 80) for CPU islands

## Fleet Speed Summary
- Current: ~219 gen/hr total
- Target (after code fixes): 320-380 gen/hr
- S15 reference at 2103 gens is the longest-running island — fleet leader by historical persistence

## ATR Context
- CPU fleet ceiling: ~0.224-0.225 (diminishing returns without code fixes)
- ATR (Colab TabICL): 0.21570
- Target: < 0.20
- GPU sessions (Kaggle/Colab) seeded from fleet best remain the primary path to target
