# Department: POLITICAL (D7)

## Mission
Build and evolve a political signal pipeline that generates alpha for ETF/stock trading by predicting political outcomes and their market impact.

## Primary Metric
- **Name:** political_brier
- **Current:** 0.24186 (P1 space)
- **Target:** < 0.22000
- **Direction:** lower_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| etf_roi_pct | 0% (pre-launch) | > 3% |
| signal_categories | 22 | 25+ |
| features_count | 743 | 900+ |
| prediction_accuracy_pct | ~60% | > 65% |
| signal_lead_time_hours | 24 | 48+ |
| market_correlation | monitoring | > 0.30 |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| signal_category_count | 22 | [15, 30] | 1 |
| feature_weight_decay | 0.95 | [0.80, 1.00] | 0.01 |
| model_type | gradient_boost | [gradient_boost, catboost, lightgbm, extra_trees] | categorical |
| timing_window_hours | 24 | [6, 72] | 6 |
| news_recency_weight | 0.8 | [0.3, 1.0] | 0.05 |
| insider_signal_threshold | 0.6 | [0.3, 0.9] | 0.05 |
| trump_signal_weight | 1.0 | [0.5, 2.0] | 0.1 |
| foreign_sovereign_weight | 0.8 | [0.3, 1.5] | 0.1 |
| max_features | 200 | [50, 200] | 10 |
| ensemble_method | averaging | [averaging, stacking, voting] | categorical |
| etf_sector_focus | broad | [broad, tech, energy, defense, finance] | categorical |

## Experiment Protocol
1. Load current best political model config from P1-P4 spaces
2. Mutate one parameter from the search space
3. Run experiment (5 min budget): retrain on recent political events, evaluate on holdout
4. Measure political_brier on holdout set, check signal quality
5. If political_brier improved -> keep, commit config to space
6. If not -> revert to previous config
7. Log result to data/departments/political/karpathy-output.json

## Mutation Strategy
- **Type:** single-parameter perturbation
- **Selection:** prioritize signal categories with highest Brier contribution
- **Category expansion:** test one new category per iteration from candidate pool
- **Timing:** political events are sparse; use 90-day evaluation windows minimum
- **Cross-domain:** test if NBA fatigue/travel features have political analogs (crowd/rally attendance)

## Tools & Paths
- **Loop script:** scripts/departments/political/political-loop.sh
- **Output:** data/departments/political/karpathy-output.json
- **Political engine:** nomos-political-alpha repo (v2.0 engine, 13 categories base)
- **Feature engine:** political feature engine (22 categories, 743 features)
- **Kaggle Karpathy:** scripts/kaggle/political_karpathy_loop.py
- **Signal categories:** Cat1-Cat22 (includes Cat17-22: insider, Trump, foreign sovereign)
- **Dashboard:** nomos-dashboard /political route

## Success Criteria
- political_brier < 0.22000 sustained over 50+ predictions
- At least 3 ETF trades with positive ROI in first month of live trading
- Signal categories expanded to 25+ with measured predictive power
- Zero false political signals (predictions on non-events)
- Cross-pollination: at least 1 technique from NBA research applied to political domain

## Dependencies
- **Upstream:** D1 (Research) for methodology, D2 (Engineering) for shared feature engine patterns
- **Downstream:** D9 (Trading Floor) political traders use these signals
- **External:** News APIs, political event calendars, market data feeds
- **Compute:** HF Spaces (P1-P4), Kaggle GPU for Karpathy loop
