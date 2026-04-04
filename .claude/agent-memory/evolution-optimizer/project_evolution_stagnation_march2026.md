---
name: Evolution Fleet Status — April 2026
description: HF Space fleet health. Apr 3: 6/6 UP but 3 islands catboost-locked, S15 true Brier stuck at 0.2456, fleet throughput 219 gen/hr vs target 380 gen/hr.
type: project
---

**Last verified: 2026-04-03 15:00 UTC**

## Current Fleet State (2026-04-03 post-diagnose)

| Space | Gen | Status Brier | Real Pop Brier | Model | Gen/hr | Action Taken |
|-------|-----|-------------|----------------|-------|--------|--------------|
| S10 nba-quant | 108 | 0.22563 | 0.2351 | catboost-locked | 14.9 | boost_mutation + config mut=0.12 feat=63 |
| S11 nba-quant-2 | 207 | 0.22799 | 0.2297 | extra_trees | 41.5 | 3 experiments submitted |
| S12 nba-evo-3 | 196 | 0.22506 | 0.2292 | lightgbm (FAST) | 78.9 | none — optimal, leave alone |
| S13 nba-evo-4 | 153 | 0.22455 | 0.2317 | catboost | 31.1 | diversify command sent |
| S14 nba-evo-5 | 174 | 0.22666 | 0.235 | xgboost | 24.7 | diversify + config mut=0.15 feat=63 |
| S15 nba-evo-6 | 164 | 0.22159 | 0.2456 | catboost-locked | 27.8 | diversify + config mut=0.15 feat=63 |

**True fleet best**: S13 at 0.22455 (real evolving population progress)
**S15 warning**: "best_brier=0.22159" is a gen-1 random_forest seed that was never reproduced. Real population stuck at 0.2456 for 159 consecutive generations.

## Critical Findings (Apr 3 diagnosis)

### Finding 1: S15 true Brier is 0.2456, NOT 0.22159
The status API returns `best_brier` = best individual ever seen, preserved in memory. S15 gen-1 random_forest 79-feat scored 0.22159. But the GA could not reproduce this and the entire evolving population converged to catboost-200-feat at 0.24564. **The fleet best metric is completely misleading.**

### Finding 2: CatBoost is 3-5x slower than LightGBM on CPU
- S12 (lightgbm dominant): 46s/gen = **78.9 gen/hr**
- S10 (catboost dominant): 242s/gen = **14.9 gen/hr**
- 5.3x difference. CatBoost not designed for CPU.

### Finding 3: NSGA-II composite not pushing Brier
S15 history shows composite=0.73618 (random_forest Brier=0.2216) was higher than composite=0.66249 (catboost Brier=0.2456) — yet catboost took over. Root cause: elitism is insufficient. Top individual not protected from replacement. Once gen-0 seed's slot was overwritten, GA lost the good configuration permanently.

### Finding 4: Feat=200 catboost trap
S15 top5 Pareto: 4/5 individuals at n_features=200. Only 1 (gen-0 seed) at 60 features. Feat=200 catboost wins raw Brier on training set but cannot generalize. The selection pressure never punishes overfitting.

## Code Fixes Required (in priority order)

1. **Elitism fix** (highest impact): top-2 by Brier + top-2 by composite ALWAYS survive to next gen
2. **CatBoost CPU cap**: if not gpu → n_estimators=min(n_estimators, 60), early_stopping=15 rounds
3. **Brier weight**: increase to 40% in composite formula (from ~20-25%)
4. **Walk-forward n_splits=3** during evolution (not 5+), full CV only for top-5 per cycle
5. **Feature penalty**: -0.001 * max(0, n_features - 80) in composite for CPU islands

## Speed Summary
- Current fleet: **219 gen/hr total**
- After code fixes: **320-380 gen/hr** (1.5-1.7x)
- S12 (lightgbm) is the reference: 78.9 gen/hr on identical hardware

## Commands Already Sent (Apr 3 15:00 UTC)
- S10: boost_mutation, config push mut=0.12 feat=63
- S13: diversify
- S14: diversify, config push mut=0.15 feat=63
- S15: diversify, config push mut=0.15 feat=63
- S11: 3 experiments (ET-63, LightGBM-55, ET-63 high priority)

## Historical Notes (pre-Apr-3)

### 2026-03-28 post-redeploy
All 6 islands redeployed fresh. S14 was stuck BUILDING for >2h. Watchdog data server bug fixed (pgrep pattern mismatch causing 12 false restarts/hr).

### 2026-03-26 pre-redeploy
- S10/S11: 100% Feat=200 takeover. All 5 of 6 islands had Feat=200 in >95% of population.
- Fix attempted: S10 config push mut=0.09 feat=63 cx=0.80.
- S11 experiments #2533-2535 submitted.
- Root cause identified: NSGA-II tournament selection rewards ROI/Sharpe overfitting without feature penalty.

## Why tracking this
The fleet Brier improvements are not coming from CPU evolution alone — CPU islands appear to be plateauing at ~0.225. True Brier gains require:
1. Code-level elitism + Brier weighting fix
2. GPU sessions (Kaggle/Colab) seeded from S13's best individuals
3. The next evolutionary step likely requires the TabICL approach (Brier 0.21570 ATR) which needs GPU.
