#!/usr/bin/env python3
"""Monitor agent runner — auto-generated."""
import socket
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

import os, sys, signal, subprocess, time
from datetime import datetime, timezone

REPO_ROOT = '/home/termius/mon-ipad'
ENV_FILE = '/home/termius/mon-ipad/.env.local'
LOG_FILE = '/home/termius/mon-ipad/logs/agents/monitor.log'
PID_FILE = '/home/termius/mon-ipad/data/agents/monitor.pid'

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

load_env()
log("Monitor agent STARTED")

# Write our PID
with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

INTERVAL = 300  # 5 minutes
cmd = [sys.executable, os.path.join(REPO_ROOT, "ops", "monitor.py"), "--loop", str(INTERVAL)]

while running:
    log(f"Running monitor.py --loop {INTERVAL}")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            stdout=open(LOG_FILE, "a"),
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )
        # monitor.py --loop handles its own looping, so we just wait
        while running and proc.poll() is None:
            time.sleep(2)
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        rc = proc.returncode
        log(f"monitor.py exited with code {rc}")
    except Exception as e:
        log(f"ERROR running monitor.py: {e}")
    if running:
        log("Restarting monitor.py in 30s...")
        for _ in range(15):
            if not running:
                break
            time.sleep(2)

log("Monitor agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
