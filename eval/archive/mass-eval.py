#!/usr/bin/env python3
"""
Mass Evaluation — Run thousands of questions against RAG pipelines.

Loads questions from sector-full-eval-extended.json, sends to n8n webhooks
(round-robin across 3 Spaces), checks expected_contains for pass/fail.

Usage:
  source .env.local
  python3 eval/mass-eval.py --pipeline standard --max 500
  python3 eval/mass-eval.py --pipeline all --max 100
  python3 eval/mass-eval.py --full   # All 5K+ questions
  nohup python3 eval/mass-eval.py --full > data/eval/mass-eval.log 2>&1 &
"""

import json
import os
import re
import sys
import time
import argparse
from datetime import datetime, timezone
from urllib import request, error

# Force unbuffered
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "eval")
QUESTIONS_FILE = os.path.join(REPO_ROOT, "sectors", "eval-datasets", "sector-full-eval-extended.json")
RESULTS_FILE = os.path.join(DATA_DIR, "mass-eval-results.json")

N8N_HOSTS = [h.strip() for h in os.environ.get("N8N_ALL_HOSTS", "").split(",") if h.strip()]
if not N8N_HOSTS:
    N8N_HOSTS = ["https://lbjlincoln-nomos-rag-engine.hf.space"]

WEBHOOK_PATHS = {
    "standard":     "/webhook/rag-multi-index-v3",
    "graph":        "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

_rr = {}


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def normalize(text):
    """Normalize for fuzzy matching."""
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    text = str(text)
    text = re.sub(r'(\d)[,\s](\d)', r'\1\2', text)
    text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
    return text.replace('$', '').replace('%', '').lower()


def get_endpoint(pipeline):
    """Round-robin across Spaces."""
    path = WEBHOOK_PATHS.get(pipeline)
    if not path:
        return None
    idx = _rr.get(pipeline, 0)
    _rr[pipeline] = idx + 1
    host = N8N_HOSTS[idx % len(N8N_HOSTS)]
    return f"{host}{path}"


def call_pipeline(endpoint, query, sector, timeout=120):
    """Call RAG pipeline and return response."""
    payload = json.dumps({
        "query": query,
        "question": query,
        "tenant_id": sector,
        "sector": sector,
        "top_k": 10,
        "include_sources": True,
    }).encode()

    req = request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
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
    except error.HTTPError as e:
        return {"ok": False, "answer": "", "latency_ms": 0, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "answer": "", "latency_ms": 0, "error": str(e)[:150]}


def load_questions():
    """Load questions from extended dataset."""
    with open(QUESTIONS_FILE) as f:
        data = json.load(f)
    return data.get("questions", [])


def run_eval(pipeline_filter, max_questions, delay):
    """Run mass evaluation."""
    questions = load_questions()

    if pipeline_filter != "all":
        questions = [q for q in questions if q.get("pipeline") == pipeline_filter]

    if max_questions > 0:
        questions = questions[:max_questions]

    log(f"Mass Eval: {len(questions)} questions, pipeline={pipeline_filter}")
    log(f"Hosts: {len(N8N_HOSTS)} Spaces")

    results = []
    stats = {"total": 0, "pass": 0, "fail": 0, "error": 0}
    pipeline_stats = {}
    sector_stats = {}

    start_time = datetime.now(timezone.utc)

    for i, q in enumerate(questions):
        qid = q.get("id", f"q{i}")
        question = q.get("question", "")
        expected = q.get("expected_contains", "")
        pipeline = q.get("pipeline", "standard")
        sector = q.get("sector", "finance")

        endpoint = get_endpoint(pipeline)
        if not endpoint:
            continue

        # Timeout: orchestrator/quant/graph need more time
        timeout = 300 if pipeline in ("orchestrator", "quantitative", "graph") else 120

        resp = call_pipeline(endpoint, question, sector, timeout)
        stats["total"] += 1

        passed = False
        if resp["ok"] and resp["answer"]:
            if expected:
                # Handle list or string expected_contains
                if isinstance(expected, list):
                    passed = any(normalize(e) in normalize(resp["answer"]) for e in expected if e)
                else:
                    passed = normalize(str(expected)) in normalize(resp["answer"])
            else:
                passed = len(resp["answer"]) > 10

        status = "pass" if passed else ("error" if not resp["ok"] else "fail")
        if passed:
            stats["pass"] += 1
        elif not resp["ok"]:
            stats["error"] += 1
        else:
            stats["fail"] += 1

        # Per-pipeline stats
        if pipeline not in pipeline_stats:
            pipeline_stats[pipeline] = {"pass": 0, "fail": 0, "error": 0, "total": 0, "latency": []}
        pipeline_stats[pipeline]["total"] += 1
        pipeline_stats[pipeline][status] += 1
        if resp["latency_ms"]:
            pipeline_stats[pipeline]["latency"].append(resp["latency_ms"])

        # Per-sector stats
        if sector not in sector_stats:
            sector_stats[sector] = {"pass": 0, "fail": 0, "error": 0, "total": 0}
        sector_stats[sector]["total"] += 1
        sector_stats[sector][status] += 1

        symbol = "[+]" if passed else "[-]"
        if (i + 1) % 10 == 0 or not passed:
            pct = stats["pass"] / stats["total"] * 100 if stats["total"] else 0
            log(f"  {symbol} {i+1}/{len(questions)} | {qid} | {pipeline} | {sector} | {resp['latency_ms']}ms | {status} | running {pct:.0f}%")
            if not passed and resp.get("error"):
                log(f"       ERR: {resp['error'][:80]}")

        results.append({
            "id": qid,
            "pipeline": pipeline,
            "sector": sector,
            "status": status,
            "latency_ms": resp["latency_ms"],
            "answer_preview": resp["answer"][:150] if resp["answer"] else "",
        })

        # Save progress every 50 questions
        if (i + 1) % 50 == 0:
            save_results(results, stats, pipeline_stats, sector_stats, start_time, len(questions))

        time.sleep(delay)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    save_results(results, stats, pipeline_stats, sector_stats, start_time, len(questions))

    # Final report
    log("")
    log("=" * 60)
    log("  MASS EVAL RESULTS")
    log("=" * 60)
    log(f"  Total: {stats['total']} | Pass: {stats['pass']} | Fail: {stats['fail']} | Error: {stats['error']}")
    pct = stats['pass'] / stats['total'] * 100 if stats['total'] else 0
    log(f"  Overall: {pct:.1f}%")
    log(f"  Duration: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    log("")
    log("  Per Pipeline:")
    for p, s in sorted(pipeline_stats.items()):
        ppct = s['pass'] / s['total'] * 100 if s['total'] else 0
        avg_lat = sum(s['latency']) / len(s['latency']) if s['latency'] else 0
        log(f"    {p}: {s['pass']}/{s['total']} ({ppct:.0f}%) | avg {avg_lat:.0f}ms")
    log("")
    log("  Per Sector:")
    for s, st in sorted(sector_stats.items()):
        spct = st['pass'] / st['total'] * 100 if st['total'] else 0
        log(f"    {s}: {st['pass']}/{st['total']} ({spct:.0f}%)")
    log("=" * 60)

    return stats


def save_results(results, stats, pipeline_stats, sector_stats, start_time, total_planned):
    """Save results to JSON."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Clean latency lists for JSON serialization
    ps_clean = {}
    for p, s in pipeline_stats.items():
        ps_clean[p] = {
            "pass": s["pass"], "fail": s["fail"], "error": s["error"], "total": s["total"],
            "avg_latency_ms": int(sum(s["latency"]) / len(s["latency"])) if s["latency"] else 0,
            "accuracy": round(s["pass"] / s["total"] * 100, 1) if s["total"] else 0,
        }

    output = {
        "metadata": {
            "started": start_time.isoformat(),
            "updated": datetime.now(timezone.utc).isoformat(),
            "total_planned": total_planned,
            "total_completed": stats["total"],
            "hosts": N8N_HOSTS,
        },
        "summary": {
            **stats,
            "accuracy": round(stats["pass"] / stats["total"] * 100, 1) if stats["total"] else 0,
        },
        "pipeline_stats": ps_clean,
        "sector_stats": sector_stats,
        "results": results[-500:],  # Keep last 500 for file size
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Mass RAG Evaluation")
    parser.add_argument("--pipeline", default="all", choices=["standard", "graph", "quantitative", "orchestrator", "all"])
    parser.add_argument("--max", type=int, default=0, help="Max questions (0=all)")
    parser.add_argument("--full", action="store_true", help="Run all 5K+ questions")
    parser.add_argument("--delay", type=float, default=2, help="Seconds between queries")
    args = parser.parse_args()

    max_q = 0 if args.full else (args.max if args.max else 100)

    run_eval(args.pipeline, max_q, args.delay)


if __name__ == "__main__":
    main()
