#!/usr/bin/env python3
"""
Universal n8n Execution Analyzer — Session-Cookie Based
Parses flattened execution data, shows node-by-node status/errors.
Saves results to JSON for dashboard integration.

Usage:
    python3 scripts/n8n-execution-analyzer.py                          # All pipelines, latest exec
    python3 scripts/n8n-execution-analyzer.py --pipeline standard      # Specific pipeline
    python3 scripts/n8n-execution-analyzer.py --execution-id 54        # Specific execution
    python3 scripts/n8n-execution-analyzer.py --test                   # Run smoke test + analyze
    python3 scripts/n8n-execution-analyzer.py --save                   # Save results to JSON

Last updated: 2026-02-28
"""

import urllib.request
import json
import os
import sys
import time
import argparse
from datetime import datetime

# ─── Config ───────────────────────────────────────────────────────
N8N_HOST = os.environ.get('N8N_HOST', 'https://lbjlincoln-nomos-rag-engine.hf.space')
CI_EMAIL = os.environ.get('CI_EMAIL', 'ci@nomos.ai')
CI_PASSWORD = os.environ.get('CI_PASSWORD', 'CI-Nomos-2026!')

PIPELINES = {
    'standard': {
        'workflow_id': 'TmgyRP20N4JFd9CB',
        'webhook': '/webhook/rag-multi-index-v3',
        'test_question': 'What are the main challenges of implementing RAG systems?',
    },
    'graph': {
        'workflow_id': '6257AfT1l4FMC6lY',
        'webhook': '/webhook/ff622742-6d71-4e91-af71-b5c666088717',
        'test_question': 'How do knowledge graphs improve information retrieval?',
    },
    'quantitative': {
        'workflow_id': 'E19NZG9WfM7FNsxr',
        'webhook': '/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9',
        'test_question': 'What is the average revenue growth for technology companies?',
    },
    'orchestrator': {
        'workflow_id': 'ALd4gOEqiKL5KR1p',
        'webhook': '/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0',
        'test_question': 'Compare vector search and graph-based retrieval for RAG.',
    },
}

# ─── HTTP Helper ──────────────────────────────────────────────────
def http_request(url, method='GET', data=None, headers=None, timeout=30):
    """Universal HTTP request with error handling."""
    if headers is None:
        headers = {}
    headers.setdefault('User-Agent', 'Mozilla/5.0')

    if data and isinstance(data, dict):
        data = json.dumps(data).encode()
        headers.setdefault('Content-Type', 'application/json')

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        body = resp.read().decode('utf-8', errors='replace')
        return {
            'status': resp.status,
            'body': body,
            'json': json.loads(body) if body else None,
            'headers': dict(resp.headers),
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return {'status': e.code, 'body': body, 'json': None, 'error': str(e)}
    except Exception as e:
        return {'status': 0, 'body': '', 'json': None, 'error': str(e)}


# ─── n8n Session ──────────────────────────────────────────────────
def n8n_login():
    """Login to n8n and return session cookie."""
    resp = http_request(
        f'{N8N_HOST}/rest/login',
        method='POST',
        data={'emailOrLdapLoginId': CI_EMAIL, 'password': CI_PASSWORD},
    )
    if resp['status'] != 200:
        print(f"  LOGIN FAILED: HTTP {resp['status']}")
        return None

    cookie_header = resp['headers'].get('Set-Cookie', resp['headers'].get('set-cookie', ''))
    cookie = cookie_header.split(';')[0] if cookie_header else ''
    return cookie


def n8n_api(path, cookie, method='GET', data=None):
    """Call n8n REST API with session cookie."""
    return http_request(
        f'{N8N_HOST}{path}',
        method=method,
        data=data,
        headers={'Cookie': cookie},
    )


# ─── Execution Parser (handles flattened format) ──────────────────
def deref(exec_data, ref):
    """Dereference a value in flattened execution data."""
    if isinstance(ref, str) and ref.isdigit():
        idx = int(ref)
        if idx < len(exec_data):
            return exec_data[idx]
    return ref


def parse_execution(exec_data_raw):
    """Parse execution data (handles both standard and flattened formats)."""
    if not exec_data_raw:
        return {}
    if isinstance(exec_data_raw, str):
        try:
            exec_data_raw = json.loads(exec_data_raw)
        except (json.JSONDecodeError, ValueError):
            return {'error': {'message': 'Failed to parse execution data'}}

    if isinstance(exec_data_raw, dict):
        # Standard format
        return exec_data_raw

    if isinstance(exec_data_raw, list):
        # Flattened format — reconstruct
        root = exec_data_raw[0]
        result = {}

        # Get resultData
        result_idx = root.get('resultData', '')
        result_data = deref(exec_data_raw, result_idx)

        if isinstance(result_data, dict):
            # Get error
            error_ref = result_data.get('error', '')
            error = deref(exec_data_raw, error_ref)
            if isinstance(error, dict):
                # Dereference error fields
                msg_ref = error.get('message', '')
                desc_ref = error.get('description', '')
                name_ref = error.get('name', '')
                node_ref = error.get('node', '')

                result['error'] = {
                    'message': deref(exec_data_raw, msg_ref) if isinstance(msg_ref, str) and msg_ref.isdigit() else msg_ref,
                    'description': deref(exec_data_raw, desc_ref) if isinstance(desc_ref, str) and desc_ref.isdigit() else desc_ref,
                    'name': deref(exec_data_raw, name_ref) if isinstance(name_ref, str) and name_ref.isdigit() else name_ref,
                    'node': deref(exec_data_raw, node_ref),
                }

            # Get lastNodeExecuted
            last_ref = result_data.get('lastNodeExecuted', '')
            result['lastNodeExecuted'] = deref(exec_data_raw, last_ref)

            # Get runData
            run_data_ref = result_data.get('runData', '')
            run_data = deref(exec_data_raw, run_data_ref)
            if isinstance(run_data, dict):
                result['runData'] = {}
                for node_name, ref in run_data.items():
                    node_runs = deref(exec_data_raw, ref)
                    if isinstance(node_runs, list):
                        parsed_runs = []
                        for run_ref in node_runs:
                            run = deref(exec_data_raw, run_ref)
                            if isinstance(run, dict):
                                parsed_run = {}
                                # Get error
                                err_ref = run.get('error')
                                if err_ref:
                                    err = deref(exec_data_raw, err_ref)
                                    if isinstance(err, dict):
                                        err_msg = err.get('message', '')
                                        parsed_run['error'] = deref(exec_data_raw, err_msg) if isinstance(err_msg, str) and err_msg.isdigit() else err_msg
                                    else:
                                        parsed_run['error'] = str(err)

                                # Get execution status
                                status_ref = run.get('executionStatus', '')
                                parsed_run['status'] = deref(exec_data_raw, status_ref) if isinstance(status_ref, str) and status_ref.isdigit() else status_ref

                                # Get timing
                                parsed_run['startTime'] = run.get('startTime', 0)

                                parsed_runs.append(parsed_run)
                        result['runData'][node_name] = parsed_runs

        return result

    return {}


# ─── Analysis Functions ───────────────────────────────────────────
def analyze_execution(cookie, execution_id):
    """Analyze a single execution by ID."""
    resp = n8n_api(f'/rest/executions/{execution_id}', cookie)
    if resp['status'] != 200:
        return {'error': f"HTTP {resp['status']}", 'execution_id': execution_id}

    detail = resp['json']
    d = detail.get('data', detail)

    result = {
        'execution_id': execution_id,
        'status': d.get('status', 'unknown'),
        'started_at': d.get('startedAt', ''),
        'stopped_at': d.get('stoppedAt', ''),
        'workflow_id': d.get('workflowId', ''),
    }

    # Parse execution data
    exec_data_raw = d.get('data', '')
    parsed = parse_execution(exec_data_raw)

    result['last_node'] = parsed.get('lastNodeExecuted', 'N/A')
    result['error'] = parsed.get('error', None)

    # Node analysis
    run_data = parsed.get('runData', {})
    nodes = []
    for node_name, runs in run_data.items():
        for run in runs:
            node_info = {
                'name': node_name,
                'status': run.get('status', 'unknown'),
                'error': run.get('error', None),
            }
            nodes.append(node_info)

    result['nodes'] = nodes
    result['nodes_executed'] = len(nodes)
    result['nodes_failed'] = sum(1 for n in nodes if n.get('error'))

    return result


def analyze_pipeline(cookie, pipeline_name):
    """Analyze the latest execution for a pipeline."""
    config = PIPELINES.get(pipeline_name)
    if not config:
        return {'error': f"Unknown pipeline: {pipeline_name}"}

    wf_id = config['workflow_id']
    resp = n8n_api(f'/rest/executions?workflowId={wf_id}&limit=3', cookie)

    if resp['status'] != 200:
        return {'error': f"HTTP {resp['status']}", 'pipeline': pipeline_name}

    exec_list = resp['json']
    if isinstance(exec_list, dict):
        exec_list = exec_list.get('data', exec_list.get('results', []))
    if not isinstance(exec_list, list):
        exec_list = [exec_list] if exec_list else []

    if not exec_list:
        return {'pipeline': pipeline_name, 'message': 'No executions found', 'executions': []}

    results = []
    for ex in list(exec_list)[:2]:
        ex_id = ex.get('id', '')
        analysis = analyze_execution(cookie, ex_id)
        analysis['pipeline'] = pipeline_name
        results.append(analysis)

    return {'pipeline': pipeline_name, 'executions': results}


def smoke_test(cookie, pipeline_name):
    """Send a test question and analyze the result."""
    config = PIPELINES.get(pipeline_name)
    if not config:
        return {'error': f"Unknown pipeline: {pipeline_name}"}

    question = config['test_question']
    webhook = config['webhook']

    t0 = time.time()
    resp = http_request(
        f'{N8N_HOST}{webhook}',
        method='POST',
        data={'question': question, 'query': question},
        timeout=120,
    )
    elapsed = time.time() - t0

    result = {
        'pipeline': pipeline_name,
        'question': question,
        'http_status': resp['status'],
        'response_time': round(elapsed, 1),
        'response_length': len(resp.get('body', '')),
    }

    # Parse response
    if resp.get('json'):
        data = resp['json']
        if isinstance(data, dict):
            answer = data.get('answer', data.get('response', data.get('result', data.get('interpretation', ''))))
            if isinstance(answer, dict):
                answer = answer.get('answer', answer.get('response', str(answer)))
            result['answer'] = str(answer)[:500] if answer else ''
            result['has_answer'] = bool(answer and len(str(answer)) > 10)
        else:
            result['answer'] = str(data)[:500]
            result['has_answer'] = len(str(data)) > 10
    else:
        result['answer'] = resp.get('body', '')[:500]
        result['has_answer'] = len(resp.get('body', '')) > 20

    result['status'] = 'PASS' if result['has_answer'] else 'FAIL'

    return result


# ─── Main ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='n8n Execution Analyzer')
    parser.add_argument('--pipeline', '-p', help='Pipeline name (standard/graph/quantitative/orchestrator)')
    parser.add_argument('--execution-id', '-e', help='Specific execution ID')
    parser.add_argument('--test', '-t', action='store_true', help='Run smoke test + analyze')
    parser.add_argument('--save', '-s', action='store_true', help='Save results to JSON')
    parser.add_argument('--all', '-a', action='store_true', help='Analyze all pipelines')
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  n8n Execution Analyzer")
    print(f"  Host: {N8N_HOST}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # Login
    print("\n[1] Logging in...")
    cookie = n8n_login()
    if not cookie:
        print("  FATAL: Cannot login to n8n")
        sys.exit(1)
    print("  Login OK")

    all_results = {
        'timestamp': datetime.now().isoformat(),
        'host': N8N_HOST,
        'pipelines': {},
    }

    # Determine what to analyze
    pipelines_to_check = []
    if args.pipeline:
        pipelines_to_check = [args.pipeline]
    elif args.all or args.test:
        pipelines_to_check = list(PIPELINES.keys())
    elif args.execution_id:
        pipelines_to_check = []
    else:
        pipelines_to_check = list(PIPELINES.keys())

    # Specific execution
    if args.execution_id:
        print(f"\n[2] Analyzing execution {args.execution_id}...")
        result = analyze_execution(cookie, args.execution_id)
        print_execution_result(result)
        all_results['execution'] = result

    # Smoke test
    if args.test:
        print(f"\n[2] Running smoke tests...")
        for pipe in pipelines_to_check:
            print(f"\n  --- {pipe.upper()} ---")
            test_result = smoke_test(cookie, pipe)
            print(f"  HTTP: {test_result['http_status']} | {test_result['response_time']}s")
            print(f"  Answer: {test_result.get('answer', 'N/A')[:100]}...")
            print(f"  Status: {test_result['status']}")
            all_results['pipelines'][pipe] = {'smoke_test': test_result}

    # Execution analysis
    if pipelines_to_check and not args.execution_id:
        print(f"\n[3] Analyzing executions...")
        for pipe in pipelines_to_check:
            print(f"\n  --- {pipe.upper()} ---")
            analysis = analyze_pipeline(cookie, pipe)

            if 'executions' in analysis:
                for ex in analysis['executions']:
                    print_execution_result(ex, indent=4)
            elif 'error' in analysis:
                print(f"    Error: {analysis['error']}")
            elif 'message' in analysis:
                print(f"    {analysis['message']}")

            if pipe in all_results['pipelines']:
                all_results['pipelines'][pipe]['analysis'] = analysis
            else:
                all_results['pipelines'][pipe] = {'analysis': analysis}

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")

    for pipe, data in all_results.get('pipelines', {}).items():
        test = data.get('smoke_test', {})
        status = test.get('status', 'N/A')
        analysis = data.get('analysis', {})
        execs = analysis.get('executions', [])

        last_status = execs[0].get('status', '?') if execs else '?'
        last_node = execs[0].get('last_node', '?') if execs else '?'
        errors = execs[0].get('nodes_failed', 0) if execs else 0

        icon = '  PASS' if status == 'PASS' else '  FAIL' if status == 'FAIL' else '  ----'
        print(f"  {icon} {pipe:15s} | test={status:4s} | exec={last_status:6s} | errors={errors} | last_node={last_node}")

    # Save
    if args.save:
        save_path = os.path.join(os.path.dirname(__file__), '..', 'logs', 'execution-analysis.json')
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\n  Saved to: {save_path}")

    print()


def print_execution_result(result, indent=2):
    """Pretty-print execution analysis result."""
    prefix = ' ' * indent

    ex_id = result.get('execution_id', '?')
    status = result.get('status', '?')
    last_node = result.get('last_node', '?')
    nodes_exec = result.get('nodes_executed', 0)
    nodes_fail = result.get('nodes_failed', 0)

    print(f"{prefix}Execution {ex_id}: {status} | {nodes_exec} nodes | {nodes_fail} errors | last: {last_node}")

    # Show errors
    error = result.get('error')
    if error and isinstance(error, dict):
        msg = error.get('message', '')
        desc = error.get('description', '')
        if msg:
            print(f"{prefix}  ERROR: {msg}")
        if desc:
            print(f"{prefix}  DESC: {desc[:150]}")

    # Show node errors
    for node in result.get('nodes', []):
        if node.get('error'):
            print(f"{prefix}  NODE ERROR @ {node['name']}: {node['error'][:150]}")


if __name__ == '__main__':
    main()
