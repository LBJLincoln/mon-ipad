#!/usr/bin/env python3
"""Build a single per-day NBA input file that ANY agent (or human) can audit.

For each simulated day in the 2025-26 season, writes:
  data/day-inputs/nba-YYYY-MM-DD.json

containing:
  - all games on that date
  - all 249 odds categories per game
  - rosters + stars + forms per team
  - model predictions (p_home, p_away, etc.)
  - server-side RANKED top-N edge candidates across all games/categories
    (pre-computed edge = model_prob vs implied_prob delta)

This lets you verify EXACTLY what context the agent sees when deciding bets.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
HF_CACHE = REPO / "scripts/arena/hf-llm-trading-floor/data"
OUT_DIR = REPO / "data" / "day-inputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FULL_ODDS = HF_CACHE / "full-odds-2025-26.json"
GAMES = HF_CACHE / "games-2025-26.json"
ROSTERS = HF_CACHE / "rosters-2025-26.json"
PLAYER_STATS = HF_CACHE / "player-stats-2025-26.json"
TEAM_ADV = HF_CACHE / "team-advanced-2025-26.json"
MODEL_PREDS = HF_CACHE / "model-predictions-2025-26.json"


def _load(p: Path) -> Any:
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except Exception: return {}


def _compute_edges_for_game(game_odds: dict, model_pred: dict) -> list[dict]:
    """For each category with odds, compute model_p vs implied_p edge.
    Prefers the pre-computed `edge` from model_preds.per_category when available."""
    out = []
    per_cat = (model_pred or {}).get("per_category", {}) or {}
    for cat_name, cat_data in (game_odds.get("categories", game_odds) or {}).items():
        if not isinstance(cat_data, dict): continue
        odds = cat_data.get("odds") or cat_data.get("price")
        if not isinstance(odds, (int, float)) or odds <= 1.0: continue
        implied_p = 1.0 / float(odds)
        model_info = per_cat.get(cat_name) or {}
        model_p = model_info.get("prob")
        # Prefer the pre-computed edge if model_preds already ran it; else compute
        edge = model_info.get("edge")
        if edge is None and isinstance(model_p, (int, float)):
            edge = float(model_p) - implied_p
        out.append({
            "category": cat_name,
            "odds": round(float(odds), 3),
            "implied_prob": round(implied_p, 4),
            "model_prob": round(model_p, 4) if isinstance(model_p, (int, float)) else None,
            "edge": round(float(edge), 4) if isinstance(edge, (int, float)) else None,
            "line": cat_data.get("line"),
        })
    return out


def build_for_date(date: str) -> dict | None:
    full_odds = _load(FULL_ODDS)
    games_root = _load(GAMES)
    rosters = _load(ROSTERS)
    model_preds = _load(MODEL_PREDS)
    team_adv = _load(TEAM_ADV)

    # games_root is {season, pulled_at, game_count, games: [...], metadata}
    games_list = games_root.get("games", []) if isinstance(games_root, dict) else games_root
    games_today = []
    for g in games_list:
        if g.get("game_date") == date:
            # key: use game_id or date_AWAY@HOME (matchup 'PHI @ NYK' -> date + PHI@NYK)
            matchup = (g.get("matchup") or "").replace(" ", "")  # PHI@NYK
            gk = g.get("game_id") or f"{date}_{matchup}"
            games_today.append((gk, g))
    if not games_today:
        return None

    day_blob: dict[str, Any] = {"date": date, "n_games": len(games_today), "games": []}
    all_edges: list[dict] = []

    for gk, g in games_today:
        # matchup formats (verified 2026-04-24):
        #   "AWAY @ HOME"   e.g., "PHI @ NYK"  -> PHI is away, NYK is home
        #   "HOME vs. AWAY" e.g., "CHA vs. ATL" -> CHA is home, ATL is away
        matchup = g.get("matchup") or ""
        home, away = "", ""
        if "@" in matchup:
            parts = [p.strip() for p in matchup.split("@")]
            if len(parts) == 2: away, home = parts[0], parts[1]
        elif "vs." in matchup:
            parts = [p.strip() for p in matchup.split("vs.")]
            if len(parts) == 2: home, away = parts[0], parts[1]
        elif "vs" in matchup.lower():
            parts = [p.strip() for p in matchup.split("vs")]
            if len(parts) == 2: home, away = parts[0], parts[1]
        # full_odds keyed as YYYY-MM-DD_AWAY@HOME
        key_away_at_home = f"{date}_{away}@{home}"
        candidate_keys = [gk, key_away_at_home, g.get("game_id")]
        odds: dict = {}
        for k in candidate_keys:
            if k and k in full_odds:
                odds = full_odds[k]; break
        pred: dict = {}
        for k in candidate_keys:
            if k and k in model_preds:
                pred = model_preds[k]; break
        edges = _compute_edges_for_game(odds, pred)
        # Flatten into master ranker
        for e in edges:
            e["game_key"] = gk
            all_edges.append(e)
        game_blob = {
            "game_key": gk,
            "home": home, "away": away,
            "n_odds_categories": len(edges),
            "full_odds": odds,
            "roster_home": rosters.get(home, {}) if isinstance(rosters, dict) else {},
            "roster_away": rosters.get(away, {}) if isinstance(rosters, dict) else {},
            "team_advanced_home": (team_adv.get(home) if isinstance(team_adv, dict) else {}) or {},
            "team_advanced_away": (team_adv.get(away) if isinstance(team_adv, dict) else {}) or {},
            "model_prediction": pred,
            "edges": edges,
        }
        day_blob["games"].append(game_blob)

    # Rank all edges: positive edges first (descending), then negative edges
    # (for short-side betting). Top-50 includes both directions.
    scored = [e for e in all_edges if e.get("edge") is not None]
    positive = sorted([e for e in scored if e["edge"] > 0], key=lambda x: -x["edge"])
    negative = sorted([e for e in scored if e["edge"] <= 0], key=lambda x: x["edge"])
    day_blob["top_positive_edges"] = positive[:25]   # long-bias candidates
    day_blob["top_negative_edges"] = negative[:10]   # fade candidates (short / avoid)
    day_blob["top_edges_ranked"] = (positive[:25] + negative[:10])
    day_blob["n_total_bet_lines"] = len(all_edges)
    day_blob["n_edges_scored"] = len(scored)
    day_blob["n_positive_edges"] = len(positive)
    return day_blob


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: build_daily_nba_input.py YYYY-MM-DD  |  all")
        return 2
    target = sys.argv[1]
    if target == "all":
        games_all = _load(GAMES)
        dates = set()
        if isinstance(games_all, dict):
            for gk, gd in games_all.items():
                if isinstance(gd, dict) and gd.get("date"):
                    dates.add(gd["date"])
        elif isinstance(games_all, list):
            dates = {gd.get("date") for gd in games_all if gd.get("date")}
        dates = sorted(d for d in dates if d)
        print(f"building {len(dates)} day-input files...")
        built = 0
        for date in dates:
            blob = build_for_date(date)
            if not blob: continue
            (OUT_DIR / f"nba-{date}.json").write_text(json.dumps(blob, indent=2, default=str))
            built += 1
        print(f"wrote {built} files to {OUT_DIR}")
        return 0
    blob = build_for_date(target)
    if not blob:
        print(f"no games on {target}"); return 1
    out = OUT_DIR / f"nba-{target}.json"
    out.write_text(json.dumps(blob, indent=2, default=str))
    print(f"wrote {out}")
    print(f"  n_games: {blob['n_games']}")
    print(f"  n_total_bet_lines: {blob['n_total_bet_lines']}")
    print(f"  top_edge_candidates: {len(blob['top_edges_ranked'])}")
    if blob["top_edges_ranked"]:
        top = blob["top_edges_ranked"][:5]
        print("  top 5 edges:")
        for e in top:
            print(f"    {e['game_key']} {e['category']} odds={e['odds']} implied={e['implied_prob']} model={e['model_prob']} edge={e['edge']:+.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
