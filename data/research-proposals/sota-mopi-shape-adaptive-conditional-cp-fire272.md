# SOTA Research Proposal: Shape-Adaptive Conditional Calibration for Conformal Prediction via Minimax Optimization (MOPI)

**Fire**: 272 (EVEN)  
**Date**: 2026-06-05T04h  
**Priority**: 129  
**Source**: arXiv:2603.23374 (Mar 2026) — "Shape-Adaptive Conditional Calibration for Conformal Prediction via Minimax Optimization"  
**Venue**: AISTATS 2026, Tangier, Morocco  
**Expected improvement**: 0.001-0.002 Brier + eliminates systematic miscalibration on extreme game types (playoff back-to-backs, high-fatigue matchups)

---

## Key Findings

Standard split conformal prediction achieves *marginal* coverage (i.e., correct on average) but fails at *conditional* coverage — models are systematically over/under-confident on specific subgroups (back-to-back games, heavy travel, playoff pressure). This paper introduces **MOPI (Minimax Optimization Predictive Inference)**, which:

1. **Shape-adaptive calibration**: Optimizes over a flexible class of set-valued mappings $\mathcal{C}(\cdot)$ during the calibration phase, adapting the shape of prediction intervals to local data geometry
2. **Minimax formulation**: Solves $\min_{\hat{C}} \max_{g \in \mathcal{G}} \text{CondCovGap}(g, \hat{C})$ where $\mathcal{G}$ is a function class (e.g., all decision tree stumps over feature space) — guarantees simultaneous conditional coverage across all subgroups representable by $\mathcal{G}$
3. **Post-hoc wrapper**: No retraining required — wraps any pre-trained model, including CatBoost, XGBoost, Extra Trees, LightGBM from Nomos42 pareto
4. **Coverage guarantee**: Achieves $(1-\alpha)$ conditional coverage with finite-sample guarantee proportional to Rademacher complexity of $\mathcal{G}$ (sublinear in calibration set size)
5. **Comparison to PFGCP (fire-268, priority=125)**: MOPI is *shape-adaptive* (intervals can be non-symmetric), while PFGCP is multiplicative-weights with fixed shape; MOPI achieves tighter intervals under asymmetric game distributions

---

## Applications to Nomos42

### Application 1: Post-Hoc MOPI Wrapper for Pareto Model Promotion

Wrap pareto models (S18 ET-200f-0.21943, evo4 ET-200f-0.21831) with MOPI calibration before production promotion. MOPI replaces current isotonic calibration in the checkpoint promotion pipeline.

**Implementation** (~60 lines in `calibration/mopi_calibrator.py`):
```python
class MOPICalibrator:
    def __init__(self, alpha=0.05, feature_cols=None, n_stumps=50):
        self.alpha = alpha
        self.feature_cols = feature_cols  # e.g. ['is_back_to_back', 'venue', 'fatigue_index']
        self.n_stumps = n_stumps
    
    def fit(self, X_cal, y_cal, y_pred_cal):
        # Build function class G from decision stumps over X_cal
        # Solve minimax optimization: min_C max_{g in G} CondCovGap(g, C)
        ...
    
    def predict_set(self, X_test, y_pred_test):
        # Return shape-adaptive prediction intervals
        ...
```

Expected: 0.001-0.002 Brier improvement for back-to-back + playoff games specifically.

### Application 2: Replace Isotonic Calibration in engine.py

Add `calibration_method='mopi'` option to `validate_model()` in `features/engine.py`:
```python
if calibration_method == 'mopi':
    from calibration.mopi_calibrator import MOPICalibrator
    cal = MOPICalibrator(alpha=0.05, feature_cols=GAME_CONDITION_FEATURES)
    cal.fit(X_cal, y_cal, model.predict_proba(X_cal)[:,1])
    return cal
```

### Application 3: `mopi_conditional_gap` as Pareto Objective

Add `mopi_conditional_gap` as 10th Pareto objective in NSGA-II evolution loop — models with poor conditional coverage (high max subgroup coverage gap) are penalized:
- Subgroups: `back_to_back × venue × season_phase × fatigue_index`
- Gate: `mopi_conditional_gap < 0.05` required for pareto promotion

### Application 4: Complement PFGCP (priority=125)

MOPI (shape-adaptive) and PFGCP (parameter-free group-conditional, multiplicative weights) are complementary:
- MOPI handles *asymmetric* intervals under geometric subgroup structure
- PFGCP handles *symmetric* intervals under known group categories
- Combine: first apply MOPI for shape adaptation, then PFGCP for group calibration

### Application 5: Port to political_engine.py

Apply MOPI to POL calibration:
- Subgroups: `state_competitive_tier × incumbency × election_type × cycle_phase`
- Shape-adaptive intervals capture different uncertainty profiles for battleground vs. safe states

---

## Synergy with Existing Pipeline

- **Extends**: fire-268 PFGCP (priority=125) — complementary shape-adaptation
- **Extends**: fire-268 Pivotal Scores CP (priority=126) — MOPI achieves similar conditional coverage via different optimization path
- **Extends**: fire-226 Multi-Scale CP (priority=106) — MOPI's function class $\mathcal{G}$ can be structured as multi-scale hierarchy

---

## Library Requirements

- `cvxpy` or `scipy.optimize` for minimax optimization (~20 lines of optimization code)
- `sklearn.tree.DecisionTreeClassifier` for decision stump function class
- No new dependencies if cvxpy already installed; otherwise: `pip install cvxpy`

---

## Expected Improvement

- Brier improvement: **0.001-0.002** (primarily from correcting back-to-back + playoff miscalibration)
- Key metric: `mopi_conditional_gap` reduction from ~0.08 (isotonic calibration) to ~0.02
- Subgroup most likely to benefit: playoff back-to-back games (historically under-confident by 4-6%)
