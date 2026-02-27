# n8n Webhook API Reference

> Last updated: 2026-02-27T16:00:00+00:00

Complete documentation for all n8n webhook endpoints in the Multi-RAG Orchestrator system.

## Base URLs

### 10 HF Space Cluster (distributed load)

| Space | URL | Account | Status |
|-------|-----|---------|--------|
| Space 1 | https://lbjlincoln-nomos-rag-engine.hf.space | LBJLincoln | ACTIVE |
| Space 2 | https://lbjlincoln26-nomos-rag-engine-2.hf.space | LBJLincoln26 | ACTIVE |
| Space 3 | https://lbjlincoln-nomos-rag-engine-3.hf.space | LBJLincoln | ACTIVE |
| Space 4 | https://lbjlincoln26-nomos-rag-engine-4.hf.space | LBJLincoln26 | ACTIVE |
| Space 5 | https://lbjlincoln-nomos-rag-engine-5.hf.space | LBJLincoln | ACTIVE |
| Space 6 | https://lbjlincoln26-nomos-rag-engine-6.hf.space | LBJLincoln26 | ACTIVE |
| Space 7 | https://lbjlincoln-nomos-rag-engine-7.hf.space | LBJLincoln | ACTIVE |
| Space 8 | https://lbjlincoln26-nomos-rag-engine-8.hf.space | LBJLincoln26 | ACTIVE |
| Space 9 | https://lbjlincoln-nomos-rag-engine-9.hf.space | LBJLincoln | ACTIVE |
| Space 10 | https://lbjlincoln26-nomos-rag-engine-10.hf.space | LBJLincoln26 | ACTIVE |

**Load balancing strategy**: Round-robin or least-loaded.

**Environment variable**: `N8N_HOST` (defaults to Space 1).

---

## Core RAG Pipelines

### 1. Standard RAG (Multi-Index Pinecone)

**Endpoint**: `/webhook/rag-multi-index-v3`

**Method**: `POST`

**Request format**:
```json
{
  "query": "What is the capital of Japan?"
}
```

**Response format**:
```json
{
  "answer": "Tokyo is the capital of Japan...",
  "sources": [
    {
      "text": "Tokyo has been Japan's capital since...",
      "score": 0.89,
      "metadata": {
        "dataset": "squad_v2",
        "id": "5a8b4d..."
      }
    }
  ],
  "pipeline": "standard",
  "execution_time_ms": 1234
}
```

**Database**: Pinecone `sota-rag-jina-1024` (1024-dim, Jina embeddings v3)

**Timeout**: 90s

**Batch size**: 10 questions (5 concurrent max)

**Example curl**:
```bash
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the capital of Japan?"}'
```

---

### 2. Graph RAG (Neo4j + Supabase)

**Endpoint**: `/webhook/ff622742-6d71-4e91-af71-b5c666088717`

**Method**: `POST`

**Request format**:
```json
{
  "query": "Who founded Microsoft?"
}
```

**Response format**:
```json
{
  "answer": "Microsoft was founded by Bill Gates and Paul Allen in 1975...",
  "graph_context": [
    {
      "entity": "Bill Gates",
      "relationship": "FOUNDED",
      "target": "Microsoft",
      "year": 1975
    }
  ],
  "sources": [
    {
      "text": "Bill Gates and Paul Allen founded Microsoft...",
      "score": 0.92
    }
  ],
  "pipeline": "graph",
  "execution_time_ms": 2345
}
```

**Databases**:
- Neo4j Aura (19,788 nodes, 76,717 relationships)
- Supabase (structured data)

**Timeout**: 90s

**Batch size**: 5 questions (3 concurrent max)

**Example curl**:
```bash
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717" \
  -H "Content-Type: application/json" \
  -d '{"query":"Who founded Microsoft?"}'
```

---

### 3. Quantitative RAG (SQL + Supabase)

**Endpoint**: `/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9`

**Method**: `POST`

**Request format**:
```json
{
  "query": "What was Apple revenue in 2023?"
}
```

**Response format**:
```json
{
  "answer": "Apple's revenue in 2023 was $394.3 billion...",
  "sql_query": "SELECT revenue FROM companies WHERE name='Apple' AND year=2023",
  "numerical_results": [
    {
      "metric": "revenue",
      "value": 394300000000,
      "unit": "USD",
      "year": 2023
    }
  ],
  "sources": [
    {
      "text": "Apple Inc. reported total revenue of $394.3B...",
      "score": 0.95
    }
  ],
  "pipeline": "quantitative",
  "execution_time_ms": 1567
}
```

**Database**: Supabase (structured tables with numerical data)

**Timeout**: 120s

**Batch size**: 3 questions (1 concurrent)

**Example curl**:
```bash
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" \
  -H "Content-Type: application/json" \
  -d '{"query":"What was Apple revenue in 2023?"}'
```

---

### 4. Orchestrator (Meta-pipeline)

**Endpoint**: `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0`

**Method**: `POST`

**Request format**:
```json
{
  "query": "What is the capital of Japan?"
}
```

**Response format**:
```json
{
  "answer": "Tokyo is the capital of Japan...",
  "pipeline_used": "standard",
  "confidence": 0.89,
  "execution_time_ms": 1456
}
```

**Logic**: Routes query to best pipeline (Standard, Graph, or Quantitative) based on intent classification.

**Timeout**: 180s

**Batch size**: 2 questions (1 concurrent)

**Example curl**:
```bash
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the capital of Japan?"}'
```

---

## Support Workflows

### 5. Dashboard Status API

**Endpoint**: `/webhook/dashboard-status`

**Method**: `GET` or `POST`

**Response format**:
```json
{
  "status": "operational",
  "pipelines": {
    "standard": {"status": "up", "latency_ms": 1234},
    "graph": {"status": "up", "latency_ms": 2345},
    "quantitative": {"status": "up", "latency_ms": 1567},
    "orchestrator": {"status": "up", "latency_ms": 1456}
  },
  "databases": {
    "pinecone": {"status": "up", "vectors": 10411},
    "neo4j": {"status": "up", "nodes": 19788, "relationships": 76717},
    "supabase": {"status": "up", "tables": 40, "rows": 17000}
  },
  "timestamp": "2026-02-27T16:00:00Z"
}
```

---

### 6. Data Ingestion

**Endpoint**: `/webhook/data-ingestion-v3`

**Method**: `POST`

**Request format**:
```json
{
  "dataset": "squad_v2",
  "action": "ingest",
  "batch_size": 100
}
```

**Response format**:
```json
{
  "status": "success",
  "records_ingested": 100,
  "total_vectors": 10511,
  "execution_time_ms": 45678
}
```

---

### 7. Enrichment

**Endpoint**: `/webhook/enrichment-v3`

**Method**: `POST`

**Request format**:
```json
{
  "dataset": "squad_v2",
  "action": "enrich",
  "enrichment_type": "entities"
}
```

---

### 8. Benchmark

**Endpoint**: `/webhook/benchmark-v3`

**Method**: `POST`

**Request format**:
```json
{
  "pipeline": "standard",
  "questions": 50,
  "label": "Phase2-relaunch"
}
```

---

## PME Workflows

### 9. PME Gateway (Multi-Canal)

**Endpoint**: `/webhook/pme-assistant-gateway`

**Method**: `POST`

**Request format**:
```json
{
  "query": "Quels sont les derniers documents dans le Drive?",
  "channel": "api"
}
```

**Supported channels**: `api`, `whatsapp`, `telegram`, `slack`

---

### 10. PME Action Executor

**Endpoint**: `/webhook/pme-action-executor`

**Method**: `POST`

**Request format**:
```json
{
  "action": "calendar_add",
  "params": {
    "title": "Réunion client",
    "date": "2026-03-01T14:00:00Z"
  }
}
```

---

## Error Codes

| HTTP Code | Meaning | Common Causes |
|-----------|---------|---------------|
| 200 | Success | Request processed successfully |
| 400 | Bad Request | Invalid JSON, missing `query` field |
| 404 | Not Found | Webhook path incorrect or workflow inactive |
| 500 | Internal Server Error | n8n node error, database connection issue |
| 503 | Service Unavailable | n8n overloaded, rate limit exceeded |
| 504 | Gateway Timeout | Execution exceeded timeout (90s/120s/180s) |

**Common error response**:
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Missing required field: query",
  "timestamp": "2026-02-27T16:00:00Z"
}
```

---

## Rate Limits

| Pipeline | Max concurrent | Batch size | Timeout |
|----------|---------------|-----------|---------|
| Standard | 5 | 10 | 90s |
| Graph | 3 | 5 | 90s |
| Quantitative | 1 | 3 | 120s |
| Orchestrator | 1 | 2 | 180s |

**10 HF Spaces**: Distribute load across 10 spaces to increase total throughput.

---

## Python Examples

### Basic webhook call

```python
import urllib.request
import json

def call_webhook(url, question, timeout=120):
    payload = json.dumps({"query": question}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

# Example
result = call_webhook(
    "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3",
    "What is the capital of Japan?"
)
print(result)
```

### Parallel calls with load balancing

```python
import concurrent.futures
import os

SPACES = [
    os.getenv("N8N_HOST_1"),
    os.getenv("N8N_HOST_2"),
    # ... up to N8N_HOST_10
]

def call_with_load_balancing(questions, webhook_path):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i, question in enumerate(questions):
            space_url = SPACES[i % len(SPACES)]
            url = f"{space_url}{webhook_path}"
            futures.append(executor.submit(call_webhook, url, question))

        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    return results
```

---

## Common Pitfalls

| Issue | Solution |
|-------|----------|
| Field name `question` instead of `query` | Use `{"query": "..."}` |
| Timeout on complex questions | Increase timeout to 120s or 180s |
| 503 Service Unavailable | Reduce concurrency, use load balancing |
| Empty response body | Check workflow is activated |
| 404 on webhook | Verify webhook path matches workflow |
| Credentials not found | Check n8n credential IDs match env vars |

---

## Testing

### Quick test (5 questions)

```bash
cd /home/termius/mon-ipad
source .env.local
python3 eval/quick-test.py --pipeline standard --questions 5
```

### Full eval (1000 questions)

```bash
python3 eval/run-eval-parallel.py --pipeline standard --label "Phase2-test"
```

### Manual curl test

```bash
curl -X POST "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the capital of Japan?"}' \
  -v
```

---

**NOTE**: Always use `query` field (NOT `question`). This is the most common error.

**Maintained by**: mon-ipad (tour de contrôle centrale)

**Related docs**:
- `directives/n8n-endpoints.md` — Full endpoint reference
- `technicals/debug/knowledge-base.md` — Section 0 (webhook patterns)
- `technicals/debug/fixes-library.md` — Common fixes
