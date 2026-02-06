#!/usr/bin/env python3
"""
RAG TEST QUESTION GENERATOR — Graph RAG + Quantitative RAG
============================================================
Generates 1000 test questions from specific datasets (excluding HotPotQA):
  - Graph RAG (500 questions): MuSiQue, 2WikiMultiHopQA, FRAMES
  - Quantitative RAG (500 questions): FinQA, TAT-QA (via RAGBench), ConvFinQA, WikiTableQuestions

Uses VERIFIED public HuggingFace dataset paths (no auth token needed).
Deduplicates against existing benchmark questions (28,053 Q&A pairs).
Pushes to GitHub every 500 questions.
Includes RAG routing analysis to verify questions target the correct RAG type.
"""

import json
import os
import sys
import time
import hashlib
import subprocess
import re
from datetime import datetime
from urllib import request, error, parse

# ─── Configuration ───────────────────────────────────────────────
BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
REPO_DIR = "/home/user/mon-ipad"
GIT_BRANCH = "claude/generate-rag-test-questions-bLLnW"

OUTPUT_FILE = os.path.join(BASE_DIR, "rag-1000-test-questions.json")
ANALYSIS_FILE = os.path.join(BASE_DIR, "rag-1000-test-analysis.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "rag-1000-test-progress.json")

# Existing files to check for deduplication
EXISTING_QA_FILE = os.path.join(BASE_DIR, "benchmark-qa-results-full.json")
EXISTING_TEST_FILE = os.path.join(BASE_DIR, "rag-1000-test-questions.json")
EXISTING_DIAG_FILE = os.path.join(BASE_DIR, "diagnostic-30q-results.json")

# ─── Dataset Definitions (VERIFIED PUBLIC HF PATHS) ─────────────

# Graph RAG: multi-hop reasoning, entity relationships, knowledge graphs
# Excluding HotPotQA as requested
GRAPH_RAG_DATASETS = [
    {
        "name": "musique",
        "hf_path": "bdsaglam/musique",
        "hf_subset": "answerable",
        "category": "multi_hop_qa",
        "split": "validation",
        "target_count": 200,
        "q_field": "question",
        "a_field": "answer",
        "context_field": "paragraphs",
        "rag_target": "graph",
        "description": "Compositional multi-hop reasoning (2-4 hops)",
        "why_graph": "Requires traversing multiple entity relationships across documents",
    },
    {
        "name": "2wikimultihopqa",
        "hf_path": "framolfese/2WikiMultihopQA",
        "hf_subset": "default",
        "category": "multi_hop_qa",
        "split": "validation",
        "target_count": 200,
        "q_field": "question",
        "a_field": "answer",
        "context_field": "context",
        "supporting_field": "supporting_facts",
        "rag_target": "graph",
        "description": "Cross-document reasoning between Wikipedia articles",
        "why_graph": "Needs graph traversal between linked Wikipedia entities",
    },
    {
        "name": "frames",
        "hf_path": "google/frames-benchmark",
        "hf_subset": "default",
        "category": "rag_benchmark",
        "split": "test",
        "target_count": 100,
        "q_field": "Prompt",
        "a_field": "Answer",
        "rag_target": "graph",
        "description": "Google FRAMES multi-hop RAG benchmark",
        "why_graph": "Multi-hop retrieval requiring entity relationship navigation",
    },
]

# Quantitative RAG: SQL, numerical reasoning, financial tables
QUANTITATIVE_RAG_DATASETS = [
    {
        "name": "finqa",
        "hf_path": "dreamerdeo/finqa",
        "hf_subset": "default",
        "category": "domain_finance",
        "split": "test",
        "target_count": 200,
        "q_field": "question",
        "a_field": "answer",
        "context_field": "pre_text",
        "table_field": "table",
        "rag_target": "quantitative",
        "description": "Financial reasoning with tables and calculations",
        "why_quantitative": "Requires numerical extraction from financial tables + computation",
    },
    {
        "name": "tatqa",
        "hf_path": "galileo-ai/ragbench",
        "hf_subset": "tatqa",
        "category": "domain_finance",
        "split": "test",
        "target_count": 150,
        "q_field": "question",
        "a_field": "response",
        "context_field": "documents",
        "rag_target": "quantitative",
        "description": "Hybrid table-and-text QA requiring arithmetic reasoning (via RAGBench)",
        "why_quantitative": "Combines table parsing with text understanding for calculations",
    },
    {
        "name": "convfinqa",
        "hf_path": "MehdiHosseiniMoghadam/ConvFinQA",
        "hf_subset": "default",
        "category": "domain_finance",
        "split": "train",
        "target_count": 100,
        "q_field": "question",
        "a_field": "answer",
        "context_field": "pre_text",
        "table_field": "table",
        "rag_target": "quantitative",
        "description": "Conversational financial QA with multi-turn numerical reasoning",
        "why_quantitative": "Multi-turn financial calculations requiring SQL-like reasoning",
    },
    {
        "name": "wikitablequestions",
        "hf_path": "TableSenseAI/WikiTableQuestions",
        "hf_subset": "default",
        "category": "table_qa",
        "split": "test",
        "target_count": 50,
        "q_field": "utterance",
        "a_field": "target_value",
        "rag_target": "quantitative",
        "description": "Table-based QA requiring SQL-like reasoning",
        "why_quantitative": "Requires structured data queries, aggregation, filtering on tables",
    },
]


# ─── Deduplication ──────────────────────────────────────────────

def load_existing_questions():
    """Load all existing questions from benchmark files for deduplication."""
    existing_hashes = set()
    existing_count = 0

    # 1. Load from benchmark-qa-results-full.json (28,053 questions)
    if os.path.exists(EXISTING_QA_FILE):
        try:
            with open(EXISTING_QA_FILE, "r") as f:
                data = json.load(f)
            results = data.get("results", [])
            for r in results:
                q = r.get("question", "")
                if q:
                    h = hashlib.md5(q.strip().lower().encode()).hexdigest()
                    existing_hashes.add(h)
                    existing_count += 1
        except Exception as e:
            print(f"  [DEDUP] Warning: could not load {EXISTING_QA_FILE}: {e}")

    # 2. Load from existing rag-1000-test-questions.json
    if os.path.exists(EXISTING_TEST_FILE):
        try:
            with open(EXISTING_TEST_FILE, "r") as f:
                data = json.load(f)
            questions = data.get("questions", [])
            for q_entry in questions:
                q = q_entry.get("question", "")
                if q:
                    h = hashlib.md5(q.strip().lower().encode()).hexdigest()
                    existing_hashes.add(h)
                    existing_count += 1
        except Exception as e:
            print(f"  [DEDUP] Warning: could not load {EXISTING_TEST_FILE}: {e}")

    # 3. Load from diagnostic-30q-results.json
    if os.path.exists(EXISTING_DIAG_FILE):
        try:
            with open(EXISTING_DIAG_FILE, "r") as f:
                data = json.load(f)
            for rag_result in data.get("results_per_rag", []):
                for qa in rag_result.get("qa_results", []):
                    q = qa.get("question", "")
                    if q:
                        h = hashlib.md5(q.strip().lower().encode()).hexdigest()
                        existing_hashes.add(h)
                        existing_count += 1
        except Exception as e:
            print(f"  [DEDUP] Warning: could not load {EXISTING_DIAG_FILE}: {e}")

    print(f"  [DEDUP] Loaded {len(existing_hashes)} unique question hashes from {existing_count} existing Q&A pairs")
    return existing_hashes


def is_duplicate(question_text, existing_hashes):
    """Check if a question already exists in the benchmark."""
    h = hashlib.md5(question_text.strip().lower().encode()).hexdigest()
    return h in existing_hashes


# ─── HuggingFace API ────────────────────────────────────────────

def hf_fetch(dataset_path, subset, split, offset=0, length=100):
    """Fetch rows from HuggingFace datasets API."""
    url = (f"https://datasets-server.huggingface.co/rows?"
           f"dataset={parse.quote(dataset_path)}"
           f"&config={parse.quote(subset)}"
           f"&split={split}"
           f"&offset={offset}&length={length}")

    req = request.Request(url)
    for attempt in range(4):
        try:
            with request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except error.HTTPError as e:
            if e.code == 404:
                print(f"    [WARN] 404 for {dataset_path}/{subset}/{split}")
                return None
            if attempt < 3:
                wait = 2 ** (attempt + 1)
                print(f"    [RETRY] HTTP {e.code}, waiting {wait}s (attempt {attempt+1}/4)...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < 3:
                wait = 2 ** (attempt + 1)
                print(f"    [RETRY] {e}, waiting {wait}s (attempt {attempt+1}/4)...")
                time.sleep(wait)
            else:
                raise


def get_field(obj, path, default=None):
    """Deep field access with support for nested structures."""
    if not path or obj is None:
        return default
    parts = path.replace('[', '.').replace(']', '').split('.')
    val = obj
    for p in parts:
        if val is None:
            return default
        if isinstance(val, dict):
            val = val.get(p)
        elif isinstance(val, list):
            try:
                val = val[int(p)]
            except (ValueError, IndexError):
                return default
        else:
            return default
    if isinstance(val, list):
        if len(val) == 0:
            return default
        if isinstance(val[0], str):
            return val[0]
        return json.dumps(val)
    return val if val is not None else default


# ─── Question Extraction ────────────────────────────────────────

def extract_questions(ds_config, existing_hashes, generated_hashes):
    """Fetch and extract questions from a HuggingFace dataset, with deduplication."""
    name = ds_config["name"]
    target = ds_config["target_count"]
    hf_path = ds_config["hf_path"]
    subset = ds_config["hf_subset"]
    split = ds_config["split"]

    print(f"\n  {'='*55}")
    print(f"  FETCHING: {name} (target: {target} questions)")
    print(f"  Source: {hf_path}/{subset}/{split}")
    print(f"  RAG target: {ds_config['rag_target']}")
    print(f"  {'='*55}")

    questions = []
    offset = 0
    page_size = 100
    max_fetch = target * 5  # Fetch more to account for dedup filtering
    duplicates_skipped = 0
    consecutive_failures = 0

    while len(questions) < target and offset < max_fetch:
        fetch_size = min(page_size, (target - len(questions)) * 2)
        if fetch_size < 10:
            fetch_size = 100

        print(f"    Fetching rows {offset}-{offset+fetch_size}...")

        try:
            result = hf_fetch(hf_path, subset, split, offset, fetch_size)
            if result is None:
                print(f"    [ERROR] No data found for {name}")
                break

            rows = result.get("rows", [])
            if not rows:
                print(f"    No more rows at offset {offset}")
                consecutive_failures += 1
                if consecutive_failures > 2:
                    break
                offset += fetch_size
                continue

            consecutive_failures = 0

            for idx, row_data in enumerate(rows):
                if len(questions) >= target:
                    break

                r = row_data.get("row", row_data)
                item_idx = offset + idx

                question_text = get_field(r, ds_config["q_field"], "")
                answer = get_field(r, ds_config["a_field"], "")

                if not question_text or len(str(question_text).strip()) < 5:
                    continue

                question_text = str(question_text).strip()

                # Deduplication check
                q_hash = hashlib.md5(question_text.lower().encode()).hexdigest()
                if q_hash in existing_hashes or q_hash in generated_hashes:
                    duplicates_skipped += 1
                    continue

                # Handle special answer formats
                if isinstance(answer, dict):
                    answer = answer.get("text", answer.get("value", json.dumps(answer)))
                if isinstance(answer, list):
                    if len(answer) > 0:
                        if isinstance(answer[0], str):
                            answer = answer[0]
                        else:
                            answer = json.dumps(answer)
                    else:
                        answer = ""
                answer = str(answer) if answer else ""

                # Get context
                context = None
                if ds_config.get("context_field"):
                    context = get_field(r, ds_config["context_field"])
                    if isinstance(context, (list, dict)):
                        context = json.dumps(context)

                # Get table data for quantitative
                table = None
                if ds_config.get("table_field"):
                    table = get_field(r, ds_config["table_field"])
                    if isinstance(table, (list, dict)):
                        table = json.dumps(table)

                # Get supporting facts for graph
                supporting_facts = None
                if ds_config.get("supporting_field"):
                    sf = get_field(r, ds_config["supporting_field"])
                    if isinstance(sf, (dict, list)):
                        supporting_facts = sf

                # Build metadata
                metadata = {
                    "hf_path": hf_path,
                    "hf_subset": subset,
                    "original_idx": item_idx,
                    "rag_target": ds_config["rag_target"],
                    "why_this_rag": ds_config.get("why_graph") or ds_config.get("why_quantitative", ""),
                    "dataset_description": ds_config["description"],
                }
                if table:
                    metadata["has_table"] = True
                    metadata["table_preview"] = str(table)[:500]
                if supporting_facts:
                    metadata["has_supporting_facts"] = True

                q_entry = {
                    "id": f"{ds_config['rag_target']}-{name}-{len(questions)}",
                    "dataset_name": name,
                    "category": ds_config["category"],
                    "split": split,
                    "item_index": item_idx,
                    "question": question_text[:10000],
                    "expected_answer": answer[:10000],
                    "context": str(context)[:20000] if context else None,
                    "table_data": str(table)[:20000] if table else None,
                    "supporting_facts": supporting_facts,
                    "rag_target": ds_config["rag_target"],
                    "metadata": metadata,
                    "tenant_id": "benchmark",
                }

                questions.append(q_entry)
                generated_hashes.add(q_hash)

            offset += len(rows)
            print(f"    Extracted {len(questions)}/{target} ({duplicates_skipped} duplicates skipped)")

        except Exception as e:
            print(f"    [ERROR] Fetch error at offset {offset}: {e}")
            consecutive_failures += 1
            if consecutive_failures > 3:
                break
            offset += fetch_size
            time.sleep(2)

    print(f"  => {name}: {len(questions)} questions extracted ({duplicates_skipped} duplicates skipped)")
    return questions


# ─── RAG Routing Analysis ───────────────────────────────────────

GRAPH_RAG_PATTERNS = [
    r"\b(who|what|which|where)\b.*\b(and|but|while|whereas)\b.*\b(who|what|which|where)\b",
    r"\bboth\b.*\band\b",
    r"\brelation(ship)?\b",
    r"\bconnect(ed|ion)?\b",
    r"\bcompar(e|ing|ison)\b",
    r"\bolder|younger|taller|shorter\b",
    r"\bborn in the same\b",
    r"\bthe country where\b",
    r"\bthe (city|person|company|director|author) (of|who|that|where)\b.*\b(the|a)\b",
    r"\bwhat is the .* of the .* of\b",
    r"\bwho .* the .* that .* the\b",
    r"\bwhere .* the .* who\b",
    r"\bsame .* as\b",
]

QUANTITATIVE_RAG_PATTERNS = [
    r"\bhow much\b",
    r"\bhow many\b",
    r"\bpercentage\b",
    r"\bratio\b",
    r"\btotal\b",
    r"\baverage|mean|median\b",
    r"\bincreas(e|ed|ing)\b.*\b(by|from|to)\b",
    r"\bdecreas(e|ed|ing)\b.*\b(by|from|to)\b",
    r"\bmargin\b",
    r"\brevenue\b",
    r"\bprofit\b",
    r"\bcalculate\b",
    r"\bgross|net\b",
    r"\b\d+[\.,]\d+\s*(%|percent|million|billion|thousand)\b",
    r"\bchange\b.*\b(from|between|over)\b.*\b(year|quarter|period)\b",
    r"\bwhat (is|was|were) the\b.*\b(value|amount|number|rate|price|cost)\b",
    r"\bmore|less|greater|fewer\b.*\bthan\b",
    r"\bgrowth\b",
    r"\b(sum|count|max|min)\b",
]


def analyze_rag_routing(question_text, expected_rag):
    """Analyze if a question would be correctly routed to the expected RAG type."""
    q_lower = question_text.lower()

    graph_score = sum(1 for p in GRAPH_RAG_PATTERNS if re.search(p, q_lower))
    quant_score = sum(1 for p in QUANTITATIVE_RAG_PATTERNS if re.search(p, q_lower))

    if quant_score > graph_score and quant_score >= 2:
        predicted_rag = "quantitative"
    elif graph_score > quant_score and graph_score >= 2:
        predicted_rag = "graph"
    elif graph_score > 0 and quant_score == 0:
        predicted_rag = "graph"
    elif quant_score > 0 and graph_score == 0:
        predicted_rag = "quantitative"
    else:
        predicted_rag = "standard"

    return {
        "predicted_rag": predicted_rag,
        "expected_rag": expected_rag,
        "correct_routing": predicted_rag == expected_rag,
        "graph_score": graph_score,
        "quant_score": quant_score,
    }


def analyze_batch(questions):
    """Analyze a batch of questions for RAG routing correctness."""
    results = {
        "total": len(questions),
        "graph_questions": 0,
        "quantitative_questions": 0,
        "correct_routing": 0,
        "incorrect_routing": 0,
        "ambiguous_routing": 0,
        "by_dataset": {},
        "by_rag_type": {
            "graph": {"total": 0, "correct": 0, "incorrect": 0, "ambiguous": 0},
            "quantitative": {"total": 0, "correct": 0, "incorrect": 0, "ambiguous": 0},
        },
        "sample_misrouted": [],
    }

    for q in questions:
        rag_target = q["rag_target"]
        ds_name = q["dataset_name"]

        if rag_target == "graph":
            results["graph_questions"] += 1
        else:
            results["quantitative_questions"] += 1

        analysis = analyze_rag_routing(q["question"], rag_target)

        if ds_name not in results["by_dataset"]:
            results["by_dataset"][ds_name] = {
                "total": 0, "correct": 0, "incorrect": 0, "ambiguous": 0,
                "rag_target": rag_target,
            }

        results["by_dataset"][ds_name]["total"] += 1
        results["by_rag_type"][rag_target]["total"] += 1

        if analysis["correct_routing"]:
            results["correct_routing"] += 1
            results["by_dataset"][ds_name]["correct"] += 1
            results["by_rag_type"][rag_target]["correct"] += 1
        elif analysis["predicted_rag"] == "standard":
            results["ambiguous_routing"] += 1
            results["by_dataset"][ds_name]["ambiguous"] += 1
            results["by_rag_type"][rag_target]["ambiguous"] += 1
        else:
            results["incorrect_routing"] += 1
            results["by_dataset"][ds_name]["incorrect"] += 1
            results["by_rag_type"][rag_target]["incorrect"] += 1
            if len(results["sample_misrouted"]) < 20:
                results["sample_misrouted"].append({
                    "question": q["question"][:200],
                    "expected": rag_target,
                    "predicted": analysis["predicted_rag"],
                    "dataset": ds_name,
                })

    total = max(results["total"], 1)
    results["correct_rate"] = f"{results['correct_routing'] / total * 100:.1f}%"
    results["incorrect_rate"] = f"{results['incorrect_routing'] / total * 100:.1f}%"
    results["ambiguous_rate"] = f"{results['ambiguous_routing'] / total * 100:.1f}%"

    for rag_type in ["graph", "quantitative"]:
        rt = results["by_rag_type"][rag_type]
        t = max(rt["total"], 1)
        rt["correct_rate"] = f"{rt['correct'] / t * 100:.1f}%"
        rt["incorrect_rate"] = f"{rt['incorrect'] / t * 100:.1f}%"
        rt["ambiguous_rate"] = f"{rt['ambiguous'] / t * 100:.1f}%"

    for ds_name in results["by_dataset"]:
        ds = results["by_dataset"][ds_name]
        t = max(ds["total"], 1)
        ds["correct_rate"] = f"{ds['correct'] / t * 100:.1f}%"

    return results


# ─── Git Operations ─────────────────────────────────────────────

def git_push(message):
    """Commit and push results to git."""
    try:
        files_to_add = [
            "benchmark-workflows/rag-1000-test-questions.json",
            "benchmark-workflows/rag-1000-test-analysis.json",
            "benchmark-workflows/rag-1000-test-progress.json",
            "benchmark-workflows/generate-1000-rag-test-questions.py",
        ]

        subprocess.run(["git", "add"] + files_to_add, cwd=REPO_DIR, capture_output=True, timeout=30)
        subprocess.run(["git", "commit", "-m", message], cwd=REPO_DIR, capture_output=True, timeout=30)

        for retry in range(4):
            result = subprocess.run(
                ["git", "push", "-u", "origin", GIT_BRANCH],
                cwd=REPO_DIR, capture_output=True, timeout=60, text=True
            )
            if result.returncode == 0:
                print(f"  [GIT] Push successful")
                return True
            wait = 2 ** (retry + 1)
            print(f"  [GIT] Push failed (attempt {retry+1}), retrying in {wait}s...")
            time.sleep(wait)

        print(f"  [GIT] Push failed after 4 retries")
        return False
    except Exception as e:
        print(f"  [GIT] Error: {e}")
        return False


def save_progress(phase, total_generated, all_questions):
    """Save progress file."""
    progress = {
        "status": "running" if phase != "completed" else "completed",
        "phase": phase,
        "total_generated": total_generated,
        "target": 1000,
        "progress_pct": f"{total_generated / 10:.1f}%",
        "graph_questions": sum(1 for q in all_questions if q["rag_target"] == "graph"),
        "quantitative_questions": sum(1 for q in all_questions if q["rag_target"] == "quantitative"),
        "datasets_used": list(set(q["dataset_name"] for q in all_questions)) if all_questions else [],
        "updated_at": datetime.now().isoformat(),
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def save_questions(all_questions):
    """Save questions to JSON file."""
    output = {
        "metadata": {
            "title": "RAG Test Questions — Graph + Quantitative (1000 questions)",
            "generated_at": datetime.now().isoformat(),
            "total_questions": len(all_questions),
            "graph_questions": sum(1 for q in all_questions if q["rag_target"] == "graph"),
            "quantitative_questions": sum(1 for q in all_questions if q["rag_target"] == "quantitative"),
            "datasets": list(set(q["dataset_name"] for q in all_questions)),
            "deduplication": "Checked against 28,053 existing benchmark Q&A pairs",
            "note": "Questions from specific datasets (excluding HotPotQA) for Graph and Quantitative RAG testing",
        },
        "questions": all_questions,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def save_analysis(analysis):
    """Save analysis to JSON file."""
    with open(ANALYSIS_FILE, "w") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)


def print_analysis(analysis, label):
    """Print routing analysis to console."""
    print(f"\n  === RAG ROUTING ANALYSIS ({label}) ===")
    print(f"  Total questions: {analysis['total']}")
    print(f"  Correct routing: {analysis['correct_routing']} ({analysis['correct_rate']})")
    print(f"  Incorrect routing: {analysis['incorrect_routing']} ({analysis['incorrect_rate']})")
    print(f"  Ambiguous: {analysis['ambiguous_routing']} ({analysis['ambiguous_rate']})")
    print(f"  By RAG type:")
    for rag_type in ["graph", "quantitative"]:
        rt = analysis["by_rag_type"][rag_type]
        print(f"    {rag_type}: {rt['total']} questions, {rt['correct_rate']} correct")
    print(f"  By dataset:")
    for ds_name, ds_stats in sorted(analysis["by_dataset"].items()):
        print(f"    {ds_name:25s}: {ds_stats['total']:4d} questions, "
              f"{ds_stats['correct_rate']} correct, target={ds_stats['rag_target']}")
    if analysis["sample_misrouted"]:
        print(f"  Sample misrouted ({len(analysis['sample_misrouted'])}):")
        for m in analysis["sample_misrouted"][:5]:
            print(f"    [{m['expected']}->{m['predicted']}] ({m['dataset']}) {m['question'][:80]}...")


# ─── Main ────────────────────────────────────────────────────────

if __name__ == "__main__":
    start_time = datetime.now()
    all_questions = []
    generated_hashes = set()

    print("=" * 65)
    print("  RAG TEST QUESTION GENERATOR (v2 — corrected HF paths)")
    print("  Graph RAG (500) + Quantitative RAG (500) = 1000 questions")
    print(f"  Time: {start_time.isoformat()}")
    print("=" * 65)

    # Step 0: Load existing questions for deduplication
    print("\n  Loading existing questions for deduplication...")
    existing_hashes = load_existing_questions()

    print("\n  Graph RAG datasets (excluding HotPotQA):")
    for ds in GRAPH_RAG_DATASETS:
        print(f"    - {ds['name']:25s} {ds['target_count']:4d} questions  ({ds['hf_path']})")
    print(f"\n  Quantitative RAG datasets:")
    for ds in QUANTITATIVE_RAG_DATASETS:
        print(f"    - {ds['name']:25s} {ds['target_count']:4d} questions  ({ds['hf_path']})")

    # ═══════════════════════════════════════════════
    # PHASE 1: First 500 questions (Graph: 250, Quant: 250)
    # ═══════════════════════════════════════════════
    print("\n" + "#" * 65)
    print("  PHASE 1: First 500 questions")
    print("#" * 65)

    # Graph RAG Phase 1: musique (200) + start of 2wiki (50)
    for ds in GRAPH_RAG_DATASETS[:2]:
        ds_copy = dict(ds)
        if ds["name"] == "musique":
            ds_copy["target_count"] = 200
        elif ds["name"] == "2wikimultihopqa":
            ds_copy["target_count"] = 50
        questions = extract_questions(ds_copy, existing_hashes, generated_hashes)
        all_questions.extend(questions)
        save_progress("phase1_graph", len(all_questions), all_questions)
        time.sleep(1)

    # Quantitative RAG Phase 1: finqa (200) + tatqa (50)
    for ds in QUANTITATIVE_RAG_DATASETS[:2]:
        ds_copy = dict(ds)
        if ds["name"] == "finqa":
            ds_copy["target_count"] = 200
        elif ds["name"] == "tatqa":
            ds_copy["target_count"] = 50
        questions = extract_questions(ds_copy, existing_hashes, generated_hashes)
        all_questions.extend(questions)
        save_progress("phase1_quant", len(all_questions), all_questions)
        time.sleep(1)

    # ═══════════════════════════════════════════════
    # MILESTONE 1: ~500 questions — Analyze + Push
    # ═══════════════════════════════════════════════
    graph_count = sum(1 for q in all_questions if q["rag_target"] == "graph")
    quant_count = sum(1 for q in all_questions if q["rag_target"] == "quantitative")
    print(f"\n{'='*65}")
    print(f"  MILESTONE 1: {len(all_questions)} questions generated")
    print(f"  Graph: {graph_count} | Quantitative: {quant_count}")
    print(f"{'='*65}")

    analysis_phase1 = analyze_batch(all_questions)
    analysis_phase1["phase"] = "phase1"
    analysis_phase1["timestamp"] = datetime.now().isoformat()

    save_questions(all_questions)
    save_analysis({"title": "RAG Routing Analysis — Phase 1", "phases": [analysis_phase1]})
    save_progress("phase1_complete", len(all_questions), all_questions)
    print_analysis(analysis_phase1, "Phase 1")

    git_push(
        f"benchmark: {len(all_questions)} RAG test questions (phase 1/2) — "
        f"graph({graph_count})+quant({quant_count}) — deduplicated"
    )

    # ═══════════════════════════════════════════════
    # PHASE 2: Remaining ~500 questions
    # ═══════════════════════════════════════════════
    print("\n" + "#" * 65)
    print("  PHASE 2: Remaining 500 questions")
    print("#" * 65)

    # Graph RAG Phase 2: rest of 2wiki (150) + frames (100)
    for ds in GRAPH_RAG_DATASETS[1:]:
        ds_copy = dict(ds)
        if ds["name"] == "2wikimultihopqa":
            ds_copy["target_count"] = 150
        elif ds["name"] == "frames":
            ds_copy["target_count"] = 100
        questions = extract_questions(ds_copy, existing_hashes, generated_hashes)
        all_questions.extend(questions)
        save_progress("phase2_graph", len(all_questions), all_questions)
        time.sleep(1)

    # Fill gap: if frames was fully deduplicated, get more from 2wiki
    graph_count_now = sum(1 for q in all_questions if q["rag_target"] == "graph")
    if graph_count_now < 500:
        gap = 500 - graph_count_now
        print(f"\n  [FILL] Need {gap} more graph questions, fetching from 2wikimultihopqa...")
        ds_copy = dict(GRAPH_RAG_DATASETS[1])
        ds_copy["target_count"] = gap
        questions = extract_questions(ds_copy, existing_hashes, generated_hashes)
        all_questions.extend(questions)
        save_progress("phase2_graph_fill", len(all_questions), all_questions)

    # Quantitative RAG Phase 2: rest of tatqa (100) + convfinqa (100) + wikitable (50)
    for ds in QUANTITATIVE_RAG_DATASETS[1:]:
        ds_copy = dict(ds)
        if ds["name"] == "tatqa":
            ds_copy["target_count"] = 100
        elif ds["name"] == "convfinqa":
            ds_copy["target_count"] = 100
        elif ds["name"] == "wikitablequestions":
            ds_copy["target_count"] = 50
        questions = extract_questions(ds_copy, existing_hashes, generated_hashes)
        all_questions.extend(questions)
        save_progress("phase2_quant", len(all_questions), all_questions)
        time.sleep(1)

    # ═══════════════════════════════════════════════
    # FINAL: Full Analysis + Push
    # ═══════════════════════════════════════════════
    graph_count = sum(1 for q in all_questions if q["rag_target"] == "graph")
    quant_count = sum(1 for q in all_questions if q["rag_target"] == "quantitative")
    print(f"\n{'='*65}")
    print(f"  FINAL: {len(all_questions)} questions generated")
    print(f"  Graph: {graph_count} | Quantitative: {quant_count}")
    print(f"{'='*65}")

    analysis_final = analyze_batch(all_questions)
    analysis_final["phase"] = "final"
    analysis_final["timestamp"] = datetime.now().isoformat()

    save_questions(all_questions)
    full_analysis = {
        "title": "RAG Routing Analysis — Graph + Quantitative — 1000 Questions",
        "generated_at": datetime.now().isoformat(),
        "total_questions": len(all_questions),
        "deduplication": {
            "existing_hashes_loaded": len(existing_hashes),
            "new_hashes_generated": len(generated_hashes),
            "method": "MD5 hash of lowercased question text",
        },
        "phases": [analysis_phase1, analysis_final],
        "final_summary": {
            "total": analysis_final["total"],
            "graph_questions": analysis_final["graph_questions"],
            "quantitative_questions": analysis_final["quantitative_questions"],
            "correct_routing": analysis_final["correct_routing"],
            "correct_rate": analysis_final["correct_rate"],
            "incorrect_routing": analysis_final["incorrect_routing"],
            "incorrect_rate": analysis_final["incorrect_rate"],
            "ambiguous_routing": analysis_final["ambiguous_routing"],
            "ambiguous_rate": analysis_final["ambiguous_rate"],
        },
        "by_rag_type": analysis_final["by_rag_type"],
        "by_dataset": analysis_final["by_dataset"],
        "sample_misrouted": analysis_final["sample_misrouted"],
        "datasets_used": {
            "graph_rag": [
                {"name": d["name"], "source": d["hf_path"], "type": d["description"]}
                for d in GRAPH_RAG_DATASETS
            ],
            "quantitative_rag": [
                {"name": d["name"], "source": d["hf_path"], "type": d["description"]}
                for d in QUANTITATIVE_RAG_DATASETS
            ],
        },
    }
    save_analysis(full_analysis)
    save_progress("completed", len(all_questions), all_questions)
    print_analysis(analysis_final, "Final")

    elapsed = (datetime.now() - start_time).total_seconds()
    git_push(
        f"benchmark: {len(all_questions)} RAG test questions FINAL — "
        f"graph({graph_count})+quant({quant_count}) — "
        f"deduplicated vs {len(existing_hashes)} existing"
    )

    print(f"\n{'='*65}")
    print(f"  COMPLETE")
    print(f"  Total: {len(all_questions)} questions (target: 1000)")
    print(f"  Graph RAG: {graph_count} | Quantitative RAG: {quant_count}")
    print(f"  Dedup: checked against {len(existing_hashes)} existing questions")
    print(f"  Duration: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Analysis: {ANALYSIS_FILE}")
    print(f"{'='*65}")
