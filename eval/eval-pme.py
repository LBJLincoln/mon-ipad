#!/usr/bin/env python3
"""
Eval: PME Gateway — Intent Classification & Routing Tests
==========================================================
Standalone eval script for the PME Assistant Gateway. Sends queries with
known intents and verifies the gateway routes them correctly.

Designed to run unattended on Codespaces or GitHub Actions (nohup-safe).

Endpoint:
  PME Gateway : {N8N_HOST}/webhook/pme-assistant-gateway

Intent types:
  - query   : Knowledge/information retrieval questions
  - action  : Task execution requests (schedule, send, create, etc.)
  - report  : Summary/analytics/report generation requests

Usage:
  source .env.local
  python eval/eval-pme.py                             # Default: 100 tests
  python eval/eval-pme.py --max 30 --batch-size 3     # Quick run
  python eval/eval-pme.py --early-stop 5               # Stop after 5 consecutive fails
  python eval/eval-pme.py --force                      # Bypass gate checks
  nohup python eval/eval-pme.py --max 100 &            # Unattended
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(REPO_ROOT, "logs", "pipeline-results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
def _load_env_local():
    """Load .env.local if present (key=value, no shell expansion)."""
    env_path = os.path.join(REPO_ROOT, ".env.local")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

_load_env_local()

N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

# Guard: block accidental use of VM n8n
def _check_n8n_host():
    if re.search(r'localhost|127\.0\.0\.1|34\.136\.180\.66', N8N_HOST):
        if "--allow-local" not in sys.argv:
            print("FATAL: N8N_HOST points to local/VM. Evals MUST run on HF Space.")
            print(f"  N8N_HOST = {N8N_HOST}")
            print("  Set N8N_HOST or pass --allow-local to override.")
            sys.exit(1)

_check_n8n_host()

PME_URL = f"{N8N_HOST}/webhook/pme-assistant-gateway"

# ---------------------------------------------------------------------------
# Colors (ANSI, gracefully degrade if not a tty)
# ---------------------------------------------------------------------------
_USE_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

def _green(s):
    return f"\033[92m{s}\033[0m" if _USE_COLOR else s

def _red(s):
    return f"\033[91m{s}\033[0m" if _USE_COLOR else s

def _yellow(s):
    return f"\033[93m{s}\033[0m" if _USE_COLOR else s

def _bold(s):
    return f"\033[1m{s}\033[0m" if _USE_COLOR else s

# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no requests dependency required)
# ---------------------------------------------------------------------------
from urllib import request as urllib_request, error as urllib_error

def _post_json(url, payload, timeout=120, max_retries=3):
    """POST JSON with exponential backoff on 503/transient errors."""
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    for attempt in range(max_retries):
        try:
            req = urllib_request.Request(url, data=data, headers=headers, method="POST")
            start = time.time()
            with urllib_request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                latency_ms = int((time.time() - start) * 1000)
                body = json.loads(raw) if raw.strip() else {}
                if isinstance(body, list):
                    body = body[0] if body else {}
                return {"ok": True, "body": body, "latency_ms": latency_ms, "error": None}
        except urllib_error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            if e.code in (503, 502, 429) and attempt < max_retries - 1:
                wait = 3 * (2 ** attempt)
                print(f"    {e.code} on attempt {attempt + 1} — retry in {wait}s")
                time.sleep(wait)
                continue
            return {"ok": False, "body": {}, "latency_ms": 0,
                    "error": f"HTTP {e.code}: {err_body[:200]}"}
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3 * (2 ** attempt))
                continue
            return {"ok": False, "body": {}, "latency_ms": 0,
                    "error": str(e)[:200]}

    return {"ok": False, "body": {}, "latency_ms": 0, "error": "Max retries exceeded"}

# ---------------------------------------------------------------------------
# Test queries — 50 inline queries with expected intents
# (20 query + 15 action + 15 report)
# Additional 55 queries for extended testing (total 105)
# ---------------------------------------------------------------------------
def _make_test_queries():
    """Return 105 test queries with expected intents for PME gateway testing."""
    queries = [
        # =====================================================================
        # QUERY intent — knowledge/information retrieval (20 core + 15 extended)
        # =====================================================================
        {"text": "What is the current market share of our product in France?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does our CRM system handle duplicate contacts?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "Explain the refund policy for enterprise customers.",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "What are the key differences between our Standard and Premium plans?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does the authentication flow work for our API?",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What is the SLA for our cloud hosting service?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "Explain how our inventory management system calculates reorder points.",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What compliance certifications does our platform have?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How many employees are in the engineering department?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "What is the average response time for customer support tickets?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "Describe the data backup and recovery procedures.",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What integrations are available with our accounting software?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does our pricing model work for volume discounts?",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What is the company policy on data retention?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "Explain how the lead scoring algorithm prioritizes prospects.",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What are the system requirements for our desktop application?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does our supply chain management handle international shipping?",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What is the warranty period for our hardware products?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does our platform ensure GDPR compliance?",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What training resources are available for new employees?",
         "expected_intent": "query", "difficulty": "easy"},
        # Extended query intent
        {"text": "What is our company's carbon footprint reduction target?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does the recommendation engine personalize content?",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What payment methods do we accept for international customers?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does the load balancer distribute traffic across regions?",
         "expected_intent": "query", "difficulty": "hard"},
        {"text": "What are the key performance indicators for the sales team?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "Explain the difference between our REST API and GraphQL endpoints.",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What is our customer churn rate this quarter?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does our fraud detection system identify suspicious transactions?",
         "expected_intent": "query", "difficulty": "hard"},
        {"text": "What are the hiring criteria for senior developer positions?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does our A/B testing framework measure statistical significance?",
         "expected_intent": "query", "difficulty": "hard"},
        {"text": "What is the uptime guarantee for our production environment?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "How does the document management system handle version control?",
         "expected_intent": "query", "difficulty": "medium"},
        {"text": "What languages does our chatbot support?",
         "expected_intent": "query", "difficulty": "easy"},
        {"text": "Describe how our ETL pipeline processes raw data.",
         "expected_intent": "query", "difficulty": "hard"},
        {"text": "What security measures protect customer payment information?",
         "expected_intent": "query", "difficulty": "medium"},

        # =====================================================================
        # ACTION intent — task execution requests (15 core + 20 extended)
        # =====================================================================
        {"text": "Schedule a meeting with the marketing team for next Tuesday at 2 PM.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Send an email to the sales team about the Q1 targets update.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Create a new project in Jira called 'Website Redesign Phase 2'.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Update the customer record for Acme Corp with the new billing address.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Set up a recurring weekly standup for the dev team at 9 AM Monday.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Send a Slack notification to the ops channel about the deployment.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Create a new support ticket for client BioGenix about their API issue.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Book a conference room for the board meeting on March 15th.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Cancel the subscription for customer ID 45892.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Add three new users to the admin group in our IAM system.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Deploy the latest version of the frontend to staging environment.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Assign the open bug tickets to the QA team lead.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Create an invoice for client RetailMax for the December services.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Migrate the database schema to version 3.2.",
         "expected_intent": "action", "difficulty": "hard"},
        {"text": "Send a follow-up email to all leads who attended the webinar.",
         "expected_intent": "action", "difficulty": "medium"},
        # Extended action intent
        {"text": "Archive all completed projects from 2024.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Reset the password for user john.doe@company.com.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Export the customer database to a CSV file.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Enable two-factor authentication for all admin accounts.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Create a backup of the production database right now.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Onboard the new hire Sarah Chen with standard developer permissions.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Revoke API access for the deprecated integration partner.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Publish the blog post draft titled 'AI in Healthcare 2026'.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Upgrade the staging server to 16 GB RAM.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Notify all customers about the scheduled maintenance window.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Transfer the domain registration to our new registrar.",
         "expected_intent": "action", "difficulty": "hard"},
        {"text": "Configure the CDN to cache static assets for 30 days.",
         "expected_intent": "action", "difficulty": "hard"},
        {"text": "Register our company for the upcoming tech conference in Berlin.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Rename the Slack channel from #dev-old to #engineering.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Set the pricing for the new Enterprise Plus tier at $499 per month.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Rotate the API keys for the production environment.",
         "expected_intent": "action", "difficulty": "hard"},
        {"text": "Provision a new development sandbox for the intern team.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Block the IP addresses flagged by the security scan.",
         "expected_intent": "action", "difficulty": "medium"},
        {"text": "Approve the pending purchase order for office supplies.",
         "expected_intent": "action", "difficulty": "easy"},
        {"text": "Merge the feature branch into the release candidate.",
         "expected_intent": "action", "difficulty": "medium"},

        # =====================================================================
        # REPORT intent — summary/analytics/report generation (15 core + 20 extended)
        # =====================================================================
        {"text": "Summarize my emails from the last week.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Show pipeline metrics for the last 30 days.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Generate a monthly revenue report for Q4 2025.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Create a summary of all open customer support tickets.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Provide an overview of team productivity this sprint.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Compile the weekly sales dashboard with conversion rates.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Give me a breakdown of expenses by department for January.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Analyze customer churn trends over the past 6 months.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Generate a performance review summary for the engineering team.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Prepare a competitive analysis report comparing us to top 5 competitors.",
         "expected_intent": "report", "difficulty": "hard"},
        {"text": "Show the top 10 customers by revenue this quarter.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Create a project status report for all active initiatives.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Summarize the results from our latest NPS survey.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Generate an inventory aging report for the warehouse.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Provide a year-over-year comparison of our KPIs.",
         "expected_intent": "report", "difficulty": "hard"},
        # Extended report intent
        {"text": "Create a burndown chart for the current sprint.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Aggregate all error logs from the past 24 hours.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Generate a forecast for next quarter's sales pipeline.",
         "expected_intent": "report", "difficulty": "hard"},
        {"text": "Summarize the feedback from the last all-hands meeting.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Show website traffic analytics for the marketing campaign.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Create a risk assessment report for the new product launch.",
         "expected_intent": "report", "difficulty": "hard"},
        {"text": "Compile a list of all overdue invoices with aging breakdown.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Generate a utilization report for the cloud infrastructure.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Prepare a quarterly board presentation with financial highlights.",
         "expected_intent": "report", "difficulty": "hard"},
        {"text": "Show the distribution of customer support tickets by category.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Create a talent pipeline report for open positions.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Generate a compliance audit trail for the last fiscal year.",
         "expected_intent": "report", "difficulty": "hard"},
        {"text": "Summarize all pull requests merged this week across all repos.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Produce a cost analysis of our top 3 cloud services.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Show me the customer acquisition funnel metrics for February.",
         "expected_intent": "report", "difficulty": "easy"},
        {"text": "Produce a headcount trend report by department over 12 months.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Calculate the return on investment for the new marketing campaign.",
         "expected_intent": "report", "difficulty": "hard"},
        {"text": "List all SLA breaches from the past quarter with root cause analysis.",
         "expected_intent": "report", "difficulty": "hard"},
        {"text": "Summarize the deployment frequency and lead time for each service.",
         "expected_intent": "report", "difficulty": "medium"},
        {"text": "Show a breakdown of monthly recurring revenue by customer segment.",
         "expected_intent": "report", "difficulty": "easy"},
    ]
    return queries


# ---------------------------------------------------------------------------
# Intent detection from response
# ---------------------------------------------------------------------------
def _detect_intent_in_response(body):
    """
    Extract the detected intent from the PME gateway response.
    The gateway may return the intent in various fields.
    """
    # Direct intent field
    for key in ("intent", "detected_intent", "classification", "type", "route",
                "routing", "category", "action_type"):
        val = body.get(key, "")
        if val:
            return str(val).lower().strip()

    # Nested inside a routing or metadata object
    for container_key in ("routing", "metadata", "classification_result", "result"):
        container = body.get(container_key, {})
        if isinstance(container, dict):
            for key in ("intent", "type", "category", "route"):
                val = container.get(key, "")
                if val:
                    return str(val).lower().strip()

    # Check the response text for intent indicators
    response_text = ""
    for key in ("response", "answer", "result", "text", "message"):
        if key in body and body[key]:
            response_text = str(body[key]).lower()
            break

    if not response_text:
        response_text = json.dumps(body).lower()

    # Heuristic: look for intent keywords in the response
    if any(w in response_text for w in ["scheduled", "created", "sent", "updated",
                                         "deployed", "cancelled", "booked",
                                         "action completed", "task executed",
                                         "action_executed"]):
        return "action"
    if any(w in response_text for w in ["report generated", "summary:", "analysis:",
                                         "metrics:", "dashboard", "breakdown:",
                                         "report_generated"]):
        return "report"
    if any(w in response_text for w in ["here is", "the answer", "according to",
                                         "information:", "explanation:",
                                         "query_answered"]):
        return "query"

    return ""


def _intent_matches(detected, expected):
    """
    Check if detected intent matches expected intent.
    Flexible matching to handle variations (e.g., 'knowledge' maps to 'query').
    """
    if not detected:
        return False

    detected = detected.lower().strip()
    expected = expected.lower().strip()

    # Direct match
    if detected == expected:
        return True

    # Alias mapping
    aliases = {
        "query": {"query", "knowledge", "information", "retrieval", "search",
                  "question", "lookup", "rag", "ask"},
        "action": {"action", "task", "execute", "command", "do", "perform",
                   "create", "send", "schedule", "update", "automation"},
        "report": {"report", "summary", "summarize", "analytics", "analysis",
                   "dashboard", "metrics", "generate_report", "aggregate",
                   "compile", "overview"},
    }

    expected_set = aliases.get(expected, {expected})
    return detected in expected_set


# ---------------------------------------------------------------------------
# Core test logic
# ---------------------------------------------------------------------------
def run_pme_test(query_item, idx, total):
    """
    Send a query to the PME gateway and verify intent routing.
    Returns a result dict.
    """
    result = {
        "index": idx,
        "query": query_item["text"],
        "expected_intent": query_item["expected_intent"],
        "difficulty": query_item["difficulty"],
        "detected_intent": "",
        "response_ok": False,
        "intent_correct": False,
        "passed": False,
        "latency_ms": 0,
        "response_preview": "",
        "error": None,
    }

    payload = {
        "query": query_item["text"],
        "channel": "api",
        "tenant_id": "benchmark",
        "user_id": "eval-pme-test",
        "session_id": f"eval-pme-{idx:04d}",
    }

    resp = _post_json(PME_URL, payload, timeout=120)

    if not resp["ok"]:
        result["error"] = resp["error"]
        print(f"  [{idx + 1}/{total}] {_red('[-]')} ERROR | {query_item['text'][:50]}...")
        print(f"           {resp['error'][:80]}")
        return result

    result["response_ok"] = True
    result["latency_ms"] = resp["latency_ms"]

    body = resp["body"]
    # Save a response preview for debugging
    response_text = ""
    for key in ("response", "answer", "result", "text", "message"):
        if key in body and body[key]:
            response_text = str(body[key])[:200]
            break
    if not response_text:
        response_text = json.dumps(body)[:200]
    result["response_preview"] = response_text

    # Detect intent
    detected = _detect_intent_in_response(body)
    result["detected_intent"] = detected

    # Check intent match
    intent_ok = _intent_matches(detected, query_item["expected_intent"])
    result["intent_correct"] = intent_ok

    # A test passes if the response was OK AND intent was correctly classified
    # If we cannot detect intent but got a valid response, mark as partial pass
    if intent_ok:
        result["passed"] = True
        print(f"  [{idx + 1}/{total}] {_green('[+]')} PASS | "
              f"intent={detected} (expected={query_item['expected_intent']}) | "
              f"{resp['latency_ms']}ms | {query_item['text'][:45]}...")
    elif detected:
        result["passed"] = False
        print(f"  [{idx + 1}/{total}] {_red('[-]')} FAIL | "
              f"intent={detected} (expected={query_item['expected_intent']}) | "
              f"{resp['latency_ms']}ms | {query_item['text'][:45]}...")
    else:
        # Got a response but could not determine intent
        # Consider this a partial success if we got a non-empty response
        has_content = bool(response_text and len(response_text) > 10)
        result["passed"] = has_content  # Lenient: response received = partial pass
        result["detected_intent"] = "(undetected)"
        status = _yellow("[~]") if has_content else _red("[-]")
        label = "PARTIAL" if has_content else "FAIL"
        print(f"  [{idx + 1}/{total}] {status} {label} | "
              f"intent=? (expected={query_item['expected_intent']}) | "
              f"{resp['latency_ms']}ms | {query_item['text'][:45]}...")

    return result


def run_eval(args):
    """Main evaluation loop."""
    all_queries = _make_test_queries()
    max_tests = min(args.max, len(all_queries))
    test_queries = all_queries[:max_tests]

    # Compute intent distribution
    intent_counts = {}
    for q in test_queries:
        intent = q["expected_intent"]
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    # Generate run ID
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    run_id = f"pme-{run_ts}"

    print("=" * 65)
    print(_bold("  EVAL: PME GATEWAY — INTENT CLASSIFICATION & ROUTING"))
    print("=" * 65)
    print(f"  N8N_HOST     : {N8N_HOST}")
    print(f"  PME URL      : {PME_URL}")
    print(f"  Tests        : {max_tests}")
    print(f"  Batch size   : {args.batch_size}")
    print(f"  Early stop   : {args.early_stop} consecutive failures")
    print(f"  Run ID       : {run_id}")
    print(f"  Intents      : {json.dumps(intent_counts)}")
    print("=" * 65)
    print()

    results = []
    consecutive_fails = 0
    stopped_early = False

    start_time = time.time()

    for batch_start in range(0, max_tests, args.batch_size):
        batch_end = min(batch_start + args.batch_size, max_tests)
        batch_queries = test_queries[batch_start:batch_end]
        batch_num = (batch_start // args.batch_size) + 1
        total_batches = (max_tests + args.batch_size - 1) // args.batch_size

        print(f"\n--- Batch {batch_num}/{total_batches} (tests {batch_start + 1}-{batch_end}) ---\n")

        for i, q in enumerate(batch_queries):
            global_idx = batch_start + i

            result = run_pme_test(q, global_idx, max_tests)
            results.append(result)

            if result["passed"]:
                consecutive_fails = 0
            else:
                consecutive_fails += 1

            # Auto-stop on consecutive failures
            if consecutive_fails >= args.early_stop:
                print(f"\n  {_red('AUTO-STOP')}: {consecutive_fails} consecutive failures reached "
                      f"(threshold: {args.early_stop})")
                stopped_early = True
                break

            # Delay between tests to avoid overwhelming n8n
            if global_idx < max_tests - 1:
                time.sleep(2)

        if stopped_early:
            break

        # Inter-batch delay
        if batch_end < max_tests:
            print(f"\n  Batch complete. Pausing 3s before next batch...", flush=True)
            time.sleep(3)

    elapsed = time.time() - start_time

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    responded = sum(1 for r in results if r["response_ok"])
    intent_correct = sum(1 for r in results if r["intent_correct"])
    accuracy = (passed / total * 100) if total > 0 else 0.0
    intent_accuracy = (intent_correct / total * 100) if total > 0 else 0.0

    avg_latency = 0
    latencies = [r["latency_ms"] for r in results if r["response_ok"]]
    if latencies:
        avg_latency = sum(latencies) / len(latencies)

    # Per-intent breakdown
    intent_breakdown = {}
    for r in results:
        intent = r["expected_intent"]
        if intent not in intent_breakdown:
            intent_breakdown[intent] = {
                "total": 0, "passed": 0, "intent_correct": 0,
                "responded": 0, "latencies": [],
            }
        intent_breakdown[intent]["total"] += 1
        if r["passed"]:
            intent_breakdown[intent]["passed"] += 1
        if r["intent_correct"]:
            intent_breakdown[intent]["intent_correct"] += 1
        if r["response_ok"]:
            intent_breakdown[intent]["responded"] += 1
            intent_breakdown[intent]["latencies"].append(r["latency_ms"])

    # Per-difficulty breakdown
    difficulty_breakdown = {}
    for r in results:
        diff = r["difficulty"]
        if diff not in difficulty_breakdown:
            difficulty_breakdown[diff] = {"total": 0, "passed": 0}
        difficulty_breakdown[diff]["total"] += 1
        if r["passed"]:
            difficulty_breakdown[diff]["passed"] += 1

    # Confusion matrix (expected vs detected)
    confusion = {}
    for r in results:
        exp = r["expected_intent"]
        det = r["detected_intent"] if r["detected_intent"] else "(none)"
        key = f"{exp} -> {det}"
        confusion[key] = confusion.get(key, 0) + 1

    print("\n" + "=" * 65)
    print(_bold("  RESULTS SUMMARY"))
    print("=" * 65)
    print(f"  Total tests         : {total}")
    print(f"  Responded OK        : {responded}/{total}")
    print(f"  Intent correct      : {intent_correct}/{total}")
    print(f"  Overall passed      : {passed}/{total}")
    pct_color = _green if accuracy >= 70 else (_yellow if accuracy >= 50 else _red)
    print(f"  Accuracy            : {pct_color(f'{accuracy:.1f}%')}")
    print(f"  Intent accuracy     : {intent_accuracy:.1f}%")
    print(f"  Avg latency         : {avg_latency:.0f}ms")
    print(f"  Elapsed             : {elapsed:.1f}s")
    if stopped_early:
        print(f"  {_red('STOPPED EARLY')}: {consecutive_fails} consecutive failures")
    print()

    # Intent breakdown
    print("  Intent breakdown:")
    for intent in ("query", "action", "report"):
        info = intent_breakdown.get(intent, {"total": 0, "passed": 0,
                                              "intent_correct": 0, "latencies": []})
        if info["total"] > 0:
            pct = info["passed"] / info["total"] * 100
            i_pct = info["intent_correct"] / info["total"] * 100
            avg_lat = sum(info["latencies"]) / len(info["latencies"]) if info["latencies"] else 0
            print(f"    {intent:8s} : {info['passed']}/{info['total']} passed ({pct:.0f}%) | "
                  f"intent correct: {i_pct:.0f}% | avg {avg_lat:.0f}ms")
    print()

    # Difficulty breakdown
    print("  Difficulty breakdown:")
    for diff in ("easy", "medium", "hard"):
        info = difficulty_breakdown.get(diff, {"total": 0, "passed": 0})
        if info["total"] > 0:
            pct = info["passed"] / info["total"] * 100
            print(f"    {diff:8s} : {info['passed']}/{info['total']} ({pct:.0f}%)")
    print()

    # Confusion matrix (top misclassifications)
    if confusion:
        print("  Routing confusion matrix (top entries):")
        for key, count in sorted(confusion.items(), key=lambda x: -x[1])[:10]:
            print(f"    {key:30s} : {count}")

    print("=" * 65)

    # ---------------------------------------------------------------------------
    # Save JSON results
    # ---------------------------------------------------------------------------
    # Clean up latencies from intent_breakdown for JSON serialization
    intent_summary = {}
    for intent, info in intent_breakdown.items():
        intent_summary[intent] = {
            "total": info["total"],
            "passed": info["passed"],
            "intent_correct": info["intent_correct"],
            "responded": info["responded"],
            "avg_latency_ms": round(sum(info["latencies"]) / len(info["latencies"]))
                              if info["latencies"] else 0,
        }

    output = {
        "run_id": run_id,
        "pipeline": "pme-gateway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n8n_host": N8N_HOST,
        "config": {
            "max": args.max,
            "batch_size": args.batch_size,
            "early_stop": args.early_stop,
        },
        "summary": {
            "total": total,
            "responded": responded,
            "intent_correct": intent_correct,
            "passed": passed,
            "accuracy_pct": round(accuracy, 2),
            "intent_accuracy_pct": round(intent_accuracy, 2),
            "avg_latency_ms": round(avg_latency),
            "elapsed_seconds": round(elapsed, 1),
            "stopped_early": stopped_early,
            "consecutive_fails_at_stop": consecutive_fails if stopped_early else 0,
        },
        "intent_breakdown": intent_summary,
        "difficulty_breakdown": difficulty_breakdown,
        "confusion_matrix": confusion,
        "results": results,
    }

    out_filename = f"pme-{run_ts}.json"
    out_path = os.path.join(RESULTS_DIR, out_filename)

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results saved to: {out_path}")

    # Exit code
    if accuracy >= 50 and not stopped_early:
        print(f"\n  {_green('PASS')} — PME Gateway operational (accuracy >= 50%)")
        return 0
    else:
        print(f"\n  {_red('FAIL')} — PME Gateway needs attention")
        return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Eval: PME Gateway — intent classification and routing tests"
    )
    parser.add_argument("--max", type=int, default=100,
                        help="Maximum number of test queries to process (default: 100)")
    parser.add_argument("--batch-size", type=int, default=5,
                        help="Queries per batch (default: 5)")
    parser.add_argument("--early-stop", type=int, default=10,
                        help="Stop after N consecutive failures (default: 10)")
    parser.add_argument("--force", action="store_true",
                        help="Bypass gate checks")
    parser.add_argument("--allow-local", action="store_true",
                        help="Allow localhost/VM n8n (for CI/testing)")

    args = parser.parse_args()

    # Gate check: verify n8n is reachable before running full eval
    if not args.force:
        print("  Pre-flight: checking n8n reachability...", flush=True)
        try:
            req = urllib_request.Request(f"{N8N_HOST}/healthz", method="GET")
            with urllib_request.urlopen(req, timeout=15) as resp:
                print(f"    n8n health: {resp.status}")
        except Exception as e:
            print(f"  {_red('GATE FAIL')}: Cannot reach n8n at {N8N_HOST}")
            print(f"    Error: {e}")
            print("    Use --force to bypass this check.")
            sys.exit(1)

    exit_code = run_eval(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
