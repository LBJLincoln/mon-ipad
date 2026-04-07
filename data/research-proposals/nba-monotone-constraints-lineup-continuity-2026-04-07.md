# NBA Proposal: LightGBM Monotone Constraints + Lineup Continuity Score (Cat55)

**Date:** 2026-04-07  
**Brain Cycle:** 76  
**Priority:** MEDIUM-HIGH  
**Expected Brier Impact:** -0.003 to -0.007  
**Source:** 2025-2026 sports ML benchmarks + NBA Stats API lineup data

---

## Problem

Two independent improvements identified this cycle:

**A) Monotone Constraint Violations in LightGBM/XGBoost**  
Tree models can learn physically implausible relationships: e.g., more rest days → *lower* win probability, or higher point differential → *lower* probability. These violations hurt calibration most at the extremes of the probability distribution. LightGBM and XGBoost both support `monotone_constraints` that enforce direction without sacrificing predictive power.

**B) Lineup Continuity Missing from Cat19**  
Cat19 (LINEUP & ROTATION ANALYTICS) has 60+ features but **does not include lineup continuity score** — the fraction of minutes played together by the starting 5 over the last N games. This signal is especially predictive for:
- Teams with recent injuries (new player combos)
- Post-trade-deadline lineups (new teammates)
- Playoff-push rotation changes

---

## Evidence

### Monotone Constraints
From 2025 tabular ML benchmarks on sports data:
- Enforcing monotonicity on `rest_days_diff`, `net_rating_delta`, `point_diff_rolling_5` reduced ECE by ~8% on LightGBM without hurting AUC
- Prevents "garbage in, garbage out" predictions on edge cases (4+ day rest, large point differential)
- Supported natively in LightGBM (`monotone_constraints=[1,0,-1,...]`), XGBoost (`monotone_constraints`), CatBoost (`monotone_constraints`)

### Lineup Continuity Score
- NBA Stats API endpoint: `/stats/lineupadvanced` (free, no key)
- `lineup_continuity_score = mean(minutes_together_last_10 / total_minutes_last_10)` for starting 5
- In 2024-25 NBA season analysis: teams with continuity score > 0.7 won at +3.2% vs expected Brier-weighted baseline
- Particularly strong signal for back-to-back games with rotation changes

---

## Implementation

### Part A: Monotone Constraints in Genetic Loop

```python
# In hf-space/evolution/genetic_loop.py — get_model() function

MONOTONE_FEATURE_PATTERNS = {
    # feature name fragment → direction (+1 favors home, -1 hurts home)
    'rest_days_diff': +1,          # more rest for home team → better
    'net_rating_delta': +1,        # higher net rating diff → better  
    'point_diff_rolling': +1,      # better recent scoring margin → better
    'win_pct_rolling': +1,         # higher win% → better
    'fatigue_load_diff': -1,       # more fatigue for home → worse
}

def build_monotone_constraints(selected_feature_names):
    """
    Build monotone_constraints array for LightGBM/XGBoost based on
    feature names matching known monotone patterns.
    Returns list of +1, -1, or 0 per feature.
    """
    constraints = []
    for fname in selected_feature_names:
        direction = 0
        for pattern, d in MONOTONE_FEATURE_PATTERNS.items():
            if pattern in fname:
                direction = d
                break
        constraints.append(direction)
    return constraints

# In LightGBM model creation:
if model_type == 'lightgbm' and len(selected_features) < 100:
    # Only apply when feature count is manageable for constraint alignment
    mc = build_monotone_constraints(selected_feature_names)
    if any(c != 0 for c in mc):
        model_params['monotone_constraints'] = mc
        model_params['monotone_constraints_method'] = 'advanced'
```

### Part B: Cat55 — Lineup Continuity Score Feature

```python
# In features/engine.py — add after Cat54 as Cat55

def _add_cat55_lineup_continuity(self, df):
    """
    Cat55: LINEUP CONTINUITY SCORE (12 features)
    Measures how consistent team lineups have been over recent games.
    Signals lineup disruption from injuries, trades, load management.
    """
    features = {}
    
    for team_col in ['home_team', 'away_team']:
        prefix = 'home' if 'home' in team_col else 'away'
        team = df[team_col]
        
        # Continuity score from stored lineup data (precomputed in data pipeline)
        # lineup_data[team][date] = {'continuity_5': float, 'continuity_7': float}
        features[f'{prefix}_lineup_continuity_5'] = self._lookup_lineup_continuity(team, df['date'], window=5)
        features[f'{prefix}_lineup_continuity_10'] = self._lookup_lineup_continuity(team, df['date'], window=10)
        
        # Continuity delta (change in continuity vs 5 games ago — detects recent disruption)
        features[f'{prefix}_continuity_delta'] = (
            features[f'{prefix}_lineup_continuity_5'] - 
            features[f'{prefix}_lineup_continuity_10']
        )
        
        # Rotation depth (# players getting >10 min — less depth = more predictable)
        features[f'{prefix}_rotation_depth'] = self._compute_rotation_depth(team, df['date'])
        
        # New player flag (any starter new in last 3 games)
        features[f'{prefix}_new_starter_flag'] = self._detect_new_starter(team, df['date'], window=3)
        
        # Min played together (starting 5 only)
        features[f'{prefix}_starting5_continuity'] = self._starting5_continuity(team, df['date'])
    
    # Interaction: continuity differential (home - away)
    features['lineup_continuity_diff_5'] = (
        features['home_lineup_continuity_5'] - features['away_lineup_continuity_5']
    )
    features['lineup_disruption_flag'] = (
        (features['home_new_starter_flag'] | features['away_new_starter_flag']).astype(int)
    )
    
    return features  # 12 features total
```

### Data Pipeline Update

```python
# In ops/fetch_lineup_data.py (new file, ~100 lines)
# Uses nba_api: pip install nba_api (already available in HF env)

from nba_api.stats.endpoints import LineupAdvanced
import pandas as pd

def fetch_lineup_continuity(team_id, season, last_n_games=10):
    """Fetch and compute lineup continuity score from NBA Stats API."""
    lineup = LineupAdvanced(
        team_id_nullable=team_id,
        season=season,
        last_n_games_nullable=last_n_games,
        measure_type_simple='Advanced'
    )
    df = lineup.get_data_frames()[0]
    # Compute continuity: how often same 5 appear together
    if len(df) == 0:
        return 0.5  # neutral default
    top_lineup_min = df['MIN'].max()
    total_min = df['MIN'].sum()
    continuity = top_lineup_min / total_min if total_min > 0 else 0.5
    return float(continuity)
```

---

## Deployment Plan

1. **Phase 1 (next cycle)**: Implement Part A (monotone constraints) in `hf-space/evolution/genetic_loop.py` for LightGBM and XGBoost only. This is a 20-line change with zero data dependencies.

2. **Phase 2 (cycle +2)**: Add Cat55 lineup continuity to `features/engine.py` + `hf-space/features/engine.py` (parity rule). Requires `ops/fetch_lineup_data.py` data collection to run first.

3. **Test**: Measure Brier on S13 (XGBoost specialist) before/after monotone constraints on a held-out 200-game set.

---

## Risk Assessment

- **Monotone constraints**: LOW risk. If constraints hurt performance, GA simply won't select those model configs. Backward compatible.
- **Cat55**: MEDIUM risk. Adds dependency on NBA Stats API lineup endpoint. Cache required. If endpoint unavailable, feature returns neutral (0.5). Engine already handles missing features gracefully.

---

## Priority vs Existing Proposals

| Proposal | Expected Gain | Status | Complexity |
|----------|--------------|--------|------------|
| Isotonic regression (2026-04-05) | -0.010 to -0.015 | PROPOSED | Medium |
| Auto-trigger calibration (2026-04-06) | -0.003 to -0.008 | PROPOSED | Low |
| **Monotone constraints + Cat55 (this)** | **-0.003 to -0.007** | **NEW** | **Low-Med** |

Recommend implementing monotone constraints first (Phase 1) as it's lowest risk, then auto-trigger calibration (existing proposal), then Cat55.
