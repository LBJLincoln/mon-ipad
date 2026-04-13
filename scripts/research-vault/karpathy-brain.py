#!/usr/bin/env python3
"""
Obsidian Karpathy Brain — Mutation Proposal Engine
====================================================
Reads wiki/learnings/ articles and raw experiment data, then proposes
specific, actionable mutations for the next Karpathy loop iteration.

This is the BRAIN — it does not execute mutations, it proposes them.
The Karpathy loop skill (/karpathy-loop) or the iterate scripts execute.

Design:
  - ZERO LLM calls — pure data-driven heuristics
  - Reads structured data from wiki/learnings/ and data/karpathy/
  - Tracks proposal history to avoid repeating failed ideas
  - Outputs to data/karpathy/brain-proposals.json (consumed by loop)
  - Prints human-readable proposal to stdout

Algorithm:
  1. Load current state (config, history, fleet, calibration)
  2. Compute "regret" scores for each mutation type
  3. Rank proposals by expected improvement
  4. Exclude recently-failed proposals
  5. Output top 3 ranked proposals with reasoning

Usage:
  python3 scripts/research-vault/karpathy-brain.py              # NBA proposals
  python3 scripts/research-vault/karpathy-brain.py --domain political
  python3 scripts/research-vault/karpathy-brain.py --history     # Show proposal history
"""

import json
import sys
import math
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

ROOT = Path("/home/termius/mon-ipad")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def _load_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    entries = []
    try:
        for line in path.read_text().strip().split("\n"):
            if line.strip():
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return entries


# ══════════════════════════════════════════════════════════
# STATE LOADING
# ══════════════════════════════════════════════════════════

def load_state(domain: str) -> dict:
    """Load all relevant state for a domain."""
    karp_dir = ROOT / "data" / "karpathy"

    config = _load_json(karp_dir / f"{domain}-best-config.json")
    history = _load_json(karp_dir / f"{domain}-history.json", default=[])
    iteration_log = _load_jsonl(karp_dir / "iteration-log.jsonl")
    proposals = _load_json(karp_dir / "brain-proposals.json", default={"proposals": []})
    infra = _load_json(ROOT / "data" / "infra-status.json")
    drift = _load_json(ROOT / "data" / "monitoring" / "drift-summary.json")
    backtest = _load_json(ROOT / "data" / "nba-agent" / "full-season-backtest.json")
    lessons = _load_json(ROOT / "data" / "arena" / "lessons-learned.json")
    cpcv = _load_json(ROOT / "data" / "arena" / "cpcv-gated-strategies.json")

    # Compute derived state
    streak = 0
    for entry in reversed(history):
        if not entry.get("improved"):
            streak += 1
        else:
            break

    total_improved = sum(1 for e in history if e.get("improved"))
    improvement_rate = total_improved / len(history) if history else 0

    # Classify recent mutations
    recent_mutations = []
    for entry in history[-10:]:
        mut_str = entry.get("mutation", "")
        recent_mutations.append(_classify_mutation(mut_str))

    # Mutation hit rates
    mutation_stats = defaultdict(lambda: {"tried": 0, "improved": 0})
    for entry in history:
        mut_type = _classify_mutation(entry.get("mutation", ""))
        mutation_stats[mut_type]["tried"] += 1
        if entry.get("improved"):
            mutation_stats[mut_type]["improved"] += 1

    # Fleet briers
    fleet_briers = {}
    for name, info in infra.get("hf_spaces", {}).items():
        if "nba" in name.lower() and isinstance(info, dict):
            try:
                fleet_briers[name] = float(info.get("brier", 0))
            except (ValueError, TypeError):
                pass

    return {
        "domain": domain,
        "config": config,
        "history": history,
        "iteration_log": iteration_log,
        "past_proposals": proposals.get("proposals", []),
        "streak": streak,
        "total_iterations": len(history),
        "total_improved": total_improved,
        "improvement_rate": improvement_rate,
        "recent_mutations": recent_mutations,
        "mutation_stats": dict(mutation_stats),
        "fleet_briers": fleet_briers,
        "drift": drift,
        "backtest": backtest,
        "lessons": lessons,
        "cpcv": cpcv,
        "best_brier": config.get("best_brier", 1.0),
        "model_type": config.get("model_type", "unknown"),
        "n_features": config.get("n_features", 0),
        "n_estimators": config.get("n_estimators", 0),
        "max_depth": config.get("max_depth", 0),
        "min_samples_leaf": config.get("min_samples_leaf", 0),
        "max_features_ratio": config.get("max_features_ratio", 0),
    }


# ══════════════════════════════════════════════════════════
# PROPOSAL GENERATION
# ══════════════════════════════════════════════════════════

def score_proposals(state: dict) -> list:
    """Generate and score mutation proposals based on current state."""
    proposals = []

    streak = state["streak"]
    recent = state["recent_mutations"]
    stats = state["mutation_stats"]
    best_brier = state["best_brier"]
    model_type = state["model_type"]
    n_features = state["n_features"]
    n_estimators = state["n_estimators"]
    max_depth = state["max_depth"]
    max_features_ratio = state["max_features_ratio"]

    # ── Rule 1: If stuck (streak >= 5), force diversity move ──
    if streak >= 8:
        proposals.append({
            "mutation": "change_model",
            "score": 95,
            "detail": _suggest_model_change(state),
            "reasoning": (
                f"CRITICAL: {streak} iterations without improvement. "
                f"Current model {model_type} is at a hard local minimum. "
                f"Must switch model type entirely."
            ),
            "category": "escape_local_minimum",
        })
        proposals.append({
            "mutation": "swap_features",
            "score": 90,
            "detail": {"swap_size": 20},
            "reasoning": (
                f"Large feature swap (20) for maximum diversity. "
                f"Stuck for {streak} iterations — small mutations won't escape."
            ),
            "category": "escape_local_minimum",
        })
    elif streak >= 5:
        proposals.append({
            "mutation": "change_model",
            "score": 80,
            "detail": _suggest_model_change(state),
            "reasoning": (
                f"Stuck for {streak} iterations. "
                f"Model change is the highest-diversity move available."
            ),
            "category": "escape_local_minimum",
        })
        proposals.append({
            "mutation": "swap_features",
            "score": 75,
            "detail": {"swap_size": 15},
            "reasoning": (
                f"Medium-large feature swap (15) to explore new feature space."
            ),
            "category": "escape_local_minimum",
        })

    # ── Rule 2: Exploit what works (use best mutation types) ──
    for mut_type, s in stats.items():
        if s["tried"] < 2:
            continue
        hit_rate = s["improved"] / s["tried"]
        if hit_rate > 0:
            detail = _generate_detail(mut_type, state)
            score = int(50 + hit_rate * 40)  # 50-90 range

            # Penalize if recently tried (last 3)
            recency_penalty = 0
            if mut_type in recent[-3:]:
                recency_penalty = 15
            if mut_type in recent[-1:]:
                recency_penalty = 25

            proposals.append({
                "mutation": mut_type,
                "score": max(score - recency_penalty, 10),
                "detail": detail,
                "reasoning": (
                    f"Hit rate {hit_rate:.0%} ({s['improved']}/{s['tried']}). "
                    + ("Recently tried — deprioritized. " if recency_penalty > 0 else "")
                    + f"Detail: {json.dumps(detail)}"
                ),
                "category": "exploit_proven",
            })

    # ── Rule 3: Explore untried or under-tried mutations ──
    all_mutation_types = [
        "change_model", "change_n_estimators", "change_max_depth",
        "change_min_samples_leaf", "change_max_features_ratio",
        "add_features", "remove_features", "swap_features",
    ]
    for mut_type in all_mutation_types:
        if mut_type not in stats or stats[mut_type]["tried"] < 2:
            detail = _generate_detail(mut_type, state)
            proposals.append({
                "mutation": mut_type,
                "score": 45,  # Moderate — worth exploring
                "detail": detail,
                "reasoning": (
                    f"Under-explored mutation type (tried {stats.get(mut_type, {}).get('tried', 0)} times). "
                    f"Worth testing for signal."
                ),
                "category": "explore_unknown",
            })

    # ── Rule 4: Feature count heuristics ──
    if n_features > 150:
        proposals.append({
            "mutation": "remove_features",
            "score": 65,
            "detail": {"remove_size": 10},
            "reasoning": (
                f"Feature count {n_features} is high (>150). "
                f"Noise reduction likely to help — remove 10 weakest."
            ),
            "category": "feature_optimization",
        })
    elif n_features < 50:
        proposals.append({
            "mutation": "add_features",
            "score": 65,
            "detail": {"add_size": 10},
            "reasoning": (
                f"Feature count {n_features} is low (<50). "
                f"Adding features may capture missing signal."
            ),
            "category": "feature_optimization",
        })

    # ── Rule 5: Hyperparameter boundary suggestions ──
    if n_estimators <= 100 and model_type in ["gradient_boosting", "extra_trees"]:
        proposals.append({
            "mutation": "change_n_estimators",
            "score": 55,
            "detail": {"direction": "increase", "delta": 50},
            "reasoning": (
                f"n_estimators={n_estimators} is low for {model_type}. "
                f"More trees may reduce variance."
            ),
            "category": "hyperparam_tuning",
        })
    elif n_estimators >= 400:
        proposals.append({
            "mutation": "change_n_estimators",
            "score": 45,
            "detail": {"direction": "decrease", "delta": 50},
            "reasoning": (
                f"n_estimators={n_estimators} is high. "
                f"May be overfitting — try reducing."
            ),
            "category": "hyperparam_tuning",
        })

    if max_depth >= 20:
        proposals.append({
            "mutation": "change_max_depth",
            "score": 55,
            "detail": {"direction": "decrease", "delta": 3},
            "reasoning": (
                f"max_depth={max_depth} is deep. "
                f"Reducing may improve generalization."
            ),
            "category": "hyperparam_tuning",
        })
    elif max_depth <= 6:
        proposals.append({
            "mutation": "change_max_depth",
            "score": 55,
            "detail": {"direction": "increase", "delta": 2},
            "reasoning": (
                f"max_depth={max_depth} is shallow. "
                f"Model may be underfitting — try deeper."
            ),
            "category": "hyperparam_tuning",
        })

    # ── Rule 6: Alternation rule — avoid mutation type streaks ──
    if len(recent) >= 3:
        recent_types = set(recent[-3:])
        is_feature_heavy = all(t in {"add_features", "remove_features", "swap_features"}
                               for t in recent[-3:])
        is_hyperparam_heavy = all(t in {"change_n_estimators", "change_max_depth",
                                         "change_min_samples_leaf", "change_max_features_ratio"}
                                   for t in recent[-3:])

        if is_feature_heavy:
            # Boost hyperparameter mutations
            for p in proposals:
                if p["mutation"] in {"change_n_estimators", "change_max_depth",
                                     "change_min_samples_leaf", "change_max_features_ratio"}:
                    p["score"] += 20
                    p["reasoning"] += " [BOOSTED: last 3 were feature mutations, alternating]"
        elif is_hyperparam_heavy:
            # Boost feature mutations
            for p in proposals:
                if p["mutation"] in {"add_features", "remove_features", "swap_features"}:
                    p["score"] += 20
                    p["reasoning"] += " [BOOSTED: last 3 were hyperparam mutations, alternating]"

    # ── Rule 7: Fleet-informed proposals ──
    fleet = state["fleet_briers"]
    if fleet:
        best_fleet = min(fleet.values())
        if best_fleet < best_brier - 0.005:
            champion_island = min(fleet, key=fleet.get)
            proposals.append({
                "mutation": "seed_from_fleet",
                "score": 85,
                "detail": {
                    "source_island": champion_island,
                    "source_brier": best_fleet,
                    "current_brier": best_brier,
                },
                "reasoning": (
                    f"Fleet champion {champion_island} has Brier {best_fleet:.5f} "
                    f"which is {best_brier - best_fleet:.5f} better than current config. "
                    f"Seed from fleet champion."
                ),
                "category": "fleet_seeding",
            })

    # ── Rule 8: Calibration-driven proposals ──
    drift = state["drift"]
    if drift.get("recalibration_needed"):
        ece = drift.get("metrics", {}).get("rolling_ece", 0)
        if isinstance(ece, (int, float)) and ece > 0.05:
            proposals.append({
                "mutation": "recalibrate",
                "score": 70,
                "detail": {"rolling_ece": ece, "method": "isotonic"},
                "reasoning": (
                    f"Drift monitor says recalibration needed (ECE={ece:.5f}). "
                    f"Isotonic recalibration may reduce Brier by 0.001-0.003."
                ),
                "category": "calibration",
            })

    # ── Deduplicate and sort ──
    # Deduplicate by mutation type, keeping highest score
    best_by_type = {}
    for p in proposals:
        key = p["mutation"]
        if key not in best_by_type or p["score"] > best_by_type[key]["score"]:
            best_by_type[key] = p

    ranked = sorted(best_by_type.values(), key=lambda x: x["score"], reverse=True)

    # Filter out proposals that match recently-failed proposals
    past = state["past_proposals"]
    recently_failed = set()
    for pp in past[-5:]:
        if pp.get("outcome") == "REVERT":
            recently_failed.add(pp.get("mutation", ""))

    final = []
    for p in ranked:
        if p["mutation"] in recently_failed:
            p["score"] -= 20
            p["reasoning"] += " [PENALIZED: recently failed]"
        final.append(p)

    final.sort(key=lambda x: x["score"], reverse=True)
    return final[:5]  # Top 5


def _suggest_model_change(state: dict) -> dict:
    """Suggest which model to switch to."""
    current = state["model_type"]
    candidates = ["random_forest", "extra_trees", "gradient_boosting", "lightgbm"]
    candidates = [c for c in candidates if c != current]

    # Prefer models not recently tried
    model_history = defaultdict(list)
    for entry in state["history"]:
        mt = entry.get("model_type", "unknown")
        model_history[mt].append(entry.get("brier", 1.0))

    # Pick model with best historical Brier (or untried one)
    best_candidate = None
    best_score = 1.0
    for c in candidates:
        if c in model_history:
            avg = sum(model_history[c]) / len(model_history[c])
            if avg < best_score:
                best_score = avg
                best_candidate = c
        else:
            # Untried model gets priority
            best_candidate = c
            break

    return {
        "target_model": best_candidate or candidates[0],
        "current_model": current,
    }


def _generate_detail(mut_type: str, state: dict) -> dict:
    """Generate specific mutation details."""
    if mut_type == "change_model":
        return _suggest_model_change(state)
    elif mut_type == "change_n_estimators":
        current = state["n_estimators"]
        # Prefer direction that hasn't been tried recently
        return {"current": current, "direction": "increase" if current < 200 else "decrease",
                "delta": 50}
    elif mut_type == "change_max_depth":
        current = state["max_depth"]
        return {"current": current, "direction": "increase" if current < 15 else "decrease",
                "delta": 2}
    elif mut_type == "change_min_samples_leaf":
        current = state["min_samples_leaf"]
        return {"current": current, "direction": "decrease" if current > 5 else "increase",
                "delta": 2}
    elif mut_type == "change_max_features_ratio":
        current = state["max_features_ratio"]
        return {"current": current, "direction": "increase" if current < 0.4 else "decrease",
                "delta": 0.05}
    elif mut_type == "add_features":
        return {"add_size": 5}
    elif mut_type == "remove_features":
        return {"remove_size": 5}
    elif mut_type == "swap_features":
        swap = 10 if state["streak"] < 5 else 15
        return {"swap_size": swap}
    return {}


def _classify_mutation(mutation_str: str) -> str:
    m = mutation_str.lower()
    if "model:" in m or "model ->" in m:
        return "change_model"
    if "n_estimators" in m:
        return "change_n_estimators"
    if "max_depth" in m:
        return "change_max_depth"
    if "min_samples_leaf" in m:
        return "change_min_samples_leaf"
    if "max_features_ratio" in m:
        return "change_max_features_ratio"
    if "add" in m and "feature" in m:
        return "add_features"
    if "remove" in m and "feature" in m:
        return "remove_features"
    if "swap" in m and "feature" in m:
        return "swap_features"
    return "other"


# ══════════════════════════════════════════════════════════
# PROPOSAL PERSISTENCE
# ══════════════════════════════════════════════════════════

def save_proposals(domain: str, proposals: list, state: dict):
    """Save proposals to data/karpathy/brain-proposals.json."""
    out_path = ROOT / "data" / "karpathy" / "brain-proposals.json"

    existing = _load_json(out_path, default={"proposals": []})
    past = existing.get("proposals", [])

    # Build new entry
    entry = {
        "timestamp": _now(),
        "domain": domain,
        "state_summary": {
            "best_brier": state["best_brier"],
            "model_type": state["model_type"],
            "n_features": state["n_features"],
            "streak": state["streak"],
            "total_iterations": state["total_iterations"],
        },
        "top_proposal": proposals[0] if proposals else None,
        "all_proposals": proposals,
    }

    past.append(entry)
    # Keep last 50 proposals
    if len(past) > 50:
        past = past[-50:]

    out_data = {
        "last_updated": _now(),
        "total_proposals": len(past),
        "proposals": past,
    }

    out_path.write_text(json.dumps(out_data, indent=2, default=str))
    return out_path


def record_outcome(domain: str, mutation: str, outcome: str, brier_delta: float):
    """Record the outcome of a proposal for future learning.
    Called after a Karpathy loop completes.

    outcome: 'KEEP' or 'REVERT'
    """
    out_path = ROOT / "data" / "karpathy" / "brain-proposals.json"
    data = _load_json(out_path, default={"proposals": []})

    proposals = data.get("proposals", [])
    # Find most recent proposal matching this mutation and domain
    for p in reversed(proposals):
        if (p.get("domain") == domain and
            p.get("top_proposal", {}).get("mutation") == mutation and
            "outcome" not in p):
            p["outcome"] = outcome
            p["brier_delta"] = brier_delta
            p["outcome_recorded_at"] = _now()
            break

    data["proposals"] = proposals
    data["last_updated"] = _now()
    out_path.write_text(json.dumps(data, indent=2, default=str))


# ══════════════════════════════════════════════════════════
# OUTPUT
# ══════════════════════════════════════════════════════════

def format_proposals(proposals: list, state: dict) -> str:
    """Format proposals as human-readable output."""
    lines = [
        "=" * 60,
        f"  KARPATHY BRAIN — {state['domain'].upper()} Mutation Proposals",
        "=" * 60,
        "",
        f"  Current state:",
        f"    Best Brier:     {state['best_brier']:.6f}",
        f"    Model:          {state['model_type']}",
        f"    Features:       {state['n_features']}",
        f"    n_estimators:   {state['n_estimators']}",
        f"    max_depth:      {state['max_depth']}",
        f"    No-improve:     {state['streak']} iterations",
        f"    Total iters:    {state['total_iterations']}",
        f"    Hit rate:       {state['improvement_rate']:.1%}",
        "",
    ]

    if state["fleet_briers"]:
        best_fleet = min(state["fleet_briers"].values())
        lines.append(f"    Fleet best:     {best_fleet:.5f}")
        lines.append("")

    lines.append(f"  Target: 0.20000 | Gap: {state['best_brier'] - 0.20:.5f}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("")

    for i, p in enumerate(proposals, 1):
        lines.extend([
            f"  #{i} [{p['score']:3d} pts] {p['mutation']}",
            f"     Category: {p.get('category', 'general')}",
            f"     Detail:   {json.dumps(p.get('detail', {}), default=str)}",
            f"     Reason:   {p['reasoning'][:120]}",
            "",
        ])

    lines.append("-" * 60)

    if proposals:
        top = proposals[0]
        lines.extend([
            "",
            f"  >>> RECOMMENDED: {top['mutation']}",
            f"      {top['reasoning'][:200]}",
            "",
        ])

    lines.append("=" * 60)
    return "\n".join(lines)


def show_history():
    """Show past proposal history and outcomes."""
    data = _load_json(ROOT / "data" / "karpathy" / "brain-proposals.json",
                      default={"proposals": []})

    proposals = data.get("proposals", [])
    if not proposals:
        print("No proposal history found.")
        return

    print(f"{'Timestamp':20s} {'Domain':10s} {'Mutation':25s} {'Score':6s} {'Outcome':8s} {'Brier':10s}")
    print("-" * 85)

    for p in proposals[-20:]:
        ts = p.get("timestamp", "?")[:19]
        domain = p.get("domain", "?")
        top = p.get("top_proposal", {})
        mutation = top.get("mutation", "?")
        score = str(top.get("score", "?"))
        outcome = p.get("outcome", "pending")
        brier = p.get("state_summary", {}).get("best_brier", "?")
        if isinstance(brier, float):
            brier = f"{brier:.6f}"

        print(f"{ts:20s} {domain:10s} {mutation:25s} {score:6s} {outcome:8s} {brier:10s}")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Karpathy Brain — Mutation Proposals")
    parser.add_argument("--domain", default="nba", choices=["nba", "political"])
    parser.add_argument("--history", action="store_true", help="Show proposal history")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--record-outcome", nargs=3,
                        metavar=("MUTATION", "OUTCOME", "BRIER_DELTA"),
                        help="Record outcome: mutation KEEP/REVERT delta")
    args = parser.parse_args()

    if args.history:
        show_history()
        return

    if args.record_outcome:
        mutation, outcome, delta = args.record_outcome
        record_outcome(args.domain, mutation, outcome, float(delta))
        print(f"Recorded: {mutation} -> {outcome} (delta={delta})")
        return

    # Load state
    state = load_state(args.domain)

    # Generate proposals
    proposals = score_proposals(state)

    # Save proposals
    save_proposals(args.domain, proposals, state)

    # Output
    if args.json:
        output = {
            "timestamp": _now(),
            "domain": args.domain,
            "state": {
                "best_brier": state["best_brier"],
                "model_type": state["model_type"],
                "n_features": state["n_features"],
                "streak": state["streak"],
            },
            "proposals": proposals,
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print(format_proposals(proposals, state))


if __name__ == "__main__":
    main()
