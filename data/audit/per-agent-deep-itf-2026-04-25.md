# ITF — per-agent deep audit
Generated 2026-04-25 13:23 UTC
Seed: $5856.93 per agent  (seeded 2026-04-25T08:37:49Z, n_agents=17)

> NOTE: ITF does not persist LLM rationales to disk (only to in-memory /api/decisions). Each tick this resets. To get permanent decision-trail, app.py must persist `_LIVE_DECISIONS` to data/intraday/decisions.jsonl.

## Live /api/decisions snapshot (current tick only)
- 17 live decisions captured at audit time
  - `carry-1`   reason=
  - `breakout-1`   reason=
  - `iv-crush-1`   reason=
  - `leveraged-momentum-1`   reason=
  - `news-catalyst-1`   reason=
  - `options-1`   reason=
  - `vol-1`   reason=
  - `scalper-1`   reason=
  - `arbitrage-1`   reason=
  - `earnings-gap-1`   reason=
  - `momentum-1`   reason=
  - `mean-rev-1`   reason=
  - `pairs-1`   reason=
  - `breakdown-1`   reason=
  - `gap-fade-1`   reason=
  - `crypto-whale-1`   reason=
  - `macro-rotate-1`   reason=

## Alpaca order status summary (last 500)
| status | n |
|---|---:|

## Per-agent ledger summary
| agent | events | reserves | rejects | fills | bankroll | top reject reasons |
|---|---:|---:|---:|---:|---:|---|
| `breakout-1` | 101 | 5 | 89 | 1 | $5857 | duplicate_order×89 |
| `news-catalyst-1` | 305 | 108 | 89 | 0 | $7857 | duplicate_order×73, qty_invalid×16 |
| `macro-rotate-1` | 108 | 9 | 89 | 1 | $5857 | qty_invalid×89 |
| `pairs-1` | 329 | 116 | 87 | 11 | $7089 | duplicate_order×85, insufficient_bp×2 |
| `carry-1` | 156 | 35 | 86 | 0 | $6257 | duplicate_order×86 |
| `arbitrage-1` | 181 | 51 | 77 | 4 | $6744 | duplicate_order×67, qty_invalid×10 |
| `leveraged-momentum-1` | 405 | 162 | 73 | 9 | $7183 | duplicate_order×70, qty_invalid×2, insufficient_bp×1 |
| `breakdown-1` | 296 | 87 | 69 | 66 | $-7339 | duplicate_order×63, qty_invalid×6 |
| `scalper-1` | 280 | 102 | 69 | 8 | $7310 | duplicate_order×63, insufficient_bp×5, qty_invalid×1 |
| `gap-fade-1` | 244 | 77 | 65 | 27 | $6652 | duplicate_order×65 |
| `momentum-1` | 196 | 62 | 65 | 9 | $6504 | duplicate_order×42, qty_invalid×22, unprocessable_other×1 |
| `options-1` | 148 | 38 | 64 | 9 | $7326 | qty_invalid×43, duplicate_order×19, insufficient_bp×1, unprocessable_other×1 |
| `mean-rev-1` | 231 | 77 | 64 | 14 | $7144 | qty_invalid×38, duplicate_order×26 |
| `earnings-gap-1` | 122 | 25 | 62 | 10 | $7057 | qty_invalid×59, duplicate_order×3 |
| `vol-1` | 283 | 106 | 59 | 14 | $6521 | duplicate_order×52, qty_invalid×7 |
| `iv-crush-1` | 167 | 65 | 27 | 11 | $7703 | qty_invalid×15, duplicate_order×10, insufficient_bp×1, unprocessable_other×1 |
| `crypto-whale-1` | 116 | 42 | 9 | 37 | $-2088 | insufficient_bp×9 |

## Recent Alpaca orders (last 60)
| created | symbol | side | qty | notional | class/type | status |
|---|---|---|---:|---:|---|---|

## Open positions snapshot (0 positions)