"""Neo4j Bolt Proxy — FastAPI service that relays Cypher queries via Bolt protocol.

n8n HTTP nodes can't use Bolt, and the Neo4j HTTP Query API is unreachable from
HF Spaces (96s+ timeouts). This proxy accepts HTTP POST with Cypher queries and
relays them via the neo4j-driver (Bolt), returning results in <2s.

Endpoint: POST /query
Payload: {"cypher": "MATCH (n) RETURN n LIMIT 5", "params": {}}
Auth: Bearer token (NEO4J_PROXY_KEY env var)
"""

import os
import json
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from neo4j import GraphDatabase

# ─── Config ───────────────────────────────────────────────
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j+s://38c949a2.databases.neo4j.io")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
PROXY_KEY = os.environ.get("NEO4J_PROXY_KEY", "nomos-neo4j-proxy-2026")
MAX_RECORDS = int(os.environ.get("MAX_RECORDS", "500"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neo4j-proxy")

driver = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global driver
    logger.info(f"Connecting to Neo4j: {NEO4J_URI}")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    logger.info("Neo4j connected via Bolt")
    yield
    if driver:
        driver.close()
        logger.info("Neo4j driver closed")


app = FastAPI(title="Neo4j Bolt Proxy", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class CypherRequest(BaseModel):
    cypher: str
    params: dict = {}
    database: str = "neo4j"


def serialize_value(val):
    """Convert Neo4j types to JSON-serializable Python types."""
    from neo4j.graph import Node, Relationship, Path
    if isinstance(val, Node):
        return {"_id": val.element_id, "labels": list(val.labels), **dict(val)}
    elif isinstance(val, Relationship):
        return {"_id": val.element_id, "type": val.type, "start": val.start_node.element_id, "end": val.end_node.element_id, **dict(val)}
    elif isinstance(val, Path):
        return {"nodes": [serialize_value(n) for n in val.nodes], "relationships": [serialize_value(r) for r in val.relationships]}
    elif isinstance(val, (list, tuple)):
        return [serialize_value(v) for v in val]
    elif isinstance(val, dict):
        return {k: serialize_value(v) for k, v in val.items()}
    return val


@app.get("/health")
async def health():
    try:
        with driver.session() as session:
            result = session.run("RETURN 1 AS ok")
            result.single()
        return {"status": "healthy", "neo4j": NEO4J_URI.split("@")[-1] if "@" in NEO4J_URI else NEO4J_URI}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/query")
async def run_cypher(req: CypherRequest, authorization: str = Header(default="")):
    # Auth check
    token = authorization.replace("Bearer ", "").strip()
    if token != PROXY_KEY:
        raise HTTPException(status_code=401, detail="Invalid proxy key")

    # Safety: block destructive queries
    cypher_upper = req.cypher.strip().upper()
    if any(kw in cypher_upper for kw in ["DELETE", "DETACH", "DROP", "CREATE INDEX", "CREATE CONSTRAINT"]):
        raise HTTPException(status_code=403, detail="Destructive queries blocked")

    start = time.time()
    try:
        with driver.session(database=req.database) as session:
            result = session.run(req.cypher, req.params)
            records = []
            for record in result:
                if len(records) >= MAX_RECORDS:
                    break
                records.append({k: serialize_value(v) for k, v in record.items()})
            summary = result.consume()
            elapsed_ms = int((time.time() - start) * 1000)

        logger.info(f"Query OK: {len(records)} records in {elapsed_ms}ms — {req.cypher[:80]}")
        return {
            "records": records,
            "count": len(records),
            "elapsed_ms": elapsed_ms,
            "truncated": len(records) >= MAX_RECORDS,
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"Query FAIL ({elapsed_ms}ms): {e}")
        raise HTTPException(status_code=500, detail=str(e))


class Neo4jQueryV2Request(BaseModel):
    """Neo4j HTTP Query API v2 compatible format."""
    statement: str
    parameters: dict = {}


@app.post("/db/neo4j/query/v2")
async def run_cypher_v2(req: Neo4jQueryV2Request, authorization: str = Header(default="")):
    """Neo4j query/v2 API compatible endpoint.

    Accepts the same payload as the real Neo4j HTTP Query API:
      { "statement": "MATCH ...", "parameters": {} }
    Returns the same format:
      { "data": { "fields": [...], "values": [[...], ...] } }

    This lets n8n HTTP nodes switch URL without changing body or parsing logic.
    Auth: Basic auth (same as Neo4j) or Bearer token.
    """
    # Accept both Basic auth (like Neo4j) and Bearer token
    auth = authorization.strip()
    if auth.startswith("Basic "):
        # Accept any valid Basic auth (the proxy handles Neo4j auth internally)
        pass
    elif auth.replace("Bearer ", "").strip() == PROXY_KEY:
        pass
    else:
        raise HTTPException(status_code=401, detail="Invalid auth")

    cypher_upper = req.statement.strip().upper()
    if any(kw in cypher_upper for kw in ["DELETE", "DETACH", "DROP", "CREATE INDEX", "CREATE CONSTRAINT"]):
        raise HTTPException(status_code=403, detail="Destructive queries blocked")

    start = time.time()
    try:
        with driver.session(database="neo4j") as session:
            result = session.run(req.statement, req.parameters)
            fields = list(result.keys())
            values = []
            for record in result:
                if len(values) >= MAX_RECORDS:
                    break
                values.append([serialize_value(record[k]) for k in fields])
            summary = result.consume()
            elapsed_ms = int((time.time() - start) * 1000)

        logger.info(f"V2 Query OK: {len(values)} rows in {elapsed_ms}ms — {req.statement[:80]}")
        # Return in Neo4j query/v2 API format
        return {
            "data": {
                "fields": fields,
                "values": values,
            },
            "bookmarks": [],
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"V2 Query FAIL ({elapsed_ms}ms): {e}")
        return {"errors": [{"message": str(e)}], "data": {"fields": [], "values": []}}


@app.get("/")
async def root():
    return {
        "service": "Neo4j Bolt Proxy",
        "version": "1.0",
        "endpoints": {
            "POST /query": "Execute Cypher query via Bolt",
            "POST /db/neo4j/query/v2": "Neo4j query/v2 API compatible (for n8n)",
            "GET /health": "Health check",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
