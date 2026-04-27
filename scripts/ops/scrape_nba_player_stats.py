#!/usr/bin/env python3
"""Per-team top players (real, from LeagueDashPlayerStats), enriching star metadata.

Output: data/karpathy/player_top_data.json keyed by team_abbr:
  {top1_pts, top1_reb, top1_ast, top1_min, top1_usg, top1_per,
   top2_..., top3_..., top4_..., top5_...}
All from API LeagueDashPlayerStats season 2024-25.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "player_top_data.json"

NBA_TEAMS_BY_ID = {
    "1610612737":"ATL","1610612738":"BOS","1610612751":"BKN","1610612766":"CHA",
    "1610612741":"CHI","1610612739":"CLE","1610612742":"DAL","1610612743":"DEN",
    "1610612765":"DET","1610612744":"GSW","1610612745":"HOU","1610612754":"IND",
    "1610612746":"LAC","1610612747":"LAL","1610612763":"MEM","1610612748":"MIA",
    "1610612749":"MIL","1610612750":"MIN","1610612740":"NOP","1610612752":"NYK",
    "1610612760":"OKC","1610612753":"ORL","1610612755":"PHI","1610612756":"PHX",
    "1610612757":"POR","1610612758":"SAC","1610612759":"SAS","1610612761":"TOR",
    "1610612762":"UTA","1610612764":"WAS",
}


def main() -> int:
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
    except ImportError:
        return 2
    SEASON = "2024-25"
    out = {tabbr: {} for tabbr in NBA_TEAMS_BY_ID.values()}

    for measure_type, prefix in [("Base", "base"), ("Advanced", "adv")]:
        try:
            d = leaguedashplayerstats.LeagueDashPlayerStats(
                season=SEASON, measure_type_detailed_defense=measure_type,
                per_mode_detailed="PerGame",
            ).get_dict()
            rs = d.get("resultSets", [{}])[0]
            h = rs.get("headers", []); rows = rs.get("rowSet", [])
            idx = {n: h.index(n) for n in h}
            # Group by team
            from collections import defaultdict
            by_team = defaultdict(list)
            for r in rows:
                tid = str(r[idx.get("TEAM_ID", 0)])
                by_team[tid].append(r)
            for tid, plist in by_team.items():
                tabbr = NBA_TEAMS_BY_ID.get(tid)
                if not tabbr:
                    continue
                # Sort by minutes per game
                plist.sort(key=lambda x: -float(x[idx.get("MIN", 0)] or 0))
                for rank, p in enumerate(plist[:5], start=1):
                    if measure_type == "Base":
                        out[tabbr][f"top{rank}_pts"] = float(p[idx.get("PTS", 0)] or 0)
                        out[tabbr][f"top{rank}_reb"] = float(p[idx.get("REB", 0)] or 0)
                        out[tabbr][f"top{rank}_ast"] = float(p[idx.get("AST", 0)] or 0)
                        out[tabbr][f"top{rank}_min"] = float(p[idx.get("MIN", 0)] or 0)
                        out[tabbr][f"top{rank}_fg_pct"] = float(p[idx.get("FG_PCT", 0)] or 0)
                        out[tabbr][f"top{rank}_fg3_pct"] = float(p[idx.get("FG3_PCT", 0)] or 0)
                        out[tabbr][f"top{rank}_plus_minus"] = float(p[idx.get("PLUS_MINUS", 0)] or 0)
                    elif measure_type == "Advanced":
                        if "USG_PCT" in idx: out[tabbr][f"top{rank}_usg"] = float(p[idx["USG_PCT"]] or 0.20)
                        if "TS_PCT" in idx: out[tabbr][f"top{rank}_ts"] = float(p[idx["TS_PCT"]] or 0.55)
                        if "OFF_RATING" in idx: out[tabbr][f"top{rank}_off_rtg"] = float(p[idx["OFF_RATING"]] or 110)
                        if "DEF_RATING" in idx: out[tabbr][f"top{rank}_def_rtg"] = float(p[idx["DEF_RATING"]] or 110)
            print(f"  {measure_type}: ok", file=sys.stderr)
        except Exception as e:
            print(f"  {measure_type} err: {str(e)[:100]}", file=sys.stderr)
        time.sleep(0.6)

    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
