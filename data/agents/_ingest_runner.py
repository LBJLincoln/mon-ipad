#!/usr/bin/env python3
"""Ingest agent runner — auto-generated."""
import socket
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

import os, sys, signal, subprocess, time, json
import urllib.request, urllib.error
from datetime import datetime, timezone

REPO_ROOT = '/home/termius/mon-ipad'
ENV_FILE = '/home/termius/mon-ipad/.env.local'
LOG_FILE = '/home/termius/mon-ipad/logs/agents/ingest.log'
PID_FILE = '/home/termius/mon-ipad/data/agents/ingest.pid'
E5_HOST = 'https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io'
E5_TARGET = 100000

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
    except Exception as e:
        log(f"Failed to get vector count: {e}")
        return -1

load_env()
log("Ingest agent STARTED")

with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

INGEST_INTERVAL = 3600  # 1 hour between cycles

cycle = 0
while running:
    cycle += 1
    log(f"=== Ingest cycle {cycle} starting ===")

    # Check current E5 vector count
    count = get_vector_count()
    log(f"E5 vector count: {count} (target: {E5_TARGET})")

    if count >= 0 and count >= E5_TARGET:
        log(f"E5 at {count} >= {E5_TARGET} target. Skipping ingestion.")
    else:
        if count < 0:
            log("Could not read vector count, running ingestion anyway")
        else:
            log(f"E5 at {count} < {E5_TARGET}, starting fast-ingest...")

        cmd = [
            sys.executable,
            os.path.join(REPO_ROOT, "ops", "fast-ingest.py"),
            "--all",
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
            )
            # Wait up to 50 min for ingestion
            stdout_data, _ = proc.communicate(timeout=3000)
            output = stdout_data.decode("utf-8", errors="replace")
            with open(LOG_FILE, "a") as f:
                f.write(output)
                f.write("\n")
            rc = proc.returncode
            log(f"fast-ingest finished, exit code {rc}")

            # Signal docs agent
            marker = os.path.join(REPO_ROOT, "data", "agents", "_ingest_done.marker")
            with open(marker, "w") as f:
                f.write(datetime.now(timezone.utc).isoformat())

        except subprocess.TimeoutExpired:
            log(f"Ingest cycle {cycle} TIMEOUT (3000s), killing")
            proc.kill()
            proc.wait()
        except Exception as e:
            log(f"ERROR in ingest cycle {cycle}: {e}")

    if not running:
        break

    log(f"Sleeping {INGEST_INTERVAL}s until next ingest cycle...")
    elapsed = 0
    while running and elapsed < INGEST_INTERVAL:
        time.sleep(5)
        elapsed += 5

log("Ingest agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
