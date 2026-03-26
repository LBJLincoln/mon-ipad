# Nomos42 — NBA Quant AI

> Architecture v15 — Brain + Muscle | Updated: 2026-03-25

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.22041 (S10 MOVDA-era, xgboost, gen 435) | All-time: 0.21976 | **Target:** < 0.20, ROI > 5%, Sharpe > 1.5

## Nomos42 Ecosystem

| Flagship | Repo | Bot | Status |
|----------|------|-----|--------|
| NBA Quant AI | mon-ipad + nomos-nba-agent | @Nomos42Bot | ACTIVE -- 6 evolution islands |
| AI Artistic Generation | rgwa | @RGWAbot | ACTIVE -- generative AI |
| Factory / Complex RAGs | rag-website | -- | SHELVED |
| Dashboard Hub | nomos-dashboard | -- | ACTIVE -- monitoring all projects |

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

HF SPACES (6 islands, always-on, CPU tree-only, MAX_FEATURES=200)
    ├── S10 Nomos42/nba-quant: exploitation (mut=0.09, cx=0.80, feat=63)
    ├── S11 Nomos42/nba-quant-2: exploration (mut=0.15, feat=80)
    ├── S12 Nomos42/nba-evo-3: extra_trees specialist (mut=0.08, feat=60)
    ├── S13 Nomos42/nba-evo-4: catboost specialist (mut=0.10, feat=66)
    ├── S14 Nomos42/nba-evo-5: lightgbm specialist (mut=0.08, feat=55)
    └── S15 Nomos42/nba-evo-6: wide search (mut=0.18, feat=80, pop=50)

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
| `/karpathy-loop` | Autonomous research cycle (5 subagents → proposals → quick wins) |
| `/tony-bloom` | Daily predictions + value bets (Starlizard pattern) |
| `/progress-10pct` | Target 10% improvement in weakest metric |
| `/spaces-health` | Health check all 6 HF evolution islands |
| `/evolve-report` | Comprehensive evolution progress report |
| `/agent-review` | Weekly agent performance review (Jensen HR model) |

## Rules

1. **ZERO ML on VM** — 1 vCPU / 969 MB RAM. ALL training on HF Spaces
2. **Feature engine parity** — `features/engine.py` = `hf-space/features/engine.py` always
3. **1 fix per iteration** — never multiple simultaneous changes
4. **All experiments tagged** with `feature_engine_version` in Supabase
5. **Feature engine** — v3.0 + Cat36 EWMA + Cat37 MOVDA = 37 categories, 6135 raw features
6. **MAX_FEATURES=200** — hard cap enforced in init/mutate/crossover on all spaces
7. **Mutation cap** — adaptive mutation capped at 0.15 (deployed S10/S11/S12/S15)
8. **CPU-only islands** — no neural models on CPU (tree-based only), stacking removed
9. **Supabase** — primary (ayqviq) paused (402), using pooler connection (xivvnr)

## MCP Servers

| Server | Purpose |
|--------|---------|
| Supabase | NBA data, experiments, research_proposals |
| Neo4j | Knowledge graph |
| HuggingFace | Space management |

## Telegram

| Bot | Repo | Purpose |
|-----|------|---------|
| @Nomos42Bot | mon-ipad | NBA Brain -- predictions, analysis, research |
| @RGWAbot | rgwa | AI Art Terminal -- generation, gallery, quality |

Channel: @Nomos42

## Delegation

| Task | Model | Mechanism |
|------|-------|-----------|
| Analysis, decisions, pilotage | Opus 4.6 | Direct |
| 24/7 brain trigger | Sonnet 4.6 | Remote trigger |
| Batch execution, search | Sonnet 4.6 | Agent(model: "sonnet") |
| Codebase exploration | Haiku 4.5 | Agent(model: "haiku") |
