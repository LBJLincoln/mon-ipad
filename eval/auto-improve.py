#!/usr/bin/env python3
"""
Auto-Improve Engine — Selects and applies the best next improvement.

Reads eval results + improvement backlog, picks the highest-impact pending
improvement, and applies it via workflows/improved/apply.py.

Strategy:
  1. Read current pipeline accuracy from data.json
  2. Identify the pipeline furthest from its target (biggest gap)
  3. Pick the highest-priority pending improvement for that pipeline
  4. Apply the improvement (--deploy to n8n, --local for source files)
  5. Update improvements.json status

Usage:
  python auto-improve.py                    # Dry-run: show what would be applied
  python auto-improve.py --apply            # Apply the improvement locally
  python auto-improve.py --apply --deploy   # Apply and deploy to n8n
  python auto-improve.py --apply-all        # Apply ALL pending improvements at once
  python auto-improve.py --status           # Show improvement backlog status
  python auto-improve.py --verify ID        # Mark improvement as verified with result
  python auto-improve.py --pipeline graph   # Force target a specific pipeline
"""

import json
import os
import sys
import subprocess
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(REPO_ROOT, "docs", "data.json")
IMPROVEMENTS_FILE = os.path.join(REPO_ROOT, "eval", "improvements.json")
APPLY_SCRIPT = os.path.join(REPO_ROOT, "workflows", "improved", "apply.py")


def load_data():
    """Load current eval data."""
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE) as f:
        return json.load(f)


def load_improvements():
    """Load improvement backlog."""
    with open(IMPROVEMENTS_FILE) as f:
        return json.load(f)


def save_improvements(backlog):
    """Save improvement backlog."""
    with open(IMPROVEMENTS_FILE, "w") as f:
        json.dump(backlog, f, indent=2, ensure_ascii=False)


def get_pipeline_gaps(data):
    """Calculate accuracy gap for each pipeline."""
    from importlib.machinery import SourceFileLoader
    gate_mod = SourceFileLoader("gate", os.path.join(REPO_ROOT, "eval", "phase-gate.py")).load_module()
    report = gate_mod.check_all_gates(data)

    gaps = {}
    for name, gate in report["pipelines"].items():
        gaps[name] = {
            "current": gate["current"],
            "target": gate["target"],
            "gap": gate.get("gap", gate["target"] - gate["current"]),
            "passed": gate["passed"],
        }
    return gaps


def select_next_improvement(backlog, data=None, force_pipeline=None):
    """Select the best next improvement to apply.

    Strategy:
    1. If force_pipeline is set, pick the top pending improvement for that pipeline
    2. Otherwise, prioritize the pipeline with the biggest accuracy gap
    3. Within a pipeline, pick by priority (P0 > P1 > P2) then expected impact
    """
    pending = [imp for imp in backlog["improvements"] if imp["status"] == "pending"]

    if not pending:
        return None, "No pending improvements left"

    if force_pipeline:
        pipeline_pending = [imp for imp in pending if imp["pipeline"] == force_pipeline]
        if not pipeline_pending:
            return None, f"No pending improvements for {force_pipeline}"
        pending = pipeline_pending
    elif data:
        # Sort pipelines by gap (descending)
        gaps = get_pipeline_gaps(data)
        pipe_priority = sorted(
            [(name, g["gap"]) for name, g in gaps.items() if not g["passed"]],
            key=lambda x: -x[1]
        )

        if pipe_priority:
            # Try pipelines in order of gap size
            for target_pipe, gap in pipe_priority:
                pipe_pending = [imp for imp in pending if imp["pipeline"] == target_pipe]
                if pipe_pending:
                    pending = pipe_pending
                    break

    # Sort by priority (P0 > P1 > P2), then by expected impact
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    pending.sort(key=lambda x: (
        priority_order.get(x["priority"], 9),
        -x.get("expected_impact_pp", 0)
    ))

    return pending[0], None


def mark_applied(backlog, improvement_id):
    """Mark an improvement as applied."""
    for imp in backlog["improvements"]:
        if imp["id"] == improvement_id:
            imp["status"] = "applied"
            imp["applied_at"] = datetime.utcnow().isoformat() + "Z"
            return True
    return False


def mark_verified(backlog, improvement_id, actual_impact):
    """Mark an improvement as verified with actual measured impact."""
    for imp in backlog["improvements"]:
        if imp["id"] == improvement_id:
            imp["status"] = "verified"
            imp["verified_at"] = datetime.utcnow().isoformat() + "Z"
            imp["actual_impact_pp"] = actual_impact
            return True
    return False


def mark_failed(backlog, improvement_id, reason=""):
    """Mark an improvement as failed (caused regression)."""
    for imp in backlog["improvements"]:
        if imp["id"] == improvement_id:
            imp["status"] = "failed"
            imp["verified_at"] = datetime.utcnow().isoformat() + "Z"
            imp["failure_reason"] = reason
            return True
    return False


def apply_improvement(improvement, deploy=False):
    """Apply an improvement by running the appropriate apply.py function.

    Returns (success, message).
    """
    apply_fn = improvement.get("apply_fn")
    if not apply_fn:
        return False, f"No apply function defined for {improvement['id']}"

    # Build apply.py command
    args = [sys.executable, APPLY_SCRIPT, "--local"]
    if deploy:
        args.append("--deploy")

    # apply.py applies ALL improvements for a workflow type at once
    # So we run it and it will patch everything
    print(f"  Running: {' '.join(args)}")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO_ROOT,
        )
        if result.returncode == 0:
            return True, result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
        else:
            return False, f"Exit code {result.returncode}: {result.stderr[-500:]}"
    except subprocess.TimeoutExpired:
        return False, "apply.py timed out after 120s"
    except Exception as e:
        return False, str(e)


def show_status(backlog):
    """Display improvement backlog status."""
    by_status = {"pending": [], "applied": [], "verified": [], "failed": []}
    for imp in backlog["improvements"]:
        by_status.setdefault(imp["status"], []).append(imp)

    print("Improvement Backlog Status")
    print("=" * 60)

    for status in ["pending", "applied", "verified", "failed"]:
        items = by_status.get(status, [])
        if items:
            print(f"\n  {status.upper()} ({len(items)}):")
            for imp in items:
                impact = f"+{imp['expected_impact_pp']}pp expected"
                if imp.get("actual_impact_pp") is not None:
                    impact = f"+{imp['actual_impact_pp']}pp actual"
                print(f"    [{imp['priority']}] {imp['id']}: {imp['title']} ({impact})")

    total = len(backlog["improvements"])
    done = len(by_status.get("verified", [])) + len(by_status.get("applied", []))
    print(f"\n  Progress: {done}/{total} improvements applied/verified")


def show_recommendation(improvement, gaps):
    """Show the recommended next improvement."""
    print("Next Recommended Improvement")
    print("=" * 60)
    print(f"  ID:       {improvement['id']}")
    print(f"  Pipeline: {improvement['pipeline']}")
    print(f"  Priority: {improvement['priority']}")
    print(f"  Title:    {improvement['title']}")
    print(f"  Impact:   +{improvement['expected_impact_pp']}pp expected")
    print(f"  Category: {improvement['category']}")
    print(f"  Detail:   {improvement['description']}")

    if gaps:
        pipe = improvement["pipeline"]
        if pipe in gaps:
            g = gaps[pipe]
            print(f"\n  Pipeline gap: {g['current']}% → {g['target']}% (need +{g['gap']}pp)")
            print(f"  This fix expected to close: +{improvement['expected_impact_pp']}pp of {g['gap']}pp gap")

    print(f"\n  To apply: python eval/auto-improve.py --apply")
    print(f"  To deploy: python eval/auto-improve.py --apply --deploy")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto-Improve Engine")
    parser.add_argument("--apply", action="store_true", help="Apply the next improvement")
    parser.add_argument("--apply-all", action="store_true", help="Apply ALL pending improvements")
    parser.add_argument("--deploy", action="store_true", help="Deploy to n8n after applying")
    parser.add_argument("--status", action="store_true", help="Show backlog status")
    parser.add_argument("--verify", type=str, help="Mark improvement as verified (ID)")
    parser.add_argument("--impact", type=float, help="Actual impact in pp (with --verify)")
    parser.add_argument("--fail", type=str, help="Mark improvement as failed (ID)")
    parser.add_argument("--pipeline", type=str, help="Force target a specific pipeline")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    backlog = load_improvements()

    if args.status:
        show_status(backlog)
        return

    if args.verify:
        impact = args.impact if args.impact is not None else 0
        if mark_verified(backlog, args.verify, impact):
            save_improvements(backlog)
            print(f"  Marked {args.verify} as verified (impact: +{impact}pp)")
        else:
            print(f"  ERROR: Improvement {args.verify} not found")
        return

    if args.fail:
        if mark_failed(backlog, args.fail):
            save_improvements(backlog)
            print(f"  Marked {args.fail} as failed")
        else:
            print(f"  ERROR: Improvement {args.fail} not found")
        return

    data = load_data()
    gaps = get_pipeline_gaps(data) if data else {}

    if args.apply_all:
        # Apply all pending improvements at once
        pending = [imp for imp in backlog["improvements"] if imp["status"] == "pending"]
        if not pending:
            print("  No pending improvements to apply.")
            return

        print(f"  Applying ALL {len(pending)} pending improvements...")
        success, msg = apply_improvement(pending[0], deploy=args.deploy)
        if success:
            for imp in pending:
                if imp.get("apply_fn"):
                    mark_applied(backlog, imp["id"])
            save_improvements(backlog)
            print(f"  Applied {len(pending)} improvements successfully.")
            if msg:
                print(f"  Output: {msg[:300]}")
        else:
            print(f"  FAILED: {msg}")
        return

    # Select next improvement
    improvement, error = select_next_improvement(backlog, data, args.pipeline)

    if not improvement:
        print(f"  {error or 'No improvements available'}")
        if args.json:
            print(json.dumps({"next": None, "reason": error}))
        return

    if args.json:
        print(json.dumps({
            "next": improvement,
            "pipeline_gaps": gaps,
        }, indent=2))
        return

    if args.apply:
        print(f"  Applying: {improvement['id']} — {improvement['title']}")
        success, msg = apply_improvement(improvement, deploy=args.deploy)
        if success:
            mark_applied(backlog, improvement["id"])
            save_improvements(backlog)
            print(f"  SUCCESS: {improvement['id']} applied")
            if msg:
                print(f"  Output: {msg[:300]}")
        else:
            print(f"  FAILED: {msg}")
            sys.exit(1)
    else:
        show_recommendation(improvement, gaps)


if __name__ == "__main__":
    main()
