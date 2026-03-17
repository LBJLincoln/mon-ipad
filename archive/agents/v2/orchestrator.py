#!/usr/bin/env python3
"""V2 Orchestrator — The brain that coordinates all repos.

Architecture:
  1. Score ALL 7 repos on ALL 7 categories → 49 metrics
  2. Rank repos by worst gap from goals
  3. Run Karpathy cycle on the worst repo×category
  4. Log EVERYTHING: scores, decisions, results, learning
  5. Move to next repo
  6. Repeat

EVERYTHING IS MEASURED. EVERYTHING IS LOGGED.
No action happens without before/after measurement.
No measurement happens without being persisted for analysis.

Usage:
    source .env.local
    python3 agents/v2/orchestrator.py --once              # Single cycle
    python3 agents/v2/orchestrator.py --daemon 600        # Loop every 10min
    python3 agents/v2/orchestrator.py --repo rag-website   # Specific repo
    python3 agents/v2/orchestrator.py --scan               # Scan only (no changes)
    python3 agents/v2/orchestrator.py --report             # Full report
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Setup paths
BASE_DIR = Path("/home/termius/mon-ipad")
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(BASE_DIR / "agents"))

from engine import KarpathyEngine, Score, log
from config import get_all_repos, get_repo, REPOS
from base import load_env, telegram_notify, log_event

# ─── Persistent State ──────────────────────────────────────────────────────

STATE_DIR = BASE_DIR / "data" / "agents" / "v2"
STATE_FILE = STATE_DIR / "orchestrator-state.json"
SCORES_LOG = STATE_DIR / "scores.jsonl"
CYCLES_LOG = STATE_DIR / "cycles.jsonl"
DASHBOARD_FILE = STATE_DIR / "dashboard.json"


def ensure_dirs():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "total_cycles": 0,
        "total_improvements": 0,
        "total_reverts": 0,
        "started": datetime.now(timezone.utc).isoformat(),
        "repos": {},
    }


def save_state(state: dict):
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def log_scores(scores_by_repo: dict):
    """Log ALL scores to JSONL — nothing goes unmeasured."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "repos": {},
    }
    for repo_name, scores in scores_by_repo.items():
        entry["repos"][repo_name] = {
            s.category: {"value": s.value, "target": s.target,
                         "gap": s.gap, "details": s.details}
            for s in scores
        }
    with open(SCORES_LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_cycle(result: dict):
    """Log cycle result to JSONL."""
    with open(CYCLES_LOG, "a") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def update_dashboard(scores_by_repo: dict, state: dict):
    """Write human-readable dashboard for monitoring."""
    dashboard = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_cycles": state.get("total_cycles", 0),
        "total_improvements": state.get("total_improvements", 0),
        "total_reverts": state.get("total_reverts", 0),
        "success_rate": (
            state["total_improvements"] / max(state["total_cycles"], 1) * 100
        ),
        "repos": {},
    }

    for repo_name, scores in scores_by_repo.items():
        avg = sum(s.value for s in scores) / max(len(scores), 1)
        avg_target = sum(s.target for s in scores) / max(len(scores), 1)
        worst = max(scores, key=lambda s: s.gap)
        dashboard["repos"][repo_name] = {
            "avg_score": round(avg, 1),
            "avg_target": round(avg_target, 1),
            "avg_gap": round(avg_target - avg, 1),
            "worst_category": worst.category,
            "worst_gap": round(worst.gap, 1),
            "scores": {s.category: round(s.value, 1) for s in scores},
        }

    DASHBOARD_FILE.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False))
    return dashboard


# ─── Scan: Measure Everything ──────────────────────────────────────────────

def scan_all_repos(repos: list = None) -> dict:
    """Measure ALL repos on ALL 7 categories. Log everything."""
    if repos is None:
        repos = get_all_repos()

    scores_by_repo = {}
    for repo in repos:
        name = repo["name"]
        path = repo["path"]

        if not Path(path).exists():
            log(f"[{name}] SKIP — path not found: {path}")
            continue

        try:
            scores = repo["measure_fn"](repo)
            scores_by_repo[name] = scores

            avg = sum(s.value for s in scores) / max(len(scores), 1)
            worst = max(scores, key=lambda s: s.gap)
            log(f"[{name}] avg={avg:.0f} | worst={worst.category}({worst.value:.0f}/{worst.target:.0f})")
        except Exception as e:
            log(f"[{name}] MEASURE ERROR: {e}")
            scores_by_repo[name] = []

    # Log ALL scores
    log_scores(scores_by_repo)
    return scores_by_repo


def print_report(scores_by_repo: dict):
    """Print formatted report of all scores."""
    print(f"\n{'='*75}")
    print(f"  V2 KARPATHY × 7-CATEGORY REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*75}\n")

    cats = ["strategie", "produit", "business", "communication",
            "admin", "test_eval", "amelioration"]

    # Header
    header = f"{'Repo':<20}" + "".join(f"{'  ' + c[:4]:>7}" for c in cats) + f"{'  AVG':>7}"
    print(f"  {header}")
    print(f"  {'─'*len(header)}")

    for name in sorted(scores_by_repo.keys()):
        scores = scores_by_repo[name]
        if not scores:
            print(f"  {name:<20} (no data)")
            continue

        by_cat = {s.category: s for s in scores}
        parts = []
        for c in cats:
            s = by_cat.get(c)
            if s:
                # Color: green if gap<=0, yellow if gap<=20, red otherwise
                val = f"{s.value:.0f}"
                if s.gap <= 0:
                    parts.append(f"\033[92m{val:>7}\033[0m")
                elif s.gap <= 20:
                    parts.append(f"\033[93m{val:>7}\033[0m")
                else:
                    parts.append(f"\033[91m{val:>7}\033[0m")
            else:
                parts.append(f"{'?':>7}")

        avg = sum(s.value for s in scores) / max(len(scores), 1)
        parts.append(f"{avg:>7.0f}")
        print(f"  {name:<20}{''.join(parts)}")

    # Targets row
    print(f"  {'─'*len(header)}")
    print(f"  {'TARGETS':<20}" + "".join(f"{'80':>7}" for _ in cats) + f"{'80':>7}")
    print()


# ─── Pick Next Repo to Improve ─────────────────────────────────────────────

def pick_next_target(scores_by_repo: dict, state: dict,
                     target_repo: str = None) -> tuple:
    """Pick the repo×category with the largest gap from goal.

    Returns (repo_config, weakest_score) or (None, None).
    """
    if target_repo:
        repo = get_repo(target_repo)
        if repo and target_repo in scores_by_repo:
            scores = scores_by_repo[target_repo]
            if scores:
                weakest = max(scores, key=lambda s: s.gap)
                if weakest.gap > 0:
                    return repo, weakest
        return None, None

    # Find the repo×category with the worst gap, weighted by priority
    best_target = None
    best_score_val = -1

    for repo in get_all_repos():
        name = repo["name"]
        if name not in scores_by_repo:
            continue
        scores = scores_by_repo[name]
        if not scores:
            continue

        weakest = max(scores, key=lambda s: s.gap)
        if weakest.gap <= 0:
            continue

        # Weighted score: gap × priority
        weighted = weakest.gap * repo["priority"]

        # Penalty for recently improved repos (avoid thrashing)
        repo_state = state.get("repos", {}).get(name, {})
        last_cycle = repo_state.get("last_cycle_ts", "2020-01-01")
        try:
            last_dt = datetime.fromisoformat(last_cycle.replace("Z", "+00:00"))
            age_minutes = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
            if age_minutes < 30:
                weighted *= 0.5  # Recently touched — lower priority
        except Exception:
            pass

        if weighted > best_score_val:
            best_score_val = weighted
            best_target = (repo, weakest)

    if best_target:
        return best_target
    return None, None


# ─── Main Orchestrator Loop ────────────────────────────────────────────────

def run_orchestrator(args):
    """Main orchestrator loop."""
    load_env()
    ensure_dirs()

    engine = KarpathyEngine()
    state = load_state()

    repos = get_all_repos()
    if args.repo:
        repo = get_repo(args.repo)
        if not repo:
            print(f"Unknown repo: {args.repo}")
            sys.exit(1)
        repos = [repo]

    cycle_count = 0
    max_cycles = args.max or 100

    print("=" * 60)
    print("  V2 KARPATHY × 7-CATEGORY ORCHESTRATOR")
    print(f"  Repos: {len(repos)} | Mode: {'scan' if args.scan else 'daemon' if args.daemon else 'once'}")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    print()

    while cycle_count < max_cycles:
        cycle_start = time.time()

        # ── SCAN: Measure everything ──
        log("━━━ SCANNING ALL REPOS ━━━")
        scores_by_repo = scan_all_repos(repos)

        # ── REPORT ──
        if args.report or args.scan:
            print_report(scores_by_repo)
            dashboard = update_dashboard(scores_by_repo, state)
            if args.scan or args.report:
                return dashboard

        # ── DASHBOARD ──
        dashboard = update_dashboard(scores_by_repo, state)

        # ── PICK TARGET ──
        target_repo, target_score = pick_next_target(
            scores_by_repo, state, args.repo)

        if not target_repo:
            log("All repos at target! Nothing to improve.")
            if not args.daemon:
                break
            log(f"Sleeping {args.daemon}s...")
            time.sleep(args.daemon)
            continue

        log(f"━━━ TARGET: {target_repo['name']}/{target_score.category} "
            f"(gap={target_score.gap:.0f}) ━━━")

        # ── KARPATHY CYCLE ──
        result = engine.run_cycle(target_repo)
        cycle_result = result.to_dict()
        log_cycle(cycle_result)

        # ── UPDATE STATE ──
        state["total_cycles"] = state.get("total_cycles", 0) + 1
        cycle_count += 1

        if result.status == "improved":
            state["total_improvements"] = state.get("total_improvements", 0) + 1
        elif result.status in ("reverted", "reverted_regression"):
            state["total_reverts"] = state.get("total_reverts", 0) + 1

        if "repos" not in state:
            state["repos"] = {}
        state["repos"][target_repo["name"]] = {
            "last_cycle_ts": datetime.now(timezone.utc).isoformat(),
            "last_category": result.category,
            "last_status": result.status,
            "last_delta": result.delta,
            "all_scores": result.all_scores,
        }
        save_state(state)

        # ── CYCLE SUMMARY ──
        duration = round(time.time() - cycle_start, 1)
        log(f"Cycle {cycle_count}: {target_repo['name']}/{result.category} → "
            f"{result.status} (delta={result.delta:+.0f}) [{duration}s]")
        log(f"Total: {state['total_cycles']} cycles, "
            f"{state['total_improvements']} improvements, "
            f"{state['total_reverts']} reverts, "
            f"rate={state['total_improvements']/max(state['total_cycles'],1)*100:.0f}%")

        # ── LOG TO AGENT EVENTS (interop with V1 agents) ──
        log_event("v2_orchestrator", "cycle", {
            "repo": target_repo["name"],
            "category": result.category,
            "status": result.status,
            "before": result.before,
            "after": result.after,
            "delta": result.delta,
            "duration": duration,
        })

        if not args.daemon and (args.once or cycle_count >= max_cycles):
            break

        if args.daemon:
            log(f"Sleeping {args.daemon}s before next cycle...")
            time.sleep(args.daemon)

    # ── FINAL REPORT ──
    scores_by_repo = scan_all_repos(repos)
    print_report(scores_by_repo)
    update_dashboard(scores_by_repo, state)

    # Telegram summary
    telegram_notify(
        f"[V2 ORCHESTRATOR] Session done\n"
        f"Cycles: {state['total_cycles']}\n"
        f"Improvements: {state['total_improvements']}\n"
        f"Reverts: {state['total_reverts']}\n"
        f"Success rate: {state['total_improvements']/max(state['total_cycles'],1)*100:.0f}%",
        silent=True)


def main():
    parser = argparse.ArgumentParser(
        description="V2 Karpathy × 7-Category Orchestrator")
    parser.add_argument("--once", action="store_true",
                        help="Run single improvement cycle")
    parser.add_argument("--daemon", type=int, metavar="SECONDS",
                        help="Loop with interval (e.g., --daemon 600)")
    parser.add_argument("--repo", type=str,
                        help="Target specific repo")
    parser.add_argument("--scan", action="store_true",
                        help="Scan and score only (no changes)")
    parser.add_argument("--report", action="store_true",
                        help="Generate full report")
    parser.add_argument("--max", type=int, default=100,
                        help="Max cycles per session (default: 100)")
    args = parser.parse_args()

    if not args.once and not args.daemon and not args.scan and not args.report:
        args.once = True  # Default to single cycle

    run_orchestrator(args)


if __name__ == "__main__":
    main()
