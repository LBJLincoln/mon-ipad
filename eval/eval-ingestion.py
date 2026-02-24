#!/usr/bin/env python3
"""
Eval: Data-Ingestion Pipeline — End-to-End Ingest + Retrieve Tests
===================================================================
Standalone eval script for the ingestion pipeline. Sends documents to the
ingestion webhook, then queries the standard RAG pipeline to verify
the ingested content is retrievable and answers are correct.

Designed to run unattended on Codespaces or GitHub Actions (nohup-safe).

Endpoints:
  Ingestion : {N8N_HOST}/webhook/ingestion-v3
  Retrieval : {N8N_HOST}/webhook/rag-multi-index-v3

Usage:
  source .env.local
  python eval/eval-ingestion.py                          # Default: 50 tests
  python eval/eval-ingestion.py --max 20 --batch-size 3  # Quick run
  python eval/eval-ingestion.py --early-stop 5           # Stop after 5 consecutive fails
  python eval/eval-ingestion.py --force                   # Bypass gate checks
  nohup python eval/eval-ingestion.py --max 50 &         # Unattended
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
import hashlib
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

INGESTION_URL = f"{N8N_HOST}/webhook/ingestion-v3"
RAG_URL = f"{N8N_HOST}/webhook/rag-multi-index-v3"

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
# Answer extraction helpers
# ---------------------------------------------------------------------------
def _extract_answer(body):
    """Pull answer text from various response shapes."""
    for key in ("response", "answer", "result", "interpretation", "final_response", "text"):
        if key in body and body[key]:
            return str(body[key])
    # Fallback: stringify
    return json.dumps(body)[:500] if body else ""


def _normalize(text):
    """Normalize for fuzzy matching."""
    text = re.sub(r'(\d),(\d)', r'\1\2', text)
    return text.lower().replace('$', '').replace('%', '').strip()

# ---------------------------------------------------------------------------
# Test documents — 20 inline business documents
# ---------------------------------------------------------------------------
def _make_test_documents():
    """Return 20 diverse business test documents with verification queries."""
    docs = [
        {
            "title": "Acme Corp Q3 2025 Revenue Report",
            "content": "Acme Corp reported total revenue of $47.3 million for Q3 2025, "
                       "representing a 12% year-over-year increase. The growth was primarily "
                       "driven by the cloud services division which contributed $28.1 million. "
                       "Operating margin improved to 18.5% from 15.2% in the prior year.",
            "query": "What was Acme Corp's total revenue in Q3 2025?",
            "expected_keywords": ["47.3", "million"],
            "category": "financial",
        },
        {
            "title": "NovaTech Employee Handbook — Remote Work Policy",
            "content": "NovaTech's remote work policy allows employees to work from home up to "
                       "3 days per week. All remote employees must be available on Slack between "
                       "9:00 AM and 5:00 PM local time. VPN connection is mandatory for accessing "
                       "internal systems. Managers must approve remote schedules by the 1st of each month.",
            "query": "How many days per week can NovaTech employees work from home?",
            "expected_keywords": ["3"],
            "category": "hr_policy",
        },
        {
            "title": "GreenField Agriculture — Crop Yield Analysis 2025",
            "content": "GreenField Agriculture achieved a record corn yield of 215 bushels per acre "
                       "in the 2025 growing season, up from 198 bushels in 2024. The improvement "
                       "was attributed to the adoption of precision irrigation systems and "
                       "drought-resistant seed varieties developed by partner BioSeed Inc.",
            "query": "What was GreenField Agriculture's corn yield per acre in 2025?",
            "expected_keywords": ["215", "bushel"],
            "category": "agriculture",
        },
        {
            "title": "CyberShield Security Audit Report — March 2025",
            "content": "CyberShield conducted a comprehensive security audit of DataFlow Inc's "
                       "infrastructure in March 2025. The audit identified 14 critical vulnerabilities, "
                       "47 medium-risk issues, and 123 low-risk findings. The most severe vulnerability "
                       "was an unpatched Apache Struts instance exposed to the internet on port 8443.",
            "query": "How many critical vulnerabilities did CyberShield find in the DataFlow audit?",
            "expected_keywords": ["14"],
            "category": "security",
        },
        {
            "title": "Meridian Healthcare — Patient Satisfaction Survey Results",
            "content": "Meridian Healthcare's 2025 patient satisfaction survey achieved an overall "
                       "score of 4.6 out of 5.0 based on 12,500 respondents. Wait times averaged "
                       "22 minutes, down from 35 minutes in 2024. The emergency department scored "
                       "highest at 4.8, while billing and insurance received the lowest at 3.9.",
            "query": "What was the overall patient satisfaction score at Meridian Healthcare?",
            "expected_keywords": ["4.6"],
            "category": "healthcare",
        },
        {
            "title": "TerraLogistics — Fleet Electrification Plan",
            "content": "TerraLogistics announced its fleet electrification roadmap, targeting 60% "
                       "electric vehicles by 2028. The company will invest $230 million in 850 new "
                       "electric trucks and 45 charging stations across its North American distribution "
                       "network. Expected fuel cost savings are estimated at $18 million annually.",
            "query": "How much will TerraLogistics invest in fleet electrification?",
            "expected_keywords": ["230", "million"],
            "category": "logistics",
        },
        {
            "title": "CloudPeak SaaS — Monthly Active Users Report",
            "content": "CloudPeak SaaS platform reached 2.3 million monthly active users in January "
                       "2026, a 34% increase from July 2025. Enterprise customers now represent 41% "
                       "of total users. Average session duration increased to 47 minutes. The mobile "
                       "app accounts for 62% of all sessions.",
            "query": "How many monthly active users does CloudPeak have?",
            "expected_keywords": ["2.3", "million"],
            "category": "saas_metrics",
        },
        {
            "title": "Pinnacle Manufacturing — Quality Control Metrics",
            "content": "Pinnacle Manufacturing achieved a defect rate of 0.12% in Q4 2025, down "
                       "from 0.31% in Q4 2024. The improvement resulted from implementing AI-powered "
                       "visual inspection systems on 7 production lines. First-pass yield improved "
                       "to 98.7%. Customer returns decreased by 45%.",
            "query": "What was Pinnacle Manufacturing's defect rate in Q4 2025?",
            "expected_keywords": ["0.12"],
            "category": "manufacturing",
        },
        {
            "title": "EduBright — Online Learning Platform Curriculum Update",
            "content": "EduBright expanded its course catalog to 1,450 courses across 28 subject "
                       "areas in 2025. The platform added 320 new courses in AI and machine learning, "
                       "data science, and cybersecurity. Average course completion rate stands at 73%, "
                       "with certification programs seeing 89% completion.",
            "query": "How many total courses does EduBright offer?",
            "expected_keywords": ["1450", "1,450"],
            "category": "education",
        },
        {
            "title": "BlueWave Energy — Solar Farm Output Report",
            "content": "BlueWave Energy's Mojave Desert solar farm generated 412 GWh of electricity "
                       "in 2025, powering approximately 38,000 homes. The facility's capacity factor "
                       "reached 27.3%, exceeding the national average of 24.5%. Annual maintenance "
                       "costs were $4.2 million, a 15% reduction from the previous year.",
            "query": "How much electricity did BlueWave Energy's solar farm generate in 2025?",
            "expected_keywords": ["412", "gwh"],
            "category": "energy",
        },
        {
            "title": "UrbanMobility — Ride-Sharing Market Analysis",
            "content": "UrbanMobility's ride-sharing division completed 89 million trips in 2025, "
                       "capturing 23% of the North American market. Average fare was $14.50, with "
                       "an average trip distance of 6.8 miles. Driver retention improved to 78% "
                       "following the introduction of guaranteed minimum earnings of $22 per hour.",
            "query": "How many trips did UrbanMobility complete in 2025?",
            "expected_keywords": ["89", "million"],
            "category": "transportation",
        },
        {
            "title": "FreshHarvest — Supply Chain Sustainability Report",
            "content": "FreshHarvest reduced food waste in its supply chain by 32% in 2025, saving "
                       "an estimated 14,000 tons of produce from landfills. The company sources from "
                       "2,100 local farms within a 200-mile radius. Carbon emissions per delivery "
                       "dropped to 1.8 kg CO2e, down from 2.9 kg CO2e in 2023.",
            "query": "By what percentage did FreshHarvest reduce food waste in 2025?",
            "expected_keywords": ["32"],
            "category": "sustainability",
        },
        {
            "title": "DataVault Analytics — GDPR Compliance Status",
            "content": "DataVault Analytics completed its annual GDPR compliance review in December "
                       "2025. All 156 data processing activities were documented and approved. "
                       "Data subject access requests averaged 340 per month, with a mean response "
                       "time of 4.2 business days, well within the 30-day regulatory requirement.",
            "query": "How many data processing activities did DataVault document for GDPR?",
            "expected_keywords": ["156"],
            "category": "compliance",
        },
        {
            "title": "BioGenix Pharma — Clinical Trial Phase III Results",
            "content": "BioGenix Pharma's Phase III trial for drug candidate BGX-401 demonstrated "
                       "a 67% reduction in disease progression among 1,200 participants over 18 months. "
                       "The placebo group showed only 12% improvement. Adverse events were reported "
                       "in 8.3% of the treatment group, compared to 7.1% in the placebo group.",
            "query": "What reduction in disease progression did BGX-401 show in Phase III?",
            "expected_keywords": ["67"],
            "category": "pharma",
        },
        {
            "title": "RetailMax — Holiday Season Sales Analysis 2025",
            "content": "RetailMax reported holiday season sales of $1.2 billion, up 8% from 2024. "
                       "Online sales accounted for 54% of total revenue, with mobile purchases "
                       "growing 22% year-over-year. The average order value was $87. Returns "
                       "represented 11% of total sales, down from 14% in the prior year.",
            "query": "What were RetailMax's total holiday season sales in 2025?",
            "expected_keywords": ["1.2", "billion"],
            "category": "retail",
        },
        {
            "title": "AquaPure Water Treatment — Municipal Contract Report",
            "content": "AquaPure Water Treatment operates filtration systems for 23 municipalities "
                       "serving 4.7 million residents. In 2025, the company processed 890 billion "
                       "gallons of water with a 99.97% purity compliance rate. Infrastructure "
                       "upgrades totaling $67 million were completed across 8 facilities.",
            "query": "How many municipalities does AquaPure serve?",
            "expected_keywords": ["23"],
            "category": "utilities",
        },
        {
            "title": "FinEdge Capital — Portfolio Performance Review",
            "content": "FinEdge Capital's flagship Global Growth Fund returned 19.4% in 2025, "
                       "outperforming the benchmark S&P 500 by 3.2 percentage points. Assets "
                       "under management grew to $8.7 billion. The fund's Sharpe ratio was 1.42, "
                       "with maximum drawdown limited to 7.8%.",
            "query": "What was FinEdge Capital's Global Growth Fund return in 2025?",
            "expected_keywords": ["19.4"],
            "category": "finance",
        },
        {
            "title": "SpaceLink Communications — Satellite Deployment Update",
            "content": "SpaceLink Communications successfully deployed 144 low-earth orbit "
                       "satellites in 2025, bringing the total constellation to 512 active satellites. "
                       "Network latency averages 28 milliseconds globally. The company now provides "
                       "coverage to 94% of populated land areas with 99.5% uptime.",
            "query": "How many satellites does SpaceLink have in total?",
            "expected_keywords": ["512"],
            "category": "telecom",
        },
        {
            "title": "GourmetBox — Meal Kit Subscription Metrics",
            "content": "GourmetBox meal kit service grew to 890,000 active subscribers by end of "
                       "2025. Customer acquisition cost dropped to $38 from $52 in 2024. Monthly "
                       "churn rate stabilized at 4.2%. The average customer orders 3.1 boxes per "
                       "month with a lifetime value of $420.",
            "query": "How many active subscribers does GourmetBox have?",
            "expected_keywords": ["890000", "890,000"],
            "category": "subscription",
        },
        {
            "title": "ConstrucTech — Building Information Modeling Report",
            "content": "ConstrucTech deployed BIM technology on 78 construction projects in 2025, "
                       "reducing material waste by 25% and project timeline overruns by 33%. "
                       "The platform detected 4,200 clash conflicts before construction began, "
                       "saving an estimated $12 million in rework costs across all projects.",
            "query": "How many construction projects did ConstrucTech use BIM on in 2025?",
            "expected_keywords": ["78"],
            "category": "construction",
        },
    ]
    return docs

# ---------------------------------------------------------------------------
# Core test logic
# ---------------------------------------------------------------------------
def run_ingest_test(doc, test_id, idx, total):
    """
    Ingest a document and then query about it.
    Returns a result dict with pass/fail, latencies, and details.
    """
    result = {
        "test_id": test_id,
        "index": idx,
        "title": doc["title"],
        "category": doc["category"],
        "query": doc["query"],
        "expected_keywords": doc["expected_keywords"],
        "ingest_ok": False,
        "ingest_latency_ms": 0,
        "retrieve_ok": False,
        "retrieve_latency_ms": 0,
        "answer": "",
        "passed": False,
        "error": None,
    }

    # ---- Step 1: Ingest the document ----
    ingest_payload = {
        "documents": [
            {
                "id": test_id,
                "title": doc["title"],
                "content": doc["content"],
                "metadata": {
                    "source": "eval-ingestion",
                    "category": doc["category"],
                    "test_run": True,
                },
            }
        ],
        "tenant_id": "benchmark",
        "source": "eval-ingestion-pipeline",
    }

    print(f"  [{idx + 1}/{total}] Ingesting: {doc['title'][:55]}...", flush=True)
    ingest_resp = _post_json(INGESTION_URL, ingest_payload, timeout=120)

    if not ingest_resp["ok"]:
        result["error"] = f"Ingest failed: {ingest_resp['error']}"
        print(f"    {_red('[-]')} Ingest FAILED: {ingest_resp['error'][:80]}")
        return result

    result["ingest_ok"] = True
    result["ingest_latency_ms"] = ingest_resp["latency_ms"]
    print(f"    Ingested in {ingest_resp['latency_ms']}ms", flush=True)

    # Small delay to allow indexing to propagate
    time.sleep(3)

    # ---- Step 2: Query the standard RAG pipeline about the document ----
    query_payload = {
        "query": doc["query"],
        "tenant_id": "benchmark",
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True,
    }

    print(f"    Querying: {doc['query'][:55]}...", flush=True)
    rag_resp = _post_json(RAG_URL, query_payload, timeout=120)

    if not rag_resp["ok"]:
        result["error"] = f"Retrieve failed: {rag_resp['error']}"
        print(f"    {_red('[-]')} Retrieve FAILED: {rag_resp['error'][:80]}")
        return result

    result["retrieve_ok"] = True
    result["retrieve_latency_ms"] = rag_resp["latency_ms"]

    answer = _extract_answer(rag_resp["body"])
    result["answer"] = answer[:500]

    # ---- Step 3: Verify the answer contains expected keywords ----
    norm_answer = _normalize(answer)
    matched = []
    missing = []
    for kw in doc["expected_keywords"]:
        if _normalize(kw) in norm_answer:
            matched.append(kw)
        else:
            missing.append(kw)

    # Pass if at least one keyword matches (accounts for alternate number formats)
    if matched:
        result["passed"] = True
        print(f"    {_green('[+]')} PASS | {rag_resp['latency_ms']}ms | matched: {matched}")
    else:
        result["passed"] = False
        print(f"    {_red('[-]')} FAIL | {rag_resp['latency_ms']}ms | missing: {missing}")
        print(f"        Answer preview: {answer[:120]}")

    return result


def run_eval(args):
    """Main evaluation loop."""
    docs = _make_test_documents()
    max_tests = min(args.max, len(docs))
    test_docs = docs[:max_tests]

    # Generate run ID
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    run_id = f"ingestion-{run_ts}"

    print("=" * 65)
    print(_bold("  EVAL: DATA-INGESTION PIPELINE"))
    print("=" * 65)
    print(f"  N8N_HOST     : {N8N_HOST}")
    print(f"  Ingest URL   : {INGESTION_URL}")
    print(f"  RAG URL      : {RAG_URL}")
    print(f"  Tests        : {max_tests}")
    print(f"  Batch size   : {args.batch_size}")
    print(f"  Early stop   : {args.early_stop} consecutive failures")
    print(f"  Run ID       : {run_id}")
    print("=" * 65)
    print()

    results = []
    consecutive_fails = 0
    stopped_early = False
    batches_completed = 0

    start_time = time.time()

    for batch_start in range(0, max_tests, args.batch_size):
        batch_end = min(batch_start + args.batch_size, max_tests)
        batch_docs = test_docs[batch_start:batch_end]
        batch_num = (batch_start // args.batch_size) + 1
        total_batches = (max_tests + args.batch_size - 1) // args.batch_size

        print(f"\n--- Batch {batch_num}/{total_batches} (tests {batch_start + 1}-{batch_end}) ---\n")

        for i, doc in enumerate(batch_docs):
            global_idx = batch_start + i
            test_id = f"eval-{run_id}-{global_idx:03d}-{hashlib.md5(doc['title'].encode()).hexdigest()[:8]}"

            result = run_ingest_test(doc, test_id, global_idx, max_tests)
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

        batches_completed += 1

        if stopped_early:
            break

        # Inter-batch delay
        if batch_end < max_tests:
            print(f"\n  Batch complete. Pausing 5s before next batch...", flush=True)
            time.sleep(5)

    elapsed = time.time() - start_time

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    ingested = sum(1 for r in results if r["ingest_ok"])
    retrieved = sum(1 for r in results if r["retrieve_ok"])
    accuracy = (passed / total * 100) if total > 0 else 0.0

    avg_ingest_latency = 0
    ingest_latencies = [r["ingest_latency_ms"] for r in results if r["ingest_ok"]]
    if ingest_latencies:
        avg_ingest_latency = sum(ingest_latencies) / len(ingest_latencies)

    avg_retrieve_latency = 0
    retrieve_latencies = [r["retrieve_latency_ms"] for r in results if r["retrieve_ok"]]
    if retrieve_latencies:
        avg_retrieve_latency = sum(retrieve_latencies) / len(retrieve_latencies)

    # Category breakdown
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r["passed"]:
            categories[cat]["passed"] += 1

    print("\n" + "=" * 65)
    print(_bold("  RESULTS SUMMARY"))
    print("=" * 65)
    print(f"  Total tests      : {total}")
    print(f"  Ingested OK      : {ingested}/{total}")
    print(f"  Retrieved OK     : {retrieved}/{total}")
    print(f"  Answer correct   : {passed}/{total}")
    pct_color = _green if accuracy >= 70 else (_yellow if accuracy >= 50 else _red)
    print(f"  Accuracy         : {pct_color(f'{accuracy:.1f}%')}")
    print(f"  Avg ingest ms    : {avg_ingest_latency:.0f}")
    print(f"  Avg retrieve ms  : {avg_retrieve_latency:.0f}")
    print(f"  Elapsed          : {elapsed:.1f}s")
    if stopped_early:
        print(f"  {_red('STOPPED EARLY')}: {consecutive_fails} consecutive failures")
    print()

    if categories:
        print("  Category breakdown:")
        for cat, info in sorted(categories.items()):
            cat_pct = info["passed"] / info["total"] * 100 if info["total"] > 0 else 0
            print(f"    {cat:20s} : {info['passed']}/{info['total']} ({cat_pct:.0f}%)")
    print("=" * 65)

    # ---------------------------------------------------------------------------
    # Save JSON results
    # ---------------------------------------------------------------------------
    output = {
        "run_id": run_id,
        "pipeline": "ingestion",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n8n_host": N8N_HOST,
        "config": {
            "max": args.max,
            "batch_size": args.batch_size,
            "early_stop": args.early_stop,
        },
        "summary": {
            "total": total,
            "ingested": ingested,
            "retrieved": retrieved,
            "passed": passed,
            "accuracy_pct": round(accuracy, 2),
            "avg_ingest_latency_ms": round(avg_ingest_latency),
            "avg_retrieve_latency_ms": round(avg_retrieve_latency),
            "elapsed_seconds": round(elapsed, 1),
            "stopped_early": stopped_early,
            "consecutive_fails_at_stop": consecutive_fails if stopped_early else 0,
        },
        "categories": categories,
        "results": results,
    }

    out_filename = f"ingestion-{run_ts}.json"
    out_path = os.path.join(RESULTS_DIR, out_filename)

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results saved to: {out_path}")

    # Exit code
    if accuracy >= 50 and not stopped_early:
        print(f"\n  {_green('PASS')} — Ingestion pipeline operational (accuracy >= 50%)")
        return 0
    else:
        print(f"\n  {_red('FAIL')} — Ingestion pipeline needs attention")
        return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Eval: Data-Ingestion Pipeline — end-to-end ingest + retrieve tests"
    )
    parser.add_argument("--max", type=int, default=50,
                        help="Maximum number of test documents to process (default: 50)")
    parser.add_argument("--batch-size", type=int, default=5,
                        help="Documents per batch (default: 5)")
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
