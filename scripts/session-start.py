#!/usr/bin/env python3
"""Session start script — run at the beginning of each Claude Code session.

Usage: python3 scripts/session-start.py

This script:
1. Checks environment variables
2. Tests n8n connectivity
3. Shows current project status
4. Identifies the priority pipeline
5. Checks if MCP dependencies are available
"""

import os
import sys
import json
import subprocess

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}")

def check_env():
    required = ["N8N_HOST", "N8N_API_KEY", "PINECONE_API_KEY", "OPENROUTER_API_KEY"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"{RED}Missing env vars: {', '.join(missing)}{RESET}")
        print(f"{YELLOW}Run: copy credentials from CLAUDE.md{RESET}")
        return False
    print(f"{GREEN}All required env vars set{RESET}")
    return True

def check_n8n():
    try:
        import urllib.request
        host = os.environ.get("N8N_HOST", "http://34.136.180.66:5678")
        api_key = os.environ.get("N8N_API_KEY", "")
        req = urllib.request.Request(
            f"{host}/api/v1/workflows",
            headers={"X-N8N-API-KEY": api_key}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            count = len(data.get("data", []))
            print(f"{GREEN}n8n connected: {count} workflows found{RESET}")
            return True
    except Exception as e:
        print(f"{RED}n8n connection failed: {e}{RESET}")
        return False

def show_status():
    status_path = os.path.join(ROOT, "docs", "status.json")
    if not os.path.exists(status_path):
        print(f"{YELLOW}No status.json found. Run: python3 eval/generate_status.py{RESET}")
        return

    with open(status_path) as f:
        status = json.load(f)

    phase = status.get("phase", {})
    print(f"\n{BOLD}Phase: {phase.get('current')} - {phase.get('name')}{RESET}")
    print(f"Gates passed: {'YES' if phase.get('gates_passed') else 'NO'}")

    print(f"\n{'Pipeline':<15} {'Accuracy':>10} {'Tested':>8} {'Target':>8} {'Status':>10}")
    print("-" * 55)

    pipelines = status.get("pipelines", {})
    worst_gap = 0
    worst_pipeline = None

    for name, data in pipelines.items():
        acc = data.get("accuracy", 0)
        tested = data.get("tested", 0)
        target = data.get("target", 0)
        met = data.get("met", False)
        gap = data.get("gap", 0)

        status_str = f"{GREEN}PASS{RESET}" if met else f"{RED}FAIL{RESET}"
        print(f"{name:<15} {acc:>9.1f}% {tested:>8} {target:>7.0f}% {status_str}")

        if gap < worst_gap:
            worst_gap = gap
            worst_pipeline = name

    overall = status.get("overall", {})
    print(f"\n{BOLD}Overall: {overall.get('accuracy', 0):.1f}% (target: {overall.get('target', 75)}%){RESET}")

    if worst_pipeline:
        print(f"\n{YELLOW}>>> PRIORITY: Fix {worst_pipeline} pipeline (gap: {worst_gap:+.1f}pp){RESET}")

    blockers = status.get("blockers", [])
    if blockers:
        print(f"\n{RED}Blockers:{RESET}")
        for b in blockers:
            print(f"  - {b}")

def show_session_state():
    state_path = os.path.join(ROOT, "context", "session-state.md")
    if os.path.exists(state_path):
        with open(state_path) as f:
            content = f.read()
        if "Ce qui reste" in content:
            lines = content.split("\n")
            in_section = False
            print(f"\n{BOLD}Remaining from last session:{RESET}")
            for line in lines:
                if "Ce qui reste" in line:
                    in_section = True
                    continue
                if in_section:
                    if line.startswith("---") or (line.startswith("#") and "Ce qui reste" not in line):
                        break
                    if line.strip():
                        print(f"  {line.strip()}")

def check_git():
    try:
        result = subprocess.run(["git", "branch", "--show-current"],
                              capture_output=True, text=True, cwd=ROOT)
        branch = result.stdout.strip()
        print(f"Git branch: {branch}")

        result = subprocess.run(["git", "status", "--short"],
                              capture_output=True, text=True, cwd=ROOT)
        changes = result.stdout.strip()
        if changes:
            count = len(changes.split("\n"))
            print(f"{YELLOW}{count} uncommitted changes{RESET}")
        else:
            print(f"{GREEN}Working tree clean{RESET}")
    except Exception as e:
        print(f"{RED}Git check failed: {e}{RESET}")

def main():
    print_header("SESSION START - Multi-RAG Orchestrator SOTA 2026")

    print(f"\n{BOLD}1. Environment{RESET}")
    env_ok = check_env()

    print(f"\n{BOLD}2. Git Status{RESET}")
    check_git()

    if env_ok:
        print(f"\n{BOLD}3. n8n Connectivity{RESET}")
        check_n8n()

    print(f"\n{BOLD}4. Project Status{RESET}")
    show_status()

    print(f"\n{BOLD}5. Last Session{RESET}")
    show_session_state()

    print(f"\n{BOLD}{GREEN}Ready. Follow context/workflow-process.md for iteration protocol.{RESET}")

if __name__ == "__main__":
    main()
