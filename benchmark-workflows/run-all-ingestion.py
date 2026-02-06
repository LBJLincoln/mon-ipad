#!/usr/bin/env python3
"""
Run ingestion for all 16 benchmark datasets via the n8n BENCHMARK - Dataset Ingestion Pipeline.
Checks execution results via n8n API since webhook response is empty (OTEL node breaks response chain).
"""
import json
import time
import sys
from datetime import datetime
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
INGESTION_WF_ID = "L8irkzSrfLlgt2Bt"

# All 16 datasets matching dataset-results/ files
ALL_DATASETS = [
    # Graph RAG (multi-hop, Neo4j targets)
    {"name": "musique", "sample_size": 200, "rag_target": "graph"},
    {"name": "2wikimultihopqa", "sample_size": 300, "rag_target": "graph"},
    # Quantitative RAG (finance/table, Supabase SQL targets)
    {"name": "finqa", "sample_size": 200, "rag_target": "quantitative"},
    {"name": "tatqa", "sample_size": 150, "rag_target": "quantitative"},
    {"name": "convfinqa", "sample_size": 100, "rag_target": "quantitative"},
    {"name": "wikitablequestions", "sample_size": 50, "rag_target": "quantitative"},
    # Standard RAG benchmarks
    {"name": "hotpotqa", "sample_size": 1000, "rag_target": "standard"},
    {"name": "frames", "sample_size": 1000, "rag_target": "standard"},
    {"name": "triviaqa", "sample_size": 1000, "rag_target": "standard"},
    {"name": "squad_v2", "sample_size": 1000, "rag_target": "standard"},
    {"name": "popqa", "sample_size": 1000, "rag_target": "standard"},
    {"name": "msmarco", "sample_size": 1000, "rag_target": "standard"},
    {"name": "asqa", "sample_size": 1000, "rag_target": "standard"},
    {"name": "narrativeqa", "sample_size": 1000, "rag_target": "standard"},
    {"name": "pubmedqa", "sample_size": 500, "rag_target": "standard"},
    {"name": "natural_questions", "sample_size": 1000, "rag_target": "standard"},
]


def api_get(endpoint, timeout=30):
    """GET from n8n API."""
    url = f"{N8N_HOST}/api/v1{endpoint}"
    req = request.Request(url, headers={
        "X-N8N-API-KEY": N8N_API_KEY,
        "Accept": "application/json"
    })
    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                return None


def trigger_webhook(data, timeout=180):
    """Trigger the benchmark-ingest webhook."""
    url = f"{N8N_HOST}/webhook/benchmark-ingest"
    body = json.dumps(data).encode()
    req = request.Request(url, data=body, headers={
        "Content-Type": "application/json"
    }, method="POST")
    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw.strip() else {"triggered": True}
        except error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            return {"error": f"HTTP {e.code}: {body[:200]}"}
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return {"error": str(e)}


def get_last_execution():
    """Get the most recent execution for the ingestion workflow."""
    data = api_get(f"/executions?limit=1&workflowId={INGESTION_WF_ID}")
    if data and data.get("data"):
        return data["data"][0]
    return None


def get_execution_detail(exec_id):
    """Get detailed execution data including node results."""
    return api_get(f"/executions/{exec_id}?includeData=true", timeout=60)


def analyze_execution(exec_detail):
    """Analyze execution to extract results."""
    if not exec_detail:
        return {"status": "unknown", "error": "No execution data"}

    run_data = exec_detail.get("data", {}).get("resultData", {}).get("runData", {})
    wf_error = exec_detail.get("data", {}).get("resultData", {}).get("error")

    result = {
        "exec_id": exec_detail.get("id"),
        "status": exec_detail.get("status"),
        "started": exec_detail.get("startedAt"),
        "stopped": exec_detail.get("stoppedAt"),
        "nodes_executed": list(run_data.keys()),
        "supabase_ok": False,
        "pinecone_ok": False,
        "neo4j_ok": False,
        "items_parsed": 0,
        "errors": []
    }

    if wf_error:
        result["errors"].append(f"Workflow error: {str(wf_error)[:200]}")

    # Check each node
    for node_name, runs in run_data.items():
        for r in runs:
            err = r.get("error")
            main_data = r.get("data", {}).get("main", [])

            if node_name == "Parse & Normalize Dataset":
                if main_data and main_data[0]:
                    j = main_data[0][0].get("json", {})
                    result["items_parsed"] = j.get("total_items", 0)

            elif node_name == "Supabase: Store Q&A":
                if main_data and main_data[0] and not err:
                    result["supabase_ok"] = True
                elif main_data and len(main_data) > 1 and main_data[1]:
                    result["errors"].append(f"Supabase error")

            elif node_name == "Pinecone: Upsert Vectors":
                if main_data and main_data[0] and not err:
                    result["pinecone_ok"] = True

            elif node_name == "Neo4j: Store Graph Nodes":
                if main_data and main_data[0] and not err:
                    result["neo4j_ok"] = True

            elif node_name == "Final Summary":
                if main_data and main_data[0]:
                    j = main_data[0][0].get("json", {})
                    result["run_id"] = j.get("run_id", "")
                    result["total_items"] = j.get("total_items", 0)
                    result["duration_ms"] = j.get("duration_ms", 0)

            if err:
                msg = err.get("message", str(err))[:200] if isinstance(err, dict) else str(err)[:200]
                # Skip known non-critical errors
                if "OTEL" not in node_name and "Trace" not in node_name:
                    result["errors"].append(f"{node_name}: {msg}")

    return result


def update_result_file(ds_name, rag_target, exec_result):
    """Update the dataset result file with ingestion status."""
    import os

    # Map to result file names
    result_files = {
        "finqa": ["results-finqa.json", "results-finqa-quantitative.json"],
    }
    default_file = f"results-{ds_name}.json"
    files = result_files.get(ds_name, [default_file])

    results_dir = "/home/user/mon-ipad/dataset-results"
    for fname in files:
        filepath = os.path.join(results_dir, fname)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath) as f:
                data = json.load(f)
        except Exception:
            continue

        dv = data.get("data_verification", {})
        dv["ingestion_status"] = "completed" if exec_result.get("supabase_ok") else "partial"
        dv["ingestion_run_id"] = exec_result.get("run_id", "")
        dv["items_ingested"] = exec_result.get("items_parsed", 0)
        dv["ingested_at"] = exec_result.get("stopped", "")
        dv["supabase_ready"] = exec_result.get("supabase_ok", False)
        dv["pinecone_ready"] = exec_result.get("pinecone_ok", False)
        dv["neo4j_ready"] = exec_result.get("neo4j_ok", False)
        dv["exec_id"] = exec_result.get("exec_id", "")
        if exec_result.get("errors"):
            dv["ingestion_errors"] = exec_result["errors"]

        data["data_verification"] = dv
        data["last_updated"] = datetime.now().isoformat()

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"      Updated: {fname}")


if __name__ == "__main__":
    print("=" * 70)
    print("RAG BENCHMARK — PUSH ALL DATASETS VIA BENCHMARK WORKFLOWS")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Datasets: {len(ALL_DATASETS)}")
    print(f"Target Q&A: {sum(d['sample_size'] for d in ALL_DATASETS)}")
    print("=" * 70)

    all_results = []
    total_items = 0

    for idx, ds in enumerate(ALL_DATASETS):
        name = ds["name"]
        size = ds["sample_size"]
        rag = ds["rag_target"]

        print(f"\n  [{idx+1}/{len(ALL_DATASETS)}] {name} ({rag}, {size} items)")

        # Get current execution count to detect new execution
        before_exec = get_last_execution()
        before_id = before_exec.get("id") if before_exec else "0"

        # Trigger ingestion — disable embeddings to avoid OpenAI auth error
        # Neo4j only for graph-targeted datasets
        payload = {
            "dataset_name": name,
            "sample_size": size,
            "batch_size": min(50, size),
            "generate_embeddings": False,
            "include_neo4j": rag == "graph",
            "tenant_id": "benchmark"
        }

        start = time.time()
        resp = trigger_webhook(payload, timeout=300)
        elapsed = time.time() - start

        # Wait briefly for execution to register
        time.sleep(2)

        # Get the execution that just ran
        after_exec = get_last_execution()
        exec_id = after_exec.get("id") if after_exec else None

        if exec_id and exec_id != before_id:
            # Get detailed results
            detail = get_execution_detail(exec_id)
            result = analyze_execution(detail)
            result["name"] = name
            result["rag_target"] = rag
            result["elapsed_s"] = round(elapsed, 1)

            items = result.get("items_parsed", 0) or result.get("total_items", 0)
            total_items += items

            sb = "OK" if result.get("supabase_ok") else "FAIL"
            pc = "OK" if result.get("pinecone_ok") else "SKIP"
            n4j = "OK" if result.get("neo4j_ok") else ("SKIP" if rag != "graph" else "FAIL")

            print(f"    Items: {items} | Supabase: {sb} | Pinecone: {pc} | Neo4j: {n4j} | {result['elapsed_s']}s")
            if result.get("errors"):
                for e in result["errors"][:3]:
                    print(f"    ⚠ {e[:100]}")

            # Update result file
            update_result_file(name, rag, result)
            all_results.append(result)
        else:
            print(f"    WARNING: Could not detect execution (response: {str(resp)[:100]})")
            all_results.append({"name": name, "status": "unknown", "elapsed_s": round(elapsed, 1)})

        # Brief pause between datasets
        if idx < len(ALL_DATASETS) - 1:
            time.sleep(1)

    # Summary
    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    supabase_ok = sum(1 for r in all_results if r.get("supabase_ok"))
    print(f"  Datasets processed: {len(all_results)}/{len(ALL_DATASETS)}")
    print(f"  Supabase ingested:  {supabase_ok}/{len(ALL_DATASETS)}")
    print(f"  Total items:        {total_items}")
    print()

    for r in all_results:
        st = "OK" if r.get("supabase_ok") else "??"
        items = r.get("items_parsed", 0) or r.get("total_items", 0)
        print(f"  [{st}] {r.get('name','?'):25s} {items:5d} items | {r.get('elapsed_s',0):.0f}s")

    print("=" * 70)

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_datasets": len(ALL_DATASETS),
        "supabase_ok_count": supabase_ok,
        "total_items_ingested": total_items,
        "results": all_results
    }
    with open("/home/user/mon-ipad/benchmark-workflows/ingestion-run-results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved: benchmark-workflows/ingestion-run-results.json")
