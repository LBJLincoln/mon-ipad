# Research Proposal: ELO Injection + Probability Clipping
## Date: 2026-03-27 | Priority: HIGH | Target: Brier < 0.215

## Executive Summary

Based on March 2026 research (MDPI Information 2026, Nature Scientific Reports 2025), two
techniques consistently improve NBA prediction calibration and should be implemented in the
next engine version:

1. **Explicit team ELO ratings** as features (top-3 most predictive per SHAP analysis)
2. **Probability clipping to [0.025, 0.975]** to protect Brier score from extreme mispredictions

Expected improvement: Brier 0.22126 → 0.215 (3% improvement).

## Finding 1: Team ELO is the #1 Feature (2025-2026 Research)

### Evidence
- MDPI 2025 (CNN model, Brier 0.221): SHAP analysis shows `home_next`, `team_elo_5_y`, 
  and `team_elo` are the **3 most predictive features** across ALL models tested.
- MDPI Information 2026 (Logistic Regression, Brier **0.199**): Uses rolling-form indicators 
  including Elo ratings as predictive backbone with strict chronological partitioning.
- XGBoost model in same 2026 study achieved Brier **0.202** using team momentum + ELO.

### Current Status
The Nomos42 engine (v3.0, Cat36-37) uses EWMA and MOVDA features but does NOT have 
dedicated ELO columns. Team strength is captured implicitly through win-rate and point 
differentials but not through a running ELO rating system.

### Proposed Implementation

```python
# New feature category: Cat38 - TEAM ELO RATINGS
# Add to features/engine.py after Cat37 MOVDA

ELO_K = 20  # Standard K-factor for NBA (adjust for home/away)
ELO_HOME_ADVANTAGE = 100  # ~3.5% probability advantage

def compute_elo_ratings(game_history: list) -> dict:
    """
    Compute running ELO for all teams from game history.
    Updates after each game using standard ELO formula.
    Returns {team_id: current_elo}
    """
    elos = defaultdict(lambda: 1500.0)  # Starting ELO
    
    for game in sorted(game_history, key=lambda g: g['date']):
        home = game['home_team_id']
        away = game['away_team_id']
        home_win = game['home_win']
        
        # Expected win probability
        home_elo = elos[home] + ELO_HOME_ADVANTAGE
        away_elo = elos[away]
        exp_home = 1 / (1 + 10 ** ((away_elo - home_elo) / 400))
        exp_away = 1 - exp_home
        
        # Update ELOs
        elos[home] += ELO_K * (home_win - exp_home)
        elos[away] += ELO_K * ((1 - home_win) - exp_away)
    
    return dict(elos)

# Features to add per game:
# - home_elo, away_elo
# - elo_diff (home - away)
# - home_elo_zscore (vs league mean)
# - elo_win_prob (expected home win from ELO only)
# - home_elo_5d_change, away_elo_5d_change (momentum)
# - home_elo_30d_change, away_elo_30d_change
# - elo_confidence (|elo_diff| > 100 = high confidence game)
# Total: ~12 new ELO features
```

### Expected Impact
- ELO captures team strength dynamics better than raw win % (accounts for opponent quality)
- The `elo_win_prob` feature is essentially a calibrated prior — adding it as a feature 
  and letting the GA select on it should directly improve Brier score
- Research shows logistic regression on top of ELO+features achieves Brier 0.199 

## Finding 2: Probability Clipping [QUICK WIN]

### Evidence
- March Madness 2026 ensemble achieves improved Brier by clipping to `[0.025, 0.975]`
- Prevents single badly-calibrated prediction from disproportionately hurting Brier score
- "No single wrong pick destroys the Brier score"

### Implementation (1-line fix in GA fitness evaluation)

```python
# In hf-space/evolution/genetic_algorithm.py
# In _evaluate_individual() or _compute_brier():

# BEFORE (current):
preds = model.predict_proba(X_test)[:, 1]
brier = brier_score_loss(y_test, preds)

# AFTER (add clipping):
preds = model.predict_proba(X_test)[:, 1]
preds_clipped = np.clip(preds, 0.025, 0.975)  # Protect from extreme predictions
brier = brier_score_loss(y_test, preds_clipped)
```

### Expected Impact
- Marginal improvement (~0.001-0.003 Brier) but zero cost to implement
- Particularly useful for games where model is overconfident (>97.5% or <2.5%)
- Should be applied at prediction time AND fitness evaluation time

## Implementation Priority

| Task | Effort | Expected Gain | Priority |
|------|--------|---------------|----------|
| ELO feature category (Cat38) | Medium | 0.003-0.008 Brier | HIGH |
| Probability clipping in GA fitness | Low | 0.001-0.003 Brier | HIGH (quick win) |
| LR meta-learner on top of ELO | High | 0.005-0.015 Brier | MEDIUM |

## Action Items

1. **Immediate (VM)**: Add probability clipping to `hf-space/evolution/genetic_algorithm.py` 
   on S10 (exploitation island) — 1-line change, deploy today
2. **This week**: Implement `compute_elo_ratings()` in `features/engine.py` as Cat38 
   (~50 lines of code, 12 new features)
3. **Next cycle**: Deploy Cat38 to S10, monitor for 24h, check if Brier improves

## Cross-repo Applicability

The ELO concept directly ports to Political Alpha:
- Replace team ELO with **candidate DPI (Donor Power Index) running rating**
- Update DPI after each favor delivery event (analogous to game outcome)
- Current political_engine.py has static DPI — making it dynamic (ELO-style) 
  should improve prediction of which donors receive favors next

## Sources
- [MDPI Information 2026 — Uncertainty-Aware NBA Forecasting](https://www.mdpi.com/2078-2489/17/1/56)
- [Nature Scientific Reports 2025 — Stacked Ensemble NBA](https://www.nature.com/articles/s41598-025-13657-1)
- [MDPI Computation 2025 — CNN/MLP Calibration](https://www.mdpi.com/2079-3197/13/10/230)
