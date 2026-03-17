#!/usr/bin/env python3
"""Nomos AI — Comprehensive Infrastructure Test Suite

Functional tests for every component of the Nomos AI system.
Not health checks — actual end-to-end functional verification.

Tests:
  A. HF Spaces connectivity (S1-S5, S6, S7, S9, Embeddings, Reranker)
  B. Pipeline smoke tests (Standard, Graph, Quant, Orchestrator)
  C. Database tests (Pinecone E5, Supabase, Neo4j)
  D. Embeddings functional test (1024-dim vector check)
  E. LiteLLM inference test (model routing + response)
  F. Docling document conversion test (PDF -> text)

Usage:
    python3 ops/infra-test.py                       # Run all tests
    python3 ops/infra-test.py --json                # JSON output
    python3 ops/infra-test.py --component spaces    # Only HF Spaces
    python3 ops/infra-test.py --component pipelines # Only pipeline smoke
    python3 ops/infra-test.py --component databases # Only DB tests
    python3 ops/infra-test.py --component embeddings
    python3 ops/infra-test.py --component litellm
    python3 ops/infra-test.py --component docling
"""

import argparse
import base64
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# ─── Force IPv4 (GCP VM has broken IPv6) ─────────────────────────────
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_only

# ─── SSL permissive (self-signed certs on some HF Spaces) ────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ─── Paths ────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─── Constants ────────────────────────────────────────────────────────
SPACE_TIMEOUT = 15
PIPELINE_TIMEOUT = 90
DB_TIMEOUT = 15
EMBED_TIMEOUT = 30
LLM_TIMEOUT = 30
DOCLING_TIMEOUT = 60

S1_BASE = "https://lbjlincoln-nomos-rag-engine.hf.space"

SPACES = {
    "S1":      "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S2":      "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "S3":      "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S4":      "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "S5":      "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S6":      "https://lbjlincoln-nomos-docling-api.hf.space",
    "S7":      "https://lbjlincoln-nomos-rag-engine-7.hf.space",
    "S9":      "https://lbjlincoln-nomos-rag-engine-9.hf.space",
    "Embed":   "https://lbjlincoln-nomos-embeddings-api.hf.space",
    "Rerank":  "https://lbjlincoln-nomos-reranker-api.hf.space",
}

PIPELINE_TESTS = {
    "Standard": {
        "path": "/webhook/rag-multi-index-v3",
        "payload": {
            "question": "Qu'est-ce que le ratio de solvabilite?",
            "sector": "finance",
        },
    },
    "Graph": {
        "path": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "payload": {
            "question": "Quels sont les principes du droit des contrats?",
            "sector": "juridique",
        },
    },
    "Quant": {
        "path": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "payload": {
            "question": "Quel est le chiffre d'affaires de Total en 2023?",
            "sector": "finance",
        },
    },
    "Orchestrator": {
        "path": "/webhook/orchestrator-v2",
        "payload": {
            "question": "Comment calculer le ratio de solvabilite?",
            "sector": "finance",
        },
    },
}

PINECONE_HOST = "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
EMBED_URL = "https://lbjlincoln-nomos-embeddings-api.hf.space/embed"
LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "Bearer sk-litellm-nomos-2026"
DOCLING_URL = "https://lbjlincoln-nomos-docling-api.hf.space/convert-url"
DOCLING_TEST_PDF = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"


# ─── Env loader ───────────────────────────────────────────────────────

def load_env():
    """Load .env.local into os.environ."""
    env_file = os.path.join(REPO_ROOT, ".env.local")
    if not os.path.exists(env_file):
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            eq = line.find("=")
            if eq > 0:
                key = line[:eq].strip()
                val = line[eq + 1:].strip().strip('"').strip("'")
                os.environ[key] = val


# ─── HTTP helpers (urllib only) ───────────────────────────────────────

def http_get(url, timeout=15, headers=None):
    """GET request. Returns (status_code, body_str, elapsed_seconds)."""
    hdrs = headers or {}
    req = urllib.request.Request(url, headers=hdrs)
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")[:4000]
        return resp.status, body, time.time() - start
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:1000]
        except Exception:
            pass
        return e.code, body, time.time() - start
    except Exception as e:
        return 0, str(e)[:300], time.time() - start


def http_post(url, payload, timeout=30, headers=None):
    """POST JSON. Returns (status_code, body_str, elapsed_seconds)."""
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    data = json.dumps(payload).encode("utf-8") if isinstance(payload, (dict, list)) else payload.encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")[:8000]
        return resp.status, body, time.time() - start
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass
        return e.code, body, time.time() - start
    except Exception as e:
        return 0, str(e)[:300], time.time() - start


# ─── Result class ─────────────────────────────────────────────────────

class TestResult:
    """Holds the outcome of a single test."""

    def __init__(self, component, test_name, status, latency, details=""):
        self.component = component      # e.g. "Spaces", "Pipelines"
        self.test_name = test_name      # e.g. "S1 connectivity"
        self.status = status            # "PASS", "FAIL", "SLOW", "TIMEOUT"
        self.latency = latency          # seconds (float)
        self.details = details          # human-readable note

    def passed(self):
        return self.status in ("PASS", "SLOW")

    def to_dict(self):
        return {
            "component": self.component,
            "test": self.test_name,
            "status": self.status,
            "latency_s": round(self.latency, 2),
            "details": self.details,
        }


# ═══════════════════════════════════════════════════════════════════════
# A. HF Spaces connectivity
# ═══════════════════════════════════════════════════════════════════════

def test_space(name, url):
    """Test that an HF Space responds with HTTP 200."""
    # Try /healthz first, then / as fallback
    for endpoint in ["/healthz", "/"]:
        status, body, elapsed = http_get(f"{url}{endpoint}", timeout=SPACE_TIMEOUT)
        if status == 200:
            return TestResult("Spaces", f"{name} connectivity", "PASS", elapsed,
                              f"HTTP 200 on {endpoint}")
    # All endpoints failed
    if elapsed >= SPACE_TIMEOUT - 1:
        return TestResult("Spaces", f"{name} connectivity", "TIMEOUT", elapsed,
                          f"No response within {SPACE_TIMEOUT}s")
    return TestResult("Spaces", f"{name} connectivity", "FAIL", elapsed,
                      f"HTTP {status}" + (f": {body[:80]}" if body else ""))


def run_spaces_tests():
    """Run connectivity tests for all HF Spaces in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(test_space, name, url): name for name, url in SPACES.items()}
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda r: r.test_name)


# ═══════════════════════════════════════════════════════════════════════
# B. Pipeline smoke tests
# ═══════════════════════════════════════════════════════════════════════

def _classify_latency(elapsed):
    if elapsed < 30:
        return "OK"
    elif elapsed < 60:
        return "SLOW"
    else:
        return "TIMEOUT"


def test_pipeline(name, config):
    """Send a real question to a pipeline webhook and verify the answer."""
    url = f"{S1_BASE}{config['path']}"
    # n8n webhooks accept various key names — try both common formats
    payload = config["payload"]
    status, body, elapsed = http_post(url, payload, timeout=PIPELINE_TIMEOUT)

    latency_class = _classify_latency(elapsed)

    # Parse the response
    if status == 0:
        if elapsed >= PIPELINE_TIMEOUT - 2:
            return TestResult("Pipelines", f"{name} smoke", "TIMEOUT", elapsed,
                              "Request timed out")
        return TestResult("Pipelines", f"{name} smoke", "FAIL", elapsed,
                          f"Connection error: {body[:100]}")

    if status not in (200, 201):
        return TestResult("Pipelines", f"{name} smoke", "FAIL", elapsed,
                          f"HTTP {status}: {body[:120]}")

    # Try to extract the answer from the response
    answer = ""
    try:
        data = json.loads(body)
        if isinstance(data, list):
            data = data[0] if data else {}
        # Pipelines return answer in various keys
        for key in ("response", "answer", "text", "output", "result", "message"):
            val = data.get(key, "")
            if val and isinstance(val, str) and len(val) > len(answer):
                answer = val
        # Some pipelines nest the answer
        if not answer and isinstance(data, dict):
            for v in data.values():
                if isinstance(v, str) and len(v) > len(answer):
                    answer = v
    except json.JSONDecodeError:
        # Non-JSON response — use raw body
        answer = body

    # Evaluate quality
    if not answer or len(answer) < 50:
        return TestResult("Pipelines", f"{name} smoke", "FAIL", elapsed,
                          f"Empty/short response ({len(answer)} chars): {answer[:80]}")

    if "error" in answer.lower()[:80] or "Error in workflow" in body:
        return TestResult("Pipelines", f"{name} smoke", "FAIL", elapsed,
                          f"Error in response: {answer[:120]}")

    # Passed — report latency classification
    result_status = "PASS" if latency_class == "OK" else latency_class
    return TestResult("Pipelines", f"{name} smoke", result_status, elapsed,
                      f"{latency_class} | {len(answer)} chars | {answer[:80]}...")


def run_pipeline_tests():
    """Run smoke tests for all 4 pipelines in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(test_pipeline, name, cfg): name
                   for name, cfg in PIPELINE_TESTS.items()}
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda r: r.test_name)


# ═══════════════════════════════════════════════════════════════════════
# C. Database tests
# ═══════════════════════════════════════════════════════════════════════

def test_pinecone():
    """Search Pinecone E5 index using the integrated inference API (records/search)."""
    api_key = os.environ.get("PINECONE_API_KEY", "")
    if not api_key:
        return TestResult("Databases", "Pinecone E5 search", "FAIL", 0,
                          "PINECONE_API_KEY not set in environment")

    # First get index stats to know it is reachable and has data
    stat_status, stat_body, stat_elapsed = http_get(
        f"{PINECONE_HOST}/describe_index_stats",
        timeout=DB_TIMEOUT,
        headers={"Api-Key": api_key},
    )

    if stat_status != 200:
        return TestResult("Databases", "Pinecone E5 search", "FAIL", stat_elapsed,
                          f"Stats endpoint HTTP {stat_status}: {stat_body[:100]}")

    total_vectors = 0
    try:
        stats = json.loads(stat_body)
        total_vectors = stats.get("totalRecordCount", stats.get("totalVectorCount", 0))
    except Exception:
        pass

    # Use the integrated inference search API (no need for pre-computed vectors)
    search_payload = {
        "query": {
            "top_k": 3,
            "inputs": {"text": "ratio de solvabilite bancaire"},
            "filter": {"sector": {"$eq": "finance"}},
        },
        "fields": ["text", "sector", "source"],
    }

    status, body, elapsed = http_post(
        f"{PINECONE_HOST}/records/namespaces/sectors/search",
        search_payload,
        timeout=DB_TIMEOUT,
        headers={"Api-Key": api_key},
    )

    if status != 200:
        return TestResult("Databases", "Pinecone E5 search", "FAIL", elapsed,
                          f"Search API HTTP {status}: {body[:120]}")

    hits = 0
    try:
        data = json.loads(body)
        hits = len(data.get("result", {}).get("hits", []))
    except Exception:
        pass

    if hits > 0:
        return TestResult("Databases", "Pinecone E5 search", "PASS", elapsed,
                          f"{hits} hits returned | {total_vectors:,} total vectors")
    else:
        return TestResult("Databases", "Pinecone E5 search", "FAIL", elapsed,
                          f"0 hits | {total_vectors:,} vectors in index")


def test_supabase():
    """Connect to Supabase via psycopg2 and verify sector_documents count."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return TestResult("Databases", "Supabase SQL", "FAIL", 0,
                          "DATABASE_URL not set in environment")
    start = time.time()
    try:
        import psycopg2
    except ImportError:
        return TestResult("Databases", "Supabase SQL", "FAIL", 0,
                          "psycopg2 not installed (pip install psycopg2-binary)")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=DB_TIMEOUT)
        cur = conn.cursor()
        cur.execute("SET search_path TO public")
        cur.execute("SELECT COUNT(*) FROM sector_documents")
        doc_count = cur.fetchone()[0]
        cur.execute("SELECT MAX(created_at) FROM sector_documents")
        latest = str(cur.fetchone()[0] or "N/A")
        conn.close()
        elapsed = time.time() - start

        if doc_count > 0:
            return TestResult("Databases", "Supabase SQL", "PASS", elapsed,
                              f"{doc_count:,} docs | latest: {latest[:19]}")
        else:
            return TestResult("Databases", "Supabase SQL", "FAIL", elapsed,
                              "sector_documents table is empty")
    except Exception as e:
        return TestResult("Databases", "Supabase SQL", "FAIL", time.time() - start,
                          f"Connection error: {str(e)[:150]}")


def test_neo4j():
    """Query Neo4j Aura for node count via HTTP API or bolt driver."""
    uri = os.environ.get("NEO4J_URI", "")
    user = os.environ.get("NEO4J_USERNAME", os.environ.get("NEO4J_USER", "neo4j"))
    pwd = os.environ.get("NEO4J_PASSWORD", "")

    if not uri:
        return TestResult("Databases", "Neo4j query", "FAIL", 0,
                          "NEO4J_URI not set in environment")
    if not pwd:
        return TestResult("Databases", "Neo4j query", "FAIL", 0,
                          "NEO4J_PASSWORD not set in environment")

    # Try the neo4j Python driver first (most reliable for Aura)
    driver_err = None
    start = time.time()
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS cnt LIMIT 1")
            record = result.single()
            nodes = record["cnt"] if record else 0
        driver.close()
        elapsed = time.time() - start
        if nodes and int(nodes) > 0:
            return TestResult("Databases", "Neo4j query", "PASS", elapsed,
                              f"{int(nodes):,} nodes (bolt driver)")
        else:
            return TestResult("Databases", "Neo4j query", "FAIL", elapsed,
                              "Query returned 0 nodes (bolt driver)")
    except ImportError:
        pass  # Fall through to HTTP API
    except Exception as e:
        driver_err = str(e)[:120]
        # Fall through to HTTP, but keep error for reporting

    # Fallback: HTTP Query API
    host = (uri.replace("neo4j+s://", "")
               .replace("bolt+s://", "")
               .replace("neo4j://", "")
               .replace("bolt://", "")
               .rstrip("/"))

    auth_str = base64.b64encode(f"{user}:{pwd}".encode()).decode()

    # Try multiple endpoint formats (Neo4j Aura version-dependent)
    endpoints_and_payloads = [
        (f"https://{host}/db/neo4j/query/v2",
         {"statement": "MATCH (n) RETURN count(n) AS cnt LIMIT 1"}),
        (f"https://{host}/db/neo4j/tx/commit",
         {"statements": [{"statement": "MATCH (n) RETURN count(n) AS cnt LIMIT 1"}]}),
        (f"https://{host}/db/data/transaction/commit",
         {"statements": [{"statement": "MATCH (n) RETURN count(n) AS cnt LIMIT 1"}]}),
    ]

    last_status = 0
    last_body = ""
    for endpoint, payload in endpoints_and_payloads:
        status, body, elapsed = http_post(
            endpoint, payload, timeout=DB_TIMEOUT,
            headers={"Authorization": f"Basic {auth_str}"},
        )
        last_status = status
        last_body = body

        if status == 200 and body:
            try:
                data = json.loads(body)
                nodes = 0
                # v2 format: {"data": {"values": [[count]]}}
                if "data" in data:
                    values = data["data"].get("values", [])
                    if values:
                        nodes = values[0][0] if isinstance(values[0], list) else values[0]
                # tx/commit format: {"results": [{"data": [{"row": [count]}]}]}
                elif "results" in data:
                    results_list = data["results"]
                    if results_list:
                        rows = results_list[0].get("data", [])
                        if rows:
                            nodes = rows[0]["row"][0]

                if nodes and int(nodes) > 0:
                    return TestResult("Databases", "Neo4j query", "PASS", elapsed,
                                      f"{int(nodes):,} nodes (HTTP API)")
            except Exception:
                continue  # Try next endpoint

    # All HTTP endpoints failed — report the driver error if we had one
    err_detail = f"HTTP {last_status}: {last_body[:100]}"
    if driver_err:
        err_detail = f"Driver: {driver_err} | {err_detail}"
    return TestResult("Databases", "Neo4j query", "FAIL", time.time() - start,
                      err_detail)


def run_database_tests():
    """Run all database tests in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(test_pinecone),
            pool.submit(test_supabase),
            pool.submit(test_neo4j),
        ]
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda r: r.test_name)


# ═══════════════════════════════════════════════════════════════════════
# D. Embeddings test
# ═══════════════════════════════════════════════════════════════════════

def test_embeddings():
    """POST a test text to the self-hosted embeddings API and verify 1024-dim output."""
    payload = {"inputs": ["test embedding for infrastructure validation"]}

    # Embeddings return large bodies (1024 floats), need custom read limit
    hdrs = {"Content-Type": "application/json"}
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(EMBED_URL, data=data_bytes, headers=hdrs, method="POST")
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx, timeout=EMBED_TIMEOUT)
        body = resp.read().decode("utf-8", errors="replace")
        status = resp.status
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass
        status = e.code
    except Exception as e:
        return TestResult("Embeddings", "Jina embed", "FAIL", time.time() - start,
                          f"Connection error: {str(e)[:120]}")
    elapsed = time.time() - start

    if status != 200:
        return TestResult("Embeddings", "Jina embed", "FAIL", elapsed,
                          f"HTTP {status}: {body[:120]}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return TestResult("Embeddings", "Jina embed", "FAIL", elapsed,
                          f"Invalid JSON response ({len(body)} bytes): {body[:80]}")

    # Response may be: [[...]] (raw array), {"embeddings": [[...]]}, or {"data": [...]}
    embeddings = None
    if isinstance(data, list):
        # Raw array of arrays: [[0.01, 0.02, ...]]
        embeddings = data
    elif isinstance(data, dict):
        if "embeddings" in data:
            embeddings = data["embeddings"]
        elif "data" in data and isinstance(data["data"], list):
            if data["data"] and isinstance(data["data"][0], dict) and "embedding" in data["data"][0]:
                embeddings = [data["data"][0]["embedding"]]
            elif data["data"] and isinstance(data["data"][0], list):
                embeddings = data["data"]

    if not embeddings or not isinstance(embeddings, list) or len(embeddings) == 0:
        return TestResult("Embeddings", "Jina embed", "FAIL", elapsed,
                          f"No embeddings in response: {str(data)[:120]}")

    first_vec = embeddings[0]
    if not isinstance(first_vec, list):
        return TestResult("Embeddings", "Jina embed", "FAIL", elapsed,
                          f"Unexpected vector type: {type(first_vec).__name__}")

    dim = len(first_vec)
    if dim == 1024:
        return TestResult("Embeddings", "Jina embed", "PASS", elapsed,
                          f"1024-dim vector returned ({len(embeddings)} embedding(s))")
    else:
        return TestResult("Embeddings", "Jina embed", "FAIL", elapsed,
                          f"Wrong dimension: expected 1024, got {dim}")


def run_embeddings_tests():
    return [test_embeddings()]


# ═══════════════════════════════════════════════════════════════════════
# E. LiteLLM test
# ═══════════════════════════════════════════════════════════════════════

def test_litellm():
    """Send a chat completion request to LiteLLM proxy and verify response."""
    payload = {
        "model": "smart",
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 10,
    }

    status, body, elapsed = http_post(
        LITELLM_URL, payload, timeout=LLM_TIMEOUT,
        headers={"Authorization": LITELLM_KEY},
    )

    if status == 0:
        return TestResult("LiteLLM", "Chat completion", "FAIL", elapsed,
                          f"Connection error: {body[:120]}")

    if status == 401:
        return TestResult("LiteLLM", "Chat completion", "FAIL", elapsed,
                          "401 Unauthorized — check LITELLM_KEY")

    if status not in (200, 201):
        return TestResult("LiteLLM", "Chat completion", "FAIL", elapsed,
                          f"HTTP {status}: {body[:120]}")

    try:
        data = json.loads(body)
        content = data["choices"][0]["message"]["content"]
        model_used = data.get("model", "unknown")
        return TestResult("LiteLLM", "Chat completion", "PASS", elapsed,
                          f"Model: {model_used} | Response: {content[:60]}")
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        return TestResult("LiteLLM", "Chat completion", "FAIL", elapsed,
                          f"Malformed response: {str(e)[:60]} | body: {body[:80]}")


def run_litellm_tests():
    return [test_litellm()]


# ═══════════════════════════════════════════════════════════════════════
# F. Docling test
# ═══════════════════════════════════════════════════════════════════════

def test_docling():
    """Send a PDF URL to Docling for conversion and verify text output."""
    payload = {"url": DOCLING_TEST_PDF}
    status, body, elapsed = http_post(DOCLING_URL, payload, timeout=DOCLING_TIMEOUT)

    if status == 0:
        if elapsed >= DOCLING_TIMEOUT - 2:
            return TestResult("Docling", "PDF conversion", "TIMEOUT", elapsed,
                              "Request timed out")
        return TestResult("Docling", "PDF conversion", "FAIL", elapsed,
                          f"Connection error: {body[:120]}")

    if status not in (200, 201):
        return TestResult("Docling", "PDF conversion", "FAIL", elapsed,
                          f"HTTP {status}: {body[:120]}")

    # Check we got some text content back
    try:
        data = json.loads(body)
        # Response might be {"text": "...", ...} or {"content": "...", ...}
        # or {"markdown": "...", ...} or {"full_text": "...", ...}
        text = ""
        for key in ("text", "content", "markdown", "full_text", "result", "output"):
            val = data.get(key, "")
            if isinstance(val, str) and len(val) > len(text):
                text = val
        # Might also be a list of pages
        if not text and "pages" in data:
            pages = data["pages"]
            if isinstance(pages, list):
                text = " ".join(str(p.get("text", "")) for p in pages)

        if not text:
            # Try treating whole body as the text content
            text = body

    except json.JSONDecodeError:
        # Non-JSON — raw text response
        text = body

    if text and len(text) > 10:
        return TestResult("Docling", "PDF conversion", "PASS", elapsed,
                          f"{len(text)} chars extracted | {text[:80]}...")
    else:
        return TestResult("Docling", "PDF conversion", "FAIL", elapsed,
                          f"Empty/short output ({len(text)} chars)")


def run_docling_tests():
    return [test_docling()]


# ═══════════════════════════════════════════════════════════════════════
# Output formatting
# ═══════════════════════════════════════════════════════════════════════

# ANSI color codes
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"

STATUS_COLORS = {
    "PASS":    _GREEN,
    "FAIL":    _RED,
    "SLOW":    _YELLOW,
    "TIMEOUT": _RED,
}


def _color(status):
    return STATUS_COLORS.get(status, "") + status + _RESET


def print_header():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print()
    print(f"{_BOLD}{'=' * 78}{_RESET}")
    print(f"{_BOLD}  NOMOS AI — Infrastructure Test Suite{_RESET}")
    print(f"  {now}")
    print(f"{_BOLD}{'=' * 78}{_RESET}")
    print()


def print_results_table(results):
    """Print a formatted table of test results grouped by component."""
    # Column widths
    comp_w = max(len(r.component) for r in results) + 1
    test_w = max(len(r.test_name) for r in results) + 1
    stat_w = 9  # "TIMEOUT" + padding

    current_component = None
    for r in results:
        if r.component != current_component:
            current_component = r.component
            print(f"\n{_CYAN}{_BOLD}  [{current_component}]{_RESET}")
            print(f"  {'Test':<{test_w}} {'Status':<{stat_w}} {'Latency':>8}  Details")
            print(f"  {'-' * (test_w + stat_w + 10 + 40)}")

        latency_str = f"{r.latency:.1f}s" if r.latency > 0 else "  --"
        status_colored = _color(r.status)
        # Truncate details for display
        details = r.details[:65] if len(r.details) > 65 else r.details
        print(f"  {r.test_name:<{test_w}} {status_colored:<{stat_w + len(status_colored) - len(r.status)}} {latency_str:>8}  {details}")


def print_summary(results):
    """Print final pass/fail summary."""
    total = len(results)
    passed = sum(1 for r in results if r.passed())
    failed = total - passed

    print()
    print(f"{_BOLD}{'─' * 78}{_RESET}")
    if failed == 0:
        print(f"  {_GREEN}{_BOLD}ALL {total} TESTS PASSED{_RESET}")
    else:
        print(f"  {_RED}{_BOLD}{failed} FAILED{_RESET} / {total} total "
              f"({_GREEN}{passed} passed{_RESET})")
        # List failures
        for r in results:
            if not r.passed():
                print(f"    {_RED}x{_RESET} {r.component} > {r.test_name}: {r.details[:70]}")
    print(f"{_BOLD}{'─' * 78}{_RESET}")
    print()


def output_json(results):
    """Output results as JSON to stdout."""
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed()),
        "failed": sum(1 for r in results if not r.passed()),
        "tests": [r.to_dict() for r in results],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

COMPONENT_MAP = {
    "spaces":     run_spaces_tests,
    "pipelines":  run_pipeline_tests,
    "databases":  run_database_tests,
    "embeddings": run_embeddings_tests,
    "litellm":    run_litellm_tests,
    "docling":    run_docling_tests,
}


def main():
    parser = argparse.ArgumentParser(
        description="Nomos AI — Comprehensive Infrastructure Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--component", "-c", type=str, default=None,
                        choices=list(COMPONENT_MAP.keys()),
                        help="Test only one component")
    args = parser.parse_args()

    load_env()

    # Decide which test suites to run
    if args.component:
        suites = {args.component: COMPONENT_MAP[args.component]}
    else:
        suites = COMPONENT_MAP

    if not args.json:
        print_header()

    # Run all selected suites in parallel (each suite runs its own tests internally)
    all_results = []
    with ThreadPoolExecutor(max_workers=len(suites)) as pool:
        future_to_name = {pool.submit(fn): name for name, fn in suites.items()}
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results = future.result()
                all_results.extend(results)
            except Exception as e:
                all_results.append(
                    TestResult(name.capitalize(), f"{name} suite",
                               "FAIL", 0, f"Suite crashed: {str(e)[:100]}")
                )

    # Sort by component order (preserve the natural group ordering)
    component_order = list(COMPONENT_MAP.keys())
    all_results.sort(key=lambda r: (
        component_order.index(r.component.lower()) if r.component.lower() in component_order
        else len(component_order),
        r.test_name,
    ))

    # Output
    if args.json:
        output_json(all_results)
    else:
        print_results_table(all_results)
        print_summary(all_results)

    # Exit code
    any_failed = any(not r.passed() for r in all_results)
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
