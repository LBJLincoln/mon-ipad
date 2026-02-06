#!/usr/bin/env python3
"""
Run paginated dataset ingestion via BENCHMARK - Dataset Ingestion Pipeline.
Sends pages of 100 items each via webhook, with n8n execution verification.
"""
import json
import os
import time
import sys
from datetime import datetime
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
INGESTION_WF_ID = "L8irkzSrfLlgt2Bt"
PAGE_SIZE = 100

# Datasets accessible without auth, with correct paths
ACCESSIBLE_DATASETS = [
    {"name": "hotpotqa", "total": 1000, "rag_target": "standard"},
    {"name": "popqa", "total": 1000, "rag_target": "standard"},
    {"name": "squad_v2", "total": 1000, "rag_target": "standard"},
    {"name": "frames", "total": 824, "rag_target": "standard"},
    {"name": "pubmedqa", "total": 500, "rag_target": "standard"},
    {"name": "narrativeqa", "total": 1000, "rag_target": "standard"},
    {"name": "asqa", "total": 1000, "rag_target": "standard"},
    {"name": "msmarco", "total": 1000, "rag_target": "standard"},
    {"name": "finqa", "total": 500, "rag_target": "quantitative"},
    {"name": "triviaqa", "total": 1000, "rag_target": "standard"},
    {"name": "natural_questions", "total": 1000, "rag_target": "standard"},
]

# Datasets requiring HuggingFace auth (noted for reference)
AUTH_REQUIRED = [
    {"name": "musique", "total": 200, "rag_target": "graph", "note": "StonyBrookNLP/musique - gated"},
    {"name": "2wikimultihopqa", "total": 300, "rag_target": "graph", "note": "scholarly-shadows-syndicate - gated"},
    {"name": "tatqa", "total": 150, "rag_target": "quantitative", "note": "next-tat/TAT-QA - gated"},
    {"name": "convfinqa", "total": 100, "rag_target": "quantitative", "note": "TheFinAI/ConvFinQA - gated"},
    {"name": "wikitablequestions", "total": 50, "rag_target": "quantitative", "note": "Stanford - not found publicly"},
]


def api_get(endpoint, timeout=30):
    url = f"{N8N_HOST}/api/v1{endpoint}"
    req = request.Request(url, headers={"X-N8N-API-KEY": N8N_API_KEY, "Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def trigger_webhook(data, timeout=120):
    url = f"{N8N_HOST}/webhook/benchmark-ingest"
    body = json.dumps(data).encode()
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {"ok": True}
    except Exception as e:
        return {"ok": True}  # Workflow runs regardless of response


def get_latest_exec_id():
    data = api_get(f"/executions?limit=1&workflowId={INGESTION_WF_ID}")
    if data and data.get("data"):
        return data["data"][0].get("id")
    return None


def wait_for_execution(prev_id, timeout=120):
    """Wait for a new execution to complete."""
    start = time.time()
    while time.time() - start < timeout:
        data = api_get(f"/executions?limit=1&workflowId={INGESTION_WF_ID}")
        if data and data.get("data"):
            ex = data["data"][0]
            if ex.get("id") != prev_id and ex.get("finished"):
                return ex
        time.sleep(2)
    return None


def check_execution_result(exec_id):
    """Analyze execution results."""
    detail = api_get(f"/executions/{exec_id}?includeData=true", timeout=60)
    if not detail:
        return {"status": "unknown"}

    run_data = detail.get("data", {}).get("resultData", {}).get("runData", {})
    result = {
        "exec_id": exec_id,
        "status": detail.get("status"),
        "supabase_ok": False,
        "items_parsed": 0,
        "nodes": list(run_data.keys()),
    }

    for name, runs in run_data.items():
        for r in runs:
            main_data = r.get("data", {}).get("main", [])
            if name == "Parse & Normalize Dataset":
                if main_data and main_data[0]:
                    j = main_data[0][0].get("json", {})
                    result["items_parsed"] = j.get("total_items", 0)
            elif name == "Supabase: Store Q&A":
                if main_data and main_data[0]:
                    result["supabase_ok"] = True
            elif name == "Final Summary":
                if main_data and main_data[0]:
                    j = main_data[0][0].get("json", {})
                    result["run_id"] = j.get("run_id", "")
            elif name == "Fetch HuggingFace Dataset":
                # Check for error
                if main_data and len(main_data) > 1 and main_data[1]:
                    j = main_data[1][0].get("json", {})
                    err = j.get("error", {})
                    if isinstance(err, dict):
                        result["hf_error"] = err.get("message", "")[:200]
                    else:
                        result["hf_error"] = str(err)[:200]

    return result


def update_result_files(ds_name, total_ingested, exec_results):
    """Update dataset-results files."""
    results_dir = "/home/user/mon-ipad/dataset-results"
    files = [f"results-{ds_name}.json"]
    if ds_name == "finqa":
        files.append("results-finqa-quantitative.json")

    for fname in files:
        fpath = os.path.join(results_dir, fname)
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath) as f:
                data = json.load(f)
            dv = data.get("data_verification", {})
            dv["ingestion_status"] = "completed" if total_ingested > 0 else "failed"
            dv["items_ingested"] = total_ingested
            dv["supabase_ready"] = total_ingested > 0
            dv["pinecone_ready"] = False  # Embeddings disabled
            dv["ingested_at"] = datetime.now().isoformat()
            dv["ingestion_method"] = "BENCHMARK - Dataset Ingestion Pipeline"
            dv["pages_ingested"] = len(exec_results)
            data["data_verification"] = dv
            data["last_updated"] = datetime.now().isoformat()
            with open(fpath, "w") as f:
                json.dump(data, f, indent=2)
            print(f"      Updated: {fname}")
        except Exception as e:
            print(f"      Error updating {fname}: {e}")


if __name__ == "__main__":
    print("=" * 70)
    print("BENCHMARK DATASET INGESTION — PAGINATED")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Accessible datasets: {len(ACCESSIBLE_DATASETS)}")
    print(f"Auth-required (skipped): {len(AUTH_REQUIRED)}")
    total_target = sum(d["total"] for d in ACCESSIBLE_DATASETS)
    print(f"Target Q&A: {total_target}")
    print("=" * 70)

    grand_total = 0
    all_results = []

    for ds_idx, ds in enumerate(ACCESSIBLE_DATASETS):
        name = ds["name"]
        total_size = ds["total"]
        pages = (total_size + PAGE_SIZE - 1) // PAGE_SIZE

        print(f"\n  [{ds_idx+1}/{len(ACCESSIBLE_DATASETS)}] {name} ({total_size} items, {pages} pages)")

        ds_items = 0
        ds_execs = []

        for page in range(pages):
            offset = page * PAGE_SIZE
            page_size = min(PAGE_SIZE, total_size - offset)

            sys.stdout.write(f"    Page {page+1}/{pages} (offset={offset}, size={page_size})... ")
            sys.stdout.flush()

            prev_id = get_latest_exec_id()

            payload = {
                "dataset_name": name,
                "sample_size": page_size,
                "hf_offset": offset,
                "batch_size": min(50, page_size),
                "generate_embeddings": False,
                "include_neo4j": False,
                "tenant_id": "benchmark"
            }

            start = time.time()
            trigger_webhook(payload, timeout=180)

            # Wait for execution to complete
            exec_info = wait_for_execution(prev_id, timeout=120)
            elapsed = time.time() - start

            if exec_info:
                result = check_execution_result(exec_info["id"])
                items = result.get("items_parsed", 0)
                ds_items += items
                sb = "OK" if result.get("supabase_ok") else "FAIL"
                hf_err = result.get("hf_error", "")

                if hf_err:
                    print(f"HF Error: {hf_err[:80]}")
                    if "does not exist" in hf_err or "401" in hf_err:
                        print(f"    Skipping remaining pages for {name}")
                        break
                else:
                    print(f"{items} items, SB:{sb} ({elapsed:.1f}s)")

                ds_execs.append(result)
            else:
                print(f"timeout ({elapsed:.1f}s)")
                ds_execs.append({"status": "timeout"})

            # Brief pause between pages
            time.sleep(1)

        grand_total += ds_items
        print(f"    TOTAL for {name}: {ds_items} items ingested")

        # Update result files
        update_result_files(name, ds_items, ds_execs)

        all_results.append({
            "name": name,
            "rag_target": ds["rag_target"],
            "target_items": total_size,
            "items_ingested": ds_items,
            "pages_completed": len(ds_execs),
            "supabase_ok": any(r.get("supabase_ok") for r in ds_execs)
        })

    # Also note auth-required datasets in results
    for ds in AUTH_REQUIRED:
        update_result_files(ds["name"], 0, [])
        all_results.append({
            "name": ds["name"],
            "rag_target": ds["rag_target"],
            "target_items": ds["total"],
            "items_ingested": 0,
            "status": "auth_required",
            "note": ds["note"]
        })

    # Summary
    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    ok_count = sum(1 for r in all_results if r.get("items_ingested", 0) > 0)
    print(f"  Datasets with data: {ok_count}/{len(all_results)}")
    print(f"  Total items:        {grand_total}")
    print()

    for r in all_results:
        items = r.get("items_ingested", 0)
        target = r.get("target_items", 0)
        st = "OK" if items > 0 else ("AUTH" if r.get("status") == "auth_required" else "FAIL")
        print(f"  [{st:4s}] {r['name']:25s} {items:5d}/{target:5d} items | {r['rag_target']}")

    print("=" * 70)

    # Save comprehensive results
    output = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "accessible_datasets": len(ACCESSIBLE_DATASETS),
            "auth_required_datasets": len(AUTH_REQUIRED),
            "datasets_with_data": ok_count,
            "total_items_ingested": grand_total,
        },
        "results": all_results,
        "auth_required_note": "These datasets require HuggingFace authentication. Set HF_TOKEN in n8n variables to ingest them."
    }
    with open("/home/user/mon-ipad/benchmark-workflows/ingestion-run-results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved: benchmark-workflows/ingestion-run-results.json")
