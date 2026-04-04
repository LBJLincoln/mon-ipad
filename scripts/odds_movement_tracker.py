#!/usr/bin/env python3
"""
odds_movement_tracker.py
========================
Lightweight intraday line-movement tracker for NBA odds.
Captures timestamped snapshots, extracts movement features.

Depends on: fetch_free_odds.py (same directory) for actual fetching.
stdlib-only. Under 300 lines.

Output:
  data/nba-agent/odds-history/YYYY-MM-DD.json  — Timestamped snapshots
  data/nba-agent/odds-movement-features.json    — Movement features per game
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, date
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "nba-agent"
HISTORY_DIR = DATA_DIR / "odds-history"
FEATURES_PATH = DATA_DIR / "odds-movement-features.json"

HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# ─── Import from fetch_free_odds.py ─────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_free_odds import (
    fetch_live_odds,
    american_to_implied,
    normalize_team,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _history_path(dt_str: str) -> Path:
    """Return path for a given date's history file."""
    return HISTORY_DIR / f"{dt_str}.json"


def _load_history(dt_str: str) -> dict:
    """Load existing history file or return empty structure."""
    p = _history_path(dt_str)
    if p.exists():
        with open(p, "r") as f:
            return json.load(f)
    return {"snapshots": []}


def _save_history(dt_str: str, data: dict):
    """Save history file."""
    p = _history_path(dt_str)
    with open(p, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved snapshot to {p}")


def _game_key(game: dict) -> str:
    """Canonical game key for matching across snapshots."""
    return f"{game.get('home_team', '')} vs {game.get('away_team', '')}"


def _extract_ml_home(game: dict):
    """Extract home moneyline (American) from game dict."""
    ml_market = game.get("markets", {}).get("moneyline", [])
    home_team = game.get("home_team", "")
    for outcome in ml_market:
        if normalize_team(outcome.get("name", "")) == home_team:
            try:
                return int(float(outcome["american"]))
            except (ValueError, TypeError, KeyError):
                pass
    # Fallback: second entry is usually home in our format
    if len(ml_market) >= 2:
        try:
            return int(float(ml_market[1]["american"]))
        except (ValueError, TypeError, KeyError):
            pass
    return None


def _extract_spread_home(game: dict):
    """Extract home spread from game dict."""
    sp_market = game.get("markets", {}).get("spread", [])
    home_team = game.get("home_team", "")
    for outcome in sp_market:
        if normalize_team(outcome.get("name", "")) == home_team:
            try:
                return float(outcome["handicap"])
            except (ValueError, TypeError, KeyError):
                pass
    if len(sp_market) >= 2:
        try:
            return float(sp_market[1]["handicap"])
        except (ValueError, TypeError, KeyError):
            pass
    return None


def _extract_total(game: dict):
    """Extract total from game dict."""
    tot_market = game.get("markets", {}).get("total", [])
    if tot_market:
        try:
            return float(tot_market[0]["handicap"])
        except (ValueError, TypeError, KeyError):
            pass
    return None


def _extract_public_data(game: dict) -> dict:
    """Extract public bet/money percentages."""
    return game.get("public_data", {})


# ─── 1. Fetch & Snapshot ────────────────────────────────────────────────────

def fetch_and_snapshot() -> tuple:
    """Fetch current odds and append as a timestamped snapshot.
    Returns (today_str, games_count)."""
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"[OddsTracker] Fetching odds at {ts} ...")
    games, source = fetch_live_odds()
    print(f"[OddsTracker] Got {len(games)} games from {source}")

    if not games:
        print("[OddsTracker] No games found. Saving empty snapshot.")

    # Build minimal snapshot (keep only what we need)
    snapshot_games = []
    for g in games:
        snapshot_games.append({
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "start_time": g.get("start_time"),
            "source": g.get("source", source),
            "markets": g.get("markets", {}),
            "public_data": g.get("public_data", {}),
            "pinnacle": g.get("pinnacle", {}),
        })

    snapshot = {
        "ts": ts,
        "source": source,
        "n_games": len(snapshot_games),
        "games": snapshot_games,
    }

    # Append to today's history file
    history = _load_history(today_str)
    history["snapshots"].append(snapshot)
    _save_history(today_str, history)

    print(f"[OddsTracker] Snapshot #{len(history['snapshots'])} saved for {today_str}")
    return today_str, len(games)


# ─── 2. Feature Extraction ──────────────────────────────────────────────────

def extract_movement_features(dt_str: str = None) -> dict:
    """Extract line movement features from a day's snapshots.
    Returns dict of {game_key: features}."""
    if dt_str is None:
        dt_str = date.today().strftime("%Y-%m-%d")

    history = _load_history(dt_str)
    snapshots = history.get("snapshots", [])

    if len(snapshots) < 1:
        print(f"[OddsTracker] No snapshots for {dt_str}")
        return {}

    # Build per-game timeline: list of (ts, game_data) ordered by time
    timelines = {}  # game_key -> [(ts, game_data), ...]
    for snap in snapshots:
        ts = snap["ts"]
        for g in snap.get("games", []):
            key = _game_key(g)
            if key not in timelines:
                timelines[key] = []
            timelines[key].append((ts, g))

    all_features = {}
    for key, timeline in timelines.items():
        first_ts, first_game = timeline[0]
        last_ts, last_game = timeline[-1]

        opening_ml = _extract_ml_home(first_game)
        current_ml = _extract_ml_home(last_game)
        opening_spread = _extract_spread_home(first_game)
        current_spread = _extract_spread_home(last_game)
        opening_total = _extract_total(first_game)
        current_total = _extract_total(last_game)

        opening_implied = american_to_implied(opening_ml) if opening_ml else None
        current_implied = american_to_implied(current_ml) if current_ml else None

        # ML move in implied probability
        ml_move_pct = None
        ml_direction = "STABLE"
        if opening_implied is not None and current_implied is not None:
            ml_move_pct = round((current_implied - opening_implied) * 100, 3)
            if ml_move_pct > 1.0:
                ml_direction = "HOME"
            elif ml_move_pct < -1.0:
                ml_direction = "AWAY"

        # Spread and total movement
        spread_move = None
        if opening_spread is not None and current_spread is not None:
            spread_move = round(current_spread - opening_spread, 2)

        total_move = None
        if opening_total is not None and current_total is not None:
            total_move = round(current_total - opening_total, 2)

        # Count significant inter-snapshot moves and find max single move
        n_moves = 0
        max_single_move = 0.0
        steam_detected = False
        steam_direction = None

        if len(timeline) >= 2:
            for i in range(1, len(timeline)):
                prev_ml = _extract_ml_home(timeline[i - 1][1])
                curr_ml = _extract_ml_home(timeline[i][1])
                prev_imp = american_to_implied(prev_ml) if prev_ml else None
                curr_imp = american_to_implied(curr_ml) if curr_ml else None
                if prev_imp is not None and curr_imp is not None:
                    delta = abs(curr_imp - prev_imp) * 100
                    if delta > 1.0:
                        n_moves += 1
                    if delta > max_single_move:
                        max_single_move = delta
                    if delta > 5.0:
                        steam_detected = True
                        steam_direction = "HOME" if curr_imp > prev_imp else "AWAY"

        max_single_move = round(max_single_move, 3)

        # Sharp divergence from public data (last snapshot)
        pub = _extract_public_data(last_game)
        sharp_divergence = None
        reverse_line_movement = False

        home_money_pct = pub.get("ml_home_money_pct")
        home_bets_pct = pub.get("ml_home_bets_pct")
        if home_money_pct is not None and home_bets_pct is not None:
            try:
                sharp_divergence = round(float(home_money_pct) - float(home_bets_pct), 2)
            except (ValueError, TypeError):
                pass

        # Reverse line movement: line moved opposite to public betting
        if ml_move_pct is not None and home_bets_pct is not None:
            try:
                public_favors_home = float(home_bets_pct) > 50
                line_favors_home = ml_move_pct > 0
                if public_favors_home and not line_favors_home:
                    reverse_line_movement = True
                elif not public_favors_home and line_favors_home:
                    reverse_line_movement = True
            except (ValueError, TypeError):
                pass

        features = {
            "game": key,
            "home_team": last_game.get("home_team"),
            "away_team": last_game.get("away_team"),
            "n_snapshots": len(timeline),
            "first_seen": first_ts,
            "last_seen": last_ts,
            "opening_ml_home": opening_ml,
            "current_ml_home": current_ml,
            "opening_implied_prob": opening_implied,
            "current_implied_prob": current_implied,
            "ml_move_pct": ml_move_pct,
            "ml_direction": ml_direction,
            "spread_move": spread_move,
            "total_move": total_move,
            "n_moves": n_moves,
            "max_single_move": max_single_move,
            "steam_detected": steam_detected,
            "steam_direction": steam_direction,
            "sharp_divergence": sharp_divergence,
            "reverse_line_movement": reverse_line_movement,
        }
        all_features[key] = features

    # Save features
    output = {
        "date": dt_str,
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_games": len(all_features),
        "games": all_features,
    }
    with open(FEATURES_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"[OddsTracker] Extracted features for {len(all_features)} games -> {FEATURES_PATH}")

    return all_features


# ─── 3. Show History ────────────────────────────────────────────────────────

def show_history(dt_str: str):
    """Print summary of a day's snapshots."""
    history = _load_history(dt_str)
    snapshots = history.get("snapshots", [])
    print(f"\n=== Odds History for {dt_str} ===")
    print(f"Total snapshots: {len(snapshots)}\n")

    for i, snap in enumerate(snapshots):
        n = snap.get("n_games", len(snap.get("games", [])))
        print(f"  Snapshot #{i+1}  ts={snap['ts']}  source={snap.get('source','?')}  games={n}")
        for g in snap.get("games", []):
            ml = _extract_ml_home(g)
            sp = _extract_spread_home(g)
            tot = _extract_total(g)
            ml_str = f"ML={ml}" if ml else "ML=n/a"
            sp_str = f"Spread={sp}" if sp is not None else "Spread=n/a"
            tot_str = f"Total={tot}" if tot is not None else "Total=n/a"
            print(f"    {g.get('away_team', '?'):25s} @ {g.get('home_team', '?'):25s}  {ml_str}  {sp_str}  {tot_str}")
    print()


# ─── 4. CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NBA Odds Movement Tracker — intraday line movement & feature extraction"
    )
    parser.add_argument("--fetch", action="store_true",
                        help="Fetch current odds and save snapshot")
    parser.add_argument("--features", action="store_true",
                        help="Extract movement features from today's snapshots")
    parser.add_argument("--history", type=str, metavar="YYYY-MM-DD",
                        help="Show history for a specific date")
    args = parser.parse_args()

    if not (args.fetch or args.features or args.history):
        parser.print_help()
        print("\n# Cron: */120 * * * * cd /home/termius/mon-ipad && python3 scripts/odds_movement_tracker.py --fetch >> /tmp/odds-tracker.log 2>&1")
        sys.exit(0)

    if args.fetch:
        fetch_and_snapshot()

    if args.features:
        dt = args.history if args.history else date.today().strftime("%Y-%m-%d")
        feats = extract_movement_features(dt)
        if feats:
            print("\n--- Movement Features ---")
            for key, f in feats.items():
                flags = []
                if f["steam_detected"]:
                    flags.append(f"STEAM->{f['steam_direction']}")
                if f["reverse_line_movement"]:
                    flags.append("RLM")
                flag_str = f"  [{', '.join(flags)}]" if flags else ""
                print(f"  {key}: ML {f['opening_ml_home']}->{f['current_ml_home']}  "
                      f"move={f['ml_move_pct']}%  dir={f['ml_direction']}  "
                      f"n_moves={f['n_moves']}{flag_str}")

    if args.history:
        show_history(args.history)

    print("\n# Cron: */120 * * * * cd /home/termius/mon-ipad && python3 scripts/odds_movement_tracker.py --fetch >> /tmp/odds-tracker.log 2>&1")


"""
FEATURE ENGINE INTEGRATION — Category 50: Line Movement
Add to features/engine.py build() method:

Features to add per game:
- cat50_opening_implied_prob
- cat50_current_implied_prob
- cat50_line_move_pct
- cat50_steam_flag
- cat50_sharp_divergence
- cat50_reverse_line_movement
- cat50_spread_move
- cat50_total_move
- cat50_consensus_strength

These features capture market information flow:
- Opening lines reflect overnight analysis + injury news
- Early moves reflect sharp/syndicate money
- Late moves reflect public/recreational money
- Steam = concentrated sharp action on one side
- Sharp divergence = when money% differs from ticket%
"""
