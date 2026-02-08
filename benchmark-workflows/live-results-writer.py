#!/usr/bin/env python3
"""
Live Results Writer v2 — Iteration-aware dashboard data writer.

Updates docs/data.json (v2 format) with:
- iterations[]: grouped test runs with per-question results
- question_registry{}: unique questions with cross-iteration history
- pipelines{}: endpoint + target + trend data
- quick_tests[]: endpoint smoke test results

Usage from eval scripts:
    from importlib.machinery import SourceFileLoader
    writer = SourceFileLoader("w", "benchmark-workflows/live-results-writer.py").load_module()
    writer.init(label="Iteration 4", description="After topK increase")
    writer.record_question(rag_type, question_id, question_text, correct, f1, latency_ms, ...)
    writer.record_execution(rag_type, question_id, ...)  # detailed trace to JSONL
    writer.record_quick_test(pipeline, query, status, latency_ms, response_preview)
    writer.snapshot_databases()
    writer.record_workflow_change(description, ...)
    writer.finish()

Or standalone:
    python live-results-writer.py --update-db
    python live-results-writer.py --snapshot-db
    python live-results-writer.py --reset
    python live-results-writer.py --push
"""
import json
import os
import sys
import time
import subprocess
from datetime import datetime
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
LOGS_DIR = os.path.join(REPO_ROOT, "logs")
EXEC_DIR = os.path.join(LOGS_DIR, "executions")
ERR_DIR = os.path.join(LOGS_DIR, "errors")
SNAP_DIR = os.path.join(LOGS_DIR, "db-snapshots")
DATA_FILE = os.path.join(DOCS_DIR, "data.json")

# Ensure directories exist
for d in [EXEC_DIR, ERR_DIR, SNAP_DIR]:
    os.makedirs(d, exist_ok=True)

# Current session state
_session_id = None
_exec_log_path = None
_iteration_id = None


def _load():
    """Load data.json."""
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
            "version": "2.0",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "status": "idle",
            "project": "Multi-RAG Orchestrator SOTA 2026",
            "phase": "Phase 1 — Baseline (200q)",
            "total_unique_questions": 0,
            "total_test_runs": 0,
            "total_iterations": 0,
            "total_cost_usd": 0,
        },
        "iterations": [],
        "question_registry": {},
        "pipelines": {
            "standard": {
                "endpoint": "https://amoret.app.n8n.cloud/webhook/rag-multi-index-v3",
                "target_accuracy": 85.0,
                "trend": [],
            },
            "graph": {
                "endpoint": "https://amoret.app.n8n.cloud/webhook/ff622742-6d71-4e91-af71-b5c666088717",
                "target_accuracy": 70.0,
                "trend": [],
            },
            "quantitative": {
                "endpoint": "https://amoret.app.n8n.cloud/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
                "target_accuracy": 85.0,
                "trend": [],
            },
            "orchestrator": {
                "endpoint": "https://amoret.app.n8n.cloud/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
                "target_accuracy": 70.0,
                "trend": [],
            },
        },
        "workflow_changes": [],
        "databases": {"pinecone": {}, "neo4j": {}, "supabase": {}},
        "db_snapshots": [],
        "execution_logs": [],
        "quick_tests": [],
        "history": [],
    }


def _sanitize(val, max_len=500):
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


def _ensure_v2(data):
    """Ensure data.json has v2 fields. Migrate if needed."""
    if "iterations" not in data:
        data["iterations"] = []
    if "question_registry" not in data:
        data["question_registry"] = {}
    if "quick_tests" not in data:
        data["quick_tests"] = []
    if "meta" not in data:
        data["meta"] = {}
    data["meta"].setdefault("version", "2.0")
    data["meta"].setdefault("total_unique_questions", len(data.get("question_registry", {})))
    data["meta"].setdefault("total_test_runs", 0)
    data["meta"].setdefault("total_iterations", len(data.get("iterations", [])))
    return data


def _get_current_iteration(data):
    """Get or create the current iteration object."""
    if not data["iterations"] or data["iterations"][-1]["id"] != _iteration_id:
        # Create new iteration
        iter_num = len(data["iterations"]) + 1
        data["iterations"].append({
            "id": _iteration_id,
            "number": iter_num,
            "timestamp_start": datetime.utcnow().isoformat() + "Z",
            "timestamp_end": None,
            "label": f"Iteration {iter_num}",
            "description": "",
            "changes_applied": [],
            "results_summary": {},
            "total_tested": 0,
            "total_correct": 0,
            "overall_accuracy_pct": 0,
            "questions": [],
        })
    return data["iterations"][-1]


def _recompute_iteration_summary(iteration):
    """Recompute results_summary from questions list."""
    by_type = defaultdict(lambda: {"tested": 0, "correct": 0, "errors": 0, "latencies": [], "f1s": []})
    for q in iteration["questions"]:
        rt = q["rag_type"]
        by_type[rt]["tested"] += 1
        if q.get("correct"):
            by_type[rt]["correct"] += 1
        if q.get("error"):
            by_type[rt]["errors"] += 1
        if q.get("latency_ms", 0) > 0:
            by_type[rt]["latencies"].append(q["latency_ms"])
        if q.get("f1", 0) > 0:
            by_type[rt]["f1s"].append(q["f1"])

    iteration["results_summary"] = {}
    for rt, info in by_type.items():
        lats = sorted(info["latencies"])
        iteration["results_summary"][rt] = {
            "tested": info["tested"],
            "correct": info["correct"],
            "errors": info["errors"],
            "accuracy_pct": round(info["correct"] / info["tested"] * 100, 1) if info["tested"] > 0 else 0,
            "avg_latency_ms": int(sum(lats) / len(lats)) if lats else 0,
            "p95_latency_ms": lats[int(len(lats) * 0.95)] if len(lats) > 1 else (lats[0] if lats else 0),
            "avg_f1": round(sum(info["f1s"]) / len(info["f1s"]), 4) if info["f1s"] else 0,
        }

    total = len(iteration["questions"])
    correct = sum(1 for q in iteration["questions"] if q.get("correct"))
    iteration["total_tested"] = total
    iteration["total_correct"] = correct
    iteration["overall_accuracy_pct"] = round(correct / total * 100, 1) if total > 0 else 0


def _update_question_registry(data, qid, rag_type, question_text, expected, correct, f1,
                               latency_ms, match_type, error, error_type, answer, category=""):
    """Update the question registry with a new run result."""
    reg = data.setdefault("question_registry", {})

    if qid not in reg:
        reg[qid] = {
            "id": qid,
            "question": question_text[:300],
            "expected": expected[:300],
            "expected_detail": "",
            "rag_type": rag_type,
            "category": category,
            "entities": [],
            "tables": [],
            "runs": [],
        }

    reg[qid]["runs"].append({
        "iteration_id": _iteration_id,
        "iteration_number": len(data.get("iterations", [])),
        "correct": bool(correct),
        "f1": round(f1, 4),
        "latency_ms": int(latency_ms),
        "match_type": match_type,
        "error": _sanitize(error, 200) if error else None,
        "error_type": error_type,
        "answer": _sanitize(answer, 500),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })

    # Recompute summary fields
    runs = reg[qid]["runs"]
    reg[qid]["total_runs"] = len(runs)
    reg[qid]["pass_count"] = sum(1 for r in runs if r["correct"])
    reg[qid]["pass_rate"] = round(reg[qid]["pass_count"] / len(runs), 3)
    reg[qid]["current_status"] = "pass" if runs[-1]["correct"] else ("error" if runs[-1].get("error") else "fail")
    reg[qid]["last_tested"] = runs[-1]["timestamp"]
    reg[qid]["best_f1"] = max(r["f1"] for r in runs)

    # Trend: compare first and last run
    if len(runs) >= 2:
        if not runs[0]["correct"] and runs[-1]["correct"]:
            reg[qid]["trend"] = "improving"
        elif runs[0]["correct"] and not runs[-1]["correct"]:
            reg[qid]["trend"] = "regressing"
        else:
            reg[qid]["trend"] = "stable"
    else:
        reg[qid]["trend"] = "stable"


def _update_pipeline_trends(data):
    """Update pipeline trend data from iterations."""
    for rt in ["standard", "graph", "quantitative", "orchestrator"]:
        trend = []
        for iteration in data.get("iterations", []):
            rs = iteration.get("results_summary", {}).get(rt)
            if rs:
                trend.append({
                    "iteration_id": iteration["id"],
                    "iteration_number": iteration["number"],
                    "accuracy_pct": rs["accuracy_pct"],
                    "tested": rs["tested"],
                    "errors": rs["errors"],
                    "avg_latency_ms": rs["avg_latency_ms"],
                })
        if rt in data.get("pipelines", {}):
            data["pipelines"][rt]["trend"] = trend


def _update_meta(data):
    """Recompute meta counters."""
    data["meta"]["total_unique_questions"] = len(data.get("question_registry", {}))
    data["meta"]["total_test_runs"] = sum(
        len(q.get("runs", [])) for q in data.get("question_registry", {}).values()
    )
    data["meta"]["total_iterations"] = len(data.get("iterations", []))


# ============================================================
# Public API
# ============================================================

def init(status="running", label="", description="", changes=None):
    """Initialize a new eval session/iteration.

    Args:
        label: Human-readable label for this iteration (e.g., "After topK increase")
        description: Longer description of what changed
        changes: List of change descriptions applied before this iteration
    """
    global _session_id, _exec_log_path, _iteration_id
    _session_id = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    _exec_log_path = os.path.join(EXEC_DIR, f"exec-{_session_id}.jsonl")
    _iteration_id = f"iter-{_session_id}"

    data = _load()
    data = _ensure_v2(data)
    data["meta"]["status"] = status
    data["meta"]["current_session"] = _session_id

    # Create the iteration
    iter_num = len(data["iterations"]) + 1
    data["iterations"].append({
        "id": _iteration_id,
        "number": iter_num,
        "timestamp_start": datetime.utcnow().isoformat() + "Z",
        "timestamp_end": None,
        "label": label or f"Iteration {iter_num}",
        "description": description,
        "changes_applied": changes or [],
        "results_summary": {},
        "total_tested": 0,
        "total_correct": 0,
        "overall_accuracy_pct": 0,
        "questions": [],
    })

    _save(data)
    return data


def record_question(rag_type, question_id, question_text, correct, f1=0,
                    latency_ms=0, error=None, cost_usd=0, expected="", answer="",
                    match_type="", category=""):
    """Record a single question result into the current iteration + question registry."""
    data = _load()
    data = _ensure_v2(data)

    error_type = _classify_error(str(error) if error else None, latency_ms)

    # Add to current iteration's questions list
    iteration = _get_current_iteration(data)
    iteration["questions"].append({
        "id": question_id,
        "rag_type": rag_type,
        "correct": bool(correct),
        "f1": round(f1, 4),
        "latency_ms": int(latency_ms),
        "answer": _sanitize(answer, 500),
        "expected": _sanitize(expected, 300),
        "match_type": match_type,
        "error": _sanitize(error, 200) if error else None,
        "error_type": error_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })
    iteration["timestamp_end"] = datetime.utcnow().isoformat() + "Z"

    # Recompute iteration summary
    _recompute_iteration_summary(iteration)

    # Update question registry
    _update_question_registry(data, question_id, rag_type, question_text, expected,
                               correct, f1, latency_ms, match_type, error, error_type, answer, category)

    # Update pipeline trends
    _update_pipeline_trends(data)

    # Update meta
    _update_meta(data)
    data["meta"]["status"] = "running"

    _save(data)


def record_execution(rag_type, question_id, question_text, expected="",
                     input_payload=None, raw_response=None, extracted_answer="",
                     correct=False, f1=0, match_type="", latency_ms=0,
                     http_status=None, response_size=0, error=None,
                     cost_usd=0, pipeline_details=None):
    """Record a detailed execution trace to the JSONL log file + error file if applicable."""
    error_type = _classify_error(str(error) if error else None, latency_ms, http_status)

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
            "payload": json.dumps(input_payload)[:500] if input_payload else None,
        },
        "output": {
            "raw_response_preview": raw_resp_str,
            "extracted_answer": extracted_answer[:500],
            "confidence": None,
            "engine": rag_type.upper(),
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
            "cost_usd": round(cost_usd, 6),
        },
        "error": {
            "type": error_type,
            "message": _sanitize(error, 500),
        } if error else None,
    }

    if raw_response and isinstance(raw_response, dict):
        entry["output"]["confidence"] = raw_response.get("confidence")

    # Write to JSONL execution log
    if _exec_log_path:
        with open(_exec_log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Write error trace file
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
            "expected": expected[:300],
        }
        with open(err_path, "w") as f:
            json.dump(err_trace, f, indent=2, ensure_ascii=False)

    # Update execution_logs summary in data.json (last 200)
    data = _load()
    data = _ensure_v2(data)
    if "execution_logs" not in data:
        data["execution_logs"] = []
    data["execution_logs"].append({
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
        "pipeline_details_summary": _summarize_pipeline_details(rag_type, pipeline_details),
    })
    if len(data["execution_logs"]) > 200:
        data["execution_logs"] = data["execution_logs"][-200:]
    _save(data)

    return entry


def _summarize_pipeline_details(rag_type, details):
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


def record_quick_test(pipeline, query, status, latency_ms, response_preview="",
                      trigger="manual", error=None):
    """Record a quick endpoint smoke test result.

    Args:
        pipeline: "standard"|"graph"|"quantitative"|"orchestrator"
        query: The test question used
        status: "pass"|"fail"|"error"
        latency_ms: Response time
        response_preview: First 200 chars of response
        trigger: "post-deployment"|"manual"|"pre-eval"
    """
    data = _load()
    data = _ensure_v2(data)
    data["quick_tests"].append({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pipeline": pipeline,
        "query": query[:200],
        "status": status,
        "latency_ms": int(latency_ms),
        "response_preview": _sanitize(response_preview, 200),
        "trigger": trigger,
        "error": _sanitize(error, 200) if error else None,
    })
    # Keep last 50 quick tests
    if len(data["quick_tests"]) > 50:
        data["quick_tests"] = data["quick_tests"][-50:]
    _save(data)


def record_workflow_change(description, files_changed=None, before_metrics=None,
                           after_metrics=None, change_type="modification",
                           affected_pipelines=None):
    """Record a workflow modification event."""
    data = _load()
    data = _ensure_v2(data)
    change = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "description": description,
        "change_type": change_type,
        "files_changed": files_changed or [],
        "affected_pipelines": affected_pipelines or [],
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
    }
    data["workflow_changes"].append(change)
    _save(data)
    return change


def snapshot_databases(trigger="manual"):
    """Take a snapshot of all database states."""
    snap_id = f"snap-{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}"
    snapshot = {
        "snapshot_id": snap_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "trigger": trigger,
        "pinecone": {},
        "neo4j": {},
        "supabase": {},
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
                    "namespaces": {k: v.get("vectorCount", 0) for k, v in stats.get("namespaces", {}).items()},
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
        snapshot["supabase"] = {"tables": tb, "total_rows": sum(tb.values()) if tb else 0}
    except Exception as e:
        snapshot["supabase"]["error"] = str(e)[:200]
        print(f"  Supabase snapshot failed: {e}")

    # Save to file
    snap_path = os.path.join(SNAP_DIR, f"{snap_id}.json")
    with open(snap_path, "w") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    # Add to data.json (keep last 20)
    data = _load()
    data = _ensure_v2(data)
    snap_summary = {
        "snapshot_id": snap_id,
        "timestamp": snapshot["timestamp"],
        "trigger": trigger,
        "pinecone_vectors": snapshot["pinecone"].get("total_vectors", 0),
        "neo4j_nodes": snapshot["neo4j"].get("total_nodes", 0),
        "neo4j_relationships": snapshot["neo4j"].get("total_relationships", 0),
        "supabase_rows": snapshot["supabase"].get("total_rows", 0),
        "file": f"logs/db-snapshots/{snap_id}.json",
    }
    data["db_snapshots"].append(snap_summary)
    if len(data["db_snapshots"]) > 20:
        data["db_snapshots"] = data["db_snapshots"][-20:]

    # Update current DB stats
    if snapshot["pinecone"].get("total_vectors"):
        data["databases"]["pinecone"] = {
            "total_vectors": snapshot["pinecone"]["total_vectors"],
            "namespaces": snapshot["pinecone"].get("namespaces", {}),
        }
    if snapshot["neo4j"].get("total_nodes"):
        data["databases"]["neo4j"] = {
            "total_nodes": snapshot["neo4j"]["total_nodes"],
            "total_relationships": snapshot["neo4j"].get("total_relationships", 0),
            "labels": snapshot["neo4j"].get("labels", {}),
            "relationship_types": snapshot["neo4j"].get("relationship_types", {}),
        }
    if snapshot["supabase"].get("tables"):
        data["databases"]["supabase"] = snapshot["supabase"]

    _save(data)
    print(f"  DB snapshot saved: {snap_path}")
    return snapshot


def update_db_stats():
    """Probe all 3 databases and update stats in data.json."""
    return snapshot_databases(trigger="stats-update")


def finish(event="eval_complete"):
    """Mark evaluation as complete."""
    data = _load()
    data = _ensure_v2(data)
    data["meta"]["status"] = "complete"

    # Close the current iteration
    if data["iterations"]:
        iteration = data["iterations"][-1]
        iteration["timestamp_end"] = datetime.utcnow().isoformat() + "Z"

    # Add history point
    accs = {}
    if data["iterations"]:
        latest = data["iterations"][-1]
        for rt, rs in latest.get("results_summary", {}).items():
            accs[rt] = rs["accuracy_pct"]

    point = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "total_tested": data["meta"].get("total_test_runs", 0),
    }
    point.update(accs)
    data.setdefault("history", []).append(point)

    _save(data)


def git_push(message="Update dashboard data"):
    """Commit and push data.json + logs to GitHub."""
    repo_root = os.path.dirname(DOCS_DIR)
    subprocess.run(["git", "add", "docs/data.json", "docs/tested-questions.json", "logs/"], cwd=repo_root)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_root)
    subprocess.run(["git", "push"], cwd=repo_root)


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    args = sys.argv[1:]
    if "--update-db" in args:
        print("Updating database stats...")
        snap = update_db_stats()
        print(f"  Done: {snap.get('snapshot_id', '?')}")
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
