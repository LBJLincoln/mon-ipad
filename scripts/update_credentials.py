#!/usr/bin/env python3
"""
Update credential IDs in all n8n workflows.
Replaces old (non-existent) credential IDs with new Docker-era ones.
"""

import json
import os
import sys
import copy
import requests

N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

CREDENTIAL_MAP = {
    "O2KEPiv7VzgDG5ZX": "CWih07lwPxfwFeY6",
    "0bf5AHN9S8qJTBr8": "USU8ngVzsUbED3mn",
    "FZUFrHg9RgDR3MAB": "USU8ngVzsUbED3mn",
    "zEr7jPswZNv6lWKu": "USU8ngVzsUbED3mn",
}

CREDENTIAL_NAME_MAP = {
    "O2KEPiv7VzgDG5ZX": "Redis Upstash",
    "0bf5AHN9S8qJTBr8": "Supabase Postgres Pooler",
    "FZUFrHg9RgDR3MAB": "Supabase Postgres Pooler",
    "zEr7jPswZNv6lWKu": "Supabase Postgres Pooler",
}

ALLOWED_SETTINGS_KEYS = {
    "executionOrder",
    "callerPolicy",
    "saveManualExecutions",
    "saveExecutionProgress",
}

HEADERS = {}


def api_get(path):
    resp = requests.get(f"{N8N_HOST}{path}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path):
    resp = requests.post(f"{N8N_HOST}{path}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_put(path, payload):
    resp = requests.put(f"{N8N_HOST}{path}", headers=HEADERS, json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"    PUT error {resp.status_code}: {resp.text[:500]}")
    resp.raise_for_status()
    return resp.json()


def build_payload(wf):
    """Build a clean PUT payload with only accepted fields."""
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {
            k: v
            for k, v in wf.get("settings", {}).items()
            if k in ALLOWED_SETTINGS_KEYS
        },
    }
    if wf.get("staticData") is not None:
        payload["staticData"] = wf["staticData"]
    return payload


def update_credentials_in_nodes(nodes):
    changes = 0
    details = []

    for node in nodes:
        if "credentials" not in node:
            continue

        creds = node["credentials"]
        node_name = node.get("name", "unknown")

        for cred_type, cred_info in creds.items():
            if not isinstance(cred_info, dict):
                continue

            old_id = cred_info.get("id")
            if old_id and old_id in CREDENTIAL_MAP:
                new_id = CREDENTIAL_MAP[old_id]
                new_name = CREDENTIAL_NAME_MAP.get(old_id, cred_info.get("name", ""))

                details.append(
                    f"  Node '{node_name}' ({node.get('type', '?')}): "
                    f"{cred_type} {old_id} -> {new_id}"
                )

                cred_info["id"] = new_id
                if new_name:
                    cred_info["name"] = new_name

                changes += 1

    return nodes, changes, details


def main():
    global HEADERS

    api_key = os.environ.get("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY not set. Source .env.local first.")
        sys.exit(1)

    HEADERS = {
        "X-N8N-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print("=" * 70)
    print("n8n Credential ID Updater")
    print("=" * 70)
    print()

    # Step 1: List all workflows
    print("[1] Fetching all workflows...")
    data = api_get("/api/v1/workflows?limit=100")
    workflows = data.get("data", [])
    print(f"    Found {len(workflows)} workflows.")
    print()

    # Step 2: Scan each workflow
    affected = []
    print("[2] Scanning workflows for old credential IDs...")
    print()

    for wf_summary in workflows:
        wf_id = wf_summary["id"]
        wf_name = wf_summary.get("name", "unnamed")
        was_active = wf_summary.get("active", False)

        wf = api_get(f"/api/v1/workflows/{wf_id}")
        nodes = wf.get("nodes", [])

        _, changes, details = update_credentials_in_nodes(copy.deepcopy(nodes))

        if changes > 0:
            affected.append({
                "id": wf_id,
                "name": wf_name,
                "was_active": was_active,
                "changes": changes,
                "details": details,
                "workflow": wf,
            })
            print(f"  [MATCH] {wf_id} - {wf_name} ({changes} node(s) to update)")
            for d in details:
                print(d)
        else:
            print(f"  [  OK ] {wf_id} - {wf_name}")

    print()

    if not affected:
        print("No workflows need updating. All credential IDs are current.")
        return

    print(f"[3] Updating {len(affected)} workflow(s)...")
    print()

    success_count = 0
    for item in affected:
        wf_id = item["id"]
        wf_name = item["name"]
        was_active = item["was_active"]
        wf = item["workflow"]

        print(f"  --- Updating: {wf_id} - {wf_name} ---")

        # Apply credential updates to nodes
        updated_nodes, changes, details = update_credentials_in_nodes(wf["nodes"])
        wf["nodes"] = updated_nodes

        # Build clean payload
        payload = build_payload(wf)

        try:
            # Deactivate if active
            if was_active:
                print(f"    Deactivating...")
                api_post(f"/api/v1/workflows/{wf_id}/deactivate")

            # PUT updated workflow
            print(f"    Sending PUT with {changes} credential change(s)...")
            api_put(f"/api/v1/workflows/{wf_id}", payload)

            # Reactivate if it was active
            if was_active:
                print(f"    Reactivating...")
                api_post(f"/api/v1/workflows/{wf_id}/activate")

            print(f"    SUCCESS - {changes} credential(s) updated")
            success_count += 1

        except requests.exceptions.HTTPError as e:
            print(f"    FAILED: {e}")
            if was_active:
                try:
                    api_post(f"/api/v1/workflows/{wf_id}/activate")
                    print(f"    (reactivated after failure)")
                except Exception:
                    print(f"    WARNING: could not reactivate workflow!")

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Workflows scanned:  {len(workflows)}")
    print(f"  Workflows affected: {len(affected)}")
    print(f"  Workflows updated:  {success_count}")
    print(f"  Workflows failed:   {len(affected) - success_count}")
    print()

    total_changes = sum(item["changes"] for item in affected)
    print(f"  Total credential replacements: {total_changes}")
    print()

    print("  Credential replacements applied:")
    for old_id, new_id in CREDENTIAL_MAP.items():
        cred_name = CREDENTIAL_NAME_MAP.get(old_id, "")
        print(f"    {old_id} -> {new_id} ({cred_name})")
    print()

    if success_count == len(affected):
        print("  All updates completed successfully.")
    else:
        print("  WARNING: Some updates failed. Check output above.")


if __name__ == "__main__":
    main()
