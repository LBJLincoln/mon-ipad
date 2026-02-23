#!/usr/bin/env python3
"""
HF Space n8n Setup — Create credentials, import workflows, activate.
Called by entrypoint.sh after n8n is healthy and logged in.

Usage: python3 setup-workflows.py <cookie> <base_url>
"""
import json, os, sys, time, glob
import urllib.request
import urllib.error

COOKIE = sys.argv[1] if len(sys.argv) > 1 else ""
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:7860"
WF_DIR = "/app/n8n-workflows"

def api(method, path, data=None):
    """Make authenticated n8n REST API call."""
    url = f"{BASE}/rest/{path.lstrip('/')}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", f"n8n-auth={COOKIE}")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  API {method} {path}: HTTP {e.code} — {body}")
        return None
    except Exception as e:
        print(f"  API {method} {path}: ERROR — {e}")
        return None


def create_credential(name, cred_type, cred_data):
    """Create an n8n credential and return its ID."""
    result = api("POST", "credentials", {
        "name": name,
        "type": cred_type,
        "data": cred_data,
    })
    if result:
        cid = result.get("data", result).get("id", result.get("id", ""))
        if cid:
            print(f"  Created credential: {name} (type={cred_type}, id={cid})")
            return str(cid)
    print(f"  FAILED to create credential: {name}")
    return None


def create_all_credentials():
    """Create all required n8n credentials. Returns mapping old_id -> new_id."""
    id_map = {}

    # --- Supabase PostgreSQL (Pooler) — used by standard, graph, quantitative ---
    supabase_host = os.environ.get("SUPABASE_HOST", "aws-0-eu-west-1.pooler.supabase.com")
    supabase_port = int(os.environ.get("SUPABASE_PORT", "6543"))
    supabase_db = os.environ.get("SUPABASE_DB", "postgres")
    supabase_user = os.environ.get("SUPABASE_USER", "postgres.kfyrtsmdolgioyxsglbz")
    supabase_pass = os.environ.get("SUPABASE_PASSWORD", "")

    if supabase_pass:
        new_id = create_credential("Supabase Postgres (Pooler)", "postgres", {
            "host": supabase_host,
            "port": supabase_port,
            "database": supabase_db,
            "user": supabase_user,
            "password": supabase_pass,
            "ssl": "allow",
        })
        if new_id:
            # Map all old Supabase credential IDs to the new one
            id_map["USU8ngVzsUbED3mn"] = new_id  # Supabase Postgres (Pooler)
            id_map["zEr7jPswZNv6lWKu"] = new_id  # Supabase PostgreSQL
            id_map["FZUFrHg9RgDR3MAB"] = new_id  # Postgres Production
            id_map["0bf5AHN9S8qJTBr8"] = new_id  # Postgres account
    else:
        print("  SKIP: Supabase PostgreSQL (no SUPABASE_PASSWORD)")

    # --- OpenRouter httpHeaderAuth — for PME workflows ---
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        new_id = create_credential("OpenRouter API", "httpHeaderAuth", {
            "name": "Authorization",
            "value": f"Bearer {or_key}",
        })
        if new_id:
            id_map["OPENROUTER_HEADER_AUTH"] = new_id
    else:
        print("  SKIP: OpenRouter httpHeaderAuth (no OPENROUTER_API_KEY)")

    # --- Pinecone API Key ---
    pc_key = os.environ.get("PINECONE_API_KEY", "")
    if pc_key:
        new_id = create_credential("Pinecone API Key", "httpHeaderAuth", {
            "name": "Api-Key",
            "value": pc_key,
        })
        if new_id:
            id_map["pHqLK3RCesLssL6j"] = new_id
            id_map["3DEiHDwB09D65919"] = new_id
    else:
        print("  SKIP: Pinecone (no PINECONE_API_KEY)")

    # --- Neo4j Aura ---
    neo4j_auth = os.environ.get("NEO4J_AUTH", "")
    if neo4j_auth and ":" in neo4j_auth:
        neo4j_user, neo4j_pass = neo4j_auth.split(":", 1)
        new_id = create_credential("Neo4j Aura", "httpBasicAuth", {
            "user": neo4j_user,
            "password": neo4j_pass,
        })
        if new_id:
            id_map["n4K6ZIj6aa0dsiGN"] = new_id
    else:
        print("  SKIP: Neo4j (no NEO4J_AUTH)")

    print(f"  Credential ID mapping: {len(id_map)} entries")
    return id_map


def remap_and_import_workflows(id_map):
    """Import workflow JSONs with credential IDs remapped.

    Import order matters: Standard/Graph/Quantitative first,
    then Orchestrator (which references them as sub-workflows).
    """
    imported = 0
    failed = 0
    wf_id_map = {}  # old_workflow_id -> new_workflow_id (for sub-workflow remapping)

    wf_files = sorted(glob.glob(os.path.join(WF_DIR, "*.json")))

    # Import orchestrator LAST (it references other workflows)
    orchestrator_files = []
    other_files = []
    for wf_path in wf_files:
        fname = os.path.basename(wf_path)
        if 'orchestrator' in fname.lower():
            orchestrator_files.append(wf_path)
        else:
            other_files.append(wf_path)

    ordered_files = other_files + orchestrator_files

    for wf_path in ordered_files:
        fname = os.path.basename(wf_path)
        with open(wf_path) as f:
            wf_data = json.load(f)

        old_wf_id = wf_data.get("id", "")

        # Remap credential IDs in all nodes
        remapped = 0
        for node in wf_data.get("nodes", []):
            creds = node.get("credentials", {})
            for ctype, cval in creds.items():
                if isinstance(cval, dict):
                    old_id = cval.get("id", "")
                    if old_id in id_map:
                        cval["id"] = id_map[old_id]
                        remapped += 1

            # Remap sub-workflow references (executeWorkflow nodes)
            if node.get("type") == "n8n-nodes-base.executeWorkflow":
                params = node.get("parameters", {})
                wf_ref = params.get("workflowId", {})
                if isinstance(wf_ref, dict):
                    old_sub_id = wf_ref.get("value", "")
                    if old_sub_id in wf_id_map:
                        wf_ref["value"] = wf_id_map[old_sub_id]
                        print(f"    Remapped sub-workflow: {old_sub_id} -> {wf_id_map[old_sub_id]}")

        # Import via REST API
        result = api("POST", "workflows", wf_data)
        if result:
            new_wf = result.get("data", result)
            new_wf_id = new_wf.get("id", "?")
            wf_name = new_wf.get("name", fname)
            print(f"    Imported: {wf_name} (id={new_wf_id}, {remapped} creds remapped)")
            imported += 1

            # Record ID mapping for sub-workflow remapping
            if old_wf_id:
                wf_id_map[old_wf_id] = new_wf_id
        else:
            print(f"    FAILED: {fname}")
            failed += 1

    print(f"  Import complete: {imported} OK, {failed} failed")
    print(f"  Workflow ID mapping: {len(wf_id_map)} entries")
    return imported


def activate_all_workflows():
    """Activate all inactive workflows."""
    result = api("GET", "workflows?limit=100")
    if not result:
        print("  Could not list workflows")
        return 0

    wfs = result.get("data", result)
    if isinstance(wfs, dict) and "data" in wfs:
        wfs = wfs["data"]
    if not isinstance(wfs, list):
        print(f"  Unexpected workflow list format: {type(wfs)}")
        return 0

    activated = 0
    for wf in wfs:
        wid = wf.get("id", "")
        wname = wf.get("name", "?")
        wactive = wf.get("active", False)
        wversion = wf.get("versionId", "")

        if not wactive:
            act_result = api("POST", f"workflows/{wid}/activate", {"versionId": wversion})
            if act_result:
                print(f"    Activated: {wname}")
                activated += 1
            else:
                print(f"    FAILED to activate: {wname}")
        else:
            print(f"    Already active: {wname}")

    print(f"  Activation complete: {activated} newly activated, {len(wfs)} total")
    return activated


def verify_webhooks():
    """Verify webhook endpoints respond."""
    webhooks = {
        "Standard": "webhook/rag-multi-index-v3",
        "Graph": "webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "Quantitative": "webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "Orchestrator": "webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
        "PME Gateway": "webhook/pme-assistant-gateway",
    }

    print("  Webhook verification:")
    ok = 0
    for name, path in webhooks.items():
        url = f"{BASE}/{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            code = resp.status
        except urllib.error.HTTPError as e:
            code = e.code
        except:
            code = 0

        status = "OK" if code in (200, 405) else "FAIL"
        if status == "OK":
            ok += 1
        print(f"    {name}: HTTP {code} ({status})")

    print(f"  Webhooks: {ok}/{len(webhooks)} responding")
    return ok


if __name__ == "__main__":
    if not COOKIE:
        print("ERROR: No auth cookie provided")
        sys.exit(1)

    print("\n=== [A] Creating credentials ===")
    id_map = create_all_credentials()

    print("\n=== [B] Importing workflows (with credential remap) ===")
    imported = remap_and_import_workflows(id_map)

    print("\n=== [C] Activating workflows ===")
    time.sleep(3)  # Let n8n settle
    activate_all_workflows()

    print("\n=== [D] Verifying webhooks ===")
    time.sleep(2)
    verify_webhooks()

    print("\n=== SETUP COMPLETE ===")
