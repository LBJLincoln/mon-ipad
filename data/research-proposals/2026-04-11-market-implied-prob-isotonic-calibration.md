# NBA Research Proposal: Market-Implied Probability + Isotonic Calibration

**Cycle:** 92 | **Date:** 2026-04-11 | **Rotation:** B (NBA research) | **Priority:** CRITICAL

## Executive Summary

MDPI Information 17(1):56 (2026) — *Uncertainty-Aware Machine Learning for NBA Forecasting* — proves:

| Model | Brier | Log-Loss |
|-------|-------|----------|
| XGBoost (tree only) | 0.202 | 0.589 |
| Logistic Regression (calibrated) | 0.199 | 0.583 |
| **Fused: tree + market features** | **0.089** | **0.280** |

**Market features (spread, total, implied_prob) SHAP importance = 0.803** — the single most
informative feature group, dwarfing all box-score statistics.

Our fleet target: Brier 0.20. Current best: 0.21906 (S15, gen 860). Gap: 0.019.
Adding market-implied probability as an anchor feature could halve this gap.

---

## Problem Statement

Our current feature engine (v3.1-59cat, 7213 raw features, MAX_FEATURES=200) is **entirely
box-score and derived statistics**. We have:
- Team efficiency, pace, rolling form
- ELO ratings, head-to-head records
- Injury indicators, rest days
- No market-implied probabilities
- No isotonic post-hoc calibration layer

**The market is pricing information we don't have.** Vegas lines encode:
- Injury reports (private intel from scouts)
- Lineup changes (pre-game)
- Travel fatigue (complex logistics)
- Referee tendencies (market-specific)

Currently our GA is selecting 55-80 features from 7213 raw candidates. Adding market
features gives the GA a near-certain high-SHAP feature to select.

---

## Proposed Changes

### Change 1: Market Probability Features (6 new features in engine.py)

Add to `hf-space/features/engine.py` as a new feature category:

```python
# Cat60: Market-Implied Probability Features
# Source: The Odds API / DraftKings / FanDuel line data
def compute_market_features(game_row):
    """
    6 features using Vegas/market pricing as anchor.
    SHAP importance 0.803 (MDPI 2026 study).
    """
    features = {}
    
    # Feature 1: Market implied home win probability
    # Convert American odds to probability (e.g., -150 home = 60%)
    home_odds = game_row.get('home_moneyline', None)
    if home_odds is not None:
        if home_odds < 0:
            impl_prob = abs(home_odds) / (abs(home_odds) + 100)
        else:
            impl_prob = 100 / (home_odds + 100)
        features['market_home_win_prob'] = impl_prob
        features['market_overround_adj_prob'] = impl_prob / (1 + 0.045)  # remove vig
    else:
        features['market_home_win_prob'] = 0.55  # default home advantage
        features['market_overround_adj_prob'] = 0.524
    
    # Feature 2: Point spread (normalized)
    spread = game_row.get('point_spread', 0)  # home team perspective
    features['spread_normalized'] = spread / 15.0  # typical range ±15 pts
    
    # Feature 3: Total (over/under)
    total = game_row.get('game_total', 225)  # default NBA total
    features['total_normalized'] = (total - 225) / 20.0  # Z-score vs avg
    
    # Feature 4: Market momentum (line movement from open to close)
    open_spread = game_row.get('open_spread', spread)
    line_movement = spread - open_spread  # positive = home team bet
    features['line_movement'] = line_movement
    
    # Feature 5: Closing line value flag (sharp money indicator)
    features['sharp_money_flag'] = 1.0 if abs(line_movement) >= 2.0 else 0.0
    
    # Feature 6: Log-odds transform of market probability
    p = max(0.01, min(0.99, features['market_home_win_prob']))
    features['market_logit'] = math.log(p / (1 - p))
    
    return features
```

**Integration target:** `hf-space/features/engine.py`, `features/engine.py`
**Test on:** S13 (catboost specialist, lowest risk)

---

### Change 2: Isotonic Calibration Post-Processing

After model prediction in `app.py`, apply isotonic regression calibration:

```python
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression

# In app.py GA evaluation loop (after model.fit):
def calibrate_predictions(model, X_train, y_train, X_val):
    """
    Post-hoc isotonic calibration. MDPI 2026: reduces Brier by 0.003-0.008.
    Try sigmoid first (faster), isotonic if more validation data available.
    """
    calibrated = CalibratedClassifierCV(
        estimator=model,
        method='isotonic',  # better than sigmoid for tree models
        cv='prefit'         # use already-fitted model
    )
    calibrated.fit(X_train, y_train)
    probs = calibrated.predict_proba(X_val)[:, 1]
    brier = brier_score_loss(y_val, probs)
    return probs, brier, calibrated
```

**Automatic method selection:** Try both `sigmoid` and `isotonic`, keep lower Brier.

---

### Change 3: Era Normalization (Per-100-Possessions)

All counting stats (points, assists, rebounds) expressed per 100 possessions:

```python
# Normalize raw counting stats for pace-adjusted comparison
def pace_adjust(raw_stat, possessions, league_avg_possessions=100):
    """Express stat per 100 possessions (era-normalized)."""
    if possessions <= 0:
        return raw_stat
    return raw_stat * (league_avg_possessions / possessions)
```

This corrects for pace inflation (high-pace teams appear better on raw stats).

---

## Expected Impact

| Change | Estimated Brier Delta | Confidence | Target Island |
|--------|-----------------------|------------|---------------|
| Market implied prob (6 features) | -0.005 to -0.015 | HIGH | S10, S11, S13 |
| Isotonic calibration | -0.002 to -0.006 | MEDIUM-HIGH | All islands |
| Era normalization | -0.001 to -0.003 | MEDIUM | All islands |
| **Combined** | **-0.008 to -0.024** | HIGH | **Fleet-wide** |

**Combined floor case (-0.008):** S15 from 0.21906 → 0.21106 (below checkpoint 0.21837)
**Combined ceiling case (-0.024):** Fleet best → 0.193 (below target 0.20)

---

## Data Source

**The Odds API** (free tier): https://the-odds-api.com
- Endpoint: `/v4/sports/basketball_nba/odds`
- 500 requests/month free
- Returns: moneyline, spread, totals for all NBA games
- Historical data: $5/month tier

**Current VM cron for odds:** `scripts/nba-daily-odds.py` (12:00, 18:00)
This script may already be fetching odds data — check if it's writing to `data/historical-odds/`.
If odds are already being fetched, the feature engine just needs the extraction functions.

---

## Implementation Plan

1. **VM:** Check `data/historical-odds/` for existing odds data files
2. **Engine:** Add `compute_market_features()` to `features/engine.py` (6 features)
3. **Engine:** Add `calibrate_predictions()` to `hf-space/app.py`
4. **Deploy:** Push to S13 first (catboost — lowest Brier plateau risk)
5. **Measure:** Compare Brier after 20 generations vs S13 baseline (0.22316)
6. **Fleet:** If -0.003 or better, deploy to all 6 islands

**Estimated implementation time:** 2-3 VM cycles (45 min of engineering work)

---

## References

- [MDPI Information 17(1):56 (2026)](https://www.mdpi.com/2078-2489/17/1/56) — Uncertainty-Aware ML for NBA Forecasting
- [Nature Scientific Reports (2025)](https://www.nature.com/articles/s41598-025-13657-1) — Stacked Ensemble NBA Prediction
- [PMC 11265715 (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/) — XGBoost+SHAP NBA Prediction
- The Odds API: https://the-odds-api.com

---

*Generated by Nomos42 24/7 Brain — Cycle 92 — 2026-04-11T12:30Z*
