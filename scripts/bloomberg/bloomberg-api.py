#!/usr/bin/env python3
"""
Nomos42 Bloomberg API — Lightweight HTTP Server
================================================
Serves NBA betting intelligence data via REST endpoints.
Uses ONLY stdlib http.server — no FastAPI, no Flask, no dependencies.

Endpoints:
  GET /api/odds           — Latest NBA odds
  GET /api/predictions    — Latest model predictions
  GET /api/value-bets     — Current value bets
  GET /api/trading-floor  — Trading Floor v4 leaderboard
  GET /api/evolution      — 6-island fleet status
  GET /api/bankroll       — Bankroll and P&L state
  GET /api/quant          — Quant summary (models, features, calibration)
  GET /api/health         — System health overview
  GET /api/all            — All data combined (full terminal state)

Usage:
  python3 bloomberg-api.py                  # default port 8042
  python3 bloomberg-api.py --port 9000      # custom port
  python3 bloomberg-api.py --host 0.0.0.0   # bind to all interfaces

All data is read from local JSON files in the data/ directory.
"""

import json
import os
import sys
import datetime
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
NBA_DIR = DATA_DIR / "nba-agent"
ARENA_DIR = DATA_DIR / "arena"

# Data file registry
DATA_FILES = {
    "odds": NBA_DIR / "odds-latest.json",
    "predictions": NBA_DIR / "predictions-today.json",
    "value-bets": NBA_DIR / "value-bets.json",
    "trading-floor": ARENA_DIR / "trading-floor-v4-latest.json",
    "bankroll": NBA_DIR / "bankroll-state.json",
    "quant": NBA_DIR / "quant-summary.json",
    "eval": NBA_DIR / "latest-eval.json",
    "health": DATA_DIR / "agent-health.json",
    "infra": DATA_DIR / "infra-status.json",
    "fleet": DATA_DIR / "fleet-status.json",
}

# HF Space URLs for live checks
HF_SPACES = {
    "S10": {"url": "https://nomos42-nba-quant.hf.space", "role": "exploitation"},
    "S11": {"url": "https://nomos42-nba-quant-2.hf.space", "role": "exploration"},
    "S12": {"url": "https://nomos42-nba-evo-3.hf.space", "role": "extra_trees"},
    "S13": {"url": "https://nomos42-nba-evo-4.hf.space", "role": "catboost"},
    "S14": {"url": "https://nomos42-nba-evo-5.hf.space", "role": "lightgbm"},
    "S15": {"url": "https://nomos42-nba-evo-6.hf.space", "role": "wide_search"},
}


def load_json(path: Path) -> dict | list | None:
    """Safely load a JSON file."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
        return {"error": str(e), "path": str(path)}


def get_odds() -> dict:
    """Get latest odds data."""
    data = load_json(DATA_FILES["odds"])
    return {
        "endpoint": "odds",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "source": str(DATA_FILES["odds"]),
        "data": data,
    }


def get_predictions() -> dict:
    """Get latest model predictions."""
    data = load_json(DATA_FILES["predictions"])
    return {
        "endpoint": "predictions",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "source": str(DATA_FILES["predictions"]),
        "data": data,
    }


def get_value_bets() -> dict:
    """Get current value bets."""
    data = load_json(DATA_FILES["value-bets"])
    return {
        "endpoint": "value-bets",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "source": str(DATA_FILES["value-bets"]),
        "data": data,
    }


def get_trading_floor() -> dict:
    """Get Trading Floor v4 state."""
    data = load_json(DATA_FILES["trading-floor"])
    # Extract leaderboard summary
    summary = None
    if isinstance(data, dict) and "leaderboard" in data:
        lb = data["leaderboard"]
        summary = {
            "traders": len(lb),
            "leader": lb[0].get("name", "?") if lb else "?",
            "leader_roi": lb[0].get("nba_roi_pct", 0) if lb else 0,
            "iteration": data.get("iteration", "?"),
            "generation": data.get("generation", "?"),
        }
    return {
        "endpoint": "trading-floor",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "source": str(DATA_FILES["trading-floor"]),
        "summary": summary,
        "data": data,
    }


def get_evolution() -> dict:
    """Get evolution fleet status from infra + health files."""
    infra = load_json(DATA_FILES["infra"])
    health = load_json(DATA_FILES["health"])

    islands = {}
    # Parse from infra-status
    if isinstance(infra, dict) and "hf_spaces" in infra:
        hf_raw = infra["hf_spaces"]
        for key, val in hf_raw.items():
            if key.startswith("S1"):
                sid = key.split("_")[0]
                islands[sid] = {
                    "role": HF_SPACES.get(sid, {}).get("role", "?"),
                    "url": HF_SPACES.get(sid, {}).get("url", "?"),
                    "status": val.get("status", "?") if isinstance(val, dict) else str(val),
                    "brier": val.get("brier", "?") if isinstance(val, dict) else "?",
                    "generation": val.get("gen", "?") if isinstance(val, dict) else "?",
                }

    # Fill from agent-health if missing
    if isinstance(health, dict) and "projects" in health:
        nba_spaces = health.get("projects", {}).get("nba", {}).get("spaces", {})
        for sid, sdata in nba_spaces.items():
            if sid not in islands and isinstance(sdata, dict):
                islands[sid] = {
                    "role": HF_SPACES.get(sid, {}).get("role", "?"),
                    "url": HF_SPACES.get(sid, {}).get("url", "?"),
                    "status": sdata.get("status", "?"),
                    "brier": sdata.get("brier", "?"),
                    "generation": sdata.get("generation", "?"),
                    "model": sdata.get("model", "?"),
                }

    # Find best
    best_brier = 999.0
    best_island = ""
    for sid, idata in islands.items():
        try:
            b = float(idata.get("brier", 999))
            if b < best_brier:
                best_brier = b
                best_island = sid
        except (ValueError, TypeError):
            pass

    return {
        "endpoint": "evolution",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "islands": islands,
        "best": {"island": best_island, "brier": best_brier} if best_brier < 999 else None,
        "total_islands": len(islands),
    }


def get_bankroll() -> dict:
    """Get bankroll state."""
    bank = load_json(DATA_FILES["bankroll"])
    quant = load_json(DATA_FILES["quant"])
    return {
        "endpoint": "bankroll",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "bankroll": bank,
        "quant_summary": quant,
    }


def get_quant() -> dict:
    """Get quant summary."""
    data = load_json(DATA_FILES["quant"])
    return {
        "endpoint": "quant",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "data": data,
    }


def get_health() -> dict:
    """Get system health overview."""
    health = load_json(DATA_FILES["health"])
    infra = load_json(DATA_FILES["infra"])

    # Compute overall status
    overall = "UNKNOWN"
    if isinstance(infra, dict) and "summary" in infra:
        s = infra["summary"]
        if s.get("failed", 0) == 0:
            overall = "HEALTHY"
        elif s.get("failed", 0) > 0:
            overall = "DEGRADED"

    return {
        "endpoint": "health",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "overall": overall,
        "infra": infra,
        "agent_health": health,
    }


def get_all() -> dict:
    """Get everything — full terminal state."""
    return {
        "endpoint": "all",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "version": "nomos42-bloomberg-v1.0",
        "odds": get_odds(),
        "predictions": get_predictions(),
        "value_bets": get_value_bets(),
        "trading_floor": get_trading_floor(),
        "evolution": get_evolution(),
        "bankroll": get_bankroll(),
        "health": get_health(),
    }


# ── HTTP Handler ───────────────────────────────────────────────────────────

ROUTES = {
    "/api/odds": get_odds,
    "/api/predictions": get_predictions,
    "/api/value-bets": get_value_bets,
    "/api/trading-floor": get_trading_floor,
    "/api/evolution": get_evolution,
    "/api/bankroll": get_bankroll,
    "/api/quant": get_quant,
    "/api/health": get_health,
    "/api/all": get_all,
}


class BloombergHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Bloomberg API."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Root — show API index
        if path in ("", "/", "/api"):
            self._send_json({
                "name": "Nomos42 Bloomberg API",
                "version": "1.0",
                "description": "NBA Betting Intelligence REST API",
                "endpoints": list(ROUTES.keys()),
                "docs": "GET any endpoint above for JSON data",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            })
            return

        # Route matching
        handler = ROUTES.get(path)
        if handler:
            try:
                data = handler()
                self._send_json(data)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
        else:
            self._send_json({
                "error": "Not found",
                "path": path,
                "available": list(ROUTES.keys()),
            }, status=404)

    def _send_json(self, data: dict, status: int = 200):
        """Send a JSON response with CORS headers."""
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Powered-By", "Nomos42 Bloomberg")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """Custom log format."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        sys.stderr.write(f"[{ts}] {args[0]}\n")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Nomos42 Bloomberg API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8042, help="Port (default: 8042)")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), BloombergHandler)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║          Nomos42 Bloomberg API Server v1.0               ║
╠══════════════════════════════════════════════════════════╣
║  Listening: http://{args.host}:{args.port}                       ║
║  Data dir:  {str(DATA_DIR)[:45]:<45s} ║
║                                                          ║
║  Endpoints:                                              ║
║    GET /api/odds           Latest NBA odds               ║
║    GET /api/predictions    Model predictions              ║
║    GET /api/value-bets     Value bets                     ║
║    GET /api/trading-floor  Trading Floor v4               ║
║    GET /api/evolution      6-island fleet                 ║
║    GET /api/bankroll       Bankroll & P&L                 ║
║    GET /api/quant          Quant summary                  ║
║    GET /api/health         System health                  ║
║    GET /api/all            Everything                     ║
║                                                          ║
║  Press Ctrl+C to stop                                    ║
╚══════════════════════════════════════════════════════════╝
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
