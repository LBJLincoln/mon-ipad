#!/usr/bin/env python3
"""
Disable specific Redis, Postgres, Guardrails, and Cache nodes
in the orchestrator.json workflow file.

Modifies both top-level "nodes" and "activeVersion"."nodes" arrays.
"""

import json
import sys

ORCHESTRATOR_PATH = "/home/termius/mon-ipad/n8n/live/orchestrator.json"

# Exact node names to disable
NODES_TO_DISABLE = {
    # Redis nodes
    "Redis: Fetch Conversation",
    "Redis: Store Conv V8",
    "Redis: Set Cache",
    "Redis: Cache + Generator",
    # Postgres nodes
    "Postgres L2/L3 Memory",
    "Postgres: Update Context V8",
    "Postgres: Init Tasks Table",
    "Postgres: Insert Tasks",
    "Postgres: Update Task",
    "Postgres: Update Fallback",
    "Postgres: Apply Skips",
    "Postgres: Insert New Tasks",
    "Postgres: Get Current Tasks",
    # Guardrails nodes
    "\U0001f6e1\ufe0f Advanced Guardrails",
    "IF: Guardrail Passed?",
    "Return: Guardrail Blocked",
    # Cache nodes
    "Cache Parser",
    "IF: Cache Hit?",
    "Return: Cached",
    "\U0001f4be Cache Storage",
    "\U0001f50d Cache Semantic Search",
    # Other
    "\U0001f6a8 Redis Failure Handler V10.1",
    "Memory Merger",
}

def disable_nodes_in_array(nodes_array, label):
    """Disable matching nodes in a given array. Returns count of nodes disabled."""
    count = 0
    for node in nodes_array:
        name = node.get("name", "")
        if name in NODES_TO_DISABLE:
            if not node.get("disabled", False):
                node["disabled"] = True
                print(f"  [{label}] DISABLED: {name}")
                count += 1
            else:
                print(f"  [{label}] ALREADY DISABLED: {name}")
                count += 1
    return count


def main():
    with open(ORCHESTRATOR_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_disabled = 0

    # 1. Top-level nodes
    top_nodes = data.get("nodes", [])
    print(f"\n--- Top-level nodes ({len(top_nodes)} total) ---")
    count1 = disable_nodes_in_array(top_nodes, "top-level")

    # 2. activeVersion.nodes
    av_nodes = data.get("activeVersion", {}).get("nodes", [])
    print(f"\n--- activeVersion nodes ({len(av_nodes)} total) ---")
    count2 = disable_nodes_in_array(av_nodes, "activeVersion")

    total_disabled = count1 + count2

    # Check for nodes we expected but didn't find
    found_top = {n.get("name") for n in top_nodes}
    found_av = {n.get("name") for n in av_nodes}
    missing_top = NODES_TO_DISABLE - found_top
    missing_av = NODES_TO_DISABLE - found_av

    if missing_top:
        print(f"\n  [WARNING] Not found in top-level nodes: {missing_top}")
    if missing_av:
        print(f"\n  [WARNING] Not found in activeVersion nodes: {missing_av}")

    # Save
    with open(ORCHESTRATOR_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n=== SUMMARY ===")
    print(f"Top-level nodes disabled: {count1}")
    print(f"activeVersion nodes disabled: {count2}")
    print(f"Total node entries disabled: {total_disabled}")
    print(f"File saved: {ORCHESTRATOR_PATH}")


if __name__ == "__main__":
    main()
