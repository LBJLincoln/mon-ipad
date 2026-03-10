#!/usr/bin/env python3
"""
Turbo Evaluation — 4-10x faster than sequential expert-eval.py
================================================================
Distributes questions across 4 HF Spaces in parallel, with per-worker
Groq key + model rotation for the LLM judge.

Architecture:
  - 4 workers (1 per HF Space) running in parallel via ThreadPoolExecutor
  - Each worker: sends question to its Space, then judges via its own Groq key+model
  - Graph pipeline only goes to S1 (the only Space with Graph webhook)
  - Streaming output: progress.json + expert-results-live.json after each question
  - Output format identical to expert-eval.py for comparison

Expected speed: 4x parallel → ~8-10s/question → 208 in ~35 min (was ~2h)

Usage:
  source .env.local
  python3 eval/turbo-eval.py --sample 20                   # Quick 20-question sample
  python3 eval/turbo-eval.py --full                        # All 208+ questions
  python3 eval/turbo-eval.py --sector finance --sample 10  # Finance only
  python3 eval/turbo-eval.py --workers 2 --sample 5        # Reduced parallelism
  python3 eval/turbo-eval.py --pipelines standard,graph    # Multi-pipeline
  python3 eval/turbo-eval.py --report                      # Show latest results
"""

import json
import os
import sys
import time
import random
import argparse
import re
import socket
import requests
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Event

# ─── Force IPv4 globally ──────────────────────────────────────────────────
_orig_getaddrinfo = socket.getaddrinfo

def _ipv4_getaddrinfo(*args, **kwargs):
    responses = _orig_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET] or responses

socket.getaddrinfo = _ipv4_getaddrinfo

# ─── Paths ────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "eval")
os.makedirs(DATA_DIR, exist_ok=True)

PROGRESS_FILE = os.path.join(DATA_DIR, "progress.json")
LIVE_RESULTS_FILE = os.path.join(DATA_DIR, "expert-results-live.json")
SECTOR_SCORES_FILE = os.path.join(DATA_DIR, "sector-scores.json")
RESULTS_FILE = os.path.join(DATA_DIR, "expert-results.json")

# ─── Spaces ───────────────────────────────────────────────────────────────
SPACES = [
    "https://lbjlincoln-nomos-rag-engine.hf.space",     # S1
    "https://lbjlincoln-nomos-rag-engine-3.hf.space",   # S3
    "https://lbjlincoln-nomos-rag-engine-5.hf.space",   # S5
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",   # S9
]

WEBHOOK_PATHS = {
    "standard":     "/webhook/rag-multi-index-v3",
    "graph":        "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

# Graph webhook only on S1
GRAPH_SPACE = SPACES[0]

# ─── LLM Judge config ────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

_GROQ_KEYS = [v for k, v in sorted(os.environ.items())
              if k.startswith("GROQ_API_KEY") and v]
if not _GROQ_KEYS:
    _GROQ_KEYS = [os.environ.get("GROQ_API_KEY", "")]
_GROQ_KEYS = [k for k in _GROQ_KEYS if k]

# Models to cycle through for judge — different models per worker
# to spread rate limits across model+key combos
GROQ_JUDGE_MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]

# ─── Global thread-safe state ────────────────────────────────────────────
_results_lock = Lock()
_print_lock = Lock()
_all_results = []
_completed_count = 0
_error_count = 0
_eval_start = 0.0
_total_questions = 0
_judge_backends = defaultdict(int)


# =========================================================================
#  QUESTION BANK — imported from expert-eval.py
# =========================================================================

# We import the question bank directly to keep a single source of truth
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from importlib.machinery import SourceFileLoader
    _expert_mod = SourceFileLoader(
        "expert_eval",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "expert-eval.py")
    ).load_module()
    EXPERT_QUESTIONS = _expert_mod.EXPERT_QUESTIONS
    ADVERSARIAL_QUESTIONS = _expert_mod.ADVERSARIAL_QUESTIONS
except Exception as e:
    print(f"WARNING: Could not import question bank from expert-eval.py: {e}")
    print("  Falling back to empty question bank — provide questions via --questions-file")
    EXPERT_QUESTIONS = {}
    ADVERSARIAL_QUESTIONS = []


# =========================================================================
#  LLM JUDGE — identical scoring to expert-eval.py
# =========================================================================

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for a French sector-specific AI assistant.
You evaluate answers on 5 criteria, each scored 1-5:

1. **factual_accuracy** (1-5): Is the information factually correct based on the provided sources?
   1=completely wrong, 2=mostly wrong, 3=partially correct, 4=mostly correct, 5=fully correct

2. **source_citation** (1-5): Does the answer cite specific documents, articles, or data sources?
   1=no citations, 2=vague references, 3=some citations, 4=good citations, 5=precise source references

3. **expert_terminology** (1-5): Does the answer use correct professional/technical terminology?
   1=layman language, 2=some terms, 3=adequate, 4=professional, 5=expert-level terminology

4. **completeness** (1-5): Is the answer thorough enough for a professional?
   1=empty/trivial, 2=superficial, 3=adequate, 4=thorough, 5=comprehensive expert answer

5. **language_match** (1-5): Does the response match the question's language?
   1=wrong language, 3=mixed, 5=perfect language match

Respond ONLY with valid JSON in this exact format:
{"factual_accuracy": N, "source_citation": N, "expert_terminology": N, "completeness": N, "language_match": N, "reasoning": "brief explanation"}"""


def _build_judge_prompt(question, answer, sources, sector, category):
    """Build the user prompt for the LLM judge (identical to expert-eval.py)."""
    sources_text = ""
    if sources:
        for i, s in enumerate(sources[:5]):
            text = s.get("text", "") or s.get("content", "")
            src_name = s.get("source", s.get("id", f"source-{i+1}"))
            if text:
                sources_text += f"\n[Source {i+1}: {src_name}] {text[:400]}"

    return f"""Sector: {sector}
Category: {category}

QUESTION: {question}

RAG ANSWER: {answer[:1500] if answer else "(empty)"}

RETRIEVED SOURCES: {sources_text if sources_text else "(none)"}

Score this answer on the 5 criteria (1-5 each). Respond with JSON only."""


def _parse_judge_response(content):
    """Parse JSON from LLM judge response, handling markdown and think tags."""
    content = content.strip()
    # Strip <think> tags (qwen)
    if content.startswith("<think>"):
        idx = content.find("</think>")
        if idx > 0:
            content = content[idx + 8:].strip()
    # Strip markdown code block
    if "```" in content:
        parts = content.split("```")
        for part in parts[1:]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    # Find first { and last }
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _validate_scores(scores):
    """Validate that all 5 criteria are present with 1-5 range."""
    if not isinstance(scores, dict):
        return False
    for key in ["factual_accuracy", "source_citation", "expert_terminology",
                "completeness", "language_match"]:
        val = scores.get(key)
        if not isinstance(val, (int, float)) or val < 1 or val > 5:
            return False
    return True


class WorkerJudge:
    """Per-worker judge that uses its own Groq key + model rotation.
    Falls back to OpenAI/Gemini if all Groq attempts fail."""

    def __init__(self, worker_id, groq_key, model_start_idx=0):
        self.worker_id = worker_id
        self.groq_key = groq_key
        self.model_idx = model_start_idx
        self._call_count = 0

    def _next_model(self):
        """Cycle through Groq models round-robin."""
        model = GROQ_JUDGE_MODELS[self.model_idx % len(GROQ_JUDGE_MODELS)]
        self.model_idx += 1
        return model

    def _call_groq(self, system_prompt, user_prompt, max_retries=3):
        """Call Groq with this worker's key, rotating models on failure."""
        last_err = None
        for attempt in range(max_retries):
            model = self._next_model()
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.0,
                        "max_tokens": 300,
                    },
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    parsed = _parse_judge_response(content)
                    if parsed and _validate_scores(parsed):
                        return parsed, None
                    last_err = f"Groq parse error ({model}): {content[:100]}"
                    continue
                elif r.status_code == 429:
                    last_err = f"Groq 429 ({model})"
                    time.sleep(1.0 + attempt * 0.5)
                    continue
                else:
                    last_err = f"Groq HTTP {r.status_code} ({model}): {r.text[:100]}"
                    continue
            except Exception as e:
                last_err = f"Groq error ({model}): {str(e)[:100]}"
                time.sleep(0.5)
        return None, last_err

    def _call_groq_all_keys(self, system_prompt, user_prompt):
        """Try all Groq keys with model rotation as last resort."""
        for key_idx, key in enumerate(_GROQ_KEYS):
            if key == self.groq_key:
                continue  # Already tried
            for model_attempt in range(2):
                model = GROQ_JUDGE_MODELS[(self.model_idx + key_idx + model_attempt) % len(GROQ_JUDGE_MODELS)]
                try:
                    r = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": 0.0,
                            "max_tokens": 300,
                        },
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                        timeout=30,
                    )
                    if r.status_code == 200:
                        content = r.json()["choices"][0]["message"]["content"]
                        parsed = _parse_judge_response(content)
                        if parsed and _validate_scores(parsed):
                            return parsed, None
                except Exception:
                    pass
                time.sleep(0.3)
        return None, "All Groq keys exhausted"

    def _call_openai(self, system_prompt, user_prompt):
        """Fallback: OpenAI judge."""
        if not OPENAI_API_KEY:
            return None, "No OPENAI_API_KEY"
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 300,
                },
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=45,
            )
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                return _parse_judge_response(content), None
            return None, f"OpenAI HTTP {r.status_code}"
        except Exception as e:
            return None, f"OpenAI error: {str(e)[:100]}"

    def _call_gemini(self, system_prompt, user_prompt):
        """Fallback: Gemini judge."""
        if not GOOGLE_API_KEY:
            return None, "No GOOGLE_API_KEY"
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GOOGLE_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 300},
                },
                headers={"Content-Type": "application/json"},
                timeout=45,
            )
            if r.status_code == 200:
                data = r.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                return _parse_judge_response(content), None
            return None, f"Gemini HTTP {r.status_code}"
        except Exception as e:
            return None, f"Gemini error: {str(e)[:100]}"

    def judge(self, question, answer, sources, sector, category):
        """Score a RAG answer. Priority: Groq (own key) > Groq (all keys) > OpenAI > Gemini."""
        user_prompt = _build_judge_prompt(question, answer, sources, sector, category)
        self._call_count += 1

        # 1. Try own Groq key with model rotation
        scores, err = self._call_groq(JUDGE_SYSTEM_PROMPT, user_prompt)
        if scores:
            scores["judge_backend"] = "groq"
            return scores

        # 2. Try all other Groq keys
        scores, err = self._call_groq_all_keys(JUDGE_SYSTEM_PROMPT, user_prompt)
        if scores:
            scores["judge_backend"] = "groq"
            return scores

        # 3. Fallback to OpenAI (use mini to reduce 429s)
        scores, err = self._call_openai(JUDGE_SYSTEM_PROMPT, user_prompt)
        if scores and _validate_scores(scores):
            scores["judge_backend"] = "openai"
            return scores

        # 4. Fallback to Gemini
        scores, err = self._call_gemini(JUDGE_SYSTEM_PROMPT, user_prompt)
        if scores and _validate_scores(scores):
            scores["judge_backend"] = "gemini"
            return scores

        # All backends failed
        return {
            "factual_accuracy": 0, "source_citation": 0, "expert_terminology": 0,
            "completeness": 0, "language_match": 0,
            "reasoning": "All judge backends failed", "judge_backend": "none",
        }


# =========================================================================
#  RAG QUERY
# =========================================================================

def call_webhook(space_url, pipeline, query, timeout=90):
    """Call n8n webhook on a specific Space."""
    webhook_path = WEBHOOK_PATHS.get(pipeline)
    if not webhook_path:
        return {"answer": "", "sources": [], "error": f"Unknown pipeline: {pipeline}", "latency_ms": 0}

    payload = {
        "query": query,
        "tenant_id": "benchmark",
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True,
    }
    endpoint = f"{space_url}{webhook_path}"
    try:
        start = time.time()
        r = requests.post(endpoint, json=payload, timeout=timeout)
        latency = int((time.time() - start) * 1000)
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            if isinstance(data, list):
                data = data[0] if data else {}
            answer = ""
            for key in ["response", "answer", "result", "interpretation", "final_response"]:
                if key in data and data[key]:
                    answer = str(data[key])
                    break
            return {"answer": answer, "sources": data.get("sources", []), "error": None, "latency_ms": latency}
        return {"answer": "", "sources": [], "error": f"HTTP {r.status_code}", "latency_ms": latency}
    except requests.exceptions.Timeout:
        return {"answer": "", "sources": [], "error": "Timeout", "latency_ms": timeout * 1000}
    except Exception as e:
        return {"answer": "", "sources": [], "error": str(e)[:200], "latency_ms": 0}


# =========================================================================
#  STREAMING OUTPUT
# =========================================================================

def _write_progress(current, total, sector, last_score, errors, elapsed_s=0):
    """Write progress.json for external monitoring."""
    eta_s = 0
    if current > 0 and elapsed_s > 0:
        eta_s = (elapsed_s / current) * (total - current)
    progress = {
        "current": current,
        "total": total,
        "sector": sector,
        "last_score": round(last_score, 2) if last_score else None,
        "errors": errors,
        "pct": round(current / total * 100, 1) if total > 0 else 0,
        "elapsed_s": round(elapsed_s, 1),
        "eta_s": round(eta_s, 1),
        "mode": "turbo",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _write_live_results(results):
    """Write expert-results-live.json for real-time monitoring."""
    sector_agg = defaultdict(lambda: {
        "count": 0, "errors": 0,
        "factual_accuracy": [], "source_citation": [], "expert_terminology": [],
        "completeness": [], "language_match": [],
    })
    for r in results:
        s = r.get("sector", "unknown")
        sector_agg[s]["count"] += 1
        if r.get("error"):
            sector_agg[s]["errors"] += 1
        if r.get("scores"):
            for key in ["factual_accuracy", "source_citation", "expert_terminology",
                        "completeness", "language_match"]:
                val = r["scores"].get(key, 0)
                if val > 0:
                    sector_agg[s][key].append(val)

    sector_summary = {}
    for s, sd in sector_agg.items():
        scores = {}
        for key in ["factual_accuracy", "source_citation", "expert_terminology",
                    "completeness", "language_match"]:
            vals = sd[key]
            scores[key] = round(sum(vals) / len(vals), 2) if vals else 0
        overall_vals = [v for v in scores.values() if v > 0]
        scores["overall"] = round(sum(overall_vals) / len(overall_vals), 2) if overall_vals else 0
        sector_summary[s] = {"count": sd["count"], "errors": sd["errors"], "scores": scores}

    live_output = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_questions": len(results),
        "mode": "turbo",
        "sector_summary": sector_summary,
        "results": results,
    }
    try:
        with open(LIVE_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(live_output, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _result_avg_score(result):
    """Compute the average score from a result dict."""
    scores = result.get("scores")
    if not scores:
        return None
    vals = [scores.get(k, 0) for k in
            ["factual_accuracy", "source_citation", "expert_terminology",
             "completeness", "language_match"]]
    non_zero = [v for v in vals if v > 0]
    return sum(non_zero) / len(non_zero) if non_zero else 0.0


# =========================================================================
#  WORKER — processes a queue of questions
# =========================================================================

def process_question(question_data, space_url, pipeline, judge, delay, question_idx):
    """Process a single question: query RAG on assigned Space, then judge.
    Returns the result dict."""
    global _completed_count, _error_count

    qtext = question_data["question"]
    sector = question_data.get("sector", "unknown")
    category = question_data.get("category", "factual")
    qid = question_data.get("id", "unknown")

    q_start = time.time()

    # Query RAG
    resp = call_webhook(space_url, pipeline, qtext)

    if resp["error"]:
        with _results_lock:
            _error_count += 1
        result = {
            "id": qid,
            "question": qtext,
            "sector": sector,
            "category": category,
            "difficulty": question_data.get("difficulty", "medium"),
            "language": question_data.get("language", "fr"),
            "pipeline": pipeline,
            "space": space_url.split("//")[1].split(".")[0],
            "answer": "",
            "sources": [],
            "error": resp["error"],
            "latency_ms": resp["latency_ms"],
            "scores": None,
        }
    else:
        # Judge the answer
        scores = judge.judge(qtext, resp["answer"], resp.get("sources", []), sector, category)

        result = {
            "id": qid,
            "question": qtext,
            "sector": sector,
            "category": category,
            "difficulty": question_data.get("difficulty", "medium"),
            "language": question_data.get("language", "fr"),
            "pipeline": pipeline,
            "space": space_url.split("//")[1].split(".")[0],
            "answer": resp["answer"][:500],
            "sources": resp.get("sources", [])[:3],
            "error": None,
            "latency_ms": resp["latency_ms"],
            "scores": scores,
        }

    q_elapsed = time.time() - q_start

    # Thread-safe result collection + streaming output
    with _results_lock:
        _completed_count += 1
        _all_results.append(result)
        current = _completed_count
        total_elapsed = time.time() - _eval_start

        # Update streaming files
        _write_progress(
            current=current,
            total=_total_questions,
            sector=sector,
            last_score=_result_avg_score(result),
            errors=_error_count,
            elapsed_s=total_elapsed,
        )
        _write_live_results(_all_results)

        if result.get("scores"):
            backend = result["scores"].get("judge_backend", "none")
            _judge_backends[backend] += 1

    # Print one-liner
    avg = _result_avg_score(result)
    space_tag = space_url.split("//")[1].split(".")[0].replace("lbjlincoln-nomos-rag-", "")
    with _print_lock:
        if result["error"]:
            print(f"[{current}/{_total_questions}] {space_tag} | {sector} | ERR: {result['error'][:50]} | {q_elapsed:.1f}s",
                  flush=True)
        else:
            scores = result["scores"] or {}
            print(f"[{current}/{_total_questions}] {space_tag} | {sector} | "
                  f"score={avg:.1f} | {q_elapsed:.1f}s | "
                  f"f={scores.get('factual_accuracy',0)} c={scores.get('source_citation',0)} "
                  f"t={scores.get('expert_terminology',0)} k={scores.get('completeness',0)} "
                  f"l={scores.get('language_match',0)} | {scores.get('judge_backend','?')}",
                  flush=True)

    # Per-worker delay between questions
    if delay > 0:
        time.sleep(delay)

    return result


# =========================================================================
#  MULTI-PIPELINE — test Standard + Graph in parallel
# =========================================================================

def build_task_queue(questions, pipelines, num_workers):
    """Build a list of (question, space_url, pipeline) tasks.

    Standard questions are distributed round-robin across all Spaces.
    Graph questions go only to S1.
    """
    tasks = []
    standard_idx = 0

    for pipeline in pipelines:
        for q in questions:
            if pipeline == "graph":
                # Graph only on S1
                tasks.append((q, GRAPH_SPACE, pipeline))
            else:
                # Round-robin across available spaces
                space = SPACES[standard_idx % min(num_workers, len(SPACES))]
                standard_idx += 1
                tasks.append((q, space, pipeline))

    return tasks


# =========================================================================
#  QUESTION SELECTION
# =========================================================================

def select_questions(sector=None, sample=None, full=False):
    """Select questions based on filters."""
    questions = []
    sectors = [sector] if sector else ["finance", "btp", "juridique", "industrie"]

    for s in sectors:
        qs = EXPERT_QUESTIONS.get(s, [])
        for q in qs:
            q["sector"] = s
        questions.extend(qs)

    if not full and sample:
        if sample < len(questions):
            questions = random.sample(questions, sample)

    return questions


# =========================================================================
#  RESULTS AGGREGATION — identical to expert-eval.py
# =========================================================================

def compute_sector_scores(results):
    """Aggregate scores per sector across 5 criteria."""
    sector_data = defaultdict(lambda: {
        "count": 0, "errors": 0, "total_latency": 0,
        "factual_accuracy": [], "source_citation": [], "expert_terminology": [],
        "completeness": [], "language_match": [],
    })

    for r in results:
        sector = r.get("sector", "unknown")
        sd = sector_data[sector]
        sd["count"] += 1
        sd["total_latency"] += r.get("latency_ms", 0)
        if r.get("error"):
            sd["errors"] += 1
        if r.get("scores"):
            for key in ["factual_accuracy", "source_citation", "expert_terminology",
                        "completeness", "language_match"]:
                val = r["scores"].get(key, 0)
                if val > 0:
                    sd[key].append(val)

    output = {}
    for sector, sd in sector_data.items():
        count = sd["count"]
        scores = {}
        for key in ["factual_accuracy", "source_citation", "expert_terminology",
                    "completeness", "language_match"]:
            vals = sd[key]
            scores[key] = round(sum(vals) / len(vals), 2) if vals else 0
        overall = [v for v in scores.values() if v > 0]
        scores["overall"] = round(sum(overall) / len(overall), 2) if overall else 0

        output[sector] = {
            "count": count,
            "errors": sd["errors"],
            "avg_latency_ms": round(sd["total_latency"] / count) if count else 0,
            "scores": scores,
        }
    return output


def compute_pipeline_scores(results):
    """Aggregate scores per pipeline."""
    pipe_data = defaultdict(lambda: {"count": 0, "errors": 0, "scores_sum": defaultdict(float), "scores_count": defaultdict(int)})
    for r in results:
        pipe = r.get("pipeline", "unknown")
        pipe_data[pipe]["count"] += 1
        if r.get("error"):
            pipe_data[pipe]["errors"] += 1
        if r.get("scores"):
            for key in ["factual_accuracy", "source_citation", "expert_terminology",
                        "completeness", "language_match"]:
                val = r["scores"].get(key, 0)
                if val > 0:
                    pipe_data[pipe]["scores_sum"][key] += val
                    pipe_data[pipe]["scores_count"][key] += 1

    output = {}
    for pipe, pd in pipe_data.items():
        scores = {}
        for key in ["factual_accuracy", "source_citation", "expert_terminology",
                    "completeness", "language_match"]:
            cnt = pd["scores_count"][key]
            scores[key] = round(pd["scores_sum"][key] / cnt, 2) if cnt > 0 else 0
        overall = [v for v in scores.values() if v > 0]
        scores["overall"] = round(sum(overall) / len(overall), 2) if overall else 0
        output[pipe] = {"count": pd["count"], "errors": pd["errors"], "scores": scores}
    return output


def print_report(sector_scores, pipeline_scores=None):
    """Print formatted report."""
    print("\n" + "=" * 80)
    print("  TURBO EVALUATION REPORT")
    print("=" * 80)

    criteria = {
        "factual_accuracy": "Factual",
        "source_citation": "Citation",
        "expert_terminology": "Terms",
        "completeness": "Complete",
        "language_match": "Lang",
        "overall": "OVERALL",
    }

    header = f"  {'Sector':<12}"
    for key, label in criteria.items():
        header += f" {label:>9}"
    header += f" {'Latency':>9} {'Errors':>7}"
    print(header)
    print("  " + "-" * 77)

    for sector in ["finance", "btp", "juridique", "industrie"]:
        data = sector_scores.get(sector)
        if not data:
            continue
        scores = data["scores"]
        row = f"  {sector:<12}"
        for key in criteria:
            val = scores.get(key, 0)
            row += f" {val:>8.1f}/5"
        row += f" {data['avg_latency_ms']:>7}ms"
        row += f" {data['errors']:>7}"
        print(row)

    if pipeline_scores:
        print("\n  Per-pipeline breakdown:")
        print("  " + "-" * 77)
        for pipe in sorted(pipeline_scores.keys()):
            data = pipeline_scores[pipe]
            scores = data["scores"]
            row = f"  {pipe:<12}"
            for key in criteria:
                val = scores.get(key, 0)
                row += f" {val:>8.1f}/5"
            row += f" {'':>9}"
            row += f" {data['errors']:>7}"
            print(row)

    print("=" * 80)


def save_results(results, sector_scores, pipeline_scores=None):
    """Save all evaluation results."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_file = datetime.now().strftime("%Y%m%d-%H%M%S")

    # expert-results.json (same format as expert-eval.py)
    expert_output = {
        "timestamp": ts,
        "total_questions": len(results),
        "mode": "turbo",
        "stats": {
            "total": len(results),
            "judged": sum(1 for r in results if r.get("scores") and r["scores"].get("judge_backend") != "none"),
            "errors": sum(1 for r in results if r.get("error")),
            "judge_backends": dict(_judge_backends),
        },
        "results": results,
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(expert_output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved: {RESULTS_FILE}")

    # turbo-results-{timestamp}.json (archive copy)
    archive_file = os.path.join(DATA_DIR, f"turbo-results-{ts_file}.json")
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(expert_output, f, indent=2, ensure_ascii=False)
    print(f"  Archive saved: {archive_file}")

    # sector-scores.json
    scores_output = {
        "timestamp": ts,
        "mode": "turbo",
        "sectors": sector_scores,
    }
    if pipeline_scores:
        scores_output["pipelines"] = pipeline_scores
    with open(SECTOR_SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores_output, f, indent=2, ensure_ascii=False)
    print(f"  Sector scores saved: {SECTOR_SCORES_FILE}")


def show_latest_report():
    """Load and display the latest saved report."""
    if not os.path.exists(SECTOR_SCORES_FILE):
        print("  No previous results found. Run an evaluation first.")
        return
    with open(SECTOR_SCORES_FILE, "r") as f:
        data = json.load(f)
    print(f"  Last run: {data.get('timestamp', 'unknown')} (mode: {data.get('mode', '?')})")
    print_report(data.get("sectors", {}), data.get("pipelines"))


# =========================================================================
#  MAIN
# =========================================================================

def main():
    global _eval_start, _total_questions, _completed_count, _error_count, _all_results

    parser = argparse.ArgumentParser(description="Turbo Evaluation — 4-10x faster parallel eval")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel workers (default: 4, one per Space)")
    parser.add_argument("--pipelines", type=str, default="standard",
                        help="Comma-separated pipelines: standard,graph (default: standard)")
    parser.add_argument("--sector", type=str, default=None,
                        choices=["finance", "btp", "juridique", "industrie"])
    parser.add_argument("--sample", type=int, default=None,
                        help="Random sample N questions")
    parser.add_argument("--full", action="store_true",
                        help="Run all 208+ questions")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Seconds between requests per worker (default: 1.0)")
    parser.add_argument("--report", action="store_true",
                        help="Show latest report without running eval")
    parser.add_argument("--timeout", type=int, default=90,
                        help="Per-question webhook timeout in seconds (default: 90)")
    args = parser.parse_args()

    if args.report:
        show_latest_report()
        return

    pipelines = [p.strip() for p in args.pipelines.split(",")]
    num_workers = min(args.workers, len(SPACES))

    # Select questions
    questions = select_questions(
        sector=args.sector,
        sample=args.sample,
        full=args.full,
    )
    if not questions:
        print("  No questions selected. Check --sector or question bank.")
        sys.exit(1)

    # Build task queue
    tasks = build_task_queue(questions, pipelines, num_workers)
    _total_questions = len(tasks)

    # Create per-worker judges with different keys and model offsets
    judges = {}
    for i in range(num_workers):
        groq_key = _GROQ_KEYS[i % len(_GROQ_KEYS)] if _GROQ_KEYS else ""
        judges[i] = WorkerJudge(worker_id=i, groq_key=groq_key, model_start_idx=i)

    # Header
    print("=" * 80)
    print("  TURBO EVALUATION")
    print(f"  Workers: {num_workers} | Spaces: {', '.join(s.split('//')[1].split('.')[0].replace('lbjlincoln-nomos-rag-', '') for s in SPACES[:num_workers])}")
    print(f"  Pipelines: {', '.join(pipelines)}")
    print(f"  Questions: {len(questions)} x {len(pipelines)} pipeline(s) = {_total_questions} tasks")
    print(f"  Delay: {args.delay}s per worker | Timeout: {args.timeout}s")
    judges_info = []
    if _GROQ_KEYS:
        judges_info.append(f"Groq ({len(_GROQ_KEYS)} keys x {len(GROQ_JUDGE_MODELS)} models)")
    if OPENAI_API_KEY:
        judges_info.append("OpenAI (fallback)")
    if GOOGLE_API_KEY:
        judges_info.append("Gemini (fallback)")
    print(f"  Judge: {', '.join(judges_info) if judges_info else 'NONE'}")

    est_time = (_total_questions / num_workers) * (args.delay + 8)  # ~8s per question
    print(f"  Estimated time: ~{est_time/60:.0f} min (vs ~{_total_questions*38/60:.0f} min sequential)")
    print("=" * 80)

    # Reset globals
    _all_results = []
    _completed_count = 0
    _error_count = 0
    _eval_start = time.time()

    # Assign tasks to workers round-robin (so each worker hits its own Space)
    # Group by space for better locality
    space_tasks = defaultdict(list)
    for q, space, pipe in tasks:
        space_tasks[space].append((q, space, pipe))

    # Execute in parallel
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        task_idx = 0
        for q, space, pipe in tasks:
            # Determine worker index from space
            space_idx = 0
            for si, s in enumerate(SPACES[:num_workers]):
                if s == space:
                    space_idx = si
                    break
            judge = judges[space_idx]

            future = executor.submit(
                process_question,
                question_data=q,
                space_url=space,
                pipeline=pipe,
                judge=judge,
                delay=args.delay,
                question_idx=task_idx,
            )
            futures.append(future)
            task_idx += 1

        # Wait for all to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                with _print_lock:
                    print(f"  WORKER ERROR: {str(e)[:150]}", flush=True)

    total_elapsed = time.time() - _eval_start

    # Compute scores
    sector_scores = compute_sector_scores(_all_results)
    pipeline_scores = compute_pipeline_scores(_all_results) if len(pipelines) > 1 else None

    # Print report
    print_report(sector_scores, pipeline_scores)

    # Stats
    judged = sum(1 for r in _all_results if r.get("scores") and r["scores"].get("judge_backend") != "none")
    errors = sum(1 for r in _all_results if r.get("error"))
    print(f"\n  Stats: {len(_all_results)} tested | {judged} judged | {errors} errors")
    print(f"  Time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min) | "
          f"Avg: {total_elapsed/len(_all_results):.1f}s/question")
    if _judge_backends:
        print(f"  Judge backends: {dict(_judge_backends)}")

    speedup = (_total_questions * 38) / total_elapsed if total_elapsed > 0 else 0
    print(f"  Speedup vs sequential: ~{speedup:.1f}x")

    # Save
    save_results(_all_results, sector_scores, pipeline_scores)


if __name__ == "__main__":
    main()
