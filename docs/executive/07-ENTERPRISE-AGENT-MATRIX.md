# NOMOS42 — Enterprise Agent Matrix v1.0
> 3 Products × 3 Layers × Swarm Architecture
> Last updated: 2026-03-31

## Architecture Overview

The Nomos42 ecosystem runs 3 products through an identical 3-layer Forge Factory pattern.
Each product is a live reference implementation: they are not separate from the factory,
they ARE the factory's best examples. Every new Forge user inherits the exact methodology
that produced NBA Brier 0.21570, Political Engine v3.1-22cat, and RGWA autonomous generation.

```
FORGE FACTORY PATTERN (3 layers applied to every product)
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1 — PRODUCT STRATEGY & CREATION                           │
│  What to build, how to iterate it, how to sell it at scale       │
│  Agents: Strategy Definer, Product Builder, Business & Sales     │
│  Pattern: Karpathy loop — modify → 5min run → measure → keep     │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 2 — COMMUNICATION & GROWTH                                │
│  Addictive websites, social media per persona, content automation│
│  Agents: Web Publisher, Social Media, Content Automation         │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 3 — LOGISTICS & INTENDANCE                                │
│  Infrastructure, admin/legal, finance/accounting                 │
│  Agents: Infra Manager, Admin/Legal, Finance/Accounting          │
└──────────────────────────────────────────────────────────────────┘
```

---

## PRODUCT 1: NBA QUANT AI

**What it is:** Probabilistic NBA game outcome prediction + value betting engine
**User:** Sports bettors and quant funds seeking edge over the market
**Single improvement loop:** Brier score — every cycle targets a lower number
**Karpathy pattern:** Modify feature/config → evolve 50 gens → measure Brier → keep if improved

### Layer 1 — Product Strategy & Creation

| Agent ID | Name | Role | Single Metric | Status | Trigger |
|----------|------|------|---------------|--------|---------|
| NBA-L1-S | Strategy Definer (O1) | CEO decisions: tune GA, inject diversity, checkpoint | decisions_per_day | RUNNING | 4h cycle |
| NBA-L1-P | Product Builder (E1+E2) | Feature engineering + evolution optimization | features_added_per_week | ACTIVE | /karpathy-loop |
| NBA-L1-B | Business & Sales (R4+B4) | Odds research, value detection, SaaS tier positioning | value_bets_per_day | ACTIVE | /daily-edge |

**Department Head:** O1 Brain (Sonnet 4.6, every 4h)
**Swarm workers:** R1, R2, E1, E2, B2, B3 (operate in parallel, read shared state from Supabase)
**Karpathy production loop:**
```
R1 finds paper/technique
  → E1 proposes feature category
    → HF Space evolves 50 generations (5min baseline)
      → Q1/Q2 measure Brier delta
        → O1 decides: keep or discard
          → E1 merges to engine.py if Brier improved
            → V1 cross-pollinates best individual across 6 islands
```

**Product tiers being built:**
- Free: 1 pick/day (Telegram @NomosNBABot)
- Scout ($19/mo): 3 picks + confidence scores
- Edge ($49/mo): value bets + Kelly sizing
- Whale ($149/mo): full prediction API + portfolio optimization

**Current state:**
- ATR Brier: 0.21570 (Colab TabICL, 110f, iter 15)
- Walk-forward Brier: 0.22447 (19 weeks, 934 games)
- ROI: +3.92% (13 bets, Sharpe 4.57)
- Engine: v3.1-46cat, 6253 features

### Layer 2 — Communication & Growth

| Agent ID | Name | Role | Single Metric | Status | Trigger |
|----------|------|------|---------------|--------|---------|
| NBA-L2-W | Web Publisher | nomosdashboard.vercel.app/nba | daily_active_users | PARTIAL | Manual deploy |
| NBA-L2-S | Social Media | Twitter/X + Telegram + Reddit picks posts | followers_gained_per_week | PLANNED | Daily post cron |
| NBA-L2-C | Content Automation | Win streak stories, edge articles, model transparency | content_pieces_per_week | PLANNED | arena-engine output |

**Target persona:** Male 25-45, stats-curious, -$500/yr avg bettor, wants edge without doing quant work
**Pain:** Missing value bets, no access to +EV models, complexity of building own system (pain score 8/10)
**Psychological pricing:** $49/mo feels cheap vs losing $500/yr — anchored to "less than 1 bad bet"

**Website:** nomosdashboard.vercel.app/nba (LIVE — evolution, picks, arena)
**Bot:** @NomosNBABot (RUNNING — free tier active)

### Layer 3 — Logistics & Intendance

| Agent ID | Name | Role | Single Metric | Status | Trigger |
|----------|------|------|---------------|--------|---------|
| NBA-L3-I | Infra Manager (I1+I2) | 6 HF islands + VM + Kaggle/Modal/Colab | uptime_pct | ACTIVE | */5 watchdog + */30 infra-agent |
| NBA-L3-A | Admin/Legal | Betting disclaimer, terms per jurisdiction, GDPR | compliance_issues_open | PLANNED | Weekly scan |
| NBA-L3-F | Finance (B5+bankroll) | ROI tracking, bankroll state, SaaS revenue | monthly_revenue_usd | ACTIVE | Daily 10:00 cron |

**Infrastructure deployed:**
- 6 HF evolution islands (S10-S15, always-on CPU)
- 7 HF monitoring spaces (M1-M7)
- 1 HF brain space (Nomos42/nomos42-brain)
- 19 VM crons
- Supabase (pooler connection — primary paused)

---

## PRODUCT 2: POLITICAL ALPHA

**What it is:** Prediction market + stock alpha signals from political insider data
**User:** Retail investors tracking political catalysts, political prediction traders
**Single improvement loop:** Brier score on political event predictions
**Karpathy pattern:** Modify data source/feature → run political engine → measure signal accuracy → keep

### Layer 1 — Product Strategy & Creation

| Agent ID | Name | Role | Single Metric | Status | Trigger |
|----------|------|------|---------------|--------|---------|
| POL-L1-S | Strategy Definer | Decides which political categories drive most alpha | alpha_categories_live | ACTIVE | Manual (O1 Brain) |
| POL-L1-P | Product Builder (V3) | Political engine evolution, new category injection | political_features_added_per_week | ACTIVE | political-monitor space |
| POL-L1-B | Business & Sales | Polymarket trader persona, newsletter SaaS positioning | signals_value_detected_per_day | PLANNED | /political-signals |

**Department Head:** O1 Brain (shared with NBA — same brain, 2 products)
**Swarm workers:** R1 (political papers), E5 (data pipeline), V3 (political evolution), M7 (monitoring)
**Karpathy production loop:**
```
E5 fetches FEC/SEC/Polymarket/FRED data (every 6h)
  → political_engine.py generates 743 features
    → P1-P4 HF islands evolve configurations
      → Q2 measures Brier on historical political events
        → O1 decides: keep new category or discard
          → E5 merges to political engine if signal improved
```

**Product tiers being built:**
- Free: 1 signal/week
- Scout ($19/mo): daily insider + Congress signals
- Edge ($49/mo): full 22-category engine + Polymarket integration
- Whale ($149/mo): API access + custom sector filtering

**Current state:**
- Engine: v3.1-22cat, 743 features
- New categories live: Trump investments, sovereign funds, PAC-to-regulator
- Kaggle Karpathy loop: RUNNING

### Layer 2 — Communication & Growth

| Agent ID | Name | Role | Single Metric | Status | Trigger |
|----------|------|------|---------------|--------|---------|
| POL-L2-W | Web Publisher | nomosdashboard.vercel.app/political | daily_active_users | PARTIAL | Manual deploy |
| POL-L2-S | Social Media | Twitter/X congressional trade alerts, Reddit r/stocks | followers_gained_per_week | PLANNED | Signal trigger |
| POL-L2-C | Content Automation | "Senator X just bought $2M in sector Y" posts | viral_posts_per_week | PLANNED | Signal pipeline |

**Target persona:** Retail investor 30-55, follows political news, frustrated by slow reaction to news
**Pain:** Political catalysts move stocks before news breaks, too slow to act (pain score 9/10)
**Psychological pricing:** "One good trade pays for 6 months of subscription" — anchored to missed gains

**Website:** nomosdashboard.vercel.app/political (LIVE — 6 dashboard sections)
**Bot:** @StupidPoliticalBot (RUNNING)

### Layer 3 — Logistics & Intendance

| Agent ID | Name | Role | Single Metric | Status | Trigger |
|----------|------|------|---------------|--------|---------|
| POL-L3-I | Infra Manager | 4 political HF islands + data pipeline crons | data_freshness_hrs | ACTIVE | */30 + 6h crons |
| POL-L3-A | Admin/Legal | Investment disclaimer, not financial advice compliance | disclaimers_current | PLANNED | Weekly scan |
| POL-L3-F | Finance | Signal accuracy P&L, subscription tracking | signals_correct_pct | PLANNED | Weekly eval |

**Data sources live:** FEC, SEC EDGAR, Polymarket, yfinance, FRED, CoinGecko, USAspending, enforcement tracker, Congress.gov, Reddit/Twitter/YouTube
**Infrastructure deployed:** 4 political HF islands (P1-P4), political agent-cron every 30min

---

## PRODUCT 3: RGWA — AI ARTISTIC GENERATION

**What it is:** Autonomous AI content generation system (visual, music, video)
**User:** Content creators, brands, and digital artists wanting AI-powered production
**Single improvement loop:** Quality score from quality-critic agent (0-10)
**Karpathy pattern:** Modify generation prompt/params → generate batch → critic scores → keep if higher

### Layer 1 — Product Strategy & Creation

| Agent ID | Name | Role | Single Metric | Status | Trigger |
|----------|------|------|---------------|--------|---------|
| RGWA-L1-S | Strategy Definer (style-curator) | Trend scouting, defines what to generate | trend_score | ACTIVE | /trend-scout |
| RGWA-L1-P | Product Builder (visual+music+video) | Generate, iterate, improve quality | avg_quality_score | ACTIVE | /quality-loop |
| RGWA-L1-B | Business & Sales | Gallery engagement, @RGWAbot user growth | gallery_views_per_day | PLANNED | Weekly review |

**Department Head:** style-curator agent (ACTIVE — trend-informed direction)
**Swarm workers:** visual-artist, music-composer, video-director, quality-critic (5 agents)
**Karpathy production loop:**
```
style-curator scouts trends (weekly)
  → visual-artist/music-composer/video-director generate batch
    → quality-critic scores each output (0-10)
      → only pieces scoring >7 go to gallery
        → gallery engagement measured
          → style-curator updates style parameters if engagement drops
```

**Product tiers being planned:**
- Free: gallery viewer, 1 request/week
- Creator ($29/mo): 50 generations/mo, all media types
- Pro ($99/mo): unlimited + custom style training
- Enterprise: white-label API

**Current state:**
- 5 agents defined (rgwa repo)
- @RGWAbot RUNNING (Telegram)
- Generation via HF Inference API (FLUX, MusicGen, AnimateDiff)
- Gallery dashboard: nomosdashboard.vercel.app/rgwa

### Layer 2 — Communication & Growth

| Agent ID | Name | Role | Single Metric | Status | Trigger |
|----------|------|------|---------------|--------|---------|
| RGWA-L2-W | Web Publisher | rgwa-studio.vercel.app + dashboard gallery | gallery_views_per_day | PLANNED | @RGWAbot posts |
| RGWA-L2-S | Social Media | Instagram, TikTok, Pinterest visual content | followers_gained_per_week | PLANNED | /batch-generate |
| RGWA-L2-C | Content Automation | "AI created this in 30 seconds" viral posts | viral_coefficient | PLANNED | Quality loop output |

**Target persona:** Content creator 20-35, churning through AI tools, needs consistent quality
**Pain:** AI generation quality inconsistent, time to create high-quality content (pain score 7/10)
**Psychological pricing:** $29/mo vs $200+ for human designer — saves 10h/mo of creative work

**Website:** rgwa-studio.vercel.app (NOT DEPLOYED)
**Bot:** @RGWAbot (RUNNING — ~/rgwa/scripts/telegram/start_bot.sh)

### Layer 3 — Logistics & Intendance

| Agent ID | Name | Role | Single Metric | Status | Trigger |
|----------|------|------|---------------|--------|---------|
| RGWA-L3-I | Infra Manager | HF Inference API usage, generation queue | api_calls_per_day | PLANNED | Cron monitoring |
| RGWA-L3-A | Admin/Legal | DMCA/copyright for generated content | copyright_flags_open | PLANNED | Per-generation check |
| RGWA-L3-F | Finance | Generation costs vs revenue, API cost optimization | cost_per_generation_usd | PLANNED | Monthly review |

**Zero GPU on VM rule:** All generation via HF Inference API (free tier + PRO upgrade path)

---

## Cross-Product: FORGE FACTORY (The Meta-Product)

The Forge Factory is Layer 1 of the entire Nomos42 business: it sells the NBA/Political/RGWA
methodology to external users. The three products above ARE the sales pitch.

### Forge Factory Agent Instances Per External User

When an external user joins the Factory, they get a cloned version of this same 3-layer architecture:

| Layer | Agent | Inherits from |
|-------|-------|---------------|
| L1: Strategy Definer (F0) | Intake, product brief, pain canvas | O1 Brain decision pattern |
| L1: Product Builder (F1) | Karpathy loop, MVP → Pro iterations | NBA's E1/E2 + RGWA's quality loop |
| L1: Business Strategist (F2) | TAM/SAM, persona, psychological pricing | NBA's B4 + Political's R4 |
| L2: Communication Manager (F3) | Content plan, social, SEO | RGWA's social media pattern |
| L3: Infra Manager (F4) | HF Space deploy, monitoring | NBA's I1/I2 exact pattern |
| L3: Finance Comptable (F5) | Revenue tracking, commissions | NBA's B5 + bankroll state |
| L3: Admin/Legal (F6) | CGV/CGU, GDPR, compliance | Political's disclaimer pattern |

**Reference implementations (what Forge Factory sells):**
1. NBA Quant AI — best example of Karpathy loop + scientific evolution methodology
2. Political Alpha — best example of data pipeline + signal extraction + multi-source fusion
3. RGWA — best example of generative quality loop + autonomous creative production

---

## Full Cross-Product Agent Map

```
                    NBA         POLITICAL     RGWA        FORGE (per user)
LAYER 1
Strategy           O1           O1           style-cur    F0 (clone of O1)
Product Build      E1+E2+V1     E5+V3        vis+mus+vid  F1 (Karpathy template)
Business/Sales     R4+B4        R4           planned      F2 (Big4 template)

LAYER 2
Web               dashboard    dashboard    rgwa-studio   F3 (comms template)
Social            @NomosNBABot @StupidPol   @RGWAbot      F3 social module
Content           arena output signal post  quality-loop  F3 content module

LAYER 3
Infra             I1+I2+M1-M7  I2+crons     planned       F4 (infra template)
Admin/Legal       planned      planned      planned        F6 (legal template)
Finance           B5+bankroll  planned      planned        F5 (finance template)

SWARM WORKERS (run in parallel per layer per product)
NBA:     R1 R2 E1 E2 E3 E4 E5 V1 V2 B1 B2 B3 B4 B5 Q1 Q2 I1 I2 O1 M1-M7
Pol:     R1 E5 V3 M7 (sub-swarm, shared brain)
RGWA:    visual-artist music-composer video-director quality-critic style-curator
Forge:   F0 F1 F2 F3 F4 F5 F6 (one set per user)
```

---

## Deployment Status Summary

| Component | NBA | Political | RGWA | Forge |
|-----------|-----|-----------|------|-------|
| L1 Strategy agent | RUNNING | RUNNING | RUNNING | NOT DEPLOYED |
| L1 Product build | ACTIVE | ACTIVE | ACTIVE | NOT DEPLOYED |
| L1 Business/Sales | PARTIAL | PARTIAL | PLANNED | NOT DEPLOYED |
| L2 Website | PARTIAL | PARTIAL | PLANNED | NOT DEPLOYED |
| L2 Social media | PARTIAL | PLANNED | PLANNED | NOT DEPLOYED |
| L2 Content automation | PLANNED | PLANNED | PLANNED | NOT DEPLOYED |
| L3 Infra | ACTIVE | ACTIVE | PLANNED | NOT DEPLOYED |
| L3 Admin/Legal | PLANNED | PLANNED | PLANNED | NOT DEPLOYED |
| L3 Finance | ACTIVE | PLANNED | PLANNED | NOT DEPLOYED |

**Immediate priority**: NBA is the most complete. Political and RGWA L2/L3 are the gaps.
**Forge priority**: Implement F0+F1 as CLI scripts (Option B from 06-FORGE-STATUS.md).
