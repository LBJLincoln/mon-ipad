# NOMOS42 — Agent Ecosystem v3.0
> 7 Departments | 25 Agents | 27 Skills | 17 Crons | 10 HF Spaces | 5 Bots
> Last updated: 2026-03-31

## Page 1: All Agents, Skills & Interactions

### Department Map

| Dept | Agents | Mission | Key Scripts |
|------|--------|---------|-------------|
| **Research** | R1 Analyst, R2 Karpathy, R3 Scout, R4 Market | Papers, features, repos, odds | claude subagents |
| **Engineering** | E1 Feature Eng, E2 Evolution Opt, E3 Predictions, E4 Backtest, E5 Data Pipeline | engine.py, predict, backtest | features/engine.py, predict_today.py |
| **Evolution** | V1 Island Coord, V2 GPU Trainer, V3 Political Evo | 6 NBA + 4 PA HF islands, GPU | HF Spaces, Kaggle, Modal, Colab |
| **Betting** | B1 Odds, B2 Value, B3 Kelly, B4 Strategist, B5 Evaluator | Live odds, sizing, portfolio | betting_agent.py, evaluate_predictions.py |
| **Evaluation** | Q1 Quality, Q2 Benchmark | Brier, SHAP, ATR tracking | Arena engine |
| **Infrastructure** | I1 Fleet Mgr, I2 Infra Agent | VM, HF, GPU, backups | watchdog.sh, infra-agent.sh |
| **Oversight** | O1 Brain | CEO: monitors + decides + directs | @Nomos42Bot, remote trigger |
| **Forge** | F0-F6 (7 per-user) | SaaS product factory | forge-users/{name}/ |

### Agent Detail — How They Interact

```
USER ─── Telegram / Dashboard / Colab
  │
  ├── @Nomos42Bot (O1 Brain) ──── Remote Trigger (4h) ──── Claude Code CLI
  │       │ directs all agents
  │       ├── R1-R4 Research ──── WebSearch, papers, repos ──► proposals to E1
  │       ├── E1-E5 Engineering ──── engine.py (6253 features) ──► HF Spaces
  │       ├── V1-V3 Evolution ──── S10-S15 + P1-P4 ──── Kaggle/Modal/Colab
  │       ├── B1-B5 Betting ──── odds ──► value bets ──► Kelly ──► picks
  │       ├── Q1-Q2 Evaluation ──── Brier scores, Arena results
  │       └── I1-I2 Infra ──── watchdog, keepalive, backup
  │
  ├── @NomosNBABot (SaaS) ──── free/scout/edge/whale tiers
  ├── @StupidPoliticalBot (SaaS) ──── free/scout/edge/whale tiers
  ├── @Forge42Bot (SaaS) ──── F0-F6 factory agents per user
  └── @RGWAbot (Art) ──── music/video/image generation
```

### All 27 Skills (Slash Commands)

| # | Command | Category | Purpose |
|---|---------|----------|---------|
| 1-8 | `/sp-brainstorm` `/sp-write-plan` `/sp-execute-plan` `/sp-test-driven-development` `/sp-subagent-driven-development` `/sp-dispatching-parallel-agents` `/sp-systematic-debugging` `/sp-verification-before-completion` | Superpowers | Planning, execution, TDD, debugging |
| 9-20 | `/gstack-ship` `/gstack-qa` `/gstack-review` `/gstack-browse` `/gstack-canary` `/gstack-careful` `/gstack-guard` `/gstack-cso` `/gstack-investigate` `/gstack-learn` `/gstack-plan-eng-review` `/gstack-retro` | GStack | Deploy, QA, security, monitoring |
| 21-27 | `/karpathy-loop` `/progress-10pct` `/evolve-report` `/agent-review` `/spaces-health` `/cross-repo-audit` `/daily-edge` | Nomos42 | Evolution, betting, health |

### Cron Schedule (17 active jobs)

| Freq | Agent | Script | Purpose |
|------|-------|--------|---------|
| `*/5` | I1 | watchdog.sh + start_bots.sh | Keep bots + services alive |
| `*/30` | Swarm | agent-cron.sh | NBA orchestrator (keepalive, predict, eval) |
| `*/30` | I2 | infra-agent.sh | Monitor + auto-restart GPU platforms |
| `*/30` | B1 | fetch_free_odds.py (game hours) | Live NBA odds |
| `*/30` | PA | political agent-cron.sh | Political Alpha swarm |
| `2h` | I1 | cross-repo-monitor.py | Cross-repo health |
| `6h` | E5 | fetch_political_data.py --all | Full political data |
| `3:00` | V2 | kaggle-gpu-evolution.sh | Daily Kaggle GPU evolution |
| `3:00` | I2 | backup-to-drive.sh | Daily Google Drive backup |
| `10:00` | B5 | evaluate_predictions.py | Score yesterday's NBA picks |
| `11:00` | Arena | arena-engine.py all | Triple Arena daily |
| `22:00` | B4 | betting_agent.py | Portfolio optimizer |

---

## Page 2: Improvements & Proposed Upgrades

### Per-Agent Improvements

| Agent | Current Issue | Proposed Fix | Priority |
|-------|--------------|--------------|----------|
| **O1 Brain** | Runs only on Claude Code CLI (session-dependent) | Deploy OpenClaw on HF Space for 24/7 autonomous brain | CRITICAL |
| **R1-R4 Research** | On-demand only, no scheduling | Integrate Gemini CLI for batch research when Claude is offline | HIGH |
| **E1 Feature Eng** | Manual implementation of proposals | Auto-implement proposals from R1 findings via Karpathy pattern | HIGH |
| **V1 Island Coord** | No cross-pollination between islands | Auto-migrate best individuals between S10-S15 weekly | MEDIUM |
| **V2 GPU Trainer** | Single-platform sessions | Multi-platform orchestration: Kaggle+Modal+Colab simultaneously | MEDIUM |
| **B1-B5 Betting** | Only moneyline bets live | Enable spread/totals/props from arena backtest winners | HIGH |
| **I1 Fleet Mgr** | Watchdog only restarts, no self-healing | Add auto-deploy on HF Space crash (rebuild from git) | MEDIUM |
| **F0-F6 Forge** | Pierre only, no other users | Onboard 3 demo users with stripe integration | LOW |

### Critical Upgrade: 24/7 Autonomous Brain via HF Space

**Problem**: O1 Brain only runs when Claude Code CLI is active. No autonomous decisions during sleep/offline.

**Solution**: Deploy OpenClaw (Kimi CLI) or Gemini CLI on a dedicated HF Space

```
HF Space: Nomos42/brain-24-7 (always-on, CPU)
  ├── OpenClaw CLI (Kimi token: kimi-cli-oauth)
  ├── Gemini CLI (gemini-cli-oauth)
  ├── Scheduler: run every 4h
  ├── Reads: all 6 HF /api/status endpoints
  ├── Writes: health-status.json, decisions.json
  ├── Triggers: POST /api/config on S10 (GA params)
  └── Fallback: if Kimi/Gemini fail → use cached last-good config
```

**Benefits**:
- Brain never sleeps: monitors + decides + acts 24/7
- Speed: decisions in seconds, not waiting for next CLI session
- Redundancy: Kimi primary, Gemini fallback, Claude Code for complex tasks
- Cost: $0 (free HF Space CPU + free Kimi/Gemini tokens)

### Key Docs Per Project

| Project | Key Docs | Location |
|---------|----------|----------|
| NBA Quant AI | CLAUDE.md, AGENTS.md, engine.py (6253 features) | mon-ipad, nomos-nba-agent |
| Political Alpha | CLAUDE.md, political_engine.py (13 categories) | nomos-political-alpha |
| Dashboard | /nba /political /rgwa /evolution /arena pages | nomos-dashboard |
| RGWA | CLAUDE.md, 5 agents (visual, music, video, quality, style) | rgwa |
| Forge Factory | FORGE-FACTORY-ARCHITECTURE.md, forge-users/ | mon-ipad |

### Full-Season Arena Results (994 games, 2025-10 to 2026-03)

**TOP 3 Profitable Strategies (out of 60 competitors)**:

| # | Competitor | Model | Strategy | $100→ | ROI | Sharpe | Bets |
|---|-----------|-------|----------|-------|-----|--------|------|
| 1 | catboost__confidence_scaled | CatBoost | Confidence Scaled | $181.68 | +81.7% | 1.38 | 1145 |
| 2 | catboost__first_half_sniper | CatBoost | 1st Half Sniper | $115.12 | +15.1% | 0.73 | 301 |
| 3 | extra_trees__underdog_specialist | Extra Trees | Underdog Specialist | $110.88 | +10.9% | 1.52 | 8 |

**Key Insight**: Only 5/60 competitors are profitable. CatBoost + Confidence Scaling dominates. Kelly strategies all bust (too aggressive with our Brier level). Conservative/underdog approaches survive.
