# Nomos42 — Agent Fleet (22 agents × 27 skills)

> Version 3.0 — 2026-03-30 | Updated with GStack + Superpowers + Forge Factory

## Agent Overview

```
9 Departments | 22 Agents | 27 Skills | 17 Crons | 10 HF Spaces | 5 Telegram Bots
```

## Skills Pool (27 total)

Every agent has access to a subset of these 27 skills:

| # | Skill | Category | Description |
|---|-------|----------|-------------|
| 1 | `/sp-brainstorm` | Planning | Structured brainstorming |
| 2 | `/sp-write-plan` | Planning | Detailed implementation plans |
| 3 | `/sp-execute-plan` | Execution | Step-by-step plan execution |
| 4 | `/sp-test-driven-development` | Quality | TDD methodology |
| 5 | `/sp-subagent-driven-development` | Execution | Parallel subagent dev |
| 6 | `/sp-dispatching-parallel-agents` | Execution | Multi-task dispatch |
| 7 | `/sp-systematic-debugging` | Debug | Root cause investigation |
| 8 | `/sp-verification-before-completion` | Quality | Verify before done |
| 9 | `/gstack-ship` | Deploy | Ship: merge, test, bump, push, PR |
| 10 | `/gstack-qa` | Quality | Systematic QA + bug fixing |
| 11 | `/gstack-review` | Quality | Pre-landing code review |
| 12 | `/gstack-browse` | Research | Browser QA + screenshots |
| 13 | `/gstack-canary` | Monitor | Post-deploy canary |
| 14 | `/gstack-careful` | Safety | Destructive cmd warnings |
| 15 | `/gstack-guard` | Safety | Directory-scoped edits |
| 16 | `/gstack-cso` | Security | OWASP, STRIDE, secrets |
| 17 | `/gstack-investigate` | Debug | Systematic root cause |
| 18 | `/gstack-learn` | Knowledge | Project learnings |
| 19 | `/gstack-plan-eng-review` | Architecture | Eng manager review |
| 20 | `/gstack-retro` | Monitor | Weekly retrospective |
| 21 | `/karpathy-loop` | Evolution | Autonomous research cycle |
| 22 | `/progress-10pct` | Evolution | 10% improvement target |
| 23 | `/evolve-report` | Evolution | Progress report |
| 24 | `/agent-review` | Oversight | Agent HR review (Jensen) |
| 25 | `/spaces-health` | Monitor | HF Space health check |
| 26 | `/cross-repo-audit` | Audit | Cross-repo consistency |
| 27 | `/daily-edge` | Betting | Daily predictions + Kelly |

---

## Dept 1: RESEARCH (4 agents)

### Agent R1 — Research Analyst
**Role:** Searches latest quant research papers, hedge fund techniques, calibration advances
**Skills:** brainstorm, write-plan, investigate, browse, learn, karpathy-loop
**Cron:** Part of brain trigger (every 4h)
**HF Space:** None (runs on VM via Claude Code subagent)

### Agent R2 — Karpathy Researcher
**Role:** Finds latest NBA prediction papers, techniques, open-source tools
**Skills:** brainstorm, write-plan, investigate, browse, learn, karpathy-loop, cross-repo-audit
**Cron:** /karpathy-loop skill (on-demand or Kaggle)

### Agent R3 — Repo Scout
**Role:** Discovers GitHub repos, HF models/datasets relevant to NBA quant
**Skills:** brainstorm, browse, learn, cross-repo-audit, spaces-health
**Cron:** Part of brain trigger (every 4h)
**Memory:** `.claude/agent-memory/repo-scout/`

### Agent R4 — Market Analyst
**Role:** Monitors live NBA odds, detects value bets, steam moves, CLV
**Skills:** investigate, browse, learn, daily-edge, sp-systematic-debugging
**Cron:** */30 18-23,0-6 (game hours)

---

## Dept 2: ENGINEERING (5 agents)

### Agent E1 — Feature Engineer
**Role:** Proposes and implements new features for prediction engine
**Skills:** brainstorm, write-plan, execute-plan, test-driven-development, subagent-driven-development, verification-before-completion, gstack-ship, gstack-qa, gstack-review, gstack-investigate, gstack-learn, gstack-plan-eng-review
**Engine:** features/engine.py (v3.1-46cat, 6253 features)

### Agent E2 — Evolution Optimizer
**Role:** Tunes GA parameters, diagnoses stagnation, optimizes S10 evolution
**Skills:** brainstorm, write-plan, execute-plan, systematic-debugging, investigate, learn, karpathy-loop, progress-10pct, evolve-report, spaces-health
**Cron:** Part of brain trigger

### Agent E3 — Prediction Pipeline
**Role:** Runs predict_today.py, manages daily predictions
**Skills:** gstack-ship, gstack-qa, verification-before-completion, gstack-careful, systematic-debugging
**Cron:** autonomous-cycle.sh (:30 hourly)

### Agent E4 — Backtest Engine
**Role:** Runs walk-forward backtests, validates model performance
**Skills:** write-plan, execute-plan, test-driven-development, verification-before-completion, gstack-review, gstack-investigate
**Platform:** Kaggle GPU (30hr/week)

### Agent E5 — Data Pipeline
**Role:** Fetches NBA data, player tracking, odds, social signals
**Skills:** gstack-ship, gstack-qa, systematic-debugging, gstack-canary, gstack-investigate
**Cron:** Multiple (odds, tracking, social)

---

## Dept 3: EVOLUTION (3 agents)

### Agent V1 — Island Coordinator
**Role:** Manages 6 NBA HF islands, cross-pollination, checkpoint sharing
**Skills:** spaces-health, evolve-report, karpathy-loop, progress-10pct, cross-repo-audit, gstack-canary, gstack-investigate
**Spaces:** S10-S15 (all Nomos42 account)

### Agent V2 — GPU Trainer
**Role:** Runs GPU evolution on Kaggle/Colab/Modal
**Skills:** write-plan, execute-plan, karpathy-loop, progress-10pct, evolve-report, gstack-ship, verification-before-completion
**Platforms:** Kaggle (P100), Colab (T4), Modal (A100)

### Agent V3 — Political Evolution
**Role:** Manages 4 political alpha HF islands
**Skills:** spaces-health, evolve-report, karpathy-loop, progress-10pct, gstack-investigate, cross-repo-audit
**Spaces:** P1-P4 (Nomos42 account)

---

## Dept 4: BETTING (5 agents)

### Agent B1 — Odds Harvester
**Role:** Scrapes live odds from multiple bookmakers
**Skills:** browse, investigate, learn, daily-edge, gstack-canary
**Cron:** */30 18-23,0-6

### Agent B2 — Value Detector
**Role:** Compares model predictions to odds, finds edge
**Skills:** brainstorm, investigate, learn, daily-edge, sp-systematic-debugging
**Output:** data/nba-agent/live-odds.json

### Agent B3 — Kelly Sizer
**Role:** Position sizing with Kelly criterion
**Skills:** daily-edge, sp-verification-before-completion, gstack-careful
**Bankroll:** $102.28 (+2.28% ROI)

### Agent B4 — Betting Strategist
**Role:** Portfolio-level strategy, multi-market allocation
**Skills:** brainstorm, write-plan, daily-edge, gstack-review, progress-10pct, gstack-retro
**Cron:** 0 22 (daily at 5pm ET)

### Agent B5 — Results Evaluator
**Role:** Scores predictions against actuals, updates bankroll
**Skills:** gstack-qa, verification-before-completion, gstack-investigate, gstack-retro
**Cron:** 0 10 (daily)

---

## Dept 5: EVALUATION (2 agents)

### Agent Q1 — Quality Auditor
**Role:** Validates model accuracy, calibration, feature importance
**Skills:** gstack-qa, gstack-review, gstack-cso, verification-before-completion, cross-repo-audit, gstack-plan-eng-review
**Method:** Brier score, calibration curves, SHAP values

### Agent Q2 — Benchmark Tracker
**Role:** Tracks ATR (all-time record), compares to state-of-art
**Skills:** learn, evolve-report, progress-10pct, agent-review, cross-repo-audit
**ATR:** 0.21570 (Colab TabICL) | Target: < 0.20

---

## Dept 6: INFRASTRUCTURE (2 agents)

### Agent I1 — Fleet Manager
**Role:** Monitors VM + HF Spaces + GPU platforms
**Skills:** spaces-health, gstack-canary, gstack-investigate, gstack-cso, gstack-careful, gstack-guard, cross-repo-audit, gstack-retro
**Script:** scripts/fleet-agent.sh
**Cron:** */5 watchdog + */30 agent-cron

### Agent I2 — Infra Agent
**Role:** Auto-restarts platforms, manages resources, backup
**Skills:** gstack-ship, gstack-careful, gstack-guard, gstack-cso, gstack-investigate, systematic-debugging, spaces-health
**Script:** scripts/infra-agent.sh
**Cron:** 15,45 * * * *

---

## Dept 7: OVERSIGHT (1 agent)

### Agent O1 — Brain (CEO)
**Role:** 24/7 autonomous decision maker. Monitors everything, decides actions, pushes improvements.
**Skills:** ALL 27 skills
**Trigger:** trig_01BS3ixBvt2uKHY9p5EemcgD (Sonnet 4.6, every 4h)
**Bot:** @Nomos42Bot (Telegram)

---

## Dept 8: FORGE FACTORY (7 agents) — Per User

### Agent F0 — Strategy Definer (Layer 0)
**Skills:** 8 skills (brainstorm, write-plan, investigate, browse, learn, review, cso, plan-eng-review, verification)
**Tier:** ALL (Free: limited, Builder/Factory: full)

### Agent F1 — Product Builder (Layer 1)
**Skills:** 25 skills (all except daily-edge, cross-repo-audit)
**Tier:** Builder + Factory

### Agent F2 — Business Strategist (Layer 1)
**Skills:** 17 skills (research + strategy focus)
**Tier:** Builder + Factory

### Agent F3 — Communication Manager (Layer 1)
**Skills:** 16 skills (content + channels focus)
**Tier:** Builder + Factory

### Agent F4 — Infra Manager (Layer 2)
**Skills:** 25 skills (infra + operations)
**Tier:** Factory only

### Agent F5 — Finance & Comptabilité (Layer 2)
**Skills:** 21 skills (finance + analysis)
**Tier:** Factory only

### Agent F6 — Admin & Legal (Layer 2)
**Skills:** 22 skills (compliance + documentation)
**Tier:** Factory only

---

## Deployment Map

```
VM (1 vCPU, 969MB)              HF Spaces (CPU, Nomos42)
├── Brain O1 (trigger)          ├── S10 nba-quant (exploitation)
├── 5 Telegram bots             ├── S11 nba-quant-2 (exploration)
├── Data server :8080           ├── S12 nba-evo-3 (extra_trees)
├── 17 crons                    ├── S13 nba-evo-4 (catboost)
├── Pierre monitor              ├── S14 nba-evo-5 (lightgbm) ← LEADER
└── Forge users (forge-users/)  ├── S15 nba-evo-6 (wide search)
                                ├── P1 political-alpha
GPU Platforms                   ├── P2 political-alpha-2
├── Kaggle (30hr/wk P100)      ├── P3 political-alpha-3
├── Colab (T4 on-demand)       └── P4 political-alpha-4
├── Modal ($30/mo free)
└── Lightning.ai (22 GPU-hr)   Forge Spaces (per user)
                                └── forge-{username} (on-demand)
```

## Cron Schedule

| Time | Agent | Script | Frequency |
|------|-------|--------|-----------|
| */5 | I1 Fleet | watchdog.sh | Every 5 min |
| */5 | I1 Fleet | start_bots.sh | Every 5 min |
| */30 | O1 Brain | agent-cron.sh | Every 30 min |
| */30 | B1 Odds | fetch_free_odds.py | Game hours |
| */30 | Pierre | pierre-monitor.py | Every 30 min |
| 15,45 | I2 Infra | infra-agent.sh | Every 30 min |
| 5,35 | V3 Political | agent-cron.sh (PA) | Every 30 min |
| */30 | V3 Political | fetch_political_data.py | Every 30 min |
| 0 */2 | I1 Fleet | cross-repo-monitor.py | Every 2h |
| 30 */2 | E5 Data | fetch_social_signals.py | Every 2h |
| 0 */6 | E5 Data | fetch_political_data.py --all | Every 6h |
| 0 3 | V2 GPU | kaggle-gpu-evolution.sh | Daily 3AM |
| 0 3 | I2 Infra | backup-to-drive.sh | Daily 3AM |
| 0 10 | B5 Evaluator | evaluate_predictions.py | Daily 10AM |
| 0 22 | B4 Strategist | betting_agent.py | Daily 10PM |
| 0 22 | E5 Data | fetch_political_data.py --insider | Weekdays |
| 30 22 | E5 Data | fetch_political_data.py --prices | Weekdays |
