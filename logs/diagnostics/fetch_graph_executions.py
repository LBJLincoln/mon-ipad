import json, os, sys, time, traceback
from urllib import request
from datetime import datetime

N8N_HOST = 'https://amoret.app.n8n.cloud'
N8N_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A'
WORKFLOW_ID = '95x2BBAbJlLWZtWEJn6rb'
OUTPUT_PATH = '/home/user/mon-ipad/logs/diagnostics/graph-deep-analysis.json'

def n8n_get(path, timeout=90):
    url = f'{N8N_HOST}/api/v1{path}'
    headers = {'Accept': 'application/json', 'X-N8N-API-KEY': N8N_API_KEY}
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

def truncate(s, maxlen=500):
    s = str(s)
    if len(s) > maxlen:
        return s[:maxlen] + f'... [TRUNCATED, total {len(s)} chars]'
    return s

def safe_json_str(obj, maxlen=500):
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    return truncate(s, maxlen)

def extract_question(run_data):
    """Try to find the question/query from webhook or trigger node."""
    # Look for common trigger/webhook node names
    trigger_names = ['Webhook', 'webhook', 'When clicking', 'Execute Workflow Trigger',
                     'Execute Workflow', 'Start', 'Trigger']
    for node_name, node_runs in run_data.items():
        name_lower = node_name.lower()
        if any(t.lower() in name_lower for t in trigger_names):
            try:
                output = node_runs[0]['data']['main'][0][0]['json']
                # Look for question field
                for key in ['question', 'query', 'message', 'input', 'text', 'body', 'chatInput']:
                    if key in output:
                        return str(output[key])
                # If it has nested body
                if 'body' in output and isinstance(output['body'], dict):
                    for key in ['question', 'query', 'message', 'input', 'text', 'chatInput']:
                        if key in output['body']:
                            return str(output['body'][key])
                return safe_json_str(output, 300)
            except (KeyError, IndexError, TypeError):
                pass
    # Fallback: scan all nodes for a question field
    for node_name, node_runs in run_data.items():
        try:
            output = node_runs[0]['data']['main'][0][0]['json']
            for key in ['question', 'query', 'chatInput']:
                if key in output:
                    return str(output[key])
        except (KeyError, IndexError, TypeError):
            pass
    return '[QUESTION NOT FOUND]'

def extract_final_response(run_data):
    """Try to find the final answer from the last nodes."""
    # Look for common response/output node names
    response_names = ['respond', 'response', 'output', 'answer', 'result', 'send',
                      'Respond to Webhook', 'HTTP Response', 'Return']
    for node_name, node_runs in run_data.items():
        name_lower = node_name.lower()
        if any(t.lower() in name_lower for t in response_names):
            try:
                output = node_runs[0]['data']['main'][0][0]['json']
                for key in ['output', 'answer', 'response', 'text', 'message', 'result', 'body']:
                    if key in output:
                        return truncate(str(output[key]), 500)
                return safe_json_str(output, 500)
            except (KeyError, IndexError, TypeError):
                pass
    # Fallback: look at the node with highest startTime (last executed)
    last_node = None
    last_time = 0
    for node_name, node_runs in run_data.items():
        try:
            st = node_runs[0].get('startTime', 0)
            if st > last_time:
                last_time = st
                last_node = node_name
        except (KeyError, IndexError):
            pass
    if last_node:
        try:
            output = run_data[last_node][0]['data']['main'][0][0]['json']
            for key in ['output', 'answer', 'response', 'text', 'message', 'result']:
                if key in output:
                    return truncate(str(output[key]), 500)
            return safe_json_str(output, 500)
        except (KeyError, IndexError, TypeError):
            pass
    return '[RESPONSE NOT FOUND]'

def analyze_node(node_name, node_runs):
    """Analyze a single node's execution data."""
    results = []
    for run_idx, run in enumerate(node_runs):
        node_info = {
            'node_name': node_name,
            'run_index': run_idx,
            'startTime': run.get('startTime'),
            'executionTime': run.get('executionTime'),
            'executionStatus': run.get('executionStatus', 'unknown'),
            'error': None,
            'input_summary': None,
            'output_summary': None,
            'input_item_count': 0,
            'output_item_count': 0,
        }

        # Check for errors
        if 'error' in run:
            node_info['error'] = safe_json_str(run['error'], 500)

        # Extract input data
        try:
            input_data = run.get('inputData', {})
            if 'main' in input_data:
                all_inputs = []
                for connection in input_data['main']:
                    if connection:
                        node_info['input_item_count'] += len(connection)
                        for item in connection[:3]:  # first 3 items
                            all_inputs.append(item.get('json', {}))
                node_info['input_summary'] = safe_json_str(all_inputs, 500)
        except Exception as e:
            node_info['input_summary'] = f'[ERROR extracting input: {e}]'

        # Extract output data
        try:
            output_data = run.get('data', {})
            if 'main' in output_data:
                all_outputs = []
                for connection in output_data['main']:
                    if connection:
                        node_info['output_item_count'] += len(connection)
                        for item in connection[:3]:  # first 3 items
                            all_outputs.append(item.get('json', {}))
                    else:
                        all_outputs.append(None)  # null output branch
                node_info['output_summary'] = safe_json_str(all_outputs, 500)
            else:
                node_info['output_summary'] = '[NO main OUTPUT]'
        except Exception as e:
            node_info['output_summary'] = f'[ERROR extracting output: {e}]'

        results.append(node_info)
    return results

def get_execution_order(run_data):
    """Sort nodes by startTime to get execution order."""
    nodes = []
    for node_name, node_runs in run_data.items():
        try:
            st = node_runs[0].get('startTime', 0)
            nodes.append((node_name, st))
        except (KeyError, IndexError):
            nodes.append((node_name, 0))
    nodes.sort(key=lambda x: x[1])
    return [n[0] for n in nodes]

# ============ MAIN ============
print("=" * 80)
print(f"GRAPH PIPELINE DEEP ANALYSIS — Workflow {WORKFLOW_ID}")
print(f"Timestamp: {datetime.now().isoformat()}")
print("=" * 80)

# Step 1: Fetch executions
print("\n[1/3] Fetching last 15 executions with full node data...")
try:
    resp = n8n_get(f'/executions?workflowId={WORKFLOW_ID}&limit=15&includeData=true')
except Exception as e:
    print(f"ERROR fetching executions: {e}")
    traceback.print_exc()
    sys.exit(1)

executions = resp.get('data', [])
print(f"  -> Retrieved {len(executions)} executions")

if not executions:
    print("NO EXECUTIONS FOUND. The workflow may not have been triggered yet or the ID is wrong.")
    # Save empty report
    report = {
        'workflow_id': WORKFLOW_ID,
        'timestamp': datetime.now().isoformat(),
        'executions_found': 0,
        'error': 'No executions found for this workflow ID',
        'executions': [],
        'cross_execution_summary': {}
    }
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nEmpty report saved to {OUTPUT_PATH}")
    sys.exit(0)

# Step 2: Analyze each execution
print("\n[2/3] Analyzing each execution node-by-node...")
all_exec_reports = []
all_node_durations = {}  # node_name -> [durations]
all_node_errors = {}     # node_name -> count
all_errors = []
success_count = 0
error_count = 0

for idx, exc in enumerate(executions):
    exc_id = exc.get('id', 'unknown')
    status = exc.get('status', exc.get('finished', 'unknown'))
    started = exc.get('startedAt', 'unknown')
    finished_at = exc.get('stoppedAt', 'unknown')
    mode = exc.get('mode', 'unknown')

    print(f"\n--- Execution {idx+1}/{len(executions)}: ID={exc_id} status={status} ---")

    exec_report = {
        'execution_id': exc_id,
        'status': status,
        'started_at': started,
        'finished_at': finished_at,
        'mode': mode,
        'question': None,
        'final_response': None,
        'nodes': [],
        'node_count': 0,
        'total_duration_ms': 0,
        'has_errors': False,
        'error_details': [],
    }

    # Get run data
    try:
        run_data = exc.get('data', {}).get('resultData', {}).get('runData', {})
    except (AttributeError, TypeError):
        run_data = {}

    if not run_data:
        print(f"  [WARN] No runData for execution {exc_id}")
        exec_report['error_details'].append('No runData available')
        exec_report['has_errors'] = True
        error_count += 1
        all_exec_reports.append(exec_report)
        continue

    # Extract question and final response
    question = extract_question(run_data)
    final_response = extract_final_response(run_data)
    exec_report['question'] = truncate(question, 300)
    exec_report['final_response'] = truncate(final_response, 500)

    print(f"  Question: {truncate(question, 120)}")

    # Get execution order
    exec_order = get_execution_order(run_data)
    exec_report['node_count'] = len(exec_order)

    total_dur = 0
    for node_name in exec_order:
        node_runs = run_data[node_name]
        node_analyses = analyze_node(node_name, node_runs)
        for na in node_analyses:
            exec_report['nodes'].append(na)
            dur = na.get('executionTime', 0) or 0
            total_dur += dur

            # Track durations
            if node_name not in all_node_durations:
                all_node_durations[node_name] = []
            all_node_durations[node_name].append(dur)

            # Track errors
            if na.get('error'):
                exec_report['has_errors'] = True
                exec_report['error_details'].append({
                    'node': node_name,
                    'error': na['error']
                })
                if node_name not in all_node_errors:
                    all_node_errors[node_name] = 0
                all_node_errors[node_name] += 1
                all_errors.append({
                    'execution_id': exc_id,
                    'node': node_name,
                    'error': na['error']
                })

            status_str = na.get('executionStatus', '?')
            err_flag = ' [ERROR]' if na.get('error') else ''
            print(f"  [{status_str}] {node_name}: {dur}ms, in={na['input_item_count']} items, out={na['output_item_count']} items{err_flag}")

    exec_report['total_duration_ms'] = total_dur

    if exec_report['has_errors']:
        error_count += 1
    else:
        success_count += 1

    valid_answer = (final_response and
                    final_response != '[RESPONSE NOT FOUND]' and
                    len(final_response) > 10)
    exec_report['valid_answer'] = valid_answer
    print(f"  Final response valid: {valid_answer}")
    if valid_answer:
        print(f"  Response: {truncate(final_response, 150)}")

    all_exec_reports.append(exec_report)

# Step 3: Cross-execution summary
print("\n\n" + "=" * 80)
print("[3/3] CROSS-EXECUTION SUMMARY")
print("=" * 80)

# Node duration stats
print("\n--- Node Duration Stats (ms) ---")
node_stats = {}
for node_name, durations in sorted(all_node_durations.items(), key=lambda x: -max(x[1]) if x[1] else 0):
    if not durations:
        continue
    avg_d = sum(durations) / len(durations)
    max_d = max(durations)
    min_d = min(durations)
    node_stats[node_name] = {
        'avg_ms': round(avg_d, 1),
        'max_ms': max_d,
        'min_ms': min_d,
        'count': len(durations)
    }
    print(f"  {node_name}: avg={avg_d:.0f}ms, max={max_d}ms, min={min_d}ms (n={len(durations)})")

# Error summary
print(f"\n--- Error Summary ---")
print(f"  Successful executions: {success_count}/{len(executions)}")
print(f"  Errored executions: {error_count}/{len(executions)}")
if all_node_errors:
    print(f"  Nodes with errors:")
    for node_name, cnt in sorted(all_node_errors.items(), key=lambda x: -x[1]):
        print(f"    {node_name}: {cnt} errors")
else:
    print(f"  No node-level errors detected.")

# Common failure patterns
print(f"\n--- Common Failure Patterns ---")
error_msgs = {}
for err in all_errors:
    msg = err['error'][:200]
    if msg not in error_msgs:
        error_msgs[msg] = {'count': 0, 'nodes': set(), 'executions': []}
    error_msgs[msg]['count'] += 1
    error_msgs[msg]['nodes'].add(err['node'])
    error_msgs[msg]['executions'].append(err['execution_id'])

if error_msgs:
    for msg, info in sorted(error_msgs.items(), key=lambda x: -x[1]['count']):
        print(f"  [{info['count']}x] {msg}")
        print(f"       Nodes: {', '.join(info['nodes'])}")
else:
    print("  No recurring error patterns detected.")

# Bottleneck analysis
print(f"\n--- Bottleneck Nodes (by avg duration) ---")
sorted_nodes = sorted(node_stats.items(), key=lambda x: -x[1]['avg_ms'])
for node_name, stats in sorted_nodes[:10]:
    print(f"  {node_name}: avg={stats['avg_ms']}ms, max={stats['max_ms']}ms")

# Typical data flow
print(f"\n--- Typical Data Flow ---")
if all_exec_reports:
    # Use the first successful execution as template
    template = None
    for er in all_exec_reports:
        if not er['has_errors'] and er['nodes']:
            template = er
            break
    if not template:
        template = all_exec_reports[0]

    if template and template['nodes']:
        print(f"  (Based on execution {template['execution_id']})")
        for n in template['nodes']:
            arrow = '->' if not n.get('error') else '-X'
            print(f"  {arrow} {n['node_name']}: in={n['input_item_count']}, out={n['output_item_count']}, {n.get('executionTime', 0)}ms")

# Build final JSON report
report = {
    'workflow_id': WORKFLOW_ID,
    'timestamp': datetime.now().isoformat(),
    'executions_found': len(executions),
    'successful_executions': success_count,
    'errored_executions': error_count,
    'executions': all_exec_reports,
    'cross_execution_summary': {
        'node_duration_stats': node_stats,
        'node_error_counts': all_node_errors,
        'error_patterns': [
            {
                'message': msg,
                'count': info['count'],
                'nodes': list(info['nodes']),
                'execution_ids': info['executions']
            }
            for msg, info in error_msgs.items()
        ],
        'bottleneck_nodes': [
            {'node': name, **stats}
            for name, stats in sorted_nodes[:10]
        ]
    }
}

with open(OUTPUT_PATH, 'w') as f:
    json.dump(report, f, indent=2, default=str)

print(f"\n{'=' * 80}")
print(f"Full report saved to: {OUTPUT_PATH}")
print(f"Report size: {os.path.getsize(OUTPUT_PATH)} bytes")
print(f"{'=' * 80}")
