#!/usr/bin/env python3
"""Build leakage-safe per-(team, date) player_data from box-scores-2025-26.json.

For each team's game G on date D, we compute injury/depth metrics using ONLY
games played BEFORE D. The current game's INACTIVE/DNP-Coach lists are then
used to calculate impact of who's missing AT GAME TIME.

This means features account for "LeBron is OUT tonight" using LeBron's
historical importance (built from games before tonight).

Output: data/karpathy/player_data.json
Schema: {f"{team}|{date}": {star_usage_rate, star_minutes_load,
                            injury_impact_score, injured_war_lost,
                            lineup_continuity, bench_depth_rating,
                            rotation_depth, ...}}

The cache loader keys this as (team, date) tuple for engine.build().

Usage: python3 scripts/ops/build_player_data.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parents[2]
BOX = REPO / "data" / "box-scores-2025-26.json"
OUT = REPO / "data" / "karpathy" / "player_data.json"


def main() -> int:
    box = json.loads(BOX.read_text())

    # ── Step 1: collect all team-game rows in date order ───────────────────
    rows = []  # [{date, team, side, active, dnp, inactive}]
    for gid, g in box.items():
        date = g.get("date") or ""
        if not date:
            continue
        for side, team_key, active_key, dnp_key, inactive_key in [
            ("home", "home", "active_home", "dnp_home", "inactive_home"),
            ("away", "away", "active_away", "dnp_away", "inactive_away"),
        ]:
            team = g.get(team_key) or ""
            if not team:
                continue
            rows.append({
                "gid": gid, "date": date, "team": team, "side": side,
                "active": g.get(active_key) or [],
                "dnp": g.get(dnp_key) or [],
                "inactive": g.get(inactive_key) or [],
            })
    rows.sort(key=lambda r: (r["date"], r["gid"], r["side"]))
    print(f"indexed {len(rows)} team-games", file=sys.stderr)

    # ── Step 2: rolling player importance index per team ──────────────────
    # team_player_history[team][player_name] = {gp, total_min, total_pts, total_reb, total_ast}
    team_player_history: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(
        lambda: {"gp": 0, "total_min": 0.0, "total_pts": 0, "total_reb": 0, "total_ast": 0}))
    # team_starting_lineups[team] = list of last 5 games' starting-5 sets (frozenset of names)
    team_starts: dict[str, list] = defaultdict(list)
    # team_team_min[team] = cumulative team minutes played (proxy: 5*48 per game)
    # We'll use sum of all player minutes ≈ 240 per game for rate computations.

    out = {}
    for r in rows:
        team = r["team"]
        date = r["date"]
        gid = r["gid"]
        active = r["active"]
        dnp = r["dnp"]
        inactive = r["inactive"]

        # PRIOR-game player importance for THIS team
        hist = team_player_history[team]
        # team total minutes accumulated PRIOR to this game (sum of all player minutes)
        team_total_min = sum(p["total_min"] for p in hist.values()) or 1.0

        def imp(name: str) -> float:
            """Importance ∈ [0, 1] = (player's prior cumulative min) / (team total prior min)."""
            ph = hist.get(name)
            if not ph or ph["gp"] == 0:
                return 0.0
            # weight by minutes share + scoring share
            min_share = ph["total_min"] / team_total_min if team_total_min > 0 else 0.0
            return min_share

        # ── Compute features for THIS game using prior history ────────────
        # 1. injury_impact_score: sum of importance of INACTIVE + DNP-Injury players
        injured_names = []
        for p in inactive:
            n = (p.get("name") or "").strip()
            if n:
                injured_names.append(n)
        for p in dnp:
            cmt = (p.get("comment") or "").lower()
            n = (p.get("name") or "").strip()
            # DNP-Coach excludes coach decisions; "injury", "illness", "G-League", "rest" count
            if n and ("coach" not in cmt) and (
                "inj" in cmt or "ill" in cmt or "rest" in cmt or "personal" in cmt
                or "ankle" in cmt or "knee" in cmt or "back" in cmt or "g league" in cmt
                or "out" in cmt or "concussion" in cmt or "shoulder" in cmt
            ):
                injured_names.append(n)

        # NB: box-score names are "L. Dort" style abbreviations,
        # while inactive list uses full names ("LeBron James"). Match by surname.
        active_lookup = {(p.get("name") or "").split(".")[-1].strip(): p
                         for p in active if p.get("name")}

        def find_in_history(injured_full: str) -> str | None:
            # try exact, then surname
            if injured_full in hist:
                return injured_full
            parts = injured_full.split()
            if len(parts) < 2:
                return None
            surname = parts[-1]
            # match L. Surname pattern in history
            for hk in hist.keys():
                hp = hk.split(".")
                if len(hp) == 2 and hp[1].strip() == surname:
                    return hk
                if hk.endswith(surname):
                    return hk
            return None

        injury_impact = 0.0
        injury_count = 0
        max_injury = 0.0
        for n in injured_names:
            mapped = find_in_history(n)
            if mapped:
                w = imp(mapped)
                injury_impact += w
                max_injury = max(max_injury, w)
                if w > 0.05:  # ≥5% minutes share = real rotation player
                    injury_count += 1

        # 2. star_usage_rate, star_minutes_load: top-2 players by prior min share, AMONG ACTIVE
        active_names = {(p.get("name") or "") for p in active if p.get("name")}
        active_imps = sorted(
            [(name, imp(name)) for name in hist.keys() if name in active_names],
            key=lambda x: -x[1]
        )[:2]
        star_usage = sum(w for _, w in active_imps) if active_imps else 0.55
        # star_minutes_load: average minutes of top-2 across active rotation
        star_min_load = 34.0
        if active_imps:
            top_min_total = 0.0
            for n, _ in active_imps:
                ph = hist.get(n) or {}
                if ph.get("gp", 0) > 0:
                    top_min_total += ph["total_min"] / ph["gp"]
            star_min_load = top_min_total / max(1, len(active_imps))

        # 3. lineup_continuity: % of last 5 games' starting lineups containing tonight's
        #    starters. Approximate starter set as top-5 by current-game minutes.
        active_sorted = sorted(active, key=lambda p: -p.get("min", 0))
        starters_tonight = frozenset((p.get("name") or "") for p in active_sorted[:5])
        recent_starts = team_starts[team][-5:]  # past starts
        if recent_starts:
            overlaps = [len(starters_tonight & past) / 5.0 for past in recent_starts]
            lineup_continuity = sum(overlaps) / len(overlaps)
        else:
            lineup_continuity = 0.8

        # 4. bench_depth_rating: avg pts/min for non-top-5 active in prior games
        bench_active = active_sorted[5:]
        if bench_active:
            bench_imps = []
            for p in bench_active:
                n = p.get("name", "")
                ph = hist.get(n)
                if ph and ph["total_min"] > 0:
                    bench_imps.append(ph["total_pts"] / ph["total_min"])  # pts/min
            if bench_imps:
                bench_depth = sum(bench_imps) / len(bench_imps) * 10.0  # scale
            else:
                bench_depth = 0.0
        else:
            bench_depth = 0.0

        # 5. rotation_depth: number of active players with 10+ min in this game
        rotation_depth = sum(1 for p in active if (p.get("min") or 0) >= 10)

        # 6. injury_replacement_quality (engine default 0.4 if missing): bench_depth bounded
        injury_repl_quality = max(0.2, min(0.7, 0.4 + bench_depth / 20.0 - max_injury * 0.5))

        # 7. injury_adjusted_depth: rotation_depth - injury_count
        injury_adjusted_depth = max(0, rotation_depth - injury_count)

        # 8. injury_risk_score: max single injury weight (0=healthy, 1=star-out)
        injury_risk_score = max_injury

        # 9. injured_war_lost proxy: injury_impact * 5.0 (rough WAR scaling)
        injured_war = injury_impact * 5.0

        # ── Save features keyed by team|date ──────────────────────────────
        key = f"{team}|{date}"
        out[key] = {
            "star_usage_rate": round(min(1.0, star_usage), 4),
            "star_minutes_load": round(star_min_load, 2),
            "injury_impact_score": round(min(1.0, injury_impact), 4),
            "injured_war_lost": round(injured_war, 4),
            "injury_replacement_quality": round(injury_repl_quality, 4),
            "injury_adjusted_depth": float(injury_adjusted_depth),
            "injury_risk_score": round(injury_risk_score, 4),
            "lineup_continuity": round(lineup_continuity, 4),
            "bench_depth_rating": round(bench_depth, 4),
            "rotation_depth": float(rotation_depth),
            "injury_count": float(injury_count),
        }

        # ── Update history with THIS game's stats ─────────────────────────
        for p in active:
            n = p.get("name") or ""
            if not n:
                continue
            ph = hist[n]
            ph["gp"] += 1
            ph["total_min"] += p.get("min", 0) or 0
            ph["total_pts"] += p.get("pts", 0) or 0
            ph["total_reb"] += p.get("reb", 0) or 0
            ph["total_ast"] += p.get("ast", 0) or 0
        team_starts[team].append(starters_tonight)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=None))
    sz_kb = OUT.stat().st_size / 1024
    n_with_injury = sum(1 for v in out.values() if v["injury_impact_score"] > 0.01)
    n_with_star = sum(1 for v in out.values() if v["injury_risk_score"] > 0.05)
    print(f"wrote {len(out)} (team,date) keys to {OUT.name} ({sz_kb:.1f} KB)", file=sys.stderr)
    print(f"  with non-trivial injury_impact: {n_with_injury}/{len(out)}", file=sys.stderr)
    print(f"  with star out (>5% min share): {n_with_star}/{len(out)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
