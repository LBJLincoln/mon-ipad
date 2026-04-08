#!/usr/bin/env python3
"""
darwin_weights.py — atlas-gic Darwinian + Kelly-bankroll weighting for traders.

Two-layer weighting (Cycle 14 Tier 3):

  1. atlas-gic rank layer (unchanged, github.com/chrisworsey55/atlas-gic):
       top quartile × 1.05, bottom quartile × 0.95, clamped [0.3, 2.5]

  2. Kelly-bankroll layer (arXiv:2602.09982, Feb 2026):
       Use realized Sharpe as expected log-growth proxy (Kelly-equivalent
       under log-normal returns). Normalize so the mean weight multiplier
       is 1.0 — capital is *redistributed* across traders, not inflated.

  Combined:
       new = clamp( prior * rank_mult * (1 + KELLY_BLEND * (kelly_adj - 1)),
                    MIN_W, MAX_W )

  KELLY_BLEND ∈ [0, 1]:
    0.0 → pure atlas-gic (legacy behavior, for A/B)
    0.5 → half Kelly, half rank (default, conservative)
    1.0 → pure Kelly growth

Both layers compound over the 60-day history window so bad traders fade
and good traders accumulate capital at log-growth-optimal speed.

Expected Brier delta: ~-0.003 (paper's realized vs flat weighting on a
5-trader portfolio over 6 months; scales with Sharpe dispersion).

Env vars:
  NOMOS42_KELLY_BLEND   (default 0.5)
  NOMOS42_SHARPE_FLOOR  (default 0.5 — below this, no kelly boost)
"""

import json
import math
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

# Kelly-bankroll layer knobs (arXiv:2602.09982)
KELLY_BLEND = float(os.environ.get("NOMOS42_KELLY_BLEND", "0.5"))
SHARPE_FLOOR = float(os.environ.get("NOMOS42_SHARPE_FLOOR", "0.5"))


def compute_kelly_adj(leaderboard: list[dict]) -> dict[str, float]:
    """Per-trader Kelly-growth multiplier normalized so mean == 1.0.

    We use NBA Sharpe as the realized log-growth proxy because:
      - We don't have per-bet stake history (only win/loss counts)
      - Sharpe already encodes risk-adjusted expected log growth
      - Clamping at SHARPE_FLOOR prevents negative weights and noise

    Returns a dict of {trader_id: multiplier}. Missing traders default to 1.0.
    """
    raws: list[tuple[str, float]] = []
    for entry in leaderboard:
        tid = entry.get("trader_id") or entry.get("name") or ""
        if not tid:
            continue
        sharpe = float(entry.get("nba_sharpe") or 0.0)
        # Kelly growth proxy: max(0, sharpe - floor). Floor cuts the noise
        # at low Sharpe where the sign isn't reliable.
        raw = max(0.0, sharpe - SHARPE_FLOOR)
        raws.append((tid, raw))

    if not raws:
        return {}

    # Normalize to mean 1.0 so total capital isn't inflated — we just
    # redistribute across traders.
    total = sum(r for _, r in raws)
    n = len(raws)
    if total <= 0.0:
        # All traders below floor → everyone gets 1.0 (no Kelly signal)
        return {tid: 1.0 for tid, _ in raws}
    mean_raw = total / n
    return {tid: (raw / mean_raw) if mean_raw > 0 else 1.0 for tid, raw in raws}


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

    # Kelly-bankroll layer — precompute per-trader adj factor
    kelly_adj = compute_kelly_adj(leaderboard)

    state = _load_weights()
    traders = state["traders"]
    updates = []
    for idx, entry in enumerate(leaderboard):
        tid = entry.get("trader_id") or entry.get("name") or f"t{idx}"
        prior = float(traders.get(tid, {}).get("weight", 1.0))
        rank = entry.get("rank", idx + 1)

        if idx < top_cutoff:
            rank_mult = TOP_MULT
            zone = "top"
        elif idx >= bottom_cutoff:
            rank_mult = BOTTOM_MULT
            zone = "bottom"
        else:
            rank_mult = 1.0
            zone = "middle"

        # Kelly layer: blend (1 + beta * (adj - 1)); beta=0 disables.
        k_adj = kelly_adj.get(tid, 1.0)
        kelly_mult = 1.0 + KELLY_BLEND * (k_adj - 1.0)
        # Guard against pathological Kelly values
        kelly_mult = max(0.1, min(3.0, kelly_mult))

        combined_mult = rank_mult * kelly_mult
        new_w = _clamp(prior * combined_mult)
        updates.append({
            "trader_id": tid,
            "name": entry.get("name", tid),
            "rank": rank,
            "zone": zone,
            "rank_mult": round(rank_mult, 4),
            "kelly_adj": round(k_adj, 4),
            "kelly_mult": round(kelly_mult, 4),
            "mult": round(combined_mult, 4),
            "prior_weight": round(prior, 4),
            "new_weight": round(new_w, 4),
            "nba_sharpe": round(float(entry.get("nba_sharpe") or 0.0), 4),
        })
        traders[tid] = {
            "name": entry.get("name", tid),
            "weight": round(new_w, 4),
            "last_rank": rank,
            "last_kelly_adj": round(k_adj, 4),
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
        "reference": [
            "github.com/chrisworsey55/atlas-gic (rank layer)",
            "arXiv:2602.09982 (Kelly-bankroll ensemble weighting, Feb 2026)",
        ],
        "rules": {
            "top_mult": TOP_MULT,
            "bottom_mult": BOTTOM_MULT,
            "min_weight": MIN_W,
            "max_weight": MAX_W,
            "top_quartile": f"ranks 1..{top_cutoff}",
            "bottom_quartile": f"ranks {bottom_cutoff + 1}..{n}",
            "kelly_blend": KELLY_BLEND,
            "kelly_sharpe_floor": SHARPE_FLOOR,
            "kelly_formula": "kelly_mult = 1 + beta * (sharpe_adj_i / mean_sharpe_adj - 1)",
        },
    }

    _save_weights(state)

    print(f"darwin_weights: updated {len(updates)} traders  "
          f"(kelly_blend={KELLY_BLEND} sharpe_floor={SHARPE_FLOOR})")
    for u in updates:
        arrow = "↑" if u["mult"] > 1.0 else ("↓" if u["mult"] < 1.0 else "·")
        print(f"  {arrow} {u['name']:<14} rank={u['rank']}  "
              f"{u['prior_weight']:.4f} → {u['new_weight']:.4f}  "
              f"rank×{u['rank_mult']:.2f} kelly×{u['kelly_mult']:.3f} "
              f"(sharpe={u['nba_sharpe']:.2f}, {u['zone']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
