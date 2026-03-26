---
name: Market Analyst Data Sources
description: File paths and bookmaker reference for NBA market analysis
type: reference
---

## Live Odds Files
- `/home/termius/mon-ipad/data/nba-agent/live-odds.json` — structured odds from Odds API (7 books, 3 markets each)
- `/home/termius/mon-ipad/data/nba-agent/odds-latest.json` — same data, flat array format (both files identical content)
- `/home/termius/mon-ipad/data/nba-agent/latest-picks.json` — model picks with win probs, spreads, totals, player props, Kelly sizing
- `/home/termius/mon-ipad/data/nba-agent/quant-summary.json` — model version info, Brier scores, bankroll state
- `/home/termius/nomos-nba-agent/data/results/crew-market.json` — output target for market reports

## 7 Bookmakers in odds data (as of 2026-03-26)
- pinnacle, betway, unibet, winamax, betclic, pmu, parionssport
- All European-facing books. Pinnacle = sharpest, use as no-vig reference.
- Odds format: decimal European

## Sharp Reference Protocol
- Pinnacle = market consensus sharp line
- No-vig formula: raw1 = 1/dec1, raw2 = 1/dec2, nv1 = raw1/(raw1+raw2)
- Vig on Pinnacle NBA: ~4.7-5.1% overround
- Soft books (Betway, Unibet, Betclic) lag Pinnacle on line moves by 15-30 min
