#!/usr/bin/env python3
"""
PRE-FLIGHT CHECK — Validates everything before eval runs.
===========================================================
Runs automatically before every evaluation to prevent wasted time.

Checks:
  1. Dataset integrity (via data_validator)
  2. N8N_HOST connectivity
  3. OpenRouter API key presence (for local LLM fallback)
  4. Environment variables
  5. Output directories exist
  6. Disk space

Usage:
  python eval/preflight.py                     # Check everything
  python eval/preflight.py --dataset phase-2   # Check specific dataset
  python eval/preflight.py --quick             # Skip connectivity checks
"""

import json
import os
import sys
import time

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(EVAL_DIR)
sys.path.insert(0, EVAL_DIR)

from data_validator import validate_all, print_report


def check_env_vars():
    """Check required environment variables."""
    issues = []

    # N8N_HOST
    n8n_host = os.environ.get("N8N_HOST", "")
    if not n8n_host:
        issues.append("N8N_HOST not set (will default to https://lbjlincoln-nomos-rag-engine.hf.space)")

    # OpenRouter API key (for local LLM fallback)
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not or_key:
        issues.append("OPENROUTER_API_KEY not set (local LLM fallback will not work)")

    return issues


def check_n8n_connectivity(host=None):
    """Check if n8n is reachable."""
    from urllib import request, error

    host = host or os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
    try:
        req = request.Request(f"{host}/healthz", method="GET")
        with request.urlopen(req, timeout=10) as resp:
            if resp.getcode() == 200:
                return None  # OK
            return f"n8n responded with HTTP {resp.getcode()}"
    except error.HTTPError as e:
        # Some n8n versions return 404 for /healthz but 200 for /
        if e.code == 404:
            try:
                req2 = request.Request(host, method="GET")
                with request.urlopen(req2, timeout=10) as resp2:
                    return None  # OK
            except:
                pass
        return f"n8n unreachable at {host}: HTTP {e.code}"
    except Exception as e:
        return f"n8n unreachable at {host}: {e}"


def check_openrouter():
    """Check if OpenRouter API is reachable."""
    from urllib import request, error

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return "OPENROUTER_API_KEY not set"

    try:
        req = request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET"
        )
        with request.urlopen(req, timeout=10) as resp:
            if resp.getcode() == 200:
                return None
            return f"OpenRouter responded with HTTP {resp.getcode()}"
    except Exception as e:
        return f"OpenRouter unreachable: {e}"


def check_directories():
    """Check that required output directories exist."""
    dirs = [
        os.path.join(REPO_ROOT, "docs"),
        os.path.join(REPO_ROOT, "logs"),
        os.path.join(REPO_ROOT, "logs", "pipeline-results"),
        os.path.join(REPO_ROOT, "logs", "iterative-eval"),
    ]
    issues = []
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
            issues.append(f"Created missing directory: {d}")
    return issues


def check_disk_space():
    """Check available disk space."""
    import shutil
    usage = shutil.disk_usage(REPO_ROOT)
    free_gb = usage.free / (1024 ** 3)
    if free_gb < 1.0:
        return f"Low disk space: {free_gb:.1f} GB free"
    return None


def run_preflight(dataset=None, quick=False):
    """Run all pre-flight checks.
    Returns (passed: bool, issues: list[str], warnings: list[str])
    """
    issues = []
    warnings = []

    print("  Pre-flight: Checking environment...")
    env_issues = check_env_vars()
    warnings.extend(env_issues)

    print("  Pre-flight: Checking directories...")
    dir_issues = check_directories()
    warnings.extend(dir_issues)

    print("  Pre-flight: Checking disk space...")
    disk_issue = check_disk_space()
    if disk_issue:
        issues.append(disk_issue)

    print("  Pre-flight: Validating datasets...")
    validation = validate_all(dataset=dataset)
    if not validation.valid:
        issues.extend(validation.errors[:10])
    warnings.extend(validation.warnings[:10])

    if not quick:
        print("  Pre-flight: Checking n8n connectivity...")
        n8n_issue = check_n8n_connectivity()
        if n8n_issue:
            warnings.append(n8n_issue)

        print("  Pre-flight: Checking OpenRouter...")
        or_issue = check_openrouter()
        if or_issue:
            warnings.append(or_issue)

    passed = len(issues) == 0
    return passed, issues, warnings


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pre-flight checks for RAG evaluation")
    parser.add_argument("--dataset", choices=["phase-1", "phase-2", "all"], default=None)
    parser.add_argument("--quick", action="store_true", help="Skip connectivity checks")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Load env
    env_file = os.path.join(REPO_ROOT, ".env.local")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    passed, issues, warnings = run_preflight(dataset=args.dataset, quick=args.quick)

    if args.json:
        print(json.dumps({
            "passed": passed,
            "issues": issues,
            "warnings": warnings,
        }, indent=2))
    else:
        print("\n" + "=" * 60)
        print("  PRE-FLIGHT CHECK RESULTS")
        print("=" * 60)
        if passed:
            print("  Status: READY")
        else:
            print("  Status: BLOCKED — fix issues before running eval")

        if issues:
            print(f"\n  ISSUES ({len(issues)}):")
            for i in issues:
                print(f"    [BLOCK] {i}")

        if warnings:
            print(f"\n  WARNINGS ({len(warnings)}):")
            for w in warnings:
                print(f"    [WARN] {w}")

        print("=" * 60)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
