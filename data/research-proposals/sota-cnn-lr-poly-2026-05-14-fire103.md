# SOTA Research — fire-103 — 2026-05-14T10h

## NBA Sources

### 1. [Machine Learning for Basketball Game Outcomes: NBA and WNBA Leagues](https://www.mdpi.com/2079-3197/13/10/230) — MDPI 2026
- **CNN model: Brier=0.221** — best among models tested (beats tree ensembles)
- Tabular baselines in same paper: **LogisticRegression=0.199**, XGBoost=0.202
- Note: LR 0.199 < CNN 0.221 as Brier (LR better?). Likely different eval split.
- Confirms LR is competitive at tabular NBA prediction — directly validates `vm-add-logistic-regression-model-pool` (priority 50).
- CNN architecture: feature vectors → 3-layer CNN. GPU burst target (Colab/Kaggle).

### 2. [Comparative Evaluation of ML Models for NBA Game Outcome Prediction](https://www.scirp.org/journal/paperinformation?paperid=147163) — SCIRP 2025
- Broad benchmark: LR, XGBoost, RF, SVM, DT on historical NBA data
- Confirms ensemble superiority; LR consistently competitive baseline
- Aligns with work-queue P50: logistic_regression addition to all island MODEL_TYPES

## Political Sources

### 3. [Prediction Market AI Reshapes 2026 Election Forecasting](https://www.gamblinginsider.com/in-depth/110180/prediction-market-statistics) — 2026
- **Hybrid ensemble: ML model + market forecast → +13.2% AUC** when they disagree >5%
- Polymarket hitting Brier=0.09 (liquid markets); average political prediction Brier near 0.09
- Our POL fleet at 0.24993 has large gap — hybrid approach could bridge significantly
- Actionable: fetch Polymarket odds for our 1180 political events, soft-ensemble with island predictions

## CPU-Actionable (this cycle)

| Priority | Action | Status |
|----------|--------|--------|
| A | Add `logistic_regression` to P2/P4/P5/P7 MODEL_TYPES | VM: work-queue P50 |
| B | After P50: add `adaboost` + `naive_bayes` | VM: work-queue P56 |
| C | After P56: add `knn` (validated <100f) | VM: work-queue P70 |
| D | Polymarket API research for POL hybrid | Cloud research next cycle |
| E | CNN tabular eval in Kaggle/Colab GPU burst | GPU burst queue |

## P7 Observation (fire-103)
P7 in-pop Brier=0.2490 persistent across gens 66717–66894 (134f lightgbm).  
best_brier confirmed=0.25412 (walk-forward). Classic field-lag pattern.  
If field updates → P7 joins P2/P4/P5 at convergent 0.249 signal.  
All 4 non-fleet-best POL islands converging to 0.249 = strong evidence 0.249 is current feature-set floor.
