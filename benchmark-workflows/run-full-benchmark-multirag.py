#!/usr/bin/env python3
"""
MULTI-RAG FULL BENCHMARK RUNNER (Graph + Quantitative)
=======================================================
Sends ALL questions from the 10 datasets through Graph RAG and Quantitative RAG.
Standard RAG already tested in previous session (7824 questions).

Sequential execution with delays to avoid n8n rate limiting.
Auto-pushes git every 1000 completed questions.

Usage:
  python3 run-full-benchmark-multirag.py [--workers 2] [--batch-size 100] [--test-type e2e]
"""

import json
import os
import sys
import time
import subprocess
import threading
import traceback
from datetime import datetime
from urllib import request, error
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Configuration ───────────────────────────────────────────────
N8N_HOST = "https://amoret.app.n8n.cloud"
WEBHOOK_PATH = "benchmark-test-rag"
BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
REPO_DIR = "/home/user/mon-ipad"
RESULTS_FILE = os.path.join(BASE_DIR, "full-benchmark-multirag-results.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "full-benchmark-multirag-progress.json")
GIT_BRANCH = "claude/debug-benchmark-errors-Eptwq"

# Parse CLI args
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--workers", type=int, default=2, help="Parallel webhook workers (2=graph+quant)")
parser.add_argument("--batch-size", type=int, default=100, help="Batch size per webhook call")
parser.add_argument("--test-type", default="e2e", help="Test type: retrieval, generation, e2e, domain, robustness")
parser.add_argument("--timeout", type=int, default=600, help="Webhook timeout in seconds")
parser.add_argument("--push-every", type=int, default=1000, help="Git push every N questions")
parser.add_argument("--delay", type=int, default=5, help="Delay (seconds) between webhook calls per worker")
args = parser.parse_args()

MAX_WORKERS = args.workers
BATCH_SIZE = args.batch_size
TEST_TYPE = args.test_type
WEBHOOK_TIMEOUT = args.timeout
PUSH_EVERY = args.push_every
CALL_DELAY = args.delay

# The 10 datasets (7,824 Q&A pairs)
DATASETS = [
    {"name": "hotpotqa",    "category": "multi_hop_qa",   "items": 1000},
    {"name": "frames",      "category": "rag_benchmark",  "items": 824},
    {"name": "squad_v2",    "category": "single_hop_qa",  "items": 1000},
    {"name": "popqa",       "category": "single_hop_qa",  "items": 1000},
    {"name": "pubmedqa",    "category": "domain_medical",  "items": 500},
    {"name": "triviaqa",    "category": "single_hop_qa",  "items": 1000},
    {"name": "finqa",       "category": "domain_finance",  "items": 500},
    {"name": "msmarco",     "category": "retrieval",       "items": 1000},
    {"name": "narrativeqa", "category": "long_form_qa",    "items": 500},
    {"name": "asqa",        "category": "long_form_qa",    "items": 500},
]

# Only Graph and Quantitative (Standard already done)
RAG_TYPES = ["graph", "quantitative"]

# Already completed from previous run (hotpotqa succeeded for all 3)
ALREADY_DONE = {
    ("hotpotqa", "graph"),
    ("hotpotqa", "quantitative"),
    ("hotpotqa", "standard"),
}

# ─── State ───────────────────────────────────────────────────────
lock = threading.Lock()
total_completed = 0
total_errors = 0
total_successes = 0
last_push_at = 0
results = []
start_time = datetime.now()


def webhook_call(payload, timeout=600):
    """Call n8n benchmark-test-rag webhook with retry on 403/5xx."""
    url = f"{N8N_HOST}/webhook/{WEBHOOK_PATH}"
    headers = {"Content-Type": "application/json"}

    for attempt in range(5):  # More retries, with backoff for 403
        body = json.dumps(payload).encode()
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                if not raw or raw.strip() == "":
                    return {"status": resp.status, "data": None,
                            "error": f"Empty response (HTTP {resp.status})"}
                try:
                    return {"status": resp.status, "data": json.loads(raw), "error": None}
                except json.JSONDecodeError:
                    return {"status": resp.status, "data": raw, "error": None}
        except error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()
            except:
                pass

            # Retry on 403 (rate limit) and 5xx
            if (e.code == 403 or e.code >= 500) and attempt < 4:
                wait = min(2 ** (attempt + 1), 30)  # 2, 4, 8, 16, 30s
                print(f"    [RETRY] HTTP {e.code}, waiting {wait}s (attempt {attempt+1}/5)...")
                time.sleep(wait)
                continue
            return {"status": e.code, "data": None, "error": f"HTTP {e.code}: {err_body[:500]}"}
        except Exception as e:
            if attempt < 4:
                wait = min(2 ** (attempt + 1), 30)
                print(f"    [RETRY] {e}, waiting {wait}s (attempt {attempt+1}/5)...")
                time.sleep(wait)
                continue
            return {"status": 0, "data": None, "error": str(e)}

    return {"status": 0, "data": None, "error": "Max retries exceeded"}


def git_push_results():
    """Commit and push current results to git."""
    try:
        save_progress()
        save_results()

        subprocess.run(
            ["git", "add",
             "benchmark-workflows/full-benchmark-multirag-results.json",
             "benchmark-workflows/full-benchmark-multirag-progress.json"],
            cwd=REPO_DIR, capture_output=True, timeout=30
        )
        msg = (f"benchmark: {total_completed} questions tested "
               f"({total_successes} ok, {total_errors} err) - "
               f"graph+quantitative RAG {TEST_TYPE}")
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=REPO_DIR, capture_output=True, timeout=30
        )

        for retry in range(4):
            result = subprocess.run(
                ["git", "push", "-u", "origin", GIT_BRANCH],
                cwd=REPO_DIR, capture_output=True, timeout=60
            )
            if result.returncode == 0:
                print(f"  [GIT] Pushed at {total_completed} questions completed")
                return True
            wait = 2 ** (retry + 1)
            print(f"  [GIT] Push failed (attempt {retry+1}), retrying in {wait}s...")
            time.sleep(wait)

        print(f"  [GIT] Push failed after 4 retries")
        return False
    except Exception as e:
        print(f"  [GIT] Error: {e}")
        return False


def save_progress():
    """Save progress file."""
    elapsed = (datetime.now() - start_time).total_seconds()
    rate = total_completed / max(elapsed, 1) * 3600
    total_expected = sum(d["items"] for d in DATASETS) * len(RAG_TYPES)

    progress = {
        "status": "running",
        "started_at": start_time.isoformat(),
        "updated_at": datetime.now().isoformat(),
        "elapsed_seconds": int(elapsed),
        "total_completed": total_completed,
        "total_successes": total_successes,
        "total_errors": total_errors,
        "total_expected": total_expected,
        "progress_pct": f"{(total_completed / max(total_expected, 1)) * 100:.1f}%",
        "rate_per_hour": int(rate),
        "rag_types": RAG_TYPES,
        "test_type": TEST_TYPE,
        "batch_size": BATCH_SIZE,
        "workers": MAX_WORKERS,
        "note": "Graph + Quantitative only (Standard already done)",
    }

    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def save_results():
    """Save full results file."""
    elapsed = (datetime.now() - start_time).total_seconds()
    total_expected = sum(d["items"] for d in DATASETS) * len(RAG_TYPES)

    report = {
        "suite": "MULTI-RAG FULL BENCHMARK (Graph + Quantitative)",
        "started_at": start_time.isoformat(),
        "updated_at": datetime.now().isoformat(),
        "config": {
            "test_type": TEST_TYPE,
            "batch_size": BATCH_SIZE,
            "workers": MAX_WORKERS,
            "rag_types": RAG_TYPES,
            "datasets": [d["name"] for d in DATASETS],
            "total_qa_pairs": sum(d["items"] for d in DATASETS),
            "note": "Standard RAG already tested (7824 questions in previous session)",
        },
        "summary": {
            "total_completed": total_completed,
            "total_successes": total_successes,
            "total_errors": total_errors,
            "total_expected": total_expected,
            "progress_pct": f"{(total_completed / max(total_expected, 1)) * 100:.1f}%",
            "elapsed_seconds": int(elapsed),
            "error_rate": f"{(total_errors / max(total_completed, 1)) * 100:.2f}%",
        },
        "results": results,
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump(report, f, indent=2)


def run_rag_pipeline(rag_type, dataset_queue):
    """
    Agent worker: processes a queue of datasets for a single RAG type.
    Sequential within each worker to avoid rate limiting.
    """
    global total_completed, total_errors, total_successes, last_push_at

    for dataset in dataset_queue:
        ds_name = dataset["name"]
        ds_items = dataset["items"]
        task_id = f"{ds_name}/{rag_type}"

        # Skip already completed
        if (ds_name, rag_type) in ALREADY_DONE:
            print(f"  [{task_id}] SKIP (already done)")
            continue

        print(f"  [{task_id}] Starting: {ds_items} items, batch_size={BATCH_SIZE}")

        t0 = time.time()
        payload = {
            "dataset_name": ds_name,
            "test_type": TEST_TYPE,
            "rag_target": rag_type,
            "sample_size": ds_items,
            "batch_size": BATCH_SIZE,
            "tenant_id": "benchmark",
        }

        resp = webhook_call(payload, timeout=WEBHOOK_TIMEOUT)
        elapsed_s = time.time() - t0

        result_entry = {
            "dataset": ds_name,
            "rag_type": rag_type,
            "items": ds_items,
            "test_type": TEST_TYPE,
            "status": "success" if not resp["error"] else "error",
            "error": resp["error"],
            "response_data": None,
            "latency_s": round(elapsed_s, 1),
            "timestamp": datetime.now().isoformat(),
        }

        data = resp.get("data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                pass
        if isinstance(data, dict):
            result_entry["response_data"] = {
                k: v for k, v in data.items()
                if k in ("run_id", "status", "total_items", "duration_human",
                         "duration_ms", "rag_target", "test_type", "dataset_name")
            }

        with lock:
            results.append(result_entry)
            if resp["error"]:
                total_errors += ds_items
                print(f"  [{task_id}] ERROR ({elapsed_s:.0f}s): {resp['error'][:150]}")
            else:
                total_successes += ds_items
                print(f"  [{task_id}] OK ({elapsed_s:.0f}s): {ds_items} items via {rag_type} RAG")

            total_completed += ds_items

            # Check if we should push
            push_threshold = (total_completed // PUSH_EVERY) * PUSH_EVERY
            if push_threshold > last_push_at and total_completed >= PUSH_EVERY:
                last_push_at = push_threshold
                print(f"\n  === MILESTONE: {total_completed} questions — pushing ===\n")
                git_push_results()

            # Save progress
            save_progress()
            save_results()

        # Delay between calls to avoid n8n rate limiting
        print(f"  [{rag_type}] Waiting {CALL_DELAY}s before next call...")
        time.sleep(CALL_DELAY)


# ─── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Calculate actual work (excluding already done)
    actual_tasks = [(ds, rag) for ds in DATASETS for rag in RAG_TYPES
                    if (ds["name"], rag) not in ALREADY_DONE]
    total_expected = sum(ds["items"] for ds, rag in actual_tasks)

    print("=" * 70)
    print("  MULTI-RAG BENCHMARK: Graph + Quantitative")
    print("=" * 70)
    print(f"  Time:       {start_time.isoformat()}")
    print(f"  Datasets:   {len(DATASETS)} ({sum(d['items'] for d in DATASETS)} Q&A pairs)")
    print(f"  RAG Types:  {', '.join(RAG_TYPES)} (Standard already done)")
    print(f"  Tasks:      {len(actual_tasks)} (skipping {len(ALREADY_DONE)} already done)")
    print(f"  Questions:  {total_expected}")
    print(f"  Test Type:  {TEST_TYPE}")
    print(f"  Batch Size: {BATCH_SIZE}")
    print(f"  Workers:    {MAX_WORKERS} (1 per RAG type)")
    print(f"  Delay:      {CALL_DELAY}s between calls")
    print(f"  Push Every: {PUSH_EVERY} questions")
    print(f"  Timeout:    {WEBHOOK_TIMEOUT}s per call")
    print("=" * 70)

    save_progress()

    # 2 agents: one for graph, one for quantitative
    # Each agent processes all 10 datasets sequentially
    print(f"\n  Launching 2 agents (graph + quantitative)...\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for rag_type in RAG_TYPES:
            future = executor.submit(run_rag_pipeline, rag_type, DATASETS)
            futures[future] = rag_type

        for future in as_completed(futures):
            rag_type = futures[future]
            try:
                future.result()
                print(f"\n  [AGENT {rag_type}] Completed all datasets")
            except Exception as e:
                print(f"\n  [AGENT {rag_type}] FAILED: {e}")
                traceback.print_exc()

    # Final save and push
    save_progress()
    save_results()

    print("\n" + "=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)
    print(f"  Total Completed: {total_completed}/{total_expected}")
    print(f"  Successes:       {total_successes}")
    print(f"  Errors:          {total_errors}")
    if total_completed > 0:
        print(f"  Error Rate:      {(total_errors / total_completed) * 100:.2f}%")
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"  Duration:        {elapsed:.0f}s ({elapsed/60:.1f}min)")
    if elapsed > 0:
        print(f"  Rate:            {total_completed / elapsed * 3600:.0f} questions/h")
    print("=" * 70)

    print("\n  Final git push...")
    git_push_results()

    print(f"\n  Results: {RESULTS_FILE}")
    print(f"  Progress: {PROGRESS_FILE}")
    print("  Done!")
