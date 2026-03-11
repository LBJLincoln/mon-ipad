#!/usr/bin/env python3
"""
S5 — Activate Standard + Graph workflows with versionId.
The /activate endpoint requires {"versionId": "..."} in the body.
"""

import json
import ssl
import socket
import http.client
import time
import sys

# === IPv4 ===
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda *a, **k: [r for r in _orig(*a, **k) if r[0] == socket.AF_INET]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HOST = "lbjlincoln-nomos-rag-engine-5.hf.space"
EMAIL = "ci@nomos.ai"
PASSWORD = "CI-Nomos-2026!"

WORKFLOWS_TO_FIX = {
    "Standard": "TmgyRP20N4JFd9CB",
    "Graph": "6257AfT1l4FMC6lY",
}


def req(method, path, data=None, headers=None):
    if headers is None:
        headers = {}
    conn = http.client.HTTPSConnection(HOST, 443, context=ctx, timeout=90)
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    resp_body = resp.read().decode("utf-8", errors="replace")
    cookies = [v.split(";")[0] for h, v in resp.getheaders() if h.lower() == "set-cookie"]
    conn.close()
    return resp.status, resp_body, cookies


def main():
    # Login
    print("Logging in to S5...")
    status, body, cookies = req("POST", "/rest/login",
                                data={"emailOrLdapLoginId": EMAIL, "password": PASSWORD})
    if status != 200:
        print(f"Login failed: HTTP {status} — {body[:200]}")
        sys.exit(1)
    cookie = "; ".join(cookies)
    print(f"  OK")

    # Get workflow details and activate with versionId
    for name, wf_id in WORKFLOWS_TO_FIX.items():
        print(f"\n--- {name} ({wf_id}) ---")

        # GET workflow to obtain versionId
        status, body, _ = req("GET", f"/rest/workflows/{wf_id}", headers={"Cookie": cookie})
        if status != 200:
            print(f"  Cannot fetch: HTTP {status}")
            continue

        data = json.loads(body)
        wf = data.get("data", data)
        version_id = wf.get("versionId")
        active = wf.get("active", False)
        wf_name = wf.get("name", "?")
        nodes = len(wf.get("nodes", []))

        print(f"  Name: {wf_name}")
        print(f"  Active: {active}")
        print(f"  Nodes: {nodes}")
        print(f"  VersionId: {version_id}")

        if active:
            print(f"  Already active, skipping.")
            continue

        if not version_id:
            print(f"  ERROR: No versionId found!")
            continue

        # Activate with versionId
        print(f"  Activating with versionId={version_id}...")
        status, body, _ = req("POST", f"/rest/workflows/{wf_id}/activate",
                              data={"versionId": version_id},
                              headers={"Cookie": cookie})
        print(f"  Activate response: HTTP {status}")
        if status == 200:
            try:
                r = json.loads(body)
                print(f"  Result: active={r.get('data', {}).get('active', '?')}")
            except:
                print(f"  Body: {body[:200]}")
        else:
            print(f"  Error: {body[:300]}")

            # Alternative: PATCH workflow to set active=true
            print(f"\n  Trying alternative: PATCH workflow active=true...")
            patch_data = {"active": True, "versionId": version_id}
            status, body, _ = req("PATCH", f"/rest/workflows/{wf_id}",
                                  data=patch_data,
                                  headers={"Cookie": cookie})
            print(f"  PATCH response: HTTP {status}")
            if status == 200:
                try:
                    r = json.loads(body)
                    print(f"  Result: active={r.get('data', {}).get('active', '?')}")
                except:
                    print(f"  Body: {body[:200]}")
            else:
                print(f"  Error: {body[:300]}")

        time.sleep(1)

    # Wait for webhook registration
    print("\nWaiting 8s for webhook registration...")
    time.sleep(8)

    # Verify
    print("\n--- Verification ---")

    # Check workflow status
    for name, wf_id in WORKFLOWS_TO_FIX.items():
        status, body, _ = req("GET", f"/rest/workflows/{wf_id}", headers={"Cookie": cookie})
        if status == 200:
            data = json.loads(body)
            wf = data.get("data", data)
            print(f"  [{name}] active={wf.get('active')}")

    # Test webhooks
    print("\nTesting webhooks...")
    tests = [
        ("/webhook/rag-multi-index-v3", {"query": "ratio de solvabilite", "sector": "finance", "disable_acl": True}, "Standard"),
        ("/webhook/ff622742-6d71-4e91-af71-b5c666088717", {"query": "relations CAC 40", "sector": "finance", "disable_acl": True}, "Graph"),
    ]

    all_ok = True
    for path, payload, label in tests:
        start = time.time()
        status, body, _ = req("POST", path, data=payload)
        elapsed = time.time() - start

        if status == 200:
            try:
                parsed = json.loads(body)
                if isinstance(parsed, list) and parsed:
                    txt = parsed[0].get("response", "")[:100]
                elif isinstance(parsed, dict):
                    txt = str(parsed.get("response", parsed.get("output", "")))[:100]
                else:
                    txt = body[:100]
                print(f"  [{label}] PASS ({elapsed:.1f}s): {txt}")
            except:
                print(f"  [{label}] PASS ({elapsed:.1f}s)")
        else:
            print(f"  [{label}] FAIL — HTTP {status} ({elapsed:.1f}s): {body[:150]}")
            all_ok = False

    print(f"\n{'ALL WEBHOOKS WORKING' if all_ok else 'SOME WEBHOOKS STILL FAILING'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
