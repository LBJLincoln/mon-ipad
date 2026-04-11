#!/usr/bin/env python3
"""
backfill-v5-season.py — Replay the 224+ agent Trading Floor swarm across every
real 2025-26 NBA date in a single process.

Why: Phase B council logs + bet audits only existed for 5 sparse dates
(Mar 15, Apr 3/4/5/7). The user asked for full-season coverage: "but also
focus on all real games of the 2025-2026 no?????"

How:
  1. Load 1247 completed games from games-2025-26.json
  2. Convert into the v5 internal format
  3. Instantiate TradingFloorV5(dry_run=True, lite=True)
  4. For each unique date, call the same stage-1 + _generate_bets +
     _save_results path that the live swarm uses.
  5. One council-log-<date>.jsonl and bet-audit-<date>.json per date.

Dry-run is intentional: a live run over 178 dates would burn the whole API
budget. Dry-run preserves personality/tier/voter_count attribution — which is
what the councils and the Phase C UI actually need.

Usage:
  python scripts/arena/backfill-v5-season.py                 # all 178 dates
  python scripts/arena/backfill-v5-season.py --limit 20      # first 20 dates
  python scripts/arena/backfill-v5-season.py --from 2026-01-01
  python scripts/arena/backfill-v5-season.py --skip-existing # dont clobber
"""
from __future__ import annotations

import argparse
import importlib.machinery
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/termius/mon-ipad")
NBA_AGENT = Path("/home/termius/nomos-nba-agent")

sys.path.insert(0, str(ROOT / "scripts" / "arena"))

# Load api_pool once (import-cost ~60s first time)
import api_pool  # noqa: F401

# Load trading-floor-v5 via loader because of hyphen in filename
tfv5 = importlib.machinery.SourceFileLoader(
    "tfv5", str(ROOT / "scripts" / "arena" / "trading-floor-v5.py")
).load_module()


def load_season_games() -> list[dict]:
    """Load and convert real 2025-26 games into the v5 internal format."""
    raw = json.loads((NBA_AGENT / "data" / "historical" / "games-2025-26.json").read_text())
    games_raw = raw["games"]
    complete = [
        g for g in games_raw
        if g.get("home", {}).get("pts")
        and g.get("away", {}).get("pts")
        and g.get("home_team")
    ]
    v5 = []
    for g in complete:
        h = g["home"]
        a = g["away"]
        v5.append({
            "date": g["game_date"][:10],
            "home": g["home_team"],
            "away": g["away_team"],
            "home_score": h["pts"],
            "away_score": a["pts"],
            "home_won": h["pts"] > a["pts"],
            "home_stats": h,
            "away_stats": a,
        })
    return v5


def run_one_date(floor, v5_games: list[dict], date_str: str) -> dict:
    """Run the stage-1 swarm + bet synthesis for a single date.

    Mutates floor in place (appends predictions/consensus/bets). Returns a
    small report for the summary line.
    """
    day_games = [g for g in v5_games if g["date"] == date_str]
    if not day_games:
        return {"date": date_str, "games": 0, "preds": 0, "bets": 0}

    # Reset floor state to prevent leak between dates
    floor.predictions.clear()
    floor.consensus.clear()
    floor.bets.clear()
    floor.run_stats = {
        "start_time": datetime.now(timezone.utc).isoformat(),
        "end_time": "",
        "games_processed": 0,
        "agents_called": 0,
        "api_calls_made": 0,
        "api_errors": 0,
        "total_bets": 0,
        "tier_calls": {1: 0, 2: 0, 3: 0, 4: 0},
        "phase1_hits": 0,
        "multiphase_calls": 0,
    }

    standings = tfv5.compute_standings(v5_games, date_str)

    total_preds = 0
    for g in day_games:
        ctx = tfv5.build_game_context(g, None, standings, v5_games)
        game_key = f"{g['date']}_{g['away']}@{g['home']}"

        preds = floor._stage1_parallel_predict(ctx, game_key)
        total_preds += len(preds)

        # Build a minimal synthesis from the synthetic preds (majority vote)
        def _vote(cat: str, home_dir: str, away_dir: str) -> dict:
            n_home = sum(
                1 for p in preds.values()
                if isinstance(p, dict)
                and isinstance(p.get(cat), dict)
                and p[cat].get("direction") == home_dir
            )
            n_total = sum(
                1 for p in preds.values()
                if isinstance(p, dict) and isinstance(p.get(cat), dict)
            )
            if n_total == 0:
                return {"direction": home_dir, "confidence": 0.5, "agreement_pct": 0.5}
            pct = n_home / n_total
            direction = home_dir if pct >= 0.5 else away_dir
            agreement = max(pct, 1 - pct)
            return {
                "direction": direction,
                "confidence": round(0.5 + (agreement - 0.5) * 0.8, 3),
                "agreement_pct": round(agreement, 3),
            }

        synth = {
            "consensus_ml": _vote("ml_fg", "home", "away"),
            "consensus_spread": _vote("spread_fg", "home", "away"),
            "consensus_total": _vote("total_fg", "over", "under"),
            "num_agents": len(preds),
            "avg_edge_pct": 2.5,
            "top_3_bets": [],
        }
        floor.consensus[game_key] = synth

        bets = floor._generate_bets(synth, ctx, None, game_key, g, game_predictions=preds)
        floor.bets.extend(bets)
        floor.run_stats["games_processed"] += 1

    floor.run_stats["end_time"] = datetime.now(timezone.utc).isoformat()
    floor._save_results(date_str)

    return {
        "date": date_str,
        "games": len(day_games),
        "preds": total_preds,
        "bets": len(floor.bets),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Process at most N dates")
    ap.add_argument("--from", dest="from_date", default=None, help="Start from YYYY-MM-DD")
    ap.add_argument("--to", dest="to_date", default=None, help="Stop at YYYY-MM-DD (inclusive)")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Skip dates whose council-log already exists")
    args = ap.parse_args()

    print("Loading 2025-26 season games...", flush=True)
    v5_games = load_season_games()
    print(f"  Loaded {len(v5_games)} complete games", flush=True)

    all_dates = sorted({g["date"] for g in v5_games})
    if args.from_date:
        all_dates = [d for d in all_dates if d >= args.from_date]
    if args.to_date:
        all_dates = [d for d in all_dates if d <= args.to_date]
    if args.limit:
        all_dates = all_dates[: args.limit]

    print(f"  Processing {len(all_dates)} unique dates "
          f"({all_dates[0]} → {all_dates[-1]})", flush=True)

    print("Initializing TradingFloorV5(dry_run=True, lite=True)...", flush=True)
    floor = tfv5.TradingFloorV5(
        dry_run=True, multiphase=False, lite=True, force_invest=False,
    )
    print(f"  {len(floor.registry.agents)} agents loaded", flush=True)

    council_log_dir = ROOT / "data" / "arena" / "council-log-v5"
    reports: list[dict] = []
    for i, d in enumerate(all_dates, 1):
        if args.skip_existing and (council_log_dir / f"council-log-{d}.jsonl").exists():
            print(f"  [{i}/{len(all_dates)}] {d} — skipped (existing)", flush=True)
            continue

        report = run_one_date(floor, v5_games, d)
        reports.append(report)
        print(
            f"  [{i}/{len(all_dates)}] {d} — "
            f"{report['games']} games, {report['preds']} preds, "
            f"{report['bets']} bets",
            flush=True,
        )

    # Write a season-level summary
    summary_path = council_log_dir / "backfill-summary.json"
    council_log_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "scripts/arena/backfill-v5-season.py",
        "mode": "dry_run_lite",
        "total_dates": len(all_dates),
        "processed": len(reports),
        "total_games": sum(r["games"] for r in reports),
        "total_predictions": sum(r["preds"] for r in reports),
        "total_bets": sum(r["bets"] for r in reports),
        "reports": reports,
    }, indent=2))
    print(f"\nBackfill summary: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
