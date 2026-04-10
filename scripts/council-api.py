#!/usr/bin/env python3
"""
Council Action API — receives decisions from department councils.

Endpoints:
  POST /api/council-action   — log a council decision
  GET  /api/council-status   — last action per department
  GET  /api/council-history  — recent actions (JSONL)

Port: 8043 (stdlib only, no pip dependencies)
"""

import json
import os
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = 8043
LOG_DIR = Path("/home/termius/mon-ipad/logs")
LOG_FILE = LOG_DIR / "council-actions.jsonl"
MAX_HISTORY = 200

# In-memory last action per department
_last_actions = {}
_lock = threading.Lock()


def _load_history():
    """Load last actions from JSONL on startup."""
    if not LOG_FILE.exists():
        return
    try:
        for line in LOG_FILE.read_text().strip().split("\n"):
            if not line:
                continue
            entry = json.loads(line)
            dept = entry.get("dept_id", "")
            if dept:
                _last_actions[dept] = entry
    except Exception:
        pass


class CouncilHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/council-status":
            self._handle_status()
        elif self.path == "/api/council-history":
            self._handle_history()
        elif self.path == "/api/health":
            self.send_response(200)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        else:
            self.send_response(404)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')

    def do_POST(self):
        if self.path == "/api/council-action":
            self._handle_action()
        else:
            self.send_response(404)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')

    def _handle_status(self):
        with _lock:
            data = dict(_last_actions)
        self.send_response(200)
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({
            "departments": data,
            "count": len(data),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, default=str).encode())

    def _handle_history(self):
        lines = []
        if LOG_FILE.exists():
            try:
                all_lines = LOG_FILE.read_text().strip().split("\n")
                lines = all_lines[-MAX_HISTORY:]
            except Exception:
                pass
        entries = []
        for line in lines:
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
        self.send_response(200)
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(entries, default=str).encode())

    def _handle_action(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            self.send_response(400)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(b'{"error": "invalid JSON"}')
            return

        dept_id = body.get("dept_id") or body.get("dept", "")
        if not dept_id:
            self.send_response(400)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(b'{"error": "dept_id required"}')
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dept_id": dept_id,
            "dept_name": body.get("dept_name", ""),
            "action": body.get("action", ""),
            "decision": body.get("decision", {}),
            "model_used": body.get("model_used", ""),
            "iteration": body.get("iteration", 0),
            "source": body.get("source", "unknown"),
        }

        # Append to JSONL
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(LOG_FILE, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            print(f"[COUNCIL-API] Write error: {e}")

        # Update in-memory state
        with _lock:
            _last_actions[dept_id] = entry

        self.send_response(200)
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"status": "logged", "dept_id": dept_id}).encode())


if __name__ == "__main__":
    _load_history()
    server = HTTPServer(("0.0.0.0", PORT), CouncilHandler)
    print(f"[COUNCIL-API] Listening on port {PORT}")
    print(f"[COUNCIL-API] Log file: {LOG_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[COUNCIL-API] Shutting down")
        server.server_close()
