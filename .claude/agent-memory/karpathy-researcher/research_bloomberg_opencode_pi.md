---
name: Bloomberg Terminal + OpenCode + Pi Agent Research (Apr 3, 2026)
description: Complete analysis of OpenBB (fork for NBA), OpenCode (Groq cost savings), Pi-Mono (custom agents) for Nomos42. Implementation roadmaps, integration checklists, cost-benefit analysis.
type: reference
---

# Bloomberg Terminal Alternatives + OpenCode + Pi Agent Research

**Date:** April 3, 2026 | **Status:** ACTIONABLE - Ready to deploy

## TL;DR - Three Tools for Nomos42

1. **OpenBB Terminal** (RECOMMENDED) — Fork MIT-licensed OpenBB, add ESPN/DraftKings providers, deploy "Bloomberg for NBA" with real-time odds + model outputs + Copilot. Effort: 6-8h, Cost: $0, ROI: Visible dashboard (per memo Apr 3).

2. **OpenCode** (COST SAVER) — Replace Tier-2 subagents (D1 Research, D5 Evaluation, D6 Infra) with free OpenCode + Groq Mixtral. Savings: $630/mo. Effort: 4-6h, Cost: $0.

3. **Pi-Mono** (OPTIONAL PHASE 2) — Build custom feature engineer extensions for D3 (Evolution). Effort: 1-2wks, Cost: $0, Benefit: Faster feature iteration.

## What's Free?

| Tool | License | Cost | Use Case |
|------|---------|------|----------|
| OpenBB Terminal | MIT | $0 (self-hosted) | Dashboard, real-time data |
| OpenCode | MIT | $0 (CLI) | Research, evaluation, infra agents |
| Pi-Mono | MIT | $0 (self-hosted) | Custom agent extensions |
| Groq Mixtral | Proprietary | Free (API) | LLM for OpenCode (unlimited free tier) |
| Ollama | MIT | $0 (local) | Local open models, no API costs |

## Implementation Roadmap

### Phase 1: OpenBB Terminal (Weeks 1-2, HIGH PRIORITY)
- Fork OpenBB-finance/OpenBB → nomos42-openbb
- Add 3 providers: ESPN (odds), DraftKings, BetMGM
- Add 2 routers: /predictions (S10-S15 status), /trading-floor (TF state)
- Deploy Copilot (Claude backend)
- Build CLI TUI with Rich
- Success: Query "What's our edge on LAL-BOS?" and get live answer

**Files to create:** 6 Python files (~900 LOC total)
**Deliverable:** Deployed to localhost:6900 or HF Space

### Phase 2: OpenCode Integration (Weeks 2-3, MEDIUM PRIORITY)
- Install OpenCode globally via npm
- Migrate D1 (Research) to OpenCode + Groq Mixtral
- Migrate D5 (Evaluation) to OpenCode + Claude
- Migrate D6 (Infra) to OpenCode + Ollama local
- Expected savings: $630/mo

**Files to create:** 3 bash wrapper scripts + YAML config
**Deliverable:** Cron jobs + cost reduction proof

### Phase 3: Pi-Mono Extensions (Weeks 3-4, OPTIONAL)
- Write TypeScript extensions for feature importance (SHAP)
- Write backtest runner extension
- Deploy as D3 (Evolution) enhancement
- Expected benefit: 2+ feature wins/week with higher Brier impact

**Files to create:** 2-3 TypeScript packages
**Deliverable:** Feature suggestions ranked by backtest impact

## Cost Impact

**Current spend:** $880/mo ($20 Claude Code + $800 Sonnet + $30 Haiku + $30 Lightning)

**After optimization:** $230-250/mo (Claude Code + critical Sonnet + OpenCode free)

**Savings:** $630-650/mo (~$7,800/year)

**Payback period:** 0 days (implementation pays for itself immediately)

## Key Decision Points

1. **OpenBB**: Must do for Dashboard v2 (per Apr 3 memo) and visible improvements
2. **OpenCode**: High ROI, low risk. Do Phase 2 immediately after Phase 1
3. **Pi-Mono**: Only if D3 (Evolution) needs custom feature suggestion workflows

## Critical Integration Points

- OpenBB must query HF Spaces API endpoints (S10-S15 status, latest Brier)
- OpenCode output must be valid JSON (for cron + git integration)
- All agents must have Telegram alerts on failure
- Trading floor state must feed into OpenBB dashboard in real-time

## Files Location

**Full research document:** `/tmp/bloomberg-opencode-pi-research.md` (6,000+ words, all implementation details)

**Deployment scripts:** TBD (Phase 1 completion)

## References

- OpenBB: https://github.com/OpenBB-finance/OpenBB (MIT license, 50K+ stars)
- OpenCode: https://github.com/opencode-ai/opencode (MIT license, 120K+ stars)
- Pi-Mono: https://github.com/badlogic/pi-mono (MIT license, active development)
- OpenBB Copilot: https://docs.openbb.co/workspace/openbb-copilot
- OpenCode vs Claude Code comparison: https://www.nxcode.io/resources/news/opencode-vs-claude-code-vs-cursor-2026
