#!/usr/bin/env python3
"""
Continuous LLM-as-Judge — Scores every n8n pipeline execution in real-time.

Pulls recent executions from ALL Spaces (S1-S5, S9), extracts question/response/
latency/sources, scores each with a 5-criteria LLM judge, and maintains:

  1. Execution Board — TOP 20 best + BOTTOM 20 worst per pipeline per sector
  2. Judge History    — Append-only JSONL log of every judgment
  3. Auto-improvement — Groups failure patterns + suggests n8n node fixes

Usage:
  source .env.local
  python3 eval/continuous-judge.py                    # One-shot: judge recent executions
  python3 eval/continuous-judge.py --daemon 600       # Continuous: every 10 min
  python3 eval/continuous-judge.py --board            # Show current execution board
  python3 eval/continuous-judge.py --suggestions      # Show improvement suggestions
  python3 eval/continuous-judge.py --test-suggestions # Generate staging test commands
"""

import json
import os
import sys
import ssl
import time
import socket
import argparse
import http.cookiejar
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Lock

# ═══════════════════════════════════════════════════════════════════════════
#  IPv4 MONKEY-PATCH (IPv6 broken on GCP VM)
# ═══════════════════════════════════════════════════════════════════════════
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only(*args, **kwargs):
    results = _original_getaddrinfo(*args, **kwargs)
    return [r for r in results if r[0] == socket.AF_INET] or results
socket.getaddrinfo = _ipv4_only

# ═══════════════════════════════════════════════════════════════════════════
#  PATHS & CONFIG
# ═══════════════════════════════════════════════════════════════════════════
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "eval")
BOARD_FILE = os.path.join(DATA_DIR, "execution-board.json")
SUGGESTIONS_FILE = os.path.join(DATA_DIR, "improvement-suggestions.json")
HISTORY_FILE = os.path.join(DATA_DIR, "judge-history.jsonl")

# Load .env.local
_env_path = os.path.join(REPO_ROOT, ".env.local")
if os.path.exists(_env_path):
    with open(_env_path) as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _k = _k.strip()
                _v = _v.strip().strip('"').strip("'")
                if _k and _v:
                    os.environ.setdefault(_k, _v)

# SSL context (permissive for HF proxy)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ═══════════════════════════════════════════════════════════════════════════
#  SPACES & n8n AUTH
# ═══════════════════════════════════════════════════════════════════════════
SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S2": "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S4": "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

# Workflow ID → pipeline name
WORKFLOW_PIPELINES = {
    "TmgyRP20N4JFd9CB": "standard",
    "6257AfT1l4FMC6lY": "graph",
    "cjhEhVs0KV1ExHqX": "quantitative",
    "qOSaFFrqO8Jb4VGb": "orchestrator",
    "ALd4gOEqiKL5KR1p": "orchestrator",
    "ORa01sX4xI0iRCJ8": "enrichment",
    "Yqw7Pzn0e7m0C6i3": "auto-healer",
    "AH3eXOmgxt5cOd93": "error-trigger",
    "JyrwJ6UOQeSH9WXX": "error-trigger",
    "nh1D4Up0wBZhuQbp": "ingestion",
}

# Pipeline name fallback patterns
_NAME_PATTERNS = [
    ("standard", ["standard", "wf5", "multi-index"]),
    ("graph", ["graph", "wf2"]),
    ("quantitative", ["quant", "wf4"]),
    ("orchestrator", ["orchestrator", "v11", "v13"]),
    ("enrichment", ["enrichment", "enrichissement"]),
    ("auto-healer", ["auto-healer", "auto_healer", "autohealer"]),
    ("error-trigger", ["error trigger", "error-trigger"]),
    ("ingestion", ["ingestion", "ingest"]),
]

# Webhook paths (for detecting sector from trigger data)
WEBHOOK_SECTOR_HINTS = {
    "/webhook/rag-multi-index-v3": "standard",
    "/webhook/ff622742-6d71-4e91-af71-b5c666088717": "graph",
    "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9": "quantitative",
    "/webhook/orchestrator-v2": "orchestrator",
}

# Pipelines we actually want to judge (skip infra workflows)
JUDGEABLE_PIPELINES = {"standard", "graph", "quantitative", "orchestrator"}
ALL_SECTORS = ["finance", "btp", "juridique", "industrie"]
BOARD_SIZE = 20  # top/bottom N per pipeline per sector

# ═══════════════════════════════════════════════════════════════════════════
#  LLM JUDGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════
LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")
LITELLM_MODEL = "smart"

# Groq fallback (key rotation)
_GROQ_KEYS = [v for k, v in sorted(os.environ.items())
              if k.startswith("GROQ_API_KEY") and v and "QUANTITATIVE" not in k]
_groq_idx = 0
_lock = Lock()
_stats = {
    "executions_fetched": 0,
    "executions_judged": 0,
    "judge_calls": 0,
    "judge_success": 0,
    "judge_fail": 0,
    "skipped_non_judgeable": 0,
    "skipped_no_question": 0,
    "skipped_duplicate": 0,
}


def _next_groq_key():
    global _groq_idx
    with _lock:
        if not _GROQ_KEYS:
            return ""
        key = _GROQ_KEYS[_groq_idx % len(_GROQ_KEYS)]
        _groq_idx += 1
        return key


# ═══════════════════════════════════════════════════════════════════════════
#  JUDGE PROMPT (5 criteria, 1-5 each → 5-25 total → mapped to 0-100)
# ═══════════════════════════════════════════════════════════════════════════
JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for a French sector-specific AI assistant (RAG system).
You evaluate answers on 5 criteria, each scored 1-5:

1. **accuracy** (1-5): Is the information factually correct and relevant to the question?
   1=completely wrong/irrelevant, 2=mostly wrong, 3=partially correct, 4=mostly correct, 5=fully correct

2. **completeness** (1-5): Is the answer thorough enough for a professional?
   1=empty/trivial, 2=superficial, 3=adequate, 4=thorough, 5=comprehensive expert answer

3. **terminology** (1-5): Does the answer use correct professional/technical terminology for the sector?
   1=layman language, 2=some terms, 3=adequate, 4=professional, 5=expert-level terminology

4. **sources** (1-5): Does the answer cite or reference specific documents, data, or sources?
   1=no references at all, 2=vague references, 3=some citations, 4=good citations, 5=precise document/source references

5. **language** (1-5): Does the response match the question's language (French/English)?
   1=wrong language entirely, 3=mixed languages, 5=perfect language match

Respond ONLY with valid JSON:
{"accuracy": N, "completeness": N, "terminology": N, "sources": N, "language": N, "failure_type": "none|empty_response|wrong_sector|hallucination|missing_sources|wrong_language|timeout|partial", "reasoning": "one sentence"}"""


def _build_judge_prompt(question, answer, sources_text, sector, pipeline, latency_s):
    """Build the user prompt for the LLM judge."""
    return f"""Sector: {sector}
Pipeline: {pipeline}
Latency: {latency_s:.1f}s

QUESTION: {question}

RAG ANSWER: {answer[:2000] if answer else "(empty or no response)"}

SOURCES PROVIDED: {sources_text[:1000] if sources_text else "(none)"}

Score this answer on the 5 criteria (1-5 each). Also classify the failure_type if score < 3 on any criterion. Respond with JSON only."""


def _parse_judge_response(content):
    """Parse JSON from LLM judge response, handling markdown/think blocks."""
    content = content.strip()
    # Strip <think> tags (qwen/deepseek)
    if "<think>" in content:
        idx = content.find("</think>")
        if idx > 0:
            content = content[idx + 8:].strip()
    # Strip markdown code blocks
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


# ═══════════════════════════════════════════════════════════════════════════
#  LLM BACKENDS (LiteLLM primary, Groq fallback)
# ═══════════════════════════════════════════════════════════════════════════

def _call_litellm(system_prompt, user_prompt):
    """Call LiteLLM proxy."""
    payload = json.dumps({
        "model": LITELLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 300,
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}",
    }
    try:
        req = urllib.request.Request(LITELLM_URL, data=payload, headers=headers, method="POST")
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=45)
        data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return _parse_judge_response(content), None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        return None, f"LiteLLM HTTP {e.code}: {body}"
    except Exception as e:
        return None, f"LiteLLM error: {str(e)[:150]}"


def _call_groq(system_prompt, user_prompt):
    """Call Groq with key rotation and model fallback."""
    if not _GROQ_KEYS:
        return None, "No Groq keys"
    models = ["llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct"]
    for model in models:
        for _ in range(min(3, len(_GROQ_KEYS))):
            key = _next_groq_key()
            payload = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 300,
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            }
            try:
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=payload, headers=headers, method="POST",
                )
                resp = urllib.request.urlopen(req, timeout=30)
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_judge_response(content)
                if parsed:
                    return parsed, None
                return None, f"Groq parse error: {content[:200]}"
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(1)
                    continue
                return None, f"Groq HTTP {e.code}"
            except Exception as e:
                continue
    return None, "All Groq keys/models exhausted"


def judge_execution(question, answer, sources_text, sector, pipeline, latency_s):
    """Score an execution with LLM-as-Judge. Returns (scores_dict, total_score_0_100)."""
    user_prompt = _build_judge_prompt(question, answer, sources_text, sector, pipeline, latency_s)

    # Try LiteLLM first, then Groq
    for caller, name in [(_call_litellm, "litellm"), (_call_groq, "groq")]:
        scores, err = caller(JUDGE_SYSTEM_PROMPT, user_prompt)
        if scores and isinstance(scores, dict):
            # Validate all 5 criteria
            valid = True
            for key in ["accuracy", "completeness", "terminology", "sources", "language"]:
                val = scores.get(key)
                if not isinstance(val, (int, float)) or val < 1 or val > 5:
                    valid = False
                    break
            if valid:
                scores["judge_backend"] = name
                # Total score: sum of 5 criteria (5-25) → mapped to 0-100
                raw_sum = sum(scores.get(k, 1) for k in
                              ["accuracy", "completeness", "terminology", "sources", "language"])
                total = round((raw_sum - 5) / 20 * 100, 1)
                return scores, total
        if err:
            pass  # silently try next

    # All backends failed
    return {
        "accuracy": 0, "completeness": 0, "terminology": 0,
        "sources": 0, "language": 0,
        "failure_type": "judge_error",
        "reasoning": "All judge backends failed",
        "judge_backend": "none",
    }, 0.0


# ═══════════════════════════════════════════════════════════════════════════
#  n8n CLIENT (cookie-auth per Space)
# ═══════════════════════════════════════════════════════════════════════════

class N8nClient:
    """Cookie-authenticated HTTP client for one n8n HF Space."""

    def __init__(self, label, base_url):
        self.label = label
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPSHandler(context=_ssl_ctx),
        )
        self.logged_in = False

    def _request(self, method, path, data=None, timeout=30):
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            resp = self.opener.open(req, timeout=timeout)
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, {"error": raw}
        except urllib.error.URLError as e:
            return 503, {"error": f"URLError: {e.reason}"}
        except Exception as e:
            return 0, {"error": str(e)[:300]}

    def login(self):
        status, resp = self._request("POST", "/rest/login", {
            "emailOrLdapLoginId": N8N_EMAIL,
            "password": N8N_PASSWORD,
        })
        if status == 200:
            self.logged_in = True
            return True
        print(f"  [{self.label}] Login FAILED (HTTP {status})", flush=True)
        return False

    def fetch_executions(self, status_filter="success,error"):
        """GET recent executions. Returns list of execution dicts."""
        if not self.logged_in and not self.login():
            return []
        path = f"/rest/executions?limit=50&status={status_filter}"
        code, resp = self._request("GET", path, timeout=45)
        if code == 503:
            print(f"  [{self.label}] 503 — cold start, skip", flush=True)
            return []
        if code != 200:
            print(f"  [{self.label}] Fetch failed (HTTP {code})", flush=True)
            return []
        data = resp.get("data", resp)
        if isinstance(data, dict):
            return data.get("results", data.get("data", []))
        return data if isinstance(data, list) else []

    def fetch_execution_detail(self, exec_id):
        """GET single execution with full runData."""
        if not self.logged_in and not self.login():
            return None
        code, resp = self._request("GET", f"/rest/executions/{exec_id}", timeout=30)
        if code == 200:
            return resp.get("data", resp) if isinstance(resp, dict) else resp
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  EXECUTION PARSING — Extract question, response, sector, sources
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_pipeline(wf_id, wf_name):
    """Resolve workflow to canonical pipeline name."""
    if wf_id in WORKFLOW_PIPELINES:
        return WORKFLOW_PIPELINES[wf_id]
    name_lower = (wf_name or "").lower()
    for pipeline, patterns in _NAME_PATTERNS:
        for pat in patterns:
            if pat in name_lower:
                return pipeline
    return wf_name or "unknown"


def _parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _extract_execution_data(raw_exec, space_label):
    """Extract question, answer, sector, sources, pipeline, latency from a raw execution.

    Returns dict with all extracted fields, or None if not judgeable.
    """
    exec_id = str(raw_exec.get("id", ""))
    if not exec_id:
        return None

    wf_data = raw_exec.get("workflowData", {}) or {}
    wf_id = str(wf_data.get("id", raw_exec.get("workflowId", "")))
    wf_name = wf_data.get("name", "")
    pipeline = _resolve_pipeline(wf_id, wf_name)

    # Skip non-judgeable pipelines
    if pipeline not in JUDGEABLE_PIPELINES:
        return None

    status = raw_exec.get("status", "unknown")
    started = raw_exec.get("startedAt", "")
    stopped = raw_exec.get("stoppedAt", "")

    # Duration
    latency_s = 0.0
    dt_start = _parse_iso(started)
    dt_stop = _parse_iso(stopped)
    if dt_start and dt_stop:
        latency_s = round((dt_stop - dt_start).total_seconds(), 1)

    # Dig into runData to find the trigger node (question) and final node (response)
    result_data = raw_exec.get("data", {})
    if not isinstance(result_data, dict):
        result_data = {}
    run_data = result_data.get("resultData", {}).get("runData", {})

    question = ""
    answer = ""
    sector = ""
    sources = []
    sources_text = ""

    # --- Find question from trigger/webhook node ---
    for node_name, runs in run_data.items():
        node_lower = node_name.lower()
        if not isinstance(runs, list):
            continue
        for run in runs:
            out_data = run.get("data", {}).get("main", [])
            if not isinstance(out_data, list):
                continue
            for item_list in out_data:
                if not isinstance(item_list, list):
                    continue
                for item in item_list:
                    if not isinstance(item, dict):
                        continue
                    json_data = item.get("json", item)
                    if not isinstance(json_data, dict):
                        continue

                    # Extract question (from trigger/webhook)
                    if any(kw in node_lower for kw in ["trigger", "webhook", "input"]):
                        q = (json_data.get("query", "")
                             or json_data.get("chatInput", "")
                             or json_data.get("question", "")
                             or json_data.get("body", {}).get("query", "")
                             if isinstance(json_data.get("body"), dict) else "")
                        if isinstance(q, str) and len(q) > 5 and not question:
                            question = q.strip()
                        s = (json_data.get("sector", "")
                             or json_data.get("body", {}).get("sector", "")
                             if isinstance(json_data.get("body"), dict) else "")
                        if isinstance(s, str) and s and not sector:
                            sector = s.strip().lower()

                    # Extract answer (from final response/answer/synthesis nodes)
                    if any(kw in node_lower for kw in
                           ["response", "answer", "synthesis", "output", "final",
                            "generation", "format", "reply", "result"]):
                        a = (json_data.get("response", "")
                             or json_data.get("answer", "")
                             or json_data.get("text", "")
                             or json_data.get("interpretation", "")
                             or json_data.get("output", ""))
                        if isinstance(a, str) and len(a) > len(answer):
                            answer = a.strip()
                        # Sources
                        src = json_data.get("sources", [])
                        if isinstance(src, list) and src and not sources:
                            sources = src

    # Second pass: try to find answer in the LAST executed node
    if not answer:
        last_node = None
        last_time = ""
        for node_name, runs in run_data.items():
            if not isinstance(runs, list):
                continue
            for run in runs:
                st = run.get("startTime", "")
                if st > last_time:
                    last_time = st
                    last_node = (node_name, run)
        if last_node:
            node_name, run = last_node
            out_data = run.get("data", {}).get("main", [])
            if isinstance(out_data, list):
                for item_list in out_data:
                    if not isinstance(item_list, list):
                        continue
                    for item in item_list:
                        if not isinstance(item, dict):
                            continue
                        jd = item.get("json", item)
                        if isinstance(jd, dict):
                            for key in ["response", "answer", "text", "interpretation", "output"]:
                                val = jd.get(key, "")
                                if isinstance(val, str) and len(val) > len(answer):
                                    answer = val.strip()

    # Build sources text
    if sources:
        parts = []
        for i, s in enumerate(sources[:5]):
            if isinstance(s, dict):
                txt = s.get("text", s.get("content", ""))
                name = s.get("source", s.get("id", f"src-{i+1}"))
                if txt:
                    parts.append(f"[{name}] {txt[:300]}")
            elif isinstance(s, str):
                parts.append(s[:300])
        sources_text = "\n".join(parts)

    # No question found = not a user query execution
    if not question:
        return None

    # Infer sector from question content if missing
    if not sector:
        q_lower = question.lower()
        sector_hints = {
            "finance": ["bilan", "chiffre d'affaires", "revenue", "ebitda", "capex",
                         "ratio", "dette", "actif", "profit", "marge", "10-k", "10-q",
                         "fiscal", "annual report", "earnings"],
            "btp": ["dtu", "beton", "eurocode", "construction", "fondation", "batiment",
                    "ouvrage", "dalle", "echafaudage", "maconnerie", "chantier"],
            "juridique": ["code civil", "rgpd", "contrat", "tribunal", "article",
                          "responsabilit", "licenciement", "cnil", "juridique", "droit"],
            "industrie": ["iso", "amdec", "maintenance", "qualit", "production",
                          "fabrication", "usinage", "lean", "kaizen", "norme"],
        }
        best_count = 0
        for sec, hints in sector_hints.items():
            count = sum(1 for h in hints if h in q_lower)
            if count > best_count:
                best_count = count
                sector = sec
        if not sector:
            sector = "unknown"

    return {
        "exec_id": exec_id,
        "space": space_label,
        "pipeline": pipeline,
        "workflow_id": wf_id,
        "workflow_name": wf_name,
        "status": status,
        "started_at": started,
        "stopped_at": stopped,
        "latency_s": latency_s,
        "question": question,
        "answer": answer,
        "answer_length": len(answer),
        "sector": sector,
        "sources_count": len(sources),
        "sources_text": sources_text,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  BOARD MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def _load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _append_jsonl(path, record):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _board_key(pipeline, sector):
    return f"{pipeline}:{sector}"


def load_board():
    """Load execution board. Structure: {pipeline:sector: {good: [...], bad: [...], medium: [...]}}"""
    return _load_json(BOARD_FILE, {
        "metadata": {
            "created": datetime.now(timezone.utc).isoformat(),
            "last_updated": "",
            "total_judged": 0,
        },
        "boards": {},
        "seen_exec_ids": [],
    })


def update_board(board, judgment):
    """Add a judgment to the board, maintaining top/bottom N per pipeline:sector."""
    key = _board_key(judgment["pipeline"], judgment["sector"])

    if key not in board["boards"]:
        board["boards"][key] = {"good": [], "bad": [], "medium": []}

    entry = board["boards"][key]
    total_score = judgment["total_score"]

    # Compact record for board storage
    record = {
        "exec_id": judgment["exec_id"],
        "space": judgment["space"],
        "question": judgment["question"][:200],
        "answer_preview": judgment["answer"][:500],
        "sector": judgment["sector"],
        "pipeline": judgment["pipeline"],
        "total_score": total_score,
        "scores": judgment["scores"],
        "latency_s": judgment["latency_s"],
        "sources_count": judgment["sources_count"],
        "failure_type": judgment["scores"].get("failure_type", "none"),
        "reasoning": judgment["scores"].get("reasoning", ""),
        "judged_at": judgment["judged_at"],
    }

    if total_score >= 75:
        entry["good"].append(record)
        entry["good"].sort(key=lambda x: x["total_score"], reverse=True)
        entry["good"] = entry["good"][:BOARD_SIZE]
    elif total_score < 50:
        # For bad executions, also add failure analysis
        record["failure_analysis"] = _analyze_failure(judgment)
        record["suggested_fix"] = _suggest_quick_fix(judgment)
        entry["bad"].append(record)
        entry["bad"].sort(key=lambda x: x["total_score"])
        entry["bad"] = entry["bad"][:BOARD_SIZE]
    else:
        entry["medium"].append(record)
        entry["medium"].sort(key=lambda x: x["total_score"], reverse=True)
        entry["medium"] = entry["medium"][:BOARD_SIZE]

    # Track seen IDs (keep last 5000)
    if "seen_exec_ids" not in board:
        board["seen_exec_ids"] = []
    board["seen_exec_ids"].append(judgment["exec_id"])
    if len(board["seen_exec_ids"]) > 5000:
        board["seen_exec_ids"] = board["seen_exec_ids"][-5000:]

    board["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    board["metadata"]["total_judged"] = board["metadata"].get("total_judged", 0) + 1

    return board


def _analyze_failure(judgment):
    """Produce a failure analysis string for a bad execution."""
    scores = judgment["scores"]
    parts = []

    if scores.get("accuracy", 5) <= 2:
        parts.append("INACCURATE: Response contains factually incorrect or irrelevant information")
    if scores.get("completeness", 5) <= 2:
        parts.append("INCOMPLETE: Response is too superficial or misses key aspects")
    if scores.get("terminology", 5) <= 2:
        parts.append("BAD TERMINOLOGY: Lacks professional sector-specific vocabulary")
    if scores.get("sources", 5) <= 2:
        parts.append("NO SOURCES: Missing document citations or references")
    if scores.get("language", 5) <= 2:
        parts.append("WRONG LANGUAGE: Response language does not match question language")

    if judgment.get("answer", "") == "" or judgment.get("answer_length", 0) < 10:
        parts.append("EMPTY RESPONSE: Pipeline returned no meaningful content")
    if judgment.get("latency_s", 0) > 90:
        parts.append(f"TIMEOUT RISK: Latency was {judgment['latency_s']:.0f}s")

    ft = scores.get("failure_type", "none")
    if ft and ft != "none":
        parts.append(f"LLM-CLASSIFIED: {ft}")

    return " | ".join(parts) if parts else "Low overall quality"


def _suggest_quick_fix(judgment):
    """Suggest a quick fix based on the failure pattern."""
    scores = judgment["scores"]
    pipeline = judgment["pipeline"]
    ft = scores.get("failure_type", "none")

    if ft == "empty_response" or judgment.get("answer_length", 0) < 10:
        return f"Check {pipeline} final response node — may be returning empty. Verify Pinecone query returns results for sector={judgment['sector']}."
    if ft == "wrong_sector":
        return f"Sector routing issue in {pipeline}. Check tenant_id/sector filter in Pinecone query node. Question was for {judgment['sector']}."
    if ft == "hallucination":
        return f"LLM generating content not grounded in sources. Strengthen the system prompt in {pipeline}'s LLM generation node to cite only retrieved context."
    if ft == "missing_sources":
        return f"Sources not being passed to final response. Check {pipeline}'s source aggregation node — ensure sources array is included in output."
    if ft == "wrong_language":
        return f"Language detection not working. Add language detection to {pipeline}'s system prompt or add a 'respond in the same language as the question' instruction."
    if ft == "timeout":
        return f"Pipeline too slow. Profile {pipeline} nodes for bottleneck. Consider reducing Pinecone top_k or adding caching."
    if scores.get("accuracy", 5) <= 2:
        return f"Low accuracy — check {pipeline}'s retrieval quality. May need more vectors for sector={judgment['sector']} or better HyDE prompting."
    if scores.get("completeness", 5) <= 2:
        return f"Incomplete answers — increase max_tokens in {pipeline}'s LLM node or improve the system prompt to request detailed answers."

    return f"General quality issue in {pipeline} for {judgment['sector']}. Review system prompt and retrieval parameters."


# ═══════════════════════════════════════════════════════════════════════════
#  AUTO-IMPROVEMENT SUGGESTIONS
# ═══════════════════════════════════════════════════════════════════════════

def generate_suggestions(board):
    """Analyze all bad executions to produce ranked improvement suggestions."""
    # Collect all bad executions
    all_bad = []
    for key, entry in board.get("boards", {}).items():
        for record in entry.get("bad", []):
            all_bad.append(record)

    if len(all_bad) < 3:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": f"Not enough bad executions ({len(all_bad)}/5 minimum). Keep collecting.",
            "suggestions": [],
            "failure_distribution": {},
        }

    # Group by failure type
    by_failure = defaultdict(list)
    for b in all_bad:
        ft = b.get("failure_type", "unknown")
        if ft == "none":
            # Infer from scores
            scores = b.get("scores", {})
            if b.get("answer_preview", "") == "" or len(b.get("answer_preview", "")) < 10:
                ft = "empty_response"
            elif scores.get("accuracy", 5) <= 2:
                ft = "hallucination"
            elif scores.get("sources", 5) <= 2:
                ft = "missing_sources"
            elif scores.get("language", 5) <= 2:
                ft = "wrong_language"
            elif scores.get("terminology", 5) <= 2:
                ft = "bad_terminology"
            else:
                ft = "general_low_quality"
        by_failure[ft].append(b)

    # Group by pipeline
    by_pipeline = defaultdict(list)
    for b in all_bad:
        by_pipeline[b.get("pipeline", "unknown")].append(b)

    # Group by sector
    by_sector = defaultdict(list)
    for b in all_bad:
        by_sector[b.get("sector", "unknown")].append(b)

    # Build suggestions ranked by impact
    suggestions = []

    # Failure-type-based suggestions
    _FAILURE_FIXES = {
        "empty_response": {
            "title": "Fix empty responses",
            "description": "Pipeline returns no content. Likely retrieval failure or empty Pinecone results.",
            "node_target": "Pinecone Query / Final Response Set node",
            "fix": "1) Check Pinecone namespace and filter match sector. 2) Add fallback response when no vectors found. 3) Increase top_k.",
        },
        "wrong_sector": {
            "title": "Fix cross-sector contamination",
            "description": "Pipeline returns data from wrong sector. Sector filter not applied correctly.",
            "node_target": "Pinecone Query node (filter.sector / tenant_id)",
            "fix": "1) Ensure tenant_id is set to input sector in Pinecone query. 2) Verify V3.7 tenant_id fallback is active.",
        },
        "hallucination": {
            "title": "Reduce hallucinations",
            "description": "LLM generating content not grounded in retrieved sources.",
            "node_target": "LLM Generation / Answer Synthesis node",
            "fix": "1) Strengthen system prompt: 'ONLY use information from the provided sources'. 2) Add source-grounding check. 3) Reduce temperature to 0.",
        },
        "missing_sources": {
            "title": "Include source citations",
            "description": "Responses lack document references. Sources not passed through pipeline.",
            "node_target": "Source Aggregation / Final Response node",
            "fix": "1) Ensure sources array is included in final output JSON. 2) Add 'cite your sources' to LLM prompt. 3) Check Set node maps sources correctly.",
        },
        "wrong_language": {
            "title": "Fix language matching",
            "description": "Response language does not match question language.",
            "node_target": "LLM Generation node (system prompt)",
            "fix": "1) Add to system prompt: 'ALWAYS respond in the SAME language as the question'. 2) Add language detection in Code node before LLM call.",
        },
        "bad_terminology": {
            "title": "Improve sector terminology",
            "description": "Responses use generic language instead of professional sector terms.",
            "node_target": "LLM Generation node (system prompt)",
            "fix": "1) Add sector-specific terminology examples to system prompt. 2) Include sector context: 'You are a {sector} expert'. 3) Use sector glossary in prompt.",
        },
        "timeout": {
            "title": "Reduce pipeline latency",
            "description": "Execution takes too long (>90s). Bottleneck in retrieval or LLM nodes.",
            "node_target": "Pinecone Query + LLM Generation nodes",
            "fix": "1) Profile node-by-node latency. 2) Reduce top_k. 3) Use faster LLM model. 4) Add query caching for repeated questions.",
        },
        "general_low_quality": {
            "title": "Improve general answer quality",
            "description": "Responses are technically correct but lack depth and precision.",
            "node_target": "LLM Generation node",
            "fix": "1) Increase max_tokens. 2) Improve system prompt with expert examples. 3) Add more sector documents to knowledge base.",
        },
        "partial": {
            "title": "Complete partial answers",
            "description": "Response addresses the question but misses important aspects.",
            "node_target": "LLM Generation node + Retrieval nodes",
            "fix": "1) Increase top_k for broader context. 2) Add HyDE for better query reformulation. 3) Improve system prompt to request comprehensive answers.",
        },
    }

    for ft, bad_list in sorted(by_failure.items(), key=lambda x: -len(x[1])):
        fix_info = _FAILURE_FIXES.get(ft, {
            "title": f"Fix {ft} failures",
            "description": f"Multiple executions failing with pattern: {ft}",
            "node_target": "Review workflow nodes",
            "fix": "Investigate execution logs for this failure pattern.",
        })

        # Which pipelines/sectors are affected?
        affected_pipelines = list(set(b.get("pipeline", "?") for b in bad_list))
        affected_sectors = list(set(b.get("sector", "?") for b in bad_list))
        example_questions = [b.get("question", "")[:100] for b in bad_list[:3]]

        suggestions.append({
            "rank": 0,  # will be set below
            "failure_type": ft,
            "impact_count": len(bad_list),
            "title": fix_info["title"],
            "description": fix_info["description"],
            "node_target": fix_info["node_target"],
            "fix": fix_info["fix"],
            "affected_pipelines": affected_pipelines,
            "affected_sectors": affected_sectors,
            "example_questions": example_questions,
            "avg_score": round(sum(b.get("total_score", 0) for b in bad_list) / len(bad_list), 1),
        })

    # Rank by impact (most failures first)
    suggestions.sort(key=lambda x: -x["impact_count"])
    for i, s in enumerate(suggestions):
        s["rank"] = i + 1

    # Failure distribution
    failure_dist = {ft: len(bl) for ft, bl in by_failure.items()}
    pipeline_dist = {p: len(bl) for p, bl in by_pipeline.items()}
    sector_dist = {s: len(bl) for s, bl in by_sector.items()}

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_bad_executions": len(all_bad),
        "status": "suggestions_ready",
        "failure_distribution": failure_dist,
        "pipeline_distribution": pipeline_dist,
        "sector_distribution": sector_dist,
        "suggestions": suggestions,
    }

    _save_json(SUGGESTIONS_FILE, result)
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  LLM-BASED PATTERN ANALYSIS (deep suggestions)
# ═══════════════════════════════════════════════════════════════════════════

def _llm_analyze_failures(bad_executions):
    """Call LLM to analyze failure patterns and suggest improvements.
    Only called when >= 5 bad executions are accumulated.
    Returns analysis string or None.
    """
    if len(bad_executions) < 5:
        return None

    # Build a summary of failures for the LLM
    failure_summary = []
    for b in bad_executions[:15]:  # max 15 to fit context
        failure_summary.append({
            "pipeline": b.get("pipeline"),
            "sector": b.get("sector"),
            "question": b.get("question", "")[:150],
            "score": b.get("total_score"),
            "failure_type": b.get("failure_type", "unknown"),
            "reasoning": b.get("reasoning", "")[:100],
            "answer_preview": b.get("answer_preview", "")[:200],
        })

    prompt = f"""Analyze these {len(failure_summary)} RAG pipeline failure patterns and suggest specific n8n workflow improvements.

FAILURES:
{json.dumps(failure_summary, indent=2, ensure_ascii=False)}

For each pattern you identify:
1. Name the pattern
2. How many failures match
3. Which n8n node to fix (be specific: Pinecone Query, LLM Generation, Set Response, etc.)
4. Exact change to make

Respond in JSON: {{"patterns": [{{"name": "...", "count": N, "node": "...", "fix": "..."}}]}}"""

    scores, err = _call_litellm(
        "You are an n8n workflow optimization expert. Analyze RAG pipeline failures and suggest specific node-level fixes.",
        prompt,
    )
    if scores and isinstance(scores, dict):
        return scores
    # Try Groq
    scores, err = _call_groq(
        "You are an n8n workflow optimization expert. Analyze RAG pipeline failures and suggest specific node-level fixes.",
        prompt,
    )
    return scores if scores and isinstance(scores, dict) else None


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN COLLECTION + JUDGING LOOP
# ═══════════════════════════════════════════════════════════════════════════

def collect_and_judge(board=None, max_judge=50, concurrency=3):
    """Pull executions from all Spaces, judge them, update board.
    Returns (board, judgments_list, stats_dict).
    """
    if board is None:
        board = load_board()

    seen_ids = set(board.get("seen_exec_ids", []))
    all_judgments = []
    executions_to_judge = []

    print(f"\n{'='*70}")
    print(f"  CONTINUOUS JUDGE — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Previously judged: {board['metadata'].get('total_judged', 0)}")
    print(f"{'='*70}\n")

    # Phase 1: Fetch executions from all Spaces
    print("Phase 1: Fetching executions from 6 Spaces...\n")

    for label, url in SPACES.items():
        print(f"  [{label}] Connecting...", end="", flush=True)
        client = N8nClient(label, url)
        raw_execs = client.fetch_executions("success,error")
        fetched = len(raw_execs)
        _stats["executions_fetched"] += fetched

        new_count = 0
        for raw in raw_execs:
            exec_id = str(raw.get("id", ""))
            if exec_id in seen_ids:
                _stats["skipped_duplicate"] += 1
                continue

            # Fetch detail if needed
            exec_data = raw.get("data", {})
            if isinstance(exec_data, dict):
                has_run_data = bool(exec_data.get("resultData", {}).get("runData"))
            else:
                has_run_data = False

            if not has_run_data and exec_id:
                detail = client.fetch_execution_detail(exec_id)
                if detail:
                    raw = detail

            parsed = _extract_execution_data(raw, label)
            if parsed is None:
                if exec_id:
                    seen_ids.add(exec_id)  # Don't re-fetch non-judgeable
                _stats["skipped_non_judgeable"] += 1
                continue

            if not parsed["question"]:
                _stats["skipped_no_question"] += 1
                continue

            executions_to_judge.append(parsed)
            new_count += 1

        print(f" {fetched} fetched, {new_count} judgeable", flush=True)

    # Cap at max_judge
    if len(executions_to_judge) > max_judge:
        print(f"\n  Capping to {max_judge} (from {len(executions_to_judge)}) for this cycle")
        executions_to_judge = executions_to_judge[:max_judge]

    if not executions_to_judge:
        print("\n  No new executions to judge.")
        board["seen_exec_ids"] = list(seen_ids)
        _save_json(BOARD_FILE, board)
        return board, [], _stats

    # Phase 2: Judge each execution with LLM
    print(f"\nPhase 2: Judging {len(executions_to_judge)} executions (concurrency={concurrency})...\n")

    def _judge_one(parsed):
        """Judge a single parsed execution."""
        scores, total = judge_execution(
            question=parsed["question"],
            answer=parsed["answer"],
            sources_text=parsed["sources_text"],
            sector=parsed["sector"],
            pipeline=parsed["pipeline"],
            latency_s=parsed["latency_s"],
        )

        with _lock:
            _stats["judge_calls"] += 1
            if scores.get("judge_backend", "none") != "none":
                _stats["judge_success"] += 1
            else:
                _stats["judge_fail"] += 1

        judgment = {
            **parsed,
            "scores": scores,
            "total_score": total,
            "judged_at": datetime.now(timezone.utc).isoformat(),
        }
        # Remove large fields to save memory
        judgment.pop("sources_text", None)
        return judgment

    done = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(_judge_one, p): p for p in executions_to_judge}
        for future in as_completed(futures):
            try:
                judgment = future.result()
                all_judgments.append(judgment)
                board = update_board(board, judgment)

                # Append to JSONL history
                _append_jsonl(HISTORY_FILE, {
                    "exec_id": judgment["exec_id"],
                    "space": judgment["space"],
                    "pipeline": judgment["pipeline"],
                    "sector": judgment["sector"],
                    "question": judgment["question"][:200],
                    "total_score": judgment["total_score"],
                    "scores": judgment["scores"],
                    "latency_s": judgment["latency_s"],
                    "answer_length": judgment.get("answer_length", 0),
                    "sources_count": judgment.get("sources_count", 0),
                    "judged_at": judgment["judged_at"],
                })

                done += 1
                score = judgment["total_score"]
                label = "GOOD" if score >= 75 else "BAD" if score < 50 else "MED"
                pipe = judgment["pipeline"][:8]
                sec = judgment["sector"][:6]
                q_preview = judgment["question"][:50]

                if done % 5 == 0 or done == len(executions_to_judge):
                    elapsed = time.time() - t0
                    rate = done / elapsed if elapsed > 0 else 0
                    print(f"  [{done}/{len(executions_to_judge)}] {rate:.1f}/s | "
                          f"Last: {label} {score:.0f}/100 {pipe}@{sec} — {q_preview}...")

            except Exception as e:
                done += 1
                print(f"  [{done}] ERROR: {str(e)[:100]}")

    elapsed = time.time() - t0
    _stats["executions_judged"] += len(all_judgments)

    # Update seen IDs
    for j in all_judgments:
        seen_ids.add(j["exec_id"])
    board["seen_exec_ids"] = list(seen_ids)

    # Save board
    _save_json(BOARD_FILE, board)

    # Phase 3: Generate suggestions if enough bad executions
    all_bad = []
    for key, entry in board.get("boards", {}).items():
        all_bad.extend(entry.get("bad", []))

    if len(all_bad) >= 5:
        print(f"\nPhase 3: Generating improvement suggestions ({len(all_bad)} bad executions)...")
        suggestions = generate_suggestions(board)

        # Also try LLM-based deep analysis
        llm_analysis = _llm_analyze_failures(all_bad)
        if llm_analysis:
            suggestions["llm_analysis"] = llm_analysis
            _save_json(SUGGESTIONS_FILE, suggestions)

        n_sugg = len(suggestions.get("suggestions", []))
        print(f"  Generated {n_sugg} improvement suggestions")
    else:
        print(f"\nPhase 3: Not enough bad executions ({len(all_bad)}/5) for suggestions yet.")

    # Summary
    print(f"\n{'='*70}")
    print(f"  JUDGE CYCLE COMPLETE")
    print(f"{'='*70}")
    print(f"  Judged: {len(all_judgments)} executions in {elapsed:.0f}s")

    good = sum(1 for j in all_judgments if j["total_score"] >= 75)
    medium = sum(1 for j in all_judgments if 50 <= j["total_score"] < 75)
    bad = sum(1 for j in all_judgments if j["total_score"] < 50)
    avg = round(sum(j["total_score"] for j in all_judgments) / len(all_judgments), 1) if all_judgments else 0

    print(f"  GOOD (>=75): {good} | MEDIUM (50-74): {medium} | BAD (<50): {bad}")
    print(f"  Average score: {avg}/100")

    # Per pipeline
    by_pipe = defaultdict(list)
    for j in all_judgments:
        by_pipe[j["pipeline"]].append(j["total_score"])
    for pipe, scores in sorted(by_pipe.items()):
        avg_p = round(sum(scores) / len(scores), 1)
        print(f"    {pipe:15s}: {avg_p:5.1f}/100 ({len(scores)} judged)")

    # Per sector
    by_sec = defaultdict(list)
    for j in all_judgments:
        by_sec[j["sector"]].append(j["total_score"])
    for sec, scores in sorted(by_sec.items()):
        avg_s = round(sum(scores) / len(scores), 1)
        print(f"    {sec:15s}: {avg_s:5.1f}/100 ({len(scores)} judged)")

    print(f"\n  Board saved to: {BOARD_FILE}")
    print(f"  History saved to: {HISTORY_FILE}")
    print(f"{'='*70}")

    return board, all_judgments, _stats


# ═══════════════════════════════════════════════════════════════════════════
#  DISPLAY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def show_board():
    """Display the current execution board."""
    board = load_board()
    meta = board.get("metadata", {})

    print(f"\n{'='*80}")
    print(f"  EXECUTION BOARD — {meta.get('last_updated', 'never')}")
    print(f"  Total judged: {meta.get('total_judged', 0)}")
    print(f"{'='*80}")

    boards = board.get("boards", {})
    if not boards:
        print("\n  Board is empty. Run: python3 eval/continuous-judge.py")
        return

    for key in sorted(boards.keys()):
        entry = boards[key]
        pipeline, sector = key.split(":") if ":" in key else (key, "?")
        good = entry.get("good", [])
        bad = entry.get("bad", [])
        medium = entry.get("medium", [])

        print(f"\n  --- {pipeline.upper()} / {sector.upper()} ---")
        print(f"  Good: {len(good)} | Medium: {len(medium)} | Bad: {len(bad)}")

        if good:
            best = good[0]
            print(f"  BEST:  {best['total_score']:.0f}/100 | {best['question'][:60]}...")

        if bad:
            worst = bad[0]
            print(f"  WORST: {worst['total_score']:.0f}/100 | {worst['question'][:60]}...")
            ft = worst.get("failure_type", "")
            if ft and ft != "none":
                print(f"         Failure: {ft}")
            fa = worst.get("failure_analysis", "")
            if fa:
                print(f"         Analysis: {fa[:80]}...")

    # Overall stats
    all_good = sum(len(e.get("good", [])) for e in boards.values())
    all_bad = sum(len(e.get("bad", [])) for e in boards.values())
    all_med = sum(len(e.get("medium", [])) for e in boards.values())
    print(f"\n  TOTALS: {all_good} good, {all_med} medium, {all_bad} bad")
    print(f"{'='*80}")


def show_suggestions():
    """Display improvement suggestions."""
    data = _load_json(SUGGESTIONS_FILE, {})

    print(f"\n{'='*80}")
    print(f"  IMPROVEMENT SUGGESTIONS — {data.get('generated_at', 'never')}")
    print(f"{'='*80}")

    status = data.get("status", "no data")
    if status != "suggestions_ready":
        print(f"\n  Status: {status}")
        print(f"  Run more judge cycles to accumulate bad executions.")
        return

    print(f"\n  Total bad executions: {data.get('total_bad_executions', 0)}")

    # Failure distribution
    fd = data.get("failure_distribution", {})
    if fd:
        print(f"\n  Failure Distribution:")
        for ft, count in sorted(fd.items(), key=lambda x: -x[1]):
            bar = "#" * min(count, 30)
            print(f"    {ft:20s}: {count:3d} {bar}")

    # Pipeline distribution
    pd = data.get("pipeline_distribution", {})
    if pd:
        print(f"\n  By Pipeline:")
        for p, count in sorted(pd.items(), key=lambda x: -x[1]):
            print(f"    {p:15s}: {count:3d}")

    # Sector distribution
    sd = data.get("sector_distribution", {})
    if sd:
        print(f"\n  By Sector:")
        for s, count in sorted(sd.items(), key=lambda x: -x[1]):
            print(f"    {s:15s}: {count:3d}")

    # Suggestions
    suggestions = data.get("suggestions", [])
    if suggestions:
        print(f"\n  RANKED SUGGESTIONS ({len(suggestions)}):")
        print(f"  {'─'*70}")
        for s in suggestions:
            print(f"\n  #{s['rank']} — {s['title']} (impact: {s['impact_count']} failures, avg score: {s['avg_score']:.0f})")
            print(f"     Type: {s['failure_type']}")
            print(f"     Pipelines: {', '.join(s['affected_pipelines'])}")
            print(f"     Sectors: {', '.join(s['affected_sectors'])}")
            print(f"     Target node: {s['node_target']}")
            print(f"     Fix: {s['fix']}")
            if s.get("example_questions"):
                print(f"     Examples:")
                for eq in s["example_questions"][:2]:
                    print(f"       - {eq}")

    # LLM analysis
    llm_a = data.get("llm_analysis")
    if llm_a:
        print(f"\n  LLM DEEP ANALYSIS:")
        patterns = llm_a.get("patterns", [])
        for p in patterns:
            print(f"    - {p.get('name', '?')} ({p.get('count', '?')} matches)")
            print(f"      Node: {p.get('node', '?')}")
            print(f"      Fix: {p.get('fix', '?')}")

    print(f"\n{'='*80}")


def show_test_suggestions():
    """Generate staging test commands from top suggestion."""
    data = _load_json(SUGGESTIONS_FILE, {})
    suggestions = data.get("suggestions", [])

    print(f"\n{'='*80}")
    print(f"  STAGING TEST COMMANDS")
    print(f"{'='*80}")

    if not suggestions:
        print("\n  No suggestions available. Run more judge cycles first.")
        return

    top = suggestions[0]
    print(f"\n  Top suggestion: #{top['rank']} — {top['title']}")
    print(f"  Impact: {top['impact_count']} failures would potentially be fixed")
    print(f"  Target: {top['node_target']}")
    print(f"  Fix: {top['fix']}")

    print(f"\n  STAGING WORKFLOW:")
    print(f"  {'─'*60}")

    for pipeline in top["affected_pipelines"]:
        print(f"\n  Pipeline: {pipeline}")
        print(f"  1. Identify the node to modify:")
        print(f"     python3 ops/n8n-smart-analyzer.py --deep --pipeline {pipeline}")
        print(f"  2. Export current workflow for backup:")
        print(f"     python3 ops/n8n-api.py export {pipeline}")
        print(f"  3. Apply fix and deploy to staging Space (S5):")
        print(f"     python3 ops/staging-deploy.py --pipeline {pipeline} --space S5")
        print(f"  4. Run smoke test on staging:")
        print(f"     python3 eval/smart-smoke.py --space S5 --pipeline {pipeline}")
        print(f"  5. Compare with production:")
        print(f"     python3 eval/smart-smoke.py --compare S1 S5 --pipeline {pipeline}")
        print(f"  6. If improved, deploy to all Spaces:")
        print(f"     python3 ops/deploy-standard-v35.py --all")

    print(f"\n  WHAT TO CHANGE:")
    print(f"  {'─'*60}")
    print(f"  Node: {top['node_target']}")
    print(f"  Change: {top['fix']}")
    print(f"  Failure type: {top['failure_type']}")

    if top.get("example_questions"):
        print(f"\n  TEST QUESTIONS (use these to verify the fix):")
        for i, eq in enumerate(top["example_questions"]):
            print(f"    {i+1}. {eq}")

    print(f"\n{'='*80}")


# ═══════════════════════════════════════════════════════════════════════════
#  DAEMON MODE
# ═══════════════════════════════════════════════════════════════════════════

def daemon_loop(interval_s, max_judge=50, concurrency=3):
    """Run collect_and_judge in a continuous loop."""
    print(f"\nStarting daemon mode: every {interval_s}s ({interval_s/60:.0f} min)")
    print(f"  Max judge per cycle: {max_judge}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Board: {BOARD_FILE}")
    print(f"  History: {HISTORY_FILE}")
    print(f"  Suggestions: {SUGGESTIONS_FILE}")
    print(f"\n  Press Ctrl+C to stop.\n")

    board = load_board()
    cycle = 0

    while True:
        cycle += 1
        print(f"\n{'#'*70}")
        print(f"  CYCLE {cycle} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"{'#'*70}")

        try:
            board, judgments, stats = collect_and_judge(
                board=board, max_judge=max_judge, concurrency=concurrency,
            )
            print(f"\n  Cycle {cycle} complete. Sleeping {interval_s}s...")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"\n  ERROR in cycle {cycle}: {str(e)[:200]}")
            print(f"  Sleeping {interval_s}s before retry...")

        try:
            time.sleep(interval_s)
        except KeyboardInterrupt:
            print(f"\n\nDaemon stopped after {cycle} cycles.")
            break


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Continuous LLM-as-Judge — Scores every pipeline execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 eval/continuous-judge.py                    # One-shot judge
  python3 eval/continuous-judge.py --daemon 600       # Every 10 min
  python3 eval/continuous-judge.py --board            # Show board
  python3 eval/continuous-judge.py --suggestions      # Show suggestions
  python3 eval/continuous-judge.py --test-suggestions # Staging commands
        """,
    )
    parser.add_argument("--daemon", type=int, metavar="SECONDS",
                        help="Run in daemon mode with interval in seconds (default: 600)")
    parser.add_argument("--board", action="store_true",
                        help="Display the current execution board")
    parser.add_argument("--suggestions", action="store_true",
                        help="Display improvement suggestions")
    parser.add_argument("--test-suggestions", action="store_true",
                        help="Generate staging test commands from top suggestion")
    parser.add_argument("--max-judge", type=int, default=50,
                        help="Max executions to judge per cycle (default: 50)")
    parser.add_argument("--concurrency", type=int, default=3,
                        help="Parallel LLM judge calls (default: 3)")

    args = parser.parse_args()

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    if args.board:
        show_board()
        return

    if args.suggestions:
        show_suggestions()
        return

    if args.test_suggestions:
        show_test_suggestions()
        return

    if args.daemon:
        try:
            daemon_loop(
                interval_s=args.daemon,
                max_judge=args.max_judge,
                concurrency=args.concurrency,
            )
        except KeyboardInterrupt:
            print("\nDaemon stopped.")
    else:
        # One-shot mode
        board, judgments, stats = collect_and_judge(
            max_judge=args.max_judge,
            concurrency=args.concurrency,
        )
        print(f"\nStats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    main()
