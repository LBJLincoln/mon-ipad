#!/usr/bin/env python3
"""Post-experiment council analyzer for Trading Floor v3 (day-bucket).

Reads /api/day-decisions from HF Space, computes per-agent calibration and
rationale-pattern correlation with wins. Writes to:
  data/departments/council-evaluation-latest.json (D6)
  data/departments/council-evolution-latest.json   (D3)

Usage:
  python3 scripts/councils/analyze-trading-floor.py
  python3 scripts/councils/analyze-trading-floor.py --since 2025-11-01
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import urllib.request
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

HF_BASE = "https://lbjlincoln26-nba-llm-trading-floor.hf.space"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEPT_DIR = REPO_ROOT / "data" / "departments"
ACTUATOR_STATE_PATH = DEPT_DIR / "tf-actuator-state.json"
ACTUATOR_LOG_PATH = DEPT_DIR / "tf-actuator-log.jsonl"

TRADER_DEFAULT_RISK = {
    "qwen-quant": 0.55, "qwen-arb": 0.65, "llama-contra": 0.55,
    "gemini-anl": 0.55, "gemini-tact": 0.60,
    "mistral-large": 0.50, "mistral-medium": 0.45, "mistral-small": 0.35,
    "mistral-nemo": 0.70, "mistral-ministral": 0.35,
}


def fetch(path: str, timeout: float = 30.0):
    req = urllib.request.Request(f"{HF_BASE}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def post_mutate(agent_id: str, risk_tolerance: float, timeout: float = 15.0) -> dict:
    body = json.dumps({"agent": agent_id, "risk_tolerance": risk_tolerance}).encode()
    req = urllib.request.Request(
        f"{HF_BASE}/api/mutate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def load_actuator_state() -> dict:
    if ACTUATOR_STATE_PATH.exists():
        try:
            return json.loads(ACTUATOR_STATE_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_actuator_state(state: dict):
    DEPT_DIR.mkdir(parents=True, exist_ok=True)
    ACTUATOR_STATE_PATH.write_text(json.dumps(state, indent=2))


def analyze(since: str | None = None) -> dict:
    status = fetch("/api/status")
    agents = status.get("agents", {})
    if not agents:
        return {"error": "no agent data", "status": status}

    # Pull every agent's full log
    per_agent_days = {}
    for tid in agents:
        try:
            r = fetch(f"/api/day-decisions?agent={tid}&limit=500")
            per_agent_days[tid] = r.get("days", [])
        except Exception as e:
            per_agent_days[tid] = []
            print(f"[warn] fetch {tid} failed: {e}", file=sys.stderr)

    # Per-agent calibration + rationale patterns
    per_agent_metrics = {}
    rationale_keywords = Counter()
    winning_keywords = Counter()

    for tid, days in per_agent_days.items():
        if since:
            days = [d for d in days if d.get("date", "") >= since]
        if not days:
            continue
        all_allocs = []
        bankroll_series = []
        for d in days:
            all_allocs.extend(d.get("allocations", []))
            bankroll_series.append(d.get("bankroll_after", 100))
        total_allocs = len(all_allocs)
        if total_allocs == 0:
            per_agent_metrics[tid] = {
                "trader_id": tid,
                "days_traded": len(days),
                "total_allocations": 0,
                "all_cash_days": sum(1 for d in days if d.get("cash_held_pct", 1) > 0.99),
                "final_bankroll": bankroll_series[-1] if bankroll_series else 100,
            }
            continue

        # Calibration: avg confidence vs actual win rate
        confs = [a["confidence"] for a in all_allocs]
        wins = [1 if a["won"] else 0 for a in all_allocs]
        avg_conf = sum(confs) / len(confs) if confs else 0
        win_rate = sum(wins) / len(wins) if wins else 0
        calibration_gap = avg_conf - win_rate  # positive = overconfident

        # Edge realization: avg declared edge vs realized EV
        edges = [a["edge"] for a in all_allocs]
        realized_ev = sum(a["profit"] / max(0.01, a["stake"]) for a in all_allocs) / len(all_allocs)
        avg_edge = sum(edges) / len(edges)

        # Rationale text mining
        for a in all_allocs:
            rat = (a.get("rationale") or "").lower()
            # Extract keyword tokens
            for word in ["rest", "back-to-back", "altitude", "travel", "form", "offrtg", "defrtg",
                         "net rating", "pace", "star", "injury", "home court", "rebound", "shooting",
                         "3pt", "pace", "public", "sharp", "line", "model", "consensus", "edge"]:
                if word in rat:
                    rationale_keywords[word] += 1
                    if a["won"]:
                        winning_keywords[word] += 1

        per_agent_metrics[tid] = {
            "trader_id": tid,
            "days_traded": len(days),
            "total_allocations": total_allocs,
            "wins": sum(wins),
            "losses": sum(1 - w for w in wins),
            "win_rate": round(win_rate, 3),
            "avg_confidence": round(avg_conf, 3),
            "calibration_gap": round(calibration_gap, 3),  # + = overconfident
            "avg_declared_edge": round(avg_edge, 4),
            "realized_ev": round(realized_ev, 4),  # avg profit/stake per bet
            "final_bankroll": bankroll_series[-1] if bankroll_series else 100,
            "best_bankroll": max(bankroll_series) if bankroll_series else 100,
            "worst_bankroll": min(bankroll_series) if bankroll_series else 100,
        }

    # Keyword winning rate
    keyword_win_rate = {}
    for kw, total in rationale_keywords.most_common():
        wins = winning_keywords.get(kw, 0)
        keyword_win_rate[kw] = {
            "mentions": total,
            "wins": wins,
            "win_rate": round(wins / total, 3) if total else 0,
        }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experiment_state": {
            "days_processed": status.get("days_processed"),
            "days_total": status.get("days_total"),
            "games_total": status.get("games_total"),
            "design": status.get("design"),
            "completed": status.get("completed"),
        },
        "per_agent": per_agent_metrics,
        "rationale_patterns": keyword_win_rate,
    }


def write_council_verdicts(analysis: dict):
    """Produce D3 Evolution + D6 Evaluation council verdicts."""
    if "error" in analysis:
        return
    DEPT_DIR.mkdir(parents=True, exist_ok=True)

    per_agent = analysis["per_agent"]
    best_bank = max((a.get("final_bankroll", 0) for a in per_agent.values()), default=0)
    worst_bank = min((a.get("final_bankroll", 0) for a in per_agent.values()), default=0)
    overconfident = [tid for tid, a in per_agent.items() if a.get("calibration_gap", 0) > 0.15]
    well_calibrated = [tid for tid, a in per_agent.items() if -0.05 <= a.get("calibration_gap", 1) <= 0.05]

    # D6 Evaluation: calibration + realized EV audit
    d6 = {
        "timestamp": analysis["timestamp"],
        "council": "d6-evaluation",
        "subject": "Trading Floor v3 Calibration Audit",
        "findings": {
            "n_agents": len(per_agent),
            "well_calibrated": well_calibrated,
            "overconfident": overconfident,
            "best_bankroll": round(best_bank, 2),
            "worst_bankroll": round(worst_bank, 2),
            "bankroll_spread": round(best_bank - worst_bank, 2),
        },
        "per_agent_summary": per_agent,
        "verdicts": [],
    }
    if overconfident:
        d6["verdicts"].append(
            f"{len(overconfident)} agent(s) overconfident (gap>0.15): {', '.join(overconfident)}"
        )
    if len(well_calibrated) >= len(per_agent) // 2:
        d6["verdicts"].append(f"Majority of agents well-calibrated — v3 prompt design works")
    else:
        d6["verdicts"].append("<50% agents well-calibrated — tighten prompt edge-computation instructions")

    (DEPT_DIR / "council-evaluation-latest.json").write_text(json.dumps(d6, indent=2))

    # D3 Evolution: winning rationale patterns to seed feature engineering
    top_winning = sorted(
        analysis["rationale_patterns"].items(),
        key=lambda kv: (kv[1]["win_rate"], kv[1]["mentions"]),
        reverse=True
    )[:10]
    d3 = {
        "timestamp": analysis["timestamp"],
        "council": "d3-evolution",
        "subject": "Trading Floor v3 Rationale Pattern Mining",
        "findings": {
            "best_agent": max(per_agent.items(), key=lambda kv: kv[1].get("final_bankroll", 0))[0] if per_agent else None,
            "top_winning_keywords": [
                {"keyword": k, **v} for k, v in top_winning
            ],
        },
        "verdicts": [
            f"Top-winning rationale keywords (win rate): " +
            ", ".join(f"{k} ({v['win_rate']:.0%} n={v['mentions']})" for k, v in top_winning[:5])
            if top_winning else "Insufficient allocations to mine rationale patterns",
            "→ Seed D2 Engineering to add features for top keywords (e.g. rest differential, altitude dummy)",
        ],
    }
    (DEPT_DIR / "council-evolution-latest.json").write_text(json.dumps(d3, indent=2))

    # Timestamped archive copy
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    arch = DEPT_DIR / "archive"
    arch.mkdir(exist_ok=True)
    (arch / f"council-evaluation-{ts}.json").write_text(json.dumps(d6, indent=2))
    (arch / f"council-evolution-{ts}.json").write_text(json.dumps(d3, indent=2))

    # Full analysis for debugging
    (DEPT_DIR / "trading-floor-v3-analysis-latest.json").write_text(json.dumps(analysis, indent=2))


def actuate_mutations(
    analysis: dict,
    dry_run: bool = True,
    gap_threshold: float = 0.20,
    step: float = 0.10,
    floor: float = 0.15,
    min_allocs: int = 5,
    min_bankroll: float = 10.0,
) -> list:
    """Close the D6-observe → HF-mutate loop (research W1, arXiv:2604.01658 CORAL pattern).

    For each agent with calibration_gap > gap_threshold, reduce risk_tolerance by `step`
    (floored at `floor`) via POST /api/mutate. Idempotent via ACTUATOR_STATE_PATH —
    we track last_applied_risk per agent and monotonically step down only (no oscillation).

    Skips:
      - agents with fewer than `min_allocs` bets (likely silent-fail like gemini parser bug)
      - agents already bankrupt (< `min_bankroll`) — mutation won't revive them
    """
    if "error" in analysis:
        return []
    per_agent = analysis.get("per_agent", {})
    state = load_actuator_state()
    actions: list = []

    for tid, m in per_agent.items():
        gap = m.get("calibration_gap", 0)
        bankroll = m.get("final_bankroll", 100)
        n_allocs = m.get("total_allocations", 0)

        if n_allocs < min_allocs or bankroll < min_bankroll or gap <= gap_threshold:
            continue

        prev = state.get(tid, {})
        last_risk = prev.get("last_applied_risk")
        baseline = last_risk if last_risk is not None else TRADER_DEFAULT_RISK.get(tid, 0.55)
        new_risk = max(floor, round(baseline - step, 2))

        if new_risk >= baseline:
            continue  # already at floor

        action = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": tid,
            "calibration_gap": gap,
            "total_allocations": n_allocs,
            "final_bankroll": bankroll,
            "prev_risk": baseline,
            "new_risk_tolerance": new_risk,
            "reason": f"overconfident (gap={gap:.3f} > {gap_threshold})",
            "dry_run": dry_run,
        }

        if not dry_run:
            try:
                resp = post_mutate(tid, new_risk)
                action["api_response"] = resp
                state[tid] = {
                    "last_applied_risk": new_risk,
                    "last_gap": gap,
                    "last_ts": action["ts"],
                }
            except Exception as e:
                action["error"] = str(e)

        actions.append(action)

    if not dry_run and actions:
        save_actuator_state(state)
        with ACTUATOR_LOG_PATH.open("a") as f:
            for a in actions:
                f.write(json.dumps(a) + "\n")

    return actions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="ISO date YYYY-MM-DD, only include days on/after")
    ap.add_argument("--dry-run", action="store_true", help="Print analysis without writing")
    ap.add_argument("--actuate", action="store_true",
                    help="Close the loop: POST /api/mutate for overconfident agents (gap>0.20)")
    ap.add_argument("--actuate-dry", action="store_true",
                    help="Print mutation plan without POSTing (safe default for first run)")
    args = ap.parse_args()

    print(f"[{datetime.now(timezone.utc).isoformat()}] Fetching from {HF_BASE}...", file=sys.stderr)
    analysis = analyze(since=args.since)
    if args.dry_run:
        print(json.dumps(analysis, indent=2))
        return
    write_council_verdicts(analysis)

    actions = []
    if args.actuate or args.actuate_dry:
        actions = actuate_mutations(analysis, dry_run=args.actuate_dry)

    print(json.dumps({
        "status": "ok",
        "agents_analyzed": len(analysis.get("per_agent", {})),
        "councils_written": ["d3-evolution", "d6-evaluation"],
        "mutations_attempted": len(actions),
        "mutations": actions,
    }, indent=2))


if __name__ == "__main__":
    main()
