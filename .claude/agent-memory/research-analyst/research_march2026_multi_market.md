---
name: Multi-Market NBA Betting Research March 2026
description: 26 NBA bet types catalogued, efficiency rankings, formulas for spread/totals/props, data sources, implementation roadmap — cycle 7 research
type: project
---

# Multi-Market NBA Betting Research (March 28 2026)

**Why:** User wants to expand from moneyline-only to 20+ bet types per game.
**How to apply:** Reference this when discussing new bet types, market expansion, or data pipeline additions.

## Key Market Efficiency Ranking

From most to least efficient (hardest to easiest to beat):
1. Spread (VERY HIGH efficiency) — skip for now
2. Moneyline (HIGH) — active, 1-3% ROI
3. Game Total (HIGH) — 2-4% ROI, feasible
4. First Half O/U (MEDIUM) — 2-4% ROI
5. Team Totals (MEDIUM) — 3-5% ROI, underexplored
6. Quarter Spreads/O/U (LOW-MEDIUM) — 3-6% ROI
7. Halftime 2H Markets (MEDIUM) — 5-8% ROI, BEST opportunity
8. Player Props Unders (LOW) — 4-8% ROI, systematic bias confirmed
9. Correlated SGP (LOW-MEDIUM) — 8-15% ROI but low capacity

## Biggest Three Opportunities

1. **Halftime 2H betting** — 73-75% accuracy at halftime vs 65% pre-game (Springer 2024). Live score ingestion + halftime re-run. 12h effort.
2. **Player props Unders** — bookmaker over-bias confirmed. EWMA + usage rate + opponent drtg model. 40h effort.
3. **Team totals** — predict home_pts + away_pts separately. Book team totals mispriced vs game total. 6h effort (extends totals model).

## Win Probability → Spread Formula
`spread = -ln(1/p - 1) / 0.13959`
NBA coefficient 0.13959 (empirically validated).

## Predicted Total Formula
```
home_pts = (home_ortg * away_drtg / (lg_ortg * lg_drtg)) * pace_factor * lg_avg_pts
away_pts = (away_ortg * home_drtg / (lg_ortg * lg_drtg)) * pace_factor * lg_avg_pts
total = home_pts + away_pts
```

## Correlated Parlay Key Correlations
- Home ML win ↔ Home team Over: ρ ≈ +0.35
- Away underdog cover ↔ Under: ρ ≈ +0.20
- Home ML win ↔ Game Over: ρ ≈ +0.25

## Key Data Source
Kaggle `cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024` — already downloaded (19,820 games w/ ML+Spread+Total).
The Odds API — props/period markets from May 2023, free tier 500 req/month.

## Referee Alpha
NBA.com publishes referee assignments free. Refs who call more fouls → games trend Over. Add referee_id as Cat 38 feature. 2h effort. Data from Covers.com referee stats.

## Document Location
Full research: `/home/lahargnedebartoli/mon-ipad/docs/MULTI-MARKET-BETTING-RESEARCH.md`
