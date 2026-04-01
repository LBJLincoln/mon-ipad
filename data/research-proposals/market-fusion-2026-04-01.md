# Research Proposal: Market Fusion for NBA Probability Calibration

**Date:** 2026-04-01  
**Source:** Uncertainty-Aware ML for NBA Forecasting in Digital Betting Markets (MDPI Information, Jan 2026)  
**Target:** Brier < 0.21 (from current 0.22066)  
**Priority:** HIGH

## Finding

A January 2026 study found that when market information (implied probabilities from closing moneylines) is added to the non-market feature set, the resulting fused model achieves the strongest overall performance. Market and non-market information carry complementary predictive content.

- Standalone XGBoost: Brier ≈ 0.202, AUC 0.754
- Market-only isotonic calibration: Brier ≈ 0.200
- **Fused model (non-market features + market-implied prob): Best overall**

## Proposed Implementation

### Feature Addition (features/engine.py — Category 9 MARKET MICROSTRUCTURE)
Add two new features to the existing market microstructure block:
```python
# Market fusion: implied probability from closing moneyline
# Formula: implied_prob = 1 / (1 + decimal_odds) with vig removal
names.append("mkt_implied_prob_home")      # Home win implied probability
names.append("mkt_implied_prob_vig_free")  # Vig-removed market consensus
```

### Calibration Step (hf-space/app.py)
After computing base model probability, blend with market:
```python
# Market fusion blend (alpha = 0.25 weighting toward market)
MARKET_ALPHA = 0.25
if "mkt_implied_prob_home" in feature_names:
    mkt_idx = feature_names.index("mkt_implied_prob_home")
    p_market = X_val[:, mkt_idx]
    p_fused = (1 - MARKET_ALPHA) * p + MARKET_ALPHA * p_market
    p = p_fused
```

### Data Requirements
- Closing moneyline odds from The Odds API or OddsPortal
- Already have CLV features in engine.py — can use those as proxy if moneyline unavailable

## Expected Gain
- Current best: 0.22066
- Target after market fusion: ~0.215–0.218
- Stretch goal: <0.21 (matches literature benchmark)

## Risk
- Market data availability (OddsPortal scraping or paid API needed)
- If market data is already in features/engine.py Category 9, can use existing features
- Mitigation: Use existing CLV (closing line value) features as market proxy

## Next Steps
1. Check if `mkt_implied_prob_home` is already computed in engine.py Category 9
2. If yes, add it to GA feature candidates and run experiment
3. If no, integrate closing moneyline from The Odds API
