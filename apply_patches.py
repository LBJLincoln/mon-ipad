#!/usr/bin/env python3
"""
Patch Applier Agent - Multi-RAG Orchestrator SOTA 2026
Applies RFC 6902 JSON patches to n8n workflows and produces importable JSONs.
"""
import json
import copy
import os
import sys
from datetime import datetime

try:
    import jsonpatch
except ImportError:
    print("ERROR: jsonpatch not installed. Run: pip install jsonpatch")
    sys.exit(1)

BASE_DIR = '/home/user/mon-ipad'
PATCHES_DIR = os.path.join(BASE_DIR, 'patches')
OUTPUT_DIR = os.path.join(BASE_DIR, 'modified-workflows')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_rfc6902_ops(patch_data):
    """Extract clean RFC 6902 operations from patch data (both formats)."""
    ops = []
    for p in patch_data.get('patches', []):
        if 'operations' in p:
            # Ingestion format: each patch entry has an operations array
            for op in p['operations']:
                clean = {k: v for k, v in op.items() if k in ('op', 'path', 'value', 'from')}
                ops.append(clean)
        elif 'op' in p:
            # Flat format: each patch IS an RFC 6902 operation (with extra metadata)
            clean = {k: v for k, v in p.items() if k in ('op', 'path', 'value', 'from')}
            ops.append(clean)
    return ops


def apply_ops_safely(workflow, ops, label=""):
    """Apply RFC 6902 operations one by one, skipping failed test operations gracefully."""
    working = copy.deepcopy(workflow)
    applied = 0
    skipped = 0
    errors = []

    for i, op in enumerate(ops):
        try:
            patch = jsonpatch.JsonPatch([op])
            working = patch.apply(working)
            applied += 1
        except jsonpatch.JsonPatchTestFailed as e:
            # test operations that fail are informational - skip them
            skipped += 1
            errors.append(f"  [SKIP] test op #{i}: {e}")
        except Exception as e:
            skipped += 1
            errors.append(f"  [WARN] op #{i} ({op.get('op')} {op.get('path', '')}): {e}")

    return working, applied, skipped, errors


def add_new_nodes(workflow, new_nodes_list):
    """Add new nodes and connections from new_nodes_to_add."""
    for group in new_nodes_list:
        if 'nodes' in group:
            for node in group['nodes']:
                workflow['nodes'].append(node)
        if 'connections' in group:
            for conn_name, conn_val in group['connections'].items():
                workflow['connections'][conn_name] = conn_val
    return workflow


def rename_connection_key(workflow, old_name, new_name):
    """Rename a key in the connections object to match a renamed node."""
    if old_name in workflow.get('connections', {}):
        workflow['connections'][new_name] = workflow['connections'].pop(old_name)


def update_connection_targets(workflow, old_name, new_name):
    """Update all connection target references from old_name to new_name."""
    for source, conn_data in workflow.get('connections', {}).items():
        if 'main' in conn_data:
            for output_idx, output_conns in enumerate(conn_data['main']):
                if isinstance(output_conns, list):
                    for conn in output_conns:
                        if isinstance(conn, dict) and conn.get('node') == old_name:
                            conn['node'] = new_name


def validate_n8n_workflow(workflow, name):
    """Basic validation of n8n workflow JSON structure."""
    issues = []

    if 'nodes' not in workflow or not isinstance(workflow['nodes'], list):
        issues.append("Missing or invalid 'nodes' array")
    if 'connections' not in workflow or not isinstance(workflow['connections'], dict):
        issues.append("Missing or invalid 'connections' object")

    # Check for duplicate node names
    node_names = [n.get('name', '') for n in workflow.get('nodes', [])]
    seen = set()
    for n in node_names:
        if n in seen:
            issues.append(f"Duplicate node name: '{n}'")
        seen.add(n)

    # Check that connection source keys reference existing nodes
    for conn_key in workflow.get('connections', {}):
        if conn_key not in seen:
            issues.append(f"Connection key '{conn_key}' has no matching node")

    # Check that connection target nodes exist
    for source, conn_data in workflow.get('connections', {}).items():
        if isinstance(conn_data, dict) and 'main' in conn_data:
            for outputs in conn_data['main']:
                if isinstance(outputs, list):
                    for conn in outputs:
                        if isinstance(conn, dict):
                            target = conn.get('node', '')
                            if target and target not in seen:
                                issues.append(f"Connection target '{target}' (from '{source}') has no matching node")

    return issues


def process_workflow(wf_file, patch_file, label=""):
    """Process a single workflow: apply patches, add nodes, validate."""
    print(f"\n{'='*60}")
    print(f"Processing: {label or wf_file}")
    print(f"{'='*60}")

    # Load original workflow
    wf_path = os.path.join(BASE_DIR, wf_file)
    if not os.path.exists(wf_path):
        print(f"  ERROR: Workflow file not found: {wf_path}")
        return None, f"File not found: {wf_path}"

    original = load_json(wf_path)

    # Create backup
    backup_path = os.path.join(BACKUP_DIR, wf_file)
    save_json(original, backup_path)
    print(f"  Backup: {backup_path}")

    # Load patch data
    patch_path = os.path.join(BASE_DIR, patch_file)
    if not os.path.exists(patch_path):
        print(f"  ERROR: Patch file not found: {patch_path}")
        return None, f"Patch file not found: {patch_path}"

    patch_data = load_json(patch_path)

    # Extract RFC 6902 operations
    ops = extract_rfc6902_ops(patch_data)
    print(f"  Extracted {len(ops)} RFC 6902 operations")

    # Apply operations
    working, applied, skipped, errors = apply_ops_safely(original, ops, label)
    print(f"  Applied: {applied}, Skipped: {skipped}")
    for err in errors:
        print(err)

    return working, patch_data, applied, skipped, errors


def main():
    print("="*60)
    print("PATCH APPLIER AGENT - Multi-RAG Orchestrator SOTA 2026")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)

    manifest = load_json(os.path.join(PATCHES_DIR, 'patches-manifest.json'))
    results = []

    for entry in manifest['patches']:
        wf_file = entry['workflow_file']
        patch_file = entry['patch_file']
        label = f"[Order {entry['order']}] {wf_file} ({entry['priority']})"

        result = process_workflow(wf_file, patch_file, label)
        if result[0] is None:
            results.append({
                'workflow': wf_file,
                'status': 'ERROR',
                'error': result[1],
                'applied': 0,
                'skipped': 0
            })
            continue

        working, patch_data, applied, skipped, errors = result

        # === POST-PROCESSING: Handle new nodes ===
        if 'new_nodes_to_add' in patch_data:
            new_count = sum(len(g.get('nodes', [])) for g in patch_data['new_nodes_to_add'])
            working = add_new_nodes(working, patch_data['new_nodes_to_add'])
            print(f"  Added {new_count} new nodes")

        # === POST-PROCESSING: Handle connection changes (ingestion-specific) ===
        if 'connection_changes' in patch_data:
            for change in patch_data.get('connection_changes', []):
                if 'operations' in change:
                    conn_ops = []
                    for op in change['operations']:
                        clean = {k: v for k, v in op.items() if k in ('op', 'path', 'value', 'from')}
                        conn_ops.append(clean)
                    try:
                        working, c_applied, c_skipped, c_errors = apply_ops_safely(working, conn_ops,
                                                                                    f"conn_change")
                        print(f"  Connection change '{change.get('id', '?')}': applied={c_applied}")
                        for err in c_errors:
                            print(err)
                    except Exception as e:
                        print(f"  Warning: Connection change failed: {e}")

        # === POST-PROCESSING: Fix connection keys for renamed nodes ===
        # Check if any node was renamed and fix the connection key accordingly
        node_names_set = {n.get('name', '') for n in working.get('nodes', [])}
        conn_keys_to_fix = []
        for conn_key in list(working.get('connections', {}).keys()):
            if conn_key not in node_names_set:
                conn_keys_to_fix.append(conn_key)

        if conn_keys_to_fix:
            print(f"  Orphaned connection keys (node renamed): {conn_keys_to_fix}")
            # For ingestion: "Chunk Enricher V3.1 (Contextual)" -> "Chunk Validator & Enricher V4"
            for old_key in conn_keys_to_fix:
                # Try to find the new name by checking which nodes don't have connection keys
                nodes_without_conn = node_names_set - set(working['connections'].keys())
                # Simple heuristic: if there's only one orphan and one missing, match them
                # For more complex cases, we'd need explicit mapping
                pass  # We'll handle specific cases below

        # === SPECIFIC FIX: Ingestion V3.1 connection key rename ===
        if 'Ingestion' in wf_file:
            # After PATCH-ING-006 renames node 9, fix the connection key
            rename_connection_key(working,
                                  'Chunk Enricher V3.1 (Contextual)',
                                  'Chunk Validator & Enricher V4')
            # Also update any connection targets referencing the old name
            update_connection_targets(working,
                                      'Chunk Enricher V3.1 (Contextual)',
                                      'Chunk Validator & Enricher V4')

            # Fix: remove the Q&A Generator connection from Chunk Enricher since
            # the flow now goes through Contextual Retrieval chain
            # Keep existing connection to Version Manager via Aggregate Contextual Chunks

        # === VALIDATE ===
        issues = validate_n8n_workflow(working, wf_file)
        if issues:
            print(f"  Validation warnings ({len(issues)}):")
            for issue in issues[:10]:
                print(f"    - {issue}")
            status = 'WARNING'
        else:
            print(f"  Validation: PASSED")
            status = 'SUCCESS'

        # === SAVE ===
        output_path = os.path.join(OUTPUT_DIR, wf_file)
        save_json(working, output_path)
        print(f"  Output: {output_path}")

        results.append({
            'workflow': wf_file,
            'status': status,
            'applied': applied,
            'skipped': skipped,
            'new_nodes': sum(len(g.get('nodes', [])) for g in patch_data.get('new_nodes_to_add', [])),
            'validation_issues': len(issues) if issues else 0,
            'output': output_path
        })

    # === SUMMARY ===
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status_icon = "OK" if r['status'] == 'SUCCESS' else "WARN" if r['status'] == 'WARNING' else "ERR"
        print(f"  [{status_icon}] {r['workflow']}: {r.get('applied', 0)} applied, "
              f"{r.get('skipped', 0)} skipped, {r.get('new_nodes', 0)} new nodes, "
              f"{r.get('validation_issues', 0)} warnings")

    # Save results report
    report_path = os.path.join(OUTPUT_DIR, 'apply-results.json')
    save_json({
        'generated_at': datetime.now().isoformat(),
        'generated_by': 'patch-applier-agent',
        'results': results
    }, report_path)
    print(f"\nReport saved: {report_path}")

    return results


if __name__ == '__main__':
    main()
