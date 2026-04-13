# Cat60: Playoff Context Features
**Cycle:** 98 | **Date:** 2026-04-13 | **Priority:** HIGH
**Source:** preprints.org Apr 2026 — "Key Factors Influencing NBA Game Outcomes" + current playoff season context

## Problem
The engine has 59 feature categories covering regular season dynamics, but lacks a dedicated category for **playoff-specific context**. April 2026 = NBA playoffs, and playoff games have fundamentally different statistical patterns from regular season games.

Current best: 0.22251 (S14). Gap to target (0.21837): **0.00414**. Playoff features could provide the 0.4% lift needed.

## Motivation — Why Playoffs Are Different

| Factor | Regular Season | Playoffs |
|--------|---------------|----------|
| Back-to-backs | Common | Rare (1 game every 2d) |
| Home court advantage | ~58% | ~65% (elevated) |
| Coaching adjustments | Limited film | Full series film study |
| Defensive intensity | Variable | Maximum |
| Star player rest | Load management common | Never rested |
| Market efficiency | Moderate | High (large bets) |

## Proposed Features (Cat60, ~12 features)

```python
# Category 60: PLAYOFF CONTEXT FEATURES
# Applicable to playoff games (is_playoff = 1); zero-filled for regular season

def compute_playoff_features(home, away, game_date, games_df):
    feats = {}
    
    is_playoff = int(game_date.month in [4, 5, 6] and game_date.year >= 2003)
    feats['is_playoff_game'] = is_playoff
    
    if not is_playoff:
        # All features zero for regular season (no data leakage)
        for k in ['playoff_series_game_num', 'playoff_home_adv_boost',
                   'playoff_rest_days_home', 'playoff_rest_days_away',
                   'playoff_rest_advantage', 'playoff_home_wp_series',
                   'playoff_away_wp_series', 'playoff_series_tied',
                   'playoff_elimination_pressure_home', 'playoff_elimination_pressure_away',
                   'playoff_home_series_wins', 'playoff_away_series_wins']:
            feats[k] = 0.0
        return feats
    
    # Filter to same round/series games
    # Series game number (1-7)
    series_games = games_df[
        (games_df['home_team'].isin([home, away])) &
        (games_df['away_team'].isin([home, away])) &
        (games_df['date'] < game_date) &
        (games_df['is_playoff'] == 1)
    ].sort_values('date')
    
    game_num = len(series_games) + 1
    feats['playoff_series_game_num'] = game_num
    feats['playoff_home_adv_boost'] = 0.065 * is_playoff  # 6.5pp boost
    
    if len(series_games) > 0:
        # Rest days since last game
        last_home_game = games_df[
            (games_df['home_team'] == home) | (games_df['away_team'] == home)
        ]['date'].max()
        last_away_game = games_df[
            (games_df['home_team'] == away) | (games_df['away_team'] == away)
        ]['date'].max()
        
        rest_home = max(0, (game_date - last_home_game).days)
        rest_away = max(0, (game_date - last_away_game).days)
        feats['playoff_rest_days_home'] = rest_home
        feats['playoff_rest_days_away'] = rest_away
        feats['playoff_rest_advantage'] = rest_home - rest_away
        
        # Series record
        home_wins = sum(1 for _, g in series_games.iterrows()
                        if g['home_team'] == home and g['home_score'] > g['away_score']
                        or g['away_team'] == home and g['away_score'] > g['home_score'])
        away_wins = game_num - 1 - home_wins
        feats['playoff_home_series_wins'] = home_wins
        feats['playoff_away_series_wins'] = away_wins
        feats['playoff_home_wp_series'] = home_wins / max(game_num - 1, 1)
        feats['playoff_away_wp_series'] = away_wins / max(game_num - 1, 1)
        feats['playoff_series_tied'] = int(home_wins == away_wins)
        
        # Elimination pressure (facing elimination = 0 or 3 wins for other team)
        feats['playoff_elimination_pressure_home'] = int(away_wins == 3)
        feats['playoff_elimination_pressure_away'] = int(home_wins == 3)
    else:
        for k in ['playoff_rest_days_home', 'playoff_rest_days_away', 'playoff_rest_advantage',
                   'playoff_home_series_wins', 'playoff_away_series_wins',
                   'playoff_home_wp_series', 'playoff_away_wp_series', 'playoff_series_tied',
                   'playoff_elimination_pressure_home', 'playoff_elimination_pressure_away']:
            feats[k] = 0.0
    
    return feats
```

## Implementation Plan

1. **Add to engine.py** as category 60 (after current cat59 opponent graph features)
2. **Update ENGINE_VERSION** to `v3.1-60cat`
3. **Update category count** in docstring header
4. **Deploy to S14 first** (current fleet best at 0.22251) as test island
5. **Target**: series win% + elimination pressure features should improve playoff accuracy

## Expected Impact
- **Brier reduction**: 0.002–0.005 for playoff games (estimated 15% of total games)
- **Net Brier improvement**: ~0.0003–0.0008 overall
- **Combined with S15 Gen47 direction**: could push past 0.21837 threshold

## Research Backing
- preprints.org 2026-04 "Key Factors Influencing NBA Game Outcomes" — home court amplified in playoffs
- Historical: playoff home teams win ~65% vs 58% regular season (8pp lift)
- Elimination game dynamics: teams up 3-0 win ~99%, teams facing elimination win ~45%
- Series game 7 is effectively neutral-court equivalent

## Cross-Pollination Note
Playoff context features could also apply to Political Alpha:
- **Runoff election indicator** (second round = "playoff game")
- **Incumbent under pressure** (analogous to elimination pressure)
- Consider adding `is_runoff_election` and `incumbent_approval_trend` to political_engine.py

## Priority
**HIGH** — It's April 2026 playoffs. This is the highest-leverage time to add playoff features as the GA can immediately optimize on live playoff data.
