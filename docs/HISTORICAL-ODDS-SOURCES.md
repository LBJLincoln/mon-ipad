# Historical NBA Odds — Complete Source Catalog
> Researched: 2026-03-28 | Focus: European bookmakers (Unibet, ParionsSport/FDJ, Betclic, Winamax)

---

## TL;DR — Top 3 Immediate Actions

1. **SBR Online archives (FREE, no login)** — Download all seasons 2007–2023 right now as XLS. Covers spreads, totals, moneylines. Best free bulk source.
2. **Kaggle: cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024 (FREE)** — Kaggle CLI download, 2007–2025, closing lines only, clean CSV. Complements our existing `alexismoret6/nba-2025-26-odds`.
3. **The Odds API (FREE tier, 500 req/mo)** — Covers `unibet_fr`, `betclic_fr`, `parionssport_fr`, `winamax_fr`. Free tier = current/recent odds only. Historical requires paid plan (~$50/mo). Use free tier now to start collecting from March 2026 forward.

---

## 1. Free, No-Registration, Bulk Downloads

### 1.1 SportsBookReviewsOnline (SBR) Archives
- **URL**: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba/nbaoddsarchives.htm
- **Seasons**: 2007–08 through ~2022–23 (note: site states archive will not be updated further)
- **Bookmakers**: Aggregated from various offshore + Nevada land-based sportsbooks (includes Pinnacle-style lines, Bookmaker.eu, BetOnline-era data)
- **Bet types**: Opening + closing spreads, totals (O/U), moneylines, 2nd half lines
- **Format**: Microsoft Excel (.XLS) per season, also HTML view
- **License**: Free to download, no login required
- **Note**: This is the gold standard free source. Used by most academic papers on NBA betting. Pre-scraped GitHub repos (see 4.1) also bundle this data 2011–2021.

### 1.2 Kaggle: NBA Betting Data Oct 2007–Jun 2025
- **URL**: https://www.kaggle.com/datasets/cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024
- **Seasons**: 2007–08 through 2024–25 (18 seasons, regular season + playoffs)
- **Bookmakers**: SBR Online data (2007–Jan 2023) + ESPN data (Jan 2023–Jun 2025)
- **Bet types**: Spreads (full + 2H), totals (full + 2H), moneylines (closing lines only)
- **Format**: CSV inside ZIP (~633 KB)
- **Access**: `kaggle datasets download cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024`
- **Note**: 2H spreads/totals are MISSING for ESPN-era data (post-Jan 2023). This is the most complete free closing-line dataset available.

### 1.3 Kaggle: NBA Historical Stats and Betting Data (Hallmark)
- **URL**: https://www.kaggle.com/datasets/ehallmar/nba-historical-stats-and-betting-data
- **Seasons**: Through 2018 (older dataset, last modified Aug 2018)
- **Bookmakers**: Not specified — likely SBR-sourced
- **Bet types**: Betting odds + box score stats combined
- **Format**: ZIP (~38 MB)
- **Downloads**: 6,448 — well-validated community dataset
- **Access**: `kaggle datasets download ehallmar/nba-historical-stats-and-betting-data`

### 1.4 Kaggle: NBA Odds and Scores (Qiu)
- **URL**: https://www.kaggle.com/datasets/erichqiu/nba-odds-and-scores
- **Seasons**: Most of the past decade (through ~2020, last updated May 2020)
- **Bookmakers**: Not fully documented
- **Format**: ZIP (~1.96 MB), 2,331 downloads
- **Access**: `kaggle datasets download erichqiu/nba-odds-and-scores`

### 1.5 Kaggle: NBA Odds (Giardini/OddsPortal)
- **URL**: https://www.kaggle.com/datasets/giardinidavide/nba-odds
- **Source**: OddsPortal scrape
- **Seasons**: 2010–11 through ~2021–22
- **Bookmakers**: Multiple bookmakers as listed on OddsPortal (includes European books)
- **Bet types**: Asian Handicaps + Over/Unders (the ones closest to 50/50 = sharpest market)
- **GitHub source**: https://github.com/DavideGiardini/OddsPortal-WebScraper
- **Note**: This is the only free Kaggle dataset with multi-bookmaker European odds via OddsPortal scraping.

### 1.6 Kaggle: NBA Betting Lines
- **URL**: https://www.kaggle.com/datasets/thedevastator/uncovering-hidden-trends-in-nba-betting-lines-20
- **Seasons**: Recent (2020+)
- **Access**: `kaggle datasets download thedevastator/uncovering-hidden-trends-in-nba-betting-lines-20`

---

## 2. European Bookmakers (Unibet, ParionsSport/FDJ, Betclic, Winamax)

### 2.1 The Odds API — EU Bookmakers
- **URL**: https://the-odds-api.com/
- **Bookmakers confirmed for NBA**:
  - `unibet_fr` (France)
  - `unibet_it` (Italy)
  - `unibet_nl` (Netherlands)
  - `unibet_se` (Sweden)
  - `betclic_fr` (France)
  - `parionssport_fr` (France — FDJ)
  - `winamax_fr` (France)
  - `winamax_de` (Germany)
  - Plus: 1xBet, Pinnacle (via EU region), Betsson
- **Bet types**: Moneyline (h2h), spreads, totals; props from May 2023+
- **Free tier**: 500 credits/month — covers CURRENT odds only, not historical
- **Historical tier**: Paid only. Historical data from June 2020, snapshots every 5–10 min
- **Pricing for historical**: ~$50+/mo starting tier (exact pricing requires account signup)
- **Start date for EU books**: June 6, 2020 (earlier data not available)
- **Action**: Sign up for free key → start collecting `parionssport_fr`, `unibet_fr`, `betclic_fr`, `winamax_fr` from today. After 1–2 seasons, valuable proprietary dataset.

### 2.2 OddsPortal — European Bookmaker Aggregator
- **URL**: https://www.oddsportal.com/basketball/usa/nba/results/
- **Bookmakers**: Unibet, Betclic, Winamax, ParionsSport, bet365, Pinnacle, William Hill, 1xBet, and ~50+ others
- **Seasons**: 2008–09 through 2025–26 (browsable)
- **Download**: NO direct download — web-only interface
- **Bet types**: ML, spreads, O/U, Asian Handicap, 1st quarter, halftime
- **Scraping**: Possible via OddsHarvester (see section 4.2) — can filter by specific bookmaker including `Betclic.fr`
- **Note**: This is the most comprehensive source for European bookmaker NBA odds historically, but requires scraping.

### 2.3 ParionsSport / FDJ
- **URL**: https://www.enligne.parionssport.fdj.fr/paris-basketball/usa/nba
- **Historical data**: NOT available publicly. No API, no downloads.
- **Current odds**: Web interface only
- **Workaround**: The Odds API `parionssport_fr` endpoint (paid historical, free current)
- **Note**: In March 2026, Unibet merged operations with ParionsSport in France. Their odds may be converging.

### 2.4 Unibet France
- **URL**: https://www.unibet.fr/paris-basketball
- **Historical data**: NOT available publicly via Unibet directly
- **Workaround**: The Odds API `unibet_fr` (paid historical from June 2020)
- **Note**: OddsPortal tracks Unibet historically — scrapable via OddsHarvester

### 2.5 Winamax + Betclic
- **Historical data**: NOT available directly from bookmakers
- **Workaround**: The Odds API `winamax_fr`, `betclic_fr` (paid historical from June 2020)
- **Community tool**: `pretrehr/Sports-betting` (GitHub) has live scrapers for Unibet, Betclic, Winamax, ParionsSport — but for current odds + arbitrage, not historical bulk.

---

## 3. Paid / Commercial Sources

### 3.1 The Odds API — Historical Plan
- **URL**: https://the-odds-api.com/historical-odds-data/
- **Coverage**: NBA from June 2020, snapshots every 5–10 min
- **EU books included**: unibet_fr, betclic_fr, parionssport_fr, winamax_fr
- **Pricing**: Historical queries cost 10x standard credits. Paid tiers start ~$50/mo
- **Best for**: Building a proprietary European bookmaker NBA odds dataset from 2020–present

### 3.2 BettingIsCool Pinnacle API
- **URL**: https://api.bettingiscool.com/
- **Coverage**: Pinnacle only, NBA from 2021, 2.7B+ odds records, 46 sports
- **Bet types**: Moneylines, spreads, totals, alternate lines, player props (from Mar 2026), futures
- **Format**: REST API, JSON, clean endpoints, no pagination
- **Pricing**: Not public — requires signup
- **Value**: Pinnacle = sharpest market in the world. Closing line value (CLV) analysis requires Pinnacle. Enterprise tier includes player props history.
- **Note**: Not for European retail books (Unibet/ParionsSport), but essential for calibrating model vs true market.

### 3.3 SportsAPIs.dev — Historical Odds
- **URL**: https://sportsapis.dev/historical-odds
- **Coverage**: Pinnacle + Bet365 + 40+ books
- **NBA history**: 5–10 years depending on book
- **Pricing**: $200–500/mo for multi-year per sport; $500–2000 one-time bulk CSV dump
- **Free tier**: None (30–90 days only on lower paid plans)
- **Use case**: One-time bulk purchase if budget allows

### 3.4 OddsPapi
- **URL**: https://oddspapi.io/
- **Free tier**: 250 requests including Pinnacle, Singbet, 1xBet, Betfair Exchange
- **Coverage**: 350+ bookmakers
- **NBA**: Yes
- **Pricing**: Per-request, more transparent than The Odds API
- **Sharp books on free**: YES — Pinnacle + Betfair Exchange in free tier
- **Action**: Sign up for free to get Pinnacle NBA current odds (useful for CLV analysis today)

### 3.5 OddsBase
- **URL**: https://oddsbase.net/nba-historical-odds
- **Coverage**: 16 years of NBA history, multiple bookmakers (Bet365, Pinnacle, Unibet, William Hill, 1xBet)
- **Format**: Web table only — NO download, NO API
- **Pricing**: Requires paid subscription for access
- **Verdict**: Web-browsable only — not useful for bulk ML training data

### 3.6 OddsWarehouse
- **URL**: https://www.oddswarehouse.com/products/nba-historical-sports-betting-odds
- **Coverage**: NBA 2006–2025
- **Format**: Instant download after purchase
- **Pricing**: One-time purchase per season or full database
- **Verdict**: Paid only, skip unless budget available

### 3.7 BigDataBall
- **URL**: https://www.bigdataball.com/datasets/nba-data/
- **Format**: Excel, game-by-game, box scores + betting odds
- **Pricing**: Paid subscription
- **Verdict**: Skip — SBR archives are free equivalents

---

## 4. Scraping Tools

### 4.1 flancast90/sportsbookreview-scraper (Pre-scraped dataset)
- **URL**: https://github.com/FinnedAI/sportsbookreview-scraper
- **What**: SBR scraper + pre-scraped dataset bundled in `/data` folder
- **Pre-scraped years**: NBA 2011–2021
- **Sports**: NFL, NBA, NHL, MLB
- **Note**: Data folder = immediate free download without scraping. Best for quick historical bulk.

### 4.2 OddsHarvester (OddsPortal scraper)
- **URL**: https://github.com/jordantete/OddsHarvester
- **What**: CLI app to scrape oddsportal.com — historical + upcoming odds
- **Sports**: Multi-sport including basketball/NBA
- **Bookmaker filter**: Can filter for specific bookmakers including `Betclic.fr`
- **Output**: JSON or CSV, local or S3
- **European books**: OddsPortal carries Unibet, Betclic, Winamax, ParionsSport historically
- **Action**: Run on Kaggle (free GPU session not needed — pure scraping) to pull 2008–present NBA odds with European bookmaker breakdown
- **Caution**: OddsPortal ToS prohibits automated scraping — use respectfully with delays

### 4.3 pretrehr/Sports-betting (French bookmaker live scrapers)
- **URL**: https://github.com/pretrehr/Sports-betting
- **What**: Arbitrage tool with live scrapers for French bookmakers
- **Supported**: Winamax, Betclic, Unibet, ParionsSport, Bwin, Pinnacle, PokerStars
- **Use case**: LIVE odds only (for arbitrage) — not historical bulk
- **Verdict**: Useful for collecting current odds going forward, not historical backfill

### 4.4 webscraping-oddsportal (Python package)
- **URL**: https://github.com/scooby75/webscraping-oddsportal
- **Sports**: Soccer, basketball, esports, darts, tennis, baseball, rugby, American football, hockey
- **Functions**: Historical odds, current season, upcoming games
- **Note**: Alternative to OddsHarvester for OddsPortal scraping

---

## 5. APIs with Free NBA Odds (Current Only)

### 5.1 The Odds API Free Tier
- 500 credits/month, current odds only
- EU bookmakers: unibet_fr, betclic_fr, parionssport_fr, winamax_fr
- Sign up: https://the-odds-api.com/

### 5.2 OddsPapi Free Tier
- 250 requests, includes Pinnacle + Betfair Exchange
- Best free source for sharp-line CLV analysis
- Sign up: https://oddspapi.io/

### 5.3 Betfair Exchange Historical Data
- **URL**: https://historicdata.betfair.com/
- Requires Betfair account (free to open)
- Free data available at 1-minute frequency (no volume)
- Paid data includes full price ladder + volume
- Format: .bz2 compressed files
- NBA availability: Yes — exchange markets since 2016
- Parsing tool: https://github.com/williamdevena/Betfair_historical_data_exploration_and_analysis
- **Value**: Exchange odds = crowd wisdom price (no margin), excellent for model calibration

---

## 6. What Does NOT Exist (Negative Findings)

- **football-data.co.uk equivalent for NBA**: Does NOT exist. No site offers the same free CSV-per-season format for NBA that football-data.co.uk provides for soccer.
- **ParionsSport/FDJ historical bulk download**: NOT publicly available. Only accessible via The Odds API (paid, from June 2020) or OddsPortal scraping.
- **Winamax historical NBA data**: NOT publicly available in bulk. Same workarounds.
- **Pinnacle free historical bulk**: NOT free. BettingIsCool API from 2021, paid. OddsPapi free tier = current only.
- **DonBest free API**: Requires paid API token. Python wrapper exists (mc-buckets/donbest.py) but needs auth.
- **coteur.com NBA data**: Site exists for soccer but no NBA coverage found.

---

## 7. Recommended Action Plan

### Immediate (free, this week)

1. **Download SBR archives** (2007–2023 XLS):
   ```
   # Visit: https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba/nbaoddsarchives.htm
   # Download each season XLS manually (no login required)
   # Or use: https://github.com/FinnedAI/sportsbookreview-scraper (pre-scraped 2011-2021)
   ```

2. **Download best Kaggle dataset** (2007–2025 closing lines):
   ```bash
   kaggle datasets download cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024
   ```

3. **Sign up for OddsPapi free tier** (250 req/mo, Pinnacle + sharp books):
   - Start collecting daily Pinnacle NBA closing lines for CLV benchmarking

4. **Sign up for The Odds API free tier** (500 credits/mo, EU books):
   - Start collecting unibet_fr, betclic_fr, parionssport_fr, winamax_fr daily

### Short-term (1–2 weeks)

5. **Run OddsHarvester on Kaggle** to scrape OddsPortal historical NBA odds 2008–2025 with European bookmaker breakdown (Betclic, Unibet, Winamax visible on OddsPortal)

6. **Join Betfair** and access free 1-min exchange data for NBA since 2016 (no-margin true probability)

### Medium-term (if budget available)

7. **The Odds API paid plan** (~$50/mo): Unlock `parionssport_fr` + `unibet_fr` historical from June 2020. 5+ seasons of French market data.

---

## 8. Column Reference (SBR Format)

| Column | Meaning |
|--------|---------|
| Date | Game date |
| VH | V=away (visitor), H=home |
| Team | Team name |
| Open | Opening spread/total |
| Close | Closing spread/total |
| ML | Moneyline (American format) |
| 2H | Second half line |
| Final | Final score |

---

## 9. Our Existing Dataset

- **alexismoret6/nba-2025-26-odds**: 1,128 games, 2025–26 season, BetMGM + SBR closing lines
- **Kaggle**: https://www.kaggle.com/datasets/alexismoret6/nba-2025-26-odds
- **Gap**: No European bookmaker columns. No pre-2025-26 history in this dataset.

---

*Last updated: 2026-03-28*
