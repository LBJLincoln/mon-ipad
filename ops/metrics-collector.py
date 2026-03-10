#!/usr/bin/env python3
"""
Metrics collector for n8n pipeline executions across HF Spaces.

Polls execution history from S1/S3/S9, extracts per-node performance,
computes aggregated metrics (latency, error rate, throughput, anomalies),
and stores results in rotating JSON files under data/metrics/.

Deep analysis mode (--profile) produces node-by-node pipeline profiling:
bottleneck detection, cascading delay analysis, and per-node-type stats.

Usage:
  source .env.local
  python3 ops/metrics-collector.py              # One-shot collection
  python3 ops/metrics-collector.py --daemon 300  # Run every 300s (5min)
  python3 ops/metrics-collector.py --report       # Show latest metrics report
  python3 ops/metrics-collector.py --profile      # Deep pipeline profiling
  python3 ops/metrics-collector.py --profile standard  # Profile single pipeline
"""

import json
import os
import sys
import time
import ssl
import http.cookiejar
import urllib.request
import urllib.error
from collections import defaultdict
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


# ── Node type classification ─────────────────────────────────

# Ordered list — checked top-to-bottom, first match wins
_NODE_TYPE_RULES = [
    ("trigger", ["trigger", "cron", "schedule", "manual"]),
    ("llm", ["llm", "generation", "chat", "completion", "gpt", "hyde",
             "entity extraction", "query decomposer", "answer", "synthesis"]),
    ("retrieval", ["pinecone", "neo4j", "supabase", "postgres", "search",
                   "query", "bm25", "embedding", "vector", "rerank"]),
    ("routing", ["router", "switch", "if ", "merge", "wait", "branch",
                 "decomposition", "orchestrat"]),
    ("transform", ["set ", "code", "function", "item", "split", "aggregate",
                   "filter", "transform", "map", "reduce", "edit fields"]),
    ("http", ["http", "webhook", "api request", "fetch", "curl"]),
]


def _classify_node_type(name):
    """Classify a node name into a functional category.
    Rules are checked top-to-bottom; first match wins."""
    name_lower = name.lower()
    for ntype, keywords in _NODE_TYPE_RULES:
        for kw in keywords:
            if kw in name_lower:
                return ntype
    return "other"


def _estimate_data_size(data):
    """Rough byte-size estimate for nested n8n data arrays."""
    try:
        return len(json.dumps(data, ensure_ascii=False))
    except (TypeError, ValueError, OverflowError):
        return 0


def _percentile(sorted_vals, pct):
    """Compute percentile from a pre-sorted list. Returns 0 if empty."""
    if not sorted_vals:
        return 0
    idx = int(len(sorted_vals) * pct / 100.0)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


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
    node_type = _classify_node_type(name)

    error_msg = None
    error_http_code = None
    if run.get("error"):
        err = run["error"]
        if isinstance(err, dict):
            error_msg = err.get("message", str(err))[:500]
            error_http_code = err.get("httpCode") or err.get("statusCode")
        else:
            error_msg = str(err)[:500]

    # Count input/output items + estimate data sizes
    items_in = 0
    items_out = 0
    data_size_in = 0
    data_size_out = 0
    input_data = run.get("inputData", {}).get("main", [])
    output_data = run.get("data", {}).get("main", [])
    if isinstance(input_data, list):
        items_in = sum(len(d) for d in input_data if isinstance(d, list))
        data_size_in = _estimate_data_size(input_data)
    if isinstance(output_data, list):
        items_out = sum(len(d) for d in output_data if isinstance(d, list))
        data_size_out = _estimate_data_size(output_data)

    return {
        "name": name,
        "node_type": node_type,
        "execution_time_ms": exec_time,
        "start_time": start_time,
        "status": "error" if error_msg else "success",
        "error": error_msg,
        "error_http_code": error_http_code,
        "items_in": items_in,
        "items_out": items_out,
        "data_size_bytes_in": data_size_in,
        "data_size_bytes_out": data_size_out,
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
    """Compute per-node and per-pipeline aggregated stats with deep profiling."""
    now = datetime.now(timezone.utc)
    ts_1h = now.timestamp() - 3600
    ts_6h = now.timestamp() - 21600
    ts_24h = now.timestamp() - 86400

    pipeline_stats = {}  # pipeline -> {durations, errors, count, earliest, latest}
    # node_key -> {pipeline, node, node_type, durations, errors, total, sizes_in, sizes_out,
    #              durations_1h, durations_6h, durations_24h, errors_1h, errors_6h, errors_24h}
    node_stats = {}
    # node_type -> {durations} (global averages for bottleneck comparison)
    type_stats = defaultdict(list)
    # pipeline -> list of per-execution node timelines (for cascading delay detection)
    pipeline_timelines = defaultdict(list)

    for entry in all_entries:
        pl = entry.get("pipeline", "unknown")
        entry_ts = None
        dt = _parse_iso(entry.get("started_at", ""))
        if dt:
            entry_ts = dt.timestamp()

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

        # Collect per-execution node timeline for cascading delay analysis
        exec_timeline = []

        for node in entry.get("nodes", []):
            nn = node.get("name", "unknown")
            ntype = node.get("node_type", _classify_node_type(nn))
            key = f"{pl}::{nn}"
            if key not in node_stats:
                node_stats[key] = {
                    "pipeline": pl, "node": nn, "node_type": ntype,
                    "durations": [], "error_count": 0, "total": 0,
                    "sizes_in": [], "sizes_out": [],
                    "durations_1h": [], "durations_6h": [], "durations_24h": [],
                    "errors_1h": 0, "errors_6h": 0, "errors_24h": 0,
                    "total_1h": 0, "total_6h": 0, "total_24h": 0,
                }
            ns = node_stats[key]
            ns["total"] += 1
            exec_ms = node.get("execution_time_ms", 0) or 0
            if exec_ms > 0:
                ns["durations"].append(exec_ms)
                type_stats[ntype].append(exec_ms)
            if node.get("status") == "error":
                ns["error_count"] += 1
            # Data sizes
            sz_in = node.get("data_size_bytes_in", 0) or 0
            sz_out = node.get("data_size_bytes_out", 0) or 0
            if sz_in > 0:
                ns["sizes_in"].append(sz_in)
            if sz_out > 0:
                ns["sizes_out"].append(sz_out)

            # Rolling window stats
            if entry_ts is not None:
                if entry_ts >= ts_1h:
                    ns["total_1h"] += 1
                    if exec_ms > 0:
                        ns["durations_1h"].append(exec_ms)
                    if node.get("status") == "error":
                        ns["errors_1h"] += 1
                if entry_ts >= ts_6h:
                    ns["total_6h"] += 1
                    if exec_ms > 0:
                        ns["durations_6h"].append(exec_ms)
                    if node.get("status") == "error":
                        ns["errors_6h"] += 1
                if entry_ts >= ts_24h:
                    ns["total_24h"] += 1
                    if exec_ms > 0:
                        ns["durations_24h"].append(exec_ms)
                    if node.get("status") == "error":
                        ns["errors_24h"] += 1

            # Timeline entry for cascading delay detection
            exec_timeline.append({
                "name": nn,
                "node_type": ntype,
                "start_time": node.get("start_time", ""),
                "execution_time_ms": exec_ms,
            })

        if exec_timeline:
            pipeline_timelines[pl].append(exec_timeline)

    # Compute per-type global averages (for bottleneck comparison)
    type_averages = {}
    for ntype, durations in type_stats.items():
        if durations:
            s = sorted(durations)
            type_averages[ntype] = {
                "avg_ms": int(sum(s) / len(s)),
                "p50_ms": _percentile(s, 50),
                "p95_ms": _percentile(s, 95),
                "count": len(s),
            }

    # Summarize pipelines
    pipeline_summary = {}
    for pl, ps in pipeline_stats.items():
        durations = sorted(ps["durations"])
        avg_lat = int(sum(durations) / len(durations)) if durations else 0
        p95_lat = _percentile(durations, 95)
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

    # Summarize nodes with deep stats
    node_summary = {}
    anomalies = []
    bottlenecks = []

    for key, ns in node_stats.items():
        durations = sorted(ns["durations"])
        avg = int(sum(durations) / len(durations)) if durations else 0
        max_d = max(durations) if durations else 0
        p50 = _percentile(durations, 50)
        p95 = _percentile(durations, 95)

        # Compute % of total pipeline time
        pl = ns["pipeline"]
        pl_total_avg = pipeline_summary.get(pl, {}).get("avg_latency_ms", 1) or 1
        pct_of_total = round(avg / pl_total_avg * 100, 1) if avg > 0 else 0.0

        # Rolling window averages
        def _window_avg(dur_list):
            return int(sum(dur_list) / len(dur_list)) if dur_list else 0

        rolling = {
            "avg_1h_ms": _window_avg(ns["durations_1h"]),
            "avg_6h_ms": _window_avg(ns["durations_6h"]),
            "avg_24h_ms": _window_avg(ns["durations_24h"]),
            "count_1h": ns["total_1h"],
            "count_6h": ns["total_6h"],
            "count_24h": ns["total_24h"],
            "error_rate_1h": round(ns["errors_1h"] / max(ns["total_1h"], 1) * 100, 1),
            "error_rate_6h": round(ns["errors_6h"] / max(ns["total_6h"], 1) * 100, 1),
            "error_rate_24h": round(ns["errors_24h"] / max(ns["total_24h"], 1) * 100, 1),
        }

        # Average data sizes
        avg_size_in = int(sum(ns["sizes_in"]) / len(ns["sizes_in"])) if ns["sizes_in"] else 0
        avg_size_out = int(sum(ns["sizes_out"]) / len(ns["sizes_out"])) if ns["sizes_out"] else 0

        # Anomaly flags
        anomaly_flags = []
        ntype = ns["node_type"]
        type_avg = type_averages.get(ntype, {}).get("avg_ms", 0)
        # Flag: node is 2x slower than average for its type
        if type_avg > 0 and avg > type_avg * 2 and avg > 500:
            anomaly_flags.append(f"2x_slower_than_{ntype}_avg ({avg}ms vs {type_avg}ms)")
        # Flag: P95 is 3x the median (high variance)
        if p50 > 0 and p95 > p50 * 3 and p95 > 1000:
            anomaly_flags.append(f"high_variance (P50={p50}ms, P95={p95}ms)")
        # Flag: error rate above 10%
        err_rate = round(ns["error_count"] / max(ns["total"], 1) * 100, 1)
        if err_rate > 10:
            anomaly_flags.append(f"high_error_rate ({err_rate}%)")
        # Flag: 1h avg much higher than 24h avg (recent degradation)
        if rolling["avg_24h_ms"] > 0 and rolling["avg_1h_ms"] > rolling["avg_24h_ms"] * 2:
            anomaly_flags.append(
                f"recent_degradation (1h={rolling['avg_1h_ms']}ms vs 24h={rolling['avg_24h_ms']}ms)")

        node_summary[key] = {
            "pipeline": pl,
            "node": ns["node"],
            "node_type": ntype,
            "total": ns["total"],
            "avg_ms": avg,
            "p50_ms": p50,
            "p95_ms": p95,
            "max_ms": max_d,
            "pct_of_pipeline": pct_of_total,
            "failure_rate": err_rate,
            "avg_data_in_bytes": avg_size_in,
            "avg_data_out_bytes": avg_size_out,
            "rolling": rolling,
            "anomaly_flags": anomaly_flags,
        }

        # Collect anomalies (backward-compatible: max > 2x avg and above 1s)
        if avg > 0 and max_d > avg * 2 and max_d > 1000:
            anomalies.append({
                "node": ns["node"],
                "pipeline": pl,
                "node_type": ntype,
                "avg_ms": avg,
                "max_ms": max_d,
                "ratio": round(max_d / avg, 1),
                "flags": anomaly_flags,
            })

        # Bottleneck detection: node takes > 25% of pipeline time and > 2x its type avg
        if pct_of_total > 25 and type_avg > 0 and avg > type_avg * 2:
            bottlenecks.append({
                "node": ns["node"],
                "pipeline": pl,
                "node_type": ntype,
                "avg_ms": avg,
                "p95_ms": p95,
                "pct_of_pipeline": pct_of_total,
                "type_avg_ms": type_avg,
                "slowdown_ratio": round(avg / type_avg, 1),
            })

    # Sort anomalies by ratio descending
    anomalies.sort(key=lambda a: a["ratio"], reverse=True)
    bottlenecks.sort(key=lambda b: b["pct_of_pipeline"], reverse=True)

    # Find slowest nodes per pipeline
    slowest_per_pipeline = {}
    for key, ns_info in node_summary.items():
        pl = ns_info["pipeline"]
        if pl not in slowest_per_pipeline or ns_info["avg_ms"] > slowest_per_pipeline[pl]["avg_ms"]:
            slowest_per_pipeline[pl] = ns_info

    # Cascading delay detection across pipeline timelines
    cascading_delays = _detect_cascading_delays(pipeline_timelines)

    result = {
        "updated_at": _ts_now(),
        "total_entries": len(all_entries),
        "pipelines": pipeline_summary,
        "nodes": node_summary,
        "node_type_averages": type_averages,
        "slowest_per_pipeline": slowest_per_pipeline,
        "anomalies": anomalies[:30],
        "bottlenecks": bottlenecks[:20],
        "cascading_delays": cascading_delays[:20],
    }
    _save_json(NODE_PERF, result)
    return result


def _detect_cascading_delays(pipeline_timelines):
    """Detect cascading delays: when node A is slow, is node B consistently delayed?

    Looks at per-execution timelines and correlates above-average node times with
    delays in downstream nodes.
    """
    cascading = []

    for pl, timelines in pipeline_timelines.items():
        if len(timelines) < 3:
            continue

        # Compute baseline average per node across all executions
        node_avgs = defaultdict(list)
        for timeline in timelines:
            for n in timeline:
                if n["execution_time_ms"] > 0:
                    node_avgs[n["name"]].append(n["execution_time_ms"])
        baselines = {}
        for nn, durations in node_avgs.items():
            if durations:
                baselines[nn] = int(sum(durations) / len(durations))

        # For each execution, sort nodes by start_time and check if a slow upstream
        # node correlates with a delayed downstream node
        pair_correlations = defaultdict(lambda: {"slow_together": 0, "upstream_slow": 0})

        for timeline in timelines:
            # Sort by start_time
            sorted_nodes = sorted(timeline, key=lambda n: str(n.get("start_time", "")))
            for i, upstream in enumerate(sorted_nodes):
                u_name = upstream["name"]
                u_time = upstream["execution_time_ms"]
                u_baseline = baselines.get(u_name, 0)
                if u_baseline <= 0 or u_time <= u_baseline * 1.5:
                    continue  # upstream not slow this run

                # Check downstream nodes
                for downstream in sorted_nodes[i + 1:]:
                    d_name = downstream["name"]
                    d_time = downstream["execution_time_ms"]
                    d_baseline = baselines.get(d_name, 0)
                    if d_baseline <= 0:
                        continue

                    pair_key = f"{u_name} -> {d_name}"
                    pair_correlations[pair_key]["upstream_slow"] += 1
                    if d_time > d_baseline * 1.5:
                        pair_correlations[pair_key]["slow_together"] += 1

        # Report pairs where downstream is slow > 60% of the time upstream is slow
        for pair_key, data in pair_correlations.items():
            if data["upstream_slow"] >= 3:
                correlation = data["slow_together"] / data["upstream_slow"]
                if correlation >= 0.6:
                    parts = pair_key.split(" -> ")
                    cascading.append({
                        "pipeline": pl,
                        "upstream": parts[0],
                        "downstream": parts[1],
                        "correlation": round(correlation, 2),
                        "occurrences": data["upstream_slow"],
                        "co_slow": data["slow_together"],
                    })

    cascading.sort(key=lambda c: c["correlation"], reverse=True)
    return cascading


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


# ── Deep Pipeline Profiling ──────────────────────────────────

def print_profile(pipeline_filter=None):
    """Print deep node-by-node pipeline profiling from stored metrics.

    For each pipeline, shows every node with avg/P50/P95 timing, % of total,
    error count, data sizes, rolling trends, bottleneck flags, and cascading
    delay chains.
    """
    perf = _load_json(NODE_PERF, {})
    if not perf or not perf.get("nodes"):
        print("\n  No node-level data found. Run a collection first.")
        print("  (Ensure executions have runData — detail fetching must succeed.)\n")
        return

    pipelines = perf.get("pipelines", {})
    nodes = perf.get("nodes", {})
    type_avgs = perf.get("node_type_averages", {})
    bottlenecks = perf.get("bottlenecks", [])
    cascading = perf.get("cascading_delays", [])

    target_pls = sorted(pipelines.keys())
    if pipeline_filter:
        target_pls = [p for p in target_pls if pipeline_filter.lower() in p.lower()]
        if not target_pls:
            print(f"\n  No pipeline matching '{pipeline_filter}'. "
                  f"Available: {', '.join(sorted(pipelines.keys()))}\n")
            return

    print("=" * 80)
    print("  NOMOS DEEP PIPELINE PROFILER")
    print(f"  Updated: {perf.get('updated_at', '?')}")
    print(f"  Total executions: {perf.get('total_entries', 0)}")
    print("=" * 80, flush=True)

    # Node type baseline averages
    if type_avgs:
        print(f"\n  NODE TYPE BASELINES (global):")
        print(f"  {'Type':<12} {'Avg ms':>8} {'P50 ms':>8} {'P95 ms':>8} {'Samples':>8}")
        print("  " + "-" * 48)
        for ntype in sorted(type_avgs.keys()):
            ta = type_avgs[ntype]
            print(f"  {ntype:<12} {ta['avg_ms']:>8} {ta['p50_ms']:>8} "
                  f"{ta['p95_ms']:>8} {ta['count']:>8}")

    for pl in target_pls:
        pl_info = pipelines.get(pl, {})
        total_execs = pl_info.get("total_executions", 0)
        avg_total = pl_info.get("avg_latency_ms", 0)
        p95_total = pl_info.get("p95_latency_ms", 0)
        err_rate = pl_info.get("error_rate", 0)

        print(f"\n{'=' * 80}")
        print(f"  {pl.upper()} PIPELINE PROFILE "
              f"(avg over {total_execs} executions)")
        print(f"  Total avg: {avg_total:,}ms | P95: {p95_total:,}ms | "
              f"Error rate: {err_rate}%")
        print(f"{'=' * 80}")

        # Collect nodes for this pipeline, sorted by avg_ms descending
        pl_nodes = []
        for key, info in nodes.items():
            if info.get("pipeline") == pl:
                pl_nodes.append(info)
        pl_nodes.sort(key=lambda n: n.get("avg_ms", 0), reverse=True)

        if not pl_nodes:
            print(f"  (no node data collected for this pipeline)")
            continue

        # Main profiling table
        print(f"\n  {'Node':<30} {'Type':<10} {'Avg ms':>8} {'P50':>7} "
              f"{'P95':>7} {'% total':>8} {'Errors':>7} {'Flags':>0}")
        print("  " + "-" * 80)

        for n in pl_nodes:
            name = n["node"][:29]
            ntype = n.get("node_type", "?")[:9]
            avg = n.get("avg_ms", 0)
            p50 = n.get("p50_ms", 0)
            p95 = n.get("p95_ms", 0)
            pct = n.get("pct_of_pipeline", 0)
            errs = n.get("failure_rate", 0)
            flags = n.get("anomaly_flags", [])

            # Indicator characters for quick scanning
            indicator = ""
            if pct > 40:
                indicator = " [BOTTLENECK]"
            elif pct > 25:
                indicator = " [HOT]"
            elif flags:
                indicator = " [!]"

            err_str = f"{errs:.0f}%" if errs > 0 else "0"
            print(f"  {name:<30} {ntype:<10} {avg:>7,} {p50:>7,} "
                  f"{p95:>7,} {pct:>7.1f}% {err_str:>7}{indicator}")

        # Data flow summary
        nodes_with_data = [n for n in pl_nodes
                           if n.get("avg_data_in_bytes", 0) > 0
                           or n.get("avg_data_out_bytes", 0) > 0]
        if nodes_with_data:
            print(f"\n  DATA FLOW:")
            print(f"  {'Node':<30} {'Avg In':>10} {'Avg Out':>10} {'Items In':>0}")
            print("  " + "-" * 55)
            for n in nodes_with_data[:15]:
                name = n["node"][:29]
                sz_in = n.get("avg_data_in_bytes", 0)
                sz_out = n.get("avg_data_out_bytes", 0)

                def _fmt_bytes(b):
                    if b >= 1048576:
                        return f"{b / 1048576:.1f} MB"
                    if b >= 1024:
                        return f"{b / 1024:.1f} KB"
                    return f"{b} B"

                print(f"  {name:<30} {_fmt_bytes(sz_in):>10} {_fmt_bytes(sz_out):>10}")

        # Rolling trends for this pipeline's nodes
        nodes_with_trend = [n for n in pl_nodes
                            if n.get("rolling", {}).get("count_1h", 0) > 0
                            or n.get("rolling", {}).get("count_24h", 0) > 0]
        if nodes_with_trend:
            print(f"\n  ROLLING TRENDS (node avg latency):")
            print(f"  {'Node':<30} {'1h avg':>8} {'6h avg':>8} {'24h avg':>8} {'Trend':>0}")
            print("  " + "-" * 60)
            for n in nodes_with_trend[:15]:
                name = n["node"][:29]
                r = n.get("rolling", {})
                a1 = r.get("avg_1h_ms", 0)
                a6 = r.get("avg_6h_ms", 0)
                a24 = r.get("avg_24h_ms", 0)
                # Trend arrow
                trend = ""
                if a24 > 0 and a1 > 0:
                    ratio = a1 / a24
                    if ratio > 1.5:
                        trend = "  DEGRADING"
                    elif ratio < 0.7:
                        trend = "  improving"
                    else:
                        trend = "  stable"
                a1_s = f"{a1:,}" if a1 else "-"
                a6_s = f"{a6:,}" if a6 else "-"
                a24_s = f"{a24:,}" if a24 else "-"
                print(f"  {name:<30} {a1_s:>8} {a6_s:>8} {a24_s:>8}{trend}")

    # Global bottleneck summary
    if bottlenecks:
        print(f"\n{'=' * 80}")
        print(f"  BOTTLENECK NODES (> 25% of pipeline, > 2x type average)")
        print("=" * 80)
        print(f"  {'Pipeline':<16} {'Node':<28} {'Avg ms':>8} {'% pipe':>7} "
              f"{'Type avg':>9} {'Slowdown':>9}")
        print("  " + "-" * 80)
        for b in bottlenecks[:15]:
            print(f"  {b['pipeline']:<16} {b['node'][:27]:<28} {b['avg_ms']:>7,} "
                  f"{b['pct_of_pipeline']:>6.1f}% {b['type_avg_ms']:>8,} "
                  f"{b['slowdown_ratio']:>8.1f}x")

    # Cascading delay chains
    if cascading:
        print(f"\n{'=' * 80}")
        print(f"  CASCADING DELAYS (upstream slow -> downstream slow correlation)")
        print("=" * 80)
        print(f"  {'Pipeline':<14} {'Upstream':<22} {'Downstream':<22} "
              f"{'Corr':>5} {'Seen':>5}")
        print("  " + "-" * 72)
        for c in cascading[:15]:
            print(f"  {c['pipeline']:<14} {c['upstream'][:21]:<22} "
                  f"{c['downstream'][:21]:<22} {c['correlation']:>5.0%} "
                  f"{c['occurrences']:>5}")

    # Flagged nodes (any anomaly flags)
    flagged = []
    for key, info in nodes.items():
        if info.get("anomaly_flags"):
            flagged.append(info)
    flagged.sort(key=lambda n: len(n.get("anomaly_flags", [])), reverse=True)

    if flagged:
        print(f"\n{'=' * 80}")
        print(f"  FLAGGED NODES ({len(flagged)} nodes with anomalies)")
        print("=" * 80)
        for n in flagged[:20]:
            print(f"  [{n['pipeline']}] {n['node']}")
            for flag in n["anomaly_flags"]:
                print(f"    - {flag}")

    print(f"\n{'=' * 80}", flush=True)


# ── Main ─────────────────────────────────────────────────────────

def main():
    os.makedirs(METRICS_DIR, exist_ok=True)

    # Parse args
    if "--report" in sys.argv:
        print_report()
        return 0

    if "--profile" in sys.argv:
        idx = sys.argv.index("--profile")
        pl_filter = None
        if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
            pl_filter = sys.argv[idx + 1]
        print_profile(pl_filter)
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
