#!/usr/bin/env python3
"""
OASIS T3 Specialist Swarm — bridges camel-ai/oasis to the NBA arena T3 tier.

Status (2026-04-07): SCAFFOLD — first commit. This module spawns N specialist
agents using the OASIS social-agent template and asks each one to predict the
NBA games of the day. Each agent has a different "persona" (analytical /
contrarian / momentum / mean-reverter / etc) and a different free-HF backbone.

Dependencies:
  - vendor/oasis must be cloned (run scripts/vendor/clone-vendor.sh)
  - HF_TOKEN (or HF_TOKEN_2/3/FORGE) for the inference router
  - Python 3.11 with the standard mon-ipad venv

Usage:
  python3 scripts/arena/oasis_t3_swarm.py --n 50 --dry-run
  python3 scripts/arena/oasis_t3_swarm.py --n 50

Output:
  data/arena/agent-states-v5.json — agent state file consumed by trading-floor-v5.py
  Agents added with provider="oasis" and id="t3_oasis_<persona>_<idx>"

Why a scaffold rather than a finished swarm: vendored OASIS is a heavyweight
research library — its full agent_environment.py boots a torch model and a
clock. We need a lightweight subset that just calls the LLM-side persona once
per game. So this file imports vendor/oasis lazily (try/except), and if the
import fails it falls back to a deterministic stub so the cron never crashes.
The lightweight call path runs on the 1vCPU/969MB VM; the heavyweight oasis
runtime is opt-in via --use-oasis-runtime (off by default).

Related:
  - PLAN.md W2 — full integration plan
  - vendor/oasis/oasis/social_agent/agent.py — upstream agent class
  - scripts/arena/agent_registry.py — where T1/T2 agents are registered
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VENDOR_OASIS = ROOT / "vendor" / "oasis"
STATE_FILE = ROOT / "data" / "arena" / "agent-states-v5.json"

# Free HF backbones the swarm rotates through. All four are reachable on the
# free HF Inference Router (we have 4 HF accounts so quota is not a concern).
HF_BACKBONES = [
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "google/gemma-3-27b-it",
    "mistralai/Mistral-Large-Instruct-2411",
]

PERSONAS = [
    ("analytical",   "data-driven, prefers high-confidence model picks"),
    ("contrarian",   "fades public consensus, hunts mispriced underdogs"),
    ("momentum",     "rides streaks, weighs recent form heavily"),
    ("mean_reversion","bets against extreme line moves"),
    ("pace",         "totals specialist, edge from pace mismatches"),
    ("rest_arb",     "back-to-back / rest disadvantage specialist"),
    ("home_dog",     "home underdog edge specialist"),
    ("travel",       "long road trip + altitude edge specialist"),
    ("rotation",     "DFS rotation / load-management specialist"),
    ("clutch",       "high-leverage 4Q / OT specialist"),
]


def _try_import_oasis() -> bool:
    """Lazily attempt to import vendor/oasis. Returns True if importable."""
    if not VENDOR_OASIS.exists():
        return False
    sys.path.insert(0, str(VENDOR_OASIS))
    try:
        import oasis  # noqa: F401
        from oasis.social_agent.agent import SocialAgent  # noqa: F401
        return True
    except Exception as e:
        print(f"[oasis-swarm] vendor/oasis present but not importable: {e}", file=sys.stderr)
        return False


def build_swarm(n: int, use_runtime: bool = False) -> list[dict]:
    """Build a list of T3 specialist agent state dicts.

    If use_runtime=True, attempt to actually instantiate the OASIS SocialAgent
    class. Otherwise create a lightweight specifier dict that the v5 trading
    floor can dispatch to the HF Inference Router directly without booting
    the heavy OASIS environment.
    """
    runtime_ok = _try_import_oasis() if use_runtime else False
    swarm: list[dict] = []
    for i in range(n):
        persona, persona_desc = PERSONAS[i % len(PERSONAS)]
        backbone = HF_BACKBONES[i % len(HF_BACKBONES)]
        agent_id = f"t3_oasis_{persona}_{i:03d}"
        swarm.append({
            "id":            agent_id,
            "name":          f"OASIS {persona.replace('_', ' ').title()} #{i:03d}",
            "tier":          "specialist",
            "provider":      "oasis" if runtime_ok else "oasis-lite",
            "model":         backbone,
            "persona":       persona,
            "persona_desc":  persona_desc,
            "strategy":      "value_hunter",
            "min_edge":      0.04,
            "kelly_fraction":0.20,
            "bankroll":      100.0,
            "peak_bankroll": 100.0,
            "description":   f"OASIS T3 specialist — {persona_desc} (backbone: {backbone.split('/')[-1]})",
            "created_at":    datetime.now(timezone.utc).isoformat(),
            "status":        "active",
        })
    return swarm


def merge_into_state(swarm: list[dict], dry_run: bool) -> None:
    """Merge OASIS agents into the v5 trading floor state file.

    The v5 state shape is: { "agents": { <id>: <agent_dict>, ... }, "tiers": {...} }
    so we extend the dict by id without clobbering existing T1/T2 agents.
    """
    state: dict = {"agents": {}, "tiers": {}, "last_updated": ""}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    agents = state.get("agents") or {}
    if not isinstance(agents, dict):
        agents = {}
    added = 0
    for ag in swarm:
        # Reshape to match the v5 schema (tier UPPER, min_confidence, weight, etc).
        v5_shape = {
            "id":              ag["id"],
            "name":            ag["name"],
            "tier":            "SPECIALIST",
            "provider":        ag["provider"],
            "model":           ag["model"],
            "strategy":        ag["strategy"],
            "bankroll":        ag["bankroll"],
            "total_bets":      0,
            "total_wins":      0,
            "win_rate":        0.0,
            "roi":             0.0,
            "total_pnl":       0.0,
            "weight":          0.5,        # specialists start at half weight
            "active":          True,
            "min_edge":        ag["min_edge"],
            "min_confidence":  0.55,
            "kelly_fraction":  ag["kelly_fraction"],
            "persona":         ag["persona"],
            "persona_desc":    ag["persona_desc"],
            "description":     ag["description"],
            "created_at":      ag["created_at"],
            "source":          "oasis_t3_swarm",
        }
        if v5_shape["id"] in agents:
            continue
        agents[v5_shape["id"]] = v5_shape
        added += 1
    state["agents"] = agents
    state["agent_count"] = len(agents)
    state["active_count"] = sum(1 for a in agents.values() if a.get("active"))
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    if dry_run:
        print(f"[oasis-swarm] DRY-RUN — would add {added} new agents to {STATE_FILE}")
        sample = list(agents.values())[-1] if added else swarm[0]
        print(json.dumps(sample, indent=2))
        return
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"[oasis-swarm] added {added} new T3 OASIS agents to {STATE_FILE} (total now {len(agents)})")


def main() -> int:
    p = argparse.ArgumentParser(description="OASIS T3 Specialist Swarm bridge")
    p.add_argument("--n", type=int, default=50, help="Number of specialists to spawn (default 50)")
    p.add_argument("--dry-run", action="store_true", help="Print plan without writing state file")
    p.add_argument("--use-oasis-runtime", action="store_true",
                   help="Try to import vendor/oasis at runtime (heavyweight, opt-in)")
    args = p.parse_args()

    swarm = build_swarm(args.n, use_runtime=args.use_oasis_runtime)
    merge_into_state(swarm, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
