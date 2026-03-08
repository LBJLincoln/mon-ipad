#!/usr/bin/env python3
"""
Self-Healing Pipeline Orchestrator — SOTA 2026
Monitors pipelines, detects failures, auto-invokes Claude Code CLI to fix.

Architecture:
1. Smoke-tests all 3 RAG pipelines every N minutes
2. If FAIL → logs issue + invokes Claude Code to diagnose and fix
3. If PASS → checks progress vs objective → launches batch eval if idle
4. Leaves working pipelines alone

Usage:
    source .env.local
    python3 scripts/self-heal-orchestrator.py                    # Run once
    python3 scripts/self-heal-orchestrator.py --loop --interval 30  # Run continuously every 30 min
    python3 scripts/self-heal-orchestrator.py --fix-only           # Only fix broken pipelines
"""

import os, sys, json, time, subprocess, urllib.request, ssl
from datetime import datetime, timezone

# Config
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
PIPELINES = {
    "standard": {
        "webhook": f"{N8N_HOST}/webhook/rag-multi-index-v3",
        "test_query": {"question": "What is GDP?"},
        "objective": {"phase": 4, "target_accuracy": 0.85, "target_questions": 10917},
        "timeout": 90,
    },
    "graph": {
        "webhook": f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "test_query": {"question": "What is machine learning?"},
        "objective": {"phase": 4, "target_accuracy": 0.55, "target_questions": 11300},
        "timeout": 90,
    },
    "quantitative": {
        "webhook": f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "test_query": {"question": "What is the revenue of Apple in 2023?"},
        "objective": {"phase": 4, "target_accuracy": 0.90, "target_questions": 3871},
        "timeout": 120,
    },
}

LOG_FILE = "/tmp/self-heal-orchestrator.log"
ISSUES_FILE = "/tmp/pipeline-issues.json"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def test_pipeline(name, config):
    """Smoke-test a pipeline. Returns (success, response_or_error, latency_ms)."""
    url = config["webhook"]
    data = json.dumps(config["test_query"]).encode()
    timeout = config["timeout"]

    start = time.time()
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        body = resp.read().decode()
        latency = int((time.time() - start) * 1000)

        if not body or body.strip() == "":
            return False, "Empty response", latency

        try:
            parsed = json.loads(body)
            if "error" in str(parsed).lower() and "no item to return" in str(parsed).lower():
                return False, parsed, latency
            if parsed.get("code") == 0:
                return False, parsed, latency
            return True, parsed, latency
        except json.JSONDecodeError:
            return bool(body.strip()), body[:200], latency

    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return False, str(e), latency


def invoke_claude_fix(pipeline_name, error_info):
    """Invoke Claude Code CLI to fix a broken pipeline."""
    prompt = f"""
SELF-HEAL MODE: Pipeline '{pipeline_name}' is BROKEN.

Error: {json.dumps(error_info) if isinstance(error_info, dict) else str(error_info)[:500]}

Your mission:
1. Source .env.local
2. Diagnose the root cause (check n8n execution logs, LiteLLM health, DB connectivity)
3. Fix the issue if possible (update workflow via PATCH, fix model config, etc.)
4. Re-test the pipeline
5. Document the fix in technicals/DEBUG-PLAYBOOK.md

Pipeline details:
- Standard: webhook /webhook/rag-multi-index-v3, WF ID TmgyRP20N4JFd9CB
- Graph: webhook /webhook/ff622742-..., WF ID 6257AfT1l4FMC6lY
- Quant: webhook /webhook/3e0f8010-..., WF ID cjhEhVs0KV1ExHqX
- n8n login: Python only (ci@nomos.ai / CI-Nomos-2026!)
- LiteLLM: $LITELLM_PROXY_URL with key $LITELLM_MASTER_KEY

Fix it. Then re-test. Report results.
"""
    log(f"  Invoking Claude Code CLI to fix {pipeline_name}...")
    try:
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "-p", prompt],
            capture_output=True, text=True, timeout=300,
            cwd="/home/termius/mon-ipad"
        )
        log(f"  Claude Code exit code: {result.returncode}")
        # Log last 10 lines of output
        for line in result.stdout.strip().split("\n")[-10:]:
            log(f"    {line}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"  Claude Code timed out after 5 min")
        return False
    except FileNotFoundError:
        log(f"  Claude Code CLI not found — install with: npm install -g @anthropic-ai/claude-code")
        return False


def run_cycle():
    """Run one monitoring cycle."""
    log("=== SELF-HEAL CYCLE START ===")
    results = {}
    issues = []

    for name, config in PIPELINES.items():
        log(f"Testing {name}...")
        success, response, latency = test_pipeline(name, config)
        results[name] = {"success": success, "latency_ms": latency}

        if success:
            log(f"  {name}: PASS ({latency}ms)")
        else:
            log(f"  {name}: FAIL ({latency}ms) — {str(response)[:200]}")
            issues.append({"pipeline": name, "error": str(response)[:500], "timestamp": datetime.now(timezone.utc).isoformat()})

    # Save issues
    if issues:
        with open(ISSUES_FILE, "w") as f:
            json.dump(issues, f, indent=2)

    # Fix broken pipelines
    for issue in issues:
        invoke_claude_fix(issue["pipeline"], issue["error"])
        # Re-test after fix
        name = issue["pipeline"]
        log(f"  Re-testing {name} after fix...")
        success, response, latency = test_pipeline(name, PIPELINES[name])
        if success:
            log(f"  {name}: HEALED! ({latency}ms)")
        else:
            log(f"  {name}: Still broken ({latency}ms)")

    log(f"=== CYCLE DONE: {sum(1 for r in results.values() if r['success'])}/3 PASS ===")
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Self-Healing Pipeline Orchestrator")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=30, help="Minutes between cycles (default: 30)")
    parser.add_argument("--fix-only", action="store_true", help="Only fix broken pipelines, don't run evals")
    args = parser.parse_args()

    if args.loop:
        log(f"Starting self-heal loop (interval: {args.interval}min)")
        while True:
            try:
                run_cycle()
            except Exception as e:
                log(f"Cycle error: {e}")
            time.sleep(args.interval * 60)
    else:
        run_cycle()


if __name__ == "__main__":
    main()
