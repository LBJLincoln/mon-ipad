---
name: Historical NBA Odds Sources
description: Complete catalog of free and paid historical NBA odds sources, with focus on European bookmakers (Unibet, ParionsSport/FDJ, Betclic, Winamax)
type: project
---

Researched 2026-03-28. Full doc at /home/termius/mon-ipad/docs/HISTORICAL-ODDS-SOURCES.md

## Best Free Sources (immediate action)

**SBR Online Archives** — sportsbookreviewsonline.com/scoresoddsarchives/nba/
- 2007–2023, XLS per season, no login, spreads + totals + ML + 2H lines
- Pre-scraped bundle: github.com/FinnedAI/sportsbookreview-scraper (2011-2021)

**Kaggle: cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024**
- 2007–2025, 18 seasons, CSV, closing lines only (SBR + ESPN sources)
- `kaggle datasets download cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024`

**Kaggle: giardinidavide/nba-odds**
- OddsPortal scrape, 2010–2022, Asian Handicaps + O/U, multiple European books

## European Bookmaker Access

**The Odds API** (the-odds-api.com) covers:
- `unibet_fr`, `unibet_it`, `unibet_nl`, `unibet_se`
- `betclic_fr`, `parionssport_fr`, `winamax_fr`, `winamax_de`
- Free tier = 500 credits/mo, CURRENT ODDS ONLY
- Historical (June 2020+) = paid tier ~$50/mo
- ACTION: Sign up free now to start collecting French market odds daily

**OddsPortal** (oddsportal.com/basketball/usa/nba/results/)
- Historical 2008–2026, shows Unibet, Betclic, Winamax, ParionsSport
- No download — must scrape via OddsHarvester (github.com/jordantete/OddsHarvester)
- Can filter by bookmaker including Betclic.fr

**pretrehr/Sports-betting** (GitHub)
- Live scrapers for Winamax, Betclic, Unibet, ParionsSport — CURRENT only

## Sharp Line / Calibration Sources

**OddsPapi** (oddspapi.io)
- Free: 250 req/mo, includes Pinnacle + Betfair Exchange (no-margin sharp lines)
- Best free source for CLV benchmarking

**BettingIsCool** (api.bettingiscool.com)
- Pinnacle only, 2021+, 2.7B records, paid API

**Betfair Exchange** (historicdata.betfair.com)
- Free 1-min data, requires free Betfair account, NBA since 2016
- Parser: github.com/williamdevena/Betfair_historical_data_exploration_and_analysis

## What Does NOT Exist

- No football-data.co.uk equivalent for NBA (free per-season CSVs with European books)
- No ParionsSport/Winamax/Betclic historical bulk download
- No Pinnacle free historical bulk (paid only from 2021)

**Why:** Enables market-implied probability features, CLV analysis, and closing line benchmarking. Expected Brier delta -0.003 to -0.004 from implied probability features.
**How to apply:** When asked about odds data sources, betting features, or calibration — this is the definitive reference.
