#!/usr/bin/env python3
"""
Import Missing Datasets into Pinecone + Supabase
=================================================
Imports the 9 datasets missing from Pinecone (identified from live DB audit):

CRITICAL (needed by Standard RAG questions):
  1. squad_v2 (1000) — 26 Standard RAG questions reference this namespace

HIGH PRIORITY (standard RAG benchmarks):
  2. hotpotqa (1000)
  3. frames (824)

MEDIUM (multi-hop graph RAG):
  4. musique (500)
  5. 2wikimultihopqa (1000)

LOWER (financial/table QA):
  6. finqa (500)
  7. tatqa (150)
  8. convfinqa (100)
  9. wikitablequestions (50)

Pipeline per dataset:
  1. Download from HuggingFace Datasets API
  2. Store in Supabase benchmark_datasets table
  3. Generate real embeddings (OpenAI text-embedding-3-small)
  4. Push to Pinecone with proper namespace

Prerequisites (env vars):
  PINECONE_API_KEY, SUPABASE_PASSWORD, OPENAI_API_KEY (or OPENROUTER_API_KEY)
  Optional: HF_TOKEN (for gated datasets)

Usage:
  python3 import-missing-datasets.py              # Import all 9
  python3 import-missing-datasets.py squad_v2     # Import one specific
  python3 import-missing-datasets.py --check      # Just check what's missing
"""
import json
import os
import sys
import time
import hashlib
from datetime import datetime
from urllib import request, error, parse

# ============================================================
# Configuration
# ============================================================
PINECONE_HOST = os.environ.get(
    "PINECONE_HOST",
    "https://sota-rag-a4mkzmz.svc.aped-4627-b74a.pinecone.io"
).rstrip("/")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
SUPABASE_PASSWORD = os.environ.get("SUPABASE_PASSWORD", "")
SUPABASE_CONN = f"postgresql://postgres.ayqviqmxifzmhphiqfmj:{SUPABASE_PASSWORD}@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
EMBEDDING_BATCH_SIZE = 100
PINECONE_BATCH_SIZE = 100

# ============================================================
# 9 Missing Datasets — ordered by priority
# ============================================================
MISSING_DATASETS = [
    # CRITICAL
    {
        "name": "squad_v2",
        "hf_path": "rajpurkar/squad_v2",
        "hf_config": "squad_v2",
        "split": "validation",
        "sample_size": 1000,
        "q_field": "question",
        "a_field": "answers",
        "context_field": "context",
        "category": "single_hop_qa",
        "priority": "CRITICAL",
    },
    # HIGH
    {
        "name": "hotpotqa",
        "hf_path": "hotpotqa/hotpot_qa",
        "hf_config": "distractor",
        "split": "validation",
        "sample_size": 1000,
        "q_field": "question",
        "a_field": "answer",
        "context_field": "context",
        "category": "multi_hop_qa",
        "priority": "HIGH",
    },
    {
        "name": "frames",
        "hf_path": "google/frames-benchmark",
        "hf_config": "default",
        "split": "test",
        "sample_size": 824,
        "q_field": "Prompt",
        "a_field": "Answer",
        "category": "rag_benchmark",
        "priority": "HIGH",
    },
    # MEDIUM
    {
        "name": "musique",
        "hf_path": "StonyBrookNLP/musique",
        "hf_config": "default",
        "split": "validation",
        "sample_size": 500,
        "q_field": "question",
        "a_field": "answer",
        "context_field": "paragraphs",
        "category": "multi_hop_qa",
        "priority": "MEDIUM",
    },
    {
        "name": "2wikimultihopqa",
        "hf_path": "scholarly-shadows-syndicate/2wikimultihopqa",
        "hf_config": "default",
        "split": "validation",
        "sample_size": 1000,
        "q_field": "question",
        "a_field": "answer",
        "context_field": "context",
        "category": "multi_hop_qa",
        "priority": "MEDIUM",
    },
    # LOWER
    {
        "name": "finqa",
        "hf_path": "ibm/finqa",
        "hf_config": "default",
        "split": "test",
        "sample_size": 500,
        "q_field": "question",
        "a_field": "answer",
        "category": "domain_finance",
        "priority": "LOWER",
    },
    {
        "name": "tatqa",
        "hf_path": "next-nus/tat-qa",
        "hf_config": "default",
        "split": "validation",
        "sample_size": 150,
        "q_field": "question",
        "a_field": "answer",
        "category": "domain_finance",
        "priority": "LOWER",
    },
    {
        "name": "convfinqa",
        "hf_path": "ibm/convfinqa",
        "hf_config": "default",
        "split": "test",
        "sample_size": 100,
        "q_field": "question",
        "a_field": "answer",
        "category": "domain_finance",
        "priority": "LOWER",
    },
    {
        "name": "wikitablequestions",
        "hf_path": "wikitablequestions",
        "hf_config": "default",
        "split": "test",
        "sample_size": 50,
        "q_field": "question",
        "a_field": "answers",
        "category": "table_qa",
        "priority": "LOWER",
    },
]


# ============================================================
# HuggingFace Datasets API
# ============================================================
def hf_fetch_rows(dataset_path, config, split, offset=0, length=100):
    """Fetch rows from HuggingFace datasets-server API."""
    url = (
        f"https://datasets-server.huggingface.co/rows"
        f"?dataset={parse.quote(dataset_path)}"
        f"&config={parse.quote(config)}"
        f"&split={split}"
        f"&offset={offset}&length={length}"
    )
    headers = {}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    req = request.Request(url, headers=headers)
    for attempt in range(4):
        try:
            with request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:300]
            except:
                pass
            if e.code == 429:
                wait = min(30, 5 * (attempt + 1))
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"    HF API error {e.code}: {body[:200]}")
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return None
        except Exception as e:
            print(f"    HF fetch error (attempt {attempt+1}): {e}")
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return None
    return None


def extract_field(row, field_name, default=""):
    """Extract a field from a HF row, handling nested structures."""
    if not field_name or field_name not in row:
        return default
    val = row[field_name]
    if val is None:
        return default
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        if len(val) == 0:
            return default
        if isinstance(val[0], str):
            return val[0]
        return json.dumps(val)[:5000]
    if isinstance(val, dict):
        # SQuAD-style: {"text": ["answer1", ...], "answer_start": [...]}
        if "text" in val:
            texts = val["text"]
            if isinstance(texts, list) and texts:
                return texts[0]
            return str(texts)
        return json.dumps(val)[:5000]
    return str(val)


def download_dataset(ds_config):
    """Download a dataset from HuggingFace and return structured items."""
    name = ds_config["name"]
    hf_path = ds_config["hf_path"]
    config = ds_config["hf_config"]
    split = ds_config["split"]
    sample_size = ds_config["sample_size"]

    print(f"  Downloading from HuggingFace: {hf_path} ({config}/{split})...")

    items = []
    offset = 0
    batch_size = 100
    max_retries_empty = 3
    empty_count = 0

    while len(items) < sample_size:
        remaining = sample_size - len(items)
        fetch_size = min(batch_size, remaining)

        result = hf_fetch_rows(hf_path, config, split, offset, fetch_size)
        if result is None:
            print(f"    Failed to fetch at offset {offset}")
            # Try alternate config names
            if empty_count == 0 and config != "default":
                print(f"    Retrying with config='default'...")
                result = hf_fetch_rows(hf_path, "default", split, offset, fetch_size)
            if result is None:
                empty_count += 1
                if empty_count >= max_retries_empty:
                    print(f"    Giving up after {max_retries_empty} failures")
                    break
                offset += fetch_size
                continue

        rows = result.get("rows", [])
        if not rows:
            empty_count += 1
            if empty_count >= max_retries_empty:
                break
            offset += fetch_size
            continue

        empty_count = 0
        for row_data in rows:
            row = row_data.get("row", row_data)

            question = extract_field(row, ds_config["q_field"])
            answer = extract_field(row, ds_config["a_field"])
            context = extract_field(row, ds_config.get("context_field", ""), "")

            if not question or len(question.strip()) < 5:
                continue

            items.append({
                "dataset_name": name,
                "category": ds_config["category"],
                "split": split,
                "item_index": len(items),
                "question": question.strip()[:10000],
                "expected_answer": (answer or "").strip()[:10000],
                "context": context[:20000] if context else None,
                "tenant_id": "benchmark",
            })

            if len(items) >= sample_size:
                break

        offset += len(rows)
        if len(rows) < fetch_size:
            break  # No more data

        if len(items) % 200 == 0 and len(items) > 0:
            print(f"    Downloaded {len(items)}/{sample_size}...")

    print(f"  Downloaded: {len(items)} items")
    return items


# ============================================================
# Embedding API
# ============================================================
def get_embeddings(texts):
    """Get embeddings from OpenAI or OpenRouter API."""
    api_key = OPENAI_API_KEY or OPENROUTER_API_KEY
    if not api_key:
        print("  ERROR: No OPENAI_API_KEY or OPENROUTER_API_KEY set")
        return None

    if OPENAI_API_KEY:
        url = "https://api.openai.com/v1/embeddings"
        auth_key = OPENAI_API_KEY
    else:
        url = "https://openrouter.ai/api/v1/embeddings"
        auth_key = OPENROUTER_API_KEY

    body = json.dumps({
        "model": EMBEDDING_MODEL,
        "input": [t[:6000] for t in texts],
        "encoding_format": "float"
    }).encode()

    headers = {
        "Authorization": f"Bearer {auth_key}",
        "Content-Type": "application/json"
    }

    req = request.Request(url, data=body, headers=headers, method="POST")
    for attempt in range(4):
        try:
            with request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read())
                return [item["embedding"] for item in result["data"]]
        except error.HTTPError as e:
            body_err = ""
            try:
                body_err = e.read().decode()[:300]
            except:
                pass
            print(f"    Embedding API error {e.code} (attempt {attempt+1}): {body_err[:150]}")
            if e.code == 429:
                time.sleep(10 * (attempt + 1))
            elif e.code >= 500:
                time.sleep(3 * (attempt + 1))
            else:
                return None
        except Exception as e:
            print(f"    Embedding error (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return None


def embed_items(items):
    """Generate embeddings for all items in batches."""
    texts = []
    for item in items:
        text = item["question"]
        if item.get("expected_answer"):
            text += f"\nAnswer: {item['expected_answer']}"
        if item.get("context") and len(item["context"]) > 50:
            text += f"\nContext: {item['context'][:2000]}"
        texts.append(text)

    all_embeddings = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        embeddings = get_embeddings(batch)
        if embeddings is None:
            print(f"    FAILED batch {i // EMBEDDING_BATCH_SIZE + 1}")
            all_embeddings.extend([None] * len(batch))
        else:
            all_embeddings.extend(embeddings)

        if i > 0 and i % 500 == 0:
            print(f"    Embedded {i}/{len(texts)}...")
            time.sleep(0.3)

    return all_embeddings


# ============================================================
# Pinecone operations
# ============================================================
def pinecone_describe():
    """Get Pinecone index stats."""
    req = request.Request(
        f"{PINECONE_HOST}/describe_index_stats",
        headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"},
        data=b"{}",
        method="POST"
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  Pinecone describe error: {e}")
        return None


def pinecone_upsert(vectors, namespace):
    """Upsert vectors to Pinecone."""
    total = 0
    for i in range(0, len(vectors), PINECONE_BATCH_SIZE):
        batch = vectors[i:i + PINECONE_BATCH_SIZE]
        body = json.dumps({"vectors": batch, "namespace": namespace}).encode()
        req = request.Request(
            f"{PINECONE_HOST}/vectors/upsert",
            data=body,
            headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json"},
            method="POST"
        )
        for attempt in range(3):
            try:
                with request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                    total += result.get("upsertedCount", len(batch))
                    break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    print(f"    Pinecone upsert error: {e}")
    return total


# ============================================================
# Supabase storage
# ============================================================
def store_supabase(items):
    """Store items in Supabase benchmark_datasets table."""
    import subprocess

    if not items or not SUPABASE_PASSWORD:
        return 0

    total = 0
    batch_size = 50
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        values = []
        for item in batch:
            q = item['question'].replace("'", "''").replace("\\", "\\\\")[:10000]
            a = (item.get('expected_answer') or '').replace("'", "''").replace("\\", "\\\\")[:10000]
            ctx = item.get('context')
            if ctx:
                if isinstance(ctx, (list, dict)):
                    ctx = json.dumps(ctx)
                ctx = ctx.replace("'", "''").replace("\\", "\\\\")[:20000]
                ctx_val = f"'{ctx}'"
            else:
                ctx_val = "NULL"
            values.append(
                f"('{item['dataset_name']}', '{item['category']}', '{item['split']}', "
                f"{item['item_index']}, '{q}', '{a}', {ctx_val}, "
                f"'{item.get('tenant_id', 'benchmark')}')"
            )

        sql = f"""INSERT INTO benchmark_datasets
(dataset_name, category, split, item_index, question, expected_answer, context, tenant_id)
VALUES {','.join(values)}
ON CONFLICT (dataset_name, split, item_index, tenant_id) DO UPDATE SET
  question = EXCLUDED.question,
  expected_answer = EXCLUDED.expected_answer,
  context = EXCLUDED.context,
  ingested_at = NOW();"""

        result = subprocess.run(
            ["psql", SUPABASE_CONN, "-c", sql],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            total += len(batch)
        else:
            # Try one by one on failure
            for item in batch:
                q = item['question'].replace("'", "''").replace("\\", "\\\\")[:5000]
                a = (item.get('expected_answer') or '').replace("'", "''").replace("\\", "\\\\")[:5000]
                single_sql = f"""INSERT INTO benchmark_datasets
(dataset_name, category, split, item_index, question, expected_answer, tenant_id)
VALUES ('{item['dataset_name']}', '{item['category']}', '{item['split']}',
{item['item_index']}, '{q}', '{a}', '{item.get('tenant_id', 'benchmark')}')
ON CONFLICT (dataset_name, split, item_index, tenant_id) DO NOTHING;"""
                r2 = subprocess.run(
                    ["psql", SUPABASE_CONN, "-c", single_sql],
                    capture_output=True, text=True, timeout=10
                )
                if r2.returncode == 0:
                    total += 1
    return total


# ============================================================
# Main pipeline
# ============================================================
def check_missing():
    """Check which datasets are missing from Pinecone."""
    print("Checking Pinecone index state...")
    stats = pinecone_describe()
    if not stats:
        print("  Could not reach Pinecone")
        return

    namespaces = stats.get("namespaces", {})
    print(f"  Total vectors: {stats.get('totalVectorCount', 0)}")
    print(f"  Namespaces: {len(namespaces)}")

    present = set(namespaces.keys())
    missing = []
    for ds in MISSING_DATASETS:
        ns = f"benchmark-{ds['name']}"
        count = namespaces.get(ns, {}).get("vectorCount", 0)
        status = f"  PRESENT ({count} vectors)" if ns in present else "  MISSING"
        priority = ds["priority"]
        print(f"  [{priority:8s}] {ns:40s} {status}")
        if ns not in present:
            missing.append(ds)

    print(f"\n  Missing datasets: {len(missing)}")
    return missing


def import_dataset(ds_config):
    """Full pipeline for one dataset: HF → Supabase → Embeddings → Pinecone."""
    name = ds_config["name"]
    namespace = f"benchmark-{name}"
    sample_size = ds_config["sample_size"]

    print(f"\n{'=' * 60}")
    print(f"  IMPORTING: {name} ({ds_config['priority']})")
    print(f"  Target: {sample_size} items → namespace '{namespace}'")
    print(f"{'=' * 60}")

    start = time.time()

    # Step 1: Download from HuggingFace
    items = download_dataset(ds_config)
    if not items:
        print(f"  FAILED: No items downloaded for {name}")
        return {"name": name, "status": "error", "error": "download_failed", "count": 0}

    # Step 2: Store in Supabase
    if SUPABASE_PASSWORD:
        print(f"  Storing {len(items)} items in Supabase...")
        stored = store_supabase(items)
        print(f"  Supabase: {stored} rows stored")
    else:
        print(f"  Skipping Supabase (no SUPABASE_PASSWORD)")

    # Step 3: Generate embeddings
    api_key = OPENAI_API_KEY or OPENROUTER_API_KEY
    if not api_key:
        print(f"  ERROR: No embedding API key. Set OPENAI_API_KEY or OPENROUTER_API_KEY")
        return {"name": name, "status": "error", "error": "no_embedding_key", "count": len(items)}

    print(f"  Generating embeddings ({EMBEDDING_MODEL})...")
    embeddings = embed_items(items)

    # Step 4: Build Pinecone vectors
    vectors = []
    skipped = 0
    for i, (item, emb) in enumerate(zip(items, embeddings)):
        if emb is None:
            skipped += 1
            continue
        vec_id = f"bench-{name}-{item['split']}-{item['item_index']}"
        vectors.append({
            "id": vec_id,
            "values": emb,
            "metadata": {
                "dataset_name": name,
                "category": item["category"],
                "item_index": item["item_index"],
                "question": item["question"][:400],
                "expected_answer": (item.get("expected_answer") or "")[:400],
                "tenant_id": "benchmark"
            }
        })

    if skipped:
        print(f"  WARNING: {skipped}/{len(items)} embeddings failed")

    # Step 5: Push to Pinecone
    print(f"  Upserting {len(vectors)} vectors to Pinecone namespace '{namespace}'...")
    upserted = pinecone_upsert(vectors, namespace)
    elapsed = round(time.time() - start, 1)

    print(f"  DONE: {upserted} vectors upserted in {elapsed}s")
    return {
        "name": name,
        "status": "completed",
        "downloaded": len(items),
        "embedded": len(vectors),
        "upserted": upserted,
        "skipped": skipped,
        "duration_s": elapsed,
    }


def main():
    start = datetime.now()
    print("=" * 70)
    print("  IMPORT MISSING DATASETS INTO PINECONE")
    print(f"  Time: {start.isoformat()}")
    print(f"  Pinecone: {PINECONE_HOST}")
    print(f"  Embedding: {EMBEDDING_MODEL}")
    print(f"  Supabase: {'configured' if SUPABASE_PASSWORD else 'not configured'}")
    print(f"  OpenAI: {'yes' if OPENAI_API_KEY else 'no'}")
    print(f"  OpenRouter: {'yes' if OPENROUTER_API_KEY else 'no'}")
    print(f"  HF Token: {'yes' if HF_TOKEN else 'no'}")
    print("=" * 70)

    # Check args
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            check_missing()
            return
        # Filter to specific datasets
        target_names = set(sys.argv[1:])
        datasets_to_import = [ds for ds in MISSING_DATASETS if ds["name"] in target_names]
        if not datasets_to_import:
            print(f"  No matching datasets for: {target_names}")
            print(f"  Available: {[ds['name'] for ds in MISSING_DATASETS]}")
            return
    else:
        # Check what's actually missing
        missing = check_missing()
        if missing is None:
            print("  Cannot determine missing datasets (Pinecone unreachable)")
            datasets_to_import = MISSING_DATASETS
        elif not missing:
            print("  All datasets present! Nothing to import.")
            return
        else:
            datasets_to_import = missing

    print(f"\n  Will import {len(datasets_to_import)} datasets:")
    total_items = 0
    for ds in datasets_to_import:
        print(f"    [{ds['priority']:8s}] {ds['name']} ({ds['sample_size']} items)")
        total_items += ds["sample_size"]
    print(f"  Total target: ~{total_items} items")

    # Import each dataset
    results = []
    for idx, ds in enumerate(datasets_to_import):
        print(f"\n  [{idx + 1}/{len(datasets_to_import)}]", end="")
        result = import_dataset(ds)
        results.append(result)
        if idx < len(datasets_to_import) - 1:
            time.sleep(1)

    # Summary
    elapsed = int((datetime.now() - start).total_seconds())
    completed = [r for r in results if r.get("status") == "completed"]
    failed = [r for r in results if r.get("status") != "completed"]
    total_vectors = sum(r.get("upserted", 0) for r in completed)

    print("\n" + "=" * 70)
    print("  IMPORT SUMMARY")
    print("=" * 70)
    print(f"  Elapsed: {elapsed}s ({elapsed // 60}m {elapsed % 60}s)")
    print(f"  Completed: {len(completed)}/{len(results)}")
    print(f"  Total vectors upserted: {total_vectors}")

    if completed:
        print(f"\n  Successful:")
        for r in completed:
            print(f"    {r['name']}: {r['upserted']} vectors ({r['duration_s']}s)")
    if failed:
        print(f"\n  Failed:")
        for r in failed:
            print(f"    {r['name']}: {r.get('error', 'unknown')}")

    # Save results
    output = {
        "timestamp": start.isoformat(),
        "elapsed_s": elapsed,
        "results": results,
        "summary": {
            "completed": len(completed),
            "failed": len(failed),
            "total_vectors": total_vectors,
        }
    }
    output_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "import-missing-results.json"
    )
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved: {output_file}")

    # Verify Pinecone state
    print("\n  Verifying Pinecone index...")
    time.sleep(2)
    check_missing()


if __name__ == "__main__":
    main()
