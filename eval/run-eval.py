import json
import os
import sys
from urllib import request, error
from datetime import datetime
from collections import defaultdict

# --- Constants ---
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS_DIR = os.path.join(REPO_ROOT, "datasets")
TESTED_IDS_FILE = os.path.join(REPO_ROOT, "docs", "tested_ids.json")

# RAG Endpoints from live-writer.py _default_data
RAG_ENDPOINTS = {
    "standard": "https://amoret.app.n8n.cloud/webhook/rag-multi-index-v3",
    "graph": "https://amoret.app.n8n.cloud/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "https://amoret.app.n8n.cloud/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "https://amoret.app.n8n.cloud/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
}

# --- Functions ---

def call_rag(endpoint, question, timeout=60):
    """
    Makes an HTTP POST request to the RAG endpoint.
    Returns a dictionary with 'data', 'latency_ms', 'error', 'http_status'.
    """
    start_time = datetime.now()
    try:
        payload = json.dumps({"query": question}).encode('utf-8')
        headers = {"Content-Type": "application/json"}
        req = request.Request(endpoint, data=payload, headers=headers)
        with request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return {"data": data, "latency_ms": latency_ms, "error": None, "http_status": resp.getcode()}
    except error.HTTPError as e:
        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return {"data": None, "latency_ms": latency_ms, "error": str(e), "http_status": e.code}
    except Exception as e:
        latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return {"data": None, "latency_ms": latency_ms, "error": str(e), "http_status": None}


def extract_answer(response_data):
    """
    Extracts the final answer from the RAG pipeline's response data.
    """
    return response_data.get("answer", "") or response_data.get("output", {}).get("answer", "")


def evaluate_answer(answer, expected_answer):
    """
    Evaluates the extracted answer against the expected answer.
    Returns a dictionary with 'correct', 'method', 'f1'.
    """
    answer_lower = answer.lower().strip()
    expected_lower = expected_answer.lower().strip()

    if answer_lower == expected_lower:
        return {"correct": True, "method": "EXACT_MATCH", "f1": 1.0}
    elif expected_lower in answer_lower or answer_lower in expected_lower:
        return {"correct": False, "method": "PARTIAL_MATCH", "f1": 0.5} # Arbitrary F1 for partial
    else:
        return {"correct": False, "method": "NO_MATCH", "f1": 0.0}

def compute_f1(answer, expected):
    """Placeholder for F1 computation."""
    return evaluate_answer(answer, expected)["f1"]


def extract_pipeline_details(response_data, rag_type):
    """
    Extracts specific pipeline details from the response for diagnostic purposes.
    """
    return {"rag_type": rag_type, "response_keys": list(response_data.keys())}


def load_questions(include_1000=False, dataset="phase-1"):
    """
    Loads questions from specified dataset files.
    """
    questions = defaultdict(list) # Use defaultdict for easier appending

    if dataset == "phase-1":
        phase1_files = [
            os.path.join(DATASETS_DIR, "phase-1", "standard-orch-50x2.json"),
            os.path.join(DATASETS_DIR, "phase-1", "graph-quant-50x2.json"),
        ]
        
        for pf in phase1_files:
            if os.path.exists(pf):
                with open(pf) as f:
                    data = json.load(f)
                    for q in data.get("questions", []):
                        # Use 'rag_target' to group questions
                        rag_target = q.get("rag_target", "unknown")
                        questions[rag_target].append({
                            "id": q["id"],
                            "question": q["question"],
                            "expected": q["expected_answer"], # Use expected_answer
                            "rag_type": rag_target # Store for later use
                        })
            else:
                print(f"Warning: Dataset file not found: {pf}")

    elif dataset == "phase-2":
        phase2_file = os.path.join(DATASETS_DIR, "phase-2", "hf-1000.json")
        if os.path.exists(phase2_file):
            with open(phase2_file) as f:
                data = json.load(f)
                for q in data.get("questions", []):
                    rag_target = q.get("rag_target", "unknown")
                    questions[rag_target].append({
                        "id": q["id"],
                        "question": q["question"],
                        "expected": q["expected_answer"],
                        "rag_type": rag_target
                    })
        else:
            print(f"Warning: Dataset file not found: {phase2_file}")
    
    # Handle "all" dataset explicitly
    if dataset == "all":
        # Recursively call for phase-1 and phase-2 and merge
        phase1_q = load_questions(dataset="phase-1")
        phase2_q = load_questions(dataset="phase-2")
        
        for p_type, q_list in phase1_q.items():
            questions.setdefault(p_type, []).extend(q_list)
        for p_type, q_list in phase2_q.items():
            questions.setdefault(p_type, []).extend(q_list)

    return questions


def load_tested_ids_by_type():
    """
    Loads tested question IDs from TESTED_IDS_FILE.
    """
    if os.path.exists(TESTED_IDS_FILE):
        with open(TESTED_IDS_FILE) as f:
            data = json.load(f)
            return {k: set(v) for k, v in data.items()}
    return {}


def save_tested_ids(tested_ids_by_type):
    """
    Saves tested question IDs to TESTED_IDS_FILE.
    """
    with open(TESTED_IDS_FILE, "w") as f:
        json.dump({k: list(v) for k, v in tested_ids_by_type.items()}, f, indent=2)

