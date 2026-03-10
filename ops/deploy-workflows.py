#!/usr/bin/env python3
"""Deploy n8n workflows to HF Space via REST API.

Handles:
1. Enrichment (existing, ID=ORa01sX4xI0iRCJ8) — PUT/PATCH update
2. Auto-Healer (new) — POST create

Uses cookie-based auth as fallback since n8n on HF uses HTTP/2 proxy.
"""

import json
import os
import sys
import http.cookiejar
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time

# ─── Config ───
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")
N8N_EMAIL = "ci@nomos.ai"
N8N_PASSWORD = "CI-Nomos-2026!"

ENRICHMENT_FILE = "/home/termius/mon-ipad/n8n/live/enrichment.json"
AUTOHEALER_FILE = "/home/termius/mon-ipad/n8n/live/auto-healer.json"

# ─── SSL context (permissive for HF proxy) ───
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ─── Cookie jar for session auth ───
cookie_jar = http.cookiejar.MozillaCookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookie_jar),
    urllib.request.HTTPSHandler(context=ctx)
)


def api_request(method, path, data=None, use_api_key=True):
    """Make an HTTP request to n8n API."""
    url = f"{N8N_HOST}{path}"
    headers = {"Content-Type": "application/json"}

    if use_api_key and N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY

    body = json.dumps(data).encode("utf-8") if data else None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        resp = opener.open(req, timeout=30)
        resp_body = resp.read().decode("utf-8")
        return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(resp_body)
        except json.JSONDecodeError:
            return e.code, {"error": resp_body[:500]}
    except Exception as e:
        return 0, {"error": str(e)}


def login_session():
    """Login to n8n web UI and get session cookie."""
    print("\n[AUTH] Logging in via session cookie...")

    login_data = {
        "emailOrLdapLoginId": N8N_EMAIL,
        "password": N8N_PASSWORD
    }

    status, resp = api_request("POST", "/rest/login", login_data, use_api_key=False)

    if status == 200:
        print(f"[AUTH] Login SUCCESS — session cookie acquired")
        return True
    else:
        print(f"[AUTH] Login FAILED — HTTP {status}: {resp}")
        return False


def prepare_workflow_for_update(wf_data):
    """Strip fields that n8n API rejects on update."""
    # Only keep fields that n8n accepts for PUT/PATCH
    allowed_keys = ["name", "nodes", "connections", "settings", "staticData", "active"]
    return {k: wf_data[k] for k in allowed_keys if k in wf_data}


def prepare_workflow_for_create(wf_data):
    """Prepare workflow for POST creation."""
    # Tags must be excluded or converted — n8n REST rejects object tags
    allowed_keys = ["name", "nodes", "connections", "settings", "active"]
    result = {k: wf_data[k] for k in allowed_keys if k in wf_data}
    # Force active=False on create — we activate separately after
    result["active"] = False
    return result


def deploy_enrichment(use_cookie=False):
    """Deploy enrichment workflow (existing — update)."""
    print("\n" + "="*60)
    print("[ENRICHMENT] Deploying: TEST - SOTA 2026 - Enrichissement V4.0")
    print(f"[ENRICHMENT] Workflow ID: ORa01sX4xI0iRCJ8")
    print("="*60)

    with open(ENRICHMENT_FILE) as f:
        wf_data = json.load(f)

    wf_id = wf_data["id"]
    update_data = prepare_workflow_for_update(wf_data)

    # Strategy 1: PUT /api/v1/workflows/{id}
    print("\n[ENRICHMENT] Strategy 1: PUT /api/v1/workflows/{id}...")
    status, resp = api_request("PUT", f"/api/v1/workflows/{wf_id}", update_data, use_api_key=not use_cookie)
    print(f"[ENRICHMENT] PUT → HTTP {status}")

    if status == 200:
        print(f"[ENRICHMENT] PUT SUCCESS!")
        return True, resp

    print(f"[ENRICHMENT] PUT failed: {json.dumps(resp, indent=2)[:300]}")

    # Strategy 2: PATCH /api/v1/workflows/{id}
    print("\n[ENRICHMENT] Strategy 2: PATCH /api/v1/workflows/{id}...")
    status, resp = api_request("PATCH", f"/api/v1/workflows/{wf_id}", update_data, use_api_key=not use_cookie)
    print(f"[ENRICHMENT] PATCH → HTTP {status}")

    if status == 200:
        print(f"[ENRICHMENT] PATCH SUCCESS!")
        return True, resp

    print(f"[ENRICHMENT] PATCH failed: {json.dumps(resp, indent=2)[:300]}")

    # Strategy 3: REST endpoint (cookie-based) — PUT /rest/workflows/{id}
    if use_cookie:
        print("\n[ENRICHMENT] Strategy 3: PUT /rest/workflows/{id} (cookie auth)...")
        # For /rest/ endpoint, we need to include versionId
        rest_data = dict(update_data)
        if "versionId" in wf_data:
            rest_data["versionId"] = wf_data["versionId"]
        status, resp = api_request("PUT", f"/rest/workflows/{wf_id}", rest_data, use_api_key=False)
        print(f"[ENRICHMENT] REST PUT → HTTP {status}")

        if status == 200:
            print(f"[ENRICHMENT] REST PUT SUCCESS!")
            return True, resp

        print(f"[ENRICHMENT] REST PUT failed: {json.dumps(resp, indent=2)[:300]}")

        # Strategy 4: PATCH /rest/workflows/{id}
        print("\n[ENRICHMENT] Strategy 4: PATCH /rest/workflows/{id} (cookie auth)...")
        status, resp = api_request("PATCH", f"/rest/workflows/{wf_id}", rest_data, use_api_key=False)
        print(f"[ENRICHMENT] REST PATCH → HTTP {status}")

        if status == 200:
            print(f"[ENRICHMENT] REST PATCH SUCCESS!")
            return True, resp

        print(f"[ENRICHMENT] REST PATCH failed: {json.dumps(resp, indent=2)[:300]}")

    return False, resp


def deploy_autohealer(use_cookie=False):
    """Deploy auto-healer workflow (new — create)."""
    print("\n" + "="*60)
    print("[AUTO-HEALER] Creating: Auto-Healer V1.0 — LLM Analyzer + Sandbox Test")
    print("="*60)

    with open(AUTOHEALER_FILE) as f:
        wf_data = json.load(f)

    create_data = prepare_workflow_for_create(wf_data)

    # Strategy 1: POST /api/v1/workflows
    print("\n[AUTO-HEALER] Strategy 1: POST /api/v1/workflows...")
    status, resp = api_request("POST", "/api/v1/workflows", create_data, use_api_key=not use_cookie)
    print(f"[AUTO-HEALER] POST → HTTP {status}")

    if status in (200, 201):
        new_id = resp.get("id", "unknown")
        print(f"[AUTO-HEALER] POST SUCCESS! New ID: {new_id}")
        return True, resp

    print(f"[AUTO-HEALER] POST failed: {json.dumps(resp, indent=2)[:300]}")

    # Strategy 2: REST endpoint (cookie-based) — POST /rest/workflows
    if use_cookie:
        print("\n[AUTO-HEALER] Strategy 2: POST /rest/workflows (cookie auth)...")
        status, resp = api_request("POST", "/rest/workflows", create_data, use_api_key=False)
        print(f"[AUTO-HEALER] REST POST → HTTP {status}")

        if status in (200, 201):
            new_id = resp.get("id", resp.get("data", {}).get("id", "unknown"))
            print(f"[AUTO-HEALER] REST POST SUCCESS! New ID: {new_id}")
            return True, resp

        print(f"[AUTO-HEALER] REST POST failed: {json.dumps(resp, indent=2)[:300]}")

    return False, resp


def activate_workflow(wf_id, name, use_cookie=False):
    """Activate a workflow by ID."""
    print(f"\n[ACTIVATE] Activating {name} ({wf_id})...")

    # First get versionId (required for n8n 2.8+)
    status, resp = api_request("GET", f"/api/v1/workflows/{wf_id}", use_api_key=not use_cookie)

    if status != 200:
        # Try REST endpoint
        if use_cookie:
            status, resp = api_request("GET", f"/rest/workflows/{wf_id}", use_api_key=False)
        if status != 200:
            print(f"[ACTIVATE] Cannot fetch workflow {wf_id}: HTTP {status}")
            return False

    version_id = resp.get("versionId", resp.get("data", {}).get("versionId"))

    # Activate via PATCH
    activate_data = {"active": True}
    if version_id:
        activate_data["versionId"] = version_id

    status, resp = api_request("PATCH", f"/api/v1/workflows/{wf_id}", activate_data, use_api_key=not use_cookie)
    print(f"[ACTIVATE] PATCH → HTTP {status}")

    if status == 200:
        print(f"[ACTIVATE] {name} ACTIVATED!")
        return True

    # Try REST activate
    if use_cookie:
        print(f"[ACTIVATE] Trying REST PATCH...")
        status, resp = api_request("PATCH", f"/rest/workflows/{wf_id}", activate_data, use_api_key=False)
        print(f"[ACTIVATE] REST PATCH → HTTP {status}")
        if status == 200:
            print(f"[ACTIVATE] {name} ACTIVATED via REST!")
            return True

    # Try POST /rest/workflows/{id}/activate
    if use_cookie:
        print(f"[ACTIVATE] Trying POST /rest/workflows/{id}/activate...")
        act_data = {}
        if version_id:
            act_data["versionId"] = version_id
        status, resp = api_request("POST", f"/rest/workflows/{wf_id}/activate", act_data, use_api_key=False)
        print(f"[ACTIVATE] POST activate → HTTP {status}")
        if status == 200:
            print(f"[ACTIVATE] {name} ACTIVATED via POST!")
            return True

    print(f"[ACTIVATE] Failed to activate {name}: {resp}")
    return False


def main():
    print("="*60)
    print("n8n Workflow Deployer — HF Space")
    print(f"Target: {N8N_HOST}")
    print(f"API Key: {'SET' if N8N_API_KEY else 'NOT SET'}")
    print("="*60)

    results = {}

    # ─── Phase 1: Try with API key ───
    print("\n[PHASE 1] Attempting deployment with API key...")

    enrichment_ok, enrichment_resp = deploy_enrichment(use_cookie=False)
    autohealer_ok, autohealer_resp = deploy_autohealer(use_cookie=False)

    # ─── Phase 2: If any failed, try with session cookie ───
    need_cookie = not enrichment_ok or not autohealer_ok

    if need_cookie:
        print("\n[PHASE 2] Some deployments failed — trying cookie-based auth...")
        logged_in = login_session()

        if logged_in:
            if not enrichment_ok:
                enrichment_ok, enrichment_resp = deploy_enrichment(use_cookie=True)

            if not autohealer_ok:
                autohealer_ok, autohealer_resp = deploy_autohealer(use_cookie=True)

    results["enrichment"] = {
        "success": enrichment_ok,
        "id": "ORa01sX4xI0iRCJ8",
        "name": "TEST - SOTA 2026 - Enrichissement V4.0"
    }

    autohealer_id = None
    if autohealer_ok:
        autohealer_id = autohealer_resp.get("id", autohealer_resp.get("data", {}).get("id"))

    results["auto_healer"] = {
        "success": autohealer_ok,
        "id": autohealer_id,
        "name": "Auto-Healer V1.0"
    }

    # ─── Phase 3: Activate workflows ───
    print("\n" + "="*60)
    print("[PHASE 3] Activating workflows...")
    print("="*60)

    use_cookie_for_activate = need_cookie

    if enrichment_ok:
        activate_workflow("ORa01sX4xI0iRCJ8", "Enrichment", use_cookie=use_cookie_for_activate)

    if autohealer_ok and autohealer_id:
        activate_workflow(autohealer_id, "Auto-Healer", use_cookie=use_cookie_for_activate)

    # ─── Summary ───
    print("\n" + "="*60)
    print("DEPLOYMENT SUMMARY")
    print("="*60)

    for name, r in results.items():
        status_str = "SUCCESS" if r["success"] else "FAILED"
        print(f"  {r['name']}: {status_str} (ID: {r['id']})")

    overall = all(r["success"] for r in results.values())
    print(f"\nOverall: {'ALL DEPLOYED' if overall else 'PARTIAL FAILURE'}")

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
