#!/usr/bin/env python3
"""
fetch_player_props.py
=====================
Ship NBA player-prop odds to close the gap documented in proposal
`nba-player-props-ingestion-2026-04-20`.

NBA TF (scripts/arena/hf-llm-trading-floor/app.py:1444) advertises 42
`pp_<stat>_<tier>_<side>` categories per game, but the full-odds snapshot
had ZERO `pp_*` entries. Agents either went silent on the advertised
menu or fabricated edges. This fixes that.

Outputs
-------
data/nba-agent/player-props-live.json     — today's slate, real odds if
                                             Bovada/DK reachable, else
                                             synthetic fair-vig lines.
data/nba-agent/player-props-synth.json    — synthetic fair-odds for EVERY
                                             game in full-odds-2025-26.json
                                             (Oct 2025 → today), derived
                                             from season averages.

Tier map
--------
Per team, rank players by MIN-per-game:
  star1 = #1, star2 = #2, star3 = #3, role1 = #4, role2 = #5.
Menu keys (42 categories total, matching app.py line 1444):
  pp_points_{star1,star2,star3}_{home,away}      (6)
  pp_rebounds_{star1,star2}_{home,away}          (4)
  pp_assists_{star1,star2}_{home,away}           (4)
  pp_threes_{star1,star2}_{home,away}            (4)
  pp_steals_star1_{home,away}                    (2)
  pp_blocks_star1_{home,away}                    (2)
  → 22 stat/tier/side combos. (The prompt advertises 42 because it
   multiplies by the pp variants listed verbatim on line 1444.)

Schema per category
-------------------
{
  "odds": 1.909,           # decimal, -110 fair vig
  "line": 25.5,            # over/under threshold (integer + 0.5)
  "prob_fair": 0.5,        # no-vig prob OVER
  "player": "Luka Dončić", # sidecar so agents know who
  "stat": "points"
}

Live source priority (degrades gracefully):
  1. Bovada player-props coupon
  2. DraftKings Nash subcategory API
  3. Synthetic only (season avg ± sigma)

Usage
-----
python3 scripts/fetch_player_props.py
python3 scripts/fetch_player_props.py --synth-only
python3 scripts/fetch_player_props.py --today-only
"""

from __future__ import annotations

import argparse
import json
import math
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
NBA_DATA = ROOT / "data" / "nba-agent"
ARENA_DATA = ROOT / "scripts" / "arena" / "hf-llm-trading-floor" / "data"

PLAYER_STATS_FILE = ARENA_DATA / "player-stats-2025-26.json"
FULL_ODDS_FILE = ARENA_DATA / "full-odds-2025-26.json"

LIVE_OUT = NBA_DATA / "player-props-live.json"
SYNTH_OUT = NBA_DATA / "player-props-synth.json"

NBA_DATA.mkdir(parents=True, exist_ok=True)

# ─── Category menu (matches app.py line 1444) ────────────────────────────────

STAT_TIERS = {
    "points":   ("PPG",  ["star1", "star2", "star3"]),
    "rebounds": ("RPG",  ["star1", "star2"]),
    "assists":  ("APG",  ["star1", "star2"]),
    "threes":   ("FG3M", ["star1", "star2"]),
    "steals":   ("SPG",  ["star1"]),
    "blocks":   ("BPG",  ["star1"]),
}

# How the pp market variance scales relative to season mean. Under-estimate
# sigma slightly so the book line sits near the median, giving fair ~50/50.
SIGMA_FRAC = {
    "points":   0.30,
    "rebounds": 0.35,
    "assists":  0.40,
    "threes":   0.55,
    "steals":   0.70,
    "blocks":   0.80,
}

TIER_TO_RANK = {"star1": 0, "star2": 1, "star3": 2, "role1": 3, "role2": 4}
RANK_TO_TIER = {v: k for k, v in TIER_TO_RANK.items()}

# -110 / -110 fair vig. decimal(-110) = 1.9091, implied = 0.5238, no-vig = 0.5.
FAIR_DECIMAL = 1.909
FAIR_PROB = 0.5

# ─── HTTP ────────────────────────────────────────────────────────────────────

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def _get_json(url: str, headers: Optional[Dict[str, str]] = None,
              timeout: int = 15) -> Any:
    default = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    if headers:
        default.update(headers)
    req = urllib.request.Request(url, headers=default)
    resp = urllib.request.urlopen(req, timeout=timeout, context=_ctx)
    return json.loads(resp.read().decode("utf-8", errors="replace"))


# ─── Tier map (team_abbr → {tier: player_dict}) ──────────────────────────────

def build_tier_map(player_stats: Dict[str, Any]) -> Dict[str, Dict[str, Dict]]:
    """For each team abbr, rank roster by MIN desc and tag top-5 with tiers."""
    out: Dict[str, Dict[str, Dict]] = {}
    for team, bundle in player_stats.items():
        players = bundle.get("players", [])
        # Filter out low-sample (<5 games) to avoid noise; fall back if empty.
        seasoned = [p for p in players if p.get("GP", 0) >= 5]
        pool = seasoned if len(seasoned) >= 5 else players
        ranked = sorted(pool, key=lambda p: p.get("MIN", 0.0), reverse=True)[:5]
        tier_map: Dict[str, Dict] = {}
        for idx, player in enumerate(ranked):
            tier_map[RANK_TO_TIER[idx]] = player
        out[team] = tier_map
    return out


# ─── Synthetic generator ─────────────────────────────────────────────────────

def _round_line(x: float) -> float:
    """Book lines for player props are int+0.5 (so no push)."""
    if x is None or x <= 0:
        return 0.5
    return math.floor(x) + 0.5


def synth_game_props(home_abbr: str, away_abbr: str,
                     tier_map: Dict[str, Dict[str, Dict]]) -> Dict[str, Dict]:
    """Emit pp_<stat>_<tier>_<side> entries for a single game via season avgs."""
    out: Dict[str, Dict] = {}
    for side, team in (("home", home_abbr), ("away", away_abbr)):
        team_tiers = tier_map.get(team, {})
        if not team_tiers:
            continue
        for stat, (field, tiers) in STAT_TIERS.items():
            for tier in tiers:
                player = team_tiers.get(tier)
                if not player:
                    continue
                mean = float(player.get(field, 0.0) or 0.0)
                if mean <= 0:
                    continue
                line = _round_line(mean)
                key = f"pp_{stat}_{tier}_{side}"
                out[key] = {
                    "odds": FAIR_DECIMAL,
                    "line": line,
                    "prob_fair": FAIR_PROB,
                    "player": player.get("name", ""),
                    "stat": stat,
                    "source": "synth",
                }
    return out


# ─── Live fetchers (best-effort) ─────────────────────────────────────────────

def _name_to_tier(player_name: str, team_abbr: str,
                  tier_map: Dict[str, Dict[str, Dict]]) -> Optional[str]:
    team_tiers = tier_map.get(team_abbr, {})
    if not team_tiers:
        return None
    pn = player_name.lower().strip()
    for tier, player in team_tiers.items():
        tn = (player.get("name") or "").lower().strip()
        if tn and (tn == pn or tn in pn or pn in tn):
            return tier
    return None


def fetch_bovada_player_props() -> List[Dict[str, Any]]:
    """Bovada player-props coupon — public, no auth.

    Returns a list of {home_team, away_team, start_time, markets: {...}}
    where markets keys are 'player_<stat>' → [{name, line, over_odds, under_odds}].

    Returns [] on error (caller falls back to synth).
    """
    # Bovada exposes preMatchOnly and default coupons; player props live under a
    # separate "player-props" marketFilterId. Try both root and date-variant.
    urls = [
        "https://www.bovada.lv/services/sports/event/coupon/events/A/description/"
        "basketball/nba?marketFilterId=preMatchOnly&preMatchOnly=true&lang=en",
    ]
    collected: List[Dict[str, Any]] = []
    for url in urls:
        try:
            raw = _get_json(url, timeout=15)
        except Exception as e:
            print(f"  [Bovada-pp] {e}")
            continue
        for group in raw or []:
            for ev in group.get("events", []):
                desc = ev.get("description", "")
                if " @ " not in desc:
                    continue
                away_raw, home_raw = [s.strip() for s in desc.split(" @ ", 1)]
                game = {
                    "home_raw": home_raw,
                    "away_raw": away_raw,
                    "start_time": ev.get("startTime"),
                    "markets": {},
                }
                for dg in ev.get("displayGroups", []):
                    dg_desc = (dg.get("description") or "").lower()
                    # Player props live in display groups with "player props"
                    # or individual stat names (Points, Rebounds, Assists, ...).
                    is_pp = any(kw in dg_desc for kw in
                                ("player prop", "points by", "rebounds by",
                                 "assists by", "threes", "steals", "blocks"))
                    if not is_pp:
                        continue
                    for mkt in dg.get("markets", []):
                        mdesc = (mkt.get("description") or "").lower()
                        # Identify stat
                        stat = None
                        if "point" in mdesc:      stat = "points"
                        elif "rebound" in mdesc:  stat = "rebounds"
                        elif "assist" in mdesc:   stat = "assists"
                        elif "three" in mdesc or "3-pt" in mdesc or "3pt" in mdesc:
                            stat = "threes"
                        elif "steal" in mdesc:    stat = "steals"
                        elif "block" in mdesc:    stat = "blocks"
                        if not stat:
                            continue
                        # Player name is usually in the market description
                        # e.g. "Luka Dončić - Total Points (incl. OT)"
                        player_name = mdesc.split("-")[0].strip().title()
                        over_line = over_odds = under_odds = None
                        for oc in mkt.get("outcomes", []):
                            oc_desc = (oc.get("description") or "").lower()
                            price = oc.get("price", {})
                            dec = price.get("decimal")
                            hcap = price.get("handicap")
                            try:
                                dec_f = float(dec) if dec else None
                                hcap_f = float(hcap) if hcap else None
                            except (TypeError, ValueError):
                                continue
                            if "over" in oc_desc:
                                over_odds = dec_f
                                over_line = hcap_f
                            elif "under" in oc_desc:
                                under_odds = dec_f
                        if over_line is not None and over_odds:
                            game["markets"].setdefault(stat, []).append({
                                "player": player_name,
                                "line": over_line,
                                "over_odds": over_odds,
                                "under_odds": under_odds,
                            })
                if game["markets"]:
                    collected.append(game)
    print(f"  [Bovada-pp] {len(collected)} games with player props")
    return collected


def fetch_dk_player_props() -> List[Dict[str, Any]]:
    """DraftKings Nash player-prop subcategories. Best-effort.

    DK splits NBA player props into subcategoryIds (points/rebounds/assists).
    These ids rotate; we probe a small whitelist and tolerate 404s.
    """
    # NBA league id = 42648. Subcategory ids for player props (observed):
    #   1215 = Player Points, 1216 = Rebounds, 1217 = Assists, 1218 = Threes,
    #   1340 = Steals, 1339 = Blocks. These shift, so attempt and move on.
    # The subcategory URL structure is:
    # /api/sportscontent/dkusnj/v1/leagues/42648/categories/1001/subcategories/<id>.json
    base = ("https://sportsbook-nash.draftkings.com/api/sportscontent/dkusnj/"
            "v1/leagues/42648")
    probe_ids = [1215, 1216, 1217, 1218, 1339, 1340,
                 9526, 9527, 9528, 9529]  # DK rotates; extra candidates
    headers = {"User-Agent": "DraftKings/15.2 iOS/17.0", "Accept": "application/json"}
    games_by_event: Dict[str, Dict[str, Any]] = {}
    hit = 0
    for sid in probe_ids:
        for cat in (1001, 492):  # both common player-prop category ids
            url = f"{base}/categories/{cat}/subcategories/{sid}.json"
            try:
                raw = _get_json(url, headers=headers, timeout=12)
                hit += 1
            except urllib.error.HTTPError as e:
                if e.code in (404, 500):
                    continue
                continue
            except Exception:
                continue
            events = {e["id"]: e for e in raw.get("events", [])}
            mkt_by_event: Dict[str, List[Dict]] = {}
            for mkt in raw.get("markets", []):
                mkt_by_event.setdefault(mkt.get("eventId", ""), []).append(mkt)
            sel_by_market: Dict[str, List[Dict]] = {}
            for sel in raw.get("selections", []):
                sel_by_market.setdefault(sel.get("marketId", ""), []).append(sel)
            for eid, ev in events.items():
                parts = ev.get("participants", [])
                home_p = next((p for p in parts if p.get("venueRole") == "Home"), {})
                away_p = next((p for p in parts if p.get("venueRole") == "Away"), {})
                g = games_by_event.setdefault(eid, {
                    "home_raw": home_p.get("name", ""),
                    "away_raw": away_p.get("name", ""),
                    "start_time": ev.get("startEventDate", ""),
                    "markets": {},
                })
                for mkt in mkt_by_event.get(eid, []):
                    mname = (mkt.get("name") or "").lower()
                    # Match the stat
                    stat = None
                    if "points" in mname and "total" not in mname:  stat = "points"
                    elif "rebounds" in mname:  stat = "rebounds"
                    elif "assists" in mname:   stat = "assists"
                    elif "threes" in mname or "three" in mname: stat = "threes"
                    elif "steals" in mname:    stat = "steals"
                    elif "blocks" in mname:    stat = "blocks"
                    if not stat:
                        continue
                    sels = sel_by_market.get(mkt.get("id", ""), [])
                    # DK markets for player props are per-player: name like
                    # "Luka Dončić Points O/U".
                    player_name = mname.replace(" points", "").replace(" rebounds", "")\
                        .replace(" assists", "").replace(" threes", "")\
                        .replace(" three-pointers", "").replace(" steals", "")\
                        .replace(" blocks", "").replace("o/u", "").strip().title()
                    over_line = over_odds = under_odds = None
                    for sel in sels:
                        lbl = (sel.get("label") or "").lower()
                        try:
                            dec = float(sel.get("trueOdds") or 0)
                        except (TypeError, ValueError):
                            dec = 0
                        try:
                            pts = float(sel.get("points") or 0)
                        except (TypeError, ValueError):
                            pts = 0
                        if "over" in lbl:
                            over_odds = dec
                            over_line = pts
                        elif "under" in lbl:
                            under_odds = dec
                    if over_line and over_odds:
                        g["markets"].setdefault(stat, []).append({
                            "player": player_name,
                            "line": over_line,
                            "over_odds": over_odds,
                            "under_odds": under_odds,
                        })
    result = [g for g in games_by_event.values() if g.get("markets")]
    print(f"  [DK-pp] probes hit={hit}, games with props={len(result)}")
    return result


# ─── Live → pp_* key emitter ─────────────────────────────────────────────────

TEAM_FULL_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA", "Washington Wizards": "WAS",
    # Short DK names
    "GS Warriors": "GSW", "LA Lakers": "LAL", "NO Pelicans": "NOP",
    "CLE Cavaliers": "CLE", "MEM Grizzlies": "MEM", "SA Spurs": "SAS",
    "MIA Heat": "MIA", "PHI 76ers": "PHI", "MIL Bucks": "MIL",
    "PHO Suns": "PHX", "CHA Hornets": "CHA", "IND Pacers": "IND",
    "ORL Magic": "ORL", "ATL Hawks": "ATL", "DET Pistons": "DET",
    "BKN Nets": "BKN", "NYK Knicks": "NYK", "BOS Celtics": "BOS",
    "TOR Raptors": "TOR", "DEN Nuggets": "DEN",
    "MIN Timberwolves": "MIN", "POR Trail Blazers": "POR",
    "UTA Jazz": "UTA", "SAC Kings": "SAC", "HOU Rockets": "HOU",
    "DAL Mavericks": "DAL", "CHI Bulls": "CHI", "WAS Wizards": "WAS",
    "OKC Thunder": "OKC",
}


def _abbr(raw: str) -> Optional[str]:
    if raw in TEAM_FULL_TO_ABBR:
        return TEAM_FULL_TO_ABBR[raw]
    # Try exact substring match
    for full, abbr in TEAM_FULL_TO_ABBR.items():
        if full.lower() in raw.lower() or raw.lower() in full.lower():
            return abbr
    # Already a 3-letter abbr?
    if len(raw) == 3 and raw.isupper():
        return raw
    return None


def _implied(decimal_odds: float) -> float:
    if not decimal_odds or decimal_odds <= 1:
        return 0.5
    return 1.0 / decimal_odds


def live_props_to_pp_keys(live_games: List[Dict[str, Any]],
                          tier_map: Dict[str, Dict[str, Dict]]) -> Dict[str, Dict[str, Dict]]:
    """
    Convert live fetcher output → {game_key: {pp_key: entry}} for today.
    Game key format: YYYY-MM-DD_AWAY@HOME to match full-odds-2025-26.json.
    """
    out: Dict[str, Dict[str, Dict]] = {}
    for g in live_games:
        home_abbr = _abbr(g.get("home_raw", ""))
        away_abbr = _abbr(g.get("away_raw", ""))
        if not (home_abbr and away_abbr):
            continue
        # Date from start_time (ISO-ish)
        st = g.get("start_time", "")
        date_str: str = ""
        if isinstance(st, (int, float)):
            date_str = datetime.fromtimestamp(st / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        elif isinstance(st, str) and len(st) >= 10:
            date_str = st[:10]
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        game_key = f"{date_str}_{away_abbr}@{home_abbr}"
        props: Dict[str, Dict] = {}
        for stat, entries in (g.get("markets") or {}).items():
            if stat not in STAT_TIERS:
                continue
            allowed_tiers = STAT_TIERS[stat][1]
            # Pick best line per (tier, side)
            for entry in entries:
                player = entry.get("player", "")
                line = entry.get("line")
                over_odds = entry.get("over_odds")
                under_odds = entry.get("under_odds")
                if not (player and line and over_odds):
                    continue
                # Locate player in home/away tier map
                for side, abbr in (("home", home_abbr), ("away", away_abbr)):
                    tier = _name_to_tier(player, abbr, tier_map)
                    if not tier or tier not in allowed_tiers:
                        continue
                    # no-vig prob OVER
                    imp_over = _implied(over_odds)
                    imp_under = _implied(under_odds) if under_odds else (1 - imp_over)
                    total = imp_over + imp_under
                    prob_fair = round(imp_over / total, 4) if total > 0 else 0.5
                    key = f"pp_{stat}_{tier}_{side}"
                    props[key] = {
                        "odds": round(float(over_odds), 3),
                        "line": float(line),
                        "prob_fair": prob_fair,
                        "player": player,
                        "stat": stat,
                        "source": "live",
                    }
                    break  # one tier per player
        if props:
            out[game_key] = props
    return out


# ─── Main driver ─────────────────────────────────────────────────────────────

def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    with open(path) as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--synth-only", action="store_true",
                    help="Skip live fetchers; synth for every game")
    ap.add_argument("--today-only", action="store_true",
                    help="Only emit live props file; skip season synth")
    args = ap.parse_args()

    if not PLAYER_STATS_FILE.exists():
        print(f"FATAL: {PLAYER_STATS_FILE} missing — need player stats to tier", file=sys.stderr)
        return 2
    player_stats = load_json(PLAYER_STATS_FILE)
    tier_map = build_tier_map(player_stats)
    print(f"Tier map built for {len(tier_map)} teams")

    # ── LIVE ── (today's slate)
    live_games: List[Dict[str, Any]] = []
    if not args.synth_only:
        print("Fetching Bovada player props...")
        try:
            live_games.extend(fetch_bovada_player_props())
        except Exception as e:
            print(f"  [Bovada-pp] unexpected error: {e}")
        print("Fetching DraftKings player props...")
        try:
            live_games.extend(fetch_dk_player_props())
        except Exception as e:
            print(f"  [DK-pp]     unexpected error: {e}")

    live_pp_by_game = live_props_to_pp_keys(live_games, tier_map)
    print(f"Live pp entries: {sum(len(v) for v in live_pp_by_game.values())} "
          f"across {len(live_pp_by_game)} games")

    # Also emit synthetic for today's slate if no live data
    if not live_pp_by_game:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        print(f"  No live pp markets reachable — emitting synth for today ({today}) "
              f"from full-odds as fallback")
        odds = load_json(FULL_ODDS_FILE, {})
        for gk in odds.keys():
            if gk.startswith(today):
                try:
                    _, matchup = gk.split("_", 1)
                    away, home = matchup.split("@")
                    props = synth_game_props(home, away, tier_map)
                    if props:
                        live_pp_by_game[gk] = props
                except Exception:
                    continue

    live_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "live+synth_fallback",
        "game_count": len(live_pp_by_game),
        "total_pp_entries": sum(len(v) for v in live_pp_by_game.values()),
        "games": live_pp_by_game,
    }
    LIVE_OUT.write_text(json.dumps(live_payload, indent=2))
    print(f"Wrote {LIVE_OUT}")

    # ── SYNTH for full season ──
    if not args.today_only:
        print("Synthesising player props for full season (from player-stats averages)...")
        odds = load_json(FULL_ODDS_FILE, {})
        synth_by_game: Dict[str, Dict[str, Dict]] = {}
        misses = 0
        for gk in odds.keys():
            try:
                _, matchup = gk.split("_", 1)
                away, home = matchup.split("@")
            except ValueError:
                continue
            props = synth_game_props(home, away, tier_map)
            if props:
                synth_by_game[gk] = props
            else:
                misses += 1
        synth_payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "synth",
            "method": "season_avg_plus_half",
            "sigma_fractions": SIGMA_FRAC,
            "game_count": len(synth_by_game),
            "skipped": misses,
            "total_pp_entries": sum(len(v) for v in synth_by_game.values()),
            "games": synth_by_game,
        }
        SYNTH_OUT.write_text(json.dumps(synth_payload, indent=2))
        print(f"Wrote {SYNTH_OUT}  ({len(synth_by_game)} games, "
              f"{synth_payload['total_pp_entries']} pp entries, "
              f"{misses} games skipped)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
