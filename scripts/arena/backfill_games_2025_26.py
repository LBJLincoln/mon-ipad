#!/usr/bin/env python3
"""
BACKFILL NBA GAMES — all 8 historical seasons × (Regular Season + Playoffs)
=============================================================================
Pulls every game from NBA API (leaguegamefinder) for every season we keep on
disk and merges any missing rows into:
    mon-ipad/nba-quant-space/data/historical/games-<season>.json
    nomos-nba-agent/data/historical/games-<season>.json

Motivation: the backtest engine only sees games from `games-2025-26.json`, and
that file stopped updating on 2026-03-15 — so we had 179 real prospective
predictions (2026-03-16 → 2026-04-05) with no outcomes to grade them against.
Same gap likely exists on older seasons (playoffs missing, recent weeks
missing), so we sweep all 8 seasons + both season types.

The script is idempotent — games already present (same game_id) are skipped.

Rate-limiting: NBA Stats API needs a polite 1s between requests. With 8
seasons × 2 season types = 16 calls, total fetch time ≈ 16-30s.

Usage:
  python3 scripts/arena/backfill_games_2025_26.py                  # merge missing
  python3 scripts/arena/backfill_games_2025_26.py --dry-run        # preview only
  python3 scripts/arena/backfill_games_2025_26.py --season 2025-26 # single season
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from nba_api.stats.endpoints import leaguegamefinder

MON_ROOT = Path("/home/termius/mon-ipad/nba-quant-space/data/historical")
NBA_ROOT = Path("/home/termius/nomos-nba-agent/data/historical")

SEASONS = [
    "2017-18", "2018-19", "2019-20", "2020-21", "2021-22",
    "2022-23", "2023-24", "2024-25", "2025-26",
]
SEASON_TYPES = ["Regular Season", "Playoffs"]
RATE_LIMIT_SEC = 1.0


def fetch_season(season: str, season_type: str):
    """Fetch all game rows for a given season+type. Returns empty df on error."""
    try:
        gf = leaguegamefinder.LeagueGameFinder(
            season_nullable=season,
            season_type_nullable=season_type,
            league_id_nullable="00",
            timeout=60,
        )
        return gf.get_data_frames()[0]
    except Exception as e:
        print(f"  [err] {season} {season_type}: {e}")
        return None


def pair_rows(df, season: str = "") -> dict:
    """Group the 2 rows per game into {game_id: {home: row, away: row, ...}}."""
    games = {}
    if df is None or len(df) == 0:
        return games
    for _, r in df.iterrows():
        gid = str(r["GAME_ID"])
        matchup = r["MATCHUP"]
        is_home = "vs." in matchup
        side = "home" if is_home else "away"
        if gid not in games:
            games[gid] = {
                "game_id": gid,
                "season": season or "",
                "game_date": r["GAME_DATE"],
                "matchup": matchup,
            }
        games[gid][side] = {
            "team_id": str(r["TEAM_ID"]),
            "team_abbr": r["TEAM_ABBREVIATION"],
            "team_name": r["TEAM_NAME"],
            "wl": r["WL"],
            "pts": float(r["PTS"]) if r["PTS"] is not None else None,
            "fg_pct": float(r["FG_PCT"]) if r["FG_PCT"] is not None else None,
            "fg3_pct": float(r["FG3_PCT"]) if r["FG3_PCT"] is not None else None,
            "ft_pct": float(r["FT_PCT"]) if r["FT_PCT"] is not None else None,
            "reb": float(r["REB"]) if r["REB"] is not None else None,
            "ast": float(r["AST"]) if r["AST"] is not None else None,
            "tov": float(r["TOV"]) if r["TOV"] is not None else None,
            "stl": float(r["STL"]) if r["STL"] is not None else None,
            "blk": float(r["BLK"]) if r["BLK"] is not None else None,
            "plus_minus": float(r["PLUS_MINUS"]) if r["PLUS_MINUS"] is not None else None,
        }
    # Derive home_team/away_team from matchup text once both sides are filled
    for gid, g in games.items():
        if "home" in g and "away" in g:
            g["home_team"] = g["home"]["team_abbr"]
            g["away_team"] = g["away"]["team_abbr"]
    return games


def merge_into_file(path: Path, api_games: dict, dry_run: bool = False) -> dict:
    if not path.exists():
        print(f"  [skip] {path} missing")
        return {"added": 0, "present": 0}
    raw = json.loads(path.read_text())

    # Schema detection: plain list vs {"games": [...], "metadata": {...}}
    if isinstance(raw, list):
        existing = raw
        wrapper = None
    elif isinstance(raw, dict):
        existing = raw.get("games", [])
        wrapper = raw
    else:
        print(f"  [err] {path.name}: unrecognised schema")
        return {"added": 0, "present": 0}

    existing_ids = {str(g.get("game_id")) for g in existing if isinstance(g, dict)}

    added = 0
    for gid, g in api_games.items():
        if gid in existing_ids:
            continue
        if "home" not in g or "away" not in g:
            continue
        existing.append(g)
        added += 1

    # Sort by date, then game_id for determinism
    existing.sort(key=lambda x: (x.get("game_date", ""), str(x.get("game_id", ""))))

    if wrapper is not None:
        wrapper["games"] = existing
        wrapper.setdefault("metadata", {})
        wrapper["metadata"]["last_backfill"] = datetime.utcnow().isoformat() + "Z"
        wrapper["metadata"]["total_games"] = len(existing)
        out = wrapper
    else:
        out = existing

    if dry_run:
        print(f"  [dry] {path.name}: would add {added} games (total would be {len(existing)})")
    else:
        path.write_text(json.dumps(out, indent=2))
        print(f"  [ok]  {path.name}: added {added} games, total {len(existing)}")
    return {"added": added, "present": len(existing)}


def process_season(season: str, dry_run: bool) -> dict:
    """Fetch every game for a season (regular + playoffs) and merge into both repos."""
    print(f"\n[backfill] === {season} ===")
    all_games: dict = {}
    for stype in SEASON_TYPES:
        df = fetch_season(season, stype)
        if df is None or len(df) == 0:
            print(f"  {stype}: 0 rows")
            continue
        paired = pair_rows(df, season)
        dates = [g.get("game_date", "") for g in paired.values()]
        first = min(dates) if dates else "-"
        last = max(dates) if dates else "-"
        print(f"  {stype}: {len(df)} rows -> {len(paired)} games ({first} to {last})")
        # Later entries override earlier — regular season first then playoffs
        all_games.update(paired)
        time.sleep(RATE_LIMIT_SEC)

    stats = {"season": season, "api_games": len(all_games)}
    for root in (MON_ROOT, NBA_ROOT):
        path = root / f"games-{season}.json"
        if not path.exists():
            continue
        res = merge_into_file(path, all_games, dry_run=dry_run)
        key = "mon" if "mon-ipad" in str(root) else "nba"
        stats[f"{key}_added"] = res["added"]
        stats[f"{key}_total"] = res["present"]
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--season", type=str, help="Single season (e.g. 2025-26)")
    args = ap.parse_args()

    seasons = [args.season] if args.season else SEASONS
    summary = []
    for s in seasons:
        summary.append(process_season(s, dry_run=args.dry_run))

    print("\n[backfill] Summary")
    print(f"  {'Season':<10} {'API':>6} {'mon+':>6} {'mon=':>6} {'nba+':>6} {'nba=':>6}")
    for s in summary:
        print(f"  {s['season']:<10} "
              f"{s.get('api_games', 0):>6} "
              f"{s.get('mon_added', 0):>6} "
              f"{s.get('mon_total', 0):>6} "
              f"{s.get('nba_added', 0):>6} "
              f"{s.get('nba_total', 0):>6}")
    print("[backfill] Done.")


if __name__ == "__main__":
    main()
