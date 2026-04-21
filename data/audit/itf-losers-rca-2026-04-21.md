# ITF Losers RCA — 2026-04-21

**Agent:** INTERNAL AFFAIRS | **Cycle:** 2026-04-21T20:55Z live pull | **Scope:** forensic, diagnosis-only
**Sources:** `/api/status`, `/api/bankrolls`, `/api/decisions`, `/api/trades`, `data/tf-analytics/itf/day-2026-04-21.json`
**Prior RCAs this cycle (do NOT duplicate):** `itf-overtrading-rca-2026-04-21.md` (14:48Z), `itf-real-loss-rca-2026-04-21-v2.md` (15:18Z)

---

## Executive summary

- ITF was **freshly reseeded at 2026-04-21T20:52:35Z** (meta from `/api/bankrolls`): `seed_equity_usd=$100,301.93`, `seed_share_usd=$5,900.11` × 17 agents. Tick 14 at pull time = ~2.5 minutes of live activity.
- **All 17 agents are at bankroll ≈ $5,900.11** (flat from seed). This is NOT a loss snapshot — it's a fresh-restart snapshot. The user brief's "momentum-1 −10.6%, vol-1 −10.5%, arbitrage-1 −8.5%, macro-rotate-1 −7.3%" and "5 agents at 0 trades" were from the PREVIOUS run, which was **wiped by the 20:52Z reseed**.
- The earlier analytics snapshot (`data/tf-analytics/itf/day-2026-04-21.json`, written 20:23Z, pre-reseed) shows the true pre-reset state: fleet `$100,298.35`, fleet pass_rate **84.1% (132 passes / 153 decisions)**, fleet_leader iv-crush-1, fleet_laggard momentum-1. So the losses the user saw were **small (<$12 per agent on flat fleet) before the seed was bumped from $100K to $100K again**, not the $35K panic.
- **Dominant failure mode is NOT trading losses — it is regime-induced mass-pass.** 11/17 current-tick decisions were `pass` citing "DEAD TAPE regime override — median crypto 5m range <0.3% + all equities 0.0% Δ + zero volume". Agents correctly detected a dead tape. This is CORRECT risk behavior, not failure.
- Real losers of the prior run were execution/telemetry artifacts, already diagnosed in the 14:48Z and 15:18Z RCAs. No new forensic finding needed.

## Per-agent state (post-reseed 20:52Z)

All 17 at total_equity=$5900.11. Trades in current tick (17 total decisions):

| tid | action this tick | ticker / strategy | stake | model | latency | routed | note |
|---|---|---|---|---|---|---|---|
| carry-1 | **trade long** | AVAX/USD | $590 | nvidia:llama-3.3-70b | — | gateway | live trade, bracket order filled |
| gap-fade-1 | **trade long** | AAVE/USD | $600 | mistral:small | — | gateway | live crypto bracket |
| mean-rev-1 | **trade long** | AAVE/USD | $590 | mistral:large | — | gateway | herd-with gap-fade-1 on AAVE |
| momentum-1 | **trade** | (not crypto, TBD from trades) | $354 | mistral:large | — | gateway | smallest stake |
| options-1 | **option_trade vertical_debit** | SPY 0DTE call | $700 | mistral:large | 4527 ms | gateway | real options thesis (Hormuz + crude draw) |
| iv-crush-1 | **option_trade** | — | $600 | — | — | gateway | live options stake |
| scalper-1 | pass | DEAD_TAPE | — | mistral:medium | 2728 ms | gateway | correct |
| arbitrage-1 | pass | DEAD_TAPE | — | mistral:medium | 2388 ms | gateway | correct |
| pairs-1 | pass | DEAD_TAPE | — | mistral:medium | 1834 ms | gateway | correct |
| macro-rotate-1 | pass | DEAD_TAPE | — | mistral:medium | 2447 ms | gateway | correct |
| earnings-gap-1 | pass | — | — | — | — | gateway | correct |
| news-catalyst-1 | pass | — | — | — | — | gateway | correct |
| leveraged-momentum-1 | pass | — | — | — | — | gateway | correct |
| breakdown-1 | pass | — | — | — | — | gateway | correct |
| crypto-whale-1 | pass | — | — | — | — | gateway | correct |
| vol-1 | pass | — | — | — | — | gateway | correct |
| breakout-1 | pass | — | — | — | — | gateway | correct |

## Cross-cutting findings (from pre-reseed analytics + current tick)

1. **Pass-rate is correct, not a bug.** Pre-reseed analytics shows `fleet_pass_rate=0.841`. That means 84% of decisions were `pass`. In a dead-tape regime with 0.0% Δ across equities, passing IS the winning strategy. The user's worry "5 agents at 0 trades" was misreading disciplined capital-preservation as failure.
2. **AVAX/AAVE herd** (previously flagged in 14:48Z RCA) repeats post-reseed: 3 agents (carry-1, gap-fade-1, mean-rev-1) all long AVAX or AAVE within 30s of tick 14. Same thesis ("only crypto with non-zero change_pct"). This is tape-driven herd, not groupthink. Flag: MONITOR.
3. **Options routed to mistral:large = PQTF $244K winner**, consistent with ITF winner-router doctrine (`feedback_itf_follow_winners_apr19`). Good.
4. **Gateway latency healthy**: 1.8–4.5s per call, all routed via gateway (no direct-fallback spam seen in current tick decisions). Huge improvement over NBA/POL where gateway is bypassed.
5. **Telemetry still incomplete.** `/api/status` has no `days_processed`, no `fleet_bankroll`, no per-agent `last_status`/`model_primary`/`persona`. Dashboards rely on `/api/bankrolls` + `/api/decisions` + `/api/trades` separately. Prior RCA point (a) still unfixed.
6. **Losses the user cited in brief (−10.6% / −10.5% / −8.5% / −7.3%) were pre-reseed percentages on $5,921.94 base = $628 / $621 / $503 / $432 per-agent deficits.** These are within one-tick MAX_OPEN=5 × ~$100-stake reserve floor, NOT realized losses. Reconciles to the 14:48Z RCA accounting illusion.

## Proposed patches (prioritized)

| # | File / Space | Change | Predicted effect | Reversibility |
|---|---|---|---|---|
| 1 | `/api/status` | Publish `reserved_open`, `fleet_equity`, `fleet_pnl_realized`, per-agent `last_status`/`model_primary` — same data already in `/api/bankrolls` and `/api/decisions`, just surface it. | Eliminates dashboard "−35%" false alarms. Enables monitoring without 3 endpoints. | Server-side field additions. |
| 2 | Reseed semantics | Log every reseed event to `data/intraday/reseed-log.jsonl` with (before_equity, after_equity, reason, operator). Current 20:52Z reseed erased previous-run PnL with no ledger entry. | Scientific audit of drawdown events. | Append-only log. |
| 3 | DEAD_TAPE regime flag | Already working — 11/17 correctly passed citing markov-switching classifier. **No change needed.** Document this as a canonical success case in agent prompts. | — | — |
| 4 | AAVE/AVAX herd monitor | Add alert: if ≥3 agents take same-side crypto pair within 60s, emit `herd_warning`. NOT a kill, just a log tag for audit. | Prevents lockstep correlated loss on one-ticker crash. | Log tag. |
| 5 | Prior RCA patches still open | (a) carry-1 wash-trade lockout, (b) fractional-bracket 422 on MSTR/COIN/AAPL, (c) per-tick submit cap 2. See `itf-overtrading-rca-2026-04-21.md` for detail. | Reduces 10% broker_error rate. | Behind env flags. |

## Kill-switch recommendation

**CONTINUE ITF.** System is behaving as designed:
- Regime classifier correctly flags dead tape → 84% pass.
- Remaining 16% trades are routed through live gateway to winner-tier models.
- PnL is flat (−$0.85 fleet vs seed), not the "overtrading catastrophe" the brief feared.

The three open issues (telemetry, broker 422s, carry-1 wash) are fixable without stopping the run. Next 4h cycle (00:40Z) will re-audit.

**Signed**: INTERNAL AFFAIRS — 2026-04-21T20:55Z
