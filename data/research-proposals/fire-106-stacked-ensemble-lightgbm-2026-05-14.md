# fire-106 Research Proposal: Stacked Ensemble Feature Insights + LightGBM Cross-Domain Port

**Date:** 2026-05-14  
**Fire:** fire-106 (EVEN cycle)  
**Proposer:** Cloud Brain Sonnet 4.6  
**Priority:** HIGH — CPU-actionable experiments identified

## Motivation

1. Scientific Reports 2025 stacked ensemble paper (s41598-025-13657-1) identifies top NBA features worth verifying in our engine
2. POL P4+P7+P2 all showing LightGBM at 108-117f as consistent 0.249 signal across 5+ independent cycles
3. NBA S22 (fleet laggard, 0.22551) has never been exposed to LightGBM — direct cross-domain port opportunity

## SOTA Sources

### 1. Stacked Ensemble (Sci Reports 2025) — s41598-025-13657-1
- Architecture: RF + XGBoost + LightGBM base learners → logistic regression meta-learner
- Best accuracy: ~74-75% on 2015-2023 NBA test data
- **Note:** Meta-learner stacking banned in our islands (Rule#8). Feature analysis is freely applicable.
- **Top features identified:**
  1. Rolling win rate last 5 games (home/away split)
  2. Rolling point differential last 5 games
  3. ELO rating (current team, 5-game window)
  4. Head-to-head last 10 meetings win rate
  5. Rest days differential (home - away)
  6. Back-to-back game flag (binary)
  7. Home court indicator
- **Engine audit needed:** features/engine.py v3.1 covers ELO + B2B + home. Verify H2H window >= 10 meetings and rest_days_differential is a computed diff feature (not just separate home/away rest).

### 2. Uncertainty-Aware ML (MDPI Information, Montrucchio et al., 2026) — 3rd cycle reconfirmation
- LR Brier = 0.199 (best tabular), XGBoost = 0.202
- Brier decomposition: reliability + resolution + uncertainty as calibration monitoring framework
- **Actionable:** `vm-add-logistic-regression-model-pool` (work-queue P50) remains highest-priority new model addition

## Cross-Domain LightGBM Signal (fire-106 — NEW)

This cycle provides the strongest cross-domain evidence for LightGBM:

| Island | Domain | Model | Features | Brier | Status |
|--------|--------|-------|----------|-------|--------|
| P2 | POL | LightGBM | 117f | 0.24901 | 5+ fires field-lag |
| P4 | POL | LightGBM | 108f | 0.24900 | SAVING potential best |
| P7 | POL | LightGBM | — | 0.24904 | 4+ fires field-lag |

All 3 islands at or near 0.249 threshold are running LightGBM. P1 (XGBoost, 0.2499) and P5 (extra_trees, 0.24993) are slightly behind despite comparable feature counts. This is a reproducible domain-wide LightGBM advantage.

### Why this matters for NBA:
- NBA S22 (TESTforge42) is the fleet laggard at 0.22551 with CatBoost dominant
- S22 has never been exposed to LightGBM in its MODEL_TYPES
- NBA MAX_FEATURES=200 allows 108-150f exploration
- S22's repeated hard resets (cycles 640+665) suggest current model pool has converged locally
- S13 (fresh restart, cycle=103) is already running LightGBM this cycle — verify it's in MODEL_TYPES config

## Proposed Experiments

### Experiment 1 — S22 LightGBM Addition (VM, HIGH PRIORITY)
```json
POST https://testforge42-nba-evo-s22.hf.space/api/config
{"MODEL_TYPES": ["random_forest", "extra_trees", "catboost", "lightgbm"], "MAX_FEATURES": 200}
```
Expected: S22 0.22551 → 0.221-0.222 range if POL LightGBM advantage transfers. Full eval ~40-80h on CPU.

### Experiment 2 — S13 LightGBM Config Verification (VM, MEDIUM PRIORITY)
S13 is running LightGBM this cycle (confirmed from /api/status). Verify it's in the MODEL_TYPES *config* (not just current pop selection). If only in pop by mutation, it may reset out on next hard reset.
```bash
curl https://nomos42-nba-evo-4.hf.space/api/config | jq '.MODEL_TYPES'
```

### Experiment 3 — H2H Feature Depth Audit (Cloud-readable, LOWER PRIORITY)
Read `features/engine.py` sections for H2H and rest_days features. Verify:
- H2H rolling window >= 10 meetings (paper's top-4 feature)
- `rest_days_differential` computed as home_rest - away_rest (not just separate features)
If missing, add to `engine-parity-sync` work item scope.

### Experiment 4 — P7 Diversify Trigger (VM, CONDITIONAL)
If P7 `best_brier` remains at 0.25412 after fire-108 (2 more cycles), the field-lag is stuck and the island needs external pressure:
```json
POST https://lbjlincoln-political-alpha-7.hf.space/api/command
{"command": "diversify"}
```

## Implementation Constraints

- **Rule#2:** engine.py changes must sync to nomos-nba-agent simultaneously (engine-parity-sync blocking — resolve first)
- **Rule#8:** No stacking — only the feature engineering from the Sci Reports paper is portable, not the meta-learner
- **Rule#6:** MAX_FEATURES=200 hard cap on all islands
- **Safe commit:** all VM changes via `scripts/lib/safe_commit.sh`

## Expected Impact

| Experiment | Island | Current Best | Target | Confidence |
|-----------|--------|-------------|--------|------------|
| LightGBM addition | S22 | 0.22551 | 0.221-0.222 | MEDIUM (cross-domain signal) |
| LightGBM verify | S13 | 0.22344 | maintain | HIGH |
| H2H depth audit | engine | — | feature quality | HIGH |
| LR addition | S22/P2/P4/P5/P7 | fleet | 0.220/0.248 | HIGH (3x SOTA confirmed) |
