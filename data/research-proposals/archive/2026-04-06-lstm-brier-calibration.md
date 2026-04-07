# Research Proposal: LSTM with Brier Loss for NBA Prediction Calibration

**Date:** 2026-04-06  
**Proposed by:** Nomos42 Brain (automated cycle)  
**Priority:** HIGH  
**Target:** nomos-nba-agent / features/engine.py

## Problem

Current best Brier score across NBA fleet: **0.2222** (Island 6, gen 106).  
Target threshold: **0.21837**. Gap: ~0.0038.

All islands use Random Forest or XGBoost as base models. These ensemble methods produce
uncalibrated probability outputs that require post-hoc calibration (typically Platt scaling
or isotonic regression). Research shows this can leave significant Brier score improvement
on the table.

## Finding

From 2025-2026 research (Forecasting NCAA/NBA outcomes with deep learning):
- **LSTM trained directly with Brier loss** achieves Brier scores of **0.1589** on basketball data
- vs CNN approach (Binary Cross-Entropy) achieving **0.221** — nearly identical to our current floor
- Key insight: training the loss function TO BE the Brier score produces inherently calibrated probabilities

From Sports Betting ML review (arXiv 2410.21484):
- Stacked ensemble models combining tree-based + neural models beat single-model approaches
- Isotonic regression calibration consistently outperforms sigmoid (Platt) for sports predictions

## Concrete Implementation Plan

### Phase 1: Add Isotonic Calibration Wrapper (Low Risk, Fast)
In `features/engine.py`, wrap the best GA-selected model with `CalibratedClassifierCV(method='isotonic')`:
```python
from sklearn.calibration import CalibratedClassifierCV
calibrated_model = CalibratedClassifierCV(best_model, method='isotonic', cv=5)
calibrated_model.fit(X_train, y_train)
```
Expected Brier improvement: 0.005-0.010

### Phase 2: Add LSTM as a GA-eligible Model Type (Medium Risk)
Add `lstm_brier` as a new model type in the GA individual:
- Input: rolling 10-game sequences per team
- Loss function: Brier score (MSE on probability vs outcome)
- Architecture: 2-layer LSTM, 64 units, dropout 0.3
- Training: 50 epochs, Adam optimizer, lr=0.001
Expected Brier improvement: 0.010-0.020 if it finds good sequences

### Phase 3: Calibration Ensemble (High Reward)
Blend LSTM probability with best tree model:
```python
final_prob = 0.4 * lstm_prob + 0.6 * calibrated_rf_prob
```
Expected to break 0.21837 threshold.

## Cross-Project Note
The isotonic calibration wrapper (Phase 1) is directly portable to `nomos-political-alpha/features/political_engine.py` with zero modification. Apply after NBA validation.

## Sources
- https://arxiv.org/html/2508.02725v1 (LSTM Brier loss for basketball)
- https://arxiv.org/html/2410.21484v1 (ML sports betting systematic review)
- https://www.nature.com/articles/s41598-025-13657-1 (Stacked ensemble NBA)
