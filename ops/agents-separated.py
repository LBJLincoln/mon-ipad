#!/usr/bin/env python3
"""
Separated Agent System — Two independent product systems with dedicated agents.

SYSTEM 1: DATA PIPELINE (Ingestion + Enrichment + Docling)
  - Agent INGEST: Tavily → Docling → Chunking → Embeddings → Pinecone
  - Agent ENRICH: Pinecone docs → Neo4j entities + relations
  - Agent QUALITY: Monitors ingestion quality, dedup, validates chunks

SYSTEM 2: RAG PIPELINES (Query answering)
  - Agent EVAL: Continuous eval blast (all 4 pipelines × 4 sectors)
  - Agent REGRESSION: Watches accuracy trends, blocks regressions
  - Agent FIXER: Diagnoses failures, generates fix recommendations
  - Agent MONITOR: Health checks on all Spaces, pipelines, databases

Each system runs independently with its own objectives and metrics.

Usage:
  source .env.local
  python3 ops/agents-separated.py launch all          # Launch all agents
  python3 ops/agents-separated.py launch system1      # Data pipeline agents only
  python3 ops/agents-separated.py launch system2      # RAG pipeline agents only
  python3 ops/agents-separated.py status               # Show all agent status
  python3 ops/agents-separated.py stop all             # Stop all agents
"""

# ── IPv4 fix ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "agents")
os.makedirs(DATA_DIR, exist_ok=True)

ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

# ── Agent Definitions ──
SYSTEM1_AGENTS = {
    "ingest": {
        "name": "INGEST Agent",
        "system": "data_pipeline",
        "script": "ops/continuous-ingest.py",
        "args": ["--daemon", "1800"],  # 30min cycles
        "objective": "Grow E5 vectors from 78K to 100K target. Tavily→Docling→Pinecone.",
        "metrics": ["vectors_added", "docs_processed", "sectors_covered"],
        "pid_file": "ingest-system.pid",
    },
    "enrich": {
        "name": "ENRICH Agent",
        "system": "data_pipeline",
        "script": "ops/agent-ingest-feed.py",
        "args": ["--daemon", "1800"],
        "objective": "Enrich all docs with Neo4j entities. Target 95%+ enrichment rate.",
        "metrics": ["entities_created", "relations_added", "enrichment_rate"],
        "pid_file": "enrich-system.pid",
    },
    "quality": {
        "name": "QUALITY Agent",
        "system": "data_pipeline",
        "script": "eval/full-system-test.py",
        "args": ["--component", "pinecone"],
        "objective": "Monitor data quality: dedup ratio, chunk sizes, embedding coverage.",
        "metrics": ["dedup_rate", "avg_chunk_size", "coverage"],
        "pid_file": "quality-system.pid",
        "oneshot": True,
    },
}

SYSTEM2_AGENTS = {
    "eval": {
        "name": "EVAL Agent",
        "system": "rag_pipelines",
        "script": "eval/eval-blast.py",
        "args": ["--count", "20", "--loop", "600"],  # 20 questions every 10min
        "objective": "Run continuous eval across all pipelines+sectors. Track accuracy trends.",
        "metrics": ["accuracy_standard", "accuracy_graph", "accuracy_quant", "accuracy_orch"],
        "pid_file": "eval-system.pid",
    },
    "regression": {
        "name": "REGRESSION Agent",
        "system": "rag_pipelines",
        "script": "ops/agent-regression.py",
        "args": ["--daemon", "900"],  # 15min cycles
        "objective": "Detect accuracy drops > 5%. Block regressions > 10%.",
        "metrics": ["regressions_detected", "improvements_detected", "overall_accuracy"],
        "pid_file": "regression-system.pid",
    },
    "fixer": {
        "name": "FIXER Agent",
        "system": "rag_pipelines",
        "script": "ops/agent-fixer.py",
        "args": ["--daemon", "1200"],  # 20min cycles
        "objective": "Diagnose chronic failures. Generate fix recommendations.",
        "metrics": ["fixes_proposed", "chronic_failures_resolved"],
        "pid_file": "fixer-system.pid",
    },
    "monitor": {
        "name": "MONITOR Agent",
        "system": "rag_pipelines",
        "script": "ops/monitor.py",
        "args": ["--loop", "300"],  # 5min checks
        "objective": "Health check all Spaces, pipelines, databases. Alert on failures.",
        "metrics": ["spaces_up", "pipelines_healthy", "db_connected"],
        "pid_file": "monitor-system.pid",
    },
}

ALL_AGENTS = {**SYSTEM1_AGENTS, **SYSTEM2_AGENTS}


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def is_running(pid_file):
    """Check if agent is running by PID file."""
    path = os.path.join(DATA_DIR, pid_file)
    if not os.path.exists(path):
        return False, 0
    try:
        with open(path) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True, pid
    except (ValueError, ProcessLookupError, PermissionError):
        return False, 0


def launch_agent(name, config):
    """Launch a single agent."""
    running, pid = is_running(config["pid_file"])
    if running:
        log(f"  {config['name']} already running (PID {pid})")
        return pid

    script = os.path.join(REPO_ROOT, config["script"])
    if not os.path.exists(script):
        log(f"  {config['name']}: script not found: {script}")
        return 0

    cmd = [sys.executable, script] + config.get("args", [])
    log_file = os.path.join(DATA_DIR, f"{name}-system.log")

    env = os.environ.copy()
    # Source .env.local
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    if line.startswith("export "):
                        line = line[7:]
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and v:
                        env[k] = v

    if config.get("oneshot"):
        # One-shot agents: run once and complete
        log(f"  Launching {config['name']} (one-shot)...")
        proc = subprocess.Popen(
            cmd, env=env, cwd=REPO_ROOT,
            stdout=open(log_file, "a"), stderr=subprocess.STDOUT,
        )
        proc.wait()
        log(f"  {config['name']} completed (exit {proc.returncode})")
        return 0

    # Daemon agents: run in background
    log(f"  Launching {config['name']}...")
    log(f"    Script: {config['script']}")
    log(f"    Objective: {config['objective']}")
    proc = subprocess.Popen(
        cmd, env=env, cwd=REPO_ROOT,
        stdout=open(log_file, "a"), stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    pid_path = os.path.join(DATA_DIR, config["pid_file"])
    with open(pid_path, "w") as f:
        f.write(str(proc.pid))

    log(f"  {config['name']} started (PID {proc.pid})")
    return proc.pid


def stop_agent(name, config):
    """Stop a single agent."""
    running, pid = is_running(config["pid_file"])
    if not running:
        log(f"  {config['name']} not running")
        return

    try:
        os.kill(pid, signal.SIGTERM)
        log(f"  {config['name']} stopped (PID {pid})")
    except Exception as e:
        log(f"  {config['name']} stop error: {e}")

    pid_path = os.path.join(DATA_DIR, config["pid_file"])
    if os.path.exists(pid_path):
        os.remove(pid_path)


def show_status():
    """Show status of all agents."""
    print(f"\n{'='*70}")
    print(f"  NOMOS SECTOR AI — AGENT STATUS")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*70}")

    for system_name, agents in [("SYSTEM 1: DATA PIPELINE", SYSTEM1_AGENTS),
                                  ("SYSTEM 2: RAG PIPELINES", SYSTEM2_AGENTS)]:
        print(f"\n  {system_name}")
        print(f"  {'─'*60}")
        for name, config in agents.items():
            running, pid = is_running(config["pid_file"])
            status = f"\033[92mRUNNING\033[0m (PID {pid})" if running else "\033[91mSTOPPED\033[0m"
            print(f"    {config['name']:20s} {status}")
            print(f"      Objective: {config['objective'][:65]}")

            # Check log file for last activity
            log_file = os.path.join(DATA_DIR, f"{name}-system.log")
            if os.path.exists(log_file):
                try:
                    size = os.path.getsize(log_file)
                    mtime = datetime.fromtimestamp(os.path.getmtime(log_file), tz=timezone.utc)
                    age = (datetime.now(timezone.utc) - mtime).total_seconds()
                    age_str = f"{int(age//60)}m ago" if age < 3600 else f"{int(age//3600)}h ago"
                    print(f"      Log: {size//1024}KB, last activity {age_str}")
                except Exception:
                    pass
            print()

    print(f"{'='*70}")


def write_state():
    """Write current agent state to JSON."""
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system1": {},
        "system2": {},
    }
    for name, config in SYSTEM1_AGENTS.items():
        running, pid = is_running(config["pid_file"])
        state["system1"][name] = {
            "name": config["name"],
            "running": running,
            "pid": pid if running else None,
            "objective": config["objective"],
        }
    for name, config in SYSTEM2_AGENTS.items():
        running, pid = is_running(config["pid_file"])
        state["system2"][name] = {
            "name": config["name"],
            "running": running,
            "pid": pid if running else None,
            "objective": config["objective"],
        }

    state_file = os.path.join(DATA_DIR, "agent-system-state.json")
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Separated Agent System")
    parser.add_argument("action", choices=["launch", "stop", "status", "state"])
    parser.add_argument("target", nargs="?", default="all",
                        choices=["all", "system1", "system2"] + list(ALL_AGENTS.keys()))
    args = parser.parse_args()

    if args.action == "status":
        show_status()
        write_state()
        return

    if args.action == "state":
        write_state()
        log("State written to data/agents/agent-system-state.json")
        return

    # Determine which agents to act on
    if args.target == "all":
        targets = ALL_AGENTS
    elif args.target == "system1":
        targets = SYSTEM1_AGENTS
    elif args.target == "system2":
        targets = SYSTEM2_AGENTS
    else:
        targets = {args.target: ALL_AGENTS[args.target]}

    system_label = {
        "all": "ALL SYSTEMS",
        "system1": "SYSTEM 1: DATA PIPELINE",
        "system2": "SYSTEM 2: RAG PIPELINES",
    }.get(args.target, args.target.upper())

    if args.action == "launch":
        log(f"{'='*60}")
        log(f"LAUNCHING {system_label}")
        log(f"{'='*60}")
        for name, config in targets.items():
            launch_agent(name, config)
        write_state()

    elif args.action == "stop":
        log(f"{'='*60}")
        log(f"STOPPING {system_label}")
        log(f"{'='*60}")
        for name, config in targets.items():
            stop_agent(name, config)
        write_state()


if __name__ == "__main__":
    main()
