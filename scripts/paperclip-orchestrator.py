#!/usr/bin/env python3
"""
Paperclip Orchestrator — Nomos42 Agent Swarm v3.0
==================================================
Implements the Paperclip Maximizer pattern with full HR system:
  - Each agent optimizes ONE metric relentlessly
  - Orchestrator allocates resources to agents closest to breakthrough
  - FIRE: agents with paperclip_score < 0.2 for 3+ consecutive checks
  - HIRE: replacement agents with different strategy after firing
  - PROMOTE: agents with paperclip_score > 0.9 for 3+ checks

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
import math
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
BREAKTHROUGH_THRESHOLD = 0.75   # above this = near-breakthrough
FIRE_THRESHOLD = 0.20            # below this for FIRE_CONSECUTIVE_CHECKS = fired
FIRE_CONSECUTIVE_CHECKS = 3      # how many consecutive low checks before firing
PROMOTE_THRESHOLD = 0.90         # above this for PROMOTE_CONSECUTIVE_CHECKS = promoted
PROMOTE_CONSECUTIVE_CHECKS = 3   # how many consecutive high checks before promotion
RESOURCE_BOOST_ON_BREAKTHROUGH = 1.5
RESOURCE_CUT_ON_ELIMINATION = 0.4
MAX_RESOURCES_SINGLE_AGENT = 30
MIN_RESOURCES_ACTIVE = 3

# ─── HR: Replacement blueprints ──────────────────────────────────────────────
# When an agent is fired, a replacement is proposed with different strategy.
# Key = fired agent id, value = replacement blueprint.
REPLACEMENT_BLUEPRINTS = {
    "halftime-scorer": {
        "id": "live-odds-tracker",
        "name": "live-odds-tracker",
        "title": "Live Odds Tracker",
        "department": "betting_strategy",
        "type": "market-analyst",
        "purpose": "Real-time line movement tracker — detect 2H market inefficiencies via API polling",
        "strategy": "Poll DraftKings/FanDuel 2H lines every 60s. Fire signal when line moves >1.5 pts vs model.",
        "metric_name": "live_signals_per_game_night",
        "metric_target": 3,
        "trigger": "live every 60s during games",
        "expected_improvement": "0 to 3+ live signals/night via API (no scraping needed)"
    },
    "code-optimizer": {
        "id": "feature-profiler",
        "name": "feature-profiler",
        "title": "Feature Profiler",
        "department": "engineering",
        "type": "general-purpose",
        "purpose": "Profile + cache feature build time — reduce Colab iteration from 36min to <10min",
        "strategy": "Use cProfile on engine.py categories. Add joblib.Memory cache. Target: top-3 slow cats.",
        "metric_name": "feature_build_minutes",
        "metric_target": 10,
        "trigger": "weekly + before GPU sessions",
        "expected_improvement": "4x faster GPU iterations = more TabICL experiments per session"
    },
    "test-creator": {
        "id": "mock-test-builder",
        "name": "mock-test-builder",
        "title": "Mock Test Builder",
        "department": "engineering",
        "type": "general-purpose",
        "purpose": "Build mock-based tests with zero ML deps — 90%+ coverage without sklearn/xgb on VM",
        "strategy": "unittest.mock to patch all ML imports. Test feature math, Kelly formula, Brier calc.",
        "metric_name": "test_coverage_pct",
        "metric_target": 90,
        "trigger": "on-demand",
        "expected_improvement": "65% → 90% coverage. Zero ML violations on VM."
    },
    "strategy-corrector": {
        "id": "edge-calibrator",
        "name": "edge-calibrator",
        "title": "Edge Calibrator",
        "department": "betting_strategy",
        "type": "market-analyst",
        "purpose": "Calibrate model edge thresholds using historical CLV and closing line data",
        "strategy": "Analyze 1,128-game odds dataset. Fit optimal MIN_EDGE per market via Platt scaling.",
        "metric_name": "strategies_with_positive_clv",
        "metric_target": 4,
        "trigger": "weekly + post-backtest",
        "expected_improvement": "From 0/5 to 4/5 strategies with proven CLV edge"
    },
    "data-scout": {
        "id": "api-integrator",
        "name": "api-integrator",
        "title": "API Integrator",
        "department": "research",
        "type": "research-analyst",
        "purpose": "Integrate pre-identified FREE data APIs into engine — focus on highest Brier impact",
        "strategy": "nba_api hustle/speed/drives already fetched. Wire them into Cat45+ features NOW.",
        "metric_name": "new_data_sources_integrated",
        "metric_target": 3,
        "trigger": "cron 24h",
        "expected_improvement": "10 datasets already in data/player-tracking/ — just need integration"
    }
}

# ─── HR: Promotion titles ─────────────────────────────────────────────────────
# When an agent is promoted, their title is upgraded.
PROMOTION_UPGRADES = {
    "evolution-optimizer": {
        "new_title": "Chief Evolution Officer",
        "new_role": "Leads ALL 6 island evolution strategies. Own GA roadmap to Brier < 0.20.",
        "resource_bonus": 5,
        "new_responsibilities": [
            "Coordinate island specialization (S10-S15)",
            "Approve all GA parameter changes",
            "Own Kaggle GPU session strategy",
            "Monthly Brier target reviews"
        ]
    },
    "feature-engineer": {
        "new_title": "Principal Feature Architect",
        "new_role": "Owns the full feature engine roadmap. Signs off on all new categories.",
        "resource_bonus": 4,
        "new_responsibilities": [
            "Define feature engine roadmap (Cat 46-56)",
            "Review all engine parity checks",
            "Coordinate with evolution-optimizer on feature selection",
            "Own Brier attribution analysis per feature category"
        ]
    },
    "orchestrator": {
        "new_title": "Grand Orchestrator",
        "new_role": "System-wide health + hiring decisions + strategic direction.",
        "resource_bonus": 3,
        "new_responsibilities": [
            "HR decisions: fire/hire/promote with full authority",
            "Cross-repo audit ownership",
            "Quarterly architecture reviews",
            "Budget allocation across all 7 departments"
        ]
    },
    "strategy-researcher": {
        "new_title": "Head of Quant Research",
        "new_role": "Leads deep-dive research agenda. Prioritizes techniques for GPU testing.",
        "resource_bonus": 3,
        "new_responsibilities": [
            "Annual research roadmap",
            "Venn-Abers + TabICL integration lead",
            "Academic paper pipeline (arXiv weekly review)",
            "ROI attribution for each research technique"
        ]
    }
}

# Generic promotion for unknown agents
DEFAULT_PROMOTION = {
    "new_title_suffix": " (Senior)",
    "resource_bonus": 2,
    "new_responsibilities": [
        "Mentorship of lower-performing agents in same department",
        "Extended metric targets",
        "First candidate for new strategic initiatives"
    ]
}

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


# ─── HR System ───────────────────────────────────────────────────────────────

def evaluate_fire_candidates(agents: list) -> list:
    """
    Identify agents that should be FIRED.
    Condition: paperclip_score < FIRE_THRESHOLD for FIRE_CONSECUTIVE_CHECKS consecutive checks.
    Returns list of fire decisions.
    """
    fired = []
    for agent in agents:
        if agent.get("status") == "eliminated":
            continue

        score = agent.get("paperclip_score", 0.5)
        consecutive_low = agent.get("consecutive_low_scores", 0)

        # Update consecutive low score counter
        if score < FIRE_THRESHOLD:
            consecutive_low += 1
        else:
            consecutive_low = 0

        # Write updated count back
        agent["consecutive_low_scores"] = consecutive_low

        if consecutive_low >= FIRE_CONSECUTIVE_CHECKS:
            fired.append({
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "agent_title": agent.get("title", agent["name"]),
                "department": agent["department"],
                "final_score": score,
                "consecutive_low_scores": consecutive_low,
                "fire_reason": (
                    f"paperclip_score={score:.3f} below FIRE_THRESHOLD={FIRE_THRESHOLD} "
                    f"for {consecutive_low} consecutive checks. "
                    f"Metric: {agent.get('metric_name','?')}={agent.get('metric_value','?')} "
                    f"vs target={agent.get('metric_target','?')}."
                ),
                "last_action": agent.get("last_action", "unknown"),
                "performance_trend": agent.get("performance_trend", "unknown"),
                "fired_date": now_iso()
            })

    return fired


def propose_replacements(fired_agents: list) -> list:
    """
    For each fired agent, propose a REPLACEMENT agent with a different strategy.
    """
    hires = []
    for fired in fired_agents:
        agent_id = fired["agent_id"]
        blueprint = REPLACEMENT_BLUEPRINTS.get(agent_id)

        if blueprint:
            hire = {
                **blueprint,
                "status": "active",
                "paperclip_score": 0.5,
                "resources_allocated": MIN_RESOURCES_ACTIVE + 2,
                "elimination_risk": "low",
                "consecutive_low_scores": 0,
                "consecutive_high_scores": 0,
                "promotion_eligible": False,
                "fire_risk": False,
                "hired_date": now_iso(),
                "performance_trend": "stable",
                "score_history": [0.5],
                "replacing": agent_id,
                "hired_reason": f"Replacement for fired agent '{fired['agent_title']}' — different approach"
            }
        else:
            # Generic replacement: same dept, augmented mandate
            hire = {
                "id": f"{agent_id}-v2",
                "name": f"{agent_id}-v2",
                "title": f"{fired['agent_title']} v2",
                "department": fired["department"],
                "type": "general-purpose",
                "purpose": f"Replacement for {agent_id} — redesigned mandate with clearer KPI",
                "strategy": "Single measurable KPI, 2-week probation period, daily check-ins",
                "metric_name": "kpi_hit_rate",
                "metric_target": 3,
                "trigger": "on-demand",
                "status": "active",
                "paperclip_score": 0.5,
                "resources_allocated": MIN_RESOURCES_ACTIVE + 2,
                "elimination_risk": "low",
                "consecutive_low_scores": 0,
                "consecutive_high_scores": 0,
                "promotion_eligible": False,
                "fire_risk": False,
                "hired_date": now_iso(),
                "performance_trend": "stable",
                "score_history": [0.5],
                "replacing": agent_id,
                "hired_reason": f"Replacement for fired agent '{fired['agent_title']}' — generic redesign",
                "expected_improvement": "TBD after 2-week probation"
            }

        hires.append(hire)

    return hires


def evaluate_promote_candidates(agents: list) -> list:
    """
    Identify agents that should be PROMOTED.
    Condition: paperclip_score > PROMOTE_THRESHOLD for PROMOTE_CONSECUTIVE_CHECKS consecutive checks.
    Returns list of promotion decisions.
    """
    promoted = []
    for agent in agents:
        if agent.get("status") == "eliminated":
            continue

        score = agent.get("paperclip_score", 0.0)
        consecutive_high = agent.get("consecutive_high_scores", 0)

        # Update consecutive high score counter
        if score > PROMOTE_THRESHOLD:
            consecutive_high += 1
        else:
            consecutive_high = max(0, consecutive_high - 1)  # decay on miss

        agent["consecutive_high_scores"] = consecutive_high

        if consecutive_high >= PROMOTE_CONSECUTIVE_CHECKS:
            agent_id = agent["id"]
            upgrade = PROMOTION_UPGRADES.get(agent_id, None)

            if upgrade:
                new_title = upgrade["new_title"]
                resource_bonus = upgrade["resource_bonus"]
                new_role = upgrade["new_role"]
                new_responsibilities = upgrade["new_responsibilities"]
            else:
                current_title = agent.get("title", agent["name"])
                new_title = current_title + DEFAULT_PROMOTION["new_title_suffix"]
                resource_bonus = DEFAULT_PROMOTION["resource_bonus"]
                new_role = f"Extended responsibilities as senior performer in {agent['department']}"
                new_responsibilities = DEFAULT_PROMOTION["new_responsibilities"]

            promoted.append({
                "agent_id": agent_id,
                "agent_name": agent["name"],
                "old_title": agent.get("title", agent["name"]),
                "new_title": new_title,
                "department": agent["department"],
                "current_score": score,
                "consecutive_high_scores": consecutive_high,
                "resource_bonus": resource_bonus,
                "new_role": new_role,
                "new_responsibilities": new_responsibilities,
                "promote_reason": (
                    f"paperclip_score={score:.3f} above PROMOTE_THRESHOLD={PROMOTE_THRESHOLD} "
                    f"for {consecutive_high} consecutive checks. Outstanding performance."
                ),
                "promoted_date": now_iso()
            })

            # Update agent title in health data
            agent["title"] = new_title
            agent["promotion_eligible"] = False  # reset after actual promotion
            agent["consecutive_high_scores"] = 0  # reset counter
            agent["resources_allocated"] = min(
                MAX_RESOURCES_SINGLE_AGENT,
                agent.get("resources_allocated", 10) + resource_bonus
            )

    return promoted


def apply_fire_to_agents(agents: list, fired_agents: list) -> list:
    """Mark fired agents as eliminated in the agents list."""
    fired_ids = {f["agent_id"] for f in fired_agents}
    for agent in agents:
        if agent["id"] in fired_ids:
            agent["status"] = "eliminated"
            agent["fire_risk"] = True
            agent["performance_trend"] = "terminated"
    return agents


def redistribute_fired_resources(agents: list, fired_agents: list) -> list:
    """Redistribute resources from fired agents to top performers."""
    if not fired_agents:
        return agents

    # Sum resources freed from fired agents
    freed = sum(
        next((a.get("resources_allocated", 3) for a in agents if a["id"] == f["agent_id"]), 3)
        for f in fired_agents
    )

    # Find top-3 performers (by paperclip_score, active only)
    active = [a for a in agents if a.get("status") == "active"]
    top = sorted(active, key=lambda a: a.get("paperclip_score", 0), reverse=True)[:3]

    # Distribute freed resources proportionally
    if top:
        per_agent = freed // len(top)
        remainder = freed % len(top)
        for i, agent in enumerate(top):
            bonus = per_agent + (1 if i < remainder else 0)
            agent["resources_allocated"] = min(
                MAX_RESOURCES_SINGLE_AGENT,
                agent.get("resources_allocated", 5) + bonus
            )

    return agents


def build_hr_actions(fired_agents: list, hired_agents: list, promoted_agents: list) -> list:
    """Build the unified hr_actions log."""
    actions = []
    ts = now_iso()

    for f in fired_agents:
        actions.append({
            "type": "fire",
            "agent_id": f["agent_id"],
            "agent_name": f["agent_title"],
            "department": f["department"],
            "reason": f["fire_reason"],
            "final_score": f["final_score"],
            "date": f["fired_date"]
        })

    for h in hired_agents:
        actions.append({
            "type": "hire",
            "agent_id": h["id"],
            "agent_name": h["title"],
            "department": h["department"],
            "reason": h["hired_reason"],
            "initial_score": h["paperclip_score"],
            "replacing": h.get("replacing"),
            "date": h["hired_date"]
        })

    for p in promoted_agents:
        actions.append({
            "type": "promote",
            "agent_id": p["agent_id"],
            "agent_name": p["old_title"],
            "new_title": p["new_title"],
            "department": p["department"],
            "reason": p["promote_reason"],
            "score": p["current_score"],
            "date": p["promoted_date"]
        })

    return actions


# ─── Core Logic ──────────────────────────────────────────────────────────────

def compute_breakthrough_distance(agent: dict) -> float:
    """
    Compute how close an agent is to its next breakthrough.
    Returns a score 0-1 where 1 = at breakthrough.
    """
    score = agent.get("paperclip_score", 0.5)
    status = agent.get("status", "idle")
    risk = agent.get("elimination_risk", "low")

    if status == "active":
        score *= 1.05
    elif status == "remodeling":
        score *= 0.80
    elif status == "eliminated":
        return 0.0
    elif status == "idle":
        score *= 0.90

    risk_penalty = {"low": 1.0, "medium": 0.95, "high": 0.80, "critical": 0.60}
    score *= risk_penalty.get(risk, 1.0)

    return min(score, 1.0)


def suggest_remodel(agent: dict) -> dict:
    """Generate a remodel proposal for an underperforming agent."""
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
    scored = []
    for a in agents:
        if a.get("status") == "eliminated":
            continue
        dist = compute_breakthrough_distance(a)
        scored.append((a["id"], a["name"], dist, a.get("resources_allocated", 5)))

    if not scored:
        return {}

    raw_weights = [math.exp(s * 3.0) for (_, _, s, _) in scored]
    total_weight = sum(raw_weights)
    normalized = [w / total_weight for w in raw_weights]

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
    """Generate actionable resource decisions."""
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

    summary = health_data.get("summary", {})
    fleet_best_brier = summary.get("fleet_best_brier", 0.225)
    atr_brier = summary.get("atr_brier", 0.216)
    target_brier = summary.get("target_brier", 0.200)

    brier_progress = (0.25 - fleet_best_brier) / (0.25 - target_brier)
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
    agents: list,
    hr_actions: list
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

    # Recommendation 2: HR actions needed
    fires = [a for a in hr_actions if a["type"] == "fire"]
    hires = [a for a in hr_actions if a["type"] == "hire"]
    promos = [a for a in hr_actions if a["type"] == "promote"]

    if fires:
        recs.append({
            "priority": 2,
            "recommendation": f"Process {len(fires)} FIRING(S) and {len(hires)} HIRING(S)",
            "detail": f"Fired: {', '.join(f['agent_name'] for f in fires)}. Replacements queued: {', '.join(h['agent_name'] for h in hires)}.",
            "action": "hr_execute",
            "department": "oversight"
        })
    elif promos:
        recs.append({
            "priority": 2,
            "recommendation": f"Finalize {len(promos)} PROMOTION(S)",
            "detail": f"Promote: {', '.join(p['agent_name'] + ' → ' + p['new_title'] for p in promos)}.",
            "action": "hr_execute",
            "department": "oversight"
        })
    elif elimination_risks:
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

    # Recommendation 5: Deploy Props Unders strategy
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
    parser = argparse.ArgumentParser(description="Paperclip Orchestrator — Nomos42 v3.0")
    parser.add_argument("--dry-run", action="store_true", help="Compute decisions but do not write output files")
    parser.add_argument("--verbose", action="store_true", help="Show debug allocation logs")
    args = parser.parse_args()

    log("=" * 60)
    log("PAPERCLIP ORCHESTRATOR v3.0 — Starting (HR Edition)")
    log("=" * 60)

    # 1. Load agent health data
    health_data = load_json(AGENT_HEALTH_PATH)
    if not health_data:
        log("ERROR: agent-health.json not found or empty. Aborting.")
        sys.exit(1)

    agents = health_data.get("agents", [])
    log(f"Loaded {len(agents)} agents from agent-health.json")

    # 2. ── HR SYSTEM: FIRE evaluation ─────────────────────────────────────────
    log("")
    log("── HR SYSTEM ─────────────────────────────────────────────")
    fired_agents = evaluate_fire_candidates(agents)

    if fired_agents:
        log(f"FIRED {len(fired_agents)} agent(s):")
        for f in fired_agents:
            log(f"  [FIRED] {f['agent_title']} (score={f['final_score']:.3f}, {f['consecutive_low_scores']} consecutive low checks)")
        # Mark as eliminated + redistribute resources
        agents = apply_fire_to_agents(agents, fired_agents)
        agents = redistribute_fired_resources(agents, fired_agents)
    else:
        log("FIRE: No agents to fire this cycle.")

    # 3. ── HR SYSTEM: HIRE replacements ──────────────────────────────────────
    hired_agents = propose_replacements(fired_agents)
    if hired_agents:
        log(f"HIRED {len(hired_agents)} replacement(s):")
        for h in hired_agents:
            log(f"  [HIRED] {h['title']} replacing {h.get('replacing','?')} (start score=0.5)")
    else:
        log("HIRE: No new hires this cycle.")

    # 4. ── HR SYSTEM: PROMOTE evaluation ─────────────────────────────────────
    promoted_agents = evaluate_promote_candidates(agents)
    if promoted_agents:
        log(f"PROMOTED {len(promoted_agents)} agent(s):")
        for p in promoted_agents:
            log(f"  [PROMOTED] {p['old_title']} → {p['new_title']} (score={p['current_score']:.3f})")
    else:
        log("PROMOTE: No promotions this cycle.")

    # 5. ── HR actions log ────────────────────────────────────────────────────
    hr_actions = build_hr_actions(fired_agents, hired_agents, promoted_agents)
    log(f"HR actions logged: {len(hr_actions)}")
    log("")

    # 6. Allocate resources
    allocation = allocate_resources(agents, verbose=args.verbose)
    log(f"Resource allocation computed for {len(allocation)} agents")

    # 7. Identify breakthrough candidates
    breakthrough_candidates = identify_breakthrough_candidates(agents)
    log(f"Breakthrough candidates: {len(breakthrough_candidates)}")
    for c in breakthrough_candidates[:3]:
        log(f"  -> {c['name']} (score={c['paperclip_score']:.2f})")

    # 8. Identify elimination risks
    elimination_risks = identify_elimination_risks(agents)
    log(f"Elimination risks: {len(elimination_risks)}")
    for r in elimination_risks:
        log(f"  -> {r['name']} (score={r['paperclip_score']:.2f}, risk={r['elimination_risk']})")

    # 9. Generate decisions
    decisions = generate_resource_boost_decisions(breakthrough_candidates, elimination_risks, allocation)
    log(f"Decisions generated: {len(decisions)}")

    # 10. Compute global health
    global_health = compute_global_health(agents, health_data)
    log(f"Global health: {global_health['health_score']:.4f} — {global_health['interpretation']}")

    # 11. Strategic recommendations (now HR-aware)
    strategic_recs = generate_strategic_recommendations(
        breakthrough_candidates, elimination_risks, global_health, agents, hr_actions
    )

    # 12. Build arena summary (if arena files exist)
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

    # 13. Load previous decisions to carry forward historical HR log
    prev_decisions = load_json(DECISIONS_PATH)
    prev_fired = prev_decisions.get("fired_agents", [])
    prev_hired = prev_decisions.get("hired_agents", [])
    prev_promoted = prev_decisions.get("promoted_agents", [])
    prev_hr_actions = prev_decisions.get("hr_actions", [])

    # Merge (append new ones, avoid duplicates by agent_id+date)
    all_fired = prev_fired + [
        f for f in fired_agents
        if not any(p["agent_id"] == f["agent_id"] and p["fired_date"] == f["fired_date"] for p in prev_fired)
    ]
    all_hired = prev_hired + [
        h for h in hired_agents
        if not any(p["id"] == h["id"] and p["hired_date"] == h["hired_date"] for p in prev_hired)
    ]
    all_promoted = prev_promoted + [
        p for p in promoted_agents
        if not any(x["agent_id"] == p["agent_id"] and x["promoted_date"] == p["promoted_date"] for x in prev_promoted)
    ]
    all_hr_actions = prev_hr_actions + [
        a for a in hr_actions
        if not any(x["agent_id"] == a["agent_id"] and x["date"] == a["date"] and x["type"] == a["type"] for x in prev_hr_actions)
    ]

    # 14. Build output document
    output = {
        "schema_version": "2.0",
        "timestamp": now_iso(),
        "run_mode": "dry_run" if args.dry_run else "live",
        "global_health": global_health,

        # ── HR System ──────────────────────────────────────────────────────
        "hr_summary": {
            "fired_this_cycle": len(fired_agents),
            "hired_this_cycle": len(hired_agents),
            "promoted_this_cycle": len(promoted_agents),
            "total_fired_all_time": len(all_fired),
            "total_hired_all_time": len(all_hired),
            "total_promoted_all_time": len(all_promoted),
            "fire_threshold": FIRE_THRESHOLD,
            "fire_consecutive_checks": FIRE_CONSECUTIVE_CHECKS,
            "promote_threshold": PROMOTE_THRESHOLD,
            "promote_consecutive_checks": PROMOTE_CONSECUTIVE_CHECKS
        },
        "fired_agents": all_fired,
        "hired_agents": all_hired,
        "promoted_agents": all_promoted,
        "hr_actions": all_hr_actions,

        # ── Resource Allocation ────────────────────────────────────────────
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

        # ── Performance Intel ──────────────────────────────────────────────
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
            "elimination_risk_score": ELIMINATION_RISK_SCORE,
            "fire_threshold": FIRE_THRESHOLD,
            "promote_threshold": PROMOTE_THRESHOLD
        }
    }

    # 15. Write output
    if not args.dry_run:
        save_json(DECISIONS_PATH, output)
        log(f"Decisions written to {DECISIONS_PATH}")
    else:
        log("[DRY RUN] Output not written to disk.")
        if args.verbose:
            print(json.dumps(output, indent=2))

    # 16. Print summary
    log("=" * 60)
    log("PAPERCLIP ORCHESTRATOR v3.0 — Summary")
    log("=" * 60)
    log(f"Health Score:        {global_health['health_score']:.4f} ({global_health['interpretation']})")
    log(f"Fleet Best Brier:    {global_health['fleet_best_brier']:.5f} (target: {global_health['target_brier']:.5f})")
    log(f"Brier Progress:      {global_health['brier_progress_pct']:.1f}% of the way to target")
    log(f"Breakthrough Agents: {len(breakthrough_candidates)} ready")
    log(f"At-Risk Agents:      {len(elimination_risks)} need remodeling")
    log(f"Decisions Issued:    {len(decisions)}")
    log("")
    log("── HR Actions This Cycle ─────────────────────────────────")
    log(f"  FIRED:    {len(fired_agents)}")
    log(f"  HIRED:    {len(hired_agents)}")
    log(f"  PROMOTED: {len(promoted_agents)}")
    for action in hr_actions:
        emoji_map = {"fire": "[FIRE]", "hire": "[HIRE]", "promote": "[PROMO]"}
        tag = emoji_map.get(action["type"], "[HR]")
        log(f"  {tag} {action['agent_name']} — {action['reason'][:80]}")
    log("")
    log("Top Strategic Recommendations:")
    for r in strategic_recs:
        log(f"  [{r['priority']}] {r['recommendation']}")
    log("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
