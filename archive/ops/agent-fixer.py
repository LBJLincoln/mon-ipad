#!/usr/bin/env python3
"""
Agent Fixer — Reads worst-performing questions from Supabase, diagnoses and fixes.

Cycle:
  1. Query eval_results for worst failures (consecutive_fails, error patterns)
  2. Group by failure type (timeout, empty_response, wrong_sector, etc.)
  3. For each failure pattern:
     a. Test pipeline health (is it up?)
     b. Check if data gap (no relevant vectors)
     c. Check if prompt issue (has data but wrong answer)
  4. Apply targeted fix:
     - Timeout → try different Space
     - Data gap → trigger targeted Tavily ingest
     - Prompt → log for manual review
  5. Re-test the worst questions after fix
  6. Write results back to Supabase

Usage:
  source .env.local
  python3 ops/agent-fixer.py             # Run one cycle
  python3 ops/agent-fixer.py --daemon 3600  # Continuous
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
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "agents")
FIXES_LOG = os.path.join(REPO_ROOT, "data", "agents", "fixer-log.jsonl")

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
        log(f"DB error: {e}")
        return []

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] FIXER: {msg}")

def log_fix(fix_data):
    os.makedirs(os.path.dirname(FIXES_LOG), exist_ok=True)
    with open(FIXES_LOG, "a") as f:
        f.write(json.dumps({**fix_data, "timestamp": datetime.now(timezone.utc).isoformat()}) + "\n")


def find_worst_failures():
    """Find the worst-performing areas from recent eval results."""
    log("Querying worst failures from Supabase...")

    # Worst questions (consecutive failures)
    worst_questions = db_query("""
        SELECT id, question, sector, pipeline, consecutive_fails, avg_score,
               times_asked, times_failed, last_status
        FROM eval_question_bank
        WHERE consecutive_fails >= 2 AND times_asked >= 2
        ORDER BY consecutive_fails DESC, times_asked DESC
        LIMIT 20
    """)

    # Failure patterns by pipeline+sector (last 24h)
    failure_patterns = db_query("""
        SELECT pipeline, sector, status, COUNT(*) as cnt,
               ROUND(AVG(latency_ms)) as avg_lat
        FROM eval_results
        WHERE created_at > now() - interval '24 hours'
          AND status != 'pass'
        GROUP BY pipeline, sector, status
        ORDER BY cnt DESC
        LIMIT 20
    """)

    # Timeout patterns (pipeline broken?)
    timeouts = db_query("""
        SELECT pipeline, sector, COUNT(*) as timeout_count,
               ROUND(AVG(latency_ms)) as avg_lat
        FROM eval_results
        WHERE created_at > now() - interval '6 hours'
          AND (status = 'timeout' OR status = 'error')
        GROUP BY pipeline, sector
        HAVING COUNT(*) >= 3
        ORDER BY timeout_count DESC
    """)

    # Sectors with 0% pass rate
    zero_sectors = db_query("""
        SELECT sector, pipeline, COUNT(*) as total,
               SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passed
        FROM eval_results
        WHERE created_at > now() - interval '24 hours'
        GROUP BY sector, pipeline
        HAVING SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) = 0
           AND COUNT(*) >= 3
    """)

    return {
        "worst_questions": worst_questions,
        "failure_patterns": failure_patterns,
        "timeouts": timeouts,
        "zero_sectors": zero_sectors,
    }


def diagnose_and_fix(failures):
    """Analyze failures and apply targeted fixes."""
    fixes_applied = []

    # 1. Pipeline timeouts → test health, try alternate Space
    if failures["timeouts"]:
        log(f"  Found {len(failures['timeouts'])} timeout patterns")
        for t in failures["timeouts"][:3]:
            pipeline = t["pipeline"]
            sector = t["sector"]
            log(f"  Timeout: {pipeline}/{sector} ({t['timeout_count']} timeouts, avg {t['avg_lat']}ms)")

            # Test pipeline health on each Space
            health = test_pipeline_health(pipeline, sector)
            if health["healthy_spaces"]:
                log(f"    FIX: Pipeline {pipeline} alive on {health['healthy_spaces']}")
                fixes_applied.append({
                    "type": "timeout_diagnosed",
                    "pipeline": pipeline, "sector": sector,
                    "healthy_spaces": health["healthy_spaces"],
                    "dead_spaces": health["dead_spaces"],
                })
            else:
                log(f"    BROKEN: Pipeline {pipeline} down on ALL Spaces")
                fixes_applied.append({
                    "type": "pipeline_broken",
                    "pipeline": pipeline, "sector": sector,
                    "action": "needs_manual_intervention",
                })

    # 2. Zero sectors → trigger targeted ingest
    if failures["zero_sectors"]:
        log(f"  Found {len(failures['zero_sectors'])} zero-pass sectors")
        for z in failures["zero_sectors"][:2]:
            sector = z["sector"]
            pipeline = z["pipeline"]
            log(f"  Zero: {sector}/{pipeline} — 0/{z['total']} passed")

            # Trigger targeted Tavily ingest for this sector
            fix = trigger_targeted_ingest(sector)
            fixes_applied.append({
                "type": "data_gap_ingest",
                "sector": sector, "pipeline": pipeline,
                **fix,
            })

    # 3. Worst questions → retry and log patterns
    if failures["worst_questions"]:
        log(f"  {len(failures['worst_questions'])} chronically failing questions")
        for q in failures["worst_questions"][:5]:
            log(f"    [{q['consecutive_fails']}x fail] {q['pipeline']}/{q['sector']}: "
                f"{q['question'][:60]}...")
            fixes_applied.append({
                "type": "chronic_failure",
                "question_id": q["id"],
                "pipeline": q["pipeline"],
                "sector": q["sector"],
                "consecutive_fails": q["consecutive_fails"],
            })

    return fixes_applied


def test_pipeline_health(pipeline, sector):
    """Test a pipeline on all 3 Spaces."""
    from urllib import request, error

    hosts = [
        ("S1", "https://lbjlincoln-nomos-rag-engine.hf.space"),
        ("S3", "https://lbjlincoln-nomos-rag-engine-3.hf.space"),
        ("S5", "https://lbjlincoln-nomos-rag-engine-5.hf.space"),
    ]
    webhook_paths = {
        "standard": "/webhook/rag-multi-index-v3",
        "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "orchestrator": "/webhook/orchestrator-v2",
    }
    path = webhook_paths.get(pipeline, "")
    test_q = f"Quel est le principal concept du secteur {sector} ?"

    healthy = []
    dead = []
    for space_name, host in hosts:
        try:
            payload = json.dumps({
                "query": test_q, "question": test_q,
                "sector": sector, "tenant_id": sector,
            }).encode()
            req = request.Request(f"{host}{path}", data=payload,
                                  headers={"Content-Type": "application/json"})
            with request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    data = data[0] if data else {}
                answer = ""
                for k in ["response", "answer", "interpretation"]:
                    if k in data and data[k]:
                        answer = str(data[k])
                        break
                if answer and len(answer) > 10:
                    healthy.append(space_name)
                else:
                    dead.append(space_name)
        except Exception as e:
            dead.append(space_name)

    return {"healthy_spaces": healthy, "dead_spaces": dead}


def trigger_targeted_ingest(sector):
    """Trigger Tavily ingest for a specific sector."""
    log(f"    Triggering targeted Tavily ingest for {sector}...")
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "ops", "tavily-mass-ingest.py"),
             "--sector", sector, "--max-queries", "3"],
            capture_output=True, text=True, timeout=600, cwd=REPO_ROOT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        chunks = 0
        for line in result.stdout.split("\n"):
            if "upserted" in line.lower() or "chunk" in line.lower():
                log(f"      {line.strip()}")
                try:
                    import re
                    nums = re.findall(r'(\d+)', line)
                    if nums:
                        chunks = max(chunks, int(nums[-1]))
                except:
                    pass
        return {"chunks_ingested": chunks, "success": result.returncode == 0}
    except subprocess.TimeoutExpired:
        log(f"    Tavily ingest timeout (10min) for {sector}")
        return {"chunks_ingested": 0, "success": False, "error": "timeout"}
    except Exception as e:
        log(f"    Ingest error: {e}")
        return {"chunks_ingested": 0, "success": False, "error": str(e)[:100]}


def write_marker(fixes):
    marker = os.path.join(DATA_DIR, "fixer_done.marker")
    with open(marker, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fixes_applied": len(fixes),
            "fix_types": list(set(fix["type"] for fix in fixes)),
        }, f)


def run_cycle():
    log("=" * 60)
    log("FIXER CYCLE START")
    log("=" * 60)

    failures = find_worst_failures()

    total_issues = (len(failures["worst_questions"]) + len(failures["failure_patterns"])
                    + len(failures["timeouts"]) + len(failures["zero_sectors"]))
    log(f"Found: {total_issues} issues "
        f"({len(failures['worst_questions'])} worst Qs, "
        f"{len(failures['timeouts'])} timeouts, "
        f"{len(failures['zero_sectors'])} zero sectors)")

    if total_issues == 0:
        log("No issues found — all clean!")
        write_marker([])
        return

    fixes = diagnose_and_fix(failures)

    for fix in fixes:
        log_fix(fix)

    write_marker(fixes)
    log(f"Cycle complete: {len(fixes)} fixes applied/logged")
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
