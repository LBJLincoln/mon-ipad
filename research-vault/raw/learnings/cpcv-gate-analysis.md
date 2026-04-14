# CPCV Strategy Gate — Analysis

> Generated 2026-04-14 14:23 UTC

## Gate Configuration
- Min bets: 50
- DSR p-value max: 0.05
- PBO max: 0.4

## Results
- Passed: 0
- Rejected: 10
- Pass rate: 0%


## Top Rejected (potential with tuning)

- **Specialist: Spread**: DSR -2.3773, p=0.99128, ROI 46.428%
- **Fixed 2%**: DSR -19.0724, p=1.0, ROI -20.241%
- **Sharpe Maximizer (risk-adjusted)**: DSR -19.1254, p=1.0, ROI -23.601%
- **Quarter Kelly (edge>3%)**: DSR -19.1827, p=1.0, ROI -22.401%
- **Bayesian Adaptive (shrinkage)**: DSR -19.1827, p=1.0, ROI -22.401%

## Key Learning

ZERO strategies pass CPCV gate.
This indicates:
- Current model predictions lack sufficient edge for profitable betting
- Strategy optimization alone cannot overcome model weakness
- Priority: improve Brier score (model accuracy) before tuning strategies
- DSR negative = Sharpe ratios not stable across folds = overfitting to history