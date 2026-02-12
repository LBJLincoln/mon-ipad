import json
import os
import sys
from importlib.machinery import SourceFileLoader

# Set up paths and N8n credentials
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = REPO_ROOT
sys.path.append(EVAL_DIR) # Add eval directory to Python path

N8N_HOST = os.environ.get("N8N_HOST", "https://amoret.app.n8n.cloud")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A")
os.environ["N8N_API_KEY"] = N8N_API_KEY # Ensure it's set for imported modules

# Load node-analyzer as a module
node_analyzer = SourceFileLoader("node_analyzer", os.path.join(EVAL_DIR, "node-analyzer.py")).load_module()

# Load docs/data.json
DATA_FILE = os.path.join(os.path.dirname(REPO_ROOT), "docs", "data.json")
with open(DATA_FILE, 'r') as f:
    data_json = json.load(f)

# Get the 5 execution IDs for the "standard" pipeline
standard_execution_ids = [
    qt["execution_id"]
    for qt in data_json["quick_tests"]
    if qt["pipeline"] == "standard" and qt.get("execution_id")
]

print(f"Found {len(standard_execution_ids)} standard pipeline execution IDs from quick_tests.")
for eid in standard_execution_ids:
    print(f"  - {eid}")

if not standard_execution_ids:
    print("No standard execution IDs found to analyze.")
    sys.exit(0)

# Fetch recent executions for the "standard" pipeline
# We need to fetch enough to make sure our specific 5 are included.
# Let's fetch 20 to be safe.
print("
Fetching recent executions for 'standard' pipeline from N8n API...")
recent_standard_executions = node_analyzer.fetch_rich_executions("standard", limit=20)

if not recent_standard_executions:
    print("Failed to fetch recent standard executions. Check N8n API key and host.")
    sys.exit(1)

print(f"Fetched {len(recent_standard_executions)} recent standard executions.")

# Analyze each specific execution
for target_exec_id in standard_execution_ids:
    found_raw_exec = None
    for raw_exec in recent_standard_executions:
        if raw_exec.get("execution_id") == target_exec_id:
            found_raw_exec = raw_exec
            break
    
    if found_raw_exec:
        print(f"
{'='*80}")
        print(f"Analyzing Execution ID: {target_exec_id} (Query: {found_raw_exec.get('trigger_query', 'N/A')})")
        print(f"{'='*80}")
        
        # We already have the parsed execution from fetch_rich_executions
        # If parse_rich_execution is called again, it uses the raw data
        parsed_execution = node_analyzer.parse_rich_execution(found_raw_exec, "standard")
        
        if parsed_execution:
            print(f"  Status: {parsed_execution.get('status', 'N/A')}")
            print(f"  Duration: {parsed_execution.get('duration_ms', 0)}ms")
            print(f"  Trigger Query: {parsed_execution.get('trigger_query', 'N/A')}")
            print(f"  Nodes in execution: {parsed_execution.get('node_count', 0)}")

            for node in parsed_execution["nodes"]:
                issues = node_analyzer.detect_node_issues(node)
                status_indicator = "ERR" if node.get("error") else ("WARN" if issues else "OK")
                print(f"
    --- Node: {node.get('name', 'Unnamed Node')} [{status_indicator}] ---")
                print(f"      Status: {node.get('status', 'N/A')}")
                print(f"      Duration: {node.get('duration_ms', 0)}ms")
                if node.get('error'):
                    print(f"      Error: {node['error']}")

                if node.get('llm_output'):
                    llm_out = node['llm_output']
                    print(f"      LLM Output Chars: {llm_out.get('length_chars', 0)}")
                    print(f"      LLM Output Content: {llm_out.get('content', '')[:100]}... (full in raw)")
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
                if node.get('retrieval_metadata'):
                    meta = node['retrieval_metadata']
                    if meta.get("warnings"):
                        print(f"      Retrieval Warnings: {meta['warnings']}")
                    if meta.get("total_unique_docs") == 0:
                         print(f"      Retrieval: ZERO DOCUMENTS RETRIEVED")


                for issue in issues:
                    print(f"      ⚠ ISSUE [{issue['severity'].upper()}]: {issue['type']} - {issue['detail']}")
                    print(f"        Suggestion: {issue['suggestion']}")
        else:
            print(f"  Failed to parse execution details for {target_exec_id}.")
    else:
        print(f"
  Execution ID {target_exec_id} not found in recent fetches. It might be too old or there was an error fetching.")

print("
Analysis complete.")
