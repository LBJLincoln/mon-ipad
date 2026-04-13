# What Works — Empirically Validated

> Auto-generated from experiment data on 2026-04-13 08:25 UTC
> Only includes findings backed by measured improvement

## NBA — Mutation Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| swap_features | 5 | 0 | 0% | +0.03617 |
| change_max_depth | 5 | 0 | 0% | +0.00430 |
| change_min_samples_leaf | 11 | 0 | 0% | +0.02529 |
| change_model | 4 | 0 | 0% | +0.02562 |
| change_max_features_ratio | 6 | 0 | 0% | +0.03118 |
| add_features | 7 | 0 | 0% | +0.02562 |
| remove_features | 7 | 0 | 0% | +0.02715 |
| change_n_estimators | 5 | 0 | 0% | +0.00183 |

## POLITICAL — Mutation Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_n_estimators | 8 | 0 | 0% | +0.00451 |
| add_features | 12 | 0 | 0% | +0.01773 |
| change_max_depth | 4 | 0 | 0% | +0.01646 |
| change_max_features_ratio | 6 | 0 | 0% | +0.02298 |
| swap_features | 7 | 0 | 0% | +0.01901 |
| change_min_samples_leaf | 4 | 0 | 0% | +0.01035 |
| change_model | 5 | 0 | 0% | +0.05229 |
| remove_features | 4 | 0 | 0% | +0.02737 |

## Arena — Proven Insights

1. value_hunter with contrarian personality is the #1 strategy (Grok $3,687 from $100)
2. half_kelly is the best Kelly variant: 50% fraction balances growth vs survival (Gemini +$1530)
3. full_kelly is suicide for most personalities (Codex 100% drawdown) unless paired with high min_edge
4. quarter_kelly is ultra-safe but slow — Claude survived everything but only 3.2x
5. Alt spreads (home_big + away_big) are the #1 profitable category across ALL traders
6. team_total_home_under has 59-64% win rate across all traders — hidden gem
7. team_total_home_over has 74-81% win rate but low volume — needs more action
8. h1_ml_away has near 100% win rate (tiny sample) — worth exploring as specialist
9. ml_home is a trap: looks safe but negative profit for 4 of 5 traders
10. spread_home and spread_away are break-even at best — avoid as primary
11. Sharpe ratio matters more than raw ROI: Claude (4.423) outperformed Gemini (2.660) risk-adjusted
12. Conference matchups have higher edge than division games
13. Fewer, higher-conviction bets beat high-volume spray (Grok 1228 bets vs Codex 4232)
14. elo_baseline model surprisingly profitable for Grok (+$1996) — simple models + good strategy > complex models + bad strategy
15. stacking_meta best model for Gemini (+$909) — ensemble models reward analytical personality
16. Max drawdown tolerance: >50% is recoverable (Grok 53.5%), >75% is dangerous (Gemini 77%), >90% is terminal (Codex 100%)

## Arena — Optimal Parameters

- **kelly_fraction_range**: [0.25, 0.5]
- **min_edge_threshold**: 0.03
- **max_bet_pct**: 0.12
- **best_bet_categories**: ['alt_spread_home_big', 'alt_spread_away_big', 'team_total_home_under', 'team_total_home_over', 'h1_ml_home']
- **worst_bet_categories**: ['ml_home', 'spread_home', 'spread_away', 'total_under']
- **ideal_bet_volume**: 1000-2000 per season (not 4000+)
- **drawdown_kill_threshold**: 0.85

## Current Best Strategy (Backtest)

- Strategy: **Specialist: Spread**
- ROI: 51.3%
- Win rate: 77.7%
- Sharpe: 8.9
- Brier: 0.20939

## NBA — Best Known Config

- Model: **gradient_boosting**
- n_estimators: 125
- max_depth: 10
- min_samples_leaf: 7
- max_features_ratio: 0.4
- n_features: 85
- Best Brier: 0.1909689543969487

## POLITICAL — Best Known Config

- Model: **random_forest**
- n_estimators: 50
- max_depth: 7
- min_samples_leaf: 1
- max_features_ratio: 0.4
- n_features: 80
- Best Brier: 0.20454312075559716
