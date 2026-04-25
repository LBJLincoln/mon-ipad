# Scientific Scorecard — Nomos42 Trading Floors
Generated 2026-04-25 14:00 UTC  |  Reset cutoff: 2026-04-25T08:00:00  |  Settlement-fix: 2026-04-25T09:30:00

## NBA — pre-fix archive vs post-reset live

| metric | post-reset | pre-fix delta |
|---|---:|---|
| n_days_simmed | 91 | (vs 13 pre-fix) |
| fleet bets/day (mean) | 3.2 | 3.2 (-3.41 vs 6.6) |
| active agents/day (mean) | 2.2 | 2.2 (-2.96 vs 5.2) |
| distinct cats/agent (mean) | 9.94 | 9.94 (+6.00 vs 3.94) |
| distinct cats/agent (max) | 19 | 19 (+6.00 vs 13) |
| fleet distinct cats (union) | 54 | 54 (+23.00 vs 31) |
| **mean_odds** | 1.899 | 1.899 (+0.04 vs 1.856) |
| odds range | 1.001 – 9.158 | (was 1.071 – 1.91) |
| odds unique values | 26 | 26 (+16.00 vs 10) |
| fleet PnL | -545.22 | -545.2 (-404.56 vs -140.7) |

## POL — pre-fix archive vs post-reset live

| metric | post-reset | pre-fix delta |
|---|---:|---|
| n_days_simmed | 48 | (vs 277 pre-fix) |
| fleet bets/day (mean) | 15.2 | 15.2 (+0.15 vs 15.0) |
| active agents/day (mean) | 6.2 | 6.2 (-0.52 vs 6.8) |
| distinct event_types/agent (mean) | 1 | 1.00 (-0.65 vs 1.65) |
| fleet distinct event_types | 1 | 1 (-1.00 vs 2)  ⚠ data-bug: 98.4% insider_trade |
| fleet PnL | 34.55 | 34.5 (-858.06 vs 892.6) |

## ITF — Alpaca-direct (real-time)

- Equity: $99,454.33  |  Cash: $-4,771.99  |  BP: $16,940.22  |  PDT: True

### PARENT orders (real trade decisions, last 500)
- total: 276  filled: 93  canceled: 160  rejected: 0  pending: 23
- **PARENT_FILL_RATE = 34%** (vs the misleading 12% overall fill_rate that includes bracket children)

### Bracket-child cleanup (auto-cancel artifact, NOT real failures)
- 224/224 canceled — these are stop/limit children orphaned when close_stale_losers killed parent positions

## Status & known gaps
- **NBA settlement fix verified**: day-018+ records varied alt_spread odds (1.39–3.31 range) instead of hardcoded 1.91
- **NBA parser fix verified**: agents now place bets across multiple distinct (game, category) tuples
- **POL data-bug acknowledged**: 98.4% of source events are `insider_trade`; needs upstream FEC/polling/sovereign-flow ingestion to diversify (not a parser fix)
- **ITF env loosened**: ITF_CLOSE_STALE_MAX_AGE_SEC 1h→3h, MIN_LOSS 0.5%→1.5% — should reduce premature parent-position kills + bracket-child orphan count