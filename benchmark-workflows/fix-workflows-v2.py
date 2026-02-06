#!/usr/bin/env python3
"""
Fix #2: Address deployment-tested issues:
1. Graph RAG: Update deprecated model google/gemini-2.0-flash-exp
2. Quantitative RAG: Disable OTEL Export node (swallows webhook response)
"""
import json, os

REPO = "/home/user/mon-ipad"

def fix_graph_rag():
    path = os.path.join(REPO, "TEST - SOTA 2026 - WF2 Graph RAG V3.3 - CORRECTED (1).json")
    with open(path) as f:
        wf = json.load(f)

    # Fix 1: Update model in Response Formatter (Context Builder) code
    for node in wf["nodes"]:
        if node["name"] == "Response Formatter" and node["type"] == "n8n-nodes-base.code":
            code = node["parameters"]["jsCode"]
            # Replace hardcoded deprecated model with variable reference
            code = code.replace(
                "model: 'google/gemini-2.0-flash-exp'",
                "model: $vars.LLM_ANSWER_MODEL || $vars.LLM_HYDE_MODEL || 'google/gemini-2.5-flash-preview-05-20'"
            )
            node["parameters"]["jsCode"] = code
            print("  [Graph RAG] Updated model in Context Builder")
            break

    # Fix 2: Also update HyDE default fallback model (in case $vars not set)
    for node in wf["nodes"]:
        if node["name"] == "WF3: HyDE & Entity Extraction":
            body = node["parameters"].get("jsonBody", "")
            body = body.replace("google/gemini-2.0-flash-exp", "google/gemini-2.5-flash-preview-05-20")
            node["parameters"]["jsonBody"] = body
            print("  [Graph RAG] Updated HyDE fallback model")
            break

    with open(path, "w") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f"  [Graph RAG] Saved")


def fix_quantitative_rag():
    path = os.path.join(REPO, "TEST - SOTA 2026 - WF4 Quantitative V2.0 (1).json")
    with open(path) as f:
        wf = json.load(f)

    # Fix 1: Disable OTEL Export node (it swallows webhook response with continueErrorOutput)
    for node in wf["nodes"]:
        if node["name"] == "OTEL Export (Shield #9)":
            node["disabled"] = True
            print("  [Quant RAG] Disabled OTEL Export (was swallowing webhook response)")
            break

    # Fix 2: Update deprecated model fallbacks
    for node in wf["nodes"]:
        code = node.get("parameters", {}).get("jsCode", "")
        if "google/gemini-2.0-flash-exp" in code:
            code = code.replace("google/gemini-2.0-flash-exp", "google/gemini-2.5-flash-preview-05-20")
            node["parameters"]["jsCode"] = code
            print(f"  [Quant RAG] Updated model in {node['name']}")

        # Also update HTTP Request nodes
        body = node.get("parameters", {}).get("jsonBody", "")
        if "google/gemini-2.0-flash-exp" in body:
            body = body.replace("google/gemini-2.0-flash-exp", "google/gemini-2.5-flash-preview-05-20")
            node["parameters"]["jsonBody"] = body
            print(f"  [Quant RAG] Updated model in {node['name']} (jsonBody)")

    with open(path, "w") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f"  [Quant RAG] Saved")


if __name__ == "__main__":
    print("=" * 60)
    print("  FIXING DEPLOYMENT ISSUES (Round 2)")
    print("=" * 60)

    print("\n--- Graph RAG ---")
    fix_graph_rag()

    print("\n--- Quantitative RAG ---")
    fix_quantitative_rag()

    print("\n  Done!")
