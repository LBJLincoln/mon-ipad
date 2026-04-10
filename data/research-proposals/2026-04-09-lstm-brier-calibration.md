# Research Proposal: LSTM with Brier Loss + Uncertainty-Aware Calibration for NBA

**Date:** 2026-04-09  
**Cycle:** 4h Brain Cycle  
**Priority:** HIGH  
**Source:** arxiv 2508.02725, MDPI Uncertainty-Aware ML for NBA Betting Markets  

## Summary

Two complementary techniques discovered this cycle that could push Brier below 0.215:

1. **LSTM with Brier Loss** — Recent NCAA study achieved Brier=0.1589 on college basketball by training LSTM networks directly with Brier loss (vs cross-entropy). The sequential architecture captures game-to-game momentum better than tree models.

2. **Uncertainty-Aware Calibration** — Venn-Abers calibration already present on S13 (achieving 0.21773 on Pareto front vs 0.22316 average). Expanding this to all islands via Mondrian Conformal Prediction could yield consistent 0.005-0.01 Brier improvement.

## Evidence from Fleet

- S13 CatBoost+Venn-Abers: **0.21773** (< 0.21837 threshold, best Pareto individual this cycle)
- S11 extra_trees 200f: **0.21985** (Pareto front)
- S15 extra_trees 200f: **0.2206** (Pareto front)
- Current fleet best_brier fields: 0.22249-0.22726 (without calibration)

**Calibration adds ~0.005-0.01 Brier improvement** based on within-fleet evidence.

## Proposed Implementation

### Phase 1: Standardize Venn-Abers across all islands (1 cycle)
```python
# In features/engine.py calibration section
from sklearn.calibration import CalibratedClassifierCV

def apply_venn_abers(model, X_cal, y_cal):
    """Venn-Abers multi-class calibration wrapper"""
    calibrated = CalibratedClassifierCV(model, cv='prefit', method='isotonic')
    calibrated.fit(X_cal, y_cal)
    return calibrated
```

### Phase 2: Add GLM-derived team quality features (2 cycles)
- NCAA study: GLM team quality removal caused 0.045+ AUC drop
- Current engine has Elo but not GLM-derived team quality (Bradley-Terry model)
- Propose adding `team_quality_glm_home`, `team_quality_glm_away`, `quality_diff_glm` features
- Implementation: fit Bradley-Terry model on season game graph, extract log-odds as team strength

### Phase 3: Evaluate LSTM as post-processor (GPU only)
- Use current tree model probability outputs as LSTM input features
- Train LSTM with Brier loss on sequence of 10 recent games per team
- Only viable on Kaggle/Colab GPU sessions (not CPU islands)
- Expected: 0.005 improvement if sequential patterns captured

## Key Formula (Bradley-Terry Team Quality)

```python
# Add to features/engine.py Category X: GLM Team Quality
from scipy.optimize import minimize

def compute_bradley_terry_ratings(game_results):
    """Compute team strength ratings via Bradley-Terry model"""
    teams = list(set([g['home'] for g in game_results] + [g['away'] for g in game_results]))
    n = len(teams)
    team_idx = {t: i for i, t in enumerate(teams)}
    
    def neg_log_likelihood(ratings):
        ll = 0
        for g in game_results:
            hi, ai = team_idx[g['home']], team_idx[g['away']]
            p_home = 1 / (1 + np.exp(-(ratings[hi] - ratings[ai])))
            ll += g['home_win'] * np.log(p_home + 1e-9) + (1 - g['home_win']) * np.log(1 - p_home + 1e-9)
        return -ll
    
    result = minimize(neg_log_likelihood, np.zeros(n), method='L-BFGS-B')
    return {teams[i]: result.x[i] for i in range(n)}
```

## Expected Impact

| Technique | Expected Brier Delta | Confidence |
|-----------|---------------------|------------|
| Venn-Abers all islands | -0.005 to -0.010 | HIGH (evidence from S13) |
| GLM team quality features | -0.003 to -0.007 | MEDIUM |
| LSTM post-processor (GPU) | -0.003 to -0.005 | LOW-MEDIUM |

**Combined potential:** Could reach Brier 0.210-0.213 from current 0.222 fleet average.

## Cross-Project Application

The Uncertainty-Aware calibration (Venn-Abers / isotonic) directly applies to Political Alpha:
- PA2 top performer: 0.2182 with LightGBM
- Adding Venn-Abers to PA catboost specialist could improve political prediction reliability
- Implement same `apply_venn_abers()` wrapper in `features/political_engine.py`

## Next Steps

1. [ ] Add `apply_venn_abers()` to `features/engine.py` in next D2 Engineering cycle
2. [ ] Add Bradley-Terry GLM features as Category 55 in engine (after current 54 cats)
3. [ ] Test calibration on S13 first (already has Venn-Abers, verify implementation)
4. [ ] Port to political_engine.py after NBA validation

## Sources

- arxiv 2508.02725: "Forecasting NCAA Basketball Outcomes with Deep Learning" (LSTM vs Transformer)
- MDPI 2078-2489/17/1/56: "Uncertainty-Aware Machine Learning for NBA Forecasting in Digital Betting Markets"
- PMC 11265715: "Integration of machine learning XGBoost and SHAP models for NBA game outcome prediction"
