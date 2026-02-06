#!/usr/bin/env python3
"""
DIAGNOSTIC VALIDATION: 10 questions per RAG type
=================================================
Tests the corrected workflows with a targeted sample to validate fixes:
- Standard RAG: 10 questions from squad_v2 (simple factual)
- Graph RAG: 10 questions from the 1000 specialized set (musique — multi-hop)
- Quantitative RAG: 10 questions from the 1000 specialized set (finqa — financial)

Checks:
1. Do we get non-empty answers?
2. Are answers in English (not French)?
3. Are Graph RAG answers coherent (not raw community summaries)?
4. Are Quantitative RAG answers meaningful for financial questions?
5. What is the F1 score?
"""

import json
import os
import re
import time
from datetime import datetime
from urllib import request, error

N8N_HOST = "https://amoret.app.n8n.cloud"
BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
QUESTIONS_1000 = os.path.join(BASE_DIR, "rag-1000-test-questions.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "diagnostic-validation-results.json")

RAG_ENDPOINTS = {
    "standard": f"{N8N_HOST}/webhook/rag-multi-index-v3",
    "graph": f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9"
}

# 10 standard questions (squad_v2 — simple factual, via benchmark tester)
STANDARD_QUESTIONS = [
    {"question": "In what country is Normandy located?", "expected": "France"},
    {"question": "When were the Normans in Normandy?", "expected": "10th and 11th centuries"},
    {"question": "From which countries did the Norsesemen come?", "expected": "Denmark, Iceland and Norway"},
    {"question": "Who was the Norse leader?", "expected": "Rollo"},
    {"question": "What century did the Normans first gain their pointion in France?", "expected": "10th century"},
    {"question": "What did the Normans gain in France?", "expected": "Normandy"},
    {"question": "Who painted the Mona Lisa?", "expected": "Leonardo da Vinci"},
    {"question": "What is the largest planet in our solar system?", "expected": "Jupiter"},
    {"question": "Who wrote Romeo and Juliet?", "expected": "William Shakespeare"},
    {"question": "What is the chemical symbol for water?", "expected": "H2O"},
]


def call_rag(endpoint, question, tenant_id="benchmark", timeout=60):
    """Call a RAG endpoint and return the response."""
    url = endpoint
    body = json.dumps({
        "query": question,
        "tenant_id": tenant_id,
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True
    }).encode()
    headers = {"Content-Type": "application/json"}

    for attempt in range(4):
        try:
            req = request.Request(url, data=body, headers=headers, method="POST")
            start = time.time()
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                latency = int((time.time() - start) * 1000)
                if raw and raw.strip():
                    data = json.loads(raw)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    return {"data": data, "latency_ms": latency, "error": None}
                return {"data": None, "latency_ms": latency, "error": "Empty response"}
        except error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()[:300]
            except:
                pass
            if (e.code == 403 or e.code >= 500) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"data": None, "latency_ms": 0, "error": f"HTTP {e.code}: {err_body}"}
        except Exception as e:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"data": None, "latency_ms": 0, "error": str(e)}

    return {"data": None, "latency_ms": 0, "error": "Max retries exceeded"}


def extract_answer(data):
    """Extract the answer string from RAG response."""
    if not data:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        # Standard RAG: { response: "answer string" }
        if isinstance(data.get("response"), str):
            return data["response"]
        # Quantitative: { answer: "...", interpretation: "..." }
        if isinstance(data.get("answer"), str):
            return data["answer"]
        if isinstance(data.get("interpretation"), str):
            return data["interpretation"]
        # Graph RAG (legacy): { response: { budgeted_context: ... } }
        if isinstance(data.get("response"), dict):
            inner = data["response"]
            if isinstance(inner.get("response"), str):
                return inner["response"]
            # Worst case: concatenate
            ctx = inner.get("budgeted_context", inner)
            docs = ctx.get("reranked", []) or ctx.get("graph", []) or ctx.get("vector", [])
            if docs:
                return " | ".join(
                    [d.get("content", d.get("text", d.get("document", "")))
                     for d in docs[:3] if isinstance(d, dict)]
                )
    return str(data)[:500]


def compute_f1(predicted, expected):
    """Token-level F1 score."""
    if not predicted or not expected:
        return 0.0
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


def detect_french(text):
    """Simple heuristic to detect if text is primarily in French."""
    if not text:
        return False
    french_words = {"est", "les", "des", "une", "dans", "pas", "pour", "qui", "sur",
                    "sont", "avec", "cette", "mais", "aussi", "peut", "fait", "bien",
                    "aucun", "trouvé", "réponse", "pertinent", "contexte"}
    words = set(text.lower().split())
    matches = words & french_words
    return len(matches) >= 3


def detect_community_summary(text):
    """Detect if answer contains raw community summary patterns."""
    if not text:
        return False
    patterns = [
        r'\|.*\|',  # pipe-separated fragments
        r'Community \d+',  # community IDs
        r'Machine learning.*neural network',  # irrelevant ML content
        r'\{.*"content".*"source".*\}',  # raw JSON objects
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    # Check for very long responses with no punctuation (dump patterns)
    sentences = text.split('.')
    if len(sentences) <= 1 and len(text) > 200:
        return True
    return False


if __name__ == "__main__":
    print("=" * 70)
    print("  DIAGNOSTIC VALIDATION TEST — Post-Fix Verification")
    print("=" * 70)
    print(f"  Date: {datetime.now().isoformat()}")
    print(f"  Testing: 10 Standard + 10 Graph + 10 Quantitative = 30 questions")
    print("=" * 70)

    # Load 1000 specialized questions for Graph + Quantitative
    with open(QUESTIONS_1000) as f:
        q1000 = json.load(f)["questions"]

    graph_questions = [q for q in q1000 if q["rag_target"] == "graph"][:10]
    quant_questions = [q for q in q1000 if q["rag_target"] == "quantitative"][:10]

    all_results = []
    overall_start = time.time()

    # ─── TEST 1: Standard RAG ─────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"  TEST 1: STANDARD RAG (10 squad_v2 questions)")
    print(f"{'─'*50}")

    for i, q in enumerate(STANDARD_QUESTIONS):
        resp = call_rag(RAG_ENDPOINTS["standard"], q["question"])
        answer = extract_answer(resp["data"])
        f1 = compute_f1(answer, q["expected"])
        is_french = detect_french(answer)
        is_garbage = detect_community_summary(answer)

        result = {
            "rag_type": "standard",
            "question": q["question"],
            "expected": q["expected"],
            "answer": answer[:300],
            "f1": round(f1, 4),
            "latency_ms": resp["latency_ms"],
            "error": resp["error"],
            "is_french": is_french,
            "is_garbage": is_garbage,
            "has_answer": bool(answer and len(answer) > 2),
        }
        all_results.append(result)

        status = "OK" if result["has_answer"] and not is_french and not is_garbage else "PROBLEM"
        if resp["error"]:
            status = "ERROR"
        print(f"  [{i+1}/10] {status} | F1={f1:.2f} | {resp['latency_ms']}ms "
              f"| {'FR!' if is_french else 'EN'} "
              f"| Q: {q['question'][:50]}...")
        if answer:
            print(f"           A: {answer[:100]}...")
        time.sleep(1)

    # ─── TEST 2: Graph RAG ────────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"  TEST 2: GRAPH RAG (10 musique multi-hop questions)")
    print(f"{'─'*50}")

    for i, q in enumerate(graph_questions):
        resp = call_rag(RAG_ENDPOINTS["graph"], q["question"])
        answer = extract_answer(resp["data"])
        f1 = compute_f1(answer, str(q.get("expected_answer", "")))
        is_french = detect_french(answer)
        is_garbage = detect_community_summary(answer)

        result = {
            "rag_type": "graph",
            "dataset": q.get("dataset_name", "unknown"),
            "question": q["question"],
            "expected": str(q.get("expected_answer", ""))[:200],
            "answer": answer[:300],
            "f1": round(f1, 4),
            "latency_ms": resp["latency_ms"],
            "error": resp["error"],
            "is_french": is_french,
            "is_garbage": is_garbage,
            "has_answer": bool(answer and len(answer) > 2),
        }
        all_results.append(result)

        status = "OK" if result["has_answer"] and not is_garbage else "PROBLEM"
        if resp["error"]:
            status = "ERROR"
        print(f"  [{i+1}/10] {status} | F1={f1:.2f} | {resp['latency_ms']}ms "
              f"| {'FR!' if is_french else 'EN'} | {'GARBAGE' if is_garbage else 'clean'}"
              f"\n           Q: {q['question'][:80]}..."
              f"\n           Expected: {str(q.get('expected_answer',''))[:60]}")
        if answer:
            print(f"           Got: {answer[:120]}...")
        time.sleep(1)

    # ─── TEST 3: Quantitative RAG ─────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"  TEST 3: QUANTITATIVE RAG (10 finqa/tatqa financial questions)")
    print(f"{'─'*50}")

    for i, q in enumerate(quant_questions):
        resp = call_rag(RAG_ENDPOINTS["quantitative"], q["question"])
        answer = extract_answer(resp["data"])
        f1 = compute_f1(answer, str(q.get("expected_answer", "")))
        is_french = detect_french(answer)

        result = {
            "rag_type": "quantitative",
            "dataset": q.get("dataset_name", "unknown"),
            "question": q["question"],
            "expected": str(q.get("expected_answer", ""))[:200],
            "answer": answer[:300],
            "f1": round(f1, 4),
            "latency_ms": resp["latency_ms"],
            "error": resp["error"],
            "is_french": is_french,
            "is_garbage": False,
            "has_answer": bool(answer and len(answer) > 2),
        }
        all_results.append(result)

        status = "OK" if result["has_answer"] else "EMPTY"
        if resp["error"]:
            status = "ERROR"
        print(f"  [{i+1}/10] {status} | F1={f1:.2f} | {resp['latency_ms']}ms "
              f"| {'FR!' if is_french else 'EN'}"
              f"\n           Q: {q['question'][:80]}..."
              f"\n           Expected: {str(q.get('expected_answer',''))[:60]}")
        if answer:
            print(f"           Got: {answer[:120]}...")
        time.sleep(1)

    # ─── SUMMARY ──────────────────────────────────────────────────
    elapsed = time.time() - overall_start
    print(f"\n{'='*70}")
    print(f"  VALIDATION SUMMARY")
    print(f"{'='*70}")

    for rag_type in ["standard", "graph", "quantitative"]:
        rag_results = [r for r in all_results if r["rag_type"] == rag_type]
        has_answer = sum(1 for r in rag_results if r["has_answer"])
        has_error = sum(1 for r in rag_results if r["error"])
        is_french = sum(1 for r in rag_results if r["is_french"])
        is_garbage = sum(1 for r in rag_results if r.get("is_garbage", False))
        f1_scores = [r["f1"] for r in rag_results if r["has_answer"]]
        avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0

        print(f"\n  {rag_type.upper()}:")
        print(f"    Answers:    {has_answer}/10")
        print(f"    Errors:     {has_error}/10")
        print(f"    French:     {is_french}/10 {'⚠ STILL FRENCH' if is_french > 0 else '✓ English'}")
        if rag_type == "graph":
            print(f"    Garbage:    {is_garbage}/10 {'⚠ STILL RAW SUMMARIES' if is_garbage > 0 else '✓ Clean answers'}")
        print(f"    Avg F1:     {avg_f1:.4f}")
        print(f"    F1 > 0.3:   {sum(1 for f in f1_scores if f > 0.3)}/{len(f1_scores)}")

    # Overall verdict
    total_answers = sum(1 for r in all_results if r["has_answer"])
    total_french = sum(1 for r in all_results if r["is_french"])
    total_garbage = sum(1 for r in all_results if r.get("is_garbage", False))
    total_errors = sum(1 for r in all_results if r["error"])
    all_f1 = [r["f1"] for r in all_results if r["has_answer"]]
    overall_f1 = sum(all_f1) / len(all_f1) if all_f1 else 0

    print(f"\n{'─'*50}")
    print(f"  OVERALL VERDICT:")
    print(f"    Answers:  {total_answers}/30")
    print(f"    Errors:   {total_errors}/30")
    print(f"    French:   {total_french}/30")
    print(f"    Garbage:  {total_garbage}/30")
    print(f"    Avg F1:   {overall_f1:.4f}")
    print(f"    Time:     {elapsed:.0f}s")

    if total_answers >= 20 and total_french <= 2 and total_garbage <= 2:
        print(f"\n  ✓ VERDICT: FIXES APPEAR TO WORK — Safe to proceed with batch testing")
    elif total_answers >= 10:
        print(f"\n  ⚠ VERDICT: PARTIAL SUCCESS — Review issues before batch testing")
    else:
        print(f"\n  ✗ VERDICT: FIXES NOT WORKING — Do NOT proceed with batch testing")
    print(f"{'='*70}")

    # Save results
    with open(OUTPUT_FILE, "w") as f:
        json.dump({
            "suite": "Diagnostic Validation — Post-Fix",
            "date": datetime.now().isoformat(),
            "elapsed_seconds": int(elapsed),
            "summary": {
                "total": 30,
                "answers": total_answers,
                "errors": total_errors,
                "french": total_french,
                "garbage": total_garbage,
                "avg_f1": round(overall_f1, 4),
            },
            "results": all_results,
        }, f, indent=2)

    print(f"\n  Results saved to: {OUTPUT_FILE}")
