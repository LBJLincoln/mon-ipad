# Nomos42 -- r/sportsbook Post

> **Status:** PUBLICATION-READY | Updated: 2026-04-01
> **Subreddit:** r/sportsbook
> **Tone:** Results-focused, practical, no hype -- this audience detects BS instantly
> **Warning:** r/sportsbook is skeptical of model posts. Lead with verified results, not architecture.

---

**Title:** 19-week walk-forward NBA model results: 0.224 Brier, 934 games. Sharing methodology and what actually works.

**Body:**

Posting verified walk-forward results from our NBA prediction model over 19 weeks of the 2025-26 season. Not cherry-picked backtests -- these are true out-of-sample predictions made before game time.

**The numbers**

- Walk-forward Brier score: 0.22447 (934 games, 19 weeks)
- Best single-run Brier: 0.21570 (different validation, Colab GPU)
- For comparison: average sportsbook implied Brier is roughly 0.25
- Models tested: 11 (XGBoost, CatBoost, LightGBM, Extra-Trees, ensemble variants)
- Features: 6,253 raw features narrowed to 110-200 via genetic selection

**What the model actually uses**

46 feature categories including:
- Standard: team stats, player stats, pace, efficiency ratings
- Interesting: rest/travel patterns, back-to-back effects, altitude adjustment
- Advanced: shot chart zones, lineup combination effects, drive-to-rim frequency, passing network metrics, play-type points-per-possession

The model trains on all available historical data up to the prediction date. No future leakage. Feature selection is done via genetic algorithms running on 6 separate "evolution islands" 24/7.

**Simulated betting results**

We run a full-season backtest across 994 games with multiple strategy variants. The honest summary:

- 20 out of 26 strategies survived (6 eliminated for consistent losses)
- Best performer: full Kelly on the best model turned $100 into $302K (yes, that is full Kelly -- extremely aggressive and not recommended for real money)
- Most realistic strategy: half Kelly turned $100 into $128K with a 16.1 Sharpe
- Conservative approaches: $100 to $4.5K-$23K range

Before anyone asks: no, these are not real money results. This is backtested on the 2025-26 season with live odds data. We are sharing the methodology, not selling picks.

**What actually moves the needle**

1. Feature selection > model tuning. Dropping from 200 random features to 110 selected features improved Brier by 0.011. That is enormous.

2. Ensemble disagreement is a signal. When our 11 models disagree significantly on a game, we bet smaller or skip. When they converge, the edge is larger.

3. Rest and travel matter more than most people think. Back-to-back games, especially with cross-timezone travel, create consistent edges that the market underprices.

4. Line movement timing matters. Our odds snapshot is taken at a fixed time. Earlier lines have more edge than lines close to tip-off.

5. Totals and spreads have different difficulty. Our model is meaningfully better at spreads than totals. If you are building a model, start with sides.

**What does not work**

- Pure momentum strategies (-72% ROI before elimination)
- Betting only totals (-97% ROI)
- Betting everything with max Kelly (-100% ROI, obviously)
- Ignoring the vig -- the market is efficient enough that you need genuine edge, not just a good model

**The tools**

The system is called Nomos42. Open source.
- Repository: github.com/LBJLincoln/mon-ipad
- Daily predictions posted to Telegram: @Nomos42Bot
- Dashboard: nomos-dashboard.vercel.app

We post daily predictions with confidence levels. Track record is public and verifiable.

Not selling anything. Building in public. Feedback from experienced bettors is genuinely valuable to us.

---

*Posting guidelines: DO NOT hype. DO NOT promise profits. DO NOT link to paid products. r/sportsbook respects verified track records and punishes marketing. Engage substantively with skeptics -- they are usually right about something.*
