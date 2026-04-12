#!/usr/bin/env python3
"""
guardian-cross-pollinate.py -- Nomos42 Guardian Orchestrator

The "brain" that connects all departments across all repos.
Reads karpathy outputs from every department, identifies wins (metrics that
improved), and cross-pollinates knowledge between departments.

Cross-pollination rules:
  - Evolution found better feature set -> notify Engineering to deploy
  - Betting found better strategy -> notify Trading Floor
  - Research extracted technique -> notify Engineering to implement
  - Evaluation found bias -> notify Engineering + Betting
  - Creative improved quality -> notify Dashboard
  - Political found signal -> notify Political Trading Floor
  - Infra fixed issue -> notify all affected departments

Usage:
    python3 /home/termius/mon-ipad/scripts/sync/guardian-cross-pollinate.py
    python3 /home/termius/mon-ipad/scripts/sync/guardian-cross-pollinate.py --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BRAIN = Path(__file__).resolve().parent.parent.parent
REPORT_OUTPUT = BRAIN / "data" / "departments" / "guardian-report.json"
WINS_OUTPUT = BRAIN / "data" / "departments" / "wins-latest.json"

# All department karpathy output locations across all repos
DEPARTMENT_SOURCES = {
    # mon-ipad (brain) departments
    "research": BRAIN / "data" / "departments" / "research" / "karpathy-output.json",
    "engineering": BRAIN / "data" / "departments" / "engineering" / "karpathy-output.json",
    "evolution": BRAIN / "data" / "departments" / "evolution" / "karpathy-output.json",
    "betting": BRAIN / "data" / "departments" / "betting" / "karpathy-output.json",
    "evaluation": BRAIN / "data" / "departments" / "evaluation" / "karpathy-output.json",
    "infra": BRAIN / "data" / "departments" / "infra" / "karpathy-output.json",
    "political": BRAIN / "data" / "departments" / "political" / "karpathy-output.json",
    "creative": BRAIN / "data" / "departments" / "creative" / "karpathy-output.json",
    "trading_floor": BRAIN / "data" / "departments" / "trading_floor" / "karpathy-output.json",
    # Satellite repo departments
    "nba_prediction": Path("/home/termius/nomos-nba-agent/data/departments/prediction/karpathy-output.json"),
    "political_signals": Path("/home/termius/nomos-political-alpha/data/departments/signals/karpathy-output.json"),
    "rgwa_creative": Path("/home/termius/rgwa/data/departments/creative/karpathy-output.json"),
}

# Cross-pollination routing: source_dept -> [target_depts]
POLLINATION_ROUTES = {
    "evolution": {
        "better_brier": ["engineering", "trading_floor"],
        "new_features": ["engineering"],
        "model_drift": ["infra"],
        "stagnation": ["infra"],
    },
    "research": {
        "new_technique": ["engineering", "evolution"],
        "sota_gap_closed": ["evaluation", "betting"],
        "new_paper": ["engineering"],
    },
    "engineering": {
        "feature_deployed": ["evolution", "evaluation"],
        "bug_fixed": ["evaluation", "betting"],
        "calibration_improved": ["betting", "trading_floor"],
    },
    "evaluation": {
        "bias_detected": ["engineering", "betting"],
        "calibration_crisis": ["engineering", "betting", "trading_floor"],
        "phantom_game": ["engineering"],
        "brier_improved": ["betting", "trading_floor"],
    },
    "betting": {
        "strategy_improved": ["trading_floor"],
        "strategy_eliminated": ["trading_floor"],
        "roi_improved": ["trading_floor", "evaluation"],
        "negative_roi": ["evaluation", "engineering"],
    },
    "infra": {
        "space_restarted": ["evolution"],
        "space_down": ["evolution", "engineering"],
        "cron_fixed": ["all"],
    },
    "political": {
        "brier_improved": ["political_signals", "trading_floor"],
        "new_signal": ["trading_floor"],
    },
    "creative": {
        "quality_improved": ["rgwa_creative"],
    },
    "nba_prediction": {
        "prediction_improved": ["evaluation", "betting"],
    },
    "political_signals": {
        "signal_detected": ["political", "trading_floor"],
    },
    "rgwa_creative": {
        "quality_improved": ["creative"],
    },
}

# Previous state for comparison (loaded from wins-latest.json)
TRACKED_METRICS = {
    "evolution": ["best_brier", "fleet_avg_brier", "total_generations"],
    "evaluation": ["brier", "ece", "fp_rate", "roi_pct"],
    "betting": ["bankroll", "roi_pct", "sharpe", "win_rate_pct"],
    "research": ["papers_scanned", "techniques_extracted"],
    "political": ["brier"],
    "infra": ["spaces_up", "uptime_pct"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict | None:
    """Load JSON file, return None on failure."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_json(path: Path, data: dict) -> None:
    """Save dict to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def extract_metrics(dept_name: str, data: dict) -> dict:
    """Extract key metrics from a department karpathy output."""
    if data is None:
        return {}

    metrics = {
        "department": dept_name,
        "timestamp": data.get("timestamp"),
        "iteration": data.get("iteration"),
        "status": data.get("status", "unknown"),
        "improved": data.get("improved", False),
    }

    # Department-specific metrics
    if dept_name == "evolution":
        metrics["best_brier"] = data.get("best_brier") or data.get("fleet_metrics", {}).get("best_brier")
        metrics["fleet_avg_brier"] = data.get("fleet_avg_brier") or data.get("fleet_metrics", {}).get("fleet_avg")
        metrics["best_island"] = data.get("best_island") or data.get("fleet_metrics", {}).get("best_island")
        metrics["total_generations"] = data.get("total_generations") or data.get("fleet_metrics", {}).get("total_generations")
        metrics["stagnation_detected"] = data.get("stagnation_detected", [])
        metrics["cross_pollination_candidates"] = data.get("cross_pollination_candidates", [])
        metrics["diversity_score"] = data.get("diversity_score")

    elif dept_name == "evaluation":
        raw = data.get("raw_metrics", {}).get("evaluation", data)
        metrics["brier"] = raw.get("brier")
        metrics["ece"] = raw.get("ece")
        metrics["fp_rate"] = raw.get("fp_rate")
        metrics["roi_pct"] = raw.get("roi_pct")
        metrics["bias_detected"] = raw.get("bias_detected", [])
        metrics["improvements_proposed"] = raw.get("improvements_proposed", [])

    elif dept_name == "betting":
        raw = data.get("raw_metrics", {}).get("betting", data)
        metrics["bankroll"] = raw.get("bankroll")
        metrics["roi_pct"] = raw.get("roi_pct")
        metrics["sharpe"] = raw.get("sharpe")
        metrics["win_rate_pct"] = raw.get("win_rate_pct")
        metrics["strategy_rankings"] = raw.get("strategy_rankings", [])[:5]  # top 5 only

    elif dept_name == "research":
        raw = data.get("raw_metrics", {}).get("research", data)
        metrics["papers_scanned"] = raw.get("papers_scanned")
        metrics["techniques_extracted"] = raw.get("techniques_extracted")
        metrics["sota_reference"] = raw.get("sota_reference")
        metrics["gap_to_close"] = raw.get("gap_to_close")

    elif dept_name == "infra":
        raw = data.get("raw_metrics", {}).get("infra", data)
        metrics["spaces_up"] = raw.get("spaces_up")
        metrics["spaces_total"] = raw.get("spaces_total")
        metrics["uptime_pct"] = raw.get("uptime_pct")
        metrics["restart_count"] = raw.get("restart_count")

    elif dept_name == "political":
        raw = data.get("raw_metrics", {}).get("political", data)
        metrics["brier"] = raw.get("brier")
        metrics["etf_roi"] = raw.get("etf_roi")
        metrics["signal_accuracy"] = raw.get("signal_accuracy")

    elif dept_name in ("creative", "rgwa_creative"):
        raw = data.get("raw_metrics", {}).get("creative", data)
        metrics["quality_score"] = raw.get("quality_score")
        metrics["pieces_today"] = raw.get("pieces_today")

    elif dept_name == "trading_floor":
        metrics["traders"] = data.get("traders", {})
        metrics["best_trader"] = data.get("best_trader")
        metrics["total_pnl"] = data.get("total_pnl")

    elif dept_name == "nba_prediction":
        metrics["predictions_made"] = data.get("predictions_made")
        metrics["accuracy"] = data.get("accuracy")

    elif dept_name == "political_signals":
        metrics["signals_detected"] = data.get("signals_detected")
        metrics["categories"] = data.get("categories")

    return metrics


def detect_wins(current: dict, previous: dict | None) -> list:
    """Compare current metrics against previous state to detect improvements."""
    wins = []

    if previous is None:
        # First run, mark anything with improved=True as a win
        for dept, metrics in current.items():
            if isinstance(metrics, dict) and metrics.get("improved"):
                wins.append({
                    "department": dept,
                    "type": "self_reported_improvement",
                    "description": f"{dept} reports improvement in iteration {metrics.get('iteration')}",
                    "timestamp": metrics.get("timestamp"),
                })
        return wins

    # Compare tracked metrics
    for dept, metric_keys in TRACKED_METRICS.items():
        curr = current.get(dept, {})
        prev = previous.get(dept, {})
        if not isinstance(curr, dict) or not isinstance(prev, dict):
            continue

        for key in metric_keys:
            curr_val = curr.get(key)
            prev_val = prev.get(key)
            if curr_val is None or prev_val is None:
                continue
            if not isinstance(curr_val, (int, float)) or not isinstance(prev_val, (int, float)):
                continue

            # For Brier/ECE/FP-rate, lower is better
            lower_is_better = key in ("best_brier", "fleet_avg_brier", "brier", "ece", "fp_rate")

            improved = False
            delta = curr_val - prev_val
            if lower_is_better and delta < 0:
                improved = True
            elif not lower_is_better and delta > 0:
                improved = True

            if improved:
                wins.append({
                    "department": dept,
                    "type": "metric_improvement",
                    "metric": key,
                    "previous": prev_val,
                    "current": curr_val,
                    "delta": round(delta, 6),
                    "direction": "decreased" if lower_is_better else "increased",
                    "timestamp": curr.get("timestamp"),
                })

    # Check for self-reported improvements
    for dept, metrics in current.items():
        if isinstance(metrics, dict) and metrics.get("improved"):
            if not any(w["department"] == dept for w in wins):
                wins.append({
                    "department": dept,
                    "type": "self_reported_improvement",
                    "description": f"{dept} reports improvement",
                    "timestamp": metrics.get("timestamp"),
                })

    return wins


def generate_pollination_actions(wins: list, current_metrics: dict) -> list:
    """Generate cross-pollination actions based on detected wins."""
    actions = []

    for win in wins:
        dept = win["department"]
        routes = POLLINATION_ROUTES.get(dept, {})

        # Map win type to route key
        metric = win.get("metric", "")
        win_type = win.get("type", "")

        route_key = None
        if dept == "evolution":
            if metric in ("best_brier", "fleet_avg_brier"):
                route_key = "better_brier"
            elif "feature" in str(win.get("description", "")):
                route_key = "new_features"
        elif dept == "research":
            if metric == "techniques_extracted":
                route_key = "new_technique"
            elif metric == "papers_scanned":
                route_key = "new_paper"
        elif dept == "engineering":
            if "calibration" in str(win.get("description", "")):
                route_key = "calibration_improved"
            elif "bug" in str(win.get("description", "")):
                route_key = "bug_fixed"
            else:
                route_key = "feature_deployed"
        elif dept == "evaluation":
            if metric == "brier":
                route_key = "brier_improved"
            elif metric == "ece":
                route_key = "calibration_crisis"  # ECE improving is still relevant
            elif "bias" in str(win.get("description", "")):
                route_key = "bias_detected"
        elif dept == "betting":
            if metric == "roi_pct":
                curr_roi = win.get("current", 0)
                route_key = "roi_improved" if curr_roi > 0 else "negative_roi"
            elif metric == "sharpe":
                route_key = "strategy_improved"
        elif dept == "infra":
            route_key = "space_restarted"
        elif dept == "political":
            if metric == "brier":
                route_key = "brier_improved"
            else:
                route_key = "new_signal"
        elif dept == "creative":
            route_key = "quality_improved"
        elif dept == "nba_prediction":
            route_key = "prediction_improved"
        elif dept == "political_signals":
            route_key = "signal_detected"

        if route_key and route_key in routes:
            targets = routes[route_key]
            if targets == ["all"]:
                targets = list(DEPARTMENT_SOURCES.keys())

            for target in targets:
                action_desc = _format_action(dept, target, win, route_key, current_metrics)
                actions.append({
                    "from_department": dept,
                    "to_department": target,
                    "route": route_key,
                    "win": win,
                    "action": action_desc,
                    "priority": _action_priority(route_key, win),
                    "timestamp": now_utc(),
                })

    # Add evolution cross-pollination candidates if present
    evo_data = current_metrics.get("evolution", {})
    if isinstance(evo_data, dict):
        for cand in evo_data.get("cross_pollination_candidates", []):
            actions.append({
                "from_department": "evolution",
                "to_department": "evolution",
                "route": "island_cross_pollination",
                "action": f"Seed {cand.get('target')} with {cand.get('source')} config "
                          f"(Brier gain: {cand.get('potential_gain', 0):.5f})",
                "priority": "MEDIUM",
                "source_island": cand.get("source"),
                "target_island": cand.get("target"),
                "timestamp": now_utc(),
            })

    return actions


def _format_action(source: str, target: str, win: dict, route_key: str, metrics: dict) -> str:
    """Format a human-readable action description."""
    metric = win.get("metric", "")
    delta = win.get("delta")
    curr = win.get("current")

    if route_key == "better_brier":
        return (f"Evolution achieved Brier {curr} (delta {delta:+.5f}). "
                f"Deploy winning config to {target}.")
    elif route_key == "new_technique":
        tech_count = metrics.get("research", {}).get("techniques_extracted", "?")
        return f"Research extracted {tech_count} techniques. Queue for {target} implementation."
    elif route_key == "calibration_improved":
        return f"Engineering improved calibration (ECE delta {delta}). Notify {target} to update Kelly sizing."
    elif route_key == "bias_detected":
        return f"Evaluation detected bias. Notify {target} for correction."
    elif route_key == "strategy_improved":
        return f"Betting improved {metric} to {curr}. Update {target} strategy config."
    elif route_key == "brier_improved":
        return f"{source} improved Brier to {curr}. Notify {target}."
    elif route_key == "space_restarted":
        return f"Infra restarted space. Notify {target} evolution is back online."
    elif route_key == "new_paper":
        return f"Research scanned new papers. Notify {target} for technique extraction."
    elif route_key == "prediction_improved":
        return f"NBA prediction pipeline improved. Notify {target} for evaluation."
    elif route_key == "signal_detected":
        return f"Political signals detected new data. Notify {target}."
    elif route_key == "quality_improved":
        return f"Creative quality improved. Notify {target}."
    else:
        return f"{source} win ({route_key}) -> notify {target}. Delta: {delta}"


def _action_priority(route_key: str, win: dict) -> str:
    """Determine action priority."""
    high_priority_routes = {
        "better_brier", "calibration_crisis", "bias_detected",
        "negative_roi", "space_down", "phantom_game",
    }
    medium_priority_routes = {
        "new_technique", "strategy_improved", "brier_improved",
        "feature_deployed", "calibration_improved",
    }

    if route_key in high_priority_routes:
        return "HIGH"
    elif route_key in medium_priority_routes:
        return "MEDIUM"
    else:
        return "LOW"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Nomos42 Guardian Cross-Pollination Orchestrator")
    parser.add_argument("--dry-run", action="store_true",
                        help="Analyze and report but do not write output files")
    parser.add_argument("--output", "-o", default=str(REPORT_OUTPUT),
                        help="Output report path")
    args = parser.parse_args()

    timestamp = now_utc()
    print(f"[guardian] Cross-pollination starting at {timestamp}")

    # -----------------------------------------------------------------------
    # 1. Load all department karpathy outputs
    # -----------------------------------------------------------------------
    print("[guardian] Loading department karpathy outputs...")
    raw_outputs = {}
    for dept, path in DEPARTMENT_SOURCES.items():
        data = load_json(path)
        if data is not None:
            raw_outputs[dept] = data
            print(f"  Loaded: {dept} (iteration {data.get('iteration', '?')})")
        else:
            print(f"  Missing: {dept} ({path})")

    if not raw_outputs:
        print("[guardian] WARNING: No department outputs found. Nothing to cross-pollinate.")
        report = {
            "timestamp": timestamp,
            "status": "no_data",
            "departments_loaded": 0,
            "wins": [],
            "actions": [],
        }
        if not args.dry_run:
            save_json(Path(args.output), report)
        return 0

    # -----------------------------------------------------------------------
    # 2. Extract current metrics
    # -----------------------------------------------------------------------
    print("[guardian] Extracting metrics...")
    current_metrics = {}
    for dept, data in raw_outputs.items():
        current_metrics[dept] = extract_metrics(dept, data)

    # -----------------------------------------------------------------------
    # 3. Load previous state for comparison
    # -----------------------------------------------------------------------
    print("[guardian] Loading previous wins state...")
    previous_metrics = load_json(WINS_OUTPUT)
    prev_metrics_data = None
    if previous_metrics is not None:
        prev_metrics_data = previous_metrics.get("current_metrics")

    # -----------------------------------------------------------------------
    # 4. Detect wins
    # -----------------------------------------------------------------------
    print("[guardian] Detecting wins...")
    wins = detect_wins(current_metrics, prev_metrics_data)
    print(f"  Wins detected: {len(wins)}")
    for w in wins:
        metric_str = f" ({w['metric']}: {w.get('previous')} -> {w.get('current')})" if w.get("metric") else ""
        print(f"    [{w['department']}] {w['type']}{metric_str}")

    # -----------------------------------------------------------------------
    # 5. Generate cross-pollination actions
    # -----------------------------------------------------------------------
    print("[guardian] Generating cross-pollination actions...")
    actions = generate_pollination_actions(wins, current_metrics)
    print(f"  Actions generated: {len(actions)}")
    for a in actions:
        print(f"    [{a['priority']}] {a['from_department']} -> {a['to_department']}: {a['action'][:80]}")

    # -----------------------------------------------------------------------
    # 6. Build guardian report
    # -----------------------------------------------------------------------
    # Department summaries
    dept_summaries = {}
    for dept, metrics in current_metrics.items():
        if not isinstance(metrics, dict):
            continue
        summary_parts = []
        if metrics.get("best_brier"):
            summary_parts.append(f"Brier={metrics['best_brier']}")
        if metrics.get("brier"):
            summary_parts.append(f"Brier={metrics['brier']}")
        if metrics.get("roi_pct") is not None:
            summary_parts.append(f"ROI={metrics['roi_pct']}%")
        if metrics.get("sharpe") is not None:
            summary_parts.append(f"Sharpe={metrics['sharpe']}")
        if metrics.get("papers_scanned"):
            summary_parts.append(f"{metrics['papers_scanned']} papers")
        if metrics.get("techniques_extracted"):
            summary_parts.append(f"{metrics['techniques_extracted']} techniques")
        if metrics.get("spaces_up") is not None:
            summary_parts.append(f"{metrics['spaces_up']}/{metrics.get('spaces_total', '?')} spaces UP")
        if metrics.get("quality_score") is not None:
            summary_parts.append(f"quality={metrics['quality_score']}")
        summary_parts.append(f"status={metrics.get('status', 'unknown')}")
        dept_summaries[dept] = " | ".join(summary_parts)

    report = {
        "timestamp": timestamp,
        "status": "completed",
        "departments_loaded": len(raw_outputs),
        "departments_total": len(DEPARTMENT_SOURCES),
        "dept_summaries": dept_summaries,
        "wins": wins,
        "wins_count": len(wins),
        "actions": actions,
        "actions_count": len(actions),
        "actions_by_priority": {
            "HIGH": sum(1 for a in actions if a["priority"] == "HIGH"),
            "MEDIUM": sum(1 for a in actions if a["priority"] == "MEDIUM"),
            "LOW": sum(1 for a in actions if a["priority"] == "LOW"),
        },
        "cross_pollination": {
            "routes_active": len(set(a["route"] for a in actions)),
            "departments_sending": len(set(a["from_department"] for a in actions)),
            "departments_receiving": len(set(a["to_department"] for a in actions)),
        },
        "priority_queue": sorted(
            [
                {
                    "priority": a["priority"],
                    "from": a["from_department"],
                    "to": a["to_department"],
                    "action": a["action"],
                    "route": a["route"],
                }
                for a in actions
            ],
            key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(x["priority"], 3),
        ),
    }

    # -----------------------------------------------------------------------
    # 7. Write outputs
    # -----------------------------------------------------------------------
    if args.dry_run:
        print("\n[guardian] DRY RUN -- would write:")
        print(f"  Report: {args.output}")
        print(f"  Wins:   {WINS_OUTPUT}")
        print(json.dumps(report, indent=2, default=str)[:2000])
    else:
        save_json(Path(args.output), report)
        print(f"[guardian] Report written to {args.output}")

        # Save current metrics as wins-latest for next comparison
        wins_state = {
            "timestamp": timestamp,
            "current_metrics": current_metrics,
            "wins_this_cycle": wins,
        }
        save_json(WINS_OUTPUT, wins_state)
        print(f"[guardian] Wins state written to {WINS_OUTPUT}")

    # -----------------------------------------------------------------------
    # 8. Summary
    # -----------------------------------------------------------------------
    print("")
    print("=" * 60)
    print("  GUARDIAN CROSS-POLLINATION REPORT")
    print("=" * 60)
    print(f"  Departments loaded:   {len(raw_outputs)}/{len(DEPARTMENT_SOURCES)}")
    print(f"  Wins detected:        {len(wins)}")
    print(f"  Actions generated:    {len(actions)}")
    print(f"    HIGH priority:      {report['actions_by_priority']['HIGH']}")
    print(f"    MEDIUM priority:    {report['actions_by_priority']['MEDIUM']}")
    print(f"    LOW priority:       {report['actions_by_priority']['LOW']}")
    print(f"  Routes active:        {report['cross_pollination']['routes_active']}")
    print("=" * 60)

    if report["priority_queue"]:
        print("\nPriority Queue (top 5):")
        for item in report["priority_queue"][:5]:
            print(f"  [{item['priority']}] {item['from']} -> {item['to']}")
            print(f"    {item['action'][:100]}")

    print(f"\n[guardian] Done. {len(wins)} wins, {len(actions)} actions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
