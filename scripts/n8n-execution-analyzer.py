#!/usr/bin/env python3
"""
n8n Execution Analyzer — Automated execution analysis and error detection.

Pulls recent executions from all active pipelines, analyzes node-level
performance, detects errors, and outputs a structured health report.

Usage:
  source .env.local
  python3 scripts/n8n-execution-analyzer.py                    # Last 10 execs
  python3 scripts/n8n-execution-analyzer.py --hours 24         # Last 24h
  python3 scripts/n8n-execution-analyzer.py --workflow TmgyRP  # Specific WF
  python3 scripts/n8n-execution-analyzer.py --json             # JSON output
"""

import json
import os
import sys
import time
import argparse
import urllib.request
import urllib.error
import http.cookiejar
from collections import defaultdict
from datetime import datetime, timedelta

HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
CI_EMAIL = os.environ.get("N8N_CI_EMAIL", "ci@nomos.ai")
CI_PASSWORD = os.environ.get("N8N_CI_PASSWORD", "CI-Nomos-2026!")

PIPELINE_IDS = {
    "TmgyRP20N4JFd9CB": "Standard",
    "6257AfT1l4FMC6lY": "Graph",
    "cjhEhVs0KV1ExHqX": "Quant",
    "ALd4gOEqiKL5KR1p": "Orchestrator",
}

REPORT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "logs", "n8n-execution-report.json")


def get_opener():
    """Login to n8n, return authenticated opener."""
    cj = http.cookiejar.MozillaCookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = json.dumps({"emailOrLdapLoginId": CI_EMAIL, "password": CI_PASSWORD}).encode()
    req = urllib.request.Request(f"{HOST}/rest/login", data=data,
                                headers={"Content-Type": "application/json"}, method="POST")
    opener.open(req, timeout=20)
    return opener


def api_get(opener, path, timeout=30):
    req = urllib.request.Request(f"{HOST}/rest{path}", method="GET")
    resp = opener.open(req, timeout=timeout)
    data = json.loads(resp.read().decode())
    return data.get("data", data)


def get_executions(opener, limit=50, workflow_id=None, hours=None):
    """Fetch recent executions."""
    params = f"?limit={limit}"
    if workflow_id:
        params += f"&workflowId={workflow_id}"
    result = api_get(opener, f"/executions{params}")

    if isinstance(result, dict):
        execs = result.get("results", result.get("data", []))
    elif isinstance(result, list):
        execs = result
    else:
        execs = []

    # Filter by time if needed
    if hours:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        filtered = []
        for ex in execs:
            started = ex.get("startedAt", "")
            if started:
                try:
                    dt = datetime.fromisoformat(started.replace("Z", "+00:00").replace("+00:00", ""))
                    if dt >= cutoff:
                        filtered.append(ex)
                except (ValueError, TypeError):
                    filtered.append(ex)
        execs = filtered

    return execs


def analyze_execution(opener, exec_id):
    """Analyze a single execution node-by-node."""
    try:
        data = api_get(opener, f"/executions/{exec_id}?includeData=true")
    except Exception:
        return None

    exec_data_raw = data.get("data", "")
    if isinstance(exec_data_raw, str):
        try:
            parsed = json.loads(exec_data_raw)
            if isinstance(parsed, list):
                # n8n stores execution data as array of snapshots
                for entry in reversed(parsed):
                    if isinstance(entry, dict) and "resultData" in entry:
                        parsed = entry
                        break
                else:
                    parsed = parsed[-1] if parsed else {}
            if not isinstance(parsed, dict):
                return None
            result_data = parsed.get("resultData", {})
            if isinstance(result_data, str):
                try:
                    result_data = json.loads(result_data)
                except (json.JSONDecodeError, TypeError):
                    return None
            if not isinstance(result_data, dict):
                return None
            run_data = result_data.get("runData", {})
        except (json.JSONDecodeError, IndexError, TypeError):
            return None
    elif isinstance(exec_data_raw, dict):
        result_data = exec_data_raw.get("resultData", {})
        if isinstance(result_data, str):
            try:
                result_data = json.loads(result_data)
            except (json.JSONDecodeError, TypeError):
                return None
        run_data = result_data.get("runData", {}) if isinstance(result_data, dict) else {}
    else:
        return None

    if not isinstance(run_data, dict):
        return None

    nodes = []
    errors = []
    total_time_ms = 0

    for node_name, runs in run_data.items():
        if not runs or not isinstance(runs, list):
            continue
        run = runs[0] if isinstance(runs[0], dict) else {}
        err = run.get("error")
        start_time = run.get("startTime", 0)
        exec_time = run.get("executionTime", 0)
        total_time_ms += exec_time

        main_data = run.get("data", {})
        if isinstance(main_data, dict):
            main = main_data.get("main", [[]])
        else:
            main = [[]]
        items = main[0] if main and isinstance(main[0], list) else []

        node_info = {
            "name": node_name,
            "items": len(items),
            "time_ms": exec_time,
            "error": None,
        }

        if err:
            err_msg = err.get("message", str(err))[:300] if isinstance(err, dict) else str(err)[:300]
            node_info["error"] = err_msg
            errors.append({"node": node_name, "error": err_msg})

        # Extract key output fields
        if items and isinstance(items[0], dict):
            j = items[0].get("json", {})
            for k in ["answer", "response", "error", "status", "fallback"]:
                if k in j:
                    node_info[k] = str(j[k])[:200]

        nodes.append(node_info)

    return {
        "nodes": nodes,
        "errors": errors,
        "total_time_ms": total_time_ms,
        "node_count": len(nodes),
    }


def generate_report(executions, opener):
    """Generate a comprehensive health report."""
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_executions": len(executions),
        "by_pipeline": {},
        "errors": [],
        "slow_executions": [],
        "summary": {},
    }

    pipeline_stats = defaultdict(lambda: {
        "total": 0, "success": 0, "failed": 0, "error": 0,
        "avg_time_ms": 0, "times": [], "errors": [],
    })

    for ex in executions:
        wf_id = ex.get("workflowId", "unknown")
        pipeline_name = PIPELINE_IDS.get(wf_id, ex.get("workflowName", wf_id)[:30])
        status = ex.get("status", "unknown")
        started = ex.get("startedAt", "")
        stopped = ex.get("stoppedAt", "")

        stats = pipeline_stats[pipeline_name]
        stats["total"] += 1

        if status == "success":
            stats["success"] += 1
        elif status == "error":
            stats["error"] += 1
        else:
            stats["failed"] += 1

        # Calculate duration
        if started and stopped:
            try:
                t0 = datetime.fromisoformat(started.replace("Z", ""))
                t1 = datetime.fromisoformat(stopped.replace("Z", ""))
                duration_ms = int((t1 - t0).total_seconds() * 1000)
                stats["times"].append(duration_ms)

                if duration_ms > 60000:  # > 60s
                    report["slow_executions"].append({
                        "pipeline": pipeline_name,
                        "exec_id": ex.get("id"),
                        "duration_ms": duration_ms,
                        "status": status,
                    })
            except (ValueError, TypeError):
                pass

        # Try to get detailed error info for failed executions
        if status == "error":
            exec_id = ex.get("id")
            detail = analyze_execution(opener, exec_id) if exec_id else None
            if detail and detail["errors"]:
                for err in detail["errors"]:
                    stats["errors"].append(err)
                    report["errors"].append({
                        "pipeline": pipeline_name,
                        "exec_id": exec_id,
                        **err,
                    })

    # Compute averages
    for name, stats in pipeline_stats.items():
        if stats["times"]:
            stats["avg_time_ms"] = int(sum(stats["times"]) / len(stats["times"]))
            stats["min_time_ms"] = min(stats["times"])
            stats["max_time_ms"] = max(stats["times"])
        stats["success_rate"] = round(stats["success"] / max(stats["total"], 1) * 100, 1)
        del stats["times"]  # Don't include raw times in output
        report["by_pipeline"][name] = stats

    # Summary
    total = sum(s["total"] for s in pipeline_stats.values())
    success = sum(s["success"] for s in pipeline_stats.values())
    report["summary"] = {
        "total_executions": total,
        "success_rate": round(success / max(total, 1) * 100, 1),
        "total_errors": len(report["errors"]),
        "slow_count": len(report["slow_executions"]),
        "pipelines_active": len(pipeline_stats),
    }

    return report


def print_report(report):
    """Print human-readable report."""
    s = report["summary"]
    print(f"\n{'=' * 70}")
    print(f"  N8N EXECUTION HEALTH REPORT")
    print(f"  {report['timestamp']}")
    print(f"{'=' * 70}")
    print(f"  Total: {s['total_executions']} | Success: {s['success_rate']}% | "
          f"Errors: {s['total_errors']} | Slow: {s['slow_count']}")
    print(f"{'=' * 70}")

    print(f"\n  {'Pipeline':<20} {'Total':>6} {'OK':>6} {'Fail':>6} {'Rate':>8} {'Avg(ms)':>10}")
    print(f"  {'-' * 60}")
    for name, stats in report["by_pipeline"].items():
        print(f"  {name:<20} {stats['total']:>6} {stats['success']:>6} "
              f"{stats['error']:>6} {stats['success_rate']:>7.1f}% "
              f"{stats.get('avg_time_ms', 0):>10}")

    if report["errors"]:
        print(f"\n  ERRORS ({len(report['errors'])})")
        print(f"  {'-' * 60}")
        for err in report["errors"][:10]:
            print(f"  [{err['pipeline']}] {err['node']}")
            print(f"    {err['error'][:100]}")

    if report["slow_executions"]:
        print(f"\n  SLOW EXECUTIONS (>{60}s)")
        print(f"  {'-' * 60}")
        for slow in report["slow_executions"][:5]:
            print(f"  [{slow['pipeline']}] {slow['duration_ms']}ms — {slow['status']}")

    print()


def main():
    parser = argparse.ArgumentParser(description="n8n Execution Analyzer")
    parser.add_argument("--hours", type=int, default=0, help="Filter to last N hours")
    parser.add_argument("--limit", type=int, default=50, help="Max executions to fetch")
    parser.add_argument("--workflow", type=str, help="Filter to specific workflow ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print("Connecting to n8n...")
    opener = get_opener()

    print(f"Fetching executions (limit={args.limit})...")
    execs = get_executions(opener, limit=args.limit,
                           workflow_id=args.workflow,
                           hours=args.hours if args.hours > 0 else None)
    print(f"Found {len(execs)} executions")

    report = generate_report(execs, opener)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    # Save report
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()
