# ITF — per-agent deep audit
Generated 2026-04-25 14:24 UTC
Seed: $5856.93 per agent  (seeded 2026-04-25T08:37:49Z, n_agents=17)

> NOTE: ITF does not persist LLM rationales to disk (only to in-memory /api/decisions). Each tick this resets. To get permanent decision-trail, app.py must persist `_LIVE_DECISIONS` to data/intraday/decisions.jsonl.

## Live /api/decisions snapshot (current tick only)
- 17 live decisions captured at audit time
  - `leveraged-momentum-1`   reason=
  - `breakout-1`   reason=
  - `carry-1`   reason=
  - `mean-rev-1`   reason=
  - `gap-fade-1`   reason=
  - `pairs-1`   reason=
  - `news-catalyst-1`   reason=
  - `options-1`   reason=
  - `iv-crush-1`   reason=
  - `scalper-1`   reason=
  - `earnings-gap-1`   reason=
  - `momentum-1`   reason=
  - `arbitrage-1`   reason=
  - `crypto-whale-1`   reason=
  - `breakdown-1`   reason=
  - `vol-1`   reason=
  - `macro-rotate-1`   reason=

## Alpaca order status summary (last 500)
| status | n |
|---|---:|

## Per-agent ledger summary
| agent | events | reserves | rejects | fills | bankroll | top reject reasons |
|---|---:|---:|---:|---:|---:|---|
| `breakout-1` | 166 | 5 | 154 | 1 | $5857 | duplicate_order×126, other×27, qty_invalid×1 |
| `news-catalyst-1` | 370 | 108 | 154 | 0 | $7857 | duplicate_order×113, qty_invalid×41 |
| `macro-rotate-1` | 173 | 10 | 153 | 1 | $5457 | qty_invalid×102, insufficient_bp×26, duplicate_order×25 |
| `carry-1` | 198 | 35 | 128 | 0 | $6257 | duplicate_order×124, other×4 |
| `breakdown-1` | 354 | 87 | 127 | 66 | $-7339 | duplicate_order×97, other×19, qty_invalid×11 |
| `scalper-1` | 337 | 104 | 124 | 8 | $6510 | duplicate_order×115, insufficient_bp×5, qty_invalid×2, other×2 |
| `vol-1` | 331 | 106 | 107 | 14 | $6521 | duplicate_order×99, qty_invalid×8 |
| `gap-fade-1` | 283 | 77 | 104 | 27 | $6652 | duplicate_order×94, other×9, qty_invalid×1 |
| `options-1` | 187 | 38 | 103 | 9 | $7326 | qty_invalid×63, duplicate_order×36, other×2, insufficient_bp×1 |
| `pairs-1` | 343 | 118 | 99 | 11 | $6289 | duplicate_order×96, insufficient_bp×2, qty_invalid×1 |
| `mean-rev-1` | 266 | 81 | 95 | 14 | $5544 | qty_invalid×54, duplicate_order×41 |
| `arbitrage-1` | 197 | 54 | 90 | 4 | $5544 | duplicate_order×78, qty_invalid×11, other×1 |
| `leveraged-momentum-1` | 420 | 164 | 86 | 9 | $6383 | duplicate_order×83, qty_invalid×2, insufficient_bp×1 |
| `momentum-1` | 212 | 66 | 77 | 9 | $4904 | duplicate_order×50, qty_invalid×26, unprocessable_other×1 |
| `earnings-gap-1` | 143 | 32 | 74 | 11 | $5410 | qty_invalid×66, duplicate_order×8 |
| `iv-crush-1` | 182 | 65 | 42 | 11 | $7703 | qty_invalid×22, duplicate_order×13, other×5, insufficient_bp×1 |
| `crypto-whale-1` | 116 | 42 | 9 | 37 | $-2088 | insufficient_bp×9 |

## Recent Alpaca orders (last 60)
| created | symbol | side | qty | notional | class/type | status |
|---|---|---|---:|---:|---|---|

## Open positions snapshot (0 positions)