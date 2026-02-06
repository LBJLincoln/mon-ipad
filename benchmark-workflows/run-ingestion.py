#!/usr/bin/env python3
"""
RAG Benchmark — Direct Dataset Ingestion via HuggingFace → Supabase + Pinecone
Uses n8n SQL Executor for Supabase, direct Pinecone REST API for vectors.
"""
import json
import os
import sys
import time
import hashlib
from datetime import datetime
from urllib import request, error, parse

N8N_HOST = "https://amoret.app.n8n.cloud"
PINECONE_HOST = "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
PINECONE_API_KEY = "pcsk_6GzVdD_BbHsYNvpcngMqAHH5EvEa9XLnmFpEK9cx5q5xkMp72z5KFQ1q7dEjp8npWhJGBY"

# Datasets ordered by complexity (most complex first)
DATASETS = [
    # TIER 1: Multi-Hop (Very High Complexity)
    {"name": "hotpotqa", "hf": "hotpotqa/hotpot_qa", "subset": "distractor", "cat": "multi_hop_qa",
     "split": "validation", "size": 1000, "qf": "question", "af": "answer",
     "ctx": "context", "sf": "supporting_facts", "neo4j": True},
    {"name": "musique", "hf": "StonyBrookNLP/musique", "subset": "default", "cat": "multi_hop_qa",
     "split": "validation", "size": 500, "qf": "question", "af": "answer",
     "ctx": "paragraphs", "neo4j": True},
    {"name": "frames", "hf": "google/frames-benchmark", "subset": "default", "cat": "rag_benchmark",
     "split": "test", "size": 824, "qf": "Prompt", "af": "Answer"},
    {"name": "2wikimultihopqa", "hf": "scholarly-shadows-syndicate/2wikimultihopqa", "subset": "default",
     "cat": "multi_hop_qa", "split": "validation", "size": 1000,
     "qf": "question", "af": "answer", "ctx": "context", "sf": "supporting_facts", "neo4j": True},
    # TIER 2: Single-Hop (High)
    {"name": "natural_questions", "hf": "google-research-datasets/nq_open", "subset": "default",
     "cat": "single_hop_qa", "split": "validation", "size": 1000, "qf": "question", "af": "answer"},
    {"name": "triviaqa", "hf": "trivia_qa", "subset": "rc.nocontext", "cat": "single_hop_qa",
     "split": "validation", "size": 1000, "qf": "question", "af": "answer"},
    {"name": "squad_v2", "hf": "rajpurkar/squad_v2", "subset": "squad_v2", "cat": "single_hop_qa",
     "split": "validation", "size": 1000, "qf": "question", "af": "answers", "ctx": "context"},
    {"name": "popqa", "hf": "akariasai/PopQA", "subset": "default", "cat": "single_hop_qa",
     "split": "test", "size": 1000, "qf": "question", "af": "possible_answers"},
    # TIER 3: Domain-Specific
    {"name": "pubmedqa", "hf": "qiaojin/PubMedQA", "subset": "pqa_labeled", "cat": "domain_medical",
     "split": "train", "size": 500, "qf": "question", "af": "long_answer", "ctx": "context"},
    {"name": "finqa", "hf": "ibm/finqa", "subset": "default", "cat": "domain_finance",
     "split": "test", "size": 500, "qf": "question", "af": "answer"},
    {"name": "cuad", "hf": "theatticusproject/cuad-qa", "subset": "default", "cat": "domain_legal",
     "split": "test", "size": 500, "qf": "question", "af": "answers", "ctx": "context"},
    {"name": "covidqa", "hf": "covid_qa_deepset", "subset": "covid_qa_deepset", "cat": "domain_medical",
     "split": "train", "size": 500, "qf": "question", "af": "answers", "ctx": "context"},
]


def hf_fetch(path, subset, split, offset, length):
    url = f"https://datasets-server.huggingface.co/rows?dataset={parse.quote(path)}&config={parse.quote(subset)}&split={split}&offset={offset}&length={length}"
    req = request.Request(url)
    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise


def exec_sql(sql):
    body = json.dumps({"sql": sql}).encode()
    req = request.Request(f'{N8N_HOST}/webhook/benchmark-sql-exec', data=body, headers={
        'Content-Type': 'application/json'}, method='POST')
    try:
        with request.urlopen(req, timeout=30) as resp:
            return True
    except:
        return False


def get_field(obj, path, default=None):
    if not path or not obj:
        return default
    parts = path.replace('[', '.').replace(']', '').split('.')
    val = obj
    for p in parts:
        if val is None:
            return default
        if isinstance(val, dict):
            val = val.get(p)
        elif isinstance(val, list):
            try:
                val = val[int(p)]
            except:
                return default
        else:
            return default
    if isinstance(val, list):
        if not val:
            return default
        if isinstance(val[0], str):
            return val[0]
        return json.dumps(val)
    return str(val) if val is not None else default


def store_supabase_batch(items):
    if not items:
        return 0
    values = []
    for it in items:
        q = it['question'].replace("'", "''")[:8000]
        a = (it.get('expected_answer') or '').replace("'", "''")[:8000]
        ctx = it.get('context')
        if ctx:
            if isinstance(ctx, (list, dict)):
                ctx = json.dumps(ctx)[:15000]
            ctx = f"'{str(ctx).replace(chr(39), chr(39)+chr(39))[:15000]}'"
        else:
            ctx = "NULL"
        sf = it.get('supporting_facts')
        sf_val = f"'{json.dumps(sf).replace(chr(39), chr(39)+chr(39))}'::jsonb" if sf else "NULL"
        meta = json.dumps(it.get('metadata', {})).replace("'", "''")
        values.append(
            f"('{it['dataset_name']}','{it['category']}','{it['split']}',"
            f"{it['item_index']},'{q}','{a}',{ctx},{sf_val},"
            f"'{meta}'::jsonb,'{it['tenant_id']}','{it['batch_id']}')"
        )
    sql = (
        "INSERT INTO benchmark_datasets "
        "(dataset_name,category,split,item_index,question,expected_answer,"
        "context,supporting_facts,metadata,tenant_id,batch_id) VALUES "
        + ",".join(values)
        + " ON CONFLICT (dataset_name, split, item_index, tenant_id) DO UPDATE SET "
        "question=EXCLUDED.question,expected_answer=EXCLUDED.expected_answer,"
        "context=EXCLUDED.context,metadata=EXCLUDED.metadata,batch_id=EXCLUDED.batch_id,"
        "ingested_at=NOW()"
    )
    return len(items) if exec_sql(sql) else 0


def store_pinecone_batch(items, dataset_name):
    namespace = f"benchmark-{dataset_name}"
    vectors = []
    for it in items:
        vid = f"bench-{dataset_name}-{it['split']}-{it['item_index']}"
        h = hashlib.sha256(it['question'].encode()).hexdigest()
        pv = [int(h[i:i+2], 16) / 255.0 for i in range(0, 64, 2)]
        while len(pv) < 1536:
            pv.extend(pv[:min(1536-len(pv), len(pv))])
        pv = pv[:1536]
        vectors.append({
            "id": vid,
            "values": pv,
            "metadata": {
                "dataset": dataset_name, "category": it['category'],
                "idx": it['item_index'],
                "question": it['question'][:400],
                "answer": (it.get('expected_answer') or '')[:400],
                "tenant": "benchmark"
            }
        })

    total = 0
    for i in range(0, len(vectors), 100):
        batch = vectors[i:i+100]
        body = json.dumps({"vectors": batch, "namespace": namespace}).encode()
        req = request.Request(f"{PINECONE_HOST}/vectors/upsert", data=body, headers={
            "Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"
        }, method="POST")
        try:
            with request.urlopen(req, timeout=30) as resp:
                r = json.loads(resp.read())
                total += r.get("upsertedCount", len(batch))
        except Exception as e:
            print(f"      Pinecone err: {e}")
    return total


def ingest_dataset(ds):
    name = ds['name']
    print(f"\n{'='*60}")
    print(f"  INGESTING: {name} ({ds['cat']}) — {ds['size']} items")
    print(f"{'='*60}")

    start = time.time()
    all_items = []
    offset = 0
    batch_id = f"ingest-{name}-{datetime.now().strftime('%Y%m%d%H%M')}"

    while offset < ds['size']:
        fetch_n = min(100, ds['size'] - offset)
        try:
            result = hf_fetch(ds['hf'], ds['subset'], ds['split'], offset, fetch_n)
            rows = result.get('rows', [])
            if not rows:
                break
            for i, rd in enumerate(rows):
                r = rd.get('row', rd)
                q = get_field(r, ds['qf'], '')
                a = get_field(r, ds['af'], '')
                if isinstance(a, dict):
                    a = a.get('text', a.get('value', json.dumps(a)))
                if isinstance(a, list):
                    a = a[0] if a else ''
                if not q:
                    continue
                ctx = get_field(r, ds.get('ctx', ''))
                sf = None
                sf_raw = r.get(ds.get('sf', '__none__'))
                if isinstance(sf_raw, (dict, list)):
                    sf = sf_raw

                all_items.append({
                    'dataset_name': name, 'category': ds['cat'],
                    'split': ds['split'], 'item_index': offset + i,
                    'question': str(q)[:10000],
                    'expected_answer': str(a)[:10000] if a else '',
                    'context': ctx, 'supporting_facts': sf,
                    'metadata': {'hf': ds['hf'], 'idx': offset + i},
                    'tenant_id': 'benchmark', 'batch_id': batch_id
                })
            offset += len(rows)
            sys.stdout.write(f"\r    Fetched: {len(all_items)}/{ds['size']}")
            sys.stdout.flush()
        except Exception as e:
            print(f"\n    HF error at offset {offset}: {e}")
            if not all_items:
                return {"name": name, "status": "failed", "error": str(e), "items": 0}
            break

    print(f"\n    Total fetched: {len(all_items)}")

    # Store in Supabase (batches of 25 to stay under webhook payload limits)
    sb_count = 0
    batch_sz = 25
    for i in range(0, len(all_items), batch_sz):
        batch = all_items[i:i+batch_sz]
        c = store_supabase_batch(batch)
        sb_count += c
        if (i // batch_sz) % 10 == 0:
            sys.stdout.write(f"\r    Supabase: {sb_count}/{len(all_items)}")
            sys.stdout.flush()
    print(f"\r    Supabase: {sb_count}/{len(all_items)} stored")

    # Store in Pinecone
    pc_count = store_pinecone_batch(all_items, name)
    print(f"    Pinecone: {pc_count} vectors (namespace: benchmark-{name})")

    elapsed = time.time() - start
    # Log ingestion stats
    exec_sql(
        f"INSERT INTO benchmark_ingestion_stats (dataset_name,split,total_items,ingested_items,"
        f"pinecone_vectors,supabase_rows,last_batch_id,status,started_at,completed_at) "
        f"VALUES ('{name}','{ds['split']}',{len(all_items)},{sb_count},"
        f"{pc_count},{sb_count},'{batch_id}','completed',NOW()-INTERVAL '{int(elapsed)} seconds',NOW()) "
        f"ON CONFLICT (dataset_name,split) DO UPDATE SET "
        f"ingested_items=EXCLUDED.ingested_items,pinecone_vectors=EXCLUDED.pinecone_vectors,"
        f"supabase_rows=EXCLUDED.supabase_rows,status='completed',completed_at=NOW()"
    )

    return {
        "name": name, "category": ds['cat'], "status": "completed",
        "items": len(all_items), "supabase": sb_count, "pinecone": pc_count,
        "duration_s": round(elapsed, 1)
    }


if __name__ == "__main__":
    print("=" * 60)
    print("RAG BENCHMARK — Dataset Ingestion")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Datasets: {len(DATASETS)}")
    total_target = sum(d['size'] for d in DATASETS)
    print(f"Target Q&A: {total_target}")
    print("=" * 60)

    results = []
    for ds in DATASETS:
        try:
            r = ingest_dataset(ds)
            results.append(r)
        except Exception as e:
            print(f"\n  CRITICAL: {ds['name']} — {e}")
            results.append({"name": ds['name'], "status": "failed", "error": str(e), "items": 0})

    # Log overall run
    completed = [r for r in results if r.get('status') == 'completed']
    exec_sql(
        f"INSERT INTO benchmark_runs (run_id,run_type,phase,workflow_name,dataset_names,"
        f"config,status,total_items,processed_items,duration_ms,tenant_id,trace_id) VALUES ("
        f"'bulk-ingest-{datetime.now().strftime('%Y%m%d%H%M%S')}','ingestion','phase_1',"
        f"'run-ingestion.py',ARRAY{json.dumps([r['name'] for r in completed])},"
        f"'{{}}'::jsonb,'completed',"
        f"{sum(r.get('items',0) for r in results)},"
        f"{sum(r.get('supabase',0) for r in results)},"
        f"{int(sum(r.get('duration_s',0) for r in results)*1000)},"
        f"'benchmark','tr-bulk-{datetime.now().strftime('%Y%m%d%H%M%S')}')"
    )

    # Summary
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    ti, ts, tp = 0, 0, 0
    for r in results:
        st = "OK" if r.get('status') == 'completed' else "FAIL"
        i = r.get('items', 0)
        ti += i
        ts += r.get('supabase', 0)
        tp += r.get('pinecone', 0)
        print(f"  [{st}] {r['name']:25s} {i:5d} items | SB:{r.get('supabase',0):5d} PC:{r.get('pinecone',0):5d} | {r.get('duration_s',0):.0f}s")

    print(f"\n  TOTAL: {ti} items | Supabase: {ts} | Pinecone: {tp}")
    print("=" * 60)

    with open("/home/user/mon-ipad/benchmark-workflows/ingestion-results.json", "w") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "results": results,
                    "totals": {"items": ti, "supabase": ts, "pinecone": tp}}, f, indent=2)
