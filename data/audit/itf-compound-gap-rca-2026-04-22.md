# ITF Compound-Gap RCA — 2026-04-22

Signed: INTERNAL AFFAIRS
Timestamp: 2026-04-22T02:45Z
Scope: Intraday Trading Floor only (NBA / POL / PQTF not touched)
Upstream incident: app.py:990 truthful-doctrine + executor.py MIN_HOLD_SEC=900 fix shipped at commit 9f846905a

---

## TL;DR

The ITF Space was **reseeded at 2026-04-22T02:35:34Z** (48 min before this audit) as part of the compound-gap fix deploy, which is why `/api/bankrolls` and `/api/leaderboard` show all 17 agents at a clean $5,942.89 with 0 trades / 0 realized PnL — that's the expected state 2 ticks into a fresh run, NOT the bug.

The real bug is **upstream of the ledger**: the 232 daytrades that drained buying-power to $1.9K over the preceding 36 hours were placed by an executor that could not trace broker fills back to any persona, so the sub-bankroll ledger never recorded a single realized PnL event. Three concrete defects:

1. **`_make_client_order_id` not deployed** — local `executor.py` has agent-tagged client_order_ids ("tid:TICKER:hex8"), but the HF Space copy doesn't. All 2,059 live orders in the last 49h carry random UUIDs. No reconciler can ever map a fill to a persona.
2. **No fill-reconciliation cron** — `RECON_CURSOR_PATH` is declared as a constant but there's no function that reads Alpaca fills, matches them to open positions by client_order_id, and calls `credit_bankroll` with realized PnL. `close_expired` only credits back the reserved stake (line 695: `stake + pnl` where `pnl=0` because `_mark_to_market` uses local `quote_fn`, not broker fills). `close_position` explicitly credits only the stake back (line 842-854) and leaves a comment saying "P&L reconciles … next tick via a snapshot reconciliation" — that reconciler was never written.
3. **Positions ledger doesn't survive factory reboot** — `data/intraday/positions.json` is NOT in the HF repo manifest (404 on `hf_hub_download`). It's written to the container filesystem and evaporates on every restart. The 232 daytrades that generated $97K of notional buy flow have no local record at all.

Net effect: fleet-realized-PnL is structurally **unknowable** per agent. The $300 of unrealized PnL sitting on the Alpaca account (+$572 AAVEUSD +$40 XLK +$57 ETHUSD minus small bleeders) can't be attributed, so persona selection pressure is zero — every persona looks equally good/bad on the leaderboard.

---

## 1 · Alpaca ground truth (2026-04-21T13:33 → 2026-04-22T01:27, 12h window, 500-fill cap)

| Metric | Value |
|---|---|
| Account equity | $101,022.26 |
| Cash | $44,355.51 |
| Market value | $56,666.75 (56% of equity) |
| Buying power | $79.50 ← drained |
| Pattern-day-trader flag | **True** |
| Daytrade count | 232 |
| Open positions | 29 |
| Total unrealized PnL | +$738.05 (+0.7% on MV) |
| AAVEUSD concentration | $24,759 / 24.5% of equity / +$572 upnl |
| Crypto MV vs equity MV | $30,036 crypto / $26,630 equity |

### Portfolio equity trajectory (Alpaca `/v2/account/portfolio/history`, 2D/1H)
- base_value: $100,000.00
- first: $100,224.69 → last: $100,296.60 (Δ **+$71.91 over 14 hours**)
- peak: $100,945.57 → trough: $100,119.91 → drawdown: −$825.66

**This is the compound gap**: ~$97K gross buy notional cycled through, ~$74K sell notional cycled out, net +$71 realized. **97k of volume to move $71 of PnL = slippage + spread is eating everything.**

### Fill distribution (500 most recent fills)

- 267 buys + 233 sells = 500 fills
- Total buy notional: $97,198
- Total sell notional: $74,320
- Net flow (buys-sells): +$22,878 (that's cash still parked in open positions)

### Hold-time distribution (FIFO-matched buy→sell per symbol, 163 round-trips)
| percentile | minutes |
|---|---|
| p10 | 13.6 |
| p50 | 150.4 |
| p90 | 284.5 |

- Held < 15 min (MIN_HOLD_SEC threshold): **18/163 = 11.0%**
- Those 11% are the exact positions the new `blocked_by_min_hold` guard is designed to kill. The 89% already held past the threshold — so the minimum-hold fix is correctly scoped.

### Top churn symbols (by fill count)
| Symbol | buys | sells | buy $ | sell $ | net $ |
|---|---:|---:|---:|---:|---:|
| AAVE/USD | 84 | 40 | 41,714 | 19,486 | **−22,227** (accumulation, this is the single surviving bet) |
| AVAX/USD | 32 | 35 | 12,917 | 17,769 | +4,851 |
| XLU | 11 | 31 | 1,907 | 3,614 | +1,707 |
| UVXY | 16 | 17 | 2,269 | 3,515 | +1,246 |
| SPXL | 6 | 13 | 1,419 | 3,051 | +1,632 |
| VXX | 14 | 17 | 2,303 | 2,733 | +430 |

**AAVEUSD accumulated 84 buys vs 40 sells (2.1× ratio) for 24.5% of equity**. This is almost certainly `crypto-whale-1` or `momentum-1` — but we can't prove it because no client_order_id is tagged.

---

## 2 · Per-persona ledger (after 2026-04-22T02:35:34Z reseed)

From `/api/bankrolls` and `/api/leaderboard`:

| persona | tier | bankroll | decisions | trades | realized | unrealized | open |
|---|---|---:|---:|---:|---:|---:|---:|
| ALL 17 | — | 5,942.89 | 0 | 0 | 0.00 | 0.00 | 0 |

Fleet meta: `seed_equity_usd=101,029.15`, `seed_share_usd=5,942.89`, `seeded_at=2026-04-22T02:35:34Z`, `tick_count=2`.

**This table is accurate for post-restart state** — 2 ticks in, no trades yet. Everything pre-restart is lost because `positions.json` is not persisted to the HF repo.

### Pre-restart activity (inferred from 500 fills, cannot attribute)

- Top-3 candidate BLEEDERS (by symbols with negative sell-minus-buy that closed): **AAPL (−$1,341), NVDA (−$604), ETHUSD (−$269)** — symbols where more was spent buying than sold back, and underlying didn't rally.
- Top-3 candidate WINNERS: **SPXL (+$1,632), XLU (+$1,707), UVXY (+$1,246)** — these are VIX/leveraged-ETF day-scalps where the sold-notional exceeded bought-notional AND position is now flat.
- **CANNOT identify the persona behind any of these** because `client_order_id` is a random UUID on every order.

---

## 3 · Reconciliation-gap diagnosis: why `/api/bankrolls` shows zero activity

### Evidence chain

1. **Deployed executor.py verified** (`hf_hub_download` → 36,105 bytes):
   - `_make_client_order_id`: **NOT PRESENT** in deployed code
   - `MIN_HOLD_SEC`: present (the fix WAS deployed)
   - `RECON_CURSOR_PATH`: **NOT PRESENT**
   - `fill_reconciliation`: **NOT PRESENT**
   - `blocked_by_min_hold`: present

2. **Alpaca orders**: 2,059 orders pulled spanning 2026-04-20T01:30 → 2026-04-22T02:03. `client_order_id` format breakdown: **2,059 / 2,059 = 100% random UUID**. Zero agent-tagged orders.

3. **HF Space repo manifest**: no `data/intraday/positions.json`, no `data/intraday/agent_bankrolls.json`, no `data/intraday/agent_ledger.jsonl`, no `data/intraday/dry-run-orders.jsonl`. These files exist only on the container's ephemeral filesystem. Any factory_reboot wipes them.

4. **Close-path doesn't realize PnL**:
   - `close_expired` line 695 credits `stake + pnl` where `pnl` comes from `_mark_to_market` using the **local** `quote_fn` — which on a crypto fill delta of 0.1% gives noise-level numbers, not actual broker-realized PnL.
   - `close_position` line 842-854 explicitly writes "we don't have a live quote for exact P&L, so credit only the reserved stake" and defers to "a snapshot reconciliation … next tick" that doesn't exist.

### So why is the leaderboard zero?

- Container restarted at 2026-04-22T02:35:34Z (post-fix deploy).
- `seed_bankrolls(tids, force=True)` ran via `/api/reset` → all 17 agents seeded at $5,942.89.
- Tick 1 + 2 have executed (tick_count=2) but no trades yet (market partially closed, agents warming up).
- Positions.json is empty on the new container.
- Meanwhile, 29 real positions still sit on the Alpaca account from BEFORE the restart, worth $56,666 + $738 unrealized — completely invisible to the fleet's internal ledger.

**The agents reseeded with $5,942.89 each do not own any of the 29 open Alpaca positions.** The fleet is effectively running 17 paper accounts on top of a broker account that already has someone else's 29 positions on it.

---

## 4 · Three concrete patches for DR FRANKENSTEIN

### Patch 1 — Deploy `_make_client_order_id` + verify all orders are agent-tagged

**File**: `scripts/arena/hf-intraday-trading-floor/executor.py:248-255` (already written locally, NOT on HF).

**Action**: `HfApi.upload_file` the local `executor.py` (36,268 bytes) to the Space, then factory_reboot. Verify by pulling 10 new orders after the first live tick and confirming `client_order_id` starts with a known `tid:`.

**Why this is P0**: without this, zero of the other reconciliation work pays off. Every persona attribution depends on this tag.

### Patch 2 — Write the fill reconciler that populates `agent_ledger.jsonl` from broker fills

**File**: `scripts/arena/hf-intraday-trading-floor/executor.py` — new function, ~80 LOC.

Required behavior (pseudocode):
```python
def reconcile_fills(now_utc, fleet_tids) -> dict:
    """Read Alpaca fills since last cursor, match to open positions by client_order_id,
    mark them closed with realized_pnl_usd, and credit each agent's sub-bankroll.
    Persist cursor to RECON_CURSOR_PATH. Call from tick_once() top-of-tick."""
    cursor = _load_cursor()  # last fill id OR last transaction_time
    fills = alpaca_fills_since(cursor)
    positions = _load_positions()
    for f in fills:
        coid = alpaca_order_client_id(f["order_id"])  # 1 extra API call per order_id, cache
        tid, ticker, _hex = coid.split(":", 2) if coid and ":" in coid else (None, None, None)
        if not tid or tid not in fleet_tids:
            continue  # not our order
        # Match: find the open position with that broker_order_id
        for p in positions.get(tid, []):
            if p.get("broker_order_id") == f["order_id"] and p["status"] == "open":
                # ... compute realized_pnl from entry_price + fill price
                # ... call credit_bankroll(tid, stake + pnl, meta={...})
                # ... mark p["status"] = "closed_reconciled"
    _save_positions(positions)
    _save_cursor(fills[-1]["id"] if fills else cursor)
```

**File**: `scripts/arena/hf-intraday-trading-floor/app.py:~1200` (tick_once, already calls `refresh_broker_statuses`). Add `executor.reconcile_fills(now_utc, [p.tid for p in config_agents])` one line below.

**Why**: this is the ONLY way realized PnL ever lands in the per-agent bankroll when positions close via bracket stop/TP or via agent-driven `close_position` calls on the broker side.

### Patch 3 — Persist `positions.json` / `agent_bankrolls.json` / `agent_ledger.jsonl` to the HF repo

**File**: `scripts/arena/hf-intraday-trading-floor/app.py` — new cron-on-tick or end-of-tick hook.

Required behavior: at end of each tick (or every Nth tick to limit HF write quota), upload the three ledger files to the Space repo via `HfApi.upload_file(..., repo_type='space', commit_message='[ITF] ledger snapshot tick=...)`. Analogous to how NBA/POL TFs snapshot `day-XXX.json`.

**Why**: without this, every factory_reboot (our own or HF's spontaneous sleep) silently zeros the leaderboard. We've already lost 36 hours of attribution.

**Alternative**: mount `/data` as a persistent HF Space volume (if the account tier supports it). Check Space settings — LBJLincoln26 pro tier should, Nomos42 free doesn't. If supported, that's lower-friction than commit-on-tick.

---

## 5 · Follow-up items (NOT for this patch cycle)

- The 29 stranded positions on Alpaca need to be either (a) adopted by the new fleet via a one-time import into `positions.json` with dummy `agent_tid="pre-restart-pool"`, or (b) flattened via `DELETE /v2/positions` once equity markets open. If they're left as-is, they'll close via bracket orders with no one's ledger updating. Recommend option (a) with a dedicated pool tid so the PnL at least lands somewhere scientific.
- `daytrade_count=232` is now locked behind the MIN_HOLD_SEC guard. Monitor the 5-day PDT rolling window: if >3 in any rolling 5-business-day window, Alpaca will restrict. Current count is historical and will decay.
- The AAVEUSD 24.5%-of-equity concentration is a separate risk-management issue. Once persona attribution is restored, whichever persona owns that bet should have a 10% position-size cap enforced in `submit()` pre-check.

---

## Signatures / audit trail

- Alpaca fills pulled: `/tmp/alpaca_fills.json` (500 rows, 2026-04-21T13:33 → 2026-04-22T01:27)
- Alpaca orders pulled: `/tmp/alpaca_orders_full.json` (2,059 rows)
- Alpaca account snapshot: `/tmp/alpaca_account.json` + `/tmp/alpaca_positions.json`
- ITF endpoints captured: `/tmp/itf_bankrolls.json`, `/tmp/itf_leaderboard.json`, `/tmp/itf_trades.json`, `/tmp/itf_status.json`
- HF Space executor.py hash: deployed 36,105 bytes vs local 36,268 bytes (Δ = 163 bytes of undeployed reconcile plumbing)

No TF code was modified. No Space was restarted. Nomos42 account not touched. THE BOSS should dispatch DR FRANKENSTEIN for patches 1-3 in order; the deploy recipe requires `HfApi.upload_file` + factory_reboot on `LBJLincoln26/intraday-trading-floor`.
