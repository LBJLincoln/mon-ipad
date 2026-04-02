# La Forge Factory — political-alpha

> Your AI Company Factory powered by 7 autonomous agents
> Plan: factory | Created: 2026-04-02

## Your Product
- **Product**: Political Alpha v3.1 — AI-powered political event prediction + ETF/stock trading signals
- **Target user**: Political analysts, hedge funds, ETF traders, political data nerds
- **Pain solved**: No systematic way to quantify political events' market impact → costly mispriced bets and missed alpha
- **Revenue model**: SaaS subscription + API access

## Product Description

Political Alpha is the first systematic AI engine that transforms political events into quantified market signals. It ingests 22 categories of political intelligence (insider trading signals, Trump policy moves, foreign sovereign fund activity, legislative outcomes, regulatory changes, and more), runs them through 743 engineered features, and outputs ETF/stock trading recommendations with probability scores and Kelly-sized positions.

**Core technology stack:**
- 22 political signal categories, 743 features
- Karpathy autonomous evolution loop (continuous improvement)
- Trading Floor with 5 AI political traders (Gemini, OpenRouter, Claude, Codex, Grok)
- Political Brier score as primary accuracy metric
- Nomos42 research infrastructure (same engine as NBA Quant AI)

**Signal categories include:**
- Insider trading detection (congressional trades, SEC filings)
- Trump policy signals (executive orders, social media, statements)
- Foreign sovereign fund flows (SWF, central bank activity)
- Legislative outcomes (bill passage probabilities, committee votes)
- Regulatory changes (SEC, FED, CFTC, FERC, FDA decisions)
- Geopolitical risk events (elections, coups, sanctions)

## Your 7 Agents

### Active Agents
| # | Agent | Status | Capability |
|---|-------|--------|------------|
| 0 | Strategy Definer | FULL + UNLIMITED | Political alpha market scan, signal discovery |
| 1 | Product Builder | FULL + UNLIMITED | Evolution loop, feature engineering, API |
| 2 | Business Strategist | FULL + UNLIMITED | Hedge fund BD, PE-grade market analysis |
| 3 | Communication Manager | FULL + UNLIMITED | Financial Twitter, fintech channels, press |
| 4 | Infra Manager | FULL | 24/7 signal pipeline, auto-restart, GPU |
| 5 | Finance & Comptabilité | FULL | Revenue tracking, API billing, forecasting |
| 6 | Admin & Legal | FULL | Financial data compliance, MiFID II, Reg D |

## Agent Swarm Coordination

All agents share state via `data/agent-state/`:
```
data/agent-state/
├── agent-0-state.json  # Strategy Definer — signal discovery status
├── agent-1-state.json  # Product Builder — engine evolution status
├── agent-2-state.json  # Business Strategist — market/BD status
├── agent-3-state.json  # Communication Manager — comms status
├── agent-4-state.json  # Infra Manager — pipeline health
├── agent-5-state.json  # Finance — revenue/billing status
└── agent-6-state.json  # Legal — compliance status
```

When Strategy discovers new political signal categories → Product evolves the engine → Business targets new client segments → Comms publishes alpha signals → Finance tracks conversions.

## Key Metrics
- **Political Brier score** — primary prediction accuracy (target: < 0.22)
- **ETF ROI** — annualized return on political signal trades
- **Sharpe ratio** — risk-adjusted return (target: > 1.5)
- **Signal coverage** — % of major political events captured
- **API latency** — signal delivery speed (target: < 500ms)

## Skills Available

ALL 27 skills active (see .claude/tier-config.md for full list)

## Rules

1. **Karpathy pattern**: modify → test 5 min → measure → keep if better → repeat
2. **All iterations logged** in Supabase `political_alpha_iterations`
3. **Never ship without green metrics** — always test before deploy
4. **Agent coordination** — check other agents' state before acting
5. **No financial advice** — signals are research/data products, not regulated advice
6. **Political neutrality** — system predicts market impact, not political outcomes
7. **Compliance first** — all financial data usage subject to legal review before ship
8. **ZERO ML on VM** — training on HF Spaces / Kaggle / Colab only

## MCP Servers
- **Supabase**: `political_alpha_*` tables — signal data, predictions, experiments
- **Neo4j**: political event knowledge graph, entity relationships
- **WebSearch**: real-time political news, SEC filings, regulatory feeds

## Infrastructure
- HF Spaces: Nomos42/political-alpha (CPU, tree-based models)
- Kaggle: political_karpathy_loop.py (GPU evolution sessions)
- Repo: nomos-political-alpha
- Dashboard: nomosdashboard.vercel.app/political

## Support
- Telegram: @Nomos42Bot
- Dashboard: nomosdashboard.vercel.app/forge/political-alpha
- Admin: @Nomos42 (Alexis)
