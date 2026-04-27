#!/usr/bin/env python3
"""Q4 clutch stats per team via LeagueDashTeamClutch endpoint.

Engine fields filled: q4_clutch_netrtg, q4_close_win_pct (already partial),
plus new clutch_* columns.

Output: data/karpathy/clutch_data.json keyed by team_abbr.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "clutch_data.json"

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
        from nba_api.stats.endpoints import leaguedashteamclutch
    except ImportError:
        return 2
    out = {tabbr: {} for tabbr in NBA_TEAMS_BY_ID.values()}
    SEASON = "2024-25"
    try:
        c = leaguedashteamclutch.LeagueDashTeamClutch(
            season=SEASON, measure_type_detailed_defense="Advanced",
            per_mode_detailed="Per100Possessions",
            clutch_time="Last 5 Minutes", ahead_behind="Ahead or Behind",
            point_diff=5,
        ).get_dict()
        rs = c.get("resultSets", [{}])[0]
        h = rs.get("headers", []); rows = rs.get("rowSet", [])
        idx = {n: h.index(n) for n in h}
        for r in rows:
            tid = str(r[idx.get("TEAM_ID", 0)])
            tabbr = NBA_TEAMS_BY_ID.get(tid)
            if not tabbr:
                continue
            out[tabbr]["clutch_net_rating"] = float(r[idx["NET_RATING"]] or 0.0) if "NET_RATING" in idx else 0.0
            out[tabbr]["clutch_off_rating"] = float(r[idx["OFF_RATING"]] or 0.0) if "OFF_RATING" in idx else 110.0
            out[tabbr]["clutch_def_rating"] = float(r[idx["DEF_RATING"]] or 0.0) if "DEF_RATING" in idx else 110.0
            out[tabbr]["clutch_w_pct"] = float(r[idx["W_PCT"]] or 0.5) if "W_PCT" in idx else 0.5
            out[tabbr]["clutch_pace"] = float(r[idx["PACE"]] or 100.0) if "PACE" in idx else 100.0
            out[tabbr]["clutch_efg"] = float(r[idx["EFG_PCT"]] or 0.5) if "EFG_PCT" in idx else 0.5
            out[tabbr]["clutch_ts"] = float(r[idx["TS_PCT"]] or 0.55) if "TS_PCT" in idx else 0.55
        print(f"clutch (Last 5min): {sum(1 for v in out.values() if v)} teams", file=sys.stderr)
    except Exception as e:
        print(f"clutch err: {e}", file=sys.stderr)

    DEFS = {"clutch_net_rating": 0.0, "clutch_off_rating": 110.0, "clutch_def_rating": 110.0,
            "clutch_w_pct": 0.5, "clutch_pace": 100.0, "clutch_efg": 0.5, "clutch_ts": 0.55}
    for v in out.values():
        for k, dv in DEFS.items():
            v.setdefault(k, dv)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
