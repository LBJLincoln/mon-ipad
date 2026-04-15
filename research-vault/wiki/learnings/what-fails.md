# What Fails — Avoid These

> Auto-generated from experiment data on 2026-04-15 22:24 UTC
> Only includes findings backed by measured failure

## Eliminated Strategies

- totals_expert (-72% ROI, ELIMINATED)
- spread_only (-97% ROI, ELIMINATED)
- full_blast (-100% ROI, ELIMINATED)
- SECTOR_ROTATE (-75% ROI, ELIMINATED political)
- DEFENSE_LONG_individual (-65% ROI, ELIMINATED political)
- BILL_PASSES (-64% ROI, ELIMINATED political)
- value_hunter on Codex: -$153.07 (high-volume value hunting with aggressive sizing = death)

## CPCV Gate: ALL Strategies Rejected

Out of 10 strategies tested, ZERO pass the CPCV gate.
This means no strategy has stable risk-adjusted returns across fold permutations.

**Implication**: Model accuracy (Brier) must improve before strategies can be profitable.
Optimizing strategy parameters on a weak model is polishing a turd.

### Top Rejected Strategies

- **Specialist: Spread**: DSR -2.377, p=0.9913
- **Fixed 2%**: DSR -19.072, p=1.0000
- **Sharpe Maximizer (risk-adjusted)**: DSR -19.125, p=1.0000
- **Quarter Kelly (edge>3%)**: DSR -19.183, p=1.0000
- **Bayesian Adaptive (shrinkage)**: DSR -19.183, p=1.0000

## NBA — Never-Improving Mutations

- **change_max_features_ratio**: tried 6 times, ZERO improvements. Skip this.
- **change_max_depth**: tried 4 times, ZERO improvements. Skip this.
- **remove_features**: tried 5 times, ZERO improvements. Skip this.
- **add_features**: tried 7 times, ZERO improvements. Skip this.
- **change_model**: tried 23 times, ZERO improvements. Skip this.

## POLITICAL — Never-Improving Mutations

- **remove_features**: tried 5 times, ZERO improvements. Skip this.
- **add_features**: tried 7 times, ZERO improvements. Skip this.
- **change_model**: tried 13 times, ZERO improvements. Skip this.
- **change_max_features_ratio**: tried 7 times, ZERO improvements. Skip this.
- **change_max_depth**: tried 6 times, ZERO improvements. Skip this.
- **change_n_estimators**: tried 3 times, ZERO improvements. Skip this.
- **swap_features**: tried 3 times, ZERO improvements. Skip this.
- **change_min_samples_leaf**: tried 6 times, ZERO improvements. Skip this.

## NBA — Underperforming Models

- **xgboost**: best=1.00000, avg=1.00000 (vs champion extra_trees best=0.21616)
- **catboost**: best=1.00000, avg=1.00000 (vs champion extra_trees best=0.21616)
- **gradient_boosting**: best=0.27070, avg=0.27489 (vs champion extra_trees best=0.21616)

## POLITICAL — Underperforming Models

- **lightgbm**: best=0.24506, avg=0.24506 (vs champion random_forest best=0.20454)
- **extra_trees**: best=0.24356, avg=0.24356 (vs champion random_forest best=0.20454)

## Personality Anti-Patterns

- **conservative**: Safe but slow — great Sharpe but limited upside
- **diversified**: Mediocre — diversification without conviction leads to slow bleed
- **aggressive**: Dangerous — high risk tolerance without discipline = ruin
