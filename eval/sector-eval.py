#!/usr/bin/env python3
"""
Sector RAG Evaluation — Tests RAG pipelines against sector-specific data.

Evaluates 4 ETI sectors (Finance, BTP, Juridique, Industrie) using data
ingested in:
  - Pinecone: website-sectors-jina-1024 (31,937 vectors, namespace: sectors)
  - Supabase: sector_documents (11,387 rows)
  - Neo4j: SectorDocument + Entity nodes

Supports three modes:
  1. --webhook (default): Calls n8n webhooks for each pipeline. Tests the
     full end-to-end RAG pipeline including retrieval + LLM generation.
  2. --direct-pinecone: Bypasses n8n, queries sector Pinecone directly +
     uses LiteLLM/Groq for answer generation.
  3. --all-pipelines: Tests every question against ALL 3 pipelines
     (standard, graph, quantitative) via webhooks.

Usage:
  source .env.local
  python3 eval/sector-eval.py                          # Webhook mode, full dataset
  python3 eval/sector-eval.py --questions 5            # 5 per sector smoke test
  python3 eval/sector-eval.py --questions 5 --webhook  # 5 per sector via webhooks
  python3 eval/sector-eval.py --sector finance         # Single sector
  python3 eval/sector-eval.py --all-pipelines          # Test all 3 pipelines
  python3 eval/sector-eval.py --direct-pinecone        # Direct Pinecone query
  python3 eval/sector-eval.py --dry-run                # Show questions, no calls
  python3 eval/sector-eval.py --dataset path/to/file   # Custom dataset
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from urllib import request, error
from collections import defaultdict

# ─── Paths ────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
# Default to full eval dataset (220 questions); use --dataset for smoke test
DATASET_FILE = os.path.join(REPO_ROOT, "sectors", "eval-datasets", "sector-full-eval.json")
SMOKE_DATASET = os.path.join(REPO_ROOT, "sectors", "eval-datasets", "sector-smoke-test.json")
RESULTS_DIR = os.path.join(REPO_ROOT, "logs", "sector-eval")
RESULTS_DOCS = os.path.join(REPO_ROOT, "docs", "sector-eval-results.json")

# ─── Environment ──────────────────────────────────────────────────────────
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
JINA_API_KEY = os.environ.get("JINA_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Multi-Space round-robin support
N8N_ALL_HOSTS = [h.strip() for h in os.environ.get("N8N_ALL_HOSTS", N8N_HOST).split(",") if h.strip()]
_rr_counters = {}

# Sector Pinecone index host
SECTOR_INDEX_HOST = "https://website-sectors-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
SECTOR_NAMESPACE = "sectors"

# Self-hosted embeddings
EMBEDDINGS_URL = os.environ.get(
    "EMBEDDINGS_URL",
    "https://lbjlincoln-nomos-embeddings-api.hf.space/v1/embeddings"
)

# Guard: block VM n8n for evals
if re.search(r'localhost|127\.0\.0\.1|34\.136\.180\.66', N8N_HOST):
    if "--allow-local" not in sys.argv:
        print(f"FATAL: N8N_HOST points to local/VM ({N8N_HOST}).")
        print("Set N8N_HOST to HF Space or pass --allow-local.")
        sys.exit(1)

# ─── Webhook paths ────────────────────────────────────────────────────────
WEBHOOK_PATHS = {
    "standard":     "/webhook/rag-multi-index-v3",
    "graph":        "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
}

ALL_PIPELINES = ["standard", "graph", "quantitative"]


def _get_hosts_for_pipeline(pipeline):
    """Get list of hosts for a pipeline (from env or global)."""
    env_key = f"N8N_HOST_{pipeline.upper()}"
    hosts_str = os.environ.get(env_key, "")
    if hosts_str and "<" not in hosts_str:
        return [h.strip() for h in hosts_str.split(",") if h.strip()]
    return N8N_ALL_HOSTS


def _rr_endpoint(pipeline, webhook_path):
    """Round-robin across hosts for a pipeline."""
    hosts = _get_hosts_for_pipeline(pipeline)
    if not hosts:
        return f"{N8N_HOST}{webhook_path}"
    idx = _rr_counters.get(pipeline, 0)
    _rr_counters[pipeline] = idx + 1
    host = hosts[idx % len(hosts)]
    return f"{host}{webhook_path}"


def load_sector_dataset(filepath=DATASET_FILE, sector_filter=None, max_per_sector=None):
    """Load sector eval questions from JSON dataset file."""
    if not os.path.exists(filepath):
        # Fallback to smoke test if full eval not found
        if os.path.exists(SMOKE_DATASET):
            print(f"  WARN: {filepath} not found, falling back to smoke test")
            filepath = SMOKE_DATASET
        else:
            print(f"ERROR: Dataset not found: {filepath}")
            sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data.get("questions", [])

    if sector_filter:
        questions = [q for q in questions if q.get("sector") == sector_filter]

    if max_per_sector:
        by_sector = defaultdict(list)
        for q in questions:
            by_sector[q.get("sector", "unknown")].append(q)
        questions = []
        for sector_qs in by_sector.values():
            questions.extend(sector_qs[:max_per_sector])

    return questions, data.get("metadata", {})


def normalize_for_match(text):
    """Normalize text for fuzzy matching."""
    normalized = re.sub(r'(\d),(\d)', r'\1\2', text)
    normalized = normalized.replace('$', '').replace('%', '').replace('\u20ac', '')
    # Normalize unit expressions
    normalized = re.sub(r'(\d+)\s*(meter|metre|meters|metres)', r'\1m', normalized)
    normalized = re.sub(r'(\d+)\s*(millimeter|millimetre|millimeters|millimetres)', r'\1mm', normalized)
    normalized = re.sub(r'(\d+)\s*(kilonewton|kilonewtons)', r'\1kn', normalized)
    # Remove diacritics for French matching (caducité → caducite)
    import unicodedata
    normalized = unicodedata.normalize('NFD', normalized)
    normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.lower().strip()


def flexible_match(answer, expected):
    """Check if expected string matches answer with multiple strategies."""
    norm_answer = normalize_for_match(answer)
    norm_expected = normalize_for_match(expected)

    # Strategy 1: Direct substring match
    if norm_expected in norm_answer:
        return True

    # Strategy 2: Word-level match (all words of expected appear in answer)
    expected_words = norm_expected.split()
    if len(expected_words) > 1:
        if all(w in norm_answer for w in expected_words):
            return True

    # Strategy 3: Stem-based matching for French (check if expected is prefix of any word)
    answer_words = norm_answer.split()
    if len(norm_expected) >= 3:
        for word in answer_words:
            # Check prefix match (at least 75% of expected length)
            min_prefix = max(3, int(len(norm_expected) * 0.75))
            if word.startswith(norm_expected[:min_prefix]):
                return True
            # Check if expected is a prefix of a word in the answer
            if norm_expected.startswith(word[:min_prefix]) and len(word) >= min_prefix:
                return True

    # Strategy 4: Number extraction - check if the expected number appears anywhere
    expected_numbers = re.findall(r'\d+\.?\d*', norm_expected)
    if expected_numbers:
        answer_numbers = re.findall(r'\d+\.?\d*', norm_answer)
        for exp_num in expected_numbers:
            if exp_num in answer_numbers:
                return True

    # Strategy 5: Synonym/concept matching for common expected terms
    SYNONYMS = {
        'still image': ['static image', 'fixed image', 'stationary image', 'still picture'],
        'hacking': ['malware', 'cyber threat', 'security threat', 'virus', 'unauthorized access'],
        'remote': ['ip remote', 'ip control', 'remote control', 'network control'],
        'pressure': ['pressure test', 'water pressure', 'hydrostatic', 'pressure testing'],
        'settings': ['setting', 'menu', 'configuration', 'navigate to settings'],
        'select': ['choose', 'pick', 'navigate', 'go to'],
        'reinstall': ['re-install', 'install again', 'reset app'],
        'increase': ['grew', 'rise', 'higher', 'up', 'improved', 'growth'],
        'decrease': ['declined', 'lower', 'down', 'reduced', 'fell', 'drop'],
        'consistent': ['stable', 'steady', 'not fluctuat'],
        'improving': ['improved', 'better', 'increasing', 'grew', 'growth'],
        'government': ['defense', 'military', 'dod', 'federal', 'u.s. government'],
        'forestiere': ['forestier', 'foret', 'naturel', 'boise'],
        'ministre': ['ministeriel', 'ministere', 'autorite administrative'],
        'subrog': ['subrogation', 'subroger', 'subrogatoire'],
        'cassation': ['cour de cassation', 'pourvoi', 'arret'],
        'renvoi': ['renvoyer', 'renvoyee', 'renvoi devant'],
        'rejet': ['rejete', 'rejeter', 'pourvoi rejete'],
    }
    for key, synonyms in SYNONYMS.items():
        if key in norm_expected:
            for syn in synonyms:
                if syn in norm_answer:
                    return True

    return False


def call_webhook(pipeline, query, timeout=90, max_retries=3):
    """Call a RAG pipeline webhook endpoint with round-robin and retry."""
    webhook_path = WEBHOOK_PATHS.get(pipeline)
    if not webhook_path:
        return {"answer": "", "error": f"Unknown pipeline: {pipeline}", "latency_ms": 0}

    payload = json.dumps({
        "query": query,
        "tenant_id": "benchmark",
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True,
    }).encode()
    headers = {"Content-Type": "application/json"}

    last_err = ""
    for attempt in range(max_retries):
        endpoint = _rr_endpoint(pipeline, webhook_path)
        try:
            req = request.Request(endpoint, data=payload, headers=headers, method="POST")
            start = time.time()
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                latency = int((time.time() - start) * 1000)
                if raw and raw.strip():
                    data = json.loads(raw)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    answer = ""
                    for key in ["response", "answer", "result", "interpretation", "final_response"]:
                        if key in data and data[key]:
                            answer = str(data[key])
                            break
                    return {"answer": answer, "error": None, "latency_ms": latency}
                return {"answer": "", "error": "Empty response", "latency_ms": latency}
        except error.HTTPError as e:
            last_err = f"HTTP {e.code}: {str(e)[:150]}"
            if e.code in (429, 502, 503, 504) and attempt < max_retries - 1:
                wait = 3 * (2 ** attempt)
                time.sleep(wait)
                continue
            return {"answer": "", "error": last_err, "latency_ms": 0}
        except error.URLError as e:
            last_err = f"URL error: {str(e)[:150]}"
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return {"answer": "", "error": last_err, "latency_ms": 0}
        except Exception as e:
            last_err = str(e)[:200]
            if "timed out" in last_err.lower() and attempt < max_retries - 1:
                time.sleep(3)
                continue
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return {"answer": "", "error": last_err, "latency_ms": 0}

    return {"answer": "", "error": f"Max retries ({max_retries}). Last: {last_err}", "latency_ms": 0}


def embed_query_selfhosted(query, max_retries=3):
    """Generate embedding using self-hosted Jina v3 on HF Space with retry."""
    payload = json.dumps({
        "model": "jina-embeddings-v3",
        "input": [query],
    }).encode()
    headers = {"Content-Type": "application/json"}

    last_err = ""
    for attempt in range(max_retries):
        try:
            req = request.Request(EMBEDDINGS_URL, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                embedding = data["data"][0]["embedding"]
                return embedding, None
        except Exception as e:
            last_err = str(e)[:180]
            if "timed out" in last_err.lower() and attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            if attempt < max_retries - 1:
                time.sleep(3)
                continue

    return None, f"Self-hosted embed failed after {max_retries} retries: {last_err}"


def embed_query_jina(query):
    """Generate embedding for a query -- tries self-hosted first, then Jina API."""
    embedding, err = embed_query_selfhosted(query)
    if embedding:
        return embedding, None

    # Fallback to Jina API (likely exhausted but try)
    if not JINA_API_KEY:
        return None, f"Self-hosted failed ({err}) and JINA_API_KEY not set"

    payload = json.dumps({
        "model": "jina-embeddings-v3",
        "task": "retrieval.query",
        "dimensions": 1024,
        "input": [query],
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JINA_API_KEY}",
    }

    try:
        req = request.Request("https://api.jina.ai/v1/embeddings",
                              data=payload, headers=headers, method="POST")
        with request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            embedding = data["data"][0]["embedding"]
            return embedding, None
    except Exception as e2:
        return None, f"Both failed. Self-hosted: {err} | Jina: {str(e2)[:100]}"


def query_sector_pinecone(embedding, top_k=5):
    """Query the sector Pinecone index directly."""
    if not PINECONE_API_KEY:
        return [], "PINECONE_API_KEY not set"

    payload = json.dumps({
        "vector": embedding,
        "topK": top_k,
        "namespace": SECTOR_NAMESPACE,
        "includeMetadata": True,
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Api-Key": PINECONE_API_KEY,
    }

    try:
        req = request.Request(f"{SECTOR_INDEX_HOST}/query",
                              data=payload, headers=headers, method="POST")
        with request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            matches = data.get("matches", [])
            return matches, None
    except Exception as e:
        return [], str(e)[:200]


def generate_answer_groq(query, context_chunks, model="llama-3.3-70b-versatile"):
    """Generate an answer using LiteLLM proxy (primary) or Groq (fallback)."""
    context_parts = []
    for i, match in enumerate(context_chunks[:5]):
        meta = match.get("metadata", {})
        text = meta.get("text", "") or meta.get("content", "") or meta.get("question", "")
        answer = meta.get("answer", "")
        sector = meta.get("sector", "")
        dataset = meta.get("dataset", "")
        if text:
            chunk = f"[Source {i+1} | {sector}/{dataset}] {text[:1000]}"
            if answer:
                chunk += f"\nAnswer: {answer[:500]}"
            context_parts.append(chunk)

    if not context_parts:
        return "", "No context retrieved from Pinecone"

    context_str = "\n\n".join(context_parts)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful RAG assistant. Answer the question using ONLY "
                "the provided context. Be precise and concise. If the context does "
                "not contain the answer, say 'Information not found in context.'"
            ),
        },
        {
            "role": "user",
            "content": f"Context:\n{context_str}\n\nQuestion: {query}\n\nAnswer:",
        },
    ]

    litellm_url = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
    litellm_key = "sk-litellm-nomos-2026"

    endpoints = [
        (litellm_url, litellm_key, "default"),
        ("https://api.groq.com/openai/v1/chat/completions", GROQ_API_KEY, model),
    ]

    last_err = ""
    for ep_url, ep_key, ep_model in endpoints:
        if not ep_key:
            continue
        payload = json.dumps({
            "model": ep_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 512,
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ep_key}",
        }

        try:
            req = request.Request(ep_url, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                answer = data["choices"][0]["message"]["content"]
                return answer.strip(), None
        except Exception as e:
            last_err = str(e)[:150]
            continue

    return "", f"All LLM endpoints failed. Last: {last_err}"


def call_direct_pinecone(query, timeout=90):
    """Full direct pipeline: embed -> Pinecone query -> LLM answer."""
    start = time.time()

    embedding, err = embed_query_jina(query)
    if err:
        return {"answer": "", "error": f"Embed error: {err}", "latency_ms": 0}

    matches, err = query_sector_pinecone(embedding, top_k=5)
    if err:
        latency = int((time.time() - start) * 1000)
        return {"answer": "", "error": f"Pinecone error: {err}", "latency_ms": latency}

    if not matches:
        latency = int((time.time() - start) * 1000)
        return {"answer": "", "error": "No matches in Pinecone sectors index", "latency_ms": latency}

    answer, err = generate_answer_groq(query, matches)
    latency = int((time.time() - start) * 1000)

    if err:
        return {"answer": "", "error": f"LLM error: {err}", "latency_ms": latency}

    return {"answer": answer, "error": None, "latency_ms": latency}


def evaluate_question(question, use_direct=False, pipeline_override=None):
    """Evaluate a single question. Returns result dict."""
    qtext = question["question"]
    expected = question.get("expected_contains", "")
    pipeline = pipeline_override or question.get("pipeline", "standard")
    sector = question.get("sector", "unknown")

    if use_direct:
        resp = call_direct_pinecone(qtext)
    else:
        resp = call_webhook(pipeline, qtext)

    passed = False
    if resp["answer"] and not resp["error"]:
        if expected:
            passed = flexible_match(resp["answer"], expected)
        elif len(resp["answer"]) > 0:
            passed = True  # No expected = just check non-empty

    return {
        "id": question.get("id", ""),
        "sector": sector,
        "pipeline": pipeline,
        "question": qtext[:100],
        "expected": expected,
        "answer_preview": resp["answer"][:200] if resp["answer"] else "",
        "passed": passed,
        "error": resp["error"],
        "latency_ms": resp["latency_ms"],
        "category": question.get("category", ""),
        "dataset_source": question.get("dataset_source", ""),
    }


def run_sector_eval(questions, use_direct=False, delay_between=3,
                    all_pipelines=False, consecutive_errors_limit=10):
    """Run evaluation on all questions. Returns results grouped by sector+pipeline."""
    results_by_sector = defaultdict(list)
    results_by_pipeline = defaultdict(list)
    total = len(questions)
    consecutive_errors = 0

    pipelines_to_test = ALL_PIPELINES if all_pipelines else [None]

    for pi, pipeline_override in enumerate(pipelines_to_test):
        if all_pipelines:
            print(f"\n{'='*60}")
            print(f"  PIPELINE: {pipeline_override.upper()}")
            print(f"{'='*60}")

        for i, q in enumerate(questions):
            sector = q.get("sector", "unknown")
            pipeline = pipeline_override or q.get("pipeline", "standard")
            idx = i + 1 + (pi * total)
            total_all = total * len(pipelines_to_test)
            print(f"\n  [{idx}/{total_all}] {sector.upper()} | {pipeline} | {q['question'][:55]}...")

            result = evaluate_question(q, use_direct=use_direct,
                                       pipeline_override=pipeline_override)
            results_by_sector[sector].append(result)
            results_by_pipeline[pipeline].append(result)

            symbol = "[+]" if result["passed"] else "[-]"
            print(f"    {symbol} {result['latency_ms']}ms | ", end="")
            if result["error"]:
                print(f"ERR: {result['error'][:80]}")
                consecutive_errors += 1
            else:
                print(f"A: {result['answer_preview'][:80]}")
                consecutive_errors = 0

            # Auto-stop on too many consecutive errors
            if consecutive_errors >= consecutive_errors_limit:
                print(f"\n  AUTO-STOP: {consecutive_errors_limit} consecutive errors. Aborting.")
                return dict(results_by_sector), dict(results_by_pipeline)

            # Rate limiting between calls
            if i < total - 1 or (all_pipelines and pi < len(pipelines_to_test) - 1):
                time.sleep(delay_between)

    return dict(results_by_sector), dict(results_by_pipeline)


def print_summary(results_by_sector, results_by_pipeline, metadata=None):
    """Print evaluation summary with per-sector AND per-pipeline breakdown."""
    print("\n" + "=" * 70)
    print("  SECTOR EVALUATION SUMMARY")
    print("=" * 70)

    if metadata:
        print(f"  Dataset: {metadata.get('title', 'unknown')}")
        print(f"  Pinecone: {metadata.get('data_sources', {}).get('pinecone', 'N/A')}")

    # Per-sector summary
    total_pass = 0
    total_count = 0
    sector_summary = {}

    print("\n  --- BY SECTOR ---")
    for sector in ["finance", "btp", "juridique", "industrie"]:
        results = results_by_sector.get(sector, [])
        if not results:
            continue
        passed = sum(1 for r in results if r["passed"])
        count = len(results)
        errors = sum(1 for r in results if r["error"])
        total_pass += passed
        total_count += count
        pct = (passed / count * 100) if count > 0 else 0
        status = "PASS" if pct >= 60 else "FAIL"
        avg_latency = sum(r["latency_ms"] for r in results) / count if count > 0 else 0

        sector_summary[sector] = {
            "passed": passed, "total": count, "errors": errors,
            "accuracy": round(pct, 1), "avg_latency_ms": round(avg_latency),
            "status": status,
        }

        print(f"\n  {sector.upper():12s}: {passed}/{count} ({pct:.0f}%) {status}  | avg {avg_latency:.0f}ms | {errors} errors")
        for r in results:
            sym = "+" if r["passed"] else "-"
            err_info = f" ERR: {r['error'][:40]}" if r["error"] else ""
            print(f"    [{sym}] {r['question'][:55]}...{err_info}")

    # Per-pipeline summary
    pipeline_summary = {}
    if results_by_pipeline and len(results_by_pipeline) > 1:
        print("\n  --- BY PIPELINE ---")
        for pipeline in ALL_PIPELINES:
            results = results_by_pipeline.get(pipeline, [])
            if not results:
                continue
            passed = sum(1 for r in results if r["passed"])
            count = len(results)
            errors = sum(1 for r in results if r["error"])
            pct = (passed / count * 100) if count > 0 else 0
            avg_latency = sum(r["latency_ms"] for r in results) / count if count > 0 else 0

            pipeline_summary[pipeline] = {
                "passed": passed, "total": count, "errors": errors,
                "accuracy": round(pct, 1), "avg_latency_ms": round(avg_latency),
            }

            print(f"\n  {pipeline.upper():15s}: {passed}/{count} ({pct:.0f}%)  | avg {avg_latency:.0f}ms | {errors} errors")
    else:
        # Single pipeline mode - derive from results
        for pipeline in ALL_PIPELINES:
            results = results_by_pipeline.get(pipeline, [])
            if results:
                passed = sum(1 for r in results if r["passed"])
                count = len(results)
                errors = sum(1 for r in results if r["error"])
                pct = (passed / count * 100) if count > 0 else 0
                avg_latency = sum(r["latency_ms"] for r in results) / count if count > 0 else 0
                pipeline_summary[pipeline] = {
                    "passed": passed, "total": count, "errors": errors,
                    "accuracy": round(pct, 1), "avg_latency_ms": round(avg_latency),
                }

    # Category summary
    results_by_category = defaultdict(list)
    for sector_results in results_by_sector.values():
        for r in sector_results:
            cat = r.get("category", "unknown")
            results_by_category[cat].append(r)

    if results_by_category:
        print("\n  --- BY CATEGORY ---")
        for cat in sorted(results_by_category.keys()):
            results = results_by_category[cat]
            passed = sum(1 for r in results if r["passed"])
            count = len(results)
            pct = (passed / count * 100) if count > 0 else 0
            print(f"    {cat:25s}: {passed}/{count} ({pct:.0f}%)")

    if total_count > 0:
        overall_pct = total_pass / total_count * 100
        print(f"\n  OVERALL: {total_pass}/{total_count} ({overall_pct:.1f}%)")
    print("=" * 70)

    return total_pass, total_count, sector_summary, pipeline_summary


def save_results(results_by_sector, results_by_pipeline, metadata, mode,
                 sector_summary, pipeline_summary):
    """Save results to timestamped log AND to docs/sector-eval-results.json."""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filepath = os.path.join(RESULTS_DIR, f"sector-eval-{timestamp}.json")

    total_pass = sum(s["passed"] for s in sector_summary.values())
    total_count = sum(s["total"] for s in sector_summary.values())

    output = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "metadata": metadata,
        "overall": {
            "passed": total_pass,
            "total": total_count,
            "accuracy": round(total_pass / total_count * 100, 1) if total_count > 0 else 0,
        },
        "by_sector": sector_summary,
        "by_pipeline": pipeline_summary,
        "results_by_sector": results_by_sector,
        "results_by_pipeline": results_by_pipeline,
    }

    # Save to logs
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved: {filepath}")

    # Also save to docs/sector-eval-results.json (dashboard-friendly)
    docs_output = {
        "last_updated": datetime.now().isoformat(),
        "mode": mode,
        "overall": output["overall"],
        "by_sector": sector_summary,
        "by_pipeline": pipeline_summary,
        "dataset": metadata.get("title", "unknown"),
        "total_questions_available": metadata.get("total_questions", 0),
    }

    os.makedirs(os.path.dirname(RESULTS_DOCS), exist_ok=True)
    with open(RESULTS_DOCS, "w", encoding="utf-8") as f:
        json.dump(docs_output, f, indent=2, ensure_ascii=False)
    print(f"  Dashboard results: {RESULTS_DOCS}")

    return filepath


def check_embeddings_health():
    """Quick health check on self-hosted embeddings."""
    health_url = EMBEDDINGS_URL.replace("/v1/embeddings", "/health")
    try:
        req = request.Request(health_url, method="GET")
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return True, data
    except Exception as e:
        return False, str(e)[:100]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sector RAG Evaluation")
    parser.add_argument("--sector", type=str, default=None,
                        help="Filter to a single sector (finance, btp, juridique, industrie)")
    parser.add_argument("--questions", type=int, default=None,
                        help="Max questions per sector (e.g., 5 for smoke test)")
    parser.add_argument("--direct-pinecone", action="store_true",
                        help="Bypass webhooks, query sector Pinecone index directly")
    parser.add_argument("--webhook", action="store_true", default=True,
                        help="Use n8n webhooks (default)")
    parser.add_argument("--all-pipelines", action="store_true",
                        help="Test every question against ALL 3 pipelines")
    parser.add_argument("--pipeline", type=str, default=None,
                        help="Test a specific pipeline only (standard, graph, quantitative)")
    parser.add_argument("--dataset", type=str, default=None,
                        help="Path to sector eval dataset JSON (default: sector-full-eval.json)")
    parser.add_argument("--smoke", action="store_true",
                        help="Use smoke test dataset (20 questions)")
    parser.add_argument("--delay", type=int, default=3,
                        help="Seconds between API calls (default: 3)")
    parser.add_argument("--timeout", type=int, default=90,
                        help="Timeout per API call in seconds (default: 90)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show questions without calling APIs")
    parser.add_argument("--allow-local", action="store_true",
                        help="Allow localhost/VM n8n (for testing)")
    parser.add_argument("--webhook-override", type=str, default=None,
                        help="Override webhook path for standard pipeline")
    args = parser.parse_args()

    # Determine dataset
    dataset_path = DATASET_FILE
    if args.dataset:
        dataset_path = args.dataset
    elif args.smoke:
        dataset_path = SMOKE_DATASET

    # Apply webhook override if provided
    if args.webhook_override:
        WEBHOOK_PATHS["standard"] = args.webhook_override
        print(f"  Webhook override: standard -> {args.webhook_override}")

    # Load dataset
    questions, metadata = load_sector_dataset(
        filepath=dataset_path,
        sector_filter=args.sector,
        max_per_sector=args.questions,
    )

    if not questions:
        print("ERROR: No questions loaded. Check dataset file.")
        sys.exit(1)

    # If --pipeline is set, override all questions to use that pipeline
    if args.pipeline:
        if args.pipeline not in WEBHOOK_PATHS:
            print(f"ERROR: Unknown pipeline '{args.pipeline}'. Use: {', '.join(WEBHOOK_PATHS.keys())}")
            sys.exit(1)
        for q in questions:
            q["pipeline"] = args.pipeline

    mode = "direct-pinecone" if args.direct_pinecone else "webhook"
    if args.all_pipelines:
        mode = "all-pipelines"

    # Header
    print("=" * 70)
    print("  SECTOR RAG EVALUATION")
    print(f"  Mode: {mode}")
    print(f"  Dataset: {os.path.basename(dataset_path)}")
    print(f"  Questions: {len(questions)}", end="")
    if args.all_pipelines:
        print(f" x {len(ALL_PIPELINES)} pipelines = {len(questions) * len(ALL_PIPELINES)} total")
    else:
        print()
    if args.sector:
        print(f"  Sector filter: {args.sector}")
    if args.pipeline:
        print(f"  Pipeline override: {args.pipeline}")
    print(f"  N8N Host: {N8N_HOST}")
    print(f"  Hosts available: {len(N8N_ALL_HOSTS)} (round-robin)")

    # Check embeddings health if using direct pinecone
    if args.direct_pinecone:
        print(f"  Pinecone: {SECTOR_INDEX_HOST}")
        print(f"  Namespace: {SECTOR_NAMESPACE}")
        healthy, info = check_embeddings_health()
        print(f"  Embeddings: {'UP' if healthy else 'DOWN'} ({info})")
        if not healthy:
            print("  WARNING: Self-hosted embeddings are DOWN. Direct Pinecone mode may fail.")
    print("=" * 70)

    if args.dry_run:
        print("\n  DRY RUN -- listing questions only:\n")
        by_sector = defaultdict(list)
        for q in questions:
            by_sector[q["sector"]].append(q)
        for sector in ["finance", "btp", "juridique", "industrie"]:
            qs = by_sector.get(sector, [])
            if qs:
                print(f"\n  === {sector.upper()} ({len(qs)} questions) ===")
                for q in qs:
                    print(f"    [{q['id']}] {q['question'][:70]}")
                    print(f"             expected: {q.get('expected_contains', 'N/A')} | cat: {q.get('category', '')}")
        print(f"\n  Total: {len(questions)} questions")
        return

    # Run evaluation
    results_by_sector, results_by_pipeline = run_sector_eval(
        questions,
        use_direct=args.direct_pinecone,
        delay_between=args.delay,
        all_pipelines=args.all_pipelines,
    )

    # Print summary
    total_pass, total_count, sector_summary, pipeline_summary = print_summary(
        results_by_sector, results_by_pipeline, metadata
    )

    # Save results
    save_results(results_by_sector, results_by_pipeline, metadata, mode,
                 sector_summary, pipeline_summary)

    # Exit code
    if total_count > 0 and total_pass / total_count < 0.5:
        sys.exit(1)


if __name__ == "__main__":
    main()
