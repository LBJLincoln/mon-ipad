# Research Proposal: Uncertainty-Aware ML + ECE Calibration for NBA Prediction

**Date:** 2026-05-05
**Source:** Montrucchio et al. 2026 — "Uncertainty-Aware Machine Learning for NBA Forecasting"
**Priority:** HIGH — ECE/MCE calibration explicitly targets NBA prediction domain

## SOTA Finding
Recent 2026 paper explicitly benchmarks NBA prediction via ECE (Expected Calibration Error), MCE (Maximum Calibration Error), log-loss, AUC, and Brier score. Beach volleyball analog achieves **Brier 0.2082** — sub-0.21 is achievable with proper calibration. Current fleet best 0.22019 leaves meaningful room.

## Key Techniques to Evaluate

1. **ECE-aware training objective** — Add ECE penalty term to XGBoost/LightGBM loss during GA fitness evaluation
2. **Temperature scaling** — Post-hoc calibration on top of tree ensemble output (cheap, reversible)
3. **Platt scaling per model type** — Separate sigmoid calibrators for RF / XGBoost / LightGBM / CatBoost
4. **Reliability diagrams** — Visual calibration per probability decile (already in `tf_rigorous_validation.py`; extend to island GA)

## Why Calibration Matters for Fleet
- Current isotonic calibration: 0.22169 CV → 0.22054 calibrated (0.11% gain from post-processing alone)
- ECE-aware loss during training (not just post-processing) expected to yield larger gains
- TF agents receive predicted probabilities from oracle — miscalibrated probs → bad Kelly sizing

## Proposed Integration (3 Phases)

### Phase 1: Measure (0 code changes)
- Add ECE measurement to island `/api/status` output alongside Brier
- Baseline: compute ECE for S14 (logistic regression, expected well-calibrated) vs S15 (XGBoost-brier)
- Tools: `reliability_diagram` from `sklearn.calibration`

### Phase 2: Post-hoc calibration
- After GA selects best chromosome, wrap predict_proba with isotonic regression
- Already proven: 0.22169 → 0.22054 on TabICL model
- Apply same wrapper to S14/S15 island output before saving model pickle

### Phase 3: ECE in Pareto front
- Add ECE as third objective: minimise (Brier, ECE, -ROI) simultaneously
- Islands already run multi-objective Pareto; adding ECE adds calibration pressure during evolution
- Expected: lower Brier *and* better-calibrated probabilities for oracle use

## Island Targets (Priority Order)

| Island | Model | Current Brier | Why Target |
|--------|-------|---------------|------------|
| S15 | xgboost_brier | 0.22034 ★ | Approaching fleet best; calibration could push sub-0.22 |
| S14 | logistic_regr | 0.22019 (all-time best) | Logistic inherently calibrated — use as ECE baseline |
| S22 | catboost | 0.22431 | stagnation=9, calibration could break plateau |
| P4 | lightgbm | 0.24904 (POL best) | Political oracle probabilities feed TF agent Kelly sizing |

## Expected Improvement
- Conservative (post-hoc only): 0.1-0.3% Brier reduction (proven by isotonic)
- Optimistic (ECE-aware training): 0.5-1.0% reduction (based on beach volleyball analog)
- Fleet best target: 0.22019 → sub-0.220 within 2-3 cycles if ECE training adopted

## Implementation Notes
- `backfill_boxscores` API available on islands — ensure data quality before calibration test
- Do NOT change `MAX_FEATURES=200` hard cap while testing calibration
- Calibration layer should be a post-GA wrapper, not a change to the GA fitness function (Phase 1/2)
- Phase 3 (Pareto ECE) requires island code change → submit via `engine_parity_sync` flow
- Supabase experiment tagging: `feature_engine_version` + new field `calibration_method`
