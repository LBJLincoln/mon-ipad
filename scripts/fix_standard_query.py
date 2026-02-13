
import os
import json
from urllib import request, error

# --- N8n Credentials (from user's prompt) ---
N8N_HOST = os.environ.get("N8N_HOST", "http://34.136.180.66:5678")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

WF_ID = "M12n4cmiVBoBusUe"
NODE_NAME = "Init & ACL Pre-Filter V3.4"
WORKFLOW_FILE = "workflows/live/standard.json"

def n8n_api(method, path, data=None):
    url = f"{N8N_HOST}/api/v1{path}"
    body = json.dumps(data).encode() if data else None
    req = request.Request(url, data=body, method=method,
        headers={"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"})
    try:
        with request.urlopen(req) as resp:
            return json.loads(resp.read())
    except error.HTTPError as e:
        body_content = e.read().decode() if e.fp else ""
        print(f"ERROR: n8n API HTTP error {e.code} for {path}: {body_content}")
        raise
    except Exception as e:
        print(f"ERROR: n8n API general error for {path}: {e}")
        raise

def update_workflow_node():
    print(f"Loading workflow from {WORKFLOW_FILE}...")
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        workflow_data = json.load(f)

    # Find the target node and update its jsCode
    found_node = False
    for node in workflow_data["nodes"]:
        if node.get("name") == NODE_NAME and node.get("type") == "n8n-nodes-base.code":
            old_js_code = node["parameters"]["jsCode"]
            
            # Simple string replacement - fix for the 'input.query' vs 'input.question'
            new_js_code = old_js_code.replace("input.query", "input.question")
            
            if old_js_code == new_js_code:
                print(f"WARNING: No changes detected in '{NODE_NAME}' node's jsCode. It might already be updated or the pattern changed.")
            else:
                node["parameters"]["jsCode"] = new_js_code
                print(f"Updated jsCode for node '{NODE_NAME}'.")
            found_node = True
            break

    if not found_node:
        print(f"ERROR: Node '{NODE_NAME}' not found in {WORKFLOW_FILE}.")
        return

    # --- Construct a clean payload for N8n API ---
    # Include required 'name' property
    clean_payload = {
        "nodes": workflow_data["nodes"],
        "connections": workflow_data["connections"],
        "name": workflow_data.get("name", "Unnamed Workflow"), # Add name back as it's required
    }
    
    # Handle settings separately as per N8n docs
    if "settings" in workflow_data:
        allowed_settings = {"executionOrder", "callerPolicy", "saveManualExecutions", "saveExecutionProgress"}
        clean_payload["settings"] = {k: v for k, v in workflow_data["settings"].items() if k in allowed_settings}

    print(f"Deactivating workflow {WF_ID}...")
    n8n_api("POST", f"/workflows/{WF_ID}/deactivate")
    
    print(f"Updating workflow {WF_ID} via N8n API...")
    n8n_api("PUT", f"/workflows/{WF_ID}", clean_payload)
    
    print(f"Activating workflow {WF_ID}...")
    n8n_api("POST", f"/workflows/{WF_ID}/activate")
    
    print(f"Workflow {WF_ID} updated and reactivated successfully.")

if __name__ == "__main__":
    try:
        update_workflow_node()
    except Exception as e:
        print(f"An error occurred: {e}")

