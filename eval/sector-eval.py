#!/usr/bin/env python3
"""
Sector RAG Evaluation — Tests RAG pipelines against sector-specific data.

Evaluates 4 ETI sectors (Finance, BTP, Juridique, Industrie) using data
ingested in:
  - Pinecone: website-sectors-jina-1024 (31,916 vectors, namespace: sectors)
  - Supabase: sector_documents (11,387 rows)
  - Neo4j: SectorDocument nodes (7,509)

IMPORTANT: The standard/graph/quant pipelines currently point to the
benchmark Pinecone index (sota-rag-jina-1024), NOT the sectors index.
This script supports two modes:

  1. --direct-pinecone: Bypasses n8n webhooks entirely, queries the sector
     Pinecone index directly + uses Groq LLM for answer generation.
     (Works NOW, does not require pipeline reconfiguration.)

  2. --webhook (default): Calls the standard n8n webhook. Will only work
     once pipelines are reconfigured to support an index_name or
     namespace parameter. Until then, results reflect benchmark index
     retrieval (expected low accuracy on sector questions).

Usage:
  source .env.local
  python3 eval/sector-eval.py                          # Webhook mode (all sectors)
  python3 eval/sector-eval.py --sector finance         # Single sector
  python3 eval/sector-eval.py --direct-pinecone        # Direct Pinecone query
  python3 eval/sector-eval.py --questions 3            # Limit questions per sector
  python3 eval/sector-eval.py --dry-run                # Show questions, no calls
"""

import json
import os
import sys
import time
from datetime import datetime
from urllib import request, error
from collections import defaultdict

# ─── Paths ────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FILE = os.path.join(REPO_ROOT, "datasets", "sector-eval", "sector-smoke-test.json")
RESULTS_DIR = os.path.join(REPO_ROOT, "logs", "sector-eval")

# ─── Environment ──────────────────────────────────────────────────────────
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
JINA_API_KEY = os.environ.get("JINA_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Sector Pinecone index host
SECTOR_INDEX_HOST = "https://website-sectors-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
SECTOR_NAMESPACE = "sectors"

# Guard: block VM n8n for evals
import re as _re
if _re.search(r'localhost|127\.0\.0\.1|34\.136\.180\.66', N8N_HOST):
    if "--allow-local" not in sys.argv:
        print(f"FATAL: N8N_HOST points to local/VM ({N8N_HOST}).")
        print("Set N8N_HOST to HF Space or pass --allow-local.")
        sys.exit(1)

# ─── Webhook paths (same as quick-test.py) ────────────────────────────────
WEBHOOK_PATHS = {
    "standard":     "/webhook/rag-multi-index-v3",
    "graph":        "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
}

# Sector → recommended pipeline mapping
SECTOR_PIPELINE = {
    "finance": "standard",
    "btp": "standard",
    "juridique": "standard",
    "industrie": "standard",
}


def load_sector_dataset(filepath=DATASET_FILE, sector_filter=None, max_per_sector=None):
    """Load sector eval questions from JSON dataset file."""
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
    normalized = _re.sub(r'(\d),(\d)', r'\1\2', text)
    normalized = normalized.replace('$', '').replace('%', '').replace('\u20ac', '')
    # Normalize unit expressions: "2 meters" -> "2m", "180 millimetres" -> "180mm"
    normalized = _re.sub(r'(\d+)\s*(meter|metre|meters|metres)', r'\1m', normalized)
    normalized = _re.sub(r'(\d+)\s*(millimeter|millimetre|millimeters|millimetres)', r'\1mm', normalized)
    return normalized.lower()


def call_webhook(pipeline, query, timeout=90, max_retries=2):
    """Call a RAG pipeline webhook endpoint."""
    webhook_path = WEBHOOK_PATHS.get(pipeline)
    if not webhook_path:
        return {"answer": "", "error": f"Unknown pipeline: {pipeline}", "latency_ms": 0}

    endpoint = f"{N8N_HOST}{webhook_path}"
    payload = json.dumps({
        "query": query,
        "tenant_id": "benchmark",
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True,
    }).encode()
    headers = {"Content-Type": "application/json"}

    for attempt in range(max_retries):
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
            if e.code in (429, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(3 * (2 ** attempt))
                continue
            return {"answer": "", "error": f"HTTP {e.code}: {str(e)[:150]}", "latency_ms": 0}
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return {"answer": "", "error": str(e)[:200], "latency_ms": 0}

    return {"answer": "", "error": "Max retries exceeded", "latency_ms": 0}


def embed_query_selfhosted(query):
    """Generate embedding using self-hosted Jina v3 on HF Space (primary)."""
    selfhosted_url = os.environ.get(
        "EMBEDDINGS_URL",
        "https://lbjlincoln-nomos-embeddings-api.hf.space/v1/embeddings"
    )
    payload = json.dumps({
        "model": "jina-embeddings-v3",
        "input": [query],
    }).encode()
    headers = {"Content-Type": "application/json"}

    try:
        req = request.Request(selfhosted_url, data=payload, headers=headers, method="POST")
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            embedding = data["data"][0]["embedding"]
            return embedding, None
    except Exception as e:
        return None, f"Self-hosted embed error: {str(e)[:180]}"


def embed_query_jina(query):
    """Generate embedding for a query — tries self-hosted first, then Jina API."""
    # Try self-hosted first (Jina keys exhausted)
    embedding, err = embed_query_selfhosted(query)
    if embedding:
        return embedding, None

    # Fallback to Jina API
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
    # Build context from Pinecone matches
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

    # Try LiteLLM proxy first (Groq API key may be exhausted)
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
    """Full direct pipeline: Jina embed -> Pinecone query -> Groq answer."""
    start = time.time()

    # Step 1: Embed query
    embedding, err = embed_query_jina(query)
    if err:
        return {"answer": "", "error": f"Embed error: {err}", "latency_ms": 0}

    # Step 2: Query Pinecone sectors index
    matches, err = query_sector_pinecone(embedding, top_k=5)
    if err:
        latency = int((time.time() - start) * 1000)
        return {"answer": "", "error": f"Pinecone error: {err}", "latency_ms": latency}

    if not matches:
        latency = int((time.time() - start) * 1000)
        return {"answer": "", "error": "No matches in Pinecone sectors index", "latency_ms": latency}

    # Step 3: Generate answer with Groq
    answer, err = generate_answer_groq(query, matches)
    latency = int((time.time() - start) * 1000)

    if err:
        return {"answer": "", "error": f"LLM error: {err}", "latency_ms": latency}

    return {"answer": answer, "error": None, "latency_ms": latency}


def evaluate_question(question, use_direct=False):
    """Evaluate a single question. Returns result dict."""
    qtext = question["question"]
    expected = question.get("expected_contains", "")
    pipeline = question.get("pipeline", "standard")
    sector = question.get("sector", "unknown")

    if use_direct:
        resp = call_direct_pinecone(qtext)
    else:
        resp = call_webhook(pipeline, qtext)

    passed = False
    if resp["answer"] and not resp["error"]:
        if expected:
            norm_answer = normalize_for_match(resp["answer"])
            norm_expected = normalize_for_match(expected)
            if norm_expected in norm_answer:
                passed = True
        elif len(resp["answer"]) > 0:
            passed = True  # No expected = just check non-empty

    return {
        "id": question.get("id", ""),
        "sector": sector,
        "pipeline": pipeline,
        "question": qtext[:80],
        "expected": expected,
        "answer_preview": resp["answer"][:150] if resp["answer"] else "",
        "passed": passed,
        "error": resp["error"],
        "latency_ms": resp["latency_ms"],
    }


def run_sector_eval(questions, use_direct=False, delay_between=3):
    """Run evaluation on all questions. Returns results grouped by sector."""
    results_by_sector = defaultdict(list)
    total = len(questions)

    for i, q in enumerate(questions):
        sector = q.get("sector", "unknown")
        print(f"\n  [{i+1}/{total}] {sector.upper()} | {q['question'][:65]}...")

        result = evaluate_question(q, use_direct=use_direct)
        results_by_sector[sector].append(result)

        symbol = "[+]" if result["passed"] else "[-]"
        print(f"    {symbol} {result['latency_ms']}ms | ", end="")
        if result["error"]:
            print(f"ERR: {result['error'][:80]}")
        else:
            print(f"A: {result['answer_preview'][:80]}")

        # Rate limiting between calls
        if i < total - 1:
            time.sleep(delay_between)

    return dict(results_by_sector)


def print_summary(results_by_sector, metadata=None):
    """Print evaluation summary."""
    print("\n" + "=" * 60)
    print("  SECTOR EVALUATION SUMMARY")
    print("=" * 60)

    if metadata:
        print(f"  Dataset: {metadata.get('title', 'unknown')}")
        print(f"  Pinecone: {metadata.get('data_sources', {}).get('pinecone', 'N/A')}")

    total_pass = 0
    total_count = 0

    for sector in ["finance", "btp", "juridique", "industrie"]:
        results = results_by_sector.get(sector, [])
        if not results:
            continue
        passed = sum(1 for r in results if r["passed"])
        count = len(results)
        total_pass += passed
        total_count += count
        pct = (passed / count * 100) if count > 0 else 0
        status = "PASS" if pct >= 60 else "FAIL"
        avg_latency = sum(r["latency_ms"] for r in results) / count if count > 0 else 0

        print(f"\n  {sector.upper():12s}: {passed}/{count} ({pct:.0f}%) {status}  | avg {avg_latency:.0f}ms")
        for r in results:
            sym = "+" if r["passed"] else "-"
            err_info = f" ERR: {r['error'][:40]}" if r["error"] else ""
            print(f"    [{sym}] {r['question'][:55]}...{err_info}")

    if total_count > 0:
        overall_pct = total_pass / total_count * 100
        print(f"\n  OVERALL: {total_pass}/{total_count} ({overall_pct:.1f}%)")
    print("=" * 60)

    return total_pass, total_count


def save_results(results_by_sector, metadata, mode):
    """Save results to JSON file."""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filepath = os.path.join(RESULTS_DIR, f"sector-eval-{timestamp}.json")

    output = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "metadata": metadata,
        "results_by_sector": results_by_sector,
        "summary": {},
    }

    for sector, results in results_by_sector.items():
        passed = sum(1 for r in results if r["passed"])
        count = len(results)
        output["summary"][sector] = {
            "passed": passed,
            "total": count,
            "accuracy": round(passed / count * 100, 1) if count > 0 else 0,
        }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  Results saved: {filepath}")
    return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sector RAG Evaluation")
    parser.add_argument("--sector", type=str, default=None,
                        help="Filter to a single sector (finance, btp, juridique, industrie)")
    parser.add_argument("--questions", type=int, default=None,
                        help="Max questions per sector")
    parser.add_argument("--direct-pinecone", action="store_true",
                        help="Bypass webhooks, query sector Pinecone index directly")
    parser.add_argument("--dataset", type=str, default=DATASET_FILE,
                        help="Path to sector eval dataset JSON")
    parser.add_argument("--delay", type=int, default=3,
                        help="Seconds between API calls (default: 3)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show questions without calling APIs")
    parser.add_argument("--allow-local", action="store_true",
                        help="Allow localhost/VM n8n (for testing)")
    parser.add_argument("--webhook-override", type=str, default=None,
                        help="Override webhook path for standard pipeline (e.g. /webhook/website-standard-v3)")
    args = parser.parse_args()

    # Apply webhook override if provided
    if args.webhook_override:
        WEBHOOK_PATHS["standard"] = args.webhook_override
        print(f"  Webhook override: standard -> {args.webhook_override}")

    # Load dataset
    questions, metadata = load_sector_dataset(
        filepath=args.dataset,
        sector_filter=args.sector,
        max_per_sector=args.questions,
    )

    if not questions:
        print("ERROR: No questions loaded. Check dataset file.")
        sys.exit(1)

    mode = "direct-pinecone" if args.direct_pinecone else "webhook"

    print("=" * 60)
    print("  SECTOR RAG EVALUATION")
    print(f"  Mode: {mode}")
    print(f"  Questions: {len(questions)}")
    if args.sector:
        print(f"  Sector filter: {args.sector}")
    print(f"  N8N Host: {N8N_HOST}")
    if args.direct_pinecone:
        print(f"  Pinecone: {SECTOR_INDEX_HOST}")
        print(f"  Namespace: {SECTOR_NAMESPACE}")
        has_keys = all([PINECONE_API_KEY, JINA_API_KEY, GROQ_API_KEY])
        print(f"  API Keys: {'ALL SET' if has_keys else 'MISSING (source .env.local)'}")
    print("=" * 60)

    if args.dry_run:
        print("\n  DRY RUN — listing questions only:\n")
        for q in questions:
            print(f"  [{q['id']}] {q['sector'].upper()} | {q['question'][:70]}")
            print(f"         expected_contains: {q.get('expected_contains', 'N/A')}")
        print(f"\n  Total: {len(questions)} questions")
        return

    # Run evaluation
    results = run_sector_eval(questions, use_direct=args.direct_pinecone, delay_between=args.delay)

    # Print summary
    total_pass, total_count = print_summary(results, metadata)

    # Save results
    save_results(results, metadata, mode)

    # Exit code
    if total_count > 0 and total_pass / total_count < 0.5:
        sys.exit(1)


if __name__ == "__main__":
    main()
