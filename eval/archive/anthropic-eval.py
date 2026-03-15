#!/usr/bin/env python3
"""
Anthropic-Style Evaluation — Multi-dimensional rubric scoring with golden answers.

Uses expert questions with golden_answer + source_url from eval_question_bank.
Scores on 5 dimensions: Faithfulness, Relevance, Completeness, Coherence, Grounding.

Usage:
  source .env.local
  python3 eval/anthropic-eval.py --sector all --max 50
  python3 eval/anthropic-eval.py --sector finance --pipeline standard --max 20
  python3 eval/anthropic-eval.py --full   # All 170 expert questions
"""

# ── IPv4 fix ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import json
import os
import re
import ssl
import sys
import time
import argparse
from datetime import datetime, timezone
from urllib import request, error

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "eval")

# Load env
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip().lstrip("export").strip()
                v = v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

DB_URL = os.environ.get("DATABASE_URL", "")
LITELLM_URL = os.environ.get("LITELLM_URL",
    "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")

N8N_HOSTS = [h.strip() for h in os.environ.get("N8N_ALL_HOSTS", "").split(",") if h.strip()]
if not N8N_HOSTS:
    N8N_HOSTS = ["https://lbjlincoln-nomos-rag-engine.hf.space"]

WEBHOOK_PATHS = {
    "standard":     "/webhook/rag-multi-index-v3",
    "graph":        "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

_ssl = ssl.create_default_context()
_ssl.check_hostname = False
_ssl.verify_mode = ssl.CERT_NONE

_rr = {}

# ── Anthropic-style 5-dimension rubric ──
RUBRIC_PROMPT = """You are a senior expert evaluator for a RAG system specialized in {sector}.

Score the ANSWER against the REFERENCE ANSWER on 5 dimensions (0-100 each).

QUESTION: {question}
REFERENCE ANSWER (gold standard): {golden_answer}
SOURCE DOCUMENT: {source_url}
ACTUAL RAG ANSWER: {answer}

DIMENSIONS:
1. FAITHFULNESS (0-100): Does the answer contain only factually correct information? No hallucinations?
2. RELEVANCE (0-100): Does the answer directly address the question asked?
3. COMPLETENESS (0-100): Does the answer cover all key points from the reference answer?
4. COHERENCE (0-100): Is the answer well-structured, clear, and professional?
5. GROUNDING (0-100): Does the answer cite or reference source material?

SCORING GUIDE:
- 90-100: Expert-level, matches or exceeds reference
- 70-89: Good, covers main points with minor gaps
- 50-69: Partial, some correct info but significant gaps
- 25-49: Poor, mostly incorrect or off-topic
- 0-24: Failure, empty/irrelevant/hallucinated

Respond with EXACTLY this JSON (no markdown, no extra text):
{{"faithfulness": N, "relevance": N, "completeness": N, "coherence": N, "grounding": N, "pass": true/false, "overall": N, "reasoning": "1-2 sentences"}}

Where "overall" is the weighted average: faithfulness*0.3 + relevance*0.25 + completeness*0.25 + coherence*0.1 + grounding*0.1
And "pass" = overall >= 60"""


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def get_db():
    import psycopg2
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    with conn.cursor() as c:
        c.execute("SET search_path TO public")
    return conn


def load_expert_questions(sector_filter="all", pipeline_filter="all", max_q=0):
    """Load expert questions with golden answers from DB + files."""
    questions = []

    # Source 1: Supabase eval_question_bank
    try:
        conn = get_db()
        with conn.cursor() as c:
            sql = """
                SELECT id, question, golden_answer, expected_contains, sector,
                       source_url, pipeline
                FROM eval_question_bank
                WHERE golden_answer IS NOT NULL AND golden_answer != ''
            """
            params = []
            if sector_filter != "all":
                sql += " AND sector = %s"
                params.append(sector_filter)
            sql += " ORDER BY sector, id"
            c.execute(sql, params)
            for row in c.fetchall():
                q = {
                    "id": str(row[0]), "question": row[1],
                    "golden_answer": row[2], "expected_contains": row[3] or "",
                    "sector": row[4], "source_url": row[5] or "",
                    "pipeline": row[6] or "standard", "source": "db",
                }
                questions.append(q)
        conn.close()
    except Exception as e:
        log(f"DB load error: {e}")

    # Source 2: Expert JSON files
    import glob
    pattern = "all" if sector_filter == "all" else sector_filter
    files = sorted(glob.glob(os.path.join(REPO_ROOT, "sectors", "eval-datasets", f"expert-*-generated.json")))
    for f in files:
        if sector_filter != "all" and sector_filter not in f:
            continue
        try:
            with open(f) as fh:
                data = json.load(fh)
            items = data if isinstance(data, list) else data.get("questions", [])
            for item in items:
                if not item.get("golden_answer"):
                    continue
                qid = item.get("id", f"file-{os.path.basename(f)}-{len(questions)}")
                # Avoid duplicates (check by question text)
                if any(q["question"] == item["question"] for q in questions):
                    continue
                questions.append({
                    "id": qid, "question": item["question"],
                    "golden_answer": item["golden_answer"],
                    "expected_contains": item.get("expected_contains", ""),
                    "sector": item.get("sector", "finance"),
                    "source_url": item.get("source_url", ""),
                    "pipeline": item.get("pipeline", "standard"),
                    "source": "file",
                })
        except Exception as e:
            log(f"File load error {f}: {e}")

    if pipeline_filter != "all":
        questions = [q for q in questions if q["pipeline"] == pipeline_filter]

    if max_q > 0:
        questions = questions[:max_q]

    return questions


def call_pipeline(question, sector, pipeline, timeout=120):
    """Call RAG pipeline and return answer."""
    path = WEBHOOK_PATHS.get(pipeline)
    if not path:
        return {"ok": False, "answer": "", "latency_ms": 0, "error": f"Unknown pipeline: {pipeline}"}

    idx = _rr.get(pipeline, 0)
    _rr[pipeline] = idx + 1
    host = N8N_HOSTS[idx % len(N8N_HOSTS)]
    endpoint = f"{host}{path}"

    payload = json.dumps({
        "question": question, "query": question,
        "sector": sector, "tenant_id": sector,
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
            return {"ok": True, "answer": answer, "latency_ms": latency}
    except Exception as e:
        return {"ok": False, "answer": "", "latency_ms": 0, "error": str(e)[:150]}


def llm_judge_rubric(question, answer, golden_answer, source_url, sector, timeout=20):
    """Call LLM judge with 5-dimension rubric."""
    prompt = RUBRIC_PROMPT.format(
        question=question[:500],
        golden_answer=golden_answer[:800],
        source_url=source_url[:200] if source_url else "N/A",
        answer=str(answer)[:1000],
        sector=sector,
    )

    data = json.dumps({
        "model": "smart",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0,
    }).encode()

    req = request.Request(LITELLM_URL, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}",
    }, method="POST")

    try:
        with request.urlopen(req, context=_ssl, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            raw = result["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = re.sub(r'^```\w*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)
            scores = json.loads(raw)
            return {
                "faithfulness": int(scores.get("faithfulness", 0)),
                "relevance": int(scores.get("relevance", 0)),
                "completeness": int(scores.get("completeness", 0)),
                "coherence": int(scores.get("coherence", 0)),
                "grounding": int(scores.get("grounding", 0)),
                "overall": int(scores.get("overall", 0)),
                "pass": bool(scores.get("pass", False)),
                "reasoning": str(scores.get("reasoning", ""))[:300],
                "judge_method": "rubric_llm",
            }
    except Exception as e:
        # Fallback to simple keyword match
        from eval.llm_judge import _keyword_fallback
        passed = _keyword_fallback(answer, golden_answer[:50])
        return {
            "faithfulness": 50 if passed else 10,
            "relevance": 50 if passed else 10,
            "completeness": 40 if passed else 5,
            "coherence": 50 if passed else 20,
            "grounding": 10,
            "overall": 40 if passed else 10,
            "pass": passed,
            "reasoning": f"Keyword fallback (LLM error: {str(e)[:80]})",
            "judge_method": "keyword_fallback",
        }


def run_eval(sector_filter, pipeline_filter, max_questions, delay):
    """Run Anthropic-style evaluation."""
    questions = load_expert_questions(sector_filter, pipeline_filter, max_questions)
    log(f"Anthropic Eval: {len(questions)} expert questions with golden answers")
    log(f"Sector: {sector_filter} | Pipeline: {pipeline_filter}")
    log(f"Hosts: {len(N8N_HOSTS)} Spaces")

    if not questions:
        log("No expert questions found. Generate with: python3 eval/generate-expert-questions.py")
        return {}

    results = []
    stats = {"total": 0, "pass": 0, "fail": 0, "error": 0}
    dimension_totals = {"faithfulness": [], "relevance": [], "completeness": [],
                        "coherence": [], "grounding": [], "overall": []}
    sector_stats = {}
    pipeline_stats = {}

    start_time = datetime.now(timezone.utc)

    for i, q in enumerate(questions):
        pipeline = q["pipeline"]
        sector = q["sector"]
        timeout = 300 if pipeline in ("orchestrator", "quantitative", "graph") else 120

        resp = call_pipeline(q["question"], sector, pipeline, timeout)
        stats["total"] += 1

        if resp["ok"] and resp["answer"] and len(resp["answer"]) > 10:
            scores = llm_judge_rubric(
                q["question"], resp["answer"],
                q["golden_answer"], q["source_url"], sector
            )
        elif not resp["ok"]:
            stats["error"] += 1
            scores = {"faithfulness": 0, "relevance": 0, "completeness": 0,
                      "coherence": 0, "grounding": 0, "overall": 0,
                      "pass": False, "reasoning": f"Pipeline error: {resp.get('error','')}",
                      "judge_method": "error"}
        else:
            scores = {"faithfulness": 0, "relevance": 0, "completeness": 0,
                      "coherence": 0, "grounding": 0, "overall": 0,
                      "pass": False, "reasoning": "Empty or too short answer",
                      "judge_method": "empty"}

        if scores["pass"]:
            stats["pass"] += 1
        else:
            stats["fail"] += 1

        for dim in dimension_totals:
            dimension_totals[dim].append(scores.get(dim, 0))

        # Per-sector
        if sector not in sector_stats:
            sector_stats[sector] = {"pass": 0, "fail": 0, "total": 0, "scores": []}
        sector_stats[sector]["total"] += 1
        sector_stats[sector]["pass" if scores["pass"] else "fail"] += 1
        sector_stats[sector]["scores"].append(scores.get("overall", 0))

        # Per-pipeline
        if pipeline not in pipeline_stats:
            pipeline_stats[pipeline] = {"pass": 0, "fail": 0, "total": 0, "scores": [], "latency": []}
        pipeline_stats[pipeline]["total"] += 1
        pipeline_stats[pipeline]["pass" if scores["pass"] else "fail"] += 1
        pipeline_stats[pipeline]["scores"].append(scores.get("overall", 0))
        if resp["latency_ms"]:
            pipeline_stats[pipeline]["latency"].append(resp["latency_ms"])

        symbol = "[+]" if scores["pass"] else "[-]"
        log(f"  {symbol} {i+1}/{len(questions)} | {q['id'][:20]} | {pipeline} | {sector} | "
            f"overall={scores['overall']} | {resp['latency_ms']}ms | {scores.get('reasoning','')[:60]}")

        results.append({
            "id": q["id"], "question": q["question"][:100],
            "pipeline": pipeline, "sector": sector,
            "status": "pass" if scores["pass"] else "fail",
            "latency_ms": resp["latency_ms"],
            "answer_preview": resp["answer"][:150] if resp["answer"] else "",
            "golden_preview": q["golden_answer"][:100],
            **{k: scores.get(k, 0) for k in ["faithfulness", "relevance", "completeness",
                                               "coherence", "grounding", "overall"]},
            "reasoning": scores.get("reasoning", ""),
            "judge_method": scores.get("judge_method", ""),
        })

        # Write to Supabase eval_results
        try:
            _write_result_to_db(q, resp, scores)
        except Exception:
            pass

        if (i + 1) % 10 == 0:
            _save_report(results, stats, dimension_totals, sector_stats, pipeline_stats, start_time, len(questions))

        time.sleep(delay)

    _save_report(results, stats, dimension_totals, sector_stats, pipeline_stats, start_time, len(questions))

    # Final report
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    log("")
    log("=" * 70)
    log("  ANTHROPIC-STYLE EVAL RESULTS")
    log("=" * 70)
    pct = stats['pass'] / stats['total'] * 100 if stats['total'] else 0
    log(f"  Total: {stats['total']} | Pass: {stats['pass']} | Fail: {stats['fail']} | Error: {stats['error']}")
    log(f"  Overall Pass Rate: {pct:.1f}%")
    log(f"  Duration: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    log("")
    log("  Dimension Averages:")
    for dim, vals in dimension_totals.items():
        avg = sum(vals) / len(vals) if vals else 0
        log(f"    {dim:15s}: {avg:.1f}/100")
    log("")
    log("  Per Pipeline:")
    for p, s in sorted(pipeline_stats.items()):
        ppct = s['pass'] / s['total'] * 100 if s['total'] else 0
        avg_score = sum(s['scores']) / len(s['scores']) if s['scores'] else 0
        avg_lat = sum(s['latency']) / len(s['latency']) if s['latency'] else 0
        log(f"    {p:15s}: {s['pass']}/{s['total']} ({ppct:.0f}%) | avg_score={avg_score:.0f} | avg_lat={avg_lat:.0f}ms")
    log("")
    log("  Per Sector:")
    for s, st in sorted(sector_stats.items()):
        spct = st['pass'] / st['total'] * 100 if st['total'] else 0
        avg_score = sum(st['scores']) / len(st['scores']) if st['scores'] else 0
        log(f"    {s:15s}: {st['pass']}/{st['total']} ({spct:.0f}%) | avg_score={avg_score:.0f}")
    log("=" * 70)

    return stats


def _write_result_to_db(q, resp, scores):
    """Write result to Supabase eval_results."""
    conn = get_db()
    with conn.cursor() as c:
        c.execute("""
            INSERT INTO eval_results (question_id, question, pipeline, sector,
                                      status, latency_ms, answer_preview,
                                      judge_score, judge_classification)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            q["id"], q["question"][:500], q["pipeline"], q["sector"],
            "pass" if scores["pass"] else "fail",
            resp["latency_ms"],
            resp["answer"][:500] if resp["answer"] else "",
            min(scores.get("overall", 0) // 5, 20),  # Scale to 0-20
            "GOOD" if scores.get("overall", 0) >= 70 else
            "MEDIUM" if scores.get("overall", 0) >= 40 else "BAD",
        ))
    conn.close()


def _save_report(results, stats, dimensions, sector_stats, pipeline_stats, start_time, total_planned):
    """Save evaluation report to JSON."""
    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    dim_avgs = {}
    for dim, vals in dimensions.items():
        dim_avgs[dim] = round(sum(vals) / len(vals), 1) if vals else 0

    ps_clean = {}
    for p, s in pipeline_stats.items():
        ps_clean[p] = {
            "pass": s["pass"], "fail": s["fail"], "total": s["total"],
            "accuracy": round(s["pass"] / s["total"] * 100, 1) if s["total"] else 0,
            "avg_score": round(sum(s["scores"]) / len(s["scores"]), 1) if s["scores"] else 0,
            "avg_latency_ms": int(sum(s["latency"]) / len(s["latency"])) if s["latency"] else 0,
        }

    ss_clean = {}
    for s, st in sector_stats.items():
        ss_clean[s] = {
            "pass": st["pass"], "fail": st["fail"], "total": st["total"],
            "accuracy": round(st["pass"] / st["total"] * 100, 1) if st["total"] else 0,
            "avg_score": round(sum(st["scores"]) / len(st["scores"]), 1) if st["scores"] else 0,
        }

    output = {
        "eval_type": "anthropic_style",
        "metadata": {
            "started": start_time.isoformat(),
            "updated": datetime.now(timezone.utc).isoformat(),
            "total_planned": total_planned,
            "total_completed": stats["total"],
            "hosts": N8N_HOSTS,
            "judge": "LLM rubric (5-dimension)",
        },
        "summary": {
            **stats,
            "accuracy": round(stats["pass"] / stats["total"] * 100, 1) if stats["total"] else 0,
        },
        "dimensions": dim_avgs,
        "pipeline_stats": ps_clean,
        "sector_stats": ss_clean,
        "results": results,
    }

    outfile = os.path.join(DATA_DIR, f"anthropic-eval-{ts}.json")
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Also write latest
    latest = os.path.join(DATA_DIR, "anthropic-eval-latest.json")
    with open(latest, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Anthropic-Style RAG Evaluation")
    parser.add_argument("--sector", default="all", choices=["finance", "btp", "juridique", "industrie", "all"])
    parser.add_argument("--pipeline", default="all", choices=["standard", "graph", "quantitative", "orchestrator", "all"])
    parser.add_argument("--max", type=int, default=0, help="Max questions (0=all)")
    parser.add_argument("--full", action="store_true", help="Run all expert questions")
    parser.add_argument("--delay", type=float, default=3, help="Seconds between queries")
    args = parser.parse_args()

    max_q = 0 if args.full else (args.max if args.max else 50)
    run_eval(args.sector, args.pipeline, max_q, args.delay)


if __name__ == "__main__":
    main()
