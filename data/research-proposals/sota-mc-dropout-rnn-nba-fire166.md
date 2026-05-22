# SOTA Research Proposal: Uncertainty-Aware NBA Forecasting via Monte Carlo Dropout RNN

**Fire:** 166 (EVEN WebSearch)  
**Date:** 2026-05-25T20h  
**Source:** MDPI Information 2026, 17(1), 56 — https://www.mdpi.com/2078-2489/17/1/56  
**Title:** Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets

## Key Findings

- **Pregame Brier score: 0.206** (Model A) / 0.216 (Model B) — vs our fleet best 0.22012
- Average Brier (all periods incl. in-game): 0.152 / 0.163
- Architecture: Recurrent neural network (RNN) with **Monte Carlo (MC) dropout** for uncertainty quantification
- Features: team-level performance metrics + rolling-form indicators + spatial shot-chart embeddings
- Evaluated on: accuracy, Brier score, log-loss, AUC, calibration curves
- Baselines beaten: logistic regression, XGBoost, convolutional models, GRU sequence model, market benchmarks

## Why This Matters

- Our best pregame Brier is 0.22012 (S15 RF-75f fleet best)
- MDPI 2026 achieves **0.206 pregame** — genuinely better by ~0.014
- MC dropout provides **calibrated uncertainty estimates** (not just point predictions)
- Shot-chart spatial embeddings are a novel feature source not in our engine
- RNN captures temporal momentum which our static GA feature selection doesn't model directly
- Confirms direction: rolling-form + calibration are both high-leverage improvements

## Connection to Existing Research

- Complements arXiv:2508.02725 (LSTM+Brier-loss, fire-160): both show deep sequence models outperform static ML
- Confirms Venn-Abers finding (arXiv:2605.03816, fire-158): calibration wrappers add 0.001-0.003 Brier
- MC dropout is simpler to implement than full LSTM overhaul — do this first
- PMC12357926 (fire-162): top SHAP features 2PA/FG/TRB/FGA align with rolling-form approach

## Actionable Recommendations

### Priority 1: Monte Carlo Dropout Calibration Layer (near-term)
- Add MC dropout wrapper to best models: S15 RF-75f, S22 RF-48f, any CatBoost candidates
- MC dropout = run inference N=50 times with dropout active → mean prediction + uncertainty interval
- Libraries: PyTorch (native dropout layers), or sklearn-compatible wrapper
- Expected improvement: 0.001-0.003 Brier (calibration effect)
- Target: post-GA calibration layer, not replacing GA loop
- Extend work-queue item: vm-mc-dropout-calibration-s15 (priority=30)

### Priority 2: Rolling-Form Indicators (near-term, BLOCKED)
- Paper's rolling-form indicators confirm: win-diff-last-5-games = top SHAP predictor
- Action: accelerate vm-add-win-diff-5game-feature (priority=35)
- Add: last-10-game win%, home/away split streaks, point-differential rolling average
- BLOCKED by engine-parity-sync (priority=40) — fix first

### Priority 3: Shot-Chart Spatial Embeddings (long-term)
- Novel feature: spatial shot-chart heatmaps per team (zone percentages as features)
- Data source: NBA Stats API shot chart detail endpoint
- Implementation: 2D histogram zone features (corner 3, above-break 3, mid-range, paint) per team
- Estimated lead time: 2-3 weeks of engine work
- Add to backlog: shot-chart-spatial-embeddings (priority=100)

## Implementation Path

1. engine-parity-sync (priority=40) → unblocks feature additions
2. win-diff-5-game rolling feature (priority=35) — confirmed by MDPI2026 + SHAP
3. MC dropout calibration wrapper for S15 fleet-best RF (extend vm-mc-dropout-calibration-s15, priority=30)
4. Long-term: shot-chart zone features as additional feature category

## Verdict

**HIGH VALUE** — pregame Brier 0.206 is genuinely better than our 0.22012 fleet best. Rolling-form indicators and MC dropout calibration are immediately actionable. Shot-chart embeddings are longer-term. The MC uncertainty quantification also helps with position sizing on the trading floor once POL TF is reactivated.
