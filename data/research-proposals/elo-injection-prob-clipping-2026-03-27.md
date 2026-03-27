# Research Proposal: ELO Injection + Probability Clipping

**Date**: 2026-03-27  
**Priority**: HIGH  
**Based on**: 2025-2026 Academic Research (MDPI Information 2026, Nature Scientific Reports 2025)  
**Target**: Brier score from 0.22126 → sub-0.21837 (checkpoint trigger)

## Background

Analysis of 2025-2026 NBA prediction literature reveals two high-impact, low-cost improvements:

1. **Team ELO is the #1 predictive feature** — consistently ranked top-3 by SHAP across all models
   (MDPI 2025: `home_next`, `team_elo_5_y`, `team_elo`). Current engine has EWMA momentum
   features but no explicit Elo rating system.

2. **Probability clipping to [0.025, 0.975]** — technique from March Madness 2026 competition
   that prevents extreme probability predictions from destroying Brier score on upsets.
   Each wrong prediction at 0.99 probability costs 0.9801 Brier; clipping to 0.975 caps cost at 0.9506.

## Evidence from Literature

| Paper | Model | Brier Score | Key Feature |
|-------|-------|-------------|-------------|
| MDPI Information 2026 | Logistic Regression (no leakage) | **0.199** | ELO + home court |
| MDPI Information 2026 | XGBoost | 0.202 | ELO + rolling form |
| MDPI Computers 2025 | CNN | 0.221 | Home next + ELO |
| MDPI Computers 2025 | LR/RR | 0.223 | Home next + ELO |
| Current fleet best (S14) | RandomForest | 0.22126 | 34 features |

The 2026 paper achieving Brier 0.199 uses ELO + home court + rolling form, with strict chronological
partitioning (train ≤2022, val 2023, test 2024) — directly comparable to our setup.

## Proposed Changes

### Change 1: Add Cat38_ELO to features/engine.py

Add a new feature category with ~12 ELO-based features:

```python
# Cat38: ELO Ratings
# Standard 538-style ELO with K=20
def compute_elo_features(home_team, away_team, elo_ratings, date):
    elo_home = elo_ratings.get(home_team, 1500)
    elo_away = elo_ratings.get(away_team, 1500)
    elo_diff = elo_home - elo_away
    elo_win_prob = 1 / (1 + 10 ** ((elo_away - elo_home) / 400))
    
    features = [
        elo_home,                          # elo_home
        elo_away,                          # elo_away
        elo_diff,                          # elo_diff
        elo_win_prob,                      # elo_win_prob
        elo_home - elo_ratings.get(f"{home_team}_5d", elo_home),  # elo_home_5d_change
        elo_away - elo_ratings.get(f"{away_team}_5d", elo_away),  # elo_away_5d_change
        elo_home - elo_ratings.get(f"{home_team}_10d", elo_home), # elo_home_10d_change
        elo_away - elo_ratings.get(f"{away_team}_10d", elo_away), # elo_away_10d_change
        elo_home / max(elo_away, 1),       # elo_ratio
        abs(elo_diff),                     # elo_abs_diff (upset potential)
        1 if elo_diff > 100 else 0,        # elo_strong_favorite
        1 if abs(elo_diff) < 30 else 0,   # elo_toss_up
    ]
    return features
```

**ELO Update Rule** (after each game):  
`new_elo = old_elo + K * (actual_result - elo_win_probability)`  
where K=20, resets to 1505 at season start with 2/3 carryover.

**Data source**: FiveThirtyEight NBA ELO dataset covers 2018-2026.
Alternative: compute from game results already in Supabase.

### Change 2: Probability Clipping in GA Fitness Evaluation

In `hf-space/evolution/ga_engine.py`, after `model.predict_proba()`:

```python
# Before (current):
probs = model.predict_proba(X_val)[:, 1]
brier = mean_squared_error(y_val, probs)

# After (with clipping):
probs = np.clip(model.predict_proba(X_val)[:, 1], 0.025, 0.975)
brier = mean_squared_error(y_val, probs)
```

This is a 1-line change. Deploy to all 6 islands immediately.

## Expected Impact

| Improvement | Expected Brier Delta | Confidence | Implementation Effort |
|-------------|---------------------|------------|---------------------|
| Probability clipping | -0.002 to -0.005 | HIGH | 1 line, deploy now |
| ELO features (Cat38) | -0.003 to -0.008 | HIGH | ~50 lines |
| Combined | -0.005 to -0.013 | MEDIUM | 2 PRs |

**Current fleet best**: 0.22126 (S14)  
**Expected range after**: 0.208 – 0.216  
**Target checkpoint**: < 0.21837  

## Implementation Priority

1. **IMMEDIATE**: Probability clipping (1 line, 0 risk) → all 6 islands  
2. **SHORT-TERM**: Add Cat38_ELO to engine.py and push parity to HF spaces  
3. **VALIDATION**: Monitor S10 for 2 cycles, then fleet-wide if Brier improves  

## Cross-Project Insight

NBA ELO features parallel the DPI (Donor Power Index) in Political Alpha — both are composite
strength/influence ratings. If ELO improves NBA prediction, the Donor Power Index could similarly
benefit from:
- Momentum-adjusted DPI (DPI trend over 30/60/90 days)
- Relative DPI (vs sector average)
- Interaction: DPI × policy heat × sector ELO equivalent

## References

- [Uncertainty-Aware ML for NBA (MDPI Information 2026)](https://www.mdpi.com/2078-2489/17/1/56)
- [ML for Basketball Outcomes (MDPI Computers 2025)](https://www.mdpi.com/2079-3197/13/10/230)
- [Stacked Ensemble for NBA (Nature Scientific Reports 2025)](https://www.nature.com/articles/s41598-025-13657-1)
- [March Madness 2026 Prob Clipping](https://jtmarcu.github.io/projects/march-madness.html)
