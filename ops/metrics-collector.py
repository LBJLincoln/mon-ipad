#!/usr/bin/env python3
"""
Metrics collector for n8n pipeline executions across HF Spaces.

Polls execution history from S1/S3/S9, extracts per-node performance,
computes aggregated metrics (latency, error rate, throughput, anomalies),
and stores results in rotating JSON files under data/metrics/.

Usage:
  source .env.local
  python3 ops/metrics-collector.py              # One-shot collection
  python3 ops/metrics-collector.py --daemon 300  # Run every 300s (5min)
  python3 ops/metrics-collector.py --report       # Show latest metrics report
"""

import json
import os
import sys
import time
import ssl
import http.cookiejar
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS_DIR = os.path.join(BASE_DIR, "data", "metrics")

EXECUTION_LOG = os.path.join(METRICS_DIR, "execution_log.json")
NODE_PERF = os.path.join(METRICS_DIR, "node_performance.json")
ERROR_CATALOG = os.path.join(METRICS_DIR, "error_catalog.json")
REGRESSION_TRACKER = os.path.join(METRICS_DIR, "regression_tracker.json")

MAX_LOG_ENTRIES = 10000
FETCH_LIMIT = 50

SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

# Known workflow IDs → pipeline names
WORKFLOW_NAMES = {
    "TmgyRP20N4JFd9CB": "standard",
    "6257AfT1l4FMC6lY": "graph",
    "cjhEhVs0KV1ExHqX": "quant",
    "ALd4gOEqiKL5KR1p": "orchestrator",
    "ORa01sX4xI0iRCJ8": "enrichment",
    "Yqw7Pzn0e7m0C6i3": "auto-healer",
}

# Fallback: match workflow name patterns to pipeline names
_NAME_PATTERNS = [
    ("standard", ["standard", "wf5"]),
    ("graph", ["graph", "wf2"]),
    ("quant", ["quant", "wf4"]),
    ("orchestrator", ["orchestrator", "v11"]),
    ("enrichment", ["enrichment", "enrichissement"]),
    ("auto-healer", ["auto-healer", "auto_healer", "autohealer"]),
]


def _resolve_pipeline(wf_id, wf_name):
    """Resolve workflow to a canonical pipeline name."""
    # Direct ID match
    if wf_id in WORKFLOW_NAMES:
        return WORKFLOW_NAMES[wf_id]
    # Name pattern match
    name_lower = wf_name.lower()
    for pipeline, patterns in _NAME_PATTERNS:
        for pat in patterns:
            if pat in name_lower:
                return pipeline
    return wf_name  # Keep raw name as fallback

# ── SSL context (permissive for HF proxy) ───
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


# ── HTTP client per Space (each needs its own cookie jar) ───
class N8nClient:
    """Cookie-authenticated HTTP client for one n8n HF Space."""

    def __init__(self, space_label, base_url):
        self.label = space_label
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPSHandler(context=_ssl_ctx),
        )
        self.logged_in = False

    def _request(self, method, path, data=None, timeout=30):
        """Low-level HTTP request returning (status, body_dict)."""
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            resp = self.opener.open(req, timeout=timeout)
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")[:500]
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, {"error": raw}
        except urllib.error.URLError as e:
            # Connection refused, DNS failure, timeout — likely cold start
            return 503, {"error": f"URLError: {e.reason}"}
        except Exception as e:
            return 0, {"error": str(e)[:300]}

    def login(self):
        """Authenticate via session cookie."""
        status, resp = self._request("POST", "/rest/login", {
            "emailOrLdapLoginId": N8N_EMAIL,
            "password": N8N_PASSWORD,
        })
        if status == 200:
            self.logged_in = True
            return True
        print(f"  [{self.label}] Login FAILED — HTTP {status}", flush=True)
        return False

    def fetch_executions(self):
        """GET /rest/executions with cookie auth. Returns list of executions."""
        if not self.logged_in:
            if not self.login():
                return []

        path = f"/rest/executions?limit={FETCH_LIMIT}&status=success,error,waiting"
        status, resp = self._request("GET", path, timeout=45)

        if status == 503:
            print(f"  [{self.label}] 503 — Space is cold-starting, skip", flush=True)
            return []
        if status != 200:
            print(f"  [{self.label}] Fetch failed — HTTP {status}", flush=True)
            return []

        # n8n wraps in {"data": {"results": [...]}} or {"data": [...]}
        data = resp.get("data", resp)
        if isinstance(data, dict):
            results = data.get("results", data.get("data", []))
        elif isinstance(data, list):
            results = data
        else:
            results = []

        return results

    def fetch_execution_detail(self, exec_id):
        """GET single execution with full run data."""
        if not self.logged_in:
            if not self.login():
                return None
        path = f"/rest/executions/{exec_id}"
        status, resp = self._request("GET", path, timeout=30)
        if status == 200:
            return resp.get("data", resp) if isinstance(resp, dict) else resp
        return None


# ── Parsing helpers ──────────────────────────────────────────────

def _parse_iso(ts):
    """Parse ISO timestamp string to datetime (UTC). Returns None on failure."""
    if not ts:
        return None
    try:
        # Handle both Z and +00:00 suffixes
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _ts_now():
    """Current UTC ISO timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_execution(raw, space_label):
    """Parse a raw n8n execution dict into our normalized format."""
    exec_id = str(raw.get("id", ""))
    if not exec_id:
        return None

    wf_data = raw.get("workflowData", {}) or {}
    wf_id = str(wf_data.get("id", raw.get("workflowId", "")))
    wf_name = wf_data.get("name", WORKFLOW_NAMES.get(wf_id, "unknown"))
    pipeline = _resolve_pipeline(wf_id, wf_name)

    started = raw.get("startedAt", "")
    stopped = raw.get("stoppedAt", "")
    status = raw.get("status", "unknown")

    # Compute duration
    duration_ms = 0
    dt_start = _parse_iso(started)
    dt_stop = _parse_iso(stopped)
    if dt_start and dt_stop:
        duration_ms = int((dt_stop - dt_start).total_seconds() * 1000)

    # Node-level data from resultData.runData
    run_data = {}
    result_data = raw.get("data", {})
    if isinstance(result_data, dict):
        run_data = result_data.get("resultData", {}).get("runData", {})

    nodes = []
    for node_name, runs in run_data.items():
        if not isinstance(runs, list):
            continue
        for run in runs:
            node_entry = _parse_node(node_name, run)
            nodes.append(node_entry)

    return {
        "id": exec_id,
        "space": space_label,
        "workflow_id": wf_id,
        "workflow_name": wf_name,
        "pipeline": pipeline,
        "status": status,
        "started_at": started,
        "stopped_at": stopped,
        "duration_ms": duration_ms,
        "node_count": len(nodes),
        "nodes": nodes,
        "collected_at": _ts_now(),
    }


def _parse_node(name, run):
    """Extract performance data for a single node run."""
    exec_time = run.get("executionTime", 0) or 0
    start_time = run.get("startTime", "")
    error_msg = None
    if run.get("error"):
        err = run["error"]
        error_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)

    # Count input/output items
    items_in = 0
    items_out = 0
    input_data = run.get("inputData", {}).get("main", [])
    output_data = run.get("data", {}).get("main", [])
    if isinstance(input_data, list):
        items_in = sum(len(d) for d in input_data if isinstance(d, list))
    if isinstance(output_data, list):
        items_out = sum(len(d) for d in output_data if isinstance(d, list))

    return {
        "name": name,
        "execution_time_ms": exec_time,
        "start_time": start_time,
        "status": "error" if error_msg else "success",
        "error": error_msg,
        "items_in": items_in,
        "items_out": items_out,
    }


# ── Storage helpers ──────────────────────────────────────────────

def _load_json(path, default=None):
    """Load JSON file, return default on any error."""
    if default is None:
        default = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    """Atomically write JSON file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ── Core collection ──────────────────────────────────────────────

def collect_all():
    """Poll all Spaces, parse executions, store and return new entries."""
    os.makedirs(METRICS_DIR, exist_ok=True)

    # Load existing execution IDs for de-duplication
    existing_log = _load_json(EXECUTION_LOG, [])
    seen_ids = {e["id"] for e in existing_log if isinstance(e, dict) and "id" in e}

    new_entries = []
    space_stats = {}

    for label, url in SPACES.items():
        print(f"\n  [{label}] Connecting to {url} ...", flush=True)
        client = N8nClient(label, url)
        raw_list = client.fetch_executions()

        fetched = 0
        new = 0
        errors = 0

        for raw_exec in raw_list:
            fetched += 1
            exec_id = str(raw_exec.get("id", ""))
            if exec_id in seen_ids:
                continue

            # Fetch detailed data if runData is missing
            has_run_data = False
            exec_data = raw_exec.get("data", {})
            if isinstance(exec_data, dict):
                has_run_data = bool(exec_data.get("resultData", {}).get("runData"))

            if not has_run_data and exec_id:
                detail = client.fetch_execution_detail(exec_id)
                if detail:
                    raw_exec = detail

            parsed = parse_execution(raw_exec, label)
            if not parsed:
                continue

            new_entries.append(parsed)
            seen_ids.add(exec_id)
            new += 1
            if parsed["status"] == "error":
                errors += 1

        space_stats[label] = {"fetched": fetched, "new": new, "errors": errors}
        print(f"  [{label}] {fetched} fetched, {new} new, {errors} errors", flush=True)

    # Append to execution log (keep max entries, drop oldest)
    combined = existing_log + new_entries
    if len(combined) > MAX_LOG_ENTRIES:
        combined = combined[-MAX_LOG_ENTRIES:]
    _save_json(EXECUTION_LOG, combined)

    # Update aggregated files
    _update_node_performance(combined)
    _update_error_catalog(combined)
    _update_regression_tracker(combined)

    return new_entries, space_stats


# ── Aggregation ──────────────────────────────────────────────────

def _update_node_performance(all_entries):
    """Compute per-node and per-pipeline aggregated stats."""
    pipeline_stats = {}  # pipeline -> {durations, errors, count, earliest, latest}
    node_stats = {}      # node_name -> {durations, errors, count}

    for entry in all_entries:
        pl = entry.get("pipeline", "unknown")
        if pl not in pipeline_stats:
            pipeline_stats[pl] = {
                "durations": [], "error_count": 0, "total": 0,
                "earliest": entry.get("started_at", ""),
                "latest": entry.get("started_at", ""),
            }
        ps = pipeline_stats[pl]
        ps["total"] += 1
        if entry.get("duration_ms", 0) > 0:
            ps["durations"].append(entry["duration_ms"])
        if entry.get("status") == "error":
            ps["error_count"] += 1
        if entry.get("started_at", "") > ps["latest"]:
            ps["latest"] = entry["started_at"]
        if entry.get("started_at", "") < ps["earliest"] or not ps["earliest"]:
            ps["earliest"] = entry["started_at"]

        for node in entry.get("nodes", []):
            nn = node.get("name", "unknown")
            key = f"{pl}::{nn}"
            if key not in node_stats:
                node_stats[key] = {"pipeline": pl, "node": nn, "durations": [], "error_count": 0, "total": 0}
            ns = node_stats[key]
            ns["total"] += 1
            if node.get("execution_time_ms", 0) > 0:
                ns["durations"].append(node["execution_time_ms"])
            if node.get("status") == "error":
                ns["error_count"] += 1

    # Summarize pipelines
    pipeline_summary = {}
    for pl, ps in pipeline_stats.items():
        durations = ps["durations"]
        avg_lat = int(sum(durations) / len(durations)) if durations else 0
        p95_lat = int(sorted(durations)[int(len(durations) * 0.95)]) if len(durations) > 1 else avg_lat
        # Throughput: requests per hour based on time window
        dt_earliest = _parse_iso(ps["earliest"])
        dt_latest = _parse_iso(ps["latest"])
        hours_span = 1.0
        if dt_earliest and dt_latest:
            span = (dt_latest - dt_earliest).total_seconds() / 3600.0
            if span > 0.01:
                hours_span = span
        throughput = round(ps["total"] / hours_span, 1)

        pipeline_summary[pl] = {
            "total_executions": ps["total"],
            "avg_latency_ms": avg_lat,
            "p95_latency_ms": p95_lat,
            "error_rate": round(ps["error_count"] / max(ps["total"], 1) * 100, 1),
            "throughput_per_hour": throughput,
            "earliest": ps["earliest"],
            "latest": ps["latest"],
        }

    # Summarize nodes + find anomalies
    node_summary = {}
    anomalies = []
    for key, ns in node_stats.items():
        durations = ns["durations"]
        avg = int(sum(durations) / len(durations)) if durations else 0
        max_d = max(durations) if durations else 0
        node_summary[key] = {
            "pipeline": ns["pipeline"],
            "node": ns["node"],
            "total": ns["total"],
            "avg_ms": avg,
            "max_ms": max_d,
            "failure_rate": round(ns["error_count"] / max(ns["total"], 1) * 100, 1),
        }
        # Anomaly: max is 2x the average and above 1s
        if avg > 0 and max_d > avg * 2 and max_d > 1000:
            anomalies.append({
                "node": ns["node"],
                "pipeline": ns["pipeline"],
                "avg_ms": avg,
                "max_ms": max_d,
                "ratio": round(max_d / avg, 1),
            })

    # Sort anomalies by ratio descending
    anomalies.sort(key=lambda a: a["ratio"], reverse=True)

    # Find slowest nodes per pipeline
    slowest_per_pipeline = {}
    for key, ns_info in node_summary.items():
        pl = ns_info["pipeline"]
        if pl not in slowest_per_pipeline or ns_info["avg_ms"] > slowest_per_pipeline[pl]["avg_ms"]:
            slowest_per_pipeline[pl] = ns_info

    result = {
        "updated_at": _ts_now(),
        "total_entries": len(all_entries),
        "pipelines": pipeline_summary,
        "nodes": node_summary,
        "slowest_per_pipeline": slowest_per_pipeline,
        "anomalies": anomalies[:20],
    }
    _save_json(NODE_PERF, result)
    return result


def _update_error_catalog(all_entries):
    """Build a catalog of unique errors with counts."""
    errors = {}  # error_key -> {message, pipeline, node, count, last_seen, space}
    for entry in all_entries:
        for node in entry.get("nodes", []):
            err = node.get("error")
            if not err:
                continue
            # Normalize: take first 200 chars as key
            err_key = err[:200].strip()
            if err_key not in errors:
                errors[err_key] = {
                    "message": err[:500],
                    "pipeline": entry.get("pipeline", "unknown"),
                    "node": node.get("name", "unknown"),
                    "count": 0,
                    "first_seen": entry.get("started_at", ""),
                    "last_seen": "",
                    "spaces": [],
                }
            errors[err_key]["count"] += 1
            errors[err_key]["last_seen"] = entry.get("started_at", "")
            space = entry.get("space", "")
            if space and space not in errors[err_key]["spaces"]:
                errors[err_key]["spaces"].append(space)

    # Sort by count descending
    catalog = sorted(errors.values(), key=lambda e: e["count"], reverse=True)

    result = {
        "updated_at": _ts_now(),
        "unique_errors": len(catalog),
        "total_error_occurrences": sum(e["count"] for e in catalog),
        "errors": catalog[:200],
    }
    _save_json(ERROR_CATALOG, result)
    return result


def _update_regression_tracker(all_entries):
    """Add an hourly snapshot of pipeline performance for trend tracking."""
    tracker = _load_json(REGRESSION_TRACKER, {"snapshots": []})
    # Handle legacy format (was a plain list) or corrupted data
    if not isinstance(tracker, dict) or "snapshots" not in tracker:
        tracker = {"snapshots": []}
    snapshots = tracker.get("snapshots", [])

    now = datetime.now(timezone.utc)
    one_hour_ago = now.timestamp() - 3600
    twenty_four_hours_ago = now.timestamp() - 86400

    # Split entries into 1h and 24h windows
    recent_1h = []
    recent_24h = []
    for entry in all_entries:
        dt = _parse_iso(entry.get("started_at", ""))
        if not dt:
            continue
        ts = dt.timestamp()
        if ts >= one_hour_ago:
            recent_1h.append(entry)
        if ts >= twenty_four_hours_ago:
            recent_24h.append(entry)

    def _window_stats(entries):
        """Compute per-pipeline stats for a time window."""
        by_pipeline = {}
        for e in entries:
            pl = e.get("pipeline", "unknown")
            if pl not in by_pipeline:
                by_pipeline[pl] = {"durations": [], "errors": 0, "total": 0}
            by_pipeline[pl]["total"] += 1
            if e.get("duration_ms", 0) > 0:
                by_pipeline[pl]["durations"].append(e["duration_ms"])
            if e.get("status") == "error":
                by_pipeline[pl]["errors"] += 1
        result = {}
        for pl, data in by_pipeline.items():
            d = data["durations"]
            result[pl] = {
                "count": data["total"],
                "avg_latency_ms": int(sum(d) / len(d)) if d else 0,
                "error_rate": round(data["errors"] / max(data["total"], 1) * 100, 1),
            }
        return result

    snapshot = {
        "timestamp": _ts_now(),
        "last_1h": _window_stats(recent_1h),
        "last_24h": _window_stats(recent_24h),
        "entries_1h": len(recent_1h),
        "entries_24h": len(recent_24h),
    }

    # Detect anomalies: compare 1h vs 24h
    trend_alerts = []
    for pl, stats_1h in snapshot["last_1h"].items():
        stats_24h = snapshot["last_24h"].get(pl)
        if not stats_24h or stats_24h["count"] < 5:
            continue
        # Latency spike
        if stats_24h["avg_latency_ms"] > 0:
            ratio = stats_1h["avg_latency_ms"] / stats_24h["avg_latency_ms"]
            if ratio > 2.0:
                trend_alerts.append({
                    "type": "latency_spike",
                    "pipeline": pl,
                    "last_1h_ms": stats_1h["avg_latency_ms"],
                    "last_24h_ms": stats_24h["avg_latency_ms"],
                    "ratio": round(ratio, 1),
                })
        # Error spike
        if stats_1h["error_rate"] > stats_24h["error_rate"] + 10:
            trend_alerts.append({
                "type": "error_spike",
                "pipeline": pl,
                "last_1h_err": stats_1h["error_rate"],
                "last_24h_err": stats_24h["error_rate"],
            })

    snapshot["trend_alerts"] = trend_alerts
    snapshots.append(snapshot)

    # Keep last 168 snapshots (~7 days at hourly)
    if len(snapshots) > 168:
        snapshots = snapshots[-168:]

    tracker["snapshots"] = snapshots
    tracker["updated_at"] = _ts_now()
    _save_json(REGRESSION_TRACKER, tracker)
    return snapshot


# ── Reporting ────────────────────────────────────────────────────

def print_report():
    """Print a formatted summary from stored metrics."""
    print("=" * 70)
    print("  NOMOS METRICS REPORT")
    print("=" * 70, flush=True)

    # Node performance
    perf = _load_json(NODE_PERF, {})
    if not perf:
        print("\n  No metrics data found. Run a collection first.\n")
        return

    print(f"\n  Updated: {perf.get('updated_at', '?')}")
    print(f"  Total executions tracked: {perf.get('total_entries', 0)}")

    # Per-pipeline summary
    pipelines = perf.get("pipelines", {})
    if pipelines:
        print(f"\n  {'PIPELINE':<16} {'TOTAL':>6} {'AVG ms':>8} {'P95 ms':>8} {'ERR %':>7} {'req/h':>7}")
        print("  " + "-" * 54)
        for pl, stats in sorted(pipelines.items()):
            print(f"  {pl:<16} {stats['total_executions']:>6} "
                  f"{stats['avg_latency_ms']:>8} {stats['p95_latency_ms']:>8} "
                  f"{stats['error_rate']:>6.1f}% {stats['throughput_per_hour']:>7.1f}")

    # Slowest nodes
    slowest = perf.get("slowest_per_pipeline", {})
    if slowest:
        print(f"\n  SLOWEST NODES (per pipeline):")
        for pl, info in sorted(slowest.items()):
            print(f"    {pl}: {info['node']} — avg {info['avg_ms']}ms, max {info['max_ms']}ms")

    # Anomalies
    anomalies = perf.get("anomalies", [])
    if anomalies:
        print(f"\n  ANOMALIES (max > 2x avg, > 1s):")
        for a in anomalies[:10]:
            print(f"    [{a['pipeline']}] {a['node']} — avg {a['avg_ms']}ms, max {a['max_ms']}ms ({a['ratio']}x)")

    # Error catalog
    err_cat = _load_json(ERROR_CATALOG, {})
    if err_cat.get("errors"):
        print(f"\n  TOP ERRORS ({err_cat.get('unique_errors', 0)} unique, "
              f"{err_cat.get('total_error_occurrences', 0)} total):")
        for e in err_cat["errors"][:5]:
            print(f"    [{e['pipeline']}:{e['node']}] x{e['count']} — {e['message'][:80]}")
            if e.get("spaces"):
                print(f"      Spaces: {', '.join(e['spaces'])}")

    # Regression tracker — latest snapshot
    tracker = _load_json(REGRESSION_TRACKER, {})
    snapshots = tracker.get("snapshots", [])
    if snapshots:
        latest = snapshots[-1]
        print(f"\n  TRENDS (snapshot {latest['timestamp']}):")
        print(f"    Entries last 1h: {latest.get('entries_1h', 0)}, "
              f"last 24h: {latest.get('entries_24h', 0)}")

        # Show 1h vs 24h comparison
        last_1h = latest.get("last_1h", {})
        last_24h = latest.get("last_24h", {})
        all_pls = sorted(set(list(last_1h.keys()) + list(last_24h.keys())))
        if all_pls:
            print(f"\n    {'PIPELINE':<16} {'1h avg':>8} {'24h avg':>8} {'1h err%':>8} {'24h err%':>8}")
            print("    " + "-" * 50)
            for pl in all_pls:
                s1 = last_1h.get(pl, {})
                s24 = last_24h.get(pl, {})
                print(f"    {pl:<16} "
                      f"{s1.get('avg_latency_ms', '-'):>8} "
                      f"{s24.get('avg_latency_ms', '-'):>8} "
                      f"{str(s1.get('error_rate', '-')) + '%' if 'error_rate' in s1 else '-':>8} "
                      f"{str(s24.get('error_rate', '-')) + '%' if 'error_rate' in s24 else '-':>8}")

        alerts = latest.get("trend_alerts", [])
        if alerts:
            print(f"\n    ALERTS:")
            for a in alerts:
                if a["type"] == "latency_spike":
                    print(f"      LATENCY SPIKE [{a['pipeline']}]: "
                          f"{a['last_1h_ms']}ms vs {a['last_24h_ms']}ms ({a['ratio']}x)")
                elif a["type"] == "error_spike":
                    print(f"      ERROR SPIKE [{a['pipeline']}]: "
                          f"{a['last_1h_err']}% vs {a['last_24h_err']}%")
        else:
            print(f"\n    No trend alerts.")

    print(f"\n{'=' * 70}", flush=True)


# ── Main ─────────────────────────────────────────────────────────

def main():
    os.makedirs(METRICS_DIR, exist_ok=True)

    # Parse args
    if "--report" in sys.argv:
        print_report()
        return 0

    daemon_mode = False
    interval = 300
    if "--daemon" in sys.argv:
        daemon_mode = True
        idx = sys.argv.index("--daemon")
        if idx + 1 < len(sys.argv):
            try:
                interval = int(sys.argv[idx + 1])
            except ValueError:
                pass

    print("=" * 70)
    print("  NOMOS METRICS COLLECTOR")
    print(f"  Spaces: {', '.join(SPACES.keys())}")
    print(f"  Mode: {'daemon (every ' + str(interval) + 's)' if daemon_mode else 'one-shot'}")
    print(f"  Storage: {METRICS_DIR}")
    print("=" * 70, flush=True)

    run_count = 0
    while True:
        run_count += 1
        ts = _ts_now()
        print(f"\n{'─' * 50}")
        print(f"  Run #{run_count} at {ts}")
        print(f"{'─' * 50}", flush=True)

        try:
            new_entries, space_stats = collect_all()
        except Exception as e:
            print(f"\n  COLLECTION ERROR: {e}", flush=True)
            if not daemon_mode:
                return 1
            print(f"  Retrying in {interval}s ...", flush=True)
            time.sleep(interval)
            continue

        total_new = sum(s["new"] for s in space_stats.values())
        total_err = sum(s["errors"] for s in space_stats.values())

        print(f"\n  SUMMARY: {total_new} new executions collected, {total_err} errors", flush=True)

        # Print compact per-pipeline breakdown of new entries
        by_pipeline = {}
        for entry in new_entries:
            pl = entry.get("pipeline", "unknown")
            if pl not in by_pipeline:
                by_pipeline[pl] = {"count": 0, "errors": 0, "durations": []}
            by_pipeline[pl]["count"] += 1
            if entry.get("status") == "error":
                by_pipeline[pl]["errors"] += 1
            if entry.get("duration_ms", 0) > 0:
                by_pipeline[pl]["durations"].append(entry["duration_ms"])

        if by_pipeline:
            print(f"\n  {'PIPELINE':<16} {'NEW':>5} {'ERR':>5} {'AVG ms':>8}")
            print("  " + "-" * 36)
            for pl, data in sorted(by_pipeline.items()):
                d = data["durations"]
                avg = int(sum(d) / len(d)) if d else 0
                print(f"  {pl:<16} {data['count']:>5} {data['errors']:>5} {avg:>8}")

        # Load current total
        log = _load_json(EXECUTION_LOG, [])
        print(f"\n  Total tracked: {len(log)} executions (max {MAX_LOG_ENTRIES})")

        if not daemon_mode:
            print()
            print_report()
            return 0

        print(f"\n  Sleeping {interval}s ...", flush=True)
        time.sleep(interval)

    return 0


if __name__ == "__main__":
    sys.exit(main())
