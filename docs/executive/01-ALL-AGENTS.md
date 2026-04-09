# NOMOS42 — Complete Agent Registry
> 30 Agents | 9 Departments | Updated 2026-04-04

## Agent Matrix

### Department: Research (4 agents)

| ID | Name | Type | Location | Status | Trigger |
|----|------|------|----------|--------|---------|
| R1 | Research Analyst | Claude subagent | CLI | ON-DEMAND | /karpathy-loop |
| R2 | Karpathy Researcher | Claude subagent | CLI | ON-DEMAND | /karpathy-loop |
| R3 | Repo Scout | Claude subagent | CLI + HF | DEPLOYING | research-radar space |
| R4 | Market Analyst | Claude subagent | CLI | ON-DEMAND | /daily-edge |

**Outputs**: Research proposals -> Supabase `research_proposals` table
**Inputs**: ArXiv, GitHub, HuggingFace, web search
**Coordination**: R1 findings feed E1 (feature engineering). R3 monitors continuously.

### Department: Engineering (5 agents)

| ID | Name | Type | Location | Status | Trigger |
|----|------|------|----------|--------|---------|
| E1 | Feature Engineer | Claude subagent | CLI | ON-DEMAND | /karpathy-loop |
| E2 | Evolution Optimizer | Claude subagent | CLI | ON-DEMAND | /evolve-report |
| E3 | Predictions | Script + HF | VM + HF | ACTIVE | predictions-monitor space |
| E4 | Backtest | Script | VM/Kaggle | ON-DEMAND | Manual |
| E5 | Data Pipeline | Script | VM cron | ACTIVE | */30 cron |

**Outputs**: engine.py updates, predictions, backtest results
**Key files**: `features/engine.py` (6253 features), `predict_today.py`, `multi_market_backtest.py`

### Department: Evolution (3 agents)

| ID | Name | Type | Location | Status | Trigger |
|----|------|------|----------|--------|---------|
| V1 | Island Coordinator | HF Space | LBJLincoln | DEPLOYING | island-coordinator space |
| V2 | GPU Trainer | Kaggle/Colab | Remote | ON-DEMAND | kaggle-gpu-evolution.sh |
| V3 | Political Evo | HF Space | LBJLincoln26 | DEPLOYING | political-monitor space |

**Outputs**: Evolved model configs, best individuals, Brier scores
**Key spaces**: S10-S15 (NBA), P1-P4 (Political)

### Department: Betting (5 agents)

| ID | Name | Type | Location | Status | Trigger |
|----|------|------|----------|--------|---------|
| B1 | Odds Monitor | Script + HF | VM + HF | ACTIVE | */30 cron + betting-monitor |
| B2 | Value Detector | Script | VM | ACTIVE | Part of betting_agent.py |
| B3 | Kelly Sizer | Script | VM | ACTIVE | Part of betting_agent.py |
| B4 | Strategist | Script | VM | ACTIVE | Daily 22:00 cron |
| B5 | Evaluator | Script + HF | VM + HF | ACTIVE | Daily 10:00 cron |

**Outputs**: picks, bankroll state, ROI tracking
**Key files**: `betting_agent.py`, `evaluate_predictions.py`, `fetch_free_odds.py`

### Department: Evaluation (2 agents)

| ID | Name | Type | Location | Status | Trigger |
|----|------|------|----------|--------|---------|
| Q1 | Quality Tracker | HF Space | LBJLincoln26 | DEPLOYING | quality-tracker space |
| Q2 | Arena Benchmark | Script | VM | ACTIVE | Daily 11:00 cron |

**Outputs**: Brier scores, Arena rankings, ATR tracking
**Key files**: `arena-engine.py`, `arena-full-season.py`

### Department: Infrastructure (2 agents)

| ID | Name | Type | Location | Status | Trigger |
|----|------|------|----------|--------|---------|
| I1 | Fleet Manager | HF Space + cron | LBJLincoln + VM | DEPLOYING | fleet-monitor space + watchdog */5 |
| I2 | Infra Agent | Script | VM cron | ACTIVE | infra-agent.sh */30 |

**Outputs**: health status, auto-restarts, backup confirmations
**Key files**: `watchdog.sh`, `infra-agent.sh`, `cross-repo-monitor.py`

### Department: Oversight (1 agent)

| ID | Name | Type | Location | Status | Trigger |
|----|------|------|----------|--------|---------|
| O1 | Brain | HF Space + CLI | Nomos42 + VM | RUNNING | 4h cycle + remote trigger |

**Outputs**: Decisions (tune GA, inject diversity, restart, checkpoint)
**Key files**: `hf-brain/app.py`, `multi-brain.sh`
**AI Chain**: Gemini -> OpenAI -> Rule-based (Claude Code for complex tasks)

### Department: Forge Factory (7 agents)

| ID | Name | Type | Location | Status | Trigger |
|----|------|------|----------|--------|---------|
| F0 | Strategy Definer | Planned | - | NOT DEPLOYED | @Forge42Bot intake |
| F1 | Product Builder | Planned | - | NOT DEPLOYED | Layer 1 swarm |
| F2 | Business Strategist | Planned | - | NOT DEPLOYED | Layer 1 swarm |
| F3 | Communication Manager | Planned | - | NOT DEPLOYED | Layer 1 swarm |
| F4 | Infra Manager | Planned | - | NOT DEPLOYED | Layer 2 |
| F5 | Finance Comptable | Planned | - | NOT DEPLOYED | Layer 2 |
| F6 | Admin/Legal Compliance | Planned | - | NOT DEPLOYED | Layer 2 |

**STATUS: ARCHITECTURE ONLY** — FORGE-FACTORY-ARCHITECTURE.md defines the 4 layers and 7 agents, Pierre is test user with directory structure, @Forge42Bot running, but NO autonomous agent code exists.

---

## Data Flow

```
EXTERNAL DATA
    ├── nba_api (box scores, tracking, hustle, drives)
    ├── FEC API (donors, PAC)
    ├── SEC EDGAR (Form 4, insider)
    ├── Polymarket (markets, prices)
    ├── Congress.gov (committees, hearings)
    ├── Reddit/Twitter/YouTube (social sentiment)
    ├── FRED/CoinGecko/yfinance (macro)
    ├── SBR/BetMGM (odds)
    └── ArXiv/GitHub/HF (research)
           │
           ▼
    ENGINE (features/engine.py)
    NBA: 6253 features, 46 categories
    Political: 743 features, 22 categories
           │
           ▼
    EVOLUTION (HF Spaces)
    6 NBA islands + 4 Political islands
    Genetic algorithm: mutate → evaluate → select
           │
           ▼
    PREDICTIONS (predict_today.py)
    Best evolved config → predict each game
           │
           ▼
    BETTING (betting_agent.py)
    Value detection → Kelly sizing → picks
           │
           ▼
    EVALUATION (evaluate_predictions.py)
    Score vs actual results → update bankroll
           │
           ▼
    MONITORING (7 HF monitoring spaces)
    Fleet, islands, betting, quality, research, predictions, political
           │
           ▼
    BRAIN (nomos42-brain)
    Analyze all data → decide → act → alert
```

## Deployment Summary

| Deployed | Count | Where |
|----------|-------|-------|
| HF Spaces (evolution) | 10 | Nomos42 (6 NBA + 4 political) |
| HF Spaces (monitoring) | 8 | Brain(1) + 7 deploying |
| VM crons | 17 | termius VM |
| Telegram bots | 5 | VM (watchdog managed) |
| Dashboard | 1 | Vercel |
| CLI agents | 8 | Claude Code subagents |
| Forge agents | 0/7 | NOT DEPLOYED |
| **Total active** | **~42** | |
