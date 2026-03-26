---
name: Evolution Fleet Stagnation — March 2026
description: All 6 HF Space islands health snapshot. Feat=200 universal takeover confirmed (5/6 at 100%), S14 is fleet best at 0.22093, S13 only active improver, 3 experiments submitted to S11.
type: project
---

**Last verified: 2026-03-26 17:05 UTC**

## Current Fleet State

| Space | Gen | Cycle | Brier (best) | Gen-Pop Brier | Mut | Model | Feat=200% | Supabase | Risk |
|-------|-----|-------|--------------|----------------|-----|-------|-----------|----------|------|
| S10 | 1970 | 657 | 0.22278 | 0.2214 (frozen) | 0.05→0.09* | extra_trees | 100% | OK | MEDIUM |
| S11 | 898 | 299 | 0.22365 | 0.2245 (frozen) | 0.08 | lightgbm | 100% | DEAD | HIGH |
| S12 | 56 | 19 | 0.22116 | 0.2206 | 0.0715 | extra_trees | 98% | DEAD | MEDIUM |
| S13 | 61 | 21 | 0.22367 | 0.2221 (improving) | 0.1126 | lightgbm | 72% | UNKNOWN | LOW |
| S14 | 589 | 197 | 0.22093 | 0.2252 (regressed) | 0.1024 | extra_trees | 100% | OK | HIGH |
| S15 | 1017 | 339 | 0.22625 | 0.2221 (frozen) | 0.08 | extra_trees | 100% | OK | RESTART |

*Config push applied 2026-03-26

## Fleet Best
- **Current**: S14, Brier=0.22093, gen 589, extra_trees, 67 features
- **All-time best**: 0.21976 (experiment #734, extra_trees, 142 features)
- **Target**: 0.20 — gap = 0.02093

## Actions Taken 2026-03-26

### Config pushes
- **S10**: POST /api/config → mutation_rate=0.09, target_features=63, crossover_rate=0.80 (was decayed to 0.05)

### Experiments submitted to S11 (/api/experiment/submit)
- **#2533** evo-agent-et63-001 (priority 9): extra_trees + target_features=63 + mutation=0.09
- **#2534** evo-agent-mut-rescue-002 (priority 8): mutation_rate=0.12 rescue config
- **#2535** evo-agent-xgb-sigmoid-003 (priority 7): xgboost+sigmoid + target_features=63 (MOVDA-era best config)

## Critical Issues (2026-03-26)

1. **Feat=200 universal takeover** — 5 of 6 islands at 100% Feat=200 in ALL logged gen lines. Best individuals are 54-98 features. The GA is not searching — it is iterating dead 200-feature genomes. Root cause: NSGA-II tournament selection rewards ROI/Sharpe overfitting of bloated genomes. REQUIRES CODE FIX to genetic_loop_v3.py selection penalty.

2. **S14 regression** — Fleet best (0.22093) but gen population at 0.2252 — gap of 0.0043. Feat=200 displacement likely eliminated the 67-feature champion from the population. Needs elite injection or checkpoint rollback.

3. **Supabase dead on S11/S12/S13** — Error: "FATAL: Tenant or user not found — aws-1-eu-west-1.pooler.supabase.com port 6543". Wrong DATABASE_URL pooler credentials on those 3 spaces. S10/S14/S15 use working credentials. Fix: update DATABASE_URL env var in HF Space settings.

4. **S15 — restart recommended** — 1017 generations, worst fleet Brier (0.22625), Sharpe=23.93 anomalous (ROI metric being gamed). Restart with lightgbm specialist config seeded from S13's best individual.

5. **Migration spreading Feat=200** — Current automatic migration (3 individuals every ~30 gens) is net-negative: Feat=200 immigrants win tournament selection in receiving islands. Need feature-count filter on migration candidates (<= 120 features only).

## S13 — The Most Promising Island
S13 (gen 61) is the ONLY island showing active Brier improvement in its log:
- Gen log trend: 0.2233 → 0.2233 → 0.2221 → 0.2221 (actively dropping)
- Feat=200 at 72% (not yet total takeover)
- Mutation healthy at 0.1126
- **Do not intervene until gen 150 or Feat=200 hits 95%+**

## Structural Fix Required
The only path to breaking 0.22 on CPU islands is:
1. Fix genetic_loop_v3.py: add Pareto crowding penalty for n_features > 150 (weight 0.15)
2. Fix Supabase credentials on S11/S12/S13
3. Restart S15 as lightgbm specialist seeded from S13
4. Use Colab GPU notebook (TabICLv2 + TabPFN) for final push below 0.22

**Why:** Feat=200 bloat consumes 100% of compute on genomes that score well in training but generalize poorly. The selection mechanism must be fixed at the code level. Config-only rescues (mutation boosts) provide temporary relief but Feat=200 re-establishes dominance within 20-30 gens.

**How to apply:** When reviewing island health, check Feat=200% first. If >80% on any island, push mutation_rate=0.12 AND target_features to island's intended sweet spot as an emergency measure. Code fix takes priority over config fixes.

## API Reference (correct endpoints)
- Status: `GET /api/status`
- Config push: `POST /api/config` (allowed: pop_size, mutation_rate, target_features, crossover_rate, cooldown, elite_size, tournament_size, n_islands, migration_interval, migrants_per_island)
- Experiment submit: `POST /api/experiment/submit` (NOT /api/submit-experiment)
- Population reset: `POST /api/reset`
- Command: `POST /api/command` (commands: diversify, boost_mutation, backfill_boxscores)
