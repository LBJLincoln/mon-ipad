#!/usr/bin/env python3
"""Nomos AI — Live Health Board

Single command to see EVERYTHING: pipelines, databases, infra, agents, eval, ingestion.
Checks every node, every credential, every endpoint. Shows what's wrong.

Usage:
    python3 ops/health-board.py              # Full board
    python3 ops/health-board.py --json       # JSON output for dashboard
    python3 ops/health-board.py --loop 300   # Continuous (every 5 min)
"""

import json
import os
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force IPv4
_orig = socket.getaddrinfo
def _ipv4(h, p, f=0, t=0, pr=0, fl=0):
    return _orig(h, p, socket.AF_INET, t, pr, fl)
socket.getaddrinfo = _ipv4

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─── Configuration ───────────────────────────────────────────────
SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S2": "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S4": "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S6": "https://lbjlincoln-nomos-docling-api.hf.space",
    "S7": "https://lbjlincoln-nomos-rag-engine-7.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
    "Embed": "https://lbjlincoln-nomos-embeddings-api.hf.space",
    "Rerank": "https://lbjlincoln-nomos-reranker-api.hf.space",
}

PIPELINES = {
    "standard": {"path": "/webhook/rag-multi-index-v3", "test_q": "Quels sont les ratios financiers du CAC40 ?", "sector": "finance"},
    "graph": {"path": "/webhook/ff622742-6d71-4e91-af71-b5c666088717", "test_q": "Quelles entreprises du CAC40 sont dans le BTP ?", "sector": "btp"},
    "quant": {"path": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9", "test_q": "Quel est le CA de TotalEnergies ?", "sector": "finance"},
    "orchestrator": {"path": "/webhook/orchestrator-v2", "test_q": "Compare les normes IFRS et les Eurocodes", "sector": "finance"},
}

INGESTION_PIPELINES = {
    "ingestion": {"path": "/webhook/rag-v6-ingestion", "test_q": '{"test": true}'},
    "enrichment": {"path": "/webhook/rag-v6-enrichment", "test_q": '{"test": true}'},
}

E5_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
JINA_HOST = "https://website-sectors-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"


def load_env():
    env_file = os.path.join(REPO_ROOT, ".env.local")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                eq = line.find("=")
                if eq > 0:
                    key = line[:eq].strip()
                    val = line[eq+1:].strip().strip('"').strip("'")
                    os.environ[key] = val


def http_get(url, timeout=10, headers=None):
    """GET request, returns (status, body, elapsed)."""
    req = urllib.request.Request(url, headers=headers or {})
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
        return resp.status, resp.read().decode()[:2000], time.time() - start
    except urllib.error.HTTPError as e:
        return e.code, "", time.time() - start
    except Exception as e:
        return 0, str(e)[:200], time.time() - start


def http_post(url, payload, timeout=30, headers=None):
    """POST JSON, returns (status, body, elapsed)."""
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    data = json.dumps(payload).encode() if isinstance(payload, (dict, list)) else payload.encode()
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
        return resp.status, resp.read().decode()[:2000], time.time() - start
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:500]
        except:
            pass
        return e.code, body, time.time() - start
    except Exception as e:
        return 0, str(e)[:200], time.time() - start


# ─── Check functions ─────────────────────────────────────────────

def check_space(name, url):
    status, _, elapsed = http_get(f"{url}/healthz", timeout=8)
    if status == 0:
        # Try webhook ping as fallback
        status, _, elapsed = http_post(f"{url}/webhook/rag-multi-index-v3",
            {"query": "ping", "sector": "finance"}, timeout=10)
    ok = status in (200, 201)
    return {"name": name, "url": url, "status": status, "ok": ok, "elapsed": round(elapsed, 1)}


def check_pipeline(name, config, space_url="https://lbjlincoln-nomos-rag-engine.hf.space"):
    url = f"{space_url}{config['path']}"
    payload = {"message": config["test_q"], "sector": config["sector"]}
    status, body, elapsed = http_post(url, payload, timeout=45)

    ok = False
    answer_len = 0
    error = ""

    if status in (200, 201) and body:
        try:
            data = json.loads(body)
            if isinstance(data, list):
                data = data[0] if data else {}
            answer = str(data.get("response", data.get("answer", data.get("interpretation", ""))))
            answer_len = len(answer)
            if answer_len > 20 and "error" not in answer.lower()[:50]:
                ok = True
            elif "Error in workflow" in body:
                error = "WORKFLOW ERROR"
            elif answer_len < 20:
                error = "EMPTY RESPONSE"
        except:
            error = f"JSON PARSE ERROR: {body[:100]}"
    elif status == 0:
        error = "TIMEOUT" if elapsed > 40 else f"CONNECTION ERROR"
    else:
        error = f"HTTP {status}"

    return {
        "name": name, "status": status, "ok": ok,
        "elapsed": round(elapsed, 1), "answer_len": answer_len, "error": error
    }


def check_pinecone(name, host):
    key = os.environ.get("PINECONE_API_KEY", "")
    status, body, elapsed = http_get(
        f"{host}/describe_index_stats",
        timeout=10,
        headers={"Api-Key": key}
    )
    count = 0
    if status == 200:
        try:
            data = json.loads(body)
            count = data.get("totalRecordCount", data.get("totalVectorCount", 0))
        except:
            pass
    return {"name": name, "ok": status == 200, "count": count, "elapsed": round(elapsed, 1)}


def check_supabase():
    """Check Supabase via psycopg2 (MCP not available in scripts)."""
    try:
        import psycopg2
        url = os.environ.get("DATABASE_URL", "")
        conn = psycopg2.connect(url, connect_timeout=10)
        cur = conn.cursor()
        cur.execute("SET search_path TO public")
        cur.execute("SELECT COUNT(*) FROM sector_documents")
        docs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM processing_queue")
        queue = cur.fetchone()[0]
        cur.execute("SELECT MAX(created_at) FROM sector_documents")
        latest = str(cur.fetchone()[0])
        conn.close()
        return {"ok": True, "docs": docs, "queue": queue, "latest": latest}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100], "docs": 0, "queue": 0, "latest": ""}


def check_neo4j():
    uri = os.environ.get("NEO4J_URI", "")
    user = os.environ.get("NEO4J_USERNAME", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "")
    if not uri:
        return {"ok": False, "error": "NEO4J_URI not set", "nodes": 0}

    # Convert bolt:// to https://
    host = uri.replace("neo4j+s://", "").replace("bolt+s://", "").replace("neo4j://", "").replace("bolt://", "")
    url = f"https://{host}/db/neo4j/query/v2"

    import base64
    auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()

    status, body, elapsed = http_post(url,
        {"statement": "MATCH (n) RETURN count(n) AS cnt"},
        timeout=15,
        headers={"Authorization": f"Basic {auth}"}
    )

    nodes = 0
    if status == 200:
        try:
            data = json.loads(body)
            nodes = data.get("data", {}).get("values", [[0]])[0][0]
        except:
            pass

    return {"ok": status == 200, "nodes": nodes, "elapsed": round(elapsed, 1)}


def check_litellm():
    status, body, elapsed = http_post(
        "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions",
        {"model": "smart", "messages": [{"role": "user", "content": "Say OK"}]},
        timeout=30,
        headers={"Authorization": "Bearer sk-litellm-nomos-2026"}
    )
    ok = status == 200 and "choices" in body
    model = ""
    if ok:
        try:
            model = json.loads(body).get("model", "")
        except:
            pass
    return {"ok": ok, "status": status, "model": model, "elapsed": round(elapsed, 1)}


def check_agents():
    pid_dir = os.path.join(REPO_ROOT, "data", "agents")
    agents = {}
    for name in ["monitor", "eval", "ingest", "pipeline", "docs"]:
        pid_file = os.path.join(pid_dir, f"{name}.pid")
        alive = False
        pid = None
        if os.path.exists(pid_file):
            try:
                pid = int(open(pid_file).read().strip())
                os.kill(pid, 0)
                alive = True
            except:
                pass
        agents[name] = {"pid": pid, "alive": alive}
    return agents


def check_agentic_loop():
    import subprocess
    try:
        result = subprocess.run(["pgrep", "-f", "agentic-loop"], capture_output=True, text=True, timeout=5)
        pids = [int(p) for p in result.stdout.strip().split() if p.isdigit()]
        running = len(pids) > 0
    except:
        running = False
        pids = []

    # Check last cycle
    reports_dir = os.path.join(REPO_ROOT, "data", "agentic-loop", "reports")
    last_cycle = {}
    if os.path.exists(reports_dir):
        files = sorted([f for f in os.listdir(reports_dir) if f.endswith(".json")])
        if files:
            try:
                last_cycle = json.load(open(os.path.join(reports_dir, files[-1])))
            except:
                pass

    return {"running": running, "pids": pids, "last_cycle": last_cycle}


def check_eval():
    import subprocess
    try:
        result = subprocess.run(["pgrep", "-f", "parallel-eval"], capture_output=True, text=True, timeout=5)
        pids = [int(p) for p in result.stdout.strip().split() if p.isdigit()]
        running = len(pids) > 0
    except:
        running = False
        pids = []

    # Check log
    log_file = "/tmp/full-eval-5k.log"
    progress = ""
    if os.path.exists(log_file):
        try:
            lines = open(log_file).readlines()
            if lines:
                progress = lines[-1].strip()
        except:
            pass

    return {"running": running, "pids": pids, "progress": progress}


def check_codespace():
    import subprocess
    try:
        result = subprocess.run(["gh", "cs", "list", "--json", "name,state"],
                              capture_output=True, text=True, timeout=15)
        spaces = json.loads(result.stdout)
        return [{"name": s["name"], "state": s["state"]} for s in spaces]
    except:
        return []


# ─── Main Board ──────────────────────────────────────────────────

def run_board():
    load_env()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"\n{'='*75}")
    print(f"  NOMOS AI — LIVE HEALTH BOARD — {now}")
    print(f"{'='*75}\n")

    # 1. HF Spaces (parallel)
    print("  HF SPACES")
    print("  " + "-"*70)
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(check_space, n, u): n for n, u in SPACES.items()}
        results = {}
        for f in as_completed(futures):
            r = f.result()
            results[r["name"]] = r

    for name in SPACES:
        r = results.get(name, {"ok": False, "status": 0, "elapsed": 0})
        icon = "OK" if r["ok"] else "DOWN"
        print(f"  {name:<8} {icon:<6} HTTP {r['status']:<4} {r['elapsed']:.1f}s")

    # 2. Pipelines (S1 only, sequential)
    print(f"\n  RAG PIPELINES (on S1)")
    print("  " + "-"*70)
    for name, config in PIPELINES.items():
        r = check_pipeline(name, config)
        icon = "OK" if r["ok"] else "FAIL"
        err = f" — {r['error']}" if r["error"] else f" — {r['answer_len']} chars"
        print(f"  {name:<14} {icon:<6} {r['elapsed']:>5.1f}s{err}")

    # 3. Ingestion pipelines
    print(f"\n  INGESTION PIPELINES (on S1)")
    print("  " + "-"*70)
    for name, config in INGESTION_PIPELINES.items():
        url = f"{SPACES['S1']}{config['path']}"
        status, body, elapsed = http_post(url, json.loads(config["test_q"]), timeout=15)
        ok = status in (200, 201)
        err = body[:60] if not ok else ""
        print(f"  {name:<14} {'OK' if ok else 'ERR':<6} HTTP {status:<4} {elapsed:.1f}s {err}")

    # 4. Databases
    print(f"\n  DATABASES")
    print("  " + "-"*70)

    e5 = check_pinecone("E5 (primary)", E5_HOST)
    jina = check_pinecone("Jina (secondary)", JINA_HOST)
    sb = check_supabase()
    neo = check_neo4j()

    print(f"  E5 Pinecone    {'OK' if e5['ok'] else 'DOWN':<6} {e5['count']:>10,} vectors")
    print(f"  Jina Pinecone  {'OK' if jina['ok'] else 'DOWN':<6} {jina['count']:>10,} vectors")
    print(f"  Supabase       {'OK' if sb['ok'] else 'DOWN':<6} {sb['docs']:>10,} docs | queue: {sb['queue']} | latest: {sb['latest'][:16]}")
    print(f"  Neo4j          {'OK' if neo['ok'] else 'DOWN':<6} {neo.get('nodes',0):>10,} nodes")

    # 5. LiteLLM
    print(f"\n  LLM (LiteLLM S7)")
    print("  " + "-"*70)
    llm = check_litellm()
    print(f"  LiteLLM S7     {'OK' if llm['ok'] else 'DOWN':<6} model={llm['model'][:40]} {llm['elapsed']:.1f}s")

    # 6. Agents
    print(f"\n  AGENTS & PROCESSES")
    print("  " + "-"*70)
    agents = check_agents()
    for name, info in agents.items():
        icon = "RUN" if info["alive"] else "STOP"
        pid = info["pid"] or "-"
        print(f"  {name:<12} {icon:<6} PID {pid}")

    loop = check_agentic_loop()
    print(f"  agentic-loop {'RUN' if loop['running'] else 'STOP':<6} PIDs {loop['pids']}")
    if loop["last_cycle"]:
        lc = loop["last_cycle"]
        score = lc.get("scores", {}).get("overall", "?")
        delta = lc.get("scores", {}).get("delta", "?")
        print(f"               Last: cycle {lc.get('cycle','?')} | score={score} | delta={delta}")

    ev = check_eval()
    print(f"  eval           {'RUN' if ev['running'] else 'STOP':<6} {ev['progress'][:60]}")

    # 7. Codespaces
    print(f"\n  CODESPACES")
    print("  " + "-"*70)
    cs = check_codespace()
    for c in cs:
        icon = "RUN" if c["state"] == "Available" else "OFF"
        print(f"  {c['name']:<30} {icon}")
    if not cs:
        print("  (none found)")

    # 8. Summary
    print(f"\n{'='*75}")
    space_ok = sum(1 for n in SPACES if results.get(n, {}).get("ok"))
    print(f"  Spaces: {space_ok}/{len(SPACES)} | E5: {e5['count']:,} | Supabase: {sb['docs']:,} | Neo4j: {neo.get('nodes',0):,}")
    agent_ok = sum(1 for a in agents.values() if a["alive"])
    print(f"  Agents: {agent_ok}/5 | Loop: {'ON' if loop['running'] else 'OFF'} | Eval: {'ON' if ev['running'] else 'OFF'}")
    print(f"  LiteLLM: {'OK' if llm['ok'] else 'DOWN'} | Redis: check from HF Space")
    print(f"{'='*75}\n")

    # Save JSON
    board = {
        "timestamp": now,
        "spaces": {n: results.get(n, {}) for n in SPACES},
        "databases": {"e5": e5, "jina": jina, "supabase": sb, "neo4j": neo},
        "llm": llm,
        "agents": agents,
        "agentic_loop": loop,
        "eval": ev,
        "codespaces": cs,
    }

    out = os.path.join(REPO_ROOT, "data", "health-board.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(board, f, indent=2, default=str)

    return board


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="JSON output only")
    parser.add_argument("--loop", type=int, help="Continuous mode (interval in seconds)")
    args = parser.parse_args()

    if args.loop:
        while True:
            board = run_board()
            if args.json:
                print(json.dumps(board, indent=2, default=str))
            time.sleep(args.loop)
    else:
        board = run_board()
        if args.json:
            print(json.dumps(board, indent=2, default=str))
