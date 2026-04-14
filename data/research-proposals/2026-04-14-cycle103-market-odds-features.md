# NBA Research Proposal: Market-Derived Features (Cat55)
**Cycle:** 103 | **Date:** 2026-04-14 | **Priority:** HIGH

## Source
Paper: "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets"
Journal: MDPI Information 2078-2489/17/1/56 (2026)

## Key Finding
Combining team statistics with **market pricing (bookmaker odds)** achieves **AUC 0.95**
vs team statistics alone (**AUC 0.76**) or odds alone (**AUC 0.94**).

> The ablation reveals that market and non-market information carry complementary
> predictive content — combining them substantially outperforms either alone.

**Logistic regression baseline** with odds features: **Brier 0.199** (below our 0.20 target!)
**XGBoost** with odds features: **Brier 0.202**

Current fleet best: **0.22251** (S14). Target: **< 0.20**.
Gap to close: **0.02251 → 0.00** (with odds features, paper shows 0.199 is achievable on
a comparable dataset: 2024 season, similar feature count).

## Proposed Features (5)

New category: **Cat55 — Market Odds Features**

| Feature | Description | Source |
|---------|-------------|--------|
| `mkt_home_implied_prob` | Closing moneyline → implied probability (home win) | Odds API / scraped |
| `mkt_spread_abs` | Absolute point spread (market estimate of margin) | Odds API |
| `mkt_total_line` | Over/under total (market estimate of total scoring pace) | Odds API |
| `mkt_overround` | Bookmaker margin = sum(implied_probs) - 1 (market efficiency) | Computed |
| `mkt_line_movement` | (closing_spread - opening_spread) / abs(opening_spread) | Odds API |

## Why These Work

1. **Implied probability** directly encodes the market's aggregated belief — effectively
   an ensemble of thousands of informed predictors including team staff, sharp bettors,
   quant funds. It subsumes most statistical signals.

2. **Overround** measures how certain the market is. Low overround (e.g. 1.02) = strong
   consensus; high overround (1.08+) = uncertainty. High uncertainty games are where
   our model can add most value.

3. **Line movement** is a canonical sharp-money signal. Spread moves against public
   consensus indicate professional money is on the other side.

4. **Total line** captures pace context: high totals = fast-paced game → reduces
   variance in outcome, narrows win probability distribution.

## Implementation Plan

### Data Source Options (in order of preference)
1. **The Odds API** (https://the-odds-api.com/) — free tier 500 req/month, covers NBA
   - Endpoint: `/sports/basketball_nba/odds/`
   - Returns: all major books, H2H + spreads + totals
   - Historical: request historical endpoint (paid) or use already-scraped data in
     `data/historical-odds/` directory

2. **Existing `data/historical-odds/`** — check if moneyline data already exists
   in the repo (the directory exists per the data/ listing)

3. **Sportradar / BetaAPI** — if already in use for game data, odds may be included

### Feature Engineering Notes
- All odds must be **strictly pre-game** (closing line, not live). Never use
  live or post-game odds.
- Implied probability formula: `1 / decimal_odds` (normalized to remove overround)
- Era normalization: odds-to-implied-prob is already scale-free; no season normalization needed
- **Line movement**: `(closing_spread - opening_spread)`. Positive = home team got worse;
  negative = home team improved in market's view.
- Missing odds (for some early-season games): use home_win_pct as fallback proxy

### Integration into engine.py
```python
# Cat55: Market Odds Features (5 features)
def _compute_cat55_market_odds(self, row) -> dict:
    """Market-derived odds features. Strictly pre-game closing lines."""
    home_ml = row.get('home_moneyline_close', None)  # decimal odds e.g. 1.87
    away_ml = row.get('away_moneyline_close', None)
    spread  = row.get('spread_close', None)          # positive = home favored
    total   = row.get('total_close', None)
    spread_open = row.get('spread_open', None)

    if home_ml is None or away_ml is None:
        # Fallback: neutral priors
        return {
            'mkt_home_implied_prob': 0.5,
            'mkt_spread_abs': 0.0,
            'mkt_total_line': 224.0,  # 2025-26 NBA avg total
            'mkt_overround': 0.046,   # typical book margin
            'mkt_line_movement': 0.0,
        }

    home_raw = 1.0 / home_ml
    away_raw = 1.0 / away_ml
    overround = home_raw + away_raw - 1.0
    home_prob = home_raw / (home_raw + away_raw)  # normalized

    line_movement = 0.0
    if spread is not None and spread_open is not None and abs(spread_open) > 0.5:
        line_movement = (spread - spread_open) / abs(spread_open)

    return {
        'mkt_home_implied_prob': float(home_prob),
        'mkt_spread_abs': float(abs(spread)) if spread is not None else 0.0,
        'mkt_total_line': float(total) if total is not None else 224.0,
        'mkt_overround': float(max(overround, 0.0)),
        'mkt_line_movement': float(np.clip(line_movement, -0.5, 0.5)),
    }
```

## Expected Impact

| Metric | Current | With Cat55 | Change |
|--------|---------|------------|--------|
| Fleet best Brier | 0.22251 | ~0.207-0.213 | -0.009 to -0.015 |
| Walk-forward Brier | 0.22447 | ~0.210-0.218 | -0.006 to -0.014 |
| ROI | ~29% | ~35-45% | +6-16% |

Basis: paper shows Brier 0.199 with LR+odds. Our XGBoost/LightGBM ensemble +
200-feature selection should reach 0.205-0.210 on our test set.

## Data Availability Check
- [ ] Check `data/historical-odds/` for existing odds data
- [ ] If empty: run `scripts/data-fetch/fetch_odds.py` (create if needed)
- [ ] Verify closing vs opening odds are both available (for line_movement)
- [ ] Verify data coverage: need ≥ 80% of 9,551 historical games

## Risk Assessment
- **Low risk**: odds are a highly robust, stable signal used in all serious sports
  prediction literature since 2000s. No lookahead bias if we use closing lines.
- **Main risk**: data gaps for early-season games or some historical seasons.
  Mitigation: neutral-prior fallback (0.5 implied prob, 0.0 line movement).

## Next Steps
1. **Check data availability** (1 cycle): verify historical odds exist in repo
2. **Implement Cat55** in features/engine.py (1 cycle): ~30 lines, follows existing cat pattern
3. **Deploy to one test island** (S14 or S15) via POST /api/config (1 cycle)
4. **Evaluate**: if S14/S15 Brier improves > 0.003 within 20 gens, roll out to all islands

## Cross-Project Applicability
Same technique applies to **Political Alpha**:
- Replace "moneyline" with Polymarket/Kalshi implied probabilities
- Line movement → rapid probability change in prediction market
- Cat27 (PREDICTION MARKET INSIDER SIGNALS) already captures some of this
- Propose Cat47: Prediction Market Odds Features (5 features) in next rotation A
