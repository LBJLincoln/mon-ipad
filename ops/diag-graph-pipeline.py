#!/usr/bin/env python3
"""
Graph RAG Pipeline Diagnosis — S97
Investigate why Graph pipeline returns "Unknown" after Groq→LiteLLM migration.
"""

import socket
import ssl
import json
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

# ── IPv4 monkey-patch ──
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(*args, **kwargs):
    return [r for r in _orig_getaddrinfo(*args, **kwargs) if r[0] == socket.AF_INET]
socket.getaddrinfo = _ipv4_only

# ── SSL no-verify context ──
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = "https://lbjlincoln-nomos-rag-engine.hf.space"
WORKFLOW_ID = "6257AfT1l4FMC6lY"

def api_request(method, path, data=None, headers=None, cookie=None):
    """Make HTTP request with IPv4+SSL handling."""
    url = f"{BASE}{path}"
    if data is not None:
        if isinstance(data, dict):
            data = json.dumps(data).encode("utf-8")
        elif isinstance(data, str):
            data = data.encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=60)
        body = resp.read().decode("utf-8")
        # Extract Set-Cookie if present
        set_cookie = resp.headers.get("Set-Cookie", "")
        return {"status": resp.status, "body": body, "set_cookie": set_cookie}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return {"status": e.code, "body": body, "set_cookie": ""}
    except Exception as e:
        return {"status": 0, "body": str(e), "set_cookie": ""}

# ═══════════════════════════════════════════════════
# STEP 1: Login to n8n
# ═══════════════════════════════════════════════════
print("=" * 70)
print("STEP 1: Login to n8n S1")
print("=" * 70)

login_data = {
    "emailOrLdapLoginId": "ci@nomos.ai",
    "password": "CI-Nomos-2026!"
}
resp = api_request("POST", "/rest/login", data=login_data)
print(f"  Status: {resp['status']}")

if resp['status'] != 200:
    print(f"  ERROR: Login failed: {resp['body'][:300]}")
    sys.exit(1)

# Parse cookie
cookie = ""
sc = resp['set_cookie']
if sc:
    # Extract n8n-auth cookie
    for part in sc.split(","):
        if "n8n-auth" in part:
            cookie = part.split(";")[0].strip()
            break
if not cookie:
    # Try from body
    login_body = json.loads(resp['body'])
    if 'data' in login_body and 'authToken' in login_body.get('data', {}):
        token = login_body['data']['authToken']
        cookie = f"n8n-auth={token}"

print(f"  Cookie: {cookie[:50]}...")
print(f"  Login body keys: {list(json.loads(resp['body']).get('data', {}).keys())[:10]}")

# ═══════════════════════════════════════════════════
# STEP 2: GET workflow definition
# ═══════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 2: GET Graph Workflow Definition")
print("=" * 70)

resp = api_request("GET", f"/rest/workflows/{WORKFLOW_ID}", cookie=cookie)
print(f"  Status: {resp['status']}")

if resp['status'] != 200:
    print(f"  ERROR: {resp['body'][:500]}")
    sys.exit(1)

wf_data = json.loads(resp['body'])
wf = wf_data.get('data', wf_data)  # n8n wraps in data
print(f"  Workflow name: {wf.get('name', 'N/A')}")
print(f"  Active: {wf.get('active', 'N/A')}")
print(f"  Version ID: {wf.get('versionId', 'N/A')}")

# ═══════════════════════════════════════════════════
# STEP 3: List ALL nodes with types
# ═══════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 3: ALL Nodes in Graph Pipeline")
print("=" * 70)

nodes = wf.get('nodes', [])
print(f"  Total nodes: {len(nodes)}\n")

for i, node in enumerate(nodes):
    name = node.get('name', 'unnamed')
    ntype = node.get('type', 'unknown')
    disabled = node.get('disabled', False)
    position = node.get('position', [0, 0])

    status_icon = "DISABLED" if disabled else "active"
    print(f"  [{i+1:2d}] {name}")
    print(f"       Type: {ntype} | Status: {status_icon}")

    # Extract key parameters for important nodes
    params = node.get('parameters', {})

    if 'neo4j' in ntype.lower() or 'neo4j' in name.lower():
        print(f"       >>> NEO4J NODE DETECTED <<<")
        if 'query' in params:
            q = params['query']
            print(f"       Cypher: {q[:200]}")
        if 'operation' in params:
            print(f"       Operation: {params['operation']}")

    if 'http' in ntype.lower() or 'httpRequest' in ntype:
        url_val = params.get('url', 'N/A')
        method_val = params.get('method', 'N/A')
        print(f"       URL: {url_val}")
        print(f"       Method: {method_val}")

    if 'openai' in ntype.lower() or 'llm' in name.lower() or 'chat' in ntype.lower():
        print(f"       >>> LLM NODE DETECTED <<<")
        model = params.get('model', params.get('options', {}).get('model', 'N/A'))
        print(f"       Model: {model}")
        # Check for resource/credentials reference
        if 'resource' in params:
            print(f"       Resource: {params['resource']}")
        # Dump all params keys
        print(f"       Params keys: {list(params.keys())}")

    if 'code' in ntype.lower() or 'function' in ntype.lower():
        code = params.get('jsCode', params.get('functionCode', params.get('code', '')))
        if code:
            print(f"       Code preview: {code[:150]}...")

    if 'set' in ntype.lower() and 'set' in name.lower():
        print(f"       Params keys: {list(params.keys())}")

    print()

# ═══════════════════════════════════════════════════
# STEP 4: Deep dive — dump full config of LLM + Neo4j + HTTP nodes
# ═══════════════════════════════════════════════════
print("=" * 70)
print("STEP 4: Deep Dive — LLM, Neo4j, HTTP, Code node configs")
print("=" * 70)

for node in nodes:
    name = node.get('name', '')
    ntype = node.get('type', '')
    params = node.get('parameters', {})
    creds = node.get('credentials', {})

    # Show full config for important nodes
    important = any(kw in ntype.lower() + name.lower() for kw in [
        'neo4j', 'http', 'openai', 'llm', 'chat', 'groq', 'litellm',
        'generate', 'response', 'answer', 'unknown'
    ])

    if important:
        print(f"\n  --- {name} ({ntype}) ---")
        print(f"  Credentials: {json.dumps(creds, indent=4)[:500]}")
        print(f"  Full params: {json.dumps(params, indent=4)[:1000]}")
        print()

# ═══════════════════════════════════════════════════
# STEP 5: Recent executions
# ═══════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 5: Recent Executions (last 3)")
print("=" * 70)

resp = api_request("GET", f"/rest/executions?workflowId={WORKFLOW_ID}&limit=3", cookie=cookie)
print(f"  Status: {resp['status']}")

if resp['status'] == 200:
    exec_data = json.loads(resp['body'])
    execs = exec_data.get('data', exec_data)

    # Handle different response shapes
    if isinstance(execs, dict) and 'results' in execs:
        execs = execs['results']
    elif isinstance(execs, dict) and 'data' in execs:
        execs = execs['data']

    if isinstance(execs, list):
        print(f"  Found {len(execs)} executions\n")

        for ex in execs[:3]:
            ex_id = ex.get('id', 'N/A')
            status = ex.get('status', ex.get('finished', 'N/A'))
            started = ex.get('startedAt', 'N/A')
            finished_at = ex.get('stoppedAt', 'N/A')
            mode = ex.get('mode', 'N/A')

            print(f"  Execution #{ex_id}")
            print(f"    Status: {status} | Mode: {mode}")
            print(f"    Started: {started}")
            print(f"    Finished: {finished_at}")

            # Check for execution data with node results
            if 'data' in ex and ex['data']:
                run_data = ex['data']
                if isinstance(run_data, str):
                    try:
                        run_data = json.loads(run_data)
                    except:
                        pass

                if isinstance(run_data, dict):
                    result_data = run_data.get('resultData', {})
                    run_data_nodes = result_data.get('runData', {})

                    if run_data_nodes:
                        print(f"    Node results ({len(run_data_nodes)} nodes):")
                        for node_name, node_runs in run_data_nodes.items():
                            if isinstance(node_runs, list) and len(node_runs) > 0:
                                last_run = node_runs[-1]
                                exec_status = "unknown"
                                error_msg = ""
                                output_preview = ""

                                if isinstance(last_run, dict):
                                    exec_status = last_run.get('executionStatus',
                                                    last_run.get('status', 'N/A'))
                                    if 'error' in last_run:
                                        err = last_run['error']
                                        if isinstance(err, dict):
                                            error_msg = err.get('message', str(err))[:200]
                                        else:
                                            error_msg = str(err)[:200]

                                    # Get output data
                                    out = last_run.get('data', {})
                                    if isinstance(out, dict):
                                        main_out = out.get('main', [[]])
                                        if main_out and isinstance(main_out, list) and len(main_out) > 0:
                                            first_output = main_out[0]
                                            if isinstance(first_output, list) and len(first_output) > 0:
                                                item = first_output[0]
                                                if isinstance(item, dict):
                                                    json_data = item.get('json', item)
                                                    output_preview = json.dumps(json_data)[:200]

                                status_str = f"{'FAIL' if error_msg else 'OK'} ({exec_status})"
                                print(f"      [{status_str}] {node_name}")
                                if error_msg:
                                    print(f"        ERROR: {error_msg}")
                                if output_preview:
                                    print(f"        Output: {output_preview}")

                    # Check last node output for "Unknown"
                    last_node = result_data.get('lastNodeExecuted', 'N/A')
                    print(f"    Last node executed: {last_node}")

                    # Check error
                    if 'error' in result_data:
                        print(f"    EXECUTION ERROR: {json.dumps(result_data['error'])[:300]}")

            print()
    else:
        print(f"  Unexpected shape: {type(execs)}")
        print(f"  Keys: {list(execs.keys()) if isinstance(execs, dict) else 'N/A'}")
        print(f"  Preview: {json.dumps(execs)[:500]}")
else:
    print(f"  ERROR: {resp['body'][:500]}")

# ═══════════════════════════════════════════════════
# STEP 5b: Get individual execution details
# ═══════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 5b: Detailed Execution Data (individual fetch)")
print("=" * 70)

# Re-fetch exec list to get IDs
resp = api_request("GET", f"/rest/executions?workflowId={WORKFLOW_ID}&limit=3", cookie=cookie)
if resp['status'] == 200:
    exec_data = json.loads(resp['body'])
    execs = exec_data.get('data', exec_data)
    if isinstance(execs, dict) and 'results' in execs:
        execs = execs['results']
    elif isinstance(execs, dict) and 'data' in execs:
        execs = execs['data']

    if isinstance(execs, list):
        for ex in execs[:3]:
            ex_id = ex.get('id', None)
            if not ex_id:
                continue

            print(f"\n  --- Fetching execution #{ex_id} ---")
            resp2 = api_request("GET", f"/rest/executions/{ex_id}", cookie=cookie)
            if resp2['status'] == 200:
                ex_detail = json.loads(resp2['body'])
                ex_d = ex_detail.get('data', ex_detail)

                # Navigate to run data
                data_field = ex_d.get('data', {})
                if isinstance(data_field, str):
                    try:
                        data_field = json.loads(data_field)
                    except:
                        data_field = {}

                result_data = data_field.get('resultData', {})
                run_data = result_data.get('runData', {})
                last_node = result_data.get('lastNodeExecuted', 'N/A')

                print(f"  Status: {ex_d.get('status', 'N/A')}")
                print(f"  Last node: {last_node}")
                print(f"  Nodes executed: {list(run_data.keys())}")

                # Dump each node's status and output
                for node_name, node_runs in run_data.items():
                    if not isinstance(node_runs, list):
                        continue
                    for run in node_runs:
                        if not isinstance(run, dict):
                            continue
                        status = run.get('executionStatus', 'N/A')
                        error = run.get('error', None)

                        # Get output
                        out = run.get('data', {})
                        output_str = ""
                        if isinstance(out, dict):
                            main_out = out.get('main', [[]])
                            if main_out and isinstance(main_out[0], list) and len(main_out[0]) > 0:
                                items = main_out[0]
                                for item in items[:2]:
                                    if isinstance(item, dict):
                                        j = item.get('json', item)
                                        output_str += json.dumps(j)[:300] + " "

                        marker = "FAIL" if error else "OK"
                        print(f"    [{marker}] {node_name} (status={status})")
                        if error:
                            err_msg = error.get('message', str(error)) if isinstance(error, dict) else str(error)
                            print(f"      ERROR: {err_msg[:300]}")
                        if output_str:
                            print(f"      Output: {output_str[:400]}")

                # Check for execution error
                if 'error' in result_data:
                    print(f"  EXECUTION ERROR: {json.dumps(result_data['error'])[:500]}")
            else:
                print(f"  Failed to fetch: {resp2['status']} - {resp2['body'][:200]}")

# ═══════════════════════════════════════════════════
# STEP 6: Check Neo4j Cypher queries in detail
# ═══════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 6: Neo4j Query Node Details")
print("=" * 70)

neo4j_found = False
for node in nodes:
    name = node.get('name', '')
    ntype = node.get('type', '')
    params = node.get('parameters', {})
    creds = node.get('credentials', {})

    if 'neo4j' in ntype.lower() or 'neo4j' in name.lower() or 'cypher' in name.lower():
        neo4j_found = True
        print(f"\n  Node: {name}")
        print(f"  Type: {ntype}")
        print(f"  Credentials: {json.dumps(creds, indent=2)}")
        print(f"  Full params:")
        print(json.dumps(params, indent=2)[:2000])

if not neo4j_found:
    print("  No Neo4j nodes found! Checking HTTP nodes for Neo4j API calls...")
    for node in nodes:
        params = node.get('parameters', {})
        url = params.get('url', '')
        body = json.dumps(params)
        if 'neo4j' in body.lower() or 'cypher' in body.lower():
            print(f"\n  Found Neo4j reference in: {node.get('name', 'N/A')}")
            print(f"  Type: {node.get('type', 'N/A')}")
            print(f"  Params: {json.dumps(params, indent=2)[:1000]}")

# ═══════════════════════════════════════════════════
# STEP 7: Test webhook directly
# ═══════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 7: Direct Webhook Test")
print("=" * 70)

webhook_url = f"{BASE}/webhook/ff622742-6d71-4e91-af71-b5c666088717"
test_payload = {
    "query": "Quelles entites sont liees aux normes IFRS?",
    "sector": "finance",
    "disable_acl": True
}

print(f"  URL: {webhook_url}")
print(f"  Payload: {json.dumps(test_payload)}")
print(f"  Sending...")

start_time = time.time()

try:
    data = json.dumps(test_payload).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    resp = urllib.request.urlopen(req, context=ctx, timeout=120)
    body = resp.read().decode("utf-8")
    elapsed = time.time() - start_time

    print(f"  Status: {resp.status}")
    print(f"  Time: {elapsed:.1f}s")

    try:
        parsed = json.loads(body)
        print(f"  Response type: {type(parsed).__name__}")
        if isinstance(parsed, list):
            for item in parsed:
                print(f"  Item: {json.dumps(item, ensure_ascii=False)[:500]}")
        elif isinstance(parsed, dict):
            print(f"  Response: {json.dumps(parsed, ensure_ascii=False)[:800]}")
        else:
            print(f"  Raw: {body[:500]}")
    except:
        print(f"  Raw body: {body[:500]}")

except urllib.error.HTTPError as e:
    elapsed = time.time() - start_time
    body = e.read().decode("utf-8") if e.fp else ""
    print(f"  HTTP ERROR: {e.code}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Body: {body[:500]}")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"  EXCEPTION: {e}")
    print(f"  Time: {elapsed:.1f}s")

# ═══════════════════════════════════════════════════
# STEP 8: Test LiteLLM proxy directly
# ═══════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 8: Test LiteLLM Proxy (S7) directly")
print("=" * 70)

litellm_url = "https://lbjlincoln-nomos-rag-engine-7.hf.space"

# Health check
print("\n  8a. Health check...")
try:
    req = urllib.request.Request(f"{litellm_url}/health", method="GET")
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    body = resp.read().decode("utf-8")
    print(f"  Health: {resp.status} — {body[:300]}")
except Exception as e:
    print(f"  Health FAILED: {e}")

# Model list
print("\n  8b. Model list...")
try:
    req = urllib.request.Request(f"{litellm_url}/v1/models", method="GET")
    req.add_header("Authorization", "Bearer sk-litellm-nomos-2026")
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    body = resp.read().decode("utf-8")
    models = json.loads(body)
    if 'data' in models:
        for m in models['data'][:10]:
            print(f"    Model: {m.get('id', 'N/A')}")
    else:
        print(f"  Models response: {body[:500]}")
except Exception as e:
    print(f"  Models FAILED: {e}")

# Chat completion test
print("\n  8c. Chat completion test (model=smart)...")
try:
    chat_payload = {
        "model": "smart",
        "messages": [{"role": "user", "content": "Hello, test."}],
        "max_tokens": 50
    }
    data = json.dumps(chat_payload).encode("utf-8")
    req = urllib.request.Request(f"{litellm_url}/v1/chat/completions", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer sk-litellm-nomos-2026")
    resp = urllib.request.urlopen(req, context=ctx, timeout=30)
    body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    print(f"  Status: {resp.status}")
    if 'choices' in parsed and len(parsed['choices']) > 0:
        content = parsed['choices'][0].get('message', {}).get('content', 'N/A')
        print(f"  Response: {content[:200]}")
        print(f"  Model used: {parsed.get('model', 'N/A')}")
    else:
        print(f"  Response: {body[:300]}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8") if e.fp else ""
    print(f"  FAILED: HTTP {e.code} — {body[:400]}")
except Exception as e:
    print(f"  FAILED: {e}")

# ═══════════════════════════════════════════════════
# STEP 9: Diagnosis summary
# ═══════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 9: Diagnosis Summary")
print("=" * 70)

# Collect LLM-related nodes
llm_nodes = []
for node in nodes:
    ntype = node.get('type', '')
    name = node.get('name', '')
    if any(kw in (ntype + name).lower() for kw in ['openai', 'llm', 'chat', 'groq', 'http']):
        llm_nodes.append(f"  - {name} ({ntype})")

print(f"\n  LLM-related nodes in workflow:")
for n in llm_nodes:
    print(n)

# Check for "Unknown" patterns in code nodes
print(f"\n  Checking Code nodes for 'Unknown' fallback...")
for node in nodes:
    ntype = node.get('type', '')
    params = node.get('parameters', {})
    if 'code' in ntype.lower() or 'function' in ntype.lower():
        code = params.get('jsCode', params.get('functionCode', params.get('code', '')))
        if 'unknown' in code.lower() or 'Unknown' in code:
            print(f"    FOUND 'Unknown' in: {node.get('name', 'N/A')}")
            # Find the line
            for i, line in enumerate(code.split('\n')):
                if 'unknown' in line.lower() or 'Unknown' in line:
                    print(f"      Line {i+1}: {line.strip()}")

print("\n  DIAGNOSIS COMPLETE — Check output above for root cause.")
print("=" * 70)
