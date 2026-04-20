"""Cross-repo context bus — merges NBA + POL + PQTF + quote state.

ITF agents call build_intraday_context() each tick to get a single dict
they can inject into their LLM prompts.

Philosophy: read-only, best-effort. If a source file is missing we skip it
rather than fail. Every ITF agent sees the same context.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .quote_bus import latest as quote_latest

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data"

# In-process caches (module-scoped). Intentionally cheap — every tick re-evals staleness.
_NEWS_CACHE: Dict[str, Any] = {"ts": 0, "items": []}
_POLY_CACHE: Dict[str, Any] = {"ts": 0, "items": []}
_NEWS_TTL_S = 300    # 5 min — matches tick cadence
_POLY_TTL_S = 900    # 15 min — Polymarket markets change slower


def _read_json(p: Path) -> Any:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _top_nba_edges(n: int = 5) -> List[Dict[str, Any]]:
    """Pull top-N highest-edge NBA games from the most recent predictions file."""
    # Prefer explicit latest pred file, then the t1-science track, then nba-fleet.
    candidates = [
        DATA / "arena" / "model-predictions-latest.json",
        DATA / "arena" / "nba-arena-full-season.json",
    ]
    for p in candidates:
        body = _read_json(p)
        if not body:
            continue
        games = body.get("games") or body.get("predictions") or []
        if not isinstance(games, list) or not games:
            continue
        scored: List[Dict[str, Any]] = []
        for g in games[:200]:
            edge = g.get("edge_pct") or g.get("edge") or g.get("max_edge") or 0
            scored.append({
                "game_key": g.get("game_key") or g.get("id") or "?",
                "home": g.get("home") or g.get("home_team") or "?",
                "away": g.get("away") or g.get("away_team") or "?",
                "edge_pct": float(edge or 0),
                "pick": g.get("pick") or g.get("direction") or "?",
            })
        scored.sort(key=lambda x: -abs(x["edge_pct"]))
        return scored[:n]
    return []


def _top_pol_signals(n: int = 5) -> List[Dict[str, Any]]:
    """Pull top-N political events from POL TF analytics / fleet status."""
    analytics = DATA / "tf-analytics" / "pol"
    if analytics.exists():
        days = sorted(analytics.glob("day-*.json"))
        if days:
            body = _read_json(days[-1])
            if body and isinstance(body, dict):
                events = body.get("events") or body.get("signals") or []
                if events:
                    return [
                        {"event": e.get("title") or e.get("event") or "?",
                         "sector_etf": e.get("sector_etf") or e.get("etf") or "",
                         "strength": float(e.get("strength") or e.get("score") or 0)}
                        for e in events[:n]
                    ]
    # Fallback: surface pol fleet best brier as a single "signal"
    pol = _read_json(DATA / "political-fleet-status.json")
    if pol and pol.get("fleet_best"):
        fb = pol["fleet_best"]
        return [{
            "event": f"POL fleet best: {fb.get('island')} brier={fb.get('brier')}",
            "sector_etf": "",
            "strength": 0.0,
        }]
    return []


def _pqtf_state() -> Dict[str, Any]:
    """Pull latest PQTF bankroll + open-position snapshot."""
    analytics = DATA / "tf-analytics" / "pqtf"
    if analytics.exists():
        days = sorted(analytics.glob("day-*.json"))
        if days:
            body = _read_json(days[-1])
            if body:
                return {
                    "last_day": body.get("date") or days[-1].stem,
                    "fleet_bankroll": body.get("fleet_bankroll") or body.get("bankroll_total"),
                    "open_positions": body.get("open_positions") or [],
                }
    return {}


def _nba_fleet_summary() -> Dict[str, Any]:
    fs = _read_json(DATA / "nba-fleet-status.json") or {}
    return {
        "fleet_best_brier": fs.get("fleet_best_brier"),
        "fleet_best_island": fs.get("fleet_best_island"),
    }


def _alpaca_news(symbols: List[str], limit: int = 20) -> List[Dict[str, Any]]:
    """Pull live news from Alpaca /v1beta1/news. Free with paper keys, 200 req/min cap.

    Returns list of {headline, summary, symbols, created_at, source}.
    Cached for _NEWS_TTL_S to avoid hammering the endpoint on sub-5-min ticks.
    """
    now = time.time()
    if now - _NEWS_CACHE.get("ts", 0) < _NEWS_TTL_S and _NEWS_CACHE.get("items"):
        return _NEWS_CACHE["items"]

    key = os.environ.get("ALPACA_PAPER_KEY")
    sec = os.environ.get("ALPACA_PAPER_SECRET")
    if not key or not sec or not symbols:
        return []

    try:
        import requests
        r = requests.get(
            "https://data.alpaca.markets/v1beta1/news",
            params={"symbols": ",".join(symbols[:20]), "limit": limit, "sort": "desc"},
            headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec},
            timeout=6,
        )
        r.raise_for_status()
        news = r.json().get("news") or []
        items = [
            {
                "headline": (n.get("headline") or "")[:180],
                "summary": (n.get("summary") or "")[:220],
                "symbols": (n.get("symbols") or [])[:5],
                "created_at": n.get("created_at"),
                "source": n.get("source"),
            }
            for n in news[:limit]
        ]
        _NEWS_CACHE["ts"] = now
        _NEWS_CACHE["items"] = items
        return items
    except Exception:
        return _NEWS_CACHE.get("items", [])


def _polymarket_events(limit: int = 10) -> List[Dict[str, Any]]:
    """Pull top-volume active Polymarket binary markets. No auth required.

    Returns [{question, probability, volume_24h, end_date}] sorted by 24h volume.
    Cached for _POLY_TTL_S since market lists shift slowly.
    """
    now = time.time()
    if now - _POLY_CACHE.get("ts", 0) < _POLY_TTL_S and _POLY_CACHE.get("items"):
        return _POLY_CACHE["items"]

    try:
        import requests
        r = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"limit": 50, "order": "volume24hr", "ascending": "false",
                    "active": "true", "closed": "false"},
            timeout=6,
        )
        r.raise_for_status()
        raw = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
        items: List[Dict[str, Any]] = []
        for m in raw[:limit]:
            probs: List[float] = []
            try:
                # Polymarket encodes YES/NO prices in outcomePrices as a JSON string.
                prices = json.loads(m.get("outcomePrices") or "[]") if isinstance(m.get("outcomePrices"), str) else (m.get("outcomePrices") or [])
                probs = [float(p) for p in prices if p not in (None, "")]
            except Exception:
                pass
            items.append({
                "question": (m.get("question") or "")[:160],
                "yes_prob": probs[0] if probs else None,
                "volume_24h": m.get("volume24hr") or m.get("volume24Hr"),
                "end_date": m.get("endDate") or m.get("end_date"),
            })
        _POLY_CACHE["ts"] = now
        _POLY_CACHE["items"] = items
        return items
    except Exception:
        return _POLY_CACHE.get("items", [])


def build_intraday_context() -> Dict[str, Any]:
    """Single dict ITF agents see in their prompt each tick."""
    quotes = quote_latest() or {}
    tickers_map = quotes.get("tickers") or {}
    # Build symbol list for Alpaca News — strip crypto slashes (Alpaca news is equity-indexed)
    news_syms = [t for t in tickers_map.keys() if "/" not in t and not t.startswith("^")][:20]
    return {
        "quotes_ts": quotes.get("ts"),
        "quotes_source": quotes.get("_source"),
        "quotes": tickers_map,
        "nba_top_edges": _top_nba_edges(5),
        "nba_fleet": _nba_fleet_summary(),
        "pol_top_signals": _top_pol_signals(5),
        "pqtf_state": _pqtf_state(),
        "live_news": _alpaca_news(news_syms, limit=15),
        "polymarket_events": _polymarket_events(limit=8),
    }


if __name__ == "__main__":
    import json as _json
    ctx = build_intraday_context()
    print(_json.dumps(ctx, indent=2, default=str)[:1500])
