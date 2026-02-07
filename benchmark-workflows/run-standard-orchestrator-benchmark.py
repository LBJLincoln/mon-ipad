#!/usr/bin/env python3
"""
Benchmark Runner — 50 Standard RAG + 50 Orchestrator questions
================================================================
Usage:
  python3 run-standard-orchestrator-benchmark.py [--timeout 180] [--delay 2]
"""
import json, os, re, sys, time, subprocess
from datetime import datetime
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
STANDARD_RAG_WEBHOOK = f"{N8N_HOST}/webhook/rag-multi-index-v3"
ORCHESTRATOR_WEBHOOK = f"{N8N_HOST}/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0"
TENANT_ID = "benchmark"

BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
REPO_DIR = "/home/user/mon-ipad"
QUESTIONS_FILE = os.path.join(BASE_DIR, "benchmark-standard-orchestrator-questions.json")
RESULTS_FILE = os.path.join(BASE_DIR, "benchmark-standard-orchestrator-results.json")
GIT_BRANCH = "claude/verify-sql-results-nuklI"

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--timeout", type=int, default=180)
parser.add_argument("--delay", type=float, default=2.0)
parser.add_argument("--max-questions", type=int, default=100)
parser.add_argument("--rag-type", default="both", choices=["standard", "orchestrator", "both"])
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()


def call_webhook(url, payload, timeout=180):
    headers = {"Content-Type": "application/json"}
    for attempt in range(4):
        body = json.dumps(payload).encode()
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                if not raw or not raw.strip():
                    return {"error": f"Empty response (HTTP {resp.status})", "data": None}
                try:
                    return {"error": None, "data": json.loads(raw)}
                except json.JSONDecodeError:
                    return {"error": None, "data": raw}
        except error.HTTPError as e:
            err_body = ""
            try: err_body = e.read().decode()[:500]
            except: pass
            if (e.code == 403 or e.code >= 500) and attempt < 3:
                wait = 2 ** (attempt + 1)
                print(f"      [RETRY] HTTP {e.code}, wait {wait}s ({attempt+1}/4)")
                time.sleep(wait)
                continue
            return {"error": f"HTTP {e.code}: {err_body}", "data": None}
        except Exception as e:
            if attempt < 3:
                wait = 2 ** (attempt + 1)
                print(f"      [RETRY] {str(e)[:80]}, wait {wait}s")
                time.sleep(wait)
                continue
            return {"error": str(e), "data": None}
    return {"error": "Max retries exceeded", "data": None}


def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-z0-9\s\.]', '', str(text).lower().strip())


def compute_f1(predicted, expected):
    pred_tokens = set(normalize(predicted).split())
    exp_tokens = set(normalize(expected).split())
    if not pred_tokens or not exp_tokens: return 0.0
    common = pred_tokens & exp_tokens
    if not common: return 0.0
    p = len(common) / len(pred_tokens)
    r = len(common) / len(exp_tokens)
    return 2 * p * r / (p + r)


def extract_number(text):
    if not text: return None
    text = str(text)
    clean = re.sub(r'[$€£]', '', text)
    clean = re.sub(r'(\d),(\d)', r'\1\2', clean)
    matches = re.findall(r'-?\d+\.?\d*', clean)
    if not matches: return None
    numbers = []
    for m in matches:
        try: numbers.append(float(m))
        except: continue
    if not numbers: return None
    if len(numbers) == 1: return numbers[0]
    non_years = [n for n in numbers if not (2019 <= n <= 2030)]
    if non_years: return max(non_years, key=abs)
    return numbers[0]


def evaluate_answer(actual, expected, rag_type, raw_results=None):
    result = {
        "has_answer": bool(actual and str(actual).strip()),
        "answer_correct": False,
        "f1": 0.0,
        "notes": []
    }
    if not result["has_answer"]:
        result["notes"].append("NO_ANSWER")
        return result

    result["f1"] = compute_f1(str(actual), str(expected))

    # Check entity presence
    answer_norm = normalize(actual)
    expected_parts = [e.strip() for e in str(expected).split(",")]
    found = 0
    for part in expected_parts:
        words = [w for w in normalize(part).split() if len(w) > 2]
        if words and all(w in answer_norm for w in words):
            found += 1

    if len(expected_parts) > 0 and found / len(expected_parts) >= 0.5:
        result["answer_correct"] = True
        result["notes"].append(f"ENTITY_MATCH: {found}/{len(expected_parts)}")
    elif result["f1"] >= 0.3:
        result["answer_correct"] = True
        result["notes"].append(f"F1_MATCH: {result['f1']:.3f}")
    else:
        # Numeric check
        a_num = extract_number(str(actual))
        e_num = extract_number(str(expected))
        if a_num and e_num and e_num != 0:
            ratio = a_num / e_num
            if 0.95 <= ratio <= 1.05:
                result["answer_correct"] = True
                result["notes"].append(f"NUMERIC_MATCH: {a_num}≈{e_num}")
            else:
                result["notes"].append(f"NUMERIC_MISMATCH: {a_num} vs {e_num}")
        else:
            # Substring
            if normalize(expected) in answer_norm:
                result["answer_correct"] = True
                result["notes"].append("SUBSTRING_MATCH")
            else:
                result["notes"].append(f"PARTIAL: {found}/{len(expected_parts)}, F1={result['f1']:.3f}")

    return result


def save_results(all_results, summary, status="running"):
    output = {
        "suite": "Benchmark 50×2 — Standard RAG + Orchestrator",
        "status": status,
        "started_at": start_time.isoformat(),
        "updated_at": datetime.now().isoformat(),
        "config": {
            "standard_webhook": STANDARD_RAG_WEBHOOK,
            "orchestrator_webhook": ORCHESTRATOR_WEBHOOK,
            "tenant_id": TENANT_ID
        },
        "summary": summary,
        "results": all_results
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def git_push(message):
    try:
        subprocess.run(["git", "add",
            "benchmark-workflows/benchmark-standard-orchestrator-results.json",
            "benchmark-workflows/benchmark-standard-orchestrator-questions.json"],
            cwd=REPO_DIR, capture_output=True, timeout=30)
        subprocess.run(["git", "commit", "-m", message],
            cwd=REPO_DIR, capture_output=True, timeout=30)
        for attempt in range(4):
            r = subprocess.run(["git", "push", "-u", "origin", GIT_BRANCH],
                cwd=REPO_DIR, capture_output=True, timeout=60)
            if r.returncode == 0:
                print(f"  [GIT] Push OK")
                return True
            time.sleep(2 ** (attempt + 1))
        return False
    except Exception as e:
        print(f"  [GIT] Error: {e}")
        return False


if __name__ == "__main__":
    start_time = datetime.now()
    print("=" * 70)
    print("  BENCHMARK 50×2 — Standard RAG + Orchestrator Evaluation")
    print(f"  Started: {start_time.isoformat()}")
    print("=" * 70)

    with open(QUESTIONS_FILE) as f:
        data = json.load(f)
    all_questions = data["questions"]

    if args.rag_type == "standard":
        questions = [q for q in all_questions if q["rag_target"] == "standard"]
    elif args.rag_type == "orchestrator":
        questions = [q for q in all_questions if q["rag_target"] == "orchestrator"]
    else:
        questions = all_questions
    questions = questions[:args.max_questions]

    std_count = sum(1 for q in questions if q["rag_target"] == "standard")
    orch_count = sum(1 for q in questions if q["rag_target"] == "orchestrator")
    print(f"  Total: {len(questions)} | Standard: {std_count} | Orchestrator: {orch_count}")
    print("=" * 70)

    if args.dry_run:
        print("  [DRY RUN] Done.")
        sys.exit(0)

    all_results = []
    std_results = []
    orch_results = []

    for i, q in enumerate(questions):
        q_id = q["id"]
        rag_type = q["rag_target"]
        question = q["question"]
        expected = q.get("expected_answer", "")

        print(f"\n  [{i+1}/{len(questions)}] {q_id} ({rag_type})")
        print(f"    Q: {question[:100]}...")

        if rag_type == "standard":
            webhook = STANDARD_RAG_WEBHOOK
            payload = {
                "query": question,
                "tenant_id": TENANT_ID,
                "namespace": q.get("namespace", "benchmark-squad_v2"),
                "top_k": 10,
                "include_sources": True,
                "benchmark_mode": True
            }
        else:
            webhook = ORCHESTRATOR_WEBHOOK
            payload = {
                "query": question,
                "tenant_id": TENANT_ID,
                "user_groups": ["default"]
            }

        t0 = time.time()
        response = call_webhook(webhook, payload, timeout=args.timeout)
        latency_ms = int((time.time() - t0) * 1000)

        actual_answer = ""
        raw_results = []
        resp_status = "ERROR"
        routing_info = ""

        if response["error"]:
            print(f"    ERROR: {response['error'][:100]}")
        elif response["data"]:
            d = response["data"]
            if isinstance(d, list):
                d = d[0] if d else {}
            if isinstance(d, dict):
                # Try various response fields
                actual_answer = (d.get("response") or d.get("answer") or
                    d.get("interpretation") or d.get("result") or
                    d.get("output") or "")
                if isinstance(actual_answer, dict):
                    actual_answer = actual_answer.get("response", str(actual_answer))
                resp_status = d.get("status", "UNKNOWN")
                raw_results = d.get("raw_results", [])
                routing_info = str(d.get("routing", d.get("engines_used", d.get("metadata", {}).get("routing", ""))))

        evaluation = evaluate_answer(actual_answer, expected, rag_type, raw_results)

        result = {
            "id": q_id,
            "rag_type": rag_type,
            "question": question,
            "expected_answer": expected,
            "actual_answer": str(actual_answer)[:1000],
            "response_status": resp_status,
            "routing_info": routing_info[:500],
            "latency_ms": latency_ms,
            "evaluation": evaluation,
            "error": response["error"],
            "category": q.get("category", ""),
            "timestamp": datetime.now().isoformat()
        }

        all_results.append(result)
        if rag_type == "standard":
            std_results.append(result)
        else:
            orch_results.append(result)

        icon = "+" if evaluation["answer_correct"] else "-"
        print(f"    [{icon}] F1={evaluation['f1']:.3f} | {latency_ms}ms | {', '.join(evaluation.get('notes', []))}")
        if actual_answer:
            print(f"    A: {str(actual_answer)[:120]}...")

        if (i + 1) % 10 == 0:
            s_ok = sum(1 for r in std_results if r["evaluation"]["answer_correct"])
            o_ok = sum(1 for r in orch_results if r["evaluation"]["answer_correct"])
            save_results(all_results, {
                "processed": i + 1,
                "standard": {"total": len(std_results), "correct": s_ok},
                "orchestrator": {"total": len(orch_results), "correct": o_ok}
            })
            print(f"\n  --- Checkpoint @ {i+1}: Std {s_ok}/{len(std_results)} | Orch {o_ok}/{len(orch_results)} ---\n")

        if i < len(questions) - 1:
            time.sleep(args.delay)

    # Final
    elapsed = (datetime.now() - start_time).total_seconds()

    def summarize(results):
        if not results: return {"total": 0, "correct": 0, "accuracy": "N/A"}
        correct = sum(1 for r in results if r["evaluation"]["answer_correct"])
        has_answer = sum(1 for r in results if r["evaluation"]["has_answer"])
        f1s = [r["evaluation"]["f1"] for r in results]
        lats = [r["latency_ms"] for r in results]
        errs = sum(1 for r in results if r["error"])
        return {
            "total": len(results), "correct": correct,
            "accuracy": f"{correct/len(results)*100:.1f}%",
            "has_answer": has_answer,
            "answer_rate": f"{has_answer/len(results)*100:.1f}%",
            "errors": errs,
            "avg_f1": round(sum(f1s)/len(f1s), 4) if f1s else 0,
            "avg_latency_ms": int(sum(lats)/len(lats)) if lats else 0,
            "p95_latency_ms": int(sorted(lats)[int(len(lats)*0.95)]) if lats else 0
        }

    std_sum = summarize(std_results)
    orch_sum = summarize(orch_results)
    total_ok = std_sum["correct"] + orch_sum["correct"]
    total_n = std_sum["total"] + orch_sum["total"]

    final = {
        "status": "completed", "elapsed_seconds": int(elapsed),
        "total_questions": total_n, "total_correct": total_ok,
        "overall_accuracy": f"{total_ok/total_n*100:.1f}%" if total_n else "N/A",
        "standard_rag": std_sum, "orchestrator": orch_sum
    }

    print(f"\n{'='*70}")
    print(f"  FINAL RESULTS")
    print(f"{'='*70}")
    print(f"  Elapsed:       {int(elapsed)}s")
    print(f"  Overall:       {total_ok}/{total_n} ({final['overall_accuracy']})")
    print(f"\n  STANDARD RAG ({std_sum['total']}):")
    print(f"    Correct:     {std_sum['correct']} ({std_sum['accuracy']})")
    print(f"    Avg F1:      {std_sum['avg_f1']}")
    print(f"    Avg latency: {std_sum['avg_latency_ms']}ms")
    print(f"\n  ORCHESTRATOR ({orch_sum['total']}):")
    print(f"    Correct:     {orch_sum['correct']} ({orch_sum['accuracy']})")
    print(f"    Avg F1:      {orch_sum['avg_f1']}")
    print(f"    Avg latency: {orch_sum['avg_latency_ms']}ms")
    print(f"{'='*70}")

    # Category breakdown
    print(f"\n  By category:")
    cats = {}
    for r in all_results:
        c = r.get("category", "unknown")
        cats.setdefault(c, {"total": 0, "correct": 0})
        cats[c]["total"] += 1
        if r["evaluation"]["answer_correct"]: cats[c]["correct"] += 1
    for c, s in sorted(cats.items()):
        print(f"    {c:25s} {s['correct']:3d}/{s['total']:3d} ({s['correct']/s['total']*100:.0f}%)")

    save_results(all_results, final, "completed")
    print(f"\n  Results: {RESULTS_FILE}")
    git_push(f"benchmark: Std+Orch — Std {std_sum['accuracy']} | Orch {orch_sum['accuracy']} | Overall {final['overall_accuracy']}")
