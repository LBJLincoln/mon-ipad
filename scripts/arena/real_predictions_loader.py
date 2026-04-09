#!/usr/bin/env python3
"""
REAL PREDICTIONS LOADER
=========================
Replaces backtest_engine.py's synthetic ModelSimulator with actual stored
model predictions from /home/termius/nomos-nba-agent/data/predictions/.

Data sources (all REAL, generated prospectively before each game):
  1. predictions-YYYY-MM-DD.json  (16 daily files, ~136 games)
  2. predictions.jsonl            (52 additional rows)

Each real prediction contains:
  - home_win_prob (from ensemble model, not synthetic)
  - model_spread / model_total
  - market_implied
  - edge vs market
  - player_props (30 per game)

This loader builds a dict keyed by (date, home_abbr, away_abbr) so the
backtest can replace predict_game() with a lookup. Games without a real
prediction are DROPPED from the backtest (not synthesized) so every
result is scientifically honest.

Usage:
  from real_predictions_loader import load_real_predictions
  real_preds = load_real_predictions()
  # real_preds[(date, home_abbr, away_abbr)] = {prob_home, edge_ml, ...}
"""

import glob
import json
from pathlib import Path
from typing import Dict, Tuple

NBA_AGENT_PREDICTIONS = Path("/home/termius/nomos-nba-agent/data/predictions")
DAILY_GLOB = str(NBA_AGENT_PREDICTIONS / "predictions-2026-*.json")
JSONL_FILE = NBA_AGENT_PREDICTIONS / "predictions.jsonl"


# Team-name → 3-letter abbr mapping for when the real prediction file uses
# full names. Matches backtest_engine.py's TEAM_ABBR_MAP.
FULL_NAME_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM", "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}


def _abbr(name: str) -> str:
    """Resolve a team identifier to a 3-letter abbreviation."""
    if not name:
        return "UNK"
    n = name.strip()
    if len(n) == 3 and n.isupper():
        return n
    return FULL_NAME_TO_ABBR.get(n, n[:3].upper())


def _f(val, default: float = 0.0) -> float:
    """Coerce None / strings / NaN to a float safely."""
    if val is None:
        return default
    try:
        v = float(val)
        return v if v == v else default   # NaN guard
    except (TypeError, ValueError):
        return default


def _normalise_prediction(raw: dict) -> dict:
    """Coerce a raw prediction dict into the shape backtest_engine expects."""
    home_prob = _f(raw.get("home_win_prob", raw.get("model_raw_prob", 0.5)), 0.5)
    away_prob = _f(raw.get("away_win_prob", 1.0 - home_prob), 1.0 - home_prob)
    # Normalise so the two sum to 1
    total = home_prob + away_prob
    if total > 0:
        home_prob /= total
        away_prob /= total

    market_prob = _f(raw.get("market_implied", raw.get("market_prob", home_prob)), home_prob)
    edge_ml = home_prob - market_prob

    # Spread/total can be nested dicts (daily files) or flat (jsonl)
    sp = raw.get("spread", {})
    if isinstance(sp, dict):
        line_spread = _f(sp.get("line"), 0.0)
        model_spread = _f(sp.get("model_spread"),
                          line_spread + _f(sp.get("edge"), 0.0))
    else:
        model_spread = _f(raw.get("predicted_spread"), 0.0)
        line_spread = 0.0

    tot = raw.get("total", {})
    if isinstance(tot, dict):
        line_total = _f(tot.get("line"), 0.0)
        model_total = _f(tot.get("model_total"),
                         line_total + _f(tot.get("edge"), 0.0))
    else:
        model_total = _f(raw.get("predicted_total"), 0.0)
        line_total = 0.0

    # Edges normalised to the scale backtest_engine._get_category_edge expects
    edge_spread = (model_spread - line_spread) / 12.0 if line_spread else 0.0
    edge_total = (model_total - line_total) / 10.0 if line_total else 0.0

    # Confidence: prefer numeric, fall back on string bucket
    conf_raw = raw.get("confidence", 0.5)
    if isinstance(conf_raw, str):
        conf_map = {"HIGH": 0.85, "MED": 0.6, "MEDIUM": 0.6, "LOW": 0.4}
        confidence = conf_map.get(conf_raw.upper(), 0.5)
    else:
        try:
            confidence = float(conf_raw)
        except (TypeError, ValueError):
            confidence = 0.5

    return {
        "prob_home": round(home_prob, 4),
        "predicted_margin": round(model_spread if model_spread else (home_prob - 0.5) * 24.0, 2),
        "predicted_total": round(model_total if model_total else 224.5, 2),
        "confidence": round(confidence, 4),
        "edge_ml": round(edge_ml, 5),
        "edge_spread": round(edge_spread, 5),
        "edge_total": round(edge_total, 5),
        "market_prob": round(market_prob, 4),
        "source": "real",
    }


def load_real_predictions() -> Dict[Tuple[str, str, str], dict]:
    """
    Build a dict of (date, home_abbr, away_abbr) -> prediction.
    Returns empty dict if no source files exist.
    """
    preds: Dict[Tuple[str, str, str], dict] = {}

    # 1. Daily files (preferred — richer schema)
    for fpath in sorted(glob.glob(DAILY_GLOB)):
        try:
            data = json.loads(Path(fpath).read_text())
            date = data.get("date", "")
            if not date:
                continue
            for g in data.get("games", []):
                home = _abbr(g.get("home", g.get("home_name", "")))
                away = _abbr(g.get("away", g.get("away_name", "")))
                if home == "UNK" or away == "UNK":
                    continue
                preds[(date, home, away)] = _normalise_prediction(g)
        except Exception as e:
            print(f"[real_preds] skip {fpath}: {e}")

    # 2. JSONL additions (legacy format).
    #    IMPORTANT: rows only carry a `timestamp` (prediction run time), not the
    #    actual game date. We therefore only keep a row if we can unambiguously
    #    pin it to a real game — either (a) the same (home, away) matchup is
    #    already present in preds from the daily files, or (b) the timestamp
    #    date matches a game played that day. Otherwise we drop it; the
    #    alternative (stamping by timestamp) pollutes the loader with ~45
    #    phantom games per day that will never match the real schedule.
    if JSONL_FILE.exists():
        try:
            # Build a set of (home, away) pairs already keyed by date
            with open(JSONL_FILE) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    home = _abbr(row.get("home_team", ""))
                    away = _abbr(row.get("away_team", ""))
                    if home == "UNK" or away == "UNK":
                        continue
                    ts = row.get("timestamp", "")
                    date_hint = ts.split("T")[0] if "T" in ts else ts[:10]
                    game_date = row.get("game_date") or row.get("game_start")
                    if isinstance(game_date, str) and len(game_date) >= 10:
                        key = (game_date[:10], home, away)
                    elif date_hint:
                        # Only use the timestamp-date when it matches a date
                        # already represented by the daily files (sanity gate)
                        key = (date_hint, home, away)
                        if not any(k[0] == date_hint and k[1:] == (home, away)
                                   for k in preds):
                            # no daily-file corroboration → skip to avoid
                            # stamping the prediction-run day on the wrong game
                            continue
                    else:
                        continue
                    if key not in preds:
                        preds[key] = _normalise_prediction(row)
        except Exception as e:
            print(f"[real_preds] jsonl error: {e}")

    return preds


if __name__ == "__main__":
    preds = load_real_predictions()
    print(f"[real_preds] Loaded {len(preds)} real model predictions")
    if preds:
        sample_key = next(iter(preds.keys()))
        print(f"[real_preds] Sample key: {sample_key}")
        print(f"[real_preds] Sample value:")
        print(json.dumps(preds[sample_key], indent=2))
        # Date distribution
        from collections import Counter
        by_date = Counter(k[0] for k in preds.keys())
        print(f"\n[real_preds] Dates covered: {len(by_date)}")
        for d, c in sorted(by_date.items()):
            print(f"  {d}: {c} games")
