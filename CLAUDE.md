# Nomos42 — NBA Quant AI

> Last updated: 2026-03-24

## Mission
Build the best NBA prediction AI in the world.
Best: Brier 0.2198 (Stacking) | Target: < 0.20, ROI > 5%, Sharpe > 1.5

## Architecture (Claude Code 2026)

```
Claude Code CLI (Opus 4.6)
├── Hooks: post-commit tests, pre-push engine parity
├── Skills: /eval, /status-check, /improve, /monitor, /karpathy-loop
├── Cron: /karpathy-loop every 6h, health checks, evolution monitoring
├── Subagents: Sonnet (execution), Haiku (exploration)
└── MCP: Supabase, Neo4j, HuggingFace
```

## Active Infrastructure

| Component | Where | Purpose |
|-----------|-------|---------|
| **S10** (nba-quant) | HF Space (lbjlincoln) | 24/7 genetic evolution |
| **S11** (nba-quant-2) | HF Space (lbjlincoln) | Experiment queue runner |
| **Supabase** | Cloud | NBA data, experiments, predictions, research_proposals |
| **VM** (this) | GCP 34.136.180.66 | Claude Code, data server, git |

## Repos

| Repo | Role |
|------|------|
| **mon-ipad** (this) | Control tower, ops, config |
| **nomos-nba-agent** | Models, features, evolution, predictions |
| **rag-website** | Next.js frontend (nomos42.vercel.app/nba) |

## Rules

1. **ZERO ML on VM** — 1 vCPU / 969 MB RAM. ALL training on HF Spaces / Colab
2. **Feature engine parity** — `features/engine.py` = `hf-space/features/engine.py` always
3. **1 fix per iteration** — never multiple simultaneous changes
4. **All experiments tagged** with `feature_engine_version` in Supabase

## Key Commands

```bash
source .env.local
python3 scripts/nba-data-server.py &          # JSON API for Vercel
python3 -c "from features.engine import ENGINE_VERSION; print(ENGINE_VERSION)"  # Check engine
```

## Delegation

| Task | Model | Mechanism |
|------|-------|-----------|
| Analysis, decisions, pilotage | Opus 4.6 | Direct |
| Batch execution, search | Sonnet 4.6 | Agent(model: "sonnet") |
| Codebase exploration | Haiku 4.5 | Agent(model: "haiku") |
