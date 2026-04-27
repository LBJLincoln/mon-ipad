#!/usr/bin/env python3
"""Scrape NBA 5-man lineup data via LeagueDashLineups (free nba_api endpoint).

Pulls per-team top lineup combinations + their net rating, plus/minus, minutes.
Then maps to engine cat 26b combo features (h_combo1_netrtg, etc).

Output: data/karpathy/synergy_data.json keyed by f"{team}|{season}":
  {combo1_netrtg, combo1_minutes, combo1_plus_minus, combo2_..., ..., combo5_...}

Note: this is per-SEASON not per-game (LeagueDashLineups is season-scoped).
For leakage-safety we only fetch 2024-25 stats and apply to 2025-26 games (= prior).

Usage: python3 scripts/ops/scrape_nba_lineup_synergy.py
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "karpathy" / "synergy_data.json"

NBA_TEAMS = {
    "ATL": "1610612737", "BOS": "1610612738", "BKN": "1610612751", "CHA": "1610612766",
    "CHI": "1610612741", "CLE": "1610612739", "DAL": "1610612742", "DEN": "1610612743",
    "DET": "1610612765", "GSW": "1610612744", "HOU": "1610612745", "IND": "1610612754",
    "LAC": "1610612746", "LAL": "1610612747", "MEM": "1610612763", "MIA": "1610612748",
    "MIL": "1610612749", "MIN": "1610612750", "NOP": "1610612740", "NYK": "1610612752",
    "OKC": "1610612760", "ORL": "1610612753", "PHI": "1610612755", "PHX": "1610612756",
    "POR": "1610612757", "SAC": "1610612758", "SAS": "1610612759", "TOR": "1610612761",
    "UTA": "1610612762", "WAS": "1610612764",
}


def main() -> int:
    try:
        from nba_api.stats.endpoints import leaguedashlineups
    except ImportError:
        print("nba_api missing — pip install --break-system-packages nba_api", file=sys.stderr)
        return 2

    out = {}
    if OUT.exists():
        try:
            out = json.loads(OUT.read_text())
            print(f"resume: {len(out)} teams already cached", file=sys.stderr)
        except Exception:
            out = {}
    failures = []

    # Use prior season (2024-25) for leakage-safe synergy applied to 2025-26 sim
    SEASON = "2024-25"

    for tabbr, tid in NBA_TEAMS.items():
        if tabbr in out:
            continue
        try:
            r = leaguedashlineups.LeagueDashLineups(
                team_id_nullable=tid,
                season=SEASON,
                group_quantity=5,
                measure_type_detailed_defense="Advanced",  # has NET_RATING / OFF_RATING / DEF_RATING
                per_mode_detailed="Per100Possessions",
            )
            data = r.get_dict()
            rs = data.get("resultSets", [{}])[0]
            headers = rs.get("headers", [])
            rows = rs.get("rowSet", [])
            try:
                min_idx = headers.index("MIN")
            except ValueError:
                failures.append(f"{tabbr}: no MIN header")
                continue
            netrtg_idx = headers.index("NET_RATING") if "NET_RATING" in headers else None
            plusm_idx = headers.index("PLUS_MINUS") if "PLUS_MINUS" in headers else None
            if netrtg_idx is None:
                # Fall back to OFF_RATING - DEF_RATING
                off_idx = headers.index("OFF_RATING") if "OFF_RATING" in headers else None
                def_idx = headers.index("DEF_RATING") if "DEF_RATING" in headers else None
                if off_idx is None or def_idx is None:
                    failures.append(f"{tabbr}: no rating headers ({headers[:5]})")
                    continue
            sorted_rows = sorted(rows, key=lambda x: -float(x[min_idx] or 0))[:5]
            entry = {}
            for i, lineup in enumerate(sorted_rows, start=1):
                if netrtg_idx is not None:
                    netrtg = float(lineup[netrtg_idx] or 0.0)
                else:
                    netrtg = float(lineup[off_idx] or 0) - float(lineup[def_idx] or 0)
                entry[f"combo{i}_netrtg"] = netrtg
                entry[f"combo{i}_minutes"] = float(lineup[min_idx] or 0.0)
                entry[f"combo{i}_plus_minus"] = float(lineup[plusm_idx] or 0.0) if plusm_idx is not None else 0.0
            # Pad if <5 lineups
            for i in range(len(sorted_rows) + 1, 6):
                entry[f"combo{i}_netrtg"] = 0.0
                entry[f"combo{i}_minutes"] = 10.0
                entry[f"combo{i}_plus_minus"] = 0.0
            out[tabbr] = entry
            print(f"  {tabbr}: {len(sorted_rows)} top lineups, top combo1_netrtg={entry['combo1_netrtg']}", file=sys.stderr)
            # Save incrementally so resume works on rate-limit interruptions
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(out, indent=2))
            time.sleep(2.0)  # generous to avoid rate limit
        except Exception as e:
            failures.append(f"{tabbr}: {str(e)[:80]}")
            print(f"  {tabbr} FAIL: {e}", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} teams to {OUT.name}, {len(failures)} fails")
    return 0


if __name__ == "__main__":
    sys.exit(main())
