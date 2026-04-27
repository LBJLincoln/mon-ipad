#!/usr/bin/env python3
"""Scrape NBA tracking stats via LeagueDashPtStats (free nba_api endpoint).

Per-team season-aggregated tracking: shot_contest, deflections, paint touches,
hustle, screen assists, etc. Applied as static prior-season values for
leakage-safe baselines (2024-25 → 2025-26).

Output: data/karpathy/tracking_data.json keyed by team_abbr:
  {shot_contest_rate, deflections_per_game, paint_pts, fb_pts}

Usage: python3 scripts/ops/scrape_nba_tracking.py
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "tracking_data.json"

NBA_TEAMS_BY_ID = {
    "1610612737": "ATL", "1610612738": "BOS", "1610612751": "BKN", "1610612766": "CHA",
    "1610612741": "CHI", "1610612739": "CLE", "1610612742": "DAL", "1610612743": "DEN",
    "1610612765": "DET", "1610612744": "GSW", "1610612745": "HOU", "1610612754": "IND",
    "1610612746": "LAC", "1610612747": "LAL", "1610612763": "MEM", "1610612748": "MIA",
    "1610612749": "MIL", "1610612750": "MIN", "1610612740": "NOP", "1610612752": "NYK",
    "1610612760": "OKC", "1610612753": "ORL", "1610612755": "PHI", "1610612756": "PHX",
    "1610612757": "POR", "1610612758": "SAC", "1610612759": "SAS", "1610612761": "TOR",
    "1610612762": "UTA", "1610612764": "WAS",
}


def main() -> int:
    try:
        from nba_api.stats.endpoints import leaguedashteamstats, leaguedashptstats
    except ImportError:
        print("nba_api missing", file=sys.stderr)
        return 2

    SEASON = "2024-25"
    out = {tabbr: {} for tabbr in NBA_TEAMS_BY_ID.values()}

    # Hustle stats — separate endpoint
    try:
        from nba_api.stats.endpoints import leaguehustlestatsteam
        hustle = leaguehustlestatsteam.LeagueHustleStatsTeam(season=SEASON).get_dict()
        rs = hustle.get("resultSets", [{}])[0]
        headers = rs.get("headers", [])
        rows = rs.get("rowSet", [])
        tid_idx = headers.index("TEAM_ID")
        gp_idx = headers.index("GP") if "GP" in headers else None
        try:
            cs_idx = headers.index("CONTESTED_SHOTS")
        except ValueError:
            cs_idx = None
        try:
            def_idx = headers.index("DEFLECTIONS")
        except ValueError:
            def_idx = None
        for r in rows:
            tid = str(r[tid_idx])
            tabbr = NBA_TEAMS_BY_ID.get(tid)
            if not tabbr:
                continue
            gp = float(r[gp_idx] or 1) if gp_idx is not None else 82.0
            out[tabbr]["shot_contest_rate"] = (float(r[cs_idx] or 0) / gp) if cs_idx is not None else 30.0
            out[tabbr]["deflections_per_game"] = (float(r[def_idx] or 0) / gp) if def_idx is not None else 12.0
        print(f"hustle: {sum(1 for v in out.values() if 'shot_contest_rate' in v)} teams", file=sys.stderr)
    except Exception as e:
        print(f"hustle endpoint err: {e}", file=sys.stderr)

    # Paint/FB pts via LeagueDashTeamStats Scoring
    try:
        ts = leaguedashteamstats.LeagueDashTeamStats(
            season=SEASON, measure_type_detailed_defense="Scoring", per_mode_detailed="PerGame",
        ).get_dict()
        rs = ts.get("resultSets", [{}])[0]
        headers = rs.get("headers", [])
        rows = rs.get("rowSet", [])
        tid_idx = headers.index("TEAM_ID")
        # PTS_PAINT or PCT_PTS_PAINT
        paint_idx = headers.index("PCT_PTS_PAINT") if "PCT_PTS_PAINT" in headers else None
        fb_idx = headers.index("PCT_PTS_FB") if "PCT_PTS_FB" in headers else None
        for r in rows:
            tid = str(r[tid_idx])
            tabbr = NBA_TEAMS_BY_ID.get(tid)
            if not tabbr:
                continue
            out[tabbr]["paint_pts_pct"] = float(r[paint_idx] or 0) if paint_idx is not None else 0.45
            out[tabbr]["fb_pts_pct"] = float(r[fb_idx] or 0) if fb_idx is not None else 0.13
        print(f"scoring: {sum(1 for v in out.values() if 'paint_pts_pct' in v)} teams", file=sys.stderr)
    except Exception as e:
        print(f"scoring endpoint err: {e}", file=sys.stderr)

    # Defaults for missing
    for tabbr, v in out.items():
        v.setdefault("shot_contest_rate", 30.0)
        v.setdefault("deflections_per_game", 12.0)
        v.setdefault("paint_pts_pct", 0.45)
        v.setdefault("fb_pts_pct", 0.13)
        v.setdefault("perimeter_defense", 0.5)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
