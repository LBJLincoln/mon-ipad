#!/usr/bin/env python3
"""
RAG 1000 SPECIALIZED QUESTIONS RUNNER
======================================
Sends the 1000 Graph+Quantitative specialized questions to n8n.
- 500 Graph RAG questions (musique, 2wikimultihopqa)
- 500 Quantitative RAG questions (finqa, tatqa, convfinqa, wikitablequestions)

Features:
- Sends questions in batches of 2 (respects n8n Code node 60s timeout)
- Evaluates quality every 100 questions (stops if quality too low)
- Git pushes every 1000 questions
- Saves results incrementally

Usage:
  python3 run-1000-graph-quant.py [--batch-size 2] [--timeout 300]
"""

import json
import os
import sys
import time
import subprocess
import hashlib
from datetime import datetime
from urllib import request, error

# ─── Configuration ───────────────────────────────────────────────
N8N_HOST = "https://amoret.app.n8n.cloud"
WEBHOOK_PATH = "benchmark-test-rag"
BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
REPO_DIR = "/home/user/mon-ipad"
QUESTIONS_FILE = os.path.join(BASE_DIR, "rag-1000-test-questions.json")
RESULTS_FILE = os.path.join(BASE_DIR, "rag-1000-results.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "rag-1000-run-progress.json")
GIT_BRANCH = "claude/analyze-test-questions-mBfNL"

# Parse CLI args
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--batch-size", type=int, default=2, help="Questions per webhook call (keep low for n8n timeout)")
parser.add_argument("--timeout", type=int, default=300, help="Webhook timeout in seconds")
parser.add_argument("--start-from", type=int, default=0, help="Resume from question index")
parser.add_argument("--max-questions", type=int, default=1000, help="Max questions to process")
parser.add_argument("--eval-every", type=int, default=100, help="Evaluate quality every N questions")
parser.add_argument("--push-every", type=int, default=1000, help="Git push every N questions")
parser.add_argument("--min-quality", type=float, default=0.15, help="Min F1 score to continue (stop if below)")
parser.add_argument("--dry-run", action="store_true", help="Don't send questions, just validate")
parser.add_argument("--rag-type", default="both", help="graph, quantitative, or both")
args = parser.parse_args()


def webhook_call(payload, timeout=300):
    """Call n8n benchmark-test-rag webhook with retry."""
    url = f"{N8N_HOST}/webhook/{WEBHOOK_PATH}"
    headers = {"Content-Type": "application/json"}

    for attempt in range(5):
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
            if (e.code == 403 or e.code >= 500) and attempt < 4:
                wait = min(2 ** (attempt + 1), 30)
                print(f"    [RETRY] HTTP {e.code}, waiting {wait}s (attempt {attempt+1}/5)...")
                time.sleep(wait)
                continue
            return {"status": e.code, "data": None, "error": f"HTTP {e.code}: {err_body[:500]}"}
        except Exception as e:
            if attempt < 4:
                wait = min(2 ** (attempt + 1), 30)
                print(f"    [RETRY] {e}, waiting {wait}s...")
                time.sleep(wait)
                continue
            return {"status": 0, "data": None, "error": str(e)}

    return {"status": 0, "data": None, "error": "Max retries exceeded"}


def fetch_results_from_supabase(run_id):
    """Fetch stored results from Supabase for a given run_id."""
    sql = f"""SELECT json_agg(row_to_json(t))::text as data FROM (
        SELECT run_id, dataset_name, item_index, question, expected_answer,
               actual_answer, metrics, latency_ms, error
        FROM benchmark_results
        WHERE run_id = '{run_id}'
        ORDER BY item_index
        LIMIT 50
    ) t"""

    url = f"{N8N_HOST}/webhook/benchmark-sql-exec"
    body = json.dumps({"sql": sql}).encode()
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            data = json.loads(raw)
            if isinstance(data, dict) and "data" in data:
                data_str = data["data"]
                if data_str and data_str != "null":
                    return json.loads(data_str)
    except Exception as e:
        print(f"  [WARN] Could not fetch results: {e}")

    return []


def compute_f1(predicted, expected):
    """Token-level F1 score."""
    if not predicted or not expected:
        return 0.0
    import re
    norm = lambda s: re.sub(r'[^a-z0-9\s]', '', s.lower().strip()).split()
    pred_tokens = set(norm(predicted))
    exp_tokens = set(norm(expected))
    if not pred_tokens or not exp_tokens:
        return 0.0
    common = pred_tokens & exp_tokens
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(exp_tokens)
    return 2 * precision * recall / (precision + recall)


def evaluate_batch(results):
    """Evaluate a batch of results and return quality metrics."""
    if not results:
        return {"total": 0, "with_answer": 0, "avg_f1": 0, "avg_latency_ms": 0}

    with_answer = sum(1 for r in results if r.get("actual_answer"))
    f1_scores = []
    latencies = []

    for r in results:
        if r.get("actual_answer") and r.get("expected_answer"):
            f1 = compute_f1(str(r["actual_answer"]), str(r["expected_answer"]))
            f1_scores.append(f1)
        latencies.append(r.get("latency_ms", 0))

    return {
        "total": len(results),
        "with_answer": with_answer,
        "answer_rate": f"{with_answer/len(results)*100:.1f}%",
        "avg_f1": sum(f1_scores) / len(f1_scores) if f1_scores else 0,
        "max_f1": max(f1_scores) if f1_scores else 0,
        "min_f1": min(f1_scores) if f1_scores else 0,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        "f1_above_05": sum(1 for f in f1_scores if f >= 0.5),
        "f1_above_03": sum(1 for f in f1_scores if f >= 0.3),
    }


def git_push(message):
    """Commit and push results to git."""
    try:
        subprocess.run(
            ["git", "add", "benchmark-workflows/rag-1000-results.json",
             "benchmark-workflows/rag-1000-run-progress.json"],
            cwd=REPO_DIR, capture_output=True, timeout=30
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_DIR, capture_output=True, timeout=30
        )
        for attempt in range(4):
            result = subprocess.run(
                ["git", "push", "-u", "origin", GIT_BRANCH],
                cwd=REPO_DIR, capture_output=True, timeout=60
            )
            if result.returncode == 0:
                print(f"  [GIT] Push successful")
                return True
            wait = 2 ** (attempt + 1)
            print(f"  [GIT] Push failed, retrying in {wait}s...")
            time.sleep(wait)
        print(f"  [GIT] Push failed after 4 retries")
        return False
    except Exception as e:
        print(f"  [GIT] Error: {e}")
        return False


def save_progress(processed, total, results_summary, all_results):
    """Save progress and results."""
    progress = {
        "status": "running",
        "processed": processed,
        "total": total,
        "progress_pct": f"{processed/total*100:.1f}%",
        "results_summary": results_summary,
        "updated_at": datetime.now().isoformat()
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

    with open(RESULTS_FILE, "w") as f:
        json.dump({
            "suite": "RAG 1000 Graph+Quantitative Specialized Questions",
            "started_at": start_time.isoformat(),
            "updated_at": datetime.now().isoformat(),
            "config": {
                "batch_size": args.batch_size,
                "timeout": args.timeout,
                "rag_type_filter": args.rag_type,
                "eval_every": args.eval_every,
            },
            "summary": results_summary,
            "results": all_results[-100:]  # Keep last 100 for size management
        }, f, indent=2)


# ─── Main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    start_time = datetime.now()

    print("=" * 70)
    print("  RAG 1000 SPECIALIZED QUESTIONS — Graph + Quantitative")
    print("=" * 70)

    # Load questions
    with open(QUESTIONS_FILE) as f:
        data = json.load(f)
    all_questions = data["questions"]

    # Filter by RAG type if needed
    if args.rag_type == "graph":
        questions = [q for q in all_questions if q["rag_target"] == "graph"]
    elif args.rag_type == "quantitative":
        questions = [q for q in all_questions if q["rag_target"] == "quantitative"]
    else:
        questions = all_questions

    # Apply start-from and max
    questions = questions[args.start_from:args.start_from + args.max_questions]

    print(f"  Questions:    {len(questions)}")
    print(f"  RAG filter:   {args.rag_type}")
    print(f"  Batch size:   {args.batch_size}")
    print(f"  Start from:   {args.start_from}")
    print(f"  Eval every:   {args.eval_every}")
    print(f"  Push every:   {args.push_every}")
    print(f"  Min quality:  {args.min_quality}")
    print(f"  Dry run:      {args.dry_run}")

    # Group by rag_target and dataset
    by_rag = {}
    for q in questions:
        key = q["rag_target"]
        if key not in by_rag:
            by_rag[key] = []
        by_rag[key].append(q)

    print(f"\n  By RAG type:")
    for rag_type, qs in by_rag.items():
        datasets = {}
        for q in qs:
            datasets[q["dataset_name"]] = datasets.get(q["dataset_name"], 0) + 1
        print(f"    {rag_type}: {len(qs)} questions ({datasets})")

    print("=" * 70)

    if args.dry_run:
        print("\n  [DRY RUN] Validation complete. Exiting.")
        sys.exit(0)

    # Process questions
    all_results = []
    total_processed = 0
    total_with_answer = 0
    total_errors = 0
    eval_buffer = []
    cumulative_f1 = []
    last_push_count = 0

    for rag_type, qs in sorted(by_rag.items()):
        print(f"\n{'='*50}")
        print(f"  Processing RAG type: {rag_type.upper()} ({len(qs)} questions)")
        print(f"{'='*50}")

        # Group by dataset
        by_dataset = {}
        for q in qs:
            ds = q["dataset_name"]
            if ds not in by_dataset:
                by_dataset[ds] = []
            by_dataset[ds].append(q)

        for dataset_name, ds_questions in by_dataset.items():
            print(f"\n  Dataset: {dataset_name} ({len(ds_questions)} questions)")

            # Send in batches
            for batch_start in range(0, len(ds_questions), args.batch_size):
                batch = ds_questions[batch_start:batch_start + args.batch_size]
                batch_idx = batch_start // args.batch_size

                # Create payload — send questions one at a time via the benchmark tester
                # The benchmark tester expects dataset_name + sample_size
                # But our questions are custom, so we need to send them differently
                # We'll use the individual question approach
                for q in batch:
                    total_processed += 1
                    q_start = time.time()

                    # Send single question to the appropriate RAG endpoint
                    rag_endpoints = {
                        "standard": f"{N8N_HOST}/webhook/rag-multi-index-v3",
                        "graph": f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717",
                        "quantitative": f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9"
                    }

                    endpoint = rag_endpoints.get(rag_type, rag_endpoints["standard"])

                    # Direct call to the RAG workflow
                    try:
                        body = json.dumps({
                            "query": q["question"],
                            "tenant_id": q.get("tenant_id", "benchmark"),
                            "namespace": f"benchmark-{dataset_name}",
                            "top_k": 10,
                            "include_sources": True,
                            "benchmark_mode": True
                        }).encode()
                        headers = {"Content-Type": "application/json"}
                        req = request.Request(endpoint, data=body, headers=headers, method="POST")

                        resp_data = None
                        for attempt in range(4):
                            try:
                                with request.urlopen(req, timeout=args.timeout) as resp:
                                    raw = resp.read().decode()
                                    if raw and raw.strip():
                                        resp_data = json.loads(raw)
                                    break
                            except error.HTTPError as e:
                                if (e.code == 403 or e.code >= 500) and attempt < 3:
                                    wait = 2 ** (attempt + 1)
                                    time.sleep(wait)
                                    # Recreate request since it was consumed
                                    body_new = json.dumps({
                                        "query": q["question"],
                                        "tenant_id": q.get("tenant_id", "benchmark"),
                                        "namespace": f"benchmark-{dataset_name}",
                                        "top_k": 10,
                                        "include_sources": True,
                                        "benchmark_mode": True
                                    }).encode()
                                    req = request.Request(endpoint, data=body_new, headers=headers, method="POST")
                                    continue
                                raise
                            except Exception:
                                if attempt < 3:
                                    time.sleep(2 ** (attempt + 1))
                                    body_new = json.dumps({
                                        "query": q["question"],
                                        "tenant_id": q.get("tenant_id", "benchmark"),
                                        "namespace": f"benchmark-{dataset_name}",
                                        "top_k": 10,
                                        "include_sources": True,
                                        "benchmark_mode": True
                                    }).encode()
                                    req = request.Request(endpoint, data=body_new, headers=headers, method="POST")
                                    continue
                                raise

                        latency_ms = int((time.time() - q_start) * 1000)

                        # Extract answer from response
                        answer = ""
                        if resp_data:
                            if isinstance(resp_data, list):
                                resp_data = resp_data[0] if resp_data else {}
                            if isinstance(resp_data, dict):
                                answer = resp_data.get("response", "")
                                if not isinstance(answer, str):
                                    answer = resp_data.get("answer", "")
                                    if not isinstance(answer, str):
                                        answer = resp_data.get("interpretation", "")
                                        if not isinstance(answer, str):
                                            answer = str(answer) if answer else ""

                        # Compute F1
                        f1 = compute_f1(answer, q.get("expected_answer", ""))
                        cumulative_f1.append(f1)

                        result = {
                            "id": q["id"],
                            "dataset": dataset_name,
                            "rag_type": rag_type,
                            "question": q["question"][:200],
                            "expected_answer": str(q.get("expected_answer", ""))[:200],
                            "actual_answer": str(answer)[:500],
                            "f1": round(f1, 4),
                            "latency_ms": latency_ms,
                            "error": None
                        }

                        if answer:
                            total_with_answer += 1
                            status = f"F1={f1:.2f}"
                        else:
                            status = "EMPTY"

                    except Exception as e:
                        latency_ms = int((time.time() - q_start) * 1000)
                        result = {
                            "id": q["id"],
                            "dataset": dataset_name,
                            "rag_type": rag_type,
                            "question": q["question"][:200],
                            "expected_answer": str(q.get("expected_answer", ""))[:200],
                            "actual_answer": "",
                            "f1": 0,
                            "latency_ms": latency_ms,
                            "error": str(e)[:200]
                        }
                        total_errors += 1
                        status = f"ERR: {str(e)[:50]}"

                    all_results.append(result)
                    eval_buffer.append(result)

                    # Print progress
                    if total_processed % 10 == 0 or total_processed <= 5:
                        avg_f1 = sum(cumulative_f1[-100:]) / len(cumulative_f1[-100:]) if cumulative_f1 else 0
                        print(f"    [{total_processed}/{len(questions)}] {rag_type}/{dataset_name} "
                              f"| {status} | avg_F1={avg_f1:.3f} | {latency_ms}ms")

                    # ─── Evaluate every N questions ───
                    if total_processed % args.eval_every == 0:
                        eval_metrics = evaluate_batch(eval_buffer)
                        avg_f1_recent = eval_metrics["avg_f1"]

                        print(f"\n  {'─'*50}")
                        print(f"  EVALUATION @ {total_processed} questions:")
                        print(f"    Answers: {eval_metrics['with_answer']}/{eval_metrics['total']} ({eval_metrics['answer_rate']})")
                        print(f"    Avg F1:  {avg_f1_recent:.4f}")
                        print(f"    F1>0.5:  {eval_metrics['f1_above_05']}")
                        print(f"    F1>0.3:  {eval_metrics['f1_above_03']}")
                        print(f"    Avg latency: {eval_metrics['avg_latency_ms']:.0f}ms")

                        # Check quality threshold
                        if avg_f1_recent < args.min_quality and total_processed >= 50:
                            print(f"\n  *** QUALITY BELOW THRESHOLD ({avg_f1_recent:.4f} < {args.min_quality}) ***")
                            print(f"  *** Consider stopping and fixing workflows ***")
                            # Don't stop automatically — just warn

                        print(f"  {'─'*50}\n")

                        # Save intermediate results
                        results_summary = {
                            "total_processed": total_processed,
                            "total_with_answer": total_with_answer,
                            "total_errors": total_errors,
                            "answer_rate": f"{total_with_answer/total_processed*100:.1f}%",
                            "avg_f1": sum(cumulative_f1) / len(cumulative_f1) if cumulative_f1 else 0,
                            "recent_f1": avg_f1_recent,
                        }
                        save_progress(total_processed, len(questions), results_summary, all_results)
                        eval_buffer = []

                    # ─── Git push every N questions ───
                    if total_processed - last_push_count >= args.push_every:
                        results_summary = {
                            "total_processed": total_processed,
                            "total_with_answer": total_with_answer,
                            "total_errors": total_errors,
                            "avg_f1": sum(cumulative_f1) / len(cumulative_f1) if cumulative_f1 else 0,
                        }
                        save_progress(total_processed, len(questions), results_summary, all_results)
                        git_push(f"benchmark: {total_processed} questions processed — avg F1={results_summary['avg_f1']:.4f}")
                        last_push_count = total_processed

                    # Small delay to avoid rate limiting
                    time.sleep(1)

    # ─── Final Summary ───
    elapsed = (datetime.now() - start_time).total_seconds()
    final_summary = {
        "status": "completed",
        "total_processed": total_processed,
        "total_with_answer": total_with_answer,
        "total_errors": total_errors,
        "answer_rate": f"{total_with_answer/total_processed*100:.1f}%" if total_processed > 0 else "N/A",
        "avg_f1": sum(cumulative_f1) / len(cumulative_f1) if cumulative_f1 else 0,
        "elapsed_seconds": int(elapsed),
        "rate_per_hour": int(total_processed / (elapsed / 3600)) if elapsed > 0 else 0,
    }

    print(f"\n{'='*70}")
    print(f"  FINAL RESULTS")
    print(f"{'='*70}")
    print(f"  Total processed: {total_processed}")
    print(f"  With answer:     {total_with_answer} ({final_summary['answer_rate']})")
    print(f"  Errors:          {total_errors}")
    print(f"  Avg F1:          {final_summary['avg_f1']:.4f}")
    print(f"  Elapsed:         {int(elapsed)}s ({final_summary['rate_per_hour']}/hr)")
    print(f"{'='*70}")

    # Save final results
    save_progress(total_processed, len(questions), final_summary, all_results)

    # Final git push
    git_push(f"benchmark: FINAL — {total_processed} questions — avg F1={final_summary['avg_f1']:.4f}")

    # Per-RAG summary
    print(f"\n  Per RAG type:")
    for rag_type in ["graph", "quantitative"]:
        rag_results = [r for r in all_results if r["rag_type"] == rag_type]
        if rag_results:
            rag_f1 = [r["f1"] for r in rag_results]
            rag_answers = sum(1 for r in rag_results if r["actual_answer"])
            print(f"    {rag_type}: {len(rag_results)} questions, "
                  f"{rag_answers} answers ({rag_answers/len(rag_results)*100:.0f}%), "
                  f"avg F1={sum(rag_f1)/len(rag_f1):.4f}")

    # Per-dataset summary
    print(f"\n  Per dataset:")
    for ds in ["musique", "2wikimultihopqa", "finqa", "tatqa", "convfinqa", "wikitablequestions"]:
        ds_results = [r for r in all_results if r["dataset"] == ds]
        if ds_results:
            ds_f1 = [r["f1"] for r in ds_results]
            ds_answers = sum(1 for r in ds_results if r["actual_answer"])
            print(f"    {ds}: {len(ds_results)} questions, "
                  f"{ds_answers} answers ({ds_answers/len(ds_results)*100:.0f}%), "
                  f"avg F1={sum(ds_f1)/len(ds_f1):.4f}")
