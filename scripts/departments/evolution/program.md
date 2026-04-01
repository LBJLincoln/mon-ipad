# Department: EVOLUTION (D3)

## Mission
Run continuous genetic evolution across 6 HF Space islands to discover optimal feature combinations, model hyperparameters, and ensemble configurations that minimize Brier score.

## Primary Metric
- **Name:** best_brier
- **Current:** 0.22066 (S13 CatBoost specialist)
- **Target:** < 0.21000 (fleet best)
- **Direction:** lower_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| generations_per_hour | ~4 | 6+ |
| fleet_avg_brier | 0.22223 | < 0.21500 |
| diversity_index | 0.65 | > 0.70 |
| stagnation_count | varies | 0 |
| total_generations | 952+ | continuous |
| cross_pollination_rate | manual | automated |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| mutation_rate | 0.08-0.18 | [0.03, 0.15] | 0.01 |
| crossover_rate | 0.80 | [0.50, 0.95] | 0.05 |
| population_size | 20-50 | [10, 50] | 5 |
| tournament_size | 3 | [2, 7] | 1 |
| elitism_count | 2 | [1, 5] | 1 |
| feature_count | 55-80 | [30, 200] | 5 |
| model_type | per-island | [random_forest, extra_trees, catboost, lightgbm, xgboost] | categorical |
| n_estimators | 300 | [100, 1000] | 50 |
| max_depth | 8 | [4, 16] | 1 |
| learning_rate | 0.1 | [0.01, 0.3] | 0.01 |
| subsample | 0.8 | [0.5, 1.0] | 0.05 |

## Island Configuration
| Island | Role | mutation_rate | feature_count | model_type |
|--------|------|---------------|---------------|------------|
| S10 | Exploitation | 0.09 | 63 | best_available |
| S11 | Exploration | 0.15 | 80 | best_available |
| S12 | Specialist | 0.08 | 60 | extra_trees |
| S13 | Specialist | 0.10 | 66 | catboost |
| S14 | Specialist | 0.08 | 55 | lightgbm |
| S15 | Wide Search | 0.18 | 80 | best_available |

## Experiment Protocol
1. Load current best config from fleet (agent-health.json, swarm-metrics.json)
2. Mutate one island's GA parameter (mutation rate, crossover, population, etc.)
3. Run experiment (5 min budget): deploy config change via POST /api/config, monitor 1 generation
4. Measure best_brier, diversity_index, stagnation_count
5. If best_brier improved or diversity increased without regression -> keep
6. If stagnation detected (>5 cycles) -> trigger diversify or boost_mutation
7. Log result to data/departments/evolution/karpathy-output.json

## Mutation Strategy
- **Type:** per-island parameter perturbation
- **Selection:** prioritize stagnant islands (highest stagnation_cycles first)
- **Anti-stagnation:** if stagnation_cycles >= 15 -> diversify command; >= 8 -> boost_mutation
- **Cross-pollination:** seed lagging islands with top features from best island
- **Diversity guard:** if diversity_index < 0.40, force specialist models back to designated types
- **Mutation cap:** adaptive mutation capped at 0.15 (enforced on all islands)

## Tools & Paths
- **Loop script:** scripts/departments/evolution/evolution-loop.sh
- **Output:** data/departments/evolution/karpathy-output.json
- **Fleet health:** data/agent-health.json, data/swarm-metrics.json
- **Cross-pollination:** data/cross-pollination/report-*.json
- **Karpathy best:** data/karpathy/nba-best-config.json
- **HF Spaces API:** POST /api/config for each island
- **Keepalive:** scripts/keepalive-spaces.sh (*/30 cron)
- **Kaggle Karpathy:** scripts/kaggle/nba_karpathy_loop.py (GPU sessions, seeds from 6 islands)

## Success Criteria
- Fleet best Brier < 0.21000 sustained across 3+ consecutive checkpoints
- Zero islands stagnant for > 15 cycles (auto-diversify must trigger)
- Diversity index > 0.70 (model type variety + Brier spread)
- Generations per hour >= 6 across fleet
- Specialist islands maintain designated model types (no drift)

## Dependencies
- **Upstream:** D2 (Engineering) provides feature engine updates, D1 (Research) provides new features
- **Downstream:** D4 (Betting) uses best predictions, D5 (Evaluation) audits calibration
- **External:** HF Spaces uptime (6 islands), Kaggle/Colab GPU for TabICL
- **Compute:** CPU on HF Spaces (tree-based only), GPU on Kaggle/Colab
