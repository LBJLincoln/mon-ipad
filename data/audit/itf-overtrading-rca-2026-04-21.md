# ITF OVERTRADING RCA — 2026-04-21

**Agent**: INTERNAL AFFAIRS  
**Window**: 2026-04-21T13:28Z (seed) → 14:38Z (now) — **70 min, 15 ticks, not 3h**  
**Seed**: $100,672.94 from Alpaca equity, split $5,921.94 × 17 personas  
**Current sum of agent bankrolls**: $65,411 → appears as -35% drawdown  
**Severity**: MEDIUM (NOT critical) — bleed is mostly **accounting illusion**, not losses

## The "35% bleed" is $40,108 in reserved open-position stake

| Status | n | $ locked | Where |
|---|---|---|---|
| `open` (reserved) | 83 | **$40,108** | Counted OUT of bankroll, not yet closed |
| `rejected` (MAX_OPEN=5) | 127 | $47,352 | Not reserved — correctly bypassed |
| `broker_error` | 30 | $13,246 | Not reserved — 22× 422 (fractional/wash) + 8× 403 |
| `filled` | **0** | — | No `filled` status records exist yet |

Reconciliation per agent: `current_bankroll + reserved_open ≈ seed $5,922`. 5/17 agents match exactly; the other 12 are **$131–$646 ABOVE seed** (not below). Fleet total recovers to **~$105,520 if all opens closed flat** — above seed. **There is no $35K loss.** There is $40K locked in open positions.

## Real issues found (worth fixing)

1. **Zero `filled` → telemetry blind spot.** Alpaca returns `accepted`/`new` on bracket submit, never "filled" until trigger. `executor.submit()` writes `status="open"`, and `close_expired` is what credits P&L. No RCA possible on decision quality until closes fire.
2. **30 broker_errors ≈ 10% submission rate.** Dominant: `carry-1` wash-trade lockout (SPY long+short same tick), `news-catalyst-1` fractional-bracket 422 on MSTR/COIN/AAPL (stake ÷ price < 1, goes notional path then returns no `qty` field). Matches `project_itf_v21_executor_apr20` — regression, not a new bug.
3. **127 MAX_OPEN=5 rejections = 44% of all decisions.** Agents are proposing ~3 trades per tick each; rejections carry no stake, but LLM calls wasted (15 ticks × avg 4.2s latency = ~60 min compute/agent).
4. **AVAX/USD herd**: 4 agents long AVAX/USD within 30s of tick 1 at $9.37 entry (iv-crush / breakout / leveraged-momentum + scalper). Weekend crypto + same thesis ("only crypto with non-zero volume") = lockstep, but triggered by tape data, not groupthink. Flag: MONITOR.
5. **False "bleed" in dashboard** — bankroll display doesn't add reserved open. User sees "-35%" and panics. This is a UX bug, not a trading bug.

## Recommendation: **CONTINUE** — do not kill-switch

Patches for FRANKENSTEIN (priority order):
- (a) `/api/bankrolls` should return `{available, reserved_open, total_equity}` — hide the phantom drawdown.
- (b) Dedupe `close_expired` to credit realized P&L in ledger within the same tick a broker position closes; right now the loop is external.
- (c) Enforce per-tick cap: `max 2 submit() calls per agent per tick` — kills the 127-rejection waste without touching MAX_OPEN=5.
- (d) `carry-1` wash fix: reject opposite-side order if same-ticker open position within 60s — stops the 403 loop.

Next 4h audit cycle will re-check once 83 open positions close and real P&L appears.

**Signed**: INTERNAL AFFAIRS — 2026-04-21T14:48Z
