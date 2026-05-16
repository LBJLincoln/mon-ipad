# Research Proposal: Elo Ratings as Top Feature Category
## fire-119 EVEN | 2026-05-17T04:00:00Z

### Summary
Even-cycle SOTA WebSearch confirms Elo rating features are the #1 most important feature class across multiple 2025-2026 NBA prediction studies. This directly validates the pending `vm-add-elo-ratings-engine` work-queue item (priority=75) and elevates its urgency.

### Evidence

| Source | Finding |
|--------|---------|
| IEEE Xplore 2026 — "Comparing Machine Learning Methods for NBA Game Outcome Prediction" | `team_elo`, `team_elo_5_y`, `home_next` = top-3 features across all tested models |
| MDPI Jan2026 — "Uncertainty-Aware Machine Learning for NBA Forecasting" | LR Brier=0.199 (8th confirmation); Elo features dominant; shot-chart embeddings secondary |
| arXiv 2508.02725 (NCAA LSTM Brier=0.1589) | Elo + form indicators core to deep learning pipeline |
| Scientific Reports 2025 — Stacked ensemble | Elo-based team ratings feature prominently |

### Proposed Elo Feature Category for features/engine.py

```python
# Category: elo_ratings (~12 features)
# Head-to-head rolling Elo with:
#   - Season reset to 1500 each Oct
#   - K-factor = 20 (standard)
#   - Home advantage = +100 Elo points
# Features:
#   home_elo_current         # current Elo before game
#   away_elo_current
#   home_elo_5_season_avg    # 5-season rolling avg Elo (team_elo_5_y analog)
#   away_elo_5_season_avg
#   elo_diff                 # home - away (most predictive single feature)
#   elo_win_prob             # logistic transform: 1/(1+10^(diff/400))
#   home_elo_last10          # Elo from 10 games ago (form indicator)
#   away_elo_last10
#   home_elo_trend           # home_elo_current - home_elo_last10 (momentum)
#   away_elo_trend
#   home_elo_vs_avg          # vs league average 1500
#   away_elo_vs_avg
```

### Implementation Notes
- **Prerequisite**: engine-parity-sync must complete first (54KB delta between mon-ipad and nomos-nba-agent engine.py)
- **Data**: Elo can be computed from existing `game_results` data in Supabase — no new data source needed
- **CPU-safe**: Elo computation is O(n games) per team, negligible overhead
- **Port to POL**: Political event Elo (candidate win streaks, party momentum) — medium priority after NBA validated

### Expected Gain
Based on IEEE Xplore 2026 feature importance, replacing 5-10 current weak features with Elo features could improve Brier by 0.002-0.005 (from 0.22012 toward 0.215 range). Combined with LR already confirmed at 0.199, Elo is the next highest-confidence addition.

### Priority Recommendation
After engine-parity-sync: elevate vm-add-elo-ratings-engine from priority=75 to priority=42 (between engine-parity-sync and vm-remove-stacking items).
