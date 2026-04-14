# Research Proposal: ELO Features + Isotonic Calibration
**Cycle:** 102 | **Date:** 2026-04-14 | **Priority:** HIGH

## Motivation

WebSearch results from cycle102 surfaced two high-impact techniques from 2025-2026 NBA prediction literature:

1. **ELO features** — `team_elo`, `team_elo_5y`, `home_next` are consistently the top 3 most influential features across all models (MDPI 2025: *Uncertainty-Aware ML for NBA Forecasting*)
2. **Isotonic calibration** — Logistic regression with `CalibratedClassifierCV(method='isotonic')` achieves Brier 0.199 (best tabular result), while XGBoost gets 0.202. Our fleet best is 0.22195 — isotonic post-calibration alone could close ~50% of the remaining gap.

Sources:
- [Uncertainty-Aware ML for NBA Forecasting (MDPI 2026)](https://www.mdpi.com/2078-2489/17/1/56)
- [Stacked Ensemble for NBA Prediction (Nature Scientific Reports 2025)](https://www.nature.com/articles/s41598-025-13657-1)
- [XGBoost + SHAP for NBA (PMC 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11265715/)

## Proposal 1: ELO Feature Block (engine.py Cat55)

Add 5 ELO-based features as a new category (`cat55_elo_dynamics`) to `features/engine.py`:

```python
# cat55_elo_dynamics — 5 features
def compute_elo_dynamics(home_team, away_team, game_date, elo_df):
    """
    ELO-based features consistently ranked top-3 in 2025-2026 NBA literature.
    Source: team_elo, team_elo_5y, home_next (MDPI uncertainty-aware study).
    """
    feats = {}
    # 1. Raw ELO gap (home - away)
    feats['elo_gap'] = elo_df.loc[home_team, 'elo'] - elo_df.loc[away_team, 'elo']
    # 2. 5-year rolling ELO (dynasty signal)
    feats['home_elo_5y'] = elo_df.loc[home_team, 'elo_5y_avg']
    feats['away_elo_5y'] = elo_df.loc[away_team, 'elo_5y_avg']
    # 3. ELO momentum (last 7 days delta)
    feats['home_elo_momentum_7d'] = elo_df.loc[home_team, 'elo_delta_7d']
    # 4. Home advantage ELO adjustment (empirically ~+100 ELO pts)
    feats['elo_home_adj_gap'] = feats['elo_gap'] + 100
    return feats
```

**Data source:** FiveThirtyEight historical ELO data (public, downloadable) or computed from game history using standard ELO update rule (K=20, home_adv=100).

**Expected Brier impact:** -0.001 to -0.003 (ELO gap is the single highest-MI feature per SHAP analysis in PMC study).

## Proposal 2: Isotonic Calibration Post-Processing

Add a calibration wrapper to the genetic algorithm evaluation loop in HF spaces:

```python
from sklearn.calibration import CalibratedClassifierCV

# In GA individual evaluation (evaluate_individual function):
def evaluate_with_calibration(model, X_train, y_train, X_val, y_val):
    # Fit on training fold
    model.fit(X_train, y_train)
    # Wrap with isotonic calibration on validation split
    cal_model = CalibratedClassifierCV(
        model, method='isotonic', cv='prefit'
    )
    cal_model.fit(X_val, y_val)  # calibrate on held-out val
    # Score on test
    proba = cal_model.predict_proba(X_test)[:, 1]
    brier = brier_score_loss(y_test, proba)
    return brier, cal_model
```

**Why isotonic over sigmoid:** Isotonic is non-parametric and handles the asymmetric probability distributions common in NBA games (strong favorites ~0.7+ win rate). Sigmoid (Platt scaling) assumes symmetric logistic shape.

**Expected Brier impact:** -0.002 to -0.005 (literature: isotonic reduces Brier by 5-15% on tree models vs raw output).

## Implementation Plan

| Step | File | Change | Cycle |
|------|------|--------|-------|
| 1 | `features/engine.py` | Add cat55_elo_dynamics (5 features) | 103 |
| 2 | `hf-space/features/engine.py` | Sync cat55 to HF space | 103 |
| 3 | `hf-space/app.py` | Add isotonic calibration in evaluate_individual | 104 |
| 4 | Monitor S14/S15 | Deploy calibration to best 2 islands first | 104 |

## Cross-Project Application

**Political Alpha:** Same isotonic calibration applies directly to political engine. The `CalibratedClassifierCV` wrapper can be added to `features/political_engine.py` evaluation loop with zero modification. Expected political Brier improvement: -0.002 to -0.004 (current best 0.2499 → ~0.246).

## Risk Assessment

- **ELO features:** Low risk — additive features, engine parity maintained, GA will select or ignore
- **Isotonic calibration:** Medium risk — changes evaluation loop logic. Must test on one island (S14) before fleet-wide rollout. Revert plan: remove cv='prefit' wrapper, restore raw predict_proba.

## Why Not Implement Now

Rule 3: "1 fix per iteration — never multiple simultaneous changes." This cycle already sent diversify to S12+S16. Engine changes in next cycle (103) after observing diversify results.
