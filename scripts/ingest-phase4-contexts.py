#!/usr/bin/env python3
"""Ingest Phase 4 benchmark contexts into Pinecone sota-rag-jina-1024.

Reads Phase 4 datasets, deduplicates contexts, embeds via Jina API,
and upserts to Pinecone default namespace so RAG pipelines can find them.

Usage:
    source .env.local
    python3 scripts/ingest-phase4-contexts.py [--max N] [--pipeline standard|graph|quantitative|all]
"""

import json, hashlib, os, sys, time, argparse
import urllib.request
import urllib.error

# Config
JINA_API_KEY = os.environ.get('JINA_API_KEY', '')
PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY', '')
PINECONE_HOST = 'sota-rag-jina-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io'
NAMESPACE = ''  # default namespace — where RAG pipelines search

JINA_BATCH_SIZE = 16  # texts per Jina API call (conservative for free tier)
PINECONE_BATCH_SIZE = 100  # vectors per Pinecone upsert
JINA_DELAY = 2.0  # seconds between Jina calls (rate limiting)

DATASETS = {
    'standard': 'datasets/phase-4/standard-39805.json',
    'graph': 'datasets/phase-4/graph-13856.json',
    'quantitative': 'datasets/phase-4/quantitative-8000.json',
}


def jina_embed(texts):
    """Embed texts using Jina API with Cloudflare bypass."""
    url = 'https://api.jina.ai/v1/embeddings'
    data = json.dumps({
        'model': 'jina-embeddings-v3',
        'input': texts,
        'dimensions': 1024,
        'task': 'retrieval.passage'
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {JINA_API_KEY}',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Accept': 'application/json'
    })
    for attempt in range(5):
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            result = json.loads(resp.read())
            return [d['embedding'] for d in result['data']], result.get('usage', {})
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 429:
                wait = min(60, 10 * (2 ** attempt))
                print(f'  Rate limited (429), waiting {wait}s... (attempt {attempt+1}/5)')
                time.sleep(wait)
                # Rebuild request (urlopen consumes it)
                req = urllib.request.Request(url, data=data, headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {JINA_API_KEY}',
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                })
                continue
            raise Exception(f'Jina API {e.code}: {body[:200]}')
        except Exception as e:
            if attempt < 4:
                time.sleep(5)
                # Rebuild request
                req = urllib.request.Request(url, data=data, headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {JINA_API_KEY}',
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                })
                continue
            raise
    raise Exception('Jina API: 5 attempts failed')


def pinecone_upsert(vectors, namespace=''):
    """Upsert vectors to Pinecone."""
    url = f'https://{PINECONE_HOST}/vectors/upsert'
    data = json.dumps({
        'vectors': vectors,
        'namespace': namespace
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        'Api-Key': PINECONE_API_KEY
    })
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def load_contexts(pipeline, max_contexts=None):
    """Load and deduplicate contexts from a Phase 4 dataset."""
    filepath = DATASETS[pipeline]
    print(f'Loading {filepath}...')
    with open(filepath) as f:
        data = json.load(f)

    questions = data.get('questions', [])
    contexts = {}
    context_to_questions = {}

    for q in questions:
        ctx = q.get('context', '').strip()
        if not ctx or len(ctx) < 20:
            continue
        h = hashlib.md5(ctx.encode()).hexdigest()
        if h not in contexts:
            contexts[h] = {
                'text': ctx,
                'dataset': q.get('dataset_name', 'unknown'),
                'pipeline': pipeline,
                'category': q.get('category', ''),
            }
            context_to_questions[h] = []
        context_to_questions[h].append(q.get('id', ''))

    # Add question count to metadata
    for h in contexts:
        contexts[h]['question_count'] = len(context_to_questions[h])

    items = list(contexts.items())
    if max_contexts:
        items = items[:max_contexts]

    print(f'  {len(questions)} questions -> {len(contexts)} unique contexts'
          f'{f" (limited to {max_contexts})" if max_contexts else ""}')
    return items


def ingest(pipeline, max_contexts=None):
    """Full ingestion pipeline for one dataset."""
    items = load_contexts(pipeline, max_contexts)
    if not items:
        print('  No contexts to ingest.')
        return 0

    total = len(items)
    ingested = 0
    total_tokens = 0
    pending_vectors = []
    start_time = time.time()

    for batch_start in range(0, total, JINA_BATCH_SIZE):
        batch = items[batch_start:batch_start + JINA_BATCH_SIZE]
        texts = [ctx['text'][:8000] for _, ctx in batch]  # truncate very long contexts

        try:
            embeddings, usage = jina_embed(texts)
            total_tokens += usage.get('total_tokens', 0)
        except Exception as e:
            print(f'  ERROR at batch {batch_start}: {e}')
            if 'quota' in str(e).lower() or '402' in str(e):
                print(f'  Jina quota exhausted after {ingested} contexts.')
                break
            continue

        # Build vectors
        for i, (ctx_hash, ctx_meta) in enumerate(batch):
            vec_id = f'p4-{ctx_meta["pipeline"]}-{ctx_hash[:12]}'
            pending_vectors.append({
                'id': vec_id,
                'values': embeddings[i],
                'metadata': {
                    'text': ctx_meta['text'][:3000],  # Pinecone metadata limit ~40KB
                    'source': f'phase4-{ctx_meta["dataset"]}',
                    'dataset': ctx_meta['dataset'],
                    'pipeline': ctx_meta['pipeline'],
                    'category': ctx_meta['category'],
                    'tenant_id': 'benchmark',
                    'phase': 4,
                    'question_count': ctx_meta['question_count'],
                }
            })

        # Upsert when batch is full
        if len(pending_vectors) >= PINECONE_BATCH_SIZE:
            batch_to_upsert = pending_vectors[:PINECONE_BATCH_SIZE]
            try:
                result = pinecone_upsert(batch_to_upsert, NAMESPACE)
                ingested += len(batch_to_upsert)
                pending_vectors = pending_vectors[PINECONE_BATCH_SIZE:]
                elapsed = time.time() - start_time
                rate = ingested / elapsed * 60
                print(f'  [{ingested}/{total}] upserted, {total_tokens:,} tokens, '
                      f'{rate:.0f}/min, ETA {(total-ingested)/max(rate,1)*60:.0f}s')
            except Exception as e:
                print(f'  Pinecone upsert ERROR: {e}')

        time.sleep(JINA_DELAY)

    # Final upsert for remaining vectors
    if pending_vectors:
        try:
            result = pinecone_upsert(pending_vectors, NAMESPACE)
            ingested += len(pending_vectors)
            print(f'  [{ingested}/{total}] final upsert done')
        except Exception as e:
            print(f'  Final upsert ERROR: {e}')

    elapsed = time.time() - start_time
    print(f'\n  DONE: {ingested}/{total} contexts ingested in {elapsed:.0f}s '
          f'({total_tokens:,} Jina tokens used)')
    return ingested


def main():
    parser = argparse.ArgumentParser(description='Ingest Phase 4 contexts into Pinecone')
    parser.add_argument('--pipeline', default='all', choices=['standard', 'graph', 'quantitative', 'all'])
    parser.add_argument('--max', type=int, default=None, help='Max contexts per pipeline')
    args = parser.parse_args()

    if not JINA_API_KEY:
        print('ERROR: JINA_API_KEY not set. Run: source .env.local')
        sys.exit(1)
    if not PINECONE_API_KEY:
        print('ERROR: PINECONE_API_KEY not set. Run: source .env.local')
        sys.exit(1)

    # Verify Jina API
    print('Testing Jina API...')
    try:
        _, usage = jina_embed(['connectivity test'])
        print(f'  Jina OK (tokens used: {usage})')
    except Exception as e:
        print(f'  Jina FAILED: {e}')
        sys.exit(1)

    pipelines = ['standard', 'graph', 'quantitative'] if args.pipeline == 'all' else [args.pipeline]
    total_ingested = 0

    for pipeline in pipelines:
        print(f'\n=== Ingesting {pipeline.upper()} contexts ===')
        count = ingest(pipeline, args.max)
        total_ingested += count

    print(f'\n=== TOTAL: {total_ingested} contexts ingested across {len(pipelines)} pipelines ===')


if __name__ == '__main__':
    main()
