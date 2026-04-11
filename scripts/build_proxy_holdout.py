#!/usr/bin/env python3
"""
build_proxy_holdout.py — One-shot builder for the 30-second Brier proxy.

Extracts the last N (default: 50) real NBA games with full outcome + market
data from data/historical-odds/nba_2008-2025.csv and writes a minimal feature
holdout to data/proxy/holdout.json.

Purpose: give council/research loops (D1-D9 Hermes departments) a CHEAP
measurement signal they can use for keep/revert decisions instead of the
10-minute full Brier eval. See Cycle 18 audit:

    "Our councils CANNOT do keep/revert because Brier eval takes 10+ minutes
     on VM. Fix: 30-second proxy metric (cross-val on last 50 games)."
    — research_april2026_cycle18_competitor_audit.md

Design:
  * Features are strictly market-implied and calendar-based (no engine.py
    dependency, no player-tracking fetch) so the builder runs in <2s:
      - spread (home perspective)
      - total
      - moneyline_implied_home_prob (when available, else 0.5)
      - moneyline_implied_away_prob (when available, else 0.5)
      - implied_prob_market_delta (ml_home - ml_away)
      - playoffs flag
      - season progress (month-of-season proxy)
      - is_back_to_back_home (placeholder, 0)
      - is_back_to_back_away (placeholder, 0)
      - home_advantage_constant (1.0)
  * Label = 1 if home team won, else 0.
  * Games with missing moneyline are KEPT (ml feats fall back to 0.5) so we
    can reach 50 recent games even when sportsbook coverage is thin.

Run:
  python3 scripts/build_proxy_holdout.py
  python3 scripts/build_proxy_holdout.py --n 100
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "historical-odds" / "nba_2008-2025.csv"
OUT_PATH = ROOT / "data" / "proxy" / "holdout.json"

FEATURE_NAMES = [
    "spread",
    "total",
    "ml_home_implied_prob",
    "ml_away_implied_prob",
    "ml_delta",
    "is_playoff",
    "season_progress",
    "home_advantage",
    "favored_home",
    "ml_sum_minus_1",
]


def american_to_prob(american) -> float | None:
    try:
        v = float(american)
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    if v < 0:
        return (-v) / ((-v) + 100.0)
    return 100.0 / (v + 100.0)


def game_features(row: dict) -> tuple[list[float], int, str] | None:
    """Return (features, label, game_id) or None if the game is unusable."""
    try:
        score_home = int(row["score_home"])
        score_away = int(row["score_away"])
    except (KeyError, ValueError):
        return None
    label = 1 if score_home > score_away else 0

    try:
        spread = float(row.get("spread") or 0.0)
        total = float(row.get("total") or 0.0)
    except ValueError:
        return None
    if total <= 0:  # reject rows with no market line
        return None

    ml_home_p = american_to_prob(row.get("moneyline_home")) or 0.5
    ml_away_p = american_to_prob(row.get("moneyline_away")) or 0.5
    ml_delta = ml_home_p - ml_away_p
    is_playoff = 1.0 if str(row.get("playoffs", "")).lower() == "true" else 0.0
    favored_home = 1.0 if str(row.get("whos_favored", "")).lower() == "home" else 0.0
    ml_sum_minus_1 = (ml_home_p + ml_away_p) - 1.0  # vig proxy

    date_str = row.get("date", "")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        month = dt.month
        # season runs Oct (month=10) → Jun (month=6); map to 0..1
        season_progress = ((month - 10) % 12) / 8.0
    except ValueError:
        season_progress = 0.5

    features = [
        spread,
        total,
        ml_home_p,
        ml_away_p,
        ml_delta,
        is_playoff,
        season_progress,
        1.0,  # home advantage constant
        favored_home,
        ml_sum_minus_1,
    ]
    game_id = f"{date_str}_{row.get('away', '')}_{row.get('home', '')}"
    return features, label, game_id


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=100, help="number of most-recent games")
    args = p.parse_args()

    if not CSV_PATH.exists():
        print(f"[proxy] missing historical CSV at {CSV_PATH}")
        return 1

    rows: list[dict] = []
    with CSV_PATH.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)

    # Walk backwards from the latest date
    rows.sort(key=lambda r: r.get("date", ""))
    holdout: list[tuple[list[float], int, str]] = []
    for row in reversed(rows):
        item = game_features(row)
        if item is not None:
            holdout.append(item)
        if len(holdout) >= args.n:
            break
    holdout.reverse()  # chronological

    if not holdout:
        print("[proxy] no usable games")
        return 1

    X = [h[0] for h in holdout]
    y = [h[1] for h in holdout]
    ids = [h[2] for h in holdout]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_games": len(holdout),
        "feature_names": FEATURE_NAMES,
        "X": X,
        "y": y,
        "game_ids": ids,
        "home_win_rate": sum(y) / len(y),
    }, indent=2))
    print(
        f"[proxy] wrote {OUT_PATH} "
        f"(n={len(holdout)}, home_win_rate={sum(y)/len(y):.3f}, "
        f"feat_dim={len(FEATURE_NAMES)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
