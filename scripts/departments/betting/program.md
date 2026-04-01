# Department: BETTING (D4)

## Mission
Maximize risk-adjusted returns by optimizing betting strategies, Kelly sizing, category allocation, and agent selection across NBA and political markets.

## Primary Metric
- **Name:** roi_pct
- **Current:** varies by agent (best ~202% simulated, live +3.92%)
- **Target:** > 5% live ROI, Sharpe > 1.5
- **Direction:** higher_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| sharpe_ratio | varies | > 1.5 |
| win_rate_pct | ~55% | > 55% |
| max_drawdown_pct | varies | < 15% |
| kelly_edge | ~0.03 | > 0.05 |
| profitable_categories | 60% | > 80% |
| live_bankroll | $103.92 | $500+ |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| kelly_fraction | 0.25 | [0.10, 0.75] | 0.05 |
| min_edge_threshold | 0.03 | [0.01, 0.10] | 0.005 |
| strategy_type | quarter_kelly | [quarter_kelly, half_kelly, full_kelly, fixed_pct] | categorical |
| category_weights | uniform | per-category [0.0, 2.0] | 0.1 |
| max_bet_pct | 0.05 | [0.02, 0.15] | 0.01 |
| min_odds | 1.50 | [1.20, 2.00] | 0.05 |
| max_odds | 5.00 | [3.00, 10.00] | 0.50 |
| agent_trust_weight | uniform | per-agent [0.0, 1.0] | 0.1 |
| bankroll_staging | none | [none, progressive, kelly_growth] | categorical |
| underdog_filter_prob | 0.45 | [0.35, 0.55] | 0.01 |
| drawdown_pause_pct | 0.20 | [0.10, 0.40] | 0.05 |

## Experiment Protocol
1. Load current best strategy config (kelly_fraction, category weights, agent trust)
2. Mutate one parameter from the search space
3. Run experiment (5 min budget): backtest mutated strategy on last 30 days of predictions
4. Measure roi_pct, sharpe_ratio, max_drawdown_pct on backtest window
5. If risk-adjusted score improved (ROI * sqrt(Sharpe) / max_drawdown) -> keep, commit
6. If not -> revert to previous strategy
7. Log result to data/departments/betting/karpathy-output.json

## Mutation Strategy
- **Type:** single-parameter perturbation with risk guard
- **Selection:** prioritize parameters correlated with largest ROI variance
- **Safety:** never increase kelly_fraction by more than 0.10 in one step
- **Category pruning:** auto-disable categories with < 40% win rate over 30+ bets
- **Agent rotation:** weight agents by trailing 7-day Sharpe ratio
- **Drawdown circuit breaker:** if drawdown > 20%, halve kelly_fraction for 48 hours

## Tools & Paths
- **Loop script:** scripts/departments/betting/betting-loop.sh
- **Output:** data/departments/betting/karpathy-output.json
- **Bankroll state:** data/nba-agent/bankroll-state.json
- **Backtest results:** data/nba-agent/backtest-results.json
- **Arena full season:** data/arena/nba-arena-full-season.json
- **Trading Floor v4:** data/arena/trading-floor-v4-latest.json
- **Trading engine:** scripts/trading-floor-v4.py
- **Odds data:** data/odds/, scripts/nba-daily-odds.py

## Success Criteria
- Live ROI > 5% sustained over 30+ bets
- Sharpe ratio > 1.5 over rolling 30-day window
- Max drawdown < 15% from peak
- Win rate > 52.4% (minimum for profitability at average odds)
- Zero losing categories remain active (auto-pruned within 1 week)
- Live bankroll shows consistent growth trajectory

## Dependencies
- **Upstream:** D2 (Engineering) provides prediction quality, D3 (Evolution) provides best models
- **Downstream:** D9 (Trading Floor) uses strategy recommendations
- **External:** Odds providers (daily scraping at 12:00/18:00), NBA schedule
- **Compute:** CPU only (backtest calculations, no ML)
