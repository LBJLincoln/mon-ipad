#!/usr/bin/env python3
"""VM-runnable NBA box-score scraper — leakage-safe per-game data (V3 endpoint).

V2 was deprecated for 2025-26. Uses BoxScoreTraditionalV3 + BoxScoreSummaryV3.
Each player has nested {personId, firstName, familyName, nameI, position,
comment, jerseyNum, statistics: {minutes, points, rebounds, assists, ...}}.

Output: data/box-scores-2025-26.json keyed by game_id with:
  active_home/away [name, min, pts, reb, ast, comment, position]
  dnp_home/away    [name, comment, position]
  officials        [name, jersey]

Pure I/O — no model compute. ~12-14 min for 1257 games at 0.6s rate limit.
"""
from __future__ import annotations
import json, math, os, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GAMES_LOCAL = REPO / "data" / "historical" / "games-2025-26.json"
OUT_LOCAL = REPO / "data" / "box-scores-2025-26.json"
TF_SPACE = "LBJLincoln26/nba-llm-trading-floor"
ARCHIVE_DATASET = "LBJLincoln26/nba-box-scores"
RATE_LIMIT_SEC = 0.6


def _safe_int(v) -> int:
    try:
        if v is None: return 0
        f = float(v)
        if math.isnan(f): return 0
        return int(f)
    except Exception:
        return 0


def _parse_minutes(m_raw) -> float:
    if m_raw is None: return 0.0
    if isinstance(m_raw, str):
        if ":" in m_raw:
            try:
                mm, ss = m_raw.split(":", 1)
                return round(float(mm) + float(ss) / 60.0, 1)
            except Exception:
                return 0.0
        try: return float(m_raw)
        except Exception: return 0.0
    if isinstance(m_raw, (int, float)):
        try:
            f = float(m_raw)
            if math.isnan(f): return 0.0
            return round(f, 1)
        except Exception:
            return 0.0
    return 0.0


def _player_to_dict(p: dict) -> dict:
    name = p.get("nameI") or f"{p.get('firstName','')} {p.get('familyName','')}".strip()
    stats = p.get("statistics") or {}
    return {
        "name": name[:40],
        "min": _parse_minutes(stats.get("minutes")),
        "pts": _safe_int(stats.get("points")),
        "reb": _safe_int(stats.get("reboundsTotal") or stats.get("rebounds")),
        "ast": _safe_int(stats.get("assists")),
        "comment": (p.get("comment") or "")[:60],
        "pos": p.get("position", "")[:3],
    }


def main() -> int:
    try:
        from nba_api.stats.endpoints import boxscoretraditionalv3, boxscoresummaryv3
    except ImportError:
        print("nba_api not installed. Run: pip install --break-system-packages nba_api", file=sys.stderr)
        return 2

    if not GAMES_LOCAL.exists():
        print(f"games file missing: {GAMES_LOCAL}", file=sys.stderr)
        return 1
    doc = json.loads(GAMES_LOCAL.read_text())
    games = doc.get("games", doc) if isinstance(doc, dict) else doc
    print(f"loaded {len(games)} games from {GAMES_LOCAL.name}", file=sys.stderr)

    out: dict = {}
    if OUT_LOCAL.exists():
        try:
            out = json.loads(OUT_LOCAL.read_text())
            print(f"resume: {len(out)} games already scraped", file=sys.stderr)
        except Exception:
            out = {}

    failures = []
    new_count = 0
    skipped_preseason = 0
    for i, g in enumerate(games):
        gid = g.get("game_id", "")
        if not gid or gid in out:
            continue
        # Skip preseason (game_id starts with "001") — V3 has no data for these
        if gid.startswith("001"):
            skipped_preseason += 1
            continue
        date = (g.get("game_date") or "")[:10]
        h_obj = g.get("home", {}); a_obj = g.get("away", {})
        home = (h_obj.get("team_abbr") if isinstance(h_obj, dict) else "") or ""
        away = (a_obj.get("team_abbr") if isinstance(a_obj, dict) else "") or ""
        if not (home and away):
            m = (g.get("matchup") or "").replace(" ", "")
            if "@" in m:
                away, home = m.split("@", 1)
        if not (home and away):
            failures.append(f"{gid}: no team abbrs")
            continue

        try:
            bs = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=gid).get_dict()
            payload = bs.get("boxScoreTraditional") or {}
            home_block = payload.get("homeTeam") or {}
            away_block = payload.get("awayTeam") or {}
            home_team_abbr = home_block.get("teamTricode") or home
            away_team_abbr = away_block.get("teamTricode") or away
            # Verify abbrs match (V3 might disagree with our games file)
            if home_team_abbr != home: home = home_team_abbr
            if away_team_abbr != away: away = away_team_abbr

            home_players = [_player_to_dict(p) for p in (home_block.get("players") or [])]
            away_players = [_player_to_dict(p) for p in (away_block.get("players") or [])]
            active_home = [p for p in home_players if p["min"] > 0]
            active_away = [p for p in away_players if p["min"] > 0]
            dnp_home = [p for p in home_players if p["min"] == 0]
            dnp_away = [p for p in away_players if p["min"] == 0]

            # Officials + INACTIVE list via SummaryV3
            # 2026-04-27: V3 BoxScoreTraditional only lists players who suited up
            # (active + DNP). Players who were INACTIVE (injured DNS, suspended,
            # etc.) never appear there — that's why LeBron didn't show in Oct 21
            # 2025 LAL game (he was injured, on inactive list, didn't suit up).
            # SummaryV3.inactivePlayers fills this gap.
            officials = []
            inactive_home = []
            inactive_away = []
            try:
                summary = boxscoresummaryv3.BoxScoreSummaryV3(game_id=gid).get_dict()
                bs_sum = summary.get("boxScoreSummary") or {}
                offs = bs_sum.get("officials") or []
                for r in offs:
                    nm = r.get("nameI") or f"{r.get('firstName','')} {r.get('familyName','')}".strip()
                    if nm.strip():
                        officials.append({"name": nm[:40], "jersey": str(r.get("jerseyNum") or "")})
                # Inactive players list
                for ip in (bs_sum.get("inactivePlayers") or []):
                    nm = ip.get("nameI") or f"{ip.get('firstName','')} {ip.get('familyName','')}".strip()
                    team_abbr = ip.get("teamTricode") or ""
                    entry = {"name": nm[:40], "comment": "INACTIVE"}
                    if team_abbr == home:
                        inactive_home.append(entry)
                    elif team_abbr == away:
                        inactive_away.append(entry)
                time.sleep(0.5)
            except Exception:
                pass

            out[gid] = {
                "date": date,
                "home": home, "away": away,
                "active_home": active_home,
                "active_away": active_away,
                "dnp_home": dnp_home,
                "dnp_away": dnp_away,
                "inactive_home": inactive_home,
                "inactive_away": inactive_away,
                "officials": officials,
            }
            new_count += 1
        except Exception as e:
            failures.append(f"{gid}: {str(e)[:80]}")
            if len(failures) <= 5 or len(failures) % 50 == 0:
                print(f"  [{i+1}/{len(games)}] {gid} FAIL: {e}", file=sys.stderr)
            continue

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(games)}] {len(out)} scraped (+{new_count} new), {len(failures)} fails",
                  file=sys.stderr)
            OUT_LOCAL.parent.mkdir(parents=True, exist_ok=True)
            OUT_LOCAL.write_text(json.dumps(out, indent=None))
        time.sleep(RATE_LIMIT_SEC)

    OUT_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOCAL.write_text(json.dumps(out, indent=None))
    sz_mb = OUT_LOCAL.stat().st_size / (1024 * 1024)
    print(f"\n=== scraped {len(out)} games (+{new_count} new this run), "
          f"{len(failures)} failures, {skipped_preseason} preseason-skipped, "
          f"{sz_mb:.1f} MB ===", file=sys.stderr)

    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN", "")
    if not tok:
        print("HF_TOKEN_NBA missing — local file written, no upload", file=sys.stderr)
        return 0
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=tok)
        api.create_repo(ARCHIVE_DATASET, repo_type="dataset", private=False, exist_ok=True)
        api.upload_file(
            path_or_fileobj=str(OUT_LOCAL),
            path_in_repo="box-scores-2025-26.json",
            repo_id=ARCHIVE_DATASET, repo_type="dataset",
            commit_message=f"[box-scrape V3] {len(out)} games (+refs)",
        )
        api.upload_file(
            path_or_fileobj=str(OUT_LOCAL),
            path_in_repo="data/box-scores-2025-26.json",
            repo_id=TF_SPACE, repo_type="space",
            commit_message=f"[box-scrape V3] {len(out)} leakage-safe per-game lineups + refs",
        )
        print(f"pushed to {ARCHIVE_DATASET} + {TF_SPACE}", file=sys.stderr)
    except Exception as e:
        print(f"push err: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
