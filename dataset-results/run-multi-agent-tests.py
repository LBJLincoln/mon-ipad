#!/usr/bin/env python3
"""
MULTI-AGENT RAG TEST RUNNER
=============================
Tests 1000 Graph+Quantitative RAG questions using concurrent workers.
Focus: Graph RAG (musique, 2wikimultihopqa) and Quantitative RAG (finqa, tatqa, convfinqa, wikitablequestions).

Features:
- Concurrent workers (configurable, default 5)
- Checkpoint verification every 100 questions
- Auto-correction detection after first 100
- Git push every 1000 questions
- Per-dataset result files updated incrementally
- F1 scoring with quality monitoring

Usage:
  python3 run-multi-agent-tests.py [--workers 5] [--batch-size 1] [--verify-first]

  --verify-first   Run data verification before starting tests
  --workers N      Number of concurrent workers (default 5)
  --rag-type X     graph, quantitative, or both (default both)
  --start-from N   Resume from question index N
  --max-questions  Max questions to process (default 1000)
  --dry-run        Validate without sending questions
"""

import json
import os
import sys
import time
import re
import subprocess
import hashlib
import argparse
from datetime import datetime
from urllib import request, error
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ─── Configuration ──────────────────────────────────────────────
N8N_HOST = "https://amoret.app.n8n.cloud"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
QUESTIONS_FILE = os.path.join(REPO_DIR, "benchmark-workflows", "rag-1000-test-questions.json")
RESULTS_DIR = BASE_DIR
GIT_BRANCH = "claude/analyze-datasets-qa-5LJIH"

# RAG workflow endpoints
RAG_ENDPOINTS = {
    "standard": f"{N8N_HOST}/webhook/rag-multi-index-v3",
    "graph": f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9"
}

# Thread-safe counters
lock = Lock()
stats = {
    "total_processed": 0,
    "total_answered": 0,
    "total_errors": 0,
    "f1_scores": [],
    "latencies": [],
    "by_dataset": {},
    "by_rag_type": {"graph": {"processed": 0, "answered": 0, "f1_sum": 0},
                     "quantitative": {"processed": 0, "answered": 0, "f1_sum": 0}},
}

# Per-dataset result caches
dataset_results_cache = {}
dataset_locks = {}


def parse_args():
    parser = argparse.ArgumentParser(description="Multi-Agent RAG Test Runner")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent workers")
    parser.add_argument("--batch-size", type=int, default=1, help="Questions per request")
    parser.add_argument("--timeout", type=int, default=300, help="Request timeout (s)")
    parser.add_argument("--start-from", type=int, default=0, help="Resume from index")
    parser.add_argument("--max-questions", type=int, default=1000, help="Max questions")
    parser.add_argument("--eval-every", type=int, default=100, help="Evaluate every N")
    parser.add_argument("--push-every", type=int, default=1000, help="Git push every N")
    parser.add_argument("--min-quality", type=float, default=0.05, help="Min avg F1")
    parser.add_argument("--rag-type", default="both", choices=["graph", "quantitative", "both"])
    parser.add_argument("--verify-first", action="store_true", help="Verify data before testing")
    parser.add_argument("--dry-run", action="store_true", help="Validate only")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (s)")
    return parser.parse_args()


def compute_f1(predicted, expected):
    """Token-level F1 score between predicted and expected answers."""
    if not predicted or not expected:
        return 0.0
    norm = lambda s: re.sub(r'[^a-z0-9\s]', '', str(s).lower().strip()).split()
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


def send_question(question, rag_type, timeout=300):
    """Send a single question to the appropriate RAG endpoint."""
    endpoint = RAG_ENDPOINTS.get(rag_type, RAG_ENDPOINTS["standard"])
    dataset_name = question.get("dataset_name", "unknown")

    payload = {
        "query": question["question"],
        "tenant_id": question.get("tenant_id", "benchmark"),
        "namespace": f"benchmark-{dataset_name}",
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True
    }

    headers = {"Content-Type": "application/json"}
    start_time = time.time()

    for attempt in range(4):
        try:
            body = json.dumps(payload).encode()
            req = request.Request(endpoint, data=body, headers=headers, method="POST")

            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                latency_ms = int((time.time() - start_time) * 1000)

                if not raw or raw.strip() == "":
                    return {"answer": "", "latency_ms": latency_ms, "error": "Empty response", "raw": None}

                try:
                    resp_data = json.loads(raw)
                except json.JSONDecodeError:
                    return {"answer": raw[:500], "latency_ms": latency_ms, "error": None, "raw": raw[:1000]}

                # Extract answer from various response formats
                answer = ""
                if isinstance(resp_data, list):
                    resp_data = resp_data[0] if resp_data else {}
                if isinstance(resp_data, dict):
                    for key in ["response", "answer", "interpretation", "result", "output", "text"]:
                        val = resp_data.get(key)
                        if val and isinstance(val, str) and val.strip():
                            answer = val.strip()
                            break
                    if not answer:
                        # Try nested structures
                        for key in ["data", "body"]:
                            nested = resp_data.get(key)
                            if isinstance(nested, dict):
                                for subkey in ["response", "answer", "text"]:
                                    val = nested.get(subkey)
                                    if val and isinstance(val, str):
                                        answer = val.strip()
                                        break

                return {
                    "answer": answer,
                    "latency_ms": latency_ms,
                    "error": None,
                    "raw": json.dumps(resp_data)[:1000] if resp_data else None
                }

        except error.HTTPError as e:
            if (e.code == 403 or e.code >= 500) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            err_body = ""
            try:
                err_body = e.read().decode()[:500]
            except:
                pass
            latency_ms = int((time.time() - start_time) * 1000)
            return {"answer": "", "latency_ms": latency_ms,
                    "error": f"HTTP {e.code}: {err_body}", "raw": None}

        except Exception as e:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            latency_ms = int((time.time() - start_time) * 1000)
            return {"answer": "", "latency_ms": latency_ms,
                    "error": str(e)[:300], "raw": None}

    latency_ms = int((time.time() - start_time) * 1000)
    return {"answer": "", "latency_ms": latency_ms,
            "error": "Max retries exceeded", "raw": None}


def process_question(question, rag_type, timeout=300):
    """Process a single question: send, evaluate, record."""
    q_id = question["id"]
    dataset = question["dataset_name"]
    expected = str(question.get("expected_answer", ""))

    result = send_question(question, rag_type, timeout)
    answer = result["answer"]
    f1 = compute_f1(answer, expected)

    record = {
        "id": q_id,
        "dataset": dataset,
        "rag_type": rag_type,
        "question": question["question"][:300],
        "expected_answer": expected[:300],
        "actual_answer": answer[:500] if answer else "",
        "f1_score": round(f1, 4),
        "latency_ms": result["latency_ms"],
        "error": result["error"],
        "status": "answered" if answer else ("error" if result["error"] else "empty"),
        "tested_at": datetime.now().isoformat()
    }

    # Update thread-safe stats
    with lock:
        stats["total_processed"] += 1
        stats["f1_scores"].append(f1)
        stats["latencies"].append(result["latency_ms"])

        if answer:
            stats["total_answered"] += 1
        if result["error"]:
            stats["total_errors"] += 1

        # Per RAG type
        if rag_type in stats["by_rag_type"]:
            stats["by_rag_type"][rag_type]["processed"] += 1
            if answer:
                stats["by_rag_type"][rag_type]["answered"] += 1
            stats["by_rag_type"][rag_type]["f1_sum"] += f1

        # Per dataset
        if dataset not in stats["by_dataset"]:
            stats["by_dataset"][dataset] = {"processed": 0, "answered": 0, "f1_sum": 0, "errors": 0}
        stats["by_dataset"][dataset]["processed"] += 1
        if answer:
            stats["by_dataset"][dataset]["answered"] += 1
        stats["by_dataset"][dataset]["f1_sum"] += f1
        if result["error"]:
            stats["by_dataset"][dataset]["errors"] += 1

    return record


def update_dataset_result_file(record):
    """Update the per-dataset result file with a new test result."""
    dataset = record["dataset"]
    rag_type = record["rag_type"]

    # Map to the correct result file
    if dataset == "finqa" and rag_type == "quantitative":
        filename = "results-finqa-quantitative.json"
    else:
        filename = f"results-{dataset}.json"

    filepath = os.path.join(RESULTS_DIR, filename)

    if dataset not in dataset_locks:
        dataset_locks[dataset] = Lock()

    with dataset_locks[dataset]:
        if dataset not in dataset_results_cache:
            if os.path.exists(filepath):
                with open(filepath) as f:
                    dataset_results_cache[dataset] = json.load(f)
            else:
                return

        data = dataset_results_cache[dataset]

        # Find and update the question entry
        for q in data.get("questions", []):
            if q["id"] == record["id"]:
                q["actual_answer"] = record["actual_answer"]
                q["f1_score"] = record["f1_score"]
                q["latency_ms"] = record["latency_ms"]
                q["error"] = record["error"]
                q["status"] = record["status"]
                q["tested_at"] = record["tested_at"]
                break

        # Update summary
        tested = sum(1 for q in data.get("questions", []) if q.get("status") != "not_tested")
        answered = sum(1 for q in data.get("questions", []) if q.get("status") == "answered")
        errors = sum(1 for q in data.get("questions", []) if q.get("status") == "error")
        f1_scores = [q["f1_score"] for q in data.get("questions", [])
                     if q.get("f1_score") is not None]

        data["summary"]["total_tested"] = tested
        data["summary"]["total_answered"] = answered
        data["summary"]["total_errors"] = errors
        data["summary"]["avg_f1"] = round(sum(f1_scores) / len(f1_scores), 4) if f1_scores else 0
        data["summary"]["answer_rate"] = f"{answered/tested*100:.1f}%" if tested > 0 else "0%"
        data["summary"]["status"] = "IN_PROGRESS"
        data["summary"]["last_updated"] = datetime.now().isoformat()

        # Write to disk periodically (every 10 questions per dataset)
        if tested % 10 == 0 or tested == data["total_questions"]:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)


def save_all_dataset_results():
    """Flush all cached dataset results to disk."""
    for dataset, data in dataset_results_cache.items():
        rag_type = data.get("rag_target", "")
        if dataset == "finqa" and rag_type == "quantitative":
            filename = "results-finqa-quantitative.json"
        else:
            filename = f"results-{dataset}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def save_master_progress(all_records, start_time):
    """Save master progress file."""
    elapsed = (datetime.now() - start_time).total_seconds()
    total = stats["total_processed"]
    avg_f1 = sum(stats["f1_scores"]) / len(stats["f1_scores"]) if stats["f1_scores"] else 0
    avg_latency = sum(stats["latencies"]) / len(stats["latencies"]) if stats["latencies"] else 0

    progress = {
        "suite": "Multi-Agent RAG Test Runner — Graph + Quantitative",
        "started_at": start_time.isoformat(),
        "updated_at": datetime.now().isoformat(),
        "elapsed_seconds": int(elapsed),
        "summary": {
            "total_processed": total,
            "total_answered": stats["total_answered"],
            "total_errors": stats["total_errors"],
            "answer_rate": f"{stats['total_answered']/total*100:.1f}%" if total > 0 else "0%",
            "avg_f1": round(avg_f1, 4),
            "avg_latency_ms": round(avg_latency, 0),
            "rate_per_hour": int(total / (elapsed / 3600)) if elapsed > 0 else 0,
        },
        "by_rag_type": {},
        "by_dataset": {},
        "last_100_records": all_records[-100:]
    }

    for rag_type, rag_stats in stats["by_rag_type"].items():
        if rag_stats["processed"] > 0:
            progress["by_rag_type"][rag_type] = {
                "processed": rag_stats["processed"],
                "answered": rag_stats["answered"],
                "answer_rate": f"{rag_stats['answered']/rag_stats['processed']*100:.1f}%",
                "avg_f1": round(rag_stats["f1_sum"] / rag_stats["processed"], 4)
            }

    for ds_name, ds_stats in stats["by_dataset"].items():
        if ds_stats["processed"] > 0:
            progress["by_dataset"][ds_name] = {
                "processed": ds_stats["processed"],
                "answered": ds_stats["answered"],
                "errors": ds_stats["errors"],
                "avg_f1": round(ds_stats["f1_sum"] / ds_stats["processed"], 4)
            }

    filepath = os.path.join(RESULTS_DIR, "test-run-progress.json")
    with open(filepath, "w") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    return progress


def git_push(message):
    """Commit and push results to git."""
    try:
        # Stage all result files
        subprocess.run(
            ["git", "add", "dataset-results/"],
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
            print(f"  [GIT] Push failed (attempt {attempt+1}/4), retrying in {wait}s...")
            time.sleep(wait)

        print("  [GIT] Push failed after 4 retries")
        return False
    except Exception as e:
        print(f"  [GIT] Error: {e}")
        return False


def evaluate_checkpoint(all_records, checkpoint_num, start_time):
    """Evaluate results at a checkpoint (every 100 questions)."""
    recent = all_records[-100:] if len(all_records) >= 100 else all_records

    answered = sum(1 for r in recent if r["status"] == "answered")
    errors = sum(1 for r in recent if r["status"] == "error")
    f1_scores = [r["f1_score"] for r in recent if r.get("f1_score")]
    avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0
    f1_above_03 = sum(1 for f in f1_scores if f >= 0.3)
    f1_above_05 = sum(1 for f in f1_scores if f >= 0.5)

    print(f"\n{'─'*60}")
    print(f"  CHECKPOINT #{checkpoint_num} @ {stats['total_processed']} questions")
    print(f"{'─'*60}")
    print(f"  Recent {len(recent)} questions:")
    print(f"    Answered: {answered}/{len(recent)} ({answered/len(recent)*100:.0f}%)")
    print(f"    Errors:   {errors}")
    print(f"    Avg F1:   {avg_f1:.4f}")
    print(f"    F1 > 0.3: {f1_above_03}")
    print(f"    F1 > 0.5: {f1_above_05}")

    # Per-rag breakdown for recent
    for rag_type in ["graph", "quantitative"]:
        rag_recent = [r for r in recent if r["rag_type"] == rag_type]
        if rag_recent:
            rag_answered = sum(1 for r in rag_recent if r["status"] == "answered")
            rag_f1 = [r["f1_score"] for r in rag_recent if r.get("f1_score")]
            rag_avg = sum(rag_f1) / len(rag_f1) if rag_f1 else 0
            print(f"  {rag_type}: {len(rag_recent)} tested, {rag_answered} answered, avg F1={rag_avg:.4f}")

    # Per-dataset breakdown
    for ds in ["musique", "2wikimultihopqa", "finqa", "tatqa", "convfinqa", "wikitablequestions"]:
        ds_recent = [r for r in recent if r["dataset"] == ds]
        if ds_recent:
            ds_answered = sum(1 for r in ds_recent if r["status"] == "answered")
            ds_f1 = [r["f1_score"] for r in ds_recent if r.get("f1_score")]
            ds_avg = sum(ds_f1) / len(ds_f1) if ds_f1 else 0
            print(f"    {ds}: {len(ds_recent)} tested, {ds_answered} answered, avg F1={ds_avg:.4f}")

    print(f"{'─'*60}\n")

    # Save checkpoint progress
    save_master_progress(all_records, start_time)
    save_all_dataset_results()

    return {
        "checkpoint": checkpoint_num,
        "total_processed": stats["total_processed"],
        "recent_answered": answered,
        "recent_avg_f1": avg_f1,
        "recent_f1_above_03": f1_above_03,
        "needs_correction": avg_f1 < 0.05 and answered < len(recent) * 0.3
    }


def main():
    args = parse_args()
    start_time = datetime.now()

    print("=" * 70)
    print("  MULTI-AGENT RAG TEST RUNNER")
    print("  Graph + Quantitative RAG — 1000 Specialized Questions")
    print("=" * 70)

    # ── Optional: Verify data first ──
    if args.verify_first:
        print("\n[VERIFY] Running data presence verification...")
        from verify_data_presence import main as verify_main
        report = verify_main()
        if not report["overall_readiness"]["graph_rag_ready"] and args.rag_type in ("graph", "both"):
            print("\n  WARNING: Graph RAG data is NOT ready. Graph questions will likely fail.")
            print("  Continue anyway? Set --rag-type quantitative to skip graph questions.")
        if not report["overall_readiness"]["quantitative_rag_ready"] and args.rag_type in ("quantitative", "both"):
            print("\n  WARNING: Quantitative RAG data is NOT ready. Quantitative questions will likely fail.")
            print("  Continue anyway? Set --rag-type graph to skip quantitative questions.")

    # ── Load questions ──
    print("\n[LOAD] Loading questions...")
    with open(QUESTIONS_FILE) as f:
        data = json.load(f)
    all_questions = data["questions"]

    # Filter by RAG type
    if args.rag_type == "graph":
        questions = [q for q in all_questions if q["rag_target"] == "graph"]
    elif args.rag_type == "quantitative":
        questions = [q for q in all_questions if q["rag_target"] == "quantitative"]
    else:
        questions = all_questions

    # Apply start-from and max
    questions = questions[args.start_from:args.start_from + args.max_questions]

    # Distribution
    by_dataset = {}
    for q in questions:
        by_dataset[q["dataset_name"]] = by_dataset.get(q["dataset_name"], 0) + 1

    print(f"  Total questions: {len(questions)}")
    print(f"  RAG filter:      {args.rag_type}")
    print(f"  Workers:         {args.workers}")
    print(f"  Start from:      {args.start_from}")
    print(f"  Eval every:      {args.eval_every}")
    print(f"  Push every:      {args.push_every}")
    print(f"  Delay:           {args.delay}s")
    print(f"\n  By dataset:")
    for ds, cnt in sorted(by_dataset.items()):
        rag = next(q["rag_target"] for q in questions if q["dataset_name"] == ds)
        print(f"    {ds} ({rag}): {cnt} questions")

    if args.dry_run:
        print(f"\n  [DRY RUN] Validation complete. Would test {len(questions)} questions.")
        return

    print(f"\n{'='*70}")
    print(f"  STARTING TESTS...")
    print(f"{'='*70}")

    # ── Process questions with concurrent workers ──
    all_records = []
    checkpoint_num = 0
    last_push_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        submitted = 0

        for i, q in enumerate(questions):
            rag_type = q["rag_target"]
            future = executor.submit(process_question, q, rag_type, args.timeout)
            futures[future] = (i, q)
            submitted += 1

            # Rate limiting
            if args.delay > 0:
                time.sleep(args.delay)

            # Process completed futures
            done_futures = [f for f in futures if f.done()]
            for future in done_futures:
                idx, question = futures.pop(future)
                try:
                    record = future.result(timeout=5)
                    all_records.append(record)
                    update_dataset_result_file(record)

                    # Progress display
                    processed = stats["total_processed"]
                    if processed % 10 == 0 or processed <= 5:
                        avg_f1 = sum(stats["f1_scores"][-50:]) / len(stats["f1_scores"][-50:]) if stats["f1_scores"] else 0
                        print(f"  [{processed}/{len(questions)}] {record['rag_type']}/{record['dataset']} "
                              f"| {record['status']} | F1={record['f1_score']:.3f} "
                              f"| avg_F1={avg_f1:.3f} | {record['latency_ms']}ms")

                    # Checkpoint evaluation
                    if processed % args.eval_every == 0 and processed > 0:
                        checkpoint_num += 1
                        checkpoint = evaluate_checkpoint(all_records, checkpoint_num, start_time)

                        if checkpoint["needs_correction"] and checkpoint_num == 1:
                            print("\n  *** FIRST 100 QUESTIONS SHOW LOW QUALITY ***")
                            print("  *** Possible issues:")
                            print("  ***   - Data not ingested in databases")
                            print("  ***   - Graph RAG returning community summaries instead of answers")
                            print("  ***   - Quantitative RAG missing tabular data")
                            print("  *** Consider stopping and fixing the pipeline ***\n")

                    # Git push checkpoint
                    if processed - last_push_count >= args.push_every:
                        save_all_dataset_results()
                        save_master_progress(all_records, start_time)
                        avg_f1 = sum(stats["f1_scores"]) / len(stats["f1_scores"]) if stats["f1_scores"] else 0
                        git_push(f"benchmark: {processed} questions — avg F1={avg_f1:.4f}")
                        last_push_count = processed

                except Exception as e:
                    print(f"  [ERROR] Question {idx}: {e}")

        # Wait for remaining futures
        for future in as_completed(futures):
            idx, question = futures[future]
            try:
                record = future.result(timeout=args.timeout + 30)
                all_records.append(record)
                update_dataset_result_file(record)
            except Exception as e:
                print(f"  [ERROR] Question {idx}: {e}")

    # ── Final evaluation ──
    elapsed = (datetime.now() - start_time).total_seconds()
    total = stats["total_processed"]
    avg_f1 = sum(stats["f1_scores"]) / len(stats["f1_scores"]) if stats["f1_scores"] else 0

    print(f"\n{'='*70}")
    print(f"  FINAL RESULTS")
    print(f"{'='*70}")
    print(f"  Total processed: {total}")
    print(f"  Answered:        {stats['total_answered']} ({stats['total_answered']/total*100:.1f}%)" if total > 0 else "  Answered: 0")
    print(f"  Errors:          {stats['total_errors']}")
    print(f"  Avg F1:          {avg_f1:.4f}")
    print(f"  Elapsed:         {int(elapsed)}s")
    print(f"  Rate:            {int(total/(elapsed/3600)) if elapsed > 0 else 0}/hr")

    print(f"\n  Per RAG type:")
    for rag_type, rag_stats in stats["by_rag_type"].items():
        if rag_stats["processed"] > 0:
            avg = rag_stats["f1_sum"] / rag_stats["processed"]
            rate = rag_stats["answered"] / rag_stats["processed"] * 100
            print(f"    {rag_type}: {rag_stats['processed']} tested, "
                  f"{rag_stats['answered']} answered ({rate:.0f}%), avg F1={avg:.4f}")

    print(f"\n  Per dataset:")
    for ds_name, ds_stats in sorted(stats["by_dataset"].items()):
        if ds_stats["processed"] > 0:
            avg = ds_stats["f1_sum"] / ds_stats["processed"]
            rate = ds_stats["answered"] / ds_stats["processed"] * 100
            print(f"    {ds_name}: {ds_stats['processed']} tested, "
                  f"{ds_stats['answered']} answered ({rate:.0f}%), "
                  f"avg F1={avg:.4f}, errors={ds_stats['errors']}")

    print(f"{'='*70}")

    # ── Save final results ──
    save_all_dataset_results()
    progress = save_master_progress(all_records, start_time)
    progress["summary"]["status"] = "COMPLETED"

    filepath = os.path.join(RESULTS_DIR, "test-run-progress.json")
    with open(filepath, "w") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    # ── Final git push ──
    git_push(f"benchmark: FINAL — {total} questions — avg F1={avg_f1:.4f}")


if __name__ == "__main__":
    main()
