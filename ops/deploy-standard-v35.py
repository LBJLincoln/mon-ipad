#!/usr/bin/env python3
"""Deploy Standard RAG V3.5 Expert Mode to S1, S3, S5 and test with 4 sector questions."""

import json
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

# === Force IPv4 ===
_original_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    responses = _original_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET] or responses
socket.getaddrinfo = _ipv4_only_getaddrinfo

# === Config ===
WORKFLOW_ID = "TmgyRP20N4JFd9CB"
N8N_PASSWORD = "CI-Nomos-2026!"
N8N_EMAIL = "ci@nomos.ai"

SPACES = {
    "S1": "https://lbjlincoln-nomos-rag-engine.hf.space",
    "S2": "https://lbjlincoln26-nomos-rag-engine-2.hf.space",
    "S3": "https://lbjlincoln-nomos-rag-engine-3.hf.space",
    "S4": "https://lbjlincoln26-nomos-rag-engine-4.hf.space",
    "S5": "https://lbjlincoln-nomos-rag-engine-5.hf.space",
    "S9": "https://lbjlincoln-nomos-rag-engine-9.hf.space",
}

# SSL context that skips verification for HF spaces
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def http_request(url, method="GET", data=None, headers=None, cookie=None):
    """Make HTTP request with cookie auth."""
    if headers is None:
        headers = {}
    headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        set_cookie = resp.headers.get("Set-Cookie", "")
        resp_data = resp.read().decode("utf-8")
        return resp.status, resp_data, set_cookie
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8") if e.fp else ""
        return e.code, body_err, ""
    except Exception as e:
        return 0, str(e), ""

def login(base_url):
    """Login to n8n and get session cookie."""
    url = f"{base_url}/rest/login"
    data = {"emailOrLdapLoginId": N8N_EMAIL, "password": N8N_PASSWORD}
    status, body, set_cookie = http_request(url, method="POST", data=data)

    if status == 200:
        # Extract session cookie
        cookies = []
        if set_cookie:
            for part in set_cookie.split(","):
                for item in part.split(";"):
                    item = item.strip()
                    if "=" in item and not any(k in item.lower() for k in ["path", "expires", "max-age", "domain", "secure", "httponly", "samesite"]):
                        cookies.append(item)
        cookie_str = "; ".join(cookies) if cookies else set_cookie.split(";")[0] if set_cookie else ""
        print(f"  Login OK, cookie: {cookie_str[:50]}...")
        return cookie_str
    else:
        print(f"  Login FAILED ({status}): {body[:200]}")
        return None

def deploy_workflow(base_url, cookie, workflow_json):
    """Deploy workflow via PATCH, then activate."""
    # Step 1: PATCH workflow
    url = f"{base_url}/rest/workflows/{WORKFLOW_ID}"

    # Prepare the payload - only send nodes and connections
    payload = {
        "name": workflow_json["name"],
        "nodes": workflow_json["nodes"],
        "connections": workflow_json["connections"],
        "settings": workflow_json.get("settings", {}),
    }

    status, body, _ = http_request(url, method="PATCH", data=payload, cookie=cookie)
    if status != 200:
        print(f"  PATCH FAILED ({status}): {body[:300]}")
        return False

    print(f"  PATCH OK")

    # Step 2: GET workflow to get versionId
    status, body, _ = http_request(url, method="GET", cookie=cookie)
    if status != 200:
        print(f"  GET versionId FAILED ({status}): {body[:200]}")
        return False

    wf_data = json.loads(body)
    # n8n wraps response in "data" key
    inner = wf_data.get("data", wf_data)
    version_id = inner.get("versionId")
    print(f"  versionId: {version_id}")

    if not version_id:
        print("  WARNING: No versionId found, trying to activate anyway")

    # Step 3: POST activate
    activate_url = f"{base_url}/rest/workflows/{WORKFLOW_ID}/activate"
    activate_data = {}
    if version_id:
        activate_data["versionId"] = version_id

    status, body, _ = http_request(activate_url, method="POST", data=activate_data, cookie=cookie)
    if status in (200, 201):
        print(f"  ACTIVATE OK")
        return True
    else:
        print(f"  ACTIVATE ({status}): {body[:200]}")
        # Try without versionId if it failed
        if version_id:
            status2, body2, _ = http_request(activate_url, method="POST", data={}, cookie=cookie)
            if status2 in (200, 201):
                print(f"  ACTIVATE (retry) OK")
                return True
        return status == 200

def test_query(base_url, question, sector):
    """Send a test query and return the response."""
    url = f"{base_url}/webhook/rag-multi-index-v3"
    data = {
        "query": question,
        "user_context": {"tenant_id": "benchmark", "groups": ["admin"]},
        "disable_acl": True,
    }

    start = time.time()
    status, body, _ = http_request(url, method="POST", data=data)
    elapsed = time.time() - start

    if status == 200:
        try:
            resp = json.loads(body)
            # n8n webhook may return a list
            if isinstance(resp, list):
                resp = resp[0] if resp else {}
            answer = resp.get("response", "")
            sources = resp.get("sources", [])
            version = resp.get("version", "unknown")
            return {
                "status": "OK",
                "sector": sector,
                "answer_preview": answer[:300],
                "answer_length": len(answer),
                "sources_count": len(sources),
                "sources_names": [s.get("source", "?") for s in sources[:5]],
                "latency_s": round(elapsed, 1),
                "version": version,
                "has_citations": "[Source" in answer or "[source" in answer or "Source:" in answer,
                "in_french": any(w in answer.lower() for w in ["le ", "la ", "les ", "des ", "une ", "est ", "sont "]),
            }
        except json.JSONDecodeError:
            return {"status": "JSON_ERROR", "body": body[:200], "latency_s": round(elapsed, 1)}
    else:
        return {"status": f"HTTP_{status}", "body": body[:200], "latency_s": round(elapsed, 1)}


# === MAIN ===
if __name__ == "__main__":
    print("=" * 70)
    print("DEPLOY Standard RAG V3.5 Expert Mode")
    print("=" * 70)

    # Load workflow JSON
    with open("/home/termius/mon-ipad/n8n/live/standard-rag-v3.4-fixed.json", "r") as f:
        workflow_json = json.load(f)

    print(f"\nWorkflow: {workflow_json['name']}")
    print(f"Nodes: {len(workflow_json['nodes'])}")

    # Deploy to each space
    deploy_results = {}
    for space_name, base_url in SPACES.items():
        print(f"\n--- Deploying to {space_name} ({base_url}) ---")

        cookie = login(base_url)
        if not cookie:
            deploy_results[space_name] = "LOGIN_FAILED"
            continue

        success = deploy_workflow(base_url, cookie, workflow_json)
        deploy_results[space_name] = "OK" if success else "FAILED"

    print(f"\n{'=' * 70}")
    print("DEPLOYMENT RESULTS:")
    for space, result in deploy_results.items():
        status_icon = "PASS" if result == "OK" else "FAIL"
        print(f"  {space}: {status_icon} ({result})")

    # Wait for workflows to initialize
    print(f"\nWaiting 5s for workflows to initialize...")
    time.sleep(5)

    # Test with 4 sector questions
    TEST_QUESTIONS = [
        ("Quels sont les principaux ratios financiers pour evaluer la solvabilite d'une entreprise selon les normes IFRS?", "Finance"),
        ("Quelles sont les exigences du DTU 13.3 pour les dallages en beton sur terre-plein?", "BTP"),
        ("Quelles sont les conditions de la responsabilite contractuelle en droit francais?", "Juridique"),
        ("Comment mettre en place une demarche AMDEC dans un processus de fabrication industrielle?", "Industrie"),
    ]

    # Use S1 for testing
    test_base = SPACES["S1"]
    print(f"\n{'=' * 70}")
    print(f"TESTING on {test_base}")
    print(f"{'=' * 70}")

    test_results = []
    for question, sector in TEST_QUESTIONS:
        print(f"\n--- {sector} ---")
        print(f"Q: {question[:80]}...")
        result = test_query(test_base, question, sector)
        test_results.append(result)

        if result["status"] == "OK":
            print(f"  Status: OK | Length: {result['answer_length']} chars | Sources: {result['sources_count']} | Latency: {result['latency_s']}s")
            print(f"  Citations: {'YES' if result['has_citations'] else 'NO'} | French: {'YES' if result['in_french'] else 'NO'}")
            print(f"  Sources: {result['sources_names']}")
            print(f"  Answer: {result['answer_preview'][:200]}...")
        else:
            print(f"  Status: {result['status']}")
            print(f"  Body: {result.get('body', 'N/A')[:200]}")

    # Summary
    print(f"\n{'=' * 70}")
    print("TEST SUMMARY:")
    ok_count = sum(1 for r in test_results if r["status"] == "OK")
    cite_count = sum(1 for r in test_results if r.get("has_citations", False))
    fr_count = sum(1 for r in test_results if r.get("in_french", False))
    print(f"  Queries OK: {ok_count}/4")
    print(f"  With citations: {cite_count}/4")
    print(f"  In French: {fr_count}/4")
    avg_len = sum(r.get("answer_length", 0) for r in test_results if r["status"] == "OK") / max(ok_count, 1)
    print(f"  Avg answer length: {avg_len:.0f} chars (was ~50-100, target 300+)")
    avg_lat = sum(r.get("latency_s", 0) for r in test_results) / len(test_results)
    print(f"  Avg latency: {avg_lat:.1f}s")
    print(f"{'=' * 70}")
