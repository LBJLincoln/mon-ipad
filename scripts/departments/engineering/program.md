# Department: ENGINEERING (D2)

## Mission
Implement research proposals into production code, measure Brier improvement per iteration, and maintain feature engine parity across all deployment targets.

## Primary Metric
- **Name:** brier_delta
- **Current:** 0.21570 (ATR, Colab TabICL 110f iter 15)
- **Target:** < 0.20000
- **Direction:** lower_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| test_pass_rate | 95% | 100% |
| feature_engine_version | v3.1-46cat | v3.2+ |
| features_raw_count | 6253 | 7000+ |
| deploy_success_rate | 90% | 99% |
| parity_drift_count | 0 | 0 |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| max_features | 200 | [50, 200] | 10 |
| feature_selection_method | mutual_info | [mutual_info, boruta, shap, permutation] | categorical |
| preprocessing_scaler | standard | [standard, robust, quantile, none] | categorical |
| missing_value_strategy | median | [median, knn, iterative, indicator] | categorical |
| feature_interaction_depth | 2 | [1, 3] | 1 |
| categorical_encoding | target | [target, ordinal, woe, catboost_native] | categorical |
| outlier_clip_pct | 0.01 | [0.0, 0.05] | 0.005 |
| rolling_window_sizes | [5,10,20] | subsets of [3,5,7,10,15,20,30] | add/remove one |
| temporal_split_gap_days | 7 | [1, 14] | 1 |
| ensemble_n_models | 3 | [1, 7] | 1 |

## Experiment Protocol
1. Load current best config from latest HF Space checkpoint (S10 exploitation)
2. Mutate one parameter from the search space
3. Run experiment (5 min budget): train on CPU with tree model, evaluate on holdout
4. Measure brier_delta = new_brier - current_best_brier
5. If brier_delta < 0 (improvement) -> keep, commit to feature engine, deploy to HF
6. If not -> revert, log negative result
7. Log result to data/departments/engineering/karpathy-output.json

## Mutation Strategy
- **Type:** single-parameter mutation (1 fix per iteration rule)
- **Selection:** prioritize parameters with highest expected impact (from D1 proposals)
- **Categorical:** uniform random from allowed values
- **Numerical:** gaussian perturbation within range, sigma = step_size
- **Constraint:** MAX_FEATURES=200 hard cap enforced

## Tools & Paths
- **Loop script:** scripts/departments/engineering/engineering-loop.sh
- **Output:** data/departments/engineering/karpathy-output.json
- **Feature engine:** features/engine.py (canonical) + hf-space/features/engine.py (deployed)
- **HF Spaces:** S10 (exploitation), S11 (exploration), S12-S15 (specialists)
- **Colab:** colab/nba_evolution_gpu.ipynb (GPU training)
- **Test suite:** tests/ directory
- **Deploy:** subtree push to HF Spaces (hf-space/ directory)

## Success Criteria
- Brier score < 0.20000 on walk-forward validation (19+ weeks, 900+ games)
- Feature engine parity: features/engine.py == hf-space/features/engine.py at all times
- Zero regressions: every deploy must pass holdout validation before push
- Improvement rate: at least 1 measurable Brier improvement per week

## Dependencies
- **Upstream:** D1 (Research) provides proposals to implement
- **Downstream:** D3 (Evolution) runs evolved configs, D4 (Betting) uses predictions
- **External:** HF Spaces (6 islands), Colab/Kaggle GPU
- **Compute:** ZERO ML on VM (1 vCPU / 969 MB). All training on HF Spaces or GPU
