#!/usr/bin/env python3
"""
Continuous Monitor — Background daemon for 10 HF Spaces cluster monitoring.

Runs as daemon:
  nohup python3 scripts/continuous-monitor.py &

Single-run mode:
  python3 scripts/continuous-monitor.py --once

Features:
- Every 5 min: ping 5 webhooks × 10 spaces (1 question each)
- Every 15 min: deep test 5 questions on primary space
- Detect: rate-limit, credentials, empty responses, outages
- Update: docs/status.json with live metrics
- Log: logs/monitor/YYYY-MM-DD.jsonl (append-only)
"""
import json
import os
import signal
import sys
import time
from datetime import datetime
from urllib import request, error

# Paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(REPO_ROOT, "logs", "monitor")
STATUS_JSON = os.path.join(REPO_ROOT, "docs", "status.json")

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

# 10 HF Spaces
SPACES = [
    "https://lbjlincoln-nomos-rag-engine.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-6.hf.space",
    "https://lbjlincoln-nomos-rag-engine-7.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-8.hf.space",
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",
    "https://lbjlincoln26-nomos-rag-engine-10.hf.space",
]

# Webhook config
WEBHOOKS = {
    "standard": {
        "path": "/webhook/rag-multi-index-v3",
        "field": "query",
        "test_q": "What is the capital of Japan?",
    },
    "graph": {
        "path": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "field": "query",
        "test_q": "What did Marie Curie win Nobel Prizes for?",
    },
    "quantitative": {
        "path": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "field": "query",
        "test_q": "What was TechVision Inc's total revenue in 2023?",
    },
    "orchestrator": {
        "path": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
        "field": "query",
        "test_q": "What is the largest ocean?",
    },
    "chatbot": {
        "path": "/webhook/project-chatbot",
        "field": "question",
        "test_q": "What is this project about?",
    },
}

# Deep test questions (5 per pipeline)
DEEP_QUESTIONS = {
    "standard": [
        "What is the capital of Japan?",
        "Who painted the Mona Lisa?",
        "What is the largest ocean?",
        "Where is Normandy located?",
        "What year did World War II end?",
    ],
    "graph": [
        "What did Marie Curie win Nobel Prizes for?",
        "What did Alexander Fleming discover?",
        "Who founded Microsoft?",
        "What is the WHO?",
        "What disease is caused by mosquitoes?",
    ],
    "quantitative": [
        "What was TechVision Inc's total revenue in 2023?",
        "What was GreenEnergy Corp's total revenue in 2023?",
        "What was HealthPlus Labs' net income in 2022?",
        "What was TechVision's revenue in Q1 2023?",
        "What is the total number of products across all companies?",
    ],
    "orchestrator": [
        "What is the capital of Japan?",
        "What was TechVision Inc's total revenue in 2023?",
        "What did Marie Curie win Nobel Prizes for?",
        "Who painted the Mona Lisa?",
        "What is the largest ocean?",
    ],
}

# State
SHUTDOWN = False


def handle_sigterm(signum, frame):
    """Graceful shutdown on SIGTERM/SIGINT."""
    global SHUTDOWN
    print(f"\n[{now()}] SIGTERM received — shutting down gracefully...")
    SHUTDOWN = True


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


def now():
    """ISO timestamp."""
    return datetime.utcnow().isoformat() + "Z"


def log_to_file(event):
    """Append JSON line to daily log file."""
    date = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = os.path.join(LOGS_DIR, f"{date}.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(event) + "\n")


def call_webhook(space_url, webhook_path, field, query, timeout=30):
    """
    Call webhook and return result dict.

    Returns:
      {
        "status": "ok" | "empty" | "error" | "timeout",
        "latency_ms": int,
        "answer": str,
        "error": str | None,
        "http_code": int | None
      }
    """
    url = space_url + webhook_path
    payload = json.dumps({
        field: query,
        "tenant_id": "monitor",
        "benchmark_mode": True,
    }).encode()
    headers = {"Content-Type": "application/json"}

    try:
        req = request.Request(url, data=payload, headers=headers, method="POST")
        start = time.time()
        with request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.time() - start) * 1000)
            raw = resp.read().decode()
            if raw and raw.strip():
                data = json.loads(raw)
                if isinstance(data, list):
                    data = data[0] if data else {}
                # Extract answer from various keys
                answer = ""
                for key in ["response", "answer", "result", "interpretation", "final_response"]:
                    if key in data and data[key]:
                        answer = str(data[key])
                        break
                if answer and len(answer) > 5:
                    return {
                        "status": "ok",
                        "latency_ms": latency,
                        "answer": answer,
                        "error": None,
                        "http_code": 200,
                    }
                else:
                    return {
                        "status": "empty",
                        "latency_ms": latency,
                        "answer": answer,
                        "error": "Empty or very short answer",
                        "http_code": 200,
                    }
            else:
                return {
                    "status": "empty",
                    "latency_ms": latency,
                    "answer": "",
                    "error": "Empty response body",
                    "http_code": 200,
                }
    except error.HTTPError as e:
        err_body = e.read().decode()[:200] if e.fp else ""
        return {
            "status": "error",
            "latency_ms": 0,
            "answer": "",
            "error": f"HTTP {e.code}: {err_body}",
            "http_code": e.code,
        }
    except Exception as e:
        err_str = str(e)
        if "timed out" in err_str.lower():
            return {
                "status": "timeout",
                "latency_ms": timeout * 1000,
                "answer": "",
                "error": f"Timeout after {timeout}s",
                "http_code": None,
            }
        return {
            "status": "error",
            "latency_ms": 0,
            "answer": "",
            "error": str(e)[:200],
            "http_code": None,
        }


def lightweight_ping():
    """
    Ping 5 webhooks on 3 sample spaces (representative sample).
    Returns dict with results and detected patterns.
    """
    # Sample 3 spaces: primary, middle, last
    sample_spaces = [SPACES[0], SPACES[4], SPACES[9]]
    print(f"[{now()}] Lightweight ping: 5 webhooks × 3 sample spaces")
    results = []

    for i, space in enumerate(sample_spaces):
        space_name = space.split("//")[1].split(".")[0]
        print(f"  Testing space {i+1}/3: {space_name}")
        for pipe, config in WEBHOOKS.items():
            res = call_webhook(
                space, config["path"], config["field"], config["test_q"], timeout=60
            )
            results.append({
                "space": space_name,
                "pipeline": pipe,
                "status": res["status"],
                "latency_ms": res["latency_ms"],
                "error": res["error"],
                "http_code": res["http_code"],
            })
            print(f"    {pipe}: {res['status']} ({res['latency_ms']}ms)")
            # Small delay to avoid hammering
            time.sleep(1)

    # Analyze patterns
    total = len(results)
    ok = sum(1 for r in results if r["status"] == "ok")
    empty = sum(1 for r in results if r["status"] == "empty")
    errors = sum(1 for r in results if r["status"] == "error")
    timeouts = sum(1 for r in results if r["status"] == "timeout")
    rate_limit = sum(1 for r in results if r["http_code"] == 429)
    slow = sum(1 for r in results if r["latency_ms"] > 30000)
    credential_errors = sum(
        1 for r in results if r["error"] and "credential" in r["error"].lower()
    )

    patterns = {
        "rate_limiting": rate_limit > 0 or slow > 5,
        "credential_issues": credential_errors > 0,
        "empty_responses": empty > total * 0.2,  # >20% empty
        "total_outage": ok == 0,
    }

    summary = {
        "timestamp": now(),
        "type": "lightweight_ping",
        "total_tests": total,
        "ok": ok,
        "empty": empty,
        "errors": errors,
        "timeouts": timeouts,
        "rate_limit_429": rate_limit,
        "slow_30s": slow,
        "credential_errors": credential_errors,
        "patterns": patterns,
        "results": results,
    }

    log_to_file(summary)
    print(f"  Results: {ok}/{total} OK, {empty} empty, {errors} errors, {timeouts} timeout")
    if patterns["rate_limiting"]:
        print("  ⚠ PATTERN: Rate limiting detected")
    if patterns["credential_issues"]:
        print("  ⚠ PATTERN: Credential issues detected")
    if patterns["empty_responses"]:
        print("  ⚠ PATTERN: High rate of empty responses")
    if patterns["total_outage"]:
        print("  ⚠ PATTERN: TOTAL OUTAGE — no spaces responding")

    return summary


def deep_test():
    """
    Run 5 questions per pipeline on primary space.
    Returns dict with results and patterns.
    """
    primary = SPACES[0]
    print(f"[{now()}] Deep test: 5 questions per pipeline on primary space")
    results = {}

    for pipe in ["standard", "graph", "quantitative", "orchestrator"]:
        config = WEBHOOKS[pipe]
        questions = DEEP_QUESTIONS.get(pipe, [])
        pipe_results = []

        for q in questions:
            res = call_webhook(
                primary, config["path"], config["field"], q, timeout=90
            )
            pipe_results.append({
                "query": q,
                "status": res["status"],
                "latency_ms": res["latency_ms"],
                "answer_preview": res["answer"][:100] if res["answer"] else "",
                "error": res["error"],
            })
            time.sleep(2)  # 2s between questions

        ok = sum(1 for r in pipe_results if r["status"] == "ok")
        results[pipe] = {
            "tested": len(pipe_results),
            "ok": ok,
            "accuracy_pct": round(ok / len(pipe_results) * 100, 1) if pipe_results else 0,
            "results": pipe_results,
        }

    summary = {
        "timestamp": now(),
        "type": "deep_test",
        "space": primary.split("//")[1].split(".")[0],
        "pipelines": results,
    }

    log_to_file(summary)
    for pipe, res in results.items():
        print(f"  {pipe}: {res['ok']}/{res['tested']} OK ({res['accuracy_pct']}%)")

    return summary


def update_status_json(ping_summary, deep_summary):
    """
    Update docs/status.json with live metrics from monitoring.
    Merge with existing status or create minimal if missing.
    """
    # Load existing status
    if os.path.exists(STATUS_JSON):
        with open(STATUS_JSON) as f:
            status = json.load(f)
    else:
        status = {
            "generated_at": now(),
            "phase": {"current": 1, "name": "Baseline (200q)", "gates_passed": False},
            "pipelines": {},
            "overall": {"accuracy": 0, "target": 75.0, "met": False},
            "blockers": [],
            "next_action": "Run continuous monitoring",
            "totals": {},
        }

    # Add monitor section
    status["monitor"] = {
        "last_check": now(),
        "lightweight_ping": {
            "timestamp": ping_summary["timestamp"],
            "ok_pct": round(ping_summary["ok"] / ping_summary["total_tests"] * 100, 1),
            "total_tests": ping_summary["total_tests"],
            "ok": ping_summary["ok"],
            "patterns": ping_summary["patterns"],
        },
        "deep_test": {
            "timestamp": deep_summary["timestamp"] if deep_summary else None,
            "pipelines": {
                pipe: {
                    "accuracy_pct": res["accuracy_pct"],
                    "tested": res["tested"],
                    "ok": res["ok"],
                }
                for pipe, res in deep_summary["pipelines"].items()
            } if deep_summary else {},
        },
    }

    # Write atomically
    tmp = STATUS_JSON + ".tmp"
    with open(tmp, "w") as f:
        json.dump(status, f, indent=2)
    os.replace(tmp, STATUS_JSON)
    print(f"  Updated {STATUS_JSON}")


def run_daemon():
    """Main daemon loop."""
    print(f"[{now()}] Continuous monitor started (PID {os.getpid()})")
    print(f"  Logs: {LOGS_DIR}")
    print(f"  Status: {STATUS_JSON}")
    print(f"  Schedule: ping 5min, deep test 15min")

    last_ping = 0
    last_deep = 0
    PING_INTERVAL = 5 * 60  # 5 minutes
    DEEP_INTERVAL = 15 * 60  # 15 minutes

    while not SHUTDOWN:
        now_ts = time.time()

        # Lightweight ping every 5 min
        if now_ts - last_ping >= PING_INTERVAL:
            try:
                ping_summary = lightweight_ping()
                last_ping = now_ts

                # Deep test every 15 min
                deep_summary = None
                if now_ts - last_deep >= DEEP_INTERVAL:
                    deep_summary = deep_test()
                    last_deep = now_ts

                # Update status.json
                update_status_json(ping_summary, deep_summary)
            except Exception as e:
                print(f"[{now()}] ERROR in monitor loop: {e}")
                log_to_file({
                    "timestamp": now(),
                    "type": "error",
                    "error": str(e)[:500],
                })

        # Sleep 30s between checks
        time.sleep(30)

    print(f"[{now()}] Continuous monitor stopped")


def run_once():
    """Single-run mode for testing."""
    print(f"[{now()}] Single-run mode")
    ping_summary = lightweight_ping()
    deep_summary = deep_test()
    update_status_json(ping_summary, deep_summary)
    print(f"[{now()}] Done")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Continuous HF Spaces monitor")
    parser.add_argument("--once", action="store_true", help="Single-run mode (no daemon)")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        run_daemon()


if __name__ == "__main__":
    main()
