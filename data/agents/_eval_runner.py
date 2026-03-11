#!/usr/bin/env python3
"""Eval agent runner — auto-generated."""
import socket
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

import os, sys, signal, subprocess, time
from datetime import datetime, timezone

REPO_ROOT = '/home/termius/mon-ipad'
ENV_FILE = '/home/termius/mon-ipad/.env.local'
LOG_FILE = '/home/termius/mon-ipad/logs/agents/eval.log'
PID_FILE = '/home/termius/mon-ipad/data/agents/eval.pid'
HEALTH_FILE = '/home/termius/mon-ipad/data/health-status.json'

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
log("Eval agent STARTED")

with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

EVAL_INTERVAL = 1800  # 30 minutes between cycles
cmd = [
    sys.executable,
    os.path.join(REPO_ROOT, "eval", "quick-test.py"),
    "--proxy",
    "--pipelines", "standard,graph",
    "--questions", "10",
]

cycle = 0
while running:
    cycle += 1
    log(f"=== Eval cycle {cycle} starting ===")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )
        stdout_data, _ = proc.communicate(timeout=600)  # 10min max per eval
        output = stdout_data.decode("utf-8", errors="replace")
        # Write output to log
        with open(LOG_FILE, "a") as f:
            f.write(output)
            f.write("\n")
        rc = proc.returncode
        log(f"Eval cycle {cycle} finished, exit code {rc}")

        # Signal docs agent by writing a marker
        marker = os.path.join(REPO_ROOT, "data", "agents", "_eval_done.marker")
        with open(marker, "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())

    except subprocess.TimeoutExpired:
        log(f"Eval cycle {cycle} TIMEOUT (600s), killing")
        proc.kill()
        proc.wait()
    except Exception as e:
        log(f"ERROR in eval cycle {cycle}: {e}")

    if not running:
        break

    log(f"Sleeping {EVAL_INTERVAL}s until next eval cycle...")
    elapsed = 0
    while running and elapsed < EVAL_INTERVAL:
        time.sleep(5)
        elapsed += 5

log("Eval agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
