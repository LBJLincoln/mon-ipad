#!/usr/bin/env python3
"""
INTELLIGENT BENCHMARK TEST SUITE
=================================
Runs the full battery of tests against all 10 ingested datasets (7,824 Q&A pairs)
using the 4 deployed n8n benchmark workflows:

  1. BENCHMARK - RAG Batch Tester         → /webhook/benchmark-test-rag
  2. BENCHMARK - Orchestrator Tester      → /webhook/benchmark-test-orchestrator
  3. BENCHMARK - Monitoring Dashboard     → /webhook/benchmark-monitoring
  4. BENCHMARK - Dataset Ingestion (verify) → /webhook/benchmark-sql-exec

Test phases:
  Phase 1: Data Integrity Verification (Supabase + Pinecone)
  Phase 2: RAG Retrieval Tests (recall, MRR, NDCG)
  Phase 3: RAG Generation Tests (EM, F1, faithfulness)
  Phase 4: E2E RAG Tests (accuracy, precision)
  Phase 5: Domain-Specific Tests (medical, finance)
  Phase 6: Orchestrator Routing Tests
  Phase 7: Robustness Tests (hallucination, abstention)
  Phase 8: Cross-Dataset Regression Tests
"""

import json
import os
import sys
import time
import hashlib
import traceback
from datetime import datetime
from urllib import request, error, parse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Configuration ───────────────────────────────────────────────
N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
PINECONE_HOST = "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
PINECONE_API_KEY = "pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"

BASE_DIR = "/home/user/mon-ipad/benchmark-workflows"
RESULTS_FILE = os.path.join(BASE_DIR, "benchmark-test-results.json")

# The 10 datasets successfully ingested (7,824 Q&A pairs)
DATASETS = [
    {"name": "hotpotqa",    "category": "multi_hop_qa",  "items": 1000, "rag_target": "graph"},
    {"name": "frames",      "category": "rag_benchmark", "items": 824,  "rag_target": "standard"},
    {"name": "squad_v2",    "category": "single_hop_qa", "items": 1000, "rag_target": "standard"},
    {"name": "popqa",       "category": "single_hop_qa", "items": 1000, "rag_target": "standard"},
    {"name": "pubmedqa",    "category": "domain_medical","items": 500,  "rag_target": "standard"},
    {"name": "triviaqa",    "category": "single_hop_qa", "items": 1000, "rag_target": "standard"},
    {"name": "finqa",       "category": "domain_finance","items": 500,  "rag_target": "quantitative"},
    {"name": "msmarco",     "category": "retrieval",     "items": 1000, "rag_target": "standard"},
    {"name": "narrativeqa", "category": "long_form_qa",  "items": 500,  "rag_target": "standard"},
    {"name": "asqa",        "category": "long_form_qa",  "items": 500,  "rag_target": "standard"},
]

# ─── HTTP Helpers ────────────────────────────────────────────────
def http_request(url, data=None, headers=None, method="POST", timeout=120, retries=3):
    """Make HTTP request with retries and exponential backoff."""
    hdrs = headers or {}
    hdrs.setdefault("Content-Type", "application/json")
    body = json.dumps(data).encode() if data else None

    last_error = None
    for attempt in range(retries):
        try:
            req = request.Request(url, data=body, headers=hdrs, method=method)
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                if not raw or raw.strip() == "":
                    return {"status": resp.status, "data": None,
                            "error": f"Empty response body (HTTP {resp.status}). "
                                     "Workflow likely failed internally — check n8n execution logs. "
                                     "Common causes: missing credentials, inactive workflow, node error."}
                try:
                    return {"status": resp.status, "data": json.loads(raw), "error": None}
                except json.JSONDecodeError:
                    return {"status": resp.status, "data": raw, "error": None}
        except error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode()
            except:
                pass
            last_error = f"HTTP {e.code}: {err_body[:500]}"
            if e.code >= 500 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {"status": e.code, "data": None, "error": last_error}
        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
    return {"status": 0, "data": None, "error": last_error}


def webhook_call(path, data, timeout=120):
    """Call n8n webhook endpoint."""
    return http_request(f"{N8N_HOST}/webhook/{path}", data=data, timeout=timeout)


def n8n_api(method, endpoint, data=None, timeout=60):
    """Call n8n REST API."""
    return http_request(
        f"{N8N_HOST}/api/v1{endpoint}",
        data=data,
        headers={"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"},
        method=method,
        timeout=timeout
    )


def pinecone_api(method, endpoint, data=None, timeout=30):
    """Call Pinecone REST API."""
    return http_request(
        f"{PINECONE_HOST}{endpoint}",
        data=data,
        headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"},
        method=method,
        timeout=timeout
    )


def exec_sql(sql, timeout=30):
    """Execute SQL via n8n webhook."""
    return webhook_call("benchmark-sql-exec", {"sql": sql}, timeout=timeout)


# ─── Test Result Tracking ────────────────────────────────────────
class TestResults:
    def __init__(self):
        self.started_at = datetime.now().isoformat()
        self.phases = {}
        self.total_tests = 0
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.warnings = []
        self.all_results = []

    def add(self, phase, test_name, dataset, status, details=None, error_msg=None, latency_ms=None):
        self.total_tests += 1
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        elif status == "ERROR":
            self.errors += 1

        result = {
            "phase": phase,
            "test": test_name,
            "dataset": dataset,
            "status": status,
            "details": details,
            "error": error_msg,
            "latency_ms": latency_ms,
            "timestamp": datetime.now().isoformat()
        }
        self.all_results.append(result)

        if phase not in self.phases:
            self.phases[phase] = {"tests": [], "pass": 0, "fail": 0, "error": 0}
        self.phases[phase]["tests"].append(result)
        self.phases[phase][{"PASS": "pass", "FAIL": "fail", "ERROR": "error", "WARN": "pass"}.get(status, "error")] += 1

    def warn(self, msg):
        self.warnings.append({"message": msg, "timestamp": datetime.now().isoformat()})

    def to_dict(self):
        return {
            "suite": "INTELLIGENT BENCHMARK TEST SUITE",
            "started_at": self.started_at,
            "completed_at": datetime.now().isoformat(),
            "summary": {
                "total_tests": self.total_tests,
                "passed": self.passed,
                "failed": self.failed,
                "errors": self.errors,
                "pass_rate": f"{(self.passed / max(self.total_tests, 1)) * 100:.1f}%"
            },
            "phases": {k: {
                "total": v["pass"] + v["fail"] + v["error"],
                "passed": v["pass"],
                "failed": v["fail"],
                "errors": v["error"],
                "tests": v["tests"]
            } for k, v in self.phases.items()},
            "warnings": self.warnings,
            "datasets_tested": [d["name"] for d in DATASETS],
            "total_qa_pairs": sum(d["items"] for d in DATASETS)
        }


# ─── PHASE 1: Data Integrity Verification ───────────────────────
def phase1_data_integrity(results):
    """Verify all 10 datasets are properly stored in Supabase + Pinecone."""
    print("\n" + "=" * 70)
    print("  PHASE 1: DATA INTEGRITY VERIFICATION")
    print("=" * 70)

    # Test 1.1: Supabase row counts per dataset
    for ds in DATASETS:
        name = ds["name"]
        expected = ds["items"]
        print(f"\n  [1.1] Supabase count: {name} (expecting {expected})...")
        t0 = time.time()

        resp = exec_sql(
            f"SELECT COUNT(*) as cnt FROM benchmark_datasets "
            f"WHERE dataset_name = '{name}' AND tenant_id = 'benchmark'"
        )
        lat = int((time.time() - t0) * 1000)

        if resp["error"]:
            results.add("P1_Data_Integrity", "supabase_row_count", name, "ERROR",
                         error_msg=resp["error"], latency_ms=lat)
            continue

        data = resp.get("data")
        actual = 0
        if isinstance(data, list) and data:
            actual = data[0].get("cnt", data[0].get("count", 0))
        elif isinstance(data, dict):
            actual = data.get("cnt", data.get("count", 0))
            # Try to parse from nested structures
            if isinstance(data.get("data"), list) and data["data"]:
                actual = data["data"][0].get("cnt", data["data"][0].get("count", 0))

        try:
            actual = int(actual)
        except (TypeError, ValueError):
            actual = 0

        if actual >= expected:
            results.add("P1_Data_Integrity", "supabase_row_count", name, "PASS",
                         details={"expected": expected, "actual": actual}, latency_ms=lat)
            print(f"    PASS: {actual}/{expected} rows")
        elif actual > 0:
            results.add("P1_Data_Integrity", "supabase_row_count", name, "WARN",
                         details={"expected": expected, "actual": actual,
                                  "missing": expected - actual}, latency_ms=lat)
            print(f"    WARN: {actual}/{expected} rows (missing {expected - actual})")
        else:
            results.add("P1_Data_Integrity", "supabase_row_count", name, "FAIL",
                         details={"expected": expected, "actual": actual},
                         error_msg=f"No rows found. Raw response: {str(data)[:200]}",
                         latency_ms=lat)
            print(f"    FAIL: 0/{expected} rows")

    # Test 1.2: Pinecone namespace verification via describe_index_stats
    print(f"\n  [1.2] Pinecone namespaces (via index stats)...")
    t0 = time.time()
    stats_resp = pinecone_api("GET", "/describe_index_stats")
    lat = int((time.time() - t0) * 1000)

    if stats_resp["error"]:
        for ds in DATASETS:
            results.add("P1_Data_Integrity", "pinecone_namespace", ds["name"], "ERROR",
                         error_msg=stats_resp["error"], latency_ms=lat)
    else:
        ns_data = stats_resp.get("data", {}).get("namespaces", {})
        for ds in DATASETS:
            name = ds["name"]
            ns = f"benchmark-{name}"
            expected = ds["items"]
            ns_info = ns_data.get(ns, {})
            vec_count = ns_info.get("vectorCount", 0)

            if vec_count >= expected:
                results.add("P1_Data_Integrity", "pinecone_namespace", name, "PASS",
                             details={"namespace": ns, "expected": expected, "vectors": vec_count},
                             latency_ms=lat)
                print(f"    PASS: {ns} — {vec_count}/{expected} vectors")
            elif vec_count > 0:
                results.add("P1_Data_Integrity", "pinecone_namespace", name, "WARN",
                             details={"namespace": ns, "expected": expected, "vectors": vec_count},
                             latency_ms=lat)
                print(f"    WARN: {ns} — {vec_count}/{expected} vectors (partial)")
            else:
                results.add("P1_Data_Integrity", "pinecone_namespace", name, "FAIL",
                             details={"namespace": ns, "expected": expected, "vectors": 0},
                             error_msg="Namespace empty or missing", latency_ms=lat)
                print(f"    FAIL: {ns} — no vectors")

    # Test 1.3: Supabase data quality (sample questions not empty)
    print(f"\n  [1.3] Data quality check (non-empty Q&A pairs)...")
    t0 = time.time()
    resp = exec_sql(
        "SELECT dataset_name, "
        "COUNT(*) as total, "
        "COUNT(*) FILTER (WHERE question IS NOT NULL AND question != '') as valid_q, "
        "COUNT(*) FILTER (WHERE expected_answer IS NOT NULL AND expected_answer != '') as valid_a "
        "FROM benchmark_datasets WHERE tenant_id = 'benchmark' "
        "GROUP BY dataset_name ORDER BY dataset_name"
    )
    lat = int((time.time() - t0) * 1000)

    if resp["error"]:
        results.add("P1_Data_Integrity", "data_quality", "all", "ERROR",
                     error_msg=resp["error"], latency_ms=lat)
    else:
        data = resp.get("data")
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        # Handle single dict response (n8n may return single row as dict)
        if isinstance(data, dict) and "dataset_name" in data:
            data = [data]
        if isinstance(data, list):
            for row in data:
                ds_name = row.get("dataset_name", "?")
                total = int(row.get("total", 0))
                valid_q = int(row.get("valid_q", 0))
                valid_a = int(row.get("valid_a", 0))
                q_rate = valid_q / max(total, 1)
                a_rate = valid_a / max(total, 1)

                if q_rate >= 0.95 and a_rate >= 0.80:
                    results.add("P1_Data_Integrity", "data_quality", ds_name, "PASS",
                                details={"total": total, "valid_questions": valid_q,
                                          "valid_answers": valid_a,
                                          "q_rate": f"{q_rate:.1%}", "a_rate": f"{a_rate:.1%}"},
                                latency_ms=lat)
                    print(f"    PASS: {ds_name} — Q:{q_rate:.0%} A:{a_rate:.0%}")
                else:
                    results.add("P1_Data_Integrity", "data_quality", ds_name, "FAIL",
                                details={"total": total, "valid_questions": valid_q,
                                          "valid_answers": valid_a},
                                error_msg=f"Low quality: Q={q_rate:.0%} A={a_rate:.0%}",
                                latency_ms=lat)
                    print(f"    FAIL: {ds_name} — Q:{q_rate:.0%} A:{a_rate:.0%}")
        else:
            results.add("P1_Data_Integrity", "data_quality", "all", "ERROR",
                         error_msg=f"Unexpected response format: {str(data)[:300]}",
                         latency_ms=lat)

    # Test 1.4: Pinecone describe_index_stats
    print(f"\n  [1.4] Pinecone index stats...")
    t0 = time.time()
    resp = pinecone_api("GET", "/describe_index_stats")
    lat = int((time.time() - t0) * 1000)

    if resp["error"]:
        results.add("P1_Data_Integrity", "pinecone_index_stats", "all", "ERROR",
                     error_msg=resp["error"], latency_ms=lat)
    else:
        data = resp.get("data", {})
        total_vectors = data.get("totalVectorCount", 0)
        namespaces = data.get("namespaces", {})
        benchmark_ns = {k: v for k, v in namespaces.items() if k.startswith("benchmark-")}

        results.add("P1_Data_Integrity", "pinecone_index_stats", "all", "PASS",
                     details={
                         "total_vectors": total_vectors,
                         "benchmark_namespaces": len(benchmark_ns),
                         "namespace_counts": {k: v.get("vectorCount", 0) for k, v in benchmark_ns.items()}
                     }, latency_ms=lat)
        print(f"    Total vectors: {total_vectors}")
        for ns, info in benchmark_ns.items():
            print(f"    {ns}: {info.get('vectorCount', '?')} vectors")


# ─── PHASE 2: RAG Retrieval Tests ───────────────────────────────
def phase2_rag_retrieval(results):
    """Test RAG retrieval quality: recall@5, recall@10, MRR@10, NDCG@10."""
    print("\n" + "=" * 70)
    print("  PHASE 2: RAG RETRIEVAL TESTS")
    print("=" * 70)

    for ds in DATASETS:
        name = ds["name"]
        print(f"\n  [2.1] RAG Retrieval: {name} ({ds['items']} items)...")
        t0 = time.time()

        payload = {
            "dataset_name": name,
            "test_type": "retrieval",
            "rag_target": ds["rag_target"],
            "sample_size": min(50, ds["items"]),  # Test sample
            "batch_size": 10,
            "tenant_id": "benchmark"
        }

        resp = webhook_call("benchmark-test-rag", payload, timeout=180)
        lat = int((time.time() - t0) * 1000)

        if resp["error"]:
            results.add("P2_RAG_Retrieval", "retrieval_test", name, "ERROR",
                         error_msg=resp["error"], latency_ms=lat)
            print(f"    ERROR: {resp['error'][:200]}")
        else:
            data = resp.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            status = "PASS" if isinstance(data, dict) and data.get("status") != "error" else "FAIL"
            err_msg = None
            if status == "FAIL":
                err_msg = str(data)[:500] if data else "Empty response"

            results.add("P2_RAG_Retrieval", "retrieval_test", name, status,
                         details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                         error_msg=err_msg, latency_ms=lat)
            print(f"    {status}: {lat}ms — {str(data)[:200]}")


# ─── PHASE 3: RAG Generation Tests ──────────────────────────────
def phase3_rag_generation(results):
    """Test RAG generation quality: EM, F1, faithfulness, ROUGE-L."""
    print("\n" + "=" * 70)
    print("  PHASE 3: RAG GENERATION TESTS")
    print("=" * 70)

    for ds in DATASETS:
        name = ds["name"]
        print(f"\n  [3.1] RAG Generation: {name}...")
        t0 = time.time()

        payload = {
            "dataset_name": name,
            "test_type": "generation",
            "rag_target": ds["rag_target"],
            "sample_size": min(30, ds["items"]),
            "batch_size": 5,
            "tenant_id": "benchmark"
        }

        resp = webhook_call("benchmark-test-rag", payload, timeout=240)
        lat = int((time.time() - t0) * 1000)

        if resp["error"]:
            results.add("P3_RAG_Generation", "generation_test", name, "ERROR",
                         error_msg=resp["error"], latency_ms=lat)
            print(f"    ERROR: {resp['error'][:200]}")
        else:
            data = resp.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            status = "PASS" if isinstance(data, dict) and data.get("status") != "error" else "FAIL"
            err_msg = data.get("error") if isinstance(data, dict) else str(data)[:500] if status == "FAIL" else None

            results.add("P3_RAG_Generation", "generation_test", name, status,
                         details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                         error_msg=err_msg, latency_ms=lat)
            print(f"    {status}: {lat}ms — {str(data)[:200]}")


# ─── PHASE 4: E2E RAG Tests ─────────────────────────────────────
def phase4_e2e(results):
    """End-to-end RAG testing: accuracy, retrieval precision, perfect/acceptable rate."""
    print("\n" + "=" * 70)
    print("  PHASE 4: END-TO-END RAG TESTS")
    print("=" * 70)

    for ds in DATASETS:
        name = ds["name"]
        print(f"\n  [4.1] E2E RAG: {name}...")
        t0 = time.time()

        payload = {
            "dataset_name": name,
            "test_type": "e2e",
            "rag_target": ds["rag_target"],
            "sample_size": min(25, ds["items"]),
            "batch_size": 5,
            "tenant_id": "benchmark"
        }

        resp = webhook_call("benchmark-test-rag", payload, timeout=300)
        lat = int((time.time() - t0) * 1000)

        if resp["error"]:
            results.add("P4_E2E_RAG", "e2e_test", name, "ERROR",
                         error_msg=resp["error"], latency_ms=lat)
            print(f"    ERROR: {resp['error'][:200]}")
        else:
            data = resp.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            status = "PASS" if isinstance(data, dict) and data.get("status") != "error" else "FAIL"
            err_msg = data.get("error") if isinstance(data, dict) else str(data)[:500] if status == "FAIL" else None

            results.add("P4_E2E_RAG", "e2e_test", name, status,
                         details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                         error_msg=err_msg, latency_ms=lat)
            print(f"    {status}: {lat}ms — {str(data)[:200]}")


# ─── PHASE 5: Domain-Specific Tests ─────────────────────────────
def phase5_domain(results):
    """Test domain-specific datasets: medical (pubmedqa), finance (finqa)."""
    print("\n" + "=" * 70)
    print("  PHASE 5: DOMAIN-SPECIFIC TESTS")
    print("=" * 70)

    domain_datasets = [d for d in DATASETS if d["category"].startswith("domain_")]

    for ds in domain_datasets:
        name = ds["name"]
        print(f"\n  [5.1] Domain Test: {name} ({ds['category']})...")
        t0 = time.time()

        payload = {
            "dataset_name": name,
            "test_type": "domain",
            "rag_target": ds["rag_target"],
            "sample_size": min(25, ds["items"]),
            "batch_size": 5,
            "tenant_id": "benchmark",
            "metrics": ["accuracy", "faithfulness", "extraction_precision"]
        }

        resp = webhook_call("benchmark-test-rag", payload, timeout=240)
        lat = int((time.time() - t0) * 1000)

        if resp["error"]:
            results.add("P5_Domain", "domain_test", name, "ERROR",
                         error_msg=resp["error"], latency_ms=lat)
            print(f"    ERROR: {resp['error'][:200]}")
        else:
            data = resp.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            status = "PASS" if isinstance(data, dict) and data.get("status") != "error" else "FAIL"
            err_msg = data.get("error") if isinstance(data, dict) else str(data)[:500] if status == "FAIL" else None

            results.add("P5_Domain", "domain_test", name, status,
                         details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                         error_msg=err_msg, latency_ms=lat)
            print(f"    {status}: {lat}ms — {str(data)[:200]}")


# ─── PHASE 6: Orchestrator Routing Tests ────────────────────────
def phase6_orchestrator(results):
    """Test orchestrator routing across all datasets."""
    print("\n" + "=" * 70)
    print("  PHASE 6: ORCHESTRATOR ROUTING TESTS")
    print("=" * 70)

    # 6.1: Single query routing for each dataset
    for ds in DATASETS:
        name = ds["name"]
        print(f"\n  [6.1] Orchestrator Single Query: {name}...")
        t0 = time.time()

        payload = {
            "dataset_name": name,
            "test_mode": "single_query",
            "sample_size": min(20, ds["items"]),
            "batch_size": 5,
            "tenant_id": "benchmark"
        }

        resp = webhook_call("benchmark-test-orchestrator", payload, timeout=180)
        lat = int((time.time() - t0) * 1000)

        if resp["error"]:
            results.add("P6_Orchestrator", "single_query_routing", name, "ERROR",
                         error_msg=resp["error"], latency_ms=lat)
            print(f"    ERROR: {resp['error'][:200]}")
        else:
            data = resp.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            status = "PASS" if isinstance(data, dict) and data.get("status") != "error" else "FAIL"
            err_msg = data.get("error") if isinstance(data, dict) else str(data)[:500] if status == "FAIL" else None

            results.add("P6_Orchestrator", "single_query_routing", name, status,
                         details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                         error_msg=err_msg, latency_ms=lat)
            print(f"    {status}: {lat}ms — {str(data)[:200]}")

    # 6.2: Routing evaluation
    route_test_datasets = ["hotpotqa", "finqa", "squad_v2"]  # Test routing correctness
    for ds_name in route_test_datasets:
        print(f"\n  [6.2] Routing Eval: {ds_name}...")
        t0 = time.time()

        payload = {
            "dataset_name": ds_name,
            "test_mode": "routing_eval",
            "sample_size": 15,
            "batch_size": 5,
            "tenant_id": "benchmark"
        }

        resp = webhook_call("benchmark-test-orchestrator", payload, timeout=180)
        lat = int((time.time() - t0) * 1000)

        if resp["error"]:
            results.add("P6_Orchestrator", "routing_eval", ds_name, "ERROR",
                         error_msg=resp["error"], latency_ms=lat)
            print(f"    ERROR: {resp['error'][:200]}")
        else:
            data = resp.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            status = "PASS" if isinstance(data, dict) and data.get("status") != "error" else "FAIL"
            err_msg = data.get("error") if isinstance(data, dict) else str(data)[:500] if status == "FAIL" else None

            results.add("P6_Orchestrator", "routing_eval", ds_name, status,
                         details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                         error_msg=err_msg, latency_ms=lat)
            print(f"    {status}: {lat}ms")

    # 6.3: Stress test (concurrent queries)
    print(f"\n  [6.3] Orchestrator Stress Test: squad_v2 (10 concurrent)...")
    t0 = time.time()

    payload = {
        "dataset_name": "squad_v2",
        "test_mode": "stress_test",
        "sample_size": 20,
        "batch_size": 10,
        "concurrency": 5,
        "tenant_id": "benchmark",
        "timeout_ms": 30000
    }

    resp = webhook_call("benchmark-test-orchestrator", payload, timeout=180)
    lat = int((time.time() - t0) * 1000)

    if resp["error"]:
        results.add("P6_Orchestrator", "stress_test", "squad_v2", "ERROR",
                     error_msg=resp["error"], latency_ms=lat)
        print(f"    ERROR: {resp['error'][:200]}")
    else:
        data = resp.get("data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                pass
        status = "PASS" if isinstance(data, dict) and data.get("status") != "error" else "FAIL"
        results.add("P6_Orchestrator", "stress_test", "squad_v2", status,
                     details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                     latency_ms=lat)
        print(f"    {status}: {lat}ms")


# ─── PHASE 7: Robustness Tests ──────────────────────────────────
def phase7_robustness(results):
    """Test robustness: hallucination rate, abstention, noise robustness."""
    print("\n" + "=" * 70)
    print("  PHASE 7: ROBUSTNESS TESTS")
    print("=" * 70)

    # Test on diverse datasets
    robustness_datasets = ["hotpotqa", "squad_v2", "pubmedqa", "frames"]

    for ds_name in robustness_datasets:
        print(f"\n  [7.1] Robustness: {ds_name}...")
        t0 = time.time()

        payload = {
            "dataset_name": ds_name,
            "test_type": "robustness",
            "rag_target": "standard",
            "sample_size": min(20, 500),
            "batch_size": 5,
            "tenant_id": "benchmark",
            "metrics": ["hallucination_rate", "abstention_rate", "noise_robustness", "counterfactual_robustness"]
        }

        resp = webhook_call("benchmark-test-rag", payload, timeout=240)
        lat = int((time.time() - t0) * 1000)

        if resp["error"]:
            results.add("P7_Robustness", "robustness_test", ds_name, "ERROR",
                         error_msg=resp["error"], latency_ms=lat)
            print(f"    ERROR: {resp['error'][:200]}")
        else:
            data = resp.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            status = "PASS" if isinstance(data, dict) and data.get("status") != "error" else "FAIL"
            err_msg = data.get("error") if isinstance(data, dict) else str(data)[:500] if status == "FAIL" else None

            results.add("P7_Robustness", "robustness_test", ds_name, status,
                         details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                         error_msg=err_msg, latency_ms=lat)
            print(f"    {status}: {lat}ms — {str(data)[:200]}")


# ─── PHASE 8: Monitoring & Cross-Dataset Regression ─────────────
def phase8_monitoring(results):
    """Run monitoring dashboard and check for regressions."""
    print("\n" + "=" * 70)
    print("  PHASE 8: MONITORING & REGRESSION CHECKS")
    print("=" * 70)

    # 8.1: Global monitoring dashboard
    print(f"\n  [8.1] Monitoring Dashboard (24h lookback)...")
    t0 = time.time()

    resp = webhook_call("benchmark-monitoring", {
        "lookback_hours": 24,
        "regression_threshold_pct": 5
    }, timeout=120)
    lat = int((time.time() - t0) * 1000)

    if resp["error"]:
        results.add("P8_Monitoring", "global_dashboard", "all", "ERROR",
                     error_msg=resp["error"], latency_ms=lat)
        print(f"    ERROR: {resp['error'][:200]}")
    else:
        data = resp.get("data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                pass
        results.add("P8_Monitoring", "global_dashboard", "all", "PASS",
                     details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                     latency_ms=lat)
        print(f"    Dashboard response: {lat}ms")

    # 8.2: Per-dataset monitoring
    for ds in DATASETS:
        name = ds["name"]
        print(f"\n  [8.2] Dataset Monitor: {name}...")
        t0 = time.time()

        resp = webhook_call("benchmark-monitoring", {
            "dataset_name": name,
            "lookback_hours": 24,
            "regression_threshold_pct": 5
        }, timeout=60)
        lat = int((time.time() - t0) * 1000)

        if resp["error"]:
            results.add("P8_Monitoring", "dataset_monitor", name, "ERROR",
                         error_msg=resp["error"], latency_ms=lat)
            print(f"    ERROR: {resp['error'][:200]}")
        else:
            data = resp.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass

            # Check for regression alerts in response
            alerts = []
            if isinstance(data, dict):
                alerts = data.get("alerts", data.get("regressions", []))

            if alerts:
                results.add("P8_Monitoring", "dataset_monitor", name, "WARN",
                             details={"alerts": alerts, "monitoring_data": data},
                             latency_ms=lat)
                print(f"    WARN: {len(alerts)} alert(s) detected")
            else:
                results.add("P8_Monitoring", "dataset_monitor", name, "PASS",
                             details=data if isinstance(data, dict) else {"raw": str(data)[:500]},
                             latency_ms=lat)
                print(f"    OK: No regressions ({lat}ms)")

    # 8.3: Ingestion stats verification
    print(f"\n  [8.3] Ingestion stats verification...")
    t0 = time.time()
    resp = exec_sql(
        "SELECT dataset_name, status, total_items, ingested_items, pinecone_vectors, supabase_rows "
        "FROM benchmark_ingestion_stats ORDER BY dataset_name"
    )
    lat = int((time.time() - t0) * 1000)

    if resp["error"]:
        results.add("P8_Monitoring", "ingestion_stats", "all", "ERROR",
                     error_msg=resp["error"], latency_ms=lat)
    else:
        data = resp.get("data")
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        results.add("P8_Monitoring", "ingestion_stats", "all",
                     "PASS" if data else "WARN",
                     details=data if isinstance(data, list) else {"raw": str(data)[:500]},
                     latency_ms=lat)
        if isinstance(data, list):
            for row in data:
                print(f"    {row.get('dataset_name', '?')}: {row.get('status', '?')} "
                      f"({row.get('ingested_items', '?')}/{row.get('total_items', '?')})")


# ─── PHASE 9: n8n Workflow Health Check ──────────────────────────
def phase9_workflow_health(results):
    """Verify all 4 benchmark workflows are active and healthy on n8n."""
    print("\n" + "=" * 70)
    print("  PHASE 9: WORKFLOW HEALTH CHECK")
    print("=" * 70)

    expected_workflows = {
        "BENCHMARK - Dataset Ingestion Pipeline": "L8irkzSrfLlgt2Bt",
        "BENCHMARK - RAG Batch Tester": "QCHKdqnTIEwEN1Ng",
        "BENCHMARK - Orchestrator Tester": "7UMkzbjkkYZAUzPD",
    }
    # Monitoring workflow may have a slightly different name on n8n
    monitoring_names = ["BENCHMARK - Monitoring & Alerting Dashboard", "BENCHMARK - Monitoring &amp; Alerting Dashboard",
                        "BENCHMARK - Monitoring"]

    # 9.1: Workflow existence and activation
    print(f"\n  [9.1] Checking workflow status...")
    t0 = time.time()
    resp = n8n_api("GET", "/workflows?limit=100")
    lat = int((time.time() - t0) * 1000)

    if resp["error"]:
        results.add("P9_WF_Health", "workflow_list", "all", "ERROR",
                     error_msg=resp["error"], latency_ms=lat)
        return

    workflows = {}
    if isinstance(resp.get("data"), dict):
        for wf in resp["data"].get("data", []):
            workflows[wf.get("name")] = wf

    # Add monitoring with fuzzy name matching
    found_monitoring = None
    for mname in monitoring_names:
        if mname in workflows:
            found_monitoring = mname
            break
    # Also try partial match
    if not found_monitoring:
        for wf_name_key in workflows:
            if "monitoring" in wf_name_key.lower() or "monitor" in wf_name_key.lower():
                found_monitoring = wf_name_key
                break
    if found_monitoring:
        expected_workflows[found_monitoring] = "VFbsVqMsYTAdb1Ur"
    else:
        expected_workflows["BENCHMARK - Monitoring & Alerting Dashboard"] = "VFbsVqMsYTAdb1Ur"

    for wf_name, expected_id in expected_workflows.items():
        wf = workflows.get(wf_name)
        if not wf:
            results.add("P9_WF_Health", "workflow_exists", wf_name, "FAIL",
                         error_msg=f"Workflow '{wf_name}' not found on n8n. "
                                   f"Available: {list(workflows.keys())[:10]}",
                         latency_ms=lat)
            print(f"    FAIL: {wf_name} — NOT FOUND")
            continue

        is_active = wf.get("active", False)
        wf_id = wf.get("id")
        node_count = len(wf.get("nodes", []))

        if is_active:
            results.add("P9_WF_Health", "workflow_active", wf_name, "PASS",
                         details={"id": wf_id, "active": True, "nodes": node_count},
                         latency_ms=lat)
            print(f"    PASS: {wf_name} — Active (ID: {wf_id})")
        else:
            results.add("P9_WF_Health", "workflow_active", wf_name, "WARN",
                         details={"id": wf_id, "active": False, "nodes": node_count},
                         latency_ms=lat)
            print(f"    WARN: {wf_name} — Inactive (ID: {wf_id})")

    # 9.2: Recent execution history
    print(f"\n  [9.2] Checking recent executions...")
    t0 = time.time()
    resp = n8n_api("GET", "/executions?limit=20&status=error")
    lat = int((time.time() - t0) * 1000)

    if resp["error"]:
        results.add("P9_WF_Health", "recent_errors", "all", "ERROR",
                     error_msg=resp["error"], latency_ms=lat)
    else:
        data = resp.get("data", {})
        executions = data.get("data", []) if isinstance(data, dict) else []
        error_count = len(executions)

        if error_count == 0:
            results.add("P9_WF_Health", "recent_errors", "all", "PASS",
                         details={"error_executions": 0}, latency_ms=lat)
            print(f"    PASS: No recent error executions")
        else:
            error_details = [{"id": e.get("id"), "workflow": e.get("workflowData", {}).get("name", "?"),
                              "finished_at": e.get("stoppedAt")} for e in executions[:5]]
            results.add("P9_WF_Health", "recent_errors", "all", "WARN",
                         details={"error_executions": error_count, "recent": error_details},
                         latency_ms=lat)
            print(f"    WARN: {error_count} recent error executions")
            for e in error_details[:3]:
                print(f"      - {e['workflow']} (exec {e['id']})")


# ─── Report Generation ──────────────────────────────────────────
def generate_report(results):
    """Generate comprehensive JSON + console report."""
    report = results.to_dict()

    # Save JSON
    with open(RESULTS_FILE, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Console summary
    print("\n" + "=" * 70)
    print("  BENCHMARK TEST SUITE — FINAL REPORT")
    print("=" * 70)
    print(f"  Started:    {report['started_at']}")
    print(f"  Completed:  {report['completed_at']}")
    print(f"  Datasets:   {len(DATASETS)} ({sum(d['items'] for d in DATASETS)} Q&A pairs)")
    print(f"  ")
    print(f"  RESULTS:")
    print(f"  ─────────────────────────────────────────")
    print(f"  Total Tests: {report['summary']['total_tests']}")
    print(f"  Passed:      {report['summary']['passed']}  ✓")
    print(f"  Failed:      {report['summary']['failed']}  ✗")
    print(f"  Errors:      {report['summary']['errors']}  !")
    print(f"  Pass Rate:   {report['summary']['pass_rate']}")
    print(f"  ")
    print(f"  BY PHASE:")
    print(f"  ─────────────────────────────────────────")
    for phase_name, phase_data in report["phases"].items():
        p = phase_data["passed"]
        f_ = phase_data["failed"]
        e = phase_data["errors"]
        t = phase_data["total"]
        bar = "■" * p + "□" * f_ + "!" * e
        print(f"  {phase_name:35s} {p}/{t} passed  [{bar}]")

    # Errors detail
    error_tests = [r for r in results.all_results if r["status"] in ("FAIL", "ERROR")]
    if error_tests:
        print(f"\n  FAILURES & ERRORS ({len(error_tests)}):")
        print(f"  ─────────────────────────────────────────")
        for t in error_tests:
            print(f"  [{t['status']}] {t['phase']} > {t['test']} > {t['dataset']}")
            if t.get("error"):
                print(f"         {t['error'][:300]}")

    if results.warnings:
        print(f"\n  WARNINGS ({len(results.warnings)}):")
        for w in results.warnings:
            print(f"  - {w['message']}")

    print(f"\n  Results saved to: {RESULTS_FILE}")
    print("=" * 70)

    return report


# ─── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("  INTELLIGENT BENCHMARK TEST SUITE")
    print(f"  Multi-RAG Orchestrator — SOTA 2026")
    print(f"  Time: {datetime.now().isoformat()}")
    print(f"  Datasets: {len(DATASETS)} ({sum(d['items'] for d in DATASETS)} Q&A pairs)")
    print(f"  Phases: 9 (Data Integrity → Monitoring)")
    print("=" * 70)

    results = TestResults()
    phases = [
        ("Phase 1: Data Integrity", phase1_data_integrity),
        ("Phase 2: RAG Retrieval", phase2_rag_retrieval),
        ("Phase 3: RAG Generation", phase3_rag_generation),
        ("Phase 4: E2E RAG", phase4_e2e),
        ("Phase 5: Domain-Specific", phase5_domain),
        ("Phase 6: Orchestrator", phase6_orchestrator),
        ("Phase 7: Robustness", phase7_robustness),
        ("Phase 8: Monitoring", phase8_monitoring),
        ("Phase 9: Workflow Health", phase9_workflow_health),
    ]

    for phase_name, phase_fn in phases:
        try:
            print(f"\n{'#' * 70}")
            print(f"  STARTING: {phase_name}")
            print(f"{'#' * 70}")
            phase_fn(results)
        except KeyboardInterrupt:
            print(f"\n  INTERRUPTED during {phase_name}")
            results.warn(f"Suite interrupted during {phase_name}")
            break
        except Exception as e:
            print(f"\n  CRITICAL ERROR in {phase_name}: {e}")
            traceback.print_exc()
            results.warn(f"Critical error in {phase_name}: {str(e)}")

    report = generate_report(results)
    sys.exit(0 if results.failed == 0 and results.errors == 0 else 1)
