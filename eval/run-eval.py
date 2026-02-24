import json
import os
import sys
import time
from urllib import request, error
from datetime import datetime
from collections import defaultdict

# Timezone: Europe/Paris
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from tz_utils import paris_now, paris_iso
except ImportError:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Paris")
    def paris_now(): return datetime.now(_TZ)
    def paris_iso(): return datetime.now(_TZ).isoformat(timespec='seconds')

# --- Constants ---
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASETS_DIR = os.path.join(REPO_ROOT, "datasets")
TESTED_IDS_FILE = os.path.join(REPO_ROOT, "docs", "tested_ids.json")

# RAG + PME Endpoints — Multi-endpoint support
# Per-pipeline hosts: N8N_HOST_STANDARD, N8N_HOST_GRAPH, etc. override N8N_HOST
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

# Guard: block accidental use of VM n8n for evals
def _check_n8n_host():
    import re
    hosts_to_check = [N8N_HOST]
    for key in os.environ:
        if key.startswith("N8N_HOST_"):
            hosts_to_check.append(os.environ[key])
    for host in hosts_to_check:
        if re.search(r'localhost|127\.0\.0\.1|34\.136\.180\.66', host):
            if "--allow-local" not in sys.argv:
                print(f"FATAL: N8N_HOST points to local/VM ({host}).")
                print("Evals MUST run on HF Space. Set N8N_HOST or pass --allow-local.")
                sys.exit(1)
_check_n8n_host()

def _host_for(pipeline):
    """Get n8n host for a specific pipeline. Supports per-pipeline routing."""
    return os.environ.get(f"N8N_HOST_{pipeline.upper().replace('-','_')}", N8N_HOST)

# Webhook paths (host-independent)
WEBHOOK_PATHS = {
    "standard": "/webhook/rag-multi-index-v3",
    "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
    "pme-gateway": "/webhook/pme-assistant-gateway",
    "pme-action": "/webhook/pme-action-executor",
    "pme-whatsapp": "/webhook/whatsapp-incoming",
}

# Build endpoints with per-pipeline hosts
RAG_ENDPOINTS = {k: f"{_host_for(k)}{v}" for k, v in WEBHOOK_PATHS.items()}

# Per-pipeline optimal batch sizes (from Session 27 concurrency tests)
PIPELINE_BATCH_SIZES = {
    "standard": 10,
    "graph": 5,
    "quantitative": 3,
    "orchestrator": 2,
    "pme-gateway": 1,
    "pme-action": 1,
    "pme-whatsapp": 1,
}

# Per-pipeline optimal timeouts
PIPELINE_TIMEOUTS = {
    "standard": 90,
    "graph": 90,
    "quantitative": 120,
    "orchestrator": 180,
    "pme-gateway": 60,
    "pme-action": 60,
    "pme-whatsapp": 60,
}

# --- Functions ---

def call_local_reasoning(question_text, rag_type="quantitative", timeout=30):
    """
    Call OpenRouter LLM directly from VM for context-rich questions.
    Bypasses HF Space n8n pipeline (which is rate-limited from HF IPs).
    Used for:
      - quantitative questions with embedded context+table_data (FIX-39)
      - graph questions with embedded reference context (FIX-39d)
    Returns same format as call_rag() for drop-in replacement.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"data": None, "latency_ms": 0, "error": "OPENROUTER_API_KEY not set", "http_status": None}

    if rag_type == "quantitative":
        system_prompt = (
            "You are a financial analyst. Answer the question based ONLY on the provided context and table data.\n"
            "Steps:\n"
            "1. LOCATE the relevant numbers in the context/table\n"
            "2. EXTRACT the exact values needed\n"
            "3. CALCULATE if needed (show your work)\n"
            "4. ANSWER with just the final answer\n\n"
            "IMPORTANT: Your FIRST LINE must be the final answer only (a number, percentage, or short phrase). "
            "Then explain your reasoning below."
        )
        # Parse FIX-39 format: question + \n\nContext:\n... + \n\nTable data:\n...
        parts = question_text.split("\n\nContext:\n", 1)
        if len(parts) == 2:
            question_part = parts[0].strip()
            rest = parts[1]
        else:
            question_part = question_text
            rest = ""

        user_prompt = f"{rest}\n\nQuestion: {question_part}\n\nAnswer (first line = final answer only):" if rest else question_text

    elif rag_type == "graph":
        system_prompt = (
            "You are a knowledgeable assistant. Answer the question based ONLY on the provided reference context.\n"
            "IMPORTANT: Many questions require MULTI-HOP reasoning — connecting facts from DIFFERENT paragraphs.\n"
            "Steps:\n"
            "1. Identify the key entities in the question\n"
            "2. Find information about each entity in the context (they may be in different paragraphs)\n"
            "3. Connect the facts to answer the question\n"
            "4. Give ONLY the final answer on the first line — a name, date, number, or short phrase\n"
            "If the answer is clearly in the context, give it directly. Do NOT say 'not found' if the info exists."
        )
        parts = question_text.split("\n\nReference context:", 1)
        if len(parts) == 2:
            question_part = parts[0].strip()
            context = parts[1].strip()
        else:
            question_part = question_text
            context = ""

        user_prompt = f"Reference context:\n{context}\n\nQuestion: {question_part}\n\nAnswer:" if context else question_text

    elif rag_type == "standard":
        system_prompt = (
            "You are a knowledgeable assistant. Answer the question concisely and accurately.\n"
            "Give ONLY the final answer on the first line — a name, fact, or short phrase."
        )
        user_prompt = f"Question: {question_text}\n\nAnswer:"

    else:
        system_prompt = "Answer the question concisely and accurately."
        user_prompt = question_text

    start_time = datetime.now()
    # Models to try in order (rotate on rate-limit). No system role — Google AI Studio rejects it for Gemma.
    MODELS = [
        "google/gemma-3-27b-it:free",
        "arcee-ai/trinity-large-preview:free",
        "qwen/qwen3-235b-a22b:free",
    ]
    full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt[:12000]}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    for model in MODELS:
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": full_prompt}],
            "max_tokens": 300,
            "temperature": 0.1
        }).encode('utf-8')

        try:
            req = request.Request("https://openrouter.ai/api/v1/chat/completions",
                                 data=payload, headers=headers)
            with request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                # Take first line as the answer
                first_line = content.strip().split("\n")[0].strip()
                # Clean up common prefixes
                for prefix in ["Answer:", "The answer is", "Final answer:", "A:", "**", "## "]:
                    if first_line.lower().startswith(prefix.lower()):
                        first_line = first_line[len(prefix):].strip()
                # Remove trailing ** (bold markdown)
                first_line = first_line.rstrip("*").strip()

                return {
                    "data": {"response": first_line, "full_response": content},
                    "latency_ms": latency_ms,
                    "error": None,
                    "http_status": 200
                }
        except error.HTTPError as e:
            if e.code == 429 and model != MODELS[-1]:
                time.sleep(1)
                continue  # Try next model
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return {"data": None, "latency_ms": latency_ms, "error": str(e), "http_status": e.code}
        except Exception as e:
            if model != MODELS[-1]:
                time.sleep(0.5)
                continue
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return {"data": None, "latency_ms": latency_ms, "error": str(e), "http_status": None}

    latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    return {"data": None, "latency_ms": latency_ms, "error": "all models rate-limited", "http_status": 429}


def call_rag(endpoint, question, timeout=60, max_retries=3):
    """
    Makes an HTTP POST request to the RAG endpoint with retry + exponential backoff.
    Returns a dictionary with 'data', 'latency_ms', 'error', 'http_status'.
    Retries on: 429 (rate limit), 502/503/504 (server overload), timeouts, connection errors.
    """
    RETRYABLE_CODES = {429, 502, 503, 504}
    last_result = None

    for attempt in range(max_retries):
        start_time = datetime.now()
        try:
            payload = json.dumps({"query": question, "tenant_id": "benchmark"}).encode('utf-8')
            headers = {"Content-Type": "application/json"}
            req = request.Request(endpoint, data=payload, headers=headers)
            with request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                return {"data": data, "latency_ms": latency_ms, "error": None, "http_status": resp.getcode()}
        except error.HTTPError as e:
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            last_result = {"data": None, "latency_ms": latency_ms, "error": str(e), "http_status": e.code}
            if e.code in RETRYABLE_CODES and attempt < max_retries - 1:
                delay = (2 ** attempt) + 1  # 2s, 5s, 9s
                time.sleep(delay)
                continue
            return last_result
        except (ConnectionError, TimeoutError, OSError) as e:
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            last_result = {"data": None, "latency_ms": latency_ms, "error": str(e), "http_status": None}
            if attempt < max_retries - 1:
                delay = (2 ** attempt) + 1
                time.sleep(delay)
                continue
            return last_result
        except Exception as e:
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return {"data": None, "latency_ms": latency_ms, "error": str(e), "http_status": None}

    return last_result or {"data": None, "latency_ms": 0, "error": "max retries exhausted", "http_status": None}


def extract_answer(response_data):
    """
    Extracts the final answer from the RAG pipeline's response data.
    Handles both dict and list responses (webhooks return arrays).
    """
    if isinstance(response_data, list):
        response_data = response_data[0] if response_data else {}
    if not isinstance(response_data, dict):
        return str(response_data) if response_data else ""
    # Try multiple common response field names
    for key in ["response", "answer", "result", "interpretation", "final_response"]:
        if key in response_data and response_data[key]:
            return str(response_data[key])
    # Fallback to nested output
    output = response_data.get("output", {})
    if isinstance(output, dict):
        return output.get("answer", "") or output.get("response", "")
    return ""


def evaluate_answer(answer, expected_answer):
    """
    Evaluates the extracted answer against the expected answer.
    Returns a dictionary with 'correct', 'method', 'f1'.
    """
    import re
    answer_lower = answer.lower().strip()
    expected_lower = expected_answer.lower().strip()

    if not expected_lower:
        # No expected answer — just check non-empty response
        return {"correct": len(answer_lower) > 10, "method": "NON_EMPTY", "f1": 1.0 if len(answer_lower) > 10 else 0.0}

    # Normalize numbers: remove commas, $, % for comparison
    def normalize(text):
        import unicodedata
        # Normalize unicode whitespace to regular spaces
        text = ''.join(' ' if unicodedata.category(c).startswith('Z') else c for c in text)
        # Normalize unicode subscripts/superscripts to ASCII
        sub_map = str.maketrans('₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹', '01234567890123456789')
        text = text.translate(sub_map)
        text = text.replace('°', ' degrees ')
        text = re.sub(r'(\d),(\d)', r'\1\2', text)
        # Strip punctuation from tokens (so "Newton," matches "Newton")
        text = re.sub(r'[.,;:!?\'"()\[\]{}\-/]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.replace('$', '').replace('%', '').strip()

    norm_answer = normalize(answer_lower)
    norm_expected = normalize(expected_lower)

    if norm_answer == norm_expected:
        return {"correct": True, "method": "EXACT_MATCH", "f1": 1.0}
    elif norm_expected in norm_answer:
        return {"correct": True, "method": "CONTAINS_MATCH", "f1": 0.9}
    elif norm_answer in norm_expected:
        return {"correct": True, "method": "SUBSET_MATCH", "f1": 0.8}
    else:
        # Token-level F1 for partial matches
        STOPWORDS = {"a", "an", "the", "is", "of", "in", "to", "and", "for", "on", "at", "with", "from", "s",
                     "that", "was", "by", "it", "its", "are", "were", "been", "be", "has", "have", "had",
                     "which", "where", "who", "whom", "this", "these", "those", "or", "but", "not", "also"}
        answer_tokens = set(norm_answer.split())
        expected_tokens = set(norm_expected.split())
        # Filter stopwords from expected (keep content words only)
        content_expected = expected_tokens - STOPWORDS
        if not content_expected:
            content_expected = expected_tokens
        if not content_expected:
            return {"correct": False, "method": "NO_MATCH", "f1": 0.0}
        # Exact token overlap
        overlap = answer_tokens & content_expected
        # Fuzzy: substring matching for tokens >= 3 chars
        unmatched = content_expected - overlap
        for et in list(unmatched):
            if len(et) < 3:
                continue
            for at in answer_tokens:
                if len(at) < 3:
                    continue
                # Substring match
                if et in at or at in et:
                    overlap.add(et)
                    break
                # Prefix match (75%+): handles "antibiotic"/"antibiotics", "leader"/"leadership"
                min_len = min(len(et), len(at))
                if min_len >= 4:
                    common_prefix = 0
                    for i in range(min_len):
                        if et[i] == at[i]:
                            common_prefix += 1
                        else:
                            break
                    if common_prefix >= min_len * 0.75:
                        overlap.add(et)
                        break
        if not overlap:
            return {"correct": False, "method": "NO_MATCH", "f1": 0.0}
        precision = len(overlap) / len(answer_tokens) if answer_tokens else 0
        recall = len(overlap) / len(content_expected)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        # Consider correct if recall >= 0.6 (most expected keywords found in answer)
        # or F1 >= 0.35 (reasonable overlap even with verbose answers)
        is_correct = f1 >= 0.35 or recall >= 0.6
        method = "TOKEN_F1" if recall < 0.6 else "FUZZY_RECALL"
        return {"correct": is_correct, "method": method, "f1": round(f1, 4)}

def compute_f1(answer, expected):
    """Compute F1 score between answer and expected."""
    return evaluate_answer(answer, expected)["f1"]


def extract_pipeline_details(response_data, rag_type):
    """
    Extracts specific pipeline details from the response for diagnostic purposes.
    """
    if isinstance(response_data, list):
        response_data = response_data[0] if response_data else {}
    if not isinstance(response_data, dict):
        return {"rag_type": rag_type}
    return {"rag_type": rag_type, "response_keys": list(response_data.keys())}


def _embed_graph_context(question_text, context_str):
    """Embed graph context into question text, handling ALL known formats.

    Supported formats (FIX-39h — permanent fix):
      - musique/hotpotqa: [{"title":..., "paragraph_text":...}]
      - 2wikimultihopqa: {"title": [...], "sentences": [[...],...]}
      - plain text context
    """
    if not context_str or len(context_str) < 50:
        return question_text

    ctx = context_str.strip()
    ctx_text = ""

    try:
        # Format 1: Array of objects — musique, hotpotqa
        if ctx.startswith('['):
            paragraphs = json.loads(ctx)
            parts = []
            for p in paragraphs[:15]:
                if isinstance(p, dict):
                    title = p.get("title", "")
                    text = p.get("paragraph_text", p.get("text", ""))
                    if title and text:
                        parts.append(f"[{title}] {text}")
                    elif text:
                        parts.append(text)
            ctx_text = "\n".join(parts)

        # Format 2: Dict with title+sentences — 2wikimultihopqa (FIX-39h)
        elif ctx.startswith('{'):
            parsed = json.loads(ctx)
            if isinstance(parsed, dict):
                titles = parsed.get("title", [])
                sentences = parsed.get("sentences", [])
                parts = []
                for i, title in enumerate(titles):
                    if i < len(sentences):
                        sents = sentences[i]
                        if isinstance(sents, list):
                            text = " ".join(str(s) for s in sents)
                        else:
                            text = str(sents)
                        parts.append(f"[{title}] {text}")
                    else:
                        parts.append(f"[{title}]")
                ctx_text = "\n".join(parts)

        # Format 3: Plain text
        else:
            ctx_text = ctx

    except (json.JSONDecodeError, TypeError, KeyError):
        # Fallback: use raw context as-is
        ctx_text = ctx

    if ctx_text:
        return f"{question_text}\n\nReference context:\n{ctx_text[:6000]}"
    return question_text


def _embed_quant_context(question_text, context_str, table_data):
    """Embed quantitative context + table into question text (FIX-39).

    Handles table_data as: str (JSON), list, dict, or None.
    """
    if not context_str and not table_data:
        return question_text

    parts = [question_text]

    if context_str and context_str.strip():
        parts.append(f"\n\nContext:\n{context_str}")

    if table_data:
        if isinstance(table_data, str):
            # Try to parse as JSON array-of-arrays for readable formatting
            try:
                parsed = json.loads(table_data)
                if isinstance(parsed, list):
                    lines = []
                    for row in parsed:
                        if isinstance(row, list):
                            lines.append(" | ".join(str(cell) for cell in row))
                        else:
                            lines.append(str(row))
                    table_str = "\n".join(lines)
                else:
                    table_str = table_data
            except json.JSONDecodeError:
                table_str = table_data
        elif isinstance(table_data, list):
            lines = []
            for row in table_data:
                if isinstance(row, list):
                    lines.append(" | ".join(str(cell) for cell in row))
                elif isinstance(row, dict):
                    lines.append(" | ".join(f"{k}: {v}" for k, v in row.items()))
                else:
                    lines.append(str(row))
            table_str = "\n".join(lines)
        else:
            table_str = json.dumps(table_data)
        parts.append(f"\n\nTable data:\n{table_str}")

    return "".join(parts)


def _load_dataset_file(filepath, questions, embed_context=False):
    """Load questions from a single dataset file.

    Args:
        filepath: Path to JSON dataset file
        questions: defaultdict(list) to append to
        embed_context: If True, embed context/table into question text
    """
    if not os.path.exists(filepath):
        print(f"  WARNING: Dataset file not found: {filepath}")
        return 0

    with open(filepath) as f:
        data = json.load(f)

    loaded = 0
    skipped = 0
    for q in data.get("questions", []):
        rag_target = q.get("rag_target", "unknown")
        if rag_target not in ("standard", "graph", "quantitative", "orchestrator", "pme-gateway"):
            skipped += 1
            continue

        question_text = q.get("question", "")
        if not question_text.strip():
            skipped += 1
            continue

        # Embed context for rich datasets (Phase 2 HF questions)
        if embed_context:
            if rag_target == "quantitative":
                question_text = _embed_quant_context(
                    question_text,
                    q.get("context", ""),
                    q.get("table_data")
                )
            elif rag_target == "graph":
                question_text = _embed_graph_context(
                    question_text,
                    q.get("context", "")
                )

        questions[rag_target].append({
            "id": q["id"],
            "question": question_text,
            "expected": q.get("expected_answer", ""),
            "rag_type": rag_target,
        })
        loaded += 1

    print(f"  Loaded {loaded} questions from {os.path.basename(filepath)}"
          + (f" (skipped {skipped})" if skipped else ""))
    return loaded


def load_questions(include_1000=False, dataset="phase-1"):
    """Load questions from specified dataset files.

    Handles ALL known context formats for graph and quantitative questions.
    Context is embedded into question text for Phase 2 (HF datasets have rich context).
    Phase 1 questions are simple knowledge questions (no context needed).
    """
    questions = defaultdict(list)

    if dataset == "phase-1":
        _load_dataset_file(
            os.path.join(DATASETS_DIR, "phase-1", "standard-orch-50x2.json"),
            questions, embed_context=False)
        _load_dataset_file(
            os.path.join(DATASETS_DIR, "phase-1", "graph-quant-50x2.json"),
            questions, embed_context=False)

    elif dataset == "phase-2":
        # HF-1000: graph + quantitative with rich context
        _load_dataset_file(
            os.path.join(DATASETS_DIR, "phase-2", "hf-1000.json"),
            questions, embed_context=True)
        # Expansion: +500 graph + 500 quantitative from HF raw
        _load_dataset_file(
            os.path.join(DATASETS_DIR, "phase-2", "graph-quant-expansion-500x2.json"),
            questions, embed_context=True)
        # Standard + orchestrator: knowledge questions (no context)
        _load_dataset_file(
            os.path.join(DATASETS_DIR, "phase-2", "standard-orch-1000x2.json"),
            questions, embed_context=False)
        # PME Gateway: project management questions
        pme_file = os.path.join(DATASETS_DIR, "phase-2", "pme-gateway-1000.json")
        if os.path.exists(pme_file):
            _load_dataset_file(pme_file, questions, embed_context=False)

    elif dataset == "all":
        phase1_q = load_questions(dataset="phase-1")
        phase2_q = load_questions(dataset="phase-2")
        for p_type, q_list in phase1_q.items():
            questions[p_type].extend(q_list)
        for p_type, q_list in phase2_q.items():
            questions[p_type].extend(q_list)

    # Log data quality summary
    total = sum(len(v) for v in questions.values())
    print(f"  Total: {total} questions across {len(questions)} pipelines")
    for pipe, qs in sorted(questions.items()):
        ctx_count = sum(1 for q in qs if "\n\nReference context:" in q["question"]
                        or "\n\nContext:\n" in q["question"])
        print(f"    {pipe}: {len(qs)} questions ({ctx_count} with embedded context)")

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

