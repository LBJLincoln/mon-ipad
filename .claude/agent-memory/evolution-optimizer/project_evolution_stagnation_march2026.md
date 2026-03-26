---
name: Evolution Fleet Stagnation — March 2026
description: All 6 HF Space islands health snapshot. Feat=200 takeover persistent, S14 is new fleet best at 0.21837, S10 regressed to worst, Supabase dead on 4/6 islands.
type: project
---

**Last verified: 2026-03-26**

## Current Fleet State

| Space | Gen | Brier | Mut | Model | Stagnation |
|-------|-----|-------|-----|-------|------------|
| S10 | 149 | 0.2246 | 0.0668 | random_forest | MEDIUM — worst fleet |
| S11 | 183 | 0.22205 | 0.1025 | catboost | LOW — mutation healthy |
| S12 | 29 | 0.22116 | 0.0755 | extra_trees | LOW — fresh restart |
| S13 | 33 | 0.22367 | 0.119 | lightgbm | LOW — fresh restart |
| S14 | 487 | 0.22093 | 0.04 | extra_trees | CRITICAL — mut=0.04 |
| S15 | 840 | 0.22625 | 0.08 | extra_trees | HIGH — never improved |

## Fleet Best
- **Current**: S14, Brier=0.22093, gen 487
- **All-time**: S14, Brier=0.21837 (Supabase logged OK earlier)
- **Target**: 0.20 — gap = 0.02093

## Critical Issues (2026-03-26)

1. **S14 mutation at 0.04** — population is frozen. Need POST /api/config mutation_rate=0.12 to escape local optimum.
2. **Feat=200 takeover universal** — S12/S14/S15 all show 20/20 recent gens at Feat=200. Best individuals have 60-80 features but Feat=200 wins every tournament. Root cause: feature penalty too weak in NSGA-II selection.
3. **Supabase dead on S10/S11/S12/S13** — pooler returns "Tenant or user not found". S14 was logging OK. Cannot track cross-restart progress for most islands.
4. **S10 regressed badly** — was 0.22041 (MOVDA-era best), now 0.2246 (worst in fleet). random_forest winning over extra_trees, suggesting seeding or model config broken.
5. **S15 never improved** — gen 840, all-time best 0.22209 = current best. Sharpe=23.93 anomalous vs Brier plateau — ROI metric being gamed.

## Role Mismatches (persistent)
- S10: exploitation → random_forest (expected extra_trees)
- S13: catboost specialist → lightgbm
- S14: lightgbm specialist → extra_trees
- S15: wide search → extra_trees (extra_trees dominates everywhere)

## Stagnation Counter Blind Spot
Stagnation counters read 0 for all islands — they reset per-cycle, so multi-cycle plateaus are invisible. S14 flat at 0.22070 for 10+ gens despite counter showing 0.

**Why:** Adaptive mutation in genetic_loop_v3.py decays when no improvement detected within a cycle. At 0.04 floor, crossover produces near-identical offspring. Feature penalty in NSGA-II selection is too weak to resist Feat=200 bloat.

**How to apply:** When mutation_rate < 0.08 on any island and Brier same for >5 gens in history, push config reset mutation_rate=0.12. Feat=200 takeover requires a code fix to the selection/tournament logic — a config push alone won't fix it.
