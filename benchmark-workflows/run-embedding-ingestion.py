#!/usr/bin/env python3
"""
Re-run ingestion with embeddings enabled to populate Pinecone.
Uses the same BENCHMARK - Dataset Ingestion Pipeline with generate_embeddings=True.
Also attempts Neo4j for graph datasets with include_neo4j=True.
"""
import json
import time
import sys
from datetime import datetime
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
INGESTION_WF_ID = "L8irkzSrfLlgt2Bt"
PAGE_SIZE = 50  # Smaller pages for embedding API calls

# All accessible datasets
DATASETS = [
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


def api_get(endpoint, timeout=30):
    url = f"{N8N_HOST}/api/v1{endpoint}"
    req = request.Request(url, headers={"X-N8N-API-KEY": N8N_API_KEY, "Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except:
        return None


def trigger_webhook(data, timeout=300):
    url = f"{N8N_HOST}/webhook/benchmark-ingest"
    body = json.dumps(data).encode()
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {"ok": True}
    except:
        return {"ok": True}


def get_latest_exec_id():
    data = api_get(f"/executions?limit=1&workflowId={INGESTION_WF_ID}")
    if data and data.get("data"):
        return data["data"][0].get("id")
    return None


def wait_and_check(prev_id, timeout=180):
    """Wait for new execution to complete and return results."""
    start = time.time()
    while time.time() - start < timeout:
        data = api_get(f"/executions?limit=1&workflowId={INGESTION_WF_ID}")
        if data and data.get("data"):
            ex = data["data"][0]
            if ex.get("id") != prev_id and ex.get("finished"):
                eid = ex["id"]
                detail = api_get(f"/executions/{eid}?includeData=true", timeout=60)
                if not detail:
                    return {"exec_id": eid, "status": ex.get("status")}

                rd = detail.get("data", {}).get("resultData", {}).get("runData", {})
                result = {
                    "exec_id": eid,
                    "status": ex.get("status"),
                    "items_parsed": 0,
                    "embeddings_ok": False,
                    "pinecone_ok": False,
                    "pinecone_count": 0,
                    "neo4j_ok": False,
                    "supabase_ok": False,
                    "errors": []
                }

                for name, runs in rd.items():
                    for r in runs:
                        err = r.get("error")
                        md = r.get("data", {}).get("main", [])

                        if name == "Parse & Normalize Dataset":
                            if md and md[0]:
                                j = md[0][0].get("json", {})
                                result["items_parsed"] = j.get("total_items", 0)
                        elif name == "Generate Embeddings":
                            if md and md[0]:
                                j = md[0][0].get("json", {})
                                if "data" in j and isinstance(j["data"], list):
                                    result["embeddings_ok"] = True
                                    result["embedding_count"] = len(j["data"])
                            if err:
                                msg = err.get("message", str(err))[:200] if isinstance(err, dict) else str(err)[:200]
                                result["errors"].append(f"Embeddings: {msg}")
                        elif name == "Pinecone: Upsert Vectors":
                            if md and md[0]:
                                j = md[0][0].get("json", {})
                                uc = j.get("upsertedCount", 0)
                                if uc > 0:
                                    result["pinecone_ok"] = True
                                    result["pinecone_count"] = uc
                            if err:
                                msg = err.get("message", str(err))[:200] if isinstance(err, dict) else str(err)[:200]
                                result["errors"].append(f"Pinecone: {msg}")
                        elif name == "Supabase: Store Q&A":
                            if md and md[0] and not err:
                                result["supabase_ok"] = True
                        elif name == "Neo4j: Store Graph Nodes":
                            if md and md[0] and not err:
                                result["neo4j_ok"] = True
                            if err:
                                msg = err.get("message", str(err))[:200] if isinstance(err, dict) else str(err)[:200]
                                result["errors"].append(f"Neo4j: {msg}")

                return result
        time.sleep(3)
    return None


if __name__ == "__main__":
    print("=" * 70)
    print("BENCHMARK EMBEDDING INGESTION — PINECONE + NEO4J POPULATION")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Datasets: {len(DATASETS)}")
    total_target = sum(d["total"] for d in DATASETS)
    print(f"Target items: {total_target}")
    print(f"Page size: {PAGE_SIZE}")
    print("=" * 70)

    grand_total_vectors = 0
    all_results = []

    for ds_idx, ds in enumerate(DATASETS):
        name = ds["name"]
        total_size = ds["total"]
        rag = ds["rag_target"]
        pages = (total_size + PAGE_SIZE - 1) // PAGE_SIZE
        is_graph = rag == "graph"

        print(f"\n  [{ds_idx+1}/{len(DATASETS)}] {name} ({total_size} items, {pages} pages, {rag})")

        ds_vectors = 0
        ds_errors = []

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
                "batch_size": page_size,  # Single batch per page
                "generate_embeddings": True,
                "include_neo4j": is_graph,
                "tenant_id": "benchmark"
            }

            start = time.time()
            trigger_webhook(payload, timeout=300)
            time.sleep(2)

            result = wait_and_check(prev_id, timeout=180)
            elapsed = time.time() - start

            if result:
                vectors = result.get("pinecone_count", 0)
                ds_vectors += vectors
                emb = "OK" if result.get("embeddings_ok") else "FAIL"
                pc = f"{vectors}v" if result.get("pinecone_ok") else "FAIL"
                sb = "OK" if result.get("supabase_ok") else "FAIL"

                if result.get("errors"):
                    err_str = "; ".join(result["errors"][:2])
                    print(f"EMB:{emb} PC:{pc} SB:{sb} ({elapsed:.1f}s) ERR: {err_str[:80]}")
                    ds_errors.extend(result["errors"])
                    # If embedding auth fails, skip remaining pages
                    if any("401" in e for e in result["errors"]):
                        print(f"    AUTH ERROR - stopping {name}")
                        break
                else:
                    print(f"EMB:{emb} PC:{pc} SB:{sb} ({elapsed:.1f}s)")
            else:
                print(f"timeout ({elapsed:.1f}s)")

            # Brief pause between pages
            time.sleep(2)

        grand_total_vectors += ds_vectors
        print(f"    TOTAL for {name}: {ds_vectors} vectors in Pinecone")

        all_results.append({
            "name": name,
            "rag_target": rag,
            "target_items": total_size,
            "pinecone_vectors": ds_vectors,
            "errors": ds_errors[:5]
        })

    # Summary
    print("\n" + "=" * 70)
    print("EMBEDDING INGESTION SUMMARY")
    print("=" * 70)
    ok_count = sum(1 for r in all_results if r.get("pinecone_vectors", 0) > 0)
    print(f"  Datasets with vectors: {ok_count}/{len(all_results)}")
    print(f"  Total Pinecone vectors: {grand_total_vectors}")
    print()

    for r in all_results:
        vecs = r.get("pinecone_vectors", 0)
        target = r.get("target_items", 0)
        st = "OK" if vecs > 0 else "FAIL"
        errs = f" | ERR: {r['errors'][0][:50]}" if r.get("errors") else ""
        print(f"  [{st:4s}] {r['name']:25s} {vecs:5d}/{target:5d} vectors | {r['rag_target']}{errs}")

    print("=" * 70)

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_vectors": grand_total_vectors,
        "datasets_ok": ok_count,
        "results": all_results
    }
    with open("/home/user/mon-ipad/benchmark-workflows/embedding-ingestion-results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved: benchmark-workflows/embedding-ingestion-results.json")
