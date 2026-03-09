#!/usr/bin/env python3
"""
Auto-Healer CLI — Fetch reports from n8n and present to Claude Code for decisions.

This script is the VM-side counterpart to the n8n Auto-Healer workflow.
It fetches the latest analysis report, displays it, and can trigger new runs.

Usage:
  python3 ops/auto-healer-cli.py                  # Fetch last report
  python3 ops/auto-healer-cli.py --trigger         # Trigger a new analysis run
  python3 ops/auto-healer-cli.py --watch           # Watch mode (check every 5min)
  python3 ops/auto-healer-cli.py --apply-last      # Show patch for Claude Code to apply
"""

import json
import os
import sys
import argparse
import urllib.request
import urllib.error
from datetime import datetime

N8N_HOSTS = [
    "https://lbjlincoln-nomos-rag-engine.hf.space",
    "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",
]

RESULTS_PATH = "/webhook/auto-healer-results"
TRIGGER_PATH = "/webhook/auto-healer-trigger"
REPORT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "logs", "auto-healer-latest.json")


def fetch_url(url, method="GET", data=None, timeout=30):
    """Fetch URL with proper error handling."""
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "body": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)}


def fetch_latest_report():
    """Try all hosts to fetch the latest auto-healer report."""
    for host in N8N_HOSTS:
        result = fetch_url(f"{host}{RESULTS_PATH}")
        if "error" not in result:
            return result, host
    return None, None


def trigger_run():
    """Trigger a new auto-healer analysis run."""
    for host in N8N_HOSTS:
        result = fetch_url(f"{host}{TRIGGER_PATH}", method="POST",
                           data=json.dumps({"triggered_by": "cli"}).encode())
        if "error" not in result:
            return result, host
    return None, None


def display_report(report):
    """Display report in a clear format for Claude Code."""
    lr = report.get("last_report", {})
    if not lr or "error" in lr:
        print("No reports available yet. Run --trigger first.")
        return

    print(f"\n{'=' * 70}")
    print(f"  AUTO-HEALER REPORT — {lr.get('timestamp', 'unknown')}")
    print(f"  Run ID: {lr.get('run_id', 'unknown')}")
    print(f"{'=' * 70}")

    # Health
    health = lr.get("execution_health", {})
    print(f"\n  PIPELINE HEALTH: {health.get('healthy', '?')}H / "
          f"{health.get('degraded', '?')}D / {health.get('unhealthy', '?')}U")
    for d in health.get("details", []):
        status_icon = "OK" if d["status"] == "HEALTHY" else "!!" if d["status"] == "DEGRADED" else "XX"
        print(f"    [{status_icon}] {d['pipeline']}: {d.get('success_rate', '?')}% success, "
              f"avg {d.get('avg_duration_ms', '?')}ms")

    # Smoke tests
    smoke = lr.get("smoke_tests", {})
    print(f"\n  SMOKE TESTS: {smoke.get('overall_score', '?')}% overall "
          f"| {smoke.get('avg_response_ms', '?')}ms avg "
          f"| {smoke.get('timeouts', 0)} timeouts")
    for s in smoke.get("details", []):
        icon = "OK" if s["score"] >= 75 else ".." if s["score"] >= 50 else "XX"
        print(f"    [{icon}] {s['sector']}: {s['score']}% | {s.get('response_ms', '?')}ms "
              f"| missing: {', '.join(s.get('missing_kw', []))}")

    # Gaps
    print(f"\n  SECTOR GAPS (current vs target):")
    for g in lr.get("gaps", []):
        bar = "#" * max(g["current"] // 5, 1) + "." * max((g["target"] - g["current"]) // 5, 0)
        print(f"    {g['sector']:12s}: {g['current']:3d}% / {g['target']:3d}% "
              f"(gap: {g['gap']:+d}pp) [{bar}]")

    # Patch proposal
    print(f"\n  RECOMMENDATION: {lr.get('recommendation', 'NONE')}")
    patch = lr.get("patch_proposal")
    if patch and patch.get("severity") != "LOW":
        print(f"\n  PROPOSED PATCH:")
        print(f"    Severity:    {patch.get('severity', '?')}")
        print(f"    Pipeline:    {patch.get('target_pipeline', '?')}")
        print(f"    Type:        {patch.get('improvement_type', '?')}")
        print(f"    Diagnosis:   {patch.get('diagnosis', '?')}")
        sc = patch.get("specific_change", {})
        if sc:
            print(f"    Node:        {sc.get('node_name', '?')}")
            print(f"    Field:       {sc.get('field', '?')}")
            print(f"    New value:   {str(sc.get('new_value', '?'))[:200]}")
            print(f"    Rationale:   {sc.get('rationale', '?')}")
        print(f"    Expected:    {patch.get('expected_impact', '?')}")
        print(f"    Risk:        {patch.get('risk', '?')}")
        print(f"    Rollback:    {patch.get('rollback_plan', '?')}")
    elif patch:
        print(f"    Status: Low severity — no action needed.")
    else:
        print(f"    No patch proposed (parse error or LLM failure).")
        if lr.get("patch_parse_error"):
            print(f"    Error: {lr['patch_parse_error'][:200]}")

    print(f"\n  Total reports stored: {report.get('total_reports', '?')}")
    print(f"  Last updated: {report.get('last_updated', '?')}")
    print()


def save_report(report):
    """Save report locally for Claude Code to read."""
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved to {REPORT_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Auto-Healer CLI")
    parser.add_argument("--trigger", action="store_true", help="Trigger a new analysis run")
    parser.add_argument("--watch", action="store_true", help="Watch mode (poll every 5min)")
    parser.add_argument("--apply-last", action="store_true",
                        help="Output last patch as JSON for Claude Code to apply")
    parser.add_argument("--json", action="store_true", help="Raw JSON output")
    args = parser.parse_args()

    if args.trigger:
        print("Triggering auto-healer run...")
        result, host = trigger_run()
        if result:
            print(f"  Triggered on {host}")
            if not args.json:
                display_report(result)
            else:
                print(json.dumps(result, indent=2))
            save_report(result)
        else:
            print("  FAILED: Could not reach any n8n host.")
            sys.exit(1)
        return

    if args.apply_last:
        report, _ = fetch_latest_report()
        if report:
            lr = report.get("last_report", {})
            patch = lr.get("patch_proposal")
            if patch:
                print(json.dumps(patch, indent=2))
            else:
                print('{"error": "No patch available"}')
        else:
            print('{"error": "No report available"}')
        return

    # Default: fetch and display
    print("Fetching latest auto-healer report...")
    report, host = fetch_latest_report()
    if report:
        print(f"  Source: {host}")
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            display_report(report)
        save_report(report)
    else:
        print("  No report available. Use --trigger to run analysis.")


if __name__ == "__main__":
    main()
