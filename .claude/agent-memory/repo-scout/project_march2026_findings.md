---
name: project_march2026_findings
description: Top repo-scout findings from two broad March 2026 scans (NBA-specific + AI ecosystem)
type: project
---

Two scans completed 2026-03-25. Scan 1: NBA/tabular ML focus. Scan 2: AI agents/GPU/ML framework focus.

**Why:** User requested full ecosystem coverage beyond NBA-only: official agent frameworks, GPU tools, hot trending repos, HuggingFace models.

## Top 5 Actionable Items (highest ROI)

1. **TabICLv2 stacking meta-learner** — Colab T4: fit TabICLv2 on S10's 63-feature evolved subset, add predict_proba() as meta-features to XGBoost blender. TabArena shows GBDT+DL ensemble beats GBDT-only. 6h, -0.004 Brier. (~0.21467 target)

2. **Parallel Karpathy subagents** — claude-code-workflow-orchestration plugin enables parallel dispatch of all 4 subagents simultaneously. 3x Brain cycle speedup. 3h, no direct Brier delta but 3x research velocity.

3. **Hindsight MCP persistent Brain memory** — Add vectorize-io/hindsight MCP to Brain's config. retain(experiment outcomes), reflect('what feature categories improved Brier in last 50 generations'). Enables data-driven Brain decisions. 4h, -0.003 estimated indirect Brier improvement.

4. **SDK session tagging** — claude-agent-sdk>=0.1.49 tag_session(f'gen{N}_brier{score}') in autonomous-cycle.sh. Creates searchable audit trail. 2h, operational improvement.

5. **TabPFN-2.5 distillation** — Colab T4: fit TabPFN-2.5 on 63 features, distill to tree ensemble, deploy to HF Spaces CPU. Foundation model quality at CPU inference speed. 8h, -0.003 Brier.

## Prior Scan Top 3 (still valid)

6. **MAPIE Venn-Abers calibration** — 3h, -0.005 to -0.008 Brier. Still not implemented.
7. **BALLDONTLIE MCP + injury/market features** — 5h, -0.003 to -0.006 Brier.
8. **LLM-FE evolutionary features + TabICLv2 stacking** — 10h combined, -0.007 to -0.013 Brier potential.

## Key Structural Discovery (Scan 1)

**Ogham-MCP** (github.com/ogham-mcp/ogham-mcp) — Supabase + pgvector shared memory MCP server. All 6 HF Space islands + Brain share searchable experiment memory. 3h to set up.

## Tabular ML State 2026

TabPFN-2.5 scales to 50k samples / 2000 features. TabICLv2 is faster than v1. TabArena confirms: diverse GBDT+DL ensemble beats GBDT-only. Our GA should evolve BLEND WEIGHTS across {XGBoost, LightGBM, CatBoost, extra_trees, TabICLv2, TabPFN-2.5 distilled} rather than just 4 GBDT types.

**TabPFN constraint:** max 2000 features. Our GA-evolved 63-feature subset is well within this limit.

## Agent Ecosystem State 2026

- **Claude Agent SDK v0.1.49-50 (Mar 20):** AgentDefinition gains skills/memory/mcpServers fields, session tagging, per-turn token usage tracking, StopFailure hook
- **Claude Code 2.1.77-81:** Opus 4.6 64k output tokens, 1M context for all plans, bare mode, channel permission relays, MCP elicitation (interactive forms)
- **Google ADK v1.27.3 / v2.0.0a1 (Mar 2026):** 18.6k stars, graph-based workflow runtime in v2.0.0a1 pre-release, native A2A protocol
- **OpenAI Agents SDK v0.13.0 (Mar 23):** 20.3k stars, provider-agnostic, 100+ LLMs
- **Microsoft Agent Framework python-1.0.0rc5 (Mar 20):** 8.2k stars, GA expected end of March, AutoGen in maintenance mode
- **obra/superpowers (Mar 2026):** 95k stars (+37.8k in March), spec-first + TDD methodology, Claude Code native
- **vectorize-io/hindsight (Mar 15+):** SOTA LongMemEval, MCP server mode, 3 ops: retain/recall/reflect
- **666ghj/MiroFish:** 33.7k stars, swarm intelligence for prediction tasks — worth reading for ensemble patterns
- **barkain/claude-code-workflow-orchestration:** parallel agent execution for Claude Code — must evaluate for Karpathy loop

## New Data Sources Discovered (Scan 1)

- BALLDONTLIE MCP: 23 NBA tools, injury reports, prop odds, advanced stats V2
- Odds-API.io Python SDK: 250+ bookmakers, line movement timestamps, arbitrage detection
- NBA_AI GitHub: 3-season dev DB (2023-2026, ~4100 games) downloadable

## GPU Options 2026

- Colab T4: still free, our primary
- Modal: best DX for serverless GPU, free credits available
- RunPod: cheapest spot instances ($0.20/hr)
- Kaggle: BROKEN for us
- Lightning AI: unexplored, worth testing

**How to apply:** Next Karpathy cycle priority order: (1) TabICLv2 stacking on Colab, (2) Hindsight MCP setup, (3) MAPIE calibration (still pending from Scan 1), (4) parallel Karpathy via workflow-orchestration plugin.
