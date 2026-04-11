# NBA Scientific Experiment Report
**Generated:** 2026-04-11 12:00:15
**Engine:** scientific-experiment.py v1.0

## Part 1: Model Evaluation

### Consensus Model Performance
- **Predictions evaluated:** 14
- **Brier Score:** 0.18929 (95% CI: [0.09876, 0.29123])
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
| 2 | Half Kelly (edge>3%) | -2.335 | -24.1% | $-80.88 | 137 | 0.809 |
| 3 | Quarter Kelly (edge>3%) | -2.335 | -21.3% | $-80.33 | 160 | 0.804 |
| 4 | Fixed 2% | -2.335 | -16.5% | $-50.90 | 198 | 0.509 |
| 5 | Value Hunter (edge>5%) | -2.335 | -24.1% | $-80.88 | 137 | 0.809 |

### Kelly Fraction Optimization
| Fraction | Min Edge | Sharpe | ROI% | MaxDD | Bets |
|----------|----------|--------|------|-------|------|
| 0.50 | 3% | -2.335 | -24.1% | 0.809 | 137 |
| 0.25 | 3% | -2.335 | -21.3% | 0.804 | 160 |

### Regression Analysis: PnL ~ confidence + edge + odds
- **N observations:** 10000
- **R-squared:** 0.0561

| Variable | Coefficient | Std Error | p-value | Sig |
|----------|-------------|-----------|---------|-----|
| intercept | -314.105172 | 16.908241 | 0.0000 | *** |
| confidence | 447.240661 | 22.112879 | 0.0000 | *** |
| edge_pct | -0.467759 | 0.103265 | 0.0000 | *** |
| odds | 43.696244 | 2.920430 | 0.0000 | *** |

### Profit by Betting Category
| Category | Bets | Win Rate | Total Profit | Avg Profit | Avg Edge |
|----------|------|----------|--------------|------------|----------|
| alt_spread_home_7.5 | 1291 | 0.508 | +$47841.36 | $37.0576 | 59.9% |
| race_to_75_home | 457 | 1.000 | +$41715.96 | $91.2822 | 32.5% |
| alt_spread_home_big | 1018 | 0.554 | +$39600.91 | $38.9007 | 41.5% |
| race_to_100_home | 416 | 0.964 | +$37519.33 | $90.1907 | 29.8% |
| q1_home | 539 | 0.809 | +$32479.64 | $60.2591 | 40.0% |
| alt_spread_home_3.5 | 460 | 0.763 | +$31774.22 | $69.0744 | 32.6% |
| q3_home | 520 | 0.811 | +$31186.16 | $59.9734 | 37.9% |
| q2_home | 489 | 0.822 | +$30565.99 | $62.5071 | 34.6% |
| alt_spread_away_7.5 | 766 | 0.526 | +$29802.56 | $38.9067 | 48.5% |
| q4_home | 448 | 0.821 | +$27903.15 | $62.2838 | 31.7% |
| h1_ml_home | 89 | 0.461 | +$18374.07 | $206.4502 | 19.8% |
| alt_spread_away_3.5 | 199 | 0.844 | +$16379.40 | $82.3085 | 29.2% |
| alt_spread_away_big | 495 | 0.533 | +$14664.37 | $29.6250 | 35.7% |
| double_result_aa | 114 | 0.509 | +$3064.40 | $26.8807 | 23.7% |
| home_and_over | 165 | 0.370 | +$1793.40 | $10.8691 | 20.7% |

### Optimal Threshold Search (Walk-Forward)
- **Train/Test split:** 7000 / 3000 bets
- **Grid configurations tested:** 168

**Optimal Configuration:**
- Min Confidence: 0.50
- Min Edge: 15.0%
- Kelly Fraction: 0.25
- Train ROI: 9462.1% | Test ROI: 9519.57
- Train Sharpe: 9.915 | Test Sharpe: 19.559
- Test Max Drawdown: 0.4453

**Top 10 Configurations by Train Sharpe:**
| Conf | Edge | Kelly | Train ROI | Train Sharpe | Bets |
|------|------|-------|-----------|--------------|------|
| 0.50 | 0% | 0.50 | 9175.2% | 10.134 | 4779 |
| 0.50 | 2% | 0.50 | 9175.2% | 10.134 | 4779 |
| 0.50 | 5% | 0.50 | 9175.2% | 10.134 | 4779 |
| 0.50 | 8% | 0.50 | 9175.2% | 10.124 | 4775 |
| 0.50 | 0% | 0.25 | 9177.3% | 10.118 | 4779 |
| 0.50 | 2% | 0.25 | 9177.3% | 10.118 | 4779 |
| 0.50 | 5% | 0.25 | 9177.3% | 10.118 | 4779 |
| 0.50 | 8% | 0.25 | 9177.3% | 10.108 | 4775 |
| 0.50 | 10% | 0.50 | 9175.2% | 10.102 | 4761 |
| 0.50 | 10% | 0.25 | 9177.3% | 10.093 | 4761 |

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
- OPTIMAL THRESHOLDS: confidence >= 0.50, edge >= 15.0%, Kelly fraction = 0.25
- OUT-OF-SAMPLE validation positive: ROI 9519.6%. Strategy is robust.
- REGRESSION: confidence significantly increases PnL (beta=447.2407, p=0.0000)
- REGRESSION: edge_pct significantly decreases PnL (beta=-0.4678, p=0.0000)
- REGRESSION: odds significantly increases PnL (beta=43.6962, p=0.0000)
- PROFITABLE categories (16): alt_spread_home_7.5, race_to_75_home, alt_spread_home_big, race_to_100_home, q1_home
- AVOID categories (7): away_and_under, margin_6_10, ml_away, spread_home, ml_home
- BEST AGENT: t1_llama70b (Brier 0.16302)
- WORST AGENT: t1_qwen72b (Brier 0.25250) — consider removing or retraining
