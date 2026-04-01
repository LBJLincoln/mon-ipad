# Department: EVALUATION (D5)

## Mission
Audit prediction quality, detect calibration drift, eliminate false positives, and ensure model outputs are trustworthy before they reach the betting pipeline.

## Primary Metric
- **Name:** calibration_ece (Expected Calibration Error)
- **Current:** monitoring (estimated ~0.06)
- **Target:** < 0.05
- **Direction:** lower_is_better

## Secondary Metrics
| Metric | Current | Target |
|--------|---------|--------|
| false_positive_rate | monitoring | < 5% |
| brier_reliability | monitoring | < 0.02 |
| brier_resolution | monitoring | > 0.08 |
| overconfidence_rate | monitoring | < 10% |
| prediction_coverage | 95%+ | 100% |
| phantom_prediction_count | 0 (fixed) | 0 |

## Search Space
| Parameter | Current | Range | Step |
|-----------|---------|-------|------|
| calibration_method | isotonic | [isotonic, platt, beta, venn_abers, none] | categorical |
| calibration_bins | 10 | [5, 30] | 1 |
| confidence_threshold | 0.55 | [0.50, 0.70] | 0.01 |
| ensemble_disagreement_max | 0.15 | [0.05, 0.30] | 0.01 |
| recalibration_window_days | 30 | [7, 90] | 7 |
| outlier_detection_method | iqr | [iqr, zscore, isolation_forest, none] | categorical |
| min_sample_size_for_eval | 50 | [20, 200] | 10 |
| reliability_diagram_bins | 10 | [5, 20] | 1 |
| overconfidence_penalty | 1.0 | [0.5, 2.0] | 0.1 |
| abstain_threshold | 0.48 | [0.45, 0.52] | 0.005 |

## Experiment Protocol
1. Load current best calibration config and recent prediction history
2. Mutate one parameter from the search space
3. Run experiment (5 min budget): recalibrate predictions with mutated config, compute ECE on holdout
4. Measure calibration_ece, false_positive_rate, reliability decomposition
5. If ECE improved without increasing false_positive_rate -> keep, commit
6. If not -> revert to previous calibration config
7. Log result to data/departments/evaluation/karpathy-output.json

## Mutation Strategy
- **Type:** single-parameter perturbation with safety constraints
- **Selection:** prioritize calibration_method changes first, then threshold tuning
- **Safety:** never lower confidence_threshold below 0.50 (coin flip floor)
- **Validation:** all changes validated on at least 50 games before deployment
- **Decomposition:** track Brier = reliability + resolution - uncertainty separately

## Tools & Paths
- **Loop script:** scripts/departments/evaluation/evaluation-loop.sh
- **Output:** data/departments/evaluation/karpathy-output.json
- **Prediction history:** data/nba-agent/predictions-*.json
- **Calibration tools:** sklearn.calibration (IsotonicRegression, CalibratedClassifierCV)
- **Evaluation scripts:** scripts/evaluate-predictions.py
- **Phantom fix:** scripts/fix-phantom-predictions.py (already deployed)

## Success Criteria
- ECE < 0.05 sustained over 100+ game evaluation window
- False positive rate < 5% (predictions with > 60% confidence that lose)
- Zero phantom predictions (predictions for games that don't exist)
- Reliability component of Brier < 0.02
- All model outputs pass sanity checks before reaching betting pipeline
- Weekly calibration audit produces actionable report

## Dependencies
- **Upstream:** D2 (Engineering) provides model predictions, D3 (Evolution) provides ensemble outputs
- **Downstream:** D4 (Betting) trusts calibrated probabilities for Kelly sizing
- **External:** NBA game results for ground truth evaluation
- **Compute:** CPU only (statistical evaluation, no ML training)
