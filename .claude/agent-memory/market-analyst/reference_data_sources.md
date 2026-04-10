---
name: Market Analyst Data Sources
description: File paths and FREE bookmaker APIs for NBA market analysis — no paid APIs
type: reference
---

## Live Odds Files
- `/home/lahargnedebartoli/mon-ipad/data/nba-agent/live-odds.json` — structured odds from free sources
- `/home/lahargnedebartoli/mon-ipad/data/nba-agent/odds-latest.json` — same data, flat array format
- `/home/lahargnedebartoli/mon-ipad/data/nba-agent/market-data.json` — analysis: implied probs, edges, steam, sharp/square
- `/home/lahargnedebartoli/mon-ipad/data/nba-agent/latest-picks.json` — model picks with win probs, spreads, totals, player props, Kelly sizing
- `/home/lahargnedebartoli/mon-ipad/data/nba-agent/quant-summary.json` — model version info, Brier scores, bankroll state
- `/home/lahargnedebartoli/nomos-nba-agent/data/results/crew-market.json` — output target for market reports

## Primary Odds Script (FREE, no API keys)
`/home/lahargnedebartoli/mon-ipad/scripts/fetch_free_odds.py`
- Usage: `python3 scripts/fetch_free_odds.py --source all`
- Historical: `python3 scripts/fetch_free_odds.py --historical 2026-01-01 2026-03-28`

## FREE Data Sources (verified working 2026-03-28)

### 1. ActionNetwork (BEST SOURCE)
- URL: `https://api.actionnetwork.com/web/v1/scoreboard/nba?periods=event&bookIds=15,30,68,69,123`
- No key needed, unlimited requests
- Provides: moneyline, spread, totals + public bet % + public money %
- Book IDs: 15=DraftKings, 30=FanDuel, 68=BetMGM, 69=Caesars, 123=Pinnacle, 19=BetRivers, 283=Bet365
- Sharp/square: ml_away_public (ticket%) vs ml_away_money (money%) per game

### 2. Bovada
- URL: `https://www.bovada.lv/services/sports/event/coupon/events/A/description/basketball/nba?marketFilterId=def&lang=en`
- No key, returns moneyline + spread + totals, decimal odds

### 3. DraftKings
- URL: `https://sportsbook-nash.draftkings.com/api/sportscontent/dkusnj/v1/leagues/42648.json`
- Nash mobile API, no key, NBA league ID = 42648
- American odds, all markets

### 4. SBR (Historical closing lines)
- URL: `https://www.sportsbookreview.com/betting-odds/nba-basketball/money-line/?date=YYYY-MM-DD`
- Parses __NEXT_DATA__ JSON. Works for any date 2007+.
- Best for CLV calculation (closing lines)

## REMOVED: The Odds API
- `the-odds-api.com` has been ELIMINATED — quota exhausted, paid service
- Do NOT use `ODDS_API_KEY` in any new code
- `predict_today.py` has ODDS_API_KEY hardcoded to "" (disabled)

## Sharp Reference Protocol
- Pinnacle (ActionNetwork book_id=123) = sharpest market reference
- No-vig formula: imp_h = 1/dec_h, imp_a = 1/dec_a, nv_h = imp_h / (imp_h + imp_a)
- ActionNetwork vig on DraftKings NBA: ~4.5-5.0% overround
- Sharp signal: money% diverges from ticket% by 15%+ = sharp vs public disagreement
