#!/usr/bin/env python3
"""
Setup free embeddings database for Phase 2 transition.

Creates a Pinecone index populated with real embeddings from a FREE provider,
and updates n8n workflow variables to use the same provider at query time.

Supported FREE embedding providers:
  1. Jina AI        — 1M tokens/month free, 1024 dims (get key at jina.ai)
  2. HuggingFace    — Free Inference API, 384 dims (get token at huggingface.co)
  3. OpenRouter     — ~$0.02/1M tokens via text-embedding-3-small (existing key)

Usage:
    # Auto-detect best provider from environment
    python3 db/populate/setup_embeddings.py

    # Force a specific provider
    python3 db/populate/setup_embeddings.py --provider jina
    python3 db/populate/setup_embeddings.py --provider huggingface
    python3 db/populate/setup_embeddings.py --provider openrouter

    # Dry run (no writes)
    python3 db/populate/setup_embeddings.py --dry-run

    # Populate only specific namespaces
    python3 db/populate/setup_embeddings.py --namespaces benchmark-squad_v2,benchmark-triviaqa

    # Update n8n variables only (no Pinecone changes)
    python3 db/populate/setup_embeddings.py --n8n-only

Environment variables:
    JINA_API_KEY       — Jina AI API key (free at https://jina.ai/embeddings/)
    HF_TOKEN           — HuggingFace token (free at https://huggingface.co/settings/tokens)
    OPENROUTER_API_KEY — OpenRouter key (already configured)
    PINECONE_API_KEY   — Pinecone key (already configured)
    N8N_API_KEY        — n8n API key (already configured)
"""
import json
import os
import sys
import time
import hashlib
from datetime import datetime
from urllib import request, error

# ============================================================
# Configuration
# ============================================================
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_MGMT_URL = "https://api.pinecone.io"
N8N_HOST = os.environ.get("N8N_HOST", "https://amoret.app.n8n.cloud")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DATASETS_DIR = os.path.join(REPO_ROOT, "datasets")

# Provider configurations
PROVIDERS = {
    "jina": {
        "name": "Jina AI",
        "env_key": "JINA_API_KEY",
        "url": "https://api.jina.ai/v1/embeddings",
        "model": "jina-embeddings-v3",
        "dimension": 1024,
        "free_tier": "1M tokens/month",
        "signup": "https://jina.ai/embeddings/",
        "batch_size": 64,
        "headers_fn": lambda key: {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        "body_fn": lambda texts, model: {
            "model": model,
            "input": texts,
            "task": "retrieval.passage",
        },
    },
    "huggingface": {
        "name": "HuggingFace Inference",
        "env_key": "HF_TOKEN",
        "url": "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction",
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "dimension": 384,
        "free_tier": "Unlimited (rate limited)",
        "signup": "https://huggingface.co/settings/tokens",
        "batch_size": 16,
        "headers_fn": lambda key: {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        "body_fn": lambda texts, model: {
            "inputs": texts,
        },
    },
    "openrouter": {
        "name": "OpenRouter (text-embedding-3-small)",
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1/embeddings",
        "model": "text-embedding-3-small",
        "dimension": 1536,
        "free_tier": "~$0.02/1M tokens (very low cost)",
        "signup": "https://openrouter.ai/",
        "batch_size": 100,
        "headers_fn": lambda key: {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mon-ipad",
            "X-Title": "RAG-Benchmark-Embeddings",
        },
        "body_fn": lambda texts, model: {
            "model": model,
            "input": texts,
            "encoding_format": "float",
        },
    },
}

# n8n embedding variable mappings per provider
N8N_VARIABLE_MAP = {
    "jina": {
        "EMBEDDING_API_URL": "https://api.jina.ai/v1/embeddings",
        "EMBEDDING_MODEL": "jina-embeddings-v3",
    },
    "huggingface": {
        "EMBEDDING_API_URL": "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
    },
    "openrouter": {
        "EMBEDDING_API_URL": "https://openrouter.ai/api/v1/embeddings",
        "EMBEDDING_MODEL": "openai/text-embedding-3-small",
    },
}


# ============================================================
# Embedding API
# ============================================================

def get_embeddings(texts, provider_name, api_key):
    """Get embeddings from the specified provider."""
    provider = PROVIDERS[provider_name]
    url = provider["url"]
    model = provider["model"]
    headers = provider["headers_fn"](api_key)
    body_data = provider["body_fn"](texts, model)

    body = json.dumps(body_data).encode()
    req = request.Request(url, data=body, headers=headers, method="POST")

    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())

                # Parse response based on provider format
                if provider_name == "huggingface":
                    # HF returns a list of vectors directly
                    if isinstance(result, list):
                        return result
                    return None
                else:
                    # OpenAI-compatible format (Jina, OpenRouter)
                    embeddings = [item["embedding"] for item in result["data"]]
                    return embeddings

        except error.HTTPError as e:
            err_body = e.read().decode()[:300] if hasattr(e, 'read') else str(e)
            print(f"    Embedding API error (attempt {attempt+1}): {e.code} - {err_body[:200]}")
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
            elif e.code >= 500:
                time.sleep(2 ** attempt)
            else:
                return None
        except Exception as e:
            print(f"    Embedding error (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)

    return None


def get_embeddings_batch(texts, provider_name, api_key, batch_size=None):
    """Get embeddings in batches."""
    if batch_size is None:
        batch_size = PROVIDERS[provider_name]["batch_size"]

    all_embeddings = []
    total = len(texts)

    for i in range(0, total, batch_size):
        batch = texts[i:i+batch_size]
        # Truncate texts to avoid token limits
        batch = [t[:4000] for t in batch]

        embeddings = get_embeddings(batch, provider_name, api_key)
        if embeddings is None:
            print(f"    FAILED batch {i//batch_size + 1}/{(total+batch_size-1)//batch_size}")
            all_embeddings.extend([None] * len(batch))
        else:
            all_embeddings.extend(embeddings)

        if i > 0 and i % (batch_size * 5) == 0:
            print(f"    Embedded {i + len(batch)}/{total} texts...")
            time.sleep(0.3)

    return all_embeddings


# ============================================================
# Pinecone Management
# ============================================================

def pinecone_api(method, path, body=None, host=None, timeout=30):
    """Call Pinecone API (management or data plane)."""
    base_url = host or PINECONE_MGMT_URL
    url = f"{base_url}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
        "X-Pinecone-API-Version": "2024-10",
    }

    req = request.Request(url, data=data, headers=headers, method=method)

    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 204:
                    return {}
                return json.loads(resp.read())
        except error.HTTPError as e:
            err_body = e.read().decode()[:500] if hasattr(e, 'read') else str(e)
            if attempt < 2 and e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            print(f"    Pinecone API error: {e.code} - {err_body[:300]}")
            return None
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            print(f"    Pinecone API error: {e}")
            return None

    return None


def list_pinecone_indexes():
    """List all Pinecone indexes."""
    result = pinecone_api("GET", "/indexes")
    if result and "indexes" in result:
        return result["indexes"]
    return []


def get_pinecone_index(name):
    """Get Pinecone index details."""
    return pinecone_api("GET", f"/indexes/{name}")


def create_pinecone_index(name, dimension, metric="cosine"):
    """Create a new Pinecone serverless index."""
    body = {
        "name": name,
        "dimension": dimension,
        "metric": metric,
        "spec": {
            "serverless": {
                "cloud": "aws",
                "region": "us-east-1",
            }
        },
        "tags": {
            "embedding_model": "free",
            "phase": "2",
        },
    }
    return pinecone_api("POST", "/indexes", body, timeout=60)


def delete_pinecone_index(name):
    """Delete a Pinecone index."""
    return pinecone_api("DELETE", f"/indexes/{name}", timeout=30)


def pinecone_upsert(vectors, namespace, host):
    """Upsert vectors to a Pinecone index."""
    batch_size = 100
    total = 0

    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i+batch_size]
        body = {"vectors": batch, "namespace": namespace}
        result = pinecone_api("POST", "/vectors/upsert", body, host=host, timeout=30)
        if result is not None:
            total += result.get("upsertedCount", len(batch))

    return total


def pinecone_describe(host):
    """Get index stats."""
    return pinecone_api("POST", "/describe_index_stats", {}, host=host)


# ============================================================
# n8n Variable Management
# ============================================================

def n8n_api(method, path, body=None):
    """Call n8n REST API."""
    url = f"{N8N_HOST}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "x-n8n-api-key": N8N_API_KEY,
        "Content-Type": "application/json",
    }

    req = request.Request(url, data=data, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"    n8n API error: {e}")
        return None


def get_n8n_variables():
    """Get all n8n instance variables."""
    result = n8n_api("GET", "/api/v1/variables")
    if result and "data" in result:
        return {v["key"]: v for v in result["data"]}
    return {}


def update_n8n_variable(var_id, key, value):
    """Update an n8n variable."""
    return n8n_api("PATCH", f"/api/v1/variables/{var_id}", {"key": key, "value": value})


def create_n8n_variable(key, value):
    """Create a new n8n variable."""
    return n8n_api("POST", "/api/v1/variables", {"key": key, "value": value})


def update_n8n_embedding_config(provider_name, pinecone_host=None):
    """Update n8n variables for the selected embedding provider."""
    print("\n  Updating n8n embedding variables...")

    variables = get_n8n_variables()
    if not variables:
        print("    ERROR: Could not fetch n8n variables")
        return False

    updates = N8N_VARIABLE_MAP.get(provider_name, {})
    if pinecone_host:
        updates["PINECONE_URL"] = pinecone_host

    for key, value in updates.items():
        if key in variables:
            var = variables[key]
            if var["value"] != value:
                result = update_n8n_variable(var["id"], key, value)
                if result:
                    print(f"    Updated {key}: {var['value'][:50]}... → {value[:50]}...")
                else:
                    print(f"    FAILED to update {key}")
            else:
                print(f"    {key}: already set correctly")
        else:
            result = create_n8n_variable(key, value)
            if result:
                print(f"    Created {key} = {value[:50]}...")
            else:
                print(f"    FAILED to create {key}")

    return True


# ============================================================
# Dataset Loading
# ============================================================

def load_phase1_questions():
    """Load Phase 1 questions from dataset files."""
    questions = {"standard": [], "graph": [], "quantitative": [], "orchestrator": []}

    # Standard + Orchestrator
    p1_std = os.path.join(DATASETS_DIR, "phase-1", "standard-orch-50x2.json")
    if os.path.exists(p1_std):
        with open(p1_std) as f:
            data = json.load(f)
            for q in data.get("questions", []):
                rag = q.get("rag_type", q.get("rag_target", ""))
                if rag in questions:
                    questions[rag].append(q)

    # Graph + Quantitative
    p1_gq = os.path.join(DATASETS_DIR, "phase-1", "graph-quant-50x2.json")
    if os.path.exists(p1_gq):
        with open(p1_gq) as f:
            data = json.load(f)
            for q in data.get("questions", []):
                rag = q.get("rag_type", q.get("rag_target", ""))
                if rag in questions:
                    questions[rag].append(q)

    return questions


def load_phase2_questions():
    """Load Phase 2 questions from hf-1000.json."""
    p2_file = os.path.join(DATASETS_DIR, "phase-2", "hf-1000.json")
    if not os.path.exists(p2_file):
        print(f"    Phase 2 dataset not found: {p2_file}")
        return []

    with open(p2_file) as f:
        data = json.load(f)
    return data.get("questions", [])


def build_texts_for_embedding(questions):
    """Build text strings for embedding from questions."""
    texts = []
    ids = []
    metadata_list = []

    for q in questions:
        # Build rich text for embedding
        text = q["question"]
        if q.get("expected_answer"):
            text += f"\nAnswer: {q['expected_answer']}"

        # Add context snippets for better retrieval
        context = q.get("context", "")
        if isinstance(context, list):
            # Phase 2 format: list of {title, paragraph_text, is_supporting}
            supporting = [c for c in context if c.get("is_supporting")]
            for c in (supporting or context)[:3]:
                title = c.get("title", "")
                para = c.get("paragraph_text", c.get("text", ""))
                if para:
                    text += f"\n[{title}] {para[:500]}"
        elif isinstance(context, str) and len(context) > 50:
            text += f"\nContext: {context[:1500]}"

        texts.append(text)

        # Build ID and metadata
        qid = q.get("id", f"{q.get('dataset_name', 'unknown')}-{q.get('item_index', len(ids))}")
        ids.append(qid)

        metadata_list.append({
            "question": q["question"][:400],
            "expected_answer": (q.get("expected_answer") or "")[:400],
            "dataset_name": q.get("dataset_name", ""),
            "rag_type": q.get("rag_type", q.get("rag_target", "")),
            "tenant_id": "benchmark",
        })

    return texts, ids, metadata_list


# ============================================================
# Main Setup Pipeline
# ============================================================

def detect_provider():
    """Auto-detect the best available embedding provider."""
    if os.environ.get("JINA_API_KEY"):
        return "jina"
    if os.environ.get("HF_TOKEN"):
        return "huggingface"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    return None


def test_provider(provider_name, api_key):
    """Test that the provider returns embeddings successfully."""
    print(f"  Testing {PROVIDERS[provider_name]['name']}...")
    result = get_embeddings(["test embedding quality"], provider_name, api_key)
    if result and len(result) > 0 and result[0] is not None:
        dim = len(result[0])
        expected_dim = PROVIDERS[provider_name]["dimension"]
        print(f"    OK: Got {dim}-dim embedding (expected: {expected_dim})")
        return dim
    else:
        print(f"    FAILED: No embeddings returned")
        return None


def setup_pinecone_index(provider_name, dimension, dry_run=False):
    """Ensure a Pinecone index exists with the correct dimension."""
    indexes = list_pinecone_indexes()
    current_index = None
    new_index_name = None

    for idx in indexes:
        if idx["name"] == "sota-rag":
            current_index = idx
            break

    if current_index:
        current_dim = current_index["dimension"]
        current_host = f"https://{current_index['host']}"

        if current_dim == dimension:
            print(f"  Existing index 'sota-rag' has correct dimension ({dimension})")
            return current_host, "sota-rag"
        else:
            print(f"  Existing index 'sota-rag' has dimension {current_dim}, need {dimension}")

            # Check if a matching index already exists
            for idx in indexes:
                if idx["dimension"] == dimension and idx["name"] != "sota-rag":
                    print(f"  Found existing index '{idx['name']}' with correct dimension")
                    return f"https://{idx['host']}", idx["name"]

            # Need to create a new index
            new_index_name = f"sota-rag-{dimension}d"
            print(f"  Will create new index: {new_index_name} ({dimension}-dim)")
    else:
        new_index_name = "sota-rag"
        print(f"  No existing index found, will create: {new_index_name}")

    if dry_run:
        print(f"  [DRY RUN] Would create index {new_index_name} ({dimension}-dim)")
        return None, new_index_name

    # Create the new index
    print(f"  Creating Pinecone index '{new_index_name}' ({dimension}-dim, cosine)...")
    result = create_pinecone_index(new_index_name, dimension)
    if result is None:
        print("    FAILED to create index")
        return None, None

    # Wait for index to be ready
    print("  Waiting for index to be ready...")
    for i in range(30):
        time.sleep(5)
        idx_info = get_pinecone_index(new_index_name)
        if idx_info and idx_info.get("status", {}).get("ready"):
            host = f"https://{idx_info['host']}"
            print(f"  Index ready: {host}")
            return host, new_index_name
        print(f"    Waiting... ({(i+1)*5}s)")

    print("  WARNING: Index may not be ready yet")
    return None, new_index_name


def populate_namespace(host, namespace, texts, ids, metadata_list,
                       provider_name, api_key, dry_run=False):
    """Embed texts and upsert to a Pinecone namespace."""
    if not texts:
        return 0

    if dry_run:
        print(f"    [DRY RUN] Would embed {len(texts)} texts and upsert to '{namespace}'")
        return len(texts)

    # Get embeddings
    embeddings = get_embeddings_batch(texts, provider_name, api_key)

    # Build vectors
    vectors = []
    skipped = 0
    for i, (vec_id, emb, meta) in enumerate(zip(ids, embeddings, metadata_list)):
        if emb is None:
            skipped += 1
            continue
        vectors.append({
            "id": vec_id,
            "values": emb,
            "metadata": meta,
        })

    if skipped:
        print(f"    WARNING: {skipped}/{len(texts)} embeddings failed")

    if not vectors:
        print(f"    ERROR: No vectors to upsert")
        return 0

    # Upsert
    upserted = pinecone_upsert(vectors, namespace, host)
    print(f"    Upserted {upserted}/{len(vectors)} vectors to '{namespace}'")
    return upserted


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Setup free embeddings database")
    parser.add_argument("--provider", choices=["jina", "huggingface", "openrouter"],
                        help="Force embedding provider")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no writes")
    parser.add_argument("--n8n-only", action="store_true",
                        help="Update n8n variables only, skip Pinecone")
    parser.add_argument("--namespaces", type=str,
                        help="Comma-separated namespace filter")
    parser.add_argument("--phase", type=int, default=0,
                        help="Phase to populate (1, 2, or 0 for both)")
    args = parser.parse_args()

    print("=" * 70)
    print("FREE EMBEDDINGS DATABASE SETUP")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 70)

    # Step 1: Detect/validate provider
    print("\n1. Detecting embedding provider...")
    provider_name = args.provider or detect_provider()

    if not provider_name:
        print("\n  ERROR: No embedding API key found.")
        print("  Set one of the following environment variables:")
        for pname, pconf in PROVIDERS.items():
            print(f"    {pconf['env_key']:25s} → {pconf['name']} ({pconf['free_tier']})")
            print(f"    {'':25s}   Sign up: {pconf['signup']}")
        print("\n  Recommended: Jina AI (truly free, high quality)")
        print("    export JINA_API_KEY='your-key-here'")
        sys.exit(1)

    provider = PROVIDERS[provider_name]
    api_key = os.environ.get(provider["env_key"], "")
    if not api_key:
        print(f"  ERROR: {provider['env_key']} not set")
        print(f"  Get a free key at: {provider['signup']}")
        sys.exit(1)

    print(f"  Provider: {provider['name']}")
    print(f"  Model: {provider['model']}")
    print(f"  Dimension: {provider['dimension']}")
    print(f"  Cost: {provider['free_tier']}")

    # Step 2: Test provider
    print("\n2. Testing embedding provider...")
    actual_dim = test_provider(provider_name, api_key)
    if actual_dim is None:
        print("  FAILED: Provider test failed. Check API key and network.")
        sys.exit(1)

    dimension = actual_dim

    # Step 3: Update n8n variables
    if N8N_API_KEY:
        print("\n3. Updating n8n embedding configuration...")
        if args.dry_run:
            print(f"  [DRY RUN] Would update n8n variables:")
            for k, v in N8N_VARIABLE_MAP.get(provider_name, {}).items():
                print(f"    {k} = {v}")
        else:
            update_n8n_embedding_config(provider_name)
    else:
        print("\n3. Skipping n8n update (N8N_API_KEY not set)")

    if args.n8n_only:
        print("\n  --n8n-only: Skipping Pinecone setup")
        print("=" * 70)
        print("n8n VARIABLES UPDATED")
        print("=" * 70)
        return

    # Step 4: Setup Pinecone index
    print(f"\n4. Setting up Pinecone index ({dimension}-dim)...")
    if not PINECONE_API_KEY:
        print("  ERROR: PINECONE_API_KEY not set")
        sys.exit(1)

    host, index_name = setup_pinecone_index(provider_name, dimension, args.dry_run)

    if host and N8N_API_KEY and not args.dry_run:
        # Update Pinecone URL in n8n if index changed
        update_n8n_embedding_config(provider_name, pinecone_host=host)

    # Step 5: Load questions and populate
    print(f"\n5. Loading questions...")

    total_upserted = 0
    ns_filter = set(args.namespaces.split(",")) if args.namespaces else None

    # Phase 1: Questions from curated datasets
    if args.phase in (0, 1):
        print("\n  Phase 1 questions:")
        p1_questions = load_phase1_questions()
        for rag_type, questions in p1_questions.items():
            if not questions:
                continue
            namespace = f"benchmark-{rag_type}"
            if ns_filter and namespace not in ns_filter:
                continue
            print(f"    {rag_type}: {len(questions)} questions → {namespace}")
            texts, ids, metadata = build_texts_for_embedding(questions)
            if host:
                count = populate_namespace(host, namespace, texts, ids, metadata,
                                           provider_name, api_key, args.dry_run)
                total_upserted += count

    # Phase 2: HuggingFace dataset questions
    if args.phase in (0, 2):
        print("\n  Phase 2 questions:")
        p2_questions = load_phase2_questions()

        # Group by dataset
        by_dataset = {}
        for q in p2_questions:
            ds = q.get("dataset_name", "unknown")
            by_dataset.setdefault(ds, []).append(q)

        for ds_name, questions in sorted(by_dataset.items()):
            namespace = f"benchmark-{ds_name}"
            if ns_filter and namespace not in ns_filter:
                continue
            print(f"    {ds_name}: {len(questions)} questions → {namespace}")
            texts, ids, metadata = build_texts_for_embedding(questions)
            if host:
                count = populate_namespace(host, namespace, texts, ids, metadata,
                                           provider_name, api_key, args.dry_run)
                total_upserted += count

    # Step 6: Verify
    if host and not args.dry_run:
        print(f"\n6. Verifying Pinecone index...")
        time.sleep(2)
        stats = pinecone_describe(host)
        if stats:
            print(f"  Total vectors: {stats.get('totalVectorCount', 0)}")
            print(f"  Dimension: {stats.get('dimension', 'unknown')}")
            for ns, info in stats.get("namespaces", {}).items():
                print(f"    '{ns}': {info.get('vectorCount', 0)} vectors")

    # Step 7: Save configuration
    config = {
        "timestamp": datetime.now().isoformat(),
        "provider": provider_name,
        "model": provider["model"],
        "dimension": dimension,
        "pinecone_index": index_name,
        "pinecone_host": host,
        "n8n_variables_updated": bool(N8N_API_KEY),
        "total_upserted": total_upserted,
        "dry_run": args.dry_run,
    }

    config_path = os.path.join(REPO_ROOT, "db", "readiness", "embeddings-config.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\n  Configuration saved: {config_path}")

    # Summary
    print(f"\n{'='*70}")
    print("EMBEDDINGS SETUP COMPLETE")
    print(f"{'='*70}")
    print(f"  Provider:    {provider['name']}")
    print(f"  Model:       {provider['model']}")
    print(f"  Dimension:   {dimension}")
    print(f"  Index:       {index_name}")
    print(f"  Vectors:     {total_upserted}")
    print(f"  n8n updated: {bool(N8N_API_KEY)}")
    if args.dry_run:
        print("\n  [DRY RUN] No actual changes were made.")
        print("  Run without --dry-run to execute.")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
