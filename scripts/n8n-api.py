#!/usr/bin/env python3
"""
n8n REST API helper — authenticates via session cookie (not API key).

Usage:
  python3 scripts/n8n-api.py list              # List all workflows
  python3 scripts/n8n-api.py get <wf_id>       # Get workflow details
  python3 scripts/n8n-api.py deploy <file>     # Deploy a local JSON to matching workflow
  python3 scripts/n8n-api.py activate <wf_id>  # Deactivate + reactivate (registers webhooks)
  python3 scripts/n8n-api.py test-webhooks     # Test all known webhook endpoints

Auth: Uses CI credentials from entrypoint.sh defaults.
      Override with N8N_CI_EMAIL / N8N_CI_PASSWORD env vars.
"""
import urllib.request, urllib.error, json, http.cookiejar, os, sys, time

HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
CI_EMAIL = os.environ.get("N8N_CI_EMAIL", "ci@nomos.ai")
CI_PASSWORD = os.environ.get("N8N_CI_PASSWORD", "CI-Nomos-2026!")

KNOWN_WEBHOOKS = {
    "Standard": "webhook/rag-multi-index-v3",
    "Graph": "webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "Quantitative": "webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "Orchestrator": "webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
    "Ingestion": "webhook/rag-v6-ingestion",
    "Enrichment": "webhook/rag-v6-enrichment",
    "PME Gateway": "webhook/pme-assistant-gateway",
    "Benchmark Ingest": "webhook/benchmark-ingest",
}


def get_opener():
    """Login and return authenticated opener."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = json.dumps({"emailOrLdapLoginId": CI_EMAIL, "password": CI_PASSWORD}).encode()
    req = urllib.request.Request(f"{HOST}/rest/login", data=data,
                                headers={"Content-Type": "application/json"}, method="POST")
    opener.open(req, timeout=20)
    return opener


def api_get(opener, path, timeout=20):
    req = urllib.request.Request(f"{HOST}/rest{path}", method="GET")
    resp = opener.open(req, timeout=timeout)
    data = json.loads(resp.read().decode())
    return data.get("data", data)


def api_patch(opener, path, body, timeout=30):
    req = urllib.request.Request(f"{HOST}/rest{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="PATCH")
    resp = opener.open(req, timeout=timeout)
    data = json.loads(resp.read().decode())
    return data.get("data", data)


def api_post(opener, path, body=None, timeout=20):
    req = urllib.request.Request(f"{HOST}/rest{path}",
        data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    resp = opener.open(req, timeout=timeout)
    return json.loads(resp.read().decode())


def cmd_list(opener):
    workflows = api_get(opener, "/workflows?limit=50")
    if isinstance(workflows, dict):
        workflows = workflows.get("data", [])
    print(f"{'ID':25s} {'Active':8s} Name")
    print("-" * 70)
    for w in workflows:
        print(f"{w['id']:25s} {str(w.get('active', '?')):8s} {w['name'][:50]}")


def cmd_get(opener, wf_id):
    wf = api_get(opener, f"/workflows/{wf_id}")
    print(f"Name: {wf.get('name')}")
    print(f"Active: {wf.get('active')}")
    print(f"VersionId: {wf.get('versionId')}")
    print(f"Nodes: {len(wf.get('nodes', []))}")
    triggers = [n for n in wf.get("nodes", [])
                if "trigger" in n.get("type", "").lower() or "webhook" in n.get("type", "").lower()]
    for t in triggers:
        path = t.get("parameters", {}).get("path", "")
        print(f"  Trigger: {t['name']} ({t['type']}) path={path}")


def cmd_deploy(opener, filepath):
    with open(filepath) as f:
        wf_json = json.load(f)

    # Try to match by workflow name or ID
    all_wfs = api_get(opener, "/workflows?limit=50")
    if isinstance(all_wfs, dict):
        all_wfs = all_wfs.get("data", [])

    wf_name = wf_json.get("name", "")
    wf_id = wf_json.get("id", "")

    target = None
    for w in all_wfs:
        if w["id"] == wf_id or w["name"] == wf_name:
            target = w
            break

    if not target:
        print(f"No matching workflow found for '{wf_name}' (id={wf_id})")
        print("Available workflows:")
        for w in all_wfs:
            print(f"  {w['id']} — {w['name']}")
        return

    print(f"Deploying to: {target['id']} — {target['name']}")
    patch = {"nodes": wf_json["nodes"], "connections": wf_json["connections"]}
    result = api_patch(opener, f"/workflows/{target['id']}", patch)
    vid = result.get("versionId")
    print(f"  Updated, versionId={vid}")

    # Reactivate to register webhooks
    api_patch(opener, f"/workflows/{target['id']}", {"active": False, "versionId": vid})
    time.sleep(2)
    try:
        api_post(opener, f"/workflows/{target['id']}/activate", {"versionId": vid})
        print(f"  Reactivated (webhooks registered)")
    except urllib.error.HTTPError:
        api_patch(opener, f"/workflows/{target['id']}", {"active": True, "versionId": vid})
        print(f"  Reactivated via PATCH fallback")


def cmd_activate(opener, wf_id):
    wf = api_get(opener, f"/workflows/{wf_id}")
    vid = wf.get("versionId")
    print(f"Toggling: {wf.get('name')} (versionId={vid})")
    api_patch(opener, f"/workflows/{wf_id}", {"active": False, "versionId": vid})
    time.sleep(2)
    try:
        api_post(opener, f"/workflows/{wf_id}/activate", {"versionId": vid})
        print("  Activated via POST (webhooks registered)")
    except urllib.error.HTTPError:
        api_patch(opener, f"/workflows/{wf_id}", {"active": True, "versionId": vid})
        print("  Activated via PATCH fallback")


def cmd_exec(opener, exec_id=None, wf_id=None):
    """Show execution details node by node."""
    if exec_id:
        data = api_get(opener, f"/executions/{exec_id}", timeout=30)
    else:
        # Get latest for workflow
        all_execs = api_get(opener, f"/executions?limit=5", timeout=15)
        results = all_execs.get("results", all_execs) if isinstance(all_execs, dict) else all_execs
        if wf_id:
            results = [e for e in results if e.get("workflowId") == wf_id]
        if not results:
            print("No executions found")
            return
        exec_id = results[0]["id"]
        print(f"Latest execution: {exec_id} ({results[0].get('workflowName','?')})")
        data = api_get(opener, f"/executions/{exec_id}", timeout=30)

    ed = data if isinstance(data, dict) else data
    # Handle compressed format
    if isinstance(ed.get("data"), list):
        print("Compressed execution format — saving raw to /tmp/n8n-exec-raw.json")
        with open("/tmp/n8n-exec-raw.json", "w") as f:
            json.dump(ed, f)
        return

    rd = ed.get("resultData", {}).get("runData", {})
    print(f"\nNodes executed: {len(rd)}")
    for node_name, runs in rd.items():
        if not runs or not runs[0]:
            print(f"  SKIP | {node_name}")
            continue
        run = runs[0]
        main = run.get("data", {}).get("main", [[]])
        items = main[0] if main and main[0] else []
        err = run.get("error")
        n = len(items) if items else 0
        tag = "ERR" if err else "OK "
        print(f"  {tag} | {node_name:45s} | {n} items")
        if err:
            msg = err.get("message", str(err))[:200] if isinstance(err, dict) else str(err)[:200]
            print(f"        error: {msg}")
        if n > 0:
            j = items[0].get("json", {})
            for k in ["answer", "error", "response", "hyde_query", "results_count",
                       "neo4j_results", "pinecone_results", "embedding_error",
                       "status", "context_sources", "question"]:
                if k in j:
                    v = str(j[k])[:150]
                    print(f"        {k}: {v}")


def cmd_test_webhooks():
    print(f"Testing webhooks on {HOST}...\n")
    for name, path in KNOWN_WEBHOOKS.items():
        try:
            data = json.dumps({"query": "health-check", "test": True}).encode()
            req = urllib.request.Request(f"{HOST}/{path}", data=data,
                                        headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=10)
            print(f"  {name:20s} HTTP {resp.status} OK")
        except urllib.error.HTTPError as e:
            status = "REGISTERED" if e.code == 500 else "NOT FOUND" if e.code == 404 else f"ERROR {e.code}"
            print(f"  {name:20s} HTTP {e.code} — {status}")
        except Exception as e:
            print(f"  {name:20s} ERROR — {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "test-webhooks":
        cmd_test_webhooks()
        sys.exit(0)

    opener = get_opener()

    if cmd == "list":
        cmd_list(opener)
    elif cmd == "get" and len(sys.argv) > 2:
        cmd_get(opener, sys.argv[2])
    elif cmd == "deploy" and len(sys.argv) > 2:
        cmd_deploy(opener, sys.argv[2])
    elif cmd == "activate" and len(sys.argv) > 2:
        cmd_activate(opener, sys.argv[2])
    elif cmd == "exec":
        eid = sys.argv[2] if len(sys.argv) > 2 else None
        wfid = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_exec(opener, exec_id=eid, wf_id=wfid)
    else:
        print(__doc__)
