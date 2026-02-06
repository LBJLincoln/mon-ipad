#!/usr/bin/env python3
"""Deploy fixed Graph RAG and Quantitative RAG workflows to n8n cloud.
Fixes applied:
- Graph RAG: Split Response Formatter into Context Builder + HTTP Request (with openRouterApi cred) + Answer Formatter
- Quantitative RAG: Error-safe SQL Validator, error-path-aware Response Formatter
"""
import json, os, copy, time
from urllib import request, error
from datetime import datetime

N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"
REPO = "/home/user/mon-ipad"

ALLOWED_SETTINGS = {"executionOrder", "errorWorkflow", "callerPolicy",
                    "saveDataErrorExecution", "saveDataSuccessExecution",
                    "saveManualExecutions", "saveExecutionProgress",
                    "executionTimeout", "timezone"}

TARGETS = [
    ("TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED (1).json",
     ["95x2BBAbJlLWZtWEJn6rb"],
     "Graph RAG V3.3"),
    ("TEST - SOTA 2026 - WF4 Quantitative V2.0 (1).json",
     ["LjUz8fxQZ03G9IsU", "xrzL7TRX9F0UrWks0tdCI"],
     "Quantitative V2.0"),
]


def api(method, endpoint, data=None):
    url = f"{N8N_HOST}/api/v1{endpoint}"
    headers = {"X-N8N-API-KEY": N8N_API_KEY, "Accept": "application/json",
               "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as resp:
            return {"ok": True, "data": json.loads(resp.read().decode())}
    except error.HTTPError as e:
        err = ""
        try: err = e.read().decode()[:500]
        except: pass
        return {"ok": False, "code": e.code, "error": err}
    except Exception as e:
        return {"ok": False, "code": 0, "error": str(e)}


def prepare(wf):
    p = {}
    for k in ("name", "nodes", "connections", "settings"):
        if k in wf:
            p[k] = copy.deepcopy(wf[k])
    if "settings" in p:
        p["settings"] = {k: v for k, v in p["settings"].items() if k in ALLOWED_SETTINGS}
    for n in p.get("nodes", []):
        for k in list(n.keys()):
            if k.startswith('_'):
                del n[k]
    return p


def deploy_one(filepath, wf_id, name):
    print(f"\n  [{name}] Deploying to {wf_id}")
    with open(filepath) as f:
        wf = json.load(f)
    prepared = prepare(wf)

    # Deactivate
    print(f"  [{name}] Deactivating...")
    api("POST", f"/workflows/{wf_id}/deactivate")
    time.sleep(1)

    # Update
    print(f"  [{name}] Updating ({len(prepared.get('nodes',[]))} nodes)...")
    r = api("PUT", f"/workflows/{wf_id}", prepared)
    if r["ok"]:
        print(f"  [{name}] Updated: {r['data'].get('name','?')}")
    else:
        print(f"  [{name}] UPDATE FAILED: {r.get('code')} {r.get('error','')[:200]}")
        return False
    time.sleep(1)

    # Activate
    print(f"  [{name}] Activating...")
    a = api("POST", f"/workflows/{wf_id}/activate")
    if a["ok"]:
        print(f"  [{name}] Active: {a['data'].get('active','?')}")
    else:
        print(f"  [{name}] Activation warning: {a.get('error','')[:200]}")
    time.sleep(1)
    return True


if __name__ == "__main__":
    print("=" * 60)
    print(f"  DEPLOYING FIXED WORKFLOWS - {datetime.now().isoformat()}")
    print("=" * 60)

    ok = 0
    fail = 0

    for fname, ids, name in TARGETS:
        path = os.path.join(REPO, fname)
        if not os.path.exists(path):
            print(f"\n  SKIP: {fname} not found")
            continue

        for wf_id in ids:
            if deploy_one(path, wf_id, name):
                ok += 1
            else:
                fail += 1
            time.sleep(2)

    print(f"\n{'=' * 60}")
    print(f"  DONE: {ok} OK, {fail} FAILED")
    print(f"{'=' * 60}")
