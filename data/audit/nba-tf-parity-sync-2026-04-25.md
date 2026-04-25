# NBA TF parity sync 2026-04-25T11:15Z

**Trigger:** user "all perfect, finally" — verified parlay/full-decisions code parity local↔Space.

## Findings

- **Parlays**: implemented in code (lines 2367-2467, cap 8/day, 2-6 legs, settled all-or-nothing with combined odds). Already in local app.py.
- **`/api/day-decisions/full`** endpoint: implemented at line 4780, returns per-agent `{allocations: [{game_idx, category, side, odds, stake_pct, edge}], parlays: [{legs, stake_pct, combined_odds}], rationale, llm_ok}` for last 30 days max.
- **sha256 mismatch**: local `da3dc79163...` vs Space `29fac0cd30...` BEFORE sync. Local was ahead.

## Action

- Uploaded local `scripts/arena/hf-llm-trading-floor/app.py` to Space `LBJLincoln26/nba-llm-trading-floor`
- Hub commit: `c43e4b5cf15094e970b4ad4fdc6933f1cb6936df`
- post-upload sha: `da3dc79163a5ca9c20980611823992b563479d6ed666adddc9d9155507f5c523` (parity ✓)
- hot-restart issued
- post-restart `/api/day-decisions/full` returns `{"total_days":0,"days":[]}` (route resolved)
- post-restart `/api/status` returns `running:True, days_processed:48` (state preserved from morning DAY-0)

## Verification

- `/api/day-decisions?detail=full` ✓ resolves
- `/api/day-decisions/full` ✓ resolves
- `/api/run` ✓ resumes engine
