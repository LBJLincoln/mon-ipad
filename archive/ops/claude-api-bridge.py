#!/usr/bin/env python3
"""Claude Code CLI API Bridge — HTTP server that forwards messages to claude --print.

Allows Dashboard chatbot and Telegram to talk to Claude Code CLI
as if they were on Termius.

Usage:
    source .env.local
    python3 ops/claude-api-bridge.py [--port 3001]

Endpoints:
    POST /ask   { "message": "...", "cwd": "/home/termius/mon-ipad" }
                → { "response": "...", "duration": 2.3 }
    GET  /health → { "status": "ok", "claude_version": "..." }
"""

import json
import os
import subprocess
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 3001
BASE_DIR = "/home/termius/mon-ipad"
BRIDGE_SECRET = os.environ.get("CLAUDE_BRIDGE_SECRET", "nomos-bridge-2026")

# Rate limiting
last_request_time = 0
MIN_INTERVAL = 2  # seconds between requests
active_lock = threading.Lock()

def get_claude_version():
    try:
        r = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except:
        return "unknown"

def ask_claude(message, cwd=None):
    """Send a message to claude --print and return the response."""
    env = os.environ.copy()
    # Source .env.local
    env_file = Path(BASE_DIR) / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                if line.startswith("export "):
                    line = line[7:]
                k, v = line.split("=", 1)
                v = v.strip("'\"")
                env[k.strip()] = v

    start = time.time()
    try:
        r = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions", message],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd or BASE_DIR,
            env=env,
        )
        duration = time.time() - start
        output = (r.stdout or "").strip()
        if r.returncode != 0 and r.stderr:
            output = output + "\n" + r.stderr.strip() if output else r.stderr.strip()
        # Truncate very long responses
        if len(output) > 8000:
            output = output[:3500] + "\n\n...(tronque)...\n\n" + output[-3500:]
        return {"response": output, "duration": round(duration, 2), "ok": True}
    except subprocess.TimeoutExpired:
        return {"response": "Timeout (120s). La requete etait trop complexe.", "duration": 120, "ok": False}
    except Exception as e:
        return {"response": f"Erreur: {str(e)}", "duration": time.time() - start, "ok": False}


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {args[0]}" if args else "")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _check_auth(self):
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {BRIDGE_SECRET}":
            self._json_response(401, {"error": "Non autorise"})
            return False
        return True

    def do_GET(self):
        if self.path == "/health":
            self._json_response(200, {
                "status": "ok",
                "claude_version": get_claude_version(),
                "uptime_pid": os.getpid(),
            })
        else:
            self._json_response(404, {"error": "Not found"})

    def do_POST(self):
        global last_request_time

        if self.path == "/ask":
            if not self._check_auth():
                return

            # Rate limit
            now = time.time()
            if now - last_request_time < MIN_INTERVAL:
                self._json_response(429, {"error": "Trop de requetes. Attendez quelques secondes."})
                return

            # Read body
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except:
                self._json_response(400, {"error": "JSON invalide"})
                return

            message = data.get("message", "").strip()
            cwd = data.get("cwd", BASE_DIR)

            if not message:
                self._json_response(400, {"error": "Message vide"})
                return

            if len(message) > 5000:
                self._json_response(400, {"error": "Message trop long (max 5000 chars)"})
                return

            # Ensure only one request at a time
            if not active_lock.acquire(blocking=False):
                self._json_response(503, {"error": "Claude est occupe avec une autre requete."})
                return

            try:
                last_request_time = time.time()
                print(f"[{time.strftime('%H:%M:%S')}] ASK: {message[:80]}...")
                result = ask_claude(message, cwd)
                print(f"[{time.strftime('%H:%M:%S')}] DONE: {result['duration']}s, {len(result['response'])} chars")
                self._json_response(200, result)
            finally:
                active_lock.release()
        else:
            self._json_response(404, {"error": "Not found"})


if __name__ == "__main__":
    print(f"=== CLAUDE API BRIDGE ===")
    print(f"Port: {PORT}")
    print(f"Claude: {get_claude_version()}")
    print(f"Secret: {BRIDGE_SECRET[:8]}...")
    print(f"CWD: {BASE_DIR}")
    print(f"Listening on http://0.0.0.0:{PORT}")
    print()

    server = HTTPServer(("0.0.0.0", PORT), BridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
