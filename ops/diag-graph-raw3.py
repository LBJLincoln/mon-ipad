#!/usr/bin/env python3
"""
Graph RAG — Deep deref + correct workflow filtering + output extraction
"""

import socket, ssl, json, sys
import urllib.request, urllib.error, http.cookiejar

_orig = socket.getaddrinfo
socket.getaddrinfo = lambda *a, **kw: [r for r in _orig(*a, **kw) if r[0] == socket.AF_INET]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = "https://lbjlincoln-nomos-rag-engine.hf.space"
WORKFLOW_ID = "6257AfT1l4FMC6lY"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(jar),
    urllib.request.HTTPSHandler(context=ctx)
)

def do_req(method, path, data=None, timeout=60):
    url = f"{BASE}{path}"
    if data and isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        resp = opener.open(req, timeout=timeout)
        return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8") if e.fp else "")
    except Exception as e:
        return 0, str(e)

def deep_deref(data_list, val, depth=0, max_depth=30, visited=None):
    """Recursively dereference string-integer references deeply."""
    if visited is None:
        visited = set()
    if depth > max_depth:
        return val

    # String digit = reference to index
    if isinstance(val, str) and val.isdigit():
        idx = int(val)
        if 0 <= idx < len(data_list) and idx not in visited:
            visited.add(idx)
            return deep_deref(data_list, data_list[idx], depth+1, max_depth, visited)
        return val

    if isinstance(val, dict):
        return {k: deep_deref(data_list, v, depth+1, max_depth, visited.copy()) for k, v in val.items()}

    if isinstance(val, list):
        return [deep_deref(data_list, item, depth+1, max_depth, visited.copy()) for item in val]

    return val

# Login
do_req("POST", "/rest/login", data={
    "emailOrLdapLoginId": "ci@nomos.ai", "password": "CI-Nomos-2026!"
})

# List executions ONLY for the Graph workflow
print(f"=== Fetching executions for workflow {WORKFLOW_ID} ===")
status, body = do_req("GET", f"/rest/executions?workflowId={WORKFLOW_ID}&limit=30")
data = json.loads(body)
results = data.get('data', {}).get('results', [])

# Filter and show
print(f"Total results: {len(results)}")
for ex in results[:10]:
    wf_id = ex.get('workflowId', '?')
    print(f"  #{ex['id']}: status={ex.get('status','?')}, workflowId={wf_id}, mode={ex.get('mode','?')}, started={ex.get('startedAt','?')[:19]}")

# Filter for Graph workflow only
graph_execs = [e for e in results if e.get('workflowId') == WORKFLOW_ID]
completed = [e for e in graph_execs if e.get('status') in ('success', 'error')]
print(f"\nGraph pipeline executions: {len(graph_execs)}")
print(f"  Completed: {len(completed)}")
print(f"  Running: {len([e for e in graph_execs if e.get('status') == 'running'])}")

# If no Graph-specific completed, check all and see what workflows they belong to
if not completed:
    print("\nNo completed Graph executions found. Checking ALL executions...")
    all_completed = [e for e in results if e.get('status') in ('success', 'error')]
    wf_ids = set()
    for e in all_completed:
        wf_ids.add(e.get('workflowId', '?'))
    print(f"Workflow IDs in results: {wf_ids}")

# Analyze the first Graph execution (even if running)
target_execs = completed if completed else [e for e in graph_execs if e.get('status') == 'running']
if not target_execs:
    target_execs = graph_execs[:2]

for ex in target_execs[:2]:
    ex_id = ex['id']
    ex_status = ex.get('status')
    print(f"\n{'='*70}")
    print(f"EXECUTION #{ex_id} — {ex_status} (wf={ex.get('workflowId','?')})")
    print(f"{'='*70}")

    status, body = do_req("GET", f"/rest/executions/{ex_id}")
    full = json.loads(body)
    if isinstance(full, dict) and 'data' in full:
        full = full['data']

    exec_data_raw = full.get('data', '')
    if isinstance(exec_data_raw, str):
        exec_data = json.loads(exec_data_raw)
    else:
        exec_data = exec_data_raw

    if not isinstance(exec_data, list):
        print(f"  Not a list: {type(exec_data).__name__}")
        continue

    print(f"  Data items: {len(exec_data)}")

    header = exec_data[0]
    rd_ref = header.get('resultData', '2')

    # Deep deref
    result_data = deep_deref(exec_data, rd_ref)

    if not isinstance(result_data, dict):
        print(f"  resultData deref: {type(result_data).__name__}")
        # Try manual
        if isinstance(rd_ref, str) and rd_ref.isdigit():
            idx = int(rd_ref)
            raw = exec_data[idx]
            print(f"  Raw at [{idx}]: {json.dumps(raw)[:500]}")
        continue

    last_node = result_data.get('lastNodeExecuted', 'N/A')
    error = result_data.get('error')
    run_data = result_data.get('runData', {})

    print(f"  Last node: {last_node}")

    if error:
        if isinstance(error, dict):
            print(f"\n  *** EXECUTION ERROR ***")
            print(f"  Message: {error.get('message', '?')}")
            print(f"  Node: {error.get('node', '?')}")
            desc = error.get('description', '')
            if desc:
                print(f"  Description: {str(desc)[:500]}")
        elif error is not None:
            print(f"  ERROR: {str(error)[:400]}")

    if not isinstance(run_data, dict):
        print(f"  runData type: {type(run_data).__name__}")
        continue

    print(f"  Nodes: {len(run_data)}")

    for node_name in run_data:
        node_runs = run_data[node_name]
        if not isinstance(node_runs, list):
            continue

        for run in node_runs:
            if not isinstance(run, dict):
                continue

            ns = run.get('executionStatus', 'N/A')
            ne = run.get('error', None)
            nt = run.get('executionTime', 0)

            out = run.get('data', {})
            out_items = []
            if isinstance(out, dict):
                main = out.get('main', [])
                if isinstance(main, list):
                    for branch in main:
                        if isinstance(branch, list):
                            for item in branch[:3]:
                                if isinstance(item, dict):
                                    j = item.get('json', item)
                                    out_items.append(j)

            flag = "FAIL" if ne else "OK"
            print(f"\n  [{flag}] {node_name} ({ns}, {nt}ms)")

            if ne:
                if isinstance(ne, dict):
                    print(f"    ERROR: {ne.get('message', str(ne))[:500]}")
                    if ne.get('description'):
                        print(f"    DESC: {str(ne['description'])[:300]}")
                else:
                    print(f"    ERROR: {str(ne)[:400]}")

            for j in out_items[:2]:
                if not isinstance(j, dict):
                    print(f"    Out: {json.dumps(j, ensure_ascii=False)[:400]}")
                    continue

                s = json.dumps(j, ensure_ascii=False)
                if len(s) > 600:
                    for k in ['response', 'answer', 'error', 'message',
                              'choices', 'hyde_document', 'cypher',
                              'query', 'skip_graph', 'context',
                              'total_sources', 'model', 'status',
                              'requestBody', 'fallback',
                              'embedding_fallback', 'content']:
                        if k in j:
                            v = j[k]
                            vs = json.dumps(v, ensure_ascii=False)
                            print(f"    .{k} = {vs[:500]}")
                    print(f"    Keys: {list(j.keys())[:20]}")
                else:
                    if 'Unknown' in s or 'unknown' in s:
                        print(f"    >>> UNKNOWN: {s}")
                    else:
                        print(f"    Out: {s[:500]}")

print("\n=== DONE ===")
