# Nomos42 -- Product Hunt Launch

> **Status:** PUBLICATION-READY | Updated: 2026-04-01
> **Format:** Product Hunt listing -- tagline, description, FAQ, maker comment
> **Category:** Artificial Intelligence, Data Science, Sports

---

## Listing Details

**Product Name:** Nomos42

**Tagline:** Open-source NBA prediction AI that beats the market -- 0.215 Brier vs 0.25 average

**Topics:** Artificial Intelligence, Machine Learning, Sports Analytics, Open Source, Quantitative Finance

**Thumbnail text suggestion:** "6,253 features. 6 evolution islands. 5 AI traders. $20/month."

---

## Description

### What is Nomos42?

Nomos42 is an autonomous NBA prediction engine that uses genetic evolution and Karpathy's autoresearch pattern to outperform sportsbook markets. It achieves a 0.21570 Brier score -- 14% better than the approximately 0.25 market average -- while running on $20/month of free-tier infrastructure.

### How does it work?

**Feature Engine (v3.1)**
46 categories of NBA data generating 6,253 raw features per game. Categories span team performance, player statistics, shot chart zones, lineup combinations, rest/travel effects, drive-to-rim metrics, passing networks, and play-type points-per-possession.

**Genetic Evolution**
6 HuggingFace evolution islands run genetic algorithms 24/7. Each island specializes differently: exploitation, exploration, extra-trees, CatBoost, LightGBM, and wide search. Populations of 30-50 models evolve independently with periodic cross-island migration.

**11 Competing Models**
XGBoost, CatBoost, LightGBM, Extra-Trees, TabICL, and ensemble variants. Each model uses a genetically-selected subset of 110-200 features from the 6,253 pool.

**5-AI Trading Floor**
Five AI agents powered by Gemini (Google), Claude (Anthropic), Codex (OpenAI), Grok (xAI), and OpenRouter compete head-to-head. Each agent independently selects models, strategies, and Kelly-criterion bet sizing per game.

**11 Autonomous Departments**
Research, Engineering, Evolution, Betting, Evaluation, Infrastructure, Political Alpha, Creative, Communication, Business, and Finance -- each running a Karpathy loop (5-minute autonomous cycles of mutate, measure, keep-or-revert). A Guardian Orchestrator cross-pollinates wins every 4 hours.

### Key Results

| Metric | Value |
|--------|-------|
| Best Brier score | 0.21570 (TabICL, 110 features) |
| Walk-forward Brier | 0.22447 (934 games, 19 weeks) |
| Market average Brier | ~0.25 |
| Trading Floor leader | Codex: $100 to $302,155 |
| Best Sharpe ratio | 16.148 (Gemini) |
| Features | 6,253 raw across 46 categories |
| Models competing | 11 |
| Active strategies | 20 (6 eliminated) |
| Infrastructure cost | $20/month |
| Evolution islands | 6, running 24/7 |

### Beyond NBA

**Political Alpha:** 22 signal categories with 743 features scanning executive orders, FEC donations, enforcement actions, insider trading patterns, and foreign sovereign wealth fund activity to generate ETF trading signals.

**AI Art (RGWA):** Autonomous generative AI art system with quality scoring and curation.

**Dashboard Hub:** Live visualization of all systems at nomos-dashboard.vercel.app.

---

## Pricing

| Tier | Price | Includes |
|------|-------|----------|
| Free | $0/mo | Daily predictions via Telegram @Nomos42Bot |
| API | $19/mo | Programmatic access to predictions |
| Pro | $49/mo | All 11 models + confidence intervals |
| Trading Floor | $149/mo | Full agent competition + strategy signals |

---

## FAQ

**Q: Is this real money or backtested?**
A: The Trading Floor results ($302K from $100) are backtested on the full 2025-26 NBA season using live historical odds. Walk-forward results (0.22447 Brier across 934 games) are true out-of-sample predictions made before game time.

**Q: What is a Brier score?**
A: The Brier score measures prediction accuracy for probabilistic forecasts. It ranges from 0 (perfect) to 1 (worst). Sportsbook lines imply an average Brier score of approximately 0.25. Our 0.215 means we are 14% more accurate than the market baseline.

**Q: How can this run on $20/month?**
A: Free-tier everything. HuggingFace Spaces for 24/7 evolution (CPU), Kaggle P100 for GPU bursts (free 9-hour sessions), Google Colab T4 for TabICL experiments, Supabase for data storage, Vercel for the dashboard. The VM pilot (1 vCPU, 969 MB RAM) does zero ML training -- it only orchestrates.

**Q: Is it open source?**
A: Yes. Repository: github.com/LBJLincoln/mon-ipad. The code, feature engine, evolution configs, and Trading Floor logic are all public and verifiable.

**Q: What is the Karpathy autoresearch pattern?**
A: A method inspired by Andrej Karpathy: define a clear metric (Brier score), give the system a 5-minute experiment budget per iteration, and let it run autonomously. Our system runs approximately 12 iterations per hour on Kaggle GPU.

---

## First Maker Comment

Hi Product Hunt! I am the maker of Nomos42.

The origin story: I wanted to know if an AI system, given enough autonomy and a clear metric, could beat professional sportsbooks at NBA prediction. Eighteen months later, it can -- with a 0.215 Brier score versus the 0.25 market average.

The most surprising finding: infrastructure cost does not correlate with model quality. Our entire system runs on free tiers ($20/month total) and outperforms what many well-funded teams achieve. The key is the autonomous evolution loop -- 6 islands of genetic algorithms running 24/7, each evolving feature selection and model hyperparameters independently.

The most interesting technical decision: instead of building one optimized model, we built a Trading Floor where 5 AI agents from different providers (Gemini, Claude, Codex, Grok, OpenRouter) compete against each other. Each agent sees the same predictions but makes independent strategy decisions. The emergent behavior is more informative than any single agent.

What I am most excited about: the 11-department Karpathy loop architecture. Each department -- from Research to Finance -- runs its own 5-minute autonomous improvement cycle. A Guardian Orchestrator cross-pollinates wins between departments. This is the closest thing I have built to an organization that improves itself.

Would love your feedback. Try the daily predictions via @Nomos42Bot on Telegram, or explore the dashboard at nomos-dashboard.vercel.app.

---

*Launch guidelines:*
- *Schedule for 12:01 AM PT on a Tuesday*
- *Have 5-10 supporters ready to upvote and comment in first hour*
- *Respond to every comment within 30 minutes*
- *Prepare a GIF showing the Trading Floor visualization*
- *Prepare a 60-second demo video of the dashboard*
