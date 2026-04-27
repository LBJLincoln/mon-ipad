#!/usr/bin/env python3
"""Build per-(team, date) position breakdown from box-scores active rosters.

For each game, group active players by position (PG/SG/SF/PF/C — derived from
the 'pos' field in box-scores) and compute leakage-safe rolling stats up to
(but not including) game date for each position bucket.

Output: data/karpathy/position_data.json keyed by f"{team}|{date}":
  {pos_pg_rating, pos_pg_minutes_share, pos_pg_plus_minus, pos_pg_usage,
   pos_pg_ts_pct, pos_pg_def_rating, ...same for sg/sf/pf/c}

Used by engine cat 26b position breakdown features (40 dead columns → alive).
NB: NBA box-scores only have 1-letter pos codes (G/F/C). We split G→PG/SG and
F→SF/PF using minutes-rank: top G = PG, second G = SG; top F = SF, second F = PF.

Usage: python3 scripts/ops/build_position_data.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parents[2]
BOX = REPO / "data" / "box-scores-2025-26.json"
OUT = REPO / "data" / "karpathy" / "position_data.json"

POS_ORDER = ["pg", "sg", "sf", "pf", "c"]


def assign_positions(active: list) -> dict:
    """Map each player in active roster to a fine-grained position slot.

    NBA box-scores have pos in {'G','F','C',''}. We split:
      G = guard pool sorted by minutes desc → PG (top), SG (rest)
      F = forward pool sorted by minutes desc → SF (top), PF (rest)
      C = center
    Returns {player_name: pos_slot}.
    """
    guards = [p for p in active if p.get("pos") == "G"]
    forwards = [p for p in active if p.get("pos") == "F"]
    centers = [p for p in active if p.get("pos") == "C"]
    untyped = [p for p in active if p.get("pos") not in ("G", "F", "C")]

    guards.sort(key=lambda p: -p.get("min", 0))
    forwards.sort(key=lambda p: -p.get("min", 0))

    out = {}
    if guards:
        out[guards[0]["name"]] = "pg"
        for p in guards[1:]:
            out[p["name"]] = "sg"
    if forwards:
        out[forwards[0]["name"]] = "sf"
        for p in forwards[1:]:
            out[p["name"]] = "pf"
    for p in centers:
        out[p["name"]] = "c"
    # Untyped go to their best-fit bucket by minutes — assign as bench-tier sg/pf
    for p in untyped:
        out[p["name"]] = "sg" if p.get("min", 0) > 15 else "pf"
    return out


def main() -> int:
    box = json.loads(BOX.read_text())

    # Index team-games chronologically
    rows = []
    for gid, g in box.items():
        date = g.get("date") or ""
        if not date:
            continue
        for team_key, active_key in [("home", "active_home"), ("away", "active_away")]:
            team = g.get(team_key) or ""
            active = g.get(active_key) or []
            if not (team and active):
                continue
            rows.append({"gid": gid, "date": date, "team": team, "active": active})
    rows.sort(key=lambda r: (r["date"], r["gid"]))
    print(f"indexed {len(rows)} team-games", file=sys.stderr)

    # Per-team per-position rolling history
    # team_pos_history[team][pos] = list of {min, pts, reb, ast, plus_minus}
    team_pos_history: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    out = {}
    for r in rows:
        team = r["team"]
        date = r["date"]
        active = r["active"]
        slots = assign_positions(active)

        # Compute prior-history aggregates per position before this game
        pos_stats = {}
        team_total_min = sum(sum(s["min"] for s in lst)
                              for lst in team_pos_history[team].values()) or 1.0

        for pos in POS_ORDER:
            hist = team_pos_history[team][pos]
            if not hist:
                pos_stats[pos] = {
                    "rating": 0.0, "minutes_share": 0.2, "plus_minus": 0.0,
                    "usage": 0.2, "ts_pct": 0.55, "def_rating": 110.0,
                }
                continue
            n = len(hist)
            tot_min = sum(s["min"] for s in hist)
            tot_pts = sum(s["pts"] for s in hist)
            tot_reb = sum(s["reb"] for s in hist)
            tot_ast = sum(s["ast"] for s in hist)
            avg_min = tot_min / n if n else 0
            # rating proxy: ppg * 1.0 + ast * 0.7 + reb * 0.4 (PER-style) / 30
            rating = ((tot_pts + tot_ast * 0.7 + tot_reb * 0.4) / n) / 30.0 if n else 0.0
            min_share = tot_min / team_total_min if team_total_min > 0 else 0.2
            # usage proxy: pts share within the position bucket
            usage = tot_pts / (tot_pts + tot_ast * 0.5 + 1.0) if (tot_pts + tot_ast) > 0 else 0.2
            # ts_pct proxy: pts per minute scaled to 0-1 ~ ts%
            ts_pct = min(0.75, max(0.40, 0.50 + (tot_pts / max(tot_min, 1)) / 5.0))
            # def_rating proxy: more rebounds + minutes + lower opp pts → lower drtg
            def_rating = max(95.0, 115.0 - tot_reb / max(n, 1) * 0.5)
            # plus_minus proxy: 0 (need explicit pm in box-scores; we don't track yet)
            plus_minus = 0.0
            pos_stats[pos] = {
                "rating": round(rating, 4),
                "minutes_share": round(min_share, 4),
                "plus_minus": round(plus_minus, 4),
                "usage": round(usage, 4),
                "ts_pct": round(ts_pct, 4),
                "def_rating": round(def_rating, 2),
            }

        # Save flat dict matching engine expectations
        key = f"{team}|{date}"
        out[key] = {f"pos_{pos}_{stat}": v for pos, stats in pos_stats.items() for stat, v in stats.items()}

        # Update history with THIS game's contributions per position
        for p in active:
            n = p.get("name") or ""
            if not n:
                continue
            slot = slots.get(n, "sg")
            team_pos_history[team][slot].append({
                "min": p.get("min", 0) or 0,
                "pts": p.get("pts", 0) or 0,
                "reb": p.get("reb", 0) or 0,
                "ast": p.get("ast", 0) or 0,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=None))
    sz_kb = OUT.stat().st_size / 1024
    sample_key = list(out.keys())[100] if out else None
    print(f"wrote {len(out)} (team,date) entries to {OUT.name} ({sz_kb:.1f} KB)", file=sys.stderr)
    if sample_key:
        sample = out[sample_key]
        n_keys = len(sample)
        print(f"  features per key: {n_keys}, sample key: {sample_key}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
