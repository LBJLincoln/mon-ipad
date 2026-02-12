import os
import sys
import json
from importlib.machinery import SourceFileLoader

# Set N8n credentials from the user's prompt BEFORE importing node_analyzer
os.environ["N8N_HOST"] = "https://amoret.app.n8n.cloud"
os.environ["N8N_API_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A"

# Add the 'eval' directory to the Python path to import node_analyzer
EVAL_DIR = os.path.join(os.path.dirname(__file__), 'eval')
REPO_ROOT = os.path.dirname(EVAL_DIR)
sys.path.insert(0, EVAL_DIR)

try:
    node_analyzer = SourceFileLoader("node_analyzer", os.path.join(EVAL_DIR, "node-analyzer.py")).load_module()
except Exception as e:
    print(f"Error loading node-analyzer.py: {e}")
    sys.exit(1)

execution_ids = ["19305", "19306", "19311"]

for exec_id in execution_ids:
    print(f"\n{'='*80}")
    print(f"Analyzing N8n Execution ID: {exec_id}")
    print(f"{'='*80}")

    execution = node_analyzer.fetch_execution_by_id(exec_id)

    if execution:
        print(f"  Pipeline: {execution.get('pipeline', 'N/A')}")
        print(f"  Status: {execution.get('status', 'N/A')}")
        print(f"  Duration: {execution.get('duration_ms', 0)}ms")
        print(f"  Trigger Query: {execution.get('trigger_query', 'N/A')}")
        print(f"  Nodes in execution: {execution.get('node_count', 0)}")

        for node in execution.get('nodes', []):
            print(f"\n    --- Node: {node.get('name', 'Unnamed Node')} ---")
            print(f"      Status: {node.get('status', 'N/A')}")
            print(f"      Duration: {node.get('duration_ms', 0)}ms")
            if node.get('error'):
                print(f"      Error: {node['error']}")

            # Input Preview
            if node.get('input_preview'):
                print(f"      Input Preview: {node['input_preview'][:500]}...") # Truncate for readability
            else:
                print(f"      Input Preview: (empty or N/A)")

            # Output Preview
            if node.get('output_preview'):
                print(f"      Output Preview: {node['output_preview'][:500]}...") # Truncate for readability
            else:
                print(f"      Output Preview: (empty or N/A)")

            # LLM Details
            if node.get('llm_output'):
                llm_out = node['llm_output']
                print(f"      LLM Output Chars: {llm_out.get('length_chars', 0)}")
                print(f"      LLM Output Content: {llm_out.get('content', '')[:500]}...")
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

            # Routing Flags
            if node.get('routing_flags'):
                print(f"      Routing Flags: {json.dumps(node['routing_flags'])}")
            
            # Additional details from _parse_rich_node that might be useful
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
print("Analysis complete.")
print(f"\n{'='*80}\n")
