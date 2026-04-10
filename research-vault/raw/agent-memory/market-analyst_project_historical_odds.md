---
name: Historical odds dataset 2025-26
description: Location, sources and format of the complete 2025-26 NBA historical moneyline dataset
type: project
---

Complete 2025-26 NBA season closing moneylines assembled 2026-03-28.

**File:** `/home/lahargnedebartoli/nomos-nba-agent/data/historical-odds/nba_2025-26_odds.csv`
**Script:** `/home/lahargnedebartoli/nomos-nba-agent/scripts/scrape_season_odds.py`
**Docs:** `/home/lahargnedebartoli/nomos-nba-agent/data/historical-odds/SOURCES.md`

Coverage: 1,128 games, Oct 21 2025 – Mar 28 2026.

| Source | Games | Dates | Format |
|--------|-------|-------|--------|
| mgm_kaggle (Kaggle: caseydurfee/mgm-grand-nba-betting-data) | 808 | Oct 2025–Feb 12 2026 | American ML |
| sbr_scrape (SportsBettingReview.com) | 291 | Feb 19–Mar 28 2026 | American ML |
| local_snapshot_decimal (The Odds API snapshots) | 29 | Mar 15–17 + 28, 2026 | Decimal |

**Why:** SBR scraping was the key discovery. URL:
`https://www.sportsbookreview.com/betting-odds/nba-basketball/money-line/?date=YYYY-MM-DD`
Data is in `<script id="__NEXT_DATA__">` → `props.pageProps.oddsTables[0].oddsTableModel.gameRows[n].oddsViews[n].currentLine.{homeOdds,awayOdds}`.
Rate limit: 2.5s between requests. No auth required. Preferred book: BetMGM (first available).

**How to apply:** Use for Kaggle season backtest (full walk-forward 2025-26), CLV calculation,
and model ROI validation. The Odds API historical endpoint costs $99/mo and is NOT needed.

**All-Star break:** Feb 13–18, 2026 had no NBA games (expected gap in data).

**To extend coverage for playoff games (Apr 2026+):**
```bash
python3 /home/lahargnedebartoli/nomos-nba-agent/scripts/scrape_season_odds.py --source sbr --from-date 2026-04-01 --to-date YYYY-MM-DD
```
