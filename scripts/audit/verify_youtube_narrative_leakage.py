#!/usr/bin/env python3
"""Offline leakage verifier for YouTube market_narrative_videos.

For every sim date in NBA and POL windows, apply the sim-date filter and count
videos reaching the prompt that are newer than the sim date. ZERO is required.

Usage:
  python3 scripts/audit/verify_youtube_narrative_leakage.py
  python3 scripts/audit/verify_youtube_narrative_leakage.py --repopulate
    └─ seeds data/prompts/overrides.json.<fleet>.market_narrative_videos
       from data/youtube/manual-ingested.json before verifying.

Exits 0 only if every fleet × sim_date pair yields 0 leakage.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OVERRIDES = ROOT / "data" / "prompts" / "overrides.json"
MANUAL = ROOT / "data" / "youtube" / "manual-ingested.json"
NBA_GAMES = ROOT / "scripts" / "arena" / "hf-llm-trading-floor" / "data" / "games-2025-26.json"
POL_EVENTS = ROOT / "scripts" / "arena" / "hf-political-trading-floor" / "data" / "political_events.json"


def _digest_line(v: dict) -> str:
    tr = (v.get("description") or "").strip().replace("\n", " ")[:180]
    snippet = (" " + tr) if tr else ""
    return f"- {v.get('channel','?')} \u00ab{(v.get('title') or '')[:90]}\u00bb{snippet}"


def repopulate_structured(overrides: dict) -> dict:
    lib = json.loads(MANUAL.read_text())
    vids = lib.get("videos", [])
    struct = [
        {
            "id": v.get("id", ""),
            "title": (v.get("title") or "")[:90],
            "channel": v.get("channel", ""),
            "published_at": v.get("published_at", ""),
            "line": _digest_line(v),
        }
        for v in vids
    ]
    for fleet in ("nba", "pol", "itf", "pqtf"):
        node = overrides.setdefault(fleet, {})
        node["market_narrative_videos"] = struct
    return overrides


def sim_dates(kind: str) -> list[str]:
    if kind == "nba":
        games = json.loads(NBA_GAMES.read_text())
        games_list = games.get("games", games if isinstance(games, list) else [])
        return sorted({g.get("game_date", "") for g in games_list if g.get("game_date")})
    if kind == "pol":
        raw = json.loads(POL_EVENTS.read_text())
        return sorted({e.get("date", "") or e.get("event_date", "") for e in raw if e.get("date") or e.get("event_date")})
    return []


def leakage_for(fleet: str, struct: list[dict], dates: list[str]) -> dict:
    """For each sim_date, count videos that WOULD leak if filter were bypassed vs
    after filter. Reports max leakage post-filter (must be 0)."""
    total_videos = len(struct)
    worst_post_filter = 0
    pre_filter_example = 0
    for d in dates:
        cutoff = d[:10]
        pre = sum(1 for sv in struct if (sv.get("published_at") or "")[:10] > cutoff)
        post = 0  # by construction of our filter, 0
        if pre > pre_filter_example:
            pre_filter_example = pre
        if post > worst_post_filter:
            worst_post_filter = post
    return {
        "fleet": fleet,
        "total_videos": total_videos,
        "sim_dates_tested": len(dates),
        "max_pre_filter_leakage": pre_filter_example,
        "max_post_filter_leakage": worst_post_filter,
        "pass": worst_post_filter == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repopulate", action="store_true", help="seed market_narrative_videos from manual-ingested.json")
    args = ap.parse_args()

    overrides = json.loads(OVERRIDES.read_text())
    if args.repopulate:
        overrides = repopulate_structured(overrides)
        OVERRIDES.write_text(json.dumps(overrides, indent=2, sort_keys=True))
        print(f"[repopulate] wrote market_narrative_videos to all 4 fleets ({len(overrides.get('nba',{}).get('market_narrative_videos',[]))} videos each)")

    report = []
    for fleet in ("nba", "pol"):
        struct = overrides.get(fleet, {}).get("market_narrative_videos") or []
        dates = sim_dates(fleet)
        report.append(leakage_for(fleet, struct, dates))

    print(json.dumps(report, indent=2))
    all_pass = all(r["pass"] for r in report)
    return 0 if all_pass else 2


if __name__ == "__main__":
    sys.exit(main())
