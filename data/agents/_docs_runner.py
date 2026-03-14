#!/usr/bin/env python3
"""Docs agent runner — auto-generated. Watches for agent completion markers
and updates data/health-status.json accordingly."""
import socket
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

import os, sys, signal, time, json
import urllib.request, urllib.error
from datetime import datetime, timezone

REPO_ROOT = '/home/termius/mon-ipad'
ENV_FILE = '/home/termius/mon-ipad/.env.local'
LOG_FILE = '/home/termius/mon-ipad/logs/agents/docs.log'
PID_FILE = '/home/termius/mon-ipad/data/agents/docs.pid'
HEALTH_FILE = '/home/termius/mon-ipad/data/health-status.json'
MARKER_DIR = os.path.join(REPO_ROOT, "data", "agents")
E5_HOST = 'https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io'

running = True
def handle_term(signum, frame):
    global running
    running = False
signal.signal(signal.SIGTERM, handle_term)
signal.signal(signal.SIGINT, handle_term)

def load_env():
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            eq = line.find("=")
            if eq < 1:
                continue
            k = line[:eq].strip()
            v = line[eq+1:].strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1]
            os.environ[k] = v

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def check_space(url, name):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"name": name, "url": url, "status": "UP"}
    except Exception:
        return {"name": name, "url": url, "status": "DOWN"}

def get_vector_count():
    api_key = os.environ.get("PINECONE_API_KEY", "")
    if not api_key:
        return -1
    url = f"{E5_HOST}/describe_index_stats"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Api-Key", api_key)
    req.add_header("Content-Type", "application/json")
    req.data = b"{}"
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("totalVectorCount", data.get("totalRecordCount", 0))
    except Exception:
        return -1

def get_agent_statuses():
    agents = {}
    for name in ["monitor", "eval", "ingest", "pipeline", "docs"]:
        pf = os.path.join(MARKER_DIR, f"{name}.pid")
        pid = None
        alive = False
        if os.path.exists(pf):
            try:
                with open(pf, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)
                alive = True
            except (ValueError, ProcessLookupError, PermissionError, OSError):
                alive = False
        agents[name] = {"pid": pid, "alive": alive}
    return agents

def update_health():
    log("Updating health-status.json...")

    # Check HF Spaces
    spaces_config = [
        ("S1", "https://lbjlincoln-nomos-rag-engine.hf.space"),
        ("S3", "https://lbjlincoln-nomos-rag-engine-3.hf.space"),
        ("S5", "https://lbjlincoln-nomos-rag-engine-5.hf.space"),
        ("S9", "https://lbjlincoln-nomos-rag-engine-9.hf.space"),
    ]
    spaces = []
    for name, url in spaces_config:
        spaces.append(check_space(url, name))

    # E5 vectors
    e5_count = get_vector_count()

    # Agent statuses
    agent_info = get_agent_statuses()

    # Read pipeline marker if exists
    pipeline_marker = os.path.join(MARKER_DIR, "_pipeline_done.marker")
    pipeline_last = None
    if os.path.exists(pipeline_marker):
        try:
            with open(pipeline_marker, "r") as f:
                pipeline_last = json.loads(f.read())
        except Exception:
            pass

    # Build health status
    health = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "spaces": spaces,
        "e5_vectors": e5_count,
        "agents": {
            name: {
                "pid": info["pid"],
                "status": "RUNNING" if info["alive"] else "STOPPED",
            }
            for name, info in agent_info.items()
        },
    }

    if pipeline_last:
        health["last_pipeline_check"] = pipeline_last

    # Read existing health file and preserve pipeline stats if present
    if os.path.exists(HEALTH_FILE):
        try:
            with open(HEALTH_FILE, "r") as f:
                existing = json.loads(f.read())
            if "pipelines" in existing:
                health["pipelines"] = existing["pipelines"]
        except Exception:
            pass

    with open(HEALTH_FILE, "w") as f:
        json.dump(health, f, indent=2)
        f.write("\n")

    spaces_up = sum(1 for s in spaces if s["status"] == "UP")
    log(f"Health updated: {spaces_up}/{len(spaces)} spaces UP, E5={e5_count}")

load_env()
log("Docs agent STARTED")

with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

# Track marker mtimes to detect changes
MARKERS = ["_eval_done.marker", "_ingest_done.marker", "_pipeline_done.marker"]
last_mtimes = {}
for m in MARKERS:
    path = os.path.join(MARKER_DIR, m)
    if os.path.exists(path):
        last_mtimes[m] = os.path.getmtime(path)
    else:
        last_mtimes[m] = 0

POLL_INTERVAL = 30  # Check for markers every 30s
FORCE_UPDATE_INTERVAL = 300  # Force update every 5min regardless

last_force_update = time.time()

# Initial update
update_health()

while running:
    time.sleep(POLL_INTERVAL)
    if not running:
        break

    now = time.time()
    trigger = False

    # Check if any marker files changed
    for m in MARKERS:
        path = os.path.join(MARKER_DIR, m)
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            if mtime > last_mtimes.get(m, 0):
                log(f"Marker {m} updated, triggering health update")
                last_mtimes[m] = mtime
                trigger = True

    # Force update periodically
    if now - last_force_update >= FORCE_UPDATE_INTERVAL:
        trigger = True
        last_force_update = now

    if trigger:
        try:
            update_health()
        except Exception as e:
            log(f"ERROR updating health: {e}")

log("Docs agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
