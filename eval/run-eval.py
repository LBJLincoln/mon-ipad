#!/usr/bin/env python3
"""
COMPREHENSIVE RAG EVALUATION — Dashboard-Connected
====================================================
Unified eval script for all 4 RAG pipelines. Feeds results in real-time
to docs/data.json (GitHub Pages dashboard) and tracks tested question IDs
to prevent re-testing across sessions.

Datasets:
  - datasets/phase-1/graph-quant-50x2.json           → 50 graph + 50 quantitative
  - datasets/phase-1/standard-orch-50x2.json         → 50 standard + 50 orchestrator
  - datasets/phase-2/hf-1000.json                    → 500 graph + 500 quantitative (HF)

Usage:
  python run-eval.py                    # All untested questions
  python run-eval.py --max 10           # Max 10 per pipeline
  python run-eval.py --types graph,quantitative  # Specific types
  python run-eval.py --include-1000     # Include HF-1000 questions
  python run-eval.py --reset            # Re-test everything (ignore dedup)
  python run-eval.py --push             # Git push after completion
"""

import json
import os
import re
import time
import sys
from datetime import datetime
from urllib import request, error
from importlib.machinery import SourceFileLoader

# === CONFIGURATION ===
N8N_HOST = os.environ.get("N8N_HOST", "https://amoret.app.n8n.cloud")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(REPO_ROOT, "datasets")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
DEDUP_FILE = os.path.join(DOCS_DIR, "tested-questions.json")

RAG_ENDPOINTS = {
    "standard":     f"{N8N_HOST}/webhook/rag-multi-index-v3",
    "graph":        f"{N8N_HOST}/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": f"{N8N_HOST}/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": f"{N8N_HOST}/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
}

# Load live-writer module
writer = SourceFileLoader("w", os.path.join(EVAL_DIR, "live-writer.py")).load_module()


# ============================================================
# Dedup: track tested question IDs
# ============================================================

def load_tested_ids():
    """Load set of already-tested question IDs from dedup manifest."""
    if not os.path.exists(DEDUP_FILE):
        return set()
    with open(DEDUP_FILE) as f:
        data = json.load(f)
    ids = set()
    for rag_type, info in data.get("tested", {}).items():
        for qid in info.get("ids", []):
            ids.add(qid)
    return ids


def save_tested_ids(tested_ids_by_type):
    """Save updated dedup manifest."""
    data = {
        "description": "Tracks all tested question IDs to prevent re-testing across sessions",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total_tested": sum(len(ids) for ids in tested_ids_by_type.values()),
        "tested": {}
    }
    for rag_type, ids in tested_ids_by_type.items():
        data["tested"][rag_type] = {
            "count": len(ids),
            "ids": sorted(ids)
        }
    tmp = DEDUP_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, DEDUP_FILE)


def load_tested_ids_by_type():
    """Load tested IDs grouped by rag_type."""
    if not os.path.exists(DEDUP_FILE):
        return {"standard": set(), "graph": set(), "quantitative": set(), "orchestrator": set()}
    with open(DEDUP_FILE) as f:
        data = json.load(f)
    result = {}
    for rag_type in ["standard", "graph", "quantitative", "orchestrator"]:
        result[rag_type] = set(data.get("tested", {}).get(rag_type, {}).get("ids", []))
    return result


# ============================================================
# Load questions from all dataset files
# ============================================================

def load_questions(include_1000=False, dataset=None):
    """Load questions from dataset files.

    Args:
        include_1000: Legacy flag — include Phase 2 HF-1000 questions alongside Phase 1.
        dataset: Explicit dataset selector:
            - None or "phase-1": Phase 1 only (200 questions)
            - "phase-2": Phase 2 only (1,000 HF questions)
            - "all": Phase 1 + Phase 2 (1,200 questions)
    """
    questions = {"standard": [], "graph": [], "quantitative": [], "orchestrator": []}

    # Determine which datasets to load
    load_phase1 = True
    load_phase2 = include_1000
    if dataset == "phase-2":
        load_phase1 = False
        load_phase2 = True
    elif dataset == "all":
        load_phase2 = True

    # Phase 1: Standard + Orchestrator
    if load_phase1:
        std_orch_path = os.path.join(DATASETS_DIR, "phase-1", "standard-orch-50x2.json")
        with open(std_orch_path) as f:
            raw = json.load(f)
        std_orch_data = raw.get("questions", raw) if isinstance(raw, dict) else raw
        for q in std_orch_data:
            if not isinstance(q, dict):
                continue
            target = q.get("rag_target", "")
            if target in ("standard", "orchestrator"):
                questions[target].append({
                    "id": q["id"],
                    "question": q["question"],
                    "expected": q["expected_answer"],
                    "category": q.get("category", ""),
                    "dataset_name": q.get("dataset_name", "phase-1"),
                    "phase": 1,
                })

    # Phase 1: Graph + Quantitative
    if load_phase1:
        gq_path = os.path.join(DATASETS_DIR, "phase-1", "graph-quant-50x2.json")
        with open(gq_path) as f:
            raw2 = json.load(f)
        gq_data = raw2.get("questions", raw2) if isinstance(raw2, dict) else raw2
        for q in gq_data:
            if not isinstance(q, dict):
                continue
            target = q.get("rag_target", "")
            if target in ("graph", "quantitative"):
                questions[target].append({
                    "id": q["id"],
                    "question": q["question"],
                    "expected": q["expected_answer"],
                    "category": q.get("category", ""),
                    "dataset_name": q.get("dataset_name", "phase-1"),
                    "phase": 1,
                })

    # Phase 2: HuggingFace datasets (500 graph + 500 quantitative)
    if load_phase2:
        hf_path = os.path.join(DATASETS_DIR, "phase-2", "hf-1000.json")
        if os.path.exists(hf_path):
            with open(hf_path) as f:
                raw3 = json.load(f)
            hf_data = raw3.get("questions", raw3) if isinstance(raw3, dict) else raw3
            for q in hf_data:
                if not isinstance(q, dict):
                    continue
                target = q.get("rag_target", "")
                if target in ("graph", "quantitative"):
                    expected = q.get("expected_answer", "")
                    if not expected:
                        continue  # Skip questions with empty expected answers
                    questions[target].append({
                        "id": q["id"],
                        "question": q["question"],
                        "expected": expected,
                        "category": q.get("category", ""),
                        "dataset_name": q.get("dataset_name", ""),
                        "phase": 2,
                    })

    phase_label = dataset or ("phase-1+2" if include_1000 else "phase-1")
    for t in questions:
        if questions[t]:
            print(f"  {t}: {len(questions[t])} questions loaded ({phase_label})")
    return questions


# ============================================================
# HTTP caller + answer extraction + scoring
# ============================================================

def call_rag(endpoint, question, tenant_id="benchmark", timeout=60):
    """Call a RAG endpoint with retry logic. Returns enriched response with raw data."""
    input_payload = {
        "query": question,
        "tenant_id": tenant_id,
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True
    }
    body = json.dumps(input_payload).encode()
    headers = {"Content-Type": "application/json"}

    for attempt in range(4):
        try:
            req = request.Request(endpoint, data=body, headers=headers, method="POST")
            start = time.time()
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                latency = int((time.time() - start) * 1000)
                http_status = resp.status
                if raw and raw.strip():
                    data = json.loads(raw)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    # Check if response has actual content (not just metadata)
                    answer_found = False
                    if isinstance(data, dict):
                        for key in ["response", "answer", "result", "final_response", "interpretation"]:
                            if key in data and data[key] and str(data[key]).strip():
                                answer_found = True
                                break
                    if not answer_found and attempt < 2:
                        # Retry once on empty-content response
                        time.sleep(2)
                        continue
                    return {"data": data, "latency_ms": latency, "error": None,
                            "http_status": http_status, "response_size": len(raw),
                            "input_payload": input_payload, "raw_response": data,
                            "attempts": attempt + 1}
                if attempt < 2:
                    # Retry once on truly empty response
                    time.sleep(2)
                    continue
                return {"data": None, "latency_ms": latency,
                        "error": "Empty response (HTTP 200)",
                        "http_status": http_status, "response_size": 0,
                        "input_payload": input_payload, "raw_response": None,
                        "attempts": attempt + 1}
        except error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()[:300]
            except:
                pass
            if (e.code == 403 or e.code >= 500) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"data": None, "latency_ms": 0,
                    "error": f"HTTP {e.code}: {err_body}",
                    "http_status": e.code, "response_size": 0,
                    "input_payload": input_payload, "raw_response": None,
                    "attempts": attempt + 1}
        except Exception as e:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"data": None, "latency_ms": 0, "error": str(e),
                    "http_status": None, "response_size": 0,
                    "input_payload": input_payload, "raw_response": None,
                    "attempts": attempt + 1}

    return {"data": None, "latency_ms": 0, "error": "Max retries exceeded",
            "http_status": None, "response_size": 0,
            "input_payload": input_payload, "raw_response": None,
            "attempts": 4}


def extract_answer(data):
    """Extract the answer string from different RAG response formats."""
    if not data:
        return ""
    if isinstance(data, str):
        return data

    # Priority 1: Direct answer fields
    for key in ["response", "answer", "result", "final_response", "interpretation"]:
        if key in data and data[key]:
            val = data[key]
            if isinstance(val, str) and len(val.strip()) > 0:
                return val.strip()

    # Priority 2: Nested response formats
    if "success" in data and "response" in data:
        resp = data["response"]
        if isinstance(resp, str):
            return resp.strip()

    # Priority 3: Orchestrator-specific nested response
    if "task_results" in data and isinstance(data["task_results"], list):
        for tr in data["task_results"]:
            if isinstance(tr, dict):
                for key in ["response", "answer", "result"]:
                    if key in tr and tr[key]:
                        return str(tr[key]).strip()

    # Priority 4: LLM-style response format
    if "choices" in data:
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            pass

    # Priority 5: Any non-empty string value (heuristic)
    for key, val in data.items():
        if key not in ("query", "tenant_id", "benchmark_mode", "top_k", "include_sources",
                        "trace_id", "confidence", "sources", "metadata", "perf"):
            if isinstance(val, str) and len(val.strip()) > 20:
                return val.strip()

    return str(data)[:500]


def extract_pipeline_details(data, rag_type):
    """Extract pipeline-specific execution details from the raw response."""
    if not data or not isinstance(data, dict):
        return {}
    details = {}
    if rag_type == "graph":
        details["entities_extracted"] = data.get("entities", [])
        details["neo4j_paths_found"] = len(data.get("sources", []))
        details["traversal_depth"] = data.get("traversal_depth_used", 0)
        details["community_summaries_matched"] = data.get("community_matches", 0)
        if "source_counts" in data:
            details["source_counts"] = data["source_counts"]
    elif rag_type == "standard":
        details["topK"] = data.get("topK", data.get("top_k"))
        details["pinecone_results_count"] = len(data.get("sources", []))
        details["embedding_model"] = data.get("embedding_model")
        details["complexity"] = data.get("complexity")
    elif rag_type == "quantitative":
        details["sql_generated"] = data.get("sql_executed", "")
        details["sql_validation_status"] = data.get("metadata", {}).get("validation_status")
        details["result_count"] = data.get("result_count", 0)
        details["null_aggregation"] = data.get("null_aggregation", False)
        details["raw_results_preview"] = str(data.get("raw_results", []))[:200]
    elif rag_type == "orchestrator":
        details["sub_pipelines_invoked"] = data.get("engines_used", [])
        details["routing_decision"] = data.get("routing", data.get("intent"))
        details["confidence"] = data.get("confidence")
        if "perf" in data:
            details["perf"] = data["perf"]
    return details


def normalize_text(text):
    """Normalize text for comparison: lowercase, remove articles/punctuation."""
    text = text.lower().strip()
    # Remove common prefixes that don't affect correctness
    for prefix in ["the answer is ", "the answer is: ", "based on the context, ",
                    "according to the data, ", "based on the provided context, "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
    # Remove trailing periods and whitespace
    text = text.rstrip('. ')
    return text


def compute_f1(prediction, reference):
    """Compute token-level F1 score with normalization."""
    pred_norm = normalize_text(prediction)
    ref_norm = normalize_text(reference)
    pred_tokens = set(re.findall(r'\w+', pred_norm))
    ref_tokens = set(re.findall(r'\w+', ref_norm))
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
    entities = re.split(r'[,;|]', expected)
    matched = 0
    total = 0
    for entity in entities:
        entity = entity.strip()
        if len(entity) < 2:
            continue
        total += 1
        words = [w for w in entity.split() if len(w) > 2]
        if any(w.lower() in pred_lower for w in words):
            matched += 1
    if total == 0:
        return 0, 0
    return matched, total


def normalize_number(text):
    """Extract and normalize a numeric value from text, handling currency and units."""
    text = text.strip().lower()
    # Handle "X percent" or "X %" patterns
    text = text.replace(" percent", "%").replace(" per cent", "%")
    # Handle currency symbols
    text = text.replace("$", "").replace("€", "").replace("£", "")
    # Handle magnitude words
    multipliers = {"billion": 1e9, "million": 1e6, "thousand": 1e3, "k": 1e3, "m": 1e6, "b": 1e9}
    for word, mult in multipliers.items():
        if word in text:
            nums = re.findall(r'[\d,]+\.?\d*', text.replace(',', ''))
            if nums:
                try:
                    return float(nums[0]) * mult
                except ValueError:
                    pass
    return None


def numeric_match(prediction, expected):
    """Check if numeric values match (within 5% tolerance).
    Handles percentages, currency, and magnitude words."""
    pred_nums = re.findall(r'[\d,]+\.?\d*', prediction.replace(',', ''))
    exp_nums = re.findall(r'[\d,]+\.?\d*', expected.replace(',', ''))
    if not exp_nums:
        return False, None, None

    # Also try magnitude-aware matching
    exp_normalized = normalize_number(expected)

    for exp_str in exp_nums:
        try:
            exp_val = float(exp_str)
        except ValueError:
            continue
        for pred_str in pred_nums:
            try:
                pred_val = float(pred_str)
            except ValueError:
                continue
            if exp_val == 0:
                if pred_val == 0:
                    return True, pred_val, exp_val
            elif abs(pred_val - exp_val) / abs(exp_val) < 0.05:
                return True, pred_val, exp_val

    # Try magnitude-aware matching (e.g., "$56.7 million" vs "56700000")
    if exp_normalized is not None:
        for pred_str in pred_nums:
            try:
                pred_val = float(pred_str)
            except ValueError:
                continue
            if exp_normalized != 0 and abs(pred_val - exp_normalized) / abs(exp_normalized) < 0.05:
                return True, pred_val, exp_normalized
        pred_normalized = normalize_number(prediction)
        if pred_normalized is not None and exp_normalized != 0:
            if abs(pred_normalized - exp_normalized) / abs(exp_normalized) < 0.05:
                return True, pred_normalized, exp_normalized

    return False, None, None


def exact_match(prediction, expected):
    """Check if the expected answer is contained exactly (case-insensitive) in the prediction."""
    pred_norm = normalize_text(prediction)
    exp_norm = normalize_text(expected)
    if not exp_norm:
        return False
    # Direct containment check
    if exp_norm in pred_norm:
        return True
    # Check if all words of expected appear in prediction (for short expected answers)
    exp_words = exp_norm.split()
    if len(exp_words) <= 3:
        return all(w in pred_norm for w in exp_words)
    return False


def evaluate_answer(prediction, expected):
    """Multi-strategy answer evaluation with improved scoring."""
    if not prediction or prediction.strip() == "":
        return {"correct": False, "method": "NO_ANSWER", "f1": 0.0, "detail": "Empty prediction"}

    f1 = compute_f1(prediction, expected)

    # Strategy 1: Exact containment (highest confidence)
    if exact_match(prediction, expected):
        return {"correct": True, "method": "EXACT_MATCH", "f1": f1,
                "detail": f"Expected found in answer"}

    # Strategy 2: Numeric match (5% tolerance)
    num_ok, pred_num, exp_num = numeric_match(prediction, expected)
    if num_ok:
        return {"correct": True, "method": "NUMERIC_MATCH", "f1": f1,
                "detail": f"{pred_num}~={exp_num}"}

    # Strategy 3: Entity match (at least 50% of expected entities found)
    matched, total = entity_match(prediction, expected)
    if total > 0 and matched >= max(1, total * 0.5):
        return {"correct": True, "method": "ENTITY_MATCH", "f1": f1,
                "detail": f"{matched}/{total}"}

    # Strategy 4: Percentage match (handle "6%" matching "6.0%", "6 percent", etc.)
    if "%" in expected or "percent" in expected.lower():
        exp_pct = re.findall(r'([\d.]+)\s*%', expected)
        pred_pct = re.findall(r'([\d.]+)\s*%', prediction)
        if not pred_pct:
            pred_pct = re.findall(r'([\d.]+)\s*percent', prediction.lower())
        if exp_pct and pred_pct:
            try:
                for ep in exp_pct:
                    for pp in pred_pct:
                        if abs(float(ep) - float(pp)) < 0.5:  # within 0.5 percentage points
                            return {"correct": True, "method": "PERCENTAGE_MATCH", "f1": f1,
                                    "detail": f"{pp}%~={ep}%"}
            except ValueError:
                pass

    # Strategy 5: F1 threshold (lower threshold for short expected answers)
    f1_threshold = 0.4 if len(expected.split()) <= 3 else 0.5
    if f1 >= f1_threshold:
        return {"correct": True, "method": "F1_THRESHOLD", "f1": f1,
                "detail": f"F1={f1:.3f} (threshold={f1_threshold})"}

    return {"correct": False, "method": "PARTIAL", "f1": f1,
            "detail": f"F1={f1:.3f}"}


# ============================================================
# Main evaluation loop
# ============================================================

def run_eval(questions_by_type, tested_ids_by_type, max_per_type=None):
    """Run evaluation, feeding each result to the dashboard in real-time."""
    totals = {"tested": 0, "correct": 0, "errors": 0}

    for rag_type in ["standard", "graph", "quantitative", "orchestrator"]:
        all_qs = questions_by_type.get(rag_type, [])
        already_tested = tested_ids_by_type.get(rag_type, set())

        # Filter out already-tested questions
        untested = [q for q in all_qs if q["id"] not in already_tested]
        if max_per_type and len(untested) > max_per_type:
            untested = untested[:max_per_type]

        if not untested:
            print(f"\n  --- {rag_type.upper()} RAG --- SKIPPED (all {len(all_qs)} already tested)")
            continue

        endpoint = RAG_ENDPOINTS[rag_type]
        print(f"\n  --- {rag_type.upper()} RAG --- {len(untested)} questions "
              f"(skipping {len(already_tested)} already tested)")

        for i, q in enumerate(untested):
            qid = q["id"]
            # Orchestrator needs more time due to sub-workflow chaining
            rag_timeout = 90 if rag_type == "orchestrator" else 60
            resp = call_rag(endpoint, q["question"], timeout=rag_timeout)

            if resp["error"]:
                answer = ""
                evaluation = {"correct": False, "method": "NO_ANSWER", "f1": 0.0,
                              "detail": resp["error"]}
                pipeline_details = {}
            else:
                answer = extract_answer(resp["data"])
                evaluation = evaluate_answer(answer, q["expected"])
                pipeline_details = extract_pipeline_details(resp["data"], rag_type)

            is_correct = evaluation.get("correct", False)
            f1_val = evaluation.get("f1", compute_f1(answer, q["expected"]))
            has_error = resp["error"] is not None

            # Print result
            symbol = "[+]" if is_correct else "[-]"
            truncated_answer = (answer[:100] + "...") if len(answer) > 100 else answer
            print(f"  [{i+1}/{len(untested)}] {symbol} {qid} | F1={f1_val:.3f} | "
                  f"{resp['latency_ms']}ms | {evaluation['method']}: {evaluation.get('detail', '')}")
            if resp["error"]:
                print(f"         ERR: {resp['error'][:150]}")
            else:
                print(f"         A: {truncated_answer}")
            print(f"         E: {q['expected'][:150]}")

            # Record to dashboard (live-results-writer)
            writer.record_question(
                rag_type=rag_type,
                question_id=qid,
                question_text=q["question"],
                correct=is_correct,
                f1=f1_val,
                latency_ms=resp["latency_ms"],
                error=resp["error"],
                cost_usd=0,
                expected=q["expected"],
                answer=answer,
                match_type=evaluation.get("method", "")
            )

            # Record detailed execution trace (for logs + error files)
            writer.record_execution(
                rag_type=rag_type,
                question_id=qid,
                question_text=q["question"],
                expected=q["expected"],
                input_payload=resp.get("input_payload"),
                raw_response=resp.get("raw_response"),
                extracted_answer=answer,
                correct=is_correct,
                f1=f1_val,
                match_type=evaluation.get("method", ""),
                latency_ms=resp["latency_ms"],
                http_status=resp.get("http_status"),
                response_size=resp.get("response_size", 0),
                error=resp["error"],
                cost_usd=0,
                pipeline_details=pipeline_details
            )

            # Track as tested
            tested_ids_by_type.setdefault(rag_type, set()).add(qid)

            totals["tested"] += 1
            if is_correct:
                totals["correct"] += 1
            if has_error:
                totals["errors"] += 1

        # Save dedup after each pipeline type completes
        save_tested_ids({k: v for k, v in tested_ids_by_type.items()})

    return totals


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Comprehensive RAG Evaluation")
    parser.add_argument("--max", type=int, default=None,
                        help="Max questions per pipeline type")
    parser.add_argument("--types", type=str, default="standard,graph,quantitative,orchestrator",
                        help="Comma-separated pipeline types to test")
    parser.add_argument("--dataset", type=str, default=None,
                        choices=["phase-1", "phase-2", "all"],
                        help="Dataset to evaluate: phase-1 (200q), phase-2 (1000q HF), all (1200q)")
    parser.add_argument("--include-1000", action="store_true",
                        help="[Legacy] Include HF-1000 questions (use --dataset all instead)")
    parser.add_argument("--reset", action="store_true",
                        help="Ignore dedup, re-test all questions")
    parser.add_argument("--push", action="store_true",
                        help="Git push docs/data.json after completion")
    parser.add_argument("--label", type=str, default="",
                        help="Human-readable label for this iteration")
    parser.add_argument("--description", type=str, default="",
                        help="Description of what changed before this eval")
    args = parser.parse_args()

    dataset_label = args.dataset or ("phase-1+2" if args.include_1000 else "phase-1")

    start_time = datetime.now()
    print("=" * 70)
    print("  COMPREHENSIVE RAG EVALUATION — Dashboard-Connected")
    print(f"  Started: {start_time.isoformat()}")
    print(f"  Dataset: {dataset_label}")
    print(f"  Types: {args.types}")
    print(f"  Reset dedup: {args.reset}")
    print("=" * 70)

    # Initialize dashboard with iteration metadata
    writer.init(
        status="running",
        label=args.label or f"Eval {dataset_label} {args.types}",
        description=args.description or f"Dataset: {dataset_label}, Types: {args.types}, Max: {args.max}, Reset: {args.reset}",
    )

    # Load questions
    print("\n  Loading questions...")
    questions = load_questions(include_1000=args.include_1000, dataset=args.dataset)

    # Filter to requested types
    requested_types = set(args.types.split(","))
    for t in list(questions.keys()):
        if t not in requested_types:
            questions[t] = []

    # Load dedup state
    if args.reset:
        tested_ids = {t: set() for t in ["standard", "graph", "quantitative", "orchestrator"]}
        print("  Dedup RESET — all questions will be re-tested")
    else:
        tested_ids = load_tested_ids_by_type()
        total_already = sum(len(v) for v in tested_ids.values())
        print(f"  Dedup: {total_already} questions already tested (will be skipped)")

    # Snapshot databases before eval
    print("\n  Taking pre-evaluation DB snapshot...")
    try:
        writer.snapshot_databases(trigger="pre-eval")
    except Exception as e:
        print(f"  DB snapshot failed (non-fatal): {e}")

    # Run evaluation
    totals = run_eval(questions, tested_ids, max_per_type=args.max)

    # Snapshot databases after eval
    print("\n  Taking post-evaluation DB snapshot...")
    try:
        writer.snapshot_databases(trigger="post-eval")
    except Exception as e:
        print(f"  DB snapshot failed (non-fatal): {e}")

    # Finish
    elapsed = int((datetime.now() - start_time).total_seconds())
    print(f"\n{'='*70}")
    print("  EVALUATION COMPLETE")
    print(f"{'='*70}")
    print(f"  Tested:  {totals['tested']}")
    print(f"  Correct: {totals['correct']}")
    print(f"  Errors:  {totals['errors']}")
    print(f"  Elapsed: {elapsed}s ({elapsed // 60}m)")

    if totals["tested"] > 0:
        writer.finish(event="eval_complete")
        print(f"  Dashboard updated: docs/data.json")

    if args.push:
        print("  Pushing to GitHub (data + logs)...")
        writer.git_push(f"eval: {totals['tested']}q tested, "
                        f"{totals['correct']} correct ({elapsed}s)")

    # Final dedup save
    save_tested_ids(tested_ids)
    final_total = sum(len(v) for v in tested_ids.values())
    print(f"  Dedup manifest: {final_total} total tested IDs saved")


if __name__ == "__main__":
    main()
