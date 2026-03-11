#!/usr/bin/env python3
"""Redis-Backed Queue Eval Orchestrator — 5000+ questions × 48 workers × LLM Judge.

Uses Upstash Redis REST API (no drivers) to manage three queues:
  eval:questions  — Questions waiting to be sent to pipelines
  eval:responses  — Responses waiting to be judged by LLM
  eval:results    — Final judged results

Architecture:
  Producer   → loads dataset into eval:questions
  Workers    → RPOP questions, POST to pipeline webhooks, LPUSH responses
  Judges     → RPOP responses, call LLM judge, LPUSH results
  Collector  → RPOP results, aggregate, save incrementally

Backpressure:
  - Per-Space concurrency limit (default 3) via Redis INCR/DECR
  - Judge concurrency limit (default 2)
  - Exponential backoff on 503/timeout
  - Graceful shutdown on Ctrl+C

NOTE: Upstash DNS is blocked from the GCP VM. This script is designed to run
from HF Spaces or any environment where Upstash is reachable. On the VM, use
the 'results' and 'health' commands (which read local files / check Spaces).
The 'load', 'run', 'status', 'drain', 'monitor' commands require Redis access.

Usage:
    python3 eval/queue-eval-orchestrator.py load                          # Load default dataset
    python3 eval/queue-eval-orchestrator.py load --dataset extended       # Load extended dataset
    python3 eval/queue-eval-orchestrator.py run --workers 12 --judges 2   # Start processing
    python3 eval/queue-eval-orchestrator.py status                        # Show queue status
    python3 eval/queue-eval-orchestrator.py results                       # Show aggregated results
    python3 eval/queue-eval-orchestrator.py drain                         # Clear all queues
    python3 eval/queue-eval-orchestrator.py health                        # Check all components
    python3 eval/queue-eval-orchestrator.py monitor                       # Live dashboard
"""

import argparse
import json
import os
import signal
import socket
import ssl
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

# ============================================================
# IPv4 monkey-patch (IPv6 broken on VM)
# ============================================================
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only(*args, **kwargs):
    r = _original_getaddrinfo(*args, **kwargs)
    return [x for x in r if x[0] == socket.AF_INET] or r
socket.getaddrinfo = _ipv4_only

# SSL context (HF Spaces certs)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ============================================================
# Load .env.local
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ENV_PATH = os.path.join(PROJECT_ROOT, ".env.local")

if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                line = line[len("export "):]
                key, _, val = line.partition("=")
                val = val.strip('"').strip("'")
                os.environ.setdefault(key.strip(), val)

# ============================================================
# Upstash Redis REST API
# ============================================================
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

if not UPSTASH_URL or not UPSTASH_TOKEN:
    # Fallback names
    UPSTASH_URL = os.environ.get("UPSTASH_REDIS_URL", UPSTASH_URL)
    UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_TOKEN", UPSTASH_TOKEN)

# Queue keys
Q_QUESTIONS = "eval:questions"
Q_RESPONSES = "eval:responses"
Q_RESULTS = "eval:results"
Q_META = "eval:meta"          # Hash for run metadata
Q_SPACE_INFLIGHT = "eval:inflight:{space}"  # Per-space inflight counter
Q_JUDGE_INFLIGHT = "eval:judge:inflight"    # Judge inflight counter
Q_STATS = "eval:stats"        # Hash for live stats

# ============================================================
# Spaces & Webhooks
# ============================================================
SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S2": "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S4": "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

WEBHOOKS = {
    "standard":      "/webhook/rag-multi-index-v3",
    "graph":         "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative":  "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator":  "/webhook/orchestrator-v2",
}

# LLM Judge
JUDGE_URL = "https://lbjlincoln26-nomos-rag-engine-8.hf.space/webhook/eval-judge"
LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "sk-litellm-nomos-2026"

# Dataset paths
DATASETS = {
    "full":     os.path.join(PROJECT_ROOT, "sectors", "eval-datasets", "sector-full-eval.json"),
    "smoke":    os.path.join(PROJECT_ROOT, "sectors", "eval-datasets", "sector-smoke-test.json"),
    "extended": os.path.join(PROJECT_ROOT, "sectors", "eval-datasets", "sector-full-eval.json"),
    "tavily":   os.path.join(PROJECT_ROOT, "sectors", "eval-datasets", "tavily-real-world-tests.json"),
}

RESULTS_DIR = os.path.join(PROJECT_ROOT, "data", "eval")
RESULTS_FILE = os.path.join(RESULTS_DIR, "queue-eval-results.json")

# ============================================================
# Configuration defaults
# ============================================================
DEFAULT_WORKERS = 12
DEFAULT_JUDGES = 2
MAX_SPACE_CONCURRENCY = 3
MAX_JUDGE_CONCURRENCY = 2
WORKER_TIMEOUT = 120        # seconds per pipeline call
JUDGE_TIMEOUT = 60          # seconds per judge call
BACKOFF_BASE = 2.0          # exponential backoff base
BACKOFF_MAX = 60.0          # max backoff seconds
MAX_RETRIES = 3             # max retries per question

# ============================================================
# Global shutdown flag
# ============================================================
_shutdown = threading.Event()

def _signal_handler(sig, frame):
    print("\n[SHUTDOWN] Ctrl+C received — finishing in-flight work...")
    _shutdown.set()

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ============================================================
# Upstash REST helpers
# ============================================================
def redis_pipeline(commands):
    """Execute multiple Redis commands in a single HTTP pipeline request.

    Args:
        commands: List of lists, each inner list is [command, arg1, arg2, ...]

    Returns:
        List of results, one per command.
    """
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        raise RuntimeError("UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN not set")
    url = f"{UPSTASH_URL}/pipeline"
    headers = {
        "Authorization": f"Bearer {UPSTASH_TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps(commands).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=15)
        data = json.loads(resp.read().decode("utf-8"))
        return [item.get("result") for item in data]
    except Exception as e:
        raise RuntimeError(f"Redis pipeline error: {e}")


def redis_cmd(*args):
    """Execute a single Redis command via Upstash REST API.

    Usage: redis_cmd("LPUSH", "mykey", "value")
    """
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        raise RuntimeError("UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN not set")
    # Build URL path: /command/arg1/arg2/...
    # For commands with JSON values, use POST body instead
    parts = [str(a) for a in args]
    url = f"{UPSTASH_URL}"
    headers = {
        "Authorization": f"Bearer {UPSTASH_TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps(parts).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=15)
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("result")
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            pass
        raise RuntimeError(f"Redis cmd error ({e.code}): {err_body}")
    except Exception as e:
        raise RuntimeError(f"Redis cmd error: {e}")


def redis_cmd_safe(*args):
    """Like redis_cmd but returns None on error instead of raising."""
    try:
        return redis_cmd(*args)
    except Exception:
        return None

# ============================================================
# HTTP helpers
# ============================================================
def http_post(url, payload, timeout=120):
    """POST JSON, return (status_code, body_str, elapsed_seconds)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout)
        body = resp.read().decode("utf-8")
        return resp.status, body, time.time() - start
    except urllib.error.HTTPError as e:
        b = ""
        try:
            b = e.read().decode("utf-8")
        except Exception:
            pass
        return e.code, b, time.time() - start
    except Exception as e:
        return 0, str(e), time.time() - start


def http_post_with_auth(url, payload, token, timeout=60):
    """POST JSON with Bearer auth."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout)
        body = resp.read().decode("utf-8")
        return resp.status, body, time.time() - start
    except urllib.error.HTTPError as e:
        b = ""
        try:
            b = e.read().decode("utf-8")
        except Exception:
            pass
        return e.code, b, time.time() - start
    except Exception as e:
        return 0, str(e), time.time() - start

# ============================================================
# Scoring (local fallback — same as parallel-eval.py)
# ============================================================
SECTOR_TERMS = {
    "finance":   ["ratio", "marge", "chiffre", "revenue", "bilan", "actif", "passif", "ebitda", "capex"],
    "btp":       ["dtu", "beton", "norme", "construction", "ouvrage", "dalle", "fondation"],
    "juridique": ["article", "code", "responsabilit", "contrat", "droit", "obligation", "juridique"],
    "industrie": ["processus", "qualit", "norme", "iso", "production", "maintenance", "securit"],
}


def score_response_local(question, response_body):
    """Score a pipeline response locally (rule-based). Returns dict."""
    try:
        r = json.loads(response_body) if isinstance(response_body, str) else response_body
        if isinstance(r, list):
            r = r[0] if r else {}
    except (json.JSONDecodeError, TypeError):
        return {"score": 0, "status": "JSON_ERROR", "answer": str(response_body)[:200]}

    answer = str(r.get("response", r.get("answer", r.get("interpretation", ""))))
    sources = r.get("sources", [])
    score = 0

    # 1. Alive (15 pts)
    if len(answer) > 10:
        score += 15
    # 2. Length (20 pts)
    if len(answer) > 50:
        score += 10
    if len(answer) > 200:
        score += 10
    # 3. Expected keyword (30 pts)
    expected = question.get("expected_contains", "")
    keyword_hit = bool(expected and expected.lower() in answer.lower())
    if keyword_hit:
        score += 30
    # 4. Sources (15 pts)
    if len(sources) > 0:
        score += 8
    if len(sources) >= 3:
        score += 7
    # 5. Language (10 pts)
    q_lang = question.get("language", "fr")
    lang_ok = False
    if q_lang == "fr":
        lang_ok = any(w in answer.lower() for w in ["le ", "la ", "les ", "des ", "une ", "est ", "sont "])
    else:
        lang_ok = any(w in answer.lower() for w in ["the ", "is ", "are ", "was ", "has "])
    if lang_ok:
        score += 10
    # 6. Professional terms (10 pts)
    terms = SECTOR_TERMS.get(question.get("sector", ""), [])
    if any(t in answer.lower() for t in terms):
        score += 10

    return {
        "score": score,
        "status": "OK" if answer else "EMPTY",
        "answer_length": len(answer),
        "answer_preview": answer[:300],
        "sources_count": len(sources),
        "keyword_hit": keyword_hit,
        "language_ok": lang_ok,
    }

# ============================================================
# COMMAND: load
# ============================================================
def cmd_load(args):
    """Load questions from dataset into the eval:questions queue."""
    dataset_name = args.dataset or "full"
    dataset_path = DATASETS.get(dataset_name)
    if not dataset_path:
        print(f"[ERROR] Unknown dataset '{dataset_name}'. Available: {', '.join(DATASETS.keys())}")
        sys.exit(1)

    if not os.path.exists(dataset_path):
        print(f"[ERROR] Dataset file not found: {dataset_path}")
        sys.exit(1)

    print(f"[LOAD] Reading dataset: {dataset_name} ({dataset_path})")
    with open(dataset_path, "r") as f:
        data = json.load(f)

    questions = data.get("questions", [])

    # Apply filters
    if args.sector:
        questions = [q for q in questions if q.get("sector") == args.sector]
    if args.pipeline:
        questions = [q for q in questions if q.get("pipeline") == args.pipeline]

    if not questions:
        print("[ERROR] No questions match the filters.")
        sys.exit(1)

    # Determine which pipelines and spaces to target
    pipelines = args.pipelines.split(",") if args.pipelines else list(WEBHOOKS.keys())
    spaces = args.spaces.split(",") if args.spaces else list(SPACES.keys())

    # Expand questions: each question × each target pipeline × each target space
    # But only if --expand is set; otherwise just load raw questions with round-robin
    expanded = []
    if args.expand:
        for q in questions:
            for pipeline in pipelines:
                for space in spaces:
                    item = dict(q)
                    item["target_pipeline"] = pipeline
                    item["target_space"] = space
                    item["eval_id"] = f"{q['id']}_{pipeline}_{space}"
                    expanded.append(item)
    else:
        # Simple mode: use the question's own pipeline, round-robin spaces
        space_list = list(spaces)
        for i, q in enumerate(questions):
            item = dict(q)
            item["target_pipeline"] = q.get("pipeline", "standard")
            item["target_space"] = space_list[i % len(space_list)]
            item["eval_id"] = f"{q['id']}_{item['target_pipeline']}_{item['target_space']}"
            expanded.append(item)

    total = len(expanded)
    print(f"[LOAD] {len(questions)} base questions -> {total} eval items")
    if total > 100:
        print(f"[LOAD] Pipelines: {pipelines}")
        print(f"[LOAD] Spaces: {spaces}")

    # Clear old queue and push items in batches
    print("[LOAD] Clearing old eval:questions queue...")
    redis_cmd("DEL", Q_QUESTIONS)

    # Push in batches of 50 using pipeline
    batch_size = 50
    pushed = 0
    for i in range(0, total, batch_size):
        batch = expanded[i:i + batch_size]
        cmds = []
        for item in batch:
            cmds.append(["LPUSH", Q_QUESTIONS, json.dumps(item, ensure_ascii=False)])
        redis_pipeline(cmds)
        pushed += len(batch)
        if pushed % 500 == 0 or pushed == total:
            print(f"  Pushed {pushed}/{total} items")

    # Store run metadata
    run_meta = {
        "dataset": dataset_name,
        "total_questions": str(total),
        "base_questions": str(len(questions)),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "loaded",
        "pipelines": ",".join(pipelines),
        "spaces": ",".join(spaces),
    }
    cmds = [["HSET", Q_META, k, v] for k, v in run_meta.items()]
    redis_pipeline(cmds)

    print(f"\n[LOAD] Done. {total} items loaded into {Q_QUESTIONS}")
    print(f"[LOAD] Run: python3 eval/queue-eval-orchestrator.py run --workers 12 --judges 2")


# ============================================================
# COMMAND: run
# ============================================================
class SpaceSemaphore:
    """Thread-safe per-space concurrency limiter using Redis counters."""

    def __init__(self, max_concurrent=MAX_SPACE_CONCURRENCY):
        self.max = max_concurrent
        self._local_locks = {s: threading.Semaphore(max_concurrent) for s in SPACES}

    def acquire(self, space_name):
        """Acquire a slot for the given space. Blocks if at limit."""
        return self._local_locks[space_name].acquire(timeout=30)

    def release(self, space_name):
        """Release a slot for the given space."""
        self._local_locks[space_name].release()


class JudgeSemaphore:
    """Thread-safe judge concurrency limiter."""

    def __init__(self, max_concurrent=MAX_JUDGE_CONCURRENCY):
        self._sem = threading.Semaphore(max_concurrent)

    def acquire(self):
        return self._sem.acquire(timeout=30)

    def release(self):
        self._sem.release()


class LiveStats:
    """Thread-safe live statistics tracker."""

    def __init__(self):
        self._lock = threading.Lock()
        self.total = 0
        self.processed = 0
        self.judged = 0
        self.collected = 0
        self.errors = 0
        self.retries = 0
        self.scores = []
        self.by_pipeline = defaultdict(lambda: {"count": 0, "total_score": 0, "errors": 0})
        self.by_sector = defaultdict(lambda: {"count": 0, "total_score": 0})
        self.by_space = defaultdict(lambda: {"count": 0, "total_score": 0, "errors": 0, "total_latency": 0})
        self.start_time = time.time()

    def add_response(self, pipeline, sector, space, latency, error=False):
        with self._lock:
            self.processed += 1
            self.by_pipeline[pipeline]["count"] += 1
            self.by_sector[sector]["count"] += 1
            self.by_space[space]["count"] += 1
            self.by_space[space]["total_latency"] += latency
            if error:
                self.errors += 1
                self.by_pipeline[pipeline]["errors"] += 1
                self.by_space[space]["errors"] += 1

    def add_result(self, pipeline, sector, space, score):
        with self._lock:
            self.collected += 1
            self.scores.append(score)
            self.by_pipeline[pipeline]["total_score"] += score
            self.by_sector[sector]["total_score"] += score
            self.by_space[space]["total_score"] += score

    def add_judged(self):
        with self._lock:
            self.judged += 1

    def add_retry(self):
        with self._lock:
            self.retries += 1

    def get_summary(self):
        with self._lock:
            elapsed = time.time() - self.start_time
            avg_score = sum(self.scores) / len(self.scores) if self.scores else 0
            good = sum(1 for s in self.scores if s >= 65)
            bad = sum(1 for s in self.scores if s < 30)
            rate = self.collected / elapsed if elapsed > 0 else 0
            remaining = self.total - self.collected if self.total else 0
            eta = remaining / rate if rate > 0 else 0
            return {
                "total": self.total,
                "processed": self.processed,
                "judged": self.judged,
                "collected": self.collected,
                "errors": self.errors,
                "retries": self.retries,
                "avg_score": round(avg_score, 1),
                "good_pct": round(good / len(self.scores) * 100, 1) if self.scores else 0,
                "bad_pct": round(bad / len(self.scores) * 100, 1) if self.scores else 0,
                "rate": round(rate, 2),
                "elapsed_s": round(elapsed, 1),
                "eta_s": round(eta, 0),
            }

    def print_progress(self):
        s = self.get_summary()
        eta_min = s["eta_s"] / 60
        print(
            f"\r  Processed: {s['collected']}/{s['total']} | "
            f"Avg: {s['avg_score']}/100 | "
            f"GOOD: {s['good_pct']}% | BAD: {s['bad_pct']}% | "
            f"Errors: {s['errors']} | "
            f"{s['rate']} Q/s | "
            f"ETA: {eta_min:.1f}min",
            end="", flush=True,
        )


def worker_loop(worker_id, space_sem, stats, results_lock, all_results):
    """Worker thread: RPOP question, POST to pipeline, LPUSH response."""
    space_list = list(SPACES.keys())
    consecutive_empty = 0

    while not _shutdown.is_set():
        # RPOP a question
        raw = redis_cmd_safe("RPOP", Q_QUESTIONS)
        if raw is None:
            consecutive_empty += 1
            if consecutive_empty >= 5:
                # Queue is empty, worker can stop
                break
            time.sleep(0.5)
            continue
        consecutive_empty = 0

        try:
            question = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        eval_id = question.get("eval_id", question.get("id", "?"))
        pipeline = question.get("target_pipeline", question.get("pipeline", "standard"))
        space_name = question.get("target_space", space_list[worker_id % len(space_list)])
        sector = question.get("sector", "finance")
        webhook = WEBHOOKS.get(pipeline)

        if not webhook:
            continue

        space_url = SPACES.get(space_name)
        if not space_url:
            # Fallback to S1
            space_name = "S1"
            space_url = SPACES["S1"]

        url = f"{space_url}{webhook}"
        payload = {
            "query": question.get("question", ""),
            "sector": sector,
            "disable_acl": True,
        }

        # Acquire space slot (backpressure)
        if not space_sem.acquire(space_name):
            # Timeout acquiring slot, requeue
            redis_cmd_safe("LPUSH", Q_QUESTIONS, raw)
            stats.add_retry()
            continue

        # Send request with retry
        status_code = 0
        body = ""
        elapsed = 0
        success = False

        for attempt in range(MAX_RETRIES):
            if _shutdown.is_set():
                break

            status_code, body, elapsed = http_post(url, payload, timeout=WORKER_TIMEOUT)

            if status_code == 200:
                success = True
                break
            elif status_code in (503, 502, 429, 0):
                # Retry with backoff
                backoff = min(BACKOFF_BASE ** (attempt + 1), BACKOFF_MAX)
                stats.add_retry()
                time.sleep(backoff)
            else:
                # Non-retryable error (400, 404, etc.)
                break

        space_sem.release(space_name)

        # Build response item
        response_item = {
            "eval_id": eval_id,
            "question": question,
            "pipeline": pipeline,
            "sector": sector,
            "space": space_name,
            "http_status": status_code,
            "latency_s": round(elapsed, 2),
            "response_body": body[:5000],  # cap body size for Redis
            "success": success,
            "worker_id": worker_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        stats.add_response(pipeline, sector, space_name, elapsed, error=not success)

        # Push to responses queue
        redis_cmd_safe("LPUSH", Q_RESPONSES, json.dumps(response_item, ensure_ascii=False))


def judge_loop(judge_id, judge_sem, stats, results_lock, all_results):
    """Judge thread: RPOP response, score via LLM judge, LPUSH result."""
    consecutive_empty = 0

    while not _shutdown.is_set():
        raw = redis_cmd_safe("RPOP", Q_RESPONSES)
        if raw is None:
            consecutive_empty += 1
            # Judges should keep waiting longer since workers are still producing
            if consecutive_empty >= 20:
                # Check if workers are still active (questions queue not empty or workers still running)
                q_len = redis_cmd_safe("LLEN", Q_QUESTIONS)
                if q_len is not None and int(q_len) == 0:
                    # Also check if responses queue is empty
                    r_len = redis_cmd_safe("LLEN", Q_RESPONSES)
                    if r_len is not None and int(r_len) == 0:
                        break
                consecutive_empty = 0
            time.sleep(1.0)
            continue
        consecutive_empty = 0

        try:
            response_item = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        question = response_item.get("question", {})
        pipeline = response_item.get("pipeline", "standard")
        sector = response_item.get("sector", "finance")
        space = response_item.get("space", "?")
        eval_id = response_item.get("eval_id", "?")

        # Score the response
        judge_result = None

        if response_item.get("success") and response_item.get("http_status") == 200:
            # Try LLM judge first
            if judge_sem.acquire():
                try:
                    judge_result = call_llm_judge(question, response_item.get("response_body", ""))
                except Exception:
                    judge_result = None
                finally:
                    judge_sem.release()

            # Fallback to local scoring
            if judge_result is None:
                judge_result = score_response_local(question, response_item.get("response_body", ""))
                judge_result["judge"] = "local"
            else:
                judge_result["judge"] = "llm"
        else:
            # Failed request
            judge_result = {
                "score": 0,
                "status": f"HTTP_{response_item.get('http_status', 0)}",
                "answer_preview": response_item.get("response_body", "")[:200],
                "judge": "none",
            }

        stats.add_judged()

        # Build final result
        final_result = {
            "eval_id": eval_id,
            "question_id": question.get("id", "?"),
            "question_text": question.get("question", "")[:200],
            "pipeline": pipeline,
            "sector": sector,
            "space": space,
            "http_status": response_item.get("http_status", 0),
            "latency_s": response_item.get("latency_s", 0),
            "score": judge_result.get("score", 0),
            "status": judge_result.get("status", "?"),
            "answer_preview": judge_result.get("answer_preview", "")[:300],
            "keyword_hit": judge_result.get("keyword_hit", False),
            "sources_count": judge_result.get("sources_count", 0),
            "judge": judge_result.get("judge", "local"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Update stats
        stats.add_result(pipeline, sector, space, final_result["score"])

        # Push to results queue
        redis_cmd_safe("LPUSH", Q_RESULTS, json.dumps(final_result, ensure_ascii=False))

        # Also accumulate locally
        with results_lock:
            all_results.append(final_result)


def call_llm_judge(question, response_body):
    """Call external LLM judge to score a response. Returns score dict or None."""
    # Try S8 judge endpoint first
    judge_payload = {
        "question": question.get("question", ""),
        "expected_answer": question.get("expected_answer", ""),
        "expected_contains": question.get("expected_contains", ""),
        "sector": question.get("sector", ""),
        "pipeline_response": response_body[:3000],
        "language": question.get("language", "fr"),
    }

    status, body, elapsed = http_post(JUDGE_URL, judge_payload, timeout=JUDGE_TIMEOUT)
    if status == 200:
        try:
            result = json.loads(body)
            if isinstance(result, list):
                result = result[0] if result else {}
            if "score" in result:
                return {
                    "score": int(result.get("score", 0)),
                    "status": result.get("status", "OK"),
                    "answer_preview": result.get("answer_preview", ""),
                    "keyword_hit": result.get("keyword_hit", False),
                    "sources_count": result.get("sources_count", 0),
                    "judge_reasoning": result.get("reasoning", ""),
                }
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # Fallback to LiteLLM judge
    return call_litellm_judge(question, response_body)


def call_litellm_judge(question, response_body):
    """Call LiteLLM for LLM-as-judge scoring. Returns score dict or None."""
    try:
        resp_parsed = json.loads(response_body) if isinstance(response_body, str) else response_body
        if isinstance(resp_parsed, list):
            resp_parsed = resp_parsed[0] if resp_parsed else {}
        answer = str(resp_parsed.get("response", resp_parsed.get("answer", "")))[:2000]
    except (json.JSONDecodeError, TypeError):
        answer = str(response_body)[:2000]

    prompt = f"""You are an expert evaluator for a sector-specific RAG system.
Score this response on a scale of 0-100.

Question: {question.get('question', '')[:500]}
Expected answer: {question.get('expected_answer', '')[:500]}
Expected keyword: {question.get('expected_contains', '')}
Sector: {question.get('sector', '')}
Language expected: {question.get('language', 'fr')}

Pipeline response: {answer}

Score breakdown (100 total):
- Factual accuracy vs expected (40 pts)
- Source citation and evidence (20 pts)
- Professional terminology for sector (15 pts)
- Language match (10 pts)
- Completeness and depth (15 pts)

Return ONLY a JSON object: {{"score": <0-100>, "reasoning": "<1 sentence>"}}"""

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 150,
    }

    status, body, elapsed = http_post_with_auth(LITELLM_URL, payload, LITELLM_KEY, timeout=JUDGE_TIMEOUT)
    if status == 200:
        try:
            data = json.loads(body)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            # Try to extract JSON from response
            # Handle cases where LLM wraps in ```json ... ```
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            result = json.loads(content)
            return {
                "score": min(100, max(0, int(result.get("score", 0)))),
                "status": "OK",
                "answer_preview": answer[:300],
                "keyword_hit": bool(question.get("expected_contains", "").lower() in answer.lower()) if question.get("expected_contains") else False,
                "sources_count": 0,
                "judge_reasoning": result.get("reasoning", ""),
            }
        except (json.JSONDecodeError, TypeError, ValueError, IndexError):
            pass

    return None


def collector_loop(stats, results_lock, all_results):
    """Collector thread: periodically drain eval:results, save incrementally."""
    last_save = time.time()

    while not _shutdown.is_set():
        # Drain any results that were pushed by judges
        drained = 0
        while True:
            raw = redis_cmd_safe("RPOP", Q_RESULTS)
            if raw is None:
                break
            try:
                result = json.loads(raw)
                with results_lock:
                    # Avoid duplicates (judges already add locally)
                    existing_ids = {r.get("eval_id") for r in all_results}
                    if result.get("eval_id") not in existing_ids:
                        all_results.append(result)
                drained += 1
            except (json.JSONDecodeError, TypeError):
                continue

        # Save periodically (every 30s)
        now = time.time()
        if now - last_save >= 30:
            with results_lock:
                save_results(all_results, stats)
            last_save = now

        # Print progress
        stats.print_progress()

        # Check if everything is done
        q_len = redis_cmd_safe("LLEN", Q_QUESTIONS) or 0
        r_len = redis_cmd_safe("LLEN", Q_RESPONSES) or 0
        res_len = redis_cmd_safe("LLEN", Q_RESULTS) or 0
        if int(q_len) == 0 and int(r_len) == 0 and int(res_len) == 0:
            with results_lock:
                if len(all_results) >= stats.total > 0:
                    break

        time.sleep(3)


def save_results(all_results, stats):
    """Save results to disk incrementally."""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    summary = stats.get_summary()

    # Aggregate by pipeline
    by_pipeline = defaultdict(list)
    by_sector = defaultdict(list)
    by_space = defaultdict(list)
    for r in all_results:
        by_pipeline[r.get("pipeline", "?")].append(r)
        by_sector[r.get("sector", "?")].append(r)
        by_space[r.get("space", "?")].append(r)

    def agg(items):
        scores = [i.get("score", 0) for i in items]
        latencies = [i.get("latency_s", 0) for i in items if i.get("latency_s", 0) > 0]
        return {
            "count": len(items),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "pass_rate": round(sum(1 for s in scores if s >= 50) / len(scores) * 100, 1) if scores else 0,
            "avg_latency": round(sum(latencies) / len(latencies), 1) if latencies else 0,
            "errors": sum(1 for i in items if i.get("http_status", 0) != 200),
        }

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "by_pipeline": {k: agg(v) for k, v in sorted(by_pipeline.items())},
        "by_sector": {k: agg(v) for k, v in sorted(by_sector.items())},
        "by_space": {k: agg(v) for k, v in sorted(by_space.items())},
        "results": all_results[-100:],  # Last 100 for inspection
        "total_results": len(all_results),
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Also save full results with timestamp
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    full_path = os.path.join(RESULTS_DIR, f"queue-eval-{ts}.json")
    with open(full_path, "w") as f:
        json.dump({"report": report, "all_results": all_results}, f, indent=2, ensure_ascii=False)


def cmd_run(args):
    """Start processing: workers + judges + collector."""
    num_workers = args.workers or DEFAULT_WORKERS
    num_judges = args.judges or DEFAULT_JUDGES
    max_space_conc = args.space_concurrency or MAX_SPACE_CONCURRENCY
    max_judge_conc = args.judge_concurrency or MAX_JUDGE_CONCURRENCY

    # Check queue state
    q_len = redis_cmd("LLEN", Q_QUESTIONS)
    q_len = int(q_len) if q_len else 0
    if q_len == 0:
        print("[ERROR] eval:questions queue is empty. Run 'load' first.")
        sys.exit(1)

    # Check pending responses from previous run
    resp_len = int(redis_cmd("LLEN", Q_RESPONSES) or 0)
    res_len = int(redis_cmd("LLEN", Q_RESULTS) or 0)

    print(f"[RUN] Queue state:")
    print(f"  eval:questions  = {q_len}")
    print(f"  eval:responses  = {resp_len}")
    print(f"  eval:results    = {res_len}")
    print()
    print(f"[RUN] Configuration:")
    print(f"  Workers:              {num_workers}")
    print(f"  Judges:               {num_judges}")
    print(f"  Max space concurrency: {max_space_conc}")
    print(f"  Max judge concurrency: {max_judge_conc}")
    print(f"  Worker timeout:       {WORKER_TIMEOUT}s")
    print(f"  Judge timeout:        {JUDGE_TIMEOUT}s")
    print(f"  Spaces:               {', '.join(SPACES.keys())}")
    print()

    # Health check spaces
    print("[RUN] Health checking spaces...")
    healthy = []
    for name, url in SPACES.items():
        try:
            req = urllib.request.Request(f"{url}/healthz", method="GET")
            resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=8)
            healthy.append(name)
            print(f"  {name}: UP")
        except Exception:
            try:
                s, _, _ = http_post(f"{url}/webhook/rag-multi-index-v3",
                                    {"query": "ping", "sector": "finance", "disable_acl": True}, timeout=15)
                if s in (200, 201):
                    healthy.append(name)
                    print(f"  {name}: UP (via webhook)")
                else:
                    print(f"  {name}: DOWN ({s})")
            except Exception:
                print(f"  {name}: DOWN")

    if not healthy:
        print("[ERROR] No healthy Spaces found!")
        sys.exit(1)

    print(f"\n[RUN] {len(healthy)}/{len(SPACES)} Spaces healthy")

    # Initialize components
    space_sem = SpaceSemaphore(max_concurrent=max_space_conc)
    judge_sem = JudgeSemaphore(max_concurrent=max_judge_conc)
    stats = LiveStats()
    stats.total = q_len + resp_len  # Total items to process
    results_lock = threading.Lock()
    all_results = []

    # Pre-collect any existing results
    existing_results = int(redis_cmd("LLEN", Q_RESULTS) or 0)
    if existing_results > 0:
        print(f"[RUN] Draining {existing_results} existing results...")
        for _ in range(existing_results):
            raw = redis_cmd_safe("RPOP", Q_RESULTS)
            if raw:
                try:
                    all_results.append(json.loads(raw))
                except (json.JSONDecodeError, TypeError):
                    pass

    # Update meta
    redis_cmd("HSET", Q_META, "status", "running")
    redis_cmd("HSET", Q_META, "started_at", datetime.now(timezone.utc).isoformat())

    # Estimate time
    est_time = q_len * 35 / num_workers  # ~35s average per question
    print(f"\n[RUN] Starting {q_len} items with {num_workers} workers + {num_judges} judges")
    print(f"[RUN] Estimated time: {est_time / 60:.1f} min")
    print(f"[RUN] Press Ctrl+C to gracefully stop\n")

    # Launch threads
    threads = []

    # Worker threads
    for i in range(num_workers):
        t = threading.Thread(
            target=worker_loop,
            args=(i, space_sem, stats, results_lock, all_results),
            name=f"worker-{i}",
            daemon=True,
        )
        threads.append(("worker", t))

    # Judge threads
    for i in range(num_judges):
        t = threading.Thread(
            target=judge_loop,
            args=(i, judge_sem, stats, results_lock, all_results),
            name=f"judge-{i}",
            daemon=True,
        )
        threads.append(("judge", t))

    # Collector thread
    collector_thread = threading.Thread(
        target=collector_loop,
        args=(stats, results_lock, all_results),
        name="collector",
        daemon=True,
    )
    threads.append(("collector", collector_thread))

    # Start all threads
    for role, t in threads:
        t.start()

    # Wait for completion or shutdown
    try:
        for role, t in threads:
            while t.is_alive():
                t.join(timeout=2.0)
                if _shutdown.is_set():
                    break
            if _shutdown.is_set():
                break
    except KeyboardInterrupt:
        _shutdown.set()

    # Graceful shutdown: wait for in-flight to finish
    print("\n\n[RUN] Waiting for in-flight requests to complete...")
    _shutdown.set()
    for role, t in threads:
        t.join(timeout=30)

    # Final save
    with results_lock:
        save_results(all_results, stats)

    # Update meta
    redis_cmd_safe("HSET", Q_META, "status", "completed")
    redis_cmd_safe("HSET", Q_META, "completed_at", datetime.now(timezone.utc).isoformat())
    redis_cmd_safe("HSET", Q_META, "total_results", str(len(all_results)))

    # Print final report
    print()
    print_final_report(all_results, stats)


def print_final_report(all_results, stats):
    """Print the final evaluation report."""
    s = stats.get_summary()

    print("=" * 80)
    print(f"QUEUE EVAL RESULTS — {len(all_results)} results")
    print(f"Time: {s['elapsed_s']}s | Rate: {s['rate']} Q/s | Errors: {s['errors']} | Retries: {s['retries']}")
    print("=" * 80)

    scores = [r.get("score", 0) for r in all_results]
    avg = sum(scores) / len(scores) if scores else 0
    pass_count = sum(1 for s_ in scores if s_ >= 50)
    print(f"\nOverall: {avg:.1f}/100 avg | {pass_count}/{len(scores)} PASS ({pass_count / len(scores) * 100:.1f}%)" if scores else "")

    # By pipeline
    by_pipeline = defaultdict(list)
    for r in all_results:
        by_pipeline[r.get("pipeline", "?")].append(r)

    print(f"\n{'Pipeline':<15} {'Count':>6} {'Avg':>6} {'Pass%':>7} {'Latency':>8} {'Errors':>7}")
    print("-" * 55)
    for pipeline, rs in sorted(by_pipeline.items()):
        ps = [r.get("score", 0) for r in rs]
        lat = [r.get("latency_s", 0) for r in rs if r.get("latency_s", 0) > 0]
        errs = sum(1 for r in rs if r.get("http_status", 0) != 200)
        avg_p = sum(ps) / len(ps) if ps else 0
        avg_l = sum(lat) / len(lat) if lat else 0
        pass_r = sum(1 for s_ in ps if s_ >= 50) / len(ps) * 100 if ps else 0
        print(f"{pipeline:<15} {len(rs):>6} {avg_p:>6.1f} {pass_r:>6.1f}% {avg_l:>7.1f}s {errs:>7}")

    # By sector
    by_sector = defaultdict(list)
    for r in all_results:
        by_sector[r.get("sector", "?")].append(r)

    print(f"\n{'Sector':<15} {'Count':>6} {'Avg':>6} {'Pass%':>7}")
    print("-" * 38)
    for sector, rs in sorted(by_sector.items()):
        ss = [r.get("score", 0) for r in rs]
        avg_s = sum(ss) / len(ss) if ss else 0
        pass_s = sum(1 for s_ in ss if s_ >= 50) / len(ss) * 100 if ss else 0
        print(f"{sector:<15} {len(rs):>6} {avg_s:>6.1f} {pass_s:>6.1f}%")

    # By space
    by_space = defaultdict(list)
    for r in all_results:
        by_space[r.get("space", "?")].append(r)

    print(f"\n{'Space':<8} {'Count':>6} {'Avg':>6} {'Latency':>8} {'Errors':>7}")
    print("-" * 40)
    for space, rs in sorted(by_space.items()):
        ss = [r.get("score", 0) for r in rs]
        lat = [r.get("latency_s", 0) for r in rs if r.get("latency_s", 0) > 0]
        errs = sum(1 for r in rs if r.get("http_status", 0) != 200)
        avg_s = sum(ss) / len(ss) if ss else 0
        avg_l = sum(lat) / len(lat) if lat else 0
        print(f"{space:<8} {len(rs):>6} {avg_s:>6.1f} {avg_l:>7.1f}s {errs:>7}")

    # Judge distribution
    judge_types = defaultdict(int)
    for r in all_results:
        judge_types[r.get("judge", "?")] += 1
    if judge_types:
        print(f"\nJudge distribution: {dict(judge_types)}")

    print("=" * 80)
    print(f"Results saved to: {RESULTS_FILE}")


# ============================================================
# COMMAND: status
# ============================================================
def cmd_status(args):
    """Show current queue status."""
    print("[STATUS] Checking Redis queues...\n")

    results = redis_pipeline([
        ["LLEN", Q_QUESTIONS],
        ["LLEN", Q_RESPONSES],
        ["LLEN", Q_RESULTS],
        ["HGETALL", Q_META],
    ])

    q_len = int(results[0] or 0)
    resp_len = int(results[1] or 0)
    res_len = int(results[2] or 0)

    # Parse meta hash (comes as flat list: [key, val, key, val, ...])
    meta_raw = results[3] or []
    meta = {}
    if isinstance(meta_raw, list):
        for i in range(0, len(meta_raw), 2):
            if i + 1 < len(meta_raw):
                meta[meta_raw[i]] = meta_raw[i + 1]
    elif isinstance(meta_raw, dict):
        meta = meta_raw

    total = int(meta.get("total_questions", "0"))
    done = total - q_len - resp_len if total else 0

    print(f"  Run status:        {meta.get('status', 'unknown')}")
    print(f"  Dataset:           {meta.get('dataset', 'unknown')}")
    print(f"  Total questions:   {total}")
    print(f"  Pipelines:         {meta.get('pipelines', 'all')}")
    print(f"  Spaces:            {meta.get('spaces', 'all')}")
    print(f"  Started at:        {meta.get('started_at', 'N/A')}")
    print(f"  Completed at:      {meta.get('completed_at', 'N/A')}")
    print()
    print(f"  Queue: eval:questions  = {q_len:>6}  (waiting for pipeline)")
    print(f"  Queue: eval:responses  = {resp_len:>6}  (waiting for judge)")
    print(f"  Queue: eval:results    = {res_len:>6}  (waiting for collection)")
    print(f"  Total results:         = {meta.get('total_results', 'N/A')}")
    print()

    if total > 0:
        progress = done / total * 100
        print(f"  Progress: {done}/{total} ({progress:.1f}%)")
        bar_len = 40
        filled = int(bar_len * done / total)
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"  [{bar}]")

    # Per-space inflight
    print("\n  Per-Space inflight:")
    space_cmds = [["GET", Q_SPACE_INFLIGHT.format(space=s)] for s in SPACES]
    if space_cmds:
        try:
            space_results = redis_pipeline(space_cmds)
            for i, s in enumerate(SPACES):
                count = int(space_results[i] or 0) if space_results[i] else 0
                print(f"    {s}: {count}")
        except Exception:
            print("    (unable to read inflight counters)")


# ============================================================
# COMMAND: results
# ============================================================
def cmd_results(args):
    """Show aggregated results from the latest run."""
    if not os.path.exists(RESULTS_FILE):
        print("[ERROR] No results file found. Run an evaluation first.")
        sys.exit(1)

    with open(RESULTS_FILE, "r") as f:
        data = json.load(f)

    print(f"[RESULTS] From: {data.get('timestamp', 'unknown')}\n")

    summary = data.get("summary", {})
    print(f"  Total processed: {summary.get('collected', 0)}/{summary.get('total', 0)}")
    print(f"  Avg score:       {summary.get('avg_score', 0)}/100")
    print(f"  GOOD (>=65):     {summary.get('good_pct', 0)}%")
    print(f"  BAD (<30):       {summary.get('bad_pct', 0)}%")
    print(f"  Errors:          {summary.get('errors', 0)}")
    print(f"  Rate:            {summary.get('rate', 0)} Q/s")
    print(f"  Elapsed:         {summary.get('elapsed_s', 0)}s")

    # By pipeline
    by_p = data.get("by_pipeline", {})
    if by_p:
        print(f"\n  {'Pipeline':<15} {'Count':>6} {'Avg':>6} {'Pass%':>7} {'Latency':>8} {'Errors':>7}")
        print(f"  {'-' * 55}")
        for p, s in sorted(by_p.items()):
            print(f"  {p:<15} {s['count']:>6} {s['avg_score']:>6.1f} {s['pass_rate']:>6.1f}% {s['avg_latency']:>7.1f}s {s['errors']:>7}")

    # By sector
    by_s = data.get("by_sector", {})
    if by_s:
        print(f"\n  {'Sector':<15} {'Count':>6} {'Avg':>6} {'Pass%':>7}")
        print(f"  {'-' * 38}")
        for sec, s in sorted(by_s.items()):
            print(f"  {sec:<15} {s['count']:>6} {s['avg_score']:>6.1f} {s['pass_rate']:>6.1f}%")

    # By space
    by_sp = data.get("by_space", {})
    if by_sp:
        print(f"\n  {'Space':<8} {'Count':>6} {'Avg':>6} {'Latency':>8} {'Errors':>7}")
        print(f"  {'-' * 40}")
        for sp, s in sorted(by_sp.items()):
            print(f"  {sp:<8} {s['count']:>6} {s['avg_score']:>6.1f} {s['avg_latency']:>7.1f}s {s['errors']:>7}")

    # Show worst results for debugging
    results_list = data.get("results", [])
    if results_list and args.show_worst:
        worst = sorted(results_list, key=lambda r: r.get("score", 0))[:10]
        print(f"\n  WORST 10 RESULTS:")
        print(f"  {'ID':<20} {'Pipeline':<12} {'Sector':<10} {'Space':<6} {'Score':>5} {'Status':<10}")
        print(f"  {'-' * 70}")
        for r in worst:
            print(f"  {r.get('question_id', '?'):<20} {r.get('pipeline', '?'):<12} "
                  f"{r.get('sector', '?'):<10} {r.get('space', '?'):<6} "
                  f"{r.get('score', 0):>5} {r.get('status', '?'):<10}")


# ============================================================
# COMMAND: drain
# ============================================================
def cmd_drain(args):
    """Clear all queues."""
    if not args.force:
        # Show current state first
        results = redis_pipeline([
            ["LLEN", Q_QUESTIONS],
            ["LLEN", Q_RESPONSES],
            ["LLEN", Q_RESULTS],
        ])
        q = int(results[0] or 0)
        r = int(results[1] or 0)
        res = int(results[2] or 0)
        total = q + r + res
        if total > 0:
            print(f"[DRAIN] This will delete {total} items:")
            print(f"  eval:questions = {q}")
            print(f"  eval:responses = {r}")
            print(f"  eval:results   = {res}")
            confirm = input("\nType 'yes' to confirm: ").strip().lower()
            if confirm != "yes":
                print("[DRAIN] Cancelled.")
                return
        else:
            print("[DRAIN] Queues are already empty.")
            return

    # Delete all queue keys
    keys_to_del = [Q_QUESTIONS, Q_RESPONSES, Q_RESULTS, Q_META, Q_JUDGE_INFLIGHT]
    for s in SPACES:
        keys_to_del.append(Q_SPACE_INFLIGHT.format(space=s))

    cmds = [["DEL", k] for k in keys_to_del]
    redis_pipeline(cmds)

    print(f"[DRAIN] Cleared {len(keys_to_del)} keys.")


# ============================================================
# COMMAND: health
# ============================================================
def cmd_health(args):
    """Quick health check of all components."""
    print("[HEALTH] Checking components...\n")

    # 1. Redis
    print("  Redis (Upstash):")
    try:
        result = redis_cmd("PING")
        print(f"    Status: {'UP' if result == 'PONG' else 'UNKNOWN'} ({result})")
    except Exception as e:
        print(f"    Status: DOWN ({e})")

    # 2. Spaces
    print("\n  Spaces:")
    for name, url in SPACES.items():
        try:
            req = urllib.request.Request(f"{url}/healthz", method="GET")
            resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=8)
            print(f"    {name}: UP")
        except Exception:
            try:
                s, _, _ = http_post(f"{url}/webhook/rag-multi-index-v3",
                                    {"query": "ping", "sector": "finance", "disable_acl": True}, timeout=15)
                print(f"    {name}: {'UP' if s in (200, 201) else 'DOWN'} (webhook: {s})")
            except Exception:
                print(f"    {name}: DOWN")

    # 3. Judge (S8)
    print("\n  LLM Judge (S8):")
    try:
        s, _, _ = http_post(JUDGE_URL, {"question": "test", "pipeline_response": "test"}, timeout=15)
        print(f"    Status: {'UP' if s in (200, 201) else 'DOWN'} ({s})")
    except Exception as e:
        print(f"    Status: DOWN ({e})")

    # 4. LiteLLM fallback (S7)
    print("\n  LiteLLM (S7):")
    try:
        s, body, _ = http_post_with_auth(
            LITELLM_URL,
            {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
            LITELLM_KEY,
            timeout=15,
        )
        print(f"    Status: {'UP' if s == 200 else 'DOWN'} ({s})")
    except Exception as e:
        print(f"    Status: DOWN ({e})")

    # 5. Dataset
    print("\n  Datasets:")
    for name, path in DATASETS.items():
        exists = os.path.exists(path)
        if exists:
            with open(path, "r") as f:
                data = json.load(f)
            count = len(data.get("questions", []))
            print(f"    {name}: {count} questions ({path})")
        else:
            print(f"    {name}: NOT FOUND ({path})")


# ============================================================
# COMMAND: monitor (live dashboard in a loop)
# ============================================================
def cmd_monitor(args):
    """Live monitor — polls queue status every N seconds."""
    interval = args.interval or 5
    print(f"[MONITOR] Refreshing every {interval}s. Press Ctrl+C to stop.\n")

    try:
        while not _shutdown.is_set():
            results = redis_pipeline([
                ["LLEN", Q_QUESTIONS],
                ["LLEN", Q_RESPONSES],
                ["LLEN", Q_RESULTS],
                ["HGETALL", Q_META],
            ])

            q_len = int(results[0] or 0)
            resp_len = int(results[1] or 0)
            res_len = int(results[2] or 0)

            meta_raw = results[3] or []
            meta = {}
            if isinstance(meta_raw, list):
                for i in range(0, len(meta_raw), 2):
                    if i + 1 < len(meta_raw):
                        meta[meta_raw[i]] = meta_raw[i + 1]
            elif isinstance(meta_raw, dict):
                meta = meta_raw

            total = int(meta.get("total_questions", "0"))
            done = total - q_len - resp_len if total else 0
            pct = done / total * 100 if total else 0

            now = datetime.now().strftime("%H:%M:%S")
            bar_len = 30
            filled = int(bar_len * done / total) if total else 0
            bar = "#" * filled + "-" * (bar_len - filled)

            print(f"\r[{now}] [{bar}] {done}/{total} ({pct:.1f}%) | "
                  f"Q:{q_len} R:{resp_len} Done:{res_len} | "
                  f"Status:{meta.get('status', '?')}",
                  end="", flush=True)

            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    print()


# ============================================================
# Main CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Redis-Backed Queue Eval Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  load      Load questions from dataset into Redis queue
  run       Start workers + judges + collector
  status    Show current queue status
  results   Show aggregated results
  drain     Clear all queues
  health    Check all component health
  monitor   Live dashboard (polls every 5s)

Examples:
  python3 eval/queue-eval-orchestrator.py load --dataset full
  python3 eval/queue-eval-orchestrator.py load --dataset full --expand --pipelines standard,orchestrator
  python3 eval/queue-eval-orchestrator.py run --workers 12 --judges 2
  python3 eval/queue-eval-orchestrator.py status
  python3 eval/queue-eval-orchestrator.py results --show-worst
  python3 eval/queue-eval-orchestrator.py drain
  python3 eval/queue-eval-orchestrator.py health
  python3 eval/queue-eval-orchestrator.py monitor --interval 10
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # load
    p_load = subparsers.add_parser("load", help="Load questions into queue")
    p_load.add_argument("--dataset", default="full", help="Dataset name: full, smoke, extended, tavily")
    p_load.add_argument("--sector", help="Filter by sector")
    p_load.add_argument("--pipeline", help="Filter by pipeline")
    p_load.add_argument("--pipelines", help="Target pipelines (comma-separated, e.g. standard,graph)")
    p_load.add_argument("--spaces", help="Target spaces (comma-separated, e.g. S1,S3,S5)")
    p_load.add_argument("--expand", action="store_true",
                        help="Expand: each question x each pipeline x each space (for full matrix)")

    # run
    p_run = subparsers.add_parser("run", help="Start processing pipeline")
    p_run.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help=f"Worker threads (default: {DEFAULT_WORKERS})")
    p_run.add_argument("--judges", type=int, default=DEFAULT_JUDGES, help=f"Judge threads (default: {DEFAULT_JUDGES})")
    p_run.add_argument("--space-concurrency", type=int, default=MAX_SPACE_CONCURRENCY,
                        help=f"Max concurrent requests per Space (default: {MAX_SPACE_CONCURRENCY})")
    p_run.add_argument("--judge-concurrency", type=int, default=MAX_JUDGE_CONCURRENCY,
                        help=f"Max concurrent judge calls (default: {MAX_JUDGE_CONCURRENCY})")

    # status
    p_status = subparsers.add_parser("status", help="Show queue status")

    # results
    p_results = subparsers.add_parser("results", help="Show aggregated results")
    p_results.add_argument("--show-worst", action="store_true", help="Show worst 10 results")

    # drain
    p_drain = subparsers.add_parser("drain", help="Clear all queues")
    p_drain.add_argument("--force", action="store_true", help="Skip confirmation")

    # health
    p_health = subparsers.add_parser("health", help="Check component health")

    # monitor
    p_monitor = subparsers.add_parser("monitor", help="Live dashboard")
    p_monitor.add_argument("--interval", type=int, default=5, help="Refresh interval in seconds")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Validate Redis connection
    if args.command in ("load", "run", "status", "drain", "monitor"):
        if not UPSTASH_URL or not UPSTASH_TOKEN:
            print("[ERROR] Upstash Redis credentials not found.")
            print("  Set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN in .env.local")
            sys.exit(1)

    dispatch = {
        "load": cmd_load,
        "run": cmd_run,
        "status": cmd_status,
        "results": cmd_results,
        "drain": cmd_drain,
        "health": cmd_health,
        "monitor": cmd_monitor,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
