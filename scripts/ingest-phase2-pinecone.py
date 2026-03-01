#!/usr/bin/env python3
"""
Ingest Phase 2 dataset paragraphs into Pinecone with proper metadata.

The Standard RAG pipeline expects vectors in Pinecone with a `content` metadata field.
The existing benchmark namespace vectors lack this field, causing empty retrieval.

This script:
1. Reads hf-1000.json Phase 2 dataset
2. Extracts unique paragraphs from question contexts
3. Embeds them via Jina API (batch of 20)
4. Upserts to Pinecone default namespace with `content` metadata
"""

import json
import os
import sys
import time
import hashlib
import urllib.request
import urllib.error

# Config
JINA_API_KEY = os.environ.get('JINA_API_KEY', '')
PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY', '')
PINECONE_HOST = 'https://sota-rag-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io'
DATASET_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'datasets', 'phase-2', 'hf-1000.json')
NAMESPACE = ''  # Default namespace (where Standard pipeline queries)
JINA_BATCH_SIZE = 20
PINECONE_BATCH_SIZE = 50
JINA_MODEL = 'jina-embeddings-v3'
DIMENSIONS = 1024

# State tracking for resume
STATE_FILE = '/tmp/ingest-phase2-state.json'


def jina_embed(texts, api_key):
    """Embed texts via Jina API."""
    payload = json.dumps({
        'model': JINA_MODEL,
        'input': texts,
        'dimensions': DIMENSIONS
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.jina.ai/v1/embeddings',
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'curl/7.88.1'
        }
    )

    resp = urllib.request.urlopen(req, timeout=60)
    data = json.loads(resp.read().decode('utf-8'))
    return [item['embedding'] for item in data['data']]


def pinecone_upsert(vectors, api_key, namespace=''):
    """Upsert vectors to Pinecone."""
    payload = json.dumps({
        'vectors': vectors,
        'namespace': namespace
    }).encode('utf-8')

    req = urllib.request.Request(
        f'{PINECONE_HOST}/vectors/upsert',
        data=payload,
        headers={
            'Api-Key': api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'curl/7.88.1'
        }
    )

    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode('utf-8'))


def load_state():
    """Load resume state."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {'completed_batches': 0, 'total_vectors': 0}


def save_state(state):
    """Save resume state."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


def main():
    if not JINA_API_KEY or not PINECONE_API_KEY:
        print("ERROR: Set JINA_API_KEY and PINECONE_API_KEY env vars")
        sys.exit(1)

    # Load dataset
    print(f"Loading dataset from {DATASET_PATH}...")
    with open(DATASET_PATH) as f:
        data = json.load(f)

    questions = data['questions']
    print(f"Total questions: {len(questions)}")

    # Extract unique paragraphs with metadata
    paragraphs = []
    seen_ids = set()

    for q in questions:
        ctx_raw = q.get('context', '')
        if not ctx_raw or ctx_raw == '[]':
            continue

        try:
            ctx = json.loads(ctx_raw) if isinstance(ctx_raw, str) else ctx_raw
        except:
            continue

        q_id = q.get('id', '')
        dataset = q.get('metadata', {}).get('hf_subset', q_id.split('-')[0] if '-' in q_id else 'unknown')

        for item in ctx:
            if not isinstance(item, dict):
                continue

            text = item.get('paragraph_text', '')
            title = item.get('title', '')

            if len(text) < 20:
                continue

            # Create unique ID based on content hash
            content_hash = hashlib.md5(f"{title}:{text}".encode()).hexdigest()[:12]
            vec_id = f"p2-{content_hash}"

            if vec_id in seen_ids:
                continue
            seen_ids.add(vec_id)

            paragraphs.append({
                'id': vec_id,
                'text': text,
                'metadata': {
                    'content': text,  # CRITICAL: Standard pipeline reads this field
                    'source': dataset,
                    'dataset_name': dataset,
                    'title': title,
                    'is_supporting': item.get('is_supporting', False),
                    'tenant_id': 'benchmark',
                    'phase': 'phase2',
                    'question_id': q_id
                }
            })

    print(f"Unique paragraphs to ingest: {len(paragraphs)}")

    # Load resume state
    state = load_state()
    start_batch = state['completed_batches']

    # Process in batches
    total_batches = (len(paragraphs) + JINA_BATCH_SIZE - 1) // JINA_BATCH_SIZE
    print(f"Total batches: {total_batches} (starting from {start_batch})")

    vectors_upserted = state['total_vectors']
    errors = 0
    max_errors = 5

    for batch_idx in range(start_batch, total_batches):
        batch_start = batch_idx * JINA_BATCH_SIZE
        batch_end = min(batch_start + JINA_BATCH_SIZE, len(paragraphs))
        batch = paragraphs[batch_start:batch_end]

        texts = [p['text'] for p in batch]

        try:
            # Embed
            embeddings = jina_embed(texts, JINA_API_KEY)

            # Prepare Pinecone vectors
            vectors = []
            for i, para in enumerate(batch):
                vectors.append({
                    'id': para['id'],
                    'values': embeddings[i],
                    'metadata': para['metadata']
                })

            # Upsert to Pinecone
            result = pinecone_upsert(vectors, PINECONE_API_KEY, NAMESPACE)
            vectors_upserted += len(vectors)

            # Save state
            state['completed_batches'] = batch_idx + 1
            state['total_vectors'] = vectors_upserted
            save_state(state)

            progress = (batch_idx + 1) / total_batches * 100
            print(f"  Batch {batch_idx + 1}/{total_batches} ({progress:.0f}%): "
                  f"{len(vectors)} vectors upserted (total: {vectors_upserted})")

            # Rate limit: ~2 requests/sec for Jina free tier
            time.sleep(0.5)

        except urllib.error.HTTPError as e:
            errors += 1
            body = e.read().decode('utf-8', errors='replace')[:200]
            print(f"  ERROR batch {batch_idx + 1}: HTTP {e.code} - {body}")

            if e.code == 429:
                print("  Rate limited, waiting 30s...")
                time.sleep(30)
            elif e.code == 403:
                print("  Forbidden (Cloudflare?), waiting 60s...")
                time.sleep(60)

            if errors >= max_errors:
                print(f"  Max errors ({max_errors}) reached. Stopping.")
                break

        except Exception as e:
            errors += 1
            print(f"  ERROR batch {batch_idx + 1}: {e}")
            if errors >= max_errors:
                print(f"  Max errors ({max_errors}) reached. Stopping.")
                break
            time.sleep(2)

    print(f"\n=== DONE ===")
    print(f"Vectors upserted: {vectors_upserted}")
    print(f"Errors: {errors}")
    print(f"Resume state saved to {STATE_FILE}")


if __name__ == '__main__':
    main()
