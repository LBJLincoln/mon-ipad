# La Forge Factory — pierre

> Your AI Company Factory powered by 7 autonomous agents
> Plan: factory | Created: 2026-03-30

## Your Product
- **Idea**: NBA Quant dashboard
- **Target user**: TBD — Agent 2 will define
- **Pain solved**: TBD — Agent 0 will discover
- **Revenue model**: TBD — Agent 2 will recommend

## Your 7 Agents

### Active Agents
| # | Agent | Status | Capability |
|---|-------|--------|------------|
| 0 | Strategy Definer | FULL + UNLIMITED | Unlimited briefs, full market scan |
| 1 | Product Builder | FULL + UNLIMITED | Unlimited products, dedicated Space |
| 2 | Business Strategist | FULL + UNLIMITED | Big4 synthesis, PE-grade analysis |
| 3 | Communication Manager | FULL + UNLIMITED | ALL channels, full A/B, video scripts |
| 4 | Infra Manager | FULL | 24/7 monitoring, auto-restart, GPU |
| 5 | Finance & Comptabilité | FULL | Multi-channel tracking, invoices, forecast |
| 6 | Admin & Legal | FULL | Custom CGV/CGU, GDPR, KYC, disputes |

## Agent Swarm Coordination

All Layer 1 agents share state via `data/agent-state/`:
```
data/agent-state/
├── agent-0-state.json  # Strategy Definer status
├── agent-1-state.json  # Product Builder status
├── agent-2-state.json  # Business Strategist status
├── agent-3-state.json  # Communication Manager status
├── agent-4-state.json  # Infra Manager status (Factory only)
├── agent-5-state.json  # Finance status (Factory only)
└── agent-6-state.json  # Legal status (Factory only)
```

Each agent reads others' state before making decisions. When Business discovers a niche, Product pivots its MVP. When Product ships, Communication writes launch posts. When Communication finds viral traction, Business recalibrates TAM.

## Skills Available

ALL 27 skills active (see tier-factory.md for full list)

## Rules

1. **Karpathy pattern**: modify → test 5 min → measure → keep if better → repeat
2. **All iterations logged** in Supabase `forge_iterations`
3. **Never ship without green metrics** — always test before deploy
4. **Agent coordination** — check other agents' state before acting
5. **User never touches backend** — agents handle everything
6. **Tier limits enforced** — respect factory plan quotas

## MCP Servers
- Supabase: forge_pierre_* tables
- Neo4j: product/market knowledge graph
- HuggingFace: Space management
- WebSearch: market research, trends

## Support
- Telegram: @Forge42Bot
- Dashboard: nomosdashboard.vercel.app/forge/pierre
- Admin: @Nomos42 (Alexis)
