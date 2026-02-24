#!/usr/bin/env python3
"""
node-tracker.py — Build a precise, timestamped history of every n8n workflow
node's success/failure across all executions.

Data sources:
  1. n8n_analysis_results/*.json  — execution trace files
  2. snapshot/                    — workflow snapshots for node type definitions

Output:
  - JSON report  → logs/node-tracker-report.json
  - Human-readable summary to stdout

Usage:
  python3 scripts/node-tracker.py
"""

import json
import os
import sys
import glob
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
EXECUTIONS_DIR = BASE_DIR / "n8n_analysis_results"
SNAPSHOT_DIRS = [
    BASE_DIR / "snapshot" / "current",
    BASE_DIR / "snapshot" / "workflows",
]
OUTPUT_JSON = BASE_DIR / "logs" / "node-tracker-report.json"

# ---------------------------------------------------------------------------
# 1. Build node-type map from workflow snapshots
# ---------------------------------------------------------------------------

def build_node_type_map():
    """Parse all workflow snapshot JSONs and return {(workflow_name, node_name): node_type}."""
    node_types = {}
    for snap_dir in SNAPSHOT_DIRS:
        if not snap_dir.is_dir():
            continue
        for filepath in sorted(snap_dir.glob("*.json")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    wf = json.load(f)
                if not isinstance(wf, dict):
                    continue
                wf_name = wf.get("name")
                nodes = wf.get("nodes")
                if not wf_name or not isinstance(nodes, list):
                    continue
                for n in nodes:
                    name = n.get("name")
                    ntype = n.get("type", "unknown")
                    if name:
                        node_types[(wf_name, name)] = ntype
            except (json.JSONDecodeError, OSError) as e:
                print(f"  [WARN] Skipping snapshot {filepath.name}: {e}", file=sys.stderr)
    return node_types


# ---------------------------------------------------------------------------
# 2. Parse all execution JSON files
# ---------------------------------------------------------------------------

def parse_executions():
    """
    Parse every execution_*.json and return a list of dicts:
    [
      {
        "execution_id": str,
        "workflow_name": str,
        "started_at": str (ISO),
        "finished_at": str (ISO) or None,
        "status": str,
        "duration_ms": int,
        "nodes": [
          {
            "name": str,
            "status": str,
            "error": str or None,
            "duration_ms": int,
            "items_in": int,
            "items_out": int,
          }, ...
        ]
      }, ...
    ]
    """
    executions = []
    if not EXECUTIONS_DIR.is_dir():
        print(f"[ERROR] Executions directory not found: {EXECUTIONS_DIR}", file=sys.stderr)
        return executions

    files = sorted(EXECUTIONS_DIR.glob("execution_*.json"))
    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [WARN] Skipping malformed file {filepath.name}: {e}", file=sys.stderr)
            continue

        if not isinstance(data, dict):
            print(f"  [WARN] Skipping {filepath.name}: top-level is not a dict", file=sys.stderr)
            continue

        exec_id = str(data.get("execution_id", filepath.stem))
        workflow_name = data.get("workflow_name", "unknown")
        started_at = data.get("started_at")
        finished_at = data.get("stopped_at")
        exec_status = data.get("status", "unknown")
        duration_ms = data.get("duration_ms", 0)

        raw_nodes = data.get("nodes", [])
        if not isinstance(raw_nodes, list):
            raw_nodes = []

        parsed_nodes = []
        for n in raw_nodes:
            if not isinstance(n, dict):
                continue
            node_name = n.get("name", "unnamed")
            node_status = n.get("status", "unknown")
            node_error = n.get("error")  # str or None
            node_duration = n.get("duration_ms", 0)
            items_in = n.get("items_in", 0)
            items_out = n.get("items_out", 0)

            # Normalize: if error is empty string, treat as None
            if node_error is not None and not str(node_error).strip():
                node_error = None

            parsed_nodes.append({
                "name": node_name,
                "status": node_status,
                "error": str(node_error) if node_error else None,
                "duration_ms": int(node_duration) if node_duration else 0,
                "items_in": int(items_in) if items_in else 0,
                "items_out": int(items_out) if items_out else 0,
            })

        executions.append({
            "execution_id": exec_id,
            "workflow_name": workflow_name,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": exec_status,
            "duration_ms": int(duration_ms) if duration_ms else 0,
            "nodes": parsed_nodes,
        })

    return executions


# ---------------------------------------------------------------------------
# 3. Build per-node timeline
# ---------------------------------------------------------------------------

def build_node_timelines(executions, node_type_map):
    """
    Returns:
      {
        (workflow_name, node_name): {
          "workflow": str,
          "node": str,
          "node_type": str,
          "history": [
            {
              "timestamp": str (ISO),
              "execution_id": str,
              "status": str,
              "error": str or None,
              "duration_ms": int,
              "items_in": int,
              "items_out": int,
            }, ...
          ]
        }, ...
      }
    """
    timelines = {}

    for ex in executions:
        wf = ex["workflow_name"]
        ts = ex["started_at"]  # execution-level timestamp
        exec_id = ex["execution_id"]

        for node in ex["nodes"]:
            key = (wf, node["name"])
            if key not in timelines:
                ntype = node_type_map.get(key, "unknown")
                timelines[key] = {
                    "workflow": wf,
                    "node": node["name"],
                    "node_type": ntype,
                    "history": [],
                }

            timelines[key]["history"].append({
                "timestamp": ts,
                "execution_id": exec_id,
                "status": node["status"],
                "error": node["error"],
                "duration_ms": node["duration_ms"],
                "items_in": node["items_in"],
                "items_out": node["items_out"],
            })

    # Sort each node's history by timestamp
    for key in timelines:
        timelines[key]["history"].sort(key=lambda h: h["timestamp"] or "")

    return timelines


# ---------------------------------------------------------------------------
# 4. Calculate per-node statistics
# ---------------------------------------------------------------------------

def parse_ts(ts_str):
    """Parse ISO timestamp string to datetime, returning None on failure."""
    if not ts_str:
        return None
    try:
        # Handle Z suffix and various formats
        s = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def compute_node_stats(timelines):
    """
    For each node, compute:
      - total_executions, success_count, failure_count, success_rate
      - avg_duration_ms (of successes), avg_duration_all_ms
      - most_common_error
      - last_seen_ok, last_seen_fail
      - regression_detected (was OK then started failing recently)
      - fix_detected (was failing then started succeeding recently)
    """
    stats = {}

    for key, tl in timelines.items():
        history = tl["history"]
        total = len(history)
        successes = [h for h in history if h["status"] == "success"]
        failures = [h for h in history if h["status"] != "success"]

        success_count = len(successes)
        failure_count = len(failures)
        success_rate = (success_count / total * 100) if total > 0 else 0.0

        # Average duration
        all_durations = [h["duration_ms"] for h in history if h["duration_ms"] is not None]
        success_durations = [h["duration_ms"] for h in successes if h["duration_ms"] is not None]

        avg_duration_all = (sum(all_durations) / len(all_durations)) if all_durations else 0.0
        avg_duration_success = (sum(success_durations) / len(success_durations)) if success_durations else 0.0

        # Most common error
        error_counts = defaultdict(int)
        for h in failures:
            err_msg = h.get("error") or "unknown error"
            error_counts[err_msg] += 1
        most_common_error = None
        most_common_error_count = 0
        if error_counts:
            most_common_error = max(error_counts, key=error_counts.get)
            most_common_error_count = error_counts[most_common_error]

        # Last seen timestamps
        last_seen_ok = None
        last_seen_fail = None
        for h in reversed(history):
            if h["status"] == "success" and last_seen_ok is None:
                last_seen_ok = h["timestamp"]
            if h["status"] != "success" and last_seen_fail is None:
                last_seen_fail = h["timestamp"]
            if last_seen_ok and last_seen_fail:
                break

        # Regression detection: last N entries started failing after prior successes
        # Strategy: look at the tail of the history. If the last entry is a failure
        # and there are earlier successes, it's a regression.
        regression_detected = False
        fix_detected = False
        if len(history) >= 2:
            last_status = history[-1]["status"]
            has_earlier_success = any(h["status"] == "success" for h in history[:-1])
            has_earlier_failure = any(h["status"] != "success" for h in history[:-1])

            if last_status != "success" and has_earlier_success:
                regression_detected = True
            if last_status == "success" and has_earlier_failure:
                fix_detected = True

        stats[key] = {
            "workflow": tl["workflow"],
            "node": tl["node"],
            "node_type": tl["node_type"],
            "total_executions": total,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": round(success_rate, 1),
            "avg_duration_ms": round(avg_duration_all, 1),
            "avg_duration_success_ms": round(avg_duration_success, 1),
            "most_common_error": most_common_error,
            "most_common_error_count": most_common_error_count,
            "last_seen_ok": last_seen_ok,
            "last_seen_fail": last_seen_fail,
            "regression_detected": regression_detected,
            "fix_detected": fix_detected,
            "history": tl["history"],
        }

    return stats


# ---------------------------------------------------------------------------
# 5. Output: JSON report
# ---------------------------------------------------------------------------

def write_json_report(stats, executions):
    """Write full JSON report to logs/node-tracker-report.json."""
    # Convert dict-keyed stats to a list for JSON serialization
    nodes_list = []
    for key in sorted(stats.keys()):
        s = stats[key]
        nodes_list.append(s)

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "total_executions_parsed": len(executions),
        "total_unique_nodes": len(nodes_list),
        "summary": {
            "nodes_with_failures": sum(1 for s in nodes_list if s["failure_count"] > 0),
            "nodes_always_ok": sum(1 for s in nodes_list if s["failure_count"] == 0),
            "regressions_detected": sum(1 for s in nodes_list if s["regression_detected"]),
            "fixes_detected": sum(1 for s in nodes_list if s["fix_detected"]),
        },
        "nodes": nodes_list,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


# ---------------------------------------------------------------------------
# 6. Output: Human-readable stdout
# ---------------------------------------------------------------------------

def print_summary(stats, executions):
    """Print a structured summary to stdout."""

    stats_list = list(stats.values())

    print("=" * 80)
    print("  N8N NODE TRACKER — Execution History Report")
    print("=" * 80)
    print(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"  Executions parsed: {len(executions)}")
    print(f"  Unique nodes tracked: {len(stats_list)}")
    print()

    # --- Workflows breakdown ---
    wf_execs = defaultdict(int)
    wf_statuses = defaultdict(lambda: defaultdict(int))
    for ex in executions:
        wf_execs[ex["workflow_name"]] += 1
        wf_statuses[ex["workflow_name"]][ex["status"]] += 1

    print("-" * 80)
    print("  WORKFLOW EXECUTION SUMMARY")
    print("-" * 80)
    for wf in sorted(wf_execs.keys()):
        statuses_str = ", ".join(f"{s}: {c}" for s, c in sorted(wf_statuses[wf].items()))
        print(f"  {wf}")
        print(f"    Executions: {wf_execs[wf]}  ({statuses_str})")
    print()

    # --- Section 1: Nodes sorted by failure rate (worst first) ---
    nodes_with_failures = [s for s in stats_list if s["failure_count"] > 0]
    nodes_with_failures.sort(key=lambda s: (-s["failure_count"], s["success_rate"]))

    print("-" * 80)
    print("  NODES BY FAILURE RATE (worst first)")
    print("-" * 80)
    if not nodes_with_failures:
        print("  (none — all nodes succeeded in every execution)")
    else:
        for s in nodes_with_failures:
            fail_pct = 100.0 - s["success_rate"]
            print(f"  [{s['workflow']}]")
            print(f"    Node: {s['node']}")
            print(f"    Type: {s['node_type']}")
            print(f"    Failure rate: {fail_pct:.1f}% ({s['failure_count']}/{s['total_executions']})")
            print(f"    Avg duration: {s['avg_duration_ms']:.0f}ms")
            if s["most_common_error"]:
                err_display = s["most_common_error"]
                if len(err_display) > 120:
                    err_display = err_display[:117] + "..."
                print(f"    Most common error ({s['most_common_error_count']}x): {err_display}")
            if s["last_seen_fail"]:
                print(f"    Last failure: {s['last_seen_fail']}")
            if s["last_seen_ok"]:
                print(f"    Last success: {s['last_seen_ok']}")
            print()

    # --- Section 2: Regressions (recently started failing) ---
    regressions = [s for s in stats_list if s["regression_detected"]]
    regressions.sort(key=lambda s: s.get("last_seen_fail") or "", reverse=True)

    print("-" * 80)
    print("  REGRESSION DETECTION (recently started failing)")
    print("-" * 80)
    if not regressions:
        print("  (none detected)")
    else:
        for s in regressions:
            print(f"  [REGRESSION] {s['node']}  (in {s['workflow']})")
            print(f"    Last OK:   {s['last_seen_ok'] or 'never'}")
            print(f"    Last FAIL: {s['last_seen_fail'] or 'never'}")
            if s["most_common_error"]:
                err_display = s["most_common_error"]
                if len(err_display) > 100:
                    err_display = err_display[:97] + "..."
                print(f"    Error: {err_display}")
            # Show recent history tail
            recent = s["history"][-5:]
            print(f"    Recent history ({len(s['history'])} total):")
            for h in recent:
                status_marker = "OK" if h["status"] == "success" else "FAIL"
                err_part = ""
                if h["error"]:
                    short_err = h["error"][:80] + ("..." if len(h["error"]) > 80 else "")
                    err_part = f' — {short_err}'
                print(f"      {h['timestamp']} — {status_marker} ({h['duration_ms']}ms){err_part}")
            print()

    # --- Section 3: Fixes (recently started succeeding) ---
    fixes = [s for s in stats_list if s["fix_detected"]]
    fixes.sort(key=lambda s: s.get("last_seen_ok") or "", reverse=True)

    print("-" * 80)
    print("  FIX DETECTION (recently started succeeding)")
    print("-" * 80)
    if not fixes:
        print("  (none detected)")
    else:
        for s in fixes:
            print(f"  [FIXED] {s['node']}  (in {s['workflow']})")
            print(f"    Last OK:   {s['last_seen_ok'] or 'never'}")
            print(f"    Last FAIL: {s['last_seen_fail'] or 'never'}")
            print(f"    Success rate: {s['success_rate']}% ({s['success_count']}/{s['total_executions']})")
            # Show recent history tail
            recent = s["history"][-5:]
            print(f"    Recent history ({len(s['history'])} total):")
            for h in recent:
                status_marker = "OK" if h["status"] == "success" else "FAIL"
                err_part = ""
                if h["error"]:
                    short_err = h["error"][:80] + ("..." if len(h["error"]) > 80 else "")
                    err_part = f' — {short_err}'
                print(f"      {h['timestamp']} — {status_marker} ({h['duration_ms']}ms){err_part}")
            print()

    # --- Section 4: Fully healthy nodes ---
    healthy = [s for s in stats_list if s["failure_count"] == 0]
    print("-" * 80)
    print(f"  HEALTHY NODES ({len(healthy)} nodes — 100% success rate)")
    print("-" * 80)
    # Group by workflow
    by_wf = defaultdict(list)
    for s in healthy:
        by_wf[s["workflow"]].append(s)
    for wf in sorted(by_wf.keys()):
        nodes = sorted(by_wf[wf], key=lambda s: s["node"])
        print(f"  [{wf}] — {len(nodes)} nodes")
        for s in nodes:
            print(f"    {s['node']:50s} {s['total_executions']:3d} runs  avg {s['avg_duration_ms']:8.0f}ms  type: {s['node_type']}")
    print()

    # --- Summary ---
    print("=" * 80)
    total_failures = sum(s["failure_count"] for s in stats_list)
    total_runs = sum(s["total_executions"] for s in stats_list)
    print(f"  TOTALS: {total_runs} node-executions across {len(executions)} executions")
    print(f"  Failed node-runs: {total_failures}")
    print(f"  Nodes with failures: {len(nodes_with_failures)}")
    print(f"  Regressions detected: {len(regressions)}")
    print(f"  Fixes detected: {len(fixes)}")
    print(f"  Report saved to: {OUTPUT_JSON}")
    print("=" * 80)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading node type map from snapshots...")
    node_type_map = build_node_type_map()
    print(f"  Found {len(node_type_map)} node-type mappings from workflow snapshots.")

    print("Parsing execution files...")
    executions = parse_executions()
    print(f"  Parsed {len(executions)} executions from {EXECUTIONS_DIR}")

    if not executions:
        print("[ERROR] No executions found. Nothing to report.", file=sys.stderr)
        sys.exit(1)

    print("Building per-node timelines...")
    timelines = build_node_timelines(executions, node_type_map)
    print(f"  Tracking {len(timelines)} unique nodes across all workflows.")

    print("Computing per-node statistics...")
    stats = compute_node_stats(timelines)

    print("Writing JSON report...")
    report = write_json_report(stats, executions)
    print(f"  Written to {OUTPUT_JSON}")

    print()
    print_summary(stats, executions)


if __name__ == "__main__":
    main()
