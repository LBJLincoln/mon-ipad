import json, os, sys, traceback
from urllib import request
from datetime import datetime

N8N_HOST = 'https://amoret.app.n8n.cloud'
N8N_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A'
WORKFLOW_ID = 'LnTqRX4LZlI009Ks-3Jnp'
OUTPUT_PATH = '/home/user/mon-ipad/logs/diagnostics/standard-deep-analysis.json'

def n8n_get(path, timeout=90):
    url = f'{N8N_HOST}/api/v1{path}'
    headers = {'Accept': 'application/json', 'X-N8N-API-KEY': N8N_API_KEY}
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

def truncate(obj, max_len=500):
    """Truncate any value to max_len chars for readability."""
    s = str(obj)
    if len(s) > max_len:
        return s[:max_len] + f'... [TRUNCATED, total {len(s)} chars]'
    return s

def safe_json_summary(obj, max_len=500):
    """Create a readable summary of a JSON-like object."""
    if obj is None:
        return "null"
    if isinstance(obj, str):
        return truncate(obj, max_len)
    if isinstance(obj, (int, float, bool)):
        return str(obj)
    if isinstance(obj, list):
        if len(obj) == 0:
            return "[] (empty list)"
        summary = f"[list of {len(obj)} items] "
        # Show first item summary
        first = str(obj[0])
        return truncate(summary + first, max_len)
    if isinstance(obj, dict):
        keys = list(obj.keys())
        summary = f"{{dict with keys: {keys[:10]}}}"
        # Try to extract key values
        for key in ['query', 'question', 'text', 'output', 'response', 'answer', 'message', 'content']:
            if key in obj:
                summary += f" | {key}={truncate(str(obj[key]), 200)}"
        return truncate(summary, max_len)
    return truncate(str(obj), max_len)

def extract_question(run_data):
    """Try to extract the question/query from the execution's trigger/webhook node."""
    question = None
    # Check common trigger node names
    trigger_names = ['Webhook', 'webhook', 'When Called by Another Workflow', 'Execute Workflow Trigger']
    for node_name, node_runs in run_data.items():
        if any(t.lower() in node_name.lower() for t in ['webhook', 'trigger', 'when called', 'execute workflow']):
            if node_runs and len(node_runs) > 0:
                run = node_runs[0]
                # Check output data
                out_data = None
                if 'data' in run and 'main' in run['data']:
                    main = run['data']['main']
                    if main and len(main) > 0 and main[0] and len(main[0]) > 0:
                        out_data = main[0][0].get('json', {})
                if out_data:
                    for key in ['query', 'question', 'chatInput', 'input', 'text', 'message', 'body']:
                        if key in out_data:
                            val = out_data[key]
                            if isinstance(val, dict):
                                for subkey in ['query', 'question', 'chatInput', 'input', 'text', 'message']:
                                    if subkey in val:
                                        question = str(val[subkey])
                                        break
                            elif isinstance(val, str):
                                question = val
                            if question:
                                break
    return question

def extract_final_answer(run_data):
    """Try to extract the final response from the last node or response-building node."""
    answer = None
    # Check common response node names
    response_names = ['respond', 'response', 'output', 'final', 'answer', 'result', 'build']
    last_node_name = None
    last_node_data = None

    for node_name, node_runs in run_data.items():
        if any(r in node_name.lower() for r in response_names):
            if node_runs and len(node_runs) > 0:
                run = node_runs[0]
                if 'data' in run and 'main' in run['data']:
                    main = run['data']['main']
                    if main and len(main) > 0 and main[0] and len(main[0]) > 0:
                        out_json = main[0][0].get('json', {})
                        for key in ['output', 'response', 'answer', 'text', 'result', 'message', 'content']:
                            if key in out_json:
                                answer = str(out_json[key])
                                break
                        if not answer:
                            answer = truncate(str(out_json), 500)
        # Track last node for fallback
        last_node_name = node_name
        last_node_data = node_runs

    if not answer and last_node_data and len(last_node_data) > 0:
        run = last_node_data[0]
        if 'data' in run and 'main' in run.get('data', {}):
            main = run['data']['main']
            if main and len(main) > 0 and main[0] and len(main[0]) > 0:
                out_json = main[0][0].get('json', {})
                for key in ['output', 'response', 'answer', 'text', 'result', 'message', 'content']:
                    if key in out_json:
                        answer = str(out_json[key])
                        break
                if not answer:
                    answer = truncate(str(out_json), 500)

    return answer

def analyze_node(node_name, node_runs):
    """Analyze a single node's execution data."""
    if not node_runs or len(node_runs) == 0:
        return {"name": node_name, "status": "no_runs", "error": "No run data"}

    run = node_runs[0]  # Take first run
    result = {
        "name": node_name,
        "startTime": run.get("startTime"),
        "executionTime_ms": run.get("executionTime"),
        "executionStatus": run.get("executionStatus", "unknown"),
    }

    # Extract input data
    if 'inputData' in run and 'main' in run.get('inputData', {}):
        main_input = run['inputData']['main']
        if main_input and len(main_input) > 0 and main_input[0]:
            items = main_input[0]
            result["input_item_count"] = len(items)
            if len(items) > 0:
                result["input_summary"] = safe_json_summary(items[0].get('json', {}), 500)
        else:
            result["input_item_count"] = 0
            result["input_summary"] = "(empty)"
    else:
        result["input_item_count"] = "N/A"
        result["input_summary"] = "(no inputData.main)"

    # Extract output data
    if 'data' in run and 'main' in run.get('data', {}):
        main_output = run['data']['main']
        if main_output and len(main_output) > 0 and main_output[0]:
            items = main_output[0]
            result["output_item_count"] = len(items)
            if len(items) > 0:
                result["output_summary"] = safe_json_summary(items[0].get('json', {}), 500)
                # Extract specific keys for deeper analysis
                out_json = items[0].get('json', {})
                for key in ['output', 'response', 'answer', 'text', 'query', 'documents']:
                    if key in out_json:
                        result[f"output_{key}"] = truncate(str(out_json[key]), 300)
        else:
            result["output_item_count"] = 0
            result["output_summary"] = "(empty output)"
    else:
        result["output_item_count"] = "N/A"
        result["output_summary"] = "(no data.main)"

    # Check for errors
    if run.get("error"):
        result["error"] = truncate(str(run["error"]), 500)

    return result

def main():
    print("=" * 80)
    print(f"STANDARD PIPELINE DEEP ANALYSIS")
    print(f"Workflow ID: {WORKFLOW_ID}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("=" * 80)

    # Step 1: Fetch executions
    print("\n[1/3] Fetching last 15 executions with full node data...")
    try:
        resp = n8n_get(f'/executions?workflowId={WORKFLOW_ID}&limit=15&includeData=true')
    except Exception as e:
        print(f"ERROR fetching executions: {e}")
        traceback.print_exc()
        # Try without includeData first to see if workflow exists
        try:
            print("\nTrying without includeData to check workflow existence...")
            resp2 = n8n_get(f'/executions?workflowId={WORKFLOW_ID}&limit=5')
            print(f"Response keys: {list(resp2.keys()) if isinstance(resp2, dict) else type(resp2)}")
            if isinstance(resp2, dict) and 'data' in resp2:
                print(f"Found {len(resp2['data'])} executions (without full data)")
            elif isinstance(resp2, list):
                print(f"Found {len(resp2)} executions (without full data)")
        except Exception as e2:
            print(f"Also failed without includeData: {e2}")

        # Try listing all workflows to find the correct ID
        print("\nListing all workflows to find standard pipeline...")
        try:
            wfs = n8n_get('/workflows')
            if isinstance(wfs, dict) and 'data' in wfs:
                wf_list = wfs['data']
            elif isinstance(wfs, list):
                wf_list = wfs
            else:
                wf_list = []
            for wf in wf_list:
                print(f"  - ID: {wf.get('id')} | Name: {wf.get('name')} | Active: {wf.get('active')}")
        except Exception as e3:
            print(f"Failed to list workflows: {e3}")
        sys.exit(1)

    # Handle response format
    if isinstance(resp, dict) and 'data' in resp:
        executions = resp['data']
    elif isinstance(resp, list):
        executions = resp
    else:
        print(f"Unexpected response format: {type(resp)}, keys: {list(resp.keys()) if isinstance(resp, dict) else 'N/A'}")
        executions = []

    print(f"Retrieved {len(executions)} executions")

    if len(executions) == 0:
        print("No executions found. Checking workflow list...")
        try:
            wfs = n8n_get('/workflows')
            if isinstance(wfs, dict) and 'data' in wfs:
                wf_list = wfs['data']
            elif isinstance(wfs, list):
                wf_list = wfs
            else:
                wf_list = []
            for wf in wf_list:
                print(f"  - ID: {wf.get('id')} | Name: {wf.get('name')} | Active: {wf.get('active')}")
        except Exception as e:
            print(f"Failed to list workflows: {e}")
        sys.exit(1)

    # Step 2: Analyze each execution
    print("\n[2/3] Analyzing each execution node-by-node...")
    all_analyses = []
    all_node_stats = {}  # node_name -> {durations: [], errors: [], statuses: []}
    all_errors = []

    for i, ex in enumerate(executions):
        exec_id = ex.get('id', 'unknown')
        status = ex.get('status', ex.get('finished', 'unknown'))
        started = ex.get('startedAt', 'unknown')
        finished_at = ex.get('stoppedAt', ex.get('finishedAt', 'unknown'))

        print(f"\n--- Execution {i+1}/{len(executions)}: ID={exec_id} Status={status} Started={started} ---")

        exec_analysis = {
            "execution_id": exec_id,
            "status": status,
            "startedAt": started,
            "stoppedAt": finished_at,
            "nodes": [],
            "question": None,
            "final_answer": None,
            "has_errors": False,
            "error_nodes": [],
        }

        # Get run data
        run_data = None
        if ex.get('data') and ex['data'].get('resultData') and ex['data']['resultData'].get('runData'):
            run_data = ex['data']['resultData']['runData']
        elif ex.get('resultData') and ex['resultData'].get('runData'):
            run_data = ex['resultData']['runData']

        if not run_data:
            print(f"  No runData found for execution {exec_id}")
            # Try fetching individual execution
            try:
                print(f"  Fetching individual execution data...")
                single = n8n_get(f'/executions/{exec_id}?includeData=true')
                if single.get('data') and single['data'].get('resultData'):
                    run_data = single['data']['resultData'].get('runData', {})
                elif single.get('resultData'):
                    run_data = single['resultData'].get('runData', {})
            except Exception as e:
                print(f"  Failed to fetch individual execution: {e}")

        if not run_data:
            exec_analysis["notes"] = "No runData available"
            all_analyses.append(exec_analysis)
            continue

        # Extract question
        question = extract_question(run_data)
        exec_analysis["question"] = question
        print(f"  Question: {truncate(question or 'NOT FOUND', 120)}")

        # Analyze each node
        # Sort nodes by start time if possible
        node_order = []
        for node_name, node_runs in run_data.items():
            start_time = None
            if node_runs and len(node_runs) > 0:
                start_time = node_runs[0].get('startTime', 0)
            node_order.append((node_name, start_time or 0))
        node_order.sort(key=lambda x: x[1])

        for node_name, _ in node_order:
            node_runs = run_data[node_name]
            node_info = analyze_node(node_name, node_runs)
            exec_analysis["nodes"].append(node_info)

            # Track stats
            if node_name not in all_node_stats:
                all_node_stats[node_name] = {"durations": [], "errors": 0, "runs": 0, "statuses": []}
            all_node_stats[node_name]["runs"] += 1
            if node_info.get("executionTime_ms"):
                all_node_stats[node_name]["durations"].append(node_info["executionTime_ms"])
            all_node_stats[node_name]["statuses"].append(node_info.get("executionStatus", "unknown"))

            if node_info.get("error"):
                all_node_stats[node_name]["errors"] += 1
                exec_analysis["has_errors"] = True
                exec_analysis["error_nodes"].append(node_name)
                all_errors.append({
                    "execution_id": exec_id,
                    "node": node_name,
                    "error": node_info["error"],
                    "question": question
                })

            duration_str = f"{node_info.get('executionTime_ms', '?')}ms"
            status_str = node_info.get('executionStatus', '?')
            in_count = node_info.get('input_item_count', '?')
            out_count = node_info.get('output_item_count', '?')
            err_str = f" ERROR: {truncate(node_info.get('error', ''), 80)}" if node_info.get('error') else ""
            print(f"  [{status_str}] {node_name}: {duration_str} | in={in_count} out={out_count}{err_str}")

        # Extract final answer
        final_answer = extract_final_answer(run_data)
        exec_analysis["final_answer"] = truncate(final_answer, 500) if final_answer else None
        print(f"  Final Answer: {truncate(final_answer or 'NOT FOUND', 150)}")

        all_analyses.append(exec_analysis)

    # Step 3: Cross-execution summary
    print("\n" + "=" * 80)
    print("CROSS-EXECUTION SUMMARY")
    print("=" * 80)

    total = len(all_analyses)
    successful = sum(1 for a in all_analyses if a["status"] in ["success", True, "finished"])
    with_errors = sum(1 for a in all_analyses if a["has_errors"])
    with_questions = sum(1 for a in all_analyses if a["question"])
    with_answers = sum(1 for a in all_analyses if a["final_answer"])

    print(f"\nExecution Overview:")
    print(f"  Total executions: {total}")
    print(f"  Successful: {successful}")
    print(f"  With errors: {with_errors}")
    print(f"  Questions extracted: {with_questions}")
    print(f"  Answers produced: {with_answers}")

    print(f"\nNode Performance Summary:")
    print(f"{'Node Name':<45} {'Runs':>5} {'Avg ms':>8} {'Max ms':>8} {'Errors':>7}")
    print("-" * 80)
    for node_name, stats in sorted(all_node_stats.items(), key=lambda x: -sum(x[1]["durations"])/(len(x[1]["durations"]) or 1)):
        avg_dur = sum(stats["durations"]) / len(stats["durations"]) if stats["durations"] else 0
        max_dur = max(stats["durations"]) if stats["durations"] else 0
        print(f"  {node_name:<43} {stats['runs']:>5} {avg_dur:>8.0f} {max_dur:>8.0f} {stats['errors']:>7}")

    # Error patterns
    if all_errors:
        print(f"\nError Patterns ({len(all_errors)} total errors):")
        error_by_node = {}
        for err in all_errors:
            node = err["node"]
            if node not in error_by_node:
                error_by_node[node] = []
            error_by_node[node].append(err)
        for node, errs in sorted(error_by_node.items(), key=lambda x: -len(x[1])):
            print(f"\n  {node}: {len(errs)} errors")
            for err in errs[:3]:
                print(f"    - Exec {err['execution_id']}: {truncate(err['error'], 200)}")
    else:
        print("\nNo errors found across all executions.")

    # Typical data flow
    print(f"\nTypical Node Execution Order (from most recent successful execution):")
    for a in all_analyses:
        if a["status"] in ["success", True, "finished"] and a["nodes"]:
            for j, node in enumerate(a["nodes"]):
                in_s = truncate(node.get("input_summary", "N/A"), 80)
                out_s = truncate(node.get("output_summary", "N/A"), 80)
                print(f"  {j+1}. {node['name']} ({node.get('executionTime_ms', '?')}ms)")
                print(f"     In:  {in_s}")
                print(f"     Out: {out_s}")
            break

    # Build full report JSON
    report = {
        "metadata": {
            "workflow_id": WORKFLOW_ID,
            "pipeline": "standard",
            "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
            "executions_analyzed": total,
        },
        "summary": {
            "total_executions": total,
            "successful": successful,
            "with_errors": with_errors,
            "questions_extracted": with_questions,
            "answers_produced": with_answers,
        },
        "node_stats": {
            name: {
                "runs": stats["runs"],
                "avg_duration_ms": round(sum(stats["durations"]) / len(stats["durations"]), 1) if stats["durations"] else None,
                "max_duration_ms": max(stats["durations"]) if stats["durations"] else None,
                "min_duration_ms": min(stats["durations"]) if stats["durations"] else None,
                "error_count": stats["errors"],
                "status_distribution": dict((s, stats["statuses"].count(s)) for s in set(stats["statuses"])),
            }
            for name, stats in all_node_stats.items()
        },
        "error_patterns": [
            {
                "node": err["node"],
                "execution_id": err["execution_id"],
                "error": err["error"],
                "question": err.get("question"),
            }
            for err in all_errors
        ],
        "executions": all_analyses,
    }

    # Save report
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to: {OUTPUT_PATH}")
    print(f"Report size: {os.path.getsize(OUTPUT_PATH)} bytes")

if __name__ == '__main__':
    main()
