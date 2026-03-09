#!/usr/bin/env python3
"""Update n8n workflow files to use self-hosted embedding endpoint.

Replaces Jina API URLs with TEI/Gradio HF Space URLs in workflow JSON files,
then syncs to n8n via API.

Usage:
    source .env.local
    python3 scripts/update-embedding-endpoint.py --endpoint https://lbjlincoln-nomos-embeddings-api.hf.space
    python3 scripts/update-embedding-endpoint.py --dry-run  # preview changes
"""

import json, os, sys, argparse, glob, re

JINA_EMBED_URL = 'https://api.jina.ai/v1/embeddings'
JINA_RERANK_URL = 'https://api.jina.ai/v1/rerank'

def update_workflow(filepath, embed_url, dry_run=False):
    """Update embedding URLs and remove Jina auth headers in a workflow JSON file."""
    with open(filepath) as f:
        data = json.load(f)

    changes = []

    for node in data.get('nodes', []):
        params = node.get('parameters', {})
        url = params.get('url', '')

        # Only replace embedding URLs (NOT rerank)
        if url == JINA_EMBED_URL:
            new_url = f'{embed_url}/v1/embeddings'
            if not dry_run:
                params['url'] = new_url
            changes.append(f'{node["name"]}: URL → {new_url}')

            # Remove Jina auth header (self-hosted needs no auth)
            hp = params.get('headerParameters', {})
            hp_params = hp.get('parameters', [])
            stripped = [p for p in hp_params if 'JINA' not in str(p.get('value', ''))]
            if len(stripped) < len(hp_params):
                if not dry_run:
                    if stripped:
                        hp['parameters'] = stripped
                    else:
                        params['sendHeaders'] = False
                        params.pop('headerParameters', None)
                changes.append(f'{node["name"]}: removed Jina auth header')

    if not changes:
        return 0

    if dry_run:
        print(f'  {filepath}: {len(changes)} changes')
        for c in changes:
            print(f'    - {c}')
        return len(changes)

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f'  {filepath}: {len(changes)} changes applied')
    for c in changes:
        print(f'    - {c}')
    return len(changes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', default='https://lbjlincoln-nomos-embeddings-api.hf.space')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--dir', default='n8n/live')
    args = parser.parse_args()

    workflow_dir = os.path.join('/home/termius/mon-ipad', args.dir)
    files = glob.glob(os.path.join(workflow_dir, '*.json'))

    print(f'Scanning {len(files)} workflows in {workflow_dir}')
    print(f'New endpoint: {args.endpoint}')
    if args.dry_run:
        print('(DRY RUN — no files modified)')
    print()

    total = 0
    for f in sorted(files):
        n = update_workflow(f, args.endpoint, args.dry_run)
        total += n

    print(f'\nTotal: {total} changes {"(preview)" if args.dry_run else "applied"}')
    if not args.dry_run and total > 0:
        print('\nNext: run `python3 n8n/sync.py` to push changes to n8n')


if __name__ == '__main__':
    main()
