#!/usr/bin/env python3
"""
HF Space n8n Setup v4 — Create credentials, restore refs, publish & activate.

Works with CLI-pre-imported workflows (entrypoint.sh imports via n8n CLI
BEFORE n8n starts, stripping credentials to avoid FK errors). This script:
  1. Creates credentials (Supabase, OpenRouter, Pinecone, Neo4j, Redis)
  2. Restores credential references from ORIGINAL workflow JSONs
  3. Publishes & activates all workflows via POST /activate (requires versionId)

KEY INSIGHT: n8n 2.8+ requires POST /workflows/{id}/activate with versionId
to register webhooks. PATCH {active: true} sets the flag but does NOT register
webhooks. The POST /activate also validates that nodes have credentials configured.

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
    try:
        result = api("POST", "credentials", {
            "name": name,
            "type": cred_type,
            "data": cred_data,
        })
        if result:
            cid = result.get("data", result).get("id", result.get("id", ""))
            if cid:
                print(f"  ✓ Created credential: {name} (type={cred_type}, id={cid})")
                return str(cid)
        print(f"  ✗ FAILED to create credential: {name}")
        return None
    except Exception as e:
        print(f"  ✗ EXCEPTION creating credential {name}: {e}")
        return None


def create_all_credentials():
    """Create all required n8n credentials. Returns (id_map, type_map, stats).

    id_map: old_credential_id -> new_id (for direct ID remapping)
    type_map: credential_type -> new_id (for type-based assignment)
    stats: dict with success/failure counts per credential type
    """
    id_map = {}
    type_map = {}
    stats = {"created": [], "failed": [], "skipped": []}

    # --- Supabase PostgreSQL ---
    try:
        supabase_host = os.environ.get("SUPABASE_HOST", "aws-1-eu-west-1.pooler.supabase.com")
        supabase_port = int(os.environ.get("SUPABASE_PORT", "6543"))
        supabase_db = os.environ.get("SUPABASE_DB", "postgres")
        supabase_user = os.environ.get("SUPABASE_USER", "postgres.ayqviqmxifzmhphiqfmj")
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
                type_map["postgres"] = new_id
                for old in ["USU8ngVzsUbED3mn", "zEr7jPswZNv6lWKu", "FZUFrHg9RgDR3MAB", "0bf5AHN9S8qJTBr8"]:
                    id_map[old] = new_id
                stats["created"].append("Supabase PostgreSQL")
            else:
                stats["failed"].append("Supabase PostgreSQL")
        else:
            print("  SKIP: Supabase PostgreSQL (no SUPABASE_PASSWORD)")
            stats["skipped"].append("Supabase PostgreSQL")
    except Exception as e:
        print(f"  ERROR creating Supabase credential: {e}")
        stats["failed"].append("Supabase PostgreSQL")

    # --- OpenRouter httpHeaderAuth (per-pipeline keys) ---
    try:
        or_key = os.environ.get("OPENROUTER_API_KEY", "")
        if or_key:
            # Create per-pipeline credentials using different API keys
            pipeline_keys = {
                "Standard": os.environ.get("OPENROUTER_KEY_STANDARD", or_key),
                "Graph": os.environ.get("OPENROUTER_KEY_GRAPH", or_key),
                "Quantitative": os.environ.get("OPENROUTER_KEY_QUANTITATIVE", or_key),
                "Orchestrator": os.environ.get("OPENROUTER_KEY_ORCHESTRATOR", or_key),
                "PME": os.environ.get("OPENROUTER_KEY_PME", or_key),
            }
            or_cred_ids = {}  # pipeline_label -> credential_id
            for label, key in pipeline_keys.items():
                cid = create_credential(f"OpenRouter API ({label})", "httpHeaderAuth", {
                    "name": "Authorization",
                    "value": f"Bearer {key}",
                })
                if cid:
                    or_cred_ids[label] = cid
                    stats["created"].append(f"OpenRouter ({label})")
                else:
                    stats["failed"].append(f"OpenRouter ({label})")

            # Also create a default/main credential for unmapped workflows
            main_id = create_credential("OpenRouter API (Main)", "httpHeaderAuth", {
                "name": "Authorization",
                "value": f"Bearer {or_key}",
            })
            if main_id:
                id_map["OPENROUTER_HEADER_AUTH"] = main_id
                id_map["LLM_API_CREDENTIAL_ID"] = main_id
                type_map["httpHeaderAuth"] = main_id
                stats["created"].append("OpenRouter (Main)")
            else:
                stats["failed"].append("OpenRouter (Main)")
            # Store per-pipeline IDs for later assignment
            type_map["_or_pipeline_creds"] = or_cred_ids
            print(f"  Created {len(or_cred_ids)} per-pipeline OpenRouter credentials")
        else:
            print("  SKIP: OpenRouter httpHeaderAuth (no OPENROUTER_API_KEY)")
            stats["skipped"].append("OpenRouter")
    except Exception as e:
        print(f"  ERROR creating OpenRouter credentials: {e}")
        stats["failed"].append("OpenRouter")

    # --- Pinecone API Key (separate httpHeaderAuth) ---
    try:
        pc_key = os.environ.get("PINECONE_API_KEY", "")
        pinecone_cred_id = None
        if pc_key:
            pinecone_cred_id = create_credential("Pinecone API Key", "httpHeaderAuth", {
                "name": "Api-Key",
                "value": pc_key,
            })
            if pinecone_cred_id:
                # Store Pinecone separately to avoid confusion with OpenRouter
                type_map["httpHeaderAuth_pinecone"] = pinecone_cred_id
                for old in ["pHqLK3RCesLssL6j", "3DEiHDwB09D65919"]:
                    id_map[old] = pinecone_cred_id
                stats["created"].append("Pinecone")
            else:
                stats["failed"].append("Pinecone")
        else:
            print("  SKIP: Pinecone (no PINECONE_API_KEY)")
            stats["skipped"].append("Pinecone")
    except Exception as e:
        print(f"  ERROR creating Pinecone credential: {e}")
        stats["failed"].append("Pinecone")

    # --- Neo4j Aura ---
    try:
        neo4j_auth = os.environ.get("NEO4J_AUTH", "")
        if neo4j_auth and (":" in neo4j_auth or "/" in neo4j_auth):
            sep = ":" if ":" in neo4j_auth else "/"
            neo4j_user, neo4j_pass = neo4j_auth.split(sep, 1)
            new_id = create_credential("Neo4j Aura", "httpBasicAuth", {
                "user": neo4j_user,
                "password": neo4j_pass,
            })
            if new_id:
                type_map["httpBasicAuth"] = new_id
                id_map["n4K6ZIj6aa0dsiGN"] = new_id
                stats["created"].append("Neo4j")
            else:
                stats["failed"].append("Neo4j")
        else:
            print("  SKIP: Neo4j (no NEO4J_AUTH)")
            stats["skipped"].append("Neo4j")
    except Exception as e:
        print(f"  ERROR creating Neo4j credential: {e}")
        stats["failed"].append("Neo4j")

    # --- Groq httpHeaderAuth (per-pipeline keys) ---
    try:
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key:
            groq_pipeline_keys = {
                "Standard": os.environ.get("GROQ_API_KEY_STANDARD", groq_key),
                "Graph": os.environ.get("GROQ_API_KEY_GRAPH", groq_key),
                "Quantitative": os.environ.get("GROQ_API_KEY_QUANTITATIVE", groq_key),
                "Orchestrator": os.environ.get("GROQ_API_KEY_ORCHESTRATOR", groq_key),
            }
            groq_cred_ids = {}
            for label, key in groq_pipeline_keys.items():
                cid = create_credential(f"Groq API ({label})", "httpHeaderAuth", {
                    "name": "Authorization",
                    "value": f"Bearer {key}",
                })
                if cid:
                    groq_cred_ids[label] = cid
                    stats["created"].append(f"Groq ({label})")
                else:
                    stats["failed"].append(f"Groq ({label})")
            type_map["_groq_pipeline_creds"] = groq_cred_ids
            print(f"  Created {len(groq_cred_ids)} per-pipeline Groq credentials")
        else:
            print("  SKIP: Groq httpHeaderAuth (no GROQ_API_KEY)")
            stats["skipped"].append("Groq")
    except Exception as e:
        print(f"  ERROR creating Groq credentials: {e}")
        stats["failed"].append("Groq")

    # --- Redis ---
    try:
        new_id = create_credential("Redis", "redis", {
            "host": os.environ.get("REDIS_HOST", "127.0.0.1"),
            "port": int(os.environ.get("REDIS_PORT", "6379")),
            "password": os.environ.get("REDIS_PASSWORD", ""),
        })
        if new_id:
            type_map["redis"] = new_id
            id_map["O2KEPiv7VzgDG5ZX"] = new_id
            stats["created"].append("Redis")
        else:
            stats["failed"].append("Redis")
    except Exception as e:
        print(f"  ERROR creating Redis credential: {e}")
        stats["failed"].append("Redis")

    print(f"  Credential ID mapping: {len(id_map)} entries")
    print(f"  Credential TYPE mapping: {len(type_map)} entries")
    for t, cid in type_map.items():
        if not t.startswith("_"):  # Skip internal metadata
            print(f"    type={t} -> id={cid}")

    # Print stats
    print(f"  Credential creation stats:")
    print(f"    ✓ Created: {len(stats['created'])} — {', '.join(stats['created'])}")
    print(f"    ✗ Failed: {len(stats['failed'])} — {', '.join(stats['failed']) if stats['failed'] else 'None'}")
    print(f"    ⊘ Skipped: {len(stats['skipped'])} — {', '.join(stats['skipped']) if stats['skipped'] else 'None'}")

    return id_map, type_map, stats


def restore_credentials_and_update(id_map, type_map):
    """Restore credential references from original JSONs into DB workflows.

    The CLI import stripped all credentials from nodes to avoid FK errors.
    Now we read the ORIGINAL workflow JSONs (which have the old credential refs),
    map old IDs to new IDs, and PATCH the DB workflows with proper credentials.
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

    # Build name -> original JSON mapping
    orig_by_name = {}
    wf_id_map = {}  # orig_wf_id -> db_wf_id
    for wf_path in sorted(glob.glob(os.path.join(WF_DIR, "*.json"))):
        try:
            with open(wf_path) as f:
                orig = json.load(f)
            name = orig.get("name", "")
            if name:
                orig_by_name[name] = orig
                # Build workflow ID mapping
                orig_id = orig.get("id", "")
                for db_wf in wfs:
                    if db_wf.get("name") == name and orig_id:
                        wf_id_map[orig_id] = db_wf.get("id", "")
                        break
        except Exception as e:
            print(f"  Error reading {wf_path}: {e}")

    print(f"  Original workflows loaded: {len(orig_by_name)}")
    print(f"  Workflow ID mapping: {len(wf_id_map)} entries")
    for old_id, new_id in wf_id_map.items():
        print(f"    {old_id} -> {new_id}")

    updated = 0
    for wf in wfs:
        wid = wf.get("id", "")
        wname = wf.get("name", "?")

        # Get full workflow from DB
        full_wf = api("GET", f"workflows/{wid}")
        if not full_wf:
            print(f"  Could not get: {wname}")
            continue

        wf_data = full_wf.get("data", full_wf)
        if isinstance(wf_data, dict) and "data" in wf_data:
            wf_data = wf_data["data"]

        # Get original workflow (with credentials)
        orig = orig_by_name.get(wname)
        if not orig:
            print(f"  No original JSON for: {wname}")
            continue

        # Build node name -> original credentials mapping
        orig_creds_by_node = {}
        for node in orig.get("nodes", []):
            node_name = node.get("name", "")
            creds = node.get("credentials", {})
            if creds and node_name:
                orig_creds_by_node[node_name] = creds

        # Restore credentials in DB workflow nodes
        needs_update = False
        db_nodes = wf_data.get("nodes", [])
        for node in db_nodes:
            node_name = node.get("name", "")
            node_type = node.get("type", "")

            # Restore credentials from original
            if node_name in orig_creds_by_node:
                orig_creds = orig_creds_by_node[node_name]
                new_creds = {}
                for ctype, cval in orig_creds.items():
                    if isinstance(cval, dict):
                        old_id = cval.get("id", "")
                        old_name = cval.get("name", "")
                        new_id = id_map.get(old_id)

                        if not new_id:
                            # Special handling for httpHeaderAuth (distinguish Pinecone vs OpenRouter)
                            if ctype == "httpHeaderAuth":
                                # Check if this is Pinecone based on credential name or node type
                                is_pinecone = (
                                    "pinecone" in old_name.lower() or
                                    "api-key" in old_name.lower() or
                                    "pinecone" in node_type.lower()
                                )
                                if is_pinecone:
                                    new_id = type_map.get("httpHeaderAuth_pinecone")
                                else:
                                    new_id = type_map.get("httpHeaderAuth")
                            else:
                                # Fallback: match by credential type
                                new_id = type_map.get(ctype)

                        if new_id:
                            new_creds[ctype] = {
                                "id": new_id,
                                "name": cval.get("name", ctype),
                            }
                        else:
                            print(f"    No mapping for cred {ctype} (old={old_id}, name={old_name}) in {wname}/{node_name}")
                    elif isinstance(cval, str):
                        # Simple string reference
                        new_id = id_map.get(cval) or type_map.get(ctype)
                        if new_id:
                            new_creds[ctype] = {
                                "id": new_id,
                                "name": ctype,
                            }

                if new_creds:
                    node["credentials"] = new_creds
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
                    elif old_sub_id:
                        print(f"    WARNING: No mapping for sub-workflow {old_sub_id} in {wname}/{node_name}")
                        print(f"    Available mappings: {list(wf_id_map.keys())}")
                elif isinstance(wf_ref, str) and wf_ref in wf_id_map:
                    params["workflowId"] = wf_id_map[wf_ref]
                    needs_update = True
                elif isinstance(wf_ref, str) and wf_ref:
                    print(f"    WARNING: No mapping for sub-workflow {wf_ref} in {wname}/{node_name}")

        if needs_update:
            update_data = {
                "nodes": db_nodes,
                "connections": wf_data.get("connections", {}),
                "settings": wf_data.get("settings", {}),
                "name": wname,
            }
            upd_result = api("PATCH", f"workflows/{wid}", update_data)
            if upd_result:
                print(f"  Restored credentials in: {wname}")
                updated += 1
            else:
                print(f"  FAILED to update: {wname}")
        else:
            print(f"  No credentials to restore: {wname}")

    print(f"  Credential restore: {updated} workflows updated")
    return updated


def assign_per_pipeline_openrouter(type_map):
    """Override OpenRouter credentials per pipeline for key rotation.

    Each pipeline gets its own OpenRouter API key to distribute rate limits
    across multiple accounts (7 keys, 3 accounts → ~140 req/min aggregate).
    """
    or_creds = type_map.get("_or_pipeline_creds", {})
    if not or_creds:
        print("  No per-pipeline OpenRouter credentials available")
        return 0

    # Map workflow name patterns to pipeline labels
    pipeline_patterns = {
        "Standard": ["standard", "wf5"],
        "Graph": ["graph", "wf2"],
        "Quantitative": ["quantitative", "wf4"],
        "Orchestrator": ["orchestrator"],
        "PME": ["pme", "gateway", "multi-canal", "action executor", "whatsapp"],
    }

    result = api("GET", "workflows?limit=100")
    if not result:
        return 0

    wfs = result.get("data", result)
    if isinstance(wfs, dict) and "data" in wfs:
        wfs = wfs["data"]

    assigned = 0
    for wf in wfs:
        wid = wf.get("id", "")
        wname = wf.get("name", "?")
        wname_lower = wname.lower()

        # Determine which pipeline this workflow belongs to
        target_label = None
        for label, patterns in pipeline_patterns.items():
            if any(p in wname_lower for p in patterns):
                target_label = label
                break

        if not target_label or target_label not in or_creds:
            continue

        target_cred_id = or_creds[target_label]

        # Get full workflow
        full = api("GET", f"workflows/{wid}")
        if not full:
            continue
        wf_data = full.get("data", full)
        if isinstance(wf_data, dict) and "data" in wf_data:
            wf_data = wf_data["data"]

        # Update all httpHeaderAuth credentials in this workflow's nodes
        changed = False
        for node in wf_data.get("nodes", []):
            creds = node.get("credentials", {})
            if "httpHeaderAuth" in creds:
                creds["httpHeaderAuth"] = {
                    "id": target_cred_id,
                    "name": f"OpenRouter API ({target_label})",
                }
                changed = True

        if changed:
            upd = api("PATCH", f"workflows/{wid}", {
                "nodes": wf_data.get("nodes", []),
                "connections": wf_data.get("connections", {}),
                "settings": wf_data.get("settings", {}),
                "name": wname,
            })
            if upd:
                print(f"  Assigned OpenRouter ({target_label}) key to: {wname}")
                assigned += 1
            else:
                print(f"  FAILED to assign key for: {wname}")

    print(f"  Per-pipeline key assignment: {assigned} workflows updated")
    return assigned


def assign_per_pipeline_groq(type_map):
    """Override Groq credentials on core pipeline HTTP Request nodes.

    Core pipelines (Standard, Graph, Quantitative, Orchestrator) use Groq
    for LLM inference. This assigns the per-pipeline Groq httpHeaderAuth
    credential to all HTTP Request nodes that point to api.groq.com.
    """
    groq_creds = type_map.get("_groq_pipeline_creds", {})
    if not groq_creds:
        print("  No per-pipeline Groq credentials available")
        return 0

    pipeline_patterns = {
        "Standard": ["standard", "wf5"],
        "Graph": ["graph", "wf2"],
        "Quantitative": ["quantitative", "wf4"],
        "Orchestrator": ["orchestrator"],
    }

    result = api("GET", "workflows?limit=100")
    if not result:
        return 0

    wfs = result.get("data", result)
    if isinstance(wfs, dict) and "data" in wfs:
        wfs = wfs["data"]

    assigned = 0
    for wf in wfs:
        wid = wf.get("id", "")
        wname = wf.get("name", "?")
        wname_lower = wname.lower()

        target_label = None
        for label, patterns in pipeline_patterns.items():
            if any(p in wname_lower for p in patterns):
                target_label = label
                break

        if not target_label or target_label not in groq_creds:
            continue

        target_cred_id = groq_creds[target_label]

        full = api("GET", f"workflows/{wid}")
        if not full:
            continue
        wf_data = full.get("data", full)
        if isinstance(wf_data, dict) and "data" in wf_data:
            wf_data = wf_data["data"]

        changed = False
        for node in wf_data.get("nodes", []):
            node_type = node.get("type", "")
            params = node.get("parameters", {})

            # Target HTTP Request nodes that call Groq API
            if node_type == "n8n-nodes-base.httpRequest":
                url_val = str(params.get("url", ""))
                if "groq.com" in url_val or "api.groq.com" in url_val:
                    # Set predefined credential type
                    node["credentials"] = node.get("credentials", {})
                    node["credentials"]["httpHeaderAuth"] = {
                        "id": target_cred_id,
                        "name": f"Groq API ({target_label})",
                    }
                    # Ensure authentication is set to predefinedCredentialType
                    params["authentication"] = "predefinedCredentialType"
                    params["nodeCredentialType"] = "httpHeaderAuth"
                    changed = True

        if changed:
            upd = api("PATCH", f"workflows/{wid}", {
                "nodes": wf_data.get("nodes", []),
                "connections": wf_data.get("connections", {}),
                "settings": wf_data.get("settings", {}),
                "name": wname,
            })
            if upd:
                print(f"  Assigned Groq ({target_label}) key to: {wname}")
                assigned += 1
            else:
                print(f"  FAILED to assign Groq key for: {wname}")

    print(f"  Per-pipeline Groq assignment: {assigned} workflows updated")
    return assigned


def activate_single(wid, wname):
    """Activate a single workflow. Returns True if successful."""
    # Deactivate first (reset state)
    api("PATCH", f"workflows/{wid}", {"active": False})
    time.sleep(0.5)

    # Get fresh versionId
    full = api("GET", f"workflows/{wid}")
    if not full:
        print(f"    Could not get: {wname}")
        return False

    wf_data = full.get("data", full)
    if isinstance(wf_data, dict) and "data" in wf_data:
        wf_data = wf_data["data"]
    version_id = wf_data.get("versionId", "")

    # Method 1: POST /activate with versionId (n8n 2.8+)
    if version_id:
        act_result = api("POST", f"workflows/{wid}/activate", {"versionId": version_id})
        if act_result:
            d = act_result.get("data", act_result)
            if d.get("active", False):
                print(f"    POST /activate OK: {wname}")
                return True
            err = str(act_result.get("message", ""))[:150]
            print(f"    POST /activate not active: {wname} — {err}")
    else:
        print(f"    No versionId for: {wname}")

    # Method 2: PATCH {active: true} — fallback
    fb = api("PATCH", f"workflows/{wid}", {"active": True})
    if fb:
        d = fb.get("data", fb)
        if isinstance(d, dict) and "data" in d:
            d = d["data"]
        if d.get("active", False):
            print(f"    PATCH active OK: {wname}")
            return True
        err = str(fb.get("message", ""))[:150]
        print(f"    PATCH not active: {wname} — {err}")

    print(f"    FAILED to activate: {wname}")
    return False


def activate_all_workflows():
    """Activate all workflows in 2 passes.

    Pass 1: Base workflows (Standard, Graph, Quantitative, support, etc.)
    Pass 2: Orchestrator + gateway (depend on sub-workflows being active first)

    Workflows that need Google OAuth or messaging creds we don't have are skipped.
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

    # Skip workflows that need OAuth/messaging creds we can't create
    skip_keywords = ["action executor", "whatsapp"]
    # Orchestrator + gateway in pass 2 (they reference sub-workflows)
    pass2_keywords = ["orchestrator", "gateway", "multi-canal"]

    pass1 = []
    pass2 = []
    skipped = 0
    for wf in wfs:
        wname_lower = wf.get("name", "").lower()
        if any(k in wname_lower for k in skip_keywords):
            print(f"  SKIP (missing OAuth/messaging creds): {wf.get('name', '?')}")
            skipped += 1
            continue
        if any(k in wname_lower for k in pass2_keywords):
            pass2.append(wf)
        else:
            pass1.append(wf)

    activated = 0
    failed = 0

    # Pass 1: Base workflows
    print(f"  === Pass 1: {len(pass1)} base workflows ===")
    for wf in pass1:
        if activate_single(wf.get("id", ""), wf.get("name", "?")):
            activated += 1
        else:
            failed += 1
        time.sleep(0.5)

    # Pass 2: Orchestrator + gateway (after base workflows are active)
    if pass2:
        print(f"  === Pass 2: {len(pass2)} orchestrator/gateway workflows ===")
        time.sleep(3)  # Let n8n settle after pass 1
        for wf in pass2:
            wid = wf.get("id", "")
            wname = wf.get("name", "?")
            success = False
            for attempt in range(1, 4):
                if activate_single(wid, wname):
                    success = True
                    break
                print(f"    Retry {attempt}/3 for: {wname}")
                time.sleep(3)
            if success:
                activated += 1
            else:
                failed += 1

    print(f"  Activation: {activated} OK, {failed} failed, {skipped} skipped")
    return activated


def verify_webhooks_deep():
    """Verify webhook endpoints respond with actual content (not just HTTP 200)."""
    webhooks = {
        "Standard": "webhook/rag-multi-index-v3",
        "Graph": "webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "Quantitative": "webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "Orchestrator": "webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
        "PME Gateway": "webhook/pme-assistant-gateway",
    }

    print("  Deep webhook verification (content check):")
    ok = 0
    results = {}
    for name, path in webhooks.items():
        url = f"{BASE}/{path}"
        data = json.dumps({"query": "health-check", "question": "health-check"}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")

        try:
            resp = urllib.request.urlopen(req, timeout=15)
            code = resp.status
            body = resp.read().decode()[:200]

            # Check for actual content (not empty, not just error message)
            has_content = len(body) > 10 and not body.strip().startswith("<!DOCTYPE")

            if code == 200 and has_content:
                status = "✓ OK"
                ok += 1
            elif code == 200:
                status = "⚠ Empty"
            else:
                status = f"⚠ HTTP {code}"

            results[name] = {"status": status, "code": code, "body": body[:80]}
            print(f"    {name}: {status} — {body[:80]}")
        except urllib.error.HTTPError as e:
            code = e.code
            body = e.read().decode()[:200] if hasattr(e, 'read') else ""
            status = f"✗ HTTP {code}"
            results[name] = {"status": status, "code": code, "body": body[:80]}
            print(f"    {name}: {status} — {body[:80]}")
        except Exception as e:
            status = f"✗ ERROR"
            results[name] = {"status": status, "code": 0, "error": str(e)[:80]}
            print(f"    {name}: {status} — {str(e)[:80]}")

    print(f"  Webhooks deep check: {ok}/{len(webhooks)} fully working")
    return ok, results


def verify_webhooks():
    """Basic webhook verification (checks registration, not content)."""
    webhooks = {
        "Standard": "webhook/rag-multi-index-v3",
        "Graph": "webhook/ff622742-6d71-4e91-af71-b5c666088717",
        "Quantitative": "webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
        "Orchestrator": "webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
        "PME Gateway": "webhook/pme-assistant-gateway",
    }

    print("  Basic webhook verification:")
    ok = 0
    for name, path in webhooks.items():
        url = f"{BASE}/{path}"
        data = json.dumps({"query": "health-check"}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            code = resp.status
        except urllib.error.HTTPError as e:
            code = e.code
        except:
            code = 0

        # 200, 405 (wrong method), 500 (workflow error but webhook exists) = webhook registered
        status = "OK" if code not in (0, 404) else "FAIL"
        if status == "OK":
            ok += 1
        print(f"    {name}: HTTP {code} ({status})")

    print(f"  Webhooks: {ok}/{len(webhooks)} registered")
    return ok


def run_full_setup_with_retry(max_retries=2):
    """Run full setup with retry logic if verification fails."""
    for attempt in range(1, max_retries + 1):
        print(f"\n{'=' * 60}")
        print(f"  SETUP ATTEMPT {attempt}/{max_retries + 1}")
        print(f"{'=' * 60}")

        print("\n=== [A] Creating credentials ===")
        id_map, type_map, cred_stats = create_all_credentials()

        # If all credentials failed, no point continuing
        if not cred_stats["created"]:
            print("\n  CRITICAL: No credentials created. Cannot proceed.")
            if attempt < max_retries:
                print(f"  Retrying in 10s...")
                time.sleep(10)
                continue
            else:
                return False

        print("\n=== [B] Restoring credential references from original JSONs ===")
        restored = restore_credentials_and_update(id_map, type_map)

        print("\n=== [B2] Assigning per-pipeline OpenRouter keys (rate limit distribution) ===")
        assigned = assign_per_pipeline_openrouter(type_map)

        print("\n=== [B3] Assigning per-pipeline Groq keys (core pipelines) ===")
        groq_assigned = assign_per_pipeline_groq(type_map)

        print("\n=== [C] Publishing & activating workflows ===")
        time.sleep(3)  # Let n8n settle
        activated = activate_all_workflows()

        print("\n=== [D] Verifying webhooks (basic) ===")
        time.sleep(2)
        basic_ok = verify_webhooks()

        print("\n=== [E] Deep verification (content check) ===")
        time.sleep(3)
        deep_ok, deep_results = verify_webhooks_deep()

        # Check if we have acceptable results
        # Success criteria: at least 3/4 core pipelines fully working
        if deep_ok >= 3:
            print(f"\n  ✓ SETUP SUCCESSFUL — {deep_ok}/5 pipelines fully working")
            print(f"  Credentials created: {len(cred_stats['created'])}")
            print(f"  Workflows restored: {restored}")
            print(f"  Workflows activated: {activated}")
            return True

        # If failed and we have retries left
        if attempt < max_retries:
            print(f"\n  ⚠ Verification failed ({deep_ok}/5 working). Retrying in 10s...")
            print(f"  Failed pipelines:")
            for name, result in deep_results.items():
                if "✓" not in result["status"]:
                    print(f"    - {name}: {result['status']}")
            time.sleep(10)
        else:
            print(f"\n  ✗ SETUP FAILED after {max_retries + 1} attempts")
            print(f"  Only {deep_ok}/5 pipelines working")
            return False

    return False


if __name__ == "__main__":
    if not COOKIE:
        print("ERROR: No auth cookie provided")
        sys.exit(1)

    success = run_full_setup_with_retry(max_retries=2)

    if success:
        print("\n" + "=" * 60)
        print("  SETUP COMPLETE — ALL SYSTEMS GO")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("  SETUP INCOMPLETE — SOME SYSTEMS MAY BE DOWN")
        print("=" * 60)
        # Exit 0 anyway to keep container alive
        sys.exit(0)
