# SOTA: LSTM-Brier Loss for NBA Sequence Modeling
## Sources: arXiv 2508.02725 + MDPI 2078-2489/17/1/56 + SciReports s41598-025-13657-1
## Fire: 116 EVEN | Date: 2026-05-16 | Priority: HIGH

## Key Findings

### arXiv 2508.02725 (NCAA Basketball, 2025)
- LSTM + Brier loss: **Brier = 0.1589** (best calibrated model tested)
- Transformer + BCE: Brier = 0.1823 (better AUC, worse calibration)
- Brier-loss training produces significantly better-calibrated probabilistic predictions

### MDPI 2078-2489/17/1/56 (NBA Jan 2026, 6th confirmation)
- Uncertainty-aware RNN + Monte Carlo dropout
- **Logistic Regression Brier = 0.199** | **XGBoost Brier = 0.202**
- Our gap: **-0.021 vs LR** — no GPU required to close this gap
- Finding: LR consistently beats XGB; GA must produce more LR models

### Scientific Reports s41598-025-13657-1 (2025)
- Stacked ensemble: NB + AdaBoost + MLP + KNN + XGB + DT + LR
- Outperforms any single model; validates our GA Pareto multi-model approach

## Experiments

### E1: Brier-Loss LSTM [GPU burst, Modal A10G — NEW SCRIPT]
- 3-layer BiLSTM h=128 dropout=0.3, Brier loss
- Input: rolling 10-game window × 75 features (S15 ET attractor)
- Target: Brier < 0.215 on 2025-26 holdout
- Script: scripts/gpu-burst/nba-lstm-brier.py (to create)

### E2: LR Model Pool Boost [VM-READY — BUMP PRIORITY 50→30]
- LR=0.199 confirmed 6 independent times. S14/S15/S18 need /api/config.
- S15: CHECKPOINT FIRST, then add LR+elastic_net.
- Fastest path to closing -0.021 gap vs our 0.22012.

### E3: Temporal Momentum Features [ENGINE CHANGE, after parity-sync]
- win_streak×home×rest_days, back-to-back fatigue, travel_distance
- +15-20 feature candidates to features/engine.py

### E4: Ensemble S15-ET + LSTM [post E1]
- Calibrated average → expected ~0.2176

## Evidence
| Finding | Level | Source |
|---------|-------|--------|
| LR Brier=0.199 | STRONG | 6x independent |
| LSTM-Brier 0.1589 | MODERATE | arXiv 2508.02725 (NCAA) |
| Stacked ensemble | STRONG | SciReports 2025 |
| GA underweights LR | VERIFIED | S13 gen=684 confirmed |

## Priority Order
1. Add LR islands (VM-ready, priority bump to 30)
2. LSTM GPU burst (Modal A10G, new script ~45 min)
3. Temporal momentum features (engine-parity-sync first)
4. Stacking ensemble (after 1-2 confirmed)

## Cross-Project
- pol-oracle CV 0.23274 → LR gap = -0.034 (larger than NBA)
- scripts/gpu-burst/pol-lstm-brier.py as political parallel
