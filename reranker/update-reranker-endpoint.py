#!/usr/bin/env python3
"""
Update n8n workflow JSON files to use the self-hosted reranker instead of Jina API.

Replaces:
  - URL: https://api.jina.ai/v1/rerank -> https://<your-space>.hf.space/v1/rerank
  - Removes Jina auth headers (Bearer token)
  - Keeps model field (mapped automatically by the reranker)

Usage:
  python3 reranker/update-reranker-endpoint.py --endpoint https://lbjlincoln-nomos-reranker-api.hf.space
  python3 reranker/update-reranker-endpoint.py --dry-run  # preview changes
"""

import argparse
import json
import os
import re
import sys

DEFAULT_ENDPOINT = "https://lbjlincoln-nomos-reranker-api.hf.space"
JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
COHERE_RERANK_URL = "https://api.cohere.com/v1/rerank"

WORKFLOW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "n8n", "live")


def update_workflow(filepath: str, new_endpoint: str, dry_run: bool = False) -> dict:
    """Update a single workflow JSON file."""
    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    changes = []

    # Replace Jina rerank URL
    new_url = f"{new_endpoint.rstrip('/')}/v1/rerank"

    if JINA_RERANK_URL in content:
        content = content.replace(JINA_RERANK_URL, new_url)
        changes.append(f"Jina URL -> {new_url}")

    if COHERE_RERANK_URL in content:
        content = content.replace(COHERE_RERANK_URL, new_url)
        changes.append(f"Cohere URL -> {new_url}")

    # Remove Jina auth headers from reranker nodes
    # The n8n JSON has headerParameters with Bearer tokens for Jina
    # We need to parse as JSON for precise editing
    if changes:
        try:
            data = json.loads(content)
            nodes_modified = _remove_reranker_auth(data, changes)
            if nodes_modified:
                content = json.dumps(data, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            changes.append("WARNING: Could not parse JSON for auth header removal")

    if content != original:
        if not dry_run:
            with open(filepath, 'w') as f:
                f.write(content)

        return {
            "file": os.path.basename(filepath),
            "modified": True,
            "changes": changes
        }

    return {
        "file": os.path.basename(filepath),
        "modified": False,
        "changes": []
    }


def _remove_reranker_auth(data: dict, changes: list) -> bool:
    """
    Remove Authorization headers from reranker HTTP Request nodes.
    Walks the workflow JSON looking for nodes named *Reranker* with auth headers.
    """
    modified = False

    # Handle both top-level and versioned nodes
    nodes_lists = []
    if "nodes" in data:
        nodes_lists.append(data["nodes"])
    # n8n versionedNodes
    if "versionedNodes" in data:
        for version in data["versionedNodes"]:
            if "nodes" in version:
                nodes_lists.append(version["nodes"])
    # Check inside versions array
    if "versions" in data:
        for version in data["versions"]:
            if "nodes" in version:
                nodes_lists.append(version["nodes"])

    for nodes in nodes_lists:
        for node in nodes:
            name = node.get("name", "")
            node_type = node.get("type", "")

            # Only modify HTTP Request nodes that are reranker-related
            if "httpRequest" not in node_type.lower() and "httprequest" not in node_type.lower():
                continue
            if "rerank" not in name.lower():
                continue

            params = node.get("parameters", {})

            # Remove auth from headerParameters
            header_params = params.get("options", {}).get("headerParameters", {})
            if header_params:
                param_list = header_params.get("parameters", [])
                new_params = [p for p in param_list if p.get("name", "").lower() != "authorization"]
                if len(new_params) != len(param_list):
                    header_params["parameters"] = new_params
                    changes.append(f"Removed auth header from node '{name}'")
                    modified = True

            # Also set authentication to "none" if it references credentials
            if params.get("authentication") and params["authentication"] != "none":
                params["authentication"] = "none"
                changes.append(f"Set authentication=none on node '{name}'")
                modified = True

            # Remove any sendHeaders with auth
            if "sendHeaders" in params:
                # Check headerParameters inside the main params level too
                hp = params.get("headerParameters", {})
                if hp:
                    pl = hp.get("parameters", [])
                    new_pl = [p for p in pl if p.get("name", "").lower() != "authorization"]
                    if len(new_pl) != len(pl):
                        hp["parameters"] = new_pl
                        changes.append(f"Removed sendHeaders auth from node '{name}'")
                        modified = True
                    if not new_pl:
                        params.pop("sendHeaders", None)
                        params.pop("headerParameters", None)
                        changes.append(f"Removed empty sendHeaders from node '{name}'")

    return modified


def main():
    parser = argparse.ArgumentParser(description="Update n8n reranker endpoints")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                        help=f"Self-hosted reranker URL (default: {DEFAULT_ENDPOINT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without modifying files")
    parser.add_argument("--dir", default=WORKFLOW_DIR,
                        help=f"Workflow JSON directory (default: {WORKFLOW_DIR})")
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        print(f"ERROR: Directory not found: {args.dir}")
        sys.exit(1)

    json_files = [f for f in os.listdir(args.dir) if f.endswith(".json")]
    if not json_files:
        print(f"No JSON files found in {args.dir}")
        sys.exit(1)

    print(f"{'DRY RUN - ' if args.dry_run else ''}Updating reranker endpoint")
    print(f"  Target: {args.endpoint}")
    print(f"  Directory: {args.dir}")
    print(f"  Files: {len(json_files)}")
    print()

    total_modified = 0
    for filename in sorted(json_files):
        filepath = os.path.join(args.dir, filename)
        result = update_workflow(filepath, args.endpoint, args.dry_run)

        if result["modified"]:
            total_modified += 1
            print(f"  MODIFIED {result['file']}")
            for change in result["changes"]:
                print(f"    - {change}")
        else:
            print(f"  (skip)   {result['file']}")

    print(f"\n{'DRY RUN: ' if args.dry_run else ''}{total_modified}/{len(json_files)} files modified")

    if args.dry_run and total_modified > 0:
        print("\nRun without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
