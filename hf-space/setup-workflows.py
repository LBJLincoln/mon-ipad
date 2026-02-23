#!/usr/bin/env python3
"""
HF Space n8n Setup v3 — Create credentials, update workflows, activate.

Works with CLI-pre-imported workflows (entrypoint.sh imports via n8n CLI
BEFORE n8n starts). This script:
  1. Creates credentials (Supabase, OpenRouter, Pinecone, Neo4j, Redis)
  2. Updates existing workflows to use new credential IDs
  3. Activates all workflows

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

    # --- Supabase PostgreSQL ---
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
            for old in ["USU8ngVzsUbED3mn", "zEr7jPswZNv6lWKu", "FZUFrHg9RgDR3MAB", "0bf5AHN9S8qJTBr8"]:
                id_map[old] = new_id
    else:
        print("  SKIP: Supabase PostgreSQL (no SUPABASE_PASSWORD)")

    # --- OpenRouter httpHeaderAuth ---
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
            for old in ["pHqLK3RCesLssL6j", "3DEiHDwB09D65919"]:
                id_map[old] = new_id
    else:
        print("  SKIP: Pinecone (no PINECONE_API_KEY)")

    # --- Neo4j Aura ---
    neo4j_auth = os.environ.get("NEO4J_AUTH", "")
    if neo4j_auth and (":" in neo4j_auth or "/" in neo4j_auth):
        sep = ":" if ":" in neo4j_auth else "/"
        neo4j_user, neo4j_pass = neo4j_auth.split(sep, 1)
        new_id = create_credential("Neo4j Aura", "httpBasicAuth", {
            "user": neo4j_user,
            "password": neo4j_pass,
        })
        if new_id:
            id_map["n4K6ZIj6aa0dsiGN"] = new_id
    else:
        print("  SKIP: Neo4j (no NEO4J_AUTH)")

    # --- Redis ---
    new_id = create_credential("Redis", "redis", {
        "host": os.environ.get("REDIS_HOST", "127.0.0.1"),
        "port": int(os.environ.get("REDIS_PORT", "6379")),
        "password": os.environ.get("REDIS_PASSWORD", ""),
    })
    if new_id:
        id_map["O2KEPiv7VzgDG5ZX"] = new_id

    print(f"  Credential ID mapping: {len(id_map)} entries")
    for old, new in id_map.items():
        print(f"    {old} -> {new}")
    return id_map


def update_existing_workflows(id_map):
    """Update credential IDs in all existing workflows (already in DB from CLI import)."""
    result = api("GET", "workflows?limit=100")
    if not result:
        print("  Could not list workflows for credential update")
        return 0

    wfs = result.get("data", result)
    if isinstance(wfs, dict) and "data" in wfs:
        wfs = wfs["data"]
    if not isinstance(wfs, list):
        print(f"  Unexpected workflow list format: {type(wfs)}")
        return 0

    updated = 0
    wf_id_map = {}  # old_workflow_id -> new_workflow_id (for sub-workflow remapping)

    # Build workflow ID map from what's in the database
    # Read original IDs from the JSON files to build the mapping
    for wf_path in sorted(glob.glob(os.path.join(WF_DIR, "*.json"))):
        try:
            with open(wf_path) as f:
                orig = json.load(f)
            orig_id = orig.get("id", "")
            orig_name = orig.get("name", "")
            # Find the matching workflow in the database by name
            for db_wf in wfs:
                if db_wf.get("name") == orig_name and orig_id:
                    wf_id_map[orig_id] = db_wf.get("id", "")
                    break
        except Exception:
            pass

    print(f"  Workflow ID mapping (orig->db): {len(wf_id_map)} entries")
    for old, new in wf_id_map.items():
        print(f"    {old} -> {new}")

    for wf in wfs:
        wid = wf.get("id", "")
        wname = wf.get("name", "?")

        # Get full workflow details (nodes included)
        full_wf = api("GET", f"workflows/{wid}")
        if not full_wf:
            print(f"  Could not get details for: {wname}")
            continue

        wf_data = full_wf.get("data", full_wf)
        if isinstance(wf_data, dict) and "data" in wf_data:
            wf_data = wf_data["data"]

        # Remap credential IDs
        needs_update = False
        nodes = wf_data.get("nodes", [])
        for node in nodes:
            creds = node.get("credentials", {})
            for ctype, cval in creds.items():
                if isinstance(cval, dict):
                    old_id = cval.get("id", "")
                    if old_id in id_map:
                        cval["id"] = id_map[old_id]
                        needs_update = True

            # Remap sub-workflow references
            if node.get("type") == "n8n-nodes-base.executeWorkflow":
                params = node.get("parameters", {})
                wf_ref = params.get("workflowId", {})
                if isinstance(wf_ref, dict):
                    old_sub_id = wf_ref.get("value", "")
                    if old_sub_id in wf_id_map:
                        wf_ref["value"] = wf_id_map[old_sub_id]
                        needs_update = True
                        print(f"    Remapped sub-workflow in {wname}: {old_sub_id} -> {wf_id_map[old_sub_id]}")
                elif isinstance(wf_ref, str) and wf_ref in wf_id_map:
                    params["workflowId"] = wf_id_map[wf_ref]
                    needs_update = True
                    print(f"    Remapped sub-workflow (str) in {wname}: {wf_ref} -> {wf_id_map[wf_ref]}")

        if needs_update:
            # Update the workflow via REST API
            update_data = {
                "nodes": nodes,
                "connections": wf_data.get("connections", {}),
                "settings": wf_data.get("settings", {}),
                "name": wname,
            }
            upd_result = api("PATCH", f"workflows/{wid}", update_data)
            if upd_result:
                print(f"  Updated credentials in: {wname}")
                updated += 1
            else:
                print(f"  FAILED to update: {wname}")
        else:
            print(f"  No credential changes needed: {wname}")

    print(f"  Credential update: {updated} workflows updated")
    return updated


def activate_all_workflows():
    """Activate all workflows via PATCH. Forces re-activation even if already active.

    n8n 2.9.x requires workflows to be PUBLISHED (not just active in DB).
    PATCH via REST API creates the published version, enabling webhook registration.
    SQLite active=1 alone creates "draft" workflows — webhooks won't register.
    """
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
    failed = 0
    for wf in wfs:
        wid = wf.get("id", "")
        wname = wf.get("name", "?")

        # ALWAYS PATCH — even if already active. This ensures the published version
        # is created, which is required for webhook registration in n8n 2.9.x.
        # First deactivate, then activate (forces n8n to create published version)
        api("PATCH", f"workflows/{wid}", {"active": False})
        act_result = api("PATCH", f"workflows/{wid}", {"active": True})
        if act_result:
            is_active = act_result.get("data", act_result).get("active", False)
            if is_active:
                print(f"    Activated: {wname}")
                activated += 1
            else:
                print(f"    PATCH OK but not active: {wname}")
                failed += 1
        else:
            print(f"    FAILED to activate: {wname}")
            failed += 1

    print(f"  Activation: {activated} new, {already} already, {failed} failed")
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

        # 200 or 405 (method not allowed = webhook exists but expects POST)
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

    print("\n=== [B] Updating workflows with new credential IDs ===")
    update_existing_workflows(id_map)

    print("\n=== [C] Activating workflows ===")
    time.sleep(3)  # Let n8n settle
    activate_all_workflows()

    print("\n=== [D] Verifying webhooks ===")
    time.sleep(2)
    verify_webhooks()

    print("\n=== SETUP COMPLETE ===")
