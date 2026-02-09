#!/usr/bin/env python3
"""
TEAM-AGENTIC LOOP — Autonomous Phase 1 completion orchestrator.

Runs the full improvement cycle until Phase 1 gates pass:
  1. EVAL AGENT    — Run fast-iter (10q) or full eval (200q) in parallel
  2. ANALYZER AGENT — Analyze results, detect regressions
  3. GATE AGENT    — Check Phase 1 exit criteria
  4. IMPROVE AGENT — Select and apply the best next improvement
  5. DEPLOY AGENT  — Deploy workflow changes to n8n
  6. Loop → back to step 1

The loop exits when:
  - All Phase 1 gates pass (SUCCESS)
  - Max iterations reached (TIMEOUT)
  - No more improvements available (EXHAUSTED)
  - Critical regression detected (ABORT)

Architecture:
  ┌─────────────────────────────────────────────────────────┐
  │                    AGENT LOOP                           │
  │                                                         │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
  │  │ Standard │  │  Graph   │  │  Quant   │  ← Parallel │
  │  │  Eval    │  │  Eval    │  │  Eval    │    Eval      │
  │  │  Agent   │  │  Agent   │  │  Agent   │    Agents    │
  │  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
  │       └──────────────┼──────────────┘                   │
  │              ┌───────┴───────┐                          │
  │              │   Analyzer    │                          │
  │              │    Agent      │                          │
  │              └───────┬───────┘                          │
  │              ┌───────┴───────┐                          │
  │              │  Gate Check   │                          │
  │              │    Agent      │                          │
  │              └───────┬───────┘                          │
  │                      │                                  │
  │              Pass? ──┤── Yes → DONE ✓                   │
  │                      │ No                               │
  │              ┌───────┴───────┐                          │
  │              │   Improver    │                          │
  │              │    Agent      │                          │
  │              └───────┬───────┘                          │
  │                      │                                  │
  │              ┌───────┴───────┐                          │
  │              │   Validator   │                          │
  │              │    Agent      │                          │
  │              └───────────────┘                          │
  │                      │                                  │
  │                  Loop back                              │
  └─────────────────────────────────────────────────────────┘

Usage:
  # Full autonomous loop (fast-iter mode, 10q per pipeline)
  python agent-loop.py

  # With full 200q evals
  python agent-loop.py --full-eval

  # Limit iterations
  python agent-loop.py --max-iterations 5

  # Deploy improvements to n8n automatically
  python agent-loop.py --auto-deploy

  # Dry-run: show what would happen without running evals
  python agent-loop.py --dry-run

  # Resume from previous run
  python agent-loop.py --resume

  # Target specific pipeline only
  python agent-loop.py --pipeline graph
"""

import json
import os
import sys
import time
import subprocess
from datetime import datetime

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
LOOP_LOG_DIR = os.path.join(LOGS_DIR, "agent-loop")
os.makedirs(LOOP_LOG_DIR, exist_ok=True)

# Agent scripts
FAST_ITER = os.path.join(EVAL_DIR, "fast-iter.py")
FULL_EVAL = os.path.join(EVAL_DIR, "run-eval-parallel.py")
ANALYZER = os.path.join(EVAL_DIR, "analyzer.py")
PHASE_GATE = os.path.join(EVAL_DIR, "phase-gate.py")
AUTO_IMPROVE = os.path.join(EVAL_DIR, "auto-improve.py")
QUICK_TEST = os.path.join(EVAL_DIR, "quick-test.py")


class AgentLoop:
    """Orchestrates the team-agentic Phase 1 completion loop."""

    def __init__(self, max_iterations=10, full_eval=False, auto_deploy=False,
                 dry_run=False, pipeline=None, auto_push=False, questions=10):
        self.max_iterations = max_iterations
        self.full_eval = full_eval
        self.auto_deploy = auto_deploy
        self.dry_run = dry_run
        self.pipeline = pipeline
        self.auto_push = auto_push
        self.questions = questions

        self.start_time = datetime.utcnow()
        self.session_id = self.start_time.strftime("%Y-%m-%dT%H-%M-%S")
        self.log_file = os.path.join(LOOP_LOG_DIR, f"loop-{self.session_id}.json")
        self.iteration = 0
        self.history = []
        self.status = "starting"

    def log(self, msg, level="INFO"):
        """Print and log a message."""
        ts = datetime.utcnow().strftime("%H:%M:%S")
        prefix = {"INFO": "  ", "AGENT": ">>", "PASS": "OK", "FAIL": "!!", "WARN": "??"}
        print(f"  [{ts}] {prefix.get(level, '  ')} {msg}", flush=True)

    def run_script(self, script, args=None, timeout=600):
        """Run a Python script and return (returncode, stdout, stderr)."""
        cmd = [sys.executable, script] + (args or [])
        self.log(f"Running: {' '.join(os.path.basename(c) for c in cmd)}", "AGENT")

        if self.dry_run:
            self.log("  [DRY-RUN] Skipped", "WARN")
            return 0, "[dry-run]", ""

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=REPO_ROOT,
            )
            if result.stdout:
                # Print last few lines
                lines = result.stdout.strip().split("\n")
                for line in lines[-10:]:
                    self.log(f"  {line}")
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            self.log(f"  TIMEOUT after {timeout}s", "FAIL")
            return -1, "", "timeout"
        except Exception as e:
            self.log(f"  ERROR: {e}", "FAIL")
            return -1, "", str(e)

    def save_loop_state(self):
        """Save loop progress for resume capability."""
        state = {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat() + "Z",
            "current_iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "status": self.status,
            "history": self.history,
            "settings": {
                "full_eval": self.full_eval,
                "auto_deploy": self.auto_deploy,
                "pipeline": self.pipeline,
                "questions": self.questions,
            }
        }
        with open(self.log_file, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    # ── AGENT 1: EVALUATOR ──────────────────────────────────────────

    def run_eval_agent(self):
        """Run evaluation (fast-iter or full-eval)."""
        self.log("EVAL AGENT: Starting evaluation...", "AGENT")

        if self.full_eval:
            args = ["--reset", "--label", f"Agent loop iter {self.iteration}"]
            if self.pipeline:
                args += ["--types", self.pipeline]
            rc, stdout, stderr = self.run_script(FULL_EVAL, args, timeout=1800)
        else:
            args = ["--questions", str(self.questions),
                    "--label", f"Agent loop iter {self.iteration}"]
            if self.pipeline:
                args += ["--pipelines", self.pipeline]
            rc, stdout, stderr = self.run_script(FAST_ITER, args, timeout=600)

        success = rc == 0
        self.log(f"EVAL AGENT: {'SUCCESS' if success else 'FAILED'}", "PASS" if success else "FAIL")
        return {"success": success, "output": stdout[-1000:] if stdout else stderr[-500:]}

    # ── AGENT 2: ANALYZER ───────────────────────────────────────────

    def run_analyzer_agent(self):
        """Analyze results and detect regressions."""
        self.log("ANALYZER AGENT: Analyzing results...", "AGENT")
        rc, stdout, stderr = self.run_script(ANALYZER, ["--json"], timeout=30)

        if rc == 0 and stdout.strip():
            try:
                analysis = json.loads(stdout)
                reg_count = len(analysis.get("regressions", {}).get("regressions", []))
                fix_count = len(analysis.get("regressions", {}).get("fixes", []))
                suggestions = analysis.get("suggestions", [])
                high_priority = [s for s in suggestions if s["priority"] == "HIGH"]

                self.log(f"  Regressions: {reg_count}, Fixes: {fix_count}, "
                         f"Suggestions: {len(high_priority)} HIGH / {len(suggestions)} total")

                return {
                    "success": True,
                    "analysis": analysis,
                    "regressions": reg_count,
                    "fixes": fix_count,
                    "critical_regression": reg_count >= 5,
                }
            except json.JSONDecodeError:
                pass

        self.log("ANALYZER AGENT: Could not parse analysis", "WARN")
        return {"success": False, "analysis": None, "regressions": 0, "critical_regression": False}

    # ── AGENT 3: GATE CHECKER ───────────────────────────────────────

    def run_gate_agent(self):
        """Check Phase 1 exit criteria."""
        self.log("GATE AGENT: Checking Phase 1 exit criteria...", "AGENT")
        rc, stdout, stderr = self.run_script(PHASE_GATE, ["--json"], timeout=15)

        if rc == 0 and stdout.strip():
            try:
                report = json.loads(stdout)
                passed = report.get("gates_passed", 0)
                total = report.get("gates_total", 0)
                complete = report.get("phase1_complete", False)

                self.log(f"  Gates: {passed}/{total} passed", "PASS" if complete else "FAIL")

                # Show per-pipeline status
                for name, gate in report.get("pipelines", {}).items():
                    icon = "OK" if gate["passed"] else "!!"
                    self.log(f"  [{icon}] {name}: {gate['current']}% / {gate['target']}%")

                return {
                    "success": True,
                    "report": report,
                    "all_pass": complete,
                    "gates_passed": passed,
                    "gates_total": total,
                }
            except json.JSONDecodeError:
                pass

        return {"success": False, "all_pass": False}

    # ── AGENT 4: IMPROVER ───────────────────────────────────────────

    def run_improve_agent(self):
        """Select and apply the best next improvement."""
        self.log("IMPROVE AGENT: Selecting next improvement...", "AGENT")

        # First, get recommendation
        args = ["--json"]
        if self.pipeline:
            args += ["--pipeline", self.pipeline]
        rc, stdout, stderr = self.run_script(AUTO_IMPROVE, args, timeout=30)

        if rc == 0 and stdout.strip():
            try:
                rec = json.loads(stdout)
                next_imp = rec.get("next")
                if not next_imp:
                    self.log("  No more improvements available", "WARN")
                    return {"success": False, "reason": "exhausted"}

                self.log(f"  Selected: [{next_imp['priority']}] {next_imp['id']} "
                         f"— {next_imp['title']} (+{next_imp['expected_impact_pp']}pp)")

                # Apply it
                apply_args = ["--apply"]
                if self.auto_deploy:
                    apply_args.append("--deploy")
                if self.pipeline:
                    apply_args += ["--pipeline", self.pipeline]

                rc2, stdout2, stderr2 = self.run_script(AUTO_IMPROVE, apply_args, timeout=120)

                if rc2 == 0:
                    self.log(f"  Applied: {next_imp['id']}", "PASS")
                    return {"success": True, "improvement": next_imp}
                else:
                    self.log(f"  Failed to apply: {stderr2[:200]}", "FAIL")
                    return {"success": False, "reason": "apply_failed"}

            except json.JSONDecodeError:
                pass

        self.log("  Could not select improvement", "WARN")
        return {"success": False, "reason": "selection_failed"}

    # ── AGENT 5: VALIDATOR ──────────────────────────────────────────

    def run_validator_agent(self):
        """Quick smoke test to validate no critical regression after improvement."""
        self.log("VALIDATOR AGENT: Running smoke test...", "AGENT")

        args = ["--questions", "3"]
        if self.pipeline:
            args += ["--pipelines", self.pipeline]
        rc, stdout, stderr = self.run_script(QUICK_TEST, args, timeout=120)

        success = rc == 0
        self.log(f"  Smoke test: {'PASS' if success else 'FAIL'}", "PASS" if success else "FAIL")
        return {"success": success}

    # ── GIT AGENT ───────────────────────────────────────────────────

    def run_git_agent(self, message):
        """Commit and push results."""
        if not self.auto_push:
            return

        self.log("GIT AGENT: Committing results...", "AGENT")
        if self.dry_run:
            self.log("  [DRY-RUN] Skipped git operations", "WARN")
            return

        try:
            subprocess.run(
                ["git", "add", "docs/", "logs/", "eval/improvements.json"],
                cwd=REPO_ROOT, capture_output=True, timeout=15
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=REPO_ROOT, capture_output=True, timeout=15
            )
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=REPO_ROOT, capture_output=True, timeout=30
            )
            self.log("  Pushed to origin/main", "PASS")
        except Exception as e:
            self.log(f"  Git error: {e}", "WARN")

    # ── MAIN LOOP ───────────────────────────────────────────────────

    def run(self):
        """Execute the full agentic loop."""
        mode = "full-eval" if self.full_eval else f"fast-iter ({self.questions}q)"
        print("=" * 70)
        print("  TEAM-AGENTIC LOOP — Phase 1 Completion")
        print(f"  Session:   {self.session_id}")
        print(f"  Mode:      {mode}")
        print(f"  Max iters: {self.max_iterations}")
        print(f"  Deploy:    {'auto' if self.auto_deploy else 'manual'}")
        print(f"  Pipeline:  {self.pipeline or 'all'}")
        print(f"  Dry-run:   {self.dry_run}")
        print("=" * 70)

        self.status = "running"
        self.save_loop_state()

        for iteration in range(1, self.max_iterations + 1):
            self.iteration = iteration
            iter_start = datetime.utcnow()
            iter_record = {
                "iteration": iteration,
                "start": iter_start.isoformat() + "Z",
                "agents": {},
            }

            print(f"\n{'─' * 70}")
            print(f"  ITERATION {iteration}/{self.max_iterations}")
            print(f"{'─' * 70}")

            # ── Step 1: EVALUATE ──
            eval_result = self.run_eval_agent()
            iter_record["agents"]["eval"] = eval_result

            if not eval_result["success"]:
                self.log("Evaluation failed — skipping analysis", "WARN")
                self.history.append(iter_record)
                self.save_loop_state()
                continue

            # ── Step 2: ANALYZE ──
            analysis_result = self.run_analyzer_agent()
            iter_record["agents"]["analyzer"] = {
                k: v for k, v in analysis_result.items() if k != "analysis"
            }

            # Check for critical regression
            if analysis_result.get("critical_regression"):
                self.log("CRITICAL: Major regression detected — ABORTING", "FAIL")
                self.status = "aborted_regression"
                iter_record["outcome"] = "aborted_regression"
                self.history.append(iter_record)
                self.save_loop_state()
                break

            # ── Step 3: GATE CHECK ──
            gate_result = self.run_gate_agent()
            iter_record["agents"]["gate"] = {
                k: v for k, v in gate_result.items() if k != "report"
            }

            if gate_result.get("all_pass"):
                self.log("ALL PHASE 1 GATES PASSED!", "PASS")
                self.status = "phase1_complete"
                iter_record["outcome"] = "phase1_complete"
                self.history.append(iter_record)
                self.save_loop_state()

                self.run_git_agent(f"agent-loop: Phase 1 COMPLETE (iter {iteration})")

                print(f"\n{'=' * 70}")
                print("  PHASE 1 COMPLETE — All gates passed!")
                print(f"  Total iterations: {iteration}")
                elapsed = (datetime.utcnow() - self.start_time).total_seconds()
                print(f"  Total time: {int(elapsed)}s ({int(elapsed // 60)}m {int(elapsed % 60)}s)")
                print(f"  Log: {self.log_file}")
                print(f"{'=' * 70}")
                return True

            # ── Step 4: IMPROVE ──
            improve_result = self.run_improve_agent()
            iter_record["agents"]["improve"] = improve_result

            if not improve_result["success"]:
                reason = improve_result.get("reason", "unknown")
                if reason == "exhausted":
                    self.log("All improvements exhausted — manual intervention needed", "WARN")
                    self.status = "improvements_exhausted"
                    iter_record["outcome"] = "improvements_exhausted"
                    self.history.append(iter_record)
                    self.save_loop_state()
                    break
                else:
                    self.log(f"Improvement failed ({reason}) — continuing to next iteration", "WARN")

            # ── Step 5: VALIDATE ──
            if improve_result["success"]:
                validate_result = self.run_validator_agent()
                iter_record["agents"]["validator"] = validate_result

                if not validate_result["success"]:
                    self.log("Validation failed — improvement may have caused regression", "WARN")
                    # Don't abort, next eval iteration will catch it

            # ── Step 6: GIT ──
            imp_name = improve_result.get("improvement", {}).get("id", "unknown")
            self.run_git_agent(
                f"agent-loop iter {iteration}: {imp_name} "
                f"(gates {gate_result.get('gates_passed', '?')}/{gate_result.get('gates_total', '?')})"
            )

            iter_record["outcome"] = "continue"
            iter_record["elapsed_s"] = int((datetime.utcnow() - iter_start).total_seconds())
            self.history.append(iter_record)
            self.save_loop_state()

        else:
            self.status = "max_iterations_reached"
            self.log(f"Max iterations ({self.max_iterations}) reached", "WARN")

        # Final summary
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        print(f"\n{'=' * 70}")
        print(f"  AGENT LOOP FINISHED — Status: {self.status.upper()}")
        print(f"  Iterations: {self.iteration}/{self.max_iterations}")
        print(f"  Total time: {int(elapsed)}s ({int(elapsed // 60)}m {int(elapsed % 60)}s)")
        print(f"  Log: {self.log_file}")
        print(f"{'=' * 70}")

        self.save_loop_state()
        return self.status == "phase1_complete"


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Team-Agentic Loop — Autonomous Phase 1 completion"
    )
    parser.add_argument("--max-iterations", type=int, default=10,
                        help="Maximum loop iterations (default: 10)")
    parser.add_argument("--full-eval", action="store_true",
                        help="Run full 200q eval instead of fast-iter")
    parser.add_argument("--auto-deploy", action="store_true",
                        help="Auto-deploy improvements to n8n")
    parser.add_argument("--auto-push", action="store_true",
                        help="Auto git push after each iteration")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without running evals")
    parser.add_argument("--pipeline", type=str, default=None,
                        help="Target a specific pipeline only")
    parser.add_argument("--questions", type=int, default=10,
                        help="Questions per pipeline in fast-iter mode (default: 10)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from the latest loop session")
    args = parser.parse_args()

    loop = AgentLoop(
        max_iterations=args.max_iterations,
        full_eval=args.full_eval,
        auto_deploy=args.auto_deploy,
        dry_run=args.dry_run,
        pipeline=args.pipeline,
        auto_push=args.auto_push,
        questions=args.questions,
    )

    success = loop.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
