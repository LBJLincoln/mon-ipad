---
tags: [betting, bankroll, kelly, categories, ROI, nomos42]
date: 2026-04-04
aliases: [Betting, Bankroll, Kelly, Wagering, Value Bets]
---

# 07 -- Betting

> Bankroll: $91.89 / $100 | ROI: -8.11% | Record: 16W-25L | Last bet: 2026-04-02

---

## Live Bankroll (from bankroll-state.json)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Balance | $91.89 | growing | RED |
| Start | $100.00 | -- | -- |
| ROI | **-8.11%** | > +5% | RED |
| Sharpe | -2.99 | > 1.5 | RED |
| Win Rate | 39.02% | > 52% | RED |
| Total Bets | 41 | -- | -- |
| Total Wagered | $103.86 | -- | -- |
| Peak Balance | $110.43 | -- | -- |
| Trough | $100.00 | -- | -- |
| Max Drawdown | 16.79% | < 25% | OK |
| Avg Edge | 130.53% | -- | SUSPICIOUS |
| Season Start | 2026-03-19 | -- | -- |

> [!warning] Root cause of negative ROI
> **SAS team normalization bug**: 5 bets where model confidence >60% but market implied <15% = systematic losses.
> The avg edge of 130.53% is inflated by these corrupted bets -- they look like massive edges but are data errors.

---

## Calibration Config

| Parameter | Value | Notes |
|-----------|-------|-------|
| Kelly fraction | 0.35 | Production |
| Min edge | 3% | Gate threshold |
| ELO K-factor | 22 | Tuned |
| Home court advantage | 2.8 pts | Should reduce to 2.2 |
| Monte Carlo stdev | 11.5 | Scoring model |
| Avg team score | 114.2 | NBA 2025-26 baseline |

Model weights:
- Power ranking: 0.35
- ELO: 0.20
- Poisson: 0.15
- Monte Carlo: 0.30

---

## Strategy Rankings (from TF Backtest)

| Rank | Strategy | Avg ROI | Verdict | Notes |
|------|----------|---------|---------|-------|
| 1 | full_kelly | +135,550% | ELITE | Extreme variance risk |
| 2 | anti_martingale | +125,583% | ELITE | Double after wins |
| 3 | proportional_edge | +73,112% | STRONG | Size proportional to edge |
| 4 | ev_threshold_110 | +52,320% | STRONG | Only bet EV>1.10 |
| 5 | half_kelly | +34,739% | STRONG | Safe sweet spot |
| 6 | quarter_kelly | +222% (Claude live) | STABLE | Conservative, best Sharpe |
| -- | **value_hunter** | **+3,588%** (Grok live) | **CHAMPION** | Contrarian underdog edge |

> [!tip] Recommended production strategy
> **value_hunter + half_kelly** (Grok's winning recipe from [[03-Trading-Floor]])

---

## Bet Categories (50+ available)

### Best Performing (Claude TF season)

| Category | Bets | Win Rate | Profit |
|----------|------|----------|--------|
| alt_spread_home_big | 497 | 47.1% | +$191.49 |
| alt_spread_away_big | 258 | 48.1% | +$82.07 |
| h1_ml_home | 113 | 54.0% | +$17.54 |
| team_total_home_under | 160 | 63.1% | +$11.12 |
| team_total_home_over | 38 | 81.6% | +$4.13 |

### Grok's Best Categories (value_hunter)

| Category | Bets | Profit |
|----------|------|--------|
| alt_spread_home_big | 489 | +$2,016.79 |
| alt_spread_away_big | 254 | +$1,302.49 |
| h1_ml_home | 111 | +$115.43 |
| spread_away | 5 | +$81.78 |

### Underperforming (avoid)

| Category | Bets | Win Rate | Profit |
|----------|------|----------|--------|
| spread_home | 388 | 46.9% | -$57.36 |
| spread_away | 194 | 46.9% | -$19.14 |
| total_under | 95 | 42.1% | -$4.61 |

---

## Known Bugs & Fixes

### 1. SAS Team Normalization Bug (CRITICAL)

- 5 bets with model >60% but market <15% -- all losses
- Fix: validate TEAM_MAP completeness, add odds sanity gate
- Gate: skip if |model_prob - market_implied| > 0.50
- Gate: skip if market_implied < 0.10 or > 0.90
- Expected: eliminate 8 corrupted bets

### 2. Phantom Game (CRITICAL)

- BKN vs BKN detected (home == away), prob 0.6128
- Fix: assert game['home'] != game['away']
- Status: proposed to [[04-Departments#D2 -- Engineering]]

### 3. Overconfidence (HIGH)

- ECE: 0.2758 | Worst bucket: 60-70%
- Fix: Platt scaling (LogisticRegression C=1 on held-out preds)
- Expected: Brier -0.008, ECE -0.17

### 4. Home Bias (LOW)

- 21 home bets WR 38.1% vs 10 away bets WR 40%
- Fix: reduce home_court_advantage 2.8 -> 2.2 pts
- Expected: Brier -0.002

---

## Kelly Sizing Guide

```
Edge = model_prob - market_implied_prob
Kelly_fraction = edge / (odds - 1)
Bet_size = bankroll * kelly_fraction * safety_factor (0.35)

Example: 
  model_prob = 0.60, market_implied = 0.45, odds = 2.10
  edge = 0.60 - 0.45 = 0.15
  kelly = 0.15 / (2.10 - 1) = 0.136
  bet = $91.89 * 0.136 * 0.35 = $4.38
```

---

## Path to +5% ROI

1. Fix SAS normalization bug -> removes ~5 losing bets
2. Apply odds sanity gate -> removes 8 more corrupted bets
3. Implement value_hunter strategy (Grok model) -> higher edge selection
4. Target alt_spread categories (proven +$273 combined in season)
5. Reduce Kelly fraction during calibration (0.35 -> 0.25)
6. Beat Brier 0.20 -> more accurate probs = better edge detection

> [!info] Simulation estimate
> If SAS bug fixed + Platt scaling + value_hunter -> estimated ROI swing of +15-20% over 100 bets

---

## $100 -> $1M Roadmap

| Milestone | Bankroll | Brier Required | ROI/Season | Bets/Week |
|-----------|----------|----------------|------------|-----------|
| Break even | $100 | 0.22 | 0% | 10 |
| Tier 1 | $200 | 0.21 | +50% | 15 |
| Tier 2 | $1,000 | 0.20 | +100% | 20+ |
| Tier 3 | $10,000 | 0.20 | +150% | 25+ |
| Tier 4 | $100,000 | < 0.20 | +200% | 30+ |
| Target | $1,000,000 | < 0.19 | -- | -- |

Key insight: **Brier 0.20 = +25-50% ROI per season** (historical simulation)

---

## Links

[[00-Dashboard]] | [[03-Trading-Floor]] | [[04-Departments]] | [[06-Research]] | [[08-API-Vision]] | [[15-Business-Plan]]
