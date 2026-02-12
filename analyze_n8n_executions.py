
import os
import sys
import json
from urllib import request, error
from datetime import datetime

# --- N8n Credentials (from user's prompt) ---
N8N_HOST = "https://amoret.app.n8n.cloud"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"

# --- Utility Functions (Adapted from node-analyzer.py) ---
def _get_first_output_item(output_data):
    """Safely extract the first item from node output."""
    if not output_data or not isinstance(output_data, list):
        return None
    if not output_data[0] or not isinstance(output_data[0], list):
        return None
    if not output_data[0][0]:
        return None
    return output_data[0][0]

def _extract_llm_data(node, item):
    """Extract LLM-specific data: content, tokens, model."""
    choices = item.get("choices", [])
    if choices and isinstance(choices, list):
        msg = choices[0].get("message", {})
        content = msg.get("content", "")
        node["llm_output"] = {
            "content": content,
            "length_chars": len(content),
            "finish_reason": choices[0].get("finish_reason", ""),
        }

    usage = item.get("usage", {})
    if usage:
        node["llm_tokens"] = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cost": usage.get("cost", 0),
        }

    node["llm_model"] = item.get("model", "")
    node["llm_provider"] = item.get("provider", "")

def _extract_routing_flags(node, item):
    """Extract boolean routing/skip flags from node output."""
    flag_keys = [
        "skip_neo4j", "skip_graph", "skip_llm", "skip_reranker",
        "fallback", "embedding_fallback", "empty_database",
        "is_simple", "is_decomposed", "needs_decomposition",
        "reranked", "hyde_success",
    ]
    for key in flag_keys:
        if key in item:
            node["routing_flags"][key] = item[key]
    if "fallback_response" in item:
        node["routing_flags"]["has_fallback_response"] = True

# --- Core N8n API Interaction ---
def n8n_api_call(path, timeout=30):
    """Call n8n REST API."""
    url = f"{N8N_HOST}/api/v1{path}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-N8N-API-KEY": N8N_API_KEY
    }
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  ERROR: n8n API HTTP error for path '{path}': {e.code} — {body}")
        return None
    except Exception as e:
        print(f"  ERROR: n8n API general error for path '{path}': {e}")
        return None

def parse_rich_node(name, run, node_keywords):
    """Extract rich data from a single node execution."""
    node = {
        "name": name,
        "duration_ms": run.get("executionTime", 0),
        "status": "error" if run.get("error") else "success",
        "error": None,
        "llm_output": None,
        "llm_tokens": None,
        "llm_model": None,
        "llm_provider": None,
        "routing_flags": {},
        "items_in": 0,
        "items_out": 0,
        "full_input_data": None,
        "full_output_data": None,
        "retrieval_count": None,
        "active_branches": None,
        "total_branches": None,
    }

    if run.get("error"):
        err = run["error"]
        node["error"] = err.get("message", str(err)) if isinstance(err, dict) else str(err)

    input_data = run.get("inputData", {}).get("main", [])
    output_data = run.get("data", {}).get("main", [])
    if input_data:
        node["items_in"] = sum(len(d) if isinstance(d, list) else 0 for d in input_data)
        node["full_input_data"] = input_data
    if output_data:
        node["items_out"] = sum(len(d) if isinstance(d, list) else 0 for d in output_data)
        node["full_output_data"] = output_data

    first_item_output = _get_first_output_item(output_data)
    if first_item_output:
        _extract_llm_data(node, first_item_output)
        _extract_routing_flags(node, first_item_output)

        if "results" in first_item_output and isinstance(first_item_output["results"], list):
            node["retrieval_count"] = len(first_item_output["results"])

    return node

def fetch_and_parse_execution(exec_id):
    """Fetches and parses a single N8n execution with full node data."""
    raw_execution = n8n_api_call(f"/executions/{exec_id}?includeData=true")
    if not raw_execution:
        return None

    # Simulate WORKFLOW_IDS and node type checking for basic display
    # (These are not used for functional routing but for display classification)
    LLM_NODE_KEYWORDS = ["llm", "generation", "chat", "completion", "gpt", "hyde", "entity extraction",
                      "query decomposer", "answer", "synthesis"]
    ROUTING_NODE_KEYWORDS = ["router", "switch", "if", "branch"] # Simplified for display

    execution_data = {
        "execution_id": raw_execution.get("id", "N/A"),
        "status": raw_execution.get("status", "N/A"),
        "started_at": raw_execution.get("startedAt", "N/A"),
        "stopped_at": raw_execution.get("stoppedAt", "N/A"),
        "duration_ms": 0,
        "workflow_name": raw_execution.get("workflowData", {}).get("name", "N/A"),
        "nodes": []
    }

    if execution_data["started_at"] != "N/A" and execution_data["stopped_at"] != "N/A":
        try:
            s = datetime.fromisoformat(execution_data["started_at"].replace("Z", "+00:00"))
            e = datetime.fromisoformat(execution_data["stopped_at"].replace("Z", "+00:00"))
            execution_data["duration_ms"] = int((e - s).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass

    run_data = raw_execution.get("data", {}).get("resultData", {}).get("runData", {})
    if not run_data:
        return execution_data

    # Attempt to extract trigger query from Webhook node if present
    trigger_query = "N/A"
    for node_name, runs in run_data.items():
        if node_name.lower() == "webhook" and isinstance(runs, list) and runs:
            first_run = runs[0]
            first_input_item = _get_first_output_item(first_run.get("data", {}).get("main", []))
            if first_input_item and first_input_item.get("body"):
                trigger_query = first_input_item["body"].get("query", first_input_item["body"].get("question", ""))
                break
    execution_data["trigger_query"] = trigger_query[:300]


    for node_name, node_runs in run_data.items():
        if not isinstance(node_runs, list):
            continue
        for run in node_runs:
            parsed_node = parse_rich_node(node_name, run, {"LLM": LLM_NODE_KEYWORDS, "ROUTING": ROUTING_NODE_KEYWORDS})
            execution_data["nodes"].append(parsed_node)
    
    execution_data["node_count"] = len(execution_data["nodes"])
    return execution_data

# --- Main execution loop ---
output_dir = "n8n_analysis_results"
os.makedirs(output_dir, exist_ok=True)

if __name__ == "__main__":
    import argparse
    from importlib.machinery import SourceFileLoader

    # Dynamically load node-analyzer.py to access WORKFLOW_IDS and fetch functions
    EVAL_DIR = os.path.join(os.path.dirname(__file__), 'eval')
    sys.path.insert(0, EVAL_DIR)
    try:
        node_analyzer = SourceFileLoader("node_analyzer", os.path.join(EVAL_DIR, "node-analyzer.py")).load_module()
    except Exception as e:
        print(f"Error loading node-analyzer.py: {e}")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Analyze N8n Executions")
    parser.add_argument("--pipeline", type=str, choices=node_analyzer.WORKFLOW_IDS.keys(),
                        help="Specify a pipeline to analyze (e.g., 'standard', 'graph'). Fetches recent executions.")
    parser.add_argument("--limit", type=int, default=5,
                        help="Number of recent executions to fetch for the specified pipeline. Defaults to 5.")
    parser.add_argument("--execution-id", type=str, help="Specify a single execution ID to analyze (overrides --pipeline and --limit)")
    args = parser.parse_args()

    exec_ids_to_process = []
    if args.execution_id:
        exec_ids_to_process.append(args.execution_id)
    elif args.pipeline:
        print(f"Fetching last {args.limit} executions for pipeline '{args.pipeline}'...")
        # fetch_rich_executions returns parsed executions, we need their IDs
        recent_executions = node_analyzer.fetch_rich_executions(args.pipeline, limit=args.limit)
        if recent_executions:
            exec_ids_to_process = [ex["execution_id"] for ex in recent_executions]
            print(f"Found {len(exec_ids_to_process)} executions: {', '.join(exec_ids_to_process)}")
        else:
            print(f"No recent executions found for pipeline '{args.pipeline}'.")
            sys.exit(0)
    else:
        print("Please specify either --pipeline or --execution-id.")
        sys.exit(1)

    for exec_id in exec_ids_to_process:
        print(f"\\n{'='*80}")
        print(f"Analyzing N8n Execution ID: {exec_id}")
        print(f"{'='*80}")

        execution_details = fetch_and_parse_execution(exec_id)

        if execution_details:
            output_filepath = os.path.join(output_dir, f"execution_{exec_id}.json")
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(execution_details, f, ensure_ascii=False, indent=2)
            print(f"  Details saved to {output_filepath}")

            print(f"  Workflow Name: {execution_details.get('workflow_name', 'N/A')}")
            print(f"  Status: {execution_details.get('status', 'N/A')}")
            print(f"  Duration: {execution_details.get('duration_ms', 0)}ms")
            print(f"  Trigger Query: {execution_details.get('trigger_query', 'N/A')}")
            print(f"  Nodes in execution: {execution_details.get('node_count', 0)}")

            for node in execution_details["nodes"]:
                print(f"\\n    --- Node: {node.get('name', 'Unnamed Node')} ---")
                print(f"      Status: {node.get('status', 'N/A')}")
                print(f"      Duration: {node.get('duration_ms', 0)}ms")
                if node.get('error'):
                    print(f"      Error: {node['error']}")

                # Check if full_input_data is not empty before printing its presence
                if node.get('full_input_data') and len(node['full_input_data']) > 0:
                    print(f"      Full Input Data: (present, see JSON file for details)")
                else:
                    print(f"      Full Input Data: (empty or N/A)")

                # Check if full_output_data is not empty before printing its presence
                if node.get('full_output_data') and len(node['full_output_data']) > 0:
                    print(f"      Full Output Data: (present, see JSON file for details)")
                else:
                    print(f"      Full Output Data: (empty or N/A)")


                if node.get('llm_output'):
                    llm_out = node['llm_output']
                    print(f"      LLM Output Chars: {llm_out.get('length_chars', 0)}")
                    print(f"      LLM Output Content: {llm_out.get('content', '')[:500]}... (full content in JSON)")
                if node.get('llm_tokens'):
                    llm_tokens = node['llm_tokens']
                    print(f"      LLM Tokens (Prompt/Completion/Total): "
                          f"{llm_tokens.get('prompt_tokens', 0)}/"
                          f"{llm_tokens.get('completion_tokens', 0)}/"
                          f"{llm_tokens.get('total_tokens', 0)}")
                if node.get('llm_model'):
                    print(f"      LLM Model: {node['llm_model']}")
                if node.get('llm_provider'):
                    print(f"      LLM Provider: {node['llm_provider']}")

                if node.get('routing_flags'):
                    print(f"      Routing Flags: {json.dumps(node['routing_flags'])}")

                if node.get('items_in') is not None:
                    print(f"      Items In: {node['items_in']}")
                if node.get('items_out') is not None:
                    print(f"      Items Out: {node['items_out']}")
                if node.get('retrieval_count') is not None:
                    print(f"      Retrieval Count: {node['retrieval_count']}")
                if node.get('active_branches') is not None:
                    print(f"      Active Branches: {node['active_branches']} out of {node['total_branches']}")
        else:
            print(f"  Could not fetch execution details for ID {exec_id}. Check N8n API key or execution ID.")
print(f"\n{'='*80}")
print("N8n Execution Analysis Complete.")
print(f"\n{'='*80}\n")
