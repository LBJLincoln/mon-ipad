#!/usr/bin/env python3
"""
FEEDBACK LOOP — Scientific Experiment → Agent Registry
======================================================
After each scientific-experiment.py run, push the optimal_thresholds + best
strategies into data/arena/agent-states-v5.json so the 217-agent swarm
adapts its min_edge / kelly_fraction / min_confidence to whatever is currently
optimal on the full season.

This is the Bayesian-style scientific feedback loop that makes the swarm
self-tune instead of using static defaults.

Usage:
  python3 scripts/arena/feedback-loop-from-experiment.py
"""

import json
import glob
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXPERIMENTS_DIR = ROOT / "data" / "experiments"
AGENT_STATE = ROOT / "data" / "arena" / "agent-states-v5.json"


def _name_of(obj):
    """sa.best_by_sharpe may be a dict or a list (top-N). Return a printable name."""
    if isinstance(obj, dict):
        return obj.get("name") or obj.get("strategy")
    if isinstance(obj, list) and obj:
        first = obj[0]
        if isinstance(first, dict):
            return first.get("name") or first.get("strategy")
        return str(first)
    return None


def latest_nba_experiment():
    files = sorted(glob.glob(str(EXPERIMENTS_DIR / "nba-experiment-*.json")))
    if not files:
        return None
    with open(files[-1]) as f:
        return json.load(f)


def main():
    exp = latest_nba_experiment()
    if not exp:
        print("[feedback] No experiment file — abort")
        return
    if not AGENT_STATE.exists():
        print("[feedback] No agent state — abort")
        return

    opt = exp.get("optimal_thresholds", {}).get("optimal_config", {})
    sa = exp.get("strategy_analysis", {})
    cat_analysis = exp.get("category_analysis", {})

    if not opt:
        print("[feedback] No optimal_config in experiment — abort")
        return

    min_conf = float(opt.get("min_confidence", 0.5))
    min_edge = float(opt.get("min_edge_pct", 0.0)) / 100.0
    kelly_frac = float(opt.get("kelly_fraction", 0.25))

    state = json.loads(AGENT_STATE.read_text())
    agents = state.get("agents", {})

    # Profitable + avoid categories from the experiment recommendations
    profitable_cats = set()
    avoid_cats = set()
    for k, v in cat_analysis.items() if isinstance(cat_analysis, dict) else []:
        if isinstance(v, dict):
            roi = v.get("roi", 0)
            if roi > 0.05:
                profitable_cats.add(k)
            elif roi < -0.05:
                avoid_cats.add(k)

    deactivated = 0
    activated = 0
    tuned = 0

    for aid, ag in agents.items():
        # Tune min_edge / kelly per agent
        old_edge = ag.get("min_edge", 0.02)
        old_kelly = ag.get("kelly_fraction", 0.5)
        ag["min_edge"] = min_edge
        ag["min_confidence"] = min_conf
        ag["kelly_fraction"] = kelly_frac
        if (abs(old_edge - min_edge) > 0.005 or abs(old_kelly - kelly_frac) > 0.05):
            tuned += 1

        # Disable specialists pointing at "avoid" categories
        cat = ag.get("focus_category")
        if not cat and aid.startswith("t3_"):
            core = aid[len("t3_"):]
            for suffix in ("_s0", "_s1"):
                if core.endswith(suffix):
                    cat = core[: -len(suffix)]
                    break
        if cat:
            if cat in avoid_cats and ag.get("active", True):
                ag["active"] = False
                deactivated += 1
            elif cat in profitable_cats and not ag.get("active", True):
                ag["active"] = True
                activated += 1

    state["last_feedback_sync"] = datetime.now(timezone.utc).isoformat()
    state["feedback_source"] = {
        "experiment_timestamp": exp.get("timestamp"),
        "optimal_min_confidence": min_conf,
        "optimal_min_edge_pct": min_edge * 100,
        "optimal_kelly_fraction": kelly_frac,
        "test_roi": opt.get("test_roi"),
        "test_sharpe": opt.get("test_sharpe"),
        "test_bankroll": opt.get("test_bankroll"),
        "best_by_sharpe": _name_of(sa.get("best_by_sharpe")) if sa else None,
        "profitable_categories": sorted(profitable_cats),
        "avoid_categories": sorted(avoid_cats),
    }
    AGENT_STATE.write_text(json.dumps(state, indent=2))

    print(f"[feedback] Tuned {tuned} agents (min_edge={min_edge*100:.1f}% kelly={kelly_frac})")
    print(f"[feedback] Deactivated {deactivated} (avoid cats), activated {activated} (profitable cats)")
    print(f"[feedback] Source experiment: {exp.get('timestamp')}")


if __name__ == "__main__":
    main()
