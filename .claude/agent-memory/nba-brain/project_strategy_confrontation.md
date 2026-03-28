---
name: Strategy Confrontation Backtest
description: Kaggle tree-only multi-market backtest — 55 strategy combos, 12 bet types, confrontation table
type: project
---

Tree-only walk-forward backtest deployed 2026-03-28.

**Why:** Previous backtest placed 0 bets because TabICL fails on P100 CUDA (torch.cuda not compatible with TabICL's CUDA requirements). Replaced entirely with CPU-safe tree ensemble.

**How to apply:** When the next confrontation results arrive, read `/kaggle/working/strategy-confrontation.json` from the kernel output and import best strategy into the daily prediction pipeline.

**Kernel:** `alexismoret6/nba-strategy-confrontation-tree-only` — pushed 2026-03-28T15:54
**Script:** `scripts/kaggle/nba_season_backtest.py` + `scripts/kaggle-backtest/`

**Models:** XGBoost (25%), LightGBM (25%), CatBoost (20%), ExtraTrees (20%), RandomForest (10%)

**Bet types (12):** ML_HOME, ML_AWAY, ATS_HOME, ATS_AWAY, OVER, UNDER, H2_ATS_HOME, H2_ATS_AWAY, H2_OVER, H2_UNDER, H1_ATS_HOME, H1_ATS_AWAY, H1_OVER, H1_UNDER, VALUE_DOG, TEAM_TOTAL_HOME_OVER, TEAM_TOTAL_AWAY_OVER

**Sizing strategies (5):** Kelly 25%, Kelly 15%, Kelly 10%, Flat $10, Proportional 1%

**Bet filter sets (11):** ALL, ML_ONLY, ATS_ONLY, TOTALS, H1_ONLY, H2_ONLY, VALUE_DOG, ML_ATS, ML_TOTALS, TEAM_TOTAL, TOP4

**Total combos:** 55 (11 × 5)

**Prior multi-market findings (Elo baseline, 2022 season):**
- H1_ATS_AWAY: +$426 (positive)
- H1_UNDER: +$950 (positive)
- H2_UNDER: +$1,159 (positive)
- ML_AWAY: +$58 (marginally positive)
- TOP4 filter tests these specifically
