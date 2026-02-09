#!/usr/bin/env python3
"""
MCP Server — Jina AI Embeddings + Pinecone Vector Management

Provides tools for generating embeddings with Jina AI's free tier
and managing Pinecone vector indexes. Designed for the Multi-RAG
Orchestrator benchmark pipeline.

Free: Jina AI gives 10M tokens free (no credit card needed).
Get your key at: https://jina.ai/api-dashboard/key-manager

Usage (stdio transport — default for Claude Code):
    python3 mcp/jina-embeddings-server.py

Environment:
    JINA_API_KEY       — Required. Free at https://jina.ai/
    PINECONE_API_KEY   — For vector operations
    N8N_API_KEY        — For updating n8n workflow variables
    N8N_HOST           — n8n cloud URL (default: https://amoret.app.n8n.cloud)
"""
import json
import os
import asyncio
from datetime import datetime
from urllib import request, error
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ============================================================
# Configuration
# ============================================================
JINA_API_KEY = os.environ.get("JINA_API_KEY", "")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_MGMT_URL = "https://api.pinecone.io"
N8N_HOST = os.environ.get("N8N_HOST", "https://amoret.app.n8n.cloud")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

JINA_EMBEDDING_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v3"
JINA_DIMENSION = 1024

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

server = Server("jina-embeddings")


# ============================================================
# HTTP helpers (sync — run in executor for async context)
# ============================================================

def http_request(url, method="GET", body=None, headers=None, timeout=30):
    """Make an HTTP request and return parsed JSON."""
    data = json.dumps(body).encode() if body else None
    req = request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 204:
                return {}
            return json.loads(resp.read())
    except error.HTTPError as e:
        err_body = e.read().decode()[:500] if hasattr(e, 'read') else ""
        return {"error": True, "status": e.code, "message": err_body}
    except Exception as e:
        return {"error": True, "message": str(e)}


def jina_embed(texts, task="retrieval.passage", dimensions=JINA_DIMENSION):
    """Generate embeddings using Jina AI API."""
    if not JINA_API_KEY:
        return {"error": True, "message": "JINA_API_KEY not set. Get free key at https://jina.ai/api-dashboard/key-manager"}

    headers = {
        "Authorization": f"Bearer {JINA_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": JINA_MODEL,
        "input": texts[:64],  # Jina batch limit
        "task": task,
        "dimensions": dimensions,
        "normalized": True,
    }
    return http_request(JINA_EMBEDDING_URL, "POST", body, headers, timeout=60)


def pinecone_mgmt(method, path, body=None):
    """Pinecone management API call."""
    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
        "X-Pinecone-API-Version": "2024-10",
    }
    return http_request(f"{PINECONE_MGMT_URL}{path}", method, body, headers)


def pinecone_data(method, path, body, host):
    """Pinecone data plane API call."""
    headers = {
        "Api-Key": PINECONE_API_KEY,
        "Content-Type": "application/json",
    }
    return http_request(f"{host}{path}", method, body, headers, timeout=30)


def n8n_api(method, path, body=None):
    """n8n REST API call."""
    headers = {
        "x-n8n-api-key": N8N_API_KEY,
        "Content-Type": "application/json",
    }
    return http_request(f"{N8N_HOST}{path}", method, body, headers)


# ============================================================
# MCP Tool Definitions
# ============================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="jina_embed",
            description="Generate embeddings for a list of texts using Jina AI's free API (jina-embeddings-v3, 1024-dim). Returns vectors ready for Pinecone upsert. Free: 10M tokens/month.",
            inputSchema={
                "type": "object",
                "properties": {
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of texts to embed (max 64 per call)",
                        "maxItems": 64,
                    },
                    "task": {
                        "type": "string",
                        "enum": ["retrieval.passage", "retrieval.query", "text-matching"],
                        "default": "retrieval.passage",
                        "description": "Task type: 'retrieval.passage' for indexing, 'retrieval.query' for search queries",
                    },
                    "dimensions": {
                        "type": "integer",
                        "default": 1024,
                        "description": "Output dimension (32-1024, default 1024)",
                    },
                },
                "required": ["texts"],
            },
        ),
        Tool(
            name="pinecone_index_status",
            description="Get the status of a Pinecone index: dimensions, vector count, namespace breakdown. Also lists all available indexes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "index_name": {
                        "type": "string",
                        "default": "sota-rag",
                        "description": "Name of the Pinecone index",
                    },
                },
            },
        ),
        Tool(
            name="pinecone_create_index",
            description="Create a new Pinecone serverless index with the specified dimension. For Jina embeddings v3, use dimension=1024.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Index name (e.g., 'sota-rag-1024')",
                    },
                    "dimension": {
                        "type": "integer",
                        "default": 1024,
                        "description": "Vector dimension (must match embedding model)",
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["cosine", "euclidean", "dotproduct"],
                        "default": "cosine",
                    },
                },
                "required": ["name", "dimension"],
            },
        ),
        Tool(
            name="pinecone_upsert",
            description="Upsert vectors to a Pinecone namespace. Takes pre-computed embeddings and metadata. Use jina_embed first to generate vectors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "index_host": {
                        "type": "string",
                        "description": "Pinecone index host URL (e.g., https://sota-rag-xxx.svc.pinecone.io)",
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Target namespace (e.g., 'benchmark-squad_v2')",
                    },
                    "vectors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "values": {"type": "array", "items": {"type": "number"}},
                                "metadata": {"type": "object"},
                            },
                            "required": ["id", "values"],
                        },
                        "description": "Vectors to upsert (max 100 per call)",
                        "maxItems": 100,
                    },
                },
                "required": ["index_host", "namespace", "vectors"],
            },
        ),
        Tool(
            name="embed_and_upsert",
            description="All-in-one: embed texts with Jina AI and upsert to Pinecone in one operation. Handles batching automatically. Perfect for populating a namespace from question data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "index_host": {
                        "type": "string",
                        "description": "Pinecone index host URL",
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Target namespace",
                    },
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                                "metadata": {"type": "object"},
                            },
                            "required": ["id", "text"],
                        },
                        "description": "Items to embed and upsert. Each item needs an id and text.",
                    },
                    "task": {
                        "type": "string",
                        "default": "retrieval.passage",
                        "description": "Embedding task type",
                    },
                },
                "required": ["index_host", "namespace", "items"],
            },
        ),
        Tool(
            name="update_n8n_embedding_config",
            description="Update n8n workflow variables to use Jina AI for embeddings. Sets EMBEDDING_API_URL and EMBEDDING_MODEL in n8n instance variables so all workflows use Jina.",
            inputSchema={
                "type": "object",
                "properties": {
                    "embedding_url": {
                        "type": "string",
                        "default": "https://api.jina.ai/v1/embeddings",
                    },
                    "embedding_model": {
                        "type": "string",
                        "default": "jina-embeddings-v3",
                    },
                    "pinecone_host": {
                        "type": "string",
                        "description": "New Pinecone host URL (optional, only if index changed)",
                    },
                },
            },
        ),
        Tool(
            name="load_dataset_questions",
            description="Load questions from Phase 1 or Phase 2 dataset files. Returns questions with text and metadata ready for embedding.",
            inputSchema={
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "integer",
                        "enum": [1, 2],
                        "description": "Phase number (1 = 200 curated questions, 2 = 1000 HF questions)",
                    },
                    "dataset_filter": {
                        "type": "string",
                        "description": "Optional: filter by dataset name (e.g., 'musique', 'finqa')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max questions to return",
                        "default": 50,
                    },
                },
                "required": ["phase"],
            },
        ),
        Tool(
            name="setup_status",
            description="Check the current embeddings setup status: Jina API connectivity, Pinecone index state, n8n configuration, and readiness for Phase 2.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


# ============================================================
# Tool Implementations
# ============================================================

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    loop = asyncio.get_event_loop()

    if name == "jina_embed":
        result = await loop.run_in_executor(None, lambda: _jina_embed(arguments))
    elif name == "pinecone_index_status":
        result = await loop.run_in_executor(None, lambda: _pinecone_status(arguments))
    elif name == "pinecone_create_index":
        result = await loop.run_in_executor(None, lambda: _pinecone_create(arguments))
    elif name == "pinecone_upsert":
        result = await loop.run_in_executor(None, lambda: _pinecone_upsert(arguments))
    elif name == "embed_and_upsert":
        result = await loop.run_in_executor(None, lambda: _embed_and_upsert(arguments))
    elif name == "update_n8n_embedding_config":
        result = await loop.run_in_executor(None, lambda: _update_n8n(arguments))
    elif name == "load_dataset_questions":
        result = await loop.run_in_executor(None, lambda: _load_questions(arguments))
    elif name == "setup_status":
        result = await loop.run_in_executor(None, lambda: _setup_status(arguments))
    else:
        result = {"error": f"Unknown tool: {name}"}

    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


def _jina_embed(args):
    texts = args.get("texts", [])
    task = args.get("task", "retrieval.passage")
    dims = args.get("dimensions", JINA_DIMENSION)

    if not texts:
        return {"error": "No texts provided"}

    result = jina_embed(texts, task, dims)
    if result.get("error"):
        return result

    embeddings = []
    for item in result.get("data", []):
        embeddings.append({
            "index": item.get("index"),
            "dimension": len(item.get("embedding", [])),
            "embedding": item.get("embedding"),
        })

    return {
        "success": True,
        "count": len(embeddings),
        "dimension": embeddings[0]["dimension"] if embeddings else 0,
        "model": result.get("model", JINA_MODEL),
        "usage": result.get("usage", {}),
        "embeddings": embeddings,
    }


def _pinecone_status(args):
    index_name = args.get("index_name", "sota-rag")

    # List all indexes
    indexes = pinecone_mgmt("GET", "/indexes")
    if indexes.get("error"):
        return {"error": f"Failed to list indexes: {indexes.get('message', '')}"}

    all_indexes = indexes.get("indexes", [])
    target = None
    for idx in all_indexes:
        if idx["name"] == index_name:
            target = idx
            break

    result = {
        "all_indexes": [
            {"name": i["name"], "dimension": i["dimension"], "host": i["host"],
             "status": i.get("status", {}).get("state", "unknown")}
            for i in all_indexes
        ],
    }

    if target:
        host = f"https://{target['host']}"
        stats = pinecone_data("POST", "/describe_index_stats", {}, host)
        if not stats.get("error"):
            result["target_index"] = {
                "name": index_name,
                "dimension": target["dimension"],
                "host": host,
                "total_vectors": stats.get("totalVectorCount", 0),
                "namespaces": {
                    ns: info.get("vectorCount", 0)
                    for ns, info in stats.get("namespaces", {}).items()
                },
            }
    else:
        result["target_index"] = None
        result["message"] = f"Index '{index_name}' not found"

    return result


def _pinecone_create(args):
    name = args["name"]
    dimension = args["dimension"]
    metric = args.get("metric", "cosine")

    body = {
        "name": name,
        "dimension": dimension,
        "metric": metric,
        "spec": {"serverless": {"cloud": "aws", "region": "us-east-1"}},
        "tags": {"embedding_model": "jina-embeddings-v3", "phase": "2"},
    }
    result = pinecone_mgmt("POST", "/indexes", body)
    if result.get("error"):
        return {"error": f"Failed to create index: {result.get('message', '')}"}

    return {
        "success": True,
        "name": name,
        "dimension": dimension,
        "host": result.get("host", ""),
        "message": f"Index '{name}' created. Wait ~60s for it to become ready.",
    }


def _pinecone_upsert(args):
    host = args["index_host"]
    namespace = args["namespace"]
    vectors = args["vectors"]

    result = pinecone_data("POST", "/vectors/upsert",
                           {"vectors": vectors, "namespace": namespace}, host)
    if result.get("error"):
        return {"error": f"Upsert failed: {result.get('message', '')}"}

    return {
        "success": True,
        "upserted": result.get("upsertedCount", len(vectors)),
        "namespace": namespace,
    }


def _embed_and_upsert(args):
    host = args["index_host"]
    namespace = args["namespace"]
    items = args["items"]
    task = args.get("task", "retrieval.passage")

    if not items:
        return {"error": "No items provided"}

    total_upserted = 0
    batch_size = 64
    errors = []

    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        texts = [item["text"][:4000] for item in batch]

        # Embed
        emb_result = jina_embed(texts, task)
        if emb_result.get("error"):
            errors.append(f"Batch {i//batch_size}: {emb_result.get('message', '')}")
            continue

        embeddings = emb_result.get("data", [])
        if len(embeddings) != len(batch):
            errors.append(f"Batch {i//batch_size}: got {len(embeddings)} embeddings for {len(batch)} texts")
            continue

        # Build vectors
        vectors = []
        for item, emb_data in zip(batch, embeddings):
            vec = {
                "id": item["id"],
                "values": emb_data["embedding"],
            }
            if item.get("metadata"):
                vec["metadata"] = item["metadata"]
            vectors.append(vec)

        # Upsert in sub-batches of 100
        for j in range(0, len(vectors), 100):
            sub = vectors[j:j+100]
            up_result = pinecone_data("POST", "/vectors/upsert",
                                      {"vectors": sub, "namespace": namespace}, host)
            if up_result.get("error"):
                errors.append(f"Upsert batch {j//100}: {up_result.get('message', '')}")
            else:
                total_upserted += up_result.get("upsertedCount", len(sub))

    return {
        "success": total_upserted > 0,
        "total_embedded": len(items),
        "total_upserted": total_upserted,
        "namespace": namespace,
        "errors": errors if errors else None,
    }


def _update_n8n(args):
    if not N8N_API_KEY:
        return {"error": "N8N_API_KEY not set"}

    emb_url = args.get("embedding_url", "https://api.jina.ai/v1/embeddings")
    emb_model = args.get("embedding_model", "jina-embeddings-v3")
    pc_host = args.get("pinecone_host")

    # Get current variables
    vars_result = n8n_api("GET", "/api/v1/variables")
    if vars_result.get("error"):
        return {"error": f"Failed to get n8n variables: {vars_result.get('message', '')}"}

    var_map = {v["key"]: v for v in vars_result.get("data", [])}
    updates = {}

    for key, value in [("EMBEDDING_API_URL", emb_url), ("EMBEDDING_MODEL", emb_model)]:
        if key in var_map:
            old_val = var_map[key]["value"]
            if old_val != value:
                result = n8n_api("PATCH", f"/api/v1/variables/{var_map[key]['id']}",
                                 {"key": key, "value": value})
                updates[key] = {"old": old_val, "new": value, "success": not result.get("error")}
            else:
                updates[key] = {"status": "already_correct", "value": value}
        else:
            result = n8n_api("POST", "/api/v1/variables", {"key": key, "value": value})
            updates[key] = {"created": True, "value": value, "success": not result.get("error")}

    if pc_host and "PINECONE_URL" in var_map:
        old_val = var_map["PINECONE_URL"]["value"]
        if old_val != pc_host:
            result = n8n_api("PATCH", f"/api/v1/variables/{var_map['PINECONE_URL']['id']}",
                             {"key": "PINECONE_URL", "value": pc_host})
            updates["PINECONE_URL"] = {"old": old_val, "new": pc_host, "success": not result.get("error")}

    return {"success": True, "updates": updates}


def _load_questions(args):
    phase = args["phase"]
    ds_filter = args.get("dataset_filter")
    limit = args.get("limit", 50)

    questions = []

    if phase == 1:
        for fname in ["standard-orch-50x2.json", "graph-quant-50x2.json"]:
            path = os.path.join(REPO_ROOT, "datasets", "phase-1", fname)
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
                for q in data.get("questions", []):
                    if ds_filter and q.get("rag_type", q.get("rag_target")) != ds_filter:
                        continue
                    questions.append(q)
    elif phase == 2:
        path = os.path.join(REPO_ROOT, "datasets", "phase-2", "hf-1000.json")
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            for q in data.get("questions", []):
                if ds_filter and q.get("dataset_name") != ds_filter:
                    continue
                questions.append(q)

    questions = questions[:limit]

    # Build items ready for embedding
    items = []
    for q in questions:
        text = q["question"]
        if q.get("expected_answer"):
            text += f"\nAnswer: {q['expected_answer']}"
        context = q.get("context", "")
        if isinstance(context, list):
            for c in context[:3]:
                para = c.get("paragraph_text", c.get("text", ""))
                if para:
                    text += f"\n{para[:500]}"
        elif isinstance(context, str) and len(context) > 50:
            text += f"\nContext: {context[:1500]}"

        items.append({
            "id": q.get("id", f"q-{len(items)}"),
            "text": text,
            "question": q["question"],
            "dataset": q.get("dataset_name", ""),
            "rag_type": q.get("rag_type", q.get("rag_target", "")),
            "metadata": {
                "question": q["question"][:400],
                "expected_answer": (q.get("expected_answer") or "")[:400],
                "dataset_name": q.get("dataset_name", ""),
                "rag_type": q.get("rag_type", q.get("rag_target", "")),
                "tenant_id": "benchmark",
            },
        })

    return {
        "phase": phase,
        "total_loaded": len(items),
        "datasets": list(set(i["dataset"] for i in items if i["dataset"])),
        "items": items,
    }


def _setup_status(args):
    status = {
        "timestamp": datetime.now().isoformat(),
        "jina": {"configured": bool(JINA_API_KEY)},
        "pinecone": {"configured": bool(PINECONE_API_KEY)},
        "n8n": {"configured": bool(N8N_API_KEY)},
    }

    # Test Jina
    if JINA_API_KEY:
        result = jina_embed(["connectivity test"], "retrieval.passage")
        if not result.get("error"):
            dim = len(result.get("data", [{}])[0].get("embedding", []))
            status["jina"]["connected"] = True
            status["jina"]["model"] = JINA_MODEL
            status["jina"]["dimension"] = dim
        else:
            status["jina"]["connected"] = False
            status["jina"]["error"] = result.get("message", "")[:200]
    else:
        status["jina"]["message"] = "Set JINA_API_KEY. Free: https://jina.ai/api-dashboard/key-manager"

    # Check Pinecone
    if PINECONE_API_KEY:
        indexes = pinecone_mgmt("GET", "/indexes")
        if not indexes.get("error"):
            status["pinecone"]["connected"] = True
            status["pinecone"]["indexes"] = [
                {"name": i["name"], "dimension": i["dimension"]}
                for i in indexes.get("indexes", [])
            ]
        else:
            status["pinecone"]["connected"] = False

    # Check n8n
    if N8N_API_KEY:
        vars_result = n8n_api("GET", "/api/v1/variables")
        if not vars_result.get("error"):
            var_map = {v["key"]: v["value"] for v in vars_result.get("data", [])}
            status["n8n"]["connected"] = True
            status["n8n"]["embedding_url"] = var_map.get("EMBEDDING_API_URL", "not set")
            status["n8n"]["embedding_model"] = var_map.get("EMBEDDING_MODEL", "not set")
            status["n8n"]["pinecone_url"] = var_map.get("PINECONE_URL", "not set")
        else:
            status["n8n"]["connected"] = False

    # Check dataset files
    p1_std = os.path.join(REPO_ROOT, "datasets", "phase-1", "standard-orch-50x2.json")
    p1_gq = os.path.join(REPO_ROOT, "datasets", "phase-1", "graph-quant-50x2.json")
    p2 = os.path.join(REPO_ROOT, "datasets", "phase-2", "hf-1000.json")
    status["datasets"] = {
        "phase_1_standard_orch": os.path.exists(p1_std),
        "phase_1_graph_quant": os.path.exists(p1_gq),
        "phase_2_hf_1000": os.path.exists(p2),
    }

    # Readiness assessment
    ready = all([
        status["jina"].get("connected"),
        status["pinecone"].get("connected"),
    ])
    status["ready_for_embedding"] = ready
    if not ready:
        blockers = []
        if not status["jina"].get("connected"):
            blockers.append("Jina API not connected (set JINA_API_KEY)")
        if not status["pinecone"].get("connected"):
            blockers.append("Pinecone API not connected (set PINECONE_API_KEY)")
        status["blockers"] = blockers

    return status


# ============================================================
# Main
# ============================================================

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
