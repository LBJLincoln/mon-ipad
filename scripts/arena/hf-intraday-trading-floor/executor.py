"""ITF executor — DRY_RUN writes to jsonl, live uses Alpaca paper bracket orders.

Auto-detect: ALPACA_PAPER_KEY + ALPACA_PAPER_SECRET in env => live mode.
Otherwise: dry-run (simulated fill at last quote).

Position management:
  - max 3 open positions per agent
  - max hold = persona.max_hold_min
  - EOD flatten at 19:50 UTC (15:50 ET — 10 min before market close)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[3]
ORDERS_JSONL = REPO / "data" / "intraday" / "dry-run-orders.jsonl"
POSITIONS_PATH = REPO / "data" / "intraday" / "positions.json"
BANKROLLS_PATH = REPO / "data" / "intraday" / "agent_bankrolls.json"
LEDGER_JSONL = REPO / "data" / "intraday" / "agent_ledger.jsonl"
RECON_CURSOR_PATH = REPO / "data" / "intraday" / "fill_reconciliation_cursor.json"
POSITIONS_PATH.parent.mkdir(parents=True, exist_ok=True)

MAX_OPEN_PER_AGENT = int(os.environ.get("ITF_MAX_OPEN_PER_AGENT", "30"))  # 2026-04-25: 5→30 to push 500/day. Was bottleneck — 17 agents × 5 = 85 fleet ceiling, currently 65 → most decisions rejected. New ceiling 17×30 = 510 fleet positions (matches 500/day round-trip target). Env-overridable.
EOD_FLATTEN_UTC_HOUR = 19
EOD_FLATTEN_UTC_MIN = 50

# 2026-04-22 — HF Space /app is wiped on every factory_reboot, so the four
# attribution files above evaporate. persist_ledgers_to_hub() uploads them
# back to the repo at end-of-tick; restore_ledgers.py re-hydrates them on
# boot. _LEDGER_DIRTY guards against no-op commits when a tick didn't mutate
# anything. The ledger jsonl is append-only: we flip dirty on every append.
_LEDGER_DIRTY: bool = False
# Max bytes to keep uploading for the append-only ledger before we stop
# shipping it every tick (still shipped on the tick that crosses the limit).
_LEDGER_MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# 2026-04-24 MARKET-HOURS GATE — 189 broker_errors observed pre-market with
# message "options market orders are only allowed during market hours" plus
# same-day-expiry asset-not-found. Fix: poll /v2/clock once per 60s and
# reject both equity AND options market orders when closed. Re-submission
# happens next tick after market opens.
_CLOCK_CACHE: tuple[float, bool] | None = None
_CLOCK_TTL_SEC = 60.0


def _market_is_open() -> bool:
    """True iff Alpaca reports the equity market is open. Cached 60s.
    Fail-closed: any error -> return False (safer than blasting broker_errors).
    When live_mode() is False (dry run), assume open -- dry run shouldn't
    depend on external availability."""
    if not live_mode():
        return True
    global _CLOCK_CACHE
    now = time.time()
    if _CLOCK_CACHE is not None and (now - _CLOCK_CACHE[0] < _CLOCK_TTL_SEC):
        return _CLOCK_CACHE[1]
    try:
        import requests
        key = os.environ.get("ALPACA_PAPER_KEY", "")
        secret = os.environ.get("ALPACA_PAPER_SECRET", "")
        r = requests.get(
            "https://paper-api.alpaca.markets/v2/clock",
            headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
            timeout=5,
        )
        if r.ok:
            is_open = bool(r.json().get("is_open"))
            _CLOCK_CACHE = (now, is_open)
            return is_open
    except Exception:
        pass
    _CLOCK_CACHE = (now, False)
    return False


# ───── 2026-04-21 v2.5 PER-AGENT SUB-BANKROLL ─────
# Each of 14 personas gets an equal slice of current Alpaca equity at cold-start.
# Every submit() reserves stake_usd from agent's bankroll; close_expired /
# close_position credits stake + realized_pnl back. Enables a SCIENTIFIC
# leaderboard (which persona is actually best) instead of a single blended pool.

def _load_bankrolls() -> Dict[str, float]:
    if not BANKROLLS_PATH.exists():
        return {}
    try:
        return json.loads(BANKROLLS_PATH.read_text())
    except Exception:
        return {}


def _save_bankrolls(b: Dict[str, float]) -> None:
    BANKROLLS_PATH.write_text(json.dumps(b, indent=2, sort_keys=True))
    global _LEDGER_DIRTY
    _LEDGER_DIRTY = True


def _fetch_alpaca_equity() -> float:
    """Pull live Alpaca paper equity. Fallback $100k if not live or API error."""
    if not live_mode():
        return 100_000.0
    try:
        import requests
        r = requests.get(
            "https://paper-api.alpaca.markets/v2/account",
            headers={
                "APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_KEY", ""),
                "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET", ""),
            },
            timeout=5,
        )
        if r.ok:
            return float(r.json().get("equity") or 100_000.0)
    except Exception:
        pass
    return 100_000.0


def seed_bankrolls(tids: List[str], force: bool = False) -> Dict[str, float]:
    """Seed each tid at equal share of current Alpaca equity. Idempotent unless
    `force=True` (used by /api/reset)."""
    existing = _load_bankrolls()
    if existing and not force:
        return existing
    total = _fetch_alpaca_equity()
    share = round(total / max(1, len(tids)), 2)
    b = {tid: share for tid in tids}
    b["_meta"] = {
        "seeded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed_equity_usd": round(total, 2),
        "seed_share_usd": share,
        "n_agents": len(tids),
    }
    _save_bankrolls(b)
    return b


def get_bankroll(tid: str) -> float:
    b = _load_bankrolls()
    return float(b.get(tid, 0.0) or 0.0)


def _append_ledger(event: Dict[str, Any]) -> None:
    """Append a per-agent bankroll event to agent_ledger.jsonl for scientific audit."""
    LEDGER_JSONL.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = event.get("ts") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with LEDGER_JSONL.open("a") as fh:
        fh.write(json.dumps(event, default=str) + "\n")
    global _LEDGER_DIRTY
    _LEDGER_DIRTY = True


def _classify_reject(err: str) -> str:
    """Map raw Alpaca error body to a short reason_code so the ledger histograms cleanly."""
    e = err or ""
    if "available\":\"0\"" in e or "balance\":\"-" in e:
        return "insufficient_bp"
    if "existing_order" in e or "40310000" in e:
        return "duplicate_order"
    if "42210000" in e or "qty must be" in e or "qty must" in e:
        return "qty_invalid"
    if "base_price" in e:
        return "limit_too_far"
    if "wash" in e.lower():
        return "wash_trade"
    if "market_closed" in e or "trading_blocked" in e:
        return "market_closed"
    if "422" in e:
        return "unprocessable_other"
    if "403" in e:
        return "forbidden_other"
    if "429" in e:
        return "rate_limited"
    return "other"


def reserve_bankroll(tid: str, amount: float, meta: Optional[Dict[str, Any]] = None) -> float:
    """Deduct amount from tid's bankroll. Returns new balance (can go negative — caller checks)."""
    b = _load_bankrolls()
    before = float(b.get(tid, 0.0) or 0.0)
    b[tid] = round(before - amount, 2)
    _save_bankrolls(b)
    _append_ledger({"tid": tid, "event": "reserve", "delta": -round(amount, 2),
                    "balance_before": round(before, 2), "balance_after": b[tid],
                    **(meta or {})})
    return b[tid]


def credit_bankroll(tid: str, amount: float, meta: Optional[Dict[str, Any]] = None) -> float:
    b = _load_bankrolls()
    before = float(b.get(tid, 0.0) or 0.0)
    b[tid] = round(before + amount, 2)
    _save_bankrolls(b)
    _append_ledger({"tid": tid, "event": "credit", "delta": round(amount, 2),
                    "balance_before": round(before, 2), "balance_after": b[tid],
                    **(meta or {})})
    return b[tid]


def all_bankrolls() -> Dict[str, float]:
    """Return copy without _meta for leaderboard rendering."""
    b = _load_bankrolls()
    return {k: v for k, v in b.items() if not k.startswith("_")}


def live_mode() -> bool:
    """Live only when ITF_MODE=live AND Alpaca keys present.
    Default is dry_run — safer for an unvalidated key-pair. Explicitly opt in
    via env `ITF_MODE=live` once you've confirmed the key at /v2/account.
    """
    if os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("ITF_MODE", "").lower() != "live":
        return False
    return bool(os.environ.get("ALPACA_PAPER_KEY") and os.environ.get("ALPACA_PAPER_SECRET"))


def _load_positions() -> Dict[str, List[Dict[str, Any]]]:
    if not POSITIONS_PATH.exists():
        return {}
    try:
        return json.loads(POSITIONS_PATH.read_text())
    except Exception:
        return {}


def _save_positions(p: Dict[str, List[Dict[str, Any]]]) -> None:
    POSITIONS_PATH.write_text(json.dumps(p, indent=2, default=str))
    global _LEDGER_DIRTY
    _LEDGER_DIRTY = True


def _append_order_log(entry: Dict[str, Any]) -> None:
    ORDERS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with ORDERS_JSONL.open("a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def refresh_broker_statuses() -> Dict[str, int]:
    """Re-poll Alpaca for every position with a broker_order_id whose cached
    broker_status is non-terminal. Updates positions.json in place.

    Terminal statuses (skipped to save API calls): filled, canceled, expired,
    rejected, replaced, closed_by_agent, sim_*, closed.

    Returns a counter dict of what changed, e.g. {"polled": 23, "updated": 18,
    "filled": 11, "canceled": 2}. Called once at the top of tick_once() so the
    /api/status view never shows stale pending_new.
    """
    stats = {"polled": 0, "updated": 0, "filled": 0, "canceled": 0, "other": 0,
             "errors": 0, "budget_exceeded": 0}
    if not live_mode():
        return stats
    key = os.environ.get("ALPACA_PAPER_KEY")
    secret = os.environ.get("ALPACA_PAPER_SECRET")
    if not (key and secret):
        return stats

    TERMINAL = {
        "filled", "canceled", "cancelled", "expired", "rejected", "replaced",
        "closed_by_agent", "closed", "done_for_day", "stopped", "suspended",
        "not_found",
    }
    import requests
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    # 2026-04-22 — time-budget guard. Without this, a flaky Alpaca paper-api
    # with N non-terminal orders × 6s per-call could block tick_once() for
    # ~N*6s (observed: ~16 min stall at tick 1 after 232 daytrades piled up).
    budget_sec = float(os.environ.get("ITF_REFRESH_BROKER_BUDGET_SEC", "20"))
    deadline = time.monotonic() + budget_sec

    positions = _load_positions()
    changed = False
    for agent_tid, lst in positions.items():
        for p in lst:
            if time.monotonic() >= deadline:
                stats["budget_exceeded"] += 1
                if changed:
                    _save_positions(positions)
                return stats
            oid = p.get("broker_order_id")
            if not oid:
                continue
            cur = (p.get("broker_status") or "").lower()
            if cur in TERMINAL:
                continue
            stats["polled"] += 1
            try:
                r = requests.get(
                    f"https://paper-api.alpaca.markets/v2/orders/{oid}",
                    headers=headers, timeout=6,
                )
                if r.status_code == 404:
                    p["broker_status"] = "not_found"
                    stats["updated"] += 1
                    stats["other"] += 1
                    changed = True
                    continue
                if not r.ok:
                    stats["errors"] += 1
                    continue
                body = r.json()
                new = (body.get("status") or "").lower()
                if new and new != cur:
                    p["broker_status"] = new
                    if body.get("filled_avg_price"):
                        p["filled_avg_price"] = float(body["filled_avg_price"])
                    if body.get("filled_at"):
                        p["filled_at"] = body["filled_at"]
                    if body.get("filled_qty"):
                        p["filled_qty"] = float(body["filled_qty"])
                    stats["updated"] += 1
                    if new == "filled":
                        stats["filled"] += 1
                    elif new in {"canceled", "cancelled"}:
                        stats["canceled"] += 1
                    else:
                        stats["other"] += 1
                    changed = True
            except Exception:
                stats["errors"] += 1
    if changed:
        _save_positions(positions)
    return stats


def close_stale_losers(max_age_sec: int = 14400, min_loss_pct: float = 0.02) -> Dict[str, Any]:
    """Close equity positions older than max_age_sec with unrealized PnL <= -min_loss_pct.

    2026-04-22 ROUND-2 BP UNLOCK — Alpaca paper `insufficient balance` + free_bp=$0
    while total cash sits at $49K = open positions consumed all free BP. Nothing
    in the fleet closes stale losers proactively (MIN_HOLD_SEC=900 only prevents
    churn; EOD-flatten doesn't fire intra-day). This helper sweeps equity
    positions that are both >max_age_sec old AND underwater >=min_loss_pct, so
    the 70% deploy target can actually reserve BP.

    Safety:
      * Respects MIN_HOLD_SEC implicitly (default 4h >> 15min)
      * Equities only — crypto (BTC/USD etc) use non-USD margin, no BP pressure
      * Time-budgeted at ITF_CLOSE_STALE_BUDGET_SEC (default 10s) so a flaky
        Alpaca API can't stall tick_once()
      * Credits reserved stake back to agent sub-bankroll via credit_bankroll()
        (conservative — realized PnL reconciles via reconcile_broker_fills next tick)

    Returns: {closed, pnl_freed_usd, errors, skipped_too_young, skipped_winning,
              skipped_crypto, budget_exceeded}.
    """
    budget_sec = float(os.environ.get("ITF_CLOSE_STALE_BUDGET_SEC", "10"))
    deadline = time.monotonic() + budget_sec
    stats = {
        "closed": 0, "pnl_freed_usd": 0.0, "errors": 0,
        "skipped_too_young": 0, "skipped_winning": 0, "skipped_crypto": 0,
        "budget_exceeded": 0,
    }
    if not live_mode():
        return stats
    key = os.environ.get("ALPACA_PAPER_KEY")
    secret = os.environ.get("ALPACA_PAPER_SECRET")
    if not (key and secret):
        return stats

    import requests
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    now_utc = datetime.now(timezone.utc)
    positions = _load_positions()
    dirty = False

    try:
        for agent_tid, lst in list(positions.items()):
            for p in list(lst):
                if time.monotonic() >= deadline:
                    stats["budget_exceeded"] += 1
                    if dirty:
                        _save_positions(positions)
                    return stats
                try:
                    if p.get("status") != "open":
                        continue
                    ticker = (p.get("ticker") or "").strip()
                    if not ticker:
                        continue
                    # Skip crypto — settles in non-USD margin, no BP pressure.
                    if _asset_class(ticker) == "crypto":
                        stats["skipped_crypto"] += 1
                        continue
                    # Age check. Accept either `opened_at` or `ts`; both ISO-Z.
                    opened_raw = p.get("opened_at") or p.get("ts") or ""
                    try:
                        opened_dt = datetime.fromisoformat(
                            str(opened_raw).replace("Z", "+00:00")
                        )
                    except Exception:
                        # unreadable timestamp → don't close (treat as young)
                        stats["skipped_too_young"] += 1
                        continue
                    age_sec = (now_utc - opened_dt).total_seconds()
                    if age_sec < max_age_sec:
                        stats["skipped_too_young"] += 1
                        continue
                    # Fetch live position to get unrealized_plpc. If position not
                    # found at broker, skip — fill reconciler will tidy it up.
                    try:
                        r = requests.get(
                            f"https://paper-api.alpaca.markets/v2/positions/{ticker}",
                            headers=headers, timeout=6,
                        )
                    except Exception:
                        stats["errors"] += 1
                        continue
                    if r.status_code == 404:
                        # Broker doesn't have it — nothing to close, our ledger
                        # will self-heal via the reconciler.
                        continue
                    if not r.ok:
                        stats["errors"] += 1
                        continue
                    try:
                        live = r.json()
                        upl = float(live.get("unrealized_plpc") or 0)
                        mv = float(live.get("market_value") or 0)
                    except Exception:
                        stats["errors"] += 1
                        continue
                    if upl > -min_loss_pct:
                        stats["skipped_winning"] += 1
                        continue
                    # Close via positions endpoint (net-flat, correct for bracket).
                    try:
                        rd = requests.delete(
                            f"https://paper-api.alpaca.markets/v2/positions/{ticker}",
                            headers=headers, timeout=10,
                        )
                        if not rd.ok:
                            stats["errors"] += 1
                            continue
                    except Exception:
                        stats["errors"] += 1
                        continue
                    # Mark local position closed + credit reserved stake back.
                    p["status"] = "closed_stale_loser"
                    p["closed_at"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                    p["close_reason"] = f"stale_loser age={int(age_sec)}s upl={upl:.4f}"
                    dirty = True
                    stake_portion = float(p.get("stake_usd") or 0)
                    if stake_portion > 0:
                        try:
                            credit_bankroll(agent_tid, stake_portion, meta={
                                "ticker": ticker,
                                "event_type": "stale_loser_close",
                                "age_sec": int(age_sec),
                                "unrealized_plpc": round(upl, 4),
                                "market_value_usd": round(mv, 2),
                            })
                        except Exception:
                            pass
                    # Also log to order log for audit parity with close_position().
                    try:
                        _append_order_log({
                            "ts": p["closed_at"],
                            "agent_tid": agent_tid,
                            "ticker": ticker,
                            "action": "close_stale_loser",
                            "age_sec": int(age_sec),
                            "unrealized_plpc": round(upl, 4),
                            "market_value_usd": round(mv, 2),
                            "mode": "live",
                        })
                    except Exception:
                        pass
                    stats["closed"] += 1
                    stats["pnl_freed_usd"] += mv
                except Exception:
                    stats["errors"] += 1
    finally:
        if dirty:
            _save_positions(positions)
    return stats


# ───── 2026-04-22 ROUND-3 ORDER-PILEUP GUARDS ─────
# Incident: 319 open bracket orders stacked on Alpaca paper (SPY×61, QQQ×37,
# NVDA×35…) consumed $63K of initial_margin. daytrading_buying_power fell to
# $246 on $101K equity. Agents kept emitting bracket orders every tick; none
# filled (limit prices drifted, or same-symbol contention). Manual
# `DELETE /v2/orders` freed BP back to $157K. Without these three guards the
# pile rebuilds within hours.
#
# Guard 1: _refresh_pending_count() — 30s cached map of open-orders-by-symbol
# Guard 2: cancel_stale_pending() — cancels orders older than max_age_min
# Guard 3: _bp_pre_check() — rejects new placements when free BP < $500
#
# All three fail-open (errors logged, never raise).

_PENDING_BY_SYMBOL: Dict[str, int] = {}
_PENDING_BY_SYMBOL_TS: float = 0.0
_PENDING_CACHE_TTL_SEC: float = 30.0


def _refresh_pending_count(force: bool = False) -> None:
    """Refresh the open-order-by-symbol cache. 30s TTL to keep HTTP traffic
    bounded while still catching pileup within a single tick."""
    global _PENDING_BY_SYMBOL, _PENDING_BY_SYMBOL_TS
    if not live_mode():
        return
    if not force and (time.time() - _PENDING_BY_SYMBOL_TS) < _PENDING_CACHE_TTL_SEC:
        return
    key = os.environ.get("ALPACA_PAPER_KEY")
    secret = os.environ.get("ALPACA_PAPER_SECRET")
    if not (key and secret):
        return
    try:
        import requests
        r = requests.get(
            "https://paper-api.alpaca.markets/v2/orders",
            headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
            params={"status": "open", "limit": 500},
            timeout=6,
        )
        if not r.ok:
            return
        orders = r.json() or []
        counts: Dict[str, int] = {}
        for o in orders:
            sym = (o.get("symbol") or "").strip()
            if not sym:
                continue
            counts[sym] = counts.get(sym, 0) + 1
        _PENDING_BY_SYMBOL = counts
        _PENDING_BY_SYMBOL_TS = time.time()
    except Exception:
        # Fail-open: stale cache is fine, will refresh next tick.
        pass


def _pending_count_for(symbol: str) -> int:
    """Return cached pending-order count for a symbol. Refreshes if stale."""
    _refresh_pending_count()
    return int(_PENDING_BY_SYMBOL.get(symbol, 0))


def _get_daytrading_buying_power() -> float:
    """Fetch Alpaca daytrading_buying_power. Returns 0.0 on error (fail-closed
    for BP-pre-check: if we can't read BP, treat as starved so we don't pile up)."""
    if not live_mode():
        return 1_000_000.0  # dry-run: unlimited
    key = os.environ.get("ALPACA_PAPER_KEY")
    secret = os.environ.get("ALPACA_PAPER_SECRET")
    if not (key and secret):
        return 0.0
    try:
        import requests
        r = requests.get(
            "https://paper-api.alpaca.markets/v2/account",
            headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
            timeout=5,
        )
        if not r.ok:
            return 0.0
        j = r.json()
        # Prefer daytrading_buying_power; fall back to buying_power.
        return float(j.get("daytrading_buying_power") or j.get("buying_power") or 0)
    except Exception:
        return 0.0


def _bp_pre_check(min_bp: float = 500.0) -> Dict[str, Any]:
    """Return {ok: bool, bp: float, reason: str}. If BP is below `min_bp` the
    caller should skip placement this tick. If BP is below 5% of equity, we
    also trigger a fast cancel_stale_pending(max_age_min=10) to unblock."""
    out = {"ok": True, "bp": 0.0, "reason": ""}
    if not live_mode():
        out["bp"] = 1_000_000.0
        return out
    bp = _get_daytrading_buying_power()
    out["bp"] = bp
    equity = _fetch_alpaca_equity()
    if bp < min_bp:
        out["ok"] = False
        out["reason"] = f"bp={bp:.2f} < min={min_bp:.2f}"
    if equity > 0 and bp < 0.05 * equity:
        # BP less than 5% of equity — the pileup is eating margin. Force an
        # inline 10-min stale cancel to unblock, best-effort.
        try:
            cs = cancel_stale_pending(max_age_min=10)
            out["inline_stale_cancel"] = cs
        except Exception as e:
            out["inline_stale_cancel_err"] = str(e)[:200]
    return out


def cancel_stale_pending(max_age_min: int = 30) -> Dict[str, Any]:
    """Cancel Alpaca open orders older than `max_age_min` minutes.

    2026-04-22 ROUND-3 — Pileup RCA: Alpaca paper accumulated 319 open brackets
    on ~12 symbols (SPY×61, QQQ×37, etc). None filled — limit prices drifted or
    same-symbol contention blocked sequencing. initial_margin ate BP down to
    $246 on $101K equity. This helper sweeps every tick/10 so the pile never
    rebuilds.

    Safety:
      * Live-mode only (no dry-run no-op noise)
      * Time-budgeted at ITF_CANCEL_STALE_BUDGET_SEC (default 10s)
      * Only cancels orders where `submitted_at > max_age_min min ago`
      * Uses DELETE /v2/orders/{id}; logs non-OK per-order but continues
      * DOES cancel during pre-open (caller controls age threshold; legit GTC
        overnight orders aren't stale at 30min so default is safe)

    Returns: {cancelled, errors, skipped_young, budget_exceeded, seen}.
    """
    stats = {"cancelled": 0, "errors": 0, "skipped_young": 0,
             "budget_exceeded": 0, "seen": 0}
    if not live_mode():
        return stats
    key = os.environ.get("ALPACA_PAPER_KEY")
    secret = os.environ.get("ALPACA_PAPER_SECRET")
    if not (key and secret):
        return stats
    budget_sec = float(os.environ.get("ITF_CANCEL_STALE_BUDGET_SEC", "10"))
    deadline = time.monotonic() + budget_sec
    import requests
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    now_utc = datetime.now(timezone.utc)

    try:
        r = requests.get(
            "https://paper-api.alpaca.markets/v2/orders",
            headers=headers, params={"status": "open", "limit": 500},
            timeout=8,
        )
        if not r.ok:
            stats["errors"] += 1
            return stats
        orders = r.json() or []
    except Exception:
        stats["errors"] += 1
        return stats

    stats["seen"] = len(orders)
    for o in orders:
        if time.monotonic() >= deadline:
            stats["budget_exceeded"] += 1
            break
        try:
            oid = o.get("id")
            subm = o.get("submitted_at") or o.get("created_at") or ""
            if not (oid and subm):
                continue
            try:
                subm_dt = datetime.fromisoformat(str(subm).replace("Z", "+00:00"))
            except Exception:
                continue
            age_min = (now_utc - subm_dt).total_seconds() / 60.0
            if age_min < max_age_min:
                stats["skipped_young"] += 1
                continue
            try:
                rd = requests.delete(
                    f"https://paper-api.alpaca.markets/v2/orders/{oid}",
                    headers=headers, timeout=6,
                )
                if rd.status_code in (200, 204, 207):
                    stats["cancelled"] += 1
                else:
                    stats["errors"] += 1
            except Exception:
                stats["errors"] += 1
        except Exception:
            stats["errors"] += 1
    # Force-refresh the per-symbol cache so the next placement sees post-cancel state.
    try:
        _refresh_pending_count(force=True)
    except Exception:
        pass
    return stats


def _asset_class(ticker: str) -> str:
    if "/" in ticker:
        return "crypto"
    return "equity"


def _make_client_order_id(agent_tid: str, ticker: str) -> str:
    """2026-04-22 — every outbound order gets a deterministic client_order_id so
    the reconciler can trace a broker fill back to the right agent even if the
    local positions.json is wiped. Format: "<tid>:<TICKER>:<uuid-hex-8>".
    Alpaca caps this at 128 chars; normalize ticker (no "/" etc) to be safe."""
    safe_ticker = (ticker or "").replace("/", "-").replace(" ", "")[:16].upper()
    safe_tid = (agent_tid or "anon").replace(":", "-")[:32]
    return f"{safe_tid}:{safe_ticker}:{uuid.uuid4().hex[:8]}"


def _alpaca_place_bracket(ticker: str, qty: float, stake: float, last: float,
                          side: str, stop_price: float, tp_price: float,
                          client_order_id: Optional[str] = None) -> Dict[str, Any]:
    """Place an Alpaca paper order.

    Routing (canonical alpaca-py examples pattern):
      * crypto (BTC/USD etc)    → market GTC, fractional qty ok, NO bracket
      * equity qty >= 1 integer → bracket with integer qty + stop_loss + take_profit
      * equity qty < 1 or frac  → notional-based market day, NO bracket
        (Alpaca 422s on bracket+fractional; stop/TP tracked client-side in close_expired)
    """
    import requests
    key = os.environ["ALPACA_PAPER_KEY"]
    secret = os.environ["ALPACA_PAPER_SECRET"]

    asset = _asset_class(ticker)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    if asset == "crypto":
        payload = {
            "symbol": ticker,
            "qty": qty,
            "side": side,
            "type": "market",
            "time_in_force": "gtc",
        }
    else:
        int_qty = int(qty)  # floor — Alpaca rejects bracket on fractional
        if int_qty >= 1:
            # Defensive: bracket MUST have integer qty >= 1. If this assert ever fires,
            # it means something bypassed the fractional routing — crash-log the call
            # site so we can pin the regression fast.
            assert int_qty >= 1 and float(int_qty).is_integer(), \
                f"bracket qty must be integer>=1, got {qty!r} (ticker={ticker}, stake={stake})"
            payload = {
                "symbol": ticker,
                "qty": int_qty,
                "side": side,
                "type": "market",
                "time_in_force": "day",
                "order_class": "bracket",
                "extended_hours": False,
                "stop_loss": {"stop_price": round(stop_price, 2)},
                "take_profit": {"limit_price": round(tp_price, 2)},
            }
        else:
            # Stake too small for 1 whole share → notional fractional, no bracket.
            # close_expired() already tracks stop/TP client-side via age/EOD flatten.
            payload = {
                "symbol": ticker,
                "notional": round(stake, 2),
                "side": side,
                "type": "market",
                "time_in_force": "day",
            }
    if client_order_id:
        payload["client_order_id"] = client_order_id
    r = requests.post(
        "https://paper-api.alpaca.markets/v2/orders",
        headers=headers,
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def submit(agent_tid: str, order: Dict[str, Any], last_quote: float) -> Dict[str, Any]:
    """Submit an order. Shape of `order`:
       {ticker, side: long|short, stake_usd, stop_pct, take_profit_pct, thesis}
    Returns the recorded order entry (with fill or simulated fill).
    """
    positions = _load_positions()
    open_for_agent = [p for p in positions.get(agent_tid, []) if p.get("status") == "open"]
    # 2026-04-21 wash-trade pre-check: if same agent has an OPEN opposite-side
    # position on same ticker, skip. Alpaca rejects these as wash-trades anyway;
    # pre-check gives a clean ledger event instead of a broker_error.
    _inbound_side = order.get("side")
    _inbound_ticker = order.get("ticker")
    for _p in open_for_agent:
        if _p.get("ticker") == _inbound_ticker and _p.get("side") and _inbound_side and _p.get("side") != _inbound_side:
            wash = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "agent_tid": agent_tid, "status": "wash_skip",
                "reason": f"opposite-side {_p.get('side')} open on {_inbound_ticker}",
                "order": order,
            }
            _append_order_log(wash)
            return wash
    if len(open_for_agent) >= MAX_OPEN_PER_AGENT:
        reject = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_tid": agent_tid, "status": "rejected",
            "reason": f"max {MAX_OPEN_PER_AGENT} open positions already",
            "order": order,
        }
        _append_order_log(reject)
        return reject

    # 2026-04-22 ROUND-3 GUARD 1 — per-symbol dedup. Before we even build the
    # order payload, check how many OPEN orders already exist at Alpaca for
    # this symbol. If >= ITF_MAX_PENDING_PER_SYMBOL (default 2), skip: another
    # bracket will just deepen the 319-order pileup.
    max_pending = int(os.environ.get("ITF_MAX_PENDING_PER_SYMBOL", "2"))
    if live_mode():
        sym_for_check = str(order.get("ticker") or "")
        try:
            pend = _pending_count_for(sym_for_check)
        except Exception:
            pend = 0
        if pend >= max_pending:
            skip = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "agent_tid": agent_tid, "status": "broker_skip_dedupe",
                "reason": f"already {pend} open orders for {sym_for_check} "
                          f">= max_pending_per_symbol={max_pending}",
                "order": order,
            }
            _append_order_log(skip)
            return skip
        # 2026-04-22 ROUND-3 GUARD 3 — BP pre-check. If daytrading_buying_power
        # is starved (<$500), refuse and let cancel_stale_pending reclaim BP
        # before we try again next tick.
        try:
            bp_ok = _bp_pre_check(min_bp=float(os.environ.get("ITF_MIN_BP_USD", "500")))
        except Exception:
            bp_ok = {"ok": True, "bp": -1.0, "reason": ""}
        if not bp_ok.get("ok"):
            skip = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "agent_tid": agent_tid, "status": "broker_skip_bp_starved",
                "reason": bp_ok.get("reason", "bp low"),
                "bp": round(float(bp_ok.get("bp") or 0), 2),
                "inline_stale_cancel": bp_ok.get("inline_stale_cancel"),
                "order": order,
            }
            _append_order_log(skip)
            return skip

    ticker = order["ticker"]
    side = order["side"]  # "long" | "short"
    stake = float(order.get("stake_usd", 1000))
    stop_pct = float(order.get("stop_pct", 0.005))
    tp_pct = float(order.get("take_profit_pct", 0.012))
    last = float(last_quote or 0) or 1.0
    qty = round(stake / last, 2)

    if side == "long":
        stop_price = last * (1 - stop_pct)
        tp_price = last * (1 + tp_pct)
        alp_side = "buy"
    else:
        stop_price = last * (1 + stop_pct)
        tp_price = last * (1 - tp_pct)
        alp_side = "sell"

    client_order_id = _make_client_order_id(agent_tid, ticker)
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_tid": agent_tid,
        "ticker": ticker,
        "side": side,
        "qty": qty,
        "entry_price": round(last, 4),
        "stop_price": round(stop_price, 4),
        "take_profit_price": round(tp_price, 4),
        "stake_usd": round(stake, 2),
        "stop_pct": stop_pct,
        "take_profit_pct": tp_pct,
        "thesis": order.get("thesis", "")[:500],
        "status": "open",
        "mode": "live" if live_mode() else "dry_run",
        "client_order_id": client_order_id,
    }

    if live_mode():
        try:
            resp = _alpaca_place_bracket(ticker, qty, stake, last, alp_side,
                                         stop_price, tp_price,
                                         client_order_id=client_order_id)
            entry["broker_order_id"] = resp.get("id")
            entry["broker_status"] = resp.get("status")
            entry["broker_class"] = resp.get("order_class") or ("notional" if resp.get("notional") else "bracket")
            # 2026-04-22 ROUND-3 — optimistically bump the per-symbol pending
            # cache so a second agent in the same tick will see the dedup guard.
            try:
                _PENDING_BY_SYMBOL[ticker] = int(_PENDING_BY_SYMBOL.get(ticker, 0)) + 1
            except Exception:
                pass
        except Exception as e:
            entry["status"] = "broker_error"
            # Capture Alpaca body text when available (RequestException.response) so we can
            # diagnose broker_errors beyond the generic "422 Unprocessable Entity" prefix.
            body = ""
            try:
                body = " | body=" + getattr(e, "response", None).text[:400]  # type: ignore
            except Exception:
                pass
            entry["error"] = (str(e) + body)[:600]
            # 2026-04-25 — mirror reject into agent_ledger so per-agent visibility
            # exists without correlating against positions.json (5MB+ blob).
            _append_ledger({
                "tid": agent_tid, "event": "broker_reject",
                "ticker": ticker, "side": entry.get("side"),
                "stake": entry.get("stake_usd"),
                "instrument": "equity_or_crypto",
                "reason_code": _classify_reject(entry["error"]),
                "reason": entry["error"][:300],
            })
    else:
        # Dry run — simulate the fill and set sim_close_at for EOD flatten
        entry["sim_filled_at"] = last
        entry["sim_pnl_usd"] = 0.0  # filled flat, realized on close

    positions.setdefault(agent_tid, []).append(entry)
    _save_positions(positions)
    _append_order_log(entry)
    # v2.5 — reserve stake from agent's sub-bankroll (do NOT reserve if broker rejected).
    if entry.get("status") == "open":
        new_bal = reserve_bankroll(agent_tid, stake, meta={
            "ticker": ticker, "side": side, "stake": round(stake, 2),
            "instrument": "equity_or_crypto",
            "broker_order_id": entry.get("broker_order_id"),
        })
        entry["agent_bankroll_after_reserve"] = new_bal
    return entry


def _occ_symbol(underlying: str, expiry: datetime, option_type: str, strike: float) -> str:
    """OCC-standard option symbol: <UND><YYMMDD><C|P><strike*1000 zero-padded to 8>.
    Example: SPY251220C00480000 = SPY call, strike $480, expiring 2025-12-20.
    """
    exp = expiry.strftime("%y%m%d")
    cp = "C" if option_type.lower().startswith("c") else "P"
    strike_int = int(round(strike * 1000))
    return f"{underlying.upper()}{exp}{cp}{strike_int:08d}"


def _next_expiry(dte: int, now_utc: datetime) -> datetime:
    """Return the nearest US market expiry that is `dte` trading days ahead.
    SPY/QQQ/IWM have daily expiries (0/1/2 DTE) during the week; we approximate
    by skipping weekends only (holidays treated as weekdays for dry-run intent)."""
    d = now_utc
    added = 0
    while added < max(0, dte):
        d = d + timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def submit_option(agent_tid: str, order: Dict[str, Any], last_quote: float) -> Dict[str, Any]:
    """Submit an intraday option order. Shape:
       {underlying, option_type, strategy, dte, strike_offset_pct, wing_width_pct, stake_usd, max_loss_pct, thesis}

    Strategy handling:
      - "long":              1-leg long call/put
      - "vertical_debit":    2-leg debit spread (buy ATM, sell ATM+wing)
      - "vertical_credit":   2-leg credit spread (sell ATM, buy ATM+wing)
      - "iron_condor":       4-leg (call spread above, put spread below)
      - "straddle":          2-leg long call + long put at same strike

    Dry-run logs the structured intent with computed OCC symbols.
    Live mode routes to Alpaca /v2/options/orders (minimal wrapper; paper-only).
    """
    positions = _load_positions()
    open_for_agent = [p for p in positions.get(agent_tid, []) if p.get("status") == "open"]
    if len(open_for_agent) >= MAX_OPEN_PER_AGENT:
        reject = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_tid": agent_tid, "status": "rejected",
            "reason": f"max {MAX_OPEN_PER_AGENT} open positions already",
            "order": order,
        }
        _append_order_log(reject)
        return reject

    now = datetime.now(timezone.utc)
    underlying = order["underlying"]
    option_type = order.get("option_type", "call")
    strategy   = order.get("strategy", "long")
    dte = int(order.get("dte", 0) or 0)
    offset_pct = float(order.get("strike_offset_pct", 0.0) or 0.0)
    wing_pct   = float(order.get("wing_width_pct", 0.01) or 0.01)
    stake      = float(order.get("stake_usd", 500))
    last       = float(last_quote or 0) or 1.0
    expiry     = _next_expiry(dte, now)

    # Compute strikes (rounded to $1 — broker will snap to chain)
    atm = round(last * (1 + offset_pct))
    wing_up = round(last * (1 + offset_pct + wing_pct))
    wing_dn = round(last * (1 + offset_pct - wing_pct))

    legs: List[Dict[str, Any]] = []
    if strategy == "long":
        legs = [{"side": "buy", "symbol": _occ_symbol(underlying, expiry, option_type, atm), "qty": 1}]
    elif strategy == "vertical_debit":
        outer = wing_up if option_type == "call" else wing_dn
        legs = [
            {"side": "buy",  "symbol": _occ_symbol(underlying, expiry, option_type, atm),   "qty": 1},
            {"side": "sell", "symbol": _occ_symbol(underlying, expiry, option_type, outer), "qty": 1},
        ]
    elif strategy == "vertical_credit":
        outer = wing_up if option_type == "call" else wing_dn
        legs = [
            {"side": "sell", "symbol": _occ_symbol(underlying, expiry, option_type, atm),   "qty": 1},
            {"side": "buy",  "symbol": _occ_symbol(underlying, expiry, option_type, outer), "qty": 1},
        ]
    elif strategy == "iron_condor":
        legs = [
            # call spread above
            {"side": "sell", "symbol": _occ_symbol(underlying, expiry, "call", wing_up),                "qty": 1},
            {"side": "buy",  "symbol": _occ_symbol(underlying, expiry, "call", round(last*(1+offset_pct+2*wing_pct))), "qty": 1},
            # put spread below
            {"side": "sell", "symbol": _occ_symbol(underlying, expiry, "put",  wing_dn),                "qty": 1},
            {"side": "buy",  "symbol": _occ_symbol(underlying, expiry, "put",  round(last*(1+offset_pct-2*wing_pct))), "qty": 1},
        ]
    elif strategy == "straddle":
        legs = [
            {"side": "buy", "symbol": _occ_symbol(underlying, expiry, "call", atm), "qty": 1},
            {"side": "buy", "symbol": _occ_symbol(underlying, expiry, "put",  atm), "qty": 1},
        ]
    else:
        legs = [{"side": "buy", "symbol": _occ_symbol(underlying, expiry, option_type, atm), "qty": 1}]

    entry = {
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_tid": agent_tid,
        "instrument_type": "option",
        "underlying": underlying,
        "option_type": option_type,
        "strategy": strategy,
        "dte": dte,
        "expiry": expiry.strftime("%Y-%m-%d"),
        "atm_strike": atm,
        "legs": legs,
        "stake_usd": round(stake, 2),
        "max_loss_pct": float(order.get("max_loss_pct", 0.02)),
        "last_quote_underlying": round(last, 4),
        "thesis": order.get("thesis", "")[:500],
        "status": "open",
        "mode": "live" if live_mode() else "dry_run",
    }

    if live_mode() and os.environ.get("ITF_OPTIONS_LIVE", "").lower() in ("1","true","yes"):
        # Alpaca multi-leg options (order_class=mleg) — canonical alpaca-py pattern.
        # Single atomic POST replaces the old per-leg loop which broke spread pricing
        # AND left naked legs when one fill succeeded and another failed.
        try:
            import requests
            key = os.environ["ALPACA_PAPER_KEY"]
            secret = os.environ["ALPACA_PAPER_SECRET"]
            headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

            if len(legs) == 1:
                # Single-leg: simple market order on OCC symbol (no mleg).
                leg = legs[0]
                payload = {
                    "symbol": leg["symbol"],
                    "qty": leg["qty"],
                    "side": leg["side"],
                    "type": "market",
                    "time_in_force": "day",
                }
                r = requests.post("https://paper-api.alpaca.markets/v2/orders",
                                  headers=headers, json=payload, timeout=10)
                r.raise_for_status()
                entry["broker_order_ids"] = [r.json().get("id")]
            else:
                # Multi-leg: one mleg order, 2-4 legs. ratio_qty defines leg proportions;
                # position_intent declares open vs close so Alpaca can validate margin.
                mleg_legs = []
                for leg in legs:
                    mleg_legs.append({
                        "symbol": leg["symbol"],
                        "side": leg["side"],
                        "ratio_qty": str(leg["qty"]),
                        "position_intent": "buy_to_open" if leg["side"] == "buy" else "sell_to_open",
                    })
                payload = {
                    "order_class": "mleg",
                    "qty": "1",
                    "type": "market",
                    "time_in_force": "day",
                    "legs": mleg_legs,
                }
                r = requests.post("https://paper-api.alpaca.markets/v2/orders",
                                  headers=headers, json=payload, timeout=10)
                r.raise_for_status()
                resp = r.json()
                entry["broker_order_ids"] = [resp.get("id")]
                entry["broker_class"] = "mleg"
                entry["broker_legs_count"] = len(mleg_legs)
        except Exception as e:
            entry["status"] = "broker_error"
            # Capture Alpaca body text when available (RequestException.response) so we can
            # diagnose broker_errors beyond the generic "422 Unprocessable Entity" prefix.
            body = ""
            try:
                body = " | body=" + getattr(e, "response", None).text[:400]  # type: ignore
            except Exception:
                pass
            entry["error"] = (str(e) + body)[:600]
            # 2026-04-25 — mirror reject into agent_ledger (options path)
            _append_ledger({
                "tid": agent_tid, "event": "broker_reject",
                "ticker": underlying, "side": entry.get("side"),
                "stake": entry.get("stake_usd"),
                "instrument": "option",
                "reason_code": _classify_reject(entry["error"]),
                "reason": entry["error"][:300],
            })
    else:
        entry["sim_opened_at_underlying"] = last

    positions.setdefault(agent_tid, []).append(entry)
    _save_positions(positions)
    _append_order_log(entry)
    # v2.5 — reserve option stake from agent's sub-bankroll
    if entry.get("status") == "open":
        new_bal = reserve_bankroll(agent_tid, stake, meta={
            "underlying": underlying, "strategy": strategy, "stake": round(stake, 2),
            "instrument": "option",
        })
        entry["agent_bankroll_after_reserve"] = new_bal
    return entry


def _mark_to_market(p: Dict[str, Any], quote_fn) -> Dict[str, Any]:
    """Compute realized P&L on close. Mutates `p` with realized_pnl_usd + exit_price + return_pct.

    For equities: P&L = qty * (exit - entry) for long, qty * (entry - exit) for short.
    For options (dry-run): approximate intrinsic value delta via underlying quote — coarse
    but gives a direction/magnitude signal. Live options P&L pulled from broker fill feed.
    For broker_error / rejected entries: leave P&L at 0.0.
    """
    if p.get("status") in ("broker_error", "rejected"):
        p["realized_pnl_usd"] = 0.0
        return p

    if p.get("instrument_type") == "option":
        # Dry-run option P&L: Δ(underlying) × stake × direction sign. Not real Greeks,
        # but enough to produce non-zero leaderboard numbers and catch obviously
        # losing theses. Live mode will overwrite via broker fills.
        underlying_entry = float(p.get("last_quote_underlying") or 0) or 0.0
        exit_q = quote_fn(p.get("underlying", "")) or underlying_entry
        if underlying_entry > 0:
            delta_pct = (exit_q - underlying_entry) / underlying_entry
        else:
            delta_pct = 0.0
        direction = 1 if p.get("option_type", "call") == "call" else -1
        if p.get("strategy") in ("vertical_credit",):
            direction *= -1  # credit: we profit on small moves, lose on large in direction
        stake = float(p.get("stake_usd") or 0)
        pnl = stake * delta_pct * direction
        # Cap loss at stake (long premium) — no naked unlimited here by design.
        pnl = max(pnl, -stake)
        p["realized_pnl_usd"] = round(pnl, 2)
        p["exit_underlying"] = round(exit_q, 4)
        p["return_pct"] = round(delta_pct * direction, 5)
        return p

    entry_px = float(p.get("entry_price") or 0) or 0.0
    qty = float(p.get("qty") or 0) or 0.0
    ticker = p.get("ticker", "")
    exit_px = quote_fn(ticker) or entry_px
    if p.get("side") == "short":
        gross = qty * (entry_px - exit_px)
    else:
        gross = qty * (exit_px - entry_px)
    p["realized_pnl_usd"] = round(gross, 2)
    p["exit_price"] = round(exit_px, 4)
    if entry_px > 0:
        p["return_pct"] = round((exit_px - entry_px) / entry_px, 5)
    else:
        p["return_pct"] = 0.0
    return p


def close_expired(now_utc: datetime, quote_fn=None) -> List[Dict[str, Any]]:
    """Walk positions and close any that passed persona.max_hold or hit EOD flatten.

    `quote_fn(ticker) -> last_price` is injected from app.py so we can stay
    decoupled from the quote_bus import. If None, we fall back to entry_price
    (zero P&L) but still mark status=closed_expired.
    """
    closed: List[Dict[str, Any]] = []
    positions = _load_positions()
    qf = quote_fn or (lambda _t: None)
    for agent_tid, rows in positions.items():
        for p in rows:
            if p.get("status") != "open":
                continue
            try:
                opened = datetime.fromisoformat(p["ts"].replace("Z", "+00:00"))
            except Exception:
                continue
            age_min = (now_utc - opened).total_seconds() / 60.0
            eod = (now_utc.hour > EOD_FLATTEN_UTC_HOUR or
                   (now_utc.hour == EOD_FLATTEN_UTC_HOUR and now_utc.minute >= EOD_FLATTEN_UTC_MIN))
            # We don't know per-agent max_hold here without loading personas; use 240 as a ceiling.
            if age_min > 240 or eod:
                p["status"] = "closed_expired"
                p["closed_at"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                _mark_to_market(p, qf)
                # v2.5 — credit stake + realized_pnl back to agent's sub-bankroll
                _stake = float(p.get("stake_usd") or 0)
                _pnl = float(p.get("realized_pnl_usd") or 0)
                credit_bankroll(agent_tid, _stake + _pnl, meta={
                    "ticker": p.get("ticker") or p.get("underlying"),
                    "event_type": "eod_or_expired_close",
                    "stake_returned": round(_stake, 2),
                    "realized_pnl": round(_pnl, 2),
                })
                closed.append(p)
    _save_positions(positions)
    return closed


def pnl_snapshot(quote_fn=None) -> Dict[str, Any]:
    """Per-agent P&L aggregate. Realized = sum(realized_pnl_usd) on closed rows.
    Unrealized = mark-to-market on still-open rows. Total = realized + unrealized.

    Uses `quote_fn(ticker)` for the open-position mark. If quote missing, mark is 0.
    """
    positions = _load_positions()
    qf = quote_fn or (lambda _t: None)
    per_agent: Dict[str, Dict[str, float]] = {}
    for agent_tid, rows in positions.items():
        realized = 0.0
        unrealized = 0.0
        wins = 0
        losses = 0
        trades_closed = 0
        trades_open = 0
        for p in rows:
            if p.get("status") == "open":
                trades_open += 1
                # Shadow-copy to mark-to-market without persisting.
                tmp = dict(p)
                _mark_to_market(tmp, qf)
                unrealized += float(tmp.get("realized_pnl_usd") or 0)
            elif p.get("status", "").startswith("closed"):
                trades_closed += 1
                r = float(p.get("realized_pnl_usd") or 0)
                realized += r
                if r > 0: wins += 1
                elif r < 0: losses += 1
        per_agent[agent_tid] = {
            "realized_pnl_usd": round(realized, 2),
            "unrealized_pnl_usd": round(unrealized, 2),
            "total_pnl_usd": round(realized + unrealized, 2),
            "trades_closed": trades_closed,
            "trades_open": trades_open,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / trades_closed, 4) if trades_closed else 0.0,
        }
    total_realized = sum(a["realized_pnl_usd"] for a in per_agent.values())
    total_unrealized = sum(a["unrealized_pnl_usd"] for a in per_agent.values())
    return {
        "per_agent": per_agent,
        "fleet_realized_pnl_usd": round(total_realized, 2),
        "fleet_unrealized_pnl_usd": round(total_unrealized, 2),
        "fleet_total_pnl_usd": round(total_realized + total_unrealized, 2),
    }


MIN_HOLD_SEC = int(os.environ.get("ITF_MIN_HOLD_SEC", "180"))  # 3 min default. 2026-04-25: push fleet from ~60 to ~500 fills/day. Was 900 (15min) anti-churn, but BP drain root-cause was order pile-up (fixed via MAX_PENDING_PER_SYMBOL=4 + cancel_stale_pending). Account equity > $25K so PDT 4-roundtrip rule is moot; daytrading_buying_power=0 is the structural Reg-T limit (margin used). MIN_HOLD now prevents only sub-3min flap.


# ───── 2026-04-22 BROKER-FILL RECONCILIATION ─────
# The submit path reserves stake from the agent's sub-bankroll, but until
# 2026-04-22 no code path credited realized PnL back from Alpaca fills, so every
# /api/bankrolls read still showed the cold-start seed. reconcile_broker_fills()
# polls Alpaca /v2/account/activities/FILL, matches fills to local positions via
# broker_order_id, and credits realized_pnl to the right agent on closing sides.
# A cursor at data/intraday/fill_reconciliation_cursor.json prevents double-count.


def _load_recon_cursor() -> Dict[str, Any]:
    if not RECON_CURSOR_PATH.exists():
        return {"seen_ids": [], "last_run_at": None}
    try:
        d = json.loads(RECON_CURSOR_PATH.read_text())
        if not isinstance(d, dict):
            return {"seen_ids": [], "last_run_at": None}
        d.setdefault("seen_ids", [])
        d.setdefault("last_run_at", None)
        return d
    except Exception:
        return {"seen_ids": [], "last_run_at": None}


def _save_recon_cursor(cur: Dict[str, Any]) -> None:
    # Keep seen_ids bounded — 2k most-recent is plenty for a ~15min lookback.
    seen = cur.get("seen_ids") or []
    if len(seen) > 2000:
        cur["seen_ids"] = seen[-2000:]
    RECON_CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECON_CURSOR_PATH.write_text(json.dumps(cur, indent=2, default=str))
    global _LEDGER_DIRTY
    _LEDGER_DIRTY = True


def _fetch_fill_activities(lookback_min: int) -> List[Dict[str, Any]]:
    """GET /v2/account/activities/FILL?after=<iso>&direction=desc — stdlib only."""
    if not live_mode():
        return []
    key = os.environ.get("ALPACA_PAPER_KEY")
    secret = os.environ.get("ALPACA_PAPER_SECRET")
    if not (key and secret):
        return []
    import urllib.parse
    import urllib.request
    after = (datetime.now(timezone.utc) - timedelta(minutes=max(1, lookback_min))).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    qs = urllib.parse.urlencode({
        "activity_types": "FILL",
        "after": after,
        "direction": "desc",
        "page_size": "100",
    })
    url = f"https://paper-api.alpaca.markets/v2/account/activities?{qs}"
    req = urllib.request.Request(
        url, headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
            body = r.read().decode("utf-8")
            data = json.loads(body or "[]")
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _index_positions_by_order_id(
    positions: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Dict[str, Any]]:
    """Build {broker_order_id -> position_ref} + {client_order_id -> position_ref}.
    position_ref is a dict {"agent_tid": ..., "position": <mutable row>}."""
    idx: Dict[str, Dict[str, Any]] = {}
    for agent_tid, rows in (positions or {}).items():
        for p in (rows or []):
            oid = p.get("broker_order_id")
            cid = p.get("client_order_id")
            if oid:
                idx[str(oid)] = {"agent_tid": agent_tid, "position": p}
            if cid:
                idx[str(cid)] = {"agent_tid": agent_tid, "position": p}
    return idx


def reconcile_broker_fills(lookback_min: int = 15) -> Dict[str, Any]:
    """Poll Alpaca FILL activities and credit realized PnL back to per-agent
    sub-bankrolls on closing fills (FIFO within a matched position).

    Called at the top of every tick so executor.get_bankroll(tid) reflects true
    post-fill balance before the next prompt is built.

    Behavior:
      * In dry-run mode, no-op (returns zeroed stats).
      * Fills already in cursor.seen_ids are skipped.
      * A fill whose order_id (or client_order_id) matches a local open position
        with an OPPOSITE broker side is treated as a CLOSE:
            - computes realized_pnl = qty_closed * (fill_px - entry_px) * direction
            - credits (stake_portion + realized_pnl) to the agent's bankroll
            - marks the position status="closed_by_fill" when the full qty closed
        A same-side fill is just an open-fill confirmation — updates
        filled_avg_price/filled_qty on the position, no bankroll move (the stake
        was already reserved at submit).

    Returns a stats dict:
      {
        "fills_processed": N,
        "closes_applied":  K,
        "bankroll_delta_by_agent": {tid: float_delta_usd},
        "unmatched_fills": M,
        "skipped_seen":    S,
        "mode":            "live" | "dry_run",
      }
    """
    stats: Dict[str, Any] = {
        "fills_processed": 0,
        "closes_applied": 0,
        "bankroll_delta_by_agent": {},
        "unmatched_fills": 0,
        "skipped_seen": 0,
        "mode": "live" if live_mode() else "dry_run",
    }
    if not live_mode():
        return stats

    cursor = _load_recon_cursor()
    seen: List[str] = list(cursor.get("seen_ids") or [])
    seen_set = set(seen)

    fills = _fetch_fill_activities(lookback_min)
    if not fills:
        cursor["last_run_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _save_recon_cursor(cursor)
        return stats

    positions = _load_positions()
    idx = _index_positions_by_order_id(positions)
    dirty = False

    # Alpaca returns fills newest-first when direction=desc; process oldest-first
    # so FIFO closes are applied in trade order.
    for fill in reversed(fills):
        fill_id = str(fill.get("id") or "")
        if not fill_id:
            continue
        if fill_id in seen_set:
            stats["skipped_seen"] += 1
            continue
        seen_set.add(fill_id)
        seen.append(fill_id)

        order_id = str(fill.get("order_id") or "")
        client_order_id = str(fill.get("client_order_id") or "")
        symbol = (fill.get("symbol") or "").upper()
        fill_side = (fill.get("side") or "").lower()  # buy | sell | sell_short
        try:
            qty_filled = float(fill.get("qty") or 0)
        except Exception:
            qty_filled = 0.0
        try:
            fill_px = float(fill.get("price") or 0)
        except Exception:
            fill_px = 0.0

        match = idx.get(order_id) or idx.get(client_order_id)
        stats["fills_processed"] += 1

        if not match:
            # Fill we don't know about (e.g. bracket child stop-loss legs Alpaca
            # generates internally). Log but don't credit — we can't safely pick
            # an agent without a position link.
            stats["unmatched_fills"] += 1
            _append_ledger({
                "event": "unmatched_fill",
                "source": "broker_reconcile",
                "fill_id": fill_id,
                "order_id": order_id,
                "client_order_id": client_order_id,
                "ticker": symbol,
                "side": fill_side,
                "qty": qty_filled,
                "price": fill_px,
            })
            continue

        agent_tid = match["agent_tid"]
        pos = match["position"]
        pos_side = (pos.get("side") or "").lower()  # long | short
        # Broker "sell" (for a long) OR "buy" (for a short) = closing fill.
        is_close = (
            (pos_side == "long" and fill_side == "sell")
            or (pos_side == "short" and fill_side in ("buy", "buy_to_cover"))
        )
        is_open_confirm = (
            (pos_side == "long" and fill_side == "buy")
            or (pos_side == "short" and fill_side in ("sell", "sell_short"))
        )

        if is_open_confirm:
            # Mark the fill on the position so subsequent MTM reads are honest.
            pos["filled_avg_price"] = fill_px or pos.get("filled_avg_price")
            # Accumulate filled_qty across partial fills.
            prev_filled = float(pos.get("filled_qty") or 0)
            pos["filled_qty"] = round(prev_filled + qty_filled, 6)
            pos["filled_at"] = fill.get("transaction_time") or pos.get("filled_at")
            if (pos.get("broker_status") or "").lower() != "filled":
                pos["broker_status"] = "filled" if pos["filled_qty"] >= float(pos.get("qty") or 0) else "partially_filled"
            dirty = True
            _append_ledger({
                "event": "open_fill_confirm",
                "source": "broker_reconcile",
                "fill_id": fill_id,
                "ts": fill.get("transaction_time"),
                "agent_tid": agent_tid,
                "ticker": symbol,
                "side": fill_side,
                "qty": qty_filled,
                "price": fill_px,
                "realized_pnl": 0.0,
            })
            continue

        if not is_close:
            # Side doesn't make sense vs our recorded pos_side (e.g. recorded as
            # long but fill came back as sell_short). Log and skip — surfaces as
            # unmatched for audit, cursor still advances.
            stats["unmatched_fills"] += 1
            _append_ledger({
                "event": "side_mismatch",
                "source": "broker_reconcile",
                "fill_id": fill_id,
                "agent_tid": agent_tid,
                "pos_side": pos_side,
                "fill_side": fill_side,
                "ticker": symbol,
            })
            continue

        # CLOSING FILL: credit stake_portion + realized_pnl to the agent.
        entry_px = float(pos.get("entry_price") or pos.get("filled_avg_price") or 0)
        total_qty = float(pos.get("qty") or 0) or qty_filled
        if total_qty <= 0:
            stats["unmatched_fills"] += 1
            continue
        portion = min(1.0, qty_filled / total_qty) if total_qty else 1.0
        stake = float(pos.get("stake_usd") or 0)
        stake_portion = round(stake * portion, 2)
        if pos_side == "long":
            pnl = qty_filled * (fill_px - entry_px)
        else:
            pnl = qty_filled * (entry_px - fill_px)
        pnl = round(pnl, 2)
        credit = stake_portion + pnl

        # Don't double-credit: if close_expired/close_position already credited
        # this position (status starts with "closed"), skip the bankroll write
        # but still ledger the broker fill for audit.
        already_closed = str(pos.get("status") or "").startswith("closed")
        if not already_closed:
            credit_bankroll(agent_tid, credit, meta={
                "event_type": "broker_reconcile_close",
                "source": "broker_reconcile",
                "fill_id": fill_id,
                "ticker": symbol,
                "qty_closed": qty_filled,
                "fill_price": fill_px,
                "entry_price": entry_px,
                "stake_portion_returned": stake_portion,
                "realized_pnl": pnl,
            })
            stats["bankroll_delta_by_agent"][agent_tid] = round(
                stats["bankroll_delta_by_agent"].get(agent_tid, 0.0) + credit, 2
            )
            # Mark position closed when the full qty has been sold off.
            if qty_filled >= total_qty - 1e-6:
                pos["status"] = "closed_by_fill"
                pos["closed_at"] = fill.get("transaction_time") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                pos["realized_pnl_usd"] = pnl
                pos["exit_price"] = fill_px
            dirty = True

        _append_ledger({
            "event": "close_fill",
            "source": "broker_reconcile",
            "fill_id": fill_id,
            "ts": fill.get("transaction_time"),
            "agent_tid": agent_tid,
            "ticker": symbol,
            "side": fill_side,
            "qty": qty_filled,
            "price": fill_px,
            "entry_price": entry_px,
            "realized_pnl": pnl,
            "stake_portion_returned": stake_portion,
            "already_closed_locally": already_closed,
        })
        stats["closes_applied"] += 1

    if dirty:
        _save_positions(positions)
    cursor["seen_ids"] = seen
    cursor["last_run_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_recon_cursor(cursor)
    return stats


def close_position(agent_tid: str, ticker: str) -> Dict[str, Any]:
    """2026-04-21 — agent-driven close. Mark matching local open positions closed
    and (in live mode) submit Alpaca DELETE /v2/positions/{symbol} to flatten the
    broker position. Returns entry-style dict mirroring submit().

    Scope: matches ALL open positions for this agent_tid + ticker pair. Broker
    close is market-time-in-force, so crypto closes GTC via order, equities via
    the dedicated positions-close endpoint (net flat).

    2026-04-22 — MIN_HOLD_SEC guard: if ALL matched positions are younger than
    MIN_HOLD_SEC, reject the close with status=blocked_by_min_hold. Forces the
    fleet to hold through intra-hour noise instead of churning daytrades.
    """
    positions = _load_positions()
    ticker_u = (ticker or "").upper().strip()
    matched: List[Dict[str, Any]] = [
        p for p in positions.get(agent_tid, [])
        if p.get("status") == "open" and (p.get("ticker", "") or "").upper().strip() == ticker_u
    ]
    if matched and MIN_HOLD_SEC > 0:
        now_utc = datetime.now(timezone.utc)
        eligible = []
        for p in matched:
            try:
                opened = datetime.fromisoformat((p.get("opened_at") or p.get("ts") or "").replace("Z", "+00:00"))
                if (now_utc - opened).total_seconds() >= MIN_HOLD_SEC:
                    eligible.append(p)
            except Exception:
                eligible.append(p)  # if timestamp unreadable, don't block
        if not eligible:
            blocked = {
                "ts": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "agent_tid": agent_tid,
                "ticker": ticker_u,
                "action": "close_position",
                "status": "blocked_by_min_hold",
                "min_hold_sec": MIN_HOLD_SEC,
                "youngest_age_sec": int(min(
                    (now_utc - datetime.fromisoformat((p.get("opened_at") or p.get("ts") or "").replace("Z", "+00:00"))).total_seconds()
                    for p in matched
                )),
                "matched_positions": len(matched),
            }
            _append_order_log(blocked)
            return blocked
        matched = eligible
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_tid": agent_tid,
        "ticker": ticker_u,
        "action": "close_position",
        "matched_positions": len(matched),
        "mode": "live" if live_mode() else "dry_run",
    }
    if not matched:
        entry["status"] = "no_open_position"
        _append_order_log(entry)
        return entry

    if live_mode():
        import requests
        key = os.environ["ALPACA_PAPER_KEY"]
        secret = os.environ["ALPACA_PAPER_SECRET"]
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        try:
            r = requests.delete(
                f"https://paper-api.alpaca.markets/v2/positions/{ticker_u}",
                headers=headers,
                timeout=10,
            )
            if r.ok:
                entry["broker_status"] = "closed"
                entry["broker_resp"] = (r.json() if r.text else {}).get("status", "submitted")
            else:
                entry["broker_status"] = f"error_{r.status_code}"
                entry["broker_resp"] = r.text[:300]
        except Exception as e:
            entry["broker_status"] = "exception"
            entry["broker_resp"] = str(e)[:300]

    # Mark all matched local positions closed + credit stake back to sub-bankroll.
    # For agent-driven closes we don't have a live quote for exact P&L, so credit
    # only the reserved stake (P&L reconciles from broker fills → next tick via
    # a snapshot reconciliation). This is intentionally conservative: the stake
    # returns, any unrealized gain is "free" on close until reconciled.
    total_stake_returned = 0.0
    for p in matched:
        p["status"] = "closed_by_agent"
        p["closed_at"] = entry["ts"]
        total_stake_returned += float(p.get("stake_usd") or 0)
    if total_stake_returned > 0:
        credit_bankroll(agent_tid, total_stake_returned, meta={
            "ticker": ticker_u,
            "event_type": "agent_close",
            "stake_returned": round(total_stake_returned, 2),
            "n_positions": len(matched),
        })
    _save_positions(positions)
    _append_order_log(entry)
    return entry


def read_trades(limit: int = 200) -> List[Dict[str, Any]]:
    """Tail the dry_run_orders.jsonl log. Shape: every submit() call (fill or reject)."""
    if not ORDERS_JSONL.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        lines = ORDERS_JSONL.read_text().splitlines()
    except Exception:
        return []
    for line in lines[-limit:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def list_open() -> List[Dict[str, Any]]:
    positions = _load_positions()
    out: List[Dict[str, Any]] = []
    for agent_tid, rows in positions.items():
        for p in rows:
            if p.get("status") == "open":
                out.append(p)
    return out


# ───── 2026-04-22 — HF-persistence for the 4 ledger files ─────
# HF Spaces wipe /app on every factory_reboot. positions.json, agent_bankrolls.json,
# fill_reconciliation_cursor.json and agent_ledger.jsonl live under /app/data/intraday
# → every restart = full attribution reset (IA confirmed "36 hours lost").
# Solution: persist_ledgers_to_hub() uploads all four files to the ITF repo itself
# (path_in_repo=data/intraday/*). restore_ledgers.py (shipped alongside app.py in
# the Dockerfile) downloads them on boot before uvicorn starts.

_ITF_REPO_ID = os.environ.get("SPACE_ID") or "LBJLincoln26/intraday-trading-floor"


def _hf_token() -> Optional[str]:
    """Prefer HF_TOKEN_2 (write token, what the memory index says to use), then
    NBA token, then generic HF_TOKEN. Never raise — silent skip if absent."""
    for k in ("HF_TOKEN_2", "HF_TOKEN_NBA", "HF_WRITE_TOKEN", "NOMOS_HF_TOKEN", "HF_TOKEN"):
        v = os.environ.get(k)
        if v:
            return v
    return None


def persist_ledgers_to_hub(force: bool = False) -> Dict[str, Any]:
    """Upload the 4 ledger files to the ITF HF repo so a factory_reboot can
    re-hydrate them via restore_ledgers.py.

    One commit per invocation (batched via `create_commit` with up to 4 ops)
    so we don't spam the repo with tick-cadence commits. Called at the end of
    every tick_once(); _LEDGER_DIRTY gates so ticks with no mutations skip
    the Hub round-trip entirely.

    Rules:
      * missing file       → skipped (no error).
      * agent_ledger.jsonl → skipped when size > 5 MB (append-only, would
                             thrash the LFS-free 10 MB quota).
      * no HF token        → returns early with {"skipped": "no-token"}.
      * any exception      → caught, returned in `errors`, never raised.

    Returns {"uploaded": [...], "skipped": "...", "errors": [...]}.
    """
    out: Dict[str, Any] = {"uploaded": [], "errors": []}

    global _LEDGER_DIRTY
    if not force and not _LEDGER_DIRTY:
        out["skipped"] = "clean"
        return out

    tok = _hf_token()
    if not tok:
        out["skipped"] = "no-token"
        return out

    try:
        from huggingface_hub import HfApi
        from huggingface_hub import CommitOperationAdd
    except Exception as e:
        out["errors"].append(f"import_hfapi: {str(e)[:200]}")
        return out

    candidates = [
        (POSITIONS_PATH, "data/intraday/positions.json", False),
        (BANKROLLS_PATH, "data/intraday/agent_bankrolls.json", False),
        (RECON_CURSOR_PATH, "data/intraday/fill_reconciliation_cursor.json", False),
        (LEDGER_JSONL, "data/intraday/agent_ledger.jsonl", True),
    ]
    ops: List[Any] = []
    for local, remote, is_ledger in candidates:
        try:
            if not local.exists():
                continue
            if is_ledger:
                try:
                    size = local.stat().st_size
                except Exception:
                    size = 0
                if size > _LEDGER_MAX_UPLOAD_BYTES:
                    out.setdefault("skipped_big", []).append(
                        {"path": remote, "bytes": size}
                    )
                    continue
            ops.append(CommitOperationAdd(path_in_repo=remote, path_or_fileobj=str(local)))
        except Exception as e:
            out["errors"].append(f"{remote}: {str(e)[:200]}")

    if not ops:
        out["skipped"] = "no-ops"
        _LEDGER_DIRTY = False
        return out

    try:
        api = HfApi(token=tok)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        api.create_commit(
            repo_id=_ITF_REPO_ID,
            repo_type="space",
            operations=ops,
            commit_message=f"[ITF-LEDGER] tick snapshot {ts}",
        )
        out["uploaded"] = [op.path_in_repo for op in ops]
        _LEDGER_DIRTY = False
    except Exception as e:
        out["errors"].append(f"commit: {str(e)[:300]}")
    return out
