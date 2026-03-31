# NOMOS42 — Agent Ecosystem v4.0
> 8 Departments | 30 Agents | 31 Skills | 19 Crons | 20 HF Spaces | 5 Bots
> Last updated: 2026-03-31

## Page 1: All Agents, Skills & Interactions

### Department Map

| Dept | Agents | Mission | Key Scripts |
|------|--------|---------|-------------|
| **Research** | R1 Analyst, R2 Karpathy, R3 Scout, R4 Market | Papers, features, repos, odds | claude subagents, research-cron.sh |
| **Engineering** | E1 Feature Eng, E2 Evolution Opt, E3 Predictions, E4 Backtest, E5 Data Pipeline | engine.py, predict, backtest | features/engine.py, predict_today.py |
| **Evolution** | V1 Island Coord, V2 GPU Trainer, V3 Political Evo | 6 NBA + 4 PA HF islands, GPU | HF Spaces, Kaggle, Modal, Colab |
| **Betting** | B1 Odds, B2 Value, B3 Kelly, B4 Strategist, B5 Evaluator | Live odds, sizing, portfolio | betting_agent.py, evaluate_predictions.py |
| **Evaluation** | Q1 Quality, Q2 Benchmark | Brier, SHAP, ATR tracking | Arena engine |
| **Infrastructure** | I1 Fleet Mgr, I2 Infra Agent | VM, HF, GPU, backups | watchdog.sh, infra-agent.sh, auto-deploy-engine.sh |
| **Oversight** | O1 Brain | CEO: monitors + decides + directs | @Nomos42Bot, remote trigger |
| **Monitoring** | M1-M7 Fleet/Island/Betting/Quality/Research/Predictions/Political | 7 HF Spaces monitoring all systems | hf-agents/ |
| **Forge** | F0-F6 (7 per-user) | SaaS product factory | forge-users/{name}/ |

### HF Spaces (20 total)

| # | Space | Account | Role | Type |
|---|-------|---------|------|------|
| S10 | Nomos42/nba-quant | Nomos42 | NBA exploitation (mut=0.09, feat=63) | Evolution |
| S11 | Nomos42/nba-quant-2 | Nomos42 | NBA exploration (mut=0.15, feat=80) | Evolution |
| S12 | Nomos42/nba-evo-3 | Nomos42 | Extra-trees specialist (mut=0.08, feat=60) | Evolution |
| S13 | Nomos42/nba-evo-4 | Nomos42 | CatBoost specialist (mut=0.10, feat=66) | Evolution |
| S14 | Nomos42/nba-evo-5 | Nomos42 | LightGBM specialist (mut=0.08, feat=55) | Evolution |
| S15 | Nomos42/nba-evo-6 | Nomos42 | Wide search (mut=0.18, feat=80, pop=50) | Evolution |
| P1-P4 | Nomos42/political-* | Nomos42 | Political Alpha evolution (4 islands) | Evolution |
| -- | Nomos42/nomos42-brain | Nomos42 | 24/7 AI decisions (O1 Brain) | Brain |
| M1 | LBJLincoln/fleet-monitor | LBJLincoln | All services health | Monitoring |
| M2 | LBJLincoln/island-coordinator | LBJLincoln | Evolution progress + cross-pollination | Monitoring |
| M3 | LBJLincoln/betting-monitor | LBJLincoln | Odds + bankroll tracking | Monitoring |
| M4 | LBJLincoln26/quality-tracker | LBJLincoln26 | Brier score tracking | Monitoring |
| M5 | LBJLincoln26/research-radar | LBJLincoln26 | Papers + repos scanning | Monitoring |
| M6 | LBJLincoln26/predictions-monitor | LBJLincoln26 | Daily predictions status | Monitoring |
| M7 | LBJLincoln26/political-monitor | LBJLincoln26 | Political signals tracking | Monitoring |
| -- | (2 legacy) | Various | Paused/archived | Legacy |

### Agent Detail — How They Interact

```
USER ─── Telegram / Dashboard / Colab
  │
  ├── @Nomos42Bot (O1 Brain) ──── Remote Trigger (4h) ──── Claude Code CLI
  │       │ directs all agents
  │       ├── R1-R4 Research ──── WebSearch, papers, repos ──► proposals to E1
  │       │      └── research-cron.sh (2x/day) ──► M5 research-radar
  │       ├── E1-E5 Engineering ──── engine.py (6253 features) ──► HF Spaces
  │       │      └── auto-deploy-engine.sh (*/6h) ──► sync to all islands
  │       ├── V1-V3 Evolution ──── S10-S15 + P1-P4 ──── Kaggle/Modal/Colab
  │       │      └── cross-pollinate.py (weekly) ──► M2 island-coordinator
  │       ├── B1-B5 Betting ──── odds ──► value bets ──► Kelly ──► picks
  │       │      └── M3 betting-monitor (live tracking)
  │       ├── Q1-Q2 Evaluation ──── Brier scores, Arena results
  │       │      └── M4 quality-tracker (continuous)
  │       └── I1-I2 Infra ──── watchdog, keepalive, backup
  │              └── M1 fleet-monitor (all services health)
  │
  ├── M1-M7 Monitoring Fleet ──── 7 HF Spaces (always-on, CPU)
  │       ├── M1 fleet-monitor ──────── services + islands up/down
  │       ├── M2 island-coordinator ─── evolution progress + cross-pollination
  │       ├── M3 betting-monitor ────── odds pipeline + bankroll state
  │       ├── M4 quality-tracker ────── Brier scores + model quality
  │       ├── M5 research-radar ─────── papers + repos + proposals
  │       ├── M6 predictions-monitor ── daily prediction pipeline
  │       └── M7 political-monitor ──── political signals + alpha
  │
  ├── @NomosNBABot (SaaS) ──── free/scout/edge/whale tiers
  ├── @StupidPoliticalBot (SaaS) ──── free/scout/edge/whale tiers
  ├── @Forge42Bot (SaaS) ──── F0-F6 factory agents per user
  └── @RGWAbot (Art) ──── music/video/image generation
```

### All 31 Skills (Slash Commands)

| # | Command | Category | Purpose |
|---|---------|----------|---------|
| 1-8 | `/sp-brainstorm` `/sp-write-plan` `/sp-execute-plan` `/sp-test-driven-development` `/sp-subagent-driven-development` `/sp-dispatching-parallel-agents` `/sp-systematic-debugging` `/sp-verification-before-completion` | Superpowers | Planning, execution, TDD, debugging |
| 9-20 | `/gstack-ship` `/gstack-qa` `/gstack-review` `/gstack-browse` `/gstack-canary` `/gstack-careful` `/gstack-guard` `/gstack-cso` `/gstack-investigate` `/gstack-learn` `/gstack-plan-eng-review` `/gstack-retro` | GStack | Deploy, QA, security, monitoring |
| 21-27 | `/karpathy-loop` `/progress-10pct` `/evolve-report` `/agent-review` `/spaces-health` `/cross-repo-audit` `/daily-edge` | Nomos42 | Evolution, betting, health |
| 28 | `/deploy-hf` | Infra | Deploy engine.py + configs to all HF Spaces |
| 29 | `/fleet-status` | Monitoring | Health check of all 20 HF Spaces + 5 bots |
| 30 | `/forge-intake` | Forge | Onboard new Forge user (profile + tier + agents) |
| 31 | `/political-signals` | Political | Scan political data sources for alpha signals |

### Cron Schedule (19 active jobs)

| Freq | Agent | Script | Purpose |
|------|-------|--------|---------|
| `*/5` | I1 | watchdog.sh + start_bots.sh | Keep bots + services alive |
| `*/30` | Swarm | agent-cron.sh | NBA orchestrator (keepalive, predict, eval) |
| `*/30` | I2 | infra-agent.sh | Monitor + auto-restart GPU platforms |
| `*/30` | B1 | fetch_free_odds.py (game hours) | Live NBA odds |
| `*/30` | PA | political agent-cron.sh | Political Alpha swarm |
| `2h` | I1 | cross-repo-monitor.py | Cross-repo health |
| `4h` | O1 | Remote trigger (Sonnet 4.6) | Multi-brain AI cycle |
| `*/6h` | I1 | auto-deploy-engine.sh | Engine sync to all HF Spaces |
| `6h` | E5 | fetch_political_data.py --all | Full political data |
| `6:00,18:00` | R1-R4 | research-cron.sh | Research scanning (papers, repos, proposals) |
| `3:00` | V2 | kaggle-gpu-evolution.sh | Daily Kaggle GPU evolution |
| `3:00` | I2 | backup-to-drive.sh | Daily Google Drive backup |
| `10:00` | B5 | evaluate_predictions.py | Score yesterday's NBA picks |
| `11:00` | Arena | arena-engine.py all | Triple Arena daily |
| `22:00` | B4 | betting_agent.py | Portfolio optimizer |
| `Sun 4:00` | V1 | cross-pollinate.py | Weekly island migration (best individuals between S10-S15) |

---

## Page 2: Improvements & Proposed Upgrades

### Per-Agent Improvements

| Agent | Status | Fix Applied | Notes |
|-------|--------|-------------|-------|
| **O1 Brain** | FIXED | Deployed to Nomos42/nomos42-brain | 24/7 autonomous decisions on HF Space (Gradio 5.49.1, cpu-basic) |
| **R1-R4 Research** | FIXED | research-cron.sh every 12h + research-radar space | Automated paper/repo scanning at 6:00 and 18:00 UTC |
| **V1 Island Coord** | FIXED | cross-pollinate.py weekly + island-coordinator space | Best individuals migrate between S10-S15 every Sunday at 4:00 |
| **I1 Fleet Mgr** | FIXED | fleet-monitor space + auto-deploy-engine.sh | Auto-deploy engine.py to all islands every 6h + health dashboard |
| **E1 Feature Eng** | PENDING | Auto-implement proposals from R1 via Karpathy pattern | Awaiting Karpathy loop integration |
| **V2 GPU Trainer** | PENDING | Multi-platform orchestration: Kaggle+Modal+Colab | Lightning.ai credits arrive Apr 1 |
| **B1-B5 Betting** | PENDING | Enable spread/totals/props from arena backtest winners | Monte Carlo shows +24.1% ROI on UNDER bets |
| **F0-F6 Forge** | PARTIAL | Architecture done, Pierre test user active | F1-F6 agents not yet implemented as autonomous code |

### Monitoring Fleet Architecture

```
Nomos42/nomos42-brain (O1 Brain, always-on)
  │ reads /api/status from all islands every 4h
  │
  ├── M1 fleet-monitor ──── pings all 20 HF Spaces
  │     └── alerts on downtime, auto-triggers rebuild
  ├── M2 island-coordinator ──── tracks generation counts, best Brier
  │     └── cross-pollinate.py migrates top individuals weekly
  ├── M3 betting-monitor ──── odds pipeline freshness, bankroll state
  │     └── alerts if odds stale >2h on game days
  ├── M4 quality-tracker ──── Brier score trend, model drift
  │     └── flags if Brier degrades >0.005 from ATR
  ├── M5 research-radar ──── new papers, GitHub repos, HF models
  │     └── feeds proposals to E1 Feature Engineering
  ├── M6 predictions-monitor ──── daily prediction pipeline status
  │     └── verifies predictions posted before game time
  └── M7 political-monitor ──── political data source freshness
        └── tracks FEC, SEC, Polymarket signal quality
```

### Key Docs Per Project

| Project | Key Docs | Location |
|---------|----------|----------|
| NBA Quant AI | CLAUDE.md, AGENTS.md, engine.py (6253 features) | mon-ipad, nomos-nba-agent |
| Political Alpha | CLAUDE.md, political_engine.py (22 categories, 743 features) | nomos-political-alpha |
| Dashboard | /nba /political /rgwa /evolution /arena pages | nomos-dashboard |
| RGWA | CLAUDE.md, 5 agents (visual, music, video, quality, style) | rgwa |
| Forge Factory | FORGE-FACTORY-ARCHITECTURE.md, forge-users/ | mon-ipad |

### Current Metrics

| Metric | Value | Target | Gap |
|--------|-------|--------|-----|
| NBA Brier (ATR) | 0.21570 | < 0.20 | 0.01570 |
| SOTA (Montrucchio) | 0.199 | -- | 0.01670 |
| Walk-forward Brier | 0.22447 | < 0.21 | 0.01447 |
| Betting ROI | +3.92% | > 5% | 1.08% |
| Bankroll | $103.92 | -- | -- |
| Sharpe | 4.57 | > 1.5 | ACHIEVED |
| Feature Engine | v3.1-46cat (6253 features) | -- | -- |
| Political Engine | v3.1-22cat (743 features) | -- | -- |

### Full-Season Arena Results (994 games, 2025-10 to 2026-03)

**TOP 3 Profitable Strategies (out of 60 competitors)**:

| # | Competitor | Model | Strategy | $100-> | ROI | Sharpe | Bets |
|---|-----------|-------|----------|-------|-----|--------|------|
| 1 | catboost__confidence_scaled | CatBoost | Confidence Scaled | $181.68 | +81.7% | 1.38 | 1145 |
| 2 | catboost__first_half_sniper | CatBoost | 1st Half Sniper | $115.12 | +15.1% | 0.73 | 301 |
| 3 | extra_trees__underdog_specialist | Extra Trees | Underdog Specialist | $110.88 | +10.9% | 1.52 | 8 |

**Key Insight**: Only 5/60 competitors are profitable. CatBoost + Confidence Scaling dominates. Kelly strategies all bust (too aggressive with our Brier level). Conservative/underdog approaches survive.
