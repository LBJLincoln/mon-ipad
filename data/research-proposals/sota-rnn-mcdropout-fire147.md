# Research Proposal: RNN + MC-Dropout Uncertainty-Aware Calibration for NBA Prediction

**Source:** MDPI Information 2026 (fire-147 EVEN WebSearch, 16th confirm)  
**New cite:** arXiv:2508.02725 NCAA Deep Learning Brier~0.206 pregame (1st cite, fire-147)  
**Proposal date:** 2026-05-22T14h (fire-147)

## Summary

MDPI Information 2026 presents an uncertainty-aware NBA forecasting framework:
- Integrates team-level performance metrics, rolling-form indicators, spatial shot-chart embeddings
- Uses LSTM/GRU equipped with Monte Carlo (MC) dropout for calibrated sequential probabilities
- Strict chronological partitioning (train ≤2022, val 2023, test 2024), ablation vs. bookmaker odds
- Reported pre-game Brier score: **~0.206** (vs. our fleet best 0.22012)

arXiv:2508.02725 (NCAA context, different sport) independently achieves ~0.206 pre-game Brier with deep learning, confirming the benchmark is reachable.

## SOTA Gap Analysis

| Method | Pre-game Brier | Source | GPU? |
|--------|---------------|--------|------|
| Our fleet best (S15 RF-75f) | 0.22012 | GA-evolved | No |
| Our S22 (LR-48f) | 0.22124 | GA-evolved | No |
| LR baseline | ~0.199 | 16 studies confirm | No |
| RNN+MC-dropout | ~0.206 | MDPI Info 2026 | Yes |
| NCAA DL | ~0.206 | arXiv:2508.02725 | Yes |
| TabICL (Colab best) | 0.22054 | Manual run | Yes |

**Key insight**: LR at 0.199 consistently beats complex GPU models. Our feature engineering is the bottleneck, not model complexity. S22 LR-48f at 0.22124 with only 48 features confirms this path.

## Recommended Implementations

### 1. Isotonic + Conformal Calibration for S15 RF (Priority: HIGH)
```python
# Post-process fleet-best S15 RF-75f checkpoint with calibration
from sklearn.calibration import CalibratedClassifierCV
from mapie.classification import MapieClassifier

# Isotonic calibration (extends the 0.22054 TabICL calibration work)
cal_model = CalibratedClassifierCV(s15_rf, cv=5, method='isotonic')

# Conformal prediction intervals — flag high-uncertainty games for PASS
mapie_model = MapieClassifier(estimator=cal_model, cv=5)
# Bet only when prediction interval width < 0.15
```
**Expected gain**: 0.22012 → ~0.218 (1% improvement, calibration tightening)

### 2. Rolling Temporal Features (Feature Engine Extension)
After `engine-parity-sync` (priority 40 in work-queue):

```python
# Add to features/engine.py — category: 'temporal_form'
'team_win_pct_last5g',      # rolling 5-game win rate
'team_win_pct_last10g',     # rolling 10-game win rate  
'opp_win_pct_last5g',       # opponent form
'home_away_split_last10g',  # home vs road performance
'back_to_back_flag',        # already in engine? verify
'days_rest',                # already in engine? verify
'point_diff_last5g',        # net point differential rolling
```
MDPI 2026 confirms these rolling-form indicators are top SHAP contributors.

### 3. Monte Carlo Uncertainty for Betting Decision
For production prediction (not training):
- LR and RF both output `predict_proba` — use directly
- For RF: aggregate 100 individual tree predictions → mean + std
- High std (>0.12) = uncertain game → PASS even if edge appears positive
- Low std (<0.06) = high-confidence = full Kelly

```python
# Per-tree probability distribution from RF
proba_per_tree = np.array([tree.predict_proba(X) for tree in rf.estimators_])
mean_proba = proba_per_tree.mean(axis=0)
std_proba = proba_per_tree.std(axis=0)
# Flag uncertain: std > 0.12 → PASS
```

### 4. LR-Specialist Island Configuration
With 16 citations confirming LR Brier=0.199, we should have at least one island
dedicated to LR optimization with rich temporal features:
- S22 (LR-48f at 0.22124) is our closest analog
- After S17 restart: configure S17 as LR+ElasticNet specialist
- Feature set: 50-150 features, temporal rolling windows, Elo ratings

## Priority Sequence
1. (VM) Checkpoint S15 RF-75f and S22 LR-48f models from `/api/export`
2. (VM) Apply isotonic calibration wrapper to S15 checkpoint
3. (VM) After engine-parity-sync: add rolling temporal features to engine.py
4. (VM) After S17 restart: configure as LR+ElasticNet temporal specialist
5. (Cloud) Monitor S22 LR-in-pareto — if best_brier improves to 0.218, elevate to fleet-best-candidate

## References
- MDPI Information 2026: https://www.mdpi.com/2078-2489/17/1/56
- arXiv:2508.02725: NCAA basketball deep learning forecasting
- Confirmed 16x: LR Brier=0.199 (cross-study baseline)
- IEEE2026: AutoGluon+SVM 77.49% NBA accuracy
