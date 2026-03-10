#!/usr/bin/env python3
"""
Continuous Evaluation & Improvement Loop
==========================================
Runs turbo-eval at regular intervals, analyzes weak questions,
classifies gaps (data vs retrieval), tracks score evolution over time,
and optionally triggers auto-ingestion for data gaps.

Features:
  1. Periodic turbo-eval runs (every N minutes)
  2. Gap analysis: data gap vs retrieval gap classification
  3. Improvement targets: actionable file with weak questions + suggested actions
  4. Score history: track evolution across runs with regression alerts
  5. Optional auto-ingest: search Tavily for data gaps and queue ingestion

Usage:
  source .env.local
  python3 eval/continuous-eval.py                           # One run, analyze gaps
  python3 eval/continuous-eval.py --interval 30             # Run every 30 minutes
  python3 eval/continuous-eval.py --sample 50               # 50 questions per run
  python3 eval/continuous-eval.py --auto-ingest             # Auto-search for data gaps
  python3 eval/continuous-eval.py --analyze-only            # Analyze last results only
"""

import json
import os
import sys
import time
import signal
import socket
import subprocess
import argparse
import requests
from datetime import datetime
from collections import defaultdict

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

RESULTS_FILE = os.path.join(DATA_DIR, "expert-results.json")
LIVE_RESULTS_FILE = os.path.join(DATA_DIR, "expert-results-live.json")
SECTOR_SCORES_FILE = os.path.join(DATA_DIR, "sector-scores.json")
IMPROVEMENT_TARGETS_FILE = os.path.join(DATA_DIR, "improvement-targets.json")
SCORE_HISTORY_FILE = os.path.join(DATA_DIR, "score-history.json")
INGEST_QUEUE_FILE = os.path.join(DATA_DIR, "ingest-queue.json")

# ─── Env ──────────────────────────────────────────────────────────────────
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

# ─── Thresholds ───────────────────────────────────────────────────────────
WEAK_SCORE_THRESHOLD = 2.0   # Questions scoring below this are "weak"
REGRESSION_ALERT_PCT = 5.0   # Alert if sector drops > 5% between runs
DATA_GAP_KEYWORDS = [
    "information non disponible", "pas d'information", "no information available",
    "not available", "cannot find", "aucune donnee", "pas de donnee",
    "je n'ai pas", "i don't have", "no data", "unavailable",
    "no relevant", "aucun resultat", "not found", "introuvable",
]

# ─── Sector data gap suggestions ─────────────────────────────────────────
SECTOR_INGEST_SUGGESTIONS = {
    "finance": {
        "data": "Ingest more SEC filings (10-K, 10-Q), IFRS standards, annual reports, earnings call transcripts",
        "retrieval": "Improve E5 chunking for financial tables, increase top_k, add sector filter boost",
    },
    "btp": {
        "data": "Ingest DTU norms, Eurocodes, CCTP templates, AFNOR standards, RE2020 documentation",
        "retrieval": "Improve chunking for technical norms, add BTP-specific terminology to embeddings",
    },
    "juridique": {
        "data": "Ingest more Code civil/commerce/travail articles, RGPD texts, jurisprudence databases",
        "retrieval": "Improve legal article cross-referencing, boost exact article number matches",
    },
    "industrie": {
        "data": "Ingest ISO standards (9001, 14001, 45001), AMDEC templates, maintenance procedure guides",
        "retrieval": "Improve technical procedure chunking, add ISO standard number matching",
    },
}

# ─── Graceful shutdown ────────────────────────────────────────────────────
_shutdown = False

def _signal_handler(signum, frame):
    global _shutdown
    print("\n  Received shutdown signal. Finishing current run...")
    _shutdown = True

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# =========================================================================
#  TURBO-EVAL RUNNER
# =========================================================================

def run_turbo_eval(sample=50, sector=None, full=False, workers=4, delay=1.0):
    """Run turbo-eval.py as a subprocess and return the results."""
    cmd = [
        sys.executable,
        os.path.join(REPO_ROOT, "eval", "turbo-eval.py"),
        "--workers", str(workers),
        "--delay", str(delay),
    ]
    if full:
        cmd.append("--full")
    elif sample:
        cmd.extend(["--sample", str(sample)])
    if sector:
        cmd.extend(["--sector", sector])

    print(f"\n  {'='*60}")
    print(f"  RUNNING TURBO-EVAL: {' '.join(cmd[2:])}")
    print(f"  {'='*60}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            timeout=3600,  # 1 hour max
            capture_output=False,  # Let output stream to terminal
        )
        elapsed = time.time() - start
        print(f"\n  Turbo-eval completed in {elapsed:.1f}s (exit code: {result.returncode})")

        if result.returncode != 0:
            print(f"  WARNING: turbo-eval exited with code {result.returncode}")
            return None

        # Read results
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    except subprocess.TimeoutExpired:
        print("  ERROR: turbo-eval timed out after 1 hour")
        return None
    except Exception as e:
        print(f"  ERROR running turbo-eval: {e}")
        return None


# =========================================================================
#  GAP ANALYSIS
# =========================================================================

def classify_gap(result):
    """Classify a weak question's failure as 'data' or 'retrieval' gap.

    Data gap: The system says it doesn't have the information.
    Retrieval gap: The system found sources but gave wrong/incomplete answer.
    """
    answer = (result.get("answer") or "").lower()
    sources = result.get("sources") or []
    scores = result.get("scores") or {}
    factual = scores.get("factual_accuracy", 0)
    citation = scores.get("source_citation", 0)

    # Data gap indicators
    is_data_gap = False

    # Check for "no data" language in the answer
    for keyword in DATA_GAP_KEYWORDS:
        if keyword in answer:
            is_data_gap = True
            break

    # Low factual + low citation = data gap
    if factual <= 1.5 and citation <= 1.5:
        is_data_gap = True

    # Empty or near-empty answer
    if len(answer.strip()) < 50:
        is_data_gap = True

    # No sources retrieved
    if not sources or len(sources) == 0:
        is_data_gap = True

    if is_data_gap:
        return "data"

    # Retrieval gap: has sources but bad answer
    return "retrieval"


def analyze_weak_questions(results):
    """Find and classify weak questions from evaluation results.

    Returns list of dicts: {id, sector, question, score, gap_type, suggested_action, details}
    """
    weak = []

    for r in results:
        scores = r.get("scores")
        if not scores:
            # Error — no scores means we couldn't even get an answer
            weak.append({
                "id": r.get("id", "?"),
                "sector": r.get("sector", "unknown"),
                "question": r.get("question", "")[:120],
                "score": 0.0,
                "gap_type": "error",
                "error": r.get("error", "unknown error"),
                "suggested_action": f"Fix pipeline error: {r.get('error', '?')[:80]}",
            })
            continue

        # Compute overall score
        vals = [scores.get(k, 0) for k in
                ["factual_accuracy", "source_citation", "expert_terminology",
                 "completeness", "language_match"]]
        non_zero = [v for v in vals if v > 0]
        avg = sum(non_zero) / len(non_zero) if non_zero else 0.0

        if avg >= WEAK_SCORE_THRESHOLD:
            continue

        gap_type = classify_gap(r)
        sector = r.get("sector", "unknown")
        suggestions = SECTOR_INGEST_SUGGESTIONS.get(sector, {})

        weak.append({
            "id": r.get("id", "?"),
            "sector": sector,
            "question": r.get("question", "")[:120],
            "score": round(avg, 2),
            "gap_type": gap_type,
            "scores_detail": {
                "factual_accuracy": scores.get("factual_accuracy", 0),
                "source_citation": scores.get("source_citation", 0),
                "expert_terminology": scores.get("expert_terminology", 0),
                "completeness": scores.get("completeness", 0),
                "language_match": scores.get("language_match", 0),
            },
            "suggested_action": suggestions.get(gap_type, "Investigate manually"),
            "answer_snippet": (r.get("answer") or "")[:100],
            "num_sources": len(r.get("sources") or []),
        })

    # Sort by score ascending (worst first)
    weak.sort(key=lambda x: x["score"])
    return weak


def write_improvement_targets(weak_questions, run_timestamp):
    """Write improvement-targets.json with actionable gap analysis."""
    # Group by sector and gap type
    by_sector = defaultdict(lambda: {"data": [], "retrieval": [], "error": []})
    for wq in weak_questions:
        by_sector[wq["sector"]][wq["gap_type"]].append(wq)

    sector_summaries = {}
    for sector, gaps in by_sector.items():
        sector_summaries[sector] = {
            "total_weak": len(gaps["data"]) + len(gaps["retrieval"]) + len(gaps["error"]),
            "data_gaps": len(gaps["data"]),
            "retrieval_gaps": len(gaps["retrieval"]),
            "errors": len(gaps["error"]),
            "priority_action": (
                SECTOR_INGEST_SUGGESTIONS.get(sector, {}).get("data", "Ingest more documents")
                if len(gaps["data"]) >= len(gaps["retrieval"])
                else SECTOR_INGEST_SUGGESTIONS.get(sector, {}).get("retrieval", "Improve retrieval")
            ),
        }

    output = {
        "timestamp": run_timestamp,
        "total_weak_questions": len(weak_questions),
        "threshold": WEAK_SCORE_THRESHOLD,
        "sector_summaries": sector_summaries,
        "weak_questions": weak_questions,
    }

    with open(IMPROVEMENT_TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Improvement targets saved: {IMPROVEMENT_TARGETS_FILE}")
    return output


# =========================================================================
#  SCORE HISTORY & REGRESSION DETECTION
# =========================================================================

def load_score_history():
    """Load score history from file."""
    if os.path.exists(SCORE_HISTORY_FILE):
        try:
            with open(SCORE_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"runs": []}


def save_score_history(history):
    """Save score history to file."""
    with open(SCORE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def update_score_history(sector_scores, run_timestamp, num_questions):
    """Add a new entry to score history and check for regressions."""
    history = load_score_history()

    # Build entry
    entry = {
        "timestamp": run_timestamp,
        "num_questions": num_questions,
        "sectors": {},
    }
    for sector, data in sector_scores.items():
        entry["sectors"][sector] = {
            "overall": data["scores"].get("overall", 0),
            "factual_accuracy": data["scores"].get("factual_accuracy", 0),
            "source_citation": data["scores"].get("source_citation", 0),
            "expert_terminology": data["scores"].get("expert_terminology", 0),
            "completeness": data["scores"].get("completeness", 0),
            "language_match": data["scores"].get("language_match", 0),
            "count": data["count"],
            "errors": data["errors"],
        }

    history["runs"].append(entry)

    # Keep last 100 runs
    if len(history["runs"]) > 100:
        history["runs"] = history["runs"][-100:]

    save_score_history(history)
    print(f"  Score history updated: {SCORE_HISTORY_FILE} ({len(history['runs'])} runs)")

    # Check for regressions
    regressions = detect_regressions(history)
    return regressions


def detect_regressions(history):
    """Compare latest run with previous run. Alert if any sector drops > 5%."""
    runs = history.get("runs", [])
    if len(runs) < 2:
        return []

    current = runs[-1]
    previous = runs[-2]
    regressions = []

    for sector in current["sectors"]:
        if sector not in previous["sectors"]:
            continue
        curr_overall = current["sectors"][sector].get("overall", 0)
        prev_overall = previous["sectors"][sector].get("overall", 0)

        if prev_overall <= 0:
            continue

        # Calculate percentage change (on 5-point scale)
        change_pct = ((curr_overall - prev_overall) / prev_overall) * 100

        if change_pct < -REGRESSION_ALERT_PCT:
            regressions.append({
                "sector": sector,
                "previous": round(prev_overall, 2),
                "current": round(curr_overall, 2),
                "change_pct": round(change_pct, 1),
                "timestamp": current["timestamp"],
            })

    return regressions


# =========================================================================
#  AUTO-INGEST (Tavily search for data gaps)
# =========================================================================

SECTOR_SEARCH_TERMS = {
    "finance": [
        "SEC 10-K filing", "IFRS financial reporting standard",
        "annual report financial statements", "earnings call transcript",
    ],
    "btp": [
        "DTU norme construction", "Eurocode structure batiment",
        "RE2020 reglementation thermique", "CCTP marche public travaux",
    ],
    "juridique": [
        "Code civil francais articles", "RGPD conformite traitement donnees",
        "Code du travail licenciement", "jurisprudence Cour de cassation",
    ],
    "industrie": [
        "ISO 9001 qualite management", "maintenance preventive industrielle",
        "AMDEC analyse risques production", "ISO 14001 environnement industriel",
    ],
}


def search_tavily(query, max_results=5):
    """Search Tavily for relevant documents."""
    if not TAVILY_API_KEY:
        return []
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": "advanced",
                "include_raw_content": False,
            },
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("results", [])
        return []
    except Exception as e:
        print(f"    Tavily error: {str(e)[:100]}")
        return []


def auto_ingest_for_gaps(weak_questions):
    """For data gap questions, search Tavily and queue URLs for ingestion."""
    if not TAVILY_API_KEY:
        print("  Auto-ingest: No TAVILY_API_KEY, skipping")
        return []

    data_gap_sectors = defaultdict(list)
    for wq in weak_questions:
        if wq["gap_type"] == "data":
            data_gap_sectors[wq["sector"]].append(wq["question"])

    if not data_gap_sectors:
        print("  Auto-ingest: No data gaps found, skipping")
        return []

    ingest_queue = []
    for sector, questions in data_gap_sectors.items():
        print(f"  Auto-ingest: Searching for {sector} data ({len(questions)} gaps)...")

        # Use sector-specific search terms + specific question keywords
        search_terms = SECTOR_SEARCH_TERMS.get(sector, [])
        # Add question-derived terms (first 2 questions)
        for q in questions[:2]:
            search_terms.append(q[:80])

        seen_urls = set()
        for term in search_terms[:4]:  # Max 4 searches per sector
            results = search_tavily(term, max_results=3)
            for result in results:
                url = result.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    ingest_queue.append({
                        "url": url,
                        "title": result.get("title", ""),
                        "sector": sector,
                        "search_query": term,
                        "relevance_score": result.get("score", 0),
                        "queued_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    })
            time.sleep(0.5)  # Rate limit Tavily

    if ingest_queue:
        # Merge with existing queue
        existing = []
        if os.path.exists(INGEST_QUEUE_FILE):
            try:
                with open(INGEST_QUEUE_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f).get("queue", [])
            except Exception:
                pass

        existing_urls = {item["url"] for item in existing}
        new_items = [item for item in ingest_queue if item["url"] not in existing_urls]
        all_items = existing + new_items

        output = {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_queued": len(all_items),
            "new_added": len(new_items),
            "queue": all_items,
        }
        with open(INGEST_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"  Ingest queue: {len(new_items)} new URLs added ({len(all_items)} total)")
        print(f"  Saved to: {INGEST_QUEUE_FILE}")

    return ingest_queue


# =========================================================================
#  ANALYSIS (from existing results)
# =========================================================================

def analyze_existing_results():
    """Analyze the most recent results file without running a new eval."""
    if not os.path.exists(RESULTS_FILE):
        print("  No results file found. Run an eval first.")
        return None

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])
    timestamp = data.get("timestamp", datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))

    print(f"\n  Analyzing {len(results)} results from {timestamp}...")
    return results, timestamp


# =========================================================================
#  REPORT
# =========================================================================

def print_gap_report(weak_questions, regressions=None):
    """Print a human-readable gap analysis report."""
    print("\n" + "=" * 70)
    print("  IMPROVEMENT ANALYSIS")
    print("=" * 70)

    if not weak_questions:
        print("  No weak questions found (all above threshold).")
        print("=" * 70)
        return

    # Summary by sector
    by_sector = defaultdict(lambda: {"data": 0, "retrieval": 0, "error": 0, "scores": []})
    for wq in weak_questions:
        by_sector[wq["sector"]][wq["gap_type"]] += 1
        by_sector[wq["sector"]]["scores"].append(wq["score"])

    print(f"\n  Weak questions (score < {WEAK_SCORE_THRESHOLD}): {len(weak_questions)}")
    print(f"  {'Sector':<12} {'Data Gaps':>10} {'Retr Gaps':>10} {'Errors':>8} {'Avg Score':>10}")
    print("  " + "-" * 55)

    for sector in ["finance", "btp", "juridique", "industrie"]:
        sd = by_sector.get(sector)
        if not sd:
            continue
        avg = sum(sd["scores"]) / len(sd["scores"]) if sd["scores"] else 0
        print(f"  {sector:<12} {sd['data']:>10} {sd['retrieval']:>10} {sd['error']:>8} {avg:>9.2f}")

    # Top 10 worst questions
    print(f"\n  Top 10 worst questions:")
    print(f"  {'ID':<15} {'Sector':<10} {'Score':>6} {'Gap':>10} {'Question':<40}")
    print("  " + "-" * 85)
    for wq in weak_questions[:10]:
        print(f"  {wq['id']:<15} {wq['sector']:<10} {wq['score']:>5.1f} {wq['gap_type']:>10} "
              f"{wq['question'][:38]:<40}")

    # Regressions
    if regressions:
        print(f"\n  REGRESSIONS DETECTED:")
        for reg in regressions:
            print(f"    {reg['sector']}: {reg['previous']:.2f} -> {reg['current']:.2f} "
                  f"({reg['change_pct']:+.1f}%)")

    # Suggested actions per sector
    print(f"\n  Suggested actions per sector:")
    for sector, sd in by_sector.items():
        if sd["data"] >= sd["retrieval"]:
            action_type = "data"
            suggestion = SECTOR_INGEST_SUGGESTIONS.get(sector, {}).get("data", "Ingest more docs")
        else:
            action_type = "retrieval"
            suggestion = SECTOR_INGEST_SUGGESTIONS.get(sector, {}).get("retrieval", "Improve retrieval")
        print(f"    {sector} ({action_type} gap): {suggestion}")

    print("=" * 70)


# =========================================================================
#  MAIN LOOP
# =========================================================================

def run_single_cycle(sample=50, sector=None, full=False, workers=4, delay=1.0,
                     auto_ingest=False, analyze_only=False):
    """Run one eval + analysis cycle. Returns sector_scores or None."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Get results
    if analyze_only:
        analysis = analyze_existing_results()
        if not analysis:
            return None
        results, ts = analysis
    else:
        eval_data = run_turbo_eval(
            sample=sample, sector=sector, full=full,
            workers=workers, delay=delay,
        )
        if not eval_data:
            print("  Eval failed, skipping analysis")
            return None
        results = eval_data.get("results", [])

    if not results:
        print("  No results to analyze")
        return None

    # Load sector scores
    sector_scores = {}
    if os.path.exists(SECTOR_SCORES_FILE):
        with open(SECTOR_SCORES_FILE, "r", encoding="utf-8") as f:
            sector_scores = json.load(f).get("sectors", {})

    # Analyze weak questions
    weak_questions = analyze_weak_questions(results)

    # Write improvement targets
    write_improvement_targets(weak_questions, ts)

    # Update score history + check regressions
    regressions = update_score_history(sector_scores, ts, len(results))

    # Print report
    print_gap_report(weak_questions, regressions)

    # Auto-ingest if enabled
    if auto_ingest and weak_questions:
        auto_ingest_for_gaps(weak_questions)

    return sector_scores


def main():
    parser = argparse.ArgumentParser(description="Continuous Evaluation & Improvement Loop")
    parser.add_argument("--interval", type=int, default=0,
                        help="Minutes between runs (0 = single run, default: 0)")
    parser.add_argument("--sample", type=int, default=50,
                        help="Questions per run (default: 50)")
    parser.add_argument("--full", action="store_true",
                        help="Run all 208+ questions each cycle")
    parser.add_argument("--sector", type=str, default=None,
                        choices=["finance", "btp", "juridique", "industrie"])
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel workers (default: 4)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Per-worker delay in seconds (default: 1.0)")
    parser.add_argument("--auto-ingest", action="store_true",
                        help="Auto-search Tavily for data gaps and queue ingestion")
    parser.add_argument("--analyze-only", action="store_true",
                        help="Analyze existing results without running new eval")
    parser.add_argument("--max-cycles", type=int, default=0,
                        help="Max cycles in continuous mode (0 = unlimited)")
    args = parser.parse_args()

    print("=" * 70)
    print("  CONTINUOUS EVALUATION & IMPROVEMENT LOOP")
    if args.interval > 0:
        print(f"  Mode: Continuous (every {args.interval} min)")
    elif args.analyze_only:
        print(f"  Mode: Analyze existing results")
    else:
        print(f"  Mode: Single run")
    print(f"  Sample: {'FULL' if args.full else args.sample} questions")
    if args.sector:
        print(f"  Sector: {args.sector}")
    if args.auto_ingest:
        print(f"  Auto-ingest: {'ENABLED' if TAVILY_API_KEY else 'DISABLED (no TAVILY_API_KEY)'}")
    print("=" * 70)

    if args.interval <= 0:
        # Single run
        run_single_cycle(
            sample=args.sample,
            sector=args.sector,
            full=args.full,
            workers=args.workers,
            delay=args.delay,
            auto_ingest=args.auto_ingest,
            analyze_only=args.analyze_only,
        )
        return

    # Continuous loop
    cycle = 0
    while not _shutdown:
        cycle += 1
        print(f"\n  {'#'*60}")
        print(f"  CYCLE {cycle} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  {'#'*60}")

        run_single_cycle(
            sample=args.sample,
            sector=args.sector,
            full=args.full,
            workers=args.workers,
            delay=args.delay,
            auto_ingest=args.auto_ingest,
        )

        if args.max_cycles > 0 and cycle >= args.max_cycles:
            print(f"\n  Reached max cycles ({args.max_cycles}). Stopping.")
            break

        if _shutdown:
            break

        # Wait for next interval
        print(f"\n  Next run in {args.interval} minutes... (Ctrl+C to stop)")
        wait_until = time.time() + args.interval * 60
        while time.time() < wait_until and not _shutdown:
            time.sleep(5)

    print("\n  Continuous eval stopped.")


if __name__ == "__main__":
    main()
