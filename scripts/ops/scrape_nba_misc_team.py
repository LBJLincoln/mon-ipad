#!/usr/bin/env python3
"""LeagueDashTeamStats Misc + Defense — fouls drawn, opponent shooting,
opponent rebounding, second-chance pts.

Output: data/karpathy/misc_team_data.json keyed by team_abbr.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "misc_team_data.json"

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
        from nba_api.stats.endpoints import leaguedashteamstats
    except ImportError:
        return 2
    SEASON = "2024-25"
    out = {tabbr: {} for tabbr in NBA_TEAMS_BY_ID.values()}

    for measure_type, prefix in [("Misc", "misc"), ("Defense", "def"), ("Opponent", "opp"), ("Four Factors", "4f"), ("Advanced", "adv")]:
        try:
            d = leaguedashteamstats.LeagueDashTeamStats(
                season=SEASON, measure_type_detailed_defense=measure_type,
                per_mode_detailed="PerGame",
            ).get_dict()
            rs = d.get("resultSets", [{}])[0]
            h = rs.get("headers", []); rows = rs.get("rowSet", [])
            idx = {n: h.index(n) for n in h}
            for r in rows:
                tid = str(r[idx.get("TEAM_ID", 0)])
                tabbr = NBA_TEAMS_BY_ID.get(tid)
                if not tabbr:
                    continue
                # Pick a few high-signal columns per measure_type
                if measure_type == "Misc":
                    out[tabbr]["pts_off_tov"] = float(r[idx.get("PTS_OFF_TOV", 0)] or 0)
                    out[tabbr]["second_chance_pts"] = float(r[idx.get("PTS_2ND_CHANCE", 0)] or 0)
                    out[tabbr]["fb_pts"] = float(r[idx.get("PTS_FB", 0)] or 0)
                    out[tabbr]["paint_pts"] = float(r[idx.get("PTS_PAINT", 0)] or 0)
                    out[tabbr]["opp_pts_off_tov"] = float(r[idx.get("OPP_PTS_OFF_TOV", 0)] or 0)
                elif measure_type == "Defense":
                    if "DEF_RATING" in idx: out[tabbr]["def_rating_season"] = float(r[idx["DEF_RATING"]] or 110.0)
                    if "OPP_FG_PCT" in idx: out[tabbr]["opp_fg_pct"] = float(r[idx["OPP_FG_PCT"]] or 0.46)
                    if "OPP_FG3_PCT" in idx: out[tabbr]["opp_fg3_pct"] = float(r[idx["OPP_FG3_PCT"]] or 0.36)
                elif measure_type == "Four Factors":
                    if "EFG_PCT" in idx: out[tabbr]["efg_pct_season"] = float(r[idx["EFG_PCT"]] or 0.53)
                    if "FTA_RATE" in idx: out[tabbr]["fta_rate"] = float(r[idx["FTA_RATE"]] or 0.20)
                    if "TM_TOV_PCT" in idx: out[tabbr]["tov_pct"] = float(r[idx["TM_TOV_PCT"]] or 0.13)
                    if "OREB_PCT" in idx: out[tabbr]["oreb_pct"] = float(r[idx["OREB_PCT"]] or 0.27)
                elif measure_type == "Advanced":
                    if "PACE" in idx: out[tabbr]["pace_season"] = float(r[idx["PACE"]] or 100.0)
                    if "AST_RATIO" in idx: out[tabbr]["ast_ratio"] = float(r[idx["AST_RATIO"]] or 18.0)
                    if "OFF_RATING" in idx: out[tabbr]["off_rating_season"] = float(r[idx["OFF_RATING"]] or 110.0)
            print(f"  {measure_type}: ok", file=sys.stderr)
        except Exception as e:
            print(f"  {measure_type} err: {str(e)[:80]}", file=sys.stderr)
        time.sleep(0.6)

    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
