#!/usr/bin/env python3
"""Quick test for continuous-monitor.py webhook calls."""
import json
import sys
import time
from urllib import request, error

def test_webhook():
    """Test a single webhook call."""
    space = "https://lbjlincoln-nomos-rag-engine.hf.space"
    path = "/webhook/rag-multi-index-v3"
    query = "What is the capital of Japan?"

    url = space + path
    payload = json.dumps({
        "query": query,
        "tenant_id": "monitor",
        "benchmark_mode": True,
    }).encode()
    headers = {"Content-Type": "application/json"}

    print(f"Testing: {url}")
    print(f"Query: {query}")

    try:
        req = request.Request(url, data=payload, headers=headers, method="POST")
        start = time.time()
        with request.urlopen(req, timeout=30) as resp:
            latency = int((time.time() - start) * 1000)
            raw = resp.read().decode()
            print(f"Latency: {latency}ms")
            print(f"Response length: {len(raw)} chars")
            if raw:
                data = json.loads(raw)
                print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                # Try to extract answer
                if isinstance(data, list):
                    data = data[0] if data else {}
                for key in ["response", "answer", "result", "interpretation", "final_response"]:
                    if key in data and data[key]:
                        print(f"Answer ({key}): {str(data[key])[:200]}")
                        return True
                print("No answer found in response")
                return False
            else:
                print("Empty response")
                return False
    except error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()[:200]}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = test_webhook()
    sys.exit(0 if success else 1)
