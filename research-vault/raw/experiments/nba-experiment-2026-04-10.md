# NBA Scientific Experiment Report
**Generated:** 2026-04-10 08:01:29
**Engine:** scientific-experiment.py v1.0

## Part 1: Model Evaluation

## Part 2: Strategy Backtesting

- **Model Brier:** 0.24246
- **Games in backtest:** 1247
- **Strategies tested:** 10

### Best Strategies by Sharpe Ratio
| Rank | Strategy | Sharpe | ROI% | PnL | Bets | MaxDD |
|------|----------|--------|------|-----|------|-------|
| 1 | Specialist: Spread | 3.333 | 45.1% | $127082.10 | 445 | 0.537 |
| 2 | Half Kelly (edge>3%) | -2.335 | -29.1% | $-80.66 | 138 | 0.806 |
| 3 | Quarter Kelly (edge>3%) | -2.335 | -22.8% | $-80.20 | 153 | 0.802 |
| 4 | Fixed 2% | -2.335 | -20.3% | $-50.21 | 184 | 0.502 |
| 5 | Value Hunter (edge>5%) | -2.335 | -29.1% | $-80.66 | 138 | 0.806 |

### Kelly Fraction Optimization
| Fraction | Min Edge | Sharpe | ROI% | MaxDD | Bets |
|----------|----------|--------|------|-------|------|
| 0.50 | 3% | -2.335 | -29.1% | 0.806 | 138 |
| 0.25 | 3% | -2.335 | -22.8% | 0.802 | 153 |

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
| ml_fg | 31 | $1369.45 | 0.557 | 0.655 | 13.6% | 0 |
| spread_fg | 14 | $2.76 | 0.655 | 0.750 | 0.0% | 14 |
| total_fg | 30 | $1392.06 | 0.574 | 0.675 | 0.0% | 0 |

## Recommendations

- BEST STRATEGY: Specialist: Spread (Sharpe 3.333, ROI 45.1%, MaxDD 0.537)
- OPTIMAL THRESHOLDS: confidence >= 0.55, edge >= 0.0%, Kelly fraction = 0.10
- OUT-OF-SAMPLE validation positive: ROI 6470.4%. Strategy is robust.
- REGRESSION: confidence significantly decreases PnL (beta=-8.6664, p=0.0002)
- REGRESSION: edge_pct significantly increases PnL (beta=0.1225, p=0.0000)
- REGRESSION: odds significantly decreases PnL (beta=-0.6208, p=0.0277)
- PROFITABLE categories (6): alt_spread_home_big, alt_spread_away_big, h1_ml_home, team_total_home_under, team_total_home_over
- AVOID categories (5): ml_away, total_under, ml_home, spread_away, spread_home
