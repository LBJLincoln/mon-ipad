#!/usr/bin/env python3
"""
Remote Control Client — Simplified client for mobile/remote access.

Usage:
    python3 scripts/remote-control-client.py status
    python3 scripts/remote-control-client.py test standard 5
    python3 scripts/remote-control-client.py fix graph
    python3 scripts/remote-control-client.py revert quantitative
    python3 scripts/remote-control-client.py jobs
    python3 scripts/remote-control-client.py job <job-id>

Configuration:
    Set environment variables:
    - REMOTE_CONTROL_URL (default: http://localhost:8081)
    - REMOTE_CONTROL_KEY (required)
"""

import json
import os
import sys
import time
from urllib import request, error


def load_config():
    """Load configuration from environment."""
    url = os.environ.get("REMOTE_CONTROL_URL", "http://localhost:8081")
    key = os.environ.get("REMOTE_CONTROL_KEY", "")

    if not key:
        print("ERROR: REMOTE_CONTROL_KEY not set", file=sys.stderr)
        print("       export REMOTE_CONTROL_KEY=your-key-here", file=sys.stderr)
        sys.exit(1)

    return url.rstrip("/"), key


def api_call(base_url, auth_key, method, path, data=None):
    """Make API call to remote control server."""
    url = base_url + path
    headers = {
        "X-Auth-Key": auth_key,
        "Content-Type": "application/json",
    }

    body = None
    if data:
        body = json.dumps(data).encode("utf-8")

    try:
        req = request.Request(url, data=body, headers=headers, method=method)
        with request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_data = json.loads(err_body)
            print(f"ERROR {e.code}: {err_data.get('error', err_body)}", file=sys.stderr)
        except Exception:
            print(f"ERROR {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(base_url, auth_key):
    """Get pipeline status."""
    result = api_call(base_url, auth_key, "GET", "/status")

    print("=" * 60)
    print("  PIPELINE STATUS")
    print("=" * 60)
    print(f"  Overall: {result['overall_status'].upper()}")
    print(f"  Host: {result['n8n_host']}")
    print(f"  Timestamp: {result['timestamp']}")
    print("=" * 60)

    for name, pipe in result["pipelines"].items():
        status_color = {
            "healthy": "\033[92m",  # green
            "degraded": "\033[93m",  # yellow
            "down": "\033[91m",  # red
            "timeout": "\033[91m",  # red
        }.get(pipe["status"], "")
        reset = "\033[0m"

        print(f"\n  {name.upper()}")
        print(f"    Status: {status_color}{pipe['status']}{reset}")
        print(f"    Latency: {pipe['latency_ms']}ms (expected: {pipe['expected_latency_ms']}ms)")
        print(f"    HTTP: {pipe['http_code']}")
        print(f"    Answer: {pipe['answer_length']} chars")
        if pipe["error"]:
            print(f"    Error: {pipe['error'][:80]}")

    summary = result["summary"]
    print("\n" + "=" * 60)
    print(f"  {summary['healthy']}/{summary['total']} healthy, "
          f"{summary['degraded']} degraded, {summary['down']} down")
    print("=" * 60)


def cmd_test(base_url, auth_key, pipeline, n_questions):
    """Launch test job."""
    result = api_call(base_url, auth_key, "POST", f"/test/{pipeline}/{n_questions}")

    print(f"Job started: {result['job_id']}")
    print(f"Command: {result['command']}")
    print(f"\nCheck status: python3 scripts/remote-control-client.py job {result['job_id']}")


def cmd_fix(base_url, auth_key, pipeline):
    """Launch fix job."""
    result = api_call(base_url, auth_key, "POST", f"/fix/{pipeline}")

    print(f"Fix job started: {result['job_id']}")
    print(f"Command: {result['command']}")
    print(f"\nCheck status: python3 scripts/remote-control-client.py job {result['job_id']}")


def cmd_revert(base_url, auth_key, pipeline):
    """Launch revert job."""
    result = api_call(base_url, auth_key, "POST", f"/revert/{pipeline}")

    print(f"Revert job started: {result['job_id']}")
    print(f"Command: {result['command']}")
    print(f"\nCheck status: python3 scripts/remote-control-client.py job {result['job_id']}")


def cmd_jobs(base_url, auth_key):
    """List all jobs."""
    result = api_call(base_url, auth_key, "GET", "/jobs")

    print("=" * 60)
    print(f"  JOBS ({result['count']})")
    print("=" * 60)

    for job in result["jobs"]:
        status_icon = {
            "running": "🔄",
            "completed": "✅",
            "failed": "❌",
        }.get(job["status"], "?")

        print(f"\n  {status_icon} {job['id']}")
        print(f"    Type: {job['type']}")
        print(f"    Pipeline: {job['pipeline']}")
        print(f"    Status: {job['status']}")
        print(f"    Started: {job['started_at']}")
        if job["finished_at"]:
            print(f"    Finished: {job['finished_at']}")
        if job["exit_code"] is not None:
            print(f"    Exit code: {job['exit_code']}")

    print("\n" + "=" * 60)


def cmd_job(base_url, auth_key, job_id):
    """Get job details."""
    result = api_call(base_url, auth_key, "GET", f"/jobs/{job_id}")

    status_icon = {
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
    }.get(result["status"], "?")

    print("=" * 60)
    print(f"  {status_icon} JOB: {result['id']}")
    print("=" * 60)
    print(f"  Type: {result['type']}")
    print(f"  Pipeline: {result['pipeline']}")
    print(f"  Status: {result['status']}")
    print(f"  Started: {result['started_at']}")
    if result["finished_at"]:
        print(f"  Finished: {result['finished_at']}")
    if result["exit_code"] is not None:
        print(f"  Exit code: {result['exit_code']}")
    print(f"  Command: {result['command']}")

    if result["stdout"]:
        print("\n" + "-" * 60)
        print("  STDOUT:")
        print("-" * 60)
        print(result["stdout"])

    if result["stderr"]:
        print("\n" + "-" * 60)
        print("  STDERR:")
        print("-" * 60)
        print(result["stderr"])

    print("=" * 60)


def cmd_wait(base_url, auth_key, job_id, max_wait=300):
    """Wait for job to complete."""
    start = time.time()
    print(f"Waiting for job {job_id} to complete...")

    while time.time() - start < max_wait:
        result = api_call(base_url, auth_key, "GET", f"/jobs/{job_id}")

        if result["status"] != "running":
            print(f"\nJob {result['status']}: {result['id']}")
            if result["exit_code"] is not None:
                print(f"Exit code: {result['exit_code']}")
            return result["exit_code"] or 0

        print(".", end="", flush=True)
        time.sleep(5)

    print(f"\nTIMEOUT: Job still running after {max_wait}s")
    return 1


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  remote-control-client.py status")
        print("  remote-control-client.py test <pipeline> <n>")
        print("  remote-control-client.py fix <pipeline>")
        print("  remote-control-client.py revert <pipeline>")
        print("  remote-control-client.py jobs")
        print("  remote-control-client.py job <job-id>")
        print("  remote-control-client.py wait <job-id> [max_wait_seconds]")
        print()
        print("Pipelines: standard, graph, quantitative, orchestrator")
        sys.exit(1)

    base_url, auth_key = load_config()
    command = sys.argv[1].lower()

    if command == "status":
        cmd_status(base_url, auth_key)

    elif command == "test":
        if len(sys.argv) < 4:
            print("Usage: remote-control-client.py test <pipeline> <n>", file=sys.stderr)
            sys.exit(1)
        cmd_test(base_url, auth_key, sys.argv[2], sys.argv[3])

    elif command == "fix":
        if len(sys.argv) < 3:
            print("Usage: remote-control-client.py fix <pipeline>", file=sys.stderr)
            sys.exit(1)
        cmd_fix(base_url, auth_key, sys.argv[2])

    elif command == "revert":
        if len(sys.argv) < 3:
            print("Usage: remote-control-client.py revert <pipeline>", file=sys.stderr)
            sys.exit(1)
        cmd_revert(base_url, auth_key, sys.argv[2])

    elif command == "jobs":
        cmd_jobs(base_url, auth_key)

    elif command == "job":
        if len(sys.argv) < 3:
            print("Usage: remote-control-client.py job <job-id>", file=sys.stderr)
            sys.exit(1)
        cmd_job(base_url, auth_key, sys.argv[2])

    elif command == "wait":
        if len(sys.argv) < 3:
            print("Usage: remote-control-client.py wait <job-id> [max_wait_seconds]", file=sys.stderr)
            sys.exit(1)
        max_wait = int(sys.argv[3]) if len(sys.argv) > 3 else 300
        exit_code = cmd_wait(base_url, auth_key, sys.argv[2], max_wait)
        sys.exit(exit_code)

    else:
        print(f"ERROR: Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
