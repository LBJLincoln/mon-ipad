---
name: research_april2026_cycle10_betting_markets
description: Apr 3 2026 cycle 10: Complete 64-market NBA betting taxonomy — US + French books, efficiency rankings, data APIs, quantitative edge by market
type: project
---

# NBA Betting Markets — Full Taxonomy (April 2026)

**Why:** User requested comprehensive 50+ market research for model expansion. Full file at /tmp/betting-categories-research.md

## Key Findings

### Market Count
- 64 distinct market types identified across 7 tiers
- US books (DraftKings/FanDuel/BetMGM/bet365): 62/64 available
- French books (all 4): 26/64 standard; Betclic specifically offers 350 markets/match for major games

### French Book Status (Critical Update)
- ParionsSport and Unibet FR MERGED on March 24, 2026 — Unibet brand retained, ParionsSport technical platform
- ParionsSport EXCLUSIVE market: **Pari +20** — bet wins the instant your team leads by 20+ at any point in the game. No US equivalent.

### Softest Markets (Highest Expected Edge)

| Rank | Market | Efficiency Rating (5=softest) | Data Source |
|------|--------|------------------------------|-------------|
| 1 | Player Blocks/Steals O/U | 5 | The Odds API paid |
| 2 | Q1 Player Props | 5 | The Odds API paid |
| 3 | Alt Team Totals (quarterly) | 5 | The Odds API paid |
| 4 | Triple-Double Yes/No | 5 | The Odds API paid |
| 5 | Race to X Points (per quarter) | 5 | nba_api play-by-play |
| 6 | SGP correlated legs | 4-5 | No direct data |
| 7 | Pari +20 (FR) | 4 | Simulate from distribution |
| 8 | Player Rebounds O/U | 5 | The Odds API paid |

### The Odds API — Market Keys Reference

**Player props:** player_points, player_rebounds, player_assists, player_threes, player_blocks, player_steals, player_blocks_steals, player_turnovers, player_points_rebounds_assists, player_points_rebounds, player_points_assists, player_rebounds_assists, player_field_goals, player_frees_made, player_frees_attempts, player_fantasy_points

**Special bets:** player_first_basket, player_first_team_basket, player_double_double, player_triple_double, player_method_of_first_basket

**Quarter/Half:** player_points_q1, player_rebounds_q1, player_assists_q1 (limited)

**Game periods:** h2h_q1-q4, h2h_h1/h2, h2h_3_way_q1-q4, team_totals_q1-q4/h1/h2, alternate_spreads_q1-q4/h1/h2, alternate_totals_q1-q4/h1/h2, alternate_team_totals_q1-q4/h1/h2

**Historical availability:** Moneyline/spread/total from 2020 (free). All other markets from May 3, 2023 (paid only). Paid plans start ~$99/month.

### Derivable Without Paid API (Use nba_api Play-by-Play)
- First basket scorer (opening play-by-play events)
- Race to 10/20/30 points (cumulative scoring from play-by-play)
- Pari +20 probability (maximum lead achieved, extractable from play-by-play)
- Quarter-specific team totals (sum of play-by-play scoring by period)
- Overtime probability (derive from our win probability distribution)
- Margin of victory bands (our score differential model)

### Computable From Our EXISTING Model (Deploy Now)
1. **Overtime Yes/No** — P(OT) = P(final score within X) from win probability curve
2. **Margin of Victory Bands** — Our score distribution directly prices (1-5, 6-10, 11-15, 16-20, 20+)
3. **Team Total** — ORTG vs opponent DRTG × pace factor already in feature set
4. **First Half Total** — Same calculation restricted to 2 quarters

### SGP Insight
Research confirms: sportsbook copula models for within-game correlations are systematically wrong. E.g., combining "team to win" with "star player over 25 pts" at fair prices = positive correlation that books underprice. Our joint model (player features × team win probability) captures this.

## How to Apply
- Phase 1 (now, free): Derive OT/margin/team-total predictions from current model
- Phase 2 (paid API ~$99/mo): Add player props pipeline — rebounds and blocks/steals first
- Phase 3 (nba_api free): Extract first basket + Race-to-20 + Pari+20 training data from play-by-play
- Phase 4 (infrastructure): Live model for 2H totals and garbage-time unders
