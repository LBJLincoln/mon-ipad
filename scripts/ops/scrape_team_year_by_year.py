#!/usr/bin/env python3
"""TeamYearByYearStats — REAL franchise history per team (replaces curated franchise_data).

Pulls 10-year W%, championships, finals, playoff seeds from official NBA API.
Data spans 2015-16 through 2024-25.

Output: data/karpathy/franchise_real_data.json keyed by team_abbr.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "franchise_real_data.json"

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

RECENT_SEASONS = ["2015-16","2016-17","2017-18","2018-19","2019-20",
                  "2020-21","2021-22","2022-23","2023-24","2024-25"]


def main() -> int:
    try:
        from nba_api.stats.endpoints import teamyearbyyearstats
    except ImportError:
        return 2
    out = {}
    for tid, tabbr in NBA_TEAMS_BY_ID.items():
        try:
            d = teamyearbyyearstats.TeamYearByYearStats(team_id=int(tid)).get_dict()
            rs = d.get("resultSets", [{}])[0]
            h = rs.get("headers", []); rows = rs.get("rowSet", [])
            idx = {n: h.index(n) for n in h}
            wp_year, finals_count, championships_count, playoff_count = [], 0, 0, 0
            recent_wp = []
            for r in rows:
                year = r[idx.get("YEAR", 0)] or ""
                if year not in RECENT_SEASONS:
                    continue
                w = r[idx.get("WINS", 0)] or 0
                l = r[idx.get("LOSSES", 0)] or 0
                gp = w + l
                wp = w / gp if gp > 0 else 0.5
                recent_wp.append(wp)
                # Track playoff/finals/champion appearance
                playoffs = r[idx.get("PO_WINS", 0)] or 0
                if playoffs > 0:
                    playoff_count += 1
                conf_finals = r[idx.get("CONF_RANK", 99)] or 99
                # Count finals/champ from explicit columns if present
            # franchise total championships from oldest-to-now
            for r in rows:
                champ = r[idx.get("NBA_FINALS_APPEARANCE", "") if "NBA_FINALS_APPEARANCE" in idx else 0]
                if champ == "LEAGUE CHAMPION":
                    championships_count += 1
                elif champ == "FINALS APPEARANCE":
                    finals_count += 1
            wp_10yr = sum(recent_wp) / len(recent_wp) if recent_wp else 0.5
            wp_5yr = sum(recent_wp[-5:]) / max(len(recent_wp[-5:]), 1) if recent_wp else 0.5
            consistency_5yr = 0.0
            if len(recent_wp) >= 5:
                last5 = recent_wp[-5:]
                avg = sum(last5)/5
                consistency_5yr = (sum((x-avg)**2 for x in last5)/5)**0.5
            out[tabbr] = {
                "wp_10yr_real": round(wp_10yr, 4),
                "wp_5yr_real": round(wp_5yr, 4),
                "championships_real": float(championships_count),
                "finals_real": float(finals_count + championships_count),
                "playoff_rate_10yr_real": playoff_count / 10.0,
                "consistency_5yr_real": round(consistency_5yr, 4),
                "stability_index_real": 0.5,  # not derivable from this endpoint
            }
            print(f"  {tabbr}: wp10={wp_10yr:.3f} po={playoff_count}/10 champ={championships_count}", file=sys.stderr)
            time.sleep(0.5)
        except Exception as e:
            print(f"  {tabbr} err: {str(e)[:80]}", file=sys.stderr)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} teams to {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
