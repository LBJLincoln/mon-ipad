# NBA Research Proposal: Era-Normalized Per-100-Possession Features + Season-Fixed Effects
**Date:** 2026-04-11  
**Cycle:** 90  
**Priority:** HIGH  
**Source:** MDPI Information Systems 2026 — Uncertainty-Aware NBA Forecasting (Brier 0.089 fused model)

## Summary
Add era normalization (per-100-possession statistics with season-fixed effects) to the feature engine to eliminate the 2010–2026 pace revolution bias. The MDPI 2026 paper achieved Brier **0.089** by fusing these normalized features with market-implied probabilities — representing a 57% improvement over our current best (0.21570).

## Problem
Raw box-score statistics are **era-biased**: teams in 2026 shoot 40+ 3-pointers/game vs 15 in 2010. Without normalization:
- Feature importance shifts with era rather than team skill
- Cross-season models mix pace-adjusted and raw stats leading to hidden bias
- Rolling averages conflate team improvement with league-wide style changes

## Proposed Features (15 new features in engine.py)

### Per-100-Possession Normalization
```python
# Current: raw stats (points, rebounds, assists)
# Proposed: per-100-possession adjusted
pos_per_game = team_pace  # possessions used per game
pts_per100 = (raw_pts / pos_per_game) * 100
reb_per100 = (raw_reb / pos_per_game) * 100
ast_per100 = (raw_ast / pos_per_game) * 100
tov_per100 = (raw_tov / pos_per_game) * 100
```

### Season-Fixed Effects
```python
# Z-score relative to that season's league average
season_avg_pts = df.groupby('season')['pts_per100'].transform('mean')
season_std_pts = df.groupby('season')['pts_per100'].transform('std')
pts_season_z = (pts_per100 - season_avg_pts) / season_std_pts
```

### Features to Add to engine.py
1. `team_pts_per100_5g` — 5-game rolling points/100 possessions
2. `opp_pts_per100_5g` — opponent points allowed/100
3. `team_pts_season_zscore` — season-normalized offensive efficiency
4. `opp_pts_season_zscore` — season-normalized defensive efficiency
5. `pace_diff` — home_pace - away_pace (game tempo predictor)
6. `efg_pct_per100` — effective FG% (already pace-neutral, validate)
7. `ts_pct_per100` — true shooting % per 100 possessions
8. `ast_to_tov_per100` — assist/turnover ratio (pace-adjusted)
9. `reb_pct_per100` — rebounding rate adjusted for possessions
10. `def_rtg_season_z` — defensive rating, season z-score
11. `off_rtg_season_z` — offensive rating, season z-score
12. `net_rtg_season_z` — net rating, season z-score
13. `era_3pt_rate` — season's league-avg 3pt rate (era marker)
14. `team_3pt_rate_vs_era` — team 3pt rate minus era average
15. `pace_season_z` — team pace relative to season average

## Implementation

### File: `features/engine.py`
Add new feature category (Cat60: ERA NORMALIZATION) with the 15 features above.

### Key Code Pattern
```python
def _era_normalized_features(self, game: dict) -> tuple:
    """Cat60: Per-100-possession + season-fixed effects (20 features)."""
    features, names = [], []
    
    pace = game.get("home_pace", 97.5)  # possessions per game
    season = game.get("season", "2025-26")
    season_avg_pace = game.get("season_avg_pace", 97.5)
    
    pts_per100 = (game.get("home_pts_l5", 110) / pace) * 100
    opp_pts_per100 = (game.get("away_pts_l5", 110) / pace) * 100
    
    season_avg_pts = game.get("season_avg_pts_per100", 110)
    season_std_pts = game.get("season_std_pts_per100", 8.0)
    pts_z = (pts_per100 - season_avg_pts) / max(season_std_pts, 1)
    
    features.append(pts_per100); names.append("home_pts_per100_l5")
    features.append(opp_pts_per100); names.append("away_pts_per100_l5")
    features.append(pts_z); names.append("home_pts_season_z")
    features.append((pace - season_avg_pace) / max(1, season_avg_pace)); names.append("pace_vs_season_norm")
    
    return features, names
```

## Expected Impact
- Eliminates era-mixing bias → estimated **+0.003 to 0.005 Brier improvement**
- Better cross-season generalization in walk-forward validation
- Directly improves the 22-week walk-forward Brier (currently 0.22447 Kaggle)

## Cross-Port
Same normalization applicable to Political Alpha (normalize financial metrics by year/cycle era).

## Assign To
- **Kaggle Karpathy loop**: Implement + test as isolated Brier experiment
- **S12 (extra_trees)**: Strongest candidate to benefit from era-normalized inputs
- **Priority**: After stacked ensemble implementation (which builds on existing features first)

## References
- [MDPI Information Systems 2026: Uncertainty-Aware NBA Forecasting](https://www.mdpi.com/2078-2489/17/1/56) — Brier 0.089 fused model
- [Nature Scientific Reports 2025: Stacked Ensemble](https://www.nature.com/articles/s41598-025-13657-1)
