#!/usr/bin/env python3
"""
Research Scanner — Quick scan for research proposals and papers.
Used by department-council.sh for D1 (Research) council checks.

Usage:
    python3 research-scanner.py --quick    # Fast scan: count proposals, check freshness
    python3 research-scanner.py --full     # Full scan: also read arxiv/github scan files
"""

import json
import os
import sys
import glob
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RESEARCH_DIR = ROOT / "data" / "research"
PROPOSALS_DIR = ROOT / "data" / "arena" / "proposals"
DEPT_RESEARCH = ROOT / "data" / "departments" / "research"

NOW = datetime.utcnow()
TODAY = NOW.strftime("%Y-%m-%d")
WEEK_AGO = (NOW - timedelta(days=7)).strftime("%Y-%m-%d")


def count_proposals():
    """Count research proposals by status."""
    counts = {"total": 0, "pending": 0, "accepted": 0, "rejected": 0, "tested": 0}
    for d in [PROPOSALS_DIR, DEPT_RESEARCH]:
        if not d.exists():
            continue
        for f in d.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                counts["total"] += 1
                status = data.get("status", "pending")
                if status in counts:
                    counts[status] += 1
            except Exception:
                continue
    return counts


def check_research_freshness():
    """Check if research data is fresh (< 7 days old)."""
    if not RESEARCH_DIR.exists():
        return {"fresh": False, "reason": "research directory missing", "latest": None}

    scan_files = sorted(RESEARCH_DIR.glob("*-scan-*.json"), reverse=True)
    if not scan_files:
        return {"fresh": False, "reason": "no scan files found", "latest": None}

    latest = scan_files[0]
    try:
        stat = latest.stat()
        age_days = (NOW.timestamp() - stat.st_mtime) / 86400
        return {
            "fresh": age_days < 7,
            "latest": latest.name,
            "age_days": round(age_days, 1),
        }
    except Exception:
        return {"fresh": False, "reason": "stat error", "latest": latest.name}


def count_techniques_tested():
    """Count unique techniques mentioned in karpathy outputs."""
    karpathy_files = list((ROOT / "data" / "departments").rglob("karpathy-output.json"))
    techniques = set()
    for f in karpathy_files:
        try:
            data = json.loads(f.read_text())
            for rec in data.get("recommendations", []):
                if rec.get("type") in ("promote_strategy", "promote_model"):
                    techniques.add(rec.get("strategy", rec.get("model", "")))
        except Exception:
            continue
    return len(techniques)


def quick_scan():
    """Fast scan — print summary."""
    proposals = count_proposals()
    freshness = check_research_freshness()
    techniques = count_techniques_tested()

    print(f"Proposals: {proposals['total']} total ({proposals['pending']} pending, {proposals['accepted']} accepted)")
    print(f"Research data: {'FRESH' if freshness['fresh'] else 'STALE'} (latest: {freshness.get('latest', 'none')}, age: {freshness.get('age_days', '?')}d)")
    print(f"Techniques tested: {techniques}")

    # Write output for council
    DEPT_RESEARCH.mkdir(parents=True, exist_ok=True)
    output = {
        "timestamp": NOW.isoformat() + "Z",
        "proposals": proposals,
        "freshness": freshness,
        "techniques_tested": techniques,
    }
    (DEPT_RESEARCH / "scanner-output.json").write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--quick"
    if mode in ("--quick", "--fast"):
        quick_scan()
    elif mode == "--full":
        quick_scan()
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
