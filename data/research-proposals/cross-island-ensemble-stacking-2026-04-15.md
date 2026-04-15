# Cross-Island Ensemble Stacking — NBA Fleet Brier Reduction Proposal
**Date:** 2026-04-15 | **Source:** Brain cycle 4h-auto | **Priority:** HIGH

## Motivation

Fleet status (2026-04-15 04:00 UTC):
- S10 (nba-quant):   Gen 659,  Brier 0.2271
- S11 (nba-quant-2): Gen 859,  Brier 0.22486
- S12 (nba-evo-3):   Gen 1475, Brier 0.22334
- S13 (nba-evo-4):   Gen 243,  Brier 0.22326
- S14 (nba-evo-5):   Gen 609,  Brier 0.22251  ← fleet best
- S15 (nba-evo-6):   Gen 999,  Brier 0.22328  (14-cycle stagnation)
- S16 (nba-evo-s16): Gen 686,  Brier 0.22573
- S17 (nba-evo-s17): Gen 715,  Brier 0.22085  ← previous fleet best; DIVERSIFY triggered

**Problem:** All 8 islands are converging to Brier ~0.221–0.227, each with a different
model specialist (XGBoost, LightGBM, CatBoost, ExtraTrees, RandomForest). The target
is 0.21837. Individual islands seem stuck above this threshold.

**Key insight from research:**
Nature Scientific Reports (2025) "Stacked ensemble model for NBA game outcome prediction"
found that combining heterogeneous base learners with a meta-learner outperforms any
single model. Brier score improvement of ~3-5% over best individual model.

## Approach: Cross-Island Checkpoint Ensemble

### Step 1: Export checkpoints from all 8 islands
Each island's `/api/status` already tracks `best_brier` and `best_features`. Expose
the trained model weights via a new `/api/checkpoint` endpoint (or use the Supabase
checkpoint table already in the system).

### Step 2: Stacked ensemble with logistic regression meta-learner
**WHY this works on CPU:** The meta-learner only needs to fit 8 probability columns
(one per island model), NOT retrain any base model. Logistic regression on 8 features
takes <1ms on any CPU.

```python
# Pseudo-code for ensemble (NO neural networks — pure sklearn, CPU-friendly)
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV

# p1..p8: predicted probabilities from each island's best checkpoint
meta_X = np.column_stack([p1, p2, p3, p4, p5, p6, p7, p8])  # shape (n_games, 8)
meta_y = actual_outcomes

# With Venn-Abers calibration (already in system)
meta = LogisticRegression(C=0.1, solver='lbfgs')
calibrated_meta = CalibratedClassifierCV(meta, method='isotonic', cv=5)
calibrated_meta.fit(meta_X, meta_y)

# Expected Brier improvement: 0.22085 → ~0.215 (based on Nature 2025 results)
```

### Step 3: Uncertainty-weighted voting (bonus)
From MDPI 2026 "Uncertainty-Aware ML for NBA Forecasting":
- Compute prediction variance across islands as uncertainty signal
- Down-weight bets when variance > threshold
- Boosts Sharpe ratio by 15-20% with no Brier degradation

### Step 4: Island diversity score
If cross-correlation of island predictions > 0.95, trigger `diversify` on the most
correlated pair. This maintains ensemble benefit.

## Implementation Plan

### Phase 1 (this cycle): Export predictions
Add `/api/predict_batch` endpoint to each HF space that returns raw probabilities
for a shared held-out test set (2025-26 season games).

### Phase 2 (next cycle): Meta-learner training
On VM: load 8 probability arrays → train LR meta → evaluate on walk-forward splits.

### Phase 3 (following cycle): Deploy as `ensemble_checkpoint` in Supabase
Store ensemble weights as a new experiment type. Route `predict_today.py` to use
the ensemble probabilities.

## Expected Outcome
- Brier improvement: 0.22085 → ~0.215 (target: 0.21837)
- Sharpe improvement: +15-20% via uncertainty gating
- Implementation risk: LOW (logistic regression, no GPU, no neural nets)

## References
1. Nature Scientific Reports (2025): "Stacked ensemble model for NBA game outcome prediction"
   https://www.nature.com/articles/s41598-025-13657-1
2. MDPI Information (2026): "Uncertainty-Aware Machine Learning for NBA Forecasting"
   https://www.mdpi.com/2078-2489/17/1/56
3. MDPI CSIT (2025): "Machine Learning for Basketball Game Outcomes"
   https://www.mdpi.com/2079-3197/13/10/230
