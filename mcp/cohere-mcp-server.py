#!/usr/bin/env python3
"""
MCP Server - Cohere API Integration
Connecte Claude/Kimi à Cohere pour embeddings, rerank, et generation
"""
import json
import os
import asyncio
from urllib import request, error
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "")
COHERE_API_URL = "https://api.cohere.com/v1"

server = Server("cohere-api")


def cohere_api(endpoint, body):
    """Call Cohere API."""
    if not COHERE_API_KEY:
        return {"error": True, "message": "COHERE_API_KEY not set"}
    
    url = f"{COHERE_API_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {COHERE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = json.dumps(body).encode()
    req = request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except error.HTTPError as e:
        err = e.read().decode()[:500]
        return {"error": True, "status": e.code, "message": err}
    except Exception as e:
        return {"error": True, "message": str(e)}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="cohere_embed",
            description="Generate embeddings using Cohere embed-v4.0 model (1024 dimensions). Free tier: 10K calls/month.",
            inputSchema={
                "type": "object",
                "properties": {
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of texts to embed (max 96)"
                    },
                    "model": {
                        "type": "string",
                        "enum": ["embed-english-v3.0", "embed-multilingual-v3.0", "embed-english-light-v3.0"],
                        "default": "embed-english-v3.0"
                    },
                    "input_type": {
                        "type": "string",
                        "enum": ["search_document", "search_query", "classification", "clustering"],
                        "default": "search_document"
                    }
                },
                "required": ["texts"]
            }
        ),
        Tool(
            name="cohere_rerank",
            description="Rerank documents using Cohere rerank model for better search results",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "documents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Documents to rerank"
                    },
                    "top_n": {"type": "integer", "default": 5, "description": "Number of top results"}
                },
                "required": ["query", "documents"]
            }
        ),
        Tool(
            name="cohere_generate",
            description="Generate text using Cohere Command model",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Text prompt"},
                    "max_tokens": {"type": "integer", "default": 500},
                    "temperature": {"type": "number", "default": 0.7}
                },
                "required": ["prompt"]
            }
        ),
        Tool(
            name="cohere_status",
            description="Check Cohere API status and available models",
            inputSchema={{"type": "object", "properties": {}}}
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    loop = asyncio.get_event_loop()
    
    if name == "cohere_embed":
        result = await loop.run_in_executor(None, lambda: _embed(arguments))
    elif name == "cohere_rerank":
        result = await loop.run_in_executor(None, lambda: _rerank(arguments))
    elif name == "cohere_generate":
        result = await loop.run_in_executor(None, lambda: _generate(arguments))
    elif name == "cohere_status":
        result = await loop.run_in_executor(None, lambda: _status(arguments))
    else:
        result = {"error": f"Unknown tool: {name}"}
    
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _embed(args):
    texts = args.get("texts", [])
    model = args.get("model", "embed-english-v3.0")
    input_type = args.get("input_type", "search_document")
    
    if not texts:
        return {"error": "No texts provided"}
    
    body = {
        "texts": texts[:96],  # Cohere limit
        "model": model,
        "input_type": input_type
    }
    
    result = cohere_api("/embed", body)
    if result.get("error"):
        return result
    
    embeddings = result.get("embeddings", [])
    return {
        "success": True,
        "count": len(embeddings),
        "dimension": len(embeddings[0]) if embeddings else 0,
        "model": model,
        "embeddings": [{"index": i, "embedding": emb} for i, emb in enumerate(embeddings)]
    }


def _rerank(args):
    query = args.get("query", "")
    documents = args.get("documents", [])
    top_n = args.get("top_n", 5)
    
    if not query or not documents:
        return {"error": "Query and documents required"}
    
    body = {
        "query": query,
        "documents": documents,
        "top_n": top_n,
        "model": "rerank-english-v3.0"
    }
    
    result = cohere_api("/rerank", body)
    if result.get("error"):
        return result
    
    results = []
    for item in result.get("results", []):
        results.append({
            "index": item.get("index"),
            "relevance_score": item.get("relevance_score"),
            "document": documents[item.get("index", 0)] if item.get("index", 0) < len(documents) else ""
        })
    
    return {
        "success": True,
        "results": results,
        "total_docs": len(documents)
    }


def _generate(args):
    prompt = args.get("prompt", "")
    max_tokens = args.get("max_tokens", 500)
    temperature = args.get("temperature", 0.7)
    
    body = {
        "message": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "model": "command-r-plus"
    }
    
    result = cohere_api("/chat", body)
    if result.get("error"):
        return result
    
    return {
        "success": True,
        "text": result.get("text", ""),
        "finish_reason": result.get("finish_reason"),
        "usage": result.get("usage", {})
    }


def _status(args):
    # Simple check
    test = cohere_api("/models", {})
    return {
        "configured": bool(COHERE_API_KEY),
        "api_accessible": not test.get("error"),
        "models": ["embed-english-v3.0", "embed-multilingual-v3.0", "rerank-english-v3.0", "command-r-plus"],
        "free_tier_limit": "10K calls/month"
    }


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
