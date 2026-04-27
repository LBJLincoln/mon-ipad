#!/usr/bin/env python3
"""Scrape NBA play-by-play V3 for 2025-26 → leakage-safe quarter patterns.

Per game: extract Q1/Q2/Q3/Q4/OT margins, half adjustment, comeback/blowout
flags, garbage time minutes. Then aggregate per (team, date) using only games
BEFORE that date — feeding engine cat 13 quarter_data param.

Output: data/karpathy/quarter_data.json keyed by f"{team}|{date}":
  {q1_margin_avg, q2_margin_avg, q3_margin_avg, q4_clutch_netrtg,
   half_adjustment, comeback_win_pct, blowout_hold_pct, garbage_time_margin,
   q1_lead_pct, q3_lead_pct, q4_close_win_pct, ot_count}

Also writes raw per-game scores to data/play-by-play-2025-26.json for reuse.

Resume-safe: skips games already in raw output.
Rate limit: 0.6s/game (NBA stats API throttle).

Usage: python3 scripts/ops/scrape_nba_play_by_play.py
"""
from __future__ import annotations
import json, sys, time, math
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parents[2]
GAMES_LOCAL = REPO.parent / "nomos-nba-agent" / "data" / "historical" / "games-2025-26.json"
RAW_OUT = REPO / "data" / "play-by-play-2025-26.json"
OUT = REPO / "data" / "karpathy" / "quarter_data.json"
RATE_LIMIT_SEC = 0.6


def _safe_int(v) -> int:
    try:
        if v is None:
            return 0
        f = float(v)
        if math.isnan(f):
            return 0
        return int(f)
    except Exception:
        return 0


def main() -> int:
    try:
        from nba_api.stats.endpoints import boxscoresummaryv3
    except ImportError:
        print("nba_api missing — install with: pip install --break-system-packages nba_api", file=sys.stderr)
        return 2

    games_raw = json.loads(GAMES_LOCAL.read_text())
    games = games_raw.get("games", games_raw) if isinstance(games_raw, dict) else games_raw

    raw = {}
    if RAW_OUT.exists():
        try:
            raw = json.loads(RAW_OUT.read_text())
            print(f"resume: {len(raw)} games already scraped", file=sys.stderr)
        except Exception:
            raw = {}

    failures = []
    new_count = 0
    skipped = 0

    for i, g in enumerate(games):
        gid = g.get("game_id", "")
        if not gid or gid in raw:
            continue
        if gid.startswith("001"):  # preseason
            skipped += 1
            continue

        date = (g.get("game_date") or "")[:10]
        h_obj = g.get("home", {})
        a_obj = g.get("away", {})
        home = (h_obj.get("team_abbr") if isinstance(h_obj, dict) else "") or ""
        away = (a_obj.get("team_abbr") if isinstance(a_obj, dict) else "") or ""
        if not (home and away):
            failures.append(f"{gid}: no team abbrs")
            continue

        try:
            # Use BoxScoreSummaryV3 — has line scores per quarter (q1/q2/q3/q4 + OTs)
            summary = boxscoresummaryv3.BoxScoreSummaryV3(game_id=gid).get_dict()
            bs = summary.get("boxScoreSummary") or {}
            home_team = bs.get("homeTeam") or {}
            away_team = bs.get("awayTeam") or {}

            # Periods are in "periods" field per team — list of {period, score}
            def periods_dict(team_obj):
                d = {}
                for pr in team_obj.get("periods", []) or []:
                    period = pr.get("period")
                    score = _safe_int(pr.get("score"))
                    if period:
                        d[period] = score
                return d

            h_pers = periods_dict(home_team)
            a_pers = periods_dict(away_team)

            q1_margin = h_pers.get(1, 0) - a_pers.get(1, 0)
            q2_margin = h_pers.get(2, 0) - a_pers.get(2, 0)
            q3_margin = h_pers.get(3, 0) - a_pers.get(3, 0)
            q4_margin = h_pers.get(4, 0) - a_pers.get(4, 0)
            ot_count = sum(1 for p in h_pers.keys() if p > 4)

            h_total = sum(h_pers.values())
            a_total = sum(a_pers.values())
            margin_total = h_total - a_total

            half_lead = (q1_margin + q2_margin)
            second_half = (q3_margin + q4_margin)
            half_adjustment = second_half - half_lead

            # Comeback flag: trailed at half but won
            comeback = 1 if (half_lead < -3 and margin_total > 0) else 0
            comeback_neg = 1 if (half_lead > 3 and margin_total < 0) else 0
            # Blowout hold: led by 10+ at half AND won by 10+
            blowout_hold = 1 if (half_lead >= 10 and margin_total >= 10) else 0
            blowout_loss = 1 if (half_lead <= -10 and margin_total <= -10) else 0
            garbage_time_margin = (q4_margin if abs(q3_margin + half_lead) >= 15 else 0)

            raw[gid] = {
                "date": date, "home": home, "away": away,
                "q1": q1_margin, "q2": q2_margin, "q3": q3_margin, "q4": q4_margin,
                "ot_count": ot_count,
                "h_total": h_total, "a_total": a_total, "margin": margin_total,
                "half_lead": half_lead, "half_adjustment": half_adjustment,
                "comeback": comeback, "comeback_neg": comeback_neg,
                "blowout_hold": blowout_hold, "blowout_loss": blowout_loss,
                "garbage_time_margin": garbage_time_margin,
            }
            new_count += 1
        except Exception as e:
            failures.append(f"{gid}: {str(e)[:80]}")
            if len(failures) <= 5 or len(failures) % 50 == 0:
                print(f"  [{i+1}/{len(games)}] {gid} FAIL: {e}", file=sys.stderr)
            continue

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(games)}] {len(raw)} scraped (+{new_count}), {len(failures)} fails",
                  file=sys.stderr)
            RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
            RAW_OUT.write_text(json.dumps(raw, indent=None))
        time.sleep(RATE_LIMIT_SEC)

    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUT.write_text(json.dumps(raw, indent=None))
    print(f"=== {len(raw)} games scraped (+{new_count} new), {len(failures)} fails, {skipped} preseason ===",
          file=sys.stderr)

    # ── Aggregate per (team, date) using leakage-safe rolling history ────
    # Index every game by date order
    rows = []
    for gid, r in raw.items():
        for side in ("home", "away"):
            t = r.get(side)
            if not t:
                continue
            sign = 1 if side == "home" else -1
            rows.append({
                "gid": gid, "date": r["date"], "team": t,
                "q1": r["q1"] * sign, "q2": r["q2"] * sign,
                "q3": r["q3"] * sign, "q4": r["q4"] * sign,
                "margin": r["margin"] * sign,
                "half_lead": r["half_lead"] * sign,
                "half_adjustment": r["half_adjustment"] * sign,
                "comeback": r["comeback"] if side == "home" else r["comeback_neg"],
                "blowout_hold": r["blowout_hold"] if side == "home" else r["blowout_loss"],
                "garbage_time_margin": r["garbage_time_margin"] * sign,
                "won": 1 if (r["margin"] > 0) == (side == "home") else 0,
                "ot_count": r["ot_count"],
            })
    rows.sort(key=lambda r: (r["date"], r["gid"]))

    history = defaultdict(list)
    out = {}
    for r in rows:
        team, date = r["team"], r["date"]
        past = history[team]

        if not past:
            out[f"{team}|{date}"] = {
                "q1_margin_avg": 0.0, "q2_margin_avg": 0.0, "q3_margin_avg": 0.0,
                "q4_margin_avg": 0.0, "q4_clutch_netrtg": 0.0,
                "half_adjustment": 0.0, "comeback_win_pct": 0.30,
                "blowout_hold_pct": 0.70, "garbage_time_margin": 0.0,
                "q1_lead_pct": 0.5, "q3_lead_pct": 0.5,
                "q4_close_win_pct": 0.5, "ot_pct": 0.05,
            }
        else:
            n = len(past)
            avg = lambda k: sum(p[k] for p in past) / n
            close_games = [p for p in past if abs(p["margin"]) <= 5]
            close_wins = sum(p["won"] for p in close_games)
            comebacks = sum(p["comeback"] for p in past)
            blowout_holds = sum(p["blowout_hold"] for p in past)
            comeback_setups = sum(1 for p in past if p["half_lead"] < -3)
            blowout_setups = sum(1 for p in past if p["half_lead"] >= 10)

            out[f"{team}|{date}"] = {
                "q1_margin_avg": round(avg("q1"), 4),
                "q2_margin_avg": round(avg("q2"), 4),
                "q3_margin_avg": round(avg("q3"), 4),
                "q4_margin_avg": round(avg("q4"), 4),
                "q4_clutch_netrtg": round(avg("q4") / 12.0, 4),  # per-min proxy
                "half_adjustment": round(avg("half_adjustment"), 4),
                "comeback_win_pct": round(comebacks / max(comeback_setups, 1), 4),
                "blowout_hold_pct": round(blowout_holds / max(blowout_setups, 1), 4),
                "garbage_time_margin": round(avg("garbage_time_margin"), 4),
                "q1_lead_pct": round(sum(1 for p in past if p["q1"] > 0) / n, 4),
                "q3_lead_pct": round(sum(1 for p in past if (p["q1"]+p["q2"]+p["q3"]) > 0) / n, 4),
                "q4_close_win_pct": round(close_wins / max(len(close_games), 1), 4),
                "ot_pct": round(sum(1 for p in past if p["ot_count"] > 0) / n, 4),
            }

        history[team].append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=None))
    print(f"wrote {len(out)} (team,date) quarter entries", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
