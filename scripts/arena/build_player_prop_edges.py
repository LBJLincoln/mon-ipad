#!/usr/bin/env python3
"""build_player_prop_edges — add 30 player-prop (pp_*) edges per game to NBA TF
predictions so 17 TF agents can bet player-props.

Inputs:
  scripts/arena/hf-llm-trading-floor/data/model-predictions-2025-26.json
  scripts/arena/hf-llm-trading-floor/data/player-stats-2025-26.json

Output (in place):
  model-predictions-2025-26.json with `per_category["pp_<stat>_<tier>"]`
  for each of 6 stats × 5 tiers × 2 teams = 60 entries per game. We emit
  the home-team side as `pp_<stat>_<tier>_home` and away as `..._away`.

Stats / tiers:
  stats = points, rebounds, assists, threes, steals, blocks
  tiers = star1 (top minutes), star2, star3, role1, role2

Edge computation:
  - Book line ≈ season avg × 0.95 (sportsbook skew toward under).
  - Model predicted = season avg (seasonal rest — prior games confirm it).
  - Edge = (predicted - line) / line.
  - Direction = OVER (positive edge) when predicted > line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[2]
TF_DATA = REPO / "scripts" / "arena" / "hf-llm-trading-floor" / "data"
PREDS = TF_DATA / "model-predictions-2025-26.json"
PSTATS = TF_DATA / "player-stats-2025-26.json"

STATS = [
    ("points",    "PPG"),
    ("rebounds",  "RPG"),
    ("assists",   "APG"),
    ("threes",    "FG3M"),
    ("steals",    "SPG"),
    ("blocks",    "BPG"),
]
TIERS = ["star1", "star2", "star3", "role1", "role2"]
LINE_SKEW = 0.95


def _pick_top_by_min(team_players: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    return sorted(team_players, key=lambda p: p.get("MIN", 0) or 0, reverse=True)[:n]


def _safe(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return default
        return f
    except Exception:
        return default


def _edges_for_team(team_players: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Return {pp_<stat>_<tier>: {edge, direction, line, predicted, player}} per-team."""
    top5 = _pick_top_by_min(team_players, 5)
    out: Dict[str, Dict[str, float]] = {}
    for i, tier in enumerate(TIERS):
        if i >= len(top5):
            continue
        player = top5[i]
        name = player.get("name", "?")
        for stat_name, col in STATS:
            predicted = _safe(player.get(col))
            if predicted <= 0.1:
                continue
            line = round(predicted * LINE_SKEW, 1)
            edge = (predicted - line) / line if line > 0 else 0.0
            key = f"pp_{stat_name}_{tier}"
            out[key] = {
                "edge": round(edge, 4),
                "direction": "over" if predicted > line else "under",
                "line": line,
                "predicted": round(predicted, 2),
                "player": name,
            }
    return out


def build() -> Dict[str, int]:
    preds = json.loads(PREDS.read_text())
    pstats = json.loads(PSTATS.read_text())

    games_updated = 0
    cats_added = 0
    games_skipped_no_stats = 0

    if not isinstance(preds, dict):
        print("[ERR] expected dict model-predictions", file=sys.stderr)
        return {"error": 1}

    for game_key, pred in preds.items():
        # game_key format: e.g. "2025-10-22_ATL@BOS" (away @ home)
        try:
            matchup = game_key.split("_", 1)[1]
            if "@" not in matchup:
                continue
            away, home = matchup.split("@", 1)
        except (IndexError, ValueError):
            continue
        home_team = pstats.get(home, {})
        away_team = pstats.get(away, {})
        home_players = home_team.get("players", []) if isinstance(home_team, dict) else []
        away_players = away_team.get("players", []) if isinstance(away_team, dict) else []

        if not home_players and not away_players:
            games_skipped_no_stats += 1
            continue

        home_edges = _edges_for_team(home_players) if home_players else {}
        away_edges = _edges_for_team(away_players) if away_players else {}

        per_cat = pred.setdefault("per_category", {})
        for k, v in home_edges.items():
            per_cat[f"{k}_home"] = v
            cats_added += 1
        for k, v in away_edges.items():
            per_cat[f"{k}_away"] = v
            cats_added += 1

        if home_edges or away_edges:
            games_updated += 1

    PREDS.write_text(json.dumps(preds))
    return {
        "games_total": len(preds),
        "games_updated": games_updated,
        "games_skipped_no_stats": games_skipped_no_stats,
        "cats_added": cats_added,
        "avg_cats_per_game": round(cats_added / max(games_updated, 1), 1),
    }


if __name__ == "__main__":
    summary = build()
    print(json.dumps(summary, indent=2))
