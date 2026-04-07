# Research Proposal: EV>1.10 Filter + 0.3-Kelly Selective Wagering

**Date:** 2026-04-05  
**Cycle:** 63  
**Status:** IMPLEMENTED (nomos-nba-agent/models/kelly.py)  
**Source:** MDPI 2026 "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets" (Brier=0.089)

## Finding

The MDPI 2026 paper achieved **Brier score 0.089** by combining:
1. A non-market model (team stats, Elo, momentum) — AUC=0.94
2. Market-implied probabilities as features — overround, spread, line movement
3. **Fused model**: Outperformed both components (AUC=0.95, Brier=0.089)

Key wagering insight: **EV>1.10 filter + 0.3-Kelly staking**
- Only bet when `model_probability × decimal_odds > 1.10` (at least 10% edge)
- Use 30% of full Kelly (not 25%)
- Result: Fewer bets but dramatically higher average edge quality
- "Trades frequency for quality — concentrates on sparse right-tail high-EV opportunities"

## What Was Changed

**File:** `nomos-nba-agent/models/kelly.py`

```python
# Before
FRACTIONAL_KELLY = 0.25       # Use 1/4 Kelly
MIN_EDGE_THRESHOLD = 0.02     # Minimum 2% edge

# After  
FRACTIONAL_KELLY = 0.30       # 0.3-Kelly (MDPI 2026)
MIN_EV_RATIO = 1.10           # EV filter: model_prob * odds > 1.10
```

Added `min_ev_ratio` check to `evaluate_bet()` — first filter applied before edge check.

## Cross-Project Application

Same change should be ported to `nomos-political-alpha/ops/bankroll_manager.py` (identical Kelly code).

## Next Step

Port the **market fusion** idea: add bookmaker-implied probability as a feature to the NBA feature engine (Category 9 already has market microstructure but could add explicit `market_fusion_prob = blend(model_prob, market_implied_prob, alpha=0.3)`).

This single change could unlock Brier < 0.22 by using market information to calibrate model outputs at test time.
