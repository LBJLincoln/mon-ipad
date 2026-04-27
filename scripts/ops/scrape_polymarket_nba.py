#!/usr/bin/env python3
"""Scrape Polymarket NBA event archive via gamma-api.polymarket.com.

For each NBA game, find the corresponding Polymarket event (matched by date +
team names), pull the close price (= market-implied home win probability), and
24h volume. Output keyed by (date, home_abbr, away_abbr).

Output: data/karpathy/polymarket_data.json keyed by f"{date}|{home}|{away}":
  {polymarket_home_prob, polymarket_volume, polymarket_line_movement_velocity}

NB: Polymarket's NBA market liquidity is sporadic — many regular-season games
have zero or tiny volume. We default to 0.5 prob + 0 volume when no match.

Usage: python3 scripts/ops/scrape_polymarket_nba.py
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import urllib.request

REPO = Path(__file__).resolve().parents[2]
GAMES_LOCAL = REPO.parent / "nomos-nba-agent" / "data" / "historical" / "games-2025-26.json"
OUT = REPO / "data" / "karpathy" / "polymarket_data.json"

GAMMA = "https://gamma-api.polymarket.com"


def http_get(url: str, timeout: int = 15) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "nomos42-research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch_nba_events(max_pages: int = 10) -> list:
    events = []
    for offset in range(0, max_pages * 100, 100):
        try:
            data = http_get(f"{GAMMA}/events?tag_slug=nba&limit=100&offset={offset}&order=startDate&ascending=false")
            if not data:
                break
            events.extend(data)
            print(f"  fetched offset {offset}: +{len(data)} events", file=sys.stderr)
            if len(data) < 100:
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"  fetch err at offset {offset}: {e}", file=sys.stderr)
            break
    return events


def main() -> int:
    games_raw = json.loads(GAMES_LOCAL.read_text())
    games = games_raw.get("games", games_raw) if isinstance(games_raw, dict) else games_raw

    print("fetching Polymarket NBA events...", file=sys.stderr)
    events = fetch_nba_events()
    print(f"total events: {len(events)}", file=sys.stderr)

    # Index events by (date, home, away) — events have markets like "Lakers vs Celtics, Nov 3"
    by_key = {}
    for e in events:
        title = (e.get("title") or "").lower()
        slug = (e.get("slug") or "").lower()
        start = (e.get("startDate") or "")[:10]
        if not start or not (title or slug):
            continue
        # Polymarket markets often have title "Will the Lakers beat the Celtics on Nov 3?"
        # We just store start date + slug for fuzzy matching
        by_key.setdefault(start, []).append({
            "title": title, "slug": slug,
            "outcome_prices": e.get("outcomes") or [],
            "volume": float(e.get("volume") or 0),
            "markets": e.get("markets") or [],
        })

    out = {}
    matched = 0
    for g in games:
        gid = g.get("game_id", "")
        if not gid or gid.startswith("001"):
            continue
        date = (g.get("game_date") or "")[:10]
        h_obj = g.get("home", {})
        a_obj = g.get("away", {})
        home = (h_obj.get("team_abbr") if isinstance(h_obj, dict) else "") or ""
        away = (a_obj.get("team_abbr") if isinstance(a_obj, dict) else "") or ""
        home_name = (h_obj.get("team_name") if isinstance(h_obj, dict) else "") or ""
        away_name = (a_obj.get("team_name") if isinstance(a_obj, dict) else "") or ""
        key = f"{date}|{home}|{away}"

        # Default: no market data
        out[key] = {
            "polymarket_home_prob": 0.5,
            "polymarket_volume": 0.0,
            "polymarket_line_movement_velocity": 0.0,
        }

        candidates = by_key.get(date, [])
        if not (home_name and away_name):
            continue
        for c in candidates:
            t = c["title"] + " " + c["slug"]
            home_words = home_name.lower().split()
            away_words = away_name.lower().split()
            if not (home_words and away_words):
                continue
            home_l = home_words[-1]  # last word, e.g. "Lakers"
            away_l = away_words[-1]
            if home_l in t and away_l in t:
                # Found a match. Try to extract home win probability from markets.
                home_prob = 0.5
                try:
                    for m in c.get("markets", []):
                        op = m.get("outcomePrices")
                        if op:
                            # outcomePrices is "[\"0.65\", \"0.35\"]" string-ish
                            if isinstance(op, str):
                                op = json.loads(op)
                            if isinstance(op, list) and len(op) >= 2:
                                home_prob = float(op[0])
                                break
                except Exception:
                    pass
                out[key] = {
                    "polymarket_home_prob": round(home_prob, 4),
                    "polymarket_volume": c["volume"],
                    "polymarket_line_movement_velocity": 0.0,  # placeholder, needs intraday history
                }
                matched += 1
                break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=None))
    print(f"wrote {len(out)} games, {matched} matched to Polymarket events", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
