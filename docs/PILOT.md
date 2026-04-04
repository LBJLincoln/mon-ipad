# Nomos42 — Live Piloting Dashboard

> Auto-generated cross-repo command center. Read from iPad via GitHub.
> Last structure update: 2026-04-04

## Quick Links

| Resource | URL |
|----------|-----|
| Dashboard | nomos42.vercel.app |
| NBA Picks | nomos42.vercel.app/nba |
| Evolution | nomos42.vercel.app/evolution |
| Trading Floor | nomos42.vercel.app/trading-floor |
| Forge | nomos42.vercel.app/forge |
| Telegram | @Nomos42 (channel) / @Nomos42Bot (brain) |

## Repos (8)

| # | Repo | Purpose | Vercel | HF Space |
|---|------|---------|--------|----------|
| 1 | **mon-ipad** | Brain + control tower | nomos42.vercel.app | — |
| 2 | **nomos-nba-agent** | Engine + features + predict | — | S10-S15 |
| 3 | **nomos-political-alpha** | Political signal engine | — | — |
| 4 | **nomos-dashboard** | Web dashboard | nomos42.vercel.app | — |
| 5 | **rgwa** | AI art generation | — | — |
| 6 | **nomos-picks** | Public picks page | — | — |
| 7 | **nomos-pierre** | First user sandbox | — | — |
| 8 | **OddsHarvester** | Odds scraping | — | — |

## HF Spaces (6 Islands)

| Island | Space | Role | Target Brier |
|--------|-------|------|-------------|
| S10 | Nomos42/nba-quant | Exploitation (low mut) | < 0.222 |
| S11 | Nomos42/nba-quant-2 | Exploration (high mut) | < 0.220 |
| S12 | Nomos42/nba-evo-3 | ExtraTrees specialist | < 0.224 |
| S13 | Nomos42/nba-evo-4 | CatBoost specialist | < 0.222 |
| S14 | Nomos42/nba-evo-5 | LightGBM specialist | < 0.225 |
| S15 | Nomos42/nba-evo-6 | Wide search (pop=50) | < 0.221 |

## Departments (8 — Forge v19)

| Layer | Dept | Karpathy Loop | Key Metric |
|-------|------|---------------|-----------|
| **L1 Strategic** | — | Claude Code CLI + User | Vision, milestones |
| **L2 Application** | D1 Research | paper→extract→propose→measure | papers/week |
| | D2 Engineering | code→test→measure→keep/revert | Brier delta |
| | D3 Evolution | mutate→eval→select | gen/hr, best Brier |
| | D4 Product | build→test→ship→measure | features shipped |
| | D5 Business | price→onboard→convert→optimize | MRR, ARPU |
| | D6 Evaluation | audit→identify→fix→verify | calibration |
| **L3 Logistics** | D7 Infra | check→detect→fix→verify | uptime % |
| | D8 Finance | track→report→reconcile→forecast | burn rate |

## Trading Floor (5 AI Traders)

| # | Trader | Provider | Personality | Best Strategy |
|---|--------|----------|-------------|--------------|
| T1 | Gemini | Google | Analytical | half_kelly + confidence |
| T2 | OpenRouter | Multi | Diversified | diversified_flat |
| T3 | Claude | Anthropic | Conservative | quarter_kelly |
| T4 | Codex | OpenAI | Aggressive | full_kelly (ruined) |
| T5 | **Grok** | xAI | Contrarian | **value_hunter + underdog** |

## Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| VM | Google Cloud (1vCPU/969MB) | Control tower, crons, bots |
| Laptop | Acer Aspire 3 (Aurelien) | Local models, Claude Desktop |
| iPad | Termius | Piloting, monitoring |
| HF Spaces | 3 accounts (LBJLincoln, LBJLincoln26, Nomos42) | Evolution, agents |
| Supabase | ayqviq (pooler: xivvnr) | Data warehouse |
| Neo4j | 38c949a2 | Knowledge graph |
| GitHub | LBJLincoln | All repos |
| Vercel | nomos42 | Dashboard deploy |
| Kaggle | alexismoret6 | GPU evolution (P100) |
| Google Colab | — | GPU burst (T4) |

## Crons (Summary)

| Frequency | What | Script |
|-----------|------|--------|
| */5m | Watchdog (bots, server, spaces) | watchdog.sh |
| */30m | Agent swarm (NBA orchestrator) | agent-cron.sh |
| */30m | Odds monitor (game hours) | fetch_free_odds.py |
| */2h | Cross-repo health | cross-repo-monitor.py |
| */4h | Multi-brain (4h cycles) | multi-brain.sh |
| 9,21 UTC | Telegram daily report | daily_report.py |
| 22 UTC | Betting strategist | betting_agent.py |
| 10 UTC | Results evaluator | evaluate_predictions.py |
| 3 UTC | Kaggle GPU evolution | kaggle-gpu-evolution.sh |
| Hourly | Dept councils (research, eng, evo) | department-council.sh |
| */2h | Dept councils (betting, eval, infra) | department-council.sh |
| Daily | Strategic depts (comms, biz, finance) | department-council.sh |
| 23:30 | Daily summary | daily-summary.py |
| Sunday 4am | Cross-pollination | cross-pollinate.py |

## Storage Map

| System | Content | Access |
|--------|---------|--------|
| GitHub | All code, data JSON, configs | git pull |
| HF Spaces | Evolution state, models | HF API |
| Supabase | NBA data, experiments, proposals | SQL/API |
| Neo4j | Knowledge graph | Cypher/MCP |
| Google Drive | Backups | backup-to-drive.sh |
| /tmp/ on VM | Logs, research outputs | SSH |

## Key Metrics to Watch

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Best Brier (ATR) | 0.21570 | < 0.20 | IMPROVING |
| Fleet avg Brier | ~0.224 | < 0.215 | PLATEAU |
| Bankroll | $91.89 | $1,000 | DOWN (-8%) |
| Trading Floor #1 | Grok $3,687 | — | DOMINATING |
| Spaces UP | 6/6 | 6/6 | OK |
| Kaggle status | ERROR | RUNNING | NEEDS FIX |
| Dept councils | 8/8 active | 8/8 | OK |
| Bets/week | ~2 | 20-30 | LOW |

## How to Pilot

From iPad (Termius):
```bash
# Check everything
cat data/agent-health.json | python3 -m json.tool | head -20

# Trading floor status
cat data/arena/traders/grok-state.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Grok: ${d[\"bankroll_nba\"]:,.0f} | ROI: {(d[\"bankroll_nba\"]-100)/100*100:.0f}%')"

# Force a department council run
bash scripts/councils/department-council.sh research

# Send daily report NOW
source .env.local && python3 scripts/telegram/daily_report.py

# Check all repos health
python3 scripts/cross-repo-monitor.py
```
