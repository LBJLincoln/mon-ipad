# What Works — Empirically Validated

> Auto-generated from experiment data on 2026-04-15 20:23 UTC
> Only includes findings backed by measured improvement

## NBA — Mutation Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| change_min_samples_leaf | 7 | 0 | 0% | +0.00689 |
| change_max_features_ratio | 6 | 0 | 0% | +0.00600 |
| change_n_estimators | 4 | 0 | 0% | +0.00586 |
| swap_features | 2 | 0 | 0% | +0.00622 |
| change_max_depth | 3 | 0 | 0% | +0.00590 |
| change_model | 24 | 0 | 0% | +0.34501 |
| remove_features | 2 | 0 | 0% | +0.00717 |
| add_features | 2 | 0 | 0% | +0.00501 |

## POLITICAL — Mutation Effectiveness

| Mutation Type | Tried | Improved | Hit Rate | Avg Brier Delta |
|---------------|-------|----------|----------|-----------------|
| swap_features | 11 | 0 | 0% | +0.03394 |
| add_features | 7 | 0 | 0% | +0.01628 |
| change_model | 6 | 0 | 0% | +0.05377 |
| remove_features | 5 | 0 | 0% | +0.02729 |
| change_n_estimators | 10 | 0 | 0% | +0.00657 |
| change_min_samples_leaf | 2 | 0 | 0% | +0.00925 |
| change_max_depth | 6 | 0 | 0% | +0.01752 |
| change_max_features_ratio | 3 | 0 | 0% | +0.02100 |

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

- Model: **random_forest**
- n_estimators: 275
- max_depth: 13
- min_samples_leaf: 5
- max_features_ratio: 0.32
- n_features: 200
- Best Brier: 0.21218334576044304

## POLITICAL — Best Known Config

- Model: **random_forest**
- n_estimators: 50
- max_depth: 7
- min_samples_leaf: 1
- max_features_ratio: 0.4
- n_features: 80
- Best Brier: 0.20454312075559716
