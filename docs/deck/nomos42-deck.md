# Nomos42 — Investor Deck

> **Status:** DRAFT — VC-compatible narrative
> **Format:** Slide-by-slide outline for presentation builder

---

## Slide 1: Title

**Nomos42**
*AI-Powered Prediction Engine for Sports & Financial Markets*

Democratizing alpha. Beating the house.

---

## Slide 2: The Problem (La Faille)

**Information asymmetry is the most profitable exploit in the world.**

- Sports betting: $100B+ global industry. The house wins because it has teams of quants. Retail bettors have gut feelings.
- Financial markets: Insider trading advantages benefit the few. Political signals (executive orders, enforcement actions, FEC donations) move markets — but only insiders act fast enough.
- Prediction markets: Market-makers systematically exploit retail participants through superior models and data access.

**The faille:** These advantages can be replicated and democratized with AI.

---

## Slide 3: The Solution

**Nomos42 is an autonomous AI prediction engine that:**

1. **Predicts better than markets** — Brier score 0.215 vs market average 0.25 (14% better calibration)
2. **Runs 24/7 without human intervention** — 6 evolution islands, autonomous research loops, auto-improving every 4 hours
3. **Competes internally** — 5 AI agents (Gemini, Claude, Codex, Grok, OpenRouter) compete to find optimal strategies
4. **Democratizes access** — SaaS tiers starting at $19/month give anyone institutional-grade predictions

---

## Slide 4: How It Works

```
┌──────────────────────────────────────────────────────┐
│                  DATA PIPELINE                        │
│  6,253 features per game × 46 categories             │
│  Standings, form, matchups, odds, pace, defense...   │
└──────────────┬───────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────┐
│              11 PREDICTION MODELS                     │
│  XGBoost │ CatBoost │ LightGBM │ Extra-Trees │ etc  │
│  Each trained via genetic evolution (24/7)            │
└──────────────┬───────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────┐
│             5-AI TRADING FLOOR                        │
│  Gemini vs Claude vs Codex vs Grok vs OpenRouter     │
│  Per-game: model selection + strategy + Kelly sizing  │
│  Full justification for every bet placed              │
└──────────────┬───────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────┐
│           KARPATHY AUTORESEARCH LOOP                  │
│  12 experiments/hour → measure → keep if better       │
│  Autonomous improvement overnight                     │
│  Target: $100 → $1,000,000                           │
└──────────────────────────────────────────────────────┘
```

---

## Slide 5: Traction & Results

| Metric | Value |
|--------|-------|
| **Brier Score** | 0.215 (vs market 0.25) — 14% better calibration |
| **Games Backtested** | 994 (full 2025-26 NBA season) |
| **Best Agent Return** | $100 → $302,155 (Codex, aggressive Kelly) |
| **Models in Production** | 11 competing prediction models |
| **Evolution Islands** | 6 running 24/7 on HuggingFace |
| **Experiments/Hour** | 12 (Karpathy autoresearch pattern) |
| **Feature Categories** | 46 (6,253 raw features) |
| **Iterations Completed** | 7 generations, 952 evolution cycles |

**Walk-forward validation:** Average Brier 0.224 across 19 weeks, 934 games — no look-ahead bias.

---

## Slide 6: Market Opportunity

### Sports Betting
- **Global market:** $100B+ and growing 10%+ annually
- **Online segment:** Fastest growing, regulatory tailwinds (US state-by-state legalization)
- **Pain:** Retail bettors lose ~4.5% house edge; no access to quant tools
- **Opportunity:** B2C prediction SaaS, B2B model API

### Political/Financial Alpha
- **Pain:** Insider trading advantages — political signals move markets but only insiders react fast enough
- **Opportunity:** 22 signal categories → ETF trading strategies accessible to retail investors
- **Example signals:** Executive orders, enforcement actions, FEC donations, social sentiment, Congressional trades

### Total Addressable Market
- Sports analytics SaaS: $5B+ by 2028
- Political prediction markets: $1B+ (Polymarket alone: $500M+ volume)
- Retail quant tools: $10B+ (growing fast)

---

## Slide 7: Product & Pricing

| Tier | Price | What You Get |
|------|-------|-------------|
| **Starter** | $19/mo | Daily NBA picks, basic model (top 1 model) |
| **Pro** | $49/mo | All 11 models, consensus picks, historical accuracy, Political Alpha signals |
| **Trading Floor** | $149/mo | Full agent competition data, strategy breakdowns, API access, real-time evolution dashboard |

### Monetization Path
1. **Phase 1 (now):** Subscription SaaS — predictions + analysis
2. **Phase 2:** API marketplace — models, features, strategies
3. **Phase 3:** Managed funds — AI-driven sports/political alpha portfolios (regulatory dependent)

**LTV assumptions:** $19 × 12mo = $228 (Starter), $49 × 18mo = $882 (Pro), $149 × 24mo = $3,576 (Trading Floor)

---

## Slide 8: Competitive Advantage (Moat)

1. **Data compounding** — Every game played adds training data. Our 46-category feature engine is the deepest in the space.
2. **Autonomous improvement** — Karpathy autoresearch pattern: 12 experiments/hour, ~100 overnight. The system gets better while we sleep.
3. **Multi-model competition** — Not one model, but 11 competing models + 5 AI agents. Ensemble diversity prevents overfitting.
4. **Evolution at scale** — 6 islands running genetic algorithms 24/7. Feature selection, model hyperparameters, and strategies all evolve continuously.
5. **Open & verifiable** — All predictions are timestamped and public. Trust through transparency.
6. **Cross-domain transfer** — Same architecture (features → models → evolution → competition) applies to any prediction market.

---

## Slide 9: Technology & Infrastructure

| Component | Role | Cost |
|-----------|------|------|
| **VM (mon-ipad)** | Orchestrator, pilot | ~$20/mo |
| **HuggingFace Spaces** (10) | 24/7 CPU evolution islands | Free |
| **GPU Bursts** (Colab/Kaggle) | Heavy experiments, 10-30 min max | Free tier |
| **Vercel** | Frontend dashboard | Free |
| **GitHub** | Source of truth, version control | Free |
| **Total monthly burn** | | **~$20** |

**Key insight:** We achieve institutional-grade AI with a $20/month infrastructure bill by:
- Using free-tier GPU bursts instead of dedicated hardware
- Running evolution on CPU (tree-based models don't need GPU)
- Leveraging HuggingFace Spaces as always-on infrastructure
- Following Karpathy's "5-minute experiment budget" discipline

**Scaling cost with revenue:** GPU infrastructure scales with paying customers, not with R&D.

---

## Slide 10: Team & Vision

**Builder:** Solo technical founder, building with AI-native tools (Claude Code, multi-agent orchestration)

**Philosophy:**
- "Give the AI a clear metric, a 5-minute experiment budget, and walk away." — Andrej Karpathy
- Build in public. Open code. Verifiable results.
- Democratize the tools that currently only insiders have.

**Vision:** Nomos42 becomes the Bloomberg Terminal for prediction markets — giving anyone access to AI-powered alpha across sports, politics, and financial markets.

---

## Slide 11: The Ask

**Seed Round: $500K — $1M**

| Use of Funds | Allocation |
|--------------|-----------|
| **GPU Infrastructure** | 40% — Dedicated A100/H100 for 10x faster evolution |
| **Team** | 30% — ML engineer, frontend dev, data engineer |
| **Data & APIs** | 15% — Premium odds feeds, alternative data sources |
| **Marketing & Growth** | 10% — User acquisition, content, partnerships |
| **Legal & Compliance** | 5% — Sports betting regulations, financial compliance |

**Milestones with funding:**
- Month 1-3: Brier < 0.20 (SOTA), 1,000 paying users
- Month 4-6: Political Alpha live trading, $10K MRR
- Month 7-12: Multi-sport expansion (NFL, MLB, Soccer), $50K MRR
- Year 2: Managed fund pilot, international markets

---

## Slide 12: Why Now

1. **AI infrastructure is free** — HuggingFace, Colab, Kaggle give us compute that cost $100K/month 3 years ago
2. **Sports betting legalization** — US market opening state by state, creating massive new demand
3. **Prediction markets mainstream** — Polymarket proved the model; now it needs better predictions
4. **LLM agents are production-ready** — We run 5 AI agents (Gemini, Claude, Codex, Grok, OpenRouter) that make real strategic decisions
5. **Karpathy autoresearch pattern** — The paradigm for autonomous AI research is now established and proven

**The window is open. The tools exist. We're building.**

---

*Appendix available with: detailed model performance data, feature engineering documentation, full backtest methodology, codebase architecture, HF Space topology.*
