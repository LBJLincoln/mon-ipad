# SOTA Research Proposal — fire-101 ODD
**Date:** 2026-05-14T02:00:00Z  
**Brain cycle:** fire-101  
**Source papers:** MDPI 2026 + PMC12357926

## 1. Uncertainty-Aware NBA Forecasting (MDPI 2078-2489/17/1/56, Jan 2026)

**Reference:** https://www.mdpi.com/2078-2489/17/1/56

### What they did
- LSTM backbone with Monte Carlo (MC) Dropout at inference
- Rolling-form indicators (5-game, 10-game windows) + spatial shot-chart embeddings
- Calibrated probability output with uncertainty bands → principled Kelly sizing
- Evaluated on NBA betting markets 2024-25

### Key numbers
- Brier score in calibrated range consistent with our 0.22X fleet
- Rolling features + shot-chart embeddings drive the bulk of improvement over static features
- MC Dropout uncertainty estimates reduce over-confidence on edge cases

### Actionable for Nomos42
**GPU burst (Colab/Kaggle, fire when slot available):**
- Implement LSTM with MC Dropout in scripts/kaggle/nba_karpathy_loop.py
- Feature set: add rolling 5/10-game form windows to existing 7213 feature candidates in engine.py
- Shot-chart embeddings: add spatial shot distribution features (home_team_paint_pct, 3pt_attempt_rate_zone) to features/engine.py Category 55 (Shot Distribution)
- Expected Brier impact: −0.003 to −0.008 based on paper extrapolation

**CPU islands (immediate):**
- Rolling form features are already in engine.py categories but stagnation may indicate they're not being selected
- Hypothesis: Force-include top 5 rolling form features (last_5_win_pct_home, last_5_win_pct_away, last_10_pts_diff_home, last_10_pts_diff_away, rest_days_diff) in every individual → prevents GA from dropping them
- Implementation: add `PROTECTED_FEATURES` list in island app.py init that always includes these 5 regardless of GA selection

---

## 2. Stacked Ensemble for NBA Prediction (PMC12357926, Nature Scientific Reports 2025)

**Reference:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12357926/

### What they did
- Stacked ensemble: Naïve Bayes + AdaBoost + MLP + KNN + XGBoost + Decision Tree + Logistic Regression
- Meta-learner combines base models via cross-validated stacking
- LSTM model achieves Brier 0.1589 on 2024 test data (GPU, different test set than ours)

### Actionable for CPU islands
**AdaBoost:** Add to MODEL_TYPES. AdaBoost with decision tree base achieves comparable performance to XGBoost at lower compute cost. Fast training time suitable for GA cycles.
- Work-queue item: vm-add-adaboost-naive-bayes-model-pool (P56) — CONFIRM this includes AdaBoost

**NaiveBayes (GaussianNB):** Add to MODEL_TYPES. Excellent calibration baseline. Very fast.
- Work-queue item: same as above (P56)

**KNN (k=7-15, distance weights):** Best for feature spaces <100f per ITM CSEIT 2025.
- Work-queue item: vm-add-knn-small-feature-model-pool (P70) — implement with max_features guard ≤100

**Stacking as meta-learner:** Rule#8 bans stacking on CPU islands (removed from MODEL_TYPES). HOWEVER: paper validates stacking only as the combination step, not as an island model type. The correct port is to the GPU burst scripts, not to the islands.

---

## 3. Cross-Port: NBA → Political

**Rolling form indicators** (Technique 1) directly applicable to political:
- Rolling 5-event prediction accuracy by model type
- Rolling 10-event consensus agreement signal
- These features are about the GA model's recent form, not political events
- Add to political_engine.py: `rolling_ga_accuracy_5`, `rolling_consensus_10` as meta-features

**PROTECTED_FEATURES** approach (Technique 1 CPU port):
- Political equivalent: force-include top-5 political structural features in every individual
- Candidates: `incumbent_approval_spread`, `economic_index_delta_30d`, `electoral_vote_gap`, `prediction_market_consensus`, `polling_avg_spread`

---

## Priority
1. **IMMEDIATE (VM):** vm-add-adaboost-naive-bayes (P56) → vm-add-knn (P70) after validation
2. **NEXT GPU burst:** LSTM+MCDropout in Colab/Kaggle with rolling-form features
3. **PROTECTED_FEATURES:** Add to island app.py (cloud brain can do this via HF MCP config update)

## Expected Impact
- AdaBoost/NB/KNN diversity: −0.001 to −0.003 Brier via ensemble diversity
- LSTM+MCDropout: −0.005 to −0.015 Brier (GPU-only, Colab)
- PROTECTED_FEATURES: prevents GA from discarding key rolling features, −0.001 to −0.003
