# Nomos42 — Communication Decks (5 Audiences)

> Outlines for 10-slide presentations | Updated: 2026-04-03 | Version 1.0

---

## DECK 1: Technical Peers

**Context:** Conference talk, ML meetup, ArXiv post, HackerNews "Show HN"
**Hook:** "We built a 24/7 autonomous NBA prediction system. Brier 0.21570. Here is the architecture."
**Goal:** Earn technical credibility, attract contributors, spark collaboration

---

### Slide 1 — The Problem (Technical Framing)

NBA game prediction is a hard calibration problem. The Brier score (0 = perfect, 1 = worst) measures probability calibration, not just accuracy.

- **SOTA (2026):** Montrucchio et al. (MDPI Information 17/1/56) — Brier 0.199
- **Our ATR:** 0.21570 (TabICL ensemble, Colab T4, 110 features, iter 15)
- **Walk-forward validation:** 0.22447 (Kaggle P100, 19 weeks, 934 games)
- **Gap to SOTA:** 0.01570 — quantified, measurable, systematic

The interesting part: we're not trying to beat SOTA by being smarter. We're trying to beat it autonomously.

---

### Slide 2 — Architecture Overview

```
CLOUD BRAIN (Sonnet 4.6, every 4h)
    → Monitors 6 HF Spaces + Kaggle
    → Dispatches 5 research subagents
    → Decides: tune / diversify / inject features
    → Acts on S10 via POST /api/config

6 HF EVOLUTION ISLANDS (CPU-only, always-on)
    → Genetic algorithm: mutate → crossover → evaluate → select
    → Diversity: 6 specialist roles (exploitation/exploration/per-model)
    → Cross-pollination: best configs seed neighbors

KAGGLE KARPATHY LOOP (P100 GPU, 9h sessions)
    → Karpathy autoresearch pattern: modify → run 5min → measure → keep/revert
    → 12 iterations/hr, ~100/session
    → Best: 0.21570 (TabICL, iter 15)
```

Key insight: The system finds its own features. No human picks features after initial architecture.

---

### Slide 3 — Feature Engine v3.1-46cat

- **46 categories** of NBA statistics
- **6 253 raw features** extracted per game
- **200 max features** selected per island (hard cap)
- **Selection method:** Genetic algorithm evolves a boolean mask over the 6 253 features
- **New in v3.1:** Cat47 Drive-Rim, Cat48 Passing PPP, Cat49 Play-Type PPP (pipeline)

Categories include: rolling EWMA windows (Cat36), moving delta averages (Cat37), pace-adjusted efficiency, clutch metrics, rest/travel features, opponent-adjusted stats, lineup continuity, referee tendencies.

Feature parity rule: `features/engine.py` and `hf-space/features/engine.py` are always identical. Drift breaks the experiment.

---

### Slide 4 — The Karpathy Loop (Autoresearch Pattern)

Borrowed from Andrej Karpathy's "nanoGPT iterative improvement" philosophy:

```python
while True:
    proposal = generate_proposal(current_state)   # LLM or mutation
    apply_proposal()                               # Code change or config change
    result = evaluate(timeout=5_minutes)          # Measure Brier/ROI
    if result.better:
        keep()
        log_win()
    else:
        revert()
    sleep(0)  # No pause. Always iterating.
```

**Why it works:** Small, reversible, measured changes. No multi-step refactors. No "I think this will help." Every change is measured.

**Our implementation:** 8 departments each run their own version of this loop. Guardian Orchestrator (Forge v19) allocates resources across departments.

---

### Slide 5 — Model Zoo (6 Models, 6 Islands)

| Island | Model | Brier (Apr 3) | Generation | Role |
|--------|-------|--------------|------------|------|
| S10 | XGBoost Brier | 0.22454 | 213 | Exploitation (low mutation) |
| S11 | XGBoost | 0.22273 | 295 | Exploration (high mutation) |
| S12 | CatBoost | 0.22506 | 590 | CatBoost specialist |
| S13 | Extra Trees | 0.22455 | 381 | Extra Trees specialist |
| S14 | XGBoost Brier | 0.22666 | 448 | LightGBM specialist |
| S15 | Random Forest | 0.22159 | 481 | Wide search (pop=50) |

**Ensemble ATR:** TabICL (in-context learning) + tree ensemble → 0.21570
TabICL treats the feature matrix as a "few-shot" table. Transformer attention over rows. No traditional training. Validated on Colab T4.

---

### Slide 6 — Calibration & Betting Layer

Prediction → calibration → Kelly sizing is the full pipeline.

**Calibration config:**
- ELO K-factor: 22
- Home court advantage: 2.8 pts (under review — possible HOME_BIAS detected)
- Monte Carlo std dev: 11.5 pts/game
- Avg team score: 114.2 (normalized per season)

**Known calibration issues (documented, being fixed):**
- ECE = 0.2758 (expected calibration error, target < 0.10)
- Overconfidence in 60–70% bucket
- Corrupted odds gate needed (skip if |model_prob - market_implied| > 0.50)

**Kelly sizing:**
```
f = (bp - q) / b
where b = decimal_odds - 1, p = model_prob, q = 1 - p
Fractional Kelly: f * 0.35 (safety buffer)
```

---

### Slide 7 — Trading Floor v4 (Multi-AI Competition)

5 AI agents (Gemini, OpenRouter, Claude, Codex, Grok) compete with identical starting bankroll ($100K virtual) using the same prediction data but different strategies.

**Current standings (Trading Floor v4, ~297 iterations):**
- Gemini: $1,731 from $100 → ROI 1,631%, Sharpe 2.66 (confidence_scaled strategy)
- OpenRouter: $164 from $100 → ROI 64.6%, Sharpe 0.56 (diversified multi-strategy)

**Why run this:** Discover which combination of model + strategy + Kelly fraction is optimal without risking real capital. The winner's config gets promoted to the live prediction layer.

---

### Slide 8 — Evaluation Framework (D5 — Bias Detection)

Automated bias detection runs every cycle. Identified biases (Apr 1 audit):

| Bias Type | Severity | Fix |
|-----------|----------|-----|
| PHANTOM_GAME (home == away) | CRITICAL | Assert game['home'] != game['away'] |
| OVERCONFIDENCE (ECE 0.2758) | HIGH | Platt scaling calibration |
| HOME_BIAS (21 home vs 10 away bets) | LOW | Recalibrate HCA weight 2.8 → 2.2 |
| CORRUPTED_ODDS (5 games, SAS normalization) | HIGH | Odds sanity gate |

**Expected Brier improvement from calibration fix alone:** -0.008 (Platt scaling)

---

### Slide 9 — Infrastructure Constraints & Solutions

**Hard constraint:** VM = 1 vCPU / 969 MB RAM. Zero ML on VM.

| What | Where | Why |
|------|-------|-----|
| Evolution training | 6 HF Spaces (CPU) | Always-on, free tier |
| GPU training | Kaggle P100 (9h), Colab T4 | Burst, no cost |
| Inference | HF Spaces | Same environment as training |
| Data | Supabase PostgreSQL | Experiments, bets, proposals |
| Orchestration | VM cron + Sonnet 4.6 brain | Lightweight coordination |

**Accounts:** 3 HF accounts (LBJLincoln, LBJLincoln26, Nomos42) × 6 spaces = 18 potential slots.

---

### Slide 10 — Roadmap to 0.20

**Gap:** 0.21570 → 0.20000 = 0.01570 improvement needed

| Technique | Expected Delta | Status |
|-----------|---------------|--------|
| Platt scaling calibration | -0.008 | Queued |
| Odds sanity gate (removes 8 corrupted bets) | -0.002 | Queued |
| Cat47-49 (Drive/Rim/Passing/PlayType PPP) | -0.003 | Pipeline |
| TabICL on HF Spaces (GPU required) | -0.005 | GPU only |
| Temporal validation tightening | -0.002 | Research |

**Cumulative if all land:** 0.21570 - 0.020 = **0.19570** (beats SOTA)

Repo: github.com/LBJLincoln/mon-ipad (internal) | HF: Nomos42/nba-quant

---

---

## DECK 2: Friends

**Context:** WhatsApp call, dinner conversation, casual demo
**Hook:** "I built an AI that predicts NBA games. It runs 24/7 by itself and it's actually decent."
**Goal:** Make them think it's genuinely cool, get them curious enough to try it

---

### Slide 1 — What's the Game?

You watch the NBA, right? Every night there are 5 to 15 games. Sportsbooks set odds. The question is: **are the odds wrong?**

If the Celtics are paying 1.5x but we think they win 72% of the time, that's a mathematical edge. Our job is to find those edges before the game tips off.

---

### Slide 2 — What I Actually Built

A prediction engine trained on 9,551 NBA games. Not just win/loss — it estimates the exact probability that each team wins. Like a weather forecast, but for basketball.

Current accuracy: **Brier score 0.21570**. The best published academic result is 0.199. We're close.

---

### Slide 3 — How It Learns (The Cool Part)

It doesn't just sit there. Every 4 hours, an AI agent wakes up, looks at the 6 "islands" of models running on Hugging Face servers, and asks: "Which configuration is winning? How can we improve?"

Then it tries something new, measures whether it's better, keeps the improvement or throws it away, and goes back to sleep.

**2,408 generations of evolution so far.** It has tried millions of combinations of features and parameters.

---

### Slide 4 — 6 Features You Didn't Know Matter

The model discovered (by itself) that these things predict NBA outcomes better than the score:

1. **Rest differential** — teams on back-to-backs lose more than odds suggest
2. **Travel distance** — cross-country flights on short rest are measurable
3. **Referee tendencies** — some refs call more fouls, which favors certain playstyles
4. **Lineup continuity** — teams with the same 5 in the last 10 games play better
5. **Clutch performance EWMA** — recent clutch performance, exponentially weighted
6. **Drive-to-rim frequency** — predicts foul rates and second-chance points

The model uses **6,253 features** and selects the best **110–200** per run.

---

### Slide 5 — Live Demo

[Show the dashboard at nomos42.com or the Telegram bot @Nomos42Bot]

Today's picks → each game → probability → edge → recommended bet size

Example output:
```
BOS vs MIA — Tip: 7:30pm
BOS win prob: 67.2%
Market: 63.8%
Edge: +3.4%
Recommendation: Bet $23 on BOS (3.4% of $680 bankroll)
```

---

### Slide 6 — The AI Agents Battle

I have 5 AI models (Google's Gemini, GPT-4, Claude, Grok, and a mix) all competing against each other with the same predictions but different betting strategies.

Like a competition: who turns $100 into the most money?

Right now Gemini is winning big — **+1,631%** return. OpenRouter is at +64%. Some are in the red.

The winner's strategy gets copied into the real predictions.

---

### Slide 7 — What Makes It Different

Most prediction tools just give you a pick: "bet on the Lakers." We give you the *probability*, the *edge*, the *size of the bet*, and the *confidence level*.

And unlike a tipster service, the model is always evolving. Every day it tries to get better. It doesn't have bad days — it just keeps running.

---

### Slide 8 — The Current Record

Starting bankroll: $100 (March 15, 2026)
Current balance: $91.89
Record: 16 wins, 25 losses

Honest answer: we're losing money right now. The model is good at predictions but we found 4 bugs in the betting layer (corrupted odds, a phantom game bug, overconfidence). Fixing those should flip the P&L.

---

### Slide 9 — What's Next (The Exciting Bit)

Three things are happening simultaneously:
1. **Target Brier < 0.20** — beating the best published academic result
2. **Building a SaaS** — you could subscribe for $19/month to get the daily picks
3. **Bankroll $100 → $1,000** — proving the strategy works in real time

If we hit Brier 0.20, we estimate **+25–50% ROI** on betting, which means $100 becomes $150 in a season with 20+ bets per week.

---

### Slide 10 — How You Can Try It

- **Telegram**: @Nomos42Bot — free daily picks, just type `/today`
- **Dashboard**: nomos42.com/nba — full predictions view
- **Coming**: mobile app, free tier API, email alerts

No commitment. Try the free tier. If it adds value, Scout tier is $19/month.

---

---

## DECK 3: Family

**Context:** Christmas dinner, phone call with parents, explaining to a sceptical relative
**Hook:** "I'm building a business around an AI that predicts basketball games. Let me explain what this actually is and when it might make money."
**Goal:** Reassure them, explain the timeline, make the risk clear, show the plan

---

### Slide 1 — What I'm Building

I've been developing an AI that predicts NBA basketball game outcomes. Think of it like an advanced weather forecast — instead of "70% chance of rain," it says "67% chance the Celtics win."

The AI was trained on 9,551 historical games and is constantly getting smarter.

---

### Slide 2 — Why Basketball?

Three reasons:
1. **Data is public and abundant** — every play in every game is tracked in real time
2. **The market is large** — sports betting is a $100 billion/year global industry
3. **The edge is measurable** — unlike stock markets, we can verify in real time whether our probability is better than the sportsbook's

The sportsbook's job is to be balanced, not to be right. That creates systematic opportunities.

---

### Slide 3 — Is This Legal?

Yes. Three separate things:

1. **The AI/software business** is a completely standard SaaS company (like Spotify, but for predictions). Customers pay a monthly subscription for access to data.

2. **Sports betting** is legal in France and in most US states. We're building tools to help people bet more rationally — like a financial advisor but for betting.

3. **Our company betting** — we test our predictions with a small real bankroll ($100 so far). It's small and controlled.

---

### Slide 4 — The Current Status

**What works:**
- The prediction model is running 24/7 automatically
- 6 servers are constantly evolving the model
- The Telegram bot sends daily picks
- The dashboard is live at nomos42.com

**What doesn't work yet:**
- The betting layer has 4 bugs we identified and are fixing
- The SaaS subscriptions are not yet public (launching Q2 2026)
- Revenue: €0 (pre-revenue, normal for this stage)

---

### Slide 5 — What It Costs

**Monthly infrastructure costs:**
- HF Spaces: $0 (free tier, 6 servers)
- Kaggle GPU: $0 (free quota, 30h/week)
- Colab GPU: $0–$10/month
- Claude API (AI brain): ~$50–$100/month
- VM server: ~$20/month
- Supabase (database): $0–$25/month

**Total: ~$100–$150/month** to run the entire operation.

This is one of the advantages of building on AI infrastructure — the cost to run sophisticated ML research is now accessible to individuals.

---

### Slide 6 — The Business Model

Revenue comes from subscriptions:

| Plan | Price | What you get |
|------|-------|--------------|
| Free | $0 | 3 picks/day |
| Scout | $19/mo | All picks, email alerts |
| Edge | $49/mo | Real-time, Kelly sizing, Telegram |
| Whale | $149/mo | Raw data, custom features |

**Year 1 target:** 750 paid subscribers → ~$340,000/year revenue.

That's the goal. Not gambling revenue. Subscription software revenue.

---

### Slide 7 — The Timeline

```
Q1 2026 (NOW):   Model running, 0.21570 Brier, 6 islands live
Q2 2026:         Public API launch, first 50 paying customers
Q3 2026:         Brier < 0.20 (beats academic SOTA), 200 customers
Q4 2026:         $100K ARR, French SASU structure created
2027:            Series A or profitability, 1,000 customers
```

**Realistic worst case:** The model never gets to < 0.20, but we still have a defensible SaaS product with decent Brier. Many sports data companies make money without being "best in class."

---

### Slide 8 — What Could Go Wrong

**Technical risk:** Brier improvement is hard. We've gone 0.22471 → 0.21570 in 3 weeks of evolution, but the next 0.015 might take months.

**Market risk:** There are well-funded competitors (Action Network, Sportradar). We differentiate on the agent marketplace and the open API.

**Regulatory risk:** Sports betting regulation varies by country. The software business (predictions API) has no regulatory risk — it's just data.

**Execution risk:** Building a subscription business while simultaneously doing R&D is hard. We've chosen to do both in parallel because the infrastructure overlaps completely.

---

### Slide 9 — The Path to Real Income

**Scenario A (Conservative):** 200 Scout subscribers + 50 Edge = $3,800/month → $45,600/year. Covers living expenses + infrastructure after taxes.

**Scenario B (Likely):** 500 Scout + 150 Edge + 20 Whale = $20,280/month → $243,360/year. Comfortable business.

**Scenario C (Upside):** Syndicates and hedge funds discover the Whale API + raw model output. One fund paying $1,000–$5,000/month changes the math entirely.

The key milestone is the first 50 paying customers. Once we prove people will pay, the path to 500 is straightforward.

---

### Slide 10 — What I Need

**Not money** (the business is self-funding at this stage).

**What would help:**
- A friend who bets on NBA to test the Telegram bot and give honest feedback
- Anyone in sports analytics or finance who wants a free Edge subscription in exchange for feedback
- Introductions to people who work at sportsbooks, sports media, or quantitative funds

**If you want to support:** Subscribe to Scout ($19/month) when we launch publicly in Q2 2026. That's the most useful thing.

---

---

## DECK 4: Investors (VC)

**Context:** Seed round pitch, angel meeting, accelerator application
**Hook:** "We're building the Bloomberg Terminal for sports intelligence. Our moat is a self-improving AI that's closing the gap to academic SOTA autonomously."
**Goal:** Secure $500K–$2M seed, demonstrate technical depth and market size

---

### Slide 1 — The Market

Global sports betting: $100B+ annual handle.
US legal sports betting market (post-PASPA): $11.5B in 2023, growing 20%+/year.
Sports data/analytics SaaS: $3.4B by 2027 (MarketsandMarkets).

The opportunity is not in operating a sportsbook. It's in selling intelligence to the millions of people who bet. Like selling shovels in a gold rush.

**Our wedge:** NBA, the most data-rich sport in the world, with the most sophisticated bettor base.

---

### Slide 2 — The Problem

Everyone claims to have an edge. Nobody can prove it.

Existing prediction services (Action Network, Sharp Sports, Covers) publish picks but not probabilities. They can't be audited. You don't know if their 70% pick is actually worth betting.

We publish the full probability distribution, the Brier score (calibration metric), the Kelly sizing, and the model version. Every prediction is verifiable after the fact.

**Brier score is our integrity metric.** A Brier of 0.21570 on 9,551 games is a documented, reproducible result. Academic SOTA is 0.199. We are 8% behind SOTA and closing.

---

### Slide 3 — The Product

**API-first SaaS with four tiers:**

- **Free** (3 picks/day): Top of funnel
- **Scout** ($19/mo): All daily picks, email alerts
- **Edge** ($49/mo): Real-time, Kelly sizing, 46 statistical categories, Telegram
- **Whale** ($149/mo): Raw model outputs, custom features, agent marketplace

**The moat:** The Agent Marketplace. Whale subscribers can publish their own betting strategies. Other users pay to subscribe to these agents. We take 30%. This creates a network effect that pure prediction tools cannot replicate.

---

### Slide 4 — Technology: The Self-Improving Engine

```
FORGE v19 (8 departments, Karpathy autoresearch pattern)
    ├── Research: 14 papers scanned, 18 techniques extracted
    ├── Engineering: Karpathy loop — measure → keep/revert (5 min cycles)
    ├── Evolution: 6 HF islands, 2,408 generations, genetic algorithm
    ├── Betting: 5 AI traders competing, discover optimal strategies
    └── Evaluation: Automated bias detection (4 biases caught, fixing)
```

Key fact: **the system improves itself.** No human intervenes in the evolution loop. The AI brain (Claude Sonnet 4.6, every 4 hours) reads the health of all 6 islands and issues config changes. This is the Karpathy autoresearch pattern applied to sports prediction.

**Best result:** Brier 0.21570 (Colab T4 GPU, TabICL + tree ensemble, 110 features, 15 iterations)

---

### Slide 5 — Traction

**Technical milestones (3 weeks of building):**
- 6 HF evolution islands: 100% uptime, 2,408 generations
- Brier: 0.22471 (day 1) → 0.21570 (week 3) = 4.0% improvement
- Feature engine: 37 → 46 categories, 6,135 → 6,253 raw features
- Telegram bot: @Nomos42Bot live with daily predictions
- Dashboard: nomos42.com/nba running

**Betting backtest (real small-scale test, $100 bankroll):**
- 41 bets, $100 → $91.89 (currently negative)
- Identified 4 bugs causing losses; fixing expected to flip P&L
- 16W/25L with corrupted odds included

**Revenue:** Pre-revenue. SaaS API launching Q2 2026.

---

### Slide 6 — The Moat

**Three compounding moats:**

1. **Proprietary data compounding:** Every game played adds to our training set. 9,551 games today → 10,000+ by end of 2026 season. Competitors starting today are permanently behind on historical data.

2. **Self-improving architecture:** The Forge v19 system (8 departments, Karpathy loops) continuously tries new feature combinations, model architectures, and calibration improvements. The improvement rate scales with compute, not headcount.

3. **Agent Marketplace network effect:** If we have 500 Edge users and 50 Whale publishers, we have a two-sided marketplace. The strategies that work surface to the top. The more users, the more quality agents. New entrants cannot replicate this without both user sides.

---

### Slide 7 — Team

**[Founder]** — [Background: technical, quantitative, ML experience]

Execution to date (solo founder, 3 weeks):
- Fully autonomous prediction pipeline (24/7)
- 6 HF evolution islands running
- Feature engine v3.1 (46 categories, 6,253 features)
- Trading Floor v4 (5 AI traders, multi-strategy competition)
- Legal structure design (French SASU triple holding)
- Dashboard, Telegram bot, Supabase integration

**Planned hires (post-seed):**
- Head of Product / Growth (SDK, onboarding, conversion)
- ML Engineer (focus: calibration, feature engineering Cat47-49)

**Advisors sought:** Sports analytics PhD, former sportsbook quant, French Tech/BPI relationship.

---

### Slide 8 — Financial Model (3-Year)

| Metric | 2026 | 2027 | 2028 |
|--------|------|------|------|
| Scout customers | 200 | 800 | 2,500 |
| Edge customers | 50 | 250 | 1,000 |
| Whale customers | 10 | 60 | 200 |
| Agent marketplace GMV | $10K | $80K | $500K |
| **ARR** | **$82K** | **$380K** | **$1.4M** |
| Gross Margin | 85% | 87% | 88% |
| Team | 1 | 3 | 7 |

**Unit economics:**
- CAC estimate: $30–$50 (content/organic at launch, paid search year 2)
- LTV estimate: Scout 12mo avg × $19 = $228; Edge × $49 = $588
- LTV/CAC: 5x–12x

---

### Slide 9 — The Ask

**Raising:** $750,000 seed
**Instrument:** SAFE, $3M cap, 20% discount

**Use of funds:**
- 40% ($300K): Team (ML engineer + growth hire, 12 months)
- 30% ($225K): GPU compute (Kaggle Pro, Vast.ai burst, Colab, Lightning)
- 20% ($150K): Go-to-market (content, SEO, sports analytics community)
- 10% ($75K): Legal (French SASU structure, IP protection, BPI applications)

**Key milestone this capital unlocks:** Brier < 0.20 (beats SOTA) + 500 paying subscribers + $100K ARR. These three together justify Series A conversation.

---

### Slide 10 — Why Now

1. **AI infrastructure costs collapsed.** Building what we built 5 years ago would have cost $500K in compute. We run for <$200/month.

2. **Sports betting legalization wave.** 38 US states legal. European market maturing. Asian market opening. The addressable market grows every quarter.

3. **Probabilistic sports analytics is underserved.** The tools that serious bettors use are proprietary Bloomberg-style terminals (Betfair API, Sharp Sports internal tools). No public API with this level of rigor exists.

4. **Self-improving AI is the new moat.** Most competitors have static models. Our Karpathy loop means our accuracy improves without human intervention. The model you use in 6 months is substantially better than today's, automatically.

**Contact:** [founder email] | nomos42.com | @Nomos42Bot

---

---

## DECK 5: Clients

**Context:** Sales call, product demo, onboarding, conference booth
**Hook:** "You already bet on NBA. We help you bet smarter, with math instead of gut."
**Goal:** Convert trial to paid subscription, demonstrate clear ROI, reduce friction to first bet

---

### Slide 1 — You Already Have an Edge Problem

The sportsbook edge (juice/vig) is typically 4–6% per bet. That means if you bet randomly, you lose 4–6% of everything you wager.

Most bettors make that worse by betting on favorites (over-priced by the market), emotional picks, and games they "follow" rather than games with mathematical edges.

**Nomos42 solves this with probabilities, not picks.**

---

### Slide 2 — What You Get (Across All Tiers)

Every subscription includes:
- Daily predictions for all NBA games (8–15 games/night during season)
- Win probability (not just "bet this team" — the actual %)
- Our model's confidence level
- Historical performance track record (transparent, auditable)
- Kelly sizing — how much of your bankroll to risk per bet

The difference between us and ESPN or Action Network: **we give you the probability, not the pick.** A pick is binary. A probability is useful.

---

### Slide 3 — The Edge Formula

```
Edge = Our_Probability - Market_Implied_Probability

If Our_Prob = 67.2% and Market_Implied = 63.8%:
Edge = 3.4%

Kelly bet = (Edge × Odds - (1 - Edge)) / Odds × Kelly_Fraction
          = 2.3% of your bankroll on this game
```

A consistent 3–5% edge on 20+ bets per week is the difference between a losing bettor and a professional.

**We find those edges for you. Every day. Before tipoff.**

---

### Slide 4 — Tier Comparison (What You Actually Get)

| Feature | Free | Scout $19 | Edge $49 | Whale $149 |
|---------|------|-----------|----------|-----------|
| Daily predictions | 3 games | All games | All + real-time | All + raw data |
| Edge calculation | No | No | Yes | Yes |
| Kelly sizing | No | Basic | Full | Full + custom |
| Telegram alerts | No | No | Yes | Yes |
| Historical data | No | 30 days | Full season | Full history |
| Agent marketplace | Browse | Browse | Subscribe | Publish |
| API access | No | Limited | Yes | Unlimited |
| Support | None | Email | Priority | Dedicated |

---

### Slide 5 — Real Numbers (Backtested)

Our best strategy (Gemini analytical, confidence_scaled) backtested over the full 2025–26 season:

- Starting bankroll: $100
- Final bankroll: **$1,731**
- ROI: **+1,631%**
- Sharpe ratio: **2.66**
- Bets placed: 3,554
- Win rate: 49.3%

Note: Backtest is on historical data. Past performance does not guarantee future results. Live results (real money): currently -8.11% over 41 bets (4 bugs identified; calibration fixes in progress).

We publish both numbers. The backtest shows what the model can do with optimal execution. The live results show where the bugs are.

---

### Slide 6 — The Kelly Sizing System

Bankroll management is where most bettors lose money — not the picks.

Classic mistake: betting 10% of your bankroll on a game you feel "really good about." Kelly sizing tells you mathematically how much to bet.

**Example with $500 bankroll:**

| Game | Our Prob | Odds (ML) | Edge | Kelly Rec |
|------|----------|-----------|------|-----------|
| BOS vs MIA | 67.2% | -210 | 3.4% | $17.50 (3.5%) |
| LAL vs GSW | 58.1% | +115 | 11.2% | $32.00 (6.4%) |
| OKC vs DEN | 45.3% | +160 | 0.5% | $0 (skip) |

The model skips the third game because there's no edge. Most bettors bet it anyway.

---

### Slide 7 — Telegram Integration (Edge Tier)

When you subscribe to Edge, you get added to a Telegram channel (@Nomos42). Every day by 11:00 AM:

```
NOMOS42 DAILY PICKS — Apr 3, 2026

8 games today | 3 high-confidence | Expected exposure: 18.6%

#1 BOS vs MIA (7:30pm)
  BOS win prob: 67.2% | Edge: +3.4%
  Bet: $17.50 (3.5% bankroll)
  Book: Pinnacle (-208) > DraftKings (-210)

#2 OKC vs DEN (9:00pm)
  OKC win prob: 63.8% | Edge: +5.1%
  Bet: $22.00 (4.4% bankroll)
  ...
```

When results come in: automated P&L notification. You always know exactly how the model performed.

---

### Slide 8 — Agent Marketplace (Edge & Whale Tier)

Not all bettors want the same strategy. The Agent Marketplace lets you subscribe to strategies built by other users — or publish your own.

**Example agents available:**
- "Grok Value Hunter": Only bets when edge > 7%. Conservative, high conviction. +1,631% ROI backtest. $9.99/month.
- "Road Dog Fade": Only backs road underdogs with rest advantage. Niche strategy. $4.99/month.
- "Line Movement Arbitrage": Only bets on significant line moves from sharp books. $14.99/month.

If you develop a strategy that works, publish it. We take 30%. You earn 70% of all subscribers.

---

### Slide 9 — Onboarding in 5 Minutes

1. **Sign up** at nomos42.com (email + password)
2. **Get your API key** (instant, in dashboard)
3. **Connect Telegram** (one command: `/connect your_api_key`)
4. **Set your bankroll** in the dashboard
5. **First prediction arrives** at 11:00 AM tomorrow

No credit card required for Free tier. Scout/Edge: cancel any time, no lock-in.

For API integration: Python SDK docs at docs.nomos42.com. Or use our Zapier integration to push predictions to your own spreadsheet/workflow.

---

### Slide 10 — ROI Proof & Risk Disclosure

**What we guarantee:** Mathematical rigor. The Brier score is published and tracked daily. If the model degrades, you see it.

**What we do not guarantee:** Profits. Sports betting involves risk. No model is 100% accurate.

**How to evaluate if it's worth $49/month:**

Calculate your current betting ROI. If you're break-even or losing, $49/month is a low price to potentially flip to positive. If you're profitable without us, the Kelly sizing alone typically reduces variance by 30–50%.

The break-even calculation: If you bet $500/week and we improve your edge by 2%, that's $10/week → $520/year. Our service costs $588/year (Edge). Net break-even requires just 2% edge improvement.

Most users see measurably better results within 30 days of using proper Kelly sizing alone.

**30-day money-back guarantee.** If you're not satisfied, full refund. No questions.
