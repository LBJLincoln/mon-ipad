#!/usr/bin/env python3
"""
Webhook Health Monitor — Multi-RAG Orchestrator

Checks health of all RAG pipeline webhooks and reports status as JSON.
Uses Python urllib.request (NOT curl, NOT requests) per project convention.

Usage:
    source .env.local && python3 scripts/webhook-health-monitor.py --once
    source .env.local && python3 scripts/webhook-health-monitor.py --daemon
    source .env.local && python3 scripts/webhook-health-monitor.py --daemon --interval 120

Daemon mode:
    nohup python3 scripts/webhook-health-monitor.py --daemon > logs/webhook-health.log 2>&1 &
"""

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib import request, error

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
HEALTH_LOG = os.path.join(LOGS_DIR, "webhook-health.jsonl")
STATUS_JSON = os.path.join(REPO_ROOT, "docs", "status.json")

os.makedirs(LOGS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Load .env.local
# ---------------------------------------------------------------------------
def load_env():
    """Load environment variables from .env.local."""
    env_file = os.path.join(REPO_ROOT, ".env.local")
    if not os.path.exists(env_file):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                if "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip()
                    if val and val[0] in ('"', "'") and val[-1] == val[0]:
                        val = val[1:-1]
                    if "${" not in val:
                        os.environ.setdefault(key, val)


load_env()

# ---------------------------------------------------------------------------
# Webhook definitions (from agentic-automation-spec.md Section 1.3)
# ---------------------------------------------------------------------------
WEBHOOKS: Dict[str, dict] = {
    "standard": {
        "path": "/webhook/rag-multi-index-v3",
        "expected_latency_s": 3,
        "timeout_s": 90,
        "field": "query",
        "test_query": "What is the capital of Japan?",
    },
    "graph": {
        "path": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "expected_latency_s": 5,
        "timeout_s": 90,
        "field": "query",
        "test_query": "What did Marie Curie win Nobel Prizes for?",
    },
    "quantitative": {
        "path": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "expected_latency_s": 8,
        "timeout_s": 120,
        "field": "query",
        "test_query": "What was TechVision Inc's total revenue in 2023?",
    },
    "orchestrator": {
        "path": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
        "expected_latency_s": 10,
        "timeout_s": 180,
        "field": "query",
        "test_query": "What is the largest ocean?",
    },
    "nomos42": {
        "path": "/webhook/project-chatbot",
        "expected_latency_s": 3,
        "timeout_s": 60,
        "field": "question",
        "test_query": "What is this project about?",
    },
}

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
SHUTDOWN = False


def handle_signal(signum, frame):
    global SHUTDOWN
    print(f"\n[{_now()}] Signal {signum} received -- shutting down")
    SHUTDOWN = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Health check logic
# ---------------------------------------------------------------------------
def check_webhook(n8n_host: str, pipeline: str, config: dict) -> dict:
    """Send a health query to a single webhook and return result dict.

    Uses urllib.request per project convention (HF Space proxy issues with curl).

    Returns:
        {
            "pipeline": str,
            "url": str,
            "status": "healthy" | "degraded" | "down" | "timeout",
            "http_code": int | None,
            "latency_ms": int,
            "expected_latency_ms": int,
            "answer_length": int,
            "error": str | None,
            "checked_at": str,
        }
    """
    url = n8n_host.rstrip("/") + config["path"]
    timeout = config["timeout_s"]
    payload = json.dumps({
        config["field"]: config["test_query"],
        "sessionId": f"health-monitor-{int(time.time())}",
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    result = {
        "pipeline": pipeline,
        "url": url,
        "status": "down",
        "http_code": None,
        "latency_ms": 0,
        "expected_latency_ms": config["expected_latency_s"] * 1000,
        "answer_length": 0,
        "error": None,
        "checked_at": _now(),
    }

    try:
        req = request.Request(url, data=payload, headers=headers, method="POST")
        start = time.time()
        with request.urlopen(req, timeout=timeout) as resp:
            latency_ms = int((time.time() - start) * 1000)
            result["http_code"] = resp.status
            result["latency_ms"] = latency_ms
            raw = resp.read().decode("utf-8")

            if not raw or not raw.strip():
                result["status"] = "degraded"
                result["error"] = "Empty response body"
                return result

            # Parse response
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    data = data[0] if data else {}
            except json.JSONDecodeError:
                data = {}

            # Extract answer from known keys
            answer = ""
            for key in ["response", "answer", "result", "interpretation", "final_response"]:
                if key in data and data[key]:
                    answer = str(data[key])
                    break

            result["answer_length"] = len(answer)

            if not answer or len(answer) < 5:
                result["status"] = "degraded"
                result["error"] = "Empty or very short answer"
            elif latency_ms > config["expected_latency_s"] * 1000 * 3:
                # More than 3x expected = degraded
                result["status"] = "degraded"
                result["error"] = f"Slow: {latency_ms}ms (expected <{config['expected_latency_s'] * 1000}ms)"
            else:
                result["status"] = "healthy"

    except error.HTTPError as e:
        result["http_code"] = e.code
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        result["error"] = f"HTTP {e.code}: {err_body}"

        if e.code == 404:
            result["status"] = "down"
            result["error"] = "Webhook not registered (404)"
        elif e.code == 429:
            result["status"] = "degraded"
            result["error"] = "Rate limited (429)"
        elif e.code >= 500:
            result["status"] = "down"
        else:
            result["status"] = "degraded"

    except Exception as e:
        err_str = str(e)
        if "timed out" in err_str.lower() or "timeout" in err_str.lower():
            result["status"] = "timeout"
            result["latency_ms"] = timeout * 1000
            result["error"] = f"Timeout after {timeout}s"
        else:
            result["status"] = "down"
            result["error"] = err_str[:200]

    return result


def run_health_check() -> dict:
    """Run health checks on all webhooks.

    Returns a full report dict.
    """
    n8n_host = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
    print(f"[{_now()}] Webhook health check starting (host: {n8n_host})")

    results: List[dict] = []
    for pipeline, config in WEBHOOKS.items():
        print(f"  Checking {pipeline}...", end=" ", flush=True)
        result = check_webhook(n8n_host, pipeline, config)
        results.append(result)

        # Print status with color
        status = result["status"]
        if status == "healthy":
            color = C.GREEN
        elif status == "degraded":
            color = C.YELLOW
        else:
            color = C.RED
        latency = result["latency_ms"]
        print(f"{color}{status}{C.END} ({latency}ms, {result['answer_length']} chars)")

        if result["error"]:
            print(f"    error: {result['error'][:120]}")

        # Small delay between checks to avoid hammering
        time.sleep(1)

    # Build summary
    healthy = sum(1 for r in results if r["status"] == "healthy")
    degraded = sum(1 for r in results if r["status"] == "degraded")
    down = sum(1 for r in results if r["status"] in ("down", "timeout"))
    total = len(results)

    overall = "healthy"
    if down > 0:
        overall = "critical" if down > total // 2 else "degraded"
    elif degraded > 0:
        overall = "degraded"

    report = {
        "timestamp": _now(),
        "n8n_host": n8n_host,
        "overall_status": overall,
        "summary": {
            "total": total,
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
        },
        "pipelines": {r["pipeline"]: r for r in results},
    }

    # Print summary
    print(f"\n  Overall: {C.BOLD}{overall.upper()}{C.END} "
          f"({healthy}/{total} healthy, {degraded} degraded, {down} down)")

    return report


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log_report(report: dict):
    """Append report to JSONL log file."""
    try:
        with open(HEALTH_LOG, "a") as f:
            f.write(json.dumps(report) + "\n")
    except (OSError, IOError) as e:
        print(f"  {C.YELLOW}WARN{C.END} Cannot write health log: {e}")


def print_json_report(report: dict):
    """Print the full report as formatted JSON to stdout."""
    print(json.dumps(report, indent=2))


# ---------------------------------------------------------------------------
# Daemon loop
# ---------------------------------------------------------------------------
def run_daemon(interval: int = 60):
    """Run continuous health monitoring.

    Args:
        interval: Seconds between check cycles (default 60).
    """
    print(f"[{_now()}] Webhook Health Monitor daemon started (PID {os.getpid()})")
    print(f"  Interval: {interval}s")
    print(f"  Health log: {HEALTH_LOG}")

    consecutive_failures = 0

    while not SHUTDOWN:
        try:
            report = run_health_check()
            log_report(report)

            # Track consecutive critical states for escalation
            if report["overall_status"] == "critical":
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    print(f"\n  {C.RED}ALERT: {consecutive_failures} consecutive critical states!{C.END}")
                    print(f"  Consider running: python3 scripts/auto-revert.py --pipeline all")
            else:
                consecutive_failures = 0

        except Exception as e:
            print(f"[{_now()}] ERROR in health check: {e}")

        # Sleep in 1-second increments for responsive shutdown
        for _ in range(interval):
            if SHUTDOWN:
                break
            time.sleep(1)

    print(f"[{_now()}] Webhook Health Monitor daemon stopped")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Webhook Health Monitor -- Multi-RAG Orchestrator"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--daemon", action="store_true",
        help="Run in continuous monitoring mode"
    )
    mode.add_argument(
        "--once", action="store_true",
        help="Run a single health check and exit"
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Check interval in seconds for daemon mode (default: 60)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output full report as JSON (for --once mode)"
    )

    args = parser.parse_args()

    if args.once:
        report = run_health_check()
        log_report(report)
        if args.json:
            print_json_report(report)
        # Exit code: 0 = all healthy, 1 = any down, 2 = all down
        down = report["summary"]["down"]
        total = report["summary"]["total"]
        if down == 0:
            sys.exit(0)
        elif down == total:
            sys.exit(2)
        else:
            sys.exit(1)
    elif args.daemon:
        run_daemon(interval=args.interval)


if __name__ == "__main__":
    main()
