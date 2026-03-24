# Nomos42 — NBA Quant AI

> Architecture v14 — Brain + Muscle | Updated: 2026-03-24

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.2200 | **Target:** < 0.20, ROI > 5%, Sharpe > 1.5

## 24/7 Autonomous Architecture

```
CLOUD BRAIN (Sonnet 4.6, every 4h at :00)
    ├── Monitor S10-S15 via public /api/status
    ├── Research via 4 Claude Code subagents
    ├── DECIDE: tune GA / diversify / inject features / checkpoint
    ├── ACT on S10 via POST /api/config
    └── Write health-status.json + push
    Trigger: trig_01BS3ixBvt2uKHY9p5EemcgD

VM MUSCLE (cron, every 4h at :30)
    ├── Run predict_today.py (if NBA games)
    ├── Push results to git
    └── Auto-restart data server
    Script: scripts/autonomous-cycle.sh

HF SPACES (6 islands, always-on)
    ├── S10 LBJLincoln/nomos-nba-quant: exploitation (mut=0.09)
    ├── S11 LBJLincoln/nomos-nba-quant-2: exploration (mut=0.15)
    ├── S12 LBJLincoln26/nba-evo-3: extra_trees specialist
    ├── S13 LBJLincoln26/nba-evo-4: catboost specialist
    ├── S14 Nomos42/nba-evo-5: lightgbm specialist
    └── S15 Nomos42/nba-evo-6: wide search

GOOGLE COLAB (GPU, on-demand)
    └── colab/nba_evolution_gpu.ipynb: T4 GPU evolution

SYSTEM CRONS
    ├── */30  keepalive-spaces.sh (all 6 islands)
    ├── 12,18 nba-daily-odds.py
    └── :30   autonomous-cycle.sh
```

## Skills

| Skill | Purpose |
|-------|---------|
| `/karpathy-loop` | Autonomous research cycle (4 subagents → proposals → quick wins) |
| `/tony-bloom` | Daily predictions + value bets (Starlizard pattern) |
| `/progress-10pct` | Target 10% improvement in weakest metric |

## Rules

1. **ZERO ML on VM** — 1 vCPU / 969 MB RAM. ALL training on HF Spaces
2. **Feature engine parity** — `features/engine.py` = `hf-space/features/engine.py` always
3. **1 fix per iteration** — never multiple simultaneous changes
4. **All experiments tagged** with `feature_engine_version` in Supabase

## MCP Servers

| Server | Purpose |
|--------|---------|
| Supabase | NBA data, experiments, research_proposals |
| Neo4j | Knowledge graph |
| HuggingFace | Space management |

## Delegation

| Task | Model | Mechanism |
|------|-------|-----------|
| Analysis, decisions, pilotage | Opus 4.6 | Direct |
| 24/7 brain trigger | Sonnet 4.6 | Remote trigger |
| Batch execution, search | Sonnet 4.6 | Agent(model: "sonnet") |
| Codebase exploration | Haiku 4.5 | Agent(model: "haiku") |
