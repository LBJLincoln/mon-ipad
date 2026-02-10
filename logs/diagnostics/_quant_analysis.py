import json, os, sys, traceback
from urllib import request
from datetime import datetime

N8N_HOST = 'https://amoret.app.n8n.cloud'
N8N_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMTU3NjdlMC05NThhLTRjNzQtYTY3YS1lMzM1ODA3ZWJhNjQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY5MDQ2NTExLCJleHAiOjE3NzE2Mjg0MDB9.fyOBVwb32HlzwQhSxCxoKsmMlYcxppTFGbj6S01AX2A'
WF_ID = 'E19NZG9WfM7FNsxr'

def n8n_get(path, timeout=120):
    url = f'{N8N_HOST}/api/v1{path}'
    headers = {'Accept': 'application/json', 'X-N8N-API-KEY': N8N_API_KEY}
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

def trunc(s, maxlen=500):
    s = str(s)
    if len(s) > maxlen:
        return s[:maxlen] + f'... [TRUNCATED, total {len(s)} chars]'
    return s

def safe_json(obj):
    """Make object JSON serializable"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

def extract_node_info(node_name, node_runs):
    """Extract detailed info from a node's execution data"""
    results = []
    for run_idx, run in enumerate(node_runs):
        info = {
            'node_name': node_name,
            'run_index': run_idx,
            'startTime': run.get('startTime'),
            'executionTime': run.get('executionTime'),
            'executionStatus': run.get('executionStatus'),
            'error': None,
            'input_summary': None,
            'output_summary': None,
            'sql_query': None,
            'question': None,
            'answer': None,
        }

        # Extract error
        if run.get('error'):
            info['error'] = trunc(json.dumps(run['error'], default=safe_json), 800)

        # Extract input data
        input_data = run.get('inputData', {})
        if input_data:
            main_input = input_data.get('main', [])
            if main_input:
                flat_inputs = []
                for connection in main_input:
                    if connection:
                        for item in connection:
                            flat_inputs.append(item.get('json', {}))
                info['input_summary'] = trunc(json.dumps(flat_inputs, default=safe_json))

        # Extract output data
        output_data = run.get('data', {})
        if output_data:
            main_output = output_data.get('main', [])
            if main_output:
                flat_outputs = []
                for connection in main_output:
                    if connection:
                        for item in connection:
                            flat_outputs.append(item.get('json', {}))
                info['output_summary'] = trunc(json.dumps(flat_outputs, default=safe_json))

                # Try to extract specific fields
                for item in flat_outputs:
                    if isinstance(item, dict):
                        # Look for SQL queries
                        for key in ['query', 'sql', 'sqlQuery', 'sql_query', 'generatedSql']:
                            if key in item:
                                info['sql_query'] = trunc(str(item[key]), 600)
                        # Look for questions
                        for key in ['question', 'query', 'chatInput', 'input', 'message']:
                            if key in item and not info['question']:
                                info['question'] = trunc(str(item[key]), 300)
                        # Look for answers
                        for key in ['answer', 'response', 'output', 'text', 'result']:
                            if key in item and not info['answer']:
                                info['answer'] = trunc(str(item[key]), 500)

        results.append(info)
    return results

def analyze_execution(exec_data):
    """Analyze a single execution in detail"""
    exec_id = exec_data.get('id', 'unknown')
    status = exec_data.get('status', 'unknown')
    finished = exec_data.get('finished', False)
    started_at = exec_data.get('startedAt', '')
    stopped_at = exec_data.get('stoppedAt', '')
    mode = exec_data.get('mode', '')

    analysis = {
        'execution_id': exec_id,
        'status': status,
        'finished': finished,
        'started_at': started_at,
        'stopped_at': stopped_at,
        'mode': mode,
        'question_asked': None,
        'final_answer': None,
        'nodes': [],
        'node_execution_order': [],
        'total_duration_ms': 0,
        'error_summary': None,
        'cancellation_analysis': None,
        'sql_queries_generated': [],
    }

    # Get run data
    data = exec_data.get('data', {})
    if not data:
        analysis['error_summary'] = 'No execution data available'
        return analysis

    result_data = data.get('resultData', {})
    run_data = result_data.get('runData', {})
    last_node_executed = result_data.get('lastNodeExecuted', '')

    # Check for top-level error
    if result_data.get('error'):
        analysis['error_summary'] = trunc(json.dumps(result_data['error'], default=safe_json), 800)

    # Sort nodes by start time to get execution order
    node_start_times = []
    for node_name, node_runs in run_data.items():
        if node_runs:
            start = node_runs[0].get('startTime', 0)
            node_start_times.append((start, node_name))
    node_start_times.sort()
    analysis['node_execution_order'] = [n for _, n in node_start_times]

    # Extract all node data
    for _, node_name in node_start_times:
        node_runs = run_data[node_name]
        node_infos = extract_node_info(node_name, node_runs)
        for ni in node_infos:
            analysis['nodes'].append(ni)
            analysis['total_duration_ms'] += (ni.get('executionTime') or 0)

            # Capture question from trigger/webhook nodes
            if any(kw in node_name.lower() for kw in ['webhook', 'trigger', 'chat']):
                if ni.get('question'):
                    analysis['question_asked'] = ni['question']
                elif ni.get('output_summary'):
                    # Try to find question in output
                    try:
                        out = json.loads(ni['output_summary'].split('... [TRUNCATED')[0]) if '... [TRUNCATED' in ni['output_summary'] else json.loads(ni['output_summary'])
                        for item in out:
                            if isinstance(item, dict):
                                for k in ['chatInput', 'question', 'query', 'input', 'message', 'body']:
                                    if k in item:
                                        val = item[k]
                                        if isinstance(val, dict):
                                            for sk in ['chatInput', 'question', 'query', 'input', 'message']:
                                                if sk in val:
                                                    analysis['question_asked'] = trunc(str(val[sk]), 300)
                                                    break
                                        else:
                                            analysis['question_asked'] = trunc(str(val), 300)
                                        break
                    except:
                        pass

            # Capture SQL queries
            if ni.get('sql_query'):
                analysis['sql_queries_generated'].append({
                    'node': node_name,
                    'sql': ni['sql_query']
                })

    # Find the final answer (from last node or response builder)
    if analysis['nodes']:
        last_node = analysis['nodes'][-1]
        analysis['final_answer'] = last_node.get('answer') or last_node.get('output_summary')

    # For canceled executions, analyze what happened
    if status == 'canceled' or not finished:
        last_nodes = analysis['node_execution_order'][-3:] if len(analysis['node_execution_order']) >= 3 else analysis['node_execution_order']
        last_node_errors = []
        for n in analysis['nodes']:
            if n['node_name'] in last_nodes and n.get('error'):
                last_node_errors.append({'node': n['node_name'], 'error': n['error']})

        analysis['cancellation_analysis'] = {
            'last_node_executed': last_node_executed,
            'last_3_nodes': last_nodes,
            'errors_in_last_nodes': last_node_errors,
            'total_nodes_executed': len(analysis['node_execution_order']),
            'hypothesis': ''
        }

        if last_node_errors:
            analysis['cancellation_analysis']['hypothesis'] = f'Canceled due to error in {last_node_errors[-1]["node"]}'
        elif analysis['total_duration_ms'] > 30000:
            analysis['cancellation_analysis']['hypothesis'] = f'Likely timeout — total duration {analysis["total_duration_ms"]}ms'
        else:
            analysis['cancellation_analysis']['hypothesis'] = f'Canceled after {len(analysis["node_execution_order"])} nodes, last was "{last_node_executed}". Possible external cancellation or workflow logic halt.'

    return analysis


def main():
    print("=" * 80)
    print("QUANTITATIVE PIPELINE DEEP ANALYSIS")
    print(f"Workflow ID: {WF_ID}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 80)

    # Fetch executions
    print("\n[1/3] Fetching last 15 executions with full data...")
    try:
        resp = n8n_get(f'/executions?workflowId={WF_ID}&limit=15&includeData=true')
    except Exception as e:
        print(f"ERROR fetching executions: {e}")
        traceback.print_exc()
        sys.exit(1)

    executions = resp.get('data', [])
    print(f"  Fetched {len(executions)} executions")

    # Analyze each execution
    print("\n[2/3] Analyzing each execution...")
    analyses = []
    status_counts = {}
    canceled_analyses = []
    successful_analyses = []

    for i, ex in enumerate(executions):
        exec_id = ex.get('id', 'unknown')
        status = ex.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

        print(f"\n{'─' * 70}")
        print(f"EXECUTION {i+1}/{len(executions)} — ID: {exec_id} — Status: {status}")
        print(f"{'─' * 70}")

        analysis = analyze_execution(ex)
        analyses.append(analysis)

        if status == 'canceled':
            canceled_analyses.append(analysis)
        elif status == 'success':
            successful_analyses.append(analysis)

        # Print per-execution report
        print(f"  Question: {analysis['question_asked'] or '(not extracted)'}")
        print(f"  Nodes executed: {len(analysis['node_execution_order'])}")
        print(f"  Total duration: {analysis['total_duration_ms']}ms")
        print(f"  Node order: {' → '.join(analysis['node_execution_order'])}")

        if analysis['sql_queries_generated']:
            for sq in analysis['sql_queries_generated']:
                print(f"  SQL ({sq['node']}): {sq['sql'][:200]}")

        print(f"  Final answer: {trunc(str(analysis['final_answer']), 300)}")

        if analysis['error_summary']:
            print(f"  ERROR: {analysis['error_summary'][:300]}")

        if analysis.get('cancellation_analysis'):
            ca = analysis['cancellation_analysis']
            print(f"  CANCELLATION ANALYSIS:")
            print(f"    Last node: {ca['last_node_executed']}")
            print(f"    Nodes run: {ca['total_nodes_executed']}")
            print(f"    Hypothesis: {ca['hypothesis']}")

        # Per-node detail
        print(f"\n  NODE DETAILS:")
        for node in analysis['nodes']:
            dur = node.get('executionTime', 0) or 0
            status_str = node.get('executionStatus', '?')
            err = ' [ERROR]' if node.get('error') else ''
            print(f"    [{dur:>6}ms] [{status_str:>7}]{err} {node['node_name']}")
            if node.get('input_summary'):
                print(f"             IN:  {trunc(node['input_summary'], 200)}")
            if node.get('output_summary'):
                print(f"             OUT: {trunc(node['output_summary'], 200)}")
            if node.get('error'):
                print(f"             ERR: {trunc(node['error'], 300)}")
            if node.get('sql_query'):
                print(f"             SQL: {trunc(node['sql_query'], 300)}")

    # Cross-execution summary
    print("\n" + "=" * 80)
    print("CROSS-EXECUTION SUMMARY")
    print("=" * 80)

    print(f"\nStatus distribution: {json.dumps(status_counts)}")
    print(f"Total executions analyzed: {len(analyses)}")

    # Common node patterns
    all_node_names = set()
    node_durations = {}
    node_error_counts = {}
    node_success_counts = {}
    for a in analyses:
        for n in a['nodes']:
            name = n['node_name']
            all_node_names.add(name)
            dur = n.get('executionTime', 0) or 0
            node_durations.setdefault(name, []).append(dur)
            if n.get('error'):
                node_error_counts[name] = node_error_counts.get(name, 0) + 1
            else:
                node_success_counts[name] = node_success_counts.get(name, 0) + 1

    print(f"\nAll unique nodes encountered ({len(all_node_names)}):")
    for name in sorted(all_node_names):
        durs = node_durations.get(name, [])
        avg_dur = sum(durs) / len(durs) if durs else 0
        max_dur = max(durs) if durs else 0
        errs = node_error_counts.get(name, 0)
        successes = node_success_counts.get(name, 0)
        print(f"  {name:40s} | avg={avg_dur:>7.0f}ms | max={max_dur:>7.0f}ms | ok={successes} err={errs}")

    # Bottleneck analysis
    print("\nBOTTLENECK NODES (avg duration > 1000ms):")
    for name in sorted(all_node_names, key=lambda n: sum(node_durations.get(n, [0]))/max(len(node_durations.get(n, [1])),1), reverse=True):
        durs = node_durations.get(name, [])
        avg_dur = sum(durs) / len(durs) if durs else 0
        if avg_dur > 1000:
            print(f"  {name:40s} | avg={avg_dur:>7.0f}ms | samples={len(durs)}")

    # Error pattern analysis
    print("\nERROR NODES:")
    for name, count in sorted(node_error_counts.items(), key=lambda x: -x[1]):
        print(f"  {name:40s} | errors={count}")

    # Canceled execution deep dive
    print(f"\nCANCELED EXECUTIONS ({len(canceled_analyses)}):")
    for ca in canceled_analyses:
        canc = ca.get('cancellation_analysis', {})
        print(f"  ID={ca['execution_id']}: last_node='{canc.get('last_node_executed')}', "
              f"nodes_run={canc.get('total_nodes_executed')}, "
              f"hypothesis='{canc.get('hypothesis')}'")
        print(f"    Question: {ca.get('question_asked', '(unknown)')}")

    # Successful executions analysis — why 0% accuracy?
    print(f"\nSUCCESSFUL EXECUTIONS ANALYSIS ({len(successful_analyses)}):")
    print("Investigating why accuracy might be 0% despite successful executions:")
    for sa in successful_analyses:
        q = sa.get('question_asked', '(unknown)')
        a = trunc(str(sa.get('final_answer', '(none)')), 400)
        sqls = [sq['sql'] for sq in sa.get('sql_queries_generated', [])]
        print(f"\n  Q: {q}")
        print(f"  A: {a}")
        if sqls:
            for sql in sqls:
                print(f"  SQL: {trunc(sql, 300)}")
        else:
            print(f"  SQL: (none generated)")

        # Check for common failure patterns in "successful" executions
        issues = []
        if not sa.get('final_answer'):
            issues.append("NO FINAL ANSWER PRODUCED")
        final = str(sa.get('final_answer', ''))
        if 'error' in final.lower() or 'unable' in final.lower() or 'cannot' in final.lower():
            issues.append("ANSWER CONTAINS ERROR/INABILITY LANGUAGE")
        if 'no data' in final.lower() or 'no results' in final.lower() or 'empty' in final.lower():
            issues.append("ANSWER INDICATES EMPTY RESULTS")
        if not sqls:
            issues.append("NO SQL QUERY WAS GENERATED")

        # Check node chain for data loss
        for node in sa['nodes']:
            out = str(node.get('output_summary', ''))
            if node.get('error'):
                issues.append(f"NODE ERROR in '{node['node_name']}': {trunc(str(node['error']), 150)}")
            if out == '[]' or out == '[{}]' or out == 'None':
                issues.append(f"EMPTY OUTPUT from '{node['node_name']}'")

        if issues:
            print(f"  ISSUES FOUND:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print(f"  NO OBVIOUS ISSUES DETECTED")

    # Typical data flow
    print("\nTYPICAL DATA FLOW:")
    # Find the most common node order
    from collections import Counter
    orders = [' → '.join(a['node_execution_order']) for a in analyses if a['node_execution_order']]
    order_counts = Counter(orders)
    for order, count in order_counts.most_common(3):
        print(f"  [{count}x] {order}")

    # Final summary
    print("\n" + "=" * 80)
    print("ROOT CAUSE HYPOTHESES")
    print("=" * 80)

    # Gather all questions and answers for pattern matching
    all_answers = [str(a.get('final_answer', '')) for a in successful_analyses]
    all_sqls_flat = []
    for a in analyses:
        for sq in a.get('sql_queries_generated', []):
            all_sqls_flat.append(sq['sql'])

    hypotheses = []
    if not all_sqls_flat:
        hypotheses.append("1. NO SQL QUERIES GENERATED: The pipeline may not be generating SQL from questions")
    if all(not a.get('final_answer') for a in successful_analyses):
        hypotheses.append("2. NO ANSWERS PRODUCED: Successful executions produce no final answer")
    if len(canceled_analyses) >= 3:
        cancel_nodes = [ca.get('cancellation_analysis', {}).get('last_node_executed', '') for ca in canceled_analyses]
        hypotheses.append(f"3. HIGH CANCELLATION RATE: {len(canceled_analyses)}/15 canceled. Last nodes: {cancel_nodes}")
    if node_error_counts:
        top_err = max(node_error_counts.items(), key=lambda x: x[1])
        hypotheses.append(f"4. MOST ERROR-PRONE NODE: '{top_err[0]}' with {top_err[1]} errors")

    for h in hypotheses:
        print(f"  {h}")
    if not hypotheses:
        print("  Need deeper analysis of answer quality vs expected answers")

    # Save full report to JSON
    report = {
        'timestamp': datetime.now().isoformat(),
        'workflow_id': WF_ID,
        'total_executions': len(analyses),
        'status_counts': status_counts,
        'execution_analyses': analyses,
        'cross_execution': {
            'all_node_names': sorted(all_node_names),
            'node_avg_durations': {n: sum(d)/len(d) for n, d in node_durations.items()},
            'node_error_counts': node_error_counts,
            'node_success_counts': node_success_counts,
            'typical_flows': dict(order_counts.most_common(5)),
            'bottleneck_nodes': [n for n in all_node_names if sum(node_durations.get(n, [0]))/max(len(node_durations.get(n, [1])),1) > 1000],
        },
        'canceled_deep_dive': [a.get('cancellation_analysis') for a in canceled_analyses],
        'hypotheses': hypotheses,
    }

    outpath = '/home/user/mon-ipad/logs/diagnostics/quantitative-deep-analysis.json'
    with open(outpath, 'w') as f:
        json.dump(report, f, indent=2, default=safe_json)
    print(f"\nFull report saved to: {outpath}")
    print(f"Report size: {os.path.getsize(outpath)} bytes")

if __name__ == '__main__':
    main()
