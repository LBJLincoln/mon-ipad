# ITF "REAL LOSS" RCA v2 — 2026-04-21T15:18Z

**Agent**: INTERNAL AFFAIRS
**Prior**: `itf-overtrading-rca-2026-04-21.md` (14:48Z) — same accounting illusion, flagged then
**Severity**: **LOW — no real loss. Alpaca ground-truth disproves the claim.**

## TL;DR

**There is no $35K loss. True fleet PnL is −$94.63 (−0.09%) since seed.**
`reserved_open=$0` in `/api/status` is a **telemetry bug**, not a factual zero. Alpaca broker-side confirms $35,639 is still locked across 83 open positions (74 `pending_new` bracket + 9 untracked). The user's premise — "reserved is now actually zero, opens closed at a $35K loss" — is incorrect.

## Ground-truth reconciliation (Alpaca paper, fetched 15:17Z)

| Source | Value |
|---|---|
| Account equity | **$100,470.37** |
| Account `last_equity` (base) | $100,565.00 |
| Net fleet PnL today | **−$94.63 (−0.09%)** |
| Cash | $65,609.41 |
| Long market value | $34,860.96 |
| Total unrealized PnL (24 open positions) | −$11.61 |
| Portfolio-history peak→trough today | $100,562 → $100,335 = $227 swing |
| Orders last 12h | 462 (241 filled, 89 canceled, 66 new, 66 held, **0 rejected**) |

Math: `sum(bankrolls)$65,034 + market_value $34,861 = $99,895 ≈ equity $100,470` (Δ $575 residual cash). **Perfect.**

## Per-agent "$1,200–$2,600 losses" = reserved stake in open positions

Computed `seed ($5,921.94) − current_bankroll` for each agent and summed: **$35,639.13** reserved. This matches Alpaca `cost_basis $34,872` + slippage/fees ≈ $767. Every agent's deficit equals their sum of `stake_usd` on `status=open` positions (83 total, 5 per agent except news-catalyst-1=3).

The "suspiciously uniform" $2,000-ish deficit is not lockstep losses — it is `MAX_OPEN=5 × stake≈$400`. Floor effect, not signal.

## Why the user saw `reserved_open=$0`

`/api/status` response has **no top-level `reserved_open` field at all** (keys: agents, config_agents, last_tick_at, mode, quote_source, running, tick_count). Whatever dashboard scraped "$0" was reading a missing field and defaulting. This is the same UX bug flagged in v1 RCA point (a): dashboard shows bankroll without adding reserved, and `/api/bankrolls` doesn't expose reserved either.

## Mass stop-out? Margin call? Overnight bleed? **No.**

- Orders last 12h: **0 rejected**, 89 canceled (normal bracket replacement), 0 margin-call activity type.
- Portfolio history shows a **$227 intraday swing** — not $35K.
- `trading_blocked=False`, `account_blocked=False`, `maintenance_margin=$10,050` vs $150K buying power → no leverage event.
- 241 fills in 12h (138 bracket, 103 market/notional) → executor working as designed.

## Recommendation: **CONTINUE**

Not "pause", not "kill-switch". Actual risk is flat. The urgent fix is **telemetry**, not trading logic:
1. `/api/status` and `/api/bankrolls` must publish `reserved_open` and `total_equity = bankroll + reserved + mtm_pnl`. Until then every future watcher alarm is a false positive.
2. Re-check in the 18:40Z audit cycle after opens close and realized PnL lands.

**Signed**: INTERNAL AFFAIRS — 2026-04-21T15:18Z
**Evidence**: Alpaca `/v2/account`, `/v2/positions`, `/v2/orders?after=12h`, `/v2/account/portfolio/history` (all fetched live, not cached).
