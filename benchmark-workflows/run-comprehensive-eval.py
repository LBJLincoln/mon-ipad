#!/usr/bin/env python3
"""
COMPREHENSIVE RAG EVALUATION — Multi-Phase
============================================
Tests all 4 RAG pipelines with questions that MATCH the actual seeded datasets:

- Standard RAG:     Uses benchmark-standard-orchestrator-questions.json (std-01..std-50)
                    → Pinecone vectors from squad_v2, triviaqa, pubmedqa, etc.
- Graph RAG:        Uses benchmark-50x2-questions.json (graph-01..graph-50)
                    → Neo4j entities: Marie Curie, Einstein, Turing, etc.
- Quantitative RAG: Uses benchmark-50x2-questions.json (quant-01..quant-50)
                    → Supabase financials: TechVision, GreenEnergy, HealthPlus
- Orchestrator RAG: Uses benchmark-standard-orchestrator-questions.json (orch-01..orch-50)
                    → Routes to correct sub-workflow (standard/graph/quantitative)

Phase 1: Quick test — 5 questions per type
Phase 2: Full test — all questions (if Phase 1 shows >50% on a type)
"""

import json
import os
import re
import time
import sys
from datetime import datetime
from urllib import request, error

# === CONFIGURATION ===
N8N_HOST = os.environ.get("N8N_HOST", "https://amoret.app.n8n.cloud")
BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
OUTPUT_FILE = os.path.join(BASE_DIR, "comprehensive-rag-evaluation-results.json")

RAG_ENDPOINTS = {
    "standard":     f"{N8N_HOST}/webhook/rag-multi-index-v3",
    "graph":        f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": f"{N8N_HOST}/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
}

# === LOAD QUESTIONS FROM CORRECT DATASETS ===
def load_questions():
    """Load questions from the correct dataset files."""
    questions = {"standard": [], "graph": [], "quantitative": [], "orchestrator": []}

    # Standard + Orchestrator from benchmark-standard-orchestrator-questions.json
    std_orch_path = os.path.join(BASE_DIR, "benchmark-standard-orchestrator-questions.json")
    with open(std_orch_path) as f:
        std_orch_data = json.load(f)
    for q in std_orch_data:
        target = q.get("rag_target", "")
        if target == "standard":
            questions["standard"].append({
                "id": q["id"],
                "question": q["question"],
                "expected": q["expected_answer"],
                "category": q.get("category", "")
            })
        elif target == "orchestrator":
            questions["orchestrator"].append({
                "id": q["id"],
                "question": q["question"],
                "expected": q["expected_answer"],
                "category": q.get("category", ""),
                "expected_routing": q.get("expected_routing", [])
            })

    # Graph + Quantitative from benchmark-50x2-questions.json
    gq_path = os.path.join(BASE_DIR, "benchmark-50x2-questions.json")
    with open(gq_path) as f:
        gq_data = json.load(f)
    for q in gq_data:
        target = q.get("rag_target", "")
        if target == "graph":
            questions["graph"].append({
                "id": q["id"],
                "question": q["question"],
                "expected": q["expected_answer"],
                "category": q.get("category", "")
            })
        elif target == "quantitative":
            questions["quantitative"].append({
                "id": q["id"],
                "question": q["question"],
                "expected": q["expected_answer"],
                "category": q.get("category", "")
            })

    print(f"  Loaded: {len(questions['standard'])} standard, {len(questions['graph'])} graph, "
          f"{len(questions['quantitative'])} quantitative, {len(questions['orchestrator'])} orchestrator")
    return questions


# === HTTP CALLER ===
def call_rag(endpoint, question, tenant_id="benchmark", timeout=60):
    """Call a RAG endpoint with retry logic."""
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
            req = request.Request(endpoint, data=body, headers=headers, method="POST")
            start = time.time()
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                latency = int((time.time() - start) * 1000)
                if raw and raw.strip():
                    data = json.loads(raw)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    return {"data": data, "latency_ms": latency, "error": None}
                return {"data": None, "latency_ms": latency, "error": "Empty response (HTTP 200)"}
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


# === ANSWER EXTRACTION ===
def extract_answer(data):
    """Extract the answer string from different RAG response formats."""
    if not data:
        return ""
    if isinstance(data, str):
        return data

    # Standard RAG: response field
    for key in ["response", "answer", "result", "interpretation", "final_response"]:
        if key in data and data[key]:
            val = data[key]
            if isinstance(val, str) and len(val) > 0:
                return val

    # Orchestrator: nested response
    if "success" in data and "response" in data:
        resp = data["response"]
        if isinstance(resp, str):
            return resp

    # Quantitative: interpretation
    if "interpretation" in data:
        return str(data["interpretation"])

    # Fallback: try choices (OpenRouter passthrough)
    if "choices" in data:
        try:
            return data["choices"][0]["message"]["content"]
        except:
            pass

    return str(data)[:500]


# === SCORING ===
def compute_f1(prediction, reference):
    """Compute token-level F1 score."""
    pred_tokens = set(re.findall(r'\w+', prediction.lower()))
    ref_tokens = set(re.findall(r'\w+', reference.lower()))
    if not pred_tokens or not ref_tokens:
        return 0.0
    common = pred_tokens & ref_tokens
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def entity_match(prediction, expected):
    """Check if expected entities appear in the prediction."""
    pred_lower = prediction.lower()
    # Split expected by common separators
    entities = re.split(r'[,;|]', expected)
    matched = 0
    total = 0
    for entity in entities:
        entity = entity.strip()
        if len(entity) < 2:
            continue
        total += 1
        # Check if any significant word from entity appears in prediction
        words = [w for w in entity.split() if len(w) > 2]
        if any(w.lower() in pred_lower for w in words):
            matched += 1

    if total == 0:
        return 0, 0
    return matched, total


def numeric_match(prediction, expected):
    """Check if numeric values match (within 5% tolerance)."""
    # Extract numbers from both
    pred_nums = re.findall(r'[\d,]+\.?\d*', prediction.replace(',', ''))
    exp_nums = re.findall(r'[\d,]+\.?\d*', expected.replace(',', ''))

    if not exp_nums:
        return False, None, None

    for exp_str in exp_nums:
        try:
            exp_val = float(exp_str)
        except:
            continue
        for pred_str in pred_nums:
            try:
                pred_val = float(pred_str)
            except:
                continue
            if exp_val == 0:
                if pred_val == 0:
                    return True, pred_val, exp_val
            elif abs(pred_val - exp_val) / abs(exp_val) < 0.05:
                return True, pred_val, exp_val

    return False, None, None


def evaluate_answer(prediction, expected):
    """Multi-strategy answer evaluation."""
    if not prediction or prediction.strip() == "":
        return {"correct": False, "method": "NO_ANSWER", "detail": "Empty prediction"}

    f1 = compute_f1(prediction, expected)

    # Strategy 1: Numeric match (for quantitative)
    num_ok, pred_num, exp_num = numeric_match(prediction, expected)
    if num_ok:
        return {"correct": True, "method": "NUMERIC_MATCH", "f1": f1,
                "detail": f"{pred_num}~={exp_num}"}

    # Strategy 2: Entity match
    matched, total = entity_match(prediction, expected)
    if total > 0 and matched >= max(1, total * 0.5):
        return {"correct": True, "method": "ENTITY_MATCH", "f1": f1,
                "detail": f"{matched}/{total}"}

    # Strategy 3: F1 threshold
    if f1 >= 0.5:
        return {"correct": True, "method": "F1_THRESHOLD", "f1": f1,
                "detail": f"F1={f1:.3f}"}

    return {"correct": False, "method": "PARTIAL", "f1": f1,
            "detail": f"F1={f1:.3f}"}


# === PHASE RUNNER ===
def run_phase(rag_type, questions, count, phase_label):
    """Run evaluation for one RAG type with a subset of questions."""
    endpoint = RAG_ENDPOINTS[rag_type]
    subset = questions[:count]

    results = []
    correct = 0
    has_answer = 0
    total_f1 = 0.0
    max_f1 = 0.0
    latencies = []

    print(f"  --- {rag_type.upper()} RAG ---")
    for i, q in enumerate(subset):
        qid = q.get("id", f"p-{rag_type}-{i+1}")
        resp = call_rag(endpoint, q["question"])

        if resp["error"]:
            answer = ""
            evaluation = {"correct": False, "method": "NO_ANSWER", "f1": 0.0,
                          "detail": resp["error"]}
        else:
            answer = extract_answer(resp["data"])
            has_answer += 1
            evaluation = evaluate_answer(answer, q["expected"])

        if evaluation.get("correct"):
            correct += 1

        f1_val = evaluation.get("f1", compute_f1(answer, q["expected"]))
        total_f1 += f1_val
        max_f1 = max(max_f1, f1_val)
        latencies.append(resp["latency_ms"])

        # Print result
        symbol = "[+]" if evaluation.get("correct") else "[-]"
        truncated_answer = (answer[:100] + "...") if len(answer) > 100 else answer
        error_prefix = f"ERROR: {resp['error']}\n" if resp["error"] else ""
        print(f"  [{i+1}/{count}] {symbol} {qid} | F1={f1_val:.3f} | "
              f"{resp['latency_ms']}ms | {evaluation['method']}: {evaluation.get('detail', '')}")
        if error_prefix:
            print(f"         {error_prefix.strip()}")
        else:
            print(f"         A: {truncated_answer}")
        print(f"         E: {q['expected']}")

        results.append({
            "id": qid,
            "question": q["question"],
            "expected": q["expected"],
            "actual": answer,
            "correct": evaluation.get("correct", False),
            "method": evaluation.get("method", ""),
            "f1": f1_val,
            "latency_ms": resp["latency_ms"],
            "error": resp.get("error"),
            "category": q.get("category", "")
        })

    # Summary
    avg_f1 = total_f1 / max(1, len(subset))
    sorted_lat = sorted(latencies)
    p95 = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0
    avg_lat = sum(latencies) / max(1, len(latencies))

    summary = {
        "rag_type": rag_type,
        "phase": phase_label,
        "total": len(subset),
        "correct": correct,
        "accuracy": round(correct / max(1, len(subset)) * 100, 1),
        "has_answer": has_answer,
        "errors": len(subset) - has_answer,
        "avg_f1": round(avg_f1, 4),
        "max_f1": round(max_f1, 4),
        "avg_latency_ms": int(avg_lat),
        "p95_latency_ms": p95,
        "results": results
    }

    print(f"  === {rag_type.upper()} RAG — {phase_label} ===")
    print(f"  Total:       {summary['total']}")
    print(f"  Correct:     {summary['correct']} ({summary['accuracy']}%)")
    print(f"  Has answer:  {summary['has_answer']} ({round(has_answer/max(1,len(subset))*100,1)}%)")
    print(f"  Errors:      {summary['errors']}")
    print(f"  Avg F1:      {summary['avg_f1']}")
    print(f"  Max F1:      {summary['max_f1']}")
    print(f"  Avg latency: {summary['avg_latency_ms']}ms")
    print(f"  P95 latency: {summary['p95_latency_ms']}ms")

    return summary


# === MAIN ===
def main():
    start_time = datetime.now()
    print("=" * 70)
    print("  COMPREHENSIVE RAG EVALUATION — Multi-Phase")
    phase_1_count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"  Phase 1 count: {phase_1_count} questions per RAG type")
    print(f"  Started: {start_time.isoformat()}")
    print("=" * 70)

    # Load correct datasets
    questions = load_questions()
    all_results = {}

    # === PHASE 1: Quick Test ===
    print("\n" + "=" * 70)
    print(f"  PHASE 1: Quick Test — {phase_1_count} Questions per RAG Type")
    print("=" * 70)

    for rag_type in ["standard", "graph", "quantitative", "orchestrator"]:
        if not questions[rag_type]:
            print(f"  --- {rag_type.upper()} RAG --- SKIPPED (no questions)")
            continue
        summary = run_phase(rag_type, questions[rag_type], phase_1_count, "Phase 1")
        all_results[f"phase1_{rag_type}"] = summary

    # === PHASE 2: Full Test (for types that passed Phase 1 threshold) ===
    phase2_threshold = 40.0  # Only run full test if Phase 1 accuracy >= 40%
    phase2_types = []
    for rag_type in ["standard", "graph", "quantitative", "orchestrator"]:
        key = f"phase1_{rag_type}"
        if key in all_results and all_results[key]["accuracy"] >= phase2_threshold:
            if len(questions[rag_type]) > phase_1_count:
                phase2_types.append(rag_type)

    if phase2_types:
        print("\n" + "=" * 70)
        print(f"  PHASE 2: Full Test — Types with Phase 1 >= {phase2_threshold}%")
        print(f"  Running: {', '.join(t.upper() for t in phase2_types)}")
        print("=" * 70)

        for rag_type in phase2_types:
            remaining = questions[rag_type][phase_1_count:]
            if remaining:
                summary = run_phase(rag_type, remaining, len(remaining), "Phase 2")
                all_results[f"phase2_{rag_type}"] = summary

    # === SAVE RESULTS ===
    elapsed = int((datetime.now() - start_time).total_seconds())
    output = {
        "timestamp": start_time.isoformat(),
        "elapsed_seconds": elapsed,
        "endpoints": RAG_ENDPOINTS,
        "datasets": {
            "standard": "benchmark-standard-orchestrator-questions.json (std-01..std-50)",
            "graph": "benchmark-50x2-questions.json (graph-01..graph-50) — matches Neo4j entities",
            "quantitative": "benchmark-50x2-questions.json (quant-01..quant-50) — matches Supabase financials",
            "orchestrator": "benchmark-standard-orchestrator-questions.json (orch-01..orch-50)"
        },
        "results": all_results
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {OUTPUT_FILE}")

    # === FINAL SUMMARY ===
    print("\n" + "=" * 70)
    print("  FINAL COMPREHENSIVE SUMMARY")
    print("=" * 70)
    print(f"  Elapsed: {elapsed}s ({elapsed // 60}m)")

    for rag_type in ["standard", "graph", "quantitative", "orchestrator"]:
        p1 = all_results.get(f"phase1_{rag_type}", {})
        p2 = all_results.get(f"phase2_{rag_type}", {})
        if p1:
            total = p1["correct"] + p2.get("correct", 0)
            count = p1["total"] + p2.get("total", 0)
            pct = round(total / max(1, count) * 100, 1)
            print(f"  {rag_type:15s}: {total}/{count} ({pct}%)")


if __name__ == "__main__":
    main()
