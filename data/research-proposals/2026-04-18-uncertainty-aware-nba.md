# Research Proposal: Uncertainty-Aware NBA Prediction (Monte Carlo Dropout + Rolling Form)

**Date:** 2026-04-18  
**Source:** MDPI Information, Jan 2026 — "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets" (https://www.mdpi.com/2078-2489/17/1/56)  
**Current Fleet Best:** 0.22085 (S17 ensemble, checkpointed 2026-04-16)  
**SOTA Reference:** ~0.199 (uncertainty-aware RNN), ~0.202 (XGBoost with calibration), ~0.199 (logistic regression with calibration)

## Key Findings

A January 2026 paper achieves Brier ~0.199 via:
- **Monte Carlo (MC) Dropout** on recurrent neural networks for uncertainty quantification
- **Rolling-form indicators**: per-team weighted moving averages (last 7/14/21/30 games)
- **Spatial shot-chart embeddings**: 15-zone court distribution as dense feature vector
- Post-training calibration via temperature scaling

## Gap Analysis

| Method | Brier | Platform |
|--------|-------|----------|
| SOTA MC Dropout + RNN | ~0.199 | ZeroGPU/Modal |
| Our fleet best (ensemble) | 0.22085 | CPU islands |
| XGBoost SOTA | ~0.202 | CPU-feasible |
| Our best XGBoost (S13) | 0.22132 | CPU island |

**Gap to SOTA: 0.022 Brier points (10% improvement)**

## CPU-Feasible Actions (High Priority)

### Action 1: Rolling-Form Feature Windows (features/engine.py — est. 1h)
- Add weighted rolling averages per team: last 7, 14, 21, 30, 60 games
- Stats: eFG%, TS%, pace, OREB%, DRtg, net rating
- Estimated cost: +20-30 candidates added to feature pool
- **Expected Brier improvement: 0.003-0.005**

### Action 2: Isotonic Recalibration Cross-Pollination
- S20 (isotonic_cpcv) already uses this — extract pattern and apply to S10/S12/S13
- Apply isotonic regression to tree ensemble output on held-out validation fold
- **Expected Brier improvement: 0.001-0.003**

## GPU Actions (Next ZeroGPU/Modal Burst)

### Action 3: MC Dropout + TabICL Ensemble
- TabICL already achieves 0.21514 (Colab best)
- Add MC Dropout heads for uncertainty-aware calibration
- Run 5 epochs on Modal A10G (within budget)
- **Target: 0.210 Brier**

## Priority Ranking

1. **IMMEDIATE (CPU):** Rolling-form windows in features/engine.py — highest CPU ROI
2. **NEXT GPU BURST:** MC Dropout + TabICL ensemble on Modal/ZeroGPU
3. **MEDIUM-TERM:** Shot-chart zone embeddings (needs data pipeline addition)

## Also Applicable to Political Islands

- Rolling-form indicators translate to political rolling event windows (last 30/60/90 days of polling, FEC filings)
- Isotonic recalibration applies directly to political tree ensembles
- P7 lightgbm 84f at 0.24937 shows feature expansion + model diversity pays off
