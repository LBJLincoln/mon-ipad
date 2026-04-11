# NBA Research Proposal — Cycle 93
**Date:** 2026-04-11T16:30Z  
**Brain cycle:** 93  
**Priority:** CRITICAL — market-implied features SHAP 0.803 (dominant)

## Source
MDPI Information 17(1):56 (2026) — "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets"  
URL: https://www.mdpi.com/2078-2489/17/1/56

## Key Finding
Market-implied probability has **mean |SHAP| = 0.803** — dominates all other features combined (rolling win rate = 0.026, rolling points = 0.008). This single feature has **30x more predictive power** than the next most important feature.

> "Predictions are driven primarily by market expectations and simple form indicators"
> "Market-implied probability: mean |SHAP| = 0.803"

## Proposed Implementation (2 components)

### Component 1: Market-Implied Probability Features (6 features)
Already proposed in cycle 92 — this cycle confirms CRITICAL priority.

```python
# In features/engine.py — add to feature set
def market_implied_features(odds_home, odds_away):
    # American odds → implied prob (remove vig)
    prob_home_raw = 1 / (1 + 10**(odds_away/100)) if odds_home > 0 else odds_home/(odds_home-100)
    prob_away_raw = 1 / (1 + 10**(odds_home/100)) if odds_away > 0 else odds_away/(odds_away-100)
    overround = prob_home_raw + prob_away_raw
    
    features = {
        'market_home_win_prob': prob_home_raw / overround,      # vig-removed
        'market_overround': overround,                           # bookmaker margin
        'market_logit': math.log(prob_home_raw / prob_away_raw),# log-odds
        'market_home_prob_raw': prob_home_raw,                   # raw implied prob
        'market_spread_normalized': spread / 10.0,              # point spread
        'market_total_normalized': total / 220.0,               # over/under
    }
    return features
```

**Data source:** The Odds API (free tier) — check if `scripts/nba-daily-odds.py` is already writing to `data/historical-odds/`. If yes, deploy IMMEDIATELY.

### Component 2: Isotonic Calibration of Market Baseline
Paper validates: "isotonic-regression calibration of closing moneylines = best-possible probabilistic forecaster using only market information"

```python
# In app.py — calibrate tree model output against market baseline
from sklearn.isotonic import IsotonicRegression
from sklearn.calibration import CalibratedClassifierCV

# Option A: Auto-select best calibration method by Brier CV
calibrated = CalibratedClassifierCV(base_model, method='isotonic', cv=5)

# Option B: Post-hoc isotonic on market probs as pseudo-labels
# Use market_implied_prob as soft labels → isotonic regress tree output to it
```

## Expected Brier Improvement
| Component | Estimated Delta | Source |
|-----------|----------------|--------|
| Market features (6f) | -0.015 to -0.024 | SHAP 0.803 dominance |
| Isotonic calibration | -0.003 to -0.008 | Paper baseline validation |
| Combined | **-0.018 to -0.032** | Conservative estimate |

If combined: 0.21906 (S15 last seen) - 0.018 = **0.201** — near target of 0.200!

## Deployment Plan
1. **Check:** Does `data/historical-odds/` have recent files? If yes → skip to step 3
2. **Enable:** Verify `scripts/nba-daily-odds.py` cron is running (12:00, 18:00 UTC)
3. **Add to engine.py:** Add `market_implied_features()` function (6 features)
4. **Test on S13 (catboost):** POST /api/config with updated feature set
5. **If Brier improves > 0.001:** Roll out to all islands

## Target Island
S13 (catboost specialist) — CatBoost handles well-calibrated probability features naturally.

## Cross-Repo Note
Similar "market-implied" concept exists in Political Alpha (prediction markets like Polymarket/Kalshi). Cat22-Cat24 cover prediction market signals. The NBA market-implied feature engineering pattern should be cross-ported to political_engine.py if NBA results confirm value.
