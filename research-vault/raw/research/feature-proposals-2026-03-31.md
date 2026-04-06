# Research Scan: feature-proposals-2026-03-31


## generated
2026-03-31


## engine_version
v3.1-46cat


## proposals

- **Drive-Offense vs Rim-Defense Matchup**: 
- **Play Type PPP Matchup (PnR / Isolation / Transition)**: 
- **Passing Network Quality (Ball Movement vs Defense)**: 

## implementation_order

- **?**: Add defense.csv loader (DEF_RIM_FG_PCT, BLK) and passing.csv loader (AST_TO_PASS_PCT, POTENTIAL_AST, SECONDARY_AST, AST_POINTS_CREATED). Also add drive_tov_pct, drive_pts_pct from drives.csv.
- **?**: 15-line script to aggregate NBA_Play_Types_12_25.csv into team_playtypes_2025-26.json. Output: {TEAM: {play_type: ppp_float}}
- **?**: Add feature names in _build_feature_names() and computation block in build() after Cat46 block (line ~5666).
- **?**: Add loader function near load_historical_odds(). Add play_type_data param to build(). Add Cat48 computation block. Feature names registration.
- **?**: Feature names registration and computation block. No new loader needed — uses same tracking_data dict after build_tracking_data.py update.
- **?**: Re-run build_tracking_data.py with new defense + passing loaders. Validate BOS entry has def_rim_fg_pct=0.620, ast_to_pass_pct=0.086.
- **?**: Deploy updated engine.py to all 6 islands via subtree push. Run quick sanity check: expected feature count = 6211 + 14 + 16 + 10 = 6251.