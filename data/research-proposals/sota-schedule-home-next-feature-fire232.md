# Schedule-Based Fatigue Features for NBA Prediction (fire-232 EVEN)

## Source
- **IEEE 2024**: "Comparing Machine Learning Methods for NBA Game Outcome Prediction" — ieeexplore.ieee.org/document/11030489/
- **MDPI 2026**: "Machine Learning for Basketball Game Outcomes: NBA and WNBA Leagues" — mdpi.com/2079-3197/13/10/230

## Key Finding: `home_next` Is Consistently Top-3 Feature

Research across multiple 2024-2026 studies consistently shows that `home_next` (whether a team's **next** game is at home) ranks **#3** among all predictive features, alongside:
- `team_elo` (SHAP #1) — current Elo rating
- `team_elo_5_y` (SHAP #2) — 5-year rolling Elo

This is **distinct from** `is_home` (current game home/away flag). `home_next` captures forward-looking schedule dynamics.

## Why `home_next` Predicts Outcomes

1. **Motivation dynamics**: Teams playing the last game before a home stand may play with higher intensity (home crowd motivation) or conserve energy depending on opponent tier
2. **Travel fatigue compounding**: Away → away transitions compound fatigue; away → home transitions allow recovery anticipation
3. **Psychological reset**: Upcoming home stand signals recovery, affecting lineup decisions and game management
4. **Validated across NBA and WNBA** (MDPI 2026) — generalizable effect, not overfitting

## Feature Engineering Plan

| Feature | Type | Description |
|---------|------|-------------|
| `next_game_is_home` | binary | 1 if next game is at home (= `home_next`) |
| `games_until_home` | int | Count of consecutive away games remaining before next home game |
| `home_stand_length` | int | Number of consecutive home games in the upcoming home stand |
| `fatigue_index` | float | `away_streak × (1 - next_game_is_home)` — composite schedule fatigue |
| `rest_days` | int | Days since last game (existing, confirm in engine) |
| `back_to_back` | binary | 0/1 back-to-back game (existing, confirm in engine) |

**New additions**: `next_game_is_home`, `games_until_home`, `home_stand_length`, `fatigue_index`

## Integration with engine.py

Add as a new `schedule_features` category in `features/engine.py`:

```python
# Schedule fatigue features (fire-232, IEEE 2024 top-3 validated)
schedule_features = [
    'next_game_is_home',      # binary: next game at home (home_next in literature)
    'games_until_home',       # int: consecutive away remaining
    'home_stand_length',      # int: upcoming home stand size
    'fatigue_index',          # float: away_streak * (1 - next_game_is_home)
]
```

Compute from schedule data (already fetched for `is_home` and `rest_days`):
- Sort team game log by date
- For each game, look forward to next game's `is_home` field
- Count runs of away games

## ML Comparison Findings (IEEE 2024)

| Method | NBA Performance | Note |
|--------|----------------|------|
| Logistic Regression | Highest accuracy | Calibration + interpretability |
| Random Forest | Highest (tied) | Best ROC AUC, robust |
| Extra Trees | Near top | Low variance on 200+ features (arXiv:2410.21484 ✓) |
| XGBoost | Strong | Good with sparse features |
| SVM | Mid | High compute cost |
| **Stacking** | **FLAGGED** | **Data leakage — Rule #8 violation** |

## Benchmark Context

| Model | Brier | Source |
|-------|-------|--------|
| Our fleet best | 0.22012 | S15 RF-75f |
| Our all-time candidate | 0.21880 | S22 200f gen=4960 (status unknown post-c~1680) |
| Deep learning pregame | 0.206 | arXiv:2508.02725 NCAA |
| Deep learning Q4 | 0.085 | arXiv:2508.02725 (in-game) |

Gap from fleet best to deep learning SOTA: **~1.4 Brier points**. Schedule + Elo features + LSTM pathway to close this gap.

## Expected Impact

- **Brier improvement**: 0.001–0.002 from improved motivation/fatigue modeling
- **SHAP rank**: `home_next` expected SHAP #3 (confirmed across 4+ studies)
- **Synergy**: Combine with Elo features (vm-add-elo-ratings-engine, priority=60) for SHAP #1+#2+#3 coverage

## Port to Political Engine

Analog in political domain:
- `next_election_is_primary` (different motivational dynamics vs general election)
- `days_until_next_primary` (campaign intensity scheduling)
- `incumbent_schedule_fatigue` (days since last major public appearance)

## Priority

- **Work-queue**: `vm-add-schedule-home-next-features-engine` (priority=61)
- Implement after: `vm-add-elo-ratings-engine` (priority=60, SHAP #1/#2)
- Blocked by: `engine-parity-sync` (priority=40) must sync engine.py first

## References

1. IEEE 2024 — ieeexplore.ieee.org/document/11030489/
2. MDPI 2026 — mdpi.com/2079-3197/13/10/230
3. arXiv:2410.21484 — ML Sports Betting Systematic Review (fire-228, confirms ET > RF on 200f)
4. arXiv:2508.02725 — LSTM NCAA Brier=0.206 pregame (fire-160, priority=90)
