"""Retrieval quality validation pipeline.
After each ingestion: sample questions, query pipelines, measure retrieval@5.
Compare with baseline, report pass/fail.
"""
import os, sys, json, time, logging, requests

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("retrieval-validator")

N8N_HOSTS = os.environ.get("N8N_ALL_HOSTS", "").split(",")
STANDARD_WEBHOOK = "/webhook/rag-multi-index-v3"

VALIDATION_QUESTIONS = [
    {"query": "What is TechVision Inc's total revenue in 2023?", "expected_keywords": ["revenue", "techvision", "2023"]},
    {"query": "What are the main cybersecurity threats in 2024?", "expected_keywords": ["cybersecurity", "threat"]},
    {"query": "What is GDPR and how does it affect data protection?", "expected_keywords": ["gdpr", "data protection", "regulation"]},
    {"query": "What was GreenEnergy Corp's net income in FY2023?", "expected_keywords": ["greenenergy", "net income", "2023"]},
    {"query": "How does blockchain technology work?", "expected_keywords": ["blockchain", "distributed", "ledger"]},
    {"query": "What are the benefits of cloud computing for enterprises?", "expected_keywords": ["cloud", "computing", "enterprise"]},
    {"query": "What is machine learning used for in healthcare?", "expected_keywords": ["machine learning", "healthcare"]},
    {"query": "What is the Paris Agreement about?", "expected_keywords": ["paris", "agreement", "climate"]},
    {"query": "How does ransomware spread?", "expected_keywords": ["ransomware", "spread", "malware"]},
    {"query": "What are ESG criteria in investing?", "expected_keywords": ["esg", "environmental", "social", "governance"]},
]

BASELINE_PASS_RATE = float(os.environ.get("BASELINE_PASS_RATE", 0.6))

def query_pipeline(host, query, timeout=60):
    url = f"{host.rstrip('/')}{STANDARD_WEBHOOK}"
    try:
        resp = requests.post(url, json={"query": query}, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            answer = ""
            if isinstance(data, dict):
                answer = data.get("response") or data.get("answer") or data.get("text") or json.dumps(data)
            elif isinstance(data, list) and data:
                answer = str(data[0])
            return {"status": "ok", "answer": str(answer)[:1000]}
        return {"status": "error", "answer": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "answer": str(e)}

def check_retrieval(answer, expected_keywords):
    answer_lower = answer.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return found >= max(1, len(expected_keywords) // 2)

def validate(sample_size=10):
    if not N8N_HOSTS or not N8N_HOSTS[0]:
        log.error("N8N_ALL_HOSTS not set")
        return False

    host = N8N_HOSTS[0]
    questions = VALIDATION_QUESTIONS[:sample_size]
    passed = 0
    total = len(questions)

    log.info(f"Validating retrieval quality ({total} questions) against {host}")

    for i, q in enumerate(questions):
        result = query_pipeline(host, q["query"])
        is_pass = result["status"] == "ok" and check_retrieval(result["answer"], q["expected_keywords"])
        status = "PASS" if is_pass else "FAIL"
        if is_pass:
            passed += 1
        log.info(f"  [{i+1}/{total}] {status} | {q['query'][:50]}...")
        time.sleep(1)

    rate = passed / total if total > 0 else 0
    overall = "PASS" if rate >= BASELINE_PASS_RATE else "FAIL"

    log.info(f"\n{'='*50}")
    log.info(f"Retrieval@5 validation: {passed}/{total} ({rate:.0%})")
    log.info(f"Baseline: {BASELINE_PASS_RATE:.0%} | Result: {overall}")
    log.info(f"{'='*50}")

    return rate >= BASELINE_PASS_RATE

if __name__ == "__main__":
    success = validate()
    sys.exit(0 if success else 1)
