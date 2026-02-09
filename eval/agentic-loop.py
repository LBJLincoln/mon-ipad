#!/usr/bin/env python3
"""
Agentic Iteration Loop — Automated Phase 1 completion pipeline.
================================================================
Orchestrates the full iteration cycle autonomously:

  1. DEPLOY  — Apply workflow patches to n8n (via apply.py)
  2. VALIDATE — Run fast-iter (10q/pipeline, ~3 min) to check patches work
  3. ANALYZE — Run analyzer.py to detect regressions/improvements
  4. GATE    — Check Phase 1 exit criteria (via phase-gate.py)
  5. FULL    — If fast-iter looks good, run full 200q parallel eval
  6. DECIDE  — If gates pass → transition to Phase 2
               If gates fail → log findings, prepare next iteration

This script is designed to run on a terminal with API access (Termius/GCloud).
It CANNOT run in Claude Code sandbox (no network).

Usage:
  # Full agentic loop: deploy + fast-iter + analyze + gate check
  python agentic-loop.py

  # Skip deployment, just eval + gate check
  python agentic-loop.py --skip-deploy

  # Run full 200q eval after fast-iter passes
  python agentic-loop.py --full-eval

  # Auto-push results to GitHub
  python agentic-loop.py --push

  # Multiple iterations until gates pass (max N)
  python agentic-loop.py --max-iterations 5

  # Phase 2 transition mode
  python agentic-loop.py --phase2-transition

Requires environment variables:
  N8N_API_KEY, N8N_HOST, SUPABASE_PASSWORD, PINECONE_API_KEY,
  NEO4J_PASSWORD, OPENROUTER_API_KEY
"""

import json
import os
import sys
import subprocess
import time
from datetime import datetime

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
WORKFLOWS_DIR = os.path.join(REPO_ROOT, "workflows", "improved")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
DATA_FILE = os.path.join(DOCS_DIR, "data.json")

# Import phase-gate
sys.path.insert(0, EVAL_DIR)


def log(msg, level="INFO"):
    """Print timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] [{level}] {msg}", flush=True)


def run_script(script_path, args=None, timeout_min=30):
    """Run a Python script and return (success, stdout, stderr)."""
    cmd = [sys.executable, script_path] + (args or [])
    log(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_min * 60,
        )
        # Print output in real-time style
        if result.stdout:
            for line in result.stdout.strip().split('\n')[-20:]:  # last 20 lines
                print(f"    {line}")
        if result.returncode != 0 and result.stderr:
            for line in result.stderr.strip().split('\n')[-10:]:
                print(f"    [ERR] {line}")
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        log(f"TIMEOUT after {timeout_min} minutes", "ERROR")
        return False, "", "Timeout"
    except Exception as e:
        log(f"Failed to run {script_path}: {e}", "ERROR")
        return False, "", str(e)


def check_env_vars():
    """Verify required environment variables are set."""
    required = ["N8N_HOST"]
    recommended = ["N8N_API_KEY", "OPENROUTER_API_KEY", "SUPABASE_PASSWORD",
                    "PINECONE_API_KEY", "NEO4J_PASSWORD"]

    missing_required = [v for v in required if not os.environ.get(v)]
    missing_recommended = [v for v in recommended if not os.environ.get(v)]

    if missing_required:
        log(f"MISSING REQUIRED env vars: {', '.join(missing_required)}", "ERROR")
        return False

    if missing_recommended:
        log(f"MISSING recommended env vars: {', '.join(missing_recommended)}", "WARN")

    return True


def step_deploy(local_only=False):
    """Step 1: Deploy workflow patches to n8n."""
    log("STEP 1: DEPLOY WORKFLOW PATCHES")
    apply_script = os.path.join(WORKFLOWS_DIR, "apply.py")

    if not os.path.exists(apply_script):
        log("apply.py not found — skipping deployment", "WARN")
        return True

    args = ["--local"]
    if not local_only and os.environ.get("N8N_API_KEY"):
        args.append("--deploy")
        log("Deploying to n8n cloud...")
    else:
        log("Local-only mode (no N8N_API_KEY or --skip-deploy)")

    success, stdout, stderr = run_script(apply_script, args, timeout_min=5)
    if success:
        log("Workflow patches applied successfully")
    else:
        log("Patch application had issues (continuing anyway)", "WARN")

    return True  # Non-blocking — patches may partially apply


def step_fast_iter(label="", questions=10):
    """Step 2: Run fast iteration to validate patches."""
    log(f"STEP 2: FAST ITERATION ({questions}q/pipeline)")
    fast_iter_script = os.path.join(EVAL_DIR, "fast-iter.py")

    args = ["--questions", str(questions)]
    if label:
        args.extend(["--label", label])

    success, stdout, stderr = run_script(fast_iter_script, args, timeout_min=10)

    if not success:
        log("Fast iteration failed", "ERROR")
        return False, {}

    # Parse results from the output
    results = _parse_fast_iter_output(stdout)
    log(f"Fast-iter results: {json.dumps(results, indent=2)}")
    return True, results


def step_analyze():
    """Step 3: Run analyzer for regression detection."""
    log("STEP 3: ANALYZE RESULTS")
    analyzer_script = os.path.join(EVAL_DIR, "analyzer.py")

    success, stdout, stderr = run_script(analyzer_script, ["--json"], timeout_min=2)

    if not success:
        log("Analysis failed (continuing)", "WARN")
        return {}

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        log("Could not parse analyzer output", "WARN")
        return {}


def step_gate_check(phase=1, strict=False):
    """Step 4: Check phase gates."""
    log(f"STEP 4: PHASE {phase} GATE CHECK")
    gate_script = os.path.join(EVAL_DIR, "phase-gate.py")

    args = ["--phase", str(phase), "--json"]
    if strict:
        args.append("--strict")

    success, stdout, stderr = run_script(gate_script, args, timeout_min=1)

    try:
        result = json.loads(stdout)
        log(result.get("summary", "Gate check complete"))
        return result
    except json.JSONDecodeError:
        log("Could not parse gate check output", "WARN")
        return {"passed": False, "summary": "Parse error"}


def step_full_eval(label="", reset=True):
    """Step 5: Run full 200q parallel evaluation."""
    log("STEP 5: FULL PARALLEL EVALUATION (200q)")
    parallel_script = os.path.join(EVAL_DIR, "run-eval-parallel.py")

    args = []
    if reset:
        args.append("--reset")
    if label:
        args.extend(["--label", label])

    success, stdout, stderr = run_script(parallel_script, args, timeout_min=30)

    if not success:
        log("Full evaluation failed", "ERROR")
        return False

    log("Full evaluation complete")
    return True


def step_commit_push(message="", push=False):
    """Step 6: Commit and optionally push results."""
    log("STEP 6: COMMIT RESULTS")

    # Stage results
    subprocess.run(
        ["git", "add", "docs/data.json", "docs/tested-questions.json",
         "logs/", "workflows/improved/"],
        cwd=REPO_ROOT,
        capture_output=True,
    )

    # Check if there are changes
    result = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        cwd=REPO_ROOT,
        capture_output=True,
    )

    if result.returncode == 0:
        log("No changes to commit")
        return True

    # Commit
    if not message:
        message = f"agentic-loop: iteration results {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    log(f"Committed: {message}")

    if push:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        ).stdout.strip()

        for attempt in range(4):
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch],
                cwd=REPO_ROOT, capture_output=True,
            )
            if result.returncode == 0:
                log(f"Pushed to {branch}")
                return True
            wait = 2 ** (attempt + 1)
            log(f"Push failed, retry {attempt + 1}/4 (waiting {wait}s)", "WARN")
            time.sleep(wait)

        log("Push failed after 4 retries", "ERROR")
        return False

    return True


def _parse_fast_iter_output(stdout):
    """Parse fast-iter output to extract per-pipeline results."""
    results = {}
    for line in stdout.split('\n'):
        line = line.strip()
        # Match lines like: "STANDARD        : 8/10 (80.0%) | 0 errors"
        for pipe in ["STANDARD", "GRAPH", "QUANTITATIVE", "ORCHESTRATOR", "OVERALL"]:
            if pipe in line and ":" in line and "%" in line:
                try:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        rest = parts[-1].strip()
                        # Extract accuracy percentage
                        pct_start = rest.find("(")
                        pct_end = rest.find("%")
                        if pct_start >= 0 and pct_end > pct_start:
                            acc = float(rest[pct_start + 1:pct_end])
                            results[pipe.lower()] = acc
                except (ValueError, IndexError):
                    pass
    return results


def save_iteration_log(iteration_num, steps_completed, gate_result, label=""):
    """Save a structured log of this iteration."""
    log_path = os.path.join(LOGS_DIR, "agentic-iterations.jsonl")
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "iteration": iteration_num,
        "label": label,
        "steps_completed": steps_completed,
        "gate_result": gate_result,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agentic Iteration Loop")
    parser.add_argument("--skip-deploy", action="store_true",
                        help="Skip workflow deployment step")
    parser.add_argument("--full-eval", action="store_true",
                        help="Run full 200q eval if fast-iter passes")
    parser.add_argument("--push", action="store_true",
                        help="Git push results after each iteration")
    parser.add_argument("--max-iterations", type=int, default=1,
                        help="Max number of iterations to run (default: 1)")
    parser.add_argument("--label", type=str, default="",
                        help="Label for this iteration")
    parser.add_argument("--fast-questions", type=int, default=10,
                        help="Questions per pipeline in fast-iter (default: 10)")
    parser.add_argument("--phase", type=int, default=1,
                        help="Phase to check gates for (default: 1)")
    parser.add_argument("--strict", action="store_true",
                        help="Include stability requirement in gate check")
    parser.add_argument("--phase2-transition", action="store_true",
                        help="Run Phase 2 transition after gates pass")
    args = parser.parse_args()

    print("=" * 70)
    print("  AGENTIC ITERATION LOOP")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"  Max iterations: {args.max_iterations}")
    print(f"  Phase: {args.phase}")
    print(f"  Full eval: {args.full_eval}")
    print(f"  Push: {args.push}")
    if args.label:
        print(f"  Label: {args.label}")
    print("=" * 70)

    # Pre-flight checks
    if not check_env_vars():
        print("\n  ABORT: Missing required environment variables.")
        print("  Set them with: export N8N_HOST=... N8N_API_KEY=... etc.")
        sys.exit(2)

    for iteration in range(1, args.max_iterations + 1):
        print(f"\n{'='*70}")
        print(f"  ITERATION {iteration}/{args.max_iterations}")
        print(f"{'='*70}")

        iter_label = f"{args.label} (iter {iteration})" if args.label else f"Agentic iter {iteration}"
        steps_completed = []

        # Step 1: Deploy patches
        if not args.skip_deploy and iteration == 1:
            step_deploy()
            steps_completed.append("deploy")
        elif args.skip_deploy:
            log("Skipping deployment (--skip-deploy)")

        # Step 2: Fast iteration
        success, fast_results = step_fast_iter(
            label=iter_label, questions=args.fast_questions
        )
        steps_completed.append("fast_iter")

        if not success:
            log("Fast iteration failed — stopping this iteration", "ERROR")
            save_iteration_log(iteration, steps_completed, None, iter_label)
            continue

        # Step 3: Analyze
        analysis = step_analyze()
        steps_completed.append("analyze")

        # Check for severe regressions
        regressions = analysis.get("regressions", {}).get("regressions", [])
        if len(regressions) >= 5:
            log(f"SEVERE: {len(regressions)} regressions detected — stopping", "ERROR")
            save_iteration_log(iteration, steps_completed, {"severe_regression": True}, iter_label)
            break

        # Step 4: Gate check (preliminary, on fast-iter data)
        gate_result = step_gate_check(phase=args.phase, strict=args.strict)
        steps_completed.append("gate_check")

        # Step 5: Full eval if fast-iter looks good and requested
        if args.full_eval:
            # Only run full eval if fast-iter accuracy is reasonable (>60%)
            overall_fast = fast_results.get("overall", 0)
            if overall_fast >= 55 or not fast_results:
                step_full_eval(label=iter_label, reset=True)
                steps_completed.append("full_eval")

                # Re-check gates after full eval
                gate_result = step_gate_check(phase=args.phase, strict=args.strict)
                steps_completed.append("gate_check_post_full")
            else:
                log(f"Fast-iter accuracy too low ({overall_fast}%) — skipping full eval", "WARN")

        # Step 6: Commit and push
        commit_msg = (
            f"agentic: {iter_label} | "
            f"gate={'PASS' if gate_result.get('passed') else 'FAIL'} | "
            f"overall={gate_result.get('overall_accuracy', '?')}%"
        )
        step_commit_push(message=commit_msg, push=args.push)
        steps_completed.append("commit")

        # Save iteration log
        save_iteration_log(iteration, steps_completed, gate_result, iter_label)

        # Check if gates passed
        if gate_result.get("passed"):
            print(f"\n{'='*70}")
            print(f"  PHASE {args.phase} GATES PASSED!")
            print(f"{'='*70}")

            if args.phase2_transition:
                log("Starting Phase 2 transition...")
                transition_script = os.path.join(EVAL_DIR, "phase2-transition.py")
                if os.path.exists(transition_script):
                    run_script(transition_script, ["--auto"], timeout_min=5)
                else:
                    log("phase2-transition.py not found", "WARN")

            break
        else:
            # Print what needs fixing
            priorities = gate_result.get("priorities", [])
            if priorities:
                log(f"Top priority: {priorities[0]['name']} "
                    f"({priorities[0]['current']} → {priorities[0]['target']})")

            if iteration < args.max_iterations:
                log(f"Gates not met — will run iteration {iteration + 1}")
                # Small delay between iterations
                time.sleep(5)

    # Final summary
    print(f"\n{'='*70}")
    print(f"  AGENTIC LOOP COMPLETE")
    print(f"  Iterations run: {min(iteration, args.max_iterations)}")
    print(f"  Final gate status: {'PASSED' if gate_result.get('passed') else 'NOT MET'}")
    print(f"  Overall accuracy: {gate_result.get('overall_accuracy', '?')}%")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
