"""Modal job — scrape every 2025-26 NBA game's per-player box score.

Closes the leakage that user caught in the day-005 audit:
  - qwen-quant reasoned from "AD/Sarr/Vukcevic injuries" on WAS Oct 26 2025
  - Reality: AD wasn't traded to WAS yet, Sarr/Vukcevic injuries were April 2026
  - Static rosters + current-injuries file = future data leaked into past sims

Solution: pull each game's BoxScoreTraditionalV2 from nba_api.
For each game_id, we get every player who SUITED UP that night with their MIN.
  - Player on roster but MIN=0 (or absent from box) = INACTIVE that game
  - That's the only leakage-safe "did_not_play" signal

Output: data/box-scores-2025-26.json
  {
    "<game_id>": {
      "date": "2025-10-21",
      "home": "LAL", "away": "MIN",
      "active_home": [{"name": "...", "min": 35.4, "pts": 22, ...}, ...],
      "active_away": [...],
      "dnp_home": [...names...],   // on team but didn't play
      "dnp_away": [...names...]
    }
  }

Then `_format_game_block` looks up THIS game's box score, shows actual MIN
+ scoring + DNP list. No future data, no static roster — only what was on
the floor that night, which is what an oracle would have known pre-tip
(injury reports drop ~2h before tip).

USAGE on Modal:
  pip install modal
  modal secret create hf-token HF_TOKEN=hf_GKGLi...  (LBJLincoln26 token)
  modal run scripts/modal/scrape_nba_box_scores.py

USAGE on Colab (no Modal):
  Just paste the scrape() body into a cell with HF_TOKEN as env var.
"""
from __future__ import annotations
import modal

app = modal.App("nba-box-score-scrape")
image = (
    modal.Image.debian_slim()
    .pip_install("nba_api", "huggingface_hub", "requests")
)


@app.function(image=image, timeout=14400, secrets=[modal.Secret.from_name("hf-token")])
def scrape():
    """Scrape every 2025-26 game's box score → push to HF dataset."""
    import json, os, time
    from pathlib import Path
    from huggingface_hub import HfApi, hf_hub_download
    from nba_api.stats.endpoints import boxscoretraditionalv2

    tok = os.environ.get("HF_TOKEN", "")
    api = HfApi(token=tok)

    # Pull the games file from TF Space
    games_path = hf_hub_download(
        repo_id="LBJLincoln26/nba-llm-trading-floor",
        filename="data/games-2025-26.json",
        repo_type="space", token=tok,
    )
    doc = json.loads(open(games_path).read())
    games = doc.get("games", doc) if isinstance(doc, dict) else doc
    print(f"loaded {len(games)} games from TF")

    out: dict = {}
    failures = []
    for i, g in enumerate(games):
        gid = g.get("game_id", "")
        if not gid: continue
        date = g.get("game_date", "")[:10]
        home_obj = g.get("home", {})
        away_obj = g.get("away", {})
        home = (home_obj.get("team_abbr") if isinstance(home_obj, dict) else "") or ""
        away = (away_obj.get("team_abbr") if isinstance(away_obj, dict) else "") or ""
        if not (home and away):
            # parse from matchup field
            m = (g.get("matchup") or "").replace(" ", "")
            if "@" in m:
                away, home = m.split("@", 1)
        if not (home and away):
            failures.append(f"{gid}: no team abbrs")
            continue

        try:
            box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=gid).get_data_frames()
            player_df = box[0]   # per-player rows
            home_rows = player_df[player_df["TEAM_ABBREVIATION"] == home]
            away_rows = player_df[player_df["TEAM_ABBREVIATION"] == away]

            def _row_to_dict(row):
                # MIN comes as "MM:SS" string for active or NaN/None for DNP
                m_raw = row.get("MIN")
                if m_raw is None or (isinstance(m_raw, float) and m_raw != m_raw):
                    min_dec = 0.0
                elif isinstance(m_raw, str) and ":" in m_raw:
                    parts = m_raw.split(":")
                    min_dec = round(int(parts[0]) + int(parts[1]) / 60.0, 1)
                else:
                    try: min_dec = float(m_raw)
                    except: min_dec = 0.0
                return {
                    "name": row.get("PLAYER_NAME", "?"),
                    "min": min_dec,
                    "pts": int(row.get("PTS") or 0),
                    "reb": int(row.get("REB") or 0),
                    "ast": int(row.get("AST") or 0),
                    "comment": (row.get("COMMENT") or "")[:60],  # "DNP - Coach's Decision", "DND - Injury", etc.
                }

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
        except Exception as e:
            failures.append(f"{gid}: {str(e)[:80]}")
            print(f"  [{i+1}/{len(games)}] {gid} FAIL: {e}")
            continue

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(games)}] ok")
        time.sleep(0.6)  # nba_api rate limit

    # Save + push to HF dataset
    out_path = "/tmp/box-scores-2025-26.json"
    Path(out_path).write_text(json.dumps(out, indent=None))
    sz_mb = os.path.getsize(out_path) / (1024*1024)
    print(f"\n=== scraped {len(out)} games ({len(failures)} failures), {sz_mb:.1f} MB ===")

    api.create_repo("LBJLincoln26/nba-box-scores", repo_type="dataset", private=False, exist_ok=True)
    api.upload_file(
        path_or_fileobj=out_path,
        path_in_repo="box-scores-2025-26.json",
        repo_id="LBJLincoln26/nba-box-scores", repo_type="dataset",
        commit_message=f"[box-scrape] {len(out)} games via nba_api",
    )
    # Also push to NBA TF Space so app.py can read it locally
    api.upload_file(
        path_or_fileobj=out_path,
        path_in_repo="data/box-scores-2025-26.json",
        repo_id="LBJLincoln26/nba-llm-trading-floor", repo_type="space",
        commit_message=f"[box-scrape] {len(out)} games — leakage-safe per-game DNP data",
    )
    return {"games": len(out), "failures": len(failures), "size_mb": sz_mb}


@app.local_entrypoint()
def main():
    result = scrape.remote()
    print("done:", result)
