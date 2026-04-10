---
name: Backtest Audit March 2026
description: Three critical bugs found in nba_season_backtest.py that inflated ROI from ~27% to 4,470% and Sharpe from ~3 to 22.91
type: project
---

Audit completed 2026-03-28. Three compounding bugs in `scripts/kaggle/nba_season_backtest.py` made financial results completely unreliable.

**Why:** These bugs were discovered when ROI of 4,470% and Sharpe of 22.91 were flagged as unrealistically high. Full code + data audit confirmed three separate root causes.

**How to apply:** Do not reference $4,570 final bankroll or 902% flat ROI or 22.91 Sharpe in any decision. The 67% win rate and Brier 0.22447 are real. Financial metrics need a clean re-run with all three bugs fixed.

---

## Bug 1 (CRITICAL): Circular Implied-Odds

**Code:** Lines 524-531 in `nba_season_backtest.py`

When real odds CSV key did not match a game (team name normalization failure), code fell back to:
```python
odds_home = 1.0 / (home_prob * 1.05)
```
This derived "market odds" from the model's own probability — the same probability used to measure edge. Result: bets on a 73.5% team at +575 decimal (6.75) which is physically impossible. Edge computed as 396%.

**Fix applied:** `if not odds_home and not odds_away: continue` — hard skip, no fallback.

**Impact:** Inflated ROI from realistic ~14-27% to 4,470%.

---

## Bug 2 (HIGH): Sharpe Wrong Annualization Factor

**Code:** Line 815

Code used `sqrt(252)` (daily annualization) on **weekly** returns. Correct factor is `sqrt(52)`.

**Fix applied:** Changed to `(52 ** 0.5)`.

**Impact:** Inflated Sharpe 2.20x: 22.91 -> 10.4. Even 10.4 is still inflated by Bug 1.

---

## Bug 3 (MEDIUM): Max Drawdown Weekly Snapshots

Drawdown computed from weekly equity snapshots, not per-bet. Jan 9 week shows 4 consecutive losses totaling ~10% intraday drawdown that was invisible.

**Fix applied:** Added per-bet peak/DD update inside the bet loop.

**Impact:** Reported 1.97% DD; true intraday DD estimated 10-15%.

---

## Bug 4 (MEDIUM): ATS/O/U Zero Bets

Zero ATS and O/U bets despite `real_odds_pct = 100%` claim. nba_2025-26_odds.csv lacks `spread` and `total` columns. ATS/O/U code silently skips when those fields are None.

**Fix needed (not yet done):** Augment odds CSV via `scrape_season_odds.py` with spread/total lines.

---

## What IS Real

- **Brier 0.22447** on 19-week walk-forward — legitimate, verified
- **67% win rate** on 227 filtered picks (24% of 934 games) — plausible, needs CLV validation
- **Weekly Brier range 0.167-0.301** — genuine model variance
- **Walk-forward methodology** — sound, no look-ahead bias

## Realistic Financial Expectation

With real market odds, 67% win rate, avg -110 to -120 odds:
- Flat $5/bet, 250 games/season: **$25-75 profit** (2-6% yield on wagered)
- Kelly 2.5% stake: **$100 grows to ~$128** over full season at 4% yield
- NOT $4,570. NOT 4,470% ROI.

## Files

- Verification script: `/home/lahargnedebartoli/mon-ipad/scripts/verify_backtest.py`
- Verified results: `/home/lahargnedebartoli/mon-ipad/data/nba-agent/verified-results.json`
- Updated backtest: `/home/lahargnedebartoli/mon-ipad/data/nba-agent/backtest-results.json`
- Fixed script: `/home/lahargnedebartoli/mon-ipad/scripts/kaggle/nba_season_backtest.py`
