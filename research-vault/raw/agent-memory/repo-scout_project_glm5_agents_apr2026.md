---
name: GLM-5.1 + Autonomous Agents Deep Dive (April 2026)
description: GLM-5.1 deployment verdict + top 4 autonomous agent platforms assessed for Nomos42 NBA system
type: project
---

## GLM-5.1 (Z.ai, released 2026-04-07)

754B MoE (40B active), MIT license, open weights. #1 SWE-Bench Pro: 58.4 (beats GPT-5.4 57.7, Claude Opus 4.6 57.3).
200K context, 128K max output. 8-hour autonomous task loops demonstrated.
API: OpenRouter $0.95/M input, $3.15/M output (model id: z-ai/glm-5.1)
HF: https://huggingface.co/zai-org/GLM-5.1 — 24 quantized variants available.

CANNOT be self-hosted: requires 860GB VRAM (FP8) or 236GB RAM (2-bit GGUF).
ZeroGPU H200 (80GB) is NOT enough. VM (969MB RAM) is NOT enough. Use API.

**Why:** Cost/capability best ratio for agentic coding tasks in our stack.
**How to apply:** Wire into OpenRouter key as z-ai/glm-5.1. Use as backend for OpenHands or Trading Floor 6th agent.

## Autonomous Agent Platforms Ranked (April 2026)

### 1. OpenHands v1.6.0 (2026-03-30) — HIGHEST PRIORITY
70K stars. Docker, port 3000, mounts Docker socket. Planning Mode beta.
Full browser + shell + file + Git. Connects to any LLM via OpenRouter.
RAM needed: ~1.5-2GB (VM cannot run it — use brother's PC via Tailscale).
Command: `docker run ghcr.io/all-hands-ai/openhands:v1.6 + LLM_MODEL=z-ai/glm-5.1 + LLM_BASE_URL=openrouter`
Use: Standing task — daily pull top proposal from research_proposals, implement, eval, commit.

### 2. Agent Zero (April 2026)
Multi-agent: primary spawns 3-5 sub-agents in Docker. Integrated browser-use + SearXNG (free search).
Deploy on $5 Hetzner VPS. Best for parallel feature experiment loops with live web scraping.

### 3. Hermes Agent v0.7.0 (Nous Research, 2026-02-25, 32K stars)
Self-improving: builds persistent reusable skills across sessions. Railway one-click deploy.
Killer use: end Karpathy loop cycle-to-cycle rediscovery (cycles 7-13 overlap confirmed).
Backend: MiniMax M2.7 at $0.30/M tokens.

### 4. Open SWE (LangChain, Feb 2026)
Async PR creation pattern: agent picks proposal, implements, opens PR. Highest setup effort (8h).

## Deployment Constraints Confirmed
- HF Spaces free: SLEEP after inactivity. NOT 24/7. Not viable for agents.
- GitHub Codespaces: 60 free hours/month (2-core, 8GB). Good for burst sprints, NOT continuous.
- VM (969MB RAM): Cannot run OpenHands Docker. Use brother's PC (Tailscale) or $5 VPS.

## Supabase Insertions
4 proposals inserted 2026-04-12 with agent_source='research', category='architecture', status='proposed'.
IDs not captured but can be retrieved with: SELECT * FROM research_proposals WHERE technique LIKE '%GLM%' OR technique LIKE '%OpenHands%' OR technique LIKE '%Hermes%' OR technique LIKE '%Agent Zero%' ORDER BY created_at DESC LIMIT 4;
