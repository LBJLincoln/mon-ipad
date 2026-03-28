#!/usr/bin/env python3
"""
Terminal API Server for Nomos42 Dashboard
Listens on port 8081, accepts POST /api/exec with command + token.
Rate-limited, blocklisted, CORS-enabled.
Multi-user: reads scripts/terminal/users.json for per-user tokens + access control.
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import deque

# ── Config ──────────────────────────────────────────────────────────────────

PORT = 8081
TERMINAL_TOKEN = os.environ.get("TERMINAL_TOKEN", "")
TIMEOUT = 30  # seconds
MAX_OUTPUT = 50_000  # chars

USERS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "terminal", "users.json",
)

# Rate limiting: max 10 requests per 60 seconds (global)
RATE_WINDOW = 60
RATE_LIMIT = 10
request_times: deque = deque()

# ── Multi-user helpers ───────────────────────────────────────────────────────

def load_users() -> dict:
    """Load users.json. Returns empty dict on failure."""
    try:
        with open(USERS_FILE) as f:
            data = json.load(f)
            return data.get("users", {})
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"[WARNING] Could not load users file: {e}")
        return {}


def resolve_token(token: str) -> dict | None:
    """
    Look up a token. Checks TERMINAL_TOKEN (admin) first, then users.json.
    Returns a user-info dict with at least: name, access_level.
    Returns None if the token is invalid.
    """
    if not token:
        return None
    # Admin token (env var)
    if TERMINAL_TOKEN and token == TERMINAL_TOKEN:
        return {"name": "admin", "access_level": "admin", "username": "admin"}
    # Per-user tokens from users.json
    users = load_users()
    for username, u in users.items():
        if u.get("terminal_token") == token and u.get("status") == "active":
            return {
                "name": u.get("name", username),
                "access_level": u.get("access_level", "operator"),
                "username": username,
                "role": u.get("role", ""),
            }
    return None


# Commands that operator-level users cannot run
OPERATOR_BLOCKLIST = [
    "kill", "pkill", "killall",
    "rm -rf", "rm -f",
    "git push",
    "git reset",
    "shutdown", "reboot", "poweroff", "halt",
    "sudo",
    "chmod -r",
    "passwd",
    "> /dev",
]


def is_operator_blocked(command: str) -> bool:
    """Return True if an operator-level user is not allowed to run this command."""
    cmd_lower = command.strip().lower()
    for pattern in OPERATOR_BLOCKLIST:
        if pattern in cmd_lower:
            return True
    return False

# Commands that are never allowed
BLOCKLIST = [
    "rm -rf /",
    "rm -rf /*",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "init 0",
    "init 6",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "> /dev/sda",
    "chmod -R 777 /",
]

ALLOWED_ORIGINS = [
    "https://nomosdashboard.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
]


def is_rate_limited() -> bool:
    """Check if rate limit exceeded."""
    now = time.time()
    # Remove old entries
    while request_times and request_times[0] < now - RATE_WINDOW:
        request_times.popleft()
    if len(request_times) >= RATE_LIMIT:
        return True
    request_times.append(now)
    return False


def is_blocked(command: str) -> bool:
    """Check command against blocklist."""
    cmd_lower = command.strip().lower()
    for blocked in BLOCKLIST:
        if blocked in cmd_lower:
            return True
    return False


class TerminalHandler(BaseHTTPRequestHandler):
    """HTTP handler for terminal API."""

    def _cors_headers(self, origin: str = ""):
        """Set CORS headers."""
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGINS[0])
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "3600")

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        origin = self.headers.get("Origin", "")
        self._cors_headers(origin)
        self.end_headers()

    def do_GET(self):
        """Health check endpoint."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "service": "terminal-api",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle command execution."""
        origin = self.headers.get("Origin", "")

        if self.path != "/api/exec":
            self.send_response(404)
            self._cors_headers(origin)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
            return

        # Rate limit
        if is_rate_limited():
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self._cors_headers(origin)
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Rate limit exceeded (10 req/min)",
                "output": "",
                "exit_code": -1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }).encode())
            return

        # Parse body
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self._cors_headers(origin)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
            return

        token = body.get("token", "")
        command = body.get("command", "").strip()

        # Auth — check admin token and per-user tokens
        if not TERMINAL_TOKEN and not load_users():
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self._cors_headers(origin)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "No tokens configured"}).encode())
            return

        user_info = resolve_token(token)
        if user_info is None:
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self._cors_headers(origin)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid token"}).encode())
            return

        if not command:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self._cors_headers(origin)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Empty command"}).encode())
            return

        # Per-user access control: operators get a restricted command set
        if user_info.get("access_level") == "operator" and is_operator_blocked(command):
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self._cors_headers(origin)
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": f"Command blocked for operator access level",
                "output": f"BLOCKED: '{command}' — operators cannot run kill/rm -rf/git push/reboot/sudo",
                "exit_code": -1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": user_info.get("name"),
            }).encode())
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] OPERATOR BLOCKED "
                  f"user={user_info.get('name')} cmd={command[:60]}")
            return

        # Global blocklist check
        if is_blocked(command):
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self._cors_headers(origin)
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Command blocked for safety",
                "output": f"BLOCKED: '{command}' matches global blocklist",
                "exit_code": -1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": user_info.get("name"),
            }).encode())
            return

        # Execute
        ts = datetime.now(timezone.utc)
        print(f"[{ts.strftime('%H:%M:%S')}] EXEC user={user_info.get('name')} "
              f"access={user_info.get('access_level')} cmd={command[:80]}")
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                cwd=os.path.expanduser("~"),
                env={**os.environ, "TERM": "dumb", "COLUMNS": "120"},
            )
            output = result.stdout + result.stderr
            if len(output) > MAX_OUTPUT:
                output = output[:MAX_OUTPUT] + f"\n\n[...truncated at {MAX_OUTPUT} chars]"

            response = {
                "output": output,
                "exit_code": result.returncode,
                "timestamp": ts.isoformat(),
                "user": user_info.get("name"),
            }
        except subprocess.TimeoutExpired:
            response = {
                "output": f"Command timed out after {TIMEOUT}s",
                "exit_code": -1,
                "timestamp": ts.isoformat(),
                "user": user_info.get("name"),
            }
        except Exception as e:
            response = {
                "output": f"Execution error: {str(e)}",
                "exit_code": -1,
                "timestamp": ts.isoformat(),
                "user": user_info.get("name"),
            }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._cors_headers(origin)
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        """Custom log format."""
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] {args[0]}" if args else "")


def main():
    users = load_users()
    active_users = [u for u, v in users.items() if v.get("status") == "active"]

    if not TERMINAL_TOKEN and not users:
        print("WARNING: No tokens configured!")
        print("  Set TERMINAL_TOKEN env var, or add users to scripts/terminal/users.json")
        print("  Continuing anyway — all requests will return 500 until tokens are set.")

    server = HTTPServer(("0.0.0.0", PORT), TerminalHandler)
    print(f"Terminal API listening on port {PORT}")
    print(f"Admin token (TERMINAL_TOKEN): {'configured' if TERMINAL_TOKEN else 'NOT SET'}")
    print(f"Users file: {USERS_FILE}")
    print(f"Active user accounts: {active_users}")
    print(f"Pending accounts: {[u for u, v in users.items() if v.get('status') == 'pending-setup']}")
    print(f"Rate limit: {RATE_LIMIT} req/{RATE_WINDOW}s")
    print(f"Timeout: {TIMEOUT}s")
    print(f"Allowed origins: {', '.join(ALLOWED_ORIGINS)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down terminal API...")
        server.shutdown()


if __name__ == "__main__":
    main()
