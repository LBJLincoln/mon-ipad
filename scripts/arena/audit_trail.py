#!/usr/bin/env python3
"""
Trading Floor Audit Trail Builder
===================================
Reads ALL council-iter-*.json files and trader state files to build:
  1. full-audit-trail.json   — unified log of every decision at every iteration
  2. strategy-evolution.json — timeline of each strategy's params/ROI across iterations
  3. agent-decisions.json    — per-agent decision history

Lightweight: pure JSON processing, no ML, no heavy deps.

Usage:
  python3 scripts/arena/audit_trail.py              # full rebuild from scratch
  python3 scripts/arena/audit_trail.py --append N   # append iteration N only (incremental)
"""

import json
import os
import sys
import glob
import argparse
from datetime import datetime, timezone
from collections import defaultdict

# ── PATHS ────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COUNCIL_DIR = os.path.join(ROOT, "data", "arena", "council")
TRADERS_DIR = os.path.join(ROOT, "data", "arena", "traders")
AUDIT_DIR = os.path.join(ROOT, "data", "arena", "audit")

FULL_TRAIL_PATH = os.path.join(AUDIT_DIR, "full-audit-trail.json")
STRATEGY_EVO_PATH = os.path.join(AUDIT_DIR, "strategy-evolution.json")
AGENT_DECISIONS_PATH = os.path.join(AUDIT_DIR, "agent-decisions.json")
AUDIT_META_PATH = os.path.join(AUDIT_DIR, "audit-meta.json")


def load_json(path):
    """Safely load a JSON file, return None on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        print(f"  WARN: Could not load {path}: {e}", file=sys.stderr)
        return None


def load_all_council_iters():
    """Load all council-iter-*.json files, sorted by iteration number."""
    pattern = os.path.join(COUNCIL_DIR, "council-iter-*.json")
    files = glob.glob(pattern)

    iters = []
    for fpath in files:
        basename = os.path.basename(fpath)
        # Extract iteration number from council-iter-N.json
        try:
            num = int(basename.replace("council-iter-", "").replace(".json", ""))
        except ValueError:
            continue
        iters.append((num, fpath))

    iters.sort(key=lambda x: x[0])
    return iters


def load_trader_states():
    """Load current trader state files (NBA only)."""
    states = {}
    nba_traders = ["claude", "codex", "gemini", "grok", "openrouter"]
    for trader in nba_traders:
        path = os.path.join(TRADERS_DIR, f"{trader}-state.json")
        data = load_json(path)
        if data:
            states[trader] = {
                "trader_id": data.get("trader_id", trader),
                "name": data.get("name", trader.title()),
                "provider": data.get("provider", ""),
                "personality": data.get("personality", ""),
                "risk_tolerance": data.get("risk_tolerance", 0),
                "nba_bankroll": data.get("nba_bankroll", 0),
                "nba_roi_pct": data.get("nba_roi_pct", 0),
                "nba_sharpe": data.get("nba_sharpe", 0),
                "nba_bets": data.get("nba_bets", 0),
                "nba_wins": data.get("nba_wins", 0),
                "nba_losses": data.get("nba_losses", 0),
                "nba_peak": data.get("nba_peak", 0),
                "nba_max_drawdown": data.get("nba_max_drawdown", 0),
            }
    return states


def extract_audit_entries(council_data, prev_council_data=None):
    """
    Extract structured audit entries from a single council iteration.
    Compares with previous iteration to detect changes.

    Returns a list of audit entry dicts.
    """
    entries = []
    iteration = council_data.get("council_iteration", 0)
    timestamp = council_data.get("timestamp", "")
    source_iter = council_data.get("source_iteration", 0)
    source_gen = council_data.get("source_generation", 0)

    analysis = council_data.get("analysis", {})
    decisions = council_data.get("decisions", {})
    metrics = council_data.get("metrics", {})
    leaderboard = analysis.get("leaderboard_summary", [])

    # Build trader performance lookup for this iteration
    trader_perf = {}
    for t in leaderboard:
        tid = t.get("trader_id", "")
        trader_perf[tid] = {
            "rank": t.get("rank", 0),
            "bankroll": t.get("nba_bankroll", 0),
            "roi_pct": t.get("nba_roi_pct", 0),
            "sharpe": t.get("nba_sharpe", 0),
        }

    # Previous iteration leaderboard for comparison
    prev_trader_perf = {}
    if prev_council_data:
        for t in prev_council_data.get("analysis", {}).get("leaderboard_summary", []):
            tid = t.get("trader_id", "")
            prev_trader_perf[tid] = {
                "rank": t.get("rank", 0),
                "bankroll": t.get("nba_bankroll", 0),
                "roi_pct": t.get("nba_roi_pct", 0),
                "sharpe": t.get("nba_sharpe", 0),
            }

    # ── 1. Mutation decisions (adopt_winner_strategies) ──────────────────
    for mut in decisions.get("mutations", []):
        agent = mut.get("agent", "unknown")
        perf = trader_perf.get(agent, {})
        prev_perf = prev_trader_perf.get(agent, {})

        entries.append({
            "iteration": iteration,
            "timestamp": timestamp,
            "source_iteration": source_iter,
            "source_generation": source_gen,
            "trader_id": agent,
            "action_type": "mutation",
            "action_subtype": mut.get("action", "adopt_winner_strategies"),
            "old_value": {
                "rank": prev_perf.get("rank"),
                "bankroll": prev_perf.get("bankroll"),
            } if prev_perf else None,
            "new_value": {
                "adopt_strategies": mut.get("adopt_strategies", []),
                "adopt_models": mut.get("adopt_models", []),
                "from_agent": mut.get("from_agent", ""),
            },
            "reason": mut.get("reason", ""),
            "performance_at_time": perf,
        })

    # ── 2. New experiment proposals ──────────────────────────────────────
    for exp in decisions.get("new_experiments", []):
        exp_type = exp.get("type", "unknown")
        entries.append({
            "iteration": iteration,
            "timestamp": timestamp,
            "source_iteration": source_iter,
            "source_generation": source_gen,
            "trader_id": "_council",  # Council-level decision
            "action_type": "experiment",
            "action_subtype": exp_type,
            "old_value": None,
            "new_value": {
                k: v for k, v in exp.items() if k != "type"
            },
            "reason": exp.get("hypothesis", ""),
            "performance_at_time": {
                "best_bankroll": metrics.get("best_bankroll", 0),
                "best_trader": metrics.get("best_trader", ""),
                "distance_to_1m": metrics.get("distance_to_1m", 0),
            },
        })

    # ── 3. Elimination decisions ─────────────────────────────────────────
    for elim in decisions.get("eliminations", []):
        entries.append({
            "iteration": iteration,
            "timestamp": timestamp,
            "source_iteration": source_iter,
            "source_generation": source_gen,
            "trader_id": "_council",
            "action_type": "elimination",
            "action_subtype": "strategy_elimination",
            "old_value": {
                "strategy": elim.get("strategy", ""),
                "roi_pct": elim.get("roi_pct", 0),
                "bets": elim.get("bets", 0),
            },
            "new_value": {
                "action": elim.get("action", "eliminate_next_iteration"),
            },
            "reason": elim.get("reason", ""),
            "performance_at_time": {
                "best_bankroll": metrics.get("best_bankroll", 0),
                "best_trader": metrics.get("best_trader", ""),
            },
        })

    # ── 4. Leaderboard changes (rank shifts) ─────────────────────────────
    if prev_trader_perf:
        for tid, perf in trader_perf.items():
            prev = prev_trader_perf.get(tid, {})
            if prev and prev.get("rank") != perf.get("rank"):
                entries.append({
                    "iteration": iteration,
                    "timestamp": timestamp,
                    "source_iteration": source_iter,
                    "source_generation": source_gen,
                    "trader_id": tid,
                    "action_type": "rank_change",
                    "action_subtype": "leaderboard_shift",
                    "old_value": {
                        "rank": prev.get("rank"),
                        "bankroll": prev.get("bankroll"),
                    },
                    "new_value": {
                        "rank": perf.get("rank"),
                        "bankroll": perf.get("bankroll"),
                    },
                    "reason": f"Rank moved from #{prev.get('rank')} to #{perf.get('rank')}",
                    "performance_at_time": perf,
                })

    # ── 5. Strategy shifts (top strategies changed) ──────────────────────
    if prev_council_data:
        prev_top = set(
            s.get("strategy", "")
            for s in prev_council_data.get("analysis", {}).get("top_strategies", [])
        )
        curr_top = set(
            s.get("strategy", "")
            for s in analysis.get("top_strategies", [])
        )
        new_top = curr_top - prev_top
        dropped = prev_top - curr_top
        if new_top or dropped:
            entries.append({
                "iteration": iteration,
                "timestamp": timestamp,
                "source_iteration": source_iter,
                "source_generation": source_gen,
                "trader_id": "_council",
                "action_type": "strategy_shift",
                "action_subtype": "top_strategies_changed",
                "old_value": {
                    "top_strategies": sorted(prev_top),
                },
                "new_value": {
                    "top_strategies": sorted(curr_top),
                    "newly_promoted": sorted(new_top),
                    "dropped": sorted(dropped),
                },
                "reason": f"Top strategies shifted: +{sorted(new_top)} / -{sorted(dropped)}",
                "performance_at_time": {
                    "best_bankroll": metrics.get("best_bankroll", 0),
                },
            })

    # ── 6. Bankroll milestones ───────────────────────────────────────────
    for tid, perf in trader_perf.items():
        prev = prev_trader_perf.get(tid, {})
        if prev:
            old_b = prev.get("bankroll", 0)
            new_b = perf.get("bankroll", 0)
            # Detect significant bankroll changes (>10% shift)
            if old_b > 0 and abs(new_b - old_b) / old_b > 0.10:
                direction = "surge" if new_b > old_b else "decline"
                pct_change = ((new_b - old_b) / old_b) * 100
                entries.append({
                    "iteration": iteration,
                    "timestamp": timestamp,
                    "source_iteration": source_iter,
                    "source_generation": source_gen,
                    "trader_id": tid,
                    "action_type": "bankroll_milestone",
                    "action_subtype": direction,
                    "old_value": {"bankroll": round(old_b, 2)},
                    "new_value": {"bankroll": round(new_b, 2)},
                    "reason": f"Bankroll {direction}: {pct_change:+.1f}% (${old_b:.2f} -> ${new_b:.2f})",
                    "performance_at_time": perf,
                })

    return entries


def build_strategy_evolution(all_council_data):
    """
    Build a timeline of each strategy's performance across all iterations.
    Returns dict: { strategy_name: [{ iteration, roi_pct, win_rate, bets, traders }] }
    """
    evolution = defaultdict(list)

    for council in all_council_data:
        iteration = council.get("council_iteration", 0)
        timestamp = council.get("timestamp", "")
        source_gen = council.get("source_generation", 0)

        all_strats = (
            council.get("analysis", {}).get("top_strategies", [])
            + council.get("analysis", {}).get("bottom_strategies", [])
        )

        seen = set()
        for s in all_strats:
            name = s.get("strategy", "")
            if not name or name in seen:
                continue
            seen.add(name)
            evolution[name].append({
                "iteration": iteration,
                "timestamp": timestamp,
                "generation": source_gen,
                "roi_pct": s.get("roi_pct", 0),
                "win_rate_pct": s.get("win_rate_pct", 0),
                "bets": s.get("bets", 0),
                "traders_using": s.get("traders_using", []),
            })

    # Sort each strategy's timeline by iteration
    for name in evolution:
        evolution[name].sort(key=lambda x: x["iteration"])

    # Add summary stats per strategy
    result = {}
    for name, timeline in evolution.items():
        rois = [t["roi_pct"] for t in timeline]
        result[name] = {
            "strategy": name,
            "first_seen_iteration": timeline[0]["iteration"],
            "last_seen_iteration": timeline[-1]["iteration"],
            "appearances": len(timeline),
            "roi_range": {
                "min": round(min(rois), 2),
                "max": round(max(rois), 2),
                "latest": round(rois[-1], 2),
            },
            "latest_traders": timeline[-1].get("traders_using", []),
            "timeline": timeline,
        }

    return result


def build_agent_decisions(all_entries):
    """
    Group all audit entries by trader_id.
    Returns dict: { trader_id: { summary, decisions[] } }
    """
    agent_groups = defaultdict(list)
    for entry in all_entries:
        tid = entry.get("trader_id", "unknown")
        agent_groups[tid].append(entry)

    result = {}
    for tid, decisions in agent_groups.items():
        # Count by action type
        action_counts = defaultdict(int)
        for d in decisions:
            action_counts[d.get("action_type", "unknown")] += 1

        # Find performance trajectory
        perfs = []
        for d in decisions:
            p = d.get("performance_at_time", {})
            if "bankroll" in p:
                perfs.append({
                    "iteration": d["iteration"],
                    "bankroll": p["bankroll"],
                    "rank": p.get("rank"),
                })

        result[tid] = {
            "trader_id": tid,
            "total_decisions": len(decisions),
            "action_type_counts": dict(action_counts),
            "first_decision_iteration": decisions[0]["iteration"] if decisions else None,
            "last_decision_iteration": decisions[-1]["iteration"] if decisions else None,
            "performance_trajectory": perfs[:50] if len(perfs) > 50 else perfs,  # Cap to keep file small
            "decisions": decisions,
        }

    return result


def build_full_audit(council_iters_to_process=None):
    """
    Main function: build or incrementally update all audit trail files.

    Args:
        council_iters_to_process: list of (iter_num, filepath) tuples.
            If None, loads all iterations.
    """
    os.makedirs(AUDIT_DIR, exist_ok=True)

    if council_iters_to_process is None:
        council_iters_to_process = load_all_council_iters()

    total = len(council_iters_to_process)
    print(f"[AUDIT] Processing {total} council iterations...")

    # Load all council data in order
    all_council_data = []
    for idx, (num, fpath) in enumerate(council_iters_to_process):
        data = load_json(fpath)
        if data:
            all_council_data.append(data)
        if (idx + 1) % 50 == 0:
            print(f"  Loaded {idx + 1}/{total} iterations...")

    print(f"[AUDIT] Successfully loaded {len(all_council_data)} iterations")

    # ── Build full audit trail entries ───────────────────────────────────
    print("[AUDIT] Extracting audit entries...")
    all_entries = []
    prev = None
    for council in all_council_data:
        entries = extract_audit_entries(council, prev)
        all_entries.extend(entries)
        prev = council

    print(f"[AUDIT] Generated {len(all_entries)} audit entries")

    # ── Load trader states for current snapshot ──────────────────────────
    trader_states = load_trader_states()

    # ── Build full-audit-trail.json ──────────────────────────────────────
    print("[AUDIT] Writing full-audit-trail.json...")
    trail = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(all_entries),
            "council_iterations_processed": len(all_council_data),
            "iteration_range": {
                "first": all_council_data[0].get("council_iteration", 0) if all_council_data else 0,
                "last": all_council_data[-1].get("council_iteration", 0) if all_council_data else 0,
            },
            "generation_range": {
                "first": all_council_data[0].get("source_generation", 0) if all_council_data else 0,
                "last": all_council_data[-1].get("source_generation", 0) if all_council_data else 0,
            },
            "action_type_summary": {},
            "trader_ids": sorted(set(e["trader_id"] for e in all_entries)),
        },
        "current_trader_states": trader_states,
        "entries": all_entries,
    }

    # Compute action type summary
    action_counts = defaultdict(int)
    for e in all_entries:
        action_counts[e.get("action_type", "unknown")] += 1
    trail["metadata"]["action_type_summary"] = dict(action_counts)

    with open(FULL_TRAIL_PATH, "w") as f:
        json.dump(trail, f, indent=2)
    size_kb = os.path.getsize(FULL_TRAIL_PATH) / 1024
    print(f"  -> {FULL_TRAIL_PATH} ({size_kb:.0f} KB, {len(all_entries)} entries)")

    # ── Build strategy-evolution.json ────────────────────────────────────
    print("[AUDIT] Writing strategy-evolution.json...")
    strat_evo = build_strategy_evolution(all_council_data)
    strat_output = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_strategies_tracked": len(strat_evo),
            "council_iterations_analyzed": len(all_council_data),
        },
        "strategies": strat_evo,
    }
    with open(STRATEGY_EVO_PATH, "w") as f:
        json.dump(strat_output, f, indent=2)
    size_kb = os.path.getsize(STRATEGY_EVO_PATH) / 1024
    print(f"  -> {STRATEGY_EVO_PATH} ({size_kb:.0f} KB, {len(strat_evo)} strategies)")

    # ── Build agent-decisions.json ───────────────────────────────────────
    print("[AUDIT] Writing agent-decisions.json...")
    agent_decs = build_agent_decisions(all_entries)
    agent_output = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_agents": len(agent_decs),
            "total_decisions": len(all_entries),
        },
        "agents": agent_decs,
    }
    with open(AGENT_DECISIONS_PATH, "w") as f:
        json.dump(agent_output, f, indent=2)
    size_kb = os.path.getsize(AGENT_DECISIONS_PATH) / 1024
    print(f"  -> {AGENT_DECISIONS_PATH} ({size_kb:.0f} KB, {len(agent_decs)} agents)")

    # ── Write audit metadata ─────────────────────────────────────────────
    meta = {
        "last_processed_iteration": all_council_data[-1].get("council_iteration", 0) if all_council_data else 0,
        "last_processed_at": datetime.now(timezone.utc).isoformat(),
        "total_iterations_processed": len(all_council_data),
        "total_audit_entries": len(all_entries),
        "files": {
            "full_trail": FULL_TRAIL_PATH,
            "strategy_evolution": STRATEGY_EVO_PATH,
            "agent_decisions": AGENT_DECISIONS_PATH,
        },
    }
    with open(AUDIT_META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"[AUDIT] Done. Metadata written to {AUDIT_META_PATH}")
    return meta


def append_iteration(iteration_num):
    """
    Incrementally append a single iteration to the existing audit trail.
    Much faster than full rebuild -- just processes 1 file.
    """
    os.makedirs(AUDIT_DIR, exist_ok=True)

    iter_path = os.path.join(COUNCIL_DIR, f"council-iter-{iteration_num}.json")
    if not os.path.exists(iter_path):
        print(f"[AUDIT] ERROR: {iter_path} not found", file=sys.stderr)
        return False

    new_data = load_json(iter_path)
    if not new_data:
        print(f"[AUDIT] ERROR: Could not parse {iter_path}", file=sys.stderr)
        return False

    # Load previous iteration for comparison
    prev_path = os.path.join(COUNCIL_DIR, f"council-iter-{iteration_num - 1}.json")
    prev_data = load_json(prev_path) if os.path.exists(prev_path) else None

    # Extract new entries
    new_entries = extract_audit_entries(new_data, prev_data)

    # ── Append to full-audit-trail.json ──────────────────────────────────
    trail = load_json(FULL_TRAIL_PATH)
    if trail is None:
        print("[AUDIT] No existing trail found -- running full rebuild instead.")
        build_full_audit()
        return True

    trail["entries"].extend(new_entries)
    trail["metadata"]["total_entries"] = len(trail["entries"])
    trail["metadata"]["council_iterations_processed"] += 1
    trail["metadata"]["iteration_range"]["last"] = iteration_num
    trail["metadata"]["generation_range"]["last"] = new_data.get("source_generation", 0)
    trail["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()

    # Update action type summary
    for e in new_entries:
        atype = e.get("action_type", "unknown")
        trail["metadata"]["action_type_summary"][atype] = (
            trail["metadata"]["action_type_summary"].get(atype, 0) + 1
        )

    # Update trader states
    trail["current_trader_states"] = load_trader_states()

    with open(FULL_TRAIL_PATH, "w") as f:
        json.dump(trail, f, indent=2)

    # ── Append to strategy-evolution.json ────────────────────────────────
    strat_evo_data = load_json(STRATEGY_EVO_PATH)
    if strat_evo_data:
        all_strats = (
            new_data.get("analysis", {}).get("top_strategies", [])
            + new_data.get("analysis", {}).get("bottom_strategies", [])
        )
        seen = set()
        for s in all_strats:
            name = s.get("strategy", "")
            if not name or name in seen:
                continue
            seen.add(name)
            point = {
                "iteration": iteration_num,
                "timestamp": new_data.get("timestamp", ""),
                "generation": new_data.get("source_generation", 0),
                "roi_pct": s.get("roi_pct", 0),
                "win_rate_pct": s.get("win_rate_pct", 0),
                "bets": s.get("bets", 0),
                "traders_using": s.get("traders_using", []),
            }
            strategies = strat_evo_data.get("strategies", {})
            if name in strategies:
                strategies[name]["timeline"].append(point)
                strategies[name]["last_seen_iteration"] = iteration_num
                strategies[name]["appearances"] += 1
                rois = [t["roi_pct"] for t in strategies[name]["timeline"]]
                strategies[name]["roi_range"] = {
                    "min": round(min(rois), 2),
                    "max": round(max(rois), 2),
                    "latest": round(rois[-1], 2),
                }
                strategies[name]["latest_traders"] = s.get("traders_using", [])
            else:
                strategies[name] = {
                    "strategy": name,
                    "first_seen_iteration": iteration_num,
                    "last_seen_iteration": iteration_num,
                    "appearances": 1,
                    "roi_range": {
                        "min": round(point["roi_pct"], 2),
                        "max": round(point["roi_pct"], 2),
                        "latest": round(point["roi_pct"], 2),
                    },
                    "latest_traders": s.get("traders_using", []),
                    "timeline": [point],
                }

        strat_evo_data["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()
        strat_evo_data["metadata"]["total_strategies_tracked"] = len(strat_evo_data.get("strategies", {}))
        with open(STRATEGY_EVO_PATH, "w") as f:
            json.dump(strat_evo_data, f, indent=2)

    # ── Append to agent-decisions.json ───────────────────────────────────
    agent_data = load_json(AGENT_DECISIONS_PATH)
    if agent_data:
        for entry in new_entries:
            tid = entry.get("trader_id", "unknown")
            agents = agent_data.get("agents", {})
            if tid in agents:
                agents[tid]["decisions"].append(entry)
                agents[tid]["total_decisions"] += 1
                agents[tid]["last_decision_iteration"] = iteration_num
                atype = entry.get("action_type", "unknown")
                agents[tid]["action_type_counts"][atype] = (
                    agents[tid]["action_type_counts"].get(atype, 0) + 1
                )
                # Update performance trajectory
                p = entry.get("performance_at_time", {})
                if "bankroll" in p:
                    traj = agents[tid].get("performance_trajectory", [])
                    if len(traj) < 50:
                        traj.append({
                            "iteration": iteration_num,
                            "bankroll": p["bankroll"],
                            "rank": p.get("rank"),
                        })
            else:
                agents[tid] = {
                    "trader_id": tid,
                    "total_decisions": 1,
                    "action_type_counts": {entry.get("action_type", "unknown"): 1},
                    "first_decision_iteration": iteration_num,
                    "last_decision_iteration": iteration_num,
                    "performance_trajectory": [],
                    "decisions": [entry],
                }

        agent_data["metadata"]["generated_at"] = datetime.now(timezone.utc).isoformat()
        agent_data["metadata"]["total_decisions"] = sum(
            a["total_decisions"] for a in agent_data.get("agents", {}).values()
        )
        with open(AGENT_DECISIONS_PATH, "w") as f:
            json.dump(agent_data, f, indent=2)

    # ── Update audit metadata ────────────────────────────────────────────
    meta = load_json(AUDIT_META_PATH) or {}
    meta["last_processed_iteration"] = iteration_num
    meta["last_processed_at"] = datetime.now(timezone.utc).isoformat()
    meta["total_iterations_processed"] = meta.get("total_iterations_processed", 0) + 1
    meta["total_audit_entries"] = len(trail["entries"])
    with open(AUDIT_META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"[AUDIT] Appended iteration {iteration_num}: {len(new_entries)} new entries")
    return True


def main():
    parser = argparse.ArgumentParser(description="Trading Floor Audit Trail Builder")
    parser.add_argument(
        "--append", type=int, default=None,
        help="Append a single iteration number (incremental mode)"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print summary stats from existing audit trail"
    )
    args = parser.parse_args()

    if args.stats:
        trail = load_json(FULL_TRAIL_PATH)
        if not trail:
            print("[AUDIT] No audit trail found. Run without --stats first.")
            return
        meta = trail.get("metadata", {})
        print(f"\n=== AUDIT TRAIL STATS ===")
        print(f"Total entries:      {meta.get('total_entries', 0)}")
        print(f"Iterations covered: {meta.get('iteration_range', {}).get('first', 0)} - {meta.get('iteration_range', {}).get('last', 0)}")
        print(f"Generation range:   {meta.get('generation_range', {}).get('first', 0)} - {meta.get('generation_range', {}).get('last', 0)}")
        print(f"Action types:")
        for atype, count in sorted(meta.get("action_type_summary", {}).items()):
            print(f"  {atype:25s} {count:5d}")
        print(f"Traders tracked:    {', '.join(meta.get('trader_ids', []))}")

        # Strategy evolution stats
        strat_data = load_json(STRATEGY_EVO_PATH)
        if strat_data:
            print(f"\n=== STRATEGY EVOLUTION ===")
            print(f"Strategies tracked: {strat_data.get('metadata', {}).get('total_strategies_tracked', 0)}")
            for name, info in sorted(strat_data.get("strategies", {}).items()):
                roi = info.get("roi_range", {})
                print(f"  {name:25s} | appearances: {info.get('appearances', 0):3d} | ROI: {roi.get('min', 0):>10.2f} - {roi.get('max', 0):>10.2f} (latest: {roi.get('latest', 0):>10.2f}) | traders: {info.get('latest_traders', [])}")

        # Agent decision stats
        agent_data = load_json(AGENT_DECISIONS_PATH)
        if agent_data:
            print(f"\n=== AGENT DECISION HISTORY ===")
            for tid, info in sorted(agent_data.get("agents", {}).items()):
                print(f"  {tid:15s} | decisions: {info.get('total_decisions', 0):4d} | types: {info.get('action_type_counts', {})}")

        print()
        return

    if args.append is not None:
        append_iteration(args.append)
    else:
        build_full_audit()


if __name__ == "__main__":
    main()
