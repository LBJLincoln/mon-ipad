# Nomos42 -- Hacker News (Show HN) Post

> **Status:** PUBLICATION-READY | Updated: 2026-04-01
> **Format:** Show HN submission + top-level comment with details
> **Tone:** Technical, understated, intellectually honest. HN hates hype.

---

**Title:** Show HN: Nomos42 -- Autonomous NBA prediction engine using genetic evolution and Karpathy's autoresearch pattern

**URL:** github.com/LBJLincoln/mon-ipad

---

**Top-level comment (post immediately after submission):**

Hi HN,

Nomos42 is an autonomous system for NBA game prediction. The core idea is simple: apply Karpathy's autoresearch pattern (clear metric, 5-minute experiment budget, iterate forever) to sports prediction.

The interesting technical bits:

**Genetic feature selection at scale.** We have 6,253 raw features across 46 categories (team stats, player metrics, shot charts, lineup effects, rest/travel, pace, etc.). Each model uses a genetically-selected subset of 110-200 features. Six "evolution islands" on HuggingFace Spaces run different selection strategies 24/7 -- exploitation, exploration, model-specific specialists, and wide search. This island model is borrowed from evolutionary biology: isolated populations evolve independently, with periodic migration preventing premature convergence.

**Multi-agent trading floor.** Five AI agents (Gemini, Claude, Codex, Grok, OpenRouter) each independently decide which model to use, which strategy to apply, and how much to bet per game. After 994 games: Codex reached $302K from $100 (full Kelly, extremely aggressive), Gemini reached $128K (half Kelly, 16.1 Sharpe). The agent diversity reveals strategy-level insights that single-agent optimization misses.

**Department Karpathy loops.** The system has 9 departments (research, engineering, evolution, product, business, evaluation, infra, finance, cross-repo), each running an autonomous 5-minute loop: mutate something, measure the result, keep or revert. A Guardian Orchestrator cross-pollinates wins between departments every 4 hours.

**Results.** Best Brier score: 0.21570 (TabICL on Colab T4). Walk-forward over 934 games: 0.22447. Market sportsbook average is roughly 0.25. The gap between our best (0.215) and our walk-forward (0.224) tells us there is real overfitting we have not fully solved.

**The cheapskate infrastructure.** Everything runs on free tiers. Six HuggingFace Spaces for evolution (CPU), Kaggle P100 for GPU bursts (9h sessions), Colab T4 for TabICL, Supabase for data, Vercel for dashboard. Total cost: $20/month. The VM (1 vCPU, 969 MB RAM) does zero ML training -- it just orchestrates.

Beyond NBA, we apply the same architecture to political signal detection (22 categories, 743 features, ETF trading signals) and AI art generation (RGWA).

Dashboard: nomos-dashboard.vercel.app
Telegram bot with daily predictions: @Nomos42Bot

Happy to discuss the evolutionary architecture, feature engineering, or the multi-agent competition design.

---

*Posting guidelines for HN:*
- *Submit between 8-10 AM ET on a weekday (Tuesday-Thursday optimal)*
- *Do not ask for upvotes*
- *Respond to every comment substantively and quickly (first 2 hours are critical)*
- *Be honest about limitations: overfitting gap, backtest vs live, full Kelly unrealism*
- *If asked "why not just use [simple approach]?" -- answer honestly, do not be defensive*
- *HN loves: infrastructure efficiency, intellectual honesty, novel architecture*
- *HN hates: marketing language, claims without evidence, "disrupting" anything*
