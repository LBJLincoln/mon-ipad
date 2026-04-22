"""Prediction-market event executor — Kalshi + Polymarket, paper mode.

Both venues are READ live (free public APIs — no auth needed for market data):
  - Kalshi:     https://trading-api.kalshi.com/trade-api/v2/markets
  - Polymarket: https://gamma-api.polymarket.com/markets

Fills are SIMULATED at midpoint (+slippage) and kept in a paper ledger. Live
execution is gated behind env flags (KALSHI_LIVE=1 / POLY_LIVE=1) — neither
is on by default because Polymarket trading requires USDC+gas on Polygon and
Kalshi requires signed API credentials.

Positions survive across ticks, are marked to market via current midpoint,
and close on agent-close / stop / take-profit / EOD flatten.

Public surface:
  list_markets(venue, limit)       → [ {market_id, question, yes_price, no_price, volume_usd, close_ts} ]
  place_paper_order(agent_tid, venue, market_id, side, size_usd, thesis) → dict entry or None
  close_paper_position(agent_tid, venue, market_id)                       → dict entry with realized P&L
  mark_to_market(agent_tid)                                               → {unrealized: float, open_n: int}
  realized_pnl(agent_tid)                                                  → float (all-time)
  load_positions()                                                         → raw ledger
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import urllib.request
import urllib.error

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[3]
_LEDGER = _REPO / "data" / "intraday" / "event_positions.json"
_LEDGER.parent.mkdir(parents=True, exist_ok=True)

# 2026-04-22 — trading-api.kalshi.com/* returns 401 without signed creds. The
# public election API serves identical market data with no auth (verified live).
_KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
_POLY_BASE = "https://gamma-api.polymarket.com"

_MARKET_CACHE: Dict[str, Any] = {"kalshi": {"ts": 0, "rows": []}, "polymarket": {"ts": 0, "rows": []}}
_CACHE_TTL_S = 60  # refresh markets once per minute

PAPER_SLIPPAGE = 0.01  # 1¢ slippage on a 0-1 price — conservative for prediction markets
MIN_EVENT_STAKE_USD = 5.0  # sanity floor; prediction markets pay 0-100¢ on $1
MAX_EVENT_STAKE_USD = 5000.0  # per single event position


def _http_get_json(url: str, timeout: float = 6.0) -> Optional[Any]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nomos42-itf/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return None


def _kalshi_markets(limit: int = 30) -> List[Dict[str, Any]]:
    # Kalshi modernized 2025 — fields moved to *_dollars (already in USD, not cents).
    # Older yes_bid/no_bid are deprecated. Also request a larger page + tiered filters
    # so we return enough quotable binaries after dropping mid-less contracts.
    data = _http_get_json(f"{_KALSHI_BASE}/markets?status=open&limit={max(limit, 100)}")
    if not data:
        return []
    rows: List[Dict[str, Any]] = []
    def _f(v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    for m in (data.get("markets") or []):
        yb = _f(m.get("yes_bid_dollars"))
        ya = _f(m.get("yes_ask_dollars"))
        nb = _f(m.get("no_bid_dollars"))
        na = _f(m.get("no_ask_dollars"))
        if yb is None:
            raw = _f(m.get("yes_bid"))
            yb = (raw / 100.0) if raw is not None else None
        if ya is None:
            raw = _f(m.get("yes_ask"))
            ya = (raw / 100.0) if raw is not None else None
        last = _f(m.get("last_price_dollars"))
        if last is None:
            raw = _f(m.get("last_price"))
            last = (raw / 100.0) if raw else None
        # Midpoint preference: (yb+ya)/2 > ya > last > yb. Skip markets with no price.
        if yb is not None and ya is not None and yb > 0 and ya > 0:
            yes_price = (yb + ya) / 2.0
        elif ya is not None and ya > 0:
            yes_price = ya
        elif last is not None and last > 0:
            yes_price = last
        elif yb is not None and yb > 0:
            yes_price = yb
        else:
            yes_price = None
        if nb is not None and na is not None and nb > 0 and na > 0:
            no_price = (nb + na) / 2.0
        elif na is not None and na > 0:
            no_price = na
        elif yes_price is not None:
            no_price = 1.0 - yes_price
        else:
            no_price = None
        vol = _f(m.get("notional_value_dollars")) or _f(m.get("liquidity_dollars")) or _f(m.get("volume")) or 0.0
        rows.append({
            "venue": "kalshi",
            "market_id": m.get("ticker"),
            "question": (m.get("title") or m.get("subtitle") or m.get("yes_sub_title") or "")[:220],
            "yes_price": yes_price,
            "no_price": no_price,
            "volume_usd": float(vol),
            "close_ts": m.get("close_time") or m.get("expected_expiration_time"),
        })
    usable = [r for r in rows if r["yes_price"] is not None and 0 < r["yes_price"] < 1]
    # Highest-liquidity first so the prompt slot goes to the most tradeable markets.
    usable.sort(key=lambda r: r["volume_usd"], reverse=True)
    return usable[:limit]


def _polymarket_markets(limit: int = 30) -> List[Dict[str, Any]]:
    data = _http_get_json(f"{_POLY_BASE}/markets?active=true&closed=false&limit={limit}&order=volume24hr&ascending=false")
    if not isinstance(data, list):
        return []
    rows: List[Dict[str, Any]] = []
    for m in data[:limit]:
        try:
            outcomes = json.loads(m.get("outcomePrices") or "[]")
            if not (isinstance(outcomes, list) and len(outcomes) >= 2):
                continue
            yes_price = float(outcomes[0])
            no_price = float(outcomes[1])
        except (ValueError, TypeError):
            continue
        rows.append({
            "venue": "polymarket",
            "market_id": m.get("conditionId") or m.get("id"),
            "question": (m.get("question") or "")[:220],
            "yes_price": yes_price,
            "no_price": no_price,
            "volume_usd": float(m.get("volume24hr") or 0),
            "close_ts": m.get("endDate"),
        })
    return rows


def list_markets(venue: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Cached live feed of open markets for a venue."""
    now = time.time()
    cache = _MARKET_CACHE.get(venue) or {"ts": 0, "rows": []}
    if now - cache["ts"] < _CACHE_TTL_S and cache["rows"]:
        return cache["rows"][:limit]
    rows = _kalshi_markets(limit=max(limit, 30)) if venue == "kalshi" else _polymarket_markets(limit=max(limit, 30))
    _MARKET_CACHE[venue] = {"ts": now, "rows": rows}
    return rows[:limit]


def _find_market(venue: str, market_id: str) -> Optional[Dict[str, Any]]:
    for row in list_markets(venue, limit=50):
        if row["market_id"] == market_id:
            return row
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_positions() -> Dict[str, List[Dict[str, Any]]]:
    if not _LEDGER.exists():
        return {}
    try:
        return json.loads(_LEDGER.read_text() or "{}")
    except json.JSONDecodeError:
        return {}


def _save_positions(ledger: Dict[str, List[Dict[str, Any]]]) -> None:
    _LEDGER.write_text(json.dumps(ledger, indent=2))


def place_paper_order(
    agent_tid: str,
    venue: str,
    market_id: str,
    side: str,
    size_usd: float,
    thesis: str = "",
) -> Optional[Dict[str, Any]]:
    """Open a paper position at midpoint + slippage. Returns the ledger entry."""
    side = (side or "").lower()
    if side not in ("yes", "no"):
        return {"status": "error", "reason": f"bad side: {side}"}
    if venue not in ("kalshi", "polymarket"):
        return {"status": "error", "reason": f"bad venue: {venue}"}
    size_usd = max(MIN_EVENT_STAKE_USD, min(MAX_EVENT_STAKE_USD, float(size_usd or 0)))

    market = _find_market(venue, market_id)
    if not market:
        return {"status": "error", "reason": f"market not found: {venue}:{market_id}"}
    entry_price = market["yes_price"] if side == "yes" else market["no_price"]
    if entry_price is None or entry_price <= 0 or entry_price >= 1:
        return {"status": "error", "reason": f"bad midpoint: {entry_price}"}
    entry_price = min(0.99, entry_price + PAPER_SLIPPAGE)  # pay slippage on entry

    contracts = size_usd / entry_price
    entry = {
        "venue": venue,
        "market_id": market_id,
        "question": market["question"],
        "side": side,
        "size_usd": round(size_usd, 2),
        "entry_price": round(entry_price, 4),
        "contracts": round(contracts, 4),
        "entry_ts": _now_iso(),
        "thesis": (thesis or "")[:300],
        "status": "open",
        "realized_pnl": 0.0,
        "mode": "paper",
    }
    ledger = load_positions()
    ledger.setdefault(agent_tid, []).append(entry)
    _save_positions(ledger)
    return entry


def close_paper_position(agent_tid: str, venue: str, market_id: str) -> Optional[Dict[str, Any]]:
    """Close a paper position at current midpoint. Returns the closed entry with realized P&L."""
    ledger = load_positions()
    positions = ledger.get(agent_tid) or []
    for p in positions:
        if (p.get("venue") == venue and p.get("market_id") == market_id
                and p.get("status") == "open"):
            market = _find_market(venue, market_id)
            exit_price = (market["yes_price"] if p["side"] == "yes" else market["no_price"]) if market else p["entry_price"]
            exit_price = max(0.01, min(0.99, float(exit_price or p["entry_price"])))
            pnl = (exit_price - p["entry_price"]) * p["contracts"]
            p["status"] = "closed"
            p["exit_price"] = round(exit_price, 4)
            p["exit_ts"] = _now_iso()
            p["realized_pnl"] = round(pnl, 2)
            _save_positions(ledger)
            return p
    return {"status": "error", "reason": f"no open position: {agent_tid} {venue}:{market_id}"}


def mark_to_market(agent_tid: str) -> Dict[str, float]:
    """Compute unrealized P&L + open notional across agent's event positions."""
    positions = load_positions().get(agent_tid) or []
    unrealized = 0.0
    open_n = 0
    for p in positions:
        if p.get("status") != "open":
            continue
        market = _find_market(p["venue"], p["market_id"])
        if not market:
            continue
        cur_price = market["yes_price"] if p["side"] == "yes" else market["no_price"]
        if cur_price is None:
            continue
        unrealized += (float(cur_price) - p["entry_price"]) * p["contracts"]
        open_n += 1
    return {"unrealized_pnl": round(unrealized, 2), "open_positions": open_n}


def realized_pnl(agent_tid: str) -> float:
    positions = load_positions().get(agent_tid) or []
    return round(sum(float(p.get("realized_pnl") or 0) for p in positions if p.get("status") == "closed"), 2)


def agent_event_exposure(agent_tid: str) -> float:
    """Total USD currently locked in open event positions."""
    positions = load_positions().get(agent_tid) or []
    return round(sum(float(p.get("size_usd") or 0) for p in positions if p.get("status") == "open"), 2)


def expire_stale(now: Optional[datetime] = None) -> int:
    """Close any position whose market close_ts has passed. Returns count closed."""
    now = now or datetime.now(timezone.utc)
    ledger = load_positions()
    closed = 0
    for agent_tid, positions in ledger.items():
        for p in positions:
            if p.get("status") != "open":
                continue
            close_iso = p.get("close_ts")
            if not close_iso:
                continue
            try:
                close_dt = datetime.fromisoformat(close_iso.replace("Z", "+00:00"))
                if close_dt.tzinfo is None:
                    close_dt = close_dt.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue
            if now >= close_dt:
                market = _find_market(p["venue"], p["market_id"])
                exit_price = (market["yes_price"] if p["side"] == "yes" else market["no_price"]) if market else p["entry_price"]
                exit_price = max(0.01, min(0.99, float(exit_price or p["entry_price"])))
                p["status"] = "closed"
                p["exit_price"] = round(exit_price, 4)
                p["exit_ts"] = _now_iso()
                p["realized_pnl"] = round((exit_price - p["entry_price"]) * p["contracts"], 2)
                p["close_reason"] = "market_expired"
                closed += 1
    if closed:
        _save_positions(ledger)
    return closed
