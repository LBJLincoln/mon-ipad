---
name: Evolution Fleet Status — April 2026
description: HF Space island evolution monitoring — per-iteration fleet status, root causes, actions
type: project
---

# Evolution Fleet — Iteration Log

## ROOT CAUSE CONFIRMED (iter 6) + AMPLIFIED BY RESTARTS (iter 10)
**Issue:** `HARDCODED_STARTUP_MUTATION_DECAY + FREQUENT_RESTARTS`
- app.py starts mutation from hardcoded value and decays at 0.998^gen
- Mutation NOT persisted in checkpoint — every restart resets decay
- 5/6 islands restarted iter9→10, amplifying root cause severely
- API only accepts: mutation_rate, target_features, crossover_rate (model_type, diversity_reset, source_island silently ignored)
- **Fix required:** persist mutation_rate in checkpoint, floor 0.04→0.07, add model_type to /api/config
- **Escalated to:** D2 ENGINEERING (CRITICAL)

## Current Fleet State (iter 10, 2026-04-07 18:00 UTC)
| Island | Brier | Gen | Mut | Model | Status |
|--------|-------|-----|-----|-------|--------|
| S10 | 0.22390 | 176 | 0.0634 | random_forest | DECAY_CRITICAL, RESTARTED |
| S11 | 0.22926 | 125 | 0.1137 | catboost | REGRESSED +0.00683, RESTARTED |
| S12 | 0.22287 | 176 | 0.0901 | random_forest | IMPROVING -0.00145, RESTARTED |
| S13 | 0.22300 | 220 | 0.0868 | random_forest | RECOVERED -0.00565 |
| S14 | 0.24696 | 70  | 0.0697 | lightgbm | CATASTROPHE +0.02220, RESTARTED |
| S15 | 0.22158 | 124 | 0.1592 | extra_trees | FLEET BEST -0.00032, RESTARTED |

- Fleet avg: 0.22793 (regressed from 0.22440 due to S14)
- Spread: 0.02538 (CRITICAL > 0.01)
- ATR gap: 0.00638 | Target gap: 0.01158

## Iter 10 Interventions (all 200 OK, queued, 2026-04-07 18:00 UTC)
- S14 — Emergency: mut=0.15, target_features=65, cx=0.82 (catastrophe recovery)
- S10 — Mutation boost: mut=0.14, target_features=65, cx=0.82 (decay critical)
- S11 — Nudge: mut=0.13, target_features=70, cx=0.80 (regression fix)
- S13 — Gentle boost: mut=0.11, target_features=65 (sustain recovery momentum)

## Iter 9 Interventions (all 200 OK, queued, 2026-04-07 09:30 UTC)
- S10 — Mutation boost: mut=0.11, target_features=63, cx=0.82 (regression)
- S12 — Mutation boost: mut=0.12, target_features=65, cx=0.82 (fleet best regression)
- S13 — Emergency diversity reset: mut=0.13, target_features=72, cx=0.80 (fleet worst)
- S15 — Emergency extra_trees reset from iter8 — now fleet best 0.22158

## Key Insight: S15 Winning Formula
extra_trees + pop=50 + feats=75 + mut=0.1592 = fleet best 0.22158
Propagating this formula is the #1 priority (blocked by API not accepting model_type)

## Kaggle Karpathy Context
- Kaggle best_brier: 0.1968 (iteration 11, gradient_boosting, 80 feats) — GPU advantage
- Kaggle vs HF fleet gap: 0.0248 Brier — TabICL/GPU essential for <0.20

## Priority Actions
0. D2: Fix mutation persistence in app.py checkpoint (10 iters confirmed)
1. D2: Add model_type to /api/config endpoint
2. D7: Audit keepalive-spaces.sh for restart triggers
3. Iter11: Verify S14 recovery (if > 0.235, escalate)
4. Seed next Kaggle session with S15 extra_trees config
