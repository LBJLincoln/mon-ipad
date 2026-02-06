#!/usr/bin/env python3
"""
Extract all benchmark Q&A results from Supabase and save to JSON files.
Fetches questions, expected answers, actual answers, metrics per run.
"""

import json
import os
import time
from datetime import datetime
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
OUTPUT_FILE = os.path.join(BASE_DIR, "benchmark-qa-results-full.json")
BATCH_SIZE = 500

def exec_sql(sql, timeout=120):
    url = f"{N8N_HOST}/webhook/benchmark-sql-exec"
    for attempt in range(5):
        body = json.dumps({"sql": sql}).encode()
        req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                return json.loads(raw)
        except error.HTTPError as e:
            if (e.code == 403 or e.code >= 500) and attempt < 4:
                wait = min(2 ** (attempt + 1), 30)
                print(f"    [RETRY] HTTP {e.code}, wait {wait}s (attempt {attempt+1}/5)...")
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            if attempt < 4:
                time.sleep(2 ** (attempt + 1))
                continue
            raise


def fetch_batch(offset, limit):
    """Fetch a batch of results using json_agg."""
    sql = f"""SELECT json_agg(row_to_json(t))::text as data FROM (
        SELECT
            run_id,
            dataset_name,
            item_index,
            question,
            expected_answer,
            actual_answer,
            metrics,
            latency_ms,
            tokens_used,
            error
        FROM benchmark_results
        WHERE tenant_id = 'benchmark'
        ORDER BY id
        LIMIT {limit} OFFSET {offset}
    ) t"""

    resp = exec_sql(sql, timeout=120)

    if isinstance(resp, dict) and "data" in resp:
        data_str = resp["data"]
        if data_str and data_str != "null":
            return json.loads(data_str)
    return []


def fetch_run_configs_by_batch():
    """Fetch run configs in small batches to avoid 500 errors."""
    configs = {}
    offset = 0
    batch = 50

    while True:
        sql = f"""SELECT json_agg(row_to_json(t))::text as data FROM (
            SELECT run_id, config::text as config_text
            FROM benchmark_runs
            WHERE tenant_id = 'benchmark'
            ORDER BY run_id
            LIMIT {batch} OFFSET {offset}
        ) t"""

        try:
            resp = exec_sql(sql, timeout=30)
            if isinstance(resp, dict) and "data" in resp:
                data_str = resp["data"]
                if data_str and data_str != "null":
                    rows = json.loads(data_str)
                    for r in rows:
                        config_text = r.get("config_text", "{}")
                        try:
                            config = json.loads(config_text) if isinstance(config_text, str) else config_text
                        except:
                            config = {}
                        configs[r["run_id"]] = config.get("rag_target", "unknown")

                    if len(rows) < batch:
                        break
                    offset += len(rows)
                    time.sleep(2)
                    continue
            break
        except Exception as e:
            print(f"    [WARN] Could not fetch run configs at offset {offset}: {e}")
            break

    return configs


if __name__ == "__main__":
    print("=" * 60)
    print("  BENCHMARK Q&A RESULTS EXTRACTOR")
    print("=" * 60)

    # Get total count
    count_resp = exec_sql(
        "SELECT COUNT(*) as total FROM benchmark_results WHERE tenant_id = 'benchmark'"
    )
    total = int(count_resp.get("total", 0))
    print(f"  Total results in Supabase: {total}")

    time.sleep(3)

    # Try to get run configs for rag_type mapping
    print("  Fetching run configurations (rag_type mapping)...")
    run_rag_map = fetch_run_configs_by_batch()
    print(f"  Mapped {len(run_rag_map)} run_ids to rag_types")

    time.sleep(3)

    # Fetch all results in batches
    all_results = []
    offset = 0

    print(f"\n  Extracting {total} results in batches of {BATCH_SIZE}...")

    while offset < total:
        try:
            batch = fetch_batch(offset, BATCH_SIZE)
        except Exception as e:
            print(f"    [ERROR] Batch at offset {offset}: {e}")
            time.sleep(10)
            # Try smaller batch
            try:
                batch = fetch_batch(offset, 100)
            except Exception as e2:
                print(f"    [FATAL] Smaller batch also failed: {e2}. Stopping.")
                break

        if not batch:
            break

        # Enrich with RAG type
        for row in batch:
            run_id = row.get("run_id", "")
            row["rag_type"] = run_rag_map.get(run_id, "unknown")

        all_results.extend(batch)
        offset += len(batch)

        pct = (offset / total) * 100
        print(f"    Fetched {offset}/{total} ({pct:.0f}%)")

        time.sleep(3)

    print(f"\n  Total extracted: {len(all_results)}")

    # Compute stats
    by_dataset = {}
    by_rag = {}
    by_dataset_rag = {}
    has_answer = 0
    has_error = 0

    for r in all_results:
        ds = r.get("dataset_name", "?")
        rag = r.get("rag_type", "?")
        key = f"{ds}/{rag}"

        by_dataset[ds] = by_dataset.get(ds, 0) + 1
        by_rag[rag] = by_rag.get(rag, 0) + 1
        by_dataset_rag[key] = by_dataset_rag.get(key, 0) + 1

        if r.get("actual_answer"):
            has_answer += 1
        if r.get("error"):
            has_error += 1

    # Build output
    output = {
        "suite": "Multi-RAG Benchmark - Full Q&A Results",
        "extracted_at": datetime.now().isoformat(),
        "total_results": len(all_results),
        "with_actual_answer": has_answer,
        "with_error": has_error,
        "stats": {
            "by_dataset": dict(sorted(by_dataset.items())),
            "by_rag_type": dict(sorted(by_rag.items())),
            "by_dataset_and_rag": dict(sorted(by_dataset_rag.items())),
        },
        "results": all_results,
    }

    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)

    file_size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)

    print(f"\n  Saved to: {OUTPUT_FILE}")
    print(f"  File size: {file_size_mb:.1f} MB")
    print(f"  With actual answers: {has_answer}/{len(all_results)}")
    print(f"  With errors: {has_error}/{len(all_results)}")
    print(f"\n  By dataset:")
    for ds, cnt in sorted(by_dataset.items()):
        print(f"    {ds}: {cnt}")
    print(f"\n  By RAG type:")
    for rag, cnt in sorted(by_rag.items()):
        print(f"    {rag}: {cnt}")

    print("\n  Done!")
