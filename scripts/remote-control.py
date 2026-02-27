#!/usr/bin/env python3
"""
Remote Control Server — HTTP endpoint for pipeline management on VM.

Provides RESTful endpoints to manage RAG pipelines remotely:
- GET /status — health check for all 4 pipelines
- POST /fix/<pipeline> — launch auto-remediate.py for a pipeline
- POST /revert/<pipeline> — launch auto-revert.py for a pipeline
- POST /test/<pipeline>/<n> — launch quick-test.py with n questions
- GET /jobs — list all background jobs
- GET /jobs/<id> — get specific job status and output

Usage:
    python3 scripts/remote-control.py                    # Start on port 8081
    python3 scripts/remote-control.py --port 8082        # Custom port

Authentication:
    All requests require header: X-Auth-Key: <key>
    Key is loaded from REMOTE_CONTROL_KEY in .env.local
    If not set, a random key is generated and printed on startup.
"""

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Lock
from typing import Dict, Optional
from urllib import request, error

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
EVAL_DIR = os.path.join(REPO_ROOT, "eval")
CONTROL_LOG = os.path.join(LOGS_DIR, "remote-control.jsonl")

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
# Authentication
# ---------------------------------------------------------------------------
AUTH_KEY = os.environ.get("REMOTE_CONTROL_KEY", "")
if not AUTH_KEY:
    AUTH_KEY = secrets.token_urlsafe(32)
    print(f"[WARN] REMOTE_CONTROL_KEY not set in .env.local. Generated random key:")
    print(f"       {AUTH_KEY}")
    print(f"       Add to .env.local: export REMOTE_CONTROL_KEY={AUTH_KEY}")

# ---------------------------------------------------------------------------
# Webhook definitions (from webhook-health-monitor.py)
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
}

PIPELINES = list(WEBHOOKS.keys())

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
JOBS: Dict[str, dict] = {}
JOBS_LOCK = Lock()
JOB_COUNTER = 0
SHUTDOWN = False


def handle_signal(signum, frame):
    global SHUTDOWN
    print(f"\n[{_now()}] Signal {signum} received -- shutting down")
    SHUTDOWN = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_event(event_type: str, data: dict):
    """Append event to JSONL log."""
    try:
        with open(CONTROL_LOG, "a") as f:
            log_entry = {
                "timestamp": _now(),
                "event": event_type,
                **data,
            }
            f.write(json.dumps(log_entry) + "\n")
    except (OSError, IOError) as e:
        print(f"[WARN] Cannot write control log: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Health check logic (from webhook-health-monitor.py)
# ---------------------------------------------------------------------------
def check_webhook(n8n_host: str, pipeline: str, config: dict) -> dict:
    """Send a health query to a single webhook and return result dict."""
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


def get_all_pipeline_status() -> dict:
    """Run health checks on all webhooks."""
    n8n_host = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
    results = {}

    for pipeline, config in WEBHOOKS.items():
        result = check_webhook(n8n_host, pipeline, config)
        results[pipeline] = result
        time.sleep(0.5)  # Small delay between checks

    # Build summary
    healthy = sum(1 for r in results.values() if r["status"] == "healthy")
    degraded = sum(1 for r in results.values() if r["status"] == "degraded")
    down = sum(1 for r in results.values() if r["status"] in ("down", "timeout"))
    total = len(results)

    overall = "healthy"
    if down > 0:
        overall = "critical" if down > total // 2 else "degraded"
    elif degraded > 0:
        overall = "degraded"

    return {
        "timestamp": _now(),
        "n8n_host": n8n_host,
        "overall_status": overall,
        "summary": {
            "total": total,
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
        },
        "pipelines": results,
    }


# ---------------------------------------------------------------------------
# Background job management
# ---------------------------------------------------------------------------
def create_job(job_type: str, pipeline: str, command: list) -> str:
    """Create and start a background job."""
    global JOB_COUNTER

    with JOBS_LOCK:
        JOB_COUNTER += 1
        job_id = f"{job_type}-{pipeline}-{JOB_COUNTER}"

        # Start subprocess
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=REPO_ROOT,
            )

            JOBS[job_id] = {
                "id": job_id,
                "type": job_type,
                "pipeline": pipeline,
                "command": " ".join(command),
                "status": "running",
                "process": process,
                "started_at": _now(),
                "finished_at": None,
                "stdout": "",
                "stderr": "",
                "exit_code": None,
            }

            _log_event("job_started", {
                "job_id": job_id,
                "type": job_type,
                "pipeline": pipeline,
                "command": " ".join(command),
            })

            return job_id

        except Exception as e:
            raise RuntimeError(f"Failed to start job: {e}")


def update_job_status(job_id: str):
    """Check and update job status."""
    with JOBS_LOCK:
        if job_id not in JOBS:
            return

        job = JOBS[job_id]
        if job["status"] != "running":
            return

        process = job["process"]
        poll_result = process.poll()

        if poll_result is not None:
            # Process finished
            try:
                stdout, stderr = process.communicate(timeout=1)
                job["stdout"] = stdout
                job["stderr"] = stderr
            except Exception:
                job["stdout"] = "(could not read)"
                job["stderr"] = "(could not read)"

            job["exit_code"] = poll_result
            job["status"] = "completed" if poll_result == 0 else "failed"
            job["finished_at"] = _now()

            _log_event("job_finished", {
                "job_id": job_id,
                "status": job["status"],
                "exit_code": poll_result,
            })


def get_job_info(job_id: str) -> Optional[dict]:
    """Get job info (without process object)."""
    update_job_status(job_id)

    with JOBS_LOCK:
        if job_id not in JOBS:
            return None

        job = JOBS[job_id].copy()
        job.pop("process", None)  # Remove process object
        return job


def get_all_jobs() -> list:
    """Get all jobs info."""
    # Update all running jobs
    with JOBS_LOCK:
        job_ids = list(JOBS.keys())

    for job_id in job_ids:
        update_job_status(job_id)

    with JOBS_LOCK:
        jobs = []
        for job in JOBS.values():
            job_copy = job.copy()
            job_copy.pop("process", None)  # Remove process object
            jobs.append(job_copy)

        return sorted(jobs, key=lambda x: x["started_at"], reverse=True)


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------
class RemoteControlHandler(BaseHTTPRequestHandler):
    """HTTP request handler for remote control endpoints."""

    def log_message(self, format, *args):
        """Override to log to stderr with timestamp."""
        sys.stderr.write(f"[{_now()}] {format % args}\n")

    def send_cors_headers(self):
        """Send CORS headers for browser access."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Key")

    def check_auth(self) -> bool:
        """Check X-Auth-Key header."""
        auth_header = self.headers.get("X-Auth-Key", "")
        return auth_header == AUTH_KEY

    def send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def send_error_json(self, status: int, message: str):
        """Send JSON error response."""
        self.send_json({
            "error": message,
            "status": status,
            "timestamp": _now(),
        }, status=status)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        if not self.check_auth():
            return self.send_error_json(401, "Unauthorized. Missing or invalid X-Auth-Key header.")

        # GET /status
        if self.path == "/status":
            try:
                status = get_all_pipeline_status()
                _log_event("status_check", {"overall": status["overall_status"]})
                return self.send_json(status)
            except Exception as e:
                return self.send_error_json(500, f"Failed to get status: {e}")

        # GET /jobs
        if self.path == "/jobs":
            try:
                jobs = get_all_jobs()
                return self.send_json({"jobs": jobs, "count": len(jobs)})
            except Exception as e:
                return self.send_error_json(500, f"Failed to get jobs: {e}")

        # GET /jobs/<id>
        if self.path.startswith("/jobs/"):
            job_id = self.path.split("/")[-1]
            try:
                job = get_job_info(job_id)
                if job is None:
                    return self.send_error_json(404, f"Job not found: {job_id}")
                return self.send_json(job)
            except Exception as e:
                return self.send_error_json(500, f"Failed to get job: {e}")

        # Unknown endpoint
        return self.send_error_json(404, f"Unknown endpoint: {self.path}")

    def do_POST(self):
        """Handle POST requests."""
        if not self.check_auth():
            return self.send_error_json(401, "Unauthorized. Missing or invalid X-Auth-Key header.")

        parts = self.path.strip("/").split("/")

        # POST /fix/<pipeline>
        if len(parts) == 2 and parts[0] == "fix":
            pipeline = parts[1]
            if pipeline not in PIPELINES:
                return self.send_error_json(400, f"Unknown pipeline: {pipeline}")

            try:
                script_path = os.path.join(SCRIPTS_DIR, "auto-remediate.py")
                if not os.path.exists(script_path):
                    return self.send_error_json(404, f"auto-remediate.py not found")

                command = ["python3", script_path, "--pipeline", pipeline]
                job_id = create_job("fix", pipeline, command)

                return self.send_json({
                    "job_id": job_id,
                    "message": f"Fix job started for {pipeline}",
                    "command": " ".join(command),
                }, status=202)
            except Exception as e:
                return self.send_error_json(500, f"Failed to start fix job: {e}")

        # POST /revert/<pipeline>
        if len(parts) == 2 and parts[0] == "revert":
            pipeline = parts[1]
            if pipeline not in PIPELINES:
                return self.send_error_json(400, f"Unknown pipeline: {pipeline}")

            try:
                script_path = os.path.join(SCRIPTS_DIR, "auto-revert.py")
                if not os.path.exists(script_path):
                    return self.send_error_json(404, f"auto-revert.py not found")

                command = ["python3", script_path, "--pipeline", pipeline]
                job_id = create_job("revert", pipeline, command)

                return self.send_json({
                    "job_id": job_id,
                    "message": f"Revert job started for {pipeline}",
                    "command": " ".join(command),
                }, status=202)
            except Exception as e:
                return self.send_error_json(500, f"Failed to start revert job: {e}")

        # POST /test/<pipeline>/<n>
        if len(parts) == 3 and parts[0] == "test":
            pipeline = parts[1]
            try:
                n_questions = int(parts[2])
            except ValueError:
                return self.send_error_json(400, f"Invalid number of questions: {parts[2]}")

            if pipeline not in PIPELINES:
                return self.send_error_json(400, f"Unknown pipeline: {pipeline}")

            if n_questions < 1 or n_questions > 100:
                return self.send_error_json(400, "Number of questions must be between 1 and 100")

            try:
                script_path = os.path.join(EVAL_DIR, "quick-test.py")
                if not os.path.exists(script_path):
                    return self.send_error_json(404, f"quick-test.py not found")

                command = ["python3", script_path, "--questions", str(n_questions), "--pipeline", pipeline]
                job_id = create_job("test", pipeline, command)

                return self.send_json({
                    "job_id": job_id,
                    "message": f"Test job started for {pipeline} with {n_questions} questions",
                    "command": " ".join(command),
                }, status=202)
            except Exception as e:
                return self.send_error_json(500, f"Failed to start test job: {e}")

        # Unknown endpoint
        return self.send_error_json(404, f"Unknown endpoint: {self.path}")


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
def run_server(port: int):
    """Run the remote control HTTP server."""
    server_address = ("", port)
    httpd = HTTPServer(server_address, RemoteControlHandler)

    print("=" * 60)
    print("  REMOTE CONTROL SERVER")
    print("=" * 60)
    print(f"  Listening on: http://0.0.0.0:{port}")
    print(f"  Auth key: {AUTH_KEY}")
    print(f"  Log file: {CONTROL_LOG}")
    print("=" * 60)
    print(f"  Endpoints:")
    print(f"    GET  /status               - Pipeline health check")
    print(f"    POST /fix/<pipeline>       - Launch auto-remediate.py")
    print(f"    POST /revert/<pipeline>    - Launch auto-revert.py")
    print(f"    POST /test/<pipeline>/<n>  - Launch quick-test.py")
    print(f"    GET  /jobs                 - List all jobs")
    print(f"    GET  /jobs/<id>            - Get job details")
    print("=" * 60)
    print(f"  Pipelines: {', '.join(PIPELINES)}")
    print("=" * 60)

    _log_event("server_started", {"port": port, "pid": os.getpid()})

    try:
        while not SHUTDOWN:
            httpd.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n[{_now()}] Server stopped")
        _log_event("server_stopped", {})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Remote Control Server - HTTP endpoint for pipeline management"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8081,
        help="Port to listen on (default: 8081)"
    )
    args = parser.parse_args()

    if args.port < 1 or args.port > 65535:
        print("ERROR: Port must be between 1 and 65535", file=sys.stderr)
        sys.exit(1)

    run_server(args.port)


if __name__ == "__main__":
    main()
