# SOTA Research Proposal — fire-110 (EVEN cycle, 2026-05-15T10h)

## Top Find: LSTM + Brier Loss Achieves 0.1589 on NCAA Basketball

**Source:** arXiv:2508.02725 — "Forecasting NCAA Basketball Outcomes with Deep Learning: A Comparative Study of LSTM and Transformer Models" (Md Imtiaz Habib, Aug 1 2025)

### Key Results
- **LSTM + Brier loss: Brier score = 0.1589** (best probabilistic calibration)
- **Transformer + BCE loss: AUC = 0.8473** (best discriminative power)
- NCAA Division 1 Men's + Women's Basketball, 2025 tournament data
- Features: GLM-derived team quality metrics, Elo ratings, seed differences, box-score stats

### Gap Analysis vs Our Fleet
| Model | Brier | Notes |
|-------|-------|-------|
| LSTM+Brier (NCAA) | **0.1589** | Neural, GPU-required, tournament data |
| Our S15 fleet best | 0.22012 | CPU tree, full 9551-game NBA season |
| Gap | **0.061** | 27% relative gap — major opportunity |

**Caution:** NCAA tournament ≠ NBA regular season. Tournament data is smaller, bracket-structured, and may have simpler predictability (seed diff is a strong feature). Direct comparison not valid. However, architecture is inspiring.

### CPU-Applicable Insights
1. **Elo ratings** as features: paper uses head-to-head Elo as one of 4 feature categories. Our engine (7213 raw features) does NOT currently have Elo ratings as a category. **VM task:** add Elo ratings to features/engine.py (rolling win-weighted Elo per team, season-reset).
2. **Brier loss objective**: we already use `xgboost_brier` (XGB with Brier objective). The paper confirms Brier loss > BCE for calibration. Our islands are already on this. ✓
3. **GLM-based team quality**: similar to our scaled-form features. Already have. ✓

### GPU-Required Plan (Colab/Modal next session)
- Implement LSTM (2-layer, 128 hidden) with Brier loss on 9551-game NBA dataset
- Input: sequential game stats in chronological order (game-level time series per team)
- Compare to RF Brier=0.22012 on same holdout
- Use MC-Dropout at inference for calibrated intervals (Montrucchio 2026)
- Target: Brier < 0.21 on NBA (25% harder than NCAA due to data structure)

---

## Supporting Finds (6th-cycle confirmation)

### LR Brier=0.199 — 6th Consecutive Confirmation
Sources: Montrucchio 2026 (MDPI) + ACM CISAI 2025 + MDPI WNBA + MDPI Symmetry 2023 + Sci Reports 2025 + this cycle search.
S13 already has LR in model pool (gen=684 using logistic_regression 48f). All other islands should add LR + ElasticNet.

### Stacked Ensemble (Sci Reports 2025)
Naïve Bayes + AdaBoost + MLP + KNN + XGB + DT + LR stacked ensemble outperforms individual models.
Our Rule#8 bans stacking but individual models are all valid:
- **AdaBoost**: not yet in pool → vm-add-adaboost-naive-bayes-model-pool
- **NaiveBayes**: not yet in pool → same
- **KNN**: queued for vm-add-knn-small-feature-model-pool

---

## Cross-Project Insight: P4 Model Type Change

At fire-110, P4 (LBJLincoln/political-alpha-4) shows model_type=lightgbm (was xgboost_brier at fire-109). Hard resets at cycles 26734+26754 may have cleared xgboost-dominant population. LightGBM now champion at P4 — 4th POL island with LightGBM dominance (P2, P4, P5, P7 all showing LightGBM).

**Implication:** LightGBM cross-port to NBA S22 (currently 0.22551, weakest NBA survivor) is highest-priority model pool addition after LR/ElasticNet. See vm-add-lightgbm-s22-s13.

---

## Immediate VM Actions from This Research

| Priority | Task | Evidence |
|----------|------|----------|
| P50 | Add LR+ElasticNet to S14/S15/S18/S22 + P1/P2/P4/P5/P7 | 6x SOTA, S13 already working |
| P48 | Add LightGBM to S22 (primary) and verify S13 | 4/5 POL converged on LightGBM |
| P80 | Add Elo ratings to features/engine.py | arXiv:2508.02725 + multiple papers |
| Future | LSTM+Brier on Colab/Modal (GPU) | arXiv:2508.02725 Brier=0.1589 |
