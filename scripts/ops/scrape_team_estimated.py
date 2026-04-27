#!/usr/bin/env python3
"""TeamEstimatedMetrics — official NBA team estimated ratings.

Pulls offensive/defensive rating estimates, EFG%, pace, etc. — official advanced
metrics from NBA stats. Real API.

Output: data/karpathy/team_est_data.json keyed by team_abbr.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "team_est_data.json"

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
        from nba_api.stats.endpoints import teamestimatedmetrics
    except ImportError:
        return 2
    SEASON = "2024-25"
    out = {tabbr: {} for tabbr in NBA_TEAMS_BY_ID.values()}
    try:
        d = teamestimatedmetrics.TeamEstimatedMetrics(season=SEASON).get_dict()
        rs = d.get("resultSet", {})
        h = rs.get("headers", []); rows = rs.get("rowSet", [])
        idx = {n: h.index(n) for n in h}
        for r in rows:
            tid = str(r[idx.get("TEAM_ID", 0)])
            tabbr = NBA_TEAMS_BY_ID.get(tid)
            if not tabbr:
                continue
            for col in ("E_OFF_RATING", "E_DEF_RATING", "E_NET_RATING", "E_PACE", "E_AST_RATIO",
                        "E_OREB_PCT", "E_DREB_PCT", "E_REB_PCT", "E_TM_TOV_PCT", "E_USG_PCT",
                        "OFF_RATING_RANK", "DEF_RATING_RANK", "PACE_RANK"):
                if col in idx:
                    val = r[idx[col]]
                    out[tabbr][f"est_{col.lower()}"] = float(val) if val is not None else 0.0
        print(f"team_est: {sum(1 for v in out.values() if v)} teams", file=sys.stderr)
    except Exception as e:
        print(f"err: {e}", file=sys.stderr)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
