#!/usr/bin/env python3
"""
Push All Benchmark Datasets via n8n Benchmark Workflows.

Steps:
1. Deploy all 4 Benchmark workflows to n8n cloud (create or update + activate)
2. Trigger WF-Benchmark-Dataset-Ingestion for each dataset via webhook
3. Track results and update dataset-results/ files
4. Trigger WF-Benchmark-RAG-Tester for ready datasets
5. Trigger WF-Benchmark-Orchestrator-Tester for routing evaluation
"""
import json
import os
import sys
import time
import copy
from datetime import datetime
from urllib import request, error, parse

# ============================================================
# Configuration
# ============================================================
N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKFLOWS_DIR = os.path.join(REPO_ROOT, "workflows")
RESULTS_DIR = os.path.join(REPO_ROOT, "dataset-results")

WORKFLOW_FILES = [
    "WF-Benchmark-Dataset-Ingestion.json",
    "WF-Benchmark-RAG-Tester.json",
    "WF-Benchmark-Orchestrator-Tester.json",
    "WF-Benchmark-Monitoring.json",
]

# All datasets to ingest — ordered by priority (most complex first)
ALL_DATASETS = [
    # TIER 1: Graph RAG (Multi-Hop) — needs Neo4j
    {"name": "musique", "sample_size": 200, "include_neo4j": True, "rag_target": "graph"},
    {"name": "2wikimultihopqa", "sample_size": 300, "include_neo4j": True, "rag_target": "graph"},
    {"name": "hotpotqa", "sample_size": 1000, "include_neo4j": True, "rag_target": "standard"},
    # TIER 2: Quantitative RAG — needs Supabase SQL tables
    {"name": "finqa", "sample_size": 200, "rag_target": "quantitative"},
    {"name": "tatqa", "sample_size": 150, "rag_target": "quantitative"},
    {"name": "convfinqa", "sample_size": 100, "rag_target": "quantitative"},
    {"name": "wikitablequestions", "sample_size": 50, "rag_target": "quantitative"},
    # TIER 3: Standard RAG Benchmarks
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


def api_request(method, endpoint, data=None, timeout=60):
    """Make a request to the n8n REST API."""
    url = f"{N8N_HOST}/api/v1{endpoint}"
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode('utf-8') if data else None
    req = request.Request(url, data=body, headers=headers, method=method)
    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                response_data = resp.read().decode('utf-8')
                return {"status": resp.status, "data": json.loads(response_data) if response_data else None}
        except error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            return {"status": e.code, "error": str(e), "body": error_body}
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return {"status": 0, "error": str(e)}


def webhook_request(path, data, timeout=120):
    """Trigger an n8n webhook."""
    url = f"{N8N_HOST}/webhook/{path}"
    body = json.dumps(data).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    req = request.Request(url, data=body, headers=headers, method="POST")
    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                response_data = resp.read().decode('utf-8')
                return {"status": resp.status, "data": json.loads(response_data) if response_data else None}
        except error.HTTPError as e:
            error_body = ''
            try:
                error_body = e.read().decode('utf-8')
            except Exception:
                pass
            return {"status": e.code, "error": str(e), "body": error_body}
        except Exception as e:
            if attempt < 2:
                print(f"      Retry {attempt+1}/3: {e}")
                time.sleep(2 ** (attempt + 1))
                continue
            return {"status": 0, "error": str(e)}


def prepare_workflow(wf_data):
    """Strip workflow JSON to only n8n-accepted fields."""
    ALLOWED_TOP_LEVEL = {"name", "nodes", "connections", "settings"}
    prepared = {}
    for key in ALLOWED_TOP_LEVEL:
        if key in wf_data:
            prepared[key] = copy.deepcopy(wf_data[key])
    if "settings" in prepared:
        for field in ["timeSavedMode", "saveExecutionProgress", "saveManualExecutions"]:
            prepared["settings"].pop(field, None)
    if "name" not in prepared:
        prepared["name"] = "Unnamed Workflow"
    if "nodes" not in prepared:
        prepared["nodes"] = []
    if "connections" not in prepared:
        prepared["connections"] = {}
    for node in prepared.get("nodes", []):
        if "id" not in node:
            import uuid
            node["id"] = str(uuid.uuid4())
        if "typeVersion" not in node:
            node["typeVersion"] = 1
        if "position" not in node:
            node["position"] = [0, 0]
        for key in list(node.keys()):
            if key.startswith('_'):
                del node[key]
    return prepared


# ============================================================
# PHASE 1: Deploy Benchmark Workflows
# ============================================================
def deploy_workflows():
    """Deploy all 4 benchmark workflows to n8n cloud."""
    print("\n" + "=" * 70)
    print("PHASE 1: DEPLOYING BENCHMARK WORKFLOWS TO N8N")
    print("=" * 70)

    # Get existing workflows
    resp = api_request("GET", "/workflows?limit=100")
    existing = {}
    if resp.get("data"):
        for wf in resp["data"].get("data", []):
            existing[wf["name"]] = wf["id"]
        print(f"  Found {len(existing)} existing workflows on n8n")

    results = {}
    for filename in WORKFLOW_FILES:
        filepath = os.path.join(WORKFLOWS_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  SKIP: {filename} not found")
            continue

        with open(filepath, 'r') as f:
            wf_data = json.load(f)

        wf_name = wf_data.get("name", filename)
        prepared = prepare_workflow(wf_data)

        print(f"\n  Processing: {wf_name}")

        if wf_name in existing:
            wf_id = existing[wf_name]
            print(f"    Updating existing workflow: {wf_id}")
            resp = api_request("PUT", f"/workflows/{wf_id}", prepared)
        else:
            print(f"    Creating new workflow...")
            resp = api_request("POST", "/workflows", prepared)

        if resp.get("data"):
            wf_id = resp["data"].get("id", "?")
            print(f"    SUCCESS: ID={wf_id}")
            results[filename] = {"id": wf_id, "status": "deployed", "name": wf_name}

            # Activate the workflow
            activate_resp = api_request("PATCH", f"/workflows/{wf_id}", {"active": True})
            if activate_resp.get("data", {}).get("active"):
                print(f"    ACTIVATED")
                results[filename]["active"] = True
            else:
                print(f"    Warning: Could not activate (may need credential config)")
                results[filename]["active"] = False
        else:
            err = resp.get("error", resp.get("body", "unknown error"))
            print(f"    FAILED: {err[:200]}")
            results[filename] = {"status": "error", "error": str(err)[:200]}

    return results


# ============================================================
# PHASE 2: Trigger Dataset Ingestion
# ============================================================
def ingest_all_datasets():
    """Trigger WF-Benchmark-Dataset-Ingestion for each dataset."""
    print("\n" + "=" * 70)
    print("PHASE 2: TRIGGERING DATASET INGESTION VIA BENCHMARK WORKFLOW")
    print("=" * 70)
    print(f"  Total datasets: {len(ALL_DATASETS)}")
    print(f"  Total target Q&A: {sum(d['sample_size'] for d in ALL_DATASETS)}")

    ingestion_results = []

    for idx, ds in enumerate(ALL_DATASETS):
        name = ds["name"]
        size = ds["sample_size"]
        print(f"\n  [{idx+1}/{len(ALL_DATASETS)}] Ingesting: {name} ({size} items)")
        print(f"    RAG target: {ds.get('rag_target', 'standard')}")
        print(f"    Neo4j: {ds.get('include_neo4j', False)}")

        start_time = time.time()

        payload = {
            "dataset_name": name,
            "sample_size": size,
            "batch_size": 50,
            "include_neo4j": ds.get("include_neo4j", False),
            "generate_embeddings": True,
            "tenant_id": "benchmark"
        }

        resp = webhook_request("benchmark-ingest", payload, timeout=300)
        elapsed = time.time() - start_time

        result = {
            "name": name,
            "sample_size": size,
            "rag_target": ds.get("rag_target", "standard"),
            "duration_s": round(elapsed, 1),
            "timestamp": datetime.now().isoformat()
        }

        if resp.get("data"):
            data = resp["data"]
            result["status"] = "completed"
            result["run_id"] = data.get("run_id", "")
            result["total_items"] = data.get("total_items", 0)
            result["webhook_response"] = data
            print(f"    SUCCESS: {data.get('total_items', '?')} items ingested in {result['duration_s']}s")
            print(f"    Run ID: {data.get('run_id', '?')}")
        else:
            result["status"] = "error"
            result["error"] = resp.get("error", resp.get("body", "unknown"))[:500]
            print(f"    ERROR: {result['error'][:200]}")

        ingestion_results.append(result)

        # Brief pause between datasets to avoid overwhelming n8n
        if idx < len(ALL_DATASETS) - 1:
            time.sleep(2)

    return ingestion_results


# ============================================================
# PHASE 3: Trigger RAG Testing for ingested datasets
# ============================================================
def test_rag_datasets(ingestion_results):
    """Trigger WF-Benchmark-RAG-Tester for successfully ingested datasets."""
    print("\n" + "=" * 70)
    print("PHASE 3: TRIGGERING RAG TESTS VIA BENCHMARK WORKFLOW")
    print("=" * 70)

    completed = [r for r in ingestion_results if r.get("status") == "completed"]
    print(f"  Datasets ready for testing: {len(completed)}/{len(ingestion_results)}")

    test_results = []
    for idx, ds in enumerate(completed):
        name = ds["name"]
        rag_target = ds.get("rag_target", "standard")
        print(f"\n  [{idx+1}/{len(completed)}] Testing: {name} (rag_target={rag_target})")

        payload = {
            "dataset_name": name,
            "test_type": "e2e",
            "rag_target": rag_target,
            "sample_size": min(ds.get("sample_size", 100), 100),  # Test first 100
            "batch_size": 10,
            "tenant_id": "benchmark"
        }

        start_time = time.time()
        resp = webhook_request("benchmark-test-rag", payload, timeout=300)
        elapsed = time.time() - start_time

        result = {
            "name": name,
            "rag_target": rag_target,
            "duration_s": round(elapsed, 1),
            "timestamp": datetime.now().isoformat()
        }

        if resp.get("data"):
            data = resp["data"]
            result["status"] = "completed"
            result["run_id"] = data.get("run_id", "")
            result["metrics"] = data.get("aggregate_metrics", {})
            print(f"    SUCCESS in {result['duration_s']}s")
        else:
            result["status"] = "error"
            result["error"] = resp.get("error", resp.get("body", "unknown"))[:500]
            print(f"    ERROR: {result['error'][:200]}")

        test_results.append(result)
        time.sleep(1)

    return test_results


# ============================================================
# PHASE 4: Trigger Orchestrator Tests
# ============================================================
def test_orchestrator(ingestion_results):
    """Trigger WF-Benchmark-Orchestrator-Tester for routing evaluation."""
    print("\n" + "=" * 70)
    print("PHASE 4: TRIGGERING ORCHESTRATOR ROUTING TESTS")
    print("=" * 70)

    # Test a sample from each category
    categories = {}
    for r in ingestion_results:
        if r.get("status") == "completed":
            cat = r.get("rag_target", "standard")
            if cat not in categories:
                categories[cat] = r["name"]

    print(f"  Testing {len(categories)} routing categories: {list(categories.keys())}")

    orch_results = []
    for cat, ds_name in categories.items():
        print(f"\n  Testing orchestrator routing for: {ds_name} (expected: {cat})")

        payload = {
            "dataset_name": ds_name,
            "test_mode": "routing_eval",
            "sample_size": 20,
            "batch_size": 10,
            "tenant_id": "benchmark"
        }

        start_time = time.time()
        resp = webhook_request("benchmark-test-orchestrator", payload, timeout=180)
        elapsed = time.time() - start_time

        result = {
            "name": ds_name,
            "expected_routing": cat,
            "duration_s": round(elapsed, 1),
            "timestamp": datetime.now().isoformat()
        }

        if resp.get("data"):
            data = resp["data"]
            result["status"] = "completed"
            result["run_id"] = data.get("run_id", "")
            result["routing_accuracy"] = data.get("aggregate_metrics", {}).get("routing_correctness", 0)
            print(f"    SUCCESS in {result['duration_s']}s")
        else:
            result["status"] = "error"
            result["error"] = resp.get("error", resp.get("body", "unknown"))[:500]
            print(f"    ERROR: {result['error'][:200]}")

        orch_results.append(result)
        time.sleep(1)

    return orch_results


# ============================================================
# PHASE 5: Update dataset-results/ files
# ============================================================
def update_result_files(ingestion_results, test_results):
    """Update per-dataset result files with ingestion and test status."""
    print("\n" + "=" * 70)
    print("PHASE 5: UPDATING DATASET RESULT FILES")
    print("=" * 70)

    # Build lookup from results
    ingest_lookup = {r["name"]: r for r in ingestion_results}
    test_lookup = {r["name"]: r for r in (test_results or [])}

    updated_count = 0

    # Map dataset names to their result files
    result_files = {}
    for f in os.listdir(RESULTS_DIR):
        if f.startswith("results-") and f.endswith(".json"):
            result_files[f] = os.path.join(RESULTS_DIR, f)

    for filename, filepath in result_files.items():
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except Exception:
            continue

        ds_name = data.get("dataset_name", "")
        if not ds_name:
            continue

        ingest_info = ingest_lookup.get(ds_name)
        test_info = test_lookup.get(ds_name)

        if ingest_info:
            data["data_verification"] = data.get("data_verification", {})
            if ingest_info.get("status") == "completed":
                data["data_verification"]["ingestion_status"] = "completed"
                data["data_verification"]["ingestion_run_id"] = ingest_info.get("run_id", "")
                data["data_verification"]["items_ingested"] = ingest_info.get("total_items", 0)
                data["data_verification"]["ingested_at"] = ingest_info.get("timestamp", "")
                data["data_verification"]["supabase_ready"] = True
                data["data_verification"]["pinecone_ready"] = True
                if ingest_info.get("rag_target") == "graph":
                    data["data_verification"]["neo4j_ready"] = True
            else:
                data["data_verification"]["ingestion_status"] = "error"
                data["data_verification"]["ingestion_error"] = ingest_info.get("error", "")

        if test_info and test_info.get("status") == "completed":
            data["data_verification"]["test_run_id"] = test_info.get("run_id", "")
            data["data_verification"]["test_metrics"] = test_info.get("metrics", {})

        data["last_updated"] = datetime.now().isoformat()

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        updated_count += 1
        print(f"  Updated: {filename}")

    print(f"\n  Total files updated: {updated_count}")
    return updated_count


# ============================================================
# PHASE 6: Regenerate Master Dashboard
# ============================================================
def regenerate_dashboard():
    """Regenerate master-dashboard.json from updated result files."""
    print("\n" + "=" * 70)
    print("PHASE 6: REGENERATING MASTER DASHBOARD")
    print("=" * 70)

    dashboard_script = os.path.join(RESULTS_DIR, "generate-dashboard.py")
    if os.path.exists(dashboard_script):
        import subprocess
        result = subprocess.run(
            [sys.executable, dashboard_script],
            capture_output=True, text=True, timeout=30,
            cwd=RESULTS_DIR
        )
        if result.returncode == 0:
            print("  Dashboard regenerated successfully")
        else:
            print(f"  Dashboard generation output: {result.stdout[:300]}")
            if result.stderr:
                print(f"  Errors: {result.stderr[:300]}")
    else:
        print(f"  Dashboard script not found at {dashboard_script}")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    start_total = time.time()

    print("=" * 70)
    print("RAG BENCHMARK — PUSH ALL DATASETS VIA BENCHMARK WORKFLOWS")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"n8n Host: {N8N_HOST}")
    print(f"Datasets: {len(ALL_DATASETS)}")
    print(f"Total Q&A target: {sum(d['sample_size'] for d in ALL_DATASETS)}")
    print("=" * 70)

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "n8n_host": N8N_HOST,
        "phases": {}
    }

    # PHASE 1: Deploy workflows
    deploy_results = deploy_workflows()
    all_results["phases"]["deploy"] = deploy_results

    deployed_ok = sum(1 for r in deploy_results.values() if r.get("status") == "deployed")
    if deployed_ok == 0:
        print("\nWARNING: No workflows deployed successfully. Attempting ingestion anyway (workflows may already be active).")

    # PHASE 2: Ingest all datasets
    ingestion_results = ingest_all_datasets()
    all_results["phases"]["ingestion"] = ingestion_results

    # PHASE 3: Test RAG on ingested datasets
    test_results = test_rag_datasets(ingestion_results)
    all_results["phases"]["rag_tests"] = test_results

    # PHASE 4: Test orchestrator routing
    orch_results = test_orchestrator(ingestion_results)
    all_results["phases"]["orchestrator_tests"] = orch_results

    # PHASE 5: Update result files
    update_result_files(ingestion_results, test_results)

    # PHASE 6: Regenerate dashboard
    regenerate_dashboard()

    # Final summary
    total_elapsed = time.time() - start_total
    ingested_ok = [r for r in ingestion_results if r.get("status") == "completed"]
    ingested_fail = [r for r in ingestion_results if r.get("status") != "completed"]
    tested_ok = [r for r in test_results if r.get("status") == "completed"]

    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"  Workflows deployed: {deployed_ok}/{len(WORKFLOW_FILES)}")
    print(f"  Datasets ingested:  {len(ingested_ok)}/{len(ALL_DATASETS)}")
    print(f"  RAG tests passed:   {len(tested_ok)}/{len(test_results)}")
    print(f"  Orchestrator tests: {len([r for r in orch_results if r.get('status') == 'completed'])}/{len(orch_results)}")
    print(f"  Total duration:     {round(total_elapsed, 1)}s")

    if ingested_ok:
        total_items = sum(r.get("total_items", 0) for r in ingested_ok)
        print(f"\n  Total items ingested: {total_items}")
        print(f"  Datasets ingested successfully:")
        for r in ingested_ok:
            print(f"    - {r['name']}: {r.get('total_items', '?')} items ({r['duration_s']}s)")

    if ingested_fail:
        print(f"\n  Datasets that FAILED ingestion:")
        for r in ingested_fail:
            print(f"    - {r['name']}: {r.get('error', 'unknown')[:100]}")

    print("=" * 70)

    # Save comprehensive results
    all_results["summary"] = {
        "workflows_deployed": deployed_ok,
        "datasets_ingested": len(ingested_ok),
        "datasets_failed": len(ingested_fail),
        "rag_tests_passed": len(tested_ok),
        "total_items_ingested": sum(r.get("total_items", 0) for r in ingested_ok),
        "total_duration_s": round(total_elapsed, 1)
    }

    output_file = os.path.join(REPO_ROOT, "push-all-results.json")
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull results saved: {output_file}")
