#!/bin/bash
# Simple test of continuous monitor - single ping only

source /home/termius/mon-ipad/.env.local

python3 - << 'PYEOF'
import json
import time
from urllib import request, error

space = "https://lbjlincoln-nomos-rag-engine.hf.space"
path = "/webhook/rag-multi-index-v3"
query = "What is the capital of Japan?"

url = space + path
payload = json.dumps({"query": query, "tenant_id": "monitor", "benchmark_mode": True}).encode()
headers = {"Content-Type": "application/json"}

print(f"Testing: {url}")
start = time.time()
try:
    req = request.Request(url, data=payload, headers=headers, method="POST")
    with request.urlopen(req, timeout=90) as resp:
        latency = int((time.time() - start) * 1000)
        raw = resp.read().decode()
        print(f"OK - Latency: {latency}ms, Response: {len(raw)} chars")
except Exception as e:
    print(f"ERROR: {e}")
PYEOF
