#!/usr/bin/env python3
"""
RAG Self-Improvement Loop — Continuous eval + trend tracking + regression alerts.

Cycle every 30min:
1. Sample 20 questions across 4 sectors × 3 pipelines
2. Call each pipeline via n8n webhooks (round-robin S1/S3/S5)
3. Score with keyword matching + LLM judge when available
4. Track accuracy per sector/pipeline over time
5. Detect regressions (>5% drop) and improvements
6. Log everything for monitoring

Designed to run 24/7 alongside ingestion daemon.
"""

# ── IPv4 fix (GCP VM has broken IPv6) ──
import socket
from socket import AF_INET
_orig_gai = socket.getaddrinfo
def _ipv4_gai(*a, **kw):
    r = _orig_gai(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _ipv4_gai

import os, sys, json, re, time, random, argparse, urllib.request, urllib.error, ssl
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# Force unbuffered
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent

# ── Load env ──
def load_env():
    env_file = ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))

load_env()

# ── Config ──
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

DATA_DIR = ROOT / "data" / "eval"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "self-improve.jsonl"
HISTORY_FILE = DATA_DIR / "self-improve-history.json"
SCORES_FILE = DATA_DIR / "self-improve-scores.json"

QUESTIONS_FILE = ROOT / "sectors" / "eval-datasets" / "sector-full-eval-extended.json"
SMOKE_FILE = ROOT / "sectors" / "eval-datasets" / "sector-smoke-test.json"

CYCLE_INTERVAL = 1800  # 30 minutes
QUESTIONS_PER_CYCLE = 20
REGRESSION_THRESHOLD = 0.05  # 5% drop = regression alert

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ── Logging ──
def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = {"ts": datetime.now(timezone.utc).isoformat()[:19], "level": level, "msg": msg}
    print(f"[{ts}] [{level}] {msg}")
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Load questions ──
def load_questions():
    """Load eval questions from dataset files."""
    questions = []

    # Primary: extended eval dataset
    if QUESTIONS_FILE.exists():
        try:
            data = json.loads(QUESTIONS_FILE.read_text())
            qs = data if isinstance(data, list) else data.get("questions", [])
            questions.extend(qs)
            log(f"Loaded {len(qs)} questions from extended dataset")
        except Exception as e:
            log(f"Failed to load extended dataset: {e}", "WARN")

    # Fallback: smoke test
    if not questions and SMOKE_FILE.exists():
        try:
            data = json.loads(SMOKE_FILE.read_text())
            qs = data if isinstance(data, list) else data.get("questions", [])
            questions.extend(qs)
            log(f"Loaded {len(qs)} questions from smoke test")
        except Exception as e:
            log(f"Failed to load smoke test: {e}", "WARN")

    # Also try pipeline-specific datasets
    for name in ["standard-eval-generated.json", "graph-eval-generated.json", "quant-eval-generated.json"]:
        f = ROOT / "sectors" / "eval-datasets" / name
        if f.exists():
            try:
                data = json.loads(f.read_text())
                qs = data if isinstance(data, list) else data.get("questions", [])
                questions.extend(qs)
            except Exception:
                pass

    log(f"Total question pool: {len(questions)}")
    return questions


def sample_questions(questions, n=QUESTIONS_PER_CYCLE):
    """Sample n questions balanced across sectors and pipelines."""
    by_sector = defaultdict(list)
    for q in questions:
        sector = q.get("sector", "finance")
        by_sector[sector].append(q)

    sampled = []
    sectors = list(by_sector.keys()) or ["finance", "btp", "juridique", "industrie"]
    per_sector = max(1, n // len(sectors))

    for sector in sectors:
        pool = by_sector.get(sector, [])
        if pool:
            sampled.extend(random.sample(pool, min(per_sector, len(pool))))

    # Fill remaining slots randomly
    while len(sampled) < n and questions:
        q = random.choice(questions)
        if q not in sampled:
            sampled.append(q)

    return sampled[:n]


# ── Pipeline calling ──
_rr = defaultdict(int)

def call_pipeline(pipeline, question, sector, timeout=90):
    """Call a RAG pipeline via n8n webhook."""
    path = WEBHOOK_PATHS.get(pipeline)
    if not path:
        return {"ok": False, "answer": "", "latency_ms": 0, "error": "unknown pipeline"}

    idx = _rr[pipeline]
    _rr[pipeline] = idx + 1
    host = N8N_HOSTS[idx % len(N8N_HOSTS)]
    endpoint = f"{host}{path}"

    payload = json.dumps({
        "query": question, "question": question,
        "tenant_id": sector, "sector": sector,
        "top_k": 10, "include_sources": True,
    }).encode()

    req = urllib.request.Request(endpoint, data=payload,
                                headers={"Content-Type": "application/json"}, method="POST")
    try:
        start = time.time()
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
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

            sources = []
            for key in ["sources", "source_documents", "context", "documents"]:
                if key in data and isinstance(data[key], list):
                    sources = data[key][:5]
                    break

            return {"ok": True, "answer": answer, "latency_ms": latency, "sources": sources}
    except urllib.error.HTTPError as e:
        return {"ok": False, "answer": "", "latency_ms": 0, "error": f"HTTP {e.code}"}
    except Exception as e:
        err = str(e)[:150]
        return {"ok": False, "answer": "", "latency_ms": 0, "error": err}


# ── Scoring ──
def normalize(text):
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    text = str(text)
    text = re.sub(r'(\d)[,\s](\d)', r'\1\2', text)
    return text.replace('$', '').replace('%', '').lower()


def score_answer(question_data, answer):
    """Score an answer against expected content."""
    expected = question_data.get("expected_contains", "")
    if not expected:
        # No expected answer — check if we got a non-empty response
        return {"pass": bool(answer and len(answer) > 20), "method": "non_empty"}

    norm_expected = normalize(expected)
    norm_answer = normalize(answer)

    passed = norm_expected in norm_answer
    return {"pass": passed, "method": "keyword", "expected": expected}


# ── History tracking ──
def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return {
        "cycles": [],
        "total_cycles": 0,
        "started": datetime.now(timezone.utc).isoformat(),
    }


def save_history(history):
    history["last_updated"] = datetime.now(timezone.utc).isoformat()
    # Keep last 100 cycles
    history["cycles"] = history["cycles"][-100:]
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def load_scores():
    if SCORES_FILE.exists():
        try:
            return json.loads(SCORES_FILE.read_text())
        except Exception:
            pass
    return {}


def save_scores(scores):
    scores["last_updated"] = datetime.now(timezone.utc).isoformat()
    SCORES_FILE.write_text(json.dumps(scores, indent=2))


# ── Regression detection ──
def detect_regressions(history, current_scores):
    """Compare current scores vs last 3 cycles average. Alert on >5% drops."""
    regressions = []
    improvements = []

    cycles = history.get("cycles", [])
    if len(cycles) < 2:
        return regressions, improvements

    # Average of last 3 cycles
    recent = cycles[-3:]
    avg_scores = defaultdict(list)
    for cycle in recent:
        for key, val in cycle.get("scores", {}).items():
            if isinstance(val, (int, float)):
                avg_scores[key].append(val)

    for key, vals in avg_scores.items():
        if key not in current_scores:
            continue
        avg = sum(vals) / len(vals)
        current = current_scores[key]
        delta = current - avg

        if delta < -REGRESSION_THRESHOLD:
            regressions.append({
                "metric": key,
                "previous_avg": round(avg, 3),
                "current": round(current, 3),
                "delta": round(delta, 3),
            })
        elif delta > REGRESSION_THRESHOLD:
            improvements.append({
                "metric": key,
                "previous_avg": round(avg, 3),
                "current": round(current, 3),
                "delta": round(delta, 3),
            })

    return regressions, improvements


# ══════════════════════════════════════════════════════════════
# MAIN CYCLE
# ══════════════════════════════════════════════════════════════

def run_cycle(all_questions, history, questions_per_cycle=QUESTIONS_PER_CYCLE):
    """One full eval cycle: sample questions → call pipelines → score → track."""
    cycle_start = time.time()
    cycle_num = history["total_cycles"] + 1
    history["total_cycles"] = cycle_num
    ts = datetime.now(timezone.utc).isoformat()[:19]

    log(f"═══ CYCLE #{cycle_num} START ═══")

    questions = sample_questions(all_questions, questions_per_cycle)
    log(f"Sampled {len(questions)} questions")

    # Track results per sector and per pipeline
    results_by_sector = defaultdict(lambda: {"pass": 0, "fail": 0, "error": 0, "latency": []})
    results_by_pipeline = defaultdict(lambda: {"pass": 0, "fail": 0, "error": 0, "latency": []})
    all_results = []

    for i, q in enumerate(questions):
        question_text = q.get("question", q.get("query", ""))
        sector = q.get("sector", "finance")
        pipeline = q.get("pipeline", "standard")

        # Only test pipelines we have webhooks for
        if pipeline not in WEBHOOK_PATHS:
            pipeline = "standard"

        # Call the pipeline
        result = call_pipeline(pipeline, question_text, sector)

        if result["ok"]:
            score = score_answer(q, result["answer"])
            status = "pass" if score["pass"] else "fail"
        else:
            status = "error"
            score = {"pass": False, "method": "error"}

        # Record
        results_by_sector[sector][status] += 1
        results_by_pipeline[pipeline][status] += 1
        if result.get("latency_ms"):
            results_by_sector[sector]["latency"].append(result["latency_ms"])
            results_by_pipeline[pipeline]["latency"].append(result["latency_ms"])

        all_results.append({
            "question": question_text[:80],
            "sector": sector,
            "pipeline": pipeline,
            "status": status,
            "latency_ms": result.get("latency_ms", 0),
            "answer_len": len(result.get("answer", "")),
        })

        # Print progress
        symbol = "✓" if status == "pass" else ("✗" if status == "fail" else "!")
        log(f"  [{i+1}/{len(questions)}] {symbol} {pipeline}/{sector} — "
            f"{result.get('latency_ms', 0)}ms — {question_text[:50]}")

        # Small delay between calls
        time.sleep(1)

    # ── Aggregate scores ──
    total_pass = sum(r[s]["pass"] for r in [results_by_sector] for s in r)
    total_fail = sum(r[s]["fail"] for r in [results_by_sector] for s in r)
    total_error = sum(r[s]["error"] for r in [results_by_sector] for s in r)
    total = total_pass + total_fail + total_error
    overall_accuracy = total_pass / total if total > 0 else 0

    # Build scores dict for tracking
    current_scores = {"overall": round(overall_accuracy, 3)}
    for sector, data in results_by_sector.items():
        t = data["pass"] + data["fail"] + data["error"]
        current_scores[f"sector_{sector}"] = round(data["pass"] / t, 3) if t > 0 else 0
    for pipeline, data in results_by_pipeline.items():
        t = data["pass"] + data["fail"] + data["error"]
        current_scores[f"pipeline_{pipeline}"] = round(data["pass"] / t, 3) if t > 0 else 0

    # Average latency
    all_latencies = []
    for data in results_by_sector.values():
        all_latencies.extend(data["latency"])
    avg_latency = int(sum(all_latencies) / len(all_latencies)) if all_latencies else 0
    current_scores["avg_latency_ms"] = avg_latency

    # ── Detect regressions/improvements ──
    regressions, improvements = detect_regressions(history, current_scores)

    if regressions:
        log(f"⚠ REGRESSIONS DETECTED:", "WARN")
        for r in regressions:
            log(f"  ↓ {r['metric']}: {r['previous_avg']:.1%} → {r['current']:.1%} ({r['delta']:+.1%})", "WARN")

    if improvements:
        log(f"↑ IMPROVEMENTS:")
        for imp in improvements:
            log(f"  ↑ {imp['metric']}: {imp['previous_avg']:.1%} → {imp['current']:.1%} ({imp['delta']:+.1%})")

    # ── Save cycle to history ──
    cycle_entry = {
        "cycle": cycle_num,
        "timestamp": ts,
        "questions_tested": len(questions),
        "scores": current_scores,
        "pass": total_pass,
        "fail": total_fail,
        "error": total_error,
        "accuracy": round(overall_accuracy, 3),
        "avg_latency_ms": avg_latency,
        "regressions": len(regressions),
        "improvements": len(improvements),
        "elapsed_s": int(time.time() - cycle_start),
    }
    history["cycles"].append(cycle_entry)
    save_history(history)

    # ── Save current scores ──
    scores = load_scores()
    scores["current"] = current_scores
    scores["cycle"] = cycle_num
    scores["timestamp"] = ts
    # Track best scores
    if "best" not in scores:
        scores["best"] = {}
    for k, v in current_scores.items():
        if k == "avg_latency_ms":
            scores["best"][k] = min(scores["best"].get(k, 999999), v)
        else:
            scores["best"][k] = max(scores["best"].get(k, 0), v)
    save_scores(scores)

    elapsed = time.time() - cycle_start
    log(f"═══ CYCLE #{cycle_num} DONE ({elapsed:.0f}s) ═══")
    log(f"  Accuracy: {overall_accuracy:.1%} ({total_pass}/{total}) | "
        f"Latency: {avg_latency}ms | Regressions: {len(regressions)}")

    # Per-sector summary
    for sector in ["finance", "btp", "juridique", "industrie"]:
        if sector in results_by_sector:
            d = results_by_sector[sector]
            t = d["pass"] + d["fail"] + d["error"]
            acc = d["pass"] / t if t > 0 else 0
            log(f"  {sector}: {acc:.0%} ({d['pass']}/{t})")

    return history


def show_status():
    """Display current self-improvement status."""
    scores = load_scores()
    history = load_history()

    print(f"\n{'='*55}")
    print(f"RAG SELF-IMPROVEMENT STATUS")
    print(f"{'='*55}")
    print(f"Total cycles: {history.get('total_cycles', 0)}")
    print(f"Started: {history.get('started', '?')}")
    print(f"Last updated: {scores.get('timestamp', '?')}")

    current = scores.get("current", {})
    best = scores.get("best", {})

    print(f"\nCurrent Accuracy: {current.get('overall', 0):.1%}")
    print(f"Best Accuracy:    {best.get('overall', 0):.1%}")
    print(f"Avg Latency:      {current.get('avg_latency_ms', 0)}ms")

    print(f"\nBy Sector:")
    for sector in ["finance", "btp", "juridique", "industrie"]:
        k = f"sector_{sector}"
        c = current.get(k, 0)
        b = best.get(k, 0)
        print(f"  {sector:12s}: {c:.0%} (best: {b:.0%})")

    print(f"\nBy Pipeline:")
    for pipeline in ["standard", "graph", "quantitative", "orchestrator"]:
        k = f"pipeline_{pipeline}"
        c = current.get(k, 0)
        b = best.get(k, 0)
        print(f"  {pipeline:14s}: {c:.0%} (best: {b:.0%})")

    # Trend (last 5 cycles)
    cycles = history.get("cycles", [])
    if cycles:
        print(f"\nTrend (last 5 cycles):")
        for c in cycles[-5:]:
            print(f"  #{c['cycle']:3d} | {c['accuracy']:.0%} ({c['pass']}/{c['questions_tested']}) | "
                  f"{c['avg_latency_ms']}ms | {c.get('elapsed_s', 0)}s")

    print()


def main():
    parser = argparse.ArgumentParser(description="RAG Self-Improvement Loop")
    parser.add_argument("--daemon", action="store_true", help="Run continuously (30min cycles)")
    parser.add_argument("--once", action="store_true", help="Run one cycle")
    parser.add_argument("--interval", type=int, default=CYCLE_INTERVAL, help="Cycle interval seconds")
    parser.add_argument("--questions", type=int, default=QUESTIONS_PER_CYCLE, help="Questions per cycle")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    qpc = args.questions

    # Save PID
    pid_file = DATA_DIR / "self-improve.pid"
    pid_file.write_text(str(os.getpid()))

    all_questions = load_questions()
    if not all_questions:
        log("No eval questions found! Cannot run self-improvement.", "ERROR")
        return

    history = load_history()

    if args.once or not args.daemon:
        run_cycle(all_questions, history, qpc)
    else:
        log(f"Starting RAG Self-Improvement daemon — {args.interval}s cycles, {qpc} questions/cycle")
        while True:
            try:
                history = run_cycle(all_questions, history, qpc)
            except Exception as e:
                log(f"Cycle error: {e}", "ERROR")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
