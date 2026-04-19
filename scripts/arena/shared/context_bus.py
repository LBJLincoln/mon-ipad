"""Cross-repo context bus — merges NBA + POL + PQTF + quote state.

ITF agents call build_intraday_context() each tick to get a single dict
they can inject into their LLM prompts.

Philosophy: read-only, best-effort. If a source file is missing we skip it
rather than fail. Every ITF agent sees the same context.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .quote_bus import latest as quote_latest

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data"


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


def build_intraday_context() -> Dict[str, Any]:
    """Single dict ITF agents see in their prompt each tick."""
    quotes = quote_latest() or {}
    return {
        "quotes_ts": quotes.get("ts"),
        "quotes_source": quotes.get("_source"),
        "quotes": quotes.get("tickers") or {},
        "nba_top_edges": _top_nba_edges(5),
        "nba_fleet": _nba_fleet_summary(),
        "pol_top_signals": _top_pol_signals(5),
        "pqtf_state": _pqtf_state(),
    }


if __name__ == "__main__":
    import json as _json
    ctx = build_intraday_context()
    print(_json.dumps(ctx, indent=2, default=str)[:1500])
