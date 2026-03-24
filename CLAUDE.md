# Nomos42 — NBA Quant AI

> Architecture v14 — Brain + Muscle | Updated: 2026-03-24

## Mission
Build the best NBA prediction AI in the world.
**Best:** Brier 0.2200 | **Target:** < 0.20, ROI > 5%, Sharpe > 1.5

## 24/7 Autonomous Architecture

```
☁️  CLOUD BRAIN (Sonnet 4.6, every 4h at :00)
    ├── Monitor S10/S11 via public APIs (7 endpoints)
    ├── Read crew results + analyze trends
    ├── DECIDE: tune GA / diversify / inject features / checkpoint
    ├── ACT on S10 via POST /api/config
    └── Write health-status.json + push
    Trigger: trig_01BS3ixBvt2uKHY9p5EemcgD

🔧 VM MUSCLE (cron, every 4h at :30)
    ├── Run crew research (4 agents via key_rotator)
    ├── Run predict_today.py (if NBA games)
    ├── Push results to git
    └── Auto-restart data server
    Script: scripts/autonomous-cycle.sh

🖥️  HF SPACES (always-on)
    ├── S10 (nba-quant): 24/7 genetic evolution (5×100 islands, NSGA-II)
    └── S11 (nba-quant-2): Experiment queue runner

⏰ SYSTEM CRONS
    ├── */30  keepalive-spaces.sh
    ├── 12,18 nba-daily-odds.py
    └── :30   autonomous-cycle.sh
```

## Skills

| Skill | Purpose |
|-------|---------|
| `/karpathy-loop` | Autonomous research cycle (crew → proposals → quick wins) |
| `/tony-bloom` | Daily predictions + value bets (Starlizard pattern) |
| `/monitor` | System health check |
| `/improve` | Highest-impact improvement |
| `/status-check` | Infrastructure status |

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
