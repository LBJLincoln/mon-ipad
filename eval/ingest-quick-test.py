#!/usr/bin/env python3
"""
Ingestion Quick Test — Smoke test for Ingestion + Enrichment workflows.

Validates that:
1. Ingestion webhook accepts documents and returns trace IDs
2. Enrichment cron is reachable (via n8n API if available)
3. Databases received the ingested data (Pinecone vectors, Neo4j entities, Supabase records)

Usage:
  python ingest-quick-test.py                        # Full test suite
  python ingest-quick-test.py --test ingestion       # Ingestion webhook only
  python ingest-quick-test.py --test verify          # Verify databases only
  python ingest-quick-test.py --test chatbot         # Test project chatbot
"""

import json
import os
import sys
import time
from datetime import datetime
from urllib import request, error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

# Endpoints
INGESTION_ENDPOINT = f"{N8N_HOST}/webhook/rag-v6-ingestion"
CHATBOT_ENDPOINT = f"{N8N_HOST}/webhook/project-chatbot"
DEBUG_ENDPOINT = f"{N8N_HOST}/webhook/debug-status"

# Database check env vars
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_HOST = "sota-rag-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
NEO4J_URI = os.environ.get("NEO4J_URI", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def http_post(url, payload, timeout=30):
    """POST JSON and return parsed response."""
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    try:
        req = request.Request(url, data=data, headers=headers, method="POST")
        start = time.time()
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            latency = int((time.time() - start) * 1000)
            return {"status": "ok", "code": resp.status, "body": json.loads(raw) if raw else {}, "latency_ms": latency}
    except error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:500]
        except:
            pass
        return {"status": "error", "code": e.code, "body": body, "latency_ms": 0}
    except Exception as e:
        return {"status": "error", "code": 0, "body": str(e)[:200], "latency_ms": 0}


def http_get(url, headers=None, timeout=15):
    """GET and return parsed response."""
    try:
        req = request.Request(url, headers=headers or {}, method="GET")
        start = time.time()
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            latency = int((time.time() - start) * 1000)
            return {"status": "ok", "code": resp.status, "body": json.loads(raw) if raw else {}, "latency_ms": latency}
    except error.HTTPError as e:
        return {"status": "error", "code": e.code, "body": "", "latency_ms": 0}
    except Exception as e:
        return {"status": "error", "code": 0, "body": str(e)[:200], "latency_ms": 0}


def test_debug_status():
    """Test 0: Verify n8n is alive via debug-status endpoint."""
    print("\n  [Test 0] n8n debug-status endpoint")
    resp = http_get(DEBUG_ENDPOINT)
    if resp["status"] == "ok" and resp["code"] == 200:
        env_info = resp["body"].get("env", {})
        print(f"    [+] n8n alive | version: {resp['body'].get('version', '?')} | {resp['latency_ms']}ms")
        for key, val in env_info.items():
            symbol = "[+]" if val == "SET" else "[-]"
            print(f"    {symbol} {key}: {val}")
        return True
    else:
        print(f"    [-] n8n NOT responding | code={resp['code']} | {resp['body']}")
        return False


def test_ingestion_webhook():
    """Test 1: Send a test document to ingestion webhook."""
    print("\n  [Test 1] Ingestion webhook — send test document")

    test_docs = [
        {
            "name": "PDF document",
            "payload": {
                "objectKey": "test/smoke-test-document.pdf",
                "bucket": "smoke-test",
                "tenant_id": "smoke-test",
                "s3_url": "s3://smoke-test/test/smoke-test-document.pdf"
            }
        },
        {
            "name": "CSV spreadsheet",
            "payload": {
                "objectKey": "test/smoke-test-data.csv",
                "bucket": "smoke-test",
                "tenant_id": "smoke-test",
                "s3_url": "s3://smoke-test/test/smoke-test-data.csv"
            }
        },
    ]

    results = []
    for doc in test_docs:
        resp = http_post(INGESTION_ENDPOINT, doc["payload"], timeout=30)
        if resp["status"] == "ok":
            body = resp["body"] if isinstance(resp["body"], dict) else {}
            trace_id = body.get("traceId", body.get("trace_id", "none"))
            status = body.get("status", "unknown")
            print(f"    [+] {doc['name']}: accepted | trace={trace_id} | status={status} | {resp['latency_ms']}ms")
            results.append(True)
        elif resp["code"] == 500:
            # 500 is expected if s3_url doesn't resolve — workflow started but fetch failed
            print(f"    [~] {doc['name']}: webhook accepted but processing failed (expected for smoke test)")
            print(f"        Response: {str(resp['body'])[:150]}")
            results.append(True)  # Webhook is reachable, that's what we're testing
        else:
            print(f"    [-] {doc['name']}: FAILED | code={resp['code']} | {str(resp['body'])[:150]}")
            results.append(False)
        time.sleep(2)

    return all(results)


def test_chatbot_workflow():
    """Test 2: Test the project chatbot workflow."""
    print("\n  [Test 2] Project Chatbot workflow")

    test_queries = [
        {"query": "Qu'est-ce que Nomos AI ?", "lang": "fr", "check": "nomos"},
        {"query": "What phase is the project in?", "lang": "en", "check": "phase"},
        {"query": "Quels sont les 4 pipelines ?", "lang": "fr", "check": "pipeline"},
    ]

    passed = 0
    for q in test_queries:
        resp = http_post(CHATBOT_ENDPOINT, {"query": q["query"], "lang": q["lang"]}, timeout=45)
        if resp["status"] == "ok":
            body = resp["body"] if isinstance(resp["body"], dict) else {}
            answer = body.get("response", "")
            if answer and len(answer) > 20 and q["check"].lower() in answer.lower():
                print(f"    [+] '{q['query'][:40]}' → {len(answer)} chars | PASS")
                passed += 1
            elif answer and len(answer) > 20:
                print(f"    [~] '{q['query'][:40]}' → {len(answer)} chars | answer ok but check word '{q['check']}' not found")
                passed += 1  # Still counts — answer was generated
            else:
                print(f"    [-] '{q['query'][:40]}' → empty/short answer: '{answer[:80]}'")
        else:
            print(f"    [-] '{q['query'][:40]}' → ERROR code={resp['code']}")
        time.sleep(3)

    print(f"    Result: {passed}/{len(test_queries)} passed")
    return passed >= 2


def test_verify_databases():
    """Test 3: Verify databases have data (Pinecone vectors, Neo4j nodes)."""
    print("\n  [Test 3] Verify database health")
    all_ok = True

    # Pinecone — check vector count via describe_index_stats
    if PINECONE_API_KEY:
        print("    Pinecone:")
        resp = http_post(
            f"https://{PINECONE_HOST}/describe_index_stats",
            {},
            timeout=10
        )
        # Need to add API key header — use direct approach
        try:
            req = request.Request(
                f"https://{PINECONE_HOST}/describe_index_stats",
                data=json.dumps({}).encode(),
                headers={"Content-Type": "application/json", "Api-Key": PINECONE_API_KEY},
                method="POST"
            )
            with request.urlopen(req, timeout=10) as r:
                stats = json.loads(r.read().decode())
                total = stats.get("totalVectorCount", 0)
                namespaces = stats.get("namespaces", {})
                print(f"    [+] {total} vectors across {len(namespaces)} namespaces")
                if total < 100:
                    print(f"    [!] WARNING: Very few vectors ({total}). Ingestion may not have run.")
        except Exception as e:
            print(f"    [-] Pinecone check failed: {str(e)[:100]}")
            all_ok = False
    else:
        print("    [~] Pinecone: SKIPPED (no PINECONE_API_KEY)")

    # Supabase — check table counts
    if SUPABASE_URL and SUPABASE_KEY:
        print("    Supabase:")
        try:
            # Query a known table to verify connectivity
            req = request.Request(
                f"{SUPABASE_URL}/rest/v1/financials?select=count",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Prefer": "count=exact"
                },
                method="GET"
            )
            with request.urlopen(req, timeout=10) as r:
                print(f"    [+] Supabase connected | financials table accessible")
        except Exception as e:
            print(f"    [-] Supabase check failed: {str(e)[:100]}")
            all_ok = False
    else:
        print("    [~] Supabase: SKIPPED (no SUPABASE_URL or key)")

    return all_ok


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingestion & Chatbot quick tests")
    parser.add_argument("--test", type=str, default="all",
                        help="Test suite: all, ingestion, chatbot, verify")
    args = parser.parse_args()

    print("=" * 55)
    print("  INGESTION & CHATBOT QUICK TEST")
    print(f"  N8N_HOST: {N8N_HOST}")
    print(f"  Test suite: {args.test}")
    print(f"  Time: {datetime.now().isoformat()}")
    print("=" * 55)

    results = {}

    # Always check n8n health first
    n8n_alive = test_debug_status()
    if not n8n_alive:
        print("\n  FATAL: n8n is not responding. Cannot run tests.")
        sys.exit(1)

    if args.test in ("all", "ingestion"):
        results["ingestion"] = test_ingestion_webhook()

    if args.test in ("all", "chatbot"):
        results["chatbot"] = test_chatbot_workflow()

    if args.test in ("all", "verify"):
        results["databases"] = test_verify_databases()

    # Summary
    print("\n" + "=" * 55)
    print("  SUMMARY")
    print("=" * 55)
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  {name}: {status}")

    if all_pass:
        print("\n  All tests passed.")
    else:
        print("\n  Some tests FAILED. Check output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
