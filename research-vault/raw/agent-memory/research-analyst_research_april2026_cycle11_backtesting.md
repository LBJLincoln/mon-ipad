---
name: Backtesting & Multi-Agent Portfolio Research — April 2026 Cycle 11
description: Apr 5 2026 cycle 11: CPCV walk-forward, 200-agent DSR gating, Bayesian Kelly, multivariable Kelly covariance, Walsh&Joshi calibration-first (+34% ROI), Walsh github, mlfinlab
type: project
---

# Backtesting & Multi-Agent Portfolio Optimization — April 5 2026

## Core Finding: Calibration-First Selection is Worth +70pp ROI
Walsh & Joshi (arXiv:2303.06021, GitHub: conorwalsh99/ml-for-sports-betting):
- Calibration-based model selection: +34.69% ROI
- Accuracy-based model selection: -35.17% ROI
- Delta: 69.86 percentage points on NBA moneyline backtest
- OUR SYSTEM IS CORRECT: we select by Brier score = calibration selection
- Key: the BETTING SIMULATION must also use calibration-filtered predictions, not accuracy

## The 200-Agent False Discovery Problem
Running 200 strategy agents on same historical data:
- E[false positives] = 200 * 0.05 = 10 strategies appear profitable by chance alone
- Solution: Deflated Sharpe Ratio (DSR) gating (Bailey, Lopez de Prado SSRN:2326253)
- DSR adjusts Sharpe for: number of trials, autocorrelation, non-normality
- Require: DSR > 0 at p<0.05 AND OOS_Sharpe > 0.70 * IS_Sharpe
- Implementation: mlfinlab.backtest_statistics.deflated_sharpe_ratio

## Walk-Forward Architecture (CPCV not simple hold-out)
CPCV (Combinatorial Purged Cross-Validation):
- k=8 folds, n_test_splits=2 → 28 IS/OOS paths
- Purge=7 days, Embargo=1 day (prevents NBA game correlation leakage)
- Accept strategy only if parameter values stable: CV(param) < 0.30 across 28 paths
- mlfinlab.cross_validation.CombinatorialPurgedKFold

## Bayesian Kelly Formula
```python
p_adj = (alpha_hist + p_ml * N_eff) / (alpha_hist + beta_hist + N_eff)
f = max(0, (p_adj*(b+1) - 1)/b) * 0.25
```
Parameters: alpha_hist/beta_hist = team wins/losses last 3 seasons, N_eff=20, b=decimal_odds-1

## Multivariable Kelly for Correlated Bets (SSRN:5341539)
```
f* = 0.25 * Sigma^-1 * mu_ev
Sigma[i,j] = Cov(R_i, R_j) from 1000-game rolling window
Same-game correlations: rho(ML,total)~0.25, rho(ML,spread)~0.35
```
CVXPY form: Maximize mu_ev@f - 0.5*lambda*quad_form(f,Sigma); sum(f)<=0.25; f_i<=0.05

## Key Repos
- conorwalsh99/ml-for-sports-betting — full NBA backtest pipeline
- thk3421-models/KellyPortfolio — correlated Kelly via covariance matrix
- georgedouzas/sports-betting — Python bettor/dataloader framework
- mlfinlab — CPCV, DSR, PBO (pip install mlfinlab)

## Overfitting Detection Rules
1. OOS Sharpe < 0.70 * IS Sharpe → REJECT
2. DSR <= 0 at p=0.05 → REJECT
3. PBO > 0.50 from CSCV → REJECT
4. OOS ROI declines monotonically over OOS folds → REJECT (regime decay)
5. Backtest ROI > 20% on large sample → SUSPICIOUS, require explanation

## Why: User wants to build 200-agent strategy tournament. Without statistical gating, 10+ false-positive strategies would be deployed live.
## How to apply: Reference these formulas in any bet-sizing or strategy selection implementation.
