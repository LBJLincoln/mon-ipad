#!/usr/bin/env python3
"""VM-runnable NBA box-score scraper — leakage-safe per-game data.

Pulls every 2025-26 game's BoxScoreTraditionalV2 via nba_api (free) and writes
data/box-scores-2025-26.json keyed by game_id with:
  - active_home/away: players who suited up that night [name, min, pts, reb, ast, comment]
  - dnp_home/away:    players on bench with reason ("DND - Injury", etc.)

Pure I/O — no model compute. ~12-14 min for 1257 games at 0.6s rate limit.
~150 MB RAM, fits the 969 MB VM.

Output also pushed to:
  - HF dataset LBJLincoln26/nba-box-scores
  - NBA TF Space data/box-scores-2025-26.json (so app.py reads it)

USAGE:
  cd /home/termius/mon-ipad
  source .env.local
  python3 scripts/ops/scrape_nba_box_scores.py
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GAMES_LOCAL = REPO / "data" / "historical" / "games-2025-26.json"
OUT_LOCAL = REPO / "data" / "box-scores-2025-26.json"
TF_SPACE = "LBJLincoln26/nba-llm-trading-floor"
ARCHIVE_DATASET = "LBJLincoln26/nba-box-scores"
RATE_LIMIT_SEC = 0.6


def _row_to_dict(row) -> dict:
    """Pull MIN/PTS/REB/AST + DNP comment from a player box-score row."""
    m_raw = row.get("MIN")
    if m_raw is None or (isinstance(m_raw, float) and m_raw != m_raw):
        min_dec = 0.0
    elif isinstance(m_raw, str) and ":" in m_raw:
        try:
            mm, ss = m_raw.split(":")
            min_dec = round(int(mm) + int(ss) / 60.0, 1)
        except Exception:
            min_dec = 0.0
    else:
        try:
            min_dec = float(m_raw or 0)
        except Exception:
            min_dec = 0.0
    return {
        "name": row.get("PLAYER_NAME", "?"),
        "min": min_dec,
        "pts": int(row.get("PTS") or 0),
        "reb": int(row.get("REB") or 0),
        "ast": int(row.get("AST") or 0),
        "comment": (row.get("COMMENT") or "")[:60],
    }


def main() -> int:
    try:
        from nba_api.stats.endpoints import boxscoretraditionalv2
    except ImportError:
        print("nba_api not installed. Run: pip install --break-system-packages nba_api", file=sys.stderr)
        return 2

    if not GAMES_LOCAL.exists():
        print(f"games file missing: {GAMES_LOCAL}", file=sys.stderr)
        return 1
    doc = json.loads(GAMES_LOCAL.read_text())
    games = doc.get("games", doc) if isinstance(doc, dict) else doc
    print(f"loaded {len(games)} games from {GAMES_LOCAL.name}", file=sys.stderr)

    # Resume from existing file if present
    out: dict = {}
    if OUT_LOCAL.exists():
        try:
            out = json.loads(OUT_LOCAL.read_text())
            print(f"resume: {len(out)} games already scraped", file=sys.stderr)
        except Exception:
            out = {}

    failures = []
    new_count = 0
    for i, g in enumerate(games):
        gid = g.get("game_id", "")
        if not gid or gid in out:
            continue
        date = (g.get("game_date") or "")[:10]
        h_obj = g.get("home", {})
        a_obj = g.get("away", {})
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
            box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=gid).get_data_frames()
            player_df = box[0]
            home_rows = player_df[player_df["TEAM_ABBREVIATION"] == home]
            away_rows = player_df[player_df["TEAM_ABBREVIATION"] == away]

            home_players = [_row_to_dict(r) for _, r in home_rows.iterrows()]
            away_players = [_row_to_dict(r) for _, r in away_rows.iterrows()]
            active_home = [p for p in home_players if p["min"] > 0]
            active_away = [p for p in away_players if p["min"] > 0]
            dnp_home = [p for p in home_players if p["min"] == 0]
            dnp_away = [p for p in away_players if p["min"] == 0]

            out[gid] = {
                "date": date,
                "home": home, "away": away,
                "active_home": active_home,
                "active_away": active_away,
                "dnp_home": dnp_home,
                "dnp_away": dnp_away,
            }
            new_count += 1
        except Exception as e:
            failures.append(f"{gid}: {str(e)[:80]}")
            print(f"  [{i+1}/{len(games)}] {gid} FAIL: {e}", file=sys.stderr)
            continue

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(games)}] {len(out)} scraped", file=sys.stderr)
            # Snapshot every 50 — resilient to ctrl-C / network drops
            OUT_LOCAL.parent.mkdir(parents=True, exist_ok=True)
            OUT_LOCAL.write_text(json.dumps(out, indent=None))
        time.sleep(RATE_LIMIT_SEC)

    # Final save
    OUT_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOCAL.write_text(json.dumps(out, indent=None))
    sz_mb = OUT_LOCAL.stat().st_size / (1024 * 1024)
    print(f"\n=== scraped {len(out)} games (+{new_count} new), {len(failures)} failures, {sz_mb:.1f} MB ===",
          file=sys.stderr)

    # Push to HF — token resolution: HF_TOKEN_NBA owns LBJLincoln26 datasets/spaces
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN", "")
    if not tok:
        print("HF_TOKEN_NBA missing — local file written but not uploaded", file=sys.stderr)
        return 0

    try:
        from huggingface_hub import HfApi
        api = HfApi(token=tok)
        api.create_repo(ARCHIVE_DATASET, repo_type="dataset", private=False, exist_ok=True)
        api.upload_file(
            path_or_fileobj=str(OUT_LOCAL),
            path_in_repo="box-scores-2025-26.json",
            repo_id=ARCHIVE_DATASET, repo_type="dataset",
            commit_message=f"[box-scrape] {len(out)} games via nba_api",
        )
        api.upload_file(
            path_or_fileobj=str(OUT_LOCAL),
            path_in_repo="data/box-scores-2025-26.json",
            repo_id=TF_SPACE, repo_type="space",
            commit_message=f"[box-scrape] {len(out)} leakage-safe per-game lineups",
        )
        print(f"pushed to {ARCHIVE_DATASET} + {TF_SPACE}", file=sys.stderr)
    except Exception as e:
        print(f"push err: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
