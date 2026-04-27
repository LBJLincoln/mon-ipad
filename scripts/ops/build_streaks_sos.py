#!/usr/bin/env python3
"""Per-(team, date) win streak + strength-of-schedule (rolling opponent W%).

Derived purely from games-2025-26.json, leakage-safe (only games before D).

Output: data/karpathy/streaks_data.json keyed by f"{team}|{date}":
  current_win_streak, current_loss_streak, last10_wp, last5_wp,
  sos_l10 (opponent W% rolling 10), sos_season,
  vs_winning_record_wp, vs_losing_record_wp,
  home_wp_l10, road_wp_l10,
  margin_avg_l10, margin_var_l10
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parents[2]
GAMES = REPO.parent / "nomos-nba-agent" / "data" / "historical" / "games-2025-26.json"
OUT = REPO / "data" / "karpathy" / "streaks_data.json"


def main() -> int:
    games_raw = json.loads(GAMES.read_text())
    games = games_raw.get("games", games_raw) if isinstance(games_raw, dict) else games_raw

    rows = []
    for g in games:
        gid = g.get("game_id", "")
        if not gid or gid.startswith("001"):
            continue
        date = (g.get("game_date") or "")[:10]
        h_obj = g.get("home", {})
        a_obj = g.get("away", {})
        if not isinstance(h_obj, dict) or not isinstance(a_obj, dict):
            continue
        h = h_obj.get("team_abbr", "")
        a = a_obj.get("team_abbr", "")
        h_pts = h_obj.get("pts")
        a_pts = a_obj.get("pts")
        if not (h and a and h_pts is not None and a_pts is not None):
            continue
        h_pts = int(h_pts); a_pts = int(a_pts)
        margin = h_pts - a_pts
        rows.append({"date": date, "home": h, "away": a, "margin": margin, "h_pts": h_pts, "a_pts": a_pts})
    rows.sort(key=lambda r: r["date"])

    # team_results[team] = list of {date, opp, won, margin, side, opp_wp_at_time}
    team_results = defaultdict(list)
    out = {}

    for r in rows:
        h, a, m = r["home"], r["away"], r["margin"]
        date = r["date"]

        # compute features for THIS game using PRIOR history
        for team_key, side in [(h, "home"), (a, "away")]:
            past = team_results[team_key]
            n = len(past)

            if n == 0:
                out[f"{team_key}|{date}"] = {
                    "current_win_streak": 0.0, "current_loss_streak": 0.0,
                    "last10_wp": 0.5, "last5_wp": 0.5,
                    "sos_l10": 0.5, "sos_season": 0.5,
                    "vs_winning_record_wp": 0.5, "vs_losing_record_wp": 0.5,
                    "home_wp_l10": 0.5, "road_wp_l10": 0.5,
                    "margin_avg_l10": 0.0, "margin_var_l10": 25.0,
                }
            else:
                # Streak
                ws, ls = 0, 0
                for p in reversed(past):
                    if p["won"]:
                        if ls > 0: break
                        ws += 1
                    else:
                        if ws > 0: break
                        ls += 1

                last10 = past[-10:]
                last5 = past[-5:]
                last10_wp = sum(p["won"] for p in last10) / len(last10)
                last5_wp = sum(p["won"] for p in last5) / max(1, len(last5))
                # SOS: opponent's W% AT THE TIME we played them
                sos_l10 = sum(p["opp_wp_at_time"] for p in last10) / len(last10) if last10 else 0.5
                sos_season = sum(p["opp_wp_at_time"] for p in past) / n
                # vs winners/losers
                wins_winners = sum(p["won"] for p in past if p["opp_wp_at_time"] > 0.55)
                games_winners = sum(1 for p in past if p["opp_wp_at_time"] > 0.55)
                wins_losers = sum(p["won"] for p in past if p["opp_wp_at_time"] < 0.45)
                games_losers = sum(1 for p in past if p["opp_wp_at_time"] < 0.45)
                home_l10 = [p for p in last10 if p["side"] == "home"]
                road_l10 = [p for p in last10 if p["side"] == "away"]
                home_wp_l10 = sum(p["won"] for p in home_l10) / len(home_l10) if home_l10 else 0.5
                road_wp_l10 = sum(p["won"] for p in road_l10) / len(road_l10) if road_l10 else 0.5
                margins = [p["margin"] for p in last10]
                m_avg = sum(margins) / len(margins) if margins else 0.0
                m_var = sum((mm - m_avg)**2 for mm in margins) / len(margins) if margins else 25.0

                out[f"{team_key}|{date}"] = {
                    "current_win_streak": float(ws),
                    "current_loss_streak": float(ls),
                    "last10_wp": round(last10_wp, 4),
                    "last5_wp": round(last5_wp, 4),
                    "sos_l10": round(sos_l10, 4),
                    "sos_season": round(sos_season, 4),
                    "vs_winning_record_wp": round(wins_winners / max(1, games_winners), 4),
                    "vs_losing_record_wp": round(wins_losers / max(1, games_losers), 4),
                    "home_wp_l10": round(home_wp_l10, 4),
                    "road_wp_l10": round(road_wp_l10, 4),
                    "margin_avg_l10": round(m_avg, 4),
                    "margin_var_l10": round(m_var, 4),
                }

        # update history with THIS game's result
        # opponent's W% at time = win rate up to now (excluding this game)
        h_past = team_results[h]; a_past = team_results[a]
        h_wp_now = sum(p["won"] for p in h_past) / max(1, len(h_past))
        a_wp_now = sum(p["won"] for p in a_past) / max(1, len(a_past))
        team_results[h].append({"date": date, "opp": a, "won": (m > 0), "margin": m, "side": "home", "opp_wp_at_time": a_wp_now})
        team_results[a].append({"date": date, "opp": h, "won": (m < 0), "margin": -m, "side": "away", "opp_wp_at_time": h_wp_now})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=None))
    sz = OUT.stat().st_size / 1024
    print(f"wrote {len(out)} (team,date) entries to {OUT.name} ({sz:.1f} KB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
