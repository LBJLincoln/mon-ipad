#!/usr/bin/env python3
"""
prepare_data.py — Download and prepare comprehensive NBA datasets for the HF LLM Trading Floor.

Creates 6 data files in data/:
  1. rosters-2025-26.json         — All 30 team rosters via nba_api
  2. team-advanced-2025-26.json   — Advanced team stats (OFF/DEF rating, pace, etc.)
  3. player-stats-2025-26.json    — Player season averages from existing CSV
  4. full-odds-2025-26.json       — 100+ derived betting categories per game
  5. model-predictions-2025-26.json — Compiled agent predictions with consensus
  6. strategies.json              — 22 SOTA betting strategies

Usage:
    python prepare_data.py
"""

import csv
import glob
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
MONO_ROOT = Path("/home/termius/mon-ipad")
PLAYER_STATS_CSV = MONO_ROOT / "data" / "player-tracking" / "player_stats_2025-26.csv"
ODDS_CSV = DATA_DIR / "nba_2025-26_odds.csv"
PREDICTIONS_DIR = MONO_ROOT / "data" / "arena" / "predictions-v5"

# Ensure output directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Team name -> abbreviation map
# ---------------------------------------------------------------------------
TEAM_MAP = {
    "Los Angeles Lakers": "LAL", "Los Angeles Clippers": "LAC",
    "Golden State Warriors": "GSW", "Boston Celtics": "BOS",
    "Oklahoma City Thunder": "OKC", "Houston Rockets": "HOU",
    "Cleveland Cavaliers": "CLE", "New York Knicks": "NYK",
    "Milwaukee Bucks": "MIL", "Denver Nuggets": "DEN",
    "Phoenix Suns": "PHX", "Dallas Mavericks": "DAL",
    "Memphis Grizzlies": "MEM", "Minnesota Timberwolves": "MIN",
    "Sacramento Kings": "SAC", "Indiana Pacers": "IND",
    "Miami Heat": "MIA", "Philadelphia 76ers": "PHI",
    "Orlando Magic": "ORL", "Atlanta Hawks": "ATL",
    "Chicago Bulls": "CHI", "Toronto Raptors": "TOR",
    "Brooklyn Nets": "BKN", "San Antonio Spurs": "SAS",
    "Detroit Pistons": "DET", "Charlotte Hornets": "CHA",
    "Portland Trail Blazers": "POR", "New Orleans Pelicans": "NOP",
    "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}
TEAM_MAP_REV = {v: k for k, v in TEAM_MAP.items()}


# ===================================================================
# 1. Team Rosters
# ===================================================================
def fetch_rosters():
    """Download all 30 NBA team rosters via nba_api."""
    print("\n[1/6] Fetching team rosters via nba_api...")
    try:
        from nba_api.stats.endpoints import commonteamroster
        from nba_api.stats.static import teams as nba_teams
    except ImportError:
        print("  WARNING: nba_api not installed. Generating placeholder rosters.")
        return _generate_placeholder_rosters()

    all_teams = nba_teams.get_teams()
    # Build id -> abbreviation map
    id_to_abbr = {t["id"]: t["abbreviation"] for t in all_teams}

    rosters = {}
    for team in sorted(all_teams, key=lambda t: t["abbreviation"]):
        abbr = team["abbreviation"]
        team_id = team["id"]
        print(f"  Fetching {abbr} ({team['full_name']})...")
        try:
            roster = commonteamroster.CommonTeamRoster(
                team_id=team_id, season="2025-26"
            )
            rows = roster.get_normalized_dict()["CommonTeamRoster"]
            players = []
            for r in rows:
                players.append({
                    "name": r.get("PLAYER", r.get("PLAYER_NAME", "")),
                    "player_id": r.get("PLAYER_ID", ""),
                    "position": r.get("POSITION", ""),
                    "number": r.get("NUM", ""),
                    "height": r.get("HEIGHT", ""),
                    "weight": r.get("WEIGHT", ""),
                    "age": r.get("AGE", None),
                    "experience": r.get("EXP", r.get("SEASON_EXP", "")),
                    "school": r.get("SCHOOL", ""),
                })
            rosters[abbr] = {
                "team_name": team["full_name"],
                "team_id": team_id,
                "player_count": len(players),
                "players": players,
            }
        except Exception as e:
            print(f"  ERROR fetching {abbr}: {e}")
            rosters[abbr] = {"team_name": team["full_name"], "team_id": team_id, "players": [], "error": str(e)}
        time.sleep(1)  # Rate limit

    out = DATA_DIR / "rosters-2025-26.json"
    with open(out, "w") as f:
        json.dump(rosters, f, indent=2)
    print(f"  Saved {out} ({len(rosters)} teams)")
    return rosters


def _generate_placeholder_rosters():
    """Fallback if nba_api unavailable — create stubs so downstream works."""
    rosters = {}
    for full_name, abbr in TEAM_MAP.items():
        rosters[abbr] = {
            "team_name": full_name,
            "team_id": None,
            "player_count": 0,
            "players": [],
            "_placeholder": True,
        }
    out = DATA_DIR / "rosters-2025-26.json"
    with open(out, "w") as f:
        json.dump(rosters, f, indent=2)
    print(f"  Saved placeholder {out} ({len(rosters)} teams)")
    return rosters


# ===================================================================
# 2. Advanced Team Stats
# ===================================================================
def fetch_team_advanced():
    """Fetch advanced team stats (OFF_RATING, DEF_RATING, PACE, etc.)."""
    print("\n[2/6] Fetching advanced team stats via nba_api...")
    try:
        from nba_api.stats.endpoints import leaguedashteamstats
        from nba_api.stats.static import teams as nba_teams
    except ImportError:
        print("  WARNING: nba_api not installed. Generating placeholder stats.")
        return _generate_placeholder_team_advanced()

    all_teams = nba_teams.get_teams()
    id_to_abbr = {t["id"]: t["abbreviation"] for t in all_teams}

    try:
        stats = leaguedashteamstats.LeagueDashTeamStats(
            season="2025-26",
            measure_type_detailed_defense="Advanced",
            per_mode_detailed="PerGame",
        )
        rows = stats.get_normalized_dict()["LeagueDashTeamStats"]
    except Exception as e:
        print(f"  ERROR fetching advanced stats: {e}")
        return _generate_placeholder_team_advanced()

    time.sleep(1)

    WANTED_FIELDS = [
        "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE",
        "AST_PCT", "REB_PCT", "E_OFF_RATING", "E_DEF_RATING",
        "TS_PCT", "EFG_PCT", "AST_RATIO", "AST_TO",
        "OREB_PCT", "DREB_PCT", "TM_TOV_PCT",
        "GP", "W", "L", "W_PCT", "MIN",
    ]

    advanced = {}
    for row in rows:
        team_id = row.get("TEAM_ID")
        abbr = id_to_abbr.get(team_id, row.get("TEAM_ABBREVIATION", "???"))
        entry = {"team_name": row.get("TEAM_NAME", ""), "team_id": team_id}
        for field in WANTED_FIELDS:
            if field in row:
                entry[field] = row[field]
        # Also grab anything else that looks useful
        for k, v in row.items():
            if k not in entry and isinstance(v, (int, float)) and k not in ("TEAM_ID", "CFID", "CFPARAMS"):
                entry[k] = v
        advanced[abbr] = entry

    out = DATA_DIR / "team-advanced-2025-26.json"
    with open(out, "w") as f:
        json.dump(advanced, f, indent=2)
    print(f"  Saved {out} ({len(advanced)} teams)")
    return advanced


def _generate_placeholder_team_advanced():
    """Fallback placeholder advanced stats."""
    advanced = {}
    for full_name, abbr in TEAM_MAP.items():
        advanced[abbr] = {
            "team_name": full_name,
            "OFF_RATING": 110.0, "DEF_RATING": 110.0, "NET_RATING": 0.0,
            "PACE": 100.0, "AST_PCT": 0.60, "REB_PCT": 0.50,
            "E_OFF_RATING": 110.0, "E_DEF_RATING": 110.0,
            "TS_PCT": 0.56, "EFG_PCT": 0.52,
            "_placeholder": True,
        }
    out = DATA_DIR / "team-advanced-2025-26.json"
    with open(out, "w") as f:
        json.dump(advanced, f, indent=2)
    print(f"  Saved placeholder {out}")
    return advanced


# ===================================================================
# 3. Player Season Averages (from existing CSV)
# ===================================================================
def compile_player_stats():
    """Read player_stats_2025-26.csv and compile per-team JSON."""
    print("\n[3/6] Compiling player season averages...")
    if not PLAYER_STATS_CSV.exists():
        print(f"  WARNING: {PLAYER_STATS_CSV} not found. Creating empty file.")
        out = DATA_DIR / "player-stats-2025-26.json"
        with open(out, "w") as f:
            json.dump({}, f, indent=2)
        return {}

    players_by_team = defaultdict(list)
    with open(PLAYER_STATS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            team_abbr = row.get("TEAM_ABBREVIATION", "")
            if not team_abbr:
                continue

            def safe_float(key, default=0.0):
                try:
                    return float(row.get(key, default))
                except (ValueError, TypeError):
                    return default

            def safe_int(key, default=0):
                try:
                    return int(float(row.get(key, default)))
                except (ValueError, TypeError):
                    return default

            player = {
                "name": row.get("PLAYER_NAME", "Unknown"),
                "player_id": row.get("PLAYER_ID", ""),
                "age": safe_float("AGE"),
                "GP": safe_int("GP"),
                "PPG": safe_float("PTS"),
                "RPG": safe_float("REB"),
                "APG": safe_float("AST"),
                "SPG": safe_float("STL"),
                "BPG": safe_float("BLK"),
                "FG_PCT": safe_float("FG_PCT"),
                "FG3_PCT": safe_float("FG3_PCT"),
                "FT_PCT": safe_float("FT_PCT"),
                "MIN": safe_float("MIN"),
                "PLUS_MINUS": safe_float("PLUS_MINUS"),
                "TOV": safe_float("TOV"),
                "FGM": safe_float("FGM"),
                "FGA": safe_float("FGA"),
                "FG3M": safe_float("FG3M"),
                "FG3A": safe_float("FG3A"),
                "FTM": safe_float("FTM"),
                "FTA": safe_float("FTA"),
                "OREB": safe_float("OREB"),
                "DREB": safe_float("DREB"),
                "PF": safe_float("PF"),
            }
            players_by_team[team_abbr].append(player)

    # Sort players within each team by PPG descending
    result = {}
    for team, players in sorted(players_by_team.items()):
        players.sort(key=lambda p: p["PPG"], reverse=True)
        result[team] = {
            "player_count": len(players),
            "team_ppg": round(sum(p["PPG"] for p in players if p["GP"] >= 20) / max(1, sum(1 for p in players if p["GP"] >= 20)), 1),
            "players": players,
        }

    out = DATA_DIR / "player-stats-2025-26.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  Saved {out} ({len(result)} teams, {sum(len(v['players']) for v in result.values())} players)")
    return result


# ===================================================================
# 4. Derived Odds Categories (100+ per game)
# ===================================================================

def _american_to_implied(american):
    """Convert American odds to implied probability."""
    if american is None or american == 0:
        return 0.5
    if american > 0:
        return 100.0 / (american + 100.0)
    else:
        return abs(american) / (abs(american) + 100.0)


def _implied_to_american(prob):
    """Convert implied probability to American odds."""
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return round(-prob / (1 - prob) * 100)
    else:
        return round((1 - prob) / prob * 100)


def _shift_american_odds(base_american, points_shift, cents_per_point=18):
    """
    Shift American odds by a number of points.
    Positive points_shift = making the bet harder (e.g., tighter spread for favorite).
    cents_per_point ~18 on American odds scale.
    """
    if base_american is None:
        return -110
    base_prob = _american_to_implied(base_american)
    # Each point of shift changes implied probability by ~1.8%
    prob_shift = points_shift * 0.018
    new_prob = max(0.05, min(0.95, base_prob + prob_shift))
    return _implied_to_american(new_prob)


def _juice_line(fair_prob, juice=0.05):
    """Add juice (vig) to a fair probability and return American odds."""
    juiced = min(0.95, fair_prob + juice / 2)
    return _implied_to_american(juiced)


def derive_odds_categories(row):
    """
    Given a single odds row (dict from CSV), derive 100+ betting categories.
    Returns a dict of category_name -> {odds, implied_prob, description}.
    """
    cats = {}

    def safe_float(val, default=None):
        try:
            v = float(val)
            return v if not math.isnan(v) else default
        except (ValueError, TypeError):
            return default

    ml_home = safe_float(row.get("moneyline_home"))
    ml_away = safe_float(row.get("moneyline_away"))
    spread_home = safe_float(row.get("spread_home"))
    total = safe_float(row.get("total"))

    home_team_full = row.get("home_team", "")
    away_team_full = row.get("away_team", "")
    home = TEAM_MAP.get(home_team_full, home_team_full[:3].upper())
    away = TEAM_MAP.get(away_team_full, away_team_full[:3].upper())

    # Handle decimal odds (bovada) — convert to American
    if ml_home is not None and 1.0 < ml_home < 20.0:
        # This is decimal odds, convert to American
        if ml_home >= 2.0:
            ml_home = round((ml_home - 1) * 100)
        else:
            ml_home = round(-100 / (ml_home - 1))
    if ml_away is not None and 1.0 < ml_away < 20.0:
        if ml_away >= 2.0:
            ml_away = round((ml_away - 1) * 100)
        else:
            ml_away = round(-100 / (ml_away - 1))

    # Skip rows with no usable odds
    if ml_home is None and ml_away is None and spread_home is None and total is None:
        return None

    # Default spread/total if missing
    if spread_home is None:
        # Estimate from moneyline if available
        if ml_home is not None and ml_away is not None:
            home_prob = _american_to_implied(ml_home)
            # Rough conversion: spread ≈ (prob - 0.5) * 13
            spread_home = round((home_prob - 0.5) * 13, 1)
        else:
            spread_home = 0.0

    if total is None:
        total = 224.0  # NBA average

    if ml_home is None:
        ml_home = _implied_to_american(0.5 + spread_home * 0.018)
    if ml_away is None:
        ml_away = _implied_to_american(0.5 - spread_home * 0.018)

    spread_away = -spread_home

    # ---------------------------------------------------------------
    # BASE (6 categories)
    # ---------------------------------------------------------------
    cats["ml_home"] = {"odds": ml_home, "implied_prob": round(_american_to_implied(ml_home), 4), "desc": f"{home} moneyline"}
    cats["ml_away"] = {"odds": ml_away, "implied_prob": round(_american_to_implied(ml_away), 4), "desc": f"{away} moneyline"}
    cats["spread_home"] = {"line": spread_home, "odds": -110, "implied_prob": 0.5238, "desc": f"{home} {spread_home:+.1f}"}
    cats["spread_away"] = {"line": spread_away, "odds": -110, "implied_prob": 0.5238, "desc": f"{away} {spread_away:+.1f}"}
    cats["total_over"] = {"line": total, "odds": -110, "implied_prob": 0.5238, "desc": f"Over {total}"}
    cats["total_under"] = {"line": total, "odds": -110, "implied_prob": 0.5238, "desc": f"Under {total}"}

    # ---------------------------------------------------------------
    # ALTERNATE SPREADS (20 categories)
    # ---------------------------------------------------------------
    alt_spread_points = [1.5, 3.5, 5.5, 7.5, 10.5]
    for pts in alt_spread_points:
        # Home getting fewer points (harder for home)
        new_line_home = spread_home - pts  # tighter
        odds_home = _shift_american_odds(ml_home, -pts)
        cats[f"alt_spread_home_minus{pts}"] = {
            "line": round(new_line_home, 1), "odds": odds_home,
            "implied_prob": round(_american_to_implied(odds_home), 4),
            "desc": f"{home} {new_line_home:+.1f} (alt)"
        }
        # Home getting more points (easier for home)
        new_line_home2 = spread_home + pts
        odds_home2 = _shift_american_odds(ml_home, pts)
        cats[f"alt_spread_home_plus{pts}"] = {
            "line": round(new_line_home2, 1), "odds": odds_home2,
            "implied_prob": round(_american_to_implied(odds_home2), 4),
            "desc": f"{home} {new_line_home2:+.1f} (alt)"
        }
        # Away getting fewer/more
        new_line_away = spread_away + pts  # tighter for away
        odds_away = _shift_american_odds(ml_away, -pts)
        cats[f"alt_spread_away_plus{pts}"] = {
            "line": round(new_line_away, 1), "odds": odds_away,
            "implied_prob": round(_american_to_implied(odds_away), 4),
            "desc": f"{away} {new_line_away:+.1f} (alt)"
        }
        new_line_away2 = spread_away - pts
        odds_away2 = _shift_american_odds(ml_away, pts)
        cats[f"alt_spread_away_minus{pts}"] = {
            "line": round(new_line_away2, 1), "odds": odds_away2,
            "implied_prob": round(_american_to_implied(odds_away2), 4),
            "desc": f"{away} {new_line_away2:+.1f} (alt)"
        }

    # ---------------------------------------------------------------
    # ALTERNATE TOTALS (8 categories)
    # ---------------------------------------------------------------
    for shift in [-5, -3, 3, 5]:
        alt_total = total + shift
        direction = "higher" if shift > 0 else "lower"
        # Over on higher total = harder, so shift odds
        over_odds = _shift_american_odds(-110, -shift)  # harder over when total raised
        under_odds = _shift_american_odds(-110, shift)
        cats[f"alt_total_over_{'+' if shift>0 else ''}{shift}"] = {
            "line": alt_total, "odds": over_odds,
            "implied_prob": round(_american_to_implied(over_odds), 4),
            "desc": f"Over {alt_total} ({direction} alt)"
        }
        cats[f"alt_total_under_{'+' if shift>0 else ''}{shift}"] = {
            "line": alt_total, "odds": under_odds,
            "implied_prob": round(_american_to_implied(under_odds), 4),
            "desc": f"Under {alt_total} ({direction} alt)"
        }

    # ---------------------------------------------------------------
    # TEAM TOTALS (4 categories)
    # ---------------------------------------------------------------
    home_total = round((total - spread_home) / 2, 1)
    away_total = round((total + spread_home) / 2, 1)
    cats["home_total_over"] = {"line": home_total, "odds": -110, "implied_prob": 0.5238, "desc": f"{home} over {home_total}"}
    cats["home_total_under"] = {"line": home_total, "odds": -110, "implied_prob": 0.5238, "desc": f"{home} under {home_total}"}
    cats["away_total_over"] = {"line": away_total, "odds": -110, "implied_prob": 0.5238, "desc": f"{away} over {away_total}"}
    cats["away_total_under"] = {"line": away_total, "odds": -110, "implied_prob": 0.5238, "desc": f"{away} under {away_total}"}

    # ---------------------------------------------------------------
    # FIRST HALF (4 categories)
    # ---------------------------------------------------------------
    h1_spread = round(spread_home / 2, 1)
    h1_total = round(total / 2, 1)
    h1_ml_home_prob = _american_to_implied(ml_home) * 0.85 + 0.5 * 0.15  # Regress toward 50%
    h1_ml_away_prob = 1 - h1_ml_home_prob
    cats["h1_spread"] = {"line": h1_spread, "odds": -110, "implied_prob": 0.5238, "desc": f"1H {home} {h1_spread:+.1f}"}
    cats["h1_total"] = {"line": h1_total, "odds": -110, "implied_prob": 0.5238, "desc": f"1H over/under {h1_total}"}
    cats["h1_ml_home"] = {"odds": _implied_to_american(h1_ml_home_prob), "implied_prob": round(h1_ml_home_prob, 4), "desc": f"1H {home} ML"}
    cats["h1_ml_away"] = {"odds": _implied_to_american(h1_ml_away_prob), "implied_prob": round(h1_ml_away_prob, 4), "desc": f"1H {away} ML"}

    # ---------------------------------------------------------------
    # QUARTER (3 categories)
    # ---------------------------------------------------------------
    q1_total = round(total / 4, 1)
    q1_ml_home_prob = _american_to_implied(ml_home) * 0.70 + 0.5 * 0.30  # More regression for quarters
    q1_ml_away_prob = 1 - q1_ml_home_prob
    cats["q1_total"] = {"line": q1_total, "odds": -110, "implied_prob": 0.5238, "desc": f"Q1 over/under {q1_total}"}
    cats["q1_ml_home"] = {"odds": _implied_to_american(q1_ml_home_prob), "implied_prob": round(q1_ml_home_prob, 4), "desc": f"Q1 {home} ML"}
    cats["q1_ml_away"] = {"odds": _implied_to_american(q1_ml_away_prob), "implied_prob": round(q1_ml_away_prob, 4), "desc": f"Q1 {away} ML"}

    # ---------------------------------------------------------------
    # SECOND HALF (4 categories)
    # ---------------------------------------------------------------
    h2_spread = round(spread_home / 2, 1)
    h2_total = round(total / 2, 1)
    cats["h2_spread"] = {"line": h2_spread, "odds": -110, "implied_prob": 0.5238, "desc": f"2H {home} {h2_spread:+.1f}"}
    cats["h2_total"] = {"line": h2_total, "odds": -110, "implied_prob": 0.5238, "desc": f"2H over/under {h2_total}"}
    h2_ml_home_prob = h1_ml_home_prob  # Similar regression
    cats["h2_ml_home"] = {"odds": _implied_to_american(h2_ml_home_prob), "implied_prob": round(h2_ml_home_prob, 4), "desc": f"2H {home} ML"}
    cats["h2_ml_away"] = {"odds": _implied_to_american(1 - h2_ml_home_prob), "implied_prob": round(1 - h2_ml_home_prob, 4), "desc": f"2H {away} ML"}

    # ---------------------------------------------------------------
    # QUARTERS 2-4 (9 more categories)
    # ---------------------------------------------------------------
    for q in [2, 3, 4]:
        q_total = round(total / 4, 1)
        q_prob = _american_to_implied(ml_home) * 0.70 + 0.5 * 0.30
        cats[f"q{q}_total"] = {"line": q_total, "odds": -110, "implied_prob": 0.5238, "desc": f"Q{q} over/under {q_total}"}
        cats[f"q{q}_ml_home"] = {"odds": _implied_to_american(q_prob), "implied_prob": round(q_prob, 4), "desc": f"Q{q} {home} ML"}
        cats[f"q{q}_ml_away"] = {"odds": _implied_to_american(1 - q_prob), "implied_prob": round(1 - q_prob, 4), "desc": f"Q{q} {away} ML"}

    # ---------------------------------------------------------------
    # DERIVED GAME PROPS (7+ categories)
    # ---------------------------------------------------------------
    # Both teams over 100 — depends on total
    both_100_fair = max(0.05, min(0.95, (total - 200) / 50))  # Rough: at total=225, ~50%
    cats["both_teams_over_100"] = {
        "odds": _implied_to_american(both_100_fair),
        "implied_prob": round(both_100_fair, 4),
        "desc": "Both teams score 100+"
    }

    # Margin categories (based on spread)
    home_prob = _american_to_implied(ml_home)
    abs_spread = abs(spread_home)

    # Margin 1-5 (close game)
    m1_5_prob = max(0.05, 0.30 - abs_spread * 0.01)
    cats["margin_1_5"] = {"odds": _implied_to_american(m1_5_prob), "implied_prob": round(m1_5_prob, 4), "desc": "Margin 1-5 points"}

    # Margin 6-10
    m6_10_prob = max(0.05, 0.25 - abs(abs_spread - 8) * 0.015)
    cats["margin_6_10"] = {"odds": _implied_to_american(m6_10_prob), "implied_prob": round(m6_10_prob, 4), "desc": "Margin 6-10 points"}

    # Margin 11-15
    m11_15_prob = max(0.05, 0.20 - abs(abs_spread - 13) * 0.015)
    cats["margin_11_15"] = {"odds": _implied_to_american(m11_15_prob), "implied_prob": round(m11_15_prob, 4), "desc": "Margin 11-15 points"}

    # Margin 16-20
    m16_20_prob = max(0.05, 0.12 - abs(abs_spread - 18) * 0.01)
    cats["margin_16_20"] = {"odds": _implied_to_american(m16_20_prob), "implied_prob": round(m16_20_prob, 4), "desc": "Margin 16-20 points"}

    # Margin 21+
    m21p_prob = max(0.05, 0.08 + max(0, abs_spread - 15) * 0.015)
    cats["margin_21plus"] = {"odds": _implied_to_american(m21p_prob), "implied_prob": round(m21p_prob, 4), "desc": "Margin 21+ points"}

    # Overtime
    ot_prob = 0.065  # ~6.5% of NBA games go to OT
    cats["overtime_yes"] = {"odds": _implied_to_american(ot_prob), "implied_prob": round(ot_prob, 4), "desc": "Game goes to overtime"}

    # ---------------------------------------------------------------
    # ADDITIONAL PROPS (to reach 100+ total)
    # ---------------------------------------------------------------
    # Double result (halftime/fulltime)
    cats["double_result_hh"] = {"odds": _implied_to_american(home_prob * 0.75), "implied_prob": round(home_prob * 0.75, 4), "desc": f"{home}/{home} (HT/FT)"}
    cats["double_result_ha"] = {"odds": _implied_to_american(home_prob * 0.15), "implied_prob": round(home_prob * 0.15, 4), "desc": f"{home}/{away} (HT/FT)"}
    cats["double_result_ah"] = {"odds": _implied_to_american((1-home_prob) * 0.15), "implied_prob": round((1-home_prob) * 0.15, 4), "desc": f"{away}/{home} (HT/FT)"}
    cats["double_result_aa"] = {"odds": _implied_to_american((1-home_prob) * 0.75), "implied_prob": round((1-home_prob) * 0.75, 4), "desc": f"{away}/{away} (HT/FT)"}

    # Race markets
    race_20_home_prob = home_prob * 0.55 + 0.5 * 0.45
    cats["race_to_20_home"] = {"odds": _implied_to_american(race_20_home_prob), "implied_prob": round(race_20_home_prob, 4), "desc": f"{home} first to 20"}
    cats["race_to_20_away"] = {"odds": _implied_to_american(1 - race_20_home_prob), "implied_prob": round(1 - race_20_home_prob, 4), "desc": f"{away} first to 20"}

    # Highest scoring quarter
    for q in [1, 2, 3, 4]:
        prob = 0.28 if q in [1, 3] else 0.22  # Q1/Q3 slightly more scoring usually
        cats[f"highest_scoring_q{q}"] = {"odds": _implied_to_american(prob), "implied_prob": round(prob, 4), "desc": f"Q{q} is highest scoring"}

    # Odd/even total
    cats["total_odd"] = {"odds": -110, "implied_prob": 0.5238, "desc": "Total points odd"}
    cats["total_even"] = {"odds": -110, "implied_prob": 0.5238, "desc": "Total points even"}

    # Lead after Q1
    cats["lead_q1_home"] = {"odds": _implied_to_american(q1_ml_home_prob), "implied_prob": round(q1_ml_home_prob, 4), "desc": f"{home} leads after Q1"}
    cats["lead_q1_away"] = {"odds": _implied_to_american(q1_ml_away_prob), "implied_prob": round(q1_ml_away_prob, 4), "desc": f"{away} leads after Q1"}
    cats["lead_q1_tie"] = {"odds": _implied_to_american(0.08), "implied_prob": 0.08, "desc": "Tied after Q1"}

    # Blowout (15+ margin)
    blowout_prob = max(0.05, 0.15 + abs_spread * 0.01)
    cats["blowout_15plus"] = {"odds": _implied_to_american(blowout_prob), "implied_prob": round(blowout_prob, 4), "desc": "Margin 15+ (blowout)"}

    # Triple double in game
    cats["triple_double_yes"] = {"odds": _implied_to_american(0.18), "implied_prob": 0.18, "desc": "Any triple-double in game"}

    # Both teams 110+ (high scoring)
    both_110_prob = max(0.05, min(0.90, (total - 220) / 30))
    cats["both_teams_110plus"] = {"odds": _implied_to_american(both_110_prob), "implied_prob": round(both_110_prob, 4), "desc": "Both teams score 110+"}

    # 3-pointers total markets
    expected_3s = total * 0.14  # ~14% of total scoring from 3s (rough)
    cats["total_3pm_over"] = {"line": round(expected_3s, 1), "odds": -110, "implied_prob": 0.5238, "desc": f"Total 3PM over {round(expected_3s, 1)}"}
    cats["total_3pm_under"] = {"line": round(expected_3s, 1), "odds": -110, "implied_prob": 0.5238, "desc": f"Total 3PM under {round(expected_3s, 1)}"}

    # Free throw markets
    expected_ft = total * 0.08
    cats["total_ft_over"] = {"line": round(expected_ft, 1), "odds": -110, "implied_prob": 0.5238, "desc": f"Total FT made over {round(expected_ft, 1)}"}
    cats["total_ft_under"] = {"line": round(expected_ft, 1), "odds": -110, "implied_prob": 0.5238, "desc": f"Total FT made under {round(expected_ft, 1)}"}

    # Rebounds total
    expected_reb = 88.0  # NBA average ~44 per team
    cats["total_rebounds_over"] = {"line": expected_reb, "odds": -110, "implied_prob": 0.5238, "desc": f"Total rebounds over {expected_reb}"}
    cats["total_rebounds_under"] = {"line": expected_reb, "odds": -110, "implied_prob": 0.5238, "desc": f"Total rebounds under {expected_reb}"}

    # Assists total
    expected_ast = 50.0
    cats["total_assists_over"] = {"line": expected_ast, "odds": -110, "implied_prob": 0.5238, "desc": f"Total assists over {expected_ast}"}
    cats["total_assists_under"] = {"line": expected_ast, "odds": -110, "implied_prob": 0.5238, "desc": f"Total assists under {expected_ast}"}

    # Pace-related
    cats["pace_over_100"] = {"odds": -150, "implied_prob": 0.60, "desc": "Combined pace over 100 possessions"}
    cats["pace_under_95"] = {"odds": 200, "implied_prob": 0.33, "desc": "Combined pace under 95 possessions"}

    # Parlay combinations (synthetic)
    parlay_ml_over_prob = _american_to_implied(ml_home) * 0.5
    cats["sgp_home_ml_over"] = {"odds": _implied_to_american(parlay_ml_over_prob), "implied_prob": round(parlay_ml_over_prob, 4), "desc": f"SGP: {home} ML + Over {total}"}
    parlay_ml_under_prob = _american_to_implied(ml_home) * 0.5
    cats["sgp_home_ml_under"] = {"odds": _implied_to_american(parlay_ml_under_prob), "implied_prob": round(parlay_ml_under_prob, 4), "desc": f"SGP: {home} ML + Under {total}"}
    parlay_away_over_prob = _american_to_implied(ml_away) * 0.5
    cats["sgp_away_ml_over"] = {"odds": _implied_to_american(parlay_away_over_prob), "implied_prob": round(parlay_away_over_prob, 4), "desc": f"SGP: {away} ML + Over {total}"}
    parlay_away_under_prob = _american_to_implied(ml_away) * 0.5
    cats["sgp_away_ml_under"] = {"odds": _implied_to_american(parlay_away_under_prob), "implied_prob": round(parlay_away_under_prob, 4), "desc": f"SGP: {away} ML + Under {total}"}

    # Teaser markets
    teaser_6_home_line = spread_home + 6
    teaser_6_away_line = spread_away + 6
    cats["teaser_6pt_home"] = {"line": round(teaser_6_home_line, 1), "odds": -130, "implied_prob": 0.5652, "desc": f"6pt teaser: {home} {teaser_6_home_line:+.1f}"}
    cats["teaser_6pt_away"] = {"line": round(teaser_6_away_line, 1), "odds": -130, "implied_prob": 0.5652, "desc": f"6pt teaser: {away} {teaser_6_away_line:+.1f}"}
    teaser_7_home_line = spread_home + 7
    teaser_7_away_line = spread_away + 7
    cats["teaser_7pt_home"] = {"line": round(teaser_7_home_line, 1), "odds": -150, "implied_prob": 0.60, "desc": f"7pt teaser: {home} {teaser_7_home_line:+.1f}"}
    cats["teaser_7pt_away"] = {"line": round(teaser_7_away_line, 1), "odds": -150, "implied_prob": 0.60, "desc": f"7pt teaser: {away} {teaser_7_away_line:+.1f}"}

    # Exact margin bands (more granular)
    cats["margin_exact_1"] = {"odds": 700, "implied_prob": 0.0625, "desc": "Exact margin = 1"}
    cats["margin_exact_2"] = {"odds": 700, "implied_prob": 0.0625, "desc": "Exact margin = 2"}
    cats["margin_exact_3"] = {"odds": 600, "implied_prob": 0.0714, "desc": "Exact margin = 3"}

    # Home/away specific margins
    cats["home_wins_by_1_5"] = {"odds": _implied_to_american(home_prob * m1_5_prob), "implied_prob": round(home_prob * m1_5_prob, 4), "desc": f"{home} wins by 1-5"}
    cats["home_wins_by_6_10"] = {"odds": _implied_to_american(home_prob * m6_10_prob), "implied_prob": round(home_prob * m6_10_prob, 4), "desc": f"{home} wins by 6-10"}
    cats["away_wins_by_1_5"] = {"odds": _implied_to_american((1-home_prob) * m1_5_prob), "implied_prob": round((1-home_prob) * m1_5_prob, 4), "desc": f"{away} wins by 1-5"}
    cats["away_wins_by_6_10"] = {"odds": _implied_to_american((1-home_prob) * m6_10_prob), "implied_prob": round((1-home_prob) * m6_10_prob, 4), "desc": f"{away} wins by 6-10"}

    return cats


def compile_full_odds():
    """Read odds CSV and derive 100+ categories per game."""
    print("\n[4/6] Deriving full odds categories (100+ per game)...")
    if not ODDS_CSV.exists():
        print(f"  WARNING: {ODDS_CSV} not found. Creating empty file.")
        out = DATA_DIR / "full-odds-2025-26.json"
        with open(out, "w") as f:
            json.dump({}, f, indent=2)
        return {}

    # Read all rows, pick best row per game (prefer betmgm, prefer rows with spread+total)
    games_raw = defaultdict(list)
    with open(ODDS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get("date", "")
            home_full = row.get("home_team", "")
            away_full = row.get("away_team", "")
            home = TEAM_MAP.get(home_full, home_full[:3].upper() if home_full else "???")
            away = TEAM_MAP.get(away_full, away_full[:3].upper() if away_full else "???")
            game_key = f"{date}_{away}@{home}"
            games_raw[game_key].append(row)

    all_odds = {}
    for game_key, rows in sorted(games_raw.items()):
        # Pick best row: prefer one with spread AND total, then betmgm
        def row_quality(r):
            score = 0
            if r.get("spread_home") and r["spread_home"].strip():
                score += 10
            if r.get("total") and r["total"].strip():
                score += 10
            if r.get("book", "") == "betmgm":
                score += 5
            if r.get("source", "") == "mgm_kaggle":
                score += 3
            return score

        best_row = max(rows, key=row_quality)
        cats = derive_odds_categories(best_row)
        if cats is None:
            continue

        all_odds[game_key] = {
            "date": best_row.get("date", ""),
            "home_team": TEAM_MAP.get(best_row.get("home_team", ""), "???"),
            "away_team": TEAM_MAP.get(best_row.get("away_team", ""), "???"),
            "source_book": best_row.get("book", ""),
            "category_count": len(cats),
            "categories": cats,
        }

    out = DATA_DIR / "full-odds-2025-26.json"
    with open(out, "w") as f:
        json.dump(all_odds, f, indent=2)

    # Stats
    cat_counts = [v["category_count"] for v in all_odds.values()]
    avg_cats = sum(cat_counts) / max(1, len(cat_counts))
    print(f"  Saved {out} ({len(all_odds)} games, avg {avg_cats:.0f} categories/game, min={min(cat_counts, default=0)}, max={max(cat_counts, default=0)})")
    return all_odds


# ===================================================================
# 5. Model Predictions Compiled
# ===================================================================
def compile_predictions():
    """Read all predictions-v5 files and compile consensus per game."""
    print("\n[5/6] Compiling model predictions and consensus...")
    if not PREDICTIONS_DIR.exists():
        print(f"  WARNING: {PREDICTIONS_DIR} not found. Creating empty file.")
        out = DATA_DIR / "model-predictions-2025-26.json"
        with open(out, "w") as f:
            json.dump({}, f, indent=2)
        return {}

    pred_files = sorted(glob.glob(str(PREDICTIONS_DIR / "predictions-*.json")))
    print(f"  Found {len(pred_files)} prediction files")

    # Aggregate: game_key -> category -> list of (agent, direction, confidence, edge)
    game_preds = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    agent_counts = defaultdict(int)

    for fpath in pred_files:
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  WARNING: Could not read {fpath}: {e}")
            continue

        for agent_id, games in data.items():
            if not isinstance(games, dict):
                continue
            for game_key, pred in games.items():
                if not isinstance(pred, dict):
                    continue
                if game_key.startswith("_"):
                    continue
                agent_counts[agent_id] += 1

                for cat in ["ml_fg", "spread_fg", "total_fg"]:
                    if cat in pred and isinstance(pred[cat], dict):
                        direction = pred[cat].get("direction", "")
                        confidence = pred[cat].get("confidence", 0.5)
                        edge = pred[cat].get("edge_pct", 0)
                        game_preds[game_key][cat]["entries"].append({
                            "agent": agent_id,
                            "direction": direction,
                            "confidence": confidence,
                            "edge": edge,
                        })

    # Build consensus per game
    compiled = {}
    for game_key in sorted(game_preds.keys()):
        game_data = {"game_key": game_key}
        total_agents_for_game = set()

        for cat in ["ml_fg", "spread_fg", "total_fg"]:
            entries = game_preds[game_key][cat].get("entries", [])
            if not entries:
                continue

            for e in entries:
                total_agents_for_game.add(e["agent"])

            # Count directions
            direction_counts = defaultdict(int)
            direction_confidences = defaultdict(list)
            direction_edges = defaultdict(list)
            for e in entries:
                d = e["direction"]
                direction_counts[d] += 1
                direction_confidences[d].append(e["confidence"])
                direction_edges[d].append(e["edge"])

            # Consensus = majority direction
            consensus_dir = max(direction_counts, key=direction_counts.get)
            agree_count = direction_counts[consensus_dir]
            total_count = len(entries)

            avg_confidence = sum(direction_confidences[consensus_dir]) / max(1, len(direction_confidences[consensus_dir]))
            avg_edge = sum(direction_edges[consensus_dir]) / max(1, len(direction_edges[consensus_dir]))

            prefix = cat.replace("_fg", "")  # ml, spread, total
            game_data[f"consensus_{prefix}_direction"] = consensus_dir
            game_data[f"consensus_{prefix}_confidence"] = round(avg_confidence, 4)
            game_data[f"consensus_{prefix}_edge"] = round(avg_edge, 2)
            game_data[f"{prefix}_agents_agreeing"] = agree_count
            game_data[f"{prefix}_total_agents"] = total_count
            game_data[f"{prefix}_agreement_pct"] = round(agree_count / max(1, total_count) * 100, 1)

            # Direction breakdown
            game_data[f"{prefix}_direction_breakdown"] = {
                d: {"count": c, "avg_confidence": round(sum(direction_confidences[d]) / max(1, len(direction_confidences[d])), 4)}
                for d, c in direction_counts.items()
            }

        game_data["total_unique_agents"] = len(total_agents_for_game)
        compiled[game_key] = game_data

    out = DATA_DIR / "model-predictions-2025-26.json"
    with open(out, "w") as f:
        json.dump(compiled, f, indent=2)
    print(f"  Saved {out} ({len(compiled)} games, {len(agent_counts)} unique agents across all files)")
    return compiled


# ===================================================================
# 6. SOTA Strategies
# ===================================================================
def save_strategies():
    """Save 22 SOTA betting strategies."""
    print("\n[6/6] Saving 22 SOTA betting strategies...")

    STRATEGIES = {
        "full_kelly": {
            "family": "kelly", "fraction": 1.0, "min_edge": 0.02, "max_pct": 0.25,
            "desc": "Full Kelly criterion - mathematically optimal but high variance. Bet fraction = edge/odds. Research: Kelly 1956."
        },
        "half_kelly": {
            "family": "kelly", "fraction": 0.5, "min_edge": 0.02, "max_pct": 0.15,
            "desc": "Half Kelly - 75% of optimal growth at 50% variance. Most recommended by professional bettors. Research: Thorp 2006."
        },
        "quarter_kelly": {
            "family": "kelly", "fraction": 0.25, "min_edge": 0.03, "max_pct": 0.08,
            "desc": "Quarter Kelly - conservative growth, very low ruin probability. Good for bankroll preservation."
        },
        "eighth_kelly": {
            "family": "kelly", "fraction": 0.125, "min_edge": 0.03, "max_pct": 0.05,
            "desc": "Eighth Kelly - ultra conservative. Near-zero ruin probability. For large bankrolls."
        },
        "flat_1pct": {
            "family": "flat", "bet_pct": 0.01, "min_edge": 0.01,
            "desc": "Flat 1% of bankroll per bet. Simple, predictable. Research: Ziemba 2017."
        },
        "flat_2pct": {
            "family": "flat", "bet_pct": 0.02, "min_edge": 0.01,
            "desc": "Flat 2% - moderate flat betting. Standard recreational approach."
        },
        "flat_5pct": {
            "family": "flat", "bet_pct": 0.05, "min_edge": 0.02,
            "desc": "Flat 5% - aggressive flat. Higher growth but higher drawdown risk."
        },
        "diversified_flat": {
            "family": "flat", "bet_pct": 0.01, "min_edge": 0.005,
            "desc": "Diversified flat 1% with low edge threshold. Spread bets across many games. Volume strategy."
        },
        "confidence_scaled": {
            "family": "confidence", "min_edge": 0.02, "max_pct": 0.20,
            "desc": "Scale bet size with confidence level. 0-100% confidence maps to 0-max_pct. Research: Prediction Arena 2604.07355."
        },
        "proportional_edge": {
            "family": "proportional", "min_edge": 0.02, "max_pct": 0.15, "multiplier": 3.0,
            "desc": "Bet size proportional to edge x multiplier. Larger edges = larger bets. Research: Benter 1994."
        },
        "ev_threshold_110": {
            "family": "ev_threshold", "min_edge": 0.02, "max_pct": 0.15, "ev_gate": 1.10,
            "desc": "Only bet when EV > 1.10 (10% expected profit). High selectivity. Research: Haghani & White 2017."
        },
        "value_hunter": {
            "family": "value", "min_edge": 0.05, "max_pct": 0.12,
            "desc": "Only bet when edge > 5%. Very selective, high-conviction plays only. Research: Pinnacle sharp methodology."
        },
        "underdog_specialist": {
            "family": "underdog", "min_odds": 2.2, "min_edge": 0.03, "max_pct": 0.08,
            "desc": "Only bet underdogs (odds > +120). Exploits favorite-longshot bias. Research: Woodland & Woodland 1994."
        },
        "dog_value_plus": {
            "family": "underdog", "min_odds": 3.0, "min_edge": 0.02, "max_pct": 0.06,
            "desc": "Big underdogs only (odds > +200). Small bets, large payoffs. Lottery-style value hunting."
        },
        "first_half_sniper": {
            "family": "kelly", "fraction": 0.5, "min_edge": 0.02, "max_pct": 0.15,
            "cats": ["h1_ml_home", "h1_ml_away"],
            "desc": "Specializes in first-half moneylines. Teams often show true form early. Research: Paul & Weinbach 2005."
        },
        "first_half_away": {
            "family": "kelly", "fraction": 0.5, "min_edge": 0.02, "max_pct": 0.12,
            "desc": "First-half away ML specialist. 53.2% win rate in backtest. Away teams underpriced in H1."
        },
        "home_specialist": {
            "family": "kelly", "fraction": 0.5, "min_edge": 0.02, "max_pct": 0.12,
            "cats": ["ml_home", "spread_home", "h1_ml_home"],
            "desc": "Home advantage specialist. NBA home teams win ~58%. Exploits travel fatigue and crowd effect."
        },
        "anti_martingale": {
            "family": "anti_mart", "min_edge": 0.02, "max_pct": 0.20, "base_pct": 0.02,
            "desc": "Increase bets after wins, decrease after losses. Ride hot streaks. Research: Anti-Martingale system, Dubins & Savage 1976."
        },
        "drawdown_adjusted": {
            "family": "drawdown_adj", "min_edge": 0.02, "max_pct": 0.15, "dd_threshold": 0.15,
            "desc": "Reduce bet size when drawdown exceeds threshold. Protects against ruin. Research: DMAD framework."
        },
        "streak_momentum": {
            "family": "streak", "min_edge": 0.02, "max_pct": 0.20, "streak_boost": 3,
            "desc": "Boost bet size after N consecutive wins. Captures momentum. Research: TradingAgents 2412.20138."
        },
        "parlay_2leg": {
            "family": "parlay", "legs": 2, "min_edge": 0.03, "max_pct": 0.05,
            "desc": "2-leg parlays combining correlated bets (e.g., ML + total). Higher payoff. Research: PolySwarm correlation analysis."
        },
        "teaser_6pt": {
            "family": "teaser", "points": 6, "min_edge": 0.01, "max_pct": 0.08,
            "desc": "6-point NBA teaser. Move spread 6 points in your favor at reduced odds. Research: Wong teasers methodology."
        },
    }

    out = DATA_DIR / "strategies.json"
    with open(out, "w") as f:
        json.dump(STRATEGIES, f, indent=2)
    print(f"  Saved {out} ({len(STRATEGIES)} strategies)")
    return STRATEGIES


# ===================================================================
# Main
# ===================================================================
def print_summary():
    """Print file sizes for all generated data files."""
    print("\n" + "=" * 60)
    print("DATA PREPARATION COMPLETE")
    print("=" * 60)
    total_size = 0
    for fpath in sorted(DATA_DIR.glob("*.json")):
        size = fpath.stat().st_size
        total_size += size
        if size > 1_000_000:
            size_str = f"{size / 1_000_000:.1f} MB"
        elif size > 1_000:
            size_str = f"{size / 1_000:.1f} KB"
        else:
            size_str = f"{size} B"
        # Count entries
        try:
            with open(fpath) as f:
                data = json.load(f)
            if isinstance(data, dict):
                count = len(data)
            elif isinstance(data, list):
                count = len(data)
            else:
                count = "?"
        except Exception:
            count = "?"
        print(f"  {fpath.name:40s} {size_str:>10s}  ({count} entries)")
    print(f"  {'TOTAL':40s} {total_size / 1_000_000:.1f} MB")
    print("=" * 60)


def merge_player_props():
    """Step 4b: merge player-prop odds into full-odds-2025-26.json.

    Ships pp_<stat>_<tier>_<side> keys that NBA TF app.py line 1444 advertises.
    Data is produced by /scripts/fetch_player_props.py which runs twice daily
    via cron; we read the live file first (today's real odds) and fall back
    to the synthetic season-avg file for every historical game.
    """
    print("\n[4b/6] Merging player-prop odds into full-odds...")
    odds_path = DATA_DIR / "full-odds-2025-26.json"
    if not odds_path.exists():
        print(f"  SKIP: {odds_path} missing (run step 4 first)")
        return
    live_path = MONO_ROOT / "data" / "nba-agent" / "player-props-live.json"
    synth_path = MONO_ROOT / "data" / "nba-agent" / "player-props-synth.json"

    pp_live: dict = {}
    pp_synth: dict = {}
    if live_path.exists():
        try:
            pp_live = json.loads(live_path.read_text()).get("games", {})
        except Exception as e:
            print(f"  WARN live load failed: {e}")
    if synth_path.exists():
        try:
            pp_synth = json.loads(synth_path.read_text()).get("games", {})
        except Exception as e:
            print(f"  WARN synth load failed: {e}")
    if not pp_live and not pp_synth:
        print("  SKIP: no player-props files found — "
              "run `python3 scripts/fetch_player_props.py` first")
        return

    with open(odds_path) as f:
        odds = json.load(f)

    touched = pp_keys_added = 0
    for gk, bundle in odds.items():
        cats = bundle.setdefault("categories", {})
        # Live takes priority, synth fills gaps
        merged_props: dict = {}
        merged_props.update(pp_synth.get(gk, {}))
        merged_props.update(pp_live.get(gk, {}))
        if not merged_props:
            continue
        before = sum(1 for k in cats if k.startswith("pp_"))
        cats.update(merged_props)
        after = sum(1 for k in cats if k.startswith("pp_"))
        bundle["category_count"] = len(cats)
        pp_keys_added += (after - before)
        touched += 1

    with open(odds_path, "w") as f:
        json.dump(odds, f, indent=2)
    games_with_six = sum(1 for b in odds.values()
                         if sum(1 for k in b.get("categories", {})
                                if k.startswith("pp_")) >= 6)
    print(f"  Merged into {touched}/{len(odds)} games, "
          f"{pp_keys_added} new pp_* keys. "
          f"Games ≥6 pp keys: {games_with_six}")


def main():
    print("=" * 60)
    print("NBA LLM Trading Floor — Data Preparation")
    print(f"Output directory: {DATA_DIR}")
    print("=" * 60)

    # Step 1: Rosters (API call, may be slow)
    fetch_rosters()

    # Step 2: Advanced team stats (API call)
    fetch_team_advanced()

    # Step 3: Player stats (local CSV)
    compile_player_stats()

    # Step 4: Full odds with 100+ categories (local CSV)
    compile_full_odds()

    # Step 4b: Player-prop injection (pp_<stat>_<tier>_<side>)
    merge_player_props()

    # Step 5: Model predictions consensus (local JSON files)
    compile_predictions()

    # Step 6: Strategies
    save_strategies()

    # Summary
    print_summary()


if __name__ == "__main__":
    main()
