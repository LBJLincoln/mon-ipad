# NBA Scientific Experiment Report
**Generated:** 2026-04-07 08:28:58
**Engine:** scientific-experiment.py v1.0

## Part 1: Model Evaluation

### Consensus Model Performance
- **Predictions evaluated:** 14
- **Brier Score:** 0.18929 (95% CI: [0.1028, 0.28882])
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

- **Model Brier:** 0.2152
- **Games in backtest:** 1081
- **Strategies tested:** 42

### Best Strategies by Sharpe Ratio
| Rank | Strategy | Sharpe | ROI% | PnL | Bets | MaxDD |
|------|----------|--------|------|-----|------|-------|
| 1 | EV>20% Kelly=10% | 3.586 | 14.6% | $151.24 | 172 | 0.381 |
| 2 | Tenth Kelly (edge>2%) | 3.581 | 18.3% | $256.40 | 210 | 0.352 |
| 3 | Value Hunter (edge>15%) | 3.580 | 12.7% | $189.97 | 194 | 0.623 |
| 4 | Conservative (low stakes, high threshold) | 3.579 | 11.9% | $49.38 | 192 | 0.320 |
| 5 | Value Hunter (edge>10%) | 3.573 | 11.8% | $172.93 | 199 | 0.623 |

### Kelly Fraction Optimization
| Fraction | Min Edge | Sharpe | ROI% | MaxDD | Bets |
|----------|----------|--------|------|-------|------|
| 0.10 | 2% | 3.581 | 18.3% | 0.352 | 210 |
| 0.10 | 5% | 3.565 | 12.8% | 0.459 | 197 |
| 0.10 | 3% | 3.533 | 16.2% | 0.381 | 200 |
| 0.25 | 5% | 3.505 | 12.4% | 0.572 | 212 |
| 0.50 | 5% | 3.476 | 10.3% | 0.624 | 212 |
| 0.25 | 2% | 3.439 | 18.2% | 0.470 | 223 |
| 0.50 | 2% | 3.431 | 15.8% | 0.534 | 223 |
| 0.25 | 3% | 3.279 | 15.8% | 0.470 | 213 |
| 0.50 | 3% | 3.230 | 13.4% | 0.534 | 213 |
| 1.00 | 5% | 3.212 | 8.0% | 0.866 | 212 |

### Regression Analysis: PnL ~ confidence + edge + odds
- **N observations:** 10000
- **R-squared:** 0.0119

| Variable | Coefficient | Std Error | p-value | Sig |
|----------|-------------|-----------|---------|-----|
| intercept | 4.174710 | 1.717876 | 0.0151 | * |
| confidence | -8.666375 | 2.321446 | 0.0002 | *** |
| edge_pct | 0.122494 | 0.011932 | 0.0000 | *** |
| odds | -0.620816 | 0.281947 | 0.0277 | * |

### Profit by Betting Category
| Category | Bets | Win Rate | Total Profit | Avg Profit | Avg Edge |
|----------|------|----------|--------------|------------|----------|
| alt_spread_home_big | 3282 | 0.470 | +$7372.29 | $2.2463 | 34.2% |
| alt_spread_away_big | 1680 | 0.485 | +$3094.53 | $1.8420 | 25.2% |
| h1_ml_home | 606 | 0.480 | +$1031.80 | $1.7026 | 8.6% |
| team_total_home_under | 463 | 0.620 | +$197.04 | $0.4256 | 6.1% |
| team_total_home_over | 113 | 0.735 | +$79.86 | $0.7067 | 3.6% |
| h1_ml_away | 14 | 0.786 | +$32.59 | $2.3281 | 4.4% |
| ml_away | 275 | 0.178 | -$15.72 | $-0.0572 | 5.6% |
| total_under | 292 | 0.459 | -$66.85 | $-0.2289 | 4.4% |
| ml_home | 1483 | 0.443 | -$528.29 | $-0.3562 | 9.8% |
| spread_away | 583 | 0.475 | -$1052.07 | $-1.8046 | 23.5% |
| spread_home | 1209 | 0.470 | -$1737.58 | $-1.4372 | 31.5% |

### Optimal Threshold Search (Walk-Forward)
- **Train/Test split:** 7000 / 3000 bets
- **Grid configurations tested:** 168

**Optimal Configuration:**
- Min Confidence: 0.55
- Min Edge: 0.0%
- Kelly Fraction: 0.10
- Train ROI: 9900.0% | Test ROI: 6470.41
- Train Sharpe: 2.636 | Test Sharpe: 7.88
- Test Max Drawdown: 0.532

**Top 10 Configurations by Train Sharpe:**
| Conf | Edge | Kelly | Train ROI | Train Sharpe | Bets |
|------|------|-------|-----------|--------------|------|
| 0.50 | 0% | 0.50 | 5067.1% | 2.726 | 4543 |
| 0.50 | 2% | 0.50 | 5067.1% | 2.726 | 4543 |
| 0.55 | 5% | 0.10 | 9900.0% | 2.678 | 3191 |
| 0.55 | 8% | 0.50 | 9397.3% | 2.675 | 2591 |
| 0.55 | 8% | 0.10 | 9900.0% | 2.664 | 2591 |
| 0.55 | 8% | 0.25 | 9397.3% | 2.661 | 2591 |
| 0.55 | 0% | 0.10 | 9900.0% | 2.636 | 3344 |
| 0.55 | 2% | 0.10 | 9900.0% | 2.636 | 3344 |
| 0.55 | 5% | 0.50 | 9438.4% | 2.617 | 3191 |
| 0.55 | 5% | 0.25 | 9665.1% | 2.600 | 3191 |

### Betting Category Profile (from Trading Floor)
| Category | Bets | Avg Stake | Avg Conf | Avg Agreement | Avg Edge | Forced |
|----------|------|-----------|----------|---------------|----------|--------|
| ml_fg | 17 | $3.96 | 0.653 | 0.758 | 6.0% | 0 |
| spread_fg | 14 | $2.76 | 0.655 | 0.750 | 0.0% | 14 |
| total_fg | 16 | $1.00 | 0.691 | 0.802 | 0.0% | 0 |

## Recommendations

- CONSENSUS Brier 0.18929 is competitive. Target: < 0.21570 (ATR)
- WARNING: Low-agreement bets outperform high-agreement. Consensus mechanism may be flawed.
- BEST STRATEGY: EV>20% Kelly=10% (Sharpe 3.586, ROI 14.6%, MaxDD 0.381)
- OPTIMAL THRESHOLDS: confidence >= 0.55, edge >= 0.0%, Kelly fraction = 0.10
- OUT-OF-SAMPLE validation positive: ROI 6470.4%. Strategy is robust.
- REGRESSION: confidence significantly decreases PnL (beta=-8.6664, p=0.0002)
- REGRESSION: edge_pct significantly increases PnL (beta=0.1225, p=0.0000)
- REGRESSION: odds significantly decreases PnL (beta=-0.6208, p=0.0277)
- PROFITABLE categories (6): alt_spread_home_big, alt_spread_away_big, h1_ml_home, team_total_home_under, team_total_home_over
- AVOID categories (5): ml_away, total_under, ml_home, spread_away, spread_home
- BEST AGENT: t1_llama70b (Brier 0.16302)
- WORST AGENT: t1_qwen72b (Brier 0.25250) — consider removing or retraining
