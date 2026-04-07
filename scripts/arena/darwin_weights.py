#!/usr/bin/env python3
"""
darwin_weights.py — atlas-gic Darwinian weighting for the 5 T1-T5 traders.

Reference: github.com/chrisworsey55/atlas-gic (1.3k★). Their result:
54 mutations over 18 months kept 16 traders, +22% over 173 days on a $20/mo
VM. Their rule: per-day multiplier on allocation weight, top quartile ×1.05,
bottom quartile ×0.95, bounded [0.3, 2.5]. Compounds daily so bad traders
die gracefully, good traders get more capital.

This script runs BEFORE trading-floor-v4.py via cron (or as a pre-hook in
continuous-backtest-swarm.sh). It:

  1. Reads data/arena/trading-floor-v4-latest.json for today's leaderboard.
  2. Loads the existing data/arena/trader-darwin-weights.json (or seeds 1.0).
  3. Computes the new weight per trader:
       - rank 1 of 5 (top quartile) → × 1.05
       - rank 5 of 5 (bottom quartile) → × 0.95
       - middle ranks (2, 3, 4) → unchanged
  4. Clamps to [0.3, 2.5].
  5. Writes back to data/arena/trader-darwin-weights.json with a history log.

trading-floor-v4.py reads this file via _load_darwin_weights() and multiplies
the per-trader kelly_adj by the weight, scaling up winning traders' stake
sizes and scaling down losing traders' stake sizes.

No dependencies beyond the stdlib. Safe to run on the 1vCPU VM.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LATEST = REPO / "data" / "arena" / "trading-floor-v4-latest.json"
WEIGHTS = REPO / "data" / "arena" / "trader-darwin-weights.json"

TOP_MULT = 1.05
BOTTOM_MULT = 0.95
MIN_W = 0.30
MAX_W = 2.50
HISTORY_LIMIT = 60  # keep last 60 days


def _load_weights() -> dict:
    if not WEIGHTS.exists():
        return {"traders": {}, "history": []}
    try:
        with WEIGHTS.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"traders": {}, "history": []}
            data.setdefault("traders", {})
            data.setdefault("history", [])
            return data
    except (OSError, json.JSONDecodeError):
        return {"traders": {}, "history": []}


def _save_weights(state: dict) -> None:
    tmp = WEIGHTS.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    tmp.replace(WEIGHTS)


def _clamp(x: float) -> float:
    return max(MIN_W, min(MAX_W, x))


def main() -> int:
    if not LATEST.exists():
        print(f"darwin_weights: {LATEST} not found, nothing to do", file=sys.stderr)
        return 1

    try:
        with LATEST.open("r", encoding="utf-8") as f:
            latest = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"darwin_weights: failed to read latest: {exc}", file=sys.stderr)
        return 1

    leaderboard = latest.get("leaderboard") or []
    if len(leaderboard) < 2:
        print(f"darwin_weights: only {len(leaderboard)} traders in leaderboard, skipping")
        return 0

    leaderboard = sorted(leaderboard, key=lambda t: t.get("rank", 999))
    n = len(leaderboard)
    top_cutoff = max(1, n // 4)
    bottom_cutoff = n - max(1, n // 4)

    state = _load_weights()
    traders = state["traders"]
    updates = []
    for idx, entry in enumerate(leaderboard):
        tid = entry.get("trader_id") or entry.get("name") or f"t{idx}"
        prior = float(traders.get(tid, {}).get("weight", 1.0))
        rank = entry.get("rank", idx + 1)

        if idx < top_cutoff:
            mult = TOP_MULT
            zone = "top"
        elif idx >= bottom_cutoff:
            mult = BOTTOM_MULT
            zone = "bottom"
        else:
            mult = 1.0
            zone = "middle"

        new_w = _clamp(prior * mult)
        updates.append({
            "trader_id": tid,
            "name": entry.get("name", tid),
            "rank": rank,
            "zone": zone,
            "mult": mult,
            "prior_weight": round(prior, 4),
            "new_weight": round(new_w, 4),
        })
        traders[tid] = {
            "name": entry.get("name", tid),
            "weight": round(new_w, 4),
            "last_rank": rank,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    history_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iteration": latest.get("iteration"),
        "generation": latest.get("generation"),
        "updates": updates,
    }
    state["history"].append(history_entry)
    state["history"] = state["history"][-HISTORY_LIMIT:]
    state["_meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "scripts/arena/darwin_weights.py",
        "reference": "github.com/chrisworsey55/atlas-gic",
        "rules": {
            "top_mult": TOP_MULT,
            "bottom_mult": BOTTOM_MULT,
            "min_weight": MIN_W,
            "max_weight": MAX_W,
            "top_quartile": f"ranks 1..{top_cutoff}",
            "bottom_quartile": f"ranks {bottom_cutoff + 1}..{n}",
        },
    }

    _save_weights(state)

    print(f"darwin_weights: updated {len(updates)} traders")
    for u in updates:
        arrow = "↑" if u["mult"] > 1.0 else ("↓" if u["mult"] < 1.0 else "·")
        print(f"  {arrow} {u['name']:<14} rank={u['rank']}  "
              f"{u['prior_weight']:.4f} → {u['new_weight']:.4f}  ({u['zone']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
