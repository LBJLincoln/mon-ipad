"""Polymarket event feed — real-money political event catalysts for PQTF.

Polymarket is the largest real-money political/geo prediction market. We use it
as an event-source for PQTF: when a Polymarket price moves sharply (>5% in 1h)
on a known political event (Fed, election, sanction), we tag that as a live
event and let the PQTF agents bet sector-ETF options on the implied catalyst.

Shared with POL TF (Rule 2 parity): same events feed both floors.

API: CLOB v2 public read endpoints (no auth for public markets).
  GET https://gamma-api.polymarket.com/markets?limit=50&active=true&tags=politics
  GET https://clob.polymarket.com/markets

Usage:
  from polymarket_feed import fetch_live_political_events
  events = fetch_live_political_events(min_volume=10_000, top_n=20)
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:
    requests = None

GAMMA_BASE = "https://gamma-api.polymarket.com"
_cache: Dict[str, Any] = {"ts": 0.0, "data": None}
_CACHE_TTL = 300.0  # 5min


def _enabled() -> bool:
    return os.environ.get("USE_POLYMARKET") == "1" and requests is not None


def _fetch_markets(limit: int = 50) -> List[dict]:
    if not _enabled():
        return []
    try:
        r = requests.get(f"{GAMMA_BASE}/markets",
                         params={"limit": limit, "active": "true", "closed": "false"},
                         timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
    except Exception:
        pass
    return []


def fetch_live_political_events(min_volume: float = 10_000.0,
                                top_n: int = 20) -> List[dict]:
    """Return top-N active political markets by 24h volume, above min_volume.

    Each returned dict has:
      {market_id, question, yes_price, no_price, volume_24h, volume_total,
       end_date, category, sector_map, source:'polymarket', ts}
    sector_map heuristically maps question keywords to sector ETFs so PQTF
    agents can target XLF/XLE/XLK/etc.
    """
    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]
    raw = _fetch_markets(limit=100)
    out: List[dict] = []
    for m in raw:
        try:
            vol_24h = float(m.get("volume24hr") or 0)
            vol_total = float(m.get("volume") or 0)
            vol = vol_24h if vol_24h > 0 else vol_total
            if vol < min_volume:
                continue
            q = (m.get("question") or "").lower()
            sector_map = _map_to_sector(q)
            prices = m.get("outcomePrices") or []
            if isinstance(prices, str):
                try:
                    import json as _j; prices = _j.loads(prices)
                except Exception:
                    prices = []
            yes_p = float(prices[0]) if len(prices) > 0 else 0.0
            no_p = float(prices[1]) if len(prices) > 1 else 0.0
            out.append({
                "market_id": m.get("id") or m.get("conditionId"),
                "question": m.get("question"),
                "yes_price": yes_p,
                "no_price": no_p,
                "volume_24h": vol_24h,
                "volume_total": vol_total,
                "liquidity": float(m.get("liquidity") or 0),
                "end_date": m.get("endDate"),
                "slug": m.get("slug"),
                "sector_map": sector_map,
                "source": "polymarket",
                "ts": now,
            })
        except Exception:
            continue
    out.sort(key=lambda x: x.get("volume_24h", 0.0), reverse=True)
    out = out[:top_n]
    _cache["ts"] = now
    _cache["data"] = out
    return out


def _map_to_sector(question_lower: str) -> List[str]:
    """Heuristic: keyword → sector ETF list."""
    m: List[str] = []
    kw = {
        "XLF": ["bank", "fed", "rate", "interest", "regulator"],
        "XLE": ["oil", "gas", "energy", "opec", "saudi", "pipeline"],
        "XLK": ["tech", "antitrust", "ai", "chip", "semiconductor"],
        "XLV": ["health", "fda", "drug", "medicare", "biotech"],
        "XLI": ["infra", "defense", "military", "boeing", "lockheed"],
        "XLB": ["mining", "metal", "commodity", "trade war"],
        "XLY": ["consumer", "tariff", "amazon"],
        "XLP": ["food", "staple", "procter"],
        "XLRE": ["real estate", "housing", "mortgage"],
        "XLU": ["utility", "power", "grid", "climate"],
        "XLC": ["media", "social", "speech", "meta", "google"],
        "SPY": ["election", "president", "congress", "geopolitic", "war"],
    }
    for etf, words in kw.items():
        if any(w in question_lower for w in words):
            m.append(etf)
    return m or ["SPY"]


if __name__ == "__main__":
    os.environ.setdefault("USE_POLYMARKET", "1")
    evts = fetch_live_political_events()
    print(f"fetched {len(evts)} events")
    for e in evts[:5]:
        print(f"  vol=${e['volume_24h']:>12,.0f}  yes={e['yes_price']:.2f}  "
              f"sector={e['sector_map']}  q={e['question'][:60]}")
