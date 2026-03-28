#!/usr/bin/env python3
"""
Paperclip Orchestrator — Nomos42 Agent Swarm v2.0
==================================================
Implements the Paperclip Maximizer pattern:
  - Each agent optimizes ONE metric relentlessly
  - Orchestrator allocates resources to agents closest to breakthrough
  - Underperforming agents get remodeled or eliminated

Usage:
  python3 scripts/paperclip-orchestrator.py
  python3 scripts/paperclip-orchestrator.py --dry-run
  python3 scripts/paperclip-orchestrator.py --verbose

Output:
  data/paperclip-decisions.json

Author: Nomos42 Brain
Updated: 2026-03-28
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path("/home/termius/mon-ipad")
AGENT_HEALTH_PATH = BASE_DIR / "data" / "agent-health.json"
DECISIONS_PATH = BASE_DIR / "data" / "paperclip-decisions.json"
ARENA_LIVE_PATH = BASE_DIR / "data" / "arena" / "arena-live.json"
ARENA_RESULTS_PATH = BASE_DIR / "data" / "arena" / "arena-results.json"
LOG_PATH = BASE_DIR / "logs" / "paperclip-orchestrator.log"

# ─── Thresholds ──────────────────────────────────────────────────────────────
ELIMINATION_RISK_SCORE = 0.25    # paperclip_score below this = critical
REMODEL_THRESHOLD = 0.35         # below this = remodel proposal
BREAKTHROUGH_THRESHOLD = 0.75    # above this = near-breakthrough
RESOURCE_BOOST_ON_BREAKTHROUGH = 1.5   # multiply resources for near-breakthrough agents
RESOURCE_CUT_ON_ELIMINATION = 0.4     # multiply resources for elimination-risk agents
MAX_RESOURCES_SINGLE_AGENT = 30       # hard cap per agent
MIN_RESOURCES_ACTIVE = 3              # floor for active agents

# ─── Helpers ─────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=indent)


def log(msg: str, verbose: bool = False) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    if verbose or not msg.startswith("[DEBUG]"):
        print(line)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


# ─── Core Logic ──────────────────────────────────────────────────────────────

def compute_breakthrough_distance(agent: dict) -> float:
    """
    Compute how close an agent is to its next breakthrough.
    Returns a score 0-1 where 1 = at breakthrough.
    Based on paperclip_score, status, elimination_risk.
    """
    score = agent.get("paperclip_score", 0.5)
    status = agent.get("status", "idle")
    risk = agent.get("elimination_risk", "low")

    # Active agents get a small boost
    if status == "active":
        score *= 1.05
    elif status == "remodeling":
        score *= 0.80
    elif status == "eliminated":
        return 0.0
    elif status == "idle":
        score *= 0.90

    # Penalize high elimination risk
    risk_penalty = {"low": 1.0, "medium": 0.95, "high": 0.80, "critical": 0.60}
    score *= risk_penalty.get(risk, 1.0)

    return min(score, 1.0)


def suggest_remodel(agent: dict) -> dict:
    """
    Generate a remodel proposal for an underperforming agent.
    """
    name = agent["name"]
    dept = agent["department"]
    score = agent.get("paperclip_score", 0.0)
    risk = agent.get("elimination_risk", "low")

    remodel_templates = {
        "halftime-scorer": {
            "action": "integrate_live_odds_api",
            "changes": [
                "Connect DraftKings live API for 2H line feed",
                "Set entry condition: score_diff < 10 at halftime",
                "Add momentum features from 1H box score",
                "Test on 50 historical halftimes before going live"
            ],
            "expected_improvement": "0 to 15+ live bets/week",
            "priority": "HIGH"
        },
        "strategy-corrector": {
            "action": "run_v4_kaggle_backtest",
            "changes": [
                "Run full v4 season confrontation on Kaggle GPU",
                "MIN_EDGE=0.005 (down from 0.03), MAX_EXPO=100%",
                "Enable compound interest mode",
                "Auto-apply corrections if Sharpe improves by >0.2"
            ],
            "expected_improvement": "From 2/5 to 4/5 strategies fixed",
            "priority": "MEDIUM"
        },
        "test-creator": {
            "action": "move_engine_tests_to_hf_ci",
            "changes": [
                "Create HF Space CI hook that runs tests on deploy",
                "Remove sklearn/lgbm/xgb dependency from VM tests",
                "Add mock-based unit tests for feature categories",
                "Target coverage 90% with mocks for ML deps"
            ],
            "expected_improvement": "65% to 85% coverage (no VM ML violations)",
            "priority": "MEDIUM"
        },
        "data-scout": {
            "action": "add_real_time_injury_feed",
            "changes": [
                "Wire ESPN injury API (free, no auth required)",
                "Add referee tendency data (NBA stats API)",
                "Implement weather API for outdoor venues (none in NBA, skip)",
                "Daily 09:00 UTC injury status refresh"
            ],
            "expected_improvement": "10 to 18 datasets, estimated -0.003 Brier",
            "priority": "LOW"
        },
        "code-optimizer": {
            "action": "profile_feature_build_time",
            "changes": [
                "Profile feature engine: identify top-3 slow categories",
                "Add joblib.Memory caching for expensive features",
                "Reduce feature_build time from 36min to <10min on Colab",
                "Document category build times in engine.py"
            ],
            "expected_improvement": "4x faster Colab iterations = more TabICL experiments",
            "priority": "LOW"
        }
    }

    template = remodel_templates.get(name)
    if template:
        return {
            "type": "remodel",
            "agent_id": agent["id"],
            "agent_name": name,
            "department": dept,
            "current_score": score,
            "risk": risk,
            **template
        }

    # Generic remodel for unknown agents
    return {
        "type": "remodel",
        "agent_id": agent["id"],
        "agent_name": name,
        "department": dept,
        "current_score": score,
        "risk": risk,
        "action": "reset_and_reconfigure",
        "changes": [
            f"Review {name} metric definition — may be tracking wrong KPI",
            "Assign clearer single metric to optimize",
            "Set 2-week trial period with clear elimination threshold"
        ],
        "expected_improvement": "TBD",
        "priority": "LOW"
    }


def allocate_resources(agents: list, verbose: bool = False) -> dict:
    """
    Paperclip allocation: more resources to agents closest to breakthrough.
    Returns {agent_id: resources_allocated (0-100)}.
    """
    # Calculate breakthrough distance for each agent
    scored = []
    for a in agents:
        if a.get("status") == "eliminated":
            continue
        dist = compute_breakthrough_distance(a)
        scored.append((a["id"], a["name"], dist, a.get("resources_allocated", 5)))

    if not scored:
        return {}

    # Compute raw weights (softmax-like, emphasize top performers)
    import math
    raw_weights = [math.exp(s * 3.0) for (_, _, s, _) in scored]
    total_weight = sum(raw_weights)
    normalized = [w / total_weight for w in raw_weights]

    # Total budget = 100 units
    total_budget = 100
    allocation = {}
    for i, (agent_id, agent_name, dist, _) in enumerate(scored):
        raw = normalized[i] * total_budget
        clamped = max(MIN_RESOURCES_ACTIVE, min(MAX_RESOURCES_SINGLE_AGENT, round(raw)))
        allocation[agent_id] = clamped
        if verbose:
            log(f"[DEBUG] Agent {agent_id} ({agent_name}): score={dist:.3f} weight={normalized[i]:.3f} → {clamped}%")

    return allocation


def identify_breakthrough_candidates(agents: list) -> list:
    """Agents with paperclip_score >= BREAKTHROUGH_THRESHOLD."""
    candidates = []
    for a in agents:
        score = a.get("paperclip_score", 0.0)
        if score >= BREAKTHROUGH_THRESHOLD and a.get("status") != "eliminated":
            candidates.append({
                "agent_id": a["id"],
                "name": a["name"],
                "department": a["department"],
                "paperclip_score": score,
                "metric_name": a.get("metric_name"),
                "metric_value": a.get("metric_value"),
                "metric_target": a.get("metric_target"),
                "next_action": a.get("last_action", "unknown"),
                "resources_to_allocate": min(
                    MAX_RESOURCES_SINGLE_AGENT,
                    round(a.get("resources_allocated", 10) * RESOURCE_BOOST_ON_BREAKTHROUGH)
                )
            })
    return sorted(candidates, key=lambda x: x["paperclip_score"], reverse=True)


def identify_elimination_risks(agents: list) -> list:
    """Agents with high/critical elimination risk or score below threshold."""
    at_risk = []
    for a in agents:
        if a.get("status") == "eliminated":
            continue
        score = a.get("paperclip_score", 0.5)
        risk = a.get("elimination_risk", "low")
        if risk in ("high", "critical") or score < REMODEL_THRESHOLD:
            at_risk.append({
                "agent_id": a["id"],
                "name": a["name"],
                "department": a["department"],
                "paperclip_score": score,
                "elimination_risk": risk,
                "status": a.get("status"),
                "reason": _elimination_reason(a),
                "remodel": suggest_remodel(a)
            })
    return sorted(at_risk, key=lambda x: x["paperclip_score"])


def _elimination_reason(agent: dict) -> str:
    name = agent.get("name", "")
    score = agent.get("paperclip_score", 0.0)
    risk = agent.get("elimination_risk", "low")
    metric_value = agent.get("metric_value", "N/A")
    metric_target = agent.get("metric_target", "N/A")
    status = agent.get("status", "unknown")

    if status == "remodeling":
        return f"Currently remodeling. Score={score:.2f} below threshold {REMODEL_THRESHOLD}."
    if risk == "high":
        return f"High elimination risk. Metric: {metric_value}/{metric_target}. Score={score:.2f}."
    if score < ELIMINATION_RISK_SCORE:
        return f"Critically low paperclip score {score:.2f} < {ELIMINATION_RISK_SCORE}."
    return f"Below remodel threshold. Score={score:.2f} < {REMODEL_THRESHOLD}."


def generate_resource_boost_decisions(breakthrough_candidates: list, elimination_risks: list, allocation: dict) -> list:
    """
    Generate actionable resource decisions.
    """
    decisions = []

    for agent in breakthrough_candidates[:3]:
        decisions.append({
            "type": "resource_boost",
            "agent_id": agent["agent_id"],
            "agent_name": agent["name"],
            "current_resources": allocation.get(agent["agent_id"], 10),
            "target_resources": agent["resources_to_allocate"],
            "reason": f"Near breakthrough: paperclip_score={agent['paperclip_score']:.2f}",
            "expected_impact": f"Push {agent['metric_name']} to target",
            "priority": "HIGH"
        })

    for risk in elimination_risks:
        remodel = risk["remodel"]
        decisions.append({
            "type": "remodel_or_eliminate",
            "agent_id": risk["agent_id"],
            "agent_name": risk["name"],
            "current_resources": allocation.get(risk["agent_id"], 5),
            "target_resources": max(
                MIN_RESOURCES_ACTIVE,
                round(allocation.get(risk["agent_id"], 5) * RESOURCE_CUT_ON_ELIMINATION)
            ),
            "reason": risk["reason"],
            "remodel_proposal": remodel,
            "priority": remodel.get("priority", "MEDIUM")
        })

    return decisions


def compute_global_health(agents: list, health_data: dict) -> dict:
    """Compute a single system health score from agent states."""
    active = sum(1 for a in agents if a.get("status") == "active")
    total = len(agents)
    avg_paperclip = sum(a.get("paperclip_score", 0.0) for a in agents) / max(total, 1)
    eliminated = sum(1 for a in agents if a.get("status") == "eliminated")

    # Pull fleet brier from summary
    fleet_best_brier = health_data.get("summary", {}).get("fleet_best_brier", 0.225)
    atr_brier = health_data.get("summary", {}).get("atr_brier", 0.216)
    target_brier = health_data.get("summary", {}).get("target_brier", 0.200)

    brier_progress = (0.25 - fleet_best_brier) / (0.25 - target_brier)  # 0 = stuck, 1 = at target
    brier_progress = max(0.0, min(1.0, brier_progress))

    health_score = (
        0.35 * (active / max(total, 1)) +
        0.30 * avg_paperclip +
        0.25 * brier_progress +
        0.10 * (1.0 - eliminated / max(total, 1))
    )

    return {
        "health_score": round(health_score, 4),
        "active_agents": active,
        "total_agents": total,
        "avg_paperclip_score": round(avg_paperclip, 4),
        "eliminated_agents": eliminated,
        "fleet_best_brier": fleet_best_brier,
        "atr_brier": atr_brier,
        "target_brier": target_brier,
        "brier_progress_pct": round(brier_progress * 100, 1),
        "interpretation": _interpret_health(health_score)
    }


def _interpret_health(score: float) -> str:
    if score >= 0.90:
        return "EXCELLENT — near all targets, no blockers"
    elif score >= 0.75:
        return "GOOD — most agents performing, minor issues"
    elif score >= 0.60:
        return "FAIR — several agents below target, remodeling needed"
    elif score >= 0.45:
        return "POOR — significant underperformance, urgent intervention"
    else:
        return "CRITICAL — system health degraded, immediate action required"


def generate_strategic_recommendations(
    breakthrough_candidates: list,
    elimination_risks: list,
    global_health: dict,
    agents: list
) -> list:
    """Top 5 strategic recommendations for the orchestrator."""
    recs = []

    # Recommendation 1: Top breakthrough push
    if breakthrough_candidates:
        top = breakthrough_candidates[0]
        recs.append({
            "priority": 1,
            "recommendation": f"Push {top['name']} to breakthrough",
            "detail": f"paperclip_score={top['paperclip_score']:.2f}. Metric: {top['metric_name']}={top['metric_value']} → target {top['metric_target']}.",
            "action": "increase_resources",
            "department": top["department"]
        })

    # Recommendation 2: Elimination risk handling
    if elimination_risks:
        worst = elimination_risks[0]
        recs.append({
            "priority": 2,
            "recommendation": f"Remodel {worst['name']} immediately",
            "detail": worst["reason"],
            "action": "remodel",
            "department": worst["department"]
        })

    # Recommendation 3: Brier gap
    brier_gap = global_health.get("fleet_best_brier", 0.220) - global_health.get("target_brier", 0.200)
    if brier_gap > 0.015:
        recs.append({
            "priority": 3,
            "recommendation": "Activate GPU evolution session (Kaggle/Colab)",
            "detail": f"Brier gap to target = {brier_gap:.4f}. Need GPU TabICL evolution. Current best: {global_health['fleet_best_brier']:.5f}.",
            "action": "launch_kaggle_session",
            "department": "evolution"
        })

    # Recommendation 4: Apply mutation cap to S13/S14
    recs.append({
        "priority": 4,
        "recommendation": "Apply mutation cap 0.15 to S13 (CatBoost) and S14 (LightGBM)",
        "detail": "S13 has 14 stagnation cycles. S13/S14 still on old 0.25 cap. Mutation data: 0.10-0.15 = 80% improvement rate vs 18% at >=0.20.",
        "action": "update_hf_space_config",
        "department": "evolution"
    })

    # Recommendation 5: Deploy Props Unders strategy to arena
    recs.append({
        "priority": 5,
        "recommendation": "Add Player Props Unders strategy to arena (estimated 4-8% edge)",
        "detail": "Multi-market research identified Props Unders as top undeployed edge. Build backtest for 2025-26 season before adding to arena.",
        "action": "build_and_test_strategy",
        "department": "betting_strategy"
    })

    return recs[:5]


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Paperclip Orchestrator — Nomos42")
    parser.add_argument("--dry-run", action="store_true", help="Compute decisions but do not write output files")
    parser.add_argument("--verbose", action="store_true", help="Show debug allocation logs")
    args = parser.parse_args()

    log("=" * 60)
    log("PAPERCLIP ORCHESTRATOR — Starting")
    log("=" * 60)

    # 1. Load agent health data
    health_data = load_json(AGENT_HEALTH_PATH)
    if not health_data:
        log("ERROR: agent-health.json not found or empty. Aborting.")
        sys.exit(1)

    agents = health_data.get("agents", [])
    log(f"Loaded {len(agents)} agents from agent-health.json")

    # 2. Allocate resources
    allocation = allocate_resources(agents, verbose=args.verbose)
    log(f"Resource allocation computed for {len(allocation)} agents")

    # 3. Identify breakthrough candidates
    breakthrough_candidates = identify_breakthrough_candidates(agents)
    log(f"Breakthrough candidates: {len(breakthrough_candidates)}")
    for c in breakthrough_candidates[:3]:
        log(f"  -> {c['name']} (score={c['paperclip_score']:.2f})")

    # 4. Identify elimination risks
    elimination_risks = identify_elimination_risks(agents)
    log(f"Elimination risks: {len(elimination_risks)}")
    for r in elimination_risks:
        log(f"  -> {r['name']} (score={r['paperclip_score']:.2f}, risk={r['elimination_risk']})")

    # 5. Generate decisions
    decisions = generate_resource_boost_decisions(breakthrough_candidates, elimination_risks, allocation)
    log(f"Decisions generated: {len(decisions)}")

    # 6. Compute global health
    global_health = compute_global_health(agents, health_data)
    log(f"Global health: {global_health['health_score']:.4f} — {global_health['interpretation']}")

    # 7. Strategic recommendations
    strategic_recs = generate_strategic_recommendations(
        breakthrough_candidates, elimination_risks, global_health, agents
    )

    # 8. Build arena summary (if arena files exist)
    arena_live = load_json(ARENA_LIVE_PATH)
    arena_summary = {}
    if arena_live:
        arena_summary = {
            "active_strategies": arena_live.get("active_count", 0),
            "eliminated_strategies": arena_live.get("eliminated_count", 0),
            "best_strategy": arena_live.get("best_strategy", {}).get("recommended_production", {}),
            "worst_strategy": arena_live.get("worst_strategy", {}),
            "total_bets": arena_live.get("total_bets", 0),
            "total_profit": arena_live.get("total_profit", 0.0)
        }

    # 9. Build output document
    output = {
        "schema_version": "1.0",
        "timestamp": now_iso(),
        "run_mode": "dry_run" if args.dry_run else "live",
        "global_health": global_health,
        "resource_allocation": {
            "method": "paperclip_softmax",
            "description": "Resources proportional to exp(paperclip_score * 3). Top agents get exponentially more compute.",
            "total_budget": 100,
            "allocations": [
                {
                    "agent_id": agent_id,
                    "agent_name": next((a["name"] for a in agents if a["id"] == agent_id), "unknown"),
                    "department": next((a["department"] for a in agents if a["id"] == agent_id), "unknown"),
                    "resources": resources,
                    "paperclip_score": next((a.get("paperclip_score", 0) for a in agents if a["id"] == agent_id), 0)
                }
                for agent_id, resources in sorted(allocation.items(), key=lambda x: -x[1])
            ]
        },
        "breakthrough_candidates": breakthrough_candidates,
        "elimination_risks": [
            {k: v for k, v in r.items() if k != "remodel"} for r in elimination_risks
        ],
        "remodel_proposals": [r["remodel"] for r in elimination_risks],
        "decisions": decisions,
        "strategic_recommendations": strategic_recs,
        "arena_summary": arena_summary,
        "next_run": "Cron: runs on-demand or via agent-cron.sh every 4h",
        "meta": {
            "agents_analyzed": len(agents),
            "active_agents": global_health["active_agents"],
            "eliminated_agents": global_health["eliminated_agents"],
            "breakthrough_threshold": BREAKTHROUGH_THRESHOLD,
            "remodel_threshold": REMODEL_THRESHOLD,
            "elimination_risk_score": ELIMINATION_RISK_SCORE
        }
    }

    # 10. Write output
    if not args.dry_run:
        save_json(DECISIONS_PATH, output)
        log(f"Decisions written to {DECISIONS_PATH}")
    else:
        log("[DRY RUN] Output not written to disk.")
        if args.verbose:
            print(json.dumps(output, indent=2))

    # 11. Print summary
    log("=" * 60)
    log("PAPERCLIP ORCHESTRATOR — Summary")
    log("=" * 60)
    log(f"Health Score:        {global_health['health_score']:.4f} ({global_health['interpretation']})")
    log(f"Fleet Best Brier:    {global_health['fleet_best_brier']:.5f} (target: {global_health['target_brier']:.5f})")
    log(f"Brier Progress:      {global_health['brier_progress_pct']:.1f}% of the way to target")
    log(f"Breakthrough Agents: {len(breakthrough_candidates)} ready")
    log(f"At-Risk Agents:      {len(elimination_risks)} need remodeling")
    log(f"Decisions Issued:    {len(decisions)}")
    log("")
    log("Top Strategic Recommendations:")
    for r in strategic_recs:
        log(f"  [{r['priority']}] {r['recommendation']}")
    log("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
