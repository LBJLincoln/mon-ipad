#!/usr/bin/env python3
"""
Workflow Sync — Pull workflows from n8n, store versioned snapshots, compute diffs.

This script:
1. Pulls the current state of all 4 RAG workflows from n8n cloud API
2. Saves them as versioned JSON snapshots in workflows/snapshots/
3. Computes diffs against previous versions (node changes, parameter changes)
4. Updates data.json with workflow_versions[] for the dashboard
5. Records changes in workflow_changes[] for the agentic evaluator

Usage:
  python workflow-sync.py                    # Pull all workflows, store + diff
  python workflow-sync.py --deploy FILE      # Deploy a local JSON to n8n
  python workflow-sync.py --diff V1 V2       # Compare two stored versions
  python workflow-sync.py --list             # List all stored versions
"""

import json
import os
import sys
import hashlib
from datetime import datetime
from urllib import request, error
from importlib.machinery import SourceFileLoader

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS_DIR = os.path.join(REPO_ROOT, "workflows")
SNAPSHOTS_DIR = os.path.join(WORKFLOWS_DIR, "snapshots")
MANIFEST_FILE = os.path.join(WORKFLOWS_DIR, "manifest.json")
DATA_FILE = os.path.join(REPO_ROOT, "docs", "data.json")

os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

# Load writer for recording changes
writer = SourceFileLoader("w", os.path.join(REPO_ROOT, "eval", "live-writer.py")).load_module()

# n8n API config
N8N_HOST = os.environ.get("N8N_HOST", "https://amoret.app.n8n.cloud")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A")

WORKFLOW_IDS = {
    "standard": {
        "id": "LnTqRX4LZlI009Ks-3Jnp",
        "name": "WF5 Standard RAG V3.4",
        "webhook": "/webhook/rag-multi-index-v3",
    },
    "graph": {
        "id": "95x2BBAbJlLWZtWEJn6rb",
        "name": "WF2 Graph RAG V3.3",
        "webhook": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    },
    "quantitative": {
        "id": "LjUz8fxQZ03G9IsU",
        "name": "WF4 Quantitative V2.0",
        "webhook": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    },
    "orchestrator": {
        "id": "FZxkpldDbgV8AD_cg7IWG",
        "name": "V10.1 Orchestrator",
        "webhook": "/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0",
    },
}


def api_get(endpoint, timeout=30):
    """GET request to n8n API."""
    url = f"{N8N_HOST}/api/v1{endpoint}"
    headers = {"X-N8N-API-KEY": N8N_API_KEY, "Accept": "application/json"}
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        print(f"  API error {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  API error: {e}")
        return None


def api_put(endpoint, data, timeout=60):
    """PUT request to n8n API."""
    url = f"{N8N_HOST}/api/v1{endpoint}"
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode()
    req = request.Request(url, data=body, headers=headers, method="PUT")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        print(f"  API error {e.code}: {e.read().decode()[:300]}")
        return None


def api_patch(endpoint, data, timeout=30):
    """PATCH request to n8n API."""
    url = f"{N8N_HOST}/api/v1{endpoint}"
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode()
    req = request.Request(url, data=body, headers=headers, method="PATCH")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        print(f"  API error {e.code}: {e.read().decode()[:300]}")
        return None


def compute_workflow_hash(workflow_data):
    """Compute a stable hash of the workflow (ignoring volatile fields)."""
    # Extract only structural data: nodes and connections
    stable = {
        "nodes": [],
        "connections": workflow_data.get("connections", {}),
    }
    for node in workflow_data.get("nodes", []):
        stable["nodes"].append({
            "name": node.get("name", ""),
            "type": node.get("type", ""),
            "parameters": node.get("parameters", {}),
            "typeVersion": node.get("typeVersion"),
        })
    # Sort nodes by name for stability
    stable["nodes"].sort(key=lambda n: n["name"])
    raw = json.dumps(stable, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def extract_workflow_summary(wf_data):
    """Extract a human-readable summary of the workflow structure."""
    nodes = wf_data.get("nodes", [])
    node_types = {}
    for node in nodes:
        ntype = node.get("type", "unknown").split(".")[-1]
        node_types[ntype] = node_types.get(ntype, 0) + 1

    # Find LLM models used
    models = set()
    for node in nodes:
        params = node.get("parameters", {})
        for key in ["model", "modelId", "model_name"]:
            if key in params:
                models.add(str(params[key]))
        # Check nested options
        options = params.get("options", {})
        if isinstance(options, dict):
            for key in ["model", "modelId"]:
                if key in options:
                    models.add(str(options[key]))

    return {
        "total_nodes": len(nodes),
        "node_types": node_types,
        "models_used": sorted(models) if models else [],
        "node_names": [n.get("name", "") for n in nodes],
    }


def diff_workflows(old_wf, new_wf):
    """Compute a diff between two workflow versions."""
    old_nodes = {n.get("name", ""): n for n in old_wf.get("nodes", [])}
    new_nodes = {n.get("name", ""): n for n in new_wf.get("nodes", [])}

    added = [name for name in new_nodes if name not in old_nodes]
    removed = [name for name in old_nodes if name not in new_nodes]

    modified = []
    for name in set(old_nodes.keys()) & set(new_nodes.keys()):
        old_params = json.dumps(old_nodes[name].get("parameters", {}), sort_keys=True)
        new_params = json.dumps(new_nodes[name].get("parameters", {}), sort_keys=True)
        if old_params != new_params:
            # Find what changed
            old_p = old_nodes[name].get("parameters", {})
            new_p = new_nodes[name].get("parameters", {})
            changes = []
            all_keys = set(list(old_p.keys()) + list(new_p.keys()))
            for key in all_keys:
                old_val = json.dumps(old_p.get(key), sort_keys=True, default=str)
                new_val = json.dumps(new_p.get(key), sort_keys=True, default=str)
                if old_val != new_val:
                    changes.append({
                        "param": key,
                        "old": str(old_p.get(key, ""))[:200],
                        "new": str(new_p.get(key, ""))[:200],
                    })
            modified.append({"node": name, "changes": changes})

    return {
        "added_nodes": added,
        "removed_nodes": removed,
        "modified_nodes": modified,
        "has_changes": bool(added or removed or modified),
        "summary": f"+{len(added)} -{len(removed)} ~{len(modified)} nodes",
    }


def load_manifest():
    """Load the workflow version manifest."""
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    return {"versions": {}, "history": []}


def save_manifest(manifest):
    """Save the manifest."""
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def pull_all_workflows():
    """Pull all workflows from n8n, snapshot, and compute diffs."""
    manifest = load_manifest()
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    results = {}

    for pipeline, config in WORKFLOW_IDS.items():
        wf_id = config["id"]
        print(f"\n  Pulling {pipeline} (ID: {wf_id})...")

        wf_data = api_get(f"/workflows/{wf_id}")
        if not wf_data:
            print(f"    FAILED: Could not pull {pipeline}")
            results[pipeline] = {"status": "error", "error": "API call failed"}
            continue

        # Compute hash
        wf_hash = compute_workflow_hash(wf_data)
        summary = extract_workflow_summary(wf_data)
        print(f"    Nodes: {summary['total_nodes']}, Hash: {wf_hash}")
        if summary["models_used"]:
            print(f"    Models: {', '.join(summary['models_used'])}")

        # Check if changed from previous version
        prev = manifest["versions"].get(pipeline, {})
        prev_hash = prev.get("hash", "")
        changed = wf_hash != prev_hash

        if changed:
            # Save snapshot
            snap_file = f"{pipeline}-{timestamp}-{wf_hash}.json"
            snap_path = os.path.join(SNAPSHOTS_DIR, snap_file)
            with open(snap_path, "w") as f:
                json.dump(wf_data, f, indent=2, ensure_ascii=False)
            print(f"    CHANGED: Saved snapshot {snap_file}")

            # Compute diff
            diff = None
            if prev.get("snapshot_file"):
                prev_snap_path = os.path.join(SNAPSHOTS_DIR, prev["snapshot_file"])
                if os.path.exists(prev_snap_path):
                    with open(prev_snap_path) as f:
                        prev_wf = json.load(f)
                    diff = diff_workflows(prev_wf, wf_data)
                    print(f"    Diff: {diff['summary']}")
                    for mod in diff.get("modified_nodes", []):
                        for ch in mod.get("changes", [])[:3]:
                            print(f"      {mod['node']}.{ch['param']}: {ch['old'][:50]} -> {ch['new'][:50]}")

            # Update manifest
            version_num = prev.get("version", 0) + 1
            manifest["versions"][pipeline] = {
                "version": version_num,
                "hash": wf_hash,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "snapshot_file": snap_file,
                "name": config["name"],
                "webhook": config["webhook"],
                "summary": summary,
                "diff_from_previous": diff,
            }

            # Record in history
            manifest["history"].append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "pipeline": pipeline,
                "version": version_num,
                "hash": wf_hash,
                "diff_summary": diff["summary"] if diff else "initial",
                "snapshot_file": snap_file,
            })

            # Record workflow change in data.json
            desc = f"{pipeline} workflow updated (v{version_num}, hash {wf_hash})"
            if diff:
                desc += f" — {diff['summary']}"
            writer.record_workflow_change(
                description=desc,
                change_type="workflow-sync",
                affected_pipelines=[pipeline],
                files_changed=[snap_file],
            )

            results[pipeline] = {
                "status": "updated",
                "version": version_num,
                "hash": wf_hash,
                "diff": diff,
                "summary": summary,
            }
        else:
            print(f"    UNCHANGED (hash: {wf_hash})")
            results[pipeline] = {
                "status": "unchanged",
                "version": prev.get("version", 0),
                "hash": wf_hash,
            }

    save_manifest(manifest)

    # Update data.json with current workflow versions
    update_data_json_workflows(manifest)

    return results


def update_data_json_workflows(manifest):
    """Update data.json with workflow_versions for the dashboard."""
    if not os.path.exists(DATA_FILE):
        return

    with open(DATA_FILE) as f:
        data = json.load(f)

    data["workflow_versions"] = {}
    for pipeline, info in manifest.get("versions", {}).items():
        data["workflow_versions"][pipeline] = {
            "version": info.get("version", 0),
            "hash": info.get("hash", ""),
            "timestamp": info.get("timestamp", ""),
            "name": info.get("name", ""),
            "webhook": info.get("webhook", ""),
            "total_nodes": info.get("summary", {}).get("total_nodes", 0),
            "models_used": info.get("summary", {}).get("models_used", []),
            "snapshot_file": info.get("snapshot_file", ""),
            "diff_from_previous": info.get("diff_from_previous"),
        }

    data["workflow_history"] = manifest.get("history", [])[-20:]

    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)
    print(f"\n  Updated data.json with workflow versions")


def list_versions():
    """List all stored workflow versions."""
    manifest = load_manifest()
    print("\nCurrent workflow versions:")
    for pipeline, info in manifest.get("versions", {}).items():
        print(f"  {pipeline}: v{info.get('version', '?')} ({info.get('hash', '?')[:8]}) "
              f"— {info.get('summary', {}).get('total_nodes', '?')} nodes "
              f"— {info.get('timestamp', '?')}")

    print(f"\nHistory ({len(manifest.get('history', []))} entries):")
    for entry in manifest.get("history", [])[-10:]:
        print(f"  {entry['timestamp'][:19]} | {entry['pipeline']} v{entry['version']} "
              f"| {entry.get('diff_summary', '?')}")


def main():
    if "--list" in sys.argv:
        list_versions()
    elif "--deploy" in sys.argv:
        idx = sys.argv.index("--deploy")
        if idx + 1 < len(sys.argv):
            print("Deploy not yet implemented via this script. Use deploy-corrected-workflows.py.")
        else:
            print("Usage: --deploy <file.json>")
    else:
        print("=" * 60)
        print("  WORKFLOW SYNC — Pull from n8n Cloud")
        print(f"  Host: {N8N_HOST}")
        print(f"  Time: {datetime.utcnow().isoformat()}Z")
        print("=" * 60)
        results = pull_all_workflows()
        print("\n" + "=" * 60)
        print("  SUMMARY")
        print("=" * 60)
        for pipe, info in results.items():
            status = info["status"].upper()
            version = info.get("version", "?")
            print(f"  {pipe}: {status} (v{version})")


if __name__ == "__main__":
    main()
