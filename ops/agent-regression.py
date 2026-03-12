#!/usr/bin/env python3
"""
Agent Regression — Watches accuracy trends, alerts on drops, blocks regressions.

Cycle (every 15min):
  1. Query eval_results for last 2 windows (current vs previous)
  2. Compare accuracy per pipeline, per sector
  3. If drop > 5% → flag regression, write alert
  4. If drop > 10% → CRITICAL alert
  5. Track improving/degrading questions in eval_question_bank
  6. Generate regression report in data/agents/

Usage:
  source .env.local
  python3 ops/agent-regression.py              # One check
  python3 ops/agent-regression.py --daemon 900 # Continuous (15min)
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
import sys
import time
import traceback
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "agents")
REPORT_DIR = os.path.join(REPO_ROOT, "data", "agents", "regression-reports")
os.makedirs(REPORT_DIR, exist_ok=True)

DB_URL = os.environ.get("DATABASE_URL", "")
_db = None

def get_db():
    global _db
    if _db and not _db.closed:
        return _db
    import psycopg2
    _db = psycopg2.connect(DB_URL)
    _db.autocommit = True
    with _db.cursor() as c:
        c.execute("SET search_path TO public")
    return _db

def db_query(sql, params=None):
    try:
        conn = get_db()
        with conn.cursor() as c:
            c.execute(sql, params)
            if c.description:
                cols = [d[0] for d in c.description]
                return [dict(zip(cols, row)) for row in c.fetchall()]
            return []
    except Exception as e:
        log(f"DB: {e}")
        return []

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] REGR: {msg}")


def get_window_stats(hours_ago_start, hours_ago_end):
    """Get accuracy stats for a time window."""
    return db_query("""
        SELECT pipeline, sector,
               COUNT(*) as total,
               SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passed,
               ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as accuracy,
               ROUND(AVG(latency_ms)) as avg_latency
        FROM eval_results
        WHERE created_at BETWEEN now() - interval '%s hours' AND now() - interval '%s hours'
        GROUP BY pipeline, sector
        HAVING COUNT(*) >= 3
        ORDER BY pipeline, sector
    """, (hours_ago_start, hours_ago_end))


def get_overall_stats():
    """Get overall stats across all time."""
    return db_query("""
        SELECT
            COUNT(*) as total_results,
            SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as total_passed,
            ROUND(100.0 * SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as accuracy,
            COUNT(DISTINCT question_id) as unique_questions,
            (SELECT COUNT(*) FROM eval_runs) as total_runs,
            (SELECT COUNT(*) FROM eval_question_bank WHERE consecutive_fails >= 3) as chronic_failures
        FROM eval_results
    """)


def get_degrading_questions():
    """Find questions that are getting worse."""
    return db_query("""
        SELECT id, question, sector, pipeline, consecutive_fails,
               times_asked, times_passed, times_failed,
               score_trend, avg_score
        FROM eval_question_bank
        WHERE score_trend = 'degrading'
           OR consecutive_fails >= 3
        ORDER BY consecutive_fails DESC
        LIMIT 20
    """)


def get_improving_questions():
    """Find questions that are getting better."""
    return db_query("""
        SELECT id, question, sector, pipeline, consecutive_fails,
               times_asked, times_passed, score_trend
        FROM eval_question_bank
        WHERE score_trend = 'improving'
        ORDER BY times_asked DESC
        LIMIT 10
    """)


def check_regressions():
    """Compare current window vs previous window."""
    log("Checking for regressions...")

    # Current: last 6h vs Previous: 6-12h ago
    current = get_window_stats(6, 0)
    previous = get_window_stats(12, 6)

    if not current:
        log("  No recent eval data (last 6h) — need more eval runs")
        return {"regressions": [], "improvements": [], "status": "no_data"}

    if not previous:
        log("  No previous window data (6-12h ago) — first comparison")
        return {"regressions": [], "improvements": [], "status": "baseline_only",
                "current": current}

    # Build lookup
    prev_map = {}
    for p in previous:
        key = f"{p['pipeline']}|{p['sector']}"
        prev_map[key] = p

    regressions = []
    improvements = []

    for c in current:
        key = f"{c['pipeline']}|{c['sector']}"
        if key not in prev_map:
            continue

        prev = prev_map[key]
        delta = float(c["accuracy"] or 0) - float(prev["accuracy"] or 0)

        if delta <= -5:
            severity = "CRITICAL" if delta <= -10 else "WARNING"
            regressions.append({
                "pipeline": c["pipeline"],
                "sector": c["sector"],
                "current_accuracy": float(c["accuracy"] or 0),
                "previous_accuracy": float(prev["accuracy"] or 0),
                "delta": round(delta, 1),
                "severity": severity,
                "current_total": c["total"],
                "previous_total": prev["total"],
            })
            log(f"  {severity}: {c['pipeline']}/{c['sector']} "
                f"{prev['accuracy']}% → {c['accuracy']}% (delta {delta:+.1f}%)")
        elif delta >= 5:
            improvements.append({
                "pipeline": c["pipeline"],
                "sector": c["sector"],
                "current_accuracy": float(c["accuracy"] or 0),
                "previous_accuracy": float(prev["accuracy"] or 0),
                "delta": round(delta, 1),
            })
            log(f"  IMPROVED: {c['pipeline']}/{c['sector']} "
                f"{prev['accuracy']}% → {c['accuracy']}% (delta {delta:+.1f}%)")

    return {
        "regressions": regressions,
        "improvements": improvements,
        "status": "checked",
        "current_window": current,
        "previous_window": previous,
    }


def run_cycle():
    log("=" * 60)
    log("REGRESSION CHECK")
    log("=" * 60)

    # Overall stats
    overall = get_overall_stats()
    if overall:
        o = overall[0]
        log(f"Overall: {o.get('total_results', 0)} results | "
            f"{o.get('accuracy', 0)}% accuracy | "
            f"{o.get('unique_questions', 0)} unique Qs | "
            f"{o.get('total_runs', 0)} runs | "
            f"{o.get('chronic_failures', 0)} chronic failures")

    # Regression check
    result = check_regressions()

    if result["regressions"]:
        log(f"\n  REGRESSIONS DETECTED: {len(result['regressions'])}")
        for r in result["regressions"]:
            log(f"    {r['severity']}: {r['pipeline']}/{r['sector']} dropped {r['delta']:+.1f}%")
    else:
        log("  No regressions detected")

    if result["improvements"]:
        log(f"\n  Improvements: {len(result['improvements'])}")
        for imp in result["improvements"]:
            log(f"    {imp['pipeline']}/{imp['sector']} improved {imp['delta']:+.1f}%")

    # Degrading questions
    degrading = get_degrading_questions()
    if degrading:
        log(f"\n  Degrading questions: {len(degrading)}")
        for q in degrading[:5]:
            log(f"    [{q['consecutive_fails']}x fail] {q['pipeline']}/{q['sector']}: "
                f"{q['question'][:50]}...")

    # Improving questions
    improving = get_improving_questions()
    if improving:
        log(f"\n  Improving questions: {len(improving)}")

    # Write report
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": overall[0] if overall else {},
        "regressions": result.get("regressions", []),
        "improvements": result.get("improvements", []),
        "degrading_questions": len(degrading),
        "improving_questions": len(improving),
        "status": result.get("status", "unknown"),
    }

    report_file = os.path.join(REPORT_DIR, f"regression-{ts}.json")
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Write marker
    marker = os.path.join(DATA_DIR, "regression_done.marker")
    with open(marker, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "regressions": len(result.get("regressions", [])),
            "improvements": len(result.get("improvements", [])),
            "overall_accuracy": float(overall[0].get("accuracy", 0)) if overall else 0,
            "total_results": int(overall[0].get("total_results", 0)) if overall else 0,
        }, f)

    log(f"\nReport saved: {report_file}")
    log("=" * 60)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", type=int, default=0)
    args = parser.parse_args()

    if args.daemon > 0:
        log(f"DAEMON MODE: every {args.daemon}s")
        while True:
            try:
                run_cycle()
            except Exception as e:
                log(f"Cycle error: {e}")
                traceback.print_exc()
            time.sleep(args.daemon)
    else:
        run_cycle()


if __name__ == "__main__":
    main()
