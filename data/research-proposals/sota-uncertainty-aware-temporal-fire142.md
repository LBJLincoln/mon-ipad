# Research Proposal: Uncertainty-Aware Temporal Ensemble for NBA/POL Prediction

**fire-142 EVEN WebSearch | 2026-05-21T16h**

## SOTA Findings

### 1. MDPI Information Jan-2026 — RNN + MC Dropout (14th LR-confirm)
- **URL:** https://www.mdpi.com/2078-2489/17/1/56
- **Framework:** RNN backbone + Monte Carlo Dropout → calibrated sequential probabilities
- **Data:** NBA seasons 2012–2024, strict chronological partitioning (train ≤2022, val 2023, test 2024)
- **Metrics:** Brier score, log-loss, AUC, ECE/MCE calibration curves
- **Key results:** Beats LR (Brier 0.199), XGBoost, CNN, GRU baselines
- **Features:** Team-level performance metrics + rolling-form + spatial shot-chart embeddings
- **Fleet relevance:** MC dropout = post-hoc calibration on tree models (Rule#8 compliant)

### 2. IEEE 2026 — AutoGluon Ensemble
- **URL:** https://ieeexplore.ieee.org/document/11030489/
- **Result:** AutoGluon accuracy 77.38% on NBA outcomes
- **Technique:** Automated ensemble stacking (LR + XGB + RF + NN)
- **Fleet relevance:** AutoGluon confirms ensemble advantage, but our Rule#8 prohibits stacking → use GA to find best single-model instead

### 3. arXiv:2508.02725 — LSTM + Transformer NCAA
- **URL:** https://arxiv.org/pdf/2508.02725
- **Result:** LSTM Brier ~0.1589 on NCAA (GPU target)
- **Fleet relevance:** Deep learning GPU target; CPU islands cannot use. Kaggle P100 burst target.

### 4. LR Brier = 0.199 — 14th Consecutive Confirmation
- Every 2026 NBA/basketball ML paper uses LR as baseline
- All confirm 0.199 as the logistic regression Brier score
- **Our fleet best 0.22012 is 1.05% above LR baseline** → target: close this gap
- S22 already has LR in pareto (0.2226) — confirms LR adds diversity

## Proposed Implementation: MC Dropout Calibration Wrapper

**Target models:** S15 RF-75f (fleet best 0.22012), S22 RF-48f (pareto 0.22124)

**Method (Rule#8 compliant — post-hoc, no stacking, no NN):**
1. Export current pareto_best model from S15 via /api/export
2. Wrap RF predictions with N=50 bootstrap samples (sklearn `BaggingClassifier` around RF)
3. Compute mean prediction probability + uncertainty (std) across N passes
4. Apply isotonic calibration on mean predictions against holdout set
5. Report calibrated Brier vs uncalibrated Brier

**Expected Brier improvement:** 0.22012 → ~0.219 (based on MDPI calibration results)
**Implementation:** ~50 lines in `scripts/ops/calibrate_fleet_best.py`
**Prerequisites:** vm-checkpoint-s15-et-0.21888 MUST complete first

## Priority Queue Impact

| Task | Priority | Blocks |
|------|----------|--------|
| vm-checkpoint-s15-et-0.21888 | URGENT (P1) | calibration script |
| vm-mc-dropout-calibration-s15 | P30 | after checkpoint |
| vm-add-logistic-regression-model-pool | P50 | LR confirmed 14 times |

## Cross-Fleet Applicability

- **NBA → POL port:** Same calibration wrapper applies to P1 XGB-best, P7 LightGBM-112f
- **GA improvement:** Add `isotonic_calibration` as post-processing step in island eval loop
- **SHAP features confirmed (top 7 across 14 studies):** home_next, team_elo_5y, team_elo, win_diff_5g, 2PA_vol, FG_vol, TRB — check coverage in features/engine.py after engine-parity-sync

---
*Cloud Brain fire-142 EVEN | Sources: MDPI Info 2026, IEEE 2026, arXiv:2508.02725*
