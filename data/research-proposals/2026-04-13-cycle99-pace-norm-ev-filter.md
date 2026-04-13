# Cycle 99 Research Proposal: Pace-Normalized Per-100 Features + EV-Gated Fractional-Kelly

**Date:** 2026-04-13T13:00Z  
**Source:** MDPI Information 2025, "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets" (doi:10.3390/info17010056)  
**Brier achieved (paper):** 0.089 (fused MC-dropout model), 0.199 (logistic regression baseline)  
**Fleet best (ours):** 0.22251 (S14) — gap to 0.199 baseline is 0.023

## Key Finding #1: Per-100-Possessions Normalization

The paper normalizes ALL box-score aggregates per 100 possessions, removing pace effects from raw counts. This is distinct from per-game averaging.

**Current state:** Unknown — engine.py is 413KB, requires search for `per_100` or `per100` term. If absent, this is a concrete improvement.

**Proposed feature additions to engine.py (new category: `pace_adjusted_per100`):**
```python
# Normalize team stats per 100 possessions
# possessions ≈ FGA - OREB + TOV + 0.44*FTA
def possessions(fga, oreb, tov, fta):
    return fga - oreb + tov + 0.44 * fta

# Per-100 normalized variants of all existing box-score features:
# pts_per100 = pts / possessions * 100
# ast_per100 = ast / possessions * 100
# reb_per100 = reb / possessions * 100
# tov_per100 = tov / possessions * 100 (pace-adjusted turnover rate)
# stl_per100, blk_per100, pf_per100
```

**Why it helps:** Raw pts/game conflates team pace with efficiency. High-pace teams look better offensively but not necessarily more predictable. Per-100 normalization isolates true efficiency, improving cross-team comparability.

**Expected Brier impact:** ~0.001-0.003 reduction if not already present.

## Key Finding #2: 5-Game Rolling Form Window

The paper uses rolling 5-game windows for momentum features, capturing short-term form that bookmaker lines incompletely reflect.

**Proposed features:**
```python
# Rolling 5-game window (already have rolling windows, but verify 5-game specifically)
features['home_win_rate_5g'] = rolling_win_rate(home_games[-5:])
features['away_win_rate_5g'] = rolling_win_rate(away_games[-5:])
features['home_pts_diff_5g'] = rolling_pt_diff(home_games[-5:])
features['away_pts_diff_5g'] = rolling_pt_diff(away_games[-5:])
features['home_pace_5g'] = rolling_pace(home_games[-5:])  # per-100 denominator
features['form_divergence_5g'] = home_win_rate_5g - away_win_rate_5g
```

**Key insight:** Form divergence (home momentum - away momentum) over 5 games captures matchup-specific momentum not in season-level stats.

## Key Finding #3: EV Filter for Decision Layer

The paper applies an EV threshold BEFORE Kelly sizing, suppressing marginal bets.

**Proposed decision layer change (predict_today.py):**
```python
# Only bet when expected value > 10% edge
# p = model probability, o = decimal odds
EV_THRESHOLD = 1.10  # p * o > 1.10

def should_bet(p_model, decimal_odds):
    ev = p_model * decimal_odds
    return ev > EV_THRESHOLD

# Fractional Kelly with EV gate:
def kelly_stake(p_model, decimal_odds, fraction=0.3, bankroll=1000):
    if not should_bet(p_model, decimal_odds):
        return 0.0  # Skip marginal bets
    b = decimal_odds - 1
    q = 1 - p_model
    f_star = (b * p_model - q) / b
    return fraction * f_star * bankroll  # 30% fractional Kelly
```

**Why it matters:** The paper shows simple LR at 0.199 Brier fails to generate positive returns under realistic staking. The EV filter concentrates capital on high-confidence, positive-expectation bets only.

## Key Finding #4: Systematic Market Miscalibration Signal

The paper documents: **favorites are systematically overpriced, underdogs are underpriced.**

**Proposed feature:**
```python
# Market bias signal: model vs implied probability divergence
# If model_p(home) significantly > implied_p(home) = 1/home_odds
# That is an underdog signal — the market undervalues the home underdog
features['market_model_divergence'] = model_prob - market_implied_prob
features['favorite_flag'] = 1 if market_implied_prob > 0.55 else 0
features['underdog_edge'] = market_model_divergence * (1 - favorite_flag)
```

## Implementation Priority

| Feature | Effort | Expected Brier Impact | Priority |
|---------|--------|----------------------|----------|
| Per-100 normalization | Medium (verify first) | 0.001-0.003 | HIGH |
| EV filter decision layer | Low (predict_today.py) | ROI improvement | HIGH |
| 5-game rolling form | Low (verify window exists) | 0.0005-0.001 | MEDIUM |
| Market divergence signal | Low (needs odds data) | 0.001-0.002 | MEDIUM |

## Cross-Repo Application

The per-100 normalization and EV filter are directly applicable to Political Alpha:
- Political outcomes per-N-events (normalize by district population or election cycle length)
- EV filter on political bets (only bet when model diverges >10% from prediction market implied)

## Action Items (Next Engineering Cycle)

1. `grep -n 'per_100\|per100\|possessions' features/engine.py` to verify if already present
2. If absent: add `pace_adjusted_per100` category (~8 features) to engine.py cat55
3. Add EV filter to `scripts/predict_today.py` (low risk, quick win)
4. Test: run walk-forward with EV filter on historical predictions to measure ROI improvement

## Sources

- MDPI: https://www.mdpi.com/2078-2489/17/1/56
- Nature Scientific Reports (stacked ensemble): https://www.nature.com/articles/s41598-025-13657-1
- ACM DL (ML + DL comparison 2025): https://dl.acm.org/doi/10.1145/3773365.3773520
