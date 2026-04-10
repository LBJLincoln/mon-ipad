# NBA Scientific Experiment Report
**Generated:** 2026-04-10 22:01:01
**Engine:** scientific-experiment.py v1.0

## Part 1: Model Evaluation

### Consensus Model Performance
- **Predictions evaluated:** 14
- **Brier Score:** 0.18929 (95% CI: [0.10358, 0.2924])
- **Log Loss:** 0.5454
- **AUC-ROC:** 0.7556
- **ECE (Calibration):** 0.2152
- **Directional Accuracy:** 57.1%

#### Agreement Analysis
- High agreement (>80%): 7 games, accuracy 57.1%
- Low agreement (<60%): 1 games, accuracy 100.0%

#### Calibration (Reliability Diagram)
| Bucket | Predicted | Actual | Count | Error |
|--------|-----------|--------|-------|-------|
| 0.1-0.2 | 0.155 | 0.000 | 1 | 0.155 |
| 0.3-0.4 | 0.370 | 0.500 | 2 | 0.130 |
| 0.4-0.5 | 0.467 | 1.000 | 1 | 0.533 |
| 0.5-0.6 | 0.598 | 1.000 | 1 | 0.402 |
| 0.6-0.7 | 0.670 | 0.333 | 3 | 0.337 |
| 0.7-0.8 | 0.761 | 0.667 | 3 | 0.095 |
| 0.8-0.9 | 0.859 | 1.000 | 2 | 0.141 |
| 0.9-1.0 | 0.914 | 1.000 | 1 | 0.086 |

#### Brier Score Progression
| Date | Avg Brier | Games |
|------|-----------|-------|
| 2026-03-15 | 0.03050 | 2 |
| 2026-04-04 | 0.00741 | 1 |
| 2026-04-05 | 0.23469 | 11 |

### Per-Agent Model Ranking
| Rank | Agent | Brier | Log-Loss | AUC | Accuracy | N |
|------|-------|-------|----------|-----|----------|---|
| 1 | t1_llama70b | 0.16302 | 0.51130 | 0.8833 | 0.818 | 11 |
| 2 | t1_gemma27b | 0.24432 | 0.68088 | 0.6667 | 0.545 | 11 |
| 3 | t1_qwen72b | 0.25250 | 0.69582 | 0.7333 | 0.500 | 8 |

### Statistical Significance (Paired Bootstrap)
No statistically significant differences found at p < 0.05.

## Part 2: Strategy Backtesting

- **Model Brier:** 0.24246
- **Games in backtest:** 1247
- **Strategies tested:** 10

### Best Strategies by Sharpe Ratio
| Rank | Strategy | Sharpe | ROI% | PnL | Bets | MaxDD |
|------|----------|--------|------|-----|------|-------|
| 1 | Specialist: Spread | 3.333 | 45.1% | $127082.10 | 445 | 0.537 |
| 2 | Half Kelly (edge>3%) | -2.335 | -16.7% | $-80.82 | 233 | 0.808 |
| 3 | Quarter Kelly (edge>3%) | -2.335 | -17.0% | $-80.34 | 230 | 0.804 |
| 4 | Fixed 2% | -2.335 | -22.6% | $-50.59 | 156 | 0.506 |
| 5 | Value Hunter (edge>5%) | -2.335 | -16.7% | $-80.82 | 233 | 0.808 |

### Kelly Fraction Optimization
| Fraction | Min Edge | Sharpe | ROI% | MaxDD | Bets |
|----------|----------|--------|------|-------|------|
| 0.50 | 3% | -2.335 | -16.7% | 0.808 | 233 |
| 0.25 | 3% | -2.335 | -17.0% | 0.804 | 230 |

### Regression Analysis: PnL ~ confidence + edge + odds
- **N observations:** 10000
- **R-squared:** 0.0215

| Variable | Coefficient | Std Error | p-value | Sig |
|----------|-------------|-----------|---------|-----|
| intercept | -0.880337 | 2.333705 | 0.7060 |  |
| confidence | -5.676557 | 3.384837 | 0.0936 |  |
| edge_pct | 0.216754 | 0.017893 | 0.0000 | *** |
| odds | 0.335744 | 0.336550 | 0.3185 |  |

### Profit by Betting Category
| Category | Bets | Win Rate | Total Profit | Avg Profit | Avg Edge |
|----------|------|----------|--------------|------------|----------|
| alt_spread_home_big | 3357 | 0.485 | +$15199.75 | $4.5278 | 35.1% |
| alt_spread_away_big | 1769 | 0.483 | +$5755.98 | $3.2538 | 27.2% |
| h1_ml_home | 660 | 0.504 | +$3738.02 | $5.6637 | 10.2% |
| h1_ml_away | 20 | 0.700 | +$327.38 | $16.3691 | 5.2% |
| team_total_home_under | 434 | 0.634 | +$123.99 | $0.2857 | 6.1% |
| team_total_home_over | 104 | 0.740 | +$36.70 | $0.3528 | 3.5% |
| total_under | 270 | 0.470 | -$51.76 | $-0.1917 | 4.4% |
| ml_away | 280 | 0.139 | -$78.56 | $-0.2806 | 6.0% |
| spread_away | 545 | 0.473 | -$674.97 | $-1.2385 | 23.3% |
| ml_home | 1458 | 0.422 | -$875.04 | $-0.6002 | 10.9% |
| spread_home | 1103 | 0.475 | -$1011.40 | $-0.9170 | 31.4% |

### Optimal Threshold Search (Walk-Forward)
- **Train/Test split:** 7000 / 3000 bets
- **Grid configurations tested:** 168

**Optimal Configuration:**
- Min Confidence: 0.50
- Min Edge: 0.0%
- Kelly Fraction: 0.05
- Train ROI: 9476.5% | Test ROI: 9900.0
- Train Sharpe: 2.147 | Test Sharpe: 8.053
- Test Max Drawdown: 0.36

**Top 10 Configurations by Train Sharpe:**
| Conf | Edge | Kelly | Train ROI | Train Sharpe | Bets |
|------|------|-------|-----------|--------------|------|
| 0.55 | 15% | 0.10 | 9244.3% | 3.075 | 2220 |
| 0.55 | 8% | 0.10 | 9244.3% | 3.070 | 2587 |
| 0.55 | 5% | 0.10 | 9244.3% | 3.025 | 3202 |
| 0.55 | 10% | 0.10 | 9244.3% | 3.022 | 2398 |
| 0.55 | 8% | 0.25 | 9275.6% | 3.015 | 2587 |
| 0.55 | 8% | 0.50 | 9275.6% | 3.009 | 2587 |
| 0.55 | 15% | 0.25 | 9275.6% | 2.992 | 2220 |
| 0.55 | 15% | 0.50 | 9275.6% | 2.992 | 2220 |
| 0.55 | 0% | 0.10 | 9244.3% | 2.983 | 3360 |
| 0.55 | 2% | 0.10 | 9244.3% | 2.983 | 3360 |

### Betting Category Profile (from Trading Floor)
| Category | Bets | Avg Stake | Avg Conf | Avg Agreement | Avg Edge | Forced |
|----------|------|-----------|----------|---------------|----------|--------|
| ml_fg | 31 | $1369.45 | 0.557 | 0.655 | 13.6% | 0 |
| spread_fg | 14 | $2.76 | 0.655 | 0.750 | 0.0% | 14 |
| total_fg | 30 | $1392.06 | 0.574 | 0.675 | 0.0% | 0 |

## Recommendations

- CONSENSUS Brier 0.18929 is competitive. Target: < 0.21570 (ATR)
- WARNING: Low-agreement bets outperform high-agreement. Consensus mechanism may be flawed.
- BEST STRATEGY: Specialist: Spread (Sharpe 3.333, ROI 45.1%, MaxDD 0.537)
- OPTIMAL THRESHOLDS: confidence >= 0.50, edge >= 0.0%, Kelly fraction = 0.05
- OUT-OF-SAMPLE validation positive: ROI 9900.0%. Strategy is robust.
- REGRESSION: edge_pct significantly increases PnL (beta=0.2168, p=0.0000)
- PROFITABLE categories (6): alt_spread_home_big, alt_spread_away_big, h1_ml_home, h1_ml_away, team_total_home_under
- AVOID categories (5): total_under, ml_away, spread_away, ml_home, spread_home
- BEST AGENT: t1_llama70b (Brier 0.16302)
- WORST AGENT: t1_qwen72b (Brier 0.25250) — consider removing or retraining
