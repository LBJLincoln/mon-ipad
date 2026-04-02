# Nomos42 -- r/datascience Post

> **Status:** PUBLICATION-READY | Updated: 2026-04-01
> **Subreddit:** r/datascience
> **Flair:** Project
> **Tone:** Technical peer discussion, humble but data-rich, inviting critique

---

**Title:** We built an autonomous NBA prediction system using genetic evolution + Karpathy's autoresearch pattern. Brier score: 0.215 vs 0.25 market average. Here is what we learned.

**Body:**

Hey r/datascience,

We have been working on Nomos42, an open-source NBA prediction engine, for about 18 months. Sharing because the architecture might be interesting to this community, and we are genuinely looking for feedback on our approach.

**The core metric**

Our all-time record Brier score is 0.21570, achieved with TabICL (a tabular in-context learning model) on 110 selected features using a Colab T4 GPU. For context, the average implied Brier score from sportsbook lines is approximately 0.25, so we are operating roughly 14% better than market.

Walk-forward validation across 934 games over 19 weeks gives us 0.22447 average Brier -- this is on a Kaggle P100 using tree ensembles only (no TabICL, since P100 does not support it well).

**Architecture overview**

The system is built around Andrej Karpathy's autoresearch pattern: give the AI a clear metric, a 5-minute experiment budget, and let it iterate autonomously.

Feature engineering:
- 46 feature categories, 6,253 raw features per game (engine v3.1)
- Categories include: team performance, player stats, pace/efficiency, rest days, travel distance, shot charts, lineup combinations, drive-and-rim metrics, passing networks, play-type PPP
- Hard cap of 200 features per model (genetic selection from the 6,253 pool)

Model zoo:
- 11 models compete: XGBoost, CatBoost, LightGBM, Extra-Trees, TabICL, and ensemble variants
- Each model is independently evolved via genetic algorithms
- Best single model: XGBoost at +$322/bet average edge

Evolution infrastructure:
- 6 HuggingFace Spaces ("islands") run genetic algorithms 24/7 on free CPU tier
- Each island has a different specialization: exploitation, exploration, extra-trees specialist, catboost specialist, lightgbm specialist, wide search
- Population sizes: 30-50 individuals per island
- Mutation rates: 0.08-0.18 (adaptive, capped at 0.15 on most islands)
- GPU bursts on Kaggle P100 (free 9h sessions) and Colab T4 for TabICL experiments
- Karpathy loop rate: approximately 12 iterations/hour

**The interesting part: Trading Floor simulation**

We run 5 AI agents (Gemini, Claude, Codex, Grok, OpenRouter) in a simulated trading floor. Each agent sees all available predictions and independently decides:
- Which model to use per game
- Which betting strategy to apply (20 active strategies)
- How much to wager (Kelly criterion variants)
- Which bet categories to target (moneyline, spread, totals, team totals, etc.)

After 994 games (full 2025-26 season backtest), iteration 44, generation 5,984:

| Agent | Style | Bankroll (from $100) | Sharpe |
|-------|-------|---------------------|--------|
| Codex | Aggressive, full Kelly | $302,155 | 8.12 |
| Gemini | Analytical, half Kelly | $128,288 | 16.15 |
| Grok | Contrarian | $23,401 | 11.74 |
| OpenRouter | Diversified | $21,987 | 10.02 |
| Claude | Conservative | $4,536 | 9.00 |

Yes, the Codex numbers look insane -- full Kelly on a model with genuine edge compounds aggressively. The Sharpe ratios are more meaningful indicators. Gemini's 16.15 Sharpe with $128K bankroll is the most interesting result to us.

**What we learned**

1. Feature selection matters more than model architecture. Going from 200 random features to 110 genetically-selected features dropped Brier from 0.226 to 0.215.

2. Island model evolution prevents premature convergence. Having 6 islands with different mutation rates and specializations maintains genetic diversity.

3. Walk-forward validation is non-negotiable. Our Colab Brier (0.215) uses a different validation scheme than the walk-forward (0.224). The gap is real and humbling.

4. CPU-only tree models are surprisingly competitive. Our fleet average on free HuggingFace CPU is 0.222 Brier. TabICL on GPU only adds approximately 0.007 improvement.

5. Strategy evolution is as important as model evolution. 6 out of 26 strategies have been eliminated for consistently negative ROI. The surviving 20 are meaningfully different from where we started.

**Infrastructure cost: $20/month**

The entire system runs on free tiers: HuggingFace Spaces (CPU), Kaggle (GPU), Colab (GPU), Supabase (data), Vercel (dashboard). The VM pilot is 1 vCPU with 969 MB RAM -- zero ML training on it.

**Open questions we are wrestling with**

- How to close the gap between 0.215 and our target of 0.200 (the Montrucchio benchmark)
- Whether TabICL's advantage over tree ensembles justifies the GPU dependency
- How to better detect regime changes mid-season (injuries, trades, rest patterns)
- Whether the Trading Floor agent diversity actually produces alpha vs. a single optimized strategy

**Links**

- Repository: github.com/LBJLincoln/mon-ipad
- Dashboard: nomos-dashboard.vercel.app
- Evolution islands: nomos42-nba-quant.hf.space

Happy to share more details on any aspect. Genuinely interested in this community's take on the approach.

---

*Posting guidelines: Do not self-promote in title. Frame as discussion/learnings. Engage with every comment. Cross-post to r/MachineLearning with [P] tag if well-received.*
