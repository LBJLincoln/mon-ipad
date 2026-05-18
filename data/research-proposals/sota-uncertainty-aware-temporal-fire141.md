# SOTA Research Proposal: Uncertainty-Aware Temporal Ensemble for NBA Prediction
**Source**: fire-141 EVEN WebSearch — 2026-05-21T12h  
**Priority**: HIGH  
**Fleet best**: 0.22012 (S15) | **Target**: < 0.21 | **LR benchmark**: 0.199 (13th confirm)

## Papers Identified

### 1. Uncertainty-Aware Machine Learning for NBA Forecasting (MDPI Information 2026)
- **URL**: https://www.mdpi.com/2078-2489/17/1/56
- **Key Result**: RNN with Monte Carlo (MC) dropout achieves calibrated sequential probabilities
- **Brier**: LR=0.199, XGBoost=0.202
- **Novelty**: MC dropout quantifies prediction uncertainty per game, not just point estimates
- **Architecture**: team-level metrics + rolling-form indicators + spatial shot-chart embeddings → RNN + MC dropout

### 2. Long-Sequence LSTM for NBA Game Outcome Prediction (arXiv 2512.08591)
- **URL**: https://arxiv.org/pdf/2512.08591
- **Key Result**: 72.35% accuracy, 73.15% precision, 76.13% AUC-ROC
- **Dataset**: 9,840 games across 8 NBA seasons
- **Novelty**: Long-sequence temporal modeling captures inter-season dependencies — best of all baselines

### 3. ML for Basketball Game Outcomes: NBA and WNBA (MDPI Computation 2026)
- **URL**: https://www.mdpi.com/2079-3197/13/10/230
- **Key Result**: Stacked ensemble (NB+AdaBoost+MLP+KNN+XGB+DT+LR) + SHAP
- **Top SHAP features (SHAP #1-7)**: home_next, team_elo_5y, team_elo, win_diff_5g, 2PA, FG, TRB

## Analysis vs Nomos42 Current State

### Gap Analysis
| Metric | MDPI SOTA | Our Fleet Best | Delta |
|--------|-----------|---------------|-------|
| Brier (LR baseline) | 0.199 | 0.22012 (S15 RF) | +0.021 |
| Brier (XGB) | 0.202 | 0.22216 (S13 XGB) | +0.020 |
| Coverage | all metrics | Brier + ROI + Sharpe | comparable |

### Our Advantages vs SOTA
- Multi-objective Pareto optimization (Brier + ROI + Sharpe) — SOTA only optimizes Brier
- GA feature selection (47-200 features from 3,377 candidates) vs fixed feature sets
- Ensemble diversity across 5 evolutionary islands

## Techniques to Implement

### Technique 1: MC Dropout Calibration (Immediate, Low Risk)
**Applies to**: S15 RF-75f fleet best + S22 RF-48f pareto leaders  
- Run N=50 stochastic forward passes at inference time → mean prediction + uncertainty score
- Replace or augment isotonic calibration with MC ensemble voting
- Expected Brier improvement: 0.22012 → ~0.219 (based on MDPI paper gap LR-vs-tree)
- **Rule compliance**: CPU-only, post-hoc (no change to GA), no stacking violation
- **Effort**: 2-3 hours VM script
- **work-queue item**: vm-mc-dropout-calibration-s15 (priority=30)

### Technique 2: ELO + Rolling-Form Features (High Priority)
**Status**: Partially in work-queue  
- vm-add-elo-ratings-engine (priority=75, blocked by engine-parity-sync)
- vm-add-win-diff-5game-feature (priority=35, blocked by engine-parity-sync)
- Additional rolling features from MDPI: 2PA_rolling_5g, FG_rolling_5g, TRB_rolling_5g
- team_elo_5y (5-year ELO trajectory) = SHAP #2 across multiple studies
- **Priority action**: Unblock engine-parity-sync (priority=40) first

### Technique 3: AdaBoost + GaussianNB in Model Pool (Medium Priority)
**Status**: vm-add-adaboost-naive-bayes-model-pool (priority=56)  
- MDPI Computation 2026 stacked ensemble: AdaBoost + NaiveBayes are standalone models
- Rule#8 compliant (no stacking, single-model GA candidates)
- Expected: AdaBoost ~0.225 Brier, GaussianNB ~0.228 Brier on NBA (from paper)
- Diversifies model pool beyond XGB/LGB/RF/ET/CatBoost

### Technique 4: 8-Season Training Window
**Source**: arXiv 2512.08591 (9,840 games 8 seasons = best of baselines)  
- Current fleet: 9,551 games (close to SOTA dataset size)
- LSTM not viable on CPU. Action: Ensure full 8-season data is loaded in cached NPZ
- Add season-relative features (years_into_era, era_elo_drift) for temporal context
- **Effort**: Medium, data pipeline work on VM

## LightGBM Cross-Fleet Finding (fire-141)
**NEW: S15 LightGBM-56f detected in pareto (1st detect fire-141)**  
This validates the NBA→POL cross-port already underway:  
- P5 LightGBM-102f-0.249 Sharpe=1.01 (CONFIRMED)  
- P7 LightGBM-112f-0.24931 (CONFIRMED)  
- **Gap**: P1 and P2 running XGBoost-only — LightGBM not in their model pool  
- **Action**: vm-add-lightgbm-p1-p2 (new work-queue item, priority=48)

## LR=0.199 Benchmark
**Confirmed 13th time (fire-141)** via MDPI Information 2026, SCIRP 2025, NCBl 2024, MDPI Computation 2026.  
This is the definitive calibrated LR lower bound. Our 0.22012 is ~1% above.  
Calibration improvement path: isotonic → venn_abers → MC dropout ensemble.

## Recommended Implementation Order
1. engine-parity-sync (unblocks elo + win_diff_5g features)
2. vm-mc-dropout-calibration-s15 (0-risk calibration improvement)
3. vm-add-elo-ratings-engine (SHAP #1+#2 validated)
4. vm-add-win-diff-5game-feature (SHAP #4 validated)
5. vm-add-adaboost-naive-bayes-model-pool (pool diversification)
