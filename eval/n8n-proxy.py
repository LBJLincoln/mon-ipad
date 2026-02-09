#!/usr/bin/env python3
"""
N8N Live Proxy — Fetches n8n execution logs and serves them for the dashboard.

This script provides two modes:
  1. FETCH mode: Pulls execution data from n8n REST API and saves to logs/n8n-live/
  2. SERVE mode: Serves execution data as a JSON API for the dashboard

The dashboard can then query this data to show node-by-node execution details.

Usage:
  python eval/n8n-proxy.py --fetch                  # Fetch latest executions from n8n
  python eval/n8n-proxy.py --fetch --workflow graph  # Fetch for specific workflow
  python eval/n8n-proxy.py --fetch --last 20         # Fetch last 20 executions
  python eval/n8n-proxy.py --serve --port 8787       # Serve data for dashboard
  python eval/n8n-proxy.py --fetch --continuous      # Fetch every 30s
"""

import json
import os
import sys
import time
from datetime import datetime
from urllib import request, error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N8N_LIVE_DIR = os.path.join(REPO_ROOT, "logs", "n8n-live")
LATEST_FILE = os.path.join(N8N_LIVE_DIR, "latest.json")
os.makedirs(N8N_LIVE_DIR, exist_ok=True)

N8N_HOST = os.environ.get("N8N_HOST", "https://amoret.app.n8n.cloud")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

WORKFLOW_IDS = {
    "standard": "LnTqRX4LZlI009Ks-3Jnp",
    "graph": "95x2BBAbJlLWZtWEJn6rb",
    "quantitative": "E19NZG9WfM7FNsxr",
    "orchestrator": "ALd4gOEqiKL5KR1p",
}

WORKFLOW_NAMES = {v: k for k, v in WORKFLOW_IDS.items()}


def n8n_api(path, method="GET", data=None):
    """Call n8n REST API."""
    url = f"{N8N_HOST}/api/v1{path}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY

    body = json.dumps(data).encode() if data else None
    req = request.Request(url, data=body, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  n8n API error: {e.code} {e.reason} — {body[:200]}")
        return None
    except Exception as e:
        print(f"  n8n API error: {e}")
        return None


def fetch_executions(workflow_id=None, limit=10, status=None):
    """Fetch executions from n8n API."""
    params = [f"limit={limit}", "includeData=true"]
    if workflow_id:
        params.append(f"workflowId={workflow_id}")
    if status:
        params.append(f"status={status}")

    path = "/executions?" + "&".join(params)
    result = n8n_api(path)

    if not result:
        return []

    return result.get("data", [])


def parse_execution(execution):
    """Parse a raw n8n execution into a structured format."""
    exec_id = execution.get("id", "unknown")
    wf_id = execution.get("workflowId", "")
    pipeline = WORKFLOW_NAMES.get(wf_id, "unknown")
    status = execution.get("status", "unknown")
    started = execution.get("startedAt", "")
    finished = execution.get("stoppedAt", "")
    mode = execution.get("mode", "")

    # Parse node execution data
    nodes = []
    run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})

    for node_name, node_runs in run_data.items():
        if not isinstance(node_runs, list):
            continue
        for run in node_runs:
            node_info = {
                "name": node_name,
                "status": "success",
                "started": run.get("startTime"),
                "finished": None,
                "duration_ms": run.get("executionTime", 0),
                "items_in": 0,
                "items_out": 0,
                "error": None,
                "data_preview": None,
            }

            # Extract execution status
            if run.get("error"):
                node_info["status"] = "error"
                err = run["error"]
                if isinstance(err, dict):
                    node_info["error"] = err.get("message", str(err))[:500]
                else:
                    node_info["error"] = str(err)[:500]

            # Extract input/output counts
            input_data = run.get("inputData", {}).get("main", [])
            output_data = run.get("data", {}).get("main", [])

            if input_data:
                node_info["items_in"] = sum(len(d) if isinstance(d, list) else 0 for d in input_data)
            if output_data:
                node_info["items_out"] = sum(len(d) if isinstance(d, list) else 0 for d in output_data)

            # Extract data preview (first item output)
            if output_data and isinstance(output_data, list) and len(output_data) > 0:
                first_output = output_data[0]
                if isinstance(first_output, list) and len(first_output) > 0:
                    item = first_output[0]
                    if isinstance(item, dict):
                        json_data = item.get("json", item)
                        preview = json.dumps(json_data, ensure_ascii=False)[:500]
                        node_info["data_preview"] = preview

            nodes.append(node_info)

    # Compute total duration
    duration_ms = 0
    if started and finished:
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass

    # Extract trigger data (query)
    trigger_query = ""
    trigger_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
    for node_name, node_runs in trigger_data.items():
        if "webhook" in node_name.lower() or "trigger" in node_name.lower():
            if isinstance(node_runs, list) and node_runs:
                output_data = node_runs[0].get("data", {}).get("main", [])
                if output_data and isinstance(output_data, list) and output_data:
                    first = output_data[0]
                    if isinstance(first, list) and first:
                        item = first[0]
                        if isinstance(item, dict):
                            json_data = item.get("json", item)
                            trigger_query = json_data.get("query", json_data.get("question", ""))
                            if isinstance(trigger_query, str):
                                trigger_query = trigger_query[:200]

    return {
        "execution_id": exec_id,
        "workflow_id": wf_id,
        "pipeline": pipeline,
        "status": status,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": duration_ms,
        "mode": mode,
        "trigger_query": trigger_query,
        "nodes": nodes,
        "node_count": len(nodes),
        "error_nodes": [n for n in nodes if n["status"] == "error"],
    }


def fetch_and_save(workflow_filter=None, limit=10):
    """Fetch executions and save to disk."""
    print(f"\n  Fetching last {limit} executions from n8n...")

    all_executions = []

    if workflow_filter:
        wf_id = WORKFLOW_IDS.get(workflow_filter)
        if not wf_id:
            print(f"  Unknown workflow: {workflow_filter}")
            return []
        raw = fetch_executions(workflow_id=wf_id, limit=limit)
        for ex in raw:
            parsed = parse_execution(ex)
            all_executions.append(parsed)
            print(f"    [{parsed['pipeline']}] exec-{parsed['execution_id']} | "
                  f"{parsed['status']} | {parsed['duration_ms']}ms | {parsed['node_count']} nodes"
                  + (f" | query: {parsed['trigger_query'][:60]}" if parsed['trigger_query'] else ""))
    else:
        for name, wf_id in WORKFLOW_IDS.items():
            raw = fetch_executions(workflow_id=wf_id, limit=limit)
            for ex in raw:
                parsed = parse_execution(ex)
                all_executions.append(parsed)
                print(f"    [{parsed['pipeline']}] exec-{parsed['execution_id']} | "
                      f"{parsed['status']} | {parsed['duration_ms']}ms | {parsed['node_count']} nodes")

    # Sort by timestamp
    all_executions.sort(key=lambda x: x.get("started_at", ""), reverse=True)

    # Save latest
    latest = {
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "total_executions": len(all_executions),
        "executions": all_executions,
        "summary": {
            "by_pipeline": {},
            "by_status": {},
            "error_nodes_total": sum(len(e["error_nodes"]) for e in all_executions),
        },
    }

    # Compute summary
    for ex in all_executions:
        pipe = ex["pipeline"]
        status = ex["status"]
        if pipe not in latest["summary"]["by_pipeline"]:
            latest["summary"]["by_pipeline"][pipe] = {"total": 0, "success": 0, "error": 0, "avg_duration_ms": 0}
        latest["summary"]["by_pipeline"][pipe]["total"] += 1
        if status == "success":
            latest["summary"]["by_pipeline"][pipe]["success"] += 1
        else:
            latest["summary"]["by_pipeline"][pipe]["error"] += 1

        latest["summary"]["by_status"][status] = latest["summary"]["by_status"].get(status, 0) + 1

    # Compute avg durations
    for pipe, info in latest["summary"]["by_pipeline"].items():
        durations = [e["duration_ms"] for e in all_executions if e["pipeline"] == pipe and e["duration_ms"] > 0]
        info["avg_duration_ms"] = int(sum(durations) / len(durations)) if durations else 0

    with open(LATEST_FILE, "w") as f:
        json.dump(latest, f, indent=2, ensure_ascii=False)

    # Also save individual execution files for deep inspection
    for ex in all_executions[:20]:
        ex_path = os.path.join(N8N_LIVE_DIR, f"exec-{ex['execution_id']}.json")
        if not os.path.exists(ex_path):
            with open(ex_path, "w") as f:
                json.dump(ex, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved {len(all_executions)} executions to {LATEST_FILE}")
    return all_executions


def serve_api(port=8787):
    """Serve execution data as a simple HTTP JSON API for the dashboard."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            if self.path == "/api/executions" or self.path == "/":
                if os.path.exists(LATEST_FILE):
                    with open(LATEST_FILE) as f:
                        data = f.read()
                    self.wfile.write(data.encode())
                else:
                    self.wfile.write(b'{"executions":[],"error":"No data yet. Run --fetch first."}')

            elif self.path.startswith("/api/execution/"):
                exec_id = self.path.split("/")[-1]
                ex_path = os.path.join(N8N_LIVE_DIR, f"exec-{exec_id}.json")
                if os.path.exists(ex_path):
                    with open(ex_path) as f:
                        data = f.read()
                    self.wfile.write(data.encode())
                else:
                    self.wfile.write(b'{"error":"Execution not found"}')

            elif self.path == "/api/knowledge-base":
                kb_path = os.path.join(REPO_ROOT, "docs", "knowledge-base.json")
                if os.path.exists(kb_path):
                    with open(kb_path) as f:
                        data = f.read()
                    self.wfile.write(data.encode())
                else:
                    self.wfile.write(b'{"error":"Knowledge base not found"}')

            elif self.path == "/api/stages":
                stages_path = os.path.join(REPO_ROOT, "logs", "iterative-eval", "latest-stages.json")
                if os.path.exists(stages_path):
                    with open(stages_path) as f:
                        data = f.read()
                    self.wfile.write(data.encode())
                else:
                    self.wfile.write(b'{"error":"No stage data. Run iterative-eval.py first."}')

            else:
                self.wfile.write(b'{"endpoints":["/api/executions","/api/execution/{id}","/api/knowledge-base","/api/stages"]}')

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress request logs

    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"  n8n proxy serving on http://localhost:{port}")
    print(f"  Endpoints:")
    print(f"    GET /api/executions       — All latest executions")
    print(f"    GET /api/execution/{{id}}   — Single execution detail")
    print(f"    GET /api/knowledge-base   — Knowledge base")
    print(f"    GET /api/stages           — Latest iterative eval stages")
    server.serve_forever()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="n8n Live Proxy — Fetch and serve execution data")
    parser.add_argument("--fetch", action="store_true", help="Fetch latest executions from n8n")
    parser.add_argument("--serve", action="store_true", help="Serve execution data as JSON API")
    parser.add_argument("--port", type=int, default=8787, help="Port for API server (default: 8787)")
    parser.add_argument("--workflow", type=str, default=None,
                        choices=["standard", "graph", "quantitative", "orchestrator"],
                        help="Filter to specific workflow")
    parser.add_argument("--last", type=int, default=10, help="Number of executions to fetch (default: 10)")
    parser.add_argument("--continuous", action="store_true", help="Fetch every 30s continuously")
    args = parser.parse_args()

    if args.fetch:
        if args.continuous:
            print("  Continuous fetch mode (Ctrl+C to stop)...")
            while True:
                fetch_and_save(workflow_filter=args.workflow, limit=args.last)
                time.sleep(30)
        else:
            fetch_and_save(workflow_filter=args.workflow, limit=args.last)
    elif args.serve:
        serve_api(port=args.port)
    else:
        # Default: fetch then print summary
        execs = fetch_and_save(workflow_filter=args.workflow, limit=args.last)
        if execs:
            print(f"\n  Summary:")
            for pipe in ["standard", "graph", "quantitative", "orchestrator"]:
                pipe_execs = [e for e in execs if e["pipeline"] == pipe]
                if pipe_execs:
                    successes = sum(1 for e in pipe_execs if e["status"] == "success")
                    avg_dur = int(sum(e["duration_ms"] for e in pipe_execs) / len(pipe_execs)) if pipe_execs else 0
                    print(f"    {pipe:15s}: {successes}/{len(pipe_execs)} success | avg {avg_dur}ms")


if __name__ == "__main__":
    main()
