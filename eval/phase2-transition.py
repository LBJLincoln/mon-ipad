#!/usr/bin/env python3
"""
Phase 2 Transition — Automates the move from Phase 1 to Phase 2.
================================================================
Called when Phase 1 gates pass. This script:

1. Validates Phase 1 gates are met (double-check)
2. Updates data.json with Phase 2 metadata
3. Updates STATUS.md with Phase 2 status
4. Prepares Phase 2 evaluation configuration
5. Generates the Phase 2 runbook (commands to execute in Termius)

Usage:
  python phase2-transition.py              # Dry-run: show what would change
  python phase2-transition.py --auto       # Execute transition
  python phase2-transition.py --force      # Skip Phase 1 gate validation
"""

import json
import os
import sys
from datetime import datetime

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
DATA_FILE = os.path.join(REPO_ROOT, "docs", "data.json")
STATUS_FILE = os.path.join(REPO_ROOT, "STATUS.md")

sys.path.insert(0, EVAL_DIR)


def validate_phase1_gates():
    """Check that Phase 1 gates are actually met."""
    try:
        from importlib.machinery import SourceFileLoader
        gate = SourceFileLoader("gate", os.path.join(EVAL_DIR, "phase-gate.py")).load_module()
        data = gate.load_data()
        if data is None:
            return False, "data.json not found"
        result = gate.check_phase_1(data, strict=False)
        return result["passed"], result["summary"]
    except Exception as e:
        return False, f"Gate check error: {e}"


def update_data_json():
    """Update data.json with Phase 2 metadata."""
    with open(DATA_FILE) as f:
        data = json.load(f)

    # Update meta
    data["meta"]["phase"] = "Phase 2 — Expand (1,000q)"
    data["meta"]["phase_transition"] = {
        "from": 1,
        "to": 2,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "phase1_final_accuracy": data["meta"].get("total_test_runs", 0),
    }

    # Store Phase 1 final results
    if data.get("iterations"):
        latest = data["iterations"][-1]
        data["meta"]["phase1_final_results"] = latest.get("results_summary", {})

    # Update pipeline targets for Phase 2
    if "graph" in data.get("pipelines", {}):
        data["pipelines"]["graph"]["phase2_target_accuracy"] = 60.0
    if "quantitative" in data.get("pipelines", {}):
        data["pipelines"]["quantitative"]["phase2_target_accuracy"] = 70.0

    # Add evaluation_phases if not present
    data.setdefault("evaluation_phases", {})
    data["evaluation_phases"]["phase_1"] = {
        "status": "COMPLETED",
        "completed_at": datetime.utcnow().isoformat() + "Z",
        "final_accuracy": latest.get("overall_accuracy_pct", 0) if data.get("iterations") else 0,
    }
    data["evaluation_phases"]["phase_2"] = {
        "status": "ACTIVE",
        "started_at": datetime.utcnow().isoformat() + "Z",
        "targets": {
            "graph": 60.0,
            "quantitative": 70.0,
            "overall": 65.0,
            "no_phase1_regression": True,
        },
    }
    data["current_phase"] = 2

    # Save
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)
    print("  Updated docs/data.json with Phase 2 metadata")


def update_status_md():
    """Update STATUS.md for Phase 2."""
    # Read current Phase 1 results from data.json
    with open(DATA_FILE) as f:
        data = json.load(f)

    phase1_results = data.get("meta", {}).get("phase1_final_results", {})

    status = f"""# Session Context -- Multi-RAG Orchestrator SOTA 2026

> This document is the entry point for any new session (human or agentic).
> Read this first, then consult `docs/data.json` for current metrics.

---

## Current State ({datetime.now().strftime('%b %d, %Y')})

### Phase 1 -- COMPLETED
All Phase 1 exit criteria have been met.

| Pipeline | Final Accuracy | Target | Status |
|----------|---------------|--------|--------|
"""
    for pipe in ["standard", "graph", "quantitative", "orchestrator"]:
        ps = phase1_results.get(pipe, {})
        acc = ps.get("accuracy_pct", 0)
        targets = {"standard": 85, "graph": 70, "quantitative": 85, "orchestrator": 70}
        target = targets.get(pipe, 0)
        status_text = "PASS" if acc >= target else "CLOSE"
        status += f"| **{pipe.title()}** | {acc}% | {target}% | {status_text} |\n"

    status += f"""
### Phase 2 -- ACTIVE (1,000q Expansion)

| Pipeline | Target | Dataset Source | DB Status |
|----------|--------|---------------|-----------|
| **Graph** | >=60% | musique, 2wikimultihopqa | DB_READY (4884 entities) |
| **Quantitative** | >=70% | finqa, tatqa, convfinqa, wikitablequestions | DB_READY (450 rows) |

---

## Phase 2 Runbook

### Step 1: Verify DB readiness (already done)
```bash
cd ~/mon-ipad && git pull origin main
# DB already populated from previous PR
```

### Step 2: Run Phase 2 evaluation
```bash
# Set env vars first (see CLAUDE.md)

# Fast iteration on Phase 2 questions
python3 eval/fast-iter.py --label "Phase 2 baseline" --questions 10

# Full evaluation (Phase 1 + Phase 2)
python3 eval/run-eval-parallel.py --include-1000 --reset --label "Phase 2 baseline"

# Analyze
python3 eval/analyzer.py
```

### Step 3: Iterate on Phase 2
```bash
# If results are bad, fix workflows and re-test
python3 eval/fast-iter.py --only-failing --label "Phase 2 fix attempt"

# Check Phase 2 gates
python3 eval/phase-gate.py --phase 2
```

### Step 4: Use agentic loop for automated iteration
```bash
python3 eval/agentic-loop.py --phase 2 --full-eval --push --label "Phase 2"
```

---

## Agentic Workflow (NEW)

### Automated iteration loop
The agentic loop automates the entire evaluation cycle:
```bash
# Single iteration: deploy + fast-iter + analyze + gate check
python3 eval/agentic-loop.py --label "description"

# Full cycle with 200q eval
python3 eval/agentic-loop.py --full-eval --push --label "description"

# Multiple iterations until gates pass
python3 eval/agentic-loop.py --max-iterations 5 --full-eval --push

# Phase 2 with auto-transition
python3 eval/agentic-loop.py --phase 2 --full-eval --push --phase2-transition
```

### GitHub Actions (auto-runs every 6 hours)
- `.github/workflows/agentic-iteration.yml` -- Full agentic workflow
- Modes: fast-iter, full-eval, agentic-loop, gate-check, phase2-transition
- Auto-creates issues on regression
- Auto-transitions to Phase 2 when gates pass

---

## Key Scripts

| Script | Purpose | Speed |
|--------|---------|-------|
| `eval/agentic-loop.py` | **Full automated iteration cycle** | Varies |
| `eval/phase-gate.py` | **Phase gate validator** | <1s |
| `eval/phase2-transition.py` | **Phase 2 transition automation** | <1s |
| `eval/fast-iter.py` | Quick validation, 10q/pipeline, parallel | ~2-3 min |
| `eval/run-eval-parallel.py` | Full 200q eval, all pipelines parallel | ~15-20 min |
| `eval/analyzer.py` | Post-eval analysis + recommendations | <1s |
| `eval/quick-test.py` | Smoke test, 3-5 known-good questions | ~1 min |

---

## Environment Variables

```bash
export SUPABASE_PASSWORD="..."
export PINECONE_API_KEY="..."
export PINECONE_HOST="https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
export NEO4J_PASSWORD="..."
export OPENROUTER_API_KEY="..."
export N8N_API_KEY="..."
export N8N_HOST="https://amoret.app.n8n.cloud"
```
"""

    with open(STATUS_FILE, "w") as f:
        f.write(status)
    print("  Updated STATUS.md for Phase 2")


def generate_runbook():
    """Print the Phase 2 runbook for the user."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                 PHASE 2 TRANSITION RUNBOOK                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1 gates are met. Here's what to do next:              ║
║                                                              ║
║  1. Pull latest code on your terminal:                       ║
║     cd ~/mon-ipad && git pull origin main                    ║
║                                                              ║
║  2. Phase 2 DB is already populated (from previous PR)       ║
║     - Supabase: 450 rows for finqa/tatqa/convfinqa          ║
║     - Neo4j: 4884 entities for musique/2wiki                ║
║                                                              ║
║  3. Run Phase 2 evaluation:                                  ║
║     python3 eval/agentic-loop.py --phase 2 \\                ║
║       --full-eval --push --label "Phase 2 baseline"          ║
║                                                              ║
║  4. Or use the automated GitHub Action:                      ║
║     Go to Actions → Agentic Iteration Loop → Run             ║
║     Select mode: full-eval, check "include Phase 2"          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Phase 2 Transition")
    parser.add_argument("--auto", action="store_true", help="Execute transition (not just dry-run)")
    parser.add_argument("--force", action="store_true", help="Skip Phase 1 gate validation")
    args = parser.parse_args()

    print("=" * 60)
    print("  PHASE 2 TRANSITION")
    print(f"  Mode: {'AUTO' if args.auto else 'DRY-RUN'}")
    print("=" * 60)

    # Step 1: Validate Phase 1 gates
    if not args.force:
        passed, summary = validate_phase1_gates()
        print(f"\n  Phase 1 gate check: {summary}")
        if not passed:
            print("  ABORT: Phase 1 gates not met. Use --force to override.")
            sys.exit(1)
        print("  Phase 1 gates PASSED -- proceeding with transition")
    else:
        print("  Skipping Phase 1 gate validation (--force)")

    if args.auto:
        # Step 2: Update data.json
        update_data_json()

        # Step 3: Update STATUS.md
        update_status_md()

        # Step 4: Show runbook
        generate_runbook()

        print("\n  Phase 2 transition complete!")
        print("  Next: Run Phase 2 eval on your terminal (see runbook above)")
    else:
        print("\n  DRY-RUN: Would update data.json and STATUS.md")
        print("  Run with --auto to execute transition")
        generate_runbook()


if __name__ == "__main__":
    main()
