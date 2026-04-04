# La Forge Factory — dashboard

> Your AI Company Factory powered by 7 autonomous agents
> Plan: factory | Created: 2026-04-02

## Your Product
- **Idea**: Nomos42 Dashboard — unified hub for NBA, Political, RGWA, Evolution, Forge
- **Target user**: All Nomos42 users, investors, internal teams
- **Pain solved**: No single place to view all AI operations, predictions, and evolution progress in real time
- **Revenue model**: Included in all SaaS subscription tiers ($19/$49/$149) — dashboard access is the core value-add

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

## Product Context

### Platform: Nomos42 Dashboard Hub
- **URL**: nomosdashboard.vercel.app
- **Tech stack**: Next.js 14, Vercel, Tailwind CSS, Recharts
- **Repo**: nomos-dashboard (LBJLincoln/nomos-dashboard)
- **Pages**: /nba, /political, /rgwa, /evolution, /forge

### Pages & Sections
| Page | Content | Data Source |
|------|---------|-------------|
| / (Home) | Hero, system status, all 6 islands, recent picks | agent-health.json, HF Spaces API |
| /nba | Today's predictions, bankroll tracker, Brier history | nba-agent/*.json |
| /political | 13-category signals, ETF positions, alpha radar | political data |
| /rgwa | Gallery, quality scores, generation stats | rgwa art data |
| /evolution | Trading Floor v4, 5 AI traders, iteration charts | arena/*.json |
| /forge | 9 departments, guardian report, D1-D9 loops | departments/*.json |

### Pixel Agents (Dashboard-side)
- **Pixel Agent Alpha**: NBA predictions widget, live odds integration
- **Pixel Agent Beta**: Evolution charts, Trading Floor leaderboard
- **Pixel Agent Gamma**: Political alpha signals, ETF tracker

### Key Metrics to Track
| Metric | Current | Target |
|--------|---------|--------|
| Page load time | TBD | < 1.5s (P95) |
| User engagement (session) | TBD | > 3 min avg |
| Data freshness (NBA) | TBD | < 10 min lag |
| Pixel agent uptime | TBD | > 99.5% |
| Mobile score (Lighthouse) | TBD | > 90 |

### Pain Points (User)
1. No single view of all AI operations — fragmented across repos and HF Spaces
2. Predictions buried in Telegram — no web interface
3. Evolution progress invisible to non-technical users
4. Investor-grade reporting missing
5. Trading Floor competition has no visual scoreboard

### Technical Architecture
- **Frontend**: Next.js 14 (App Router), Tailwind, shadcn/ui
- **Data**: Static JSON from mon-ipad repo, fetched at build + revalidated every 5 min
- **Deploy**: Vercel (auto-deploy on push to main)
- **Auth**: None for public pages; admin via Vercel env vars

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
7. **ZERO ML on VM** — all compute on HF Spaces; VM = data serving only
8. **Data freshness** — revalidate every 5 min, stale-while-revalidate for speed

## MCP Servers
- Supabase: forge_dashboard_* tables
- Neo4j: product/page/component knowledge graph
- HuggingFace: Space management for pixel agents
- WebSearch: competitor dashboard research, Next.js best practices

## Support
- Telegram: @Nomos42Bot
- Dashboard: nomosdashboard.vercel.app (the product itself)
- Admin: @Nomos42 (Alexis)
