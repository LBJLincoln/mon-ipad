#!/usr/bin/env python3
"""
Nomos42 — Kraken Crypto Trading Client
=======================================
Spot REST API client for the Kraken exchange.
Covers the political alpha crypto basket: COIN proxy (via BTC/ETH/SOL),
and any crypto-adjacent donor tickers tradeable on Kraken.

Why Kraken:
  - Direct REST + WebSocket v2 API, fully documented
  - 200+ assets, fractional trading, no minimum balance
  - EU-accessible, low fees (0.25% taker, 0.16% maker at $10M+ tier)
  - Supports BTC, ETH, SOL, and xStocks (tokenized equities) — covers our basket
  - python-kraken-sdk available but we use stdlib urllib to stay zero-dep on VM

Accounts available (set via env var KRAKEN_ACCOUNT):
  - "main"   → KRAKEN_API_KEY / KRAKEN_API_SECRET
  - "paper"  → no real Kraken paper mode; we implement local dry-run like Alpaca client

Usage:
    # Account status
    python3 scripts/alpaca/kraken_client.py status

    # Live BTC/ETH/SOL ticker prices
    python3 scripts/alpaca/kraken_client.py ticker

    # Check open positions
    python3 scripts/alpaca/kraken_client.py positions

    # Sync political alpha signals → dry-run orders (safe default)
    python3 scripts/alpaca/kraken_client.py sync-political

    # Place a live limit order (requires --live flag)
    python3 scripts/alpaca/kraken_client.py order --pair XBTUSD --side buy --qty 0.001 --live

Rate limits (Starter tier):
  - Counter max: 15, decay 0.33/sec
  - AddOrder on separate limiter (1 req/sec effective)
  - We throttle to 1 public + 1 private call per 3 seconds to stay safe

Env vars:
  KRAKEN_API_KEY     — REST API key (read+trade permissions)
  KRAKEN_API_SECRET  — REST API secret (base64-encoded)
  DRY_RUN            — "true" (default) to log orders without executing
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ══════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════

BASE_URL = "https://api.kraken.com"
API_VERSION = "0"

# Political alpha crypto basket — Kraken pair names
# Kraken uses XBT (not BTC). Check /0/public/AssetPairs for exact names.
CRYPTO_BASKET = {
    "BTC":  "XBTUSD",   # Bitcoin — core basket
    "ETH":  "ETHUSD",   # Ethereum
    "SOL":  "SOLUSD",   # Solana
    "COIN": None,        # Coinbase not tradeable on Kraken (use MSTR as proxy)
    "MSTR": None,        # MicroStrategy — xStocks endpoint, check availability
}

# NBA bankroll parallel: crypto not bet-routable, so Kraken is political alpha only
POLITICAL_TICKERS = list(t for t in CRYPTO_BASKET if CRYPTO_BASKET[t])

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "kraken"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ORDER_LOG = DATA_DIR / "order-log.jsonl"
POSITIONS_FILE = DATA_DIR / "positions-latest.json"
ACCOUNT_FILE = DATA_DIR / "account-status.json"

# Throttle: never exceed 1 call per 3 seconds to stay within Starter tier limits
_last_call_ts = 0.0


def _throttle():
    global _last_call_ts
    elapsed = time.time() - _last_call_ts
    if elapsed < 3.0:
        time.sleep(3.0 - elapsed)
    _last_call_ts = time.time()


# ══════════════════════════════════════════════════════════
# AUTH — Kraken signed request (HMAC-SHA512)
# ══════════════════════════════════════════════════════════

def _kraken_signature(url_path: str, data: dict, secret: str) -> str:
    """Generate Kraken API-Sign header value."""
    post_data = urllib.parse.urlencode(data)
    encoded = (str(data["nonce"]) + post_data).encode()
    message = url_path.encode() + hashlib.sha256(encoded).digest()
    mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
    return base64.b64encode(mac.digest()).decode()


def _nonce() -> str:
    return str(int(time.time() * 1000))


# ══════════════════════════════════════════════════════════
# HTTP HELPERS
# ══════════════════════════════════════════════════════════

def _public_get(endpoint: str, params: dict | None = None) -> dict:
    """Call a public Kraken endpoint (no auth needed)."""
    _throttle()
    url = f"{BASE_URL}/{API_VERSION}/public/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Nomos42/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read())
    if body.get("error"):
        raise RuntimeError(f"Kraken public error: {body['error']}")
    return body.get("result", {})


def _private_post(endpoint: str, data: dict, api_key: str, api_secret: str) -> dict:
    """Call a private Kraken endpoint (signed)."""
    _throttle()
    url_path = f"/{API_VERSION}/private/{endpoint}"
    data["nonce"] = _nonce()
    post_data = urllib.parse.urlencode(data).encode()
    signature = _kraken_signature(url_path, data, api_secret)
    headers = {
        "API-Key": api_key,
        "API-Sign": signature,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Nomos42/1.0",
    }
    req = urllib.request.Request(
        BASE_URL + url_path, data=post_data, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read())
    if body.get("error"):
        raise RuntimeError(f"Kraken private error: {body['error']}")
    return body.get("result", {})


# ══════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════

def get_ticker(pairs: list[str]) -> dict:
    """Fetch current bid/ask/last for a list of Kraken pair names."""
    pair_str = ",".join(pairs)
    return _public_get("Ticker", {"pair": pair_str})


def get_ohlc(pair: str, interval: int = 60, since: int | None = None) -> dict:
    """Fetch OHLC candles. interval in minutes: 1,5,15,30,60,240,1440,10080,21600."""
    params = {"pair": pair, "interval": interval}
    if since:
        params["since"] = since
    return _public_get("OHLC", params)


def get_order_book(pair: str, count: int = 10) -> dict:
    """Fetch top-N bids/asks for a pair."""
    return _public_get("Depth", {"pair": pair, "count": count})


# ══════════════════════════════════════════════════════════
# PRIVATE API
# ══════════════════════════════════════════════════════════

def _creds() -> tuple[str, str]:
    key = os.environ.get("KRAKEN_API_KEY", "")
    secret = os.environ.get("KRAKEN_API_SECRET", "")
    if not key or not secret:
        raise RuntimeError(
            "Set KRAKEN_API_KEY and KRAKEN_API_SECRET env vars. "
            "Generate at: https://www.kraken.com/u/settings/api"
        )
    return key, secret


def get_balance() -> dict:
    key, secret = _creds()
    return _private_post("Balance", {}, key, secret)


def get_open_orders() -> dict:
    key, secret = _creds()
    return _private_post("OpenOrders", {}, key, secret)


def get_closed_orders(trades: bool = False) -> dict:
    key, secret = _creds()
    return _private_post("ClosedOrders", {"trades": trades}, key, secret)


def get_trade_history() -> dict:
    key, secret = _creds()
    return _private_post("TradesHistory", {}, key, secret)


def place_order(
    pair: str,
    side: str,          # "buy" or "sell"
    order_type: str,    # "market" or "limit"
    qty: float,
    price: float | None = None,
    dry_run: bool = True,
) -> dict:
    """
    Place a spot order. dry_run=True (default) logs the order without executing.

    Args:
        pair:       Kraken pair name e.g. "XBTUSD", "ETHUSD"
        side:       "buy" or "sell"
        order_type: "market" or "limit"
        qty:        Volume in base currency (e.g. 0.001 BTC)
        price:      Required for limit orders
        dry_run:    If True, log but do not submit to exchange

    Returns:
        Order result dict (or dry-run log entry)
    """
    order = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pair": pair,
        "side": side,
        "order_type": order_type,
        "qty": qty,
        "price": price,
        "dry_run": dry_run,
    }

    if dry_run or os.environ.get("DRY_RUN", "true").lower() == "true":
        order["status"] = "DRY_RUN_LOGGED"
        _append_log(order)
        print(f"[DRY-RUN] {side.upper()} {qty} {pair} @ {'market' if not price else price}")
        return order

    # Live order
    key, secret = _creds()
    data: dict = {
        "pair": pair,
        "type": side,
        "ordertype": order_type,
        "volume": str(qty),
    }
    if order_type == "limit" and price is not None:
        data["price"] = str(price)

    result = _private_post("AddOrder", data, key, secret)
    order["status"] = "SUBMITTED"
    order["txid"] = result.get("txid", [])
    order["descr"] = result.get("descr", {})
    _append_log(order)
    print(f"[LIVE] Order placed: {result}")
    return order


def cancel_order(txid: str) -> dict:
    key, secret = _creds()
    return _private_post("CancelOrder", {"txid": txid}, key, secret)


# ══════════════════════════════════════════════════════════
# LOG HELPERS
# ══════════════════════════════════════════════════════════

def _append_log(entry: dict):
    with open(ORDER_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ══════════════════════════════════════════════════════════
# HIGH-LEVEL COMMANDS
# ══════════════════════════════════════════════════════════

def cmd_status():
    """Fetch and save account balance snapshot."""
    balance = get_balance()
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "balance": balance,
        "crypto_basket_pairs": CRYPTO_BASKET,
    }
    ACCOUNT_FILE.write_text(json.dumps(snapshot, indent=2))
    print(json.dumps(snapshot, indent=2))


def cmd_ticker():
    """Print current prices for crypto basket."""
    pairs = [v for v in CRYPTO_BASKET.values() if v]
    result = get_ticker(pairs)
    print(f"\n{'Pair':<12} {'Bid':>10} {'Ask':>10} {'Last':>10}")
    print("-" * 45)
    for pair_key, data in result.items():
        bid  = float(data["b"][0])
        ask  = float(data["a"][0])
        last = float(data["c"][0])
        print(f"{pair_key:<12} {bid:>10.2f} {ask:>10.2f} {last:>10.2f}")


def cmd_positions():
    """Fetch open orders and balance, save to positions file."""
    balance = get_balance()
    open_orders = get_open_orders()
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "balance": balance,
        "open_orders": open_orders,
    }
    POSITIONS_FILE.write_text(json.dumps(snapshot, indent=2))
    print(json.dumps(snapshot, indent=2))


def cmd_sync_political(live: bool = False):
    """
    Read latest political trading floor signals and route buy/sell orders.
    Default: dry-run. Pass --live to execute real orders.

    Signal source: data/arena/political-trading-floor-latest.json
    Only acts on crypto assets (BTC, ETH, SOL) in the donor basket.
    Kelly sizing: max 2% of portfolio per position (conservative, political alpha only).
    """
    signals_file = REPO_ROOT / "data" / "arena" / "political-trading-floor-latest.json"
    if not signals_file.exists():
        print("No political trading floor signals found. Run political-trading-floor.py first.")
        return

    signals = json.loads(signals_file.read_text())
    consensus = signals.get("consensus", {}).get("recommendations", [])

    balance = {}
    if live:
        balance = get_balance()

    orders_placed = []
    for rec in consensus:
        ticker = rec.get("ticker", "")
        kraken_pair = CRYPTO_BASKET.get(ticker)
        if not kraken_pair:
            continue  # Skip non-Kraken assets (COIN, stocks, etc.)

        action = rec.get("action", "hold").lower()
        confidence = float(rec.get("confidence", 0.5))
        if action == "hold" or confidence < 0.6:
            continue

        # Kelly sizing: 2% of ZUSD balance max, scaled by confidence
        zusd_balance = float(balance.get("ZUSD", 1000))
        kelly_fraction = min(0.02, (confidence - 0.5) * 0.04)  # max 2%
        usd_size = zusd_balance * kelly_fraction

        # Get current price to convert to qty
        price_data = get_ticker([kraken_pair])
        ask = float(list(price_data.values())[0]["a"][0])
        qty = round(usd_size / ask, 6)

        if qty <= 0.0001:
            continue  # Below minimum order size

        result = place_order(
            pair=kraken_pair,
            side="buy" if action == "buy" else "sell",
            order_type="market",
            qty=qty,
            dry_run=not live,
        )
        orders_placed.append(result)

    print(f"\nSync complete: {len(orders_placed)} orders {'placed (LIVE)' if live else 'logged (dry-run)'}")
    print(f"Order log: {ORDER_LOG}")


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nomos42 Kraken Client")
    parser.add_argument("command", choices=["status", "ticker", "positions", "sync-political", "order"])
    parser.add_argument("--pair",  help="Kraken pair (e.g. XBTUSD)")
    parser.add_argument("--side",  choices=["buy", "sell"])
    parser.add_argument("--qty",   type=float)
    parser.add_argument("--price", type=float)
    parser.add_argument("--live",  action="store_true", help="Execute real orders (default: dry-run)")
    args = parser.parse_args()

    try:
        if args.command == "status":
            cmd_status()
        elif args.command == "ticker":
            cmd_ticker()
        elif args.command == "positions":
            cmd_positions()
        elif args.command == "sync-political":
            cmd_sync_political(live=args.live)
        elif args.command == "order":
            if not all([args.pair, args.side, args.qty]):
                parser.error("order requires --pair, --side, --qty")
            place_order(
                pair=args.pair, side=args.side,
                order_type="limit" if args.price else "market",
                qty=args.qty, price=args.price, dry_run=not args.live,
            )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
