#!/usr/bin/env python3
"""V2 Karpathy Engine — The closed-loop improvement core.

The fundamental problem with V1 agents:
  - amelioration PROPOSES but never EXECUTES
  - test_eval DETECTS but never FIXES
  - repo-improver CHANGES but never MEASURES before/after
  - No agent closes the loop

V2 closes the loop:
  MEASURE → FIND WEAKEST → PLAN → EXECUTE → RE-MEASURE → KEEP/REVERT → LEARN

This is THE Karpathy loop applied to software:
  "The most important thing is to have a tight eval loop."
  — Andrej Karpathy

Combined with 7 Enterprise Categories:
  Every repo is scored on ALL 7 dimensions.
  The weakest dimension gets improved first.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add parent for base imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from base import load_env, llm_call, telegram_notify, log_event, http_get, http_post, ctx

# ─── 7 Enterprise Categories ───────────────────────────────────────────────

CATEGORIES = [
    "strategie",      # Roadmap, positioning, goals clarity
    "produit",        # Product quality, UX, reliability, uptime
    "business",       # Revenue, costs, growth, unit economics
    "communication",  # Docs, content, social, messaging clarity
    "admin",          # Infra health, credentials, security, compliance
    "test_eval",      # Test coverage, accuracy, regression guards
    "amelioration",   # Improvement velocity, tech debt, performance trends
]

# ─── Data Structures ───────────────────────────────────────────────────────

class Score:
    __slots__ = ("category", "value", "target", "gap", "details")

    def __init__(self, category: str, value: float, target: float, details: dict = None):
        self.category = category
        self.value = min(value, 100.0)
        self.target = target
        self.gap = max(target - self.value, 0.0)
        self.details = details or {}

    def __repr__(self):
        return f"{self.category}: {self.value:.0f}/{self.target:.0f} (gap={self.gap:.0f})"

    def to_dict(self):
        return {"category": self.category, "value": self.value, "target": self.target,
                "gap": self.gap, "details": self.details}


class CycleResult:
    __slots__ = ("repo", "status", "category", "before", "after", "delta",
                 "hypothesis", "all_scores", "duration", "timestamp")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {k: getattr(self, k, None) for k in self.__slots__}


# ─── Learning Memory ───────────────────────────────────────────────────────

class Memory:
    """JSONL-backed learning: what worked, what didn't, per repo × category."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, repo: str, category: str, hypothesis: str,
               success: bool, delta: float, details: str = ""):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "repo": repo, "category": category,
            "hypothesis": hypothesis[:300],
            "success": success, "delta": round(delta, 1),
            "details": details[:200],
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_history(self, repo: str = None, category: str = None,
                    success: bool = None, limit: int = 10) -> list:
        if not self.path.exists():
            return []
        entries = []
        for line in self.path.read_text().splitlines():
            try:
                e = json.loads(line)
                if repo and e.get("repo") != repo:
                    continue
                if category and e.get("category") != category:
                    continue
                if success is not None and e.get("success") != success:
                    continue
                entries.append(e)
            except Exception:
                pass
        return entries[-limit:]

    def success_rate(self, repo: str = None, limit: int = 20) -> float:
        history = self.get_history(repo=repo, limit=limit)
        if not history:
            return 0.0
        return sum(1 for h in history if h["success"]) / len(history)


# ─── Git Operations ────────────────────────────────────────────────────────

def git_head(repo_path: str) -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"],
                       capture_output=True, text=True, cwd=repo_path)
    return r.stdout.strip()


def git_has_changes(repo_path: str) -> bool:
    r = subprocess.run(["git", "status", "--porcelain"],
                       capture_output=True, text=True, cwd=repo_path)
    return bool(r.stdout.strip())


def git_revert(repo_path: str, to_hash: str):
    """Safely revert to a known state."""
    if git_has_changes(repo_path):
        subprocess.run(["git", "checkout", "."], cwd=repo_path,
                       capture_output=True)
        subprocess.run(["git", "clean", "-fd"], cwd=repo_path,
                       capture_output=True)


def git_commit_push(repo_path: str, message: str) -> bool:
    """Stage all, commit, push. Returns True if pushed."""
    subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True)
    r = subprocess.run(
        ["git", "commit", "-m",
         f"{message}\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"],
        cwd=repo_path, capture_output=True)
    if r.returncode != 0:
        return False
    push = subprocess.run(["git", "push", "origin", "main"],
                          cwd=repo_path, capture_output=True, text=True)
    return push.returncode == 0


# ─── Claude Code Execution ─────────────────────────────────────────────────

def execute_claude(repo_path: str, prompt: str, timeout: int = 600) -> dict:
    """Run Claude Code CLI to make actual improvements.

    This is the execution engine: Claude reads code, plans changes,
    edits files, runs tests — just like a human developer.
    """
    try:
        r = subprocess.run(
            ["claude", "-p", "--dangerously-skip-permissions", prompt],
            capture_output=True, text=True, timeout=timeout, cwd=repo_path,
        )
        output = (r.stdout or "")[:2000]
        return {"ok": r.returncode == 0, "output": output,
                "has_changes": git_has_changes(repo_path)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "TIMEOUT", "has_changes": False}
    except Exception as e:
        return {"ok": False, "output": str(e), "has_changes": False}


# ─── The Karpathy Loop ─────────────────────────────────────────────────────

class KarpathyEngine:
    """The closed-loop improvement engine.

    For each repo:
      1. MEASURE all 7 categories → get scores
      2. FIND the category with the largest gap from target
      3. PLAN an improvement using LLM + learning history
      4. EXECUTE via Claude Code CLI
      5. RE-MEASURE the category
      6. KEEP if improved (commit+push), REVERT if not
      7. LEARN from the result

    This is Anthropic 2026 agent architecture:
      Plan → Act → Observe → Reflect → Repeat
    """

    def __init__(self, memory_path: str = None):
        if memory_path is None:
            memory_path = str(Path("/home/termius/mon-ipad/data/agents/v2/memory.jsonl"))
        self.memory = Memory(memory_path)
        self.max_retries = 2

    def run_cycle(self, repo_config: dict) -> CycleResult:
        """Run one full Karpathy cycle on a repo.

        repo_config = {
            "name": "rag-website",
            "path": "/home/termius/rag-website",
            "measure_fn": callable(repo_config) → list[Score],
            "goals": {"strategie": 80, "produit": 90, ...},
            "improve_context": "Next.js 15 chatbot site...",
        }
        """
        name = repo_config["name"]
        path = repo_config["path"]
        t0 = time.time()

        log(f"[{name}] ━━━ KARPATHY CYCLE START ━━━")

        # ── 1. MEASURE ──
        measure_fn = repo_config["measure_fn"]
        scores = measure_fn(repo_config)
        log(f"[{name}] Scores: {', '.join(str(s) for s in scores)}")

        # ── 2. FIND WEAKEST ──
        actionable = [s for s in scores if s.gap > 0]
        if not actionable:
            log(f"[{name}] All targets met!")
            return CycleResult(
                repo=name, status="all_targets_met", category=None,
                before=0, after=0, delta=0, hypothesis="",
                all_scores={s.category: s.value for s in scores},
                duration=round(time.time() - t0, 1))

        weakest = max(actionable, key=lambda s: s.gap)
        log(f"[{name}] Weakest: {weakest}")

        # ── 3. PLAN ──
        hypothesis = self._plan_improvement(repo_config, weakest)
        log(f"[{name}] Hypothesis: {hypothesis[:120]}...")

        # ── 4. EXECUTE ──
        snapshot = git_head(path)
        prompt = self._build_execution_prompt(repo_config, weakest, hypothesis)
        result = execute_claude(path, prompt)
        log(f"[{name}] Claude: ok={result['ok']}, changes={result['has_changes']}")

        if not result["has_changes"]:
            log(f"[{name}] No changes made, skipping verification")
            self.memory.record(name, weakest.category, hypothesis, False, 0,
                               "no_changes_made")
            return CycleResult(
                repo=name, status="no_changes", category=weakest.category,
                before=weakest.value, after=weakest.value, delta=0,
                hypothesis=hypothesis,
                all_scores={s.category: s.value for s in scores},
                duration=round(time.time() - t0, 1))

        # ── 5. RE-MEASURE ──
        new_scores = measure_fn(repo_config)
        new_weakest = next(
            (s for s in new_scores if s.category == weakest.category), None)
        new_value = new_weakest.value if new_weakest else weakest.value
        delta = new_value - weakest.value

        # ── 6. KEEP or REVERT ──
        if delta > 0:
            # Improved! Commit and push
            msg = (f"karpathy({weakest.category}): "
                   f"+{delta:.0f} ({weakest.value:.0f}→{new_value:.0f})")
            pushed = git_commit_push(path, msg)
            self.memory.record(name, weakest.category, hypothesis, True, delta,
                               result["output"][:200])
            log(f"[{name}] IMPROVED {weakest.category}: "
                f"{weakest.value:.0f} → {new_value:.0f} (+{delta:.0f}) "
                f"{'pushed' if pushed else 'commit only'}")
            status = "improved"

            telegram_notify(
                f"[KARPATHY] {name}/{weakest.category}\n"
                f"{weakest.value:.0f} → {new_value:.0f} (+{delta:.0f})\n"
                f"{hypothesis[:150]}", silent=True)
        elif delta == 0 and result["has_changes"]:
            # Changes made but no measurable improvement — keep if no regression
            # Check ALL categories didn't regress
            any_regression = False
            for old_s in scores:
                new_s = next((s for s in new_scores if s.category == old_s.category), None)
                if new_s and new_s.value < old_s.value - 5:
                    any_regression = True
                    break

            if not any_regression:
                msg = f"karpathy({weakest.category}): refactor (no regression)"
                pushed = git_commit_push(path, msg)
                self.memory.record(name, weakest.category, hypothesis, True, 0,
                                   "neutral_no_regression")
                log(f"[{name}] Neutral change kept (no regression)")
                status = "neutral_kept"
            else:
                git_revert(path, snapshot)
                self.memory.record(name, weakest.category, hypothesis, False, 0,
                                   "caused_regression")
                log(f"[{name}] REVERTED — caused regression in other category")
                status = "reverted_regression"
        else:
            # Worse! Revert
            git_revert(path, snapshot)
            self.memory.record(name, weakest.category, hypothesis, False, delta,
                               result["output"][:200])
            log(f"[{name}] REVERTED {weakest.category}: "
                f"{weakest.value:.0f} → {new_value:.0f} ({delta:.0f})")
            status = "reverted"

        # ── 7. LEARN ──
        all_scores = {s.category: s.value for s in new_scores}
        duration = round(time.time() - t0, 1)

        return CycleResult(
            repo=name, status=status, category=weakest.category,
            before=weakest.value, after=new_value, delta=delta,
            hypothesis=hypothesis, all_scores=all_scores, duration=duration)

    def _plan_improvement(self, repo_config: dict, weakest: Score) -> str:
        """Use LLM + learning history to generate improvement hypothesis."""
        name = repo_config["name"]
        cat = weakest.category

        successes = self.memory.get_history(name, cat, success=True, limit=5)
        failures = self.memory.get_history(name, cat, success=False, limit=5)

        context = repo_config.get("improve_context", "")
        cat_descriptions = {
            "strategie": "roadmap clarity, goal tracking, competitive positioning",
            "produit": "product quality, UX, reliability, uptime, features",
            "business": "revenue generation, cost efficiency, growth metrics",
            "communication": "documentation quality, content, messaging clarity",
            "admin": "infrastructure health, security, credentials, compliance",
            "test_eval": "test coverage, accuracy metrics, regression detection",
            "amelioration": "code quality, performance, tech debt reduction",
        }

        prompt = f"""Repo: {name} ({context})
Category: {cat} — {cat_descriptions.get(cat, cat)}
Current score: {weakest.value:.0f}/100 (target: {weakest.target:.0f})
Gap: {weakest.gap:.0f} points
Details: {json.dumps(weakest.details, ensure_ascii=False)[:500]}

{"PAST SUCCESSES (do more of this):" if successes else ""}
{chr(10).join(f"- {s['hypothesis'][:150]} (delta=+{s['delta']})" for s in successes) if successes else ""}

{"PAST FAILURES (avoid these):" if failures else ""}
{chr(10).join(f"- {f['hypothesis'][:150]}" for f in failures) if failures else ""}

Propose ONE concrete, surgical improvement that will increase the {cat} score.
Be specific: which file to edit, what to change, why it helps.
Reply in 1-2 sentences, no code."""

        response = llm_call(prompt,
                            system="Expert software engineer. Propose ONE precise improvement.",
                            max_tokens=300, temperature=0.4)
        if response.startswith("LLM_ERROR"):
            return f"Improve {cat} for {name}: fix the weakest aspect based on details"
        return response.strip()

    def _build_execution_prompt(self, repo_config: dict, weakest: Score,
                                hypothesis: str) -> str:
        """Build the prompt for Claude Code CLI execution."""
        name = repo_config["name"]
        cat = weakest.category

        return f"""You are improving the repository '{name}'.

TASK: {hypothesis}

CATEGORY: {cat} (score: {weakest.value:.0f}/{weakest.target:.0f})
DETAILS: {json.dumps(weakest.details, ensure_ascii=False)[:300]}

RULES:
1. Make exactly ONE focused change (1-3 files max)
2. The change must directly improve the '{cat}' dimension
3. Do NOT break existing functionality
4. Do NOT touch CLAUDE.md, .env files, or credentials
5. Edit under 50 lines total — surgical, not rewrite
6. No TODOs, no placeholders — commit-ready code only

Read the relevant files first, then make the change."""


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)
