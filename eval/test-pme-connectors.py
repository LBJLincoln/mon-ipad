#!/usr/bin/env python3
"""
Test PME Connectors — Smoke test multi-canal assistant workflows.

Tests the gateway webhook, intent classification, and action routing.
Does NOT require real credentials (tests API channel only).

Usage:
  python test-pme-connectors.py                    # All tests
  python test-pme-connectors.py --only gateway     # Gateway only
  python test-pme-connectors.py --only intent      # Intent classification only
  python test-pme-connectors.py --only actions     # Action routing only
"""

import json
import os
import sys
import time
from datetime import datetime
from urllib import request, error

N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

# Guard: block accidental use of VM n8n for evals
def _check_n8n_host():
    import re
    if re.search(r'localhost|127\.0\.0\.1|34\.136\.180\.66', N8N_HOST):
        if "--allow-local" not in sys.argv:
            print(f"FATAL: N8N_HOST points to local/VM ({N8N_HOST}).")
            print("Evals MUST run on HF Space. Set N8N_HOST or pass --allow-local.")
            sys.exit(1)
_check_n8n_host()
GATEWAY_URL = f"{N8N_HOST}/webhook/pme-assistant-gateway"
TIMEOUT = 60

# ── Test Cases ──────────────────────────────────────────────────

GATEWAY_TESTS = [
    {
        "name": "Basic RAG query via API",
        "payload": {"query": "What is the capital of France?", "channel": "api"},
        "expect_field": "answer",
        "expect_contains": None,
    },
    {
        "name": "WhatsApp-style message",
        "payload": {
            "query": "Resume mes 5 derniers emails",
            "channel": "whatsapp",
            "user_id": "test-user-001",
        },
        "expect_field": "answer",
        "expect_contains": None,
    },
    {
        "name": "Telegram-style message",
        "payload": {
            "query": "Planifie un RDV demain a 14h avec Jean",
            "channel": "telegram",
            "user_id": "test-user-002",
        },
        "expect_field": "answer",
        "expect_contains": None,
    },
]

INTENT_TESTS = [
    {
        "name": "Query intent detection",
        "payload": {"query": "Trouve le rapport budget du mois dernier", "channel": "api"},
        "expect_intent": "query",
    },
    {
        "name": "Action intent detection (calendar)",
        "payload": {"query": "Planifie une demo avec Jean mardi 15h", "channel": "api"},
        "expect_intent": "action",
    },
    {
        "name": "Report intent detection",
        "payload": {"query": "Resume hebdo des mails importants", "channel": "api"},
        "expect_intent": "report",
    },
    {
        "name": "Action intent (email send)",
        "payload": {"query": "Envoie un email de relance au client Dupont", "channel": "api"},
        "expect_intent": "action",
    },
]

ACTION_TESTS = [
    {
        "name": "Calendar action routed correctly",
        "payload": {
            "query": "Cree un evenement demain 10h reunion equipe",
            "channel": "api",
        },
        "expect_action": "calendar",
    },
    {
        "name": "Email send action routed correctly",
        "payload": {
            "query": "Envoie le devis a contact@client.fr",
            "channel": "api",
        },
        "expect_action": "email",
    },
    {
        "name": "File search action routed correctly",
        "payload": {
            "query": "Trouve le contrat signe dans Google Drive",
            "channel": "api",
        },
        "expect_action": "file",
    },
]

# ── Test Runner ─────────────────────────────────────────────────

def send_request(url, payload):
    """Send POST request to n8n webhook."""
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body), resp.status
    except error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return {"error": str(e), "body": body}, e.code
    except error.URLError as e:
        return {"error": str(e)}, 0
    except Exception as e:
        return {"error": str(e)}, 0


def run_test(test, url=GATEWAY_URL):
    """Run a single test case."""
    start = time.time()
    result, status = send_request(url, test["payload"])
    elapsed = round(time.time() - start, 2)

    passed = status == 200

    # Check expected field exists
    if passed and "expect_field" in test:
        passed = test["expect_field"] in result

    # Check expected content
    if passed and test.get("expect_contains"):
        field_val = str(result.get(test.get("expect_field", "answer"), ""))
        passed = test["expect_contains"].lower() in field_val.lower()

    # Check expected intent
    if passed and "expect_intent" in test:
        intent = result.get("intent", result.get("classified_intent", ""))
        if intent:
            passed = test["expect_intent"].lower() in intent.lower()

    # Check expected action
    if passed and "expect_action" in test:
        action = result.get("action_type", result.get("action", ""))
        if action:
            passed = test["expect_action"].lower() in action.lower()

    return {
        "name": test["name"],
        "passed": passed,
        "status": status,
        "elapsed": elapsed,
        "response_preview": str(result)[:200],
    }


def run_suite(name, tests, url=GATEWAY_URL):
    """Run a test suite."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    results = []
    for test in tests:
        r = run_test(test, url)
        results.append(r)
        icon = "PASS" if r["passed"] else "FAIL"
        print(f"  [{icon}] {r['name']} ({r['elapsed']}s, HTTP {r['status']})")
        if not r["passed"]:
            print(f"         Response: {r['response_preview']}")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n  Result: {passed}/{total}")
    return results


def main():
    only = None
    if "--only" in sys.argv:
        idx = sys.argv.index("--only")
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1].lower()

    all_results = []
    ts = datetime.now().isoformat()

    # Check gateway is reachable
    print(f"\nPME Connectors Test Suite — {ts}")
    print(f"Gateway: {GATEWAY_URL}")

    if only in (None, "gateway"):
        all_results.extend(run_suite("Gateway Connectivity", GATEWAY_TESTS))

    if only in (None, "intent"):
        all_results.extend(run_suite("Intent Classification", INTENT_TESTS))

    if only in (None, "actions"):
        all_results.extend(run_suite("Action Routing", ACTION_TESTS))

    # Summary
    total_pass = sum(1 for r in all_results if r["passed"])
    total = len(all_results)
    print(f"\n{'='*60}")
    print(f"  TOTAL: {total_pass}/{total} passed")
    print(f"{'='*60}")

    # Save results
    output = {
        "timestamp": ts,
        "gateway_url": GATEWAY_URL,
        "total": total,
        "passed": total_pass,
        "accuracy": round(total_pass / total * 100, 1) if total else 0,
        "results": all_results,
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "logs",
        "pme-connectors-test.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")

    return 0 if total_pass == total else 1


if __name__ == "__main__":
    sys.exit(main())
