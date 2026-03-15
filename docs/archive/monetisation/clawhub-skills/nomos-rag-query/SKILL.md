---
name: nomos-rag-query
description: Query a production multi-pipeline RAG system with 3 specialized pipelines — Standard (vector search, 87.5% accuracy), Graph (Neo4j entity traversal), and Quantitative (SQL, 95.2% accuracy). Free LLM inference. No API key needed.
version: 1.0.0
metadata:
  openclaw:
    requires:
      env: []
      bins:
        - curl
---

# Nomos RAG Query

Query a production RAG system with 3 specialized pipelines. No API key required. Free tier: 10 req/min.

## Pipelines

| Pipeline | Best For | Accuracy | Database |
|----------|----------|----------|----------|
| **Standard** | Factual questions, definitions | 87.5% (10K questions) | Pinecone — 46,263 Jina v3 embeddings |
| **Graph** | Relationships, entity connections | 40.9% (11K questions) | Neo4j — 79,451 nodes, 219K relations |
| **Quantitative** | Numbers, rankings, comparisons | 95.2% (3.5K questions) | Supabase — 40 PostgreSQL tables |

## Usage

### Step 1: Choose Pipeline

- **Factual question?** → Standard
- **Relationship question?** → Graph
- **Numerical question?** → Quantitative
- **Not sure?** → Standard (highest accuracy)

### Step 2: Send Request

All pipelines accept the same JSON body:

```json
{
  "question": "Your question here",
  "tenant_id": "benchmark"
}
```

### Step 3: Standard Pipeline

```bash
curl -s -X POST \
  "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/rag-multi-index-v3" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is retrieval-augmented generation?", "tenant_id": "benchmark"}'
```

### Step 4: Graph Pipeline

```bash
curl -s -X POST \
  "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/ff622742-6d71-4e91-af71-b5c666088717" \
  -H "Content-Type: application/json" \
  -d '{"question": "What entities are related to deep learning?", "tenant_id": "benchmark"}'
```

### Step 5: Quantitative Pipeline

```bash
curl -s -X POST \
  "https://lbjlincoln-nomos-rag-engine.hf.space/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many companies are in the BTP sector?", "tenant_id": "benchmark"}'
```

### Step 6: Parse Response

```json
{
  "answer": "RAG combines retrieval with generation...",
  "sources": [{"title": "RAG Survey", "score": 0.89}],
  "pipeline": "standard",
  "latency_ms": 2340
}
```

## Error Handling

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Parse `answer` field |
| 404 | Webhook not active | Try another pipeline |
| 429 | Rate limited | Wait 60s, retry |
| 500 | Internal error | Retry once |
| 502/503 | HF Space sleeping | Wait 30s for cold start |

## Rate Limits (Free Tier)

- 10 requests/minute
- 100 requests/day
- Max question: 500 chars

## Health Check

```bash
curl -s "https://lbjlincoln-nomos-rag-engine.hf.space/healthz"
```

## Full Access

Unlimited queries + 61,661 eval questions + n8n workflow source files:

- **Eval Framework** ($127): https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605
- **MEGA BUNDLE** ($497): https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d

## Technical Specs

- Embedding: Jina v3 (1024-dim, self-hosted)
- LLMs: Llama 3.3 70B, Gemma 27B, Trinity Large (free via OpenRouter)
- Orchestration: n8n on 9 Hugging Face Spaces
- Cost per query: $0.00
- Avg latency: 2-12 seconds
