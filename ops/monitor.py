#!/usr/bin/env python3
"""
Unified Pipeline Monitor — Per-execution error detection + JSONL tracking + live dashboard.

Features:
- Fetches recent executions from ALL n8n Spaces
- Detects errors per node with classification
- Logs every error to logs/errors/pipeline-errors.jsonl (persistent)
- Outputs a live dashboard summary
- Can run in continuous mode (--loop) for tmux panes

Usage:
  source .env.local
  python3 ops/monitor.py                    # One-shot report
  python3 ops/monitor.py --loop 300         # Continuous every 5min
  python3 ops/monitor.py --hours 24         # Last 24h only
  python3 ops/monitor.py --json             # JSON output
  python3 ops/monitor.py --errors-only      # Show only errors
"""

import json
import os
import sys
import time
import socket
import argparse
import urllib.request
import urllib.error
import http.cookiejar
from collections import defaultdict
from datetime import datetime, timedelta

# ─── IPv4 monkey-patch (GCP VM has broken IPv6) ────────────────────────
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

# ─── Config ────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SPACES = [
    {"name": "S1", "url": "https://lbjlincoln-nomos-rag-engine.hf.space"},
    {"name": "S3", "url": "https://lbjlincoln-nomos-rag-engine-3.hf.space"},
    {"name": "S5", "url": "https://lbjlincoln-nomos-rag-engine-5.hf.space"},
    {"name": "S9", "url": "https://lbjlincoln-nomos-rag-engine-9.hf.space"},
]

PIPELINES = {
    "9FQdtx38JLPiT3Hx": "Standard",
    "6257AfT1l4FMC6lY": "Graph",
    "cjhEhVs0KV1ExHqX": "Quant",
    "qOSaFFrqO8Jb4VGb": "Orchestrator",
    "Yqw7Pzn0e7m0C6i3": "Auto-Healer",
    "ALd4gOEqiKL5KR1p": "Orchestrator-Old",
}

WEBHOOKS = {
    "Standard":     "/webhook/rag-multi-index-v3",
    "Graph":        "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "Quant":        "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "Orchestrator": "/webhook/orchestrator-v2",
}

CI_EMAIL = os.environ.get("N8N_CI_EMAIL", "ci@nomos.ai")
CI_PASSWORD = os.environ.get("N8N_CI_PASSWORD", "CI-Nomos-2026!")

ERROR_LOG = os.path.join(REPO_ROOT, "logs", "errors", "pipeline-errors.jsonl")
REPORT_FILE = os.path.join(REPO_ROOT, "logs", "monitor-report.json")
HEALTH_FILE = os.path.join(REPO_ROOT, "data", "health-status.json")

# ─── n8n Auth ──────────────────────────────────────────────────────────

def get_opener(host):
    """Login to n8n Space, return authenticated opener."""
    cj = http.cookiejar.MozillaCookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = json.dumps({"emailOrLdapLoginId": CI_EMAIL, "password": CI_PASSWORD}).encode()
    req = urllib.request.Request(f"{host}/rest/login", data=data,
                                headers={"Content-Type": "application/json"}, method="POST")
    try:
        opener.open(req, timeout=15)
        return opener
    except Exception as e:
        print(f"[WARN] Login failed for {host}: {e}", file=sys.stderr)
        return None

def api_get(opener, host, path, timeout=30):
    url = f"{host}/rest{path}"
    req = urllib.request.Request(url, method="GET")
    try:
        resp = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise ConnectionError(f"HTTP {e.code} from {url}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ConnectionError(f"Connection failed for {url}: {e.reason}") from e
    raw = resp.read().decode()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Non-JSON response from {url}: {raw[:200]}")
    return data.get("data", data) if isinstance(data, dict) else data

# ─── Execution Analysis ───────────────────────────────────────────────

def fetch_executions(opener, host, limit=50, hours=None):
    """Fetch recent executions from a Space."""
    result = api_get(opener, host, f"/executions?limit={limit}")
    if isinstance(result, dict):
        execs = result.get("results", result.get("data", []))
    elif isinstance(result, list):
        execs = result
    else:
        execs = []

    if hours:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        filtered = []
        for ex in execs:
            started = ex.get("startedAt", "")
            if started:
                try:
                    dt = datetime.fromisoformat(started.replace("Z", "").replace("+00:00", ""))
                    if dt >= cutoff:
                        filtered.append(ex)
                except (ValueError, TypeError):
                    filtered.append(ex)
        execs = filtered

    return execs

def analyze_execution_nodes(opener, host, exec_id):
    """Deep-analyze a single execution: extract every node's status, timing, errors."""
    try:
        data = api_get(opener, host, f"/executions/{exec_id}?includeData=true")
    except Exception:
        return None

    exec_data_raw = data.get("data", "")
    run_data = {}

    if isinstance(exec_data_raw, str):
        try:
            parsed = json.loads(exec_data_raw)
            if isinstance(parsed, list):
                for entry in reversed(parsed):
                    if isinstance(entry, dict) and "resultData" in entry:
                        parsed = entry
                        break
                else:
                    parsed = parsed[-1] if parsed else {}
            result_data = parsed.get("resultData", {}) if isinstance(parsed, dict) else {}
            if isinstance(result_data, str):
                result_data = json.loads(result_data)
            run_data = result_data.get("runData", {}) if isinstance(result_data, dict) else {}
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

    if not isinstance(run_data, dict):
        return None

    nodes = []
    errors = []
    total_ms = 0

    for node_name, runs in run_data.items():
        if not runs or not isinstance(runs, list):
            continue
        run = runs[0] if isinstance(runs[0], dict) else {}
        err = run.get("error")
        exec_time = run.get("executionTime", 0)
        total_ms += exec_time

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
            "status": "error" if err else "ok",
        }

        if err:
            err_msg = err.get("message", str(err))[:500] if isinstance(err, dict) else str(err)[:500]
            err_type = classify_error(err_msg)
            node_info["error"] = err_msg
            node_info["error_type"] = err_type
            errors.append({
                "node": node_name,
                "error": err_msg,
                "error_type": err_type,
                "time_ms": exec_time,
            })

        nodes.append(node_info)

    return {"nodes": nodes, "errors": errors, "total_ms": total_ms}

def classify_error(msg):
    """Classify an error message into a category."""
    msg_lower = msg.lower()
    if "timeout" in msg_lower or "timed out" in msg_lower:
        return "TIMEOUT"
    if "429" in msg or "rate limit" in msg_lower:
        return "RATE_LIMIT"
    if "401" in msg or "403" in msg or "unauthorized" in msg_lower:
        return "AUTH"
    if "connection" in msg_lower or "econnrefused" in msg_lower or "enotfound" in msg_lower:
        return "CONNECTION"
    if "syntax" in msg_lower or "unexpected token" in msg_lower or "parse" in msg_lower:
        return "SYNTAX"
    if "undefined" in msg_lower or "null" in msg_lower or "cannot read" in msg_lower:
        return "NULL_REF"
    if "500" in msg or "internal server" in msg_lower:
        return "SERVER_ERROR"
    return "UNKNOWN"

# ─── Error Logging ─────────────────────────────────────────────────────

def log_error(pipeline, space, exec_id, node, error_msg, error_type, exec_time_ms):
    """Append a structured error entry to the JSONL log."""
    os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "pipeline": pipeline,
        "space": space,
        "exec_id": str(exec_id),
        "node": node,
        "error": error_msg[:500],
        "type": error_type,
        "time_ms": exec_time_ms,
    }
    with open(ERROR_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

def load_seen_errors():
    """Load exec IDs we've already logged to avoid duplicates."""
    seen = set()
    if os.path.exists(ERROR_LOG):
        try:
            with open(ERROR_LOG) as f:
                for line in f:
                    try:
                        d = json.loads(line.strip())
                        seen.add(d.get("exec_id", ""))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
    return seen

# ─── Health Check (webhook pings) ──────────────────────────────────────

def ping_pipeline(space_url, webhook_path, timeout=30):
    """Ping a pipeline webhook, return response time and status."""
    t0 = time.time()
    try:
        req = urllib.request.Request(
            f"{space_url}{webhook_path}",
            data=json.dumps({"query": "health check", "tenant_id": "monitor", "top_k": 1}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        body = resp.read().decode()
        elapsed = int((time.time() - t0) * 1000)
        ok = len(body) > 20 and "error" not in body.lower()[:100]
        return {"status": "HEALTHY" if ok else "DEGRADED", "time_ms": elapsed, "size": len(body)}
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        return {"status": "DOWN", "time_ms": elapsed, "error": str(e)[:100]}

# ─── Dashboard Output ─────────────────────────────────────────────────

def print_dashboard(report):
    """Print a compact live dashboard."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"\033[2J\033[H")  # Clear screen
    print(f"╔══════════════════════════════════════════════════════════════════╗")
    print(f"║  NOMOS RAG — LIVE MONITOR                    {now}  ║")
    print(f"╠══════════════════════════════════════════════════════════════════╣")

    # Spaces health
    print(f"║  SPACES                                                        ║")
    for s in report.get("spaces", []):
        status_icon = "●" if s["status"] == "UP" else "○"
        print(f"║    {status_icon} {s['name']:<6} {s['status']:<6} {s.get('url',''):<46} ║")

    print(f"╠══════════════════════════════════════════════════════════════════╣")

    # Pipeline health
    print(f"║  PIPELINES                                                     ║")
    print(f"║  {'Name':<15} {'Status':<10} {'Execs':>6} {'OK%':>6} {'Errors':>7} {'Avg ms':>8} ║")
    print(f"║  {'─'*54}  ║")
    for name, stats in report.get("pipelines", {}).items():
        icon = "✓" if stats["success_rate"] >= 80 else "✗" if stats["success_rate"] < 50 else "~"
        print(f"║  {icon} {name:<13} {stats['success_rate']:>5.0f}%  {stats['total']:>6} "
              f"{stats['success_rate']:>5.0f}% {stats['error_count']:>7} {stats.get('avg_ms',0):>8} ║")

    print(f"╠══════════════════════════════════════════════════════════════════╣")

    # Recent errors
    errors = report.get("recent_errors", [])
    print(f"║  RECENT ERRORS ({len(errors)})                                         ║")
    for err in errors[:8]:
        ts = err.get("ts", "")[-8:]  # HH:MM:SS
        print(f"║  {ts} [{err.get('pipeline','?'):<12}] {err.get('node','?'):<20} {err.get('type',''):<10} ║")
    if not errors:
        print(f"║    No errors detected                                          ║")

    print(f"╠══════════════════════════════════════════════════════════════════╣")

    # Error frequency (last 24h)
    freq = report.get("error_frequency", {})
    print(f"║  ERROR FREQUENCY (24h)                                         ║")
    for etype, count in sorted(freq.items(), key=lambda x: -x[1])[:5]:
        bar = "█" * min(count, 30)
        print(f"║    {etype:<15} {count:>4} {bar:<30}          ║")
    if not freq:
        print(f"║    Clean                                                       ║")

    print(f"╠══════════════════════════════════════════════════════════════════╣")

    # Databases
    db = report.get("databases", {})
    print(f"║  DATABASES                                                     ║")
    print(f"║    E5 Pinecone:  {db.get('e5_vectors', '?'):>10} vectors                        ║")
    print(f"║    Supabase:     {db.get('supabase_docs', '?'):>10} docs                           ║")
    print(f"║    Neo4j:        {db.get('neo4j_nodes', '?'):>10} nodes                          ║")

    print(f"╚══════════════════════════════════════════════════════════════════╝")

# ─── Main Logic ────────────────────────────────────────────────────────

def run_monitor(hours=None, errors_only=False, json_output=False):
    """Run a full monitoring pass."""
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "spaces": [],
        "pipelines": {},
        "recent_errors": [],
        "error_frequency": {},
        "databases": {},
    }

    seen_errors = load_seen_errors()
    new_errors = 0

    # 1. Check Space health
    for space in SPACES:
        try:
            urllib.request.urlopen(f"{space['url']}/healthz", timeout=10)
            report["spaces"].append({"name": space["name"], "url": space["url"], "status": "UP"})
        except Exception:
            report["spaces"].append({"name": space["name"], "url": space["url"], "status": "DOWN"})

    # 2. Fetch executions from each Space
    pipeline_stats = defaultdict(lambda: {
        "total": 0, "success": 0, "error_count": 0, "times": [],
        "success_rate": 0, "avg_ms": 0,
    })

    all_errors = []

    for space in SPACES:
        opener = get_opener(space["url"])
        if not opener:
            continue

        try:
            execs = fetch_executions(opener, space["url"], limit=50, hours=hours)
        except Exception:
            continue

        for ex in execs:
            wf_id = ex.get("workflowId", "unknown")
            pipeline = PIPELINES.get(wf_id, "Unknown")
            status = ex.get("status", "unknown")
            exec_id = str(ex.get("id", ""))

            stats = pipeline_stats[pipeline]
            stats["total"] += 1

            if status == "success":
                stats["success"] += 1

            # Duration
            started = ex.get("startedAt", "")
            stopped = ex.get("stoppedAt", "")
            if started and stopped:
                try:
                    t0 = datetime.fromisoformat(started.replace("Z", ""))
                    t1 = datetime.fromisoformat(stopped.replace("Z", ""))
                    ms = int((t1 - t0).total_seconds() * 1000)
                    stats["times"].append(ms)
                except (ValueError, TypeError):
                    pass

            # Error analysis
            if status == "error" and exec_id not in seen_errors:
                stats["error_count"] += 1
                detail = analyze_execution_nodes(opener, space["url"], exec_id)
                if detail and detail["errors"]:
                    for err in detail["errors"]:
                        log_error(pipeline, space["name"], exec_id,
                                  err["node"], err["error"], err["error_type"], err["time_ms"])
                        all_errors.append({
                            "ts": datetime.utcnow().isoformat() + "Z",
                            "pipeline": pipeline,
                            "space": space["name"],
                            "exec_id": exec_id,
                            "node": err["node"],
                            "error": err["error"][:200],
                            "type": err["error_type"],
                        })
                        new_errors += 1
                elif status == "error":
                    # No detailed node info, log the execution-level error
                    log_error(pipeline, space["name"], exec_id,
                              "UNKNOWN", "Execution failed (no node detail)", "UNKNOWN", 0)
                    all_errors.append({
                        "ts": datetime.utcnow().isoformat() + "Z",
                        "pipeline": pipeline, "space": space["name"],
                        "exec_id": exec_id, "node": "UNKNOWN",
                        "error": "Execution failed", "type": "UNKNOWN",
                    })
                    new_errors += 1
            elif status == "error":
                stats["error_count"] += 1

    # Compute stats
    for name, stats in pipeline_stats.items():
        if stats["times"]:
            stats["avg_ms"] = int(sum(stats["times"]) / len(stats["times"]))
        stats["success_rate"] = round(stats["success"] / max(stats["total"], 1) * 100, 1)
        del stats["times"]

    report["pipelines"] = dict(pipeline_stats)
    report["recent_errors"] = all_errors[:20]

    # Error frequency from JSONL (last 24h)
    freq = defaultdict(int)
    if os.path.exists(ERROR_LOG):
        cutoff = datetime.utcnow() - timedelta(hours=24)
        with open(ERROR_LOG) as f:
            for line in f:
                try:
                    d = json.loads(line.strip())
                    ts = d.get("ts", "")
                    dt = datetime.fromisoformat(ts.replace("Z", ""))
                    if dt >= cutoff:
                        freq[d.get("type", "UNKNOWN")] += 1
                except (json.JSONDecodeError, ValueError):
                    pass
    report["error_frequency"] = dict(freq)

    # Save report
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    os.makedirs(os.path.dirname(HEALTH_FILE), exist_ok=True)
    with open(HEALTH_FILE, "w") as f:
        json.dump({
            "timestamp": report["timestamp"],
            "spaces": report["spaces"],
            "pipelines": {k: {"success_rate": v["success_rate"], "total": v["total"]}
                          for k, v in report["pipelines"].items()},
            "error_count_24h": sum(freq.values()),
            "new_errors": new_errors,
        }, f, indent=2)

    return report, new_errors


def main():
    parser = argparse.ArgumentParser(description="Nomos RAG Pipeline Monitor")
    parser.add_argument("--hours", type=int, default=0, help="Filter to last N hours")
    parser.add_argument("--loop", type=int, default=0, help="Continuous mode: interval in seconds")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--errors-only", action="store_true", help="Show only errors")
    args = parser.parse_args()

    hours = args.hours if args.hours > 0 else None

    while True:
        try:
            report, new_errors = run_monitor(hours=hours, errors_only=args.errors_only)

            if args.json:
                print(json.dumps(report, indent=2))
            elif args.errors_only:
                for err in report["recent_errors"]:
                    print(f"[{err['pipeline']}] {err['node']}: {err['type']} — {err['error'][:100]}")
                if not report["recent_errors"]:
                    print("No new errors.")
            else:
                print_dashboard(report)

            if new_errors > 0:
                print(f"\n  >> {new_errors} new errors logged to {ERROR_LOG}")

        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break
        except Exception as e:
            print(f"Monitor error: {e}", file=sys.stderr)

        if args.loop <= 0:
            break

        try:
            time.sleep(args.loop)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break


if __name__ == "__main__":
    main()
