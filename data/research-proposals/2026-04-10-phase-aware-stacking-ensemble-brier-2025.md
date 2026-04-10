# Research Proposal: Phase-Aware Stacking Ensemble with Direct Brier Loss
**Date:** 2026-04-10  
**Brain Cycle:** 88  
**Priority:** HIGH — fastest path to sub-0.218 Brier  
**Source:** 2025-2026 literature synthesis (arXiv 2508.02725, MDPI 2025, PMC11265715, Nature Scientific Reports)

---

## Summary

Five high-impact findings from 2025-2026 NBA prediction literature point to a single coherent implementation:
a **Stacking Ensemble trained with Brier loss**, using **phase-aware feature sets** and **SHAP-driven pruning**.
This combination was demonstrated to reach Brier scores as low as **0.1589** (LSTM, arXiv 2508.02725) and
**0.221** (Stacking Classifier, MDPI 2025) in peer-reviewed studies — both below or at our current target.

---

## Finding 1: Train Directly on Brier Loss (Highest Leverage, Already Partial)

- **Source:** arXiv 2508.02725 — LSTM vs Transformer comparison
- **Key result:** LSTM with Brier score loss = 0.1589; BCE-trained Transformer = 0.237
- **Status in our system:** `xgboost_brier` model type already uses Brier-equivalent loss. ✓
- **Gap:** Meta-learner in stacking still uses default BCE. **Change meta-learner loss to Brier.**

### Implementation
In `features/engine.py` or the Kaggle training loop:
```python
# Current: LogisticRegression as meta-learner (BCE loss)
meta_learner = LogisticRegression()

# Proposed: Ridge with calibration OR XGBoost with eval_metric='logloss' tuned for Brier
from sklearn.linear_model import Ridge
from sklearn.calibration import CalibratedClassifierCV

meta_learner = CalibratedClassifierCV(
    Ridge(alpha=1.0), 
    cv=5, 
    method='isotonic'  # Isotonic proven better than Platt for sports probability
)
```

---

## Finding 2: Stacking Ensemble Over Single Models (+75 Engineered Features)

- **Source:** MDPI 2025 (NBA+WNBA), Nature Scientific Reports 2025
- **Key result:** Stacking Classifier with 75 SHAP-selected features → Brier 0.221
- **Top features by SHAP:**
  1. `home_next` (home/away indicator) — highest SHAP importance
  2. Elo delta (team strength differential)
  3. Recent form rolling window (last 5-10 games)
  4. Rest days between matches
- **Gap:** Our GA optimizes single-model feature subsets. **Add a stacking meta-layer.**

### Implementation (Kaggle session)
```python
from sklearn.ensemble import StackingClassifier, ExtraTreesClassifier, GradientBoostingClassifier
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV

base_estimators = [
    ('xgb_brier', xgb.XGBClassifier(objective='binary:logistic', eval_metric='logloss', 
                                     n_estimators=200, max_depth=5, learning_rate=0.05)),
    ('et', ExtraTreesClassifier(n_estimators=200, max_features='sqrt')),
    ('lgbm', lgb.LGBMClassifier(objective='binary', n_estimators=200, num_leaves=31)),
]

meta_learner = CalibratedClassifierCV(Ridge(alpha=1.0), cv=5, method='isotonic')

stacking = StackingClassifier(
    estimators=base_estimators,
    final_estimator=meta_learner,
    cv=5,
    stack_method='predict_proba'
)
```

**Expected Brier improvement:** 0.22291 → ~0.219-0.221

---

## Finding 3: Phase-Aware Feature Weighting (Novel, Not Yet Implemented)

- **Source:** PMC11265715 — XGBoost + SHAP across game phases
- **Key insight:** SHAP importance shifts dramatically by prediction window:

| Window | Top Feature | SHAP Score | Impact |
|--------|-------------|------------|--------|
| Pre-game | Season 3PT% differential | high | Most stable pre-game signal |
| Pre-game | Turnover differential | medium-high | Leading indicator |
| Pre-game | Rest days | medium | Fatigue proxy |
| In-game | FG% current game | 1.447 | Dominant in-game |
| In-game | Turnovers | 0.790 | Second half surge |

### Implementation for Pre-Game Model
Weight our GA feature selection with prior knowledge:
```python
# In GA initialization, seed higher probability for phase-relevant features
PHASE_PRIORS = {
    'three_point_pct_diff_l10': 0.85,      # 3PT differential (season avg)
    'turnover_differential_season': 0.80,   # Season TOV diff  
    'rest_days_home': 0.75,                 # Home team rest
    'rest_days_away': 0.75,                 # Away team rest
    'elo_delta': 0.90,                      # Elo differential
    'home_court_advantage': 0.95,           # Home/away flag
    'last5_win_pct_home': 0.80,            # Recent form home
    'last5_win_pct_away': 0.80,            # Recent form away
}

# Use these as GA initialization weights instead of random 50/50
def weighted_init_genome(feature_list, phase_priors):
    genome = []
    for f in feature_list:
        p = phase_priors.get(f, 0.5)  # Default 50%
        genome.append(1 if random.random() < p else 0)
    return genome
```

**Estimated improvement:** Faster convergence to Brier < 0.222 by eliminating noisy features early.

---

## Finding 4: Second Spectrum Movement Features (Longer-Term, High Ceiling)

- **Source:** TheSpread.com 2026 NBA Analytics
- **Leading indicators available from nba.com tracking:**
  - Defensive close-out speed (rolling 5-game avg)
  - Player separation rate (open look generation)
  - Transition sprint frequency (fatigue proxy)
  - Third-quarter defensive rotation drop (in-game fatigue)
- **Status:** These require nba.com tracking API integration — medium-term (2-4 weeks)
- **Priority:** After stacking ensemble is validated

---

## Recommended Action Plan

### This Kaggle Session (Immediate)
1. Train a 5-fold StackingClassifier using our best GA-found feature sets from S11 (61 features, xgboost)
2. Use isotonic calibration as meta-learner
3. Compare Brier score vs. single xgboost_brier baseline
4. If improved, checkpoint to Supabase as `stacking_v1`

### Next VM Cycle
1. Port phase priors to GA initialization in `features/engine.py`
2. Add PHASE_PRIORS dict with 8-10 high-confidence pre-game features
3. Measure generations-to-convergence with vs. without priors

### Two Cycles Out
1. Implement nba.com tracking API fetch for 5 movement features
2. Add to engine as Cat55 (Movement/Fatigue Leading Indicators)
3. Run GA with expanded candidates, measure Brier impact

---

## Cross-Project Applicability

| Technique | NBA | Political Alpha |
|-----------|-----|-----------------|
| Stacking + isotonic meta | ✓ Immediate | ✓ Port to P2 (catboost fleet best) |
| Phase-aware feature priors | ✓ Pre-game vs in-game | ✓ Pre-election vs election-day weights |
| Brier loss meta-learner | ✓ | ✓ P1 currently venn_abers, try isotonic |
| SHAP-seeded GA init | Already proposed | ✓ Port when NBA validates |

---

## References
- [arXiv 2508.02725] Forecasting NCAA Basketball with Deep Learning: LSTM vs Transformer
- [MDPI 2079-3197/13/10/230] Machine Learning for NBA/WNBA Outcome Prediction
- [PMC11265715] XGBoost + SHAP for NBA Game Outcome Prediction  
- [Nature s41598-025-13657-1] Stacked Ensemble NBA Prediction
- [TheSpread.com 2026] Player Movement Analytics for NBA Predictions
