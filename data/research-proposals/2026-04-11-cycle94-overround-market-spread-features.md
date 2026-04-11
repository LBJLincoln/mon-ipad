# NBA Research Proposal: Overround + Market-Spread Features as Predictive Signals

**Cycle:** 94 | **Date:** 2026-04-11 | **Source:** MDPI Uncertainty-Aware ML (2026) + NBA betting research  
**Target:** Brier < 0.218 | **Target Island(s):** S13 (catboost), S15 (wide_search)  
**Estimated Brier improvement:** −0.002 to −0.004

---

## Background

The MDPI 2026 paper "Uncertainty-Aware Machine Learning for NBA Forecasting" (doi:10.3390/info17010056)
reports LR achieves Brier **0.199** when combined with:
1. Market-derived features (implied probs, spreads, totals, **overround**)
2. Fractional Kelly staking (0.3× multiplier) for betting decisions

Key insight: **overround** (bookmaker margin = sum of de-vigged implied probs − 1) is a direct signal of
bookmaker confidence. High overround → market is uncertain → model predictions more valuable.

---

## Proposed Features (Cat50 candidate)

### Group A: Overround Features (bookmaker margin)
```python
# Overround = how much the book takes above fair odds
# Formula: overround = (1/home_odds + 1/away_odds) - 1.0
tc50_overround = home_imp_prob + away_imp_prob - 1.0            # raw overround
tc50_overround_norm = tc50_overround / 0.045                    # normalize by league avg ~4.5%
tc50_high_overround_flag = (tc50_overround > 0.06).astype(int) # flag >6% margin
tc50_low_overround_flag = (tc50_overround < 0.02).astype(int)  # flag <2% (sharp game)
```

### Group B: Market Spread Features
```python
# Spread normalized by team ELO difference — detects market mispricing
tc50_spread_elo_ratio = abs(point_spread) / (abs(home_elo - away_elo) + 1)
tc50_spread_sign = np.sign(point_spread)  # home favored +1, away favored -1
tc50_spread_magnitude = abs(point_spread) / 10.0  # normalized to [0, 3]
tc50_total_line = game_total / 220.0               # normalized around league avg 220pts
```

### Group C: Market Consensus Features
```python
# How much does market agree with team ELO?
elo_implied_prob = 1 / (1 + 10 ** ((away_elo - home_elo) / 400))
tc50_market_elo_agreement = 1.0 - abs(home_imp_prob - elo_implied_prob)
tc50_market_surprise = home_imp_prob - elo_implied_prob         # + if market overvalues home
tc50_line_move_proxy = abs(open_spread - close_spread)         # if available
```

---

## Implementation Plan

### Step 1: Add features to features/engine.py (NBA)

Add `_build_market_features()` function:
```python
def _build_market_features(df):
    """Cat50: Overround + market-spread signals (MDPI 2026 uncertainty-aware ML)."""
    feats = {}
    
    # Require: home_ml_odds, away_ml_odds (moneyline), point_spread, game_total
    if 'home_ml_odds' in df.columns and 'away_ml_odds' in df.columns:
        # Convert American odds to implied probs
        home_imp = np.where(df.home_ml_odds > 0, 
                            100 / (df.home_ml_odds + 100),
                            -df.home_ml_odds / (-df.home_ml_odds + 100))
        away_imp = np.where(df.away_ml_odds > 0,
                            100 / (df.away_ml_odds + 100), 
                            -df.away_ml_odds / (-df.away_ml_odds + 100))
        
        feats['tc50_overround'] = home_imp + away_imp - 1.0
        feats['tc50_overround_norm'] = feats['tc50_overround'] / 0.045
        feats['tc50_high_overround'] = (feats['tc50_overround'] > 0.06).astype(float)
        feats['tc50_low_overround'] = (feats['tc50_overround'] < 0.025).astype(float)
        feats['tc50_home_impl_prob'] = home_imp
        feats['tc50_away_impl_prob'] = away_imp
        
        # Market surprise vs team ELO
        if 'team_elo' in df.columns and 'opp_elo' in df.columns:
            elo_prob = 1 / (1 + 10 ** ((df.opp_elo - df.team_elo) / 400))
            feats['tc50_market_elo_agreement'] = 1.0 - abs(home_imp - elo_prob.values)
            feats['tc50_market_surprise'] = home_imp - elo_prob.values
    
    if 'point_spread' in df.columns:
        feats['tc50_spread_abs'] = abs(df.point_spread) / 10.0
        feats['tc50_spread_sign'] = np.sign(df.point_spread)
        
    if 'game_total' in df.columns:
        feats['tc50_total_norm'] = df.game_total / 220.0
        feats['tc50_high_total'] = (df.game_total > 230).astype(float)
        feats['tc50_low_total'] = (df.game_total < 210).astype(float)
    
    return pd.DataFrame(feats, index=df.index)
```

### Step 2: Verify data availability
Check that `home_ml_odds`, `away_ml_odds`, `point_spread`, `game_total` are in the data pipeline.
File: `data/nba-odds/` or `scripts/nba-daily-odds.py` output.

### Step 3: Deploy to S13 via API when awake
```bash
curl -X POST https://nomos42-nba-evo-4.hf.space/api/command \
  -H "Content-Type: application/json" \
  -d '{"action": "inject_features", "features": ["tc50_overround", "tc50_market_surprise", "tc50_spread_abs"]}'
```

---

## Why This Works

- **Overround encodes market uncertainty**: When bookmakers widen margins, they're hedging uncertainty.
  High-overround games have higher variance — our model's Brier benefit is larger in these games.
- **Market surprise (model vs market) is a direct edge signal**: When our Brier probability disagrees
  with the market implied probability, one of them is wrong. This disagreement is a feature.
- **Paper evidence**: MDPI 2026 shows market features push LR from Brier ~0.215 to **0.199** (-0.016).
  Even partial adoption should yield −0.003 to −0.005 improvement.

---

## Risk Assessment

- **Data dependency**: Requires odds data in pipeline. Check `scripts/nba-daily-odds.py` output format.
- **Lookahead risk**: ZERO — all odds are available pre-game. No future leakage.
- **Feature count**: ~12 new features per game → well within MAX_FEATURES=200 budget.
- **CPU cost**: Trivial arithmetic operations, no additional models.

---

## Priority: HIGH

S15 (wide_search, last Brier 0.21906) is only 0.00069 from checkpoint threshold 0.21837.
Adding market features when S15 wakes could push it past the checkpoint.

**Deploy order**: S13 (catboost specialist) first to validate, then inject to S15 and S10.
