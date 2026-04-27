#!/usr/bin/env python3
"""Build leakage-safe per-game referee_data from box-scores-2025-26.json.

For each game G with crew (R1, R2, R3), we compute crew rolling stats from
ALL prior games (date < G.date) where AT LEAST ONE crew member officiated.
This is leakage-safe: only past data informs the row for game G.

Output: data/karpathy/referee_data.json
Schema: {game_id: {home_foul_bias, total_fouls_avg, foul_rate_vs_league,
                   home_ft_advantage, experience_games, over_tendency,
                   close_game_bias, tech_foul_rate, home_win_rate,
                   pace_impact}}

Usage: python3 scripts/ops/build_referee_data.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parents[2]
BOX = REPO / "data" / "box-scores-2025-26.json"
GAMES = REPO.parent / "nomos-nba-agent" / "data" / "historical" / "games-2025-26.json"
OUT = REPO / "data" / "karpathy" / "referee_data.json"


def main() -> int:
    box = json.loads(BOX.read_text())
    games_raw = json.loads(GAMES.read_text())
    games = games_raw.get("games", games_raw) if isinstance(games_raw, dict) else games_raw
    by_id = {g["game_id"]: g for g in games if "game_id" in g}

    # ── Step 1: index every game's per-crew metrics ────────────────────────
    # Per game: home/away points, home/away pts diff, total points proxy.
    # Box scores don't have foul/FT/tech counts (only per-player pts/reb/ast/min)
    # so we proxy:
    #   home_foul_bias proxy: (home_pts - away_pts at home) signed margin avg
    #   total_fouls_avg proxy: avg total points (gives pace+style proxy)
    #   foul_rate_vs_league: total_avg / league_total_avg
    #   home_ft_advantage proxy: home win rate edge in crew games
    #   over_tendency: % games with total > league avg
    #   close_game_bias: % home wins in games |margin| <= 5
    #   home_win_rate: home win rate for crew
    #   pace_impact: total_avg - league_total_avg
    # tech_foul_rate stays at constant 0.3 (no source data) — engine fallback.
    # NOTE: this is a structural improvement vs prior all-zero columns.
    #       proper foul/FT data needs nba_api StatsByOfficial endpoint (TODO).

    rows = []
    for gid, g in box.items():
        date = g.get("date") or ""
        home = g.get("home") or ""
        away = g.get("away") or ""
        offs = g.get("officials") or []
        ref_names = tuple(sorted({o.get("name", "").strip() for o in offs if o.get("name")}))
        if not (date and home and away and ref_names):
            continue
        # Compute pts from active rosters
        h_pts = sum(p.get("pts", 0) for p in (g.get("active_home") or []))
        a_pts = sum(p.get("pts", 0) for p in (g.get("active_away") or []))
        if h_pts <= 0 or a_pts <= 0:
            continue
        margin = h_pts - a_pts  # +ve = home win
        total = h_pts + a_pts
        rows.append({
            "gid": gid, "date": date, "home": home, "away": away,
            "ref_names": ref_names, "h_pts": h_pts, "a_pts": a_pts,
            "margin": margin, "total": total, "home_won": int(margin > 0),
        })

    rows.sort(key=lambda r: (r["date"], r["gid"]))
    print(f"indexed {len(rows)} games with valid refs+pts", file=sys.stderr)

    # League totals (for relative metrics) — also leakage-safe rolling
    league_total_running = []
    league_avg_at_date = {}
    for r in rows:
        if league_total_running:
            league_avg_at_date[r["gid"]] = sum(league_total_running) / len(league_total_running)
        else:
            league_avg_at_date[r["gid"]] = 220.0  # league baseline
        league_total_running.append(r["total"])

    # ── Step 2: rolling per-ref stats ──────────────────────────────────────
    # ref_name -> list of past rows (in date order)
    ref_history: dict[str, list] = defaultdict(list)

    out = {}
    for r in rows:
        # Aggregate across all crew members' past games
        crew_past = []
        for rn in r["ref_names"]:
            crew_past.extend(ref_history[rn])
        # Dedup by gid (same game might be in multiple refs' lists)
        seen = set()
        crew_past_uniq = []
        for cp in crew_past:
            if cp["gid"] in seen:
                continue
            seen.add(cp["gid"])
            crew_past_uniq.append(cp)

        if not crew_past_uniq:
            # No prior games for this crew — emit defaults but don't skip
            # (engine will fall back to defaults via .get)
            out[r["gid"]] = {
                "home_foul_bias": 0.0,
                "total_fouls_avg": 42.0,
                "foul_rate_vs_league": 1.0,
                "home_ft_advantage": 0.0,
                "experience_games": 0.0,
                "over_tendency": 0.5,
                "close_game_bias": 0.5,
                "tech_foul_rate": 0.3,
                "home_win_rate": 0.58,
                "pace_impact": 0.0,
            }
        else:
            n = len(crew_past_uniq)
            avg_margin = sum(c["margin"] for c in crew_past_uniq) / n
            avg_total = sum(c["total"] for c in crew_past_uniq) / n
            home_wins = sum(c["home_won"] for c in crew_past_uniq)
            home_win_rate = home_wins / n
            close_games = [c for c in crew_past_uniq if abs(c["margin"]) <= 5]
            close_home_wins = sum(c["home_won"] for c in close_games)
            close_bias = close_home_wins / len(close_games) if close_games else 0.5
            league_avg = league_avg_at_date.get(r["gid"], 220.0)
            over_tend = sum(1 for c in crew_past_uniq if c["total"] > league_avg) / n
            pace_impact = (avg_total - league_avg) / 10.0  # normalized
            foul_rate_vs_league = avg_total / league_avg if league_avg > 0 else 1.0
            # home_foul_bias proxy: scaled signed margin (favor home %)
            home_foul_bias = avg_margin / 100.0  # bounded ~[-0.3, 0.3]

            out[r["gid"]] = {
                "home_foul_bias": round(home_foul_bias, 4),
                "total_fouls_avg": round(avg_total / 5.5, 2),  # rough fouls~total/5.5
                "foul_rate_vs_league": round(foul_rate_vs_league, 4),
                "home_ft_advantage": round(avg_margin / 50.0, 4),
                "experience_games": float(n),
                "over_tendency": round(over_tend, 4),
                "close_game_bias": round(close_bias, 4),
                "tech_foul_rate": 0.3,  # no source — engine default
                "home_win_rate": round(home_win_rate, 4),
                "pace_impact": round(pace_impact, 4),
            }

        # Append THIS game to each crew member's history (after computing)
        for rn in r["ref_names"]:
            ref_history[rn].append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=None))
    sz_kb = OUT.stat().st_size / 1024
    n_with_history = sum(1 for v in out.values() if v["experience_games"] > 0)
    print(f"wrote {len(out)} games to {OUT.name} ({sz_kb:.1f} KB)", file=sys.stderr)
    print(f"  games with crew history (>0 prior): {n_with_history}/{len(out)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
