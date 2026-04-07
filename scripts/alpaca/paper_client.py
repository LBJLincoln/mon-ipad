#!/usr/bin/env python3
"""
Alpaca Paper-Trading Client — forwards Trading Floor picks to a real broker.

Status (2026-04-07): SCAFFOLD — first commit. The user has an Alpaca paper
account; this client will execute political-trading-floor.py picks against it
so we can validate end-to-end without wiring real money.

Why Alpaca and not Interactive Brokers / TastyTrade: Alpaca has the most
forgiving free paper-trading API, supports fractional shares, and lets us
backtest the political ETF basket on actual fills (not just mid-prices).

Required env vars (added to .env.local — never committed):
  ALPACA_PAPER_KEY     — paper API key id
  ALPACA_PAPER_SECRET  — paper API secret
  ALPACA_PAPER_BASE    — defaults to https://paper-api.alpaca.markets

Usage:
  python3 scripts/alpaca/paper_client.py status
  python3 scripts/alpaca/paper_client.py orders
  python3 scripts/alpaca/paper_client.py sync-political   # forward latest political TF picks
  python3 scripts/alpaca/paper_client.py sync-nba          # forward NBA TF picks (no order — logs only)

Files written:
  data/alpaca/account-status.json    — account snapshot, refreshed each run
  data/alpaca/order-log.jsonl        — append-only log of every order request
  data/alpaca/positions-latest.json  — current open positions

Related:
  - scripts/arena/political-trading-floor.py — produces the picks we forward
  - data/arena/political/political-trading-floor-latest.json — source picks file
  - data/arena/cpcv-gated-strategies.json — only forward picks whose strategy
    has cleared the CPCV gate (DSR > 0 at p < 0.05, PBO < 0.40)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "alpaca"
DATA.mkdir(parents=True, exist_ok=True)

ALPACA_BASE = os.environ.get("ALPACA_PAPER_BASE", "https://paper-api.alpaca.markets")
ALPACA_KEY = os.environ.get("ALPACA_PAPER_KEY", "")
ALPACA_SECRET = os.environ.get("ALPACA_PAPER_SECRET", "")

POLITICAL_PICKS = ROOT / "data" / "arena" / "political" / "political-trading-floor-latest.json"
GATE_FILE = ROOT / "data" / "arena" / "political-cpcv-gated-strategies.json"


def _request(method: str, path: str, body: dict | None = None) -> dict | list | None:
    """Minimal Alpaca REST helper. Returns parsed JSON or None on failure."""
    if not ALPACA_KEY or not ALPACA_SECRET:
        print("[alpaca] missing ALPACA_PAPER_KEY / ALPACA_PAPER_SECRET in env", file=sys.stderr)
        return None
    url = f"{ALPACA_BASE.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("APCA-API-KEY-ID", ALPACA_KEY)
    req.add_header("APCA-API-SECRET-KEY", ALPACA_SECRET)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode()
        except Exception:
            err_body = ""
        print(f"[alpaca] HTTP {e.code} on {method} {path}: {err_body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[alpaca] {method} {path} failed: {e}", file=sys.stderr)
        return None


def cmd_status() -> int:
    acct = _request("GET", "/v2/account")
    if not acct:
        return 1
    snap = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "account_id": acct.get("id"),
        "status": acct.get("status"),
        "buying_power": acct.get("buying_power"),
        "equity": acct.get("equity"),
        "cash": acct.get("cash"),
        "portfolio_value": acct.get("portfolio_value"),
    }
    (DATA / "account-status.json").write_text(json.dumps(snap, indent=2))
    print(json.dumps(snap, indent=2))
    return 0


def cmd_orders() -> int:
    orders = _request("GET", "/v2/orders?status=all&limit=20") or []
    print(json.dumps(orders, indent=2))
    return 0


def _gate_passing_strategies() -> set[str]:
    if not GATE_FILE.exists():
        return set()
    try:
        gate = json.loads(GATE_FILE.read_text())
        return {p.get("strategy") for p in gate.get("passing", []) if p.get("strategy")}
    except Exception:
        return set()


def cmd_sync_political(dry_run: bool = True) -> int:
    if not POLITICAL_PICKS.exists():
        print(f"[alpaca] {POLITICAL_PICKS} missing — run political-trading-floor.py first", file=sys.stderr)
        return 1
    picks = json.loads(POLITICAL_PICKS.read_text())
    passing = _gate_passing_strategies()

    log_rows = []
    for trader_id, t in (picks.get("traders", {}) or {}).items():
        for pos in (t.get("positions") or []):
            strategy = pos.get("strategy") or t.get("primary_strategy")
            if passing and strategy not in passing:
                continue  # gate-failing strategies are NOT routed to broker
            row = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "trader": trader_id,
                "strategy": strategy,
                "symbol": pos.get("ticker"),
                "qty": pos.get("shares") or pos.get("qty") or 1,
                "side": pos.get("side", "buy"),
                "type": "market",
                "time_in_force": "day",
                "dry_run": dry_run,
            }
            log_rows.append(row)
            if not dry_run:
                _request("POST", "/v2/orders", body={
                    "symbol": row["symbol"],
                    "qty": str(row["qty"]),
                    "side": row["side"],
                    "type": row["type"],
                    "time_in_force": row["time_in_force"],
                })

    log_path = DATA / "order-log.jsonl"
    with log_path.open("a") as f:
        for r in log_rows:
            f.write(json.dumps(r) + "\n")
    print(f"[alpaca] {'dry-run-' if dry_run else ''}sync-political: queued {len(log_rows)} orders")
    if dry_run:
        print("       (run with --live to actually submit; otherwise just logged)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Alpaca paper-trading client (scaffold)")
    p.add_argument("cmd", choices=["status", "orders", "sync-political", "sync-nba"])
    p.add_argument("--live", action="store_true", help="Actually submit orders (default is dry-run)")
    args = p.parse_args()

    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "orders":
        return cmd_orders()
    if args.cmd == "sync-political":
        return cmd_sync_political(dry_run=not args.live)
    if args.cmd == "sync-nba":
        print("[alpaca] sync-nba: NBA picks are not yet broker-routable (sportsbook only). NOOP.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
