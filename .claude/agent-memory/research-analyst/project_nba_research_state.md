---
name: project_nba_research_state
description: Current NBA model state as of 2026-03-25, evolution results, feature counts, key gaps
type: project
---

Current best Brier: 0.21867 (experiment #734, extra_trees, 142 features, gen 104)
Target: Brier < 0.20

**Why:** $1B fund needs sub-0.20 Brier to achieve ROI > 5% and Sharpe > 1.5 threshold for deploying real capital.

**How to apply:** All research proposals must include realistic Brier delta estimates. Sub-0.20 requires multiple techniques in combination — no single technique gets there alone.

## Latest Evolution Run (2026-03-16)

Source: evolution-20260316-2142.json
- 9290 games, 164 raw features, 94 selected, 30 GA generations, 100 Optuna trials
- Best model: stacking (Brier 0.2205)
- XGBoost: 0.2206, RF: 0.2218, LR: 0.2225
- LightGBM: 0.2394 (anomalously bad — hyperparameter issue suspected)
- CatBoost: 0.2282
- All calibrated variants WORSE than uncalibrated (calibration stub not properly fitted)

## Critical Gap Identified

LightGBM at 0.2394 vs XGBoost at 0.2206 on identical data — 18.8 Brier points difference. S14 (LightGBM specialist) should be investigating this. Root cause likely: Optuna not exploring LightGBM-specific hyperparams (num_leaves, min_child_samples, reg_alpha).

## Calibration Status

calibration/isotonic_calibrator.py has STUB breakpoints — never properly fitted. This is why all calibrated variants are WORSE. Fixing calibration is a high-priority quick win.

## Feature Engine

v3.0-35cat, 6000+ features available, 35 categories. Evolution selects 60-142 features. SHAP analysis on top evolved set has NOT been run yet — unknown which features are actually driving predictions.

## HF March 2026 Scan Results (2026-03-25)

NEW SOTA: TabICLv2 (arXiv 2602.11139, MIT, Feb 2026) beats RealTabPFN-2.5 on TabArena — pip3 install tabicl. Our 9k dataset is in its optimal range.
TabPFN-2.5 (Prior-Labs/tabpfn_2_5) is #1 trending HF tabular model with 100% win rate vs XGBoost on our dataset size.
Top missing features: 5-year ELO (team_elo_5y), circadian advantage (directional travel), L-RAPM lineup differential.
Scientific Reports 2025 SHAP: team_elo_5_y is #1 predictive feature ahead of all box score stats.
See: /home/termius/nomos-nba-agent/data/results/hf-scan-march2026.json for full findings.
