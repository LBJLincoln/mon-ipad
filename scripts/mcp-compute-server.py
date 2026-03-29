#!/usr/bin/env python3
"""
NOMOS42 MCP Compute Server
==========================
Lightweight HTTP server (port 8082) that exposes compute platform
operations as tools callable by Claude Code.

Shells out to compute-cli.sh and returns JSON results.

Usage:
    python3 scripts/mcp-compute-server.py
    python3 scripts/mcp-compute-server.py --port 8082

Endpoints:
    GET  /tools                 List all available tools
    POST /tools/<tool_name>     Invoke a tool with JSON body args
    GET  /health                Health check
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_DIR   = SCRIPT_DIR.parent
CLI        = str(SCRIPT_DIR / "compute-cli.sh")
PORT       = int(os.environ.get("MCP_PORT", 8082))

# ── Tool registry ──────────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "spaces_status",
        "description": "Check health of all 6 HF evolution islands (brier, generation, HTTP status)",
        "parameters": {},
        "cli": ["spaces", "status"],
    },
    {
        "name": "spaces_keepalive",
        "description": "Ping all 6 HF Spaces to prevent auto-sleep on free tier",
        "parameters": {},
        "cli": ["spaces", "keepalive"],
    },
    {
        "name": "spaces_list",
        "description": "List all 6 HF islands with their roles and configs",
        "parameters": {},
        "cli": ["spaces", "list"],
    },
    {
        "name": "spaces_restart",
        "description": "Restart a specific HF Space island",
        "parameters": {
            "id": {
                "type": "string",
                "description": "Island ID: S10, S11, S12, S13, S14, or S15",
                "required": True,
            }
        },
        "cli": ["spaces", "restart"],  # + id
    },
    {
        "name": "spaces_logs",
        "description": "Get current status/logs from a specific HF Space",
        "parameters": {
            "id": {
                "type": "string",
                "description": "Island ID: S10-S15",
                "required": True,
            }
        },
        "cli": ["spaces", "logs"],
    },
    {
        "name": "spaces_config",
        "description": "Show current evolution config for a specific HF Space",
        "parameters": {
            "id": {
                "type": "string",
                "description": "Island ID: S10-S15",
                "required": True,
            }
        },
        "cli": ["spaces", "config"],
    },
    {
        "name": "spaces_deploy",
        "description": "Push feature engine (features/engine.py) to all 6 HF Spaces",
        "parameters": {},
        "cli": ["spaces", "deploy"],
    },
    {
        "name": "kaggle_status",
        "description": "Check status of Kaggle kernels (NBA + Political + backtest)",
        "parameters": {
            "kernel": {
                "type": "string",
                "description": "Kernel alias: nba, pol, backtest (optional, default: all)",
                "required": False,
            }
        },
        "cli": ["kaggle", "status"],
    },
    {
        "name": "kaggle_list",
        "description": "List all Kaggle kernels owned by this account",
        "parameters": {},
        "cli": ["kaggle", "list"],
    },
    {
        "name": "kaggle_push",
        "description": "Push and run a Kaggle kernel from a local directory",
        "parameters": {
            "dir": {
                "type": "string",
                "description": "Absolute path to the kernel directory containing kernel-metadata.json",
                "required": True,
            }
        },
        "cli": ["kaggle", "push"],
    },
    {
        "name": "kaggle_logs",
        "description": "Get output logs from a Kaggle kernel",
        "parameters": {
            "kernel": {
                "type": "string",
                "description": "Kernel alias: nba, pol, backtest",
                "required": False,
            }
        },
        "cli": ["kaggle", "logs"],
    },
    {
        "name": "kaggle_run_nba",
        "description": "Push and run the NBA Karpathy loop on Kaggle GPU",
        "parameters": {},
        "cli": ["kaggle", "run-nba"],
    },
    {
        "name": "kaggle_run_pol",
        "description": "Push and run the Political Karpathy loop on Kaggle GPU",
        "parameters": {},
        "cli": ["kaggle", "run-pol"],
    },
    {
        "name": "kaggle_run_backtest",
        "description": "Push and run the NBA season backtest on Kaggle GPU",
        "parameters": {},
        "cli": ["kaggle", "run-backtest"],
    },
    {
        "name": "modal_status",
        "description": "Check Modal app status and list active/recent runs",
        "parameters": {},
        "cli": ["modal", "status"],
    },
    {
        "name": "modal_run",
        "description": "Run NBA TabICL evolution on Modal serverless GPU",
        "parameters": {
            "gens": {
                "type": "integer",
                "description": "Number of generations to run (default: 200)",
                "required": False,
            },
            "resume": {
                "type": "boolean",
                "description": "Resume from last checkpoint",
                "required": False,
            },
        },
        "cli": ["modal", "run"],
    },
    {
        "name": "modal_logs",
        "description": "Get recent Modal evolution logs",
        "parameters": {},
        "cli": ["modal", "logs"],
    },
    {
        "name": "modal_deploy",
        "description": "Deploy or update the Modal app",
        "parameters": {},
        "cli": ["modal", "deploy"],
    },
    {
        "name": "modal_stop",
        "description": "Stop a running Modal app",
        "parameters": {},
        "cli": ["modal", "stop"],
    },
    {
        "name": "codespace_create",
        "description": "Create a new GitHub Codespace for the mon-ipad repo",
        "parameters": {},
        "cli": ["codespace", "create"],
    },
    {
        "name": "codespace_status",
        "description": "List all GitHub Codespaces and their status",
        "parameters": {},
        "cli": ["codespace", "status"],
    },
    {
        "name": "codespace_stop",
        "description": "Stop a GitHub Codespace",
        "parameters": {
            "name": {
                "type": "string",
                "description": "Codespace name (optional, defaults to first active)",
                "required": False,
            }
        },
        "cli": ["codespace", "stop"],
    },
    {
        "name": "all_status",
        "description": "Check all compute platforms at once: HF Spaces + Kaggle + Modal + Codespaces",
        "parameters": {},
        "cli": ["all", "status"],
    },
]

TOOL_INDEX = {t["name"]: t for t in TOOLS}


# ── CLI runner ─────────────────────────────────────────────────────────────

def run_cli(args: list[str], timeout: int = 60) -> dict[str, Any]:
    """Run compute-cli.sh with the given args and return structured result."""
    cmd = ["bash", CLI] + args
    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_DIR),
        )
        elapsed = time.monotonic() - start
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "elapsed_s": round(elapsed, 2),
            "cmd": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"Timed out after {timeout}s",
            "cmd": " ".join(cmd),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "cmd": " ".join(cmd),
        }


def build_cli_args(tool: dict[str, Any], params: dict[str, Any]) -> list[str]:
    """Build CLI args from tool definition and incoming params."""
    args = list(tool["cli"])  # e.g. ["spaces", "restart"]
    tool_params = tool.get("parameters", {})

    # Append positional args for required/provided params
    for pname, pdef in tool_params.items():
        val = params.get(pname)
        if val is None:
            continue
        # Special handling for modal --gens
        if pname == "gens":
            args.extend(["--gens", str(val)])
        elif pname == "resume" and val:
            args.append("--resume")
        else:
            args.append(str(val))

    return args


# ── HTTP handler ───────────────────────────────────────────────────────────

class MCPHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt: str, *args: Any) -> None:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        print(f"[{ts}] {fmt % args}", flush=True)

    def send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")

        if path == "/health":
            self.send_json({
                "status": "ok",
                "server": "nomos42-mcp-compute",
                "version": "1.0",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tools_count": len(TOOLS),
                "cli": CLI,
            })

        elif path == "/tools":
            # Return tool list (MCP format)
            self.send_json({
                "tools": [
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t.get("parameters", {}),
                    }
                    for t in TOOLS
                ]
            })

        elif path.startswith("/tools/"):
            tool_name = path[len("/tools/"):]
            if tool_name in TOOL_INDEX:
                t = TOOL_INDEX[tool_name]
                self.send_json({
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("parameters", {}),
                    "cli": t["cli"],
                })
            else:
                self.send_json({"error": f"Tool not found: {tool_name}"}, 404)

        else:
            self.send_json({"error": "Not found", "path": path}, 404)

    def do_POST(self) -> None:
        path = self.path.split("?")[0].rstrip("/")

        if not path.startswith("/tools/"):
            self.send_json({"error": "POST only supported on /tools/<name>"}, 400)
            return

        tool_name = path[len("/tools/"):]
        if tool_name not in TOOL_INDEX:
            self.send_json({"error": f"Tool not found: {tool_name}"}, 404)
            return

        # Parse body
        params: dict[str, Any] = {}
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw = self.rfile.read(content_length)
            try:
                params = json.loads(raw)
            except json.JSONDecodeError as exc:
                self.send_json({"error": f"Invalid JSON body: {exc}"}, 400)
                return

        tool = TOOL_INDEX[tool_name]
        cli_args = build_cli_args(tool, params)
        result = run_cli(cli_args, timeout=90)

        self.send_json({
            "tool": tool_name,
            "params": params,
            "result": result,
        })


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    port = PORT
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        port = int(sys.argv[idx + 1])

    # Verify CLI exists
    if not Path(CLI).exists():
        print(f"[ERROR] compute-cli.sh not found at: {CLI}", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"[INFO] MCP Compute Server listening on http://0.0.0.0:{port}", flush=True)
    print(f"[INFO] Tools: {len(TOOLS)} | CLI: {CLI}", flush=True)
    print(f"[INFO] Endpoints: GET /health  GET /tools  POST /tools/<name>", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped", flush=True)


if __name__ == "__main__":
    main()
