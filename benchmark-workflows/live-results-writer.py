#!/usr/bin/env python3
"""
Live Results Writer — Updates docs/data.json after each question.
Also writes structured execution logs and error traces to logs/ directory.

Usage from eval scripts:
    from importlib.machinery import SourceFileLoader
    writer = SourceFileLoader("w", "benchmark-workflows/live-results-writer.py").load_module()
    writer.init()
    writer.record_question(rag_type, question_id, question_text, correct, f1, latency_ms, error, cost_usd)
    writer.record_execution(rag_type, question_id, question_text, input_payload, raw_response, ...)
    writer.snapshot_databases()  # take DB snapshot
    writer.record_workflow_change(description, files_changed, before_metrics, after_metrics)
    writer.update_db_stats()  # re-probe databases

Or standalone:
    python live-results-writer.py --update-db       # refresh DB stats in data.json
    python live-results-writer.py --snapshot-db      # take a DB snapshot
    python live-results-writer.py --reset            # reset all results
    python live-results-writer.py --push             # git add+commit+push
"""
import json
import os
import sys
import time
import subprocess
import hashlib
import traceback
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
EXEC_DIR = os.path.join(LOGS_DIR, "executions")
ERR_DIR = os.path.join(LOGS_DIR, "errors")
SNAP_DIR = os.path.join(LOGS_DIR, "db-snapshots")
DATA_FILE = os.path.join(DOCS_DIR, "data.json")
LOCK_FILE = DATA_FILE + ".lock"

# Ensure directories exist
for d in [EXEC_DIR, ERR_DIR, SNAP_DIR]:
    os.makedirs(d, exist_ok=True)

# Current execution session
_session_id = None
_exec_log_path = None


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
        "db_snapshots": [],
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
        "history": [],
        "workflow_changes": [],
        "execution_logs": []
    }


def _sanitize(val, max_len=500):
    """Truncate and sanitize a value for JSON storage."""
    if val is None:
        return None
    s = str(val)
    return s[:max_len] if len(s) > max_len else s


def _classify_error(error_str, latency_ms, http_status=None):
    """Classify an error into a category for analytics."""
    if not error_str:
        return None
    err = error_str.lower()
    if "timed out" in err or "timeout" in err or latency_ms > 25000:
        return "TIMEOUT"
    if "urlopen error" in err or "connection" in err:
        return "NETWORK"
    if http_status and http_status >= 500:
        return "SERVER_ERROR"
    if http_status == 429:
        return "RATE_LIMIT"
    if http_status and 400 <= http_status < 500:
        return "CLIENT_ERROR"
    if "empty response" in err:
        return "EMPTY_RESPONSE"
    if "entity" in err and ("not found" in err or "miss" in err):
        return "ENTITY_MISS"
    if "sql" in err:
        return "SQL_ERROR"
    return "UNKNOWN"


# ============================================================
# Public API
# ============================================================

def init(status="running"):
    """Initialize a new eval session. Creates execution log file."""
    global _session_id, _exec_log_path
    _session_id = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    _exec_log_path = os.path.join(EXEC_DIR, f"exec-{_session_id}.jsonl")

    data = _load()
    data["meta"]["status"] = status
    data["meta"]["current_session"] = _session_id

    # Ensure new schema fields exist
    if "db_snapshots" not in data:
        data["db_snapshots"] = []
    if "workflow_changes" not in data:
        data["workflow_changes"] = []
    if "execution_logs" not in data:
        data["execution_logs"] = []

    _save(data)
    return data


def record_question(rag_type, question_id, question_text, correct, f1=0,
                    latency_ms=0, error=None, cost_usd=0, expected="", answer="",
                    match_type=""):
    """Record a single question result and update pipeline stats."""
    data = _load()

    # Classify error
    error_type = _classify_error(str(error) if error else None, latency_ms)

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
        "error_type": error_type,
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


def record_execution(rag_type, question_id, question_text, expected="",
                     input_payload=None, raw_response=None, extracted_answer="",
                     correct=False, f1=0, match_type="", latency_ms=0,
                     http_status=None, response_size=0, error=None,
                     cost_usd=0, pipeline_details=None):
    """Record a detailed execution trace to the JSONL log file + error file if applicable.

    Args:
        pipeline_details: dict with pipeline-specific info:
          For graph: entities_extracted, neo4j_paths_found, traversal_depth, community_summaries_matched
          For standard: topK, embedding_model, pinecone_results_count
          For quantitative: sql_generated, sql_validation_status, result_count, null_aggregation
          For orchestrator: sub_pipelines_invoked, sub_pipeline_results, routing_decision
    """
    error_type = _classify_error(str(error) if error else None, latency_ms, http_status)

    # Truncate raw_response for storage
    raw_resp_str = None
    if raw_response is not None:
        try:
            raw_resp_str = json.dumps(raw_response, ensure_ascii=False)[:2000]
        except (TypeError, ValueError):
            raw_resp_str = str(raw_response)[:2000]

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": _session_id,
        "question_id": question_id,
        "rag_type": rag_type,
        "question": question_text[:300],
        "expected": expected[:300],

        "input": {
            "query": question_text[:300],
            "payload": json.dumps(input_payload)[:500] if input_payload else None
        },

        "output": {
            "raw_response_preview": raw_resp_str,
            "extracted_answer": extracted_answer[:500],
            "confidence": None,
            "engine": rag_type.upper()
        },

        "pipeline_details": pipeline_details or {},

        "evaluation": {
            "correct": bool(correct),
            "method": match_type,
            "f1": round(f1, 4),
        },

        "performance": {
            "total_latency_ms": int(latency_ms),
            "http_status": http_status,
            "response_size_bytes": response_size,
            "cost_usd": round(cost_usd, 6)
        },

        "error": {
            "type": error_type,
            "message": _sanitize(error, 500),
        } if error else None
    }

    # Extract confidence from raw_response if available
    if raw_response and isinstance(raw_response, dict):
        entry["output"]["confidence"] = raw_response.get("confidence")

    # Write to execution log (JSONL)
    if _exec_log_path:
        with open(_exec_log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Write error trace file if error
    if error:
        err_id = f"err-{datetime.utcnow().strftime('%Y-%m-%d')}-{question_id}-{error_type or 'unknown'}".lower()
        err_id = err_id.replace(" ", "-")
        err_path = os.path.join(ERR_DIR, f"{err_id}.json")
        err_trace = {
            "error_id": err_id,
            "timestamp": entry["timestamp"],
            "session_id": _session_id,
            "question_id": question_id,
            "rag_type": rag_type,
            "error_type": error_type,
            "error_message": _sanitize(error, 1000),
            "http_status": http_status,
            "input_payload": input_payload,
            "partial_response": raw_resp_str,
            "pipeline_details": pipeline_details or {},
            "performance": entry["performance"],
            "question": question_text[:300],
            "expected": expected[:300]
        }
        with open(err_path, "w") as f:
            json.dump(err_trace, f, indent=2, ensure_ascii=False)

    # Update execution_logs summary in data.json (last 50 only for dashboard)
    data = _load()
    if "execution_logs" not in data:
        data["execution_logs"] = []
    summary = {
        "timestamp": entry["timestamp"],
        "question_id": question_id,
        "rag_type": rag_type,
        "correct": bool(correct),
        "f1": round(f1, 4),
        "latency_ms": int(latency_ms),
        "error_type": error_type,
        "error_preview": _sanitize(error, 100) if error else None,
        "answer_preview": extracted_answer[:100],
        "confidence": entry["output"]["confidence"],
        "pipeline_details_summary": _summarize_pipeline_details(rag_type, pipeline_details)
    }
    data["execution_logs"].append(summary)
    # Keep only last 200 entries in data.json
    if len(data["execution_logs"]) > 200:
        data["execution_logs"] = data["execution_logs"][-200:]
    _save(data)

    return entry


def _summarize_pipeline_details(rag_type, details):
    """Create a compact summary of pipeline details for the dashboard."""
    if not details:
        return None
    summary = {}
    if rag_type == "graph":
        summary["entities"] = details.get("entities_extracted", [])
        summary["neo4j_paths"] = details.get("neo4j_paths_found", 0)
        summary["traversal_depth"] = details.get("traversal_depth", 0)
        summary["community_matches"] = details.get("community_summaries_matched", 0)
    elif rag_type == "standard":
        summary["topK"] = details.get("topK")
        summary["pinecone_results"] = details.get("pinecone_results_count", 0)
    elif rag_type == "quantitative":
        summary["sql"] = _sanitize(details.get("sql_generated"), 200)
        summary["sql_status"] = details.get("sql_validation_status")
        summary["result_count"] = details.get("result_count", 0)
        summary["null_agg"] = details.get("null_aggregation", False)
    elif rag_type == "orchestrator":
        summary["sub_pipelines"] = details.get("sub_pipelines_invoked", [])
        summary["routing"] = details.get("routing_decision")
    return summary


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


def record_workflow_change(description, files_changed=None, before_metrics=None,
                           after_metrics=None, change_type="modification",
                           affected_pipelines=None):
    """Record a workflow modification event for the evolution timeline.

    Args:
        description: Human-readable description of the change
        files_changed: list of filenames modified
        before_metrics: dict {pipeline: {accuracy, errors, latency}} before change
        after_metrics: dict {pipeline: {accuracy, errors, latency}} after change
        change_type: "enrichment"|"bugfix"|"optimization"|"feature"|"modification"
        affected_pipelines: list of pipeline names affected
    """
    data = _load()
    if "workflow_changes" not in data:
        data["workflow_changes"] = []

    change = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "description": description,
        "change_type": change_type,
        "files_changed": files_changed or [],
        "affected_pipelines": affected_pipelines or [],
        "before_metrics": before_metrics,
        "after_metrics": after_metrics
    }
    data["workflow_changes"].append(change)
    _save(data)
    return change


def snapshot_databases(trigger="manual"):
    """Take a snapshot of all database states and store it.

    Args:
        trigger: "pre-eval"|"post-eval"|"manual"|"enrichment"
    """
    snap_id = f"snap-{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}"
    snapshot = {
        "snapshot_id": snap_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "trigger": trigger,
        "pinecone": {},
        "neo4j": {},
        "supabase": {}
    }

    # Pinecone
    try:
        from urllib import request as url_request
        host = os.environ.get("PINECONE_HOST", "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io")
        api_key = os.environ.get("PINECONE_API_KEY", "")
        if api_key:
            req = url_request.Request(f"{host}/describe_index_stats", data=b"{}",
                headers={"Api-Key": api_key, "Content-Type": "application/json"}, method="POST")
            with url_request.urlopen(req, timeout=10) as resp:
                stats = json.loads(resp.read())
                snapshot["pinecone"] = {
                    "total_vectors": stats.get("totalVectorCount", 0),
                    "namespaces": {k: v.get("vectorCount", 0) for k, v in stats.get("namespaces", {}).items()}
                }
    except Exception as e:
        snapshot["pinecone"]["error"] = str(e)[:200]
        print(f"  Pinecone snapshot failed: {e}")

    # Neo4j
    try:
        from urllib import request as url_request
        import base64
        pwd = os.environ.get("NEO4J_PASSWORD", "")
        if pwd:
            auth = base64.b64encode(f"neo4j:{pwd}".encode()).decode()
            neo4j_url = "https://38c949a2.databases.neo4j.io/db/neo4j/query/v2"
            queries = [
                ("MATCH (n) RETURN count(n)", "total_nodes"),
                ("MATCH ()-[r]->() RETURN count(r)", "total_relationships"),
                ("MATCH (n) RETURN labels(n)[0] as l, count(*) as c ORDER BY c DESC", "labels"),
                ("MATCH ()-[r]->() RETURN type(r) as t, count(*) as c ORDER BY c DESC", "relationship_types"),
            ]
            for cypher, key in queries:
                req = url_request.Request(neo4j_url,
                    data=json.dumps({"statement": cypher}).encode(),
                    headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json",
                             "Accept": "application/json"}, method="POST")
                with url_request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read())
                    vals = result.get("data", {}).get("values", [])
                    if key in ("labels", "relationship_types"):
                        snapshot["neo4j"][key] = {r[0]: r[1] for r in vals}
                    else:
                        snapshot["neo4j"][key] = vals[0][0] if vals else 0
    except Exception as e:
        snapshot["neo4j"]["error"] = str(e)[:200]
        print(f"  Neo4j snapshot failed: {e}")

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
        snapshot["supabase"] = {
            "tables": tb,
            "total_rows": sum(tb.values()) if tb else 0
        }
    except Exception as e:
        snapshot["supabase"]["error"] = str(e)[:200]
        print(f"  Supabase snapshot failed: {e}")

    # Save to file
    snap_path = os.path.join(SNAP_DIR, f"{snap_id}.json")
    with open(snap_path, "w") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    # Add summary to data.json (keep last 20 snapshots)
    data = _load()
    if "db_snapshots" not in data:
        data["db_snapshots"] = []
    snap_summary = {
        "snapshot_id": snap_id,
        "timestamp": snapshot["timestamp"],
        "trigger": trigger,
        "pinecone_vectors": snapshot["pinecone"].get("total_vectors", 0),
        "neo4j_nodes": snapshot["neo4j"].get("total_nodes", 0),
        "neo4j_relationships": snapshot["neo4j"].get("total_relationships", 0),
        "supabase_rows": snapshot["supabase"].get("total_rows", 0),
        "file": f"logs/db-snapshots/{snap_id}.json"
    }
    data["db_snapshots"].append(snap_summary)
    if len(data["db_snapshots"]) > 20:
        data["db_snapshots"] = data["db_snapshots"][-20:]

    # Also update current DB stats
    if snapshot["pinecone"].get("total_vectors"):
        data["databases"]["pinecone"] = {
            "total_vectors": snapshot["pinecone"]["total_vectors"],
            "namespaces": snapshot["pinecone"].get("namespaces", {})
        }
    if snapshot["neo4j"].get("total_nodes"):
        data["databases"]["neo4j"] = {
            "total_nodes": snapshot["neo4j"]["total_nodes"],
            "total_relationships": snapshot["neo4j"].get("total_relationships", 0),
            "labels": snapshot["neo4j"].get("labels", {}),
            "relationship_types": snapshot["neo4j"].get("relationship_types", {})
        }
    if snapshot["supabase"].get("tables"):
        data["databases"]["supabase"] = snapshot["supabase"]

    _save(data)
    print(f"  DB snapshot saved: {snap_path}")
    return snapshot


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
    """Commit and push data.json + logs to GitHub."""
    repo_root = os.path.dirname(DOCS_DIR)
    subprocess.run(["git", "add", "docs/data.json", "logs/"], cwd=repo_root)
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
    elif "--snapshot-db" in args:
        print("Taking database snapshot...")
        snap = snapshot_databases(trigger="manual")
        print(f"  Done: {snap.get('snapshot_id', '?')}")
    elif "--reset" in args:
        print("Resetting data.json...")
        _save(_default_data())
        print("Done.")
    elif "--push" in args:
        print("Pushing data.json + logs to GitHub...")
        git_push()
    elif "--finish" in args:
        finish()
        print("Marked as complete.")
    else:
        print("Usage: python live-results-writer.py [--update-db|--snapshot-db|--reset|--push|--finish]")
