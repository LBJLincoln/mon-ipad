#!/usr/bin/env python3
"""Write data/tracks/t{1..4}-latest.json — 4-track status summaries.

Consumed by:
- scripts/claude-session.sh (launcher display)
- scripts/tracks/orchestrate.sh (Opus-every-8h reader)

Each file is ≤2kB: {timestamp, status, last_metric, last_action, next_proposal, blocked_on}.

Cron: hourly. Pulls from monitoring/health/fleet-matrix/TF status already on disk.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
TRACKS_DIR = ROOT / "data" / "tracks"
TRACKS_DIR.mkdir(parents=True, exist_ok=True)


def _load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        return None
    return None


def _fleet_best_brier() -> Optional[float]:
    sb = _load(ROOT / "data" / "fleet-matrix" / "scoreboard.json") or {}
    gb = sb.get("global_best") or {}
    return gb.get("best_brier")


def build_t1_science() -> Dict[str, Any]:
    drift = _load(ROOT / "data" / "monitoring" / "drift-summary.json") or {}
    cal = _load(ROOT / "data" / "monitoring" / "drift-calibration.json") or {}
    fleet_best = _fleet_best_brier()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "track": "T1 SCIENCE",
        "absorbs": ["D1 research", "D3 evolution", "D6 evaluation"],
        "status": "ok" if fleet_best and fleet_best < 0.225 else "watch",
        "last_metric": {
            "fleet_best_brier": fleet_best,
            "target_brier": 0.20,
            "calibration_mce": cal.get("mce"),
            "calibration_ece": cal.get("ece"),
            "drift_alarms": drift.get("n_alarms", 0),
        },
        "last_action": "21 evolution islands running, fleet-matrix scoreboard fresh every 30min",
        "next_proposal": "If fleet_best stagnates >24h, trigger diversify on worst 2 islands",
        "blocked_on": None if fleet_best else "fleet-matrix has no brier reports yet",
    }


def build_t2_platform() -> Dict[str, Any]:
    parity = _load(ROOT / "data" / "departments" / "cross-repo" / "engine-parity.json") or {}
    infra = _load(ROOT / "data" / "infra-status.json") or {}
    fleet = _load(ROOT / "data" / "nba-fleet-status.json") or {}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "track": "T2 PLATFORM",
        "absorbs": ["D2 engineering", "D7 infra", "D9 cross-repo"],
        "status": "ok" if parity.get("sha_match") else "watch",
        "last_metric": {
            "engine_sha_match": parity.get("sha_match"),
            "nba_fleet_up": fleet.get("n_up"),
            "infra_alerts": infra.get("alerts", 0),
        },
        "last_action": "Both TFs deployed w/ T13/T14 NVIDIA parity 2026-04-17",
        "next_proposal": "Wire auto-deploy-engine for engine.py parity drift detection",
        "blocked_on": None,
    }


def build_t3_market() -> Dict[str, Any]:
    telegram = _load(ROOT / "data" / "telegram-stats.json") or {}
    subs = _load(ROOT / "data" / "monetization" / "subs.json") or {}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "track": "T3 MARKET",
        "absorbs": ["D4 product", "D5 business"],
        "status": "behind" if (subs.get("count", 0) < 5) else "ok",
        "last_metric": {
            "telegram_subs": telegram.get("subs", 0),
            "paying_subs": subs.get("count", 0),
            "mrr_usd": subs.get("mrr", 0),
            "target_may1": 95,
        },
        "last_action": "@Nomos42Picks channel + Stripe paywall scaffolded",
        "next_proposal": "Publish first daily-picks pilot to warm the channel",
        "blocked_on": "Need ≥5 subs by May 8 to pay Claude Code CLI",
    }


def build_t4_capital() -> Dict[str, Any]:
    nba_tf = _load(ROOT / "data" / "nba-agent" / "tf-llm-health.json") or {}
    pol_tf = _load(ROOT / "data" / "nba-agent" / "tf-llm-health-pol.json") or {}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "track": "T4 CAPITAL",
        "absorbs": ["D8 finance", "NBA TF", "POL TF"],
        "status": "ok",
        "last_metric": {
            "nba_tf_total_bankroll": nba_tf.get("total_bankroll"),
            "pol_tf_total_bankroll": pol_tf.get("total_bankroll"),
            "nba_tf_agents": 14,   # post T13/T14 NVIDIA
            "pol_tf_agents": 14,
            "target_collective_usd": 1_000_000,
            "min_deploy_pct": 0.75,
        },
        "last_action": "T13 nvidia-minimax + T14 nvidia-llama70 deployed to both TFs 2026-04-17",
        "next_proposal": "Monitor NVIDIA agent performance 24h; add parlay sizing if NBA conviction high",
        "blocked_on": None,
    }


def main() -> None:
    builders = {
        "t1-latest.json": build_t1_science,
        "t2-latest.json": build_t2_platform,
        "t3-latest.json": build_t3_market,
        "t4-latest.json": build_t4_capital,
    }
    for name, fn in builders.items():
        out = fn()
        (TRACKS_DIR / name).write_text(json.dumps(out, indent=2))
        # Also write the TRACKS.md-spec filename alias for orchestrator symmetry.
        alias = name.replace("-latest.json", "-" + out["track"].split()[-1].lower() + ".json")
        (TRACKS_DIR / alias).write_text(json.dumps(out, indent=2))
        print(f"[tracks] wrote {name} + {alias} — status={out['status']}")


if __name__ == "__main__":
    main()
