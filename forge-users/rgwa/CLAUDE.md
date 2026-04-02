# La Forge Factory — rgwa

> Your AI Company Factory powered by 7 autonomous agents
> Plan: factory | Created: 2026-04-02

## Your Product
- **Idea**: AI Artistic Generation platform — generative AI art with automated quality curation
- **Target user**: AI art enthusiasts, digital artists, collectors
- **Pain solved**: AI art quality is inconsistent — no automated curation separates great outputs from mediocre
- **Revenue model**: Premium generation credits, gallery features, collector subscriptions

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

### Platform: RGWA (AI Artistic Generation)
- **Bot**: @RGWAbot on Telegram — generation requests, gallery browsing, quality feedback
- **Tech stack**: Generative AI models (FLUX, SDXL), quality scoring pipeline, automated gallery
- **Core loop**: User prompts → AI generation → Quality scoring → Curated gallery → Social sharing
- **Repo**: rgwa (LBJLincoln/rgwa)
- **Dashboard**: nomosdashboard.vercel.app/rgwa

### Key Metrics to Track
| Metric | Current | Target |
|--------|---------|--------|
| Quality score | TBD | > 7.5/10 avg |
| Output/day | TBD | > 100 curated outputs |
| User satisfaction | TBD | > 4.2/5 |
| Rejection rate (quality filter) | TBD | < 30% |
| Premium conversion | TBD | > 8% |

### Pain Points (User)
1. AI art generation is inconsistent — 1 great image out of 10
2. No automated curator separates signal from noise
3. Building a portfolio is manual and time-consuming
4. No community quality standard — everything looks the same
5. Hard to discover prompts that reliably produce good art

### Competitive Landscape
- Midjourney: great quality, no automation, Discord-only UX
- DALL-E 3: good quality, OpenAI pricing, no gallery
- Stable Diffusion: open source, complex UX, no curation
- **RGWA edge**: automated quality scoring + curated gallery + Telegram native UX

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
6. **Quality gate** — no image published without quality score >= 6.0
7. **GPU usage** — generation runs on HF Spaces GPU, NOT on VM

## MCP Servers
- Supabase: forge_rgwa_* tables
- Neo4j: art generation knowledge graph
- HuggingFace: Space management (generation + gallery)
- WebSearch: market research, AI art trends

## Support
- Telegram: @RGWAbot (user-facing), @Nomos42Bot (admin)
- Dashboard: nomosdashboard.vercel.app/rgwa
- Admin: @Nomos42 (Alexis)
