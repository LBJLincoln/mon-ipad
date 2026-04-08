# Nomos42 Agent Swarm Architecture v3.0
# 25 specialized agents across 9 departments
# Shared by NBA Quant + Political Alpha (project-agnostic)
# Updated: 2026-03-28

## Department 1: RESEARCH (4 agents)
| # | Agent | Type | Trigger | Purpose |
|---|-------|------|---------|---------|
| 1 | paper-scout | research-analyst | cron 6h | Search arXiv, SSRN, MDPI for new prediction/betting papers |
| 2 | repo-scout | repo-scout | cron 12h | Find GitHub repos, HF models, Kaggle notebooks, free data |
| 3 | strategy-researcher | karpathy-researcher | on-demand | Deep-dive specific technique (Ridge-Kelly, Venn-Abers, etc.) |
| 4 | data-scout | research-analyst | cron 24h | Find new FREE data sources (player stats, props, tracking, social) |

## Department 2: ENGINEERING (5 agents)
| # | Agent | Type | Trigger | Purpose |
|---|-------|------|---------|---------|
| 5 | feature-engineer | feature-engineer | on-demand | Propose + implement new feature categories in engine.py |
| 6 | test-creator | general-purpose | on-demand | Write unit/integration/data-leakage tests for new features |
| 7 | test-runner | general-purpose | cron 4h | Run full test suite (17+ tests), report failures |
| 8 | bug-fixer | general-purpose | on-demand | Diagnose + fix test failures and production bugs |
| 9 | code-optimizer | general-purpose | weekly | Profile bottlenecks, optimize feature engine, reduce compute |

## Department 3: EVOLUTION (3 agents)
| # | Agent | Type | Trigger | Purpose |
|---|-------|------|---------|---------|
| 10 | evolution-monitor | evolution-optimizer | cron 2h | Monitor all 6 HF islands + Kaggle, detect stagnation |
| 11 | evolution-optimizer | evolution-optimizer | on-demand | Tune GA params, inject diversity, restart stuck islands |
| 12 | karpathy-loop | general-purpose | cron (Kaggle 9h) | Autonomous research iterations on GPU |

## Department 4: BETTING & STRATEGY (5 agents)
| # | Agent | Type | Trigger | Purpose |
|---|-------|------|---------|---------|
| 13 | odds-monitor | market-analyst | cron 30min (game days) | Fetch live odds, detect steam moves, CLV, line shopping |
| 14 | betting-strategist | market-analyst | daily 5pm ET | Portfolio Kelly, multi-market bets (ML+ATS+O/U+2H+props) |
| 15 | strategy-tester | general-purpose | on-demand | Backtest new strategies against historical data, validate edge |
| 16 | strategy-corrector | general-purpose | on-demand | Diagnose losing strategies, fix sizing/filters, recalibrate |
| 17 | halftime-scorer | general-purpose | live (every 2min during games) | 2H live re-scoring pipeline, in-game bet signals |

## Department 5: EVALUATION (2 agents)
| # | Agent | Type | Trigger | Purpose |
|---|-------|------|---------|---------|
| 18 | results-evaluator | general-purpose | daily 10am UTC | Score predictions vs actuals, update P&L, Brier, Sharpe |
| 19 | performance-analyst | general-purpose | weekly | Full review: calibration curves, bet type breakdown, Jensen alpha |

## Department 6: INFRASTRUCTURE (2 agents)
| # | Agent | Type | Trigger | Purpose |
|---|-------|------|---------|---------|
| 20 | infra-agent | general-purpose | cron */30 | Monitor GPU credits (Kaggle/Colab/Modal), auto-restart platforms |
| 21 | dashboard-sync | general-purpose | cron 1h | Push data to dashboard, update JSON endpoints, cross-repo health |

## Department 7: OVERSIGHT (1 agent)
| # | Agent | Type | Trigger | Purpose |
|---|-------|------|---------|---------|
| 22 | orchestrator | nba-brain | cron 4h | Health check ALL agents, restart failures, make decisions |

## Department 8: FLEET MONITORING (3 agents — Pierre)
| # | Agent | Type | Trigger | Purpose |
|---|-------|------|---------|---------|
| 23 | pierre-usage-monitor | general-purpose | cron */30 | Track Claude Code CLI quota (daily/weekly cost) |
| 24 | pierre-practice-monitor | general-purpose | cron */30 | Analyze usage patterns, suggest optimizations |
| 25 | pierre-infra-monitor | general-purpose | cron */30 | Track MacBook RAM/CPU, determine offloadable compute |

Implementation: `scripts/agents/pierre-monitor.py` (all 3 in one file)
Cron: `*/30 * * * * python3 ~/mon-ipad/scripts/agents/pierre-monitor.py`
Output: `data/fleet/pierre-monitor.json`

## Cross-Project Config

Each agent reads project config to adapt behavior:

```json
{
  "nba": {
    "engine": "nomos-nba-agent/features/engine.py",
    "predictions_table": "nba_predictions",
    "spaces": ["nba-quant", "nba-quant-2", "nba-evo-3", "nba-evo-4", "nba-evo-5", "nba-evo-6"],
    "kaggle_kernels": ["nba-karpathy-loop", "nba-season-backtest"],
    "betting_markets": ["moneyline", "ats", "totals", "1h_spread", "2h_spread", "2h_ou", "team_totals", "player_props", "value_dogs"],
    "betting_agent": "scripts/betting_agent.py",
    "totals_model": "scripts/totals_model.py",
    "halftime_model": "scripts/halftime_rescore.py",
    "target_brier": 0.20,
    "current_brier": 0.21570,
    "current_roi": 3.92,
    "features": 5859,
    "categories": 41
  },
  "political": {
    "engine": "nomos-political-alpha/features/engine.py",
    "predictions_table": "political_predictions",
    "spaces": ["nomos-political-alpha"],
    "kaggle_kernels": ["political-alpha-karpathy-loop"],
    "betting_markets": ["stock_direction", "sector_alpha", "event_binary", "polymarket_arb"],
    "betting_agent": "scripts/political_betting_agent.py",
    "data_sources": ["FEC", "Federal Register", "SEC EDGAR", "Polymarket", "yfinance", "FRED", "CoinGecko", "USAspending"],
    "target_brier": 0.20,
    "current_brier": null,
    "features": 2400,
    "categories": 13
  }
}
```

## Agent Cron Schedule (consolidated)

```
# Every 2 min (game hours 23:00-05:00 UTC = 7pm-1am ET)
*/2 23,0,1,2,3,4,5 * * *  halftime-scorer (NBA live 2H bets)

# Every 5 min
*/5 * * * *                watchdog (VM health)

# Every 30 min
*/30 * * * *               agent-cron.sh (NBA orchestrator — keepalive, odds, predictions)
15,45 * * * *              infra-agent (GPU credits, platform health)
*/30 * * * *               political-fast-fetch (signals + polymarket)

# Every 2 hours
0 */2 * * *                cross-repo-monitor (health JSON)
0 */2 * * *                evolution-monitor (6 islands + Kaggle stagnation)
30 */2 * * *               social-signals (Reddit/YouTube/Twitter)

# Every 4 hours
0 */4 * * *                test-runner (full test suite)

# Every 6 hours
0 */6 * * *                political-full-fetch
0 */6 * * *                paper-scout (new papers)

# Daily
0 3 * * *                  kaggle-gpu-evolution (daily launch)
0 10 * * *                 results-evaluator (score yesterday)
0 12 * * *                 data-scout (new data sources)
0 17 * * *                 betting-strategist (daily bet slips)
0 22 * * 1-5               political-insider-fetch
30 22 * * 1-5              political-prices-fetch
0 23 * * *                 git-auto-commit

# Weekly
0 6 * * 1                  performance-analyst (Monday review)
0 8 * * 1                  code-optimizer (Monday optimization)
0 12 * * 3                 repo-scout (Wednesday scan)
```

## Skills (user-invocable)

| Skill | Agents Used | Purpose |
|-------|-------------|---------|
| `/karpathy-loop` | 1,2,3,5 | Full research cycle → feature proposals → quick wins |
| `/daily-edge` | 13,14,17 | Daily predictions + multi-market bets + Kelly sizing |
| `/progress-10pct` | 10,11,5 | Target 10% improvement in weakest metric |
| `/spaces-health` | 10,20 | Health check all HF evolution islands |
| `/evolve-report` | 10,19 | Comprehensive evolution progress report |
| `/agent-review` | 22,19 | Weekly agent performance review (Jensen HR model) |
| `/cross-repo-audit` | 21,22 | Audit all repos for consistency |
| `/multi-market-scan` | 13,14,15 | Scan all bet types for today's edge |
| `/political-scan` | 1,4,14 | Political signal scan + affected stocks |
| `/backtest-strategy` | 15,16 | Full strategy backtest on historical data |

## Implementation Status

| Agent | File | Status |
|-------|------|--------|
| 1 paper-scout | Claude Code research-analyst agent | ACTIVE |
| 2 repo-scout | Claude Code repo-scout agent | ACTIVE |
| 3 strategy-researcher | Claude Code karpathy-researcher agent | ACTIVE |
| 4 data-scout | Claude Code research-analyst agent | NEW |
| 5 feature-engineer | Claude Code feature-engineer agent | ACTIVE |
| 6 test-creator | scripts/agents/test_data_leakage.py | PARTIAL |
| 7 test-runner | scripts/agents/test_data_leakage.py | ACTIVE (17 tests) |
| 8 bug-fixer | Claude Code general-purpose agent | ON-DEMAND |
| 9 code-optimizer | Claude Code general-purpose agent | NEW |
| 10 evolution-monitor | scripts/agents/orchestrator.py | ACTIVE |
| 11 evolution-optimizer | Claude Code evolution-optimizer agent | ACTIVE |
| 12 karpathy-loop | scripts/kaggle/nba_karpathy_loop.py | ACTIVE |
| 13 odds-monitor | scripts/nba-daily-odds.py | ACTIVE |
| 14 betting-strategist | scripts/betting_agent.py | ACTIVE |
| 15 strategy-tester | scripts/multi_market_backtest.py | NEW |
| 16 strategy-corrector | (auto from #15 results) | NEW |
| 17 halftime-scorer | scripts/halftime_rescore.py | BUILDING |
| 18 results-evaluator | scripts/evaluate_predictions.py | ACTIVE |
| 19 performance-analyst | (weekly review template) | PARTIAL |
| 20 infra-agent | scripts/infra-agent.sh | ACTIVE |
| 21 dashboard-sync | scripts/autonomous-cycle.sh | ACTIVE |
| 22 orchestrator | scripts/agents/orchestrator.py | ACTIVE |
| 23 pierre-usage-monitor | scripts/agents/pierre-monitor.py | NEW |
| 24 pierre-practice-monitor | scripts/agents/pierre-monitor.py | NEW |
| 25 pierre-infra-monitor | scripts/agents/pierre-monitor.py | NEW |
