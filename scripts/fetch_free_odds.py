#!/usr/bin/env python3
"""
fetch_free_odds.py
==================
100% FREE NBA odds fetcher. No API keys, no paid services.

Sources (live odds):
  1. Bovada            — Public API, no key, moneyline + spread + totals
  2. DraftKings        — Nash mobile API, no key, full markets
  3. ActionNetwork     — Free API, moneyline + spread + totals + public money %
  4. SBR               — SportsBettingReview, __NEXT_DATA__ scrape, closing lines

Historical odds (for CLV and backtest):
  5. SBR date scraper  — Any date from 2007+, American moneylines
  6. nba_2008-2025.csv — Pre-loaded Kaggle dataset (23k games, BetMGM)

Sharp/square divergence:
  ActionNetwork includes both public bet % and public money % per game.
  Divergence = when the sharp money (money %) opposes the public tickets (bet %).

Output files:
  data/nba-agent/live-odds.json     — Live odds in Odds API-compatible format
  data/nba-agent/odds-latest.json   — Flat list (same data, no wrapper)
  data/nba-agent/market-data.json   — Market analysis: implied probs, edges, sharp/square

Usage:
  python3 scripts/fetch_free_odds.py              # fetch + analyse today
  python3 scripts/fetch_free_odds.py --source bovada
  python3 scripts/fetch_free_odds.py --source action
  python3 scripts/fetch_free_odds.py --source draftkings
  python3 scripts/fetch_free_odds.py --source sbr
  python3 scripts/fetch_free_odds.py --historical 2026-03-01 2026-03-28

ZERO paid APIs. ZERO ML on VM. Pure urllib + stdlib.
"""

import os
import sys
import ssl
import json
import time
import math
import re
import csv
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "nba-agent"
HIST_DIR = BASE_DIR / "data" / "historical-odds"
DATA_DIR.mkdir(parents=True, exist_ok=True)
HIST_DIR.mkdir(parents=True, exist_ok=True)

LIVE_ODDS_PATH  = DATA_DIR / "live-odds.json"
FLAT_ODDS_PATH  = DATA_DIR / "odds-latest.json"
MARKET_PATH     = DATA_DIR / "market-data.json"
HIST_CSV        = HIST_DIR / "nba_2008-2025.csv"

# ─── SSL context (VM has no cert bundle issues) ───────────────────────────────

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def _get(url, headers=None, timeout=20):
    """Simple HTTP GET, returns decoded string. Raises on error."""
    default_headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    if headers:
        default_headers.update(headers)
    req = urllib.request.Request(url, headers=default_headers)
    resp = urllib.request.urlopen(req, timeout=timeout, context=_ctx)
    return resp.read().decode("utf-8", errors="replace")


def _get_json(url, headers=None, timeout=20):
    """HTTP GET, parse JSON."""
    return json.loads(_get(url, headers=headers, timeout=timeout))


# ─── Team name normalisation ──────────────────────────────────────────────────

FULL_NAMES = [
    "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets",
    "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets",
    "Detroit Pistons", "Golden State Warriors", "Houston Rockets", "Indiana Pacers",
    "Los Angeles Clippers", "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat",
    "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans", "New York Knicks",
    "Oklahoma City Thunder", "Orlando Magic", "Philadelphia 76ers", "Phoenix Suns",
    "Portland Trail Blazers", "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors",
    "Utah Jazz", "Washington Wizards",
]

_PARTIALS = {
    # Short city/nickname forms → full name
    "Atlanta": "Atlanta Hawks", "Boston": "Boston Celtics",
    "Brooklyn": "Brooklyn Nets", "Charlotte": "Charlotte Hornets",
    "Chicago": "Chicago Bulls", "Cleveland": "Cleveland Cavaliers",
    "Dallas": "Dallas Mavericks", "Denver": "Denver Nuggets",
    "Detroit": "Detroit Pistons", "Golden State": "Golden State Warriors",
    "GS Warriors": "Golden State Warriors", "Houston": "Houston Rockets",
    "Indiana": "Indiana Pacers", "LA Clippers": "Los Angeles Clippers",
    "L.A. Clippers": "Los Angeles Clippers", "LA Lakers": "Los Angeles Lakers",
    "L.A. Lakers": "Los Angeles Lakers", "Los Angeles": "Los Angeles Lakers",
    "Memphis": "Memphis Grizzlies", "Miami": "Miami Heat",
    "Milwaukee": "Milwaukee Bucks", "Minnesota": "Minnesota Timberwolves",
    "New Orleans": "New Orleans Pelicans", "New York": "New York Knicks",
    "Oklahoma City": "Oklahoma City Thunder", "OKC Thunder": "Oklahoma City Thunder",
    "Orlando": "Orlando Magic", "Philadelphia": "Philadelphia 76ers",
    "Phoenix": "Phoenix Suns", "Portland": "Portland Trail Blazers",
    "Sacramento": "Sacramento Kings", "San Antonio": "San Antonio Spurs",
    "Toronto": "Toronto Raptors", "Utah": "Utah Jazz",
    "Washington": "Washington Wizards",
    # DraftKings short names
    "WAS Wizards": "Washington Wizards", "LA Lakers": "Los Angeles Lakers",
    "LA Clippers": "Los Angeles Clippers", "GS Warriors": "Golden State Warriors",
    "NO Pelicans": "New Orleans Pelicans", "CLE Cavaliers": "Cleveland Cavaliers",
    "MEM Grizzlies": "Memphis Grizzlies", "SA Spurs": "San Antonio Spurs",
    "MIA Heat": "Miami Heat", "PHI 76ers": "Philadelphia 76ers",
    "MIL Bucks": "Milwaukee Bucks", "PHO Suns": "Phoenix Suns",
    "CHA Hornets": "Charlotte Hornets", "IND Pacers": "Indiana Pacers",
    "ORL Magic": "Orlando Magic", "ATL Hawks": "Atlanta Hawks",
    "DET Pistons": "Detroit Pistons", "BKN Nets": "Brooklyn Nets",
    "NYK Knicks": "New York Knicks", "BOS Celtics": "Boston Celtics",
    "TOR Raptors": "Toronto Raptors", "DEN Nuggets": "Denver Nuggets",
    "MIN Timberwolves": "Minnesota Timberwolves",
    "POR Trail Blazers": "Portland Trail Blazers", "UTA Jazz": "Utah Jazz",
    "SAC Kings": "Sacramento Kings", "HOU Rockets": "Houston Rockets",
    "DAL Mavericks": "Dallas Mavericks", "CHI Bulls": "Chicago Bulls",
}


def normalize_team(name):
    if not name:
        return name
    # Already exact
    if name in FULL_NAMES:
        return name
    # Direct map
    if name in _PARTIALS:
        return _PARTIALS[name]
    # Fuzzy: find full name that contains this token
    name_lower = name.lower()
    for full in FULL_NAMES:
        if name_lower in full.lower():
            return full
    return name


# ─── American odds conversions ────────────────────────────────────────────────

def american_to_decimal(american):
    """Convert American odds (int or str) to decimal odds."""
    try:
        a = int(str(american).replace("+", ""))
    except (ValueError, TypeError):
        return None
    if a > 0:
        return round(1 + a / 100, 4)
    elif a < 0:
        return round(1 - 100 / a, 4)
    return None


def american_to_implied(american):
    """Convert American odds to implied probability (with vig)."""
    dec = american_to_decimal(american)
    if dec is None or dec <= 1:
        return None
    return round(1 / dec, 6)


def decimal_to_american(decimal):
    """Convert decimal odds to American."""
    if decimal is None or decimal <= 1:
        return None
    if decimal >= 2:
        return int(round((decimal - 1) * 100))
    else:
        return int(round(-100 / (decimal - 1)))


def no_vig_prob(implied_home, implied_away):
    """Remove bookmaker vig, return (nv_home, nv_away) true probabilities."""
    if not implied_home or not implied_away:
        return None, None
    total = implied_home + implied_away
    if total <= 0:
        return None, None
    return round(implied_home / total, 6), round(implied_away / total, 6)


def calc_edge(model_prob, book_implied_prob):
    """
    Edge = (model_prob - no_vig_book_prob).
    Positive = model says bet is underpriced (value exists).
    """
    if model_prob is None or book_implied_prob is None:
        return None
    return round(model_prob - book_implied_prob, 6)


# ─── Source 1: Bovada ─────────────────────────────────────────────────────────

def fetch_bovada():
    """
    Bovada public API — moneyline, spread, totals.
    No authentication, no rate limits known.
    """
    url = (
        "https://www.bovada.lv/services/sports/event/coupon/events/A/description/"
        "basketball/nba?marketFilterId=def&lang=en"
    )
    try:
        raw = _get_json(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    except Exception as e:
        print(f"  [Bovada] Fetch error: {e}")
        return []

    games = []
    for group in raw:
        for ev in group.get("events", []):
            parts = ev.get("description", "").split(" @ ")
            if len(parts) != 2:
                continue
            away_raw, home_raw = parts[0].strip(), parts[1].strip()
            away_team = normalize_team(away_raw)
            home_team = normalize_team(home_raw)

            game = {
                "id": str(ev.get("id", "")),
                "home_team": home_team,
                "away_team": away_team,
                "start_time": ev.get("startTime"),
                "source": "bovada",
                "markets": {},
            }

            for dg in ev.get("displayGroups", []):
                for mkt in dg.get("markets", []):
                    mtype = mkt.get("description", "").lower()
                    outcomes = []
                    for oc in mkt.get("outcomes", []):
                        price = oc.get("price", {})
                        american = price.get("american", "")
                        outcomes.append({
                            "name": oc.get("description", ""),
                            "american": american,
                            "decimal": price.get("decimal", ""),
                            "handicap": price.get("handicap", ""),
                        })
                    if "spread" in mtype:
                        game["markets"]["spread"] = outcomes
                    elif "moneyline" in mtype or "money line" in mtype:
                        game["markets"]["moneyline"] = outcomes
                    elif "total" in mtype:
                        game["markets"]["total"] = outcomes

            games.append(game)

    print(f"  [Bovada] {len(games)} games")
    return games


# ─── Source 2: DraftKings ─────────────────────────────────────────────────────

_DK_TEAM_MAP = {
    "WAS Wizards": "Washington Wizards", "OKC Thunder": "Oklahoma City Thunder",
    "LA Lakers": "Los Angeles Lakers",   "LA Clippers": "Los Angeles Clippers",
    "GS Warriors": "Golden State Warriors", "NO Pelicans": "New Orleans Pelicans",
    "CLE Cavaliers": "Cleveland Cavaliers", "MEM Grizzlies": "Memphis Grizzlies",
    "SA Spurs": "San Antonio Spurs",     "MIA Heat": "Miami Heat",
    "PHI 76ers": "Philadelphia 76ers",   "MIL Bucks": "Milwaukee Bucks",
    "PHO Suns": "Phoenix Suns",          "CHA Hornets": "Charlotte Hornets",
    "IND Pacers": "Indiana Pacers",      "ORL Magic": "Orlando Magic",
    "ATL Hawks": "Atlanta Hawks",        "DET Pistons": "Detroit Pistons",
    "BKN Nets": "Brooklyn Nets",         "NYK Knicks": "New York Knicks",
    "BOS Celtics": "Boston Celtics",     "TOR Raptors": "Toronto Raptors",
    "DEN Nuggets": "Denver Nuggets",     "MIN Timberwolves": "Minnesota Timberwolves",
    "POR Trail Blazers": "Portland Trail Blazers", "UTA Jazz": "Utah Jazz",
    "SAC Kings": "Sacramento Kings",     "HOU Rockets": "Houston Rockets",
    "DAL Mavericks": "Dallas Mavericks", "CHI Bulls": "Chicago Bulls",
    "NYK Knicks": "New York Knicks",
}


def fetch_draftkings():
    """
    DraftKings Nash mobile API — no authentication required.
    NBA league ID = 42648.
    """
    url = "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusnj/v1/leagues/42648.json"
    try:
        raw = _get_json(url, headers={
            "User-Agent": "DraftKings/15.2 iOS/17.0",
            "Accept": "application/json",
        })
    except Exception as e:
        print(f"  [DraftKings] Fetch error: {e}")
        return []

    sel_by_market = {}
    for sel in raw.get("selections", []):
        mid = sel.get("marketId", "")
        sel_by_market.setdefault(mid, []).append(sel)

    events = {e["id"]: e for e in raw.get("events", [])}
    mkt_by_event = {}
    for mkt in raw.get("markets", []):
        mkt_by_event.setdefault(mkt.get("eventId", ""), []).append(mkt)

    games = []
    for eid, ev in events.items():
        parts = ev.get("participants", [])
        home_p = next((p for p in parts if p.get("venueRole") == "Home"), {})
        away_p = next((p for p in parts if p.get("venueRole") == "Away"), {})
        home_raw = home_p.get("name", "")
        away_raw = away_p.get("name", "")
        home_team = _DK_TEAM_MAP.get(home_raw, normalize_team(home_raw))
        away_team = _DK_TEAM_MAP.get(away_raw, normalize_team(away_raw))

        game = {
            "id": str(eid),
            "home_team": home_team,
            "away_team": away_team,
            "start_time": ev.get("startEventDate", ""),
            "source": "draftkings",
            "markets": {},
        }

        for mkt in mkt_by_event.get(eid, []):
            mkt_id = mkt.get("id", "")
            mkt_name = mkt.get("name", "").lower()
            sels = sel_by_market.get(mkt_id, [])
            outcomes = []
            for sel in sels:
                display_odds = sel.get("displayOdds", {})
                american = display_odds.get("american", "").replace("\u2212", "-")
                outcomes.append({
                    "name": sel.get("label", ""),
                    "american": american,
                    "decimal": str(sel.get("trueOdds", "")),
                    "handicap": str(sel.get("points", "")) if sel.get("points") != "" else "",
                })
            if "moneyline" in mkt_name:
                game["markets"]["moneyline"] = outcomes
            elif "spread" in mkt_name:
                game["markets"]["spread"] = outcomes
            elif "total" in mkt_name and "player" not in mkt_name:
                game["markets"]["total"] = outcomes

        games.append(game)

    print(f"  [DraftKings] {len(games)} games")
    return games


# ─── Source 3: ActionNetwork ──────────────────────────────────────────────────

# Book ID mapping (ActionNetwork internal IDs)
_ACTION_BOOKS = {
    15:  "draftkings",
    30:  "fanduel",
    68:  "betmgm",
    69:  "caesars",
    76:  "pointsbet",
    123: "pinnacle",
    19:  "betrivers",
    283: "bet365",
    100: "bovada",
    111: "betway",
}

ACTION_BOOK_IDS = ",".join(str(k) for k in _ACTION_BOOKS)


def fetch_actionnetwork():
    """
    ActionNetwork free scoreboard API.
    Returns moneyline, spread, total, AND public bet/money percentages.
    Sharp/square divergence detectable when bet% != money%.
    """
    url = (
        f"https://api.actionnetwork.com/web/v1/scoreboard/nba"
        f"?periods=event&bookIds={ACTION_BOOK_IDS}"
    )
    try:
        raw = _get_json(url)
    except Exception as e:
        print(f"  [ActionNetwork] Fetch error: {e}")
        return []

    games_raw = raw.get("games", [])
    games = []

    for g in games_raw:
        teams = g.get("teams", [])
        away_id = g.get("away_team_id")
        home_id = g.get("home_team_id")
        away_obj = next((t for t in teams if t["id"] == away_id), {})
        home_obj = next((t for t in teams if t["id"] == home_id), {})

        home_team = normalize_team(home_obj.get("full_name", ""))
        away_team = normalize_team(away_obj.get("full_name", ""))

        # Find the best available odds entry (first with valid ML)
        odds_list = g.get("odds", [])
        main_odds = next(
            (o for o in odds_list if o.get("ml_away") and o.get("ml_home")), {}
        )

        # Find Pinnacle line specifically (book_id=123)
        pin_odds = next(
            (o for o in odds_list if o.get("book_id") == 123 and o.get("ml_away")), {}
        )

        game = {
            "id": str(g.get("id", "")),
            "home_team": home_team,
            "away_team": away_team,
            "start_time": g.get("start_time", ""),
            "source": "actionnetwork",
            "markets": {},
            # Public money data for sharp/square analysis
            "public_data": {
                "ml_away_bets_pct":  main_odds.get("ml_away_public"),   # % of tickets
                "ml_home_bets_pct":  main_odds.get("ml_home_public"),
                "ml_away_money_pct": main_odds.get("ml_away_money"),    # % of $
                "ml_home_money_pct": main_odds.get("ml_home_money"),
                "spread_away_bets_pct":  main_odds.get("spread_away_public"),
                "spread_home_bets_pct":  main_odds.get("spread_home_public"),
                "spread_away_money_pct": main_odds.get("spread_away_money"),
                "spread_home_money_pct": main_odds.get("spread_home_money"),
                "over_bets_pct":   main_odds.get("total_over_public"),
                "under_bets_pct":  main_odds.get("total_under_public"),
                "over_money_pct":  main_odds.get("total_over_money"),
                "under_money_pct": main_odds.get("total_under_money"),
            },
            # Pinnacle line (sharp reference)
            "pinnacle": {
                "ml_away": pin_odds.get("ml_away"),
                "ml_home": pin_odds.get("ml_home"),
                "spread":  pin_odds.get("spread_away"),
                "total":   pin_odds.get("total"),
            } if pin_odds else {},
            # Raw multi-book odds
            "multi_book": [],
        }

        # Build markets from main odds
        if main_odds.get("ml_away") and main_odds.get("ml_home"):
            game["markets"]["moneyline"] = [
                {"name": away_team, "american": str(main_odds["ml_away"])},
                {"name": home_team, "american": str(main_odds["ml_home"])},
            ]
        if main_odds.get("spread_away") is not None:
            sp_a = main_odds.get("spread_away_line", -110)
            sp_h = main_odds.get("spread_home_line", -110)
            game["markets"]["spread"] = [
                {"name": away_team, "american": str(sp_a), "handicap": str(main_odds["spread_away"])},
                {"name": home_team, "american": str(sp_h), "handicap": str(main_odds["spread_home"])},
            ]
        if main_odds.get("total") is not None:
            game["markets"]["total"] = [
                {"name": "Over",  "american": str(main_odds.get("over", -110)),  "handicap": str(main_odds["total"])},
                {"name": "Under", "american": str(main_odds.get("under", -110)), "handicap": str(main_odds["total"])},
            ]

        # Per-book odds
        book_seen = {}
        for o in odds_list:
            bid = o.get("book_id")
            bname = _ACTION_BOOKS.get(bid, f"book_{bid}")
            if bname not in book_seen and o.get("ml_away") and o.get("ml_home"):
                book_seen[bname] = True
                game["multi_book"].append({
                    "book": bname,
                    "ml_away": o.get("ml_away"),
                    "ml_home": o.get("ml_home"),
                    "spread":  o.get("spread_away"),
                    "total":   o.get("total"),
                })

        games.append(game)

    print(f"  [ActionNetwork] {len(games)} games")
    return games


# ─── Source 4: SBR live ───────────────────────────────────────────────────────

SBR_BASE = "https://www.sportsbookreview.com/betting-odds/nba-basketball/money-line/"
SBR_PREFERRED = ["betmgm", "fanduel", "draftkings", "caesars", "bet365"]


def fetch_sbr_date(game_date, retries=3):
    """
    Scrape SportsBettingReview for a specific date.
    Parses the embedded __NEXT_DATA__ JSON.
    Good for both live (today) and historical closing lines.
    """
    url = f"{SBR_BASE}?date={game_date}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.5",
    }

    content = None
    for attempt in range(retries):
        try:
            content = _get(url, headers=headers, timeout=30)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (attempt + 1) * 10
                print(f"    [SBR] Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    [SBR] HTTP {e.code} for {game_date}")
                return []
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(5)
            else:
                print(f"    [SBR] Error for {game_date}: {e}")
                return []

    if not content:
        return []

    match = re.search(r'__NEXT_DATA__[^>]*>([^<]+)<', content)
    if not match:
        return []

    try:
        d = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    tables = d.get("props", {}).get("pageProps", {}).get("oddsTables", [])
    if not tables:
        return []

    rows = tables[0].get("oddsTableModel", {}).get("gameRows", [])
    games = []

    for row in rows:
        gv = row.get("gameView", {})
        away_full = normalize_team(gv.get("awayTeam", {}).get("fullName", ""))
        home_full = normalize_team(gv.get("homeTeam", {}).get("fullName", ""))
        start_date = game_date

        ml_home = ml_away = None
        book_used = None
        odds_views = row.get("oddsViews", [])

        # Try preferred books first
        for pbook in SBR_PREFERRED:
            for ov in odds_views:
                if not isinstance(ov, dict):
                    continue
                if ov.get("sportsbook", "").lower() != pbook:
                    continue
                cl = ov.get("currentLine", {})
                if not cl:
                    continue
                mh = cl.get("homeOdds")
                ma = cl.get("awayOdds")
                if mh is not None and ma is not None and mh != 0 and ma != 0:
                    ml_home, ml_away, book_used = mh, ma, pbook
                    break
            if ml_home is not None:
                break

        # Fallback: first valid book
        if ml_home is None:
            for ov in odds_views:
                if not isinstance(ov, dict):
                    continue
                cl = ov.get("currentLine", {})
                if not cl:
                    continue
                mh, ma = cl.get("homeOdds"), cl.get("awayOdds")
                if mh is not None and ma is not None and mh != 0 and ma != 0:
                    ml_home, ml_away = mh, ma
                    book_used = ov.get("sportsbook", "unknown")
                    break

        if ml_home is None:
            continue

        games.append({
            "id": f"sbr-{start_date}-{home_full}",
            "home_team": home_full,
            "away_team": away_full,
            "start_time": start_date,
            "source": "sbr",
            "book": book_used or "sbr_consensus",
            "markets": {
                "moneyline": [
                    {"name": away_full, "american": str(ml_away)},
                    {"name": home_full, "american": str(ml_home)},
                ]
            },
        })

    return games


def fetch_sbr_today():
    """Fetch today's NBA odds from SBR."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    games = fetch_sbr_date(today)
    print(f"  [SBR] {len(games)} games for {today}")
    return games


def fetch_sbr_range(start_date, end_date, delay=2.5):
    """
    Scrape SBR for a date range. Used for historical CLV data.
    Returns list of game dicts with closing moneylines.
    """
    all_games = []
    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    total = (end - current).days + 1
    i = 0
    while current <= end:
        ds = current.strftime("%Y-%m-%d")
        print(f"  [SBR] {ds} ({i+1}/{total})", end=" ")
        games = fetch_sbr_date(ds)
        if games:
            all_games.extend(games)
            print(f"-> {len(games)} games")
        else:
            print("-> 0 games")
        i += 1
        current += timedelta(days=1)
        if current <= end:
            time.sleep(delay)
    return all_games


# ─── Cascade fetch ────────────────────────────────────────────────────────────

def fetch_live_odds():
    """
    Fetch live odds from all free sources, cascading on failure.
    Returns (games, source_name).
    Priority: ActionNetwork (most data) > Bovada > DraftKings > SBR
    """
    sources = [
        ("actionnetwork", fetch_actionnetwork),
        ("bovada",        fetch_bovada),
        ("draftkings",    fetch_draftkings),
        ("sbr",           fetch_sbr_today),
    ]
    for name, fn in sources:
        try:
            games = fn()
            if games:
                return games, name
        except Exception as e:
            print(f"  [{name}] Failed: {e}")
    return [], "none"


def fetch_all_sources():
    """
    Fetch from ALL free sources in parallel (sequential for VM safety).
    Merge: ActionNetwork as primary, enrich with Bovada/DK data.
    """
    results = {}

    for name, fn in [
        ("actionnetwork", fetch_actionnetwork),
        ("bovada",        fetch_bovada),
        ("draftkings",    fetch_draftkings),
    ]:
        try:
            results[name] = fn()
        except Exception as e:
            print(f"  [{name}] Failed: {e}")
            results[name] = []

    # Merge: ActionNetwork is canonical (has public money data)
    # Enrich with Bovada spread/total if ActionNetwork missing
    merged = {}

    for g in results.get("actionnetwork", []):
        key = (g["home_team"], g["away_team"])
        merged[key] = g

    for source in ("bovada", "draftkings"):
        for g in results.get(source, []):
            key = (g["home_team"], g["away_team"])
            if key not in merged:
                merged[key] = g
            else:
                # Enrich missing markets
                existing = merged[key]
                for mkt_type, mkt_data in g.get("markets", {}).items():
                    if mkt_type not in existing.get("markets", {}):
                        existing.setdefault("markets", {})[mkt_type] = mkt_data

    games = list(merged.values())
    print(f"  [Merged] {len(games)} unique games across all sources")
    return games


# ─── Market analysis ──────────────────────────────────────────────────────────

def analyze_game(game, model_probs=None):
    """
    Compute implied probabilities, edge vs model, sharp/square signal.

    model_probs: dict {(home, away): home_prob} from our prediction model.
    Returns enriched game dict with analysis fields.
    """
    home = game["home_team"]
    away = game["away_team"]
    ml = game.get("markets", {}).get("moneyline", [])

    # Extract moneyline odds
    home_american = away_american = None
    for oc in ml:
        name = oc.get("name", "")
        am = oc.get("american", "")
        if name == home or normalize_team(name) == home:
            home_american = am
        elif name == away or normalize_team(name) == away:
            away_american = am

    # Fall back to ActionNetwork's direct fields
    if home_american is None and "multi_book" in game:
        for b in game.get("multi_book", []):
            if b.get("ml_home"):
                home_american = b["ml_home"]
                away_american = b["ml_away"]
                break

    # Implied probabilities
    home_implied = american_to_implied(home_american) if home_american else None
    away_implied = american_to_implied(away_american) if away_american else None
    nv_home, nv_away = no_vig_prob(home_implied, away_implied)

    # Model predictions
    model_home_prob = None
    if model_probs:
        key = (home, away)
        rev_key = (away, home)
        if key in model_probs:
            model_home_prob = model_probs[key]
        elif rev_key in model_probs:
            model_home_prob = 1 - model_probs[rev_key]

    # Edge calculation (positive = value on home side)
    home_edge = calc_edge(model_home_prob, nv_home) if model_home_prob and nv_home else None

    # Sharp/square divergence
    # Sharp money = money percentage (proportional to $)
    # Square money = ticket percentage (proportional to # bets)
    sharp_signal = None
    public_data = game.get("public_data", {})
    ml_away_bets  = public_data.get("ml_away_bets_pct")
    ml_away_money = public_data.get("ml_away_money_pct")
    ml_home_bets  = public_data.get("ml_home_bets_pct")
    ml_home_money = public_data.get("ml_home_money_pct")

    if ml_away_bets is not None and ml_away_money is not None:
        # Reverse line movement: public bets on away but money on home = sharp home
        bets_away = int(ml_away_bets)
        money_away = int(ml_away_money)
        divergence = money_away - bets_away  # positive = sharp money on away beyond ticket count

        if abs(divergence) >= 15:  # 15% divergence threshold
            if divergence > 0:
                sharp_signal = f"SHARP_AWAY: {bets_away}% tickets vs {money_away}% money on {away}"
            else:
                sharp_signal = f"SHARP_HOME: {ml_home_bets}% tickets vs {ml_home_money}% money on {home}"

    analysis = {
        "home_team": home,
        "away_team": away,
        "matchup": f"{away} @ {home}",
        "start_time": game.get("start_time", ""),
        "source": game.get("source", ""),
        "odds": {
            "home_american": home_american,
            "away_american": away_american,
            "home_decimal": american_to_decimal(home_american) if home_american else None,
            "away_decimal": american_to_decimal(away_american) if away_american else None,
        },
        "implied_prob": {
            "home_raw": home_implied,
            "away_raw": away_implied,
            "home_no_vig": nv_home,
            "away_no_vig": nv_away,
            "vig_pct": round((home_implied + away_implied - 1) * 100, 2) if home_implied and away_implied else None,
        },
        "model": {
            "home_prob": model_home_prob,
            "away_prob": round(1 - model_home_prob, 6) if model_home_prob else None,
            "home_edge": home_edge,
            "away_edge": round(-home_edge, 6) if home_edge else None,
        },
        "public_data": public_data,
        "sharp_signal": sharp_signal,
        "markets": game.get("markets", {}),
        "multi_book": game.get("multi_book", []),
        "pinnacle": game.get("pinnacle", {}),
    }

    return analysis


def detect_steam_moves(current_games, previous_games, threshold_pct=5.0):
    """
    Detect steam moves: line movement > threshold_pct in probability space.
    current_games, previous_games: lists of analyzed game dicts.
    Returns list of steam move alerts.
    """
    prev_map = {}
    for g in previous_games:
        key = (g.get("home_team", ""), g.get("away_team", ""))
        prev_map[key] = g

    steam_moves = []
    for g in current_games:
        key = (g.get("home_team", ""), g.get("away_team", ""))
        prev = prev_map.get(key)
        if not prev:
            continue

        curr_nv = g.get("implied_prob", {}).get("home_no_vig")
        prev_nv = prev.get("implied_prob", {}).get("home_no_vig")
        if curr_nv is None or prev_nv is None:
            continue

        move_pct = abs(curr_nv - prev_nv) * 100
        if move_pct >= threshold_pct:
            direction = "HOME" if curr_nv > prev_nv else "AWAY"
            steam_moves.append({
                "matchup": g["matchup"],
                "direction": direction,
                "prob_before": prev_nv,
                "prob_after": curr_nv,
                "move_pct": round(move_pct, 2),
                "ml_before": prev.get("odds", {}).get("home_american"),
                "ml_after": g.get("odds", {}).get("home_american"),
            })

    return steam_moves


def load_model_predictions():
    """
    Load our model's game predictions from the latest predictions file.
    Returns dict {(home_team, away_team): home_prob}.
    """
    import glob as glob_mod

    pred_dir = Path("/home/lahargnedebartoli/nomos-nba-agent/data/results")
    pred_files = sorted(glob_mod.glob(str(pred_dir / "predictions-*.json")), reverse=True)

    # Also check mon-ipad data dir
    for f in sorted((BASE_DIR / "data" / "nba-agent").glob("predictions-*.json"), reverse=True):
        if str(f) not in pred_files:
            pred_files.insert(0, str(f))

    for fpath in pred_files[:3]:
        try:
            with open(fpath) as f:
                data = json.load(f)

            probs = {}
            games = data if isinstance(data, list) else data.get("games", data.get("predictions", []))
            for g in games:
                home = normalize_team(g.get("home_team", g.get("home", "")))
                away = normalize_team(g.get("away_team", g.get("away", "")))
                prob = g.get("home_prob", g.get("model_prob", g.get("predicted_prob")))
                if home and away and prob is not None:
                    probs[(home, away)] = float(prob)

            if probs:
                print(f"  [Model] Loaded {len(probs)} predictions from {Path(fpath).name}")
                return probs
        except Exception as e:
            continue

    print("  [Model] No predictions found")
    return {}


def load_previous_market():
    """Load previous market snapshot for steam detection."""
    crew_path = Path("/home/lahargnedebartoli/nomos-nba-agent/data/results/crew-market.json")
    for p in [crew_path, MARKET_PATH]:
        try:
            if p.exists():
                data = json.loads(p.read_text())
                return data.get("games", [])
        except Exception:
            continue
    return []


# ─── Historical odds to CSV ───────────────────────────────────────────────────

def fetch_historical_range(start_date, end_date, output_path=None, delay=2.5):
    """
    Scrape SBR for a historical date range, save to CSV.
    Uses existing nba_2008-2025.csv for pre-2024 data.
    """
    if output_path is None:
        output_path = HIST_DIR / f"nba_{start_date}_{end_date}.csv"

    print(f"\nFetching historical odds: {start_date} to {end_date}")
    games = fetch_sbr_range(start_date, end_date, delay=delay)

    if not games:
        print("No games fetched.")
        return

    # Write CSV
    fieldnames = ["date", "home_team", "away_team", "ml_home", "ml_away", "book", "source"]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for g in games:
            ml = g.get("markets", {}).get("moneyline", [])
            home_american = away_american = ""
            home = g["home_team"]
            away = g["away_team"]
            for oc in ml:
                if oc.get("name") == home:
                    home_american = oc.get("american", "")
                elif oc.get("name") == away:
                    away_american = oc.get("american", "")
            writer.writerow({
                "date": g.get("start_time", "")[:10],
                "home_team": home,
                "away_team": away,
                "ml_home": home_american,
                "ml_away": away_american,
                "book": g.get("book", "sbr"),
                "source": "sbr_scrape",
            })

    print(f"Saved {len(games)} games to {output_path}")
    return games


# ─── Main output builder ──────────────────────────────────────────────────────

def build_market_output(games, analyzed, steam_moves, timestamp):
    """
    Build crew-market.json compatible output.
    Also identifies CLV opportunities and sharp/square divergence.
    """
    clv_opportunities = []
    sharp_square = []

    for a in analyzed:
        # CLV opportunity: model edge > 3%
        home_edge = a.get("model", {}).get("home_edge")
        if home_edge is not None and abs(home_edge) >= 0.03:
            side = a["home_team"] if home_edge > 0 else a["away_team"]
            clv_opportunities.append({
                "matchup": a["matchup"],
                "side": side,
                "edge": round(abs(home_edge) * 100, 2),
                "direction": "HOME" if home_edge > 0 else "AWAY",
                "model_prob": a["model"].get("home_prob") if home_edge > 0 else a["model"].get("away_prob"),
                "market_prob": a["implied_prob"].get("home_no_vig") if home_edge > 0 else a["implied_prob"].get("away_no_vig"),
            })

        # Sharp/square divergence
        if a.get("sharp_signal"):
            pd = a.get("public_data", {})
            sharp_square.append({
                "matchup": a["matchup"],
                "signal": a["sharp_signal"],
                "ml_bets_away_pct":  pd.get("ml_away_bets_pct"),
                "ml_money_away_pct": pd.get("ml_away_money_pct"),
                "ml_bets_home_pct":  pd.get("ml_home_bets_pct"),
                "ml_money_home_pct": pd.get("ml_home_money_pct"),
            })

    return {
        "agent": "market",
        "timestamp": timestamp,
        "sources": list({g.get("source", "") for g in games}),
        "games": [
            {
                "matchup":    a["matchup"],
                "start_time": a["start_time"],
                "source":     a["source"],
                "odds": {
                    "home_american": a["odds"]["home_american"],
                    "away_american": a["odds"]["away_american"],
                    "home_decimal":  a["odds"]["home_decimal"],
                    "away_decimal":  a["odds"]["away_decimal"],
                    "spread":        a.get("markets", {}).get("spread", [{}])[0].get("handicap"),
                    "total":         a.get("markets", {}).get("total", [{}])[0].get("handicap"),
                },
                "implied_prob": a["implied_prob"].get("home_no_vig"),
                "model_prob":   a["model"].get("home_prob"),
                "edge":         a["model"].get("home_edge"),
                "public_data":  a.get("public_data", {}),
                "pinnacle":     a.get("pinnacle", {}),
                "multi_book":   a.get("multi_book", []),
            }
            for a in analyzed
        ],
        "steam_moves": steam_moves,
        "clv_opportunities": clv_opportunities,
        "sharp_square_divergence": sharp_square,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FREE NBA odds fetcher — no paid APIs.")
    parser.add_argument("--source", choices=["all", "actionnetwork", "bovada", "draftkings", "sbr"],
                        default="all", help="Data source to use")
    parser.add_argument("--historical", nargs=2, metavar=("START", "END"),
                        help="Fetch historical odds for date range (YYYY-MM-DD YYYY-MM-DD)")
    parser.add_argument("--output", default=None, help="Output path (for historical mode)")
    parser.add_argument("--delay", type=float, default=2.5,
                        help="Seconds between SBR requests (historical mode)")
    parser.add_argument("--steam-threshold", type=float, default=5.0,
                        help="% probability shift to flag as steam move (default 5.0)")
    args = parser.parse_args()

    # Historical mode
    if args.historical:
        start, end = args.historical
        fetch_historical_range(start, end, output_path=args.output, delay=args.delay)
        return

    # Live mode
    ts = datetime.now(timezone.utc).isoformat()
    print(f"\n=== NBA Free Odds Fetcher — {ts[:19]} UTC ===\n")

    # Fetch odds
    if args.source == "all":
        games = fetch_all_sources()
    elif args.source == "actionnetwork":
        games = fetch_actionnetwork()
    elif args.source == "bovada":
        games = fetch_bovada()
    elif args.source == "draftkings":
        games = fetch_draftkings()
    elif args.source == "sbr":
        games = fetch_sbr_today()
    else:
        games = []

    if not games:
        print("\nNo games found from any source.")
        # Write empty output so downstream scripts don't crash
        empty = {"games": [], "timestamp": ts, "agent": "market", "sources": []}
        LIVE_ODDS_PATH.write_text(json.dumps(empty, indent=2))
        return

    # Load model predictions and previous market
    model_probs = load_model_predictions()
    previous = load_previous_market()

    # Analyze each game
    print(f"\n=== Analysing {len(games)} games ===")
    analyzed = [analyze_game(g, model_probs) for g in games]

    # Detect steam moves
    steam = detect_steam_moves(analyzed, previous, threshold_pct=args.steam_threshold)
    if steam:
        print(f"\n STEAM MOVES DETECTED: {len(steam)}")
        for s in steam:
            print(f"  {s['matchup']}: {s['direction']} +{s['move_pct']}% move")
    else:
        print("\nNo steam moves detected.")

    # Print summary
    print(f"\n=== Market Summary ===")
    for a in analyzed:
        home = a["home_team"]
        away = a["away_team"]
        ml_h = a["odds"]["home_american"]
        ml_a = a["odds"]["away_american"]
        nv_h = a["implied_prob"].get("home_no_vig")
        edge = a["model"].get("home_edge")
        pd = a.get("public_data", {})
        bets_h = pd.get("ml_home_bets_pct", "?")
        money_h = pd.get("ml_home_money_pct", "?")

        edge_str = f"  edge={edge*100:+.1f}%" if edge else ""
        pub_str  = f"  public={bets_h}%bets/{money_h}%money(home)" if bets_h != "?" else ""
        sig_str  = f"  *** {a['sharp_signal']}" if a.get("sharp_signal") else ""
        print(f"  {away:30s} @ {home:30s} | ML: {ml_a}/{ml_h} | nv_home={nv_h:.3f}{edge_str}{pub_str}{sig_str}")

    # Build output
    output = build_market_output(games, analyzed, steam, ts)

    # Write outputs
    LIVE_ODDS_PATH.write_text(json.dumps({"games": games, "timestamp": ts}, indent=2))
    FLAT_ODDS_PATH.write_text(json.dumps(games, indent=2))
    MARKET_PATH.write_text(json.dumps(output, indent=2))

    # Write to crew-market.json (for agent compatibility)
    crew_path = Path("/home/lahargnedebartoli/nomos-nba-agent/data/results/crew-market.json")
    crew_path.parent.mkdir(parents=True, exist_ok=True)
    crew_path.write_text(json.dumps(output, indent=2))

    print(f"\nWrote:")
    print(f"  {LIVE_ODDS_PATH}")
    print(f"  {FLAT_ODDS_PATH}")
    print(f"  {MARKET_PATH}")
    print(f"  {crew_path}")

    # Summary stats
    clv = output["clv_opportunities"]
    sharp = output["sharp_square_divergence"]
    print(f"\nCLV opportunities (>3% edge): {len(clv)}")
    for c in clv:
        print(f"  {c['matchup']}: {c['side']} +{c['edge']:.1f}%")
    print(f"Sharp/square divergences: {len(sharp)}")
    for s in sharp:
        print(f"  {s['matchup']}: {s['signal']}")


if __name__ == "__main__":
    main()
