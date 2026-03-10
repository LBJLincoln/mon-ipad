#!/usr/bin/env python3
"""
Pipeline Error Analyzer — Automated error analysis across all RAG pipelines.

Queries Supabase pipeline_errors table and n8n execution APIs to produce:
  1. Error analysis grouped by workflow, node, and error type
  2. Node-by-node performance reports with best/worst executions
  3. Persistent error library at data/error-library.json
  4. Per-node timing and throughput metrics from n8n executions
  5. Human-readable CLI summary + JSON report files

Usage:
  source .env.local
  python3 ops/error-analyzer.py                    # Full analysis (last 24h)
  python3 ops/error-analyzer.py --period 7d        # Last 7 days
  python3 ops/error-analyzer.py --period 30d       # Last 30 days
  python3 ops/error-analyzer.py --pipeline standard # Specific pipeline
  python3 ops/error-analyzer.py --library           # Show error library
  python3 ops/error-analyzer.py --loop 300          # Continuous every 5min
  python3 ops/error-analyzer.py --no-n8n            # Skip n8n API (Supabase only)

Last updated: 2026-03-10
"""

# ── IPv4 monkey-patch (required for HF Spaces DNS) ──────────────
import socket
from socket import AF_INET

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only

# ── Standard library imports ────────────────────────────────────
import argparse
import http.cookiejar
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# ── Config ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

ERROR_LIBRARY_PATH = os.path.join(DATA_DIR, "error-library.json")
ERROR_REPORT_PATH = os.path.join(DATA_DIR, "error-analysis-report.json")
HEALTH_STATUS_PATH = os.path.join(DATA_DIR, "health-status.json")
DEBUG_PLAYBOOK_PATH = os.path.join(BASE_DIR, "technicals", "DEBUG-PLAYBOOK.md")

# Paris timezone (CET = UTC+1)
PARIS_TZ = timezone(timedelta(hours=1))

# Supabase REST API
SUPABASE_URL = "https://ayqviqmxifzmhphiqfmj.supabase.co/rest/v1"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF5cXZpcW14aWZ6bWhwaGlxZm1qIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3NjkwMjM1NTgsImV4cCI6MjA4NDU5OTU1OH0."
    "5_OSvXMCUYJjGis3qsHBa-jrODFFFJpHO_H84eLp9eM"
)

# n8n HF Spaces
SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

# Workflow ID → pipeline name mapping
WORKFLOW_MAP = {
    "TmgyRP20N4JFd9CB": "standard",
    "6257AfT1l4FMC6lY": "graph",
    "cjhEhVs0KV1ExHqX": "quant",
    "ALd4gOEqiKL5KR1p": "orchestrator",
    "qOSaFFrqO8Jb4VGb": "orchestrator",
    "ORa01sX4xI0iRCJ8": "enrichment",
    "Yqw7Pzn0e7m0C6i3": "auto-healer",
}

# Name-based fallback patterns
_NAME_PATTERNS = [
    ("standard", ["standard", "wf5"]),
    ("graph", ["graph", "wf2"]),
    ("quant", ["quant", "wf4"]),
    ("orchestrator", ["orchestrator", "v11"]),
    ("enrichment", ["enrichment", "enrichissement"]),
    ("auto-healer", ["auto-healer", "auto_healer", "autohealer"]),
]

# Period shortcuts
PERIOD_MAP = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "3d": timedelta(days=3),
    "14d": timedelta(days=14),
}

# Error type classification rules
_ERROR_TYPE_RULES = [
    ("RATE_LIMIT", ["429", "rate limit", "too many requests", "quota"]),
    ("TIMEOUT", ["timeout", "timed out", "etimedout", "econnreset"]),
    ("AUTH", ["401", "403", "unauthorized", "forbidden", "credential"]),
    ("CONNECTION", ["econnrefused", "enotfound", "dns", "connection refused",
                    "502", "503", "service unavailable"]),
    ("LLM_ERROR", ["llm", "model", "completion", "generation failed",
                   "content_policy", "context_length"]),
    ("SQL_ERROR", ["sql", "syntax error", "relation", "column", "query must start"]),
    ("EMBEDDING", ["embedding", "jina", "pinecone", "vector"]),
    ("NEO4J", ["neo4j", "bolt", "cypher"]),
    ("PARSE_ERROR", ["json", "parse", "unexpected token", "invalid json"]),
    ("ENV_VAR", ["$env", "env var", "environment variable", "block_env"]),
    ("WEBHOOK", ["404", "webhook not registered", "not found"]),
    ("MEMORY", ["oom", "out of memory", "heap", "allocation"]),
]


# ── SSL context ─────────────────────────────────────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


# ── .env.local loader ───────────────────────────────────────────
def _load_env():
    env_file = os.path.join(BASE_DIR, ".env.local")
    if not os.path.exists(env_file):
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env()


# ── Utility functions ───────────────────────────────────────────

def _ts_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_paris(dt):
    """Convert datetime to Paris timezone formatted string."""
    if dt is None:
        return "N/A"
    paris = dt.astimezone(PARIS_TZ)
    return paris.strftime("%H:%M:%S")


def _ts_paris_full(dt):
    """Full Paris datetime string."""
    if dt is None:
        return "N/A"
    paris = dt.astimezone(PARIS_TZ)
    return paris.strftime("%Y-%m-%d %H:%M:%S CET")


def _parse_iso(ts):
    """Parse ISO timestamp string to datetime (UTC). Returns None on failure."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _classify_error_type(error_msg):
    """Classify an error message into a type category."""
    if not error_msg:
        return "UNKNOWN"
    msg_lower = error_msg.lower()
    for etype, keywords in _ERROR_TYPE_RULES:
        for kw in keywords:
            if kw in msg_lower:
                return etype
    return "OTHER"


def _resolve_pipeline(wf_id, wf_name=""):
    """Resolve workflow ID or name to canonical pipeline name."""
    if wf_id in WORKFLOW_MAP:
        return WORKFLOW_MAP[wf_id]
    name_lower = (wf_name or "").lower()
    for pipeline, patterns in _NAME_PATTERNS:
        for pat in patterns:
            if pat in name_lower:
                return pipeline
    return wf_name or "unknown"


def _load_json(path, default=None):
    """Load JSON file, return default on any error."""
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _save_json(path, data):
    """Atomically write JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _truncate(s, maxlen=120):
    """Truncate string with ellipsis."""
    if not s:
        return ""
    s = str(s)
    return s[:maxlen] + "..." if len(s) > maxlen else s


# ── Supabase client ─────────────────────────────────────────────

class SupabaseClient:
    """REST client for Supabase pipeline_errors table."""

    def __init__(self):
        self.base_url = SUPABASE_URL
        self.headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _request(self, path, timeout=30):
        """GET request to Supabase REST API."""
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        for k, v in self.headers.items():
            req.add_header(k, v)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else []
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            print(f"  [Supabase] HTTP {e.code}: {body}", flush=True)
            return []
        except Exception as e:
            print(f"  [Supabase] Error: {e}", flush=True)
            return []

    def fetch_errors(self, since_dt=None, limit=500):
        """Fetch pipeline errors, optionally filtered by timestamp."""
        path = "/pipeline_errors?select=*&order=timestamp.desc"
        if since_dt:
            iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            path += f"&timestamp=gte.{iso}"
        path += f"&limit={limit}"
        return self._request(path)

    def fetch_all_errors(self, limit=1000):
        """Fetch all errors without time filter."""
        path = f"/pipeline_errors?select=*&order=timestamp.desc&limit={limit}"
        return self._request(path)


# ── n8n client (cookie auth) ────────────────────────────────────

class N8nClient:
    """Cookie-authenticated HTTP client for one n8n HF Space."""

    def __init__(self, label, base_url):
        self.label = label
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPSHandler(context=_ssl_ctx),
        )
        self.logged_in = False

    def _request(self, method, path, data=None, timeout=30):
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
            return 503, {"error": f"URLError: {e.reason}"}
        except Exception as e:
            return 0, {"error": str(e)[:300]}

    def login(self):
        status, resp = self._request("POST", "/rest/login", {
            "emailOrLdapLoginId": N8N_EMAIL,
            "password": N8N_PASSWORD,
        })
        if status == 200:
            self.logged_in = True
            return True
        print(f"  [{self.label}] Login FAILED — HTTP {status}", flush=True)
        return False

    def fetch_executions(self, workflow_id=None, limit=20):
        if not self.logged_in:
            if not self.login():
                return []
        path = f"/rest/executions?limit={limit}&status=success,error,waiting"
        if workflow_id:
            path += f"&workflowId={workflow_id}"
        status, resp = self._request("GET", path, timeout=45)
        if status != 200:
            return []
        data = resp.get("data", resp)
        if isinstance(data, dict):
            return data.get("results", data.get("data", []))
        return data if isinstance(data, list) else []

    def fetch_execution_detail(self, exec_id):
        if not self.logged_in:
            if not self.login():
                return None
        path = f"/rest/executions/{exec_id}"
        status, resp = self._request("GET", path, timeout=30)
        if status == 200:
            return resp.get("data", resp) if isinstance(resp, dict) else resp
        return None


# ── Debug Playbook parser ───────────────────────────────────────

def parse_debug_playbook():
    """Parse DEBUG-PLAYBOOK.md to extract known fixes indexed by keyword."""
    fixes = {}
    if not os.path.exists(DEBUG_PLAYBOOK_PATH):
        return fixes

    try:
        with open(DEBUG_PLAYBOOK_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return fixes

    # Match FIX-XX entries: ### FIX-NN: Description
    pattern = r"### (FIX-\d+):\s*(.+?)(?=\n###|\n---|\n## |\Z)"
    for match in re.finditer(pattern, content, re.DOTALL):
        fix_id = match.group(1)
        block = match.group(2).strip()
        # First line is the title
        lines = block.split("\n")
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        # Extract keywords from title and body
        keywords = set()
        for word in re.findall(r'\b[a-zA-Z_$]{3,}\b', title.lower()):
            keywords.add(word)
        # Also extract specific patterns
        for kw in ["rate limit", "timeout", "429", "401", "403", "500", "502",
                    "503", "env", "credential", "webhook", "neo4j", "pinecone",
                    "sql", "embedding", "oom", "memory", "stuck", "json"]:
            if kw in block.lower():
                keywords.add(kw)

        fixes[fix_id] = {
            "title": title,
            "keywords": list(keywords),
            "body_preview": body[:300],
        }

    return fixes


def find_matching_fix(error_msg, known_fixes):
    """Find the best matching FIX for an error message."""
    if not error_msg or not known_fixes:
        return None, None

    msg_lower = error_msg.lower()
    best_fix = None
    best_score = 0

    for fix_id, fix_data in known_fixes.items():
        score = 0
        for kw in fix_data["keywords"]:
            if kw in msg_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_fix = fix_id

    if best_score >= 2:
        return best_fix, known_fixes[best_fix]["title"]
    return None, None


# ── Error Library management ────────────────────────────────────

def load_error_library():
    """Load or initialize the error library."""
    lib = _load_json(ERROR_LIBRARY_PATH, {"errors": {}, "meta": {}})
    if "errors" not in lib:
        lib["errors"] = {}
    if "meta" not in lib:
        lib["meta"] = {}
    return lib


def update_error_library(library, errors, known_fixes):
    """Update the error library with new error occurrences."""
    now = _ts_now()
    updated_count = 0

    for err in errors:
        node = err.get("error_node") or err.get("node_name") or "Unknown"
        error_msg = err.get("error_message") or err.get("error") or ""
        error_type = _classify_error_type(error_msg)
        timestamp = err.get("timestamp") or err.get("created_at") or now

        if node not in library["errors"]:
            library["errors"][node] = {
                "count": 0,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "types": {},
                "fix_documented": False,
                "fix": None,
                "recent_messages": [],
            }
            updated_count += 1

        entry = library["errors"][node]
        entry["count"] += 1
        entry["last_seen"] = timestamp

        # Track first_seen
        if timestamp < entry.get("first_seen", timestamp):
            entry["first_seen"] = timestamp

        # Count by type
        entry["types"][error_type] = entry["types"].get(error_type, 0) + 1

        # Keep last 5 unique error messages
        msg_short = _truncate(error_msg, 200)
        if msg_short and msg_short not in entry.get("recent_messages", []):
            msgs = entry.get("recent_messages", [])
            msgs.append(msg_short)
            entry["recent_messages"] = msgs[-5:]

        # Try to find matching fix from DEBUG-PLAYBOOK
        fix_id, fix_title = find_matching_fix(error_msg, known_fixes)
        if fix_id:
            entry["fix_documented"] = True
            entry["fix"] = f"{fix_id}: {fix_title}"

    library["meta"]["last_updated"] = now
    library["meta"]["total_error_nodes"] = len(library["errors"])
    library["meta"]["total_occurrences"] = sum(
        e["count"] for e in library["errors"].values()
    )

    return updated_count


def print_error_library(library):
    """Print the error library in a human-readable format."""
    errors = library.get("errors", {})
    meta = library.get("meta", {})

    print("\n" + "=" * 70)
    print("  ERROR LIBRARY")
    print("=" * 70)
    print(f"  Last updated: {meta.get('last_updated', 'N/A')}")
    print(f"  Total error nodes: {meta.get('total_error_nodes', 0)}")
    print(f"  Total occurrences: {meta.get('total_occurrences', 0)}")
    print("-" * 70)

    if not errors:
        print("  (empty — no errors recorded yet)")
        return

    # Sort by count descending
    sorted_errors = sorted(errors.items(), key=lambda x: x[1]["count"], reverse=True)

    for node, data in sorted_errors[:30]:
        fix_str = f"  FIX: {data['fix']}" if data.get("fix") else "  NO FIX DOCUMENTED"
        types_str = ", ".join(
            f"{t}({c})" for t, c in sorted(data["types"].items(), key=lambda x: -x[1])
        )
        last_seen_dt = _parse_iso(data.get("last_seen"))
        last_seen_str = _ts_paris_full(last_seen_dt) if last_seen_dt else data.get("last_seen", "N/A")

        print(f"\n  [{data['count']:>4}x] {node}")
        print(f"         Types: {types_str}")
        print(f"         Last: {last_seen_str}")
        print(f"        {fix_str}")

    print("\n" + "-" * 70)


# ── Core analysis ───────────────────────────────────────────────

def analyze_errors(errors, pipeline_filter=None):
    """Analyze errors: group by workflow, node, type. Return structured analysis."""
    if pipeline_filter:
        pf = pipeline_filter.lower()
        errors = [
            e for e in errors
            if pf in (e.get("workflow_name") or "").lower()
            or pf in (e.get("pipeline") or "").lower()
            or pf == _resolve_pipeline(
                e.get("workflow_id", ""),
                e.get("workflow_name", "")
            )
        ]

    if not errors:
        return {
            "total_errors": 0,
            "by_workflow": {},
            "by_node": {},
            "by_type": {},
            "timeline": [],
            "top_errors": [],
        }

    # Group by workflow
    by_workflow = defaultdict(lambda: {"count": 0, "nodes": set(), "types": set()})
    for e in errors:
        wf = e.get("workflow_name") or e.get("pipeline") or "unknown"
        by_workflow[wf]["count"] += 1
        node = e.get("error_node") or e.get("node_name") or "Unknown"
        by_workflow[wf]["nodes"].add(node)
        etype = _classify_error_type(e.get("error_message") or e.get("error") or "")
        by_workflow[wf]["types"].add(etype)

    # Convert sets to lists for JSON
    by_workflow_out = {}
    for wf, data in by_workflow.items():
        by_workflow_out[wf] = {
            "count": data["count"],
            "nodes": sorted(data["nodes"]),
            "types": sorted(data["types"]),
        }

    # Group by node
    by_node = defaultdict(lambda: {
        "count": 0, "types": defaultdict(int),
        "last_error": None, "last_message": None
    })
    for e in errors:
        node = e.get("error_node") or e.get("node_name") or "Unknown"
        by_node[node]["count"] += 1
        etype = _classify_error_type(e.get("error_message") or e.get("error") or "")
        by_node[node]["types"][etype] += 1
        ts = e.get("timestamp") or e.get("created_at")
        if ts:
            if not by_node[node]["last_error"] or ts > by_node[node]["last_error"]:
                by_node[node]["last_error"] = ts
                by_node[node]["last_message"] = _truncate(
                    e.get("error_message") or e.get("error") or "", 200
                )

    by_node_out = {}
    for node, data in by_node.items():
        top_type = max(data["types"].items(), key=lambda x: x[1])[0] if data["types"] else "UNKNOWN"
        by_node_out[node] = {
            "count": data["count"],
            "types": dict(data["types"]),
            "top_type": top_type,
            "last_error": data["last_error"],
            "last_message": data["last_message"],
        }

    # Group by type
    by_type = defaultdict(int)
    for e in errors:
        etype = _classify_error_type(e.get("error_message") or e.get("error") or "")
        by_type[etype] += 1

    # Timeline (last 20 errors with Paris timestamps)
    timeline = []
    for e in errors[:20]:
        ts = _parse_iso(e.get("timestamp") or e.get("created_at"))
        timeline.append({
            "time_paris": _ts_paris(ts),
            "time_full": _ts_paris_full(ts),
            "node": e.get("error_node") or e.get("node_name") or "Unknown",
            "type": _classify_error_type(e.get("error_message") or e.get("error") or ""),
            "message": _truncate(e.get("error_message") or e.get("error") or "", 100),
            "workflow": e.get("workflow_name") or "unknown",
        })

    # Top errors (most frequent node+type combos)
    combo_counts = defaultdict(int)
    combo_msgs = {}
    for e in errors:
        node = e.get("error_node") or e.get("node_name") or "Unknown"
        etype = _classify_error_type(e.get("error_message") or e.get("error") or "")
        key = f"{node}|{etype}"
        combo_counts[key] += 1
        if key not in combo_msgs:
            combo_msgs[key] = _truncate(e.get("error_message") or e.get("error") or "", 150)

    top_errors = []
    for key, count in sorted(combo_counts.items(), key=lambda x: -x[1])[:15]:
        node, etype = key.split("|", 1)
        top_errors.append({
            "node": node,
            "type": etype,
            "count": count,
            "sample_message": combo_msgs.get(key, ""),
        })

    return {
        "total_errors": len(errors),
        "period_start": errors[-1].get("timestamp") if errors else None,
        "period_end": errors[0].get("timestamp") if errors else None,
        "by_workflow": by_workflow_out,
        "by_node": by_node_out,
        "by_type": dict(by_type),
        "timeline": timeline,
        "top_errors": top_errors,
    }


# ── n8n execution metrics ──────────────────────────────────────

def collect_n8n_metrics(pipeline_filter=None):
    """Collect per-node timing and throughput from n8n execution APIs."""
    all_executions = []

    for label, url in SPACES.items():
        print(f"  [{label}] Connecting to {url}...", flush=True)
        client = N8nClient(label, url)
        if not client.login():
            print(f"  [{label}] Skipped (login failed)", flush=True)
            continue

        # Fetch executions for each known workflow
        workflow_ids = list(WORKFLOW_MAP.keys())
        if pipeline_filter:
            workflow_ids = [
                wid for wid, pname in WORKFLOW_MAP.items()
                if pname == pipeline_filter.lower()
            ]

        for wf_id in workflow_ids:
            execs = client.fetch_executions(workflow_id=wf_id, limit=10)
            for raw in execs:
                parsed = _parse_n8n_execution(raw, label)
                if parsed:
                    all_executions.append(parsed)

        print(f"  [{label}] Got {len(all_executions)} executions total", flush=True)

    if not all_executions:
        return {
            "total_executions": 0,
            "pipelines": {},
            "node_metrics": {},
            "best_executions": [],
            "worst_executions": [],
        }

    # Group by pipeline
    by_pipeline = defaultdict(list)
    for ex in all_executions:
        by_pipeline[ex["pipeline"]].append(ex)

    pipeline_metrics = {}
    all_node_metrics = defaultdict(lambda: {
        "total_runs": 0, "total_time_ms": 0, "error_count": 0,
        "min_time_ms": float("inf"), "max_time_ms": 0,
        "items_processed": 0,
    })

    for pipeline, execs in by_pipeline.items():
        durations = [e["duration_ms"] for e in execs if e["duration_ms"] > 0]
        error_execs = [e for e in execs if e["status"] == "error"]
        success_execs = [e for e in execs if e["status"] == "success"]

        pipeline_metrics[pipeline] = {
            "total_executions": len(execs),
            "success": len(success_execs),
            "errors": len(error_execs),
            "error_rate": round(len(error_execs) / max(len(execs), 1) * 100, 1),
            "avg_duration_ms": int(sum(durations) / max(len(durations), 1)),
            "min_duration_ms": min(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
        }

        # Node-level aggregation
        for ex in execs:
            for node in ex.get("nodes", []):
                nm = node["name"]
                m = all_node_metrics[nm]
                m["total_runs"] += 1
                m["total_time_ms"] += node["execution_time_ms"]
                if node["status"] == "error":
                    m["error_count"] += 1
                if node["execution_time_ms"] < m["min_time_ms"]:
                    m["min_time_ms"] = node["execution_time_ms"]
                if node["execution_time_ms"] > m["max_time_ms"]:
                    m["max_time_ms"] = node["execution_time_ms"]
                m["items_processed"] += node.get("items_out", 0)

    # Finalize node metrics
    node_metrics_out = {}
    for nm, m in all_node_metrics.items():
        if m["min_time_ms"] == float("inf"):
            m["min_time_ms"] = 0
        node_metrics_out[nm] = {
            "total_runs": m["total_runs"],
            "avg_time_ms": int(m["total_time_ms"] / max(m["total_runs"], 1)),
            "min_time_ms": m["min_time_ms"],
            "max_time_ms": m["max_time_ms"],
            "error_count": m["error_count"],
            "error_rate": round(m["error_count"] / max(m["total_runs"], 1) * 100, 1),
            "items_processed": m["items_processed"],
        }

    # Best and worst executions
    sorted_by_duration = sorted(
        [e for e in all_executions if e["duration_ms"] > 0],
        key=lambda x: x["duration_ms"]
    )

    best_3 = []
    for e in sorted_by_duration[:3]:
        best_3.append({
            "id": e["id"],
            "pipeline": e["pipeline"],
            "space": e["space"],
            "duration_ms": e["duration_ms"],
            "status": e["status"],
            "node_count": e["node_count"],
        })

    worst_3 = []
    for e in sorted_by_duration[-3:]:
        worst_3.append({
            "id": e["id"],
            "pipeline": e["pipeline"],
            "space": e["space"],
            "duration_ms": e["duration_ms"],
            "status": e["status"],
            "node_count": e["node_count"],
            "error_nodes": [
                n["name"] for n in e.get("nodes", []) if n["status"] == "error"
            ],
        })

    return {
        "total_executions": len(all_executions),
        "pipelines": pipeline_metrics,
        "node_metrics": node_metrics_out,
        "best_executions": best_3,
        "worst_executions": list(reversed(worst_3)),
    }


def _parse_n8n_execution(raw, space_label):
    """Parse a raw n8n execution dict."""
    exec_id = str(raw.get("id", ""))
    if not exec_id:
        return None

    wf_data = raw.get("workflowData", {}) or {}
    wf_id = str(wf_data.get("id", raw.get("workflowId", "")))
    wf_name = wf_data.get("name", WORKFLOW_MAP.get(wf_id, "unknown"))
    pipeline = _resolve_pipeline(wf_id, wf_name)

    started = raw.get("startedAt", "")
    stopped = raw.get("stoppedAt", "")
    status = raw.get("status", "unknown")

    duration_ms = 0
    dt_start = _parse_iso(started)
    dt_stop = _parse_iso(stopped)
    if dt_start and dt_stop:
        duration_ms = int((dt_stop - dt_start).total_seconds() * 1000)

    # Node data
    run_data = {}
    result_data = raw.get("data", {})
    if isinstance(result_data, dict):
        run_data = result_data.get("resultData", {}).get("runData", {})

    nodes = []
    error_node = None
    for node_name, runs in run_data.items():
        if not isinstance(runs, list):
            continue
        for run in runs:
            node = _parse_node_run(node_name, run)
            nodes.append(node)
            if node["status"] == "error" and not error_node:
                error_node = node_name

    return {
        "id": exec_id,
        "space": space_label,
        "workflow_id": wf_id,
        "pipeline": pipeline,
        "status": status,
        "started_at": started,
        "stopped_at": stopped,
        "duration_ms": duration_ms,
        "node_count": len(nodes),
        "nodes": nodes,
        "error_node": error_node,
    }


def _parse_node_run(name, run):
    """Extract performance data for a single node run."""
    exec_time = run.get("executionTime", 0) or 0
    start_time = run.get("startTime", "")

    error_msg = None
    if run.get("error"):
        err = run["error"]
        if isinstance(err, dict):
            error_msg = err.get("message", str(err))[:500]
        else:
            error_msg = str(err)[:500]

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


# ── Report generation ───────────────────────────────────────────

def generate_report(analysis, n8n_metrics, library):
    """Generate full JSON report."""
    report = {
        "generated_at": _ts_now(),
        "generated_at_paris": _ts_paris_full(datetime.now(timezone.utc)),
        "error_analysis": analysis,
        "n8n_metrics": n8n_metrics,
        "error_library_summary": {
            "total_nodes": len(library.get("errors", {})),
            "total_occurrences": sum(
                e["count"] for e in library.get("errors", {}).values()
            ),
            "top_5": sorted(
                [
                    {"node": k, "count": v["count"], "top_type": max(
                        v["types"].items(), key=lambda x: x[1]
                    )[0] if v["types"] else "UNKNOWN"}
                    for k, v in library.get("errors", {}).items()
                ],
                key=lambda x: -x["count"]
            )[:5],
        },
    }
    return report


def update_health_status(analysis, n8n_metrics):
    """Update data/health-status.json with latest error counts."""
    health = _load_json(HEALTH_STATUS_PATH, {})

    health["error_analysis"] = {
        "last_run": _ts_now(),
        "total_errors": analysis.get("total_errors", 0),
        "errors_by_type": analysis.get("by_type", {}),
        "top_error_node": (
            analysis["top_errors"][0]["node"]
            if analysis.get("top_errors") else None
        ),
        "error_pipelines": {
            wf: data["count"]
            for wf, data in analysis.get("by_workflow", {}).items()
        },
    }

    if n8n_metrics and n8n_metrics.get("total_executions", 0) > 0:
        health["n8n_execution_metrics"] = {
            "last_run": _ts_now(),
            "total_executions": n8n_metrics["total_executions"],
            "pipeline_error_rates": {
                p: data.get("error_rate", 0)
                for p, data in n8n_metrics.get("pipelines", {}).items()
            },
        }

    _save_json(HEALTH_STATUS_PATH, health)


# ── CLI output ──────────────────────────────────────────────────

def print_summary(analysis, n8n_metrics, period_label):
    """Print human-readable summary to CLI."""
    print("\n" + "=" * 70)
    print(f"  PIPELINE ERROR ANALYSIS — {period_label}")
    print(f"  Generated: {_ts_paris_full(datetime.now(timezone.utc))}")
    print("=" * 70)

    total = analysis.get("total_errors", 0)
    print(f"\n  Total errors: {total}")

    if total == 0:
        print("  No errors found in this period.")
        _print_n8n_metrics(n8n_metrics)
        return

    # Errors by workflow
    print("\n  --- Errors by Workflow ---")
    by_wf = analysis.get("by_workflow", {})
    for wf, data in sorted(by_wf.items(), key=lambda x: -x[1]["count"]):
        print(f"    {wf:30s}  {data['count']:>4} errors  "
              f"nodes=[{', '.join(data['nodes'][:5])}]")

    # Errors by type
    print("\n  --- Errors by Type ---")
    by_type = analysis.get("by_type", {})
    for etype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        bar = "#" * min(count, 40)
        print(f"    {etype:20s}  {count:>4}  {bar}")

    # Top errors
    print("\n  --- Top Errors (node + type) ---")
    for i, err in enumerate(analysis.get("top_errors", [])[:10], 1):
        print(f"    {i:>2}. [{err['count']:>3}x] {err['node']} — {err['type']}")
        if err.get("sample_message"):
            print(f"        {_truncate(err['sample_message'], 80)}")

    # Node-by-node breakdown
    print("\n  --- Node-by-Node Error Report ---")
    by_node = analysis.get("by_node", {})
    sorted_nodes = sorted(by_node.items(), key=lambda x: -x[1]["count"])
    for node, data in sorted_nodes[:15]:
        last_dt = _parse_iso(data.get("last_error"))
        last_str = _ts_paris(last_dt) if last_dt else "N/A"
        print(f"    {node:40s}  {data['count']:>3}x  "
              f"top={data['top_type']:15s}  last={last_str}")

    # Timeline
    print("\n  --- Recent Error Timeline (Paris TZ) ---")
    for entry in analysis.get("timeline", [])[:10]:
        print(f"    {entry['time_paris']}  {entry['node']:30s}  "
              f"{entry['type']:15s}  {_truncate(entry['message'], 50)}")

    _print_n8n_metrics(n8n_metrics)


def _print_n8n_metrics(n8n_metrics):
    """Print n8n execution metrics section."""
    if not n8n_metrics or n8n_metrics.get("total_executions", 0) == 0:
        print("\n  --- n8n Execution Metrics ---")
        print("    (no data collected)")
        return

    print("\n  --- n8n Execution Metrics ---")
    print(f"  Total executions analyzed: {n8n_metrics['total_executions']}")

    # Pipeline summary
    print("\n  Pipeline Performance:")
    for pipeline, data in sorted(n8n_metrics.get("pipelines", {}).items()):
        err_pct = data.get("error_rate", 0)
        status_icon = "OK" if err_pct < 10 else "WARN" if err_pct < 30 else "CRIT"
        print(f"    [{status_icon:>4}] {pipeline:20s}  "
              f"runs={data['total_executions']:>3}  "
              f"err={err_pct:>5.1f}%  "
              f"avg={data['avg_duration_ms']:>6}ms  "
              f"max={data['max_duration_ms']:>6}ms")

    # Top 3 slowest nodes
    node_metrics = n8n_metrics.get("node_metrics", {})
    if node_metrics:
        sorted_nodes = sorted(
            node_metrics.items(), key=lambda x: -x[1]["avg_time_ms"]
        )
        print("\n  Slowest Nodes (avg):")
        for name, data in sorted_nodes[:5]:
            print(f"    {name:40s}  avg={data['avg_time_ms']:>6}ms  "
                  f"max={data['max_time_ms']:>6}ms  "
                  f"err={data['error_rate']:>5.1f}%  "
                  f"runs={data['total_runs']:>3}")

        # Highest error rate nodes
        error_nodes = sorted(
            [(n, d) for n, d in node_metrics.items() if d["error_count"] > 0],
            key=lambda x: -x[1]["error_rate"]
        )
        if error_nodes:
            print("\n  Highest Error Rate Nodes:")
            for name, data in error_nodes[:5]:
                print(f"    {name:40s}  err={data['error_rate']:>5.1f}%  "
                      f"({data['error_count']}/{data['total_runs']})")

    # Best/worst executions
    if n8n_metrics.get("best_executions"):
        print("\n  Top 3 Fastest Executions:")
        for ex in n8n_metrics["best_executions"]:
            print(f"    {ex['pipeline']:20s}  {ex['duration_ms']:>6}ms  "
                  f"[{ex['space']}]  nodes={ex['node_count']}")

    if n8n_metrics.get("worst_executions"):
        print("\n  Top 3 Slowest Executions:")
        for ex in n8n_metrics["worst_executions"]:
            err_str = ""
            if ex.get("error_nodes"):
                err_str = f"  errors=[{', '.join(ex['error_nodes'][:3])}]"
            print(f"    {ex['pipeline']:20s}  {ex['duration_ms']:>6}ms  "
                  f"[{ex['space']}]  nodes={ex['node_count']}{err_str}")

    print()


# ── Main execution ──────────────────────────────────────────────

def run_analysis(period="24h", pipeline_filter=None, skip_n8n=False):
    """Run a full error analysis cycle."""
    period_label = f"Last {period}"
    delta = PERIOD_MAP.get(period, timedelta(hours=24))
    since_dt = datetime.now(timezone.utc) - delta

    print(f"\n  Starting error analysis ({period_label})...", flush=True)
    print(f"  Since: {_ts_paris_full(since_dt)}", flush=True)

    # 1. Parse known fixes from DEBUG-PLAYBOOK.md
    print("  Parsing DEBUG-PLAYBOOK.md for known fixes...", flush=True)
    known_fixes = parse_debug_playbook()
    print(f"  Found {len(known_fixes)} documented fixes", flush=True)

    # 2. Query Supabase for pipeline errors
    print("  Querying Supabase pipeline_errors...", flush=True)
    sb = SupabaseClient()
    errors = sb.fetch_errors(since_dt=since_dt, limit=500)
    print(f"  Got {len(errors)} errors from Supabase", flush=True)

    # 3. Analyze errors
    print("  Analyzing error patterns...", flush=True)
    analysis = analyze_errors(errors, pipeline_filter=pipeline_filter)

    # 4. Collect n8n execution metrics
    n8n_metrics = {}
    if not skip_n8n:
        print("  Collecting n8n execution metrics...", flush=True)
        n8n_metrics = collect_n8n_metrics(pipeline_filter=pipeline_filter)
    else:
        print("  Skipping n8n metrics (--no-n8n)", flush=True)

    # 5. Update error library
    print("  Updating error library...", flush=True)
    library = load_error_library()
    new_entries = update_error_library(library, errors, known_fixes)
    _save_json(ERROR_LIBRARY_PATH, library)
    print(f"  Error library updated ({new_entries} new nodes, "
          f"{len(library['errors'])} total)", flush=True)

    # 6. Generate report
    report = generate_report(analysis, n8n_metrics, library)
    _save_json(ERROR_REPORT_PATH, report)
    print(f"  Report saved to {ERROR_REPORT_PATH}", flush=True)

    # 7. Update health status
    update_health_status(analysis, n8n_metrics)
    print(f"  Health status updated at {HEALTH_STATUS_PATH}", flush=True)

    # 8. Print CLI summary
    print_summary(analysis, n8n_metrics, period_label)

    return analysis, n8n_metrics, library


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Error Analyzer — Automated error analysis system"
    )
    parser.add_argument(
        "--period", default="24h",
        choices=list(PERIOD_MAP.keys()),
        help="Time period to analyze (default: 24h)"
    )
    parser.add_argument(
        "--pipeline", default=None,
        help="Filter to specific pipeline (standard, graph, quant, orchestrator)"
    )
    parser.add_argument(
        "--library", action="store_true",
        help="Show error library and exit"
    )
    parser.add_argument(
        "--loop", type=int, default=0, metavar="SECONDS",
        help="Run continuously with given interval in seconds"
    )
    parser.add_argument(
        "--no-n8n", action="store_true",
        help="Skip n8n execution API queries (Supabase only)"
    )
    args = parser.parse_args()

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Library-only mode
    if args.library:
        library = load_error_library()
        print_error_library(library)
        return

    # Single run or loop
    if args.loop > 0:
        print(f"\n  Continuous mode: running every {args.loop}s (Ctrl+C to stop)")
        cycle = 0
        while True:
            cycle += 1
            print(f"\n{'#' * 70}")
            print(f"  Cycle {cycle} — {_ts_paris_full(datetime.now(timezone.utc))}")
            print(f"{'#' * 70}")
            try:
                run_analysis(
                    period=args.period,
                    pipeline_filter=args.pipeline,
                    skip_n8n=args.no_n8n,
                )
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\n  ERROR in cycle {cycle}: {e}", flush=True)
            print(f"\n  Sleeping {args.loop}s until next cycle...", flush=True)
            try:
                time.sleep(args.loop)
            except KeyboardInterrupt:
                print("\n  Stopped by user.")
                break
    else:
        try:
            run_analysis(
                period=args.period,
                pipeline_filter=args.pipeline,
                skip_n8n=args.no_n8n,
            )
        except KeyboardInterrupt:
            print("\n  Interrupted.")
            sys.exit(1)


if __name__ == "__main__":
    main()
