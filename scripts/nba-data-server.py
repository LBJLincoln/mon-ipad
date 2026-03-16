#!/usr/bin/env python3
"""
Simple HTTP server to serve NBA agent data files to Vercel.
Runs on port 8080, serves files from /home/termius/mon-ipad/data/nba-agent/
Also serves latest odds snapshots from nomos-nba-agent/data/

CORS enabled for nomos42.vercel.app
"""

import http.server
import json
import os
from pathlib import Path
from datetime import datetime, timezone

NBA_AGENT_DIR = Path("/home/termius/mon-ipad/data/nba-agent")
ODDS_DIR = Path("/home/termius/nomos-nba-agent/data")
PORT = 8080

ALLOWED_ORIGINS = [
    "https://nomos42.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
]


class NBADataHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet logging
        pass

    def do_GET(self):
        path = self.path.rstrip("/")

        # CORS headers
        origin = self.headers.get("Origin", "")
        cors_origin = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]

        # Route: /data/nba-agent/<file>
        if path.startswith("/data/nba-agent/"):
            filename = path.replace("/data/nba-agent/", "")
            filepath = NBA_AGENT_DIR / filename
            if filepath.exists() and filepath.is_file():
                self._serve_json(filepath, cors_origin)
                return

        # Route: /data/odds-latest.json — serve most recent odds snapshot
        if path == "/data/odds-latest.json":
            odds_files = sorted(ODDS_DIR.glob("odds-*.json"), reverse=True)
            if odds_files:
                self._serve_json(odds_files[0], cors_origin)
                return

        # Route: /health
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.end_headers()
            health = {
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "files": sorted([f.name for f in NBA_AGENT_DIR.glob("*.json")]),
            }
            self.wfile.write(json.dumps(health).encode())
            return

        # 404
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.end_headers()
        self.wfile.write(json.dumps({"error": "not found", "path": path}).encode())

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        cors_origin = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0]
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _serve_json(self, filepath, cors_origin):
        try:
            content = filepath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Cache-Control", "public, max-age=60")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), NBADataHandler)
    print(f"NBA Data Server running on port {PORT}")
    print(f"Serving: {NBA_AGENT_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
