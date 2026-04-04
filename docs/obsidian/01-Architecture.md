---
tags: [architecture, forge-v19, departments, nomos42]
date: 2026-04-03
aliases: [Architecture, Forge v19, System Design]
---

# 01 — Architecture (Forge v19)

> Forge v19 — 3 Layers × 8 Departments | Deployed: 2026-04-03T20:02:58Z

## The 3-Layer Model

```
┌─────────────────────────────────────────────────────────────┐
│  L1 STRATEGIC                                               │
│  Claude Code CLI + User  (vision, milestones, decisions)    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  L2 APPLICATION                                             │
│  D1 Research | D2 Engineering | D3 Evolution                │
│  D4 Product  | D5 Business    | D6 Evaluation               │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  L3 LOGISTICS                                               │
│  D7 Infra | D8 Finance                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 24/7 Autonomous Runtime

```
CLOUD BRAIN (Sonnet 4.6, every 4h at :00)
    ├── Monitor S10-S15 via public /api/status
    ├── Research via 4 Claude Code subagents
    ├── DECIDE: tune GA / diversify / inject features / checkpoint
    ├── ACT on S10 via POST /api/config
    └── Write health-status.json + push git
    Trigger: trig_01BS3ixBvt2uKHY9p5EemcgD

VM MUSCLE (cron, every 4h at :30)
    ├── Run predict_today.py (if NBA games)
    ├── Push results to git
    └── Auto-restart data server
    Script: scripts/autonomous-cycle.sh

HF SPACES (6 islands, always-on, CPU tree-only, MAX_FEATURES=200)
    └── See [[02-Evolution]] for full island config

KAGGLE KARPATHY (GPU, 9h sessions)
    ├── nba_karpathy_loop.py — NBA evolution
    └── political_karpathy_loop.py — Political alpha
    Status: ERROR (timeout) — needs investigation
```

---

## 8 Departments (Forge v19)

| Dept | Name | Karpathy Loop | Primary Metric |
|------|------|---------------|----------------|
| D1 | Research | paper→extract→propose→measure | papers/week, techniques tested |
| D2 | Engineering | code→test→measure Brier→keep/revert | Brier delta, test pass rate |
| D3 | Evolution | mutate→eval→measure fitness→select | gen/hr, best Brier, diversity |
| D4 | Product | ship→user→measure feedback→iterate | user stories, features shipped |
| D5 | Business | pricing→onboard→measure conversion | MRR, conversion rate, ARPU |
| D6 | Evaluation | audit→identify→fix→verify | false positive rate, calibration |
| D7 | Infra | check→detect→fix→verify | uptime %, restart count |
| D8 | Finance | track→report→reconcile→forecast | burn rate, financial accuracy |

Max run per loop: **5 minutes** | Cadence: hourly to daily per dept

→ Full dept loops and metrics: [[04-Departments]]

---

## Guardian Orchestrator v3

Analyzes ALL departments, allocates resources, cross-pollinates wins.

- Departments loaded: 12/12
- Active cross-pollination routes: 1
- Pending actions: 3 (all MEDIUM priority, island seeding)
- Last run: 2026-04-03T21:28:07Z

Cross-pollination actions pending:
1. Seed S10 with S14 config (Brier gain: +0.00545)
2. Seed S10 with S12 config (Brier gain: +0.00465)
3. Seed S11 with S14 config (Brier gain: +0.00433)

---

## Ecosystem Overview

```
NBA Quant AI ──── mon-ipad (brain) ──── nomos-nba-agent (engine)
                        │
Political Alpha ── nomos-political-alpha
                        │
AI Art ─────────── rgwa (@RGWAbot)
                        │
Dashboard ──────── nomos-dashboard (Vercel)
                        │
HF Brain ───────── hf-brain (subtree)
```

→ All repos: [[10-Repos]]
→ All infra: [[05-Infrastructure]]

---

## Rules (Hard Constraints)

1. **ZERO ML on VM** — 1 vCPU / 969 MB RAM. ALL training on HF Spaces
2. **Feature engine parity** — `features/engine.py` = `hf-space/features/engine.py`
3. **1 fix per iteration** — never multiple simultaneous changes
4. **MAX_FEATURES=200** — hard cap on all spaces
5. **Mutation cap** — adaptive mutation capped at 0.15
6. **CPU-only islands** — no neural models (tree-based only)

---

## Delegation Matrix

| Task | Model | Mechanism |
|------|-------|-----------|
| Analysis, decisions, piloting | Opus 4.6 | Direct |
| 24/7 brain trigger | Sonnet 4.6 | Remote trigger |
| Batch execution, search | Sonnet 4.6 | Agent(model: "sonnet") |
| Codebase exploration | Haiku 4.5 | Agent(model: "haiku") |

---

## Links

[[README]] | [[00-Dashboard]] | [[02-Evolution]] | [[04-Departments]] | [[05-Infrastructure]] | [[10-Repos]]
