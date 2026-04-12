#!/usr/bin/env python3
"""
fetch_euro_odds.py
==================
Fetch and analyse NBA odds from French/European bookmakers.

WHAT WE HAVE (as of 2026-03-28)
---------------------------------
Our live-odds.json already contains all 5 French books + Pinnacle:
  - unibet / unibet_fr     (Unibet France)
  - winamax / winamax_fr   (Winamax France)
  - betclic / betclic_fr   (Betclic France)
  - pmu / pmu_fr           (PMU France)
  - parionssport / parionssport_fr  (ParionsSport / FDJ France)
  - pinnacle               (sharp reference line)

The Odds API key: in /home/termius/nomos-nba-agent/.env.local
  - Free tier: 500 requests/month (exhausted for March 2026)
  - Reset: April 1, 2026
  - FR region bookmaker keys: unibet_fr, winamax_fr, betclic_fr,
    parionssport_fr, pmu_fr, betclic
  - EU region: betsson, marathonbet, coolbet, nordicbet

Historical snapshots (Mar 15-28 2026) in:
  /home/termius/nomos-nba-agent/data/odds-*.json
  These already contain all French books (full EU coverage).

nba_2008-2025.csv: 23118 games, American moneylines (no book breakdown).
  No French book columns - those need to be sourced from the API.

MODES
------
1. --mode live        Read live-odds.json, compute edge vs Pinnacle for all French books
2. --mode snapshot    Extract Euro odds from historical odds-*.json snapshots
3. --mode fetch       Fetch fresh odds from The Odds API (uses ~10 credits per call)
4. --mode backtest    Compute per-book edge stats across all available snapshots

Usage:
    python3 scripts/fetch_euro_odds.py --mode live
    python3 scripts/fetch_euro_odds.py --mode snapshot --output data/nba-agent/euro-odds-history.json
    python3 scripts/fetch_euro_odds.py --mode fetch --regions fr,eu
    python3 scripts/fetch_euro_odds.py --mode backtest

CREDIT BUDGET (The Odds API)
------------------------------
One call to /v4/sports/basketball_nba/odds/ consumes:
  ~1 credit per bookmaker per game (see x-requests-last header)
Typical NBA slate: 8 games x 7 books = ~56 credits
At 500 credits/month free tier: ~8 full fetches per month.
Resets April 1.

EDGE CALCULATION
-----------------
We use Pinnacle as the "true line" (lowest vig sharp book).
  1. Remove Pinnacle's vig (no-vig true probability):
       pin_home_imp = 1 / pin_home_odds
       pin_away_imp = 1 / pin_away_odds
       pin_juice    = pin_home_imp + pin_away_imp
       nv_home      = pin_home_imp / pin_juice
       nv_away      = pin_away_imp / pin_juice
  2. Edge on French book side X:
       ev_x = (nv_x * book_x_odds - 1) * 100
  Positive EV = book offers better price than Pinnacle's no-vig line.
  French books are "soft" (more square) so edges are common and large.

IMPORTANT NOTE ON LARGE EDGES
------------------------------
Very large edges (>15%) typically indicate one of:
  a) French book hasn't yet updated its line (stale)
  b) French book uses different line format (different spread embedded)
  c) Game is lopsided and French book rounds aggressively
  Real exploitable edge threshold: ~3-8% sustained.
"""

import os
import sys
import json
import time
import glob
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ─── Paths ───────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_ODDS_PATH = os.path.join(BASE_DIR, "data", "nba-agent", "live-odds.json")
_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR   = str(_ROOT.parent / "nomos-nba-agent" / "data")
OUTPUT_DIR     = os.path.join(BASE_DIR, "data", "nba-agent")
ENV_FILE       = str(_ROOT.parent / "nomos-nba-agent" / ".env.local")

# ─── The Odds API ─────────────────────────────────────────────────────────────

ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# French/EU bookmaker keys used by The Odds API
# Region "fr" is a dedicated French region (most reliable for FR books)
# Region "eu" also includes many EU books
FR_BOOKS = [
    "unibet_fr",
    "winamax_fr",
    "betclic_fr",
    "parionssport_fr",
    "pmu_fr",
]
EU_BOOKS = [
    "betsson",
    "marathonbet",
    "unibet_nl",
    "unibet_se",
    "nordicbet",
    "coolbet",
]
SHARP_BOOKS = [
    "pinnacle",
    "betfair_ex_eu",
    "matchbook",
    "smarkets",
]

# Keys that appear in live-odds.json (no country suffix — unified key)
LIVE_EURO_KEYS = {
    "unibet", "winamax", "betclic", "pmu", "parionssport", "betway"
}
LIVE_SHARP_KEY = "pinnacle"


def load_api_key():
    """Read ODDS_API_KEY from .env.local."""
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith("export ODDS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return key
    except FileNotFoundError:
        pass
    return os.environ.get("ODDS_API_KEY", "")


# ─── Pinnacle no-vig probability ─────────────────────────────────────────────

def pinnacle_no_vig(pin_home, pin_away):
    """
    Return (nv_home, nv_away) no-vig probabilities from Pinnacle decimal odds.
    """
    h_imp = 1.0 / pin_home
    a_imp = 1.0 / pin_away
    juice  = h_imp + a_imp
    return h_imp / juice, a_imp / juice


def expected_value(nv_prob, book_odds):
    """EV% = (nv_prob * book_odds - 1) * 100"""
    return (nv_prob * book_odds - 1) * 100


# ─── Edge analysis ────────────────────────────────────────────────────────────

def analyse_game_euro_edge(game):
    """
    For a single game dict (from The Odds API), compute EV for every
    French/EU bookmaker vs Pinnacle sharp line.

    Returns a dict with keys:
      matchup, date, home_team, away_team,
      pinnacle: {home_odds, away_odds, nv_home, nv_away},
      books: [{key, title, home_odds, away_odds, ev_home, ev_away,
               best_ev, best_side, value_flag}]
    """
    home = game["home_team"]
    away = game["away_team"]
    ct = game.get("commence_time", "")
    if isinstance(ct, int):
        date = datetime.fromtimestamp(ct / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    else:
        date = str(ct)[:10]

    # Find Pinnacle
    pin_home = pin_away = None
    for b in game.get("bookmakers", []):
        if b["key"] in (LIVE_SHARP_KEY, "pinnacle"):
            for mkt in b.get("markets", []):
                if mkt["key"] == "h2h":
                    for o in mkt["outcomes"]:
                        if o["name"] == home:
                            pin_home = float(o["price"])
                        elif o["name"] == away:
                            pin_away = float(o["price"])

    if not pin_home or not pin_away:
        return None

    nv_home, nv_away = pinnacle_no_vig(pin_home, pin_away)

    books_data = []
    target_keys = LIVE_EURO_KEYS | set(FR_BOOKS) | set(EU_BOOKS)

    for b in game.get("bookmakers", []):
        if b["key"] not in target_keys:
            continue
        bk_home = bk_away = None
        for mkt in b.get("markets", []):
            if mkt["key"] == "h2h":
                for o in mkt["outcomes"]:
                    if o["name"] == home:
                        bk_home = float(o["price"])
                    elif o["name"] == away:
                        bk_away = float(o["price"])
        if not bk_home or not bk_away:
            continue

        ev_h = expected_value(nv_home, bk_home)
        ev_a = expected_value(nv_away, bk_away)
        best_ev   = max(ev_h, ev_a)
        best_side = home if ev_h >= ev_a else away

        books_data.append({
            "key":       b["key"],
            "title":     b.get("title", b["key"]),
            "home_odds": round(bk_home, 3),
            "away_odds": round(bk_away, 3),
            "ev_home":   round(ev_h, 2),
            "ev_away":   round(ev_a, 2),
            "best_ev":   round(best_ev, 2),
            "best_side": best_side,
            "value_flag": (
                "HIGH_VALUE"  if best_ev >= 5.0 else
                "VALUE"       if best_ev >= 2.0 else
                "SLIGHT_EDGE" if best_ev >= 0.5 else
                "NO_EDGE"
            ),
        })

    return {
        "matchup":  f"{away} @ {home}",
        "date":     date,
        "home_team": home,
        "away_team": away,
        "pinnacle": {
            "home_odds": round(pin_home, 3),
            "away_odds": round(pin_away, 3),
            "nv_home":   round(nv_home, 4),
            "nv_away":   round(nv_away, 4),
        },
        "books": books_data,
    }


def print_edge_report(results):
    """Pretty-print the edge analysis to stdout."""
    if not results:
        print("No results.")
        return

    print()
    print("=" * 80)
    print("  EURO BOOKMAKER EDGE vs PINNACLE SHARP LINE")
    print("=" * 80)
    print()

    total_value = 0
    for r in results:
        if not r:
            continue
        pin = r["pinnacle"]
        print(f"  {r['matchup']}")
        print(f"  Date: {r['date']}  |  "
              f"Pinnacle: H={pin['home_odds']} A={pin['away_odds']}  |  "
              f"NV prob: H={pin['nv_home']:.3f} A={pin['nv_away']:.3f}")
        print(f"  {'Book':<20} {'H_odds':>7} {'A_odds':>7} {'EV_H':>8} {'EV_A':>8} {'Best EV':>9}  Best Side")
        print(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*8} {'-'*8} {'-'*9}  ---------")
        for bk in sorted(r["books"], key=lambda x: -x["best_ev"]):
            flag = " ***" if bk["value_flag"] == "HIGH_VALUE" else (" *" if bk["value_flag"] == "VALUE" else "")
            side_short = bk["best_side"][:20]
            print(f"  {bk['title']:<20} {bk['home_odds']:>7.3f} {bk['away_odds']:>7.3f} "
                  f"{bk['ev_home']:>+7.2f}% {bk['ev_away']:>+7.2f}% {bk['best_ev']:>+8.2f}%  "
                  f"{side_short}{flag}")
            if bk["best_ev"] >= 2.0:
                total_value += 1
        print()

    print(f"  Total value opportunities (EV >= 2%): {total_value}")
    print("=" * 80)


# ─── Mode: live ───────────────────────────────────────────────────────────────

def mode_live():
    """Analyse today's games from live-odds.json."""
    print(f"Reading {LIVE_ODDS_PATH} ...")
    with open(LIVE_ODDS_PATH) as f:
        data = json.load(f)

    games = data.get("games", data) if isinstance(data, dict) else data
    print(f"Found {len(games)} games.")

    results = []
    for g in games:
        r = analyse_game_euro_edge(g)
        if r:
            results.append(r)

    print_edge_report(results)
    return results


# ─── Mode: snapshot ───────────────────────────────────────────────────────────

def mode_snapshot(output_path=None):
    """
    Extract Euro odds from all historical odds-*.json snapshots.
    Keeps the LAST snapshot before game tip-off as the closing line.
    """
    snapshots = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, "odds-*.json")))
    print(f"Found {len(snapshots)} snapshot files in {SNAPSHOT_DIR}")

    all_results = {}  # (home, away, date) -> best result

    for fpath in snapshots:
        fname = os.path.basename(fpath)
        # parse snapshot timestamp
        import re
        m = re.search(r"odds-(\d{8})-(\d{4})", fname)
        if not m:
            continue

        try:
            with open(fpath) as f:
                raw = json.load(f)
        except Exception as e:
            print(f"  [SKIP] {fname}: {e}")
            continue

        data   = raw.get("data", raw) if isinstance(raw, dict) else raw
        games  = data if isinstance(data, list) else []

        for g in games:
            r = analyse_game_euro_edge(g)
            if not r:
                continue
            key = (r["home_team"], r["away_team"], r["date"])
            # Keep latest snapshot (closer to game time)
            if key not in all_results or fname > all_results[key]["_snapshot"]:
                r["_snapshot"] = fname
                all_results[key] = r

    results = list(all_results.values())
    print(f"\nExtracted {len(results)} unique games with Euro odds.")
    print_edge_report(results[:10])  # show first 10

    if output_path:
        # clean _snapshot keys
        clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(clean, f, indent=2)
        print(f"\nWrote {len(clean)} games to {output_path}")

    return results


# ─── Mode: fetch ──────────────────────────────────────────────────────────────

def mode_fetch(regions="fr,eu", save=True):
    """
    DEPRECATED: The Odds API (the-odds-api.com) quota is exhausted.
    Use fetch_free_odds.py instead:
      python3 scripts/fetch_free_odds.py --source all

    For Euro/French book analysis, use --mode live or --mode snapshot
    with the existing live-odds.json snapshots.
    """
    print("ERROR: --mode fetch is DEPRECATED.")
    print("The Odds API quota is exhausted and this is a paid service.")
    print("Use instead:")
    print("  python3 scripts/fetch_free_odds.py --source all  # ActionNetwork + Bovada + DraftKings")
    print("  python3 scripts/fetch_euro_odds.py --mode live   # Analyse existing live-odds.json")
    sys.exit(1)

    api_key = load_api_key()
    if not api_key:
        print("ERROR: No ODDS_API_KEY found in", ENV_FILE)
        sys.exit(1)

    # Determine bookmakers by region
    books_by_region = {
        "fr": FR_BOOKS,
        "eu": EU_BOOKS,
        "sharp": SHARP_BOOKS,
    }

    region_list = [r.strip() for r in regions.split(",")]
    bookmakers  = [LIVE_SHARP_KEY]  # always include Pinnacle
    for r in region_list:
        bookmakers.extend(books_by_region.get(r, []))
    bookmakers = list(dict.fromkeys(bookmakers))  # deduplicate

    # The Odds API: bookmakers mode fetches specific books only
    # regions= param only needed for general region queries
    params = (
        f"apiKey={api_key}"
        f"&regions=eu"       # eu region includes FR books
        f"&bookmakers={','.join(bookmakers)}"
        f"&markets=h2h,spreads,totals"
        f"&oddsFormat=decimal"
    )
    url = f"{ODDS_API_BASE}/sports/basketball_nba/odds/?{params}"

    print(f"Fetching NBA odds from The Odds API...")
    print(f"  Books: {', '.join(bookmakers)}")
    print(f"  URL: {url[:100]}...")

    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            remaining = resp.headers.get("x-requests-remaining", "?")
            used      = resp.headers.get("x-requests-last", "?")
            content   = resp.read().decode("utf-8")
        print(f"  Credits used: {used}  |  Remaining: {remaining}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body[:300]}")
        sys.exit(1)
    except Exception as e:
        print(f"Fetch error: {e}")
        sys.exit(1)

    games = json.loads(content)
    if not isinstance(games, list):
        print(f"Unexpected response: {games}")
        sys.exit(1)

    print(f"  Fetched {len(games)} games.")

    # Save raw snapshot
    if save:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        snap_path = os.path.join(OUTPUT_DIR, f"euro-odds-{ts}.json")
        with open(snap_path, "w") as f:
            json.dump(games, f, indent=2)
        print(f"  Saved raw snapshot to {snap_path}")

    results = [analyse_game_euro_edge(g) for g in games]
    results = [r for r in results if r]
    print_edge_report(results)
    return results


# ─── Mode: backtest ───────────────────────────────────────────────────────────

def mode_backtest():
    """
    Compute aggregate edge statistics for each French/EU book
    across all historical snapshot data.

    Shows: per-book avg EV, % games with >2% edge, which side has more value.
    """
    snapshots = sorted(glob.glob(os.path.join(SNAPSHOT_DIR, "odds-*.json")))
    print(f"Analysing {len(snapshots)} snapshots from {SNAPSHOT_DIR}...")

    # Per-book stats: {book_key: {ev_sum, count, value_count, home_value, away_value}}
    stats = {}
    seen_games = set()

    for fpath in snapshots:
        try:
            with open(fpath) as f:
                raw = json.load(f)
        except Exception:
            continue

        data  = raw.get("data", raw) if isinstance(raw, dict) else raw
        games = data if isinstance(data, list) else []

        for g in games:
            # Use game ID + date to avoid double-counting same game across snapshots
            gid  = g.get("id", "")
            ct   = g.get("commence_time", "")
            # commence_time may be int (epoch ms) or ISO string
            if isinstance(ct, int):
                from datetime import timezone as _tz
                date = datetime.fromtimestamp(ct / 1000, tz=_tz.utc).strftime("%Y-%m-%d")
            else:
                date = str(ct)[:10]
            key  = (gid, date)
            if key in seen_games:
                continue
            seen_games.add(key)

            r = analyse_game_euro_edge(g)
            if not r:
                continue

            for bk in r["books"]:
                bkey = bk["key"]
                if bkey not in stats:
                    stats[bkey] = {
                        "title": bk["title"],
                        "ev_sum": 0.0,
                        "count": 0,
                        "value_count": 0,    # EV >= 2%
                        "high_count": 0,     # EV >= 5%
                        "home_value": 0,
                        "away_value": 0,
                    }
                s = stats[bkey]
                s["ev_sum"]    += bk["best_ev"]
                s["count"]     += 1
                if bk["best_ev"] >= 2.0:
                    s["value_count"] += 1
                    if bk["best_side"] == g.get("home_team"):
                        s["home_value"] += 1
                    else:
                        s["away_value"] += 1
                if bk["best_ev"] >= 5.0:
                    s["high_count"] += 1

    if not stats:
        print("No data found.")
        return

    print()
    print("=" * 90)
    print("  EURO BOOK BACKTEST: Average EV vs Pinnacle Sharp Line")
    print(f"  ({len(seen_games)} unique games across {len(snapshots)} snapshots)")
    print("=" * 90)
    print(f"  {'Book':<22} {'Games':>6} {'Avg EV':>8} {'Value%':>8} {'High%':>8} {'Home%':>8} {'Away%':>8}")
    print(f"  {'-'*22} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for bkey, s in sorted(stats.items(), key=lambda x: -x[1]["ev_sum"] / max(x[1]["count"], 1)):
        avg_ev      = s["ev_sum"] / s["count"]
        value_pct   = 100 * s["value_count"] / s["count"]
        high_pct    = 100 * s["high_count"] / s["count"]
        total_val   = s["home_value"] + s["away_value"]
        home_pct    = 100 * s["home_value"] / max(total_val, 1)
        away_pct    = 100 * s["away_value"] / max(total_val, 1)
        print(f"  {s['title']:<22} {s['count']:>6} {avg_ev:>+7.2f}% {value_pct:>7.1f}% "
              f"{high_pct:>7.1f}% {home_pct:>7.1f}% {away_pct:>7.1f}%")

    print("=" * 90)
    print()
    print("  NOTE: High EV% on large underdogs often reflects stale lines,")
    print("  not real exploitable edge. Focus on EV 3-8% for real value.")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch and analyse NBA odds from French/European bookmakers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("MODES")[1].split("Usage:")[0]
    )
    parser.add_argument(
        "--mode",
        choices=["live", "snapshot", "fetch", "backtest"],
        default="live",
        help="Operation mode (default: live)"
    )
    parser.add_argument(
        "--regions",
        default="fr,eu",
        help="Comma-separated regions for --mode fetch: fr,eu,sharp (default: fr,eu)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path for --mode snapshot (default: print only)"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save raw snapshot in --mode fetch"
    )

    args = parser.parse_args()

    if args.mode == "live":
        mode_live()
    elif args.mode == "snapshot":
        out = args.output or os.path.join(OUTPUT_DIR, "euro-odds-history.json")
        mode_snapshot(output_path=out)
    elif args.mode == "fetch":
        mode_fetch(regions=args.regions, save=not args.no_save)
    elif args.mode == "backtest":
        mode_backtest()


if __name__ == "__main__":
    main()
