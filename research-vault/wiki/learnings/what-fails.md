# What Fails — Avoid These

> Auto-generated from experiment data on 2026-04-15 12:25 UTC
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

- **change_n_estimators**: tried 5 times, ZERO improvements. Skip this.
- **swap_features**: tried 6 times, ZERO improvements. Skip this.
- **add_features**: tried 5 times, ZERO improvements. Skip this.
- **change_max_features_ratio**: tried 4 times, ZERO improvements. Skip this.
- **change_model**: tried 22 times, ZERO improvements. Skip this.
- **change_max_depth**: tried 4 times, ZERO improvements. Skip this.

## POLITICAL — Never-Improving Mutations

- **change_max_depth**: tried 10 times, ZERO improvements. Skip this.
- **change_model**: tried 4 times, ZERO improvements. Skip this.
- **swap_features**: tried 6 times, ZERO improvements. Skip this.
- **add_features**: tried 6 times, ZERO improvements. Skip this.
- **change_n_estimators**: tried 12 times, ZERO improvements. Skip this.
- **change_max_features_ratio**: tried 5 times, ZERO improvements. Skip this.
- **change_min_samples_leaf**: tried 4 times, ZERO improvements. Skip this.
- **remove_features**: tried 3 times, ZERO improvements. Skip this.

## NBA — Underperforming Models

- **gradient_boosting**: best=0.25849, avg=0.26710 (vs champion random_forest best=0.21529)
- **xgboost**: best=1.00000, avg=1.00000 (vs champion random_forest best=0.21529)
- **lightgbm**: best=0.22791, avg=0.23281 (vs champion random_forest best=0.21529)
- **catboost**: best=1.00000, avg=1.00000 (vs champion random_forest best=0.21529)

## POLITICAL — Underperforming Models

- **gradient_boosting**: best=0.26569, avg=0.26569 (vs champion random_forest best=0.20454)

## Personality Anti-Patterns

- **conservative**: Safe but slow — great Sharpe but limited upside
- **diversified**: Mediocre — diversification without conviction leads to slow bleed
- **aggressive**: Dangerous — high risk tolerance without discipline = ruin
