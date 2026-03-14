#!/usr/bin/env python3
"""Pipeline agent runner — auto-generated."""
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
LOG_FILE = '/home/termius/mon-ipad/logs/agents/pipeline.log'
PID_FILE = '/home/termius/mon-ipad/data/agents/pipeline.pid'

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

# Smoke test: hit each pipeline with a simple question
SMOKE_TESTS = {
    "standard": {
        "path": "/webhook/rag-multi-index-v3",
        "payload": {"question": "Quel est le taux directeur de la BCE en 2024?", "sector": "finance"},
    },
    "graph": {
        "path": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "payload": {"question": "Quelles entites sont liees au secteur BTP?", "sector": "btp"},
    },
    "quantitative": {
        "path": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "payload": {"question": "Quel est le chiffre d affaires total du secteur finance?", "sector": "finance"},
    },
    "orchestrator": {
        "path": "/webhook/orchestrator-v2",
        "payload": {"question": "Quels sont les principaux risques du secteur BTP?", "sector": "btp"},
    },
}

def run_smoke(host, name, test):
    url = host + test["path"]
    payload = json.dumps(test["payload"]).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else {}
            answer = ""
            if isinstance(data, dict):
                answer = data.get("answer", data.get("response", data.get("output", data.get("interpretation", ""))))
            elif isinstance(data, list) and data:
                answer = data[0].get("answer", data[0].get("output", data[0].get("interpretation", ""))) if isinstance(data[0], dict) else str(data[0])
            if answer and len(str(answer)) > 10:
                return True, str(answer)[:200]
            else:
                return False, f"Empty/short answer: {str(data)[:200]}"
    except Exception as e:
        return False, str(e)[:200]

load_env()
log("Pipeline agent STARTED")

with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

INTERVAL = 900  # 15 minutes
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

cycle = 0
while running:
    cycle += 1
    log(f"=== Pipeline smoke cycle {cycle} ===")

    failures = []
    for name, test in SMOKE_TESTS.items():
        ok, detail = run_smoke(N8N_HOST, name, test)
        status_str = "PASS" if ok else "FAIL"
        log(f"  {name}: {status_str} — {detail[:120]}")
        if not ok:
            failures.append(name)

    if failures:
        log(f"FAILURES detected: {', '.join(failures)}. Running monitor --errors-only...")
        try:
            proc = subprocess.Popen(
                [sys.executable, os.path.join(REPO_ROOT, "ops", "monitor.py"), "--errors-only"],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
            )
            stdout_data, _ = proc.communicate(timeout=120)
            output = stdout_data.decode("utf-8", errors="replace")
            with open(LOG_FILE, "a") as f:
                f.write(output)
                f.write("\n")
            log(f"monitor --errors-only finished, exit code {proc.returncode}")
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            log("monitor --errors-only TIMEOUT")
        except Exception as e:
            log(f"ERROR running monitor: {e}")

        # Signal docs agent
        marker = os.path.join(REPO_ROOT, "data", "agents", "_pipeline_done.marker")
        with open(marker, "w") as f:
            f.write(json.dumps({"cycle": cycle, "failures": failures, "ts": datetime.now(timezone.utc).isoformat()}))
    else:
        log(f"All {len(SMOKE_TESTS)} pipelines PASS")

        marker = os.path.join(REPO_ROOT, "data", "agents", "_pipeline_done.marker")
        with open(marker, "w") as f:
            f.write(json.dumps({"cycle": cycle, "failures": [], "ts": datetime.now(timezone.utc).isoformat()}))

    if not running:
        break

    log(f"Sleeping {INTERVAL}s until next pipeline check...")
    elapsed = 0
    while running and elapsed < INTERVAL:
        time.sleep(5)
        elapsed += 5

log("Pipeline agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
