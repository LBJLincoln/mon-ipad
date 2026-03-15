#!/usr/bin/env python3
"""Parallel Eval — 6 Spaces × 4 Pipelines = 24 workers.

Distributes 220 questions across all available Spaces for maximum throughput.
Each Space handles questions independently via round-robin assignment.

Usage:
    python3 eval/parallel-eval.py                    # Full 220Q eval
    python3 eval/parallel-eval.py --smoke            # Quick 20Q smoke
    python3 eval/parallel-eval.py --sector finance   # Single sector
    python3 eval/parallel-eval.py --pipeline standard # Single pipeline
    python3 eval/parallel-eval.py --workers 12       # Custom worker count
"""

import json
import os
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime, timezone

# === Force IPv4 ===
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only(*args, **kwargs):
    r = _original_getaddrinfo(*args, **kwargs)
    return [r2 for r2 in r if r2[0] == socket.AF_INET] or r
socket.getaddrinfo = _ipv4_only

# SSL
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# === ALL 6 SPACES ===
SPACES = [
    "https://lbjlincoln-nomos-rag-engine.hf.space",      # S1
    "https://lbjlincoln26-nomos-rag-engine-2.hf.space",   # S2
    "https://lbjlincoln-nomos-rag-engine-3.hf.space",     # S3
    "https://lbjlincoln26-nomos-rag-engine-4.hf.space",   # S4
    "https://lbjlincoln-nomos-rag-engine-5.hf.space",     # S5
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",     # S9
]

SPACE_NAMES = ["S1", "S2", "S3", "S4", "S5", "S9"]

# === PIPELINE WEBHOOKS ===
WEBHOOKS = {
    "standard": "/webhook/rag-multi-index-v3",
    "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}

DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "sectors", "eval-datasets", "sector-full-eval.json")
SMOKE_PATH = os.path.join(os.path.dirname(__file__), "..", "sectors", "eval-datasets", "sector-smoke-test.json")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "eval")


def http_post(url, payload, timeout=120):
    """POST JSON and return (status, body, elapsed)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
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


def health_check(spaces):
    """Check which Spaces are alive. Returns list of healthy Space URLs."""
    healthy = []
    for i, base in enumerate(spaces):
        try:
            req = urllib.request.Request(f"{base}/healthz", method="GET")
            resp = urllib.request.urlopen(req, context=ctx, timeout=8)
            healthy.append(base)
        except Exception:
            # Try webhook endpoint as backup
            try:
                status, _, _ = http_post(f"{base}/webhook/rag-multi-index-v3",
                                         {"query": "ping", "sector": "finance", "disable_acl": True}, timeout=15)
                if status in (200, 201):
                    healthy.append(base)
                else:
                    print(f"  {SPACE_NAMES[i]}: DOWN ({status})")
            except Exception:
                print(f"  {SPACE_NAMES[i]}: DOWN")
    return healthy


def score_result(question, response_body):
    """Score a single Q&A result. Returns dict with score and details."""
    try:
        r = json.loads(response_body)
        if isinstance(r, list):
            r = r[0] if r else {}
    except json.JSONDecodeError:
        return {"score": 0, "status": "JSON_ERROR", "answer": response_body[:200]}

    answer = str(r.get("response", r.get("answer", r.get("interpretation", ""))))
    sources = r.get("sources", [])
    status = r.get("status", "OK" if answer else "EMPTY")

    # Score components
    score = 0

    # 1. Alive (15 pts)
    if len(answer) > 10:
        score += 15

    # 2. Answer length (20 pts)
    if len(answer) > 50:
        score += 10
    if len(answer) > 200:
        score += 10

    # 3. Expected keyword hit (30 pts)
    expected = question.get("expected_contains", "")
    if expected and expected.lower() in answer.lower():
        score += 30

    # 4. Sources (15 pts)
    if len(sources) > 0:
        score += 8
    if len(sources) >= 3:
        score += 7

    # 5. Language match (10 pts)
    q_lang = question.get("language", "fr")
    if q_lang == "fr":
        if any(w in answer.lower() for w in ["le ", "la ", "les ", "des ", "une ", "est ", "sont "]):
            score += 10
    else:
        if any(w in answer.lower() for w in ["the ", "is ", "are ", "was ", "has "]):
            score += 10

    # 6. Professional terminology (10 pts)
    sector = question.get("sector", "")
    sector_terms = {
        "finance": ["ratio", "marge", "chiffre", "revenue", "bilan", "actif", "passif", "ebitda", "capex"],
        "btp": ["dtu", "beton", "norme", "construction", "ouvrage", "dalle", "fondation"],
        "juridique": ["article", "code", "responsabilit", "contrat", "droit", "obligation", "juridique"],
        "industrie": ["processus", "qualit", "norme", "iso", "production", "maintenance", "securit"],
    }
    terms = sector_terms.get(sector, [])
    if any(t in answer.lower() for t in terms):
        score += 10

    return {
        "score": score,
        "status": status,
        "answer_length": len(answer),
        "answer_preview": answer[:200],
        "sources_count": len(sources),
        "keyword_hit": bool(expected and expected.lower() in answer.lower()),
        "language_ok": score >= 10,  # approximation
    }


def run_question(question, space_url, space_name):
    """Run a single question against a specific Space. Returns result dict."""
    pipeline = question.get("pipeline", "standard")
    webhook = WEBHOOKS.get(pipeline)
    if not webhook:
        return {"id": question["id"], "status": "UNKNOWN_PIPELINE", "score": 0, "space": space_name}

    url = f"{space_url}{webhook}"
    payload = {
        "query": question["question"],
        "sector": question.get("sector", "finance"),
        "disable_acl": True,
    }

    status, body, elapsed = http_post(url, payload, timeout=120)

    result = {
        "id": question["id"],
        "pipeline": pipeline,
        "sector": question.get("sector", ""),
        "space": space_name,
        "http_status": status,
        "latency_s": round(elapsed, 1),
        "difficulty": question.get("difficulty", ""),
        "category": question.get("category", ""),
    }

    if status == 200:
        scoring = score_result(question, body)
        result.update(scoring)
    else:
        result["score"] = 0
        result["status"] = f"HTTP_{status}"
        result["answer_preview"] = body[:200]

    return result


def load_questions(path, sector_filter=None, pipeline_filter=None):
    """Load questions from dataset file."""
    with open(path, "r") as f:
        data = json.load(f)

    questions = data.get("questions", [])

    if sector_filter:
        questions = [q for q in questions if q.get("sector") == sector_filter]
    if pipeline_filter:
        questions = [q for q in questions if q.get("pipeline") == pipeline_filter]

    return questions


def run_parallel_eval(questions, healthy_spaces, max_workers=12):
    """Run all questions in parallel across all healthy Spaces."""
    results = []
    space_count = len(healthy_spaces)

    # Assign questions to Spaces round-robin
    assignments = []
    for i, q in enumerate(questions):
        space_idx = i % space_count
        space_url = healthy_spaces[space_idx]
        space_name = SPACE_NAMES[SPACES.index(space_url)] if space_url in SPACES else f"S?"
        assignments.append((q, space_url, space_name))

    total = len(assignments)
    completed = 0
    start_time = time.time()

    print(f"\nRunning {total} questions across {space_count} Spaces with {max_workers} workers...")
    print(f"Estimated time: {total * 30 / max_workers:.0f}s ({total * 30 / max_workers / 60:.1f} min)")
    print()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for q, space_url, space_name in assignments:
            future = executor.submit(run_question, q, space_url, space_name)
            futures[future] = (q["id"], space_name)

        for future in as_completed(futures):
            qid, sname = futures[future]
            try:
                result = future.result()
                results.append(result)
                completed += 1

                # Progress
                score = result.get("score", 0)
                status = result.get("status", "?")
                latency = result.get("latency_s", 0)
                pipeline = result.get("pipeline", "?")
                sector = result.get("sector", "?")

                icon = "PASS" if score >= 50 else "WEAK" if score > 0 else "FAIL"
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0

                if completed % 10 == 0 or completed == total:
                    print(f"  [{completed}/{total}] {rate:.1f} Q/s | Last: {qid} {icon} {score}/100 {pipeline}@{sname} {latency}s")

            except Exception as e:
                results.append({"id": qid, "space": sname, "score": 0, "status": f"ERROR: {str(e)[:100]}"})
                completed += 1

    return results


def generate_report(results, questions, elapsed_s):
    """Generate summary report from results."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_questions": len(results),
        "total_elapsed_s": round(elapsed_s, 1),
        "throughput_q_per_s": round(len(results) / elapsed_s, 2) if elapsed_s > 0 else 0,
        "spaces_used": list(set(r.get("space", "?") for r in results)),
    }

    # Overall stats
    scores = [r.get("score", 0) for r in results]
    report["avg_score"] = round(sum(scores) / len(scores), 1) if scores else 0
    report["pass_count"] = sum(1 for s in scores if s >= 50)
    report["pass_rate"] = round(report["pass_count"] / len(scores) * 100, 1) if scores else 0

    # By pipeline
    by_pipeline = defaultdict(list)
    for r in results:
        by_pipeline[r.get("pipeline", "?")].append(r)

    report["by_pipeline"] = {}
    for pipeline, rs in sorted(by_pipeline.items()):
        pscores = [r.get("score", 0) for r in rs]
        latencies = [r.get("latency_s", 0) for r in rs if r.get("latency_s", 0) > 0]
        report["by_pipeline"][pipeline] = {
            "count": len(rs),
            "avg_score": round(sum(pscores) / len(pscores), 1) if pscores else 0,
            "pass_rate": round(sum(1 for s in pscores if s >= 50) / len(pscores) * 100, 1) if pscores else 0,
            "avg_latency_s": round(sum(latencies) / len(latencies), 1) if latencies else 0,
            "keyword_hit_rate": round(sum(1 for r in rs if r.get("keyword_hit")) / len(rs) * 100, 1) if rs else 0,
        }

    # By sector
    by_sector = defaultdict(list)
    for r in results:
        by_sector[r.get("sector", "?")].append(r)

    report["by_sector"] = {}
    for sector, rs in sorted(by_sector.items()):
        sscores = [r.get("score", 0) for r in rs]
        report["by_sector"][sector] = {
            "count": len(rs),
            "avg_score": round(sum(sscores) / len(sscores), 1) if sscores else 0,
            "pass_rate": round(sum(1 for s in sscores if s >= 50) / len(sscores) * 100, 1) if sscores else 0,
        }

    # By Space (distribution check)
    by_space = defaultdict(list)
    for r in results:
        by_space[r.get("space", "?")].append(r)

    report["by_space"] = {}
    for space, rs in sorted(by_space.items()):
        sscores = [r.get("score", 0) for r in rs]
        report["by_space"][space] = {
            "count": len(rs),
            "avg_score": round(sum(sscores) / len(sscores), 1) if sscores else 0,
        }

    # Cross-matrix: pipeline × sector
    report["matrix"] = {}
    for pipeline in by_pipeline:
        report["matrix"][pipeline] = {}
        for sector in by_sector:
            cell = [r for r in results if r.get("pipeline") == pipeline and r.get("sector") == sector]
            if cell:
                cell_scores = [r.get("score", 0) for r in cell]
                report["matrix"][pipeline][sector] = {
                    "count": len(cell),
                    "avg_score": round(sum(cell_scores) / len(cell_scores), 1),
                }

    return report


def print_report(report):
    """Pretty-print the evaluation report."""
    print()
    print("=" * 80)
    print(f"PARALLEL EVAL RESULTS — {report['total_questions']}Q across {len(report['spaces_used'])} Spaces")
    print(f"Time: {report['total_elapsed_s']}s | Throughput: {report['throughput_q_per_s']} Q/s")
    print("=" * 80)

    print(f"\nOverall: {report['avg_score']}/100 avg | {report['pass_count']}/{report['total_questions']} PASS ({report['pass_rate']}%)")

    print(f"\n{'Pipeline':<15} {'Count':>5} {'Avg':>6} {'Pass%':>6} {'Latency':>8} {'KW Hit%':>8}")
    print("-" * 55)
    for pipeline, stats in report["by_pipeline"].items():
        print(f"{pipeline:<15} {stats['count']:>5} {stats['avg_score']:>6.1f} {stats['pass_rate']:>5.1f}% {stats['avg_latency_s']:>7.1f}s {stats['keyword_hit_rate']:>7.1f}%")

    print(f"\n{'Sector':<15} {'Count':>5} {'Avg':>6} {'Pass%':>6}")
    print("-" * 35)
    for sector, stats in report["by_sector"].items():
        print(f"{sector:<15} {stats['count']:>5} {stats['avg_score']:>6.1f} {stats['pass_rate']:>5.1f}%")

    print(f"\n{'Space':<8} {'Count':>5} {'Avg':>6}")
    print("-" * 22)
    for space, stats in report["by_space"].items():
        print(f"{space:<8} {stats['count']:>5} {stats['avg_score']:>6.1f}")

    # Matrix
    sectors = sorted(report.get("matrix", {}).get(list(report["matrix"].keys())[0], {}).keys()) if report.get("matrix") else []
    if sectors:
        header = 'Pipeline \\ Sector'
        print(f"\n{header:<15}", end="")
        for s in sectors:
            print(f" {s:>10}", end="")
        print()
        print("-" * (15 + 11 * len(sectors)))
        for pipeline in report["matrix"]:
            print(f"{pipeline:<15}", end="")
            for s in sectors:
                cell = report["matrix"][pipeline].get(s, {})
                if cell:
                    print(f" {cell['avg_score']:>9.1f}", end="")
                else:
                    print(f"        —", end="")
            print()

    print("=" * 80)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parallel Eval — 6 Spaces × 4 Pipelines")
    parser.add_argument("--smoke", action="store_true", help="Quick 20Q smoke test")
    parser.add_argument("--dataset", help="Path to custom dataset JSON file")
    parser.add_argument("--extended", action="store_true", help="Use extended 5K+ dataset")
    parser.add_argument("--sector", help="Filter by sector (finance, btp, juridique, industrie)")
    parser.add_argument("--pipeline", help="Filter by pipeline (standard, graph, quantitative, orchestrator)")
    parser.add_argument("--workers", type=int, default=12, help="Max parallel workers (default: 12)")
    parser.add_argument("--timeout", type=int, default=120, help="Per-question timeout seconds")
    args = parser.parse_args()

    # Load dataset
    EXTENDED_PATH = os.path.join(os.path.dirname(__file__), "..", "sectors", "eval-datasets", "sector-full-eval-extended.json")
    if args.dataset:
        path = os.path.abspath(args.dataset)
        print(f"Loading custom dataset: {path}")
    elif args.smoke:
        path = os.path.abspath(SMOKE_PATH)
        print("Loading smoke test dataset (20Q)...")
    elif args.extended:
        path = os.path.abspath(EXTENDED_PATH)
        print("Loading extended dataset (5K+)...")
    else:
        path = os.path.abspath(DATASET_PATH)
        print("Loading full eval dataset (220Q)...")

    if not os.path.exists(path):
        print(f"ERROR: Dataset not found: {path}")
        sys.exit(1)

    questions = load_questions(path, sector_filter=args.sector, pipeline_filter=args.pipeline)
    print(f"Loaded {len(questions)} questions")

    if not questions:
        print("No questions match filters.")
        sys.exit(0)

    # Health check all Spaces
    print(f"\nHealth check on {len(SPACES)} Spaces...")
    healthy = health_check(SPACES)
    print(f"Healthy: {len(healthy)}/{len(SPACES)} Spaces")

    if not healthy:
        print("ERROR: No healthy Spaces found!")
        sys.exit(1)

    # Run parallel eval
    start = time.time()
    results = run_parallel_eval(questions, healthy, max_workers=args.workers)
    elapsed = time.time() - start

    # Generate and print report
    report = generate_report(results, questions, elapsed)
    print_report(report)

    # Save results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    results_path = os.path.join(RESULTS_DIR, f"parallel-eval-{ts}.json")
    with open(results_path, "w") as f:
        json.dump({"report": report, "results": results}, f, indent=2, ensure_ascii=False)

    summary_path = os.path.join(RESULTS_DIR, "parallel-eval-latest.json")
    with open(summary_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {results_path}")
    print(f"Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
