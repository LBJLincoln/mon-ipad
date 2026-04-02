# La Forge Factory — nba-agent

> Your AI Company Factory powered by 7 autonomous agents
> Plan: factory | Created: 2026-04-02

## Your Product
- **Idea**: NBA Quant AI — Best NBA prediction model in the world
- **Target user**: Sports bettors, quant traders, NBA analysts, data scientists
- **Pain solved**: No reliable, data-driven NBA prediction system at consumer level (Brier < 0.22)
- **Revenue model**: SaaS subscription $19/$49/$149/mo (Pro/Serious/Star)

## Your 7 Agents

### Active Agents
| # | Agent | Status | Capability |
|---|-------|--------|------------|
| 0 | Strategy Definer | FULL + UNLIMITED | NBA market analysis, competitor scan, positioning |
| 1 | Product Builder | FULL + UNLIMITED | Evolution engine, feature engineering, model training |
| 2 | Business Strategist | FULL + UNLIMITED | Pricing optimization, TAM analysis, conversion |
| 3 | Communication Manager | FULL + UNLIMITED | SEO/GEO posts, Telegram @Nomos42Bot, newsletter |
| 4 | Infra Manager | FULL | 6 HF islands, Kaggle GPU, VM, Vercel monitoring |
| 5 | Finance & Comptabilité | FULL | Bankroll tracking, GPU costs, subscription revenue |
| 6 | Admin & Legal | FULL | Sports betting compliance, data licensing, GDPR |

## Key Metrics
- **Best Brier**: 0.21570 (ATR, Colab TabICL) → Target < 0.20
- **Feature Engine**: v3.1-46cat, 6253 raw features, 200 max per space
- **HF Fleet**: 6 islands (S10-S15), fleet best 0.22066
- **Bankroll**: $103.92 (+3.92% from $100)
- **Karpathy**: 12 iter/hr GPU, 30 iter/session CPU

## Agent Swarm Coordination

All agents share state via `data/agent-state/`:
- Agent 0 → defines betting market strategy, identifies edge opportunities
- Agent 1 → builds models, evolves features, runs Karpathy loops
- Agent 2 → optimizes pricing, tracks conversion, analyzes TAM
- Agent 3 → writes posts for @Nomos42Bot, prepares social content
- Agent 4 → monitors 6 HF islands, GPU availability, data pipeline
- Agent 5 → tracks bankroll P&L, GPU burn rate, revenue projections
- Agent 6 → sports betting legal compliance, data source licensing

## Karpathy Pattern per Department
- D1 Research: paper → extract → propose → measure (papers/week)
- D2 Engineering: code → test → Brier → keep/revert (Brier delta)
- D3 Evolution: mutate → eval → fitness → select (gen/hr, best Brier)
- D4 Betting: strategy → backtest → ROI → keep/revert (ROI, Sharpe)
- D5 Evaluation: audit → identify → fix → verify (calibration)

## MCP Servers
- Supabase: NBA data, experiments, research_proposals
- Neo4j: Feature/model knowledge graph
- HuggingFace: 6 evolution island management
