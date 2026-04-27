#!/usr/bin/env python3
"""Build per-(team, date) travel/timezone data from games file + arena coords.

For each team's game on date D, computes:
  - travel_distance: haversine miles from prior game's host arena
  - timezone_change: hours of TZ shift vs prior game
  - b2b_travel: 1 if game N-1 was yesterday AND distance > 500mi
  - tz_disadvantage: |timezone_change| weighted by direction (east > west penalty)
  - days_since_last_game

Output: data/karpathy/travel_data.json keyed by f"{team}|{date}".
"""
from __future__ import annotations
import json, sys, math
from pathlib import Path
from collections import defaultdict
from datetime import datetime

REPO = Path(__file__).resolve().parents[2]
GAMES = REPO.parent / "nomos-nba-agent" / "data" / "historical" / "games-2025-26.json"
OUT = REPO / "data" / "karpathy" / "travel_data.json"

# NBA arena lat, lon, timezone offset (UTC hrs)
ARENAS = {
    "ATL": (33.7573, -84.3963, -5), "BOS": (42.3662, -71.0621, -5),
    "BKN": (40.6826, -73.9754, -5), "CHA": (35.2251, -80.8392, -5),
    "CHI": (41.8807, -87.6742, -6), "CLE": (41.4965, -81.6882, -5),
    "DAL": (32.7905, -96.8103, -6), "DEN": (39.7487, -105.0078, -7),
    "DET": (42.3411, -83.0553, -5), "GSW": (37.7681, -122.3878, -8),
    "HOU": (29.7508, -95.3621, -6), "IND": (39.7639, -86.1555, -5),
    "LAC": (34.0430, -118.2673, -8), "LAL": (34.0430, -118.2673, -8),
    "MEM": (35.1382, -90.0506, -6), "MIA": (25.7814, -80.1870, -5),
    "MIL": (43.0451, -87.9173, -6), "MIN": (44.9795, -93.2761, -6),
    "NOP": (29.9489, -90.0820, -6), "NYK": (40.7505, -73.9934, -5),
    "OKC": (35.4634, -97.5151, -6), "ORL": (28.5392, -81.3839, -5),
    "PHI": (39.9012, -75.1719, -5), "PHX": (33.4457, -112.0712, -7),
    "POR": (45.5316, -122.6668, -8), "SAC": (38.5802, -121.4998, -8),
    "SAS": (29.4271, -98.4375, -6), "TOR": (43.6435, -79.3791, -5),
    "UTA": (40.7683, -111.9011, -7), "WAS": (38.8981, -77.0209, -5),
}


def haversine(lat1, lon1, lat2, lon2):
    R = 3959.0  # earth radius miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def main() -> int:
    games_raw = json.loads(GAMES.read_text())
    games = games_raw.get("games", games_raw) if isinstance(games_raw, dict) else games_raw

    rows = []
    for g in games:
        gid = g.get("game_id", "")
        if not gid or gid.startswith("001"):
            continue
        date = (g.get("game_date") or "")[:10]
        h = (g.get("home", {}) or {}).get("team_abbr", "") if isinstance(g.get("home"), dict) else ""
        a = (g.get("away", {}) or {}).get("team_abbr", "") if isinstance(g.get("away"), dict) else ""
        if not (date and h and a):
            continue
        # Each game = home team plays AT home, away team TRAVELED to home arena
        rows.append({"date": date, "team": h, "host": h, "side": "home"})
        rows.append({"date": date, "team": a, "host": h, "side": "away"})
    rows.sort(key=lambda r: (r["date"], r["team"]))

    last_game: dict[str, dict] = {}  # team → most recent {date, host}
    out = {}
    for r in rows:
        team = r["team"]
        date = r["date"]
        host = r["host"]
        cur_lat, cur_lon, cur_tz = ARENAS.get(host, (39.0, -98.0, -6))

        prev = last_game.get(team)
        if prev:
            p_host = prev["host"]
            p_lat, p_lon, p_tz = ARENAS.get(p_host, (39.0, -98.0, -6))
            dist = haversine(p_lat, p_lon, cur_lat, cur_lon)
            tz_change = cur_tz - p_tz
            d_prev = datetime.strptime(prev["date"], "%Y-%m-%d")
            d_cur = datetime.strptime(date, "%Y-%m-%d")
            days_since = (d_cur - d_prev).days
            b2b_travel = 1.0 if (days_since == 1 and dist > 500) else 0.0
            # east-bound travel is harder than west (jet-lag penalty asymmetry)
            tz_disadvantage = max(0.0, tz_change) * 1.2 + abs(min(0.0, tz_change)) * 0.7
        else:
            dist = 0.0
            tz_change = 0.0
            days_since = 5.0
            b2b_travel = 0.0
            tz_disadvantage = 0.0

        out[f"{team}|{date}"] = {
            "travel_distance": round(dist, 1),
            "timezone_change": float(tz_change),
            "tz_disadvantage": round(tz_disadvantage, 3),
            "b2b_travel": float(b2b_travel),
            "days_since_last_game": float(days_since),
        }
        last_game[team] = {"date": date, "host": host}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=None))
    n_b2b = sum(1 for v in out.values() if v["b2b_travel"] > 0)
    n_far = sum(1 for v in out.values() if v["travel_distance"] > 1000)
    print(f"wrote {len(out)} (team,date) entries", file=sys.stderr)
    print(f"  b2b travel games: {n_b2b}", file=sys.stderr)
    print(f"  long-haul (>1000mi): {n_far}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
