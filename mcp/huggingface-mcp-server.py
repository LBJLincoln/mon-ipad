#!/usr/bin/env python3
"""
MCP Server - Hugging Face Hub Integration
Connecte Claude/Kimi à Hugging Face Hub pour rechercher models, datasets, spaces
"""
import json
import os
import asyncio
from urllib import request, error
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

HF_API_TOKEN = os.environ.get("HF_TOKEN", "")
HF_API_URL = "https://huggingface.co/api"

server = Server("huggingface-hub")


def hf_api(endpoint, params=None):
    """Call Hugging Face API."""
    url = f"{HF_API_URL}{endpoint}"
    if params:
        url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
    
    headers = {}
    if HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {HF_API_TOKEN}"
    
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except error.HTTPError as e:
        return {"error": True, "status": e.code, "message": e.read().decode()[:500]}
    except Exception as e:
        return {"error": True, "message": str(e)}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="hf_search_models",
            description="Search for ML models on Hugging Face Hub by name, task, or library",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "task": {"type": "string", "description": "ML task (e.g., text-generation, image-classification)"},
                    "limit": {"type": "integer", "default": 10, "description": "Max results"}
                }
            }
        ),
        Tool(
            name="hf_search_datasets",
            description="Search for datasets on Hugging Face Hub",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10}
                }
            }
        ),
        Tool(
            name="hf_model_info",
            description="Get detailed information about a specific model",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_id": {"type": "string", "description": "Full model ID (e.g., meta-llama/Llama-2-7b)"}
                },
                "required": ["model_id"]
            }
        ),
        Tool(
            name="hf_list_spaces",
            description="Search for Gradio Spaces on Hugging Face",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10}
                }
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    loop = asyncio.get_event_loop()
    
    if name == "hf_search_models":
        result = await loop.run_in_executor(None, lambda: _search_models(arguments))
    elif name == "hf_search_datasets":
        result = await loop.run_in_executor(None, lambda: _search_datasets(arguments))
    elif name == "hf_model_info":
        result = await loop.run_in_executor(None, lambda: _model_info(arguments))
    elif name == "hf_list_spaces":
        result = await loop.run_in_executor(None, lambda: _list_spaces(arguments))
    else:
        result = {"error": f"Unknown tool: {name}"}
    
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


def _search_models(args):
    query = args.get("query", "")
    task = args.get("task", "")
    limit = args.get("limit", 10)
    
    params = {"limit": limit}
    if task:
        params["filter"] = task
    
    # HF search endpoint
    url = f"{HF_API_URL}/models"
    if query:
        url += f"?search={query}"
    
    data = hf_api("/models", params)
    if data.get("error"):
        return data
    
    models = []
    for item in data[:limit]:
        models.append({
            "id": item.get("id"),
            "downloads": item.get("downloads", 0),
            "likes": item.get("likes", 0),
            "task": item.get("pipeline_tag", "unknown"),
            "library": item.get("library_name", "unknown")
        })
    
    return {"models": models, "count": len(models)}


def _search_datasets(args):
    query = args.get("query", "")
    limit = args.get("limit", 10)
    
    data = hf_api("/datasets", {"search": query, "limit": limit})
    if data.get("error"):
        return data
    
    datasets = []
    for item in data[:limit]:
        datasets.append({
            "id": item.get("id"),
            "downloads": item.get("downloads", 0),
            "likes": item.get("likes", 0),
            "tags": item.get("tags", [])
        })
    
    return {"datasets": datasets, "count": len(datasets)}


def _model_info(args):
    model_id = args["model_id"]
    data = hf_api(f"/models/{model_id}")
    
    if data.get("error"):
        return data
    
    return {
        "id": data.get("id"),
        "downloads": data.get("downloads", 0),
        "likes": data.get("likes", 0),
        "task": data.get("pipeline_tag"),
        "tags": data.get("tags", []),
        "description": data.get("cardData", {}).get("description", "")[:500],
        "url": f"https://huggingface.co/{model_id}"
    }


def _list_spaces(args):
    query = args.get("query", "")
    limit = args.get("limit", 10)
    
    # Spaces API
    url = f"{HF_API_URL}/spaces"
    params = {"limit": limit}
    if query:
        params["search"] = query
    
    data = hf_api("/spaces", params)
    if data.get("error"):
        return data
    
    spaces = []
    for item in data[:limit]:
        spaces.append({
            "id": item.get("id"),
            "likes": item.get("likes", 0),
            "sdk": item.get("sdk", "unknown"),
            "url": f"https://huggingface.co/spaces/{item.get('id')}"
        })
    
    return {"spaces": spaces, "count": len(spaces)}


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
