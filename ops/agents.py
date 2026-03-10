#!/usr/bin/env python3
"""
Master Agent Launcher — Entry point for all 5 specialized agents.

Manages lifecycle of background agents: monitor, eval, ingest, pipeline, docs.
Each agent runs as a subprocess with PID tracking, log capture, and graceful shutdown.

Usage:
  python3 ops/agents.py launch all                  # Start all agents
  python3 ops/agents.py launch monitor              # Start single agent
  python3 ops/agents.py launch eval ingest           # Start multiple agents
  python3 ops/agents.py status                       # Show all agent statuses
  python3 ops/agents.py stop all                     # Stop all agents
  python3 ops/agents.py stop monitor                 # Stop single agent
  python3 ops/agents.py logs monitor                 # Show recent logs
  python3 ops/agents.py logs eval --lines 100        # Show last 100 lines
"""

# ─── IPv4 monkey-patch (GCP VM has broken IPv6) ─────────────────────────
import socket
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ─── Paths ──────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PID_DIR = os.path.join(REPO_ROOT, "data", "agents")
LOG_DIR = os.path.join(REPO_ROOT, "logs", "agents")
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")
HEALTH_FILE = os.path.join(REPO_ROOT, "data", "health-status.json")

# Pinecone E5 index for vector count checks
E5_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
E5_TARGET = 100_000

# ─── Ensure directories exist ──────────────────────────────────────────
os.makedirs(PID_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ─── Agent Definitions ─────────────────────────────────────────────────
AGENT_NAMES = ["monitor", "eval", "ingest", "pipeline", "docs"]


def load_env():
    """Load .env.local into os.environ, parsing 'export KEY=VALUE' lines."""
    if not os.path.exists(ENV_FILE):
        print(f"[WARN] {ENV_FILE} not found, skipping env load")
        return
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Handle 'export KEY=VALUE' and 'KEY=VALUE'
            if line.startswith("export "):
                line = line[7:]
            eq_idx = line.find("=")
            if eq_idx < 1:
                continue
            key = line[:eq_idx].strip()
            value = line[eq_idx + 1:].strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ[key] = value


def pid_file(name):
    return os.path.join(PID_DIR, f"{name}.pid")


def log_file(name):
    return os.path.join(LOG_DIR, f"{name}.log")


def read_pid(name):
    """Read PID from file, return int or None."""
    pf = pid_file(name)
    if not os.path.exists(pf):
        return None
    try:
        with open(pf, "r") as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def write_pid(name, pid):
    with open(pid_file(name), "w") as f:
        f.write(str(pid))


def remove_pid(name):
    pf = pid_file(name)
    if os.path.exists(pf):
        os.remove(pf)


def is_alive(pid):
    """Check if a process with given PID is running."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def agent_status(name):
    """Return (pid, alive) tuple for an agent."""
    pid = read_pid(name)
    alive = is_alive(pid)
    return pid, alive


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_msg(name, msg):
    """Append a timestamped message to agent log file."""
    lf = log_file(name)
    line = f"[{timestamp()}] {msg}\n"
    with open(lf, "a") as f:
        f.write(line)


# ─── E5 Vector Count ───────────────────────────────────────────────────
def get_e5_vector_count():
    """Query Pinecone E5 index stats to get total vector count."""
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
        return -1


# ─── Agent Runner Functions ────────────────────────────────────────────
# Each function is the main loop for an agent. They run in a child process
# (forked via subprocess) and loop until SIGTERM.

def _write_agent_wrapper(name, code):
    """Write a temporary Python wrapper script for an agent."""
    wrapper_path = os.path.join(PID_DIR, f"_{name}_runner.py")
    with open(wrapper_path, "w") as f:
        f.write(code)
    return wrapper_path


def build_monitor_script():
    """Build the monitor agent runner script."""
    return f'''#!/usr/bin/env python3
"""Monitor agent runner — auto-generated."""
import socket
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

import os, sys, signal, subprocess, time
from datetime import datetime, timezone

REPO_ROOT = {REPO_ROOT!r}
ENV_FILE = {ENV_FILE!r}
LOG_FILE = {log_file("monitor")!r}
PID_FILE = {pid_file("monitor")!r}

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
        f.write(f"[{{ts}}] {{msg}}\\n")

load_env()
log("Monitor agent STARTED")

# Write our PID
with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

INTERVAL = 300  # 5 minutes
cmd = [sys.executable, os.path.join(REPO_ROOT, "ops", "monitor.py"), "--loop", str(INTERVAL)]

while running:
    log(f"Running monitor.py --loop {{INTERVAL}}")
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
        log(f"monitor.py exited with code {{rc}}")
    except Exception as e:
        log(f"ERROR running monitor.py: {{e}}")
    if running:
        log("Restarting monitor.py in 30s...")
        for _ in range(15):
            if not running:
                break
            time.sleep(2)

log("Monitor agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
'''


def build_eval_script():
    """Build the eval agent runner script."""
    return f'''#!/usr/bin/env python3
"""Eval agent runner — auto-generated."""
import socket
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

import os, sys, signal, subprocess, time
from datetime import datetime, timezone

REPO_ROOT = {REPO_ROOT!r}
ENV_FILE = {ENV_FILE!r}
LOG_FILE = {log_file("eval")!r}
PID_FILE = {pid_file("eval")!r}
HEALTH_FILE = {HEALTH_FILE!r}

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
        f.write(f"[{{ts}}] {{msg}}\\n")

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
    log(f"=== Eval cycle {{cycle}} starting ===")
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
            f.write("\\n")
        rc = proc.returncode
        log(f"Eval cycle {{cycle}} finished, exit code {{rc}}")

        # Signal docs agent by writing a marker
        marker = os.path.join(REPO_ROOT, "data", "agents", "_eval_done.marker")
        with open(marker, "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())

    except subprocess.TimeoutExpired:
        log(f"Eval cycle {{cycle}} TIMEOUT (600s), killing")
        proc.kill()
        proc.wait()
    except Exception as e:
        log(f"ERROR in eval cycle {{cycle}}: {{e}}")

    if not running:
        break

    log(f"Sleeping {{EVAL_INTERVAL}}s until next eval cycle...")
    elapsed = 0
    while running and elapsed < EVAL_INTERVAL:
        time.sleep(5)
        elapsed += 5

log("Eval agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
'''


def build_ingest_script():
    """Build the ingest agent runner script."""
    return f'''#!/usr/bin/env python3
"""Ingest agent runner — auto-generated."""
import socket
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

import os, sys, signal, subprocess, time, json
import urllib.request, urllib.error
from datetime import datetime, timezone

REPO_ROOT = {REPO_ROOT!r}
ENV_FILE = {ENV_FILE!r}
LOG_FILE = {log_file("ingest")!r}
PID_FILE = {pid_file("ingest")!r}
E5_HOST = {E5_HOST!r}
E5_TARGET = {E5_TARGET}

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
        f.write(f"[{{ts}}] {{msg}}\\n")

def get_vector_count():
    api_key = os.environ.get("PINECONE_API_KEY", "")
    if not api_key:
        return -1
    url = f"{{E5_HOST}}/describe_index_stats"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Api-Key", api_key)
    req.add_header("Content-Type", "application/json")
    req.data = b"{{}}"
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("totalVectorCount", data.get("totalRecordCount", 0))
    except Exception as e:
        log(f"Failed to get vector count: {{e}}")
        return -1

load_env()
log("Ingest agent STARTED")

with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

INGEST_INTERVAL = 3600  # 1 hour between cycles

cycle = 0
while running:
    cycle += 1
    log(f"=== Ingest cycle {{cycle}} starting ===")

    # Check current E5 vector count
    count = get_vector_count()
    log(f"E5 vector count: {{count}} (target: {{E5_TARGET}})")

    if count >= 0 and count >= E5_TARGET:
        log(f"E5 at {{count}} >= {{E5_TARGET}} target. Skipping ingestion.")
    else:
        if count < 0:
            log("Could not read vector count, running ingestion anyway")
        else:
            log(f"E5 at {{count}} < {{E5_TARGET}}, starting fast-ingest...")

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
                f.write("\\n")
            rc = proc.returncode
            log(f"fast-ingest finished, exit code {{rc}}")

            # Signal docs agent
            marker = os.path.join(REPO_ROOT, "data", "agents", "_ingest_done.marker")
            with open(marker, "w") as f:
                f.write(datetime.now(timezone.utc).isoformat())

        except subprocess.TimeoutExpired:
            log(f"Ingest cycle {{cycle}} TIMEOUT (3000s), killing")
            proc.kill()
            proc.wait()
        except Exception as e:
            log(f"ERROR in ingest cycle {{cycle}}: {{e}}")

    if not running:
        break

    log(f"Sleeping {{INGEST_INTERVAL}}s until next ingest cycle...")
    elapsed = 0
    while running and elapsed < INGEST_INTERVAL:
        time.sleep(5)
        elapsed += 5

log("Ingest agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
'''


def build_pipeline_script():
    """Build the pipeline agent runner script."""
    return f'''#!/usr/bin/env python3
"""Pipeline agent runner — auto-generated."""
import socket
_orig = socket.getaddrinfo
def _ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4

import os, sys, signal, subprocess, time, json
import urllib.request, urllib.error
from datetime import datetime, timezone

REPO_ROOT = {REPO_ROOT!r}
ENV_FILE = {ENV_FILE!r}
LOG_FILE = {log_file("pipeline")!r}
PID_FILE = {pid_file("pipeline")!r}

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
        f.write(f"[{{ts}}] {{msg}}\\n")

# Smoke test: hit each pipeline with a simple question
SMOKE_TESTS = {{
    "standard": {{
        "path": "/webhook/rag-multi-index-v3",
        "payload": {{"question": "Quel est le taux directeur de la BCE en 2024?", "sector": "finance"}},
    }},
    "graph": {{
        "path": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "payload": {{"question": "Quelles entites sont liees au secteur BTP?", "sector": "btp"}},
    }},
    "quantitative": {{
        "path": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "payload": {{"question": "Quel est le chiffre d affaires total du secteur finance?", "sector": "finance"}},
    }},
    "orchestrator": {{
        "path": "/webhook/orchestrator-v2",
        "payload": {{"question": "Quels sont les principaux risques du secteur BTP?", "sector": "btp"}},
    }},
}}

def run_smoke(host, name, test):
    url = host + test["path"]
    payload = json.dumps(test["payload"]).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else {{}}
            answer = ""
            if isinstance(data, dict):
                answer = data.get("answer", data.get("response", data.get("output", "")))
            elif isinstance(data, list) and data:
                answer = data[0].get("answer", data[0].get("output", "")) if isinstance(data[0], dict) else str(data[0])
            if answer and len(str(answer)) > 10:
                return True, str(answer)[:200]
            else:
                return False, f"Empty/short answer: {{str(data)[:200]}}"
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
    log(f"=== Pipeline smoke cycle {{cycle}} ===")

    failures = []
    for name, test in SMOKE_TESTS.items():
        ok, detail = run_smoke(N8N_HOST, name, test)
        status_str = "PASS" if ok else "FAIL"
        log(f"  {{name}}: {{status_str}} — {{detail[:120]}}")
        if not ok:
            failures.append(name)

    if failures:
        log(f"FAILURES detected: {{', '.join(failures)}}. Running monitor --errors-only...")
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
                f.write("\\n")
            log(f"monitor --errors-only finished, exit code {{proc.returncode}}")
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            log("monitor --errors-only TIMEOUT")
        except Exception as e:
            log(f"ERROR running monitor: {{e}}")

        # Signal docs agent
        marker = os.path.join(REPO_ROOT, "data", "agents", "_pipeline_done.marker")
        with open(marker, "w") as f:
            f.write(json.dumps({{"cycle": cycle, "failures": failures, "ts": datetime.now(timezone.utc).isoformat()}}))
    else:
        log(f"All {{len(SMOKE_TESTS)}} pipelines PASS")

        marker = os.path.join(REPO_ROOT, "data", "agents", "_pipeline_done.marker")
        with open(marker, "w") as f:
            f.write(json.dumps({{"cycle": cycle, "failures": [], "ts": datetime.now(timezone.utc).isoformat()}}))

    if not running:
        break

    log(f"Sleeping {{INTERVAL}}s until next pipeline check...")
    elapsed = 0
    while running and elapsed < INTERVAL:
        time.sleep(5)
        elapsed += 5

log("Pipeline agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
'''


def build_docs_script():
    """Build the docs agent runner script."""
    return f'''#!/usr/bin/env python3
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

REPO_ROOT = {REPO_ROOT!r}
ENV_FILE = {ENV_FILE!r}
LOG_FILE = {log_file("docs")!r}
PID_FILE = {pid_file("docs")!r}
HEALTH_FILE = {HEALTH_FILE!r}
MARKER_DIR = os.path.join(REPO_ROOT, "data", "agents")
E5_HOST = {E5_HOST!r}

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
        f.write(f"[{{ts}}] {{msg}}\\n")

def check_space(url, name):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {{"name": name, "url": url, "status": "UP"}}
    except Exception:
        return {{"name": name, "url": url, "status": "DOWN"}}

def get_vector_count():
    api_key = os.environ.get("PINECONE_API_KEY", "")
    if not api_key:
        return -1
    url = f"{{E5_HOST}}/describe_index_stats"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Api-Key", api_key)
    req.add_header("Content-Type", "application/json")
    req.data = b"{{}}"
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("totalVectorCount", data.get("totalRecordCount", 0))
    except Exception:
        return -1

def get_agent_statuses():
    agents = {{}}
    for name in ["monitor", "eval", "ingest", "pipeline", "docs"]:
        pf = os.path.join(MARKER_DIR, f"{{name}}.pid")
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
        agents[name] = {{"pid": pid, "alive": alive}}
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
    health = {{
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "spaces": spaces,
        "e5_vectors": e5_count,
        "agents": {{
            name: {{
                "pid": info["pid"],
                "status": "RUNNING" if info["alive"] else "STOPPED",
            }}
            for name, info in agent_info.items()
        }},
    }}

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
        f.write("\\n")

    spaces_up = sum(1 for s in spaces if s["status"] == "UP")
    log(f"Health updated: {{spaces_up}}/{{len(spaces)}} spaces UP, E5={{e5_count}}")

load_env()
log("Docs agent STARTED")

with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

# Track marker mtimes to detect changes
MARKERS = ["_eval_done.marker", "_ingest_done.marker", "_pipeline_done.marker"]
last_mtimes = {{}}
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
                log(f"Marker {{m}} updated, triggering health update")
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
            log(f"ERROR updating health: {{e}}")

log("Docs agent STOPPED")
if os.path.exists(PID_FILE):
    os.remove(PID_FILE)
'''


# ─── Agent script builders map ─────────────────────────────────────────
AGENT_BUILDERS = {
    "monitor": build_monitor_script,
    "eval": build_eval_script,
    "ingest": build_ingest_script,
    "pipeline": build_pipeline_script,
    "docs": build_docs_script,
}


# ─── Launch / Stop / Status ────────────────────────────────────────────

def launch_agent(name):
    """Launch a single agent as a background subprocess."""
    if name not in AGENT_NAMES:
        print(f"[ERROR] Unknown agent: {name}. Available: {', '.join(AGENT_NAMES)}")
        return False

    pid, alive = agent_status(name)
    if alive:
        print(f"[SKIP] Agent '{name}' already running (PID {pid})")
        return True

    # Clean stale PID file
    if pid is not None:
        remove_pid(name)

    # Generate runner script
    builder = AGENT_BUILDERS[name]
    script_code = builder()
    wrapper_path = _write_agent_wrapper(name, script_code)

    # Launch subprocess
    lf = log_file(name)
    log_handle = open(lf, "a")
    log_handle.write(f"\n[{timestamp()}] === Agent '{name}' launching ===\n")
    log_handle.flush()

    proc = subprocess.Popen(
        [sys.executable, wrapper_path],
        cwd=REPO_ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
        start_new_session=True,  # Detach from parent process group
    )

    write_pid(name, proc.pid)
    print(f"[OK] Agent '{name}' launched (PID {proc.pid}), log: {lf}")
    return True


def stop_agent(name):
    """Stop a single agent by sending SIGTERM."""
    if name not in AGENT_NAMES:
        print(f"[ERROR] Unknown agent: {name}")
        return False

    pid, alive = agent_status(name)
    if not alive:
        print(f"[SKIP] Agent '{name}' not running")
        remove_pid(name)
        return True

    print(f"[STOP] Sending SIGTERM to '{name}' (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print(f"[OK] Agent '{name}' already exited")
        remove_pid(name)
        return True

    # Wait up to 15 seconds for graceful shutdown
    for i in range(30):
        if not is_alive(pid):
            break
        time.sleep(0.5)

    if is_alive(pid):
        print(f"[WARN] Agent '{name}' did not exit, sending SIGKILL...")
        try:
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
        except ProcessLookupError:
            pass

    remove_pid(name)
    print(f"[OK] Agent '{name}' stopped")
    return True


def show_status():
    """Display status of all agents."""
    print("=" * 65)
    print(f"  AGENT STATUS — {timestamp()}")
    print("=" * 65)
    print(f"  {'Agent':<12} {'Status':<10} {'PID':<10} {'Log Size':<12} {'Log File'}")
    print("-" * 65)

    for name in AGENT_NAMES:
        pid, alive = agent_status(name)
        status = "RUNNING" if alive else "STOPPED"
        pid_str = str(pid) if pid else "-"
        lf = log_file(name)
        if os.path.exists(lf):
            size = os.path.getsize(lf)
            if size > 1_000_000:
                size_str = f"{size / 1_000_000:.1f}MB"
            elif size > 1000:
                size_str = f"{size / 1000:.1f}KB"
            else:
                size_str = f"{size}B"
        else:
            size_str = "-"

        status_color = status
        print(f"  {name:<12} {status_color:<10} {pid_str:<10} {size_str:<12} {lf}")

    print("=" * 65)

    # Show E5 vector count if env loaded
    load_env()
    count = get_e5_vector_count()
    if count >= 0:
        pct = (count / E5_TARGET) * 100
        print(f"\n  E5 Vectors: {count:,} / {E5_TARGET:,} ({pct:.1f}%)")

    # Show health file age
    if os.path.exists(HEALTH_FILE):
        age = time.time() - os.path.getmtime(HEALTH_FILE)
        if age < 60:
            age_str = f"{age:.0f}s ago"
        elif age < 3600:
            age_str = f"{age / 60:.0f}min ago"
        else:
            age_str = f"{age / 3600:.1f}h ago"
        print(f"  Health file: {HEALTH_FILE} (updated {age_str})")
    print()


def show_logs(name, lines=50):
    """Show recent log lines for an agent."""
    if name not in AGENT_NAMES:
        print(f"[ERROR] Unknown agent: {name}. Available: {', '.join(AGENT_NAMES)}")
        return

    lf = log_file(name)
    if not os.path.exists(lf):
        print(f"[INFO] No log file found for agent '{name}' at {lf}")
        return

    print(f"=== Last {lines} lines of {lf} ===\n")

    # Read last N lines efficiently
    try:
        with open(lf, "rb") as f:
            # Seek to end
            f.seek(0, 2)
            file_size = f.tell()
            if file_size == 0:
                print("(empty log)")
                return

            # Read chunks from end to find enough newlines
            block_size = 8192
            data = b""
            pos = file_size
            found_lines = 0

            while pos > 0 and found_lines <= lines:
                read_size = min(block_size, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size)
                data = chunk + data
                found_lines = data.count(b"\n")

        # Split and take last N lines
        all_lines = data.decode("utf-8", errors="replace").split("\n")
        tail = all_lines[-(lines + 1):]
        for line in tail:
            print(line)

    except Exception as e:
        print(f"[ERROR] Failed to read log: {e}")


# ─── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Master Agent Launcher — manage background agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ops/agents.py launch all          Start all 5 agents
  python3 ops/agents.py launch monitor      Start monitor agent only
  python3 ops/agents.py launch eval ingest  Start eval and ingest agents
  python3 ops/agents.py status              Show status of all agents
  python3 ops/agents.py stop all            Stop all agents
  python3 ops/agents.py stop pipeline       Stop pipeline agent only
  python3 ops/agents.py logs eval           Show last 50 lines of eval log
  python3 ops/agents.py logs monitor -n 200 Show last 200 lines
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # launch
    launch_parser = subparsers.add_parser("launch", help="Launch agents")
    launch_parser.add_argument(
        "agents", nargs="+",
        help=f"Agent names to launch, or 'all'. Available: {', '.join(AGENT_NAMES)}",
    )

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop agents")
    stop_parser.add_argument(
        "agents", nargs="+",
        help=f"Agent names to stop, or 'all'. Available: {', '.join(AGENT_NAMES)}",
    )

    # status
    subparsers.add_parser("status", help="Show status of all agents")

    # logs
    logs_parser = subparsers.add_parser("logs", help="Show recent logs for an agent")
    logs_parser.add_argument("agent", help="Agent name")
    logs_parser.add_argument("-n", "--lines", type=int, default=50, help="Number of lines (default 50)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Load env for all commands
    load_env()

    if args.command == "launch":
        names = AGENT_NAMES if "all" in args.agents else args.agents
        # Validate all names first
        for name in names:
            if name != "all" and name not in AGENT_NAMES:
                print(f"[ERROR] Unknown agent: {name}. Available: {', '.join(AGENT_NAMES)}")
                sys.exit(1)

        print(f"\n  Launching {len(names)} agent(s): {', '.join(names)}\n")
        success = 0
        for name in names:
            if launch_agent(name):
                success += 1

        print(f"\n  {success}/{len(names)} agents launched.\n")
        # Brief pause then show status
        time.sleep(1)
        show_status()

    elif args.command == "stop":
        names = AGENT_NAMES if "all" in args.agents else args.agents
        for name in names:
            if name != "all" and name not in AGENT_NAMES:
                print(f"[ERROR] Unknown agent: {name}. Available: {', '.join(AGENT_NAMES)}")
                sys.exit(1)

        print(f"\n  Stopping {len(names)} agent(s): {', '.join(names)}\n")
        for name in names:
            stop_agent(name)

        print()
        time.sleep(1)
        show_status()

    elif args.command == "status":
        show_status()

    elif args.command == "logs":
        show_logs(args.agent, args.lines)


if __name__ == "__main__":
    main()
