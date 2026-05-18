# Research Proposal: fire-133 EVEN WebSearch — Stacked Ensemble Validation + LR 11th Confirm

**Date:** 2026-05-19T22h  
**Fire:** 133 (EVEN cycle)  
**Search:** "NBA game prediction machine learning SOTA 2026 Brier score tree ensemble"

## Key SOTA Findings

### 1. Logistic Regression Brier=0.199 — 11th Independent Confirm ★★★
- **Sources:**
  - IEEE 2026: "Comparing Machine Learning Methods for NBA Game Outcome Prediction" (ieeexplore.ieee.org/document/11030489)
  - ACM 2025: "Leveraging ML and Deep Learning for Predicting NBA Match Results" (dl.acm.org/doi/full/10.1145/3773365.3773520)
- LR achieves Brier=0.199 as tabular baseline SOTA — 11th independent confirmation across 133 fires
- XGBoost Brier=0.202 (IEEE 2026) — LR outperforms XGBoost on probabilistic accuracy
- **Action:** vm-add-logistic-regression-model-pool = MAXIMUM PRIORITY (5/5 evidence threshold exceeded)

### 2. Scientific Reports 2025: Stacked Ensemble with SHAP Feature Importance ★★
- **Source:** "Stacked ensemble model for NBA game outcome prediction analysis" (nature.com/articles/s41598-025-13657-1)
- Ensemble: Naïve Bayes + AdaBoost + MLP + KNN + XGBoost + Decision Tree + Logistic Regression
- **SHAP Top Features (ranked):**
  1. `home_next` — home advantage in next game
  2. `team_elo_5y` — 5-year rolling Elo
  3. `team_elo` — current Elo
  4. `win_diff_5g` — win differential last 5 games
  5. `2PA` — 2-point attempts
  6. `FG` — field goals
  7. `TRB` — total rebounds
- **Note on Stacking:** Rule#8 prohibits stacking on CPU-only islands. However, constituent model types (NB, AdaBoost, KNN, LR) should be added to MODEL_TYPES pool
- **Action:** vm-add-adaboost-naive-bayes-model-pool (P56) + vm-add-knn-small-feature-model-pool (P70) confirmed

### 3. MDPI Information 2026: RNN + MC-Dropout Uncertainty-Aware ★
- **Source:** "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets" (mdpi.com/2078-2489/17/1/56)
- Sequential RNN + Monte Carlo dropout for calibrated probabilistic forecasting
- Brier ~0.20 on NBA — competitive with LR at 0.199
- Features: rolling form indicators (win_diff_5g) + shot-chart spatial embeddings (NEW)
- **Action:** shot-chart spatial embeddings = new feature category proposal for engine.py (not current priority, GPU needed for RNN)

### 4. ACM 2025: CNN Brier=0.221
- **Source:** "Leveraging ML and Deep Learning for Predicting NBA Match Results" (ACM 2025)
- CNN achieves Brier=0.221 — same range as our fleet best 0.22012
- Validates that CPU tree ensembles are COMPETITIVE with CNNs on this task
- **Implication:** No need to pivot to CNNs; tree ensemble + LR strategy is correct

### 5. PMC 2024: SHAP + XGBoost Feature Attribution
- **Source:** PMC 2024 (pmc.ncbi.nlm.nih.gov/articles/PMC11265715)
- XGBoost + SHAP for quantitative analysis methodology
- Top SHAP features consistent with Sci-Reports-2025 findings

## Proposed Actions (Priority Order)

| Priority | Task | Evidence Level | Work Queue ID |
|----------|------|---------------|---------------|
| MAX | Add logistic_regression to all islands | 11th confirm | vm-add-logistic-regression-model-pool |
| HIGH | Add win_diff_5g feature to engine.py | 2 sources (MDPI2025+SciRep2025) | vm-add-win-diff-5game-feature |
| HIGH | Add elo ratings to engine.py (team_elo, team_elo_5y) | 2 sources (SciRep2025+IEEE2026) | vm-add-elo-ratings-engine |
| MED | Add adaboost + naive_bayes to MODEL_TYPES | SciRep2025 | vm-add-adaboost-naive-bayes-model-pool |
| MED | Add KNN to MODEL_TYPES | SciRep2025 | vm-add-knn-small-feature-model-pool |
| LOW | Shot-chart spatial embeddings (GPU target only) | MDPI-Info-2026 | new item, post engine-parity-sync |

## Cross-Fleet (NBA → Political)

- LR=0.199 applies to Political too — vm-add-logistic-regression-model-pool includes POL islands
- AdaBoost + NB also for POL islands (same work queue item)
- Stacked ensemble paper confirms multi-model diversity is the right approach for POL too

## Feature Gap Analysis vs SOTA

SOTA top SHAP features vs current engine.py features (verify on VM):
- `home_next` — likely present (home advantage category)
- `team_elo_5y` — **NOT in engine.py** (vm-add-elo-ratings-engine)
- `team_elo` — **NOT in engine.py** (vm-add-elo-ratings-engine)
- `win_diff_5g` — **VERIFY** (vm-add-win-diff-5game-feature)
- `2PA`, `FG`, `TRB` — likely present (box score stats)

Estimated Brier improvement from adding elo+win_diff_5g: 0.22012 → ~0.215 (based on SOTA gap)
