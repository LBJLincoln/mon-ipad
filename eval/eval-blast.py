#!/usr/bin/env python3
"""
Eval Blast — Full-blast continuous evaluation with Supabase tracking.

Runs ALL 4 pipelines with incremental questions from the 29K+ pool.
Results stored per-question in Supabase eval_results + eval_runs tables.
Tracks sources, scores, trends. Designed to run as agentic loop agent.

Usage:
  source .env.local
  python3 eval/eval-blast.py                          # 50 questions, all pipelines
  python3 eval/eval-blast.py --max 200                # 200 questions
  python3 eval/eval-blast.py --pipeline standard      # Single pipeline
  python3 eval/eval-blast.py --sector finance         # Single sector
  python3 eval/eval-blast.py --daemon 1800            # Continuous every 30min
  python3 eval/eval-blast.py --backfill               # Seed question bank from dataset
"""

# ── IPv4 fix (GCP VM has broken IPv6) ──
import socket
from socket import AF_INET
_orig_gai = socket.getaddrinfo
def _ipv4_gai(*a, **kw):
    r = _orig_gai(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _ipv4_gai

import argparse
import json
import os
import random
import re
import sys
import time
import traceback
from datetime import datetime, timezone

# Force unbuffered
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_FILE = os.path.join(REPO_ROOT, "sectors", "eval-datasets", "sector-full-eval-extended.json")
DATA_DIR = os.path.join(REPO_ROOT, "data", "eval")
STATE_FILE = os.path.join(DATA_DIR, "blast-state.json")

N8N_HOSTS = [h.strip() for h in os.environ.get("N8N_ALL_HOSTS",
    "https://lbjlincoln-nomos-rag-engine.hf.space,"
    "https://lbjlincoln-nomos-rag-engine-3.hf.space,"
    "https://lbjlincoln-nomos-rag-engine-5.hf.space").split(",") if h.strip()]

WEBHOOK_PATHS = {
    "standard":     "/webhook/rag-multi-index-v3",
    "graph":        "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

# ── Supabase connection ──
DB_URL = os.environ.get("DATABASE_URL", "")
_db_conn = None

def get_db():
    global _db_conn
    if _db_conn and not _db_conn.closed:
        return _db_conn
    try:
        import psycopg2
        _db_conn = psycopg2.connect(DB_URL)
        _db_conn.autocommit = True
        with _db_conn.cursor() as cur:
            cur.execute("SET search_path TO public")
        return _db_conn
    except Exception as e:
        log(f"DB connect failed: {e}")
        return None

def db_execute(query, params=None):
    conn = get_db()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchall()
            return True
    except Exception as e:
        log(f"DB error: {e}")
        try:
            conn.rollback()
        except:
            pass
        return None

# ── Logging ──
def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def normalize(text):
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    text = str(text)
    text = re.sub(r'(\d)[,\s](\d)', r'\1\2', text)
    return text.replace('$', '').replace('%', '').lower()

# ── LLM Judge ──
try:
    from eval.llm_judge import judge_answer as llm_judge
    USE_LLM_JUDGE = True
    log("LLM Judge loaded")
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from llm_judge import judge_answer as llm_judge
        USE_LLM_JUDGE = True
        log("LLM Judge loaded (direct)")
    except ImportError:
        USE_LLM_JUDGE = False
        log("WARNING: LLM Judge not available, using keyword matching")

# ── Pipeline calls ──
_rr = {}

def call_pipeline(pipeline, question, sector, timeout=120):
    from urllib import request, error
    path = WEBHOOK_PATHS.get(pipeline)
    if not path:
        return {"ok": False, "answer": "", "latency_ms": 0, "error": "unknown pipeline", "sources": []}

    idx = _rr.get(pipeline, 0)
    _rr[pipeline] = idx + 1
    host = N8N_HOSTS[idx % len(N8N_HOSTS)]
    endpoint = f"{host}{path}"
    space = f"S{['1','3','5'][idx % len(N8N_HOSTS)]}" if len(N8N_HOSTS) == 3 else f"H{idx % len(N8N_HOSTS)}"

    payload = json.dumps({
        "query": question, "question": question,
        "tenant_id": sector, "sector": sector,
        "top_k": 10, "include_sources": True,
    }).encode()

    req = request.Request(endpoint, data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
    try:
        start = time.time()
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            latency = int((time.time() - start) * 1000)
            data = json.loads(raw)
            if isinstance(data, list):
                data = data[0] if data else {}

            answer = ""
            for key in ["response", "answer", "result", "interpretation", "final_response"]:
                if key in data and data[key]:
                    answer = str(data[key])
                    break

            # Extract sources from response
            sources = []
            for key in ["sources", "source_documents", "context", "documents"]:
                if key in data and isinstance(data[key], list):
                    for s in data[key][:10]:
                        if isinstance(s, dict):
                            sources.append({
                                "title": s.get("title", s.get("source", "")),
                                "sector": s.get("sector", sector),
                                "score": s.get("score", s.get("relevance_score", 0)),
                                "doc_id": s.get("id", s.get("doc_id", "")),
                            })
                        elif isinstance(s, str):
                            sources.append({"title": s[:100], "sector": sector})
                    break

            return {"ok": True, "answer": answer, "latency_ms": latency,
                    "sources": sources, "space": space,
                    "execution_id": data.get("execution_id", "")}
    except error.HTTPError as e:
        return {"ok": False, "answer": "", "latency_ms": 0,
                "error": f"HTTP {e.code}", "sources": [], "space": space}
    except Exception as e:
        err = str(e)[:150]
        status = "timeout" if "timed out" in err.lower() or "timeout" in err.lower() else "error"
        return {"ok": False, "answer": "", "latency_ms": 0,
                "error": err, "sources": [], "space": space, "status_hint": status}


# ── Supabase tracking ──
def create_run(run_type, pipeline, sector, triggered_by="eval_blast"):
    result = db_execute("""
        INSERT INTO eval_runs (run_type, pipeline, sector, triggered_by, started_at)
        VALUES (%s, %s, %s, %s, now())
        RETURNING id
    """, (run_type, pipeline or "all", sector or "all", triggered_by))
    if result and len(result) > 0:
        return str(result[0][0])
    return None

def save_result(run_id, q, resp, status, pipeline, sector, judge_result=None):
    sources_json = json.dumps(resp.get("sources", []))
    source_ids = [s.get("doc_id", "") for s in resp.get("sources", []) if s.get("doc_id")]
    answer = resp.get("answer", "") or resp.get("interpretation", "")

    # Judge scores — DB expects 0-20 per dimension, 0-100 total
    j = judge_result or {}
    accuracy_score = int(j["accuracy"] / 5) if j.get("accuracy") is not None else None
    completeness_score = int(j["completeness"] / 5) if j.get("completeness") is not None else None
    terminology_score = int(j["terminology"] / 5) if j.get("terminology") is not None else None
    total_score = int((j.get("accuracy", 0) + j.get("completeness", 0) + j.get("terminology", 0)) / 3) if j.get("accuracy") is not None else None
    judge_reasoning = j.get("reasoning", "")
    judge_method = j.get("judge_method", "keyword")
    # classification must be GOOD/MEDIUM/BAD
    if total_score is not None:
        classification = "GOOD" if total_score >= 70 else ("MEDIUM" if total_score >= 40 else "BAD")
    else:
        classification = None

    db_execute("""
        INSERT INTO eval_results
            (run_id, question_id, question, sector, pipeline, expected_contains,
             answer, answer_preview, status, latency_ms, space, execution_id,
             sources, source_count, source_doc_ids,
             accuracy_score, completeness_score, terminology_score, total_score,
             judge_reasoning, classification,
             difficulty, category, language, dataset_source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s)
    """, (
        run_id, q.get("id", ""), q.get("question", ""), sector, pipeline,
        q.get("expected_contains", ""),
        answer, answer[:500] if answer else "",
        status, resp.get("latency_ms", 0), resp.get("space", ""),
        resp.get("execution_id", ""),
        sources_json, len(resp.get("sources", [])), source_ids or [],
        accuracy_score, completeness_score, terminology_score, total_score,
        judge_reasoning[:500] if judge_reasoning else "", classification,
        q.get("difficulty", "medium"), q.get("category", ""),
        q.get("language", "fr"), q.get("dataset_source", "generated"),
    ))

def update_question_bank(q, status, latency_ms, score=None):
    qid = q.get("id", "")
    if not qid:
        return
    db_execute("""
        INSERT INTO eval_question_bank
            (id, question, sector, pipeline, expected_contains, difficulty, category,
             language, dataset_source, times_asked, times_passed, times_failed,
             avg_latency_ms, last_status, last_asked_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s, now(), now())
        ON CONFLICT (id) DO UPDATE SET
            times_asked = eval_question_bank.times_asked + 1,
            times_passed = eval_question_bank.times_passed + EXCLUDED.times_passed,
            times_failed = eval_question_bank.times_failed + EXCLUDED.times_failed,
            avg_latency_ms = (eval_question_bank.avg_latency_ms * eval_question_bank.times_asked + %s)
                / (eval_question_bank.times_asked + 1),
            last_status = EXCLUDED.last_status,
            last_asked_at = now(),
            consecutive_fails = CASE WHEN EXCLUDED.last_status = 'fail' OR EXCLUDED.last_status = 'error'
                THEN eval_question_bank.consecutive_fails + 1 ELSE 0 END,
            score_trend = CASE
                WHEN EXCLUDED.last_status = 'pass' AND eval_question_bank.last_status != 'pass' THEN 'improving'
                WHEN EXCLUDED.last_status != 'pass' AND eval_question_bank.last_status = 'pass' THEN 'degrading'
                ELSE eval_question_bank.score_trend END,
            updated_at = now()
    """, (
        qid, q.get("question", ""), q.get("sector", ""), q.get("pipeline", "standard"),
        q.get("expected_contains", ""), q.get("difficulty", "medium"),
        q.get("category", ""), q.get("language", "fr"), q.get("dataset_source", "generated"),
        1 if status == "pass" else 0, 0 if status == "pass" else 1,
        latency_ms, status, latency_ms,
    ))

def finalize_run(run_id, stats):
    total = stats["total"]
    accuracy = round(stats["pass"] / total * 100, 2) if total else 0
    avg_lat = round(stats["total_latency"] / total) if total else 0
    db_execute("""
        UPDATE eval_runs SET
            total_questions = %s, passed = %s, failed = %s, errors = %s,
            accuracy = %s, avg_latency_ms = %s, completed_at = now()
        WHERE id = %s
    """, (total, stats["pass"], stats["fail"], stats["error"],
          accuracy, avg_lat, run_id))


# ── Load & select questions ──
def load_questions():
    with open(QUESTIONS_FILE) as f:
        data = json.load(f)
    return data.get("questions", [])

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"asked_ids": [], "run_count": 0, "total_asked": 0}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def select_questions(all_questions, max_q, pipeline_filter, sector_filter, state):
    """Select questions incrementally — prioritize never-asked, then worst-performing."""
    asked_set = set(state.get("asked_ids", [])[-5000:])  # Keep last 5K

    # Filter by pipeline/sector
    pool = all_questions
    if pipeline_filter and pipeline_filter != "all":
        pool = [q for q in pool if q.get("pipeline") == pipeline_filter]
    if sector_filter and sector_filter != "all":
        pool = [q for q in pool if q.get("sector") == sector_filter]

    if not pool:
        log("No questions match filters!")
        return []

    # Split: never-asked vs already-asked
    never_asked = [q for q in pool if q.get("id") not in asked_set]
    already_asked = [q for q in pool if q.get("id") in asked_set]

    # Prioritize: 70% never-asked, 30% retry (for regression detection)
    n_new = min(int(max_q * 0.7), len(never_asked))
    n_retry = min(max_q - n_new, len(already_asked))

    selected = random.sample(never_asked, n_new) if never_asked else []
    if n_retry > 0 and already_asked:
        selected += random.sample(already_asked, n_retry)

    # If still not enough, fill from pool
    remaining = max_q - len(selected)
    if remaining > 0:
        leftover = [q for q in pool if q not in selected]
        selected += random.sample(leftover, min(remaining, len(leftover)))

    random.shuffle(selected)
    return selected[:max_q]


# ── Main eval loop ──
def run_blast(max_q=50, pipeline_filter=None, sector_filter=None,
              run_type="full_blast", triggered_by="eval_blast"):
    log(f"=== EVAL BLAST: {max_q}Q | pipeline={pipeline_filter or 'all'} | sector={sector_filter or 'all'} ===")

    all_questions = load_questions()
    log(f"Question pool: {len(all_questions)} total")

    state = load_state()
    questions = select_questions(all_questions, max_q, pipeline_filter, sector_filter, state)
    log(f"Selected: {len(questions)} questions (incremental)")

    if not questions:
        return {"total": 0}

    # Create run in Supabase
    run_id = create_run(run_type, pipeline_filter, sector_filter, triggered_by)
    if run_id:
        log(f"DB Run: {run_id}")
    else:
        log("WARNING: No DB connection — results saved to JSON only")

    stats = {"total": 0, "pass": 0, "fail": 0, "error": 0, "total_latency": 0}
    pipeline_stats = {}
    sector_stats = {}
    results_json = []

    for i, q in enumerate(questions):
        qid = q.get("id", f"q{i}")
        question = q.get("question", "")
        expected = q.get("expected_contains", "")
        pipeline = q.get("pipeline", "standard")
        sector = q.get("sector", "finance")

        timeout = 300 if pipeline in ("orchestrator", "quantitative") else 180 if pipeline == "graph" else 120

        resp = call_pipeline(pipeline, question, sector, timeout)
        stats["total"] += 1
        stats["total_latency"] += resp.get("latency_ms", 0)

        # Evaluate — LLM Judge (with keyword fallback)
        passed = False
        judge_result = None
        if resp["ok"] and resp["answer"]:
            if USE_LLM_JUDGE:
                judge_result = llm_judge(
                    question=question, answer=resp["answer"],
                    expected_contains=expected, sector=sector, pipeline=pipeline,
                )
                passed = judge_result["pass"]
            else:
                if expected:
                    if isinstance(expected, list):
                        passed = any(normalize(e) in normalize(resp["answer"]) for e in expected if e)
                    else:
                        passed = normalize(str(expected)) in normalize(resp["answer"])
                else:
                    passed = len(resp["answer"]) > 10

        if not resp["ok"]:
            status = resp.get("status_hint", "error")
        else:
            status = "pass" if passed else "fail"

        stats[status if status in stats else "error"] += 1

        # Track per-pipeline / per-sector
        for d, key in [(pipeline_stats, pipeline), (sector_stats, sector)]:
            if key not in d:
                d[key] = {"pass": 0, "fail": 0, "error": 0, "timeout": 0, "total": 0, "latency": []}
            d[key]["total"] += 1
            d[key][status if status in d[key] else "error"] += 1
            if resp.get("latency_ms"):
                d[key]["latency"].append(resp["latency_ms"])

        # Save to Supabase
        if run_id:
            save_result(run_id, q, resp, status, pipeline, sector, judge_result)
            update_question_bank(q, status, resp.get("latency_ms", 0))

        # Track in state
        state.setdefault("asked_ids", []).append(qid)
        state["total_asked"] = state.get("total_asked", 0) + 1

        # Log progress
        symbol = "+" if passed else ("T" if status == "timeout" else "-")
        pct = stats["pass"] / stats["total"] * 100 if stats["total"] else 0
        src_count = len(resp.get("sources", []))
        if (i + 1) % 5 == 0 or not passed:
            log(f"  [{symbol}] {i+1}/{len(questions)} | {qid[:25]:25} | {pipeline:13} | {sector:10} | "
                f"{resp.get('latency_ms',0):5}ms | {status:7} | src={src_count} | running {pct:.0f}%")

        # Save results JSON backup
        results_json.append({
            "id": qid, "pipeline": pipeline, "sector": sector,
            "status": status, "latency_ms": resp.get("latency_ms", 0),
            "sources": len(resp.get("sources", [])),
            "answer_preview": resp.get("answer", "")[:200],
        })

        time.sleep(1.5)  # Rate limiting

    # Finalize
    if run_id:
        finalize_run(run_id, stats)

    state["run_count"] = state.get("run_count", 0) + 1
    state["asked_ids"] = state.get("asked_ids", [])[-5000:]  # Trim
    save_state(state)

    # JSON backup
    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(DATA_DIR, f"blast-{ts}.json")
    with open(backup, "w") as f:
        json.dump({
            "run_id": run_id, "timestamp": ts,
            "stats": stats, "pipeline_stats": {k: {**v, "latency": []} for k, v in pipeline_stats.items()},
            "sector_stats": sector_stats, "results": results_json,
        }, f, indent=2, ensure_ascii=False)

    # Report
    total = stats["total"]
    pct = stats["pass"] / total * 100 if total else 0
    log("")
    log("=" * 70)
    log(f"  EVAL BLAST COMPLETE — {total}Q | {pct:.1f}% accuracy")
    log("=" * 70)
    for p, s in sorted(pipeline_stats.items()):
        ppct = s["pass"] / s["total"] * 100 if s["total"] else 0
        avg_lat = sum(s["latency"]) / len(s["latency"]) if s["latency"] else 0
        log(f"  {p:15} {s['pass']}/{s['total']} ({ppct:.0f}%) | {avg_lat:.0f}ms avg")
    log("")
    for s, st in sorted(sector_stats.items()):
        spct = st["pass"] / st["total"] * 100 if st["total"] else 0
        log(f"  {s:15} {st['pass']}/{st['total']} ({spct:.0f}%)")
    log("=" * 70)

    return {"total": total, "pass": stats["pass"], "fail": stats["fail"],
            "accuracy": pct, "run_id": run_id}


def backfill_question_bank():
    """Seed the eval_question_bank table from the full dataset."""
    log("Backfilling question bank from dataset...")
    all_q = load_questions()
    log(f"  {len(all_q)} questions to insert")

    batch = []
    for i, q in enumerate(all_q):
        qid = q.get("id", "")
        if not qid:
            continue
        batch.append((
            qid, q.get("question", ""), q.get("sector", ""),
            q.get("pipeline", "standard"), q.get("expected_contains", ""),
            q.get("difficulty", "medium"), q.get("category", ""),
            q.get("language", "fr"), q.get("dataset_source", "generated"),
        ))

        if len(batch) >= 500:
            _insert_bank_batch(batch)
            batch = []
            if (i + 1) % 5000 == 0:
                log(f"  ... {i+1}/{len(all_q)}")

    if batch:
        _insert_bank_batch(batch)

    log(f"  Done: {len(all_q)} questions seeded")

def _insert_bank_batch(batch):
    conn = get_db()
    if not conn:
        return
    with conn.cursor() as cur:
        args = ",".join(cur.mogrify(
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s)", b).decode() for b in batch)
        cur.execute(f"""
            INSERT INTO eval_question_bank
                (id, question, sector, pipeline, expected_contains, difficulty,
                 category, language, dataset_source)
            VALUES {args}
            ON CONFLICT (id) DO NOTHING
        """)


def daemon_loop(interval, max_q, pipeline_filter, sector_filter):
    log(f"DAEMON MODE: every {interval}s, {max_q}Q per cycle")
    while True:
        try:
            run_blast(max_q, pipeline_filter, sector_filter, triggered_by="daemon")
        except Exception as e:
            log(f"Cycle error: {e}")
            traceback.print_exc()
        log(f"Sleeping {interval}s until next cycle...")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Eval Blast — Full-blast pipeline evaluation")
    parser.add_argument("--max", type=int, default=50)
    parser.add_argument("--pipeline", default=None)
    parser.add_argument("--sector", default=None)
    parser.add_argument("--daemon", type=int, default=0, help="Continuous mode interval (seconds)")
    parser.add_argument("--backfill", action="store_true", help="Seed question bank from dataset")
    parser.add_argument("--triggered-by", default="manual")
    args = parser.parse_args()

    if args.backfill:
        backfill_question_bank()
        return

    if args.daemon > 0:
        daemon_loop(args.daemon, args.max, args.pipeline, args.sector)
    else:
        run_blast(args.max, args.pipeline, args.sector, triggered_by=args.triggered_by)


if __name__ == "__main__":
    main()
