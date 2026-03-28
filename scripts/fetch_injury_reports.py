#!/usr/bin/env python3
"""
NBA Injury Report Parser
========================
Downloads and parses official NBA injury report PDFs.

URL pattern: https://ak-static.cms.nba.com/referee/injury/Injury-Report_{date}_{time}.pdf
Tries multiple time suffixes (01PM-07PM) until a valid PDF is found.

Output: data/injuries/injury_report_{date}.json

Usage:
    python scripts/fetch_injury_reports.py                    # today
    python scripts/fetch_injury_reports.py --date 2025-03-01  # specific date
    python scripts/fetch_injury_reports.py --date 2025-03-01 --verbose
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, date
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

import pdfplumber

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
DATA_DIR = REPO_DIR / "data" / "injuries"
STAR_FILE = REPO_DIR / "data" / "star_players.json"

BASE_URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_{date}_{time}.pdf"
TIME_SUFFIXES = ["01PM", "02PM", "03PM", "04PM", "05PM", "06PM", "07PM"]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
}

# ---------------------------------------------------------------------------
# Status -> impact mapping
# ---------------------------------------------------------------------------
STATUS_IMPACT = {
    "out": 1.0,
    "doubtful": 0.8,
    "questionable": 0.4,
    "probable": 0.1,
    "available": 0.0,
}

# ---------------------------------------------------------------------------
# Team abbreviation mapping (full names as they appear in the PDF, no spaces)
# ---------------------------------------------------------------------------
TEAM_ABBREV = {
    "atlantahawks": "ATL",
    "bostonceltics": "BOS",
    "brooklynnets": "BKN",
    "charlottebobcats": "CHA",
    "charlottehornets": "CHA",
    "chicagobulls": "CHI",
    "clevelandcavaliers": "CLE",
    "dallasmavericks": "DAL",
    "denvernuggets": "DEN",
    "detroitpistons": "DET",
    "goldenstatewarriors": "GSW",
    "houstonrockets": "HOU",
    "indianapacers": "IND",
    "laclippers": "LAC",
    "losangelesclippers": "LAC",
    "lalakers": "LAL",
    "losangeleslakers": "LAL",
    "memphisgrizzlies": "MEM",
    "miamiheat": "MIA",
    "milwaukeebucks": "MIL",
    "minnesotatimberwolves": "MIN",
    "neworleanspelicans": "NOP",
    "newyorkknicks": "NYK",
    "oklahomacitythunder": "OKC",
    "orlandomagic": "ORL",
    "philadelphia76ers": "PHI",
    "phoenixsuns": "PHX",
    "portlandtrailblazers": "POR",
    "sacramentokings": "SAC",
    "sanantoniospurs": "SAS",
    "torontoraptors": "TOR",
    "utahjazz": "UTA",
    "washingtonwizards": "WAS",
}

# Sorted by length descending so longer names match first
TEAM_NAMES_SORTED = sorted(TEAM_ABBREV.keys(), key=len, reverse=True)

VALID_STATUSES = {"Out", "Doubtful", "Questionable", "Probable", "Available"}
STATUS_PATTERN = "|".join(VALID_STATUSES)

HEADER_WORDS = {"PlayerName", "GameTime", "GameDate", "Matchup", "Team",
                "CurrentStatus", "Reason"}


def load_star_players() -> dict:
    """Load star players data. Returns dict mapping 'Last, First' -> ws_per_game."""
    if not STAR_FILE.exists():
        print(f"[WARN] Star players file not found: {STAR_FILE}")
        return {}
    with open(STAR_FILE) as f:
        data = json.load(f)
    stars = {}
    for name, info in data.get("players", {}).items():
        stars[name] = info.get("ws_per_game", 0.15)
    return stars


def download_pdf(target_date: str, verbose: bool = False) -> str | None:
    """
    Try to download the injury report PDF for the given date.
    Tries time suffixes in reverse order (07PM first -- later is more complete).
    Returns path to downloaded temp file, or None if not found.
    """
    for time_suffix in reversed(TIME_SUFFIXES):
        url = BASE_URL.format(date=target_date, time=time_suffix)
        if verbose:
            print(f"  Trying: {url}")
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            resp = urlopen(req, timeout=15)
            if resp.status == 200:
                content = resp.read()
                if len(content) < 500:
                    if verbose:
                        print(f"    -> Too small ({len(content)} bytes), skipping")
                    continue
                tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                tmp.write(content)
                tmp.close()
                if verbose:
                    print(f"    -> Downloaded {len(content):,} bytes ({time_suffix})")
                return tmp.name
        except HTTPError as e:
            if verbose:
                print(f"    -> HTTP {e.code}")
        except (URLError, OSError) as e:
            if verbose:
                print(f"    -> Error: {e}")
    return None


def _resolve_team(raw_team: str) -> str | None:
    """Map a raw team string (e.g. 'WashingtonWizards') to abbreviation."""
    if not raw_team:
        return None
    key = raw_team.lower().replace(" ", "")
    return TEAM_ABBREV.get(key)


def _find_team_in_text(text: str) -> tuple[str | None, int]:
    """
    Find a team name anywhere in text. Returns (abbreviation, end_index) or (None, -1).
    """
    lower = text.lower().replace(" ", "")
    for tname in TEAM_NAMES_SORTED:
        idx = lower.find(tname)
        if idx >= 0:
            return TEAM_ABBREV[tname], idx + len(tname)
    return None, -1


def _normalize_name(raw: str) -> str:
    """Normalize player name from PDF 'Last,First' to 'Last, First'."""
    return re.sub(r",\s*", ", ", raw.strip())


def _display_name(name: str) -> str:
    """Convert 'Last, First' to 'First Last' for display."""
    parts = [p.strip() for p in name.split(",", 1)]
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    return name


def _is_player_name(text: str) -> bool:
    """Check if text looks like a player name (Last,First format)."""
    return bool(re.match(
        r"^[A-Za-z\-']+(?:Jr\.|Sr\.|III|II|IV|V)?\s*,\s*[A-Za-z\-']+",
        text
    ))


def _clean_reason(reason: str) -> str:
    """Clean up a reason string."""
    # Join hyphen-broken words (e.g. "Hyper-\nextension" -> "Hyperextension")
    reason = re.sub(r"-\s+", "", reason)
    reason = " ".join(reason.split())
    return reason.strip()


# ---------------------------------------------------------------------------
# Unified row type for cross-page processing
# ---------------------------------------------------------------------------

def _normalize_row(cells: list[str]) -> dict:
    """
    Normalize a table row of any column count into a standard dict.
    Returns: {"team": str, "player": str, "status": str, "reason": str}
    """
    ncols = len(cells)

    if ncols >= 6:
        # Page 1: [GameTime, Matchup, Team, PlayerName, CurrentStatus, Reason]
        return {
            "team": cells[2],
            "player": cells[3],
            "status": cells[4],
            "reason": cells[5],
        }
    elif ncols == 4:
        # [Team_or_empty, PlayerName, CurrentStatus, Reason]
        return {
            "team": cells[0],
            "player": cells[1],
            "status": cells[2],
            "reason": cells[3],
        }
    elif ncols == 3:
        # [PlayerName, CurrentStatus, Reason] -- no team column
        if cells[1] in VALID_STATUSES:
            return {"team": "", "player": cells[0], "status": cells[1], "reason": cells[2]}
        else:
            # Probably [empty, empty, reason_continuation]
            return {"team": "", "player": "", "status": "", "reason": cells[2]}
    elif ncols == 2:
        return {"team": "", "player": "", "status": "", "reason": cells[1]}
    elif ncols == 1:
        return {"team": "", "player": "", "status": "", "reason": cells[0]}
    return {"team": "", "player": "", "status": "", "reason": ""}


def _extract_team_context_from_text(page) -> list[tuple[str, str]]:
    """
    Extract (team_abbrev, first_player_after_team) pairs from raw page text.
    This provides team context for pages where the table extraction loses team info.
    Returns list of (team_abbrev, first_player_name_after).
    """
    text = page.extract_text()
    if not text:
        return []

    results = []
    lines = text.split("\n")
    for line in lines:
        if line.strip().startswith("Injury Report:") or line.strip().startswith("GameDate"):
            continue
        if re.match(r"^Page\s*\d+\s*of\s*\d+$", line.strip()):
            continue

        # Strip game date/time/matchup prefix
        cleaned = line.strip()
        cleaned = re.sub(r"^\d{2}/\d{2}/\d{4}\s+", "", cleaned)
        cleaned = re.sub(r"^\d{2}:\d{2}\(ET\)\s+", "", cleaned)
        cleaned = re.sub(r"^[A-Z]{2,3}@[A-Z]{2,3}\s+", "", cleaned)

        lower_nospace = cleaned.lower().replace(" ", "")
        for tname in TEAM_NAMES_SORTED:
            if tname in lower_nospace:
                team_abbrev = TEAM_ABBREV[tname]
                # Find the player name after the team name
                # Remove team name from the cleaned string
                idx = lower_nospace.find(tname)
                after = lower_nospace[idx + len(tname):]
                # Try to find a player name in what follows
                # Map back to original case by counting characters
                orig_idx = 0
                count = 0
                for ch_idx, ch in enumerate(cleaned):
                    if ch.lower() == cleaned.lower()[ch_idx]:
                        count += 1
                after_text = cleaned
                # Actually, just find a "Last,First" pattern after the team name
                m = re.search(
                    r"([A-Za-z\-']+(?:Jr\.|Sr\.|III|II|IV|V)?\s*,\s*[A-Za-z\-']+)",
                    cleaned
                )
                player_after = ""
                if m:
                    player_after = m.group(1)
                results.append((team_abbrev, player_after))
                break

    return results


def parse_pdf(pdf_path: str, verbose: bool = False) -> list[dict]:
    """
    Parse the injury report PDF and return player entries.
    Uses a two-phase approach:
    1. Extract structured rows from tables + team context from raw text
    2. Process rows with look-ahead for multi-line reasons
    """
    all_rows = []  # list of {"team", "player", "status", "reason"}
    page_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_count = page_idx + 1
            tables = page.extract_tables(TABLE_SETTINGS)

            # For pages with 3-column tables, get team context from raw text
            team_context = []  # (team_abbrev, first_player)
            page_has_3col = False

            for table in tables:
                for r in table:
                    if r and len(r) == 3 and any((c or "").strip() for c in r):
                        page_has_3col = True
                        break
                if page_has_3col:
                    break

            if page_has_3col:
                team_context = _extract_team_context_from_text(page)

            # Track which team context entries we've "consumed"
            team_ctx_idx = 0

            for table in tables:
                for row in table:
                    if not row:
                        continue

                    cells = [(c or "").strip() for c in row]
                    if not any(c for c in cells):
                        continue

                    fields = _normalize_row(cells)

                    # Skip headers
                    if fields["player"] in HEADER_WORDS or fields["team"] in HEADER_WORDS:
                        continue
                    if not any(fields[k] for k in ("team", "player", "status", "reason")):
                        continue

                    # For 3-column rows, inject team from text context
                    if len(cells) == 3 and not fields["team"]:
                        # Check if this player matches the next team context entry
                        while team_ctx_idx < len(team_context):
                            ctx_team, ctx_player = team_context[team_ctx_idx]
                            if ctx_player and fields["player"]:
                                # Normalize for comparison
                                fp = fields["player"].lower().replace(" ", "")
                                cp = ctx_player.lower().replace(" ", "")
                                if fp == cp or fp.startswith(cp[:10]):
                                    fields["team"] = ctx_team
                                    team_ctx_idx += 1
                                    break
                            team_ctx_idx += 1
                        else:
                            # No more context -- try to use previous context
                            pass

                    # Resolve team abbreviation
                    if fields["team"]:
                        resolved = _resolve_team(fields["team"])
                        if resolved:
                            fields["team"] = resolved
                        elif len(fields["team"]) == 3 and fields["team"].isupper():
                            pass  # Already an abbreviation
                        else:
                            fields["team"] = ""

                    all_rows.append(fields)

    # ---- Pass 2: assign teams and assemble multi-line reasons ----
    #
    # Build a team assignment map from raw text across all pages.
    # Then iterate rows, tracking current team.

    # First, build an ordered list of (team, player) from raw text of ALL pages
    team_player_order = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split("\n"):
                cleaned = line.strip()
                if not cleaned or cleaned.startswith("Injury Report:") or cleaned.startswith("GameDate"):
                    continue
                if re.match(r"^Page\s*\d+\s*of\s*\d+$", cleaned):
                    continue

                # Strip date/time/matchup prefix
                cleaned = re.sub(r"^\d{2}/\d{2}/\d{4}\s+", "", cleaned)
                cleaned = re.sub(r"^\d{2}:\d{2}\(ET\)\s+", "", cleaned)
                cleaned = re.sub(r"^[A-Z]{2,3}@[A-Z]{2,3}\s+", "", cleaned)

                lower_nospace = cleaned.lower().replace(" ", "")
                for tname in TEAM_NAMES_SORTED:
                    if lower_nospace.startswith(tname):
                        team_abbrev = TEAM_ABBREV[tname]
                        team_player_order.append(team_abbrev)
                        break

    # Now process all_rows with team tracking
    entries = []
    current_team = None
    team_order_idx = 0

    def _is_reason_only(r):
        return r["reason"] and not r["player"] and r["status"] not in VALID_STATUSES

    def _is_player_row(r):
        return r["player"] and _is_player_name(r["player"]) and r["status"] in VALID_STATUSES

    # Advance team from team_player_order when we see a team in a row
    def update_team(row):
        nonlocal current_team, team_order_idx
        if row["team"]:
            current_team = row["team"]
            # Also advance the team_order_idx to stay in sync
            while team_order_idx < len(team_player_order):
                if team_player_order[team_order_idx] == current_team:
                    team_order_idx += 1
                    break
                team_order_idx += 1

    # For 3-col rows without team, we need to figure out team from context.
    # Build a player->team map from the raw text.
    player_team_map = {}
    with pdfplumber.open(pdf_path) as pdf:
        cur_t = None
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split("\n"):
                cleaned = line.strip()
                if not cleaned:
                    continue
                # Strip prefixes
                c2 = re.sub(r"^\d{2}/\d{2}/\d{4}\s+", "", cleaned)
                c2 = re.sub(r"^\d{2}:\d{2}\(ET\)\s+", "", c2)
                c2 = re.sub(r"^[A-Z]{2,3}@[A-Z]{2,3}\s+", "", c2)

                lower_nospace = c2.lower().replace(" ", "")
                for tname in TEAM_NAMES_SORTED:
                    if lower_nospace.startswith(tname):
                        cur_t = TEAM_ABBREV[tname]
                        # Remove team name and check for player
                        remainder = c2
                        # Walk through original string to skip team chars
                        oi = 0
                        ti = 0
                        while ti < len(tname) and oi < len(remainder):
                            if remainder[oi].lower() == tname[ti]:
                                ti += 1
                            oi += 1
                        remainder = remainder[oi:].strip()
                        m = re.match(
                            r"([A-Za-z\-']+(?:Jr\.|Sr\.|III|II|IV|V)?\s*,\s*[A-Za-z\-']+)",
                            remainder
                        )
                        if m:
                            pname = _normalize_name(m.group(1))
                            player_team_map[pname] = cur_t
                        break
                else:
                    # No team found -- check for player name
                    m = re.match(
                        r"^([A-Za-z\-']+(?:Jr\.|Sr\.|III|II|IV|V)?\s*,\s*[A-Za-z\-']+)",
                        c2
                    )
                    if m and cur_t:
                        pname = _normalize_name(m.group(1))
                        player_team_map[pname] = cur_t

    # Now do the actual assembly
    pending = None
    i = 0

    def flush_pending():
        nonlocal pending
        if pending and pending.get("name") and pending.get("status"):
            pending["reason"] = _clean_reason(pending.get("reason", ""))
            entries.append(pending)
        pending = None

    while i < len(all_rows):
        row = all_rows[i]

        # Update team from row
        if row["team"]:
            current_team = row["team"]

        # Player row
        if _is_player_row(row):
            flush_pending()

            # Determine team: explicit row team > player_team_map > current_team
            pname = _normalize_name(row["player"])
            if row["team"]:
                team = row["team"]
            elif pname in player_team_map:
                team = player_team_map[pname]
            else:
                team = current_team or "UNK"

            if team and team != current_team:
                current_team = team

            pending = {
                "team": team or "UNK",
                "name": pname,
                "status": row["status"],
                "reason": row["reason"],
            }
            i += 1
            continue

        # Reason-only row
        if _is_reason_only(row):
            # Collect consecutive reason-only rows
            reason_texts = []
            while i < len(all_rows) and _is_reason_only(all_rows[i]):
                reason_texts.append(all_rows[i]["reason"])
                i += 1

            # Check what follows
            next_is_empty_player = (
                i < len(all_rows)
                and _is_player_row(all_rows[i])
                and not all_rows[i]["reason"]
            )

            if next_is_empty_player and reason_texts:
                if len(reason_texts) == 1:
                    if pending and not pending["reason"]:
                        # Post-reason for pending (pending has no reason yet)
                        pending["reason"] = reason_texts[0]
                    else:
                        # Pre-reason for next player
                        flush_pending()
                        nr = all_rows[i]
                        if nr["team"]:
                            current_team = nr["team"]
                        pname = _normalize_name(nr["player"])
                        team = nr["team"] or player_team_map.get(pname, current_team or "UNK")
                        if team:
                            current_team = team
                        pending = {
                            "team": team or "UNK",
                            "name": pname,
                            "status": nr["status"],
                            "reason": reason_texts[0],
                        }
                        i += 1
                else:
                    # Multiple reason rows before next player with no reason.
                    # Split: find where pre-reason starts (scans backwards for
                    # a new reason descriptor like "Injury/Illness" or "GLeague").
                    split = len(reason_texts)
                    for k in range(len(reason_texts) - 1, -1, -1):
                        txt = reason_texts[k]
                        if re.match(r"^(Injury|GLeague|Not|Concussion|Rest|League|Personal|Return|Trade|Inactive)", txt):
                            split = k
                            break
                    if split == len(reason_texts):
                        split = len(reason_texts) - 1  # last one is pre-reason

                    # Post-reasons for pending
                    if pending:
                        for txt in reason_texts[:split]:
                            pending["reason"] = (pending["reason"] + " " + txt).strip()

                    # Pre-reasons for next player
                    pre_parts = reason_texts[split:]
                    flush_pending()
                    nr = all_rows[i]
                    if nr["team"]:
                        current_team = nr["team"]
                    pname = _normalize_name(nr["player"])
                    team = nr["team"] or player_team_map.get(pname, current_team or "UNK")
                    if team:
                        current_team = team
                    pending = {
                        "team": team or "UNK",
                        "name": pname,
                        "status": nr["status"],
                        "reason": " ".join(pre_parts),
                    }
                    i += 1
            else:
                # All are post-reasons for pending
                if pending:
                    for txt in reason_texts:
                        pending["reason"] = (pending["reason"] + " " + txt).strip()
            continue

        # Team-only or other row
        i += 1

    flush_pending()

    if verbose:
        print(f"  Parsed {len(entries)} player entries from {page_count} pages")

    return entries


def build_report(entries: list[dict], target_date: str, star_players: dict,
                 verbose: bool = False) -> dict:
    """Build the final JSON report from parsed entries."""
    teams = {}

    for entry in entries:
        team = entry["team"]
        status_lower = entry["status"].lower()
        impact = STATUS_IMPACT.get(status_lower, 0.5)

        player_record = {
            "name": _display_name(entry["name"]),
            "status": entry["status"],
            "reason": entry.get("reason", ""),
            "impact": impact,
        }

        # Check if this player is a star (try both name formats)
        name_key = entry["name"]
        ws_per_game = star_players.get(name_key, 0.0)
        if ws_per_game == 0.0:
            ws_per_game = star_players.get(_display_name(entry["name"]), 0.0)

        if ws_per_game > 0:
            player_record["star"] = True
            player_record["ws_per_game"] = ws_per_game

        if team not in teams:
            teams[team] = {"players": [], "total_impact": 0.0, "star_out": False}

        teams[team]["players"].append(player_record)
        teams[team]["total_impact"] = round(
            teams[team]["total_impact"] + impact, 2
        )

        # star_out if a star player has impact >= 0.8 (Out or Doubtful)
        if ws_per_game > 0 and impact >= 0.8:
            teams[team]["star_out"] = True

    # Sort players within each team by impact descending
    for team_data in teams.values():
        team_data["players"].sort(key=lambda p: -p["impact"])

    report = {
        "date": target_date,
        "generated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_players": len(entries),
        "total_teams": len(teams),
        "teams": dict(sorted(teams.items())),
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="NBA Injury Report Parser")
    parser.add_argument("--date", type=str, default=None,
                        help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output file path (default: data/injuries/injury_report_{date}.json)")
    args = parser.parse_args()

    target_date = args.date or date.today().strftime("%Y-%m-%d")

    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError:
        print(f"[ERROR] Invalid date format: {target_date}. Use YYYY-MM-DD.")
        sys.exit(1)

    print(f"[INFO] Fetching NBA injury report for {target_date}...")

    pdf_path = download_pdf(target_date, verbose=args.verbose)
    if not pdf_path:
        print(f"[WARN] No injury report PDF found for {target_date}")
        print("  This is normal if:")
        print("  - No games scheduled on this date")
        print("  - The report hasn't been published yet")
        print("  - The date is in the future")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        out_path = args.output or str(DATA_DIR / f"injury_report_{target_date}.json")
        empty_report = {
            "date": target_date,
            "generated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_players": 0,
            "total_teams": 0,
            "teams": {},
            "error": "no_pdf_found",
        }
        with open(out_path, "w") as f:
            json.dump(empty_report, f, indent=2)
        print(f"[INFO] Empty report written to {out_path}")
        sys.exit(0)

    try:
        print("[INFO] Parsing PDF...")
        entries = parse_pdf(pdf_path, verbose=args.verbose)

        star_players = load_star_players()
        if args.verbose:
            print(f"  Loaded {len(star_players)} star players")

        report = build_report(entries, target_date, star_players, verbose=args.verbose)

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        out_path = args.output or str(DATA_DIR / f"injury_report_{target_date}.json")
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"[OK] Injury report saved to {out_path}")
        print(f"     {report['total_players']} players across {report['total_teams']} teams")

        star_teams = {t: d for t, d in report["teams"].items() if d.get("star_out")}
        if star_teams:
            print(f"\n     STAR PLAYERS OUT/DOUBTFUL:")
            for team, data in star_teams.items():
                star_names = [
                    p["name"]
                    for p in data["players"]
                    if p.get("star") and p["impact"] >= 0.8
                ]
                if star_names:
                    print(f"       {team}: {', '.join(star_names)} (total_impact={data['total_impact']})")

        high_impact = sorted(
            report["teams"].items(),
            key=lambda x: -x[1]["total_impact"],
        )[:5]
        if high_impact:
            print(f"\n     TOP 5 MOST IMPACTED TEAMS:")
            for team, data in high_impact:
                n_out = sum(1 for p in data["players"] if p["status"] == "Out")
                print(f"       {team}: impact={data['total_impact']}, out={n_out}, star_out={data['star_out']}")

    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


if __name__ == "__main__":
    main()
