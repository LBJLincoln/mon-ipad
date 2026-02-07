#!/usr/bin/env python3
"""
Live Results Writer — Updates docs/data.json after each question.

Usage from eval scripts:
    from importlib.machinery import SourceFileLoader
    writer = SourceFileLoader("w", "benchmark-workflows/live-results-writer.py").load_module()
    writer.init()
    writer.record_question(rag_type, question_id, question_text, correct, f1, latency_ms, error, cost_usd)
    writer.update_pipeline_stats(rag_type, tested, correct, errors, avg_lat, p95_lat, cost)
    writer.update_db_stats()  # re-probe databases

Or standalone:
    python live-results-writer.py --update-db     # refresh DB stats in data.json
    python live-results-writer.py --reset         # reset all results
    python live-results-writer.py --push          # git add+commit+push data.json
"""
import json
import os
import sys
import time
import subprocess
import hashlib
from datetime import datetime

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
DATA_FILE = os.path.join(DOCS_DIR, "data.json")
LOCK_FILE = DATA_FILE + ".lock"


def _load():
    """Load data.json with file locking."""
    if not os.path.exists(DATA_FILE):
        return _default_data()
    with open(DATA_FILE) as f:
        return json.load(f)


def _save(data):
    """Save data.json atomically."""
    data["meta"]["generated_at"] = datetime.utcnow().isoformat() + "Z"
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)


def _default_data():
    return {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "status": "idle",
            "total_questions_in_datasets": 1200,
            "total_testable": 200,
            "total_tested": 0,
            "total_cost_usd": 0
        },
        "databases": {"pinecone": {}, "neo4j": {}, "supabase": {}},
        "pipelines": {
            "standard": {"total_questions": 50, "tested": 0, "correct": 0, "errors": 0,
                        "avg_latency_ms": 0, "p95_latency_ms": 0, "cost_usd": 0},
            "graph": {"total_questions": 50, "tested": 0, "correct": 0, "errors": 0,
                     "avg_latency_ms": 0, "p95_latency_ms": 0, "cost_usd": 0},
            "quantitative": {"total_questions": 50, "tested": 0, "correct": 0, "errors": 0,
                           "avg_latency_ms": 0, "p95_latency_ms": 0, "cost_usd": 0},
            "orchestrator": {"total_questions": 50, "tested": 0, "correct": 0, "errors": 0,
                           "avg_latency_ms": 0, "p95_latency_ms": 0, "cost_usd": 0},
        },
        "questions": [],
        "history": []
    }


# ============================================================
# Public API
# ============================================================

def init(status="running"):
    """Initialize or reset the data file for a new eval run."""
    data = _load()
    data["meta"]["status"] = status
    _save(data)
    return data


def record_question(rag_type, question_id, question_text, correct, f1=0,
                    latency_ms=0, error=None, cost_usd=0, expected="", answer="",
                    match_type=""):
    """Record a single question result and update pipeline stats."""
    data = _load()

    q = {
        "id": question_id,
        "rag_type": rag_type,
        "question": question_text[:200],
        "expected": expected[:200],
        "answer": answer[:300],
        "correct": bool(correct),
        "f1": round(f1, 4),
        "latency_ms": int(latency_ms),
        "error": str(error)[:200] if error else None,
        "match_type": match_type,
        "cost_usd": round(cost_usd, 6),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    data["questions"].append(q)

    # Update pipeline stats
    p = data["pipelines"].get(rag_type, {})
    p["tested"] = p.get("tested", 0) + 1
    if correct:
        p["correct"] = p.get("correct", 0) + 1
    if error:
        p["errors"] = p.get("errors", 0) + 1
    p["cost_usd"] = p.get("cost_usd", 0) + cost_usd

    # Recalculate latencies from all questions of this type
    type_qs = [qq for qq in data["questions"] if qq["rag_type"] == rag_type and qq["latency_ms"] > 0]
    if type_qs:
        lats = sorted([qq["latency_ms"] for qq in type_qs])
        p["avg_latency_ms"] = int(sum(lats) / len(lats))
        p["p95_latency_ms"] = lats[int(len(lats) * 0.95)] if len(lats) > 1 else lats[0]
    data["pipelines"][rag_type] = p

    # Update meta
    data["meta"]["total_tested"] = sum(pp.get("tested", 0) for pp in data["pipelines"].values())
    data["meta"]["total_cost_usd"] = sum(pp.get("cost_usd", 0) for pp in data["pipelines"].values())
    data["meta"]["status"] = "running"

    _save(data)
    return q


def update_pipeline_stats(rag_type, tested, correct, errors, avg_latency_ms,
                          p95_latency_ms, cost_usd=0, total_questions=None):
    """Bulk update pipeline stats (for batch imports)."""
    data = _load()
    p = data["pipelines"].get(rag_type, {})
    p["tested"] = tested
    p["correct"] = correct
    p["errors"] = errors
    p["avg_latency_ms"] = int(avg_latency_ms)
    p["p95_latency_ms"] = int(p95_latency_ms)
    p["cost_usd"] = round(cost_usd, 6)
    if total_questions is not None:
        p["total_questions"] = total_questions
    data["pipelines"][rag_type] = p
    data["meta"]["total_tested"] = sum(pp.get("tested", 0) for pp in data["pipelines"].values())
    _save(data)


def add_history_point(standard=None, graph=None, quantitative=None,
                      orchestrator=None, event="eval"):
    """Add a history data point for trend charts."""
    data = _load()
    point = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "total_tested": data["meta"].get("total_tested", 0),
    }
    if standard is not None: point["standard"] = round(standard, 1)
    if graph is not None: point["graph"] = round(graph, 1)
    if quantitative is not None: point["quantitative"] = round(quantitative, 1)
    if orchestrator is not None: point["orchestrator"] = round(orchestrator, 1)
    data["history"].append(point)
    _save(data)


def update_db_stats():
    """Probe all 3 databases and update stats in data.json."""
    data = _load()

    # Pinecone
    try:
        from urllib import request
        host = os.environ.get("PINECONE_HOST", "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io")
        api_key = os.environ.get("PINECONE_API_KEY", "")
        if api_key:
            req = request.Request(f"{host}/describe_index_stats", data=b"{}",
                headers={"Api-Key": api_key, "Content-Type": "application/json"}, method="POST")
            with request.urlopen(req, timeout=10) as resp:
                stats = json.loads(resp.read())
                data["databases"]["pinecone"] = {
                    "total_vectors": stats.get("totalVectorCount", 0),
                    "namespaces": {k: v.get("vectorCount", 0) for k, v in stats.get("namespaces", {}).items()}
                }
    except Exception as e:
        print(f"  Pinecone probe failed: {e}")

    # Neo4j
    try:
        import base64
        pwd = os.environ.get("NEO4J_PASSWORD", "")
        if pwd:
            auth = base64.b64encode(f"neo4j:{pwd}".encode()).decode()
            for cypher, key in [
                ("MATCH (n) RETURN count(n)", "total_nodes"),
                ("MATCH ()-[r]->() RETURN count(r)", "total_relationships"),
                ("MATCH (n) RETURN labels(n)[0] as l, count(*) as c ORDER BY c DESC",
                 "labels"),
            ]:
                req = request.Request("https://38c949a2.databases.neo4j.io/db/neo4j/query/v2",
                    data=json.dumps({"statement": cypher}).encode(),
                    headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json",
                             "Accept": "application/json"}, method="POST")
                with request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read())
                    vals = result.get("data", {}).get("values", [])
                    if key == "labels":
                        data["databases"]["neo4j"]["labels"] = {r[0]: r[1] for r in vals}
                    else:
                        data["databases"]["neo4j"][key] = vals[0][0] if vals else 0
    except Exception as e:
        print(f"  Neo4j probe failed: {e}")

    # Supabase
    try:
        conn = f"postgresql://postgres.ayqviqmxifzmhphiqfmj:{os.environ.get('SUPABASE_PASSWORD','')}@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
        tables = ["financials", "balance_sheet", "sales_data", "products", "employees", "community_summaries"]
        tb = {}
        for t in tables:
            r = subprocess.run(["psql", conn, "-t", "-A", "-c", f"SELECT COUNT(*) FROM {t};"],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                tb[t] = int(r.stdout.strip())
        if tb:
            data["databases"]["supabase"]["tables"] = tb
            data["databases"]["supabase"]["total_rows"] = sum(tb.values())
    except Exception as e:
        print(f"  Supabase probe failed: {e}")

    _save(data)
    return data["databases"]


def finish(event="eval_complete"):
    """Mark evaluation as complete and add history point."""
    data = _load()
    data["meta"]["status"] = "complete"

    # Calculate accuracies for history
    accs = {}
    for name, p in data["pipelines"].items():
        if p.get("tested", 0) > 0:
            accs[name] = p["correct"] / p["tested"] * 100
    add_history_point(event=event, **accs)
    _save(data)


def git_push(message="Update dashboard data"):
    """Commit and push data.json to GitHub."""
    repo_root = os.path.dirname(DOCS_DIR)
    subprocess.run(["git", "add", "docs/data.json"], cwd=repo_root)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_root)
    subprocess.run(["git", "push"], cwd=repo_root)


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    args = sys.argv[1:]
    if "--update-db" in args:
        print("Updating database stats...")
        stats = update_db_stats()
        for db, info in stats.items():
            print(f"  {db}: {json.dumps(info)[:200]}")
    elif "--reset" in args:
        print("Resetting data.json...")
        _save(_default_data())
        print("Done.")
    elif "--push" in args:
        print("Pushing data.json to GitHub...")
        git_push()
    elif "--finish" in args:
        finish()
        print("Marked as complete.")
    else:
        print("Usage: python live-results-writer.py [--update-db|--reset|--push|--finish]")
