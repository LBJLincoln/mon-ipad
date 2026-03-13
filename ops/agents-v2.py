#!/usr/bin/env python3
"""
Agents V2 — 4 Adapted Agentic Loop Agents
==========================================

4 agents that do REAL WORK, not just monitor:

  1. EVAL-BLAST   — Continuous full-blast eval (all 4 pipelines), results → Supabase
  2. FIXER        — Reads worst-performing questions, diagnoses, applies targeted fixes
  3. INGEST-FEED  — Tavily → Docling → n8n Ingestion/Enrichment workflows
  4. REGRESSION   — Watches for accuracy drops, blocks bad changes, alerts

Architecture:
  - Each agent runs as a background process
  - Inter-agent communication via JSON marker files in data/agents/
  - All results stored in Supabase (eval_runs, eval_results, eval_question_bank)
  - Fixer reads from eval_results to find what's broken

Usage:
  source .env.local
  python3 ops/agents-v2.py launch all          # Start all 4
  python3 ops/agents-v2.py launch eval-blast   # Start one
  python3 ops/agents-v2.py status              # Status of all
  python3 ops/agents-v2.py stop all            # Stop all
  python3 ops/agents-v2.py logs fixer          # Tail logs
"""

# ── IPv4 fix ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "agents")
LOG_DIR = os.path.join(REPO_ROOT, "logs", "agents")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")

def log(msg):
    print(f"[{ts()}] {msg}")

# ════════════════════════════════════════════════════════════════════
# AGENT DEFINITIONS
# ════════════════════════════════════════════════════════════════════

AGENTS = {
    "eval-blast": {
        "description": "Full-blast eval: 4 pipelines, 50Q/cycle, results → Supabase",
        "command": [
            sys.executable, os.path.join(REPO_ROOT, "eval", "eval-blast.py"),
            "--daemon", "1800", "--max", "50",
        ],
        "cycle_seconds": 1800,
        "marker": "eval_blast_done.marker",
    },
    "fixer": {
        "description": "Reads worst questions from DB, diagnoses failures, applies fixes",
        "command": [
            sys.executable, os.path.join(REPO_ROOT, "ops", "agent-fixer.py"),
            "--daemon", "3600",
        ],
        "cycle_seconds": 3600,
        "marker": "fixer_done.marker",
    },
    "ingest-feed": {
        "description": "Tavily → n8n Ingestion V4.0 → Docling → Enrichment → DBs",
        "command": [
            sys.executable, os.path.join(REPO_ROOT, "ops", "agent-ingest-feed.py"),
            "--daemon", "3600",
        ],
        "cycle_seconds": 3600,
        "marker": "ingest_feed_done.marker",
    },
    "regression": {
        "description": "Watches accuracy trends, alerts on drops >5%, blocks regressions",
        "command": [
            sys.executable, os.path.join(REPO_ROOT, "ops", "agent-regression.py"),
            "--daemon", "900",
        ],
        "cycle_seconds": 900,
        "marker": "regression_done.marker",
    },
}

# ════════════════════════════════════════════════════════════════════
# PROCESS MANAGEMENT
# ════════════════════════════════════════════════════════════════════

def pid_file(name):
    return os.path.join(DATA_DIR, f"{name}.pid")

def log_file(name):
    return os.path.join(LOG_DIR, f"{name}.log")

def is_running(name):
    pf = pid_file(name)
    if not os.path.exists(pf):
        return False, 0
    with open(pf) as f:
        pid = int(f.read().strip())
    try:
        os.kill(pid, 0)
        return True, pid
    except OSError:
        os.remove(pf)
        return False, 0

def launch_agent(name):
    if name not in AGENTS:
        log(f"Unknown agent: {name}")
        return False

    running, pid = is_running(name)
    if running:
        log(f"  {name} already running (PID {pid})")
        return True

    agent = AGENTS[name]
    lf = log_file(name)
    log(f"  Launching {name}: {agent['description']}")

    with open(lf, "a") as logf:
        logf.write(f"\n{'='*60}\n[{ts()}] Starting {name}\n{'='*60}\n")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    with open(lf, "a") as logf:
        proc = subprocess.Popen(
            agent["command"],
            stdout=logf, stderr=subprocess.STDOUT,
            env=env, cwd=REPO_ROOT,
            preexec_fn=os.setsid,
        )

    with open(pid_file(name), "w") as f:
        f.write(str(proc.pid))

    log(f"  {name} started (PID {proc.pid})")
    return True

def stop_agent(name):
    running, pid = is_running(name)
    if not running:
        log(f"  {name} not running")
        return
    log(f"  Stopping {name} (PID {pid})")
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        time.sleep(2)
        try:
            os.kill(pid, 0)
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            pass
    except Exception as e:
        log(f"  Error stopping {name}: {e}")
    pf = pid_file(name)
    if os.path.exists(pf):
        os.remove(pf)
    log(f"  {name} stopped")

def show_status():
    log("Agent Status V2:")
    log("-" * 75)
    for name, agent in AGENTS.items():
        running, pid = is_running(name)
        status = f"RUNNING (PID {pid})" if running else "STOPPED"
        marker = os.path.join(DATA_DIR, agent["marker"])
        last_run = ""
        if os.path.exists(marker):
            with open(marker) as f:
                try:
                    data = json.load(f)
                    last_run = f" | Last: {data.get('timestamp', '?')[:19]}"
                except:
                    last_run = f" | Last: {datetime.fromtimestamp(os.path.getmtime(marker)).strftime('%H:%M')}"

        cycle = agent["cycle_seconds"]
        log(f"  {name:15} {status:25} | cycle={cycle}s{last_run}")
        log(f"  {'':15} {agent['description']}")
    log("-" * 75)

    # Show eval stats from Supabase
    try:
        import psycopg2
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SET search_path TO public")
                cur.execute("SELECT COUNT(*) FROM eval_runs")
                runs = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM eval_results")
                results = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM eval_question_bank")
                bank = cur.fetchone()[0]
                cur.execute("""
                    SELECT pipeline, COUNT(*),
                           SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END),
                           ROUND(AVG(latency_ms))
                    FROM eval_results
                    WHERE created_at > now() - interval '24 hours'
                    GROUP BY pipeline ORDER BY pipeline
                """)
                recent = cur.fetchall()
            conn.close()

            log("")
            log("Supabase Eval Stats:")
            log(f"  Runs: {runs} | Results: {results} | Question Bank: {bank}")
            if recent:
                log("  Last 24h per pipeline:")
                for pipe, total, passed, avg_lat in recent:
                    pct = passed / total * 100 if total else 0
                    log(f"    {pipe:15} {passed}/{total} ({pct:.0f}%) | {avg_lat}ms avg")
    except Exception as e:
        log(f"  (DB stats unavailable: {e})")

def tail_logs(name, lines=50):
    lf = log_file(name)
    if not os.path.exists(lf):
        log(f"No logs for {name}")
        return
    with open(lf) as f:
        all_lines = f.readlines()
    for line in all_lines[-lines:]:
        print(line, end="")


# ════════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage: agents-v2.py {launch|stop|status|logs} [agent|all]")
        print(f"Agents: {', '.join(AGENTS.keys())}")
        sys.exit(1)

    cmd = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "status":
        show_status()
    elif cmd == "launch":
        if target == "all":
            for name in AGENTS:
                launch_agent(name)
        elif target:
            launch_agent(target)
        else:
            print("Specify agent name or 'all'")
    elif cmd == "stop":
        if target == "all":
            for name in AGENTS:
                stop_agent(name)
        elif target:
            stop_agent(target)
        else:
            print("Specify agent name or 'all'")
    elif cmd == "logs":
        name = target or "eval-blast"
        lines = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        tail_logs(name, lines)
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
