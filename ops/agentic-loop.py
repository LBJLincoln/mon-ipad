#!/usr/bin/env python3
"""
Agentic Loop — Master Continuous Improvement Orchestrator
==========================================================
The most important script in the Nomos Sector AI Expert project.

Ties together ALL existing tools (eval, metrics, judge, discovery, ingestion)
into a single autonomous 7-phase improvement loop:

  Phase 1: STRATEGIZE — Analyze state, pick highest-impact priority via LLM
  Phase 2: PLAN       — Create detailed action plan for the priority
  Phase 3: BUILD      — Execute the plan (ingest, deploy, modify)
  Phase 4: OBSERVE    — Run targeted eval on the weak area (measure impact)
  Phase 5: COLLECT    — Gather execution metrics + LLM judge scores
  Phase 6: ANALYZE    — Deep failure analysis, generate new test questions
  Phase 7: REPORT     — Structured report, delta tracking, next cycle prep

Each cycle moves the system closer to world-class sector expert accuracy.

Usage:
  source .env.local
  python3 ops/agentic-loop.py                     # Run one cycle
  python3 ops/agentic-loop.py --daemon 1800       # Continuous (every 30 min)
  python3 ops/agentic-loop.py --phase strategize  # Run single phase
  python3 ops/agentic-loop.py --phase analyze     # Run analysis only
  python3 ops/agentic-loop.py --report            # Show latest cycle report
  python3 ops/agentic-loop.py --history           # Show all cycle summaries
  python3 ops/agentic-loop.py --dry-run           # Plan without executing
"""

# ============================================================================
# IPv4 MONKEY-PATCH (must be FIRST — GCP VM has broken IPv6)
# ============================================================================
import socket
from socket import AF_INET

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(*args, **kwargs):
    results = _original_getaddrinfo(*args, **kwargs)
    return [r for r in results if r[0] == AF_INET] or results


socket.getaddrinfo = _ipv4_only_getaddrinfo

# ============================================================================
# IMPORTS
# ============================================================================
import argparse
import hashlib
import json
import os
import signal
import ssl
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

# ============================================================================
# CONFIGURATION
# ============================================================================
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

# Load .env.local
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _k = _k.strip()
                _v = _v.strip().strip('"').strip("'")
                if _k and _v:
                    os.environ.setdefault(_k, _v)

# LiteLLM proxy (S7)
LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")
LITELLM_MODEL = "smart"

# Groq direct fallback
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# SSL (permissive for HF Spaces)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# Data directories
DATA_DIR = os.path.join(REPO_ROOT, "data", "agentic-loop")
STRATEGY_LOG = os.path.join(DATA_DIR, "strategy-log.jsonl")
PLANS_DIR = os.path.join(DATA_DIR, "plans")
BASELINES_DIR = os.path.join(DATA_DIR, "baselines")
COLLECTED_DIR = os.path.join(DATA_DIR, "collected")
ANALYSES_DIR = os.path.join(DATA_DIR, "analyses")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
BUILDS_DIR = os.path.join(DATA_DIR, "builds")
CYCLE_SUMMARY_LOG = os.path.join(DATA_DIR, "cycle-summary.jsonl")
STATE_FILE = os.path.join(DATA_DIR, "loop-state.json")

# Eval data directories (written by other scripts)
EVAL_DIR = os.path.join(REPO_ROOT, "data", "eval")
METRICS_DIR = os.path.join(REPO_ROOT, "data", "metrics")

# Other script paths
PARALLEL_EVAL_SCRIPT = os.path.join(REPO_ROOT, "eval", "parallel-eval.py")
METRICS_COLLECTOR_SCRIPT = os.path.join(REPO_ROOT, "ops", "metrics-collector.py")
CONTINUOUS_JUDGE_SCRIPT = os.path.join(REPO_ROOT, "eval", "continuous-judge.py")
EXPERT_DISCOVERY_SCRIPT = os.path.join(REPO_ROOT, "eval", "expert-discovery.py")
MASS_QUESTION_SCRIPT = os.path.join(REPO_ROOT, "eval", "mass-question-generator.py")
STAGING_DEPLOY_SCRIPT = os.path.join(REPO_ROOT, "ops", "staging-deploy.py")
FAST_INGEST_SCRIPT = os.path.join(REPO_ROOT, "ops", "fast-ingest.py")
DOCLING_CRON_SCRIPT = os.path.join(REPO_ROOT, "codespace", "docling-cron.py")
DOCLING_S6_SCRIPT = os.path.join(REPO_ROOT, "ops", "docling-s6-ingest.py")
INFRA_TEST_SCRIPT = os.path.join(REPO_ROOT, "ops", "infra-test.py")

# Sectors and pipelines
SECTORS = ["finance", "btp", "juridique", "industrie"]
PIPELINES = ["standard", "graph", "quantitative", "orchestrator"]

# Accuracy targets (from CLAUDE.md)
TARGETS = {
    "finance":   {"standard": 90, "graph": 75, "quantitative": 95, "orchestrator": 85},
    "btp":       {"standard": 85, "graph": 70, "quantitative": 80, "orchestrator": 75},
    "juridique": {"standard": 90, "graph": 80, "quantitative": 0,  "orchestrator": 80},
    "industrie": {"standard": 85, "graph": 70, "quantitative": 80, "orchestrator": 75},
}

# HF Space URLs for BUILD phase (staging = S9)
STAGING_SPACE = "lbjlincoln-nomos-rag-engine-9.hf.space"
PRODUCTION_SPACES = [
    "lbjlincoln-nomos-rag-engine.hf.space",      # S1
    "lbjlincoln26-nomos-rag-engine-2.hf.space",   # S2
    "lbjlincoln-nomos-rag-engine-3.hf.space",     # S3
    "lbjlincoln26-nomos-rag-engine-4.hf.space",   # S4
    "lbjlincoln-nomos-rag-engine-5.hf.space",     # S5
]
DOCLING_API_URL = "https://lbjlincoln-nomos-docling-api.hf.space"

# Pinecone E5 integrated inference
PINECONE_E5_HOST = os.environ.get("PINECONE_E5_HOST", "")
PINECONE_E5_KEY = os.environ.get("PINECONE_API_KEY", "")

# Webhook paths for smoke testing on staging
WEBHOOK_PATHS = {
    "standard": "/webhook/rag-multi-index-v3",
    "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

# Max consecutive failures before stopping (high to allow continuous operation)
MAX_CONSECUTIVE_FAILURES = 10

# Graceful shutdown
_shutdown_requested = False
_log_lock = Lock()


def _handle_signal(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    log("Shutdown requested (Ctrl+C). Finishing current phase...", "WARN")


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ============================================================================
# ANSI COLORS
# ============================================================================
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    MAGENTA = "\033[95m"


# ============================================================================
# LOGGING
# ============================================================================
def log(msg, level="INFO"):
    """Thread-safe timestamped logging."""
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix_map = {
        "INFO": f"{C.BLUE}[*]{C.RESET}",
        "OK":   f"{C.GREEN}[+]{C.RESET}",
        "WARN": f"{C.YELLOW}[!]{C.RESET}",
        "ERROR": f"{C.RED}[X]{C.RESET}",
        "PHASE": f"{C.MAGENTA}[>]{C.RESET}",
        "STRAT": f"{C.CYAN}[S]{C.RESET}",
    }
    prefix = prefix_map.get(level, "[?]")
    with _log_lock:
        print(f" {C.DIM}{ts}{C.RESET} {prefix} {msg}", flush=True)


def log_jsonl(filepath, entry):
    """Append a JSON entry to a JSONL file (thread-safe)."""
    entry["_logged_at"] = datetime.now(timezone.utc).isoformat()
    with _log_lock:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            log(f"Failed to write JSONL {filepath}: {e}", "WARN")


# ============================================================================
# DIRECTORY SETUP
# ============================================================================
def ensure_directories():
    """Create all data directories on first run."""
    for d in [DATA_DIR, PLANS_DIR, BASELINES_DIR, BUILDS_DIR, COLLECTED_DIR, ANALYSES_DIR, REPORTS_DIR]:
        os.makedirs(d, exist_ok=True)


# ============================================================================
# STATE MANAGEMENT
# ============================================================================
def load_state():
    """Load loop state (cycle number, last results, consecutive failures)."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "cycle": 0,
        "last_cycle_at": None,
        "last_priority": None,
        "last_scores": {},
        "consecutive_no_improvement": 0,
        "total_improvements": 0,
        "total_regressions": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def save_state(state):
    """Persist loop state atomically."""
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, STATE_FILE)


# ============================================================================
# HTTP HELPERS
# ============================================================================
def http_request(url, method="GET", data=None, headers=None, timeout=60):
    """Make HTTP request. Returns (status_code, response_body)."""
    if headers is None:
        headers = {}
    headers.setdefault("Content-Type", "application/json")

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout)
        return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            pass
        return e.code, err_body
    except Exception as e:
        return 0, str(e)


def llm_call(prompt, system_prompt=None, max_tokens=2000, temperature=0.3):
    """Call LLM via LiteLLM proxy (S7) with Groq direct fallback.

    Returns the assistant message content string, or None on failure.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Attempt 1: LiteLLM proxy
    status, body = http_request(
        LITELLM_URL,
        method="POST",
        data={
            "model": LITELLM_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LITELLM_KEY}",
        },
        timeout=90,
    )

    if status == 200:
        try:
            resp = json.loads(body)
            content = resp["choices"][0]["message"]["content"]
            return content
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            log(f"LiteLLM parse error: {e}", "WARN")

    # Attempt 2: Groq direct fallback
    if GROQ_API_KEY:
        log("LiteLLM failed, falling back to Groq direct...", "WARN")
        status2, body2 = http_request(
            GROQ_URL,
            method="POST",
            data={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            timeout=90,
        )

        if status2 == 200:
            try:
                resp2 = json.loads(body2)
                return resp2["choices"][0]["message"]["content"]
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                log(f"Groq parse error: {e}", "WARN")
        else:
            log(f"Groq direct also failed: HTTP {status2}", "ERROR")

    log(f"All LLM backends failed (LiteLLM: {status}, body: {body[:200]})", "ERROR")
    return None


def extract_json_from_llm(text):
    """Extract the first JSON object from LLM response text.

    Handles markdown code blocks, preamble text, and trailing text.
    """
    if not text:
        return None

    # Try direct parse first
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try to extract from markdown code block
    import re
    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try to find first { ... } block
    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break

    return None


# ============================================================================
# DATA READERS — Read outputs from other scripts
# ============================================================================
def read_latest_eval_results():
    """Read the latest parallel-eval results."""
    latest = os.path.join(EVAL_DIR, "parallel-eval-latest.json")
    if os.path.exists(latest):
        try:
            with open(latest) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def read_sector_scores():
    """Read expert-eval sector scores (LLM-judge based)."""
    path = os.path.join(EVAL_DIR, "sector-scores.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def read_improvement_targets():
    """Read the improvement-targets.json (weak questions + gaps)."""
    path = os.path.join(EVAL_DIR, "improvement-targets.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def read_execution_board():
    """Read the continuous-judge execution board (top/bottom per pipeline)."""
    path = os.path.join(EVAL_DIR, "execution-board.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def read_improvement_suggestions():
    """Read the continuous-judge improvement suggestions."""
    path = os.path.join(EVAL_DIR, "improvement-suggestions.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def read_score_history():
    """Read the score history for trend analysis."""
    path = os.path.join(EVAL_DIR, "score-history.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def read_metrics():
    """Read the latest metrics from the metrics collector."""
    results = {}
    for name in ["execution_log.json", "node_performance.json",
                  "error_catalog.json", "regression_tracker.json",
                  "analysis_report.json"]:
        path = os.path.join(METRICS_DIR, name)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    results[name.replace(".json", "")] = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
    return results


def read_error_library():
    """Read the error library from error-analyzer."""
    path = os.path.join(REPO_ROOT, "data", "error-library.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def read_debug_playbook(max_chars=4000):
    """Read the DEBUG-PLAYBOOK.md fix library (90+ documented fixes).

    This is the SINGLE SOURCE OF TRUTH for debugging pipelines.
    Returns a condensed version focusing on fix entries and diagnostic trees.
    """
    path = os.path.join(REPO_ROOT, "technicals", "DEBUG-PLAYBOOK.md")
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r") as f:
            content = f.read()

        # Extract the most useful sections for the LLM:
        # 1. Quick Diagnostic Flowcharts (section 1)
        # 2. Fixes Library entries (FIX-XX patterns)
        # 3. Recurring Patterns (section 5)
        import re

        fixes = []
        # Extract all FIX-XX entries
        for match in re.finditer(r'(FIX-\d+[^#]*?)(?=\n## |\nFIX-|\n---|\Z)', content, re.DOTALL):
            fix_text = match.group(1).strip()
            if len(fix_text) > 20:
                # Truncate each fix to 200 chars for context window efficiency
                fixes.append(fix_text[:200])

        # Extract diagnostic trees (indented code blocks)
        diag_trees = []
        for match in re.finditer(r'```\n(.*?)```', content, re.DOTALL):
            tree = match.group(1).strip()
            if len(tree) > 30 and ("YES" in tree or "NO" in tree or "→" in tree):
                diag_trees.append(tree[:300])

        # Extract recurring patterns (section 5)
        patterns = []
        for match in re.finditer(r'### (5\.\d+.*?)\n(.*?)(?=\n### |\n## |\Z)', content, re.DOTALL):
            patterns.append(f"{match.group(1)}: {match.group(2)[:150]}")

        result = {
            "total_fixes": len(fixes),
            "diagnostic_trees": diag_trees[:3],  # Top 3 trees
            "fixes_summary": fixes[:30],  # Top 30 fixes
            "patterns": patterns[:10],  # Top 10 patterns
        }

        # Compact to fit max_chars
        result_str = json.dumps(result, ensure_ascii=False)
        if len(result_str) > max_chars:
            result["fixes_summary"] = fixes[:15]
            result["patterns"] = patterns[:5]

        return result
    except Exception:
        return None


# ============================================================================
# SUBPROCESS RUNNER — Calls other scripts safely
# ============================================================================
def run_script(script_path, args=None, timeout_s=600, capture=True):
    """Run a Python script as subprocess.

    Returns (return_code, stdout, stderr) if capture=True,
    or (return_code, None, None) if capture=False.
    """
    if not os.path.exists(script_path):
        log(f"Script not found: {script_path}", "ERROR")
        return (1, "", f"Script not found: {script_path}")

    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)

    log(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout_s,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        if capture:
            return (result.returncode, result.stdout or "", result.stderr or "")
        return (result.returncode, None, None)
    except subprocess.TimeoutExpired:
        log(f"Script timed out after {timeout_s}s: {script_path}", "ERROR")
        return (124, "", f"Timeout after {timeout_s}s")
    except Exception as e:
        log(f"Failed to run script: {e}", "ERROR")
        return (1, "", str(e))


# ============================================================================
# BUILD SYSTEM CONTEXT — Summarize current state for LLM prompts
# ============================================================================
def build_system_context():
    """Build a structured summary of the current system state for LLM prompts."""
    ctx = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sectors": SECTORS,
        "pipelines": PIPELINES,
        "targets": TARGETS,
        "eval_results": {},
        "sector_scores": {},
        "improvement_targets": None,
        "execution_board_summary": None,
        "suggestions": None,
        "error_patterns": None,
        "metrics_summary": None,
        "score_history": None,
        "pipeline_health": None,
    }

    # Latest parallel-eval results
    eval_results = read_latest_eval_results()
    if eval_results:
        ctx["eval_results"] = {
            "timestamp": eval_results.get("timestamp"),
            "avg_score": eval_results.get("avg_score"),
            "pass_rate": eval_results.get("pass_rate"),
            "by_pipeline": eval_results.get("by_pipeline", {}),
            "by_sector": eval_results.get("by_sector", {}),
            "matrix": eval_results.get("matrix", {}),
        }

    # LLM-judge sector scores
    sector_scores = read_sector_scores()
    if sector_scores:
        ctx["sector_scores"] = sector_scores.get("sectors", {})

    # Improvement targets (weak questions)
    targets = read_improvement_targets()
    if targets:
        ctx["improvement_targets"] = {
            "total_weak": targets.get("total_weak_questions", 0),
            "sector_summaries": targets.get("sector_summaries", {}),
            "sample_weak": targets.get("weak_questions", [])[:5],
        }

    # Execution board summary
    board = read_execution_board()
    if board:
        summary = {}
        for pipeline, data in board.items():
            if isinstance(data, dict):
                summary[pipeline] = {
                    "best_count": len(data.get("best", [])),
                    "worst_count": len(data.get("worst", [])),
                }
        ctx["execution_board_summary"] = summary

    # Improvement suggestions
    suggestions = read_improvement_suggestions()
    if suggestions:
        if isinstance(suggestions, list):
            ctx["suggestions"] = suggestions[:10]
        elif isinstance(suggestions, dict):
            ctx["suggestions"] = suggestions

    # Error patterns
    errors = read_error_library()
    if errors:
        if isinstance(errors, list):
            ctx["error_patterns"] = errors[:10]
        elif isinstance(errors, dict):
            ctx["error_patterns"] = {k: v for k, v in list(errors.items())[:10]}

    # Metrics summary
    metrics = read_metrics()
    if metrics:
        report = metrics.get("analysis_report")
        if report:
            ctx["metrics_summary"] = report
        else:
            # Summarize from execution log
            exec_log = metrics.get("execution_log")
            if exec_log and isinstance(exec_log, list):
                recent = exec_log[:50]
                statuses = defaultdict(int)
                for e in recent:
                    statuses[e.get("status", "unknown")] += 1
                durations = [e.get("duration_ms", 0) for e in recent if e.get("duration_ms", 0) > 0]
                ctx["metrics_summary"] = {
                    "recent_executions": len(recent),
                    "status_distribution": dict(statuses),
                    "avg_duration_ms": round(sum(durations) / len(durations)) if durations else 0,
                }

    # Score history for trends
    history = read_score_history()
    if history:
        ctx["score_history"] = history

    # DEBUG-PLAYBOOK fix library (90+ documented fixes — CRITICAL for diagnosis)
    playbook = read_debug_playbook()
    if playbook:
        ctx["debug_playbook"] = playbook

    return ctx


def format_context_for_prompt(ctx, max_chars=6000):
    """Format system context into a concise text block for LLM prompts."""
    lines = []
    lines.append("=== CURRENT SYSTEM STATE ===")
    lines.append(f"Timestamp: {ctx['timestamp']}")
    lines.append(f"Sectors: {', '.join(ctx['sectors'])}")
    lines.append(f"Pipelines: {', '.join(ctx['pipelines'])}")

    # Pipeline health (live smoke test results)
    ph = ctx.get("pipeline_health")
    if ph:
        lines.append(f"\n--- Pipeline Health (live smoke test) ---")
        for pname, pdata in sorted(ph.items()):
            status_str = "OK" if pdata.get("status") == "ok" else f"BROKEN ({pdata.get('error', '?')[:60]})"
            lines.append(f"  {pname}: {status_str} "
                         f"(latency={pdata.get('latency_s', '?')}s, "
                         f"response_len={pdata.get('response_length', 0)})")

    # Eval results
    er = ctx.get("eval_results", {})
    if er:
        lines.append(f"\n--- Parallel Eval (latest) ---")
        lines.append(f"Overall avg score: {er.get('avg_score', '?')}/100, pass rate: {er.get('pass_rate', '?')}%")
        lines.append(f"Last run: {er.get('timestamp', '?')}")
        by_sector = er.get("by_sector", {})
        if by_sector:
            lines.append("By sector:")
            for s, data in sorted(by_sector.items()):
                target_std = ctx["targets"].get(s, {}).get("standard", 0)
                lines.append(f"  {s}: avg={data.get('avg_score', '?')}/100, "
                             f"pass={data.get('pass_rate', '?')}% "
                             f"(target: {target_std}% standard)")
        by_pipeline = er.get("by_pipeline", {})
        if by_pipeline:
            lines.append("By pipeline:")
            for p, data in sorted(by_pipeline.items()):
                lines.append(f"  {p}: avg={data.get('avg_score', '?')}/100, "
                             f"pass={data.get('pass_rate', '?')}%, "
                             f"latency={data.get('avg_latency_s', '?')}s, "
                             f"keyword_hit={data.get('keyword_hit_rate', '?')}%")

    # LLM-judge sector scores
    ss = ctx.get("sector_scores", {})
    if ss:
        lines.append(f"\n--- LLM-Judge Sector Scores (1-5 scale) ---")
        for s, data in sorted(ss.items()):
            if isinstance(data, dict) and "scores" in data:
                scores = data["scores"]
                lines.append(f"  {s}: overall={scores.get('overall', '?')}, "
                             f"factual={scores.get('factual_accuracy', '?')}, "
                             f"sources={scores.get('source_citation', '?')}, "
                             f"terminology={scores.get('expert_terminology', '?')}")

    # Improvement targets
    it = ctx.get("improvement_targets")
    if it:
        lines.append(f"\n--- Weak Areas ---")
        lines.append(f"Total weak questions: {it.get('total_weak', 0)}")
        for s, data in (it.get("sector_summaries") or {}).items():
            lines.append(f"  {s}: {data.get('total_weak', 0)} weak "
                         f"(data_gaps={data.get('data_gaps', 0)}, "
                         f"retrieval_gaps={data.get('retrieval_gaps', 0)}, "
                         f"errors={data.get('errors', 0)})")
            if data.get("priority_action"):
                lines.append(f"    Action: {data['priority_action'][:120]}")

    # Suggestions
    sugg = ctx.get("suggestions")
    if sugg:
        lines.append(f"\n--- Improvement Suggestions ---")
        if isinstance(sugg, list):
            for s in sugg[:5]:
                if isinstance(s, dict):
                    lines.append(f"  - {s.get('suggestion', s.get('fix', str(s)[:100]))}")
                else:
                    lines.append(f"  - {str(s)[:100]}")

    # Error patterns
    ep = ctx.get("error_patterns")
    if ep:
        lines.append(f"\n--- Error Patterns ---")
        if isinstance(ep, list):
            for e in ep[:5]:
                if isinstance(e, dict):
                    lines.append(f"  - {e.get('pattern', e.get('error', str(e)[:100]))}: "
                                 f"count={e.get('count', '?')}")
        elif isinstance(ep, dict):
            for k, v in list(ep.items())[:5]:
                lines.append(f"  - {k}: {json.dumps(v, ensure_ascii=False)[:100]}")

    # Metrics summary
    ms = ctx.get("metrics_summary")
    if ms:
        lines.append(f"\n--- Pipeline Metrics ---")
        if isinstance(ms, dict):
            lines.append(f"  Recent executions: {ms.get('recent_executions', '?')}")
            lines.append(f"  Avg duration: {ms.get('avg_duration_ms', '?')}ms")
            sd = ms.get("status_distribution")
            if sd:
                lines.append(f"  Statuses: {json.dumps(sd)}")

    # DEBUG-PLAYBOOK fixes (user-documented, 90+ entries)
    playbook = ctx.get("debug_playbook")
    if playbook:
        lines.append(f"\n--- DEBUG-PLAYBOOK Fix Library ({playbook.get('total_fixes', 0)} fixes) ---")
        # Include diagnostic trees
        for i, tree in enumerate(playbook.get("diagnostic_trees", [])[:2]):
            lines.append(f"  Diagnostic Tree {i+1}:\n{tree[:200]}")
        # Include relevant fix summaries
        for fix in playbook.get("fixes_summary", [])[:10]:
            lines.append(f"  - {fix[:120]}")
        # Include patterns
        for pattern in playbook.get("patterns", [])[:5]:
            lines.append(f"  Pattern: {pattern[:120]}")

    # Targets
    lines.append(f"\n--- Accuracy Targets ---")
    for s in SECTORS:
        t = ctx["targets"].get(s, {})
        lines.append(f"  {s}: standard>={t.get('standard', 0)}%, "
                     f"graph>={t.get('graph', 0)}%, "
                     f"quant>={t.get('quantitative', 0)}%, "
                     f"orch>={t.get('orchestrator', 0)}%")

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text


# ============================================================================
# STRATEGIC SYSTEM PROMPT — Shared across all LLM calls
# ============================================================================
STRATEGIC_SYSTEM_PROMPT = """\
You are the strategic AI brain of the Nomos Sector AI Expert system.

MISSION: Build the BEST AI sector expert for 4 domains (Finance, BTP/Construction, \
Juridique/Legal, Industrie/Manufacturing) serving French and European enterprises \
(grands groupes and PMEs). They have massive document bases (IFRS, Eurocodes, Code civil, \
ISO norms) and need an AI that answers expert-level questions with perfect accuracy, \
proper professional terminology, and source citations.

ARCHITECTURE: 4 RAG pipelines (Standard, Graph, Quantitative, Orchestrator) running \
on 6 HF Spaces (n8n workflows), backed by Pinecone (58K+ E5 vectors), Supabase (43K+ docs), \
and Neo4j (70K+ entity nodes). LLM inference via Groq (llama-3.3-70b) free tier.

SCORING: Questions scored 0-100 via keyword matching + source presence + language match + \
terminology. Also scored 1-5 by LLM judge on factual_accuracy, source_citation, \
expert_terminology, completeness, and language_match.

KEY CONSTRAINTS:
- Groq free tier = rate limits (avoid concurrent heavy calls)
- HF Spaces = free tier (may sleep, 503s, cold starts)
- Changes go through n8n workflow nodes (JSON modifications)
- 1 fix per iteration (never multiple simultaneous changes)
- Must measure before/after (no change without measurement)

YOUR ROLE: Analyze data, prioritize improvements, create action plans. \
Always respond in the exact JSON format requested. Be specific and actionable. \
Focus on the SINGLE highest-impact improvement at each step."""


# ============================================================================
# PHASE 1: STRATEGIZE
# ============================================================================
def phase_strategize(ctx, state, dry_run=False):
    """Analyze current state and pick the highest-impact priority.

    Returns a strategy dict or None on failure.
    """
    log(f"{C.BOLD}{'=' * 70}{C.RESET}", "PHASE")
    log(f"{C.BOLD}PHASE 1: STRATEGIZE — Analyzing state, picking priority{C.RESET}", "PHASE")
    log(f"{'=' * 70}", "PHASE")

    # --- Pipeline health smoke test (detect broken pipelines) ---
    if not dry_run:
        log("Running pipeline health smoke tests on production...", "INFO")
        pipeline_health = _smoke_test_all_pipelines()
        ctx["pipeline_health"] = pipeline_health

        broken_pipelines = []
        for pname, pdata in pipeline_health.items():
            status_icon = "OK" if pdata["status"] == "ok" else "BROKEN"
            latency_str = f"{pdata['latency_s']}s" if pdata.get("latency_s") else "?"
            log(f"  {pname}: {status_icon} (latency={latency_str}, len={pdata.get('response_length', 0)})",
                "OK" if pdata["status"] == "ok" else "ERROR")
            if pdata["status"] != "ok":
                broken_pipelines.append(pname)

        if broken_pipelines:
            log(f"BROKEN pipelines detected: {', '.join(broken_pipelines)} — will prioritize fixing", "WARN")
    else:
        pipeline_health = {}
        broken_pipelines = []

    context_text = format_context_for_prompt(ctx)

    # Include previous cycle info if available
    prev_info = ""
    if state.get("last_priority"):
        prev_info = f"""

PREVIOUS CYCLE:
- Last priority: {state.get('last_priority')}
- Last target sector: {state.get('last_target_sector', '?')}
- Last target pipeline: {state.get('last_target_pipeline', '?')}
- Consecutive no-improvement: {state.get('consecutive_no_improvement', 0)}
- Total improvements so far: {state.get('total_improvements', 0)}
If the previous priority did not improve scores, choose a DIFFERENT approach."""

    # Inject broken pipeline info so LLM prioritizes fixing them
    broken_info = ""
    if broken_pipelines:
        broken_details = []
        for bp in broken_pipelines:
            bdata = pipeline_health.get(bp, {})
            broken_details.append(
                f"  - {bp}: {bdata.get('error', 'unknown error')} "
                f"(HTTP {bdata.get('http_status', '?')}, latency={bdata.get('latency_s', '?')}s)"
            )
        broken_info = f"""

CRITICAL — BROKEN PIPELINES DETECTED (smoke test on production):
{chr(10).join(broken_details)}

A broken pipeline returns 0% accuracy FOREVER until fixed. This is the HIGHEST priority.
You MUST choose category "fix_pipeline" and target one of the broken pipelines above.
Do NOT choose "data_gap" if a pipeline is broken — fixing the pipeline comes first."""

    prompt = f"""{context_text}
{prev_info}
{broken_info}

TASK: Based on all the data above, determine the SINGLE highest-impact improvement \
to make in the next cycle.

Consider these improvement categories (in order of typical impact):
1. FIX BROKEN PIPELINE — If any pipeline returns errors/empty for a sector
2. DATA GAP — If a sector has low scores due to missing documents/vectors
3. RETRIEVAL QUALITY — If vectors exist but retrieval misses relevant chunks
4. PROMPT ENGINEERING — If retrieval works but LLM generates poor answers
5. NEW TEST COVERAGE — If we lack questions to detect regressions

Respond ONLY with a JSON object (no markdown, no preamble):
{{
  "priority": "description of the single highest-impact improvement",
  "category": "one of: fix_pipeline, data_gap, retrieval_quality, prompt_engineering, test_coverage",
  "target_pipeline": "standard|graph|quantitative|orchestrator",
  "target_sector": "finance|btp|juridique|industrie",
  "expected_impact": "estimated score improvement (e.g. +10 points on BTP standard)",
  "reasoning": "why this is the highest priority right now (2-3 sentences)",
  "action": "specific first step to take"
}}"""

    if dry_run:
        log("DRY RUN: Would call LLM for strategy", "WARN")
        return {
            "priority": "[dry-run] Placeholder priority",
            "category": "data_gap",
            "target_pipeline": "standard",
            "target_sector": "btp",
            "expected_impact": "+5 points",
            "reasoning": "Dry run placeholder",
            "action": "No action (dry run)",
        }

    log("Calling LLM for strategic analysis...")
    response = llm_call(prompt, system_prompt=STRATEGIC_SYSTEM_PROMPT, max_tokens=800)

    if not response:
        log("LLM call failed for strategy phase", "ERROR")
        return None

    strategy = extract_json_from_llm(response)
    if not strategy:
        log(f"Could not parse strategy JSON from LLM response: {response[:300]}", "ERROR")
        # Try to create a minimal strategy from the response text
        strategy = {
            "priority": response[:200] if response else "Unknown",
            "category": "unknown",
            "target_pipeline": "standard",
            "target_sector": _find_weakest_sector(ctx),
            "expected_impact": "unknown",
            "reasoning": response[:500] if response else "LLM response unparseable",
            "action": "Run targeted eval to establish baseline",
        }

    # Validate required fields
    for field in ["priority", "target_pipeline", "target_sector"]:
        if field not in strategy:
            strategy[field] = "unknown"

    # Normalize
    if strategy.get("target_sector") not in SECTORS:
        strategy["target_sector"] = _find_weakest_sector(ctx)
    if strategy.get("target_pipeline") not in PIPELINES:
        strategy["target_pipeline"] = "standard"

    # Log the strategy
    log(f"Priority: {C.BOLD}{strategy.get('priority', '?')}{C.RESET}", "STRAT")
    log(f"Category: {strategy.get('category', '?')}", "STRAT")
    log(f"Target:   {strategy.get('target_sector', '?')} / {strategy.get('target_pipeline', '?')}", "STRAT")
    log(f"Impact:   {strategy.get('expected_impact', '?')}", "STRAT")
    log(f"Action:   {strategy.get('action', '?')}", "STRAT")

    # Attach pipeline health for downstream phases (report)
    if pipeline_health:
        strategy["_pipeline_health"] = {
            pname: {
                "status": pdata.get("status", "unknown"),
                "error": pdata.get("error"),
                "latency_s": pdata.get("latency_s"),
                "response_length": pdata.get("response_length", 0),
            }
            for pname, pdata in pipeline_health.items()
        }

    # Persist
    log_jsonl(STRATEGY_LOG, {
        "event": "strategy_decided",
        "cycle": state.get("cycle", 0) + 1,
        "strategy": {k: v for k, v in strategy.items() if not k.startswith("_")},
        "pipeline_health": strategy.get("_pipeline_health"),
    })

    return strategy


def _find_weakest_sector(ctx):
    """Find the sector with the lowest eval score."""
    by_sector = ctx.get("eval_results", {}).get("by_sector", {})
    if not by_sector:
        return "btp"  # default weakest from known data

    weakest = min(by_sector.items(), key=lambda x: x[1].get("avg_score", 100))
    return weakest[0]


# ============================================================================
# PHASE 2: PLAN
# ============================================================================
def phase_plan(strategy, ctx, state, dry_run=False):
    """Create a detailed action plan for the chosen priority.

    Returns a plan dict or None on failure.
    """
    log(f"\n{C.BOLD}{'=' * 70}{C.RESET}", "PHASE")
    log(f"{C.BOLD}PHASE 2: PLAN — Creating action plan{C.RESET}", "PHASE")
    log(f"{'=' * 70}", "PHASE")

    context_text = format_context_for_prompt(ctx, max_chars=3000)

    prompt = f"""STRATEGY CHOSEN:
{json.dumps(strategy, indent=2, ensure_ascii=False)}

SYSTEM CONTEXT (abbreviated):
{context_text}

TASK: Create a detailed action plan to implement this improvement.

Available tools/scripts you can reference:
- eval/parallel-eval.py — Run eval across 6 Spaces (--sector X --pipeline Y)
- eval/continuous-judge.py — LLM-as-Judge scoring (--suggestions for improvement ideas)
- ops/metrics-collector.py — Collect n8n execution metrics (--profile for deep analysis)
- eval/expert-discovery.py — Discover expert documents via Tavily (--sector X)
- eval/mass-question-generator.py — Generate new test questions (--sector X)
- ops/staging-deploy.py — Deploy workflow changes (staging -> production)
- codespace/docling-cron.py — Process expert PDFs via Docling

Available n8n modifications:
- Prompt templates (system prompt, RAG prompt, HyDE prompt)
- Retrieval parameters (top_k, similarity threshold, namespace)
- Index selection (E5 vs Jina, which namespaces to query)
- Reranking configuration (FlashRank parameters)
- Response formatting instructions
- Error handling / fallback logic

Respond ONLY with a JSON object (no markdown, no preamble):
{{
  "plan_id": "plan-YYYYMMDD-HHMMSS",
  "target_sector": "{strategy.get('target_sector', 'unknown')}",
  "target_pipeline": "{strategy.get('target_pipeline', 'unknown')}",
  "category": "{strategy.get('category', 'unknown')}",
  "actions": [
    {{
      "step": 1,
      "type": "eval|script|n8n_change|ingest|manual",
      "description": "what to do",
      "command": "python3 script.py --args (if applicable)",
      "reason": "why this step"
    }}
  ],
  "test_questions": [
    {{
      "question": "a question that would verify the fix worked",
      "sector": "sector",
      "expected_behavior": "what a good answer looks like"
    }}
  ],
  "success_metric": "how we measure if the plan succeeded (e.g., BTP standard score > 50)",
  "estimated_duration_min": 15,
  "risk_assessment": "what could go wrong"
}}"""

    if dry_run:
        log("DRY RUN: Would call LLM for plan", "WARN")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return {
            "plan_id": f"plan-{ts}",
            "target_sector": strategy.get("target_sector", "btp"),
            "target_pipeline": strategy.get("target_pipeline", "standard"),
            "category": strategy.get("category", "unknown"),
            "actions": [{"step": 1, "type": "eval", "description": "[dry-run] Baseline eval",
                         "command": "python3 eval/parallel-eval.py --smoke", "reason": "Establish baseline"}],
            "test_questions": [],
            "success_metric": "Score improvement > 0",
            "estimated_duration_min": 5,
            "risk_assessment": "None (dry run)",
        }

    log("Calling LLM for action plan...")
    response = llm_call(prompt, system_prompt=STRATEGIC_SYSTEM_PROMPT, max_tokens=1500)

    if not response:
        log("LLM call failed for plan phase", "ERROR")
        return None

    plan = extract_json_from_llm(response)
    if not plan:
        log(f"Could not parse plan JSON from LLM response: {response[:300]}", "ERROR")
        # Minimal fallback plan
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        plan = {
            "plan_id": f"plan-{ts}",
            "target_sector": strategy.get("target_sector", "unknown"),
            "target_pipeline": strategy.get("target_pipeline", "standard"),
            "category": strategy.get("category", "unknown"),
            "actions": [
                {"step": 1, "type": "eval", "description": "Run baseline eval",
                 "command": f"python3 eval/parallel-eval.py --sector {strategy.get('target_sector', 'finance')} --pipeline {strategy.get('target_pipeline', 'standard')}",
                 "reason": "Establish current score before changes"}
            ],
            "test_questions": [],
            "success_metric": "Score improvement > 0",
            "estimated_duration_min": 10,
            "risk_assessment": "Plan generated from fallback logic",
        }

    # Ensure plan_id
    if not plan.get("plan_id"):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        plan["plan_id"] = f"plan-{ts}"

    # Log plan details
    actions = plan.get("actions", [])
    log(f"Plan: {plan.get('plan_id', '?')}", "OK")
    log(f"Steps: {len(actions)}", "OK")
    for a in actions:
        log(f"  Step {a.get('step', '?')}: [{a.get('type', '?')}] {a.get('description', '?')[:80]}")
    log(f"Success metric: {plan.get('success_metric', '?')}")
    log(f"Estimated duration: {plan.get('estimated_duration_min', '?')} min")

    # Persist plan
    plan_file = os.path.join(PLANS_DIR, f"{plan['plan_id']}.json")
    with open(plan_file, "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    log(f"Plan saved: {plan_file}", "OK")

    return plan


# ============================================================================
# PHASE 3: BUILD — Execute the plan (THE MISSING PIECE)
# ============================================================================
def phase_build(strategy, plan, state, dry_run=False):
    """Execute the plan: ingest data, deploy fixes, modify workflows.

    This is the phase that actually DOES things — discovers documents,
    processes PDFs via Docling, ingests into Pinecone E5, deploys to
    staging (S9), and runs a smoke test before promoting to production.

    Returns a build_result dict with actions taken and their outcomes.
    """
    log(f"\n{C.BOLD}{'=' * 70}{C.RESET}", "PHASE")
    log(f"{C.BOLD}PHASE 3: BUILD — Executing the plan{C.RESET}", "PHASE")
    log(f"{'=' * 70}", "PHASE")

    category = strategy.get("category", plan.get("category", "unknown"))
    target_sector = strategy.get("target_sector", "btp")
    target_pipeline = strategy.get("target_pipeline", "standard")

    build_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "target_sector": target_sector,
        "target_pipeline": target_pipeline,
        "actions_taken": [],
        "docs_discovered": 0,
        "docs_ingested": 0,
        "vectors_added": 0,
        "deployment": None,
        "smoke_test": None,
        "success": False,
    }

    if dry_run:
        log("DRY RUN: Would execute plan actions", "WARN")
        build_result["dry_run"] = True
        build_result["success"] = True
        return build_result

    try:
        if category == "data_gap":
            build_result = _build_data_gap(target_sector, target_pipeline, plan, build_result)
        elif category == "fix_pipeline":
            # Use the enhanced broken-pipeline handler which does diagnosis + redeployment
            build_result = _build_fix_broken_pipeline(target_sector, target_pipeline, plan, build_result)
        elif category == "retrieval_quality":
            build_result = _build_retrieval_quality(target_sector, target_pipeline, plan, build_result)
        elif category == "prompt_engineering":
            build_result = _build_prompt_engineering(target_sector, target_pipeline, plan, build_result)
        elif category == "test_coverage":
            build_result = _build_test_coverage(target_sector, target_pipeline, plan, build_result)
        else:
            log(f"Unknown category '{category}', executing plan commands directly", "WARN")
            build_result = _build_generic(plan, build_result)
    except Exception as e:
        log(f"BUILD phase error: {e}", "ERROR")
        build_result["error"] = str(e)
        build_result["actions_taken"].append({
            "action": "error",
            "detail": str(e),
        })

    # Always run smoke test on S9 staging after any build action
    if build_result.get("actions_taken") and not build_result.get("dry_run"):
        smoke = _smoke_test_staging(target_pipeline, target_sector)
        build_result["smoke_test"] = smoke
        if smoke.get("pass"):
            log(f"Staging smoke test PASSED (score={smoke.get('score', '?')})", "OK")
        else:
            log(f"Staging smoke test FAILED: {smoke.get('error', 'unknown')}", "WARN")

    # Determine success
    actions_ok = sum(1 for a in build_result["actions_taken"] if a.get("success", False))
    total_actions = len(build_result["actions_taken"])
    build_result["success"] = actions_ok > 0

    log(f"BUILD complete: {actions_ok}/{total_actions} actions succeeded", "OK" if build_result["success"] else "WARN")
    if build_result["docs_ingested"] > 0:
        log(f"  Docs ingested: {build_result['docs_ingested']}", "OK")
    if build_result["vectors_added"] > 0:
        log(f"  Vectors added: {build_result['vectors_added']}", "OK")

    # Save build result
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    build_file = os.path.join(BUILDS_DIR, f"build-{ts}.json")
    with open(build_file, "w") as f:
        json.dump(build_result, f, indent=2, ensure_ascii=False, default=str)
    log(f"Build result saved: {build_file}", "OK")

    log_jsonl(STRATEGY_LOG, {
        "event": "build_completed",
        "cycle": state.get("cycle", 0) + 1,
        "category": category,
        "actions_ok": actions_ok,
        "total_actions": total_actions,
        "docs_ingested": build_result["docs_ingested"],
        "vectors_added": build_result["vectors_added"],
        "success": build_result["success"],
    })

    return build_result


# ---------------------------------------------------------------------------
# BUILD SUB-FUNCTIONS by category
# ---------------------------------------------------------------------------

def _build_data_gap(sector, pipeline, plan, result):
    """Fill data gap: Tavily discovery → Docling PDF processing → E5 ingestion."""
    log(f"DATA GAP build for {sector}", "STRAT")

    # Step 1: Discover expert documents via Tavily
    log("Step 1: Discovering expert documents via Tavily...")
    disc_rc, disc_out, disc_err = run_script(
        EXPERT_DISCOVERY_SCRIPT,
        ["--sector", sector, "--max-queries", "5"],
        timeout_s=180,
    )
    result["actions_taken"].append({
        "action": "expert_discovery",
        "sector": sector,
        "return_code": disc_rc,
        "success": disc_rc == 0,
        "detail": disc_out[:500] if disc_out else disc_err[:500] if disc_err else "no output",
    })

    # Count discovered docs
    disc_file = os.path.join(REPO_ROOT, "data", "eval", "expert-discovery", "discovered-documents.json")
    discovered_count = 0
    if os.path.exists(disc_file):
        try:
            with open(disc_file) as f:
                disc_data = json.load(f)
            discovered_count = len(disc_data) if isinstance(disc_data, list) else disc_data.get("total", 0)
        except Exception:
            pass
    result["docs_discovered"] = discovered_count
    log(f"  Discovered: {discovered_count} documents", "OK" if discovered_count > 0 else "WARN")

    # Step 2: Ingest via fast-ingest (handles E5 embedding + Pinecone upsert + Supabase)
    log("Step 2: Ingesting into E5 Pinecone + Supabase via fast-ingest...")
    ingest_rc, ingest_out, ingest_err = run_script(
        FAST_INGEST_SCRIPT,
        ["--sector", sector],
        timeout_s=600,
    )
    result["actions_taken"].append({
        "action": "fast_ingest",
        "sector": sector,
        "return_code": ingest_rc,
        "success": ingest_rc == 0,
        "detail": ingest_out[:500] if ingest_out else ingest_err[:500] if ingest_err else "no output",
    })

    # Parse ingestion counts from output
    if ingest_out:
        for line in ingest_out.split("\n"):
            if "ingested" in line.lower() or "upserted" in line.lower():
                # Try to extract numbers
                import re
                nums = re.findall(r'(\d+)', line)
                if nums:
                    result["docs_ingested"] += int(nums[0])
            if "vector" in line.lower():
                import re
                nums = re.findall(r'(\d+)', line)
                if nums:
                    result["vectors_added"] += int(nums[0])

    # Step 3: Process PDFs via Docling S6 API (adapted for HF Space CPU-basic)
    # Prefer S6 adapter over codespace cron (S6 is always available)
    docling_script = DOCLING_S6_SCRIPT if os.path.exists(DOCLING_S6_SCRIPT) else DOCLING_CRON_SCRIPT
    if os.path.exists(docling_script):
        log(f"Step 3: Processing PDFs via Docling ({os.path.basename(docling_script)})...")
        doc_args = ["--from-discovered", "--sector", sector, "--max", "5"]
        if docling_script == DOCLING_CRON_SCRIPT:
            doc_args = ["--sector", sector, "--max-pdfs", "5"]
        doc_rc, doc_out, doc_err = run_script(
            docling_script,
            doc_args,
            timeout_s=900,  # 15 min — S6 CPU-basic is slow
        )
        result["actions_taken"].append({
            "action": "docling_process",
            "sector": sector,
            "return_code": doc_rc,
            "success": doc_rc == 0,
            "detail": doc_out[:500] if doc_out else doc_err[:500] if doc_err else "no output",
        })
    else:
        log("No Docling script found (neither S6 adapter nor cron), skipping PDF processing", "WARN")

    return result


def _build_fix_pipeline(sector, pipeline, plan, result):
    """Fix a broken pipeline: deploy workflow fix to S9 staging, smoke test, promote."""
    log(f"PIPELINE FIX build for {sector}/{pipeline}", "STRAT")

    # Check if plan has specific workflow file to deploy
    workflow_file = None
    for action in plan.get("actions", []):
        cmd = action.get("command", "")
        if "staging-deploy" in cmd and "--workflow" in cmd:
            # Extract workflow file from command
            parts = cmd.split("--workflow")
            if len(parts) > 1:
                workflow_file = parts[1].strip().split()[0]
                break

    if not workflow_file:
        # Find the latest live workflow for this pipeline
        live_dir = os.path.join(REPO_ROOT, "n8n", "live")
        if os.path.exists(live_dir):
            candidates = [f for f in os.listdir(live_dir)
                          if pipeline in f.lower() and f.endswith(".json")]
            if candidates:
                candidates.sort(key=lambda f: os.path.getmtime(os.path.join(live_dir, f)), reverse=True)
                workflow_file = os.path.join("n8n", "live", candidates[0])

    if not workflow_file:
        log(f"No workflow file found for {pipeline}, cannot deploy", "WARN")
        result["actions_taken"].append({
            "action": "deploy_skipped",
            "reason": f"No workflow file for {pipeline}",
            "success": False,
        })
        return result

    # Deploy to staging (S9) first
    log(f"Deploying {workflow_file} to staging (S9)...")
    deploy_rc, deploy_out, deploy_err = run_script(
        STAGING_DEPLOY_SCRIPT,
        ["--workflow", workflow_file, "--pipeline", pipeline, "--staging-only", "--skip-tests"],
        timeout_s=180,
    )
    result["actions_taken"].append({
        "action": "deploy_staging",
        "workflow": workflow_file,
        "pipeline": pipeline,
        "return_code": deploy_rc,
        "success": deploy_rc == 0,
        "detail": deploy_out[:500] if deploy_out else deploy_err[:500] if deploy_err else "no output",
    })
    result["deployment"] = {
        "target": "staging_s9",
        "workflow": workflow_file,
        "success": deploy_rc == 0,
    }

    if deploy_rc != 0:
        log(f"Staging deploy failed (rc={deploy_rc}), aborting", "ERROR")
        return result

    # Smoke test on S9
    smoke = _smoke_test_staging(pipeline, sector)
    if smoke.get("pass"):
        log("Staging smoke PASSED — promoting to production", "OK")
        # Promote to all production Spaces
        promote_rc, promote_out, promote_err = run_script(
            STAGING_DEPLOY_SCRIPT,
            ["--workflow", workflow_file, "--pipeline", pipeline, "--production-spaces", "--skip-tests"],
            timeout_s=300,
        )
        result["actions_taken"].append({
            "action": "promote_production",
            "workflow": workflow_file,
            "return_code": promote_rc,
            "success": promote_rc == 0,
            "detail": promote_out[:500] if promote_out else "",
        })
        result["deployment"]["promoted"] = promote_rc == 0
    else:
        log(f"Staging smoke FAILED — NOT promoting. Score: {smoke.get('score', 'N/A')}", "WARN")
        result["deployment"]["promoted"] = False

    return result


def _build_fix_broken_pipeline(sector, pipeline, plan, result):
    """Diagnose and attempt to fix a broken pipeline detected by smoke tests.

    Steps:
    1. Re-confirm the pipeline is broken (re-test on multiple Spaces)
    2. Inspect workflow JSON for obvious issues (wrong endpoints, missing creds)
    3. Check n8n execution logs for recent error patterns
    4. Log a detailed diagnosis
    5. Attempt to redeploy the workflow if a valid one exists
    """
    log(f"FIX BROKEN PIPELINE: {pipeline} on {sector}", "STRAT")

    # Step 1: Re-confirm on all production Spaces
    log("Step 1: Re-testing pipeline across all production Spaces...")
    space_results = {}
    working_spaces = []
    broken_spaces = []
    for space_url in PRODUCTION_SPACES:
        health = _smoke_test_all_pipelines(space_url=space_url, timeout=60)
        p_health = health.get(pipeline, {})
        space_results[space_url] = p_health
        if p_health.get("status") == "ok":
            working_spaces.append(space_url)
        else:
            broken_spaces.append(space_url)

    result["actions_taken"].append({
        "action": "confirm_broken",
        "pipeline": pipeline,
        "working_spaces": len(working_spaces),
        "broken_spaces": len(broken_spaces),
        "success": True,
        "detail": f"{len(working_spaces)}/{len(PRODUCTION_SPACES)} Spaces working, "
                  f"{len(broken_spaces)} broken",
    })

    if not broken_spaces:
        log(f"Pipeline {pipeline} is actually working on all Spaces now (transient failure)", "OK")
        result["actions_taken"].append({
            "action": "diagnosis",
            "detail": "Pipeline was transiently broken — now working on all Spaces",
            "success": True,
        })
        return result

    log(f"Confirmed broken on {len(broken_spaces)} Spaces: {', '.join(s[:30] for s in broken_spaces)}", "WARN")

    # Step 1b: Run infra-test for precise component diagnosis
    infra_test_script = os.path.join(REPO_ROOT, "ops", "infra-test.py")
    if os.path.exists(infra_test_script):
        log("Step 1b: Running infrastructure tests for component-level diagnosis...")
        it_rc, it_out, it_err = run_script(infra_test_script, ["--json", "--component", "pipelines"], timeout_s=180)
        if it_rc == 0 and it_out:
            try:
                it_data = json.loads(it_out)
                for t in it_data.get("tests", []):
                    if t.get("status") != "PASS":
                        log(f"  INFRA FAIL: {t.get('component','?')}/{t.get('test','?')}: "
                            f"{t.get('detail','?')[:100]}", "ERROR")
                        diagnosis_details = t.get("detail", "")
                        if "timeout" in diagnosis_details.lower():
                            log("    → Likely: Node hanging on external call (Neo4j? Embedding?)", "WARN")
                        elif "empty" in diagnosis_details.lower():
                            log("    → Likely: Pipeline returns empty response (config issue)", "WARN")
                result["actions_taken"].append({
                    "action": "infra_test_diagnosis",
                    "return_code": it_rc,
                    "success": True,
                    "detail": it_out[:500],
                })
            except (json.JSONDecodeError, KeyError):
                pass

    # Step 2: Check for workflow JSON files and inspect for known issues
    log("Step 2: Inspecting workflow JSON for known issues...")
    diagnosis = {
        "pipeline": pipeline,
        "sector": sector,
        "broken_spaces": broken_spaces,
        "working_spaces": working_spaces,
        "issues_found": [],
        "space_errors": {s: space_results[s].get("error", "?") for s in broken_spaces},
    }

    live_dir = os.path.join(REPO_ROOT, "n8n", "live")
    workflow_file = None
    if os.path.exists(live_dir):
        candidates = [f for f in os.listdir(live_dir)
                      if pipeline in f.lower() and f.endswith(".json")]
        if candidates:
            candidates.sort(key=lambda f: os.path.getmtime(os.path.join(live_dir, f)), reverse=True)
            workflow_file = os.path.join(live_dir, candidates[0])

    if workflow_file and os.path.exists(workflow_file):
        log(f"  Inspecting: {workflow_file}")
        try:
            with open(workflow_file) as wf:
                workflow_data = json.load(wf)

            # Check for common issues in workflow JSON
            workflow_str = json.dumps(workflow_data, ensure_ascii=False)

            # Issue: Expired or placeholder API keys
            if "sk-or-" in workflow_str or "YOUR_API_KEY" in workflow_str:
                diagnosis["issues_found"].append("Hardcoded or placeholder API key found in workflow")

            # Issue: Wrong LiteLLM endpoint
            if "engine-7" not in workflow_str and "litellm" not in workflow_str.lower():
                diagnosis["issues_found"].append("No LiteLLM S7 endpoint reference found — may use wrong LLM backend")

            # Issue: Wrong embedding endpoint
            if pipeline == "graph" and "embeddings-api" not in workflow_str:
                diagnosis["issues_found"].append("Graph pipeline missing self-hosted embeddings reference")

            # Issue: Check for disabled/inactive nodes
            nodes = workflow_data.get("nodes", [])
            if isinstance(nodes, list):
                disabled_nodes = [n.get("name", "?") for n in nodes
                                  if isinstance(n, dict) and n.get("disabled", False)]
                if disabled_nodes:
                    diagnosis["issues_found"].append(
                        f"Disabled nodes found: {', '.join(disabled_nodes[:5])}")

            # Issue: Check for HTTP Request nodes with wrong URLs
            for node in (nodes if isinstance(nodes, list) else []):
                if isinstance(node, dict) and node.get("type", "").endswith("httpRequest"):
                    params = node.get("parameters", {})
                    url_val = params.get("url", "")
                    if "localhost" in str(url_val) or "127.0.0.1" in str(url_val):
                        diagnosis["issues_found"].append(
                            f"Node '{node.get('name', '?')}' points to localhost — needs HF Space URL")

            log(f"  Issues found: {len(diagnosis['issues_found'])}")
            for issue in diagnosis["issues_found"]:
                log(f"    - {issue}", "WARN")

        except (json.JSONDecodeError, IOError) as e:
            log(f"  Failed to parse workflow: {e}", "ERROR")
            diagnosis["issues_found"].append(f"Workflow JSON parse error: {str(e)[:80]}")
    else:
        log(f"  No workflow file found for {pipeline}", "WARN")
        diagnosis["issues_found"].append(f"No workflow JSON found in n8n/live/ for {pipeline}")

    result["actions_taken"].append({
        "action": "diagnosis",
        "pipeline": pipeline,
        "issues_found": diagnosis["issues_found"],
        "success": True,
        "detail": json.dumps(diagnosis, ensure_ascii=False, default=str)[:500],
    })

    # Step 3: Collect error info from the broken Space responses
    log("Step 3: Analyzing error patterns from Space responses...")
    error_patterns = {}
    for space_url, sdata in space_results.items():
        err = sdata.get("error", "")
        if err:
            # Categorize the error
            if "timeout" in err.lower() or "timed out" in err.lower():
                error_patterns["timeout"] = error_patterns.get("timeout", 0) + 1
            elif "500" in err or "502" in err or "503" in err:
                error_patterns["server_error"] = error_patterns.get("server_error", 0) + 1
            elif "404" in err:
                error_patterns["not_found"] = error_patterns.get("not_found", 0) + 1
            elif "401" in err or "403" in err:
                error_patterns["auth_error"] = error_patterns.get("auth_error", 0) + 1
            else:
                error_patterns["other"] = error_patterns.get("other", 0) + 1

    diagnosis["error_patterns"] = error_patterns
    log(f"  Error patterns: {json.dumps(error_patterns)}")

    # Step 4: Attempt to redeploy if we have a workflow file
    if workflow_file and os.path.exists(STAGING_DEPLOY_SCRIPT):
        log("Step 4: Attempting redeployment to broken Spaces...")
        # Deploy to staging first for safety
        deploy_rc, deploy_out, deploy_err = run_script(
            STAGING_DEPLOY_SCRIPT,
            ["--workflow", workflow_file, "--pipeline", pipeline, "--staging-only", "--skip-tests"],
            timeout_s=180,
        )
        result["actions_taken"].append({
            "action": "redeploy_staging",
            "workflow": workflow_file,
            "return_code": deploy_rc,
            "success": deploy_rc == 0,
            "detail": deploy_out[:300] if deploy_out else deploy_err[:300] if deploy_err else "",
        })

        if deploy_rc == 0:
            # Smoke test staging
            smoke = _smoke_test_staging(pipeline, sector)
            if smoke.get("pass"):
                log("Staging smoke PASSED after redeployment — promoting to production", "OK")
                promote_rc, promote_out, promote_err = run_script(
                    STAGING_DEPLOY_SCRIPT,
                    ["--workflow", workflow_file, "--pipeline", pipeline,
                     "--production-spaces", "--skip-tests"],
                    timeout_s=300,
                )
                result["actions_taken"].append({
                    "action": "promote_fix_to_production",
                    "return_code": promote_rc,
                    "success": promote_rc == 0,
                    "detail": promote_out[:300] if promote_out else "",
                })
                result["deployment"] = {
                    "target": "production",
                    "workflow": workflow_file,
                    "success": promote_rc == 0,
                    "promoted": promote_rc == 0,
                }
            else:
                log(f"Staging smoke FAILED after redeployment: {smoke.get('error', '?')}", "WARN")
                result["actions_taken"].append({
                    "action": "staging_smoke_after_redeploy",
                    "success": False,
                    "detail": f"Smoke failed: {smoke.get('error', 'unknown')}",
                })
    else:
        log("Step 4: Cannot redeploy (no workflow file or deploy script missing)", "WARN")

    # Save diagnosis to a dedicated file for debugging
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    diag_file = os.path.join(BUILDS_DIR, f"diagnosis-{pipeline}-{ts}.json")
    with open(diag_file, "w") as f:
        json.dump(diagnosis, f, indent=2, ensure_ascii=False, default=str)
    log(f"Diagnosis saved: {diag_file}", "OK")

    return result


def _build_retrieval_quality(sector, pipeline, plan, result):
    """Improve retrieval: adjust parameters, reindex, or add reranking."""
    log(f"RETRIEVAL QUALITY build for {sector}/{pipeline}", "STRAT")

    # For now, retrieval quality improvements require running the plan's specific commands
    result = _build_generic(plan, result)

    # Additionally run fast-ingest to ensure vectors are up-to-date
    log("Re-running fast-ingest to refresh vectors...")
    ingest_rc, ingest_out, ingest_err = run_script(
        FAST_INGEST_SCRIPT,
        ["--sector", sector],
        timeout_s=300,
    )
    result["actions_taken"].append({
        "action": "refresh_vectors",
        "sector": sector,
        "return_code": ingest_rc,
        "success": ingest_rc == 0,
        "detail": ingest_out[:300] if ingest_out else "",
    })

    return result


def _build_prompt_engineering(sector, pipeline, plan, result):
    """Improve prompts: extract from plan commands and execute."""
    log(f"PROMPT ENGINEERING build for {sector}/{pipeline}", "STRAT")

    # Prompt changes are typically workflow modifications
    # Execute any staging-deploy commands from the plan
    deployed = False
    for action in plan.get("actions", []):
        cmd = action.get("command", "")
        if "staging-deploy" in cmd:
            # Parse and execute
            parts = cmd.split()
            args = parts[2:] if len(parts) > 2 else []  # skip "python3 ops/staging-deploy.py"
            if not any("--staging-only" in a for a in args):
                args.append("--staging-only")  # Always deploy to staging first
            deploy_rc, deploy_out, deploy_err = run_script(STAGING_DEPLOY_SCRIPT, args, timeout_s=180)
            result["actions_taken"].append({
                "action": "deploy_prompt_change",
                "command": cmd,
                "return_code": deploy_rc,
                "success": deploy_rc == 0,
                "detail": deploy_out[:300] if deploy_out else deploy_err[:300] if deploy_err else "",
            })
            deployed = True

    if not deployed:
        # Fall back to generic plan execution
        result = _build_generic(plan, result)
        log("No staging-deploy commands in plan, executed generic actions", "WARN")

    return result


def _build_test_coverage(sector, pipeline, plan, result):
    """Generate new test questions to improve coverage."""
    log(f"TEST COVERAGE build for {sector}/{pipeline}", "STRAT")

    log("Generating new test questions...")
    gen_rc, gen_out, gen_err = run_script(
        MASS_QUESTION_SCRIPT,
        ["--sector", sector, "--count", "20"],
        timeout_s=180,
    )
    result["actions_taken"].append({
        "action": "generate_questions",
        "sector": sector,
        "return_code": gen_rc,
        "success": gen_rc == 0,
        "detail": gen_out[:500] if gen_out else gen_err[:300] if gen_err else "",
    })

    return result


def _build_generic(plan, result):
    """Execute plan commands generically (for unknown categories)."""
    for action in plan.get("actions", []):
        cmd = action.get("command", "")
        if not cmd or cmd.startswith("#"):
            continue

        # Only execute python scripts from our repo (safety)
        if not cmd.startswith("python3 "):
            log(f"Skipping non-python command: {cmd[:80]}", "WARN")
            result["actions_taken"].append({
                "action": "skipped_command",
                "command": cmd[:100],
                "success": False,
                "detail": "Only python3 commands are auto-executed",
            })
            continue

        # Parse script and args
        parts = cmd.split()
        script_name = parts[1] if len(parts) > 1 else ""
        script_path = os.path.join(REPO_ROOT, script_name)
        args = parts[2:] if len(parts) > 2 else []

        if not os.path.exists(script_path):
            log(f"Script not found: {script_path}", "WARN")
            result["actions_taken"].append({
                "action": "script_not_found",
                "command": cmd[:100],
                "success": False,
            })
            continue

        log(f"Executing: {cmd[:100]}...")
        rc, out, err = run_script(script_path, args, timeout_s=300)
        result["actions_taken"].append({
            "action": "execute_command",
            "command": cmd[:200],
            "return_code": rc,
            "success": rc == 0,
            "detail": out[:300] if out else err[:300] if err else "",
        })

    return result


def _smoke_test_staging(pipeline, sector):
    """Run a quick smoke test on S9 staging to verify the build."""
    log(f"Smoke testing {pipeline} on S9 staging...")

    webhook_path = WEBHOOK_PATHS.get(pipeline, WEBHOOK_PATHS["standard"])
    url = f"https://{STAGING_SPACE}{webhook_path}"

    # Simple smoke question per sector
    smoke_questions = {
        "finance": "Quels sont les principaux ratios financiers pour analyser une entreprise du CAC40 ?",
        "btp": "Quelles sont les principales normes DTU pour la construction en France ?",
        "juridique": "Quels sont les principes fondamentaux du droit des contrats en France ?",
        "industrie": "Quelles sont les normes ISO les plus importantes pour l'industrie manufacturière ?",
    }

    question = smoke_questions.get(sector, smoke_questions["finance"])

    try:
        status, body = http_request(
            url,
            method="POST",
            data={"query": question, "sector": sector, "chatInput": question},
            timeout=90,
        )

        if status == 200:
            try:
                resp = json.loads(body) if isinstance(body, str) else body
                # Handle list response format
                if isinstance(resp, list) and resp:
                    resp = resp[0]
                response_text = resp.get("response", resp.get("output", ""))
                has_content = len(response_text) > 50
                has_sources = "source" in response_text.lower() or "document" in response_text.lower()
                score = 70 if has_content else 20
                if has_sources:
                    score += 20
                return {
                    "pass": has_content,
                    "score": score,
                    "response_length": len(response_text),
                    "has_sources": has_sources,
                    "status_code": status,
                }
            except (json.JSONDecodeError, AttributeError, TypeError):
                return {"pass": False, "error": "Invalid JSON response", "status_code": status}
        else:
            return {"pass": False, "error": f"HTTP {status}", "status_code": status, "body": body[:200]}
    except Exception as e:
        return {"pass": False, "error": str(e)}


# ---------------------------------------------------------------------------
# PIPELINE HEALTH CHECK — Quick smoke test on all pipelines (for STRATEGIZE)
# ---------------------------------------------------------------------------
def _smoke_test_all_pipelines(space_url=None, timeout=45):
    """Run a quick smoke test on each pipeline to detect broken ones.

    Tests Standard, Graph, Quantitative, and Orchestrator with a simple question.
    Returns a dict: {pipeline_name: {status, error, latency_s, response_length}}.
    Uses the first production Space by default.
    """
    if space_url is None:
        space_url = PRODUCTION_SPACES[0] if PRODUCTION_SPACES else STAGING_SPACE

    test_question = "Quels sont les principaux indicateurs financiers ?"
    test_payload = {
        "query": test_question,
        "sector": "finance",
        "chatInput": test_question,
    }

    results = {}
    for pipeline, webhook_path in WEBHOOK_PATHS.items():
        url = f"https://{space_url}{webhook_path}"
        t0 = time.time()
        try:
            status_code, body = http_request(
                url,
                method="POST",
                data=test_payload,
                timeout=timeout,
            )
            latency = round(time.time() - t0, 1)

            if status_code == 200:
                try:
                    resp = json.loads(body) if isinstance(body, str) else body
                    if isinstance(resp, list) and resp:
                        resp = resp[0]
                    response_text = resp.get("response", resp.get("output", ""))
                    has_content = len(response_text) > 30
                    results[pipeline] = {
                        "status": "ok" if has_content else "empty_response",
                        "error": None if has_content else "Response shorter than 30 chars",
                        "latency_s": latency,
                        "response_length": len(response_text),
                        "http_status": status_code,
                    }
                except (json.JSONDecodeError, AttributeError, TypeError) as e:
                    results[pipeline] = {
                        "status": "error",
                        "error": f"Invalid JSON: {str(e)[:80]}",
                        "latency_s": latency,
                        "response_length": 0,
                        "http_status": status_code,
                    }
            else:
                results[pipeline] = {
                    "status": "error",
                    "error": f"HTTP {status_code}: {body[:120] if body else 'no body'}",
                    "latency_s": latency,
                    "response_length": 0,
                    "http_status": status_code,
                }
        except Exception as e:
            latency = round(time.time() - t0, 1)
            results[pipeline] = {
                "status": "error",
                "error": f"Exception: {str(e)[:120]}",
                "latency_s": latency,
                "response_length": 0,
                "http_status": 0,
            }

        # ── Classify failure type for smarter decisions ──
        r = results[pipeline]
        if r["status"] != "ok":
            lat = r.get("latency_s", 0)
            if lat >= timeout * 0.9:
                r["failure_type"] = "timeout_hang"
                r["likely_cause"] = "External call hanging (Neo4j, embedding, or LLM)"
            elif lat <= 5:
                r["failure_type"] = "instant_fail"
                r["likely_cause"] = "Config error, wrong credential, or missing workflow"
            elif r.get("http_status", 0) in (401, 403):
                r["failure_type"] = "auth_error"
                r["likely_cause"] = "Authentication failed (API key expired or wrong)"
            elif r.get("http_status", 0) in (502, 503):
                r["failure_type"] = "space_down"
                r["likely_cause"] = "HF Space sleeping or crashed"
            elif r["status"] == "empty_response":
                r["failure_type"] = "empty_response"
                r["likely_cause"] = "Workflow runs but returns no content (node config issue)"
            else:
                r["failure_type"] = "unknown"
                r["likely_cause"] = r.get("error", "Unknown error")[:80]

    return results


# ============================================================================
# PHASE 4: OBSERVE (measure impact after build)
# ============================================================================
def phase_observe(strategy, plan, state, dry_run=False):
    """Run targeted eval to measure impact of the build phase.

    Returns a baseline dict or None on failure.
    """
    log(f"\n{C.BOLD}{'=' * 70}{C.RESET}", "PHASE")
    log(f"{C.BOLD}PHASE 4: OBSERVE — Measuring impact{C.RESET}", "PHASE")
    log(f"{'=' * 70}", "PHASE")

    target_sector = strategy.get("target_sector", "finance")
    target_pipeline = strategy.get("target_pipeline", "standard")

    log(f"Target: {target_sector} / {target_pipeline}")

    # Build eval command
    eval_args = ["--sector", target_sector]
    if target_pipeline != "all":
        eval_args.extend(["--pipeline", target_pipeline])
    # Use smoke for faster feedback
    eval_args.append("--smoke")

    if dry_run:
        log(f"DRY RUN: Would run parallel-eval.py {' '.join(eval_args)}", "WARN")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_sector": target_sector,
            "target_pipeline": target_pipeline,
            "avg_score": 0,
            "pass_rate": 0,
            "total_questions": 0,
            "dry_run": True,
        }

    log(f"Running: parallel-eval.py {' '.join(eval_args)}")
    rc, stdout, stderr = run_script(PARALLEL_EVAL_SCRIPT, eval_args, timeout_s=600)

    baseline = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target_sector": target_sector,
        "target_pipeline": target_pipeline,
        "eval_return_code": rc,
    }

    if rc == 0:
        # Read the results that parallel-eval just wrote
        latest = read_latest_eval_results()
        if latest:
            # Extract targeted scores
            sector_data = latest.get("by_sector", {}).get(target_sector, {})
            pipeline_data = latest.get("by_pipeline", {}).get(target_pipeline, {})

            baseline["overall_avg_score"] = latest.get("avg_score", 0)
            baseline["overall_pass_rate"] = latest.get("pass_rate", 0)
            baseline["sector_avg_score"] = sector_data.get("avg_score", 0)
            baseline["sector_pass_rate"] = sector_data.get("pass_rate", 0)
            baseline["pipeline_avg_score"] = pipeline_data.get("avg_score", 0)
            baseline["pipeline_pass_rate"] = pipeline_data.get("pass_rate", 0)
            baseline["pipeline_keyword_hit"] = pipeline_data.get("keyword_hit_rate", 0)
            baseline["pipeline_latency"] = pipeline_data.get("avg_latency_s", 0)
            baseline["total_questions"] = latest.get("total_questions", 0)

            log(f"Baseline established:", "OK")
            log(f"  Overall:  {baseline['overall_avg_score']}/100, {baseline['overall_pass_rate']}% pass")
            log(f"  {target_sector}: {baseline['sector_avg_score']}/100, {baseline['sector_pass_rate']}% pass")
            log(f"  {target_pipeline}: {baseline['pipeline_avg_score']}/100, "
                f"{baseline['pipeline_pass_rate']}% pass, "
                f"keyword={baseline['pipeline_keyword_hit']}%, "
                f"latency={baseline['pipeline_latency']}s")
        else:
            log("Eval ran but no results file found", "WARN")
            baseline["error"] = "No results file after eval"
    else:
        log(f"Eval failed (rc={rc})", "ERROR")
        if stderr:
            log(f"Stderr: {stderr[:300]}", "ERROR")
        baseline["error"] = f"Eval failed with rc={rc}"
        # Fall back to reading existing results
        latest = read_latest_eval_results()
        if latest:
            sector_data = latest.get("by_sector", {}).get(target_sector, {})
            baseline["sector_avg_score"] = sector_data.get("avg_score", 0)
            baseline["sector_pass_rate"] = sector_data.get("pass_rate", 0)
            baseline["fallback"] = True
            log(f"Using existing baseline: {target_sector} avg={baseline['sector_avg_score']}/100", "WARN")

    # Save baseline
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    baseline_file = os.path.join(BASELINES_DIR, f"baseline-{ts}.json")
    with open(baseline_file, "w") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    log(f"Baseline saved: {baseline_file}", "OK")

    return baseline


# ============================================================================
# PHASE 5: COLLECT (gather execution data)
# ============================================================================
def phase_collect(strategy, plan, baseline, state, dry_run=False):
    """Gather all execution data: metrics + LLM judge scores.

    Returns a collected-data dict or None on failure.
    """
    log(f"\n{C.BOLD}{'=' * 70}{C.RESET}", "PHASE")
    log(f"{C.BOLD}PHASE 5: COLLECT — Gathering execution data{C.RESET}", "PHASE")
    log(f"{'=' * 70}", "PHASE")

    collected = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target_sector": strategy.get("target_sector"),
        "target_pipeline": strategy.get("target_pipeline"),
        "baseline": baseline,
        "metrics": None,
        "judge_results": None,
    }

    if dry_run:
        log("DRY RUN: Would run metrics-collector + continuous-judge", "WARN")
        collected["dry_run"] = True
        return collected

    # Step 1: Run metrics collector
    log("Step 1/2: Running metrics collector...")
    rc1, stdout1, stderr1 = run_script(METRICS_COLLECTOR_SCRIPT, timeout_s=120)
    if rc1 == 0:
        metrics = read_metrics()
        collected["metrics"] = {
            "execution_count": len(metrics.get("execution_log", [])) if isinstance(metrics.get("execution_log"), list) else 0,
            "has_node_perf": "node_performance" in metrics,
            "has_error_catalog": "error_catalog" in metrics,
            "has_analysis": "analysis_report" in metrics,
        }
        log(f"Metrics collected: {collected['metrics']}", "OK")
    else:
        log(f"Metrics collector failed (rc={rc1})", "WARN")
        if stderr1:
            log(f"  {stderr1[:200]}", "WARN")

    # Step 2: Run continuous judge
    log("Step 2/2: Running continuous judge...")
    rc2, stdout2, stderr2 = run_script(CONTINUOUS_JUDGE_SCRIPT, timeout_s=300)
    if rc2 == 0:
        board = read_execution_board()
        suggestions = read_improvement_suggestions()
        collected["judge_results"] = {
            "has_board": board is not None,
            "has_suggestions": suggestions is not None,
            "suggestion_count": len(suggestions) if isinstance(suggestions, list) else 0,
        }
        log(f"Judge results: {collected['judge_results']}", "OK")
    else:
        log(f"Continuous judge failed (rc={rc2})", "WARN")
        if stderr2:
            log(f"  {stderr2[:200]}", "WARN")
        # Still try to read existing data
        board = read_execution_board()
        suggestions = read_improvement_suggestions()
        if board or suggestions:
            collected["judge_results"] = {
                "has_board": board is not None,
                "has_suggestions": suggestions is not None,
                "fallback": True,
            }
            log("Using existing judge data", "WARN")

    # Save collected data
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    collected_file = os.path.join(COLLECTED_DIR, f"collected-{ts}.json")
    with open(collected_file, "w") as f:
        json.dump(collected, f, indent=2, ensure_ascii=False)
    log(f"Collected data saved: {collected_file}", "OK")

    return collected


# ============================================================================
# PHASE 6: ANALYZE (deep failure analysis + new question generation)
# ============================================================================
def phase_analyze(strategy, plan, baseline, collected, ctx, state, dry_run=False):
    """Deep analysis of all collected data. Generate insights + new questions.

    Returns an analysis dict or None on failure.
    """
    log(f"\n{C.BOLD}{'=' * 70}{C.RESET}", "PHASE")
    log(f"{C.BOLD}PHASE 6: ANALYZE — Deep failure analysis{C.RESET}", "PHASE")
    log(f"{'=' * 70}", "PHASE")

    # Rebuild context with freshly collected data
    fresh_ctx = build_system_context()
    context_text = format_context_for_prompt(fresh_ctx, max_chars=4000)

    # Build analysis-specific data
    baseline_info = json.dumps({
        k: v for k, v in (baseline or {}).items()
        if k not in ("eval_return_code",)
    }, indent=2, ensure_ascii=False, default=str)

    collected_info = json.dumps({
        k: v for k, v in (collected or {}).items()
        if k not in ("baseline",)
    }, indent=2, ensure_ascii=False, default=str)

    prompt = f"""STRATEGY:
{json.dumps(strategy, indent=2, ensure_ascii=False)}

BASELINE (before any changes):
{baseline_info}

COLLECTED DATA:
{collected_info}

SYSTEM CONTEXT:
{context_text}

TASK: Perform a deep analysis of the collected data and produce actionable insights.

1. Identify the top 3 failure patterns (specific error types, not generic)
2. For each pattern: root cause, affected sector/pipeline, suggested fix, expected improvement
3. Suggest 3 NEW test questions that would catch edge cases we're missing
4. Rate overall system health (1-10) with justification

Respond ONLY with a JSON object (no markdown, no preamble):
{{
  "health_score": 7,
  "health_justification": "...",
  "failure_patterns": [
    {{
      "pattern": "description",
      "root_cause": "why it happens",
      "affected_sector": "sector",
      "affected_pipeline": "pipeline",
      "suggested_fix": "specific fix",
      "expected_improvement": "+N points"
    }}
  ],
  "new_test_questions": [
    {{
      "question": "...",
      "sector": "...",
      "pipeline": "standard",
      "expected_behavior": "what a correct answer looks like",
      "edge_case_type": "what edge case this catches"
    }}
  ],
  "key_insight": "the single most important insight from this analysis",
  "next_action": "the most impactful next step based on this analysis"
}}"""

    if dry_run:
        log("DRY RUN: Would call LLM for analysis", "WARN")
        return {
            "health_score": 5,
            "health_justification": "Dry run placeholder",
            "failure_patterns": [],
            "new_test_questions": [],
            "key_insight": "[dry-run] No analysis performed",
            "next_action": "Run actual analysis",
        }

    log("Calling LLM for deep analysis...")
    response = llm_call(prompt, system_prompt=STRATEGIC_SYSTEM_PROMPT, max_tokens=2000)

    if not response:
        log("LLM call failed for analysis phase", "ERROR")
        return {
            "health_score": 0,
            "health_justification": "Analysis failed (LLM unreachable)",
            "failure_patterns": [],
            "new_test_questions": [],
            "key_insight": "LLM analysis unavailable",
            "next_action": "Retry when LLM proxy is available",
            "error": "LLM call failed",
        }

    analysis = extract_json_from_llm(response)
    if not analysis:
        log(f"Could not parse analysis JSON: {response[:300]}", "WARN")
        analysis = {
            "health_score": 0,
            "health_justification": "JSON parse failed",
            "failure_patterns": [],
            "new_test_questions": [],
            "key_insight": response[:300] if response else "No response",
            "next_action": "Retry analysis",
            "raw_response": response[:1000] if response else None,
        }

    # Log highlights
    log(f"Health: {analysis.get('health_score', '?')}/10 — {analysis.get('health_justification', '?')[:80]}", "OK")
    log(f"Key insight: {analysis.get('key_insight', '?')[:100]}", "STRAT")
    log(f"Next action: {analysis.get('next_action', '?')[:100]}", "STRAT")

    patterns = analysis.get("failure_patterns", [])
    if patterns:
        log(f"Failure patterns ({len(patterns)}):")
        for i, p in enumerate(patterns[:5]):
            log(f"  {i + 1}. {p.get('pattern', '?')[:80]}")
            log(f"     Fix: {p.get('suggested_fix', '?')[:80]}")

    new_qs = analysis.get("new_test_questions", [])
    if new_qs:
        log(f"New test questions ({len(new_qs)}):")
        for q in new_qs[:3]:
            log(f"  - [{q.get('sector', '?')}] {q.get('question', '?')[:80]}")

    # Save analysis
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    analysis_file = os.path.join(ANALYSES_DIR, f"analysis-{ts}.json")
    analysis["baseline_snapshot"] = {
        "sector_avg": baseline.get("sector_avg_score") if baseline else None,
        "pipeline_avg": baseline.get("pipeline_avg_score") if baseline else None,
    }
    with open(analysis_file, "w") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    log(f"Analysis saved: {analysis_file}", "OK")

    return analysis


# ============================================================================
# PHASE 7: REPORT (structured output)
# ============================================================================
def phase_report(strategy, plan, baseline, collected, analysis, state, cycle_start_time):
    """Generate a structured cycle report.

    Returns the report dict.
    """
    log(f"\n{C.BOLD}{'=' * 70}{C.RESET}", "PHASE")
    log(f"{C.BOLD}PHASE 7: REPORT — Generating cycle report{C.RESET}", "PHASE")
    log(f"{'=' * 70}", "PHASE")

    cycle_num = state.get("cycle", 0) + 1
    cycle_duration = round(time.time() - cycle_start_time, 1)

    # Calculate score deltas
    prev_scores = state.get("last_scores", {})
    current_scores = {}
    baseline_scores = {}

    if baseline:
        target_sector = strategy.get("target_sector", "unknown")
        target_pipeline = strategy.get("target_pipeline", "unknown")
        baseline_scores = {
            "overall_avg": baseline.get("overall_avg_score", 0),
            "sector_avg": baseline.get("sector_avg_score", 0),
            "pipeline_avg": baseline.get("pipeline_avg_score", 0),
        }
        current_scores = baseline_scores.copy()

    # Compute deltas
    deltas = {}
    for key in ["overall_avg", "sector_avg", "pipeline_avg"]:
        prev = prev_scores.get(key, 0)
        curr = current_scores.get(key, 0)
        if prev > 0 and curr > 0:
            deltas[key] = round(curr - prev, 1)
        elif curr > 0:
            deltas[key] = 0  # first measurement

    # Determine if improvement was achieved
    sector_delta = deltas.get("sector_avg", 0)
    improved = sector_delta > 0

    report = {
        "cycle": cycle_num,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_s": cycle_duration,
        "strategy": {
            "priority": strategy.get("priority", "?"),
            "category": strategy.get("category", "?"),
            "target_sector": strategy.get("target_sector", "?"),
            "target_pipeline": strategy.get("target_pipeline", "?"),
            "expected_impact": strategy.get("expected_impact", "?"),
        },
        "plan_id": plan.get("plan_id", "?") if plan else None,
        "plan_steps": len(plan.get("actions", [])) if plan else 0,
        "baseline_scores": baseline_scores,
        "current_scores": current_scores,
        "deltas": deltas,
        "improved": improved,
        "sector_delta": sector_delta,
        "analysis": {
            "health_score": analysis.get("health_score", 0) if analysis else 0,
            "key_insight": analysis.get("key_insight", "?") if analysis else "No analysis",
            "failure_pattern_count": len(analysis.get("failure_patterns", [])) if analysis else 0,
            "new_questions_generated": len(analysis.get("new_test_questions", [])) if analysis else 0,
        },
        "next_action": analysis.get("next_action", "?") if analysis else "Retry cycle",
        "pipeline_health": strategy.get("_pipeline_health"),
        "suggested_commands": [],
    }

    # Build suggested commands for next cycle
    if analysis:
        for pattern in analysis.get("failure_patterns", [])[:3]:
            fix = pattern.get("suggested_fix", "")
            if fix:
                report["suggested_commands"].append(f"# {pattern.get('pattern', 'Fix')}: {fix}")

    # Add ready-to-execute commands
    target_sector = strategy.get("target_sector", "finance")
    target_pipeline = strategy.get("target_pipeline", "standard")
    report["suggested_commands"].extend([
        f"python3 eval/parallel-eval.py --sector {target_sector} --pipeline {target_pipeline}",
        f"python3 eval/continuous-judge.py --suggestions",
        f"python3 ops/metrics-collector.py --profile {target_pipeline}",
    ])
    if analysis and analysis.get("next_action"):
        report["suggested_commands"].append(f"# LLM suggestion: {analysis['next_action']}")

    # Save full report
    report_file = os.path.join(REPORTS_DIR, f"cycle-{cycle_num}.json")
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Append summary to JSONL
    ph = report.get("pipeline_health") or {}
    pipelines_ok = sum(1 for p in ph.values() if p.get("status") == "ok")
    pipelines_total = len(ph) if ph else 0
    summary = {
        "cycle": cycle_num,
        "timestamp": report["timestamp"],
        "duration_s": cycle_duration,
        "priority": strategy.get("priority", "?")[:80],
        "target": f"{target_sector}/{target_pipeline}",
        "sector_score": current_scores.get("sector_avg", 0),
        "sector_delta": sector_delta,
        "improved": improved,
        "health": analysis.get("health_score", 0) if analysis else 0,
        "pipelines_ok": f"{pipelines_ok}/{pipelines_total}" if pipelines_total else "?",
    }
    log_jsonl(CYCLE_SUMMARY_LOG, summary)

    # Print human-readable report
    _print_cycle_report(report)

    log(f"Report saved: {report_file}", "OK")

    return report


def _print_cycle_report(report):
    """Pretty-print a cycle report to stdout."""
    print()
    print(f"  {C.CYAN}{'=' * 70}{C.RESET}")
    print(f"  {C.BOLD}  AGENTIC LOOP — CYCLE {report['cycle']} REPORT{C.RESET}")
    print(f"  {C.CYAN}{'=' * 70}{C.RESET}")
    print()

    strat = report.get("strategy", {})
    print(f"  {C.BOLD}Priority:{C.RESET}  {strat.get('priority', '?')[:65]}")
    print(f"  {C.BOLD}Target:{C.RESET}    {strat.get('target_sector', '?')} / {strat.get('target_pipeline', '?')}")
    print(f"  {C.BOLD}Category:{C.RESET}  {strat.get('category', '?')}")
    print(f"  {C.BOLD}Duration:{C.RESET}  {report.get('duration_s', 0)}s")
    print()

    # Pipeline health
    ph = report.get("pipeline_health")
    if ph:
        print(f"  {C.BOLD}Pipeline Health:{C.RESET}")
        for pname in sorted(ph.keys()):
            pdata = ph[pname]
            status = pdata.get("status", "unknown")
            if status == "ok":
                icon = f"{C.GREEN}OK{C.RESET}"
            else:
                icon = f"{C.RED}BROKEN{C.RESET}"
            err_str = f" — {pdata.get('error', '')[:50]}" if pdata.get("error") else ""
            lat_str = f"{pdata.get('latency_s', '?')}s"
            print(f"    {pname:<15} {icon}  (latency={lat_str}, len={pdata.get('response_length', 0)}){err_str}")
        print()

    # Scores
    bl = report.get("baseline_scores", {})
    dl = report.get("deltas", {})
    if bl:
        print(f"  {C.BOLD}Scores:{C.RESET}")
        for key, label in [("overall_avg", "Overall"), ("sector_avg", "Sector"), ("pipeline_avg", "Pipeline")]:
            val = bl.get(key, 0)
            delta = dl.get(key)
            delta_str = ""
            if delta is not None and delta != 0:
                color = C.GREEN if delta > 0 else C.RED
                delta_str = f" ({color}{'+' if delta > 0 else ''}{delta}{C.RESET})"
            print(f"    {label}: {val}/100{delta_str}")
        print()

    # Improvement status
    if report.get("improved"):
        print(f"  {C.GREEN}{C.BOLD}  IMPROVED (+{report.get('sector_delta', 0)} pts){C.RESET}")
    else:
        delta = report.get("sector_delta", 0)
        if delta < 0:
            print(f"  {C.RED}{C.BOLD}  REGRESSION ({delta} pts){C.RESET}")
        else:
            print(f"  {C.YELLOW}{C.BOLD}  NO CHANGE (delta={delta}){C.RESET}")
    print()

    # Analysis
    a = report.get("analysis", {})
    print(f"  {C.BOLD}Analysis:{C.RESET}")
    print(f"    Health:    {a.get('health_score', '?')}/10")
    print(f"    Insight:   {a.get('key_insight', '?')[:70]}")
    print(f"    Failures:  {a.get('failure_pattern_count', 0)} patterns identified")
    print(f"    New Q&A:   {a.get('new_questions_generated', 0)} questions generated")
    print()

    # Next action
    print(f"  {C.BOLD}Next action:{C.RESET} {report.get('next_action', '?')[:70]}")

    # Commands
    cmds = report.get("suggested_commands", [])
    if cmds:
        print(f"\n  {C.BOLD}Suggested commands:{C.RESET}")
        for cmd in cmds[:5]:
            print(f"    {C.DIM}{cmd}{C.RESET}")

    print()
    print(f"  {C.CYAN}{'=' * 70}{C.RESET}")
    print()


# ============================================================================
# FULL CYCLE — Run all 6 phases
# ============================================================================
def run_cycle(state, dry_run=False):
    """Run one complete agentic loop cycle (7 phases).

    Returns (report, updated_state) or (None, state) on failure.
    """
    cycle_start = time.time()
    cycle_num = state.get("cycle", 0) + 1

    print()
    print(f"  {C.MAGENTA}{C.BOLD}{'#' * 70}{C.RESET}")
    print(f"  {C.MAGENTA}{C.BOLD}  AGENTIC LOOP — CYCLE {cycle_num}{C.RESET}")
    print(f"  {C.MAGENTA}{C.BOLD}  {datetime.now(timezone.utc).isoformat()}{C.RESET}")
    print(f"  {C.MAGENTA}{C.BOLD}{'#' * 70}{C.RESET}")
    print()

    # Build system context
    log("Building system context...")
    ctx = build_system_context()

    # Phase 1: Strategize
    if _shutdown_requested:
        log("Shutdown requested, aborting cycle", "WARN")
        return None, state

    strategy = phase_strategize(ctx, state, dry_run=dry_run)
    if not strategy:
        log("Strategy phase failed, aborting cycle", "ERROR")
        return None, state

    # ── SMART OVERRIDE: Force fix_pipeline when smoke test detects broken ──
    # The LLM often picks data_gap even when pipelines return 0%. Override it.
    pipeline_health = ctx.get("pipeline_health", {})
    broken_pipelines = [
        p for p, d in pipeline_health.items()
        if d.get("status") != "ok"
    ]
    if broken_pipelines and strategy.get("category") != "fix_pipeline":
        # Classify broken type
        for bp in broken_pipelines:
            bdata = pipeline_health[bp]
            latency = bdata.get("latency_s", 0)
            err = bdata.get("error", "")
            if latency >= 60 or "timeout" in str(err).lower():
                failure_type = "TIMEOUT (likely Neo4j/embedding hang)"
            elif latency <= 10:
                failure_type = "INSTANT FAIL (likely credential/config error)"
            else:
                failure_type = f"ERROR ({err[:50]})"
            log(f"OVERRIDE: {bp} is BROKEN — {failure_type}", "WARN")

        # Pick the first broken pipeline to fix
        target_bp = broken_pipelines[0]
        old_cat = strategy.get("category")
        old_target = strategy.get("target_pipeline")
        strategy["category"] = "fix_pipeline"
        strategy["target_pipeline"] = target_bp
        strategy["priority"] = f"Fix broken {target_bp} pipeline ({pipeline_health[target_bp].get('error', 'unknown')[:80]})"
        strategy["reasoning"] = (
            f"OVERRIDDEN by smart detection: LLM chose '{old_cat}' for '{old_target}' "
            f"but {len(broken_pipelines)} pipeline(s) are broken: {', '.join(broken_pipelines)}. "
            f"A broken pipeline = 0% accuracy FOREVER. Must fix before any data work."
        )
        log(f"OVERRIDE: Forced fix_pipeline for {target_bp} (LLM wanted {old_cat}/{old_target})", "WARN")

    # ── ANTI-STUCK: If same target for 3+ cycles with no improvement, rotate ──
    consec = state.get("consecutive_no_improvement", 0)
    last_sector = state.get("last_target_sector")
    last_pipeline = state.get("last_target_pipeline")
    if (consec >= 3
        and strategy.get("target_sector") == last_sector
        and strategy.get("target_pipeline") == last_pipeline
        and strategy.get("category") != "fix_pipeline"):
        # Find a different sector to work on
        all_sectors = ["finance", "btp", "juridique", "industrie"]
        other_sectors = [s for s in all_sectors if s != last_sector]
        if other_sectors:
            new_sector = other_sectors[0]  # Pick the first different one
            log(f"ANTI-STUCK: {consec} cycles on {last_sector}/{last_pipeline} with no improvement. "
                f"Rotating to {new_sector}", "WARN")
            strategy["target_sector"] = new_sector
            strategy["reasoning"] = (
                f"ROTATED: {consec} consecutive cycles targeted {last_sector}/{last_pipeline} "
                f"without improvement. Trying {new_sector} for fresh progress."
            )

    # Phase 2: Plan
    if _shutdown_requested:
        log("Shutdown requested, aborting cycle", "WARN")
        return None, state

    plan = phase_plan(strategy, ctx, state, dry_run=dry_run)
    if not plan:
        log("Plan phase failed, continuing with minimal plan", "WARN")
        plan = {
            "plan_id": f"plan-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            "actions": [],
            "test_questions": [],
            "success_metric": "Any improvement",
        }

    # Phase 3: BUILD — Execute the plan (ingest, deploy, modify)
    if _shutdown_requested:
        log("Shutdown requested, aborting cycle", "WARN")
        return None, state

    build_result = phase_build(strategy, plan, state, dry_run=dry_run)

    # Phase 4: Observe (measure impact after build)
    if _shutdown_requested:
        log("Shutdown requested, aborting cycle", "WARN")
        return None, state

    baseline = phase_observe(strategy, plan, state, dry_run=dry_run)

    # Phase 5: Collect
    if _shutdown_requested:
        log("Shutdown requested, aborting cycle", "WARN")
        return None, state

    collected = phase_collect(strategy, plan, baseline, state, dry_run=dry_run)
    # Attach build info to collected data
    if collected and build_result:
        collected["build_result"] = {
            "success": build_result.get("success", False),
            "docs_ingested": build_result.get("docs_ingested", 0),
            "vectors_added": build_result.get("vectors_added", 0),
            "actions_taken": len(build_result.get("actions_taken", [])),
        }

    # Phase 6: Analyze
    if _shutdown_requested:
        log("Shutdown requested, aborting cycle", "WARN")
        return None, state

    analysis = phase_analyze(strategy, plan, baseline, collected, ctx, state, dry_run=dry_run)

    # Phase 7: Report
    report = phase_report(strategy, plan, baseline, collected, analysis, state, cycle_start)
    # Attach build summary to report
    if report and build_result:
        report["build_summary"] = {
            "success": build_result.get("success", False),
            "docs_ingested": build_result.get("docs_ingested", 0),
            "vectors_added": build_result.get("vectors_added", 0),
            "smoke_test": build_result.get("smoke_test"),
            "deployment": build_result.get("deployment"),
        }

    # Update state
    state["cycle"] = cycle_num
    state["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
    state["last_priority"] = strategy.get("priority")
    state["last_target_sector"] = strategy.get("target_sector")
    state["last_target_pipeline"] = strategy.get("target_pipeline")

    # Track scores for delta computation
    if baseline:
        state["last_scores"] = {
            "overall_avg": baseline.get("overall_avg_score", 0),
            "sector_avg": baseline.get("sector_avg_score", 0),
            "pipeline_avg": baseline.get("pipeline_avg_score", 0),
        }

    # Track improvement / regression
    improved = report.get("improved", False)
    sector_delta = report.get("sector_delta", 0)

    if improved:
        state["consecutive_no_improvement"] = 0
        state["total_improvements"] = state.get("total_improvements", 0) + 1
        log(f"Improvement achieved! Total improvements: {state['total_improvements']}", "OK")
    elif sector_delta < 0:
        state["consecutive_no_improvement"] = state.get("consecutive_no_improvement", 0) + 1
        state["total_regressions"] = state.get("total_regressions", 0) + 1
        log(f"REGRESSION detected ({sector_delta} pts). "
            f"Consecutive no-improvement: {state['consecutive_no_improvement']}", "WARN")
    else:
        state["consecutive_no_improvement"] = state.get("consecutive_no_improvement", 0) + 1
        log(f"No improvement. Consecutive: {state['consecutive_no_improvement']}", "WARN")

    save_state(state)
    return report, state


# ============================================================================
# SINGLE PHASE RUNNERS
# ============================================================================
def run_single_phase(phase_name, dry_run=False):
    """Run a single named phase."""
    state = load_state()
    ctx = build_system_context()

    if phase_name == "strategize":
        strategy = phase_strategize(ctx, state, dry_run=dry_run)
        if strategy:
            print(json.dumps(strategy, indent=2, ensure_ascii=False))

    elif phase_name == "plan":
        # Need a strategy first — use last or generate
        strategy = phase_strategize(ctx, state, dry_run=dry_run)
        if strategy:
            plan = phase_plan(strategy, ctx, state, dry_run=dry_run)
            if plan:
                print(json.dumps(plan, indent=2, ensure_ascii=False))

    elif phase_name == "build":
        # Need strategy + plan first
        strategy = phase_strategize(ctx, state, dry_run=dry_run)
        if strategy:
            plan = phase_plan(strategy, ctx, state, dry_run=dry_run)
            if plan:
                build_result = phase_build(strategy, plan, state, dry_run=dry_run)
                if build_result:
                    print(json.dumps(build_result, indent=2, ensure_ascii=False, default=str))

    elif phase_name == "observe":
        strategy = {
            "target_sector": state.get("last_target_sector", _find_weakest_sector(ctx)),
            "target_pipeline": state.get("last_target_pipeline", "standard"),
        }
        baseline = phase_observe(strategy, None, state, dry_run=dry_run)
        if baseline:
            print(json.dumps(baseline, indent=2, ensure_ascii=False))

    elif phase_name == "collect":
        strategy = {
            "target_sector": state.get("last_target_sector", _find_weakest_sector(ctx)),
            "target_pipeline": state.get("last_target_pipeline", "standard"),
        }
        collected = phase_collect(strategy, None, None, state, dry_run=dry_run)
        if collected:
            print(json.dumps(collected, indent=2, ensure_ascii=False, default=str))

    elif phase_name == "analyze":
        strategy = {
            "target_sector": state.get("last_target_sector", _find_weakest_sector(ctx)),
            "target_pipeline": state.get("last_target_pipeline", "standard"),
            "priority": state.get("last_priority", "Unknown"),
            "category": "unknown",
        }
        # Read baseline from latest file
        baseline = None
        baselines = sorted(
            [f for f in os.listdir(BASELINES_DIR) if f.endswith(".json")]
        ) if os.path.exists(BASELINES_DIR) else []
        if baselines:
            with open(os.path.join(BASELINES_DIR, baselines[-1])) as f:
                baseline = json.load(f)

        analysis = phase_analyze(strategy, None, baseline, None, ctx, state, dry_run=dry_run)
        if analysis:
            print(json.dumps(analysis, indent=2, ensure_ascii=False))

    elif phase_name == "report":
        show_latest_report()

    else:
        log(f"Unknown phase: {phase_name}. Valid: strategize, plan, build, observe, collect, analyze, report", "ERROR")


# ============================================================================
# REPORT DISPLAY
# ============================================================================
def show_latest_report():
    """Display the latest cycle report."""
    if not os.path.exists(REPORTS_DIR):
        print("No reports yet. Run a cycle first.")
        return

    reports = sorted([f for f in os.listdir(REPORTS_DIR) if f.endswith(".json")])
    if not reports:
        print("No reports yet. Run a cycle first.")
        return

    latest_file = os.path.join(REPORTS_DIR, reports[-1])
    with open(latest_file) as f:
        report = json.load(f)

    _print_cycle_report(report)
    print(f"  Report file: {latest_file}")


def show_history():
    """Display all cycle summaries."""
    if not os.path.exists(CYCLE_SUMMARY_LOG):
        print("No cycle history yet. Run a cycle first.")
        return

    print()
    print(f"  {C.CYAN}{'=' * 80}{C.RESET}")
    print(f"  {C.BOLD}  AGENTIC LOOP — CYCLE HISTORY{C.RESET}")
    print(f"  {C.CYAN}{'=' * 80}{C.RESET}")
    print()
    print(f"  {'Cycle':>5}  {'Timestamp':<22} {'Target':<20} {'Score':>6} {'Delta':>7} {'Health':>7}  {'Priority'}")
    print(f"  {'-' * 5}  {'-' * 22} {'-' * 20} {'-' * 6} {'-' * 7} {'-' * 7}  {'-' * 30}")

    with open(CYCLE_SUMMARY_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                cycle = entry.get("cycle", "?")
                ts = entry.get("timestamp", "?")[:19]
                target = entry.get("target", "?")
                score = entry.get("sector_score", 0)
                delta = entry.get("sector_delta", 0)
                health = entry.get("health", 0)
                priority = entry.get("priority", "?")[:35]
                improved = entry.get("improved", False)

                # Color the delta
                if delta > 0:
                    delta_str = f"{C.GREEN}+{delta:>5.1f}{C.RESET}"
                elif delta < 0:
                    delta_str = f"{C.RED}{delta:>6.1f}{C.RESET}"
                else:
                    delta_str = f"  {delta:>4.1f}"

                # Color the status icon
                icon = f"{C.GREEN}+{C.RESET}" if improved else f"{C.YELLOW}={C.RESET}"

                print(f"  {cycle:>5}  {ts:<22} {target:<20} {score:>5.1f} {delta_str} {health:>6}/10  {icon} {priority}")

            except json.JSONDecodeError:
                continue

    print()
    print(f"  {C.CYAN}{'=' * 80}{C.RESET}")

    # Summary stats
    state = load_state()
    print(f"\n  Total cycles:         {state.get('cycle', 0)}")
    print(f"  Total improvements:   {state.get('total_improvements', 0)}")
    print(f"  Total regressions:    {state.get('total_regressions', 0)}")
    print(f"  Consec. no-improve:   {state.get('consecutive_no_improvement', 0)}")
    print(f"  Last cycle at:        {state.get('last_cycle_at', 'never')}")
    print()


# ============================================================================
# DAEMON MODE
# ============================================================================
def run_daemon(interval_s, dry_run=False):
    """Run the agentic loop continuously at the given interval."""
    global _shutdown_requested
    log(f"Starting agentic loop daemon (interval: {interval_s}s = {interval_s / 60:.0f} min)", "OK")
    log(f"Press Ctrl+C to stop gracefully", "INFO")

    state = load_state()

    while not _shutdown_requested:
        try:
            report, state = run_cycle(state, dry_run=dry_run)

            if report:
                # Check for auto-stop on consecutive REGRESSIONS (not just no-improvement)
                consec_regr = state.get("total_regressions", 0)
                consec_no_imp = state.get("consecutive_no_improvement", 0)
                if consec_regr >= 3:
                    log(f"AUTO-STOP: {consec_regr} regressions detected — need human review", "ERROR")
                    _print_failure_report(state)
                    break
                if consec_no_imp >= MAX_CONSECUTIVE_FAILURES:
                    log(f"AUTO-PAUSE: {consec_no_imp} cycles without improvement — escalating strategy", "WARN")
                    _print_failure_report(state)
                    # ESCALATION: Run infra-test to get real component status
                    infra_test = os.path.join(REPO_ROOT, "ops", "infra-test.py")
                    if os.path.exists(infra_test):
                        log("ESCALATION: Running infrastructure tests to find root cause...", "WARN")
                        rc, out, err = run_script(infra_test, ["--json"], timeout_s=120)
                        if rc == 0 and out:
                            try:
                                infra_results = json.loads(out)
                                failed_tests = [t for t in infra_results.get("tests", [])
                                               if t.get("status") != "PASS"]
                                if failed_tests:
                                    log(f"INFRA FAILURES FOUND: {len(failed_tests)} tests failed", "ERROR")
                                    for ft in failed_tests[:5]:
                                        log(f"  FAIL: {ft.get('component', '?')}/{ft.get('test', '?')}: {ft.get('detail', '?')[:80]}", "ERROR")
                                    # Save escalation report
                                    esc_file = os.path.join(REPORTS_DIR, f"escalation-{state.get('cycle', 0)}.json")
                                    with open(esc_file, "w") as ef:
                                        json.dump({"cycle": state.get("cycle", 0),
                                                   "infra_failures": failed_tests,
                                                   "consecutive_no_improvement": consec_no_imp,
                                                   "timestamp": datetime.now(timezone.utc).isoformat()}, ef, indent=2)
                            except (json.JSONDecodeError, KeyError):
                                pass
                    # Reset counter but CHANGE strategy — force different sector/pipeline
                    state["consecutive_no_improvement"] = 0
                    state["_escalated_at"] = datetime.now(timezone.utc).isoformat()
                    save_state(state)

            if _shutdown_requested:
                break

            # Wait for next cycle
            log(f"Next cycle in {interval_s}s ({interval_s / 60:.0f} min). Ctrl+C to stop.")
            for _ in range(int(interval_s)):
                if _shutdown_requested:
                    break
                time.sleep(1)

        except KeyboardInterrupt:
            _shutdown_requested = True
            break
        except Exception as e:
            log(f"Cycle error: {e}", "ERROR")
            log(traceback.format_exc(), "ERROR")
            # Wait before retrying
            log(f"Retrying in 60s...")
            for _ in range(60):
                if _shutdown_requested:
                    break
                time.sleep(1)

    log("Daemon stopped.", "OK")
    save_state(state)


def _print_failure_report(state):
    """Print a structured failure report when auto-stop is triggered."""
    print()
    print(f"  {C.RED}{'=' * 70}{C.RESET}")
    print(f"  {C.RED}{C.BOLD}  AUTO-STOP FAILURE REPORT{C.RESET}")
    print(f"  {C.RED}{'=' * 70}{C.RESET}")
    print()
    print(f"  Cycles completed:            {state.get('cycle', 0)}")
    print(f"  Consecutive no-improvement:  {state.get('consecutive_no_improvement', 0)}")
    print(f"  Total improvements:          {state.get('total_improvements', 0)}")
    print(f"  Total regressions:           {state.get('total_regressions', 0)}")
    print(f"  Last priority:               {state.get('last_priority', '?')}")
    print(f"  Last target:                 {state.get('last_target_sector', '?')}/{state.get('last_target_pipeline', '?')}")
    print()
    print(f"  {C.BOLD}Possible causes:{C.RESET}")
    print(f"    1. The identified improvements require n8n workflow changes (manual intervention)")
    print(f"    2. Data gaps that can only be filled by ingesting new documents")
    print(f"    3. Rate limiting from Groq/HF Spaces causing unreliable eval results")
    print(f"    4. Scoring too strict for current data coverage")
    print()
    print(f"  {C.BOLD}Recommended actions:{C.RESET}")
    print(f"    1. Review latest analysis: ls {ANALYSES_DIR}/")
    print(f"    2. Check improvement suggestions: python3 eval/continuous-judge.py --suggestions")
    print(f"    3. Run expert discovery: python3 eval/expert-discovery.py --sector all")
    print(f"    4. Manual review of n8n workflows for the target sector")
    print()
    print(f"  {C.RED}{'=' * 70}{C.RESET}")
    print()


# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Agentic Loop -- Master Continuous Improvement Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           Run one complete cycle
  %(prog)s --daemon 1800             Continuous loop every 30 min
  %(prog)s --phase strategize        Run strategy analysis only
  %(prog)s --phase analyze           Run deep analysis only
  %(prog)s --report                  Show latest cycle report
  %(prog)s --history                 Show all cycle summaries
  %(prog)s --dry-run                 Plan without executing scripts
        """,
    )

    parser.add_argument(
        "--daemon", type=int, metavar="SECONDS",
        help="Run continuously at the given interval (seconds)",
    )
    parser.add_argument(
        "--phase",
        choices=["strategize", "plan", "build", "observe", "collect", "analyze", "report"],
        help="Run a single phase only",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Show the latest cycle report",
    )
    parser.add_argument(
        "--history", action="store_true",
        help="Show all cycle summaries",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run without executing external scripts or making LLM calls",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Reset cycle counter and state (does not delete reports)",
    )

    args = parser.parse_args()

    # Ensure directory structure
    ensure_directories()

    # Banner
    print()
    print(f"  {C.MAGENTA}{'=' * 70}{C.RESET}")
    print(f"  {C.MAGENTA}{C.BOLD}  NOMOS SECTOR AI EXPERT — AGENTIC LOOP{C.RESET}")
    print(f"  {C.MAGENTA}{C.BOLD}  Master Continuous Improvement Orchestrator{C.RESET}")
    print(f"  {C.MAGENTA}{'=' * 70}{C.RESET}")
    print(f"  Time:       {datetime.now(timezone.utc).isoformat()}")
    print(f"  Repo:       {REPO_ROOT}")
    print(f"  LiteLLM:    {LITELLM_URL[:50]}...")
    print(f"  Groq key:   {'SET' if GROQ_API_KEY else 'MISSING'}")

    state = load_state()
    print(f"  Cycle:      {state.get('cycle', 0)} completed")
    print(f"  Last run:   {state.get('last_cycle_at', 'never')}")
    print(f"  Improvs:    {state.get('total_improvements', 0)} / Regressions: {state.get('total_regressions', 0)}")
    if args.dry_run:
        print(f"  {C.YELLOW}Mode:       DRY RUN (no external calls){C.RESET}")
    print()

    # Handle --reset
    if args.reset:
        log("Resetting loop state...", "WARN")
        state = {
            "cycle": 0,
            "last_cycle_at": None,
            "last_priority": None,
            "last_scores": {},
            "consecutive_no_improvement": 0,
            "total_improvements": 0,
            "total_regressions": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        save_state(state)
        log("State reset. Reports and analyses preserved.", "OK")
        return

    # Handle --report
    if args.report:
        show_latest_report()
        return

    # Handle --history
    if args.history:
        show_history()
        return

    # Handle --phase
    if args.phase:
        run_single_phase(args.phase, dry_run=args.dry_run)
        return

    # Handle --daemon
    if args.daemon:
        run_daemon(args.daemon, dry_run=args.dry_run)
        return

    # Default: run one cycle
    report, state = run_cycle(state, dry_run=args.dry_run)
    if report:
        log(f"Cycle {report['cycle']} complete.", "OK")
        if report.get("improved"):
            log(f"Improvement achieved: +{report.get('sector_delta', 0)} pts", "OK")
        else:
            log(f"No improvement this cycle. Consider: {report.get('next_action', '?')[:80]}", "WARN")
    else:
        log("Cycle failed. Check logs above.", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
