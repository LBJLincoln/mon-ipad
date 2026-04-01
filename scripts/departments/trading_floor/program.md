# Department: TRADING FLOOR (D9)

## Mission
Run a 5-AI agent trading competition across NBA and political markets, optimizing each agent's personality, strategy, and risk parameters to maximize collective bankroll toward $1M.

## Primary Metric
- **Name:** best_bankroll
- **Current:** $302,155 (best agent, simulated)
- **Target:** $1,000,000
- **Direction:** higher_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| fleet_avg_roi_pct | ~120% | > 200% |
| best_agent_sharpe | ~12.0 | > 15.0 |
| surviving_agents | 5/5 | 5/5 |
| profitable_agents | 4/5 | 5/5 |
| nba_total_bets | 1000+ | continuous |
| political_etf_roi | 0% (pre-launch) | > 5% |
| agent_consensus_accuracy | monitoring | > 60% |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| t1_gemini_kelly_fraction | 0.25 | [0.10, 0.75] | 0.05 |
| t1_gemini_risk_tolerance | medium | [conservative, medium, aggressive] | categorical |
| t2_openrouter_model_rotation | fixed | [fixed, round_robin, best_recent] | categorical |
| t2_openrouter_kelly_fraction | 0.25 | [0.10, 0.75] | 0.05 |
| t3_claude_confidence_threshold | 0.55 | [0.50, 0.70] | 0.01 |
| t3_claude_kelly_fraction | 0.25 | [0.10, 0.75] | 0.05 |
| t4_codex_strategy_type | balanced | [balanced, value, volume, contrarian] | categorical |
| t4_codex_kelly_fraction | 0.25 | [0.10, 0.75] | 0.05 |
| t5_grok_underdog_bias | 0.10 | [0.0, 0.30] | 0.02 |
| t5_grok_kelly_fraction | 0.25 | [0.10, 0.75] | 0.05 |
| consensus_weight_method | equal | [equal, sharpe_weighted, roi_weighted, bayesian] | categorical |
| political_allocation_pct | 0 | [0, 30] | 5 |
| rebalance_frequency | daily | [daily, weekly, event_driven] | categorical |
| starting_capital | 100000 | [50000, 500000] | 50000 |

## Agent Profiles
| # | Agent | Provider | Personality | Sees | Decides |
|---|-------|----------|-------------|------|---------|
| T1 | Gemini | Google | Analytical | All predictions + all strategies + others' results | Betting strategy + Kelly sizing |
| T2 | OpenRouter | Multi-model | Diversified | Same | Same |
| T3 | Claude | Anthropic CLI | Conservative | Same | Same |
| T4 | Codex | OpenAI | Systematic | Same | Same |
| T5 | Grok | xAI | Contrarian | Same | Same |

## Experiment Protocol
1. Load current agent configs (personalities, Kelly fractions, strategy types)
2. Mutate one agent's parameter from the search space
3. Run experiment (5 min budget): simulate one day of trading with mutated config on historical data
4. Measure best_bankroll, fleet_avg_roi, agent survival
5. If best_bankroll increased or fleet risk decreased -> keep, commit config
6. If agent would go bankrupt under mutated config -> reject immediately
7. Log result to data/departments/trading_floor/karpathy-output.json

## Mutation Strategy
- **Type:** single-agent parameter perturbation
- **Selection:** rotate agents round-robin; prioritize worst-performing agent
- **Safety:** bankruptcy guard — reject any config that causes bankroll < $10,000 in backtest
- **Diversity:** maintain at least 3 distinct strategy types across 5 agents
- **Consensus:** when 4/5 agents agree on a bet, increase position size 1.5x
- **Political activation:** begin political trading when political_brier < 0.23 (from D7)
- **Rebalancing:** daily at market close, compare agent bankrolls and optionally rebalance

## Tools & Paths
- **Loop script:** (to be created) scripts/departments/trading_floor/trading-floor-loop.sh
- **Output:** data/departments/trading_floor/karpathy-output.json
- **Trading engine:** scripts/trading-floor-v4.py
- **Agent state:** data/arena/trading-floor-v4-latest.json
- **Full season data:** data/arena/nba-arena-full-season.json
- **NBA predictions:** data/nba-agent/predictions-*.json
- **Political signals:** data/departments/political/ (from D7)
- **Dashboard:** nomos-dashboard /nba route (Trading Floor tab)

## Success Criteria
- best_bankroll reaches $1,000,000 (simulated, from $100,000 start)
- All 5 agents survive (bankroll > $10,000) for full NBA season
- Fleet average ROI > 200%
- Best agent Sharpe > 15.0
- At least 1 agent profitable in political ETF trading
- Agent consensus bets (4/5 agree) have > 65% win rate
- Zero agent bankruptcies

## Dependencies
- **Upstream:** D2 (Engineering) for predictions, D3 (Evolution) for model quality, D4 (Betting) for strategy optimization, D7 (Political) for political signals
- **Downstream:** Dashboard displays leaderboard, Telegram reports daily results
- **External:** AI provider APIs (Google, OpenRouter, Anthropic, OpenAI, xAI), odds data
- **Compute:** CPU only (API calls + strategy computation, no ML training)
