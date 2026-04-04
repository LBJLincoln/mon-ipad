---
tags: [API, marketplace, SaaS, vision, monetization, nomos42]
date: 2026-04-03
aliases: [API Vision, Marketplace, SaaS, Monetization, Agent Sales]
---

# 08 — API Vision & Marketplace

> API-first architecture | Agent marketplace | SaaS tiers | $1B enterprise vision

## Vision

Nomos42 is not just an internal prediction engine — it is the foundation for a sports AI API platform that:
1. Sells predictions to individual bettors (SaaS)
2. Sells evolved agents to hedge funds (B2B)
3. Creates an AI trader marketplace (Web3-optional)
4. Becomes the Bloomberg Terminal for sports quant

---

## SaaS Pricing Tiers

| Tier | Price | Features | Target |
|------|-------|----------|--------|
| Free | $0/mo | 3 picks/week, 24h delay | Individual, testing |
| Starter | $19/mo | 10 picks/day, same-day | Casual bettor |
| Pro | $49/mo | All picks, Kelly sizing, API access | Serious bettor |
| Quant | $149/mo | Full API, backtest, model details | Quant developer |
| Institutional | Custom | White-label, dedicated island | Hedge fund / sportsbook |

---

## API Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  PUBLIC API (Vercel edge, nomos-dashboard)                  │
│  /api/predictions  — today's picks + probabilities          │
│  /api/value-bets   — Kelly-sized high-edge picks            │
│  /api/backtest     — historical performance                  │
│  /api/evolution    — island status + best Brier             │
│  /api/health       — system status                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PRIVATE API (VM + HF Spaces)                               │
│  /api/config       — POST to update island GA params        │
│  /api/train        — trigger evolution cycle                │
│  /api/agent        — spawn new trading agent                │
└─────────────────────────────────────────────────────────────┘
```

---

## Agent Marketplace Concept

### What We Sell

**Agent Packages** — pre-trained Grok/Claude/Gemini trading agents:
- Full season backtested P&L
- Configurable risk tolerance
- Model selection (tabicl, catboost, xgboost...)
- Category specialization (alt_spread, ML, totals)

**Island Subscriptions** — dedicated HF evolution island:
- Customer's own private island
- Custom feature set
- Custom mutation parameters
- Monthly Brier improvement reports

**Signal API** — raw probability stream:
- Per-game win probabilities
- Calibrated Kelly fractions
- Confidence intervals
- Live odds integration

---

## Revenue Model

| Product | Unit Price | Volume Target | Monthly Revenue |
|---------|-----------|---------------|-----------------|
| Starter subs | $19/mo | 100 users | $1,900 |
| Pro subs | $49/mo | 50 users | $2,450 |
| Quant subs | $149/mo | 20 users | $2,980 |
| Institutional | $5,000/mo | 2 clients | $10,000 |
| Agent packages | $299 one-time | 20/mo | $5,980 |
| **Total (Year 1 target)** | | | **$23,310/mo** |

---

## Dashboard — Current State

Live at: nomos-dashboard.vercel.app

Pages:
- `/` — Homepage hub (links to all projects)
- `/nba` — NBA predictions, picks, evolution status
- `/arena` — Trading Floor, agent P&L, 5 live charts
- `/political` — Political alpha signals
- `/infra` — Infrastructure health
- `/forge` — Department council status

Charts deployed (Apr 3):
1. Bankroll evolution over season
2. Strategy comparison (ROI bars)
3. Model performance heatmap
4. Evolution Brier progression
5. Agent P&L comparison

---

## Telegram Bot as API Gateway

@Nomos42Bot serves as the primary user interface:
- `/predict` — today's game predictions
- `/bankroll` — current bankroll state
- `/pick [game]` — specific game analysis
- `/evolution` — fleet status
- `/alert on/off` — subscribe to alerts

Channel: @Nomos42 — public predictions + daily summary

---

## Enterprise Vision ($1B)

```
Layer 1: Individual bettor SaaS ($19-149/mo)
Layer 2: Quant developer API ($149-999/mo)
Layer 3: Hedge fund institutional (custom, $5K-50K/mo)
Layer 4: Sportsbook licensing (white-label, $100K+/yr)
Layer 5: International expansion (UK, EU, Asia markets)
```

**Bloomberg Terminal analogy:** $24,000/yr per terminal × 300,000 subscribers = $7.2B
**Sports quant niche:** 1% of that TAM = $72M ARR

---

## Technical Requirements for API Launch

| Requirement | Status | ETA |
|-------------|--------|-----|
| Public prediction API | PARTIAL (Vercel) | Q2 2026 |
| Authentication + rate limiting | NOT STARTED | Q2 2026 |
| Stripe billing integration | NOT STARTED | Q2 2026 |
| User dashboard | PARTIAL | Q2 2026 |
| Documentation | NOT STARTED | Q2 2026 |
| Beat Brier < 0.20 | IN PROGRESS | 0.21570 today |

---

## Links

[[README]] | [[00-Dashboard]] | [[07-Betting]] | [[09-Legal-Finance]] | [[10-Repos]]
