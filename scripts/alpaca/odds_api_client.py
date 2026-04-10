#!/usr/bin/env python3
"""
Nomos42 — The Odds API Client (Pinnacle + 70+ Bookmakers)
==========================================================
Replaces direct Pinnacle access (API closed July 2025).
The Odds API aggregates 70+ bookmakers including Pinnacle, DraftKings,
BetMGM, FanDuel, Betfair, Bet365, William Hill, and more.

Why The Odds API:
  - Includes Pinnacle (still #1 sharp bookmaker reference line)
  - Free tier: 500 requests/month (enough for daily NBA monitoring)
  - Paid tiers start at $79/month for 30,000 req/month
  - REST + WebSocket (paid). 2-5 second latency from exchange.
  - NBA, NFL, MLB, NHL, soccer, tennis, political markets all available

Docs: https://the-odds-api.com/lob-odds-api/

Env vars:
  ODDS_API_KEY    — Free at https://the-odds-api.com/ (sign up, instant key)

Usage:
    python3 scripts/alpaca/odds_api_client.py sports          # List all available sports
    python3 scripts/alpaca/odds_api_client.py nba             # NBA h2h odds (all books)
    python3 scripts/alpaca/odds_api_client.py nba --pinnacle  # Pinnacle lines only
    python3 scripts/alpaca/odds_api_client.py nba --compare   # Compare our model vs Pinnacle
    python3 scripts/alpaca/odds_api_client.py political       # US political markets
    python3 scripts/alpaca/odds_api_client.py usage           # Check remaining API quota

Rate limits (Free tier: 500 req/month):
  - We cache responses for 5 minutes to avoid burning quota
  - ~16 requests/day at 500/month budget
  - Cron: run 3x daily for NBA (pre-game, tipoff, final)

Integration with existing system:
  - Output format matches fetch_free_odds.py / fetch_euro_odds.py
  - Saves to data/odds/odds-api-latest.json (same dir as existing odds)
  - Pinnacle lines feed directly into our calibration (they're the sharpest)
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ══════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════

BASE_URL = "https://api.the-odds-api.com/v4"

# Sport keys used by The Odds API
SPORT_KEYS = {
    "nba":       "basketball_nba",
    "ncaab":     "basketball_ncaab",
    "nfl":       "americanfootball_nfl",
    "nhl":       "icehockey_nhl",
    "mlb":       "baseball_mlb",
    "political": "politics_us_presidential_election_winner",  # Changes each cycle
    "soccer":    "soccer_epl",
}

# Bookmaker keys — Pinnacle is the primary sharp reference
PINNACLE_KEY = "pinnacle"
ALL_SHARP_BOOKS = ["pinnacle", "betfair_ex_eu", "matchbook"]
EU_BOOKS = ["pinnacle", "bet365", "betfair_ex_eu", "williamhill", "unibet_eu"]
US_BOOKS = ["draftkings", "fanduel", "betmgm", "caesars", "pointsbetus"]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "odds"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = DATA_DIR / "odds-api-cache.json"
OUTPUT_FILE = DATA_DIR / "odds-api-latest.json"
USAGE_FILE  = DATA_DIR / "odds-api-usage.json"

# Cache duration: 5 minutes to preserve free tier quota
CACHE_TTL = 300


# ══════════════════════════════════════════════════════════
# CACHE
# ══════════════════════════════════════════════════════════

def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache))


def _cache_key(endpoint: str, params: dict) -> str:
    return endpoint + "?" + urllib.parse.urlencode(sorted(params.items()))


# ══════════════════════════════════════════════════════════
# HTTP
# ══════════════════════════════════════════════════════════

def _get(endpoint: str, params: dict) -> tuple[dict | list, dict]:
    """
    Fetch from The Odds API. Returns (data, headers_with_quota).
    Checks cache first; falls back to live request.
    """
    api_key = os.environ.get("ODDS_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "Set ODDS_API_KEY env var. Free key at https://the-odds-api.com/"
        )

    cache = _load_cache()
    ck = _cache_key(endpoint, params)
    cached = cache.get(ck, {})
    if cached and (time.time() - cached.get("ts", 0)) < CACHE_TTL:
        print(f"[CACHE HIT] {endpoint} (expires in {int(CACHE_TTL - (time.time() - cached['ts']))}s)")
        return cached["data"], cached.get("quota", {})

    params["apiKey"] = api_key
    url = f"{BASE_URL}/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Nomos42/1.0"})

    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
        quota = {
            "requests_remaining": resp.headers.get("x-requests-remaining", "?"),
            "requests_used":      resp.headers.get("x-requests-used", "?"),
            "requests_last":      resp.headers.get("x-requests-last", "?"),
        }

    # Update usage log
    usage_log = {"timestamp": datetime.now(timezone.utc).isoformat(), **quota}
    USAGE_FILE.write_text(json.dumps(usage_log, indent=2))
    print(f"[QUOTA] Remaining: {quota['requests_remaining']} / used this call: {quota['requests_last']}")

    # Cache
    cache[ck] = {"ts": time.time(), "data": data, "quota": quota}
    _save_cache(cache)

    return data, quota


# ══════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════

def list_sports() -> list:
    """List all available sport markets."""
    data, _ = _get("sports", {"all": "true"})
    return data


def get_odds(
    sport: str,
    regions: str = "eu,us",
    markets: str = "h2h",
    bookmakers: Optional[list] = None,
    odds_format: str = "decimal",
) -> list:
    """
    Fetch odds for upcoming games in a sport.

    Args:
        sport:      Sport key (e.g. "basketball_nba")
        regions:    Comma-separated: "us", "eu", "uk", "au"
        markets:    "h2h" (moneyline), "spreads", "totals"
        bookmakers: Optional list of bookmaker keys to filter. None = all available.
        odds_format: "decimal" or "american"

    Returns:
        List of game dicts, each with bookmaker odds attached.
    """
    params = {
        "sport": sport,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
        "dateFormat": "iso",
    }
    if bookmakers:
        params["bookmakers"] = ",".join(bookmakers)

    data, _ = _get(f"sports/{sport}/odds", params)
    return data


def get_scores(sport: str, days_from: int = 1) -> list:
    """Fetch completed game scores (last N days). Good for result verification."""
    params = {"sport": sport, "daysFrom": days_from, "dateFormat": "iso"}
    data, _ = _get(f"sports/{sport}/scores", params)
    return data


def get_events(sport: str) -> list:
    """List upcoming event IDs (cheaper quota call — use before get_event_odds)."""
    params = {"sport": sport, "dateFormat": "iso"}
    data, _ = _get(f"sports/{sport}/events", params)
    return data


def get_event_odds(sport: str, event_id: str, markets: str = "h2h") -> dict:
    """Fetch odds for a single event (cheapest: costs 1 quota unit vs N for full list)."""
    params = {"sport": sport, "markets": markets, "oddsFormat": "decimal", "dateFormat": "iso"}
    data, _ = _get(f"sports/{sport}/events/{event_id}/odds", params)
    return data


# ══════════════════════════════════════════════════════════
# PARSING HELPERS
# ══════════════════════════════════════════════════════════

def extract_pinnacle_lines(games: list) -> list:
    """
    From a list of game odds, extract Pinnacle moneyline only.
    Returns list of dicts: {game_id, home_team, away_team, commence_time,
                             pinnacle_home, pinnacle_away, pinnacle_draw (if exists)}
    """
    lines = []
    for game in games:
        game_id = game.get("id", "")
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        commence = game.get("commence_time", "")

        for bookie in game.get("bookmakers", []):
            if bookie.get("key") != PINNACLE_KEY:
                continue
            for market in bookie.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                lines.append({
                    "game_id":        game_id,
                    "home_team":      home,
                    "away_team":      away,
                    "commence_time":  commence,
                    "pinnacle_home":  outcomes.get(home),
                    "pinnacle_away":  outcomes.get(away),
                    "pinnacle_draw":  outcomes.get("Draw"),
                    "last_update":    bookie.get("last_update"),
                })
    return lines


def decimal_to_implied_prob(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability (no vig removal)."""
    if not decimal_odds or decimal_odds <= 1.0:
        return 0.5
    return 1.0 / decimal_odds


def remove_vig(prob_home: float, prob_away: float) -> tuple[float, float]:
    """
    Remove bookmaker margin (vig) using Pinnacle's multiplicative method.
    Returns fair probabilities that sum to 1.0.
    """
    total = prob_home + prob_away
    if total <= 0:
        return 0.5, 0.5
    return prob_home / total, prob_away / total


def pinnacle_to_model_format(pinnacle_lines: list) -> list:
    """
    Convert Pinnacle lines to the format our existing odds pipeline expects:
    {date, home_team, away_team, home_odds, away_odds, home_prob, away_prob}
    Matches structure of fetch_free_odds.py output.
    """
    formatted = []
    for line in pinnacle_lines:
        if not line.get("pinnacle_home") or not line.get("pinnacle_away"):
            continue
        p_home_raw = decimal_to_implied_prob(line["pinnacle_home"])
        p_away_raw = decimal_to_implied_prob(line["pinnacle_away"])
        p_home, p_away = remove_vig(p_home_raw, p_away_raw)
        formatted.append({
            "date":          line["commence_time"][:10],
            "game_id":       line["game_id"],
            "home_team":     line["home_team"],
            "away_team":     line["away_team"],
            "home_odds_dec": line["pinnacle_home"],
            "away_odds_dec": line["pinnacle_away"],
            "home_prob_raw": round(p_home_raw, 4),
            "away_prob_raw": round(p_away_raw, 4),
            "home_prob_vig_removed": round(p_home, 4),
            "away_prob_vig_removed": round(p_away, 4),
            "source":        "pinnacle_via_odds_api",
            "last_update":   line.get("last_update", ""),
        })
    return formatted


# ══════════════════════════════════════════════════════════
# CROSS-BOOK CONSENSUS
# ══════════════════════════════════════════════════════════

def compute_sharp_consensus(games: list, sharp_books: list = ALL_SHARP_BOOKS) -> list:
    """
    Average Pinnacle + Betfair + Matchbook to get a multi-sharp consensus.
    This is more robust than Pinnacle alone — reduces single-book noise.
    Returns list of {game_id, home_team, away_team, consensus_home_prob, consensus_away_prob, n_books}
    """
    consensus = []
    for game in games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        probs_home = []
        probs_away = []
        books_used = []

        for bookie in game.get("bookmakers", []):
            if bookie.get("key") not in sharp_books:
                continue
            for market in bookie.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                ph_raw = decimal_to_implied_prob(outcomes.get(home, 0))
                pa_raw = decimal_to_implied_prob(outcomes.get(away, 0))
                ph, pa = remove_vig(ph_raw, pa_raw)
                probs_home.append(ph)
                probs_away.append(pa)
                books_used.append(bookie["key"])

        if not probs_home:
            continue

        consensus.append({
            "game_id":             game.get("id"),
            "home_team":           home,
            "away_team":           away,
            "commence_time":       game.get("commence_time"),
            "consensus_home_prob": round(sum(probs_home) / len(probs_home), 4),
            "consensus_away_prob": round(sum(probs_away) / len(probs_away), 4),
            "n_books":             len(books_used),
            "books_used":          books_used,
        })
    return consensus


# ══════════════════════════════════════════════════════════
# HIGH-LEVEL COMMANDS
# ══════════════════════════════════════════════════════════

def cmd_sports():
    sports = list_sports()
    active = [s for s in sports if s.get("active")]
    print(f"\n{len(active)} active sport markets:")
    for s in active:
        print(f"  {s['key']:<45} {s.get('title', '')}")


def cmd_nba(pinnacle_only: bool = False, compare: bool = False):
    """Fetch NBA odds, extract Pinnacle lines, optionally compare vs our model."""
    books = [PINNACLE_KEY] if pinnacle_only else None
    games = get_odds(SPORT_KEYS["nba"], regions="eu,us", markets="h2h", bookmakers=books)

    if not games:
        print("No upcoming NBA games found.")
        return

    pinnacle_lines = extract_pinnacle_lines(games)
    formatted = pinnacle_to_model_format(pinnacle_lines)
    consensus = compute_sharp_consensus(games)

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sport": "basketball_nba",
        "games_found": len(games),
        "pinnacle_lines": formatted,
        "sharp_consensus": consensus,
    }

    if compare:
        # Load our model predictions and compare
        pred_file = REPO_ROOT / "data" / "nba-agent" / "predictions-today.json"
        if pred_file.exists():
            our_preds = json.loads(pred_file.read_text())
            output["model_vs_market"] = _compare_model_market(our_preds, formatted)
        else:
            print("No model predictions found for comparison.")

    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"\nSaved {len(formatted)} Pinnacle lines → {OUTPUT_FILE}")

    # Print table
    print(f"\n{'Away':<25} {'Home':<25} {'P(Home)':>8} {'P(Away)':>8}")
    print("-" * 70)
    for line in formatted:
        print(f"{line['away_team']:<25} {line['home_team']:<25} "
              f"{line['home_prob_vig_removed']:>8.3f} {line['away_prob_vig_removed']:>8.3f}")


def _compare_model_market(our_preds: dict, pinnacle_lines: list) -> list:
    """Find edges: where our model diverges from Pinnacle by >3pp."""
    edges = []
    for line in pinnacle_lines:
        home = line["home_team"]
        away = line["away_team"]
        # Fuzzy match team names (our model may use abbreviations)
        model_game = None
        for game_id, pred in our_preds.items() if isinstance(our_preds, dict) else []:
            if home[:4].lower() in str(pred).lower() or away[:4].lower() in str(pred).lower():
                model_game = pred
                break
        if not model_game:
            continue
        model_home_prob = float(model_game.get("home_win_prob", 0.5))
        market_home_prob = line["home_prob_vig_removed"]
        edge = model_home_prob - market_home_prob
        if abs(edge) >= 0.03:
            edges.append({
                "home_team": home,
                "away_team": away,
                "model_home_prob":  round(model_home_prob, 4),
                "market_home_prob": round(market_home_prob, 4),
                "edge": round(edge, 4),
                "direction": "HOME" if edge > 0 else "AWAY",
            })
    edges.sort(key=lambda x: abs(x["edge"]), reverse=True)
    return edges


def cmd_political():
    """Fetch US political prediction markets (Kalshi + Polymarket not available here, but Pinnacle has some)."""
    try:
        games = get_odds("politics_us_presidential_election_winner",
                         regions="eu,us", markets="h2h")
        print(json.dumps(games[:3], indent=2))
    except Exception as e:
        print(f"Political markets: {e}")
        print("Note: Check available political market keys with: odds_api_client.py sports")


def cmd_usage():
    """Show current API quota status."""
    if USAGE_FILE.exists():
        usage = json.loads(USAGE_FILE.read_text())
        print(json.dumps(usage, indent=2))
    else:
        print("No usage data yet. Run any odds command first.")
    print("\nFree tier: 500 requests/month. Paid tiers at the-odds-api.com")


# ══════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nomos42 Odds API Client (Pinnacle + 70 books)")
    parser.add_argument("command", choices=["sports", "nba", "political", "usage"])
    parser.add_argument("--pinnacle", action="store_true", help="Fetch Pinnacle lines only")
    parser.add_argument("--compare",  action="store_true", help="Compare model vs Pinnacle")
    args = parser.parse_args()

    try:
        if args.command == "sports":
            cmd_sports()
        elif args.command == "nba":
            cmd_nba(pinnacle_only=args.pinnacle, compare=args.compare)
        elif args.command == "political":
            cmd_political()
        elif args.command == "usage":
            cmd_usage()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
