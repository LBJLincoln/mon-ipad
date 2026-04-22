---
name: ITF broker-fill reconciliation wired (compound gap closer)
description: 2026-04-22 — executor.reconcile_broker_fills() + /api/reconcile endpoint credits realized PnL from Alpaca fills back to per-agent sub-bankrolls.
type: project
---

**Fact:** `scripts/arena/hf-intraday-trading-floor/executor.py` now owns `reconcile_broker_fills(lookback_min=15)` which polls Alpaca `/v2/account/activities?activity_types=FILL&direction=desc&after=<iso>` (stdlib `urllib.request` only, no new deps), matches fills to local positions via `broker_order_id` OR a new `client_order_id` field (`<tid>:<TICKER>:<uuid8>`) now tagged on every `submit()`, and on closing fills (long+sell or short+buy) credits `stake_portion + realized_pnl` to the agent via `credit_bankroll()`. Cursor lives at `data/intraday/fill_reconciliation_cursor.json` (bounded to 2k seen_ids). Called at the top of `tick_once()` in `app.py` BEFORE `refresh_broker_statuses()` + `close_expired()`, so the LLM sees post-fill bankrolls in the prompt. `/api/reconcile?lookback_min=60` exposes on-demand reconciliation for cron/dashboards.

**Why:** Per `project_itf_compound_fix_apr22.md` open follow-up — 232 Alpaca fills landed, but `/api/bankrolls` still showed every persona at the cold-start $5898.59 seed because no code path credited realized PnL back. The submit path reserved stake; nothing un-reserved at close-fill. This closes the compounding loop.

**How to apply:** Every new order submitted carries `client_order_id` in the payload + on the local `positions.json` row + `broker_order_id` from Alpaca's response. Close-side fills will credit their matched agent. Already-closed-locally positions (via MIN_HOLD_SEC/close_expired) are not double-credited — the ledger still records the broker fill with `already_closed_locally=true` for audit. Unmatched fills (Alpaca-generated bracket children or pre-deploy orders without tagging) are ledgered as `event=unmatched_fill` — audit-only, no bankroll move.

**Deployed:** HF Space `LBJLincoln26/intraday-trading-floor` soft-restart via `HF_TOKEN_NBA`, new SHA `69c6d72311b84eb44a779b19f82314e7e762f36e`, stage RUNNING. First `/api/reconcile?lookback_min=120` poll returned `fills_processed=28, closes_applied=0, unmatched_fills=28` — expected: pre-deploy orders have no `broker_order_id` in the freshly-reset positions.json. From next tick onward new orders will carry tagging. Commit `56f2813d4` via `safe_commit.sh DR-FRANKENSTEIN`.

**Env knobs:** `ITF_RECON_LOOKBACK_MIN` (default 15) controls per-tick lookback.
