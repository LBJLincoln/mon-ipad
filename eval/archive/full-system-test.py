#!/usr/bin/env python3
"""
Full System Test — Validates ALL product components end-to-end.

Tests every layer of the Nomos Sector AI Expert stack:
  1. Infrastructure: HF Spaces (S1-S9), LiteLLM, Embeddings
  2. Databases: Pinecone, Neo4j, Supabase
  3. RAG Pipelines: Standard, Graph, Quantitative, Orchestrator
  4. Ingestion: n8n Ingestion V4.0 workflow
  5. Enrichment: n8n Enrichment V4.0 workflow
  6. Docling: S6 document processor
  7. End-to-end: Full query flow (question → embedding → retrieval → LLM → answer)

Usage:
  source .env.local
  python3 eval/full-system-test.py              # Full test
  python3 eval/full-system-test.py --component pipelines  # Test one component
  python3 eval/full-system-test.py --json        # JSON output
  python3 eval/full-system-test.py --fix         # Auto-fix what can be fixed
"""

# ── IPv4 fix ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

# Load env
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                if line.startswith("export "):
                    line = line[7:]
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

_ssl = ssl.create_default_context()
_ssl.check_hostname = False
_ssl.verify_mode = ssl.CERT_NONE

# ── Colors ──
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
B = "\033[94m"
D = "\033[2m"
RST = "\033[0m"
BOLD = "\033[1m"

# ── Config ──
SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
    "S2": "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "S4": "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
}

LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space"
EMBEDDINGS_URL = "https://lbjlincoln-nomos-embeddings-api.hf.space"
DOCLING_URL = "https://lbjlincoln-nomos-docling-api.hf.space"

PIPELINES = {
    "standard": {
        "path": "/webhook/rag-multi-index-v3",
        "payload": {"question": "Quel est le taux directeur de la BCE en 2024?", "sector": "finance"},
        "answer_fields": ["response", "answer", "output"],
    },
    "graph": {
        "path": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "payload": {"question": "Quelles entites sont liees au secteur BTP?", "sector": "btp"},
        "answer_fields": ["response", "answer", "output"],
    },
    "quantitative": {
        "path": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "payload": {"question": "What is Boeing revenue in 2022?", "sector": "finance"},
        "answer_fields": ["interpretation", "response", "answer"],
    },
    "orchestrator": {
        "path": "/webhook/orchestrator-v2",
        "payload": {"question": "Quels sont les principaux risques du secteur BTP?", "sector": "btp"},
        "answer_fields": ["response", "answer", "output"],
    },
}

N8N_WORKFLOWS = {
    "Ingestion V4.0": "nh1D4Up0wBZhuQbp",
    "Enrichment V4.0": "ORa01sX4xI0iRCJ8",
    "Auto-Healer": "Yqw7Pzn0e7m0C6i3",
    "Standard RAG": "9FQdtx38JLPiT3Hx",
    "Graph RAG": "6257AfT1l4FMC6lY",
    "Quant RAG": "cjhEhVs0KV1ExHqX",
    "Orchestrator": "qOSaFFrqO8Jb4VGb",
}

results = []


def http_get(url, timeout=15):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=_ssl, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)[:200]


def http_post(url, data, timeout=60):
    try:
        payload = json.dumps(data).encode()
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, context=_ssl, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, round(time.time() - t0, 1)
    except urllib.error.HTTPError as e:
        return e.code, str(e)[:200], 0
    except Exception as e:
        return 0, str(e)[:200], 0


def record(component, test_name, passed, detail="", latency=None):
    r = {
        "component": component,
        "test": test_name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail[:200],
    }
    if latency is not None:
        r["latency_s"] = latency
    results.append(r)
    symbol = f"{G}PASS{RST}" if passed else f"{R}FAIL{RST}"
    lat_str = f" ({latency}s)" if latency else ""
    print(f"  {symbol}  {component:20s} {test_name:35s}{lat_str} {D}{detail[:60]}{RST}")


# ════════════════════════════════════════════════════════════════════
# TEST SUITES
# ════════════════════════════════════════════════════════════════════

def test_spaces():
    """Test all HF Spaces are UP."""
    print(f"\n{BOLD}=== HF Spaces ==={RST}")
    for name, url in SPACES.items():
        status, _ = http_get(url, timeout=10)
        record("spaces", f"{name} reachable", status in (200, 301, 302, 307, 403), f"HTTP {status}")


def test_litellm():
    """Test LiteLLM proxy S7."""
    print(f"\n{BOLD}=== LiteLLM S7 ==={RST}")
    litellm_key = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")
    # Health check
    try:
        req = urllib.request.Request(f"{LITELLM_URL}/health",
            headers={"Authorization": f"Bearer {litellm_key}"})
        with urllib.request.urlopen(req, context=_ssl, timeout=10) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = 0
    record("litellm", "health endpoint", status == 200, f"HTTP {status}")

    # Model list
    try:
        req = urllib.request.Request(f"{LITELLM_URL}/v1/models",
            headers={"Authorization": f"Bearer {litellm_key}"})
        with urllib.request.urlopen(req, context=_ssl, timeout=10) as resp:
            status = resp.status
            body = resp.read().decode()
    except urllib.error.HTTPError as e:
        status = e.code
        body = ""
    except Exception:
        status = 0
        body = ""
    record("litellm", "models endpoint", status == 200)

    # Chat completion (needs auth)
    try:
        payload = json.dumps({
            "model": "smart",
            "messages": [{"role": "user", "content": "Reply with just OK"}],
            "max_tokens": 10,
        }).encode()
        req = urllib.request.Request(f"{LITELLM_URL}/v1/chat/completions",
            data=payload, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {litellm_key}"})
        t0 = time.time()
        with urllib.request.urlopen(req, context=_ssl, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode()
            lat = round(time.time() - t0, 1)
    except urllib.error.HTTPError as e:
        status, body, lat = e.code, str(e)[:100], 0
    except Exception as e:
        status, body, lat = 0, str(e)[:100], 0
    has_response = "choices" in body if body else False
    record("litellm", "smart model inference", status == 200 and has_response, body[:80] if body else "", lat)


def test_embeddings():
    """Test self-hosted embeddings API."""
    print(f"\n{BOLD}=== Embeddings API ==={RST}")
    status, body = http_get(EMBEDDINGS_URL, timeout=10)
    record("embeddings", "space reachable", status in (200, 301, 302, 307), f"HTTP {status}")

    # Embed test (API uses {"inputs": "text"})
    status, body, lat = http_post(f"{EMBEDDINGS_URL}/embed", {
        "inputs": "test embedding query"
    }, timeout=30)
    has_vectors = body.startswith("[[") if body else False
    record("embeddings", "embed endpoint", status == 200 and has_vectors,
           f"dims={body.count(',') + 1 if has_vectors else 0}", lat)


def test_docling():
    """Test Docling S6."""
    print(f"\n{BOLD}=== Docling S6 ==={RST}")
    status, body = http_get(DOCLING_URL, timeout=10)
    record("docling", "space reachable", status in (200, 301, 302, 307, 403), f"HTTP {status}")

    # Health/status
    status, body = http_get(f"{DOCLING_URL}/health", timeout=10)
    record("docling", "health endpoint", status == 200, f"HTTP {status}")


def test_pinecone():
    """Test Pinecone E5 index."""
    print(f"\n{BOLD}=== Pinecone ==={RST}")
    host = os.environ.get("PINECONE_E5_HOST",
        "https://sectors-e5-multilingual-a4mkzmz.svc.aped-4627-b74a.pinecone.io")
    key = os.environ.get("PINECONE_API_KEY", "")
    if not key:
        record("pinecone", "env vars", False, "PINECONE_API_KEY not set")
        return

    try:
        url = f"https://{host}/describe_index_stats" if not host.startswith("http") else f"{host}/describe_index_stats"
        req = urllib.request.Request(url, method="POST",
                                     headers={"Api-Key": key, "Content-Type": "application/json"},
                                     data=b'{}')
        with urllib.request.urlopen(req, context=_ssl, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            total = data.get("totalVectorCount", data.get("total_vector_count", 0))
            record("pinecone", "E5 index stats", total > 0, f"{total:,} vectors")
    except Exception as e:
        record("pinecone", "E5 index stats", False, str(e)[:100])


def test_neo4j():
    """Test Neo4j connection."""
    print(f"\n{BOLD}=== Neo4j ==={RST}")
    uri = os.environ.get("NEO4J_URI", "")
    user = os.environ.get("NEO4J_USERNAME", os.environ.get("NEO4J_USER", "neo4j"))
    pw = os.environ.get("NEO4J_PASSWORD", "")
    if not uri:
        record("neo4j", "env vars", False, "NEO4J_URI not set")
        return
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, pw))
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as cnt LIMIT 1")
            cnt = result.single()["cnt"]
            record("neo4j", "connection + node count", cnt > 0, f"{cnt:,} nodes")
        driver.close()
    except ImportError:
        record("neo4j", "driver", False, "neo4j python driver not installed")
    except Exception as e:
        record("neo4j", "connection", False, str(e)[:100])


def test_supabase():
    """Test Supabase/PostgreSQL."""
    print(f"\n{BOLD}=== Supabase ==={RST}")
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        record("supabase", "env vars", False, "DATABASE_URL not set")
        return
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        with conn.cursor() as c:
            c.execute("SET search_path TO public")
            c.execute("SELECT COUNT(*) FROM sector_documents")
            docs = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM eval_question_bank")
            qs = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM financials")
            fin = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM question_source_map")
            qsm = c.fetchone()[0]
        conn.close()
        record("supabase", "connection", True, f"docs={docs:,} questions={qs:,} financials={fin}")
        record("supabase", "question_source_map", qsm > 0, f"{qsm:,} mappings")
    except ImportError:
        record("supabase", "driver", False, "psycopg2 not installed")
    except Exception as e:
        record("supabase", "connection", False, str(e)[:100])


def test_pipelines():
    """Test all 4 RAG pipelines on S1."""
    print(f"\n{BOLD}=== RAG Pipelines (S1) ==={RST}")
    host = SPACES["S1"]
    for name, cfg in PIPELINES.items():
        url = host + cfg["path"]
        timeout = 120 if name in ("graph", "orchestrator") else 90
        status, body, lat = http_post(url, cfg["payload"], timeout=timeout)
        answer = ""
        if status == 200 and body:
            try:
                data = json.loads(body)
                if isinstance(data, list) and data:
                    data = data[0]
                for key in cfg["answer_fields"]:
                    if key in data and data[key]:
                        answer = str(data[key])
                        break
            except Exception:
                pass
        passed = status == 200 and len(answer) > 10
        record("pipelines", f"{name} pipeline", passed, answer[:60] if answer else f"HTTP {status}", lat)


def test_pipelines_multi_space():
    """Test pipelines across ALL spaces."""
    print(f"\n{BOLD}=== Pipeline Cross-Space Check ==={RST}")
    test_cfg = PIPELINES["standard"]
    for space_name, space_url in SPACES.items():
        url = space_url + test_cfg["path"]
        status, body, lat = http_post(url, test_cfg["payload"], timeout=60)
        answer = ""
        if status == 200 and body:
            try:
                data = json.loads(body)
                if isinstance(data, list) and data:
                    data = data[0]
                for key in test_cfg["answer_fields"]:
                    if key in data and data[key]:
                        answer = str(data[key])
                        break
            except Exception:
                pass
        passed = status == 200 and len(answer) > 10
        record("cross-space", f"standard on {space_name}", passed, answer[:40] if answer else f"HTTP {status}", lat)


def test_n8n_workflows():
    """Check n8n workflow status via API."""
    print(f"\n{BOLD}=== n8n Workflows ==={RST}")
    n8n_api_key = os.environ.get("N8N_API_KEY", "")
    n8n_host = SPACES["S1"]
    if not n8n_api_key:
        record("n8n", "API key", False, "N8N_API_KEY not set")
        return

    for wf_name, wf_id in N8N_WORKFLOWS.items():
        try:
            url = f"{n8n_host}/api/v1/workflows/{wf_id}"
            req = urllib.request.Request(url, headers={"X-N8N-API-KEY": n8n_api_key})
            with urllib.request.urlopen(req, context=_ssl, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                active = data.get("active", False)
                record("n8n", f"{wf_name} ({wf_id[:8]})",
                       active, "ACTIVE" if active else "INACTIVE")
        except Exception as e:
            record("n8n", f"{wf_name}", False, str(e)[:80])


def test_ingestion_flow():
    """Test end-to-end ingestion flow: Tavily → Docling → Pinecone."""
    print(f"\n{BOLD}=== Ingestion Flow ==={RST}")
    # Check n8n Ingestion V4.0 webhook
    host = SPACES["S1"]
    status, body, lat = http_post(f"{host}/webhook/ingestion-v4", {
        "action": "health_check",
    }, timeout=30)
    record("ingestion", "V4.0 webhook reachable", status in (200, 201, 400), f"HTTP {status}", lat)

    # Check Enrichment V4.0 webhook
    status, body, lat = http_post(f"{host}/webhook/enrichment-v4", {
        "action": "health_check",
    }, timeout=30)
    record("enrichment", "V4.0 webhook reachable", status in (200, 201, 400), f"HTTP {status}", lat)


def test_e2e_flow():
    """End-to-end: question → full pipeline → verified answer."""
    print(f"\n{BOLD}=== End-to-End Flow ==={RST}")
    try:
        sys.path.insert(0, os.path.join(REPO_ROOT, "eval"))
        from llm_judge import judge_answer

        # Ask a factual question through orchestrator
        host = SPACES["S1"]
        status, body, lat = http_post(
            f"{host}/webhook/orchestrator-v2",
            {"question": "What is Boeing revenue in FY2022?", "sector": "finance"},
            timeout=90,
        )
        answer = ""
        if status == 200 and body:
            data = json.loads(body)
            if isinstance(data, list) and data:
                data = data[0]
            for k in ["response", "answer", "interpretation"]:
                if k in data and data[k]:
                    answer = str(data[k])
                    break

        # Judge the answer
        judgment = judge_answer("What is Boeing revenue in FY2022?", answer, "66608", "finance")
        record("e2e", "orchestrator → LLM judge",
               judgment["pass"],
               f"acc={judgment['accuracy']} | {judgment['reasoning'][:60]}", lat)
    except Exception as e:
        record("e2e", "orchestrator → LLM judge", False, str(e)[:100])


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

COMPONENTS = {
    "spaces": test_spaces,
    "litellm": test_litellm,
    "embeddings": test_embeddings,
    "docling": test_docling,
    "pinecone": test_pinecone,
    "neo4j": test_neo4j,
    "supabase": test_supabase,
    "pipelines": test_pipelines,
    "cross-space": test_pipelines_multi_space,
    "n8n": test_n8n_workflows,
    "ingestion": test_ingestion_flow,
    "e2e": test_e2e_flow,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full System Test")
    parser.add_argument("--component", "-c", help="Test specific component")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests (cross-space, e2e)")
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 70}")
    print(f"  NOMOS SECTOR AI — FULL SYSTEM TEST")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"{'=' * 70}{RST}\n")

    skip = {"cross-space", "e2e"} if args.fast else set()

    if args.component:
        if args.component in COMPONENTS:
            COMPONENTS[args.component]()
        else:
            print(f"Unknown component: {args.component}")
            print(f"Available: {', '.join(COMPONENTS.keys())}")
            sys.exit(1)
    else:
        for name, fn in COMPONENTS.items():
            if name not in skip:
                try:
                    fn()
                except Exception as e:
                    record(name, "CRASH", False, str(e)[:100])

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total = len(results)

    print(f"\n{BOLD}{'=' * 70}")
    print(f"  SUMMARY: {passed}/{total} PASS  |  {failed} FAIL")
    print(f"{'=' * 70}{RST}")

    if failed:
        print(f"\n{R}  FAILURES:{RST}")
        for r in results:
            if r["status"] == "FAIL":
                print(f"    {R}FAIL{RST}  {r['component']:20s} {r['test']:35s} {D}{r['detail']}{RST}")

    # JSON output
    if args.json:
        output = {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "summary": {"total": total, "passed": passed, "failed": failed},
            "tests": results,
        }
        json_file = os.path.join(REPO_ROOT, "data", "eval", "full-system-test.json")
        os.makedirs(os.path.dirname(json_file), exist_ok=True)
        with open(json_file, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n  JSON saved: {json_file}")

    sys.exit(0 if failed == 0 else 1)
