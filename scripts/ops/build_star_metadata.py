#!/usr/bin/env python3
"""Per-(team, date) star1/star2 metadata derived from box-scores rolling history.

Engine consumer keys (engine.py 4547-4570):
  star1_<stat>, star2_<stat> for stat in {pts, reb, ast, min}
  star_combined_pm, star_usage_concentration, star_minutes_ratio,
  star_efficiency_delta, star_rest_adj_rating
  chemistry_starting5, chemistry_top3
  bench_player_avg_rating, roster_talent_depth

Star = top 2 players by rolling minutes-per-game prior to current game.

Output: data/karpathy/star_metadata.json keyed by f"{team}|{date}".
Also adds those fields to player_data via re-merge step.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parents[2]
BOX = REPO / "data" / "box-scores-2025-26.json"
OUT = REPO / "data" / "karpathy" / "star_metadata.json"


def main() -> int:
    box = json.loads(BOX.read_text())
    rows = []
    for gid, g in box.items():
        date = g.get("date") or ""
        if not date:
            continue
        for team_key, active_key in [("home", "active_home"), ("away", "active_away")]:
            team = g.get(team_key) or ""
            if not team:
                continue
            rows.append({"date": date, "team": team, "active": g.get(active_key) or []})
    rows.sort(key=lambda r: (r["date"], r["team"]))

    # team_player_history[team][name] = {gp, total_min, total_pts, total_reb, total_ast}
    history: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(
        lambda: {"gp": 0, "min": 0.0, "pts": 0, "reb": 0, "ast": 0}))

    out = {}
    for r in rows:
        team = r["team"]
        date = r["date"]
        active = r["active"]
        active_names = {p.get("name") for p in active}
        h = history[team]
        # Rank prior players by avg_minutes among those active tonight
        active_with_history = []
        for n in active_names:
            ph = h.get(n)
            if ph and ph["gp"] > 0:
                active_with_history.append((n, ph))
        active_with_history.sort(key=lambda x: -x[1]["min"] / x[1]["gp"])
        s1 = active_with_history[0] if active_with_history else None
        s2 = active_with_history[1] if len(active_with_history) > 1 else None

        def stats(player_tuple):
            if not player_tuple:
                return {"pts": 18.0, "reb": 5.0, "ast": 4.0, "min": 30.0}
            n, ph = player_tuple
            gp = max(1, ph["gp"])
            return {
                "pts": round(ph["pts"] / gp, 2),
                "reb": round(ph["reb"] / gp, 2),
                "ast": round(ph["ast"] / gp, 2),
                "min": round(ph["min"] / gp, 2),
            }

        s1_stats = stats(s1); s2_stats = stats(s2)
        # combined plus-minus proxy: star1+star2 pts - league avg
        star_combined_pm = s1_stats["pts"] + s2_stats["pts"] - 38.0
        # usage concentration: pts share among top-2
        team_total_pts = sum(p.get("pts", 0) for p in active)
        top2_pts = (s1_stats["pts"] + s2_stats["pts"])
        star_usage_concentration = top2_pts / max(team_total_pts, 1)
        # minutes ratio: top2 minutes / 96 (max possible across 2 starters)
        star_minutes_ratio = (s1_stats["min"] + s2_stats["min"]) / 96.0
        # efficiency delta: top2 ts proxy vs league
        star_efficiency_delta = (s1_stats["pts"] / max(s1_stats["min"], 1)) + (s2_stats["pts"] / max(s2_stats["min"], 1)) - 1.2

        # bench: 6th-10th player avg pts/min
        bench_players = active_with_history[5:10] if len(active_with_history) > 5 else []
        bench_avg = 0.0
        if bench_players:
            br = []
            for n, ph in bench_players:
                if ph["min"] > 0:
                    br.append((ph["pts"] / ph["min"]) * 30.0)  # per 30min
            bench_avg = sum(br) / max(len(br), 1) if br else 0.0
        # roster_talent_depth: spread between starters and bench
        roster_talent_depth = min(1.0, len(active_with_history) / 10.0)

        # chemistry: % of last 5 games where same top-3 played together
        chemistry_top3 = 0.6  # placeholder (need lineup tracking; fallback)
        chemistry_starting5 = 0.7

        key = f"{team}|{date}"
        out[key] = {
            "star1_pts": s1_stats["pts"],
            "star1_reb": s1_stats["reb"],
            "star1_ast": s1_stats["ast"],
            "star1_min": s1_stats["min"],
            "star2_pts": s2_stats["pts"],
            "star2_reb": s2_stats["reb"],
            "star2_ast": s2_stats["ast"],
            "star2_min": s2_stats["min"],
            "star_combined_pm": round(star_combined_pm, 4),
            "star_usage_concentration": round(star_usage_concentration, 4),
            "star_minutes_ratio": round(star_minutes_ratio, 4),
            "star_efficiency_delta": round(star_efficiency_delta, 4),
            "star_rest_adj_rating": round(star_combined_pm * 0.5, 4),
            "chemistry_starting5": chemistry_starting5,
            "chemistry_top3": chemistry_top3,
            "bench_player_avg_rating": round(bench_avg, 4),
            "roster_talent_depth": round(roster_talent_depth, 4),
        }

        # Update history
        for p in active:
            n = p.get("name") or ""
            if not n:
                continue
            ph = h[n]
            ph["gp"] += 1
            ph["min"] += p.get("min", 0) or 0
            ph["pts"] += p.get("pts", 0) or 0
            ph["reb"] += p.get("reb", 0) or 0
            ph["ast"] += p.get("ast", 0) or 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=None))
    sz_kb = OUT.stat().st_size / 1024
    print(f"wrote {len(out)} (team,date) entries to {OUT.name} ({sz_kb:.1f} KB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
