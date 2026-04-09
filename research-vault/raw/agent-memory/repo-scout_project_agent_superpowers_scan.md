---
name: project_agent_superpowers_scan
description: Agent superpowers ecosystem scan (March 2026): gstack, Hermes, GEPA, browser automation, memory, orchestration, tool-use, voice, knowledge graphs. Relevance to NBA quant + political alpha.
type: project
---

Scan date: 2026-03-30. Focus: AI agent "superpower" frameworks released or updated Feb-Mar 2026.

**Why:** User wants to identify which agent frameworks/tools can give Nomos42 an operational edge — faster research loops, better memory, browser scraping, and multi-agent orchestration.

**How to apply:** These are infrastructure/tooling findings, NOT NBA model improvements. Use to accelerate the research-ops layer (faster scraping, better agent memory, self-evolving prompts). Do NOT confuse with tabular ML findings in project_march2026_findings.md.

## HIGHEST RELEVANCE

1. **GEPA (gepa-ai/gepa)** — ICLR 2026 Oral, MIT. Reflective prompt/config evolution outperforms GRPO by 6%, uses 35x fewer rollouts. optimize_anything API (Feb 2026) extends to configs, agent architectures. DIRECT INTEGRATION: use to evolve HF Space island configs (mutation rate, crossover prob, feature counts) instead of hand-tuning. ~$2-10/run. GitHub: github.com/gepa-ai/gepa.

2. **hermes-agent-self-evolution** — NousResearch DSPy + GEPA pipeline to auto-evolve agent skills, prompts, system configs. No GPU. ~$2-10/run. ICLR 2026 Oral. GitHub: github.com/NousResearch/hermes-agent-self-evolution.

3. **gstack (garrytan/gstack)** — 57.6k stars, MIT, 23 slash commands for Claude Code. /review, /qa, /investigate, /ship, /plan-ceo-review, /plan-eng-review. DIRECT USE: can wire gstack review/qa commands into our Karpathy loop as automated code quality gates before deploying island configs.

4. **Hermes Agent (NousResearch/hermes-agent)** — 18.4k stars, v0.6.0 (2026-03-30). Multi-platform (Telegram/Discord/CLI), persistent memory, autonomous skill creation. Supports Modal as terminal backend. RELEVANT: replace crude Nomos42Bot bash executor with Hermes Agent — gets persistent memory + skill reuse across sessions.

5. **Zep Graphiti (getzep/graphiti)** — temporal knowledge graph, Apache 2.0, actively updated March 2026. Tracks HOW FACTS CHANGE OVER TIME with validity windows. RELEVANT: store NBA team/player state as temporal graph nodes — injury status, lineup changes, form — rather than flat feature snapshots. Already have Neo4j MCP; Graphiti is the memory layer on top.

## HIGH RELEVANCE

6. **Mem0 (mem0ai/mem0)** — 51,397 stars, updated 2026-03-29. Universal memory layer: 26% accuracy boost, 91% lower latency, 90% token savings vs naive context stuffing. Integrates with CrewAI/LangGraph. RELEVANT: wire into Karpathy loop so each research cycle retains findings without re-discovering.

7. **Browser Use (browser-use/browser-use)** — 78k stars, Python, Playwright-based. Natural language → browser actions. RELEVANT: replace manual odds scraping scripts with a Browser Use agent that monitors SBR/BetMGM/Pinnacle for line moves.

8. **ACI.dev (aipotheosis-labs/aci)** — 600+ tools, Apache 2.0, MCP server OR direct function calling. Intent-aware access + multi-tenant auth. RELEVANT: drop-in 600-tool access layer for political alpha data gathering (SEC EDGAR, FEC, Federal Register, USAspending all likely covered).

9. **Agent File (letta-ai/agent-file)** — open .af format for serializing stateful agents with persistent memory. RELEVANT: checkpoint our evolved island configurations as .af files — enables version control of agent state, not just code.

## MODERATE RELEVANCE

10. **Stagehand (browserbase/stagehand)** — 8k stars, TypeScript-first, Python SDK available. act()/extract()/observe() primitives on Playwright. RELEVANT: extract() for structured NBA data from stats sites that block API access.

11. **Microsoft Playwright MCP (microsoft/playwright-mcp)** — official MCP server for browser automation. Uses accessibility tree (not screenshots). 4x fewer tokens vs screenshot-based. RELEVANT: direct MCP integration with our Claude Code environment — no new infra needed.

12. **E2B (e2b-dev/E2B)** — 8.9k stars, Apache 2.0, 80ms cold starts, Firecracker sandboxes. RELEVANT: run untrusted Karpathy-generated code safely. Currently we run Kaggle notebooks blindly — E2B would let us test locally before uploading.

13. **Letta (letta-ai/letta)** — MemGPT successor. Stateful agents with editable memory blocks. Letta Code bundles pre-built skills for continual learning. RELEVANT: Karpathy loop agent could be stateful (knows what it tried before) rather than stateless.

14. **CrewAI (crewaiinc/crewai)** — 45.9k stars. Role-based multi-agent. RELEVANT: orchestrate repo-scout + feature-engineer + eval agents as a crew rather than sequential Claude Code calls. But our current 22-agent AGENTS.md system covers this without CrewAI overhead.

15. **Microsoft GraphRAG (microsoft/graphrag)** — 31.6k stars. Knowledge graph RAG. Already have Neo4j MCP. Low priority unless we want structured NBA entity extraction from unstructured text (injury reports, beat writer tweets).

## LOW RELEVANCE (for reference)

16. **LiveKit Agents (livekit/agents)** — realtime voice AI, open-source. RELEVANT ONLY if we add voice interface to Nomos42Bot or dashboard. Not a model quality driver.

17. **Vapi** — voice agent orchestration, 14+ TTS providers. Same as LiveKit — voice only.

18. **ElevenLabs livekit-plugins** — released Mar 23 2026. <500ms latency. Same category.

19. **OpenAI Swarm** — deprecated, replaced by Agents SDK. Do not use.

20. **Composio (ComposioHQ/composio)** — 1000+ toolkits, MCP server. Alternative to ACI.dev. Overlaps with our existing tool setup. Consider if ACI.dev coverage is insufficient.

21. **Anthropic Computer Use (desktop, Mar 24 2026)** — screenshot loop, macOS only. Too slow/expensive for production data pipelines.

22. **gstack agent-orchestrator (ComposioHQ/agent-orchestrator)** — parallel coding agents with CI fixes. RELEVANT ONLY for multi-PR workflows — not relevant to our current bottleneck.

## KEY INSIGHT: GEPA for Config Evolution

GEPA's optimize_anything API is architecturally identical to what our Karpathy loop does manually (modify config → measure Brier → keep if better), but uses LLM reflection to diagnose WHY a config failed and propose targeted fixes rather than random mutation. Expected improvement: 6% fewer evaluations to reach same Brier reduction. Cost: ~$2-10 per optimization run vs our current Kaggle compute cost (~$0/run on free tier). Trade-off: adds API cost but could accelerate convergence from 100 iterations/session to ~60 iterations to same quality.

## agentskills.io open standard

Anthropic released Agent Skills open standard Dec 2025, adopted by OpenAI/Microsoft/Cursor by March 2026. Our gstack + AGENTS.md + Claude Code setup is already compatible — our SKILL.md files are essentially already in this format.
